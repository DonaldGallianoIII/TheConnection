"""
Tests for the ssh route (SSH S1, contract C3, decisions D13, D22, D23 and
D25): `tc send` to an ssh card publishes the message in the outbox, runs
ssh once with C3's argv and the body on stdin, and files the message by
the far tc's answer: sent/ on 0, kept on 255, a timeout or a far 10,
refused/ on any other code. A target with a queue gets no ssh run.

Model:  Claude Opus 5.5 (the SSH lane agent), 2026-10-15
Status: unreviewed

Real ssh never runs here (rule 5). Every test that sends puts
tests/_root.py's fake `ssh` first on PATH, asserts its record file exists
before reading it, and reads it inside the `with TcRoot()` block. A test
that asserts ssh was not called proves, in the same root, that the fake
it watched is reachable.

@interacts  runs ../tc through tests/_root.py under a throwaway TC_ROOT,
            with a fake `ssh` that records its argv and stdin. Some tests
            write a card by hand into cards/. Some hold this user's send
            lock (outbox/.send-<uid>-<key>.lock) themselves and read
            /proc/locks to see a child blocked on it. Four tests load tc
            as a module (TC_ROOT set to the harness root first, put back
            after) and work in process, under the root only: one calls
            route_and_deliver with PATH set for that call to a wrapper
            that runs the fake and then sleeps, and SSH_SEND_SECONDS
            patched down; one calls it with owned_by_me patched so one
            file counts as another member's (D22); one calls it with
            deliver_ssh swapped for a recorder and lock_deadline for a
            fixed value; one plants a file in sent/ and calls file_away.
            One class
            shares the mailbox with the user's own primary group (tc init
            --shared) and reads modes and groups.
@deps       python3 stdlib (fcntl, hashlib, json, os, pathlib, re, shlex,
            stat, subprocess, sys, unittest, unittest.mock); tests/_root.py;
            load_tc, wait_until_blocked and FINISH_CEILING_SECONDS from
            test_codex_route.py; UmaskTestCase and primary_group from
            test_shared.py; ../tc.
@complexity O(1) per test: one to five tc runs and as many fake calls,
            each under a second. Two tests wait out tc's own lock bound
            (LOCK_WAIT_SECONDS, 3 s), and the timeout test SHORT_SEND_SECONDS.
@alloc      one TcRoot per test, removed when its context exits; one open
            lock file while a test holds the send lock.
"""

import fcntl
import hashlib
import json
import os
import pathlib
import re
import shlex
import stat
import subprocess
import sys
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
# Run as `python3 -m unittest tests.test_ssh_route` from the repo root,
# tests/ is not on sys.path; under discover it is. Add it once so both work.
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import _root  # noqa: E402  (needs the path line above)
from test_codex_route import FINISH_CEILING_SECONDS, load_tc, wait_until_blocked  # noqa: E402
from test_shared import UmaskTestCase, primary_group  # noqa: E402

# C3's argv before the target, written here rather than read from tc:
# no tty, never a password prompt, the connect timeout (SSH_CONNECT_SECONDS,
# 10), and `--` right before the target.
SSH_ARGV_HEAD = ["-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "--"]
TARGET = "u@h"
OTHER_TARGET = "u@h2"
DEFAULT_REMOTE_TC = "~/TheConnection/tc"
# The exit table's rows this route uses.
EXIT_QUEUED = 4
EXIT_BAD_NAME = 6
EXIT_GATE_REFUSED = 7
EXIT_BUSY = 10
SSH_CONNECT_FAILED = 255
# C3's words, written here.
SENT_WORDS = "sent over ssh to {target}"
KEPT_WORDS = "could not reach {target} ({reason}); kept in outbox: {path}. Run: tc flush\n"
QUEUED_WORDS = "{target} has {n} waiting in the outbox; queued behind them. Run: tc flush\n"
NOT_TRIED_WORDS = ("{target} was not tried: another tc is sending to it right now (a send or a tc flush); "
                   "kept in outbox: {path}. Run: tc flush\n")
# What the fake ssh says on stderr for each failure. Made up for the test;
# not real ssh's or a real far tc's wording.
FAKE_CONNECT_STDERR = "ssh: connect to host h port 22: Connection refused\n"
FAKE_BUSY_STDERR = "tc: another process is holding b's lock; try again\n"
FAKE_REFUSED_STDERR = "tc gate: refused\n"
# D25's origin id: 32 hex digits of the mailbox's token, the outbox number,
# the sender.
TOKEN_PATTERN = re.compile(r"[0-9a-f]{32}")
# The send lock's name: this user's id and the start of the target's
# sha256 in hex (tc's SEND_LOCK_KEY_CHARS, written here).
SEND_LOCK_KEY_CHARS = 16
# The shared modes C4 and D22 want for the outbox, written here: each
# outbox/to-<name>/ and its sent/ and refused/ sticky like the top folders,
# and every file in them the owner's alone to write.
STICKY_FOLDER_MODE = 0o3775
OWNED_FILE_MODE = 0o640
# The timeout test: tc's SSH_SEND_SECONDS patched down to this, and the
# wrapper's sleep after the fake has recorded its call, well past it. The
# wrapper execs the sleep, so the kill at the timeout ends it.
SHORT_SEND_SECONDS = 2
SLOW_SLEEP_SECONDS = 30
# Owner may read, write and run the slow wrapper. Nobody else needs to.
OWN_WRAPPER_MODE = 0o700


def write_card(root, name, card):
    """Write cards/<name>.json by hand, as a person could.

    @interacts  makes cards/ when missing; writes one file.
    @deps       json, pathlib.
    @complexity O(1).
    @alloc      one JSON string, freed on return.
    """
    (root.path / "cards").mkdir(exist_ok=True)
    (root.path / "cards" / f"{name}.json").write_text(json.dumps(card))


def ssh_card(name, target=TARGET, tc=DEFAULT_REMOTE_TC):
    """A hand-made ssh card for `name`, as tc card writes one, with `target` and `tc` as given.

    @interacts  none.
    @deps       none.
    @complexity O(1).
    @alloc      one dict, returned.
    """
    return {"version": 1, "name": name, "kind": "other", "account": "unknown", "route": "ssh",
            "session_id": None, "pid": None, "thread_id": None, "ssh": {"target": target, "tc": tc},
            "reports_to": None, "joined_at": "2026-10-15T00:00:00+00:00"}


def outbox(root, to, folder=None):
    """The *.md names directly in outbox/to-<to>/ (or its `folder`), sorted; [] when it is not there.

    @interacts  lists one folder.
    @deps       pathlib.
    @complexity O(f) over f files there (a handful).
    @alloc      one list, returned.
    """
    box = root.path / "outbox" / f"to-{to}"
    if folder is not None:
        box = box / folder
    return sorted(p.name for p in box.glob("*.md"))


def token_of(root):
    """This root's origin token, from outbox/.origin-token.

    @interacts  reads one file.
    @deps       pathlib.
    @complexity O(1).
    @alloc      one string, returned.
    """
    return (root.path / "outbox" / ".origin-token").read_text().strip()


def remote_command(root, n, sender, to, tc=DEFAULT_REMOTE_TC):
    """The remote command C3 and D25 want for message `n` from `sender` to `to`, with a remote tc path that needs no quoting past a bare ~/.

    @interacts  reads the root's origin token.
    @deps       token_of.
    @complexity O(1).
    @alloc      one string, returned.
    """
    return f"{tc} send --from {sender} --to {to} --origin {token_of(root)}-{n}-{sender}"


def send_lock_path(root, target):
    """This user's send lock for `target` under this root: outbox/.send-<uid>-<key>.lock.

    @interacts  reads this process's user id.
    @deps       hashlib, os.
    @complexity O(t) over t characters of the target.
    @alloc      one path, returned.
    """
    key = hashlib.sha256(target.encode()).hexdigest()[:SEND_LOCK_KEY_CHARS]
    return root.path / "outbox" / f".send-{os.geteuid()}-{key}.lock"


def assert_called(test, folder, calls):
    """The fake's calls, after asserting its record file exists (the harness's rule: never read a record that may not be there).

    @interacts  stats and reads the fake's record.
    @deps       pathlib.
    @complexity O(B) over B bytes recorded.
    @alloc      one list of dicts, returned.
    """
    record = folder.parent / "calls.jsonl"
    test.assertTrue(record.exists(), f"{record} missing: the fake ssh never ran")
    return calls()


class SshRouteTest(unittest.TestCase):
    """deliver_ssh through `tc send`, against a fake ssh.

    @interacts  see the module block.
    @deps       _root.TcRoot, _root.TcRoot.fake_bin.
    @complexity O(1) per test.
    @alloc      one TcRoot per test.
    """

    def test_the_argv_is_c3s_and_the_body_goes_on_stdin(self):
        """Fake ssh exiting 0: argv is exactly C3's, -T present, `--` right before the target, the body on stdin and on no argv word; exit 0; the message in sent/ with its origin id on argv.

        Must reject the body on the command line, and a send with no
        --origin (D25).

        @interacts  one tc card, one send, one fake call.
        @deps       assert_called, remote_command, outbox, token_of.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        body = "hello over ssh; $(echo not run)"
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("ssh", 0)
            root.tc("card", "b", "--ssh", TARGET)
            code, out, err = root.tc("send", "--from", "a", "--to", "b", body)
            seen = assert_called(self, folder, calls)
            want = SSH_ARGV_HEAD + [TARGET, remote_command(root, 1, "a", "b")]
            token = token_of(root)
            sent, waiting = outbox(root, "b", "sent"), outbox(root, "b")
            text = (root.path / "outbox" / "to-b" / "sent" / "000001-from-a.md").read_text()
        self.assertEqual((code, err), (0, ""), err)
        self.assertEqual(out, SENT_WORDS.format(target=TARGET) + "\n")
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0]["argv"], want)
        self.assertEqual(seen[0]["argv"].index("--") + 1, seen[0]["argv"].index(TARGET))
        self.assertEqual(seen[0]["stdin"], body + "\n")
        self.assertFalse(any("hello" in word for word in seen[0]["argv"]), "the body is on ssh's command line")
        self.assertTrue(TOKEN_PATTERN.fullmatch(token), token)
        self.assertEqual((sent, waiting), (["000001-from-a.md"], []))
        self.assertTrue(text.startswith("# #1 from a to b, "), text)
        self.assertTrue(text.endswith(f"\n\n{body}\n"), text)

    def test_a_card_from_tc_card_is_sent_over_ssh_now_the_route_is_built(self):
        """`tc card x --ssh u@h` says no not-built note, and a send to x reaches the fake (once tests/test_router.py's not-built case).

        @interacts  one tc card, one send, one fake call.
        @deps       assert_called.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("ssh", 0)
            card = root.tc("card", "x", "--ssh", TARGET)
            code, out, err = root.tc("send", "--from", "a", "--to", "x", "hi")
            seen = assert_called(self, folder, calls)
        self.assertEqual(card[0], 0)
        self.assertEqual(card[2], "", "tc card still says the ssh route is not built")
        self.assertEqual(code, 0, err)
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0]["argv"][len(SSH_ARGV_HEAD)], TARGET)

    def test_a_name_with_a_quote_is_refused_before_ssh_runs(self):
        """--to or --from holding a quote: exit 6 by C0, nothing in the outbox, the fake never called; then a good send reaches it.

        @interacts  one tc card, three sends, one fake call.
        @deps       assert_called.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("ssh", 0)
            root.tc("card", "b", "--ssh", TARGET)
            bad_to = root.tc("send", "--from", "a", "--to", "b'x", "hi")
            bad_from = root.tc("send", "--from", "a'x", "--to", "b", "hi")
            record = folder.parent / "calls.jsonl"
            called_before = record.exists()
            outbox_before = (root.path / "outbox").exists()
            good = root.tc("send", "--from", "a", "--to", "b", "hi")
            seen = assert_called(self, folder, calls)
        self.assertEqual(bad_to[0], EXIT_BAD_NAME, bad_to)
        self.assertEqual(bad_from[0], EXIT_BAD_NAME, bad_from)
        self.assertFalse(called_before, "ssh ran for a name C0 refuses")
        self.assertFalse(outbox_before, "a refused name wrote to the outbox")
        self.assertEqual(good[0], 0, good)
        self.assertEqual(len(seen), 1)

    def test_a_remote_path_goes_bare_after_a_tilde_slash_and_is_quoted_as_one_word(self):
        """The default path is `~/TheConnection/tc` as is; `~/my dir/tc` is `~/'my dir/tc'`; `/opt/it's/tc` reaches the far shell as one word.

        Must reject a remote command built by string joining without
        shlex: the quote would split the path, and the space would make
        two words of it.

        @interacts  three hand-made cards, three sends, three fake calls.
        @deps       write_card, ssh_card, assert_called, token_of; shlex.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("ssh", 0)
            write_card(root, "b", ssh_card("b"))
            write_card(root, "c", ssh_card("c", tc="~/my dir/tc"))
            write_card(root, "d", ssh_card("d", tc="/opt/it's/tc"))
            for to in ("b", "c", "d"):
                code, out, err = root.tc("send", "--from", "a", "--to", to, "hi")
                self.assertEqual(code, 0, err)
            seen = assert_called(self, folder, calls)
            token = token_of(root)
        remotes = [call["argv"][-1] for call in seen]
        self.assertEqual(remotes[0], f"~/TheConnection/tc send --from a --to b --origin {token}-1-a")
        self.assertEqual(remotes[1], f"~/'my dir/tc' send --from a --to c --origin {token}-2-a")
        words = shlex.split(remotes[2])
        self.assertEqual(words, ["/opt/it's/tc", "send", "--from", "a", "--to", "d", "--origin", f"{token}-3-a"])

    def test_a_hand_made_card_with_a_tilde_user_path_or_a_dash_target_exits_6_and_ssh_never_runs(self):
        """A card whose tc is `~bob/tc` or `~`, or whose target is `-oProxyCommand=x`: exit 6, nothing written to the outbox, the fake never called (D13); then a good card reaches it.

        @interacts  three hand-made cards, four sends, one fake call.
        @deps       write_card, ssh_card, assert_called.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("ssh", 0)
            write_card(root, "b", ssh_card("b", tc="~bob/tc"))
            write_card(root, "c", ssh_card("c", tc="~"))
            write_card(root, "d", ssh_card("d", target="-oProxyCommand=x"))
            refused = [root.tc("send", "--from", "a", "--to", to, "hi") for to in ("b", "c", "d")]
            called_before = (folder.parent / "calls.jsonl").exists()
            outbox_before = (root.path / "outbox").exists()
            write_card(root, "e", ssh_card("e"))
            good = root.tc("send", "--from", "a", "--to", "e", "hi")
            seen = assert_called(self, folder, calls)
        for (code, out, err), to in zip(refused, ("b", "c", "d")):
            self.assertEqual(code, EXIT_BAD_NAME, f"send to {to}: {err}")
            self.assertIn("nothing sent", err)
        self.assertIn('bad remote tc path "~bob/tc"', refused[0][2])
        self.assertIn('bad ssh target "-oProxyCommand=x"', refused[2][2])
        self.assertFalse(called_before, "ssh ran for a card C1 refuses")
        self.assertFalse(outbox_before, "a refused card wrote to the outbox")
        self.assertEqual(good[0], 0, good)
        self.assertEqual(len(seen), 1)

    def test_a_connection_failure_or_a_far_10_keeps_the_message_and_exits_4(self):
        """Fake ssh exiting 255, or 10 (D23): exit 4, one file waiting in outbox/to-b/, nothing in sent/ or refused/, stderr names tc flush.

        Must reject a far 10 filed as a refusal: it was busy and wrote
        nothing, so it must be tried again.

        @interacts  per case: one tc card, one send, one fake call.
        @deps       assert_called, outbox.
        @complexity O(1): two cases.
        @alloc      one TcRoot per case.
        """
        cases = [(SSH_CONNECT_FAILED, FAKE_CONNECT_STDERR, FAKE_CONNECT_STDERR.strip()),
                 (EXIT_BUSY, FAKE_BUSY_STDERR, f"the far tc was busy, exit {EXIT_BUSY}: {FAKE_BUSY_STDERR.strip()}")]
        for exit_code, stderr, reason in cases:
            with self.subTest(exit_code=exit_code):
                with _root.TcRoot() as root:
                    folder, calls = root.fake_bin("ssh", exit_code, stderr=stderr)
                    root.tc("card", "b", "--ssh", TARGET)
                    code, out, err = root.tc("send", "--from", "a", "--to", "b", "hi")
                    seen = assert_called(self, folder, calls)
                    path = root.path / "outbox" / "to-b" / "000001-from-a.md"
                    waiting = outbox(root, "b")
                    filed = outbox(root, "b", "sent") + outbox(root, "b", "refused")
                self.assertEqual(code, EXIT_QUEUED, err)
                self.assertEqual(out, "")
                self.assertEqual(err, KEPT_WORDS.format(target=TARGET, reason=reason, path=path))
                self.assertEqual(len(seen), 1)
                self.assertEqual(waiting, ["000001-from-a.md"])
                self.assertEqual(filed, [])

    def test_a_far_refusal_is_filed_in_refused_with_its_stderr_and_exits_with_its_code(self):
        """Fake ssh exiting 7: exit 7, the far stderr printed, the file in refused/ with a note holding the far stderr beside it, nothing waiting.

        Must reject a refusal queued for retry.

        @interacts  one tc card, one send, one fake call.
        @deps       assert_called, outbox.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("ssh", EXIT_GATE_REFUSED, stderr=FAKE_REFUSED_STDERR)
            root.tc("card", "b", "--ssh", TARGET)
            code, out, err = root.tc("send", "--from", "a", "--to", "b", "hi")
            seen = assert_called(self, folder, calls)
            refused = outbox(root, "b", "refused")
            note = root.path / "outbox" / "to-b" / "refused" / "000001-from-a.md.stderr"
            note_text = note.read_text() if note.exists() else None
            waiting = outbox(root, "b")
            filed = root.path / "outbox" / "to-b" / "refused" / "000001-from-a.md"
        self.assertEqual(code, EXIT_GATE_REFUSED, err)
        self.assertEqual(len(seen), 1)
        self.assertEqual(err, f"{FAKE_REFUSED_STDERR.strip()}\nrefused by {TARGET} (exit {EXIT_GATE_REFUSED}); "
                              f"filed in {filed}, and nothing retries it\n")
        self.assertEqual(refused, ["000001-from-a.md"])
        self.assertEqual(waiting, [], "a refused message was kept for a retry")
        self.assertIsNotNone(note_text, "no note beside the refused message")
        self.assertIn(FAKE_REFUSED_STDERR, note_text)
        self.assertIn(f"exited {EXIT_GATE_REFUSED}", note_text)

    def test_with_mail_already_waiting_a_new_send_never_calls_ssh_and_queues_behind_it(self):
        """One message waiting for u@h: a new send to it is published behind it without trying (the second fake's record stays empty), exit 4, C3's words; a send to another target still goes.

        @interacts  one tc card per name, three sends, two fakes.
        @deps       assert_called, outbox.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            first_folder, first_calls = root.fake_bin("ssh", SSH_CONNECT_FAILED, stderr=FAKE_CONNECT_STDERR)
            root.tc("card", "b", "--ssh", TARGET)
            root.tc("card", "c", "--ssh", OTHER_TARGET)
            first = root.tc("send", "--from", "a", "--to", "b", "one")
            assert_called(self, first_folder, first_calls)
            folder, calls = root.fake_bin("ssh", 0)
            code, out, err = root.tc("send", "--from", "a", "--to", "b", "two")
            not_called = not (folder.parent / "calls.jsonl").exists()
            waiting = outbox(root, "b")
            other = root.tc("send", "--from", "a", "--to", "c", "three")
            seen = assert_called(self, folder, calls)
        self.assertEqual(first[0], EXIT_QUEUED, first)
        self.assertEqual((code, out, err), (EXIT_QUEUED, "", QUEUED_WORDS.format(target=TARGET, n=1)))
        self.assertTrue(not_called, "a send to a target with a queue ran ssh")
        self.assertEqual(waiting, ["000001-from-a.md", "000002-from-a.md"])
        self.assertEqual(other[0], 0, other)
        self.assertEqual([call["argv"][len(SSH_ARGV_HEAD)] for call in seen], [OTHER_TARGET])

    def test_the_queue_is_keyed_by_target_across_names(self):
        """x and y both point at u@h: with x's message waiting, a send to y queues behind it (C3: the queue is the target's).

        @interacts  two tc cards, two sends, two fakes.
        @deps       assert_called, outbox.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            first_folder, first_calls = root.fake_bin("ssh", SSH_CONNECT_FAILED, stderr=FAKE_CONNECT_STDERR)
            root.tc("card", "x", "--ssh", TARGET)
            root.tc("card", "y", "--ssh", TARGET)
            root.tc("send", "--from", "a", "--to", "x", "one")
            assert_called(self, first_folder, first_calls)
            folder, calls = root.fake_bin("ssh", 0)
            code, out, err = root.tc("send", "--from", "a", "--to", "y", "two")
            not_called = not (folder.parent / "calls.jsonl").exists()
            waiting = outbox(root, "x") + outbox(root, "y")
            root.tc("card", "z", "--ssh", OTHER_TARGET)
            root.tc("send", "--from", "a", "--to", "z", "three")
            reachable = len(assert_called(self, folder, calls))
        self.assertEqual((code, err), (EXIT_QUEUED, QUEUED_WORDS.format(target=TARGET, n=1)))
        self.assertTrue(not_called, "a send behind another name's queue for the same target ran ssh")
        self.assertEqual(waiting, ["000001-from-a.md", "000002-from-a.md"])
        self.assertEqual(reachable, 1)

    def test_queue_order_counts_only_this_users_own_files(self):
        """In process, D22: a waiting file another member owns (owned_by_me patched to say so) holds nothing back; the send goes, exit 0. Control: the same file as this user's queues the next send.

        One Linux user cannot make a file another user owns, so the
        owner check is patched for that file alone, by its inode.

        @interacts  one tc card, two sends as commands (one failing), one
                    in process with PATH set to the fake's and owned_by_me
                    patched, one more as a command; loads tc.
        @deps       load_tc, assert_called, outbox; unittest.mock.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("ssh", [SSH_CONNECT_FAILED, 0, 0])
            root.tc("card", "b", "--ssh", TARGET)
            root.tc("send", "--from", "a", "--to", "b", "bob's, from before")
            theirs = root.path / "outbox" / "to-b" / "000001-from-a.md"
            inode = theirs.stat().st_ino
            tc = load_tc(root)
            mine = tc.owned_by_me
            with mock.patch.dict(os.environ, {"PATH": root.env["PATH"]}), \
                    mock.patch.object(tc, "owned_by_me", lambda st: st.st_ino != inode and mine(st)):
                got = tc.route_and_deliver("a", "b", "alice's")
            sent = outbox(root, "b", "sent")
            control = root.tc("send", "--from", "a", "--to", "b", "alice's next")
            seen = assert_called(self, folder, calls)
        self.assertEqual(got.exit, 0, got)
        self.assertEqual(sent, ["000002-from-a.md"])
        self.assertEqual(len(seen), 2, "the in-process send did not run ssh, or the control did")
        self.assertEqual(control[0], EXIT_QUEUED, control)
        self.assertEqual(control[2], QUEUED_WORDS.format(target=TARGET, n=1))

    def test_a_send_waits_for_the_send_lock_and_goes_once_it_is_let_go(self):
        """With the test holding this user's send lock for u@h, a send blocks on it (proven in /proc/locks), runs no ssh, and sends once the lock is let go.

        @interacts  one tc card; holds the send lock; one background send;
                    reads /proc/locks.
        @deps       send_lock_path, wait_until_blocked, assert_called;
                    fcntl.
        @complexity O(1).
        @alloc      one TcRoot, one open lock file, one background child.
        """
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("ssh", 0)
            root.tc("card", "b", "--ssh", TARGET)
            lock = send_lock_path(root, TARGET)
            lock.parent.mkdir()
            with open(lock, "a") as held:
                fcntl.flock(held, fcntl.LOCK_EX)
                proc = root.start("send", "--from", "a", "--to", "b", "hi")
                wait_until_blocked(self, proc, lock)
                while_held = (folder.parent / "calls.jsonl").exists()
            out, err = proc.communicate(timeout=FINISH_CEILING_SECONDS)
            seen = assert_called(self, folder, calls)
        self.assertFalse(while_held, "ssh ran while another tc held the send lock")
        self.assertEqual(proc.returncode, 0, err)
        self.assertEqual(len(seen), 1)

    def test_a_send_lock_held_past_the_bound_keeps_the_message_and_runs_no_ssh(self):
        """With the send lock held past tc's 3 s bound: exit 4, the not-tried words, one file waiting, no ssh; a send to another target still goes.

        Also a symlink planted at the lock's name: exit 4, kept, the words
        name it, and nothing is written through it (D17).

        @interacts  one tc card per name; holds the send lock; three
                    sends; plants one symlink at another target's lock.
        @deps       send_lock_path, assert_called, outbox; fcntl.
        @complexity O(1): about LOCK_WAIT_SECONDS (3 s).
        @alloc      one TcRoot, one open lock file.
        """
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("ssh", 0)
            root.tc("card", "b", "--ssh", TARGET)
            root.tc("card", "c", "--ssh", OTHER_TARGET)
            root.tc("card", "d", "--ssh", "u@h3")
            lock = send_lock_path(root, TARGET)
            lock.parent.mkdir()
            outside = root.base / "outside.txt"
            outside.write_text("untouched\n")
            send_lock_path(root, OTHER_TARGET).symlink_to(outside)
            with open(lock, "a") as held:
                fcntl.flock(held, fcntl.LOCK_EX)
                code, out, err = root.tc("send", "--from", "a", "--to", "b", "hi")
            linked = root.tc("send", "--from", "a", "--to", "c", "hi")
            not_called = not (folder.parent / "calls.jsonl").exists()
            waiting = outbox(root, "b") + outbox(root, "c")
            path = root.path / "outbox" / "to-b" / "000001-from-a.md"
            kept = outside.read_text()
            good = root.tc("send", "--from", "a", "--to", "d", "hi")
            seen = assert_called(self, folder, calls)
        self.assertEqual((code, err), (EXIT_QUEUED, NOT_TRIED_WORDS.format(target=TARGET, path=path)))
        self.assertEqual(linked[0], EXIT_QUEUED, linked)
        self.assertIn("it is a symlink", linked[2])
        self.assertEqual(kept, "untouched\n", "the send wrote through a link at its lock")
        self.assertTrue(not_called, "ssh ran without the send lock")
        self.assertEqual(waiting, ["000001-from-a.md", "000002-from-a.md"])
        self.assertEqual(good[0], 0, good)
        self.assertEqual(len(seen), 1)

    def test_a_send_past_ssh_send_seconds_keeps_the_message_and_exits_4(self):
        """In process, SSH_SEND_SECONDS patched to 2 s: a fake that records its call and then sleeps is killed, the message stays waiting, exit 4, `no answer in 2 s`.

        The wrapper runs tests/_root.py's fake (so the record is the
        harness's), then execs a sleep, which the timeout's kill ends.

        @interacts  writes a wrapper `ssh` in the root's temp folder; one
                    tc card; loads tc and calls route_and_deliver once
                    with PATH set to put the wrapper first and
                    SSH_SEND_SECONDS patched down.
        @deps       load_tc, assert_called, outbox; shlex, unittest.mock.
        @complexity O(1): about SHORT_SEND_SECONDS.
        @alloc      one TcRoot and one module.
        """
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("ssh", 0)
            slow = root.base / "slow-ssh"
            slow.mkdir()
            wrapper = slow / "ssh"
            wrapper.write_text(f'#!/bin/sh\n{shlex.quote(str(folder / "ssh"))} "$@"\n'
                               f"exec sleep {SLOW_SLEEP_SECONDS}\n")
            wrapper.chmod(OWN_WRAPPER_MODE)
            root.tc("card", "b", "--ssh", TARGET)
            tc = load_tc(root)
            with mock.patch.dict(os.environ, {"PATH": f"{slow}{os.pathsep}{root.env['PATH']}"}), \
                    mock.patch.object(tc, "SSH_SEND_SECONDS", SHORT_SEND_SECONDS):
                got = tc.route_and_deliver("a", "b", "hi")
            seen = assert_called(self, folder, calls)
            path = root.path / "outbox" / "to-b" / "000001-from-a.md"
            waiting = outbox(root, "b")
        self.assertEqual(got.exit, EXIT_QUEUED, got)
        self.assertEqual(got.words + "\n", KEPT_WORDS.format(target=TARGET, reason=f"no answer in {SHORT_SEND_SECONDS} s",
                                                             path=path))
        self.assertEqual(len(seen), 1)
        self.assertEqual(waiting, ["000001-from-a.md"])

    def test_a_move_into_sent_never_replaces_a_file_already_there(self):
        """In process: file_away into sent/ where a file already has the message's name keeps that file byte for byte and files the message at by-hand-1-<name> (D25).

        Must reject a rename, which replaces whatever holds its target.

        @interacts  one tc card, one failing send as a command (so a
                    message waits); plants a file in sent/; loads tc and
                    calls file_away once.
        @deps       load_tc, assert_called, outbox.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("ssh", SSH_CONNECT_FAILED, stderr=FAKE_CONNECT_STDERR)
            root.tc("card", "b", "--ssh", TARGET)
            root.tc("send", "--from", "a", "--to", "b", "the real one")
            assert_called(self, folder, calls)
            path = root.path / "outbox" / "to-b" / "000001-from-a.md"
            planted = root.path / "outbox" / "to-b" / "sent" / "000001-from-a.md"
            planted.parent.mkdir()
            planted.write_text("planted\n")
            tc = load_tc(root)
            filed = tc.file_away(path, "sent")
            kept = planted.read_text()
            moved = filed.read_text()
            waiting = outbox(root, "b")
        self.assertEqual(filed, planted.parent / "by-hand-1-000001-from-a.md")
        self.assertEqual(kept, "planted\n", "the move replaced a file already in sent/")
        self.assertIn("the real one", moved)
        self.assertEqual(waiting, [])

    def test_route_and_deliver_hands_its_one_deadline_to_deliver_ssh(self):
        """In process: route_and_deliver calls deliver_ssh with C2's five arguments and its own lock deadline (SHARED's DEBT-2), so a send never waits two bounds.

        @interacts  one tc card; loads tc; calls route_and_deliver once with
                    deliver_ssh (and its ROUTES entry) swapped for a
                    recorder, so nothing is sent.
        @deps       load_tc; unittest.mock.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        with _root.TcRoot() as root:
            root.tc("card", "b", "--ssh", TARGET)
            tc = load_tc(root)
            seen = []

            def recorder(*args, **kwargs):
                seen.append((args, kwargs))
                return tc.Delivery(0, "recorded", [])

            with mock.patch.object(tc, "deliver_ssh", recorder), mock.patch.dict(tc.ROUTES, {"ssh": recorder}), \
                    mock.patch.object(tc, "lock_deadline", lambda: 12345.0):
                got = tc.route_and_deliver("a", "b", "hi", "a note")
        self.assertEqual(got.words, "recorded")
        self.assertEqual(len(seen), 1)
        args, kwargs = seen[0]
        self.assertEqual(args[1:], ("a", "b", "hi", "a note"))
        self.assertEqual(args[0]["route"], "ssh")
        self.assertEqual(kwargs, {"deadline": 12345.0})


class SharedOutboxTest(UmaskTestCase):
    """The outbox on a shared mailbox (C4, D22): sticky folders, files the sender's alone, and init finding all of it right.

    @interacts  see the module block.
    @deps       UmaskTestCase, primary_group, _root.TcRoot.
    @complexity O(1) per test.
    @alloc      one TcRoot per test.
    """

    def test_outbox_folders_are_sticky_and_its_files_0640_and_init_leaves_them(self):
        """Shared with the user's primary group: outbox/to-b/, sent/ and refused/ are 3775 in the group; the messages, the note, the token and the send lock are 0640; init run again exits 0 and changes none of it.

        Must reject outbox/to-b/ at 2775, where any member could move
        another member's queued file (D22).

        @interacts  tc init twice, one tc card, two sends (one refused,
                    one sent); lstats the outbox.
        @deps       primary_group, assert_called, send_lock_path; os, stat.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        _, group, gid = primary_group()
        with _root.TcRoot() as root:
            init = root.tc("init", "--shared", "--group", group)
            folder, calls = root.fake_bin("ssh", [EXIT_GATE_REFUSED, 0], stderr=FAKE_REFUSED_STDERR)
            root.tc("card", "b", "--ssh", TARGET)
            refused = root.tc("send", "--from", "a", "--to", "b", "one")
            sent = root.tc("send", "--from", "a", "--to", "b", "two")
            assert_called(self, folder, calls)
            box = root.path / "outbox" / "to-b"
            entries = {"to-b": box, "sent": box / "sent", "refused": box / "refused",
                       "sent message": box / "sent" / "000002-from-a.md",
                       "refused message": box / "refused" / "000001-from-a.md",
                       "note": box / "refused" / "000001-from-a.md.stderr",
                       "token": root.path / "outbox" / ".origin-token",
                       "send lock": send_lock_path(root, TARGET)}
            before = {k: (stat.S_IMODE(os.lstat(p).st_mode), os.lstat(p).st_gid) for k, p in entries.items()}
            again = root.tc("init", "--shared", "--group", group)
            after = {k: (stat.S_IMODE(os.lstat(p).st_mode), os.lstat(p).st_gid) for k, p in entries.items()}
        self.assertEqual(init[0], 0, init)
        self.assertEqual(refused[0], EXIT_GATE_REFUSED, refused)
        self.assertEqual(sent[0], 0, sent)
        for name in ("to-b", "sent", "refused"):
            self.assertEqual(before[name], (STICKY_FOLDER_MODE, gid), f"{name}: {oct(before[name][0])}")
        for name in ("sent message", "refused message", "note", "token", "send lock"):
            self.assertEqual(before[name], (OWNED_FILE_MODE, gid), f"{name}: {oct(before[name][0])}")
        self.assertEqual(again[0], 0, again)
        self.assertNotIn("skipped", again[2])
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
