"""
Tests for the shared mailbox (contract C4, D16; task H1): `tc init --shared
--group <g>`, the umask, the group and setgid on folders tc makes after
init, and the `mailbox shared with group <g>` or `mailbox private` line in
`tc health`. And D17 (SHARED D17, Claude Opus 5.5, unreviewed): the
sticky bit on mail/, status/, cards/ and outbox/, a symlink planted at a
lock, mail/.seq, a status file or the ring marker refused with its target
unchanged, a symlink planted as an inbox or its read/ refused with nothing
landing, and a file already there reopened without O_CREAT. And D19
(SHARED fix round 1, Claude Opus 5.5, unreviewed): a link or FIFO planted
as a message never printed and left in place, a FIFO at a lock's name
refused within FIFO_REFUSE_SECONDS, and no listener or count taken
through a link.

Model:  Claude Opus 5.5 (the SHARED lane agent), 2026-10-14
Status: unreviewed

The harness cannot make a second Linux user, so modes and the group are
tested with the running user's own groups: the primary group, and a
supplementary group when the user has one (os.getgroups()). The
supplementary group is the sharper test. A folder made without setgid, or
a top folder left without its chown, takes the primary group, not g, and
fails there. The second-user walk-through is the owner's human QA (D4,
route-shared.md).

@interacts  runs ../tc through tests/_root.py under a throwaway TC_ROOT.
            Sets this process's umask to CHILD_UMASK for each test and puts
            the old one back after; children inherit it, so a tc that never
            sets its own umask writes PRIVATE_FILE_MODE and fails. Reads
            the group database and this process's groups. Stats every entry
            under the root. The H1 tests write nothing by hand; the D17
            tests make folders, symlinks, message files and link targets by
            hand (the targets in the root's temp folder, outside TC_ROOT),
            run a fake codex through the harness, and load tc in process
            once, with os.open wrapped to record its flags. The D19 tests
            make FIFOs and links by hand, hold an flock on one lock file in
            this process, and load tc in process to call show() (stdout
            captured), listeners() and unread_count().
@deps       python3 stdlib (contextlib, fcntl, grp, importlib, io, json, os,
            pathlib, stat, subprocess, sys, unittest, unittest.mock);
            tests/_root.py.
@complexity O(1) per test: a handful of tc runs over a root of a few dozen
            entries, once per group tested (one or two).
@alloc      one TcRoot per test and group, removed when its context exits.
"""

import argparse
import contextlib
import errno
import fcntl
import grp
import importlib.machinery
import importlib.util
import io
import json
import os
import pathlib
import stat
import subprocess
import sys
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
# Run as `python3 -m unittest tests.test_shared` from the repo root, tests/
# is not on sys.path; under discover it is. Add it once so both work.
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import _root  # noqa: E402  (needs the path line above)

# The usual login umask. Every child inherits it, so a tc that does not set
# its own umask under a shared mailbox writes files at PRIVATE_FILE_MODE.
CHILD_UMASK = 0o022
# Written out here, not read from tc, so a change in tc fails these tests
# instead of moving them. C4: folders 2775 (setgid).
FOLDER_MODE = 0o2775
# SHARED fix round 1 (Claude Opus 5.5, unreviewed): D20, written out for the
# same reason. The files every member writes, directly in mail/ (mail/.seq,
# the locks, the ring marker): 0664.
SHARED_WRITABLE_FILE_MODE = 0o664
# Messages, cards and status files: 0640, never group-writable.
SHARED_OWNED_FILE_MODE = 0o640
# An inbox and its read/, owned by the recipient: setgid, sticky, no other.
SHARED_INBOX_MODE = 0o3770
# What a file gets under CHILD_UMASK: the mode C4 must never leave behind.
PRIVATE_FILE_MODE = 0o644
# The folders C4 shares, by name under the root.
SHARED_FOLDERS = ("mail", "status", "cards", "outbox")
# Row 1 of the exit table: refused with words.
EXIT_REFUSED = 1
# Row 2: a wait that timed out. A wait with --timeout 0 makes its lock and
# exits with it at once.
EXIT_TIMEOUT = 2
# A group name no machine has, for the refusal of a group that does not exist.
NO_SUCH_GROUP = "tc-test-no-such-group"
# SHARED D17 (Claude Opus 5.5, unreviewed): no planted links.
# mail/, status/, cards/ and outbox/ themselves: FOLDER_MODE plus the sticky
# bit. Written out here for the same reason as FOLDER_MODE.
TOP_FOLDER_MODE = 0o3775
# What tc says when it refuses a symlink at a file it opens by name.
LINK_WORDS = "is a symlink, which tc never follows"
# What tc says when it refuses a symlink at an inbox or its read/.
INBOX_LINK_WORDS = "is a symlink, not a real folder"
# The text of every planted link's target, outside TC_ROOT. A refusal
# leaves it as it was.
TARGET_TEXT = "a file outside the mailbox; tc must not touch it\n"
# How long a wait or watch may run. A refused one exits at once; this only
# bounds a broken one, under the harness's DEFAULT_TC_TIMEOUT_SECONDS.
LISTEN_SECONDS = "3"
# Thresholds no real machine reaches, so a watch that does start can only
# heartbeat, never alert.
QUIET = ["--load-ratio", "100000", "--mem-min-pct", "0", "--gpu-max-c", "100000"]
# The thread a codex card carries in these tests.
THREAD = "t1"
# SHARED fix round 1 (Claude Opus 5.5, unreviewed): D19.
# What tc says when it refuses a FIFO, or anything else that is not a
# regular file, at a name it opens.
FIFO_WORDS = "is not a regular file, which tc never opens"
# D19's bound (phases.md H1): a FIFO at a lock's name is refused within
# this many seconds, never waited on. It also bounds a read, peek or log
# that must not block on a FIFO planted as a message.
FIFO_REFUSE_SECONDS = 2
# A wait that polls once and times out: its first poll comes at once, then
# it sleeps out the rest.
ONE_POLL_SECONDS = "1"
# The body of the real message beside each planted entry.
REAL_TEXT = "real mail from a"
# SHARED fix round 1 (Claude Opus 5.5, unreviewed): D20, nobody touches
# another member's mail.
# C4's words for a send to a name with no card and no inbox (D20 item 3).
NOBODY_WORDS = "tc send: nobody has joined as {name} on this shared mailbox"
# What tc says for a card with no inbox, and what it asks of the owner.
NO_INBOX_WORDS = "has a card but no inbox on this shared mailbox"
REJOIN_WORDS = "rejoin (tc join {name}"
# What tc says for an inbox whose owner is not its card's owner (item 4).
OWNER_WORDS = "under a shared mailbox an inbox belongs to the owner of its card"
# What tc join says for a card or an inbox another user owns.
TAKEN_CARD_WORDS = "under a shared mailbox only its owner can replace it"
TAKEN_INBOX_WORDS = "under a shared mailbox an inbox belongs to its recipient"
# What tc read says for a message it may not move into read/.
NOT_MOVED_WORDS = "not moved to read/"
# What tc says for a file this user may not open to write.
MAY_NOT_OPEN_WORDS = "and this user may not open it"
# A status file its owner may read and not write: owner and group read.
READ_ONLY_FILE_MODE = 0o440
# The fake codex's exit codes: a ring that fails, then one that is queued.
CODEX_FAILS, CODEX_QUEUED = 1, 0
# The ring marker's first line after a failed ring, and once nothing is owed.
FAILED_STATE = "failed"
CLEAR_STATE = "clear"
# SHARED fix round 1 (Claude Opus 5.5, unreviewed): init, make_folder and
# the refusals' words (the audit's MEDIUM-4, LOW-2 to LOW-8).
# What init says when .shared cannot be written, by the mailbox's state.
STAYS_PRIVATE_WORDS = "the mailbox stays private"
STAYS_SHARED_WORDS = "the mailbox stays shared with group {group}"
# A group name .shared may hold for the words; no machine needs to have it.
OTHER_GROUP = "tc-test-other-group"
# What tc says when it cannot reach .shared, or ROOT, for want of access.
SEARCH_WORDS = "needs search (x) access on every folder from / down to"
# What tc says for a .shared it can read that names no group.
REWRITE_WORDS = "Run tc init --shared --group <g> to rewrite it"
# What make_folder says for a folder in the wrong group, and after it
# removed the folder it could not share.
WRONG_GROUP_WORDS = "is in group {have}, not {want}"
REMOVED_WORDS = "removed it again"
# Folder modes a test sets by hand: read and enter only (no new entries),
# nothing at all (no search), and the owner's full access to put back.
READ_ONLY_FOLDER_MODE = 0o555
NO_ACCESS_MODE = 0o000
OWNER_FOLDER_MODE = 0o700


def groups_to_test():
    """The groups to share with: [("primary", name, gid)], plus ("supplementary", ...) when the user has one.

    The supplementary group is the first of os.getgroups(), in number
    order, that is not the effective group and has a name.

    @interacts  reads this process's groups and the group database.
    @deps       grp, os.
    @complexity O(s) over s supplementary groups (a handful).
    @alloc      one short list, returned.
    """
    primary = os.getegid()
    found = [("primary", grp.getgrgid(primary).gr_name, primary)]
    for gid in sorted(set(os.getgroups()) - {primary}):
        try:
            found.append(("supplementary", grp.getgrgid(gid).gr_name, gid))
            break
        except KeyError:
            continue
    return found


def foreign_group():
    """The name of a group this machine has and the running user is not in, or None.

    @interacts  reads the group database and this process's groups.
    @deps       grp, os.
    @complexity O(g) over g groups on the machine (tens).
    @alloc      the group list while it is read.
    """
    mine = set(os.getgroups()) | {os.getegid()}
    for entry in grp.getgrall():
        if entry.gr_gid not in mine:
            return entry.gr_name
    return None


def tree(path, under=SHARED_FOLDERS):
    """Every entry under the named folders of `path`: {relative path: (kind, mode, gid)}.

    kind is "folder", "file" or "other", from lstat, so a link is never
    followed. `under` None means every entry under `path` itself.

    @interacts  lstats each entry. Writes nothing.
    @deps       os, stat, pathlib.
    @complexity O(e) over e entries (a few dozen).
    @alloc      one dict, returned.
    """
    tops = [path] if under is None else [path / name for name in under]
    out = {}
    for top in tops:
        if not os.path.lexists(top):
            continue
        for entry in [top, *top.rglob("*")]:
            if entry == path:
                continue
            st = os.lstat(entry)
            kind = ("folder" if stat.S_ISDIR(st.st_mode) else
                    "file" if stat.S_ISREG(st.st_mode) else "other")
            out[str(entry.relative_to(path))] = (kind, stat.S_IMODE(st.st_mode), st.st_gid)
    return out


def shared_as(path, kind, gid):
    """The (kind, mode, gid) C4, D17 and D20 want for the `kind` entry at relative `path`, shared with `gid`.

    A file directly in mail/ (mail/.seq, a lock, the ring marker):
    SHARED_WRITABLE_FILE_MODE; any other file (a message, a card, a
    status): SHARED_OWNED_FILE_MODE (D20). A folder: TOP_FOLDER_MODE
    (sticky, D17) when it is one of SHARED_FOLDERS itself,
    SHARED_INBOX_MODE for mail/to-<name> and its read/ (D20), else
    FOLDER_MODE.

    @interacts  none.
    @deps       SHARED_FOLDERS, TOP_FOLDER_MODE, SHARED_INBOX_MODE,
                FOLDER_MODE, SHARED_WRITABLE_FILE_MODE,
                SHARED_OWNED_FILE_MODE.
    @complexity O(1).
    @alloc      the split path and one tuple, returned.
    """
    parts = path.split("/")
    if kind != "folder":
        writable = len(parts) == 2 and parts[0] == "mail"
        return (kind, SHARED_WRITABLE_FILE_MODE if writable else SHARED_OWNED_FILE_MODE, gid)
    if path in SHARED_FOLDERS:
        return (kind, TOP_FOLDER_MODE, gid)
    inbox = parts[0] == "mail" and len(parts) in (2, 3) and parts[1].startswith("to-") and parts[2:] in ([], ["read"])
    return (kind, SHARED_INBOX_MODE if inbox else FOLDER_MODE, gid)


class SharedTest(unittest.TestCase):
    """`tc init --shared`, the umask, D16's later folders, and the health line.

    @interacts  see the module block.
    @deps       _root.TcRoot.
    @complexity O(1) per test.
    @alloc      one TcRoot per test and group.
    """

    def setUp(self):
        """Set this process's umask to CHILD_UMASK; the cleanup puts the old one back.

        @interacts  sets the umask of this process (and so of every child).
        @deps       os.
        @complexity O(1).
        @alloc      none.
        """
        self.addCleanup(os.umask, os.umask(CHILD_UMASK))

    def test_init_shares_every_folder_and_file_already_there(self):
        """After init, every entry has group g and its mode (shared_as: the four 3775, inboxes 3770, mail/ files 0664, the rest 0640); so has a message sent after.

        Before init the root holds an inbox with its read/, a message,
        mail/.seq, an inbox lock, a status file and a card, all written
        under CHILD_UMASK (files at 0644, checked, so the test is not
        vacuous). .shared holds the group's name. Must reject: files left
        at 0644 after init (init did not reach them, or the umask was not
        set before the send after it).

        @interacts  per group: a send, a status, a join, init, a send.
        @deps       _root.TcRoot.tc, groups_to_test, tree, shared_as.
        @complexity O(1) per group.
        @alloc      one TcRoot per group.
        """
        for label, name, gid in groups_to_test():
            with self.subTest(group=label), _root.TcRoot() as root:
                root.tc("send", "--from", "a", "--to", "b", "before")
                root.tc("status", "b", "busy")
                root.tc("join", "b", env={"CLAUDECODE": "1"})
                before = tree(root.path)
                code, out, err = root.tc("init", "--shared", "--group", name)
                after = tree(root.path)
                marker = (root.path / ".shared").read_text()
                sent = root.tc("send", "--from", "a", "--to", "b", "after")
                later = tree(root.path)
                self.assertEqual(sorted(after), ["cards", "cards/b.json", "mail", "mail/.box-b.lock",
                                                 "mail/.seq", "mail/to-b", "mail/to-b/000001-from-a.md",
                                                 "mail/to-b/read", "outbox", "status", "status/b.md"])
                self.assertEqual({p: m for p, (k, m, g) in before.items() if k == "file"},
                                 {p: PRIVATE_FILE_MODE for p, (k, m, g) in before.items() if k == "file"},
                                 "files before init are not 0644: the umask never reached the child")
                self.assertEqual(code, 0, f"tc init exited {code}: {err}")
                self.assertEqual(after, {p: shared_as(p, k, gid) for p, (k, m, g) in after.items()})
                self.assertEqual(marker, f"{name}\n")
                self.assertEqual(sent[0], 0, sent[2])
                for path in ("mail/to-b/000002-from-a.md", "mail/.seq"):
                    self.assertEqual(later[path], shared_as(path, "file", gid))

    def test_a_group_the_user_is_not_in_is_refused_and_nothing_changes(self):
        """init with a foreign group, or one that does not exist: exit 1, words, every entry as it was, no .shared.

        Must reject an init that changes what it can before it finds it
        may not, or that writes .shared for a group the user cannot use.

        @interacts  one send, then two refused inits; stats the whole root.
        @deps       _root.TcRoot.tc, foreign_group, tree.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        foreign = foreign_group()
        if foreign is None:
            self.skipTest("every group on this machine holds the running user")
        with _root.TcRoot() as root:
            root.tc("send", "--from", "a", "--to", "b", "hi")
            before = tree(root.path, under=None)
            refused = root.tc("init", "--shared", "--group", foreign)
            missing = root.tc("init", "--shared", "--group", NO_SUCH_GROUP)
            after = tree(root.path, under=None)
        self.assertEqual(refused[0], EXIT_REFUSED, refused[2])
        self.assertIn(f"tc init: you are not in group {foreign}; nothing changed", refused[2])
        self.assertEqual(missing[0], EXIT_REFUSED, missing[2])
        self.assertIn(f"tc init: no group named {NO_SUCH_GROUP}", missing[2])
        self.assertEqual(after, before, "a refused init changed the root")
        self.assertNotIn(".shared", after)

    def test_health_says_private_then_shared_with_the_group(self):
        """tc health says `mailbox private` before init and `mailbox shared with group <g>` after; --json agrees.

        Must reject a health line that never changes, or names no group.

        @interacts  four tc health runs and one init.
        @deps       _root.TcRoot.tc, groups_to_test.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        label, name, gid = groups_to_test()[-1]
        with _root.TcRoot() as root:
            private_text = root.tc("health")
            private_json = root.tc("health", "--json")
            root.tc("init", "--shared", "--group", name)
            shared_text = root.tc("health")
            shared_json = root.tc("health", "--json")
        for code, out, err in (private_text, private_json, shared_text, shared_json):
            self.assertEqual(code, 0, err)
        self.assertIn("\nmailbox private\n", private_text[1])
        self.assertIsNone(json.loads(private_json[1])["shared_group"])
        self.assertIn(f"\nmailbox shared with group {name}\n", shared_text[1])
        self.assertNotIn("mailbox private", shared_text[1])
        self.assertEqual(json.loads(shared_json[1])["shared_group"], name)

    def test_folders_made_after_init_get_the_group_and_setgid(self):
        """Init on an empty root, then a join, a send, a status and a wait: each new folder and file in g at its mode (shared_as) (D16, D20).

        SHARED fix round 1 (Claude Opus 5.5, unreviewed): D19. Init makes
        mail/, status/, cards/ and outbox/ itself, each 3775 in g, so no
        other user has to make one in a ROOT the first user owns. The
        inbox and its read/ then come from the first join (D20), the
        message from the first send, the status file from the first
        status, and the wait lock from a wait that times out at once.
        Must reject an init that makes no top folder (the second user's
        first command would need write access to ROOT), a later folder
        without setgid (0775), or a top folder left in the primary group
        (the supplementary run), and any file at 0644.

        @interacts  per group: init, a join, a send, a status, a wait.
        @deps       _root.TcRoot.tc, groups_to_test, tree, shared_as.
        @complexity O(1) per group.
        @alloc      one TcRoot per group.
        """
        for label, name, gid in groups_to_test():
            with self.subTest(group=label), _root.TcRoot() as root:
                code, out, err = root.tc("init", "--shared", "--group", name)
                self.assertEqual(code, 0, f"tc init exited {code}: {err}")
                self.assertEqual(tree(root.path), {top: ("folder", TOP_FOLDER_MODE, gid) for top in SHARED_FOLDERS},
                                 "init did not make the four top folders (D19)")
                runs = [root.tc("join", "b", env={"CLAUDECODE": "1"}),
                        root.tc("send", "--from", "a", "--to", "b", "hi"),
                        root.tc("status", "b", "busy")]
                waited = root.tc("wait", "c", "--timeout", "0")
                made = tree(root.path)
                for run in runs:
                    self.assertEqual(run[0], 0, run[2])
                self.assertEqual(waited[0], EXIT_TIMEOUT, waited[2])
                self.assertEqual(sorted(made), ["cards", "cards/b.json", "mail", "mail/.box-b.lock",
                                                "mail/.seq", "mail/.wait-c.lock", "mail/to-b",
                                                "mail/to-b/000001-from-a.md", "mail/to-b/read", "outbox",
                                                "status", "status/b.md"])
                self.assertEqual(made, {p: shared_as(p, k, gid) for p, (k, m, g) in made.items()})


# SHARED D17 (Claude Opus 5.5, unreviewed): no planted links.
def plant(root, at, target_name="target", make_target=True):
    """A symlink at TC_ROOT/`at` to a file in the root's temp folder, outside TC_ROOT. Returns the target's path.

    The target holds TARGET_TEXT, or is left missing when `make_target` is
    false, for a dangling link. The link's folder is made if missing.

    @interacts  makes the link's folder, the link and (unless told not to)
                the target file.
    @deps       pathlib; TARGET_TEXT.
    @complexity O(1).
    @alloc      the target file and the link, removed with the temp folder.
    """
    target = root.base / target_name
    if make_target:
        target.write_text(TARGET_TEXT)
    link = root.path / at
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(target)
    return target


def landed(root):
    """Every message file under TC_ROOT's inboxes, unread or read, as relative paths.

    @interacts  globs mail/to-*/ and their read/ folders. Writes nothing.
    @deps       pathlib.
    @complexity O(m) over m message files (a handful).
    @alloc      one sorted list, returned.
    """
    mail = root.path / "mail"
    return sorted(str(p.relative_to(root.path)) for p in [*mail.glob("to-*/*.md"), *mail.glob("to-*/read/*.md")])


def load_tc(root):
    """Load ../tc as a module with TC_ROOT set to the harness root, without running main().

    tc reads TC_ROOT once, at import, so it is set before the load and the
    old value is put back after (CLAUDE.md, Key patterns).

    @interacts  sets and restores os.environ["TC_ROOT"]; runs tc's top
                level (constants only, no disk writes).
    @deps       importlib, os; _root.TC.
    @complexity O(1).
    @alloc      one module object, returned.
    """
    old = os.environ.get("TC_ROOT")
    os.environ["TC_ROOT"] = str(root.path)
    try:
        loader = importlib.machinery.SourceFileLoader("tc_shared_under_test", str(_root.TC))
        mod = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
        loader.exec_module(mod)
        return mod
    finally:
        if old is None:
            os.environ.pop("TC_ROOT", None)
        else:
            os.environ["TC_ROOT"] = old


class NoPlantedLinksTest(unittest.TestCase):
    """D17: the sticky folders, planted file links, planted inbox links, and reopening without O_CREAT.

    The link checks hold whether or not the mailbox is shared, so only the
    sticky test runs init.

    @interacts  see the module block.
    @deps       _root.TcRoot, plant, landed, load_tc.
    @complexity O(1) per test.
    @alloc      one TcRoot per case.
    """

    def test_the_shared_folders_carry_the_sticky_bit(self):
        """After init, mail/, outbox/ (made by hand, as the ssh route will) and the later cards/ and status/ are 3775; inboxes and read/ are 3770 (D20); outbox/sent/ is 2775.

        Must reject a top folder without the sticky bit (a member could
        delete or swap another user's inbox, card or lock), and an inbox
        without it or open to other users (D20: a member could delete or
        rename another member's unread mail).

        @interacts  per group: a send, one folder pair made by hand, init,
                    two joins, a status and a second send.
        @deps       _root.TcRoot.tc, groups_to_test, tree.
        @complexity O(1) per group.
        @alloc      one TcRoot per group.
        """
        for label, name, gid in groups_to_test():
            with self.subTest(group=label):
                with _root.TcRoot() as root:
                    root.tc("send", "--from", "a", "--to", "b", "before")
                    (root.path / "outbox" / "sent").mkdir(parents=True)
                    code, out, err = root.tc("init", "--shared", "--group", name)
                    runs = [root.tc("join", "b", env={"CLAUDECODE": "1"}), root.tc("status", "b", "busy"),
                            root.tc("join", "c", env={"CLAUDECODE": "1"}),
                            root.tc("send", "--from", "a", "--to", "c", "after")]
                    folders = {p: (m, g) for p, (k, m, g) in tree(root.path).items() if k == "folder"}
                self.assertEqual(code, 0, err)
                for run in runs:
                    self.assertEqual(run[0], 0, run[2])
                self.assertEqual(folders, {
                    "mail": (TOP_FOLDER_MODE, gid), "outbox": (TOP_FOLDER_MODE, gid),
                    "cards": (TOP_FOLDER_MODE, gid), "status": (TOP_FOLDER_MODE, gid),
                    "mail/to-b": (SHARED_INBOX_MODE, gid), "mail/to-b/read": (SHARED_INBOX_MODE, gid),
                    "mail/to-c": (SHARED_INBOX_MODE, gid), "mail/to-c/read": (SHARED_INBOX_MODE, gid),
                    "outbox/sent": (FOLDER_MODE, gid)})

    def test_a_link_at_a_file_tc_opens_by_name_is_refused_and_its_target_unchanged(self):
        """A symlink at a wait, watch or inbox lock, mail/.seq or status/x.md: exit 1, the words, the target as it was, no mail.

        One fresh root per case. The mail/.seq case also runs with a
        dangling link, whose target must still not exist after. Showing
        every status with a link among them prints the rest, names the
        link and never prints its target. Must reject an open that follows
        the link (the target would be truncated or written, or made).

        @interacts  per case: makes folders, a message file and a link by
                    hand, then one tc run.
        @deps       _root.TcRoot.tc, plant, landed.
        @complexity O(1) per case, seven cases.
        @alloc      one TcRoot per case.
        """
        send = ["send", "--from", "a", "--to", "x", "hi"]
        cases = [
            ("wait lock", "mail/.wait-x.lock", ["wait", "x", "--timeout", LISTEN_SECONDS], True),
            ("watch lock", "mail/.watch-x.lock",
             ["watch", "x", "--heartbeat", LISTEN_SECONDS, "--poll", "1", *QUIET], True),
            ("inbox lock, send", "mail/.box-x.lock", send, True),
            ("inbox lock, read", "mail/.box-x.lock", ["read", "x"], True),
            ("mail/.seq", "mail/.seq", send, True),
            ("mail/.seq, dangling", "mail/.seq", send, False),
            ("status/x.md, post", "status/x.md", ["status", "x", "busy"], True),
        ]
        for label, at, argv, make_target in cases:
            with self.subTest(case=label):
                with _root.TcRoot() as root:
                    if argv[0] == "read":
                        (root.path / "mail" / "to-x" / "read").mkdir(parents=True)
                        (root.path / "mail" / "to-x" / "000001-from-a.md").write_text("# #1 from a to x\n\nhi\n")
                    target = plant(root, at, make_target=make_target)
                    code, out, err = root.tc(*argv)
                    after = target.read_text() if target.exists() else None
                    still_link = (root.path / at).is_symlink()
                    mail = landed(root)
                self.assertEqual(code, EXIT_REFUSED, f"{label}: exited {code}: {err}")
                self.assertIn(LINK_WORDS, err, label)
                self.assertEqual(after, TARGET_TEXT if make_target else None, f"{label}: the target changed")
                self.assertTrue(still_link, f"{label}: the link was replaced")
                self.assertEqual(mail, ["mail/to-x/000001-from-a.md"] if argv[0] == "read" else [],
                                 f"{label}: mail moved or landed")
        with _root.TcRoot() as root:
            self.assertEqual(root.tc("status", "a", "fine")[0], 0)
            plant(root, "status/x.md")
            code, out, err = root.tc("status")
        self.assertEqual(code, EXIT_REFUSED, err)
        self.assertIn("fine", out)
        self.assertNotIn(TARGET_TEXT.strip(), out, "tc status printed a link's target")
        self.assertIn("status/x.md not shown", err)
        self.assertIn(LINK_WORDS, err)

    def test_a_link_at_the_ring_marker_is_refused_and_nothing_rings(self):
        """A symlink at mail/.ring-pending-x: a send to codex card x exits 1, lands nothing, rings nothing; a join of codex z over one writes no card.

        A send to codex card y with no link rings the same fake, so the
        fake is proven to be wired up. Must reject a send that rings or
        lands mail past the link, or a join that writes its card.

        @interacts  two codex joins, one link per marker, two sends, one
                    refused join; a fake codex.
        @deps       _root.TcRoot.tc, _root.TcRoot.fake_bin, plant, landed.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("codex", 0)
            joins = [root.tc("join", n, env={"CODEX_THREAD_ID": THREAD}) for n in ("x", "y")]
            target = plant(root, "mail/.ring-pending-x")
            refused = root.tc("send", "--from", "a", "--to", "x", "hi")
            control = root.tc("send", "--from", "a", "--to", "y", "hi")
            plant(root, "mail/.ring-pending-z", target_name="target-z")
            joined = root.tc("join", "z", env={"CODEX_THREAD_ID": THREAD})
            record = folder.parent / "calls.jsonl"
            self.assertTrue(record.exists(), f"{record} missing: the fake codex never ran")
            rang = [call["argv"] for call in calls()]
            after = target.read_text()
            mail = landed(root)
            card_z = (root.path / "cards" / "z.json").exists()
        for run in joins:
            self.assertEqual(run[0], 0, run[2])
        self.assertEqual(refused[0], EXIT_REFUSED, refused[2])
        self.assertIn(LINK_WORDS, refused[2])
        self.assertEqual(control[0], 0, control[2])
        self.assertEqual(len(rang), 1, f"rang {rang}")
        self.assertIn("MAIL: 1 unread for y.", rang[0][-1])
        self.assertEqual(after, TARGET_TEXT)
        self.assertEqual(mail, ["mail/to-y/000001-from-a.md"])
        self.assertEqual(joined[0], EXIT_REFUSED, joined[2])
        self.assertIn(LINK_WORDS, joined[2])
        self.assertFalse(card_z, "a join over a linked marker wrote its card")

    def test_a_link_planted_as_an_inbox_or_its_read_is_refused_and_nothing_lands(self):
        """mail/to-x a symlink to a real folder: send, read, peek and wait exit 1 and the folder stays empty; mail/to-y/read a symlink: read and send exit 1.

        The refused send takes no number (mail/.seq never appears). The
        message in to-y stays unread. Must reject a send that lands mail
        through the link, or a read that moves mail into it.

        @interacts  makes two real folders outside TC_ROOT, one inbox and
                    one message by hand, two links; six tc runs.
        @deps       _root.TcRoot.tc.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            elsewhere, elsewhere_read = root.base / "elsewhere", root.base / "elsewhere-read"
            elsewhere.mkdir()
            elsewhere_read.mkdir()
            (root.path / "mail").mkdir()
            (root.path / "mail" / "to-x").symlink_to(elsewhere, target_is_directory=True)
            box = root.path / "mail" / "to-y"
            box.mkdir()
            (box / "000001-from-a.md").write_text("# #1 from a to y\n\nhi\n")
            (box / "read").symlink_to(elsewhere_read, target_is_directory=True)
            runs = {"send x": root.tc("send", "--from", "a", "--to", "x", "hi"),
                    "read x": root.tc("read", "x"),
                    "peek x": root.tc("peek", "x"),
                    "wait x": root.tc("wait", "x", "--timeout", LISTEN_SECONDS),
                    "read y": root.tc("read", "y"),
                    "send y": root.tc("send", "--from", "a", "--to", "y", "hi")}
            outside = sorted(p.name for p in [*elsewhere.iterdir(), *elsewhere_read.iterdir()])
            seq = (root.path / "mail" / ".seq").exists()
            unread_y = sorted(p.name for p in box.glob("*.md"))
        for label, (code, out, err) in runs.items():
            with self.subTest(run=label):
                self.assertEqual(code, EXIT_REFUSED, f"{label}: exited {code}: {err}")
                self.assertIn(INBOX_LINK_WORDS, err, label)
        self.assertEqual(outside, [], "mail landed or moved through a linked folder")
        self.assertFalse(seq, "a refused send took a number")
        self.assertEqual(unread_y, ["000001-from-a.md"])

    def test_a_file_already_there_is_reopened_without_o_creat(self):
        """In process: mail/.seq and an inbox lock, opened twice each: O_NOFOLLOW every time, O_CREAT only once and only with O_EXCL.

        Under C4, Linux with fs.protected_regular = 2 refuses an O_CREAT
        open of a file another user made in a sticky, group-writable
        folder, and the harness has no second user to show it. So this
        checks the flags tc passes. Must reject a reopen with O_CREAT (it
        would fail for the third user of a shared mailbox) and any open
        without O_NOFOLLOW.

        @interacts  loads tc in process; wraps os.open to record its calls
                    while next_seq and inbox_lock each run twice.
        @deps       load_tc, unittest.mock; tc.next_seq, tc.inbox_lock.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        with _root.TcRoot() as root:
            tc = load_tc(root)
            lock = root.path / "mail" / ".box-b.lock"
            with mock.patch.object(os, "open", wraps=os.open) as opened:
                numbers = [tc.next_seq(), tc.next_seq()]
                for _ in range(2):
                    with tc.inbox_lock("b"):
                        pass
            seen = {}
            for call in opened.call_args_list:
                path, flags = pathlib.Path(call.args[0]), call.args[1]
                seen.setdefault(path, []).append(flags)
        self.assertEqual(numbers, [1, 2])
        for path in (root.path / "mail" / ".seq", lock):
            with self.subTest(file=path.name):
                flags = seen.get(path, [])
                self.assertTrue(flags, f"{path.name} was never opened through os.open")
                self.assertTrue(all(f & os.O_NOFOLLOW for f in flags), f"{path.name}: an open without O_NOFOLLOW")
                creating = [f for f in flags if f & os.O_CREAT]
                self.assertEqual(len(creating), 1, f"{path.name}: {len(creating)} opens with O_CREAT")
                self.assertTrue(creating[0] & os.O_EXCL, f"{path.name}: O_CREAT without O_EXCL")



# SHARED fix round 1 (Claude Opus 5.5, unreviewed): D19 and the audit's MEDIUM-5 and LOW-9.
class RegularFilesOnlyTest(unittest.TestCase):
    """D19: messages only from regular files, a FIFO at a lock's name refused, and no listener or count taken through a link.

    None of this needs a shared mailbox: the checks hold either way.

    @interacts  see the module block.
    @deps       _root.TcRoot, plant, landed, load_tc.
    @complexity O(1) per test.
    @alloc      one TcRoot per case.
    """

    def test_a_link_or_fifo_planted_as_a_message_is_never_printed_and_stays_in_place(self):
        """A link to a file outside the mailbox and a FIFO, each named like a message in to-x, and to-zzz a link to a folder: peek, read and log never print the target, never block, and leave both in place.

        Each prints the real message beside them, names each planted entry
        on stderr and exits 1. read moves only the real message into
        read/, and a wait with only the planted two left times out instead
        of waking. show() itself, handed the link in process, prints
        nothing and names it (never the FIFO in process, where a broken
        show() would block this test with no timeout). Must reject a show() that follows a
        link (the target prints), a read of the FIFO (it blocks), a read
        that moves the link, and a wait that counts it.

        @interacts  one send; a link, a FIFO and a linked folder made by
                    hand; peek, read, log and a one-poll wait; loads tc in
                    process for show(), with stdout captured.
        @deps       _root.TcRoot.tc, plant, load_tc; contextlib, io;
                    tc.show.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        with _root.TcRoot() as root:
            root.tc("send", "--from", "a", "--to", "x", REAL_TEXT)
            box = root.path / "mail" / "to-x"
            target = plant(root, "mail/to-x/000099-from-z.md")
            fifo = box / "000098-from-z.md"
            os.mkfifo(fifo)
            elsewhere = root.base / "elsewhere"
            elsewhere.mkdir()
            (elsewhere / "000097-from-z.md").write_text(TARGET_TEXT)
            (root.path / "mail" / "to-zzz").symlink_to(elsewhere, target_is_directory=True)
            runs = {}
            for label, argv in (("peek", ["peek", "x"]), ("read", ["read", "x"]), ("log", ["log"])):
                try:
                    runs[label] = root.tc(*argv, timeout=FIFO_REFUSE_SECONDS)
                except subprocess.TimeoutExpired:
                    self.fail(f"tc {label} blocked on the FIFO in mail/to-x past {FIFO_REFUSE_SECONDS} s")
            waited = root.tc("wait", "x", "--timeout", ONE_POLL_SECONDS)
            left = (os.path.islink(box / "000099-from-z.md"),
                    os.path.lexists(fifo) and stat.S_ISFIFO(os.lstat(fifo).st_mode))
            moved = sorted(p.name for p in (box / "read").iterdir())
            after = target.read_text()
            tc = load_tc(root)
            with contextlib.redirect_stdout(io.StringIO()) as printed:
                unshown = tc.show([box / "000099-from-z.md"])
        for label, (code, out, err) in runs.items():
            with self.subTest(run=label):
                self.assertNotIn(TARGET_TEXT.strip(), out + err, f"tc {label} printed a link's target")
                self.assertIn(REAL_TEXT, out, f"tc {label} did not print the real message")
                self.assertEqual(code, EXIT_REFUSED, f"tc {label} exited {code}: {err}")
                self.assertIn("000099-from-z.md not shown", err)
                self.assertIn("000098-from-z.md not shown", err)
        self.assertIn("to-zzz not shown", runs["log"][2])
        self.assertIn("left in place", runs["read"][2])
        self.assertEqual(left, (True, True), "tc read moved the planted link or FIFO")
        self.assertEqual(moved, ["000001-from-a.md"])
        self.assertEqual(waited[0], EXIT_TIMEOUT, f"tc wait woke for a planted entry: {waited}")
        self.assertEqual(after, TARGET_TEXT)
        self.assertEqual(printed.getvalue(), "", "show() printed what it was handed through a link")
        self.assertEqual([p.name for p, why in unshown], ["000099-from-z.md"])

    def test_a_fifo_at_a_lock_seq_or_status_is_refused_within_2_s(self):
        """A FIFO at the wait, watch or inbox lock, mail/.seq, status/x.md or a codex name's ring marker: exit 1 within FIFO_REFUSE_SECONDS, the words, the FIFO left, no mail.

        One fresh root per case; the ring marker case joins x as codex
        first. Must reject an open without O_NONBLOCK (the wait, watch,
        inbox lock and status opens block forever), one without the
        S_ISREG check (mail/.seq opens, then the send fails with a
        traceback, not words), and a marker check that lets a FIFO
        through (the send lands, then tries to write the FIFO).

        @interacts  per case: one FIFO made by hand (after a codex join for
                    the marker), then one tc run.
        @deps       _root.TcRoot.tc, landed.
        @complexity O(1) per case, six cases.
        @alloc      one TcRoot per case.
        """
        send = ["send", "--from", "a", "--to", "x", "hi"]
        cases = [
            ("wait lock", "mail/.wait-x.lock", ["wait", "x", "--timeout", LISTEN_SECONDS]),
            ("watch lock", "mail/.watch-x.lock",
             ["watch", "x", "--heartbeat", LISTEN_SECONDS, "--poll", "1", *QUIET]),
            ("inbox lock", "mail/.box-x.lock", send),
            ("mail/.seq", "mail/.seq", send),
            ("status/x.md, post", "status/x.md", ["status", "x", "busy"]),
            ("ring marker", "mail/.ring-pending-x", send),
        ]
        for label, at, argv in cases:
            with self.subTest(case=label):
                with _root.TcRoot() as root:
                    if at.startswith("mail/.ring-pending-"):
                        root.tc("join", "x", env={"CODEX_THREAD_ID": THREAD})
                    fifo = root.path / at
                    fifo.parent.mkdir(parents=True, exist_ok=True)
                    os.mkfifo(fifo)
                    try:
                        code, out, err = root.tc(*argv, timeout=FIFO_REFUSE_SECONDS)
                    except subprocess.TimeoutExpired:
                        self.fail(f"{label}: tc blocked on the FIFO past {FIFO_REFUSE_SECONDS} s")
                    still = stat.S_ISFIFO(os.lstat(fifo).st_mode)
                    mail = landed(root)
                self.assertEqual(code, EXIT_REFUSED, f"{label}: exited {code}: {err}")
                self.assertIn(FIFO_WORDS, err, label)
                self.assertTrue(still, f"{label}: the FIFO was replaced")
                self.assertEqual(mail, [], f"{label}: mail landed")

    def test_a_linked_lock_is_never_reported_as_a_listener(self):
        """In process: mail/.wait-b.lock a link to a's lock, which this process holds: listeners() names a with this pid, and never b.

        Must reject a lock key read through the link (b would show a's
        holder, while b's own tc wait is refused).

        @interacts  loads tc in process; makes mail/, one lock file and one
                    link by hand; holds an flock on the lock while
                    listeners() reads /proc/locks.
        @deps       load_tc; fcntl; tc.listeners.
        @complexity O(1).
        @alloc      one TcRoot, one module and one open file.
        """
        with _root.TcRoot() as root:
            tc = load_tc(root)
            mail = root.path / "mail"
            mail.mkdir()
            lock = mail / ".wait-a.lock"
            lock.write_text("")
            (mail / ".wait-b.lock").symlink_to(lock)
            with open(lock, "w") as held:
                fcntl.flock(held, fcntl.LOCK_EX)
                seen = tc.listeners("wait")
        self.assertEqual(seen, {"a": os.getpid()})

    def test_a_linked_inbox_and_a_planted_message_are_left_out_of_health_and_counts(self):
        """mail/to-z a link to a folder holding a message, and a link planted as a message in to-x: health and unread_count count neither.

        Must reject a summary that follows the linked inbox (z would show,
        with 1 unread) and a count of the planted link (x would show 2).

        @interacts  one send; one planted link and one linked folder made by
                    hand; one tc health --json; loads tc in process for
                    unread_count.
        @deps       _root.TcRoot.tc, plant, load_tc; json; tc.unread_count.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        with _root.TcRoot() as root:
            root.tc("send", "--from", "a", "--to", "x", REAL_TEXT)
            plant(root, "mail/to-x/000099-from-z.md")
            elsewhere = root.base / "elsewhere"
            elsewhere.mkdir()
            (elsewhere / "000001-from-z.md").write_text(TARGET_TEXT)
            (root.path / "mail" / "to-z").symlink_to(elsewhere, target_is_directory=True)
            code, out, err = root.tc("health", "--json")
            tc = load_tc(root)
            counts = {name: tc.unread_count(name) for name in ("x", "z")}
        self.assertEqual(code, 0, err)
        mail = json.loads(out)["mail"]
        self.assertEqual(sorted(mail), ["x"], "tc health counted a linked inbox")
        self.assertEqual(mail["x"]["unread"], 1, "tc health counted a planted link as mail")
        self.assertEqual(counts, {"x": 1, "z": 0})



# SHARED fix round 1 (Claude Opus 5.5, unreviewed): D20.
def marker_seen(marker):
    """(first line, inode) of the ring marker at `marker`, or (None, None) when nothing is there.

    @interacts  lstats and reads `marker`.
    @deps       os, pathlib.
    @complexity O(1): one short file.
    @alloc      the file's text, freed on return; one tuple, returned.
    """
    try:
        return marker.read_text().partition("\n")[0], os.lstat(marker).st_ino
    except FileNotFoundError:
        return None, None


def owner_patched_lstat(path_to_patch):
    """An os.lstat that reports `path_to_patch` as owned by another user (its uid plus one), and every other path as it is.

    One Linux user cannot make a file another user owns, so the D20
    owner check is shown by what tc's lstat reports (phases.md H1: "a card
    file whose recorded owner is patched").

    @interacts  none until called; then lstats the path it is given.
    @deps       os, stat, pathlib.
    @complexity O(1) per call.
    @alloc      one stat result per call.
    """
    real = os.lstat

    def lstat(path, *args, **kwargs):
        st = real(path, *args, **kwargs)
        if pathlib.Path(path) == path_to_patch:
            fields = list(st[:stat.ST_CTIME + 1])
            fields[stat.ST_UID] = st.st_uid + 1
            return os.stat_result(fields)
        return st
    return lstat


class NobodyTouchesAnotherMembersMailTest(unittest.TestCase):
    """D20: inboxes owned by their recipient at 3770, 0640 files, sends refused to names nobody joined, inbox and card owners matched, the marker rewritten in place.

    One Linux user cannot prove another user's refusals (the kernel's
    sticky and mode checks): these tests prove the modes, the owners and
    the checks tc makes. The two-user walk-through is
    qa/human/route-shared.md.

    @interacts  see the module block.
    @deps       _root.TcRoot, groups_to_test, tree, load_tc, marker_seen,
                owner_patched_lstat.
    @complexity O(1) per test.
    @alloc      one TcRoot per test and group.
    """

    def test_join_makes_the_inbox_as_the_joiner_and_new_files_are_0640(self):
        """Under shared mode, tc join x makes mail/to-x/ and read/ owned by this user at 3770 in g; a message, the card and a status are 0640, .seq and the lock 0664.

        Must reject an inbox made 2775 (any member could delete or rename
        unread mail), one open to other users, a message, card or status
        made group-writable (any member could rewrite it), and .seq or a
        lock that is not group-writable (other members could not send).

        @interacts  per group: init, a join, a send, a status; lstats the
                    entries.
        @deps       _root.TcRoot.tc, groups_to_test, tree.
        @complexity O(1) per group.
        @alloc      one TcRoot per group.
        """
        for label, name, gid in groups_to_test():
            with self.subTest(group=label), _root.TcRoot() as root:
                runs = [root.tc("init", "--shared", "--group", name),
                        root.tc("join", "x", env={"CLAUDECODE": "1"}),
                        root.tc("send", "--from", "a", "--to", "x", "hi"),
                        root.tc("status", "x", "busy")]
                made = tree(root.path)
                owners = {p: os.lstat(root.path / p).st_uid for p in ("mail/to-x", "mail/to-x/read")}
                for run in runs:
                    self.assertEqual(run[0], 0, run[2])
                for path in ("mail/to-x", "mail/to-x/read"):
                    self.assertEqual(made[path], ("folder", SHARED_INBOX_MODE, gid), path)
                self.assertEqual(owners, {"mail/to-x": os.getuid(), "mail/to-x/read": os.getuid()})
                for path in ("mail/to-x/000001-from-a.md", "cards/x.json", "status/x.md"):
                    self.assertEqual(made[path], ("file", SHARED_OWNED_FILE_MODE, gid), path)
                for path in ("mail/.seq", "mail/.box-x.lock"):
                    self.assertEqual(made[path], ("file", SHARED_WRITABLE_FILE_MODE, gid), path)

    def test_a_send_to_a_name_nobody_joined_is_refused_and_makes_no_folder(self):
        """Shared: a send to c, with no card and no inbox, exits 1 with C4's words, makes no mail/to-c and takes no number. Private: the same send lands, with O1's warning.

        Must reject a shared send that makes the inbox (the sender would
        own the recipient's inbox, and could chmod or empty it).

        @interacts  two roots: init and a send in one, a send in the other.
        @deps       _root.TcRoot.tc, groups_to_test, tree.
        @complexity O(1).
        @alloc      two TcRoots.
        """
        label, name, gid = groups_to_test()[0]
        with _root.TcRoot() as root:
            root.tc("init", "--shared", "--group", name)
            code, out, err = root.tc("send", "--from", "a", "--to", "c", "hi")
            made = tree(root.path)
        with _root.TcRoot() as private:
            control = private.tc("send", "--from", "a", "--to", "c", "hi")
        self.assertEqual(code, EXIT_REFUSED, f"exited {code}: {err}")
        self.assertIn(NOBODY_WORDS.format(name="c"), err)
        self.assertEqual([p for p in made if p.startswith("mail/to-c")], [], "a refused send made an inbox")
        self.assertNotIn("mail/.seq", made, "a refused send took a number")
        self.assertEqual(control[0], 0, control[2])
        self.assertIn("new inbox: nobody has joined as c", control[2])

    def test_a_card_with_no_inbox_is_refused_until_its_owner_rejoins(self):
        """c joins while the mailbox is private (a card, no inbox), then init: a send to c exits 1 and asks c's owner to rejoin; after tc join c it lands.

        Must reject a send that makes c's inbox as the sender.

        @interacts  a join, init, a refused send, a rejoin, a send.
        @deps       _root.TcRoot.tc, groups_to_test.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        label, name, gid = groups_to_test()[0]
        with _root.TcRoot() as root:
            root.tc("join", "c", env={"CLAUDECODE": "1"})
            root.tc("init", "--shared", "--group", name)
            refused = root.tc("send", "--from", "a", "--to", "c", "hi")
            boxed = (root.path / "mail" / "to-c").exists()
            rejoined = root.tc("join", "c", env={"CLAUDECODE": "1"})
            sent = root.tc("send", "--from", "a", "--to", "c", "hi")
        self.assertEqual(refused[0], EXIT_REFUSED, refused[2])
        self.assertIn(NO_INBOX_WORDS, refused[2])
        self.assertIn(REJOIN_WORDS.format(name="c"), refused[2])
        self.assertFalse(boxed, "a refused send made c's inbox")
        self.assertEqual(rejoined[0], 0, rejoined[2])
        self.assertEqual(sent[0], 0, sent[2])

    def test_an_inbox_whose_owner_is_not_its_cards_owner_is_refused(self):
        """In process, with lstat reporting cards/b.json as another user's: a send to b and b's wait poll exit 1 with the words, and nothing lands.

        Must reject a check that compares nothing (the send would land in
        an inbox its recipient does not control).

        @interacts  init, a join and a send; loads tc in process and runs
                    deliver_local and unread with os.lstat wrapped and
                    stderr captured.
        @deps       _root.TcRoot.tc, groups_to_test, load_tc,
                    owner_patched_lstat; contextlib, io, unittest.mock;
                    tc.deliver_local, tc.unread.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        label, name, gid = groups_to_test()[0]
        with _root.TcRoot() as root:
            root.tc("init", "--shared", "--group", name)
            root.tc("join", "b", env={"CLAUDECODE": "1"})
            root.tc("send", "--from", "a", "--to", "b", "first")
            tc = load_tc(root)
            stops, said = [], io.StringIO()
            with mock.patch.object(os, "lstat", owner_patched_lstat(root.path / "cards" / "b.json")), \
                    contextlib.redirect_stderr(said):
                for call in (lambda: tc.deliver_local(None, "a", "b", "second"), lambda: tc.unread("b", True)):
                    with self.assertRaises(SystemExit) as stop:
                        call()
                    stops.append(stop.exception.code)
            mail = landed(root)
        self.assertEqual(stops, [EXIT_REFUSED, EXIT_REFUSED])
        self.assertIn(OWNER_WORDS, said.getvalue())
        self.assertEqual(mail, ["mail/to-b/000001-from-a.md"])

    def test_join_refuses_a_name_whose_card_or_inbox_another_user_owns(self):
        """In process, with lstat reporting cards/c.json, then mail/to-d, as another user's: claim_inbox exits 1 with words and makes nothing.

        Must reject a join that makes the inbox anyway: the name's inbox
        and card would then belong to two users, and item 4 would refuse
        every send to it.

        @interacts  init; one card file and one folder made by hand; loads
                    tc in process and runs claim_inbox twice with os.lstat
                    wrapped and stderr captured.
        @deps       _root.TcRoot.tc, groups_to_test, load_tc,
                    owner_patched_lstat; contextlib, io, unittest.mock;
                    tc.claim_inbox.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        label, name, gid = groups_to_test()[0]
        with _root.TcRoot() as root:
            root.tc("init", "--shared", "--group", name)
            (root.path / "cards").mkdir(exist_ok=True)
            (root.path / "cards" / "c.json").write_text("{}\n")
            (root.path / "mail").mkdir(exist_ok=True)
            (root.path / "mail" / "to-d").mkdir()
            tc = load_tc(root)
            stops, said = [], io.StringIO()
            for who, at in (("c", root.path / "cards" / "c.json"), ("d", root.path / "mail" / "to-d")):
                with mock.patch.object(os, "lstat", owner_patched_lstat(at)), contextlib.redirect_stderr(said):
                    with self.assertRaises(SystemExit) as stop:
                        tc.claim_inbox(who)
                stops.append(stop.exception.code)
            made = [os.path.lexists(root.path / "mail" / "to-c"),
                    os.path.lexists(root.path / "mail" / "to-d" / "read")]
        self.assertEqual(stops, [EXIT_REFUSED, EXIT_REFUSED])
        self.assertIn(TAKEN_CARD_WORDS, said.getvalue())
        self.assertIn(TAKEN_INBOX_WORDS, said.getvalue())
        self.assertEqual(made, [False, False], "a refused join made a folder")

    def test_the_ring_marker_is_cleared_by_rewriting_never_unlinked(self):
        """Shared: a failed ring leaves the marker `failed`; a rejoin with nothing unread rewrites it `clear`; a ring that exits 0 leaves it `clear`. One inode throughout, 0664 in g, no .tmp.

        Must reject a marker removed (unlink) or replaced (a .tmp renamed
        over it): under the sticky mail/ only its owner could do either,
        and the inode would change.

        @interacts  init, a codex join, two sends, a read, a rejoin; a fake
                    codex that fails once, then queues.
        @deps       _root.TcRoot.tc, _root.TcRoot.fake_bin, groups_to_test,
                    marker_seen.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        label, name, gid = groups_to_test()[0]
        codex = {"CODEX_THREAD_ID": THREAD, "CLAUDECODE": None}
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("codex", [CODEX_FAILS, CODEX_QUEUED])
            marker = root.path / "mail" / ".ring-pending-x"
            runs = [root.tc("init", "--shared", "--group", name), root.tc("join", "x", env=codex),
                    root.tc("send", "--from", "a", "--to", "x", "one")]
            seen = [marker_seen(marker)]
            runs += [root.tc("read", "x"), root.tc("join", "x", env=codex)]
            seen.append(marker_seen(marker))
            runs.append(root.tc("send", "--from", "a", "--to", "x", "two"))
            seen.append(marker_seen(marker))
            self.assertTrue((folder.parent / "calls.jsonl").exists(), "the fake codex never ran")
            rang = len(calls())
            st = os.lstat(marker)
            left = sorted(p.name for p in marker.parent.glob(".ring-pending-x.*"))
        for run in runs:
            self.assertEqual(run[0], 0, run[2])
        inode = seen[0][1]
        self.assertEqual(seen, [(FAILED_STATE, inode), (CLEAR_STATE, inode), (CLEAR_STATE, inode)])
        self.assertEqual(rang, 2)
        self.assertEqual((stat.S_IMODE(st.st_mode), st.st_gid), (SHARED_WRITABLE_FILE_MODE, gid))
        self.assertEqual(left, [], "a marker write left a .tmp behind")

    def test_a_status_post_over_a_file_this_user_may_not_write_is_refused_with_words(self):
        """Shared: status/x.md made read-only for its owner, then tc status x: exit 1, words naming the owner, no traceback, the file as it was.

        Stands in for another member's 0640 status file (D20 item 2),
        which one user cannot make. Skipped as root, who may write it.

        @interacts  init, two status posts; one chmod by hand.
        @deps       _root.TcRoot.tc, groups_to_test.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        if os.geteuid() == 0:
            self.skipTest("root may write a read-only file")
        label, name, gid = groups_to_test()[0]
        with _root.TcRoot() as root:
            root.tc("init", "--shared", "--group", name)
            root.tc("status", "x", "first")
            status = root.path / "status" / "x.md"
            status.chmod(READ_ONLY_FILE_MODE)
            code, out, err = root.tc("status", "x", "second")
            after = status.read_text()
        self.assertEqual(code, EXIT_REFUSED, err)
        self.assertIn(MAY_NOT_OPEN_WORDS, err)
        self.assertNotIn("Traceback", err)
        self.assertIn("first", after)

    def test_a_read_that_may_not_move_a_message_names_it_and_leaves_it_unread(self):
        """In process, with one rename refused (EPERM, as the sticky inbox refuses a non-owner): tc read moves the rest, names that one, exits 1.

        Must reject a traceback on the refused rename (a member running tc
        read on another member's inbox).

        @interacts  three sends; loads tc in process and runs cmd_read with
                    Path.rename wrapped and stdout and stderr captured.
        @deps       _root.TcRoot.tc, load_tc; argparse, contextlib, errno,
                    io, unittest.mock; tc.cmd_read.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        with _root.TcRoot() as root:
            for sender in ("a", "c", "d"):
                root.tc("send", "--from", sender, "--to", "b", f"from {sender}")
            tc = load_tc(root)
            real = pathlib.Path.rename

            def rename(path, target):
                if path.name == "000002-from-c.md":
                    raise PermissionError(errno.EPERM, os.strerror(errno.EPERM), str(path))
                return real(path, target)
            out, err = io.StringIO(), io.StringIO()
            with mock.patch.object(pathlib.Path, "rename", rename), contextlib.redirect_stdout(out), \
                    contextlib.redirect_stderr(err):
                with self.assertRaises(SystemExit) as stop:
                    tc.cmd_read(argparse.Namespace(name="b"))
            box = root.path / "mail" / "to-b"
            unread = sorted(p.name for p in box.glob("*.md"))
            moved = sorted(p.name for p in (box / "read").glob("*.md"))
        self.assertEqual(stop.exception.code, EXIT_REFUSED)
        self.assertIn(f"000002-from-c.md {NOT_MOVED_WORDS}", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())
        self.assertEqual(unread, ["000002-from-c.md"])
        self.assertEqual(moved, ["000001-from-a.md", "000003-from-d.md"])
        self.assertIn("from a", out.getvalue())



# SHARED fix round 1 (Claude Opus 5.5, unreviewed): D19 (init makes the
# four), the audit's MEDIUM-4 and LOW-2 to LOW-8.
def run_init(tc, group):
    """Run tc.cmd_init in process for `group`: (exit code, stdout, stderr).

    @interacts  runs cmd_init, which sets this process's umask (the
                caller's setUp puts it back) and changes the root's entries;
                captures stdout and stderr.
    @deps       argparse, contextlib, io; tc.cmd_init.
    @complexity as cmd_init.
    @alloc      the captured text, returned.
    """
    out, err = io.StringIO(), io.StringIO()
    code = 0
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            tc.cmd_init(argparse.Namespace(shared=True, group=group))
        except SystemExit as stop:
            code = stop.code
    return code, out.getvalue(), err.getvalue()


class InitAndRefusalsTest(unittest.TestCase):
    """make_folder never leaves a folder in the wrong group; init reruns cleanly, walks what it cannot change and says the real state; the refusals' words; health never raises.

    @interacts  see the module block.
    @deps       _root.TcRoot, groups_to_test, tree, load_tc, run_init.
    @complexity O(1) per test.
    @alloc      one TcRoot per test.
    """

    def setUp(self):
        """Set this process's umask to CHILD_UMASK; the cleanup puts the old one back (in-process init sets its own).

        @interacts  sets the umask of this process (and so of every child).
        @deps       os.
        @complexity O(1).
        @alloc      none.
        """
        self.addCleanup(os.umask, os.umask(CHILD_UMASK))

    def test_make_folder_removes_a_folder_it_cannot_share_and_refuses(self):
        """In process, with fchown refused: make_folder(outbox/sent) exits 1 with words and leaves no outbox/sent.

        Must reject a make_folder that leaves the folder (the next run
        would accept it in the maker's group, MEDIUM-4).

        @interacts  init; loads tc in process and runs make_folder with
                    os.fchown replaced and stderr captured.
        @deps       _root.TcRoot.tc, groups_to_test, load_tc; contextlib,
                    errno, io, unittest.mock; tc.make_folder.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        label, name, gid = groups_to_test()[0]

        def refused(fd, uid, gid):
            raise PermissionError(errno.EPERM, os.strerror(errno.EPERM))
        with _root.TcRoot() as root:
            root.tc("init", "--shared", "--group", name)
            tc = load_tc(root)
            said = io.StringIO()
            with mock.patch.object(os, "fchown", refused), contextlib.redirect_stderr(said):
                with self.assertRaises(SystemExit) as stop:
                    tc.make_folder(root.path / "outbox" / "sent")
            left = os.path.lexists(root.path / "outbox" / "sent")
        self.assertEqual(stop.exception.code, EXIT_REFUSED)
        self.assertIn(REMOVED_WORDS, said.getvalue())
        self.assertFalse(left, "make_folder left a folder it could not give the group")

    def test_a_shared_folder_in_the_wrong_group_is_refused_never_accepted(self):
        """Shared with a supplementary group, status/ moved by hand to the primary group: tc status x busy exits 1 with words and writes nothing.

        Must reject a make_folder that accepts any folder that is there
        (other members could not write in it). Needs a supplementary
        group; skipped with a reason without one.

        @interacts  init; one chown by hand; one status post.
        @deps       _root.TcRoot.tc, groups_to_test.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        found = groups_to_test()
        if len(found) < 2:
            self.skipTest("the running user has no named supplementary group, so no folder can be "
                          "put in a group other than the one shared")
        (_, primary, primary_gid), (_, name, gid) = found[0], found[1]
        with _root.TcRoot() as root:
            root.tc("init", "--shared", "--group", name)
            os.chown(root.path / "status", -1, primary_gid)
            code, out, err = root.tc("status", "x", "busy")
            wrote = os.path.lexists(root.path / "status" / "x.md")
        self.assertEqual(code, EXIT_REFUSED, err)
        self.assertIn(WRONG_GROUP_WORDS.format(have=primary, want=name), err)
        self.assertFalse(wrote, "a status landed in a folder in the wrong group")

    def test_a_rerun_of_init_changes_nothing_already_right(self):
        """In process: init, then init again over the same root: the second run calls fchown and fchmod on nothing and exits 0.

        Linux lets only an entry's owner change its group, so on a live
        shared mailbox every entry another member owns would be an EPERM
        skip. Must reject a share_entry that changes entries already in g
        at their mode (LOW-2).

        @interacts  a join, a send, a status; loads tc in process and runs
                    cmd_init twice, the second time with os.fchown and
                    os.fchmod wrapped to count calls.
        @deps       _root.TcRoot.tc, groups_to_test, load_tc, run_init;
                    unittest.mock.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        label, name, gid = groups_to_test()[0]
        with _root.TcRoot() as root:
            root.tc("join", "b", env={"CLAUDECODE": "1"})
            root.tc("send", "--from", "a", "--to", "b", "hi")
            root.tc("status", "b", "busy")
            tc = load_tc(root)
            first = run_init(tc, name)
            with mock.patch.object(os, "fchown", wraps=os.fchown) as chowned, \
                    mock.patch.object(os, "fchmod", wraps=os.fchmod) as chmodded:
                second = run_init(tc, name)
        self.assertEqual(first[0], 0, first[2])
        self.assertEqual(second[0], 0, second[2])
        self.assertEqual((chowned.call_count, chmodded.call_count), (0, 0),
                         "a rerun changed entries already in the group at their mode")

    def test_init_walks_a_top_folder_whose_own_change_failed(self):
        """In process, with share_entry refusing mail/ itself: init still gives the message under it 0640, names mail/, exits 1.

        Must reject a walk that skips everything under a top folder it
        could not change, uncounted and unnamed (LOW-3).

        @interacts  a send; loads tc in process and runs cmd_init with
                    share_entry wrapped to refuse mail/.
        @deps       _root.TcRoot.tc, groups_to_test, load_tc, run_init;
                    unittest.mock; tc.share_entry.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        label, name, gid = groups_to_test()[0]
        with _root.TcRoot() as root:
            root.tc("send", "--from", "a", "--to", "b", "hi")
            tc = load_tc(root)
            real = tc.share_entry

            def share_entry(path, gid):
                if path == root.path / "mail":
                    return "folder", "Operation not permitted"
                return real(path, gid)
            with mock.patch.object(tc, "share_entry", share_entry):
                code, out, err = run_init(tc, name)
            message = os.lstat(root.path / "mail" / "to-b" / "000001-from-a.md")
        self.assertEqual(code, EXIT_REFUSED, err)
        self.assertIn(f"skipped {root.path / 'mail'}: Operation not permitted", err)
        self.assertEqual((stat.S_IMODE(message.st_mode), message.st_gid), (SHARED_OWNED_FILE_MODE, gid),
                         "init did not reach a message under the top folder it could not change")

    def test_when_init_cannot_write_shared_its_words_match_the_state_and_come_after_the_skips(self):
        """ROOT made read-only: init over a shared root exits 0 (.shared already right); over a private one it says `stays private`, after the skip line; over one shared with another group it says so.

        Must reject a rewrite of a .shared that already names the group,
        words that call a shared mailbox private, and a refusal that
        drops the skip lines (LOW-4). Skipped as root, who may write a
        read-only folder.

        @interacts  three roots: sends and statuses, init, a FIFO made by
                    hand, a hand-written .shared; ROOT chmodded read-only
                    and back.
        @deps       _root.TcRoot.tc, groups_to_test.
        @complexity O(1).
        @alloc      three TcRoots.
        """
        if os.geteuid() == 0:
            self.skipTest("root may write a read-only folder")
        label, name, gid = groups_to_test()[0]
        runs = {}
        for case in ("shared", "private", "other"):
            with _root.TcRoot() as root:
                root.tc("send", "--from", "a", "--to", "b", "hi")
                root.tc("status", "b", "busy")
                if case == "shared":
                    root.tc("init", "--shared", "--group", name)
                if case == "private":
                    os.mkfifo(root.path / "mail" / "planted-fifo")
                if case == "other":
                    (root.path / ".shared").write_text(f"{OTHER_GROUP}\n")
                mode = stat.S_IMODE(os.lstat(root.path).st_mode)
                root.path.chmod(READ_ONLY_FOLDER_MODE)
                try:
                    runs[case] = root.tc("init", "--shared", "--group", name)
                finally:
                    root.path.chmod(mode)
        self.assertEqual(runs["shared"][0], 0, runs["shared"][2])
        code, out, err = runs["private"]
        self.assertEqual(code, EXIT_REFUSED, err)
        self.assertIn(STAYS_PRIVATE_WORDS, err)
        self.assertIn("planted-fifo", err)
        self.assertLess(err.index("planted-fifo"), err.index(STAYS_PRIVATE_WORDS),
                        "the skip line came after the refusal")
        self.assertEqual(runs["other"][0], EXIT_REFUSED, runs["other"][2])
        self.assertIn(STAYS_SHARED_WORDS.format(group=OTHER_GROUP), runs["other"][2])

    def test_a_card_rename_tc_may_not_make_is_refused_with_words_and_no_tmp(self):
        """In process, with the card's rename refused (EPERM, as the sticky cards/ refuses another user's card): write_card exits 1 with words and leaves no .tmp.

        Must reject a traceback and a .tmp left in cards/ (LOW-5).

        @interacts  loads tc in process and runs write_card with os.rename
                    wrapped to refuse cards/b.json and stderr captured.
        @deps       _root.TcRoot, load_tc; contextlib, errno, io,
                    unittest.mock; tc.write_card.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        card = {"name": "b", "kind": "other", "route": "local"}
        with _root.TcRoot() as root:
            tc = load_tc(root)
            real = os.rename
            target = root.path / "cards" / "b.json"

            def rename(src, dst, *args, **kwargs):
                if pathlib.Path(dst) == target:
                    raise PermissionError(errno.EPERM, os.strerror(errno.EPERM), str(src))
                return real(src, dst, *args, **kwargs)
            said = io.StringIO()
            with mock.patch.object(os, "rename", rename), contextlib.redirect_stderr(said):
                with self.assertRaises(SystemExit) as stop:
                    tc.write_card(card)
            left = sorted(p.name for p in (root.path / "cards").iterdir())
        self.assertEqual(stop.exception.code, EXIT_REFUSED)
        self.assertIn(TAKEN_CARD_WORDS, said.getvalue())
        self.assertEqual(left, [], "a refused card left its .tmp behind")

    def test_the_unreadable_shared_refusal_says_what_to_check(self):
        """.shared at no access: a send says this user needs search access, not run init; a .shared of two lines says rewrite it; init on an unreachable ROOT says the same, never a traceback.

        Must reject one sentence for every cause (LOW-7). The access cases
        are skipped as root, who reads anything.

        @interacts  three roots: one .shared chmodded to no access and
                    back, one hand-written .shared, one temp folder made
                    unsearchable and back; a send or an init in each.
        @deps       _root.TcRoot.tc.
        @complexity O(1).
        @alloc      three TcRoots.
        """
        with _root.TcRoot() as root:
            (root.path / ".shared").write_text("one\ntwo\n")
            malformed = root.tc("send", "--from", "a", "--to", "b", "hi")
        self.assertEqual(malformed[0], EXIT_REFUSED, malformed[2])
        self.assertIn(REWRITE_WORDS, malformed[2])
        if os.geteuid() == 0:
            self.skipTest("root reads any file, so .shared cannot be made unreadable")
        with _root.TcRoot() as root:
            marker = root.path / ".shared"
            marker.write_text("anygroup\n")
            marker.chmod(NO_ACCESS_MODE)
            locked = root.tc("send", "--from", "a", "--to", "b", "hi")
        with _root.TcRoot() as root:
            root.base.chmod(NO_ACCESS_MODE)
            try:
                unreachable = root.tc("init", "--shared", "--group", groups_to_test()[0][1])
            finally:
                root.base.chmod(OWNER_FOLDER_MODE)
        self.assertEqual(locked[0], EXIT_REFUSED, locked[2])
        self.assertIn(SEARCH_WORDS, locked[2])
        self.assertNotIn(REWRITE_WORDS, locked[2])
        self.assertEqual(unreachable[0], EXIT_REFUSED, unreachable[2])
        self.assertIn(SEARCH_WORDS, unreachable[2])
        self.assertNotIn("Traceback", unreachable[2])

    def test_health_snapshot_reports_an_unreadable_shared_as_a_field(self):
        """In process, .shared of two lines: health_snapshot() returns, shared_group null and shared_problem saying why.

        Must reject a snapshot that raises (BOARD's feed would answer 500
        on every poll, LOW-8).

        @interacts  writes .shared by hand; loads tc in process and calls
                    health_snapshot (reads /proc).
        @deps       _root.TcRoot, load_tc; tc.health_snapshot.
        @complexity O(p) over p processes on the machine (hundreds).
        @alloc      one TcRoot, one module and one snapshot.
        """
        with _root.TcRoot() as root:
            (root.path / ".shared").write_text("one\ntwo\n")
            tc = load_tc(root)
            snap = tc.health_snapshot()
        self.assertIsNone(snap["shared_group"])
        self.assertIn("names no group", snap["shared_problem"])


if __name__ == "__main__":
    unittest.main()
