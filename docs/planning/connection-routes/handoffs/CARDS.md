# Handoff: CARDS (P2, wave 1)

Model:  Claude Opus 5.5 (the CARDS lane agent)
Status: unreviewed
Date:   2026-10-14
Branch: Claude-Development-TheConnection-CARDS, from
        Claude-Development-TheConnection at 89bdd2e (after GROUND merged)
Where:  ~/TheConnection-lanes/cards

## Commits

| Task | Commit | Subject (the PR line) |
|---|---|---|
| R1 | `9ce5aec` | Check every mailbox name before tc touches the disk, so a bad name exits 6 and writes nothing. |
| R2 | `fbbae13` | Add address cards: tc join, tc card and tc cards, so each name says what it is and how mail reaches it. |
| R3 | `45e1175` | Route tc send by the recipient's card, cap a message at 1 MiB, and stop read and peek making inboxes. |
| R4 | `8698576` | Add the codex route: deliver the mail, then ring the Codex thread with codex queue when its inbox was empty. |
| R5 | `0dd58c2` | Show each card in tc health: a cards line in words and a cards key in --json. |
| R6 | `4196411` | Make a usage error exit 9, so a mistyped listener cannot pass for a timeout. (phases.md's line) |
| Handoff | the commit that adds this file | Write the CARDS handoff and its six pauses. |

`phases.md` gives a PR line for R6 only; the other five are written in
its style. No amend, reset or rebase. Nothing pushed or merged.
`tests/_root.py` was not edited.

R6's parser class was not done early. R1's test of `--to -x` (with a
space) asserts a usage refusal (`usage:` on stderr, exit neither 0 nor 6,
nothing written), not a number. `tests/test_usage.py` pins that case at 9.

## What was built

Every new block in `tc` carries a one-line `CARDS R<n> (Claude Opus 5.5,
unreviewed)` comment. Every function added or changed has `@interacts`,
`@deps`, `@complexity` and `@alloc`; the module block's `@interacts`,
`@deps`, `@complexity`, `@alloc` and layout lines name cards and the codex
route. New constants each carry a comment saying why.

**R1, names (C0).** `valid_name(name)`: `NAME_PATTERN` (built from
`NAME_MAX_CHARS = 64`) with `fullmatch`, so a trailing newline fails, and
never made of dots alone. `require_names(*names)` prints C0's words and exits
`EXIT_BAD_NAME` (6). It is the first line of `send` (`--from` and `--to`),
`read`, `peek`, `wait`, `status` (when a name is given) and `watch`, and
later of `join` and `card` (name and `--reports-to`).

**R2, cards (C1).** `cards/<name>.json`, eleven fields in C1's order,
written by `write_card` to `cards/<name>.json.<pid>.tmp` and renamed.

- `tc join <name> [--account L] [--kind K] [--reports-to N]` reads only
  `CODEX_THREAD_ID`, `CLAUDECODE`, `CLAUDE_CODE_SESSION_ID`, `CLAUDE_PID`
  and `CLAUDE_CONFIG_DIR`. Kind: `--kind`, else codex when
  `CODEX_THREAD_ID` is set, else claude when `CLAUDECODE=1`, else other.
  Route codex for kind codex, else local. `--kind codex` with no thread:
  exit 1 (`EXIT_REFUSED`), words why, nothing written. Prints
  `joined as <name> (<kind>, account <a>, route <r>)`, plus
  `, reports to <N>`. A rejoin replaces the card and resets `joined_at`.
- `account_label`: `--account`, else `CLAUDE_CONFIG_DIR`'s base name,
  else `unknown`; a blank at any step falls through.
- `tc card <name> --ssh T [--remote-tc P] [--account L] [--reports-to N]
  [--force]`: route ssh, kind other, `ssh: {target, tc}` with
  `~/TheConnection/tc` as the default path. A target or path that fails
  C1's checks exits 6. Unread mail for the name refuses it (exit 1,
  naming the count) unless `--force`.
- A name that reports to itself exits 6 with `tc: <name> cannot report
  to itself`. `--reports-to` takes a C0 name.
- `tc cards`: one line per card in the same words, `route ssh to <T>` for
  an ssh card, `no cards` when there are none.

**R3, the router (C2, C0, O1, O2).** `Delivery(exit, words, warnings)`,
`read_card`, `read_body`, `deliver_local`, and `ROUTES`, one line per
route. `cmd_send` checks names, then the body's size, then the empty
message, then reads the card and calls the route. No card is route
local. A route not in `ROUTES` answers `route <r> is not built yet`, exit
1, nothing written. `read_body` reads at most `SEND_BODY_MAX_BYTES + 1`
(1 MiB plus one) bytes from stdin and decodes them with stdin's own
encoding and error mode; a text argument is measured in its argv bytes
(`os.fsencode`). Over the limit: `tc send: message over 1 MiB; this is a
mailbox for words`, exit 8 (`EXIT_TOO_LARGE`), before `next_seq()`.
`deliver_local` is today's send (the same lines, moved), plus the
new-inbox warning and `header_note`. `read` and `peek` of a name with no
inbox print `no unread mail for <name>` and create nothing. A card that is
not a JSON object refuses the send, exit 1. Nothing reads `reports_to`
to route.

**R4, the codex route (C2, D3).** `deliver_codex` counts unread first
(`unread_count`, which never makes the inbox), delivers through
`deliver_local`, and when the count was 0 runs `codex queue --thread <t>
--message "MAIL: <n> unread for <to>. Run: <tc> read <to>, act on it,
reply with <tc> send --from <to> --to <sender>."` with stdin from
`/dev/null` and `CODEX_RING_SECONDS = 30`. Exit 0 adds `rang codex <to>
(queued; delivered when its turn ends or the session is resumed)`. Any
other exit, a timeout, codex missing, or no `thread_id` adds `ring failed
for <to>: <reason>; the mail is in its inbox`; the send exits 0. `<tc>`
is tc's resolved path. `ROUTES` gains `"codex": deliver_codex`.

**R5, health shows cards.** `cards_summary()`: a list of `{name, kind,
account, route, reports_to}`, in name order, name from the file. `tc
health --json` has a `cards` key; `tc health` has a `cards` line (or
`none`), one card per line in `tc cards`' words.

**R6, usage errors (D12).** `EXIT_USAGE = 9` beside the other exit
constants. `TcParser(argparse.ArgumentParser)` overrides `error()` to
print the usage and the message to stderr and exit 9. `main()` builds the
top parser from it and passes `parser_class=TcParser` to
`add_subparsers`, so every subcommand's parser is one too.

**Tests.** Five new files and one new case, all on `tests/_root.py`:
`tests/test_names.py` (4), `tests/test_cards.py` (13),
`tests/test_router.py` (9), `tests/test_codex_route.py` (7),
`tests/test_usage.py` (5), and `HealthCardsTest` in
`tests/test_health.py` (1; the seven existing cases unchanged). 39 new
tests; the suite went from 25 to 64.

## What was not built

- The `ssh` route, `tc gate`, the outbox, the shared mailbox, the board,
  the docs. Other lanes.
- `tests/test_mailbox.py` (CORE's). It is not in this tree, so R3's
  verify here is `tests.test_router` alone; the architect runs CORE's
  file against this branch before merge.
- A shared module loader for the tests. Each new test file that loads tc
  in process carries its own ten-line `load_tc` (as `test_keepalive.py`
  does): the harness has none, `tests/_root.py` is not this lane's to
  edit, and a new helper file is named in no task.
- No change to `CLAUDE.md`, `README.md` or `JOIN.md` (see "Spotted").

## Assumptions

1. **ROUTES across two commits.** R3's "Do" lists `ROUTES` with local and
   codex. R3's commit holds `"local"` only and R4 adds `"codex"`, so each
   commit holds only its own task and the tree builds at both.
2. **Exit codes reused, none new beyond the table:** 1 for every refusal
   with words, 6 for a bad name, a self-report, a bad ssh target or path,
   8 for size, 9 for usage.
3. **A text argument over 1 MiB cannot come from a real command line.**
   Linux caps one argument at 128 KiB (`MAX_ARG_STRLEN`), so the argument
   path of the size check is tested in process.
4. **stdin decoding.** On Linux, `sys.stdin` does not translate `\r\n`.
   Checked by hand: `printf 'a\r\nb\rc'` read through `sys.stdin.read()`
   and through `sys.stdin.buffer.read()` plus `decode(sys.stdin.encoding,
   sys.stdin.errors)` gave the same string.
5. **The card's .tmp name carries the pid,** so two joins of one name at
   once never share a file. Reasoned, not tested.
6. **R5's test is a new class** at the end of `tests/test_health.py`,
   with `_root` imported at the top (the brief's instruction to build the
   new case on `TcRoot`).
7. **`CLAUDE_CONFIG_DIR` in this lane's session.** C1 records it unset in
   the architect's session. In this lane's session it is set, and its base
   name starts with a dot, so a join here would carry that dot in the
   account label. The two-accounts QA script (D4) should record both.
8. The smaller defaults are pause CARDS-6.

## Pauses

All six are open and built to their recommendation; nothing waits on
them.

- `pauses/CARDS-1.md`: `phases.md` R2 says `tc card x --ssh
  -oProxyCommand=y` exits 6; with a space the parser refuses first, as
  R1's `--to -x` does. Both forms are tested; both write nothing.
- `pauses/CARDS-2.md`: C2's new-inbox warning keys on the inbox, and
  `tc join` makes none, so the first mail to a freshly joined name says
  "nobody has joined" (every Codex name, since it never runs `tc wait`).
  Recommendation: warn only when there is no inbox and no card.
- `pauses/CARDS-3.md`: R6's stated reason is wrong in Python 3.12.3.
  `wait --timeot 1 b` is refused by the top parser, so a top-only
  override still exits 9 there; the subparser cases catch that mutation.
- `pauses/CARDS-4.md`: `tc card`'s exit code over unread mail (built 1),
  its kind (built `other`), and its account default (built C1's chain,
  which labels a far name with the local session's account).
- `pauses/CARDS-5.md`, for the SSH lane: C3's `shlex.join` quotes the
  default `~/TheConnection/tc`, and a quoted `~` never expands on the far
  side. Recommendation: send a leading `~/` bare.
- `pauses/CARDS-6.md`: nine small defaults (watch's names, a blank
  account, an unreadable card, a codex card with no thread, the ring's
  `<n>`, the shape of health's `cards` key, `header_note`'s place,
  `CLAUDE_PID`, what `tc card` prints).

## Mutations and their red runs

Method: a scratch script (in the session's scratch folder, not the repo)
made each mutation as exact text edits to `tc`, ran the task's test
module, wrote the original bytes back, and compared sha256 before and
after. Every row printed `restored: OK`, and `git status --short` showed
only the task's own files. Temp paths are cut to `<root>`.

| Task | Mutation | Run | Red line |
|---|---|---|---|
| R1 | a check on `--to` only (`--from`, read, peek, wait, status, watch unchecked) | `tests.test_names`: FAILED (failures=10) | `AssertionError: 1 != 6 : tc ('send', '--from', '../a', '--to', 'b', 'hi') exited 1`, then one line each for `--from=-a`, `read "a b"`, `read -- -x`, `read ""`, the 65-character name, `peek ..`, `wait ..`, `status a/b`, `watch ..` |
| R1 | a rule that lets a leading dash through | `tests.test_names`: FAILED (failures=4) | `AssertionError: 0 != 6 : tc ('send', '--from', 'a', '--to=-x', 'hi') exited 0`; `AssertionError: True is not false : valid_name('-x') took a bad name` |
| R2 | an empty account (a blank `--account` kept) | `tests.test_cards`: FAILED (failures=2) | `AssertionError: '' != 'unknown'` |
| R2 | a card written in place | `tests.test_cards`: FAILED (failures=1) | `AssertionError: PosixPath('<root>/cards/b.json') unexpectedly found in [PosixPath('<root>/cards/b.json')] : the card was written in place` |
| R2 | a join that copies the whole environment (kept aside, nothing extra in the card) | `tests.test_cards`: FAILED (failures=1) | `AssertionError: 1 != 0 : cmd_join iterated the whole environment` |
| R2 | a join that copies the whole environment into the card | the two environment tests: FAILED (failures=2) | `AssertionError: True is not false : a planted value reached the card, in fields ['environment']`; `AssertionError: 1 != 0 : cmd_join iterated the whole environment` |
| R2 | a self-report written as a card | `tests.test_cards`: FAILED (failures=1) | `AssertionError: Tuples differ: (0, '') != (6, 'tc: b cannot report to itself\n')` |
| R3 | a warning on every send | `tests.test_router`: FAILED (failures=1) | `AssertionError: Tuples differ: (0, '[62 chars]00002-from-a.md\n', 'new inbox: nobody has joined as nobody\n') != (0, '[62 chars]00002-from-a.md\n', '')` |
| R3 | a number taken before the size check | the two size tests: FAILED (failures=2) | `AssertionError: '3' != '2'` (stdin; message: a refused send used a number); `AssertionError: '1' is not None : a refused send made mail/.seq` (text argument) |
| R3 | peek makes the inbox of an unknown name (extra) | `tests.test_router`: FAILED (failures=1) | `AssertionError: Tuples differ: (0, '0 unread for ghost\n', '') != (0, 'no unread mail for ghost\n', '')` |
| R4 | the codex route never rings (proves the record check) | `tests.test_codex_route`: FAILED (failures=5) | `AssertionError: False is not true : <root>/fake-codex-*/calls.jsonl missing: the fake codex never ran` |
| R4 | a ring on every send | `tests.test_codex_route`: FAILED (failures=1) | `AssertionError: Tuples differ: (0, '[64 chars].md\nrang codex c (queued; delivered when its [35 chars])\n') != (0, '[64 chars].md\n')` |
| R4 | a send that fails because the ring failed | `tests.test_codex_route`: FAILED (failures=3) | `AssertionError: 1 != 0 : a failed ring failed the send: exit 1: sent #1 to c: <root>/mail/to-c/000001-from-a.md` |
| R5 | the `cards` key without `reports_to` (extra) | `HealthCardsTest`: FAILED (failures=1) | `AssertionError: Lists differ: [{'na[61 chars]ocal'}, ...] != [{'na[61 chars]ocal', 'reports_to': 'a'}, ...]` |
| R5 | a `cards` line that always says none (extra) | `HealthCardsTest`: FAILED (failures=1) | `AssertionError: '\ncards      b (claude, account unknown, route local), reports to a\n...' not found in '...cards      none\nmail       empty\n'` (machine line cut) |
| R6 | the override on the top parser only | `tests.test_usage`: FAILED (failures=6) | `AssertionError: 2 != 9 : tc ('send', '--to', 'b', 'hi') exited 2`, and the same for `wait`, `wait b --timeout soon`, `send --to -x`, `card --ssh -oProxyCommand=y`, `join --kind robot`. `wait --timeot 1 b` stayed green (CARDS-3). |
| R6 | no override at all (extra) | `tests.test_usage`: FAILED (failures=10) | `AssertionError: 2 != 9 : tc ('wait', '--timeot', '1', 'b') exited 2`, and every other usage case |

Two test changes came out of these runs, each in its task's commit:

- R2: the first run of the environment-into-card mutation failed with a
  message that printed the card, and so part of the environment, in the
  scratch output. The test now names the fields that hold the planted
  value and never prints the card. The row above is the rerun.
- R3: the first run of the number-before-size mutation went red
  (failures=5, errors=2), but the stdin size test failed on a fixed file
  name before its `.seq` check. It now finds the sent file by glob, so
  its red line is the `.seq` check. The row above is the rerun.

## Verify commands and their output

Each run at its own commit, in `~/TheConnection-lanes/cards`. The
docstring line of each test, as `-v` prints it:

```
$ python3 -m unittest tests.test_names -v        # at 9ce5aec
`--to -x` never reaches valid_name(): the parser refuses it, and nothing is written. ... ok
Each case exits 6 with C0's words and leaves the root's file list empty. ... ok
A send between two good names exits 0 and lands in mail/to-<to>/. ... ok
valid_name() takes every GOOD name and refuses every BAD one. ... ok
Ran 4 tests in 0.553s
OK

$ python3 -m unittest tests.test_cards -v        # at fbbae13
A target that reads as an ssh option, or a bad remote path: refused, nothing written. ... ok
With 2 unread in to-x, `tc card x --ssh u@h` exits 1 naming 2 and writes no card; --force writes it. ... ok
cards/b.json comes only from a rename of a .tmp sibling; nothing writes it in place. ... ok
With CLAUDECODE=1, CLAUDE_CODE_SESSION_ID=s1, CLAUDE_PID=9: kind claude, route local, those ids. ... ok
With CODEX_THREAD_ID=t1: kind codex, route codex, thread t1, no Claude ids. ... ok
A second join of b replaces the card: the new account, a new joined_at, one file. ... ok
`tc card x --ssh u@h`: route ssh, ssh {target u@h, tc ~/TheConnection/tc}. ... ok
`tc cards` prints one line per card, in name order; `no cards` when empty. ... ok
In process, cmd_join reads only C1's five variables and never copies the environment. ... ok
`tc join q --kind codex` with no CODEX_THREAD_ID exits 1, says why, writes nothing. ... ok
The native path's token and socket, and any other variable, never land in a card. ... ok
--reports-to a is stored; a rejoin without it stores null; b to b and ../x are refused. ... ok
No identity and no --account gives `unknown`; so does every blank way in. ... ok
Ran 13 tests in 1.544s
OK

$ python3 -m unittest tests.test_router -v       # at 45e1175
The first send to `nobody` exits 0, prints the send line, and warns on stderr; the second does not warn. ... ok
b joins as a Claude reporting to a; mail from c to b lands in to-b only (No hub, D7). ... ok
An ssh card, and a hand-made card naming route pigeon: exit 1, `route <r> is not built yet`. ... ok
No card: the stdout line, the header, read once, then `no unread mail` (as CORE's K1). ... ok
A card that is not JSON: the send exits 1 naming the card, and writes nothing. ... ok
In process: deliver_local gives Delivery(0, the send line, [the new-inbox warning]); header_note ends the header. ... ok
`tc peek ghost` and `tc read ghost` say `no unread mail for ghost` and leave the root empty (O2). ... ok
Exactly 1 MiB is sent; one byte more exits 8, writes nothing and uses no number. ... ok
In process: a text argument over 1 MiB in bytes exits 8 before a number, even under 1 MiB in characters. ... ok
Ran 9 tests in 0.669s
OK

$ python3 -m unittest tests.test_codex_route -v  # at 8698576
A hand-made codex card with no thread_id: exit 0, the mail lands, `ring failed` names why, no codex run. ... ok
With the fake exiting 1 (unknown thread): exit 0, the mail in the inbox, `ring failed` on stderr. ... ok
In process: codex past CODEX_RING_SECONDS gives `ring failed ... no answer in 30 s`, exit 0. ... ok
send, read, send: two rings, one per batch of unread mail. ... ok
A send to a Claude card never runs codex; a send to a codex card in the same root does. ... ok
The recorded exit codes carry the plan's label, and the codes the plan names. ... ok
Two sends to c ring once, with the argv C2 gives, and both land. ... ok
Ran 7 tests in 0.821s
OK

$ python3 -m unittest tests.test_health -v       # at 0dd58c2
The `cards` key lists name, kind, account, route, reports_to; the `cards` line says the same in words. ... ok
test_health_counts_mail ... ok
test_health_finds_a_live_listener_and_its_pid ... ok
(two ResourceWarning: unclosed file lines, from the existing HealthTest)
test_health_json_shape ... ok
test_second_watch_for_the_same_name_exits_3 ... ok
test_watch_alerts_on_low_memory ... ok
test_watch_alerts_when_a_listener_dies ... ok
test_watch_heartbeat_exits_0 ... ok
Ran 8 tests in 5.450s
OK

$ python3 -m unittest tests.test_usage -v        # at 4196411
`tc wait --timeot 1 b` exits 9 with `usage:` and no TIMEOUT line. ... ok
`tc wait b --timeout 1` exits 2 with a TIMEOUT line. ... ok
A missing --from, a missing name, a bad --timeout, a dash-led value, a bad choice: 9 each. ... ok
`tc --help` and `tc wait --help` exit 0 with the usage on stdout. ... ok
No command, an unknown command and an unknown flag each exit 9 and write nothing. ... ok
Ran 5 tests in 1.545s
OK
```

The full suites at `4196411`, the last code commit:

```
$ python3 -m unittest discover -s tests -p 'test_*.py'
(two ResourceWarning: unclosed file lines, from tests/test_health.py's HealthTest)
Ran 64 tests in 16.121s
OK
$ node --test tests/*.test.mjs
# tests 8
# pass 8
# fail 0
```

Baseline at `89bdd2e`: discover ran 25 tests OK, node 8 of 8. The two
warnings were there before this lane (GROUND's handoff says so).

`check_voice.py` and `check_american.py` were clean on this file and on
the six pause files.

## Not verified

- CORE's `tests/test_mailbox.py` against this branch. Not in this tree.
- Real `codex`. The argv, the flags `--thread` and `--message`, and the
  exit codes come from the plan (C2, D3), not from a run; the fixture is
  labeled `matches Codex 0.162.1, 2026-10-14` and was written from the
  plan's words. Every codex test ran against the harness's fake or with
  `subprocess.run` swapped; the refusing stub stood behind the fake.
  Donald runs the real one (D4).
- The 30 s ring timeout end to end. Only the in-process test, with
  `subprocess.run` raising `TimeoutExpired`.
- Python other than 3.12.3. CARDS-3 rests on how this argparse hands
  leftovers back.
- Two joins of one name at the same moment.
- A body on stdin that is not valid UTF-8.

## Spotted, not fixed

- `CLAUDE.md`'s "Exit codes" bullet says a usage error exits 2 until R6
  moves it to 9. Once this merges, that sentence is history. Not this
  lane's file.
- `README.md`'s command table has no `join`, `card` or `cards`, and its
  `tc wait` line lists exits 0, 2 and 3 only. The DOCS lane's (D1).
- The module doc block's first line still says "between Claude Code
  sessions on one machine", and its `@interacts` line runs past 80
  columns after the `cards/` edit. Left as one-line edits to a shared
  spot.
- `tests/test_health.py`'s `HealthTest` leaves two pipes unclosed (the
  ResourceWarnings above). Outside this lane's case.
