"""
Tests for the router in `tc send` (CARDS R3, contract C2, open items O1
and O2): no card means today's send; a first send to a new inbox warns
once; read and peek create nothing for an unknown name; the 1 MiB limit
is checked before a number is taken; a route not built yet is refused;
nothing routes by reports_to.

Model:  Claude Opus 5.5 (the CARDS lane agent), 2026-10-14
Status: unreviewed

@interacts  runs ../tc through tests/_root.py under a throwaway TC_ROOT and
            compares the root's file list and mail/.seq before and after.
            Two tests load tc as a module (TC_ROOT set to the harness root
            first, put back after) and call cmd_send or deliver_local in
            process, so they write under that root only. Two tests hold
            the inbox lock themselves and read /proc/locks (LOW-9). One
            plants a symlink at a message's .tmp name, pointing at a file
            in the harness's temp folder (DEBT-3).
@deps       python3 stdlib (argparse, contextlib, fcntl, importlib, io,
            json, os, pathlib, subprocess, sys, unittest); tests/_root.py;
            RELEASE_CEILING_SECONDS and wait_until_blocked from
            test_codex_route.py; ../tc.
@complexity O(1) per test: one to six tc runs, each under a second. The
            size test pipes 1 MiB twice.
@alloc      one TcRoot per test, removed when its context exits; the size
            test holds two 1 MiB strings while it runs.
"""

import argparse
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

HERE = pathlib.Path(__file__).resolve().parent
# Run as `python3 -m unittest tests.test_router` from the repo root, tests/
# is not on sys.path; under discover it is. Add it once so both work.
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import _root  # noqa: E402  (needs the path line above)
# CARDS fix round 1 (Claude Opus 5.5, unreviewed): one copy of the lock helpers.
from test_codex_route import RELEASE_CEILING_SECONDS, wait_until_blocked  # noqa: E402

# C0's limit and words, written here rather than read from tc.
MAX_BYTES = 1048576
TOO_LARGE_WORDS = "tc send: message over 1 MiB; this is a mailbox for words\n"
EXIT_REFUSED = 1
EXIT_TOO_LARGE = 8
NEW_INBOX_WORDS = "new inbox: nobody has joined as {name}\n"
# A send that shares the inbox lock with the test lands at once; this much
# is room for a loaded machine, not a wait anyone expects.
SHARED_SEND_CEILING_SECONDS = 5
# CARDS fix round 1 (Claude Opus 5.5, unreviewed): the refusals' words,
# written here. REC-13: the not-built refusal reads like the other two.
NOT_BUILT_WORDS = "tc send: route {route} is not built yet; nothing sent\n"
# LOW-15: who fixes a bad card. Never the sender running tc join.
CARD_FIX_WORDS = ("Ask {to}'s owner to rejoin (tc join {to}, run in {to}'s own session), or, "
                  "if {to} lives on another machine, write its card with tc card {to} --ssh <target>.")
EMPTY_WORDS = "tc send: empty message\n"


def files_under(root):
    """Every path under the root's TC_ROOT, relative and sorted.

    @interacts  walks root.path. Writes nothing.
    @deps       pathlib.
    @complexity O(f) over f files and folders under the root (a handful).
    @alloc      one list of strings, returned.
    """
    return sorted(str(p.relative_to(root.path)) for p in root.path.rglob("*"))


def seq_of(root):
    """mail/.seq's text under this root, or None when it does not exist.

    @interacts  reads mail/.seq.
    @deps       pathlib.
    @complexity O(1).
    @alloc      one string.
    """
    path = root.path / "mail" / ".seq"
    return path.read_text() if path.exists() else None


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
        loader = importlib.machinery.SourceFileLoader("tc_router_under_test", str(_root.TC))
        mod = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
        loader.exec_module(mod)
        return mod
    finally:
        if old is None:
            os.environ.pop("TC_ROOT", None)
        else:
            os.environ["TC_ROOT"] = old


class RouterTest(unittest.TestCase):
    """tc send's router, deliver_local, the size limit, O1 and O2.

    @interacts  see the module block.
    @deps       _root.TcRoot.
    @complexity O(1) per test.
    @alloc      one TcRoot per test.
    """

    def test_a_send_to_a_name_with_no_card_is_todays_send(self):
        """No card: the stdout line, the header, read once, then `no unread mail` (as CORE's K1).

        @interacts  one send, two reads.
        @deps       _root.TcRoot.tc.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            code, out, err = root.tc("send", "--from", "a", "--to", "b", "hi")
            path = root.path / "mail" / "to-b" / "000001-from-a.md"
            text = path.read_text()
            code1, read1, _ = root.tc("read", "b")
            moved = (root.path / "mail" / "to-b" / "read" / "000001-from-a.md").exists()
            code2, read2, _ = root.tc("read", "b")
        self.assertEqual(code, 0, f"tc send exited {code}: {err}")
        self.assertEqual(out, f"sent #1 to b: {path}\n")
        self.assertTrue(text.startswith("# #1 from a to b, "), f"header: {text!r}")
        self.assertTrue(text.endswith("\n\nhi\n"), f"body: {text!r}")
        self.assertEqual(code1, 0)
        self.assertTrue(read1.startswith("# #1 from a to b"), f"first read: {read1!r}")
        self.assertTrue(moved, "read did not move the file to read/")
        self.assertEqual((code2, read2), (0, "no unread mail for b\n"))

    def test_a_first_send_to_a_new_inbox_warns_once(self):
        """The first send to `nobody` exits 0, prints the send line, and warns on stderr; the second does not warn.

        Must reject a warning on every send.

        @interacts  two sends.
        @deps       _root.TcRoot.tc.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            first = root.tc("send", "--from", "a", "--to", "nobody", "one")
            second = root.tc("send", "--from", "a", "--to", "nobody", "two")
            box = root.path / "mail" / "to-nobody"
        self.assertEqual(first, (0, f"sent #1 to nobody: {box / '000001-from-a.md'}\n",
                                 NEW_INBOX_WORDS.format(name="nobody")))
        self.assertEqual(second, (0, f"sent #2 to nobody: {box / '000002-from-a.md'}\n", ""))

    def test_read_and_peek_of_an_unknown_name_create_nothing(self):
        """`tc peek ghost` and `tc read ghost` say `no unread mail for ghost` and leave the root empty (O2).

        @interacts  one peek, one read.
        @deps       _root.TcRoot.tc, files_under.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            peeked = root.tc("peek", "ghost")
            read = root.tc("read", "ghost")
            after = files_under(root)
        self.assertEqual(peeked, (0, "no unread mail for ghost\n", ""))
        self.assertEqual(read, (0, "no unread mail for ghost\n", ""))
        self.assertEqual(after, [], f"peek or read of an unknown name made {after}")

    def test_the_size_limit_is_checked_before_a_number_is_taken(self):
        """Exactly 1 MiB is sent; one byte more exits 8, writes nothing and uses no number.

        Must reject a size check after next_seq(): mail/.seq must read the
        same after the refusal, and the next send gets #2.

        @interacts  three sends, two of them 1 MiB on stdin.
        @deps       _root.TcRoot.tc, files_under, seq_of.
        @complexity O(MAX_BYTES).
        @alloc      two 1 MiB strings and one 1 MiB message file.
        """
        with _root.TcRoot() as root:
            code, out, err = root.tc("send", "--from", "a", "--to", "b", stdin="x" * MAX_BYTES)
            sent = [m.stat().st_size for m in (root.path / "mail" / "to-b").glob("*.md")]
            before, seq_before = files_under(root), seq_of(root)
            code2, out2, err2 = root.tc("send", "--from", "a", "--to", "b", stdin="x" * (MAX_BYTES + 1))
            after, seq_after = files_under(root), seq_of(root)
            code3, out3, _ = root.tc("send", "--from", "a", "--to", "b", "small")
        self.assertEqual(code, 0, f"1 MiB exactly exited {code}: {err}")
        self.assertEqual(len(sent), 1, f"to-b holds {len(sent)} messages")
        self.assertGreater(sent[0], MAX_BYTES, "the 1 MiB body did not land whole")
        self.assertEqual((code2, out2, err2), (EXIT_TOO_LARGE, "", TOO_LARGE_WORDS))
        self.assertEqual(after, before, "a refused send wrote a file")
        self.assertEqual(seq_after, seq_before, "a refused send used a number")
        self.assertEqual(seq_before, "1")
        self.assertEqual(code3, 0)
        self.assertTrue(out3.startswith("sent #2 to b: "), out3)

    def test_the_size_limit_on_a_text_argument_counts_bytes(self):
        """In process: a text argument over 1 MiB in bytes exits 8 before a number, even under 1 MiB in characters.

        A real command line cannot carry it: Linux caps one argument at
        128 KiB (MAX_ARG_STRLEN), so this calls cmd_send directly.

        @interacts  loads tc in process; calls cmd_send twice under the root.
        @deps       load_tc, seq_of.
        @complexity O(MAX_BYTES).
        @alloc      two strings of about 1 MiB.
        """
        two_byte = "\u00e9"  # one character, two bytes in UTF-8
        over_in_bytes = two_byte * (MAX_BYTES // 2 + 1)
        with _root.TcRoot() as root:
            tc = load_tc(root)
            with self.assertRaises(SystemExit) as caught, contextlib.redirect_stderr(io.StringIO()) as said:
                tc.cmd_send(argparse.Namespace(sender="a", to="b", message=over_in_bytes))
            refused_seq = seq_of(root)
            with contextlib.redirect_stdout(io.StringIO()) as out, \
                    contextlib.redirect_stderr(io.StringIO()):
                tc.cmd_send(argparse.Namespace(sender="a", to="b", message="x" * MAX_BYTES))
        self.assertLess(len(over_in_bytes), MAX_BYTES)
        self.assertEqual(caught.exception.code, EXIT_TOO_LARGE)
        self.assertEqual(said.getvalue(), TOO_LARGE_WORDS)
        self.assertIsNone(refused_seq, "a refused send made mail/.seq")
        self.assertTrue(out.getvalue().startswith("sent #1 to b: "), out.getvalue())

    def test_a_route_not_built_yet_is_refused_and_writes_nothing(self):
        """An ssh card, and a hand-made card naming route pigeon: exit 1, `route <r> is not built yet`.

        @interacts  one tc card, one hand-written card, two sends.
        @deps       _root.TcRoot.tc, files_under, seq_of.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            root.tc("card", "x", "--ssh", "u@h")
            (root.path / "cards" / "p.json").write_text(json.dumps({"name": "p", "route": "pigeon"}))
            before, seq_before = files_under(root), seq_of(root)
            ssh = root.tc("send", "--from", "a", "--to", "x", "hi")
            pigeon = root.tc("send", "--from", "a", "--to", "p", "hi")
            after, seq_after = files_under(root), seq_of(root)
        self.assertEqual(ssh, (EXIT_REFUSED, "", NOT_BUILT_WORDS.format(route="ssh")))
        self.assertEqual(pigeon, (EXIT_REFUSED, "", NOT_BUILT_WORDS.format(route="pigeon")))
        self.assertEqual(after, before, f"a refused route wrote {sorted(set(after) - set(before))}")
        self.assertIsNone(seq_after, "a refused route took a number")
        self.assertIsNone(seq_before)

    def test_an_unreadable_card_is_refused_not_guessed(self):
        """A card that is not JSON: the send exits 1 naming the card, and writes nothing.

        @interacts  one hand-written card, one send.
        @deps       _root.TcRoot.tc, files_under.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            (root.path / "cards").mkdir()
            (root.path / "cards" / "b.json").write_text("{ not json")
            before = files_under(root)
            code, out, err = root.tc("send", "--from", "a", "--to", "b", "hi")
            after = files_under(root)
        self.assertEqual(code, EXIT_REFUSED, f"exited {code}: {err}")
        self.assertIn("b.json is unreadable", err)
        self.assertEqual(after, before, "a send to an unreadable card wrote a file")
        # CARDS fix round 1 (Claude Opus 5.5, unreviewed): LOW-15.
        self.assertTrue(err.endswith("nothing sent. " + CARD_FIX_WORDS.format(to="b") + "\n"), err)

    # CARDS fix round 1 (Claude Opus 5.5, unreviewed): LOW-10.
    def test_a_card_with_no_route_is_refused_in_words(self):
        """A hand-made card with no route, a null route, or route 5: exit 1, the file named, `has no route`, never `None`.

        @interacts  per case: one hand-written card, one send, in its own root.
        @deps       _root.TcRoot.tc, files_under.
        @complexity O(1): three cases.
        @alloc      one TcRoot per case.
        """
        for card in ({"name": "n"}, {"name": "n", "route": None}, {"name": "n", "route": 5}):
            with self.subTest(card=card):
                with _root.TcRoot() as root:
                    (root.path / "cards").mkdir()
                    path = root.path / "cards" / "n.json"
                    path.write_text(json.dumps(card))
                    before = files_under(root)
                    code, out, err = root.tc("send", "--from", "a", "--to", "n", "hi")
                    after = files_under(root)
                self.assertEqual(code, EXIT_REFUSED, f"exited {code}: {err}")
                self.assertEqual(err, f"tc send: the card {path} has no route; nothing sent. "
                                      f"{CARD_FIX_WORDS.format(to='n')}\n")
                self.assertNotIn("None", err)
                self.assertEqual(after, before, f"a card with no route wrote {sorted(set(after) - set(before))}")

    # CARDS fix round 1 (Claude Opus 5.5, unreviewed): LOW-11.
    def test_an_empty_message_is_refused_through_refuse_with_exit_1(self):
        """An empty message exits 1 with `tc send: empty message`, in process and as a command.

        In process the exit code is the int EXIT_REFUSED and the words are
        already on stderr. Must reject sys.exit("..."), whose code is the
        string itself.

        @interacts  one send as a command; loads tc in process and calls
                    cmd_send once. Neither writes anything.
        @deps       load_tc, files_under; _root.TcRoot.tc.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        with _root.TcRoot() as root:
            ran = root.tc("send", "--from", "a", "--to", "b", "  ")
            tc = load_tc(root)
            with self.assertRaises(SystemExit) as caught, contextlib.redirect_stderr(io.StringIO()) as said:
                tc.cmd_send(argparse.Namespace(sender="a", to="b", message="  "))
            after = files_under(root)
        self.assertEqual(ran, (EXIT_REFUSED, "", EMPTY_WORDS))
        self.assertEqual(caught.exception.code, EXIT_REFUSED)
        self.assertEqual(said.getvalue(), EMPTY_WORDS)
        self.assertEqual(after, [], f"an empty message wrote {after}")

    # CARDS fix round 1 (Claude Opus 5.5, unreviewed): D13, REC-2.
    def test_the_new_inbox_warning_keys_on_the_card_file(self):
        """In process: deliver_local(None, ...) to a joined name with no inbox gives no warning.

        The gate (C3) calls deliver_local with no card in hand, so the check
        must look at cards/b.json on disk. Must reject a check on the
        `card` argument: it would warn here.

        @interacts  one join; loads tc in process; calls deliver_local once.
        @deps       load_tc; _root.TcRoot.tc.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        with _root.TcRoot() as root:
            root.tc("join", "b")
            tc = load_tc(root)
            got = tc.deliver_local(None, "x", "b", "hi")
        self.assertEqual(got.exit, 0)
        self.assertEqual(got.warnings, [], "a joined name got the new-inbox warning")

    # CARDS fix round 1 (Claude Opus 5.5, unreviewed): DEBT-3.
    def test_a_link_planted_at_the_message_tmp_is_refused(self):
        """A link at the next message's .tmp name: the send exits 1 with words, and nothing is written through it.

        Must reject a .tmp written with Path.write_text, which follows the
        link and writes the message into the file it points at.

        @interacts  two sends; one symlink and one file planted in the temp
                    folder, outside TC_ROOT's mailbox.
        @deps       _root.TcRoot.tc.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            root.tc("send", "--from", "a", "--to", "b", "one")
            outside = root.base / "outside.txt"
            outside.write_text("untouched\n")
            link = root.path / "mail" / "to-b" / "000002-from-a.tmp"
            link.symlink_to(outside)
            code, out, err = root.tc("send", "--from", "a", "--to", "b", "two")
            kept = outside.read_text()
            still_a_link = link.is_symlink()
            landed = sorted(p.name for p in (root.path / "mail" / "to-b").glob("*.md"))
        self.assertEqual(code, EXIT_REFUSED, f"exited {code}: {err}")
        self.assertEqual(err, f"tc send: could not create {link} (File exists); nothing sent\n")
        self.assertEqual(kept, "untouched\n", "the send wrote through the planted link")
        self.assertTrue(still_a_link)
        self.assertEqual(landed, ["000001-from-a.md"])

    def test_a_local_card_delivers_where_to_says_and_reports_to_routes_nothing(self):
        """b joins as a Claude reporting to a; mail from c to b lands in to-b only (No hub, D7).

        The first send to b finds no inbox, but b has a card, so it does not
        warn (D13, the CARDS-2 pause settled).

        @interacts  one join, one send.
        @deps       _root.TcRoot.tc.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            root.tc("join", "b", "--reports-to", "a", env={"CLAUDECODE": "1"})
            code, out, err = root.tc("send", "--from", "c", "--to", "b", "hi")
            boxes = sorted(p.name for p in (root.path / "mail").glob("to-*"))
            landed = sorted(p.name for p in (root.path / "mail" / "to-b").glob("*.md"))
        self.assertEqual(code, 0, f"exited {code}: {err}")
        self.assertTrue(out.startswith("sent #1 to b: "), out)
        self.assertEqual(err, "", "a joined name got the new-inbox warning")
        self.assertEqual(boxes, ["to-b"], f"mail went to {boxes}")
        self.assertEqual(landed, ["000001-from-c.md"])

    def test_deliver_local_returns_a_delivery_and_appends_the_header_note(self):
        """In process: deliver_local gives Delivery(0, the send line, [the new-inbox warning]); header_note ends the header.

        @interacts  loads tc in process; calls deliver_local once under the root.
        @deps       load_tc.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        with _root.TcRoot() as root:
            tc = load_tc(root)
            got = tc.deliver_local(None, "x", "b", "hi", header_note="via ssh gate, key x")
            path = root.path / "mail" / "to-b" / "000001-from-x.md"
            header = path.read_text().splitlines()[0]
        self.assertEqual(tuple(got), (0, f"sent #1 to b: {path}", ["new inbox: nobody has joined as b"]))
        self.assertEqual(got._fields, ("exit", "words", "warnings"))
        self.assertTrue(header.startswith("# #1 from x to b, "), header)
        self.assertTrue(header.endswith(", via ssh gate, key x"), header)

    # CARDS fix round 1 (Claude Opus 5.5, unreviewed): LOW-9.
    def test_a_local_send_waits_for_a_held_inbox_lock(self):
        """With the test holding mail/.box-b.lock alone, a send to b (no card) does not land until it is released.

        A local send reads the card again and lands under the lock, so a
        `tc card` for b, which holds it alone, never counts b's mail before
        a send that lands after. Must reject a local send outside the lock.

        @interacts  holds mail/.box-b.lock; one background send; reads
                    /proc/locks.
        @deps       wait_until_blocked; fcntl; _root.TcRoot.start.
        @complexity O(1).
        @alloc      one TcRoot, one open lock file, one background child.
        """
        with _root.TcRoot() as root:
            box = root.path / "mail" / "to-b"
            lock = root.path / "mail" / ".box-b.lock"
            lock.parent.mkdir()
            with open(lock, "a") as held:
                fcntl.flock(held, fcntl.LOCK_EX)
                proc = root.start("send", "--from", "a", "--to", "b", "hi")
                wait_until_blocked(self, proc, lock)
                while_held = sorted(p.name for p in box.glob("*.md"))
            out, err = proc.communicate(timeout=RELEASE_CEILING_SECONDS)
            landed = sorted(p.name for p in box.glob("*.md"))
        self.assertEqual(while_held, [], "the send landed while the test held the inbox lock")
        self.assertEqual(proc.returncode, 0, err)
        self.assertEqual(landed, ["000001-from-a.md"])

    def test_local_sends_share_the_inbox_lock(self):
        """With the test holding mail/.box-b.lock shared, a send to b still lands at once.

        Local senders share the lock, so many senders to one inbox queue on
        mail/.seq as before (CORE's K3), never on each other here. Must
        reject a local send that takes the lock alone.

        @interacts  holds mail/.box-b.lock shared; one background send.
        @deps       fcntl, subprocess; _root.TcRoot.start.
        @complexity O(1).
        @alloc      one TcRoot, one open lock file, one background child.
        """
        with _root.TcRoot() as root:
            lock = root.path / "mail" / ".box-b.lock"
            lock.parent.mkdir()
            with open(lock, "a") as held:
                fcntl.flock(held, fcntl.LOCK_SH)
                proc = root.start("send", "--from", "a", "--to", "b", "hi")
                try:
                    out, err = proc.communicate(timeout=SHARED_SEND_CEILING_SECONDS)
                except subprocess.TimeoutExpired:
                    self.fail(f"the send still waited {SHARED_SEND_CEILING_SECONDS} s on a lock "
                              f"the test held shared: it took the lock alone")
            landed = sorted(p.name for p in (root.path / "mail" / "to-b").glob("*.md"))
        self.assertEqual(proc.returncode, 0, err)
        self.assertEqual(landed, ["000001-from-a.md"])


if __name__ == "__main__":
    unittest.main()
