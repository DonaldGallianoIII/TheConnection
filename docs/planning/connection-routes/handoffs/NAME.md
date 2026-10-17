# Handoff: NAME, hints say the name tc was invoked by

Model:  Claude Opus 5.5 (the NAME lane agent)
Status: unreviewed
Date:   2026-10-17
Branch: Claude-Development-TheConnection-NAME, from
        Claude-Development-TheConnection at 34872ce
Where:  ~/TheConnection-lanes/name
Brief:  ~/TheConnection-lanes/briefs/NAME.md

a2's ruling, from the brief: the file and the command stay `tc`, so every
live session keeps working. Most Linux systems already have a `tc` (the
kernel's traffic control), so a stranger may link ours as `tconn`. tc
then tells them commands under that name.

## Commits

| Item | Commit | Subject |
|---|---|---|
| 1, 2, 4 | `96b0aae` | Say the invoked name in tc's hints and usage lines (NAME items 1 and 2) |
| 3 | `1760810` | Link tc as tconn when the system has a tc (NAME item 3) |
| 4 | the commit that adds this file | This handoff |

Line numbers below are at `96b0aae`.

## The function

`invoked_name()` (`tc:1222`) returns the base name of `sys.argv[0]`. It
falls back to `DEFAULT_INVOKED_NAME`, `"tc"` (`tc:458`), when that base
name does not fullmatch `INVOKED_NAME_PATTERN` (`tc:463`): letters,
digits and `._+-`, a letter, digit or underscore first, at most
`INVOKED_NAME_MAX_CHARS` (255, a Linux file name's limit, `tc:462`).
"Unusable" means a word a person could not paste into a shell as it
is. Two cases matter in practice:

1. `python3 -c` sets `sys.argv[0]` to `-c`. A leading dash fails.
2. `python3 -m unittest` sets it to `python3 -m unittest`. The spaces
   fail. So the suite's module loads still print `tc`.

No global holds the name. Each hint calls the function where it builds
its words, or a function calls it once into a local `tc`.

## Each hint changed

Every one is a command the words tell a person to run.

| Where | Words, run as `tconn` |
|---|---|
| `tc:579` `OWN_FIX_WORDS`, used at `tc:1561`, `tc:2906`, `tc:6890` | `runs tconn init --shared --group <g>, which fixes their own entries ...` |
| `tc:1060` `ORIGINS_NOT_MADE_WORDS`, used at `tc:3961` | `The user who ran init (<user>) runs tconn init --shared --group <g> again ...` |
| `tc:1098` `NOBODY_JOINED_LISTEN_WORDS`, used at `tc:4710` | `its owner runs tconn join <name> first` |
| `tc:1107` `NO_INBOX_LISTEN_WORDS`, used at `tc:4793` | `Run tconn join <name>, which makes it.` |
| `tc:1334` `shared_problem_words` | `Run tconn init --shared --group <g> to rewrite it.` |
| `tc:2333` `settle_marker_mode` | `run tconn init again, or set it by hand` |
| `tc:5074` `cmd_wait` | `MAIL: 1 unread for b. Run: tconn read b` |
| `tc:5080` `cmd_wait` | `KEEPALIVE: ... Re-arm: tconn wait b --keepalive` |
| `tc:5082` `cmd_wait` | `TIMEOUT: ... Re-arm: tconn wait b` |
| `tc:5581` `cmd_join` | `Run tconn join inside the Codex session.` |
| `tc:5619` `cmd_join` | `1 unread waiting for b: run tconn read b` |
| `tc:5677` `cmd_card` | `Read it first (tconn read b), or pass --force.` |
| `tc:5763` `card_route` | `Ask y's owner to rejoin (tconn join y, ...), or ... with tconn card y --ssh <target>.` |
| `tc:6007` `deliver_local` | `Ask b's owner to rejoin (tconn join b, run as that Linux user) ...` |
| `tc:7722` `file_outcome` | `...; kept in outbox: <path>. Run: tconn flush` |
| `tc:7879` `deliver_ssh` | `Write it again with tconn card <name> --ssh <target>.` |
| `tc:7934`, `tc:7938` `deliver_ssh` | `... kept in outbox: <path>. Run: tconn flush`, `... queued behind them. Run: tconn flush` |
| `tc:8094`, `tc:8117`, `tc:8145` `cmd_flush` | `with tconn card <name> --ssh <target>, then run tconn flush`; `then run tconn flush.`; `each member sends their own with tconn flush` |
| `tc:9556`, `tc:9567` `cmd_watch` | `Re-arm after handling: tconn watch a`, `Re-arm: tconn watch a` |
| `tc:9613` `main` | the parser's `prog`, so `usage: tconn wait ...` and `--help`; the description's `its tconn wait exits` and `runs tconn join once` |

Each changed function's `@deps` names `invoked_name`, and the module
block's `@interacts` says what NAME does. Doc blocks that quote a hint
(`file_outcome`, `deliver_ssh`, `cmd_join`) now say the invoked name.

## What stays `tc`, and why

1. **The prefixes that name the tool.** `tc send: empty message`,
   `tc: bad name ...`, `tc init: ...`, `tc wait: ...`, `tc gate: refused`
   and the rest. They say which program spoke, not a command to type.
   They are pinned word for word by contract text and by many tests, and
   a far key reads the gate's. Changing them would change every one of
   those for no gain to the person who has to act.
2. **argparse's own error line follows `prog`.** A usage error prints
   `usage: tconn wait ...` and then `tconn wait: error: ...`. That second
   line is argparse's, built from `prog` (`TcParser.error`), and the
   brief asks that `prog` say the invoked name. It is the one prefix
   that changes.
3. **The codex ring's message** (`tc:6706`'s `run`). It already names
   tc's full path, so it works under any link name.
4. **Mentions that describe, not instruct.** `ALREADY LISTENING: another
   `tc wait b` is running` names a process that may have been started
   under either name. `the next tc flush sends it again`, `only tc init
   makes it`, `another tc is sending to it right now (a send or a tc
   flush)`, and help strings such as `the kind tc works out` and `a far
   tc's ssh route` name the tool or the far machine's tc. A far machine's
   tc is not this process, so this process's name says nothing about it.
5. **The board.** `board/serve.py` runs tc by its path, so its feed is
   unchanged.

## Tests

New: `tests/test_invoked_name.py`, four tests. It runs tc through a
symlink named `tconn` in the root's temp folder, outside `TC_ROOT`
(python3 on the link's path, as the harness runs tc), and by its plain
path:

1. `test_the_mail_line_names_the_invoked_name`: `wait b` with mail
   waiting prints exactly `MAIL: 1 unread for b. Run: tconn read b`, and
   `... Run: tc read b` under the plain name.
2. `test_the_timeout_line_names_the_invoked_name`: exit 2, a `TIMEOUT:`
   line ending `Re-arm: tconn wait b`, and `Re-arm: tc wait b`.
3. `test_the_usage_line_names_the_invoked_name`: a missing name exits 9
   with stderr starting `usage: tconn wait `, and `--help` starts
   `usage: tconn `; the same with `tc`.
4. `test_an_unusable_argv0_falls_back_to_tc`: `sys.argv[0]` set to `""`
   and to `python3 -m unittest` (through `python3 -c` and `exec`, since
   `runpy.run_path` sets it back to the file's path) gives
   `usage: tc wait `.

No existing test pins a hint's words in a way that changed. Under the
plain name every hint reads as before, and the suite runs tc by its
path, so no existing test needed an edit.

### Red, before the fix

`python3 -m unittest tests.test_invoked_name -v`, with the test in place
and `tc` at 34872ce: 4 run, 3 failed, each on the `tconn` subtest:

```
AssertionError: 'MAIL: 1 unread for b. Run: tc read b' != 'MAIL: 1 unread for b. Run: tconn read b'
AssertionError: False is not true : TIMEOUT: no mail for b in 1s. Re-arm: tc wait b
AssertionError: False is not true : usage: tc wait [-h] [--timeout TIMEOUT] [--keepalive] name
```

The plain-name subtests and the fallback test passed then, as they
should: at 34872ce `prog` was the constant `"tc"`.

### Green, after

`python3 -m unittest tests.test_invoked_name`: 4 run, OK.

`python3 -m unittest discover -s tests -p 'test_*.py'` at `96b0aae`:
362 tests, OK, in 245 seconds (358 at 34872ce, plus the four new).
The four `ResourceWarning: unclosed file` lines it prints are in earlier
full runs too; `tests/test_invoked_name.py` run alone with
`-W always` prints none.

`node --test tests/*.test.mjs`: 68 tests, 68 pass, 0 fail.

### Mutations

Run with `PYTHONDONTWRITEBYTECODE=1` on a scratch copy of `tc`,
`tests/_root.py` and `tests/test_invoked_name.py`, never in the
worktree.

1. **`invoked_name` returns `DEFAULT_INVOKED_NAME` always.** Red: 3
   failed of 4, the same three lines as the red run above, first
   `AssertionError: 'MAIL: 1 unread for b. Run: tc read b' != 'MAIL: 1 unread for b. Run: tconn read b'`.
2. **`invoked_name` returns the base name with no fallback.** Red: 2
   subtests failed, `usage:  wait [-h] ...` for `""` and
   `usage: python3 -m unittest wait [-h] ...` for the spaced form.

## Docs

`README.md`, its install step: run `command -v tc` first. Nothing
printed, link ours as `tc`. A path printed, such as `/usr/sbin/tc`,
link ours as `tconn` and type that name. A paragraph says the hints
follow the name and the refusal prefixes stay `tc`. `JOIN.md`: one
sentence after the `TC_ROOT` paragraph, saying a session types the name
its user linked tc under.

Walked by hand in a throwaway home and `TC_ROOT` under the scratch
folder: `command -v tc` printed `/usr/sbin/tc` on this machine, the
`tconn` link went into the throwaway `~/.local/bin`, and through it
`send`, `wait` (MAIL line), a missing name (usage and error lines),
`--help` and an empty send (`tc send: empty message`, exit 1) printed as
the README says; `~/TheConnection/tc wait` by path printed `Run: tc read
a`. Also by hand: `card` with unread mail, a send to a card with no
route, and a `watch` heartbeat, each naming `tconn`.

## Not verified

1. `git clone` from the README was not run: the walk used a copy of this
   branch's `tc`, not the public `main`.
2. The "it printed nothing" branch: this machine has `/usr/sbin/tc`, so
   `command -v tc` never came back empty here. Its `ln` line is the one
   the README had before.
3. The ssh and shared-mailbox hints under `tconn` were checked by
   reading and by the unchanged suite under the plain name, not by a run
   under `tconn`. Real ssh was not run (rule 5).
4. Running a test file as a script (`python3 tests/test_flush.py`) sets
   `sys.argv[0]` to that file, so any module-loaded test that checks a
   hint's words would see `test_flush.py` in it. No test file was run
   that way. The documented commands use `python3 -m unittest`, where
   the fallback gives `tc`, and that is what ran.
