"""
Tests for usage errors (CARDS R6, decision D12): a mistyped command line
exits 9 with the usage on stderr, never 2, which is a `wait` timeout. A
real timeout still exits 2.

Model:  Claude Opus 5.5 (the CARDS lane agent), 2026-10-14
Status: unreviewed

@interacts  runs ../tc through tests/_root.py under a throwaway TC_ROOT,
            one root per case, and compares the root's file list before
            and after.
@deps       python3 stdlib (pathlib, sys, unittest); tests/_root.py; ../tc.
@complexity O(1) per test: about a dozen tc runs, each under a second,
            and one `tc wait --timeout 1` that runs its full second.
@alloc      one TcRoot per case, removed when its context exits.
"""

import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
# Run as `python3 -m unittest tests.test_usage` from the repo root, tests/
# is not on sys.path; under discover it is. Add it once so both work.
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import _root  # noqa: E402  (needs the path line above)

# The codes, written here rather than read from tc.
EXIT_USAGE = 9
EXIT_TIMEOUT = 2

# Errors the top parser finds: no command, an unknown command, and an
# unknown flag (argparse hands leftovers back to the top parser, so
# `wait --timeot` is reported there).
TOP_PARSER_ERRORS = [
    (),
    ("frobnicate",),
    ("wait", "--timeot", "1", "b"),
]
# Errors a subcommand's own parser finds. Only these go red when the
# override sits on the top parser alone.
SUBPARSER_ERRORS = [
    ("send", "--to", "b", "hi"),
    ("wait",),
    ("wait", "b", "--timeout", "soon"),
    ("send", "--from", "a", "--to", "-x", "hi"),
    ("card", "x", "--ssh", "-oProxyCommand=y"),
    ("join", "b", "--kind", "robot"),
]


def files_under(root):
    """Every path under the root's TC_ROOT, relative and sorted.

    @interacts  walks root.path. Writes nothing.
    @deps       pathlib.
    @complexity O(f) over f files and folders under the root (a handful).
    @alloc      one list of strings, returned.
    """
    return sorted(str(p.relative_to(root.path)) for p in root.path.rglob("*"))


class UsageTest(unittest.TestCase):
    """Usage errors exit 9 from every parser; a timeout still exits 2.

    @interacts  see the module block.
    @deps       _root.TcRoot.
    @complexity O(1) per test.
    @alloc      one TcRoot per case.
    """

    def assert_usage_error(self, argv):
        """`tc *argv` exits 9 with `usage:` on stderr, prints nothing to stdout, writes nothing.

        @interacts  one tc run in its own root.
        @deps       _root.TcRoot.tc, files_under.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            code, out, err = root.tc(*argv)
            after = files_under(root)
        self.assertEqual(code, EXIT_USAGE, f"tc {argv} exited {code}\nstdout: {out}\nstderr: {err}")
        self.assertTrue(err.startswith("usage:"), f"tc {argv} stderr: {err!r}")
        self.assertEqual(out, "", f"tc {argv} printed to stdout: {out!r}")
        self.assertEqual(after, [], f"tc {argv} wrote {after}")

    def test_a_mistyped_wait_exits_9_not_2(self):
        """`tc wait --timeot 1 b` exits 9 with `usage:` and no TIMEOUT line.

        @interacts  one tc run.
        @deps       assert_usage_error.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        self.assert_usage_error(("wait", "--timeot", "1", "b"))

    def test_a_real_timeout_still_exits_2(self):
        """`tc wait b --timeout 1` exits 2 with a TIMEOUT line.

        @interacts  one tc wait that runs its full second.
        @deps       _root.TcRoot.tc.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            code, out, err = root.tc("wait", "b", "--timeout", "1")
        self.assertEqual(code, EXIT_TIMEOUT, f"exited {code}: {err}")
        self.assertTrue(out.startswith("TIMEOUT: no mail for b"), out)

    def test_the_top_parser_exits_9(self):
        """No command, an unknown command and an unknown flag each exit 9 and write nothing.

        @interacts  one tc run per case.
        @deps       assert_usage_error.
        @complexity O(1): three cases.
        @alloc      one TcRoot per case.
        """
        for argv in TOP_PARSER_ERRORS:
            with self.subTest(argv=argv):
                self.assert_usage_error(argv)

    def test_every_subcommand_parser_exits_9(self):
        """A missing --from, a missing name, a bad --timeout, a dash-led value, a bad choice: 9 each.

        Must reject an override on the top parser only: each of these is
        found by the subcommand's own parser, which would exit 2.

        @interacts  one tc run per case.
        @deps       assert_usage_error.
        @complexity O(1): six cases.
        @alloc      one TcRoot per case.
        """
        for argv in SUBPARSER_ERRORS:
            with self.subTest(argv=argv):
                self.assert_usage_error(argv)

    def test_help_is_not_an_error(self):
        """`tc --help` and `tc wait --help` exit 0 with the usage on stdout.

        @interacts  two tc runs.
        @deps       _root.TcRoot.tc.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            top = root.tc("--help")
            wait = root.tc("wait", "--help")
        self.assertEqual(top[0], 0, top[2])
        self.assertTrue(top[1].startswith("usage: tc"), top[1])
        self.assertEqual(wait[0], 0, wait[2])
        self.assertTrue(wait[1].startswith("usage: tc wait"), wait[1])


if __name__ == "__main__":
    unittest.main()
