"""
Tests for the invoked name (NAME): tc's hints and usage lines say the
name tc was run by. Most Linux systems already have a `tc` (traffic
control), so a person may link ours as `tconn`; a hint that told them
`tc read b` would then run the wrong program.

Model:  Claude Opus 5.5 (the NAME lane agent), 2026-10-17
Status: unreviewed

@interacts  runs ../tc through tests/_root.py under a throwaway TC_ROOT,
            one root per case: by its own path, by a symlink named
            LINK_NAME in the root's temp folder (python3 on the link's
            path, as the harness runs tc), and through python3 -c and
            exec with a sys.argv[0] tc cannot use. Writes the link and the mail of
            each case inside that temp folder only.
@deps       python3 stdlib (pathlib, sys, unittest); tests/_root.py; ../tc.
@complexity O(1) per test: a handful of tc runs, each under a second,
            plus one `wait --timeout WAIT_TIMEOUT` per name for the
            TIMEOUT case, which runs its full WAIT_TIMEOUT seconds.
@alloc      one TcRoot per case, removed when its context exits.
"""

import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
# Run as `python3 -m unittest tests.test_invoked_name` from the repo root,
# tests/ is not on sys.path; under discover it is. Add it once so both work.
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import _root  # noqa: E402  (needs the path line above)

# The codes, written here rather than read from tc.
EXIT_USAGE = 9
EXIT_TIMEOUT = 2
# The other name a stranger links tc under, as README.md's install step says.
LINK_NAME = "tconn"
# The plain name, and tc's fallback when sys.argv[0] gives nothing usable.
PLAIN_NAME = "tc"
# Seconds a wait in these tests may run: long enough for a mail case to
# find the message on its first poll, short enough that a TIMEOUT case
# costs little.
WAIT_TIMEOUT = "1"
# Seconds to let one started child finish before the test gives up on it.
CHILD_SECONDS = 30
# sys.argv[0] values tc cannot use as a name to type: empty, and the
# `python3 -m unittest` form, whose spaces a pasted command would split.
UNUSABLE_ARGV0 = ("", "python3 -m unittest")
# Runs the tc at argv[1] as __main__ with sys.argv[0] set to argv[2] and
# the rest as its arguments: the only way to hand tc an argv[0] that no
# file on disk could be named. exec, not runpy.run_path, which sets
# sys.argv[0] back to the file's path.
RUN_WITH_ARGV0 = ("import sys; tc, arg0 = sys.argv[1], sys.argv[2]; sys.argv = [arg0, *sys.argv[3:]]; "
                  "source = open(tc, encoding='utf-8').read(); "
                  "exec(compile(source, tc, 'exec'), {'__name__': '__main__', '__file__': tc})")


def run_as(root, program, *args):
    """Run `python3 <program> *args` under `root`; return (exit, stdout, stderr).

    @interacts  starts one child through root.start (its env, its
                teardown) and waits for it.
    @deps       _root.TcRoot.start; sys.executable.
    @complexity O(1), plus the child's own work.
    @alloc      the captured output, returned.
    """
    proc = root.start(argv=[sys.executable, str(program), *args])
    out, err = proc.communicate(timeout=CHILD_SECONDS)
    return proc.returncode, out, err


def link_tc(root):
    """A symlink named LINK_NAME to ../tc in `root`'s temp folder, outside TC_ROOT; its path.

    @interacts  creates one symlink in root.base.
    @deps       pathlib; _root.TC.
    @complexity O(1).
    @alloc      one directory entry, removed with the temp folder.
    """
    link = root.base / LINK_NAME
    link.symlink_to(_root.TC)
    return link


class InvokedNameTest(unittest.TestCase):
    """Hints and usage lines say `tconn` run as tconn, and `tc` run as tc.

    @interacts  see the module block.
    @deps       _root.TcRoot, run_as, link_tc.
    @complexity O(1) per test.
    @alloc      one TcRoot per case.
    """

    def programs(self, root):
        """(name, path) for each way a case runs tc: by LINK_NAME, and by its plain path.

        @interacts  makes the link (link_tc).
        @deps       link_tc; _root.TC.
        @complexity O(1).
        @alloc      a list of two pairs.
        """
        return [(LINK_NAME, link_tc(root)), (PLAIN_NAME, _root.TC)]

    def test_the_mail_line_names_the_invoked_name(self):
        """`wait b` with mail waiting says `Run: <name> read b`.

        @interacts  one send, then one wait per name, each in its own root.
        @deps       run_as, programs.
        @complexity O(1): two names.
        @alloc      one TcRoot per name.
        """
        for name in (LINK_NAME, PLAIN_NAME):
            with self.subTest(name=name), _root.TcRoot() as root:
                program = dict(self.programs(root))[name]
                code, out, err = root.tc("send", "--from", "a", "--to", "b", "hello")
                self.assertEqual(code, 0, f"send exited {code}: {err}")
                code, out, err = run_as(root, program, "wait", "b", "--timeout", WAIT_TIMEOUT)
                self.assertEqual(code, 0, f"{name} wait exited {code}\nstdout: {out}\nstderr: {err}")
                self.assertEqual(out.strip(), f"MAIL: 1 unread for b. Run: {name} read b")

    def test_the_timeout_line_names_the_invoked_name(self):
        """`wait b` with no mail exits 2 and says `Re-arm: <name> wait b`.

        @interacts  one wait per name, each in its own root, running its
                    full WAIT_TIMEOUT.
        @deps       run_as, programs.
        @complexity O(1): two names.
        @alloc      one TcRoot per name.
        """
        for name in (LINK_NAME, PLAIN_NAME):
            with self.subTest(name=name), _root.TcRoot() as root:
                program = dict(self.programs(root))[name]
                code, out, err = run_as(root, program, "wait", "b", "--timeout", WAIT_TIMEOUT)
                self.assertEqual(code, EXIT_TIMEOUT, f"{name} wait exited {code}\nstdout: {out}\nstderr: {err}")
                self.assertTrue(out.startswith("TIMEOUT: no mail for b"), out)
                self.assertTrue(out.rstrip().endswith(f"Re-arm: {name} wait b"), out)

    def test_the_usage_line_names_the_invoked_name(self):
        """A missing name exits 9 with `usage: <name> wait`, and --help says `usage: <name>`.

        @interacts  two tc runs per name, in one root.
        @deps       run_as, programs.
        @complexity O(1): two names.
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            for name, program in self.programs(root):
                with self.subTest(name=name):
                    code, out, err = run_as(root, program, "wait")
                    self.assertEqual(code, EXIT_USAGE, f"{name} wait exited {code}: {err}")
                    self.assertTrue(err.startswith(f"usage: {name} wait "), err)
                    code, out, err = run_as(root, program, "--help")
                    self.assertEqual(code, 0, f"{name} --help exited {code}: {err}")
                    self.assertTrue(out.startswith(f"usage: {name} "), out)

    def test_an_unusable_argv0_falls_back_to_tc(self):
        """An empty sys.argv[0], or one with spaces, gives `tc` in the usage line.

        @interacts  one tc run per value, through python3 -c and exec.
        @deps       _root.TcRoot.start; RUN_WITH_ARGV0.
        @complexity O(1): two values.
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            for arg0 in UNUSABLE_ARGV0:
                with self.subTest(arg0=arg0):
                    proc = root.start(argv=[sys.executable, "-c", RUN_WITH_ARGV0, str(_root.TC), arg0, "wait"])
                    out, err = proc.communicate(timeout=CHILD_SECONDS)
                    self.assertEqual(proc.returncode, EXIT_USAGE, f"exited {proc.returncode}: {err}")
                    self.assertTrue(err.startswith(f"usage: {PLAIN_NAME} wait "), err)


if __name__ == "__main__":
    unittest.main()
