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
| Handoff | `0739794` | Write the CARDS handoff and its six pauses. |
| Fix 1 (a) | `fe3f7fa` | Stop the codex route losing a wake, and lock each inbox (D14, LOW-9) |
| Fix 1 (b) | `8bb1f8b` | Settle the card and router pauses (D13) and tighten the refusals and .tmp writes |
| Fix 1 (c) | `fd01c39` | Kill a timed-out ring's whole process group, name the root in the ring, fix stale tags |
| Fix 1 (d) | the commit that changes this file | Bring the CARDS handoff and its six pauses up to fix round 1 |

`phases.md` gives a PR line for R6 only; the other five are written in
its style. No amend, reset or rebase. Nothing pushed or merged.
`tests/_root.py` was not edited, in the lane or in the fix round.

Fix round 1 ran the brief
`audits/2026-10-14-1752-standard/fixes/round-1.md`: 20 items from that
audit's synthesis, built to the dev branch's contracts.md C0 to C2 (with
D13 and D14) and phases.md R1 to R6. See "Fix round 1" below. The
sections from here to "Fix round 1" record the lane as first built, with
the lines the fix round made false brought up to date.

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
- `account_label` (join): `--account`, else `CLAUDE_CONFIG_DIR`'s base
  name, else `unknown`; a blank at any step falls through. Since fix round
  1, `tc card` uses `far_account`: `--account`, else `unknown` (D13).
- `tc card <name> --ssh T [--remote-tc P] [--account L] [--reports-to N]
  [--force]`: route ssh, kind other, `ssh: {target, tc}` with
  `~/TheConnection/tc` as the default path. A target or path that fails
  C1's checks exits 6. Unread mail for the name refuses it (exit 1,
  naming the count) unless `--force`. Since fix round 1 the count and the
  write share the inbox lock, and a note on stderr says sends are refused
  until the ssh route is built.
- A name that reports to itself exits 6 with `tc: <name> cannot report
  to itself`. `--reports-to` takes a C0 name.
- `tc cards`: one line per card in the same words, `route ssh to <T>` for
  an ssh card, `no cards` when there are none.

**R3, the router (C2, C0, O1, O2).** `Delivery(exit, words, warnings)`,
`read_card`, `read_body`, `deliver_local`, and `ROUTES`, one line per
route. `cmd_send` checks names, then the body's size, then the empty
message, then reads the card and calls the route. No card is route
local. A route not in `ROUTES` answers `route <r> is not built yet`, exit
1, nothing written (since fix round 1: `tc send: route <r> is not built
yet; nothing sent`). `read_body` reads at most `SEND_BODY_MAX_BYTES + 1`
(1 MiB plus one) bytes from stdin and decodes them with stdin's own
encoding and error mode; a text argument is measured in its argv bytes
(`os.fsencode`). Over the limit: `tc send: message over 1 MiB; this is a
mailbox for words`, exit 8 (`EXIT_TOO_LARGE`), before `next_seq()`.
`deliver_local` is today's send (the same lines, moved), plus the
new-inbox warning and `header_note`. `read` and `peek` of a name with no
inbox print `no unread mail for <name>` and create nothing. A card that is
not a JSON object refuses the send, exit 1. Nothing reads `reports_to`
to route.

**R4, the codex route (C2, D3).** As first built: `deliver_codex`
counts unread first (`unread_count`, which never makes the inbox),
delivers through `deliver_local`, and when the count was 0 runs `codex
queue --thread <t> --message "MAIL: <n> unread for <to>. Run: <tc> read
<to>, act on it, reply with <tc> send --from <to> --to <sender>."` with
stdin from `/dev/null` and `CODEX_RING_SECONDS = 30`. Exit 0 adds `rang
codex <to> (queued; delivered when its turn ends or the session is
resumed)`. Any other exit, a timeout, codex missing, or no `thread_id`
adds `ring failed for <to>: <reason>; the mail is in its inbox`; the send
exits 0. `ROUTES` gains `"codex": deliver_codex`. Fix round 1 rebuilt it
to D14 (the marker, the inbox lock, the thread_id check), named the root
in the ring and killed a timed-out ring's process group; see below.

**R5, health shows cards.** `cards_summary()`: a list of `{name, kind,
account, route, reports_to}`, in name order, name from the file (fix
round 1 added `ssh_target`). `tc health --json` has a `cards` key; `tc
health` has a `cards` line (or `none`), one card per line in `tc cards`'
words. As first built that was false for an ssh card, which lost its
target; fix round 1 (LOW-4) made it true.

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
tests; the suite went from 25 to 64. Fix round 1 added 19 more (cards
16, router 15, codex route 17), so the suite runs 83.

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

All six are settled by D13 (a2, for Donald, 2026-10-14), and each file's
`Pause:` line says how. When the lane first handed off, the line here
said all six were "built to their recommendation". Two were not: CARDS-2
was built to the contract as written, and CARDS-4 item 3 to C1's chain.
Fix round 1 built both to D13.

| Pause | Status | Built |
|---|---|---|
| CARDS-1 | settled by D13 | as built (option 1); phases.md R2 now names both forms |
| CARDS-2 | settled by D13 | option 3, in fix round 1 (`8bb1f8b`), keyed on the card file |
| CARDS-3 | settled by D13 | as built (option 1); phases.md R6 now names the `--from` case |
| CARDS-4 | settled by D13 | items 1 and 2 as built; item 3 the other option, in fix round 1 (`8bb1f8b`) |
| CARDS-5 | settled by D13 | option 1, for the SSH lane (S1); the `~` refusals' tests added in fix round 1 |
| CARDS-6 | settled by D13 | the nine defaults as built; items 3, 4, 6 and 9 amended by fix round 1 |

- `pauses/CARDS-1.md`: `phases.md` R2 said `tc card x --ssh
  -oProxyCommand=y` exits 6; with a space the parser refuses first, as
  R1's `--to -x` does. Both forms are tested; both write nothing.
- `pauses/CARDS-2.md`: C2's new-inbox warning keyed on the inbox, and
  `tc join` makes none, so the first mail to a freshly joined name said
  "nobody has joined" (every Codex name, since it never runs `tc wait`).
  Now it warns only when there is no inbox and no card.
- `pauses/CARDS-3.md`: R6's stated reason was wrong in Python 3.12.3.
  `wait --timeot 1 b` is refused by the top parser, so a top-only
  override still exits 9 there; the subparser cases catch that mutation.
- `pauses/CARDS-4.md`: `tc card`'s exit code over unread mail (1), its
  kind (`other`), and its account default (now `--account`, else
  `unknown`).
- `pauses/CARDS-5.md`, for the SSH lane: C3's `shlex.join` quotes the
  default `~/TheConnection/tc`, and a quoted `~` never expands on the far
  side. D13: send a leading `~/` bare.
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

## Fix round 1

Model: Claude Opus 5.5 (the CARDS fixer), 2026-10-14. Brief:
`audits/2026-10-14-1752-standard/fixes/round-1.md`. Ids are the
synthesis's. Every new block in `tc` carries a one-line `CARDS fix round
1 (Claude Opus 5.5, unreviewed)` comment, and every function touched has
its four tags brought up to date.

**(a) `fe3f7fa`, the codex route and the inbox lock.**

- Item 1, MEDIUM-1 (D14). `deliver_codex` holds `mail/.box-<to>.lock` alone
  while it counts, checks `mail/.ring-pending-<to>`, delivers and
  decides; it rings when the count was 0 or the marker is there, after
  the lock is released. Exit 0 removes the marker; any other outcome
  writes it (`.tmp`, then rename) and warns `ring failed for <to>:
  <reason>; the mail is in its inbox; the next send to <to> rings again`.
  `tc read` holds the same lock from its glob to its last rename. The
  ring itself moved into `ring_codex`. If the marker cannot be written,
  the warning says a later send may not ring, not that it will.
- Item 2, MEDIUM-2 (D14). `THREAD_ID_PATTERN` (`[A-Za-z0-9][A-Za-z0-9._-]*`,
  with its why). `ring_codex` hands codex only a str of that shape;
  anything else is not rung, warns `its card's thread_id is not a thread
  id`, and leaves the marker; exit 0. A missing or empty `thread_id`
  keeps CARDS-6 item 4's words, `its card has no thread_id`, which D13
  settled. `tc join` refuses a `CODEX_THREAD_ID` of another shape: exit
  1, words why, no card.
- Item 11, LOW-9. `tc card` counts unread mail and writes the card under the
  inbox lock (alone). For the claim "a send cannot land in the gap" to
  hold, the send side takes it too: a local send reads the card again
  under the lock and lands under it. It takes the lock shared, so many
  local senders to one inbox never queue behind each other, only on
  `mail/.seq` as before (CORE's K3 checks that 50 senders all block on
  `.seq`). The first card read stays outside the lock, so a refused send
  still writes nothing.

**(b) `8bb1f8b`, cards, the router, refusals.**

- Item 3, MEDIUM-3 (D13). `deliver_local` warns only when the inbox did not
  exist and `cards/<to>.json` does not exist: the card file on disk, not
  the `card` argument (REC-2, the gate calls `deliver_local` directly).
- Item 4, MEDIUM-4 (D13). `far_account`: `tc card`'s account is `--account`,
  else `unknown`; it reads no environment. `cmd_card`'s doc block says
  so. Kind `other` and the exit-1 refusal were already so.
- Item 7, LOW-4. `cards_summary` adds `ssh_target` (null unless route ssh), the
  list shape kept; `tc health` prints `route ssh to <target>` as `tc
  cards` does.
- Item 12, LOW-10. A card with no string `route`: `tc send: the card <path> has
  no route; nothing sent.` plus who fixes it. Never `None`.
- Item 13, LOW-11. The empty message goes through `refuse(..., EXIT_REFUSED)`;
  same words, exit 1.
- Item 14, LOW-12. The `EXIT_BAD_NAME` and `EXIT_REFUSED` comments list every
  case the code uses them for, by row of the exit table.
- Item 16, LOW-15. An unreadable card's refusal ends `Ask <to>'s owner to rejoin
  (tc join <to>, run in <to>'s own session), or, if <to> lives on
  another machine, write its card with tc card <to> --ssh <target>.`
- Item 17, DEBT-3. `write_new_file` makes every `.tmp` (card, message, ring
  marker) with `os.open(path, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW,
  0o666)` (`NEW_FILE_FLAGS`, `NEW_FILE_MODE`; the umask applies). A
  planted link or file refuses with words: `tc send: could not create
  <tmp> (File exists); nothing sent` (the number is used), or `tc:
  could not create <tmp> (File exists); no card written`.
- Item 19, REC-13. While `ssh` is not in `ROUTES`, `tc card --ssh` prints `note:
  sends to <name> are refused until the ssh route is built` on stderr
  after the card line. The not-built refusal reads `tc send: route <r>
  is not built yet; nothing sent`.

**(c) `fd01c39`, tags, the ring's process group and words.**

- Item 5, LOW-1 and LOW-2. The module `@complexity`: health O(p + k + n + m + c),
  m every message file in every inbox and `read/`; a watch poll O(k +
  n) plus one nvidia-smi run, no cards, O(p) once per heartbeat. The
  same in `health_snapshot`'s and `cmd_watch`'s tags.
- Item 6, LOW-3. `read_body`'s `@alloc`: up to 4 bytes a character, about 5 x
  the limit at once.
- Item 9, LOW-7. `ring_codex` starts codex with `start_new_session=True`; on a
  timeout it sends SIGKILL to that process group (`os.killpg`) and reaps
  the child.
- Item 10, LOW-8. The ring decodes codex's output with `encoding="utf-8",
  errors="replace"`.
- Item 15, LOW-13. The fixture's label: `written from the plan's words (0
  queued, 1 unknown thread), not recorded from a run of codex`, and
  `test_the_fixture_is_labeled` checks that wording and that it names
  the fakes' codes.
- Item 18, REC-9. The ring's line: `Run: TC_ROOT=<root> <tc> read <to>, act on
  it, reply with TC_ROOT=<root> <tc> send --from <to> --to <sender>.`,
  the root resolved, both words through `shlex.quote`.

**Tests added (19):** `tests/test_codex_route.py` 10, `tests/test_router.py`
6, `tests/test_cards.py` 3. Thirteen older cases changed what they expect
(new words, the root in the ring, the `.tmp` made by `os.open`, two `~`
cases, the health case). The lock tests hold the lock in the
test process and read `/proc/locks` to see the child blocked on it, never
a fixed sleep. Three fakes of the test file's own (one that sleeps,
one that starts a child, one that writes odd bytes) sit inside the harness's temp
folder, ahead of the refusing stub; what they start is killed by its own
pid. `test_router.py` and `test_cards.py` import `wait_until_blocked`
and `RELEASE_CEILING_SECONDS` from `test_codex_route.py`, so there is one
copy.

### Mutations and their red runs (fix round 1)

Same method as above: a scratch script outside the repo made each
mutation as an exact text edit to `tc`, ran the named test, wrote the
original bytes back and compared sha256. Every row printed `restored:
OK`. Paths cut to `<root>`; only the assertion line is quoted.

| Item | Mutation | Test | Red line |
|---|---|---|---|
| MEDIUM-1 | ring decided on the count alone | `test_a_failed_ring_leaves_a_marker_and_the_next_send_rings` | `AssertionError: Lists differ: [['qu[213 chars] a.']] != [['qu[213 chars] a.'], ['queue', '--thread', 't1', '--message'[179 chars]b.']]` |
| MEDIUM-1 | the ring run under the inbox lock | `test_a_slow_ring_never_holds_up_a_read` | `AssertionError: 4.964908753987402 not less than 1 : tc read took 5.0 s while the ring ran: the ring held the inbox lock` |
| MEDIUM-1 | count and write outside the lock | `test_a_codex_send_waits_for_the_inbox_lock` | `AssertionError: tc exited 0 while the test held .box-c.lock, so it never waited for the lock` |
| MEDIUM-1 | `tc read` outside the lock | `test_read_holds_the_inbox_lock_from_glob_to_rename` | `AssertionError: tc exited 0 while the test held .box-b.lock, so it never waited for the lock` |
| MEDIUM-1 | marker write with no handler | `test_a_marker_that_cannot_be_written_is_said` | an error, not a failure: `IsADirectoryError: [Errno 21] Is a directory: '<root>/mail/.ring-pending-c.<pid>.tmp'` |
| MEDIUM-2 | the truthiness check alone | `test_a_thread_id_of_another_shape_never_reaches_codex` | `"-x"`: `AssertionError: "ring failed for d: its card's thread_id is not a thread id; the mail is in its inbox; the next send to d rings again" not found in 'new inbox: nobody has joined as d\n'`; `5` and `["t1"]`: `AssertionError: 1 != 0 : exited 1: Traceback (most recent call last):` (a TypeError after the mail landed) |
| MEDIUM-2 | `tc join` takes any thread id | `test_join_refuses_a_codex_thread_id_of_another_shape` | `AssertionError: 0 != 1 : exited 0: ` |
| LOW-9 | local send outside the lock | `test_a_local_send_waits_for_a_held_inbox_lock` | `AssertionError: tc exited 0 while the test held .box-b.lock, so it never waited for the lock` |
| LOW-9 | local send takes the lock alone | `test_local_sends_share_the_inbox_lock` | `AssertionError: the send still waited 5 s on a lock the test held shared: it took the lock alone` |
| LOW-9 | `tc card` outside the lock | `test_tc_card_counts_and_writes_under_the_inbox_lock` | `AssertionError: tc exited 0 while the test held .box-x.lock, so it never waited for the lock` |
| MEDIUM-3 | warning keyed on the `card` argument | `test_the_new_inbox_warning_keys_on_the_card_file` | `AssertionError: Lists differ: ['new inbox: nobody has joined as b'] != []` |
| MEDIUM-3 | warning keyed on the inbox alone | `test_a_local_card_delivers_where_to_says_and_reports_to_routes_nothing` | `AssertionError: 'new inbox: nobody has joined as b\n' != ''` |
| MEDIUM-4 | C1's join chain for `tc card` | `test_tc_card_never_takes_this_sessions_account` | `AssertionError: Tuples differ: ('acct', 'other') != ('unknown', 'other')` (no flag, and a blank flag) |
| LOW-4 | health drops the target | `HealthCardsTest` | `AssertionError: '\ncards      b (claude, account unknown, route local), reports to a\n           c (codex, account work, route codex)\n           x (other, account far, route ssh to u@h)\n' not found in '...'` (machine lines cut) |
| LOW-10 | no route check | `test_a_card_with_no_route_is_refused_in_words` | `AssertionError: 'tc send: route None is not built yet; nothing sent\n' != "tc send: the card <root>/[185 chars]>.\n"`, and the same with `route 5` |
| LOW-11 | `sys.exit("tc send: empty message")` | `test_an_empty_message_is_refused_through_refuse_with_exit_1` | `AssertionError: 'tc send: empty message' != 1` |
| LOW-15 | the old words | `test_an_unreadable_card_is_refused_not_guessed` | `AssertionError: False is not true : tc send: the card <root>/cards/b.json is unreadable (Expecting property name enclosed in double quotes: line 1 column 3 (char 2)); nothing sent. Rewrite it with tc join or tc card.` |
| DEBT-3 | `.tmp` through `Path.write_text` | the two planted-link tests and the `.tmp` test | `AssertionError: 0 != 1 : exited 0: ` (message); `AssertionError: SystemExit not raised` (card); `AssertionError: 0 != 1 : the .tmp was not made by one os.open: []` |
| REC-13 | no note | `test_card_ssh_gives_route_ssh_and_the_default_remote_path` | `AssertionError: '' != 'note: sends to x are refused until the ssh route is built\n'` |
| REC-13 | the old refusal words | `test_a_route_not_built_yet_is_refused_and_writes_nothing` | `AssertionError: Tuples differ: (1, '', 'route ssh is not built yet\n') != (1, '', 'tc send: route ssh is not built yet; nothing sent\n')` |
| LOW-7 | kill the direct child only | `test_a_ring_that_times_out_kills_codex_and_its_child` | `AssertionError: False is not true : codex's own child outlived the timed-out ring` |
| LOW-8 | a strict decode | `test_odd_bytes_from_codex_never_fail_a_send` | `AssertionError: 1 != 0 : odd bytes from codex failed the send: exit 1` |
| REC-9 | no root in the ring | `test_two_sends_to_an_empty_codex_inbox_ring_once` | `AssertionError: Lists differ: [{'ar[69 chars]Run: <tc>[122 chars] ''}] != [{'ar[69 chars]Run: TC_ROOT=<root> <tc>[192 chars] ''}]` (tc's path cut to `<tc>`) |
| REC-9 | the root unquoted | `test_the_ring_names_the_root_and_quotes_it` | `AssertionError: 'MAIL: 1 unread for c. Run: TC_ROOT=<root>[212 chars]o a.' != "MAIL: 1 unread for c. Run: TC_ROOT='<root>[216 chars]o a."` |

One test change came out of these runs, in `fd01c39`: the first run of
LOW-7's mutation stayed green. The fake's child slept 5 s and the test
polled for up to 5 s, so it watched the child exit on its own. The fake
now sleeps `ORPHAN_SLEEP_SECONDS = 30`, past the poll, and the row above
is the rerun. The MEDIUM-2 red lines were taken at `fe3f7fa`, before
MEDIUM-3 removed the new-inbox warning from that stderr.

### Verify, fix round 1

At `fd01c39`, in `~/TheConnection-lanes/cards`:

```
$ python3 -m unittest tests.test_cards -v         # Ran 16 tests, OK
$ python3 -m unittest tests.test_codex_route -v   # Ran 17 tests, OK
$ python3 -m unittest tests.test_router -v        # Ran 15 tests, OK
$ python3 -m unittest tests.test_health -v        # Ran 8 tests, OK (the two ResourceWarning lines, as before)
$ python3 -m unittest discover -s tests -p 'test_*.py'
Ran 83 tests in 21.258s
OK
$ node --test tests/*.test.mjs
# tests 8
# pass 8
# fail 0
```

CORE's `tests/test_mailbox.py` (on the dev branch, not in this tree) was
run against this `tc` in a scratch copy with the dev branch's
`tests/_root.py`: K1 and K3 to K8 pass, K3's 50 senders included. **K2
fails**, and will on merge: `AssertionError:
PosixPath('<root>/root/mail/to-b/000001-from-a.tmp') not found in [] :
the .tmp was not written through Path.write_text, so this test's write
record misses tc's writes; wrap what tc now uses`. K2 records writes by
wrapping `Path.write_text`; DEBT-3 (item 17 of the brief) makes the
message `.tmp` with `os.open`, as the brief requires. K2's own message
names the fix: record `os.open` too, as
`test_a_card_is_written_through_a_tmp_and_renamed` now does. K2 is not
in this lane's work set, so it is left for the architect or CORE.

Settled before merge (architect note): `62d8a6d` on the dev branch
widened K2's recorder to `os.open`, `open()` and `Path.write_text`, and
a trial merge of the dev branch with this lane ran 97 tests OK. CARDS
merged at `4f35efc` with K2 green.

## Not verified

- CORE's K2 after merge: settled by `62d8a6d` before the merge (see the
  architect note under "Verify, fix round 1").
- Real `codex`. The argv, the flags `--thread` and `--message`, and the
  exit codes come from the plan (C2, D3), not from a run; the fixture's
  label says so. Every codex test ran against a fake or with `Popen`
  swapped; the refusing stub stood behind the fake. Donald runs the real
  one (D4).
- The 30 s ring timeout end to end. The in-process stand-in checks the
  30 s and the group kill; the real kill ran with the timeout patched to
  2 s.
- Whether a real `codex queue` started through node leaves a native child
  (LOW-7's premise comes from tc's own docstring, not from a run).
- The marker's removal failing (the `rang codex <to>, but <marker> could
  not be removed` warning). No test reaches it.
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
- Fix round 1: a codex send reads the card before it takes the inbox
  lock. A `tc card` that turns a codex name into an ssh name in that gap
  (with an empty inbox) leaves the message in the local inbox. It needs
  that rare change and a millisecond overlap; not closed.
- Fix round 1: C3's gate calls `deliver_local` directly, so a gated send
  takes no inbox lock and a `tc card` race stays open there. For the SSH
  lane before S3, with the ring gap the audit's blast radius already
  names.
- Fix round 1: the inbox lock file is opened in append mode, so it never
  truncates, but it follows a link planted at its name, as the wait and
  watch locks do. Under C4's group-writable `mail/` that is the same class
  as DEBT-3. Left as it is.
