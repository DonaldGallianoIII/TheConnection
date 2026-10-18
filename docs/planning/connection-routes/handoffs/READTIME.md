# Handoff: READTIME, tc read records when each message was read

Model:  Claude Opus 5.5 (the READTIME lane agent)
Status: unreviewed
Date:   2026-10-17
Branch: Claude-Development-TheConnection-READTIME, from
        Claude-Development-TheConnection at 3a3dd24
Where:  ~/TheConnection-lanes/readtime

The spec is pause READTIME-1, items 1 to 8, and a2's ruling (#1615):
each line carries `name`, `number` and `read`, and those three keys are
a contract.

## Commits

| What | Commit | Subject |
|---|---|---|
| Items 1 to 5, the QA step | `fead995` | Record when each message was read: tc read appends to read/.read-times, tc log shows it |
| Pause | `7b8b232` | Add pause READTIME-2: three tests outside the work set list read/ and now find the record |
| Handoff | `79ef162` | This handoff |
| Fix round 1 | `f8bfe68` | Pause READTIME-2 settled; `1 message` |
| Fix round 2 | `ac2f9ca` | Last line wins, tail past the cap, no default record spec, and the docs the review asked for |
| Fix round 2 handoff | the commit that adds the section below | This handoff's fix round 2 section |

## Fix round 2 (the quick review, audits/2026-10-17-2020-quick)

Line numbers are at `ac2f9ca`.

1. **LOW-1 and DEBT-1.**
   - The last line for a name wins (`tc:4676`), so a reused name shows
     its newer read.
   - A record past `READ_TIMES_MAX_BYTES` (`tc:1269`) is read from its
     tail (`tc:4648`): pread from the size less the cap, one byte early,
     so a window that starts on a line's first byte keeps that line. The
     partial first line is dropped (`tc:4665`). Older messages show
     `read, time not recorded`, and one stderr line
     (`READ_TIMES_TAIL_WORDS`, `tc:1274`) says only the newest part was
     read. A record it will not read at all still says why
     (`READ_TIMES_UNREAD_WORDS`, `tc:1273`).
   - The doc sentences that claimed first-wins or an all-or-nothing cap
     are fixed: `read_times` (`tc:4596`), `cmd_log` (`tc:5572`), the
     constant's comment and the module block's `@complexity`.
2. **LOW-3.** `cmd_log`'s block (`tc:5622`) and `NOT_RECORDED_LINE`'s
   comment (`tc:1294`) say a log run while a read is between its moves
   and its write can show `read, time not recorded` for a moment.
3. **LOW-4.** `inbox_lock`'s block (`tc:3640`) and `cmd_read`'s (its
   opening paragraph and `@interacts`) now say the record's open, one
   write and fsync run under the lock, so a send cannot land between the
   moves and the record.
4. **REC-1 and DEBT-2, option B.** `RecordSpec` (`tc:1302`) with
   `WAIT_EXIT_RECORD` and `READ_TIMES_RECORD` (`tc:1303`, `tc:1304`),
   module constants. `move_record_aside(box_fd, box, name, record)`
   (`tc:5241`) has no default; all three call sites pass a spec
   (`tc:4520`, `tc:5381`, `tc:5386`). The wait record's words are byte
   for byte as before: `tests/test_wait_exit.py` and
   `tests/test_wake_files.py` pass unchanged.
5. **LOW-2, a known limit, behavior unchanged.** `open_read_times`'s
   block (`tc:4478`): a hard-link backup (`cp -al`, `rsync --link-dest`)
   gives the record a second name. tc log then will not read it, and the
   next tc read moves it aside to `.read-times.planted-<k>` with words.
   Nothing is deleted, but the earlier times drop out of tc log. The way
   back: the owner removes the backup's link, then, in read/, when a new
   record has started, `cat .read-times >> .read-times.planted-<k>` (the
   newer lines last, and the last line wins), and `mv
   .read-times.planted-<k> .read-times`.
6. **REC-7.** `JOIN.md:94` and `JOIN-CODEX.md:91`: one bullet under `tc
   read`. An exit 0 with a `tc read:` line about read times means the
   mail was still read; act on it, don't stop, and send the relay the
   line.
7. **REC-3.** `qa/human/route-shared.md` steps 45a to 45c (`:753`,
   `:762`, `:776`), each with what to type, what to see, and pass and
   fail lines. They are numbered 45a to 45c so no later step, and no
   reference to one from `route-ssh.md` (not in this lane's work set),
   moves. The order section names them.

**Red first.** Three new tests in `tests/test_read_times.py`, run before
the build with `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest
tests.test_read_times`: `Ran 14 tests`, `FAILED (failures=4)`, every one
on its assertion. Line numbers as that run printed them, before the
module block grew four lines:
- `test_when_a_name_has_two_lines_the_last_one_shows`, line 632: the
  first time shown, not `2099-01-01T00:00:00-05:00`.
- `test_a_record_over_the_limit_shows_its_newest_times_and_says_only_they_were_read`,
  line 667, both windows (`mid-line`, `on a line's start`): every
  message `read, time not recorded`.
- `test_move_record_aside_without_its_record_raises_and_removes_nothing`,
  line 507: `TypeError not raised`.

The old over-the-limit case left
`test_a_record_not_the_owners_reads_as_not_recorded_with_one_line_why`
(`:585`), since a record past the cap is no longer refused whole.

**Mutations**, each on a `git archive ac2f9ca` copy, running
`tests.test_read_times`, `tests.test_wait_exit` and
`tests.test_wake_files` (43 tests):

| Mutation | Result |
|---|---|
| First-wins put back (`times.setdefault`) | `FAILED (failures=1)`: `test_when_a_name_has_two_lines_the_last_one_shows`, line 636, on its assertion |
| A default put back, `record=WAIT_EXIT_RECORD` | `FAILED (failures=1)`: `test_move_record_aside_without_its_record_raises_and_removes_nothing`, line 511, `TypeError not raised` |

The default changes nothing at the existing call sites: all three pass
a spec, so the wait exit and wake file tests (42 of the 43) stay green
under it. Only the new test, which calls `move_record_aside` with no
spec, sees it. Without that test, no test would.

**Runs at `ac2f9ca`.** `python3 -m unittest discover -s tests -p
'test_*.py'`: `Ran 390 tests in 265.996s`, `OK`. `node --test
tests/*.test.mjs`: `# tests 68`, `# pass 68`, `# fail 0`.

**Not done, and why.**
- REC-2 (an in-process `tc log` test with read/ and the record both
  another user's), REC-4 (`tc log --help` and the README row), REC-5
  (expected dot records named once in `tests/_root.py`) and REC-6 (the
  read line of a message with no header line): left by the architect's
  ruling for this round.
- LOW-5 (contracts.md C2 and C4, CLAUDE.md's layout and lock lines):
  the architect's merge-gate item.
- Steps 45a to 45c are written, not walked: they need two Linux users.

## Fix round 1 (the architect's two fixes)

1. **Pause READTIME-2 settled** by the architect, option 1:
   `.read-times` added to the expected name list in
   `tests/test_inbox_pinned.py:629` (row d) and `tests/test_shared.py`
   at the `moved` and `history` assertions (lines 1302 and 2621 at
   `fead995`). Only those lists changed; each assertion is a listing of
   read/ and nothing more, so none was widened. The five known failures
   are gone.
2. **`1 message`.** Both word sets, `READ_TIMES_FAILED_WORDS` and
   `READ_TIMES_NOT_OWNER_WORDS`, take `{count}`: `1 message`, else
   `<n> messages`, one conditional in `write_read_times`, no new
   global. The not-owner words had the same `for 1 messages`, so they
   share the fix. `test_a_failed_record_write_says_so_prints_the_mail_and_exits_0`
   now runs over one message and two (subtests `messages=1` and
   `messages=2`). Against `fead995`'s tc the `messages=1` subtest is red
   on its assertion at line 420 (`... for 1 messages ...` against `...
   for 1 message ...`), and green on the fix. The `<n> messages` in
   pause READTIME-1's item 5 and in the brief are the architect's and
   unchanged.

## What changed

Line numbers are at `fead995`.

**Item 1, the record (tc read).**
- Constants, each with a comment saying why: `READ_TIMES_NAME`
  (`tc:1242`), `READ_TIMES_KEYS` (`tc:1246`), `READ_TIMES_MODE` 0640
  (`tc:1251`), `READ_TIMES_FLAGS` (`tc:1256`), `READ_TIMES_TRIES`
  (`tc:1259`), `READ_TIMES_MAX_BYTES`, 8 MiB (`tc:1265`), the two
  stderr word sets (`tc:1270`, `tc:1271`) and log's three lines
  (`tc:1274` to `tc:1276`).
- `write_read_times` (`tc:4481`). The owner check is `tc:4520`: the uid
  of read/'s descriptor (fstat'ed by `pin_folder`) against this user's;
  otherwise no line and `READ_TIMES_NOT_OWNER_WORDS`. One `now_iso()`
  per read (`tc:4523`), one `os.write` of every line (`tc:4532`), then
  `os.fsync` (`tc:4534`). The number comes from the name the message had
  in its inbox (`message_number`, `tc:4415`, `MESSAGE_NAME_PATTERN`),
  null when it does not match; the name is the one in read/, so a by-hand
  move's line names `by-hand-<k>-<name>` and still carries the number.
- `open_read_times` (`tc:4428`): the open by name in read/'s descriptor
  with `O_NOFOLLOW` (`tc:4459`), then fstat; kept only for this user's own
  one-name regular file (`own_wake_lock`'s test). Anything else is moved
  aside and the open tried once more (`tc:4473`).
- **Reuse, not a copy.** `move_record_aside` (`tc:5170`) now takes three
  keyword arguments: `record` (the one name where this user's own file is
  kept, never removed: `tc:5209`), `kind` and `what` for the words. The
  defaults are the wait exit record's, so its words and behavior are as
  before (`tests/test_wait_exit.py` and `tests/test_wake_files.py` pass
  unchanged).
- `cmd_read` (`tc:4614`) calls it under the inbox lock, after the last
  move, with only the messages that moved (`tc:4767`), and prints the
  words to stderr after the mail, with the lock released (`tc:4779`). The
  exit code is untouched.
- One addition the brief did not name: when the record's last byte is not
  a newline (a line torn by a crash), the append writes a newline first
  (`tc:4531`), so the next read's first line still parses. It is in the
  same one write. The torn-line test's second half pins it.

**Item 2, tc log.** `read_times` (`tc:4548`) opens the record by name in
read/'s descriptor with `O_NOFOLLOW | O_NONBLOCK` (`tc:4576`), checks a
regular file with one name, at most `READ_TIMES_MAX_BYTES`, and reads it
once. A line that does not parse is passed by (`tc:4609`); the first line
for a name wins (`tc:4610`), as its doc block says. Fix round 2 changed
both: the last line for a name wins, and a record past the cap is read
from its tail (below). `cmd_log` (`tc:5494`)
reads each read/'s record once (`tc:5601`), hands each message's line to
`show` (`tc:5614`), and prints one stderr line per record it would not
read (`tc:5616`), never changing the exit. `show` (`tc:4235`) prints the
line just after the message's first line (`tc:4270`); the file is never
changed.

One more check than the brief named: `read_times` believes a record only
when it is owned by read/'s owner, the only user who writes it, so a
file a member planted in a shared read/ before the owner's first read is
not shown as times. It reads as `read, time not recorded` with one
stderr line, like an unreadable record.

**Item 3, tc peek.** Unchanged code; its doc block says it never opens,
makes or changes the record.

**Item 4, doc blocks.** The module block (layout, `@interacts`,
`@complexity` for read and log, `@alloc`), `show`, `cmd_read`,
`cmd_peek`, `cmd_log`, `move_record_aside`, and the four new functions.
`@complexity` names the growth: the record gains one line per message
ever read; read never reads it (one fstat for its size), log reads each
whole, once, capped.

## Item 5, red first

`tests/test_read_times.py`, 11 tests, written before the build and run
against the unchanged tc with
`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_read_times`:

```
Ran 11 tests in 3.666s
FAILED (failures=14)
```

Every failure was an assertion, no errors: lines 266, 303, 347, 385
(four plants), 415, 439, 471, 507, 531 and 563 (two cases). Two pass
before the build, as they should, since they pin behavior tc already
had: the message bytes test (`test_each_message_files_bytes_are_unchanged_by_the_read`)
and the peek test's `none yet` subtest.

Green, after the build, same command:

```
Ran 11 tests in 4.176s
OK
```

The cases: three lines with names, numbers, one time with an offset
between two clock reads, 0640, this user's (`:245`); the by-hand name
with its inbox number, and null for a name not of the form (`:281`);
bytes unchanged (`:307`); peek (`:326`); a symlink, FIFO, hard link and
folder at the record's name moved aside with words, the link's target
unchanged (`:353`); ENOSPC from `os.write` in a module load: words, the
mail printed, exit 0 (`:395`); a member who does not own read/ (`:419`);
a message whose move was refused gets no line (`:443`); log's three lines
(`:485`); a torn last line (`:510`); a record over the limit or not its
owner's (`:541`).

## Item 6, mutations

Each on its own `git archive fead995` copy in a scratch folder, run with
`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_read_times`.
Each red on assertions (FAIL, no ERROR):

| Mutation | Red tests, and the line |
|---|---|
| Record written before the moves, from the messages found | `test_a_message_that_could_not_be_moved_gets_no_line` (`:471`); `test_the_number_is_the_inbox_names_and_null_for_a_name_not_of_the_form` (`:303`). `failures=2` |
| Peek writes a record | `test_peek_writes_no_record_and_changes_none`, both subtests (`:341`, `:351`). `failures=2` |
| Log drops the read line | `test_log_says_read_...` (`:507`), `test_a_torn_last_line_...` (`:531`), `test_a_record_over_the_limit_...` both cases (`:568`). `failures=4` |
| `O_NOFOLLOW` removed from `READ_TIMES_FLAGS` | `test_a_plant_at_the_records_name_...`, the symlink subtest (`:385`). `failures=1` |
| Owner check removed | `test_a_member_who_does_not_own_read_records_nothing_and_says_why` (`:439`). `failures=1` |
| Torn-line skip removed (`continue` made `raise`) | `test_a_torn_last_line_...` (`:530`), `test_log_says_read_...` (`:506`). `failures=2` |

## README and QA

- `qa/human/route-local.md` step 13 says what `tc log` now prints and
  how to check the record by hand.
- README.md is unchanged: it shows no `tc log` output. Its command table
  ("History in both directions") and its layout list do not name the
  record; the architect may want a line in each with the contract lines.
- `qa/human/route-shared.md` step 25 shows no log output line, unchanged.

## Not done, not verified

- **Pause READTIME-2** (settled in fix round 1, above). Until then, three
  existing tests outside the work set listed read/ after a `tc read` and
  found `.read-times`: five known failures at `fead995` to `79ef162`.
- **Nothing ran as a second Linux user.** The non-owner case is
  simulated in process by `os.fstat` reporting read/ as another user's,
  as the SHARED and F1 suites do. The kernel's sticky-bit refusal of a
  member's write, and `fs.protected_regular` refusing the owner's
  `O_CREAT` open of a member's plant (handled by moving it aside), are
  not proven by a test. Since fix round 2, `qa/human/route-shared.md`
  steps 45a to 45c ask a person to walk them; nobody has yet.
- contracts.md (C2, C4), decisions.md and CLAUDE.md's layout line are
  the architect's, after the pause.
