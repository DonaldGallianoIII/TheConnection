# Handoff: SHARED (P3, wave 2)

Model:  Claude Opus 5.5 (the SHARED lane agent)
Status: unreviewed
Date:   2026-10-14
Branch: Claude-Development-TheConnection-SHARED, from
        Claude-Development-TheConnection at c8708e5 (after P0, P1 and P2
        merged; the plan with D16, D17 and D18)
Where:  ~/TheConnection-lanes/shared

## Commits

| Task | Commit | Subject (the PR line) |
|---|---|---|
| H1 | `e63e8fc` | Add tc init --shared, so separate Linux users in one group share a mailbox (C4, D16) |
| D17 | `5c4981c` | Refuse planted links in the mailbox and make the shared folders sticky (D17) |
| Handoff | the commit that adds this file | Write the SHARED handoff and its two pauses. |

`phases.md` gives no PR line for H1; both subjects are written in its
style. No amend, reset or rebase. Nothing pushed or merged.
`tests/_root.py`, `contracts.md`, `phases.md`, `CLAUDE.md`, `README.md`
and `JOIN.md` were not edited. The files changed are `tc`,
`tests/test_shared.py` (new), this file and `pauses/SHARED-1.md` and
`pauses/SHARED-2.md` (new).

## What was built

Every new block in `tc` carries a one-line `SHARED H1 (Claude Opus 5.5,
unreviewed)` or `SHARED D17 (...)` comment. Every function added or
changed has `@interacts`, `@deps`, `@complexity` and `@alloc`; `inbox`
and `next_seq`, which had no block, got one. The module block's layout,
`@interacts`, `@deps`, `@complexity` and `@alloc` name `.shared`, init,
the umask, the modes and the link checks. New constants each carry a
comment saying why.

**H1, `tc init --shared` and the umask (C4, D16).**

- `tc init --shared --group <g>`. `--shared` and `--group` are both
  required (a missing one is a usage error, exit 9). A group this
  machine lacks: `tc init: no group named <g> on this machine; nothing
  changed`, exit 1. A group the user is not in (`os.getgroups()`, plus
  the effective group): `tc init: you are not in group <g>; nothing
  changed`, exit 1. Both checks run before anything is touched.
- Then init walks `mail/`, `status/`, `cards/` and `outbox/` (those
  there). Each entry is opened with `O_NOFOLLOW | O_NONBLOCK` and changed
  through that descriptor (`share_entry`): folders get group g and 2775,
  files group g and 0664, `mail/.seq` and the locks included. A link, a
  FIFO, or an entry the user may not change is skipped and named on
  stderr. Last, `ROOT/.shared` is written (a `.tmp`, then a rename)
  holding g. It prints `mailbox shared with group <g>: <n> folders and
  <m> files set to group <g>`, and exits 1 after all that when it
  skipped anything.
- `set_shared_umask`, called in `main()` just ahead of `args.fn`: when
  `.shared` names a group, `os.umask(0o002)`. An unreadable `.shared` (a
  link, a FIFO, over 4 KiB, not UTF-8, no group on one line) refuses
  every command but init, exit 1, before anything is written.
- `make_folder(path)` is now the one place tc makes a folder: `inbox`,
  `next_seq`, `inbox_lock`, `cmd_wait`, `cmd_status`, `write_card`,
  `cmd_watch` and init's own ROOT. A folder already there is left alone.
  Under a shared mailbox, each folder it makes gets group g and its mode
  as it is made (D16), through a descriptor opened with
  `O_DIRECTORY | O_NOFOLLOW`. The group is resolved before the mkdir, so
  a `.shared` naming a group this machine lacks refuses with nothing
  made.
- `tc health` ends with `mailbox shared with group <g>` or `mailbox
  private`, in the contract's words with no column padding.
  `health_snapshot()` gains `shared_group`: the name, or null.

**D17, no planted links.**

- `open_by_name(path, flags)` opens the wait, watch and inbox locks,
  `mail/.seq` and `status/<name>.md` with `O_NOFOLLOW`. A symlink there,
  dangling or not: `tc: <path> is a symlink, which tc never follows;
  nothing written through it`, exit 1. A file already there is opened
  without `O_CREAT`; only a missing one is made, with `O_CREAT | O_EXCL`,
  and it is opened again if another process made it in between.
- `tc status` with no arguments reads each status file through
  `read_regular_file` (1 MiB cap, `STATUS_READ_MAX_BYTES`). A link, a
  FIFO, an oversize or non-UTF-8 file is named on stderr (`tc status:
  <path> not shown (<why>)`) instead of shown, and the command exits 1
  after showing the rest.
- A symlink at `mail/.ring-pending-<name>`: a send to that codex name
  answers `tc send: <marker> is a symlink, which tc never follows;
  nothing sent`, exit 1, nothing landed, nothing rung. A codex join over
  one refuses, exit 1, no card written. Both check first thing under the
  inbox lock.
- `mail/`, `status/`, `cards/` and `outbox/` get 3775 (sticky) at init
  and when `make_folder` makes them later (`shared_folder_mode`). An
  inbox and its `read/` stay 2775.
- `check_inbox(name)` lstats `mail/to-<name>` and its `read/` and
  refuses a link, or anything that is not a folder, exit 1: `tc: <path>
  is a symlink, not a real folder; tc never follows it, so nothing was
  read or written there`. `inbox()` calls it, so send, read, peek and
  every wait poll are checked; `deliver_local` calls it before
  `next_seq`, so a refused send takes no number.
- The known limit is in `ring_codex`'s doc block: codex runs as the
  sending Linux user, so a Codex session of another Linux user is
  probably not reachable by its ring. The ring fails, the marker and the
  D16 backoff hold, and the mail still lands.

**Tests.** `tests/test_shared.py`, new, on `tests/_root.py`: 9 tests.
`SharedTest` (H1, 4): init over a root that already holds an inbox,
a message, `.seq`, a lock, a status and a card; a foreign group and a
missing group refused with every entry unchanged; the health line and
key before and after; and folders made after init on an empty root. The
three mode tests run once with the user's primary group and once with a
supplementary group (`os.getgroups()`), where a folder left without its
chown or setgid lands in the wrong group. `NoPlantedLinksTest` (D17, 5):
the sticky folders (with an `outbox/sent/` made by hand); a link at each
of the wait, watch and inbox locks, `.seq` (and a dangling `.seq`) and
`status/x.md`, plus a status list holding a link; a link at the ring
marker, with a second codex name rung through the same fake to prove the
fake is wired; a link as an inbox and as an inbox's `read/`; and, in
process with `os.open` wrapped, that `.seq` and an inbox lock are opened
with `O_NOFOLLOW` every time and with `O_CREAT` only once, with
`O_EXCL`. Each test sets the umask to 022 first, so a tc that never sets
its own writes 0644 and fails.

## Verify

Run in `~/TheConnection-lanes/shared` on this machine (Python 3.12.3,
Node 22). Each command's result line:

| Commit | Command | Result |
|---|---|---|
| `e63e8fc` | `python3 -m unittest tests.test_shared -v` | `Ran 4 tests`, `OK` |
| `e63e8fc` | `python3 -m unittest discover -s tests -p 'test_*.py'` | `Ran 112 tests`, `OK` |
| `5c4981c` | `python3 -m unittest tests.test_shared -v` | `Ran 9 tests`, `OK` |
| `5c4981c` | `python3 -m unittest discover -s tests -p 'test_*.py'` | `Ran 117 tests`, `OK` |
| both | `node --test tests/*.test.mjs` | `# tests 8`, `# pass 8`, `# fail 0` |

The base, `c8708e5`, ran 108 Python tests and 8 Node tests, all passing.
`check_voice.py` and `check_american.py` are clean on this file, both
pauses, `tests/test_shared.py` and the lines added to `tc`.

## Mutations and their red runs

Method: a scratch script outside the repo made each mutation as an
exact text edit to `tc`, ran `python3 -m unittest tests.test_shared`,
wrote the original bytes back and compared sha256 before and after.
Every run ended with `tc` restored. H1's six ran on the exact `tc` of
`e63e8fc` and D17's eight on the exact `tc` of `5c4981c` (sha256 of
`git show <commit>:tc` checked against the file each run restored). Each row names the tests
that went red; a group in brackets is the subtest.

| Task | Mutation | Red |
|---|---|---|
| H1 | no `set_shared_umask` in `main()` | 4 failures: the existing-entries and later-folders tests (both groups) |
| H1 | `make_folder` sets no mode | 2: later folders (both groups) |
| H1 | `make_folder` sets no group | 1: later folders (supplementary) |
| H1 | init skips the group check | 1: the foreign-group refusal |
| H1 | init leaves files as they are | 2: existing entries (both groups) |
| H1 | the health line always says private | 1: the health test |
| D17 | `open_by_name` without `O_NOFOLLOW` | 9: each of the seven planted-file cases, and the reopen test (`.seq`, the lock) |
| D17 | no sticky bit (top folders 2775) | 6: the sticky test (both groups) and H1's two mode tests (both groups) |
| D17 | the sticky bit on every folder | 6: the same six |
| D17 | no inbox check | 7: send, read, peek and wait on the linked inbox, read and send on the linked `read/`, and the nothing-landed check |
| D17 | a send ignores a linked marker | 1: the ring-marker test |
| D17 | a join ignores a linked marker | 1: the ring-marker test |
| D17 | the status list follows links | 1: the planted-file test (its status-list part) |
| D17 | a reopen with `O_CREAT` | 2: the reopen test (`.seq`, the lock) |

## Assumptions

1. **The sticky bit goes on the four folders only.** D17 names `mail/`,
   `status/`, `cards/` and `outbox/`; the lane note says "set at init
   and on every later folder (one helper)". Built as: every later
   folder goes through the one helper, and the helper gives 3775 to the
   four and 2775 to the rest. A sticky inbox would stop `tc read` by
   user B from moving mail user A wrote out of `to-b/`.
2. **Init makes no folder.** C4 and D16 say init reaches the folders
   there at the time; the test asserts init on an empty root makes
   nothing. Pause SHARED-1 asks whether it should make three.
3. **The group check adds the effective group** to `os.getgroups()`. A
   process may chown to either, and some systems leave the primary group
   out of `getgroups()`.
4. **Init exits 1 when it skipped anything**, after writing `.shared`:
   the rest of the mailbox is shared, and the umask applies from then.
5. **An unreadable `.shared` refuses every command but init**, since tc
   cannot know the group and never guesses it. In process (the board's
   feed), `health_snapshot()` raises the `ValueError` instead.
6. **`shared_group` in `tc health --json` is an interface the contract
   does not name.** C4 names only the words. The lane note puts the
   change in `health_snapshot`, so the snapshot carries the group, null
   when private. Rename or drop it at review.
7. **No `O_CREAT` on a file already there.** D17's text asks for
   `O_NOFOLLOW`. With mail/ sticky and group-writable, Linux with
   `fs.protected_regular = 2` refuses an `O_CREAT` open of a file another
   user made, unless that user also owns the folder: the third user of a
   shared mailbox could not take a lock or a number. This machine has 2
   (`/proc/sys/fs/protected_regular`). `open_by_name` splits the open so
   that rule never applies.
8. **The link checks hold shared or not.** D17 does not scope them to a
   shared mailbox, and a private one loses nothing by them.
9. **`check_inbox` also checks `read/`**, D16's "an inbox and its
   read/". A dangling link at `mail/to-x` still gives `no unread mail`
   from read and peek (exit 0), whose existing `is_dir` test sees no
   folder; send and wait refuse it (exit 1). Checked by hand.
10. **The locks keep their old open modes**: the wait and watch locks
    `O_WRONLY | O_TRUNC` (what `"w"` gave), the inbox lock append,
    `.seq` read and append (`"a+"`).
11. **`tc status` refuses after showing the rest**, exit 1, rather than
    stopping at the first file it will not show. A non-UTF-8 status file
    was a `UnicodeDecodeError` traceback at `c8708e5`; now it is a line
    on stderr. Both checked by hand.

## Pauses

| Pause | Status | Built |
|---|---|---|
| SHARED-1 | open | option 1, C4 as written: init makes no folder |
| SHARED-2 | open | nothing: outside D17's list |

- `pauses/SHARED-1.md`: on a fresh mailbox, the second Linux user's
  first command must make a folder in ROOT, which the first user owns.
  Recommends init making `mail/`, `status/` and `cards/`, words for the
  PermissionError, and a README line on search access to ROOT.
- `pauses/SHARED-2.md`: a symlink planted as a message in another
  user's inbox is printed by `tc peek`, `tc read` and `tc log` (seen by
  hand), and a FIFO at a lock's name blocks the open. Recommends reading
  messages through `read_regular_file` and adding `O_NONBLOCK` with an
  `S_ISREG` check to `open_by_name`.

## Spotted, not fixed

1. The two holes in SHARED-2.
2. **A rejoin over another user's card fails without words.** `cards/`
   is sticky, so `write_card`'s rename onto a card another user owns
   fails with EPERM, a traceback (exit 1), and its `.tmp` stays in
   `cards/`. That is D17's intent (no member replaces another's card),
   minus the words. Reasoned from the code, not run.
3. **A ring marker another user owns** cannot be rewritten or removed
   under a sticky `mail/`. `deliver_codex` and `tc join` already say so
   in words ("could not be written ... may not ring", "could not be
   removed"), and a `.ring-pending-<name>.<pid>.tmp` stays in `mail/`.
   Reasoned, not run.
4. **For the SSH lane.** `outbox/` is sticky, so one user's `tc flush`
   cannot move another user's queued file into `outbox/sent/` or
   `outbox/refused/`. S1 and S2 should make `outbox/` and its subfolders
   through `make_folder` and open any file by name through
   `open_by_name`. The gate's `health --json` now carries
   `shared_group` to a far key, unless the gate drops it as it drops
   `cards`.
5. **For the merge with BOARD.** `health_snapshot()` has one more key.
   A BOARD test that pins the snapshot's keys exactly would need it. Not
   checked: BOARD's tree is not in this worktree.
6. `mailbox_summary` (health) and `unread_count` (card, join, the codex
   route) still count names through a linked inbox. They write nothing,
   and D17 lists send, read, peek and wait.
7. `CLAUDE.md`'s layout and Status do not name `.shared` or `tc init`,
   and the README has no shared section. Not this lane's files; the
   architect keeps `CLAUDE.md` current at merges, and DOCS writes the
   README and `route-shared.md`.

## Not verified

- Anything that needs a second Linux user: another user writing the
  group-writable files, the sticky bit stopping another user's delete or
  rename, `fs.protected_regular` for a third user (the test checks the
  flags tc passes, not the kernel's answer), and the EPERM paths in
  Spotted items 2 and 3. That walk-through is Donald's human QA (D4).
- The codex ring across Linux users (the known limit). Real `codex` and
  real `ssh` were never run.
- Init skipping a link or a FIFO has no test in the tree. Checked by
  hand once, under a scratch `TC_ROOT`: a link in `mail/to-b/` to a 0600
  file outside the mailbox and a FIFO in `mail/`. Init named both on
  stderr and exited 1, and the target stayed 0600 in its own group.
- The PermissionError in SHARED-1 is reasoned from the code.
