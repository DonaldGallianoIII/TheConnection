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

D20 (SHARED fix round 1, Claude Opus 5.5, unreviewed): the marker is never
removed. A ring that exits 0, or a codex join with nothing waiting,
rewrites it as `clear`, so the D14 and D16 tests read its state
(marker_state), not whether it exists.

@interacts  runs ../tc through tests/_root.py under a throwaway TC_ROOT,
            with a fake `codex` that records its argv. Some tests hold an
            inbox lock themselves and read /proc/locks to see a child
            blocked on it. Some tests write a fake of their own (one that
            sleeps, starts a child, or writes odd bytes) and kill what it
            started by its own pid once they have what they need. Four
            tests load tc as a module (TC_ROOT set under the harness root
            first, put back after): two swap subprocess.Popen (one also
            os.killpg) for one call, so nothing runs and no signal is sent;
            two run a fake with PATH set to put it first for that call, one
            of them with the ring's timeout patched down to
            SHORT_RING_SECONDS. D16's tests (phase fix round 1, Claude
            Opus 5.5, unreviewed): two more load tc and run deliver_codex
            with the clock (wall_clock) replaced, so no test sleeps out the
            backoff; one fake kills the tc send that started it, by that
            send's own pid, once it has checked the pid is that send; one
            test leaves a `tc read` stalled on a stdout pipe it never
            drains, and the harness kills it by its own pid. P3 fix round
            1b (Claude Opus 5.5, unreviewed): DoorbellRecordTest, C2 item
            5. One test puts a wrapper fake first that looks at the
            sender's last-ring record before it runs the harness fake;
            two load tc and run deliver_codex with wall_clock replaced,
            one of them per case renaming, linking, dating or chmodding
            the record or its branch by hand (the mode put back), or
            patching os.lstat and os.fstat (test_shared.py's owner
            patches) so the branch reads as another user's.
@deps       python3 stdlib (contextlib, datetime, fcntl, importlib, json,
            os, pathlib, pwd, shlex, signal, stat, subprocess, sys,
            tempfile, time, unittest, unittest.mock); tests/_root.py;
            owner_patched_lstat and owner_patched_fstat from
            test_shared.py (DoorbellRecordTest); ../tc. test_router.py and
            test_cards.py import FINISH_CEILING_SECONDS and
            wait_until_blocked from here; test_ssh_route.py imports
            FINISH_CEILING_SECONDS, load_tc and wait_until_blocked;
            test_flush.py FINISH_CEILING_SECONDS, LOCK_POLL_SECONDS and
            load_tc; test_gate.py FINISH_CEILING_SECONDS, THREAD,
            load_tc and ring_argv (SSH fix round 1, Claude Opus 5.5,
            unreviewed: the audit's LOW-27).
@complexity O(1) per test: two to five tc runs and as many fake calls,
            each under a second. A blocked-child check polls /proc/locks
            at most BLOCK_CEILING_SECONDS / LOCK_POLL_SECONDS = 100 times, each
            O(k) over k lines (tens). The slow-ring test runs about one
            second: its fake is killed, not waited out.
@alloc      one TcRoot per test, removed when its context exits; one open
            lock file while a test holds a lock.
"""

import contextlib
import datetime
import fcntl
import importlib.machinery
import importlib.util
import json
import os
import pathlib
import pwd
import shlex
import signal
import stat
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

# The codex fixture: the exit codes of `codex queue`, 0 when the line is
# queued for the thread, 1 for a thread it does not know. phases.md R4 asks
# for a fixture recorded from Codex 0.162.1 on 2026-10-14. This is not one:
# agents never run the real codex, so it is written from the plan's words
# (phases.md R4, decisions.md D3), and its label says so (CARDS fix round
# 1). Donald's run (D4) records the real codes. The fakes below exit with
# these.
CODEX_FIXTURE_LABEL = ("written from the plan's words (0 queued, 1 unknown thread), "
                       "not recorded from a run of codex")
CODEX_QUEUE_EXIT = {"queued": 0, "unknown thread": 1}
# The fake's stderr on a failed ring. Made up for the test; it is not
# real codex's wording, which the plan does not record.
FAKE_UNKNOWN_THREAD_STDERR = "fake codex: no thread t1\n"

THREAD = "t1"
TC_PATH = str(_root.TC.resolve())
RANG_WORDS = "rang codex {to} (queued; delivered when its turn ends or the session is resumed)"
# C2's ring line. Since the CARDS fix round each command carries
# the mailbox root, and both words are quoted with shlex.quote.
RING_MESSAGE = ("MAIL: {n} unread for {to}. Run: TC_ROOT={root} {tc} read {to}, act on it, "
                "reply with TC_ROOT={root} {tc} send --from {to} --to {sender}.")
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
# How long a child gets to finish once the test lets go of the lock, or
# once its fake is killed. A guard against a hang, not a measure, so it is
# not test_mailbox.py's RELEASE_CEILING_SECONDS: that one is K3's 1 s pass
# bound, from the plan.
FINISH_CEILING_SECONDS = 10
# Gap between two reads of /proc/locks: the name and value tests/_root.py
# and test_mailbox.py give it. A fake's record and a pid's exit are polled
# at the same gap.
LOCK_POLL_SECONDS = 0.05
# The exit code of a refusal with words (contracts.md's exit table).
EXIT_REFUSED = 1
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
# A fake that starts a child of its own, as a node CLI starts a native
# codex, records both pids, and sleeps; the child sleeps too. The child's
# command line carries RECORD, so kill_own_fake knows it as this test's.
SPAWNING_FAKE_BODY = """import json, os, subprocess, sys, time
child = subprocess.Popen([sys.executable, "-c", "import sys, time; time.sleep(float(sys.argv[1]))",
                          str(SLEEP), RECORD])
with open(RECORD + ".tmp", "w") as f:
    f.write(json.dumps({"argv": sys.argv[1:], "pid": os.getpid(), "child": child.pid}) + "\\n")
os.replace(RECORD + ".tmp", RECORD)
time.sleep(SLEEP)
"""
# A fake that records its call, writes bytes that are not UTF-8 to its
# stderr, and exits 1, so the ring has to decode them.
ODD_BYTES_FAKE_BODY = """import json, os, sys
with open(RECORD + ".tmp", "w") as f:
    f.write(json.dumps({"argv": sys.argv[1:], "pid": os.getpid()}) + "\\n")
os.replace(RECORD + ".tmp", RECORD)
sys.stderr.buffer.write(b"\\xff\\xfe not utf-8\\n")
sys.exit(1)
"""
# The ring's timeout, patched down in process so a test waits this long
# for the timeout, not CODEX_RING_SECONDS. Long enough for the fake to
# start its child and record both pids first on a loaded machine.
SHORT_RING_SECONDS = 2
# How long the spawning fake and its child sleep: well past
# SHORT_RING_SECONDS plus BLOCK_CEILING_SECONDS, so a child that outlives
# the ring is still running when the test looks, and cannot pass for one
# the ring killed. Either way the test kills both by their own pids.
ORPHAN_SLEEP_SECONDS = 30
# A pid for the in-process stand-in for Popen. os.killpg is swapped out in
# that test, so no signal is ever sent to it.
STAND_IN_PID = 424242
# /proc/<pid>/stat: the state letter after the ")" that closes comm. A
# zombie (Z) has exited and only waits to be reaped.
ZOMBIE_STATE = "Z"

# Phase fix round 1 (Claude Opus 5.5, unreviewed): D16's words and numbers,
# written here rather than read from tc.
# What `tc join` prints after its joined line when mail is waiting.
WAITING_WORDS = "{n} unread waiting for {to}: run tc read {to}\n"
# A ring that timed out, and a send that finds the backoff still running.
RING_TIMED_OUT_WORDS = "ring failed for {to}: {reason}; the mail is in its inbox; a send after {until} rings again"
RING_PENDING_WORDS = "ring pending for {to}: the last ring timed out at {at}; a send after {until} rings again"
RING_BACKOFF_SECONDS = 300
# How the warnings name a time.
CLOCK_FORMAT = "%H:%M:%S"
# The first line of the marker after a ring that timed out, and after one
# that failed fast.
TIMED_OUT_STATE = "timed out"
FAILED_STATE = "failed"
# SHARED fix round 1 (Claude Opus 5.5, unreviewed): D20 item 5. The marker
# is never removed; its first line carries its state. These are the other
# states the tests read: a ring under way, a join that found mail waiting,
# and nothing owed.
RINGING_STATE = "ringing"
JOINED_STATE = "joined with unread mail"
CLEAR_STATE = "clear"
# A marker this user may read and not write: owner, group and others read
# only. Since D20 tc rewrites the marker in place, so this, not a folder at
# a .tmp name, is how a test makes it unwritable.
READ_ONLY_FILE_MODE = 0o444
# Where the patched clock stands: this far after the timeout (inside the
# window), and this far past the window's end.
INSIDE_WINDOW_SECONDS = 10
PAST_WINDOW_SECONDS = 1
# A second thread, for a rejoin.
OTHER_THREAD = "t2"
# A fake that records its call and its parent's pid, then sends SIGKILL to
# that parent, the `tc send` ringing it, as a person's Ctrl-C or a closed
# terminal would end a sender mid-ring. It kills only a parent whose
# command line holds the tc path TC and "send", so it never touches a pid
# that is not this test's own send.
KILLING_FAKE_BODY = """import json, os, signal, sys
parent = os.getppid()
with open(RECORD + ".tmp", "w") as f:
    f.write(json.dumps({"argv": sys.argv[1:], "pid": os.getpid(), "parent": parent}) + "\\n")
os.replace(RECORD + ".tmp", RECORD)
with open(f"/proc/{parent}/cmdline", "rb") as f:
    words = f.read().split(b"\\0")
if TC.encode() in words and b"send" in words:
    os.kill(parent, signal.SIGKILL)
"""
# One message larger than a pipe's default buffer on Linux (64 KiB), so a
# `tc read` whose stdout nobody drains stops partway through printing it.
STALL_BODY_BYTES = 256 * 1024
# How long a send to that inbox may take while the reader is stalled.
STALLED_READ_SEND_CEILING_SECONDS = 1


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
    Polls /proc/locks every LOCK_POLL_SECONDS; never a bare sleep.

    @interacts  reads /proc/locks; reads a finished child's stderr.
    @deps       lock_waiters, time.
    @complexity at most BLOCK_CEILING_SECONDS / LOCK_POLL_SECONDS = 100 polls,
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
        time.sleep(LOCK_POLL_SECONDS)


def wait_for_record(test, record, proc):
    """The first call `record` holds, once the fake has written it; else fail `test`.

    Fails if the send exits before the fake ran, or BLOCK_CEILING_SECONDS
    pass first.

    @interacts  stats and reads `record`.
    @deps       json, time.
    @complexity at most BLOCK_CEILING_SECONDS / LOCK_POLL_SECONDS polls.
    @alloc      one dict, returned.
    """
    deadline = time.monotonic() + BLOCK_CEILING_SECONDS
    while not record.exists():
        if proc.poll() is not None:
            test.fail(f"the send exited {proc.returncode} before the fake codex ran")
        if time.monotonic() >= deadline:
            test.fail(f"the fake codex did not run within {BLOCK_CEILING_SECONDS} s")
        time.sleep(LOCK_POLL_SECONDS)
    return json.loads(record.read_text().splitlines()[0])


def gone(pid):
    """True once `pid` has exited: no /proc entry, or a zombie waiting to be reaped.

    Polls until BLOCK_CEILING_SECONDS pass, then answers for the last look.

    @interacts  reads /proc/<pid>/stat.
    @deps       pathlib, time.
    @complexity at most BLOCK_CEILING_SECONDS / LOCK_POLL_SECONDS reads.
    @alloc      one string per read.
    """
    deadline = time.monotonic() + BLOCK_CEILING_SECONDS
    while True:
        try:
            stat = pathlib.Path(f"/proc/{pid}/stat").read_text()
        except FileNotFoundError:
            return True
        if stat[stat.rindex(")") + 2:].split()[0] == ZOMBIE_STATE:
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(LOCK_POLL_SECONDS)


def ring_argv(root, n, to, sender, thread=THREAD):
    """The argv a ring must hand codex, after the program name, for a send under `root`.

    @interacts  none.
    @deps       RING_MESSAGE, TC_PATH, THREAD; shlex.
    @complexity O(1).
    @alloc      one list, returned.
    """
    return ["queue", "--thread", thread, "--message",
            RING_MESSAGE.format(n=n, to=to, tc=shlex.quote(TC_PATH), sender=sender,
                                root=shlex.quote(str(root.path.resolve())))]


def clock(seconds):
    """`seconds` since the epoch as the local HH:MM:SS the warnings print.

    @interacts  reads the local time zone.
    @deps       datetime; CLOCK_FORMAT.
    @complexity O(1).
    @alloc      one short string, returned.
    """
    return datetime.datetime.fromtimestamp(seconds).strftime(CLOCK_FORMAT)


# SHARED fix round 1 (Claude Opus 5.5, unreviewed): D20 item 5.
def marker_state(marker):
    """The first line of the ring marker at `marker` (its state), or None when nothing is there.

    Since D20 the marker is never removed: a ring that exits 0, or a codex
    join with nothing waiting, rewrites it as CLEAR_STATE. So the tests
    read its state, not whether it exists.

    @interacts  reads `marker`. Writes nothing.
    @deps       pathlib.
    @complexity O(1): one short file.
    @alloc      the file's text, freed on return.
    """
    try:
        return marker.read_text().partition("\n")[0]
    except FileNotFoundError:
        return None


def load_tc(root, where=None):
    """Load ../tc as a module with TC_ROOT set to `root` (or `where`, inside it), without running main().

    tc reads TC_ROOT once, at import, so it is set before the load and the
    old value is put back after. `where` is a path under root.path, for a
    test that needs a root with an awkward name.

    @interacts  sets and restores os.environ["TC_ROOT"]; runs tc's top
                level (constants only, no disk writes).
    @deps       importlib, os; _root.TC.
    @complexity O(1).
    @alloc      one module object, returned.
    """
    old = os.environ.get("TC_ROOT")
    os.environ["TC_ROOT"] = str(where if where is not None else root.path)
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
        """The fixture's label says plainly it is written from the plan's words, not recorded from codex.

        The label names the same codes the fakes use. It guards the
        wording: a label that claims a recording fails here.

        @interacts  none.
        @deps       the module constants.
        @complexity O(1).
        @alloc      none.
        """
        self.assertEqual(CODEX_FIXTURE_LABEL, "written from the plan's words (0 queued, 1 unknown thread), "
                                              "not recorded from a run of codex")
        self.assertEqual(CODEX_QUEUE_EXIT, {"queued": 0, "unknown thread": 1})
        for meaning, code in CODEX_QUEUE_EXIT.items():
            self.assertIn(f"{code} {meaning}", CODEX_FIXTURE_LABEL)

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
        self.assertEqual(recorded, [{"argv": ring_argv(root, 1, "c", "a"), "stdin": ""}])
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
            marked = marker_state(root.path / "mail" / ".ring-pending-c")
        self.assertEqual(code, 0, f"a failed ring failed the send: exit {code}: {err}")
        self.assertTrue(out.startswith("sent #1 to c: "), out)
        self.assertNotIn("rang codex", out)
        self.assertIn(RING_FAILED_WORDS.format(to="c", reason="fake codex: no thread t1") + "\n", err)
        self.assertEqual(len(recorded), 1)
        self.assertEqual(landed, ["000001-from-a.md"])
        self.assertEqual(marked, FAILED_STATE, "a failed ring left no pending mail/.ring-pending-c")

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
            marked = marker_state(marker)
            second = root.tc("send", "--from", "b", "--to", "c", "two")
            cleared = marker_state(marker)
            record = folder.parent / "calls.jsonl"
            self.assertTrue(record.exists(), f"{record} missing: the fake codex never ran")
            recorded = calls()
        self.assertEqual(first[0], 0, f"first send exited {first[0]}: {first[2]}")
        self.assertIn(RING_FAILED_WORDS.format(to="c", reason="fake codex: no thread t1") + "\n", first[2])
        self.assertEqual(marked, FAILED_STATE, "the failed ring left no pending marker")
        self.assertEqual(second[0], 0, f"second send exited {second[0]}: {second[2]}")
        self.assertEqual([call["argv"] for call in recorded],
                         [ring_argv(root, 1, "c", "a"), ring_argv(root, 2, "c", "b")])
        self.assertTrue(second[1].endswith(RANG_WORDS.format(to="c") + "\n"), second[1])
        self.assertEqual(cleared, CLEAR_STATE, "a ring that exited 0 left the marker pending")

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
            sent_out, sent_err = proc.communicate(timeout=FINISH_CEILING_SECONDS)
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
            out, err = proc.communicate(timeout=FINISH_CEILING_SECONDS)
            landed = sorted(p.name for p in box.glob("*.md"))
            record = folder.parent / "calls.jsonl"
            self.assertTrue(record.exists(), f"{record} missing: the fake codex never ran")
            recorded = calls()
        self.assertEqual(while_held, [], "the send landed while the test held the inbox lock")
        self.assertEqual(proc.returncode, 0, err)
        self.assertEqual(landed, ["000001-from-a.md"])
        self.assertEqual([call["argv"] for call in recorded], [ring_argv(root, 1, "c", "a")])

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
            out, err = proc.communicate(timeout=FINISH_CEILING_SECONDS)
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
                    marked = marker_state(root.path / "mail" / ".ring-pending-d")
                    self.join_codex(root)
                    root.tc("send", "--from", "a", "--to", "c", "hi")
                    self.assertTrue(record.exists(), f"{record} missing: the fake codex is not reachable")
                    recorded = calls()
                self.assertEqual(code, 0, f"exited {code}: {err}")
                self.assertIn(RING_FAILED_WORDS.format(to="d", reason=NOT_A_THREAD_ID), err)
                self.assertFalse(rang_bad, f"codex ran for thread_id {value!r}")
                self.assertEqual(landed, ["000001-from-a.md"])
                self.assertEqual(marked, FAILED_STATE, "no pending marker after a ring that could not be tried")
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
        self.assertEqual(code, EXIT_REFUSED, f"exited {code}: {err}")
        self.assertIn('CODEX_THREAD_ID "-x" is not a thread id', err)
        self.assertEqual(after, [], f"a refused join wrote {after}")

    def test_a_marker_that_cannot_be_written_is_said(self):
        """In process: when the marker cannot be written, the warning says a later send may not ring.

        SHARED fix round 1 (Claude Opus 5.5, unreviewed): D20 changed how.
        tc rewrites the marker in place, so the marker is a regular file
        that says clear, at READ_ONLY_FILE_MODE (before D20 a folder sat at
        the .tmp's name). The send still exits 0 with the mail in the
        inbox, the marker is left as it was, no .tmp is left, and the
        warning does not promise a ring it cannot keep. Skipped as root,
        which may write any file.

        @interacts  loads tc in process; makes mail/ and one read-only
                    marker; runs deliver_codex once with PATH set to the
                    root's (the harness's fake first) for that call.
        @deps       load_tc, marker_state, _root.TcRoot.fake_bin;
                    unittest.mock.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        if os.geteuid() == 0:
            self.skipTest("root may write a read-only file, so the marker cannot be made unwritable")
        card = {"name": "c", "kind": "codex", "route": "codex", "thread_id": THREAD}
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("codex", CODEX_QUEUE_EXIT["unknown thread"],
                                          stderr=FAKE_UNKNOWN_THREAD_STDERR)
            tc = load_tc(root)
            marker = root.path / "mail" / ".ring-pending-c"
            marker.parent.mkdir()
            marker.write_text(f"{CLEAR_STATE}\n")
            marker.chmod(READ_ONLY_FILE_MODE)
            with mock.patch.dict(os.environ, {"PATH": root.env["PATH"]}):
                got = tc.deliver_codex(card, "a", "c", "hi")
            record = folder.parent / "calls.jsonl"
            self.assertTrue(record.exists(), f"{record} missing: the fake codex never ran")
            landed = sorted(p.name for p in (root.path / "mail" / "to-c").glob("*.md"))
            marked = marker_state(marker)
            left = sorted(p.name for p in marker.parent.glob(".ring-pending-c.*"))
        self.assertEqual(got.exit, 0)
        self.assertEqual(landed, ["000001-from-a.md"])
        self.assertEqual(marked, CLEAR_STATE, "an unwritable marker changed")
        self.assertEqual(left, [], "a marker write left a file behind")
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
        self.assertEqual([call["argv"] for call in recorded], [ring_argv(root, 1, "c", "a")])

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
                         [ring_argv(root, 1, "c", "a"), ring_argv(root, 1, "c", "b")])

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

        subprocess.Popen is swapped for a stand-in whose communicate() times
        out, and os.killpg for a recorder, so nothing runs and no signal is
        sent. The test also checks the ring's stdin is /dev/null, it waits
        30 s, it starts codex in a session of its own and kills that group
        (CARDS fix round 1), and it decodes with errors="replace". Since
        D16 the words name when a send rings again (the marker's time plus
        RING_BACKOFF_SECONDS), and the marker says `timed out`.

        @interacts  loads tc in process; patches subprocess.Popen and
                    os.killpg for one deliver_codex call, which writes one
                    message under the root.
        @deps       load_tc, unittest.mock.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        seen, waits, killed = [], [], []

        class Hangs:
            """Stands in for subprocess.Popen: records how codex was started; communicate() times out.

            @interacts  appends to the test's lists.
            @deps       subprocess.TimeoutExpired.
            @complexity O(1) per call.
            @alloc      none beyond the list entries.
            """

            # Phase fix round 1 (Claude Opus 5.5, unreviewed): doc blocks on the stand-in's methods.
            def __init__(self, argv, **kwargs):
                """Record how codex was started; nothing runs.

                @interacts  appends to seen.
                @deps       STAND_IN_PID.
                @complexity O(1).
                @alloc      one list entry.
                """
                seen.append((argv, kwargs))
                self.args, self.pid, self.returncode = argv, STAND_IN_PID, None

            def __enter__(self):
                """Return the stand-in, as Popen's `with` does.

                @interacts  none.
                @deps       none.
                @complexity O(1).
                @alloc      none.
                """
                return self

            def __exit__(self, *exc):
                """Let any exception through, as Popen's `with` does.

                @interacts  none.
                @deps       none.
                @complexity O(1).
                @alloc      none.
                """
                return False

            def communicate(self, timeout=None):
                """Record the timeout asked for, then time out.

                @interacts  appends to waits.
                @deps       subprocess.TimeoutExpired.
                @complexity O(1).
                @alloc      one list entry and the exception.
                """
                waits.append(timeout)
                raise subprocess.TimeoutExpired(self.args, timeout)

            def wait(self, timeout=None):
                """Answer as a process killed by SIGKILL would.

                @interacts  sets returncode.
                @deps       signal.
                @complexity O(1).
                @alloc      none.
                """
                self.returncode = -signal.SIGKILL
                return self.returncode

        card = {"name": "c", "kind": "codex", "route": "codex", "thread_id": THREAD}
        with _root.TcRoot() as root:
            tc = load_tc(root)
            with mock.patch.object(subprocess, "Popen", Hangs), \
                    mock.patch.object(os, "killpg", lambda pid, sig: killed.append((pid, sig))):
                got = tc.deliver_codex(card, "a", "c", "hi")
            landed = sorted(p.name for p in (root.path / "mail" / "to-c").glob("*.md"))
            marker = root.path / "mail" / ".ring-pending-c"
            stamp, state = marker.stat().st_mtime, marker.read_text().splitlines()[0]
        self.assertEqual(got.exit, 0)
        self.assertIn(RING_TIMED_OUT_WORDS.format(to="c", reason=f"no answer in {CODEX_RING_SECONDS} s",
                                                  until=clock(stamp + RING_BACKOFF_SECONDS)),
                      got.warnings)
        self.assertEqual(state, TIMED_OUT_STATE)
        self.assertEqual(landed, ["000001-from-a.md"])
        self.assertEqual(len(seen), 1, "codex was not called exactly once")
        argv, kwargs = seen[0]
        self.assertEqual(argv[:4], ["codex", "queue", "--thread", THREAD])
        self.assertEqual((kwargs.get("stdin"), kwargs.get("start_new_session"), kwargs.get("errors")),
                         (subprocess.DEVNULL, True, "replace"))
        self.assertEqual(waits, [CODEX_RING_SECONDS])
        self.assertEqual(killed, [(STAND_IN_PID, signal.SIGKILL)])

    # CARDS fix round 1 (Claude Opus 5.5, unreviewed): a timeout kills codex's whole group.
    def test_a_ring_that_times_out_kills_codex_and_its_child(self):
        """In process, with the timeout patched to 2 s: a codex that started a child of its own leaves nothing running.

        The fake starts a sleeping child (as a node CLI starts a native
        codex), records both pids, and sleeps. Must reject a timeout that
        kills only the direct child: the grandchild would keep sleeping.
        Both pids are killed by their own pids at the end in case it did.

        @interacts  loads tc in process; runs deliver_codex once with PATH
                    set to put this file's own fake first and
                    CODEX_RING_SECONDS patched down; reads /proc.
        @deps       load_tc, own_fake, gone, kill_own_fake; unittest.mock.
        @complexity O(1): about SHORT_RING_SECONDS.
        @alloc      one TcRoot and one module.
        """
        card = {"name": "c", "kind": "codex", "route": "codex", "thread_id": THREAD}
        with _root.TcRoot() as root:
            env, record = own_fake(root, SPAWNING_FAKE_BODY, SLEEP=ORPHAN_SLEEP_SECONDS)
            tc = load_tc(root)
            with mock.patch.dict(os.environ, env), \
                    mock.patch.object(tc, "CODEX_RING_SECONDS", SHORT_RING_SECONDS):
                got = tc.deliver_codex(card, "a", "c", "hi")
            self.assertTrue(record.exists(), f"{record} missing: the fake codex never ran")
            ring = json.loads(record.read_text().splitlines()[0])
            try:
                child_gone = gone(ring["child"])
                fake_gone = gone(ring["pid"])
            finally:
                kill_own_fake(ring["child"], record)
                kill_own_fake(ring["pid"], record)
            stamp = (root.path / "mail" / ".ring-pending-c").stat().st_mtime
        self.assertEqual(got.exit, 0)
        self.assertIn(RING_TIMED_OUT_WORDS.format(to="c", reason=f"no answer in {SHORT_RING_SECONDS} s",
                                                  until=clock(stamp + RING_BACKOFF_SECONDS)),
                      got.warnings)
        self.assertTrue(fake_gone, "the timed-out codex is still running")
        self.assertTrue(child_gone, "codex's own child outlived the timed-out ring")

    # CARDS fix round 1 (Claude Opus 5.5, unreviewed): the ring names the root.
    def test_the_ring_names_the_root_and_quotes_it(self):
        """In process, with TC_ROOT holding a space: the ring's line is `TC_ROOT=<quoted root> <quoted tc>` in both commands.

        subprocess.Popen is swapped for a stand-in that exits 0, so nothing
        runs. Must reject a ring with no root (a Codex session with another
        default root would read the wrong mailbox) and an unquoted root
        (the command it is told to run would split at the space).

        @interacts  loads tc in process with TC_ROOT under the harness root;
                    patches subprocess.Popen for one ring_codex call, which
                    writes nothing.
        @deps       load_tc, RING_MESSAGE; unittest.mock, shlex.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        seen = []

        class Rings:
            """Stands in for subprocess.Popen: records the argv; codex exits 0 at once.

            @interacts  appends to the test's list.
            @deps       none.
            @complexity O(1).
            @alloc      none beyond the list entry.
            """

            # Phase fix round 1 (Claude Opus 5.5, unreviewed): doc blocks on the stand-in's methods.
            def __init__(self, argv, **kwargs):
                """Record the argv; codex has exited 0 already.

                @interacts  appends to seen.
                @deps       STAND_IN_PID.
                @complexity O(1).
                @alloc      one list entry.
                """
                seen.append(argv)
                self.pid, self.returncode = STAND_IN_PID, 0

            def __enter__(self):
                """Return the stand-in, as Popen's `with` does.

                @interacts  none.
                @deps       none.
                @complexity O(1).
                @alloc      none.
                """
                return self

            def __exit__(self, *exc):
                """Let any exception through, as Popen's `with` does.

                @interacts  none.
                @deps       none.
                @complexity O(1).
                @alloc      none.
                """
                return False

            def communicate(self, timeout=None):
                """Empty stdout and stderr, at once.

                @interacts  none.
                @deps       none.
                @complexity O(1).
                @alloc      two empty strings.
                """
                return "", ""

        with _root.TcRoot() as root:
            spaced = root.path / "a b"
            tc = load_tc(root, spaced)
            with mock.patch.object(subprocess, "Popen", Rings):
                reason = tc.ring_codex({"thread_id": THREAD}, "a", "c", 1)
        self.assertIsNone(reason)
        self.assertEqual(len(seen), 1, "codex was not called exactly once")
        self.assertEqual(seen[0][-1], RING_MESSAGE.format(n=1, to="c", sender="a", tc=shlex.quote(TC_PATH),
                                                          root=shlex.quote(str(spaced.resolve()))))
        self.assertIn(f"TC_ROOT='{spaced.resolve()}' ", seen[0][-1])

    # CARDS fix round 1 (Claude Opus 5.5, unreviewed): odd bytes from codex.
    def test_odd_bytes_from_codex_never_fail_a_send(self):
        """A fake that writes bytes that are not UTF-8 to stderr and exits 1: the send exits 0 and warns.

        Must reject a strict decode: it raises after the mail landed and
        the send exits 1 with a traceback.

        @interacts  one join, one send; this file's own fake.
        @deps       own_fake; _root.TcRoot.tc.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            env, record = own_fake(root, ODD_BYTES_FAKE_BODY)
            self.join_codex(root)
            code, out, err = root.tc("send", "--from", "a", "--to", "c", "hi", env=env)
            self.assertTrue(record.exists(), f"{record} missing: the fake codex never ran")
            landed = sorted(p.name for p in (root.path / "mail" / "to-c").glob("*.md"))
            marked = marker_state(root.path / "mail" / ".ring-pending-c")
        self.assertEqual(code, 0, f"odd bytes from codex failed the send: exit {code}")
        self.assertIn("not utf-8; the mail is in its inbox; the next send to c rings again\n", err)
        self.assertNotIn("Traceback", err)
        self.assertEqual(landed, ["000001-from-a.md"])
        self.assertEqual(marked, FAILED_STATE)

    # Phase fix round 1 (Claude Opus 5.5, unreviewed): D16 C1, mail before a join.
    def test_mail_from_before_a_codex_join_is_rung_by_the_next_send(self):
        """send to cx with no card, join cx as codex, send again: one ring, and join said what waits.

        The first send lands local (no card), so nothing rang for it. The
        join finds it, writes the marker and prints the waiting line; the
        next send rings this thread although the inbox was not empty. Must
        reject a join that ignores unread mail: the second send would find
        1 unread, no marker, and never ring.

        @interacts  two sends, one join (CODEX_THREAD_ID set, CLAUDECODE
                    unset), one fake codex.
        @deps       _root.TcRoot.tc, _root.TcRoot.fake_bin, ring_argv.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("codex", CODEX_QUEUE_EXIT["queued"])
            record = folder.parent / "calls.jsonl"
            marker = root.path / "mail" / ".ring-pending-cx"
            first = root.tc("send", "--from", "a", "--to", "cx", "one")
            rang_before_join = record.exists()
            joined = root.tc("join", "cx", env={"CODEX_THREAD_ID": THREAD, "CLAUDECODE": None})
            marked = marker_state(marker)
            second = root.tc("send", "--from", "a", "--to", "cx", "two")
            ran = record.exists()
            recorded = calls()
            cleared = marker_state(marker)
        self.assertEqual(first[0], 0, f"first send exited {first[0]}: {first[2]}")
        self.assertFalse(rang_before_join, "a send to a name with no card rang codex")
        self.assertEqual(joined, (0, "joined as cx (codex, account unknown, route codex)\n"
                                     + WAITING_WORDS.format(n=1, to="cx"), ""))
        self.assertEqual(marked, JOINED_STATE, "the join left no pending marker with mail waiting")
        self.assertTrue(ran, f"{record} missing: the fake codex never ran, so no send rang cx")
        self.assertEqual(second[0], 0, f"second send exited {second[0]}: {second[2]}")
        self.assertEqual([call["argv"] for call in recorded], [ring_argv(root, 2, "cx", "a")])
        self.assertEqual(cleared, CLEAR_STATE, "a ring that exited 0 left the marker pending")

    def test_a_rejoin_on_a_new_thread_is_rung_by_the_next_send(self):
        """A ring to t1 exits 0; cx rejoins on t2 with that mail unread; the next send rings t2.

        Must reject a join that ignores unread mail: every later send would
        find unread mail, no marker, and never ring t2.

        @interacts  two joins, two sends, one fake codex.
        @deps       _root.TcRoot.tc, _root.TcRoot.fake_bin, ring_argv.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("codex", CODEX_QUEUE_EXIT["queued"])
            self.join_codex(root, "cx")
            root.tc("send", "--from", "a", "--to", "cx", "one")
            rejoined = root.tc("join", "cx", env={"CODEX_THREAD_ID": OTHER_THREAD})
            sent = root.tc("send", "--from", "b", "--to", "cx", "two")
            record = folder.parent / "calls.jsonl"
            self.assertTrue(record.exists(), f"{record} missing: the fake codex never ran")
            recorded = calls()
        self.assertEqual(rejoined[0], 0, f"rejoin exited {rejoined[0]}: {rejoined[2]}")
        self.assertTrue(rejoined[1].endswith(WAITING_WORDS.format(n=1, to="cx")), rejoined[1])
        self.assertEqual(sent[0], 0, f"send exited {sent[0]}: {sent[2]}")
        self.assertEqual([call["argv"] for call in recorded],
                         [ring_argv(root, 1, "cx", "a"), ring_argv(root, 2, "cx", "b", OTHER_THREAD)])

    def test_a_sender_killed_mid_ring_leaves_the_marker(self):
        """A fake that kills its own sender mid-ring: the marker stays, and the next send rings.

        The marker is written before the ring, so a sender that dies while
        codex runs still leaves it. Must reject a marker written only after
        a failed ring: the killed send writes none, and the next send finds
        1 unread, no marker, and does not ring.

        @interacts  one join, two sends; this file's own fake, which sends
                    SIGKILL to the send that started it (checked by its
                    command line first), then a harness fake.
        @deps       own_fake, kill_own_fake, ring_argv; _root.TcRoot.tc,
                    _root.TcRoot.fake_bin.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            env, record = own_fake(root, KILLING_FAKE_BODY, TC=TC_PATH)
            self.join_codex(root)
            marker = root.path / "mail" / ".ring-pending-c"
            killed = root.tc("send", "--from", "a", "--to", "c", "one", env=env)
            self.assertTrue(record.exists(), f"{record} missing: the killing fake never ran")
            kill_own_fake(json.loads(record.read_text().splitlines()[0])["pid"], record)
            marked = marker_state(marker)
            folder, calls = root.fake_bin("codex", CODEX_QUEUE_EXIT["queued"])
            after = root.tc("send", "--from", "b", "--to", "c", "two")
            ran = (folder.parent / "calls.jsonl").exists()
            recorded = calls()
            landed = sorted(p.name for p in (root.path / "mail" / "to-c").glob("*.md"))
        self.assertEqual(killed[0], -signal.SIGKILL, f"the fake did not kill the send mid-ring: {killed}")
        self.assertEqual(marked, RINGING_STATE, "a send killed mid-ring left no pending marker")
        self.assertTrue(ran, "the second fake codex never ran, so the next send did not ring")
        self.assertEqual(after[0], 0, f"the next send exited {after[0]}: {after[2]}")
        self.assertEqual([call["argv"] for call in recorded], [ring_argv(root, 2, "c", "b")])
        self.assertEqual(landed, ["000001-from-a.md", "000002-from-b.md"])

    def test_a_ring_that_timed_out_holds_rings_for_the_backoff_window(self):
        """In process: a ring times out; a send inside the window rings nothing and warns; one after it rings.

        The ring's timeout is patched to SHORT_RING_SECONDS and this file's
        sleeping fake outlasts it. The clock (wall_clock) is then set
        INSIDE_WINDOW_SECONDS after the marker's time, then past
        RING_BACKOFF_SECONDS, so the test never sleeps 300 s. Must reject a
        send inside the window that rings: the harness fake would record a
        call. The mail lands and every send exits 0.

        @interacts  loads tc in process; runs deliver_codex three times,
                    first with PATH putting this file's sleeping fake first
                    (killed by the ring's own timeout, then by its pid in
                    case), then with the harness fake first and wall_clock
                    replaced.
        @deps       load_tc, own_fake, kill_own_fake, clock, ring_argv;
                    _root.TcRoot.fake_bin; unittest.mock.
        @complexity O(1): about SHORT_RING_SECONDS.
        @alloc      one TcRoot and one module.
        """
        card = {"name": "c", "kind": "codex", "route": "codex", "thread_id": THREAD}
        with _root.TcRoot() as root:
            env, record = own_fake(root, SLOW_FAKE_BODY, SLEEP=ORPHAN_SLEEP_SECONDS)
            folder, calls = root.fake_bin("codex", CODEX_QUEUE_EXIT["queued"])
            tc = load_tc(root)
            marker = root.path / "mail" / ".ring-pending-c"
            with mock.patch.dict(os.environ, env), \
                    mock.patch.object(tc, "CODEX_RING_SECONDS", SHORT_RING_SECONDS):
                timed_out = tc.deliver_codex(card, "a", "c", "one")
            self.assertTrue(record.exists(), f"{record} missing: the sleeping fake never ran")
            kill_own_fake(json.loads(record.read_text().splitlines()[0])["pid"], record)
            stamp, state = marker.stat().st_mtime, marker.read_text().splitlines()[0]
            with mock.patch.dict(os.environ, {"PATH": root.env["PATH"]}), \
                    mock.patch.object(tc, "wall_clock", lambda: stamp + INSIDE_WINDOW_SECONDS):
                held = tc.deliver_codex(card, "a", "c", "two")
            rang_inside = calls()
            kept = (marker.stat().st_mtime, marker_state(marker)) if marker.exists() else None
            with mock.patch.dict(os.environ, {"PATH": root.env["PATH"]}), \
                    mock.patch.object(tc, "wall_clock",
                                      lambda: stamp + RING_BACKOFF_SECONDS + PAST_WINDOW_SECONDS):
                rang = tc.deliver_codex(card, "a", "c", "three")
            self.assertTrue((folder.parent / "calls.jsonl").exists(), "the harness fake codex never ran")
            recorded = calls()
            cleared = marker_state(marker)
            landed = sorted(p.name for p in (root.path / "mail" / "to-c").glob("*.md"))
        until = clock(stamp + RING_BACKOFF_SECONDS)
        self.assertEqual(timed_out.exit, 0)
        self.assertIn(RING_TIMED_OUT_WORDS.format(to="c", reason=f"no answer in {SHORT_RING_SECONDS} s",
                                                  until=until), timed_out.warnings)
        self.assertEqual(state, TIMED_OUT_STATE)
        self.assertEqual(rang_inside, [], "a send inside the backoff window rang codex")
        self.assertEqual(held.exit, 0)
        self.assertEqual(held.warnings, [RING_PENDING_WORDS.format(to="c", at=clock(stamp), until=until)])
        self.assertEqual(kept, (stamp, TIMED_OUT_STATE), "a send inside the window changed the marker")
        self.assertEqual(rang.exit, 0)
        self.assertEqual([call["argv"] for call in recorded], [ring_argv(root, 3, "c", "a")])
        self.assertTrue(rang.words.endswith(RANG_WORDS.format(to="c")), rang.words)
        self.assertEqual(cleared, CLEAR_STATE, "a ring that exited 0 left the marker pending")
        self.assertEqual(landed, ["000001-from-a.md", "000002-from-a.md", "000003-from-a.md"])

    def test_a_ring_that_fails_fast_holds_nothing_back(self):
        """In process: codex exits 1, then the very next send, with the clock inside the window, rings.

        Only a timeout starts the backoff. Must reject a backoff after a
        fast failure: the second send would ring nothing.

        @interacts  loads tc in process; runs deliver_codex twice with PATH
                    putting the harness fake first, the second time with
                    wall_clock replaced.
        @deps       load_tc, ring_argv; _root.TcRoot.fake_bin; unittest.mock.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        card = {"name": "c", "kind": "codex", "route": "codex", "thread_id": THREAD}
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin(
                "codex", [CODEX_QUEUE_EXIT["unknown thread"], CODEX_QUEUE_EXIT["queued"]],
                stderr=FAKE_UNKNOWN_THREAD_STDERR)
            tc = load_tc(root)
            marker = root.path / "mail" / ".ring-pending-c"
            with mock.patch.dict(os.environ, {"PATH": root.env["PATH"]}):
                failed = tc.deliver_codex(card, "a", "c", "one")
                stamp, state = marker.stat().st_mtime, marker.read_text().splitlines()[0]
                with mock.patch.object(tc, "wall_clock", lambda: stamp + INSIDE_WINDOW_SECONDS):
                    again = tc.deliver_codex(card, "a", "c", "two")
            self.assertTrue((folder.parent / "calls.jsonl").exists(), "the fake codex never ran")
            recorded = calls()
        self.assertIn(RING_FAILED_WORDS.format(to="c", reason="fake codex: no thread t1"), failed.warnings)
        self.assertEqual(again.exit, 0)
        self.assertEqual([call["argv"] for call in recorded],
                         [ring_argv(root, 1, "c", "a"), ring_argv(root, 2, "c", "a")],
                         "a send right after a fast failure did not ring")
        self.assertEqual(state, FAILED_STATE)
        self.assertTrue(again.words.endswith(RANG_WORDS.format(to="c")), again.words)

    # Phase fix round 1 (Claude Opus 5.5, unreviewed): tc read prints after the lock.
    def test_a_stalled_reader_never_blocks_a_send(self):
        """A `tc read b` whose stdout pipe nobody drains: a send to b still lands within 1 s.

        The message is larger than a pipe's buffer, so the reader stops
        partway through printing it. It renamed the mail into read/ under
        the inbox lock and prints after letting go. Must reject a read that
        prints under the lock: the send would wait for it forever (it is
        killed at STALLED_READ_SEND_CEILING_SECONDS).

        @interacts  two sends, one background read left stalled (the
                    harness kills it by its own pid); reads /proc/locks.
        @deps       _root.TcRoot.tc, _root.TcRoot.start,
                    _root.flock_holders; subprocess, time.
        @complexity O(STALL_BODY_BYTES), plus at most BLOCK_CEILING_SECONDS
                    / LOCK_POLL_SECONDS polls.
        @alloc      one TcRoot, one background child, one message of
                    STALL_BODY_BYTES.
        """
        with _root.TcRoot() as root:
            root.tc("send", "--from", "a", "--to", "b", stdin="x" * STALL_BODY_BYTES)
            lock = root.path / "mail" / ".box-b.lock"
            moved = root.path / "mail" / "to-b" / "read" / "000001-from-a.md"
            reader = root.start("read", "b")
            deadline = time.monotonic() + BLOCK_CEILING_SECONDS
            while not moved.exists() and reader.pid not in _root.flock_holders(lock):
                if reader.poll() is not None or time.monotonic() >= deadline:
                    self.fail(f"tc read b neither moved its mail nor held {lock.name} "
                              f"within {BLOCK_CEILING_SECONDS} s")
                time.sleep(LOCK_POLL_SECONDS)
            try:
                code, out, err = root.tc("send", "--from", "c", "--to", "b", "hi",
                                         timeout=STALLED_READ_SEND_CEILING_SECONDS)
            except subprocess.TimeoutExpired:
                self.fail(f"a send to b waited past {STALLED_READ_SEND_CEILING_SECONDS} s "
                          f"behind a reader stalled on its stdout")
            stalled = reader.poll() is None
            landed = sorted(p.name for p in (root.path / "mail" / "to-b").glob("*.md"))
            read_once = moved.exists()
        self.assertTrue(stalled, "the reader finished printing, so it never stalled: this test proves nothing")
        self.assertEqual(code, 0, err)
        self.assertEqual(landed, ["000002-from-c.md"])
        self.assertTrue(read_once, "the stalled reader's mail is not in read/")


# P3 fix round 1b (Claude Opus 5.5, unreviewed): D35 (2) and D36 (1), the
# doorbell can't be switched off (C2 item 5), written here rather than read
# from tc: each sender's own last-ring record in its outbox branch, its
# mode, and what a send says when it cannot write it.
RANG_RECORD_NAME = ".rang-{to}"
RANG_RECORD_MODE = 0o600
RECORD_NOT_WRITTEN_WORDS = "could not be written"
RECORD_LOST_WORDS = "so this user's next send to {to} rings again"
# A folder mode with read and write but no search (x): no name in it can
# be looked at.
NO_SEARCH_FOLDER_MODE = 0o600
# A wrapper fake that writes what it finds at the sender's record (its
# mode and mtime, or null when nothing is there) to SAW, then runs the
# harness's fake codex FAKE with its own arguments, which records the call.
RECORD_LOOKING_FAKE_BODY = """import json, os, sys
try:
    st = os.lstat(RANG)
    seen = {"mode": st.st_mode & 0o7777, "mtime": st.st_mtime}
except FileNotFoundError:
    seen = None
with open(SAW, "w") as f:
    f.write(json.dumps(seen))
os.execv(FAKE, [FAKE] + sys.argv[1:])
"""
# How far the record's time may sit from this test's own clock: the
# seconds a tc start and a send take on a loaded machine.
RECORD_CLOCK_SLACK_SECONDS = 10
# A record dated this far after the replaced clock: a clock set back.
FUTURE_SECONDS = 10000


def rang_record(root, to):
    """Where the running user's last-ring record for `to` lives under `root`: outbox/<login>/.rang-<to>.

    @interacts  reads this process's user id and the user database.
    @deps       os, pwd; RANG_RECORD_NAME.
    @complexity O(1).
    @alloc      one path, returned.
    """
    return root.path / "outbox" / pwd.getpwuid(os.geteuid()).pw_name / RANG_RECORD_NAME.format(to=to)


class DoorbellRecordTest(unittest.TestCase):
    """C2 item 5 (D35 (2), D36 (1)): each sender's own last-ring record, written before every ring, and a send that rings when that record is old or cannot be trusted, whatever the marker says.

    @interacts  see the module block; the in-process tests also patch
                os.lstat and os.fstat (test_shared's owner patches) for
                the squatted branch, and chmod the branch and back.
    @deps       _root.TcRoot, load_tc, own_fake, ring_argv, rang_record.
    @complexity O(1) per test.
    @alloc      one TcRoot per test or case.
    """

    def test_each_ring_writes_the_senders_own_record_0600_before_it_rings(self):
        """A send to a codex name rings once, and a fake that looks first finds outbox/<user>/.rang-c already there, 0600, its mtime the send's time; a second send to the unread inbox rings nothing.

        Must reject a record written after the ring (a sender killed
        mid-ring would leave none, and its next send would read an older
        time), a record the group could read or write, and a second ring
        while the sender's own last ring is fresh and the marker clear.

        @interacts  one join; two sends with PATH putting this file's
                    record-looking wrapper first, which runs the harness
                    fake.
        @deps       own_fake, ring_argv, rang_record; _root.TcRoot.tc,
                    fake_bin; json, time.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("codex", CODEX_QUEUE_EXIT["queued"])
            saw = root.base / "record-seen.json"
            env, _ = own_fake(root, RECORD_LOOKING_FAKE_BODY, RANG=str(rang_record(root, "c")), SAW=str(saw),
                              FAKE=str(folder / "codex"))
            self.join_codex(root)
            began = time.time()
            first = root.tc("send", "--from", "a", "--to", "c", "one", env=env)
            second = root.tc("send", "--from", "a", "--to", "c", "two", env=env)
            self.assertTrue((folder.parent / "calls.jsonl").exists(), "the fake codex never ran")
            recorded = calls()
            seen = json.loads(saw.read_text()) if saw.exists() else "the wrapper never ran"
        self.assertEqual((first[0], second[0]), (0, 0), (first, second))
        self.assertEqual([call["argv"] for call in recorded], [ring_argv(root, 1, "c", "a")])
        self.assertIsInstance(seen, dict, f"no record when the ring ran: {seen}")
        self.assertEqual(seen["mode"], RANG_RECORD_MODE)
        self.assertLessEqual(abs(seen["mtime"] - began), RECORD_CLOCK_SLACK_SECONDS, seen)

    def join_codex(self, root, name="c"):
        """Join `name` as a Codex session on THREAD; fail the test if it does not.

        @interacts  one tc join with CODEX_THREAD_ID set for that call.
        @deps       _root.TcRoot.tc.
        @complexity O(1).
        @alloc      one card file.
        """
        code, out, err = root.tc("join", name, env={"CODEX_THREAD_ID": THREAD})
        self.assertEqual(code, 0, f"tc join {name} exited {code}: {err}")

    def test_a_marker_rewritten_to_clear_costs_at_most_one_backoff(self):
        """In process: a ring fails, a member rewrites the marker to clear, and a send inside this sender's backoff rings nothing; one after it rings again (the fake asserted called), the inbox never empty.

        The audit's MEDIUM-1 and REC-3 (test-strategist). The clock
        (wall_clock) is replaced, so no test sleeps RING_BACKOFF_SECONDS.
        Must reject a decision keyed on the marker alone: the forged
        `clear` would then hold the doorbell off until the inbox empties,
        which for a Codex member is never.

        @interacts  loads tc in process; runs deliver_codex three times
                    with PATH putting the harness fake first, the last two
                    with wall_clock replaced; rewrites the marker in place.
        @deps       load_tc, ring_argv, rang_record; _root.TcRoot.fake_bin;
                    unittest.mock.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        card = {"name": "c", "kind": "codex", "route": "codex", "thread_id": THREAD}
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("codex", [CODEX_QUEUE_EXIT["unknown thread"], CODEX_QUEUE_EXIT["queued"]],
                                          stderr=FAKE_UNKNOWN_THREAD_STDERR)
            tc = load_tc(root)
            marker = root.path / "mail" / ".ring-pending-c"
            with mock.patch.dict(os.environ, {"PATH": root.env["PATH"]}):
                failed = tc.deliver_codex(card, "a", "c", "one")
                stamp = rang_record(root, "c").stat().st_mtime
                marker.write_text(f"{CLEAR_STATE}\n")  # a member's rewrite, in place
                with mock.patch.object(tc, "wall_clock", lambda: stamp + INSIDE_WINDOW_SECONDS):
                    inside = tc.deliver_codex(card, "a", "c", "two")
                rang_inside = calls()
                with mock.patch.object(tc, "wall_clock", lambda: stamp + RING_BACKOFF_SECONDS + PAST_WINDOW_SECONDS):
                    after = tc.deliver_codex(card, "a", "c", "three")
            self.assertTrue((folder.parent / "calls.jsonl").exists(), "the fake codex never ran")
            recorded = calls()
        self.assertEqual((failed.exit, inside.exit, after.exit), (0, 0, 0))
        self.assertEqual(len(rang_inside), 1, "a send inside the sender's own backoff rang over a clear marker")
        self.assertEqual([call["argv"] for call in recorded],
                         [ring_argv(root, 1, "c", "a"), ring_argv(root, 3, "c", "a")],
                         "a forged clear marker held the doorbell off past the sender's own backoff")
        self.assertTrue(after.words.endswith(RANG_WORDS.format(to="c")), after.words)

    def test_a_record_missing_untrusted_dated_after_now_or_unreachable_counts_as_old(self):
        """In process: after a ring that went through (marker clear, one unread), the sender's record is moved aside, made a link, dated after now, put in a branch with no search, or its branch reported as another user's; a send inside the backoff then rings again each time, and says so when it could not write the record.

        C2 item 5: a record dated after now (the clock was set back), or
        one that cannot be read or written, counts as old, with a warning
        for one that cannot be written: a ring too many, never a lost
        wake (D14). Must reject a send that trusts any of them as a fresh
        ring, and one that writes the record through a link or into a
        branch that is not this user's.

        @interacts  per case: loads tc in process; runs deliver_codex
                    twice with PATH putting the harness fake first, the
                    second with wall_clock replaced; renames, links,
                    dates or chmods the record or its branch by hand (the
                    branch's mode put back), or patches os.lstat and
                    os.fstat so the branch reads as another user's.
        @deps       load_tc, ring_argv, rang_record; owner_patched_lstat
                    and owner_patched_fstat from test_shared.py;
                    _root.TcRoot.fake_bin; os, stat, unittest.mock.
        @complexity O(1) per case, five cases.
        @alloc      one TcRoot and one module per case.
        """
        from test_shared import owner_patched_fstat, owner_patched_lstat
        card = {"name": "c", "kind": "codex", "route": "codex", "thread_id": THREAD}
        cases = ("missing", "a link", "dated after now", "a branch with no search", "a squatted branch")
        for case in cases:
            with self.subTest(case=case), _root.TcRoot() as root:
                folder, calls = root.fake_bin("codex", CODEX_QUEUE_EXIT["queued"])
                tc = load_tc(root)
                record = rang_record(root, "c")
                branch = record.parent
                with mock.patch.dict(os.environ, {"PATH": root.env["PATH"]}), contextlib.ExitStack() as stack:
                    first = tc.deliver_codex(card, "a", "c", "one")
                    stamp = record.stat().st_mtime
                    if case == "missing":
                        os.rename(record, branch / "aside")
                    elif case == "a link":
                        os.rename(record, branch / "aside")
                        record.symlink_to(branch / "aside")
                    elif case == "dated after now":
                        os.utime(record, (stamp + FUTURE_SECONDS, stamp + FUTURE_SECONDS))
                    elif case == "a branch with no search":
                        old_mode = stat.S_IMODE(os.lstat(branch).st_mode)
                        branch.chmod(NO_SEARCH_FOLDER_MODE)
                        stack.callback(branch.chmod, old_mode)
                    else:
                        stack.enter_context(mock.patch.object(os, "lstat", owner_patched_lstat(branch)))
                        stack.enter_context(mock.patch.object(os, "fstat", owner_patched_fstat(branch)))
                    stack.enter_context(mock.patch.object(tc, "wall_clock", lambda: stamp + INSIDE_WINDOW_SECONDS))
                    second = tc.deliver_codex(card, "a", "c", "two")
                self.assertTrue((folder.parent / "calls.jsonl").exists(), "the fake codex never ran")
                recorded = calls()
            self.assertEqual((first.exit, second.exit), (0, 0), (first, second))
            self.assertEqual([call["argv"] for call in recorded],
                             [ring_argv(root, 1, "c", "a"), ring_argv(root, 2, "c", "a")],
                             f"a record {case} was trusted as a fresh ring")
            unwritten = [w for w in second.warnings if RECORD_NOT_WRITTEN_WORDS in w]
            if case in ("a link", "a branch with no search", "a squatted branch"):
                self.assertEqual(len(unwritten), 1, second.warnings)
                self.assertIn(RECORD_LOST_WORDS.format(to="c"), unwritten[0])
            else:
                self.assertEqual(unwritten, [], second.warnings)


if __name__ == "__main__":
    unittest.main()
