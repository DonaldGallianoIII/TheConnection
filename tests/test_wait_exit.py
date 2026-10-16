"""
Tests for the wait exit record (F1; contract C5's "The wait exit record",
D28, D37 part 2): `tc wait <name>` keeps one line beside its lock,
mail/to-<name>/.wait.exit, `listening` once it holds the lock and `mail`
or `timeout` as it exits 0 or 2, replaced whole and never followed; one
reader takes it only from the inbox owner's one-line regular file; and
the record is never proof of life.

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
            holds its lock. Writes nothing outside the root's temp
            folder.
@deps       python3 stdlib (argparse, collections, contextlib, datetime,
            io, json, os, pathlib, signal, stat, subprocess, sys,
            threading, time, unittest, unittest.mock);
            tests/_root.py; UmaskTestCase, load_tc and owner_patched_fstat
            from test_shared.py; ../tc.
@complexity O(1) per test: a handful of tc runs per root, one root per
            subtest; the killed-listener test reads /proc/locks until the
            lock goes, at most LOCK_GONE_SECONDS; each watch subtest runs
            up to its watch's heartbeat (about 8 to 14 s).
@alloc      one TcRoot per subtest, removed when its context exits, with
            every child it started.
"""

import argparse
import collections
import contextlib
import datetime
import io
import json
import os
import pathlib
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
# The record's name, its .tmp's, its mode and its three words (tc's
# WAIT_EXIT_NAME, WAIT_EXIT_TMP_NAME, WAIT_EXIT_MODE, WAIT_EXIT_WORDS),
# written here rather than read from tc, so a changed constant fails a test.
RECORD = ".wait.exit"
RECORD_TMP = ".wait.exit.tmp"
RECORD_MODE = 0o640
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

    @interacts  lstats the record and its .tmp's name; reads the record
                when it is a regular file.
    @deps       datetime, os, stat; RECORD, RECORD_TMP, TIME_SLACK_SECONDS.
    @complexity O(1): one short file.
    @alloc      one Seen, returned.
    """
    path = box / RECORD
    tmp_left = os.path.lexists(box / RECORD_TMP)
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
                lock_gone.
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

    def test_a_link_at_the_records_name_is_replaced_and_its_target_unchanged(self):
        """A symlink at mail/to-b/.wait.exit to a file outside the mailbox: tc wait b exits 2, the record is a regular file of its own saying timeout, and the file the link led to keeps its text and its time.

        Must reject a record written through a link (an open by path,
        which follows it): a member could aim the owner's record at any
        file the owner may write.

        @interacts  makes the inbox, the outside file and the link by hand;
                    one wait; lstats and reads the record and the target.
        @deps       _root.TcRoot.tc; seen_record, written.
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
            code, out, err = root.tc("wait", NAME, "--timeout", AT_ONCE)
            found = seen_record(box, time.time())
            self.assertEqual((code, err, found, outside.read_text(), os.stat(outside).st_mtime_ns),
                             (EXIT_TIMEOUT, "", written(TIMEOUT), OUTSIDE_TEXT, before))

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

    def test_a_tmp_left_by_a_killed_wait_is_removed_and_one_anything_else_put_there_stops_only_the_record(self):
        """At mail/to-b/.wait.exit.tmp: this user's own leftover file is removed and the record written (exit 2, nothing on stderr); a symlink to a file outside, or a FIFO, is left as it is, the record is not written, tc says so on stderr in one line per write it could not make (two: the start and the exit), each naming the .tmp, and the wait still exits 2, within WAKE_CEILING_SECONDS.

        Must reject a leftover .tmp that stops every later record (a wait
        killed between its create and its rename would end the record for
        good), a planted .tmp followed or waited on, and a failed write
        that changes the wait's exit code or says nothing.

        @interacts  per subtest: makes the inbox and what sits at the
                    .tmp's name by hand; one wait (under a time limit);
                    lstats the record, the .tmp's name and the target.
        @deps       _root.TcRoot.tc; seen_record, written; os.
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
                code, out, err = root.tc("wait", NAME, "--timeout", AT_ONCE, timeout=WAKE_CEILING_SECONDS)
                lines = err.splitlines()
                self.assertEqual((code, len(lines), all(str(box / RECORD_TMP) in line for line in lines),
                                  seen_record(box, time.time()).word, os.lstat(box / RECORD_TMP).st_mode,
                                  outside.read_text()),
                                 (EXIT_TIMEOUT, 2, True, None, kind, OUTSIDE_TEXT),
                                 f"what tc said: {err!r}")


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


if __name__ == "__main__":
    unittest.main()
