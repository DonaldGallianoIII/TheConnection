"""
Tests for `tc flush` (SSH S2, contract C3, decisions D22, D23 and D25):
it sends this user's waiting outbox mail oldest first for each target,
stops a target on a connection failure or a far 10 so its mail stays in
order, files a far refusal in refused/ and goes on, sends only this
user's own files and counts the rest, leaves a file whose card no longer
says ssh, and shares the send lock with `tc send`, so a send and a flush
at once never send one file twice or a newer one first.

Model:  Claude Opus 5.5 (the SSH lane agent), 2026-10-15
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
            call, start `tc flush` in the background, and run `tc send`
            while it sleeps; teardown kills the flush by its own pid if it
            still runs. One test holds this user's send lock itself. One
            test moves a waiting file by hand into another member's
            outbox branch (D22, D32; SSH fix round 1, Claude Opus 5.5,
            unreviewed).
@deps       python3 stdlib (fcntl, os, pathlib, shlex, sys, time,
            unittest); tests/_root.py; LOCK_POLL_SECONDS and
            FINISH_CEILING_SECONDS from test_codex_route.py; the card,
            outbox and lock helpers from test_ssh_route.py; ../tc.
@complexity O(1) per test: two to six tc runs and as many fake calls,
            each under a second. The two concurrency tests run about
            SHORT_SLEEP_SECONDS and LONG_SLEEP_SECONDS; the held-lock test
            waits out tc's own lock bound (3 s).
@alloc      one TcRoot per test, removed when its context exits; one open
            lock file while a test holds the send lock; one background
            flush in two tests.
"""

import fcntl
import os
import pathlib
import shlex
import sys
import time
import unittest

HERE = pathlib.Path(__file__).resolve().parent
# Run as `python3 -m unittest tests.test_flush` from the repo root, tests/
# is not on sys.path; under discover it is. Add it once so both work.
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import _root  # noqa: E402  (needs the path line above)
from test_codex_route import FINISH_CEILING_SECONDS, LOCK_POLL_SECONDS  # noqa: E402
from test_ssh_route import (EXIT_BUSY, EXIT_QUEUED, FAKE_CONNECT_STDERR, OTHER_MEMBER, OTHER_TARGET,  # noqa: E402
                            SSH_CONNECT_FAILED, TARGET, assert_called, login, outbox, queue, send_lock_path)

# A far tc's refusal of a bad name (row 6), and what the fake says for it.
# Made up for the test; not a real far tc's wording.
EXIT_BAD_NAME = 6
FAKE_BAD_NAME_STDERR = "tc: bad name\n"
FAKE_BUSY_STDERR = "tc: another process is holding b's lock; try again\n"
# What flush says, written here rather than read from tc.
NOTHING_WORDS = "nothing waiting in the outbox\n"
OTHERS_WORDS = ("{k} waiting for {target} belong to other members ({names}); each member sends their own "
                "with tc flush")
NOT_SSH_WORDS = ("tc flush: left {path}: {to}'s card no longer says ssh (it says route local); it is never sent "
                 "another way. To send it over ssh, write the card again with tc card {to} --ssh <target>, then "
                 "run tc flush\n")
HELD_WORDS = "another tc is sending to it right now (a send or a tc flush)"
# How long the wrapper sleeps after the fake's first call, while the flush
# holds the send lock. Short: well under tc's LOCK_WAIT_SECONDS (3 s), so
# a send that waits for the lock gets it once the flush is done. Long:
# well past it, so the send stops waiting and queues its message, and
# the flush, still holding the lock, sends it.
SHORT_SLEEP_SECONDS = 1
LONG_SLEEP_SECONDS = 4.5
# How long a test waits for the background flush to make its first ssh
# call. Python start-up plus tc's imports is well under 1 s.
FIRST_CALL_CEILING_SECONDS = 5
# Owner may read, write and run the wrapper. Nobody else needs to.
OWN_WRAPPER_MODE = 0o700


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

    def test_a_held_send_lock_leaves_the_target_for_the_next_flush(self):
        """With this user's send lock for u@h held past tc's 3 s bound: flush runs no ssh, leaves the message with words saying why, exit 4.

        @interacts  one tc card, one send; holds the send lock; one flush;
                    then one flush with the lock let go.
        @deps       send_lock_path, assert_called, outbox; fcntl.
        @complexity O(1): about LOCK_WAIT_SECONDS (3 s).
        @alloc      one TcRoot and one open lock file.
        """
        with _root.TcRoot() as root:
            first, first_calls = root.fake_bin("ssh", SSH_CONNECT_FAILED, stderr=FAKE_CONNECT_STDERR)
            root.tc("card", "b", "--ssh", TARGET)
            root.tc("send", "--from", "a", "--to", "b", "hi")
            assert_called(self, first, first_calls)
            folder, calls = root.fake_bin("ssh", 0)
            with open(send_lock_path(root, TARGET), "a") as held:
                fcntl.flock(held, fcntl.LOCK_EX)
                code, out, err = root.tc("flush")
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
        """The flush sleeps LONG_SLEEP_SECONDS after sending #1, holding the lock; a send then stops waiting, queues #2 (exit 4), and the same flush sends #2 after #1. Each number once, in order.

        @interacts  one tc card, one send that is kept; a background flush
                    behind the slow wrapper; one send while it sleeps.
        @deps       slow_after_first_call, wait_for_first_call,
                    assert_called, origins, outbox.
        @complexity O(1): about LONG_SLEEP_SECONDS.
        @alloc      one TcRoot, one background flush.
        """
        with _root.TcRoot() as root:
            first, first_calls = root.fake_bin("ssh", SSH_CONNECT_FAILED, stderr=FAKE_CONNECT_STDERR)
            root.tc("card", "b", "--ssh", TARGET)
            root.tc("send", "--from", "a", "--to", "b", "one")
            assert_called(self, first, first_calls)
            folder, calls = root.fake_bin("ssh", 0)
            env = slow_after_first_call(root, folder, LONG_SLEEP_SECONDS)
            flush = root.start("flush", env=env)
            wait_for_first_call(self, folder, flush)
            code, out, err = root.tc("send", "--from", "a", "--to", "b", "two", env=env)
            flushed, flush_err = flush.communicate(timeout=FINISH_CEILING_SECONDS)
            sent = origins(assert_called(self, folder, calls))
            filed = (outbox(root, "b", "sent"), outbox(root, "b"))
        self.assertEqual(code, EXIT_QUEUED, err)
        self.assertIn(HELD_WORDS, err)
        self.assertEqual(flush.returncode, 0, flush_err)
        self.assertIn("#2 to b: sent over ssh", flushed)
        self.assertEqual(sent, [1, 2], "a message was sent twice, or out of order")
        self.assertEqual(filed, (["000001-from-a.md", "000002-from-a.md"], []))


if __name__ == "__main__":
    unittest.main()
