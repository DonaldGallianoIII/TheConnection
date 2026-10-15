"""
Tests for `tc flush` (SSH S2, contract C3, decisions D22, D23 and D25):
it sends this user's waiting outbox mail oldest first for each target,
stops a target on a connection failure or a far 10 so its mail stays in
order, files a far refusal in refused/ and goes on, sends only this
user's own files and counts the rest, leaves a file whose card no longer
says ssh, and shares the send lock with `tc send`, so a send and a flush
at once never send one file twice or a newer one first.

Model:  Claude Opus 5.5 (the SSH lane agent), 2026-10-15; changed in fix
        round 1 by the SSH fixer, Claude Opus 5.5, 2026-10-15
Status: unreviewed

Real ssh never runs here (rule 5). Every test that flushes puts
tests/_root.py's fake `ssh` first on PATH, asserts its record file exists
before reading it, and reads it inside the `with TcRoot()` block. A test
that asserts ssh was not called proves, in the same root, that the fake
it watched is reachable.

@interacts  runs ../tc through tests/_root.py under a throwaway TC_ROOT,
            with fake `ssh` executables that record their argv and stdin.
            Two tests put a wrapper of their own in front of the fake (in
            the root's temp folder) that sleeps after the fake's first
            call, start `tc flush` in the background, and send while it
            sleeps; teardown kills the flush by its own pid if it still
            runs. One test holds this user's send lock itself. SSH fix
            round 1 (Claude Opus 5.5, unreviewed): one test moves a
            waiting file by hand into another member's outbox branch
            (D22, D32); two write mail/.seq by hand or a file into this
            user's queue; one runs `tc flush 2>&1` through /bin/sh. Three
            tests load tc as a module (TC_ROOT set to the harness root
            first, put back after) and call cmd_flush or
            route_and_deliver in process, with PATH set for the call:
            two with SEND_LOCK_WAIT_SECONDS patched short, one with
            send_lock wrapped so a file lands as it lets go.
@deps       python3 stdlib (argparse, contextlib, fcntl, io, os, pathlib,
            shlex, sys, time, unittest, unittest.mock); tests/_root.py;
            FINISH_CEILING_SECONDS, LOCK_POLL_SECONDS and load_tc from
            test_codex_route.py; the card, outbox, lock and wording
            helpers from test_ssh_route.py; ../tc.
@complexity O(1) per test: two to six tc runs and as many fake calls,
            each under a second. The two concurrency tests run about
            SHORT_SLEEP_SECONDS and LONG_SLEEP_SECONDS; the held-lock test
            about SHORT_LOCK_WAIT_SECONDS.
@alloc      one TcRoot per test, removed when its context exits; one open
            lock file while a test holds the send lock; one background
            flush in two tests; one module in three.
"""

import argparse
import contextlib
import fcntl
import io
import os
import pathlib
import shlex
import sys
import time
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
# Run as `python3 -m unittest tests.test_flush` from the repo root, tests/
# is not on sys.path; under discover it is. Add it once so both work.
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import _root  # noqa: E402  (needs the path line above)
from test_codex_route import FINISH_CEILING_SECONDS, LOCK_POLL_SECONDS, load_tc  # noqa: E402
from test_ssh_route import (FAKE_BUSY_STDERR, FAKE_CONNECT_STDERR, OTHER_MEMBER, OTHER_TARGET,  # noqa: E402
                            OWN_WRAPPER_MODE, QUEUED_WORDS, SHORT_LOCK_WAIT_SECONDS, SSH_CONNECT_FAILED, TARGET,
                            assert_called, login, outbox, queue, send_lock_path)

# The exit table's rows flush uses, written here as every suite writes its
# own (SSH fix round 1, Claude Opus 5.5, unreviewed: the audit's LOW-19).
EXIT_QUEUED = 4
EXIT_BAD_NAME = 6
EXIT_BUSY = 10
# A far tc's refusal of a bad name (row 6), and what the fake says for it.
# Made up for the test; not a real far tc's wording.
FAKE_BAD_NAME_STDERR = "tc: bad name\n"
# What flush says, written here rather than read from tc.
NOTHING_WORDS = "nothing waiting in the outbox\n"
OTHERS_WORDS = ("{k} waiting for {target} belong to other members ({names}); each member sends their own "
                "with tc flush")
NOT_SSH_WORDS = ("tc flush: left {path}: {to}'s card no longer says ssh (it says route local); it is never sent "
                 "another way. To send it over ssh, write the card again with tc card {to} --ssh <target>, then "
                 "run tc flush\n")
HELD_WORDS = "another tc is sending to it right now (a send or a tc flush)"
# How long the wrapper sleeps after the fake's first call, while the flush
# holds the send lock. Short: well under tc's SEND_LOCK_WAIT_SECONDS (one
# ssh run), so a send that waits for the lock gets it once the flush is
# done. Long: well past SHORT_LOCK_WAIT_SECONDS, the send lock wait an
# in-process send has patched in (SSH fix round 1, Claude Opus 5.5,
# unreviewed: the audit's LOW-9), so the send stops waiting and queues
# its message, and the flush, still holding the lock, sends it.
SHORT_SLEEP_SECONDS = 1
LONG_SLEEP_SECONDS = 2.5
# How long a test waits for the background flush to make its first ssh
# call. Python start-up plus tc's imports is well under 1 s.
FIRST_CALL_CEILING_SECONDS = 5
# What flush says when `--to` names a name with no card and nothing
# waits for it (the audit's LOW-14), written here.
NOTHING_FOR_WORDS = "nothing waiting for {name}: {name} has no card now\n"


def origins(seen):
    """The outbox numbers in each recorded call's --origin id, in call order.

    @interacts  none; reads the recorded argv.
    @deps       shlex.
    @complexity O(c) over c calls.
    @alloc      one list of ints, returned.
    """
    numbers = []
    for call in seen:
        words = shlex.split(call["argv"][-1])
        numbers.append(int(words[words.index("--origin") + 1].split("-")[1]))
    return numbers


def queue_three(test, root):
    """Card b -> u@h, then three sends to b with a fake ssh exiting 255: #1 kept, #2 and #3 queued behind it, ssh run once.

    @interacts  one tc card, three sends, one fake.
    @deps       assert_called.
    @complexity O(1).
    @alloc      three outbox files.
    """
    folder, calls = root.fake_bin("ssh", SSH_CONNECT_FAILED, stderr=FAKE_CONNECT_STDERR)
    root.tc("card", "b", "--ssh", TARGET)
    for text in ("one", "two", "three"):
        code, out, err = root.tc("send", "--from", "a", "--to", "b", text)
        test.assertEqual(code, EXIT_QUEUED, err)
    test.assertEqual(len(assert_called(test, folder, calls)), 1)


def slow_after_first_call(root, folder, seconds):
    """A wrapper `ssh` that runs the fake at `folder`, then sleeps `seconds` after the fake's first call only: the env for a call that should find it.

    The wrapper reads the fake's own call counter, so the record is still
    the harness's.

    @interacts  writes slow-ssh-*/ssh (mode 0700) in the root's temp folder.
    @deps       shlex, os.
    @complexity O(1).
    @alloc      one folder, removed with the temp folder.
    """
    count = folder.parent / "calls.count"
    slow = root.base / f"slow-ssh-{len(list(root.base.glob('slow-ssh-*')))}"
    slow.mkdir()
    wrapper = slow / "ssh"
    wrapper.write_text(f'#!/bin/sh\n{shlex.quote(str(folder / "ssh"))} "$@"\ncode=$?\n'
                       f'if [ "$(cat {shlex.quote(str(count))})" = 1 ]; then sleep {seconds}; fi\nexit $code\n')
    wrapper.chmod(OWN_WRAPPER_MODE)
    return {"PATH": f"{slow}{os.pathsep}{root.env['PATH']}"}


def run_flush(tc, root, to=None):
    """Call tc.cmd_flush in process, with PATH set to the root's for the call: (exit code, stdout, stderr), 0 when it returned.

    @interacts  patches os.environ's PATH for the call; captures stdout and
                stderr.
    @deps       argparse, contextlib, io, os, unittest.mock.
    @complexity O(1), plus the flush's work.
    @alloc      the captured output, returned.
    """
    code = 0
    with mock.patch.dict(os.environ, {"PATH": root.env["PATH"]}), \
            contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()) as err:
        try:
            tc.cmd_flush(argparse.Namespace(to=to))
        except SystemExit as stop:
            code = stop.code
    return code, out.getvalue(), err.getvalue()


def wait_for_first_call(test, folder, proc):
    """Return once the fake at `folder` has recorded a call; fail `test` if `proc` exits first or the ceiling passes.

    @interacts  stats the fake's record.
    @deps       time.
    @complexity at most FIRST_CALL_CEILING_SECONDS / LOCK_POLL_SECONDS polls.
    @alloc      none.
    """
    record = folder.parent / "calls.jsonl"
    deadline = time.monotonic() + FIRST_CALL_CEILING_SECONDS
    while not record.exists():
        if proc.poll() is not None:
            test.fail(f"tc flush exited {proc.returncode} before it ran ssh")
        if time.monotonic() >= deadline:
            test.fail(f"tc flush did not run ssh within {FIRST_CALL_CEILING_SECONDS} s")
        time.sleep(LOCK_POLL_SECONDS)


class FlushTest(unittest.TestCase):
    """`tc flush` against fake ssh executables.

    @interacts  see the module block.
    @deps       _root.TcRoot, _root.TcRoot.fake_bin.
    @complexity O(1) per test.
    @alloc      one TcRoot per test.
    """

    def test_a_failure_stops_the_target_and_the_next_flush_sends_the_rest_in_order(self):
        """Three waiting, fake exiting 255 on the second: #1 to sent/, #2 and #3 stay, #3 never tried, exit 4. Fake fixed: #2 then #3, exit 0.

        Must reject a flush that skips a failure and sends the third first.

        @interacts  queue_three; two flushes, each with a fake of its own.
        @deps       queue_three, assert_called, origins, outbox.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            queue_three(self, root)
            folder, calls = root.fake_bin("ssh", [0, SSH_CONNECT_FAILED], stderr=FAKE_CONNECT_STDERR)
            code, out, err = root.tc("flush")
            first = origins(assert_called(self, folder, calls))
            after_first = (outbox(root, "b", "sent"), outbox(root, "b"))
            folder2, calls2 = root.fake_bin("ssh", 0)
            code2, out2, err2 = root.tc("flush")
            second = origins(assert_called(self, folder2, calls2))
            after_second = (outbox(root, "b", "sent"), outbox(root, "b"))
        self.assertEqual(code, EXIT_QUEUED, err)
        self.assertEqual(first, [1, 2], "the flush did not stop the target at its failure")
        self.assertEqual(after_first, (["000001-from-a.md"], ["000002-from-a.md", "000003-from-a.md"]))
        self.assertTrue(out.startswith(f"#1 to b: sent over ssh to {TARGET}"), out)
        self.assertIn(f"tc flush: #2 to b: could not reach {TARGET} ({FAKE_CONNECT_STDERR.strip()})", err)
        self.assertIn("000003-from-a.md: u@h could not be reached", err)
        self.assertEqual((code2, err2), (0, ""))
        self.assertEqual(second, [2, 3])
        self.assertEqual(after_second, (["000001-from-a.md", "000002-from-a.md", "000003-from-a.md"], []))

    def test_a_far_refusal_is_filed_with_its_stderr_and_the_flush_goes_on(self):
        """Three waiting, fake exiting 6 on the second: #2 in refused/ with the far stderr beside it, #1 and #3 sent, exit 0.

        @interacts  queue_three; one flush.
        @deps       queue_three, assert_called, origins, outbox.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            queue_three(self, root)
            folder, calls = root.fake_bin("ssh", [0, EXIT_BAD_NAME, 0], stderr=FAKE_BAD_NAME_STDERR)
            code, out, err = root.tc("flush")
            sent = origins(assert_called(self, folder, calls))
            note = queue(root, "b") / "refused" / "000002-from-a.md.stderr"
            note_text = note.read_text() if note.exists() else ""
            filed = (outbox(root, "b", "sent"), outbox(root, "b", "refused"), outbox(root, "b"))
        self.assertEqual(code, 0, err)
        self.assertEqual(sent, [1, 2, 3])
        self.assertEqual(filed, (["000001-from-a.md", "000003-from-a.md"], ["000002-from-a.md"], []))
        self.assertIn(FAKE_BAD_NAME_STDERR, note_text)
        self.assertIn(f"refused by {TARGET} (exit {EXIT_BAD_NAME})", err)

    def test_a_far_10_stops_the_target_like_255(self):
        """Three waiting, fake exiting 10 (D23): #1 tried once and kept, #2 and #3 never tried, all three waiting, exit 4.

        @interacts  queue_three; one flush.
        @deps       queue_three, assert_called, origins, outbox.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            queue_three(self, root)
            folder, calls = root.fake_bin("ssh", EXIT_BUSY, stderr=FAKE_BUSY_STDERR)
            code, out, err = root.tc("flush")
            tried = origins(assert_called(self, folder, calls))
            filed = outbox(root, "b", "sent") + outbox(root, "b", "refused")
            waiting = outbox(root, "b")
        self.assertEqual(code, EXIT_QUEUED, err)
        self.assertEqual(tried, [1])
        self.assertEqual(filed, [])
        self.assertEqual(waiting, ["000001-from-a.md", "000002-from-a.md", "000003-from-a.md"])
        self.assertIn(f"the far tc was busy, exit {EXIT_BUSY}", err)

    def test_only_this_users_own_files_are_sent_and_the_others_are_counted(self):
        """D22, D32: with #1 moved into another member's branch (outbox/ben-member/to-b/), flush sends only #2 and says 1 waiting for u@h belongs to other members, named by the file's owner; #1 stays; exit 0.

        SSH fix round 1 (Claude Opus 5.5, unreviewed): each member's queue
        is a branch of their own, so the other member's file is moved by
        hand into the branch that member's send would have made. One
        Linux user cannot make a file another user owns, so the owner
        named is the running user. The two-user walk is
        qa/human/route-shared.md's.

        @interacts  one tc card, two sends (kept, then queued), one rename
                    by hand, one flush.
        @deps       queue, assert_called, origins, outbox, login; os.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            first, first_calls = root.fake_bin("ssh", SSH_CONNECT_FAILED, stderr=FAKE_CONNECT_STDERR)
            root.tc("card", "b", "--ssh", TARGET)
            root.tc("send", "--from", "a", "--to", "b", "bob's")
            root.tc("send", "--from", "a", "--to", "b", "alice's")
            assert_called(self, first, first_calls)
            theirs = root.path / "outbox" / OTHER_MEMBER / "to-b" / "000001-from-a.md"
            theirs.parent.mkdir(parents=True)
            os.rename(queue(root, "b") / theirs.name, theirs)
            folder, calls = root.fake_bin("ssh", 0)
            code, out, err = root.tc("flush")
            sent = origins(assert_called(self, folder, calls))
            waiting = sorted(p.name for p in theirs.parent.glob("*.md"))
        self.assertEqual(code, 0, err)
        self.assertEqual(sent, [2])
        self.assertEqual(waiting, ["000001-from-a.md"])
        self.assertIn(OTHERS_WORDS.format(k=1, target=TARGET, names=login()), out)
        self.assertEqual(err, "")

    def test_a_file_whose_card_no_longer_says_ssh_stays_and_is_never_sent_another_way(self):
        """A message waits for b; b then joins here (route local). flush leaves it, names why and the fix, exit 4; nothing lands in mail/to-b; ssh never runs.

        @interacts  one tc card, one send, one join, one flush, then one
                    send to another target to prove the fake reachable.
        @deps       assert_called, outbox.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            first, first_calls = root.fake_bin("ssh", SSH_CONNECT_FAILED, stderr=FAKE_CONNECT_STDERR)
            root.tc("card", "b", "--ssh", TARGET)
            root.tc("send", "--from", "a", "--to", "b", "for the far b")
            assert_called(self, first, first_calls)
            root.tc("join", "b")
            folder, calls = root.fake_bin("ssh", 0)
            code, out, err = root.tc("flush")
            not_called = not (folder.parent / "calls.jsonl").exists()
            delivered = sorted((root.path / "mail" / "to-b").glob("*.md"))
            waiting = outbox(root, "b")
            path = queue(root, "b") / "000001-from-a.md"
            root.tc("card", "c", "--ssh", OTHER_TARGET)
            root.tc("send", "--from", "a", "--to", "c", "hi")
            reachable = len(assert_called(self, folder, calls))
        self.assertEqual((code, out), (EXIT_QUEUED, ""), err)
        self.assertEqual(err, NOT_SSH_WORDS.format(path=path, to="b"))
        self.assertTrue(not_called, "flush ran ssh for a card that says local")
        self.assertEqual(delivered, [], "flush delivered an outbox message by another route")
        self.assertEqual(waiting, ["000001-from-a.md"])
        self.assertEqual(reachable, 1)

    def test_flush_to_a_name_sends_only_the_queue_of_its_target(self):
        """b -> u@h and c -> u@h2, one waiting each: `tc flush --to b` sends b's only, says nothing of c's, exit 0; c's stays.

        @interacts  two tc cards, two sends, one flush.
        @deps       assert_called, origins, outbox.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            first, first_calls = root.fake_bin("ssh", SSH_CONNECT_FAILED, stderr=FAKE_CONNECT_STDERR)
            root.tc("card", "b", "--ssh", TARGET)
            root.tc("card", "c", "--ssh", OTHER_TARGET)
            root.tc("send", "--from", "a", "--to", "b", "one")
            root.tc("send", "--from", "a", "--to", "c", "two")
            assert_called(self, first, first_calls)
            folder, calls = root.fake_bin("ssh", 0)
            code, out, err = root.tc("flush", "--to", "b")
            seen = assert_called(self, folder, calls)
            waiting = (outbox(root, "b"), outbox(root, "c"))
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(origins(seen), [1])
        self.assertEqual(seen[0]["argv"][-2], TARGET)
        self.assertEqual(waiting, ([], ["000002-from-a.md"]))
        self.assertNotIn("to c", out)

    def test_nothing_waiting_says_so_and_exits_0(self):
        """An empty outbox (or none at all): `nothing waiting in the outbox`, exit 0, ssh never run.

        @interacts  one flush; one send to prove the fake reachable.
        @deps       assert_called.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("ssh", 0)
            got = root.tc("flush")
            not_called = not (folder.parent / "calls.jsonl").exists()
            root.tc("card", "b", "--ssh", TARGET)
            root.tc("send", "--from", "a", "--to", "b", "hi")
            reachable = len(assert_called(self, folder, calls))
        self.assertEqual(got, (0, NOTHING_WORDS, ""))
        self.assertTrue(not_called)
        self.assertEqual(reachable, 1)

    def test_a_newer_message_a_set_back_counter_numbered_lower_still_waits_behind_the_older(self):
        """mail/.seq at 4: #5 is kept (ssh failing). mail/.seq set back to 1: the next send takes #2, queues behind #5 without running ssh (exit 4, one waiting); the flush then sends #5 before #2.

        SSH fix round 1 (Claude Opus 5.5, unreviewed): the audit's LOW-7.
        Must reject a queue that counts only lower numbers (the send would
        go ahead of #5) and a flush that orders by number alone (#2 first).

        @interacts  one tc card, two writes of mail/.seq by hand, two sends,
                    one flush, two fakes.
        @deps       assert_called, origins.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            down, down_calls = root.fake_bin("ssh", SSH_CONNECT_FAILED, stderr=FAKE_CONNECT_STDERR)
            root.tc("card", "b", "--ssh", TARGET)
            seq = root.path / "mail" / ".seq"
            seq.parent.mkdir(exist_ok=True)
            seq.write_text("4")
            first = root.tc("send", "--from", "a", "--to", "b", "first")
            assert_called(self, down, down_calls)
            seq.write_text("1")
            folder, calls = root.fake_bin("ssh", 0)
            second = root.tc("send", "--from", "a", "--to", "b", "second")
            not_called = not (folder.parent / "calls.jsonl").exists()
            flushed = root.tc("flush")
            order = origins(assert_called(self, folder, calls))
        self.assertEqual(first[0], EXIT_QUEUED, first)
        self.assertEqual(second, (EXIT_QUEUED, "", QUEUED_WORDS.format(target=TARGET, n=1)))
        self.assertTrue(not_called, "the newer message went ahead of the older one")
        self.assertEqual(flushed[0], 0, flushed)
        self.assertEqual(order, [5, 2], "the flush sent the newer message first")

    def test_a_file_published_once_the_flush_lets_go_of_its_target_never_reads_as_left(self):
        """In process, send_lock wrapped so that a send publishes #9 the moment the flush lets go of u@h's lock: the flush sends #1, exits 0, and says nothing of #9, which waits for its own send.

        SSH fix round 1 (Claude Opus 5.5, unreviewed): the audit's LOW-13,
        option B. Must reject a final listing made after the lock is let
        go, which read the waiting send's file as `left ...: it came in
        after this flush looked` and exited 4.

        @interacts  one tc card, one send that is kept; loads tc and calls
                    cmd_flush once with send_lock wrapped to write one
                    file by hand into this user's queue as it lets go.
        @deps       load_tc, run_flush, queue, assert_called, origins,
                    outbox; contextlib, unittest.mock.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        with _root.TcRoot() as root:
            first, first_calls = root.fake_bin("ssh", SSH_CONNECT_FAILED, stderr=FAKE_CONNECT_STDERR)
            root.tc("card", "b", "--ssh", TARGET)
            root.tc("send", "--from", "a", "--to", "b", "one")
            assert_called(self, first, first_calls)
            folder, calls = root.fake_bin("ssh", 0)
            tc = load_tc(root)
            real, late = tc.send_lock, queue(root, "b") / "000009-from-a.md"

            @contextlib.contextmanager
            def lets_go_then_a_send_publishes(target):
                with real(target) as got:
                    yield got
                late.write_text("# #9 from a to b, published by a send that waited for the lock\n\nlate\n")
            with mock.patch.object(tc, "send_lock", lets_go_then_a_send_publishes):
                code, out, err = run_flush(tc, root)
            sent = origins(assert_called(self, folder, calls))
            waiting = outbox(root, "b")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(sent, [1])
        self.assertEqual(waiting, ["000009-from-a.md"])

    def test_flush_to_a_name_with_no_card_and_nothing_waiting_says_so_for_that_name(self):
        """b's message waits; `tc flush --to far-bb`, a name with no card: `nothing waiting for far-bb: far-bb has no card now`, exit 0, no ssh; b's message still waits, and a plain flush sends it.

        SSH fix round 1 (Claude Opus 5.5, unreviewed): the audit's LOW-14.
        Must reject `nothing waiting in the outbox` there: a mistyped name
        read as an empty outbox.

        @interacts  one tc card, one send that is kept, two flushes.
        @deps       assert_called, outbox.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            first, first_calls = root.fake_bin("ssh", SSH_CONNECT_FAILED, stderr=FAKE_CONNECT_STDERR)
            root.tc("card", "b", "--ssh", TARGET)
            root.tc("send", "--from", "a", "--to", "b", "one")
            assert_called(self, first, first_calls)
            folder, calls = root.fake_bin("ssh", 0)
            got = root.tc("flush", "--to", "far-bb")
            not_called = not (folder.parent / "calls.jsonl").exists()
            waiting = outbox(root, "b")
            again = root.tc("flush")
            reachable = len(assert_called(self, folder, calls))
        self.assertEqual(got, (0, NOTHING_FOR_WORDS.format(name="far-bb"), ""))
        self.assertTrue(not_called)
        self.assertEqual(waiting, ["000001-from-a.md"])
        self.assertEqual(again[0], 0, again)
        self.assertEqual(reachable, 1)

    def test_flushs_lines_keep_their_order_when_stdout_and_stderr_are_merged(self):
        """Three waiting, the fake exiting 255 on the second, `tc flush 2>&1` through a pipe: the sent line for #1 comes first, then #2's could-not-reach line, then #3's left line, as they happened; exit 4.

        SSH fix round 1 (Claude Opus 5.5, unreviewed): the audit's LOW-15.
        Must reject stdout left block-buffered under a pipe, which put #1's
        line after the rest.

        @interacts  queue_three; one flush run through /bin/sh with stderr
                    sent to stdout.
        @deps       queue_three, assert_called; _root.TcRoot.start,
                    _root.TC; shlex, sys.
        @complexity O(1).
        @alloc      one TcRoot and one background child, reaped here.
        """
        with _root.TcRoot() as root:
            queue_three(self, root)
            folder, calls = root.fake_bin("ssh", [0, SSH_CONNECT_FAILED])
            proc = root.start(argv=["/bin/sh", "-c", f"{shlex.quote(sys.executable)} "
                                                     f"{shlex.quote(str(_root.TC))} flush 2>&1"])
            merged, _ = proc.communicate(timeout=FINISH_CEILING_SECONDS)
            assert_called(self, folder, calls)
        lines = merged.splitlines()
        self.assertEqual(proc.returncode, EXIT_QUEUED, merged)
        self.assertEqual(len(lines), 3, merged)
        self.assertTrue(lines[0].startswith(f"#1 to b: sent over ssh to {TARGET}"), merged)
        self.assertTrue(lines[1].startswith(f"tc flush: #2 to b: could not reach {TARGET}"), merged)
        self.assertTrue(lines[2].startswith("tc flush: left "), merged)

    def test_a_held_send_lock_leaves_the_target_for_the_next_flush(self):
        """In process, SEND_LOCK_WAIT_SECONDS patched short: with this user's send lock for u@h held past it, flush runs no ssh, leaves the message with words saying why, exit 4.

        SSH fix round 1 (Claude Opus 5.5, unreviewed): the bound is one ssh
        run now (the audit's LOW-9), so it is patched down here instead of
        waited out.

        @interacts  one tc card, one send; holds the send lock; loads tc and
                    calls cmd_flush once in process with PATH set to the
                    fake's and SEND_LOCK_WAIT_SECONDS patched; then one
                    flush as a command with the lock let go.
        @deps       load_tc, run_flush, send_lock_path, assert_called,
                    outbox; fcntl, unittest.mock.
        @complexity O(1): about SHORT_LOCK_WAIT_SECONDS.
        @alloc      one TcRoot, one module and one open lock file.
        """
        with _root.TcRoot() as root:
            first, first_calls = root.fake_bin("ssh", SSH_CONNECT_FAILED, stderr=FAKE_CONNECT_STDERR)
            root.tc("card", "b", "--ssh", TARGET)
            root.tc("send", "--from", "a", "--to", "b", "hi")
            assert_called(self, first, first_calls)
            folder, calls = root.fake_bin("ssh", 0)
            tc = load_tc(root)
            with open(send_lock_path(root, TARGET), "a") as held, \
                    mock.patch.object(tc, "SEND_LOCK_WAIT_SECONDS", SHORT_LOCK_WAIT_SECONDS):
                fcntl.flock(held, fcntl.LOCK_EX)
                code, out, err = run_flush(tc, root)
            not_called = not (folder.parent / "calls.jsonl").exists()
            waiting = outbox(root, "b")
            again = root.tc("flush")
            reachable = len(assert_called(self, folder, calls))
        self.assertEqual(code, EXIT_QUEUED, err)
        self.assertIn(f"000001-from-a.md: {HELD_WORDS}", err)
        self.assertTrue(not_called, "flush ran ssh without the send lock")
        self.assertEqual(waiting, ["000001-from-a.md"])
        self.assertEqual(again[0], 0, again)
        self.assertEqual(reachable, 1)


class FlushAndSendAtOnceTest(unittest.TestCase):
    """A send while a flush holds the send lock (lane note 5): never a newer file first, never one file twice.

    @interacts  see the module block.
    @deps       _root.TcRoot, _root.TcRoot.fake_bin, _root.TcRoot.start.
    @complexity O(1) per test.
    @alloc      one TcRoot and one background flush per test.
    """

    def test_a_send_that_waits_for_a_running_flush_is_sent_once_after_it(self):
        """The flush sleeps SHORT_SLEEP_SECONDS after sending #1, holding the lock; a send then waits, publishes #2 once the flush lets go, and sends it itself. Each number is sent once, in order.

        Must reject a send that publishes before it waits for the lock:
        the flush would find #2 and send it, and the send would then send
        it again (calls 1, 2, 2).

        @interacts  one tc card, one send that is kept; a background flush
                    behind the slow wrapper; one send while it sleeps.
        @deps       slow_after_first_call, wait_for_first_call,
                    assert_called, origins, outbox.
        @complexity O(1): about SHORT_SLEEP_SECONDS.
        @alloc      one TcRoot, one background flush.
        """
        with _root.TcRoot() as root:
            first, first_calls = root.fake_bin("ssh", SSH_CONNECT_FAILED, stderr=FAKE_CONNECT_STDERR)
            root.tc("card", "b", "--ssh", TARGET)
            root.tc("send", "--from", "a", "--to", "b", "one")
            assert_called(self, first, first_calls)
            folder, calls = root.fake_bin("ssh", 0)
            env = slow_after_first_call(root, folder, SHORT_SLEEP_SECONDS)
            flush = root.start("flush", env=env)
            wait_for_first_call(self, folder, flush)
            code, out, err = root.tc("send", "--from", "a", "--to", "b", "two", env=env)
            flushed, flush_err = flush.communicate(timeout=FINISH_CEILING_SECONDS)
            sent = origins(assert_called(self, folder, calls))
            filed = (outbox(root, "b", "sent"), outbox(root, "b"))
        self.assertEqual(flush.returncode, 0, flush_err)
        self.assertEqual(code, 0, err)
        self.assertEqual(sent, [1, 2], "a message was sent twice, or out of order")
        self.assertEqual(filed, (["000001-from-a.md", "000002-from-a.md"], []))

    def test_a_send_that_queues_while_a_flush_runs_is_sent_by_that_flush_in_order(self):
        """The flush sleeps LONG_SLEEP_SECONDS after sending #1, holding the lock; a send in process, its send lock wait patched to SHORT_LOCK_WAIT_SECONDS, then stops waiting, queues #2 (exit 4), and the same flush sends #2 after #1. Each number once, in order.

        SSH fix round 1 (Claude Opus 5.5, unreviewed): a send waits one ssh
        run for the lock now (the audit's LOW-9), so the send runs in
        process with that wait patched down.

        @interacts  one tc card, one send that is kept; a background flush
                    behind the slow wrapper; loads tc and calls
                    route_and_deliver while the flush sleeps, with PATH set
                    to the wrapper's and SEND_LOCK_WAIT_SECONDS patched.
        @deps       slow_after_first_call, wait_for_first_call, load_tc,
                    assert_called, origins, outbox; unittest.mock.
        @complexity O(1): about LONG_SLEEP_SECONDS.
        @alloc      one TcRoot, one module, one background flush.
        """
        with _root.TcRoot() as root:
            first, first_calls = root.fake_bin("ssh", SSH_CONNECT_FAILED, stderr=FAKE_CONNECT_STDERR)
            root.tc("card", "b", "--ssh", TARGET)
            root.tc("send", "--from", "a", "--to", "b", "one")
            assert_called(self, first, first_calls)
            folder, calls = root.fake_bin("ssh", 0)
            env = slow_after_first_call(root, folder, LONG_SLEEP_SECONDS)
            tc = load_tc(root)
            flush = root.start("flush", env=env)
            wait_for_first_call(self, folder, flush)
            with mock.patch.dict(os.environ, env), \
                    mock.patch.object(tc, "SEND_LOCK_WAIT_SECONDS", SHORT_LOCK_WAIT_SECONDS):
                got = tc.route_and_deliver("a", "b", "two")
            flushed, flush_err = flush.communicate(timeout=FINISH_CEILING_SECONDS)
            sent = origins(assert_called(self, folder, calls))
            filed = (outbox(root, "b", "sent"), outbox(root, "b"))
        self.assertEqual(got.exit, EXIT_QUEUED, got)
        self.assertIn(HELD_WORDS, got.words)
        self.assertEqual(flush.returncode, 0, flush_err)
        self.assertIn("#2 to b: sent over ssh", flushed)
        self.assertEqual(sent, [1, 2], "a message was sent twice, or out of order")
        self.assertEqual(filed, (["000001-from-a.md", "000002-from-a.md"], []))


if __name__ == "__main__":
    unittest.main()
