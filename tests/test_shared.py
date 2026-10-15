"""
Tests for the shared mailbox (contract C4, D16; task H1): `tc init --shared
--group <g>`, the umask, the group and setgid on folders tc makes after
init, and the `mailbox shared with group <g>` or `mailbox private` line in
`tc health`.

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
            under the root. Writes nothing by hand.
@deps       python3 stdlib (grp, json, os, pathlib, stat, sys, unittest);
            tests/_root.py.
@complexity O(1) per test: a handful of tc runs over a root of a few dozen
            entries, once per group tested (one or two).
@alloc      one TcRoot per test and group, removed when its context exits.
"""

import grp
import json
import os
import pathlib
import stat
import sys
import unittest

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


def shared_as(kind, gid):
    """The (kind, mode, gid) C4 wants for a `kind` entry shared with `gid`.

    @interacts  none.
    @deps       FOLDER_MODE, FILE_MODE.
    @complexity O(1).
    @alloc      one tuple, returned.
    """
    return (kind, FOLDER_MODE if kind == "folder" else FILE_MODE, gid)


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
        """After init, every folder is 2775 and every file 0664, all in group g; so is a message sent after.

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
                self.assertEqual(after, {p: shared_as(k, gid) for p, (k, m, g) in after.items()})
                self.assertEqual(marker, f"{name}\n")
                self.assertEqual(sent[0], 0, sent[2])
                self.assertEqual(later["mail/to-b/000002-from-a.md"], shared_as("file", gid))
                self.assertEqual(later["mail/.seq"], shared_as("file", gid))

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
        """Init on an empty root, then a join, a send, a status and a wait: each new folder 2775 in g, each file 0664 in g (D16).

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
                self.assertEqual(made, {p: shared_as(k, gid) for p, (k, m, g) in made.items()})


if __name__ == "__main__":
    unittest.main()
