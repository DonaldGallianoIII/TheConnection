"""
Tests for board/serve.py's feed (C5): nodes and their states, listener
pids, wires, links, the status line, and the roles and levels of D7's
shapes. The feed never opens a message body: the main test makes every
body mode 000 and the feed still works.

Model:  Claude Opus 5.5 (the BOARD lane agent), 2026-10-14
Status: unreviewed

Cards are written by hand in C1's shape: CARDS' code is not in this tree.
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
@deps       python3 stdlib (fcntl, importlib, json, os, pathlib, sys,
            threading, time, unittest); tests/_root.py; board/serve.py; ../tc.
@complexity O(1) per test: at most 52 message files, 9 names, two
            listeners, and a few feed() calls, each O(n + m + e) in serve.py
            plus tc's health snapshot (tens of ms, most of it nvidia-smi
            when present).
@alloc      one TcRoot per test, removed when its context exits; the feeds
            are plain dicts dropped at the end of each test.
"""

import fcntl
import importlib.util
import json
import os
import pathlib
import sys
import threading
import time
import unittest

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
    """Write one read message the way tc lays one out, without tc's router.

    The file is mail/to-<to>/read/NNNNNN-from-<sender>.md, written to a
    .tmp sibling and renamed, and mail/.seq is raised to `seq` under its
    flock, as tc's send does. For mail to or from any name, including one
    whose card would route a real send elsewhere.

    @interacts  writes one message file and mail/.seq, making
                mail/to-<to>/read/ if needed.
    @deps       fcntl, pathlib.
    @complexity O(1).
    @alloc      none retained.
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


def by_id(feed):
    """{id: node} for a feed's nodes.

    @interacts  none.
    @deps       none.
    @complexity O(n) over n nodes.
    @alloc      one dict, returned.
    """
    return {node["id"]: node for node in feed["nodes"]}


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

        First feed: four nodes in states listening, listening, doorbell,
        remote; the pids are the harness's; three wires with the right
        from, to and seq. Both listeners sent mail inside the writing
        window, so this also pins listening over writing (pause BOARD-1).
        The feed writes nothing. Second feed on the same Board, 20 s
        later on its clock, after b's listener is killed: b is down. A new
        Board has seen nobody listening, so b is idle there.

        The three messages run between a and b only. Once CARDS' router is
        in tc, a send to a name with a codex card rings `codex` and one to
        an ssh card is refused until the SSH lane builds that route, so no
        test sends to cx or far; a card alone makes their nodes.

        Must reject a feed that opens message bodies: every body is mode
        000 before the first feed.

        @interacts  three `tc send`, two `tc read`; two listeners; three
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
                    first = board.feed()
                    after = every_path(root.path)
                clock.now += PAST_WRITING_S
                second = board.feed()
            fresh = serve.Board(root=root.path, clock=clock).feed()

        self.assertEqual(before, after, "feed() changed the root's file list")
        nodes = by_id(first)
        self.assertEqual(sorted(nodes), ["a", "b", "cx", "far"], json.dumps(first, indent=1))
        self.assertEqual({name: nodes[name]["state"] for name in nodes},
                         {"a": "listening", "b": "listening", "cx": "doorbell", "far": "remote"})
        self.assertEqual((nodes["a"]["listener_pid"], nodes["b"]["listener_pid"]), (pid_a, pid_b))
        self.assertEqual([(w["from"], w["to"], w["seq"]) for w in first["wires"]],
                         [("a", "b", 1), ("b", "a", 2), ("a", "b", 3)])
        for wire in first["wires"]:
            self.assertLessEqual(wire["age_s"], WRITING_WINDOW_S,
                                 f"wire {wire} is past the writing window, so listening "
                                 f"never had to beat writing")
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


class ShapesTest(unittest.TestCase):
    """D7's shapes through feed(): roles, role_source, levels, parents, links.

    @interacts  see the module block.
    @deps       _root.TcRoot, serve.Board, write_card, put_message.
    @complexity O(1) per test.
    @alloc      one TcRoot per test.
    """

    def shape(self, cards=(), talks=()):
        """Feed for a root with these cards and these exchanges; also checks ids are unique.

        `cards` is (name, reports_to) pairs, each a claude card on one
        account. `talks` is (x, y) pairs: one message x to y and one y to
        x, both read, so both names have an inbox.

        @interacts  writes cards and message files in a fresh TcRoot; one
                    feed().
        @deps       _root.TcRoot, write_card, put_message, serve.Board.
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

    def test_a_node_below_a_cycle_stays_below_it(self):
        """p and q report to each other, and a reports to q: a hangs under q at level 2.

        a sorts before p and q but is not on the cycle, so it never becomes
        the root that breaks it (assumption in the BOARD handoff).

        @interacts  one shape root.
        @deps       shape, assertNodes.
        @complexity O(1).
        @alloc      one feed.
        """
        feed = self.shape(cards=[("p", "q"), ("q", "p"), ("a", "q")])
        nodes = by_id(feed)
        self.assertEqual({name: (nodes[name]["level"], nodes[name]["parent"]) for name in nodes},
                         {"p": (0, "q"), "q": (1, "p"), "a": (2, "q")})

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


if __name__ == "__main__":
    unittest.main()
