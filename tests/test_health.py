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
            StuckOutboxTest (P3 fix round 1c, Claude Opus 5.5,
            unreviewed: D36 (4)) runs tc through tests/_root.py with a
            fake `ssh` that records its argv (asserted called), dates
            three outbox files by hand, and loads tc as a module (TC_ROOT
            set to the harness root first, put back after) with
            wall_clock and gpu_stats replaced, so no program runs. P3 fix
            round 2 (Claude Opus 5.5, unreviewed): one of its tests makes
            another member's branch, a message in it, and a FIFO or a
            symlink (to a file in the root's temp folder) at its note by
            hand, and runs tc health with a ceiling on its time.
            HealthRootTest (R2, Claude Opus 5.5, unreviewed) runs tc
            through tests/_root.py with TC_ROOT set, then a copy of tc
            it puts in the root, with TC_ROOT unset, so the default is
            that root and never this checkout's own mailbox.
@deps       python3 stdlib (argparse, contextlib, io, json, os, pathlib,
            shutil, subprocess, sys, tempfile, time, unittest,
            unittest.mock);
            tests/_root.py for HealthCardsTest and StuckOutboxTest;
            load_tc from test_codex_route.py; FAKE_CONNECT_STDERR,
            OTHER_MEMBER, SSH_CONNECT_FAILED, TARGET, assert_called, login
            and queue from test_ssh_route.py
@complexity O(1) per test; the slowest waits a few poll intervals (about 5 s)
@alloc      one tempdir per test, removed in tearDown; every child process
            is killed in tearDown
"""

import argparse
import contextlib
import io
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

TC = pathlib.Path(__file__).resolve().parent.parent / "tc"
# CARDS R5 (Claude Opus 5.5, unreviewed): the harness, for HealthCardsTest.
HERE = pathlib.Path(__file__).resolve().parent
# Run as `python3 -m unittest tests.test_health` from the repo root, tests/
# is not on sys.path; under discover it is. Add it once so both work.
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import _root  # noqa: E402  (needs the path line above)
from test_codex_route import load_tc  # noqa: E402
from test_ssh_route import (FAKE_CONNECT_STDERR, OTHER_MEMBER, SSH_CONNECT_FAILED, TARGET, assert_called,  # noqa: E402
                            login, queue)

SETTLE_TIMEOUT = 10
SETTLE_STEP = 0.2
# Thresholds no real machine reaches, so only the condition under test fires.
QUIET = ["--load-ratio", "100000", "--mem-min-pct", "0", "--gpu-max-c", "100000"]
# Phase fix round 1 (Claude Opus 5.5, unreviewed): ESC, a byte a terminal
# acts on, and how tc health must print it.
ESC = "\x1b"
ESC_SHOWN = "\\x1b"
# P3 fix round 1c (Claude Opus 5.5, unreviewed): D36 (4). How long an
# outbox message waits before tc health lists it (tc's
# OUTBOX_STALE_SECONDS, a day, written here); an hour, for a file dated
# either side of it; and the time the replaced clock reads, any fixed
# moment well after the epoch.
STALE_SECONDS = 86400
HOUR_SECONDS = 3600
CLOCK = 2000000000
# P3 fix round 2 (Claude Opus 5.5, unreviewed): test-strategist REC-5. How
# old the other member's waiting message is, two days, by its real mtime
# (a subprocess's clock is the real one); how long one tc health may take
# before it counts as hung on a planted note; how far its age may stray
# from the two days in the time the run takes; the other member's
# message, by name; the note's ending (tc's REFUSAL_NOTE_SUFFIX); and the
# text of a file outside the mailbox a planted link at the note leads to.
TWO_DAYS_SECONDS = 2 * STALE_SECONDS
HEALTH_CEILING_SECONDS = 10
AGE_SLACK_SECONDS = 30
OTHERS_MESSAGE = "000003-from-{member}.md"
NOTE_SUFFIX = ".stderr"
OUTSIDE_NOTE_TEXT = "outside the mailbox: tc health must never read this"
# R2 (Claude Opus 5.5, unreviewed): the mailbox tc health read and where
# that came from, written here rather than read from tc: health's first
# line in words, the --json keys, and each source's value and words.
ROOT_LINE = "mailbox    {root}, {words}"
ROOT_KEY = "root"
ROOT_FROM_KEY = "root_from"
ROOT_FROM_ENV = "TC_ROOT"
ROOT_FROM_DEFAULT = "default"
ROOT_FROM_ENV_WORDS = "from TC_ROOT"
ROOT_FROM_DEFAULT_WORDS = "TC_ROOT unset, so the folder tc is in"


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


# P3 fix round 1c (Claude Opus 5.5, unreviewed): D36 (4), the audit's LOW-4.
class StuckOutboxTest(unittest.TestCase):
    """A queue that stays stuck is shown, not hidden: tc health lists every outbox message waiting longer than a day, retried or not.

    @interacts  runs tc through tests/_root.py; loads tc in process
                (TC_ROOT set to the harness root first, put back after)
                with wall_clock and gpu_stats replaced; sets three files'
                times by hand.
    @deps       _root.TcRoot, load_tc.
    @complexity O(1): three sends, one in-process snapshot and print.
    @alloc      one TcRoot and one module.
    """

    def test_a_message_waiting_past_a_day_is_listed_with_its_note_and_a_younger_one_is_not(self):
        """Three ssh messages for b: #1 tried and kept (its note names the connection's reason), #2 queued behind it and never tried, both dated past a day by the replaced clock, #3 an hour short of it: health lists #1 with its note's first line and #2 with none, never #3, in --json and in words.

        Must reject a stuck queue health never shows (a far box that stays
        broken hides behind retries), a file listed only once retried, and
        a younger file listed.

        @interacts  one tc card, three sends, one fake; os.utime on three
                    files; loads tc and calls health_snapshot and
                    cmd_health in process.
        @deps       load_tc, queue, assert_called, login; argparse,
                    contextlib, io, os, unittest.mock.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("ssh", SSH_CONNECT_FAILED, stderr=FAKE_CONNECT_STDERR)
            root.tc("card", "b", "--ssh", TARGET)
            for body in ("one", "two", "three"):
                root.tc("send", "--from", "a", "--to", "b", body)
            assert_called(self, folder, calls)
            box = queue(root, "b")
            ages = {"000001-from-a.md": STALE_SECONDS + HOUR_SECONDS, "000002-from-a.md": STALE_SECONDS + 1,
                    "000003-from-a.md": STALE_SECONDS - HOUR_SECONDS}
            for name, age in ages.items():
                os.utime(box / name, (CLOCK - age, CLOCK - age))
            tc = load_tc(root)
            with mock.patch.object(tc, "wall_clock", lambda: CLOCK), mock.patch.object(tc, "gpu_stats", lambda: None):
                stuck = tc.health_snapshot(gpu=False)["stuck_outbox"]
                with contextlib.redirect_stdout(io.StringIO()) as printed:
                    tc.cmd_health(argparse.Namespace(json=False))
            text = printed.getvalue()
        note = f"could not reach {TARGET} ({FAKE_CONNECT_STDERR.strip()})"
        self.assertEqual(stuck, [
            {"member": login(), "to": "b", "path": str(box / "000001-from-a.md"),
             "age_s": STALE_SECONDS + HOUR_SECONDS, "note": note},
            {"member": login(), "to": "b", "path": str(box / "000002-from-a.md"), "age_s": STALE_SECONDS + 1,
             "note": None}])
        self.assertIn(f"\nstuck      {box / '000001-from-a.md'}: {login()}'s mail to b, waiting 1d; "
                      f"last failed try: {note}\n", text)
        self.assertIn(f"\nstuck      {box / '000002-from-a.md'}: {login()}'s mail to b, waiting 1d; "
                      f"no failed try noted beside it\n", text)
        self.assertNotIn("000003-from-a.md", text, "a message younger than a day was listed")

    # P3 fix round 2 (Claude Opus 5.5, unreviewed): test-strategist REC-5, D36 (4)'s case.
    def test_another_members_stuck_mail_is_listed_and_a_fifo_or_link_at_its_note_never_blocks_or_leads_health(self):
        """Another member's branch, made by hand, holds a message for b dated two days ago, its note a FIFO, then a symlink to a file outside the mailbox: tc health --json returns within HEALTH_CEILING_SECONDS, lists the message with that member, b, its path and no note, and prints nothing of the link's target.

        The case D36 (4) exists for: a far box that stays broken is shown
        to every member, not only the sender. The note sits in the other
        member's own branch, which that member controls. Must reject a
        stuck_outbox that lists only this user's own branch, a note opened
        without O_NONBLOCK (a FIFO there hangs every other member's tc
        health), and a note followed through a link.

        @interacts  per case: makes outbox/<member>/to-b/ and one message
                    by hand, sets its times, makes a FIFO or a link (and
                    its target in the temp folder) at its note's name; one
                    tc health --json.
        @deps       _root.TcRoot.tc; OTHER_MEMBER from test_ssh_route.py;
                    json, os, subprocess, time.
        @complexity O(1): two cases.
        @alloc      one TcRoot per case.
        """
        for planted in ("a FIFO", "a symlink"):
            with self.subTest(note=planted), _root.TcRoot() as root:
                queued = root.path / "outbox" / OTHER_MEMBER / "to-b" / OTHERS_MESSAGE.format(member=OTHER_MEMBER)
                queued.parent.mkdir(parents=True)
                queued.write_text(f"# #3 from {OTHER_MEMBER} to b\n\nwaiting\n")
                stamp = time.time() - TWO_DAYS_SECONDS
                os.utime(queued, (stamp, stamp))
                note = queued.with_name(queued.name + NOTE_SUFFIX)
                if planted == "a FIFO":
                    os.mkfifo(note)
                else:
                    outside = root.base / "outside-note"
                    outside.write_text(OUTSIDE_NOTE_TEXT + "\n")
                    note.symlink_to(outside)
                try:
                    code, out, err = root.tc("health", "--json", timeout=HEALTH_CEILING_SECONDS)
                except subprocess.TimeoutExpired:
                    self.fail(f"tc health hung on {planted} at another member's note")
                self.assertEqual(code, 0, err)
                stuck = json.loads(out)["stuck_outbox"]
                self.assertEqual([(entry["member"], entry["to"], entry["path"], entry["note"]) for entry in stuck],
                                 [(OTHER_MEMBER, "b", str(queued), None)],
                                 "health did not list the other member's stuck mail, or read its planted note")
                self.assertLessEqual(abs(stuck[0]["age_s"] - TWO_DAYS_SECONDS), AGE_SLACK_SECONDS, stuck)
                self.assertNotIn(OUTSIDE_NOTE_TEXT, out, "health read the file a planted link at the note leads to")


# R2 (Claude Opus 5.5, unreviewed): a wrong TC_ROOT is the project's loudest hazard.
class HealthRootTest(unittest.TestCase):
    """`tc health` names the mailbox it read and where that came from: TC_ROOT, or the default, the folder tc is in.

    @interacts  runs tc through tests/_root.py with TC_ROOT set, and a
                copy of tc put in the root with TC_ROOT unset.
    @deps       _root.TcRoot; json, shutil, subprocess, sys.
    @complexity O(1): four health runs.
    @alloc      one TcRoot.
    """

    def test_health_names_the_mailbox_it_read_and_where_it_came_from(self):
        """With TC_ROOT set, health's first line is `mailbox    <TC_ROOT>, from TC_ROOT` and --json gives root and root_from "TC_ROOT"; with it unset, a copy of tc in the root says the root, `TC_ROOT unset, so the folder tc is in`, and "default".

        Must reject a health that never says which mailbox it read (a
        session with the wrong TC_ROOT reads another mailbox's listeners
        and mail as its own), and a source that says TC_ROOT whatever the
        environment holds. The copy runs from the root, so its default is
        the root and never this checkout's own mailbox.

        @interacts  two tc health runs (words, --json) under the root's
                    TC_ROOT; copies tc into the root and runs the copy
                    twice with TC_ROOT unset.
        @deps       _root.TcRoot.tc, _root.DEFAULT_TC_TIMEOUT_SECONDS;
                    json, shutil, subprocess, sys.
        @complexity O(1).
        @alloc      one TcRoot and the copy of tc in it.
        """
        with _root.TcRoot() as root:
            runs = {ROOT_FROM_ENV: (root.tc("health"), root.tc("health", "--json"))}
            copy = root.path / TC.name
            shutil.copy2(TC, copy)
            unset = {key: value for key, value in root.env.items() if key != "TC_ROOT"}

            def bare(*args):
                done = subprocess.run([sys.executable, str(copy), *args], env=unset, capture_output=True, text=True,
                                      stdin=subprocess.DEVNULL, timeout=_root.DEFAULT_TC_TIMEOUT_SECONDS)
                return done.returncode, done.stdout, done.stderr

            runs[ROOT_FROM_DEFAULT] = (bare("health"), bare("health", "--json"))
            want = {ROOT_FROM_ENV: (str(root.path), ROOT_FROM_ENV_WORDS),
                    ROOT_FROM_DEFAULT: (str(root.path.resolve()), ROOT_FROM_DEFAULT_WORDS)}
        for source, ((code, text, err), (jcode, out, jerr)) in runs.items():
            path, words = want[source]
            with self.subTest(source=source, check="exit codes"):
                self.assertEqual((code, jcode), (0, 0), err + jerr)
            with self.subTest(source=source, check="first line"):
                self.assertEqual(text.splitlines()[:1], [ROOT_LINE.format(root=path, words=words)], text)
            snap = json.loads(out) if jcode == 0 else {}
            with self.subTest(source=source, check=ROOT_KEY):
                self.assertEqual(snap.get(ROOT_KEY), path)
            with self.subTest(source=source, check=ROOT_FROM_KEY):
                self.assertEqual(snap.get(ROOT_FROM_KEY), source)


if __name__ == "__main__":
    unittest.main()
