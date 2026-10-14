"""
Shared test harness for tc: a throwaway TC_ROOT, a runner, a background
runner, a proven listener, and fake `ssh` and `codex` executables that
record every call. A bare `ssh` or `codex` found through PATH is refused;
an absolute path such as /usr/bin/ssh skips PATH and is not caught. The
plan's code calls both by name (contracts C2 and C3).

Model:  Claude Opus 5.5 (the GROUND lane agent), 2026-10-14
Status: unreviewed

Use it as a context manager. Everything it makes lives in one temporary
folder, removed when the context exits:

    with TcRoot() as root:
        code, out, err = root.tc("send", "--from", "a", "--to", "b", "hi")
        with root.listener("c", 30) as pid:
            ...                     # pid holds mail/.wait-c.lock right now
        folder, calls = root.fake_bin("codex", 0)  # first on every later child's PATH
        root.tc("send", "--from", "a", "--to", "d", "hi")
        calls()                     # [] when the fake never ran
        proc = root.start("send", "--from", "a", "--to", "b", stdin="hi")
        out, err = proc.communicate(timeout=10)    # or leave it: teardown kills it
        root.tc("peek", "b", env={"CLAUDECODE": "1", "HOME": None})  # None unsets HOME
        server = root.start(argv=[sys.executable, "board/serve.py"])  # any argv, same env and teardown

Layout inside the temporary folder:
  root/                       TC_ROOT for every command run through this root
  refuse/ssh, refuse/codex    refusing stubs, first on every child's PATH
  listener-<name>-*.out       one listener's stdout and stderr
  start-stdin-*               the stdin text of one start() child
  fake-<name>-*/bin/<name>    a fake: a /bin/sh wrapper, on PATH ahead of refuse/
  fake-<name>-*/fake.py       the fake's recorder, run by the wrapper
  fake-<name>-*/calls.jsonl   one JSON line per call: {"argv": [...], "stdin": "..."}
  fake-<name>-*/calls.count   how many calls the fake has taken, one integer

@interacts  runs ../tc as a subprocess under a TC_ROOT of its own, never the
            live mail/ or status/. No child gets an inherited TC_* variable
            or any of the eight in CHILD_ENV_DROP, so the machine's tc
            settings, the session identity C1 reads, the native path's
            secrets and the ssh agent never reach a test. Everything else
            inherited passes through (HOME, PATH, LANG, a Claude session's
            other CLAUDE_CODE_* flags). Every child's
            PATH starts with refusing `ssh` and `codex` stubs, so a test
            without a fake fails instead of running the real tool. Only a
            PATH folder whose real path (os.path.realpath) sits inside the
            temp folder goes ahead of the stubs, so a symlink or a `..` in
            an entry cannot put a real tool first. An absolute path such as
            /usr/bin/ssh skips PATH and is not caught; the plan's code
            calls ssh and codex by name (contracts C2, C3). Reads
            /proc/locks to prove a listener. Starts `tc wait` and start()
            children (tc, or the argv a test gives start()) and kills each
            by its own pid. Writes fake executables that the code under
            test finds through PATH.
@deps       python3 stdlib (contextlib, json, os, pathlib, re, shlex,
            subprocess, sys, tempfile, time); /bin/sh for the stubs and the
            fakes' wrappers; Linux only (/proc/locks, flock); ../tc. No
            imports from tc itself, so a bug in tc's lock reading cannot
            hide a bug here.
@complexity Entering, and building one child's env: O(e + p) over e
            environment variables (tens) and p PATH entries (tens). tc()
            and start(): that, plus the child. listener(): one glob of the
            name's inbox, O(u) over u unread files (0 when it goes on), then
            at most P = LOCK_CEILING_SECONDS / LOCK_POLL_SECONDS = 100 reads
            of /proc/locks, each O(k) over k lines (tens on a desktop). One
            call of a fake: O(s) over s bytes of its own stdin, to record
            it; numbering it reads one counter, O(1) in earlier calls. Its
            reader, calls(), is O(B) over B bytes recorded, every call's
            stdin included (a few KB at planned loads).
            Teardown: O(h) over h children this root started, up to about
            50 (CORE K3's senders through start()). Every child gets
            SIGKILL first, then every reap shares one deadline, so h stuck
            children cost one REAP_CEILING_SECONDS in all, not h of them.
@alloc      one temporary folder per TcRoot, removed in __exit__ with
            everything in it. One Popen per listener and per start(). A
            listener's is dropped from the child list, killed and reaped in
            its own teardown; __exit__ kills and reaps the rest, then clears
            the child list and the env copy. Nothing is retained after
            __exit__.
"""

import contextlib
import json
import os
import pathlib
import re
import shlex
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
# Gap between two reads of /proc/locks. The deadline is checked before each
# read, so at most 100 reads fit in the ceiling, and a test waits about one
# Python start-up, never a fixed sleep.
LOCK_POLL_SECONDS = 0.05
# SIGKILL cannot be caught, so a child still unreaped after this is stuck in
# the kernel. Fail loudly instead of hanging the suite.
REAP_CEILING_SECONDS = 5
# tc reads its settings from environment variables with this prefix.
TC_ENV_PREFIX = "TC_"
# Dropped from every child's environment, besides every TC_* variable.
# C1's five identity variables: a child must not pass for the session that
# runs the tests, and a test of "no identity at all" must be buildable. The
# native path's socket and secret: no child of a test holds them. The ssh
# agent: no child of a test can reach the owner's keys.
CHILD_ENV_DROP = (
    "CODEX_THREAD_ID",
    "CLAUDECODE",
    "CLAUDE_CODE_SESSION_ID",
    "CLAUDE_PID",
    "CLAUDE_CONFIG_DIR",
    "CLAUDE_CODE_MESSAGING_SOCKET",
    "CLAUDE_CODE_MESSAGING_TOKEN",
    "SSH_AUTH_SOCK",
)
# Tools no agent runs for real (rule 5). A refusing stub for each sits first
# on every child's PATH, behind only the fakes a test writes.
REFUSED_TOOLS = ("ssh", "codex")
# What a refusing stub exits with. tc's own codes stop at 9 (contracts.md),
# ssh fails with 255 and a shell with 126 or 127, so 97 means one thing: a
# test reached a real tool's name with no fake in front of it.
REFUSED_EXIT_CODE = 97
# /proc/locks columns: "1: FLOCK ADVISORY WRITE <pid> <maj>:<min>:<inode> 0 EOF".
# A blocked waiter's line has "->" in column 1, so it never matches FLOCK.
LOCKS_KIND_COLUMN = 1
LOCKS_PID_COLUMN = 4
LOCKS_FILE_COLUMN = 5
# Owner may read, write and run a stub or a fake. Nobody else needs to.
FAKE_EXE_MODE = 0o700
# A fake's name becomes a file name and goes into a comment line of each
# generated script, so it is one plain lowercase word of at most 32
# characters: no path separator, no newline, nothing a shell reads. Matched
# with fullmatch, because `$` would also match before a trailing newline.
FAKE_NAME_PATTERN = re.compile(r"[a-z][a-z0-9-]{0,31}")

# A refusing stub. Its shebang is a fixed path, so nothing about this
# machine's Python reaches the kernel's shebang parser.
REFUSE_STUB = """#!/bin/sh
# Written by tests/_root.py: a test reached `{name}` with no fake in front of this stub.
echo {message} >&2
exit {code}
"""

# A fake's wrapper. The kernel splits a shebang line at its first space, so
# the interpreter's path never goes there: the shebang is a fixed /bin/sh,
# and the interpreter and the recorder are quoted words on the exec line.
FAKE_WRAPPER = """#!/bin/sh
# A fake `{name}` written by tests/_root.py. It runs its recorder, beside bin/.
exec {python} {script} "$@"
"""

# A fake's recorder. It records its arguments (not the program name, which
# is its path in a temp folder and changes every run) and its stdin, writes
# its stderr text, and exits with this call's code: call n (from 0) takes
# CODES[n], and the last code repeats. It numbers the call from a counter
# file read and rewritten under the record's flock, so overlapping calls
# still take their codes in order, and numbering a call never reads the
# earlier calls' stdin. A counter that is there but empty raises instead of
# restarting at 0. It reads stdin to the end: tc() feeds /dev/null by
# default, so it only blocks if the code under test hands it a pipe it
# never closes.
FAKE_SCRIPT = """# The recorder of a fake `{name}`, written by tests/_root.py. It records each call and does nothing else.
import fcntl
import json
import sys

CODES = {codes!r}
STDERR = {stderr!r}

data = sys.stdin.buffer.read().decode("utf-8", "replace") if sys.stdin is not None else ""
line = json.dumps({{"argv": sys.argv[1:], "stdin": data}}) + "\\n"
with open({record!r}, "a", encoding="utf-8") as f:
    fcntl.flock(f, fcntl.LOCK_EX)
    try:
        with open({count!r}, encoding="ascii") as c:
            call = int(c.read())
    except FileNotFoundError:
        call = 0
    f.write(line)
    f.flush()
    with open({count!r}, "w", encoding="ascii") as c:
        c.write(str(call + 1))
sys.stderr.write(STDERR)
sys.exit(CODES[min(call, len(CODES) - 1)])
"""


class ListenerNotProven(AssertionError):
    """A listener that never held its lock. Raised as a test failure.

    @interacts  none; carries a message naming the pid, the lock and the
                listener's own output, or why no listener was started.
    @deps       none.
    @complexity O(1).
    @alloc      one message string.
    """


class ChildNotReaped(RuntimeError):
    """Children still unreaped REAP_CEILING_SECONDS after SIGKILL.

    Raised once, after teardown has tried every child, naming each one that
    timed out.

    @interacts  none; carries a message naming each pid and its command.
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


def _kill(proc):
    """Send SIGKILL to one child by its own pid, if it still runs. No reap.

    Popen.kill checks the child first, so a child already reaped gets no
    signal, and its pid, which the kernel may have handed to another
    process, is never signaled.

    @interacts  sends SIGKILL to proc.pid and nothing else; never pkill.
    @deps       subprocess.
    @complexity O(1).
    @alloc      none.
    """
    if proc.poll() is None:
        proc.kill()


def _stop(proc, deadline=None):
    """Kill one child by its own pid, reap it by `deadline`, and close its pipes.

    `deadline` is a time.monotonic() value. None gives this child
    REAP_CEILING_SECONDS of its own, from now; __exit__ passes one deadline
    shared by all its children. Safe to call twice: a child that already
    exited is only reaped, and a deadline already past still reaps a child
    that has exited. Raises subprocess.TimeoutExpired if the child is still
    unreaped at the deadline; its pipes are closed either way.

    @interacts  sends SIGKILL to proc.pid and nothing else (_kill); never
                pkill.
    @deps       subprocess, time; _kill.
    @complexity O(1).
    @alloc      releases the child's pipes, if it has any.
    """
    try:
        _kill(proc)
        if deadline is None:
            deadline = time.monotonic() + REAP_CEILING_SECONDS
        proc.wait(timeout=max(0.0, deadline - time.monotonic()))
    finally:
        for pipe in (proc.stdin, proc.stdout, proc.stderr):
            if pipe is not None:
                pipe.close()


def _report_unreaped(procs, in_flight):
    """Raise one ChildNotReaped naming every child in `procs`; nothing if empty.

    A cleanup failure never replaces the test's own exception: when
    `in_flight` is true (an exception is already on its way out), the same
    message goes to stderr instead, and the caller's exception carries on.

    @interacts  writes one line to stderr when `in_flight`; else raises.
    @deps       shlex, sys.
    @complexity O(h) over h children in `procs`, up to about 50 (CORE K3).
    @alloc      one message string.
    """
    if not procs:
        return
    named = "; ".join(f"pid {p.pid} ({shlex.join(str(a) for a in p.args)})" for p in procs)
    message = (f"{len(procs)} child(ren) still unreaped {REAP_CEILING_SECONDS} s "
               f"after SIGKILL: {named}")
    if in_flight:
        print(f"tests/_root.py: {message}", file=sys.stderr)
        return
    raise ChildNotReaped(message)


class TcRoot:
    """A throwaway TC_ROOT and the tools that run tc against it.

    Attributes, set by __enter__: `base` (the temporary folder), `path`
    (TC_ROOT, inside base), `env` (the environment every child gets: the
    inherited one without TC_* or CHILD_ENV_DROP, TC_ROOT set to `path`,
    PATH starting with the refusing stubs; fake_bin() puts its folder in
    front of them).

    @interacts  see the module block. Every command runs with TC_ROOT set
                to `path`, whatever the caller passes.
    @deps       tempfile, subprocess, shlex; ../tc; /bin/sh.
    @complexity O(e + p) to enter, over e environment variables and p PATH
                entries (tens each). Exit is O(h) over h children started,
                up to about 50 (CORE K3), and waits at most one
                REAP_CEILING_SECONDS in all (see __exit__).
    @alloc      one temporary folder, the env dict and a list of children;
                __exit__ removes the folder and clears the dict and the list.
    """

    def __init__(self):
        """Set up empty fields; nothing exists until __enter__.

        @interacts  none.
        @deps       none.
        @complexity O(1).
        @alloc      an empty child list.
        """
        self._tmp = None
        self._refuse = None
        self._children = []
        self.base = None
        self.path = None
        self.env = None

    def __enter__(self):
        """Make the temporary folder, TC_ROOT, the refusing stubs, and a clean env.

        @interacts  creates one folder under the system temp folder, with
                    root/ and refuse/ in it, and writes one refusing stub
                    per REFUSED_TOOLS entry. Reads os.environ and copies it
                    without TC_* or CHILD_ENV_DROP variables.
        @deps       tempfile, os, shlex.
        @complexity O(e + p) over e environment variables and p PATH
                    entries (tens each), plus R = len(REFUSED_TOOLS) = 2
                    stubs written.
        @alloc      the folder and one env dict, released in __exit__.
        """
        self._tmp = tempfile.TemporaryDirectory(prefix="tc-test-")
        self.base = pathlib.Path(self._tmp.name)
        self.path = self.base / "root"
        self.path.mkdir()
        self._refuse = self.base / "refuse"
        self._refuse.mkdir()
        for name in REFUSED_TOOLS:
            stub = self._refuse / name
            stub.write_text(REFUSE_STUB.format(
                name=name, code=REFUSED_EXIT_CODE,
                message=shlex.quote(f"real {name} is not allowed in tests")))
            stub.chmod(FAKE_EXE_MODE)
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith(TC_ENV_PREFIX) and k not in CHILD_ENV_DROP}
        self.env["TC_ROOT"] = str(self.path)
        self.env["PATH"] = self._guard_path(self.env.get("PATH", os.defpath))
        return self

    def __exit__(self, exc_type, exc, tb):
        """Kill and reap every child still registered, then remove the folder.

        Sends SIGKILL to every child first, so they all die at once, then
        reaps each against one shared deadline, REAP_CEILING_SECONDS after
        the last SIGKILL: h stuck children cost one ceiling, not h. Tries
        every child even when one times out, then raises one ChildNotReaped
        naming each that did. If the test's own exception is already on its
        way out, the names go to stderr instead (see _report_unreaped).

        @interacts  SIGKILL to each child this root started that is still
                    running, by its own pid; removes the temporary folder.
        @deps       tempfile, subprocess, time; _kill, _stop,
                    _report_unreaped.
        @complexity O(h) over h children started, up to about 50 (CORE
                    K3), plus the size of the folder. Waits at most one
                    REAP_CEILING_SECONDS in all.
        @alloc      frees everything __enter__ and the tools made: clears
                    the child list and the env copy, removes the folder.
        """
        unreaped = []
        try:
            for proc in self._children:
                _kill(proc)
            deadline = time.monotonic() + REAP_CEILING_SECONDS
            for proc in self._children:
                try:
                    _stop(proc, deadline)
                except subprocess.TimeoutExpired:
                    unreaped.append(proc)
        finally:
            self._children.clear()
            self.env = None
            self._tmp.cleanup()
        _report_unreaped(unreaped, exc_type is not None)
        return False

    def _guard_path(self, path):
        """`path` with the refusing stubs put ahead of every folder outside base.

        Folders inside this root's temporary folder (a fake's bin/) keep
        their place in front; the stubs go right after them, so a fake can
        go first and a real tool never can. Inside means the entry is
        absolute and its real path (os.path.realpath) is under base's real
        path, so `<base>/../../usr/bin` or a symlink in base that points
        out of it stops the run like any outside folder. An empty or
        relative entry stops it too. This guards PATH lookups only: an
        absolute /usr/bin/ssh never reads PATH (see the module block).

        @interacts  resolves the leading entries with os.path.realpath,
                    which reads symlinks; writes nothing.
        @deps       os, pathlib.
        @complexity O(p) over p entries in `path` (tens). realpath runs on
                    the leading run of fake folders (a handful) plus the
                    entry that ends it, a few lstat calls each.
        @alloc      one list of entries and the joined string, returned.
        """
        refuse = str(self._refuse)
        real_base = os.path.realpath(self.base)
        entries = [e for e in path.split(os.pathsep) if e != refuse]
        at = 0
        while (at < len(entries) and os.path.isabs(entries[at])
               and pathlib.Path(os.path.realpath(entries[at])).is_relative_to(real_base)):
            at += 1
        entries.insert(at, refuse)
        return os.pathsep.join(entries)

    def _child_env(self, env):
        """The environment one child gets: this root's env, with `env` over it.

        A key set to None in `env` is unset for this child only. TC_ROOT is
        always this root's path, and PATH goes through _guard_path whatever
        `env` says. Raises ValueError if `env` unsets PATH: with no PATH a
        child falls back to the system's own folders, past the stubs.

        @interacts  none; reads this root's env.
        @deps       _guard_path.
        @complexity O(e + p) over e variables and p PATH entries (tens each).
        @alloc      one env dict, returned.
        """
        run_env = dict(self.env)
        for key, value in (env or {}).items():
            if value is None:
                run_env.pop(key, None)
            else:
                run_env[key] = value
        if "PATH" not in run_env:
            raise ValueError("tests/_root.py: PATH cannot be unset; the refusing "
                             "ssh and codex stubs live on it")
        run_env["TC_ROOT"] = str(self.path)
        run_env["PATH"] = self._guard_path(run_env["PATH"])
        return run_env

    def tc(self, *args, stdin=None, env=None, timeout=DEFAULT_TC_TIMEOUT_SECONDS):
        """Run `tc *args` under this root. Return (exit, stdout, stderr).

        `stdin` is a string fed to tc, or /dev/null when None. `env` holds
        variables layered over this root's env for this call only (PATH, a
        TC_* setting, an identity variable). A key set to None is unset for
        this call. TC_ROOT always stays this root, and the refusing stubs
        stay ahead of every folder outside it (see _child_env). A run past
        `timeout` raises subprocess.TimeoutExpired after killing the child.

        @interacts  runs [sys.executable, TC, *args] as a child and waits.
        @deps       subprocess; ../tc; _child_env.
        @complexity O(e + p) for the env, plus the child's own work.
        @alloc      the env copy and the captured output, returned.
        """
        feed = {"input": stdin} if stdin is not None else {"stdin": subprocess.DEVNULL}
        done = subprocess.run([sys.executable, str(TC), *args], env=self._child_env(env),
                              capture_output=True, text=True, timeout=timeout, **feed)
        return done.returncode, done.stdout, done.stderr

    def start(self, *args, stdin=None, env=None, argv=None):
        """Start `tc *args` in the background under this root; return its Popen.

        For a child the test watches while it runs, such as a send blocked
        on a lock (CORE K3). `stdin` is a string the child reads, served
        from a file in the temp folder so writing it never blocks, or
        /dev/null when None. `env` works as in tc(). stdout and stderr are
        text pipes: read them with proc.communicate(timeout=...). The child
        is registered with this root, so __exit__ kills it by its own pid
        if it still runs, reaps it, and closes its pipes.

        `argv`, when given, is the whole command to run in place of
        [sys.executable, TC, *args], such as [sys.executable,
        "board/serve.py"] for BOARD B2. It gets the same env, stdin, pipes
        and teardown. Give tc arguments or `argv`, not both: either way
        round the other would be dropped, so both raise ValueError, as does
        an empty argv or a bare string.

        @interacts  starts one child running [sys.executable, TC, *args],
                    or `argv`; writes start-stdin-* in the temp folder when
                    `stdin` is given.
        @deps       subprocess, tempfile; ../tc; _child_env.
        @complexity O(e + p) for the env, plus the child's own work.
        @alloc      one Popen with two pipes, held in the child list until
                    __exit__; one stdin file, removed with the temp folder.
        """
        if argv is None:
            command = [sys.executable, str(TC), *args]
        elif args:
            raise ValueError("tests/_root.py: start() takes tc arguments or argv=, not both")
        elif isinstance(argv, (str, bytes)) or not argv:
            raise ValueError("tests/_root.py: start(argv=) takes a non-empty list of words")
        else:
            command = list(argv)
        run_env = self._child_env(env)
        feed = contextlib.nullcontext(subprocess.DEVNULL)
        if stdin is not None:
            fd, name = tempfile.mkstemp(dir=self.base, prefix="start-stdin-")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(stdin)
            feed = open(name, "rb")
        with feed as source:
            proc = subprocess.Popen(command, env=run_env,
                                    stdin=source, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True)
        self._children.append(proc)
        return proc

    @contextlib.contextmanager
    def listener(self, name, timeout):
        """Start `tc wait <name> --timeout <timeout>`; yield its pid once proven.

        Proven means /proc/locks shows that pid holding
        mail/.wait-<name>.lock. Before starting anything it raises
        ListenerNotProven if the name already has unread mail in this root:
        a `tc wait` started over waiting mail exits at once, so it cannot
        be held. Then, every LOCK_POLL_SECONDS, it checks the deadline and
        reads /proc/locks. The first read comes before any sleep, so a
        listener already holding its lock by then costs no sleep (tc's own
        start-up usually takes longer than that, so most listeners still
        sleep once or more). It raises ListenerNotProven at
        LOCK_CEILING_SECONDS, or if the child exits first (a second
        listener for the name exits 3). Mail the test sends while the
        listener starts is the test's own race.

        Teardown drops the child from this root's list, kills the pid and
        reaps it, even when the test killed it first. If reaping times out
        it raises ChildNotReaped, unless the test's own exception is already
        on its way out: then the failure goes to stderr and the test's
        exception carries on.

        @interacts  globs mail/to-<name>/*.md; starts one `tc wait` child;
                    reads /proc/locks; writes its output to
                    listener-<name>-*.out in the temp folder.
        @deps       subprocess, tempfile, time; flock_holders, _stop,
                    _report_unreaped.
        @complexity O(u) over u unread files to check the inbox (0 when it
                    goes on), then at most P = LOCK_CEILING_SECONDS /
                    LOCK_POLL_SECONDS = 100 reads of /proc/locks, each O(k)
                    over k lines (tens).
        @alloc      one Popen, dropped from the child list and reaped in
                    teardown; one output file, removed with the temp folder.
        """
        waiting = sorted((self.path / "mail" / f"to-{name}").glob("*.md"))
        if waiting:
            raise ListenerNotProven(
                f"tc wait {name} not started: mail/to-{name} already holds {len(waiting)} "
                f"unread message(s). A tc wait started over waiting mail exits at once, "
                f"so it cannot be held as a listener. Read the mail first, or listen on "
                f"another name.")
        lock = self.path / "mail" / f".wait-{name}.lock"
        with tempfile.NamedTemporaryFile(dir=self.base, prefix=f"listener-{name}-",
                                         suffix=".out", delete=False) as out:
            proc = subprocess.Popen([sys.executable, str(TC), "wait", name, "--timeout", str(timeout)],
                                    env=self._child_env(None), stdin=subprocess.DEVNULL,
                                    stdout=out, stderr=subprocess.STDOUT)
        self._children.append(proc)
        in_flight = False
        try:
            deadline = time.monotonic() + LOCK_CEILING_SECONDS
            while True:
                if time.monotonic() >= deadline:
                    raise ListenerNotProven(f"tc wait {name} (pid {proc.pid}) did not hold {lock} "
                                            f"within {LOCK_CEILING_SECONDS} s")
                if proc.pid in flock_holders(lock):
                    break
                if proc.poll() is not None:
                    said = pathlib.Path(out.name).read_text()
                    raise ListenerNotProven(f"tc wait {name} (pid {proc.pid}) exited {proc.returncode} "
                                            f"without holding {lock}. It said: {said!r}")
                time.sleep(LOCK_POLL_SECONDS)
            yield proc.pid
        except BaseException:
            in_flight = True
            raise
        finally:
            if proc in self._children:
                self._children.remove(proc)
            try:
                _stop(proc)
            except subprocess.TimeoutExpired:
                _report_unreaped([proc], in_flight)

    def fake_bin(self, name, exit_code, stderr=""):
        """Write a fake `name` (codex or ssh) that records each call, first on PATH.

        `name` is one of REFUSED_TOOLS or a plain lowercase word matching
        FAKE_NAME_PATTERN; anything else (a slash, a newline, a capital, an
        empty string) raises ValueError before anything is written.
        `exit_code` is one int for every call, or a list with one code per
        call in order, the last repeating: [0, 255, 0] exits 0, then 255,
        then 0 from the third call on. `stderr` is text the fake writes to
        its stderr on every call. The fake's bin/ folder goes first on this
        root's PATH, ahead of the refusing stubs and any earlier fake, so
        every child started after this call finds it.

        Returns (folder, calls). `calls()` returns one dict per call, in
        order: {"argv": the arguments after the program name, "stdin": what
        it read}. While the root is live it returns [] when the fake never
        ran. After the root exits the record is gone with the temp folder,
        so calls() raises RuntimeError instead of answering []: read it
        inside the `with TcRoot()` block. The record is calls.jsonl beside
        `folder` (folder.parent / "calls.jsonl"), so a test asserts it
        exists before reading it.

        @interacts  writes fake-<name>-*/bin/<name> (a /bin/sh wrapper, mode
                    0700) and fake-<name>-*/fake.py in the temp folder; puts
                    bin/ first on this root's PATH. Each call of the fake
                    appends to fake-<name>-*/calls.jsonl and rewrites
                    fake-<name>-*/calls.count, both under the record's flock.
        @deps       re, tempfile, json, shlex; sys.executable as the
                    recorder's interpreter; /bin/sh.
        @complexity O(n + p) to write, over n codes given (a handful) and p
                    PATH entries. Each call of the fake is O(s) over s bytes
                    of its own stdin, and O(1) in earlier calls (it reads
                    one counter). calls() is O(B) over B bytes recorded,
                    every call's stdin included.
        @alloc      one folder holding the wrapper, the recorder, the record
                    and the counter, removed with the temp folder.
        """
        if not isinstance(name, str) or (name not in REFUSED_TOOLS
                                         and FAKE_NAME_PATTERN.fullmatch(name) is None):
            raise ValueError(f"fake_bin({name!r}): a fake's name is one of {REFUSED_TOOLS} or a "
                             f"plain lowercase word ({FAKE_NAME_PATTERN.pattern})")
        codes = [exit_code] if isinstance(exit_code, int) else list(exit_code)
        if not codes:
            raise ValueError(f"fake_bin({name!r}): exit_code is an empty list; give at least one code")
        codes = [int(code) for code in codes]
        home = pathlib.Path(tempfile.mkdtemp(dir=self.base, prefix=f"fake-{name}-"))
        folder = home / "bin"
        folder.mkdir()
        record = home / "calls.jsonl"
        count = home / "calls.count"
        script = home / "fake.py"
        script.write_text(FAKE_SCRIPT.format(name=name, codes=codes, stderr=str(stderr),
                                             record=str(record), count=str(count)),
                          encoding="utf-8")
        exe = folder / name
        exe.write_text(FAKE_WRAPPER.format(name=name, python=shlex.quote(sys.executable),
                                           script=shlex.quote(str(script))))
        exe.chmod(FAKE_EXE_MODE)
        self.env["PATH"] = self._guard_path(f"{folder}{os.pathsep}{self.env['PATH']}")

        def calls():
            """Every call the fake recorded, oldest first; [] if it never ran.

            Raises RuntimeError once the root has exited: the record went
            with the temp folder, and [] would then pass an "assert not
            called" whether or not the fake ran.

            @interacts  checks the fake's folder; reads calls.jsonl. Writes
                        nothing.
            @deps       json.
            @complexity O(B) over B bytes recorded, every call's stdin
                        included.
            @alloc      one list of dicts, returned.
            """
            if not home.exists():
                raise RuntimeError(f"tests/_root.py: calls() for the fake {name!r} was read after "
                                   f"its TcRoot exited, and the record went with the temp folder. "
                                   f"Read calls() inside the `with TcRoot()` block.")
            if not record.exists():
                return []
            return [json.loads(line) for line in record.read_text(encoding="utf-8").splitlines()]

        return folder, calls
