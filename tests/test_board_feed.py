"""
Tests for board/serve.py's feed (C5): nodes and their states, listener
pids, wires, links, the status line, and the roles and levels of D7's
shapes. The feed never opens a message body: the main test makes every
body mode 000 and the feed still works.

Model:  Claude Opus 5.5 (the BOARD lane agent), 2026-10-14
Status: unreviewed

Cards are written by hand in C1's shape: some are codex and ssh cards (a
codex join needs a Codex thread id in its environment, and an ssh card
comes from `tc card`), and writing every card one way keeps the tests
alike. tests/board-browser-check.mjs is the one that writes its cards
with `tc join`. The main test sends its mail with real `tc send`, between
names with no card, so the file names the feed parses are tc's own. No
test sends to a name with a codex or ssh card: tc's router rings `codex`
for the one and runs `ssh` for the other (SSH fix round 1, Claude Opus
5.5, unreviewed: the ssh route is built, the audit's LOW-29). The
shape tests write message files by hand
in tc's layout (`NNNNNN-from-<sender>.md` under `to-<name>/read/`, a .tmp
renamed, mail/.seq raised), and the feed reads only their names.

@interacts  runs ../tc through tests/_root.py under a throwaway TC_ROOT;
            starts two proven `tc wait` listeners and relies on the harness
            to kill them by their own pids. Loads board/serve.py as a
            module; each Board loads tc with TC_ROOT set to the test's root.
            Writes cards, status lines and message files in that root only.
@deps       python3 stdlib (contextlib, fcntl, importlib, io, itertools,
            json, marshal, os, pathlib, random, shlex, shutil, stat, sys,
            threading, time, unittest, unittest.mock); tests/_root.py;
            board/serve.py; ../tc.
@complexity O(1) per test: at most 52 message files, 9 names, two
            listeners, and a few feed() calls, each O(n + m + e) in serve.py
            plus Board.snapshot's parts of tc's health (milliseconds, no
            GPU query). The inference property test runs PROPERTY_CASES
            seeded cases through serve.hierarchy with no disk. The D15 state test swaps the snapshot for a
            stand-in, so it starts no listener and no child. The GPU test
            puts a fake nvidia-smi on PATH and runs it once, through
            tc.machine_stats. The hostile mailbox tests make a FIFO, a
            looping link, symlinks to files and folders outside, one
            message in two folders, a card named with an escape sequence,
            and two copies of tc (one with a planted bytecode cache) in
            their own root's temp folder only, and swap tc's
            mailbox_summary for a stand-in that fails. The wake tests
            (D24, D28) close two folders to the board (mode 000, opened
            again before the root goes), put hand-made files in read/ and
            move one message out of the board's sight, each in its own
            root. F1 (Claude Opus 5.5, unreviewed): a test that kills a
            listener first waits for its wait exit record, and the D28
            test lets b's wait end on its mail (reading /proc/locks until
            it lets go), since a killed wait's record says listening and
            reads down, after a restart and past the window too (C5).
@alloc      one TcRoot per test, removed when its context exits; the feeds
            are plain dicts dropped at the end of each test.
"""

import contextlib
import fcntl
import importlib.util
import io
import itertools
import json
import marshal
import os
import pathlib
import random
import shlex
import shutil
import stat
import sys
import threading
import time
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
# Run as `python3 -m unittest tests.test_board_feed` from the repo root,
# tests/ is not on sys.path; under discover it is. Add it once so both work.
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import _root  # noqa: E402  (needs the path line above)

SERVE_PATH = HERE.parent / "board" / "serve.py"

# Long enough that a listener never times out on its own during a test; the
# harness kills it when its context exits.
LISTENER_TIMEOUT_SECONDS = 30
# C5's numbers, written here rather than read from serve.py, so a changed
# constant fails a test instead of moving it.
WRITING_WINDOW_S = 10
STATUS_PREVIEW_CHARS = 80
WIRE_HISTORY = 50
# How far the fake clock moves to step past the writing window while
# staying well inside the 600 s down window.
PAST_WRITING_S = 20
# The cycle case must return in this long (phases.md B1).
CYCLE_CEILING_SECONDS = 2
# Mode for a message body nobody may open.
NO_ACCESS = 0o000
# Model: Claude Opus 5.5 (the BOARD fixer, round 1), 2026-10-14. Status: unreviewed.
# A fixed fake "now" for tests that age files by hand with os.utime, so no
# test logic reads the wall clock. Any epoch works; this one is in 2030.
FAKE_NOW = 1_900_000_000.0
# A send this many seconds before "now" is inside WRITING_WINDOW_S; one
# OLD_SEND_S back is well past it.
RECENT_SEND_S = 3
OLD_SEND_S = 60
# An mtime this far ahead of "now": a touched file or a clock stepped back.
FUTURE_S = 3600
# The pid a stand-in snapshot names. Nothing checks it; no process has it.
STAND_IN_PID = 4242
# C1's word for an account nobody named, written here, not read from serve.py.
ACCOUNT_UNKNOWN = "unknown"
# A card this many "[" deep is past Python's recursion limit for json, yet
# under serve.py's 65,536-byte card cap, so the read reaches json.loads.
NESTED_DEPTH = 60000
# A feed that meets a FIFO must still return within this long.
FEED_CEILING_S = 2
# Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
# The fake nvidia-smi a test puts on PATH: owner may run it, all may read.
FAKE_EXE_MODE = 0o755
# A card file name with an escape sequence in it (ESC [ 2 J clears a
# terminal), legal on Linux, illegal under C0.
ESCAPE_CARD_NAME = "deep\x1b[2J.json"
# Model: Claude Opus 5.5 (the P4 phase fixer), 2026-10-15. Status: unreviewed.
# C5 and D24's numbers, written here rather than read from serve.py: down's
# window, the grace a woken listener reads working in, and tc's poll.
DOWN_WINDOW_S = 600
WOKEN_GRACE_S = 120
TC_POLL_S = 5
# tc wait sees new mail at its next poll, TC_POLL_S at most; a woken
# listener lets go of its lock within this long of the send.
WAKE_CEILING_S = 2 * TC_POLL_S
# A status written, or a message sent, this long after the last sighting:
# a sign of life after the wake, and past the writing window.
SIGN_OF_LIFE_S = 30
# A status this long before the last sighting: written before the wake.
OLD_STATUS_S = 100
# A made-up reason in the shape tc gives for an inbox it cannot count
# (mailbox_summary's mail_problem, on a shared mailbox).
MAIL_PROBLEM = "made-up reason: cannot list this inbox"
# A newest-mail age under 0: tc's mailbox_summary rounds now less a future mtime.
NEGATIVE_AGE_S = -5
# Model: Claude Opus 5.5 (the F1 lane agent), 2026-10-16. Status: unreviewed.
# The wait exit record's name in each inbox (tc's WAIT_EXIT_NAME, C5),
# written here rather than read from tc.
WAIT_EXIT_NAME = ".wait.exit"
# A .pyc header (PEP 552): the magic number, then three little-endian
# 32-bit words: flags (0, checked by the source's mtime and size), the
# source's mtime and its size, each kept to 32 bits.
PYC_WORD_BYTES = 4
PYC_WORD_MASK = 0xFFFFFFFF
# The seeded property test over the feed's roles and levels: a fixed seed,
# so a failure replays; a few hundred cases, so it runs in well under a
# second with no disk. Names are single letters, so the order-reversing
# rename (a and z swap) is a plain lookup.
PROPERTY_SEED = 20261015
PROPERTY_CASES = 600
NAME_POOL = "abcdefghijklmnopqrstuvwxyz"
PROPERTY_NAMES_MIN = 3
PROPERTY_NAMES_MAX = 8
# Most names carry a card, and most cards report to a name made before
# them, so the declared graph has no cycle and mail has chains to close.
CARD_CHANCE = 0.9
REPORTS_CHANCE = 0.8
# Up to this many messages per name, so most names have two partners or more.
MAIL_PER_NAME = 2
# A sender that is no node: rule 1 counts it as a partner all the same.
OUTSIDER = "outsider-1"
# The property cannot pass by never building the shape it guards: at least
# this many cases must have an inferred edge on a cycle to take out.
CYCLES_BROKEN_MIN = 20
# Model: Claude Opus 5.5 (the P4 phase fixer, round 2), 2026-10-15. Status: unreviewed.
# Where tc's read puts a message when read/ already holds a file of its
# name (a hand-made twin): read/by-hand-<k>-<name>, a name MESSAGE_NAME
# does not match, so the board never sees the message arrive there.
HAND_MOVED_PREFIX = "by-hand-1-"
# A hand-made file's number, far above any tc gave in the test.
PLANTED_SEQ = 900
# D27's relay shape: a trades this many messages each way with each of its
# two workers, so one message between the workers leaves a with 10 of each
# worker's 11, well past two thirds.
RELAY_TRADES = 5
# serve.py's WAKE_CANDIDATES, written here: a stopped name's newest messages
# a poll may lstat for its wake.
WAKE_CANDIDATES = 16
# Old messages to a stopped name in the cost test: three times the
# candidates, so a walk over its whole history shows in the count.
HISTORY_TIMES = 3


def load_serve():
    """Load board/serve.py as a module named board_serve.

    @interacts  executes serve.py's top level (constants and definitions).
    @deps       importlib.
    @complexity O(1).
    @alloc      one module object, returned.
    """
    spec = importlib.util.spec_from_file_location("board_serve", SERVE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


serve = load_serve()


class FakeClock:
    """A clock the test moves by hand: seconds since the epoch, like time.time.

    @interacts  none.
    @deps       none.
    @complexity O(1).
    @alloc      one float.
    """

    def __init__(self, now):
        """Start at `now`.

        @interacts  none.
        @deps       none.
        @complexity O(1).
        @alloc      one float.
        """
        self.now = now

    def __call__(self):
        """The current fake time.

        @interacts  none.
        @deps       none.
        @complexity O(1).
        @alloc      none.
        """
        return self.now


def write_card(root, name, kind="claude", account="work", route="local",
               reports_to=None, thread_id=None, ssh=None):
    """Write cards/<name>.json by hand, in C1's shape.

    @interacts  writes one file under root/cards/.
    @deps       json, pathlib.
    @complexity O(1).
    @alloc      none retained.
    """
    folder = pathlib.Path(root) / "cards"
    folder.mkdir(exist_ok=True)
    card = {"version": 1, "name": name, "kind": kind, "account": account, "route": route,
            "session_id": None, "pid": None, "thread_id": thread_id, "ssh": ssh,
            "reports_to": reports_to, "joined_at": "2026-10-14T12:00:00-05:00"}
    (folder / f"{name}.json").write_text(json.dumps(card), encoding="utf-8")


def put_message(root, seq, sender, to, unread=False):
    """Write one read message the way tc lays one out, without tc's router; return its path.

    The file is mail/to-<to>/read/NNNNNN-from-<sender>.md (or, with
    `unread`, mail/to-<to>/NNNNNN-from-<sender>.md, still in the inbox),
    written to a .tmp sibling and renamed (tc's send links instead, with the
    same file at the end), and mail/.seq is raised to `seq` under its
    flock. For mail to or from any name,
    including one whose card would route a real send elsewhere.

    @interacts  writes one message file and mail/.seq, making
                mail/to-<to>/read/ (or mail/to-<to>/) if needed.
    @deps       fcntl, pathlib.
    @complexity O(1).
    @alloc      the returned path.
    """
    mail = pathlib.Path(root) / "mail"
    folder = mail / f"to-{to}" if unread else mail / f"to-{to}" / "read"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{seq:06d}-from-{sender}.md"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(f"# #{seq} from {sender} to {to}, 2026-10-14T12:00:00-05:00\n\nhi\n", encoding="utf-8")
    tmp.rename(path)
    with open(mail / ".seq", "a+") as counter:
        fcntl.flock(counter, fcntl.LOCK_EX)
        counter.seek(0)
        top = max(seq, int(counter.read().strip() or 0))
        counter.seek(0)
        counter.truncate()
        counter.write(str(top))
    return path


def by_id(feed):
    """{id: node} for a feed's nodes.

    @interacts  none.
    @deps       none.
    @complexity O(n) over n nodes.
    @alloc      one dict, returned.
    """
    return {node["id"]: node for node in feed["nodes"]}


def age_file(path, at):
    """Set `path`'s mtime (and atime) to `at`, seconds since the epoch.

    @interacts  writes one file's times.
    @deps       os.
    @complexity O(1).
    @alloc      none.
    """
    os.utime(path, (at, at))


def check_parents_match_walk(test, feed):
    """Every node's parent is the one the level walk used (D15, phases.md B1).

    A node at level 0 has no parent; any other node's parent is a node one
    level up. A cycle's root is at level 0, so it carries no parent.

    @interacts  none.
    @deps       by_id.
    @complexity O(n) over n nodes.
    @alloc      one dict, freed on return.
    """
    nodes = by_id(feed)
    for name, node in nodes.items():
        parent = node["parent"]
        if node["level"] == 0:
            test.assertIsNone(parent, f"{name} is a root at level 0 but carries parent {parent}")
        else:
            test.assertIn(parent, nodes, f"{name} at level {node['level']} has no parent node")
            test.assertEqual(node["level"], nodes[parent]["level"] + 1,
                             f"{name} is not one level under its parent {parent}")


def release_fifo(path):
    """Open the FIFO at `path` for writing without blocking, then close it.

    A reader stuck opening the FIFO goes on and reads end of file, so no
    thread is left hanging. With no reader waiting the open fails (ENXIO),
    which is fine: nothing is stuck.

    @interacts  opens and closes one FIFO.
    @deps       os.
    @complexity O(1).
    @alloc      none.
    """
    try:
        fd = os.open(path, os.O_WRONLY | os.O_NONBLOCK)
    except OSError:
        return
    os.close(fd)


# Model: Claude Opus 5.5 (the P4 phase fixer, round 2), 2026-10-15. Status: unreviewed.
def snapshot_for(listening, names):
    """A stand-in for Board.snapshot: `listening` as the listeners, an inbox of 0 unread for each of `names`.

    @interacts  none; the returned function reads `listening` each call.
    @deps       none.
    @complexity O(1) to build; O(n) per call over the n names.
    @alloc      one function, returned; one small dict per call.
    """
    def stand_in():
        """A snapshot in Board.snapshot's shape naming `listening` and an inbox for each name.

        @interacts  reads `listening`.
        @deps       none.
        @complexity O(n) over the names.
        @alloc      one small dict, returned.
        """
        return {"time": "2030-03-17T12:00:00-05:00",
                "machine": {"load1": 0.0, "cores": 1, "mem_avail_pct": 50.0},
                "listeners": dict(listening),
                "mail": {name: {"unread": 0, "newest_mail_age_s": None} for name in names}}
    return stand_in


# Model: Claude Opus 5.5 (the F1 lane agent), 2026-10-16. Status: unreviewed.
def exit_record_made(box):
    """True once the wait exit record (C5, F1) is in the inbox `box`, within LOCK_CEILING_SECONDS: a listener proven by its lock writes it just after it takes the lock.

    @interacts  lstats one name until it is there.
    @deps       os, time; _root.LOCK_CEILING_SECONDS, _root.LOCK_POLL_SECONDS;
                WAIT_EXIT_NAME.
    @complexity at most LOCK_CEILING_SECONDS / LOCK_POLL_SECONDS lstats.
    @alloc      none.
    """
    end = time.monotonic() + _root.LOCK_CEILING_SECONDS
    while time.monotonic() < end:
        if os.path.lexists(box / WAIT_EXIT_NAME):
            return True
        time.sleep(_root.LOCK_POLL_SECONDS)
    return os.path.lexists(box / WAIT_EXIT_NAME)


def every_path(root):
    """Every path under `root`, relative and sorted: the root's file list.

    @interacts  lists the folder tree under `root`.
    @deps       pathlib.
    @complexity O(f) over f files and folders under root.
    @alloc      one sorted list, returned.
    """
    return sorted(str(p.relative_to(root)) for p in pathlib.Path(root).rglob("*"))


class FeedTest(unittest.TestCase):
    """Nodes, states, pids, wires and the status line on a real tc mailbox.

    @interacts  see the module block.
    @deps       _root.TcRoot, serve.Board.
    @complexity O(1) per test.
    @alloc      one TcRoot per test.
    """

    def test_states_pids_wires_and_down_with_unreadable_bodies(self):
        """Two listeners, a codex card, an ssh card and three messages; then one listener dies.

        A feed RECENT_SEND_S after the newest send, on a fake clock set
        from the message files' own times (so two slow listener proofs
        cannot carry it past the window): both listeners sent inside the
        writing window, so both read writing and keep their pids (D15:
        writing comes first). First feed, its clock past the window: four
        nodes in states listening, listening, doorbell, remote; the pids
        are the harness's; three wires with the right from, to and seq. The
        feeds write nothing. Second feed on the same Board, 20 s later on
        its clock, after b's listener is killed with no new mail: b is
        down. A new Board has seen nobody listening, but b's wait exit
        record still says listening, since its wait was killed, so b is
        down there too (F1, C5; before F1 it read idle). The file list
        is taken once both listeners have written their records, which
        each does just after it takes its lock (F1).

        The three messages run between a and b only: tc's router rings
        `codex` for a name with a codex card and runs `ssh` for one with
        an ssh card (SSH fix round 1, Claude Opus 5.5, unreviewed: the
        audit's LOW-29), so no test sends to cx or far; a card alone makes
        their nodes.

        Must reject a feed that opens message bodies: every body is mode
        000 before the first feed.

        @interacts  three `tc send`, two `tc read`; two listeners; four
                    feed() calls.
        @deps       _root.TcRoot.tc, _root.TcRoot.listener, serve.Board.
        @complexity O(1).
        @alloc      one TcRoot, removed on exit.
        """
        if os.geteuid() == 0:
            self.skipTest("root reads a mode 000 file, so the body check would prove nothing")
        with _root.TcRoot() as root:
            write_card(root.path, "cx", kind="codex", route="codex", thread_id="t1")
            write_card(root.path, "far", route="ssh",
                       ssh={"target": "u@h", "tc": "~/TheConnection/tc"})
            sends = (("a", "b"), ("b", "a"), ("a", "b"))
            for sender, to in sends:
                code, out, err = root.tc("send", "--from", sender, "--to", to, f"note from {sender}")
                self.assertEqual(code, 0, f"tc send --from {sender} --to {to} exited {code}: {err}")
            for name in ("a", "b"):
                code, out, err = root.tc("read", name)
                self.assertEqual(code, 0, f"tc read {name} exited {code}: {err}")
            bodies = sorted(root.path.glob("mail/to-*/**/*.md"))
            self.assertEqual(len(bodies), len(sends), f"message files: {bodies}")
            for body in bodies:
                body.chmod(NO_ACCESS)
            with self.assertRaises(PermissionError, msg=f"{bodies[0]} is still readable"):
                bodies[0].read_bytes()

            clock = FakeClock(max(body.stat().st_mtime for body in bodies) + RECENT_SEND_S)
            board = serve.Board(root=root.path, clock=clock)
            with root.listener("a", LISTENER_TIMEOUT_SECONDS) as pid_a:
                with root.listener("b", LISTENER_TIMEOUT_SECONDS) as pid_b:
                    for name in ("a", "b"):  # F1 (Claude Opus 5.5, unreviewed): each writes its record after its lock
                        exit_record_made(root.path / "mail" / f"to-{name}")
                    before = every_path(root.path)
                    inside = board.feed()
                    # Past the window, so the senders read listening.
                    clock.now += PAST_WRITING_S
                    first = board.feed()
                    after = every_path(root.path)
                clock.now += PAST_WRITING_S
                second = board.feed()
            fresh = serve.Board(root=root.path, clock=clock).feed()

        self.assertEqual(before, after, "feed() changed the root's file list")
        busy = by_id(inside)
        self.assertEqual({name: (busy[name]["state"], busy[name]["listener_pid"]) for name in ("a", "b")},
                         {"a": ("writing", pid_a), "b": ("writing", pid_b)})
        nodes = by_id(first)
        self.assertEqual(sorted(nodes), ["a", "b", "cx", "far"], json.dumps(first, indent=1))
        self.assertEqual({name: nodes[name]["state"] for name in nodes},
                         {"a": "listening", "b": "listening", "cx": "doorbell", "far": "remote"})
        self.assertEqual((nodes["a"]["listener_pid"], nodes["b"]["listener_pid"]), (pid_a, pid_b))
        self.assertEqual([(w["from"], w["to"], w["seq"]) for w in first["wires"]],
                         [("a", "b", 1), ("b", "a", 2), ("a", "b", 3)])
        for wire in first["wires"]:
            self.assertGreater(wire["age_s"], WRITING_WINDOW_S,
                               f"wire {wire} is inside the writing window, so its sender "
                               f"reads writing, not listening")
        self.assertEqual(set(first["machine"]), {"load1", "cores", "mem_avail_pct"})

        later = by_id(second)
        self.assertEqual(later["b"]["state"], "down", json.dumps(later["b"]))
        self.assertIsNone(later["b"]["listener_pid"])
        self.assertEqual(later["a"]["state"], "listening")
        # F1 (Claude Opus 5.5, unreviewed): C5, a killed listener reads down after a restart too.
        self.assertEqual(by_id(fresh)["b"]["state"], "down",
                         "b's wait was killed and its exit record still says listening, so a new Board reads it down")

    def test_status_is_the_first_line_after_the_header_cut_at_80(self):
        """`tc status a <100 characters>`: the node's status is the first 80, no header.

        Must reject a feed that shows the header line, or the line uncut.

        @interacts  one `tc status`; one feed().
        @deps       _root.TcRoot.tc, serve.Board.
        @complexity O(1).
        @alloc      one TcRoot, removed on exit.
        """
        text = "reviewing the parser " + "x" * 100
        with _root.TcRoot() as root:
            write_card(root.path, "a")
            code, out, err = root.tc("status", "a", text)
            self.assertEqual(code, 0, f"tc status exited {code}: {err}")
            status = by_id(serve.Board(root=root.path).feed())["a"]["status"]
        self.assertEqual(status, text[:STATUS_PREVIEW_CHARS])

    def test_a_recent_sender_with_no_listener_is_writing_then_idle(self):
        """w sends with no listener: writing now, idle once the window has passed.

        @interacts  one `tc send`; two feed() calls.
        @deps       _root.TcRoot.tc, serve.Board.
        @complexity O(1).
        @alloc      one TcRoot, removed on exit.
        """
        with _root.TcRoot() as root:
            write_card(root.path, "w")
            code, out, err = root.tc("send", "--from", "w", "--to", "peer", "hi")
            self.assertEqual(code, 0, f"tc send exited {code}: {err}")
            clock = FakeClock(time.time())
            board = serve.Board(root=root.path, clock=clock)
            now = by_id(board.feed())
            clock.now += WRITING_WINDOW_S + 1
            later = by_id(board.feed())
        self.assertEqual((now["w"]["state"], now["peer"]["state"]), ("writing", "idle"))
        self.assertEqual(later["w"]["state"], "idle")

    # Model: Claude Opus 5.5 (the BOARD fixer, round 1), 2026-10-14. Status: unreviewed.
    def test_state_order_follows_d15(self):
        """D15's order: writing, down, listening, doorbell, remote, idle; the first match wins.

        One Board, a stand-in snapshot that names the listeners, and
        message files aged by hand against a fake clock. Feed 1 sees w1,
        w2, d1, d2, l1 and l2 listening. Feed 2, 20 s later: w1 (still
        listening) and w2 (stopped) each sent 3 s ago and read writing; d1
        (codex card) and d2 (ssh card) stopped and read down, not doorbell
        or remote; l1 (listening, sent 60 s ago) and l2 (codex, listening)
        read listening; cx doorbell, far remote, i1 idle. Feed 3, past the
        window: w1 reads listening again and w2 down (phases.md B1).

        Must reject the old chain (w1 would read listening, d1 doorbell)
        and a plain reorder that drops `not pid` from down: every live
        listener is in last_listening_at, so l1 would read down.

        @interacts  five cards and three message files in a fresh TcRoot;
                    three feed() calls with Board.snapshot swapped for a
                    stand-in.
        @deps       _root.TcRoot, write_card, put_message, age_file,
                    serve.Board, unittest.mock.
        @complexity O(1): nine names, three messages.
        @alloc      one TcRoot, removed on exit.
        """
        names = ("w1", "w2", "d1", "d2", "l1", "l2", "cx", "far", "i1")
        listening = {}

        def stand_in():
            """A snapshot in Board.snapshot's shape naming `listening` and an inbox for each name.

            @interacts  reads `listening`.
            @deps       none.
            @complexity O(n) over the nine names.
            @alloc      one small dict, returned.
            """
            return {"time": "2030-03-17T12:00:00-05:00",
                    "machine": {"load1": 0.0, "cores": 1, "mem_avail_pct": 50.0, "gpus": None},
                    "sessions": {"claude": 0, "codex": 0}, "listeners": dict(listening),
                    "watchers": {},
                    "mail": {name: {"unread": 0, "newest_mail_age_s": None, "status_age_s": None}
                             for name in names}}

        def states(feed):
            """{name: (state, listener_pid)} for one feed.

            @interacts  none.
            @deps       by_id.
            @complexity O(n) over n nodes.
            @alloc      one dict, returned.
            """
            return {name: (node["state"], node["listener_pid"]) for name, node in by_id(feed).items()}

        with _root.TcRoot() as root:
            for name, route in (("d1", "codex"), ("d2", "ssh"), ("l2", "codex"),
                                ("cx", "codex"), ("far", "ssh")):
                write_card(root.path, name, kind="codex" if route == "codex" else "claude",
                           route=route, thread_id="t1" if route == "codex" else None)
            clock = FakeClock(FAKE_NOW)
            board = serve.Board(root=root.path, clock=clock)
            with mock.patch.object(board, "snapshot", stand_in):
                listening.update(dict.fromkeys(("w1", "w2", "d1", "d2", "l1", "l2"), STAND_IN_PID))
                board.feed()
                clock.now += PAST_WRITING_S
                for seq, (sender, ago) in enumerate((("w1", RECENT_SEND_S), ("w2", RECENT_SEND_S),
                                                     ("l1", OLD_SEND_S)), start=1):
                    age_file(put_message(root.path, seq, sender, "i1"), clock.now - ago)
                listening.clear()
                listening.update(dict.fromkeys(("w1", "l1", "l2"), STAND_IN_PID))
                second = states(board.feed())
                clock.now += PAST_WRITING_S
                third = states(board.feed())

        self.assertEqual(second, {
            "w1": ("writing", STAND_IN_PID), "w2": ("writing", None),
            "d1": ("down", None), "d2": ("down", None),
            "l1": ("listening", STAND_IN_PID), "l2": ("listening", STAND_IN_PID),
            "cx": ("doorbell", None), "far": ("remote", None), "i1": ("idle", None),
        })
        self.assertEqual((third["w1"], third["w2"], third["l1"]),
                         (("listening", STAND_IN_PID), ("down", None), ("listening", STAND_IN_PID)))

    # Model: Claude Opus 5.5 (the P4 phase fixer), 2026-10-15. Status: unreviewed.
    def test_a_real_wake_reads_working_then_woken_and_never_down(self):
        """b and c listen; a mails b, b's wait exits; c is killed with no mail (D24).

        One poll after the wake b reads working (the grace), past
        WOKEN_GRACE_S with nothing read it reads woken, and after `tc read
        b` working again: never down. c, a listener lost with no mail,
        reads down: the control, so the test cannot pass by never saying
        down. Past DOWN_WINDOW_S b fades to idle, and c, whose wait exit
        record still says listening (it was killed), stays down (F1, C5;
        before F1 both faded to idle). b's listener output
        says MAIL:, so its wait ended on the mail, not on a kill. The
        message's mtime is set on the fake clock's own line, so no wall
        clock decides a state.

        Must reject C5's old `down` for every name seen listening and not
        listening now: b would read down one poll after its wake.

        @interacts  two proven listeners; one `tc send`, one `tc read`;
                    five feed() calls on a fake clock; reads /proc/locks
                    until b's wait lets go.
        @deps       _root.TcRoot, _root.flock_holders, serve.Board,
                    age_file.
        @complexity O(1), plus up to WAKE_CEILING_S for b's wait to see
                    its mail.
        @alloc      one TcRoot, removed on exit.
        """
        with _root.TcRoot() as root:
            clock = FakeClock(FAKE_NOW)
            board = serve.Board(root=root.path, clock=clock)
            with root.listener("b", LISTENER_TIMEOUT_SECONDS) as pid_b:
                with root.listener("c", LISTENER_TIMEOUT_SECONDS) as pid_c:
                    exit_record_made(root.path / "mail" / "to-c")  # F1 (Claude Opus 5.5, unreviewed): killed after it
                    seen = by_id(board.feed())
                    code, out, err = root.tc("send", "--from", "a", "--to", "b", "task")
                    self.assertEqual(code, 0, f"tc send exited {code}: {err}")
                    lock = root.path / "mail" / "to-b" / ".wait.lock"  # P3 fix round 1b (Claude Opus 5.5, unreviewed): D35
                    end = time.monotonic() + WAKE_CEILING_S
                    while pid_b in _root.flock_holders(lock) and time.monotonic() < end:
                        time.sleep(_root.LOCK_POLL_SECONDS)
                    self.assertNotIn(pid_b, _root.flock_holders(lock), f"b's wait never saw its mail in {WAKE_CEILING_S} s")
                    age_file(root.path / "mail" / "to-b" / "000001-from-a.md", FAKE_NOW + 1)
                said = "".join(p.read_text() for p in root.base.glob("listener-b-*.out"))
                clock.now = FAKE_NOW + 1 + RECENT_SEND_S
                grace = by_id(board.feed())
                clock.now = FAKE_NOW + 1 + WOKEN_GRACE_S + 1
                late = by_id(board.feed())
                code, out, err = root.tc("read", "b")
                self.assertEqual(code, 0, f"tc read b exited {code}: {err}")
                read = by_id(board.feed())
                clock.now = FAKE_NOW + DOWN_WINDOW_S + 1
                faded = by_id(board.feed())

        def pair(nodes):
            """{b, c: (state, listener_pid)}.

            @interacts  none.
            @deps       none.
            @complexity O(1).
            @alloc      one dict, returned.
            """
            return {name: (nodes[name]["state"], nodes[name]["listener_pid"]) for name in ("b", "c")}

        self.assertIn("MAIL:", said, f"b's wait did not end on its mail: {said!r}")
        self.assertEqual(pair(seen), {"b": ("listening", pid_b), "c": ("listening", pid_c)})
        self.assertEqual(pair(grace), {"b": ("working", None), "c": ("down", None)})
        self.assertEqual(pair(late), {"b": ("woken", None), "c": ("down", None)})
        self.assertEqual(pair(read), {"b": ("working", None), "c": ("down", None)})
        # F1 (Claude Opus 5.5, unreviewed): C5, c's record says listening, so it stays down past the window.
        self.assertEqual(pair(faded), {"b": ("idle", None), "c": ("down", None)})

    # Model: Claude Opus 5.5 (the P4 phase fixer), 2026-10-15. Status: unreviewed.
    def test_a_sign_of_life_after_a_wake_reads_working(self):
        """Past the grace, a woken name reads working on a fresh status or a send, woken on neither (D24).

        A stand-in snapshot names s1, s2, q and d listening, then none. s1,
        s2 and q each got a message after the sighting, still unread. s1
        then wrote its status and s2 sent a message, both SIGN_OF_LIFE_S
        after the sighting; q's status is from before it. Past
        WOKEN_GRACE_S: s1 and s2 working, q woken, d (no mail) down. s1's
        status shows as it is; q's reads as its last status.

        Must reject a woken state that ignores a status or a send, and a
        status from before the wake taken as a sign of life.

        @interacts  four cards' worth of mail and two status files in a
                    fresh TcRoot; two feed() calls with Board.snapshot
                    swapped for a stand-in.
        @deps       _root.TcRoot, put_message, age_file, serve.Board,
                    unittest.mock.
        @complexity O(1).
        @alloc      one TcRoot, removed on exit.
        """
        names = ("s1", "s2", "q", "d")
        listening = {}

        def stand_in():
            """A snapshot in Board.snapshot's shape naming `listening` and an inbox for each name.

            @interacts  reads `listening`.
            @deps       none.
            @complexity O(n) over the four names.
            @alloc      one small dict, returned.
            """
            return {"time": "2030-03-17T12:00:00-05:00",
                    "machine": {"load1": 0.0, "cores": 1, "mem_avail_pct": 50.0},
                    "listeners": dict(listening),
                    "mail": {name: {"unread": 0, "newest_mail_age_s": None} for name in names}}

        with _root.TcRoot() as root:
            clock = FakeClock(FAKE_NOW)
            board = serve.Board(root=root.path, clock=clock)
            status = root.path / "status"
            status.mkdir()
            with mock.patch.object(board, "snapshot", stand_in):
                listening.update(dict.fromkeys(names, STAND_IN_PID))
                board.feed()
                listening.clear()
                for seq, name in enumerate(("s1", "s2", "q"), start=1):
                    age_file(put_message(root.path, seq, "boss", name, unread=True), FAKE_NOW + 1)
                for name, text, at in (("s1", "parsing the logs", FAKE_NOW + SIGN_OF_LIFE_S),
                                       ("q", "before the wake", FAKE_NOW - OLD_STATUS_S)):
                    (status / f"{name}.md").write_text(f"## {name} status, 2030-03-17T12:00:00-05:00\n\n{text}\n")
                    age_file(status / f"{name}.md", at)
                age_file(put_message(root.path, 4, "s2", "boss"), FAKE_NOW + SIGN_OF_LIFE_S)
                clock.now = FAKE_NOW + 1 + WOKEN_GRACE_S + 1
                later = by_id(board.feed())

        self.assertEqual({name: later[name]["state"] for name in names},
                         {"s1": "working", "s2": "working", "q": "woken", "d": "down"})
        self.assertEqual((later["s1"]["status"], later["q"]["status"]), ("parsing the logs", "before the wake"))

    # Model: Claude Opus 5.5 (the P4 phase fixer, round 2), 2026-10-15. Status: unreviewed.
    def test_mail_to_a_listener_the_board_saw_gone_is_no_wake(self):
        """c's listener is killed with no mail and reads down; mail sent after the board saw it gone leaves it down (D28).

        b and c listen, proven, and the board sees both. a mails b while b
        still listens; then b's wait ends on that mail and c's is killed
        (F1, Claude Opus 5.5, unreviewed: b's wait now runs until it sees
        the mail, so its exit record says mail; a kill would leave it
        saying listening, which reads down, C5). One poll later b reads
        working (its mail landed inside its wake window, and the grace
        runs) and c down. Then a mails c, and that mail lands past
        POLL_SECONDS after the poll that first found c gone: c reads down
        on the next poll and past WOKEN_GRACE_S, never working or woken.
        b, past the grace with its mail unread, reads woken, and after `tc
        read b` working: a real wake still holds. Each message's mtime is
        set on the fake clock's line; nothing sleeps.

        Must reject a wake with no upper bound (no first-missing time):
        c's late mail would read as its wake, working and then woken.

        @interacts  two proven listeners; two `tc send`, one `tc read`;
                    five feed() calls on a fake clock.
        @deps       _root.TcRoot, serve.Board, age_file, by_id.
        @complexity O(1).
        @alloc      one TcRoot, removed on exit.
        """
        with _root.TcRoot() as root:
            clock = FakeClock(FAKE_NOW)
            board = serve.Board(root=root.path, clock=clock)
            with root.listener("b", LISTENER_TIMEOUT_SECONDS) as pid_b:
                with root.listener("c", LISTENER_TIMEOUT_SECONDS) as pid_c:
                    exit_record_made(root.path / "mail" / "to-c")  # F1 (Claude Opus 5.5, unreviewed): killed after it
                    seen = by_id(board.feed())
                    code, out, err = root.tc("send", "--from", "a", "--to", "b", "task")
                    self.assertEqual(code, 0, f"tc send exited {code}: {err}")
                    # F1 (Claude Opus 5.5, unreviewed): b's wait ends on its mail, as a real wake does.
                    lock = root.path / "mail" / "to-b" / ".wait.lock"
                    end = time.monotonic() + WAKE_CEILING_S
                    while pid_b in _root.flock_holders(lock) and time.monotonic() < end:
                        time.sleep(_root.LOCK_POLL_SECONDS)
                    self.assertNotIn(pid_b, _root.flock_holders(lock), f"b's wait never saw its mail in {WAKE_CEILING_S} s")
            age_file(root.path / "mail" / "to-b" / "000001-from-a.md", FAKE_NOW + 1)
            clock.now = FAKE_NOW + RECENT_SEND_S
            gone = by_id(board.feed())
            code, out, err = root.tc("send", "--from", "a", "--to", "c", "are you there")
            self.assertEqual(code, 0, f"tc send exited {code}: {err}")
            age_file(root.path / "mail" / "to-c" / "000002-from-a.md", clock.now + TC_POLL_S + 1)
            clock.now += TC_POLL_S + 2
            mailed = by_id(board.feed())
            clock.now = FAKE_NOW + 1 + WOKEN_GRACE_S + 1
            late = by_id(board.feed())
            code, out, err = root.tc("read", "b")
            self.assertEqual(code, 0, f"tc read b exited {code}: {err}")
            read = by_id(board.feed())

        def pair(nodes):
            """{b, c: (state, listener_pid, inbox_unreadable)}.

            @interacts  none.
            @deps       none.
            @complexity O(1).
            @alloc      one dict, returned.
            """
            return {name: (nodes[name]["state"], nodes[name]["listener_pid"], nodes[name]["inbox_unreadable"])
                    for name in ("b", "c")}

        self.assertEqual(pair(seen), {"b": ("listening", pid_b, False), "c": ("listening", pid_c, False)})
        self.assertEqual(pair(gone), {"b": ("working", None, False), "c": ("down", None, False)})
        self.assertEqual(pair(mailed), {"b": ("working", None, False), "c": ("down", None, False)},
                         "mail that reached c after the board saw it gone woke it")
        self.assertEqual(pair(late), {"b": ("woken", None, False), "c": ("down", None, False)})
        self.assertEqual(pair(read), {"b": ("working", None, False), "c": ("down", None, False)})

    # Model: Claude Opus 5.5 (the P4 phase fixer, round 2), 2026-10-15. Status: unreviewed.
    def test_a_stopped_name_lstats_only_its_newest_messages_and_none_once_settled(self):
        """b holds 48 old messages and the one that woke it: a poll lstats at most WAKE_CANDIDATES of them, and none once its window has passed (LOW-14).

        A stand-in snapshot names b listening, then not. While b's wake
        window is open, its candidates are its newest messages by number,
        kept as the scan goes, so the poll lstats WAKE_CANDIDATES of them
        and finds the wake there: working. The first poll past the window
        looks once more and settles; the next lstats none of b's messages
        and still reads working. Must reject a walk over b's whole
        history: it would lstat all 49.

        @interacts  49 message files in a fresh TcRoot; four feed() calls
                    with Board.snapshot swapped for a stand-in and
                    serve.file_time wrapped to count.
        @deps       _root.TcRoot, put_message, age_file, snapshot_for,
                    serve.Board, unittest.mock.
        @complexity O(1): 49 messages.
        @alloc      one TcRoot, removed on exit.
        """
        listening = {}
        old = HISTORY_TIMES * WAKE_CANDIDATES
        with _root.TcRoot() as root:
            clock = FakeClock(FAKE_NOW)
            board = serve.Board(root=root.path, clock=clock)
            for seq in range(1, old + 1):
                age_file(put_message(root.path, seq, "a", "b"), FAKE_NOW - OLD_SEND_S)
            age_file(put_message(root.path, old + 1, "a", "b", unread=True), FAKE_NOW + 1)
            box = str(root.path / "mail" / "to-b")
            counted = []
            real = serve.file_time

            def counting(path):
                """serve.file_time, noting each path under b's inbox.

                @interacts  see serve.file_time; appends to `counted`.
                @deps       serve.file_time.
                @complexity O(1).
                @alloc      one list entry per path under to-b.
                """
                if str(path).startswith(box):
                    counted.append(path)
                return real(path)

            polls = []
            with mock.patch.object(board, "snapshot", snapshot_for(listening, ("b",))), \
                    mock.patch.object(serve, "file_time", counting):
                listening["b"] = STAND_IN_PID
                board.feed()
                listening.clear()
                for at in (FAKE_NOW + RECENT_SEND_S, FAKE_NOW + RECENT_SEND_S + 2 * TC_POLL_S,
                           FAKE_NOW + RECENT_SEND_S + 3 * TC_POLL_S):
                    clock.now = at
                    counted.clear()
                    polls.append((by_id(board.feed())["b"]["state"], len(counted)))
        self.assertEqual(polls, [("working", WAKE_CANDIDATES), ("working", WAKE_CANDIDATES), ("working", 0)],
                         "(state, b's messages lstatted) per poll: open, the last look, settled")

    # Model: Claude Opus 5.5 (the P4 phase fixer, round 2), 2026-10-15. Status: unreviewed.
    def test_an_inbox_the_board_cannot_list_reads_down_inbox_unreadable(self):
        """u1's inbox and u2's read/ are closed to the board: each reads down, inbox_unreadable; r, open, reads working.

        A stand-in snapshot names r, u1 and u2 listening, then none. Each
        got a message in its inbox right after the sighting, so each was
        woken. The board can list r's folders: working (the grace). It
        cannot list u1's inbox (mode 000), nor u2's read/, where a read
        waking message would be: it cannot tell, so each reads down with
        inbox_unreadable true (C5, D28). Each folder gets its mode back
        before the root is removed.

        Must reject a board that takes a folder it cannot list for an
        empty one: u1 would read down with the flag false, and u2 working.

        @interacts  four message files and two folders closed, then opened
                    again, in a fresh TcRoot; two feed() calls with
                    Board.snapshot swapped for a stand-in.
        @deps       _root.TcRoot, put_message, age_file, snapshot_for,
                    serve.Board, unittest.mock.
        @complexity O(1).
        @alloc      one TcRoot, removed on exit.
        """
        if os.geteuid() == 0:
            self.skipTest("root lists a mode 000 folder, so the check would prove nothing")
        names = ("r", "u1", "u2")
        listening = {}
        with _root.TcRoot() as root:
            clock = FakeClock(FAKE_NOW)
            board = serve.Board(root=root.path, clock=clock)
            for seq, name in enumerate(names, start=1):
                age_file(put_message(root.path, seq, "boss", name, unread=True), FAKE_NOW + 1)
            age_file(put_message(root.path, len(names) + 1, "boss", "u2"), FAKE_NOW - OLD_SEND_S)
            closed = [root.path / "mail" / "to-u1", root.path / "mail" / "to-u2" / "read"]
            modes = [stat.S_IMODE(folder.stat().st_mode) for folder in closed]
            with mock.patch.object(board, "snapshot", snapshot_for(listening, names)):
                listening.update(dict.fromkeys(names, STAND_IN_PID))
                board.feed()
                listening.clear()
                clock.now = FAKE_NOW + RECENT_SEND_S
                try:
                    for folder in closed:
                        folder.chmod(NO_ACCESS)
                    nodes = by_id(board.feed())
                finally:
                    for folder, mode in zip(closed, modes):
                        folder.chmod(mode)
        self.assertEqual({name: (nodes[name]["state"], nodes[name]["inbox_unreadable"]) for name in names},
                         {"r": ("working", False), "u1": ("down", True), "u2": ("down", True)})

    def test_a_message_from_the_future_is_not_writing(self):
        """A message whose mtime is an hour ahead of now gives its sender no age: not writing.

        Its wire and its mailbox link carry no age either, so the page does
        not animate it. Must reject `max(0, ...)` in file_age, which turns
        a future mtime into "just now".

        @interacts  one card and one message file in a fresh TcRoot; one
                    feed().
        @deps       _root.TcRoot, write_card, put_message, age_file,
                    serve.Board.
        @complexity O(1).
        @alloc      one TcRoot, removed on exit.
        """
        with _root.TcRoot() as root:
            write_card(root.path, "f")
            age_file(put_message(root.path, 1, "f", "g"), FAKE_NOW + FUTURE_S)
            feed = serve.Board(root=root.path, clock=FakeClock(FAKE_NOW)).feed()
        self.assertEqual(by_id(feed)["f"]["state"], "idle", json.dumps(feed["nodes"]))
        self.assertEqual([(w["from"], w["age_s"]) for w in feed["wires"]], [("f", None)])
        self.assertEqual([link["last_age_s"] for link in feed["links"] if link["kind"] == "mailbox"], [None])

    # Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
    def test_a_feed_runs_no_gpu_query(self):
        """A fake nvidia-smi on PATH records each run: tc's machine_stats runs it, feed() never does.

        tc's health snapshot waits up to GPU_QUERY_TIMEOUT_SECONDS for
        nvidia-smi, longer than the page waits for an answer. Must reject a
        feed built from tc.health_snapshot(): the fake's record would exist
        after feed(). The control call to tc.machine_stats() proves the fake
        is found on PATH, so the check cannot pass by not checking.

        @interacts  one card and one fake nvidia-smi in a fresh TcRoot;
                    PATH patched for the test; one feed() and one
                    tc.machine_stats().
        @deps       _root.TcRoot, write_card, serve.Board, unittest.mock,
                    shlex.
        @complexity O(1).
        @alloc      one TcRoot, removed on exit.
        """
        with _root.TcRoot() as root:
            write_card(root.path, "a")
            folder = root.base / "gpu"
            folder.mkdir()
            record = root.base / "gpu-ran"
            fake = folder / "nvidia-smi"
            fake.write_text(f"#!/bin/sh\necho ran >> {shlex.quote(str(record))}\necho '30, 5'\n")
            fake.chmod(FAKE_EXE_MODE)
            board = serve.Board(root=root.path)
            with mock.patch.dict(os.environ, {"PATH": f"{folder}{os.pathsep}{os.environ.get('PATH', '')}"}):
                feed = board.feed()
                ran_in_feed = record.exists()
                gpus = board.tc.machine_stats()["gpus"]
                ran_in_control = record.exists()
        self.assertFalse(ran_in_feed, "feed() ran nvidia-smi")
        self.assertTrue(ran_in_control, "the fake nvidia-smi was never found, so the check proves nothing")
        self.assertEqual(gpus, [{"temp_c": 30, "util_pct": 5}])
        self.assertEqual(set(feed["machine"]), {"load1", "cores", "mem_avail_pct"})
        self.assertEqual(feed["machine"]["cores"], os.cpu_count() or 1)
        self.assertEqual([node["id"] for node in feed["nodes"]], ["a"])


class ShapesTest(unittest.TestCase):
    """D7's shapes through feed(): roles, role_source, levels, parents, links.

    @interacts  see the module block.
    @deps       _root.TcRoot, serve.Board, write_card, put_message.
    @complexity O(1) per test.
    @alloc      one TcRoot per test.
    """

    def shape(self, cards=(), talks=(), notes=()):
        """Feed for a root with these cards and these exchanges; checks ids and parents.

        Every node is drawn once, and each parent is the one the walk used
        (check_parents_match_walk), in every shape.

        `cards` is (name, reports_to) pairs, each a claude card on one
        account. `talks` is (x, y) pairs: one message x to y and one y to
        x, both read, so both names have an inbox; a pair listed k times
        trades k messages each way. `notes` is (x, y) pairs of one message
        x to y alone, read.

        @interacts  writes cards and message files in a fresh TcRoot; one
                    feed().
        @deps       _root.TcRoot, write_card, put_message, serve.Board,
                    check_parents_match_walk.
        @complexity O(c + t + o) over c cards, t exchanges and o notes.
        @alloc      one TcRoot, removed before return; the feed, returned.
        """
        with _root.TcRoot() as root:
            for name, reports_to in cards:
                write_card(root.path, name, reports_to=reports_to)
            seq = 0
            for sender, to in [way for x, y in talks for way in ((x, y), (y, x))] + list(notes):
                seq += 1
                put_message(root.path, seq, sender, to)
            feed = serve.Board(root=root.path).feed()
        ids = [node["id"] for node in feed["nodes"]]
        self.assertEqual(len(ids), len(set(ids)), f"a node is drawn twice: {ids}")
        check_parents_match_walk(self, feed)
        return feed

    def assert_nodes(self, feed, expected):
        """Each named node has exactly these (role, role_source, level, parent).

        @interacts  none.
        @deps       by_id.
        @complexity O(n) over n nodes.
        @alloc      two dicts, freed on return.
        """
        nodes = by_id(feed)
        got = {name: (nodes[name]["role"], nodes[name]["role_source"], nodes[name]["level"],
                      nodes[name]["parent"]) for name in expected if name in nodes}
        self.assertEqual(got, expected, json.dumps(feed["nodes"], indent=1))

    def test_star_with_hints(self):
        """b, c, d report to a: a orchestrator at 0, the rest workers at 1, all declared.

        @interacts  one shape root.
        @deps       shape, assert_nodes.
        @complexity O(1).
        @alloc      one feed.
        """
        feed = self.shape(cards=[("a", None), ("b", "a"), ("c", "a"), ("d", "a")])
        self.assert_nodes(feed, {
            "a": ("orchestrator", "declared", 0, None),
            "b": ("worker", "declared", 1, "a"),
            "c": ("worker", "declared", 1, "a"),
            "d": ("worker", "declared", 1, "a"),
        })

    def test_chain_with_hints(self):
        """b reports to a; c and d to b: levels 0, 1, 2, 2; a and b orchestrators.

        @interacts  one shape root.
        @deps       shape, assert_nodes.
        @complexity O(1).
        @alloc      one feed.
        """
        feed = self.shape(cards=[("a", None), ("b", "a"), ("c", "b"), ("d", "b")])
        self.assert_nodes(feed, {
            "a": ("orchestrator", "declared", 0, None),
            "b": ("orchestrator", "declared", 1, "a"),
            "c": ("worker", "declared", 2, "b"),
            "d": ("worker", "declared", 2, "b"),
        })

    def test_chain_with_no_cards_pins_the_known_limit(self):
        """The same chain by mail alone: b is the root, a, c and d its inferred workers.

        C5 rule 6, on purpose: with no hints, the top relay a, whose only
        partner is b, is drawn as b's worker. A change here is a decision.

        @interacts  one shape root.
        @deps       shape, assert_nodes.
        @complexity O(1).
        @alloc      one feed.
        """
        feed = self.shape(talks=[("a", "b"), ("b", "c"), ("b", "d")])
        self.assert_nodes(feed, {
            "b": ("orchestrator", "inferred", 0, None),
            "a": ("worker", "inferred", 1, "b"),
            "c": ("worker", "inferred", 1, "b"),
            "d": ("worker", "inferred", 1, "b"),
        })

    def test_two_orchestrators_side_by_side(self):
        """x over x1, x2 (cards); y over y1, y2 (mail only); x and y mail each other.

        Two level 0 orchestrators and a mailbox link between them. Must
        reject a feed that picks one root for the whole board.

        @interacts  one shape root.
        @deps       shape, assert_nodes.
        @complexity O(1).
        @alloc      one feed.
        """
        feed = self.shape(cards=[("x1", "x"), ("x2", "x")],
                          talks=[("x", "x1"), ("x", "x2"), ("y", "y1"), ("y", "y2"), ("x", "y")])
        self.assert_nodes(feed, {
            "x": ("orchestrator", "declared", 0, None),
            "y": ("orchestrator", "inferred", 0, None),
            "x1": ("worker", "declared", 1, "x"),
            "x2": ("worker", "declared", 1, "x"),
            "y1": ("worker", "inferred", 1, "y"),
            "y2": ("worker", "inferred", 1, "y"),
        })
        pairs = [(link["from"], link["to"]) for link in feed["links"] if link["kind"] == "mailbox"]
        self.assertIn(("x", "y"), pairs)

    def test_a_reports_to_cycle_ends(self):
        """p reports to q and q to p: p level 0, q level 1, and feed() returns within 2 s.

        Must reject a level walk with no cycle break: feed() runs in a
        daemon thread, and a walk that never ends leaves the thread alive.
        The root is built and removed in the test's own thread, so a hung
        walk never holds it open.

        @interacts  two cards in a fresh TcRoot; one feed() in a daemon
                    thread.
        @deps       _root.TcRoot, write_card, serve.Board, threading.
        @complexity O(1).
        @alloc      one TcRoot, removed on exit; one thread.
        """
        result = {}
        with _root.TcRoot() as root:
            write_card(root.path, "p", reports_to="q")
            write_card(root.path, "q", reports_to="p")
            board = serve.Board(root=root.path)
            worker = threading.Thread(target=lambda: result.update(feed=board.feed()), daemon=True)
            worker.start()
            worker.join(CYCLE_CEILING_SECONDS)
        self.assertFalse(worker.is_alive(), f"feed() did not return within {CYCLE_CEILING_SECONDS} s")
        nodes = by_id(result["feed"])
        self.assertEqual((nodes["p"]["level"], nodes["q"]["level"]), (0, 1))
        check_parents_match_walk(self, result["feed"])

    def test_a_node_below_a_cycle_stays_below_it(self):
        """p and q report to each other, and a reports to q: a hangs under q at level 2.

        a sorts before p and q but is not on the cycle, so it never becomes
        the root that breaks it (assumption in the BOARD handoff). p, the
        cycle's root, carries no parent, since the walk used none for it
        (D15); its reports_to still names q.

        @interacts  one shape root.
        @deps       shape, assert_nodes.
        @complexity O(1).
        @alloc      one feed.
        """
        feed = self.shape(cards=[("p", "q"), ("q", "p"), ("a", "q")])
        nodes = by_id(feed)
        self.assertEqual({name: (nodes[name]["level"], nodes[name]["parent"]) for name in nodes},
                         {"p": (0, None), "q": (1, "p"), "a": (2, "q")})
        self.assertEqual(nodes["p"]["reports_to"], "q")

    def test_a_reports_to_naming_nobody(self):
        """r reports to ghost, which is no node: r is a root and keeps the name.

        @interacts  one shape root.
        @deps       shape, assert_nodes.
        @complexity O(1).
        @alloc      one feed.
        """
        feed = self.shape(cards=[("r", "ghost")])
        nodes = by_id(feed)
        self.assertEqual(sorted(nodes), ["r"])
        self.assertEqual((nodes["r"]["level"], nodes["r"]["parent"], nodes["r"]["reports_to"]),
                         (0, None, "ghost"))
        self.assertIn({"from": "r", "to": "ghost", "kind": "reports_to"}, feed["links"])

    # Model: Claude Opus 5.5 (the BOARD fixer, round 1), 2026-10-14. Status: unreviewed.
    def test_inference_never_inverts_a_declared_edge(self):
        """b reports to the top node by card, which mails only b; b also mails x (D15).

        The top node is level 0 and b level 1 under it, with the names in
        either sort order: the top node is z, then a. Must reject rule 2
        with no D15 guard: with z, z is inferred under its own worker b
        (levels b 0, x 1, z 1). With a, the unguarded rule makes a cycle
        whose root is a, and a cycle's root carries no parent, so that
        order draws the same either way; z is the order that goes red.

        @interacts  two shape roots.
        @deps       shape, assert_nodes.
        @complexity O(1).
        @alloc      two feeds.
        """
        for top in ("z", "a"):
            with self.subTest(top=top):
                feed = self.shape(cards=[("b", top)], talks=[(top, "b"), ("b", "x")])
                self.assert_nodes(feed, {
                    top: ("orchestrator", "declared", 0, None),
                    "b": ("orchestrator", "inferred", 1, top),
                    "x": ("worker", "inferred", 2, "b"),
                })

    # Model: Claude Opus 5.5 (the P4 phase fixer), 2026-10-15. Status: unreviewed.
    def test_inference_never_closes_a_cycle_through_declared_edges(self):
        """top has a card and no parent, middle reports to top, bottom to middle; bottom mails both.

        top's one partner is bottom, whose card names middle, so rule 2's
        one-hop guard lets top be inferred under bottom, and that edge
        closes bottom, middle, top. It is taken out: top is the root,
        middle under it, bottom under middle, all declared, with no cycle
        badge (a level 0 node whose reports_to names a node) and no
        `orchestrator · inferred` on bottom. Run under all six orders of
        three names, so the order the names sort in never decides the
        drawing. Must reject the cycle break that cuts the first name's
        edge, declared or not, and roles read from the uncut edge.

        @interacts  six shape roots.
        @deps       shape, assert_nodes, itertools.
        @complexity O(1): six roots of three names.
        @alloc      six feeds.
        """
        for top, middle, bottom in itertools.permutations(("alpha", "mid", "zed")):
            with self.subTest(top=top, middle=middle, bottom=bottom):
                feed = self.shape(cards=[(top, None), (middle, top), (bottom, middle)],
                                  talks=[(bottom, middle), (top, bottom)])
                self.assert_nodes(feed, {
                    top: ("orchestrator", "declared", 0, None),
                    middle: ("orchestrator", "declared", 1, top),
                    bottom: ("worker", "declared", 2, middle),
                })
                ids = {node["id"] for node in feed["nodes"]}
                badged = [node["id"] for node in feed["nodes"] if node["level"] == 0
                          and node["reports_to"] in ids and node["reports_to"] != node["id"]]
                self.assertEqual(badged, [], "a root names a parent node: the page draws a cycle no card makes")

    # Model: Claude Opus 5.5 (the P4 phase fixer, round 2), 2026-10-15. Status: unreviewed.
    def test_one_message_between_siblings_leaves_both_under_their_relay(self):
        """a relays to b and c, trading RELAY_TRADES messages each way with each; b mails c once: b and c stay under a (D27).

        No cards. a holds 10 of b's 11 messages and 10 of c's 11, past
        PARENT_MAJORITY, and a is a hub, so both are a's inferred workers
        and a their inferred orchestrator. Must reject the old rule (a
        parent only for a node with exactly one partner): b's one message
        to c gives each two partners, and all three read as peers.

        @interacts  one shape root.
        @deps       shape, assert_nodes.
        @complexity O(1): 21 messages.
        @alloc      one feed.
        """
        feed = self.shape(talks=[("a", "b"), ("a", "c")] * RELAY_TRADES, notes=[("b", "c")])
        self.assert_nodes(feed, {
            "a": ("orchestrator", "inferred", 0, None),
            "b": ("worker", "inferred", 1, "a"),
            "c": ("worker", "inferred", 1, "a"),
        })

    # Model: Claude Opus 5.5 (the P4 phase fixer, round 2), 2026-10-15. Status: unreviewed.
    def test_a_worker_split_evenly_between_two_relays_gets_no_guess(self):
        """x trades one message each way with r1 and with r2, each a relay over two workers: x is a peer, role_source none (D27).

        Neither relay holds PARENT_MAJORITY of x's messages, so no parent
        is guessed. A peer is no guess: its role_source is `none`, and
        `inferred` is nowhere on its node. The relays' own workers, whose
        messages are all with their relay, are still guessed under them.
        Must reject a peer marked inferred.

        @interacts  one shape root.
        @deps       shape, assert_nodes, by_id.
        @complexity O(1).
        @alloc      one feed.
        """
        feed = self.shape(talks=[("r1", "w1"), ("r1", "w2"), ("r2", "w3"), ("r2", "w4"), ("x", "r1"), ("x", "r2")])
        self.assert_nodes(feed, {
            "x": ("peer", "none", 0, None),
            "r1": ("orchestrator", "inferred", 0, None),
            "w1": ("worker", "inferred", 1, "r1"),
            "w3": ("worker", "inferred", 1, "r2"),
        })
        x = by_id(feed)["x"]
        self.assertNotIn("inferred", json.dumps(x), f"a peer carries a guess: {x}")

    def test_two_orchestrators_share_a_worker(self):
        """b reports to a by card, and x also mails b: b once, at level 1 under a.

        The mailbox link between b and x stays in links. Must reject a
        shared worker drawn twice (shape() checks ids are unique) or hung
        under x, the parent it only mails.

        @interacts  one shape root.
        @deps       shape, assert_nodes.
        @complexity O(1).
        @alloc      one feed.
        """
        feed = self.shape(cards=[("b", "a"), ("a2", "a")],
                          talks=[("a", "b"), ("a", "a2"), ("x", "b"), ("x", "x1"), ("x", "x2")])
        self.assert_nodes(feed, {
            "a": ("orchestrator", "declared", 0, None),
            "b": ("worker", "declared", 1, "a"),
            "x": ("orchestrator", "inferred", 0, None),
        })
        pairs = [(link["from"], link["to"]) for link in feed["links"] if link["kind"] == "mailbox"]
        self.assertIn(("b", "x"), pairs)

    def test_links_read_every_message_not_only_the_wires(self):
        """A pair whose only messages are older than the last 50 still has its link.

        Must reject links taken from the last WIRE_HISTORY only.

        @interacts  writes 52 message files in a fresh TcRoot; one feed().
        @deps       _root.TcRoot, put_message, serve.Board.
        @complexity O(1): 52 files.
        @alloc      one TcRoot, removed on exit.
        """
        with _root.TcRoot() as root:
            put_message(root.path, 1, "old1", "old2")
            put_message(root.path, 2, "old2", "old1")
            for seq in range(3, 3 + WIRE_HISTORY):
                put_message(root.path, seq, *(("n1", "n2") if seq % 2 else ("n2", "n1")))
            feed = serve.Board(root=root.path).feed()
        self.assertEqual(len(feed["wires"]), WIRE_HISTORY)
        self.assertNotIn("old1", {wire["from"] for wire in feed["wires"]})
        old = [link for link in feed["links"] if link["kind"] == "mailbox" and link["from"] == "old1"]
        self.assertEqual(len(old), 1, f"no link for old1 and old2: {feed['links']}")
        self.assertEqual((old[0]["to"], old[0]["sent"]), ("old2", {"old1": 1, "old2": 1}))

    def test_reports_to_and_native_links(self):
        """b reports to a; a and b are claude on one account; c is codex on it too.

        links hold reports_to b to a and native a, b; no native link for c.

        @interacts  writes three cards in a fresh TcRoot; one feed().
        @deps       _root.TcRoot, write_card, serve.Board.
        @complexity O(1).
        @alloc      one TcRoot, removed on exit.
        """
        with _root.TcRoot() as root:
            write_card(root.path, "a")
            write_card(root.path, "b", reports_to="a")
            write_card(root.path, "c", kind="codex", route="codex", thread_id="t1")
            links = serve.Board(root=root.path).feed()["links"]
        self.assertEqual(links, [{"from": "b", "to": "a", "kind": "reports_to"},
                                 {"from": "a", "to": "b", "kind": "native"}])

    # Model: Claude Opus 5.5 (the BOARD fixer, round 1), 2026-10-14. Status: unreviewed.
    def test_no_native_link_on_account_unknown(self):
        """Two claude cards on account unknown get no native link; two on home get one (D15).

        The home pair is the control, so the test cannot pass by never
        making native links. Must reject a filter that drops only a missing
        account.

        @interacts  writes four cards in a fresh TcRoot; one feed().
        @deps       _root.TcRoot, write_card, serve.Board.
        @complexity O(1).
        @alloc      one TcRoot, removed on exit.
        """
        with _root.TcRoot() as root:
            for name in ("p", "q"):
                write_card(root.path, name, account=ACCOUNT_UNKNOWN)
            for name in ("m", "n"):
                write_card(root.path, name, account="home")
            links = serve.Board(root=root.path).feed()["links"]
        self.assertEqual([link for link in links if link["kind"] == "native"],
                         [{"from": "m", "to": "n", "kind": "native"}])


# Model: Claude Opus 5.5 (the P4 phase fixer), 2026-10-15. Status: unreviewed.
class InferencePropertyTest(unittest.TestCase):
    """serve.hierarchy over seeded random cards and mail: the cards always win.

    @interacts  none: the pure rule functions, no disk.
    @deps       serve.hierarchy, serve.parents_of, random.
    @complexity O(PROPERTY_CASES * n) over at most PROPERTY_NAMES_MAX names.
    @alloc      one case's dicts at a time.
    """

    def case(self, rng):
        """One random case: (names, cards, partners).

        Cards report only to a name earlier in a shuffled order, so the
        declared graph has no cycle. Mail runs between random names, and
        sometimes from OUTSIDER, a partner that is no node. `partners` is
        in feed()'s shape: {name: {partner: messages exchanged}}.

        @interacts  draws from `rng`.
        @deps       random.
        @complexity O(n) over n names.
        @alloc      three small dicts and sets, returned.
        """
        names = rng.sample(NAME_POOL, rng.randint(PROPERTY_NAMES_MIN, PROPERTY_NAMES_MAX))
        cards = {}
        for i, name in enumerate(names):
            if rng.random() < CARD_CHANCE:
                above = rng.choice(names[:i]) if i and rng.random() < REPORTS_CHANCE else None
                cards[name] = {"kind": "claude", "account": "work", "route": "local", "reports_to": above}
        partners = {}
        for _ in range(rng.randint(0, MAIL_PER_NAME * len(names))):
            sender, to = rng.choice(names + [OUTSIDER]), rng.choice(names)
            if sender != to:
                for one, other in ((sender, to), (to, sender)):
                    mine = partners.setdefault(one, {})
                    mine[other] = mine.get(other, 0) + 1
        return set(names), cards, partners

    def test_declared_edges_survive_any_mail_and_any_name_order(self):
        """Over PROPERTY_CASES seeded cases: every card's edge is drawn, no root claims a parent node, roles match the drawing, and reversing the names' order changes nothing.

        Must reject the cycle break that cuts a declared edge chosen by
        name order, and roles read from an edge the drawing does not use:
        both fail on the cases where an inferred edge closes a cycle, and
        at least CYCLES_BROKEN_MIN cases build that shape.

        @interacts  none.
        @deps       case, serve.hierarchy, serve.parents_of.
        @complexity O(PROPERTY_CASES * n).
        @alloc      one case at a time.
        """
        rng = random.Random(PROPERTY_SEED)
        flip = {c: NAME_POOL[-1 - i] for i, c in enumerate(NAME_POOL)}
        flip[OUTSIDER] = OUTSIDER
        broken = 0
        for number in range(PROPERTY_CASES):
            names, cards, partners = self.case(rng)
            where = f"case {number} of seed {PROPERTY_SEED}: cards {cards}, partners {partners}"
            parents, roles, levels = serve.hierarchy(names, cards, partners)
            if parents != serve.parents_of(names, cards, partners):
                broken += 1
            for name, card in cards.items():
                above = card["reports_to"]
                if above in names:
                    self.assertEqual(parents.get(name), (above, serve.DECLARED), where)
                    self.assertEqual(levels[name], levels[above] + 1, f"{name} is not drawn under {above}: {where}")
            for name in names:
                drawn = [x for x in names if x in parents and parents[x][0] == name and levels[x] == levels[name] + 1]
                if levels[name] > 0:
                    self.assertEqual(levels[name], levels[parents[name][0]] + 1, where)
                else:
                    above = cards.get(name, {}).get("reports_to")
                    self.assertFalse(above in names and above != name,
                                     f"root {name} reports to node {above}: a badge would name a cycle: {where}")
                self.assertEqual(roles[name][0] == serve.ORCHESTRATOR, bool(drawn),
                                 f"{name} reads {roles[name]} with {drawn} drawn under it: {where}")
            back = {flip[n]: n for n in names}
            fparents, froles, flevels = serve.hierarchy(
                {flip[n] for n in names},
                {flip[n]: {**c, "reports_to": flip.get(c["reports_to"])} for n, c in cards.items()},
                {flip[n]: {flip[m]: count for m, count in ms.items()} for n, ms in partners.items()})
            self.assertEqual({back[n]: (back[p], s) for n, (p, s) in fparents.items()}, parents,
                             f"the names' order changed the parents: {where}")
            self.assertEqual({back[n]: r for n, r in froles.items()}, roles, f"the names' order changed a role: {where}")
            self.assertEqual({back[n]: lv for n, lv in flevels.items()}, levels,
                             f"the names' order changed a level: {where}")
        self.assertGreaterEqual(broken, CYCLES_BROKEN_MIN,
                                f"only {broken} cases had an inferred edge on a cycle, so the property proves little")


# Model: Claude Opus 5.5 (the BOARD fixer, round 1), 2026-10-14. Status: unreviewed.
class HostileMailboxTest(unittest.TestCase):
    """Files in the mailbox that are not what the feed expects cost one poll nothing.

    @interacts  see the module block.
    @deps       _root.TcRoot, serve.Board, write_card, put_message.
    @complexity O(1) per test.
    @alloc      one TcRoot per test.
    """

    def test_a_card_nested_past_the_recursion_limit_is_skipped(self):
        """cards/deep.json nests too deep for json: feed() skips it and names it once on stderr.

        Must reject a read that misses RecursionError: every feed would
        fail, and the server would answer 500 until the file went.

        @interacts  two cards in a fresh TcRoot; two feed() calls with
                    stderr captured.
        @deps       _root.TcRoot, write_card, serve.Board, contextlib.
        @complexity O(NESTED_DEPTH) for the one json.loads per feed.
        @alloc      one TcRoot, removed on exit.
        """
        with _root.TcRoot() as root:
            write_card(root.path, "a")
            (root.path / "cards" / "deep.json").write_text("[" * NESTED_DEPTH)
            board = serve.Board(root=root.path)
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                first = board.feed()
                board.feed()
        self.assertEqual([node["id"] for node in first["nodes"]], ["a"])
        lines = err.getvalue().splitlines()
        self.assertEqual(len(lines), 1, f"stderr lines: {lines}")
        self.assertIn("cards/deep.json", lines[0])

    # Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
    def test_a_nested_card_is_named_escaped_on_stderr(self):
        """A nested card whose file name holds an escape sequence is named with it escaped.

        Anyone who can write to cards/ chooses the name, and serve.py's
        terminal would run the sequence. Must reject a raw print of the
        name: the ESC byte would reach stderr.

        @interacts  one card and one nested card in a fresh TcRoot; one
                    feed() with stderr captured.
        @deps       _root.TcRoot, write_card, serve.Board, contextlib.
        @complexity O(NESTED_DEPTH) for the one json.loads.
        @alloc      one TcRoot, removed on exit.
        """
        with _root.TcRoot() as root:
            write_card(root.path, "a")
            (root.path / "cards" / ESCAPE_CARD_NAME).write_text("[" * NESTED_DEPTH)
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                serve.Board(root=root.path).feed()
        lines = err.getvalue().splitlines()
        self.assertEqual(len(lines), 1, f"stderr lines: {lines!r}")
        self.assertNotIn("\x1b", lines[0], f"the escape reached stderr raw: {lines[0]!r}")
        self.assertIn(repr("cards/" + ESCAPE_CARD_NAME), lines[0])

    def test_one_bad_inbox_entry_skips_only_itself(self):
        """mail/to-loop is a link to itself; the messages between a and b still make wires and a link.

        Must reject a scan that drops every message when one to-* entry's
        stat fails.

        @interacts  two message files and one looping link in a fresh
                    TcRoot; one feed().
        @deps       _root.TcRoot, put_message, serve.Board.
        @complexity O(1).
        @alloc      one TcRoot, removed on exit.
        """
        with _root.TcRoot() as root:
            put_message(root.path, 1, "a", "b")
            put_message(root.path, 2, "b", "a")
            (root.path / "mail" / "to-loop").symlink_to("to-loop")
            feed = serve.Board(root=root.path).feed()
        self.assertEqual([(w["from"], w["to"]) for w in feed["wires"]], [("a", "b"), ("b", "a")])
        self.assertIn(("a", "b"), [(link["from"], link["to"]) for link in feed["links"]
                                   if link["kind"] == "mailbox"])

    def test_a_fifo_card_or_status_does_not_block_the_feed(self):
        """A FIFO at cards/pipe.json, then at status/a.md: feed() returns within 2 s each time.

        feed() runs in a daemon thread. If it blocks, the FIFO is opened for
        writing and closed, so the reader goes on and no thread is left.
        Must reject a plain open(), which waits for a writer while the
        server holds feed_lock.

        @interacts  one card and one FIFO in each of two fresh TcRoots; one
                    feed() in a daemon thread each.
        @deps       _root.TcRoot, write_card, serve.Board, release_fifo,
                    threading.
        @complexity O(1).
        @alloc      one TcRoot and one thread per case, both gone at its end.
        """
        for where in ("cards/pipe.json", "status/a.md"):
            with self.subTest(where=where), _root.TcRoot() as root:
                write_card(root.path, "a")
                fifo = root.path / where
                fifo.parent.mkdir(exist_ok=True)
                os.mkfifo(fifo)
                result = {}
                board = serve.Board(root=root.path)
                worker = threading.Thread(target=lambda: result.update(feed=board.feed()), daemon=True)
                worker.start()
                worker.join(FEED_CEILING_S)
                blocked = worker.is_alive()
                if blocked:
                    release_fifo(fifo)
                    worker.join(FEED_CEILING_S)
                self.assertFalse(blocked, f"feed() blocked on the FIFO at {where}")
                nodes = by_id(result["feed"])
                self.assertEqual(sorted(nodes), ["a"])
                self.assertIsNone(nodes["a"]["status"])

    def test_a_symlinked_status_or_card_is_not_followed(self):
        """status/a.md and cards/b.json are symlinks to files outside the mailbox: neither is read.

        Must reject a read that follows the link: a's status would show the
        outside file's line, and b would be a node.

        @interacts  one card, two outside files and two symlinks in a fresh
                    TcRoot; one feed().
        @deps       _root.TcRoot, write_card, serve.Board.
        @complexity O(1).
        @alloc      one TcRoot, removed on exit.
        """
        with _root.TcRoot() as root:
            write_card(root.path, "a")
            outside = root.base / "outside.md"
            outside.write_text("## a status, 2026-10-14T12:00:00-05:00\na line from outside the mailbox\n")
            outside_card = root.base / "outside.json"
            outside_card.write_text(json.dumps({"version": 1, "name": "b", "kind": "claude",
                                                "account": "work", "route": "local"}))
            (root.path / "status").mkdir(exist_ok=True)
            (root.path / "status" / "a.md").symlink_to(outside)
            (root.path / "cards" / "b.json").symlink_to(outside_card)
            feed = serve.Board(root=root.path).feed()
        nodes = by_id(feed)
        self.assertEqual(sorted(nodes), ["a"], "a symlinked card was read")
        self.assertIsNone(nodes["a"]["status"], "a symlinked status was read")

    # Model: Claude Opus 5.5 (the P4 phase fixer), 2026-10-15. Status: unreviewed.
    def test_a_message_that_vanishes_mid_poll_costs_one_retry_not_a_500(self):
        """tc's mailbox_summary raises FileNotFoundError once (a read moved a file): the feed asks again and answers.

        A stand-in in front of the real mailbox_summary raises the first
        time only, as a `tc read` between tc's glob and its stat makes it.
        A stand-in that raises every time still raises, once retried: a
        real fault is not hidden. Must reject a snapshot with no retry,
        which answers that poll 500.

        @interacts  one card and one message in a fresh TcRoot; two feed()
                    calls with board.tc.mailbox_summary swapped for a
                    stand-in.
        @deps       _root.TcRoot, write_card, put_message, serve.Board,
                    unittest.mock.
        @complexity O(1).
        @alloc      one TcRoot, removed on exit.
        """
        with _root.TcRoot() as root:
            write_card(root.path, "a")
            put_message(root.path, 1, "a", "b")
            board = serve.Board(root=root.path)
            real = board.tc.mailbox_summary
            calls = []

            def vanishes_once():
                """mailbox_summary, raising FileNotFoundError on its first call only.

                @interacts  see tc.mailbox_summary.
                @deps       none.
                @complexity tc.mailbox_summary's.
                @alloc      one entry in `calls`.
                """
                calls.append(1)
                if len(calls) == 1:
                    raise FileNotFoundError(2, "No such file or directory", "000001-from-a.md")
                return real()

            def always_vanishes():
                """mailbox_summary, raising FileNotFoundError every time.

                @interacts  none.
                @deps       none.
                @complexity O(1).
                @alloc      one entry in `calls`.
                """
                calls.append(1)
                raise FileNotFoundError(2, "No such file or directory", "000001-from-a.md")

            with mock.patch.object(board.tc, "mailbox_summary", vanishes_once):
                feed = board.feed()
            self.assertEqual(len(calls), 2, "the summary was not asked again")
            self.assertEqual(sorted(by_id(feed)), ["a", "b"])
            calls.clear()
            with mock.patch.object(board.tc, "mailbox_summary", always_vanishes):
                with self.assertRaises(FileNotFoundError):
                    board.feed()
            self.assertEqual(len(calls), 2, "a summary that keeps failing was asked other than twice")

    # Model: Claude Opus 5.5 (the P4 phase fixer), 2026-10-15. Status: unreviewed.
    def test_an_uncounted_inbox_reads_unknown_with_tc_s_reason(self):
        """unread None with a mail_problem passes through as null with the reason; a counted inbox with one does not.

        A tc that reads a shared mailbox gives `unread: None` and a
        `mail_problem` when it cannot count an inbox, and a `mail_problem`
        with a true count when it could not see only its read/; the board
        takes either shape. The reason rides in unread_problem
        only beside a null unread; a number keeps its number and no reason.
        A negative newest-mail age reads 0. Must reject a feed that turns an
        unknown count into 0, drops the reason, or calls a counted inbox
        unknown.

        @interacts  one feed() with Board.snapshot swapped for a stand-in.
        @deps       _root.TcRoot, serve.Board, unittest.mock.
        @complexity O(1).
        @alloc      one TcRoot, removed on exit.
        """
        mail = {"b": {"unread": None, "newest_mail_age_s": None, "mail_problem": MAIL_PROBLEM},
                "c": {"unread": 2, "newest_mail_age_s": NEGATIVE_AGE_S, "mail_problem": MAIL_PROBLEM},
                "d": {"unread": 0, "newest_mail_age_s": 7}}

        def stand_in():
            """A snapshot in Board.snapshot's shape with the three inboxes above.

            @interacts  none.
            @deps       none.
            @complexity O(1).
            @alloc      one small dict, returned.
            """
            return {"time": "2030-03-17T12:00:00-05:00",
                    "machine": {"load1": 0.0, "cores": 1, "mem_avail_pct": 50.0}, "listeners": {}, "mail": mail}

        with _root.TcRoot() as root:
            board = serve.Board(root=root.path, clock=FakeClock(FAKE_NOW))
            with mock.patch.object(board, "snapshot", stand_in):
                nodes = by_id(board.feed())
        self.assertEqual({name: (nodes[name]["unread"], nodes[name]["unread_problem"], nodes[name]["last_mail_age_s"])
                          for name in mail},
                         {"b": (None, MAIL_PROBLEM, None), "c": (2, None, 0), "d": (0, None, 7)})

    # Model: Claude Opus 5.5 (the P4 phase fixer), 2026-10-15. Status: unreviewed.
    def test_a_linked_inbox_read_folder_or_message_is_not_counted(self):
        """mail/to-ghost and mail/to-c/read are links to folders outside, and mail/to-b holds a link to a message: none counts.

        Each outside folder holds a well-named message (from x and from w),
        and the linked message is from y; none makes a wire or a link. The
        message a to b, a regular file, is the control. Must reject a scan
        that follows a linked folder or counts a link as a message: on a
        shared mailbox a group member could point the board at any folder
        the board's user can read.

        @interacts  one message, two outside folders, a file and three links
                    in a fresh TcRoot; one feed().
        @deps       _root.TcRoot, put_message, serve.Board.
        @complexity O(1).
        @alloc      one TcRoot, removed on exit.
        """
        with _root.TcRoot() as root:
            put_message(root.path, 1, "a", "b")
            mail = root.path / "mail"
            for folder, message in (("outside-box", "000002-from-x.md"), ("outside-read", "000003-from-w.md")):
                (root.base / folder).mkdir()
                (root.base / folder / message).write_text("hi\n")
            (root.base / "outside-message.md").write_text("hi\n")
            (mail / "to-ghost").symlink_to(root.base / "outside-box")
            (mail / "to-c").mkdir()
            (mail / "to-c" / "read").symlink_to(root.base / "outside-read")
            (mail / "to-b" / "000004-from-y.md").symlink_to(root.base / "outside-message.md")
            feed = serve.Board(root=root.path).feed()
        self.assertEqual([(w["from"], w["to"], w["seq"]) for w in feed["wires"]], [("a", "b", 1)])
        named = {link["from"] for link in feed["links"]} | {link["to"] for link in feed["links"]}
        self.assertEqual(named & {"x", "y", "w"}, set(), f"a linked folder or message was counted: {feed['links']}")

    # Model: Claude Opus 5.5 (the P4 phase fixer), 2026-10-15. Status: unreviewed.
    def test_a_message_in_both_the_inbox_and_read_counts_once(self):
        """000005-from-a.md in mail/to-b/ and in mail/to-b/read/ (a read moved it mid-scan): one wire, one sent.

        a sent it RECENT_SEND_S ago, so a reads writing. Must reject a scan
        that lists the moved message twice: two wires with one seq and a
        sent count one too high.

        @interacts  one card and the same message file twice in a fresh
                    TcRoot; one feed() on a fake clock.
        @deps       _root.TcRoot, write_card, put_message, age_file,
                    serve.Board.
        @complexity O(1).
        @alloc      one TcRoot, removed on exit.
        """
        with _root.TcRoot() as root:
            write_card(root.path, "a")
            for unread in (True, False):
                age_file(put_message(root.path, 5, "a", "b", unread=unread), FAKE_NOW - RECENT_SEND_S)
            feed = serve.Board(root=root.path, clock=FakeClock(FAKE_NOW)).feed()
        self.assertEqual([(w["from"], w["to"], w["seq"]) for w in feed["wires"]], [("a", "b", 5)])
        mailbox = [link for link in feed["links"] if link["kind"] == "mailbox"]
        self.assertEqual([link["sent"] for link in mailbox], [{"a": 1, "b": 0}])
        self.assertEqual(by_id(feed)["a"]["state"], "writing")

    # Model: Claude Opus 5.5 (the P4 phase fixer, round 2), 2026-10-15. Status: unreviewed.
    def test_a_hand_made_read_twin_cannot_hide_unread_mail(self):
        """b's waking message sits unread beside an old read/ twin of its name; c's beside a read/ file of its number from x.

        A stand-in snapshot names b and c listening, then none. Each got
        one message right after the sighting, still unread in its inbox;
        b's read/ also holds an old hand-made file of the same name, and
        c's an old one with the same number from another sender. Past
        WOKEN_GRACE_S both read woken: the unread message woke them and
        nothing read it, whatever read/ holds. b's message counts once;
        c's two files are two wires.

        Must reject the read/ copy winning the dedupe: b's twin would stand
        in for its mail, too old to be a wake, and b would read down.

        @interacts  five message files in a fresh TcRoot; two feed() calls
                    with Board.snapshot swapped for a stand-in.
        @deps       _root.TcRoot, put_message, age_file, snapshot_for,
                    serve.Board, unittest.mock.
        @complexity O(1).
        @alloc      one TcRoot, removed on exit.
        """
        names = ("b", "c")
        listening = {}
        with _root.TcRoot() as root:
            clock = FakeClock(FAKE_NOW)
            board = serve.Board(root=root.path, clock=clock)
            for seq, name in enumerate(names, start=1):
                age_file(put_message(root.path, seq, "a", name, unread=True), FAKE_NOW + 1)
            age_file(put_message(root.path, 1, "a", "b"), FAKE_NOW - OLD_SEND_S)
            age_file(put_message(root.path, 2, "x", "c"), FAKE_NOW - OLD_SEND_S)
            with mock.patch.object(board, "snapshot", snapshot_for(listening, names)):
                listening.update(dict.fromkeys(names, STAND_IN_PID))
                board.feed()
                listening.clear()
                clock.now = FAKE_NOW + 1 + WOKEN_GRACE_S + 1
                feed = board.feed()
        nodes = by_id(feed)
        self.assertEqual({name: nodes[name]["state"] for name in names}, {"b": "woken", "c": "woken"},
                         "a file in read/ hid or stood in for the unread mail that woke them")
        self.assertEqual(sorted((w["from"], w["to"], w["seq"]) for w in feed["wires"]),
                         [("a", "b", 1), ("a", "c", 2), ("x", "c", 2)])

    # Model: Claude Opus 5.5 (the P4 phase fixer, round 2), 2026-10-15. Status: unreviewed.
    def test_a_waking_message_moved_out_of_sight_is_still_read_evidence(self):
        """b's waking message leaves the inbox for read/by-hand-1-<name> (tc's clash rename): b reads working, its control c woken.

        A stand-in snapshot names b and c listening, then none. Each got a
        message right after the sighting. The first poll that finds them
        gone sees both in their inboxes. Then b's is moved where tc's read
        puts a message whose name read/ already holds, a name the board
        never matches; c's stays. Past WOKEN_GRACE_S, b reads working (the
        message that woke it left the inbox) and c woken.

        Must reject a wake looked for afresh each poll from the files in
        sight: b's waking message is gone from sight, so b would read down.

        @interacts  two message files, one renamed, in a fresh TcRoot; three
                    feed() calls with Board.snapshot swapped for a stand-in.
        @deps       _root.TcRoot, put_message, age_file, snapshot_for,
                    serve.Board, unittest.mock.
        @complexity O(1).
        @alloc      one TcRoot, removed on exit.
        """
        names = ("b", "c")
        listening = {}
        with _root.TcRoot() as root:
            clock = FakeClock(FAKE_NOW)
            board = serve.Board(root=root.path, clock=clock)
            waking = {}
            for seq, name in enumerate(names, start=1):
                waking[name] = put_message(root.path, seq, "a", name, unread=True)
                age_file(waking[name], FAKE_NOW + 1)
            with mock.patch.object(board, "snapshot", snapshot_for(listening, names)):
                listening.update(dict.fromkeys(names, STAND_IN_PID))
                board.feed()
                listening.clear()
                clock.now = FAKE_NOW + RECENT_SEND_S
                first = by_id(board.feed())
                read = waking["b"].parent / serve.READ_FOLDER
                read.mkdir()
                waking["b"].rename(read / f"{HAND_MOVED_PREFIX}{waking['b'].name}")
                clock.now = FAKE_NOW + 1 + WOKEN_GRACE_S + 1
                later = by_id(board.feed())
        self.assertEqual({name: first[name]["state"] for name in names}, {"b": "working", "c": "working"})
        self.assertEqual({name: later[name]["state"] for name in names}, {"b": "working", "c": "woken"},
                         "the waking message left b's inbox, yet b does not read as having read it")

    # Model: Claude Opus 5.5 (the P4 phase fixer, round 2), 2026-10-15. Status: unreviewed.
    def test_a_planted_old_file_with_a_high_number_does_not_end_the_wake_walk(self):
        """b's read/ holds an old hand-made file numbered 900 beside the real message that woke it: b reads working, then woken.

        A stand-in snapshot names b listening, then not. Its real waking
        message (number 1) landed right after the sighting; the planted one
        has a far higher number and an mtime long before. Inside the grace
        b reads working, past it woken, never down.

        Must reject a walk in number order that stops at the first old
        file: the planted one comes first and b would read down.

        @interacts  two message files in a fresh TcRoot; three feed() calls
                    with Board.snapshot swapped for a stand-in.
        @deps       _root.TcRoot, put_message, age_file, snapshot_for,
                    serve.Board, unittest.mock.
        @complexity O(1).
        @alloc      one TcRoot, removed on exit.
        """
        listening = {}
        with _root.TcRoot() as root:
            clock = FakeClock(FAKE_NOW)
            board = serve.Board(root=root.path, clock=clock)
            age_file(put_message(root.path, 1, "a", "b", unread=True), FAKE_NOW + 1)
            age_file(put_message(root.path, PLANTED_SEQ, "x", "b"), FAKE_NOW - OLD_SEND_S)
            with mock.patch.object(board, "snapshot", snapshot_for(listening, ("b",))):
                listening["b"] = STAND_IN_PID
                board.feed()
                listening.clear()
                clock.now = FAKE_NOW + RECENT_SEND_S
                grace = by_id(board.feed())["b"]["state"]
                clock.now = FAKE_NOW + 1 + WOKEN_GRACE_S + 1
                late = by_id(board.feed())["b"]["state"]
        self.assertEqual((grace, late), ("working", "woken"), "a planted old file with a high number hid b's wake")

    # Model: Claude Opus 5.5 (the P4 phase fixer), 2026-10-15. Status: unreviewed.
    def test_the_board_runs_tc_from_its_source_and_writes_no_bytecode_cache(self):
        """A Board leaves no __pycache__ beside tc, and a cache planted there with a matching header is never run.

        tc is copied into the harness's own temp folder (never next to the
        repo's tc), once with nothing beside it and once with a planted
        cache, built from code that sets PLANTED, whose header names the
        copy's mtime and size, as an import would check it. Must reject a
        load through an import's loader, which writes the cache in the
        first case and runs the planted code in the second.

        @interacts  two copies of tc and one planted .pyc in a fresh
                    TcRoot's temp folder; serve.TC_PATH patched for each
                    Board.
        @deps       _root.TcRoot, serve.Board, importlib.util, marshal,
                    shutil, unittest.mock.
        @complexity O(s) over s bytes of tc, compiled twice.
        @alloc      one TcRoot, removed on exit.
        """
        with _root.TcRoot() as root:
            loaded = {}
            for case in ("clean", "planted"):
                folder = root.base / f"tc-{case}"
                folder.mkdir()
                copy = folder / "tc"
                shutil.copy2(serve.TC_PATH, copy)
                if case == "planted":
                    cache = pathlib.Path(importlib.util.cache_from_source(str(copy)))
                    cache.parent.mkdir()
                    st = copy.stat()
                    words = (0, int(st.st_mtime) & PYC_WORD_MASK, st.st_size & PYC_WORD_MASK)
                    header = importlib.util.MAGIC_NUMBER + b"".join(w.to_bytes(PYC_WORD_BYTES, "little") for w in words)
                    cache.write_bytes(header + marshal.dumps(compile("PLANTED = True\n", str(copy), "exec")))
                with mock.patch.object(serve, "TC_PATH", copy):
                    loaded[case] = serve.Board(root=root.path).tc
            cached = (root.base / "tc-clean" / "__pycache__").exists()
        self.assertFalse(cached, "loading tc wrote a bytecode cache beside it")
        self.assertFalse(hasattr(loaded["planted"], "PLANTED"), "the board ran a planted bytecode cache")
        self.assertTrue(callable(getattr(loaded["planted"], "mailbox_summary", None)), "tc's own source did not run")
        self.assertEqual(loaded["clean"].ROOT, root.path)


if __name__ == "__main__":
    unittest.main()
