"""
Tests for member trust in ssh cards (R10, decision D43, contract C4's
"Only your own or the init user's ssh card"). Under a shared mailbox the
ssh route, in `tc send` and in `tc flush`, follows a card only when the
card file tc opened (O_NOFOLLOW, then fstat on that open file) is a
regular file with one name, owned by the sending user or by the init
user (the owner of ROOT/.shared), and its `name` field is its file's
name. Anything else refuses, exit 1, nothing queued and no ssh run, with
words naming the card's writer and the init user. A queued file whose
card fails stays queued, never sent and never filed as refused, and goes
once the card is fixed. `tc health` and `tc cards` mark such a card. A
private mailbox is unchanged.

Model:  Claude Opus 5.5 (the R10 lane agent), 2026-10-17
Status: unreviewed

One Linux user plays every part. Where the sender, the init user and
another member must differ, tc runs in process and os.lstat, os.fstat
and os.stat report ROOT and its .shared as the init user's (the running
user's id plus one), each file named as the init user's the same, and
each file named as another member's (ben, the running user's id plus
two), by (st_dev, st_ino), as tests/test_wake_files.py's
members_patched does. The running user is then ann, a member who did
not run init. Where the running user's own run is enough (a link, a
second name, a card naming another name), tc runs as a command, and the
running user is then the init user too. Real ssh never runs (rule 5):
every send puts tests/_root.py's fake ssh first on PATH, and every test
that asserts the fake was not called calls it in the same root
afterwards, as a positive control.

@interacts  runs ../tc through tests/_root.py under a throwaway TC_ROOT
            (init --shared with the running user's primary group, card,
            send, flush, cards, health, gate), with a fake ssh that
            records its argv and stdin; writes cards by hand in cards/,
            a symlink, hard links and a card outside cards/ in the
            root's temp folder; loads tc as a module (TC_ROOT set for
            the load and put back) and runs cmd_send, cmd_flush,
            cmd_cards, cmd_health and health_snapshot in process with
            os.lstat, os.fstat and os.stat patched (owners_patched),
            PATH set to the root's, sys.argv[0] set to tc and tc's
            gpu_stats replaced; captures stdout and stderr. Writes
            nothing outside the root's temp folder.
@deps       python3 stdlib (argparse, contextlib, json, os, pathlib,
            pwd, stat, sys, unittest, unittest.mock); tests/_root.py;
            UmaskTestCase, load_tc and primary_group from
            test_shared.py; run_in_process from test_wake_files.py;
            TARGET, FAKE_CONNECT_STDERR, SSH_CONNECT_FAILED,
            assert_called, outbox and queue from test_ssh_route.py;
            ../tc.
@complexity O(1) per test: a handful of tc runs and fake calls per
            root, a few dozen entries per root; the hard link test has
            three cases, the private test five, each a fresh root.
@alloc      one TcRoot per test or case, removed when its context exits,
            and one module per in-process run.
"""

import argparse
import contextlib
import json
import os
import pathlib
import pwd
import stat
import sys
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
# Run as `python3 -m unittest tests.test_ssh_card_trust` from the repo root,
# tests/ is not on sys.path; under discover it is. Add it once so both work.
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import _root  # noqa: E402  (needs the path line above)
from test_shared import UmaskTestCase, load_tc, primary_group  # noqa: E402
from test_ssh_route import (FAKE_CONNECT_STDERR, SSH_CONNECT_FAILED, TARGET, assert_called,  # noqa: E402
                            outbox, queue)
from test_wake_files import run_in_process  # noqa: E402

# The names. Made up. ann is the sender; far-x, far-y and far-z are names
# on another machine; ben is the other member (a user id, not a name).
SENDER = "ann"
FAR_X, FAR_Y, FAR_Z = "far-x", "far-y", "far-z"
# The user ids the patched stats report: the init user one up from the
# running user, another member two up (test_wake_files's HOLDER_UID_STEP).
INIT_UID_STEP = 1
MEMBER_UID_STEP = 2
# Exit codes (contracts.md): refused with words, kept in the outbox.
EXIT_REFUSED = 1
EXIT_QUEUED = 4
# The gate's health command and a far key's name (C3). Made up.
GATE_HEALTH = "/x/tc health --json"
GATE_KEY = "farkey"
# C4's words for D43, written here rather than read from tc. Why a card
# fails, one clause per kind, joined by WHY_JOIN when several do.
WHY_NOT_OWN = "is an ssh card {writer} wrote, and only {writer} and the user who ran init ({init}) send over it"
WHY_LINK = ("is a symlink {writer} made, and tc follows no card through a link, even one to a card of the user "
            "who ran init ({init})")
WHY_SECOND_NAME = "is a card {writer} owns with a second name (a hard link), and tc follows only a card with one name"
WHY_OTHER_NAME = "names {said}, not {name} (written by {writer}), and tc follows a card only for the name it names"
WHY_JOIN = "; it "
FIX_WORDS = ("The user who ran init ({init}) can write it for everyone: tc card {name} --ssh <target>. Or write "
             "your own card under a name of your own: tc card <your-name> --ssh <target>.")
SEND_WORDS = "tc send: {path} {why}. Nothing sent and no ssh run. {fix}\n"
FLUSH_WORDS = ("tc flush: left {file}: {path} {why}. It stays queued, never sent and never filed as refused, and "
               "goes on the next tc flush once the card is fixed. {fix}\n")
# What tc health and tc cards mark a card with, one per kind, joined by
# MARK_JOIN, after the card's line and MARK_JOIN.
MARK_NOT_OWN = "ssh card by {writer}: only its writer and {init} send over it"
MARK_LINK = "a symlink by {writer}: no ssh send follows it"
MARK_SECOND_NAME = "a card by {writer} with a second name (a hard link): no ssh send follows it"
MARK_OTHER_NAME = "names {said}, not {name}: no ssh send follows it"
MARK_JOIN = "; "
# A private mailbox's refusal of a linked card, as before R10.
PRIVATE_LINK_WORDS = ("tc send: the card {path} is unreadable (it is a symlink, which tc never follows); "
                      "nothing sent.")
# What a card in health --json reads as when it has no ssh_trust key at all.
NO_TRUST_KEY = "no ssh_trust key"
# Words that only D43's refusals and marks say.
D43_ONLY = ("the user who ran init", "no ssh send follows it", "only its writer")


def card_path(root, name):
    """cards/<name>.json under the root.

    @interacts  none.
    @deps       pathlib.
    @complexity O(1).
    @alloc      one path, returned.
    """
    return root.path / "cards" / f"{name}.json"


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
def owners_patched(root_path, init=(), member=()):
    """While entered, os.lstat, os.fstat and os.stat report ROOT and its .shared (when there) and each path in `init` as the init user's (INIT_UID_STEP up), and each path in `member` as another member's (MEMBER_UID_STEP up), matched by (st_dev, st_ino), so a hard link reads as its file's owner and a symlink's own entry as the link's.

    One Linux user cannot make a file another user owns, so the owner is
    shown by what tc's stats report, as the SHARED suites do.

    @interacts  patches os.lstat, os.fstat and os.stat while entered;
                lstats ROOT, .shared and each path once, on entry.
    @deps       os, stat, unittest.mock; identity.
    @complexity O(1) per call.
    @alloc      two sets; the patches, undone on exit; one stat result per
                call.
    """
    me = os.geteuid()
    tops = [p for p in (root_path, root_path / ".shared") if os.path.lexists(p)]
    init_ids = {identity(p) for p in [*tops, *init]}
    member_ids = {identity(p) for p in member}
    real_lstat, real_fstat, real_stat = os.lstat, os.fstat, os.stat

    def owned(st):
        key = (st.st_dev, st.st_ino)
        step = INIT_UID_STEP if key in init_ids else MEMBER_UID_STEP if key in member_ids else None
        if step is None:
            return st
        fields = list(st[:stat.ST_CTIME + 1])
        fields[stat.ST_UID] = me + step
        return os.stat_result(fields)

    def lstat(path, *args, **kwargs):
        return owned(real_lstat(path, *args, **kwargs))

    def fstat(fd):
        return owned(real_fstat(fd))

    def stat_(path, *args, **kwargs):
        return owned(real_stat(path, *args, **kwargs))

    with mock.patch.object(os, "lstat", lstat), mock.patch.object(os, "fstat", fstat), \
            mock.patch.object(os, "stat", stat_):
        yield


def in_process(root, tc, call, init=(), member=()):
    """Run `call` (one of tc's cmd_* functions, bound to its arguments) in process with the owners patched, PATH the root's (its fake ssh first) and sys.argv[0] tc: (code, out, err).

    @interacts  patches os.environ's PATH, sys.argv and the stats while it
                runs; tc's gpu_stats replaced; runs `call`.
    @deps       owners_patched, run_in_process; unittest.mock, os, sys.
    @complexity O(1), plus the call.
    @alloc      the captured text, returned.
    """
    with owners_patched(root.path, init, member), \
            mock.patch.dict(os.environ, {"PATH": root.env["PATH"]}), \
            mock.patch.object(sys, "argv", ["tc"]), \
            mock.patch.object(tc, "gpu_stats", lambda: None):
        return run_in_process(call)


def send(tc, to, sender=SENDER):
    """A call of tc's cmd_send for one message to `to`, for in_process.

    @interacts  none until called.
    @deps       argparse.
    @complexity O(1).
    @alloc      one Namespace and one closure, returned.
    """
    return lambda: tc.cmd_send(argparse.Namespace(sender=sender, to=to, message="hi", origin=None))


def flush(tc):
    """A call of tc's cmd_flush with no --to, for in_process.

    @interacts  none until called.
    @deps       argparse.
    @complexity O(1).
    @alloc      one Namespace and one closure, returned.
    """
    return lambda: tc.cmd_flush(argparse.Namespace(to=None))


def not_called(folder):
    """True when the fake whose bin/ is `folder` has recorded no call: its record file is not there.

    @interacts  stats one file.
    @deps       pathlib.
    @complexity O(1).
    @alloc      none.
    """
    return not (folder.parent / "calls.jsonl").exists()


def nothing_queued(root, to):
    """True when this user's outbox holds no message for `to`: none waiting, sent or refused.

    @interacts  lists up to three folders.
    @deps       outbox.
    @complexity O(f) over f files there (none, when it passes).
    @alloc      three short lists.
    """
    return not (outbox(root, to) or outbox(root, to, "sent") or outbox(root, to, "refused"))


def words(template, *whys, **fields):
    """D43's refusal for `template` (SEND_WORDS or FLUSH_WORDS): the whys joined by WHY_JOIN, then FIX_WORDS, every field filled from `fields`.

    @interacts  none; string work only.
    @deps       FIX_WORDS, WHY_JOIN.
    @complexity O(1).
    @alloc      one string, returned.
    """
    why = WHY_JOIN.join(w.format(**fields) for w in whys)
    return template.format(why=why, fix=FIX_WORDS.format(**fields), **fields)


def own_login():
    """The running user's login, as tc's user_name gives it: the init user and the writer when tc runs as a command.

    @interacts  reads the user database.
    @deps       pwd, os.
    @complexity O(1).
    @alloc      one short string, returned.
    """
    try:
        return pwd.getpwuid(os.geteuid()).pw_name
    except KeyError:
        return str(os.geteuid())


class SharedCase(UmaskTestCase):
    """A shared mailbox (the running user's primary group) with a fake ssh, for every test here.

    @interacts  see the module block.
    @deps       UmaskTestCase, primary_group, _root.TcRoot.
    @complexity O(1) per test.
    @alloc      one TcRoot per test.
    """

    def shared(self, root, ssh_codes=0, stderr=""):
        """Share `root` with the running user's primary group and put a fake ssh first on its PATH: (folder, calls).

        @interacts  one tc init; writes the fake.
        @deps       primary_group; _root.TcRoot.tc and fake_bin.
        @complexity O(1).
        @alloc      the fake's folder.
        """
        _, group, _ = primary_group()
        self.assertEqual(root.tc("init", "--shared", "--group", group)[0], 0)
        return root.fake_bin("ssh", ssh_codes, stderr=stderr)

    def card(self, root, name, target=TARGET):
        """`tc card <name> --ssh <target>` as the running user: the card's path.

        @interacts  one tc run.
        @deps       _root.TcRoot.tc; card_path.
        @complexity O(1).
        @alloc      one card file.
        """
        code, out, err = root.tc("card", name, "--ssh", target)
        self.assertEqual(code, 0, err)
        return card_path(root, name)


class SshCardTrustTest(SharedCase):
    """The ssh route under a shared mailbox follows only the sender's own or the init user's card, with one name, named for its own name (D43).

    @interacts  see the module block.
    @deps       SharedCase, load_tc, in_process, send, words,
                assert_called, not_called, nothing_queued.
    @complexity O(1) per test.
    @alloc      one TcRoot per test or case.
    """

    def test_the_senders_own_ssh_card_is_sent(self):
        """ann, a member who did not run init, sends to her own ssh card: exit 0, the fake ssh called once, to its target.

        @interacts  init, one tc card; one send in process.
        @deps       SharedCase.shared, SharedCase.card, load_tc, in_process,
                    send, assert_called.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        with _root.TcRoot() as root:
            folder, calls = self.shared(root)
            self.card(root, FAR_X)
            tc = load_tc(root)
            code, out, err = in_process(root, tc, send(tc, FAR_X))
            seen = assert_called(self, folder, calls)
        self.assertEqual(code, 0, err)
        self.assertEqual(len(seen), 1)
        self.assertIn(TARGET, seen[0]["argv"])

    def test_the_init_users_card_is_sent(self):
        """ann sends to a card the init user wrote: exit 0, the fake ssh called once.

        Must reject a rule that follows only the sender's own card: the
        init user writes cards for everyone (C4, D34).

        @interacts  init, one tc card; one send in process with the card
                    read as the init user's.
        @deps       SharedCase.shared, SharedCase.card, load_tc, in_process,
                    send, assert_called.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        with _root.TcRoot() as root:
            folder, calls = self.shared(root)
            path = self.card(root, FAR_X)
            tc = load_tc(root)
            code, out, err = in_process(root, tc, send(tc, FAR_X), init=[path])
            seen = assert_called(self, folder, calls)
        self.assertEqual(code, 0, err)
        self.assertEqual(len(seen), 1)

    def test_another_members_card_is_refused_with_words_and_the_senders_own_goes(self):
        """ben wrote the ssh card for far-y: ann's send exits 1 with C4's words naming ben and the init user, queues nothing and runs no ssh; then, in the same root, her send to her own far-x calls the fake.

        Must reject a send that runs the sender's ssh to a target and a
        remote program another member chose (D43).

        @interacts  init, two tc cards; two sends in process, far-y read as
                    ben's.
        @deps       SharedCase.shared, SharedCase.card, load_tc, in_process,
                    send, words, not_called, nothing_queued, assert_called.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        me = os.geteuid()
        with _root.TcRoot() as root:
            folder, calls = self.shared(root)
            theirs = self.card(root, FAR_Y)
            self.card(root, FAR_X)
            tc = load_tc(root)
            refused = in_process(root, tc, send(tc, FAR_Y), member=[theirs])
            silent, empty = not_called(folder), nothing_queued(root, FAR_Y)
            good = in_process(root, tc, send(tc, FAR_X), member=[theirs])
            reachable = len(assert_called(self, folder, calls))
            ben, init = tc.user_name(me + MEMBER_UID_STEP), tc.user_name(me + INIT_UID_STEP)
        self.assertEqual(refused, (EXIT_REFUSED, "", words(SEND_WORDS, WHY_NOT_OWN, path=theirs, writer=ben,
                                                           init=init, name=FAR_Y)))
        self.assertTrue(silent, "ssh ran over another member's card")
        self.assertTrue(empty, "a refused send queued its message")
        self.assertEqual(good[0], 0, good)
        self.assertEqual(reachable, 1)

    def test_a_symlink_to_the_init_users_card_is_refused_and_never_followed(self):
        """cards/far-y.json a symlink ben made, to the init user's far-x card, or to an init user's card named far-y outside cards/: ann's send exits 1 with the link's words, no ssh; her send to far-x then calls the fake (a2's add 1).

        The second target passes every other check (one name, the init
        user's, its own name), so only the no-follow open refuses it.

        @interacts  per case: init, one tc card, a card and a symlink by
                    hand; two sends in process.
        @deps       SharedCase.shared, SharedCase.card, load_tc, in_process,
                    send, words, not_called, nothing_queued, assert_called.
        @complexity O(1): two cases.
        @alloc      one TcRoot and one module per case.
        """
        me = os.geteuid()
        for case in ("to far-x", "to a far-y card outside cards/"):
            with self.subTest(case=case):
                with _root.TcRoot() as root:
                    folder, calls = self.shared(root)
                    real = self.card(root, FAR_X)
                    if case == "to far-x":
                        target = real
                    else:
                        target = root.base / f"{FAR_Y}.json"
                        target.write_text(real.read_text().replace(f'"name": "{FAR_X}"', f'"name": "{FAR_Y}"'))
                    link = card_path(root, FAR_Y)
                    link.symlink_to(target)
                    tc = load_tc(root)
                    refused = in_process(root, tc, send(tc, FAR_Y), init=[real, target], member=[link])
                    silent, empty = not_called(folder), nothing_queued(root, FAR_Y)
                    good = in_process(root, tc, send(tc, FAR_X), init=[real, target], member=[link])
                    reachable = len(assert_called(self, folder, calls))
                    ben, init = tc.user_name(me + MEMBER_UID_STEP), tc.user_name(me + INIT_UID_STEP)
                self.assertEqual(refused, (EXIT_REFUSED, "", words(SEND_WORDS, WHY_LINK, path=link, writer=ben,
                                                                   init=init, name=FAR_Y)))
                self.assertTrue(silent, "ssh ran through a linked card")
                self.assertTrue(empty, "a refused send queued its message")
                self.assertEqual(good[0], 0, good)
                self.assertEqual(reachable, 1)

    def test_a_hard_link_is_refused_by_its_second_name_and_by_its_name_field_each_alone(self):
        """As a command (the running user the init user): far-x's card hard-linked as cards/far-y.json is refused naming both its second name and its name field; a far-y card with a second name outside cards/ by its second name alone; a one-name copy of far-x's card at cards/far-y.json by its name field alone. Each exits 1, no ssh; a send to a third card then calls the fake (a2's add 2).

        Each check is shown alone: the second case has the right name
        field and the third one name, so a tc without the other check
        still refuses each, and the first names both whys.

        @interacts  per case: init, two tc cards, one hard link or file
                    by hand, two sends.
        @deps       SharedCase.shared, SharedCase.card, words, not_called,
                    nothing_queued, assert_called; os.
        @complexity O(1): three cases.
        @alloc      one TcRoot per case.
        """
        me = own_login()
        cases = {"far-x hard-linked as far-y": (WHY_SECOND_NAME, WHY_OTHER_NAME),
                 "a far-y card with a second name outside cards/": (WHY_SECOND_NAME,),
                 "a one-name copy of far-x's card as far-y": (WHY_OTHER_NAME,)}
        for case, whys in cases.items():
            with self.subTest(case=case):
                with _root.TcRoot() as root:
                    folder, calls = self.shared(root)
                    real = self.card(root, FAR_X)
                    self.card(root, FAR_Z)
                    at = card_path(root, FAR_Y)
                    if case.startswith("far-x"):
                        os.link(real, at)
                    elif case.startswith("a far-y"):
                        self.card(root, FAR_Y)
                        os.link(at, root.base / f"{FAR_Y}-second-name.json")
                    else:
                        at.write_text(real.read_text())
                    code, out, err = root.tc("send", "--from", SENDER, "--to", FAR_Y, "hi")
                    silent, empty = not_called(folder), nothing_queued(root, FAR_Y)
                    good = root.tc("send", "--from", SENDER, "--to", FAR_Z, "hi")
                    reachable = len(assert_called(self, folder, calls))
                said = FAR_X if WHY_OTHER_NAME in whys else FAR_Y
                self.assertEqual((code, out, err), (EXIT_REFUSED, "", words(SEND_WORDS, *whys, path=at, writer=me,
                                                                               init=me, name=FAR_Y, said=said)))
                self.assertTrue(silent, "ssh ran over a card with a second name or another name's card")
                self.assertTrue(empty, "a refused send queued its message")
                self.assertEqual(good[0], 0, good)
                self.assertEqual(reachable, 1)

    def test_a_card_whose_name_field_differs_from_its_file_name_is_refused(self):
        """As a command: the running user's own card at cards/far-y.json saying name far-x, one name: exit 1 naming far-x, no ssh; the send to far-x itself then calls the fake.

        @interacts  init, one tc card, one file by hand, two sends.
        @deps       SharedCase.shared, SharedCase.card, words, not_called,
                    nothing_queued, assert_called.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        me = own_login()
        with _root.TcRoot() as root:
            folder, calls = self.shared(root)
            real = self.card(root, FAR_X)
            at = card_path(root, FAR_Y)
            at.write_text(real.read_text())
            refused = root.tc("send", "--from", SENDER, "--to", FAR_Y, "hi")
            silent, empty = not_called(folder), nothing_queued(root, FAR_Y)
            good = root.tc("send", "--from", SENDER, "--to", FAR_X, "hi")
            reachable = len(assert_called(self, folder, calls))
        self.assertEqual(refused, (EXIT_REFUSED, "", words(SEND_WORDS, WHY_OTHER_NAME, path=at, writer=me, init=me,
                                                           name=FAR_Y, said=FAR_X)))
        self.assertTrue(silent, "ssh ran over a card naming another name")
        self.assertTrue(empty)
        self.assertEqual(good[0], 0, good)
        self.assertEqual(reachable, 1)


class FlushTrustTest(SharedCase):
    """tc flush applies the same check per target: a queued file whose card fails stays queued with the words and goes once the card is fixed (D43).

    @interacts  see the module block.
    @deps       SharedCase, load_tc, in_process, flush, words, outbox,
                queue, assert_called.
    @complexity O(1) per test.
    @alloc      one TcRoot per test.
    """

    def test_a_queued_file_whose_card_fails_stays_queued_and_goes_once_the_card_is_fixed(self):
        """ann's message to far-y waits (ssh failed once); far-y's card now reads as ben's: flush exits 4 with the words, runs no ssh, and the file stays waiting, nothing in refused/; the card now the init user's: flush sends it, exit 0, the fake called again, the file in sent/.

        Must reject a flush that sends queued mail over another member's
        card, and one that files such mail as refused for good.

        @interacts  init, one tc card, one send (kept: the fake exits 255
                    first); two flushes in process.
        @deps       SharedCase.shared, SharedCase.card, load_tc, in_process,
                    flush, words, outbox, queue, assert_called.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        me = os.geteuid()
        with _root.TcRoot() as root:
            folder, calls = self.shared(root, [SSH_CONNECT_FAILED, 0], stderr=FAKE_CONNECT_STDERR)
            path = self.card(root, FAR_Y)
            kept = root.tc("send", "--from", SENDER, "--to", FAR_Y, "hi")
            tries = len(assert_called(self, folder, calls))
            waiting = queue(root, FAR_Y) / "000001-from-ann.md"
            tc = load_tc(root)
            left = in_process(root, tc, flush(tc), member=[path])
            after_left = (len(calls()), outbox(root, FAR_Y), outbox(root, FAR_Y, "refused"))
            fixed = in_process(root, tc, flush(tc), init=[path])
            after_fixed = (len(calls()), outbox(root, FAR_Y), outbox(root, FAR_Y, "sent"))
            ben, init = tc.user_name(me + MEMBER_UID_STEP), tc.user_name(me + INIT_UID_STEP)
        self.assertEqual(kept[0], EXIT_QUEUED, kept)
        self.assertEqual(tries, 1)
        self.assertEqual(left[0], EXIT_QUEUED, left)
        self.assertIn(words(FLUSH_WORDS, WHY_NOT_OWN, file=waiting, path=path, writer=ben, init=init, name=FAR_Y),
                      left[2])
        self.assertEqual(after_left, (1, [waiting.name], []), "flush ran ssh over, or filed away, mail to ben's card")
        self.assertEqual(fixed[0], 0, fixed)
        self.assertEqual(after_fixed, (2, [], [waiting.name]))


class PrivateMailboxTest(UmaskTestCase):
    """A private mailbox is unchanged (C4, D43): another user's card, a hard link and a card naming another name are all sent as before, a queued file to one is flushed, and a linked card is refused with the words it had before R10.

    @interacts  see the module block.
    @deps       UmaskTestCase, load_tc, in_process, send, flush,
                assert_called, card_path.
    @complexity O(1) per case.
    @alloc      one TcRoot per case.
    """

    def test_every_shared_only_rule_behaves_as_before_on_a_private_mailbox(self):
        """No .shared: a card read as another user's, far-x hard-linked as far-y, and a one-name copy of far-x's card as far-y are each sent (the fake called); a message kept for a card read as another user's is flushed; a symlink is refused, exit 1, with the old words and none of D43's.

        @interacts  per case: one or two tc cards, a link or a file by
                    hand, one send or a send and a flush in process.
        @deps       load_tc, in_process, send, flush, assert_called,
                    card_path; os.
        @complexity O(1): five cases.
        @alloc      one TcRoot and one module per case.
        """
        for case in ("another user's card", "a hard link", "another name's card", "flush over another user's card",
                     "a symlink"):
            with self.subTest(case=case):
                with _root.TcRoot() as root:
                    codes = [SSH_CONNECT_FAILED, 0] if case.startswith("flush") else 0
                    folder, calls = root.fake_bin("ssh", codes, stderr=FAKE_CONNECT_STDERR)
                    self.assertEqual(root.tc("card", FAR_X, "--ssh", TARGET)[0], 0)
                    real, at = card_path(root, FAR_X), card_path(root, FAR_Y)
                    member = []
                    if case in ("another user's card", "flush over another user's card"):
                        self.assertEqual(root.tc("card", FAR_Y, "--ssh", TARGET)[0], 0)
                        member = [at]
                    elif case == "a hard link":
                        os.link(real, at)
                    elif case == "another name's card":
                        at.write_text(real.read_text())
                    else:
                        at.symlink_to(real)
                    tc = load_tc(root)
                    if case.startswith("flush"):
                        self.assertEqual(root.tc("send", "--from", SENDER, "--to", FAR_Y, "hi")[0], EXIT_QUEUED)
                        code, out, err = in_process(root, tc, flush(tc), member=member)
                        seen = len(assert_called(self, folder, calls))
                        want = 2
                    else:
                        code, out, err = in_process(root, tc, send(tc, FAR_Y), member=member)
                        seen = 0 if not_called(folder) else len(calls())
                        want = 0 if case == "a symlink" else 1
                    good = root.tc("send", "--from", SENDER, "--to", FAR_X, "hi")
                    reachable = len(assert_called(self, folder, calls))
                if case == "a symlink":
                    self.assertEqual(code, EXIT_REFUSED, err)
                    self.assertTrue(err.startswith(PRIVATE_LINK_WORDS.format(path=at)), err)
                else:
                    self.assertEqual(code, 0, err)
                self.assertFalse([w for w in D43_ONLY if w in out + err], out + err)
                self.assertEqual(seen, want)
                self.assertEqual(good[0], 0, good)
                self.assertEqual(reachable, want + 1)


class MarkedTest(SharedCase):
    """tc health and tc cards mark a card the ssh route will not follow, so nobody learns of it from a failed send, and the gate's health never shows one (D43, D36, D37).

    @interacts  see the module block.
    @deps       SharedCase, load_tc, in_process, card_path.
    @complexity O(1) per test.
    @alloc      one TcRoot per test.
    """

    def test_health_and_cards_mark_each_card_that_fails_and_none_on_a_private_mailbox(self):
        """Shared, ann a member: her own far-x, ben's far-m, ben's symlink far-l, a far-h with a second name outside cards/ (the init user's), and her one-name far-n naming far-x. tc cards and tc health say each one's mark after its line, health --json carries it as ssh_trust; the init user's card with one name carries none. On a private mailbox nothing is marked and ssh_trust is null.

        @interacts  init, five tc cards, a link, a hard link and a file by
                    hand; cmd_cards, cmd_health and health_snapshot in
                    process; on a private root, one tc card, tc cards and
                    tc health --json as commands.
        @deps       SharedCase.shared, SharedCase.card, load_tc, in_process,
                    card_path; json, os.
        @complexity O(1).
        @alloc      two TcRoots and one module.
        """
        me = os.geteuid()
        with _root.TcRoot() as root:
            self.shared(root)
            own = self.card(root, FAR_X)
            bens = self.card(root, "far-m")
            twice = self.card(root, "far-h")
            os.link(twice, root.base / "far-h-second-name.json")
            inits = self.card(root, "far-i")
            link = card_path(root, "far-l")
            link.symlink_to(own)
            copy = card_path(root, "far-n")
            copy.write_text(own.read_text())
            tc = load_tc(root)
            patched = {"init": [twice, inits], "member": [bens, link]}
            cards = in_process(root, tc, lambda: tc.cmd_cards(argparse.Namespace()), **patched)
            health = in_process(root, tc, lambda: tc.cmd_health(argparse.Namespace(json=False)), **patched)
            with owners_patched(root.path, **patched), mock.patch.object(tc, "gpu_stats", lambda: None):
                snap = {c["name"]: c.get("ssh_trust", NO_TRUST_KEY) for c in tc.health_snapshot()["cards"]}
            ann, ben, init = tc.user_name(me), tc.user_name(me + MEMBER_UID_STEP), tc.user_name(me + INIT_UID_STEP)
        marks = {FAR_X: MARK_NOT_OWN.format(writer=ann, init=init),
                 "far-m": MARK_NOT_OWN.format(writer=ben, init=init),
                 "far-h": MARK_SECOND_NAME.format(writer=init),
                 "far-i": None,
                 "far-l": MARK_LINK.format(writer=ben),
                 "far-n": MARK_JOIN.join([MARK_NOT_OWN.format(writer=ann, init=init),
                                          MARK_OTHER_NAME.format(said=FAR_X, name="far-n")])}
        self.assertEqual(cards[0], 0, cards)
        self.assertEqual(health[0], 0, health)
        self.assertEqual(snap, marks)
        for name, mark in marks.items():
            with self.subTest(card=name):
                if name == "far-l":
                    self.assertIn(f"\nfar-l.json: unreadable card{MARK_JOIN}{mark}\n", "\n" + cards[1])
                    self.assertIn(f"far-l (?, account ?, route ?){MARK_JOIN}{mark}\n", health[1])
                    continue
                said = ", card says name far-x" if name == "far-n" else ""
                line = f"{name} (other, account unknown, route ssh to {TARGET}){said}"
                if mark is None:
                    self.assertIn(f"\n{line}\n", "\n" + cards[1])
                    self.assertIn(f"{name} (other, account unknown, route ssh to {TARGET})\n", health[1])
                else:
                    self.assertIn(f"\n{line}{MARK_JOIN}{mark}\n", "\n" + cards[1])
                    self.assertIn(f"{name} (other, account unknown, route ssh to {TARGET}){MARK_JOIN}{mark}\n",
                                  health[1])
        with _root.TcRoot() as private:
            self.assertEqual(private.tc("card", FAR_X, "--ssh", TARGET)[0], 0)
            os.link(card_path(private, FAR_X), card_path(private, FAR_Y))
            listed = private.tc("cards")
            code, out, err = private.tc("health", "--json")
        self.assertEqual(code, 0, err)
        self.assertEqual([c.get("ssh_trust", NO_TRUST_KEY) for c in json.loads(out)["cards"]], [None, None])
        self.assertFalse([w for w in D43_ONLY if w in listed[1] + listed[2]], listed)

    def test_the_gates_health_never_shows_a_mark_or_a_card(self):
        """Shared, far-x hard-linked as far-y: tc health marks both, and the gate's health --json for a far key has no cards key and none of the mark's words.

        Must reject a mark that reaches a far key: it names a login and
        a card (D16, D36 part 5, D37).

        @interacts  init, one tc card, one hard link by hand; tc health
                    and tc gate as commands.
        @deps       SharedCase.shared, SharedCase.card, card_path; json, os.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        me = own_login()
        with _root.TcRoot() as root:
            self.shared(root)
            os.link(self.card(root, FAR_X), card_path(root, FAR_Y))
            home = root.tc("health")
            code, out, err = root.tc("gate", "--as", GATE_KEY, env={"SSH_ORIGINAL_COMMAND": GATE_HEALTH})
        mark = MARK_SECOND_NAME.format(writer=me)
        self.assertEqual(home[0], 0, home)
        self.assertEqual(home[1].count(mark), 2, home[1])
        self.assertEqual(code, 0, err)
        self.assertNotIn("cards", json.loads(out))
        self.assertFalse([w for w in (*D43_ONLY, "second name") if w in out + err], out + err)


if __name__ == "__main__":
    unittest.main()
