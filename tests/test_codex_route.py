"""
Tests for the codex route (CARDS R4, contract C2, decision D3): a send to
a codex card lands in the inbox like any other, then rings the thread with
`codex queue` when the inbox was empty. A failed ring is a warning, never
a failed send.

Model:  Claude Opus 5.5 (the CARDS lane agent), 2026-10-14
Status: unreviewed

Real codex never runs here (rule 5). Every test puts a fake `codex` first
on PATH (tests/_root.py's, or one of this file's own for a fake that must
sleep), asserts its record file exists before reading it, and reads it
inside the `with TcRoot()` block. A test that asserts "not called" also
proves, in the same root, that the fake is reachable.

D14 (CARDS fix round 1, Claude Opus 5.5, unreviewed): a failed ring leaves
mail/.ring-pending-<to> and the next send rings again; one flock per inbox
(mail/.box-<to>.lock) covers count plus write in a codex send and glob
plus rename in `tc read`; the ring runs after the lock is released; a
thread_id of any other shape never reaches codex's argv.

@interacts  runs ../tc through tests/_root.py under a throwaway TC_ROOT,
            with a fake `codex` that records its argv. Some tests hold an
            inbox lock themselves and read /proc/locks to see a child
            blocked on it. One test writes its own fake that sleeps and
            kills it by its own pid once it has what it needs. Two tests
            load tc as a module (TC_ROOT set to the harness root first, put
            back after): one swaps subprocess.run for one call, so nothing
            runs; one runs the harness's fake with PATH set to the root's
            for that call.
@deps       python3 stdlib (fcntl, importlib, json, os, pathlib, shlex,
            signal, subprocess, sys, tempfile, time, unittest,
            unittest.mock); tests/_root.py; ../tc. test_router.py and
            test_cards.py import RELEASE_CEILING_SECONDS and
            wait_until_blocked from here.
@complexity O(1) per test: two to five tc runs and as many fake calls,
            each under a second. A blocked-child check polls /proc/locks
            at most BLOCK_CEILING_SECONDS / POLL_SECONDS = 100 times, each
            O(k) over k lines (tens). The slow-ring test runs about one
            second: its fake is killed, not waited out.
@alloc      one TcRoot per test, removed when its context exits; one open
            lock file while a test holds a lock.
"""

import fcntl
import importlib.machinery
import importlib.util
import json
import os
import pathlib
import shlex
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
# Run as `python3 -m unittest tests.test_codex_route` from the repo root,
# tests/ is not on sys.path; under discover it is. Add it once so both work.
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import _root  # noqa: E402  (needs the path line above)

# Recorded fixture: matches Codex 0.162.1, 2026-10-14.
# The exit codes of `codex queue`: 0 when the line is queued for the
# thread, 1 for a thread it does not know. Written from the plan's words
# (phases.md R4, decisions.md D3), not from a run of codex: agents never
# run the real one. The fakes below exit with these codes.
CODEX_FIXTURE_LABEL = "matches Codex 0.162.1, 2026-10-14"
CODEX_QUEUE_EXIT = {"queued": 0, "unknown thread": 1}
# The fake's stderr on a failed ring. Made up for the test; it is not
# real codex's wording, which the plan does not record.
FAKE_UNKNOWN_THREAD_STDERR = "fake codex: no thread t1\n"

THREAD = "t1"
TC_PATH = str(_root.TC.resolve())
RANG_WORDS = "rang codex {to} (queued; delivered when its turn ends or the session is resumed)"
RING_MESSAGE = ("MAIL: {n} unread for {to}. Run: {tc} read {to}, act on it, "
                "reply with {tc} send --from {to} --to {sender}.")
# The timeout C2 gives a ring, written here rather than read from tc.
CODEX_RING_SECONDS = 30
# C2's words after a ring that did not go through (D14), written here.
RING_FAILED_WORDS = "ring failed for {to}: {reason}; the mail is in its inbox; the next send to {to} rings again"
NOT_A_THREAD_ID = "its card's thread_id is not a thread id"

# CARDS fix round 1 (Claude Opus 5.5, unreviewed): D14's numbers and the
# helpers its tests share.
# phases.md R4: a ring that sleeps this long must not hold up a `tc read`
# of the same inbox for more than READ_CEILING_SECONDS.
SLOW_RING_SECONDS = 5
READ_CEILING_SECONDS = 1
# How long a test waits for a child to show up blocked on a lock, or for a
# fake to record its call. Python start-up plus tc's imports is well under
# 1 s; the rest is room for a loaded machine. Failing here beats hanging.
BLOCK_CEILING_SECONDS = 5
# How long a child gets to finish once the test lets go of the lock.
RELEASE_CEILING_SECONDS = 10
# Gap between two reads of /proc/locks or of a fake's record.
POLL_SECONDS = 0.05
# /proc/locks for a blocked waiter: "1: -> FLOCK ADVISORY WRITE <pid> <maj>:<min>:<inode> 0 EOF".
# A holder's line has no "->", so these columns sit one to the right of it.
WAITER_MARK = "->"
WAITER_MARK_COLUMN = 1
WAITER_KIND_COLUMN = 2
WAITER_PID_COLUMN = 5
WAITER_FILE_COLUMN = 6
# Owner may read, write and run this file's own fakes. Nobody else needs to.
OWN_FAKE_MODE = 0o700
# This file's own fake `codex`: a /bin/sh wrapper with a fixed shebang that
# runs a Python body, as tests/_root.py's fakes do.
OWN_FAKE_WRAPPER = '#!/bin/sh\nexec {python} {script} "$@"\n'
# A fake that records its call whole (argv and pid, through a rename, so a
# reader never sees half a line) and then sleeps SLEEP seconds.
SLOW_FAKE_BODY = """import json, os, sys, time
with open(RECORD + ".tmp", "w") as f:
    f.write(json.dumps({"argv": sys.argv[1:], "pid": os.getpid()}) + "\\n")
os.replace(RECORD + ".tmp", RECORD)
time.sleep(SLEEP)
"""


def own_fake(root, body, **constants):
    """Write a fake `codex` running `body`; return (the env for a call that should find it, its record path).

    For a fake tests/_root.py's fake_bin cannot be (one that sleeps). Its
    folder sits inside the root's temp folder, so the harness keeps it
    ahead of the refusing stubs when a call passes the returned PATH.
    `constants` become `NAME = value` lines above `body`, with RECORD.

    @interacts  writes fake-codex-own-*/bin/codex (mode 0700) and
                fake-codex-own-*/fake.py in the root's temp folder.
    @deps       tempfile, shlex, os, sys; _root.TcRoot.
    @complexity O(1).
    @alloc      one folder, removed with the temp folder.
    """
    home = pathlib.Path(tempfile.mkdtemp(dir=root.base, prefix="fake-codex-own-"))
    folder = home / "bin"
    folder.mkdir()
    record = home / "calls.jsonl"
    script = home / "fake.py"
    lines = [f"RECORD = {str(record)!r}"] + [f"{k} = {v!r}" for k, v in constants.items()]
    script.write_text("\n".join(lines) + "\n" + body)
    exe = folder / "codex"
    exe.write_text(OWN_FAKE_WRAPPER.format(python=shlex.quote(sys.executable),
                                           script=shlex.quote(str(script))))
    exe.chmod(OWN_FAKE_MODE)
    return {"PATH": f"{folder}{os.pathsep}{root.env['PATH']}"}, record


def kill_own_fake(pid, record):
    """SIGKILL `pid` if it is still this file's fake (its command line names the fake's folder).

    Checks first, so a pid the system has handed to someone else since is
    left alone.

    @interacts  reads /proc/<pid>/cmdline; sends SIGKILL to that one pid.
    @deps       os, signal, pathlib.
    @complexity O(1).
    @alloc      the command line bytes, freed on return.
    """
    try:
        cmdline = pathlib.Path(f"/proc/{pid}/cmdline").read_bytes()
        if os.fsencode(str(record.parent)) in cmdline:
            os.kill(pid, signal.SIGKILL)
    except (FileNotFoundError, ProcessLookupError):
        pass


def lock_waiters(path):
    """Pids blocked waiting for an flock on `path`, read from /proc/locks.

    The harness's flock_holders() names only holders. A waiter's line
    carries "->" before FLOCK, so it is read here, apart.

    @interacts  stats `path`; reads /proc/locks. Writes nothing.
    @deps       os, pathlib; Linux /proc/locks.
    @complexity O(k) over k lines in /proc/locks (tens).
    @alloc      the table's lines and one set of pids, freed on return.
    """
    try:
        st = os.stat(path)
    except FileNotFoundError:
        return set()
    key = f"{os.major(st.st_dev):02x}:{os.minor(st.st_dev):02x}:{st.st_ino}"
    pids = set()
    for line in pathlib.Path("/proc/locks").read_text().splitlines():
        cols = line.split()
        if (len(cols) > WAITER_FILE_COLUMN and cols[WAITER_MARK_COLUMN] == WAITER_MARK
                and cols[WAITER_KIND_COLUMN] == "FLOCK" and cols[WAITER_FILE_COLUMN] == key):
            pids.add(int(cols[WAITER_PID_COLUMN]))
    return pids


def wait_until_blocked(test, proc, path):
    """Return once `proc` is blocked on the flock of `path`; else fail `test`.

    Fails if the child exits first (it finished while the test held the
    lock, so it never waited for it) or BLOCK_CEILING_SECONDS pass first.
    Polls /proc/locks every POLL_SECONDS; never a bare sleep.

    @interacts  reads /proc/locks; reads a finished child's stderr.
    @deps       lock_waiters, time.
    @complexity at most BLOCK_CEILING_SECONDS / POLL_SECONDS = 100 polls,
                each O(k) over k lines in /proc/locks.
    @alloc      one set of pids per poll, freed as it goes.
    """
    deadline = time.monotonic() + BLOCK_CEILING_SECONDS
    while proc.pid not in lock_waiters(path):
        if proc.poll() is not None:
            proc.communicate()
            test.fail(f"tc exited {proc.returncode} while the test held {path.name}, "
                      f"so it never waited for the lock")
        if time.monotonic() >= deadline:
            test.fail(f"tc was not blocked on {path.name} within {BLOCK_CEILING_SECONDS} s")
        time.sleep(POLL_SECONDS)


def wait_for_record(test, record, proc):
    """The first call `record` holds, once the fake has written it; else fail `test`.

    Fails if the send exits before the fake ran, or BLOCK_CEILING_SECONDS
    pass first.

    @interacts  stats and reads `record`.
    @deps       json, time.
    @complexity at most BLOCK_CEILING_SECONDS / POLL_SECONDS polls.
    @alloc      one dict, returned.
    """
    deadline = time.monotonic() + BLOCK_CEILING_SECONDS
    while not record.exists():
        if proc.poll() is not None:
            test.fail(f"the send exited {proc.returncode} before the fake codex ran")
        if time.monotonic() >= deadline:
            test.fail(f"the fake codex did not run within {BLOCK_CEILING_SECONDS} s")
        time.sleep(POLL_SECONDS)
    return json.loads(record.read_text().splitlines()[0])


def ring_argv(n, to, sender):
    """The argv a ring must hand codex, after the program name.

    @interacts  none.
    @deps       RING_MESSAGE, TC_PATH.
    @complexity O(1).
    @alloc      one list, returned.
    """
    return ["queue", "--thread", THREAD, "--message",
            RING_MESSAGE.format(n=n, to=to, tc=TC_PATH, sender=sender)]


def load_tc(root):
    """Load ../tc as a module with TC_ROOT set to `root`, without running main().

    tc reads TC_ROOT once, at import, so it is set before the load and the
    old value is put back after.

    @interacts  sets and restores os.environ["TC_ROOT"]; runs tc's top
                level (constants only, no disk writes).
    @deps       importlib, os; _root.TC.
    @complexity O(1).
    @alloc      one module object, returned.
    """
    old = os.environ.get("TC_ROOT")
    os.environ["TC_ROOT"] = str(root.path)
    try:
        loader = importlib.machinery.SourceFileLoader("tc_codex_under_test", str(_root.TC))
        mod = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
        loader.exec_module(mod)
        return mod
    finally:
        if old is None:
            os.environ.pop("TC_ROOT", None)
        else:
            os.environ["TC_ROOT"] = old


class CodexRouteTest(unittest.TestCase):
    """deliver_codex through `tc send`, against a fake codex.

    @interacts  see the module block.
    @deps       _root.TcRoot, _root.TcRoot.fake_bin.
    @complexity O(1) per test.
    @alloc      one TcRoot per test.
    """

    def join_codex(self, root, name="c"):
        """Join `name` as a Codex session on THREAD; fail the test if it does not.

        @interacts  one tc join with CODEX_THREAD_ID set for that call.
        @deps       _root.TcRoot.tc.
        @complexity O(1).
        @alloc      one card file.
        """
        code, out, err = root.tc("join", name, env={"CODEX_THREAD_ID": THREAD})
        self.assertEqual(code, 0, f"tc join {name} exited {code}: {err}")

    def test_the_fixture_is_labeled(self):
        """The recorded exit codes carry the plan's label, and the codes the plan names.

        @interacts  none.
        @deps       the module constants.
        @complexity O(1).
        @alloc      none.
        """
        self.assertEqual(CODEX_FIXTURE_LABEL, "matches Codex 0.162.1, 2026-10-14")
        self.assertEqual(CODEX_QUEUE_EXIT, {"queued": 0, "unknown thread": 1})

    def test_two_sends_to_an_empty_codex_inbox_ring_once(self):
        """Two sends to c ring once, with the argv C2 gives, and both land.

        Must reject a test that passes because the fake never ran (the
        record must exist), and a ring on every send.

        @interacts  one join, two sends, one fake codex.
        @deps       _root.TcRoot.tc, _root.TcRoot.fake_bin, ring_argv.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("codex", CODEX_QUEUE_EXIT["queued"])
            self.join_codex(root)
            first = root.tc("send", "--from", "a", "--to", "c", "one")
            second = root.tc("send", "--from", "a", "--to", "c", "two")
            record = folder.parent / "calls.jsonl"
            self.assertTrue(record.exists(), f"{record} missing: the fake codex never ran")
            recorded = calls()
            box = root.path / "mail" / "to-c"
            landed = sorted(p.name for p in box.glob("*.md"))
        self.assertEqual(first[0], 0, f"first send exited {first[0]}: {first[2]}")
        self.assertEqual(first[1], f"sent #1 to c: {box / '000001-from-a.md'}\n"
                                   f"{RANG_WORDS.format(to='c')}\n")
        self.assertEqual(second[:2], (0, f"sent #2 to c: {box / '000002-from-a.md'}\n"))
        self.assertEqual(recorded, [{"argv": ring_argv(1, "c", "a"), "stdin": ""}])
        self.assertEqual(landed, ["000001-from-a.md", "000002-from-a.md"])

    def test_a_failed_ring_is_a_warning_and_the_send_exits_0(self):
        """With the fake exiting 1 (unknown thread): exit 0, the mail in the inbox, `ring failed` on stderr.

        Must reject a send that fails because the ring failed.

        @interacts  one join, one send, one fake codex.
        @deps       _root.TcRoot.tc, _root.TcRoot.fake_bin.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("codex", CODEX_QUEUE_EXIT["unknown thread"],
                                          stderr=FAKE_UNKNOWN_THREAD_STDERR)
            self.join_codex(root)
            code, out, err = root.tc("send", "--from", "a", "--to", "c", "hi")
            record = folder.parent / "calls.jsonl"
            self.assertTrue(record.exists(), f"{record} missing: the fake codex never ran")
            recorded = calls()
            landed = sorted(p.name for p in (root.path / "mail" / "to-c").glob("*.md"))
            marked = (root.path / "mail" / ".ring-pending-c").exists()
        self.assertEqual(code, 0, f"a failed ring failed the send: exit {code}: {err}")
        self.assertTrue(out.startswith("sent #1 to c: "), out)
        self.assertNotIn("rang codex", out)
        self.assertIn(RING_FAILED_WORDS.format(to="c", reason="fake codex: no thread t1") + "\n", err)
        self.assertEqual(len(recorded), 1)
        self.assertEqual(landed, ["000001-from-a.md"])
        self.assertTrue(marked, "a failed ring left no mail/.ring-pending-c")

    # CARDS fix round 1 (Claude Opus 5.5, unreviewed): D14.
    def test_a_failed_ring_leaves_a_marker_and_the_next_send_rings(self):
        """Fake exits 1 then 0: the first send warns `rings again` and leaves the marker; the second rings and clears it.

        Must reject a ring decided on the count alone: the second send
        finds 1 unread and would not ring.

        @interacts  one join, two sends, one fake codex with two codes.
        @deps       _root.TcRoot.tc, _root.TcRoot.fake_bin, ring_argv.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin(
                "codex", [CODEX_QUEUE_EXIT["unknown thread"], CODEX_QUEUE_EXIT["queued"]],
                stderr=FAKE_UNKNOWN_THREAD_STDERR)
            self.join_codex(root)
            marker = root.path / "mail" / ".ring-pending-c"
            first = root.tc("send", "--from", "a", "--to", "c", "one")
            marked = marker.exists()
            second = root.tc("send", "--from", "b", "--to", "c", "two")
            cleared = not marker.exists()
            record = folder.parent / "calls.jsonl"
            self.assertTrue(record.exists(), f"{record} missing: the fake codex never ran")
            recorded = calls()
        self.assertEqual(first[0], 0, f"first send exited {first[0]}: {first[2]}")
        self.assertIn(RING_FAILED_WORDS.format(to="c", reason="fake codex: no thread t1") + "\n", first[2])
        self.assertTrue(marked, "the failed ring left no marker")
        self.assertEqual(second[0], 0, f"second send exited {second[0]}: {second[2]}")
        self.assertEqual([call["argv"] for call in recorded],
                         [ring_argv(1, "c", "a"), ring_argv(2, "c", "b")])
        self.assertTrue(second[1].endswith(RANG_WORDS.format(to="c") + "\n"), second[1])
        self.assertTrue(cleared, "a ring that exited 0 left the marker")

    def test_a_slow_ring_never_holds_up_a_read(self):
        """A fake that sleeps 5 s: a `tc read` of c started during the ring returns within 1 s.

        The ring runs after the inbox lock is released. Must reject a ring
        run under the lock: the read would wait the whole 5 s. The fake is
        killed by its own pid once the read is timed, so the test does not
        sit out the sleep.

        @interacts  one join, one background send, one read; this file's
                    own sleeping fake, killed by its pid.
        @deps       own_fake, wait_for_record, kill_own_fake;
                    _root.TcRoot.tc, _root.TcRoot.start.
        @complexity O(1): about one second.
        @alloc      one TcRoot and one background child.
        """
        with _root.TcRoot() as root:
            env, record = own_fake(root, SLOW_FAKE_BODY, SLEEP=SLOW_RING_SECONDS)
            self.join_codex(root)
            proc = root.start("send", "--from", "a", "--to", "c", "hi", env=env)
            ring = wait_for_record(self, record, proc)
            try:
                started = time.monotonic()
                code, out, err = root.tc("read", "c")
                took = time.monotonic() - started
            finally:
                kill_own_fake(ring["pid"], record)
            sent_out, sent_err = proc.communicate(timeout=RELEASE_CEILING_SECONDS)
        self.assertEqual(ring["argv"][:4], ["queue", "--thread", THREAD, "--message"])
        self.assertLess(took, READ_CEILING_SECONDS,
                        f"tc read took {took:.1f} s while the ring ran: the ring held the inbox lock")
        self.assertEqual(code, 0, err)
        self.assertTrue(out.startswith("# #1 from a to c"), out)
        self.assertEqual(proc.returncode, 0, "the send failed after its ring was killed")

    def test_a_codex_send_waits_for_the_inbox_lock(self):
        """With the test holding mail/.box-c.lock, a send to c does not land until it is released.

        Must reject a count and a write outside the lock.

        @interacts  one join; holds mail/.box-c.lock; one background send;
                    reads /proc/locks.
        @deps       wait_until_blocked; fcntl; _root.TcRoot.start.
        @complexity O(1).
        @alloc      one TcRoot, one open lock file, one background child.
        """
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("codex", CODEX_QUEUE_EXIT["queued"])
            self.join_codex(root)
            box = root.path / "mail" / "to-c"
            lock = root.path / "mail" / ".box-c.lock"
            lock.parent.mkdir(exist_ok=True)
            with open(lock, "a") as held:
                fcntl.flock(held, fcntl.LOCK_EX)
                proc = root.start("send", "--from", "a", "--to", "c", "hi")
                wait_until_blocked(self, proc, lock)
                while_held = sorted(p.name for p in box.glob("*.md"))
            out, err = proc.communicate(timeout=RELEASE_CEILING_SECONDS)
            landed = sorted(p.name for p in box.glob("*.md"))
            record = folder.parent / "calls.jsonl"
            self.assertTrue(record.exists(), f"{record} missing: the fake codex never ran")
            recorded = calls()
        self.assertEqual(while_held, [], "the send landed while the test held the inbox lock")
        self.assertEqual(proc.returncode, 0, err)
        self.assertEqual(landed, ["000001-from-a.md"])
        self.assertEqual([call["argv"] for call in recorded], [ring_argv(1, "c", "a")])

    def test_read_holds_the_inbox_lock_from_glob_to_rename(self):
        """With the test holding mail/.box-b.lock, `tc read b` moves nothing until it is released.

        Must reject a read that globs and renames outside the lock: that is
        the gap a send could land in and skip its ring.

        @interacts  one send; holds mail/.box-b.lock; one background read;
                    reads /proc/locks.
        @deps       wait_until_blocked; fcntl; _root.TcRoot.tc, start.
        @complexity O(1).
        @alloc      one TcRoot, one open lock file, one background child.
        """
        with _root.TcRoot() as root:
            root.tc("send", "--from", "a", "--to", "b", "hi")
            box = root.path / "mail" / "to-b"
            lock = root.path / "mail" / ".box-b.lock"
            with open(lock, "a") as held:
                fcntl.flock(held, fcntl.LOCK_EX)
                proc = root.start("read", "b")
                wait_until_blocked(self, proc, lock)
                while_held = sorted(p.name for p in box.glob("*.md"))
            out, err = proc.communicate(timeout=RELEASE_CEILING_SECONDS)
            after = sorted(p.name for p in box.glob("*.md"))
        self.assertEqual(while_held, ["000001-from-a.md"], "the read moved mail while the test held the lock")
        self.assertEqual(proc.returncode, 0, err)
        self.assertTrue(out.startswith("# #1 from a to b"), out)
        self.assertEqual(after, [])

    def test_a_thread_id_of_another_shape_never_reaches_codex(self):
        """Hand-made codex cards with thread_id "-x", 5 and ["t1"]: exit 0, the mail lands, no codex run, the marker left.

        A proper codex join afterward rings in the same root, so the fake
        was reachable. Must reject a truthiness check alone: "-x" would
        reach codex's argv, and 5 would crash the send after the mail
        landed.

        @interacts  per case: one hand-written card, one join, two sends,
                    one fake codex, in its own root.
        @deps       _root.TcRoot.tc, _root.TcRoot.fake_bin.
        @complexity O(1): three cases.
        @alloc      one TcRoot per case.
        """
        for value in ("-x", 5, ["t1"]):
            with self.subTest(thread_id=value):
                with _root.TcRoot() as root:
                    folder, calls = root.fake_bin("codex", CODEX_QUEUE_EXIT["queued"])
                    record = folder.parent / "calls.jsonl"
                    (root.path / "cards").mkdir()
                    (root.path / "cards" / "d.json").write_text(json.dumps(
                        {"name": "d", "kind": "codex", "route": "codex", "thread_id": value}))
                    code, out, err = root.tc("send", "--from", "a", "--to", "d", "hi")
                    rang_bad = record.exists()
                    landed = sorted(p.name for p in (root.path / "mail" / "to-d").glob("*.md"))
                    marked = (root.path / "mail" / ".ring-pending-d").exists()
                    self.join_codex(root)
                    root.tc("send", "--from", "a", "--to", "c", "hi")
                    self.assertTrue(record.exists(), f"{record} missing: the fake codex is not reachable")
                    recorded = calls()
                self.assertEqual(code, 0, f"exited {code}: {err}")
                self.assertIn(RING_FAILED_WORDS.format(to="d", reason=NOT_A_THREAD_ID), err)
                self.assertFalse(rang_bad, f"codex ran for thread_id {value!r}")
                self.assertEqual(landed, ["000001-from-a.md"])
                self.assertTrue(marked, "no marker after a ring that could not be tried")
                self.assertEqual([call["argv"][2] for call in recorded], [THREAD])

    def test_join_refuses_a_codex_thread_id_of_another_shape(self):
        """`tc join c` with CODEX_THREAD_ID=-x exits 1, says why, and writes nothing.

        @interacts  one tc join.
        @deps       _root.TcRoot.tc.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            code, out, err = root.tc("join", "c", env={"CODEX_THREAD_ID": "-x"})
            after = sorted(str(p.relative_to(root.path)) for p in root.path.rglob("*"))
        self.assertEqual(code, 1, f"exited {code}: {err}")
        self.assertIn('CODEX_THREAD_ID "-x" is not a thread id', err)
        self.assertEqual(after, [], f"a refused join wrote {after}")

    def test_a_marker_that_cannot_be_written_is_said(self):
        """In process: when the marker's .tmp cannot be made, the warning says a later send may not ring.

        A folder sits where the .tmp would go. The send still exits 0 with
        the mail in the inbox; the warning does not promise a ring it
        cannot keep.

        @interacts  loads tc in process; makes one folder in mail/; runs
                    deliver_codex once with PATH set to the root's (the
                    harness's fake first) for that call.
        @deps       load_tc, _root.TcRoot.fake_bin; unittest.mock.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        card = {"name": "c", "kind": "codex", "route": "codex", "thread_id": THREAD}
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("codex", CODEX_QUEUE_EXIT["unknown thread"],
                                          stderr=FAKE_UNKNOWN_THREAD_STDERR)
            tc = load_tc(root)
            (root.path / "mail" / f".ring-pending-c.{os.getpid()}.tmp").mkdir(parents=True)
            with mock.patch.dict(os.environ, {"PATH": root.env["PATH"]}):
                got = tc.deliver_codex(card, "a", "c", "hi")
            record = folder.parent / "calls.jsonl"
            self.assertTrue(record.exists(), f"{record} missing: the fake codex never ran")
            landed = sorted(p.name for p in (root.path / "mail" / "to-c").glob("*.md"))
            marked = (root.path / "mail" / ".ring-pending-c").exists()
        self.assertEqual(got.exit, 0)
        self.assertEqual(landed, ["000001-from-a.md"])
        self.assertFalse(marked)
        said = [w for w in got.warnings if w.startswith("ring failed for c: ")]
        self.assertEqual(len(said), 1, got.warnings)
        self.assertIn("could not be written", said[0])
        self.assertTrue(said[0].endswith("so a later send may not ring"), said[0])

    def test_no_ring_for_a_claude_card(self):
        """A send to a Claude card never runs codex; a send to a codex card in the same root does.

        The second half proves the fake was reachable, so "not called" is
        a check and not an absence.

        @interacts  two joins, two sends, one fake codex.
        @deps       _root.TcRoot.tc, _root.TcRoot.fake_bin.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("codex", CODEX_QUEUE_EXIT["queued"])
            record = folder.parent / "calls.jsonl"
            root.tc("join", "b", env={"CLAUDECODE": "1"})
            code, out, err = root.tc("send", "--from", "a", "--to", "b", "hi")
            rang_for_claude = record.exists()
            self.join_codex(root)
            root.tc("send", "--from", "a", "--to", "c", "hi")
            self.assertTrue(record.exists(), f"{record} missing: the fake codex is not reachable")
            recorded = calls()
        self.assertEqual(code, 0, f"send to b exited {code}: {err}")
        self.assertFalse(rang_for_claude, "a send to a claude card ran codex")
        self.assertEqual([call["argv"] for call in recorded], [ring_argv(1, "c", "a")])

    def test_it_rings_again_once_the_inbox_was_read(self):
        """send, read, send: two rings, one per batch of unread mail.

        @interacts  one join, two sends, one read, one fake codex.
        @deps       _root.TcRoot.tc, _root.TcRoot.fake_bin.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("codex", CODEX_QUEUE_EXIT["queued"])
            self.join_codex(root)
            root.tc("send", "--from", "a", "--to", "c", "one")
            root.tc("read", "c")
            root.tc("send", "--from", "b", "--to", "c", "two")
            record = folder.parent / "calls.jsonl"
            self.assertTrue(record.exists(), f"{record} missing: the fake codex never ran")
            recorded = calls()
        self.assertEqual([call["argv"] for call in recorded],
                         [ring_argv(1, "c", "a"), ring_argv(1, "c", "b")])

    def test_a_codex_card_with_no_thread_is_delivered_with_a_warning(self):
        """A hand-made codex card with no thread_id: exit 0, the mail lands, `ring failed` names why, no codex run.

        A proper codex join afterward rings in the same root, so the fake
        was reachable.

        @interacts  one hand-written card, one join, two sends, one fake codex.
        @deps       _root.TcRoot.tc, _root.TcRoot.fake_bin.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("codex", CODEX_QUEUE_EXIT["queued"])
            record = folder.parent / "calls.jsonl"
            (root.path / "cards").mkdir()
            (root.path / "cards" / "d.json").write_text(
                json.dumps({"name": "d", "kind": "codex", "route": "codex", "thread_id": None}))
            code, out, err = root.tc("send", "--from", "a", "--to", "d", "hi")
            ran_without_thread = record.exists()
            landed = sorted(p.name for p in (root.path / "mail" / "to-d").glob("*.md"))
            self.join_codex(root)
            root.tc("send", "--from", "a", "--to", "c", "hi")
            self.assertTrue(record.exists(), f"{record} missing: the fake codex is not reachable")
            recorded = calls()
        self.assertEqual(code, 0, f"exited {code}: {err}")
        self.assertIn("ring failed for d: its card has no thread_id; the mail is in its inbox", err)
        self.assertFalse(ran_without_thread, "codex ran with no thread to ring")
        self.assertEqual(landed, ["000001-from-a.md"])
        self.assertEqual(len(recorded), 1)

    def test_a_ring_that_times_out_is_a_warning(self):
        """In process: codex past CODEX_RING_SECONDS gives `ring failed ... no answer in 30 s`, exit 0.

        subprocess.run is swapped for one call, so nothing runs; the test
        also checks the ring's stdin is /dev/null and its timeout is 30 s.

        @interacts  loads tc in process; patches subprocess.run for one
                    deliver_codex call, which writes one message under the root.
        @deps       load_tc, unittest.mock.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        seen = []

        def hangs(argv, **kwargs):
            seen.append((argv, kwargs))
            raise subprocess.TimeoutExpired(argv, kwargs.get("timeout"))

        card = {"name": "c", "kind": "codex", "route": "codex", "thread_id": THREAD}
        with _root.TcRoot() as root:
            tc = load_tc(root)
            with mock.patch.object(subprocess, "run", hangs):
                got = tc.deliver_codex(card, "a", "c", "hi")
            landed = sorted(p.name for p in (root.path / "mail" / "to-c").glob("*.md"))
        self.assertEqual(got.exit, 0)
        self.assertIn(RING_FAILED_WORDS.format(to="c", reason=f"no answer in {CODEX_RING_SECONDS} s"),
                      got.warnings)
        self.assertEqual(landed, ["000001-from-a.md"])
        self.assertEqual(len(seen), 1, "codex was not called exactly once")
        argv, kwargs = seen[0]
        self.assertEqual(argv[:4], ["codex", "queue", "--thread", THREAD])
        self.assertEqual((kwargs.get("stdin"), kwargs.get("timeout")),
                         (subprocess.DEVNULL, CODEX_RING_SECONDS))


if __name__ == "__main__":
    unittest.main()
