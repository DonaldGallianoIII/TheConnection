"""
Shared test harness for tc: a throwaway TC_ROOT, a runner, a proven
listener, and fake `ssh` and `codex` executables that record every call.

Model:  Claude Opus 5.5 (the GROUND lane agent), 2026-10-14
Status: unreviewed

Use it as a context manager. Everything it makes lives in one temporary
folder, removed when the context exits:

    with TcRoot() as root:
        code, out, err = root.tc("send", "--from", "a", "--to", "b", "hi")
        with root.listener("b", 30) as pid:
            ...                     # pid holds mail/.wait-b.lock right now
        folder, calls = root.fake_bin("codex", 0)
        path = f"{folder}{os.pathsep}{os.environ['PATH']}"
        root.tc("send", "--from", "a", "--to", "c", "hi", env={"PATH": path})
        calls()                     # [] when the fake never ran

Layout inside the temporary folder:
  root/                       TC_ROOT for every command run through this root
  listener-<name>-*.out       one listener's stdout and stderr
  fake-<name>-*/bin/<name>    a fake executable; put bin/ first on PATH
  fake-<name>-*/calls.jsonl   one JSON line per call: {"argv": [...], "stdin": "..."}

@interacts  runs ../tc as a subprocess under a TC_ROOT of its own, never the
            live mail/ or status/; inherited TC_* variables are dropped so
            the machine's own settings never reach a test. Reads
            /proc/locks to prove a listener. Starts `tc wait` children and
            kills each by its own pid. Writes fake executables that the
            code under test finds through PATH.
@deps       python3 stdlib (contextlib, json, os, pathlib, subprocess, sys,
            tempfile, time); Linux only (/proc/locks, flock); ../tc. No
            imports from tc itself, so a bug in tc's lock reading cannot
            hide a bug here.
@complexity tc(): O(1) plus the child. listener(): at most
            LOCK_CEILING_SECONDS / LOCK_POLL_SECONDS polls (100), each O(k)
            over k lines in /proc/locks (tens on a desktop). A fake's
            reader: O(c) over c recorded calls (single digits per test).
            Teardown: O(h) over h children this root started (one or two
            per test).
@alloc      one temporary folder per TcRoot, removed in __exit__ with
            everything in it. One Popen per listener, killed and reaped in
            the listener's own teardown, and again in __exit__ if a context
            was left open. Nothing is retained after __exit__.
"""

import contextlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time

TC = pathlib.Path(__file__).resolve().parent.parent / "tc"

# A tc command that runs longer than this is hung, not slow. The plan sets it.
DEFAULT_TC_TIMEOUT_SECONDS = 10
# How long a listener gets to take its lock. Python start-up plus tc's
# imports is well under 1 s; 5 s is the plan's ceiling, so a slow machine
# fails here with a message instead of a test hanging.
LOCK_CEILING_SECONDS = 5
# Gap between two reads of /proc/locks. 100 reads fit in the ceiling, and a
# test waits about one Python start-up, never a fixed sleep.
LOCK_POLL_SECONDS = 0.05
# SIGKILL cannot be caught, so a child still unreaped after this is stuck in
# the kernel. Fail loudly instead of hanging the suite.
REAP_CEILING_SECONDS = 5
# tc reads its settings from environment variables with this prefix.
TC_ENV_PREFIX = "TC_"
# /proc/locks columns: "1: FLOCK ADVISORY WRITE <pid> <maj>:<min>:<inode> 0 EOF".
# A blocked waiter's line has "->" in column 1, so it never matches FLOCK.
LOCKS_KIND_COLUMN = 1
LOCKS_PID_COLUMN = 4
LOCKS_FILE_COLUMN = 5
# Owner may read, write and run the fake. Nobody else needs to.
FAKE_EXE_MODE = 0o700

# The fake executable. It records its arguments (not the program name,
# which is its path in a temp folder and changes every run) and its stdin,
# then exits with the code it was given. It reads stdin to the end: tc()
# feeds /dev/null by default, so it only blocks if the code under test
# hands it a pipe it never closes.
FAKE_SCRIPT = """#!{python}
# A fake `{name}` written by tests/_root.py. It records each call and does nothing else.
import fcntl, json, sys
data = sys.stdin.buffer.read().decode("utf-8", "replace") if sys.stdin is not None else ""
line = json.dumps({{"argv": sys.argv[1:], "stdin": data}}) + "\\n"
with open({record!r}, "a", encoding="utf-8") as f:
    fcntl.flock(f, fcntl.LOCK_EX)
    f.write(line)
sys.exit({exit_code})
"""


class ListenerNotProven(AssertionError):
    """A listener that never held its lock. Raised as a test failure.

    @interacts  none; carries a message naming the pid, the lock and the
                listener's own output.
    @deps       none.
    @complexity O(1).
    @alloc      one message string.
    """


def flock_holders(path):
    """Pids holding an flock on `path` right now, read from /proc/locks.

    Reads the kernel's table instead of trying the lock, so checking never
    gets in a starting listener's way. A path that does not exist yet has
    no holders.

    @interacts  stats `path`; reads /proc/locks. Writes nothing.
    @deps       os, pathlib; Linux /proc/locks.
    @complexity O(k) over k lines in /proc/locks, tens on a desktop.
    @alloc      the table's lines and one set of pids, freed on return.
    """
    try:
        st = os.stat(path)
    except FileNotFoundError:
        return set()
    key = f"{os.major(st.st_dev):02x}:{os.minor(st.st_dev):02x}:{st.st_ino}"
    held = set()
    for line in pathlib.Path("/proc/locks").read_text().splitlines():
        cols = line.split()
        if (len(cols) > LOCKS_FILE_COLUMN and cols[LOCKS_KIND_COLUMN] == "FLOCK"
                and cols[LOCKS_FILE_COLUMN] == key):
            held.add(int(cols[LOCKS_PID_COLUMN]))
    return held


def _stop(proc):
    """Kill one child by its own pid and reap it, so no zombie is left.

    Safe to call twice: a child that already exited is only reaped.

    @interacts  sends SIGKILL to proc.pid and nothing else; never pkill.
    @deps       subprocess.
    @complexity O(1).
    @alloc      none.
    """
    if proc.poll() is None:
        proc.kill()
    proc.wait(timeout=REAP_CEILING_SECONDS)


class TcRoot:
    """A throwaway TC_ROOT and the tools that run tc against it.

    Attributes, set by __enter__: `base` (the temporary folder), `path`
    (TC_ROOT, inside base), `env` (the environment every child gets).

    @interacts  see the module block. Every command runs with TC_ROOT set
                to `path`, whatever the caller passes.
    @deps       tempfile, subprocess; ../tc.
    @complexity O(1) to enter; exit is O(h) over h children started.
    @alloc      one temporary folder and a list of children, both released
                in __exit__.
    """

    def __init__(self):
        """Set up empty fields; nothing exists until __enter__.

        @interacts  none.
        @deps       none.
        @complexity O(1).
        @alloc      an empty child list.
        """
        self._tmp = None
        self._children = []
        self.base = None
        self.path = None
        self.env = None

    def __enter__(self):
        """Make the temporary folder, TC_ROOT inside it, and a clean env.

        @interacts  creates one folder under the system temp folder. Reads
                    os.environ and copies it without TC_* variables.
        @deps       tempfile, os.
        @complexity O(e) over e environment variables (tens).
        @alloc      the folder and one env dict, released in __exit__.
        """
        self._tmp = tempfile.TemporaryDirectory(prefix="tc-test-")
        self.base = pathlib.Path(self._tmp.name)
        self.path = self.base / "root"
        self.path.mkdir()
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(TC_ENV_PREFIX)}
        self.env["TC_ROOT"] = str(self.path)
        return self

    def __exit__(self, *exc):
        """Kill and reap any child still running, then remove the folder.

        @interacts  SIGKILL to each child this root started that is still
                    running, by its own pid; removes the temporary folder.
        @deps       tempfile.
        @complexity O(h) over h children started (one or two per test),
                    plus the size of the folder.
        @alloc      frees everything __enter__ and the tools made.
        """
        try:
            for proc in self._children:
                _stop(proc)
        finally:
            self._tmp.cleanup()
        return False

    def tc(self, *args, stdin=None, env=None, timeout=DEFAULT_TC_TIMEOUT_SECONDS):
        """Run `tc *args` under this root. Return (exit, stdout, stderr).

        `stdin` is a string fed to tc, or /dev/null when None. `env` holds
        variables layered over this root's env (PATH for a fake, a TC_*
        setting); TC_ROOT always stays this root. A run past `timeout`
        raises subprocess.TimeoutExpired after killing the child.

        @interacts  runs [sys.executable, TC, *args] as a child and waits.
        @deps       subprocess; ../tc.
        @complexity O(1) plus the child's own work.
        @alloc      the env copy and the captured output, returned.
        """
        run_env = dict(self.env)
        run_env.update(env or {})
        run_env["TC_ROOT"] = str(self.path)
        feed = {"input": stdin} if stdin is not None else {"stdin": subprocess.DEVNULL}
        done = subprocess.run([sys.executable, str(TC), *args], env=run_env,
                              capture_output=True, text=True, timeout=timeout, **feed)
        return done.returncode, done.stdout, done.stderr

    @contextlib.contextmanager
    def listener(self, name, timeout):
        """Start `tc wait <name> --timeout <timeout>`; yield its pid once proven.

        Proven means /proc/locks shows that pid holding
        mail/.wait-<name>.lock. Polls every LOCK_POLL_SECONDS up to
        LOCK_CEILING_SECONDS, then raises ListenerNotProven. It also raises
        if the child exits first: a second listener for the name (exit 3),
        or mail already waiting (tc wait exits 0 at once). Teardown kills
        the pid and reaps it, even when the test kills it first.

        @interacts  starts one `tc wait` child; reads /proc/locks; writes
                    its output to listener-<name>-*.out in the temp folder.
        @deps       subprocess, tempfile, time; flock_holders.
        @complexity at most 100 polls, each O(k) over k lines in /proc/locks.
        @alloc      one Popen and one output file, both released in
                    teardown (the file with the folder).
        """
        lock = self.path / "mail" / f".wait-{name}.lock"
        with tempfile.NamedTemporaryFile(dir=self.base, prefix=f"listener-{name}-",
                                         suffix=".out", delete=False) as out:
            proc = subprocess.Popen([sys.executable, str(TC), "wait", name, "--timeout", str(timeout)],
                                    env=self.env, stdin=subprocess.DEVNULL,
                                    stdout=out, stderr=subprocess.STDOUT)
        self._children.append(proc)
        try:
            deadline = time.monotonic() + LOCK_CEILING_SECONDS
            while proc.pid not in flock_holders(lock):
                if proc.poll() is not None:
                    said = pathlib.Path(out.name).read_text()
                    raise ListenerNotProven(f"tc wait {name} (pid {proc.pid}) exited {proc.returncode} "
                                            f"without holding {lock}. It said: {said!r}")
                if time.monotonic() >= deadline:
                    raise ListenerNotProven(f"tc wait {name} (pid {proc.pid}) did not hold {lock} "
                                            f"within {LOCK_CEILING_SECONDS} s")
                time.sleep(LOCK_POLL_SECONDS)
            yield proc.pid
        finally:
            _stop(proc)

    def fake_bin(self, name, exit_code):
        """Write a fake `name` (codex or ssh) that records each call and exits `exit_code`.

        Returns (folder, calls). Put `folder` first on PATH. `calls()`
        returns one dict per call, in order: {"argv": the arguments after
        the program name, "stdin": what it read}. It returns [] when the
        fake never ran, so a test asserts the fake was called by asserting
        calls() is not empty.

        @interacts  writes fake-<name>-*/bin/<name> (mode 0700) in the temp
                    folder. The fake appends to fake-<name>-*/calls.jsonl.
        @deps       tempfile, json, sys.executable as the fake's interpreter.
        @complexity O(1) to write; calls() is O(c) over c recorded calls.
        @alloc      one folder holding the fake and its record, removed
                    with the temp folder.
        """
        home = pathlib.Path(tempfile.mkdtemp(dir=self.base, prefix=f"fake-{name}-"))
        folder = home / "bin"
        folder.mkdir()
        record = home / "calls.jsonl"
        exe = folder / name
        exe.write_text(FAKE_SCRIPT.format(python=sys.executable, name=name,
                                          record=str(record), exit_code=int(exit_code)))
        exe.chmod(FAKE_EXE_MODE)

        def calls():
            """Every call the fake recorded, oldest first; [] if it never ran.

            @interacts  reads calls.jsonl. Writes nothing.
            @deps       json.
            @complexity O(c) over c recorded calls.
            @alloc      one list of dicts, returned.
            """
            if not record.exists():
                return []
            return [json.loads(line) for line in record.read_text(encoding="utf-8").splitlines()]

        return folder, calls
