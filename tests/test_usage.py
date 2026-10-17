"""
Tests for usage errors (CARDS R6, decision D12): a mistyped command line
exits 9 with the usage on stderr, never 2, which is a `wait` timeout. A
real timeout still exits 2. EMPTYROOT (Claude Opus 5.5, unreviewed): a
TC_ROOT set but empty, or only whitespace, refuses with one line and exit
9 before any command runs; unset still means the folder tc is in.

Model:  Claude Opus 5.5 (the CARDS lane agent), 2026-10-14
Status: unreviewed

@interacts  runs ../tc through tests/_root.py under a throwaway TC_ROOT,
            one root per case, and compares the root's file list before
            and after. EmptyRootTest runs tc itself (run_in), from an
            empty working folder in the root's base, with TC_ROOT empty,
            spaces or unset, and a copy of tc in the root for the unset
            case.
@deps       python3 stdlib (pathlib, shutil, subprocess, sys, unittest);
            tests/_root.py; ../tc.
@complexity O(1) per test: about a dozen tc runs, each under a second,
            and one `tc wait --timeout 1` that runs its full second;
            EmptyRootTest seven more, each refused at once on a fixed tc.
@alloc      one TcRoot per case, removed when its context exits.
"""

import pathlib
import shutil
import subprocess
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
# EMPTYROOT (Claude Opus 5.5, unreviewed): a TC_ROOT that is set but holds
# nothing a folder could be named by. Before EMPTYROOT tc took the working
# folder as its mailbox and made one wherever it ran.
EMPTY_ROOTS = {"empty": "", "spaces": "   "}
# Commands a stranger runs first. The wait's timeout is short so the old tc,
# which runs it, fails in a second instead of waiting the default.
EMPTY_ROOT_COMMANDS = {
    "send": ("send", "--from", "a", "--to", "b", "hi"),
    "wait": ("wait", "b", "--timeout", "1"),
    "health": ("health",),
}
# Words the refusal must carry: what is wrong, and the two ways out.
EMPTY_ROOT_WORDS = ("TC_ROOT is set but empty", "Unset it", "the mailbox's folder")
# A command that writes one known file under the mailbox, for the unset case.
UNSET_ROOT_COMMAND = ("status", "a", "here")
UNSET_ROOT_FILE = pathlib.Path("status") / "a.md"


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


def run_in(script, folder, env, argv):
    """Run `python3 <script> *argv` from `folder` with exactly `env`. Return (exit, stdout, stderr).

    The harness's tc() always sets TC_ROOT to its root, so a test of an
    empty or unset TC_ROOT runs the child itself.

    @interacts  runs one child and waits; its working folder is `folder`.
    @deps       subprocess, sys; _root.DEFAULT_TC_TIMEOUT_SECONDS.
    @complexity O(1) plus the child's own work.
    @alloc      the captured output, returned.
    """
    done = subprocess.run([sys.executable, str(script), *argv], env=env, cwd=folder, capture_output=True,
                          text=True, stdin=subprocess.DEVNULL, timeout=_root.DEFAULT_TC_TIMEOUT_SECONDS)
    return done.returncode, done.stdout, done.stderr


# EMPTYROOT (Claude Opus 5.5, unreviewed): an empty TC_ROOT refuses, exit 9.
class EmptyRootTest(unittest.TestCase):
    """A TC_ROOT set but empty, or only spaces, refuses with words and exit 9, making nothing; unset keeps tc's own folder.

    @interacts  runs tc from an empty working folder inside a TcRoot's
                base, with TC_ROOT empty, spaces or unset, and lists that
                folder after.
    @deps       _root.TcRoot, _root.TC, run_in; shutil.
    @complexity O(1): six refused runs and one run of a copy.
    @alloc      one TcRoot per test, with a working folder and a copy of
                tc in it.
    """

    def test_an_empty_tc_root_refuses_before_any_command_runs(self):
        """send, wait and health with TC_ROOT "" or "   " each exit 9, say what is wrong and what to do, print nothing to stdout, and leave the working folder empty.

        Must reject the old tc, which took the working folder (or a
        folder named by the spaces under it) as the mailbox, made mail/
        or status/ there, and ran the command.

        @interacts  six tc runs from one empty working folder.
        @deps       run_in; EMPTY_ROOTS, EMPTY_ROOT_COMMANDS,
                    EMPTY_ROOT_WORDS.
        @complexity O(1): two values times three commands.
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            work = root.base / "work"
            work.mkdir()
            for label, value in EMPTY_ROOTS.items():
                env = dict(root.env, TC_ROOT=value)
                for command, argv in EMPTY_ROOT_COMMANDS.items():
                    code, out, err = run_in(_root.TC, work, env, argv)
                    left = sorted(str(p.relative_to(work)) for p in work.rglob("*"))
                    with self.subTest(root=label, command=command, check="exit"):
                        self.assertEqual(code, EXIT_USAGE, f"stdout: {out!r}\nstderr: {err!r}")
                    for words in EMPTY_ROOT_WORDS:
                        with self.subTest(root=label, command=command, check=words):
                            self.assertIn(words, err)
                    with self.subTest(root=label, command=command, check="one line"):
                        self.assertEqual(len(err.splitlines()), 1, err)
                    with self.subTest(root=label, command=command, check="stdout"):
                        self.assertEqual(out, "")
                    with self.subTest(root=label, command=command, check="working folder empty"):
                        self.assertEqual(left, [], f"tc {argv} made {left} in the working folder")

    def test_an_unset_tc_root_still_uses_the_folder_tc_is_in(self):
        """With TC_ROOT unset, a copy of tc in a scratch folder writes its status there, run from another folder.

        Must reject a check that refuses an unset TC_ROOT as well as an
        empty one, or one that takes the working folder when unset.

        @interacts  copies tc into the root and runs the copy once from
                    an empty working folder with TC_ROOT unset.
        @deps       run_in; shutil; UNSET_ROOT_COMMAND, UNSET_ROOT_FILE.
        @complexity O(1).
        @alloc      one TcRoot and the copy of tc in it.
        """
        with _root.TcRoot() as root:
            work = root.base / "work"
            work.mkdir()
            copy = root.path / _root.TC.name
            shutil.copy2(_root.TC, copy)
            env = {key: value for key, value in root.env.items() if key != "TC_ROOT"}
            code, out, err = run_in(copy, work, env, UNSET_ROOT_COMMAND)
            made = (root.path / UNSET_ROOT_FILE).is_file()
            left = sorted(str(p.relative_to(work)) for p in work.rglob("*"))
        with self.subTest(check="exit"):
            self.assertEqual(code, 0, err)
        with self.subTest(check="the folder tc is in"):
            self.assertTrue(made, f"no {UNSET_ROOT_FILE} beside the copy of tc")
        with self.subTest(check="working folder empty"):
            self.assertEqual(left, [], f"the copy made {left} in the working folder")


if __name__ == "__main__":
    unittest.main()
