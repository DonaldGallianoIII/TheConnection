"""
Tests for tests/_root.py: a listener started through the harness holds its
lock at the moment it is handed over, `tc health --json` names it, and its
pid is gone once the context exits. Also: no child sees the session's
identity variables, a key set to None is unset for one call, a listener
refuses a name with mail waiting, teardown reaps every child when one
times out, a listener's cleanup failure never replaces the test's own
exception, a fake gives each call its exit code and stderr, start()
children die with the root and read their stdin, and a bare `ssh` or
`codex` hits the refusing stub unless a fake stands in front of it. And:
calls() read after the root exits raises, teardown gives all its children
one shared reap ceiling, a dotted or symlinked PATH entry that leads out
of the temp folder stays behind the stubs, fake_bin refuses a name that is
not a plain word, a listener already up at the first read yields without
sleeping, and start(argv=...) runs that command and dies with the root.

Model:  Claude Opus 5.5 (the GROUND lane agent), 2026-10-14
Status: unreviewed

@interacts  runs ../tc through tests/_root.py under a throwaway TC_ROOT;
            starts `tc wait` children through the harness and relies on it
            to kill them, except in the tests of teardown itself, where the
            test's own cleanup also kills each child by its own pid. Runs a
            probe script in tc's place (by patching _root.TC) to read the
            environment a child gets and to resolve `ssh` and `codex` on
            its PATH. The probe prints only TC_ROOT and the variables that
            carry the PLANTED marker, so no failing assertion can print the
            inherited environment. It runs a resolved tool only when it
            sits inside the root's temp folder, so the real tool never runs
            even when the harness is broken. Calls fakes by absolute path.
            One test writes a decoy `ssh` in its own temporary folder
            beside the root's, and never runs it. Reads /proc/locks and
            /proc/<pid> with its own code, kept apart from the harness's
            reader so a bug in one cannot hide in the other.
@deps       python3 stdlib (contextlib, io, json, os, pathlib, subprocess,
            sys, tempfile, time, types, unittest, unittest.mock);
            tests/_root.py; /bin/sh; Linux only (/proc).
@complexity O(1) per test: one to four children, and one or two `tc
            health` or probe runs (tc health is O(p + k + n) inside tc, see
            tc's header). Under a second each.
@alloc      one TcRoot per test, removed when its context exits. Nothing is
            kept between tests.
"""

import contextlib
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
# Run as `python3 -m unittest tests.test_root` from the repo root, tests/ is
# not on sys.path; under discover it is. Add it once so both work.
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import _root  # noqa: E402  (needs the path line above)

# Long enough that a listener never times out on its own during a test. The
# harness kills it the moment its context exits, so this is a ceiling only.
LISTENER_TIMEOUT_SECONDS = 30
NAME = "b"
# A child the test itself runs (a fake called by path) gets this long; a
# fake answers in well under a second.
CHILD_TIMEOUT_SECONDS = 10
# Variables the harness must keep from every child. Written out here rather
# than read from _root.CHILD_ENV_DROP, so a name dropped from the harness's
# list fails this test instead of shrinking it.
NEVER_IN_A_CHILD = (
    "CODEX_THREAD_ID",
    "CLAUDECODE",
    "CLAUDE_CODE_SESSION_ID",
    "CLAUDE_PID",
    "CLAUDE_CONFIG_DIR",
    "CLAUDE_CODE_MESSAGING_SOCKET",
    "CLAUDE_CODE_MESSAGING_TOKEN",
    "SSH_AUTH_SOCK",
)
# Marks every planted value, so a leak shows up under any name.
PLANTED = "planted-by-test-root"
# A made-up variable with no TC_ prefix and no meaning to tc.
PLAIN_KEY = "HARNESS_TEST_PLAIN_KEY"
# What a refusing stub must exit with and say. Written here, not read from
# the harness, for the same reason as NEVER_IN_A_CHILD.
REFUSED_EXIT = 97
REFUSED_WORDS = "real {name} is not allowed in tests\n"
# The argument the probe passes to a tool it runs.
PROBE_ARG = "probe-arg"
# The longest name fake_bin takes. Written here, not read from the harness's
# pattern, for the same reason as NEVER_IN_A_CHILD.
FAKE_NAME_MAX = 32
# A start(argv=...) child sleeps this long, far past any test, so only
# teardown can end it.
SLEEPER_SECONDS = 30
# A decoy `ssh` outside the root's temp folder. The probe never runs it,
# because it resolves outside that folder; it only has to be found first
# on PATH when the harness is broken.
DECOY_SCRIPT = """#!/bin/sh
# A decoy ssh written by tests/test_root.py. Nothing runs it.
exit 0
"""
# Owner may read, write and run the decoy. Nobody else needs to.
DECOY_MODE = 0o700

# Run in tc's place (the test patches _root.TC), so a test sees what a child
# of the harness gets. argv: the root's temp folder, then tool names. Prints
# {"env": {...}, "tools": {name: what it found}}, where "env" holds only
# TC_ROOT and the variables whose value carries the PLANTED marker. It
# never prints the whole environment: a failing assertion over it would
# write every inherited secret into the test's output. A tool runs only
# when it resolves inside the temp folder (a stub or a fake): a broken
# harness shows up as a path outside it, and the real tool never runs.
PROBE_SCRIPT = """\
import json
import os
import pathlib
import shutil
import subprocess
import sys

base = pathlib.Path(sys.argv[1]).resolve()
tools = {{}}
for name in sys.argv[2:]:
    found = shutil.which(name)
    seen = {{"path": found, "ran": False}}
    if found is not None and base in pathlib.Path(found).resolve().parents:
        done = subprocess.run([found, {arg!r}], stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout={timeout})
        seen.update(ran=True, code=done.returncode, stderr=done.stderr)
    tools[name] = seen
env = {{k: v for k, v in os.environ.items() if k == "TC_ROOT" or {marker!r} in v}}
print(json.dumps({{"env": env, "tools": tools}}))
"""


class Planted(Exception):
    """The test's own failure, raised inside a listener's context.

    @interacts  none.
    @deps       none.
    @complexity O(1).
    @alloc      one message string.
    """


def held_by(path):
    """Pids holding an flock on `path`, read from /proc/locks by this file.

    Written apart from _root.flock_holders on purpose: the test proves the
    harness, so it does not borrow the harness's reader.

    @interacts  stats `path`; reads /proc/locks. Writes nothing.
    @deps       os, pathlib; Linux /proc/locks.
    @complexity O(k) over k lines in /proc/locks, tens on a desktop.
    @alloc      the table's lines and one set, freed on return.
    """
    if not os.path.exists(path):
        return set()
    st = os.stat(path)
    inode = f"{os.major(st.st_dev):02x}:{os.minor(st.st_dev):02x}:{st.st_ino}"
    pids = set()
    for line in pathlib.Path("/proc/locks").read_text().splitlines():
        cols = line.split()
        if "->" in cols:
            continue  # a blocked waiter, not a holder
        if "FLOCK" in cols and inode in cols:
            pids.add(int(cols[cols.index(inode) - 1]))
    return pids


def in_proc(pid):
    """True while /proc has an entry for `pid`: running, or a zombie not yet reaped.

    @interacts  stats /proc/<pid>.
    @deps       pathlib.
    @complexity O(1).
    @alloc      none.
    """
    return pathlib.Path(f"/proc/{pid}").exists()


def kill_own(proc):
    """Kill `proc` by its own pid if it still runs, reap it, close its pipes.

    The cleanup for tests of teardown itself: when the harness under test
    fails to stop a child, this still does, so no test leaves one behind.

    @interacts  SIGKILL to proc.pid only, when it still runs.
    @deps       subprocess.
    @complexity O(1).
    @alloc      releases the child's pipes.
    """
    if proc.poll() is None:
        proc.kill()
    proc.wait(timeout=_root.REAP_CEILING_SECONDS)
    for pipe in (proc.stdin, proc.stdout, proc.stderr):
        if pipe is not None:
            pipe.close()


def probe(root, *tools, env=None):
    """Run PROBE_SCRIPT through root.tc() in tc's place. Return (exit, report, stderr).

    `report` is the parsed JSON, or None when the probe printed none.

    @interacts  writes probe.py in the root's temp folder; patches _root.TC
                for one call; the probe may run a stub or a fake in the
                temp folder, never anything outside it.
    @deps       json, unittest.mock; _root.TcRoot.tc.
    @complexity O(e) over e variables the child has (tens), to filter; it
                prints TC_ROOT and the planted ones only (a handful).
    @alloc      the probe file (removed with the temp folder) and the report.
    """
    script = root.base / "probe.py"
    script.write_text(PROBE_SCRIPT.format(arg=PROBE_ARG, timeout=CHILD_TIMEOUT_SECONDS,
                                          marker=PLANTED),
                      encoding="utf-8")
    with mock.patch.object(_root, "TC", script):
        code, out, err = root.tc(str(root.base), *tools, env=env)
    return code, (json.loads(out) if out.strip() else None), err


class RootTest(unittest.TestCase):
    """The harness: its listener, its env, its teardown, its fakes and stubs.

    @interacts  see the module block.
    @deps       _root.TcRoot.
    @complexity O(1) per test.
    @alloc      one TcRoot per test.
    """

    def test_listener_holds_its_lock_at_yield_and_health_names_it(self):
        """At yield the pid holds mail/to-b/.wait.lock, and tc health --json names it.

        Must reject a harness that yields before the lock is held: the
        first line inside the context reads /proc/locks before anything
        else can run, so a listener still starting up fails it.

        @interacts  one listener; one `tc health --json`.
        @deps       _root.TcRoot.listener, held_by.
        @complexity O(1).
        @alloc      one TcRoot, removed on exit.
        """
        with _root.TcRoot() as root:
            lock = root.path / "mail" / f"to-{NAME}" / ".wait.lock"  # P3 fix round 1b (Claude Opus 5.5, unreviewed): D35
            with root.listener(NAME, LISTENER_TIMEOUT_SECONDS) as pid:
                holders = held_by(lock)
                self.assertIn(pid, holders,
                              f"at yield, pid {pid} does not hold {lock}; holders: {holders}")
                code, out, err = root.tc("health", "--json")
                self.assertEqual(code, 0, f"tc health --json exited {code}: {err}")
                self.assertEqual(json.loads(out)["listeners"].get(NAME), pid,
                                 f"tc health --json did not name pid {pid} for {NAME}:\n{out}")

    def test_listener_pid_is_gone_after_its_context(self):
        """After the context the pid is killed and reaped, and nothing holds the lock.

        Also checks the root's folder is removed once TcRoot exits.

        @interacts  one listener; one `tc health --json` after it stops.
        @deps       _root.TcRoot.listener, held_by, in_proc.
        @complexity O(1).
        @alloc      one TcRoot, removed on exit.
        """
        with _root.TcRoot() as root:
            lock = root.path / "mail" / f"to-{NAME}" / ".wait.lock"  # P3 fix round 1b (Claude Opus 5.5, unreviewed): D35
            with root.listener(NAME, LISTENER_TIMEOUT_SECONDS) as pid:
                self.assertTrue(in_proc(pid), f"pid {pid} not in /proc while its context is open")
            self.assertFalse(in_proc(pid),
                             f"pid {pid} still in /proc after its context: running, or a zombie")
            self.assertNotIn(pid, held_by(lock), f"pid {pid} still holds {lock}")
            code, out, err = root.tc("health", "--json")
            self.assertEqual(code, 0, f"tc health --json exited {code}: {err}")
            listeners = json.loads(out)["listeners"]
            self.assertIn(NAME, listeners, f"tc health --json lost the lock file for {NAME}:\n{out}")
            self.assertIsNone(listeners[NAME], f"tc health --json still names a pid for {NAME}:\n{out}")
        self.assertFalse(root.path.exists(), f"{root.path} left behind after TcRoot exited")

    def test_identity_variables_never_reach_a_child(self):
        """The eight identity, secret and agent variables, and TC_*, are gone in a child.

        Plants each in os.environ around the root, then reads the child's
        environment through the probe. Must reject a harness that drops
        only TC_* (the session's identity would reach every test).

        @interacts  one probe run through root.tc().
        @deps       probe, unittest.mock.patch.dict.
        @complexity O(e) over e variables the child sees.
        @alloc      one TcRoot, removed on exit.
        """
        planted = {key: f"{PLANTED}-{key}" for key in NEVER_IN_A_CHILD}
        planted["TC_CACHE_TTL_SECONDS"] = f"{PLANTED}-ttl"
        with mock.patch.dict(os.environ, planted):
            with _root.TcRoot() as root:
                code, report, err = probe(root)
                where = str(root.path)
        self.assertEqual(code, 0, f"probe exited {code}: {err}")
        seen = report["env"]
        leaked = {key: value for key, value in seen.items() if PLANTED in value}
        self.assertEqual(leaked, {}, f"planted variables reached the child: {leaked}")
        self.assertEqual(seen.get("TC_ROOT"), where, f"TC_ROOT in the child: {seen.get('TC_ROOT')!r}")

    def test_none_unsets_a_key_for_one_call(self):
        """env={key: None} unsets that key for one call; the next call has it again.

        Must reject a harness that skips None (the key would stay set).

        @interacts  two probe runs through root.tc().
        @deps       probe, unittest.mock.patch.dict.
        @complexity O(e) per run.
        @alloc      one TcRoot, removed on exit.
        """
        with mock.patch.dict(os.environ, {PLAIN_KEY: PLANTED}):
            with _root.TcRoot() as root:
                code1, unset, err1 = probe(root, env={PLAIN_KEY: None})
                code2, kept, err2 = probe(root)
        self.assertEqual((code1, code2), (0, 0), f"probe exits {code1}, {code2}: {err1} {err2}")
        self.assertNotIn(PLAIN_KEY, unset["env"], f"{PLAIN_KEY} still set with env={{key: None}}")
        self.assertEqual(kept["env"].get(PLAIN_KEY), PLANTED,
                         f"{PLAIN_KEY} missing on the next call: None must unset it for one call only")

    def test_listener_refuses_a_name_with_mail_waiting(self):
        """With mail already in to-b, listener("b") raises before starting any tc wait.

        Must reject a harness that starts the wait anyway: that child exits
        0 at once, and a poll that lands while it holds the lock yields a
        pid about to die.

        @interacts  one `tc send`; no listener child.
        @deps       _root.TcRoot.listener.
        @complexity O(1).
        @alloc      one TcRoot, removed on exit.
        """
        with _root.TcRoot() as root:
            code, out, err = root.tc("send", "--from", "a", "--to", NAME, "hi")
            self.assertEqual(code, 0, f"tc send exited {code}: {err}")
            with self.assertRaises(_root.ListenerNotProven) as caught:
                with root.listener(NAME, LISTENER_TIMEOUT_SECONDS):
                    self.fail(f"listener({NAME!r}) yielded over waiting mail")
            started = sorted(root.base.glob(f"listener-{NAME}-*.out"))
        said = str(caught.exception)
        self.assertIn("not started", said, f"raised for the wrong reason: {said}")
        self.assertIn("1 unread", said, f"does not name the waiting mail: {said}")
        self.assertEqual(started, [], f"a tc wait was started over waiting mail: {started}")

    def test_teardown_reaps_every_child_when_one_times_out(self):
        """Two children time out on reap; the third is still reaped, and one error names both.

        The timeout is simulated: _stop is wrapped to stop the child for
        real and then raise TimeoutExpired for the first two. Must reject a
        teardown that stops at the first failure (the third child would
        live on).

        @interacts  three start() children; each is also killed by its own
                    pid in this test's cleanup.
        @deps       _root.TcRoot.start, _root._stop, in_proc, kill_own.
        @complexity O(1).
        @alloc      one TcRoot, removed on exit.
        """
        real_stop = _root._stop
        times_out = set()

        def stop_then_time_out(proc, deadline=None):
            """The real _stop, then a reap timeout for each pid in `times_out`.

            Stands in for _root._stop. The child is killed and reaped for
            real first, so a simulated timeout leaves nothing running.

            @interacts  SIGKILL to proc.pid through the real _stop, then
                        raises TimeoutExpired when proc.pid is in
                        `times_out`.
            @deps       _root._stop, subprocess.
            @complexity O(1).
            @alloc      none; the real _stop releases the child's pipes.
            """
            real_stop(proc, deadline)
            if proc.pid in times_out:
                raise subprocess.TimeoutExpired(proc.args, _root.REAP_CEILING_SECONDS)

        procs = []
        raised = None
        try:
            with mock.patch.object(_root, "_stop", stop_then_time_out):
                with _root.TcRoot() as root:
                    for i in range(3):
                        proc = root.start("wait", f"t{i}", "--timeout", str(LISTENER_TIMEOUT_SECONDS))
                        self.addCleanup(kill_own, proc)
                        procs.append(proc)
                    times_out.update(proc.pid for proc in procs[:2])
        except Exception as exc:  # the test checks what came out, below
            raised = exc
        last = procs[2].pid
        self.assertFalse(in_proc(last), f"pid {last} still in /proc: teardown stopped at a failure")
        self.assertIsInstance(raised, _root.ChildNotReaped, f"teardown raised {raised!r}")
        for proc in procs[:2]:
            self.assertIn(f"pid {proc.pid}", str(raised), f"pid {proc.pid} not named: {raised}")

    def test_listener_cleanup_failure_keeps_the_tests_own_exception(self):
        """A reap timeout in the listener's teardown never replaces the test's exception.

        The test raises Planted inside the listener's context while reaping
        is made to time out. Planted must come out, and the timeout must be
        on stderr. Must reject a teardown that raises over it.

        @interacts  one listener; stderr captured.
        @deps       _root.TcRoot.listener, _root._stop.
        @complexity O(1).
        @alloc      one TcRoot, removed on exit.
        """
        real_stop = _root._stop

        def stop_then_time_out(proc, deadline=None):
            """The real _stop, then a reap timeout, for every child.

            Stands in for _root._stop while the listener tears down. The
            child is killed and reaped for real first, so the simulated
            timeout leaves nothing running.

            @interacts  SIGKILL to proc.pid through the real _stop, then
                        always raises TimeoutExpired.
            @deps       _root._stop, subprocess.
            @complexity O(1).
            @alloc      none; the real _stop releases the child's pipes.
            """
            real_stop(proc, deadline)
            raise subprocess.TimeoutExpired(proc.args, _root.REAP_CEILING_SECONDS)

        log = io.StringIO()
        caught = None
        pid = None
        with _root.TcRoot() as root:
            with mock.patch.object(_root, "_stop", stop_then_time_out), \
                    contextlib.redirect_stderr(log):
                try:
                    with root.listener(NAME, LISTENER_TIMEOUT_SECONDS) as pid:
                        raise Planted("the test's own failure")
                except BaseException as exc:  # the test checks which one came out
                    caught = exc
        self.assertIsInstance(caught, Planted, f"the test's exception was replaced by {caught!r}")
        self.assertIn(f"pid {pid}", log.getvalue(), f"cleanup failure not on stderr: {log.getvalue()!r}")

    def test_fake_gives_each_call_its_exit_code_and_stderr(self):
        """fake_bin("ssh", [0, 255, 0], stderr) exits 0, 255, 0, 0 and writes stderr each call.

        Also: argv and stdin are recorded per call, in order. Must reject a
        fake that ignores the call count (it would exit 0 every time).

        @interacts  calls the fake four times by absolute path.
        @deps       _root.TcRoot.fake_bin, subprocess.
        @complexity O(1).
        @alloc      one TcRoot, removed on exit.
        """
        words = "fake ssh: connection refused\n"
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("ssh", [0, 255, 0], stderr=words)
            runs = [subprocess.run([str(folder / "ssh"), "-T", "--", f"u@h{i}"], input=f"body {i}",
                                   env=root.env, capture_output=True, text=True,
                                   timeout=CHILD_TIMEOUT_SECONDS)
                    for i in range(4)]
            record = folder.parent / "calls.jsonl"
            self.assertTrue(record.exists(), f"{record} missing: the fake never ran")
            recorded = calls()
        self.assertEqual([run.returncode for run in runs], [0, 255, 0, 0])
        self.assertEqual([run.stderr for run in runs], [words] * 4)
        self.assertEqual(recorded, [{"argv": ["-T", "--", f"u@h{i}"], "stdin": f"body {i}"}
                                    for i in range(4)])

    def test_started_children_are_dead_after_the_root_exits(self):
        """Two start() children run inside the root and are gone from /proc after it.

        Must reject a start() that does not register its child (teardown
        would leave it running).

        @interacts  two start() children; each is also killed by its own
                    pid in this test's cleanup.
        @deps       _root.TcRoot.start, in_proc, kill_own.
        @complexity O(1).
        @alloc      one TcRoot, removed on exit.
        """
        with _root.TcRoot() as root:
            procs = []
            for i in range(2):
                proc = root.start("wait", f"s{i}", "--timeout", str(LISTENER_TIMEOUT_SECONDS))
                self.addCleanup(kill_own, proc)
                procs.append(proc)
            for proc in procs:
                self.assertIsNone(proc.poll(), f"pid {proc.pid} exited {proc.returncode} at once")
        for proc in procs:
            self.assertFalse(in_proc(proc.pid), f"pid {proc.pid} still in /proc after TcRoot exited")

    def test_start_feeds_stdin_and_hands_back_the_output(self):
        """start("send", ..., stdin="hello") sends "hello"; communicate() returns its output.

        Must reject a start() that drops `stdin` (tc send would refuse an
        empty message).

        @interacts  one start() child; one `tc peek`.
        @deps       _root.TcRoot.start, _root.TcRoot.tc.
        @complexity O(1).
        @alloc      one TcRoot, removed on exit.
        """
        with _root.TcRoot() as root:
            proc = root.start("send", "--from", "a", "--to", NAME, stdin="hello")
            out, err = proc.communicate(timeout=CHILD_TIMEOUT_SECONDS)
            self.assertEqual(proc.returncode, 0, f"tc send exited {proc.returncode}: {err}")
            self.assertIn(f"sent #1 to {NAME}", out)
            code, peeked, err = root.tc("peek", NAME)
        self.assertEqual(code, 0, f"tc peek exited {code}: {err}")
        self.assertIn("hello", peeked, f"the stdin text did not arrive:\n{peeked}")

    def test_bare_ssh_and_codex_hit_the_refusing_stub(self):
        """A child that runs `ssh` or `codex` by name reaches the stub: exit 97, its words.

        Must reject a harness with no stub ahead of the system's folders:
        the name would resolve to the real tool (the probe reports that
        path and does not run it).

        @interacts  one probe run through root.tc(); the probe runs each stub.
        @deps       probe.
        @complexity O(1).
        @alloc      one TcRoot, removed on exit.
        """
        with _root.TcRoot() as root:
            code, report, err = probe(root, "ssh", "codex")
        self.assertEqual(code, 0, f"probe exited {code}: {err}")
        for name in ("ssh", "codex"):
            seen = report["tools"][name]
            self.assertTrue(seen["ran"], f"`{name}` resolved to {seen['path']}, outside the "
                                         f"test's temp folder: the real tool would have run")
            self.assertEqual(seen["code"], REFUSED_EXIT, f"`{name}` exited {seen['code']}")
            self.assertEqual(seen["stderr"], REFUSED_WORDS.format(name=name))

    def test_a_fake_goes_ahead_of_the_refusing_stub(self):
        """After fake_bin("codex"), a child's `codex` is the fake; `ssh` is still refused.

        Must reject a fake_bin that leaves its folder off the children's
        PATH (the child would reach the stub, and the fake records nothing).

        @interacts  one probe run through root.tc(); the probe runs the
                    fake and the ssh stub.
        @deps       probe, _root.TcRoot.fake_bin.
        @complexity O(1).
        @alloc      one TcRoot, removed on exit.
        """
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("codex", 0)
            code, report, err = probe(root, "codex", "ssh")
            record = folder.parent / "calls.jsonl"
            self.assertTrue(record.exists(), f"{record} missing: the fake never ran")
            recorded = calls()
        self.assertEqual(code, 0, f"probe exited {code}: {err}")
        self.assertEqual(report["tools"]["codex"]["path"], str(folder / "codex"))
        self.assertEqual(report["tools"]["codex"]["code"], 0)
        self.assertEqual(recorded, [{"argv": [PROBE_ARG], "stdin": ""}])
        self.assertEqual(report["tools"]["ssh"]["code"], REFUSED_EXIT)

    def test_calls_read_after_the_root_exits_raises(self):
        """calls() is [] while the root is live and the fake never ran; after the root exits it raises.

        Must reject a calls() that answers [] once the record is gone: an
        "assert not called" placed after the `with` block would pass even
        though the fake ran.

        @interacts  calls the fake once by absolute path.
        @deps       _root.TcRoot.fake_bin, subprocess.
        @complexity O(1).
        @alloc      one TcRoot, removed on exit.
        """
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("ssh", 0)
            before = calls()
            run = subprocess.run([str(folder / "ssh"), "-T"], env=root.env,
                                 stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                 timeout=CHILD_TIMEOUT_SECONDS)
            during = calls()
        self.assertEqual(before, [], f"calls() before any run: {before}")
        self.assertEqual(run.returncode, 0, f"the fake exited {run.returncode}: {run.stderr}")
        self.assertEqual(during, [{"argv": ["-T"], "stdin": ""}])
        with self.assertRaises(RuntimeError) as caught:
            calls()
        self.assertIn("inside the `with TcRoot()` block", str(caught.exception))

    def test_teardown_shares_one_reap_ceiling_across_children(self):
        """Four children stuck on reap cost one REAP_CEILING_SECONDS in all, and each is named.

        _root's view of time is a number the test moves by hand, so no real
        wait happens. _stop is wrapped: it stops the child for real, then
        acts stuck, using up all the time left before the deadline it was
        given, and raises TimeoutExpired. _kill is wrapped to log the
        order. Must reject a teardown that gives each child a ceiling of
        its own (the clock would reach four ceilings), and one that reaps
        before every child has had its SIGKILL.

        @interacts  four start() children; each is also killed by its own
                    pid in this test's cleanup.
        @deps       _root.TcRoot.start, _root._stop, _root._kill, types,
                    in_proc, kill_own.
        @complexity O(h) over h = 4 children.
        @alloc      one TcRoot, removed on exit.
        """
        children = 4
        real_stop = _root._stop
        real_kill = _root._kill
        now = [0.0]
        events = []

        def kill_and_log(proc):
            """The real _kill, logged as ("kill", pid).

            @interacts  SIGKILL to proc.pid through the real _kill.
            @deps       _root._kill.
            @complexity O(1).
            @alloc      one event tuple.
            """
            events.append(("kill", proc.pid))
            real_kill(proc)

        def stop_then_stick(proc, deadline=None):
            """The real _stop, then a reap that uses up the time left before `deadline`.

            @interacts  SIGKILL to proc.pid through the real _stop, which
                        reaps it for real; then moves the test's clock to
                        `deadline` and raises TimeoutExpired.
            @deps       _root._stop, subprocess.
            @complexity O(1).
            @alloc      one event tuple; the real _stop releases the pipes.
            """
            events.append(("reap", proc.pid))
            real_stop(proc)
            left = max(0.0, deadline - now[0])
            now[0] += left
            raise subprocess.TimeoutExpired(proc.args, left)

        clock = types.SimpleNamespace(monotonic=lambda: now[0], sleep=time.sleep)
        procs = []
        raised = None
        try:
            with mock.patch.object(_root, "time", clock), \
                    mock.patch.object(_root, "_kill", kill_and_log), \
                    mock.patch.object(_root, "_stop", stop_then_stick):
                with _root.TcRoot() as root:
                    for i in range(children):
                        proc = root.start("wait", f"h{i}", "--timeout", str(LISTENER_TIMEOUT_SECONDS))
                        self.addCleanup(kill_own, proc)
                        procs.append(proc)
        except Exception as exc:  # the test checks what came out, below
            raised = exc
        pids = {proc.pid for proc in procs}
        self.assertIsInstance(raised, _root.ChildNotReaped, f"teardown raised {raised!r}")
        for pid in pids:
            self.assertIn(f"pid {pid}", str(raised), f"pid {pid} not named: {raised}")
        self.assertLessEqual(now[0], _root.REAP_CEILING_SECONDS,
                             f"{children} stuck reaps took {now[0]} s of the clock, more than one ceiling")
        first = events[:children]
        self.assertEqual(first, [("kill", pid) for pid in (proc.pid for proc in procs)],
                         f"a reap came before every child had its SIGKILL: {events}")
        for proc in procs:
            self.assertFalse(in_proc(proc.pid), f"pid {proc.pid} still in /proc after teardown")

    def test_a_dotted_or_symlinked_path_out_of_base_stays_behind_the_stubs(self):
        """A PATH entry that reads as inside the temp folder but resolves outside it goes behind the stubs.

        A decoy folder beside the root's temp folder holds an `ssh`. Two
        entries name it from inside the temp folder: a symlink in base,
        and `<base>/../<decoy>`. With either first on PATH, a child's
        `ssh` must still be the stub. The probe never runs the decoy: it
        resolves outside the temp folder. Must reject a _guard_path that
        compares paths as text.

        @interacts  two probe runs through root.tc(); writes the decoy in
                    a TemporaryDirectory of its own, removed on exit.
        @deps       probe, tempfile, os, pathlib.
        @complexity O(1).
        @alloc      one TcRoot and one decoy folder, both removed on exit.
        """
        seen = {}
        with _root.TcRoot() as root, \
                tempfile.TemporaryDirectory(prefix="tc-decoy-", dir=root.base.parent) as decoy:
            tool = pathlib.Path(decoy) / "ssh"
            tool.write_text(DECOY_SCRIPT)
            tool.chmod(DECOY_MODE)
            link = root.base / "decoy-link"
            link.symlink_to(decoy, target_is_directory=True)
            entries = {"symlink": str(link),
                       "dotted": os.path.join(str(root.base), os.pardir, os.path.basename(decoy))}
            for form, entry in entries.items():
                code, report, err = probe(root, "ssh",
                                          env={"PATH": f"{entry}{os.pathsep}{root.env['PATH']}"})
                seen[form] = (code, report["tools"]["ssh"] if report else None, err)
        for form, (code, found, err) in seen.items():
            with self.subTest(form=form):
                self.assertEqual(code, 0, f"probe exited {code}: {err}")
                self.assertTrue(found["ran"], f"`ssh` resolved to {found['path']}, outside the "
                                              f"test's temp folder: the stubs were not first")
                self.assertEqual(found["code"], REFUSED_EXIT, f"`ssh` exited {found['code']}")

    def test_fake_bin_refuses_a_name_that_is_not_a_plain_word(self):
        """fake_bin raises ValueError for a slash, a newline, a capital, a space, an empty or too-long name.

        Nothing is written for a refused name, and a plain word of the
        longest length still passes. Must reject a fake_bin that takes any
        string (a newline adds a line to the generated scripts; a slash
        writes outside bin/).

        @interacts  writes one fake, for the name that passes.
        @deps       _root.TcRoot.fake_bin.
        @complexity O(1).
        @alloc      one TcRoot, removed on exit.
        """
        longest = "s" * FAKE_NAME_MAX
        bad = ("ssh\nexit 0", "ssh\n", "../ssh", "bin/ssh", "", "Ssh", "-ssh", "ssh x", longest + "s")
        with _root.TcRoot() as root:
            for name in bad:
                with self.subTest(name=name), self.assertRaises(ValueError):
                    root.fake_bin(name, 0)
            written = sorted(p.name for p in root.base.glob("fake-*"))
            folder, calls = root.fake_bin(longest, 0)
            made = (folder / longest).exists()
        self.assertEqual(written, [], f"a refused name still wrote a fake: {written}")
        self.assertTrue(made, f"fake_bin({longest!r}) wrote no fake")

    def test_a_listener_already_up_yields_without_sleeping(self):
        """When the first read of /proc/locks shows the pid, listener() yields with no sleep.

        _root's view of time is swapped so its sleeps are counted, not
        slept, and _root.flock_holders answers only once the pid really
        holds the lock, so the listener is up by the first read. Must
        reject a listener() that sleeps before its first read (every
        listener would pay one LOCK_POLL_SECONDS at least).

        @interacts  one listener; reads /proc/locks through held_by.
        @deps       _root.TcRoot.listener, _root.flock_holders, held_by,
                    types, time.
        @complexity O(1).
        @alloc      one TcRoot, removed on exit.
        """
        real_holders = _root.flock_holders
        sleeps = []

        def holders_once_up(path):
            """_root.flock_holders, answered only once some pid holds `path`.

            Waits with the real time.sleep, which the listener's counted
            sleep does not see, up to LOCK_CEILING_SECONDS.

            @interacts  reads /proc/locks through held_by, then through
                        the real flock_holders.
            @deps       held_by, _root.flock_holders, time.
            @complexity at most LOCK_CEILING_SECONDS / LOCK_POLL_SECONDS
                        = 100 reads, each O(k) over k lines (tens).
            @alloc      the set of pids, returned.
            """
            give_up = time.monotonic() + _root.LOCK_CEILING_SECONDS
            while not held_by(path) and time.monotonic() < give_up:
                time.sleep(_root.LOCK_POLL_SECONDS)
            return real_holders(path)

        counted = types.SimpleNamespace(monotonic=time.monotonic, sleep=sleeps.append)
        with _root.TcRoot() as root:
            lock = root.path / "mail" / f"to-{NAME}" / ".wait.lock"  # P3 fix round 1b (Claude Opus 5.5, unreviewed): D35
            with mock.patch.object(_root, "time", counted), \
                    mock.patch.object(_root, "flock_holders", holders_once_up):
                with root.listener(NAME, LISTENER_TIMEOUT_SECONDS) as pid:
                    holders = held_by(lock)
        self.assertIn(pid, holders, f"at yield, pid {pid} does not hold {lock}; holders: {holders}")
        self.assertEqual(sleeps, [], f"listener() slept {len(sleeps)} time(s) though the lock "
                                     f"was held at its first read")

    def test_start_runs_a_given_argv_and_teardown_kills_it(self):
        """start(argv=[...]) runs that command with the root's env, and it dies with the root.

        The child prints the TC_ROOT it sees, then sleeps far past the
        test. Also: tc arguments with argv, an empty argv and a bare string
        raise ValueError. Must reject a start() that ignores argv and runs
        tc (the first line would not be the root's path).

        @interacts  one start() child running python3 -c; it is also
                    killed by its own pid in this test's cleanup.
        @deps       _root.TcRoot.start, in_proc, kill_own.
        @complexity O(1).
        @alloc      one TcRoot, removed on exit.
        """
        script = (f"import os, time; print(os.environ['TC_ROOT'], flush=True); "
                  f"time.sleep({SLEEPER_SECONDS})")
        argv = [sys.executable, "-c", script]
        with _root.TcRoot() as root:
            for args, given in ((("peek", NAME), argv), ((), []), ((), script)):
                with self.subTest(args=args, argv=given), self.assertRaises(ValueError):
                    root.start(*args, argv=given)
            proc = root.start(argv=argv)
            self.addCleanup(kill_own, proc)
            said = proc.stdout.readline().strip()
            running = proc.poll()
            where = str(root.path)
        self.assertEqual(proc.args, argv)
        self.assertEqual(said, where, "the child did not run the given argv under this root")
        self.assertIsNone(running, f"pid {proc.pid} exited {running} before teardown")
        self.assertFalse(in_proc(proc.pid), f"pid {proc.pid} still in /proc after TcRoot exited")


if __name__ == "__main__":
    unittest.main()
