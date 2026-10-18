"""
Tests for the read-time record (READTIME; pause READTIME-1, settled by
a2 with the message number): `tc read <name>` appends one JSON line per
message it moved to mail/to-<name>/read/.read-times, with exactly the
keys name, number and read, under the inbox lock and after the moves,
and only when this user owns read/; no message file changes; `tc peek`
writes nothing; and `tc log` prints `read <time>`, `unread` or `read,
time not recorded` on the line after each message's header line.

Model:  Claude Opus 5.5 (the READTIME lane agent), 2026-10-17
Status: unreviewed

One Linux user plays every part. Where read/ or the record must be
another user's, tc runs in process and os.fstat reports it as another
user's (test_shared.owner_patched_fstat), as the SHARED and F1 suites
report owners. Nothing here runs as a second Linux user. Each mutation
that turns a test red, and the line it turns red, is in
docs/planning/connection-routes/handoffs/READTIME.md.

@interacts  runs ../tc through tests/_root.py under a throwaway TC_ROOT
            (send, read, peek, log); makes message files, a symlink, a
            FIFO, a hard link and a folder by hand in the root's temp
            folder, and appends a torn line to a record; loads tc as a
            module (TC_ROOT set for the load and put back,
            test_shared.load_tc) and runs cmd_read and cmd_log in process
            with os.write, os.rename or os.fstat patched, or tc's
            READ_TIMES_MAX_BYTES set low, stdout and stderr captured.
            Fix round 2 (Claude Opus 5.5, unreviewed): appends a second
            line for one name to a record by hand, sets
            READ_TIMES_MAX_BYTES to a window inside a three-line record,
            and calls tc's move_record_aside in process on a read/ it
            opens. Writes nothing outside the root's temp folder.
@deps       python3 stdlib (argparse, datetime, errno, json, os, pathlib,
            pwd, re, stat, sys, time, unittest, unittest.mock);
            tests/_root.py; UmaskTestCase, load_tc and
            owner_patched_fstat from test_shared.py; run_in_process from
            test_wait_exit.py; ../tc.
@complexity O(1) per test: one root per subtest, two to six tc runs in
            each, over a mailbox of at most four messages.
@alloc      one TcRoot per subtest, removed when its context exits, and
            at most one tc module per subtest.
"""

import argparse
import datetime
import errno
import json
import os
import pathlib
import pwd
import re
import stat
import sys
import time
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
# Run as `python3 -m unittest tests.test_read_times` from the repo root,
# tests/ is not on sys.path; under discover it is. Add it once so both work.
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import _root  # noqa: E402  (needs the path line above)
from test_shared import UmaskTestCase, load_tc, owner_patched_fstat  # noqa: E402
from test_wait_exit import run_in_process  # noqa: E402

# The reader's name and a sender's, made up.
NAME = "b"
SENDER = "a"
# The record's name and mode, its three keys (a contract: DASH reads
# them), and the name a plant at it is moved to (tc's READ_TIMES_NAME,
# READ_TIMES_MODE, READ_TIMES_KEYS and PLANTED_ASIDE_NAME), written here
# rather than read from tc, so a changed constant fails a test.
RECORD = ".read-times"
RECORD_MODE = 0o640
KEYS = {"name", "number", "read"}
FIRST_ASIDE = RECORD + ".planted-1"
# What tc log prints on the line after a message's header (tc's
# READ_LINE, UNREAD_LINE and NOT_RECORDED_LINE).
READ_LINE = "read {time}"
UNREAD_LINE = "unread"
NOT_RECORDED_LINE = "read, time not recorded"
# tc read's words: a plant moved aside, a record it could not write, and
# a read by someone who does not own read/ (tc's READ_TIMES_FAILED_WORDS
# and READ_TIMES_NOT_OWNER_WORDS; the moved words are move_record_aside's
# for the read-time record).
MOVED_WORDS = ("tc read: {path} was {what} owned by {owner}, not this user's own read-time record; moved it "
               "aside to {aside}")
FAILED_WORDS = "tc read: read time not recorded for {count} ({why})"
NOT_OWNER_WORDS = ("tc read: read times for {name} are kept by {owner}, who owns {read}; none recorded for "
                   "{count}")
# How both count the messages moved, written out by hand for each count a
# test uses: one is singular, any other count plural.
COUNT_WORDS = {1: "1 message", 2: "2 messages"}
# The start of tc log's line on stderr for a record it would not read.
LOG_UNREAD_RECORD_START = "tc log: {path} not read ("
# Fix round 2 (Claude Opus 5.5, unreviewed): the start of tc log's line on
# stderr for a record past the cap, read from its tail (tc's
# READ_TIMES_TAIL_WORDS), and a read time later than any a test makes,
# for a second line written by hand.
LOG_TAIL_START = "tc log: {path} is over {limit} bytes; only its newest {limit} bytes were read"
LATER_TIME = "2099-01-01T00:00:00-05:00"
# The header line tc writes at the top of every message.
HEADER = re.compile(r"^# #(\d+) from ")
# A message name not of MESSAGE_NAME_PATTERN's form, made by hand in the
# inbox: its line's number is null.
NOT_OF_THE_FORM = "note-from-nobody.md"
# A message put in read/ by hand, with no line in the record, and its text.
BY_HAND_READ = "000009-from-a.md"
BY_HAND_TEXT = "# #9 from a to b, 2026-10-17T00:00:00-05:00\n\nput here by hand\n"
# What a crash mid-append leaves: part of a line, no newline, not JSON.
TORN = b'{"name": "0000'
# What a file outside the mailbox holds, that a link at the record's name
# leads to.
OUTSIDE_TEXT = "outside the mailbox: tc must never write or read this\n"
# The exit codes (contracts.md): done, and refused with words (a message
# tc could not move).
EXIT_OK = 0
EXIT_REFUSED = 1


def message_name(n):
    """The name tc gives message number `n` from SENDER.

    @interacts  none.
    @deps       none.
    @complexity O(1).
    @alloc      one string, returned.
    """
    return f"{n:06d}-from-{SENDER}.md"


def send(test, root, count):
    """Send `count` messages from SENDER to NAME under `root`, each asserted sent (exit 0; the first says on stderr that nobody has joined as NAME, which is not under test here).

    @interacts  `count` tc runs.
    @deps       _root.TcRoot.tc.
    @complexity O(count).
    @alloc      none past each run.
    """
    for k in range(count):
        code, out, err = root.tc("send", "--from", SENDER, "--to", NAME, f"message {k}")
        test.assertEqual(code, EXIT_OK, out + err)


def paths(root):
    """(the inbox, its read/, the record) of NAME under `root`.

    @interacts  none.
    @deps       pathlib.
    @complexity O(1).
    @alloc      three paths, returned.
    """
    box = root.path / "mail" / f"to-{NAME}"
    return box, box / "read", box / "read" / RECORD


def record_lines(record):
    """Each line of the record at `record`, parsed: a list of dicts, with a line that is not JSON kept as its raw text; None when nothing is at the name. Never raises, so a test fails on its assertion.

    @interacts  reads one file.
    @deps       json, os.
    @complexity O(r) over r bytes of the record.
    @alloc      the text and one dict per line, returned.
    """
    if not os.path.lexists(record):
        return None
    out = []
    for line in record.read_bytes().split(b"\n")[:-1]:
        try:
            out.append(json.loads(line))
        except ValueError:
            out.append(line)
    return out


def when(line):
    """The `read` time of one parsed record line as seconds since the epoch, or None when it is not a time with an offset.

    @interacts  none.
    @deps       datetime.
    @complexity O(1).
    @alloc      none.
    """
    try:
        at = datetime.datetime.fromisoformat(line["read"])
    except (KeyError, TypeError, ValueError):
        return None
    return at.timestamp() if at.tzinfo is not None else None


def after_header(out):
    """{message number: the line tc log printed just after its header line} for every header in `out`.

    @interacts  none; string work only.
    @deps       re (HEADER).
    @complexity O(n) over n characters.
    @alloc      one dict, returned.
    """
    lines = out.split("\n")
    found = {}
    for k, line in enumerate(lines):
        header = HEADER.match(line)
        if header:
            found[int(header.group(1))] = lines[k + 1] if k + 1 < len(lines) else None
    return found


def login(uid):
    """The login of user number `uid`, or the number as text, as tc's user_name gives it.

    @interacts  reads the user database.
    @deps       pwd.
    @complexity O(1).
    @alloc      one short string, returned.
    """
    try:
        return pwd.getpwuid(uid).pw_name
    except KeyError:
        return str(uid)


def read_in_process(tc):
    """Run tc read NAME in process: (code, out, err).

    @interacts  see tc's cmd_read.
    @deps       run_in_process, argparse.
    @complexity tc read's.
    @alloc      the captured text, returned.
    """
    return run_in_process(lambda: tc.cmd_read(argparse.Namespace(name=NAME)))


def log_in_process(tc):
    """Run tc log in process: (code, out, err).

    @interacts  see tc's cmd_log.
    @deps       run_in_process, argparse.
    @complexity tc log's.
    @alloc      the captured text, returned.
    """
    return run_in_process(lambda: tc.cmd_log(argparse.Namespace(last=0)))


class WriterTest(UmaskTestCase):
    """tc read writes the record: its lines, its file, its plants, its failures, and the moves it follows.

    @interacts  see the module block.
    @deps       _root.TcRoot, UmaskTestCase, load_tc, owner_patched_fstat,
                send, paths, record_lines, when, read_in_process.
    @complexity O(1) per subtest.
    @alloc      one TcRoot per subtest.
    """

    def test_a_read_of_three_writes_three_lines_each_name_right_and_one_time_with_an_offset(self):
        """Three messages read: the record holds three lines, each with exactly the keys name, number and read, the three names and numbers right, one time for all, with an offset, between a clock read just before the read and one just after; a regular file with one name, this user's, at 0640.

        Must reject a record not written, a line per message missing or
        extra, a key renamed or dropped (the contract DASH reads), a time
        without its offset or not this read's, a mode the group may write
        or may not read.

        @interacts  three sends and a read; lstats and reads the record.
        @deps       send, paths, record_lines, when; os, stat, time.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            send(self, root, 3)
            _, _, record = paths(root)
            before = time.time()
            code, out, err = root.tc("read", NAME)
            after = time.time()
            self.assertEqual((code, err), (EXIT_OK, ""), out)
            lines = record_lines(record)
            self.assertIsNotNone(lines, "tc read wrote no record")
            self.assertEqual([set(line) if isinstance(line, dict) else line for line in lines], [KEYS] * 3,
                             f"the record's lines do not carry exactly the three keys: {lines}")
            self.assertEqual([(line["name"], line["number"]) for line in lines],
                             [(message_name(n), n) for n in (1, 2, 3)])
            times = {line["read"] for line in lines}
            self.assertEqual(len(times), 1, f"one read gave its messages more than one time: {times}")
            at = when(lines[0])
            self.assertIsNotNone(at, f"the read time has no offset: {lines[0]}")
            self.assertTrue(int(before) <= at <= after, f"the read time {lines[0]['read']} is not this read's "
                                                        f"(between {before} and {after})")
            st = os.lstat(record)
            self.assertEqual((stat.S_ISREG(st.st_mode), st.st_nlink, st.st_uid, stat.S_IMODE(st.st_mode)),
                             (True, 1, os.geteuid(), RECORD_MODE))

    def test_the_number_is_the_inbox_names_and_null_for_a_name_not_of_the_form(self):
        """A message moved to a by-hand name (read/ already held its name) gets its by-hand name and the number of the name it had in its inbox; a message named NOT_OF_THE_FORM gets its name and a null number.

        Must reject a number taken from the name in read/ (null for a
        by-hand name) and a number made up for a name with none.

        @interacts  one send, a read, a second file at the read message's
                    name in the inbox and one NOT_OF_THE_FORM, made by hand,
                    and a second read; reads the record.
        @deps       send, paths, record_lines.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            send(self, root, 1)
            box, _, record = paths(root)
            self.assertEqual(root.tc("read", NAME)[0], EXIT_OK)
            (box / message_name(1)).write_text("# #1 from a to b, 2026-10-17T00:00:00-05:00\n\nagain\n")
            (box / NOT_OF_THE_FORM).write_text("no header\n")
            code, out, err = root.tc("read", NAME)
            self.assertEqual(code, EXIT_OK, err)
            lines = record_lines(record) or []
            self.assertEqual([(line["name"], line["number"]) for line in lines[1:] if isinstance(line, dict)],
                             [(f"by-hand-1-{message_name(1)}", 1), (NOT_OF_THE_FORM, None)],
                             f"the second read's lines: {lines}")

    def test_each_message_files_bytes_are_unchanged_by_the_read(self):
        """Every message's bytes in read/ after tc read equal its bytes in the inbox before.

        Must reject a read time written into a message file (its header or
        its body).

        @interacts  three sends, a read; reads each message file before and
                    after.
        @deps       send, paths.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            send(self, root, 3)
            box, read, _ = paths(root)
            before = {name: (box / name).read_bytes() for name in map(message_name, (1, 2, 3))}
            self.assertEqual(root.tc("read", NAME)[0], EXIT_OK)
            self.assertEqual({name: (read / name).read_bytes() for name in before}, before)

    def test_peek_writes_no_record_and_changes_none(self):
        """tc peek over unread mail makes no record; over an inbox whose read/ holds one, it leaves its bytes and its modify time as they were.

        Must reject a peek that marks anything read.

        @interacts  sends, a peek, a read and a second peek; lstats and
                    reads the record.
        @deps       send, paths; os.
        @complexity O(1).
        @alloc      one TcRoot per subtest.
        """
        with self.subTest(record="none yet"), _root.TcRoot() as root:
            send(self, root, 2)
            _, _, record = paths(root)
            code, out, err = root.tc("peek", NAME)
            self.assertEqual((code, err, os.path.lexists(record)), (EXIT_OK, "", False))
        with self.subTest(record="one already"), _root.TcRoot() as root:
            send(self, root, 1)
            _, _, record = paths(root)
            self.assertEqual(root.tc("read", NAME)[0], EXIT_OK)
            send(self, root, 1)
            self.assertTrue(os.path.lexists(record), "tc read wrote no record for the peek to leave alone")
            before = (record.read_bytes(), os.lstat(record).st_mtime_ns)
            code, out, err = root.tc("peek", NAME)
            self.assertEqual((code, err), (EXIT_OK, ""))
            self.assertEqual((record.read_bytes(), os.lstat(record).st_mtime_ns), before)

    def test_a_plant_at_the_records_name_is_moved_aside_never_followed_and_the_record_written(self):
        """A symlink at read/.read-times to a file outside, a FIFO, a file with a second name, and a folder: tc read exits 0, says in one line that it moved the plant aside to .read-times.planted-1, the plant sits there as it was, the record is this user's own regular file holding the read's line, and the file the link led to keeps its text and its time.

        Must reject a record written through a link (an open without
        O_NOFOLLOW): a member could aim the owner's appends at any file
        the owner may write; a read that hangs on a FIFO; a line appended
        to a file with another name; and a read that gives up on a plant.

        @interacts  per subtest: one send, the plant made by hand, a read;
                    lstats and reads the record, the aside name and the
                    link's target.
        @deps       send, paths, record_lines; os, pwd, stat.
        @complexity O(1) per subtest.
        @alloc      one TcRoot per subtest.
        """
        plants = {"a symlink": lambda record, base: record.symlink_to(base / "outside"),
                  "a FIFO": lambda record, base: os.mkfifo(record),
                  "a file with another name too (a hard link)":
                      lambda record, base: (record.write_text(""), os.link(record, base / "second-name")),
                  "a folder": lambda record, base: record.mkdir()}
        for what, plant in plants.items():
            with self.subTest(plant=what), _root.TcRoot() as root:
                send(self, root, 1)
                _, read, record = paths(root)
                outside = root.base / "outside"
                outside.write_text(OUTSIDE_TEXT)
                target_before = os.stat(outside).st_mtime_ns
                plant(record, root.base)
                kind = stat.S_IFMT(os.lstat(record).st_mode)
                code, out, err = root.tc("read", NAME)
                said = MOVED_WORDS.format(path=record, what=what, owner=login(os.geteuid()),
                                          aside=read / FIRST_ASIDE)
                self.assertEqual((code, err), (EXIT_OK, said + "\n"))
                aside = os.lstat(read / FIRST_ASIDE)
                self.assertEqual(stat.S_IFMT(aside.st_mode), kind, "the plant is not at its aside name as it was")
                st = os.lstat(record)
                self.assertEqual((stat.S_ISREG(st.st_mode), st.st_nlink, st.st_uid), (True, 1, os.geteuid()))
                self.assertEqual([line["name"] for line in record_lines(record) or [] if isinstance(line, dict)],
                                 [message_name(1)])
                self.assertEqual((outside.read_text(), os.stat(outside).st_mtime_ns), (OUTSIDE_TEXT, target_before),
                                 "the file outside the mailbox changed")

    def test_a_failed_record_write_says_so_prints_the_mail_and_exits_0(self):
        """os.write raising ENOSPC while tc read runs in process, over one message and over two: the mail still prints and moves, the exit is 0, and stderr is the one line `tc read: read time not recorded for 1 message (No space left on device)`, or `for 2 messages`.

        Must reject a read that fails, or stops printing, over a missing
        timestamp, one that says nothing, and `1 messages`.

        @interacts  per count: that many sends; tc read in process with
                    os.write patched.
        @deps       send, paths, load_tc, read_in_process, message_name;
                    errno, os, unittest.mock; COUNT_WORDS.
        @complexity O(1) per count.
        @alloc      one TcRoot and one module per count.
        """
        for n in COUNT_WORDS:
            with self.subTest(messages=n), _root.TcRoot() as root:
                send(self, root, n)
                box, read, _ = paths(root)
                tc = load_tc(root)
                full = OSError(errno.ENOSPC, os.strerror(errno.ENOSPC))
                with mock.patch.object(tc.os, "write", side_effect=full):
                    code, out, err = read_in_process(tc)
                self.assertEqual(code, EXIT_OK, err)
                self.assertEqual(err, FAILED_WORDS.format(count=COUNT_WORDS[n], why=os.strerror(errno.ENOSPC)) + "\n")
                self.assertEqual([out.count(f"message {k}") for k in range(n)], [1] * n, out)
                self.assertEqual(sorted(p.name for p in read.glob("*.md")), [message_name(k + 1) for k in range(n)])

    def test_a_member_who_does_not_own_read_records_nothing_and_says_why(self):
        """tc read run in process with read/ reported as another user's (os.fstat, as the SHARED suites report owners): the mail moves and prints, the exit is 0, no record is made, and stderr is the one NOT_OWNER_WORDS line.

        Must reject a record written by anyone but read/'s owner: in a
        shared mailbox a member's read of another name moves only that
        member's own messages, which is not the recipient picking them up.

        @interacts  two sends; tc read in process with os.fstat patched.
        @deps       send, paths, load_tc, owner_patched_fstat,
                    read_in_process, login; os, unittest.mock.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        with _root.TcRoot() as root:
            send(self, root, 2)
            box, read, record = paths(root)
            tc = load_tc(root)
            with mock.patch.object(os, "fstat", owner_patched_fstat(read)):
                code, out, err = read_in_process(tc)
            said = NOT_OWNER_WORDS.format(name=NAME, owner=login(os.geteuid() + 1), read=read, count=COUNT_WORDS[2])
            self.assertEqual((code, err), (EXIT_OK, said + "\n"))
            self.assertEqual((out.count("message 0"), out.count("message 1")), (1, 1), out)
            self.assertFalse(os.path.lexists(record), "a read by someone who does not own read/ wrote a record")

    def test_a_message_that_could_not_be_moved_gets_no_line(self):
        """Three messages, the second's move refused (os.rename patched to raise EACCES for its name alone): tc read exits 1 naming it, and the record holds lines for the first and the third only.

        Must reject a record written before the moves, or from the list
        of messages found rather than those moved: a message still unread
        would carry a read time.

        @interacts  three sends; tc read in process with os.rename wrapped.
        @deps       send, paths, load_tc, record_lines, read_in_process;
                    errno, os, unittest.mock.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        with _root.TcRoot() as root:
            send(self, root, 3)
            box, _, record = paths(root)
            tc = load_tc(root)
            real_rename = os.rename

            def rename(src, dst, *, src_dir_fd=None, dst_dir_fd=None):
                if src == message_name(2):
                    raise PermissionError(errno.EACCES, os.strerror(errno.EACCES))
                return real_rename(src, dst, src_dir_fd=src_dir_fd, dst_dir_fd=dst_dir_fd)
            with mock.patch.object(tc.os, "rename", rename):
                code, out, err = read_in_process(tc)
            self.assertEqual(code, EXIT_REFUSED, err)
            self.assertIn(message_name(2), err)
            self.assertTrue((box / message_name(2)).exists(), "the refused message left its inbox")
            self.assertEqual([line["name"] for line in record_lines(record) or [] if isinstance(line, dict)],
                             [message_name(1), message_name(3)])


    # Fix round 2 (Claude Opus 5.5, unreviewed): the review's REC-1, a forgotten record is an error, never a removal.
    def test_move_record_aside_without_its_record_raises_and_removes_nothing(self):
        """tc's move_record_aside called in process on the read-time record's name with no record spec raises TypeError, and the record keeps its bytes.

        Must reject a default spec: the wait exit record's would take
        .read-times for an earlier write's leftover .tmp, this user's own,
        and remove it.

        @interacts  one send and a read; opens read/ and calls
                    move_record_aside in process; reads the record.
        @deps       send, paths, load_tc; os.
        @complexity O(1).
        @alloc      one TcRoot, one module and one descriptor, closed.
        """
        with _root.TcRoot() as root:
            send(self, root, 1)
            self.assertEqual(root.tc("read", NAME)[0], EXIT_OK)
            _, read, record = paths(root)
            self.assertTrue(os.path.lexists(record), "tc read wrote no record to keep")
            before = record.read_bytes()
            tc = load_tc(root)
            read_fd = os.open(read, os.O_RDONLY | os.O_DIRECTORY)
            try:
                with self.assertRaises(TypeError):
                    tc.move_record_aside(read_fd, read, RECORD)
            finally:
                os.close(read_fd)
            self.assertEqual(record.read_bytes() if os.path.lexists(record) else None, before,
                             "the record is gone or changed")


class LogTest(UmaskTestCase):
    """tc log shows sent and read times: the line after each header, and a record it passes by or will not read.

    @interacts  see the module block.
    @deps       _root.TcRoot, UmaskTestCase, load_tc, owner_patched_fstat,
                send, paths, record_lines, after_header, log_in_process.
    @complexity O(1) per subtest.
    @alloc      one TcRoot per subtest.
    """

    def test_log_says_read_with_the_recorded_time_unread_or_read_time_not_recorded(self):
        """Two messages read, a third unread, and BY_HAND_READ put in read/ by hand: tc log prints `read <the recorded time>` after #1's and #2's headers, `unread` after #3's, and `read, time not recorded` after #9's; exit 0, nothing on stderr.

        Must reject a log with no read line, a time that is not the
        recorded one, unread mail called read, and a message with no line
        in the record given a time.

        @interacts  three sends, a read, one file made by hand, a log;
                    reads the record.
        @deps       send, paths, record_lines, after_header.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            send(self, root, 2)
            self.assertEqual(root.tc("read", NAME)[0], EXIT_OK)
            send(self, root, 1)
            _, read, record = paths(root)
            (read / BY_HAND_READ).write_text(BY_HAND_TEXT)
            at = (record_lines(record) or [{}])[0].get("read")
            code, out, err = root.tc("log")
            self.assertEqual((code, err), (EXIT_OK, ""), out)
            self.assertEqual(after_header(out), {1: READ_LINE.format(time=at), 2: READ_LINE.format(time=at),
                                                 3: UNREAD_LINE, 9: NOT_RECORDED_LINE}, out)

    def test_a_torn_last_line_is_passed_by_and_the_others_still_show(self):
        """TORN appended to the record after a read of two: tc log still shows both read times, exit 0, nothing on stderr; and a later read's line, appended after the torn one, shows too.

        Must reject a log that fails, or drops every time, over one line a
        crash cut short; and an append that glues its first line onto the
        torn one.

        @interacts  sends, reads and logs; appends to the record by hand.
        @deps       send, paths, record_lines, after_header.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            send(self, root, 2)
            self.assertEqual(root.tc("read", NAME)[0], EXIT_OK)
            _, _, record = paths(root)
            at = (record_lines(record) or [{}])[0].get("read")
            with open(record, "ab") as f:
                f.write(TORN)
            code, out, err = root.tc("log")
            self.assertEqual((code, err), (EXIT_OK, ""), out)
            self.assertEqual(after_header(out), {1: READ_LINE.format(time=at), 2: READ_LINE.format(time=at)}, out)
            send(self, root, 1)
            self.assertEqual(root.tc("read", NAME)[0], EXIT_OK)
            later = [line for line in record_lines(record) or [] if isinstance(line, dict)
                     and line.get("name") == message_name(3)]
            code, out, err = root.tc("log")
            self.assertEqual(len(later), 1, f"the read after the torn line wrote no line of its own: "
                                            f"{record.read_bytes()!r}")
            self.assertEqual((code, err, after_header(out).get(3)), (EXIT_OK, "", READ_LINE.format(time=later[0]["read"])))

    def test_a_record_not_the_owners_reads_as_not_recorded_with_one_line_why(self):
        """tc log in process with the record reported as another user's: each message in that read/ says `read, time not recorded`, stderr is one line naming the record, and the exit is 0.

        Must reject a record a member planted in a shared read/ believed,
        and a log that fails over it. Fix round 2 (Claude Opus 5.5,
        unreviewed): the over-the-limit case moved to its own test, since
        a record past the cap is now read from its tail.

        @interacts  two sends and a read; tc log in process with os.fstat
                    patched.
        @deps       send, paths, load_tc, owner_patched_fstat,
                    log_in_process, after_header; unittest.mock.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        with _root.TcRoot() as root:
            send(self, root, 2)
            self.assertEqual(root.tc("read", NAME)[0], EXIT_OK)
            _, _, record = paths(root)
            self.assertTrue(os.path.lexists(record), "tc read wrote no record for the log to read")
            tc = load_tc(root)
            with mock.patch.object(os, "fstat", owner_patched_fstat(record)):
                code, out, err = log_in_process(tc)
            self.assertEqual(code, EXIT_OK, err)
            self.assertEqual(after_header(out), {1: NOT_RECORDED_LINE, 2: NOT_RECORDED_LINE}, out)
            self.assertEqual(err.count("\n"), 1, err)
            self.assertTrue(err.startswith(LOG_UNREAD_RECORD_START.format(path=record)), err)

    # Fix round 2 (Claude Opus 5.5, unreviewed): the review's LOW-1, the last line for a name wins.
    def test_when_a_name_has_two_lines_the_last_one_shows(self):
        """One message read, then a second line for its name appended by hand with LATER_TIME: tc log shows `read LATER_TIME`, exit 0, nothing on stderr.

        A name can take a second line honestly: once a read message's file
        has left read/ and mail/.seq is set back, tc moves a new message in
        under the same name. Must reject a log that shows the older read.

        @interacts  one send and a read; appends to the record by hand; a
                    log.
        @deps       send, paths, after_header, message_name; json.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            send(self, root, 1)
            self.assertEqual(root.tc("read", NAME)[0], EXIT_OK)
            _, _, record = paths(root)
            self.assertTrue(os.path.lexists(record), "tc read wrote no record to append to")
            with open(record, "a") as f:
                f.write(json.dumps({"name": message_name(1), "number": 1, "read": LATER_TIME}) + "\n")
            code, out, err = root.tc("log")
            self.assertEqual((code, err), (EXIT_OK, ""), out)
            self.assertEqual(after_header(out), {1: READ_LINE.format(time=LATER_TIME)}, out)

    # Fix round 2 (Claude Opus 5.5, unreviewed): the review's DEBT-1, a record past the cap is read from its tail.
    def test_a_record_over_the_limit_shows_its_newest_times_and_says_only_they_were_read(self):
        """Three reads of one message each make three lines of one length L; tc log in process with READ_TIMES_MAX_BYTES at L + L // 2 shows #3's time and `read, time not recorded` for #1 and #2 (the partial line at the window's start is dropped); at exactly 2 L it shows #2's and #3's (a window starting on a line's first byte keeps that line). Each run: exit 0 and one stderr line saying only the newest part was read.

        Must reject a record refused whole past the cap (every time lost
        at once, for good), an unbounded read, a partial first line
        believed, and a whole first line dropped.

        @interacts  three sends and three reads; tc log in process with
                    tc's READ_TIMES_MAX_BYTES patched.
        @deps       send, paths, load_tc, log_in_process, after_header,
                    record_lines; unittest.mock.
        @complexity O(1) per subtest.
        @alloc      one TcRoot and one module per subtest.
        """
        for label, shown in (("mid-line", (3,)), ("on a line's start", (2, 3))):
            with self.subTest(window=label), _root.TcRoot() as root:
                for _ in range(3):
                    send(self, root, 1)
                    self.assertEqual(root.tc("read", NAME)[0], EXIT_OK)
                _, _, record = paths(root)
                lines = [line for line in record_lines(record) or [] if isinstance(line, dict)]
                self.assertEqual(len(lines), 3, f"three reads did not write three lines: {lines}")
                sizes = {len(raw) + 1 for raw in record.read_bytes().split(b"\n")[:-1]}
                self.assertEqual(len(sizes), 1, f"the three lines differ in length: {sizes}")
                size = sizes.pop()
                limit = size + size // 2 if len(shown) == 1 else 2 * size
                tc = load_tc(root)
                with mock.patch.object(tc, "READ_TIMES_MAX_BYTES", limit):
                    code, out, err = log_in_process(tc)
                times = {line["number"]: line["read"] for line in lines}
                want = {n: READ_LINE.format(time=times[n]) if n in shown else NOT_RECORDED_LINE for n in (1, 2, 3)}
                self.assertEqual(code, EXIT_OK, err)
                self.assertEqual(after_header(out), want, out)
                self.assertEqual(err.count("\n"), 1, err)
                self.assertTrue(err.startswith(LOG_TAIL_START.format(path=record, limit=limit)), err)


if __name__ == "__main__":
    unittest.main()
