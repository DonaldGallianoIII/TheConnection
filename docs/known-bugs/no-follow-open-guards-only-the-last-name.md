# no-follow-open-guards-only-the-last-name

Model:  Claude Opus 5.5 (the TheConnection architect session), 2026-10-15
Status: unreviewed

**What:** code checks a path (lstat, a walk's listing) and then acts on
it by name: opens it, chmods it, chowns it, or descends into it.
`O_NOFOLLOW` and `os.walk`'s link check guard only the last name in the
path. Any folder earlier in the path can still be swapped for a link, by
whoever owns the folder holding it, between the check and the act. The
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

**Why it's bad:** a member's own init, run to fix that member's own
entries, changes the group and mode of that member's files outside the
mailbox (a home folder, a script folder on their PATH), at another
member's choosing. That is past D20's worst case, a failed send.

**Prevention:** after the check, never resolve a name again. Open the
top once, confirm by identity (`st_dev` and `st_ino`) that it is what
the check judged, then reach every name below by `dir_fd` on an open
folder, enter a folder only when `fstat` finds what `lstat` found, and
act on the open file (`fchown`, `fchmod`), never on a path. Use a walk
with an explicit stack and a depth cap rather than a recursive one.
Treat a file with `st_nlink > 1` as not yours to change.

**The check that catches it:** `tests/test_shared.py`,
`RootPinnedTest.test_a_swap_at_any_point_on_the_write_path_never_leads_either_walk_outside`:
it swaps every point on the write path mid-walk (ROOT's parent, ROOT,
each of the four, each folder between, the entry) for a link or another
folder, in both walks, and asserts nothing outside the mailbox changed.
With the ROOT pin dropped it fails 8 subtests; with the ROOT check
accepting any folder it fails 8. `InitWalkTest.test_a_nest_past_walk_max_depth_is_named_and_never_a_traceback`
fails both walks with the depth cap removed. `RootPinnedTest.test_a_hard_linked_file_is_skipped_and_named_and_unchanged_at_both_names`
covers the second name.

**Detection:** any `os.open`, `os.lstat`, `os.chmod`, `os.chown`,
`os.walk` or `pathlib.Path(...) / name` on a joined path after a check of
that path; an `O_NOFOLLOW` presented as the whole guard; a recursive
walk (`os.fwalk` in Python 3.12 recurses once per level) over a tree
other users can write; printed `chgrp` or `chmod` lines for someone to
paste later.

**Source:** SHARED review audits `2026-10-15-0300-quick` (round 5,
HIGH-1), `2026-10-15-0408-quick` (round 6, HIGH-1),
`2026-10-15-0840-quick` (round 7, HIGH-1 and MEDIUM-1), and
`2026-10-15-0953-quick` (round 8, SHIP). Fixes: `4e7213e` (D29, no lines
to paste), `a538fa8` (folders below the four pinned), `db66ed7` (tc's own
stack walk with a depth cap) and `930b0df` (ROOT pinned by identity, a
second name never changed), merged into the dev branch at `84b97d2`.

**Times hit:** 3, in three rounds of one lane.

**Tier when hit:** HIGH. Another member's files outside the mailbox
change at an attacker's choosing.

**Shared catalog:** none fits. The owner's catalog has no entry for a
check-then-act race on a path, or for a link swapped above the last
name. This entry is a candidate for it.
