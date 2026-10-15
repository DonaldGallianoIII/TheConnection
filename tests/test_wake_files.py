"""
Tests for the wake files of P3 fix round 1b (D35 (1), D36 (2); the audit's
HIGH-2, audits/2026-10-15-1409-full): each name's wait and watch locks
live in its owner's own inbox at 0600, a link or FIFO planted at a lock's
name is moved aside and never followed, a listener started before the
change still counts on a private mailbox until it re-arms and never on a
shared one, only a name's owner listens for it on a shared mailbox, a
private mailbox keeps its wait exactly, and tc wait and tc watch close
their lock file on every way out.

Model:  Claude Opus 5.5 (the P3 fixer, round 1b), 2026-10-15
Status: unreviewed

One Linux user plays every part. Where a second owner is needed (D36's
refusal of anyone but a name's owner), tc runs in process and os.lstat
and os.fstat report the card and the inbox as another user's
(test_shared.owner_patched_lstat and owner_patched_fstat), as the SHARED
suites do; the second-user walk is qa/human/route-shared.md.

@interacts  runs ../tc through tests/_root.py under a throwaway TC_ROOT
            (init, joins, sends, waits, watches, health); makes inboxes,
            links, FIFOs and lock files by hand; starts children of its
            own (python3 -c HOLD_SCRIPT, which opens a lock file and holds
            its flock until the harness kills it by its pid) and reads
            /proc/locks to prove a listener; loads tc as a module (TC_ROOT
            set for the load and put back) and runs cmd_wait and cmd_watch
            in process with os.lstat and os.fstat patched, or with
            resource.setrlimit made a no-op (so a wait never caps this
            process), tc's gpu_stats, unread or machine_stats replaced,
            stdout and stderr captured, and warnings recorded; reads
            /proc/self/fd. Writes nothing outside the root's temp folder.
@deps       python3 stdlib (argparse, contextlib, fcntl, gc, io, json, os,
            pathlib, pwd, stat, subprocess, sys, time, unittest,
            unittest.mock, warnings); tests/_root.py; UmaskTestCase,
            load_tc, owner_patched_lstat, owner_patched_fstat,
            primary_group and tree from test_shared.py; ../tc.
@complexity O(1) per test: a handful of tc runs and at most two children
            per root, each wait or watch run under a second or two; the
            private pin test waits out one of tc's polls (POLL_SECONDS).
@alloc      one TcRoot per test or case, removed when its context exits,
            with every child it started.
"""

import argparse
import contextlib
import fcntl
import gc
import io
import json
import os
import pathlib
import pwd
import stat
import subprocess
import sys
import time
import unittest
import warnings
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
# Run as `python3 -m unittest tests.test_wake_files` from the repo root,
# tests/ is not on sys.path; under discover it is. Add it once so both work.
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import _root  # noqa: E402  (needs the path line above)
from test_shared import (UmaskTestCase, load_tc, owner_patched_fstat, owner_patched_lstat,  # noqa: E402
                         primary_group, tree)

# The names: the member who owns an inbox, a name nobody joined, and a
# name for a private mailbox's new listener. Made up.
OWNER = "ann"
GHOST = "ghost"
NEW_NAME = "newcomer"
# The two kinds of listener, and their locks' names in the owner's inbox
# (tc's WAKE_LOCK_NAME), written here rather than read from tc.
KINDS = ("wait", "watch")
LOCK_NAME = ".{kind}.lock"
# Where the locks lived before round 1b (tc's OLD_WAKE_LOCK_NAME), the
# switch-over's old place.
OLD_LOCK_NAME = ".{kind}-{name}.lock"
# A wake lock's mode: its owner's alone.
WAKE_LOCK_MODE = 0o600
# Where tc moves an entry it finds at a lock's name: the first aside name.
FIRST_ASIDE = "{lock}.planted-1"
# Exit codes (contracts.md): refused with words, a wait's timeout, another
# listener holds the lock, a watch's alert.
EXIT_REFUSED = 1
EXIT_TIMEOUT = 2
EXIT_ALREADY = 3
EXIT_ALERT = 5
# tc's words for a second listener, as before round 1b, by kind.
ALREADY_WORDS = {"wait": "ALREADY LISTENING: another `tc wait {name}` is running. Not starting a second.\n",
                 "watch": "ALREADY WATCHING: another `tc watch {name}` is running. Not starting a second.\n"}
# C4's words for D36 (2), exit 1 (contracts.md, "Only a name's owner
# listens for it").
ONLY_OWNER_WORDS = "tc {kind}: {name}'s inbox belongs to {owner}; only {owner} listens for it\n"
NOBODY_JOINED_WORDS = ("tc {kind}: nobody has joined as {name} on this shared mailbox; its owner runs tc join "
                       "{name} first\n")
# What tc says when it moved a planted entry aside, in parts: what it was,
# then where it went.
MOVED_WORDS = "tc {kind}: {path} was {what} owned by {owner}, not this user's own {kind} lock; moved it aside to {aside}"
# Thresholds no real machine reaches, so a watch can only heartbeat, never
# alert; and one that always alerts on memory, for the exit 5 case.
QUIET = ["--load-ratio", "100000", "--mem-min-pct", "0", "--gpu-max-c", "100000"]
QUIET_ARGS = {"load_ratio": 100000.0, "mem_min_pct": 0.0, "gpu_max_c": 100000.0}
ALERT_MEM_MIN_PCT = 101.0
# A wait that times out at once, and a watch that heartbeats at once,
# with a poll gap the run never reaches.
AT_ONCE = "0"
WATCH_POLL = "1"
# A child that opens the lock file named by its first argument (making it
# when missing, as a listener before round 1b did), holds its flock
# exclusive, says so on stdout, and sleeps the seconds of its second
# argument; the harness kills it by its pid at the latest.
HOLD_SCRIPT = """import fcntl, sys, time
f = open(sys.argv[1], "a")
fcntl.flock(f, fcntl.LOCK_EX)
print("held", flush=True)
time.sleep(float(sys.argv[2]))
"""
HELD_LINE = "held\n"
# Far past any test here; the child is killed long before.
HOLD_SECONDS = 60
# How long a planted FIFO may hold a wait or watch up: never, so the run's
# own timeout is the ceiling.
FIFO_CEILING_SECONDS = 5
# A real background wait's length, killed by the harness once the test
# has what it needs; a second wait's, which exits 3 at once.
LISTEN_SECONDS = "30"
SECOND_WAIT_SECONDS = "1"
# tc's poll gap (POLL_SECONDS), plus a margin for a loaded machine: how
# long a waiting tc wait may take to see mail that landed.
WAKE_CEILING_SECONDS = 5 + 5
# How long a child gets to take its lock, and the gap between looks.
LOCK_CEILING_SECONDS = _root.LOCK_CEILING_SECONDS
LOCK_POLL_SECONDS = _root.LOCK_POLL_SECONDS
# What a link planted at a lock's name leads to, outside TC_ROOT.
TARGET_TEXT = "a file outside the mailbox; tc must not touch it\n"


def login(uid):
    """The login of user number `uid`, or the number as text when the machine has no such user (tc's user_name).

    @interacts  reads the user database.
    @deps       pwd.
    @complexity O(1).
    @alloc      one short string, returned.
    """
    try:
        return pwd.getpwuid(uid).pw_name
    except KeyError:
        return str(uid)


def run_in_process(call):
    """Run `call` with stdout and stderr captured: (code, out, err). A SystemExit gives its code, 0 for a return.

    @interacts  runs `call`; captures stdout and stderr.
    @deps       contextlib, io.
    @complexity O(1), plus the call.
    @alloc      the captured text, returned.
    """
    out, err = io.StringIO(), io.StringIO()
    code = 0
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            call()
        except SystemExit as stop:
            code = 0 if stop.code is None else stop.code
    return code, out.getvalue(), err.getvalue()


def hold(root, path):
    """Start HOLD_SCRIPT on `path` and return its Popen once it holds the flock (its HELD_LINE read).

    @interacts  starts one child through the harness (killed by its pid in
                teardown); reads one line of its stdout.
    @deps       _root.TcRoot.start; sys; HOLD_SCRIPT, HOLD_SECONDS, HELD_LINE.
    @complexity O(1).
    @alloc      one Popen, registered with the root.
    """
    proc = root.start(argv=[sys.executable, "-c", HOLD_SCRIPT, str(path), str(HOLD_SECONDS)])
    line = proc.stdout.readline()
    if line != HELD_LINE:
        raise AssertionError(f"the holder of {path} never said it held it: {line!r}")
    return proc


def proven(path, proc):
    """True once /proc/locks shows `proc` holding an flock on `path`, within LOCK_CEILING_SECONDS; False if it exits or the time runs out first.

    @interacts  reads /proc/locks (the harness's flock_holders).
    @deps       _root.flock_holders; time.
    @complexity at most LOCK_CEILING_SECONDS / LOCK_POLL_SECONDS reads.
    @alloc      none past each read.
    """
    deadline = time.monotonic() + LOCK_CEILING_SECONDS
    while time.monotonic() < deadline:
        if proc.pid in _root.flock_holders(path):
            return True
        if proc.poll() is not None:
            return False
        time.sleep(LOCK_POLL_SECONDS)
    return False


def health(root):
    """`tc health --json` under `root`, parsed.

    @interacts  one tc run.
    @deps       _root.TcRoot.tc; json.
    @complexity O(1).
    @alloc      one dict, returned.
    """
    code, out, err = root.tc("health", "--json")
    if code != 0:
        raise AssertionError(f"tc health --json exited {code}: {err}")
    return json.loads(out)


def listen(root, kind, name, *extra):
    """Run `tc wait <name>` or `tc watch <name>` (`kind`) under `root` so that it ends at once: (exit, stdout, stderr).

    @interacts  one tc run.
    @deps       _root.TcRoot.tc; AT_ONCE, WATCH_POLL, QUIET.
    @complexity O(1).
    @alloc      the run's output, returned.
    """
    if kind == "wait":
        return root.tc("wait", name, "--timeout", AT_ONCE, *extra)
    return root.tc("watch", name, "--heartbeat", AT_ONCE, "--poll", WATCH_POLL, *QUIET, *extra)


def lock_fds(path):
    """How many of this process's descriptors are open on the file at `path` now (/proc/self/fd).

    @interacts  stats `path` and every entry of /proc/self/fd.
    @deps       os.
    @complexity O(d) over d open descriptors (tens).
    @alloc      none past the listing.
    """
    want = os.stat(path)
    count = 0
    for name in os.listdir("/proc/self/fd"):
        try:
            st = os.stat(f"/proc/self/fd/{name}")
        except OSError:
            continue
        count += (st.st_dev, st.st_ino) == (want.st_dev, want.st_ino)
    return count


def wait_args(name, timeout):
    """The Namespace cmd_wait reads, for an in-process run.

    @interacts  none.
    @deps       argparse.
    @complexity O(1).
    @alloc      one Namespace, returned.
    """
    return argparse.Namespace(name=name, timeout=timeout, keepalive=False)


def watch_args(name, heartbeat, mem_min_pct=QUIET_ARGS["mem_min_pct"]):
    """The Namespace cmd_watch reads, for an in-process run: no names tracked, thresholds no machine reaches but `mem_min_pct`.

    @interacts  none.
    @deps       argparse; QUIET_ARGS, WATCH_POLL.
    @complexity O(1).
    @alloc      one Namespace, returned.
    """
    return argparse.Namespace(name=name, heartbeat=heartbeat, poll=float(WATCH_POLL), names="",
                              load_ratio=QUIET_ARGS["load_ratio"], mem_min_pct=mem_min_pct,
                              gpu_max_c=QUIET_ARGS["gpu_max_c"])


class WakeLockPlaceTest(UmaskTestCase):
    """D35 (1): each lock in its owner's own inbox at 0600, anything else at its name moved aside, and the switch-over's two halves.

    @interacts  see the module block.
    @deps       _root.TcRoot, UmaskTestCase, primary_group, listen, hold,
                proven, health.
    @complexity O(1) per test.
    @alloc      one TcRoot per case.
    """

    def test_the_wait_and_watch_locks_are_their_owners_alone_in_its_inbox(self):
        """Private and shared (ann joined): tc wait ann and tc watch ann each leave mail/to-ann/.<kind>.lock, a regular file of this user's at 0600, and nothing at the old place in mail/.

        Must reject a lock left in mail/ (the group could open it there
        and hold its flock), and one made at any mode the group may read.

        @interacts  per mailbox: an init and a join when shared; one wait
                    and one watch.
        @deps       listen, primary_group; _root.TcRoot.tc; os, stat.
        @complexity O(1): four tc runs per mailbox.
        @alloc      one TcRoot per mailbox.
        """
        _, group, _ = primary_group()
        for shared in (False, True):
            with self.subTest(shared=shared), _root.TcRoot() as root:
                if shared:
                    self.assertEqual(root.tc("init", "--shared", "--group", group)[0], 0)
                    self.assertEqual(root.tc("join", OWNER, env={"CLAUDECODE": "1"})[0], 0)
                runs = {kind: listen(root, kind, OWNER) for kind in KINDS}
                mail = root.path / "mail"
                seen = {}
                for kind in KINDS:
                    st = os.lstat(mail / f"to-{OWNER}" / LOCK_NAME.format(kind=kind))
                    seen[kind] = (stat.S_ISREG(st.st_mode), stat.S_IMODE(st.st_mode), st.st_uid)
                old = [kind for kind in KINDS if os.path.lexists(mail / OLD_LOCK_NAME.format(kind=kind, name=OWNER))]
            self.assertEqual(runs["wait"][0], EXIT_TIMEOUT, runs["wait"])
            self.assertEqual(runs["watch"][0], 0, runs["watch"])
            for kind in KINDS:
                self.assertEqual(seen[kind], (True, WAKE_LOCK_MODE, os.geteuid()),
                                 f"the {kind} lock is not this user's own regular file at 0600")
            self.assertEqual(old, [], "a lock was made at the old place in mail/")

    def test_a_link_or_fifo_at_a_locks_name_is_moved_aside_never_followed_or_waited_on(self):
        """A symlink to a file outside the mailbox, or a FIFO, at mail/to-x/.wait.lock or .watch.lock: tc wait x and tc watch x run as ever (exit 2, exit 0) within FIFO_CEILING_SECONDS, say what they moved and where, leave it at the first aside name unchanged (the link's target too), and hold a new 0600 lock of their own.

        P3 fix round 1b: these cases were in test_shared.py's D17 and D19
        tests, refused with exit 1 while the locks lived in mail/. In the
        owner's inbox, the owner's tc moves them aside (D35 (1)). Must
        reject an open that follows the link (the target changes or the
        lock is taken through it), one without O_NONBLOCK (the FIFO
        blocks the run past its ceiling), and a run that refuses instead
        of moving it.

        @interacts  per case: an inbox, a link and its target, or a FIFO,
                    made by hand; one wait or watch.
        @deps       listen; _root.TcRoot.tc; os, stat, subprocess.
        @complexity O(1) per case, four cases.
        @alloc      one TcRoot per case.
        """
        for kind in KINDS:
            for planted in ("a symlink", "a FIFO"):
                with self.subTest(kind=kind, planted=planted), _root.TcRoot() as root:
                    box = root.path / "mail" / "to-x"
                    box.mkdir(parents=True)
                    lock = box / LOCK_NAME.format(kind=kind)
                    target = root.base / "target"
                    target.write_text(TARGET_TEXT)
                    if planted == "a symlink":
                        lock.symlink_to(target)
                    else:
                        os.mkfifo(lock)
                    try:
                        code, out, err = listen(root, kind, "x")
                    except subprocess.TimeoutExpired:
                        self.fail(f"tc {kind} blocked on {planted} at its lock's name")
                    aside = box / FIRST_ASIDE.format(lock=lock.name)
                    moved = os.lstat(aside).st_mode
                    st = os.lstat(lock)
                    after = target.read_text()
                self.assertEqual(code, EXIT_TIMEOUT if kind == "wait" else 0, err)
                self.assertIn(MOVED_WORDS.format(kind=kind, path=lock, what=planted, owner=login(os.geteuid()),
                                                 aside=aside), err)
                self.assertTrue(stat.S_ISLNK(moved) if planted == "a symlink" else stat.S_ISFIFO(moved),
                                f"{planted} did not move to {aside} as itself")
                self.assertEqual((stat.S_ISREG(st.st_mode), stat.S_IMODE(st.st_mode)), (True, WAKE_LOCK_MODE))
                self.assertEqual(after, TARGET_TEXT, "the link's target changed")

    def test_on_a_private_mailbox_a_listener_from_before_still_counts_until_it_rearms(self):
        """The switch-over, private: with mail/.wait-x.lock and .watch-x.lock held by listeners from before round 1b, tc health names their pids, a new tc wait x and tc watch x exit 3 with today's words and make no inbox; once they go, a new wait runs and health names none; a link or a FIFO at the old place stops nothing.

        Must reject a new listener that ignores the old place (two
        listeners for one name while the dev branch's sessions re-arm),
        and a listeners() that drops the old holder (health and the board
        would say nobody listens while one does). The second half is in
        test_on_a_shared_mailbox_the_old_place_is_never_read.

        @interacts  two children holding the old locks, killed by their
                    own pids; health, waits and watches; one FIFO and one
                    link made by hand.
        @deps       hold, health, listen; _root.TcRoot.tc; os.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            mail = root.path / "mail"
            mail.mkdir()
            holders = {kind: hold(root, mail / OLD_LOCK_NAME.format(kind=kind, name="x")) for kind in KINDS}
            seen = health(root)
            stopped = {kind: listen(root, kind, "x") for kind in KINDS}
            made = (mail / "to-x").exists()
            for proc in holders.values():
                proc.kill()
                proc.wait(timeout=_root.REAP_CEILING_SECONDS)
            later = listen(root, "wait", "x")
            after = health(root)
            os.mkfifo(mail / OLD_LOCK_NAME.format(kind="wait", name="y"))
            (mail / OLD_LOCK_NAME.format(kind="wait", name="z")).symlink_to(mail / OLD_LOCK_NAME.format(kind="wait",
                                                                                                        name="x"))
            fifo, link = listen(root, "wait", "y"), listen(root, "wait", "z")
        self.assertEqual((seen["listeners"].get("x"), seen["watchers"].get("x")),
                         (holders["wait"].pid, holders["watch"].pid), "health lost a listener from before round 1b")
        for kind in KINDS:
            self.assertEqual(stopped[kind], (EXIT_ALREADY, ALREADY_WORDS[kind].format(name="x"), ""))
        self.assertFalse(made, "a listener stopped by the old place made an inbox")
        self.assertEqual(later[0], EXIT_TIMEOUT, later)
        self.assertIsNone(after["listeners"].get("x"), after["listeners"])
        self.assertEqual((fifo[0], link[0]), (EXIT_TIMEOUT, EXIT_TIMEOUT), (fifo, link))

    def test_on_a_shared_mailbox_the_old_place_is_never_read(self):
        """The switch-over, shared: with mail/.wait-ann.lock held by another process, tc health never names it for ann, and ann's own tc wait is not stopped: it holds mail/to-ann/.wait.lock, and health names its pid.

        Must reject a shared mailbox that reads the old place: any member
        may make and hold mail/.wait-ann.lock there, the hole D35 closes.

        @interacts  an init and a join; one child holding the old lock;
                    one background tc wait, proven in /proc/locks; two
                    health runs.
        @deps       hold, health, proven, primary_group;
                    _root.TcRoot.tc, start.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        _, group, _ = primary_group()
        with _root.TcRoot() as root:
            self.assertEqual(root.tc("init", "--shared", "--group", group)[0], 0)
            self.assertEqual(root.tc("join", OWNER, env={"CLAUDECODE": "1"})[0], 0)
            mail = root.path / "mail"
            holder = hold(root, mail / OLD_LOCK_NAME.format(kind="wait", name=OWNER))
            before = health(root)
            waiting = root.start("wait", OWNER, "--timeout", LISTEN_SECONDS)
            held = proven(mail / f"to-{OWNER}" / LOCK_NAME.format(kind="wait"), waiting)
            during = health(root)
        self.assertNotEqual(before["listeners"].get(OWNER), holder.pid, "a shared mailbox read the old place")
        self.assertTrue(held, f"ann's own tc wait (pid {waiting.pid}) never held its lock in her inbox")
        self.assertEqual(during["listeners"].get(OWNER), waiting.pid)


class OnlyTheOwnerListensTest(UmaskTestCase):
    """D36 (2): on a shared mailbox only the owner of a name's card listens for it; a private mailbox keeps its wait exactly.

    @interacts  see the module block.
    @deps       _root.TcRoot, UmaskTestCase, primary_group, load_tc,
                owner_patched_lstat, owner_patched_fstat, tree,
                run_in_process.
    @complexity O(1) per test.
    @alloc      one TcRoot per test.
    """

    def test_a_wait_or_watch_by_anyone_but_the_names_owner_or_on_a_name_nobody_joined_is_refused_and_makes_nothing(self):
        """Shared: ann's card, inbox and read/ reported as another user's, tc wait ann and tc watch ann (in process) exit 1 with C4's words naming that user; tc wait ghost and tc watch ghost (nobody joined) exit 1 with C4's other words; the root is unchanged throughout.

        Must reject a wait with no owner check (D36 (2)): with the inbox
        and its read/ reported as the card owner's too, D20's check
        passes, nothing else stops it, and it would make its lock in
        another member's inbox and hold it. Must reject a name nobody
        joined polled as no mail (the old way), and anything made before a
        refusal.

        @interacts  an init and a join; loads tc and runs cmd_wait and
                    cmd_watch in process with os.lstat and os.fstat
                    patched and resource.setrlimit made a no-op; two tc
                    runs; lstats the whole root before and after.
        @deps       load_tc, owner_patched_lstat, owner_patched_fstat,
                    primary_group, tree, run_in_process, login, wait_args,
                    watch_args; _root.TcRoot.tc; unittest.mock.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        _, group, _ = primary_group()
        with _root.TcRoot() as root:
            self.assertEqual(root.tc("init", "--shared", "--group", group)[0], 0)
            self.assertEqual(root.tc("join", OWNER, env={"CLAUDECODE": "1"})[0], 0)
            card, box = root.path / "cards" / f"{OWNER}.json", root.path / "mail" / f"to-{OWNER}"
            other = login(os.lstat(card).st_uid + 1)
            before = tree(root.path, under=None)
            tc = load_tc(root)
            ran = {}
            calls = {"wait": lambda: tc.cmd_wait(wait_args(OWNER, 0.0)),
                     "watch": lambda: tc.cmd_watch(watch_args(OWNER, 0.0))}
            for kind in KINDS:
                with mock.patch.object(os, "lstat", owner_patched_lstat(card, box, box / "read")), \
                        mock.patch.object(os, "fstat", owner_patched_fstat(box, box / "read")), \
                        mock.patch.object(tc.resource, "setrlimit", lambda *args: None), \
                        mock.patch.object(tc, "gpu_stats", lambda: None):
                    ran[kind] = run_in_process(calls[kind])
            nobody = {kind: listen(root, kind, GHOST) for kind in KINDS}
            after = tree(root.path, under=None)
        for kind in KINDS:
            with self.subTest(kind=kind):
                self.assertEqual(ran[kind], (EXIT_REFUSED, "", ONLY_OWNER_WORDS.format(kind=kind, name=OWNER,
                                                                                         owner=other)))
                self.assertEqual(nobody[kind], (EXIT_REFUSED, "", NOBODY_JOINED_WORDS.format(kind=kind, name=GHOST)))
        self.assertEqual(after, before, "a refused wait or watch made or changed something")

    def test_a_private_mailbox_keeps_its_wait_exactly(self):
        """a2's pin for every agent on this machine: on a private mailbox, tc wait <new name> makes the inbox and its lock, tc health names its pid, a second tc wait exits 3, mail makes the first exit 0, and a timeout exits 2.

        Must reject a private wait refused for want of a card (D36 (2) is
        shared only), one that makes no inbox, one health does not name,
        a second wait that starts, and a wait that misses its mail.

        @interacts  one background tc wait, proven in /proc/locks; health;
                    a second wait; one send; one read; one more wait.
        @deps       proven, health; _root.TcRoot.tc, start; os, stat.
        @complexity O(1), plus up to one tc poll for the mail.
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            box = root.path / "mail" / f"to-{NEW_NAME}"
            lock = box / LOCK_NAME.format(kind="wait")
            first = root.start("wait", NEW_NAME, "--timeout", LISTEN_SECONDS)
            held = proven(lock, first)
            made = (box.is_dir(), (box / "read").is_dir(), stat.S_IMODE(os.lstat(lock).st_mode) if held else None)
            named = health(root)["listeners"].get(NEW_NAME)
            second = root.tc("wait", NEW_NAME, "--timeout", SECOND_WAIT_SECONDS)
            sent = root.tc("send", "--from", "a", "--to", NEW_NAME, "hello")
            try:
                out, err = first.communicate(timeout=WAKE_CEILING_SECONDS)
            except subprocess.TimeoutExpired:
                self.fail(f"the first wait did not see its mail in {WAKE_CEILING_SECONDS} s")
            woke = first.returncode
            read = root.tc("read", NEW_NAME)
            timed_out = root.tc("wait", NEW_NAME, "--timeout", SECOND_WAIT_SECONDS)
        self.assertTrue(held, f"tc wait {NEW_NAME} (pid {first.pid}) never held {lock}")
        self.assertEqual(made, (True, True, WAKE_LOCK_MODE))
        self.assertEqual(named, first.pid, "tc health did not name the listener's pid")
        self.assertEqual(second, (EXIT_ALREADY, ALREADY_WORDS["wait"].format(name=NEW_NAME), ""))
        self.assertEqual(sent[0], 0, sent)
        self.assertEqual((woke, out), (0, f"MAIL: 1 unread for {NEW_NAME}. Run: tc read {NEW_NAME}\n"), err)
        self.assertEqual(read[0], 0, read)
        self.assertEqual(timed_out[0], EXIT_TIMEOUT, timed_out)
        self.assertTrue(timed_out[1].startswith(f"TIMEOUT: no mail for {NEW_NAME}"), timed_out)


class LockFileClosedTest(UmaskTestCase):
    """Item 8 of round 1b, from round 1a's report: tc wait and tc watch close their lock file on every way out.

    @interacts  see the module block.
    @deps       _root.TcRoot, UmaskTestCase, load_tc, run_in_process,
                lock_fds.
    @complexity O(1) per case.
    @alloc      one TcRoot per case.
    """

    def test_wait_and_watch_close_their_lock_file_on_every_way_out(self):
        """In process, private: tc wait exits 0, 2, 3, 1 (a refusal in a poll) and by an exception, and tc watch exits 0, 3, 5 and by an exception; after each, no descriptor of this process is open on the lock, and no ResourceWarning was raised.

        Must reject a lock file left for the garbage collector or the
        process's exit (round 1a's class proof had to ignore the
        ResourceWarning it raised).

        @interacts  per case: a send or a held lock as setup; loads tc and
                    runs cmd_wait or cmd_watch in process with
                    resource.setrlimit made a no-op, tc's gpu_stats
                    replaced, and for some cases tc's unread or
                    machine_stats replaced; records warnings; collects
                    garbage; reads /proc/self/fd.
        @deps       load_tc, run_in_process, lock_fds, wait_args,
                    watch_args; _root.TcRoot.tc; fcntl, gc, unittest.mock,
                    warnings.
        @complexity O(1) per case, nine cases.
        @alloc      one TcRoot and one module per case.
        """
        def broken(*args, **kwargs):
            raise RuntimeError("a fault inside the listener")

        cases = [  # kind, label, what it expects, setup, what to replace in tc, the call's Namespace
            ("wait", "exit 0", 0, "send", None, wait_args("x", 1.0)),
            ("wait", "exit 2", EXIT_TIMEOUT, None, None, wait_args("x", 0.0)),
            ("wait", "exit 3", EXIT_ALREADY, "hold", None, wait_args("x", 0.0)),
            ("wait", "a refusal", EXIT_REFUSED, None, ("unread", lambda *a, **k: sys.exit(EXIT_REFUSED)),
             wait_args("x", 1.0)),
            ("wait", "an exception", RuntimeError, None, ("unread", broken), wait_args("x", 1.0)),
            ("watch", "exit 0", 0, None, None, watch_args("x", 0.0)),
            ("watch", "exit 3", EXIT_ALREADY, "hold", None, watch_args("x", 0.0)),
            ("watch", "exit 5", EXIT_ALERT, None, None, watch_args("x", 0.0, ALERT_MEM_MIN_PCT)),
            ("watch", "an exception", RuntimeError, None, ("machine_stats", broken), watch_args("x", 0.0)),
        ]
        for kind, label, expected, setup, replaced, args in cases:
            with self.subTest(kind=kind, way=label), _root.TcRoot() as root:
                lock = root.path / "mail" / "to-x" / LOCK_NAME.format(kind=kind)
                self.assertEqual(listen(root, kind, "x")[0], EXIT_TIMEOUT if kind == "wait" else 0)
                if setup == "send":
                    self.assertEqual(root.tc("send", "--from", "a", "--to", "x", "hi")[0], 0)
                tc = load_tc(root)
                with contextlib.ExitStack() as stack:
                    if setup == "hold":
                        held = stack.enter_context(open(lock, "rb"))
                        fcntl.flock(held, fcntl.LOCK_EX)
                    stack.enter_context(mock.patch.object(tc.resource, "setrlimit", lambda *a: None))
                    stack.enter_context(mock.patch.object(tc, "gpu_stats", lambda: None))
                    if replaced is not None:
                        stack.enter_context(mock.patch.object(tc, replaced[0], replaced[1]))
                    seen = stack.enter_context(warnings.catch_warnings(record=True))
                    warnings.simplefilter("always", ResourceWarning)
                    command = tc.cmd_wait if kind == "wait" else tc.cmd_watch
                    try:
                        code = run_in_process(lambda: command(args))[0]
                    except RuntimeError:
                        code = RuntimeError
                    gc.collect()
                    leaks = [str(w.message) for w in seen if issubclass(w.category, ResourceWarning)]
                    open_on_lock = lock_fds(lock) - (1 if setup == "hold" else 0)
                self.assertEqual(code, expected)
                self.assertEqual(open_on_lock, 0, f"tc {kind} left its lock open after {label}")
                self.assertEqual(leaks, [], f"tc {kind} left a file for the garbage collector after {label}")


if __name__ == "__main__":
    unittest.main()
