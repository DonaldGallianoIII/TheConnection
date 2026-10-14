"""
Tests for the codex route (CARDS R4, contract C2, decision D3): a send to
a codex card lands in the inbox like any other, then rings the thread with
`codex queue` when the inbox was empty. A failed ring is a warning, never
a failed send.

Model:  Claude Opus 5.5 (the CARDS lane agent), 2026-10-14
Status: unreviewed

Real codex never runs here (rule 5). Every test puts tests/_root.py's fake
`codex` first on PATH, asserts its record file exists before reading it,
and reads calls() inside the `with TcRoot()` block. A test that asserts
"not called" also proves, in the same root, that the fake is reachable.

@interacts  runs ../tc through tests/_root.py under a throwaway TC_ROOT,
            with a fake `codex` that records its argv. One test loads tc as
            a module (TC_ROOT set to the harness root first, put back
            after) and swaps subprocess.run for one call, so nothing runs.
@deps       python3 stdlib (importlib, json, os, pathlib, subprocess, sys,
            unittest, unittest.mock); tests/_root.py; ../tc.
@complexity O(1) per test: two to five tc runs and as many fake calls,
            each under a second.
@alloc      one TcRoot per test, removed when its context exits.
"""

import importlib.machinery
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
# Run as `python3 -m unittest tests.test_codex_route` from the repo root,
# tests/ is not on sys.path; under discover it is. Add it once so both work.
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import _root  # noqa: E402  (needs the path line above)

# Recorded fixture: matches Codex 0.162.1, 2026-10-14.
# The exit codes of `codex queue`: 0 when the line is queued for the
# thread, 1 for a thread it does not know. Written from the plan's words
# (phases.md R4, decisions.md D3), not from a run of codex: agents never
# run the real one. The fakes below exit with these codes.
CODEX_FIXTURE_LABEL = "matches Codex 0.162.1, 2026-10-14"
CODEX_QUEUE_EXIT = {"queued": 0, "unknown thread": 1}
# The fake's stderr on a failed ring. Made up for the test; it is not
# real codex's wording, which the plan does not record.
FAKE_UNKNOWN_THREAD_STDERR = "fake codex: no thread t1\n"

THREAD = "t1"
TC_PATH = str(_root.TC.resolve())
RANG_WORDS = "rang codex {to} (queued; delivered when its turn ends or the session is resumed)"
RING_MESSAGE = ("MAIL: {n} unread for {to}. Run: {tc} read {to}, act on it, "
                "reply with {tc} send --from {to} --to {sender}.")
# The timeout C2 gives a ring, written here rather than read from tc.
CODEX_RING_SECONDS = 30


def ring_argv(n, to, sender):
    """The argv a ring must hand codex, after the program name.

    @interacts  none.
    @deps       RING_MESSAGE, TC_PATH.
    @complexity O(1).
    @alloc      one list, returned.
    """
    return ["queue", "--thread", THREAD, "--message",
            RING_MESSAGE.format(n=n, to=to, tc=TC_PATH, sender=sender)]


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
        loader = importlib.machinery.SourceFileLoader("tc_codex_under_test", str(_root.TC))
        mod = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
        loader.exec_module(mod)
        return mod
    finally:
        if old is None:
            os.environ.pop("TC_ROOT", None)
        else:
            os.environ["TC_ROOT"] = old


class CodexRouteTest(unittest.TestCase):
    """deliver_codex through `tc send`, against a fake codex.

    @interacts  see the module block.
    @deps       _root.TcRoot, _root.TcRoot.fake_bin.
    @complexity O(1) per test.
    @alloc      one TcRoot per test.
    """

    def join_codex(self, root, name="c"):
        """Join `name` as a Codex session on THREAD; fail the test if it does not.

        @interacts  one tc join with CODEX_THREAD_ID set for that call.
        @deps       _root.TcRoot.tc.
        @complexity O(1).
        @alloc      one card file.
        """
        code, out, err = root.tc("join", name, env={"CODEX_THREAD_ID": THREAD})
        self.assertEqual(code, 0, f"tc join {name} exited {code}: {err}")

    def test_the_fixture_is_labeled(self):
        """The recorded exit codes carry the plan's label, and the codes the plan names.

        @interacts  none.
        @deps       the module constants.
        @complexity O(1).
        @alloc      none.
        """
        self.assertEqual(CODEX_FIXTURE_LABEL, "matches Codex 0.162.1, 2026-10-14")
        self.assertEqual(CODEX_QUEUE_EXIT, {"queued": 0, "unknown thread": 1})

    def test_two_sends_to_an_empty_codex_inbox_ring_once(self):
        """Two sends to c ring once, with the argv C2 gives, and both land.

        Must reject a test that passes because the fake never ran (the
        record must exist), and a ring on every send.

        @interacts  one join, two sends, one fake codex.
        @deps       _root.TcRoot.tc, _root.TcRoot.fake_bin, ring_argv.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("codex", CODEX_QUEUE_EXIT["queued"])
            self.join_codex(root)
            first = root.tc("send", "--from", "a", "--to", "c", "one")
            second = root.tc("send", "--from", "a", "--to", "c", "two")
            record = folder.parent / "calls.jsonl"
            self.assertTrue(record.exists(), f"{record} missing: the fake codex never ran")
            recorded = calls()
            box = root.path / "mail" / "to-c"
            landed = sorted(p.name for p in box.glob("*.md"))
        self.assertEqual(first[0], 0, f"first send exited {first[0]}: {first[2]}")
        self.assertEqual(first[1], f"sent #1 to c: {box / '000001-from-a.md'}\n"
                                   f"{RANG_WORDS.format(to='c')}\n")
        self.assertEqual(second[:2], (0, f"sent #2 to c: {box / '000002-from-a.md'}\n"))
        self.assertEqual(recorded, [{"argv": ring_argv(1, "c", "a"), "stdin": ""}])
        self.assertEqual(landed, ["000001-from-a.md", "000002-from-a.md"])

    def test_a_failed_ring_is_a_warning_and_the_send_exits_0(self):
        """With the fake exiting 1 (unknown thread): exit 0, the mail in the inbox, `ring failed` on stderr.

        Must reject a send that fails because the ring failed.

        @interacts  one join, one send, one fake codex.
        @deps       _root.TcRoot.tc, _root.TcRoot.fake_bin.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("codex", CODEX_QUEUE_EXIT["unknown thread"],
                                          stderr=FAKE_UNKNOWN_THREAD_STDERR)
            self.join_codex(root)
            code, out, err = root.tc("send", "--from", "a", "--to", "c", "hi")
            record = folder.parent / "calls.jsonl"
            self.assertTrue(record.exists(), f"{record} missing: the fake codex never ran")
            recorded = calls()
            landed = sorted(p.name for p in (root.path / "mail" / "to-c").glob("*.md"))
        self.assertEqual(code, 0, f"a failed ring failed the send: exit {code}: {err}")
        self.assertTrue(out.startswith("sent #1 to c: "), out)
        self.assertNotIn("rang codex", out)
        self.assertIn("ring failed for c: fake codex: no thread t1; the mail is in its inbox\n", err)
        self.assertEqual(len(recorded), 1)
        self.assertEqual(landed, ["000001-from-a.md"])

    def test_no_ring_for_a_claude_card(self):
        """A send to a Claude card never runs codex; a send to a codex card in the same root does.

        The second half proves the fake was reachable, so "not called" is
        a check and not an absence.

        @interacts  two joins, two sends, one fake codex.
        @deps       _root.TcRoot.tc, _root.TcRoot.fake_bin.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("codex", CODEX_QUEUE_EXIT["queued"])
            record = folder.parent / "calls.jsonl"
            root.tc("join", "b", env={"CLAUDECODE": "1"})
            code, out, err = root.tc("send", "--from", "a", "--to", "b", "hi")
            rang_for_claude = record.exists()
            self.join_codex(root)
            root.tc("send", "--from", "a", "--to", "c", "hi")
            self.assertTrue(record.exists(), f"{record} missing: the fake codex is not reachable")
            recorded = calls()
        self.assertEqual(code, 0, f"send to b exited {code}: {err}")
        self.assertFalse(rang_for_claude, "a send to a claude card ran codex")
        self.assertEqual([call["argv"] for call in recorded], [ring_argv(1, "c", "a")])

    def test_it_rings_again_once_the_inbox_was_read(self):
        """send, read, send: two rings, one per batch of unread mail.

        @interacts  one join, two sends, one read, one fake codex.
        @deps       _root.TcRoot.tc, _root.TcRoot.fake_bin.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("codex", CODEX_QUEUE_EXIT["queued"])
            self.join_codex(root)
            root.tc("send", "--from", "a", "--to", "c", "one")
            root.tc("read", "c")
            root.tc("send", "--from", "b", "--to", "c", "two")
            record = folder.parent / "calls.jsonl"
            self.assertTrue(record.exists(), f"{record} missing: the fake codex never ran")
            recorded = calls()
        self.assertEqual([call["argv"] for call in recorded],
                         [ring_argv(1, "c", "a"), ring_argv(1, "c", "b")])

    def test_a_codex_card_with_no_thread_is_delivered_with_a_warning(self):
        """A hand-made codex card with no thread_id: exit 0, the mail lands, `ring failed` names why, no codex run.

        A proper codex join afterward rings in the same root, so the fake
        was reachable.

        @interacts  one hand-written card, one join, two sends, one fake codex.
        @deps       _root.TcRoot.tc, _root.TcRoot.fake_bin.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("codex", CODEX_QUEUE_EXIT["queued"])
            record = folder.parent / "calls.jsonl"
            (root.path / "cards").mkdir()
            (root.path / "cards" / "d.json").write_text(
                json.dumps({"name": "d", "kind": "codex", "route": "codex", "thread_id": None}))
            code, out, err = root.tc("send", "--from", "a", "--to", "d", "hi")
            ran_without_thread = record.exists()
            landed = sorted(p.name for p in (root.path / "mail" / "to-d").glob("*.md"))
            self.join_codex(root)
            root.tc("send", "--from", "a", "--to", "c", "hi")
            self.assertTrue(record.exists(), f"{record} missing: the fake codex is not reachable")
            recorded = calls()
        self.assertEqual(code, 0, f"exited {code}: {err}")
        self.assertIn("ring failed for d: its card has no thread_id; the mail is in its inbox", err)
        self.assertFalse(ran_without_thread, "codex ran with no thread to ring")
        self.assertEqual(landed, ["000001-from-a.md"])
        self.assertEqual(len(recorded), 1)

    def test_a_ring_that_times_out_is_a_warning(self):
        """In process: codex past CODEX_RING_SECONDS gives `ring failed ... no answer in 30 s`, exit 0.

        subprocess.run is swapped for one call, so nothing runs; the test
        also checks the ring's stdin is /dev/null and its timeout is 30 s.

        @interacts  loads tc in process; patches subprocess.run for one
                    deliver_codex call, which writes one message under the root.
        @deps       load_tc, unittest.mock.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        seen = []

        def hangs(argv, **kwargs):
            seen.append((argv, kwargs))
            raise subprocess.TimeoutExpired(argv, kwargs.get("timeout"))

        card = {"name": "c", "kind": "codex", "route": "codex", "thread_id": THREAD}
        with _root.TcRoot() as root:
            tc = load_tc(root)
            with mock.patch.object(subprocess, "run", hangs):
                got = tc.deliver_codex(card, "a", "c", "hi")
            landed = sorted(p.name for p in (root.path / "mail" / "to-c").glob("*.md"))
        self.assertEqual(got.exit, 0)
        self.assertIn(f"ring failed for c: no answer in {CODEX_RING_SECONDS} s; the mail is in its inbox",
                      got.warnings)
        self.assertEqual(landed, ["000001-from-a.md"])
        self.assertEqual(len(seen), 1, "codex was not called exactly once")
        argv, kwargs = seen[0]
        self.assertEqual(argv[:4], ["codex", "queue", "--thread", THREAD])
        self.assertEqual((kwargs.get("stdin"), kwargs.get("timeout")),
                         (subprocess.DEVNULL, CODEX_RING_SECONDS))


if __name__ == "__main__":
    unittest.main()
