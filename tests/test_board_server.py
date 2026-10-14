"""
Tests for board/serve.py's server (C6): the token on /feed, the Host check,
GET and HEAD only, the static allow list, and a socket bound to 127.0.0.1.

Model:  Claude Opus 5.5 (the BOARD lane agent), 2026-10-14
Status: unreviewed

The server runs in this process, on a thread, on a port the OS picks
(port 0). tests/_root.py in this tree has no way yet to start a script
other than tc as a child; a P0 fix adds one on its own branch.

@interacts  starts one BoardServer per test on 127.0.0.1 and a free port,
            in a daemon thread, and shuts it down and closes its socket in
            cleanup. Its Board reads a throwaway TC_ROOT from
            tests/_root.py. Talks to it with http.client over loopback.
@deps       python3 stdlib (http.client, importlib, json, pathlib, sys,
            threading, unittest); tests/_root.py; board/serve.py; ../tc.
@complexity O(1) per test: a handful of requests, one or two of them a
            feed() of an empty mailbox (tens of ms each).
@alloc      one TcRoot, one server socket and one thread per test, all
            released in cleanup.
"""

import http.client
import importlib.util
import json
import pathlib
import sys
import threading
import unittest

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

    def test_the_socket_is_bound_to_loopback_only(self):
        """The listening socket's address is 127.0.0.1.

        Must reject a server bound to 0.0.0.0.

        @interacts  reads the socket's own address.
        @deps       none.
        @complexity O(1).
        @alloc      none.
        """
        self.assertEqual(self.server.socket.getsockname()[0], LOOPBACK)


if __name__ == "__main__":
    unittest.main()
