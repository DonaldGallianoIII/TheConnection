"""
Tests for board/serve.py's feed (C5): nodes and their states, listener
pids, wires, links, the status line, and the roles and levels of D7's
shapes. The feed never opens a message body: the main test makes every
body mode 000 and the feed still works.

Model:  Claude Opus 5.5 (the BOARD lane agent), 2026-10-14
Status: unreviewed

Cards are written by hand in C1's shape on every tree, with or without
CARDS' `tc join`: some are codex and ssh cards (a codex join needs a
Codex thread id in its environment, and an ssh card comes from `tc card`),
and writing every card one way
keeps each test the same on either tc. tests/board-browser-check.mjs is
the one that writes its cards with `tc join` when the tree's tc has it.
The main test sends its mail with real `tc send`, between names with no
card, so the file names the feed parses are tc's own. No test sends to a
name with a codex or ssh card: once CARDS' router is in tc, that send
rings `codex` or is refused. The shape tests write message files by hand
in tc's layout (`NNNNNN-from-<sender>.md` under `to-<name>/read/`, a .tmp
renamed, mail/.seq raised), and the feed reads only their names.

@interacts  runs ../tc through tests/_root.py under a throwaway TC_ROOT;
            starts two proven `tc wait` listeners and relies on the harness
            to kill them by their own pids. Loads board/serve.py as a
            module; each Board loads tc with TC_ROOT set to the test's root.
            Writes cards, status lines and message files in that root only.
@deps       python3 stdlib (contextlib, fcntl, importlib, io, json, os,
            pathlib, shlex, sys, threading, time, unittest, unittest.mock);
            tests/_root.py; board/serve.py; ../tc.
@complexity O(1) per test: at most 52 message files, 9 names, two
            listeners, and a few feed() calls, each O(n + m + e) in serve.py
            plus Board.snapshot's parts of tc's health (milliseconds, no
            GPU query). The D15 state test swaps the snapshot for a
            stand-in, so it starts no listener and no child. The GPU test
            puts a fake nvidia-smi on PATH and runs it once, through
            tc.machine_stats. The hostile mailbox tests make a FIFO, a
            looping link, a symlink and a card named with an escape
            sequence in their own root only.
@alloc      one TcRoot per test, removed when its context exits; the feeds
            are plain dicts dropped at the end of each test.
"""

import contextlib
import fcntl
import importlib.util
import io
import json
import os
import pathlib
import shlex
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


def put_message(root, seq, sender, to):
    """Write one read message the way tc lays one out, without tc's router; return its path.

    The file is mail/to-<to>/read/NNNNNN-from-<sender>.md, written to a
    .tmp sibling and renamed, and mail/.seq is raised to `seq` under its
    flock, as tc's send does. For mail to or from any name, including one
    whose card would route a real send elsewhere.

    @interacts  writes one message file and mail/.seq, making
                mail/to-<to>/read/ if needed.
    @deps       fcntl, pathlib.
    @complexity O(1).
    @alloc      the returned path.
    """
    mail = pathlib.Path(root) / "mail"
    folder = mail / f"to-{to}" / "read"
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

        A feed at the real time: both listeners sent inside the writing
        window, so both read writing and keep their pids (D15: writing
        comes first). First feed, its clock past the window: four nodes in
        states listening, listening, doorbell, remote; the pids are the
        harness's; three wires with the right from, to and seq. The feeds
        write nothing. Second feed on the same Board, 20 s later on its
        clock, after b's listener is killed: b is down. A new Board has
        seen nobody listening, so b is idle there.

        The three messages run between a and b only. Once CARDS' router is
        in tc, a send to a name with a codex card rings `codex` and one to
        an ssh card is refused until the SSH lane builds that route, so no
        test sends to cx or far; a card alone makes their nodes.

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

            clock = FakeClock(time.time())
            board = serve.Board(root=root.path, clock=clock)
            with root.listener("a", LISTENER_TIMEOUT_SECONDS) as pid_a:
                with root.listener("b", LISTENER_TIMEOUT_SECONDS) as pid_b:
                    clock.now = time.time()
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
        self.assertEqual(by_id(fresh)["b"]["state"], "idle",
                         "a new Board has seen nobody listening, so nothing is down")

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

    def shape(self, cards=(), talks=()):
        """Feed for a root with these cards and these exchanges; checks ids and parents.

        Every node is drawn once, and each parent is the one the walk used
        (check_parents_match_walk), in every shape.

        `cards` is (name, reports_to) pairs, each a claude card on one
        account. `talks` is (x, y) pairs: one message x to y and one y to
        x, both read, so both names have an inbox.

        @interacts  writes cards and message files in a fresh TcRoot; one
                    feed().
        @deps       _root.TcRoot, write_card, put_message, serve.Board,
                    check_parents_match_walk.
        @complexity O(c + t) over c cards and t exchanges.
        @alloc      one TcRoot, removed before return; the feed, returned.
        """
        with _root.TcRoot() as root:
            for name, reports_to in cards:
                write_card(root.path, name, reports_to=reports_to)
            seq = 0
            for x, y in talks:
                for sender, to in ((x, y), (y, x)):
                    seq += 1
                    put_message(root.path, seq, sender, to)
            feed = serve.Board(root=root.path).feed()
        ids = [node["id"] for node in feed["nodes"]]
        self.assertEqual(len(ids), len(set(ids)), f"a node is drawn twice: {ids}")
        check_parents_match_walk(self, feed)
        return feed

    def assertNodes(self, feed, expected):
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
        @deps       shape, assertNodes.
        @complexity O(1).
        @alloc      one feed.
        """
        feed = self.shape(cards=[("a", None), ("b", "a"), ("c", "a"), ("d", "a")])
        self.assertNodes(feed, {
            "a": ("orchestrator", "declared", 0, None),
            "b": ("worker", "declared", 1, "a"),
            "c": ("worker", "declared", 1, "a"),
            "d": ("worker", "declared", 1, "a"),
        })

    def test_chain_with_hints(self):
        """b reports to a; c and d to b: levels 0, 1, 2, 2; a and b orchestrators.

        @interacts  one shape root.
        @deps       shape, assertNodes.
        @complexity O(1).
        @alloc      one feed.
        """
        feed = self.shape(cards=[("a", None), ("b", "a"), ("c", "b"), ("d", "b")])
        self.assertNodes(feed, {
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
        @deps       shape, assertNodes.
        @complexity O(1).
        @alloc      one feed.
        """
        feed = self.shape(talks=[("a", "b"), ("b", "c"), ("b", "d")])
        self.assertNodes(feed, {
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
        @deps       shape, assertNodes.
        @complexity O(1).
        @alloc      one feed.
        """
        feed = self.shape(cards=[("x1", "x"), ("x2", "x")],
                          talks=[("x", "x1"), ("x", "x2"), ("y", "y1"), ("y", "y2"), ("x", "y")])
        self.assertNodes(feed, {
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
        @deps       shape, assertNodes.
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
        @deps       shape, assertNodes.
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
        @deps       shape, assertNodes.
        @complexity O(1).
        @alloc      two feeds.
        """
        for top in ("z", "a"):
            with self.subTest(top=top):
                feed = self.shape(cards=[("b", top)], talks=[(top, "b"), ("b", "x")])
                self.assertNodes(feed, {
                    top: ("orchestrator", "declared", 0, None),
                    "b": ("orchestrator", "inferred", 1, top),
                    "x": ("worker", "inferred", 2, "b"),
                })

    def test_two_orchestrators_share_a_worker(self):
        """b reports to a by card, and x also mails b: b once, at level 1 under a.

        The mailbox link between b and x stays in links. Must reject a
        shared worker drawn twice (shape() checks ids are unique) or hung
        under x, the parent it only mails.

        @interacts  one shape root.
        @deps       shape, assertNodes.
        @complexity O(1).
        @alloc      one feed.
        """
        feed = self.shape(cards=[("b", "a"), ("a2", "a")],
                          talks=[("a", "b"), ("a", "a2"), ("x", "b"), ("x", "x1"), ("x", "x2")])
        self.assertNodes(feed, {
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


if __name__ == "__main__":
    unittest.main()
