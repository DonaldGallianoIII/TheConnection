"""
Tests for the wake files of P3 fix round 1b (D35 (1), D36 (2); the audit's
HIGH-2, audits/2026-10-15-1409-full): each name's wait and watch locks
live in its owner's own inbox at 0600, a link or FIFO planted at a lock's
name is moved aside and never followed, a listener started before the
change still counts on a private mailbox until it re-arms and never on a
shared one, only a name's owner listens for it on a shared mailbox, a
private mailbox keeps its wait exactly, and tc wait and tc watch close
their lock file on every way out. And D35 (3): a busy refusal names the
holder, its user and pid, and whom to ask, and tc health lists a lock
held by someone other than its name's owner, while the gate's health
never does. And item 6, a2's class proof for the wake files
(WakeFilesAreTheirOwnersTest): no member who is not a name's owner holds
or redirects its wait lock, watch lock, inbox lock or ring marker, and a
file planted at the owner's lock name is moved aside with words. Its
mutations, and the lines each turned red, are in handoffs/P3FIX.md.

Model:  Claude Opus 5.5 (the P3 fixer, round 1b), 2026-10-15
Status: unreviewed

One Linux user plays every part. Where a second owner is needed (D36's
refusal of anyone but a name's owner), tc runs in process and os.lstat
and os.fstat report the card and the inbox as another user's
(test_shared.owner_patched_lstat and owner_patched_fstat), as the SHARED
suites do; where a lock's holder must be another member, os.stat reports
that holder's /proc/<pid> as another user's (holder_patched_stat). The
second-user walk is qa/human/route-shared.md.

@interacts  runs ../tc through tests/_root.py under a throwaway TC_ROOT
            (init, joins, sends, waits, watches, health); makes inboxes,
            links, FIFOs and lock files by hand; starts children of its
            own (python3 -c HOLD_SCRIPT, which opens a lock file and holds
            its flock until the harness kills it by its pid) and reads
            /proc/locks to prove a listener; loads tc as a module (TC_ROOT
            set for the load and put back) and runs cmd_wait, cmd_watch,
            cmd_read, cmd_health, cmd_gate and health_snapshot in process
            with os.lstat, os.fstat or os.stat patched, or with
            resource.setrlimit made a no-op (so a wait never caps this
            process), tc's gpu_stats, unread, machine_stats or
            flock_within replaced, SSH_ORIGINAL_COMMAND set, stdout and
            stderr captured, and warnings recorded; reads /proc/self/fd.
            The class proof starts one-shot member children
            (MEMBER_SCRIPT) that make, hold or rewrite a file in place,
            and runs the owner's command, or a send, in process with
            os.lstat, os.fstat and os.stat patched (members_patched),
            tc's unread, machine_stats or read_regular_file wrapped to
            call a member while the command runs, and wall_clock replaced
            (never a RING_BACKOFF_SECONDS sleep); it makes a link, a FIFO
            and a hard link by hand, and a fake codex first on PATH, its
            calls asserted. P3 fix round 2 (Claude Opus 5.5, unreviewed:
            test-strategist REC-1, REC-2, REC-3 and REC-6): two children
            hold one inbox lock shared (HOLD_SHARED_SCRIPT), one child
            holds a lock outside mail/ that a link at the old place leads
            to, and tc's process_uid is made to see no process, as
            hidepid does; the audit's LOW-1 test runs tc's hold_wake_lock
            twice in process, the second with tc's move_aside, name_taken
            or open_wake_lock wrapped to run the first whole, or to
            rename the second's fresh lock by hand, at one moment of it.
            Writes nothing outside the root's temp folder.
@deps       python3 stdlib (argparse, contextlib, fcntl, gc, io, json, os,
            pathlib, pwd, stat, subprocess, sys, time, unittest,
            unittest.mock, warnings); tests/_root.py; UmaskTestCase,
            load_tc, owner_patched_lstat, owner_patched_fstat,
            primary_group and tree from test_shared.py; ../tc. Imported
            by test_inbox_pinned.py: hold, holder_patched_stat and
            HOLDER_UID_STEP; and by test_gate.py: hold (P3 fix round 2,
            Claude Opus 5.5, unreviewed).
@complexity O(1) per test: a handful of tc runs and at most four children
            per root, each wait or watch run under a second or two; the
            private pin test waits out one of tc's polls (POLL_SECONDS),
            and each refused command one LOCK_WAIT_SECONDS. The class
            proof: 5 subtests and 8 planted cases, each a fresh root.
@alloc      one TcRoot per test or case, removed when its context exits,
            with every child it started.
"""

import argparse
import contextlib
import fcntl
import gc
import io
import json
import os
import pathlib
import pwd
import stat
import subprocess
import sys
import time
import unittest
import warnings
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
# Run as `python3 -m unittest tests.test_wake_files` from the repo root,
# tests/ is not on sys.path; under discover it is. Add it once so both work.
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import _root  # noqa: E402  (needs the path line above)
from test_shared import (UmaskTestCase, contents, load_tc, owner_patched_fstat,  # noqa: E402
                         owner_patched_lstat, primary_group, tree)

# The names: the member who owns an inbox, a name nobody joined, and a
# name for a private mailbox's new listener. Made up.
OWNER = "ann"
GHOST = "ghost"
NEW_NAME = "newcomer"
# The two kinds of listener, and their locks' names in the owner's inbox
# (tc's WAKE_LOCK_NAME), written here rather than read from tc.
KINDS = ("wait", "watch")
LOCK_NAME = ".{kind}.lock"
# Where the locks lived before round 1b (tc's OLD_WAKE_LOCK_NAME), the
# switch-over's old place.
OLD_LOCK_NAME = ".{kind}-{name}.lock"
# A wake lock's mode: its owner's alone.
WAKE_LOCK_MODE = 0o600
# Where tc moves an entry it finds at a lock's name: the first aside name.
FIRST_ASIDE = "{lock}.planted-1"
# Exit codes (contracts.md): refused with words, a wait's timeout, another
# listener holds the lock, a watch's alert.
EXIT_REFUSED = 1
EXIT_TIMEOUT = 2
EXIT_ALREADY = 3
EXIT_ALERT = 5
# tc's words for a second listener, as before round 1b, by kind.
ALREADY_WORDS = {"wait": "ALREADY LISTENING: another `tc wait {name}` is running. Not starting a second.\n",
                 "watch": "ALREADY WATCHING: another `tc watch {name}` is running. Not starting a second.\n"}
# C4's words for D36 (2), exit 1 (contracts.md, "Only a name's owner
# listens for it").
ONLY_OWNER_WORDS = "tc {kind}: {name}'s inbox belongs to {owner}; only {owner} listens for it\n"
NOBODY_JOINED_WORDS = ("tc {kind}: nobody has joined as {name} on this shared mailbox; its owner runs tc join "
                       "{name} first\n")
# What tc says when it moved a planted entry aside, in parts: what it was,
# then where it went.
MOVED_WORDS = "tc {kind}: {path} was {what} owned by {owner}, not this user's own {kind} lock; moved it aside to {aside}"
# Thresholds no real machine reaches, so a watch can only heartbeat, never
# alert; and one that always alerts on memory, for the exit 5 case.
QUIET = ["--load-ratio", "100000", "--mem-min-pct", "0", "--gpu-max-c", "100000"]
QUIET_ARGS = {"load_ratio": 100000.0, "mem_min_pct": 0.0, "gpu_max_c": 100000.0}
ALERT_MEM_MIN_PCT = 101.0
# A wait that times out at once, and a watch that heartbeats at once,
# with a poll gap the run never reaches.
AT_ONCE = "0"
WATCH_POLL = "1"
# A child that opens the lock file named by its first argument (making it
# when missing, as a listener before round 1b did), holds its flock
# exclusive, says so on stdout, and sleeps the seconds of its second
# argument; the harness kills it by its pid at the latest.
HOLD_SCRIPT = """import fcntl, sys, time
f = open(sys.argv[1], "a")
fcntl.flock(f, fcntl.LOCK_EX)
print("held", flush=True)
time.sleep(float(sys.argv[2]))
"""
# P3 fix round 2 (Claude Opus 5.5, unreviewed): test-strategist REC-3.
# HOLD_SCRIPT's twin that holds the flock shared, as local senders do,
# so two children can hold one inbox lock at once.
HOLD_SHARED_SCRIPT = """import fcntl, sys, time
f = open(sys.argv[1], "a")
fcntl.flock(f, fcntl.LOCK_SH)
print("held", flush=True)
time.sleep(float(sys.argv[2]))
"""
HELD_LINE = "held\n"
# Far past any test here; the child is killed long before.
HOLD_SECONDS = 60
# How long a planted FIFO may hold a wait or watch up: never, so the run's
# own timeout is the ceiling.
FIFO_CEILING_SECONDS = 5
# A real background wait's length, killed by the harness once the test
# has what it needs; a second wait's, which exits 3 at once.
LISTEN_SECONDS = "30"
SECOND_WAIT_SECONDS = "1"
# tc's poll gap (POLL_SECONDS), plus a margin for a loaded machine: how
# long a waiting tc wait may take to see mail that landed.
WAKE_CEILING_SECONDS = 5 + 5
# How long a child gets to take its lock, and the gap between looks.
LOCK_CEILING_SECONDS = _root.LOCK_CEILING_SECONDS
LOCK_POLL_SECONDS = _root.LOCK_POLL_SECONDS
# What a link planted at a lock's name leads to, outside TC_ROOT.
TARGET_TEXT = "a file outside the mailbox; tc must not touch it\n"
# P3 fix round 1b (Claude Opus 5.5, unreviewed): D35 (3), item 3. A busy
# refusal (exit 10) names each holder and whom to ask; on a shared mailbox
# the user who ran init as well; and says so when /proc/locks names nobody.
EXIT_BUSY = 10
HELD_BY_WORDS = ("tc: another process is holding {what}'s lock: {user} (pid {pid}); try again. If it stays held, "
                 "ask {user} to let it go{init}.\n")
ASK_INIT_WORDS = ", or ask the user who ran init ({init}) to act"
LET_GO_WORDS = ("tc: another process held {what}'s lock past {seconds} s, and /proc/locks names no holder now "
                "(it let go, or the process that took it has ended); try again\n")
LOCK_WAIT_SECONDS = 3
# How much higher than the running user's id a holder's process is
# reported, so the holder is another member and never the init user
# (whom as_member style patching reports one higher).
HOLDER_UID_STEP = 2
# tc health's line for a lock someone else holds, and the gate's command
# for its health.
HELD_LINE_WORDS = "held       {path}: {name}'s {lock} lock, held by {user} (pid {pid}), not by its owner {owner}"
GATE_HEALTH = "/x/tc health --json"
GATE_KEY = "farkey"
# P3 fix round 2 (Claude Opus 5.5, unreviewed): REC-3. The busy words for
# a lock with several holders: each named as HOLDER_WORDS, joined in
# /proc/locks order, and every holder's user asked, by name order.
MANY_HELD_BY_WORDS = ("tc: another process is holding {what}'s lock: {holders}; try again. If it stays held, ask "
                      "{ask} to let it go{init}.\n")
HOLDER_WORDS = "{user} (pid {pid})"
ASK_JOIN_WORDS = " or "
HOLDERS_JOIN_WORDS = ", "
# P3 fix round 1b (Claude Opus 5.5, unreviewed): item 6, the class proof.
# A one-shot child, a member who is not the name's owner: it acts on the
# file named by its first argument, as its second says, and prints what
# came of it on one line. One Linux user cannot see the kernel refuse
# another user's open, so it applies the kernel's rule for a member who
# is not the file's owner itself: it may open a file already there only
# when the file's mode gives the group the access it asks for (read or
# write to hold, write to rewrite), and prints DENIED otherwise. A file
# not there yet it makes, as a member may in a folder the group can
# write. `hold` takes the flock exclusive without waiting (HELD, or BUSY
# when someone holds it) and keeps it, sleeping the seconds of its third
# argument, until the harness kills it by its pid. `rewrite:<state>:<t>`
# writes <state> as the first line in place (no moment where the file
# reads empty) and, unless <t> is "-", sets its time to <t>.
MEMBER_SCRIPT = """import fcntl, os, stat, sys, time
path, act = sys.argv[1], sys.argv[2]
try:
    st = os.lstat(path)
except FileNotFoundError:
    st = None
want = stat.S_IWGRP if act.startswith("rewrite") else stat.S_IRGRP | stat.S_IWGRP
if st is not None and not stat.S_IMODE(st.st_mode) & want:
    print("DENIED", flush=True)
    sys.exit(0)
if act == "hold":
    fd = os.open(path, os.O_RDONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o664)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("BUSY", flush=True)
        sys.exit(0)
    print("HELD", flush=True)
    time.sleep(float(sys.argv[3]))
else:
    _, state, stamp = act.split(":", 2)
    data = (state + "\\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    os.pwrite(fd, data, 0)
    os.ftruncate(fd, len(data))
    if stamp != "-":
        os.utime(fd, (float(stamp), float(stamp)))
    print("REWRITTEN", flush=True)
"""
# What MEMBER_SCRIPT prints. Its BUSY line (a flock someone else holds)
# has no name here: no test asserts it (P3 fix round 2, Claude Opus 5.5,
# unreviewed: the audit's LOW-9).
MEMBER_HELD, MEMBER_DENIED, MEMBER_REWROTE = "HELD", "DENIED", "REWRITTEN"
# How long the owner's wait runs, and the owner's watch's heartbeat and
# poll gap: one poll, where the member tries again, then the end.
CLASS_LISTEN_SECONDS = 1.0
CLASS_WATCH_POLL_SECONDS = 0.2
# Python start-up and tc's imports on a busy machine, on top of the
# inbox lock's bound: a refusal past both is a hang.
LOCK_REFUSE_MARGIN_SECONDS = 3
# The ring marker's states (tc's RING_CLEAR and RING_TIMED_OUT), its
# name, the backoff, and how far past the sender's own backoff the
# replaced clock stands.
CLEAR_STATE, TIMED_OUT_STATE = "clear", "timed out"
MARKER_NAME = ".ring-pending-{name}"
RING_BACKOFF_SECONDS = 300
PAST_BACKOFF_SECONDS = 10
THREAD = "t1"
RANG_LINE = "rang codex {to} (queued; delivered when its turn ends or the session is resumed)"
# The kinds of entry a member plants at the owner's lock name.
PLANTS = ("a file", "a symlink", "a FIFO", "a file with another name too (a hard link)")
# P3 fix round 2 (Claude Opus 5.5, unreviewed): the audit's LOW-1. The
# moments a second of the owner's own waits is interrupted at, the second
# aside name (tc's PLANTED_ASIDE_NAME with k 2), and the ending the flock
# moment's hand move gives the lock.
OWN_LOCK_BEFORE_LOOK = "before its look"
OWN_LOCK_BEFORE_MOVE = "between its look and its move"
OWN_LOCK_BEFORE_FLOCK = "before its flock"
SECOND_ASIDE = "{lock}.planted-2"
DISPLACED_SUFFIX = ".moved-by-another-wait"


def login(uid):
    """The login of user number `uid`, or the number as text when the machine has no such user (tc's user_name).

    @interacts  reads the user database.
    @deps       pwd.
    @complexity O(1).
    @alloc      one short string, returned.
    """
    try:
        return pwd.getpwuid(uid).pw_name
    except KeyError:
        return str(uid)


def run_in_process(call):
    """Run `call` with stdout and stderr captured: (code, out, err). A SystemExit gives its code, 0 for a return.

    @interacts  runs `call`; captures stdout and stderr.
    @deps       contextlib, io.
    @complexity O(1), plus the call.
    @alloc      the captured text, returned.
    """
    out, err = io.StringIO(), io.StringIO()
    code = 0
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            call()
        except SystemExit as stop:
            code = 0 if stop.code is None else stop.code
    return code, out.getvalue(), err.getvalue()


def hold(root, path, script=HOLD_SCRIPT):
    """Start HOLD_SCRIPT (or `script`, HOLD_SHARED_SCRIPT) on `path` and return its Popen once it holds the flock (its HELD_LINE read).

    @interacts  starts one child through the harness (killed by its pid in
                teardown); reads one line of its stdout.
    @deps       _root.TcRoot.start; sys; HOLD_SCRIPT, HOLD_SECONDS, HELD_LINE.
    @complexity O(1).
    @alloc      one Popen, registered with the root.
    """
    proc = root.start(argv=[sys.executable, "-c", script, str(path), str(HOLD_SECONDS)])
    line = proc.stdout.readline()
    if line != HELD_LINE:
        raise AssertionError(f"the holder of {path} never said it held it: {line!r}")
    return proc


# P3 fix round 2 (Claude Opus 5.5, unreviewed): test-strategist REC-3.
def holders_in_order(path):
    """The pids holding an flock on `path` now, in /proc/locks order, which is the order tc's busy words name them in; a waiter's line ("->") is never a holder.

    @interacts  stats `path`; reads /proc/locks. Writes nothing.
    @deps       os, pathlib; _root.LOCKS_KIND_COLUMN, LOCKS_PID_COLUMN,
                LOCKS_FILE_COLUMN.
    @complexity O(k) over k lines in /proc/locks (tens).
    @alloc      one list of pids, returned.
    """
    st = os.stat(path)
    key = f"{os.major(st.st_dev):02x}:{os.minor(st.st_dev):02x}:{st.st_ino}"
    found = []
    for line in pathlib.Path("/proc/locks").read_text().splitlines():
        cols = line.split()
        if (len(cols) > _root.LOCKS_FILE_COLUMN and cols[_root.LOCKS_KIND_COLUMN] == "FLOCK"
                and cols[_root.LOCKS_FILE_COLUMN] == key):
            found.append(int(cols[_root.LOCKS_PID_COLUMN]))
    return found


def proven(path, proc):
    """True once /proc/locks shows `proc` holding an flock on `path`, within LOCK_CEILING_SECONDS; False if it exits or the time runs out first.

    @interacts  reads /proc/locks (the harness's flock_holders).
    @deps       _root.flock_holders; time.
    @complexity at most LOCK_CEILING_SECONDS / LOCK_POLL_SECONDS reads.
    @alloc      none past each read.
    """
    deadline = time.monotonic() + LOCK_CEILING_SECONDS
    while time.monotonic() < deadline:
        if proc.pid in _root.flock_holders(path):
            return True
        if proc.poll() is not None:
            return False
        time.sleep(LOCK_POLL_SECONDS)
    return False


def health(root):
    """`tc health --json` under `root`, parsed.

    @interacts  one tc run.
    @deps       _root.TcRoot.tc; json.
    @complexity O(1).
    @alloc      one dict, returned.
    """
    code, out, err = root.tc("health", "--json")
    if code != 0:
        raise AssertionError(f"tc health --json exited {code}: {err}")
    return json.loads(out)


def listen(root, kind, name, *extra):
    """Run `tc wait <name>` or `tc watch <name>` (`kind`) under `root` so that it ends at once: (exit, stdout, stderr).

    @interacts  one tc run.
    @deps       _root.TcRoot.tc; AT_ONCE, WATCH_POLL, QUIET.
    @complexity O(1).
    @alloc      the run's output, returned.
    """
    if kind == "wait":
        return root.tc("wait", name, "--timeout", AT_ONCE, *extra)
    return root.tc("watch", name, "--heartbeat", AT_ONCE, "--poll", WATCH_POLL, *QUIET, *extra)


def lock_fds(path):
    """How many of this process's descriptors are open on the file at `path` now (/proc/self/fd).

    @interacts  stats `path` and every entry of /proc/self/fd.
    @deps       os.
    @complexity O(d) over d open descriptors (tens).
    @alloc      none past the listing.
    """
    want = os.stat(path)
    count = 0
    for name in os.listdir("/proc/self/fd"):
        try:
            st = os.stat(f"/proc/self/fd/{name}")
        except OSError:
            continue
        count += (st.st_dev, st.st_ino) == (want.st_dev, want.st_ino)
    return count


def holder_patched_stat(pids, uid):
    """An os.stat that reports /proc/<pid> for each of `pids` as owned by user `uid`, and everything else as it is: how a holder's process is made another member's, as the SHARED suites patch a file's owner.

    @interacts  none until called; then stats what it is given.
    @deps       os, stat.
    @complexity O(1) per call.
    @alloc      one stat result per call.
    """
    real = os.stat
    procs = {f"/proc/{pid}" for pid in pids}

    def patched(path, *args, **kwargs):
        st = real(path, *args, **kwargs)
        if not isinstance(path, int) and os.fspath(path) in procs:
            fields = list(st[:stat.ST_CTIME + 1])
            fields[stat.ST_UID] = uid
            return os.stat_result(fields)
        return st
    return patched


def member(root, path, act):
    """Run MEMBER_SCRIPT once on `path` with `act` ("hold", or "rewrite:<state>:<time>"): (its Popen, the one line it printed). A child that holds keeps running until the harness kills it by its pid.

    @interacts  starts one child through the harness; reads one line of
                its stdout.
    @deps       _root.TcRoot.start; sys; MEMBER_SCRIPT, HOLD_SECONDS.
    @complexity O(1).
    @alloc      one Popen, registered with the root.
    """
    proc = root.start(argv=[sys.executable, "-c", MEMBER_SCRIPT, str(path), act, str(HOLD_SECONDS)])
    return proc, proc.stdout.readline().strip()


def identity(path):
    """(st_dev, st_ino) of what has the name `path` now, never through a link.

    @interacts  lstats `path`.
    @deps       os.
    @complexity O(1).
    @alloc      one tuple, returned.
    """
    st = os.lstat(path)
    return st.st_dev, st.st_ino


@contextlib.contextmanager
def members_patched(root_path, planted, pids):
    """While entered, the running user is a member and others are too, as the SHARED suites report owners: os.lstat, os.fstat and os.stat report ROOT and its .shared as the init user's (one id up, as test_shared.as_member), each file whose (st_dev, st_ino) is in `planted` as another member's (HOLDER_UID_STEP up), and /proc/<pid> for each pid in `pids` as that member's. `planted` and `pids` are read at each call, so a caller may add to them while it runs.

    @interacts  patches os.lstat, os.fstat and os.stat while entered;
                lstats ROOT and its .shared once.
    @deps       os, stat, unittest.mock; HOLDER_UID_STEP.
    @complexity O(1) per call, plus O(p) over p pids for os.stat.
    @alloc      the patches, undone on exit; one stat result per call.
    """
    me = os.geteuid()
    init_files = {identity(root_path), identity(root_path / ".shared")}
    real_lstat, real_fstat, real_stat = os.lstat, os.fstat, os.stat

    def owned(st, uid):
        if uid is None:
            return st
        fields = list(st[:stat.ST_CTIME + 1])
        fields[stat.ST_UID] = uid
        return os.stat_result(fields)

    def owner(st):
        key = (st.st_dev, st.st_ino)
        return me + 1 if key in init_files else me + HOLDER_UID_STEP if key in planted else None

    def lstat(path, *args, **kwargs):
        st = real_lstat(path, *args, **kwargs)
        return owned(st, owner(st))

    def fstat(fd):
        st = real_fstat(fd)
        return owned(st, owner(st))

    def stat_(path, *args, **kwargs):
        st = real_stat(path, *args, **kwargs)
        if not isinstance(path, int) and os.fspath(path) in {f"/proc/{pid}" for pid in pids}:
            return owned(st, me + HOLDER_UID_STEP)
        return owned(st, owner(st))

    with mock.patch.object(os, "lstat", lstat), mock.patch.object(os, "fstat", fstat), \
            mock.patch.object(os, "stat", stat_):
        yield


def wait_args(name, timeout):
    """The Namespace cmd_wait reads, for an in-process run.

    @interacts  none.
    @deps       argparse.
    @complexity O(1).
    @alloc      one Namespace, returned.
    """
    return argparse.Namespace(name=name, timeout=timeout, keepalive=False)


def watch_args(name, heartbeat, mem_min_pct=QUIET_ARGS["mem_min_pct"]):
    """The Namespace cmd_watch reads, for an in-process run: no names tracked, thresholds no machine reaches but `mem_min_pct`.

    @interacts  none.
    @deps       argparse; QUIET_ARGS, WATCH_POLL.
    @complexity O(1).
    @alloc      one Namespace, returned.
    """
    return argparse.Namespace(name=name, heartbeat=heartbeat, poll=float(WATCH_POLL), names="",
                              load_ratio=QUIET_ARGS["load_ratio"], mem_min_pct=mem_min_pct,
                              gpu_max_c=QUIET_ARGS["gpu_max_c"])


class WakeLockPlaceTest(UmaskTestCase):
    """D35 (1): each lock in its owner's own inbox at 0600, anything else at its name moved aside, the switch-over's two halves, and (P3 fix round 2) a plant another member holds is never the owner's listener.

    @interacts  see the module block.
    @deps       _root.TcRoot, UmaskTestCase, primary_group, listen, hold,
                proven, health, member, identity, members_patched,
                load_tc.
    @complexity O(1) per test.
    @alloc      one TcRoot per case.
    """

    def test_the_wait_and_watch_locks_are_their_owners_alone_in_its_inbox(self):
        """Private and shared (ann joined): tc wait ann and tc watch ann each leave mail/to-ann/.<kind>.lock, a regular file of this user's at 0600, and nothing at the old place in mail/.

        Must reject a lock left in mail/ (the group could open it there
        and hold its flock), and one made at any mode the group may read.

        @interacts  per mailbox: an init and a join when shared; one wait
                    and one watch.
        @deps       listen, primary_group; _root.TcRoot.tc; os, stat.
        @complexity O(1): four tc runs per mailbox.
        @alloc      one TcRoot per mailbox.
        """
        _, group, _ = primary_group()
        for shared in (False, True):
            with self.subTest(shared=shared), _root.TcRoot() as root:
                if shared:
                    self.assertEqual(root.tc("init", "--shared", "--group", group)[0], 0)
                    self.assertEqual(root.tc("join", OWNER, env={"CLAUDECODE": "1"})[0], 0)
                runs = {kind: listen(root, kind, OWNER) for kind in KINDS}
                mail = root.path / "mail"
                seen = {}
                for kind in KINDS:
                    path = mail / f"to-{OWNER}" / LOCK_NAME.format(kind=kind)
                    st = os.lstat(path) if os.path.lexists(path) else None
                    seen[kind] = None if st is None else (stat.S_ISREG(st.st_mode), stat.S_IMODE(st.st_mode), st.st_uid)
                old = [kind for kind in KINDS if os.path.lexists(mail / OLD_LOCK_NAME.format(kind=kind, name=OWNER))]
                self.assertEqual(runs["wait"][0], EXIT_TIMEOUT, runs["wait"])
                self.assertEqual(runs["watch"][0], 0, runs["watch"])
                for kind in KINDS:
                    self.assertEqual(seen[kind], (True, WAKE_LOCK_MODE, os.geteuid()),
                                     f"the {kind} lock is not this user's own regular file at 0600")
                self.assertEqual(old, [], "a lock was made at the old place in mail/")

    def test_a_link_or_fifo_at_a_locks_name_is_moved_aside_never_followed_or_waited_on(self):
        """A symlink to a file outside the mailbox, or a FIFO, at mail/to-x/.wait.lock or .watch.lock: tc wait x and tc watch x run as ever (exit 2, exit 0) within FIFO_CEILING_SECONDS, say what they moved and where, leave it at the first aside name unchanged (the link's target too), and hold a new 0600 lock of their own.

        P3 fix round 1b: these cases were in test_shared.py's D17 and D19
        tests, refused with exit 1 while the locks lived in mail/. In the
        owner's inbox, the owner's tc moves them aside (D35 (1)). Must
        reject an open that follows the link (the target changes or the
        lock is taken through it), one without O_NONBLOCK (the FIFO
        blocks the run past its ceiling), and a run that refuses instead
        of moving it.

        @interacts  per case: an inbox, a link and its target, or a FIFO,
                    made by hand; one wait or watch.
        @deps       listen; _root.TcRoot.tc; os, stat, subprocess.
        @complexity O(1) per case, four cases.
        @alloc      one TcRoot per case.
        """
        for kind in KINDS:
            for planted in ("a symlink", "a FIFO"):
                with self.subTest(kind=kind, planted=planted), _root.TcRoot() as root:
                    box = root.path / "mail" / "to-x"
                    box.mkdir(parents=True)
                    lock = box / LOCK_NAME.format(kind=kind)
                    target = root.base / "target"
                    target.write_text(TARGET_TEXT)
                    if planted == "a symlink":
                        lock.symlink_to(target)
                    else:
                        os.mkfifo(lock)
                    try:
                        code, out, err = listen(root, kind, "x")
                    except subprocess.TimeoutExpired:
                        self.fail(f"tc {kind} blocked on {planted} at its lock's name")
                    aside = box / FIRST_ASIDE.format(lock=lock.name)
                    moved = os.lstat(aside).st_mode if os.path.lexists(aside) else None
                    st = os.lstat(lock)
                    after = target.read_text()
                    self.assertEqual(code, EXIT_TIMEOUT if kind == "wait" else 0, err)
                    self.assertIn(MOVED_WORDS.format(kind=kind, path=lock, what=planted, owner=login(os.geteuid()),
                                                     aside=aside), err)
                    self.assertTrue(moved is not None and (stat.S_ISLNK(moved) if planted == "a symlink"
                                                           else stat.S_ISFIFO(moved)),
                                    f"{planted} did not move to {aside} as itself")
                    self.assertEqual((stat.S_ISREG(st.st_mode), stat.S_IMODE(st.st_mode)), (True, WAKE_LOCK_MODE))
                    self.assertEqual(after, TARGET_TEXT, "the link's target changed")

    def test_on_a_private_mailbox_a_listener_from_before_still_counts_until_it_rearms(self):
        """The switch-over, private: with mail/.wait-x.lock and .watch-x.lock held by listeners from before round 1b, tc health names their pids, a new tc wait x and tc watch x exit 3 with today's words and make no inbox; once they go, a new wait runs and health names none; a FIFO at the old place stops nothing, and nor does a link there to a lock a live child holds, which health names for nobody.

        Must reject a new listener that ignores the old place (two
        listeners for one name while the dev branch's sessions re-arm),
        and a listeners() that drops the old holder (health and the board
        would say nobody listens while one does). The second half is in
        test_on_a_shared_mailbox_the_old_place_is_never_read. P3 fix round
        2 (Claude Opus 5.5, unreviewed): test-strategist REC-6. Must
        reject an old-place check that follows a link: the link leads to
        a lock someone holds, and the new wait would stop with exit 3.

        @interacts  three children holding the old locks and the link's
                    target, killed by their own pids; health, waits and
                    watches; one FIFO and one link made by hand.
        @deps       hold, health, listen; _root.TcRoot.tc; os.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            mail = root.path / "mail"
            mail.mkdir()
            holders = {kind: hold(root, mail / OLD_LOCK_NAME.format(kind=kind, name="x")) for kind in KINDS}
            seen = health(root)
            stopped = {kind: listen(root, kind, "x") for kind in KINDS}
            made = (mail / "to-x").exists()
            for proc in holders.values():
                proc.kill()
                proc.wait(timeout=_root.REAP_CEILING_SECONDS)
            later = listen(root, "wait", "x")
            after = health(root)
            os.mkfifo(mail / OLD_LOCK_NAME.format(kind="wait", name="y"))
            # P3 fix round 2 (Claude Opus 5.5, unreviewed): REC-6, the link leads to a lock a live child holds.
            elsewhere = root.base / "held-elsewhere.lock"
            target_holder = hold(root, elsewhere)
            (mail / OLD_LOCK_NAME.format(kind="wait", name="z")).symlink_to(elsewhere)
            fifo, link = listen(root, "wait", "y"), listen(root, "wait", "z")
            linked = health(root)
            still_held = target_holder.pid in _root.flock_holders(elsewhere)
        self.assertEqual((seen["listeners"].get("x"), seen["watchers"].get("x")),
                         (holders["wait"].pid, holders["watch"].pid), "health lost a listener from before round 1b")
        for kind in KINDS:
            self.assertEqual(stopped[kind], (EXIT_ALREADY, ALREADY_WORDS[kind].format(name="x"), ""))
        self.assertFalse(made, "a listener stopped by the old place made an inbox")
        self.assertEqual(later[0], EXIT_TIMEOUT, later)
        self.assertIsNone(after["listeners"].get("x"), after["listeners"])
        self.assertTrue(still_held, "the link's target was not held while the waits ran, so the case proves nothing")
        self.assertEqual((fifo[0], link[0]), (EXIT_TIMEOUT, EXIT_TIMEOUT), (fifo, link))
        self.assertIsNone(linked["listeners"].get("z"), f"health named the link's holder for z: {linked['listeners']}")

    def test_on_a_shared_mailbox_the_old_place_is_never_read(self):
        """The switch-over, shared: with mail/.wait-ann.lock held by another process, tc health never names it for ann, and ann's own tc wait is not stopped: it holds mail/to-ann/.wait.lock, and health names its pid.

        Must reject a shared mailbox that reads the old place: any member
        may make and hold mail/.wait-ann.lock there, the hole D35 closes.

        @interacts  an init and a join; one child holding the old lock;
                    one background tc wait, proven in /proc/locks; two
                    health runs.
        @deps       hold, health, proven, primary_group;
                    _root.TcRoot.tc, start.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        _, group, _ = primary_group()
        with _root.TcRoot() as root:
            self.assertEqual(root.tc("init", "--shared", "--group", group)[0], 0)
            self.assertEqual(root.tc("join", OWNER, env={"CLAUDECODE": "1"})[0], 0)
            mail = root.path / "mail"
            holder = hold(root, mail / OLD_LOCK_NAME.format(kind="wait", name=OWNER))
            before = health(root)
            waiting = root.start("wait", OWNER, "--timeout", LISTEN_SECONDS)
            held = proven(mail / f"to-{OWNER}" / LOCK_NAME.format(kind="wait"), waiting)
            during = health(root)
        self.assertNotEqual(before["listeners"].get(OWNER), holder.pid, "a shared mailbox read the old place")
        self.assertTrue(held, f"ann's own tc wait (pid {waiting.pid}) never held its lock in her inbox")
        self.assertEqual(during["listeners"].get(OWNER), waiting.pid)

    # P3 fix round 2 (Claude Opus 5.5, unreviewed): test-strategist REC-2, the P3 review's HIGH-2 by name.
    def test_a_lock_another_member_planted_and_holds_is_never_the_owners_listener_even_when_proc_hides_its_holder(self):
        """Shared, ann joined, ann not listening: a member plants mail/to-ann/.wait.lock (group-writable inbox) and holds it, and /proc hides the member's process (process_uid None, as hidepid does): tc.listeners("wait") and tc health's listeners name no pid for ann and never the member's.

        HIGH-2's own symptom: a member plants and holds `.wait.lock` in
        another member's inbox, and health names the member's pid as the
        owner's listener, so the owner's relay believes a session listens
        that never started. Must reject a listeners() that counts a lock
        file the inbox's owner does not own: under hidepid, that owner
        check is all that stands between the plant and a false
        `listening`, since the holder check cannot see the holder.

        @interacts  an init and a join; one member child that plants and
                    holds the lock, killed by its own pid; loads tc and
                    calls listeners and health_snapshot in process with
                    os.lstat, os.fstat and os.stat patched
                    (members_patched), process_uid made to see nothing and
                    gpu_stats replaced.
        @deps       member, identity, members_patched, load_tc,
                    primary_group; _root.TcRoot.tc; unittest.mock.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        _, group, _ = primary_group()
        with _root.TcRoot() as root:
            self.assertEqual(root.tc("init", "--shared", "--group", group)[0], 0)
            self.assertEqual(root.tc("join", OWNER, env={"CLAUDECODE": "1"})[0], 0)
            lock = root.path / "mail" / f"to-{OWNER}" / LOCK_NAME.format(kind="wait")
            planter, said = member(root, lock, "hold")
            tc = load_tc(root)
            with members_patched(root.path, {identity(lock)}, {planter.pid}), \
                    mock.patch.object(tc, "process_uid", lambda pid: None), \
                    mock.patch.object(tc, "gpu_stats", lambda: None):
                seen = tc.listeners("wait")
                snap = tc.health_snapshot(gpu=False)
            holders = _root.flock_holders(lock)
            self.assertEqual(said, MEMBER_HELD, "the member could not plant and hold the lock")
            self.assertIn(planter.pid, holders, "the member's plant was not held while health looked")
            for source, listening in (("listeners", seen), ("tc health", snap["listeners"])):
                with self.subTest(read_by=source):
                    self.assertIsNone(listening.get(OWNER), f"{source} named a listener for {OWNER} from a lock "
                                                            f"another member planted: {listening}")
                    self.assertNotIn(planter.pid, listening.values(), f"{source} named the member's pid")


class OnlyTheOwnerListensTest(UmaskTestCase):
    """D36 (2): on a shared mailbox only the owner of a name's card listens for it; a private mailbox keeps its wait exactly.

    @interacts  see the module block.
    @deps       _root.TcRoot, UmaskTestCase, primary_group, load_tc,
                owner_patched_lstat, owner_patched_fstat, tree,
                run_in_process.
    @complexity O(1) per test.
    @alloc      one TcRoot per test.
    """

    def test_a_wait_or_watch_by_anyone_but_the_names_owner_or_on_a_name_nobody_joined_is_refused_and_makes_nothing(self):
        """Shared: ann's card, inbox and read/ reported as another user's, tc wait ann and tc watch ann (in process) exit 1 with C4's words naming that user; tc wait ghost and tc watch ghost (nobody joined) exit 1 with C4's other words; the root is unchanged throughout.

        Must reject a wait with no owner check (D36 (2)): with the inbox
        and its read/ reported as the card owner's too, D20's check
        passes, nothing else stops it, and it would make its lock in
        another member's inbox and hold it. Must reject a name nobody
        joined polled as no mail (the old way), and anything made before a
        refusal.

        @interacts  an init and a join; loads tc and runs cmd_wait and
                    cmd_watch in process with os.lstat and os.fstat
                    patched and resource.setrlimit made a no-op; two tc
                    runs; lstats the whole root before and after.
        @deps       load_tc, owner_patched_lstat, owner_patched_fstat,
                    primary_group, tree, run_in_process, login, wait_args,
                    watch_args; _root.TcRoot.tc; unittest.mock.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        _, group, _ = primary_group()
        with _root.TcRoot() as root:
            self.assertEqual(root.tc("init", "--shared", "--group", group)[0], 0)
            self.assertEqual(root.tc("join", OWNER, env={"CLAUDECODE": "1"})[0], 0)
            card, box = root.path / "cards" / f"{OWNER}.json", root.path / "mail" / f"to-{OWNER}"
            other = login(os.lstat(card).st_uid + 1)
            before = tree(root.path, under=None)
            tc = load_tc(root)
            ran = {}
            calls = {"wait": lambda: tc.cmd_wait(wait_args(OWNER, 0.0)),
                     "watch": lambda: tc.cmd_watch(watch_args(OWNER, 0.0))}
            for kind in KINDS:
                with mock.patch.object(os, "lstat", owner_patched_lstat(card, box, box / "read")), \
                        mock.patch.object(os, "fstat", owner_patched_fstat(box, box / "read")), \
                        mock.patch.object(tc.resource, "setrlimit", lambda *args: None), \
                        mock.patch.object(tc, "gpu_stats", lambda: None):
                    ran[kind] = run_in_process(calls[kind])
            nobody = {kind: listen(root, kind, GHOST) for kind in KINDS}
            after = tree(root.path, under=None)
        for kind in KINDS:
            with self.subTest(kind=kind):
                self.assertEqual(ran[kind], (EXIT_REFUSED, "", ONLY_OWNER_WORDS.format(kind=kind, name=OWNER,
                                                                                         owner=other)))
                self.assertEqual(nobody[kind], (EXIT_REFUSED, "", NOBODY_JOINED_WORDS.format(kind=kind, name=GHOST)))
        self.assertEqual(after, before, "a refused wait or watch made or changed something")

    def test_a_private_mailbox_keeps_its_wait_exactly(self):
        """a2's pin for every agent on this machine: on a private mailbox, tc wait <new name> makes the inbox and its lock, tc health names its pid, a second tc wait exits 3, mail makes the first exit 0, and a timeout exits 2.

        Must reject a private wait refused for want of a card (D36 (2) is
        shared only), one that makes no inbox, one health does not name,
        a second wait that starts, and a wait that misses its mail.

        @interacts  one background tc wait, proven in /proc/locks; health;
                    a second wait; one send; one read; one more wait.
        @deps       proven, health; _root.TcRoot.tc, start; os, stat.
        @complexity O(1), plus up to one tc poll for the mail.
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            box = root.path / "mail" / f"to-{NEW_NAME}"
            lock = box / LOCK_NAME.format(kind="wait")
            first = root.start("wait", NEW_NAME, "--timeout", LISTEN_SECONDS)
            held = proven(lock, first)
            made = (box.is_dir(), (box / "read").is_dir(), stat.S_IMODE(os.lstat(lock).st_mode) if held else None)
            named = health(root)["listeners"].get(NEW_NAME)
            second = root.tc("wait", NEW_NAME, "--timeout", SECOND_WAIT_SECONDS)
            sent = root.tc("send", "--from", "a", "--to", NEW_NAME, "hello")
            try:
                out, err = first.communicate(timeout=WAKE_CEILING_SECONDS)
            except subprocess.TimeoutExpired:
                self.fail(f"the first wait did not see its mail in {WAKE_CEILING_SECONDS} s")
            woke = first.returncode
            read = root.tc("read", NEW_NAME)
            timed_out = root.tc("wait", NEW_NAME, "--timeout", SECOND_WAIT_SECONDS)
        self.assertTrue(held, f"tc wait {NEW_NAME} (pid {first.pid}) never held {lock}")
        self.assertEqual(made, (True, True, WAKE_LOCK_MODE))
        self.assertEqual(named, first.pid, "tc health did not name the listener's pid")
        self.assertEqual(second, (EXIT_ALREADY, ALREADY_WORDS["wait"].format(name=NEW_NAME), ""))
        self.assertEqual(sent[0], 0, sent)
        self.assertEqual((woke, out), (0, f"MAIL: 1 unread for {NEW_NAME}. Run: tc read {NEW_NAME}\n"), err)
        self.assertEqual(read[0], 0, read)
        self.assertEqual(timed_out[0], EXIT_TIMEOUT, timed_out)
        self.assertTrue(timed_out[1].startswith(f"TIMEOUT: no mail for {NEW_NAME}"), timed_out)


class HolderNamedTest(UmaskTestCase):
    """D35 (3), item 3 of round 1b: a busy refusal names the holder, and tc health lists a lock held by someone other than its name's owner.

    The extended held-lock test (test_shared.py, NoLostMailNoHangTest,
    the audit's REC-4) checks the words for each command that waits; this
    class checks the words' two forms and the health line, and since P3
    fix round 2 (Claude Opus 5.5, unreviewed) the words and the line for
    a lock with two holders and for the owner's own holder.

    @interacts  see the module block.
    @deps       _root.TcRoot, UmaskTestCase, primary_group, load_tc, hold,
                holders_in_order, holder_patched_stat, run_in_process,
                login.
    @complexity O(1) per test.
    @alloc      one TcRoot per case.
    """

    def test_a_busy_refusal_names_the_holder_and_on_a_shared_mailbox_the_init_user(self):
        """A child holds b's inbox lock: tc read b exits 10, naming the running user and the child's pid and asking that user to let it go, and on a shared mailbox the user who ran init to act; with nobody holding it by the time tc looks, the words say so.

        Must reject words that name no holder or the wrong pid, words
        that ask the init user on a private mailbox (nobody ran init
        there), and words that guess a holder when /proc/locks names
        none.

        @interacts  per mailbox: an init and a join when shared, a send,
                    one child holding the inbox lock, one tc read; then
                    loads tc and runs cmd_read in process with tc's
                    flock_within made to give up.
        @deps       hold, primary_group, load_tc, run_in_process, login;
                    _root.TcRoot.tc; unittest.mock.
        @complexity O(1): about LOCK_WAIT_SECONDS per refused read.
        @alloc      two TcRoots and one module.
        """
        _, group, _ = primary_group()
        mine = login(os.geteuid())
        seen = {}
        for shared in (False, True):
            with _root.TcRoot() as root:
                if shared:
                    self.assertEqual(root.tc("init", "--shared", "--group", group)[0], 0)
                    self.assertEqual(root.tc("join", "b", env={"CLAUDECODE": "1"})[0], 0)
                self.assertEqual(root.tc("send", "--from", "a", "--to", "b", "hi")[0], 0)
                holder = hold(root, root.path / "mail" / ".box-b.lock")
                seen[shared] = (root.tc("read", "b"), holder.pid)
        with _root.TcRoot() as root:
            self.assertEqual(root.tc("send", "--from", "a", "--to", "b", "hi")[0], 0)
            tc = load_tc(root)
            with mock.patch.object(tc, "flock_within", lambda *args, **kwargs: False):
                let_go = run_in_process(lambda: tc.cmd_read(argparse.Namespace(name="b")))
        for shared, (ran, pid) in seen.items():
            with self.subTest(shared=shared):
                init = ASK_INIT_WORDS.format(init=mine) if shared else ""
                self.assertEqual(ran, (EXIT_BUSY, "", HELD_BY_WORDS.format(what="b", user=mine, pid=pid, init=init)))
        self.assertEqual(let_go, (EXIT_BUSY, "", LET_GO_WORDS.format(what="b", seconds=LOCK_WAIT_SECONDS)))

    def test_health_lists_a_lock_held_by_someone_not_its_names_owner_and_the_gate_never_does(self):
        """Shared, ann joined: one child holds ann's inbox lock and another a file it planted at her watch lock's name, each reported as another member's: tc health --json lists both under held_by_others, tc health prints a held line for each, and health's watchers name no pid for ann; the gate's health --json has no such key; on a private mailbox the same holds list nothing.

        Must reject a health that names nobody for a lock a stranger
        holds (the stuck member learns of it only from a failed command),
        a gate that hands that line to a far key (round 1c's allow list,
        GATE_HEALTH_KEYS, leaves it home; P3 fix round 2: the audit's
        LOW-10), and a private mailbox that ever reports one (one user).
        P3 fix round 2
        (Claude Opus 5.5, unreviewed): test-strategist REC-1. Must reject
        a listeners() that names any holder of an owner's lock: the only
        holder of ann's watch lock is another member's process, and
        health would call it ann's watcher (the P3 review's HIGH-2, "tc
        health reported the holder as listening").

        @interacts  per mailbox: an init and a join when shared, a send,
                    two children holding locks; loads tc and runs
                    health_snapshot, cmd_health and cmd_gate in process
                    with os.stat reporting the children's /proc/<pid> as
                    another member's, and tc's gpu_stats replaced.
        @deps       hold, holder_patched_stat, primary_group, load_tc,
                    run_in_process, login; _root.TcRoot.tc; json,
                    unittest.mock.
        @complexity O(1).
        @alloc      two TcRoots and two modules.
        """
        _, group, _ = primary_group()
        other = login(os.geteuid() + HOLDER_UID_STEP)
        got = {}
        for shared in (False, True):
            with _root.TcRoot() as root:
                name = OWNER if shared else "b"
                if shared:
                    self.assertEqual(root.tc("init", "--shared", "--group", group)[0], 0)
                    self.assertEqual(root.tc("join", OWNER, env={"CLAUDECODE": "1"})[0], 0)
                self.assertEqual(root.tc("send", "--from", "a", "--to", name, "hi")[0], 0)
                box_lock = root.path / "mail" / f".box-{name}.lock"
                planted = root.path / "mail" / f"to-{name}" / LOCK_NAME.format(kind="watch")
                holders = [hold(root, box_lock), hold(root, planted)]
                tc = load_tc(root)
                with mock.patch.object(os, "stat", holder_patched_stat([p.pid for p in holders],
                                                                       os.geteuid() + HOLDER_UID_STEP)), \
                        mock.patch.object(tc, "gpu_stats", lambda: None), \
                        mock.patch.dict(os.environ, {"SSH_ORIGINAL_COMMAND": GATE_HEALTH}):
                    snap = tc.health_snapshot()
                    text = run_in_process(lambda: tc.cmd_health(argparse.Namespace(json=False)))
                    gate = run_in_process(lambda: tc.cmd_gate(argparse.Namespace(as_name=GATE_KEY)))
                got[shared] = (snap["held_by_others"], text, json.loads(gate[1]), [p.pid for p in holders],
                               box_lock, planted, snap["watchers"])
        private, _, _, _, _, _, _ = got[False]
        self.assertEqual(private, [], "a private mailbox reported a lock held by someone else")
        held, text, gated, (box_pid, watch_pid), box_lock, planted, watchers = got[True]
        mine = login(os.geteuid())
        want = [{"name": OWNER, "lock": "watch", "path": str(planted), "pid": watch_pid, "user": other, "owner": mine},
                {"name": OWNER, "lock": "inbox", "path": str(box_lock), "pid": box_pid, "user": other, "owner": mine}]
        self.assertEqual(held, want)
        # P3 fix round 2 (Claude Opus 5.5, unreviewed): REC-1, the holder is never ann's watcher.
        self.assertIsNone(watchers.get(OWNER), f"health named another member's holder as ann's watcher: {watchers}")
        for entry in want:
            self.assertIn(HELD_LINE_WORDS.format(**entry) + "\n", text[1])
        self.assertNotIn("held_by_others", gated, "the gate's health handed a far key who holds which lock")

    # P3 fix round 2 (Claude Opus 5.5, unreviewed): test-strategist REC-3, D35 (3)'s "names the holder".
    def test_health_never_lists_the_owners_own_holder_and_names_every_holder_of_a_shared_lock(self):
        """Shared, ann joined, a send to ann: ann's own process holds her wait lock, and two children hold her inbox lock shared, one reported as another member's: held_by_others lists exactly that one, and ann's tc read exits 10 with words naming both holders, each by user and pid, and asking both users and the init user.

        Must reject a held_by_others that lists the owner's own holder as
        someone else's (ann's own listener reported as a stranger's), and
        a holder map that keeps one holder per file: a lock held shared
        has several, and the busy words and the held line would drop all
        but one.

        @interacts  an init, a join, a send; three children holding locks,
                    killed by their own pids; loads tc and calls
                    held_by_others and cmd_read in process with os.stat
                    reporting one child's /proc/<pid> as another member's;
                    reads /proc/locks.
        @deps       hold, holders_in_order, holder_patched_stat,
                    primary_group, load_tc, run_in_process, login;
                    _root.TcRoot.tc; argparse, unittest.mock.
        @complexity O(1): one LOCK_WAIT_SECONDS of waiting.
        @alloc      one TcRoot and one module.
        """
        _, group, _ = primary_group()
        mine, other = login(os.geteuid()), login(os.geteuid() + HOLDER_UID_STEP)
        with _root.TcRoot() as root:
            self.assertEqual(root.tc("init", "--shared", "--group", group)[0], 0)
            self.assertEqual(root.tc("join", OWNER, env={"CLAUDECODE": "1"})[0], 0)
            self.assertEqual(root.tc("send", "--from", "ben", "--to", OWNER, "hi")[0], 0)
            wait_lock = root.path / "mail" / f"to-{OWNER}" / LOCK_NAME.format(kind="wait")
            box_lock = root.path / "mail" / f".box-{OWNER}.lock"
            own = hold(root, wait_lock)
            sharers = [hold(root, box_lock, HOLD_SHARED_SCRIPT) for _ in range(2)]
            stranger = sharers[-1].pid
            tc = load_tc(root)
            with mock.patch.object(os, "stat", holder_patched_stat([stranger], os.geteuid() + HOLDER_UID_STEP)):
                held = tc.held_by_others(True)
                ran = run_in_process(lambda: tc.cmd_read(argparse.Namespace(name=OWNER)))
            order = holders_in_order(box_lock)
            users = {pid: other if pid == stranger else mine for pid in order}
            words = MANY_HELD_BY_WORDS.format(
                what=OWNER, holders=HOLDERS_JOIN_WORDS.join(HOLDER_WORDS.format(user=users[pid], pid=pid)
                                                            for pid in order),
                ask=ASK_JOIN_WORDS.join(sorted(set(users.values()))), init=ASK_INIT_WORDS.format(init=mine))
            self.assertIn(own.pid, _root.flock_holders(wait_lock), "ann's own holder let go before health looked")
            self.assertEqual(sorted(order), sorted(p.pid for p in sharers), "the two sharers did not both hold it")
            self.assertEqual(held, [{"name": OWNER, "lock": "inbox", "path": str(box_lock), "pid": stranger,
                                     "user": other, "owner": mine}],
                             "held_by_others did not list exactly the other member's holder")
            self.assertEqual(ran, (EXIT_BUSY, "", words), "the busy words did not name every holder")


class LockFileClosedTest(UmaskTestCase):
    """Item 8 of round 1b, from round 1a's report: tc wait and tc watch close their lock file on every way out.

    @interacts  see the module block.
    @deps       _root.TcRoot, UmaskTestCase, load_tc, run_in_process,
                lock_fds.
    @complexity O(1) per case.
    @alloc      one TcRoot per case.
    """

    def test_wait_and_watch_close_their_lock_file_on_every_way_out(self):
        """In process, private: tc wait exits 0, 2, 3, 1 (a refusal in a poll) and by an exception, and tc watch exits 0, 3, 5 and by an exception; after each, no descriptor of this process is open on the lock, and no ResourceWarning was raised.

        Must reject a lock file left for the garbage collector or the
        process's exit (round 1a's class proof had to ignore the
        ResourceWarning it raised).

        @interacts  per case: a send or a held lock as setup; loads tc and
                    runs cmd_wait or cmd_watch in process with
                    resource.setrlimit made a no-op, tc's gpu_stats
                    replaced, and for some cases tc's unread or
                    machine_stats replaced; records warnings; collects
                    garbage; reads /proc/self/fd.
        @deps       load_tc, run_in_process, lock_fds, wait_args,
                    watch_args; _root.TcRoot.tc; fcntl, gc, unittest.mock,
                    warnings.
        @complexity O(1) per case, nine cases.
        @alloc      one TcRoot and one module per case.
        """
        def broken(*args, **kwargs):
            raise RuntimeError("a fault inside the listener")

        cases = [  # kind, label, what it expects, setup, what to replace in tc, the call's Namespace
            ("wait", "exit 0", 0, "send", None, wait_args("x", 1.0)),
            ("wait", "exit 2", EXIT_TIMEOUT, None, None, wait_args("x", 0.0)),
            ("wait", "exit 3", EXIT_ALREADY, "hold", None, wait_args("x", 0.0)),
            ("wait", "a refusal", EXIT_REFUSED, None, ("unread", lambda *a, **k: sys.exit(EXIT_REFUSED)),
             wait_args("x", 1.0)),
            ("wait", "an exception", RuntimeError, None, ("unread", broken), wait_args("x", 1.0)),
            ("watch", "exit 0", 0, None, None, watch_args("x", 0.0)),
            ("watch", "exit 3", EXIT_ALREADY, "hold", None, watch_args("x", 0.0)),
            ("watch", "exit 5", EXIT_ALERT, None, None, watch_args("x", 0.0, ALERT_MEM_MIN_PCT)),
            ("watch", "an exception", RuntimeError, None, ("machine_stats", broken), watch_args("x", 0.0)),
        ]
        for kind, label, expected, setup, replaced, args in cases:
            with self.subTest(kind=kind, way=label), _root.TcRoot() as root:
                lock = root.path / "mail" / "to-x" / LOCK_NAME.format(kind=kind)
                self.assertEqual(listen(root, kind, "x")[0], EXIT_TIMEOUT if kind == "wait" else 0)
                if setup == "send":
                    self.assertEqual(root.tc("send", "--from", "a", "--to", "x", "hi")[0], 0)
                tc = load_tc(root)
                with contextlib.ExitStack() as stack:
                    if setup == "hold":
                        held = stack.enter_context(open(lock, "rb"))
                        fcntl.flock(held, fcntl.LOCK_EX)
                    stack.enter_context(mock.patch.object(tc.resource, "setrlimit", lambda *a: None))
                    stack.enter_context(mock.patch.object(tc, "gpu_stats", lambda: None))
                    if replaced is not None:
                        stack.enter_context(mock.patch.object(tc, replaced[0], replaced[1]))
                    seen = stack.enter_context(warnings.catch_warnings(record=True))
                    warnings.simplefilter("always", ResourceWarning)
                    command = tc.cmd_wait if kind == "wait" else tc.cmd_watch
                    try:
                        code = run_in_process(lambda: command(args))[0]
                    except RuntimeError:
                        code = RuntimeError
                    gc.collect()
                    leaks = [str(w.message) for w in seen if issubclass(w.category, ResourceWarning)]
                    open_on_lock = lock_fds(lock) - (1 if setup == "hold" else 0)
                self.assertEqual(code, expected)
                self.assertEqual(open_on_lock, 0, f"tc {kind} left its lock open after {label}")
                self.assertEqual(leaks, [], f"tc {kind} left a file for the garbage collector after {label}")


class WakeFilesAreTheirOwnersTest(UmaskTestCase):
    """Item 6 of round 1b, a2's class proof for the wake files (test-strategist REC-2, the parallel to InboxPinnedTest): no member who is not a name's owner holds or redirects that name's wait lock, watch lock, inbox lock or ring marker.

    Every subtest runs on a shared mailbox (tc init with the running
    user's primary group, ann joined by the running user). The member is
    a one-shot child (MEMBER_SCRIPT) that acts before the owner's command
    and again while it runs; its process, and every file it plants, read
    as another member's (members_patched: HOLDER_UID_STEP up), never as
    the init user's, whom ROOT and .shared read as (one up, as_member).
    The owner's command runs in process, so the patches reach it.

    Per file, expected by value (the comments in the test say what the
    contract allows): the wait and watch locks, the owner's command holds
    its own lock and runs to its end, the member's open fails, and
    listeners() names the owner's pid and never the member's; the inbox
    lock, which every member may hold for a send (C4), the owner's
    command exits 10 within the bound, writes nothing, and names the
    holder's user and pid; the ring marker, which every member may write
    (C4), rewritten to clear, or to timed out and touched each time tc
    reads it, never stops a send after the sender's own backoff from
    ringing (the fake codex asserted called). Each file's mutation is
    recorded with the lines it turned red in handoffs/P3FIX.md.

    Known gap: the list of wake files is hardcoded, as InboxPinnedTest's
    families are; a wake file added later is not covered until someone
    adds its subtest. P3 fix round 2 (Claude Opus 5.5, unreviewed): and
    two of the owner's own waits over one plant never both hold a lock
    (the audit's LOW-1), at three moments.

    @interacts  see the module block.
    @deps       _root.TcRoot, UmaskTestCase, primary_group, load_tc,
                member, identity, members_patched, run_in_process, login,
                contents from test_shared.py.
    @complexity O(f) subtests over f = 5 (four files, the marker twice),
                plus eight for the planted entries and three for the
                owner's two waits.
    @alloc      one TcRoot per subtest.
    """

    def shared_with_ann(self, root, codex=False):
        """Share the root with the running user's primary group and join ann as the running user (as codex when `codex`).

        @interacts  two tc runs.
        @deps       primary_group; _root.TcRoot.tc; OWNER, THREAD.
        @complexity O(1).
        @alloc      the mailbox's folders and ann's card and inbox.
        """
        _, group, _ = primary_group()
        self.assertEqual(root.tc("init", "--shared", "--group", group)[0], 0)
        owner_env = {"CODEX_THREAD_ID": THREAD, "CLAUDECODE": None} if codex else {"CLAUDECODE": "1"}
        self.assertEqual(root.tc("join", OWNER, env=owner_env)[0], 0)

    def listener_case(self, root, kind):
        """The wait or watch lock (`kind`): the member plants and holds a file at the owner's lock name, and holds the lock's old place in mail/, before the owner's command; at its first poll, tries again to hold the lock at the name. What was seen.

        @interacts  three member children; one owner's command in
                    process (cmd_wait or cmd_watch) with tc's unread or
                    machine_stats wrapped to look at its first poll,
                    resource.setrlimit made a no-op and tc's gpu_stats
                    replaced.
        @deps       member, identity, members_patched, run_in_process,
                    load_tc, _root.flock_holders; unittest.mock.
        @complexity O(1): one CLASS_LISTEN_SECONDS run.
        @alloc      one module.
        """
        mail = root.path / "mail"
        lock = mail / f"to-{OWNER}" / LOCK_NAME.format(kind=kind)
        old = mail / OLD_LOCK_NAME.format(kind=kind, name=OWNER)
        planter, planted_said = member(root, lock, "hold")
        old_holder, old_said = member(root, old, "hold")
        planted, pids = {identity(lock)}, {planter.pid, old_holder.pid}
        tc = load_tc(root)
        seen = {}
        polled = tc.unread if kind == "wait" else tc.machine_stats

        def first_poll(*args, **kwargs):
            if not seen:
                seen["holders"] = _root.flock_holders(lock)
                trier, seen["while"] = member(root, lock, "hold")
                pids.add(trier.pid)
                seen["listeners"] = tc.listeners(kind)
            return polled(*args, **kwargs)
        call = ((lambda: tc.cmd_wait(wait_args(OWNER, CLASS_LISTEN_SECONDS))) if kind == "wait" else
                (lambda: tc.cmd_watch(argparse.Namespace(**{**vars(watch_args(OWNER, CLASS_LISTEN_SECONDS)),
                                                            "poll": CLASS_WATCH_POLL_SECONDS}))))
        with members_patched(root.path, planted, pids), \
                mock.patch.object(tc.resource, "setrlimit", lambda *args: None), \
                mock.patch.object(tc, "gpu_stats", lambda: None), \
                mock.patch.object(tc, "unread" if kind == "wait" else "machine_stats", first_poll):
            ran = run_in_process(call)
        return {"ran": ran, "seen": seen, "before": (planted_said, old_said), "member": (planter.pid, old_holder.pid),
                "lock": lock}

    def inbox_case(self, root):
        """The inbox lock: the member holds ann's inbox lock before her tc read and through it. What was seen.

        @interacts  one send; one member child; the root read before and
                    after; tc read in process.
        @deps       member, members_patched, run_in_process, load_tc,
                    contents; time.
        @complexity O(1): one LOCK_WAIT_SECONDS of waiting.
        @alloc      one module.
        """
        self.assertEqual(root.tc("send", "--from", "ben", "--to", OWNER, "hi")[0], 0)
        holder, said = member(root, root.path / "mail" / f".box-{OWNER}.lock", "hold")
        before = contents(root.path)
        tc = load_tc(root)
        began = time.monotonic()
        with members_patched(root.path, set(), {holder.pid}):
            ran = run_in_process(lambda: tc.cmd_read(argparse.Namespace(name=OWNER)))
        took = time.monotonic() - began
        return {"ran": ran, "said": said, "pid": holder.pid, "took": took, "changed": contents(root.path) != before}

    def marker_case(self, root, state):
        """The ring marker: a ring fails (owed), then the member rewrites the marker to `state` before ben's next send and again each time that send reads it, a timed-out one touched to the send's own clock each time; the send runs with the clock RING_BACKOFF_SECONDS and more past ben's last ring. What was seen.

        @interacts  a fake codex (a failure, then a success); one send as
                    setup; member children; cmd_send in process with
                    wall_clock replaced, PATH set to the root's, and tc's
                    read_regular_file wrapped to call the member first.
        @deps       member, members_patched, run_in_process, load_tc;
                    _root.TcRoot.fake_bin; time, unittest.mock.
        @complexity O(1): two codex fake runs.
        @alloc      one module.
        """
        folder, calls = root.fake_bin("codex", [1, 0])
        self.assertEqual(root.tc("send", "--from", "ben", "--to", OWNER, "one")[0], 0)
        marker = root.path / "mail" / MARKER_NAME.format(name=OWNER)
        state_after_setup = marker.read_text().partition("\n")[0]
        tc = load_tc(root)
        offset = RING_BACKOFF_SECONDS + PAST_BACKOFF_SECONDS
        pids, rewrites = set(), []

        def rewrite():
            stamp = "-" if state == CLEAR_STATE else str(time.time() + offset)
            proc, said = member(root, marker, f"rewrite:{state}:{stamp}")
            pids.add(proc.pid)
            rewrites.append(said)
        rewrite()
        real_read = tc.read_regular_file

        def read_regular_file(path, *args, **kwargs):
            if pathlib.Path(path) == marker:
                rewrite()
            return real_read(path, *args, **kwargs)
        with members_patched(root.path, set(), pids), \
                mock.patch.dict(os.environ, {"PATH": root.env["PATH"]}), \
                mock.patch.object(tc, "wall_clock", lambda: time.time() + offset), \
                mock.patch.object(tc, "read_regular_file", read_regular_file):
            ran = run_in_process(lambda: tc.cmd_send(argparse.Namespace(sender="ben", to=OWNER, message="two",
                                                                        origin=None)))
        record = folder.parent / "calls.jsonl"
        return {"ran": ran, "setup": state_after_setup, "rewrites": rewrites,
                "calls": calls() if record.exists() else None}

    def test_no_member_holds_or_redirects_another_members_wake_file(self):
        """For each wake file, a member who is not ann tries to hold or rewrite it before and while ann's command runs (or a send to ann, for the marker): ann's listener holds its own lock and health names ann's pid, never the member's; her read on a held inbox lock fails within the bound, writes nothing, and names the member; and a send after the sender's own backoff rings her Codex thread whatever the member wrote.

        D35's wake-file class proof (the audit's HIGH-2, MEDIUM-1; REC-2,
        REC-3, REC-4). Must reject a wait or watch lock the group can open
        (the member's open succeeds, or its plant is taken as the lock),
        busy words that do not name the holder, and a ring decision that
        trusts the marker's words or its time.

        @interacts  per subtest: a shared mailbox with ann joined, then
                    listener_case, inbox_case or marker_case.
        @deps       shared_with_ann, listener_case, inbox_case,
                    marker_case, login; os.
        @complexity O(f): f = 5 subtests.
        @alloc      one TcRoot per subtest.
        """
        mine, other, init = login(os.geteuid()), login(os.geteuid() + HOLDER_UID_STEP), login(os.geteuid() + 1)
        for kind in KINDS:
            with self.subTest(wake_file=f"the {kind} lock"), _root.TcRoot() as root:
                self.shared_with_ann(root)
                got = self.listener_case(root, kind)
                code, out, err = got["ran"]
                # Allowed: nothing less. D35, "Each member's listener is theirs alone".
                self.assertEqual(got["before"], (MEMBER_HELD, MEMBER_HELD), "the member could not plant and hold")
                self.assertEqual(code, EXIT_TIMEOUT if kind == "wait" else 0,
                                 f"ann's tc {kind} did not hold its own lock and run to its end: {out}{err}")
                self.assertIn(os.getpid(), got["seen"]["holders"], f"ann's tc {kind} did not hold the lock at its name")
                self.assertEqual(got["seen"]["while"], MEMBER_DENIED,
                                 f"the member's open of ann's {kind} lock did not fail")
                self.assertEqual(got["seen"]["listeners"].get(OWNER), os.getpid(),
                                 f"listeners() did not name ann's own tc {kind}")
                self.assertFalse(set(got["member"]) & set(got["seen"]["listeners"].values()),
                                 "listeners() named the member's pid")
                self.assertIn(f"was a file owned by {other}, not this user's own {kind} lock", err)
        with self.subTest(wake_file="the inbox lock"), _root.TcRoot() as root:
            self.shared_with_ann(root)
            got = self.inbox_case(root)
            # Allowed by C4 (D20, D23): any member may hold it, for a send; the cost is a failed command.
            self.assertEqual(got["said"], MEMBER_HELD)
            self.assertEqual(got["ran"], (EXIT_BUSY, "", HELD_BY_WORDS.format(
                what=OWNER, user=other, pid=got["pid"], init=ASK_INIT_WORDS.format(init=init))))
            self.assertLessEqual(got["took"], LOCK_WAIT_SECONDS + LOCK_REFUSE_MARGIN_SECONDS)
            self.assertFalse(got["changed"], "a refused read changed the mailbox")
        for state in (CLEAR_STATE, TIMED_OUT_STATE):
            with self.subTest(wake_file=f"the ring marker, rewritten to {state}"), _root.TcRoot() as root:
                self.shared_with_ann(root, codex=True)
                got = self.marker_case(root, state)
                code, out, err = got["ran"]
                # Allowed by C4: a ring once more or once fewer, never the doorbell for good (C2 item 5).
                self.assertEqual(got["setup"], "failed", "the setup's ring did not fail, so no ring was owed")
                self.assertTrue(got["rewrites"] and set(got["rewrites"]) == {MEMBER_REWROTE}, got["rewrites"])
                self.assertIsNotNone(got["calls"], "the fake codex never ran, not even in setup")
                self.assertEqual(len(got["calls"]), 2,
                                 f"a send past the sender's own backoff did not ring over a marker rewritten to "
                                 f"{state}: {got['calls']}")
                self.assertEqual(code, 0, err)
                self.assertIn(RANG_LINE.format(to=OWNER), out)

    def test_a_file_planted_at_the_owners_lock_name_is_moved_aside_with_words_and_the_owners_lock_made(self):
        """Another member's file (held), a symlink to a file outside the mailbox, a FIFO, or a file with a second name, planted at ann's wait or watch lock's name: ann's command moves it aside to the first aside name with one line naming what it was and whose, makes her own lock at 0600, and runs to its end; the planted entry itself sits at the aside name, and the link's target is unchanged.

        Must reject a planted entry taken as the lock, followed, waited on
        or refused instead of moved (D35 (1): the owner's tc owns the
        inbox and moves it, with words).

        @interacts  per case: a shared mailbox with ann joined; the plant
                    made by a member child or by hand (a link, a FIFO, a
                    hard link to a file outside the root); one owner's
                    command in process with members_patched, resource
                    .setrlimit made a no-op and tc's gpu_stats replaced.
        @deps       shared_with_ann, member, identity, members_patched,
                    run_in_process, load_tc, login; os, stat.
        @complexity O(1) per case, eight cases.
        @alloc      one TcRoot and one module per case.
        """
        other = login(os.geteuid() + HOLDER_UID_STEP)
        for kind in KINDS:
            for plant in PLANTS:
                with self.subTest(kind=kind, planted=plant), _root.TcRoot() as root:
                    self.shared_with_ann(root)
                    lock = root.path / "mail" / f"to-{OWNER}" / LOCK_NAME.format(kind=kind)
                    target = root.base / "target"
                    target.write_text(TARGET_TEXT)
                    pids = set()
                    if plant == "a file":
                        planter, said = member(root, lock, "hold")
                        self.assertEqual(said, MEMBER_HELD)
                        pids.add(planter.pid)
                    elif plant == "a symlink":
                        lock.symlink_to(target)
                    elif plant == "a FIFO":
                        os.mkfifo(lock)
                    else:
                        os.link(target, lock)
                    found = identity(lock)
                    tc = load_tc(root)
                    call = ((lambda: tc.cmd_wait(wait_args(OWNER, 0.0))) if kind == "wait" else
                            (lambda: tc.cmd_watch(watch_args(OWNER, 0.0))))
                    with members_patched(root.path, {found}, pids), \
                            mock.patch.object(tc.resource, "setrlimit", lambda *args: None), \
                            mock.patch.object(tc, "gpu_stats", lambda: None):
                        code, out, err = run_in_process(call)
                    aside = lock.with_name(FIRST_ASIDE.format(lock=lock.name))
                    moved = identity(aside) if os.path.lexists(aside) else None
                    st = os.lstat(lock)
                    text = target.read_text()
                    self.assertEqual(code, EXIT_TIMEOUT if kind == "wait" else 0,
                                     f"ann's tc {kind} did not run to its end over {plant}: {out}{err}")
                    self.assertIn(MOVED_WORDS.format(kind=kind, path=lock, what=plant, owner=other, aside=aside), err)
                    self.assertEqual(moved, found, f"{plant} is not what sits at {aside}")
                    self.assertEqual((stat.S_ISREG(st.st_mode), stat.S_IMODE(st.st_mode), st.st_uid),
                                     (True, WAKE_LOCK_MODE, os.geteuid()), "ann's own lock was not made at its name")
                    self.assertEqual(text, TARGET_TEXT, "the planted link's target changed")

    # P3 fix round 2 (Claude Opus 5.5, unreviewed): the audit's LOW-1 (test-strategist REC-7).
    def owners_waits_case(self, root, moment):
        """Two of ann's own waits over one plant a member holds at her wait lock's name: wait B (the outer call) is interrupted at `moment` while wait A (or, for the flock moment, a move by hand) runs whole. What was seen, as plain values.

        `moment`: OWN_LOCK_BEFORE_LOOK runs A just before B's move_aside
        looks at the name (B finds A's fresh lock there); OWN_LOCK_BEFORE_MOVE
        runs A after B's look and before B's rename (B judged the plant,
        then its rename takes A's lock); OWN_LOCK_BEFORE_FLOCK moves B's
        just-opened lock off its name before B's flock, as another of
        ann's waits caught in the second moment would.

        @interacts  one member child that plants and holds the lock, killed
                    by its own pid; loads tc and calls hold_wake_lock in
                    process with members_patched, and tc's move_aside,
                    name_taken or open_wake_lock wrapped; renames a lock by
                    hand for the flock moment; closes every lock it took.
        @deps       member, identity, members_patched, run_in_process,
                    load_tc; os, unittest.mock; OWNER, LOCK_NAME,
                    FIRST_ASIDE, SECOND_ASIDE, DISPLACED_SUFFIX.
        @complexity O(1).
        @alloc      one module and up to three open lock files, closed
                    before return.
        """
        lock = root.path / "mail" / f"to-{OWNER}" / LOCK_NAME.format(kind="wait")
        planter, said = member(root, lock, "hold")
        found = identity(lock)
        tc = load_tc(root)
        first, second, armed = [], [], [True]
        targets = {OWN_LOCK_BEFORE_LOOK: "move_aside", OWN_LOCK_BEFORE_MOVE: "name_taken",
                   OWN_LOCK_BEFORE_FLOCK: "open_wake_lock"}
        real = getattr(tc, targets[moment])
        try:
            with members_patched(root.path, {found}, {planter.pid}):
                share = tc.mailbox_share()

                def interrupted(*args, **kwargs):
                    if not armed[0] or moment == OWN_LOCK_BEFORE_FLOCK:
                        result = real(*args, **kwargs)
                        if armed[0]:  # the flock moment: B's lock leaves its name before B's flock
                            armed[0] = False
                            os.rename(lock, lock.with_name(lock.name + DISPLACED_SUFFIX))
                        return result
                    armed[0] = False
                    first.append(tc.hold_wake_lock(OWNER, "wait", share))
                    return real(*args, **kwargs)
                with mock.patch.object(tc, targets[moment], interrupted):
                    ran = run_in_process(lambda: second.append(tc.hold_wake_lock(OWNER, "wait", share)))
            at_name = os.lstat(lock) if os.path.lexists(lock) else None
            held = [os.fstat(f.fileno()) for f in first + second]
            return {"said": said, "ran": ran, "first": len(first), "second": len(second),
                    "held_at_name": [at_name is not None and os.path.samestat(st, at_name) for st in held],
                    "plant_aside": identity(lock.with_name(FIRST_ASIDE.format(lock=lock.name)))
                    if os.path.lexists(lock.with_name(FIRST_ASIDE.format(lock=lock.name))) else None,
                    "found": found,
                    "second_aside": os.path.lexists(lock.with_name(SECOND_ASIDE.format(lock=lock.name)))}
        finally:
            for f in first + second:
                f.close()

    def test_two_of_the_owners_own_waits_over_one_plant_never_both_hold_a_lock(self):
        """Shared, ann joined, a member holding a plant at ann's wait lock's name: two of ann's own waits started together never both hold a lock, whichever moment the second is interrupted at. Before its look or between its look and its move, the second finds the first's lock, exits 3 with ALREADY_WORDS, and the first holds the lock at the name; the plant sits at the first aside name and nothing at the second. A lock moved off its name before the second's flock makes the second take the lock that has the name.

        The audit's LOW-1 (bugs-reviewer): both waits judged the plant;
        the first moved it and made its lock; the second's rename then
        moved that fresh lock aside, over the plant, and made another, so
        each flocked its own file and two listeners ran for one name.
        Must reject a move_aside that moves this user's own lock, a
        rename it never checks, and a flock kept on a file its name no
        longer leads to.

        @interacts  per moment: a shared mailbox with ann joined, then
                    owners_waits_case.
        @deps       shared_with_ann, owners_waits_case; os; ALREADY_WORDS,
                    EXIT_ALREADY, MEMBER_HELD.
        @complexity O(1): three cases.
        @alloc      one TcRoot per case.
        """
        for moment in (OWN_LOCK_BEFORE_LOOK, OWN_LOCK_BEFORE_MOVE, OWN_LOCK_BEFORE_FLOCK):
            with self.subTest(second_wait_interrupted=moment), _root.TcRoot() as root:
                self.shared_with_ann(root)
                got = self.owners_waits_case(root, moment)
                code, out, err = got["ran"]
                self.assertEqual(got["said"], MEMBER_HELD, "the member could not plant and hold the lock")
                if moment == OWN_LOCK_BEFORE_FLOCK:
                    self.assertEqual((code, got["second"]), (0, 1), f"the wait did not run: {out}{err}")
                    self.assertEqual(got["held_at_name"], [True],
                                     "the wait holds a lock its name no longer leads to")
                else:
                    self.assertEqual((code, out), (EXIT_ALREADY, ALREADY_WORDS["wait"].format(name=OWNER)),
                                     f"a second of ann's own waits started: {err}")
                    self.assertEqual((got["first"], got["second"]), (1, 0))
                    self.assertEqual(got["held_at_name"], [True], "the first wait's lock lost its name")
                    self.assertFalse(got["second_aside"], "a lock of ann's own was moved aside")
                self.assertEqual(got["plant_aside"], got["found"], "the plant is not at the first aside name")


if __name__ == "__main__":
    unittest.main()
