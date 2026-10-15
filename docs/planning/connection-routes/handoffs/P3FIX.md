# Handoff: P3FIX, round 1a (the pinned inbox handle)

Model:  Claude Opus 5.5 (the P3 fixer, round 1a)
Status: unreviewed
Date:   2026-10-15
Branch: Claude-Development-TheConnection-P3FIX, from the dev branch at
        85a8b80 (D35 recorded)
Where:  ~/TheConnection-lanes/p3fix
Brief:  audits/2026-10-15-1409-full/fixes/round-1a.md (in the public
        checkout), against synthesis.md's HIGH-1 and its fix notes

## Commits

| Item | Commit | Subject |
|---|---|---|
| 1 | `5198710` | Pin every inbox act to one open folder (HIGH-1, D35), with LOW-6 to LOW-9 |
| 3 | `c0d9ea9` | Pin the board's inbox scan to open folders (D35) |
| 2 | `46b140d` | Add InboxPinnedTest, the class proof for D35's pinned handle |
| 4 | `67b7a6a` | Make the D32 proof fail on its own check, never in seen_as |
| 1, follow-up | `925a0b6` | Refuse an inbox lstat cannot reach with check_inbox's own words |
| Handoff | the commit that adds this file | This handoff |

Item 3 landed before item 2, against the brief's order, so every commit
is green: the class proof's row (j) is item 3's proof, and it fails on
the board's old scan.

## What was built

### Item 1: one pinned handle (HIGH-1, D35)

Every command that acts on an inbox opens it once and works inside that
open folder. New in `tc`, in the inbox block after `cmd_init`:

- `TOP_FOLDER_FLAGS` opens `mail/` and `outbox/` by their paths (only the
  init user can swap either, D34). `FOLDER_FLAGS`, already there for
  init's walk, opens every folder below by its name, never through a link.
- `pin_folder(folder_fd, name, path, make=False)` opens one folder by its
  name in an open folder and fstats it: a `Pinned` (descriptor, fstat,
  the lstat of what has the name when the open failed, the words for a
  folder it could not open or look at). Linux answers ENOTDIR, not ELOOP,
  for a link opened with `O_NOFOLLOW | O_DIRECTORY`, so the lstat decides
  the words only.
- `open_inbox` opens `mail/to-<name>/` by name in `mail/`'s descriptor and
  its `read/` by name in the inbox's. `pinned_inbox` is the context manager
  every single-inbox command uses: `mail/` opened and closed at once, the
  two descriptors held for the block and closed on every way out.
- `refuse_bad_inbox` refuses, with `check_inbox`'s words and exit 1, what
  `check_inbox` refused, judged on the open folders: an inbox lstat cannot
  reach, a link or not a folder at the inbox or its `read/`, a `read/` it
  cannot look at, and under a shared mailbox an owner (by fstat) that is
  not the card's.
- `inbox_made` makes a private mailbox's missing inbox or `read/` by name,
  after a send takes its number, as `inbox()` did, so a send refused
  before it lands makes nothing.

Each family, and where it now acts:

- (a) `tc send` and (b) the far gate: `deliver_local` opens the inbox
  before it takes a number (the brief left this to me: before `next_seq`,
  so a refusal takes no number, as `check_inbox` did). `publish_message`
  takes the folder's descriptor and `(name, descriptor)` history pairs:
  the history lstat, the `.tmp`'s create, the link
  (`follow_symlinks=False`) and the unlink are all by name. The outbox
  (`deliver_ssh`) now opens its queue by path once and publishes the same
  way; its later moves stay by path (DEBT-2, init-only).
- (c) `tc peek`, (d) `tc read`: `pinned_inbox` replaces the O2 `is_dir`
  check and `inbox()`. `show` takes `(path, descriptor)` pairs and reads
  by name (`read_regular_file` gained `dir_fd`). Read's move is
  `os.rename(name, name, src_dir_fd=inbox, dst_dir_fd=read)`;
  `by_hand_target`, `owner_words` and `still_in_inbox` work by name in the
  two descriptors, which stay open until the last print.
- (e) `tc wait`'s poll: `unread` pins the inbox afresh each poll.
- (f) `tc log`: `mail/` once, each inbox and `read/` by name, all held in
  one `ExitStack` until the log has printed.
- (g) `tc health` and the gate's `health --json`: `mailbox_summary` opens
  `mail/` once and each inbox and `read/` by name, closing each pair
  before the next.
- (h) `tc flush`'s count: `other_branches` is now a context manager that
  opens `outbox/` once and each other member's branch by name;
  `outbox_files` lists a branch in its descriptor and opens each
  `to-<name>/` by name in it.
- (i) `unread_count(name, inbox=None)`: counts in the caller's open inbox
  or in one pinned for the call. `deliver_codex` pins once under the
  inbox lock and hands that `Inbox` to its counts and to `deliver_local`,
  so the ring decision counts the folder the message lands in. When a
  private send made the inbox (nothing was there to pin), the count after
  opens it then.
- `message_files(folder, folder_fd)` lists and stats by name in the open
  folder, sorts name strings (LOW-7) and filters on `MESSAGE_SUFFIX`
  (LOW-8). The printed words keep naming the inbox's path.
- `inbox()` and `real_folder()` had no caller left and are gone.
  `check_inbox` stays for `claim_inbox` (tc join making the joiner's own
  inbox); its doc says so.
- Ride-alongs: LOW-6 (`deliver_local`'s doc no longer says the gate calls
  it directly), LOW-7, LOW-8, and LOW-9 (true `@complexity` and `@alloc` on
  `message_files`, `mailbox_summary`, `health_snapshot`, `cmd_log` and the
  module block, whose `.shared` read count also changed: a private inbox or
  `read/` made by name reads no `.shared`). Every function touched has its
  doc block brought true.

### Item 3: the board's own scan

`board/serve.py` `scan_messages` opens `mail/` once (`MAIL_FLAGS`), each
inbox by name in it and its `read/` by name in the inbox's
(`open_folder`, `FOLDER_FLAGS`), and lists each in its descriptor
(`message_names` now takes the descriptor). The board imports no new tc
function (C6) and shows nothing new.

### Item 2: the class proof

`tests/test_inbox_pinned.py`, `InboxPinnedTest`,
`test_a_member_swapping_its_inbox_mid_command_never_leads_tc_outside`:
13 rows, two kinds of swap (a link to a folder outside the mailbox,
another real folder moved in), 26 subtests. The rows: (a) tc send, (b) the
far gate's send, (c) peek, (d) read, (e) wait's poll, (f) log, (g) tc
health --json and the gate's health --json, (h) flush's count of other
members' branches, (i) tc card, a codex tc join, a codex send's ring
decision, (j) the board's scan. The mailbox is shared by tc init under
the harness's TC_ROOT; ROOT and `.shared` read as the init user's
(`as_member`), and the swap is the inbox owner's (the member who joined
as ann). The swap fires just after the first `os.open`, `os.lstat` or
`os.stat` aimed at the folder returns; for the codex join row it waits
for the first `os.open` (unread_count's pin), since its first look is
`claim_inbox`'s lstat of the joiner's own inbox. Each subtest asserts, in
this order: the swap happened, the far end's tree is unchanged, nothing
printed quotes a planted file or names its sender, then the row's counts,
ages and landing against the real folder. Known gap, in the test's doc
block: the family list is hardcoded.

Against the pre-fix tc and board (85a8b80), with this test, all 26
subtests fail on assertions.

### Item 4: the D32 proof

`tests/test_ssh_route.py`, `SharedOutboxTest.test_another_member_can_move_rename_or_remove_nothing_in_a_branch_whoever_sent_first`
now asserts ann's branch first: there, a real folder, hers, with words
naming D32. Only then does it look inside.

## Mutations

Each was applied with the Edit tool to a scratch copy of the tree at
`46b140d` (item 4's at `67b7a6a`), run with `python3 -m unittest
tests.test_inbox_pinned` (item 4: the one test), and put back; the scratch
copy was checked equal to the commit after each. Every red below is an
assertion line, not an error.

| Family | Mutation: the path back in place of the pinned descriptor | Subtests red (both kinds each) | Red line |
|---|---|---|---|
| (a), (b) | `publish_message`: the `.tmp` made, linked and unlinked by path | a, b, i (codex send) | `self.assertEqual(snapshot(far_end), far["before"],` |
| (c) | `cmd_peek` lists the inbox by a new open of its path | c | `self.assertNotIn(PLANTED_SENDER, shown, "tc named a planted file from the far end")` |
| (d) | `cmd_read` moves with `os.rename(p, target)`, two paths | d | `self.assertEqual(snapshot(far_end), far["before"],` |
| (e) | `unread` lists the inbox by a new open of its path | e | `self.assertEqual((ran.code, ran.out), (0, f"MAIL: 1 unread for {OWNER}. Run: tc read {OWNER}\n"))` |
| (f) | `cmd_log` lists each folder by a new open of its path | f | `self.assertNotIn(PLANTED_SENDER, shown, "tc named a planted file from the far end")` |
| (g) | `mailbox_summary` lists the inbox by a new open of its path | g (both rows) | `self.assertEqual((mine["unread"], mine["mail_problem"]), (1, None), mine)` |
| (h) | `outbox_files` opens each queue by its path | h | `self.assertIn(f"1 waiting for {SSH_TARGET} belong to other members", ran.out,` |
| (i) | `unread_count` lists the inbox by a new open of its path | i: tc card | `self.assertIn(f"tc card: {OWNER} has 1 unread here.", ran.err, "tc card's count is not the real inbox's")` |
| | | i: codex join | `self.assertIn(f"1 unread waiting for {OWNER}: run tc read {OWNER}", ran.out,` |
| | | i: codex send | `self.assertEqual(len(record), 2, f"the send did not ring once more: the ring decision read another "` |
| (j) | `scan_messages` opens `read/` by its path | j | `self.assertNotIn(PLANTED_SENDER, shown, "tc named a planted file from the far end")` |
| D32 proof | `outbox_branch` returns `outbox/` itself: no branch, the queue at `outbox/to-<name>/` | the D32 test | before item 4: an error, FileNotFoundError in `seen_as`; after: `self.assertIsNone(found, f"D32: ann's ssh mail waits in her own branch, {branch(root)}, a real folder "` |

## Tests whose words or helpers changed with item 1

- `tests/test_mailbox.py`, K2 (`test_k2_a_message_appears_only_whole`):
  `named` takes a `dir_fd`, and the `os.open` and `os.link` recorders
  record a name given with `dir_fd` in its folder. tc now makes and links
  a message by name in the inbox's descriptor.
- `tests/test_shared.py`,
  `RegularFilesOnlyTest.test_a_link_or_fifo_planted_as_a_message_is_never_printed_and_stays_in_place`:
  hands `show()` a `(path, descriptor)` pair.
- `tests/test_shared.py`,
  `NobodyTouchesAnotherMembersMailTest.test_a_read_that_may_not_move_a_message_names_it_and_leaves_it_unread`
  and
  `NoLostMailNoHangTest.test_a_rename_a_hard_link_turned_into_nothing_is_never_claimed_as_read`:
  wrap `os.rename`, not `Path.rename`; the module block's two lines that
  named `Path.rename` say so.

No expected words changed.

## Behavior changes, said plainly

1. A dangling link, or a file, at `mail/to-<name>` now makes `tc peek`
   and `tc read` refuse, exit 1, with the link or not-a-folder words.
   Before, their O2 check followed the link and said `no unread mail`,
   exit 0. A link at an inbox is refused wherever it leads; telling a
   dangling one apart would mean following it.
2. Every command now opens an inbox and its `read/` read-only, as the
   brief says. An inbox its owner closed to the group's read but left
   writable now refuses a send, exit 1, `tc: could not look at <inbox>
   (Permission denied); nothing was read or written there.` Before, the
   send landed. A `read/` closed to read refuses send, read, peek and wait
   the same way. Under C4 (3770) every member has read on both.
3. `tc log` no longer lists the `read/` of an inbox it cannot open; it
   still names the inbox it could not list.
4. A private send whose inbox did not exist now makes `mail/to-<name>/`
   by name in `mail/`'s descriptor; the module block's `.shared` read
   count says a private send, read, peek or wait that makes an inbox adds
   no read.

## Verified

- `python3 -m unittest discover -s tests -p 'test_*.py'`: 303 run, OK, at
  `925a0b6`.
- `node --test tests/*.test.mjs`: 66 pass, 0 fail, at `925a0b6`.
- `python3 -m unittest tests.test_inbox_pinned -v`: 1 run, OK (26
  subtests).
- A hand run under a scratch TC_ROOT: with `mail/` readable but not
  searchable, peek refuses with `could not look at`; a dangling link at an
  inbox refuses peek with the link words.

## What was not built

Not in this round, as the brief says:

- D35 (1) and (3): the wait and watch locks moved into the owner's inbox,
  the busy words naming the holder, health listing a lock someone else
  holds. Round 1b, which builds on `pinned_inbox`.
- D35 (2), the doorbell. Round 1b.
- Every other LOW: round 1c. The DEBTs stay DEBTs.
- Contracts, CLAUDE.md, 00-index, phases and known-bugs are the
  architect's, on dev. C4's "No planted links" bullet still names
  `check_inbox`'s lstat as the inbox guard, and the known-bugs entry's
  count does not show this hit.

Noticed and left, by tier:

- MEDIUM: the board's `file_age` and `file_time` stat each message by its
  path after the scan (wire and link ages, the wake walk, a stopped
  name's last sent message), and `file_age` follows a link. An inbox's
  owner who swaps the inbox after the scan can make the board date a
  same-named file at the link's target: metadata only, outside item 3's
  scope ("its inbox scan only").
- LOW: `claim_inbox` (tc join) still checks and makes the joiner's own
  inbox by path; only that owner could race it.
- LOW: `tc wait` never closes its lock file (the process's exit does); in
  process, the class proof collects it with ResourceWarning ignored.
- LOW: docstrings in `tests/test_shared.py` (`CommandsSayWhatTheyCannotSeeTest`
  and its tests) still name `check_inbox` and `message_files`' lstat as
  the code they guard.
- LOW: the item 1 follow-up commit's message points at this handoff for
  its full-suite run, which was made at that commit before this file
  landed.

## Assumptions

- The brief's `O_RDONLY | O_DIRECTORY | O_NOFOLLOW` is taken as written
  (with `O_NONBLOCK`, which `FOLDER_FLAGS` already carries), behavior
  change 2 included. `O_PATH` would let a send pin an inbox it cannot
  read; it was not used.
- `mail/` and `outbox/` are opened following a link, as before (D34).

No pause was written.
