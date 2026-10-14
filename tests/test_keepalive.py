"""
Tests for `tc wait --keepalive` and the keep-alive timing.

@interacts  runs ../tc as a subprocess and loads it as a module for the
            timing math; touches only a tempdir
@deps       python3 stdlib (unittest, subprocess, tempfile, importlib)
@complexity O(1) per test; the slowest waits about 3 s
@alloc      one tempdir per test, removed in tearDown
"""

import importlib.machinery
import importlib.util
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest

TC = pathlib.Path(__file__).resolve().parent.parent / "tc"
SHORT_TTL = "3"            # keepalive_seconds() = 3 - min(300, 3/12) = 2.75 s
SHORT_WAIT_MIN = 2.0
SHORT_WAIT_MAX = 6.0


def load_tc(ttl):
    """Import tc as a module with a given TTL, without running main()."""
    old = os.environ.get("TC_CACHE_TTL_SECONDS")
    os.environ["TC_CACHE_TTL_SECONDS"] = str(ttl)
    try:
        loader = importlib.machinery.SourceFileLoader(f"tc_{ttl}", str(TC))
        mod = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
        loader.exec_module(mod)
        return mod
    finally:
        if old is None:
            os.environ.pop("TC_CACHE_TTL_SECONDS")
        else:
            os.environ["TC_CACHE_TTL_SECONDS"] = old


class KeepaliveTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = dict(os.environ, TC_ROOT=self.tmp.name, TC_CACHE_TTL_SECONDS=SHORT_TTL)

    def tearDown(self):
        self.tmp.cleanup()

    def tc(self, *args, timeout=30):
        return subprocess.run([sys.executable, str(TC), *args], env=self.env,
                              capture_output=True, text=True, timeout=timeout)

    def test_one_hour_ttl_wakes_at_55_minutes(self):
        self.assertEqual(load_tc(3600).keepalive_seconds(), 3300)

    def test_five_minute_ttl_still_waits_most_of_it(self):
        self.assertEqual(load_tc(300).keepalive_seconds(), 275)

    def test_keepalive_wakes_before_the_ttl(self):
        start = time.monotonic()
        r = self.tc("wait", "b", "--keepalive")
        took = time.monotonic() - start
        self.assertEqual(r.returncode, 2)
        self.assertIn("KEEPALIVE", r.stdout)
        self.assertIn("--keepalive", r.stdout)
        self.assertTrue(SHORT_WAIT_MIN <= took <= SHORT_WAIT_MAX, took)

    def test_explicit_timeout_wins_over_keepalive(self):
        start = time.monotonic()
        r = self.tc("wait", "b", "--keepalive", "--timeout", "1")
        self.assertLess(time.monotonic() - start, SHORT_WAIT_MIN)
        self.assertIn("KEEPALIVE", r.stdout)

    def test_mail_still_wakes_a_keepalive_wait(self):
        self.tc("send", "--from", "a", "--to", "b", "hi")
        r = self.tc("wait", "b", "--keepalive")
        self.assertEqual(r.returncode, 0)
        self.assertIn("MAIL", r.stdout)

    def test_plain_wait_still_says_timeout(self):
        r = self.tc("wait", "b", "--timeout", "1")
        self.assertEqual(r.returncode, 2)
        self.assertIn("TIMEOUT", r.stdout)


if __name__ == "__main__":
    unittest.main()
