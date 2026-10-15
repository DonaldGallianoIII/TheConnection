# Handoff: SHARED (P3, wave 2)

Model:  Claude Opus 5.5 (the SHARED lane agent)
Status: unreviewed. Fix round 1 done (audit
        `audits/2026-10-14-2100-standard`, brief `fixes/round-1.md`).
        The D21 round done (the SHARED fixer, Claude Opus 5.5). Fix
        round 2 done (audit `audits/2026-10-14-2259-quick`, brief
        `fixes/round-2.md`, the SHARED fixer, Claude Opus 5.5). Fix
        round 3 done (audit `audits/2026-10-14-2358-quick`, brief
        `fixes/round-3.md`, the SHARED fixer, Claude Opus 5.5). Fix
        round 4 done (audit `audits/2026-10-15-0102-quick`, brief
        `fixes/round-4.md`, the SHARED fixer, Claude Opus 5.5). Fix
        round 5 done (audit `audits/2026-10-15-0201-quick`, brief
        `fixes/round-5.md`, its item 5 under the work set the architect
        amended to add one router test; the SHARED fixer, Claude Opus
        5.5).
Date:   2026-10-14; rounds 3 to 5 2026-10-15
Branch: Claude-Development-TheConnection-SHARED, from
        Claude-Development-TheConnection at c8708e5 (after P0, P1 and P2
        merged; the plan with D16, D17 and D18). Round 1 builds to the
        dev branch's plan at 1bede2c (C4 with D16, D17, D19 and D20).
        The D21 round builds to b19cd9d (C4 items 3 and 6 with D21).
        Round 3 builds to 6f0691e (exit row 10, C4's "Nobody can swap
        ROOT" and "A held lock costs a failed send", D20, D21, D23).
        Round 4 builds to 7211d3a (exit row 10 and C4's walk, both
        amended by the architect for this round). Round 5 builds to
        8bdf363 (C4's walk with no trust in the `.shared` owner, D28).
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
| D21, third | `0620372` | Refuse a member's init over an unreadable .shared before it changes anything, and name another user's 0664 .shared |
| Round 2 (a) | `3e4f07f` | Never let a set-back mail/.seq replace a message, and never let a held lock hang tc (D20) |
| Round 2 (b) | `3d5d8be` | Init never makes or leaves ROOT group-writable, and two joins of one name cannot both claim it (D21) |
| Round 2 (c) | `4e513cc` | Say what tc health cannot see, never a silent 0 or a traceback; true doc blocks, handoff and QA words |
| Round 3 (a) | `5ad8fb0` | Keep both files when tc read meets a taken name, exit 10 on a held lock, and give one send one lock deadline |
| Round 3 (b) | `89ce8af` | Init walks every folder from ROOT up to / and refuses a writable ROOT sticky or not; say why a send fails without hard links, and never trace back on an inbox tc cannot search |
| Round 3 (c) | `41c6019` | Say when an inbox cannot be listed, read tc's lock bound in two tests, and bring the tags, the handoff and the QA script up to round 3 |
| Round 4 (a) | `9fdd561` | Move every planted inbox file tc read meets, and name neither file as the forgery |
| Round 4 (b) | `7da32df` | Init's walk trusts the .shared owner and runs ROOT's rule on ROOT's real path; one bound per send in every path; log names a read/ it cannot see; out of numbers is busy |
| Round 4 (c) | `d4ae2f1` | Start K3's block ceiling before its spawns, fix QA steps 15, 30 and 31, and bring the tags and this handoff up to round 4 |
| Round 5 (a) | `33f2bbd` | Init's walk trusts no .shared owner again; on the init user's ROOT it names who ran init and prints the member's fix lines |
| Round 5 (b) | `707c73c` | Never claim a read for a file a hard link kept in the inbox, and keep .md on a by-hand name made of dots |
| Round 5 (c) | `334c4df` | Test K3's deadline before a finished child, say how busy leaves today, say a ring can be one fewer, and bring this handoff up to round 5 |
| Round 5 (d) | the last commit of round 5 | A send whose .tmp name is taken takes the next number, as a taken message name does |

Round 5's four commits change `tc`, `tests/test_shared.py`,
`qa/human/route-shared.md` and this file, plus one change to CORE's
`tests/test_mailbox.py` (K3's `wait_until_blocked` tests its deadline
before a finished child, item 4), as the brief allows, and one test in
CARDS' `tests/test_router.py` (item 5, as the architect amended the
work set). Commit (a) holds item 1 with its QA steps and the handoff
lines it undid, (b) items 2 and 3, (c) items 4, 6 and 7 and the rest of
this file, (d) item 5 and its lines here. Item 5 came last because the
brief's work set left out the router test it changes; the architect
added that one test. Existing tests changed: round
4's `test_the_walk_trusts_the_owner_of_an_existing_shared_and_nobody_else`
is gone (its "shared" case asserted the trust round 5 takes back, and
its third-user case cannot be reached once ROOT is refused first);
`test_a_members_same_group_rerun_leaves_another_users_0664_shared_and_says_so`
replaces the walk again, as in round 3; the wrong-group and
skipped-entry tests assert the printed lines and run them; the
long-name test adds a dots case. No other test in the tree asserts the
old remedy words (grep of `tests/` for `can fix it with`, `init again`
and `skipped;`). In commit (d), `tests/test_router.py`'s
`test_a_link_planted_at_the_message_tmp_is_refused` is renamed
`test_a_link_planted_at_the_message_tmp_is_never_written_through`, to
say what it now proves: the link is never written through, and the send
lands at the number after, exit 0, where it asserted exit 1. No other
test in the tree, and no file on the dev branch at `8bdf363`, names the
old test (grep).

Round 4's three commits change `tc`, `tests/test_shared.py`,
`qa/human/route-shared.md` and this file, plus one change to CORE's
`tests/test_mailbox.py` (K3 takes its block deadline before the spawn
loop, item 7), as the brief allows. Commit (a) holds items 1 and 2,
(b) items 3 to 6 and 9, (c) items 7, 8 and 10 and the words for the
rest (the QA steps and this file). One existing test changed its
assertions: `test_a_read_never_replaces_a_read_message_and_keeps_a_planted_one`
reads the new by-hand words. One dropped a stand-in:
`test_a_members_same_group_rerun_leaves_another_users_0664_shared_and_says_so`
no longer replaces the walk, which now passes a member's rerun on the
init user's ROOT. Before round 4 no test asserted the exit code of a
send out of numbers: grep of `tests/` for `numbers in a row` finds only
round 4's own `ALL_TAKEN_WORDS`.

Round 3's three commits change `tc`, `tests/test_shared.py`,
`qa/human/route-shared.md` and this file, plus one change each to
CORE's `tests/test_mailbox.py` (K3's block ceiling reads tc's
`LOCK_WAIT_SECONDS`, item 6) and CARDS' `tests/test_router.py` (the
shared-lock ceiling sits under it, item 8), as the brief allows. One
existing test asserted exit 1 for a held lock and now asserts 10:
`test_a_held_lock_makes_each_command_fail_within_the_bound_and_write_nothing`
in `tests/test_shared.py`. No other test in the tree asserts an exit
code for a held lock (grep of `tests/` for the lock words and ceilings).
Commit (a) also carries item 12's tags for `flock_within` and
`inbox_lock`, since it rewrote both blocks for the deadline; commit (c)
has the rest of item 12.

The extra commit is one the brief did not list: writing step 13 of
`route-shared.md` (step 18 since the D21 round) showed that a read which
could move nothing still printed `no unread mail`. No amend, reset or
rebase. Nothing pushed or merged.

Round 2's three commits change `tc`, `tests/test_shared.py`,
`qa/human/route-shared.md` and this file, plus one change to CORE's
`tests/test_mailbox.py` (K2 records `os.link`), which the brief allows
for that change only. `tests/test_codex_route.py` needed no change.

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
- Init makes ROOT (not shared: no group; 0755 since round 2, below), then `mail/`,
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
  never raises on a bad `.shared`, so `tc health` answers when `.shared`
  turns unreadable after `main()` read it, and so does a caller that
  loads tc as a module. BOARD's feed never calls it: it builds from
  `listeners()` and `mailbox_summary()` (round 2, the audit's LOW-5).

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

**Round 2: D20's bound and D21's ROOT** (audit
`audits/2026-10-14-2259-quick`, brief `fixes/round-2.md`). Every new
block in `tc` carries a `SHARED fix round 2 (Claude Opus 5.5,
unreviewed)` comment.

- No lost mail (MEDIUM-1, commit a). `deliver_local` hard-links the
  finished `.tmp` to the message's name (`os.link` fails on anything
  there, where a rename replaced it), then removes the `.tmp`. A name
  already taken in the inbox, or in its `read/` (where `tc read`
  renames), takes the next number, up to `PUBLISH_MAX_TRIES` (100), then
  refuses with words saying `mail/.seq` may have been set back. One
  code path, private or shared. Any other link failure refuses with
  words; the old rename raised a traceback and left the `.tmp` when
  another user owned the name.
- No hang (MEDIUM-3, commit a). `flock_within` waits at most
  `LOCK_WAIT_SECONDS` (3) for a flock: the wait sits in the kernel's
  queue as a plain flock does, and a one-shot `SIGALRM` timer cuts it
  off. `next_seq` and `inbox_lock` then refuse, exit 1, `tc: another
  process is holding <what>'s lock; try again` (`<what>` is the
  `mail/.seq` path, or the name for an inbox lock), with nothing
  written. Send, read, a codex join, `tc card` and the codex route all
  come through those two. `write_ring_marker` returns the same words,
  which its callers already say as a marker they could not write: the
  synthesis's unreviewed note on the marker's flock, covered. The wait
  and watch locks still refuse at once.
- ROOT (MEDIUM-2, commit b). Init makes a missing ROOT, and each missing
  folder above it, at `ROOT_MODE` 0755 under `ROOT_UMASK` 022, before
  the shared umask. It refuses a ROOT its group or anyone may write
  without the sticky bit, before anything changes, and tells ROOT's
  owner to run `chmod g-w,o-w <ROOT>` first.
- The claim (LOW-1, commit b). `claim_inbox` makes the inbox, then
  `read/`, each by an mkdir as the joiner, and looks at the owner after
  each, so the loser of two joins at once is refused with the taken
  words and makes nothing inside the winner's inbox.
- What health cannot see (LOW-2, LOW-4 and one item from BOARD's
  review, commit c). `message_files` lists with `os.listdir` (pathlib's
  glob hid a listing error) and returns a third value, the problem, when
  it could not list the folder or `lstat` an entry; an entry it could
  not look at (any `OSError` but gone) is skipped with words, never a
  traceback. `mailbox_summary` gives such an inbox `unread` null (or
  `newest_mail_age_s` null, for `read/`) and a new key, `mail_problem`,
  with the reason. `tc health` prints `unread unknown` and the reason,
  and its last line says `mailbox shared, group unknown: <why>` when
  `health_snapshot` reports `shared_problem`, never `mailbox private`.
- Doc blocks (LOW-3, commit c). `mailbox_summary`'s block no longer
  claims what the board counts: the board reads `mail/` on its own for
  its wires and links, and nothing in tc governs that.

**Round 3: no read mail lost, exit 10, nobody swaps ROOT** (audit
`audits/2026-10-14-2358-quick`, brief `fixes/round-3.md`, item numbers
are the brief's). Every new block in `tc` carries a `SHARED fix round 3
(Claude Opus 5.5, unreviewed)` comment.

- tc read never replaces a file in `read/` (item 1, MEDIUM-1, commit
  a). Under the inbox lock, before each move, it lstats `read/<name>`.
  When the name is taken (a member planted a file named like a read
  message), the file moves to the first free
  `read/by-hand-<k>-<name>` (`BY_HAND_NAME`, `by_hand_target`), and the
  read prints, just before it, `tc read: a second <name> arrived after
  the first was read. tc never reuses a number, so someone wrote this
  one by hand. The first stays in read/, unchanged; this one is kept as
  <path>:`. The inbox empties, so `tc wait` never wakes on that file
  again. The by-hand name starts with a letter, so it never matches
  `NNNNNN-from-<sender>.md`: the board's `MESSAGE_NAME` skips it, and
  `tc log`, which reads no sender from a name, shows it. The block says
  why the lstat and the rename may be two steps: only `tc read` moves
  mail into `read/`, under this lock, and under sticky no other member
  can replace or remove a file the reader moved, so a name found free
  and then taken can only be the planter's own new file. (Round 4
  replaced these words, which called the inbox file hand-written, and
  cuts the by-hand name to fit: see Round 4 below.)
- Exit 10 (item 3, D23, commit a). `EXIT_BUSY = 10`. `next_seq` and
  `inbox_lock` refuse with it, words unchanged, nothing written, so
  send, read, card, a codex join and the codex route all exit 10 on a
  held lock. The ring marker still says so as a warning.
- One deadline per command (item 5, LOW-2, commit a). `lock_deadline()`
  returns the monotonic clock plus `LOCK_WAIT_SECONDS`. `cmd_send` (local) and `deliver_codex`
  take one before the inbox lock and pass it to `inbox_lock` and
  `deliver_local`, whose every `next_seq` waits no later than it. So a
  send's waits on the inbox lock and `mail/.seq` add up to
  `LOCK_WAIT_SECONDS` at most, however many numbers it skips (C4: "per
  command"). `flock_within(f, how, deadline)` arms its timer for the time
  left; with none left it makes one `LOCK_NB` try, so a free lock is
  still taken. Each ring marker write keeps its own bound.
- Nobody can swap ROOT (item 2, MEDIUM-2, D21, D23, commit b).
  `root_walk_problem` walks every entry from ROOT up to `/`, on the path
  as given (absolute, never normalized) and on its real path, lstat
  each, and `swap_words` refuses one that root or the running user does
  not own, or that its group or anyone may write without the sticky bit.
  A link on the given path is judged by its owner; where it leads is on
  the real walk. Init runs the walk after the `.shared` refusals and
  before it makes anything, then again once ROOT is made (a ROOT another
  user made first). Exit 1, nothing changed, and the words name the
  folder, its owner and its mode.
- ROOT has no sticky exception (item 4, LOW-1, commit b): a ROOT its
  group or anyone may write is refused, sticky or not. Folders above it
  keep the exception.
- No hard links (item 7, LOW-3, commit b). When `os.link` fails with
  `EPERM`, `ENOTSUP` or `EOPNOTSUPP` (`NO_HARD_LINK_ERRNOS`), the send
  refuses, exit 1, `tc send: the filesystem under <ROOT> has no hard
  links (<why>), and tc needs them to publish a message without ever
  replacing another (D20); nothing sent. Put the mailbox (TC_ROOT) on a
  filesystem that has them, such as ext4.`
- `check_inbox` (item 9, commit b). An inbox or `read/` lstat cannot
  reach for any reason but absence is refused, exit 1, `tc: could not
  look at <path> (<why>); nothing was read or written there.`, plus the
  inbox's owner for `read/`. A send, read, peek or wait for an inbox its
  owner left without search stops with words, never a traceback.
- An inbox tc cannot list (item 10, REC-1, commit c). `inbox_messages`
  refuses, exit 1, `tc could not list <inbox> (<why>), so its unread
  mail is unknown; nothing was read or moved`, so peek, read and wait
  never say `0 unread`, `no unread mail` or time out over it. `tc log`
  names such a folder on stderr, `tc log: tc could not list <folder>
  (<why>); the mail in it is not shown`, exits 1 after the rest, and
  never says `mailbox empty` then.
- Tags (item 12): `write_new_file` says a message's `.tmp` is linked,
  never renamed; `inbox_lock` says a send holds it to its link;
  `flock_within` says it cancels an armed timer rather than putting it
  back; `write_ring_marker` names the case of one ring fewer as well as
  one more.
- Tests outside this lane's file (items 6 and 8, commit c). K3's
  `SENDERS_BLOCK_CEILING_SECONDS` in `tests/test_mailbox.py` is tc's
  `LOCK_WAIT_SECONDS`, read from tc's source (`tc_constant`, which runs
  nothing), less a one second margin: 2 s. The shared-lock test in
  `tests/test_router.py` reads the bound from a loaded tc and waits one
  second less, so a send that asks for the lock alone fails there with
  `... under tc's own 3 s bound: it asked for the lock alone`.

**Round 4: every planted file moves, no verdict, the walk trusts the
init user** (audit `audits/2026-10-15-0102-quick`, brief
`fixes/round-4.md`, item numbers are the brief's). Every new block in
`tc` carries a `SHARED fix round 4 (Claude Opus 5.5, unreviewed)`
comment.

- Every planted inbox file moves (item 1, HIGH-1, commit a). A name of
  246 bytes or more could not take the `by-hand-<k>-` prefix: the rename
  failed with "File name too long", the file stayed, and every re-armed
  `tc wait` exited 0 at once, a wake loop a member could start (D20).
  `by_hand_name(k, name, limit)` now cuts the name's stem from the end,
  one character at a time, so the whole by-hand name fits read/'s
  `os.pathconf(read, "PC_NAME_MAX")` (255 on ext4), and keeps the `.md`
  (the synthesis's option A). `by_hand_target` takes a name as free only
  when `os.lstat` raises `FileNotFoundError`; any other error is raised,
  and `cmd_read` files that message as not moved, never a traceback and
  never a guess. A planted name wakes `tc wait` at most once.
- No verdict (item 2, MEDIUM-1, commit a). A member may plant in the
  3770 `read/` as easily as in the inbox, so tc cannot tell which of
  two files of one name it wrote. The note, printed just before the
  moved file, now reads `tc read: two files had the name <name>, one in
  read/ and one in the inbox. tc never reuses a number, so one of them
  was not written by tc. Both are kept: <ROOT>/mail/to-<x>/read/<name>,
  unchanged, and <ROOT>/mail/to-<x>/read/by-hand-<k>-<name>, from the
  inbox, shown below:`. Under a shared mailbox each path is followed by
  ` (owned by <login>)` (`owner_words`, lstat at print time), a plain
  fact with no verdict (option A). The words are the same whichever file
  was planted.
- The walk trusts the init user (item 3, LOW-1, commit b; dev C4 as
  amended at `7211d3a`). `root_walk_problem` lstats `ROOT/.shared` and,
  when it is a regular file, passes its owner to `swap_words`, which
  takes a folder that user owns as it takes root's and the running
  user's. So a member's same-group rerun on the init user's ROOT passes
  the walk and reaches D21's own checks, and the remedies tc prints for
  a member's own entries (`run tc init again as their owner`, and
  make_folder's `Its owner, <x>, can fix it with tc init`) are true
  again. With no `.shared` (before the first init) only root and the
  running user pass. When a third user owns a folder, the words say
  `who is none of root, you and <x> (the owner of .shared)` and `Keep
  the mailbox under folders only root, you or <x> own.`; with no
  `.shared` they are unchanged. (Round 5 takes this trust back, D28:
  see Round 5 below.)
- ROOT's rule on ROOT's real path (item 4, LOW-2, commit b). The walk's
  `seen` set is keyed by the path and whether it is ROOT, so when
  TC_ROOT is a link to its own folder (`tc/here` to `.`) the real walk
  still runs the ROOT rule on `tc`, which the given walk passed above
  ROOT by the sticky exception. A sticky ROOT the group may write is
  refused that way too.
- One bound in every path (item 5, LOW-3, commit b). `cmd_send` takes
  one `lock_deadline()` before it routes, for every send, and hands it
  to `deliver_local` or to `deliver_codex`, which takes it as a new
  optional keyword, as `deliver_local` does. A local send whose card
  turned codex under its shared lock no longer waits a second bound in
  `deliver_codex`. Any other route (the ssh lane's `deliver_ssh`) gets
  C2's arguments alone, so C2's signature holds.
- `tc log` and a `read/` it cannot see (item 6, LOW-4, commit b).
  `cmd_log` lstats each inbox and its `read/` itself: one lstat cannot
  reach for any reason but absence is named, `tc log: tc could not look
  at <folder> (<why>); the mail in it is not shown`, the log exits 1, and
  it never says `mailbox empty` then.
- Out of numbers is busy (item 9, DEBT-3, commit b; dev exit row 10 as
  amended at `7211d3a`). A send that finds `PUBLISH_MAX_TRIES` numbers
  in a row taken exits 10, not 1, with the words unchanged: each try
  moved `mail/.seq` on, so the next send starts past them, and the ssh
  route must keep a far 10 queued (C3).
- K3's block ceiling (item 7, LOW-6, commit c). `check_fifty_senders`
  takes the block deadline before the spawn loop and hands it to
  `wait_until_blocked` (a new `deadline` keyword), so the ceiling always
  ends before any sender's own bound, which starts after its launch.
  The comment's "never" is now true.
- Words (items 8 and 10, commit c). QA step 31 makes ROOT with `mkdir
  -m 0755` and says why; step 30 has the new words, the other order and
  a long name; step 15 is a member's rerun that passes again.
  `unread_count`'s block names its silent-0 callers (`cmd_join`,
  `cmd_card`, `deliver_codex`) and says peek, read, wait and log now
  name an inbox they cannot list. Pause 5 and "Not in this round" below
  are brought up to date.

**Round 5: the strict walk again, and the LOWs** (audit
`audits/2026-10-15-0201-quick`, brief `fixes/round-5.md`, item numbers
are the brief's; dev's plan at `8bdf363`: C4's "Nobody can swap ROOT"
as amended, exit row 10, D20, D21, D23, D28). Every new block in `tc`
carries a `SHARED fix round 5 (Claude Opus 5.5, unreviewed)` comment.

- The strict walk (item 1, MEDIUM-1, commit a; D28). Round 4's trust in
  the owner of `.shared` is taken back: whoever makes ROOT can make the
  `.shared` in it, so the trust certified itself, and a member who made
  ROOT first passed the init user's own first init with exit 0. The
  walk takes a folder only from root or the running user, as in round
  3. `root_walk_problem` still lstats `ROOT/.shared`, for the words
  only (`marker_owner`). When ROOT and its `.shared` belong to one other
  user, `swap_words` names that user as the one who ran init and
  charges no one: `tc init: <ROOT> and its .shared belong to <x>, who
  ran init on this mailbox, so only <x> runs init on it. A member fixes
  their own entries by hand. Nothing changed.` Any other owner keeps
  round 3's words. The walk now returns a `WalkProblem` (words, and the
  id of the user who ran init on that case), and `refuse_walk` adds,
  after those words, the running user's own entries under the four
  that are not right yet (`own_entry_fixes`, read only), each as two
  lines, `chgrp <group> <path>` and `chmod <mode> <path>`
  (`fix_lines`), or `No entry you own under it needs a fix.` The same
  lines replace "run tc init again" in the two remedies the synthesis
  named: init's last refusal over skipped entries (`tc init: <n>
  skipped, each named above; its owner fixes each by hand, a folder or
  a file with these lines:`, then two lines per skipped folder or file)
  and `make_folder`'s refusal of a folder in the wrong group (`Its
  owner, <x>, fixes it by hand:`, then the two lines). Each word is
  shell-quoted, so a line runs as printed; the tests run them.
- A rename that did nothing (item 2, LOW-1, commit b). rename(2)
  between two names of one file does nothing and returns 0. So a member
  who hard-linked their own inbox file at the name `tc read` had just
  found free, between that lstat and the rename, kept the file in the
  inbox while the read showed it and exited 0, and the next `tc wait`
  woke at once. After each rename `cmd_read` now lstats the old name
  (`still_in_inbox`). Still there as the same file as the target
  (`os.path.samestat`), or with the target gone, the file is filed as
  not moved: `tc read: <path> not moved to read/ (it is still in the
  inbox after the move to <target>: a hard link to it, made there just
  before, makes a move do nothing); left unread`, exit 1, never shown
  or claimed as read. Still there as another file means the move was
  made and a new file took the name after it; the next read meets that
  one. Each race a member wins costs one more wake, D20's floor.
- `.md` on every cut name (item 3, LOW-2, commit b). `by_hand_name`
  takes the suffix from the name's own `.md` ending (`MESSAGE_SUFFIX`),
  not from `os.path.splitext`, which gives `"." * 253 + "md"` no suffix:
  the cut then took the `md`, and `tc log` never listed the moved file
  again.
- K3 tests its deadline first (item 4, LOW-3, commit c).
  `wait_until_blocked` in `tests/test_mailbox.py` checks its deadline
  before it looks for a finished child. Round 4's deadline already
  ended before any sender's own bound, but the first poll comes after
  all fifty spawns: spawns slower than a sender's bound (3 s) left a
  sender that had exited 10, and the test then blamed tc for not
  waiting. Now such a run fails by count of senders blocked. The
  comment's "never" (round 4) is now true.
- How busy leaves today (item 6, LOW-4, commit c). The note to the SSH
  lane under "Not in this round" said the busy refusal leaves through
  `sys.exit`. Round 4's out-of-numbers busy is a return value, so the
  note now names both ways.
- A ring can be one fewer (item 7, commit c). The comment on
  `SHARED_WRITABLE_FILE_MODE` and the paragraph after QA step 23 said a
  member's worst through the group-writable files is a failed send or
  one more ring. A member who holds the ring marker through a failed
  ring leaves it `clear`, so the next send may not ring: one fewer, which
  that send's warning says. Both now say so.
- A planted `.tmp` takes the next number (item 5, DEBT-1, commit d).
  `write_new_file` makes a message's `.tmp` with `O_EXCL` and
  `O_NOFOLLOW`, so a file or link a member planted at the next number's
  `.tmp` name (readable from the group's `mail/.seq`) raised
  `FileExistsError`, and the send refused at once, exit 1, which the ssh
  route would file as final (C3). `deliver_local` now takes that as a
  taken number and tries the next, as it does for a taken message name:
  under the same `PUBLISH_MAX_TRIES` and the same one deadline, nothing
  written through the planted entry, which is left as it is, and out of
  tries exit 10 with the words unchanged. Any other failure to make the
  `.tmp` still refuses, exit 1.

**Tests.** `tests/test_shared.py`, 66 tests in eleven classes (63
before round 5, 56
before round 4, 48 in ten before round 3, 39 in seven before round 2), each on
`tests/_root.py`. Every class inherits `UmaskTestCase`, so each test
runs under umask 022 and a tc that never sets its own writes 0644 and
fails. `SharedTest` (H1, 4), `NoPlantedLinksTest` (D17, 5),
`RegularFilesOnlyTest` (D19 and the status age, 5),
`NobodyTouchesAnotherMembersMailTest` (D20, 8), `InitAndRefusalsTest`
(init, make_folder and the refusals' words, 8),
`SharedIsTheInitUsersAndDeliveryNeedsACardTest` (D21, 8),
`NoLostMailNoHangTest` (rounds 2 to 5, 12), `RootAndClaimTest` (rounds 2
to 5, 9), `HealthSaysWhatItCannotSeeTest` (round 2, 3),
`CommandsSayWhatTheyCannotSeeTest` (rounds 3 and 4, 3) and
`GroupsToTestTest` (1). Round 4 adds seven: the by-hand words for a
plant in `read/`, a planted name of 250 bytes and of exactly the
filesystem's limit woken at most once, a card that turns codex under a
held lock, a send out of numbers, the walk's trust of the `.shared`
owner (with a patched `os.geteuid` for the member), a ROOT that links to
its own folder, and `tc log` over a `read/` it cannot see. Round 5
takes out the trust test and adds four: a member who made ROOT first
stops the init user's init, a member's rerun on the init user's ROOT
is refused with no charge and that member's fix lines (a patched
`os.geteuid` and `os.lstat`), a rename a hard link turned into
nothing (a patched `Path.rename` that links instead), and a file
planted at the next message's `.tmp` name (commit d). The long-name
test adds a case of dots and `md`, and the wrong-group and
skipped-entry tests run the lines tc prints through `/bin/sh`. The lock
test runs its eight cases at once (round 3 added "codex
send, mail/.seq"), each child under a
timeout, so it costs about two waits and a broken tc fails it instead of
hanging the suite. Round 3's deadline test runs the member as a child
process (`SEQ_HOLDER`): it plants a name in `read/` for each of
`PUBLISH_MAX_TRIES` numbers past the counter, holds `mail/.seq` 2.5 s
at a time, and takes it back as soon as the send has taken a number.
The mode tests run once with the
user's primary group and once with a supplementary group; a user with no
named supplementary group gets that run as a skipped subtest with its
reason, never a silent absence. One user cannot prove another user's
refusals, so the tests prove the modes, the owners and the checks tc
makes: an owner that differs is what a patched `os.lstat` reports (or,
for a member's rerun, a patched `os.geteuid`), and an EPERM rename is
injected. Round 3 does the same for a folder above ROOT that another
user owns (patched `os.lstat`), and for a filesystem without hard links
(patched `os.link`). The cross-user proof is
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
| Round 2 (a) | `python3 -m unittest tests.test_shared -v` | `Ran 42 tests`, `OK` |
| Round 2 (a) | `python3 -m unittest tests.test_mailbox -v` | `Ran 8 tests`, `OK` |
| Round 2 (a) | `python3 -m unittest discover -s tests -p 'test_*.py'` | `Ran 150 tests`, `OK` |
| Round 2 (b) | `python3 -m unittest tests.test_shared -v` | `Ran 45 tests`, `OK` |
| Round 2 (b) | `python3 -m unittest discover -s tests -p 'test_*.py'` | `Ran 153 tests`, `OK` |
| Round 2 (c) | `python3 -m unittest tests.test_shared -v` | `Ran 48 tests`, `OK` |
| Round 2 (c) | `python3 -m unittest discover -s tests -p 'test_*.py'` | `Ran 156 tests`, `OK` |
| Round 3 (a) | `python3 -m unittest tests.test_shared` | `Ran 50 tests`, `OK` |
| Round 3 (a) | `python3 -m unittest discover -s tests -p 'test_*.py'` | `Ran 158 tests`, `OK` |
| Round 3 (b) | `python3 -m unittest tests.test_shared` | `Ran 55 tests`, `OK` |
| Round 3 (b) | `python3 -m unittest discover -s tests -p 'test_*.py'` | `Ran 163 tests`, `OK` |
| Round 3 (c) | `python3 -m unittest tests.test_shared -v` | `Ran 56 tests`, `OK` |
| Round 3 (c) | `python3 -m unittest tests.test_mailbox -v` | `Ran 8 tests`, `OK` |
| Round 3 (c) | `python3 -m unittest tests.test_router -v` | `Ran 15 tests`, `OK` |
| Round 3 (c) | `python3 -m unittest discover -s tests -p 'test_*.py'` | `Ran 164 tests`, `OK` |
| Round 4 (a) | `python3 -m unittest tests.test_shared` | `Ran 58 tests`, `OK` |
| Round 4 (a) | `python3 -m unittest discover -s tests -p 'test_*.py'` | `Ran 166 tests`, `OK` |
| Round 4 (b) | `python3 -m unittest tests.test_shared` | `Ran 63 tests`, `OK` |
| Round 4 (b) | `python3 -m unittest discover -s tests -p 'test_*.py'` | `Ran 171 tests`, `OK` |
| Round 4 (c) | `python3 -m unittest tests.test_shared -v` | `Ran 63 tests`, `OK` |
| Round 4 (c) | `python3 -m unittest tests.test_mailbox -v` | `Ran 8 tests`, `OK` |
| Round 4 (c) | `python3 -m unittest discover -s tests -p 'test_*.py'` | `Ran 171 tests`, `OK` |
| Round 5 (a) | `python3 -m unittest tests.test_shared` | `Ran 64 tests`, `OK` |
| Round 5 (a) | `python3 -m unittest discover -s tests -p 'test_*.py'` | `Ran 172 tests`, `OK` |
| Round 5 (b) | `python3 -m unittest discover -s tests -p 'test_*.py'` | `Ran 173 tests`, `OK` |
| Round 5 (c) | `python3 -m unittest tests.test_shared -v` | `Ran 65 tests`, `OK` |
| Round 5 (c) | `python3 -m unittest tests.test_mailbox -v` | `Ran 8 tests`, `OK` |
| Round 5 (c) | `python3 -m unittest discover -s tests -p 'test_*.py'` | `Ran 173 tests`, `OK` |
| Round 5 (d) | `python3 -m unittest tests.test_shared -v` | `Ran 66 tests`, `OK` |
| Round 5 (d) | `python3 -m unittest tests.test_router -v` | `Ran 15 tests`, `OK` |
| Round 5 (d) | `python3 -m unittest discover -s tests -p 'test_*.py'` | `Ran 174 tests`, `OK` |
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

Round 2, on the code of the commit named, each run against its one
test. 509 is 0775 and 493 is 0755.

| Item | Mutation | Red |
|---|---|---|
| 1 (a) | the publish back to a rename | `b'# #6 ... after the set back\n' != b'# #6 ... the unread one\n' : a send after mail/.seq was set back replaced unread #6` (private and shared) |
| 1 (a) | no `read/` check before the link | `b'# #1 ... second\n' != b'# #1 ... first, read\n' : a read replaced read/#1 after mail/.seq was set back` (private and shared) |
| 1 (a) | K2's own (CORE's): the final name written directly | `PosixPath('.../000001-from-a.md') unexpectedly found in [...] : send created the final name 000001-from-a.md directly` |
| 3 (a) | no timer: a blocking flock at all three sites | `send, inbox lock: tc still waited 6 s on a lock this test held: it hangs` |
| 3 (a) | `next_seq` alone takes a blocking flock | `send, mail/.seq: tc still waited 6 s on a lock this test held: it hangs` |
| 3 (a) | `inbox_lock` alone takes a blocking flock | `send, inbox lock: tc still waited 6 s on a lock this test held: it hangs` |
| 3 (a) | `write_ring_marker` alone takes a blocking flock | `codex send, ring marker: tc still waited 9 s on a lock this test held: it hangs` |
| 2 (b) | ROOT made after the shared umask, as before | `{'made': 509, 'made/root': 509} != {'made': 493, 'made/root': 493} : init made ROOT or a folder above it group-writable` |
| 2 (b) | no refusal of a writable ROOT | `0 != 1` (init shared the 0775 ROOT) |
| 4 (b) | no owner check after the mkdir | `SystemExit not raised` |
| 5 (c) | the listing back to pathlib's glob | `0 is not None : tc health counted an inbox it could not list` |
| BOARD (c) | `message_files`' lstat catches `FileNotFoundError` only | `1 != 0 : Traceback ... PermissionError: [Errno 13] Permission denied: '.../mail/to-b/000001-from-a.md'` |
| 7 (c) | the last line reads `shared_group` only | `'mailbox private' == 'mailbox private' : tc health called a shared mailbox private` |

The brief's own form for item 3, a `LOCK_NB` poll, was run the same way
as evidence, not as a mutation: the new lock test passes under it, and
five existing tests in four files go red, each because it proves a tc
process is blocked on the lock in `/proc/locks`. K3 in
`tests/test_mailbox.py`, both checks: `... finished while the test held
.../mail/.seq, so it never waited for the lock`.
`test_a_codex_send_waits_for_the_inbox_lock` and
`test_read_holds_the_inbox_lock_from_glob_to_rename`
(`tests/test_codex_route.py`), `test_a_local_send_waits_for_a_held_inbox_lock`
(`tests/test_router.py`) and
`test_tc_card_counts_and_writes_under_the_inbox_lock`
(`tests/test_cards.py`): `tc exited 1 while the test held .box-<x>.lock,
so it never waited for the lock`. Assumption 20 says why the timer.

Round 3, on the code of the commit named, each run against its one
test. Method: each mutation made by hand with the editor, the test run,
the line put back, and `sha256sum tc` compared with the hash taken
before. `...` cuts a temp path or a time.

| Item | Mutation | Red |
|---|---|---|
| 1 (a) | the plain rename (no lstat of `read/<name>`) | `b"planted by hand under a read message's name\n" != b'# #3 from a to b, ...\n\nmessage 3\n' : tc read replaced read/#3 with a file planted in the inbox` (private and shared) |
| 3 (a) | `EXIT_BUSY = 1` | `1 != 10 : tc: another process is holding b's lock; try again` (each of the six refusing cases) |
| 5 (a) | each publish retry calls `next_seq()` with no deadline | `the send still ran 6 s on: each number it skipped bought a wait of its own` |
| 2 (b) | the walk checks ROOT alone, no folder above | `0 != 1 :` (the folder above ROOT at 0775, and the owner case "above ROOT") |
| 2 (b) | only the path as given is walked | `0 != 1 :` (link case "real path") |
| 2 (b) | only the real path is walked | `0 != 1 :` (link case "as given") |
| 4 (b) | ROOT keeps the sticky exception | `0 != 1 :` (mode 1777) |
| 7 (b) | no branch for `NO_HARD_LINK_ERRNOS` | `'tc send: the filesystem under .../root has no hard links (Operation not permitted), and tc needs them ...' not found in 'tc send: could not publish .../000001-from-a.md (Operation not permitted); nothing sent'` (and ENOTSUP) |
| 9 (b) | `check_inbox` catches nothing past `FileNotFoundError` | `'tc: could not look at .../mail/to-b/read (Permission denied); nothing was read or written there.' not found in 'Traceback (most recent call last): ...'` (send, read, peek and wait) |
| 10 (c) | `inbox_messages` drops the problem | `0 != 1 :` (peek, read), `2 != 1 :` (wait) |
| 10 (c) | `cmd_log` drops the problem | `0 != 1 :` (log) |
| 8 (c), evidence | a local send takes the inbox lock alone | `the send still waited 2 s on a lock the test held shared, under tc's own 3 s bound: it asked for the lock alone` |

Round 4, on the code of the commit named, each run against its test.
Method: each mutation made by hand with the editor, the test run, the
line put back, and `sha256sum -c` against the hash taken before. `...`
cuts a temp path; `<user>` is the running user's login, and `<user+1>`
the login of the next user id on this machine.

| Item | Mutation | Red |
|---|---|---|
| 1 (a) | `by_hand_name` returns the uncut name | `0 != 2 : a planted 250-byte name woke tc wait again after tc read: (0, 'MAIL: 1 unread for b. Run: tc read b\n', '')` (and the same for the 255-byte name) |
| 2 (a) | round 3's words back in `cmd_read` | `'tc read: two files had the name 000001-from-a.md, one in read/ and one in the inbox. tc never reuses a number, so one of them was not written by tc. Both are kept: .../read/000001-from-a.md, unchanged, and .../read/by-hand-1-000001-from-a.md, from the inbox, shown below:' not found in 'tc read: a second 000001-from-...` (both orders, private and shared; shared adds ` (owned by <user>)` to each path) |
| 3 (b) | the walk passes no `init_user` | `1 != 0 : tc init: .../root belongs to <user> (mode 0755), who is neither root nor you, ...` (the trust test's "shared" case, and the D21 member rerun test); the third-user case: `'tc init: ... belongs to <user+1> (mode 0700), who is none of root, you and <user> (the owner of .shared), ...' not found in ...` |
| 4 (b) | `seen` keyed by the path alone | `0 != 1 :` |
| 5 (b) | `cmd_send` calls `deliver_codex` without the deadline | `the send still waited 4 s after it began to wait: deliver_codex took a second bound of its own` |
| 6 (b) | `cmd_log`'s lstat error not added to `unlisted` | `0 != 1 :` |
| 9 (b) | the out-of-numbers refusal back to `EXIT_REFUSED` | `1 != 10 : tc send: 100 message numbers in a row were taken in .../root/mail/to-b, the last 000101-from-a.md ...` |

Round 5, on the code of the commit named, each run against its test.
Method: each mutation made by hand with the editor, the test run, the
line put back, and `sha256sum -c` against the hash taken before. The
red line is the assertion line alone.

| Item | Mutation | Test | Red |
|---|---|---|---|
| 1 (a) | the `.shared` owner trusted again (`marker_owner` added to the owners `swap_words` takes) | `test_a_member_who_made_root_first_stops_the_init_users_own_init` | `AssertionError: 0 != 1 :` (and the same in `test_a_members_rerun_on_the_init_users_root_is_refused_with_no_charge_and_their_fixes`) |
| 2 (b) | no check after the rename (`left = None`) | `test_a_rename_a_hard_link_turned_into_nothing_is_never_claimed_as_read` | `AssertionError: SystemExit not raised` |
| 3 (b) | `os.path.splitext` back in `by_hand_name` | `test_a_planted_name_at_the_length_limit_moves_and_wakes_tc_wait_at_most_once`, case `dots only` | `AssertionError: False is not true : by-hand-1-.....` (245 dots, no `.md`) |
| 5 (d) | today's exit 1 back (no `except FileExistsError: continue` in `deliver_local`) | `test_a_planted_tmp_at_the_next_number_takes_the_number_after` | `AssertionError: 1 != 0 : tc send: could not create .../root/mail/to-b/000002-from-a.tmp (File exists); nothing sent` (and `1 != 0 : exited 1: ...` the same in `test_a_link_planted_at_the_message_tmp_is_never_written_through`) |

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
20. **Round 2's bounded wait is a timer on a blocking flock, not the
    brief's `LOCK_NB` poll.** The bound, the name `LOCK_WAIT_SECONDS`,
    the words, exit 1 (10 since round 3, D23) and every caller are as the brief asks; only the
    poll step is gone. A poll never sits in the kernel's queue, so it
    breaks five tests in CORE's, CARDS' and the codex route's files that
    prove a waiter in `/proc/locks` (the evidence under Mutations), and
    those files are outside this work set. Signal handlers belong to the
    main thread, so `flock_within` runs only there; tc is one thread, and
    BOARD calls none of the three locked paths.
21. **`LOCK_WAIT_SECONDS` is 3.** An honest holder keeps a lock for
    milliseconds. K3's first sender waits for the other 49 to block
    before the test lets go (measured near 0.2 s on the owner's
    machine), so 3 s keeps that check far from its edge, and a refused
    command answers quickly. Since round 3 K3 gives its senders tc's
    bound less one second (2 s, read from tc) to block, so a slow start
    fails K3 by count, never by a sender giving up first.
22. **The no-replace check covers `read/` too.** The synthesis's
    MEDIUM-1 names `tc read`'s rename into `read/` as the same replace.
    A send now skips a number whose name is in `read/`, so a set-back
    counter never makes a later read replace history. `cmd_read` itself
    was unchanged in round 2; round 3 makes it check `read/` as well,
    for a file a member plants (round 3, item 1).
23. **The ring marker's flock is bounded too**, which the brief did not
    list and the synthesis asked about. A held marker costs a codex send
    at most two waits (before and after the ring); the mail lands and
    the send says the marker could not be cleared.
24. **The test for BOARD's `message_files` item uses mode 0640, not
    0740.** The test user owns the inbox, and at 0740 the owner keeps
    search, so `tc health` answers (checked by hand). 0640 gives the
    running user read without search, which is what a member sees in
    an owner's 0740 inbox, and it raised `PermissionError` before the
    fix.
25. **`mail_problem` is a new key in each `tc health --json` mail
    entry, and `unread` may be null.** The contract names neither.
26. **Round 3: the by-hand note is words, not a refusal.** The planted
    file is shown and moved, so `tc read` exits 0 for it; the note is on
    stdout, just before the file it is about.
27. **The by-hand name is a prefix, `by-hand-<k>-<name>`**, so it never
    matches `NNNNNN-from-<sender>.md` (a suffix would, since a C0 name may
    hold dots). `tc log` sorts names, so these come after every numbered
    message; a member could already plant any name in `read/` directly.
28. **One deadline covers the inbox lock and `mail/.seq`**, C4's "per
    command for them". The ring marker keeps `LOCK_WAIT_SECONDS` per
    write: its second write comes after a ring of up to 30 s, and a
    shared deadline would leave it none. `deliver_local` takes the
    deadline as a keyword C2's route signature leaves out; a call with
    C2's arguments alone takes its own.
29. **A deadline already past still takes a free lock** (one `LOCK_NB`
    try), so a send that used its time on held locks is refused only
    while one is held, never for being slow.
30. **The walk takes root and the running user only** (rounds 3 and 5;
    round 4 also took the owner of an existing `.shared`, and D28 took
    that back at `8bdf363`). Whoever makes ROOT can make the `.shared`
    in it, so that trust certified itself. ben's same-group rerun on
    ann's ROOT is refused, with words that name ann as the one who ran
    init and charge no one, and the lines that fix ben's own entries (QA
    step 15). `settle_marker_mode`'s line for another user's writable
    `.shared` is reached only where root owns ROOT and every folder
    above it. The `.shared` refusals (QA steps 7, 13 and 14) still come
    first and keep their words.
31. **Init walks twice**: before it makes anything (so a refusal changes
    nothing) and once ROOT is made (so a ROOT another user made first, in
    a sticky folder above, is refused).
32. **`EPERM` counts as "no hard links".** Linux's `vfs_link` answers
    `EPERM` on a filesystem without them; the `.tmp` is the sender's own
    new file, so `fs.protected_hardlinks` is not the cause.
33. **`inbox_messages` refuses only when the listing failed** (a problem
    and nothing else). An entry tc could not look at is still named by
    read and peek, which move or show the rest, as before.
34. **Round 4: a by-hand name is cut by whole characters**, from the end
    of the stem, and keeps its suffix: the name's own `.md` ending since
    round 5 (`MESSAGE_SUFFIX`), which every name `tc read` moves has
    (round 4 took `os.path.splitext`'s, which a name of dots and `md`
    does not get). A name in UTF-8 never ends in half a
    character, so a cut name can come out a byte or three under the
    limit. The limit is read once per move, from `read/`.
35. **A by-hand search error is a stuck message, not a free name.** Any
    `os.lstat` error but `FileNotFoundError`, and any `os.pathconf`
    error, leaves that message in the inbox with `not moved to read/
    (<why>); left unread`, exit 1, as any failed rename does. With the
    cut name the error no longer comes from the name's length, so no
    member can cause it by naming a file.
36. **The owners in the by-hand note are read after the lock is let go**,
    at print time, by `lstat`, so nothing slow runs under the inbox lock.
    A file's owner cannot change without root; a planter may still
    remove their own file in between, and then that path shows no owner.
37. **Only a regular `.shared` names who ran init**, and since round 5
    only in the walk's words, never as trust. A link or a FIFO at that
    name is not a `.shared` tc reads (`shared_group` refuses it), so it
    names nobody and the refusal keeps round 3's words. Its owner's own
    init is refused before the walk anyway when that owner is another
    user (D21).
38. **Every send takes its deadline before it routes**, local or codex.
    A codex send hands it to `deliver_codex`; before, `deliver_codex`
    took one at its own start, a few microseconds later. Routes other
    than `local` and `codex` get C2's four arguments today. The ssh
    lane's `deliver_ssh` needs the same `deadline` keyword, and
    `cmd_send` must hand it on, or a send whose card turns ssh under the
    shared lock waits two bounds (DEBT-2 of
    `audits/2026-10-15-0201-quick`, in the SSH brief; round 5 corrects
    this line, which said no keyword was needed).
39. **`cmd_read`'s own check of `read/<name>` stays `os.path.lexists`.**
    It answers False on an error, but a `read/` tc cannot search refuses
    the rename as well, so nothing is replaced; the brief named only
    `by_hand_target`'s check.
40. **Round 5: a member's refused init lists only that member's own
    entries**, those owned by the running user (`os.geteuid`) that are
    a folder or a regular file and not in the asked group at their
    shared mode. The list is read only (lstat, `os.walk`), made only on
    the init user's ROOT, and costs O(f) over the entries under the
    four, as init's own walk does. Another user's entries are theirs to
    fix; init's refusal over skipped entries names those.
41. **Round 5: each fix line is shell-quoted, then escaped by
    `printable`.** A name with a control character prints escaped, so
    that one line needs the real name; every name tc makes is plain. The
    mode prints as four octal digits (`3770`, `0640`), and chgrp comes
    before chmod, as tc's own changes run (a chgrp may clear setgid).
    The lines name only folders and regular files: a skipped link or
    FIFO is named on its own line with why, and has no fix line.
42. **Round 5: a file still at its old name after the rename is not
    moved only when it is the same file as the target** (or the target
    is gone). A different file there means the move was made and a new
    file took the name after it, by hand, since every send waits on the
    inbox lock `tc read` holds; the moved file is shown, and the next
    read meets the new one. The brief asked for "still there means not
    moved"; the inode test keeps a real move from being called stuck.

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
   (2775 from before D20). Since round 5 (D28) a member's init on the
   init user's ROOT is refused and prints the `chgrp` and `chmod` lines
   for that member's own entries, the inbox among them; the member runs
   them by hand. Init cannot change another user's entries, and its
   refusal over skipped entries prints the same lines for their owners.
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
4. **For the architect.** Exit row 1 in `contracts.md` does not list
   wait, read, peek, log, status or init (REC-18). `README.md:9` and
   `JOIN.md`'s `~/TheConnection/tc` (REC-17, REC-19) are DOCS's. (Round
   3, checked against the dev branch at `6f0691e`: `CLAUDE.md`'s layout
   already says the marker holds "pending, timed out or clear; never
   removed", so that half of this item is closed.)
5. **For the merge with BOARD** (round 2, the audit's LOW-5). BOARD's
   feed calls `listeners()` and `mailbox_summary()`, not
   `health_snapshot()`. What it inherits from SHARED: a linked inbox, and
   a lock that is not a regular file, drop out; counts are regular files
   only; a status file that is a link, or not a regular file, has a null
   age; each mail entry has a new `mail_problem` key, and its `unread` is
   null when tc could not list the inbox or look at an entry in it
   (`newest_mail_age_s` is null the same way for `read/`). BOARD's
   `look.js` tests `n.unread > 0`, so a null shows no count rather than a
   wrong one. Whether the board says "unknown" is no longer open: dev C5
   (a null `unread` carries `unread_problem`, and the page says `unread
   unknown`) and the P4 fix (P4FIX item 8, which builds `unread_problem`)
   decide it (round 4, the audit's LOW-8). On
   a shared mailbox a user outside the group cannot list a 3770 inbox or
   read a 0640 card, so the board belongs to a group member.
   `health_snapshot()` itself has two keys more than at `c8708e5`:
   `shared_group` and `shared_problem`.
6. **For the architect: `tc watch` and `health_snapshot`.** The ask was
   to say `health_snapshot` stops raising so that `tc health` and `tc
   watch` keep answering. `tc watch` never calls it (only `cmd_health`
   does), and `main()` refuses `tc health` on a `.shared` already
   unreadable before the snapshot runs. The block says the true, smaller
   reason instead.
7. **For the architect, round 2, checked again in round 3 against the
   dev branch at `6f0691e`.** `CLAUDE.md:55` (Architecture) still says a
   message is "written to a `.tmp` sibling and renamed"; it is linked
   now, then the `.tmp` removed. C4 item 5's "the worst a member can do
   through them is make a send fail or ring once more" needs "or once
   fewer" for the marker: with the marker's lock held through a codex
   send whose ring fails, both writes are refused, the marker stays
   `clear`, and the next send to the inbox, which is not empty, does not
   ring (the send warns that a later send may not ring). Mail is never
   lost or altered either way. Dev `contracts.md` no longer says the
   marker is removed; `phases.md:185` ("the marker is gone") is the one
   stale line left, the architect's.
8. **Spotted in round 2.** The `check_inbox` half is fixed in round 3
   (item 9): an inbox or `read/` lstat cannot reach is refused with
   words. Still open: `unread_count` counts what it can see, so an entry
   it cannot look at, or an inbox it cannot list, counts 0 for the codex
   route's ring decision, a codex join's marker and `tc card`'s refusal
   of a name with unread mail.
9. **Spotted in round 3, not fixed.** The comment on
   `SHARED_WRITABLE_FILE_MODE` in `tc` and the paragraph after step 23 of
   `route-shared.md` repeat "make a send fail or ring once more", which
   item 7 above qualifies; neither was in the brief's list (nor in
   round 4's). The long planted name this item named is fixed in round
   4 (item 1). `tests/test_router.py`'s module block says two tests load
   tc; five do now (four before round 3). Round 5 (its item 7) changes
   both lines to say a ring can come once fewer as well.
10. **Spotted in round 4, not fixed.** The synthesis's side case for
    HIGH-1 stands: a member who makes a folder at the exact by-hand name
    `tc read` chose, between its lstat and its rename, fails that one
    rename (EISDIR), and the message is named and left unread; the next
    read finds the folder and takes the next count. It needs a race won
    on each read. Round 5 (item 2) closes the silent sibling of this
    race: a hard link made at the chosen name turns the rename into
    nothing, and `tc read` now names that file as not moved, never as
    read. `qa/human/route-shared.md`'s paragraph after step 23
    and the comment on `SHARED_WRITABLE_FILE_MODE` (item 9) were
    unchanged in round 4; round 5 changes both.

## Not in this round

Round 5, as its brief says. LOW-5 of `audits/2026-10-15-0201-quick`
(C4's text on the `.shared` owner) is done on dev at `8bdf363`. LOW-6
(dev `JOIN.md` names no case for a send that exits 10, which now has
two causes) is the DOCS lane's. DEBT-2 (a future route's deadline:
`deliver_ssh` must take `cmd_send`'s one deadline, assumption 38) is in
the SSH brief. Its REC-1 and REC-2 (a codex-turn test and a gate test
for ssh; both machines need a tc with both exit-10 cases) are the SSH
lane's, and REC-3 (D23's row names only a held lock) the architect's.

Item 5 of the brief (DEBT-1: a planted `.tmp` at the next number takes
the next number, as a taken final name does) came last, in commit (d).
A link planted at a message's `.tmp` raises the same `FileExistsError`
as a planted file, so it now takes the next number too, and CARDS'
`tests/test_router.py:359` asserted exit 1 for it. That file was
outside the brief's work set. The fixer stopped there and asked; the
architect added that one test to the work set. It is renamed
`test_a_link_planted_at_the_message_tmp_is_never_written_through` and
asserts the send at the number after, exit 0, the link still a link,
and its target unchanged byte for byte.

For the SSH lane (round 5, item 6, the audit's LOW-4): a busy refusal
leaves `tc` two ways today. A lock held past `LOCK_WAIT_SECONDS` exits
10 through `sys.exit` inside `next_seq` and `inbox_lock`, so nothing
after the call runs. A send out of numbers returns
`Delivery(EXIT_BUSY, ...)` from `deliver_local`, passed up unchanged by
`deliver_codex`, to `cmd_send`, which prints its words and exits 10. So
code after a route call in the gate (C3) runs for the second case and
never for the first: D25's origin-id filing must come only after a
delivery returns 0, never merely after `route_and_deliver` returns.
`route_and_deliver` (C3) must also take one `lock_deadline` and hand it
on, as `cmd_send` does for both routes. And the sticky set for D25's
outbox layout must cover each `outbox/to-<name>/` and its `sent/` and
`refused/` (today `shared_folder_mode` gives them 2775, group-writable
and not sticky, where any member could move another member's queued
file, against D22).

Round 4, as its brief said. LOW-9 and LOW-10 of
`audits/2026-10-15-0102-quick` (the exit lists in dev `JOIN.md` and
`README.md`, which name no case for exit 10 and no `tc wait` exit 1 on
an inbox tc cannot list) are the DOCS lane's. Its DEBT-1 and DEBT-2 are
in the SSH brief, as above. Its REC-1 (assert the by-hand name against
the board's own `MESSAGE_NAME`) is the architect's, after the merge.
Its REC-2 (both machines need exit 10 before ssh sends rely on flush)
and REC-3 (the P4 fix copies `mail_problem` into `unread_problem` only
when `unread` is null) were not in that brief.

Earlier rounds: DEBT-4 (the timer ties the locked paths to the main
thread and to `ITIMER_REAL`) stays a stated limit (assumption 20).

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
- Round 2: steps 27 to 29 of `route-shared.md` (a second user setting
  `mail/.seq` back, ROOT refused, a second user holding a lock) are not
  run; the tests stand one user in for the member. The case where the
  timer fires at the instant the flock is granted (`flock_within` lets
  go and refuses) is reasoned from the code, not tested. A refused
  link for any reason but `EEXIST` (the "could not publish" words) has
  no test.
- Round 3: steps 30 and 31 of `route-shared.md`, and the new words of
  steps 15, 28 and 29, are not run. The owner rule of the walk is shown
  with a patched `os.lstat`, not a folder another user owns. A real
  filesystem without hard links (vfat, exFAT, WSL2's `/mnt/c`) was not
  tried; `os.link` was patched. The deadline test's member takes
  `mail/.seq` back as soon as it sees the counter move; were the send to
  win that race on every one of its `PUBLISH_MAX_TRIES` numbers, it
  would refuse as taken (since round 4 also exit 10, but with other
  words), and the test would fail on the words. It passed in every run
  here; how often the send won a race was not measured.
- Round 4: QA steps 15, 30 and 31 as changed are not run; no second
  Linux user. The member in the walk's trust test is a patched
  `os.geteuid`, and the third user a patched `os.lstat`. The long-name
  test ran on this machine's temp filesystem (limit 255); a filesystem
  with another `PC_NAME_MAX`, or one that counts the limit in
  characters, was not tried. The codex-turn test's card is written by
  hand under the held lock, standing in for a codex join. Step 31's
  `mkdir -m 0755` giving 2755 inside a setgid folder, and init's words
  and exit codes under 2775 and 3775 there, were checked by hand here
  as one user (the folder owned by this user, not root).
- Round 5: QA steps 15 and 31 as changed, and the paragraph after step
  23, are not run; no second Linux user. The member and the init user
  in the walk's tests are a patched `os.geteuid`, and the member's own
  entry a patched `os.lstat`; no real second owner. The hard-link race
  is shown by a patched `Path.rename` that links instead of moving; a
  real member winning that race was not tried, and neither was a new
  file made at the old name after a real move (assumption 42), which
  is reasoned from the code. The race variant of the audit's MEDIUM-1
  (ROOT missing at the first walk, made by a member before the second)
  has no test of its own: the second walk runs the same rule. The fix
  lines ran here only on entries this user owns, through `/bin/sh`;
  their quoting of a name that needs quotes is shlex's, not tested
  with such a name. Item 5's bound (a run of planted `.tmp` names to
  `PUBLISH_MAX_TRIES`, then exit 10) has no test of its own; it shares
  the loop and the for-else with the out-of-numbers test.
