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

---

# Round 1b: D35's locks and doorbell, D36's refusals

Model:  Claude Opus 5.5 (the P3 fixer, round 1b)
Status: unreviewed
Date:   2026-10-15
Branch: Claude-Development-TheConnection-P3FIX, from round 1a's head
        `c7580ed`
Brief:  audits/2026-10-15-1409-full/fixes/round-1b.md (in the public
        checkout), against synthesis.md's HIGH-2, MEDIUM-1 and LOW-1,
        and the dev branch's C2 item 5 and C4 (D35, D36)

## Commits

| Brief's | Commit | Items | Subject |
|---|---|---|---|
| (a) | `8d43a5c` | 1, 2, 8 | The wait and watch locks in their owner's inbox; only a name's owner listens |
| (b) | `122dacf` | 3 | A busy lock's holder named; health lists a lock held by someone else |
| (c) | `551c4af` | 4, 5 | The doorbell: each sender's own last ring; a gate's retry rings |
| (d) | `ad0bbae` | 6 | WakeFilesAreTheirOwnersTest, the class proof |
| follow-up | `b2ff2ed` | 1, 4, 6 | Each case's assertions kept inside its own subtest |
| (e) | the commit that adds this section | 7 | The two human steps, and this handoff |

The follow-up came from the first mutation run: five of my loops
asserted after `with self.subTest(...), _root.TcRoot() as root:` closed,
so the first failing case stopped the loop and its red was not
attributed to that case. Every mutation below was run again after it.

## What was built

### Item 1: the locks in the owner's inbox (D35 (1))

- `tc wait` and `tc watch` take `mail/to-<name>/.wait.lock` and
  `.watch.lock` (`WAKE_LOCK_NAME`, tc:858), through `hold_wake_lock`
  (tc:4208): the inbox is pinned (`pinned_inbox`), and the lock is
  opened by name in its descriptor by `open_wake_lock` (tc:4076): made
  `O_CREAT | O_EXCL` at 0600, or, when something is there, opened
  `O_NOFOLLOW | O_NONBLOCK` and kept only when `fstat` finds a regular
  file with one name that this user owns (an own one at another mode is
  set to 0600 through its descriptor). Anything else (another user's
  file, a link, a FIFO, a folder, a second name) is moved aside in the
  inbox by `move_aside` (tc:4024) to `<lock>.planted-<k>`, with one line
  on stderr naming what it was, whose, and where it went; then the
  owner's lock is made. At most `WAKE_LOCK_TRIES` (3) moves, then exit 1
  with words.
- `listeners()` (tc:7459) opens `mail/` once and each inbox by name,
  lstats the lock in it, and counts it only when it is a regular file
  the inbox's owner owns; it names a holder only when that holder's
  process is the owner's (`process_uid`, tc:7430) or one tc cannot look
  at. Output shape unchanged (name to pid or None, now in name order),
  so `tc health`, `tc watch` and the board read it as before.
  `_flock_holders` (tc:7402) now keeps every holder of a file.
- Init gives a wake lock 0600 (`shared_file_mode`, tc:1705), so the
  owner's own rerun never opens it to the group.
- The switch-over (`OLD_WAKE_LOCK_NAME`, tc:887), private mailboxes
  only: `old_wake_lock_held` (tc:4137) tests `mail/.<kind>-<name>.lock`
  with a non-blocking shared flock, let go at once, and a held one stops
  a new wait or watch with exit 3 and today's words, before an inbox is
  made; `listeners()` keeps listing the old place and reports its holder
  for a name whose new lock nobody holds. A shared mailbox never reads
  the old place. Each piece carries a comment that it can go once every
  session has re-armed.
- `board/serve.py`: its module block's lines on `tc.listeners` name the
  new place and cost. The board reads `tc.listeners("wait")` unchanged
  and shows no new state.

### Item 2: only a name's owner listens (D36 (2))

`refuse_other_listener` (tc:4171), on a shared mailbox only, before
anything is made: a card another user owns gives C4's words, `tc
<kind>: <name>'s inbox belongs to <owner>; only <owner> listens for it`,
and no card gives `tc <kind>: nobody has joined as <name> on this shared
mailbox; its owner runs tc join <name> first`, exit 1 both. The owner's
own wait or watch whose inbox is gone is refused too, with words to run
`tc join` (only join makes an inbox there). A private mailbox makes the
inbox and its read/ as before.

### Item 3: the holder named (D35 (3))

- `busy_words` (tc:3070), used by `next_seq` and `inbox_lock`: exit 10,
  nothing written, as before, and the words now read `tc: another
  process is holding <what>'s lock: <user> (pid <pid>); try again. If
  it stays held, ask <user> to let it go.`, with `, or ask the user who
  ran init (<init>) to act` before the stop on a shared mailbox. When
  /proc/locks names nobody by then: `tc: another process held <what>'s
  lock past 3 s, and /proc/locks names no holder now (it let go, or the
  process that took it has ended); try again`. The second case is real:
  Linux drops a flock from /proc/locks once the process that took it
  ends, even while another process still holds the file open (a shell's
  `( flock 9 && sleep 60 ) 9< file` does this).
- `held_by_others` (tc:7564): `tc health --json` gains
  `held_by_others`, and `tc health` one `held` line each, for any wait,
  watch or inbox lock held by a process whose user is not the name's
  owner (the card's owner, else the inbox's). [] on a private mailbox.
- The gate's `health --json` drops the key (`health_snapshot(...,
  held=False)`, tc:7784, called from `cmd_gate`, tc:7251). Round 1c
  makes the gate's health an allow list (D36 (5)); until then this
  projection is what keeps it home.

### Item 4: the doorbell (D35 (2), D36 (1), C2 item 5)

- `write_rang_record` (tc:5567) writes `outbox/<user>/.rang-<to>`
  (`RANG_RECORD_NAME`, tc:909), 0600, its mtime set from `wall_clock()`,
  in this user's branch through `claim_branch` and `branch_problem`
  (D33), before the ring, as the marker is. A squatted branch or a
  record it cannot write is a warning.
- `rang_long_ago` (tc:5529) reads it by name in the branch's
  descriptor: old when RING_BACKOFF_SECONDS or more, missing, not this
  user's regular file, unreachable, or dated after now.
- `ring_doorbell` (tc:5704) holds the decision and the ring that
  `deliver_codex` held: steps 1 to 4 unchanged, plus a ring whenever
  this sender's own record is old, whatever the marker says. Its doc
  block states the cost: at most one ring per sender per name per
  backoff while mail waits unread, and on a dead Codex one
  CODEX_RING_SECONDS wait per sender per backoff. Init gives the record
  0600.

### Item 5: a gate's retry rings (LOW-1, option B)

`deliver_once` (tc:3521, the branch at tc:3566): an origin id already
filed for a name whose card says codex runs `ring_doorbell` with nothing
landing. Step 1's "nothing unread before" has no before on a retry, so
it reads False, and a ring needs unread mail now; a ring owed by the
marker (a gate killed after filing, before its ring) rings. A retry is
never refused for a bad marker, inbox or card: the ring is skipped, the
answer is still `already delivered`.

### Item 6: the class proof

`tests/test_wake_files.py`, `WakeFilesAreTheirOwnersTest`
(tests/test_wake_files.py:909),
`test_no_member_holds_or_redirects_another_members_wake_file` (:1061):
five subtests on a shared mailbox, ann joined by the running user, the
member a one-shot child reported as another member (`members_patched`:
its process, and every file it plants, two ids up; ROOT and `.shared`
one id up, the init user, as `as_member` does), the owner's command in
process:

| Subtest | Before | While | Asserted, by value |
|---|---|---|---|
| the wait lock | plants and holds a file at ann's lock name; holds the old place `mail/.wait-ann.lock` | at the first poll, tries to hold ann's lock | the wait runs to its timeout (exit 2), this process holds the lock at the name, the member's open fails, `listeners()` names ann's pid and never the member's, the plant moved aside with words |
| the watch lock | the same for `.watch.lock` | at the first poll | the same, exit 0 |
| the inbox lock | holds `mail/.box-ann.lock` | holds it through | ann's tc read exits 10 within LOCK_WAIT_SECONDS plus a margin, writes nothing, and its words name the member's user and pid, and the init user |
| the ring marker, rewritten to clear | a ring fails (owed); the member writes `clear` in place | again each time the send reads the marker | the send, with `wall_clock` past ben's own backoff, rings (the fake codex asserted called, two calls) |
| the ring marker, rewritten to timed out | the same with `timed out`, touched to the send's clock | again, touched again, each read | the same |

One Linux user cannot see the kernel refuse another user's open, so the
member child applies the kernel's rule for a member who is not the
file's owner itself: it may open a file already there only when the
mode gives the group the access it asks for. That is how "the member's
open fails" is shown; the second-user walk is route-shared.md step 30.

Plus `test_a_file_planted_at_the_owners_lock_name_is_moved_aside_with_words_and_the_owners_lock_made`
(:1119): another member's held file, a symlink, a FIFO, or a hard link at
ann's wait or watch lock name (eight cases): moved aside, as itself, to
the first aside name with one line naming what and whose; ann's own
0600 lock made; the command runs to its end; the link's target
unchanged.

Known gap, in the class's block: the wake-file list is hardcoded.

### Item 7: the human steps

`qa/human/route-shared.md`: step 30, ben holds ann's wait lock (he
cannot open it) and its old place before ann arms, and health names
ann's pid; step 31, ben rewrites a Codex member's marker to `clear`, and
a send after his own backoff rings (a stand-in `codex` on ben's PATH
records the rings, so real codex is not needed). Each has pass and fail
lines. Every step after them is renumbered by two, with the references
to them. Step 29's words were brought to the code as it now is (the
holder named), and its holder command is now a `python3 -c` one-liner
whose process stays alive, since the shell's `( flock 9 && ... )` form
makes /proc/locks name nobody. The header says which numbers in its own
history are the old ones.

### Item 8: the lock file closed

`cmd_wait` (tc:4266) and `cmd_watch` (tc:7975) hold the lock in a
`with`, and `hold_wake_lock` closes its own before any exit. The
ResourceWarning ignore and its garbage collection are gone from
`tests/test_inbox_pinned.py`; `LockFileClosedTest` checks every way out.

### Item 9: doc blocks

Every function touched has its block brought true in the same commit,
the module block's layout, `@interacts`, `@complexity` and `@alloc`
included, and `tests/_root.py`'s listener.

## Mutations

Each was applied with the Edit tool to a scratch copy of the tree at
`b2ff2ed` (checked equal to it file by file first), run, and put back by
copying `tc` over it again and checking it equal (`cmp`). Every red
below is an assertion line, not an error. The class proof's subtests
come first; other suites that went red are listed after.

| Mutation | Applied as | Class proof subtests red | Red line |
|---|---|---|---|
| (a) the wait and watch locks left in mail/ at the group mode | `hold_wake_lock` makes mail/ and opens `mail/.<kind>-<name>.lock` with `open_by_name` (0664 under the shared umask) in place of the pinned inbox and `open_wake_lock` | the wait lock; the watch lock | `self.assertEqual(code, EXIT_TIMEOUT if kind == "wait" else 0,` (exit 3: the member's hold at the old place) |
| | | the planted test, all eight cases | `self.assertIn(MOVED_WORDS.format(kind=kind, path=lock, what=plant, owner=other, aside=aside), err)` |
| (b) the busy words without the holder | `busy_words` returns `tc: <LOCK_HELD_WORDS>; try again` first | the inbox lock | `self.assertEqual(got["ran"], (EXIT_BUSY, "", HELD_BY_WORDS.format(` |
| (c) the ring decision keyed on the marker alone | in `ring_doorbell`, `old = False` | the ring marker, rewritten to clear; rewritten to timed out | `self.assertEqual(len(got["calls"]), 2,` |
| (d) the record read from the marker's mtime | `rang_long_ago` lstats `mail/.ring-pending-<to>` and ages its mtime | the ring marker, rewritten to timed out (the clear one stays green: its time is the rewrite's own, past the replaced clock's backoff) | `self.assertEqual(len(got["calls"]), 2,` |
| (e) the owner check removed from tc wait | `refuse_other_listener` skipped for kind wait | none (the class proof runs the owner's own commands); `OnlyTheOwnerListensTest`, its wait subtest | `self.assertEqual(ran[kind], (EXIT_REFUSED, "", ONLY_OWNER_WORDS.format(kind=kind, name=OWNER,`, then `self.assertEqual(after, before, "a refused wait or watch made or changed something")` |
| (f) the planted-file move removed | in `open_wake_lock`, `moved = None` in place of `move_aside(...)` | the wait lock; the watch lock; the planted test, all eight cases | `self.assertEqual(code, EXIT_TIMEOUT if kind == "wait" else 0,` (exit 1: "something else had the name ... again each time") |

Other suites red under the same mutations, each on an assertion:

- (a): `WakeLockPlaceTest`, all four tests (`self.assertEqual(seen[kind],
  (True, WAKE_LOCK_MODE, os.geteuid()),`, the `MOVED_WORDS` assertIn,
  `self.assertEqual((fifo[0], link[0]), (EXIT_TIMEOUT, EXIT_TIMEOUT),
  (fifo, link))`, `self.assertTrue(held, f"ann's own tc wait ...")`).
  On the run before the follow-up, `LockFileClosedTest` errored in its
  helper `lock_fds` (no lock in the inbox to stat): an error, not an
  assertion, and outside the class proof.
- (b): `HolderNamedTest`'s two tests (both mailboxes and the let-go
  words) and the extended held-lock test in tests/test_shared.py, seven
  cases, on `self.assertEqual(err, HELD_BY_WORDS.format(what=what,
  user=running_login(), pid=os.getpid()))`.
- (c): `DoorbellRecordTest`'s clear-marker test and all five record
  cases, on `self.assertEqual([call["argv"] for call in recorded],`.
  The gate's retry test stays green under (c): that retry rings because
  the marker is owed.
- (d): `DoorbellRecordTest`'s five record cases, same line.
- (f): `WakeLockPlaceTest`'s link and FIFO cases, on
  `self.assertEqual(code, EXIT_TIMEOUT if kind == "wait" else 0, err)`.

Two more, not in the brief's list, checked the same way before their
commits: the lock file left to the garbage collector (`cmd_wait` without
its `with`) turned `LockFileClosedTest`'s wait cases red on
`self.assertEqual(leaks, [], ...)`; and item 5 removed (`deliver_once`
answering `already delivered` without the ring) turned the gate's retry
test red on `self.assertTrue(record.exists(), f"{record} missing: the
fake codex never ran")`.

## Tests whose words or helpers changed

- `tests/_root.py`: the proven listener holds
  `mail/to-<name>/.wait.lock` (`WAIT_LOCK_NAME`).
- `tests/test_root.py`, `tests/test_mailbox.py` (K4),
  `tests/test_board_feed.py`, `tests/test_health.py`: the lock's path
  (test_health's ESC lock now in an inbox of its own).
- `tests/test_inbox_pinned.py`: the ResourceWarning ignore is gone; the
  wait row lets one look pass (`Row.skip`) and the two health rows two
  (`LISTENER_LOOKS`), since the lock and listeners now open the inbox
  first; the wait row expects `.wait.lock` beside its mail in the real
  inbox.
- `tests/test_shared.py`: `shared_as` gives a wake lock 0600; the
  folders-after-init test waits on b, the joined name, before the send;
  the D17 and D19 tests lost their wait and watch cases to
  `WakeLockPlaceTest` (moved aside, no longer refused); the linked-lock
  listener test uses the new place and the old; three tests pin the new
  busy words (one accepts either form, since its member lets go and
  takes the lock on each turn); `QUIET` went with its last user.
- `tests/test_codex_route.py`: `DoorbellRecordTest`.
- `tests/test_gate.py`: the retry test.

## Behavior changes, said plainly

1. A private `tc watch <name>` now makes `mail/to-<name>/` and its
   `read/` (its lock lives there), so health and the board list that
   name with 0 unread.
2. `tc wait` opens its inbox before the first poll, so a linked or
   unlistable inbox is refused before the lock is taken, with the
   poll's own words.
3. A link, FIFO, folder, another user's file or a hard link at a wait
   or watch lock's name is moved aside with words and the command runs;
   before, a link or FIFO at the old place refused it, exit 1.
4. On a shared mailbox, a wait or watch on a name nobody joined, or by
   anyone but its card's owner, is refused, exit 1; before, it polled
   as no mail. The owner's own, with a card and no inbox, is refused
   with words to run tc join.
5. Busy refusals name each holder and whom to ask; `tc health` gains
   `held_by_others` and `held` lines; the gate's health does not.
6. A codex name rings more often: a sender with no record of its own
   (its first send to that name, or a new member) rings even with mail
   waiting, and each sender rings at most once per backoff while mail
   waits unread. On a dead Codex each sender waits CODEX_RING_SECONDS
   once per backoff.
7. A ring now makes `outbox/` and `outbox/<user>/` on a private mailbox,
   for the record.
8. A retry already delivered to a codex name takes the inbox lock and
   may ring; held past the bound, it exits 10, and the near side keeps
   the file queued (harmless: the next retry answers again).

## Verified

- `python3 -m unittest discover -s tests -p 'test_*.py'`: 310 run, OK
  at `8d43a5c`; 312 at `122dacf`; 316 at `551c4af`; 318 at `ad0bbae`;
  318 run, OK at `b2ff2ed` (round 1a ended at 303).
- `node --test tests/*.test.mjs`: 66 pass at each commit.
- Hand runs under a scratch TC_ROOT: a private `tc wait` makes the
  inbox and a 0600 `.wait.lock`, health names its pid, a second wait
  exits 3, a timeout exits 2; with `mail/.wait-<name>.lock` held by a
  live process, health names that pid and a new wait exits 3; held by
  `( flock 9 && sleep ) 9>file`, the new wait still exits 3 but
  /proc/locks names nobody (the kernel behavior above).
- Not run: the two-user walk (route-shared.md steps 29 to 31 included);
  that is the owner's. Real codex and real ssh: never.

## What was not built

As the brief says, not in this round:

- The gate's allow list (D36 (5)), init making `mail/.origins/` (D36
  (3)), the far 10 for a write failure that passes and the stuck-queue
  lines (D36 (4)), and the other LOWs: round 1c. Until round 1c, the
  gate's projection drops `held_by_others` by hand (above).
- D28's wait exit record: after the merge. The lock is the owner's 0600
  file now, so the blocker SHARED's REC-1 named is gone.
- The DEBTs stay DEBTs.
- Contracts, CLAUDE.md, 00-index, phases, known-bugs, README and JOIN
  are not mine. For the architect: CLAUDE.md:61 to 65 still names
  `mail/.wait-<name>.lock`; C4's "No planted links" bullets still say a
  link or FIFO at a lock's name is refused, where a wait or watch lock's
  is now moved aside; and the switch-over code can go once every
  session has re-armed (a later task).

Noticed and left, by tier:

- LOW: two of the owner's own `tc wait`s racing a planted file can both
  start: `move_aside` renames whatever has the name when it runs, which
  can be the first one's fresh lock. Only the owner's own processes and
  a planter racing at once reach it.
- LOW: a flock whose taking process has ended is invisible in
  /proc/locks while still held, so busy words then name nobody, and
  health and `listeners()` cannot see it. Kernel behavior; the words say
  so.
- LOW: with /proc mounted hidepid, `process_uid` sees no other user's
  process: `listeners()` then names the holder of an owner's 0600 lock
  as the owner's (only the owner can open it), and `held_by_others`
  leaves such a holder out.
- LOW: `tests/test_health.py`'s `HealthTest` leaves its children's
  pipes to the garbage collector (two ResourceWarnings, also in the
  baseline).
- DEBT: the record's branch is reached by path through `claim_branch`,
  as the send lock's is (DEBT-2: only the init user can swap it).
- REC: the switch-over code (`OLD_WAKE_LOCK_NAME`, `old_wake_lock_held`,
  the old-place loop in `listeners()`) and its two tests should go
  together, in one later task.

## Assumptions

- Names: `.wait.lock`, `.watch.lock`, `<lock>.planted-<k>`,
  `outbox/<user>/.rang-<to>`; `WAKE_LOCK_TRIES` 3; health's key
  `held_by_others` and its `held` line.
- The wake lock is opened read only: flock needs no more, and the
  owner's 0600 file can be opened for writing when D28 needs it.
- A name's owner, for health, is its card's owner, else its inbox's.
- A holder whose process tc cannot look at counts as the owner's in
  `listeners()` (only the owner can open a 0600 lock) and is left out of
  `held_by_others` (tc cannot say it is someone else).
- On a private mailbox the busy words ask no init user: nobody ran init.
- A retry's ring rule reads step 1 as False and needs unread mail now.

No pause was written.

---

# Round 1c: D36's gate, origins and stuck queues; the LOWs

Model:  Claude Opus 5.5 (the P3 fixer, round 1c)
Status: unreviewed
Date:   2026-10-15
Branch: Claude-Development-TheConnection-P3FIX, from round 1b's head
        `9f974c5`
Brief:  audits/2026-10-15-1409-full/fixes/round-1c.md (in the public
        checkout), against synthesis.md's LOW list, DEBT-5, its fix
        disagreements and REC-7, REC-12, REC-13, and the dev branch's
        D36, exit row 10, C3 and C4

## Commits

| Brief's | Commit | Items | Subject |
|---|---|---|---|
| (a) | `3d48b8c` | 1 | The gate's health --json is an allow list |
| (b) | `d95ef89` | 2 | tc init makes mail/.origins/; a shared gate never does |
| (c) | `4545832` | 3 | A far write failure that passes answers 10; each failed try leaves a note; health lists stuck mail (with LOW-11) |
| (d) | `402c676` | 4 | The automated round trip |
| (e) | `1267813` | 5, 6 | The round's tc and test LOWs |
| (f) | `ad63f74` | 7 | The board dates messages in the folders its scan opened; test_shared's guard words |
| (g) | the commit that adds this section | 8 | The records, both QA scripts, this handoff |

## What was built

### Item 1: the gate's health is an allow list (D36 (5), DEBT-5, LOW-2)

`GATE_HEALTH_KEYS` (tc:884) names, level by level, what the gate's
`health --json` gives a far key: `time`, `machine` (`load1`, `cores`,
`mem_avail_pct`, `gpus`), `sessions` (`claude`, `codex`), `listeners`,
`watchers`, `mail` (each name's `unread`, `newest_mail_age_s`,
`status_age_s`) and `shared_group`. These are the keys it gave at
`616b9db` less `mail_problem` and `shared_problem`. `gate_health`
(tc:7582) keeps only what the list names; a value that should be a dict
and is not becomes null. `cmd_gate` (tc:7606) prints
`gate_health(health_snapshot(cards=False, gpu=False, branches=False))`.
Round 1b's `held` switch on `health_snapshot` (tc:8239) is gone; the
list leaves `held_by_others` and `stuck_outbox` home.

### Item 2: init makes mail/.origins/ (D36 (3), LOW-3, REC-13)

- Init's own walk makes a missing `mail/.origins/` by its name in the
  `mail/` descriptor the walk judged, before `mail/` is listed
  (`shared_entries`, tc:1736), so the walk gives it the group and 3775
  like the four, and the init user owns it. A first try opened `mail/`
  once more before the walk; RootPinnedTest's swap test went red on it
  (the extra open moved the swap ahead of the walk, which then entered
  the folder swapped in), so it moved into the walk. A member's rerun
  makes nothing. A fresh init now says `5 folders`.
- `origin_folder` (tc:3524) makes `mail/.origins/` only on a private
  mailbox. On a shared one a missing folder raises `OriginsNotMade`
  (tc:3520), and `file_origin` (tc:3622) warns with
  `ORIGINS_NOT_MADE_WORDS` (tc:911): the message is delivered, nothing is
  made or filed, and the words say the user who ran init runs `tc init
  --shared --group <g>` again to make it; until then a retry may deliver
  twice, a duplicate, never a loss.

### Item 3: a far 10 for a write that passes; notes; stuck mail (D36 (4), LOW-4, LOW-11)

- `PASSING_WRITE_ERRNOS` (tc:694: ENOSPC, EDQUOT, EIO) and
  `PASSING_WORDS` (tc:696). `route_and_deliver` passes
  `busy_on_passing=not forward` (tc:3427, tc:3432) through
  `deliver_local` and `deliver_codex` to `publish_message` (tc:5434), so
  only the gate's delivery turns a `.tmp` that cannot be made, written
  (tc:5525) or linked (tc:5546) for such a reason into Delivery exit 10.
  tc send's own stays exit 1, since row 10 names only the gate for this.
- LOW-11 rode here, since item 3's "nothing left behind" needs it:
  `write_new_file` (tc:3307) removes the file it just made when the write
  fails, by the same name and `dir_fd`, and only while that name still
  holds the file it made (samestat on the fstat at the create). That
  covers a message's `.tmp`, a card's, `.shared`'s, the origin token's
  and a note's; the docs of `write_card`, `cmd_init` and `origin_token`
  say so.
- Notes: `note_path`, `write_note`, `carry_note` (tc:6931 to 6976).
  `file_outcome` (tc:7022) writes, on every kept try, a note beside the
  waiting file whose first line is the kept words' summary, then what
  ssh printed on stderr through `printable_lines`, then the cut line;
  written to a `.tmp` and renamed over the last note. On sent or refused
  the note moves with the file (hard link, then its old name removed;
  never removed outright), and a refusal's own words then replace it in
  `refused/`, as a later try's would.
- `OUTBOX_STALE_SECONDS` (tc:1007, a day) and `stuck_outbox` (tc:8033):
  `outbox/` opened by its path, each branch by name (pin_folder), listed
  in its descriptor (outbox_files); for a file past the bound, its queue
  is opened again by name in the branch's descriptor and the note's
  first line read there (`note_first_line`, tc:8005, at most
  `NOTE_LINE_READ_MAX_BYTES`). The age is against `wall_clock`.
  `health_snapshot` adds `stuck_outbox` with `branches`, and `tc health`
  a `stuck` line each (tc:8424).

### Item 4: the round trip (REC-7)

`RoundTripTest` (tests/test_ssh_route.py:1045) opens two harness roots,
one per machine. home-a sends to far-b through the loopback fake into the
far root's real gate as key home-a; far-b replies from that same far
mailbox through its own return key into the near root's real gate. Each
inbox is checked by content, each fake asserted called. The brief named
a third TC_ROOT; two are used on purpose: the far side's harness root is
the far mailbox itself, so the reply leaves from the mailbox the message
landed in. A third root would send the reply from a mailbox that never
received anything.

### Items 5 and 6: the LOWs

- LOW-12: `encoding="utf-8"` on every text tc writes: `next_seq`
  (tc:3241), `write_new_file` (tc:3353), `cmd_status` (tc:4542),
  `write_ring_marker` (tc:5642).
- LOW-13: `tc init --help` (tc:8643) says setgid folders, mail, card and
  status files at 0640, ROOT/.shared.
- LOW-14, option A: the squatted line puts the fix in a sentence of its
  own (tc:8421).
- LOW-15: a far 10's why is `exit 10: <first far line>` (tc:6880);
  `kept_summary` (tc:7005) says `<target> was busy (...)` for it, in the
  words and the note, and flush's stop line says the same (tc:7491). A
  255 still reads `could not reach`.
- LOW-16: `n waiting for <target> from other members (...)` (tc:7506).
- LOW-17: a divider over the core mailbox code (tc:2686).
- LOW-19: `ROUTES` after cmd_flush under its own router divider
  (tc:7518).
- LOW-20: `how = (` (tc:7101).
- LOW-21: the three long tc lines (module block, the ring states'
  comment, deliver_local's block; write_new_file's was rewritten with
  LOW-11) and tests/test_board_leak.py:133.
- LOW-22: K3's 50 senders, timed five times on this machine (32 cores,
  load 3.4 to 4.1) from the first spawn to all 50 seen blocked in
  /proc/locks: 0.207, 0.202, 0.210, 0.195, 0.211 s. The slowest is
  under half the 2 s budget, so the budget is unchanged and
  tests/test_mailbox.py is untouched. A 2 to 4 core runner is still not
  measured.
- LOW-23, option A: the dead `assertNotIn` at tests/test_cards.py:314
  dropped.
- LOW-24: OriginIdTest, FarAnswerTest and BranchTest open with what they
  test; the attribution is a comment above each.
- LOW-25: `threading` (and `errno`) in tests/test_ssh_route.py's @deps.
- LOW-26: three triple blank lines in tests/test_shared.py, one double
  blank line between methods in tests/test_gate.py.
- LOW-28, option A: tests/test_shared.py and tests/test_ssh_route.py
  name their importers; tests/test_codex_route.py's list is current
  (kill_own_fake, own_fake, test_health.py). tests/test_router.py's
  line is not written: that file is outside this round's work set.

### Item 7: the board dates by name (round 1a's MEDIUM and LOW)

- board/serve.py: `scan_messages(mail, held)` (serve.py:580) keeps each
  inbox and read/ descriptor open in the caller's `ExitStack`
  (serve.py:654); a Message's path is a `MessagePath` (serve.py:399), a
  str that carries its folder's descriptor and its name; `stat_at`
  (serve.py:746) stats a MessagePath by its name in that folder
  (`dir_fd`, never following a link) and anything else by its path,
  never followed; `file_age` (serve.py:764) and `file_time`
  (serve.py:790) use it. `feed()` holds the stack around the scan and
  `feed_from` (serve.py:1239), which is the rest of the old feed() body,
  unchanged, so every descriptor closes before feed() returns. A str
  subclass was chosen over a new Message field so tests/test_board_feed.py,
  outside this round's work set, still counts `file_time` calls by path
  text.
- tests/test_shared.py: the docstrings that named `check_inbox`'s lstat,
  `message_files`' lstat, pathlib's glob or `real_folder` as the guard
  now name the pinned inbox and the listing in the open folder
  (CommandsSayWhatTheyCannotSeeTest and four tests).

### Item 8: records

- handoffs/SHARED.md: `Status: unreviewed` alone; the round history
  moved, word for word, under `## Fix rounds` (LOW-38); `## What was
  not built` added before `## Not in this round` (LOW-39).
- handoffs/SSH.md:394: the S1 row names the test's current name, and
  the name it had at `7700fc1`, where the row ran (LOW-40).
- qa/human/route-shared.md: step 5 says `5 folders` and checks
  `mail/.origins/`; step 37 checks the note beside ben's waiting file;
  step 38's squatted line has its period; step 39 uses `ls -la` for the
  send lock (LOW-41); step 40's count reads `from other members`; step
  42 removes the note too. No step was added or renumbered.
- qa/human/route-ssh.md: the note on an older far tc says 7 (and 11
  only for a far tc with no gate at all) (LOW-42); `TC_ROOT` pinned in
  both gate lines, steps 4 and 20 (REC-12); step 12 lists the gate's
  keys; steps 15 and 16 check the note and its move into `sent/`; step
  17 has round 1b's holder words and round 1c's `was busy`. No step was
  added or renumbered.

## Mutations

Each was applied with the Edit tool to a scratch copy of the tree,
checked equal to the worktree first, run, and put back by copying the
file over it again and checking it equal (`cmp`). Every red below is an
assertion line, not an error.

| Item | Mutation | Red, by subtest | Red line |
|---|---|---|---|
| 1 (the brief's) | the old deny list back: cmd_gate prints health_snapshot less `held_by_others` | both new tests | `self.assertEqual(health_keys(json.loads(out)),` and `self.assertNotIn(NEW_HEALTH_KEY, out, "a key the allow list does not name reached the far key")` |
| 2 | init's walk makes no mail/.origins/ | the init test | `self.assertEqual(init, (0, f"mailbox shared with group {group}: 5 folders and 0 files in group {group}\n", ""))` |
| 2 | origin_folder makes mail/.origins/ on a shared mailbox too | the missing-folder test | `self.assertEqual(first, (0, f"sent #1 to b: ...", ORIGINS_NOT_MADE_WORDS.format(...)))` |
| 3 | `busy_on_passing` ignored (both checks `if False`) | all nine stage subtests; all three far gate subtests | `self.assertEqual(gated, (EXIT_BUSY, "", PASSING_WORDS.format(what=what, why=os.strerror(number))` and `self.assertEqual((code, out, err), (EXIT_QUEUED, "", ...KEPT_WORDS.format(...` (the words before LOW-15) |
| 3, LOW-11 | write_new_file never removes its file | the three write-stage subtests | `self.assertEqual(left, [], "a write that failed left a file in the inbox")` |
| 3 | carry_note returns at once | both NoteTest subtests | `self.assertFalse(left, "the note stayed beside the queue once its file was filed")` |
| 3 | no note written on a kept try | both NoteTest subtests; all three far gate subtests; StuckOutboxTest | `self.assertEqual(after_send.splitlines()[:1], ...)`, `self.assertEqual(note_lines[:1], ...)`, `self.assertEqual(stuck, [` |
| LOW-12 | write_new_file opens with no encoding | the locale test | `self.assertEqual((gated[0], sent[0]), (0, 0), (gated, sent))` (both 1) |
| LOW-15 | kept_summary says `could not reach` for a far 10 | the far 10 subtest; the flush test | `self.assertEqual(err, words.format(target=TARGET, reason=reason, path=path))` and `self.assertNotIn("could not reach", err, ...)` |
| 7 (the brief's) | file_age by `os.stat(path)` and file_time by `os.stat(path, follow_symlinks=False)`, as before | row (j), both kinds | `self.assertLessEqual(abs((age if age is not None else 0) - REAL_AGE_SECONDS), AGE_SLACK_SECONDS,` (99000 s off: the planted file's 100000 s age) |

The first runs of item 3's three loops asserted after `with
self.subTest(...), TcRoot()` closed, round 1b's slip, so a red stopped
each loop at its first case. They were nested before the commit, and
every red above counts each case.

## Tests whose words or helpers changed

- tests/test_inbox_pinned.py: row (g) reads `mail_problem` with `get()`
  (the gate's row has none now); row (h) the new plural; row (j) runs
  `board_scan_and_dates` (tests/test_inbox_pinned.py:329) and asserts
  the dates (:523).
- tests/test_shared.py: `shared_as` and three init-tree tests expect
  `mail/.origins` at 3775 (`ORIGINS_FOLDER`).
- tests/test_gate.py: `GateInProcessTest.run_gate` calls the new
  module-level `gate_in_process`.
- tests/test_ssh_route.py: the far 10 case of the kept test expects
  `BUSY_KEPT_WORDS`; `far_gate_ssh` takes `fail_errno`.
- tests/test_flush.py: `OTHERS_WORDS`; the far 10 test's line.

## Behavior changes, said plainly

1. The gate's `health --json` drops `mail_problem` and `shared_problem`,
   and gives nothing health gains later unless the list names it.
2. A fresh `tc init --shared` makes five folders, not four; on a shared
   mailbox a gate never makes `mail/.origins/`, and with none there its
   delivery warns and files nothing.
3. A far gate out of space, quota or disk health answers 10, and the
   near side keeps the message; a failed ssh try leaves a `.stderr` note
   beside the waiting file; `tc health` gains `stuck` lines and the
   `stuck_outbox` key.
4. A far 10 reads `<target> was busy (exit 10: ...)`; flush's count
   reads `from other members`; the squatted line has a period before
   its fix; `tc init --help` changed.
5. tc writes UTF-8 whatever the locale; a write that fails leaves no
   file.
6. The board holds two descriptors per name for the length of one poll.

## Verified

- `python3 -m unittest discover -s tests -p 'test_*.py'`: 320 run, OK
  at `3d48b8c`; 323 at `d95ef89`; 327 at `4545832`; 328 at `402c676`;
  329 at `1267813` and at `ad63f74` (each run on a `git archive` copy of
  the commit, or on the worktree when it equaled the commit). Round 1b
  ended at 318.
- `node --test tests/*.test.mjs`: 66 pass at each of those commits.
- New tests, with `-v`, listed in the report to the architect.
- K3's timing, above. No hand run of `tc` beyond the suite.
- Not run: both human scripts; real ssh and real codex, never.

## What was not built

As the brief says, not in this round:

- LOW-10 (measure first), LOW-18 and LOW-27 (they move code and tests;
  they ride with DEBT-11's split), and the DEBTs.
- LOW-29 to LOW-37 are the architect's. For the architect, besides: C3's
  far-10 bullet could say the near words now read `was busy`; C4's mode
  list and init bullet already carry `mail/.origins/` (D36); CLAUDE.md's
  layout could add the `.stderr` note beside a waiting file.
- D28's wait exit record: after the merge.
- LOW-28's line in tests/test_router.py: outside this round's work set.

## Work set

The brief's WORK SET line leaves out two files this round edited:
board/serve.py and tests/test_inbox_pinned.py. Item 7 names both (the
board's `file_age` and `file_time`, and round 1a's row (j)), and items 1
and 5 changed what rows (g) and (h) of tests/test_inbox_pinned.py read,
so those two lines changed with them. Each edit is its item's own. A
third file LOW-28's option A reaches, tests/test_router.py, was left
alone.

## Noticed and left, by tier

- LOW: a shared mailbox whose `mail/.origins/` a member made before this
  round keeps that member as its owner. Init's rerun names it as another
  user's and changes nothing, and no words tell the init user the way
  out: move it aside (`mv -T`), then run init again, which makes a new
  one of the init user's.
- LOW: `tc send --origin` run by a far key with no forced command is not
  the gate, so its write failure that passes still exits 1; row 10 names
  only the gate.
- LOW: `cmd_status` takes its text from argv unchecked; under a locale
  whose encoding is not UTF-8, a non-ASCII status arrives
  surrogate-escaped and the UTF-8 write raises (a traceback). The
  message path checks its body (read_body); status does not.
- LOW: tests/test_cards.py:72, `NOT_BUILT_NOTE`, has no user since
  LOW-23's line went; it is outside the brief's two-line fence there.
- LOW: the note's `.tmp` and its rename act in this user's own branch by
  path, as DEBT-2's other outbox moves do (only the init user can swap a
  level).
- LOW: the board holds two descriptors per name per poll; past about
  500 names a poll would meet the usual 1024 open-file limit and read
  the rest as unreadable.
- REC: no human step shows D36 (3)'s warning, D36 (4)'s far 10 or a
  `stuck` line (a full disk or a day's wait); the unit tests cover them.

## Assumptions

- Only the gate's delivery turns a passing write failure into 10, as
  exit row 10 says; tc send keeps 1.
- A note's first line is the kept words' summary, without the path.
- A refusal replaces the moved note's words with its own: the last try's
  words, as on every try.
- `stuck_outbox` names the member by the branch's name, and the target
  by the name the message is for, as C3 says.
- REC-7 uses two roots, not three (item 4).

No pause was written.
