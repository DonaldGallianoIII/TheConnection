"""
Tests for the wait exit record (F1; contract C5's "The wait exit record",
D28, D37 part 2): `tc wait <name>` keeps one line beside its lock,
mail/to-<name>/.wait.exit, `listening` once it holds the lock and `mail`
or `timeout` as it exits 0 or 2, replaced whole and never followed; one
reader takes it only from the inbox owner's one-line regular file; and
the record is never proof of life. F1 fix round 1 (Claude Opus 5.5,
unreviewed): a plant at the record's names is moved aside with words; a
down node carries how long ago it stopped; and a session that re-arms
between a lock listing and the record read is never read as killed. F1
fix round 2 (Claude Opus 5.5, unreviewed): an earlier write's leftover
.tmp is removed, a plant of its form moved aside once; and a down the
window rules gave carries its age too.

Model:  Claude Opus 5.5 (the F1 lane agent), 2026-10-16
Status: unreviewed

One Linux user plays every part. Where the record must be another
user's, tc runs in process and os.fstat reports it as another user's
(test_shared.owner_patched_fstat), as the SHARED suites report owners.
Each mutation that turns a test red, and the line it turns red, is in
docs/planning/connection-routes/handoffs/F1.md.

@interacts  runs ../tc through tests/_root.py under a throwaway TC_ROOT
            (wait, send); starts proven listeners and kills one by its
            own pid (os.kill), reading /proc/locks until its lock goes;
            makes inboxes, records, links, FIFOs and hard links by hand in
            the root's temp folder; loads tc as a module (TC_ROOT set for
            the load and put back, test_shared.load_tc) and calls
            wait_exits and left_on_purpose in process, with os.fstat
            patched for one case and one call run in a thread that a
            FIFO could block (released by opening the FIFO for writing).
            Starts tc watch children through the harness (killed by
            their pids in teardown) and reads /proc/locks to prove each
            holds its lock. Runs tc health and the gate's health in
            process with tc's wall_clock and gpu_stats replaced and
            SSH_ORIGINAL_COMMAND set. Loads board/serve.py and runs
            Board.feed() on a clock the test sets, over listeners it
            kills by their pids; writes one record by hand (a .tmp
            renamed over it) and moves one aside. F1 fix round 1 (Claude
            Opus 5.5, unreviewed): lists an inbox for a write's own .tmp;
            writes records dated minutes or an hour back by hand and
            reads each down node's down_age_s; runs cmd_watch in process
            (resource.setrlimit made a no-op, gpu_stats replaced) and
            Board.feed(), each with tc's listeners replaced so one listing
            misses a held lock. F1 fix round 2 (Claude Opus 5.5,
            unreviewed): makes files and a link at an earlier write's
            .tmp names by hand and runs two waits over them; renames a
            killed listener's record aside, or replaces it with an old
            `mail`, and reads its down_age_s. Writes nothing outside the
            root's temp folder.
@deps       python3 stdlib (argparse, collections, contextlib, datetime,
            importlib, io, json, os, pathlib, pwd, signal, stat,
            subprocess, sys, threading, time, unittest, unittest.mock);
            tests/_root.py; UmaskTestCase, load_tc and owner_patched_fstat
            from test_shared.py; ../tc; ../board/serve.py.
@complexity O(1) per test: a handful of tc runs per root, one root per
            subtest; the killed-listener test reads /proc/locks until the
            lock goes, at most LOCK_GONE_SECONDS; each watch subtest runs
            up to its watch's heartbeat (about 8 to 14 s; the re-arm
            watch, REARM_HEARTBEAT_SECONDS).
@alloc      one TcRoot per subtest, removed when its context exits, with
            every child it started.
"""

import argparse
import collections
import contextlib
import datetime
import importlib.util
import io
import json
import os
import pathlib
import pwd
import signal
import stat
import subprocess
import sys
import threading
import time
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
# Run as `python3 -m unittest tests.test_wait_exit` from the repo root,
# tests/ is not on sys.path; under discover it is. Add it once so both work.
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import _root  # noqa: E402  (needs the path line above)
from test_shared import UmaskTestCase, load_tc, owner_patched_fstat  # noqa: E402

# The listener's name and a sender's, made up.
NAME = "b"
SENDER = "a"
# The record's name, its old fixed .tmp's, its mode and its three words
# (tc's WAIT_EXIT_NAME, WAIT_EXIT_OLD_TMP_NAME since F1 fix round 1,
# WAIT_EXIT_MODE, WAIT_EXIT_WORDS),
# written here rather than read from tc, so a changed constant fails a test.
RECORD = ".wait.exit"
RECORD_TMP = ".wait.exit.tmp"
RECORD_MODE = 0o640
# F1 fix round 1 (Claude Opus 5.5, unreviewed): the audit's MEDIUM-1.
# RECORD_TMP is now only the old fixed .tmp name; each write's own .tmp
# starts with this (tc's WAIT_EXIT_TMP_NAME before its nonce). A plant at
# the record's name or the old .tmp name is moved to the first aside name
# (tc's PLANTED_ASIDE_NAME), with these words.
RECORD_TMP_PREFIX = ".wait.exit.tmp-"
# F1 fix round 2 (Claude Opus 5.5, unreviewed): bugs LOW-1. Two
# names of a write's own .tmp form, the prefix and 16 lowercase hex digits
# (tc's WAIT_EXIT_TMP_NONCE_BYTES, 8, two digits a byte), as a wait killed
# between a record's create and its rename leaves; and a name one digit
# short, which is not of that form and is never tc's to touch.
LEFTOVERS = (RECORD_TMP_PREFIX + "0" * 16, RECORD_TMP_PREFIX + "0123456789abcdef")
NOT_OF_THE_FORM = RECORD_TMP_PREFIX + "0" * 15
FIRST_ASIDE = "{name}.planted-1"
MOVED_RECORD_WORDS = ("tc wait: {path} was {what} owned by {owner}, not this user's own exit record; moved it "
                      "aside to {aside}")
LISTENING, MAIL, TIMEOUT = "listening", "mail", "timeout"
# The most of a record the reader takes (tc's WAIT_EXIT_MAX_BYTES).
RECORD_MAX_BYTES = 64
# How far before a lock's last sighting a mail or timeout record may be
# dated and still be that wait's own exit (tc's
# WAIT_EXIT_TIME_STEP_SECONDS).
RECORD_TIME_STEP_SECONDS = 2
# Exit codes (contracts.md): a wait's mail and its timeout.
EXIT_MAIL = 0
EXIT_TIMEOUT = 2
# A wait that ends at once, and a listener's timeout long enough that it
# never ends on its own during a test (the harness kills it).
AT_ONCE = "0"
LISTENER_SECONDS = 30
# tc wait's poll (tc's POLL_SECONDS); a wait with mail waiting finds it at
# its first poll, so this is far past what a woken wait needs.
TC_POLL_SECONDS = 5
WAKE_CEILING_SECONDS = 2 * TC_POLL_SECONDS
# How far the record's time may stray from the test's clock: it is cut to
# the second, and a tc run takes well under one.
TIME_SLACK_SECONDS = 5
# How long a killed listener's lock may take to go from /proc/locks, and
# the gap between two looks.
LOCK_GONE_SECONDS = 5
LOCK_POLL_SECONDS = 0.05
# How long a read that a FIFO could block may run before it counts as
# blocked.
FIFO_CEILING_SECONDS = 5
# A record line the reader takes, with its time as seconds since the
# epoch, worked out by hand: 12:00 at -05:00 is 17:00 UTC.
GOOD_LINE = "mail 2026-10-16T12:00:00-05:00\n"
GOOD_AT = datetime.datetime(2026, 10, 16, 17, 0, tzinfo=datetime.timezone.utc).timestamp()
# A line the reader would take but for its length: a time with sixty
# fractional digits, which datetime.fromisoformat reads, past
# RECORD_MAX_BYTES in all.
LONG_FRACTION_DIGITS = 60
LONG_LINE = f"mail 2026-10-16T12:00:00.{'0' * LONG_FRACTION_DIGITS}-05:00\n"
# Lines the reader refuses for their form alone, each under
# RECORD_MAX_BYTES so the bound is never why: an unknown word, a second
# line, no newline at its end, and a time with no offset.
MALFORMED = (("an unknown word", "dead 2026-10-16T12:00:00-05:00\n"),
             ("two lines", "mail 2026-10-16T12:00:00-05:00\nmail\n"),
             ("no newline", "mail 2026-10-16T12:00:00-05:00"),
             ("a time with no offset", "mail 2026-10-16T12:00:00\n"))
# Item 3, tc watch --names: the session the watch wakes, made up; its lock
# (tc's WAKE_LOCK_NAME for a watch) and the wait's; a watch's alert exit
# (contracts.md); thresholds no real machine reaches, so a watch only ever
# alerts for a listener; a poll a second; a heartbeat past a woken wait's
# exit (at most TC_POLL_SECONDS after the send) with a few of the watch's
# polls to spare; and how long a killed listener's alert may take.
WATCHER = "w"
WATCH_LOCK = ".watch.lock"
WAIT_LOCK = ".wait.lock"
EXIT_ALERT = 5
QUIET = ["--load-ratio", "100000", "--mem-min-pct", "0", "--gpu-max-c", "100000"]
WATCH_POLL = "1"
SPARE_POLLS_SECONDS = 4
WATCH_HEARTBEAT_SECONDS = WAKE_CEILING_SECONDS + SPARE_POLLS_SECONDS
ALERT_CEILING_SECONDS = 10
# A listener that times out on its own, soon, but long after the watch
# has taken its first look (a watch lists the locks the moment it holds
# its own), and the heartbeat of the watch over it.
SHORT_WAIT_SECONDS = 4
SHORT_HEARTBEAT_SECONDS = SHORT_WAIT_SECONDS + SPARE_POLLS_SECONDS
# Item 4, tc health: the stopped names and the record each holds (none for
# the last), a live listener's name, how long after GOOD_AT the replaced
# clock reads (two minutes, which health words as 2m), the key health's
# JSON carries them under, and the far key's command and name for the
# gate's health (made up; the gate ignores the path).
STOPPED = (("sb", "timeout 2026-10-16T12:00:00-05:00\n"), ("sc", GOOD_LINE),
           ("sd", "listening 2026-10-16T12:00:00-05:00\n"), ("se", None))
LIVE = "sf"
LATER_SECONDS = 120
LATER_WORDS = "2m ago"
EXITS_KEY = "wait_exits"
GATE_HEALTH = "/x/tc health --json"
GATE_KEY = "farkey"
# Item 5, the board (C5): five listeners, each gone one way, made-up
# names: woken by mail, killed by its pid, timed out on its own, killed
# with its record then moved aside (no record: today's rules), and killed
# after its record was put back to a `mail` an hour old (a stale record,
# from a wait before the one the board saw). Where a record is moved
# aside to; the stale record's age; the board's down window (serve.py's
# DOWN_WINDOW_S, written here); and the five names' states while all
# listen.
WOKEN, KILLED, TIMED, BARE, STALE = "woken", "killed", "timed", "bare", "stale"
FIVE = (WOKEN, KILLED, TIMED, BARE, STALE)
RECORD_ASIDE = ".wait.exit.aside"
STALE_AGE_SECONDS = 3600
DOWN_WINDOW_S = 600
ALL_LISTENING = dict.fromkeys(FIVE, "listening")
SERVE_PATH = HERE.parent / "board" / "serve.py"
# F1 fix round 1 (Claude Opus 5.5, unreviewed): the audit's LOW-1, a2's
# ruling (C5, "The pill warns only on a fresh stop"). Made-up names for a
# stop 9 minutes old, one 11 minutes old (either side of DOWN_WINDOW_S)
# and a wait that left on purpose; a long wait's age when it is killed
# (an hour: under DEFAULT_WAIT_SECONDS, 110 min); and how long after the
# board last saw it listening the next feed runs.
NINE, ELEVEN, LEFT = "nine", "eleven", "left"
NINE_MIN_S = 9 * 60
ELEVEN_MIN_S = 11 * 60
LONG_WAIT_S = 3600
STOP_SEEN_S = 5
# What a node without the down_age_s key reads as, so a feed that lacks it
# fails on the test's assertion, never on a KeyError.
MISSING = "no down_age_s key"
# F1 fix round 1 (Claude Opus 5.5, unreviewed): the audit's LOW-2 and
# LOW-3. An in-process watch's heartbeat and poll (a few polls, the first
# fed the stale listing), and thresholds no real machine reaches.
REARM_HEARTBEAT_SECONDS = 1.0
REARM_POLL_SECONDS = 0.2
QUIET_ARGS = {"load_ratio": 100000.0, "mem_min_pct": 0.0, "gpu_max_c": 100000.0}
# Which call of tc's listeners each reader makes first after the session
# re-arms: a watch lists once at its start and once per poll, so its first
# poll's is the second; a feed's snapshot lists first.
WATCH_FIRST_POLL_LISTING = 2
BOARD_FIRST_LISTING = 1
# What a file outside the mailbox holds, that a link at a record's name
# (or its .tmp's) leads to.
OUTSIDE_TEXT = "outside the mailbox: tc must never write or read this\n"
# What one look at a record finds (seen_record): its first word, what is
# at its name (file, link, other or None), its mode and owner, whether a
# .tmp is left beside it, whether it is one newline-ended line, and
# whether its time is a real one within TIME_SLACK_SECONDS of the test's
# clock.
Seen = collections.namedtuple("Seen", "word kind mode uid tmp_left one_line fresh")


def seen_record(box, now):
    """What sits at the record's name in the inbox `box`, as a Seen; never raises (each field None for what is not there), so a test fails on its assertion, never here.

    @interacts  lstats the record and the old .tmp's name, and lists the
                inbox for any write's own .tmp (F1 fix round 1); reads the
                record when it is a regular file.
    @deps       datetime, os, stat; RECORD, RECORD_TMP, RECORD_TMP_PREFIX,
                TIME_SLACK_SECONDS.
    @complexity O(e) over e names in the inbox (a handful); one short file.
    @alloc      one Seen and the inbox's name list, freed on return.
    """
    path = box / RECORD
    try:
        own_tmp = any(entry.startswith(RECORD_TMP_PREFIX) for entry in os.listdir(box))
    except OSError:
        own_tmp = False
    tmp_left = os.path.lexists(box / RECORD_TMP) or own_tmp
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return Seen(None, None, None, None, tmp_left, None, None)
    kind = "file" if stat.S_ISREG(st.st_mode) else "link" if stat.S_ISLNK(st.st_mode) else "other"
    word = one_line = fresh = None
    if kind == "file":
        line, newline, rest = path.read_text(encoding="utf-8").partition("\n")
        word, _, when = line.partition(" ")
        one_line = bool(newline) and not rest
        try:
            at = datetime.datetime.fromisoformat(when)
            fresh = at.tzinfo is not None and abs(at.timestamp() - now) <= TIME_SLACK_SECONDS
        except ValueError:
            fresh = False
    return Seen(word, kind, stat.S_IMODE(st.st_mode), st.st_uid, tmp_left, one_line, fresh)


# F1 finish (Claude Opus 5.5, unreviewed): a planted .tmp that tc removed made
# the assertion's own lstat raise, an error, not a red assertion.
def mode_at(path):
    """The full st_mode of whatever is at `path`, not followed, or None when nothing is there; never raises, so a test fails on its assertion, never here.

    @interacts  lstats one path.
    @deps       os.
    @complexity O(1).
    @alloc      none.
    """
    try:
        return os.lstat(path).st_mode
    except OSError:
        return None


def written(word):
    """The Seen a record `word` written by this user's tc just now gives.

    @interacts  reads this process's effective user id.
    @deps       os; Seen, RECORD_MODE.
    @complexity O(1).
    @alloc      one Seen, returned.
    """
    return Seen(word, "file", RECORD_MODE, os.geteuid(), False, True, True)


def record_made(box):
    """True once something has the record's name in the inbox `box`, within LOCK_GONE_SECONDS. A listener proven by its lock writes its record just after it takes the lock, so a test looks for it before reading it or killing the listener.

    @interacts  lstats one name until it is there.
    @deps       os, time; RECORD, LOCK_GONE_SECONDS, LOCK_POLL_SECONDS.
    @complexity at most LOCK_GONE_SECONDS / LOCK_POLL_SECONDS lstats.
    @alloc      none.
    """
    end = time.monotonic() + LOCK_GONE_SECONDS
    while time.monotonic() < end:
        if os.path.lexists(box / RECORD):
            return True
        time.sleep(LOCK_POLL_SECONDS)
    return os.path.lexists(box / RECORD)


def lock_gone(lock, pid, ceiling=LOCK_GONE_SECONDS):
    """True once /proc/locks no longer shows `pid` holding `lock`, within `ceiling` seconds.

    @interacts  reads /proc/locks (the harness's flock_holders).
    @deps       _root.flock_holders; time; LOCK_GONE_SECONDS,
                LOCK_POLL_SECONDS.
    @complexity at most ceiling / LOCK_POLL_SECONDS reads.
    @alloc      none past each read.
    """
    end = time.monotonic() + ceiling
    while time.monotonic() < end:
        if pid not in _root.flock_holders(lock):
            return True
        time.sleep(LOCK_POLL_SECONDS)
    return pid not in _root.flock_holders(lock)


def holds(lock, proc):
    """True once /proc/locks shows `proc` holding `lock`, within LOCK_GONE_SECONDS; False if it exits or the time runs out first.

    @interacts  reads /proc/locks (the harness's flock_holders).
    @deps       _root.flock_holders; time; LOCK_GONE_SECONDS,
                LOCK_POLL_SECONDS.
    @complexity at most LOCK_GONE_SECONDS / LOCK_POLL_SECONDS reads.
    @alloc      none past each read.
    """
    end = time.monotonic() + LOCK_GONE_SECONDS
    while time.monotonic() < end:
        if proc.pid in _root.flock_holders(lock):
            return True
        if proc.poll() is not None:
            return False
        time.sleep(LOCK_POLL_SECONDS)
    return False


def run_in_process(call):
    """Run `call` with stdout and stderr captured: (code, out, err). A SystemExit gives its code, a return 0, and any other exception its words, so a test fails on its assertion, never in here.

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
        except Exception as error:  # the run's result in words, read by the assertion
            code = f"raised {type(error).__name__}: {error}"
    return code, out.getvalue(), err.getvalue()


def stop_names(root):
    """Each of STOPPED made by hand under `root`: its inbox, a lock nobody holds (so health lists it stopped), and its record when it has one.

    @interacts  makes folders and files under the root.
    @deps       pathlib; STOPPED, WAIT_LOCK, RECORD.
    @complexity O(1): four names.
    @alloc      the files, removed with the root.
    """
    for name, line in STOPPED:
        box = root.path / "mail" / f"to-{name}"
        box.mkdir(parents=True)
        (box / WAIT_LOCK).touch()
        if line is not None:
            (box / RECORD).write_text(line)


def finish(proc, ceiling):
    """(exit code, stdout, stderr) of `proc` once it ends, within `ceiling` seconds. Past it the child is killed by its own pid and the code is None, so a test fails on its assertion, never on a timeout.

    @interacts  waits for one child; may send it SIGKILL (Popen.kill, its
                own pid only).
    @deps       subprocess.
    @complexity O(1), plus at most `ceiling` seconds.
    @alloc      the child's output, returned.
    """
    try:
        out, err = proc.communicate(timeout=ceiling)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
        return None, out, err
    return proc.returncode, out, err


def start_watch(root, heartbeat):
    """Start `tc watch w --names b` under `root` with QUIET thresholds, a poll a second and `heartbeat`; return (its Popen, whether it held its lock and b still held its own once it did).

    The second part is how a test knows the watch took its first look
    while b listened: the watch lists the locks the moment it holds its
    own, and b's lock is checked after that.

    @interacts  starts one tc watch through the harness (killed by its
                pid in teardown); reads /proc/locks.
    @deps       _root.TcRoot.start, _root.flock_holders, holds; WATCHER,
                NAME, WATCH_POLL, QUIET, WATCH_LOCK, WAIT_LOCK.
    @complexity O(1), plus holds'.
    @alloc      one Popen, registered with the root.
    """
    watch = root.start("watch", WATCHER, "--names", NAME, "--heartbeat", str(heartbeat), "--poll", WATCH_POLL, *QUIET)
    held = holds(root.path / "mail" / f"to-{WATCHER}" / WATCH_LOCK, watch)
    listening = bool(_root.flock_holders(root.path / "mail" / f"to-{NAME}" / WAIT_LOCK))
    return watch, held and listening


def release_fifo(path):
    """Open the FIFO at `path` for writing without blocking, then close it, so a reader stuck opening it goes on; nothing happens when no reader waits.

    @interacts  opens and closes one FIFO.
    @deps       os.
    @complexity O(1).
    @alloc      none.
    """
    try:
        fd = os.open(path, os.O_WRONLY | os.O_NONBLOCK)
    except OSError:
        return
    os.close(fd)


def in_thread(call, fifo):
    """Run `call` in a thread for at most FIFO_CEILING_SECONDS: (whether it was still running then, what it returned or None). A thread still running is released (release_fifo on `fifo`) and joined before this returns.

    @interacts  starts one thread; may open the FIFO at `fifo`.
    @deps       threading; release_fifo, FIFO_CEILING_SECONDS.
    @complexity O(1), plus the call, at most FIFO_CEILING_SECONDS twice.
    @alloc      one thread and one dict, freed on return.
    """
    got = {}
    worker = threading.Thread(target=lambda: got.setdefault("value", call()), daemon=True)
    worker.start()
    worker.join(FIFO_CEILING_SECONDS)
    blocked = worker.is_alive()
    if blocked:
        release_fifo(fifo)
        worker.join(FIFO_CEILING_SECONDS)
    return blocked, got.get("value")


class WriterTest(UmaskTestCase):
    """Item 1: tc wait writes the record, replaced whole, never followed, and a failure never touches its exit.

    @interacts  see the module block.
    @deps       _root.TcRoot, UmaskTestCase, seen_record, written,
                mode_at, lock_gone.
    @complexity O(1) per subtest.
    @alloc      one TcRoot per subtest.
    """

    def test_a_wait_writes_listening_then_mail_or_timeout_at_0640_its_owners_with_no_tmp_left(self):
        """A proven listener's record says listening; a wait that finds mail exits 0 and says mail; one that times out exits 2 and says timeout. Each is one line with a fresh time, a regular file at 0640, this user's, with no .tmp beside it.

        Must reject a record that is not written at the lock (listening
        missing), the wrong word for an exit, a mode the group may write
        or may not read, half a line, and a .tmp left behind.

        @interacts  per subtest: a proven listener, or a send and a wait,
                    or a wait alone; lstats and reads the record.
        @deps       _root.TcRoot.listener, _root.TcRoot.tc; seen_record,
                    written.
        @complexity O(1).
        @alloc      one TcRoot per subtest.
        """
        with self.subTest(exit=LISTENING), _root.TcRoot() as root:
            box = root.path / "mail" / f"to-{NAME}"
            with root.listener(NAME, LISTENER_SECONDS):
                record_made(box)
                found = seen_record(box, time.time())
            self.assertEqual(found, written(LISTENING))
        with self.subTest(exit=MAIL), _root.TcRoot() as root:
            sent = root.tc("send", "--from", SENDER, "--to", NAME, "hi")
            code, out, err = root.tc("wait", NAME, "--timeout", str(WAKE_CEILING_SECONDS))
            found = seen_record(root.path / "mail" / f"to-{NAME}", time.time())
            self.assertEqual((sent[0], code, err, found), (0, EXIT_MAIL, "", written(MAIL)))
        with self.subTest(exit=TIMEOUT), _root.TcRoot() as root:
            code, out, err = root.tc("wait", NAME, "--timeout", AT_ONCE)
            found = seen_record(root.path / "mail" / f"to-{NAME}", time.time())
            self.assertEqual((code, err, found), (EXIT_TIMEOUT, "", written(TIMEOUT)))

    def test_a_link_at_the_records_name_is_moved_aside_and_its_target_unchanged(self):
        """A symlink at mail/to-b/.wait.exit to a file outside the mailbox: tc wait b exits 2 and says in one line that it moved the link aside to .wait.exit.planted-1, the link sits there, the record is a regular file of its own saying timeout, and the file the link led to keeps its text and its time.

        Must reject a record written through a link (an open by path,
        which follows it): a member could aim the owner's record at any
        file the owner may write. F1 fix round 1 (Claude Opus 5.5,
        unreviewed): the audit's MEDIUM-1, a link at the record's name is
        moved aside with words, as a wake lock's plant is.

        @interacts  makes the inbox, the outside file and the link by hand;
                    one wait; lstats and reads the record, the aside name
                    and the target.
        @deps       _root.TcRoot.tc; seen_record, written, mode_at; os, pwd.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with self.subTest(at="the record's name"), _root.TcRoot() as root:
            box = root.path / "mail" / f"to-{NAME}"
            box.mkdir(parents=True)
            outside = root.base / "outside"
            outside.write_text(OUTSIDE_TEXT)
            before = os.stat(outside).st_mtime_ns
            (box / RECORD).symlink_to(outside)
            kind = os.lstat(box / RECORD).st_mode
            aside = box / FIRST_ASIDE.format(name=RECORD)
            code, out, err = root.tc("wait", NAME, "--timeout", AT_ONCE)
            found = seen_record(box, time.time())
            said = MOVED_RECORD_WORDS.format(path=box / RECORD, what="a symlink", owner=pwd.getpwuid(os.geteuid()).pw_name,
                                             aside=aside)
            self.assertEqual((code, err, found, mode_at(aside), outside.read_text(), os.stat(outside).st_mtime_ns),
                             (EXIT_TIMEOUT, said + "\n", written(TIMEOUT), kind, OUTSIDE_TEXT, before))

    def test_a_wait_killed_by_its_pid_leaves_listening(self):
        """A proven listener killed by its own pid (SIGKILL): once its lock is gone, the record still says listening.

        C5: a wait that is killed or crashes leaves `listening`, which is
        how every reader tells it from a wait that left on purpose. Must
        reject a record that says an exit word before the wait has one.

        @interacts  one proven listener, killed by its pid; reads
                    /proc/locks until its lock goes; reads the record.
        @deps       _root.TcRoot.listener, lock_gone, seen_record; os,
                    signal.
        @complexity O(1), plus at most LOCK_GONE_SECONDS.
        @alloc      one TcRoot.
        """
        with self.subTest(killed="SIGKILL"), _root.TcRoot() as root:
            box = root.path / "mail" / f"to-{NAME}"
            with root.listener(NAME, LISTENER_SECONDS) as pid:
                record_made(box)  # killed after its start is written, so the kill is what the record shows
                os.kill(pid, signal.SIGKILL)
                gone = lock_gone(box / ".wait.lock", pid)
                found = seen_record(box, time.time())
            self.assertEqual((gone, found.word, found.kind), (True, LISTENING, "file"))

    def test_a_tmp_left_by_a_killed_wait_is_removed_and_anything_else_at_the_old_tmp_name_is_moved_aside(self):
        """At mail/to-b/.wait.exit.tmp, the old fixed .tmp name: this user's own leftover file is removed and the record written (exit 2, nothing on stderr); a symlink to a file outside, or a FIFO, is moved aside to .wait.exit.tmp.planted-1 with one line of words naming what it was and whose, never followed or waited on, the record is still written (timeout), and the wait exits 2, within WAKE_CEILING_SECONDS.

        Must reject a leftover .tmp that stops every later record (a wait
        killed between its create and its rename would end the record for
        good), a planted .tmp followed or waited on, and a plant that
        stops the record or is left with nothing said. F1 fix round 1
        (Claude Opus 5.5, unreviewed): the audit's MEDIUM-1; before it, a
        plant there stopped the record, with two lines of words.

        @interacts  per subtest: makes the inbox and what sits at the
                    .tmp's name by hand; one wait (under a time limit);
                    lstats the record, the .tmp's name, its aside name and
                    the target.
        @deps       _root.TcRoot.tc; seen_record, written, mode_at; os,
                    pwd.
        @complexity O(1) per subtest.
        @alloc      one TcRoot per subtest.
        """
        with self.subTest(at_tmp="this user's own leftover"), _root.TcRoot() as root:
            box = root.path / "mail" / f"to-{NAME}"
            box.mkdir(parents=True)
            (box / RECORD_TMP).write_text("listen")
            code, out, err = root.tc("wait", NAME, "--timeout", AT_ONCE)
            self.assertEqual((code, err, seen_record(box, time.time())), (EXIT_TIMEOUT, "", written(TIMEOUT)))
        for planted in ("a symlink", "a FIFO"):
            with self.subTest(at_tmp=planted), _root.TcRoot() as root:
                box = root.path / "mail" / f"to-{NAME}"
                box.mkdir(parents=True)
                outside = root.base / "outside"
                outside.write_text(OUTSIDE_TEXT)
                if planted == "a symlink":
                    (box / RECORD_TMP).symlink_to(outside)
                else:
                    os.mkfifo(box / RECORD_TMP)
                kind = os.lstat(box / RECORD_TMP).st_mode
                aside = box / FIRST_ASIDE.format(name=RECORD_TMP)
                code, out, err = root.tc("wait", NAME, "--timeout", AT_ONCE, timeout=WAKE_CEILING_SECONDS)
                said = MOVED_RECORD_WORDS.format(path=box / RECORD_TMP, what=planted,
                                                 owner=pwd.getpwuid(os.geteuid()).pw_name, aside=aside)
                self.assertEqual((code, err, seen_record(box, time.time()), mode_at(box / RECORD_TMP), mode_at(aside),
                                  outside.read_text()),
                                 (EXIT_TIMEOUT, said + "\n", written(TIMEOUT), None, kind, OUTSIDE_TEXT),
                                 f"what tc said: {err!r}")

    # F1 fix round 2 (Claude Opus 5.5, unreviewed): bugs LOW-1.
    def test_an_earlier_writes_leftover_tmp_is_removed_and_anything_else_of_its_form_is_moved_aside_once(self):
        """In mail/to-b/: this user's own one-name files at both LEFTOVERS, and one at NOT_OF_THE_FORM. tc wait b exits 2 with nothing on stderr, both LEFTOVERS are gone, NOT_OF_THE_FORM is still there, and the record says timeout. Then a symlink at LEFTOVERS[0] to a file outside: tc wait b exits 2 and says in one line that it moved the link aside to <name>.planted-1, the link sits there, the file it led to keeps its text, and the record says timeout; a second tc wait b says nothing and leaves the aside name as it is.

        Must reject a write that never looks at an earlier write's .tmp
        (each wait killed between its create and its rename leaves one for
        good, and they pile up), one that removes a name that is not of
        the form, one that follows or removes a plant there, and one that
        moves a plant it moved before again on every write.

        @interacts  per subtest: makes the inbox and what sits at the
                    names by hand; one or two waits; lstats the names, the
                    aside name and the target; reads the record.
        @deps       _root.TcRoot.tc; seen_record, mode_at; os, pwd;
                    LEFTOVERS, NOT_OF_THE_FORM, MOVED_RECORD_WORDS.
        @complexity O(1) per subtest.
        @alloc      one TcRoot per subtest.
        """
        with self.subTest(at_tmp="this user's own leftovers"), _root.TcRoot() as root:
            box = root.path / "mail" / f"to-{NAME}"
            box.mkdir(parents=True)
            for name in (*LEFTOVERS, NOT_OF_THE_FORM):
                (box / name).write_text("listen")
            code, out, err = root.tc("wait", NAME, "--timeout", AT_ONCE)
            found = seen_record(box, time.time())
            self.assertEqual((code, err, found.word, found.kind, [mode_at(box / name) is None for name in LEFTOVERS],
                              mode_at(box / NOT_OF_THE_FORM) is None),
                             (EXIT_TIMEOUT, "", TIMEOUT, "file", [True, True], False), f"what tc said: {err!r}")
        with self.subTest(at_tmp="a symlink"), _root.TcRoot() as root:
            box = root.path / "mail" / f"to-{NAME}"
            box.mkdir(parents=True)
            outside = root.base / "outside"
            outside.write_text(OUTSIDE_TEXT)
            plant = box / LEFTOVERS[0]
            plant.symlink_to(outside)
            kind = os.lstat(plant).st_mode
            aside = box / FIRST_ASIDE.format(name=LEFTOVERS[0])
            code, out, err = root.tc("wait", NAME, "--timeout", AT_ONCE)
            word = seen_record(box, time.time()).word
            again, _, err_again = root.tc("wait", NAME, "--timeout", AT_ONCE)
            said = MOVED_RECORD_WORDS.format(path=plant, what="a symlink", owner=pwd.getpwuid(os.geteuid()).pw_name,
                                             aside=aside)
            self.assertEqual((code, err, word, mode_at(plant), mode_at(aside), outside.read_text(), again, err_again,
                              mode_at(box / FIRST_ASIDE.format(name=aside.name))),
                             (EXIT_TIMEOUT, said + "\n", TIMEOUT, None, kind, OUTSIDE_TEXT, EXIT_TIMEOUT, "", None),
                             f"what tc said: {err!r} then {err_again!r}")


class ReaderTest(UmaskTestCase):
    """Item 2: the one reader takes the record only from the inbox owner's regular file with one name, of at most RECORD_MAX_BYTES, holding a word and a time.

    @interacts  see the module block.
    @deps       _root.TcRoot, UmaskTestCase, load_tc, owner_patched_fstat,
                in_thread.
    @complexity O(1) per subtest.
    @alloc      one TcRoot and one module per subtest.
    """

    def inbox(self, root):
        """mail/to-b/ made by hand under `root`, and tc loaded for `root`: (the inbox's path, the module).

        @interacts  makes two folders; loads tc (load_tc).
        @deps       load_tc.
        @complexity O(1).
        @alloc      one module, returned.
        """
        box = root.path / "mail" / f"to-{NAME}"
        box.mkdir(parents=True)
        return box, load_tc(root)

    def test_a_good_record_reads_as_its_word_and_time(self):
        """The control: mail/to-b/.wait.exit holding GOOD_LINE, this user's own: wait_exits gives b's word and time.

        Without it every refusal below could pass by refusing everything.

        @interacts  one record made by hand; wait_exits in process.
        @deps       inbox; GOOD_LINE, GOOD_AT.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        with self.subTest(record="good"), _root.TcRoot() as root:
            box, tc = self.inbox(root)
            (box / RECORD).write_text(GOOD_LINE)
            self.assertEqual(tc.wait_exits([NAME]), {NAME: (MAIL, GOOD_AT)})

    def test_the_reader_refuses_anything_but_the_owners_one_line_regular_file(self):
        """Each of these at mail/to-b/.wait.exit is no record (wait_exits gives {} for b): GOOD_LINE in a file reported as another user's (as the SHARED suites report owners); a symlink to a file outside holding GOOD_LINE; a FIFO, within FIFO_CEILING_SECONDS; GOOD_LINE in a file with a second name; LONG_LINE, past RECORD_MAX_BYTES; each MALFORMED line.

        Must reject a record a member planted in a shared inbox believed,
        a record followed through a link, a read that hangs on a FIFO, a
        hard-linked file believed, an unbounded read, and a line that is
        not one word of the three and a time with its offset.

        @interacts  per subtest: one record (or link, FIFO, hard link)
                    made by hand; wait_exits in process, with os.fstat
                    patched for the other user's, in a thread for the
                    FIFO.
        @deps       inbox, in_thread, owner_patched_fstat; os,
                    unittest.mock; GOOD_LINE, LONG_LINE, MALFORMED,
                    OUTSIDE_TEXT.
        @complexity O(1) per subtest.
        @alloc      one TcRoot and one module per subtest.
        """
        with self.subTest(record="another user's"), _root.TcRoot() as root:
            box, tc = self.inbox(root)
            (box / RECORD).write_text(GOOD_LINE)
            with mock.patch.object(os, "fstat", owner_patched_fstat(box / RECORD)):
                self.assertEqual(tc.wait_exits([NAME]), {})
        with self.subTest(record="a symlink"), _root.TcRoot() as root:
            box, tc = self.inbox(root)
            outside = root.base / "outside"
            outside.write_text(GOOD_LINE)
            (box / RECORD).symlink_to(outside)
            self.assertEqual(tc.wait_exits([NAME]), {})
        with self.subTest(record="a FIFO"), _root.TcRoot() as root:
            box, tc = self.inbox(root)
            os.mkfifo(box / RECORD)
            blocked, got = in_thread(lambda: tc.wait_exits([NAME]), box / RECORD)
            self.assertEqual((blocked, got), (False, {}))
        with self.subTest(record="a second name"), _root.TcRoot() as root:
            box, tc = self.inbox(root)
            (box / RECORD).write_text(GOOD_LINE)
            os.link(box / RECORD, root.base / "second-name")
            self.assertEqual(tc.wait_exits([NAME]), {})
        with self.subTest(record="over the bound"), _root.TcRoot() as root:
            box, tc = self.inbox(root)
            (box / RECORD).write_text(LONG_LINE)
            self.assertEqual((len(LONG_LINE.encode()) > RECORD_MAX_BYTES, tc.wait_exits([NAME])), (True, {}))
        for label, line in MALFORMED:
            with self.subTest(record=label), _root.TcRoot() as root:
                box, tc = self.inbox(root)
                (box / RECORD).write_text(line)
                self.assertEqual((len(line.encode()) <= RECORD_MAX_BYTES, tc.wait_exits([NAME])), (True, {}))

    def test_left_on_purpose_takes_mail_or_timeout_written_since_the_lock_was_last_seen(self):
        """left_on_purpose: mail or timeout dated after the lock was last seen, in its second, or in the second before (a wait writes its exit a moment before its lock goes, and the time is cut to the second) is True, and with no sighting (None) any date is; listening, no record, and a mail or timeout dated RECORD_TIME_STEP_SECONDS or more before the sighting are False.

        Must reject a stale mail record (from a wait before the one last
        seen, whose own listening could not be written) taken as that
        wait's purposeful exit, and listening taken as one; and a wait's
        own exit, written just before a second turned and seen held just
        after, refused (tc watch would call a woken listener down).

        @interacts  per case: loads tc; calls left_on_purpose in process.
        @deps       load_tc; GOOD_AT, RECORD_TIME_STEP_SECONDS.
        @complexity O(1): eight cases.
        @alloc      one TcRoot and one module per case.
        """
        cases = (("mail, written after the sighting", MAIL, GOOD_AT - 1, True),
                 ("timeout, written in the sighting's second", TIMEOUT, GOOD_AT + 0.7, True),
                 ("mail, written just before the second the lock was seen in", MAIL, GOOD_AT + 1.5, True),
                 ("mail, never seen", MAIL, None, True),
                 ("mail, dated the step before the sighting", MAIL, GOOD_AT + RECORD_TIME_STEP_SECONDS, False),
                 ("listening", LISTENING, GOOD_AT - 1, False),
                 ("listening, never seen", LISTENING, None, False),
                 ("no record", None, None, False))
        for label, word, seen, expected in cases:
            with self.subTest(case=label), _root.TcRoot() as root:
                tc = load_tc(root)
                record = None if word is None else tc.WaitExit(word, GOOD_AT)
                self.assertEqual(tc.left_on_purpose(record, seen), expected)


# F1 (Claude Opus 5.5, unreviewed): item 3.
class WatchTest(UmaskTestCase):
    """Item 3: tc watch --names alerts LISTENER DOWN only for a tracked wait whose lock went while its record still says listening.

    @interacts  see the module block; starts tc watch children through
                the harness, each killed by its pid in teardown if still
                running.
    @deps       _root.TcRoot, UmaskTestCase, start_watch, record_made,
                lock_gone, seen_record.
    @complexity O(1) per subtest, each up to its watch's heartbeat.
    @alloc      one TcRoot per subtest.
    """

    def test_a_watch_never_calls_a_wait_that_mail_woke_or_that_timed_out_down_and_alerts_once_for_one_killed(self):
        """b listens and w watches it: b woken by mail (its record says mail), and b timing out on its own (timeout), each leave w to heartbeat, exit 0, with no LISTENER DOWN; b killed by its pid (its record still says listening) makes w alert once, exit 5, within ALERT_CEILING_SECONDS.

        The known bug liveness-gap-by-design-read-as-down's second
        instance: before F1, w compared only the locks held at its start
        with the locks held now, so every wake read as a lost listener.
        Must reject a watch that ignores the record (the woken and timed
        out cases alert) and one that trusts any record (the killed case,
        the control, would not alert).

        @interacts  per subtest: one proven listener; one tc watch; a send
                    or a kill; reads /proc/locks and the record.
        @deps       _root.TcRoot.listener, _root.TcRoot.tc, start_watch,
                    finish, record_made, lock_gone, seen_record; os,
                    signal, time.
        @complexity O(1) per subtest: up to WATCH_HEARTBEAT_SECONDS,
                    SHORT_HEARTBEAT_SECONDS and ALERT_CEILING_SECONDS.
        @alloc      one TcRoot per subtest.
        """
        with self.subTest(tracked="woken by mail"), _root.TcRoot() as root:
            box = root.path / "mail" / f"to-{NAME}"
            with root.listener(NAME, LISTENER_SECONDS) as pid:
                record_made(box)
                watch, looked = start_watch(root, WATCH_HEARTBEAT_SECONDS)
                sent = root.tc("send", "--from", SENDER, "--to", NAME, "task")
                gone = lock_gone(box / WAIT_LOCK, pid, WAKE_CEILING_SECONDS)
                code, out, err = finish(watch, WATCH_HEARTBEAT_SECONDS + ALERT_CEILING_SECONDS)
            word = seen_record(box, time.time()).word
            self.assertEqual((looked, sent[0], gone, word, code, "LISTENER DOWN" in out),
                             (True, 0, True, MAIL, 0, False), f"w said: {out!r} {err!r}")
        with self.subTest(tracked="timed out"), _root.TcRoot() as root:
            box = root.path / "mail" / f"to-{NAME}"
            with root.listener(NAME, SHORT_WAIT_SECONDS) as pid:
                record_made(box)
                watch, looked = start_watch(root, SHORT_HEARTBEAT_SECONDS)
                gone = lock_gone(box / WAIT_LOCK, pid, SHORT_HEARTBEAT_SECONDS)
                code, out, err = finish(watch, SHORT_HEARTBEAT_SECONDS + ALERT_CEILING_SECONDS)
            word = seen_record(box, time.time()).word
            self.assertEqual((looked, gone, word, code, "LISTENER DOWN" in out),
                             (True, True, TIMEOUT, 0, False), f"w said: {out!r} {err!r}")
        with self.subTest(tracked="killed by its pid"), _root.TcRoot() as root:
            box = root.path / "mail" / f"to-{NAME}"
            with root.listener(NAME, LISTENER_SECONDS) as pid:
                record_made(box)
                watch, looked = start_watch(root, LISTENER_SECONDS)
                os.kill(pid, signal.SIGKILL)
                code, out, err = finish(watch, ALERT_CEILING_SECONDS)
            word = seen_record(box, time.time()).word
            self.assertEqual((looked, word, code, out.count(f"LISTENER DOWN: {NAME}")),
                             (True, LISTENING, EXIT_ALERT, 1), f"w said: {out!r} {err!r}")


# F1 (Claude Opus 5.5, unreviewed): item 4.
def parsed(text):
    """`text` as JSON, or None when it is not JSON, so a test fails on its assertion, never on a parse.

    @interacts  none.
    @deps       json.
    @complexity O(t) over t characters.
    @alloc      the parsed value, returned.
    """
    try:
        return json.loads(text)
    except ValueError:
        return None


class HealthTest(UmaskTestCase):
    """Item 4: tc health shows each stopped name's last exit word and its age, in words and under a new JSON key, and the gate's health never carries it.

    @interacts  see the module block.
    @deps       _root.TcRoot, UmaskTestCase, load_tc, stop_names,
                record_made, run_in_process, parsed.
    @complexity O(1) per subtest.
    @alloc      one TcRoot and one module per subtest.
    """

    def health_of(self, root, call):
        """`call(tc)` for tc loaded on `root`, with tc's clock LATER_SECONDS past GOOD_AT, no GPU query, and the far key's health command set for the gate: what `call` returns.

        @interacts  loads tc; patches its wall_clock and gpu_stats and the
                    process's SSH_ORIGINAL_COMMAND while `call` runs.
        @deps       load_tc; os, unittest.mock; GOOD_AT, LATER_SECONDS,
                    GATE_HEALTH.
        @complexity O(1), plus the call.
        @alloc      one module.
        """
        tc = load_tc(root)
        with mock.patch.object(tc, "wall_clock", lambda: GOOD_AT + LATER_SECONDS), \
                mock.patch.object(tc, "gpu_stats", lambda: None), \
                mock.patch.dict(os.environ, {"SSH_ORIGINAL_COMMAND": GATE_HEALTH}):
            return call(tc)

    def test_health_shows_each_stopped_names_last_exit_and_its_age_and_the_gate_never_does(self):
        """sb, sc and sd stopped with records saying timeout, mail and listening, written two minutes before tc's clock; se stopped with no record; sf a live, proven listener whose own record says listening. tc health's listeners line: `sf (pid N) · stopped: sb (timeout, 2m ago), sc (mail, 2m ago), sd (listening, 2m ago), se`. Its JSON's wait_exits: sb, sc and sd, each its word and 120 s, and nothing for se or sf. The gate's health --json has no wait_exits key, while this mailbox's own health has one that is not empty.

        Must reject a health that drops the exit, that shows a live
        listener's record (only its lock says it is live), that invents a
        record for a name with none, and a gate that hands the key to a
        far key (GATE_HEALTH_KEYS stays as it is: an allow list).

        @interacts  per subtest: stop_names' files; one proven listener;
                    cmd_health or cmd_gate, and health_snapshot, in
                    process (health_of).
        @deps       stop_names, record_made, health_of, run_in_process,
                    parsed; _root.TcRoot.listener; argparse.
        @complexity O(1) per subtest.
        @alloc      one TcRoot and one module per subtest.
        """
        words = f" · stopped: sb (timeout, {LATER_WORDS}), sc (mail, {LATER_WORDS}), sd (listening, {LATER_WORDS}), se"
        exits = {"sb": {"word": TIMEOUT, "age_s": LATER_SECONDS}, "sc": {"word": MAIL, "age_s": LATER_SECONDS},
                 "sd": {"word": LISTENING, "age_s": LATER_SECONDS}}
        with self.subTest(shown="in words"), _root.TcRoot() as root:
            stop_names(root)
            with root.listener(LIVE, LISTENER_SECONDS) as pid:
                record_made(root.path / "mail" / f"to-{LIVE}")
                code, out, err = self.health_of(root, lambda tc: run_in_process(
                    lambda: tc.cmd_health(argparse.Namespace(json=False))))
            line = next((text for text in out.splitlines() if text.startswith("listeners")), None)
            self.assertEqual((code, line), (0, f"listeners  {LIVE} (pid {pid}){words}"), err)
        with self.subTest(shown="as JSON"), _root.TcRoot() as root:
            stop_names(root)
            with root.listener(LIVE, LISTENER_SECONDS):
                record_made(root.path / "mail" / f"to-{LIVE}")
                code, out, err = self.health_of(root, lambda tc: run_in_process(
                    lambda: tc.cmd_health(argparse.Namespace(json=True))))
            self.assertEqual((code, (parsed(out) or {}).get(EXITS_KEY)), (0, exits), err)
        with self.subTest(shown="the gate's health"), _root.TcRoot() as root:
            stop_names(root)
            mine, (code, out, err) = self.health_of(root, lambda tc: (
                tc.health_snapshot(gpu=False), run_in_process(lambda: tc.cmd_gate(argparse.Namespace(as_name=GATE_KEY)))))
            gated = parsed(out) or {}
            self.assertEqual((code, mine.get(EXITS_KEY) == exits, EXITS_KEY in gated), (0, True, False),
                             f"the gate's keys: {sorted(gated)}; {err}")


# F1 (Claude Opus 5.5, unreviewed): item 6, the record is never proof of life (rule 6).
class NeverAListenerTest(UmaskTestCase):
    """Item 2's promise, item 6's test: with the lock gone and the record saying listening or mail, listeners() and tc health name no pid.

    @interacts  see the module block.
    @deps       _root.TcRoot, UmaskTestCase, load_tc, record_made,
                lock_gone, seen_record, parsed.
    @complexity O(1) per subtest.
    @alloc      one TcRoot and one module per subtest.
    """

    def test_a_record_never_makes_a_name_a_listener(self):
        """b's wait killed by its pid (record listening), or ended on mail (record mail), its lock gone: tc's listeners() gives b None, tc health --json's listeners gives b null, and tc health's words list b only after `stopped:`, with no pid.

        Known bug listener-reported-live-without-the-lock: a listening
        claim with no lock behind it. Must reject a reader that takes the
        record as a listener: the record says what a wait last wrote, and
        only a held lock says it runs.

        @interacts  per subtest: one proven listener killed by its pid, or
                    a send and a wait that ends on it; reads /proc/locks;
                    listeners() in process; tc health twice.
        @deps       _root.TcRoot.listener, _root.TcRoot.tc, load_tc,
                    record_made, lock_gone, seen_record, parsed; os,
                    signal, time.
        @complexity O(1) per subtest.
        @alloc      one TcRoot and one module per subtest.
        """
        for word in (LISTENING, MAIL):
            with self.subTest(record=word), _root.TcRoot() as root:
                box = root.path / "mail" / f"to-{NAME}"
                if word == LISTENING:
                    with root.listener(NAME, LISTENER_SECONDS) as pid:
                        record_made(box)
                        os.kill(pid, signal.SIGKILL)
                        gone = lock_gone(box / WAIT_LOCK, pid)
                else:
                    root.tc("send", "--from", SENDER, "--to", NAME, "task")
                    gone = root.tc("wait", NAME, "--timeout", str(WAKE_CEILING_SECONDS))[0] == EXIT_MAIL
                seen = seen_record(box, time.time()).word
                listed = load_tc(root).listeners("wait")
                as_json = (parsed(root.tc("health", "--json")[1]) or {}).get("listeners", {})
                line = next((text for text in root.tc("health")[1].splitlines() if text.startswith("listeners")), "")
                self.assertEqual((gone, seen, NAME in listed, listed.get(NAME), NAME in as_json, as_json.get(NAME),
                                  line.startswith(f"listeners  none running · stopped: {NAME} ({word}, "),
                                  "pid" in line),
                                 (True, word, True, None, True, None, True, False), line)


# F1 (Claude Opus 5.5, unreviewed): item 5.
def load_serve():
    """Load board/serve.py as a module, as the board tests do.

    @interacts  executes serve.py's top level (constants and definitions).
    @deps       importlib; SERVE_PATH.
    @complexity O(1).
    @alloc      one module object, returned.
    """
    spec = importlib.util.spec_from_file_location("board_serve_wait_exit", SERVE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


serve = load_serve()


def states(feed):
    """{name: state} for each of FIVE in one board feed; None for a name it lacks.

    @interacts  none.
    @deps       FIVE.
    @complexity O(n) over n nodes.
    @alloc      one dict, returned.
    """
    nodes = {node["id"]: node["state"] for node in feed["nodes"]}
    return {name: nodes.get(name) for name in FIVE}


def stale_line():
    """A `mail` record line dated STALE_AGE_SECONDS ago, in a message header's form.

    @interacts  reads the clock and the local time zone.
    @deps       datetime, time; MAIL, STALE_AGE_SECONDS.
    @complexity O(1).
    @alloc      one string, returned.
    """
    at = datetime.datetime.fromtimestamp(time.time() - STALE_AGE_SECONDS).astimezone()
    return f"{MAIL} {at.isoformat(timespec='seconds')}\n"


# F1 fix round 1 (Claude Opus 5.5, unreviewed): the audit's LOW-1.
def stamp(at):
    """The time `at` (seconds since the epoch) in a message header's form, cut to the second, with its offset.

    @interacts  reads the local time zone.
    @deps       datetime.
    @complexity O(1).
    @alloc      one string, returned.
    """
    return datetime.datetime.fromtimestamp(at).astimezone().isoformat(timespec="seconds")


def listening_line(at):
    """A `listening` record line dated `at` (seconds since the epoch).

    @interacts  reads the local time zone (stamp).
    @deps       stamp; LISTENING.
    @complexity O(1).
    @alloc      one string, returned.
    """
    return f"{LISTENING} {stamp(at)}\n"


def stop_five(root, board=None):
    """Start FIVE proven listeners (TIMED's ends on its own after SHORT_WAIT_SECONDS), wait for each record, put STALE's back to a stale `mail`, let `board` (when given) see all five listening, then: WOKEN mailed, KILLED, BARE and STALE killed by their pids, TIMED left to time out; once every lock is gone, BARE's record is moved aside. (records all made, the send's exit, every lock gone, the board's states while all listened or None).

    @interacts  starts five listeners through the harness; one send;
                SIGKILL to three of them by their pids; reads /proc/locks;
                writes STALE's record by hand (a .tmp renamed over it) and
                renames BARE's aside; one feed of `board`.
    @deps       _root.TcRoot.listener, _root.TcRoot.tc, record_made,
                lock_gone, stale_line, states; contextlib, os, signal.
    @complexity O(1): five listeners, up to WAKE_CEILING_SECONDS for the
                locks to go.
    @alloc      the listeners, killed and reaped before return.
    """
    boxes = {name: root.path / "mail" / f"to-{name}" for name in FIVE}
    with contextlib.ExitStack() as stack:
        pids = {name: stack.enter_context(root.listener(name, SHORT_WAIT_SECONDS if name == TIMED else LISTENER_SECONDS))
                for name in FIVE}
        made = all([record_made(boxes[name]) for name in FIVE])
        tmp = boxes[STALE] / RECORD_TMP
        tmp.write_text(stale_line())
        os.rename(tmp, boxes[STALE] / RECORD)
        seen = states(board.feed()) if board is not None else None
        sent = root.tc("send", "--from", SENDER, "--to", WOKEN, "task")[0]
        for name in (KILLED, BARE, STALE):
            os.kill(pids[name], signal.SIGKILL)
        gone = all([lock_gone(boxes[name] / WAIT_LOCK, pids[name], WAKE_CEILING_SECONDS) for name in FIVE])
    os.rename(boxes[BARE] / RECORD, boxes[BARE] / RECORD_ASIDE)
    return made, sent, gone, seen


class BoardTest(UmaskTestCase):
    """Item 5: the board reads a lock gone with its wait exit record (C5), never down for a listener that left on purpose, down for one killed, after a restart too, and today's rules with no record.

    @interacts  see the module block; loads board/serve.py and runs
                Board.feed() on a clock the test sets (the real time, then
                past the down window).
    @deps       _root.TcRoot, UmaskTestCase, serve, stop_five, states.
    @complexity O(1) per subtest: five listeners and two or three feeds.
    @alloc      one TcRoot and one Board per subtest.
    """

    def test_a_listener_that_left_on_purpose_is_never_down_and_a_killed_one_is_down_after_a_restart_too(self):
        """Five listeners the board saw, then: woken by mail reads working (the woken rules), killed reads down, timed out reads idle (never down: its record says timeout), no record reads down (today's rule), and a stale mail record reads down (it is older than the board's sighting). Past DOWN_WINDOW_S: killed still reads down (its record says listening), the rest idle. A fresh Board (a restart) over the same five: killed reads down, woken (record mail) and timed (timeout) read idle, never down; no record and the stale one read idle, as a restart always has.

        Must reject a board that ignores the record (timed out reads
        down; killed fades to idle past the window and after a restart),
        that reads no record as a kill (bare reads down after a restart),
        that takes a record older than its sighting (stale reads idle),
        and that keeps the restart rule for a `listening` record.

        @interacts  per subtest: stop_five; feeds of one Board, or of a
                    fresh one after.
        @deps       stop_five, states, serve.Board; time.
        @complexity O(1) per subtest.
        @alloc      one TcRoot and one Board per subtest.
        """
        after = {WOKEN: "working", KILLED: "down", TIMED: "idle", BARE: "down", STALE: "down"}
        past = {WOKEN: "idle", KILLED: "down", TIMED: "idle", BARE: "idle", STALE: "idle"}
        restarted = {WOKEN: "idle", KILLED: "down", TIMED: "idle", BARE: "idle", STALE: "idle"}
        with self.subTest(board="live, then past the window"), _root.TcRoot() as root:
            clock = {"now": time.time()}
            board = serve.Board(root=root.path, clock=lambda: clock["now"])
            made, sent, gone, seen = stop_five(root, board)
            clock["now"] = time.time()
            first = states(board.feed())
            clock["now"] += DOWN_WINDOW_S + 1
            later = states(board.feed())
            self.assertEqual((made, sent, gone, seen, first, later), (True, 0, True, ALL_LISTENING, after, past))
        with self.subTest(board="restarted"), _root.TcRoot() as root:
            made, sent, gone, _ = stop_five(root)
            fresh = states(serve.Board(root=root.path, clock=time.time).feed())
            self.assertEqual((made, sent, gone, fresh), (True, 0, True, restarted))

    # F1 fix round 1 (Claude Opus 5.5, unreviewed): the audit's LOW-1, a2's ruling (C5).
    def test_a_down_node_carries_how_long_ago_it_stopped_from_the_sighting_or_else_the_record(self):
        """down_age_s, by value. On a fresh Board (a restart), names whose records say listening, dated NINE_MIN_S and ELEVEN_MIN_S before the Board's clock, each with no lock held, read down with down_age_s NINE_MIN_S and ELEVEN_MIN_S; one whose record says mail reads idle with none. On a Board that saw a listener whose record says listening dated LONG_WAIT_S ago (a long wait's start), killed by its pid, the next feed STOP_SEEN_S later reads it down with down_age_s STOP_SEEN_S, never LONG_WAIT_S and more.

        The page's pill warns only on a stop under DOWN_WINDOW_S old
        (tests/board-patch.test.mjs holds that half). Must reject a feed
        with no age (the pill could not tell), an age from the record
        alone (a wait runs up to 110 min, so every kill of one would read
        as stopped earlier and never warn), and an age on a node that
        left on purpose.

        @interacts  per subtest: inboxes, unheld locks and records made by
                    hand; or one proven listener, its record replaced by
                    hand (a .tmp renamed over it), killed by its pid; feeds
                    of one Board on a clock the test sets.
        @deps       serve.Board, listening_line, record_made, lock_gone,
                    _root.TcRoot.listener; os, signal, time.
        @complexity O(1) per subtest.
        @alloc      one TcRoot and one Board per subtest.
        """
        with self.subTest(board="restarted, records only"), _root.TcRoot() as root:
            now = float(int(time.time()))
            for name, line in ((NINE, listening_line(now - NINE_MIN_S)), (ELEVEN, listening_line(now - ELEVEN_MIN_S)),
                               (LEFT, f"{MAIL} {stamp(now - NINE_MIN_S)}\n")):
                box = root.path / "mail" / f"to-{name}"
                box.mkdir(parents=True)
                (box / WAIT_LOCK).touch()
                (box / RECORD).write_text(line)
            feed = serve.Board(root=root.path, clock=lambda: now).feed()
            nodes = {n["id"]: (n["state"], n.get("down_age_s", MISSING)) for n in feed["nodes"]}
            self.assertEqual(nodes, {NINE: ("down", NINE_MIN_S), ELEVEN: ("down", ELEVEN_MIN_S), LEFT: ("idle", None)})
        with self.subTest(board="saw it listening"), _root.TcRoot() as root:
            box = root.path / "mail" / f"to-{NAME}"
            clock = {"now": float(int(time.time()))}
            board = serve.Board(root=root.path, clock=lambda: clock["now"])
            with root.listener(NAME, LISTENER_SECONDS) as pid:
                made = record_made(box)
                (box / RECORD_TMP).write_text(listening_line(clock["now"] - LONG_WAIT_S))
                os.rename(box / RECORD_TMP, box / RECORD)
                seen = {n["id"]: n["state"] for n in board.feed()["nodes"]}.get(NAME)
                os.kill(pid, signal.SIGKILL)
                gone = lock_gone(box / WAIT_LOCK, pid)
            clock["now"] += STOP_SEEN_S
            after = {n["id"]: (n["state"], n.get("down_age_s", MISSING)) for n in board.feed()["nodes"]}.get(NAME)
            self.assertEqual((made, seen, gone, after), (True, "listening", True, ("down", STOP_SEEN_S)))

    # F1 fix round 2 (Claude Opus 5.5, unreviewed): bugs LOW-3, integration LOW-2.
    def test_a_down_the_window_rules_gave_carries_the_time_since_the_lock_was_last_seen(self):
        """A Board saw b listening (a proven listener), then b was killed by its pid and its record either moved aside (no record) or replaced by a `mail` dated LONG_WAIT_S before the sighting (older than it, so not this wait's exit). The next feed, STOP_SEEN_S later, reads b down by the window rules with down_age_s STOP_SEEN_S.

        C5: "The feed gives each `down` node its age (`down_age_s`)". Must
        reject a window `down` with no age (its box could not say how long
        ago it stopped) and an age taken from a record that does not say
        `listening`.

        @interacts  per subtest: one proven listener, killed by its pid;
                    its record renamed aside, or replaced by hand (a .tmp
                    renamed over it); two feeds of one Board on a clock the
                    test sets.
        @deps       serve.Board, stamp, record_made, lock_gone,
                    _root.TcRoot.listener; os, signal, time.
        @complexity O(1) per subtest.
        @alloc      one TcRoot and one Board per subtest.
        """
        for case in ("no record", "a mail record older than the sighting"):
            with self.subTest(record=case), _root.TcRoot() as root:
                box = root.path / "mail" / f"to-{NAME}"
                clock = {"now": float(int(time.time()))}
                board = serve.Board(root=root.path, clock=lambda: clock["now"])
                with root.listener(NAME, LISTENER_SECONDS) as pid:
                    made = record_made(box)
                    seen = {n["id"]: n["state"] for n in board.feed()["nodes"]}.get(NAME)
                    os.kill(pid, signal.SIGKILL)
                    gone = lock_gone(box / WAIT_LOCK, pid)
                if case == "no record":
                    os.rename(box / RECORD, box / RECORD_ASIDE)
                else:
                    (box / RECORD_TMP).write_text(f"{MAIL} {stamp(clock['now'] - LONG_WAIT_S)}\n")
                    os.rename(box / RECORD_TMP, box / RECORD)
                clock["now"] += STOP_SEEN_S
                after = {n["id"]: (n["state"], n.get("down_age_s", MISSING)) for n in board.feed()["nodes"]}.get(NAME)
                self.assertEqual((made, seen, gone, after), (True, "listening", True, ("down", STOP_SEEN_S)))


# F1 fix round 1 (Claude Opus 5.5, unreviewed): the audit's LOW-2 and LOW-3.
def stale_listing(real, name, at):
    """A stand-in for tc's listeners that answers its call number `at` (from 1) with `name` holding no lock, as a listing taken a moment before that name's session re-armed would, and every other call as `real` does. Returns (the stand-in, a dict whose "served" says the stale answer went out).

    @interacts  none until called; then calls `real`.
    @deps       none.
    @complexity O(1) per call, plus `real`'s.
    @alloc      one dict per call (a copy of the listing).
    """
    state = {"calls": 0, "served": False}

    def listing(*args, **kwargs):
        found = dict(real(*args, **kwargs))
        state["calls"] += 1
        if state["calls"] == at:
            state["served"] = True
            found[name] = None
        return found
    return listing, state


class RearmTest(UmaskTestCase):
    """The audit's LOW-2 and LOW-3: a session that re-arms between a lock listing and the record read (its new wait holds the lock and wrote `listening`) is never read as killed, by tc watch --names or by the board.

    @interacts  see the module block; runs cmd_watch in process with tc's
                listeners, gpu_stats and resource.setrlimit replaced, and
                Board.feed() with its tc's listeners replaced.
    @deps       _root.TcRoot, UmaskTestCase, load_tc, serve,
                stale_listing, record_made, run_in_process.
    @complexity O(1) per subtest.
    @alloc      one TcRoot per subtest.
    """

    def test_a_listener_that_rearmed_between_the_listing_and_the_record_is_never_down(self):
        """b listens (a proven listener, its record `listening`). The watch: w tracks b, and its first poll's listing misses b's lock, as one taken just before b re-armed would; it still heartbeats, exit 0, with no LISTENER DOWN. The board: its first listing misses b's lock the same way; b reads listening with its pid, never down.

        Staged in process: the stale listing is tc's listeners answering
        once without b, while b's real lock is held and its record says
        `listening`, the order the race gives. Must reject a watch or a
        board that takes that record as a kill with no second look at the
        locks.

        @interacts  per subtest: one proven listener; cmd_watch in process,
                    or one Board feed, with the first listing stale.
        @deps       stale_listing, record_made, run_in_process,
                    load_tc, serve.Board; argparse, unittest.mock.
        @complexity O(1): one REARM_HEARTBEAT_SECONDS watch, one feed.
        @alloc      one TcRoot and one module per subtest.
        """
        with self.subTest(reader="tc watch --names"), _root.TcRoot() as root:
            box = root.path / "mail" / f"to-{NAME}"
            with root.listener(NAME, LISTENER_SECONDS):
                made = record_made(box)
                tc = load_tc(root)
                # The watch's start lists b (call 1); its first poll's listing (call 2) is the stale one.
                listing, state = stale_listing(tc.listeners, NAME, WATCH_FIRST_POLL_LISTING)
                args = argparse.Namespace(name=WATCHER, heartbeat=REARM_HEARTBEAT_SECONDS, poll=REARM_POLL_SECONDS,
                                          names=NAME, **QUIET_ARGS)
                with mock.patch.object(tc.resource, "setrlimit", lambda *a: None), \
                        mock.patch.object(tc, "gpu_stats", lambda: None), \
                        mock.patch.object(tc, "listeners", listing):
                    code, out, err = run_in_process(lambda: tc.cmd_watch(args))
            self.assertEqual((made, state["served"], code, "LISTENER DOWN" in out), (True, True, 0, False),
                             f"w said: {out!r} {err!r}")
        with self.subTest(reader="the board"), _root.TcRoot() as root:
            box = root.path / "mail" / f"to-{NAME}"
            board = serve.Board(root=root.path, clock=time.time)
            with root.listener(NAME, LISTENER_SECONDS) as pid:
                made = record_made(box)
                listing, state = stale_listing(board.tc.listeners, NAME, BOARD_FIRST_LISTING)
                with mock.patch.object(board.tc, "listeners", listing):
                    node = {n["id"]: (n["state"], n["listener_pid"]) for n in board.feed()["nodes"]}.get(NAME)
            self.assertEqual((made, state["served"], node), (True, True, ("listening", pid)))


if __name__ == "__main__":
    unittest.main()
