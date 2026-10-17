"""
The class proof of D35's one pinned handle (P3 fix round 1a, item 2):
for each command family that acts on an inbox, or on an outbox branch it
counts, the member who owns that folder swaps it, just after tc first
looked at it, for a link to a folder outside the mailbox or for another
real folder of that member's. tc must never write, read, move, print,
count or date anything at the far end of the swap, and must do its act in
the folder it opened.

Model:  Claude Opus 5.5 (the P3 fixer, round 1a), 2026-10-15
Status: unreviewed

The audit's HIGH-1 and REC-1 (audits/2026-10-15-1409-full: test-strategist
REC-1, breaker REC-1), and known bug no-follow-open-guards-only-the-last-
name on the live paths. One row per family, four for (g) and three for (i):
(a) tc send (deliver_local, publish_message); (b) the far gate (cmd_gate
through route_and_deliver, forward False); (c) tc peek; (d) tc read; (e)
tc wait's poll (unread); (f) tc log; (g) tc health --json and the gate's
health --json (mailbox_summary), and, since P3 fix round 2 (Claude Opus
5.5, unreviewed: test-strategist REC-4), tc health's listeners and its
held_by_others, each over an inbox whose far end holds wait and watch
locks a child holds; (h) tc flush's count over other members' branches
(other_branches, outbox_files); (i) unread_count and its callers: tc card,
a codex tc join, and a codex send's ring decision; (j) the board's own
scan (board/serve.py, scan_messages); (k) tc health's stuck_outbox over
another member's branch, whose far end holds a note of its own beside the
queued message's name (P3 fix round 2, REC-4); (l) the wait exit records'
one read, wait_exits, which tc health, tc watch and the board share, over
an inbox whose far end holds an exit record of its own (F1, Claude Opus
5.5, unreviewed). Row (e)'s real inbox holds the wait's exit record beside
its lock since F1: the record goes in the folder the lock was taken in.

Known gap: the family list is hardcoded. A command added later that
touches an inbox or a branch is not covered until someone adds its row.
P3 fix round 2 (Claude Opus 5.5, unreviewed: test-strategist REC-15):
that gap is now a red test. EveryInboxActHasARowTest reads tc with
Python's ast and fails for any function that calls pinned_inbox,
open_inbox or pin_folder and is neither covered by a row (COVERED) nor
exempt with a reason (EXEMPT).

One Linux user plays every part. The mailbox is shared with the user's
primary group by tc init under the harness's own TC_ROOT, and ROOT and its
.shared are reported as the init user's (test_shared.as_member, which
patches os.lstat and os.fstat), so the running user is a member, never the
init user. That member owns the inbox (it joined as OWNER) and makes the
swap, as an entry's owner may in the sticky mail/ and outbox/ (D34: tc
protects members from each other, and this actor is a member). The same
user then runs the command as another member would.

The swap is made by wrapping os.open, os.lstat and os.stat
(swap_after_first_look): the first call aimed at the inbox, or the branch,
returns, and only then is the folder renamed aside (a dot name nothing
lists) and a link to the outside folder, or the other folder, put at its
name. Under D35 that first look is tc's pinned open, so every later act
must happen in the folder it opened. tc join's first look is
claim_inbox's lstat of the joiner's own inbox, which only that owner
could race against itself; its row waits for the first open,
unread_count's pin, the act under test. P3 fix round 1b (Claude Opus
5.5, unreviewed): tc wait's first look is now hold_wake_lock's pin, which
opens the inbox to take the wait lock in it (D35 (1)); its row lets that
one look pass (Row.skip) and swaps after the poll's own pin, the act
under test. The two health rows let two pass the same way: listeners
opens the inbox first, once for its wait lock and once for its watch
lock, and mailbox_summary's pin, the act under test, comes third. P3 fix
round 2 (Claude Opus 5.5, unreviewed): listeners' row swaps after the
first of those, and held_by_others' row lets three pass, since its own
pin comes after mailbox_summary's.

Each subtest asserts, in this order: the swap happened; the far end's
tree is unchanged (names, kinds, sizes, modify and change times); nothing
tc printed quotes a planted file or names its sender; then the row's own
counts and ages, which must equal the real inbox's, and what the real
inbox (moved aside, still pinned) holds after the act.

@interacts  runs ../tc through tests/_root.py under a throwaway TC_ROOT for
            the setup (init, joins, sends, a read, a card), with a fake
            `codex` first on PATH for the codex rows; makes folders and
            files outside TC_ROOT in the root's temp folder, sets their
            times (os.utime), and makes folders and a file under outbox/
            by hand for the branch row; loads tc as a module (TC_ROOT set
            for the load and put back) and runs one command in process
            with os.open, os.lstat and os.stat wrapped (the swap),
            os.lstat and os.fstat patched (as_member), PATH set to the
            root's for the call, stdout and stderr captured, and, per row,
            SSH_ORIGINAL_COMMAND, CODEX_THREAD_ID, sys.stdin,
            resource.setrlimit (a no-op, so the wait never caps this
            process) or tc's gpu_stats (no nvidia-smi run) patched; loads
            board/serve.py and calls scan_messages for the board row, and
            since P3 fix round 1c (Claude Opus 5.5, unreviewed: round 1a's
            MEDIUM) file_age and file_time on each message while the
            scan's folders are held open, as feed() holds them; the
            swap renames one folder in the root and makes a link or moves
            a folder in; lstats every entry of the far end before and
            after. Writes nothing outside the root's temp folder. (P3 fix
            round 1b, Claude Opus 5.5, unreviewed: tc wait closes its lock
            file on every way out now, so the garbage collection with
            ResourceWarning ignored that round 1a needed is gone.) P3 fix
            round 2 (Claude Opus 5.5, unreviewed): for the two lock rows,
            starts one child per planted lock (test_wake_files.hold), each
            holding its flock until the harness kills it by its pid, and
            for held_by_others' row patches os.stat so each holder's
            /proc/<pid> reads as another member's; for the stuck row,
            writes a note beside the real queued message and replaces
            tc's wall_clock. F1 (Claude Opus 5.5, unreviewed): for the
            exit records' row, one more tc wait in the setup and a
            record planted in each far end, and tc's wait_exits called in
            process. EveryInboxActHasARowTest reads ../tc's text and
            parses it; it runs nothing.
@deps       python3 stdlib (argparse, ast, collections, contextlib,
            importlib, io, json, os, pathlib, resource, stat, sys, time,
            unittest, unittest.mock); tests/_root.py; UmaskTestCase, as_member,
            load_tc and primary_group from test_shared.py; hold,
            holder_patched_stat and HOLDER_UID_STEP from
            test_wake_files.py; ../tc; ../board/serve.py.
@complexity O(r x k) subtests over r = 17 rows and k = 2 kinds of swap,
            each a fresh root with four to seven tc runs of setup, up to
            four lock holders, and one command in process over a mailbox
            of a dozen entries.
@alloc      one TcRoot, one tc module and two small trees outside the root
            per subtest, all removed with the root; up to four children
            per subtest, killed with it.
"""

import argparse
import ast
import collections
import contextlib
import importlib.util
import io
import json
import os
import pathlib
import resource
import stat
import sys
import time
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
# Run as `python3 -m unittest tests.test_inbox_pinned` from the repo root,
# tests/ is not on sys.path; under discover it is. Add it once so both work.
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import _root  # noqa: E402  (needs the path line above)
from test_shared import UmaskTestCase, as_member, load_tc, primary_group  # noqa: E402
from test_wake_files import HOLDER_UID_STEP, hold, holder_patched_stat  # noqa: E402

SERVE_PATH = HERE.parent / "board" / "serve.py"
# The member who owns the inbox and makes the swap, and the member who
# sends to it. Made-up names.
OWNER = "ann"
SENDER = "ben"
# The name the far gate delivers as (its --as), and the made-up far tc
# path the far side's command starts with (the gate ignores it).
FAR_KEY = "farkey"
FAR_TC = "/x/tc"
# The body of the real message ben sent ann during setup, and of the one
# the act sends.
REAL_TEXT = "real mail from ben to ann"
SENT_TEXT = "a new message the act sends"
# Every planted file outside the mailbox holds this text and is from this
# made-up sender, so no word of tc's output may quote the one or name the
# other.
PLANTED_TEXT = "PLANTED outside the mailbox: tc must never read, move or count this"
PLANTED_SENDER = "mallory"
# What a planted inbox holds, by name under the folder a link leads to (or
# the folder moved in): a file at the real unread message's own name, so
# an act by path finds one there, a second message and one in read/, so
# a count by path differs from the real inbox's.
INBOX_PLANT = (("000001-from-ben.md", PLANTED_TEXT), (f"000077-from-{PLANTED_SENDER}.md", PLANTED_TEXT),
               (f"read/000078-from-{PLANTED_SENDER}.md", PLANTED_TEXT))
# The branch row: another member's branch, its one real queued message,
# and a planted branch holding two, so a count by path says two.
OTHER_MEMBER = "ben-member"
FAR_NAME = "far-b"
QUEUED_NAME = f"000005-from-{OTHER_MEMBER}.md"
BRANCH_PLANT = ((f"to-{FAR_NAME}/000077-from-{PLANTED_SENDER}.md", PLANTED_TEXT),
                (f"to-{FAR_NAME}/000078-from-{PLANTED_SENDER}.md", PLANTED_TEXT))
# A made-up ssh target for far-b's card and for tc card; no ssh ever runs.
SSH_TARGET = "u@h"
REMOTE_TC = "~/TheConnection/tc"
# The codex rows' thread id and the account a codex join writes, made up.
THREAD = "t1"
ACCOUNT = "made-up-account"
# How old the real mail is, and how old every planted file is, in seconds,
# so an age taken at the far end shows. The slack covers the seconds
# between setting the times and tc's reading them.
REAL_AGE_SECONDS = 1000
PLANTED_AGE_SECONDS = 100000
AGE_SLACK_SECONDS = 5
# How long the wait row's tc wait may run: its first poll comes at once
# and finds the real message.
WAIT_SECONDS = 1.0
# The two kinds of swap, and where the real folder is moved aside to: a
# dot name, which no listing of to-* entries or branches reads.
LINK, REAL_FOLDER = "link", "real folder"
ASIDE_PREFIX = ".aside-"
# The os calls a swap waits on. "The first look" is the first of them
# aimed at the folder; tc join's row waits on os.open alone (module block).
LOOKS = ("open", "lstat", "stat")
OPENS = ("open",)
# The ring marker's first line after a codex join finds unread mail.
JOINED_STATE = "joined with unread mail"
# P3 fix round 1b (Claude Opus 5.5, unreviewed): the wait lock's name in
# its owner's own inbox (D35 (1)), written here rather than read from tc.
WAIT_LOCK = ".wait.lock"
# What run_in_process hands back: the exit code (0 when the call
# returned, the words of an exception it raised), stdout, stderr, and
# what the call returned.
Ran = collections.namedtuple("Ran", "code out err value")
# P3 fix round 1b (Claude Opus 5.5, unreviewed): how many times health's
# listeners opens an inbox before mailbox_summary does: once for the wait
# lock in it and once for the watch lock (D35 (1)).
LISTENER_LOOKS = 2
# P3 fix round 2 (Claude Opus 5.5, unreviewed): test-strategist REC-4. The
# watch lock's name beside WAIT_LOCK; how many of health's looks at an
# inbox come before held_by_others' own (listeners twice, mailbox_summary
# once); the first line of the note beside the real queued message, and
# the note's ending (tc's REFUSAL_NOTE_SUFFIX, written here); and how far
# past now the stuck row's replaced clock stands: a day and an hour
# (tc's OUTBOX_STALE_SECONDS plus an hour), so the real queued message has
# waited past the bound.
WATCH_LOCK = ".watch.lock"
HELD_BY_OTHERS_LOOKS = LISTENER_LOOKS + 1
REAL_NOTE = "real note: the last failed try's words"
NOTE_SUFFIX = ".stderr"
STALE_SHIFT_SECONDS = 86400 + 3600
# F1 (Claude Opus 5.5, unreviewed): the wait exit record's name beside
# WAIT_LOCK (tc's WAIT_EXIT_NAME, written here), the word a wait that finds
# mail writes there, and the record the far ends of the exit records' row
# hold: a real record's form, so a read that reaches a far end would take
# it, with a made-up word and date no real record in this test has.
WAIT_EXIT = ".wait.exit"
WAIT_EXIT_MAIL = "mail"
PLANTED_EXIT = "timeout 2001-09-09T01:46:40+00:00\n"
PLANTED_EXIT_WORD = "timeout"
# One row: its family, its label, whether it swaps an inbox or a branch,
# whether ann joins as codex, whether ann's message is read in setup, the
# os calls its swap waits on, what it patches for its call, and how many
# looks at the folder it lets pass before the one it swaps after (P3 fix
# round 1b, Claude Opus 5.5, unreviewed: tc wait's lock pin comes first).
# P3 fix round 2 (Claude Opus 5.5, unreviewed): REC-4. The lock names its
# far ends hold, each held by a child; whose process those children read
# as ("owner", ann's, or "member", another member's); and how many seconds
# past now tc's wall_clock reads (the stuck row). F1 (Claude Opus 5.5,
# unreviewed): the exit record its far ends hold, when set, and then ann's
# own wait runs in the setup, so her real inbox holds a real record.
Row = collections.namedtuple("Row", "family label target codex read_first looks environ stdin skip locks holder late "
                                    "exit_record", defaults=(0, (), "owner", 0, None))
# Real os.lstat, bound once here, so the patches in place while a swap
# runs never color what the far end looks like.
REAL_LSTAT = os.lstat


def load_serve():
    """Load board/serve.py as a module, as the board tests do.

    @interacts  executes serve.py's top level (constants and definitions).
    @deps       importlib; SERVE_PATH.
    @complexity O(1).
    @alloc      one module object, returned.
    """
    spec = importlib.util.spec_from_file_location("board_serve_pinned", SERVE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


serve = load_serve()


def snapshot(top):
    """What lstat says of `top` and every entry under it: {path relative to `top`: (kind, size, modify ns, change ns)}. A link is never followed.

    @interacts  lstats `top` and lists every folder under it (os.walk,
                which never descends a link), lstatting each entry.
                Writes nothing.
    @deps       os, pathlib, stat; REAL_LSTAT.
    @complexity O(e) over e entries (a handful).
    @alloc      one dict, returned.
    """
    def seen(path):
        st = REAL_LSTAT(path)
        kind = "folder" if stat.S_ISDIR(st.st_mode) else "file" if stat.S_ISREG(st.st_mode) else "other"
        return kind, st.st_size, st.st_mtime_ns, st.st_ctime_ns
    out = {".": seen(top)}
    for folder, folders, files in os.walk(top):
        for name in folders + files:
            path = pathlib.Path(folder) / name
            out[str(path.relative_to(top))] = seen(path)
    return out


def plant(top, layout, age):
    """Make the folder `top` and each (relative path, text) of `layout` in it, every file dated `age` seconds ago.

    @interacts  makes folders and files; sets each file's times.
    @deps       os, pathlib, time.
    @complexity O(f) over f files (two or three).
    @alloc      the folders and files, removed with the root's temp folder.
    """
    top.mkdir()
    stamp = time.time() - age
    for rel, text in layout:
        path = top / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        os.utime(path, (stamp, stamp))


def files_in(folder):
    """The names of the files directly in `folder`, sorted; [] when it is not there.

    @interacts  lists one folder.
    @deps       pathlib.
    @complexity O(f) over f entries.
    @alloc      one list, returned.
    """
    return sorted(p.name for p in folder.iterdir() if p.is_file()) if folder.is_dir() else []


@contextlib.contextmanager
def swap_after_first_look(target, swap, looks, skip=0):
    """While entered, os.open, os.lstat and os.stat (those named in `looks`) are wrapped: the first call aimed at `target` returns, and then `swap` runs, once. Yields the list of where that call was aimed (empty until it happens). `skip` calls aimed at `target` pass first, untouched (P3 fix round 1b, Claude Opus 5.5, unreviewed).

    Where a call is aimed: by a name in a folder's descriptor, that
    folder's path now (/proc/self/fd) and the name; by a path, the path
    made absolute, links not read (no lstat runs here, so the wrap never
    calls itself). `target` matches as given and by its real path, taken
    before anything is swapped.

    @interacts  patches up to three os functions; reads /proc/self/fd;
                calls `swap` once.
    @deps       contextlib, os, pathlib, unittest.mock.
    @complexity O(1) per wrapped call.
    @alloc      one list, holding at most one path; one counter.
    """
    given, real = pathlib.Path(target), pathlib.Path(os.path.realpath(target))
    made, passed = [], [0]

    def wrap(call):
        def wrapped(path, *args, **kwargs):
            result = call(path, *args, **kwargs)
            if not made and not isinstance(path, int):
                dir_fd = kwargs.get("dir_fd")
                aimed = (pathlib.Path(os.readlink(f"/proc/self/fd/{dir_fd}")) / os.fsdecode(path)
                         if dir_fd is not None else pathlib.Path(os.path.abspath(os.fsdecode(path))))
                if aimed in (given, real):
                    if passed[0] < skip:
                        passed[0] += 1
                        return result
                    made.append(aimed)
                    swap()
            return result
        return wrapped

    with contextlib.ExitStack() as stack:
        for name in looks:
            stack.enter_context(mock.patch.object(os, name, wrap(getattr(os, name))))
        yield made


def run_in_process(call):
    """Run `call` with stdout and stderr captured: a Ran.

    A SystemExit gives its code; any other exception is the run's result
    in words (its type and message as the code), so the assertions that
    come first, on the far end and on what was printed, still say what
    the run did before it.

    @interacts  runs `call`; captures stdout and stderr.
    @deps       contextlib, io; Ran.
    @complexity O(1), plus the call.
    @alloc      the captured text, returned.
    """
    out, err = io.StringIO(), io.StringIO()
    code, value = 0, None
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            value = call()
        except SystemExit as stop:
            code = 0 if stop.code is None else stop.code
        except Exception as error:  # a traceback is the run's result here, read after the far end is checked
            code = f"raised {type(error).__name__}: {error}"
    return Ran(code, out.getvalue(), err.getvalue(), value)


# P3 fix round 1c (Claude Opus 5.5, unreviewed): round 1a's MEDIUM, row (j) dates too.
def board_scan_and_dates(mail):
    """The board's scan of `mail` and the age and time feed() gives each message, with the scan's folders held open in between as feed() holds them: (messages, unreadable, {file name: (file_age, file_time)}).

    @interacts  see serve.scan_messages, serve.file_age and
                serve.file_time; reads the clock.
    @deps       serve; contextlib, os, time.
    @complexity O(m) over m messages (one or two).
    @alloc      the scan's lists and one dict, returned.
    """
    now = time.time()
    with contextlib.ExitStack() as held:
        messages, unreadable = serve.scan_messages(mail, held)
        dates = {os.path.basename(msg.path): (serve.file_age(msg.path, now), serve.file_time(msg.path))
                 for msg in messages}
    return messages, unreadable, dates


def text_stdin(text):
    """A sys.stdin stand-in holding `text` as UTF-8 bytes, as the gate reads it (sys.stdin.buffer).

    @interacts  none.
    @deps       io.
    @complexity O(t) over t characters.
    @alloc      one text wrapper over a bytes buffer, returned.
    """
    return io.TextIOWrapper(io.BytesIO(text.encode("utf-8")), encoding="utf-8")


ROWS = (
    Row("a", "tc send", "inbox", False, False, LOOKS, {}, None),
    Row("b", "the far gate's send", "inbox", False, False, LOOKS,
        {"SSH_ORIGINAL_COMMAND": f"{FAR_TC} send --from someone --to {OWNER}"}, SENT_TEXT),
    Row("c", "tc peek", "inbox", False, False, LOOKS, {}, None),
    Row("d", "tc read", "inbox", False, False, LOOKS, {}, None),
    Row("e", "tc wait's poll", "inbox", False, False, LOOKS, {}, None, skip=1),
    Row("f", "tc log", "inbox", False, False, LOOKS, {}, None),
    Row("g", "tc health --json", "inbox", False, False, LOOKS, {}, None, skip=LISTENER_LOOKS),
    Row("g", "the gate's health --json", "inbox", False, False, LOOKS,
        {"SSH_ORIGINAL_COMMAND": f"{FAR_TC} health --json"}, "", skip=LISTENER_LOOKS),
    # P3 fix round 2 (Claude Opus 5.5, unreviewed): REC-4, health's own looks at an inbox.
    Row("g", "tc health's listeners", "inbox", False, False, LOOKS, {}, None, locks=(WAIT_LOCK,)),
    Row("g", "tc health's held_by_others", "inbox", False, False, LOOKS, {}, None, skip=HELD_BY_OTHERS_LOOKS,
        locks=(WAIT_LOCK, WATCH_LOCK), holder="member"),
    Row("h", "tc flush's count of other members' branches", "branch", False, False, LOOKS, {}, None),
    Row("i", "tc card", "inbox", False, False, LOOKS, {}, None),
    Row("i", "a codex tc join", "inbox", False, False, OPENS, {"CODEX_THREAD_ID": THREAD}, None),
    Row("i", "a codex send's ring decision", "inbox", True, True, LOOKS, {}, None),
    Row("j", "the board's scan", "inbox", False, False, LOOKS, {}, None),
    # P3 fix round 2 (Claude Opus 5.5, unreviewed): REC-4, health's look into another member's branch.
    Row("k", "tc health's stuck_outbox over another member's branch", "branch", False, False, LOOKS, {}, None,
        late=STALE_SHIFT_SECONDS),
    # F1 (Claude Opus 5.5, unreviewed): the wait exit records' one read, which tc health, tc watch and the board share.
    Row("l", "the exit records' read (wait_exits)", "inbox", False, False, LOOKS, {}, None, exit_record=PLANTED_EXIT),
)
# P3 fix round 2 (Claude Opus 5.5, unreviewed): test-strategist REC-15
# (synthesis REC-17), the family list's known gap made a red test. The
# calls that pin an inbox or a branch; every function in tc that makes one
# of them, by the rows of ROWS whose act reaches it; and every other such
# function, with why no row needs to swap under it. A function added to
# tc that pins a folder, and is in neither, fails
# test_every_inbox_act_in_tc_has_a_row_or_a_named_exemption until someone
# gives it a row or a reason.
PIN_CALLS = ("pinned_inbox", "open_inbox", "pin_folder")
COVERED = {
    "deliver_local": ("tc send", "the far gate's send"),
    "cmd_peek": ("tc peek",),
    "cmd_read": ("tc read",),
    "unread": ("tc wait's poll",),
    "cmd_log": ("tc log",),
    "mailbox_summary": ("tc health --json", "the gate's health --json"),
    "listeners": ("tc health's listeners",),
    "held_by_others": ("tc health's held_by_others",),
    "other_branches": ("tc flush's count of other members' branches",),
    "outbox_files": ("tc flush's count of other members' branches",
                     "tc health's stuck_outbox over another member's branch"),
    "unread_count": ("tc card", "a codex tc join", "a codex send's ring decision"),
    "ring_doorbell": ("a codex send's ring decision",),
    "stuck_outbox": ("tc health's stuck_outbox over another member's branch",),
    "wait_exits": ("the exit records' read (wait_exits)",),  # F1 (Claude Opus 5.5, unreviewed)
}
EXEMPT = {
    "pin_folder": "the pin itself: one folder opened by its name in an open folder, never through a link",
    "open_inbox": "a pin helper: an inbox and its read/, each through pin_folder; every row reaches it",
    "pinned_inbox": "a pin helper: mail/ opened by its path (the init user's, D34), then open_inbox",
    "inbox_made": ("a private mailbox's send making the inbox it then pins by name in mail/'s descriptor; on a "
                   "shared mailbox, where another member could swap an inbox, it makes and opens nothing (D20)"),
    "hold_wake_lock": ("only the inbox's owner runs it on a shared mailbox (D36 (2)), so the only member who could "
                       "swap the inbox is the one running it; WakeFilesAreTheirOwnersTest covers its lock"),
    "deliver_ssh": ("the sender's own outbox branch, 2750, which no other member can write in (D32, D33); only "
                    "the sender or the init user can swap a level of it (D34, DEBT-1)"),
}


class InboxPinnedTest(UmaskTestCase):
    """D35's class proof: no member swapping their own inbox or branch mid-command ever leads another member's tc outside the folder it opened.

    @interacts  see the module block.
    @deps       _root.TcRoot, UmaskTestCase, primary_group, as_member,
                load_tc, swap_after_first_look, run_in_process, snapshot,
                plant, files_in, text_stdin, serve; ROWS.
    @complexity O(r x k): see the module block.
    @alloc      one TcRoot per subtest.
    """

    def build(self, root, row, group):
        """The shared mailbox for one subtest: init, the two members joined, ben's message to ann (read in setup when the row says), every real message dated REAL_AGE_SECONDS ago; for the branch rows, another member's branch with one queued message and far-b's ssh card, and for the stuck row (P3 fix round 2) a note beside that message. (the folder to swap, the codex fake's calls or None).

        @interacts  six or seven tc runs; for a codex row, a fake codex
                    first on the root's PATH; makes the branch by hand for
                    the branch rows, and the note for the stuck row; sets
                    file times.
        @deps       _root.TcRoot.tc, fake_bin; os, time.
        @complexity O(1).
        @alloc      the mailbox's files, removed with the root.
        """
        calls = None
        if row.codex:
            _, calls = root.fake_bin("codex", 0)
        owner_env = {"CODEX_THREAD_ID": THREAD, "CLAUDECODE": None} if row.codex else {"CLAUDECODE": "1"}
        setup = [root.tc("init", "--shared", "--group", group),
                 root.tc("join", OWNER, "--account", ACCOUNT, env=owner_env),
                 root.tc("join", SENDER, "--account", ACCOUNT, env={"CLAUDECODE": "1"}),
                 root.tc("send", "--from", SENDER, "--to", OWNER, REAL_TEXT)]
        if row.read_first:
            setup.append(root.tc("read", OWNER))
        if row.exit_record is not None:  # F1 (Claude Opus 5.5, unreviewed): ann's wait finds ben's mail and says so
            setup.append(root.tc("wait", OWNER, "--timeout", str(WAIT_SECONDS)))
        if row.target == "branch":
            setup.append(root.tc("card", FAR_NAME, "--ssh", SSH_TARGET))
        for code, out, err in setup:
            self.assertEqual(code, 0, f"setup: {out}{err}")
        stamp = time.time() - REAL_AGE_SECONDS
        for path in (root.path / "mail").rglob("*.md"):
            os.utime(path, (stamp, stamp))
        if row.target == "branch":
            queue = root.path / "outbox" / OTHER_MEMBER / f"to-{FAR_NAME}"
            queue.mkdir(parents=True)
            (queue / QUEUED_NAME).write_text(f"# #5 from {OTHER_MEMBER} to {FAR_NAME}\n\nqueued\n")
            os.utime(queue / QUEUED_NAME, (stamp, stamp))
            if row.late:  # P3 fix round 2 (Claude Opus 5.5, unreviewed): REC-4, the note a failed try left
                (queue / f"{QUEUED_NAME}{NOTE_SUFFIX}").write_text(f"{REAL_NOTE}\nwhat ssh said\n")
            return root.path / "outbox" / OTHER_MEMBER, calls
        return root.path / "mail" / f"to-{OWNER}", calls

    def act(self, tc, root, row):
        """The one command a row runs in process, as a callable for run_in_process.

        @interacts  none until called; see the module block.
        @deps       argparse; tc's cmd_* functions; serve.scan_messages.
        @complexity O(1).
        @alloc      one closure, returned.
        """
        commands = {
            "tc send": lambda: tc.cmd_send(argparse.Namespace(sender=SENDER, to=OWNER, message=SENT_TEXT,
                                                              origin=None)),
            "the far gate's send": lambda: tc.cmd_gate(argparse.Namespace(as_name=FAR_KEY)),
            "tc peek": lambda: tc.cmd_peek(argparse.Namespace(name=OWNER)),
            "tc read": lambda: tc.cmd_read(argparse.Namespace(name=OWNER)),
            "tc wait's poll": lambda: tc.cmd_wait(argparse.Namespace(name=OWNER, timeout=WAIT_SECONDS,
                                                                     keepalive=False)),
            "tc log": lambda: tc.cmd_log(argparse.Namespace(last=0)),
            "tc health --json": lambda: tc.cmd_health(argparse.Namespace(json=True)),
            "the gate's health --json": lambda: tc.cmd_gate(argparse.Namespace(as_name=FAR_KEY)),
            "tc health's listeners": lambda: tc.cmd_health(argparse.Namespace(json=True)),
            "tc health's held_by_others": lambda: tc.cmd_health(argparse.Namespace(json=True)),
            "tc health's stuck_outbox over another member's branch":
                lambda: tc.cmd_health(argparse.Namespace(json=True)),
            "tc flush's count of other members' branches": lambda: tc.cmd_flush(argparse.Namespace(to=None)),
            "tc card": lambda: tc.cmd_card(argparse.Namespace(name=OWNER, ssh=SSH_TARGET, remote_tc=REMOTE_TC,
                                                              account=None, reports_to=None, force=False)),
            "a codex tc join": lambda: tc.cmd_join(argparse.Namespace(name=OWNER, account=ACCOUNT, kind=None,
                                                                      reports_to=None)),
            "a codex send's ring decision": lambda: tc.cmd_send(argparse.Namespace(sender=SENDER, to=OWNER,
                                                                                   message=SENT_TEXT, origin=None)),
            "the board's scan": lambda: board_scan_and_dates(root.path / "mail"),
            "the exit records' read (wait_exits)": lambda: tc.wait_exits([OWNER]),  # F1 (Claude Opus 5.5, unreviewed)
        }
        return commands[row.label]

    def check(self, row, root, ran, real, calls, held=()):
        """The row's own assertions, after the common ones: counts and ages equal the real inbox's (or branch's), and the real one, at `real`, holds what the act should have put there. `held` holds the pids of the children holding the far ends' locks (P3 fix round 2).

        @interacts  reads files under the root; reads the fake codex's
                    record for the codex row.
        @deps       files_in; json; the module's constants.
        @complexity O(1).
        @alloc      the text read, freed on return.
        """
        box = root.path / "mail" / f"to-{OWNER}"
        # P3 fix round 2 (Claude Opus 5.5, unreviewed): REC-4. The real inbox holds no wait or watch lock, and
        # the real branch's message waits past the bound with its own note: nothing at the far end counts.
        if row.label == "tc health's listeners":
            self.assertEqual((ran.code, ran.err), (0, ""))
            listening = json.loads(ran.out)["listeners"]
            self.assertIsNone(listening.get(OWNER), f"health named a listener for {OWNER} from a lock outside her "
                                                    f"inbox: {listening}")
            self.assertFalse(set(held) & set(listening.values()), f"health named a far end's holder: {listening}")
            return
        if row.label == "tc health's held_by_others":
            self.assertEqual((ran.code, ran.err), (0, ""))
            self.assertEqual(json.loads(ran.out)["held_by_others"], [],
                             "health listed a lock held at the far end, outside the inbox it opened")
            return
        if row.family == "l":  # F1 (Claude Opus 5.5, unreviewed): the record read is the real inbox's, never a far end's
            self.assertEqual((ran.code, ran.err), (0, ""))
            words = {name: record.word for name, record in (ran.value or {}).items()}
            self.assertEqual(words, {OWNER: WAIT_EXIT_MAIL}, f"the exit record read is not the real inbox's "
                                                             f"(a far end's says {PLANTED_EXIT_WORD}): {ran.value}")
            self.assertLessEqual(abs(ran.value[OWNER].at - time.time()), REAL_AGE_SECONDS,
                                 f"the exit record's time is not the real one's: {ran.value}")
            return
        if row.family == "k":
            self.assertEqual((ran.code, ran.err), (0, ""))
            stuck = json.loads(ran.out)["stuck_outbox"]
            queued = root.path / "outbox" / OTHER_MEMBER / f"to-{FAR_NAME}" / QUEUED_NAME
            self.assertEqual([(entry["member"], entry["to"], entry["path"], entry["note"]) for entry in stuck],
                             [(OTHER_MEMBER, FAR_NAME, str(queued), REAL_NOTE)],
                             "health's stuck line is not the real branch's message and note")
            self.assertLessEqual(abs(stuck[0]["age_s"] - REAL_AGE_SECONDS - row.late), AGE_SLACK_SECONDS,
                                 f"the stuck message's age is not the real one's: {stuck}")
            return
        if row.label in ("tc send", "the far gate's send"):
            sender = SENDER if row.label == "tc send" else FAR_KEY
            name = f"000002-from-{sender}.md"
            # P3 fix round 2 (Claude Opus 5.5, unreviewed): D37 (1), the gate names the path relative to the mailbox.
            shown = box.relative_to(root.path) if row.label == "the far gate's send" else box
            self.assertEqual((ran.code, ran.out, ran.err), (0, f"sent #2 to {OWNER}: {shown / name}\n", ""))
            self.assertEqual(files_in(real), ["000001-from-ben.md", name], "the message did not land in the real inbox")
            self.assertIn(SENT_TEXT, (real / name).read_text())
        elif row.label == "tc peek":
            self.assertTrue(ran.out.startswith(f"1 unread for {OWNER}\n"), ran.out)
            self.assertIn(REAL_TEXT, ran.out, "tc peek did not show the real message")
            self.assertEqual((ran.code, ran.err), (0, ""))
            self.assertEqual(files_in(real), ["000001-from-ben.md"])
        elif row.label == "tc read":
            self.assertIn(REAL_TEXT, ran.out, "tc read did not show the real message")
            self.assertEqual((ran.code, ran.err), (0, ""))
            self.assertEqual((files_in(real), files_in(real / "read")), ([], ["000001-from-ben.md"]),
                             "tc read did not move the real message into the real read/")
        elif row.label == "tc wait's poll":
            self.assertEqual((ran.code, ran.out), (0, f"MAIL: 1 unread for {OWNER}. Run: tc read {OWNER}\n"))
            # F1 (Claude Opus 5.5, unreviewed): the exit record sits beside the lock, in the folder the lock is in.
            self.assertEqual(files_in(real), [WAIT_EXIT, WAIT_LOCK, "000001-from-ben.md"],
                             "the wait's lock and exit record are not in the real inbox beside its mail (D35 (1), F1)")
            self.assertEqual((real / WAIT_EXIT).read_text().partition(" ")[0], WAIT_EXIT_MAIL,
                             "the real inbox's exit record does not say the wait ended on mail")
        elif row.label == "tc log":
            self.assertIn(REAL_TEXT, ran.out, "tc log did not show the real message")
            self.assertEqual((ran.code, ran.err), (0, ""))
        elif row.family == "g":
            self.assertEqual((ran.code, ran.err), (0, ""))
            mine = json.loads(ran.out)["mail"][OWNER]
            # P3 fix round 1c (Claude Opus 5.5, unreviewed): the gate's health gives no mail_problem (D36 (5)).
            self.assertEqual((mine["unread"], mine.get("mail_problem")), (1, None), mine)
            self.assertLessEqual(abs(mine["newest_mail_age_s"] - REAL_AGE_SECONDS), AGE_SLACK_SECONDS,
                                 f"the newest mail's age is not the real inbox's: {mine}")
        elif row.target == "branch":
            self.assertIn(f"1 waiting for {SSH_TARGET} from other members", ran.out,  # P3 fix round 1c: LOW-16
                          "flush's count is not the real branch's")
            self.assertEqual((ran.code, ran.err), (0, ""))
            self.assertEqual(files_in(real / f"to-{FAR_NAME}"), [QUEUED_NAME])
        elif row.label == "tc card":
            self.assertIn(f"tc card: {OWNER} has 1 unread here.", ran.err, "tc card's count is not the real inbox's")
            self.assertEqual(ran.code, 1)
            card = json.loads((root.path / "cards" / f"{OWNER}.json").read_text())
            self.assertEqual(card["route"], "local", "a refused tc card wrote the card")
        elif row.label == "a codex tc join":
            self.assertIn(f"1 unread waiting for {OWNER}: run tc read {OWNER}", ran.out,
                          "the join's count is not the real inbox's")
            self.assertEqual((ran.code, ran.err), (0, ""))
            marker = (root.path / "mail" / f".ring-pending-{OWNER}").read_text().partition("\n")[0]
            self.assertEqual(marker, JOINED_STATE)
        elif row.codex:
            record = calls()
            self.assertTrue(record, "the fake codex never ran, not even in setup")
            self.assertEqual(len(record), 2, f"the send did not ring once more: the ring decision read another "
                                             f"folder's count. Calls: {record}")
            self.assertIn(f"MAIL: 1 unread for {OWNER}.", record[-1]["argv"][-1],
                          "the ring's count is not the real inbox's")
            self.assertEqual(ran.code, 0, ran.err)
            self.assertIn(f"sent #2 to {OWNER}: {box / '000002-from-ben.md'}", ran.out)
            self.assertEqual(files_in(real), ["000002-from-ben.md"], "the message did not land in the real inbox")
        else:
            messages, unreadable, dates = ran.value
            self.assertEqual(sorted((m.to, m.seq, m.sender, m.read) for m in messages),
                             [(OWNER, 1, SENDER, False)], "the board's scan is not the real inbox's")
            self.assertEqual((ran.code, unreadable), (0, set()))
            # P3 fix round 1c (Claude Opus 5.5, unreviewed): round 1a's MEDIUM, the times shown are the real inbox's.
            age, when = dates.get("000001-from-ben.md", (None, None))
            self.assertLessEqual(abs((age if age is not None else 0) - REAL_AGE_SECONDS), AGE_SLACK_SECONDS,
                                 f"the board's age of the message is not the real inbox's: {dates}")
            self.assertLessEqual(abs(time.time() - REAL_AGE_SECONDS - (when or 0)), AGE_SLACK_SECONDS,
                                 f"the board's time of the message is not the real inbox's: {dates}")

    def test_a_member_swapping_its_inbox_mid_command_never_leads_tc_outside(self):
        """For every row of ROWS and both kinds of swap (a link to a folder outside the mailbox, another real folder moved in), made by the folder's owner just after tc first looked at it: the far end keeps its tree, nothing printed quotes a planted file or names its sender, and every count, age and landing is the real folder's.

        D35's class proof (the audit's HIGH-1, REC-1). Must reject any act
        on an inbox, its read/ or a counted branch that reaches the folder
        by its path after tc opened it: the path then leads through the
        swap, and the far end changes, a planted file is printed, or a
        count or an age is the far end's. Each family's mutation (the path
        put back in place of the pinned descriptor) is recorded with the
        lines it turned red in handoffs/P3FIX.md. P3 fix round 2 (Claude
        Opus 5.5, unreviewed): REC-4. tc health's listeners and
        held_by_others must name no holder of a lock at the far end, and
        its stuck line must carry the real branch's note, never the far
        end's. F1 (Claude Opus 5.5, unreviewed): the exit records' read
        must give the real inbox's record, never a far end's, and tc
        wait's exit record must land in the real inbox beside its lock.

        @interacts  per subtest: build's setup, plant's two trees (with the
                    row's locks, each held by a child), one command in
                    process (see the module block); lstats the far end
                    before and after.
        @deps       build, act, check, primary_group, as_member, load_tc,
                    swap_after_first_look, run_in_process, snapshot,
                    plant, text_stdin, hold, holder_patched_stat;
                    contextlib, os, resource, sys, time, unittest.mock;
                    ROWS, LINK, REAL_FOLDER, ASIDE_PREFIX, INBOX_PLANT,
                    BRANCH_PLANT, PLANTED_AGE_SECONDS, PLANTED_TEXT,
                    PLANTED_SENDER, NOTE_SUFFIX, HOLDER_UID_STEP.
        @complexity O(r x k): r = 17 rows, k = 2 kinds.
        @alloc      one TcRoot per subtest.
        """
        _, group, _ = primary_group()
        for row in ROWS:
            for kind in (LINK, REAL_FOLDER):
                with self.subTest(family=row.family, run=row.label, kind=kind), _root.TcRoot() as root:
                    target, calls = self.build(root, row, group)
                    layout = BRANCH_PLANT if row.target == "branch" else INBOX_PLANT
                    # P3 fix round 2 (Claude Opus 5.5, unreviewed): REC-4, the far ends' locks and note.
                    layout += tuple((name, "") for name in row.locks)
                    if row.late:
                        layout += ((f"to-{FAR_NAME}/{QUEUED_NAME}{NOTE_SUFFIX}", PLANTED_TEXT),)
                    if row.exit_record is not None:  # F1 (Claude Opus 5.5, unreviewed): a far end's own record
                        layout += ((WAIT_EXIT, row.exit_record),)
                    outside, other = root.base / "outside", root.base / "other"
                    plant(outside, layout, PLANTED_AGE_SECONDS)
                    plant(other, layout, PLANTED_AGE_SECONDS)
                    held = [hold(root, top / name).pid for top in (outside, other) for name in row.locks]
                    real = target.with_name(ASIDE_PREFIX + target.name)
                    far = {"before": snapshot(outside) if kind == LINK else None}

                    def swap():
                        os.rename(target, real)  # the owner's own entry: sticky lets its owner rename it
                        if kind == LINK:
                            target.symlink_to(outside, target_is_directory=True)
                        else:
                            os.rename(other, target)
                            far["before"] = snapshot(target)
                    tc = load_tc(root)
                    with contextlib.ExitStack() as stack:
                        stack.enter_context(as_member(root.path))
                        stack.enter_context(mock.patch.dict(os.environ, {"PATH": root.env["PATH"], **row.environ}))
                        os.environ.pop("CLAUDECODE", None)
                        if row.stdin is not None:
                            stack.enter_context(mock.patch.object(sys, "stdin", text_stdin(row.stdin)))
                        stack.enter_context(mock.patch.object(resource, "setrlimit", lambda *args: None))
                        stack.enter_context(mock.patch.object(tc, "gpu_stats", lambda: None))
                        if row.holder == "member":  # P3 fix round 2 (Claude Opus 5.5, unreviewed): REC-4
                            stack.enter_context(mock.patch.object(os, "stat", holder_patched_stat(
                                held, os.geteuid() + HOLDER_UID_STEP)))
                        if row.late:
                            stack.enter_context(mock.patch.object(tc, "wall_clock", lambda: time.time() + row.late))
                        made = stack.enter_context(swap_after_first_look(target, swap, row.looks, row.skip))
                        ran = run_in_process(self.act(tc, root, row))
                    far_end = outside if kind == LINK else target
                    shown = ran.out + ran.err + repr(ran.value)
                    self.assertTrue(made, "the swap never happened: tc never looked at the folder")
                    self.assertEqual(snapshot(far_end), far["before"],
                                     "a change reached the far end of the swap, outside the folder tc opened")
                    self.assertNotIn(PLANTED_TEXT, shown, "tc printed a planted file from the far end")
                    self.assertNotIn(PLANTED_SENDER, shown, "tc named a planted file from the far end")
                    self.check(row, root, ran, real, calls, held)


# P3 fix round 2 (Claude Opus 5.5, unreviewed): test-strategist REC-15 (synthesis REC-17).
def pinning_functions(source):
    """Each top-level function in the Python `source` that calls one of PIN_CALLS by name, anywhere in its body (a function nested in it counts as its own): {name: sorted calls}.

    @interacts  none; parses text.
    @deps       ast; PIN_CALLS.
    @complexity O(s) over s nodes of the parsed source (tc: tens of
                thousands).
    @alloc      the parsed tree while it walks; one dict, returned.
    """
    found = {}
    for node in ast.parse(source).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            calls = {call.func.id for call in ast.walk(node)
                     if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id in PIN_CALLS}
            if calls:
                found[node.name] = sorted(calls)
    return found


class EveryInboxActHasARowTest(unittest.TestCase):
    """The class proof's family list, kept whole: every function in tc that pins an inbox or a branch has a row of ROWS, or a named exemption.

    @interacts  reads ../tc's text.
    @deps       pinning_functions, _root.TC; ROWS, COVERED, EXEMPT.
    @complexity O(s) over s nodes of tc's parsed source.
    @alloc      tc's text and parsed tree while it runs.
    """

    def test_every_inbox_act_in_tc_has_a_row_or_a_named_exemption(self):
        """Every function tc defines that calls pinned_inbox, open_inbox or pin_folder is in COVERED, by rows ROWS holds, or in EXEMPT, with a reason; neither names a function that no longer pins.

        Must reject a new command, or a new step of an old one, that
        opens an inbox or a branch and has no row: that is how listeners,
        held_by_others and stuck_outbox stood outside the class proof
        until round 2 (test-strategist's mutations A and S).

        @interacts  reads ../tc's text.
        @deps       pinning_functions, _root.TC; ROWS, COVERED, EXEMPT.
        @complexity O(s) over s nodes of tc's parsed source.
        @alloc      tc's text and parsed tree while it runs.
        """
        found = pinning_functions(_root.TC.read_text(encoding="utf-8"))
        labels = {row.label for row in ROWS}
        with self.subTest(check="every pinning function is covered or exempt"):
            self.assertEqual(sorted(set(found) - set(COVERED) - set(EXEMPT)), [],
                             "these functions pin an inbox or a branch and have no class-proof row and no exemption")
        with self.subTest(check="every entry still pins"):
            self.assertEqual(sorted((set(COVERED) | set(EXEMPT)) - set(found)), [],
                             "these entries name a function that no longer pins an inbox or a branch")
        with self.subTest(check="covered and exempt are apart"):
            self.assertEqual(sorted(set(COVERED) & set(EXEMPT)), [], "a function is both covered and exempt")
        with self.subTest(check="every covering row is a row"):
            self.assertEqual(sorted({label for rows in COVERED.values() for label in rows} - labels), [],
                             "COVERED names a row ROWS does not hold")
        with self.subTest(check="every exemption says why"):
            self.assertEqual(sorted(name for name, why in EXEMPT.items() if not why.strip()), [],
                             "an exemption gives no reason")


if __name__ == "__main__":
    unittest.main()
