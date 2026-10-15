"""
Tests for the core mailbox: send, read, peek, wait, log, status and the
message counter. CORE tasks K1 to K8 in
docs/planning/connection-routes/phases.md, one test each.

Model:  Claude Opus 5.5 (the CORE lane agent), 2026-10-14
Status: unreviewed

Every test runs tc under its own throwaway TC_ROOT from tests/_root.py and
never touches the live mail/ or status/. Every assertion message carries
the command and its captured output.

Written to hold before and after CARDS changes tc beside it. No test
asserts that a send's stderr is empty: a first send to a name nobody
joined will warn there (open item O1). No test depends on `tc read` or
`tc peek` creating an inbox folder (open item O2).

@interacts  runs ../tc as a subprocess through tests/_root.py: tc() for
            one command, start() for the K3 senders, listener() for K4's
            first wait (proven in /proc/locks, killed by its own pid in the
            harness's teardown). K2 loads tc as a module with TC_ROOT set
            to the test's root before the load, and wraps os.open,
            builtins.open, pathlib.Path.write_text, Path.rename and os.link
            for one in-process send, all restored as the send returns or
            raises.
            K3 takes an flock on the root's mail/.seq itself and reads
            /proc/locks to prove each send is blocked on it. K5 sets
            message file times with os.utime. Reads and writes only inside
            each test's temp folder. At import, K3's block ceiling reads
            LOCK_WAIT_SECONDS from ../tc's source (tc_constant; SHARED fix
            round 3, Claude Opus 5.5, unreviewed), which runs nothing.
@deps       python3 stdlib (ast, builtins, contextlib, fcntl, importlib, io,
            os, pathlib, re, shlex, subprocess, sys, time, unittest,
            unittest.mock); tests/_root.py; ../tc; Linux only (flock,
            /proc/locks).
@complexity O(1) tc commands per test, except K3: S = SENDERS = 50
            children, and each poll of /proc/locks is O(k + S) over k
            other lines (tens). K3 waits HOLD_SECONDS = 1 s on purpose and
            K4 waits WAIT_TIMEOUT_SECONDS = 1 s for its timeout; every
            other test is a handful of tc runs.
@alloc      one TcRoot per test (two in K3), removed when its context
            exits, with every child it started killed and reaped. K2's
            module object and its call records live for one test. Nothing
            is kept between tests.
"""

import ast
import builtins
import contextlib
import fcntl
import importlib.machinery
import importlib.util
import io
import os
import pathlib
import re
import shlex
import subprocess
import sys
import time
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
# Run as `python3 -m unittest tests.test_mailbox` from the repo root, tests/
# is not on sys.path; under discover it is. Add it once so both work.
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import _root  # noqa: E402  (needs the path line above)


# SHARED fix round 3 (Claude Opus 5.5, unreviewed): the audit's LOW-4, K3 reads tc's bound.
def tc_constant(name):
    """The value of the module constant `name` in ../tc, read from its source, never run.

    For a test bound that must sit under one of tc's own, so it follows tc
    instead of a copy. Raises LookupError when tc has no such constant.

    @interacts  reads ../tc's source. Writes nothing; runs nothing of tc.
    @deps       ast, pathlib; HERE.
    @complexity O(s) over s bytes of tc's source (under 200 KB).
    @alloc      the source and its syntax tree, freed on return.
    """
    for node in ast.parse((HERE.parent / "tc").read_text()).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise LookupError(f"tc has no constant {name}")


# Made-up mailbox names. b gets mail; c is a name with none; d holds a
# listener in K4.
A = "a"
B = "b"
C = "c"
D = "d"
BODY = "hi"
# The two status posts in K6. Neither is a substring of the other, so
# finding one in the output never stands in for the other.
FIRST_STATUS = "first post"
SECOND_STATUS = "second post"

# The header line tc writes at the top of every message:
# "# #<n> from <sender> to <to>, <time>". Names never hold a comma or a space.
HEADER = re.compile(r"^# #(\d+) from (\S+) to ([^,\s]+)", re.MULTILINE)
# What `tc send` prints on stdout when the mail landed.
SENT = re.compile(r"^sent #(\d+) to ", re.MULTILINE)

# K4. The plan's timeout for "a wait with no mail" (phases.md K4).
WAIT_TIMEOUT_SECONDS = 1
# K4. A wait with mail already waiting returns at once. This is only its
# ceiling, kept under the harness's 10 s per command so a wait that misses
# the mail fails with exit 2 and its own words, not a harness timeout.
MAIL_WAIT_TIMEOUT_SECONDS = 5
# K4. The listener never times out on its own during the test; the harness
# kills it when its context exits. Same value as tests/test_root.py.
LISTENER_TIMEOUT_SECONDS = 30
# K4. The exit codes it checks, from contracts.md's exit table: a wait that
# timed out, and a second wait for a name already listening. Phase fix
# round 1 (Claude Opus 5.5, unreviewed).
EXIT_TIMEOUT = 2
EXIT_ALREADY_LISTENING = 3

# K3. The plan's numbers: the send has not finished after 1 s of the
# harness holding the lock, and finishes within 1 s of the release.
HOLD_SECONDS = 1
RELEASE_CEILING_SECONDS = 1
# K3. How long a send gets to reach the lock and block on it: Python
# start-up plus tc's imports is well under 1 s. The same 5 s ceiling the
# harness gives a listener, so a slow machine fails here with a message
# instead of hanging.
BLOCK_CEILING_SECONDS = 5
# K3. Gap between two reads of /proc/locks while waiting for senders to
# block: at most 100 reads in the 5 s ceiling, never a fixed sleep. The
# harness polls a listener at the same rate.
LOCK_POLL_SECONDS = 0.05
# K3, the second check: the plan's 50 senders at once.
SENDERS = 50
# K3, the second check. All 50 must start and block on the lock within this,
# then all must finish within SENDERS_FINISH_CEILING_SECONDS of the release.
# Together they keep the check under the brief's 10 s. Measured on the
# owner's machine at a load near 16 on 32 cores: about 0.2 s.
# SHARED fix round 3 (Claude Opus 5.5, unreviewed): the audit's LOW-4. Each
# sender gives up LOCK_WAIT_SECONDS after it starts waiting (tc's bounded
# wait, D20, D23), so the block ceiling sits that bound less
# SENDERS_RELEASE_MARGIN_SECONDS (room for the release and 50 quick turns at
# the counter), read from tc rather than copied so the two never drift.
# SHARED fix round 4 (Claude Opus 5.5, unreviewed): the audit's LOW-6. The
# ceiling counts from just before the first spawn, and each sender's own
# bound starts later, after its launch, so the ceiling always ends first. A
# slow start then fails here, by count of senders blocked, never by a first
# sender giving up and the test blaming tc for not waiting.
SENDERS_RELEASE_MARGIN_SECONDS = 1
SENDERS_BLOCK_CEILING_SECONDS = tc_constant("LOCK_WAIT_SECONDS") - SENDERS_RELEASE_MARGIN_SECONDS
SENDERS_FINISH_CEILING_SECONDS = 3

# /proc/locks columns for a blocked waiter:
# "1: -> FLOCK ADVISORY WRITE <pid> <maj>:<min>:<inode> 0 EOF".
# The holder's line has no "->", so its columns sit one to the left.
WAITER_MARK = "->"
WAITER_MARK_COLUMN = 1
WAITER_KIND_COLUMN = 2
WAITER_PID_COLUMN = 5
WAITER_FILE_COLUMN = 6

# K5. How far apart the test sets the three messages' file times, newest
# first by number, so a log sorted by file time comes out backward.
MTIME_STEP_SECONDS = 100

# K2. The tool, loaded in process. The harness runs this same file.
TC = HERE.parent / "tc"
# K2. The module name tc is loaded under. Never "tc" or "__main__", so the
# load never runs main() and never shadows anything else.
TC_MODULE_NAME = "tc_under_test_mailbox"
# K2. tc reads its settings from environment variables with this prefix.
# None reaches the in-process load, as the harness keeps them from children.
TC_ENV_PREFIX = "TC_"
# K2 fix (Claude Opus 5.5, unreviewed). The open() mode letters that can
# create a file: write, append, exclusive create. "r+" opens only a file
# that already exists, so it is not here.
CREATING_MODE_LETTERS = frozenset("wax")


def said(args, code, out, err):
    """The command and everything it printed, for an assertion message.

    @interacts  none; string work only.
    @deps       shlex.
    @complexity O(n) over n characters of output.
    @alloc      one string, returned.
    """
    return (f"\n$ tc {shlex.join(str(a) for a in args)}\nexit {code}\n"
            f"--- stdout ---\n{out}--- stderr ---\n{err}--- end ---")


def run(root, *args, stdin=None):
    """Run `tc *args` under `root`. Return (exit, stdout, stderr, said).

    @interacts  one tc child through root.tc().
    @deps       _root.TcRoot.tc, said.
    @complexity the child's own work, plus O(n) over n characters of output.
    @alloc      the captured output and the message, returned.
    """
    code, out, err = root.tc(*args, stdin=stdin)
    return code, out, err, said(args, code, out, err)


def headers(text):
    """Every message header in `text`, in order, as (number, sender, to).

    @interacts  none; string work only.
    @deps       re (HEADER).
    @complexity O(n) over n characters.
    @alloc      one list of tuples, returned.
    """
    return [(int(n), sender, to) for n, sender, to in HEADER.findall(text)]


def lines(text):
    """`text` split into lines with their ends stripped.

    @interacts  none.
    @deps       none.
    @complexity O(n) over n characters.
    @alloc      one list of strings, returned.
    """
    return [line.rstrip() for line in text.splitlines()]


def inbox_files(root):
    """Every file in every inbox under `root`, unread or read, sorted.

    Leaves out mail/.seq and the listeners' lock files, which sit in mail/
    itself, outside any inbox.

    @interacts  globs mail/to-*/ under root.path. Writes nothing.
    @deps       pathlib.
    @complexity O(f) over f files in the inboxes (single digits, or 50 in K3).
    @alloc      one sorted list of paths, returned.
    """
    return sorted(p for p in (root.path / "mail").glob("to-*/**/*") if p.is_file())


def lock_waiters(path):
    """Pids blocked waiting for an flock on `path`, read from /proc/locks.

    The harness's flock_holders() names only holders. A waiter's line
    carries "->" before FLOCK, so it is read here, apart.

    @interacts  stats `path`; reads /proc/locks. Writes nothing.
    @deps       os, pathlib; Linux /proc/locks.
    @complexity O(k) over k lines in /proc/locks (tens, plus one per blocked
                sender: up to SENDERS = 50 in K3).
    @alloc      the table's lines and one set of pids, freed on return.
    """
    try:
        st = os.stat(path)
    except FileNotFoundError:
        return set()
    key = f"{os.major(st.st_dev):02x}:{os.minor(st.st_dev):02x}:{st.st_ino}"
    pids = set()
    for line in pathlib.Path("/proc/locks").read_text().splitlines():
        cols = line.split()
        if (len(cols) > WAITER_FILE_COLUMN and cols[WAITER_MARK_COLUMN] == WAITER_MARK
                and cols[WAITER_KIND_COLUMN] == "FLOCK" and cols[WAITER_FILE_COLUMN] == key):
            pids.add(int(cols[WAITER_PID_COLUMN]))
    return pids


def load_tc(root):
    """Load tc as a module pointed at `root`, without running main().

    tc reads ROOT, MAIL, STATUS and SEQ_FILE once, at import. So TC_ROOT is
    set to root.path before the load, and every inherited TC_* variable is
    dropped as the harness drops them for children. os.environ is restored
    after the load.

    @interacts  reads ../tc and runs its top level (constants and
                function definitions only); os.environ is changed for the
                load and restored.
    @deps       importlib, unittest.mock; ../tc (TC).
    @complexity O(e) over e environment variables (tens), plus tc's import.
    @alloc      one module object, returned; it is not put in sys.modules.
    """
    clean = {k: v for k, v in os.environ.items() if not k.startswith(TC_ENV_PREFIX)}
    clean["TC_ROOT"] = str(root.path)
    with mock.patch.dict(os.environ, clean, clear=True):
        loader = importlib.machinery.SourceFileLoader(TC_MODULE_NAME, str(TC))
        module = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
        loader.exec_module(module)
    return module


# K2 fix (Claude Opus 5.5, unreviewed).
def named(path, dir_fd=None):
    """`path` made absolute, its folders resolved and its last part kept as given.

    A link at the last part is named, not followed, so a K2 record says
    which name a call touched. K2 puts every path it records or compares
    through this, so the records and the inbox listing compare alike.
    P3 fix round 1a (Claude Opus 5.5, unreviewed): D35, tc now publishes
    by name in the inbox's open descriptor. With `dir_fd`, `path` is a
    name in the folder open at it, named by that folder's real path
    (/proc/self/fd), as the kernel reaches it.

    @interacts  resolves the folders above `path` (lstat and readlink on
                each), or reads the link /proc/self/fd/<dir_fd>. Writes
                nothing.
    @deps       os, pathlib.
    @complexity O(d) over d parts of the path (about ten under a temp root).
    @alloc      one Path, returned.
    """
    path = pathlib.Path(os.fsdecode(path))
    if dir_fd is not None:
        return pathlib.Path(os.readlink(f"/proc/self/fd/{dir_fd}")) / path
    return path.parent.resolve() / path.name


class MailboxTest(unittest.TestCase):
    """K1 to K8: the core mailbox, one test per row of the plan's table.

    @interacts  see the module block.
    @deps       _root.TcRoot.
    @complexity O(1) tc commands per test, except K3 (S = SENDERS = 50).
    @alloc      one TcRoot per test, two in K3.
    """

    def wait_until_blocked(self, procs, seq, ceiling, what, deadline=None):
        """Return once every child in `procs` is blocked on the flock of `seq`.

        Fails the test if a child exits first (it finished while the lock
        was held, so it never waited for it), or if `ceiling` seconds pass
        first. Polls /proc/locks every LOCK_POLL_SECONDS; never a bare sleep.
        SHARED fix round 4 (Claude Opus 5.5, unreviewed): the audit's
        LOW-6. `deadline`, a time.monotonic() value the caller took
        `ceiling` seconds ahead (K3's fifty, before their first spawn),
        counts the ceiling from then; None counts it from this call.
        SHARED fix round 5 (Claude Opus 5.5, unreviewed): the audit's LOW-3
        (audits/2026-10-15-0201-quick). Each poll tests the deadline
        before it looks for a finished child. So spawns slower than a
        sender's own bound fail by count of senders blocked, never by a
        sender that gave up past its bound being blamed for not waiting.

        @interacts  reads /proc/locks; reads a finished child's output.
        @deps       lock_waiters, said, time.
        @complexity at most ceiling / LOCK_POLL_SECONDS polls (100 for 5 s),
                    each O(k + h) over k lines in /proc/locks and h children.
        @alloc      one set of pids per poll, freed as it goes.
        """
        pids = {proc.pid for proc in procs}
        if deadline is None:
            deadline = time.monotonic() + ceiling
        while True:
            waiting = lock_waiters(seq) & pids
            if waiting == pids:
                return
            if time.monotonic() >= deadline:  # SHARED fix round 5 (Claude Opus 5.5, unreviewed): LOW-3, before a finished child
                self.fail(f"{what}: {len(waiting)} of {len(pids)} sends blocked on {seq} "
                          f"within {ceiling} s")
            done = [proc for proc in procs if proc.poll() is not None]
            if done:
                proc = done[0]
                out, err = proc.communicate()
                self.fail(f"{what}: pid {proc.pid} finished while the test held {seq}, so it "
                          f"never waited for the lock{said(proc.args[2:], proc.returncode, out, err)}")
            time.sleep(LOCK_POLL_SECONDS)

    def test_k1_a_message_is_read_once(self):
        """K1. Send hi a to b; read b twice. The first read shows it and moves it; the second says none.

        Must reject a read that prints and leaves the file (the rename in
        cmd_read commented out): the second read would print it again.

        @interacts  one send and two reads under one root.
        @deps       run, said.
        @complexity O(1).
        @alloc      one TcRoot, removed on exit.
        """
        with _root.TcRoot() as root:
            code, out, err, ran = run(root, "send", "--from", A, "--to", B, BODY)
            self.assertEqual(code, 0, ran)
            box = root.path / "mail" / f"to-{B}"

            code, out, err, ran = run(root, "read", B)
            self.assertEqual(code, 0, ran)
            self.assertTrue(out.startswith(f"# #1 from {A} to {B}"),
                            f"the first read does not start with the header{ran}")
            self.assertIn(BODY, lines(out), f"the first read does not show the body{ran}")
            unread = sorted(box.glob("*.md"))
            self.assertEqual(unread, [], f"the first read left the message unread: {unread}{ran}")
            moved = sorted((box / "read").glob("*.md"))
            self.assertEqual(len(moved), 1, f"read/ holds {moved}, not one message{ran}")
            self.assertTrue(moved[0].read_text().startswith(f"# #1 from {A} to {B}"),
                            f"{moved[0]} is not message #1 from {A} to {B}{ran}")

            code, out, err, ran = run(root, "read", B)
            self.assertEqual(code, 0, ran)
            self.assertEqual(lines(out), [f"no unread mail for {B}"],
                             f"the second read did not say there is no unread mail{ran}")

    # K2 fix (Claude Opus 5.5, unreviewed): records every way tc can create a file.
    def test_k2_a_message_appears_only_whole(self):
        """K2. One in-process send: the .md is made only by a rename or a hard link from a .tmp sibling.

        White box. tc is loaded as a module under this root. For the one
        send, each way tc can create a file is wrapped to record it, so the
        test does not lean on one write API: os.open with O_CREAT (tc's
        write_new_file goes this way), builtins.open given a path in a mode
        that creates, and Path.write_text. Each record holds the name and
        whether anything was at it before the call. Path.rename is wrapped
        too, and so is os.link (SHARED fix round 2, Claude Opus 5.5,
        unreviewed: tc now links the .tmp to the final name, which never
        replaces a file, D20). At the rename or link that makes the
        message, the test records whether the final name already existed,
        the .tmp's bytes, and what unread() lists right then, while the
        .tmp sits in the inbox.

        Then: the recorder saw at least one creation; none was the final
        name; one rename or link made the final name, from a sibling
        ending .tmp that a recorded creation made fresh; the final name did
        not exist before it; unread() at that moment listed no .tmp. A
        recorder that misses how tc writes fails loudly, never passes. Must
        reject a send that writes the final name directly: it fails every
        run, not by timing luck.

        @interacts  loads tc as a module; wraps os.open, builtins.open,
                    Path.write_text, Path.rename and os.link for the send
                    only, all restored when main() returns or raises; runs
                    tc's main() in process with sys.argv patched and stdout
                    and stderr captured.
        @deps       load_tc, named, CREATING_MODE_LETTERS; builtins,
                    contextlib, io, os, unittest.mock.
        @complexity O(c + u + n): c creations recorded (the .seq file, any
                    lock file, the .tmp: under ten), and one rename or link
                    that lists u unread files (none here) and reads the
                    .tmp's n bytes.
        @alloc      the module, two small lists of records; one TcRoot,
                    removed on exit.
        """
        with _root.TcRoot() as root:
            tc = load_tc(root)
            self.assertEqual(pathlib.Path(tc.MAIL), root.path / "mail",
                             f"tc loaded with MAIL {tc.MAIL}, not this test's root; stopping "
                             f"before it could touch a live mailbox")
            box = root.path / "mail" / f"to-{B}"
            creations, renames = [], []
            real_os_open = os.open
            real_open = builtins.open
            real_write_text = pathlib.Path.write_text
            real_rename = pathlib.Path.rename
            real_link = os.link

            def created(how, path, dir_fd=None):
                """Record that `how` is about to create `path` (a name in the folder open at `dir_fd`, when given), and whether anything is there now.

                @interacts  lstats `path` (a link counts as there). Writes
                            nothing.
                @deps       named; os.
                @complexity O(d) over d parts of the path.
                @alloc      one dict, appended to creations.
                """
                where = named(path, dir_fd)
                creations.append({"how": how, "path": where, "existed": os.path.lexists(where)})

            def os_open(path, flags, *args, **kwargs):
                """Record a path opened with O_CREAT, then open as the real os.open does.

                P3 fix round 1a (Claude Opus 5.5, unreviewed): D35. tc
                makes a message's .tmp by its name in the inbox's open
                descriptor (dir_fd), so a name given with dir_fd is
                recorded in that folder (named).

                @interacts  creates or opens `path` through the real call.
                @deps       created; os.
                @complexity O(d) over d parts of the path.
                @alloc      one dict when O_CREAT is set.
                """
                if flags & os.O_CREAT:
                    created("os.open", path, kwargs.get("dir_fd"))
                return real_os_open(path, flags, *args, **kwargs)

            def builtin_open(file, mode="r", *args, **kwargs):
                """Record a path opened in a mode that creates, then open as the real open() does.

                A descriptor (an int) is not recorded here: os.open made
                that file and recorded it.

                @interacts  opens `file` through the real call.
                @deps       created, CREATING_MODE_LETTERS; builtins.
                @complexity O(d) over d parts of the path.
                @alloc      one dict when the mode creates.
                """
                if not isinstance(file, int) and CREATING_MODE_LETTERS & set(mode):
                    created("open", file)
                return real_open(file, mode, *args, **kwargs)

            def write_text(path, data, *args, **kwargs):
                """Record the path, then write as the real Path.write_text does.

                @interacts  writes `path` through the real method.
                @deps       created; pathlib.
                @complexity O(n) over n characters of `data`.
                @alloc      one dict.
                """
                created("Path.write_text", path)
                return real_write_text(path, data, *args, **kwargs)

            def rename(path, target):
                """Record the state at this moment, then rename as the real Path.rename does.

                @interacts  reads the source file, lstats the target, and
                            lists the inbox through tc's unread(); renames
                            through the real method.
                @deps       named; os, pathlib; tc.unread.
                @complexity O(u + n) over u unread files and n bytes of the
                            source.
                @alloc      one dict per call.
                """
                src = pathlib.Path(path)
                renames.append({
                    "src": named(path),
                    "dst": named(target),
                    "dst_existed": os.path.lexists(target),
                    "src_bytes": src.read_bytes() if src.is_file() else None,
                    "unread": [p.name for p in tc.unread(B)],
                })
                return real_rename(path, target)

            # SHARED fix round 2 (Claude Opus 5.5, unreviewed): a send publishes with os.link (D20).
            def link(src, dst, *args, **kwargs):
                """Record the state at this moment, as rename() does, then link as the real os.link does.

                P3 fix round 1a (Claude Opus 5.5, unreviewed): D35. tc
                links by name in the inbox's open descriptor
                (src_dir_fd, dst_dir_fd), so each name is read in its
                folder (named).

                @interacts  reads the source file, lstats the target, and
                            lists the inbox through tc's unread(); links
                            through the real call.
                @deps       named; os, pathlib; tc.unread.
                @complexity O(u + n) over u unread files and n bytes of the
                            source.
                @alloc      one dict per call.
                """
                source = named(src, kwargs.get("src_dir_fd"))
                target = named(dst, kwargs.get("dst_dir_fd"))
                renames.append({
                    "src": source,
                    "dst": target,
                    "dst_existed": os.path.lexists(target),
                    "src_bytes": source.read_bytes() if source.is_file() else None,
                    "unread": [p.name for p in tc.unread(B)],
                })
                return real_link(src, dst, *args, **kwargs)

            wrapped = ((os, "open", os_open), (builtins, "open", builtin_open),
                       (pathlib.Path, "write_text", write_text), (pathlib.Path, "rename", rename),
                       (os, "link", link))
            argv = ["tc", "send", "--from", A, "--to", B, BODY]
            out, err = io.StringIO(), io.StringIO()
            code = 0
            # Every wrap is undone when this block exits, before any
            # assertion runs and before the TcRoot is removed.
            with contextlib.ExitStack() as patched:
                for owner, name, wrapper in wrapped:
                    patched.enter_context(mock.patch.object(owner, name, wrapper))
                patched.enter_context(mock.patch.object(sys, "argv", argv))
                patched.enter_context(contextlib.redirect_stdout(out))
                patched.enter_context(contextlib.redirect_stderr(err))
                try:
                    tc.main()
                except SystemExit as stop:
                    code = 0 if stop.code is None else stop.code
            ran = (f"\nin process: tc main() with argv {argv[1:]}{said(argv[1:], code, out.getvalue(), err.getvalue())}"
                   f"\nfile creations: {creations}\nrename and link calls: {renames}")

            self.assertEqual(code, 0, ran)
            finals = sorted(box.glob("*.md"))
            self.assertEqual(len(finals), 1, f"the inbox holds {finals}, not one message{ran}")
            final = named(finals[0])
            # A recorder that saw nothing proves nothing, so it fails here
            # rather than let the next check pass by not checking.
            self.assertNotEqual(creations, [],
                                f"recorded no file creation during the send, so this test's "
                                f"recorder misses how tc writes; wrap what tc now uses{ran}")
            created_paths = [c["path"] for c in creations]
            self.assertNotIn(final, created_paths, f"send created the final name {final.name} directly{ran}")
            made = [r for r in renames if r["dst"] == final]
            self.assertEqual(len(made), 1, f"{final.name} was not made by exactly one rename or link{ran}")
            made = made[0]
            self.assertEqual(made["src"].parent, final.parent,
                             f"the source is not a sibling of {final.name}{ran}")
            self.assertTrue(made["src"].name.endswith(".tmp"),
                            f"the source {made['src'].name} does not end .tmp{ran}")
            # Proves the creation record sees tc's writes, whichever API
            # made them, so "never created the final name" cannot pass by
            # not checking.
            self.assertIn(made["src"], created_paths,
                          f"no recorded creation (os.open with O_CREAT, open() in a creating "
                          f"mode, Path.write_text) made the .tmp, so this test's recorder "
                          f"misses how tc writes; wrap what tc now uses{ran}")
            fresh = [c for c in creations if c["path"] == made["src"] and not c["existed"]]
            self.assertNotEqual(fresh, [],
                                f"something was already at {made['src'].name} when tc created it, "
                                f"so no recorded creation made it{ran}")
            self.assertFalse(made["dst_existed"],
                             f"{final.name} existed before the rename or link, so it was not made by it{ran}")
            self.assertEqual(made["src_bytes"], finals[0].read_bytes(),
                             f"the .tmp at the rename or link differs from the final file: not whole{ran}")
            self.assertEqual([n for n in made["unread"] if n.endswith(".tmp")], [],
                             f"unread() listed a .tmp while it sat in the inbox{ran}")
            after = [p.name for p in tc.unread(B)]
            self.assertEqual(after, [finals[0].name], f"unread() after the send lists {after}{ran}")

    def check_one_send_waits_for_the_seq_lock(self):
        """K3, first check: a send blocks on the test's flock of mail/.seq, then finishes on release.

        The test takes the lock itself and proves it in /proc/locks, starts
        one send, and proves that pid is blocked on the lock. The send must
        still run HOLD_SECONDS later, and finish within
        RELEASE_CEILING_SECONDS of the release as message #1. Must reject
        the counter read without the flock: that send finishes at once.

        @interacts  creates mail/ and mail/.seq in the root and holds an
                    flock on .seq; one start() child, killed by the harness
                    if still running; reads /proc/locks.
        @deps       fcntl; _root.flock_holders, wait_until_blocked, said.
        @complexity O(1) children; at most BLOCK_CEILING_SECONDS /
                    LOCK_POLL_SECONDS polls of /proc/locks.
        @alloc      one TcRoot and one open file, both closed on exit.
        """
        with _root.TcRoot() as root:
            seq = root.path / "mail" / ".seq"
            seq.parent.mkdir()
            args = ("send", "--from", A, "--to", B, BODY)
            with open(seq, "a+") as held:
                fcntl.flock(held, fcntl.LOCK_EX)
                holders = _root.flock_holders(seq)
                self.assertIn(os.getpid(), holders,
                              f"the test does not hold {seq}; holders: {holders}")
                proc = root.start(*args)
                self.wait_until_blocked([proc], seq, BLOCK_CEILING_SECONDS,
                                        f"$ tc {shlex.join(args)}")
                try:
                    proc.wait(timeout=HOLD_SECONDS)
                except subprocess.TimeoutExpired:
                    pass
                else:
                    out, err = proc.communicate()
                    self.fail(f"the send finished within {HOLD_SECONDS} s while the test held "
                              f"{seq}{said(args, proc.returncode, out, err)}")
                fcntl.flock(held, fcntl.LOCK_UN)
                try:
                    out, err = proc.communicate(timeout=RELEASE_CEILING_SECONDS)
                except subprocess.TimeoutExpired:
                    self.fail(f"$ tc {shlex.join(args)} still running {RELEASE_CEILING_SECONDS} s "
                              f"after the test released {seq}")
            ran = said(args, proc.returncode, out, err)
            self.assertEqual(proc.returncode, 0, ran)
            self.assertEqual(SENT.findall(out), ["1"], f"the send was not numbered #1{ran}")
            files = inbox_files(root)
            self.assertEqual(len(files), 1, f"the inboxes hold {files}, not one message{ran}")
            self.assertEqual(headers(files[0].read_text()), [(1, A, B)],
                             f"{files[0]} is not message #1 from {A} to {B}{ran}")

    def check_fifty_senders_get_one_to_fifty(self):
        """K3, second check (not a mutation test): 50 senders at once get exactly 1 to 50.

        "At once" is made real: the test holds mail/.seq, starts 50 sends,
        proves all 50 pids are blocked on the lock in /proc/locks, then
        releases it, so all 50 race for the counter together.

        @interacts  creates mail/ and mail/.seq and holds an flock on .seq;
                    S = SENDERS = 50 start() children, killed by the harness
                    if still running; reads /proc/locks.
        @deps       fcntl; wait_until_blocked, said.
        @complexity O(S) children and O(S) files; at most
                    SENDERS_BLOCK_CEILING_SECONDS / LOCK_POLL_SECONDS polls,
                    each O(k + S).
        @alloc      one TcRoot (S children, 2S pipes, closed on exit) and one
                    open file.
        """
        with _root.TcRoot() as root:
            seq = root.path / "mail" / ".seq"
            seq.parent.mkdir()
            sends = [("send", "--from", f"sender{i}", "--to", B, f"{BODY} {i}")
                     for i in range(1, SENDERS + 1)]
            with open(seq, "a+") as held:
                fcntl.flock(held, fcntl.LOCK_EX)
                # SHARED fix round 4 (Claude Opus 5.5, unreviewed): LOW-6, the block ceiling counts from before the first spawn.
                deadline = time.monotonic() + SENDERS_BLOCK_CEILING_SECONDS
                procs = [root.start(*args) for args in sends]
                self.wait_until_blocked(procs, seq, SENDERS_BLOCK_CEILING_SECONDS,
                                        f"{SENDERS} senders to {B}", deadline=deadline)
                fcntl.flock(held, fcntl.LOCK_UN)
            deadline = time.monotonic() + SENDERS_FINISH_CEILING_SECONDS
            numbers, failed = [], []
            for args, proc in zip(sends, procs):
                try:
                    out, err = proc.communicate(timeout=max(0, deadline - time.monotonic()))
                except subprocess.TimeoutExpired:
                    self.fail(f"$ tc {shlex.join(args)} still running {SENDERS_FINISH_CEILING_SECONDS} s "
                              f"after the release")
                if proc.returncode != 0:
                    failed.append(said(args, proc.returncode, out, err))
                numbers += [int(n) for n in SENT.findall(out)]
            self.assertEqual(failed, [], f"{len(failed)} of {SENDERS} sends failed:{''.join(failed)}")
            expected = list(range(1, SENDERS + 1))
            self.assertEqual(sorted(numbers), expected,
                             f"the {SENDERS} sends printed numbers {sorted(numbers)}")
            on_disk = sorted(n for path in inbox_files(root) for n, _, _ in headers(path.read_text()))
            self.assertEqual(on_disk, expected, f"the inbox holds message numbers {on_disk}")
            self.assertEqual(seq.read_text().strip(), str(SENDERS),
                             f"mail/.seq reads {seq.read_text()!r} after {SENDERS} sends")

    def test_k3_the_counter_waits_for_its_lock(self):
        """K3. The counter waits for its flock; and 50 senders at once get exactly 1 to 50.

        Two checks, each its own subtest under a fresh root: the mutation
        test (a send blocked on mail/.seq) and the second check the plan
        asks for (50 senders). See each check's block.

        @interacts  see check_one_send_waits_for_the_seq_lock and
                    check_fifty_senders_get_one_to_fifty.
        @deps       those two.
        @complexity O(S) over S = SENDERS = 50 children.
        @alloc      two TcRoots, one per check, each removed on exit.
        """
        with self.subTest("one send waits for the test's lock on mail/.seq"):
            self.check_one_send_waits_for_the_seq_lock()
        with self.subTest(f"{SENDERS} senders at once get exactly 1 to {SENDERS}"):
            self.check_fifty_senders_get_one_to_fifty()

    def test_k4_wait_exit_codes(self):
        """K4. Mail waiting: 0 and MAIL. None in 1 s: 2 and TIMEOUT. A second wait: 3 and ALREADY LISTENING.

        The first wait for d is the harness's listener, proven in
        /proc/locks; it must still hold the lock after the second wait
        exits. Must reject a wait that returns 0 with no mail: the timeout
        case exits 0.

        @interacts  one send; two waits; one listener; reads /proc/locks.
        @deps       run, _root.TcRoot.listener, _root.flock_holders.
        @complexity O(1); the timeout case waits WAIT_TIMEOUT_SECONDS.
        @alloc      one TcRoot, removed on exit.
        """
        with _root.TcRoot() as root:
            code, out, err, ran = run(root, "send", "--from", A, "--to", B, BODY)
            self.assertEqual(code, 0, ran)
            code, out, err, ran = run(root, "wait", B, "--timeout", str(MAIL_WAIT_TIMEOUT_SECONDS))
            self.assertEqual(code, 0, f"a wait with mail waiting did not exit 0{ran}")
            self.assertTrue(any(line.startswith("MAIL:") for line in lines(out)),
                            f"a wait with mail waiting printed no MAIL: line{ran}")

            code, out, err, ran = run(root, "wait", C, "--timeout", str(WAIT_TIMEOUT_SECONDS))
            self.assertEqual(code, EXIT_TIMEOUT, f"a wait with no mail did not exit {EXIT_TIMEOUT}{ran}")
            self.assertTrue(any(line.startswith("TIMEOUT:") for line in lines(out)),
                            f"a wait with no mail printed no TIMEOUT: line{ran}")

            lock = root.path / "mail" / f".wait-{D}.lock"
            with root.listener(D, LISTENER_TIMEOUT_SECONDS) as first:
                code, out, err, ran = run(root, "wait", D, "--timeout", str(WAIT_TIMEOUT_SECONDS))
                self.assertEqual(code, EXIT_ALREADY_LISTENING,
                                 f"a second wait for {D} did not exit {EXIT_ALREADY_LISTENING}{ran}")
                self.assertIn("ALREADY LISTENING", out, ran)
                holders = _root.flock_holders(lock)
                self.assertIn(first, holders,
                              f"the first wait (pid {first}) no longer holds {lock}; "
                              f"holders: {holders}{ran}")

    def test_k5_log_order_is_by_number_across_inboxes(self):
        """K5. a to b, b to a, a to b: tc log shows #1, #2, #3 in that order.

        The three files' times are then set newest first by number (#1
        newest), as when a sender takes its number and writes after a later
        one. A log sorted by number is unmoved; a log sorted by file time
        comes out #3, #2, #1, so the test rejects it.

        @interacts  three sends; os.utime on the three message files; one log.
        @deps       run, headers, os.utime.
        @complexity O(1).
        @alloc      one TcRoot, removed on exit.
        """
        with _root.TcRoot() as root:
            for sender, to in ((A, B), (B, A), (A, B)):
                code, out, err, ran = run(root, "send", "--from", sender, "--to", to, BODY)
                self.assertEqual(code, 0, ran)
            by_number = {}
            for path in inbox_files(root):
                for n, _, _ in headers(path.read_text()):
                    by_number[n] = path
            self.assertEqual(sorted(by_number), [1, 2, 3], f"message files: {by_number}")
            now = time.time()
            for n, path in by_number.items():
                stamp = now - (n - 1) * MTIME_STEP_SECONDS
                os.utime(path, (stamp, stamp))
            by_time = sorted(by_number, key=lambda n: by_number[n].stat().st_mtime)
            self.assertEqual(by_time, [3, 2, 1], "the test failed to set the file times backward")

            code, out, err, ran = run(root, "log")
            self.assertEqual(code, 0, ran)
            self.assertEqual(headers(out), [(1, A, B), (2, B, A), (3, A, B)],
                             f"tc log is not in number order across inboxes{ran}")

    def test_k6_status_replaces_and_says_none_posted(self):
        """K6. With none posted, tc status says so; a second post replaces the first.

        Must reject an append instead of a replace: the first post would
        still show.

        @interacts  three status shows and two posts; reads status/b.md.
        @deps       run, lines.
        @complexity O(1).
        @alloc      one TcRoot, removed on exit.
        """
        with _root.TcRoot() as root:
            code, out, err, ran = run(root, "status")
            self.assertEqual(code, 0, ran)
            self.assertIn("no status posted", lines(out), f"tc status with none posted{ran}")

            for text in (FIRST_STATUS, SECOND_STATUS):
                code, out, err, ran = run(root, "status", B, text)
                self.assertEqual(code, 0, ran)

            code, out, err, ran = run(root, "status")
            self.assertEqual(code, 0, ran)
            self.assertIn(SECOND_STATUS, lines(out), f"the second post does not show{ran}")
            self.assertNotIn(FIRST_STATUS, lines(out), f"the first post still shows{ran}")
            self.assertEqual(out.count(f"## {B} status"), 1,
                             f"tc status shows {B}'s status header more than once{ran}")
            self.assertNotIn("no status posted", lines(out), ran)
            kept = (root.path / "status" / f"{B}.md").read_text()
            self.assertNotIn(FIRST_STATUS, kept, f"status/{B}.md still holds the first post:\n{kept}")

    def test_k7_empty_message_refused(self):
        """K7. tc send --from a --to b "": exit not 0, stderr says empty message, no file.

        Must reject a send that writes an empty file.

        @interacts  one send; globs the inboxes.
        @deps       run, lines, inbox_files.
        @complexity O(1).
        @alloc      one TcRoot, removed on exit.
        """
        with _root.TcRoot() as root:
            code, out, err, ran = run(root, "send", "--from", A, "--to", B, "")
            self.assertNotEqual(code, 0, f"an empty message was not refused{ran}")
            self.assertIn("tc send: empty message", lines(err), ran)
            files = inbox_files(root)
            self.assertEqual(files, [], f"a refused send left files: {files}{ran}")

    def test_k8_peek_does_not_mark_read(self):
        """K8. Peek b twice, then read b: both peeks and the read show the message.

        Must reject a peek that moves the file: the second peek would show
        nothing.

        @interacts  one send, two peeks, one read under one root.
        @deps       run, headers.
        @complexity O(1).
        @alloc      one TcRoot, removed on exit.
        """
        with _root.TcRoot() as root:
            code, out, err, ran = run(root, "send", "--from", A, "--to", B, BODY)
            self.assertEqual(code, 0, ran)
            box = root.path / "mail" / f"to-{B}"
            for attempt in ("first", "second"):
                code, out, err, ran = run(root, "peek", B)
                self.assertEqual(code, 0, ran)
                self.assertEqual(headers(out), [(1, A, B)],
                                 f"the {attempt} peek does not show message #1{ran}")
                self.assertIn(BODY, lines(out), f"the {attempt} peek does not show the body{ran}")
            unread = sorted(box.glob("*.md"))
            self.assertEqual(len(unread), 1, f"after two peeks {box} holds {unread} unread{ran}")

            code, out, err, ran = run(root, "read", B)
            self.assertEqual(code, 0, ran)
            self.assertEqual(headers(out), [(1, A, B)], f"the read after two peeks lost the message{ran}")
            self.assertIn(BODY, lines(out), ran)


if __name__ == "__main__":
    unittest.main()
