"""
Leak tests for board/serve.py's feed: 1,000 feed() calls on one Board grow
its RSS by less than FEED_LEAK_LIMIT_KB and leave no file open, and
last_listening_at, and first_missing_at and wakes beside it, stay bounded
when 1,000 names come and go.

Model:  Claude Opus 5.5 (the BOARD lane agent), 2026-10-14
Status: unreviewed

RSS is read from VmRSS in /proc/self/status, the way the listener's flat
13 MB was measured. During the 1,000 calls PATH holds only a fake
`nvidia-smi` that prints one GPU line. feed() never runs it (serve.py's
Board.snapshot takes no GPU reading); one direct tc.machine_stats() call
proves the fake is found.

@interacts  one TcRoot with mail (sent by tc and written by hand), a card
            and one proven listener; one Board on it; os.environ["PATH"]
            patched for the run; reads /proc/self/status and lists
            /proc/self/fd. The second test swaps the Board's snapshot
            (Board.snapshot) for a stand-in that names one new listener
            per call.
@deps       python3 stdlib (gc, importlib, os, pathlib, sys, unittest,
            unittest.mock); tests/_root.py; board/serve.py; ../tc.
@complexity first test: 1,000 feed() calls over about 23 names and 43
            messages, each O(n + m + e) plus Board.snapshot's parts of tc's
            health (no child process). Second: 1,000 feed() calls over an
            empty mailbox, under a second in all.
@alloc      one TcRoot and one Board per test, released at its end.
"""

import gc
import importlib.util
import os
import pathlib
import sys
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
# Run as `python3 -m unittest tests.test_board_leak` from the repo root,
# tests/ is not on sys.path; under discover it is. Add it once so both work.
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import _root  # noqa: E402  (needs the path line above)

SERVE_PATH = HERE.parent / "board" / "serve.py"

# The ceiling on RSS growth over the run (phases.md B5). The run's mailbox
# is sized against it: see WORKERS.
FEED_LEAK_LIMIT_KB = 2048
# Workers that each trade one message with `a`. Sized so a leak shows: with
# 20, one feed is about 40 kB of Python objects, and a Board that kept each
# feed it built grew RSS by about 42 MB over 1,000 calls when measured by
# hand. With only three names it grew 1,536 kB and slipped under the limit.
WORKERS = 20
# Calls measured (phases.md B5), and calls made first so imports, regex
# compiles and the allocator's first arenas are not counted as growth.
FEED_CALLS = 1000
WARM_UP_CALLS = 50
# Long enough that the listener never times out on its own during the run.
LISTENER_TIMEOUT_SECONDS = 120
# C5's DOWN_WINDOW_S, written here, not read from serve.py.
DOWN_WINDOW_S = 600
# The fake clock's step between calls in the come-and-go test: 1,000 steps
# span 6,000 s, ten down windows, so a map that is never pruned keeps all
# 1,000 names while a pruned one keeps the last window's worth.
NAME_STEP_S = 6
# A pruned map holds the names seen within one window, plus the one seen now.
PRUNED_MAP_MAX = DOWN_WINDOW_S // NAME_STEP_S + 1
# A pid that is never checked: the stand-in snapshot only names it.
STAND_IN_PID = 4242
# The fake nvidia-smi: one GPU at 30 C and 5 %, in nvidia-smi's CSV form.
FAKE_GPU = "#!/bin/sh\necho '30, 5'\n"
FAKE_EXE_MODE = 0o700


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


def rss_kb():
    """This process's resident set, in kB, from VmRSS in /proc/self/status.

    @interacts  reads /proc/self/status.
    @deps       pathlib; Linux /proc.
    @complexity O(1): one small file.
    @alloc      the file's text, freed on return.
    """
    for line in pathlib.Path("/proc/self/status").read_text().splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1])
    raise AssertionError("no VmRSS line in /proc/self/status")


def open_fds():
    """How many file descriptors this process holds, from /proc/self/fd.

    @interacts  lists /proc/self/fd.
    @deps       os; Linux /proc.
    @complexity O(f) over f open descriptors (tens).
    @alloc      one list, freed on return.
    """
    return len(os.listdir("/proc/self/fd"))


class FeedLeakTest(unittest.TestCase):
    """feed() holds nothing across calls but the bounded down map.

    @interacts  see the module block.
    @deps       _root.TcRoot, serve.Board.
    @complexity see the module block.
    @alloc      one TcRoot per test.
    """

    def test_a_thousand_feeds_grow_rss_under_the_limit(self):
        """1,000 feed() calls on one Board: VmRSS grows less than 2,048 kB, no fd left open.

        The mailbox holds three sent messages, WORKERS more pairs written by
        hand in tc's layout (a .tmp renamed, mail/.seq raised once after), a codex card, a status line and one proven
        listener, so every branch of feed() runs each call. Must reject a
        Board that keeps what it builds: keeping each feed grew RSS about
        42 MB by hand.

        @interacts  three `tc send`, one `tc status`, 2 * WORKERS message
                    files, one listener; 1,050 feed() calls with PATH
                    patched to the fake GPU folder.
        @deps       _root.TcRoot, serve.Board, rss_kb, open_fds.
        @complexity O(FEED_CALLS) feeds over about 2 * WORKERS + 3 messages.
        @alloc      one TcRoot, removed on exit.
        """
        with _root.TcRoot() as root:
            gpu = root.base / "gpu"
            gpu.mkdir()
            (gpu / "nvidia-smi").write_text(FAKE_GPU)
            (gpu / "nvidia-smi").chmod(FAKE_EXE_MODE)
            (root.path / "cards").mkdir()
            (root.path / "cards" / "cx.json").write_text(
                '{"version": 1, "name": "cx", "kind": "codex", "route": "codex", "reports_to": "a"}')
            # Nothing is sent TO cx: its codex card would make tc's router
            # ring `codex`. Sending from it routes by the recipient alone.
            for sender, to in (("cx", "a"), ("a", "far"), ("far", "a")):
                code, out, err = root.tc("send", "--from", sender, "--to", to, "leak run")
                self.assertEqual(code, 0, f"tc send exited {code}: {err}")
            seq = 3
            for i in range(WORKERS):
                for sender, to in (("a", f"w{i}"), (f"w{i}", "a")):
                    seq += 1
                    folder = root.path / "mail" / f"to-{to}" / "read"
                    folder.mkdir(parents=True, exist_ok=True)
                    tmp = folder / f"{seq:06d}-from-{sender}.tmp"
                    tmp.write_text(f"# #{seq} from {sender} to {to}\n\nhi\n")
                    tmp.rename(tmp.with_suffix(".md"))
            (root.path / "mail" / ".seq").write_text(str(seq))
            code, out, err = root.tc("read", "a")
            self.assertEqual(code, 0, f"tc read exited {code}: {err}")
            code, out, err = root.tc("status", "a", "watching the leak run")
            self.assertEqual(code, 0, f"tc status exited {code}: {err}")
            with root.listener("a", LISTENER_TIMEOUT_SECONDS) as pid, \
                    mock.patch.dict(os.environ, {"PATH": str(gpu)}):
                board = serve.Board(root=root.path)
                for _ in range(WARM_UP_CALLS):
                    feed = board.feed()
                self.assertEqual({n["id"]: n["listener_pid"] for n in feed["nodes"]}.get("a"), pid)
                self.assertEqual(board.tc.machine_stats()["gpus"], [{"temp_c": 30, "util_pct": 5}],
                                 "the fake nvidia-smi did not run")
                del feed
                gc.collect()
                before, fds = rss_kb(), open_fds()
                for _ in range(FEED_CALLS):
                    board.feed()
                gc.collect()
                grew, fds_after = rss_kb() - before, open_fds()
        self.assertLess(grew, FEED_LEAK_LIMIT_KB, f"VmRSS grew {grew} kB over {FEED_CALLS} feed() calls")
        self.assertEqual(fds_after, fds, f"open fds went from {fds} to {fds_after}")

    def test_last_listening_at_is_pruned_past_the_down_window(self):
        """1,000 names each listen once, 6 s apart: no map of the Board's ever holds more than one window's worth.

        Each name is seen gone on the next call, so first_missing_at (D28)
        takes it then; it and wakes are pruned with last_listening_at.
        Must reject a last_listening_at that grows without bound: unpruned,
        it would hold all 1,000 names by the end; and so would
        first_missing_at, left out of the prune.

        @interacts  1,000 feed() calls over an empty mailbox, with
                    Board.snapshot swapped for a stand-in.
        @deps       _root.TcRoot, serve.Board, unittest.mock.
        @complexity O(FEED_CALLS * PRUNED_MAP_MAX) for the prune checks.
        @alloc      one TcRoot, removed on exit.
        """
        clock = {"now": 0.0}
        listening = {}

        def stand_in():
            """A stand-in for Board.snapshot naming only this call's listener.

            It returns Board.snapshot's four keys: time, machine (load1,
            cores, mem_avail_pct), listeners (this call's one name and
            pid) and mail (empty).

            @interacts  reads `listening`.
            @deps       none.
            @complexity O(1): one listener.
            @alloc      one small dict, returned.
            """
            return {"time": "2026-10-14T12:00:00-05:00",
                    "machine": {"load1": 0.0, "cores": 1, "mem_avail_pct": 50.0},
                    "listeners": dict(listening), "mail": {}}

        biggest = gone_most = 0
        with _root.TcRoot() as root:
            board = serve.Board(root=root.path, clock=lambda: clock["now"])
            with mock.patch.object(board, "snapshot", stand_in):
                for i in range(FEED_CALLS):
                    clock["now"] = i * NAME_STEP_S
                    listening.clear()
                    listening[f"n{i}"] = STAND_IN_PID
                    board.feed()
                    biggest = max(biggest, len(board.last_listening_at))
                    # Model: Claude Opus 5.5 (the P4 phase fixer, round 2), 2026-10-15. Status: unreviewed.
                    gone_most = max(gone_most, len(board.first_missing_at), len(board.wakes))
            held = dict(board.last_listening_at)
        self.assertLessEqual(biggest, PRUNED_MAP_MAX,
                             f"last_listening_at reached {biggest} names; one window holds {PRUNED_MAP_MAX}")
        self.assertLessEqual(gone_most, PRUNED_MAP_MAX,
                             f"first_missing_at or wakes reached {gone_most} names; one window holds {PRUNED_MAP_MAX}")
        self.assertGreater(gone_most, 0, "no name was ever seen gone, so the bound proves nothing")
        oldest = clock["now"] - DOWN_WINDOW_S
        self.assertTrue(all(seen >= oldest for seen in held.values()),
                        f"names older than {DOWN_WINDOW_S} s are still held")
        self.assertIn(f"n{FEED_CALLS - 1}", held)


if __name__ == "__main__":
    unittest.main()
