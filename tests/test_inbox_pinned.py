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
name on the live paths. One row per family, two for (g) and three for (i):
(a) tc send (deliver_local, publish_message); (b) the far gate (cmd_gate
through route_and_deliver, forward False); (c) tc peek; (d) tc read; (e)
tc wait's poll (unread); (f) tc log; (g) tc health --json and the gate's
health --json (mailbox_summary); (h) tc flush's count over other members'
branches (other_branches, outbox_files); (i) unread_count and its callers:
tc card, a codex tc join, and a codex send's ring decision; (j) the
board's own scan (board/serve.py, scan_messages).

Known gap: the family list is hardcoded. A command added later that
touches an inbox or a branch is not covered until someone adds its row.

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
unread_count's pin, the act under test.

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
            board/serve.py and calls scan_messages for the board row; the
            swap renames one folder in the root and makes a link or moves
            a folder in; lstats every entry of the far end before and
            after; collects garbage after each command, ResourceWarning
            ignored for it (tc wait keeps its lock file open for its
            process's life). Writes nothing outside the root's temp folder.
@deps       python3 stdlib (argparse, collections, contextlib, gc,
            importlib, io, json, os, pathlib, resource, stat, sys, time,
            unittest, unittest.mock, warnings); tests/_root.py; UmaskTestCase, as_member,
            load_tc and primary_group from test_shared.py; ../tc;
            ../board/serve.py.
@complexity O(r x k) subtests over r = 13 rows and k = 2 kinds of swap,
            each a fresh root with four to seven tc runs of setup and one
            command in process over a mailbox of a dozen entries.
@alloc      one TcRoot, one tc module and two small trees outside the root
            per subtest, all removed with the root.
"""

import argparse
import collections
import contextlib
import gc
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
import warnings
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
# Run as `python3 -m unittest tests.test_inbox_pinned` from the repo root,
# tests/ is not on sys.path; under discover it is. Add it once so both work.
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import _root  # noqa: E402  (needs the path line above)
from test_shared import UmaskTestCase, as_member, load_tc, primary_group  # noqa: E402

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
# What run_in_process hands back: the exit code (0 when the call
# returned, the words of an exception it raised), stdout, stderr, and
# what the call returned.
Ran = collections.namedtuple("Ran", "code out err value")
# One row: its family, its label, whether it swaps an inbox or a branch,
# whether ann joins as codex, whether ann's message is read in setup, the
# os calls its swap waits on, and what it patches for its call.
Row = collections.namedtuple("Row", "family label target codex read_first looks environ stdin")
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
def swap_after_first_look(target, swap, looks):
    """While entered, os.open, os.lstat and os.stat (those named in `looks`) are wrapped: the first call aimed at `target` returns, and then `swap` runs, once. Yields the list of where that call was aimed (empty until it happens).

    Where a call is aimed: by a name in a folder's descriptor, that
    folder's path now (/proc/self/fd) and the name; by a path, the path
    made absolute, links not read (no lstat runs here, so the wrap never
    calls itself). `target` matches as given and by its real path, taken
    before anything is swapped.

    @interacts  patches up to three os functions; reads /proc/self/fd;
                calls `swap` once.
    @deps       contextlib, os, pathlib, unittest.mock.
    @complexity O(1) per wrapped call.
    @alloc      one list, holding at most one path.
    """
    given, real = pathlib.Path(target), pathlib.Path(os.path.realpath(target))
    made = []

    def wrap(call):
        def wrapped(path, *args, **kwargs):
            result = call(path, *args, **kwargs)
            if not made and not isinstance(path, int):
                dir_fd = kwargs.get("dir_fd")
                aimed = (pathlib.Path(os.readlink(f"/proc/self/fd/{dir_fd}")) / os.fsdecode(path)
                         if dir_fd is not None else pathlib.Path(os.path.abspath(os.fsdecode(path))))
                if aimed in (given, real):
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
    Row("e", "tc wait's poll", "inbox", False, False, LOOKS, {}, None),
    Row("f", "tc log", "inbox", False, False, LOOKS, {}, None),
    Row("g", "tc health --json", "inbox", False, False, LOOKS, {}, None),
    Row("g", "the gate's health --json", "inbox", False, False, LOOKS,
        {"SSH_ORIGINAL_COMMAND": f"{FAR_TC} health --json"}, ""),
    Row("h", "tc flush's count of other members' branches", "branch", False, False, LOOKS, {}, None),
    Row("i", "tc card", "inbox", False, False, LOOKS, {}, None),
    Row("i", "a codex tc join", "inbox", False, False, OPENS, {"CODEX_THREAD_ID": THREAD}, None),
    Row("i", "a codex send's ring decision", "inbox", True, True, LOOKS, {}, None),
    Row("j", "the board's scan", "inbox", False, False, LOOKS, {}, None),
)


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
        """The shared mailbox for one subtest: init, the two members joined, ben's message to ann (read in setup when the row says), every real message dated REAL_AGE_SECONDS ago; for the branch row, another member's branch with one queued message and far-b's ssh card. (the folder to swap, the codex fake's calls or None).

        @interacts  six or seven tc runs; for a codex row, a fake codex
                    first on the root's PATH; makes the branch by hand for
                    the branch row; sets file times.
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
            "tc flush's count of other members' branches": lambda: tc.cmd_flush(argparse.Namespace(to=None)),
            "tc card": lambda: tc.cmd_card(argparse.Namespace(name=OWNER, ssh=SSH_TARGET, remote_tc=REMOTE_TC,
                                                              account=None, reports_to=None, force=False)),
            "a codex tc join": lambda: tc.cmd_join(argparse.Namespace(name=OWNER, account=ACCOUNT, kind=None,
                                                                      reports_to=None)),
            "a codex send's ring decision": lambda: tc.cmd_send(argparse.Namespace(sender=SENDER, to=OWNER,
                                                                                   message=SENT_TEXT, origin=None)),
            "the board's scan": lambda: serve.scan_messages(root.path / "mail"),
        }
        return commands[row.label]

    def check(self, row, root, ran, real, calls):
        """The row's own assertions, after the common ones: counts and ages equal the real inbox's (or branch's), and the real one, at `real`, holds what the act should have put there.

        @interacts  reads files under the root; reads the fake codex's
                    record for the codex row.
        @deps       files_in; json; the module's constants.
        @complexity O(1).
        @alloc      the text read, freed on return.
        """
        box = root.path / "mail" / f"to-{OWNER}"
        if row.label in ("tc send", "the far gate's send"):
            sender = SENDER if row.label == "tc send" else FAR_KEY
            name = f"000002-from-{sender}.md"
            self.assertEqual((ran.code, ran.out, ran.err), (0, f"sent #2 to {OWNER}: {box / name}\n", ""))
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
            self.assertEqual(files_in(real), ["000001-from-ben.md"])
        elif row.label == "tc log":
            self.assertIn(REAL_TEXT, ran.out, "tc log did not show the real message")
            self.assertEqual((ran.code, ran.err), (0, ""))
        elif row.family == "g":
            self.assertEqual((ran.code, ran.err), (0, ""))
            mine = json.loads(ran.out)["mail"][OWNER]
            self.assertEqual((mine["unread"], mine["mail_problem"]), (1, None), mine)
            self.assertLessEqual(abs(mine["newest_mail_age_s"] - REAL_AGE_SECONDS), AGE_SLACK_SECONDS,
                                 f"the newest mail's age is not the real inbox's: {mine}")
        elif row.target == "branch":
            self.assertIn(f"1 waiting for {SSH_TARGET} belong to other members", ran.out,
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
            messages, unreadable = ran.value
            self.assertEqual(sorted((m.to, m.seq, m.sender, m.read) for m in messages),
                             [(OWNER, 1, SENDER, False)], "the board's scan is not the real inbox's")
            self.assertEqual((ran.code, unreadable), (0, set()))

    def test_a_member_swapping_its_inbox_mid_command_never_leads_tc_outside(self):
        """For every row of ROWS and both kinds of swap (a link to a folder outside the mailbox, another real folder moved in), made by the folder's owner just after tc first looked at it: the far end keeps its tree, nothing printed quotes a planted file or names its sender, and every count, age and landing is the real folder's.

        D35's class proof (the audit's HIGH-1, REC-1). Must reject any act
        on an inbox, its read/ or a counted branch that reaches the folder
        by its path after tc opened it: the path then leads through the
        swap, and the far end changes, a planted file is printed, or a
        count or an age is the far end's. Each family's mutation (the path
        put back in place of the pinned descriptor) is recorded with the
        lines it turned red in handoffs/P3FIX.md.

        @interacts  per subtest: build's setup, plant's two trees, one
                    command in process (see the module block); lstats the
                    far end before and after.
        @deps       build, act, check, primary_group, as_member, load_tc,
                    swap_after_first_look, run_in_process, snapshot,
                    plant, text_stdin; contextlib, gc, os, resource, sys,
                    unittest.mock, warnings; ROWS, LINK, REAL_FOLDER, ASIDE_PREFIX,
                    INBOX_PLANT, BRANCH_PLANT, PLANTED_AGE_SECONDS,
                    PLANTED_TEXT, PLANTED_SENDER.
        @complexity O(r x k): r = 13 rows, k = 2 kinds.
        @alloc      one TcRoot per subtest.
        """
        _, group, _ = primary_group()
        for row in ROWS:
            for kind in (LINK, REAL_FOLDER):
                with self.subTest(family=row.family, run=row.label, kind=kind), _root.TcRoot() as root:
                    target, calls = self.build(root, row, group)
                    layout = BRANCH_PLANT if row.target == "branch" else INBOX_PLANT
                    outside, other = root.base / "outside", root.base / "other"
                    plant(outside, layout, PLANTED_AGE_SECONDS)
                    plant(other, layout, PLANTED_AGE_SECONDS)
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
                        made = stack.enter_context(swap_after_first_look(target, swap, row.looks))
                        ran = run_in_process(self.act(tc, root, row))
                    with warnings.catch_warnings():  # tc wait keeps its lock file open for its process's life
                        warnings.simplefilter("ignore", ResourceWarning)
                        gc.collect()  # in process, that file is freed here, quietly, before the root goes
                    far_end = outside if kind == LINK else target
                    shown = ran.out + ran.err + repr(ran.value)
                    self.assertTrue(made, "the swap never happened: tc never looked at the folder")
                    self.assertEqual(snapshot(far_end), far["before"],
                                     "a change reached the far end of the swap, outside the folder tc opened")
                    self.assertNotIn(PLANTED_TEXT, shown, "tc printed a planted file from the far end")
                    self.assertNotIn(PLANTED_SENDER, shown, "tc named a planted file from the far end")
                    self.check(row, root, ran, real, calls)


if __name__ == "__main__":
    unittest.main()
