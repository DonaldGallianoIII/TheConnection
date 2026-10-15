"""
Tests for `tc health` and `tc watch` against a throwaway TC_ROOT.

@interacts  runs ../tc as a subprocess; starts and kills its own `tc wait`
            listeners; touches only a tempdir. HealthCardsTest (CARDS R5,
            Claude Opus 5.5, unreviewed) runs tc through tests/_root.py
            instead, so no identity variable of the session reaches it; one
            of its tests (phase fix round 1, Claude Opus 5.5, unreviewed)
            makes two card files, two inboxes and a lock file in one of
            them by hand, with ESC in them (the lock in its inbox since
            P3 fix round 1b, Claude Opus 5.5, unreviewed: D35).
@deps       python3 stdlib (json, os, pathlib, subprocess, sys, tempfile,
            time, unittest); tests/_root.py for HealthCardsTest
@complexity O(1) per test; the slowest waits a few poll intervals (about 5 s)
@alloc      one tempdir per test, removed in tearDown; every child process
            is killed in tearDown
"""

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest

TC = pathlib.Path(__file__).resolve().parent.parent / "tc"
# CARDS R5 (Claude Opus 5.5, unreviewed): the harness, for HealthCardsTest.
HERE = pathlib.Path(__file__).resolve().parent
# Run as `python3 -m unittest tests.test_health` from the repo root, tests/
# is not on sys.path; under discover it is. Add it once so both work.
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import _root  # noqa: E402  (needs the path line above)

SETTLE_TIMEOUT = 10
SETTLE_STEP = 0.2
# Thresholds no real machine reaches, so only the condition under test fires.
QUIET = ["--load-ratio", "100000", "--mem-min-pct", "0", "--gpu-max-c", "100000"]
# Phase fix round 1 (Claude Opus 5.5, unreviewed): ESC, a byte a terminal
# acts on, and how tc health must print it.
ESC = "\x1b"
ESC_SHOWN = "\\x1b"


class HealthTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = dict(os.environ, TC_ROOT=self.tmp.name)
        self.procs = []

    def tearDown(self):
        for p in self.procs:
            if p.poll() is None:
                p.kill()
                p.wait()
        self.tmp.cleanup()

    def tc(self, *args, timeout=60):
        return subprocess.run([sys.executable, str(TC), *args], env=self.env,
                              capture_output=True, text=True, timeout=timeout)

    def start(self, *args):
        p = subprocess.Popen([sys.executable, str(TC), *args], env=self.env,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.procs.append(p)
        return p

    def until(self, check):
        end = time.monotonic() + SETTLE_TIMEOUT
        while time.monotonic() < end:
            if check():
                return True
            time.sleep(SETTLE_STEP)
        return False

    def health(self):
        return json.loads(self.tc("health", "--json").stdout)

    def test_health_json_shape(self):
        snap = self.health()
        for key in ("time", "machine", "sessions", "listeners", "watchers", "mail"):
            self.assertIn(key, snap)
        self.assertTrue(0 <= snap["machine"]["mem_avail_pct"] <= 100)
        self.assertGreaterEqual(snap["machine"]["cores"], 1)

    def test_health_finds_a_live_listener_and_its_pid(self):
        p = self.start("wait", "b")
        self.assertTrue(self.until(lambda: self.health()["listeners"].get("b") == p.pid))
        p.kill()
        p.wait()
        self.assertTrue(self.until(lambda: self.health()["listeners"].get("b") is None))

    def test_health_counts_mail(self):
        self.tc("send", "--from", "a", "--to", "b", "one")
        self.tc("send", "--from", "a", "--to", "b", "two")
        self.assertEqual(self.health()["mail"]["b"]["unread"], 2)

    def test_watch_heartbeat_exits_0(self):
        r = self.tc("watch", "a", "--heartbeat", "2", "--poll", "1", *QUIET)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("HEARTBEAT", r.stdout)

    def test_watch_alerts_on_low_memory(self):
        r = self.tc("watch", "a", "--heartbeat", "30", "--poll", "1",
                    "--load-ratio", "100000", "--mem-min-pct", "101", "--gpu-max-c", "100000")
        self.assertEqual(r.returncode, 5)
        self.assertIn("ALERT", r.stdout)
        self.assertIn("mem free", r.stdout)

    def test_watch_alerts_when_a_listener_dies(self):
        b = self.start("wait", "b")
        self.assertTrue(self.until(lambda: self.health()["listeners"].get("b") == b.pid))
        w = self.start("watch", "a", "--names", "b", "--heartbeat", "30", "--poll", "1", *QUIET)
        self.assertTrue(self.until(lambda: self.health()["watchers"].get("a") == w.pid))
        b.kill()
        b.wait()
        out, _ = w.communicate(timeout=SETTLE_TIMEOUT)
        self.assertEqual(w.returncode, 5)
        self.assertIn("LISTENER DOWN: b", out)

    def test_second_watch_for_the_same_name_exits_3(self):
        w = self.start("watch", "a", "--heartbeat", "30", "--poll", "1", *QUIET)
        self.assertTrue(self.until(lambda: self.health()["watchers"].get("a") == w.pid))
        r = self.tc("watch", "a", "--heartbeat", "30", *QUIET)
        self.assertEqual(r.returncode, 3)
        self.assertIn("ALREADY WATCHING", r.stdout)


# CARDS R5 (Claude Opus 5.5, unreviewed): tc health shows cards.
class HealthCardsTest(unittest.TestCase):
    """`tc health` and `tc health --json` show every card.

    @interacts  runs tc through tests/_root.py under a throwaway TC_ROOT;
                identity variables go only where a call passes them.
    @deps       _root.TcRoot.
    @complexity O(1): two joins, one card, three health runs.
    @alloc      one TcRoot, removed when its context exits.
    """

    def test_health_shows_each_card_in_text_and_json(self):
        """The `cards` key lists name, kind, account, route, reports_to, ssh_target; the `cards` line says it as `tc cards` does.

        With no cards: an empty list and `cards      none`.

        @interacts  three tc health runs, two joins, one tc card.
        @deps       _root.TcRoot.tc.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            empty_json = json.loads(root.tc("health", "--json")[1])
            empty_text = root.tc("health")[1]
            root.tc("join", "b", "--reports-to", "a", env={"CLAUDECODE": "1"})
            root.tc("join", "c", "--account", "work", env={"CODEX_THREAD_ID": "t1"})
            root.tc("card", "x", "--ssh", "u@h", "--account", "far")
            code, out, err = root.tc("health", "--json")
            tcode, text, terr = root.tc("health")
        self.assertEqual(empty_json["cards"], [])
        self.assertIn("\ncards      none\n", empty_text)
        self.assertEqual(code, 0, err)
        # CARDS fix round 1 (Claude Opus 5.5, unreviewed): ssh_target,
        # null unless the route is ssh, and the ssh card in `tc cards`' words.
        self.assertEqual(json.loads(out)["cards"], [
            {"name": "b", "kind": "claude", "account": "unknown", "route": "local", "reports_to": "a",
             "ssh_target": None},
            {"name": "c", "kind": "codex", "account": "work", "route": "codex", "reports_to": None,
             "ssh_target": None},
            {"name": "x", "kind": "other", "account": "far", "route": "ssh", "reports_to": None,
             "ssh_target": "u@h"},
        ])
        self.assertEqual(tcode, 0, terr)
        self.assertIn("\ncards      b (claude, account unknown, route local), reports to a\n"
                      "           c (codex, account work, route codex)\n"
                      "           x (other, account far, route ssh to u@h)\n", text)


    # Phase fix round 1 (Claude Opus 5.5, unreviewed): escaped output.
    def test_health_escapes_control_characters(self):
        """ESC in a card's account, a card file's name, an inbox's name and a listener lock's name: tc health prints escapes.

        Must reject a card field or a file name printed raw: the terminal
        would act on it.

        @interacts  two hand-written card files, two inbox folders and one
                    lock file in the second, made by hand; one tc health.
        @deps       _root.TcRoot.tc.
        @complexity O(1): one health run.
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            cards = root.path / "cards"
            cards.mkdir()
            (cards / "b.json").write_text(json.dumps(
                {"name": "b", "kind": "claude", "account": f"{ESC}[2J", "route": "local"}))
            (cards / f"{ESC}q.json").write_text("{ not json")
            mail = root.path / "mail"
            (mail / f"to-{ESC}x").mkdir(parents=True)
            (mail / f"to-{ESC}y").mkdir()  # P3 fix round 1b (Claude Opus 5.5, unreviewed): D35, the lock in its inbox
            (mail / f"to-{ESC}y" / ".wait.lock").touch()
            code, out, err = root.tc("health")
        self.assertEqual(code, 0, err)
        self.assertNotIn(ESC, out, "tc health printed a raw ESC")
        for shown in (f"{ESC_SHOWN}q (?, account ?, route ?)", f"b (claude, account {ESC_SHOWN}[2J, route local)",
                      f"{ESC_SHOWN}x: 0 unread", f"stopped: {ESC_SHOWN}y"):
            self.assertIn(shown, out)


if __name__ == "__main__":
    unittest.main()
