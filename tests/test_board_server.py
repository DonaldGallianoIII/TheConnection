"""
Tests for board/serve.py's server (C6): the token on /feed, the Host check,
GET and HEAD only, the static allow list, and a socket bound to 127.0.0.1.
Round 1 adds the whole-request deadline (a client that trickles one byte at
a time is dropped) and the cap on connections served at once.

Model:  Claude Opus 5.5 (the BOARD lane agent), 2026-10-14
Status: unreviewed

The server runs in this process, on a thread, on a port the OS picks
(port 0). This lane's tests/_root.py cannot start a script other than tc
as a child; the dev branch's can (start(argv=...), built for BOARD B2), so
once BOARD merges these tests could start serve.py as a child instead.

@interacts  starts one BoardServer per test on 127.0.0.1 and a free port,
            in a daemon thread, and shuts it down and closes its socket in
            cleanup. Its Board reads a throwaway TC_ROOT from
            tests/_root.py. Talks to it with http.client over loopback, and
            with raw sockets for the deadline and the cap. The deadline
            tests set serve.REQUEST_DEADLINE_S to SHORT_DEADLINE_S while
            they run; the cap test starts a second server of its own. The
            font test reads board/fonts/ to compare what it is served.
@deps       python3 stdlib (http.client, importlib, json, pathlib, socket,
            sys, threading, time, unittest, unittest.mock); tests/_root.py;
            board/serve.py; ../tc.
@complexity O(1) per test: a handful of requests, one or two of them a
            feed() of an empty mailbox (tens of ms each). The two deadline
            tests each wait out SHORT_DEADLINE_S once.
@alloc      one TcRoot, one server socket and one thread per test, all
            released in cleanup.
"""

import http.client
import importlib.util
import json
import pathlib
import socket
import sys
import threading
import time
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
# Run as `python3 -m unittest tests.test_board_server` from the repo root,
# tests/ is not on sys.path; under discover it is. Add it once so both work.
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import _root  # noqa: E402  (needs the path line above)

SERVE_PATH = HERE.parent / "board" / "serve.py"
# A made-up token: the server takes whatever it is given. Never a real one.
TOKEN = "made-up-test-token"
# A request to loopback answers in milliseconds; this is a ceiling only.
REQUEST_TIMEOUT_SECONDS = 10
# serve_forever() polls for shutdown every half second; this is a ceiling.
STOP_TIMEOUT_SECONDS = 5
# The loopback address C6 requires, written here, not read from serve.py.
LOOPBACK = "127.0.0.1"
# Model: Claude Opus 5.5 (the BOARD fixer, round 1), 2026-10-14. Status: unreviewed.
# A whole-request deadline short enough to wait out, set in place of
# serve.REQUEST_DEADLINE_S while a deadline test runs.
SHORT_DEADLINE_S = 1
# The trickling client sends one byte this often: far inside any per-read
# timeout, so only a deadline on the whole request can stop it.
TRICKLE_STEP_S = 0.2
# A request line that never ends: no newline, so the server cannot answer
# it and close for that reason instead of the deadline.
TRICKLE_BYTES = b"GET /" + b"x" * 64
# The server must close a stalled connection within the deadline plus this.
CLOSE_SLACK_S = 1
# How long the trickling client keeps at it before the test calls it a hang.
TRICKLE_CEILING_S = SHORT_DEADLINE_S + CLOSE_SLACK_S + 1
# The cap test's own server serves this many connections at once.
TEST_CAP = 2
# A connection past the cap is closed this fast, well under the deadline.
AT_ONCE_S = 0.5
# How often the test looks for a freed slot while it waits.
LOOK_STEP_S = 0.05
# Model: Claude Opus 5.5 (the P4 phase fixer), 2026-10-15. Status: unreviewed.
# board/fonts/: two faces in two subsets each, and one license per face.
FONT_FILES = 6


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


class ServerTest(unittest.TestCase):
    """One live server per test, on 127.0.0.1 and a free port.

    @interacts  see the module block.
    @deps       _root.TcRoot, serve.Board, serve.BoardServer, http.client.
    @complexity O(1) per test.
    @alloc      one TcRoot, socket and thread per test.
    """

    def setUp(self):
        """Start a BoardServer on port 0 over a throwaway root, serving on a thread.

        Cleanup runs in reverse: stop serve_forever and join its thread,
        close the socket, then remove the root.

        @interacts  creates a TcRoot; binds one socket; starts one thread.
        @deps       _root.TcRoot, serve.Board, serve.BoardServer, threading.
        @complexity O(1).
        @alloc      the root, the socket and the thread, released in cleanup.
        """
        root = _root.TcRoot()
        root.__enter__()
        self.addCleanup(root.__exit__, None, None, None)
        self.server = serve.BoardServer(serve.Board(root=root.path), 0, TOKEN)
        self.addCleanup(self.server.server_close)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)
        self.port = self.server.server_address[1]

    def stop(self):
        """Stop serve_forever and wait for its thread.

        @interacts  signals the server loop to end; joins the thread.
        @deps       threading.
        @complexity O(1).
        @alloc      none.
        """
        self.server.shutdown()
        self.thread.join(STOP_TIMEOUT_SECONDS)
        self.assertFalse(self.thread.is_alive(), "serve_forever did not stop")

    def ask(self, method, path, headers=None):
        """Send one request to the server; return (status, body bytes, response headers).

        http.client sends Host: 127.0.0.1:<port> unless `headers` sets one.

        @interacts  one loopback TCP connection, closed before return.
        @deps       http.client.
        @complexity O(b) over b bytes in the answer.
        @alloc      the body, returned.
        """
        conn = http.client.HTTPConnection(LOOPBACK, self.port, timeout=REQUEST_TIMEOUT_SECONDS)
        try:
            conn.request(method, path, headers=headers or {})
            answer = conn.getresponse()
            return answer.status, answer.read(), answer.headers
        finally:
            conn.close()

    def test_feed_needs_the_token(self):
        """/feed with no token or a wrong one: 401, no body. With it: 200 and C5's JSON.

        @interacts  three requests.
        @deps       ask.
        @complexity O(1).
        @alloc      three bodies.
        """
        self.assertEqual(self.ask("GET", "/feed")[:2], (401, b""))
        self.assertEqual(self.ask("GET", "/feed", {"X-TC-Token": TOKEN + "x"})[:2], (401, b""))
        status, body, headers = self.ask("GET", "/feed", {"X-TC-Token": TOKEN})
        self.assertEqual(status, 200, body)
        self.assertTrue(headers["Content-Type"].startswith("application/json"), headers["Content-Type"])
        self.assertEqual(sorted(json.loads(body)), ["at", "links", "machine", "nodes", "wires"])

    def test_a_foreign_host_gets_421(self):
        """Host: evil.example gets 421 even with the token; localhost:<port> is let in.

        Also 421: the right name on another port.

        @interacts  three requests.
        @deps       ask.
        @complexity O(1).
        @alloc      three bodies.
        """
        token = {"X-TC-Token": TOKEN}
        self.assertEqual(self.ask("GET", "/feed", {**token, "Host": "evil.example"})[:2], (421, b""))
        self.assertEqual(self.ask("GET", "/feed", {**token, "Host": f"{LOOPBACK}:{self.port + 1}"})[0], 421)
        self.assertEqual(self.ask("GET", "/feed", {**token, "Host": f"localhost:{self.port}"})[0], 200)

    def test_only_get_and_head(self):
        """POST, PUT, DELETE and a made-up method on /feed: 405. HEAD: 200 with no body.

        @interacts  five requests.
        @deps       ask.
        @complexity O(1).
        @alloc      five bodies.
        """
        token = {"X-TC-Token": TOKEN}
        for method in ("POST", "PUT", "DELETE", "FROB"):
            status, body, headers = self.ask(method, "/feed", token)
            self.assertEqual((status, body), (405, b""), method)
        status, body, headers = self.ask("HEAD", "/feed", token)
        self.assertEqual((status, body), (200, b""))

    def test_files_outside_the_allow_list_are_404(self):
        """/../tc, /mail/, /serve.py and / are 404; /look.js and /theme.css are served.

        @interacts  six requests; two read files in board/.
        @deps       ask.
        @complexity O(1).
        @alloc      six bodies.
        """
        for path in ("/../tc", "/mail/", "/serve.py", "/"):
            self.assertEqual(self.ask("GET", path)[:2], (404, b""), path)
        status, body, headers = self.ask("GET", "/look.js")
        self.assertEqual(status, 200)
        self.assertIn(b"export function", body)
        self.assertTrue(headers["Content-Type"].startswith("text/javascript"), headers["Content-Type"])
        self.assertEqual(self.ask("GET", "/theme.css")[0], 200)

    # Model: Claude Opus 5.5 (the P4 phase fixer), 2026-10-15. Status: unreviewed.
    def test_the_fonts_are_served_from_the_allow_list_and_nothing_beside_them(self):
        """Each face and license in board/fonts/ is served whole with its type (D26); the folder and its neighbors are 404.

        Must reject a server that leaves the fonts off the allow list (the
        page would ask another host for its faces, or draw without them),
        and one that joins a request's path under fonts/.

        @interacts  one request per font file and six refused paths; reads
                    board/fonts/.
        @deps       ask.
        @complexity O(1): six files, about 100 KB in all.
        @alloc      each body, dropped after its check.
        """
        fonts = SERVE_PATH.parent / "fonts"
        files = sorted(p.name for p in fonts.iterdir())
        self.assertEqual(len(files), FONT_FILES, f"board/fonts/ holds {files}")
        for name in files:
            status, body, headers = self.ask("GET", f"/fonts/{name}")
            self.assertEqual(status, 200, name)
            want = "font/woff2" if name.endswith(".woff2") else "text/plain"
            self.assertTrue(headers["Content-Type"].startswith(want), f"{name}: {headers['Content-Type']}")
            self.assertEqual(body, (fonts / name).read_bytes(), f"{name} was not served whole")
        for path in ("/fonts/", "/fonts", "/fonts/../serve.py", "/fonts/%2e%2e/serve.py",
                     f"/fonts/{files[0]}/..", "/fonts/missing.woff2"):
            self.assertEqual(self.ask("GET", path)[:2], (404, b""), path)

    def test_the_socket_is_bound_to_loopback_only(self):
        """The listening socket's address is 127.0.0.1.

        Must reject a server bound to 0.0.0.0.

        @interacts  reads the socket's own address.
        @deps       none.
        @complexity O(1).
        @alloc      none.
        """
        self.assertEqual(self.server.socket.getsockname()[0], LOOPBACK)


    # Model: Claude Opus 5.5 (the BOARD fixer, round 1), 2026-10-14. Status: unreviewed.
    def all_slots_free(self, server, cap, within):
        """True once none of `server`'s `cap` slots is held, looking for at most `within` s.

        A slot is held while a request thread runs, so all free means every
        request thread has ended.

        @interacts  takes and gives back the server's slots.
        @deps       time.
        @complexity O(cap) per look.
        @alloc      none.
        """
        end = time.monotonic() + within
        while True:
            taken = 0
            while taken < cap and server.slots.acquire(blocking=False):
                taken += 1
            for _ in range(taken):
                server.slots.release()
            if taken == cap:
                return True
            if time.monotonic() > end:
                return False
            time.sleep(LOOK_STEP_S)

    def test_a_trickling_client_is_dropped_at_the_deadline(self):
        """One byte every 0.2 s, never a full request line: the server closes it by the deadline.

        Its thread ends too: every slot is free again. Must reject a
        timeout per read, which restarts on every byte and holds the
        thread for as long as the client keeps trickling.

        @interacts  one raw loopback connection; serve.REQUEST_DEADLINE_S
                    patched for the test.
        @deps       socket, time, unittest.mock; all_slots_free.
        @complexity O(1): about SHORT_DEADLINE_S of trickling.
        @alloc      one socket, closed before return.
        """
        closed_after = None
        with mock.patch.object(serve, "REQUEST_DEADLINE_S", SHORT_DEADLINE_S):
            sock = socket.create_connection((LOOPBACK, self.port), timeout=TRICKLE_STEP_S)
            start = time.monotonic()
            try:
                for byte in TRICKLE_BYTES:
                    if time.monotonic() - start > TRICKLE_CEILING_S:
                        break
                    try:
                        sock.send(bytes([byte]))
                        if sock.recv(1) == b"":
                            closed_after = time.monotonic() - start
                            break
                    except socket.timeout:
                        continue
                    except OSError:
                        closed_after = time.monotonic() - start
                        break
            finally:
                sock.close()
        self.assertIsNotNone(closed_after, f"a trickling client held its connection past {TRICKLE_CEILING_S} s")
        self.assertLessEqual(closed_after, SHORT_DEADLINE_S + CLOSE_SLACK_S)
        self.assertTrue(self.all_slots_free(self.server, serve.MAX_CONNECTIONS, CLOSE_SLACK_S),
                        "the trickling client's thread outlived the deadline")

    def test_a_connection_past_the_cap_is_closed_at_once(self):
        """A server capped at 2: two idle connections hold it, and a third is closed at once.

        The two idle ones end by the deadline, and their slots come back.
        Must reject a server with no cap, which leaves the third open.

        @interacts  starts a second BoardServer on a free port in a daemon
                    thread, stopped and closed in cleanup; three raw
                    loopback connections; serve.REQUEST_DEADLINE_S patched.
        @deps       socket, threading, time, unittest.mock; all_slots_free.
        @complexity O(1): about SHORT_DEADLINE_S of waiting.
        @alloc      one server, one thread and three sockets, all released.
        """
        with mock.patch.object(serve, "REQUEST_DEADLINE_S", SHORT_DEADLINE_S):
            server = serve.BoardServer(self.server.board, 0, TOKEN, max_connections=TEST_CAP)
            self.addCleanup(server.server_close)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(thread.join, STOP_TIMEOUT_SECONDS)
            self.addCleanup(server.shutdown)
            port = server.server_address[1]
            held = [socket.create_connection((LOOPBACK, port), timeout=REQUEST_TIMEOUT_SECONDS)
                    for _ in range(TEST_CAP)]
            extra = socket.create_connection((LOOPBACK, port), timeout=AT_ONCE_S)
            try:
                try:
                    answer = extra.recv(1)
                except socket.timeout:
                    answer = None
                except OSError:
                    answer = b""
                self.assertEqual(answer, b"", f"a connection past the cap of {TEST_CAP} was held open")
                self.assertTrue(self.all_slots_free(server, TEST_CAP, SHORT_DEADLINE_S + CLOSE_SLACK_S),
                                "the idle connections held their slots past the deadline")
            finally:
                for sock in held + [extra]:
                    sock.close()


if __name__ == "__main__":
    unittest.main()
