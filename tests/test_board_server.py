"""
Tests for board/serve.py's server (C6): the token on /feed, the Host check,
GET and HEAD only, the static allow list (the fonts too), and a socket
bound to 127.0.0.1; the whole-request deadline (a client that trickles one
byte at a time is dropped) and the cap on connections served at once;
every refusal with no body, http.server's own too; one stderr line, never
a traceback, for a client that hangs up mid-answer; `--port 80`
refused at start; and an empty or whitespace-only TC_ROOT refused at
start with tc's words and exit 9 (EMPTYROOT, Claude Opus 5.5,
unreviewed).

Model:  Claude Opus 5.5 (the BOARD lane agent), 2026-10-14
Status: unreviewed

The server runs in this process, on a thread, on a port the OS picks
(port 0), so a test can swap its Board's feed for a stand-in and move
serve.REQUEST_DEADLINE_S. EmptyRootStartTest starts serve.py as a child
with subprocess itself: tests/_root.py's start(argv=...) always sets
TC_ROOT to its root and keeps the test's working folder, and this test
needs an empty TC_ROOT and a working folder of its own.

@interacts  starts one BoardServer per test on 127.0.0.1 and a free port,
            in a daemon thread, and shuts it down and closes its socket in
            cleanup. Its Board reads a throwaway TC_ROOT from
            tests/_root.py. Talks to it with http.client over loopback, and
            with raw sockets for the deadline, the cap, the refusals
            http.server makes itself and a client that resets mid-answer
            (its feed swapped for a stand-in, stderr captured). The
            deadline tests set serve.REQUEST_DEADLINE_S to
            SHORT_DEADLINE_S while they run; the cap test starts a second
            server of its own. The font test reads board/fonts/ to compare
            what it is served. MainTest calls serve.main with Board and
            BoardServer swapped for stand-ins that fail if reached.
            EmptyRootStartTest starts serve.py twice as a child from an
            empty folder in a TcRoot's base, with TC_ROOT "" and "   ",
            waits up to REFUSE_CEILING_S each, kills a child still
            running by its own pid, and lists the folder after.
@deps       python3 stdlib (contextlib, http.client, io, json,
            pathlib, socket, struct, subprocess, sys, threading, time,
            unittest, unittest.mock); tests/_root.py (load_source loads serve.py
            with no bytecode cache, R30); board/serve.py; ../tc.
@complexity O(1) per test: a handful of requests, one or two of them a
            feed() of an empty mailbox (tens of ms each); one request line
            of REQUEST_LINE_MAX bytes and one answer of BIG_FEED_BYTES.
            The two deadline tests each wait out SHORT_DEADLINE_S once.
            EmptyRootStartTest: two children, each one compile of tc;
            a serve.py that does not refuse costs REFUSE_CEILING_S each.
@alloc      one TcRoot, one server socket and one thread per test, all
            released in cleanup; EmptyRootStartTest's two children,
            reaped and their pipes closed in cleanup.
"""

import contextlib
import http.client
import io
import json
import pathlib
import socket
import struct
import subprocess
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
# http.server's own limits, written here: a request line of more than
# this many bytes gets 414, and more than this many header lines 431.
REQUEST_LINE_MAX = 65536
HEADERS_MAX = 100
# How long the hang-up test waits for its request to reach the feed.
ENTER_CEILING_S = 5
# A feed answer this big cannot be sent whole to a client that is gone.
BIG_FEED_BYTES = 1 << 20
# SO_LINGER on and zero seconds: close() sends a reset, the way a page that
# goes away mid-answer can.
LINGER_RESET = (1, 0)
# http's own port: serve.py refuses it at start (a browser leaves it out of
# Host). argparse's exit code for a usage error.
HTTP_PORT = 80
ARGPARSE_USAGE_EXIT = 2
# EMPTYROOT (Claude Opus 5.5, unreviewed): a TC_ROOT set but naming no
# folder. Before this, serve.py took the working folder as the mailbox and
# served it.
EMPTY_ROOTS = {"empty": "", "spaces": "   "}
# tc's EXIT_USAGE (contract exit row 9), written here, not read from tc.
TC_EXIT_USAGE = 9
# The refusal is one compile of tc and one line, well under a second. A
# serve.py that does not refuse serves until killed, so this is how long
# the test waits before it calls that a failure and kills the child.
REFUSE_CEILING_S = 5
# How long the child gets to die after a kill by its own pid.
REAP_CEILING_S = 5
# Words the refusal must carry, tc's own: what is wrong, and the two ways out.
EMPTY_ROOT_WORDS = ("TC_ROOT is set but empty", "Unset it", "the mailbox's folder")
# The start of the line serve.py prints once it has bound its socket.
URL_LINE_START = "board: http"


def load_serve():
    """Load board/serve.py as a module named board_serve.

    R30 (Claude Opus 5.5, unreviewed): through _root.load_source, so no
    bytecode cache of serve.py is read or written.

    @interacts  executes serve.py's top level (constants and definitions).
                Writes no file.
    @deps       _root.load_source; SERVE_PATH.
    @complexity O(s) over s bytes of serve.py: one compile.
    @alloc      one module object, returned.
    """
    return _root.load_source("board_serve", SERVE_PATH)


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

    # Model: Claude Opus 5.5 (the P4 phase fixer), 2026-10-15. Status: unreviewed.
    def raw(self, data):
        """Send `data` over a raw loopback socket and return every byte the server sends back before it closes.

        Each request is exactly what http.server reads before it refuses,
        so nothing is left unread, and the server closes without a reset.

        @interacts  one loopback TCP connection, closed before return.
        @deps       socket.
        @complexity O(b) over b bytes each way.
        @alloc      the reply, returned.
        """
        with socket.create_connection((LOOPBACK, self.port), timeout=REQUEST_TIMEOUT_SECONDS) as sock:
            sock.sendall(data)
            chunks = []
            while True:
                chunk = sock.recv(REQUEST_LINE_MAX)
                if not chunk:
                    return b"".join(chunks)
                chunks.append(chunk)

    def test_every_refusal_has_no_body_http_server_s_own_too(self):
        """A bad request line (400), one too long (414), too many headers (431): each refused with no body.

        A version http.server does not speak (HTTP/2.0, 505) and a request
        line it reads as HTTP/0.9 (one word) get nothing at all: that
        version has no status line, and the board sends no body. Must
        reject http.server's own send_error, which writes an HTML page.

        @interacts  five raw loopback connections.
        @deps       raw.
        @complexity O(REQUEST_LINE_MAX) for the long line.
        @alloc      five replies.
        """
        long_line = b"GET /" + b"x" * (REQUEST_LINE_MAX + 1 - len(b"GET /"))
        for data, code in ((b"GET / / HTTP/1.0\r\n", 400), (long_line, 414),
                           (b"GET /feed HTTP/1.0\r\n" + b"X-Made-Up: 1\r\n" * (HEADERS_MAX + 1), 431)):
            with self.subTest(code=code):
                head, _, body = self.raw(data).partition(b"\r\n\r\n")
                self.assertTrue(head.startswith(f"HTTP/1.0 {code} ".encode()), head[:60])
                self.assertIn(b"Content-Length: 0", head)
                self.assertEqual(body, b"", f"a {code} refusal carries a body")
        for data in (b"GET /feed HTTP/2.0\r\n", b"GARBAGE\r\n"):
            with self.subTest(data=data):
                self.assertEqual(self.raw(data), b"", f"{data!r} got a reply with a body")

    def test_a_client_that_hangs_up_mid_answer_prints_one_line_and_no_traceback(self):
        """The page asks for /feed and resets the connection while the feed runs: one stderr line, no traceback.

        A stand-in feed waits until the client is gone, then answers
        BIG_FEED_BYTES, so writing the answer fails. Its slot comes back,
        which says the request thread ended. Must reject socketserver's own
        handle_error, which prints a traceback of a dozen lines.

        @interacts  one loopback connection reset by the client; the
                    server's Board.feed swapped for a stand-in; stderr
                    captured.
        @deps       socket, threading, contextlib, io, unittest.mock;
                    all_slots_free.
        @complexity O(BIG_FEED_BYTES).
        @alloc      one big answer, dropped by the server.
        """
        entered, go = threading.Event(), threading.Event()

        def stand_in():
            """A feed that waits for the client to go, then answers big.

            @interacts  sets `entered`; waits on `go`.
            @deps       threading.
            @complexity O(BIG_FEED_BYTES).
            @alloc      one big dict, returned.
            """
            entered.set()
            go.wait(REQUEST_TIMEOUT_SECONDS)
            return {"pad": "x" * BIG_FEED_BYTES}

        err = io.StringIO()
        with mock.patch.object(self.server.board, "feed", stand_in), contextlib.redirect_stderr(err):
            sock = socket.create_connection((LOOPBACK, self.port), timeout=REQUEST_TIMEOUT_SECONDS)
            sock.sendall(f"GET /feed HTTP/1.0\r\nHost: {LOOPBACK}:{self.port}\r\nX-TC-Token: {TOKEN}\r\n\r\n".encode())
            self.assertTrue(entered.wait(ENTER_CEILING_S), "the request never reached the feed")
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", *LINGER_RESET))
            sock.close()
            go.set()
            freed = self.all_slots_free(self.server, serve.MAX_CONNECTIONS, REQUEST_TIMEOUT_SECONDS)
        said = err.getvalue()
        self.assertTrue(freed, "the request thread never ended")
        self.assertNotIn("Traceback", said)
        self.assertEqual(said.splitlines(), ["serve.py: a client hung up before its answer was written"])

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


# Model: Claude Opus 5.5 (the P4 phase fixer), 2026-10-15. Status: unreviewed.
class MainTest(unittest.TestCase):
    """main()'s refusals at start, before anything is loaded or bound.

    @interacts  calls serve.main with Board and BoardServer swapped for
                stand-ins that fail if reached; stderr captured.
    @deps       serve.main, contextlib, io, unittest.mock.
    @complexity O(1).
    @alloc      none retained.
    """

    def test_port_80_is_refused_at_start_in_words(self):
        """`serve.py --port 80` exits 2 with words on stderr, before it loads tc or binds.

        A browser leaves port 80 out of its Host header, which the Host
        check refuses, so the board would refuse its own page. Must reject
        a main() that binds port 80 anyway.

        @interacts  one serve.main call.
        @deps       serve.main.
        @complexity O(1).
        @alloc      none retained.
        """
        reached = AssertionError("main() went past its usage check")
        err = io.StringIO()
        with mock.patch.object(serve, "Board", side_effect=reached), \
                mock.patch.object(serve, "BoardServer", side_effect=reached), \
                contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as stop:
            serve.main(["--port", str(HTTP_PORT)])
        self.assertEqual(stop.exception.code, ARGPARSE_USAGE_EXIT)
        self.assertIn(f"--port {HTTP_PORT}", err.getvalue())
        self.assertIn("Host header", err.getvalue())


# EMPTYROOT (Claude Opus 5.5, unreviewed): teardown for a serve.py child this file starts itself.
def stop_child(proc):
    """Kill `proc` by its own pid if it still runs, reap it, and close its pipes.

    @interacts  SIGKILL to proc.pid when proc.poll() is None; waits up to
                REAP_CEILING_S for it; closes its stdout and stderr.
    @deps       subprocess.
    @complexity O(1).
    @alloc      none retained.
    """
    if proc.poll() is None:
        proc.kill()
        proc.wait(timeout=REAP_CEILING_S)
    for pipe in (proc.stdout, proc.stderr):
        if pipe is not None:
            pipe.close()


# EMPTYROOT (Claude Opus 5.5, unreviewed): serve.py refuses an empty TC_ROOT as tc does.
class EmptyRootStartTest(unittest.TestCase):
    """`python3 board/serve.py` with TC_ROOT "" or "   " exits 9 with tc's words, binding nothing.

    @interacts  starts serve.py as a child from an empty working folder in
                a TcRoot's base, with TC_ROOT empty or spaces and --port 0,
                waits up to REFUSE_CEILING_S, and kills it by its own pid
                in cleanup if it still runs. Lists the folder after.
    @deps       subprocess, sys; _root.TcRoot; SERVE_PATH, stop_child.
    @complexity O(1): two children.
    @alloc      one TcRoot with a working folder; two children, reaped.
    """

    def test_an_empty_tc_root_refuses_before_anything_is_bound(self):
        """Each of "" and "   ": exit 9, tc's words in one stderr line, no URL, the working folder still empty.

        Must reject a serve.py that takes the working folder (or a folder
        named by the spaces under it) as the mailbox, binds and serves.

        @interacts  two serve.py children from one empty working folder.
        @deps       stop_child; EMPTY_ROOTS, EMPTY_ROOT_WORDS,
                    TC_EXIT_USAGE, REFUSE_CEILING_S, URL_LINE_START.
        @complexity O(1): two values; a child that serves costs
                    REFUSE_CEILING_S.
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            work = root.base / "work"
            work.mkdir()
            for label, value in EMPTY_ROOTS.items():
                proc = subprocess.Popen([sys.executable, str(SERVE_PATH), "--port", "0"],
                                        env=dict(root.env, TC_ROOT=value), cwd=work,
                                        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, text=True)
                self.addCleanup(stop_child, proc)
                try:
                    out, err = proc.communicate(timeout=REFUSE_CEILING_S)
                    code = proc.returncode
                except subprocess.TimeoutExpired:
                    proc.kill()
                    out, err = proc.communicate(timeout=REAP_CEILING_S)
                    code = f"still running after {REFUSE_CEILING_S} s"
                left = sorted(str(p.relative_to(work)) for p in work.rglob("*"))
                with self.subTest(root=label, check="exit"):
                    self.assertEqual(code, TC_EXIT_USAGE, f"stdout: {out!r}\nstderr: {err!r}")
                for words in EMPTY_ROOT_WORDS:
                    with self.subTest(root=label, check=words):
                        self.assertIn(words, err)
                with self.subTest(root=label, check="one line"):
                    self.assertEqual(len(err.splitlines()), 1, err)
                with self.subTest(root=label, check="no URL"):
                    self.assertNotIn(URL_LINE_START, out)
                with self.subTest(root=label, check="working folder empty"):
                    self.assertEqual(left, [], f"serve.py made {left} in the working folder")


if __name__ == "__main__":
    unittest.main()
