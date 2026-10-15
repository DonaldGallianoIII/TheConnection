# Handoff: SHARED (P3, wave 2)

Model:  Claude Opus 5.5 (the SHARED lane agent)
Status: unreviewed. Fix round 1 done (audit
        `audits/2026-10-14-2100-standard`, brief `fixes/round-1.md`).
        The D21 round done (the SHARED fixer, Claude Opus 5.5).
Date:   2026-10-14
Branch: Claude-Development-TheConnection-SHARED, from
        Claude-Development-TheConnection at c8708e5 (after P0, P1 and P2
        merged; the plan with D16, D17 and D18). Round 1 builds to the
        dev branch's plan at 1bede2c (C4 with D16, D17, D19 and D20).
        The D21 round builds to b19cd9d (C4 items 3 and 6 with D21).
Where:  ~/TheConnection-lanes/shared

## Commits

| Task | Commit | Subject (the PR line) |
|---|---|---|
| H1 | `e63e8fc` | Add tc init --shared, so separate Linux users in one group share a mailbox (C4, D16) |
| D17 | `5c4981c` | Refuse planted links in the mailbox and make the shared folders sticky (D17) |
| Handoff | `d13b0ad` | Write the SHARED handoff and its two pauses |
| Round 1 (a) | `0afc985` | Read messages only from regular files and refuse a FIFO at a lock (D19) |
| Round 1 (b) | `9d0bad8` | Build D20: nobody may delete, rename or alter another member's unread mail |
| Round 1 (c) | `cf92cee` | Init makes the four top folders; make_folder and init never leave a wrong group |
| Round 1 (d) | `6139a99` | Make the supplementary run skip with a reason, and the tests' and tags' claims true |
| Round 1, extra | `cc1b826` | Never say "no unread mail" when tc read could not move what is there |
| Round 1 (e) | `b36d4fc` | Bring the SHARED handoff and both pauses up to D19 and D20, and add route-shared QA |
| D21 | `f04944d` | Build D21: .shared is the init user's alone, and a shared send needs a card |
| D21, second | `e9f27eb` | Refuse another member's init before it changes anything, settle .shared at 0644, and date status files by lstat |
| D21, third | the commit that changes this file | Refuse a member's init over an unreadable .shared before it changes anything, and name another user's 0664 .shared |

The extra commit is one the brief did not list: writing step 13 of
`route-shared.md` (step 18 since the D21 round) showed that a read which
could move nothing still printed `no unread mail`. No amend, reset or
rebase. Nothing pushed or merged.

The three D21 commits change `tc`, `tests/test_shared.py`,
`qa/human/route-shared.md` and this file, nothing else. The second
builds the architect's yes to both D21 decisions this handoff asked for,
and two items from BOARD's review that land in SHARED's `tc`. The third
builds the architect's yes to the open question the second left: an
unreadable `.shared` another user owns, and another user's 0664 one.

Round 1 changed `tc`, `tests/test_shared.py`,
`tests/test_codex_route.py`, this file, `pauses/SHARED-1.md`,
`pauses/SHARED-2.md` and `qa/human/route-shared.md` (new).
`tests/test_codex_route.py` is the one existing test file whose
assertions D20 changed: the ring marker is never removed now, so its
D14 and D16 tests read the marker's state, not whether it exists, and
its unwritable-marker test makes a read-only marker instead of a folder
at the old `.tmp` name. Not edited: `tests/_root.py`, `CLAUDE.md`,
`contracts.md`, `phases.md`, `decisions.md`, `README.md`, `JOIN.md`.

## What was built

Every new block in `tc` carries a one-line `SHARED H1`, `SHARED D17`,
`SHARED fix round 1` or `SHARED D21` comment, each with `(Claude Opus
5.5, unreviewed)`. Every
function added or changed has `@interacts`, `@deps`, `@complexity` and
`@alloc`.

**H1, `tc init --shared` and the umask (C4, D16, D19).**

- `tc init --shared --group <g>`. `--shared` and `--group` are both
  required (a missing one is a usage error, exit 9). A group this
  machine lacks, or one the user is not in (`os.getgroups()` plus the
  effective group), is refused, exit 1, before anything is touched.
- Init makes ROOT (not shared: no group, no mode), then `mail/`,
  `status/`, `cards/` and `outbox/` when missing (D19). A ROOT it cannot
  reach is refused with words on search access, not a traceback. It then
  walks the four (`shared_entries`), one entry at a time, and gives each
  entry group g and the mode for its kind: 3775 for the four, 3770 for
  an inbox and its `read/`, 2775 for any other folder, 0664 for
  `mail/.seq`, the locks and the ring marker, 0640 for every message,
  card and status file (D20). An entry already right is left alone, so a
  rerun on a live mailbox never trips over entries other members own. A
  top folder whose own change failed is still walked. A link, a FIFO, or
  an entry the user may not change is skipped and named (with its owner
  on EPERM), first, before anything else is said.
- Last, init writes `ROOT/.shared` holding g (a `.tmp`, then a rename),
  unless it already names g. When it cannot be written, the words say
  the real state: `the mailbox stays private`, `the mailbox stays shared
  with group <h>`, or `.shared` still unreadable. Init exits 1 after the
  rest is done when it skipped anything.
- `set_shared_umask`, in `main()` ahead of `args.fn`: when `.shared`
  names a group, `os.umask(0o002)`, which makes the locks, `.seq` and
  the marker 0664. Message, card and status files pass 0640 to `os.open`
  instead, and the umask cannot add bits (D20). An unreadable `.shared`
  refuses every command but init, exit 1, with words by cause: no access
  (search access on every folder from `/` down to ROOT, and read access
  to `.shared`), or a bad file (rewrite it with init).
- `make_folder(path)` is the one place tc makes a folder. It resolves
  `.shared` and the group once per call and returns the Share. Under a
  shared mailbox each folder it makes gets group g and its mode as it is
  made (D16). When it cannot, tc removes the empty folder it just made
  and refuses with words. Under the four, a folder already there in
  another group, or a link, is refused, never accepted.
- `tc health` ends with `mailbox shared with group <g>` or `mailbox
  private`. `health_snapshot()` carries `shared_group` (the name, or
  null) and `shared_problem` (why `.shared` is unreadable, or null); it
  never raises on a bad `.shared`, so BOARD's feed keeps answering.

**D17, no planted links.**

- `open_by_name(path, flags, mode)` opens the wait, watch and inbox
  locks, `mail/.seq` and `status/<name>.md` through `open_regular`:
  `O_NOFOLLOW` and `O_NONBLOCK`, then an `S_ISREG` check. A symlink is
  refused (`is a symlink, which tc never follows`), and so is a FIFO, at
  once (`is not a regular file, which tc never opens`), exit 1. A file
  this user may not open (another member's 0640 status file) is refused
  with words naming its owner. A file already there is opened without
  `O_CREAT`; only a missing one is made, with `O_CREAT | O_EXCL`.
- `tc status` with no arguments reads each status file through
  `read_regular_file` and names on stderr the ones it will not show,
  exit 1 after showing the rest.
- A symlink, a FIFO or anything else that is not a regular file at
  `mail/.ring-pending-<name>` refuses a send to that codex name
  (nothing landed, nothing rung) and a codex join (no card written).
- `mail/`, `status/`, `cards/` and `outbox/` are 3775 (sticky).
- `check_inbox(name, shared)` lstats `mail/to-<name>` and its `read/`
  and refuses a link, or anything that is not a folder, exit 1. Under a
  shared mailbox it also refuses an inbox or `read/` whose owner differs
  from the owner of `cards/<name>.json` (D20).
- Known limit, in `ring_codex`'s doc block: codex runs as the sending
  Linux user, so a Codex session of another Linux user is probably not
  reachable by its ring. The mail still lands.

**D19, round 1.**

- `read`, `peek` and `log` lstat each `*.md` entry (`message_files`) and
  read only regular files, through `read_regular_file` with
  MESSAGE_READ_MAX_BYTES (`show`). Anything else is named on stderr and
  never read, and the command exits 1 after printing the rest. `tc read`
  leaves it in place. `tc log` never enters a linked inbox or `read/`.
  `unread()`, so `tc wait`, skips the same entries, and never wakes for
  a planted link.
- `listeners()` lstats each lock and leaves out one that is not a
  regular file, so `tc health`, `tc watch` and the board never take a
  linked lock for a listener's. `mailbox_summary` and `unread_count`
  skip a linked inbox and count only regular files.

**D20, round 1: nobody touches another member's mail.**

- An inbox and its `read/` belong to the recipient, mode 3770. Only
  `tc join` makes them, as the joining user (`claim_inbox`), and it
  refuses with words a name whose card or inbox another user owns,
  before anything is written. Under sticky, the recipient's `tc read`
  still moves every message into `read/`; a read by anyone else moves
  only that user's own messages and names the rest (`not moved to
  read/ ...; left unread`), never a traceback.
- Message, card and status files are 0640.
- A send to a name with no card and no inbox is refused, exit 1, `tc
  send: nobody has joined as <name> on this shared mailbox`, and makes
  no folder. A card with no inbox is refused with words asking its owner
  to rejoin. O1's deliver plus warning stays for a private mailbox. The
  D21 round widens the no-card refusal to a name that has an inbox
  (below).
- `mail/.seq`, the locks and the ring marker stay 0664 and are never
  removed. The marker keeps its state in its first line and is
  rewritten in place, under its own flock, never unlinked or renamed
  over, so no `.tmp` is ever left. A ring that exits 0, or a codex join
  with nothing waiting, rewrites it as `clear`. One code path, private
  or shared, as the brief recommends.

**D21, the D21 round: `.shared` is the init user's alone, and a shared
send needs a card.** These were items 1 and 2 of "Spotted, not fixed"
until D21 ruled on them.

- `.shared` is made `SHARED_MARKER_MODE`, 0644 (a new constant): the
  user who ran init reads and writes it, every other member only reads
  it. Init's umask 002 takes no bit from it, so a rewrite on a rerun with
  another group is 0644 too. tc never makes it group-writable.
- A rerun that finds `.shared` naming g does not rewrite it, and when
  this user owns it at another mode (0664, as init wrote it before D21)
  sets it to 0644 through an `O_NOFOLLOW` descriptor
  (`settle_marker_mode`, the second D21 commit, at the architect's yes).
  Another user's `.shared` is left as it is. When the group or anyone
  else may write it, the member's rerun says one line on stderr,
  `tc init: <ROOT>/.shared is 0664; ask <owner> to rerun init to tighten
  it`, and still exits 0 (the third D21 commit).
- When another user owns `.shared` (`marker_other_owner`, from `lstat`)
  and init would rewrite it, init refuses first, before the umask, the
  folders it makes and the walk, exit 1. A member's inbox, card and
  `mail/.seq` keep their mode and group. Two cases, one line each:
  - it names another group (the second D21 commit): `tc init: may not
    change <ROOT>/.shared; the mailbox stays shared with group <h>; only
    the user who ran init (<owner>) can change the group. Nothing
    changed.`
  - it cannot be read (the third D21 commit): `tc init: <ROOT>/.shared
    is owned by <owner> and unreadable to you; only the user who ran
    init (<owner>) can change the group. Nothing changed.`
  `INIT_USER_WORDS` holds the D21 line, so both say it the same way.
- So the refusal after the walk, when `.shared` cannot be written, is
  only ever about a `.shared` this user owns, or none, and carries no
  D21 line. The first D21 commit added the line there; the third took it
  out, since no other user's `.shared` reaches that point. Its own
  owner, refused by a read-only ROOT, gets the old words.
- Under a shared mailbox, a local send to a name with no card is
  refused, exit 1, with exactly `tc send: nobody has joined as <name>
  on this shared mailbox`, whether or not `mail/to-<name>/` is there.
  It is checked before a number is taken, so no message lands and
  `mail/.seq` is unchanged. The one entry a refused send makes is the
  inbox lock, `mail/.box-<name>.lock`, which every send takes before it
  routes, as before D21. A card with no inbox keeps its rejoin words.
  A private mailbox is unchanged: O1's deliver plus warning.

**From BOARD's review, in the second D21 commit.**

- `mailbox_summary` takes a status file's age from `lstat`. A link at
  `status/<name>.md`, anything that is not a regular file, or one
  `lstat` cannot reach has no status age (null). Before, `Path.exists()`
  followed a link into a folder others cannot search and raised
  PermissionError, so `tc health` died with a traceback on every run.
- `health_snapshot`'s doc block no longer says it keeps BOARD's feed
  answering; that feed builds from tc's parts and never calls it. It now
  names the real reason: `tc health` answers when `.shared` turns
  unreadable after `main()` read it, and so does a caller that loads tc
  as a module. `main()` refuses `tc health` on a `.shared` already
  unreadable, and `tc watch` does not call `health_snapshot`, so the
  block does not claim either.

**Tests.** `tests/test_shared.py`, 39 tests in seven classes, each on
`tests/_root.py`. Every class inherits `UmaskTestCase`, so each test
runs under umask 022 and a tc that never sets its own writes 0644 and
fails. `SharedTest` (H1, 4), `NoPlantedLinksTest` (D17, 5),
`RegularFilesOnlyTest` (D19 and the status age, 5),
`NobodyTouchesAnotherMembersMailTest` (D20, 8), `InitAndRefusalsTest`
(init, make_folder and the refusals' words, 8),
`SharedIsTheInitUsersAndDeliveryNeedsACardTest` (D21, 8) and
`GroupsToTestTest` (1). The mode tests run once with the
user's primary group and once with a supplementary group; a user with no
named supplementary group gets that run as a skipped subtest with its
reason, never a silent absence. One user cannot prove another user's
refusals, so the tests prove the modes, the owners and the checks tc
makes: an owner that differs is what a patched `os.lstat` reports (or,
for a member's rerun, a patched `os.geteuid`), and an EPERM rename is
injected. The cross-user proof is
`qa/human/route-shared.md`, for Donald.

## Verify

Run in `~/TheConnection-lanes/shared` on this machine (Python 3.12.3,
Node 22). Each command's result line:

| Commit | Command | Result |
|---|---|---|
| `e63e8fc` | `python3 -m unittest tests.test_shared -v` | `Ran 4 tests`, `OK` |
| `e63e8fc` | `python3 -m unittest discover -s tests -p 'test_*.py'` | `Ran 112 tests`, `OK` |
| `5c4981c` | `python3 -m unittest tests.test_shared -v` | `Ran 9 tests`, `OK` |
| `5c4981c` | `python3 -m unittest discover -s tests -p 'test_*.py'` | `Ran 117 tests`, `OK` |
| `cc1b826` | `python3 -m unittest tests.test_shared -v` | `Ran 30 tests`, `OK` |
| `cc1b826` | `python3 -m unittest tests.test_codex_route -v` | `Ran 23 tests`, `OK` |
| `cc1b826` | `python3 -m unittest discover -s tests -p 'test_*.py'` | `Ran 138 tests`, `OK` |
| D21 | `python3 -m unittest tests.test_shared -v` | `Ran 34 tests`, `OK` |
| D21 | `python3 -m unittest discover -s tests -p 'test_*.py'` | `Ran 142 tests`, `OK` |
| D21, second | `python3 -m unittest tests.test_shared -v` | `Ran 37 tests`, `OK` |
| D21, second | `python3 -m unittest discover -s tests -p 'test_*.py'` | `Ran 145 tests`, `OK` |
| D21, third | `python3 -m unittest tests.test_shared -v` | `Ran 39 tests`, `OK` |
| D21, third | `python3 -m unittest discover -s tests -p 'test_*.py'` | `Ran 147 tests`, `OK` |
| each | `node --test tests/*.test.mjs` | `# tests 8`, `# pass 8`, `# fail 0` |

The base, `c8708e5`, ran 108 Python tests and 8 Node tests, all passing.
No test skipped here: this user is not root and has a supplementary
group. `check_voice.py` and `check_american.py` are clean on this file,
both pauses and `qa/human/route-shared.md`.

## Mutations and their red runs

Method: a scratch script outside the repo made each mutation as an
exact text edit, ran the named suite, wrote the original bytes back and
compared sha256 before and after. Each row gives the assertion line,
cut short. Modes print in decimal: 1533 is 2775, 2040 is 3770, 436 is
0664, 416 is 0640.

H1 and D17, before round 1: six H1 mutations on `e63e8fc` and eight D17
mutations on `5c4981c`, each red, as listed in this file at `d13b0ad`.

Round 1, on the code of the commit named:

| Item | Mutation | Red |
|---|---|---|
| 1 (a) | `message_files` takes every entry | `'left in place' not found in 'tc read: .../read/000098-from-z.md not shown ...'` |
| 1 (a) | `show()` reads with `read_text()` | `'a file outside the mailbox; tc must not touch it\n\n---\n' != ''` |
| 3 (a) | no `O_NONBLOCK` in `open_regular` | `wait lock: tc blocked on the FIFO past 2 s` (and watch, inbox lock, status) |
| 3 (a) | no `S_ISREG` check | `'is not a regular file, which tc never opens' not found in 'Traceback ...' : mail/.seq` |
| 7 (a) | `listeners` uses `os.stat` | `{'a': <pid>, 'b': <pid>} != {'a': <pid>}` |
| 16 (a) | `mailbox_summary` follows a linked inbox | `Lists differ: ['x', 'z'] != ['x']` |
| 16 (a) | `unread_count` follows a linked inbox | `{'x': 1, 'z': 1} != {'x': 1, 'z': 0}` |
| 2 (b) | an inbox gets 2775 | `Tuples differ: ('folder', 1533, ...) != ('folder', 2040, ...)` |
| 2 (b) | join makes no inbox | `1 != 0 : tc send: b has a card but no inbox on this shared mailbox ...` |
| 2 (b) | a message, a card, a status at the umask's mode | `Tuples differ: ('file', 436, ...) != ('file', 416, ...)` (one run each) |
| 5 (b) | no send refusal | `'tc send: nobody has joined as c on this shared mailbox' not found in ...` |
| 5 (b) | no inbox and card owner check | `SystemExit not raised` |
| 5 (b) | `claim_inbox` ignores the card's owner | `SystemExit not raised` |
| 5 (b) | a ring that exits 0 unlinks the marker | `None != 'clear' : a ring that exited 0 left the marker pending` |
| 5 (b) | a join with nothing unread unlinks it | `[('failed', i), (None, None), ('clear', i)] != [('failed', i), ('clear', i), ('clear', i)]` |
| 5 (b) | `ring_owed` ignores `clear` | `Tuples differ: (0, '...rang codex c ...') != (0, '...md\n')` |
| 3 (b) | a FIFO at the marker passes | `0 != 1 : ring marker: exited 0: ring failed for x ...` |
| 13 (b) | the marker removed before each write | `Lists differ: [('failed', 4833943), ('clear', 4833937), ...]` |
| 4 (c) | init makes no top folder | `{} != {'mail': ('folder', 2045, ...), ...}` |
| 6 (c) | no `rmdir` after a failed `fchown` | `True is not false : make_folder left a folder it could not give the group` |
| 6 (c) | no group check on a folder already there | `0 != 1` (the status post went through) |
| 9 (c) | no skip for entries already right | `Tuples differ: (11, 11) != (0, 0)` |
| 10 (c) | walk only a top folder that changed | `Tuples differ: (420, ...) != (416, ...)` |
| 11 (c) | `.shared` always rewritten | `1 != 0 : tc init: could not write .../.shared (Permission denied); ...` |
| 11 (c) | skip lines not printed first | `'planted-fifo' not found in 'tc init: could not write ...'` |
| 11 (c) | always `stays private` | `'the mailbox stays shared with group tc-test-other-group' not found in ...` |
| 12 (c) | no handler on the card's rename | error: `PermissionError: [Errno 1] Operation not permitted: '.../cards/b.json.<pid>.tmp'` |
| 12 (c) | the `.tmp` not removed | `Lists differ: ['b.json.<pid>.tmp'] != []` |
| 14 (c) | one sentence for every cause | `'needs search (x) access ...' not found in "tc: .../.shared is unreadable ..."` |
| 14 (c) | init on an unreachable ROOT | `'needs search (x) access ...' not found in 'Traceback ...'` |
| 15 (c) | `health_snapshot` raises | error: `ValueError: .../.shared names no group on one line` |
| 8 (d) | `groups_to_test` without `skipTest` (test file) | `Expected 'skipTest' to be called once. Called 0 times.` |
| extra | a stuck read says `no unread mail` | `'no unread mail' unexpectedly found in 'no unread mail for b\n'` |

The D21 round, on `f04944d`'s code, each run against its one test in
`SharedIsTheInitUsersAndDeliveryNeedsACardTest` as it stood there. 436
is 0664 and 420 is 0644. `<uid>`, `<gid>`, `<group>` and `<user>` stand
for this machine's values.

| Mutation | Red |
|---|---|
| `.shared` made 0664 (`SHARED_MARKER_MODE = 0o664`) | `Lists differ: [('init', 436, <uid>, '<group>\n'), ...] != [('init', 420, <uid>, '<group>\n'), ...]` (both groups' runs) |
| delivery into a card-less inbox (refuse only with no inbox) | `0 != 1 : exited 0: sent #2 to c: .../mail/to-c/000002-from-a.md` |
| the card check reaches a private mailbox | `1 != 0 : tc send: nobody has joined as c on this shared mailbox` |
| no D21 words on another member's init | `'the mailbox stays shared with group tc-test-other-group; only the user who ran init (<user>) can change the group' not found in 'tc init: could not make .../status: ...'` |
| the D21 words for `.shared`'s own owner too | `'only the user who ran init' unexpectedly found in 'tc init: ... : told .shared's own owner to ask someone else` |

The second D21 commit, on its own code. The first three are the
architect's; the fourth reruns the D21 words after the walk against the
reworked test, whose other-owner case is now an unreadable `.shared`.

| Mutation | Test | Red |
|---|---|---|
| walk first, then refuse (the pre-walk check moved after the walk) | `test_a_members_init_with_another_group_after_joining_changes_nothing` | `{'mai[16 chars]045, <gid2>), 'outbox': ('folder', 2045, <gid2>), ...} != {'mai[16 chars]045, <gid1>), 'outbox': ('folder', 2045, <gid1>), ...}` |
| leave the mode alone on a same-group rerun | `test_an_owners_same_group_rerun_sets_a_0664_shared_to_0644` | `Tuples differ: (436, '<group>\n') != (420, '<group>\n')` |
| `Path.exists()` back in `mailbox_summary` | `test_a_status_link_into_an_unreadable_folder_leaves_health_answering` | `1 != 0 : Traceback (most recent call last): ... PermissionError: [Errno 13] Permission denied: '.../status/b.md'` |
| no D21 words after the walk | `test_another_members_init_may_not_change_the_group_and_says_who_can` | `'.../.shared stays unreadable, so tc refuses every command but init; only the user who ran init (<user>) can change the group' not found in 'tc init: could not make .../status: ...'` |

The third D21 commit, on its own code. The fourth row above no longer
applies: the third commit takes the D21 line out of the refusal after
the walk, and that test is now
`test_shareds_own_owner_refused_after_the_walk_is_never_told_to_ask_anyone`.
416 is 0640 and 420 is 0644.

| Mutation | Test | Red |
|---|---|---|
| walk first, then refuse (both pre-walk refusals moved after the walk) | `test_a_members_init_over_an_unreadable_shared_another_user_owns_changes_nothing` | `{'mai[330 chars]e', 416, <gid>), 'mail/to-b/read': ('folder', 2[57 chars]...)} != {'mai[330 chars]e', 420, <gid>), 'mail/to-b/read': ('folder', 2[57 chars]...)}` |
| the same, on the other-group case | `test_a_members_init_with_another_group_after_joining_changes_nothing` | `{'mai[16 chars]045, <gid2>), 'outbox': ('folder', 2045, <gid2>), ...} != {'mai[16 chars]045, <gid1>), ...}` |
| no line for another user's 0664 `.shared` (extra) | `test_a_members_same_group_rerun_leaves_another_users_0664_shared_and_says_so` | `'' != 'tc init: .../.shar[56 chars]it\n'` |

## Assumptions

1. **Sticky on the four and on every inbox.** D17 put it on `mail/`,
   `status/`, `cards/` and `outbox/`; D20 puts 3770 on each inbox and
   its `read/`. Any other folder under the four (`outbox/sent/`) is
   2775.
2. **Init makes the four top folders** (D19). This replaces the first
   build's "init makes no folder".
3. **The group check adds the effective group** to `os.getgroups()`. A
   process may chown to either, and some systems leave the primary group
   out of `getgroups()`.
4. **Init exits 1 when it skipped anything**, after writing `.shared`.
5. **An unreadable `.shared` refuses every command but init**, since tc
   cannot know the group and never guesses it. In process,
   `health_snapshot()` reports it as `shared_problem` instead.
6. **`shared_group` and `shared_problem` in `tc health --json` are
   interfaces the contract does not name.** C4 names only the words.
   Rename or drop them at review.
7. **No `O_CREAT` on a file already there.** With `mail/` sticky and
   group-writable, Linux with `fs.protected_regular = 2` refuses an
   `O_CREAT` open of a file another user made. This machine has 2.
8. **The link and FIFO checks hold shared or not.** A private mailbox
   loses nothing by them.
9. **`check_inbox` checks `read/` too**, and under a shared mailbox
   compares both owners with the card's.
10. **The locks keep their old open modes**: the wait and watch locks
    `O_WRONLY | O_TRUNC`, the inbox lock append, `.seq` read and append.
11. **`tc status`, `read`, `peek` and `log` exit 1 after showing the
    rest** when something is not shown, rather than stopping at the
    first.
12. **The marker's pending states keep their D16 words**: `joined with
    unread mail`, `ringing` and `failed` are C4's "pending"; `timed out`
    (its time in the mtime) and `clear` are C4's other two.
13. **Under a shared mailbox only `tc join` makes an inbox.** A wait or
    peek on a name with no inbox sees no mail and makes nothing. A
    missing `read/` in an existing inbox is not made by `tc read`; a
    rejoin makes it.
14. **C4 bullet 2's "every file group-writable" reads as replaced by D20
    items 2 and 5**, as the brief spells out: the umask stays 002 for
    the locks, `.seq` and the marker, and 0640 is passed for the rest.
    Under a private mailbox messages, cards and status files keep the
    umask's mode, as before.
15. **Init counts an entry already right as done**, and its line now
    says `in group g` rather than `set to group g`.
16. **Another member's rerun of init with the same group is not
    refused** (the D21 round). `.shared` already names g, so init leaves
    it alone (not rewritten, its mode not touched) and fixes only what
    that member owns. A group- or world-writable `.shared` stays so until
    its owner reruns; the member's rerun says one line about it and still
    exits 0.
17. **The D21 words go only where another user owns `.shared`**, found
    with `lstat`, and only before the walk: when it names another group,
    or cannot be read. Its own owner, refused by a read-only ROOT, keeps
    the old words, and a `.shared` that is gone or out of reach names no
    owner.
18. **"Unreadable to you" covers every unreadable `.shared`**, as the
    architect's words do: no read access, two lines, a link, too big, not
    UTF-8. When the folders above ROOT are what stops this user, `lstat`
    cannot reach `.shared` either, so no owner is named and init refuses
    on search access as before.
19. **The line about another user's writable `.shared` is advice, not a
    skip.** It names the mode and the owner whose rerun tightens it, and
    leaves the exit code alone. A `.shared` at 0640 or tighter (not
    writable by the group) gets no line.

## Pauses

| Pause | Status | Built |
|---|---|---|
| SHARED-1 | settled by D19 | init makes the four top folders (`cf92cee`) |
| SHARED-2 | settled by D19 | messages from regular files only; FIFOs refused (`0afc985`) |

## Spotted, not fixed

The first two items of this list in round 1 (`.shared` 0664 in its
writer's group, and a card-less inbox under a shared mailbox still
taking mail) are built in the D21 round, under "What was built". So are
the two the first D21 commit added (another member's init regrouping
that member's own entries before `.shared` refused it, and a pre-D21
0664 `.shared` kept on a same-group rerun), in the second D21 commit at
the architect's yes, and the one the second added (an unreadable
`.shared` another user owns still walked first), in the third.

1. **A rejoin keeps an inbox the joiner owns at whatever mode it has**
   (2775 from before D20). Each owner reruns init to fix their own
   entries; init cannot change another user's.
2. **A sender may still change or remove a message that sender wrote**
   (0640 keeps owner write; sticky lets a file's owner delete). D20 is
   about another member's mail. `route-shared.md` says so.
3. **The audit's RECs not in the brief are open**, among them REC-5 (the
   refusals' words), REC-6 (a login that predates the group), REC-7
   (words for a folder tc may not make after init), REC-8 (`tc health`
   on an unreadable `.shared` is still refused by `main()`), REC-9 to
   REC-16. DEBT-1 stands: `check_inbox`'s refusals, the D20 owner check
   included, leave `deliver_local` through `sys.exit`. DEBT-2 stands,
   and init gives files under `outbox/` 0640: the SSH lane decides.
4. **For the architect.** `CLAUDE.md`'s layout says the ring marker is
   "a failed codex ring"; it now stays, with `clear`. Exit row 1 in
   `contracts.md` does not list wait, read, peek, log, status or init
   (REC-18). `README.md:9` and `JOIN.md`'s `~/TheConnection/tc` (REC-17,
   REC-19) are DOCS's.
5. **For the merge with BOARD.** `health_snapshot()` has two keys more
   than at `c8708e5`: `shared_group` and `shared_problem`.
6. **For the architect: `tc watch` and `health_snapshot`.** The ask was
   to say `health_snapshot` stops raising so that `tc health` and `tc
   watch` keep answering. `tc watch` never calls it (only `cmd_health`
   does), and `main()` refuses `tc health` on a `.shared` already
   unreadable before the snapshot runs. The block says the true, smaller
   reason instead.

## Not verified

- Anything that needs a second Linux user: the kernel refusing another
  user's delete, rename or rewrite under sticky and 0640,
  `fs.protected_regular` for another user, and the EPERM paths for a
  card or a read across users. `qa/human/route-shared.md` walks them for
  Donald; it has not been run.
- The D20 owner check is shown with a patched `os.lstat`, not a real
  second owner. phases.md's other branch (a real `os.chown` when the
  test runs as root) is not written.
- The D21 cross-user cases: the kernel refusing ben's write or chmod of
  ann's `.shared`, ben's init words with a real second owner (the test
  shows them with a patched `os.lstat` and a read-only ROOT), and a
  card-less inbox another user made, a joined member's init leaving
  that member's entries as they were (another group, or a `.shared` ann
  made unreadable), and the line a member's rerun says about ann's 0664
  `.shared`. `route-shared.md` steps 6, 7, 13 to 15 and 22 walk them;
  not run.
- `test_a_members_init_with_another_group_after_joining_changes_nothing`
  needs a supplementary group and skips with its reason without one. It
  ran here.
- Five tests skip as root (a read-only file or folder cannot stop root):
  three in `InitAndRefusalsTest` and `NobodyTouchesAnotherMembersMailTest`,
  one in `SharedIsTheInitUsersAndDeliveryNeedsACardTest` and one in
  `tests/test_codex_route.py`. Not run as root here.
- The codex ring across Linux users (the known limit). Real `codex` and
  real `ssh` were never run.
