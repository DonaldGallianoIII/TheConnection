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
through a link. And D20 (the same round): inboxes owned by their
recipient at 3770, message, card and status files at 0640, a send to a
name nobody joined refused, an inbox not its card owner's refused, the
ring marker rewritten in place; then make_folder, init and the refusals'
words from the audit's MEDIUM-4 and LOW-1 to LOW-8. And D21 (SHARED D21,
Claude Opus 5.5, unreviewed): .shared at 0644 after init and after its
owner's rerun (a 0664 one set to 0644, and named by a member's rerun),
another member's init refused before it changes anything (another group,
or an unreadable .shared) and told who may change the group, a shared
send to an inbox with no card refused with nothing written, and a
private one still delivered. And, from BOARD's review, a status file's
age never taken through a link. And D20's bound (SHARED fix round 2,
Claude Opus 5.5, unreviewed): a mail/.seq set back never makes a send
replace a message, unread or read, and a lock held by another process
makes send, read, a codex join, tc card and a codex send fail within
LOCK_WAIT_SECONDS, never hang. And round 3 (SHARED fix round 3, Claude
Opus 5.5, unreviewed): a held lock exits 10 (busy, D23); tc read never
replaces a read message with a file planted under its name; one send's
waits on mail/.seq share one deadline, however many numbers it skips;
init refuses a ROOT the group may write, sticky or not, and any folder
from ROOT up to /, as given and by its real path, that another user
owns or the group may write without the sticky bit; a send on a
filesystem without hard links says so; and an inbox a command cannot
look into stops it with words, never a traceback. And round 4 (SHARED
fix round 4, Claude Opus 5.5, unreviewed): tc read names neither file
as the forgery when two share a name, whichever was planted, and a
planted name up to the filesystem's name limit still moves, so tc wait
wakes for it at most once; init's walk runs ROOT's rule on ROOT's real
path whatever the given walk passed; a local send whose card turns
codex under a held lock waits one bound; tc log says it could not look
at a read/; and a send out of numbers exits 10. And round 5 (SHARED fix
round 5, Claude Opus 5.5, unreviewed): init's walk gives the owner of
.shared no trust (D28), so a member who made ROOT first stops the init
user's own init, naming that member, and a member's rerun on the init
user's ROOT is refused with no charge; tc read names as not moved a
file a hard link kept in the inbox, never as read; a cut by-hand name
made of dots keeps its .md; and a file planted at the next message's
.tmp name sends the send to the number after, untouched. And round 6
(SHARED fix round 6, Claude Opus 5.5, unreviewed): that refusal fixes
the member's own entries itself, through fchown and fchmod on a
no-follow descriptor, and nothing else (D29); a link swapped in for the
member's entry, before init or while tc holds it open, leaves the
link's target as it was, and tc says it skipped the link; an entry
another user owns at its open is skipped; a folder in the wrong group
and an entry init skips tell their owner to run tc init, which puts
them right, and no chgrp or chmod line is printed; a relative TC_ROOT
still prints absolute paths; and a send out of numbers names the last
name it found taken, and blames mail/.seq only when a message's name
was taken. And round 7 (SHARED fix round 7, Claude Opus 5.5,
unreviewed): a folder on the way that a member swaps for a link after
init's walk listed it, in a member's rerun and in the init user's own
init, is named and never entered, and the folder the link leads to,
with all in it, keeps its stat; and a send out of numbers whose every
try met a .tmp name says what it found and never that mail/.seq was
not behind, even with the counter set back. And round 8 (SHARED fix
round 8, Claude Opus 5.5, unreviewed): init's own stack walk, in both
walks, names a folder past WALK_MAX_DEPTH and a top it may list but
not search, never a traceback, and never opens a link (an os.open
spy); ROOT, its parent, each of the four, an inbox and its read/, and
the entry in it, each swapped mid-walk for a link or another folder,
never lead either walk outside the mailbox, and init names what it
refused or skipped; and a hard-linked file is skipped and named,
unchanged at both names.

Model:  Claude Opus 5.5 (the SHARED lane agent), 2026-10-14
Status: unreviewed

The harness cannot make a second Linux user, so modes and the group are
tested with the running user's own groups: the primary group, and a
supplementary group when the user has one (os.getgroups()). The
supplementary group is the sharper test. A folder made without setgid, or
a top folder left without its chown, takes the primary group, not g, and
fails there. A user with no named supplementary group gets that run as a
skipped subtest with its reason (groups_to_test), never a silent absence.
One user cannot prove another user's refusals either: the D20 tests prove
the modes, the owners and the checks tc makes, and patch what lstat
reports where a second owner is needed. The second-user walk-through is
the owner's human QA (D4, qa/human/route-shared.md).

@interacts  runs ../tc through tests/_root.py under a throwaway TC_ROOT.
            Every class inherits UmaskTestCase, which sets this process's
            umask to CHILD_UMASK for each test and puts the old one back
            after; children inherit it, so a tc that never sets its own
            umask writes PRIVATE_FILE_MODE and fails. Reads
            the group database and this process's groups. Stats every entry
            under the root. The H1 tests write nothing by hand; the D17
            tests make folders, symlinks, message files and link targets by
            hand (the targets in the root's temp folder, outside TC_ROOT),
            run a fake codex through the harness, and load tc in process
            once, with os.open wrapped to record its flags. The D19 tests
            make FIFOs and links by hand, hold an flock on one lock file in
            this process, and load tc in process to call show() (stdout
            captured), listeners() and unread_count(). The D20 and init
            tests make cards, folders and FIFOs by hand, chmod or chown
            entries they own (ROOT and its temp folder put back before the
            root is removed), and load tc in process to run deliver_local,
            unread, claim_inbox, make_folder, cmd_init, cmd_read,
            write_card and health_snapshot with os.lstat, os.fchown,
            os.fchmod, os.rename or share_entry wrapped (os.rename for
            cmd_read since P3 fix round 1a, Claude Opus 5.5, unreviewed:
            it moves by name between open folders, D35).
            The D21 tests make an inbox and its read/ by hand, write
            and chmod .shared by hand, chmod ROOT read-only and back, and
            load tc in process to run cmd_init with os.lstat wrapped or
            os.geteuid replaced. The
            status age test makes a folder outside TC_ROOT, a file in it
            and a link to it in status/, and chmods that folder to no
            access and back. The round 2 tests write mail/.seq by hand,
            hold flocks on lock files and the ring marker in this process
            while tc children run under timeouts (several roots at once),
            and read every file under a root before and after. The round
            3 tests write planted files into an inbox and its read/ by
            hand, and run a member's loop as a child (python3 -c
            SEQ_HOLDER, killed by the harness by its pid) that holds
            mail/.seq on and off and plants empty files in read/. They
            chmod the root's temp folder and folders they make in it,
            and an inbox, and put each back; make links by hand; read the
            user database; and load tc in process to run cmd_init with
            os.lstat wrapped and deliver_local with os.link replaced.
            The round 4 tests write files under long names into an inbox
            and its read/, read read/'s name limit (os.pathconf) and run
            tc wait in the foreground under ONE_POLL_SECONDS; plant
            PLANTED_NAMES empty files in read/; hold an inbox lock here
            alone, then shared, while a send waits on it (read in
            /proc/locks with its access, lock_waiters) and write a card
            by hand under it; make a folder with a link to itself and
            chmod it 1777; chmod an inbox to read without search and
            back; and load tc in process to run cmd_init. The round 5
            tests write .shared by hand, chmod a status file, run
            cmd_init in process with os.geteuid replaced (and os.lstat
            wrapped); plant a name of dots and md in an inbox and its
            read/; plant a file at a .tmp name in an inbox; and run
            cmd_read in process with os.rename replaced by a hard link
            at its target. The round 6 tests write, chown and chmod a
            member's old message in another inbox's read/ by hand, make
            a folder outside TC_ROOT and a link to it at that message's
            name (by hand, or from a wrapped os.fchown after renaming the
            message aside), and run cmd_init in process with os.lstat
            wrapped (ROOT and .shared reported as another user's), and
            os.chmod, os.chown, os.lchown, os.fchown and os.fchmod
            wrapped to count calls; plant a .tmp name in an inbox for
            each of PLANTED_NAMES numbers; and run tc as a child with
            TC_ROOT relative and the root's temp folder as its working
            folder. The round 7 tests make a second folder in an inbox,
            a file in it and in read/ (chowned and chmodded), and a
            folder holding a folder and a file outside TC_ROOT; a wrapped
            os.fchown renames one inbox folder aside and links the
            outside folder at its name; and they run cmd_init in process
            with os.lstat wrapped (a call by name in a folder's
            descriptor is matched by the file it finds); and one writes
            mail/.seq back by hand and plants a .tmp name in an inbox
            for each of PLANTED_NAMES numbers from 1. The round 8 tests
            make a nest of folders under status/, chmod status/ to read
            without search and back, and plant links to a folder and a
            file outside TC_ROOT; they set this process's umask back to
            CHILD_UMASK between walks, and run cmd_init in process with
            os.lstat and os.fstat wrapped (as_member) and os.open wrapped
            to record each call (open_spy). The swap test builds a
            mailbox and two mirrors of it by hand in the root's temp
            folder, outside TC_ROOT, and runs cmd_init with os.open
            wrapped (swap_on_open) to rename one point aside and put a
            link or a mirror's folder in its place, reading
            /proc/self/fd to see where each open is aimed; the hard-link
            test chmods a status file and links it from outside TC_ROOT.
@deps       python3 stdlib (argparse, collections, contextlib, errno, fcntl, grp,
            importlib, io, json, os, pathlib, pwd, re, stat, subprocess,
            sys, time, unittest, unittest.mock); tests/_root.py. Imported
            by others (P3 fix round 1c, Claude Opus 5.5, unreviewed: the
            audit's LOW-28, option A): test_ssh_route.py UmaskTestCase,
            owner_patched_lstat and primary_group; test_gate.py
            UmaskTestCase, owner_patched_fstat and primary_group;
            test_wake_files.py UmaskTestCase, contents, load_tc,
            owner_patched_fstat, owner_patched_lstat, primary_group and
            tree; test_inbox_pinned.py UmaskTestCase, as_member, load_tc
            and primary_group; test_codex_route.py owner_patched_lstat and
            owner_patched_fstat.
@complexity O(1) per test: a handful of tc runs over a root of a few dozen
            entries, once per group tested (one or two); the round 8
            swap test O(p) over p points, kinds and moments of a swap
            (forty-two subtests, each one in-process init over a
            hand-built mailbox of thirteen entries).
@alloc      one TcRoot per test and group, removed when its context exits.
"""

import argparse
import collections
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
import pwd
import re
import stat
import subprocess
import sys
import time
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
SHARED_FOLDER_MODE = 0o2775
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
SHARED_FOLDER_NAMES = ("mail", "status", "cards", "outbox")
# P3 fix round 1c (Claude Opus 5.5, unreviewed): D36 (3). The folder init
# makes with the four, sticky like them, the init user's: where every
# member's gate files its origin ids (C3, C4).
ORIGINS_FOLDER = "mail/.origins"
# Row 1 of the exit table: refused with words.
EXIT_REFUSED = 1
# Row 2: a wait that timed out. A wait with --timeout 0 makes its lock and
# exits with it at once.
EXIT_TIMEOUT = 2
# A group name no machine has, for the refusal of a group that does not exist.
NO_SUCH_GROUP = "tc-test-no-such-group"
# SHARED D17 (Claude Opus 5.5, unreviewed): no planted links.
# mail/, status/, cards/ and outbox/ themselves: SHARED_FOLDER_MODE plus
# the sticky bit. Written out for the same reason as SHARED_FOLDER_MODE.
SHARED_TOP_FOLDER_MODE = 0o3775
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
# SHARED fix round 1 (Claude Opus 5.5, unreviewed): the audit's LOW-1. Why
# the supplementary run is skipped when the user has no such group.
NO_SUPPLEMENTARY_REASON = ("the running user has no named supplementary group, so the supplementary run "
                           "(where a folder left without its chown or setgid lands in the wrong group) "
                           "is skipped")
# SHARED D21 (Claude Opus 5.5, unreviewed): .shared's mode, written out for
# the same reason as SHARED_FOLDER_MODE. The user who ran init reads and
# writes it, everyone else only reads it: never group-writable.
SHARED_MARKER_MODE = 0o644
# What init says when another member's rerun may not rewrite .shared.
ONLY_INIT_USER_WORDS = "only the user who ran init ({owner}) can change the group"
# The words of every refusal init makes when it may not rewrite .shared.
INIT_USER_WORDS = "only the user who ran init"
# The whole refusal when another member's init asks for another group:
# made before init walks or changes anything.
MAY_NOT_CHANGE_WORDS = "tc init: may not change {marker}; the mailbox stays shared with group {group}; {only}. Nothing changed.\n"
# The whole refusal when another member's init meets a .shared it cannot
# read: made before init walks or changes anything.
UNREADABLE_TO_YOU_WORDS = "tc init: {marker} is owned by {owner} and unreadable to you; {only}. Nothing changed.\n"
# The one line a member's same-group rerun says about another user's
# writable .shared, which it leaves as it is.
TIGHTEN_WORDS = "tc init: {marker} is {mode:04o}; ask {owner} to rerun init to tighten it\n"
# The mode init gave .shared before D21: 0666 under its umask 002.
PRE_D21_MARKER_MODE = 0o664
# Why a test that needs a group other than the one .shared names is skipped.
NO_SECOND_GROUP_REASON = ("the running user has no named supplementary group, so no init can ask for a group "
                          "other than the one .shared names")
# SHARED fix round 2 (Claude Opus 5.5, unreviewed): D20's bound, no lost
# mail and no hang. Written out, not read from tc, for the same reason.
# How long tc waits for a lock another process holds before it refuses.
LOCK_WAIT_SECONDS = 3
# Python start-up and tc's imports on a busy machine, on top of the wait.
# A refused command that runs past the wait plus this is hung.
LOCK_REFUSE_MARGIN_SECONDS = 3
# What tc says when a lock is held past LOCK_WAIT_SECONDS; {what} says whose.
LOCK_HELD_WORDS = "another process is holding {what}'s lock"
# P3 fix round 1b (Claude Opus 5.5, unreviewed): D35 (3), the busy refusal
# names the holder, its user and pid, and on a private mailbox asks that
# user to let it go (a shared one also names the user who ran init); or,
# when /proc/locks names nobody by the time tc looks, says so.
HELD_BY_WORDS = ("tc: another process is holding {what}'s lock: {user} (pid {pid}); try again. If it stays held, "
                 "ask {user} to let it go.\n")
LET_GO_WORDS = ("tc: another process held {what}'s lock past {seconds} s, and /proc/locks names no holder now "
                "(it let go, or the process that took it has ended); try again\n")


def running_login():
    """The running user's login, as tc names a holder (user_name).

    @interacts  reads this process's user id and the user database.
    @deps       os, pwd.
    @complexity O(1).
    @alloc      one short string, returned.
    """
    return pwd.getpwuid(os.geteuid()).pw_name
# The number a member sets mail/.seq back to, so the next send's number
# names a message already there.
SET_BACK_SEQ = 5
# The mode init gives a ROOT it makes, and each missing folder above it:
# everyone may search it, only its owner may write it (D21).
ROOT_MODE = 0o755
# A login umask that leaves group write on, as many Linux systems give a
# user with a group of their own. Under it, a folder made without a umask
# of tc's own comes out 0775.
GROUP_WRITE_UMASK = 0o002
# A ROOT its group may write: init refuses it. SHARED fix round 3 (Claude
# Opus 5.5, unreviewed): with the sticky bit too (the audit's LOW-1: a
# member could make .shared or mail/ in it first). A folder above ROOT at
# the sticky mode is taken (only an entry's owner may rename it, as in
# /tmp); at the plain one it is refused (D23).
GROUP_WRITABLE_ROOT_MODE = 0o775
STICKY_WORLD_WRITABLE_MODE = 0o1777
# What init tells ROOT's owner to run before it shares a writable ROOT.
CHMOD_WORDS = "chmod g-w,o-w {root} first. Nothing changed."
# An inbox its owner may read but not search: the running user then sees
# what a member sees in an owner's 0740 inbox (group read, no search).
READ_NO_SEARCH_MODE = 0o640
# What tc health says for an inbox count it could not know.
UNKNOWN_WORDS = "unread unknown"
# What tc health's last line starts with when .shared turned unreadable.
GROUP_UNKNOWN_WORDS = "mailbox shared, group unknown: "
# SHARED fix round 3 (Claude Opus 5.5, unreviewed): D23 and the audit's
# MEDIUM-1 and LOW-2 (audits/2026-10-14-2358-quick). Written out, not read
# from tc, for the same reason as SHARED_FOLDER_MODE.
# Row 10 of the exit table, busy: a lock held past LOCK_WAIT_SECONDS.
EXIT_BUSY = 10
# SHARED fix round 4 (Claude Opus 5.5, unreviewed): the audit's MEDIUM-1
# (audits/2026-10-15-0102-quick). What tc read says before a file whose
# name read/ already holds: both files, neither called the forgery.
# {kept_owner} and {moved_owner} are OWNED_BY_WORDS under a shared
# mailbox, else empty.
TWIN_WORDS = ("tc read: two files had the name {name}, one in read/ and one in the inbox. tc never reuses a "
              "number, so one of them was not written by tc. Both are kept: {kept}{kept_owner}, unchanged, and "
              "{moved}{moved_owner}, from the inbox, shown below:")
OWNED_BY_WORDS = " (owned by {login})"
# Where tc read keeps that file: the first by-hand name read/ does not hold.
BY_HAND_NAME = "by-hand-{k}-{name}"
# SHARED fix round 4 (Claude Opus 5.5, unreviewed): the audit's HIGH-1.
# Before round 4 a planted name of 246 to 255 bytes could not take the
# by-hand prefix; 250 sits inside that range. The other case is read/'s
# own limit (os.pathconf PC_NAME_MAX), read at run time.
LONG_NAME_BYTES = 250
# A message name's suffix, which a cut by-hand name keeps whole.
MESSAGE_SUFFIX = ".md"
# SHARED fix round 5 (Claude Opus 5.5, unreviewed): the audit's LOW-2
# (audits/2026-10-15-0201-quick). A name of dots and then this tail
# ("." * 253 + "md" at a 255-byte limit) ends in .md, so tc takes it as
# a message, but os.path.splitext gives it no suffix at all.
DOTS_NAME_TAIL = "md"
# The text of a file planted straight into read/ under a message's name.
IN_READ_TEXT = "planted by hand in read/ under the same name\n"
# SHARED fix round 4 (Claude Opus 5.5, unreviewed): the audit's LOW-3
# (audits/2026-10-15-0102-quick). How long this test holds an inbox lock
# alone after a send began to wait for it. Under LOCK_WAIT_SECONDS, so the send still
# waits when the lock is let down to shared; over FLIP_SLACK_SECONDS, so a
# second bound of its own would show.
CARD_CHANGE_HOLD_SECONDS = 2
# Room past a send's one bound for it to print and exit.
FLIP_SLACK_SECONDS = 1
# /proc/locks columns for a blocked waiter:
# "1: -> FLOCK ADVISORY WRITE <pid> <maj>:<min>:<inode> 0 EOF". The access
# word is READ for LOCK_SH and WRITE for LOCK_EX.
WAITER_MARK = "->"
WAITER_MARK_COLUMN = 1
WAITER_KIND_COLUMN = 2
WAITER_ACCESS_COLUMN = 4
WAITER_PID_COLUMN = 5
WAITER_FILE_COLUMN = 6
# The audit's LOW-4: what tc log says for a folder lstat cannot reach.
LOG_CANNOT_LOOK_WORDS = "tc log: tc could not look at {path} ({why}); the mail in it is not shown"
# The audit's DEBT-3: what a send says when every number it tried was
# taken. Unchanged in round 4; only its exit code moved from 1 to 10.
# SHARED fix round 6 (Claude Opus 5.5, unreviewed): the audit's LOW-2
# (audits/2026-10-15-0300-quick). {last} is the last name a try found
# taken, as tc names it under the inbox; {why} blames mail/.seq only when
# a message's name was taken.
ALL_TAKEN_WORDS = ("tc send: {tries} message numbers in a row were taken in {box}, the last by {last} ({why}); "
                   "nothing sent. Each try moved mail/.seq on, so the next send starts past them.\n")
BEHIND_WHY = "mail/.seq was behind the names there: set back, or names planted ahead of it"
# SHARED fix round 7 (Claude Opus 5.5, unreviewed): the audit's LOW-1
# (audits/2026-10-15-0408-quick). When no try found a message's name
# taken: what tc found, and no word on whether mail/.seq was behind.
TMP_TAKEN_WHY = "each by a .tmp name already there, so no try got as far as the message's own name"
# SHARED fix round 5 (Claude Opus 5.5, unreviewed): the audit's DEBT-1
# (audits/2026-10-15-0201-quick). The text of a file a member plants in
# an inbox at the next message's .tmp name.
PLANTED_TMP_TEXT = "planted by hand at the next number's .tmp name\n"
# The texts of the file a member plants in an inbox under a read
# message's name, and of one planted straight into read/ at the first
# by-hand name.
PLANTED_TEXT = "planted by hand under a read message's name\n"
TAKEN_TEXT = "planted by hand at the first by-hand name\n"
# The board's message name (board/serve.py, MESSAGE_NAME), written out: a
# name it matches is read as a number and a sender. A by-hand name never is.
BOARD_MESSAGE_NAME = re.compile(r"^(\d+)-from-(.+)\.md$")
# What init says for a folder on the way from ROOT to / that would let a
# member swap ROOT (D23): one another user owns, and one its group may
# write without the sticky bit.
OWNED_ON_THE_WAY_WORDS = "tc init: {folder} belongs to {owner} (mode {mode:04o}), who is neither root nor you"
WRITABLE_ON_THE_WAY_WORDS = ("tc init: {folder}, on the way to {root}, is {mode:04o} and owned by {owner}: its "
                             "group or anyone may write it and it is not sticky")
# SHARED fix round 5 (Claude Opus 5.5, unreviewed): D28 and the audit's
# MEDIUM-1 (audits/2026-10-15-0201-quick). What init says when ROOT and
# its .shared belong to one other user: that user ran init, and no one
# is charged with anything.
RAN_INIT_WORDS = ("tc init: {root} and its .shared belong to {owner}, who ran init on this mailbox, so only "
                  "{owner} runs init on it.")
# SHARED fix round 6 (Claude Opus 5.5, unreviewed): D29 and the audit's
# HIGH-1 (audits/2026-10-15-0300-quick). What follows those words on the
# same line: tc fixes the member's own entries itself, and no line to
# paste follows.
FIXES_OWN_WORDS = " tc fixes the entries you own under it itself, and changes nothing else."
# One line per entry tc fixed through its descriptor, and per entry it
# skipped.
FIXED_WORDS = "tc init: fixed {path}: group {group}, mode {mode:04o}"
SKIPPED_WORDS = "tc init: skipped {path}: {why}"
# Why init skips a link, and an entry that turns out another user's.
SKIPPED_LINK_WHY = "a symlink, which tc never follows"
NOT_YOURS_WHY = "owned by {owner}, not by this user"
# The last line: no entry of this user's needed a fix, or the counts.
NO_FIX_WORDS = "tc init: no entry you own under it needs a fix. Nothing changed."
FIXED_COUNT_WORDS = "tc init: {fixed} fixed and {skipped} skipped, each named above. Nothing else changed."
# What follows the words, on the same line, when .shared no longer names
# the asked group by the time init walks: nothing is fixed.
NOTHING_CHANGED_WORDS = " Nothing changed."
# What tc tells the owner of an entry it may not fix: their own init
# fixes it through a no-follow open. Init's last refusal over skipped
# entries, and make_folder's refusal of a folder in the wrong group, end
# with it.
OWN_FIX_WORDS = "runs tc init --shared --group {group}, which fixes their own entries through a no-follow open"
SKIPPED_FIX_WORDS = "tc init: {n} skipped, each named above. The owner of each folder or file among them " + OWN_FIX_WORDS + "."
WRONG_GROUP_FIX_WORDS = "Nothing written. Its owner, {owner}, " + OWN_FIX_WORDS + "."
# A member's own message from before D20: owner and group read and write.
PRE_D20_FILE_MODE = 0o664
# The name of a member's own old message in another member's read/, and
# where that member puts it aside to swap a link in at its name.
OLD_OWN_MESSAGE = "000005-from-carol.md"
ASIDE_NAME = "000005-from-carol.aside"
# SHARED fix round 7 (Claude Opus 5.5, unreviewed): the audit's HIGH-1
# (audits/2026-10-15-0408-quick). Why init skips a folder it listed and
# then did not enter, because by then a link had its name.
NOT_ENTERED_WHY = ("a folder when tc first looked, but by the time tc came to enter it a link or another entry "
                   "had its name, or it was gone or would not open; tc looked at nothing under it")
# A second folder in b's inbox, beside read/, so the walk lists two folders
# there and enters one before the other.
SECOND_FOLDER = "kept"
# A file in each of the two, not right yet, whose fix makes the swap.
SWAP_TRIGGER = "000006-from-carol.md"
# What the swapped folder is renamed to: its name plus this.
FOLDER_ASIDE_SUFFIX = ".aside"
# Init's last line when nothing it skipped is a folder or a file.
SKIPPED_BY_HAND_WORDS = "tc init: {n} skipped, each named above; its owner fixes each by hand."
# SHARED fix round 8 (Claude Opus 5.5, unreviewed): the audit's MEDIUM-1,
# LOW-1 and LOW-2 (audits/2026-10-15-0840-quick), init's own stack walk.
# Written out, not read from tc, for the same reason as
# SHARED_FOLDER_MODE. How many folders deep the walk enters, counting the
# top as one, and why it names a folder past that.
WALK_MAX_DEPTH = 8
TOO_DEEP_WHY = (f"{WALK_MAX_DEPTH + 1} folders deep, counting its top as one, past the {WALK_MAX_DEPTH} the "
                f"walk enters; tc looked at nothing under it")
# Why the walk names a folder this user may list but not search.
NO_SEARCH_WHY = "this user may list it but not search (x) it; tc looked at nothing under it"
# The name of every folder in a nest a member makes under status/.
NEST_FOLDER = "d"
# SHARED fix round 8 (Claude Opus 5.5, unreviewed): the audit's HIGH-1 and
# LOW-3 (audits/2026-10-15-0840-quick), ROOT pinned by identity. Written
# out, not read from tc. What init says when ROOT, as it opens it after
# its walk, is not the folder the walk judged.
ROOT_CHANGED_WORDS = ("{root} changed after init's walk looked at it: another folder or a link has its name now. "
                      "Nothing changed.")
# Why init skips an entry that is not, at its open, the one the walk's
# lstat found, and a regular file with another name.
CHANGED_WHY = "another entry had its name by the time tc came to change it; tc changed nothing there"
HARD_LINK_WHY = ("a file with another name too (a hard link), which tc never changes: the change would show at "
                 "every name")
# A file mode init never leaves: owner read and write only.
OWNER_FILE_MODE = 0o600
# P3 fix round 1b (Claude Opus 5.5, unreviewed): D35 (1). The wait and
# watch locks' names in their owner's own inbox, and their mode, the
# owner's alone, written here rather than read from tc.
WAKE_LOCK_NAMES = (".wait.lock", ".watch.lock")
WAKE_LOCK_MODE = 0o600
# The swap test's layout under the root's temp folder: ROOT's parent and
# ROOT, and the two mirrors of them, one a link's target and one a real
# folder put in place.
SWAP_PARENT, SWAP_ROOT = "home", "mailbox"
OUTSIDE_TREE, OTHER_TREE = "outside", "other"
# The mailbox the swap test builds by hand, three times: each entry under
# the four, a folder (None) or a file (its text), each at a mode init
# never leaves (OWNER_FOLDER_MODE, OWNER_FILE_MODE), so a walk that
# reached any of them would change it.
SWAP_LAYOUT = (("mail", None), ("mail/.seq", "5\n"), ("mail/to-b", None),
               ("mail/to-b/000006-from-a.md", "a message to b\n"), ("mail/to-b/read", None),
               (f"mail/to-b/read/{OLD_OWN_MESSAGE}", "an old message from the member to b\n"),
               ("status", None), ("status/b.md", "busy\n"), ("cards", None), ("cards/b.json", "{}\n"),
               ("outbox", None), ("outbox/to-c", None), ("outbox/to-c/000007-from-a.md", "a queued message\n"))
# When the swap test swaps a point: as init opens ROOT after its walk, or
# while mail/'s walk runs.
AT_ROOT_OPEN, MID_WALK = "as init opens ROOT", "while mail/'s walk runs"
# SHARED fix round 5 (Claude Opus 5.5, unreviewed): the audit's LOW-1. What
# tc read says for an inbox file still there after its rename: a hard link
# made at the target first turns rename(2) into nothing.
STILL_THERE_WORDS = ("tc read: {path} not moved to read/ (it is still in the inbox after the move to {target}: a "
                     "hard link to it, made there just before, makes a move do nothing); left unread")
# What a send says on a filesystem without hard links (the audit's LOW-3).
NO_HARD_LINKS_WORDS = ("tc send: the filesystem under {root} has no hard links ({why}), and tc needs them to "
                       "publish a message without ever replacing another (D20); nothing sent.")
# What tc says for an inbox's read/ it cannot look at (an inbox its owner
# left without search).
CANNOT_LOOK_WORDS = "tc: could not look at {path} ({why}); nothing was read or written there."
# An inbox its owner may search but not list: what a user sees in a
# folder that gives search and no read (the audit's REC-1).
SEARCH_NO_READ_MODE = 0o100
# What tc says for a folder it could not list.
CANNOT_LIST_WORDS = "tc could not list {path} ({why})"
# What peek, read, wait and log say when they see no mail. None of them
# may say it for an inbox tc could not list.
SILENT_WORDS = ("0 unread", "no unread mail", "TIMEOUT", "mailbox empty")
# tc's PUBLISH_MAX_TRIES, written out: a send never tries more numbers, so
# a member who plants this many names past the counter covers every try.
PLANTED_NAMES = 100
# Just under LOCK_WAIT_SECONDS: how long the member holds mail/.seq on each
# turn, so a send that gave every number a wait of its own would get each
# number in time and wait again, past the bound, for as long as the names
# hold out.
HOLD_UNDER_BOUND_SECONDS = 2.5
# The member's loop, run as its own process (argv: mail/.seq, read/, the
# sender, the hold, the count). Under mail/.seq's flock it plants `count`
# names in read/ past the counter, one per number a send could take. Then,
# turn by turn: hold the lock, let go, wait (at most one hold) until the
# counter changes, which means a send took a number, and take the lock at
# once, so the send's next number waits on it again. The test kills it.
SEQ_HOLDER = """
import fcntl, os, sys, time
seq, read, sender, hold, count = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]), int(sys.argv[5])

def number():
    with open(seq) as f:
        return f.read()

with open(seq, "a+") as held:
    fcntl.flock(held, fcntl.LOCK_EX)
    held.seek(0)
    n = int(held.read().strip() or 0)
    for k in range(n + 1, n + count + 1):
        open(os.path.join(read, f"{k:06d}-from-{sender}.md"), "a").close()
    for turn in range(count):
        time.sleep(hold)
        was = number()
        fcntl.flock(held, fcntl.LOCK_UN)
        give_up = time.monotonic() + hold
        while number() == was and time.monotonic() < give_up:
            pass
        fcntl.flock(held, fcntl.LOCK_EX)
"""


def user_groups():
    """The running user's groups to share with: [("primary", name, gid)], plus ("supplementary", ...) when the user has one.

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


# SHARED fix round 1 (Claude Opus 5.5, unreviewed): the audit's LOW-1.
def groups_to_test(case):
    """user_groups() for a test that loops over them; with no supplementary group, a skipped subtest on `case` that says why.

    The supplementary run is the one that catches a folder left without
    its chown or setgid, so its absence is a skip with a reason in the
    test's output, never a silent pass.

    @interacts  reads this process's groups and the group database; may
                record one skipped subtest on `case`.
    @deps       user_groups; NO_SUPPLEMENTARY_REASON.
    @complexity O(s) over s supplementary groups (a handful).
    @alloc      one short list, returned.
    """
    found = user_groups()
    if len(found) == 1:
        with case.subTest(group="supplementary"):
            case.skipTest(NO_SUPPLEMENTARY_REASON)
    return found


def primary_group():
    """("primary", name, gid): the running user's effective group, for a test that needs one group only.

    @interacts  reads this process's groups and the group database.
    @deps       user_groups.
    @complexity O(s) over s supplementary groups (a handful).
    @alloc      one tuple, returned.
    """
    return user_groups()[0]


class UmaskTestCase(unittest.TestCase):
    """A TestCase whose every test runs with this process's umask at CHILD_UMASK, put back after (the audit's LOW-10).

    Every class in this file inherits it, so the module block's umask
    claim holds for every test.

    @interacts  sets this process's umask (and so every child's).
    @deps       os; CHILD_UMASK.
    @complexity O(1) per test.
    @alloc      none.
    """

    def setUp(self):
        """Set this process's umask to CHILD_UMASK; the cleanup puts the old one back.

        @interacts  sets the umask of this process (and so of every child).
        @deps       os.
        @complexity O(1).
        @alloc      none.
        """
        self.addCleanup(os.umask, os.umask(CHILD_UMASK))


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


def tree(path, under=SHARED_FOLDER_NAMES):
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

    A file directly in mail/ (mail/.seq, an inbox lock, the ring marker):
    SHARED_WRITABLE_FILE_MODE; a wait or watch lock in an inbox:
    WAKE_LOCK_MODE (D35, P3 fix round 1b, Claude Opus 5.5, unreviewed);
    any other file (a message, a card, a status): SHARED_OWNED_FILE_MODE
    (D20). A folder: SHARED_TOP_FOLDER_MODE
    (sticky, D17) when it is one of SHARED_FOLDER_NAMES itself, or
    mail/.origins/, which init makes too (P3 fix round 1c, Claude Opus
    5.5, unreviewed: D36 (3)), SHARED_INBOX_MODE for mail/to-<name> and
    its read/ (D20), else SHARED_FOLDER_MODE.

    @interacts  none.
    @deps       SHARED_FOLDER_NAMES, ORIGINS_FOLDER, SHARED_TOP_FOLDER_MODE,
                SHARED_INBOX_MODE, SHARED_FOLDER_MODE,
                SHARED_WRITABLE_FILE_MODE, SHARED_OWNED_FILE_MODE,
                WAKE_LOCK_NAMES, WAKE_LOCK_MODE.
    @complexity O(1).
    @alloc      the split path and one tuple, returned.
    """
    parts = path.split("/")
    if kind != "folder":
        if len(parts) == 3 and parts[0] == "mail" and parts[1].startswith("to-") and parts[2] in WAKE_LOCK_NAMES:
            return (kind, WAKE_LOCK_MODE, gid)  # P3 fix round 1b (Claude Opus 5.5, unreviewed): D35 (1)
        writable = len(parts) == 2 and parts[0] == "mail"
        return (kind, SHARED_WRITABLE_FILE_MODE if writable else SHARED_OWNED_FILE_MODE, gid)
    if path in SHARED_FOLDER_NAMES or path == ORIGINS_FOLDER:
        return (kind, SHARED_TOP_FOLDER_MODE, gid)
    inbox = parts[0] == "mail" and len(parts) in (2, 3) and parts[1].startswith("to-") and parts[2:] in ([], ["read"])
    return (kind, SHARED_INBOX_MODE if inbox else SHARED_FOLDER_MODE, gid)


class SharedTest(UmaskTestCase):
    """`tc init --shared`, the umask, D16's later folders, and the health line.

    @interacts  see the module block.
    @deps       _root.TcRoot, UmaskTestCase.
    @complexity O(1) per test.
    @alloc      one TcRoot per test and group.
    """

    def test_init_shares_every_folder_and_file_already_there(self):
        """After init, every entry has group g and its mode (shared_as: the four and mail/.origins/, which init makes, 3775, inboxes 3770, mail/ files 0664, the rest 0640); so has a message sent after.

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
        for label, name, gid in groups_to_test(self):
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
                                                 ORIGINS_FOLDER, "mail/.seq", "mail/to-b",
                                                 "mail/to-b/000001-from-a.md", "mail/to-b/read", "outbox",
                                                 "status", "status/b.md"])
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
        label, name, gid = groups_to_test(self)[-1]
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
        other user has to make one in a ROOT the first user owns (and
        mail/.origins/, 3775 too: P3 fix round 1c, Claude Opus 5.5,
        unreviewed, D36 (3)). The
        inbox and its read/ then come from the first join (D20), the
        message from the first send, the status file from the first
        status, and the wait lock and its exit record from a wait that
        times out at once (P3 fix round 1b, Claude Opus 5.5, unreviewed:
        b's own wait, before the send, since D36 (2) refuses a wait on a
        name nobody joined, and its lock is in b's inbox at
        WAKE_LOCK_MODE, D35 (1); F1, Claude Opus 5.5, unreviewed: the
        record, mail/to-b/.wait.exit, is 0640 like any inbox file that is
        not a lock, C5).
        Must reject an init that makes no top folder (the second user's
        first command would need write access to ROOT), a later folder
        without setgid (0775), or a top folder left in the primary group
        (the supplementary run), and any file at 0644.

        @interacts  per group: init, a join, a wait, a send, a status.
        @deps       _root.TcRoot.tc, groups_to_test, tree, shared_as.
        @complexity O(1) per group.
        @alloc      one TcRoot per group.
        """
        for label, name, gid in groups_to_test(self):
            with self.subTest(group=label), _root.TcRoot() as root:
                code, out, err = root.tc("init", "--shared", "--group", name)
                self.assertEqual(code, 0, f"tc init exited {code}: {err}")
                self.assertEqual(tree(root.path), {top: ("folder", SHARED_TOP_FOLDER_MODE, gid)
                                                   for top in (*SHARED_FOLDER_NAMES, ORIGINS_FOLDER)},
                                 "init did not make the four top folders (D19) and mail/.origins/ (D36 (3))")
                joined = root.tc("join", "b", env={"CLAUDECODE": "1"})
                waited = root.tc("wait", "b", "--timeout", "0")
                runs = [joined, root.tc("send", "--from", "a", "--to", "b", "hi"),
                        root.tc("status", "b", "busy")]
                made = tree(root.path)
                for run in runs:
                    self.assertEqual(run[0], 0, run[2])
                self.assertEqual(waited[0], EXIT_TIMEOUT, waited[2])
                self.assertEqual(sorted(made), ["cards", "cards/b.json", "mail", "mail/.box-b.lock",
                                                ORIGINS_FOLDER, "mail/.seq", "mail/to-b",
                                                "mail/to-b/.wait.exit",  # F1 (Claude Opus 5.5, unreviewed): C5's record
                                                "mail/to-b/.wait.lock",
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


def load_tc(root, path=None):
    """Load ../tc as a module with TC_ROOT set to the harness root (or `path`, a folder inside the root's temp folder), without running main().

    tc reads TC_ROOT once, at import, so it is set before the load and the
    old value is put back after (CLAUDE.md, Key patterns). SHARED fix
    round 2 (Claude Opus 5.5, unreviewed): `path` lets a test point tc at
    a ROOT that does not exist yet; the caller keeps it under root.base,
    so the root's own cleanup removes whatever tc makes there.

    @interacts  sets and restores os.environ["TC_ROOT"]; runs tc's top
                level (constants only, no disk writes).
    @deps       importlib, os; _root.TC.
    @complexity O(1).
    @alloc      one module object, returned.
    """
    old = os.environ.get("TC_ROOT")
    os.environ["TC_ROOT"] = str(path if path is not None else root.path)
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


class NoPlantedLinksTest(UmaskTestCase):
    """D17: the sticky folders, planted file links, planted inbox links, and reopening without O_CREAT.

    The link checks hold whether or not the mailbox is shared, so only the
    sticky test runs init.

    @interacts  see the module block.
    @deps       _root.TcRoot, UmaskTestCase, plant, landed, load_tc.
    @complexity O(1) per test.
    @alloc      one TcRoot per case.
    """

    def test_the_shared_folders_carry_the_sticky_bit(self):
        """After init, mail/, outbox/ (made by hand, as the ssh route will), the later cards/ and status/, and mail/.origins/ (init's own, D36 (3)) are 3775; inboxes and read/ are 3770 (D20); outbox/sent/ is 2775.

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
        for label, name, gid in groups_to_test(self):
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
                    "mail": (SHARED_TOP_FOLDER_MODE, gid), "outbox": (SHARED_TOP_FOLDER_MODE, gid),
                    "cards": (SHARED_TOP_FOLDER_MODE, gid), "status": (SHARED_TOP_FOLDER_MODE, gid),
                    ORIGINS_FOLDER: (SHARED_TOP_FOLDER_MODE, gid),
                    "mail/to-b": (SHARED_INBOX_MODE, gid), "mail/to-b/read": (SHARED_INBOX_MODE, gid),
                    "mail/to-c": (SHARED_INBOX_MODE, gid), "mail/to-c/read": (SHARED_INBOX_MODE, gid),
                    "outbox/sent": (SHARED_FOLDER_MODE, gid)})

    def test_a_link_at_a_file_tc_opens_by_name_is_refused_and_its_target_unchanged(self):
        """A symlink at an inbox lock, mail/.seq or status/x.md: exit 1, the words, the target as it was, no mail.

        One fresh root per case. The mail/.seq case also runs with a
        dangling link, whose target must still not exist after. Showing
        every status with a link among them prints the rest, names the
        link and never prints its target. Must reject an open that follows
        the link (the target would be truncated or written, or made).
        P3 fix round 1b (Claude Opus 5.5, unreviewed): the wait and watch
        locks live in their owner's inbox since D35 (1), where a link at
        a lock's name is moved aside, never followed (tests/test_wake_files.py,
        WakeLockPlaceTest), so their two cases left this test.

        @interacts  per case: makes folders, a message file and a link by
                    hand, then one tc run.
        @deps       _root.TcRoot.tc, plant, landed.
        @complexity O(1) per case, five cases.
        @alloc      one TcRoot per case.
        """
        send = ["send", "--from", "a", "--to", "x", "hi"]
        cases = [
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
class RegularFilesOnlyTest(UmaskTestCase):
    """D19: messages only from regular files, a FIFO at a lock's name refused, and no listener, count or status age taken through a link.

    None of this needs a shared mailbox: the checks hold either way. The
    status age test is from BOARD's review (SHARED, Claude Opus 5.5,
    unreviewed).

    @interacts  see the module block.
    @deps       _root.TcRoot, UmaskTestCase, plant, landed, load_tc.
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
                    process for show(), handed the link by its name in the
                    inbox's open descriptor, with stdout captured.
        @deps       _root.TcRoot.tc, plant, load_tc; contextlib, io, os;
                    tc.show.
        @complexity O(1).
        @alloc      one TcRoot and one module; one descriptor while show()
                    runs.
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
            box_fd = os.open(box, os.O_RDONLY | os.O_DIRECTORY)  # P3 fix round 1a (Claude Opus 5.5, unreviewed): show() reads by name in an open folder (D35)
            try:
                with contextlib.redirect_stdout(io.StringIO()) as printed:
                    unshown = tc.show([(box / "000099-from-z.md", box_fd)])
            finally:
                os.close(box_fd)
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
        """A FIFO at the inbox lock, mail/.seq, status/x.md or a codex name's ring marker: exit 1 within FIFO_REFUSE_SECONDS, the words, the FIFO left, no mail.

        One fresh root per case; the ring marker case joins x as codex
        first. Must reject an open without O_NONBLOCK (the inbox lock and
        status opens block forever), one without the
        S_ISREG check (mail/.seq opens, then the send fails with a
        traceback, not words), and a marker check that lets a FIFO
        through (the send lands, then tries to write the FIFO). P3 fix
        round 1b (Claude Opus 5.5, unreviewed): a FIFO at a wait or watch
        lock's name, in its owner's inbox since D35 (1), is moved aside
        without blocking (tests/test_wake_files.py, WakeLockPlaceTest), so
        those two cases left this test.

        @interacts  per case: one FIFO made by hand (after a codex join for
                    the marker), then one tc run.
        @deps       _root.TcRoot.tc, landed.
        @complexity O(1) per case, four cases.
        @alloc      one TcRoot per case.
        """
        send = ["send", "--from", "a", "--to", "x", "hi"]
        cases = [
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
        """In process: mail/to-b/.wait.lock a link to a's lock, which this process holds: listeners() names a with this pid, and never b.

        Must reject a lock key read through the link (b would show a's
        holder, while b's own tc wait is refused). P3 fix round 1b
        (Claude Opus 5.5, unreviewed): D35 (1), the locks in their owners'
        inboxes; and on this private mailbox the switch-over's old place
        too, mail/.wait-c.lock a link to a's lock, which is never followed
        either.

        @interacts  loads tc in process; makes mail/, two inboxes, one lock
                    file and two links by hand; holds an flock on the lock
                    while listeners() reads /proc/locks.
        @deps       load_tc; fcntl; tc.listeners.
        @complexity O(1).
        @alloc      one TcRoot, one module and one open file.
        """
        with _root.TcRoot() as root:
            tc = load_tc(root)
            mail = root.path / "mail"
            for name in ("a", "b"):
                (mail / f"to-{name}").mkdir(parents=True)
            lock = mail / "to-a" / ".wait.lock"
            lock.write_text("")
            (mail / "to-b" / ".wait.lock").symlink_to(lock)
            (mail / ".wait-c.lock").symlink_to(lock)
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

    # SHARED, from BOARD's review (Claude Opus 5.5, unreviewed): a status file's age through lstat.
    def test_a_status_link_into_an_unreadable_folder_leaves_health_answering(self):
        """status/b.md a link into a folder nobody may search, status/a.md a real file: tc health --json exits 0, a's status age is a number, b's is null.

        Must reject a summary that follows the link (Path.exists() raises
        PermissionError there, and tc health dies with a traceback on
        every run), and one that drops real status ages.

        @interacts  two sends and one status; a folder, a file in it and a
                    link to that file made by hand, the folder chmodded to
                    no access and back; one tc health --json.
        @deps       _root.TcRoot.tc; json; TARGET_TEXT, NO_ACCESS_MODE,
                    OWNER_FOLDER_MODE.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            for name in ("a", "b"):
                root.tc("send", "--from", "x", "--to", name, REAL_TEXT)
            root.tc("status", "a", "busy")
            hidden = root.base / "hidden"
            hidden.mkdir()
            (hidden / "b.md").write_text(TARGET_TEXT)
            (root.path / "status" / "b.md").symlink_to(hidden / "b.md")
            hidden.chmod(NO_ACCESS_MODE)
            try:
                code, out, err = root.tc("health", "--json")
            finally:
                hidden.chmod(OWNER_FOLDER_MODE)
        self.assertEqual(code, 0, err)
        mail = json.loads(out)["mail"]
        self.assertIsNotNone(mail["a"]["status_age_s"], "a real status file lost its age")
        self.assertIsNone(mail["b"]["status_age_s"], "tc health dated a status file through a link")


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


def owner_patched_lstat(*paths_to_patch):
    """An os.lstat that reports each of `paths_to_patch` as owned by another user (its uid plus one), and every other path as it is.

    One Linux user cannot make a file another user owns, so the D20
    owner check is shown by what tc's lstat reports (phases.md H1: "a card
    file whose recorded owner is patched"). SHARED fix round 6 (Claude
    Opus 5.5, unreviewed): several paths, so a test can make ROOT and its
    .shared the init user's and leave the running user the member.
    SHARED fix round 7 (Claude Opus 5.5, unreviewed): init's walk lstats
    each entry by its name in its folder's descriptor (dir_fd), never by
    its path, so such a call is matched by what it finds: the same file
    (os.path.samestat) as one of `paths_to_patch`.

    @interacts  none until called; then lstats the path it is given, and
                for a dir_fd call each of `paths_to_patch` too.
    @deps       os, stat, pathlib.
    @complexity O(p) per call over p paths to patch (a handful).
    @alloc      one stat result per call.
    """
    real = os.lstat

    def same_file(st, path):
        try:
            return os.path.samestat(st, real(path))
        except FileNotFoundError:
            return False

    def lstat(path, *args, **kwargs):
        st = real(path, *args, **kwargs)
        if kwargs.get("dir_fd") is not None:
            hit = any(same_file(st, patched) for patched in paths_to_patch)
        else:
            hit = pathlib.Path(path) in paths_to_patch
        if hit:
            fields = list(st[:stat.ST_CTIME + 1])
            fields[stat.ST_UID] = st.st_uid + 1
            return os.stat_result(fields)
        return st
    return lstat


# SHARED fix round 8 (Claude Opus 5.5, unreviewed): the audit's HIGH-1 (audits/2026-10-15-0840-quick).
def owner_patched_fstat(*paths_to_patch):
    """An os.fstat that reports a descriptor open on one of `paths_to_patch` (the same file, by st_dev and st_ino, as each was when this was made) as owned by another user (its uid plus one), and every other descriptor as it is.

    owner_patched_lstat's pair for a check made on an open descriptor:
    init opens ROOT once after its walk and, on a member's rerun, keeps
    it only when fstat finds the init user's folder (tc's pin_root). The
    files are fixed when this is made, so ROOT renamed or swapped later
    is still matched by the folder it was.

    @interacts  lstats each of `paths_to_patch` once, when made; then
                fstats the descriptor it is given.
    @deps       os, stat.
    @complexity O(1) per call.
    @alloc      the set of files to patch; one stat result per call.
    """
    real = os.fstat
    patched = {(st.st_dev, st.st_ino) for st in (os.lstat(path) for path in paths_to_patch)}

    def fstat(fd):
        st = real(fd)
        if (st.st_dev, st.st_ino) in patched:
            fields = list(st[:stat.ST_CTIME + 1])
            fields[stat.ST_UID] = st.st_uid + 1
            return os.stat_result(fields)
        return st
    return fstat


class NobodyTouchesAnotherMembersMailTest(UmaskTestCase):
    """D20: inboxes owned by their recipient at 3770, 0640 files, sends refused to names nobody joined, inbox and card owners matched, the marker rewritten in place.

    One Linux user cannot prove another user's refusals (the kernel's
    sticky and mode checks): these tests prove the modes, the owners and
    the checks tc makes. The two-user walk-through is
    qa/human/route-shared.md.

    @interacts  see the module block.
    @deps       _root.TcRoot, UmaskTestCase, groups_to_test, primary_group,
                tree, load_tc, marker_seen, owner_patched_lstat.
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
        for label, name, gid in groups_to_test(self):
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
        @deps       _root.TcRoot.tc, primary_group, tree.
        @complexity O(1).
        @alloc      two TcRoots.
        """
        label, name, gid = primary_group()
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
        @deps       _root.TcRoot.tc, primary_group.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        label, name, gid = primary_group()
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
        @deps       _root.TcRoot.tc, primary_group, load_tc,
                    owner_patched_lstat; contextlib, io, unittest.mock;
                    tc.deliver_local, tc.unread.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        label, name, gid = primary_group()
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
        @deps       _root.TcRoot.tc, primary_group, load_tc,
                    owner_patched_lstat; contextlib, io, unittest.mock;
                    tc.claim_inbox.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        label, name, gid = primary_group()
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
        @deps       _root.TcRoot.tc, _root.TcRoot.fake_bin, primary_group,
                    marker_seen.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        label, name, gid = primary_group()
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
        @deps       _root.TcRoot.tc, primary_group.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        if os.geteuid() == 0:
            self.skipTest("root may write a read-only file")
        label, name, gid = primary_group()
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

        A second read, with only that one left, never says `no unread
        mail`. Must reject a traceback on the refused rename (a member
        running tc read on another member's inbox), and words that call
        the stuck message gone.

        @interacts  three sends; loads tc in process and runs cmd_read twice
                    with os.rename wrapped and stdout and stderr captured.
        @deps       _root.TcRoot.tc, load_tc; argparse, contextlib, errno,
                    io, unittest.mock; tc.cmd_read.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        with _root.TcRoot() as root:
            for sender in ("a", "c", "d"):
                root.tc("send", "--from", sender, "--to", "b", f"from {sender}")
            tc = load_tc(root)
            real = os.rename

            # P3 fix round 1a (Claude Opus 5.5, unreviewed): tc read moves by name between open folders (os.rename, D35).
            def rename(src, dst, *args, **kwargs):
                if os.path.basename(src) == "000002-from-c.md":
                    raise PermissionError(errno.EPERM, os.strerror(errno.EPERM), str(src))
                return real(src, dst, *args, **kwargs)
            out, err, again = io.StringIO(), io.StringIO(), io.StringIO()
            with mock.patch.object(os, "rename", rename), contextlib.redirect_stdout(out), \
                    contextlib.redirect_stderr(err):
                with self.assertRaises(SystemExit) as stop:
                    tc.cmd_read(argparse.Namespace(name="b"))
            with mock.patch.object(os, "rename", rename), contextlib.redirect_stdout(again), \
                    contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
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
        self.assertNotIn("no unread mail", again.getvalue(),
                         "a read that could move nothing said there is no unread mail")


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


class InitAndRefusalsTest(UmaskTestCase):
    """make_folder never leaves a folder in the wrong group; init reruns cleanly, walks what it cannot change and says the real state; the refusals' words; health never raises.

    In-process init sets this process's umask; UmaskTestCase puts it back.
    SHARED fix round 6 (Claude Opus 5.5, unreviewed): D29. The refusals
    for a folder in the wrong group and for entries init skipped say the
    owner runs tc init --shared --group <g>; here that init, run as
    told, puts the entry right. Round 5's lines to paste are gone. And
    the audit's LOW-1: a relative TC_ROOT still prints absolute paths.

    @interacts  see the module block.
    @deps       _root.TcRoot, UmaskTestCase, primary_group, user_groups,
                load_tc, run_init, plant; subprocess, sys.
    @complexity O(1) per test.
    @alloc      one TcRoot per test.
    """

    def test_make_folder_removes_a_folder_it_cannot_share_and_refuses(self):
        """In process, with fchown refused: make_folder(outbox/sent) exits 1 with words and leaves no outbox/sent.

        Must reject a make_folder that leaves the folder (the next run
        would accept it in the maker's group, MEDIUM-4).

        @interacts  init; loads tc in process and runs make_folder with
                    os.fchown replaced and stderr captured.
        @deps       _root.TcRoot.tc, primary_group, load_tc; contextlib,
                    errno, io, unittest.mock; tc.make_folder.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        label, name, gid = primary_group()

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
        """Shared with a supplementary group, status/ moved by hand to the primary group: tc status x busy exits 1 with words and writes nothing; they end telling its owner to run tc init --shared --group <g>, and that init, run as told, puts status/ right, and the post then lands.

        Must reject a make_folder that accepts any folder that is there
        (other members could not write in it). SHARED fix round 6 (Claude
        Opus 5.5, unreviewed): D29. Must reject round 5's chgrp and chmod
        lines (a pasted line follows a link) and a remedy that does not
        fix it. Here the owner is the init user, whose init passes the
        walk; a member's is refused and fixes the member's own entries
        (RootAndClaimTest). Needs a supplementary group; skipped with a
        reason without one.

        @interacts  init; one chown by hand; two status posts and the
                    owner's init between them; lstats status/.
        @deps       _root.TcRoot.tc, user_groups; pwd; WRONG_GROUP_WORDS,
                    WRONG_GROUP_FIX_WORDS, SHARED_TOP_FOLDER_MODE.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        found = user_groups()
        if len(found) < 2:
            self.skipTest("the running user has no named supplementary group, so no folder can be "
                          "put in a group other than the one shared")
        (_, primary, primary_gid), (_, name, gid) = found[0], found[1]
        owner = pwd.getpwuid(os.getuid()).pw_name
        with _root.TcRoot() as root:
            root.tc("init", "--shared", "--group", name)
            status = root.path / "status"
            os.chown(status, -1, primary_gid)
            code, out, err = root.tc("status", "x", "busy")
            wrote = os.path.lexists(status / "x.md")
            told = root.tc("init", "--shared", "--group", name)
            st = os.lstat(status)
            again = root.tc("status", "x", "busy")
        self.assertEqual(code, EXIT_REFUSED, err)
        self.assertIn(WRONG_GROUP_WORDS.format(have=primary, want=name), err)
        self.assertTrue(err.endswith(f" {WRONG_GROUP_FIX_WORDS.format(owner=owner, group=name)}\n"), err)
        self.assertNotIn("chgrp", err, "a line to paste")
        self.assertFalse(wrote, "a status landed in a folder in the wrong group")
        self.assertEqual(told[0], 0, told[2])
        self.assertEqual((stat.S_IMODE(st.st_mode), st.st_gid), (SHARED_TOP_FOLDER_MODE, gid))
        self.assertEqual(again[0], 0, again[2])

    def test_a_rerun_of_init_changes_nothing_already_right(self):
        """In process: init, then init again over the same root: the second run calls fchown and fchmod on nothing and exits 0.

        Linux lets only an entry's owner change its group, so on a live
        shared mailbox every entry another member owns would be an EPERM
        skip. Must reject a share_entry that changes entries already in g
        at their mode (LOW-2).

        @interacts  a join, a send, a status; loads tc in process and runs
                    cmd_init twice, the second time with os.fchown and
                    os.fchmod wrapped to count calls.
        @deps       _root.TcRoot.tc, primary_group, load_tc, run_init;
                    unittest.mock.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        label, name, gid = primary_group()
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
        """In process, with share_entry refusing mail/ itself: init still gives the message under it 0640, names mail/, exits 1, and ends telling the owner of each folder or file skipped to run tc init --shared --group <g>; that init, run as told, puts mail/ right.

        Must reject a walk that skips everything under a top folder it
        could not change, uncounted and unnamed (LOW-3). SHARED fix round
        6 (Claude Opus 5.5, unreviewed): D29. Must reject round 5's chgrp
        and chmod lines (a pasted line follows a link) and a remedy that
        does not fix it.

        @interacts  a send; loads tc in process and runs cmd_init with
                    share_entry wrapped to refuse mail/, then once more as
                    it is; lstats mail/.
        @deps       _root.TcRoot.tc, primary_group, load_tc, run_init;
                    unittest.mock; tc.share_entry; SKIPPED_FIX_WORDS,
                    SHARED_TOP_FOLDER_MODE.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        label, name, gid = primary_group()
        with _root.TcRoot() as root:
            root.tc("send", "--from", "a", "--to", "b", "hi")
            tc = load_tc(root)
            real = tc.share_entry
            mail = root.path / "mail"
            before = stat.S_IMODE(os.lstat(mail).st_mode)  # made by a private send: not right yet

            def share_entry(entry, where, gid, owner=None):  # SHARED fix round 7 (Claude Opus 5.5, unreviewed): reached by descriptor
                if where == mail:
                    return "folder", "Operation not permitted", False
                return real(entry, where, gid, owner)
            with mock.patch.object(tc, "share_entry", share_entry):
                code, out, err = run_init(tc, name)
            message = os.lstat(mail / "to-b" / "000001-from-a.md")
            left = os.lstat(mail)
            told = run_init(tc, name)
            st = os.lstat(mail)
        self.assertEqual(code, EXIT_REFUSED, err)
        self.assertIn(f"skipped {mail}: Operation not permitted", err)
        self.assertEqual((stat.S_IMODE(message.st_mode), message.st_gid), (SHARED_OWNED_FILE_MODE, gid),
                         "init did not reach a message under the top folder it could not change")
        self.assertTrue(err.endswith(f"\n{SKIPPED_FIX_WORDS.format(n=1, group=name)}\n"), err)
        self.assertNotIn("chgrp", err, "a line to paste")
        self.assertNotEqual(before, SHARED_TOP_FOLDER_MODE, "mail/ was right before init: nothing to fix")
        self.assertEqual(stat.S_IMODE(left.st_mode), before, "the refused change went through")
        self.assertEqual(told[0], 0, told[2])
        self.assertEqual((stat.S_IMODE(st.st_mode), st.st_gid), (SHARED_TOP_FOLDER_MODE, gid))

    def test_when_init_cannot_write_shared_its_words_match_the_state_and_come_after_the_skips(self):
        """ROOT made read-only: init over a shared root exits 0 (.shared already right); over a private one it says `stays private`, after the skip line; over one shared with another group it says so.

        Must reject a rewrite of a .shared that already names the group,
        words that call a shared mailbox private, and a refusal that
        drops the skip lines (LOW-4). Skipped as root, who may write a
        read-only folder.

        @interacts  three roots: sends and statuses, init, a FIFO made by
                    hand, a hand-written .shared; ROOT chmodded read-only
                    and back.
        @deps       _root.TcRoot.tc, primary_group.
        @complexity O(1).
        @alloc      three TcRoots.
        """
        if os.geteuid() == 0:
            self.skipTest("root may write a read-only folder")
        label, name, gid = primary_group()
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
                unreachable = root.tc("init", "--shared", "--group", primary_group()[1])
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

    # SHARED fix round 6 (Claude Opus 5.5, unreviewed): the audit's LOW-1 (audits/2026-10-15-0300-quick).
    def test_a_relative_tc_root_still_names_every_path_absolute(self):
        """TC_ROOT given relative (the root's own name, from the root's temp folder): a send says where it landed, and a status post refused over a link names the link, each by its absolute path under the root.

        Words that name a path go to people whose shell starts in another
        folder: a refusal to an entry's owner, a send's path pasted
        elsewhere. Must reject a ROOT kept relative as given: each path
        then prints as root/..., which from any other folder names
        another folder, or none.

        @interacts  one link planted by hand; one send and one refused
                    status post, each a child with TC_ROOT relative and
                    the root's temp folder as its working folder, bounded
                    by _root.DEFAULT_TC_TIMEOUT_SECONDS.
        @deps       _root.TcRoot, _root.TC, plant; subprocess, sys;
                    LINK_WORDS, EXIT_REFUSED.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            plant(root, "status/x.md")
            env = dict(root.env, TC_ROOT=root.path.name)  # relative to the working folder below
            sent, refused = (subprocess.run([sys.executable, str(_root.TC), *argv], env=env, cwd=root.base,
                                            stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                            timeout=_root.DEFAULT_TC_TIMEOUT_SECONDS)
                             for argv in (["send", "--from", "a", "--to", "b", "hi"], ["status", "x", "busy"]))
        self.assertEqual(sent.returncode, 0, sent.stderr)
        self.assertEqual(sent.stdout, f"sent #1 to b: {root.path / 'mail' / 'to-b' / '000001-from-a.md'}\n")
        self.assertEqual(refused.returncode, EXIT_REFUSED, refused.stderr)
        self.assertIn(f"tc: {root.path / 'status' / 'x.md'} {LINK_WORDS}", refused.stderr)


# SHARED D21 (Claude Opus 5.5, unreviewed): .shared is owner-write only, and
# shared delivery needs a card.
class SharedIsTheInitUsersAndDeliveryNeedsACardTest(UmaskTestCase):
    """D21: .shared at 0644 after init and its owner's reruns, a 0664 one set to 0644 by its owner and named by a member; another member's init refused before it changes anything (another group, or an unreadable .shared), and told who may change the group; a shared send to a card-less inbox refused; a private one delivered.

    One Linux user cannot be another member, so the other member's init
    is shown with lstat reporting another owner for .shared, or with
    os.geteuid reporting another user, and the kernel's refusal of the
    rewrite with ROOT made read-only. The real two-user case is
    qa/human/route-shared.md.

    @interacts  see the module block.
    @deps       _root.TcRoot, UmaskTestCase, groups_to_test, primary_group,
                user_groups, tree, landed, load_tc, run_init,
                owner_patched_lstat.
    @complexity O(1) per test.
    @alloc      one TcRoot per test and group.
    """

    def test_shared_is_0644_after_init_and_after_its_owners_rerun(self):
        """init, then its owner's rerun, then (with a second group) a rerun that rewrites .shared: each exits 0 and leaves .shared 0644, owned by this user, naming the group.

        Must reject a .shared made group-writable (0664 under init's
        umask 002): any member in its group could change which group
        everyone's tc uses.

        @interacts  per group: two or three inits; lstats and reads
                    .shared after each.
        @deps       _root.TcRoot.tc, groups_to_test.
        @complexity O(1) per group.
        @alloc      one TcRoot per group.
        """
        found = groups_to_test(self)
        for label, name, gid in found:
            steps = [("init", name), ("owner's rerun", name)]
            steps += [("owner's rerun with another group", other) for _, other, _ in found if other != name]
            with self.subTest(group=label), _root.TcRoot() as root:
                marker = root.path / ".shared"
                seen = []
                for step, group in steps:
                    code, out, err = root.tc("init", "--shared", "--group", group)
                    self.assertEqual(code, 0, f"{step}: {err}")
                    st = os.lstat(marker)
                    seen.append((step, stat.S_IMODE(st.st_mode), st.st_uid, marker.read_text()))
                self.assertEqual(seen, [(step, SHARED_MARKER_MODE, os.getuid(), f"{group}\n")
                                        for step, group in steps])

    def test_shareds_own_owner_refused_after_the_walk_is_never_told_to_ask_anyone(self):
        """ROOT read-only, a .shared naming another group that this user owns: init exits 1 with the old words, the mailbox stays shared with that group, and no D21 line. .shared is unchanged.

        This is the refusal after the walk, when the rewrite fails. Every
        .shared another user owns that init would rewrite is refused
        before the walk (the next two tests), so this one never names an
        owner. Must reject a refusal that tells .shared's own owner to ask
        someone else. Skipped as root, who may write a read-only folder.

        @interacts  a send; writes .shared by hand; chmods ROOT read-only
                    and back; loads tc in process and runs cmd_init.
        @deps       _root.TcRoot.tc, primary_group, load_tc, run_init.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        if os.geteuid() == 0:
            self.skipTest("root may write a read-only folder")
        label, name, gid = primary_group()
        with _root.TcRoot() as root:
            root.tc("send", "--from", "a", "--to", "b", "hi")
            marker = root.path / ".shared"
            marker.write_text(f"{OTHER_GROUP}\n")
            tc = load_tc(root)
            mode = stat.S_IMODE(os.lstat(root.path).st_mode)
            root.path.chmod(READ_ONLY_FOLDER_MODE)
            try:
                own = run_init(tc, name)
            finally:
                root.path.chmod(mode)
            text = marker.read_text()
        self.assertEqual(own[0], EXIT_REFUSED, own[2])
        self.assertIn(STAYS_SHARED_WORDS.format(group=OTHER_GROUP), own[2])
        self.assertNotIn(INIT_USER_WORDS, own[2], "told .shared's own owner to ask someone else")
        self.assertEqual(text, f"{OTHER_GROUP}\n", "a refused init changed .shared")

    def test_a_members_init_over_an_unreadable_shared_another_user_owns_changes_nothing(self):
        """Shared, b joined, a message, a status set to 0644 by hand (an entry the walk would fix), then .shared made unreadable (two lines) while lstat reports it as another user's: init exits 1 with only the D21 refusal for an unreadable .shared, and every entry keeps its mode and group.

        Must reject an init that walks first and refuses after: it would
        change this member's entries (here, set the status file back to
        0640) before it found it may not rewrite .shared.

        @interacts  init, a join, a send, a status; one chmod and one
                    .shared written by hand; stats the whole root and reads
                    mail/.seq before and after; loads tc in process and
                    runs cmd_init with os.lstat wrapped.
        @deps       _root.TcRoot.tc, primary_group, tree, load_tc,
                    run_init, owner_patched_lstat; unittest.mock;
                    tc.user_name.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        label, name, gid = primary_group()
        with _root.TcRoot() as root:
            setup = [root.tc("init", "--shared", "--group", name),
                     root.tc("join", "b", env={"CLAUDECODE": "1"}),
                     root.tc("send", "--from", "a", "--to", "b", "hi"),
                     root.tc("status", "b", "busy")]
            (root.path / "status" / "b.md").chmod(PRIVATE_FILE_MODE)  # not right yet: the walk would fix it
            marker, seq = root.path / ".shared", root.path / "mail" / ".seq"
            marker.write_text("one\ntwo\n")  # unreadable: names no group on one line
            before, seq_before = tree(root.path, under=None), seq.read_text()
            tc = load_tc(root)
            other = tc.user_name(os.lstat(marker).st_uid + 1)
            with mock.patch.object(os, "lstat", owner_patched_lstat(marker)):
                code, out, err = run_init(tc, name)
            after, seq_after = tree(root.path, under=None), seq.read_text()
            text = marker.read_text()
        for run in setup:
            self.assertEqual(run[0], 0, run[2])
        self.assertEqual(code, EXIT_REFUSED, err)
        self.assertEqual(err, UNREADABLE_TO_YOU_WORDS.format(
            marker=marker, owner=other, only=ONLY_INIT_USER_WORDS.format(owner=other)))
        self.assertEqual(after, before, "a refused init changed an entry")
        self.assertEqual(seq_after, seq_before)
        self.assertEqual(text, "one\ntwo\n", "a refused init changed .shared")

    def test_a_members_init_with_another_group_after_joining_changes_nothing(self):
        """Shared with group g, b joined, a message, a status: an init asking for another group while lstat reports .shared as another user's exits 1 with only the D21 refusal, and every entry keeps its mode and group (b's inbox, card, mail/.seq, .shared).

        Must reject an init that walks first and refuses after: it would
        move this member's inbox, card and mail/.seq into the other group,
        and other members could no longer send. Needs a supplementary
        group; skipped with a reason without one.

        @interacts  init, a join, a send, a status; stats the whole root
                    and reads mail/.seq before and after; loads tc in
                    process and runs cmd_init with os.lstat wrapped.
        @deps       _root.TcRoot.tc, user_groups, tree, load_tc, run_init,
                    owner_patched_lstat; unittest.mock; tc.user_name.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        found = user_groups()
        if len(found) < 2:
            self.skipTest(NO_SECOND_GROUP_REASON)
        (_, first, _), (_, second, _) = found[0], found[1]
        with _root.TcRoot() as root:
            setup = [root.tc("init", "--shared", "--group", first),
                     root.tc("join", "b", env={"CLAUDECODE": "1"}),
                     root.tc("send", "--from", "a", "--to", "b", "hi"),
                     root.tc("status", "b", "busy")]
            marker, seq = root.path / ".shared", root.path / "mail" / ".seq"
            before, seq_before = tree(root.path, under=None), seq.read_text()
            tc = load_tc(root)
            other = tc.user_name(os.lstat(marker).st_uid + 1)
            with mock.patch.object(os, "lstat", owner_patched_lstat(marker)):
                code, out, err = run_init(tc, second)
            after, seq_after = tree(root.path, under=None), seq.read_text()
        for run in setup:
            self.assertEqual(run[0], 0, run[2])
        self.assertEqual(code, EXIT_REFUSED, err)
        self.assertEqual(err, MAY_NOT_CHANGE_WORDS.format(
            marker=marker, group=first, only=ONLY_INIT_USER_WORDS.format(owner=other)))
        self.assertEqual(after, before, "a refused init regrouped or changed an entry")
        self.assertEqual(seq_after, seq_before)

    def test_an_owners_same_group_rerun_sets_a_0664_shared_to_0644(self):
        """init, then .shared set to 0664 by hand (as init wrote it before D21), then the owner's rerun with the same group: exit 0, .shared 0644, still naming the group.

        Must reject a rerun that leaves a .shared written before D21
        group-writable.

        @interacts  two inits; one chmod by hand; lstats and reads .shared.
        @deps       _root.TcRoot.tc, primary_group.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        label, name, gid = primary_group()
        with _root.TcRoot() as root:
            first = root.tc("init", "--shared", "--group", name)
            marker = root.path / ".shared"
            marker.chmod(PRE_D21_MARKER_MODE)
            made = stat.S_IMODE(os.lstat(marker).st_mode)
            rerun = root.tc("init", "--shared", "--group", name)
            settled = (stat.S_IMODE(os.lstat(marker).st_mode), marker.read_text())
        self.assertEqual(first[0], 0, first[2])
        self.assertEqual(made, PRE_D21_MARKER_MODE, "the hand chmod did not take")
        self.assertEqual(rerun[0], 0, rerun[2])
        self.assertEqual(settled, (SHARED_MARKER_MODE, f"{name}\n"))

    def test_a_members_same_group_rerun_leaves_another_users_0664_shared_and_says_so(self):
        """init, .shared set to 0664 by hand, then a same-group rerun in process with os.geteuid reporting another user: exit 0, one line naming the mode and whose rerun tightens it, .shared still 0664.

        One Linux user cannot run init as a second member, so the rerun
        is shown with this process's effective uid reported as another
        user's: .shared's owner is then not the running user. Must reject
        a rerun that changes another user's .shared, and one that says
        nothing about a .shared the group may write.

        SHARED fix round 3 (Claude Opus 5.5, unreviewed): D23's walk
        (root_walk_problem) takes a folder on the way from ROOT to / only
        from root or the user running init, so a member's rerun reaches
        .shared only when root owns ROOT and the folders above it, which
        one user cannot make. The walk is replaced here (it has tests of
        its own in RootAndClaimTest) so this test keeps to .shared.
        SHARED fix round 5 (Claude Opus 5.5, unreviewed): D28 takes back
        round 4's trust in the owner of .shared, which let the walk run
        for real here, so the stand-in is back. SHARED fix round 8 (Claude
        Opus 5.5, unreviewed): the walk always returns its verdict, and
        init opens ROOT and checks it against the folder the walk judged,
        so the stand-in is a verdict with nothing to refuse and ROOT's own
        lstat.

        @interacts  one init; one chmod by hand; loads tc in process and
                    runs cmd_init with os.geteuid and root_walk_problem
                    replaced; lstats ROOT and .shared.
        @deps       _root.TcRoot.tc, primary_group, load_tc, run_init;
                    unittest.mock; tc.user_name, tc.root_walk_problem,
                    tc.WalkProblem.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        label, name, gid = primary_group()
        with _root.TcRoot() as root:
            first = root.tc("init", "--shared", "--group", name)
            marker = root.path / ".shared"
            marker.chmod(PRE_D21_MARKER_MODE)
            tc = load_tc(root)
            owner = tc.user_name(os.getuid())
            passed = tc.WalkProblem(None, None, os.lstat(root.path))  # round 8: nothing to refuse, and ROOT as judged
            with mock.patch.object(os, "geteuid", return_value=os.getuid() + 1), \
                    mock.patch.object(tc, "root_walk_problem", return_value=passed):
                code, out, err = run_init(tc, name)
            left = (stat.S_IMODE(os.lstat(marker).st_mode), marker.read_text())
        self.assertEqual(first[0], 0, first[2])
        self.assertEqual(code, 0, err)
        self.assertEqual(err, TIGHTEN_WORDS.format(marker=marker, mode=PRE_D21_MARKER_MODE, owner=owner))
        self.assertEqual(left, (PRE_D21_MARKER_MODE, f"{name}\n"), "a member's rerun changed another user's .shared")

    def test_a_shared_send_to_an_inbox_with_no_card_is_refused_and_writes_nothing(self):
        """Shared, mail/to-c and its read/ made by hand, no card for c: a send to c exits 1 with exactly C4's words, lands nothing, leaves mail/.seq as it was; the next send takes the next number.

        Every send takes the recipient's inbox lock before it routes, so
        mail/.box-c.lock is the one new entry, and the comparison leaves
        it out. Must reject delivery into a card-less inbox (one a sender
        made would belong to that sender, D20).

        @interacts  init, a join, a send; two folders made by hand; a
                    refused send and one more send; stats the root and
                    reads mail/.seq before and after.
        @deps       _root.TcRoot.tc, primary_group, tree.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        label, name, gid = primary_group()
        with _root.TcRoot() as root:
            setup = [root.tc("init", "--shared", "--group", name),
                     root.tc("join", "b", env={"CLAUDECODE": "1"}),
                     root.tc("send", "--from", "a", "--to", "b", "first")]
            for folder in ("to-c", "to-c/read"):
                (root.path / "mail" / folder).mkdir()  # an inbox nobody joined
            seq = root.path / "mail" / ".seq"
            before, seq_before = tree(root.path), seq.read_text()
            code, out, err = root.tc("send", "--from", "a", "--to", "c", "hi")
            after, seq_after = tree(root.path), seq.read_text()
            following = root.tc("send", "--from", "a", "--to", "b", "second")
        for run in setup:
            self.assertEqual(run[0], 0, run[2])
        self.assertEqual(code, EXIT_REFUSED, f"exited {code}: {out}{err}")
        self.assertEqual((out, err), ("", NOBODY_WORDS.format(name="c") + "\n"))
        after.pop("mail/.box-c.lock", None)
        self.assertEqual(after, before, "a refused send wrote something")
        self.assertEqual(seq_after, seq_before, "a refused send used a number")
        self.assertEqual(following[0], 0, following[2])
        self.assertIn("sent #2 to b", following[1])

    def test_a_private_send_to_an_inbox_with_no_card_still_delivers(self):
        """Private, mail/to-c and its read/ made by hand, no card for c: a send to c exits 0 and lands in mail/to-c (O1, unchanged by D21).

        Must reject a card check that reaches a private mailbox.

        @interacts  two folders made by hand; one send.
        @deps       _root.TcRoot.tc, landed.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            for folder in ("to-c", "to-c/read"):
                (root.path / "mail" / folder).mkdir(parents=True)
            code, out, err = root.tc("send", "--from", "a", "--to", "c", "hi")
            mail = landed(root)
        self.assertEqual(code, 0, err)
        self.assertEqual(mail, ["mail/to-c/000001-from-a.md"])


# SHARED fix round 4 (Claude Opus 5.5, unreviewed): the audit's LOW-3, which lock a waiter asked for.
def lock_waiters(path):
    """{(pid, access)} for each process blocked waiting for an flock on `path`, read from /proc/locks; access is READ (LOCK_SH) or WRITE (LOCK_EX).

    The harness's flock_holders() names only holders. A waiter's line
    carries "->" before FLOCK, so it is read here, apart.

    @interacts  stats `path`; reads /proc/locks. Writes nothing.
    @deps       os, pathlib; Linux /proc/locks; WAITER_* columns.
    @complexity O(k) over k lines in /proc/locks (tens).
    @alloc      the table's lines and one set of pairs, returned.
    """
    try:
        st = os.stat(path)
    except FileNotFoundError:
        return set()
    key = f"{os.major(st.st_dev):02x}:{os.minor(st.st_dev):02x}:{st.st_ino}"
    found = set()
    for line in pathlib.Path("/proc/locks").read_text().splitlines():
        cols = line.split()
        if (len(cols) > WAITER_FILE_COLUMN and cols[WAITER_MARK_COLUMN] == WAITER_MARK
                and cols[WAITER_KIND_COLUMN] == "FLOCK" and cols[WAITER_FILE_COLUMN] == key):
            found.add((int(cols[WAITER_PID_COLUMN]), cols[WAITER_ACCESS_COLUMN]))
    return found


# SHARED fix round 2 (Claude Opus 5.5, unreviewed): D20's bound.
def contents(path):
    """Every entry under `path`: {relative path: bytes for a file, "folder" or "other"}, from lstat, never through a link.

    @interacts  lstats every entry and reads every regular file. Writes
                nothing.
    @deps       os, stat, pathlib.
    @complexity O(e + b) over e entries (a few dozen) and b bytes in their
                files (a few KiB).
    @alloc      one dict, returned.
    """
    out = {}
    for entry in path.rglob("*"):
        mode = os.lstat(entry).st_mode
        out[str(entry.relative_to(path))] = (entry.read_bytes() if stat.S_ISREG(mode) else
                                             "folder" if stat.S_ISDIR(mode) else "other")
    return out


class NoLostMailNoHangTest(UmaskTestCase):
    """D20's bound through the group-writable files: a mail/.seq set back never makes a send replace a message, and a lock held by another process makes a command fail within LOCK_WAIT_SECONDS, never hang.

    The audit's MEDIUM-1 and MEDIUM-3 (audits/2026-10-14-2259-quick). One
    Linux user stands in for the hostile member: it sets mail/.seq back,
    or holds a lock's flock in this process, as any member of the group
    could. SHARED fix round 3 (Claude Opus 5.5, unreviewed): that member
    also plants a file under a read message's name, and holds mail/.seq
    on and off from a child process (audits/2026-10-14-2358-quick,
    MEDIUM-1 and LOW-2); a held lock exits 10 (D23). SHARED fix round 4
    (Claude Opus 5.5, unreviewed): the member plants in read/ as well as
    in the inbox, and under a name up to the filesystem's limit
    (audits/2026-10-15-0102-quick, MEDIUM-1 and HIGH-1); holds an inbox
    lock while a card turns codex (LOW-3); and plants a name for every
    number a send could take, which exits 10 (DEBT-3). SHARED fix round 5
    (Claude Opus 5.5, unreviewed): the member plants a name of dots and
    `md` (LOW-2), links an inbox file at the name tc read moves it to, so
    the rename does nothing (LOW-1), and plants a file at the next
    message's .tmp name (DEBT-1; audits/2026-10-15-0201-quick). SHARED
    fix round 6 (Claude Opus 5.5, unreviewed): the member plants a .tmp
    name for every number a send could take, and the words name the last
    .tmp and blame no set-back counter (LOW-2,
    audits/2026-10-15-0300-quick). SHARED fix round 7 (Claude Opus 5.5,
    unreviewed): with the counter set back and a .tmp at each of its
    numbers, the words never say mail/.seq was not behind (LOW-1,
    audits/2026-10-15-0408-quick).

    @interacts  see the module block.
    @deps       _root.TcRoot, UmaskTestCase, primary_group, contents,
                load_tc, landed, lock_waiters; argparse, contextlib,
                errno, fcntl, io, json, os, pathlib, pwd, subprocess, sys,
                time, unittest.mock; SEQ_HOLDER.
    @complexity O(1) per test.
    @alloc      one TcRoot per case.
    """

    def set_back_and_send(self, root, shared):
        """Join b (after init when `shared`), send two messages, set mail/.seq back so the next number names an existing one: the runs, in order.

        @interacts  init when `shared`, a join, two sends, one write of
                    mail/.seq by hand.
        @deps       _root.TcRoot.tc, primary_group; SET_BACK_SEQ.
        @complexity O(1).
        @alloc      the list of runs, returned.
        """
        runs = [root.tc("init", "--shared", "--group", primary_group()[1])] if shared else []
        runs += [root.tc("join", "b", env={"CLAUDECODE": "1"}),
                 root.tc("send", "--from", "a", "--to", "b", "first")]
        (root.path / "mail" / ".seq").write_text(str(SET_BACK_SEQ))
        runs.append(root.tc("send", "--from", "a", "--to", "b", "the unread one"))
        (root.path / "mail" / ".seq").write_text(str(SET_BACK_SEQ))
        return runs

    def test_a_send_after_mail_seq_is_set_back_never_replaces_unread_mail(self):
        """Private and shared: unread #6 from a in b's inbox and mail/.seq set back to 5: the next send from a lands as #7, and #6 is unchanged, byte for byte.

        Must reject a publish that renames over what has the name (D20:
        the member who set mail/.seq back makes the sender's own unread
        #6 vanish, and the send still says `sent #6`).

        @interacts  per mode: set_back_and_send, one more send; reads the
                    inbox.
        @deps       set_back_and_send, _root.TcRoot.tc.
        @complexity O(1) per mode.
        @alloc      one TcRoot per mode.
        """
        sixth = f"{SET_BACK_SEQ + 1:06d}-from-a.md"
        seventh = f"{SET_BACK_SEQ + 2:06d}-from-a.md"
        for shared in (False, True):
            with self.subTest(shared=shared), _root.TcRoot() as root:
                runs = self.set_back_and_send(root, shared)
                box = root.path / "mail" / "to-b"
                before = (box / sixth).read_bytes()
                code, out, err = root.tc("send", "--from", "a", "--to", "b", "after the set back")
                after = (box / sixth).read_bytes()
                names = sorted(p.name for p in box.iterdir() if p.name != "read")
                landed_text = (box / seventh).read_text() if (box / seventh).exists() else ""
                for run in runs:
                    self.assertEqual(run[0], 0, run[2])
                self.assertEqual(after, before, "a send after mail/.seq was set back replaced unread #6")
                self.assertEqual(code, 0, err)
                self.assertIn(f"sent #{SET_BACK_SEQ + 2} to b", out)
                self.assertEqual(names, ["000001-from-a.md", sixth, seventh], "a .tmp was left or a name lost")
                self.assertIn("after the set back", landed_text)

    def test_a_send_after_mail_seq_is_set_back_never_takes_a_read_messages_name(self):
        """Private and shared: b has read #1, then mail/.seq is set back to 0: the next send lands as #2, and after b reads it read/#1 is unchanged, byte for byte.

        tc read renames each message into read/ under its own name, so a
        send that took #1 again would make that read replace the old #1.
        Must reject a publish that checks only the inbox.

        @interacts  per mode: init when shared, a join, a send, two reads,
                    one write of mail/.seq by hand, one more send.
        @deps       _root.TcRoot.tc, primary_group.
        @complexity O(1) per mode.
        @alloc      one TcRoot per mode.
        """
        for shared in (False, True):
            with self.subTest(shared=shared), _root.TcRoot() as root:
                runs = [root.tc("init", "--shared", "--group", primary_group()[1])] if shared else []
                runs += [root.tc("join", "b", env={"CLAUDECODE": "1"}),
                         root.tc("send", "--from", "a", "--to", "b", "first, read"),
                         root.tc("read", "b")]
                read = root.path / "mail" / "to-b" / "read"
                before = (read / "000001-from-a.md").read_bytes()
                (root.path / "mail" / ".seq").write_text("0")
                sent = root.tc("send", "--from", "a", "--to", "b", "second")
                again = root.tc("read", "b")
                after = (read / "000001-from-a.md").read_bytes()
                history = sorted(p.name for p in read.iterdir())
                for run in runs:
                    self.assertEqual(run[0], 0, run[2])
                self.assertEqual(after, before, "a read replaced read/#1 after mail/.seq was set back")
                self.assertEqual(sent[0], 0, sent[2])
                self.assertIn("sent #2 to b", sent[1])
                self.assertEqual(again[0], 0, again[2])
                self.assertIn("second", again[1])
                self.assertEqual(history, ["000001-from-a.md", "000002-from-a.md"])

    def test_a_held_lock_makes_each_command_fail_within_the_bound_and_write_nothing(self):
        """This process holds mail/.seq or a name's inbox lock (LOCK_EX), one root per case: send, read, a codex join, tc card and a codex send (on its inbox lock, and on mail/.seq) each exit 10 (busy, D23) within LOCK_WAIT_SECONDS plus the margin, say whose lock, name its holder (the running user and this process's pid), and change nothing; a codex send with the ring marker held lands, rings once, and says the marker could not be cleared within two waits.

        The cases run at once, so the test costs about two waits, not
        eight. Each child runs under a timeout, so a tc that waits on the
        flock forever fails here instead of hanging the suite. Must reject
        a plain blocking flock on mail/.seq, the inbox lock or the marker
        (D20: a member who holds one hangs every other member's command
        for as long as it likes), and a held lock that exits 1, which
        reads as a final refusal (SHARED fix round 3, D23). P3 fix round 1b
        (Claude Opus 5.5, unreviewed): D35 (3), the audit's REC-4 (test-
        strategist). Must reject busy words that do not name the holder's
        user and pid, the stuck member's only lead to whom to ask.

        @interacts  per case, a root: sends, a codex join and a fake codex
                    as setup; one lock file opened and flocked here; the
                    whole root read before and after; one background tc.
        @deps       _root.TcRoot.tc, start, fake_bin, contents,
                    running_login; contextlib, fcntl, os, subprocess, time;
                    LOCK_WAIT_SECONDS, LOCK_REFUSE_MARGIN_SECONDS,
                    LOCK_HELD_WORDS, HELD_BY_WORDS, THREAD, EXIT_BUSY.
        @complexity O(1): eight children at once, each at most
                    LOCK_WAIT_SECONDS of waiting (the marker case two).
        @alloc      eight TcRoots, eight open lock files and eight
                    children, all released when the stack closes.
        """
        codex = {"CODEX_THREAD_ID": THREAD, "CLAUDECODE": None}
        send_b = ["send", "--from", "a", "--to", "b", "second"]
        cases = [  # label, setup, the lock held, argv, env, whose lock the words name
            ("send, inbox lock", "send b", "mail/.box-b.lock", send_b, None, "b"),
            ("send, mail/.seq", "send b", "mail/.seq", send_b, None, "mail/.seq"),
            ("read, inbox lock", "send b", "mail/.box-b.lock", ["read", "b"], None, "b"),
            ("codex join, inbox lock", None, "mail/.box-x.lock", ["join", "x"], codex, "x"),
            ("card, inbox lock", None, "mail/.box-x.lock", ["card", "x", "--ssh", "u@h"], None, "x"),
            ("codex send, inbox lock", "join c", "mail/.box-c.lock", ["send", "--from", "a", "--to", "c", "hi"],
             None, "c"),
            ("codex send, mail/.seq", "join c", "mail/.seq", ["send", "--from", "a", "--to", "c", "hi"],
             None, "mail/.seq"),  # SHARED fix round 3 (Claude Opus 5.5, unreviewed): REC-2
            ("codex send, ring marker", "join c", "mail/.ring-pending-c", ["send", "--from", "a", "--to", "c", "hi"],
             None, "mail/.ring-pending-c"),
        ]
        seen = {}
        with contextlib.ExitStack() as stack:
            running = []
            for label, setup, held_at, argv, env, whose in cases:
                root = stack.enter_context(_root.TcRoot())
                folder, _ = root.fake_bin("codex", 0)
                if setup == "send b":
                    self.assertEqual(root.tc("send", "--from", "a", "--to", "b", "first")[0], 0)
                if setup == "join c":
                    self.assertEqual(root.tc("join", "c", env=codex)[0], 0)
                lock = root.path / held_at
                lock.parent.mkdir(parents=True, exist_ok=True)
                if label.endswith("ring marker"):
                    lock.write_text(f"{CLEAR_STATE}\n")
                held = stack.enter_context(open(lock, "a"))
                fcntl.flock(held, fcntl.LOCK_EX)
                waits = 2 if label.endswith("ring marker") else 1
                ceiling = waits * LOCK_WAIT_SECONDS + LOCK_REFUSE_MARGIN_SECONDS
                before = contents(root.path)
                proc = root.start(*argv, env=env)
                running.append((label, root, proc, time.monotonic() + ceiling, ceiling, before,
                                folder.parent / "calls.jsonl", whose))
            for label, root, proc, deadline, ceiling, before, record, whose in running:
                try:
                    out, err = proc.communicate(timeout=max(0.0, deadline - time.monotonic()))
                except subprocess.TimeoutExpired:
                    self.fail(f"{label}: tc still waited {ceiling} s on a lock this test held: it hangs")
                what = str(root.path / whose) if "/" in whose else whose
                rang = len(record.read_text().splitlines()) if record.exists() else 0
                seen[label] = (proc.returncode, out, err, what, before, contents(root.path), rang)
        for label, (code, out, err, what, before, after, rang) in seen.items():
            with self.subTest(case=label):
                if label.endswith("ring marker"):
                    self.assertEqual(code, 0, err)
                    self.assertIn("sent #1 to c", out)
                    self.assertIn(f"could not be cleared ({LOCK_HELD_WORDS.format(what=what)})", err)
                    self.assertEqual(rang, 1)
                    self.assertEqual(after["mail/.ring-pending-c"], f"{CLEAR_STATE}\n".encode(),
                                     "a marker write went through a lock this test held")
                    continue
                self.assertEqual(code, EXIT_BUSY, err)  # SHARED fix round 3 (Claude Opus 5.5, unreviewed): D23
                self.assertEqual(err, HELD_BY_WORDS.format(what=what, user=running_login(), pid=os.getpid()))  # P3 fix round 1b (Claude Opus 5.5, unreviewed): REC-4
                self.assertEqual(after, before, "a refused command changed the root")
                self.assertEqual(rang, 0, "a refused codex send rang")

    # SHARED fix round 3 (Claude Opus 5.5, unreviewed): the audit's MEDIUM-1.
    def test_a_read_never_replaces_a_read_message_and_keeps_a_planted_one(self):
        """Private and shared: b has read #3, a file named 000003-from-a.md is planted in b's inbox, and read/by-hand-1-000003-from-a.md is planted too: tc read b exits 0, read/#3 and the first by-hand file are unchanged byte for byte, the planted file is kept as read/by-hand-2-000003-from-a.md, the read prints the words and the planted text, and the inbox holds no message.

        Must reject the plain rename (the planted file replaces read/#3:
        D20, a member makes the owner's read destroy a read message), a
        by-hand search that takes a name already held, a read that leaves
        the planted file unread (tc wait would wake on it for good), and a
        new name the board would read a sender from. SHARED fix round 4
        (Claude Opus 5.5, unreviewed): the audit's MEDIUM-1. The words are
        TWIN_WORDS, the same as when the plant is in read/ (the next test):
        both paths, each owner when shared, neither file called the
        forgery.

        @interacts  per mode: init when shared, a join, three sends, two
                    reads; two files written by hand; reads the user
                    database.
        @deps       _root.TcRoot.tc, primary_group; pwd; BY_HAND_NAME,
                    TWIN_WORDS, OWNED_BY_WORDS, PLANTED_TEXT, TAKEN_TEXT,
                    BOARD_MESSAGE_NAME.
        @complexity O(1) per mode.
        @alloc      one TcRoot per mode.
        """
        name = "000003-from-a.md"
        for shared in (False, True):
            with self.subTest(shared=shared), _root.TcRoot() as root:
                runs = [root.tc("init", "--shared", "--group", primary_group()[1])] if shared else []
                runs.append(root.tc("join", "b", env={"CLAUDECODE": "1"}))
                runs += [root.tc("send", "--from", "a", "--to", "b", f"message {n}") for n in (1, 2, 3)]
                runs.append(root.tc("read", "b"))
                box = root.path / "mail" / "to-b"
                read = box / "read"
                before = (read / name).read_bytes()
                taken = read / BY_HAND_NAME.format(k=1, name=name)
                taken.write_text(TAKEN_TEXT)
                (box / name).write_text(PLANTED_TEXT)
                code, out, err = root.tc("read", "b")
                kept = read / BY_HAND_NAME.format(k=2, name=name)
                after = (read / name).read_bytes()
                kept_text = kept.read_text() if kept.exists() else None
                left = sorted(p.name for p in box.glob("*.md"))
                for run in runs:
                    self.assertEqual(run[0], 0, run[2])
                self.assertEqual(after, before, "tc read replaced read/#3 with a file planted in the inbox")
                self.assertEqual(taken.read_text(), TAKEN_TEXT, "tc read replaced a by-hand name already held")
                self.assertEqual(kept_text, PLANTED_TEXT, "the planted file is not at the first free by-hand name")
                self.assertEqual(left, [], "tc read left the planted file unread")
                self.assertEqual(code, 0, err)
                owner = OWNED_BY_WORDS.format(login=pwd.getpwuid(os.getuid()).pw_name) if shared else ""
                self.assertIn(TWIN_WORDS.format(name=name, kept=read / name, kept_owner=owner, moved=kept,
                                                moved_owner=owner), out)
                self.assertIn(PLANTED_TEXT, out)
                self.assertIsNone(BOARD_MESSAGE_NAME.match(kept.name), "the board would read a sender from it")

    # SHARED fix round 4 (Claude Opus 5.5, unreviewed): the audit's MEDIUM-1, the other order.
    def test_a_file_planted_in_read_under_an_unread_name_is_kept_and_neither_file_is_called_forged(self):
        """Private and shared: unread #1 from a in b's inbox, and a file planted in read/ under its name: tc read b exits 0, the plant stays at read/000001-from-a.md and the real message moves to read/by-hand-1-000001-from-a.md, each byte for byte, and the read prints TWIN_WORDS (both paths, each owner when shared) and the real text.

        A member may make names in the 3770 read/ as easily as in the
        inbox, so tc cannot tell which of the two it wrote. Must reject
        words that call the inbox file hand-written (here it is the real
        message: the owner's agent would be told carl's mail is forged),
        and a read that replaces or changes either file.

        @interacts  per mode: init when shared, a join, a send, a read; one
                    file written by hand; reads the user database.
        @deps       _root.TcRoot.tc, primary_group; pwd; BY_HAND_NAME,
                    TWIN_WORDS, OWNED_BY_WORDS, IN_READ_TEXT, REAL_TEXT.
        @complexity O(1) per mode.
        @alloc      one TcRoot per mode.
        """
        name = "000001-from-a.md"
        for shared in (False, True):
            with self.subTest(shared=shared), _root.TcRoot() as root:
                runs = [root.tc("init", "--shared", "--group", primary_group()[1])] if shared else []
                runs += [root.tc("join", "b", env={"CLAUDECODE": "1"}),
                         root.tc("send", "--from", "a", "--to", "b", REAL_TEXT)]
                box = root.path / "mail" / "to-b"
                read = box / "read"
                real = (box / name).read_bytes()
                (read / name).write_text(IN_READ_TEXT)
                code, out, err = root.tc("read", "b")
                moved = read / BY_HAND_NAME.format(k=1, name=name)
                planted_after = (read / name).read_bytes()
                moved_after = moved.read_bytes() if moved.exists() else None
                left = sorted(p.name for p in box.glob("*.md"))
                owner = OWNED_BY_WORDS.format(login=pwd.getpwuid(os.getuid()).pw_name) if shared else ""
                for run in runs:
                    self.assertEqual(run[0], 0, run[2])
                self.assertEqual(code, 0, err)
                self.assertIn(TWIN_WORDS.format(name=name, kept=read / name, kept_owner=owner, moved=moved,
                                                moved_owner=owner), out)
                self.assertEqual(planted_after, IN_READ_TEXT.encode(), "tc read replaced the file planted in read/")
                self.assertEqual(moved_after, real, "the real message is not at the by-hand name, byte for byte")
                self.assertIn(REAL_TEXT, out)
                self.assertEqual(left, [], "tc read left the real message unread")

    # SHARED fix round 4 (Claude Opus 5.5, unreviewed): the audit's HIGH-1, a wake at most once.
    def test_a_planted_name_at_the_length_limit_moves_and_wakes_tc_wait_at_most_once(self):
        """Shared: a file planted in b's inbox and in read/ under one name, LONG_NAME_BYTES long, then (a fresh root) exactly read/'s limit (PC_NAME_MAX, .md included), then (round 5) dots and `md` to the limit: tc wait b exits 0 for it, tc read b exits 0 and moves it to a by-hand name that fits the limit and keeps .md, the inbox is empty, and a second tc wait b times out (exit 2), never 0 at once.

        The audit's HIGH-1 (audits/2026-10-15-0102-quick). Must reject a
        by-hand name that takes the prefix whole: past the limit the
        rename fails, the file stays in the inbox, and every re-armed tc
        wait exits 0 at once, a paid wake loop a member can start (D20).
        A member plants these under a shared mailbox, so the test runs
        shared; the move is one code path, shared or not. SHARED fix
        round 5 (Claude Opus 5.5, unreviewed): the audit's LOW-2
        (audits/2026-10-15-0201-quick). The dots case is `"." * 253 +
        "md"` on a 255-byte limit; must reject a suffix from
        os.path.splitext, which gives that name none, so the cut drops
        the `md` and tc log never lists the moved file again.

        @interacts  per case: init, a join, two files written by hand, two
                    waits (the second runs ONE_POLL_SECONDS), one read;
                    reads read/'s name limit and lists the inbox and read/.
        @deps       _root.TcRoot.tc, primary_group; os; LONG_NAME_BYTES,
                    MESSAGE_SUFFIX, DOTS_NAME_TAIL, BY_HAND_NAME,
                    IN_READ_TEXT, PLANTED_TEXT, ONE_POLL_SECONDS,
                    EXIT_TIMEOUT.
        @complexity O(1) per case, three cases; about ONE_POLL_SECONDS of
                    waiting each.
        @alloc      one TcRoot per case.
        """
        for case in ("LONG_NAME_BYTES", "PC_NAME_MAX", "dots only"):
            with self.subTest(name=case), _root.TcRoot() as root:
                runs = [root.tc("init", "--shared", "--group", primary_group()[1]),
                        root.tc("join", "b", env={"CLAUDECODE": "1"})]
                box = root.path / "mail" / "to-b"
                read = box / "read"
                limit = os.pathconf(read, "PC_NAME_MAX")
                size = LONG_NAME_BYTES if case == "LONG_NAME_BYTES" else limit
                name = ("." * (size - len(DOTS_NAME_TAIL)) + DOTS_NAME_TAIL if case == "dots only"
                        else "x" * (size - len(MESSAGE_SUFFIX)) + MESSAGE_SUFFIX)
                (read / name).write_text(IN_READ_TEXT)
                (box / name).write_text(PLANTED_TEXT)
                first = root.tc("wait", "b", "--timeout", ONE_POLL_SECONDS)
                code, out, err = root.tc("read", "b")
                left = sorted(p.name for p in box.glob("*.md"))
                second = root.tc("wait", "b", "--timeout", ONE_POLL_SECONDS)
                kept = [p for p in read.iterdir() if p.name.startswith(BY_HAND_NAME.format(k=1, name=""))]
                kept_text = kept[0].read_text() if len(kept) == 1 else None
                in_read = (read / name).read_text()
                for run in runs:
                    self.assertEqual(run[0], 0, run[2])
                self.assertEqual(len(os.fsencode(name)), size)
                self.assertEqual(first[0], 0, f"the first tc wait did not wake for the planted file: {first}")
                self.assertEqual(second[0], EXIT_TIMEOUT,
                                 f"a planted {size}-byte name woke tc wait again after tc read: {second}")
                self.assertEqual(left, [], "tc read left the planted file in the inbox")
                self.assertEqual(code, 0, err)
                self.assertEqual(len(kept), 1, f"by-hand files in read/: {kept}")
                self.assertLessEqual(len(os.fsencode(kept[0].name)), limit, "the by-hand name passes the limit")
                self.assertTrue(kept[0].name.endswith(MESSAGE_SUFFIX), kept[0].name)
                self.assertEqual(kept_text, PLANTED_TEXT)
                self.assertEqual(in_read, IN_READ_TEXT, "tc read changed the file already in read/")

    # SHARED fix round 5 (Claude Opus 5.5, unreviewed): the audit's LOW-1 (audits/2026-10-15-0201-quick).
    def test_a_rename_a_hard_link_turned_into_nothing_is_never_claimed_as_read(self):
        """In process, os.rename for one inbox file replaced by a hard link at its target, which is what rename(2) leaves when a member links the file there first: tc read exits 1, names that file as not moved with STILL_THERE_WORDS, never prints it, and moves and prints the other; the file stays in the inbox.

        rename(2) between two names of one file does nothing and returns
        0, and a member who owns an inbox file may link it at the name tc
        read just found free (the group may make names in a 3770 read/).
        One user cannot win that race on purpose, so the patched rename
        links instead of moving. Must reject a read that counts the rename
        as a move: it prints the file and exits 0 while the file stays, so
        the next tc wait wakes for it at once.

        @interacts  two sends; loads tc in process and runs cmd_read with
                    os.rename replaced and stdout and stderr captured;
                    makes one hard link (the stand-in rename); lists the
                    inbox.
        @deps       _root.TcRoot.tc, load_tc; argparse, contextlib, io, os,
                    pathlib, unittest.mock; tc.cmd_read; STILL_THERE_WORDS,
                    EXIT_REFUSED.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        with _root.TcRoot() as root:
            for sender in ("a", "c"):
                root.tc("send", "--from", sender, "--to", "b", f"from {sender}")
            box = root.path / "mail" / "to-b"
            linked = box / "000001-from-a.md"
            tc = load_tc(root)
            real = os.rename

            # P3 fix round 1a (Claude Opus 5.5, unreviewed): tc read moves by name between open folders (os.rename, D35).
            def rename(src, dst, *, src_dir_fd=None, dst_dir_fd=None):
                if os.path.basename(src) == linked.name:
                    # the member's link at the target: rename(2) between the two names does nothing
                    os.link(src, dst, src_dir_fd=src_dir_fd, dst_dir_fd=dst_dir_fd, follow_symlinks=False)
                    return None
                return real(src, dst, src_dir_fd=src_dir_fd, dst_dir_fd=dst_dir_fd)
            out, err = io.StringIO(), io.StringIO()
            with mock.patch.object(os, "rename", rename), contextlib.redirect_stdout(out), \
                    contextlib.redirect_stderr(err):
                with self.assertRaises(SystemExit) as stop:
                    tc.cmd_read(argparse.Namespace(name="b"))
            unread = sorted(p.name for p in box.glob("*.md"))
        self.assertEqual(stop.exception.code, EXIT_REFUSED)
        self.assertEqual(err.getvalue(),
                         STILL_THERE_WORDS.format(path=linked, target=box / "read" / linked.name) + "\n")
        self.assertNotIn("from a", out.getvalue(), "tc read showed a file it did not move")
        self.assertIn("from c", out.getvalue())
        self.assertEqual(unread, ["000001-from-a.md"])

    # SHARED fix round 4 (Claude Opus 5.5, unreviewed): the audit's LOW-3, one bound in every path.
    def test_a_local_send_whose_card_turns_codex_under_a_held_lock_waits_one_bound(self):
        """This process holds c's inbox lock alone while a send to c (no card yet: route local) waits for it shared; c's card then turns codex, and after CARD_CHANGE_HOLD_SECONDS the lock is let down to shared: the send reads the codex card, asks for the lock alone (deliver_codex, proven in /proc/locks), and exits 10 within LOCK_WAIT_SECONDS of when it began to wait, plus FLIP_SLACK_SECONDS. Nothing lands and nothing rings.

        The lock is held throughout, across the card change. The card is
        written by hand, standing in for a codex join that lands between
        the send's two card reads (a real one would wait on this lock
        too). Must reject a deliver_codex that takes a deadline of its
        own: the send then waits CARD_CHANGE_HOLD_SECONDS and a whole
        second LOCK_WAIT_SECONDS (C4: per command).

        @interacts  makes mail/ and the inbox lock and holds its flock here
                    (alone, then shared); one background send, proven
                    waiting in /proc/locks twice; writes cards/c.json by
                    hand; a fake codex, asserted never called; lists the
                    inboxes. The harness kills the send by its pid.
        @deps       _root.TcRoot.start, fake_bin, lock_waiters, landed;
                    running_login; fcntl, json, os, subprocess, time;
                    THREAD, CARD_CHANGE_HOLD_SECONDS, FLIP_SLACK_SECONDS,
                    LOCK_WAIT_SECONDS, HELD_BY_WORDS, EXIT_BUSY.
        @complexity O(1): about LOCK_WAIT_SECONDS of waiting, at most
                    _root.LOCK_CEILING_SECONDS to see the first wait.
        @alloc      one TcRoot, one open lock file, one child.
        """
        with _root.TcRoot() as root:
            folder, calls = root.fake_bin("codex", 0)
            (root.path / "mail").mkdir()
            lock = root.path / "mail" / ".box-c.lock"
            with open(lock, "a") as held:
                fcntl.flock(held, fcntl.LOCK_EX)
                proc = root.start("send", "--from", "a", "--to", "c", "hi")
                proof = time.monotonic() + _root.LOCK_CEILING_SECONDS
                while (proc.pid, "READ") not in lock_waiters(lock):
                    if proc.poll() is not None or time.monotonic() >= proof:
                        self.fail(f"the local send never waited for {lock} shared")
                    time.sleep(_root.LOCK_POLL_SECONDS)
                began = time.monotonic()
                (root.path / "cards").mkdir()
                (root.path / "cards" / "c.json").write_text(json.dumps(
                    {"version": 1, "name": "c", "kind": "codex", "route": "codex", "thread_id": THREAD}))
                time.sleep(max(0.0, began + CARD_CHANGE_HOLD_SECONDS - time.monotonic()))
                fcntl.flock(held, fcntl.LOCK_SH)
                bound = began + LOCK_WAIT_SECONDS
                while (proc.pid, "WRITE") not in lock_waiters(lock):
                    if proc.poll() is not None or time.monotonic() >= bound:
                        self.fail("the send never asked for c's lock alone after its card turned codex")
                    time.sleep(_root.LOCK_POLL_SECONDS)
                try:
                    out, err = proc.communicate(timeout=max(0.0, bound + FLIP_SLACK_SECONDS - time.monotonic()))
                except subprocess.TimeoutExpired:
                    self.fail(f"the send still waited {LOCK_WAIT_SECONDS + FLIP_SLACK_SECONDS} s after it began to "
                              f"wait: deliver_codex took a second bound of its own")
            record = folder.parent / "calls.jsonl"
            rang = calls()
            mail = landed(root)
        self.assertEqual(proc.returncode, EXIT_BUSY, err)
        self.assertEqual(err, HELD_BY_WORDS.format(what="c", user=running_login(), pid=os.getpid()))  # P3 fix round 1b (Claude Opus 5.5, unreviewed): D35 (3)
        self.assertEqual(mail, [], "a refused send landed a message")
        self.assertEqual(rang, [], f"a refused send rang ({record})")

    # SHARED fix round 4 (Claude Opus 5.5, unreviewed): the audit's DEBT-3, out of numbers is busy.
    def test_a_send_that_finds_every_number_taken_exits_10_and_the_next_send_lands(self):
        """A first send to b, then a file planted in read/ for each of the PLANTED_NAMES numbers past the counter: the next send exits 10 (busy), names the last taken name as read/<name>, says mail/.seq was behind the names there, and lands nothing; the send after it lands as the number past the planted ones.

        Dev exit row 10, amended: each try moved mail/.seq on, so the next
        send starts past the taken names, and the refusal may run again.
        Must reject exit 1, which C3 reads from the far side as final: a
        far member who plants names past the counter would turn an
        incoming ssh message into a permanent refusal. SHARED fix round 6
        (Claude Opus 5.5, unreviewed): the audit's LOW-2. Must reject
        words naming the inbox's own .md, which is not there.

        @interacts  three sends; PLANTED_NAMES empty files written by hand
                    in read/; lists the inbox.
        @deps       _root.TcRoot.tc; PLANTED_NAMES, ALL_TAKEN_WORDS,
                    BEHIND_WHY, EXIT_BUSY.
        @complexity O(PLANTED_NAMES) files, three tc runs.
        @alloc      one TcRoot, PLANTED_NAMES empty files.
        """
        with _root.TcRoot() as root:
            first = root.tc("send", "--from", "a", "--to", "b", "first")
            box = root.path / "mail" / "to-b"
            for n in range(2, PLANTED_NAMES + 2):
                (box / "read" / f"{n:06d}-from-a.md").write_text("")
            code, out, err = root.tc("send", "--from", "a", "--to", "b", "second")
            unread = sorted(p.name for p in box.iterdir() if p.name != "read")
            after = root.tc("send", "--from", "a", "--to", "b", "third")
        self.assertEqual(first[0], 0, first[2])
        self.assertEqual(code, EXIT_BUSY, err)
        self.assertEqual(err, ALL_TAKEN_WORDS.format(tries=PLANTED_NAMES, box=box,
                                                     last=f"read/{PLANTED_NAMES + 1:06d}-from-a.md", why=BEHIND_WHY))
        self.assertEqual(unread, ["000001-from-a.md"], "a refused send left a message or a .tmp")
        self.assertEqual(after[0], 0, after[2])
        self.assertIn(f"sent #{PLANTED_NAMES + 2} to b", after[1])

    # SHARED fix round 6 (Claude Opus 5.5, unreviewed): the audit's LOW-2 (audits/2026-10-15-0300-quick).
    def test_a_send_that_finds_every_tmp_name_taken_names_the_tmp_and_blames_no_set_back(self):
        """A first send to b, then a file planted in b's inbox at the .tmp name of each of the PLANTED_NAMES numbers past the counter: the next send exits 10, names the last planted .tmp, says each number was taken by a .tmp name already there and no try got as far as the message's own name, and lands nothing; each planted file is unchanged, and the send after it lands as the number past them.

        A member who reads mail/.seq plants the names a send will make its
        .tmp at, and never touches the counter. Must reject words that
        name the number's .md (not there) and blame a set-back mail/.seq.
        Also the bound round 5 left untested: a run of planted .tmp names
        to PUBLISH_MAX_TRIES ends in exit 10. SHARED fix round 7 (Claude
        Opus 5.5, unreviewed): the words no longer say mail/.seq was not
        behind (the audit's LOW-1; the set-back case is the next test).

        @interacts  three sends; PLANTED_NAMES files written by hand in
                    the inbox, read back; lists the inbox.
        @deps       _root.TcRoot.tc; PLANTED_NAMES, PLANTED_TMP_TEXT,
                    ALL_TAKEN_WORDS, TMP_TAKEN_WHY, EXIT_BUSY.
        @complexity O(PLANTED_NAMES) files, three tc runs.
        @alloc      one TcRoot, PLANTED_NAMES small files.
        """
        with _root.TcRoot() as root:
            first = root.tc("send", "--from", "a", "--to", "b", "first")
            box = root.path / "mail" / "to-b"
            planted = [box / f"{n:06d}-from-a.tmp" for n in range(2, PLANTED_NAMES + 2)]
            for path in planted:
                path.write_text(PLANTED_TMP_TEXT)
            code, out, err = root.tc("send", "--from", "a", "--to", "b", "second")
            kept = {path.read_text() for path in planted}
            unread = sorted(p.name for p in box.glob("*.md"))
            after = root.tc("send", "--from", "a", "--to", "b", "third")
        self.assertEqual(first[0], 0, first[2])
        self.assertEqual(code, EXIT_BUSY, err)
        self.assertEqual(err, ALL_TAKEN_WORDS.format(tries=PLANTED_NAMES, box=box,
                                                     last=f"{PLANTED_NAMES + 1:06d}-from-a.tmp", why=TMP_TAKEN_WHY))
        self.assertNotIn("set back", err)
        self.assertEqual(kept, {PLANTED_TMP_TEXT}, "a send changed a planted .tmp")
        self.assertEqual(unread, ["000001-from-a.md"], "a refused send landed a message")
        self.assertEqual(after[0], 0, after[2])
        self.assertIn(f"sent #{PLANTED_NAMES + 2} to b", after[1])

    # SHARED fix round 7 (Claude Opus 5.5, unreviewed): the audit's LOW-1 (audits/2026-10-15-0408-quick).
    def test_a_set_back_counter_with_tmp_names_at_its_numbers_is_never_called_not_behind(self):
        """A first send to b, unread as #1; mail/.seq set back to 0 and a file planted in b's inbox at the .tmp name of each of the PLANTED_NAMES numbers from 1: the next send exits 10, names the last planted .tmp, says what it found (TMP_TAKEN_WHY) and never that mail/.seq was not behind, and lands nothing; #1 and each planted file are unchanged.

        The synthesis's case: the counter is behind (#1 is there at the
        first number it gives), but each try meets its .tmp first and
        stops before os.link, where #1 would show. Round 6's words said
        "mail/.seq was not behind" here. Must reject any claim about the
        counter that no try checked.

        @interacts  two sends; mail/.seq written by hand; PLANTED_NAMES
                    files written by hand in the inbox, read back; reads
                    #1 before and after.
        @deps       _root.TcRoot.tc; PLANTED_NAMES, PLANTED_TMP_TEXT,
                    ALL_TAKEN_WORDS, TMP_TAKEN_WHY, EXIT_BUSY.
        @complexity O(PLANTED_NAMES) files, two tc runs.
        @alloc      one TcRoot, PLANTED_NAMES small files.
        """
        with _root.TcRoot() as root:
            first = root.tc("send", "--from", "a", "--to", "b", "first")
            box = root.path / "mail" / "to-b"
            one = box / "000001-from-a.md"
            before = one.read_bytes()
            (root.path / "mail" / ".seq").write_text("0")
            planted = [box / f"{n:06d}-from-a.tmp" for n in range(1, PLANTED_NAMES + 1)]
            for path in planted:
                path.write_text(PLANTED_TMP_TEXT)
            code, out, err = root.tc("send", "--from", "a", "--to", "b", "second")
            kept = {path.read_text() for path in planted}
            after = one.read_bytes()
            unread = sorted(p.name for p in box.glob("*.md"))
        self.assertEqual(first[0], 0, first[2])
        self.assertEqual(code, EXIT_BUSY, err)
        self.assertNotIn("not behind", err, "words about mail/.seq that no try checked")
        self.assertEqual(err, ALL_TAKEN_WORDS.format(tries=PLANTED_NAMES, box=box,
                                                     last=f"{PLANTED_NAMES:06d}-from-a.tmp", why=TMP_TAKEN_WHY))
        self.assertEqual(kept, {PLANTED_TMP_TEXT}, "a send changed a planted .tmp")
        self.assertEqual(after, before, "a send changed #1")
        self.assertEqual(unread, ["000001-from-a.md"], "a refused send landed a message")

    # SHARED fix round 5 (Claude Opus 5.5, unreviewed): the audit's DEBT-1 (audits/2026-10-15-0201-quick).
    def test_a_planted_tmp_at_the_next_number_takes_the_number_after(self):
        """A first send to b, then a file planted in b's inbox at the next message's .tmp name: the next send exits 0 and lands as the number after, and the planted file is still there, unchanged byte for byte.

        A member reads the group's mail/.seq and plants the name a send
        will make its .tmp at. Must reject the old exit 1: one planted
        file refused the send, and the ssh route would file a far 1 as
        final (C3), where a taken .tmp is a taken number like any other
        (PUBLISH_MAX_TRIES, then exit 10).

        @interacts  two sends; one file written by hand in the inbox; reads
                    it back and lists the inbox.
        @deps       _root.TcRoot.tc; PLANTED_TMP_TEXT.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            first = root.tc("send", "--from", "a", "--to", "b", "first")
            box = root.path / "mail" / "to-b"
            planted = box / "000002-from-a.tmp"
            planted.write_text(PLANTED_TMP_TEXT)
            code, out, err = root.tc("send", "--from", "a", "--to", "b", "second")
            kept = planted.read_bytes()
            names = sorted(p.name for p in box.iterdir() if p.name != "read")
        self.assertEqual(first[0], 0, first[2])
        self.assertEqual(code, 0, err)
        self.assertIn("sent #3 to b", out)
        self.assertEqual(kept, PLANTED_TMP_TEXT.encode(), "the send changed the planted file")
        self.assertEqual(names, ["000001-from-a.md", "000002-from-a.tmp", "000003-from-a.md"])

    # SHARED fix round 3 (Claude Opus 5.5, unreviewed): the audit's LOW-2.
    def test_one_sends_waits_on_mail_seq_share_one_deadline(self):
        """A member holds mail/.seq just under the bound on each turn and has planted a name in read/ for every number a send could take: the send exits 10 with the lock words within LOCK_WAIT_SECONDS plus the margin, and lands nothing.

        Each number the send takes names a planted read message, so it
        tries the next, and each try waits on the member again. Must
        reject a send that gives each try a wait of its own: it gets each
        number in time and waits again, for minutes (PUBLISH_MAX_TRIES
        tries of HOLD_UNDER_BOUND_SECONDS each), with the inbox lock held.

        @interacts  one send as setup; the member's loop as a child,
                    proven to hold mail/.seq in /proc/locks; one background
                    send under a timeout; lists the inbox. The harness kills
                    both children by pid.
        @deps       _root.TcRoot.tc, start, _root.flock_holders; subprocess,
                    sys, time, running_login; SEQ_HOLDER,
                    HOLD_UNDER_BOUND_SECONDS, PLANTED_NAMES,
                    LOCK_WAIT_SECONDS, LOCK_REFUSE_MARGIN_SECONDS,
                    HELD_BY_WORDS, LET_GO_WORDS, EXIT_BUSY.
        @complexity O(1): about one LOCK_WAIT_SECONDS of waiting, at most
                    _root.LOCK_CEILING_SECONDS to prove the hold.
        @alloc      one TcRoot, two children, PLANTED_NAMES empty files.
        """
        with _root.TcRoot() as root:
            self.assertEqual(root.tc("send", "--from", "a", "--to", "b", "first")[0], 0)
            box = root.path / "mail" / "to-b"
            seq = root.path / "mail" / ".seq"
            member = root.start(argv=[sys.executable, "-c", SEQ_HOLDER, str(seq), str(box / "read"), "a",
                                      str(HOLD_UNDER_BOUND_SECONDS), str(PLANTED_NAMES)])
            proof = time.monotonic() + _root.LOCK_CEILING_SECONDS
            while member.pid not in _root.flock_holders(seq):
                if member.poll() is not None or time.monotonic() >= proof:
                    self.fail(f"the member's loop never held {seq}")
                time.sleep(_root.LOCK_POLL_SECONDS)
            ceiling = LOCK_WAIT_SECONDS + LOCK_REFUSE_MARGIN_SECONDS
            proc = root.start("send", "--from", "a", "--to", "b", "second")
            try:
                out, err = proc.communicate(timeout=ceiling)
            except subprocess.TimeoutExpired:
                self.fail(f"the send still ran {ceiling} s on: each number it skipped bought a wait of its own")
            planted = len(list((box / "read").glob("*.md")))
            unread = sorted(p.name for p in box.iterdir() if p.name != "read")
        self.assertEqual(planted, PLANTED_NAMES, "the member's loop did not plant every name")
        self.assertEqual(proc.returncode, EXIT_BUSY, err)
        # P3 fix round 1b (Claude Opus 5.5, unreviewed): D35 (3). The member lets go and takes it again on each
        # turn, so at the send's last look it holds it (named) or has just let go (said).
        self.assertIn(err, (HELD_BY_WORDS.format(what=seq, user=running_login(), pid=member.pid),
                            LET_GO_WORDS.format(what=seq, seconds=LOCK_WAIT_SECONDS)))
        self.assertEqual(unread, ["000001-from-a.md"], "a refused send left a message or a .tmp")

    # SHARED fix round 3 (Claude Opus 5.5, unreviewed): the audit's LOW-3.
    def test_a_filesystem_without_hard_links_refuses_the_send_with_words(self):
        """In process, os.link failing as it does on a filesystem without hard links (EPERM, then ENOTSUP, which is EOPNOTSUPP on Linux): deliver_local refuses, exit 1, with words saying the filesystem has no hard links and why tc needs them, and leaves no message and no .tmp.

        A filesystem without hard links cannot be made here, so link(2)'s
        answer on one is patched in. Must reject the generic `could not
        publish` words, which do not say why every send on that mailbox
        fails.

        @interacts  per errno: loads tc in process and runs deliver_local
                    with os.link replaced; lists the inbox.
        @deps       _root.TcRoot, load_tc; errno, unittest.mock;
                    tc.deliver_local; NO_HARD_LINKS_WORDS, EXIT_REFUSED.
        @complexity O(1) per errno.
        @alloc      one TcRoot and one module per errno.
        """
        for code in sorted({errno.EPERM, errno.ENOTSUP, errno.EOPNOTSUPP}):
            with self.subTest(errno=errno.errorcode[code]), _root.TcRoot() as root:
                tc = load_tc(root)

                def link(src, dst, *args, **kwargs):
                    raise OSError(code, os.strerror(code), str(dst))
                with mock.patch.object(os, "link", link):
                    got = tc.deliver_local(None, "a", "b", "hi")
                box = root.path / "mail" / "to-b"
                left = sorted(p.name for p in box.iterdir() if p.name != "read")
                self.assertEqual(got.exit, EXIT_REFUSED, got.words)
                self.assertIn(NO_HARD_LINKS_WORDS.format(root=root.path, why=os.strerror(code)), got.words)
                self.assertEqual(left, [], "a refused send left a message or a .tmp")


# SHARED fix round 6 (Claude Opus 5.5, unreviewed): D29, a member's rerun on the init user's ROOT.
def member_setup(root, name, primary_gid):
    """Share the root with group `name`, join b, send to b, post b's status, then write the member's own old message into b's read/ at PRE_D20_FILE_MODE in group `primary_gid`: (the runs, the message's path).

    The running user plays the member. The message stands for one the
    member sent b before D20: it is not right yet (0664, and, when
    `primary_gid` is not the shared group, in the wrong group), so the
    member's init has it to fix.

    @interacts  init, a join, a send and a status; writes one file by
                hand, then chowns and chmods it.
    @deps       _root.TcRoot.tc; os; OLD_OWN_MESSAGE, PRE_D20_FILE_MODE.
    @complexity O(1).
    @alloc      the list of runs, returned.
    """
    runs = [root.tc("init", "--shared", "--group", name),
            root.tc("join", "b", env={"CLAUDECODE": "1"}),
            root.tc("send", "--from", "a", "--to", "b", "hi"),
            root.tc("status", "b", "busy")]
    own = root.path / "mail" / "to-b" / "read" / OLD_OWN_MESSAGE
    own.write_text("an old message from the member to b\n")
    os.chown(own, -1, primary_gid)
    own.chmod(PRE_D20_FILE_MODE)
    return runs, own


def stat_seen(path):
    """What lstat says of `path` that any change to it would move: mode, owner, group, and its change and modify times in nanoseconds.

    @interacts  lstats `path`. Writes nothing.
    @deps       os.
    @complexity O(1).
    @alloc      one tuple, returned.
    """
    st = os.lstat(path)
    return st.st_mode, st.st_uid, st.st_gid, st.st_ctime_ns, st.st_mtime_ns


# SHARED fix round 7 (Claude Opus 5.5, unreviewed): the audit's HIGH-1 (audits/2026-10-15-0408-quick).
def folder_swap(root, primary_gid):
    """Beside b's read/, a second folder (SECOND_FOLDER), each holding a file of the running user's not right yet; outside the root, a folder of the running user's holding a folder and a file: (the two folders, the outside entries, an os.fchown that makes the swap, the list of folders it swapped).

    The synthesis's trace for HIGH-1: the walk has listed b's inbox, with
    both folders in it, and enters one of them first. On the first fchown
    of the file in that one (its fix), the other folder, listed and not
    yet entered, is renamed aside and a link to the outside folder put at
    its name, as b may do in his own inbox. A walk that then lists that
    folder by its path lists the outside folder through the link, and
    changes what is in it.

    @interacts  makes a folder in b's inbox, a file in it and in read/
                (chowned and chmodded), and a folder holding a folder and
                a file in the root's temp folder; the fchown returned,
                when called, fstats its descriptor and may rename one
                folder and make one link.
    @deps       os, pathlib; SECOND_FOLDER, SWAP_TRIGGER,
                PRE_D20_FILE_MODE, OWNER_FOLDER_MODE, FOLDER_ASIDE_SUFFIX.
    @complexity O(1).
    @alloc      the folders, files and link, removed with the temp folder;
                the list of folders swapped, returned.
    """
    box = root.path / "mail" / "to-b"
    folders = (box / "read", box / SECOND_FOLDER)
    folders[1].mkdir()
    other_of = {}
    for folder, other in zip(folders, reversed(folders)):
        trigger = folder / SWAP_TRIGGER
        trigger.write_text("a file of the running user's in b's inbox, not right yet\n")
        os.chown(trigger, -1, primary_gid)
        trigger.chmod(PRE_D20_FILE_MODE)
        other_of[os.lstat(trigger).st_ino] = other
    outside = root.base / "outside-folder"  # the running user's own, outside the mailbox
    outside.mkdir()
    (outside / "sub").mkdir()
    (outside / "notes").write_text("the running user's own notes, outside the mailbox\n")
    outside.chmod(OWNER_FOLDER_MODE)
    swapped = []
    real_fchown = os.fchown

    def fchown(fd, uid, group_id):
        other = other_of.get(os.fstat(fd).st_ino)
        if other is not None and not swapped:
            os.rename(other, other.with_name(other.name + FOLDER_ASIDE_SUFFIX))  # b's own folder, in b's own inbox
            other.symlink_to(outside, target_is_directory=True)
            swapped.append(other)
        return real_fchown(fd, uid, group_id)
    return folders, (outside, outside / "sub", outside / "notes"), fchown, swapped


class RootAndClaimTest(UmaskTestCase):
    """D21's ROOT and the audit's LOW-1: init never makes or leaves ROOT group-writable, and of two joins of one name at once only one claims the inbox.

    The audit's MEDIUM-2 and LOW-1 (audits/2026-10-14-2259-quick). One
    Linux user cannot run a second join, so the other joiner's mkdir is
    made by a patched os.mkdir, and its ownership is what a patched
    os.lstat reports. SHARED fix round 3 (Claude Opus 5.5, unreviewed):
    D23 and the audit's MEDIUM-2 and LOW-1 (audits/2026-10-14-2358-quick),
    nobody can swap ROOT: a sticky ROOT the group may write is refused
    too, and init walks every folder from ROOT up to /, as given and by
    its real path. A folder another user owns is what a patched os.lstat
    reports. SHARED fix round 4 (Claude Opus 5.5, unreviewed): the
    audit's LOW-2 (audits/2026-10-15-0102-quick): ROOT's rule runs on
    ROOT's real path even when the given walk passed it above ROOT.
    SHARED fix round 5 (Claude Opus 5.5, unreviewed): D28 and the audit's
    MEDIUM-1 (audits/2026-10-15-0201-quick): the owner of .shared gets no
    trust, so a member who made ROOT first stops the init user's init,
    and a member's rerun on the init user's ROOT is refused with no
    charge. The other user is a patched os.geteuid, and an entry of
    theirs a patched os.lstat. SHARED fix round 6 (Claude Opus 5.5,
    unreviewed): D29 and the audit's HIGH-1 (audits/2026-10-15-0300-quick).
    That refusal fixes the member's own entries through a no-follow open,
    and nothing else: the running user is the member, and ROOT and its
    .shared (and any other user's entry) are what a patched os.lstat
    reports as the init user's. A link swapped in for the member's entry,
    before init or while tc holds the entry open (a patched os.fchown
    makes the swap), leaves the link's target as it was. SHARED fix round
    7 (Claude Opus 5.5, unreviewed): the audit's HIGH-1
    (audits/2026-10-15-0408-quick). A folder on the way swapped for a
    link after the walk listed it (a patched os.fchown makes the swap,
    folder_swap) is named and never entered, in the member's rerun and in
    the init user's own init, and the folder the link leads to keeps its
    stat.

    @interacts  see the module block.
    @deps       _root.TcRoot, UmaskTestCase, primary_group, user_groups,
                tree, load_tc, run_init, owner_patched_lstat,
                member_setup, stat_seen, folder_swap, owner_patched_fstat;
                pwd, unittest.mock.
    @complexity O(1) per test.
    @alloc      one TcRoot per test.
    """

    def test_init_makes_a_missing_root_and_its_missing_parent_0755(self):
        """In process, under a login umask of 002, TC_ROOT two folders below one that exists: init exits 0, and ROOT and the folder above it are both 0755.

        Must reject a ROOT made after the shared umask (002): it comes out
        0775, and with ROOT's group the share group any member could
        rename .shared and change the group (D21). The parent catches a
        makedirs that passes 0755 for ROOT but leaves the parents to the
        umask.

        @interacts  sets this process's umask (UmaskTestCase puts it
                    back); loads tc in process pointed at a missing ROOT
                    under the root's temp folder and runs cmd_init; lstats
                    ROOT and its parent.
        @deps       _root.TcRoot, primary_group, load_tc, run_init;
                    GROUP_WRITE_UMASK, ROOT_MODE, SHARED_TOP_FOLDER_MODE.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        label, name, gid = primary_group()
        with _root.TcRoot() as root:
            target = root.base / "made" / "root"
            tc = load_tc(root, target)
            os.umask(GROUP_WRITE_UMASK)
            code, out, err = run_init(tc, name)
            modes = {str(p.relative_to(root.base)): stat.S_IMODE(os.lstat(p).st_mode)
                     for p in (target.parent, target)}
            mail = stat.S_IMODE(os.lstat(target / "mail").st_mode) if os.path.lexists(target / "mail") else None
            marker = (target / ".shared").read_text() if os.path.lexists(target / ".shared") else None
        self.assertEqual(modes, {"made": ROOT_MODE, "made/root": ROOT_MODE},
                         "init made ROOT or a folder above it group-writable")
        self.assertEqual(code, 0, err)
        self.assertEqual(mail, SHARED_TOP_FOLDER_MODE)
        self.assertEqual(marker, f"{name}\n")

    def test_a_group_writable_root_is_refused_sticky_or_not_and_nothing_changes(self):
        """ROOT set to 0775, then to 1777 (sticky), after a send: init exits 1 each time, tells ROOT's owner to run chmod g-w,o-w on it, writes no .shared, changes no entry and leaves ROOT's mode as it was.

        Must reject an init that shares a ROOT any member may write: a
        member could rename .shared or mail/ in it and put its own in
        place (D21). SHARED fix round 3 (Claude Opus 5.5, unreviewed): the
        audit's LOW-1, sticky or not: in a sticky ROOT a member could
        still make .shared or mail/ before the first init (C4).

        @interacts  a send; ROOT chmodded by hand and put back; two inits;
                    stats every entry under ROOT before and after each.
        @deps       _root.TcRoot.tc, primary_group, tree;
                    GROUP_WRITABLE_ROOT_MODE, STICKY_WORLD_WRITABLE_MODE,
                    CHMOD_WORDS.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        label, name, gid = primary_group()
        with _root.TcRoot() as root:
            root.tc("send", "--from", "a", "--to", "b", "hi")
            mode = stat.S_IMODE(os.lstat(root.path).st_mode)
            seen = {}
            try:
                for writable in (GROUP_WRITABLE_ROOT_MODE, STICKY_WORLD_WRITABLE_MODE):
                    root.path.chmod(writable)
                    before = tree(root.path, under=None)
                    refused = root.tc("init", "--shared", "--group", name)
                    seen[writable] = (refused, before, tree(root.path, under=None),
                                      stat.S_IMODE(os.lstat(root.path).st_mode))
            finally:
                root.path.chmod(mode)
        for writable, (refused, before, after, left) in seen.items():
            with self.subTest(mode=f"{writable:04o}"):
                self.assertEqual(refused[0], EXIT_REFUSED, refused[2])
                self.assertIn(CHMOD_WORDS.format(root=root.path), refused[2])
                self.assertEqual(after, before, "a refused init changed an entry")
                self.assertNotIn(".shared", after)
                self.assertEqual(left, writable, "a refused init changed ROOT's mode")

    # SHARED fix round 3 (Claude Opus 5.5, unreviewed): D23 and the audit's MEDIUM-2, nobody can swap ROOT.
    def test_a_root_under_a_group_writable_folder_is_refused_and_under_a_sticky_one_taken(self):
        """The folder above ROOT (the harness's temp folder, which the test owns) set to 0775 after a send: init exits 1 naming that folder, its mode and its owner, and changes nothing; set to 1777 (sticky, as /tmp), init exits 0.

        Must reject an init that checks ROOT alone: a member could rename
        ROOT in a folder the group may write and put a ROOT of their own,
        with their own .shared, in its place (D21, D23). And one that
        refuses a sticky folder above ROOT, where only an entry's owner
        may rename it.

        @interacts  a send; the temp folder chmodded by hand and put back;
                    two inits; stats every entry under ROOT before and
                    after; reads the user database.
        @deps       _root.TcRoot.tc, primary_group, tree; pwd;
                    GROUP_WRITABLE_ROOT_MODE, STICKY_WORLD_WRITABLE_MODE,
                    WRITABLE_ON_THE_WAY_WORDS.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        label, name, gid = primary_group()
        owner = pwd.getpwuid(os.getuid()).pw_name
        with _root.TcRoot() as root:
            root.tc("send", "--from", "a", "--to", "b", "hi")
            mode = stat.S_IMODE(os.lstat(root.base).st_mode)
            try:
                root.base.chmod(GROUP_WRITABLE_ROOT_MODE)
                before = tree(root.path, under=None)
                refused = root.tc("init", "--shared", "--group", name)
                after = tree(root.path, under=None)
                left = stat.S_IMODE(os.lstat(root.base).st_mode)
                root.base.chmod(STICKY_WORLD_WRITABLE_MODE)
                taken = root.tc("init", "--shared", "--group", name)
                shared = (root.path / ".shared").exists()
            finally:
                root.base.chmod(mode)
        self.assertEqual(refused[0], EXIT_REFUSED, refused[2])
        self.assertIn(WRITABLE_ON_THE_WAY_WORDS.format(folder=root.base, root=root.path,
                                                       mode=GROUP_WRITABLE_ROOT_MODE, owner=owner), refused[2])
        self.assertEqual(after, before, "a refused init changed an entry")
        self.assertNotIn(".shared", after)
        self.assertEqual(left, GROUP_WRITABLE_ROOT_MODE, "a refused init changed the folder above ROOT")
        self.assertEqual(taken[0], 0, taken[2])
        self.assertTrue(shared, "init refused a ROOT under a sticky folder")

    def test_a_folder_on_the_way_that_another_user_owns_is_refused_and_nothing_changes(self):
        """In process, with os.lstat reporting the folder above ROOT, or ROOT itself, as another user's: init exits 1 naming it, that user and its mode, and changes nothing.

        One Linux user cannot make a folder another user owns, so the
        owner rule is shown by what tc's lstat reports
        (owner_patched_lstat). ROOT owned by another user, with no .shared
        of theirs, is refused with these words; with their .shared in it,
        the words name them as the one who ran init (SHARED fix round 5,
        D28: test_a_member_who_made_root_first_stops_the_init_users_own_init
        and test_a_members_rerun_on_the_init_users_root_is_refused_with_no_charge_and_their_fixes).
        Must reject
        a walk that checks modes alone: the owner of a folder on the way
        may rename what is in it whatever its mode, and put a ROOT with
        their own .shared in place (D23).

        @interacts  a send; per case, loads tc in process and runs cmd_init
                    with os.lstat wrapped; stats every entry under ROOT
                    before and after.
        @deps       _root.TcRoot.tc, primary_group, load_tc, run_init,
                    owner_patched_lstat, tree; unittest.mock;
                    tc.user_name; OWNED_ON_THE_WAY_WORDS.
        @complexity O(1) per case.
        @alloc      one TcRoot and one module per case.
        """
        label, name, gid = primary_group()
        for case in ("above ROOT", "ROOT"):
            with self.subTest(case=case), _root.TcRoot() as root:
                root.tc("send", "--from", "a", "--to", "b", "hi")
                folder = root.base if case == "above ROOT" else root.path
                mode = stat.S_IMODE(os.lstat(folder).st_mode)
                tc = load_tc(root)
                other = tc.user_name(os.getuid() + 1)
                before = tree(root.path, under=None)
                with mock.patch.object(os, "lstat", owner_patched_lstat(folder)):
                    code, out, err = run_init(tc, name)
                after = tree(root.path, under=None)
                self.assertEqual(code, EXIT_REFUSED, err)
                self.assertIn(OWNED_ON_THE_WAY_WORDS.format(folder=folder, owner=other, mode=mode), err)
                self.assertEqual(after, before, "a refused init changed an entry")
                self.assertNotIn(".shared", after)

    def test_a_link_on_the_way_is_walked_as_given_and_by_its_real_path(self):
        """In process, ROOT reached through a link: a group-writable folder only on the real path, or only on the path as given, makes init exit 1 naming that folder, with nothing made in the real ROOT.

        Real path: TC_ROOT is safe/link, and link leads to team/root, with
        team at 0775. As given: TC_ROOT is team/link, with team at 0775,
        and link leads to safe/root. Must reject a walk of one path only:
        either way a member could swap ROOT through the folder the other
        walk never sees (D23: "a link on the way is checked too").

        @interacts  per case, folders and one link made by hand under the
                    root's temp folder, one folder chmodded to 0775; loads
                    tc in process pointed at the link and runs cmd_init;
                    lists the real ROOT.
        @deps       _root.TcRoot, primary_group, load_tc, run_init; pwd;
                    GROUP_WRITABLE_ROOT_MODE, WRITABLE_ON_THE_WAY_WORDS.
        @complexity O(1) per case.
        @alloc      one TcRoot and one module per case.
        """
        label, name, gid = primary_group()
        owner = pwd.getpwuid(os.getuid()).pw_name
        for case in ("real path", "as given"):
            with self.subTest(case=case), _root.TcRoot() as root:
                team, safe = root.base / "team", root.base / "safe"
                team.mkdir()
                safe.mkdir()
                team.chmod(GROUP_WRITABLE_ROOT_MODE)
                real, given = (team, safe) if case == "real path" else (safe, team)
                (real / "root").mkdir()
                (given / "link").symlink_to(real / "root")
                tc = load_tc(root, given / "link")
                code, out, err = run_init(tc, name)
                made = sorted(p.name for p in (real / "root").iterdir())
                self.assertEqual(code, EXIT_REFUSED, err)
                self.assertIn(WRITABLE_ON_THE_WAY_WORDS.format(folder=team, root=given / "link",
                                                               mode=GROUP_WRITABLE_ROOT_MODE, owner=owner), err)
                self.assertEqual(made, [], "a refused init made something in the real ROOT")

    # SHARED fix round 5 (Claude Opus 5.5, unreviewed): D28 and the audit's MEDIUM-1 (audits/2026-10-15-0201-quick).
    def test_a_member_who_made_root_first_stops_the_init_users_own_init(self):
        """In process: a member makes ROOT and, in it, a 0644 .shared naming the group, before anyone else (this user, by hand); the init user's first init (os.geteuid reporting another user) exits 1 with words naming the member as the one who ran init, with no charge, finds no entry of its own to fix, and makes nothing.

        The bugs-reviewer's trace: round 4's walk trusted whoever owned
        .shared, and whoever makes ROOT can make that .shared, so this
        init passed and exited 0 on a mailbox whose group only the member
        can change (D21). Must reject a walk that trusts the owner of
        .shared (D28): the init then exits 0 and makes the four top
        folders. One Linux user cannot be two, so the member is this
        user, who owns ROOT and .shared, and the init user is os.geteuid
        reporting this user's id plus one.

        @interacts  writes and chmods .shared by hand; loads tc in process
                    and runs cmd_init with os.geteuid replaced; stats every
                    entry under ROOT before and after.
        @deps       _root.TcRoot, primary_group, load_tc, run_init, tree;
                    unittest.mock; tc.user_name; SHARED_MARKER_MODE,
                    RAN_INIT_WORDS, FIXES_OWN_WORDS, NO_FIX_WORDS.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        label, name, gid = primary_group()
        with _root.TcRoot() as root:
            marker = root.path / ".shared"
            marker.write_text(f"{name}\n")
            marker.chmod(SHARED_MARKER_MODE)
            tc = load_tc(root)
            member = tc.user_name(os.getuid())
            before = tree(root.path, under=None)
            with mock.patch.object(os, "geteuid", return_value=os.getuid() + 1):
                code, out, err = run_init(tc, name)
            after = tree(root.path, under=None)
        self.assertEqual(code, EXIT_REFUSED, err)
        self.assertEqual(err, f"{RAN_INIT_WORDS.format(root=root.path, owner=member)}{FIXES_OWN_WORDS}\n"
                              f"{NO_FIX_WORDS}\n")
        self.assertEqual(after, before, "the init user's init made something in the member's ROOT")

    # SHARED fix round 6 (Claude Opus 5.5, unreviewed): D29 and the audit's HIGH-1 (audits/2026-10-15-0300-quick).
    def test_a_members_rerun_on_the_init_users_root_fixes_only_their_own_entries_through_the_fd(self):
        """In process, the running user as a member, lstat reporting ROOT, .shared, b's inbox and b's status as another user's: the member's same-group rerun exits 1 with words naming the init user, with no charge; the member's own 0664 message in b's read/ is then 0640 in the group, through fchown and fchmod on its descriptor (no chmod or chown by path), with one line for it; b's inbox and status, set wrong by hand, and every other entry are as they were. With .shared read as naming no group (it changed after init read it), nothing changes.

        C4 with D29 (dev contracts.md at 463074c): tc fixes the member's
        own entries itself through an open, no-follow descriptor, changes
        nothing else and prints what it fixed. Must reject round 5's
        lines to paste, a change by path, a change to another user's
        entry, and a change toward a group .shared no longer names.
        Shares with the supplementary group when the user has one and
        puts the message in the primary group, so the group change shows;
        with one group the mode change carries the test.

        @interacts  per case: init, a join, a send, a status; one file
                    written, chowned and chmodded by hand, and two entries
                    chmodded; loads tc in process and runs cmd_init with
                    os.lstat and os.fstat wrapped (and shared_group
                    replaced in the second case), and os.chmod, os.chown,
                    os.lchown, os.fchown and os.fchmod wrapped to count
                    calls; stats every entry under ROOT before and after.
        @deps       member_setup, user_groups, load_tc, run_init, tree,
                    owner_patched_lstat, owner_patched_fstat; contextlib,
                    unittest.mock;
                    tc.user_name, tc.shared_group; RAN_INIT_WORDS,
                    FIXES_OWN_WORDS, FIXED_WORDS, FIXED_COUNT_WORDS,
                    NOTHING_CHANGED_WORDS, PRIVATE_FILE_MODE,
                    SHARED_FOLDER_MODE, SHARED_OWNED_FILE_MODE.
        @complexity O(1) per case, two cases.
        @alloc      one TcRoot and one module per case.
        """
        found = user_groups()
        (_, _, primary_gid), (_, name, gid) = found[0], found[-1]
        changes = ("chmod", "chown", "lchown", "fchown", "fchmod")
        for case in ("as init read it", ".shared changed since"):
            with self.subTest(case=case):
                with _root.TcRoot() as root:
                    setup, own = member_setup(root, name, primary_gid)
                    box, status = root.path / "mail" / "to-b", root.path / "status" / "b.md"
                    box.chmod(SHARED_FOLDER_MODE)  # b's inbox from before D20: b's to fix, not the member's
                    status.chmod(PRIVATE_FILE_MODE)
                    tc = load_tc(root)
                    init_user = tc.user_name(os.getuid() + 1)
                    before = tree(root.path, under=None)
                    with contextlib.ExitStack() as stack:
                        stack.enter_context(mock.patch.object(os, "lstat", owner_patched_lstat(
                            root.path, root.path / ".shared", box, status)))
                        stack.enter_context(mock.patch.object(os, "fstat", owner_patched_fstat(root.path)))  # round 8: pin_root
                        counted = {fn: stack.enter_context(mock.patch.object(os, fn, wraps=getattr(os, fn)))
                                   for fn in changes}
                        if case != "as init read it":
                            stack.enter_context(mock.patch.object(tc, "shared_group", return_value=None))
                        code, out, err = run_init(tc, name)
                    after = tree(root.path, under=None)
                    calls = {fn: counted[fn].call_count for fn in changes}
                for run in setup:
                    self.assertEqual(run[0], 0, run[2])
                self.assertEqual(code, EXIT_REFUSED, err)
                words = RAN_INIT_WORDS.format(root=root.path, owner=init_user)
                mine = str(own.relative_to(root.path))
                if case == "as init read it":
                    self.assertEqual(err, f"{words}{FIXES_OWN_WORDS}\n"
                                          f"{FIXED_WORDS.format(path=own, group=name, mode=SHARED_OWNED_FILE_MODE)}\n"
                                          f"{FIXED_COUNT_WORDS.format(fixed=1, skipped=0)}\n")
                    self.assertEqual(before.pop(mine), ("file", PRE_D20_FILE_MODE, primary_gid))
                    self.assertEqual(after.pop(mine), ("file", SHARED_OWNED_FILE_MODE, gid),
                                     "the member's own message was not fixed")
                    self.assertEqual(calls, {"chmod": 0, "chown": 0, "lchown": 0, "fchown": 1, "fchmod": 1},
                                     "a change went by path, or past the member's one entry")
                else:
                    self.assertEqual(err, f"{words}{NOTHING_CHANGED_WORDS}\n")
                    self.assertEqual(calls, dict.fromkeys(changes, 0), "a change toward a group .shared no longer names")
                self.assertEqual(after, before, "an entry that is not the member's own changed")

    # SHARED fix round 6 (Claude Opus 5.5, unreviewed): D29, Ben's swap (a2 for the owner).
    def test_a_link_swapped_in_for_a_members_entry_leaves_its_target_untouched(self):
        """In process, the running user as a member, lstat reporting ROOT and .shared as the init user's: the member's own 0664 message in b's read/ is put aside and a link to a folder this test owns, outside the root, put at its name, either before the member's rerun or while tc holds the message open (a patched os.fchown makes the swap first). Either way that folder's mode, owner, group and times are as they were. Before: tc says it skipped a link, and fixes the message at its new name. While open: the message, now aside, is 0640 in the group, changed through its descriptor.

        Ben's swap (D29): b renames the member's old message aside in his
        read/ and links a folder of the member's at its name. Round 5's
        pasted chmod line followed that link (the audit's HIGH-1). Must
        reject a change by path anywhere after tc looked at the entry: a
        chmod or chown by path follows the link swapped in and changes
        the folder; and an open that follows a link.

        @interacts  per case: init, a join, a send, a status; one file
                    written, chowned and chmodded by hand; a folder made
                    outside the root; a rename and a symlink (by hand, or
                    by the patched os.fchown); loads tc in process and runs
                    cmd_init with os.lstat, os.fstat and os.fchown
                    wrapped; lstats the folder, the link and the message
                    after.
        @deps       member_setup, stat_seen, user_groups, load_tc,
                    run_init, owner_patched_lstat, owner_patched_fstat;
                    unittest.mock; tc.user_name; RAN_INIT_WORDS, FIXES_OWN_WORDS,
                    FIXED_WORDS, SKIPPED_WORDS, SKIPPED_LINK_WHY,
                    FIXED_COUNT_WORDS, OWNER_FOLDER_MODE, ASIDE_NAME,
                    SHARED_OWNED_FILE_MODE.
        @complexity O(1) per case, two cases.
        @alloc      one TcRoot and one module per case.
        """
        found = user_groups()
        (_, _, primary_gid), (_, name, gid) = found[0], found[-1]
        for case in ("before init", "while tc holds it open"):
            with self.subTest(case=case):
                with _root.TcRoot() as root:
                    setup, own = member_setup(root, name, primary_gid)
                    home = root.base / "member-home"  # a folder of the member's, outside the mailbox
                    home.mkdir()
                    home.chmod(OWNER_FOLDER_MODE)
                    aside = own.with_name(ASIDE_NAME)
                    inode = os.lstat(own).st_ino
                    swapped = []

                    def swap():
                        os.rename(own, aside)  # b may rename anything in his sticky read/
                        own.symlink_to(home, target_is_directory=True)
                        swapped.append(own)
                    if case == "before init":
                        swap()
                    real_fchown = os.fchown

                    def fchown(fd, uid, group_id):
                        if not swapped and os.fstat(fd).st_ino == inode:
                            swap()  # b's swap, after tc opened and checked the message, before it changed it
                        return real_fchown(fd, uid, group_id)
                    seen = stat_seen(home)
                    tc = load_tc(root)
                    init_user = tc.user_name(os.getuid() + 1)
                    with mock.patch.object(os, "lstat", owner_patched_lstat(root.path, root.path / ".shared")), \
                            mock.patch.object(os, "fstat", owner_patched_fstat(root.path)), \
                            mock.patch.object(os, "fchown", fchown):
                        code, out, err = run_init(tc, name)
                    after = stat_seen(home)
                    linked = os.readlink(own) if os.path.islink(own) else None
                    moved = os.lstat(aside)
                for run in setup:
                    self.assertEqual(run[0], 0, run[2])
                self.assertEqual(swapped, [own], "the swap never happened")
                self.assertEqual(after, seen, "a change followed the link into the member's own folder")
                self.assertEqual(linked, str(home), "the link was replaced")
                self.assertEqual((stat.S_IMODE(moved.st_mode), moved.st_gid), (SHARED_OWNED_FILE_MODE, gid),
                                 "the member's message was not fixed through its descriptor")
                self.assertEqual(code, EXIT_REFUSED, err)
                lines = err.splitlines()
                self.assertEqual(lines[0], f"{RAN_INIT_WORDS.format(root=root.path, owner=init_user)}{FIXES_OWN_WORDS}")
                if case == "before init":
                    self.assertEqual(sorted(lines[1:-1]), sorted([
                        SKIPPED_WORDS.format(path=own, why=SKIPPED_LINK_WHY),
                        FIXED_WORDS.format(path=aside, group=name, mode=SHARED_OWNED_FILE_MODE)]))
                    self.assertEqual(lines[-1], FIXED_COUNT_WORDS.format(fixed=1, skipped=1))
                else:
                    self.assertEqual(lines[1:], [FIXED_WORDS.format(path=own, group=name, mode=SHARED_OWNED_FILE_MODE),
                                                 FIXED_COUNT_WORDS.format(fixed=1, skipped=0)])

    # SHARED fix round 6 (Claude Opus 5.5, unreviewed): D29, fstat on the descriptor decides, not the lstat before it.
    def test_an_entry_another_user_owns_at_its_open_is_skipped_and_never_changed(self):
        """In process: this user shares the root (the init user), b joins, a send, a status set to 0644 by hand; a member's same-group rerun (os.geteuid reporting another user, os.lstat reporting the status file as that member's) exits 1 with words naming the init user, says it skipped the status file as another user's, and changes nothing.

        lstat says the status file is the member's; fstat on the open
        descriptor says it is the init user's, as when an entry is
        swapped for another user's between tc's lstat and its open. Must
        reject a change that trusts the lstat: the fchown and fchmod then
        go through (this process may change the file) and set it 0640.

        @interacts  init, a join, a send, a status; one chmod by hand;
                    loads tc in process and runs cmd_init with os.geteuid
                    and os.lstat replaced; stats every entry under ROOT
                    before and after.
        @deps       _root.TcRoot.tc, primary_group, load_tc, run_init,
                    owner_patched_lstat, tree; unittest.mock; tc.user_name;
                    PRIVATE_FILE_MODE, RAN_INIT_WORDS, FIXES_OWN_WORDS,
                    SKIPPED_WORDS, NOT_YOURS_WHY, FIXED_COUNT_WORDS.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        label, name, gid = primary_group()
        with _root.TcRoot() as root:
            setup = [root.tc("init", "--shared", "--group", name),
                     root.tc("join", "b", env={"CLAUDECODE": "1"}),
                     root.tc("send", "--from", "a", "--to", "b", "hi"),
                     root.tc("status", "b", "busy")]
            status = root.path / "status" / "b.md"
            status.chmod(PRIVATE_FILE_MODE)  # the member's by lstat, not right yet
            tc = load_tc(root)
            init_user = tc.user_name(os.getuid())
            before = tree(root.path, under=None)
            with mock.patch.object(os, "geteuid", return_value=os.getuid() + 1), \
                    mock.patch.object(os, "lstat", owner_patched_lstat(status)):
                code, out, err = run_init(tc, name)
            after = tree(root.path, under=None)
        for run in setup:
            self.assertEqual(run[0], 0, run[2])
        self.assertEqual(code, EXIT_REFUSED, err)
        self.assertEqual(err, f"{RAN_INIT_WORDS.format(root=root.path, owner=init_user)}{FIXES_OWN_WORDS}\n"
                              f"{SKIPPED_WORDS.format(path=status, why=NOT_YOURS_WHY.format(owner=init_user))}\n"
                              f"{FIXED_COUNT_WORDS.format(fixed=0, skipped=1)}\n")
        self.assertEqual(after, before, "a change went to an entry another user owns at its open")

    # SHARED fix round 7 (Claude Opus 5.5, unreviewed): the audit's HIGH-1 (audits/2026-10-15-0408-quick).
    def test_a_folder_swapped_for_a_link_on_the_way_never_leads_a_members_rerun_outside(self):
        """In process, the running user as a member, lstat reporting ROOT, .shared, b's inbox and the two folders in it as another user's: when the member's rerun fixes the file in the folder it enters first, the other folder, listed and not yet entered, is put aside and a link to a folder of the member's outside the root put at its name (folder_swap). That folder, the folder and the file in it keep their mode, owner, group and times; tc names the swapped folder as not entered, fixes the one file, and ends 1 fixed and 1 skipped.

        The synthesis's trace for HIGH-1: O_NOFOLLOW guards only the last
        name of a path, and os.walk lists a folder by its path after it
        checked it for a link, so the member's own init changed the
        member's own folders and files at the far end, outside the
        mailbox. Must reject a walk that lists or opens any folder below
        the four by its path (os.walk back in walk_pinned).

        @interacts  init, a join, a send, a status; folder_swap's folders,
                    files and swap; loads tc in process and runs cmd_init
                    with os.lstat, os.fstat and os.fchown wrapped; lstats
                    the outside entries and the file fixed.
        @deps       folder_swap, stat_seen, user_groups, load_tc, run_init,
                    owner_patched_lstat, owner_patched_fstat; unittest.mock;
                    tc.user_name;
                    RAN_INIT_WORDS, FIXES_OWN_WORDS, FIXED_WORDS,
                    SKIPPED_WORDS, NOT_ENTERED_WHY, FIXED_COUNT_WORDS,
                    SWAP_TRIGGER, SHARED_OWNED_FILE_MODE.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        found = user_groups()
        (_, _, primary_gid), (_, name, gid) = found[0], found[-1]
        with _root.TcRoot() as root:
            setup = [root.tc("init", "--shared", "--group", name),
                     root.tc("join", "b", env={"CLAUDECODE": "1"}),
                     root.tc("send", "--from", "a", "--to", "b", "hi"),
                     root.tc("status", "b", "busy")]
            folders, outside, fchown, swapped = folder_swap(root, primary_gid)
            box = root.path / "mail" / "to-b"
            seen = [stat_seen(path) for path in outside]
            tc = load_tc(root)
            init_user = tc.user_name(os.getuid() + 1)
            with mock.patch.object(os, "lstat", owner_patched_lstat(root.path, root.path / ".shared", box, *folders)), \
                    mock.patch.object(os, "fstat", owner_patched_fstat(root.path)), \
                    mock.patch.object(os, "fchown", fchown):
                code, out, err = run_init(tc, name)
            after = [stat_seen(path) for path in outside]
            entered = [folder for folder in folders if folder not in swapped]
            fixed = [os.lstat(folder / SWAP_TRIGGER) for folder in entered]
        for run in setup:
            self.assertEqual(run[0], 0, run[2])
        self.assertEqual(len(swapped), 1, "the swap never happened")
        self.assertEqual(after, seen, "the walk went through the swapped link and changed a folder outside the root")
        self.assertEqual(code, EXIT_REFUSED, err)
        self.assertEqual(err, f"{RAN_INIT_WORDS.format(root=root.path, owner=init_user)}{FIXES_OWN_WORDS}\n"
                              f"{FIXED_WORDS.format(path=entered[0] / SWAP_TRIGGER, group=name, mode=SHARED_OWNED_FILE_MODE)}\n"
                              f"{SKIPPED_WORDS.format(path=swapped[0], why=NOT_ENTERED_WHY)}\n"
                              f"{FIXED_COUNT_WORDS.format(fixed=1, skipped=1)}\n")
        self.assertEqual([(stat.S_IMODE(st.st_mode), st.st_gid) for st in fixed], [(SHARED_OWNED_FILE_MODE, gid)],
                         "the file in the folder entered first was not fixed")

    # SHARED fix round 7 (Claude Opus 5.5, unreviewed): the audit's HIGH-1, init's own walk (audits/2026-10-15-0408-quick).
    def test_a_folder_swapped_for_a_link_on_the_way_never_leads_the_init_users_own_init_outside(self):
        """In process, the running user as the init user, whose init passes the walk: when init's own walk fixes the file in the folder of b's inbox it enters first, the other folder is put aside and a link to a folder of the init user's outside the root put at its name (folder_swap). That folder, the folder and the file in it keep their mode, owner, group and times; init names the swapped folder as not entered, fixes the one file, shares the rest, and exits 1.

        Init's own walk (shared_entries) had the member walk's shape since
        round 1 (the synthesis's HIGH-1): os.walk listed the swapped
        folder by its path and changed the init user's own folder and
        file at the far end. Must reject os.walk back in walk_pinned.

        @interacts  init, a join, a send, a status; folder_swap's folders,
                    files and swap; loads tc in process and runs cmd_init
                    with os.fchown wrapped; lstats the outside entries and
                    the file fixed.
        @deps       folder_swap, stat_seen, user_groups, load_tc,
                    run_init; unittest.mock; SKIPPED_WORDS,
                    NOT_ENTERED_WHY, SKIPPED_BY_HAND_WORDS, SWAP_TRIGGER,
                    SHARED_OWNED_FILE_MODE.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        found = user_groups()
        (_, _, primary_gid), (_, name, gid) = found[0], found[-1]
        with _root.TcRoot() as root:
            setup = [root.tc("init", "--shared", "--group", name),
                     root.tc("join", "b", env={"CLAUDECODE": "1"}),
                     root.tc("send", "--from", "a", "--to", "b", "hi"),
                     root.tc("status", "b", "busy")]
            folders, outside, fchown, swapped = folder_swap(root, primary_gid)
            seen = [stat_seen(path) for path in outside]
            tc = load_tc(root)
            with mock.patch.object(os, "fchown", fchown):
                code, out, err = run_init(tc, name)
            after = [stat_seen(path) for path in outside]
            entered = [folder for folder in folders if folder not in swapped]
            fixed = [os.lstat(folder / SWAP_TRIGGER) for folder in entered]
        for run in setup:
            self.assertEqual(run[0], 0, run[2])
        self.assertEqual(len(swapped), 1, "the swap never happened")
        self.assertEqual(after, seen, "the walk went through the swapped link and changed a folder outside the root")
        self.assertEqual(code, EXIT_REFUSED, err)
        self.assertEqual(err, f"{SKIPPED_WORDS.format(path=swapped[0], why=NOT_ENTERED_WHY)}\n"
                              f"{SKIPPED_BY_HAND_WORDS.format(n=1)}\n")
        self.assertEqual([(stat.S_IMODE(st.st_mode), st.st_gid) for st in fixed], [(SHARED_OWNED_FILE_MODE, gid)],
                         "the file in the folder entered first was not fixed")

    # SHARED fix round 4 (Claude Opus 5.5, unreviewed): the audit's LOW-2.
    def test_a_root_that_links_to_its_own_folder_still_gets_the_root_rule(self):
        """In process, TC_ROOT tc/here where here is a link to . (so ROOT's real path is tc, which the path as given passes as a folder above ROOT), and tc at 1777: init exits 1 with ROOT's chmod words and makes nothing in tc.

        Must reject a walk that marks an entry looked at by its path
        alone: the given walk passes tc above ROOT by the sticky
        exception, the real walk then skips it, and a sticky ROOT the
        group may write is shared (C4: ROOT has no sticky exception).

        @interacts  one folder and one link made by hand under the root's
                    temp folder, the folder chmodded to 1777; loads tc in
                    process pointed at the link and runs cmd_init; lists
                    the folder.
        @deps       _root.TcRoot, primary_group, load_tc, run_init;
                    STICKY_WORLD_WRITABLE_MODE, CHMOD_WORDS.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        label, name, gid = primary_group()
        with _root.TcRoot() as root:
            folder = root.base / "tc"
            folder.mkdir()
            (folder / "here").symlink_to(".")
            folder.chmod(STICKY_WORLD_WRITABLE_MODE)
            tc = load_tc(root, folder / "here")
            code, out, err = run_init(tc, name)
            made = sorted(p.name for p in folder.iterdir())
        self.assertEqual(code, EXIT_REFUSED, err)
        self.assertIn(f"is {STICKY_WORLD_WRITABLE_MODE:04o}: its group or anyone may write it", err)
        self.assertIn(CHMOD_WORDS.format(root=folder / "here"), err)
        self.assertEqual(made, ["here"], "a refused init made something in the real ROOT")

    def test_of_two_joins_of_one_name_at_once_the_loser_is_refused_and_makes_nothing(self):
        """In process, shared: another joiner's mkdir of mail/to-x lands just before this join's (patched os.mkdir), and lstat reports it as that user's: claim_inbox exits 1 with the taken words and makes no read/ inside it.

        Must reject a claim that takes the other joiner's inbox as made
        (make_folder accepts a folder another process just made) and goes
        on to make read/ in it: the inbox and its read/ would have two
        owners, and every send, read and wait for x would be refused.

        @interacts  init; loads tc in process and runs claim_inbox with
                    os.mkdir and os.lstat wrapped and stderr captured.
        @deps       _root.TcRoot.tc, primary_group, load_tc,
                    owner_patched_lstat; contextlib, errno, io,
                    unittest.mock; tc.claim_inbox.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        label, name, gid = primary_group()
        with _root.TcRoot() as root:
            self.assertEqual(root.tc("init", "--shared", "--group", name)[0], 0)
            box = root.path / "mail" / "to-x"
            tc = load_tc(root)
            real_mkdir, raced = os.mkdir, []

            def mkdir(path, *args, **kwargs):
                if pathlib.Path(path) == box and not raced:
                    raced.append(path)
                    real_mkdir(path, *args, **kwargs)  # the other joiner's, a moment first
                    raise FileExistsError(errno.EEXIST, os.strerror(errno.EEXIST), str(path))
                return real_mkdir(path, *args, **kwargs)
            said = io.StringIO()
            with mock.patch.object(os, "mkdir", mkdir), \
                    mock.patch.object(os, "lstat", owner_patched_lstat(box)), contextlib.redirect_stderr(said):
                with self.assertRaises(SystemExit) as stop:
                    tc.claim_inbox("x")
            inside = sorted(p.name for p in box.iterdir())
        self.assertEqual(raced, [box], "the other joiner's mkdir never ran")
        self.assertEqual(stop.exception.code, EXIT_REFUSED)
        self.assertIn(TAKEN_INBOX_WORDS, said.getvalue())
        self.assertEqual(inside, [], "the losing join made read/ inside the other joiner's inbox")


# SHARED fix round 8 (Claude Opus 5.5, unreviewed): the audit's MEDIUM-1, LOW-1 and LOW-2 (audits/2026-10-15-0840-quick).
@contextlib.contextmanager
def as_member(root_path, *others):
    """While entered, the running user plays a member on the init user's ROOT: os.lstat reports ROOT, its .shared and each of `others` as another user's (owner_patched_lstat), and os.fstat reports ROOT so (owner_patched_fstat).

    @interacts  patches os.lstat and os.fstat while entered.
    @deps       owner_patched_lstat, owner_patched_fstat; unittest.mock,
                os.
    @complexity O(1).
    @alloc      the patches, undone on exit.
    """
    with mock.patch.object(os, "lstat", owner_patched_lstat(root_path, root_path / ".shared", *others)), \
            mock.patch.object(os, "fstat", owner_patched_fstat(root_path)):
        yield


# One os.open call as open_spy records it: what it was asked to open, whether
# lstat found a link at that name just before, its flags, and whether it
# returned a descriptor.
OpenSeen = collections.namedtuple("OpenSeen", "path dir_fd was_link flags opened")


def open_spy(seen):
    """An os.open that records each call in `seen` (OpenSeen) and then opens as os.open does.

    The link test lstats the name first, by the same path and dir_fd,
    with the real os.lstat, so a call that names a link is known whatever
    its flags.

    @interacts  none until called; then lstats and opens what it is asked
                to, and appends to `seen`.
    @deps       os, stat; OpenSeen.
    @complexity O(1) per call.
    @alloc      one OpenSeen per call, kept in `seen`.
    """
    real_open, real_lstat = os.open, os.lstat

    def spy(path, flags, mode=0o777, *, dir_fd=None):
        try:
            was_link = stat.S_ISLNK(real_lstat(path, dir_fd=dir_fd).st_mode)
        except OSError:
            was_link = False
        try:
            fd = real_open(path, flags, mode, dir_fd=dir_fd)
        except OSError:
            seen.append(OpenSeen(path, dir_fd, was_link, flags, False))
            raise
        seen.append(OpenSeen(path, dir_fd, was_link, flags, True))
        return fd
    return spy


class InitWalkTest(UmaskTestCase):
    """Round 8: init's own stack walk under the four, in both walks (the init user's own init and a member's rerun on the init user's ROOT).

    The audit's MEDIUM-1 (audits/2026-10-15-0840-quick): os.fwalk recursed
    one frame per folder level, so a deep nest any member may make ended
    every init in a RecursionError traceback; tc's own walk has a stack
    and enters at most WALK_MAX_DEPTH folders deep, and names the folder
    past it. LOW-1: a top this user may list but not search is named,
    never a traceback. LOW-2: os.fwalk opened a link's target before it
    compared; tc's walk never opens a link (an os.open spy). The member
    is the running user, with ROOT and its .shared reported as the init
    user's (as_member).

    @interacts  see the module block.
    @deps       _root.TcRoot, UmaskTestCase, user_groups, primary_group,
                load_tc, run_init, as_member, open_spy, stat_seen.
    @complexity O(1) per test: a handful of tc runs over a root of a few
                dozen entries.
    @alloc      one TcRoot per test and walk.
    """

    def test_a_nest_past_walk_max_depth_is_named_and_never_a_traceback(self):
        """A nest of NEST_FOLDER folders under status/, WALK_MAX_DEPTH + 1 of them, made by hand: in the init user's own init and in a member's rerun, init names the folder WALK_MAX_DEPTH + 1 deep (counting status/ as one) with TOO_DEEP_WHY, exits 1 with its usual last line, and never looks under it; the init user's init writes .shared and shares every folder down to it.

        os.fwalk recursed one generator frame per level, so a nest about
        1000 deep ended every init in a RecursionError traceback, exit 1,
        before .shared was written (the audit's MEDIUM-1). The nest here
        is short, so the run stays quick: a walk with no depth cap enters
        the named folder, changes the one under it and names nothing, and
        this test goes red. Must reject a walk without its cap.

        @interacts  per walk: a status post (and, for the member, init
                    first); the nest made by hand; loads tc in process
                    and runs cmd_init (as_member for the member); lstats
                    the nest and reads .shared.
        @deps       _root.TcRoot.tc, user_groups, load_tc, run_init,
                    as_member, stat_seen; RAN_INIT_WORDS, FIXES_OWN_WORDS,
                    FIXED_WORDS, SKIPPED_WORDS, TOO_DEEP_WHY,
                    FIXED_COUNT_WORDS, SKIPPED_BY_HAND_WORDS,
                    SHARED_FOLDER_MODE, NEST_FOLDER, WALK_MAX_DEPTH,
                    CHILD_UMASK.
        @complexity O(WALK_MAX_DEPTH) per walk, two walks.
        @alloc      one TcRoot and one module per walk.
        """
        found = user_groups()
        _, name, gid = found[-1]
        for walk in ("the init user's own init", "a member's rerun"):
            os.umask(CHILD_UMASK)  # an in-process init before this one set its own
            with self.subTest(walk=walk), _root.TcRoot() as root:
                if walk == "a member's rerun":
                    self.assertEqual(root.tc("init", "--shared", "--group", name)[0], 0)
                self.assertEqual(root.tc("status", "b", "busy")[0], 0)
                status = root.path / "status"
                nest = [status.joinpath(*[NEST_FOLDER] * k) for k in range(1, WALK_MAX_DEPTH + 2)]
                nest[-1].mkdir(parents=True)
                deep, under = nest[-2], nest[-1]  # WALK_MAX_DEPTH + 1 deep, counting status/, and the one below
                untouched = stat_seen(under)
                tc = load_tc(root)
                if walk == "a member's rerun":
                    init_user = tc.user_name(os.getuid() + 1)
                    with as_member(root.path):
                        code, out, err = run_init(tc, name)
                else:
                    code, out, err = run_init(tc, name)
                walked = [(stat.S_IMODE(os.lstat(p).st_mode), os.lstat(p).st_gid) for p in nest[:-1]]
                left = stat_seen(under)
                marker = (root.path / ".shared").read_text()
                self.assertEqual(code, EXIT_REFUSED, err)
                skip = SKIPPED_WORDS.format(path=deep, why=TOO_DEEP_WHY)
                if walk == "a member's rerun":
                    fixes = "".join(f"{FIXED_WORDS.format(path=p, group=name, mode=SHARED_FOLDER_MODE)}\n"
                                    for p in nest[:-1])
                    self.assertEqual(err, f"{RAN_INIT_WORDS.format(root=root.path, owner=init_user)}{FIXES_OWN_WORDS}\n"
                                          f"{fixes}{skip}\n"
                                          f"{FIXED_COUNT_WORDS.format(fixed=WALK_MAX_DEPTH, skipped=1)}\n")
                else:
                    self.assertEqual(err, f"{skip}\n{SKIPPED_BY_HAND_WORDS.format(n=1)}\n")
                self.assertEqual(walked, [(SHARED_FOLDER_MODE, gid)] * WALK_MAX_DEPTH,
                                 "a folder down to the cap was not shared")
                self.assertEqual(left, untouched, "the walk looked under the folder past its cap")
                self.assertEqual(marker, f"{name}\n")

    def test_a_top_this_user_may_list_but_not_search_is_named_never_a_traceback(self):
        """A member's rerun on the init user's ROOT, status/ (the init user's, by lstat) set to READ_NO_SEARCH_MODE with b's status file in it: init names status/ with NO_SEARCH_WHY, fixes nothing, and exits 1 with the count line.

        os.fwalk resolved "." from the top's descriptor outside any try,
        which needs search, so this run ended in a PermissionError
        traceback (the audit's LOW-1). Only the member's rerun can meet
        it: the init user's own walk fixes the top before it lists it.
        Must reject a traceback and a walk that names nothing. Skipped
        as root, who searches any folder.

        @interacts  init and a status post; status/ chmodded by hand and
                    put back; loads tc in process and runs cmd_init
                    (as_member).
        @deps       _root.TcRoot.tc, primary_group, load_tc, run_init,
                    as_member; RAN_INIT_WORDS, FIXES_OWN_WORDS,
                    SKIPPED_WORDS, NO_SEARCH_WHY, FIXED_COUNT_WORDS,
                    READ_NO_SEARCH_MODE.
        @complexity O(1).
        @alloc      one TcRoot and one module.
        """
        if os.geteuid() == 0:
            self.skipTest("root searches any folder")
        label, name, gid = primary_group()
        with _root.TcRoot() as root:
            setup = [root.tc("init", "--shared", "--group", name), root.tc("status", "b", "busy")]
            status = root.path / "status"
            mode = stat.S_IMODE(os.lstat(status).st_mode)
            tc = load_tc(root)
            init_user = tc.user_name(os.getuid() + 1)
            try:
                status.chmod(READ_NO_SEARCH_MODE)
                with as_member(root.path, status):
                    code, out, err = run_init(tc, name)
            finally:
                status.chmod(mode)
        for run in setup:
            self.assertEqual(run[0], 0, run[2])
        self.assertEqual(code, EXIT_REFUSED, err)
        self.assertEqual(err, f"{RAN_INIT_WORDS.format(root=root.path, owner=init_user)}{FIXES_OWN_WORDS}\n"
                              f"{SKIPPED_WORDS.format(path=status, why=NO_SEARCH_WHY)}\n"
                              f"{FIXED_COUNT_WORDS.format(fixed=0, skipped=1)}\n")

    def test_no_link_is_ever_opened_by_either_walk(self):
        """Links to a folder and to a file outside the root, planted in b's inbox, its read/ and status/: in the init user's own init and in a member's rerun, an os.open spy finds no call that named a link and returned a descriptor, every call that named one carried O_NOFOLLOW, init names each link, and what they lead to keeps its stat.

        os.fwalk took a link to a folder into its folders (DirEntry.is_dir
        follows), then opened the name without O_NOFOLLOW before it
        compared, on every init (the audit's LOW-2): an open can act on a
        device or an automount path. Must reject any open that follows a
        link.

        @interacts  per walk: init, a join, a send, a status; a folder, a
                    file and three links made by hand; loads tc in process
                    and runs cmd_init with os.open spied (and as_member
                    for the member); lstats the link targets.
        @deps       _root.TcRoot.tc, primary_group, load_tc, run_init,
                    as_member, open_spy, stat_seen; SKIPPED_WORDS,
                    SKIPPED_LINK_WHY, CHILD_UMASK.
        @complexity O(1) per walk, two walks.
        @alloc      one TcRoot and one module per walk.
        """
        label, name, gid = primary_group()
        for walk in ("the init user's own init", "a member's rerun"):
            os.umask(CHILD_UMASK)  # an in-process init before this one set its own
            with self.subTest(walk=walk), _root.TcRoot() as root:
                setup = [root.tc("init", "--shared", "--group", name),
                         root.tc("join", "b", env={"CLAUDECODE": "1"}),
                         root.tc("send", "--from", "a", "--to", "b", "hi"),
                         root.tc("status", "b", "busy")]
                folder, file = root.base / "outside-folder", root.base / "outside-file"
                folder.mkdir()
                (folder / "notes").write_text("the running user's own notes, outside the mailbox\n")
                file.write_text("the running user's own file, outside the mailbox\n")
                box = root.path / "mail" / "to-b"
                links = {box / "linked-file": file, box / "read" / "linked-folder": folder,
                         root.path / "status" / "linked-folder": folder}
                for link, target in links.items():
                    link.symlink_to(target, target_is_directory=target.is_dir())
                targets = [folder, folder / "notes", file]
                seen_before = [stat_seen(p) for p in targets]
                tc = load_tc(root)
                calls = []
                with mock.patch.object(os, "open", open_spy(calls)):
                    if walk == "a member's rerun":
                        with as_member(root.path):
                            code, out, err = run_init(tc, name)
                    else:
                        code, out, err = run_init(tc, name)
                seen_after = [stat_seen(p) for p in targets]
                for run in setup:
                    self.assertEqual(run[0], 0, run[2])
                at_links = [call for call in calls if call.was_link]
                self.assertTrue(at_links, "no open named a link: the test reached none")
                self.assertEqual([call for call in at_links if call.opened], [], "an open followed a link")
                self.assertEqual([call for call in at_links if not call.flags & os.O_NOFOLLOW], [],
                                 "an open named a link without O_NOFOLLOW")
                for link in links:
                    self.assertIn(SKIPPED_WORDS.format(path=link, why=SKIPPED_LINK_WHY), err)
                self.assertEqual(code, EXIT_REFUSED, err)
                self.assertEqual(seen_after, seen_before, "a link's target changed")


# SHARED fix round 8 (Claude Opus 5.5, unreviewed): the audit's HIGH-1 and LOW-3 (audits/2026-10-15-0840-quick).
def build_mailbox(at):
    """Make the mailbox SWAP_LAYOUT names at `at`, by hand: ROOT at ROOT_MODE, every folder under it at OWNER_FOLDER_MODE, every file at OWNER_FILE_MODE.

    @interacts  makes `at` and its missing parents, then each folder and
                file of SWAP_LAYOUT, and chmods each.
    @deps       pathlib; SWAP_LAYOUT, ROOT_MODE, OWNER_FOLDER_MODE,
                OWNER_FILE_MODE.
    @complexity O(e) over e entries of SWAP_LAYOUT (thirteen).
    @alloc      the folders and files, removed with the root's temp
                folder.
    """
    at.mkdir(parents=True)
    at.chmod(ROOT_MODE)
    for rel, text in SWAP_LAYOUT:
        path = at / rel
        if text is None:
            path.mkdir()
            path.chmod(OWNER_FOLDER_MODE)
        else:
            path.write_text(text)
            path.chmod(OWNER_FILE_MODE)


def tree_seen(top, lstat=os.lstat):
    """What lstat says of `top` and of every entry under it that any change would move: {path relative to `top`: (mode, owner, group, change and modify times in ns)}.

    `lstat` is the real os.lstat, bound when this module loads, so a
    patch in place while it runs (as_member) never colors what it sees.
    A link is never followed; a file is the one entry ".".

    @interacts  lstats `top` and, when it is a folder, lists every folder
                under it (os.walk) and lstats each entry. Writes nothing.
    @deps       os, pathlib, stat.
    @complexity O(e) over e entries under `top` (a dozen or so).
    @alloc      one dict, returned.
    """
    def seen(path):
        st = lstat(path)
        return st.st_mode, st.st_uid, st.st_gid, st.st_ctime_ns, st.st_mtime_ns
    out = {".": seen(top)}
    if stat.S_ISDIR(lstat(top).st_mode):
        for folder, folders, files in os.walk(top):
            for name in folders + files:
                path = pathlib.Path(folder) / name
                out[str(path.relative_to(top))] = seen(path)
    return out


def swap_on_open(trigger, exact, swap):
    """An os.open that, the first time it is aimed at `trigger` (or, unless `exact`, at anything under it), calls `swap` first and then opens as os.open does: (that os.open, the list of what it was aimed at when it swapped).

    Where a call is aimed: by its path, the real path; by a name in a
    folder's descriptor, that folder's path now (/proc/self/fd) and the
    name. `trigger` is taken by its real path when this is made, before
    anything is swapped.

    @interacts  none until called; then reads /proc/self/fd or resolves
                the path, may call `swap` once, and opens what it is
                asked to.
    @deps       os, pathlib.
    @complexity O(1) per call.
    @alloc      one list, holding at most one path.
    """
    real_open = os.open
    target = pathlib.Path(os.path.realpath(trigger))
    made = []

    def aimed_open(path, flags, mode=0o777, *, dir_fd=None):
        if not made:
            aimed = (pathlib.Path(os.readlink(f"/proc/self/fd/{dir_fd}")) / path if dir_fd is not None
                     else pathlib.Path(os.path.realpath(path)))
            if aimed == target or (not exact and target in aimed.parents):
                made.append(aimed)
                swap()
        return real_open(path, flags, mode, dir_fd=dir_fd)
    return aimed_open, made


# What run_swap returns: init's exit code and words, what the swap hook was
# aimed at, the far end of the swap as seen before and after, ROOT's own
# entries before and after (wherever the original ROOT is by then), the
# text of .shared there (None when there is none), and the login of the
# user who ran init (a member's rerun).
SwapRun = collections.namedtuple("SwapRun", "code out err made far_before far_after mine_before mine_after marker "
                                            "init_user")


def run_swap(root, walk, group, rel, kind, moment):
    """Build a mailbox at SWAP_PARENT/SWAP_ROOT and its two mirrors under the root's temp folder, then run init in process for `walk` while the point `rel` is swapped for `kind` at `moment`: a SwapRun.

    The point is renamed aside (its name plus FOLDER_ASIDE_SUFFIX), and in
    its place goes a link to the same point in the OUTSIDE_TREE mirror
    ("link"), or the same point of the OTHER_TREE mirror, moved in ("real
    folder"). The far end, which a walk led by the swap would change, is
    that mirror's point: seen before the run for a link, and just after
    the move for a real folder. The swap is made by an os.open wrapped
    with swap_on_open: AT_ROOT_OPEN, as init opens ROOT itself; MID_WALK,
    for ROOT and its parent at the first open under mail/to-b, else at
    the first open aimed at the point (the walk's open of a top, or
    share_entry's of a folder or the entry, just after the walk's lstat
    of it). A member's rerun writes .shared by hand and runs as_member.

    @interacts  makes three mailboxes by hand and, for a member, .shared;
                loads tc in process pointed at the mailbox and runs
                cmd_init with os.open wrapped (and as_member); the wrap
                renames the point and makes a link or moves a folder;
                lstats the far end and the mailbox before and after.
    @deps       build_mailbox, tree_seen, swap_on_open, as_member,
                load_tc, run_init, SwapRun; contextlib, os, pathlib,
                unittest.mock; SWAP_PARENT, SWAP_ROOT, OUTSIDE_TREE,
                OTHER_TREE, FOLDER_ASIDE_SUFFIX, SHARED_MARKER_MODE,
                AT_ROOT_OPEN.
    @complexity O(e) over e entries of SWAP_LAYOUT, three times, plus
                init's walk.
    @alloc      the mailboxes and the link, removed with the root's temp
                folder; one module; one SwapRun, returned.
    """
    base = root.base
    mailbox = base / SWAP_PARENT / SWAP_ROOT
    for tree in (base, base / OUTSIDE_TREE, base / OTHER_TREE):
        build_mailbox(tree / SWAP_PARENT / SWAP_ROOT)
    if walk == "a member's rerun":
        marker = mailbox / ".shared"
        marker.write_text(f"{group}\n")
        marker.chmod(SHARED_MARKER_MODE)
    point = base / rel
    aside = point.with_name(point.name + FOLDER_ASIDE_SUFFIX)
    far = base / OUTSIDE_TREE / rel if kind == "link" else point
    seen = {"far": tree_seen(far) if kind == "link" else None}

    def swap():
        os.rename(point, aside)
        if kind == "link":
            point.symlink_to(far, target_is_directory=far.is_dir())
        else:
            os.rename(base / OTHER_TREE / rel, point)
            seen["far"] = tree_seen(point)
    above = len(rel.parts) <= len((SWAP_PARENT, SWAP_ROOT))
    trigger = (mailbox if moment == AT_ROOT_OPEN else mailbox / "mail" / "to-b" if above else point)
    aimed_open, made = swap_on_open(trigger, moment == AT_ROOT_OPEN, swap)
    pinned = (base / f"{SWAP_PARENT}{FOLDER_ASIDE_SUFFIX}" / SWAP_ROOT if rel == pathlib.Path(SWAP_PARENT)
              else aside if rel == pathlib.Path(SWAP_PARENT, SWAP_ROOT) else mailbox)
    mine_before = tree_seen(mailbox)
    tc = load_tc(root, mailbox)
    with contextlib.ExitStack() as stack:
        if walk == "a member's rerun":
            stack.enter_context(as_member(mailbox))
        stack.enter_context(mock.patch.object(os, "open", aimed_open))
        code, out, err = run_init(tc, group)
    marker = (pinned / ".shared").read_text() if os.path.lexists(pinned / ".shared") else None
    return SwapRun(code, out, err, made, seen["far"], tree_seen(far), mine_before, tree_seen(pinned), marker,
                   tc.user_name(os.getuid() + 1))


class RootPinnedTest(UmaskTestCase):
    """Round 8: after init's walk judged ROOT, no name on the write path is resolved again, in both walks (the init user's own init and a member's rerun on the init user's ROOT), and a hard-linked file is never changed.

    The audit's HIGH-1 (audits/2026-10-15-0840-quick): rounds 5, 6 and 7
    each pinned one level of the write path; round 7 still opened the four
    by their paths under ROOT, so the init user could swap ROOT for a link
    after a member's walk passed it, and the member's own init changed the
    member's own folders elsewhere. Now init opens ROOT once, checks it
    against the folder its walk judged, and opens every name from there
    down in its own folder's descriptor. The swap test swaps every point
    on the write path, one per subtest. LOW-3: a file hard-linked into the
    mailbox is skipped and named. The member is the running user, with
    ROOT and its .shared reported as the init user's (as_member).

    @interacts  see the module block.
    @deps       _root.TcRoot, UmaskTestCase, user_groups, primary_group,
                run_swap, load_tc, run_init, as_member, stat_seen.
    @complexity O(p) over p points and kinds of swap (forty-two subtests,
                each a hand-built mailbox of a dozen entries); O(1) for
                the hard-link test.
    @alloc      one TcRoot per subtest.
    """

    def test_a_swap_at_any_point_on_the_write_path_never_leads_either_walk_outside(self):
        """For each point on init's write path (ROOT's parent, ROOT, each of the four, mail/to-b and its read/, and the entry in it), swapped in the middle of either walk for a link to a folder outside the mailbox or for another real folder (the entry for a link only): what the swap leads to keeps its mode, owner, group and times, and init names what it refused or skipped.

        The audit's HIGH-1 and its REC-4: with ROOT swapped while mail/'s
        walk runs, round 7 opened status/ by its path through the swap and
        changed the far end's folders and files. Per point: ROOT or its
        parent swapped as init opens ROOT is refused with
        ROOT_CHANGED_WORDS and nothing changes; swapped while mail/'s walk
        runs, the walk carries on in the ROOT it opened, and its words
        and .shared are as on an untouched mailbox; a top swapped before
        its open is named as not entered; mail/to-b or its read/ swapped
        after its lstat is named twice, at its own change (a link, or
        changed) and as not entered; the entry swapped for a link is named
        as a link. Must reject any name on the write path resolved by its
        path after the walk judged ROOT: with the four opened by path
        (round 7) the far end of a ROOT or parent swapped while mail/'s
        walk runs changes.

        @interacts  per subtest: run_swap's.
        @deps       run_swap, user_groups, _root.TcRoot; pathlib;
                    SWAP_PARENT, SWAP_ROOT, SHARED_FOLDER_NAMES,
                    OLD_OWN_MESSAGE, AT_ROOT_OPEN, MID_WALK, CHILD_UMASK,
                    RAN_INIT_WORDS, ROOT_CHANGED_WORDS, FIXED_COUNT_WORDS,
                    SKIPPED_WORDS, NOT_ENTERED_WHY, SKIPPED_LINK_WHY,
                    CHANGED_WHY, SWAP_LAYOUT.
        @complexity O(p) over p points, kinds and moments (twenty-one per
                    walk, two walks).
        @alloc      one TcRoot per subtest.
        """
        found = user_groups()
        _, name, gid = found[-1]
        mailbox = pathlib.Path(SWAP_PARENT, SWAP_ROOT)
        points = [pathlib.Path(SWAP_PARENT), mailbox, *[mailbox / top for top in SHARED_FOLDER_NAMES],
                  mailbox / "mail" / "to-b", mailbox / "mail" / "to-b" / "read",
                  mailbox / "mail" / "to-b" / "read" / OLD_OWN_MESSAGE]
        for walk in ("the init user's own init", "a member's rerun"):
            for rel in points:
                entry, above = rel.name == OLD_OWN_MESSAGE, len(rel.parts) <= len(mailbox.parts)
                for kind in ("link",) if entry else ("link", "real folder"):
                    for moment in (AT_ROOT_OPEN, MID_WALK) if above else (MID_WALK,):
                        os.umask(CHILD_UMASK)  # an in-process init before this one set its own
                        with self.subTest(walk=walk, point=str(rel), kind=kind, moment=moment), \
                                _root.TcRoot() as root:
                            run = run_swap(root, walk, name, rel, kind, moment)
                            point, root_path = root.base / rel, root.base / mailbox
                        member = walk == "a member's rerun"
                        lines = run.err.splitlines()
                        with self.subTest(walk=walk, point=str(rel), kind=kind, moment=moment):
                            self.assertTrue(run.made, "the swap never happened")
                            self.assertEqual(run.far_after, run.far_before,
                                             "a change reached the far end of the swap, outside the mailbox")
                            if moment == AT_ROOT_OPEN:
                                lead = f"{RAN_INIT_WORDS.format(root=root_path, owner=run.init_user)} " if member else "tc init: "
                                self.assertEqual(run.err, f"{lead}{ROOT_CHANGED_WORDS.format(root=root_path)}\n")
                                self.assertEqual(run.code, EXIT_REFUSED)
                                self.assertEqual({k: v for k, v in run.mine_after.items() if k != "."},
                                                 {k: v for k, v in run.mine_before.items() if k != "."},
                                                 "a refused init changed the mailbox")
                            elif above and member:
                                self.assertEqual(run.code, EXIT_REFUSED, run.err)
                                self.assertEqual([line for line in lines if line.startswith("tc init: skipped")], [])
                                self.assertEqual(lines[-1], FIXED_COUNT_WORDS.format(fixed=len(SWAP_LAYOUT), skipped=0))
                            elif above:
                                self.assertEqual((run.code, run.err), (0, ""))
                                self.assertEqual(run.marker, f"{name}\n", ".shared was not written in the ROOT init opened")
                            elif entry:
                                self.assertEqual(run.code, EXIT_REFUSED, run.err)
                                self.assertIn(SKIPPED_WORDS.format(path=point, why=SKIPPED_LINK_WHY), lines)
                            else:
                                self.assertEqual(run.code, EXIT_REFUSED, run.err)
                                self.assertIn(SKIPPED_WORDS.format(path=point, why=NOT_ENTERED_WHY), lines)
                                if len(rel.parts) > len(mailbox.parts) + 1:  # mail/to-b and its read/: their own change too
                                    why = SKIPPED_LINK_WHY if kind == "link" else CHANGED_WHY
                                    self.assertIn(SKIPPED_WORDS.format(path=point, why=why), lines)

    def test_a_hard_linked_file_is_skipped_and_named_and_unchanged_at_both_names(self):
        """b's status file, set to 0644 by hand, with a second name outside the root (a hard link): in the init user's own init and in a member's rerun, init names it with HARD_LINK_WHY and its stat is the same at both names, before and after.

        The audit's LOW-3: share_entry checked the kind and the owner but
        not st_nlink, so a file hard-linked into the mailbox got group g
        and 0640, and the change showed at its outside name. Must reject a
        change to a regular file with more than one name.

        @interacts  per walk: init, a join, a send, a status; one chmod
                    and one hard link by hand; loads tc in process and
                    runs cmd_init (as_member for the member); lstats both
                    names.
        @deps       _root.TcRoot.tc, primary_group, load_tc, run_init,
                    as_member, stat_seen; os; PRIVATE_FILE_MODE,
                    RAN_INIT_WORDS, FIXES_OWN_WORDS, SKIPPED_WORDS,
                    HARD_LINK_WHY, FIXED_COUNT_WORDS, SKIPPED_BY_HAND_WORDS,
                    CHILD_UMASK.
        @complexity O(1) per walk, two walks.
        @alloc      one TcRoot and one module per walk.
        """
        label, name, gid = primary_group()
        for walk in ("the init user's own init", "a member's rerun"):
            os.umask(CHILD_UMASK)  # an in-process init before this one set its own
            with self.subTest(walk=walk), _root.TcRoot() as root:
                setup = [root.tc("init", "--shared", "--group", name),
                         root.tc("join", "b", env={"CLAUDECODE": "1"}),
                         root.tc("send", "--from", "a", "--to", "b", "hi"),
                         root.tc("status", "b", "busy")]
                status = root.path / "status" / "b.md"
                status.chmod(PRIVATE_FILE_MODE)  # not right yet, so init would change it
                elsewhere = root.base / "outside-name"
                os.link(status, elsewhere)
                before = [stat_seen(status), stat_seen(elsewhere)]
                tc = load_tc(root)
                if walk == "a member's rerun":
                    init_user = tc.user_name(os.getuid() + 1)
                    with as_member(root.path):
                        code, out, err = run_init(tc, name)
                else:
                    code, out, err = run_init(tc, name)
                after = [stat_seen(status), stat_seen(elsewhere)]
                for run in setup:
                    self.assertEqual(run[0], 0, run[2])
                skip = SKIPPED_WORDS.format(path=status, why=HARD_LINK_WHY)
                self.assertEqual(code, EXIT_REFUSED, err)
                if walk == "a member's rerun":
                    self.assertEqual(err, f"{RAN_INIT_WORDS.format(root=root.path, owner=init_user)}{FIXES_OWN_WORDS}\n"
                                          f"{skip}\n{FIXED_COUNT_WORDS.format(fixed=0, skipped=1)}\n")
                else:
                    self.assertEqual(err, f"{skip}\n{SKIPPED_BY_HAND_WORDS.format(n=1)}\n")
                self.assertEqual(after, before, "a hard-linked file changed")


class HealthSaysWhatItCannotSeeTest(UmaskTestCase):
    """tc health never gives a silent 0 for an inbox it cannot see into, never dies on one, and never says `mailbox private` over an unreadable .shared.

    The audit's LOW-2 and LOW-4 (audits/2026-10-14-2259-quick), and one
    item from BOARD's review. One user stands in for a member by taking
    access away from an inbox it owns. Skipped as root, who reads
    anything.

    @interacts  see the module block.
    @deps       _root.TcRoot, UmaskTestCase, load_tc; argparse,
                contextlib, io, json.
    @complexity O(1) per test.
    @alloc      one TcRoot per test.
    """

    def health_with_inbox_mode(self, mode):
        """Mail for b and c, then mail/to-b set to `mode`: (tc health --json, tc health), with to-b's mode put back after.

        @interacts  two sends; one chmod by hand and back; two tc health
                    runs.
        @deps       _root.TcRoot.tc; OWNER_FOLDER_MODE.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            for name in ("b", "c"):
                root.tc("send", "--from", "a", "--to", name, REAL_TEXT)
            box = root.path / "mail" / "to-b"
            box.chmod(mode)
            try:
                return root.tc("health", "--json"), root.tc("health")
            finally:
                box.chmod(OWNER_FOLDER_MODE)

    def test_an_inbox_tc_cannot_list_is_unknown_with_the_reason_never_0(self):
        """mail/to-b at no access: tc health --json gives b unread null and a reason, c still 1; tc health says `unread unknown` for b.

        Must reject a count from a listing that gave up in silence (b
        would read 0 unread, as a 3770 inbox does for a board run outside
        the group). P3 fix round 1c (Claude Opus 5.5, unreviewed): round
        1a's note. The listing guarded is message_files' listing of the
        inbox in its open descriptor (open_inbox), no longer pathlib's
        glob of its path.

        @interacts  see health_with_inbox_mode.
        @deps       health_with_inbox_mode; json; NO_ACCESS_MODE,
                    UNKNOWN_WORDS.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        if os.geteuid() == 0:
            self.skipTest("root lists any folder")
        (code, out, err), (text_code, text, text_err) = self.health_with_inbox_mode(NO_ACCESS_MODE)
        self.assertEqual(code, 0, err)
        mail = json.loads(out)["mail"]
        self.assertIsNone(mail["b"]["unread"], "tc health counted an inbox it could not list")
        self.assertIn("could not list", mail["b"]["mail_problem"])
        self.assertIn(os.strerror(errno.EACCES), mail["b"]["mail_problem"])
        self.assertEqual((mail["c"]["unread"], mail["c"]["mail_problem"]), (1, None))
        self.assertEqual(text_code, 0, text_err)
        self.assertIn(f"b: {UNKNOWN_WORDS}", text)

    def test_an_inbox_readable_without_search_leaves_health_answering(self):
        """mail/to-b readable without search (each lstat in it is refused): tc health --json and tc health exit 0, and b's count is unknown with the reason.

        From BOARD's review: an owner who gives their inbox group read
        without group search makes every look inside it raise
        PermissionError for every member, and tc health (and the board's
        feed) died with a traceback. Must reject a look that catches only
        FileNotFoundError. P3 fix round 1c (Claude Opus 5.5, unreviewed):
        round 1a's note. The looks guarded are the open of read/ by its
        name in the inbox's descriptor (open_inbox, pin_folder) and
        message_files' stat of each name in the open inbox, no longer an
        lstat of each path.

        @interacts  see health_with_inbox_mode.
        @deps       health_with_inbox_mode; json; READ_NO_SEARCH_MODE,
                    UNKNOWN_WORDS.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        if os.geteuid() == 0:
            self.skipTest("root searches any folder")
        (code, out, err), (text_code, text, text_err) = self.health_with_inbox_mode(READ_NO_SEARCH_MODE)
        self.assertEqual(code, 0, err)
        mail = json.loads(out)["mail"]
        self.assertIsNone(mail["b"]["unread"], "tc health counted an inbox whose entries it could not look at")
        self.assertIn("could not look at", mail["b"]["mail_problem"])
        self.assertEqual(mail["c"]["unread"], 1)
        self.assertEqual(text_code, 0, text_err)
        self.assertIn(f"b: {UNKNOWN_WORDS}", text)

    def test_health_words_say_the_shared_problem_never_private(self):
        """In process, .shared of two lines (as if it turned unreadable after main() read it): cmd_health's last line names the problem and never says `mailbox private`.

        Must reject a last line that reads only shared_group, which is
        null here (LOW-4).

        @interacts  writes .shared by hand; loads tc in process and runs
                    cmd_health with stdout captured (reads /proc).
        @deps       _root.TcRoot, load_tc; argparse, contextlib, io;
                    tc.cmd_health; GROUP_UNKNOWN_WORDS.
        @complexity O(p) over p processes on the machine (hundreds).
        @alloc      one TcRoot and one module.
        """
        with _root.TcRoot() as root:
            (root.path / ".shared").write_text("one\ntwo\n")
            tc = load_tc(root)
            with contextlib.redirect_stdout(io.StringIO()) as printed:
                tc.cmd_health(argparse.Namespace(json=False))
        last = printed.getvalue().splitlines()[-1]
        self.assertNotEqual(last, "mailbox private", "tc health called a shared mailbox private")
        self.assertTrue(last.startswith(GROUP_UNKNOWN_WORDS), last)
        self.assertIn("names no group", last)


# SHARED fix round 3 (Claude Opus 5.5, unreviewed): the synthesis's note on check_inbox, and REC-1.
class CommandsSayWhatTheyCannotSeeTest(UmaskTestCase):
    """send, read, peek, wait and log never die with a traceback, or say 0 or `mailbox empty`, for an inbox they cannot see into.

    audits/2026-10-14-2358-quick (the synthesis's coverage note on
    check_inbox, and REC-1), and for log a read/ it cannot look at
    (SHARED fix round 4, Claude Opus 5.5, unreviewed: LOW-4 of
    audits/2026-10-15-0102-quick). One user stands in for a member by
    taking access away from an inbox it owns. Skipped as root, who
    searches and lists any folder. P3 fix round 1c (Claude Opus 5.5,
    unreviewed): round 1a's note. Since round 1a (D35) the guard these
    tests hold is the pinned inbox, not check_inbox or an lstat of each
    path: pinned_inbox opens the inbox and its read/ once, by name, and
    refuse_bad_inbox refuses what it cannot open or look at, with
    check_inbox's words; message_files lists and stats each name in the
    open folder. check_inbox now serves tc join's claim_inbox alone.

    @interacts  see the module block.
    @deps       _root.TcRoot, UmaskTestCase; errno, os.
    @complexity O(1) per test.
    @alloc      one TcRoot per test.
    """

    def test_an_inbox_without_search_stops_send_read_peek_and_wait_with_words(self):
        """mail/to-b readable without search, so its read/ cannot be looked at: a send to b, tc read b, tc peek b and tc wait b each exit 1 with words naming read/, never a traceback; nothing lands or moves, and mail/.seq is unchanged.

        Must reject a look at read/ that catches only FileNotFoundError:
        each of the four dies with PermissionError. P3 fix round 1c
        (Claude Opus 5.5, unreviewed): round 1a's note. That look is the
        open of read/ by its name in the open inbox (pinned_inbox), whose
        refusal (refuse_bad_inbox) keeps check_inbox's words; it was
        check_inbox's lstat before round 1a.

        @interacts  one send; mail/to-b chmodded by hand and back; four tc
                    runs; lists the inbox and reads mail/.seq.
        @deps       _root.TcRoot.tc; errno, os; READ_NO_SEARCH_MODE,
                    OWNER_FOLDER_MODE, ONE_POLL_SECONDS, REAL_TEXT,
                    CANNOT_LOOK_WORDS, EXIT_REFUSED.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        if os.geteuid() == 0:
            self.skipTest("root searches any folder")
        commands = (["send", "--from", "c", "--to", "b", "hi"], ["read", "b"], ["peek", "b"],
                    ["wait", "b", "--timeout", ONE_POLL_SECONDS])
        with _root.TcRoot() as root:
            root.tc("send", "--from", "a", "--to", "b", REAL_TEXT)
            box = root.path / "mail" / "to-b"
            seq = (root.path / "mail" / ".seq").read_text()
            box.chmod(READ_NO_SEARCH_MODE)
            try:
                runs = {argv[0]: root.tc(*argv) for argv in commands}
            finally:
                box.chmod(OWNER_FOLDER_MODE)
            mail = sorted(str(p.relative_to(box)) for p in box.rglob("*.md"))
            seq_after = (root.path / "mail" / ".seq").read_text()
        for command, (code, out, err) in runs.items():
            with self.subTest(command=command):
                self.assertEqual(code, EXIT_REFUSED, err)
                self.assertIn(CANNOT_LOOK_WORDS.format(path=box / "read", why=os.strerror(errno.EACCES)), err)
                self.assertNotIn("Traceback", err)
        self.assertEqual(mail, ["000001-from-a.md"], "a message landed or moved")
        self.assertEqual(seq_after, seq, "a refused send took a number")

    def test_an_inbox_tc_cannot_list_is_said_by_peek_read_wait_and_log_never_0_or_empty(self):
        """mail/to-b searchable but not readable, its one message unread: tc peek b, tc read b, tc wait b and tc log each exit 1 and say tc could not list it, with the reason; none says `0 unread`, `no unread mail`, TIMEOUT or `mailbox empty`, and nothing moves.

        The audit's REC-1. Must reject inbox_messages and cmd_log dropping
        message_files' problem: peek prints `0 unread for b`, read `no
        unread mail for b`, wait times out, and log says `mailbox empty`,
        all exit 0, over mail that is there.

        @interacts  one send; mail/to-b chmodded by hand and back; four tc
                    runs; lists the inbox.
        @deps       _root.TcRoot.tc; errno, os; SEARCH_NO_READ_MODE,
                    OWNER_FOLDER_MODE, ONE_POLL_SECONDS, REAL_TEXT,
                    CANNOT_LIST_WORDS, SILENT_WORDS, EXIT_REFUSED.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        if os.geteuid() == 0:
            self.skipTest("root lists any folder")
        commands = (["peek", "b"], ["read", "b"], ["wait", "b", "--timeout", ONE_POLL_SECONDS], ["log"])
        with _root.TcRoot() as root:
            root.tc("send", "--from", "a", "--to", "b", REAL_TEXT)
            box = root.path / "mail" / "to-b"
            box.chmod(SEARCH_NO_READ_MODE)
            try:
                runs = {argv[0]: root.tc(*argv) for argv in commands}
            finally:
                box.chmod(OWNER_FOLDER_MODE)
            mail = sorted(str(p.relative_to(box)) for p in box.rglob("*.md"))
        for command, (code, out, err) in runs.items():
            with self.subTest(command=command):
                self.assertEqual(code, EXIT_REFUSED, err)
                self.assertIn(CANNOT_LIST_WORDS.format(path=box, why=os.strerror(errno.EACCES)), err)
                for silent in SILENT_WORDS:
                    self.assertNotIn(silent, out, f"tc {command} said {silent!r} over an inbox it could not list")
        self.assertEqual(mail, ["000001-from-a.md"], "a message moved")

    # SHARED fix round 4 (Claude Opus 5.5, unreviewed): the audit's LOW-4.
    def test_log_says_it_could_not_look_at_a_read_folder_never_mailbox_empty(self):
        """b has read its one message, then mail/to-b is set readable without search, so tc cannot reach its read/: tc log exits 1, says it could not look at mail/to-b/read, with the reason, and never says `mailbox empty`.

        Must reject a log that drops a read/ it cannot reach without a
        word (round 4's real_folder and os.path.islink both answered False
        on the error): it prints `mailbox empty` and exits 0 while read/
        holds the history. P3 fix round 1c (Claude Opus 5.5, unreviewed):
        round 1a's note. Since round 1a the reach guarded is the open of
        read/ by its name in the open inbox (cmd_log, open_inbox); both
        functions named above are gone.

        @interacts  one send and one read; mail/to-b chmodded by hand and
                    back; one tc log.
        @deps       _root.TcRoot.tc; errno, os; READ_NO_SEARCH_MODE,
                    OWNER_FOLDER_MODE, REAL_TEXT, LOG_CANNOT_LOOK_WORDS,
                    EXIT_REFUSED.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        if os.geteuid() == 0:
            self.skipTest("root searches any folder")
        with _root.TcRoot() as root:
            runs = [root.tc("send", "--from", "a", "--to", "b", REAL_TEXT), root.tc("read", "b")]
            box = root.path / "mail" / "to-b"
            box.chmod(READ_NO_SEARCH_MODE)
            try:
                code, out, err = root.tc("log")
            finally:
                box.chmod(OWNER_FOLDER_MODE)
        for run in runs:
            self.assertEqual(run[0], 0, run[2])
        self.assertEqual(code, EXIT_REFUSED, err)
        self.assertIn(LOG_CANNOT_LOOK_WORDS.format(path=box / "read", why=os.strerror(errno.EACCES)), err)
        self.assertNotIn("mailbox empty", out, "tc log said the mailbox is empty while read/ holds the history")


# SHARED fix round 1 (Claude Opus 5.5, unreviewed): the audit's LOW-1.
class GroupsToTestTest(UmaskTestCase):
    """groups_to_test() never lets the supplementary run vanish silently.

    @interacts  see the module block.
    @deps       UmaskTestCase, groups_to_test; contextlib, unittest.mock.
    @complexity O(1).
    @alloc      one mock.
    """

    def test_a_missing_supplementary_group_is_a_skip_with_a_reason(self):
        """With os.getgroups() reporting the primary group alone: groups_to_test returns it alone and skips the supplementary subtest with NO_SUPPLEMENTARY_REASON.

        Must reject a helper that returns the primary group with no skip
        (the supplementary subtest would vanish, LOW-1).

        @interacts  calls groups_to_test with a mock case and os.getgroups
                    patched; reads the group database.
        @deps       groups_to_test; contextlib, unittest.mock.
        @complexity O(1).
        @alloc      one mock.
        """
        case = mock.Mock()
        case.subTest.return_value = contextlib.nullcontext()
        with mock.patch.object(os, "getgroups", return_value=[os.getegid()]):
            found = groups_to_test(case)
        self.assertEqual([label for label, name, gid in found], ["primary"])
        case.skipTest.assert_called_once_with(NO_SUPPLEMENTARY_REASON)


if __name__ == "__main__":
    unittest.main()
