"""
Tests for `tc health` and `tc watch` against a throwaway TC_ROOT.

@interacts  runs ../tc as a subprocess; starts and kills its own `tc wait`
            listeners; touches only a tempdir
@deps       python3 stdlib (unittest, subprocess, tempfile, json)
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
SETTLE_TIMEOUT = 10
SETTLE_STEP = 0.2
# Thresholds no real machine reaches, so only the condition under test fires.
QUIET = ["--load-ratio", "100000", "--mem-min-pct", "0", "--gpu-max-c", "100000"]


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


if __name__ == "__main__":
    unittest.main()
