# per-owner-file-open-to-the-group

Model:  Claude Opus 5.5 (the TheConnection architect session), 2026-10-16,
        from the P3 phase review's consolidator proposal
Status: unreviewed

**What:** a file that stands for one user's state sits in a folder the
whole group can write, at a mode that lets the group open it. Either it
is a lock whose holder is read as that user's liveness, or it is a marker
whose contents or time decide whether that user is notified. At `0664`,
or even `0644` (a read-only descriptor can take `flock`), any member can
hold the lock or rewrite the marker, and the code believes the file.

**How it showed:** the P3 phase review, 2026-10-15 (HIGH-2 and MEDIUM-1),
on a shared mailbox. The wait and watch locks were `0664` files directly
in the group-writable `mail/`. A member who held another member's wait
lock made the owner's `tc wait` exit 3 ("ALREADY LISTENING", which the
waking side reads as covered) while `tc health` named the member's pid as
the owner's listener. A member who rewrote a Codex member's ring marker
to `clear` stopped every later doorbell while that inbox held unread
mail, right after the last sender was told the next send rings again.
Both were shown on scratch copies, one user standing in for two.

**Why it's bad:** mail lands and nothing wakes, while every check a
person would run says a listener is there. For a Codex member, the one
way it learns of mail goes quiet.

**Prevention:** a per-owner file lives in a folder only its owner can
write, at `0600`, reached through the pinned folder handle: the wait and
watch locks now sit in the owner's own inbox (D35). Never decide on the
contents or the time of a file another user can write; decide on a time
the deciding side holds instead (D36: each sender keeps its own
last-ring record). A lock read as identity is checked against its owner:
`tc health` names a holder only when it is the inbox owner's process, and
a busy refusal names the holder's user and pid. A command that acts as a
name's owner (`tc wait`, `tc watch`) checks that the running user owns
that name. Not this pattern: a lock every member must take by design,
whose wait is capped by a named constant and whose refusal is worded
(the inbox lock and the counter, C4).

**The check that catches it:** `tests/test_wake_files.py`,
`WakeFilesAreTheirOwnersTest.test_no_member_holds_or_redirects_another_members_wake_file`
(one subtest per wake file: the wait, watch and inbox locks and the ring
marker) and
`test_a_file_planted_at_the_owners_lock_name_is_moved_aside_with_words_and_the_owners_lock_made`;
`OnlyTheOwnerListensTest` and `HolderNamedTest` in the same file; and
`tests/test_codex_route.py`,
`DoorbellRecordTest.test_a_marker_rewritten_to_clear_costs_at_most_one_backoff`.
With the locks back in `mail/` at the group mode, the wait and watch
subtests and the planted cases fail; with the ring decided by the marker
alone, both marker subtests fail. Every cross-member test stands one
Linux user in for two; the two-user walk is `qa/human/route-shared.md`.

**Detection:** (1) `fcntl.flock` or `fcntl.lockf` on a file in a shared
folder (group-writable, sticky or setgid) made with a group or other read
bit, whose holder's pid is then reported as a name's listener by a
`/proc/locks` reader with no uid check. (2) Worse when `LOCK_NB` or
`BlockingIOError` maps to "already running" with no holder named. (3) A
state file in such a folder whose first line or mtime decides whether to
notify, retry or skip. (4) A command that takes a name and locks that
name's liveness file without checking that the running user owns it.

**Source:** P3 phase review, audit `2026-10-15-1409-full`, HIGH-2 and
MEDIUM-1 (devils-advocate, confirmed by multiuser-reviewer). Fixed by
D35 and D36 in the P3 fix round's round 1b, pinned by round 2, merged
into the dev branch at `8b9b59d`.

**Times hit:** 1 (one review, two findings: the lock and the marker).

**Tier when hit:** HIGH where the file is a lock read as its owner's
liveness or identity. A hit where the rewritten file only holds off a
notification that a later event can restore may be filed MEDIUM by
saying so, as the marker finding was.

**Shared catalog:** none fits. Closest is `written-claim-outlives-the-code`
(health's "listening" rested on a file a stranger could hold), but the
mechanism here is a mode and a folder, not a stale sentence. A candidate
for the catalog.
