"""
Tests for tests/_root.py: a listener started through the harness holds its
lock at the moment it is handed over, `tc health --json` names it, and its
pid is gone once the context exits.

Model:  Claude Opus 5.5 (the GROUND lane agent), 2026-10-14
Status: unreviewed

@interacts  runs ../tc through tests/_root.py under a throwaway TC_ROOT;
            starts one `tc wait` per test and relies on the harness to kill
            it. Reads /proc/locks and /proc/<pid> with its own code, kept
            apart from the harness's reader so a bug in one cannot hide in
            the other.
@deps       python3 stdlib (json, os, pathlib, sys, unittest);
            tests/_root.py; Linux only (/proc).
@complexity O(1) per test: one listener, one or two `tc health` runs (each
            O(p + k + n) inside tc, see tc's header). Under a second each.
@alloc      one TcRoot per test, removed when its context exits. Nothing is
            kept between tests.
"""

import json
import os
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
# Run as `python3 -m unittest tests.test_root` from the repo root, tests/ is
# not on sys.path; under discover it is. Add it once so both work.
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import _root  # noqa: E402  (needs the path line above)

# Long enough that a listener never times out on its own during a test. The
# harness kills it the moment its context exits, so this is a ceiling only.
LISTENER_TIMEOUT_SECONDS = 30
NAME = "b"


def held_by(path):
    """Pids holding an flock on `path`, read from /proc/locks by this file.

    Written apart from _root.flock_holders on purpose: the test proves the
    harness, so it does not borrow the harness's reader.

    @interacts  stats `path`; reads /proc/locks. Writes nothing.
    @deps       os, pathlib; Linux /proc/locks.
    @complexity O(k) over k lines in /proc/locks, tens on a desktop.
    @alloc      the table's lines and one set, freed on return.
    """
    if not os.path.exists(path):
        return set()
    st = os.stat(path)
    inode = f"{os.major(st.st_dev):02x}:{os.minor(st.st_dev):02x}:{st.st_ino}"
    pids = set()
    for line in pathlib.Path("/proc/locks").read_text().splitlines():
        cols = line.split()
        if "->" in cols:
            continue  # a blocked waiter, not a holder
        if "FLOCK" in cols and inode in cols:
            pids.add(int(cols[cols.index(inode) - 1]))
    return pids


def in_proc(pid):
    """True while /proc has an entry for `pid`: running, or a zombie not yet reaped.

    @interacts  stats /proc/<pid>.
    @deps       pathlib.
    @complexity O(1).
    @alloc      none.
    """
    return pathlib.Path(f"/proc/{pid}").exists()


class RootTest(unittest.TestCase):
    """The harness's listener: proven at yield, named by tc, gone after.

    @interacts  see the module block.
    @deps       _root.TcRoot.
    @complexity O(1) per test.
    @alloc      one TcRoot per test.
    """

    def test_listener_holds_its_lock_at_yield_and_health_names_it(self):
        """At yield the pid holds mail/.wait-b.lock, and tc health --json names it.

        Must reject a harness that yields before the lock is held: the
        first line inside the context reads /proc/locks before anything
        else can run, so a listener still starting up fails it.

        @interacts  one listener; one `tc health --json`.
        @deps       _root.TcRoot.listener, held_by.
        @complexity O(1).
        @alloc      one TcRoot, removed on exit.
        """
        with _root.TcRoot() as root:
            lock = root.path / "mail" / f".wait-{NAME}.lock"
            with root.listener(NAME, LISTENER_TIMEOUT_SECONDS) as pid:
                holders = held_by(lock)
                self.assertIn(pid, holders,
                              f"at yield, pid {pid} does not hold {lock}; holders: {holders}")
                code, out, err = root.tc("health", "--json")
                self.assertEqual(code, 0, f"tc health --json exited {code}: {err}")
                self.assertEqual(json.loads(out)["listeners"].get(NAME), pid,
                                 f"tc health --json did not name pid {pid} for {NAME}:\n{out}")

    def test_listener_pid_is_gone_after_its_context(self):
        """After the context the pid is killed and reaped, and nothing holds the lock.

        Also checks the root's folder is removed once TcRoot exits.

        @interacts  one listener; one `tc health --json` after it stops.
        @deps       _root.TcRoot.listener, held_by, in_proc.
        @complexity O(1).
        @alloc      one TcRoot, removed on exit.
        """
        with _root.TcRoot() as root:
            lock = root.path / "mail" / f".wait-{NAME}.lock"
            with root.listener(NAME, LISTENER_TIMEOUT_SECONDS) as pid:
                self.assertTrue(in_proc(pid), f"pid {pid} not in /proc while its context is open")
            self.assertFalse(in_proc(pid),
                             f"pid {pid} still in /proc after its context: running, or a zombie")
            self.assertNotIn(pid, held_by(lock), f"pid {pid} still holds {lock}")
            code, out, err = root.tc("health", "--json")
            self.assertEqual(code, 0, f"tc health --json exited {code}: {err}")
            listeners = json.loads(out)["listeners"]
            self.assertIn(NAME, listeners, f"tc health --json lost the lock file for {NAME}:\n{out}")
            self.assertIsNone(listeners[NAME], f"tc health --json still names a pid for {NAME}:\n{out}")
        self.assertFalse(root.path.exists(), f"{root.path} left behind after TcRoot exited")


if __name__ == "__main__":
    unittest.main()
