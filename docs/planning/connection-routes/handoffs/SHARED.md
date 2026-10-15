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
        5.5). Fix round 6 done (audit `audits/2026-10-15-0300-quick`,
        brief `fixes/round-6.md`, the SHARED fixer, Claude Opus 5.5).
        Fix round 7 done (audit `audits/2026-10-15-0408-quick`, brief
        `fixes/round-7.md`, the SHARED fixer, Claude Opus 5.5). Fix
        round 8 done (audit `audits/2026-10-15-0840-quick`, brief
        `fixes/round-8.md` and one test the coordinator added, the
        SHARED fixer, Claude Opus 5.5).
Date:   2026-10-14; rounds 3 to 8 2026-10-15
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
        Round 6 builds to 463074c (C4's "Nobody can swap ROOT" with
        D29, exit row 10, D20, D21, D23, D29). Round 7 builds to
        ef3885c (C4 with D29; D20, D21, D29). Round 8 builds to
        5dce726 (C4 with D29; D20, D21, D23, D29).
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
| Round 5 (d) | `6230442` | A send whose .tmp name is taken takes the next number, as a taken message name does |
| Round 6 (a) | `4e7213e` | On the init user's ROOT, init fixes a member's own entries through a no-follow open, and prints no line to paste (D29) |
| Round 6 (b) | `9eeae68` | Print every path absolute, and name the last name a send found taken without blaming mail/.seq for a planted .tmp |
| Round 6 (c) | `576ca51` | Say how a member's rerun ends, fix two tags and the handoff's claims, and walk Ben's swap in the QA script |
| Round 7 (a) | `a538fa8` | Init's walks pin every folder on the way, not just the last name, so a swapped link never leads them out of the mailbox |
| Round 7 (b) | `04cae7b` | Out of tries, say only what the tries found about mail/.seq, and name both causes of the bound |
| Round 7 (c) | `dca0947` | Say the walk pins every folder on the way, in this handoff and the QA script, and walk a folder swapped on the way by hand |
| Round 8 (a) | `db66ed7` | Walk init's folders with tc's own stack walk, capped at WALK_MAX_DEPTH, and never open a link |
| Round 8 (b) | `930b0df` | Pin ROOT by identity after init's walk, so no name on the write path is resolved again, and never change a hard-linked file |
| Round 8 (c) | the last commit of round 8 | Say what round 8 makes true in this handoff and the QA lead: every folder from ROOT down pinned, and D23's chmod the only command line |

Round 7's subjects at (a) and (c) say the walk pins every folder on the
way. At round 7 that held below the four only: ROOT and the four were
still reached by path (Spotted item 11, the audit's LOW-6 of
`audits/2026-10-15-0840-quick`). Round 8 makes it true from ROOT down.
The subjects stay as committed.

Round 8's three commits change `tc`, `tests/test_shared.py`,
`qa/human/route-shared.md` and this file, nothing else. Commit (a)
holds item 2 (MEDIUM-1, LOW-1, LOW-2), (b) item 1 (HIGH-1, LOW-3) and
the coordinator's test, (c) item 3 (LOW-4 to LOW-7) and the rest of
this file. Existing tests changed in (b): `owner_patched_fstat` joins
`owner_patched_lstat`, since init now checks ROOT's owner on the open
descriptor, and the three member tests that report ROOT as the init
user's (`test_a_members_rerun_on_the_init_users_root_fixes_only_their_own_entries_through_the_fd`,
`test_a_link_swapped_in_for_a_members_entry_leaves_its_target_untouched`,
`test_a_folder_swapped_for_a_link_on_the_way_never_leads_a_members_rerun_outside`)
patch `os.fstat` that way too; and
`test_a_members_same_group_rerun_leaves_another_users_0664_shared_and_says_so`
replaces the walk with a verdict that refuses nothing and carries
ROOT's own lstat, since `root_walk_problem` no longer returns None. No
assertion in an existing test changed. No file in `tests/` but
`tests/test_shared.py` names `walk_pinned`, `walk_below`,
`root_walk_problem`, `WalkProblem`, `pin_root` or `share_entry` (grep
of `tests/`).

Round 7's three commits change `tc`, `tests/test_shared.py`,
`qa/human/route-shared.md` and this file, nothing else. Commit (a)
holds item 1 (HIGH-1), (b) items 2 and 3 (LOW-1, LOW-2), (c) item 4 and
the rest of this file. A restart of the machine (Windows Update) stopped
the round between (b) and (c); (a) and (b) were whole, and the
architect ran the suites at (b): 181 Python tests OK, 8 Node tests OK.
Existing tests changed: `test_init_walks_a_top_folder_whose_own_change_failed`
wraps `share_entry` in its new signature (`entry, where, gid, owner`);
`owner_patched_lstat` also matches an lstat made by name in a folder's
descriptor, by the file it finds (`os.path.samestat`), since the walk
no longer lstats by path; and
`test_a_send_that_finds_every_tmp_name_taken_names_the_tmp_and_blames_no_set_back`
reads LOW-1's words (`TMP_TAKEN_WHY` replaces round 6's
`TMP_AHEAD_WHY`). No test in the tree expects the words `mail/.seq was
not behind` any more (round 7's own test asserts they are absent), and
no file in `tests/` but `tests/test_shared.py` names `share_entry`
(grep of `tests/`).

Round 6's three commits change `tc`, `tests/test_shared.py`,
`qa/human/route-shared.md` and this file, nothing else. Commit (a)
holds item 1 (D29), (b) items 2 and 3, (c) items 4 and 5 and the rest
of this file. Existing tests changed: round 5's
`test_a_members_rerun_on_the_init_users_root_is_refused_with_no_charge_and_their_fixes`
is gone, its setup kept as
`test_an_entry_another_user_owns_at_its_open_is_skipped_and_never_changed`;
the wrong-group, skipped-top-folder and member-made-ROOT tests read the
new words, and the first two run the owner's init in place of the
pasted lines; `test_a_send_that_finds_every_number_taken_exits_10_and_the_next_send_lands`
reads LOW-2's words. The helpers `fix_lines_for` and `run_lines` are
gone, and `owner_patched_lstat` takes several paths. No test that
compares a printed path changed for LOW-1: every test runs with an
absolute TC_ROOT (the harness's temp folder), where `absolute()`
changes nothing. No other test in the tree asserts the round 5 words
(grep of `tests/` for `fixes their own entries by hand`, `Run these for
the entries`, `fixes it by hand` and `may have been set back`).

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
test in the tree names the old test (grep). On the dev branch the old
name is still defined, at dev `tests/test_router.py:353` (the test
itself, as CARDS wrote it); no other file there names it (grep, round
6, the audit's LOW-5). The name changes there at the merge.

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
  shell-quoted, so a line runs as printed; the tests run them. (Round 6
  takes every one of these lines out, D29: a pasted line follows a
  link. See Round 6 below.)
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
  `.tmp` still refuses, exit 1. (Round 6 changes those words: LOW-2,
  below.)

**Round 6: tc fixes a member's own entries itself, and the LOWs**
(audit `audits/2026-10-15-0300-quick`, brief `fixes/round-6.md`, item
numbers are the brief's; dev's plan at `463074c`: C4's "Nobody can
swap ROOT" with D29, exit row 10, D20, D21, D23, D29). Every new block
in `tc` carries a `SHARED fix round 6 (Claude Opus 5.5, unreviewed)`
comment.

- tc fixes the member's own entries (item 1, HIGH-1, commit a; D29).
  Round 5's `chgrp` and `chmod` lines followed a link at the path they
  named, and the owner of the folder holding each entry (the recipient,
  for a message in their inbox or `read/`; the init user, in `mail/`,
  `status/` and `cards/`) could swap one in before the member pasted
  them. Now, when the walk refuses a member's init on the init user's
  ROOT, `refuse_walk` prints the words that name the init user, ending
  `tc fixes the entries you own under it itself, and changes nothing
  else.`, and `fix_own_entries` walks the four. Each entry is lstat()ed
  first: another user's folder or regular file is passed over without a
  word. Every other entry (this user's own folder or file, and a link
  or anything else, whoever owns it) goes to `share_entry` with this
  user's id, the fd path init's own walk uses: an open with
  `O_NOFOLLOW|O_NONBLOCK`, an fstat that must find this user's own
  folder or regular file, then `fchown` and `fchmod` on the descriptor.
  A link fails the open and is named, `tc init: skipped <path>: a
  symlink, which tc never follows`; an entry another user owns at its
  open is named, `... owned by <x>, not by this user`; a fix is named,
  `tc init: fixed <path>: group <g>, mode <mode>`. Each line prints as
  it happens. The last line is `tc init: <n> fixed and <m> skipped, each
  named above. Nothing else changed.`, or `tc init: no entry you own
  under it needs a fix. Nothing changed.`, and init exits 1 either way:
  the refusal stands. `.shared`, ROOT and the group setting are never
  touched. If `.shared` no longer names `--group` by the time of the
  walk (it changed after init read it), nothing is fixed and the words
  end `Nothing changed.` `share_entry` gains the `owner` argument and a
  third return value, `changed`, so only a real change gets a line.
  `fix_lines` and `own_entry_fixes` are gone. The other two places that
  printed lines now say the owner runs `tc init --shared --group <g>`
  (`OWN_FIX_WORDS`): `make_folder`'s wrong-group refusal (`Nothing
  written. Its owner, <x>, runs tc init --shared --group <g>, which
  fixes their own entries through a no-follow open.`, one line again),
  and init's last refusal over skipped entries (`tc init: <n> skipped,
  each named above. The owner of each folder or file among them runs
  ...`; with no folder or file among them, round 5's `its owner fixes
  each by hand.`). tc prints no `chgrp` or `chmod` line for an entry
  under the four. The only command line tc prints anywhere is D23's
  `chmod g-w,o-w <path>`, which the walk's refusal (`swap_words`) gives
  the owner of ROOT, or of a folder above it, by name; the walk judges
  those folders by path, and they are root's or the running user's
  (round 8, the audit's LOW-4). (The walk still reached each entry by a
  path, so `O_NOFOLLOW` guarded its last name only; round 7 pins every
  folder below the four, and round 8 every folder from ROOT down: see
  Rounds 7 and 8 below.)
- Paths absolute (item 2, LOW-1, commit b). `ROOT` is made absolute
  once, where tc builds it, so every path tc prints names one folder
  from any working folder. The brief named `os.path.abspath`; the build
  uses `pathlib.Path.absolute()`, which the walk already used:
  `abspath` folds `..` by text, so `TC_ROOT=x/link/../root` would point
  tc at `x/root` while the kernel goes through the link's target, a
  different folder. `absolute()` reads no link and folds nothing
  (assumption 46).
- The out-of-tries words (item 3, LOW-2, commit b). `deliver_local`
  keeps the name each try found taken and names the last: the `.tmp`,
  `read/<name>`, or the message's own name in the inbox. The words say
  `mail/.seq was behind the names there: set back, or names planted
  ahead of it` only when some try found a message's name taken; when
  every try found a `.tmp`, `each by a .tmp name planted ahead;
  mail/.seq was not behind`. (Round 7 takes out the second half: LOW-1,
  below.)
- Words and tags (item 4, commit c). LOW-3: assumption 16, the D21 "Not
  verified" bullet and tc's module block now say a member's same-group
  rerun passes the walk only where root owns ROOT and every folder
  above it; on the init user's ROOT it is refused. LOW-4: `refuse`'s
  `@interacts` says it may write several lines (`refuse_lines`,
  `cmd_status`); `make_folder`'s "one line" is true again since commit
  (a). LOW-5: the claim about the old router test name on dev is
  corrected above.
- QA (item 5, commit c). Steps 15 and 31 show the new words and what
  tc fixed. New step 32 walks Ben's swap with two users: ann, as the
  recipient, swaps a link to a folder of ben's in for ben's message in
  her `read/`; ben's init says it skipped a link and fixes the message
  at its new name; ben's folder is untouched.

**Round 7: every folder below the four pinned, and the words out of tries**
(audit `audits/2026-10-15-0408-quick`, brief `fixes/round-7.md`, item
numbers are the brief's; dev's plan at `ef3885c`: C4 with D29, D20,
D21, D29). Every new block in `tc` carries a `SHARED fix round 7
(Claude Opus 5.5, unreviewed)` comment.

- One pinned walk for both walks (item 1, HIGH-1, commit a). Round 6's
  `fix_own_entries`, and init's own `shared_entries` since round 1,
  listed each folder with `os.walk`, by its path, and opened each entry
  by a path built from it. `O_NOFOLLOW` guards only the last name, so
  the owner of a folder on the way (a recipient, in their own inbox;
  the init user, in the four) could swap it for a link after the walk
  listed it, and the walk then changed the walker's own folders and
  files at the far end, outside the mailbox, to group g, folders
  `2775`, files `0640`. Both walks now go through `walk_pinned(top)`:
  - The top (`mail/`, `status/`, `cards/`, `outbox/`) is lstat()ed,
    opened with `O_RDONLY|O_NOFOLLOW|O_DIRECTORY|O_NONBLOCK`
    (`FOLDER_FLAGS`), and kept only when fstat on that descriptor finds
    the folder the lstat found. A top that is a link is named `a
    symlink, which tc never follows` (`LINK_WHY`), one that is anything
    but a folder `not a folder` (`NOT_A_FOLDER_WHY`), and one that
    changed between the lstat and the open with `NOT_ENTERED_WHY`.
  - `os.fwalk(".", dir_fd=<the top's descriptor>, follow_symlinks=False)`
    lists every folder through its descriptor and enters each subfolder
    by its name in its parent's descriptor, only when fstat finds the
    folder its lstat found.
  - Each entry is lstat()ed by its name in its folder's descriptor
    (`os.lstat(name, dir_fd=...)`), and `share_entry` opens it the same
    way (`os.open(name, O_RDONLY|O_NOFOLLOW|O_NONBLOCK, dir_fd=...)`,
    `ENTRY_FLAGS`), then fstat (the owner and type checks as before),
    then `fchown` and `fchmod` on that descriptor. `share_entry(entry,
    where, gid, owner)` takes `(dir_fd, name)` or a descriptor already
    open on the entry (the top); `where`, the path, only picks the mode
    for the entry's place and names it in the words.
  - `os.fwalk` skips a folder whose lstat and fstat differ without a
    word. So when a folder is listed, `walk_pinned` opens it once to see
    it can be entered (`can_enter`), and after the top's walk names
    each such folder `os.fwalk` did not enter: `tc init: skipped <path>:
    a folder when tc first looked, but by the time tc came to enter it a
    link or another entry had its name, or it was gone or would not
    open; tc looked at nothing under it` (`NOT_ENTERED_WHY`). It counts
    as skipped, so a member's rerun ends `<n> fixed and <m> skipped`, and
    the init user's init names it among its skips and exits 1 (with no
    folder or file among them, `its owner fixes each by hand.`).
  So below the four no path is resolved, and a folder swapped for a
  link on the way is named and never entered. The four themselves are
  still opened by their paths under ROOT (`O_NOFOLLOW` on their own
  names), so ROOT and the folders above it are resolved by name, as at
  every command (Spotted item 11).
- The out-of-tries words (item 2, LOW-1, commit b). A try that finds its
  `.tmp` taken stops before `os.link`, where a message at the number's
  own name would show, so round 6's `mail/.seq was not behind` was not
  known: a set-back counter with `.tmp` names planted at the same
  numbers got it. The words could say the counter was not behind only
  after a try reached `os.link` and found the name free of a read
  message, and such a try publishes, so out of tries they never say it
  now. When no try found a message's name taken, the why is `each by a
  .tmp name already there, so no try got as far as the message's own
  name` (`TMP_TAKEN_WHY`), and no more. `already there`, not round 6's
  `planted ahead`: a `.tmp` left by a send that died has the same name.
- The cost lines (item 3, LOW-2, commit b). `deliver_local`'s
  `@complexity` and the module block's send line say the
  `PUBLISH_MAX_TRIES` bound is reached by a set-back `mail/.seq` or by
  names planted ahead of it, `.tmp` names among them.
- Words (item 4, commit c). This file (assumptions 43, 47 and 48 to 52,
  and the rows below) and the lead paragraph of
  `qa/human/route-shared.md` said the walk pins every folder on the way.
  That held below the four only; round 8 makes it true from ROOT down
  (the audit's LOW-5 and LOW-6 of `audits/2026-10-15-0840-quick`).
  `fix_own_entries`' block said the narrower truth, made true in commit
  (a), and named what it did not pin (ROOT and above). New QA step 33: ann
  swaps her own `read/` for a link to a folder of ben's while ben's init
  runs, armed with a sleep in a second terminal. The brief named the
  parts ben (the swapper) and carol (whose init runs); the script's two
  users play them, ann as the recipient who swaps and ben as the member
  whose init runs, so no third user is needed. By hand the swap lands
  before or after the walk enters `read/`, and the step gives the words
  for both; the race inside the walk is the tests' job.

**Round 8: every folder from ROOT down pinned by identity, and tc's own
walk** (audit `audits/2026-10-15-0840-quick`, brief `fixes/round-8.md`;
item numbers are the brief's and ids the synthesis's; dev's plan at
`5dce726`: C4 with D29, D20, D21, D23, D29). The architect chose the
synthesis's option A for HIGH-1 and for MEDIUM-1. Every new block in
`tc` carries a `SHARED fix round 8 (Claude Opus 5.5, unreviewed)`
comment.

- tc's own walk (item 2, MEDIUM-1, LOW-1, LOW-2, commit a). `os.fwalk`
  recursed one generator frame per folder level, so a nest about 1000
  deep, which any member may make under the four, ended every init in a
  `RecursionError` traceback before `.shared` was written. `walk_below`
  replaces it: an explicit stack, one frame per folder from the top
  down; `os.scandir` on each folder's descriptor; each name lstat()ed by
  that name in that descriptor; each subfolder opened by its name in its
  parent's descriptor with `FOLDER_FLAGS`, and entered only when fstat
  finds the folder its lstat found. Only a name whose lstat found a
  folder is opened as one, so a link is never opened, not even to
  compare (LOW-2). The walk enters folders down to `WALK_MAX_DEPTH` (8)
  deep, counting the top as one; a folder one deeper is named and not
  entered: `tc init: skipped <path>: 9 folders deep, counting its top as
  one, past the 8 the walk enters; tc looked at nothing under it`
  (`TOO_DEEP_WHY`). A folder this user may list but not search is named
  once and left: `... this user may list it but not search (x) it; tc
  looked at nothing under it` (`NO_SEARCH_WHY`, LOW-1), where `os.fwalk`
  raised `PermissionError`. A folder that changed by the time the walk
  came to enter it is named as the walk passes it (`NOT_ENTERED_WHY`),
  so `can_enter` and round 7's list of folders not yet entered go. Every
  descriptor the walk opens is closed when it leaves that folder, and on
  every way out, a refusal included (one `finally` over the stack).
- ROOT pinned (item 1, HIGH-1, commit b). Round 7 opened each of the
  four by its path under ROOT, and a member's walk judged ROOT and
  nothing above it. Where the init user can rename ROOT (a mailbox in
  their home, or under a sticky folder), they could swap ROOT for a link
  after the walk passed it, and the member's own init then shared the
  member's own folders and files elsewhere. Now, in both walks:
  1. `root_walk_problem` always returns its `WalkProblem`, words None
     when it found nothing to refuse, carrying `root`: the lstat of the
     folder it judged at ROOT's place.
  2. `pin_root` opens ROOT once by its path
     (`O_RDONLY|O_DIRECTORY|O_NONBLOCK`, `ROOT_FLAGS`) and keeps it only
     when fstat finds that folder (`st_dev` and `st_ino`) and, on a
     member's rerun, the user who ran init as its owner. Else init
     refuses and nothing changes: `tc init: <ROOT> changed after init's
     walk looked at it: another folder or a link has its name now.
     Nothing changed.` (`ROOT_CHANGED_WORDS`; on a member's rerun, after
     the walk's words that name the init user).
  3. `walk_pinned(root_fd)` lstats each of the four by its name in
     ROOT's descriptor when the walk starts. At each top's turn it opens
     the top by its name there with `FOLDER_FLAGS`, and keeps it only
     when fstat finds the folder that first lstat found; else the top is
     named as not entered.
  4. Below each top, `walk_below` (item 2).
  5. `share_entry` opens each entry by its name in its folder's
     descriptor with `ENTRY_FLAGS` and changes it only when fstat finds
     the entry the walk's lstat found (else `another entry had its name
     by the time tc came to change it; tc changed nothing there`,
     `CHANGED_WHY`), and never a regular file with another name that it
     would change (`st_nlink` over 1): `a file with another name too (a
     hard link), which tc never changes: the change would show at every
     name` (`HARD_LINK_WHY`, LOW-3). One already right is left alone, in
     silence.

  Init's own run goes the same way: after its second walk `cmd_init`
  pins ROOT, makes the four by their names in ROOT's descriptor, walks
  them through `shared_entries(root_fd, gid)`, and writes, renames and
  settles `.shared` by its name in ROOT's descriptor (`write_new_file`
  gains `dir_fd`, and `settle_marker_mode` takes ROOT's descriptor). A
  member's rerun pins ROOT in `refuse_walk` and walks through
  `fix_own_entries(group, gid, root_fd)`. One walker signature, one
  pinned path, and ROOT's descriptor closed on every way out. So once
  the walk judged ROOT, no name on init's write path is resolved again,
  and who may rename ROOT, or a folder above it, no longer reaches the
  walk.
- What is still judged by path. ROOT's owner and every folder from ROOT
  up to `/` are judged by the walk, by path, before anything is opened
  (C4, D21, D23), and ROOT is opened once by its path and checked
  against that walk. Every other command still resolves ROOT by its
  path (DEBT-1, under Not in this round). The only command line tc
  prints is D23's `chmod g-w,o-w <path>`, to the owner of ROOT or of a
  folder above it; tc prints no `chgrp` or `chmod` line for an entry
  under the four.
- Words (item 3, commit c). LOW-4: the round 6 bullet above. LOW-5: the
  lead paragraph of `qa/human/route-shared.md`. LOW-6: round 7's heading
  and Words bullet, the note under Commits, and Not in this round.
  LOW-7: Spotted item 13. Spotted items 11 to 14 are marked closed, as
  the code now stands.

**Tests.** `tests/test_shared.py`, 78 tests in thirteen classes (73 in
eleven before round 8, 70 before round 7, 66 before round 6, 63 before round 5, 56
before round 4, 48 in ten before round 3, 39 in seven before round 2), each on
`tests/_root.py`. Every class inherits `UmaskTestCase`, so each test
runs under umask 022 and a tc that never sets its own writes 0644 and
fails. `SharedTest` (H1, 4), `NoPlantedLinksTest` (D17, 5),
`RegularFilesOnlyTest` (D19 and the status age, 5),
`NobodyTouchesAnotherMembersMailTest` (D20, 8), `InitAndRefusalsTest`
(init, make_folder, the refusals' words and absolute paths, 9),
`SharedIsTheInitUsersAndDeliveryNeedsACardTest` (D21, 8),
`NoLostMailNoHangTest` (rounds 2 to 7, 14), `RootAndClaimTest` (rounds 2
to 7, 13), `HealthSaysWhatItCannotSeeTest` (round 2, 3),
`CommandsSayWhatTheyCannotSeeTest` (rounds 3 and 4, 3),
`GroupsToTestTest` (1), `InitWalkTest` (round 8, 3) and
`RootPinnedTest` (round 8, 2). Round 4 adds seven: the by-hand words for a
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
skipped-entry tests run the lines tc prints through `/bin/sh`. Round 6
takes out round 5's rerun test and adds five: a member's rerun on the
init user's ROOT fixes only that member's own entries, through the
descriptor (os.chmod, os.chown and os.lchown asserted never called,
os.fchown and os.fchmod once each), with a case where `.shared` no
longer names the group; a link swapped in for the member's message,
before init and while tc holds the message open (a wrapped os.fchown
makes the swap), leaves its target folder's lstat as it was; an entry
another user owns at its open is skipped; a relative TC_ROOT prints
absolute paths; and a send whose every number has a planted `.tmp`
names the last `.tmp`. In these the running user is the member, and
ROOT and `.shared` are what a patched `os.lstat` reports as the init
user's. The wrong-group and skipped-entry tests now run the owner's
init in place of the lines. Round 7 adds three: a folder on the way
swapped for a link after the walk listed it, in a member's rerun and
in the init user's own init (`folder_swap`: b's inbox holds `read/`
and a second folder, each with a file not right yet, and the fix of the
file in the folder entered first, a wrapped os.fchown, renames the
other aside and links a folder outside the root at its name), each
asserting that folder, the folder and the file in it keep their stat,
the skip line, and the one file fixed; and a set-back `mail/.seq` with
a `.tmp` planted at each of its numbers, whose words never say the
counter was not behind. `owner_patched_lstat` now matches an lstat
made by name in a folder's descriptor by the file it finds. Round 8
adds five. `InitWalkTest`: a nest of WALK_MAX_DEPTH + 1 folders under
`status/`, in both walks, named past the cap with the walk's usual last
line and `.shared` written, and nothing under the named folder looked
at; a top a member may list but not search, named; and an `os.open`
spy (`open_spy`) over both walks, with links to a folder and a file
planted in an inbox, its `read/` and `status/`, that finds no call
naming a link that returned a descriptor or lacked `O_NOFOLLOW`.
`RootPinnedTest`: the coordinator's swap test, one parametrized test
of 42 subtests. Each builds a mailbox by hand at `home/mailbox` in the
root's temp folder, and two mirrors of it outside, and runs init in
process, in each walk, while one point on the write path is swapped:
ROOT's parent, ROOT, each of the four, `mail/to-b/`, its `read/`, and
the entry in it. A folder is swapped for a link to the same point in
one mirror, and for the other mirror's own folder moved in; the entry
for a link. ROOT and its parent are swapped as init opens ROOT and,
again, while `mail/`'s walk runs; every other point just before the
walk opens it, after its lstat. A wrapped `os.open` (`swap_on_open`)
makes the swap, reading `/proc/self/fd` to see where each open is
aimed. Each subtest asserts the far end of the swap keeps its mode,
owner, group and times, every entry of it, and that init names what it
refused or skipped (or, for ROOT and its parent while the walk runs,
ends as on an untouched mailbox, with `.shared` in the ROOT it opened).
The REC-4 case is in it: ROOT swapped for a link while `mail/`'s walk
runs. And a hard-linked `status/b.md`, in both walks, skipped and named,
its stat the same at both names. `as_member` runs a member's rerun with
ROOT and `.shared` reported as the init user's, by `os.lstat` and, for
ROOT's descriptor, `os.fstat` (`owner_patched_fstat`). The lock
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
| Round 6 (a) | `python3 -m unittest tests.test_shared` | `Ran 68 tests`, `OK` |
| Round 6 (a) | `python3 -m unittest discover -s tests -p 'test_*.py'` | `Ran 176 tests`, `OK` |
| Round 6 (b) | `python3 -m unittest discover -s tests -p 'test_*.py'` | `Ran 178 tests`, `OK` |
| Round 6 (c) | `python3 -m unittest tests.test_shared -v` | `Ran 70 tests`, `OK` |
| Round 6 (c) | `python3 -m unittest discover -s tests -p 'test_*.py'` | `Ran 178 tests`, `OK` |
| Round 7 (a) | `python3 -m unittest tests.test_shared` | `Ran 72 tests`, `OK` |
| Round 7 (a) | `python3 -m unittest discover -s tests -p 'test_*.py'` | `Ran 180 tests`, `OK` |
| Round 7 (b) | `python3 -m unittest tests.test_shared` | `Ran 73 tests`, `OK` |
| Round 7 (b) | `python3 -m unittest discover -s tests -p 'test_*.py'` | `Ran 181 tests`, `OK` (and the architect's run after the restart) |
| Round 7 (c) | `python3 -m unittest tests.test_shared -v` | `Ran 73 tests`, `OK` |
| Round 7 (c) | `python3 -m unittest discover -s tests -p 'test_*.py'` | `Ran 181 tests`, `OK` |
| Round 8 (a) | `python3 -m unittest discover -s tests -p 'test_*.py'` | `Ran 184 tests`, `OK` |
| Round 8 (b) | `python3 -m unittest discover -s tests -p 'test_*.py'` | `Ran 186 tests`, `OK` |
| Round 8 (c) | `python3 -m unittest tests.test_shared -v` | `Ran 78 tests`, `OK` |
| Round 8 (c) | `python3 -m unittest discover -s tests -p 'test_*.py'` | `Ran 186 tests`, `OK` |
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

Round 6, on the code of the commit named, each run against its test.
Method: each mutation made by hand with the Edit tool, the test run,
the line put back the same way, and `sha256sum -c` against the hash
taken before. The red line is the assertion line alone. `...` cuts a
temp path; `<uid>`, `<gid>` (the primary group) and `<gid2>` (the
shared, supplementary group) stand for this machine's numbers. Modes
print in decimal: 16832 is a folder at 0700, 16800 one at 0640, 17917
one at 2775.

| Item | Mutation | Test | Red |
|---|---|---|---|
| 1 (a) | a path-based chmod (`os.chmod(path, want)` in place of `os.fchmod(fd, want)` in `share_entry`) | `test_a_link_swapped_in_for_a_members_entry_leaves_its_target_untouched`, case `while tc holds it open` | `AssertionError: Tuples differ: (16800, <uid>, <gid>, ...) != (16832, <uid>, <gid>, ...)` |
| 1 (a) | no `O_NOFOLLOW` in `share_entry`'s open | the same test, case `before init` | `AssertionError: Tuples differ: (17917, <uid>, <gid2>, ...) != (16832, <uid>, <gid>, ...)` |
| 1 (a) | no owner check in `share_entry` (`if False and owner is not None ...`) | `test_an_entry_another_user_owns_at_its_open_is_skipped_and_never_changed` | `AssertionError: 'tc i[221 chars]nit: fixed .../root/status/b[107 chars]d.\n' != 'tc i[221 chars]nit: skipped .../root/status[119 chars]d.\n'` |
| 2 (b) | `.absolute()` dropped from `ROOT` | `test_a_relative_tc_root_still_names_every_path_absolute` | `AssertionError: 'sent #1 to b: root/mail/to-b/000001-from-a.md\n' != 'sent #1 to b: .../root/mail/to-b/000001-from-a.md\n'` |
| 3 (b) | the words name `path.name` again, not the name found taken | `test_a_send_that_finds_every_tmp_name_taken_names_the_tmp_and_blames_no_set_back` | `AssertionError: 'tc s[107 chars]om-a.md (each by a .tmp name planted ahead; ma[100 chars]m.\n' != 'tc s[107 chars]om-a.tmp (each by a .tmp name planted ahead; m[101 chars]m.\n'` (and `... t by 000101-from-a.md ...' != '... t by read/000101-from-a.md ...'` in `test_a_send_that_finds_every_number_taken_exits_10_and_the_next_send_lands`) |
| 3 (b) | the counter always blamed (`if True` for `if behind`) | `test_a_send_that_finds_every_tmp_name_taken_names_the_tmp_and_blames_no_set_back` | `AssertionError: 'tc s[112 chars]tmp (mail/.seq was behind the names there: set[113 chars]m.\n' != 'tc s[112 chars]tmp (each by a .tmp name planted ahead; mail/.[96 chars]m.\n'` |

Round 7, on the code of the commit named, each run against its tests.
Method: each mutation made by hand with the Edit tool, the tests run,
the line put back the same way, and `sha256sum -c` against the hash
taken before (`OK` each time). The red line is the assertion line
alone. `...` cuts a temp path or a time; `<uid>`, `<gid>` (the primary
group) and `<gid2>` (the shared, supplementary group) stand for this
machine's numbers. Modes print in decimal: 16877 is a folder at 0755,
17917 one at 2775.

| Item | Mutation | Test | Red |
|---|---|---|---|
| 1 (a) | `os.walk` back in `walk_pinned`: each folder listed by `os.walk(top)` and opened by its path (`os.open(h, os.O_RDONLY)`) in place of `os.fwalk` | `test_a_folder_swapped_for_a_link_on_the_way_never_leads_a_members_rerun_outside` | `AssertionError: Lists differ: [(168[56 chars]), (17917, <uid>, <gid2>, ...)] != [(168[56 chars]), (16877, <uid>, <gid>, ...)]` (the outside folder's subfolder made group-shared; the same in `test_a_folder_swapped_for_a_link_on_the_way_never_leads_the_init_users_own_init_outside`) |
| 1 (a), evidence | the not-entered report dropped (`for path in ():`) | the same two tests | `AssertionError: 'tc i[310 chars]nit: 1 fixed and 0 skipped, each named above. [19 chars]d.\n' != 'tc i[310 chars]nit: skipped .../root/mail/t[249 chars]d.\n'` (member); `AssertionError: 0 != 1 :` (init user: init exited 0, nothing named) |
| 2 (b) | round 6's words back (`"each by a .tmp name planted ahead; mail/.seq was not behind"` for `TMP_TAKEN_WHY`) | `test_a_set_back_counter_with_tmp_names_at_its_numbers_is_never_called_not_behind` | `AssertionError: 'not behind' unexpectedly found in 'tc send: 100 message numbers in a row were taken in .../root/mail/to-b, the last by 000100-from-a.tmp (each by a .tmp name planted ahead; mail/.seq was not behind); nothing sent. Each try moved mail/.seq on, so the next send starts past them.\n' : words about mail/.seq that no try checked` (and `AssertionError: 'tc send: 100 message numbers in a row we[218 chars]m.\n' != "tc send: 100 message numbers in a row we[240 chars]m.\n"` in `test_a_send_that_finds_every_tmp_name_taken_names_the_tmp_and_blames_no_set_back`) |

Item 3 is words in two doc blocks, with no behavior to mutate.

Round 8, on the code of the commit named, each run against its test.
Method: each mutation made by hand with the Edit tool, the test run, the
line put back the same way; then a grep for the mutated text (none
left), the build, and the full suite before the commit. No sha256 was
taken this round; the commit diffs hold only the intended hunks. The red
line is the assertion line alone. `...` cuts a temp path or a time;
`<uid>`, `<gid>` (the primary group) and `<gid2>` (the shared,
supplementary group) stand for this machine's numbers. Modes print in
decimal: 16832 is a folder at 0700, 18429 one at 3775.

| Item | Mutation | Test | Red |
|---|---|---|---|
| 2 (a) | no depth cap (`if False:` for `if depth >= WALK_MAX_DEPTH:` in `walk_below`) | `test_a_nest_past_walk_max_depth_is_named_and_never_a_traceback` | `AssertionError: 0 != 1 :` (the init user's init exited 0 and named nothing); `AssertionError: 'tc i[857 chars]nit: fixed .../root/status/d[109 chars]d.\n' != 'tc i[857 chars]nit: skipped .../root/status[187 chars]d.\n'` (a member's rerun fixed the folder past the cap). The same two lines again on (b)'s code. |
| 2 (a), evidence | `os.fwalk`'s shape: a name taken as a subfolder by `os.stat` (which follows a link) and opened without `O_NOFOLLOW` | `test_no_link_is_ever_opened_by_either_walk` | `AssertionError: Lists differ: [OpenSeen(path='linked-folder', dir_fd=5, [119 chars]rue)] != []` (both walks) |
| 1 (b) | the four reached by path again, round 7's lstat and open of `ROOT/<name>` at each top's turn (`st = os.lstat(top); fd = os.open(top, FOLDER_FLAGS)`) | `test_a_swap_at_any_point_on_the_write_path_never_leads_either_walk_outside` | `AssertionError: {'.':[232 chars]': (18429, <uid>, <gid2>, ...)...} != {'.':[232 chars]': (16832, <uid>, <gid>, ...)...}` in 8 subtests: ROOT and its parent, each swapped for a link and for a real folder while `mail/`'s walk runs, in both walks (the far end's `status/` made 3775 in the shared group) |
| 1 (b), evidence | `pin_root` keeps whatever it opens (`if True:` for its identity and owner check) | the same test | the same kind of line in the other 8 subtests on ROOT and its parent: those that swap as init opens ROOT |
| 1 (b), evidence | no `st_nlink` check (`if False:` in `share_entry`) | `test_a_hard_linked_file_is_skipped_and_named_and_unchanged_at_both_names` | `AssertionError: 0 != 1 :` (the init user's init); `AssertionError: 'tc i[209 chars]nit: fixed .../root/status/b[107 chars]d.\n' != 'tc i[209 chars]nit: skipped .../root/status[181 chars]d.\n'` (a member's rerun) |

Round 7's two swap tests
(`test_a_folder_swapped_for_a_link_on_the_way_never_leads_a_members_rerun_outside`
and `..._the_init_users_own_init_outside`) pass against the new walk, run
by name: `Ran 3 tests`, `OK`, with round 6's
`test_a_link_swapped_in_for_a_members_entry_leaves_its_target_untouched`.
Item 3 is words, with no behavior to mutate.

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
    refused by the D21 checks** (the D21 round). `.shared` already names
    g, so init leaves it alone (not rewritten, its mode not touched).
    Where the walk lets the rerun through, which since round 5 is only
    where root owns ROOT and every folder above it (assumption 30), it
    fixes only what that member owns, and a group- or world-writable
    `.shared` stays so until its owner reruns: the member's rerun says
    one line about it and still exits 0. On the init user's ROOT the
    walk refuses the rerun, exit 1, and tc fixes that member's own
    entries itself (round 6, D29, assumption 43).
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
    init and charge no one, and tc then fixes ben's own entries itself
    (round 6, D29; QA steps 15 and 32). `settle_marker_mode`'s line for another user's writable
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
    fix; init's refusal over skipped entries names those. (Round 6
    replaces the list: tc makes those changes itself, assumption 43.)
41. **Round 5: each fix line is shell-quoted, then escaped by
    `printable`.** A name with a control character prints escaped, so
    that one line needs the real name; every name tc makes is plain. The
    mode prints as four octal digits (`3770`, `0640`), and chgrp comes
    before chmod, as tc's own changes run (a chgrp may clear setgid).
    The lines name only folders and regular files: a skipped link or
    FIFO is named on its own line with why, and has no fix line. (Round
    6 prints no fix line at all, D29; the `fixed` line keeps the mode's
    four octal digits.)
42. **Round 5: a file still at its old name after the rename is not
    moved only when it is the same file as the target** (or the target
    is gone). A different file there means the move was made and a new
    file took the name after it, by hand, since every send waits on the
    inbox lock `tc read` holds; the moved file is shown, and the next
    read meets the new one. The brief asked for "still there means not
    moved"; the inode test keeps a real move from being called stuck.
43. **Round 6: which entries a member's refused init opens.** Each
    entry under the four is lstat()ed first (since round 7 by its name
    in its own folder's descriptor, never by a path: assumption 49).
    Every folder below the four is entered through its parent's
    descriptor, and since round 8 the four through ROOT's, which init
    opened once and checked (assumption 57).
    A folder or regular file
    another user owns is passed over in silence: naming every other
    member's message would bury the member's own lines. Everything else
    goes to `share_entry` with the member's id: the member's own folders
    and files, and every link, FIFO or other entry whoever owns it, so a
    link another member put there is named (C4: "a link or anything else
    is skipped and named"). fstat on the descriptor, not the lstat
    before it, decides whose an entry is, so one swapped between the
    two is skipped. A FIFO is opened with `O_NONBLOCK`, as init's own
    walk opens one, so it never blocks.
44. **Round 6: the refused init exits 1 whether or not it fixed
    anything.** The brief and C4 keep the refusal: only the init user
    runs init on that ROOT. The last line says how many were fixed and
    skipped, and `Nothing else changed.`, or that none needed a fix and
    `Nothing changed.`. Every line goes to stderr, in the order things
    happened, each printed as its change is made.
45. **Round 6: no fix unless `.shared` named `--group` when init read
    it.** Init's D21 refusals already stop another group before the
    walk. The one gap is `.shared` changing between init's read and its
    walk (a `.shared` that appeared, or that its owner rewrote): then
    `refuse_walk` changes nothing and ends `Nothing changed.`. The
    test stands in for it with `shared_group` replaced.
46. **Round 6: `ROOT` is `Path.absolute()`, not `os.path.abspath`.** The
    brief named `os.path.abspath`, for an absolute ROOT with no link
    resolved. `abspath` also folds `..` by text, which can name a
    different folder from the one the kernel finds when a link comes
    before the `..`; `absolute()` adds the working folder and nothing
    else, as `root_walk_problem` already did for the walk. The one
    difference from round 5 is when TC_ROOT is relative, and every path
    tc prints is then absolute. `board/serve.py`, on dev at `463074c`
    and not in this tree, loads tc as a module and reads `tc.ROOT`
    (`git show` and grep, read only), so it gets the absolute form of
    the same folder; serve.py was not run against round 6.
47. **Round 6: "mail/.seq was behind" means a message's name was
    taken.** tc cannot tell a set-back counter from message names
    planted ahead of it, so the words name both when any try found a
    message's name (in the inbox or `read/`) taken. When every try found
    a `.tmp` name taken, the words say so, and since round 7 nothing
    more: a try stopped at its `.tmp` never looked at the message's own
    name in the inbox, so tc does not know whether the counter was
    behind (round 6 said it was not, which a set-back counter with
    `.tmp` names at its numbers made false: the audit's LOW-1, item 2).
    The last taken name is named relative to the inbox: `read/<name>`
    for one in `read/`.
48. **Round 7: `os.fwalk(".", dir_fd=<the top's descriptor>)`, not
    `os.fwalk(top)`.** The brief named `os.fwalk(top,
    follow_symlinks=False)` and a top opened with
    `O_RDONLY|O_NOFOLLOW|O_DIRECTORY|O_NONBLOCK` and checked against its
    lstat. Handing `os.fwalk` that checked descriptor walks the folder
    the check found; `os.fwalk(top)` would open `top` by its path a
    second time, which a swap in between could change. Same function,
    same `follow_symlinks=False`; its paths are `.`-relative, and the
    printed path is the top's joined with them. (Superseded in round 8:
    `os.fwalk` is gone, and `walk_below` walks from the top's checked
    descriptor.)
49. **Round 7: entries are lstat()ed by name in their folder's
    descriptor** (`os.lstat(name, dir_fd=...)`). The brief's "no
    `os.lstat(path)`" forbids a path below the top; one name in a
    pinned folder, never followed, resolves nothing on the way. The
    lstat stays so a member's rerun passes over another user's folders
    and files in silence, as round 6 did, and fstat on the open
    descriptor still decides whose an entry is. Init's own walk gains
    that lstat too (one per entry, which `os.fwalk`'s descent and the
    not-entered names use).
50. **Round 7: a folder `os.fwalk` did not enter is named.** `os.fwalk`
    drops a folder whose fstat and lstat differ without a word, so the
    brief's "tc names what it skipped" needed more. When a folder is
    listed, `walk_pinned` opens it once (`can_enter`); one it could open
    then, and that `os.fwalk` did not enter, is named after the top's
    walk with `NOT_ENTERED_WHY`. A folder this user cannot open when it
    is listed (another member's at 0700) is not expected, so a member's
    rerun passes over it in silence as before, and init's own walk names
    it once, from its own open. A folder removed between its listing and
    its entry is named too ("or it was gone"): tc looked at nothing under
    it, which is the fact. The names come at the end of each top's walk,
    not as each folder is passed. (Superseded in round 8: `walk_below`
    opens each folder only to enter it, and names one that changed as it
    passes it; `can_enter` is gone. A folder this user may not open at
    that point still passes in silence: assumption 55.)
51. **Round 7: a top that is not a folder is named, not changed.** Init
    used to give a regular file at `mail/` (or `status/`, `cards/`,
    `outbox/`) a file's mode. The brief opens the top with
    `O_DIRECTORY`, so such a top is now `skipped <top>: not a folder`,
    with no fix (its owner fixes it by hand), and init exits 1. No test
    covers this case.
52. **Round 7: `already there`, not `planted ahead`, out of tries.** A
    `.tmp` name a send finds taken was made by a member, or left by a
    send that died between making its `.tmp` and removing it; tc cannot
    tell which, so the words say what it found.
53. **Round 8: `WALK_MAX_DEPTH` is 8, counting the top as one.** The
    brief named the constant and the three-deep mailbox, not a value.
    `outbox/to-<x>/sent` and `refused/` (C3, D25) are three deep too;
    eight leaves room for folders made by hand and holds at most eight
    descriptors open at once. A folder nine deep is listed in its
    parent, which is within the cap, so `share_entry` changes it as any
    entry, then the walk names it and looks at nothing under it.
54. **Round 8: a readable but not searchable folder is found by its
    first lstat failing.** Once a folder is open and listed, an lstat of
    a name in it fails with `EACCES` only when this user may not search
    the folder, so the first such failure names the folder
    (`NO_SEARCH_WHY`) and the walk leaves it. No probe of `.` is made.
    An empty folder of that kind passes in silence: nothing under it to
    look at.
55. **Round 8: a folder the walk may not open at its entry passes in
    silence.** As round 7's `can_enter` did. `share_entry`'s
    own open names it at its listing when the walk is init's own, or
    the folder is the member's own; another user's is theirs. Any other
    error at that open is named with its own words, and a folder gone,
    or now a link or not a folder, with `NOT_ENTERED_WHY`.
56. **Round 8: an lstat failure other than `ENOENT` or `EACCES` is
    named.** Round 7 yielded such an entry with no lstat result, and a
    member's rerun passed it over in silence. Now the walk yields its
    error's words, so both walks name it. A name gone since the listing
    is passed over, as before.
57. **Round 8: the four are lstat()ed when the walk starts, all four.**
    The brief's "kept only on samestat with its lstat in that
    descriptor" left open when that lstat is taken. Taking all four at
    the start, and opening each at its turn, is what makes a top
    swapped while `mail/`'s walk runs a changed top, named and not
    entered. Init makes the four before its walk starts, so no top is
    made in between. A top gone by its turn is named (`NOT_ENTERED_WHY`,
    "or it was gone"), where round 7 passed it in silence.
58. **Round 8: `ROOT_FLAGS` has no `O_NOFOLLOW`, as the brief says.**
    TC_ROOT may reach ROOT through a link, and the walk judged the folder
    it leads to. `O_RDONLY` needs read access on ROOT, so a ROOT this
    user may search but not read refuses: `could not open <ROOT>
    (Permission denied). Nothing changed.` Init makes ROOT 0755, so this
    arises only if ROOT's owner changed it. `O_PATH` would not need
    read, but the brief named the flags.
59. **Round 8: the folder the walk judged.** `root_walk_problem`'s
    `root` is the lstat of the first folder either walk finds at ROOT's
    own place: ROOT as given, or its real path when ROOT is reached
    through a link. When a member's walk stops at ROOT as given and
    ROOT as given is the init user's own link (`swap_words` judges a
    link by its owner), the walk never lstats the folder it leads to; it
    then lstats ROOT's real path once, and `pin_root` checks that this
    folder's owner is the init user. Without that lstat such a member's
    rerun would be refused as changed.
60. **Round 8: `share_entry` checks each entry against the walk's
    lstat.** The brief's part 5 says to open each entry by its name and
    change only a folder or a file with one name. The coordinator's
    test swaps `mail/to-b/` and its `read/` for another real folder just
    after the walk's lstat of it, and `share_entry`'s open by name would
    then change that folder's own group and mode. With the check
    (`CHANGED_WHY`), no name is changed unless it is the entry the walk
    looked at. The walk's entry for a name is now `(dir_fd, name,
    found)`.
61. **Round 8: a hard-linked file already right is left alone in
    silence.** Only a file init would change is skipped and named
    (`HARD_LINK_WHY`). It has no kind, so init's last line says its
    owner fixes each by hand (removing the extra name). A message has
    two names only between its `os.link` and its `.tmp`'s removal, so
    an init that meets one then names it, and the next run clears it.
62. **Round 8: init's own run uses the pinned path past the walk.** The
    brief named the walk. Init also makes the four, and writes, renames
    and settles `.shared`; by path, each of those would follow a ROOT or
    a parent swapped while `mail/`'s walk runs, and the coordinator's
    test asserts nothing outside changes then in the init user's own
    init too. So each is done by name in ROOT's descriptor:
    `os.mkdir(name, dir_fd=...)`, `write_new_file(..., dir_fd=...)`,
    `os.rename(..., src_dir_fd=..., dst_dir_fd=...)`, and
    `settle_marker_mode(marker, root_fd)`. The words still name the
    paths. A top init could not make is named before the walk's skips
    now (all four are made, then walked), where round 7 named it in its
    top's turn.
63. **Round 8: `root_walk_problem` always returns its verdict.** A
    `WalkProblem` with words None means nothing to refuse; it carries
    `root` either way. `swap_words` still returns None for a safe entry,
    and `WalkProblem`'s third field defaults to None.

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
   (2775 from before D20). Since round 6 (D29) a member's init on the
   init user's ROOT is refused and then fixes that member's own
   entries, the inbox among them, through a no-follow open (round 5
   printed lines to paste instead). Init cannot change another user's
   entries, and its refusal over skipped entries tells their owners to
   run `tc init --shared --group <g>`, which does the same for theirs.
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
11. **Closed in round 8 (item 1, HIGH-1).** ROOT is opened once after
    the walk and checked against the folder it judged (and, on a
    member's rerun, its owner), and the four are opened by name in its
    descriptor, as the fix below proposed. What follows is the round 7
    text. **Spotted in round 7, not fixed: ROOT is not pinned (for the
    architect, HIGH by the synthesis's rule).** `walk_pinned` opens each
    of the four by its path under ROOT, as the brief says, so ROOT and
    every folder above it are resolved by name, once per top. In a
    member's rerun, ROOT is the init user's, and `root_walk_problem`
    stops at ROOT, so nothing checks the folders above it. Where the
    init user owns ROOT's parent (a mailbox in their home), they can
    rename ROOT and put a link to a folder of the member's at its name
    after the walk's lstat of ROOT, or between one top and the next (a
    big `mail/` widens that gap). The member's init then opens that
    folder's `mail/` (or `status/`, `cards/`, `outbox/`) and makes the
    member's own entries there group-shared. It needs such a folder to
    exist under the link's target. A fix: open ROOT once, open the four
    by name in its descriptor with `FOLDER_FLAGS`, and check ROOT's
    descriptor against the walk's lstat of ROOT's real path. Not done:
    the brief starts the pin at the top folder, and the change is the
    architect's to make (C4's D29 lines, merge item 9).
12. **Closed in round 8 (item 1, LOW-3), in both walks, not a member's
    alone.** `share_entry` never changes a regular file with another
    name that it would change (`HARD_LINK_WHY`). The round 7 text:
    **Spotted in round 7, not fixed: a hard link is not a link.** A
    member who may read and write another member's file outside the
    mailbox may hard-link it into the mailbox (`fs.protected_hardlinks`
    allows that). fstat then finds the other member's own regular file,
    and that member's init gives it group g and 0640. No folder on the
    way is swapped, so the pinned walk cannot tell. A check that refuses
    a regular file with more than one link (`st_nlink > 1`) in a
    member's own walk would close it. The precondition (write access to
    the file already) keeps it LOW.
13. **Closed in round 8 (item 2, LOW-2).** `os.fwalk` is gone, and
    `walk_below` opens only a name whose lstat found a folder, with
    `O_NOFOLLOW`. The round 7 text read narrower than the code (the
    audit's LOW-7): `os.fwalk` opened the target of every link to a
    folder under the four, on every init, in both walks; a folder
    swapped for a link was one case of that. **Spotted in round 7, not fixed:
    `os.fwalk` opens before it compares.** For a folder swapped for a
    link, `os.fwalk` opens the name (following the link) and only then
    finds the fstat differs, so tc opens, and never changes, what the
    link points at, for an instant. A FIFO opens without blocking; a
    device node would be opened and closed. LOW.
14. **Closed in round 8 (item 3, LOW-4).** The round 6 bullet now says
    tc prints no `chgrp` or `chmod` line for an entry under the four,
    and that D23's `chmod g-w,o-w` advice to the owner of ROOT or a
    folder above it is the only command line tc prints. The code is
    unchanged. The round 7 text: **Spotted in round 7 (the synthesis's
    note), not fixed.** Round 6's
    bullet above says "tc prints no `chgrp` or `chmod` line anywhere".
    D23's walk refusals (`swap_words`) still tell the owner of ROOT, or
    of a folder on the way to it, to run `chmod g-w,o-w <path>` first
    (also under round 2's ROOT bullet). Those name folders root or the
    running user owns, not entries under the four, so the round 5
    mechanism does not apply; the sentence reads wider than the code.
15. **Spotted in round 8, not fixed: `.shared` is read by path before
    the walk.** Init reads `.shared` (`shared_group`) and its owner
    (`marker_other_owner`, and `root_walk_problem`'s `marker_owner`) by
    their paths under ROOT, before the walk and before `pin_root`. So
    the group a member's rerun fixes toward is checked against the
    `.shared` that ROOT's path named then, which a swap of ROOT between
    that read and the walk could make another folder's. Nothing outside
    the mailbox follows from it: the pinned walk changes only the
    member's own entries in the ROOT the walk judged, toward the group
    the member asked for with `--group` and is in. The worst is a fix
    toward a group the pinned ROOT's `.shared` does not name. LOW. A fix:
    read `.shared` again by its name in ROOT's descriptor after
    `pin_root`, and refuse when it does not name `--group`.

## Not in this round

Round 8, as its brief says. DEBT-1 of `audits/2026-10-15-0840-quick`
(every other command resolves ROOT by its path, and C4's "Nobody can
swap ROOT" walk runs only inside init) stays a stated limit: init's
write path is pinned from ROOT down; `send`, `read` and the rest under
a swapped ROOT were not traced. LOW-8 and LOW-9 (dev's C4 D29 lines at
`contracts.md:369` to `377`; dev `CLAUDE.md:342` and
`00-index.md:7` to `10`) are the architect's at the merge. For C4's D29
lines (the synthesis's merge item 9, option A), what the code now
holds: ROOT is opened once after the walk and kept only when it is the
folder the walk judged (and, on a member's rerun, the init user's);
the four and every folder below them are opened by name in their
parent's descriptor and kept only when fstat finds what lstat found;
each entry is opened by name in its folder's descriptor and changed only
when it is the entry the walk found and, for a regular file, has one
name; a link, anything else, a folder past `WALK_MAX_DEPTH`, and a
folder or entry found changed are skipped and named. ROOT's owner and
the folders above it are judged by the walk, by path. REC-1 is moot
(option A for MEDIUM-1). REC-3 (a known-bugs entry, "a no-follow open
guards the last name only") is the architect's. REC-4 is done: the
coordinator's swap test holds it (ROOT swapped for a link, or for
another folder, while `mail/`'s walk runs, in both walks).

Round 7, as its brief says. LOW-3 of `audits/2026-10-15-0408-quick`
(`tc watch --names` says `LISTENER DOWN` for a `tc wait` that exited 0
on mail; pre-existing, and on dev's known-bugs list at `ef3885c`) rides
with D28's follow-up (`tc wait` writes its exit reason into its lock
file). LOW-4 to LOW-8 (dev's `CLAUDE.md:57`, `contracts.md` C2's
`deliver_local` line, C1's "like a message", C4's modes and "ring once
more", and the comments in dev's `tests/test_board_feed.py:253` and
`tests/test_board_leak.py:133`) and the synthesis's "Merge commit
changes on dev" (items 1 to 9, among them taking SHARED's side of
`tests/test_router.py`, and C4's D29 lines) are the architect's, at the
merge. Round 7 handed over "every folder on the way is pinned" for
those lines; at round 7 that held below the four only (the audit's
LOW-6 of `audits/2026-10-15-0840-quick`), and round 8, above, gives the
wording that holds now. REC-2 is done: the two swap tests in commit (a).

Round 6, as its brief says. REC-1 of `audits/2026-10-15-0300-quick`
(D28's follow-up writes a listener's exit reason into its wait lock, a
file every member may write, so it needs a record only the listener's
user can write) is the architect's, for that later task. REC-2 (both
machines need a tc with round 5 before flush is relied on) and REC-3
(the lifted publish keeps round 5's `.tmp` skip ahead of the general
`OSError`, and the outbox needs its own words) are in the SSH brief.
LOW-6 (the SSH brief's premise that busy leaves only through
`sys.exit`, and its reading list) is fixed in the SSH brief. Round 6
changes the out-of-tries words (LOW-2), which the SSH lane's outbox
version of the publish should follow.

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
  card-less inbox another user made, and a joined member's init leaving
  that member's entries as they were (another group, or a `.shared` ann
  made unreadable). `route-shared.md` steps 6, 7, 13, 14 and 22 walk
  them; not run. The line a member's rerun says about another user's
  0664 `.shared` shows only where root owns ROOT and every folder above
  it (assumption 30); no QA step builds that, and step 15 now expects
  the walk's refusal on ann's ROOT. Its test replaces the walk.
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
  the loop and the for-else with the out-of-numbers test. (Round 6
  adds that test, for LOW-2.)
- Round 6: QA steps 15, 31 and 32 as changed are not run; no second
  Linux user. In the tests the member is the running user, and the init
  user's ROOT and `.shared` are a patched `os.lstat`; the link a member
  swaps in is this user's own, and the swap while tc holds the entry
  open is made from a wrapped `os.fchown`, not by another process
  racing tc. A real recipient who swaps a link in for another member's
  message, owning the link, is step 32; the code names a link whoever
  owns it (assumption 43), which the tests show only for this user's
  own link. The `.shared`-changed case is a replaced `shared_group`,
  not a real rewrite between init's read and its walk. `board/serve.py`
  was not run with a relative TC_ROOT (assumption 46).
- Round 7: QA step 33, and the lead paragraph as changed, are not run;
  no second Linux user. In the swap tests the swap is made from a
  wrapped `os.fchown` inside tc's own process, at the one moment that
  matters (after the walk listed the folder, before it entered it), not
  by another process racing tc; the folder swapped and the link are this
  user's own, and the other owner is a patched `os.lstat`. Which of the
  two folders the walk enters first is the filesystem's listing order;
  the tests swap whichever comes second, so both orders pass, but only
  the order this machine gave was run. Not tested: a top that is not a
  folder (assumption 51), a top swapped between its lstat and its open,
  a folder that is gone or will not open between its listing and its
  entry (assumption 50), and Spotted items 11 to 13.
- Round 8: the QA lead paragraph as changed is not run, and no QA step
  swaps ROOT: in the script's setup ROOT sits under root's `/srv`, where
  only root may rename it, so HIGH-1 cannot be reached there. In the
  tests every swap is made from a wrapped `os.open` inside tc's own
  process, at the moments named (as init opens ROOT, while `mail/`'s
  walk runs, just before the walk opens a point), not by another process
  racing tc; the folders swapped and the links are this user's own, and
  the init user is a patched `os.lstat` and `os.fstat`. The nest test is
  WALK_MAX_DEPTH + 1 folders deep, not about 1000: round 7's
  `RecursionError` was not reproduced here, and the readable but not
  searchable top was not run against round 7's code (both are the
  synthesis's reading of `os.fwalk`). Not tested: the lstat of ROOT's
  real path when a member's walk stops at the init user's own link
  (assumption 59), a ROOT this user may search but not read (assumption
  58), an lstat that fails with an error other than `ENOENT` or `EACCES`
  (assumption 56), and Spotted item 15.
