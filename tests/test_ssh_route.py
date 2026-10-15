"""
Tests for the ssh route (SSH S1, contract C3, decisions D13, D22, D23 and
D25, and D32 and D33 since fix round 1): `tc send` to an ssh card
publishes the message in the sender's own outbox branch, runs ssh once
with C3's argv, an origin id unique to the message and the body on
stdin, and files the message by the far tc's answer: sent/ on 0 (the far
warnings shown), kept on 255, a timeout or a far 10, refused/ on any
other code (a code tc does not know exits 11), keeping at most a cap of
what the far side prints. A target with a queue gets no ssh run.

Model:  Claude Opus 5.5 (the SSH lane agent), 2026-10-15; changed in fix
        round 1 by the SSH fixer, Claude Opus 5.5, 2026-10-15
Status: unreviewed

Real ssh never runs here (rule 5). Every test that sends puts
tests/_root.py's fake `ssh` first on PATH, asserts its record file exists
before reading it, and reads it inside the `with TcRoot()` block. A test
that asserts ssh was not called proves, in the same root, that the fake
it watched is reachable.

@interacts  runs ../tc through tests/_root.py under a throwaway TC_ROOT,
            with a fake `ssh` that records its argv and stdin. Some tests
            write a card by hand into cards/. Some hold this user's send
            lock (outbox/<login>/.send-<key>.lock) themselves and read
            /proc/locks to see a child blocked on it. Some make folders,
            a link or a file by hand in outbox/ and rename them (SSH fix
            round 1, Claude Opus 5.5, unreviewed: D32's branches). Two
            tests write a loopback wrapper `ssh` in the root's temp
            folder that runs the fake and then this branch's own `tc
            gate` under a second TC_ROOT there, as a far machine would;
            one writes mail/.seq by hand, one plants a file in the far
            mailbox. One test's wrapper prints past tc's output cap on
            stdout after the fake. Six tests load tc as a module
            (TC_ROOT set to the harness root first, put back after) and
            work in process, under the root only: one calls
            route_and_deliver with PATH set for that call to a wrapper
            that runs the fake and then sleeps, and SSH_SEND_SECONDS
            patched down; one calls it with deliver_ssh swapped for a
            recorder and lock_deadline for a fixed value; one plants a
            file in sent/ and calls file_away; one calls route_and_deliver
            and health_snapshot with os.lstat patched so this user's
            branch reads as another member's; one calls route_and_deliver
            and cmd_flush with origin_nonce swapped for a seeded source
            (random.Random); one reads tc's timing constants. One class
            shares the mailbox with the user's own primary group (tc init
            --shared), reads modes and groups, and asks POSIX's rules what
            another member may do there.
@deps       python3 stdlib (argparse, contextlib, fcntl, hashlib, io, json,
            os, pathlib, pwd, random, re, shlex, stat, sys, unittest,
            unittest.mock); tests/_root.py; load_tc, wait_until_blocked
            and FINISH_CEILING_SECONDS from test_codex_route.py;
            UmaskTestCase, owner_patched_lstat and primary_group from
            test_shared.py; ../tc.
@complexity O(1) per test: one to five tc runs and as many fake calls,
            each under a second. One test waits out tc's own lock bound
            (LOCK_WAIT_SECONDS, 3 s), and the timeout test
            SHORT_SEND_SECONDS; the member model reads one lstat per
            entry of one branch (a handful).
@alloc      one TcRoot per test, removed when its context exits; one open
            lock file while a test holds the send lock.
"""

import argparse
import contextlib
import fcntl
import hashlib
import io
import json
import os
import pathlib
import pwd
import random
import re
import shlex
import stat
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
from test_shared import UmaskTestCase, owner_patched_lstat, primary_group  # noqa: E402

# C3's argv before the target, written here rather than read from tc:
# no tty, never a password prompt, the connect timeout (SSH_CONNECT_SECONDS,
# 10), and `--` right before the target.
SSH_ARGV_HEAD = ["-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "--"]
TARGET = "u@h"
OTHER_TARGET = "u@h2"
DEFAULT_REMOTE_TC = "~/TheConnection/tc"
# The exit table's rows this route uses.
EXIT_REFUSED = 1
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
# SSH fix round 1 (Claude Opus 5.5, unreviewed): a far tc's warning on a
# delivery that went through (D33 part 8), written here as tc words it.
FAKE_NEW_INBOX_STDERR = "new inbox: nobody has joined as b\n"
# The far codes tc does not know that the row 11 test sends (D33 part 7):
# a far tc that queued it itself, and a far shell's command not found.
UNKNOWN_FAR_CODES = (4, 127)
EXIT_FAR_UNKNOWN = 11
# The most of each far stream tc keeps (tc's SSH_OUTPUT_MAX_BYTES, written
# here), and how far past it the test's fake prints.
OUTPUT_CAP_BYTES = 65536
PAST_CAP_TIMES = 3
# A terminal escape the far side prints (clear the screen), and what it
# reads as once through tc's printable filter.
RAW_ESCAPE = "\x1b[2J"
SHOWN_ESCAPE = "\\x1b[2J"
# D25's origin id: 32 hex digits of the mailbox's token, the outbox number,
# 32 hex digits of the message's own random part (D33 part 4; SSH fix
# round 1, Claude Opus 5.5, unreviewed), the sender. The outbox file's
# header line ends with it.
TOKEN_PATTERN = re.compile(r"[0-9a-f]{32}")
HEADER_ORIGIN_PATTERN = re.compile(r", origin (\S+)$")
ORIGIN_NONCE_HEX_DIGITS = 32
# The seed of the source a test swaps in for tc's origin_nonce, so the id
# it builds is known. Any fixed number does.
NONCE_SEED = 25
# The far gate's lock waits in one send to a codex name, counted here
# (D33 part 3): its inbox lock and mail/.seq share one bound, and the ring
# marker is written twice, each with a bound of its own.
FAR_LOCK_WAITS = 3
# The far mailbox name the loopback fake's gate delivers as (its --as).
FAR_KEY = "home-a"
# The send lock's name: the start of the target's sha256 in hex (tc's
# SEND_LOCK_KEY_CHARS, written here), in the user's own outbox branch.
SEND_LOCK_KEY_CHARS = 16
# SSH fix round 1 (Claude Opus 5.5, unreviewed): the shared modes C4, D32
# and D33 want for the outbox, written here. outbox/ itself is sticky like
# the other top folders; each member's branch, outbox/<user>/, and every
# folder in it are setgid with no group write; every file in them is the
# owner's alone to write, and the send lock the owner's alone to open.
TOP_FOLDER_MODE = 0o3775
BRANCH_MODE = 0o2750
OWNED_FILE_MODE = 0o640
SEND_LOCK_MODE = 0o600
# A second member, for the tests that ask what another member may do: a
# made-up login for the folders that member's first send would make, and
# a user id the running user is not (the running user's plus one, as
# test_shared.py's owner_patched_lstat reports another user).
OTHER_MEMBER = "ben-member"
# The permission bits the member model reads, as ls shows them: read,
# write, search (x).
MAY_READ, MAY_WRITE, MAY_SEARCH = 4, 2, 1
# How a folder another member made at this user's branch name is moved
# aside, written here: tc's SQUATTED_NAME with the first free count.
ASIDE_NAME = ".squatted-{name}-1"
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


def login():
    """The running user's login, the name of that user's outbox branch (D32); the user id as text when the machine has no such user, as tc does.

    @interacts  reads this process's user id and the user database.
    @deps       os, pwd.
    @complexity O(1).
    @alloc      one short string, returned.
    """
    try:
        return pwd.getpwuid(os.geteuid()).pw_name
    except KeyError:
        return str(os.geteuid())


def branch(root):
    """The running user's outbox branch under this root: outbox/<login>/ (C3, D32).

    @interacts  reads the user database (login).
    @deps       login.
    @complexity O(1).
    @alloc      one path, returned.
    """
    return root.path / "outbox" / login()


def queue(root, to):
    """The running user's queue for `to` under this root: outbox/<login>/to-<to>/ (C3, D32).

    @interacts  reads the user database (branch).
    @deps       branch.
    @complexity O(1).
    @alloc      one path, returned.
    """
    return branch(root) / f"to-{to}"


def outbox(root, to, folder=None):
    """The *.md names directly in this user's outbox/<login>/to-<to>/ (or its `folder`), sorted; [] when it is not there.

    @interacts  lists one folder.
    @deps       queue.
    @complexity O(f) over f files there (a handful).
    @alloc      one list, returned.
    """
    box = queue(root, to)
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


def origin_in(path):
    """The origin id the outbox file at `path` ends its header line with (D33 part 4), or None when it holds none.

    @interacts  reads one file.
    @deps       re; HEADER_ORIGIN_PATTERN.
    @complexity O(b) over b bytes of the file.
    @alloc      the file's text, freed on return; one string, returned.
    """
    found = HEADER_ORIGIN_PATTERN.search(path.read_text().split("\n", 1)[0])
    return found.group(1) if found else None


def remote_command(path, sender, to, tc=DEFAULT_REMOTE_TC):
    """The remote command C3, D25 and D33 want for the outbox file at `path` from `sender` to `to`, with the origin id its header holds and a remote tc path that needs no quoting past a bare ~/.

    @interacts  reads one file (origin_in).
    @deps       origin_in.
    @complexity O(1).
    @alloc      one string, returned.
    """
    return f"{tc} send --from {sender} --to {to} --origin {origin_in(path)}"


def send_lock_path(root, target):
    """This user's send lock for `target` under this root: outbox/<login>/.send-<key>.lock (D33 part 2).

    @interacts  reads the user database (branch).
    @deps       branch; hashlib.
    @complexity O(t) over t characters of the target.
    @alloc      one path, returned.
    """
    key = hashlib.sha256(target.encode()).hexdigest()[:SEND_LOCK_KEY_CHARS]
    return branch(root) / f".send-{key}.lock"


def seen_as(path, owners):
    """The lstat result of `path`, with its owner replaced by owners[path] when `owners` names it: the member model's view of who owns what.

    One Linux user cannot make a folder another user owns, so a folder
    another member's first send would make is made here by hand and
    counted as theirs.

    @interacts  lstats `path`.
    @deps       os, stat.
    @complexity O(1).
    @alloc      one stat result, returned.
    """
    st = os.lstat(path)
    if path not in owners:
        return st
    fields = list(st[:stat.ST_CTIME + 1])
    fields[stat.ST_UID] = owners[path]
    return os.stat_result(fields)


def may(st, uid, gids, bit):
    """True when user `uid` in groups `gids` holds the permission `bit` (MAY_READ, MAY_WRITE or MAY_SEARCH) on the entry `st` describes: the owner's bits for its owner, else the group's for a member of its group, else the others' (POSIX's first match). Nobody here is root.

    @interacts  none.
    @deps       stat.
    @complexity O(1).
    @alloc      none.
    """
    mode = stat.S_IMODE(st.st_mode)
    shift = 6 if st.st_uid == uid else 3 if st.st_gid in gids else 0
    return bool((mode >> shift) & bit)


def may_move_or_remove(entry, parent, uid, gids):
    """True when user `uid` may rename or unlink the entry `entry` (a stat result) out of the folder `parent` (one): write and search on the folder and, when the folder is sticky, the entry or the folder its own (POSIX).

    @interacts  none.
    @deps       may; stat.
    @complexity O(1).
    @alloc      none.
    """
    if not (may(parent, uid, gids, MAY_WRITE) and may(parent, uid, gids, MAY_SEARCH)):
        return False
    return not parent.st_mode & stat.S_ISVTX or uid in (entry.st_uid, parent.st_uid)


def may_make_in(folder, uid, gids):
    """True when user `uid` may make an entry in the folder `folder` (a stat result): write and search on it (POSIX).

    @interacts  none.
    @deps       may.
    @complexity O(1).
    @alloc      none.
    """
    return may(folder, uid, gids, MAY_WRITE) and may(folder, uid, gids, MAY_SEARCH)


def far_gate_ssh(root, folder, far, key=FAR_KEY):
    """A loopback `ssh`: it runs the harness's fake at `folder` (the record, and its exit code: a non-zero one ends the call there), then hands the same stdin and the remote command, its last argument, to a real `tc gate --as <key>` under the far mailbox `far`, as sshd does with a forced command. The env for a call that should find it.

    No real ssh runs (rule 5): the fake records every call and is asserted
    called. The far side is this branch's own tc, under a TC_ROOT of its
    own in the temp folder, so a test sees what a far gate answers.

    @interacts  writes far-ssh-*/ssh (mode 0700) in the root's temp
                folder; each call keeps its stdin in a file beside it.
    @deps       shlex, os, sys; _root.TC; OWN_WRAPPER_MODE.
    @complexity O(1).
    @alloc      one folder, removed with the temp folder.
    """
    home = root.base / f"far-ssh-{len(list(root.base.glob('far-ssh-*')))}"
    home.mkdir()
    feed = shlex.quote(str(home / "stdin")) + ".$$"
    wrapper = home / "ssh"
    wrapper.write_text("#!/bin/sh\n"
                       f"cat > {feed}\n"
                       f'{shlex.quote(str(folder / "ssh"))} "$@" < {feed} || exit $?\n'
                       "for last; do :; done\n"
                       f'SSH_ORIGINAL_COMMAND="$last" TC_ROOT={shlex.quote(str(far))} exec '
                       f"{shlex.quote(sys.executable)} {shlex.quote(str(_root.TC))} gate --as {shlex.quote(key)} "
                       f"< {feed}\n")
    wrapper.chmod(OWN_WRAPPER_MODE)
    return {"PATH": f"{home}{os.pathsep}{root.env['PATH']}"}


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
        """Fake ssh exiting 0: argv is exactly C3's, -T present, `--` right before the target, the body on stdin and on no argv word; exit 0; the message in sent/ with its origin id on argv, the id its header line ends with: the token, 1, 32 hex digits of its own, the sender.

        Must reject the body on the command line, and a send with no
        --origin (D25), or with an id that has no random part of its own
        (D33 part 4).

        @interacts  one tc card, one send, one fake call.
        @deps       assert_called, remote_command, origin_in, queue, outbox,
                    token_of.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        body = "hello over ssh; $(echo not run)"
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("ssh", 0)
            root.tc("card", "b", "--ssh", TARGET)
            code, out, err = root.tc("send", "--from", "a", "--to", "b", body)
            seen = assert_called(self, folder, calls)
            filed = queue(root, "b") / "sent" / "000001-from-a.md"
            want = SSH_ARGV_HEAD + [TARGET, remote_command(filed, "a", "b")]
            token = token_of(root)
            origin = origin_in(filed)
            sent, waiting = outbox(root, "b", "sent"), outbox(root, "b")
            text = filed.read_text()
        self.assertEqual((code, err), (0, ""), err)
        self.assertEqual(out, SENT_WORDS.format(target=TARGET) + "\n")
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0]["argv"], want)
        self.assertEqual(seen[0]["argv"].index("--") + 1, seen[0]["argv"].index(TARGET))
        self.assertEqual(seen[0]["stdin"], body + "\n")
        self.assertFalse(any("hello" in word for word in seen[0]["argv"]), "the body is on ssh's command line")
        self.assertTrue(TOKEN_PATTERN.fullmatch(token), token)
        self.assertRegex(origin, rf"^{token}-1-[0-9a-f]{{{ORIGIN_NONCE_HEX_DIGITS}}}-a$")
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
        @deps       write_card, ssh_card, assert_called, origin_in, queue;
                    shlex.
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
            ids = [origin_in(queue(root, to) / "sent" / f"00000{n}-from-a.md") for n, to in ((1, "b"), (2, "c"), (3, "d"))]
        remotes = [call["argv"][-1] for call in seen]
        self.assertEqual(remotes[0], f"~/TheConnection/tc send --from a --to b --origin {ids[0]}")
        self.assertEqual(remotes[1], f"~/'my dir/tc' send --from a --to c --origin {ids[1]}")
        words = shlex.split(remotes[2])
        self.assertEqual(words, ["/opt/it's/tc", "send", "--from", "a", "--to", "d", "--origin", ids[2]])

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
                    path = queue(root, "b") / "000001-from-a.md"
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
            note = queue(root, "b") / "refused" / "000001-from-a.md.stderr"
            note_text = note.read_text() if note.exists() else None
            waiting = outbox(root, "b")
            filed = queue(root, "b") / "refused" / "000001-from-a.md"
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
        """D22, D32: a file waiting for u@h in another member's branch holds nothing back; the send goes, exit 0. Control: the same file moved into this user's branch queues the next send.

        SSH fix round 1 (Claude Opus 5.5, unreviewed): each member's queue
        is a branch of their own, so the other member's file is moved by
        hand into outbox/ben-member/to-b/, where that member's send would
        have put it.

        @interacts  one tc card, four sends (one failing), two renames
                    by hand.
        @deps       queue, assert_called, outbox; os.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("ssh", [SSH_CONNECT_FAILED, 0, 0])
            root.tc("card", "b", "--ssh", TARGET)
            root.tc("send", "--from", "a", "--to", "b", "bob's, from before")
            theirs = root.path / "outbox" / OTHER_MEMBER / "to-b" / "000001-from-a.md"
            theirs.parent.mkdir(parents=True)
            os.rename(queue(root, "b") / "000001-from-a.md", theirs)
            got = root.tc("send", "--from", "a", "--to", "b", "alice's")
            sent = outbox(root, "b", "sent")
            os.rename(theirs, queue(root, "b") / theirs.name)
            control = root.tc("send", "--from", "a", "--to", "b", "alice's next")
            seen = assert_called(self, folder, calls)
        self.assertEqual(got[0], 0, got)
        self.assertEqual(sent, ["000002-from-a.md"])
        self.assertEqual(len(seen), 2, "the second send did not run ssh, or the control did")
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
            lock.parent.mkdir(parents=True)
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
            lock.parent.mkdir(parents=True)
            outside = root.base / "outside.txt"
            outside.write_text("untouched\n")
            send_lock_path(root, OTHER_TARGET).symlink_to(outside)
            with open(lock, "a") as held:
                fcntl.flock(held, fcntl.LOCK_EX)
                code, out, err = root.tc("send", "--from", "a", "--to", "b", "hi")
            linked = root.tc("send", "--from", "a", "--to", "c", "hi")
            not_called = not (folder.parent / "calls.jsonl").exists()
            waiting = outbox(root, "b") + outbox(root, "c")
            path = queue(root, "b") / "000001-from-a.md"
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
            path = queue(root, "b") / "000001-from-a.md"
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
            path = queue(root, "b") / "000001-from-a.md"
            planted = queue(root, "b") / "sent" / "000001-from-a.md"
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


class OriginIdTest(unittest.TestCase):
    """SSH fix round 1 (Claude Opus 5.5, unreviewed): D33 parts 3 and 4. Each origin id carries a random part of its own, drawn once and read back by every retry, and the ssh run outlasts a far gate's worst case.

    @interacts  see the module block.
    @deps       _root.TcRoot, load_tc, far_gate_ssh.
    @complexity O(1) per test.
    @alloc      one TcRoot per test.
    """

    def test_after_mail_seq_is_set_back_a_message_to_a_second_far_name_is_delivered(self):
        """b and c both on one far user, through the loopback fake's real far gate: #1 to b lands; mail/.seq is set back to 0; the next send, to c, takes #1 again, and is delivered, never answered `already delivered`. Both ids carry 1, and differ.

        The audit's HIGH-2. Must reject an id that is only the token, the
        number and the sender: the far gate filed it for b, and c's
        message would be dropped while this side files it in sent/.

        @interacts  writes the loopback wrapper; two tc cards, two sends,
                    one write of mail/.seq by hand; the far gate runs under
                    a second TC_ROOT in the temp folder.
        @deps       far_gate_ssh, assert_called; shlex.
        @complexity O(1).
        @alloc      one TcRoot and the far mailbox in its temp folder.
        """
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("ssh", 0)
            far = root.base / "far"
            far.mkdir()
            env = far_gate_ssh(root, folder, far)
            root.tc("card", "b", "--ssh", TARGET)
            root.tc("card", "c", "--ssh", TARGET)
            first = root.tc("send", "--from", "a", "--to", "b", "one", env=env)
            (root.path / "mail" / ".seq").write_text("0")
            second = root.tc("send", "--from", "a", "--to", "c", "two", env=env)
            seen = assert_called(self, folder, calls)
            ids = [shlex.split(call["argv"][-1])[-1] for call in seen]
            landed = sorted(p.name for p in (far / "mail" / "to-c").glob("*.md"))
        self.assertEqual(first[0], 0, first)
        self.assertEqual(second[0], 0, second)
        self.assertNotIn("already delivered", second[1])
        self.assertEqual(landed, [f"000002-from-{FAR_KEY}.md"], "the second far name never got its message")
        self.assertEqual([origin.split("-")[1] for origin in ids], ["1", "1"], "mail/.seq was not set back")
        self.assertNotEqual(ids[0], ids[1])

    def test_the_random_part_is_drawn_once_per_message_and_every_retry_reads_it_back(self):
        """In process, origin_nonce swapped for a seeded source: a send that ssh cannot reach draws once, and its header ends with <token>-1-<seeded hex>-a; the flush that then sends it uses that same id and draws nothing.

        @interacts  one tc card; loads tc and calls route_and_deliver, then
                    cmd_flush, with PATH set to the fake's and origin_nonce
                    swapped; reads the sent file's header.
        @deps       load_tc, assert_called, origin_in, queue, token_of;
                    random, argparse, contextlib, io, unittest.mock.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("ssh", [SSH_CONNECT_FAILED, 0], stderr=FAKE_CONNECT_STDERR)
            root.tc("card", "b", "--ssh", TARGET)
            tc = load_tc(root)
            source, drawn = random.Random(NONCE_SEED), []

            def seeded():
                drawn.append(f"{source.getrandbits(4 * ORIGIN_NONCE_HEX_DIGITS):0{ORIGIN_NONCE_HEX_DIGITS}x}")
                return drawn[-1]
            flushed = None
            with mock.patch.dict(os.environ, {"PATH": root.env["PATH"]}), \
                    mock.patch.object(tc, "origin_nonce", seeded):
                got = tc.route_and_deliver("a", "b", "hi")
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
                    try:
                        tc.cmd_flush(argparse.Namespace(to=None))
                    except SystemExit as stop:
                        flushed = stop.code
            seen = assert_called(self, folder, calls)
            ids = [shlex.split(call["argv"][-1])[-1] for call in seen]
            sent = queue(root, "b") / "sent" / "000001-from-a.md"
            header = origin_in(sent) if sent.exists() else None
            token = token_of(root)
        nonce = f"{random.Random(NONCE_SEED).getrandbits(4 * ORIGIN_NONCE_HEX_DIGITS):0{ORIGIN_NONCE_HEX_DIGITS}x}"
        want = f"{token}-1-{nonce}-a"
        self.assertEqual(got.exit, EXIT_QUEUED, got)
        self.assertIsNone(flushed, f"flush exited {flushed}: {err.getvalue()}")
        self.assertEqual(drawn, [nonce], "the flush drew a random part of its own")
        self.assertEqual(ids, [want, want])
        self.assertEqual(header, want)

    def test_ssh_send_seconds_outlasts_a_far_ring_connect_and_lock_waits(self):
        """SSH_SEND_SECONDS is past SSH_CONNECT_SECONDS plus CODEX_RING_SECONDS plus the far gate's three lock waits (D33 part 3), read from tc's own constants; no clock.

        The audit's MEDIUM-1. Must reject the pinned 30 s, no longer than
        the far codex ring alone.

        @interacts  loads tc.
        @deps       load_tc; FAR_LOCK_WAITS.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        with _root.TcRoot() as root:
            tc = load_tc(root)
        far_worst = tc.SSH_CONNECT_SECONDS + tc.CODEX_RING_SECONDS + FAR_LOCK_WAITS * tc.LOCK_WAIT_SECONDS
        self.assertGreater(tc.SSH_SEND_SECONDS, far_worst)


class FarAnswerTest(unittest.TestCase):
    """SSH fix round 1 (Claude Opus 5.5, unreviewed): D33 parts 7 and 8 and the audit's MEDIUM-2, MEDIUM-4 and LOW-4. What the far side says reaches the sender bounded and filtered, its warnings on a delivery included, and a far code tc does not know exits 11.

    @interacts  see the module block.
    @deps       _root.TcRoot, far_gate_ssh.
    @complexity O(1) per test.
    @alloc      one TcRoot per test or case.
    """

    def test_a_far_warning_on_exit_0_reaches_the_sender_in_send_and_in_flush(self):
        """A fake that exits 0 and warns `new inbox: nobody has joined as b` on stderr: tc send exits 0 and prints `u@h said: <warning>` on stderr; a message queued and then flushed past the same fake gets the same line, after `tc flush: #2 to b: `.

        The audit's MEDIUM-5. Must reject a far warning dropped on a
        success: a card naming a far name nobody joined would deliver into
        a dead inbox with a clean line.

        @interacts  one tc card, two sends, one flush, three fakes.
        @deps       assert_called.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("ssh", 0, stderr=FAKE_NEW_INBOX_STDERR)
            root.tc("card", "b", "--ssh", TARGET)
            code, out, err = root.tc("send", "--from", "a", "--to", "b", "one")
            assert_called(self, folder, calls)
            down, down_calls = root.fake_bin("ssh", SSH_CONNECT_FAILED, stderr=FAKE_CONNECT_STDERR)
            kept = root.tc("send", "--from", "a", "--to", "b", "two")
            assert_called(self, down, down_calls)
            up, up_calls = root.fake_bin("ssh", 0, stderr=FAKE_NEW_INBOX_STDERR)
            flushed = root.tc("flush")
            assert_called(self, up, up_calls)
        said = f"{TARGET} said: {FAKE_NEW_INBOX_STDERR}"
        self.assertEqual((code, err), (0, said))
        self.assertEqual(kept[0], EXIT_QUEUED, kept)
        self.assertEqual(flushed[0], 0, flushed)
        self.assertIn(f"tc flush: #2 to b: {said}", flushed[2])

    def test_a_far_code_tc_does_not_know_exits_11_and_is_filed_with_its_code(self):
        """A fake exiting 4 (a far tc that queued it itself), then 127 (a far shell's not found): exit 11, the message in refused/, the words and the note naming the far code; nothing waits.

        D33 part 7, the audit's LOW-1. Must reject a far code passed
        through as this tc's own: a far 4 would read as `kept, run tc
        flush` for a message filed in refused/.

        @interacts  per code: one tc card, one send, one fake call.
        @deps       assert_called, outbox, queue.
        @complexity O(1): two cases.
        @alloc      one TcRoot per case.
        """
        for far in UNKNOWN_FAR_CODES:
            with self.subTest(far=far), _root.TcRoot() as root:
                folder, calls = root.fake_bin("ssh", far, stderr=f"far side said {far}\n")
                root.tc("card", "b", "--ssh", TARGET)
                code, out, err = root.tc("send", "--from", "a", "--to", "b", "hi")
                assert_called(self, folder, calls)
                filed = queue(root, "b") / "refused" / "000001-from-a.md"
                note = filed.with_name(filed.name + ".stderr")
                note_text = note.read_text() if note.exists() else ""
                waiting, refused = outbox(root, "b"), outbox(root, "b", "refused")
            self.assertEqual(code, EXIT_FAR_UNKNOWN, err)
            self.assertEqual(err, f"far side said {far}\nrefused by {TARGET} with far exit {far}, a code tc does not "
                                  f"know (exit {EXIT_FAR_UNKNOWN}); filed in {filed}, and nothing retries it\n")
            self.assertEqual((waiting, refused), ([], ["000001-from-a.md"]))
            self.assertIn(f"the far side exited {far};", note_text)

    def test_what_the_far_side_prints_past_the_cap_is_dropped_and_said_and_the_note_is_filtered(self):
        """A fake that prints a terminal escape and three times the cap on stderr, and three times the cap on stdout, then exits 7: tc exits 7, keeps the cap of each, says it cut both, and the note beside the refused file holds the escape only through the printable filter.

        The audit's MEDIUM-4 and LOW-4. Must reject a capture with no cap
        (a far side that prints without end costs this machine gigabytes)
        and a note that keeps the far bytes raw.

        @interacts  writes a wrapper `ssh` in the root's temp folder that
                    runs the fake and then prints to stdout; one tc card,
                    one send.
        @deps       assert_called, queue; shlex.
        @complexity O(c) over c = PAST_CAP_TIMES x OUTPUT_CAP_BYTES bytes
                    per stream.
        @alloc      one TcRoot and the printed text, a few hundred KB.
        """
        past = PAST_CAP_TIMES * OUTPUT_CAP_BYTES
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("ssh", EXIT_GATE_REFUSED, stderr=RAW_ESCAPE + "e" * past)
            loud = root.base / "loud-ssh"
            loud.mkdir()
            wrapper = loud / "ssh"
            wrapper.write_text(f'#!/bin/sh\n{shlex.quote(str(folder / "ssh"))} "$@"\ncode=$?\n'
                               f"head -c {past} /dev/zero | tr '\\000' o\nexit $code\n")
            wrapper.chmod(OWN_WRAPPER_MODE)
            root.tc("card", "b", "--ssh", TARGET)
            code, out, err = root.tc("send", "--from", "a", "--to", "b", "hi",
                                     env={"PATH": f"{loud}{os.pathsep}{root.env['PATH']}"})
            assert_called(self, folder, calls)
            note = queue(root, "b") / "refused" / "000001-from-a.md.stderr"
            note_text = note.read_text() if note.exists() else ""
        self.assertEqual(code, EXIT_GATE_REFUSED, err[-500:])
        self.assertLess(len(err), 2 * OUTPUT_CAP_BYTES, "tc printed past the cap")
        self.assertRegex(err, rf"tc kept the first {OUTPUT_CAP_BYTES} bytes of what {TARGET} printed on "
                              rf"(stdout and stderr|stderr and stdout), and dropped the rest")
        self.assertLess(len(note_text), 2 * OUTPUT_CAP_BYTES, "the note kept past the cap")
        self.assertIn(SHOWN_ESCAPE, note_text)
        self.assertNotIn(RAW_ESCAPE, note_text, "the note holds the far side's escape raw")

    def test_a_delivered_message_whose_far_filing_fails_is_filed_in_sent_with_the_far_warning(self):
        """Through the loopback fake's real far gate, with a regular file planted at the far mail/.origins: the send exits 0, the message lands far and is filed in sent/, never refused/, and the far warning that its id could not be filed reaches the sender; no traceback.

        The audit's MEDIUM-2. Must reject a far filing that fails after
        delivery with a traceback or an exit 1, which this side files as
        refused, with `nothing retries it`.

        @interacts  writes the loopback wrapper; plants one file in the far
                    mailbox; one tc card, one send.
        @deps       far_gate_ssh, assert_called, outbox.
        @complexity O(1).
        @alloc      one TcRoot and the far mailbox in its temp folder.
        """
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("ssh", 0)
            far = root.base / "far"
            (far / "mail").mkdir(parents=True)
            (far / "mail" / ".origins").write_text("planted\n")
            env = far_gate_ssh(root, folder, far)
            root.tc("card", "b", "--ssh", TARGET)
            code, out, err = root.tc("send", "--from", "a", "--to", "b", "hi", env=env)
            assert_called(self, folder, calls)
            filed = (outbox(root, "b", "sent"), outbox(root, "b", "refused"))
            landed = sorted(p.name for p in (far / "mail" / "to-b").glob("*.md"))
        self.assertEqual(code, 0, err)
        self.assertEqual(filed, (["000001-from-a.md"], []))
        self.assertEqual(landed, [f"000001-from-{FAR_KEY}.md"])
        self.assertIn(f"{TARGET} said: origin ", err)
        self.assertIn("could not be filed", err)
        self.assertNotIn("Traceback", err)


class BranchTest(unittest.TestCase):
    """SSH fix round 1 (Claude Opus 5.5, unreviewed): D32 and D33 part 1. This user's outbox branch, outbox/<login>/, is refused when it is not this user's own real folder, with words naming its owner and the one command that clears it, and tc health lists it.

    @interacts  see the module block.
    @deps       _root.TcRoot, load_tc, owner_patched_lstat.
    @complexity O(1) per test.
    @alloc      one TcRoot per test or case.
    """

    def test_a_branch_another_member_made_first_is_refused_with_words_and_health_lists_it(self):
        """In process, outbox/<login>/ made first by another member (os.lstat patched to say so): a send exits 1 naming that member, the user who ran init and `mv -T <branch> <aside>`, writes nothing in it and runs no ssh; tc health's `squatted` lists it with the same command. A send as a command afterwards reaches the fake.

        Must reject a send that takes a branch another member owns: that
        member could then move or remove every message in it (HIGH-1).

        @interacts  one tc card; makes the branch by hand; loads tc and
                    calls route_and_deliver and health_snapshot with
                    os.lstat patched for the branch; one send as a command.
        @deps       load_tc, owner_patched_lstat, branch, assert_called;
                    unittest.mock.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("ssh", 0)
            root.tc("card", "b", "--ssh", TARGET)
            mine = branch(root)
            mine.mkdir(parents=True)
            tc = load_tc(root)
            other, me = tc.user_name(os.geteuid() + 1), tc.user_name(os.geteuid())
            with mock.patch.dict(os.environ, {"PATH": root.env["PATH"]}), \
                    mock.patch.object(os, "lstat", owner_patched_lstat(mine)):
                got = tc.route_and_deliver("a", "b", "hi")
                squatted = tc.health_snapshot(gpu=False)["squatted"]
            written = sorted(mine.rglob("*"))
            not_called = not (folder.parent / "calls.jsonl").exists()
            good = root.tc("send", "--from", "a", "--to", "b", "hi")
            reachable = len(assert_called(self, folder, calls))
        fix = f"mv -T {mine} {mine.parent / ASIDE_NAME.format(name=login())}"
        self.assertEqual(got.exit, EXIT_REFUSED, got)
        self.assertIn(f"{mine} belongs to {other}, not to {me}", got.words)
        self.assertIn(f"The user who ran init ({me}) clears it with one command: {fix}", got.words)
        self.assertEqual(written, [], "a send wrote into a branch another member owns")
        self.assertTrue(not_called, "ssh ran for a send whose branch is not its sender's")
        self.assertEqual(squatted, [{"path": str(mine), "why": f"a folder {other} owns, not {login()}'s own branch",
                                     "fix": f"The user who ran init ({me}) runs: {fix}"}])
        self.assertEqual(good[0], 0, good)
        self.assertEqual(reachable, 1)

    def test_a_link_or_a_file_at_this_users_branch_name_is_refused_and_nothing_goes_through_it(self):
        """A symlink to a folder outside the root, or a regular file, at outbox/<login>: a send exits 1 with the words, ssh never runs, the link's folder stays empty; once the plant is moved aside (the words' own mv), the send reaches the fake.

        @interacts  per case: one tc card, a plant by hand, two sends,
                    one rename by hand.
        @deps       branch, assert_called; os.
        @complexity O(1): two cases.
        @alloc      one TcRoot per case.
        """
        for case in ("link", "file"):
            with self.subTest(case=case), _root.TcRoot() as root:
                folder, calls = root.fake_bin("ssh", 0)
                root.tc("card", "b", "--ssh", TARGET)
                mine = branch(root)
                mine.parent.mkdir()
                outside = root.base / "outside-folder"
                outside.mkdir()
                if case == "link":
                    mine.symlink_to(outside, target_is_directory=True)
                else:
                    mine.write_text("planted\n")
                code, out, err = root.tc("send", "--from", "a", "--to", "b", "hi")
                not_called = not (folder.parent / "calls.jsonl").exists()
                leaked = sorted(outside.rglob("*"))
                os.rename(mine, mine.parent / ASIDE_NAME.format(name=login()))
                good = root.tc("send", "--from", "a", "--to", "b", "hi")
                reachable = len(assert_called(self, folder, calls))
            what = "is a symlink, which tc never follows" if case == "link" else "is not a folder"
            self.assertEqual(code, EXIT_REFUSED, err)
            self.assertIn(f"{mine} {what}", err)
            self.assertTrue(not_called, "ssh ran for a send whose branch is a plant")
            self.assertEqual(leaked, [], "a send wrote through a link at its branch's name")
            self.assertEqual(good[0], 0, good)
            self.assertEqual(reachable, 1)


class SharedOutboxTest(UmaskTestCase):
    """The outbox on a shared mailbox (C4, D22, D32, D33): one branch per member at 2750, files the sender's alone, the send lock its owner's alone, and init finding all of it right.

    @interacts  see the module block.
    @deps       UmaskTestCase, primary_group, _root.TcRoot.
    @complexity O(1) per test.
    @alloc      one TcRoot per test.
    """

    def test_a_branch_and_its_folders_are_2750_its_files_0640_the_lock_0600_and_init_leaves_them(self):
        """Shared with the user's primary group: outbox/ is 3775; outbox/<login>/, to-b/, sent/ and refused/ are 2750 in the group; the messages, the note and the token are 0640; the send lock, in the branch, is 0600, and no lock is left in outbox/ itself; init run again exits 0, skips nothing and changes none of it.

        SSH fix round 1 (Claude Opus 5.5, unreviewed): D33 parts 1 and 2.
        Must reject a branch folder another member may write in (they
        could plant a folder or file in it), and a send lock another
        member may open (they could hold its flock through a read-only
        open, the audit's LOW-3).

        @interacts  tc init twice, one tc card, two sends (one refused,
                    one sent); lstats the outbox.
        @deps       primary_group, assert_called, queue, branch,
                    send_lock_path; os, stat.
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
            box = queue(root, "b")
            entries = {"outbox": root.path / "outbox", "branch": branch(root), "to-b": box, "sent": box / "sent",
                       "refused": box / "refused", "sent message": box / "sent" / "000002-from-a.md",
                       "refused message": box / "refused" / "000001-from-a.md",
                       "note": box / "refused" / "000001-from-a.md.stderr",
                       "token": root.path / "outbox" / ".origin-token",
                       "send lock": send_lock_path(root, TARGET)}
            stray = sorted(p.name for p in (root.path / "outbox").glob(".send-*"))
            missing = sorted(k for k, p in entries.items() if not os.path.lexists(p))
            entries = {k: p for k, p in entries.items() if k not in missing}
            before = {k: (stat.S_IMODE(os.lstat(p).st_mode), os.lstat(p).st_gid) for k, p in entries.items()}
            again = root.tc("init", "--shared", "--group", group)
            after = {k: (stat.S_IMODE(os.lstat(p).st_mode), os.lstat(p).st_gid) for k, p in entries.items()}
        self.assertEqual(init[0], 0, init)
        self.assertEqual(refused[0], EXIT_GATE_REFUSED, refused)
        self.assertEqual(sent[0], 0, sent)
        self.assertEqual(stray, [], "a send lock was left in outbox/ itself, where any member can reach it")
        self.assertEqual(missing, [], "not there")
        self.assertEqual(before["outbox"], (TOP_FOLDER_MODE, gid))
        for name in ("branch", "to-b", "sent", "refused"):
            self.assertEqual(before[name], (BRANCH_MODE, gid), f"{name}: {oct(before[name][0])}")
        for name in ("sent message", "refused message", "note", "token"):
            self.assertEqual(before[name], (OWNED_FILE_MODE, gid), f"{name}: {oct(before[name][0])}")
        self.assertEqual(before["send lock"], (SEND_LOCK_MODE, gid), oct(before["send lock"][0]))
        self.assertEqual(again[0], 0, again)
        self.assertNotIn("skipped", again[2])
        self.assertEqual(after, before)

    def test_another_member_can_move_rename_or_remove_nothing_in_a_branch_whoever_sent_first(self):
        """Shared: ben-member sent to far-b first (the folders that send makes, in the old shape and in D32's, made here by hand and counted as his); ann's send then queues. In the member model (POSIX's rules on the real modes, those folders his), he may rename or remove no entry of ann's queue or branch, nor the branch itself, may make no entry in any folder of it, and may neither open nor plant ann's send lock.

        SSH fix round 1 (Claude Opus 5.5, unreviewed): the audit's HIGH-1
        proof (D32, D33 parts 1 and 2). One Linux user cannot be refused
        by the kernel as another, so the test asks POSIX's rules of the
        real modes, with the owners patched as the SHARED tests patch
        them. Must reject ann's message in an outbox/to-far-b/ ben made:
        sticky never stops a folder's owner.

        @interacts  tc init, one tc card, one send (kept, ssh failing);
                    makes ben-member's folders by hand; lstats every entry
                    of ann's branch and the folders above her message.
        @deps       primary_group, assert_called, branch, send_lock_path,
                    seen_as, may, may_move_or_remove, may_make_in; os,
                    stat.
        @complexity O(e) over e entries of ann's branch (a handful).
        @alloc      one TcRoot.
        """
        _, group, gid = primary_group()
        ben, gids = os.geteuid() + 1, {gid}
        with _root.TcRoot() as root:
            init = root.tc("init", "--shared", "--group", group)
            folder, calls = root.fake_bin("ssh", SSH_CONNECT_FAILED, stderr=FAKE_CONNECT_STDERR)
            root.tc("card", "far-b", "--ssh", TARGET)
            top = root.path / "outbox"
            bens = [top / "to-far-b", top / OTHER_MEMBER, top / OTHER_MEMBER / "to-far-b"]
            for path in bens:
                path.mkdir()
            owners = {path: ben for path in bens}
            code, out, err = root.tc("send", "--from", "ann", "--to", "far-b", "from ann")
            assert_called(self, folder, calls)
            queued = [p for p in top.rglob("*-from-ann.md")]
            above = [p for q in queued for p in [q, *q.parents] if top in p.parents]
            mine = [branch(root), *branch(root).rglob("*")]
            moves = sorted({str(p) for p in above + mine
                            if may_move_or_remove(seen_as(p, owners), seen_as(p.parent, owners), ben, gids)})
            plants = sorted(str(p) for p in {*mine, *[p.parent for p in above]}
                            if os.path.isdir(p) and not os.path.islink(p)
                            and p != top and may_make_in(seen_as(p, owners), ben, gids))
            locks = sorted(top.rglob(".send-*"))
            opens = [str(p) for p in locks for bit in (MAY_READ, MAY_WRITE) if may(seen_as(p, owners), ben, gids, bit)]
        self.assertEqual(init[0], 0, init)
        self.assertEqual(code, EXIT_QUEUED, err)
        self.assertEqual(len(queued), 1, queued)
        self.assertEqual(moves, [], "ben-member may rename or remove these")
        self.assertEqual(plants, [], "ben-member may make an entry in these")
        self.assertEqual(opens, [], "ben-member may open ann's send lock")
        self.assertIn(branch(root), queued[0].parents, "ann's message is not in ann's branch")
        self.assertEqual(locks, [send_lock_path(root, TARGET)], "ann's send lock is not in ann's branch")


if __name__ == "__main__":
    unittest.main()
