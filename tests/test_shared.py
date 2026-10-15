"""
Tests for the shared mailbox (contract C4, D16; task H1): `tc init --shared
--group <g>`, the umask, the group and setgid on folders tc makes after
init, and the `mailbox shared with group <g>` or `mailbox private` line in
`tc health`. And D17 (SHARED D17, Claude Opus 5.5, unreviewed): the
sticky bit on mail/, status/, cards/ and outbox/, a symlink planted at a
lock, mail/.seq, a status file or the ring marker refused with its target
unchanged, a symlink planted as an inbox or its read/ refused with nothing
landing, and a file already there reopened without O_CREAT.

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
            once, with os.open wrapped to record its flags.
@deps       python3 stdlib (grp, importlib, json, os, pathlib, stat, sys,
            unittest, unittest.mock); tests/_root.py.
@complexity O(1) per test: a handful of tc runs over a root of a few dozen
            entries, once per group tested (one or two).
@alloc      one TcRoot per test and group, removed when its context exits.
"""

import grp
import importlib.machinery
import importlib.util
import json
import os
import pathlib
import stat
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
# instead of moving them. C4: folders 2775 (setgid), files 0664.
FOLDER_MODE = 0o2775
FILE_MODE = 0o664
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
    """The (kind, mode, gid) C4 and D17 want for the `kind` entry at relative `path`, shared with `gid`.

    A file: FILE_MODE. A folder: TOP_FOLDER_MODE (sticky, D17) when it is
    one of SHARED_FOLDERS itself, else FOLDER_MODE.

    @interacts  none.
    @deps       SHARED_FOLDERS, TOP_FOLDER_MODE, FOLDER_MODE, FILE_MODE.
    @complexity O(1).
    @alloc      one tuple, returned.
    """
    if kind != "folder":
        return (kind, FILE_MODE, gid)
    return (kind, TOP_FOLDER_MODE if path in SHARED_FOLDERS else FOLDER_MODE, gid)


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
        """After init, every folder is 2775 (3775 for the four) and every file 0664, all in group g; so is a message sent after.

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
                                                 "mail/to-b/read", "status", "status/b.md"])
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
        """Init on an empty root, then a join, a send, a status and a wait: each new folder 2775 (3775 for the four) in g, each file 0664 in g (D16).

        cards/ comes from the first join, mail/, the inbox and its read/
        from the first send, status/ from the first status, and the wait
        lock from a wait that times out at once. Must reject a later
        folder without setgid (0775), or a top folder left in the
        primary group (the supplementary run), and any file at 0644.

        @interacts  per group: init, a join, a send, a status, a wait.
        @deps       _root.TcRoot.tc, groups_to_test, tree, shared_as.
        @complexity O(1) per group.
        @alloc      one TcRoot per group.
        """
        for label, name, gid in groups_to_test():
            with self.subTest(group=label), _root.TcRoot() as root:
                code, out, err = root.tc("init", "--shared", "--group", name)
                self.assertEqual(code, 0, f"tc init exited {code}: {err}")
                self.assertEqual(tree(root.path), {}, "init made a folder: C4 reaches only what is there")
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
                                                "mail/to-b/000001-from-a.md", "mail/to-b/read", "status",
                                                "status/b.md"])
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
        """After init, mail/, outbox/ (made by hand, as the ssh route will) and the later cards/ and status/ are 3775; inboxes, read/ and outbox/sent/ are 2775.

        Must reject a top folder without the sticky bit (a member could
        delete or swap another user's inbox, card or lock), and an inbox
        with it (tc read could not move mail another user wrote).

        @interacts  per group: a send, one folder pair made by hand, init,
                    a join, a status and a second send.
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
                            root.tc("send", "--from", "a", "--to", "c", "after")]
                    folders = {p: (m, g) for p, (k, m, g) in tree(root.path).items() if k == "folder"}
                self.assertEqual(code, 0, err)
                for run in runs:
                    self.assertEqual(run[0], 0, run[2])
                self.assertEqual(folders, {
                    "mail": (TOP_FOLDER_MODE, gid), "outbox": (TOP_FOLDER_MODE, gid),
                    "cards": (TOP_FOLDER_MODE, gid), "status": (TOP_FOLDER_MODE, gid),
                    "mail/to-b": (FOLDER_MODE, gid), "mail/to-b/read": (FOLDER_MODE, gid),
                    "mail/to-c": (FOLDER_MODE, gid), "mail/to-c/read": (FOLDER_MODE, gid),
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


if __name__ == "__main__":
    unittest.main()
