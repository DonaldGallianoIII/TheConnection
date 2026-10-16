# no-follow-open-guards-only-the-last-name

Model:  Claude Opus 5.5 (the TheConnection architect session), 2026-10-15
Status: unreviewed

**What:** code checks a path (lstat, a walk's listing) and then acts on
it by name: opens it, writes or hard-links a file into it, lists it,
renames files in it, chmods it, chowns it, or descends into it.
`O_NOFOLLOW` and `os.walk`'s link check guard only the last name in the
path. Any folder earlier in the path can still be swapped for a link
between the check and the act, by anyone allowed to rename that folder's
entry: any writer of the folder holding it, or, under a sticky bit, the
entry's own owner and the holding folder's owner. The sticky bit stops
other users; it never stops the entry's owner. The
act then lands at the far end of the link, outside the tree the code
meant to touch.

**How it showed:** SHARED's review rounds 5, 6 and 7, 2026-10-15, each
closed one level and the next re-review found the next one out. Round 5
printed `chgrp` and `chmod` lines for a member to paste; both commands
follow a link, and the entry's folder belonged to another user (fixed by
D29: tc changes the member's own entries itself through an open,
no-follow file). Round 6's walk then found those entries with `os.walk`
by path, so a folder below one of the four shared folders could be
swapped mid-walk. Round 7's `os.fwalk` pinned the folders below the four
but opened the four themselves by path under ROOT, so the init user
could swap ROOT during a member's rerun; its recursion also turned a
deep folder nest into a traceback in every init. Round 8 closed the
mechanism, not the next level: init opens ROOT once, checks with
`fstat` that it is the folder its walk judged, and reaches every name
below through an open folder (its own stack walk, `WALK_MAX_DEPTH` 8,
no link ever opened), and never changes a file with a second name. A
member's own folders outside the mailbox were the target each time.
A fourth time in the P3 phase review, 2026-10-15, on the live inbox
paths, not init. The inbox check lstatted a member's inbox and kept no
descriptor; send and the far gate then made the message by path, peek,
read and log listed, read and renamed by path, and health, the unread
count and flush's count listed by path. The inbox's owner, a member,
could rename its own inbox in the sticky, group-writable `mail/` and put
a link at its name; the counter's lock wait between the check and the
write held the window open. On a scratch copy a send exited 0 and named
a path the message was not at.

**Why it's bad:** a member's own init, run to fix that member's own
entries, changes the group and mode of that member's files outside the
mailbox (a home folder, a script folder on their PATH), at another
member's choosing. That is past D20's worst case, a failed send. On the
inbox paths (the fourth hit), a member's message is written outside the
mailbox while the sender is told it landed, and another member's `tc
log` or `tc peek` prints files from outside the mailbox: a read past the
group.

**Prevention:** after the check, never resolve a name again. Open the
top once, confirm by identity (`st_dev` and `st_ino`) that it is what
the check judged, then reach every name below by `dir_fd` on an open
folder, enter a folder only when `fstat` finds what `lstat` found, and
act on the open file (`fchown`, `fchmod`), never on a path. Use a walk
with an explicit stack and a depth cap rather than a recursive one.
Treat a file with `st_nlink > 1` as not yours to change. A check that
returns a stat result or a path and keeps no descriptor is a check, not a
pin: return the open folder from the check and do every list, open,
link, rename and count through `dir_fd` on it. A lock on a sibling file
does not stop a rename of the folder.

**The check that catches it:** `tests/test_shared.py`,
`RootPinnedTest.test_a_swap_at_any_point_on_the_write_path_never_leads_either_walk_outside`:
it swaps every point on the write path mid-walk (ROOT's parent, ROOT,
each of the four, each folder between, the entry) for a link or another
folder, in both walks, and asserts nothing outside the mailbox changed.
With the ROOT pin dropped it fails 8 subtests; with the ROOT check
accepting any folder it fails 8. `InitWalkTest.test_a_nest_past_walk_max_depth_is_named_and_never_a_traceback`
fails both walks with the depth cap removed. `RootPinnedTest.test_a_hard_linked_file_is_skipped_and_named_and_unchanged_at_both_names`
covers the second name. For the live paths, `tests/test_inbox_pinned.py`,
`InboxPinnedTest.test_a_member_swapping_its_inbox_mid_command_never_leads_tc_outside`:
the member who owns an inbox (or an outbox branch) swaps it just after
tc first looks at it, for every command family that reaches one (send,
the far gate, peek, read, wait, log, health, flush's count, the unread
counts, the board), and nothing at the far end may change, print or
count. A path put back in place of the pinned descriptor in any family
turns its row red. `EveryInboxActHasARowTest` fails when tc gains a
function that opens an inbox with no row or named exemption.

**Detection:** any `os.open`, `os.lstat`, `os.chmod`, `os.chown`,
`os.walk` or `pathlib.Path(...) / name` on a joined path after a check of
that path; an `O_NOFOLLOW` presented as the whole guard; a recursive
walk (`os.fwalk` in Python 3.12 recurses once per level) over a tree
other users can write; printed `chgrp` or `chmod` lines for someone to
paste later. A helper that lstats a folder and returns its path or a
stat result, whose callers then `os.listdir`, `os.scandir`, `os.link`,
`Path.rename`, `os.open` or build `folder / name`; worse with a blocking
call (a lock wait, a subprocess) between the check and the act. For each
folder on the path, ask who may rename it: in a sticky folder, the
entry's own owner can.

**Source:** SHARED review audits `2026-10-15-0300-quick` (round 5,
HIGH-1), `2026-10-15-0408-quick` (round 6, HIGH-1),
`2026-10-15-0840-quick` (round 7, HIGH-1 and MEDIUM-1), and
`2026-10-15-0953-quick` (round 8, SHIP). Fixes: `4e7213e` (D29, no lines
to paste), `a538fa8` (folders below the four pinned), `db66ed7` (tc's own
stack walk with a depth cap) and `930b0df` (ROOT pinned by identity, a
second name never changed), merged into the dev branch at `84b97d2`. The fourth hit: the P3 phase
review, audit `2026-10-15-1409-full`, HIGH-1 (bugs-reviewer, confirmed by
breaker; the send case shown on a scratch copy by devils-advocate). Fixed
by D35's one pinned inbox handle in the P3 fix round's round 1a, merged
into the dev branch at `8b9b59d`.

**Times hit:** 4: three rounds of SHARED, then the P3 phase review's
live inbox paths (one finding, six flagged lines). Recorded as DEBT under
D34 and not counted: the SSH lane's round 1 re-review (the init user
swapping a member's outbox branch mid-send) and the P3 phase review's
init-only paths.

**Tier when hit:** HIGH. Another member's files outside the mailbox
change at an attacker's choosing. The floor is HIGH when someone the
code does not trust can make the swap. A match whose only possible
swapper is a user the project trusts as its administrator (here the init
user, D34) is filed DEBT and recorded.

**Shared catalog:** none fits. The owner's catalog has no entry for a
check-then-act race on a path, or for a link swapped above the last
name. This entry is a candidate for it.
