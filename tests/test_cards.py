"""
Tests for address cards (CARDS R2, contract C1): `tc join`, `tc card` and
`tc cards`. What a join reads, what a card holds, what is refused, and that
a card is written whole.

Model:  Claude Opus 5.5 (the CARDS lane agent), 2026-10-14
Status: unreviewed

@interacts  runs ../tc through tests/_root.py under a throwaway TC_ROOT.
            Every identity variable a test needs is passed in that call's
            env; the harness drops the session's own. Two white-box tests
            load tc as a module (TC_ROOT set to the harness root first, put
            back after) and call cmd_join in process: one wraps os.environ
            in a recorder, one wraps pathlib.Path.write_text, rename and
            os.open. Both patches end with the test. A third plants a
            symlink at the card's .tmp name, pointing at a file in the
            harness's temp folder, which the join must refuse to write
            through. One test holds the inbox lock itself and reads
            /proc/locks, to see that tc card counts and writes under it.
            Four tests (phase fix round 1, Claude Opus 5.5, unreviewed)
            write hand-made cards: control characters in fields and a file
            name, a card copied under another name, a card nested
            DEEP_NESTING deep, and a FIFO or a symlink at a card's name
            (each tc run then has CARD_READ_CEILING_SECONDS, so a read
            that blocks fails instead of hanging).
@deps       python3 stdlib (argparse, collections.abc, contextlib, fcntl,
            importlib, io, json, os, pathlib, subprocess, sys, unittest,
            unittest.mock); tests/_root.py; FINISH_CEILING_SECONDS and
            wait_until_blocked from test_codex_route.py; ../tc.
@complexity O(1) per test: one to six tc runs, each under a second.
@alloc      one TcRoot per test (or per case), removed when its context
            exits. Nothing is kept between tests.
"""

import argparse
import collections.abc
import contextlib
import fcntl
import importlib.machinery
import importlib.util
import io
import json
import os
import pathlib
import subprocess
import sys
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
# Run as `python3 -m unittest tests.test_cards` from the repo root, tests/
# is not on sys.path; under discover it is. Add it once so both work.
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import _root  # noqa: E402  (needs the path line above)
# CARDS fix round 1 (Claude Opus 5.5, unreviewed): one copy of the lock helpers.
from test_codex_route import FINISH_CEILING_SECONDS, wait_until_blocked  # noqa: E402

# C1's fields, in its order. Written here, not read from tc.
CARD_FIELDS = ["version", "name", "kind", "account", "route", "session_id", "pid",
               "thread_id", "ssh", "reports_to", "joined_at"]
# The only environment variables `tc join` may read (C1).
JOIN_READS = {"CODEX_THREAD_ID", "CLAUDECODE", "CLAUDE_CODE_SESSION_ID", "CLAUDE_PID",
              "CLAUDE_CONFIG_DIR"}
DEFAULT_REMOTE_TC = "~/TheConnection/tc"
EXIT_REFUSED = 1
EXIT_BAD_NAME = 6
BAD_NAME_WORDS =('tc: bad name "{name}": letters, digits, dot, dash, underscore, '
                  '1 to 64, not starting with a dash\n')
# A planted value that must never reach a card. Made up for the test.
SECRET = "secret123"
# A joined_at from long before any test run, to see a rejoin replace it.
OLD_JOINED_AT = "2000-01-01T00:00:00+00:00"
CLAUDE_ENV = {"CLAUDECODE": "1", "CLAUDE_CODE_SESSION_ID": "s1", "CLAUDE_PID": "9"}
# Phase fix round 1 (Claude Opus 5.5, unreviewed): hand-made cards for the
# escaping, naming and nesting checks.
# ESC and BEL, two bytes a terminal acts on, and how tc must print each.
ESC, BEL = "\x1b", "\x07"
ESC_SHOWN, BEL_SHOWN = "\\x1b", "\\x07"
# Deep enough that json.loads raises RecursionError, not ValueError (it
# does from about 10,000 here), and small enough, 2 x 20,000 bytes, to stay
# under tc's 64 KiB card read cap, so the parser refuses it, not the cap.
DEEP_NESTING = 20000
# How long tc cards, tc health or a send may take with a FIFO or a symlink
# at a card's name. Each runs in about 0.1 s; a read that blocks on the
# FIFO never returns, so the ceiling turns that into a failure.
CARD_READ_CEILING_SECONDS = 2
# A valid card the symlink points at, outside cards/. Followed, it would
# read as a working local card.
LINKED_CARD = {"name": "x", "kind": "other", "account": "far", "route": "local"}


def files_under(root):
    """Every path under the root's TC_ROOT, relative and sorted.

    @interacts  walks root.path. Writes nothing.
    @deps       pathlib.
    @complexity O(f) over f files and folders under the root (a handful).
    @alloc      one list of strings, returned.
    """
    return sorted(str(p.relative_to(root.path)) for p in root.path.rglob("*"))


def card_of(root, name):
    """The parsed card for `name` under this root, or None when there is none.

    @interacts  reads cards/<name>.json.
    @deps       json.
    @complexity O(1).
    @alloc      one dict, returned.
    """
    path = root.path / "cards" / f"{name}.json"
    return json.loads(path.read_text()) if path.exists() else None


def load_tc(root):
    """Load ../tc as a module with TC_ROOT set to `root`, without running main().

    tc reads TC_ROOT once, at import, so it is set before the load and the
    old value is put back after.

    @interacts  sets and restores os.environ["TC_ROOT"]; runs tc's top
                level (constants only, no disk writes).
    @deps       importlib, os; _root.TC.
    @complexity O(1).
    @alloc      one module object, returned.
    """
    old = os.environ.get("TC_ROOT")
    os.environ["TC_ROOT"] = str(root.path)
    try:
        loader = importlib.machinery.SourceFileLoader("tc_cards_under_test", str(_root.TC))
        mod = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
        loader.exec_module(mod)
        return mod
    finally:
        if old is None:
            os.environ.pop("TC_ROOT", None)
        else:
            os.environ["TC_ROOT"] = old


class RecordingEnviron(collections.abc.Mapping):
    """A stand-in for os.environ that records every key read and any full copy.

    Mapping builds get(), `in`, keys() and items() on __getitem__ and
    __iter__, so every way of reading goes through the two recorders.

    @interacts  none; records in its own lists.
    @deps       collections.abc.
    @complexity O(1) per read; O(e) to iterate e variables.
    @alloc      the wrapped dict and the two record lists.
    """

    def __init__(self, data):
        """Wrap `data`; record nothing yet.

        @interacts  none.
        @deps       none.
        @complexity O(e) to copy e variables.
        @alloc      one dict and two lists.
        """
        self._data = dict(data)
        self.read = []
        self.copied = 0

    def __getitem__(self, key):
        """Record the key, then answer as a dict would.

        @interacts  appends to self.read.
        @deps       none.
        @complexity O(1).
        @alloc      one list entry.
        """
        self.read.append(key)
        return self._data[key]

    def __iter__(self):
        """Record a full copy, then iterate.

        @interacts  bumps self.copied.
        @deps       none.
        @complexity O(e).
        @alloc      the iterator.
        """
        self.copied += 1
        return iter(self._data)

    def __len__(self):
        """How many variables, as a dict would say.

        @interacts  none.
        @deps       none.
        @complexity O(1).
        @alloc      none.
        """
        return len(self._data)


class CardsTest(unittest.TestCase):
    """tc join, tc card and tc cards under C1.

    @interacts  see the module block.
    @deps       _root.TcRoot.
    @complexity O(1) per test.
    @alloc      one TcRoot per test or case.
    """

    def test_a_codex_session_joins_as_codex(self):
        """With CODEX_THREAD_ID=t1: kind codex, route codex, thread t1, no Claude ids.

        @interacts  one tc join.
        @deps       _root.TcRoot.tc, card_of.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            code, out, err = root.tc("join", "c", env={"CODEX_THREAD_ID": "t1"})
            card = card_of(root, "c")
        self.assertEqual(code, 0, f"tc join c exited {code}: {err}")
        self.assertEqual(out, "joined as c (codex, account unknown, route codex)\n")
        self.assertEqual(list(card), CARD_FIELDS, f"fields or order differ: {list(card)}")
        self.assertEqual((card["version"], card["name"], card["kind"], card["route"], card["thread_id"]),
                         (1, "c", "codex", "codex", "t1"), card)
        self.assertEqual((card["session_id"], card["pid"], card["ssh"], card["reports_to"]),
                         (None, None, None, None), card)

    def test_a_claude_session_joins_as_claude_with_its_ids(self):
        """With CLAUDECODE=1, CLAUDE_CODE_SESSION_ID=s1, CLAUDE_PID=9: kind claude, route local, those ids.

        @interacts  one tc join.
        @deps       _root.TcRoot.tc, card_of.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            code, out, err = root.tc("join", "b", env=CLAUDE_ENV)
            card = card_of(root, "b")
        self.assertEqual(code, 0, f"tc join b exited {code}: {err}")
        self.assertEqual((card["kind"], card["route"], card["session_id"], card["pid"], card["thread_id"]),
                         ("claude", "local", "s1", 9, None), card)

    def test_the_account_is_never_blank(self):
        """No identity and no --account gives `unknown`; so does every blank way in.

        CLAUDE_CONFIG_DIR's base name is used when set (a trailing slash
        too), and --account wins over it. Must reject an empty account.

        @interacts  one tc join per case, each in its own root.
        @deps       _root.TcRoot.tc, card_of.
        @complexity O(1): six cases.
        @alloc      one TcRoot per case.
        """
        cases = [
            ((), {}, "unknown"),
            (("--account", ""), {}, "unknown"),
            (("--account", "  "), {}, "unknown"),
            ((), {"CLAUDE_CONFIG_DIR": ""}, "unknown"),
            ((), {"CLAUDE_CONFIG_DIR": "/home/someone/accounts/work/"}, "work"),
            (("--account", "home"), {"CLAUDE_CONFIG_DIR": "/home/someone/accounts/work"}, "home"),
        ]
        for flags, env, want in cases:
            with self.subTest(flags=flags, env=env):
                with _root.TcRoot() as root:
                    code, out, err = root.tc("join", "b", *flags, env=env)
                    card = card_of(root, "b")
                self.assertEqual(code, 0, f"tc join b {flags} exited {code}: {err}")
                self.assertEqual(card["account"], want, card)
                self.assertEqual((card["kind"], card["route"]), ("other", "local"), card)

    def test_kind_codex_with_no_thread_is_refused(self):
        """`tc join q --kind codex` with no CODEX_THREAD_ID exits 1, says why, writes nothing.

        @interacts  one tc join.
        @deps       _root.TcRoot.tc, files_under.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            code, out, err = root.tc("join", "q", "--kind", "codex")
            after = files_under(root)
        self.assertEqual(code, EXIT_REFUSED, f"exited {code}: {err}")
        self.assertIn("CODEX_THREAD_ID", err)
        self.assertEqual(after, [], f"a refused join wrote {after}")

    def test_card_ssh_gives_route_ssh_and_the_default_remote_path(self):
        """`tc card x --ssh u@h`: route ssh, ssh {target u@h, tc ~/TheConnection/tc}.

        Also --remote-tc /opt/tc/tc is kept as given. SSH S1 (Claude Opus
        5.5, unreviewed): with the ssh route built, neither run prints the
        not-built note; tests/test_ssh_route.py sends to such a card on
        the fake.

        @interacts  two tc card runs.
        @deps       _root.TcRoot.tc, card_of.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            code, out, err = root.tc("card", "x", "--ssh", "u@h")
            card = card_of(root, "x")
            code2, out2, err2 = root.tc("card", "y", "--ssh", "h", "--remote-tc", "/opt/tc/tc")
            card2 = card_of(root, "y")
        self.assertEqual(code, 0, f"tc card exited {code}: {err}")
        self.assertEqual(list(card), CARD_FIELDS)
        self.assertEqual((card["route"], card["ssh"]), ("ssh", {"target": "u@h", "tc": DEFAULT_REMOTE_TC}))
        self.assertEqual(out, "card written: x (other, account unknown, route ssh to u@h)\n")
        # SSH S1 (Claude Opus 5.5, unreviewed): ssh is in ROUTES, so no not-built note.
        self.assertEqual(err, "")
        self.assertEqual(code2, 0, f"tc card y exited {code2}: {err2}")
        self.assertEqual(card2["ssh"], {"target": "h", "tc": "/opt/tc/tc"})
        self.assertEqual(err2, "")

    # CARDS fix round 1 (Claude Opus 5.5, unreviewed): D13 (CARDS-4 item 3).
    def test_tc_card_never_takes_this_sessions_account(self):
        """With CLAUDE_CONFIG_DIR=/x/acct, `tc card x --ssh u@h` gives account `unknown` and kind `other`.

        --account still wins, and a blank --account is `unknown`. Must
        reject C1's join chain applied to a far name.

        @interacts  one tc card per case, each in its own root.
        @deps       _root.TcRoot.tc, card_of.
        @complexity O(1): three cases.
        @alloc      one TcRoot per case.
        """
        cases = [((), "unknown"), (("--account", "far"), "far"), (("--account", "  "), "unknown")]
        for flags, want in cases:
            with self.subTest(flags=flags):
                with _root.TcRoot() as root:
                    code, out, err = root.tc("card", "x", "--ssh", "u@h", *flags,
                                             env={"CLAUDE_CONFIG_DIR": "/x/acct"})
                    card = card_of(root, "x")
                self.assertEqual(code, 0, f"tc card x {flags} exited {code}: {err}")
                self.assertEqual((card["account"], card["kind"]), (want, "other"), card)

    def test_a_rejoin_overwrites_the_card_and_resets_joined_at(self):
        """A second join of b replaces the card: the new account, a new joined_at, one file.

        joined_at is set to OLD_JOINED_AT between the joins, so the test
        needs no sleep to see it change.

        @interacts  two tc joins; edits the card file between them.
        @deps       _root.TcRoot.tc, card_of.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            root.tc("join", "b", "--account", "one")
            path = root.path / "cards" / "b.json"
            card = json.loads(path.read_text())
            card["joined_at"] = OLD_JOINED_AT
            path.write_text(json.dumps(card))
            code, out, err = root.tc("join", "b", "--account", "two")
            again = card_of(root, "b")
            names = sorted(p.name for p in (root.path / "cards").iterdir())
        self.assertEqual(code, 0, f"rejoin exited {code}: {err}")
        self.assertEqual(again["account"], "two")
        self.assertNotEqual(again["joined_at"], OLD_JOINED_AT, "joined_at was not reset")
        self.assertEqual(names, ["b.json"], f"cards/ holds {names}")

    def test_a_card_is_refused_over_unread_mail_unless_forced(self):
        """With 2 unread in to-x, `tc card x --ssh u@h` exits 1 naming 2 and writes no card; --force writes it.

        @interacts  two tc sends, two tc card runs.
        @deps       _root.TcRoot.tc, card_of.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            for text in ("one", "two"):
                root.tc("send", "--from", "a", "--to", "x", text)
            code, out, err = root.tc("card", "x", "--ssh", "u@h")
            refused = card_of(root, "x")
            code2, out2, err2 = root.tc("card", "x", "--ssh", "u@h", "--force")
            forced = card_of(root, "x")
        self.assertEqual(code, EXIT_REFUSED, f"exited {code}: {err}")
        self.assertIn("x has 2 unread", err)
        self.assertIsNone(refused, "a card was written over unread mail")
        self.assertEqual(code2, 0, f"--force exited {code2}: {err2}")
        self.assertEqual(forced["route"], "ssh")

    # CARDS fix round 1 (Claude Opus 5.5, unreviewed): no send lands between tc card's count and write.
    def test_tc_card_counts_and_writes_under_the_inbox_lock(self):
        """With the test holding mail/.box-x.lock, `tc card x --ssh u@h` writes no card until it is released.

        So no send lands in x's inbox between the card's unread count and
        its write. Must reject a count and a write outside the lock.

        @interacts  holds mail/.box-x.lock; one background tc card; reads
                    /proc/locks.
        @deps       wait_until_blocked; fcntl; _root.TcRoot.start, card_of.
        @complexity O(1).
        @alloc      one TcRoot, one open lock file, one background child.
        """
        with _root.TcRoot() as root:
            lock = root.path / "mail" / ".box-x.lock"
            lock.parent.mkdir()
            with open(lock, "a") as held:
                fcntl.flock(held, fcntl.LOCK_EX)
                proc = root.start("card", "x", "--ssh", "u@h")
                wait_until_blocked(self, proc, lock)
                while_held = card_of(root, "x")
            out, err = proc.communicate(timeout=FINISH_CEILING_SECONDS)
            written = card_of(root, "x")
        self.assertIsNone(while_held, "tc card wrote the card while the test held the inbox lock")
        self.assertEqual(proc.returncode, 0, err)
        self.assertEqual(written["route"], "ssh")

    def test_a_bad_ssh_target_or_remote_path_writes_nothing(self):
        """A target that reads as an ssh option, or a bad remote path: refused, nothing written.

        The `=` form reaches tc's check: exit 6. With a space,
        `--ssh -oProxyCommand=y` never reaches it: the parser reads the
        value as a flag and refuses first (a usage error), as R1's
        `--to -x` does. Both write nothing.

        @interacts  one tc card per case, each in its own root.
        @deps       _root.TcRoot.tc, files_under.
        @complexity O(1): nine cases.
        @alloc      one TcRoot per case.
        """
        bad = [
            ("x", "--ssh=-oProxyCommand=y"),
            ("x", "--ssh", "u@-h"),
            ("x", "--ssh="),
            ("x", "--ssh", "u@h x"),
            ("x", "--ssh", "u@h;true"),
            ("x", "--ssh", "u@h", "--remote-tc", "relative/tc"),
            ("x", "--ssh", "u@h", "--remote-tc", "/a b/tc"),
            # CARDS fix round 1 (Claude Opus 5.5, unreviewed): D13, `~` forms are refused.
            ("x", "--ssh", "u@h", "--remote-tc", "~bob/tc"),
            ("x", "--ssh", "u@h", "--remote-tc", "~"),
        ]
        for argv in bad:
            with self.subTest(argv=argv):
                with _root.TcRoot() as root:
                    code, out, err = root.tc("card", *argv)
                    after = files_under(root)
                self.assertEqual(code, EXIT_BAD_NAME, f"tc card {argv} exited {code}: {err}")
                self.assertTrue(err.startswith("tc card: bad "), f"tc card {argv} said: {err!r}")
                self.assertEqual(after, [], f"tc card {argv} wrote {after}")
        with _root.TcRoot() as root:
            code, out, err = root.tc("card", "x", "--ssh", "-oProxyCommand=y")
            after = files_under(root)
        self.assertNotIn(code, (0, EXIT_BAD_NAME), f"space form exited {code}: {err}")
        self.assertIn("usage:", err)
        self.assertEqual(after, [], f"space form wrote {after}")

    def test_no_secret_and_no_other_variable_reaches_a_card(self):
        """The native path's token and socket, and any other variable, never land in a card.

        Plants SECRET in both messaging variables and in a made-up one,
        joins as a Claude session, and checks the whole file. Must reject
        a join that copies the whole environment into the card.

        @interacts  one tc join with planted variables in its env.
        @deps       _root.TcRoot.tc, card_of.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        planted = dict(CLAUDE_ENV)
        planted.update({"CLAUDE_CODE_MESSAGING_TOKEN": SECRET,
                        "CLAUDE_CODE_MESSAGING_SOCKET": f"/run/{SECRET}.sock",
                        "CARDS_TEST_PLANTED": SECRET})
        with _root.TcRoot() as root:
            code, out, err = root.tc("join", "b", env=planted)
            text = (root.path / "cards" / "b.json").read_text()
        self.assertEqual(code, 0, f"tc join b exited {code}: {err}")
        card = json.loads(text)
        # Name the fields, never print the card: on a failure it would hold
        # the environment.
        leaked = sorted(key for key, value in card.items() if SECRET in json.dumps(value))
        self.assertFalse(SECRET in text, f"a planted value reached the card, in fields {leaked}")
        self.assertEqual(list(card), CARD_FIELDS)

    def test_join_reads_exactly_the_five_variables(self):
        """In process, cmd_join reads only C1's five variables and never copies the environment.

        os.environ is swapped for a recorder for the one call. The card
        still gets every value from the five, which proves they were read
        through the recorder. Must reject a join that copies the whole
        environment, even when nothing extra lands in the card.

        @interacts  loads tc in process; patches os.environ for one call;
                    the call writes one card under the harness root.
        @deps       load_tc, RecordingEnviron, unittest.mock.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        env = dict(CLAUDE_ENV, CLAUDE_CONFIG_DIR="/home/someone/accounts/work",
                   CLAUDE_CODE_MESSAGING_TOKEN=SECRET, HOME="/home/someone")
        recorder = RecordingEnviron(env)
        args = argparse.Namespace(name="b", account=None, kind=None, reports_to=None)
        with _root.TcRoot() as root:
            tc = load_tc(root)
            with mock.patch.object(os, "environ", recorder), contextlib.redirect_stdout(io.StringIO()):
                tc.cmd_join(args)
            card = card_of(root, "b")
        self.assertEqual(recorder.copied, 0, "cmd_join iterated the whole environment")
        self.assertLessEqual(set(recorder.read), JOIN_READS,
                             f"cmd_join read {sorted(set(recorder.read) - JOIN_READS)}")
        self.assertEqual((card["kind"], card["session_id"], card["pid"], card["account"]),
                         ("claude", "s1", 9, "work"), card)

    def test_a_card_is_written_through_a_tmp_and_renamed(self):
        """cards/b.json comes only from a rename of a .tmp sibling; nothing writes it in place.

        White box, so it fails every run, not by timing luck. Must reject a
        card written in place. Since the CARDS fix round the .tmp
        is made by os.open with O_EXCL and O_NOFOLLOW, so os.open is
        recorded too, and the .tmp must come from exactly one such call.

        @interacts  loads tc in process; wraps pathlib.Path.write_text,
                    rename and replace, and os.open, for one call to
                    cmd_join.
        @deps       load_tc, unittest.mock.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        writes, moves, opens = [], [], []
        real_write, real_rename, real_replace = (pathlib.Path.write_text, pathlib.Path.rename,
                                                 pathlib.Path.replace)
        real_os_open = os.open

        # Phase fix round 1 (Claude Opus 5.5, unreviewed): doc blocks on the four wrappers.
        def os_open(path, flags, *a, **k):
            """Record the path and flags, then open as the real os.open does.

            @interacts  appends to opens; opens `path` through the real call.
            @deps       os, pathlib.
            @complexity O(1).
            @alloc      one list entry.
            """
            opens.append((pathlib.Path(path), flags))
            return real_os_open(path, flags, *a, **k)

        def write_text(path, *a, **k):
            """Record the path, then write as the real Path.write_text does.

            @interacts  appends to writes; writes `path` through the real
                        method.
            @deps       pathlib.
            @complexity O(n) over n characters written.
            @alloc      one list entry.
            """
            writes.append(pathlib.Path(path))
            return real_write(path, *a, **k)

        def rename(path, target):
            """Record the move, then rename as the real Path.rename does.

            @interacts  appends to moves; renames through the real method.
            @deps       pathlib.
            @complexity O(1).
            @alloc      one list entry.
            """
            moves.append((pathlib.Path(path), pathlib.Path(target)))
            return real_rename(path, target)

        def replace(path, target):
            """Record the move, then replace as the real Path.replace does.

            @interacts  appends to moves; replaces through the real method.
            @deps       pathlib.
            @complexity O(1).
            @alloc      one list entry.
            """
            moves.append((pathlib.Path(path), pathlib.Path(target)))
            return real_replace(path, target)

        args = argparse.Namespace(name="b", account="work", kind=None, reports_to=None)
        with _root.TcRoot() as root:
            tc = load_tc(root)
            final = root.path / "cards" / "b.json"
            with mock.patch.object(pathlib.Path, "write_text", write_text), \
                    mock.patch.object(pathlib.Path, "rename", rename), \
                    mock.patch.object(pathlib.Path, "replace", replace), \
                    mock.patch.object(os, "open", os_open), \
                    contextlib.redirect_stdout(io.StringIO()):
                tc.cmd_join(args)
            left = sorted(p.name for p in final.parent.iterdir())
        self.assertNotIn(final, writes, "the card was written in place")
        self.assertNotIn(final, [path for path, _ in opens], "the card was opened in place")
        into_final = [src for src, dst in moves if dst == final]
        self.assertEqual(len(into_final), 1, f"moves into {final.name}: {moves}")
        self.assertEqual(into_final[0].parent, final.parent)
        self.assertTrue(into_final[0].name.endswith(".tmp"), f"renamed from {into_final[0].name}")
        made = [flags for path, flags in opens if path == into_final[0]]
        self.assertEqual(len(made), 1, f"the .tmp was not made by one os.open: {opens}")
        self.assertEqual(made[0] & (os.O_EXCL | os.O_NOFOLLOW), os.O_EXCL | os.O_NOFOLLOW,
                         "the .tmp was opened without O_EXCL and O_NOFOLLOW")
        self.assertEqual(left, ["b.json"], f"cards/ holds {left}")

    # CARDS fix round 1 (Claude Opus 5.5, unreviewed): a link at the card's .tmp is refused.
    def test_a_link_planted_at_the_card_tmp_is_refused(self):
        """In process: a link at cards/b.json.<pid>.tmp makes tc join exit 1 with words; nothing is written through it.

        The .tmp name carries the pid, which in process is this test's own,
        so the link sits exactly where the join would write. Must reject a
        .tmp written with Path.write_text, which follows the link.

        @interacts  loads tc in process; plants one symlink and one file in
                    the harness's temp folder; calls cmd_join once.
        @deps       load_tc, card_of.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        args = argparse.Namespace(name="b", account="work", kind=None, reports_to=None)
        with _root.TcRoot() as root:
            tc = load_tc(root)
            outside = root.base / "outside.txt"
            outside.write_text("untouched\n")
            link = root.path / "cards" / f"b.json.{os.getpid()}.tmp"
            link.parent.mkdir()
            link.symlink_to(outside)
            with self.assertRaises(SystemExit) as caught, \
                    contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(io.StringIO()) as said:
                tc.cmd_join(args)
            kept = outside.read_text()
            card = card_of(root, "b")
        self.assertEqual(caught.exception.code, EXIT_REFUSED)
        self.assertEqual(said.getvalue(), f"tc: could not create {link} (File exists); no card written\n")
        self.assertEqual(kept, "untouched\n", "the join wrote through the planted link")
        self.assertIsNone(card, "a card was written past the planted link")

    def test_reports_to_is_a_hint_with_c0_names_and_no_self_report(self):
        """--reports-to a is stored; a rejoin without it stores null; b to b and ../x are refused.

        `tc join b --reports-to b` exits 6 with `cannot report to itself`
        and writes no card; `--reports-to ../x` exits 6 with C0's words.
        `tc cards` shows `reports to a`. Must reject a self-report written
        as a card.

        @interacts  five tc joins and one tc cards, in two roots.
        @deps       _root.TcRoot.tc, card_of, files_under.
        @complexity O(1).
        @alloc      two TcRoots.
        """
        with _root.TcRoot() as root:
            code, out, err = root.tc("join", "b", "--reports-to", "a")
            first = card_of(root, "b")
            listed = root.tc("cards")[1]
            root.tc("join", "b")
            second = card_of(root, "b")
        self.assertEqual(code, 0, f"exited {code}: {err}")
        self.assertEqual(out, "joined as b (other, account unknown, route local), reports to a\n")
        self.assertEqual(first["reports_to"], "a")
        self.assertIn("b (other, account unknown, route local), reports to a", listed)
        self.assertIsNone(second["reports_to"], "a rejoin without the flag kept the old hint")
        with _root.TcRoot() as root:
            code, out, err = root.tc("join", "b", "--reports-to", "b")
            self_files = files_under(root)
            code2, out2, err2 = root.tc("join", "b", "--reports-to", "../x")
            bad_files = files_under(root)
            code3, out3, err3 = root.tc("card", "x", "--ssh", "u@h", "--reports-to", "x")
            card_files = files_under(root)
        self.assertEqual((code, err), (EXIT_BAD_NAME, "tc: b cannot report to itself\n"))
        self.assertEqual(self_files, [], f"a self-report wrote {self_files}")
        self.assertEqual((code2, err2), (EXIT_BAD_NAME, BAD_NAME_WORDS.format(name="../x")))
        self.assertEqual(bad_files, [], f"a bad --reports-to wrote {bad_files}")
        self.assertEqual((code3, err3), (EXIT_BAD_NAME, "tc: x cannot report to itself\n"))
        self.assertEqual(card_files, [], f"tc card with a self-report wrote {card_files}")

    def test_cards_lists_every_card_and_says_when_there_are_none(self):
        """`tc cards` prints one line per card, in name order; `no cards` when empty.

        @interacts  two tc cards runs, one tc join, one tc card.
        @deps       _root.TcRoot.tc.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            empty = root.tc("cards")
            root.tc("join", "c", env={"CODEX_THREAD_ID": "t1"})
            root.tc("card", "a", "--ssh", "u@h", "--account", "far")
            code, out, err = root.tc("cards")
        self.assertEqual(empty[:2], (0, "no cards\n"))
        self.assertEqual(code, 0, err)
        self.assertEqual(out, "a (other, account far, route ssh to u@h)\n"
                              "c (codex, account unknown, route codex)\n")


    # Phase fix round 1 (Claude Opus 5.5, unreviewed): escaped output.
    def test_cards_escapes_control_characters(self):
        """BEL in a kind, ESC[2J in an account, ESC in an unreadable card's file name: tc cards prints escapes, never the bytes.

        Must reject a field or a file name printed raw: the terminal would
        ring, or clear its screen.

        @interacts  two hand-written card files, one tc cards.
        @deps       _root.TcRoot.tc.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            cards = root.path / "cards"
            cards.mkdir()
            (cards / "b.json").write_text(json.dumps(
                {"name": "b", "kind": f"claude{BEL}", "account": f"{ESC}[2J", "route": "local"}))
            (cards / f"{ESC}q.json").write_text("{ not json")
            code, out, err = root.tc("cards")
        self.assertEqual(code, 0, err)
        self.assertNotIn(ESC, out, "tc cards printed a raw ESC")
        self.assertNotIn(BEL, out, "tc cards printed a raw BEL")
        self.assertEqual(out, f"{ESC_SHOWN}q.json: unreadable card\n"
                              f"b (claude{BEL_SHOWN}, account {ESC_SHOWN}[2J, route local)\n")

    # Phase fix round 1 (Claude Opus 5.5, unreviewed): a card is named by its file.
    def test_cards_names_a_card_by_its_file(self):
        """cards/b.json copied by hand from a's card: tc cards lists it as b and says the card names a.

        The router sends to b by that file, and tc health names it b. Must
        reject a line named from the card's own name field: it would list
        a twice.

        @interacts  one join, one hand copy of its card, one tc cards.
        @deps       _root.TcRoot.tc.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            root.tc("join", "a")
            cards = root.path / "cards"
            (cards / "b.json").write_text((cards / "a.json").read_text())
            code, out, err = root.tc("cards")
        self.assertEqual(code, 0, err)
        self.assertEqual(out, "a (other, account unknown, route local)\n"
                              "b (other, account unknown, route local), card says name a\n")

    # Phase fix round 1 (Claude Opus 5.5, unreviewed): RecursionError is unreadable too.
    def test_a_card_nested_too_deep_is_unreadable_not_a_crash(self):
        """A card nested DEEP_NESTING deep: tc cards and tc health call it unreadable, and tc send refuses it in words.

        json.loads raises RecursionError on it, not ValueError. Must reject
        a card read that catches only OSError and ValueError: each command
        would end in a traceback.

        @interacts  one hand-written card, one tc cards, one tc health, one
                    tc send.
        @deps       _root.TcRoot.tc, files_under.
        @complexity O(DEEP_NESTING) to write and parse the card.
        @alloc      one TcRoot; the card's text, 2 x DEEP_NESTING characters.
        """
        with _root.TcRoot() as root:
            (root.path / "cards").mkdir()
            (root.path / "cards" / "b.json").write_text("[" * DEEP_NESTING + "]" * DEEP_NESTING)
            listed = root.tc("cards")
            health = root.tc("health")
            before = files_under(root)
            sent = root.tc("send", "--from", "a", "--to", "b", "hi")
            after = files_under(root)
        self.assertEqual(listed[0], 0, f"tc cards exited {listed[0]} on a card nested too deep")
        self.assertEqual(listed[1], "b.json: unreadable card\n")
        self.assertEqual(health[0], 0, f"tc health exited {health[0]} on a card nested too deep")
        self.assertIn("\ncards      b (?, account ?, route ?)\n", health[1])
        self.assertEqual(sent[0], EXIT_REFUSED, f"tc send exited {sent[0]}")
        self.assertTrue("b.json is unreadable" in sent[2] and "Traceback" not in sent[2],
                        "tc send did not refuse a card nested too deep in words")
        self.assertEqual(after, before, "a send to a card nested too deep wrote a file")


    # Phase fix round 1 (Claude Opus 5.5, unreviewed): a card is read only from a regular file.
    def test_a_fifo_or_a_symlink_at_a_card_is_unreadable_and_never_blocks(self):
        """A FIFO, then a symlink, at cards/x.json: tc cards, tc health and tc send --to x each return within 2 s, calling it unreadable.

        The symlink points at a valid card outside cards/. Must reject a
        card read with a plain open(): it blocks on the FIFO (the run is
        killed at CARD_READ_CEILING_SECONDS) and follows the symlink.

        @interacts  per case: one FIFO or one symlink and its target made by
                    hand, one tc cards, one tc health, one tc send, each
                    under CARD_READ_CEILING_SECONDS, in its own root.
        @deps       _root.TcRoot.tc, files_under; os, subprocess.
        @complexity O(1): two cases, three runs each.
        @alloc      one TcRoot per case.
        """
        for kind in ("fifo", "symlink"):
            with self.subTest(kind=kind):
                with _root.TcRoot() as root:
                    cards = root.path / "cards"
                    cards.mkdir()
                    path = cards / "x.json"
                    if kind == "fifo":
                        os.mkfifo(path)
                    else:
                        outside = root.base / "outside.json"
                        outside.write_text(json.dumps(LINKED_CARD))
                        path.symlink_to(outside)
                    ran = {}
                    for what, argv in (("cards", ("cards",)), ("health", ("health",)),
                                       ("send", ("send", "--from", "a", "--to", "x", "hi"))):
                        before = files_under(root)  # the last one taken is the send's
                        try:
                            ran[what] = root.tc(*argv, timeout=CARD_READ_CEILING_SECONDS)
                        except subprocess.TimeoutExpired:
                            self.fail(f"tc {what} did not return within {CARD_READ_CEILING_SECONDS} s "
                                      f"with a {kind} at cards/x.json")
                    after = files_under(root)
                self.assertEqual(ran["cards"], (0, "x.json: unreadable card\n", ""))
                self.assertEqual(ran["health"][0], 0, f"tc health exited {ran['health'][0]}")
                self.assertIn("\ncards      x (?, account ?, route ?)\n", ran["health"][1])
                self.assertEqual(ran["send"][0], EXIT_REFUSED, f"tc send exited {ran['send'][0]}")
                self.assertTrue("x.json is unreadable" in ran["send"][2] and "Traceback" not in ran["send"][2],
                                f"tc send did not refuse a {kind} card in words")
                self.assertEqual(after, before, f"a send to a {kind} card wrote a file")


if __name__ == "__main__":
    unittest.main()
