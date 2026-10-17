"""
Tests for mailbox names (CARDS R1, contract C0): every command refuses a
bad name with exit 6 and C0's words, before it writes anything.

Model:  Claude Opus 5.5 (the CARDS lane agent), 2026-10-14
Status: unreviewed

@interacts  runs ../tc through tests/_root.py under a throwaway TC_ROOT,
            one root per case, and compares the root's file list before
            and after. Loads tc as a module for valid_name(), with TC_ROOT
            set to the harness root first and restored after.
@deps       python3 stdlib (os, pathlib, sys, unittest);
            tests/_root.py (load_source loads tc with no bytecode cache,
            R30); ../tc.
@complexity O(1) per test: at most one tc run per case, a dozen cases,
            each run under a second.
@alloc      one TcRoot per case, removed when its context exits. Nothing
            is kept between tests.
"""

import os
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
# Run as `python3 -m unittest tests.test_names` from the repo root, tests/
# is not on sys.path; under discover it is. Add it once so both work.
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import _root  # noqa: E402  (needs the path line above)

# C0's words, written out here rather than read from tc, so a change to
# them fails this test instead of following it.
BAD_NAME_WORDS = ('tc: bad name "{name}": letters, digits, dot, dash, underscore, '
                  '1 to 64, not starting with a dash\n')
EXIT_BAD_NAME = 6
# The longest name C0 allows.
NAME_MAX = 64

GOOD = ["a", "b", "work-api", "home.football_1", ".a", "_x", "a-", "a" * NAME_MAX,
        "A9.b-c_d"]
BAD = ["", "-x", ".", "..", "...", "a b", "a/b", "../x", "a\n", "a" * (NAME_MAX + 1),
       "a$b", "é"]

# Each case: a bad name and the command line that gives it. --timeout and
# --heartbeat keep a broken check short: the command would run 1 s, not hours.
CASES = [
    ("../x", ("send", "--from", "a", "--to", "../x", "hi")),
    ("../a", ("send", "--from", "../a", "--to", "b", "hi")),
    ("-x", ("send", "--from", "a", "--to=-x", "hi")),
    ("-a", ("send", "--from=-a", "--to", "b", "hi")),
    ("a b", ("read", "a b")),
    ("-x", ("read", "--", "-x")),
    ("", ("read", "")),
    ("a" * (NAME_MAX + 1), ("read", "a" * (NAME_MAX + 1))),
    ("..", ("peek", "..")),
    ("..", ("wait", "..", "--timeout", "1")),
    ("a/b", ("status", "a/b", "text")),
    ("..", ("watch", "..", "--heartbeat", "1", "--poll", "1")),
]


def files_under(root):
    """Every path under the root's TC_ROOT, relative and sorted.

    @interacts  walks root.path. Writes nothing.
    @deps       pathlib.
    @complexity O(f) over f files and folders under the root (a handful).
    @alloc      one list of strings, returned.
    """
    return sorted(str(p.relative_to(root.path)) for p in root.path.rglob("*"))


def load_tc(root):
    """Load ../tc as a module with TC_ROOT set to `root`, without running main().

    tc reads TC_ROOT once, at import, so it is set before the load and the
    old value is put back after.

    @interacts  sets and restores os.environ["TC_ROOT"]; runs tc's top
                level (constants only, no disk writes). Reads and writes
                no bytecode cache (_root.load_source; R30, Claude Opus
                5.5, unreviewed).
    @deps       os; _root.TC, _root.load_source.
    @complexity O(s) over s bytes of tc: one compile.
    @alloc      one module object, returned.
    """
    old = os.environ.get("TC_ROOT")
    os.environ["TC_ROOT"] = str(root.path)
    try:
        return _root.load_source("tc_names_under_test", _root.TC)
    finally:
        if old is None:
            os.environ.pop("TC_ROOT", None)
        else:
            os.environ["TC_ROOT"] = old


class NamesTest(unittest.TestCase):
    """C0 names: the rule, every command's check, and that nothing is written.

    @interacts  see the module block.
    @deps       _root.TcRoot.
    @complexity O(1) per test.
    @alloc      one TcRoot per case.
    """

    def test_the_rule(self):
        """valid_name() takes every GOOD name and refuses every BAD one.

        Must reject a rule that lets a leading dash through, or a match
        that stops before a trailing newline.

        @interacts  loads tc in process.
        @deps       load_tc.
        @complexity O(g + b) over the two lists.
        @alloc      one TcRoot and one module.
        """
        with _root.TcRoot() as root:
            tc = load_tc(root)
            for name in GOOD:
                self.assertTrue(tc.valid_name(name), f"valid_name({name!r}) refused a good name")
            for name in BAD:
                self.assertFalse(tc.valid_name(name), f"valid_name({name!r}) took a bad name")

    def test_every_command_refuses_a_bad_name_and_writes_nothing(self):
        """Each case exits 6 with C0's words and leaves the root's file list empty.

        Covers --to, --from (space and = forms), read, peek, wait, status
        and watch. Must reject a check on --to only, and a rule that lets
        a leading dash through (`--to=-x` makes mail/to--x/ without one).

        @interacts  one tc run per case, each in its own root.
        @deps       _root.TcRoot.tc, files_under.
        @complexity O(1): twelve cases.
        @alloc      one TcRoot per case.
        """
        for name, argv in CASES:
            with self.subTest(argv=argv):
                with _root.TcRoot() as root:
                    before = files_under(root)
                    code, out, err = root.tc(*argv)
                    after = files_under(root)
                self.assertEqual(code, EXIT_BAD_NAME,
                                 f"tc {argv} exited {code}\nstdout: {out}\nstderr: {err}")
                self.assertEqual(err, BAD_NAME_WORDS.format(name=name), f"tc {argv} said: {err!r}")
                self.assertEqual(after, before, f"tc {argv} wrote {after}")

    def test_a_leading_dash_after_a_space_is_refused_by_the_parser(self):
        """`--to -x` never reaches valid_name(): the parser refuses it, and nothing is written.

        The parser reads `-x` as a flag. Its exit code is the usage error
        (2 before task R6, 9 after; tests/test_usage.py pins 9), so this
        test asserts a usage refusal, not a number.

        @interacts  one tc run.
        @deps       _root.TcRoot.tc, files_under.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        argv = ("send", "--from", "a", "--to", "-x", "hi")
        with _root.TcRoot() as root:
            code, out, err = root.tc(*argv)
            after = files_under(root)
        self.assertNotIn(code, (0, EXIT_BAD_NAME), f"tc {argv} exited {code}: {err}")
        self.assertIn("usage:", err, f"tc {argv} said: {err!r}")
        self.assertEqual(after, [], f"tc {argv} wrote {after}")

    def test_good_names_still_send(self):
        """A send between two good names exits 0 and lands in mail/to-<to>/.

        The control for the refusals above: a check that refused every
        name would pass them and fail here.

        @interacts  one tc run.
        @deps       _root.TcRoot.tc.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            code, out, err = root.tc("send", "--from", "work-api", "--to", "home.football_1", "hi")
            landed = sorted(p.name for p in (root.path / "mail" / "to-home.football_1").glob("*.md"))
        self.assertEqual(code, 0, f"tc send exited {code}: {err}")
        self.assertEqual(landed, ["000001-from-work-api.md"])


if __name__ == "__main__":
    unittest.main()
