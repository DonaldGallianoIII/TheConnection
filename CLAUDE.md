# TheConnection, project guide

Model:  Claude Opus 5.5 (the GROUND lane agent), 2026-10-14
Status: unreviewed

> **First instruction:** read this whole file before responding to any request.
> Conventions: `~/Conventions/CLAUDE.md`, in the owner's conventions folder.
> Deviations are marked below.

TheConnection is `tc`, a file mailbox that lets agent sessions message each
other. Today it serves Claude Code sessions run by one Linux user on one
machine: one message is one Markdown file, and a session wakes when the
`tc wait` it started in the background exits. The plan in
`docs/planning/connection-routes/` grows it into the one way any agent
session reaches any other, on this machine or another, and says which way
to use when. It is for the owner's own sessions and for anyone who forks it.

---

## Project-specific context

### What this is

A mailbox, not a chat server. `tc send` writes a file. `tc wait` polls one
inbox and exits when mail lands, and that exit is what wakes the Claude Code
session that started it. `tc health` and `tc watch` report on the machine,
the sessions and the listeners.

Done, for the current plan: every case in the routing rule below works.
That means address cards, a router in `tc send`, the `codex`, `ssh` and
shared-mailbox routes, a read-only live board, tests for the core mailbox,
and a README a stranger can follow. The plan's index is
`docs/planning/connection-routes/00-index.md`.

### Tech stack

- Python 3, standard library only. `tc` is one file.
- Linux and WSL2 only. It uses `flock`, `RLIMIT_AS` and `/proc`. macOS and
  Windows are out of scope.
- The board look kit (`board/`) is plain ES modules and CSS, no libraries,
  tested with `node --test`.
- No installs, no server, no network of its own. SSH is the only way off the
  machine, and only through the planned `ssh` route.

### Architecture

Two ideas carry the whole tool.

1. **The folder is the transport.** `mail/to-<name>/NNNNNN-from-<sender>.md`
   is unread mail. `tc read` moves it to `read/`, which is the history. A
   counter in `mail/.seq`, under `flock`, numbers every message. A message is
   written to a `.tmp` sibling and renamed, so a reader never sees half a
   file.
2. **The lock is the proof of life.** `tc wait <name>` holds an exclusive
   `flock` on `mail/.wait-<name>.lock` for as long as it runs, and the kernel
   drops it the moment the process dies. `tc health` reads `/proc/locks` to
   name the pid holding each lock. "Listening" is checked there, never taken
   on someone's word.

### Key patterns

- Every tunable is a module constant at the top of `tc` with a comment
  saying why (`POLL_SECONDS`, `DEFAULT_WAIT_SECONDS`,
  `WAIT_MEMORY_CAP_BYTES`). `ROOT` is the only other global.
- `TC_ROOT` moves the whole mailbox. Every test and every hand run uses its
  own `TC_ROOT` in a temp folder.
- Exit codes are the interface for the waking side. `tc wait`: 0 mail,
  2 timeout, 3 a listener for that name already runs. `tc watch`:
  0 heartbeat, 5 alert, 3 already watching.
- Tests run `tc` as a subprocess, or load it as a module without running
  `main()` (`tests/test_keepalive.py` shows how). New tests build on the
  shared harness, `tests/_root.py`.
- `tc` is one file that several lanes edit. Each lane adds its own functions
  and touches only the shared spots named in `00-index.md` section 4: the
  `ROUTES` table (planned, contract C2), the argparse block in `main()`, and
  the module doc block's `@interacts` line.

### Current focus

The connection routes plan, run in lanes and waves
(`docs/planning/connection-routes/00-index.md` section 4). Wave 0 is GROUND:
this file, `docs/known-bugs/` and `tests/_root.py`. CORE, CARDS and BOARD
wait on GROUND's merge; SHARED, SSH and DOCS come after them.

### Off limits

- `main`. Nobody commits to it or merges toward it; the owner does that.
- The live mailbox: `mail/` and `status/` in any checkout that sessions use.
  Tests and hand runs never touch them.
- `docs/planning/connection-routes/contracts.md`. A lane that needs a
  contract changed writes a pause instead.
- The owner's conventions folder (`~/Conventions/`). Read it; never edit it
  from here.
- The Azure CLI, anything that touches Azure, and Docker. Real `ssh` and
  real `codex`: only the owner runs those, in the human QA scripts.

---

## Layout

```
tc                                 the whole tool (python3, stdlib only)
JOIN.md                            what you point a new session at
board/                             look kit for a visual session board; demo.html shows every state
tests/test_*.py                    unittest suites (health, keepalive, ...)
tests/*.test.mjs                   node --test suites for the board look
tests/_root.py                     shared harness: throwaway TC_ROOT, proven listener, fake ssh and codex
qa/human/                          step-by-step scripts a person runs
docs/known-bugs/                   INDEX.md plus one detail file per entry. See ~/Conventions/code/KNOWN-BUGS.md.
docs/planning/connection-routes/   the plan: 00-index, contracts, phases, decisions, handoffs/, pauses/
mail/to-<name>/NNNNNN-from-X.md    unread messages (gitignored)
mail/to-<name>/read/               read messages, kept as history
status/<name>.md                   each side's latest status (gitignored)
```

Lane worktrees live at `~/TheConnection-lanes/<lane>`, one branch per lane.

---

## Commands

```bash
python3 -m unittest discover -s tests -p 'test_*.py'   # every Python test
python3 -m unittest tests.test_root -v                  # one suite, by module
node --test tests/*.test.mjs                            # the board look tests
python3 ~/Conventions/tools/check_voice.py FILE.md      # dashes, machine register
```

There is no single check script. Run these by hand before every commit.

**The American English check needs care.** `~/Conventions/tools/check_american.py`
takes no file argument: it scans only the conventions folder it lives in, so
its "clean" says nothing about a file in this repo. Run its word list on
your file instead. The lane coordinator's wrapper does that:
`python3 ~/TheConnection-lanes/tools/american-on.py FILE.md`. It prints
`american english: N hit(s) in M file(s)` and exits 1 on any hit.

**The voice check skips phrases in any file named `CLAUDE.md`.** The
exemption list in `voice-rules.yaml` names `CLAUDE.md`, so on this file
`check_voice.py` checks characters and slang only.

---

## Rules specific to this project

### The routing rule

**The rule** (Donald, 2026-10-14, decision D1):

| Case | Use |
|---|---|
| Two Claude sessions under **one account** on one machine | Claude Code's native messaging (SendMessage). Not tc. |
| **Codex**, or any tool with no native path | tc, `codex` route |
| **Several Claude accounts** on one machine, several SSH windows | tc, `local` route. **The headline case.** |
| A separate Linux user per account on one machine | tc, shared mailbox (C4) |
| Sessions on **another machine** | tc, `ssh` route |
| Unsure | tc |

Why the native path is not the whole answer even for one account: a
session in a different permission mode holds a native message for its
user's approval and can let it expire, and the mailbox is a record anyone
can read on disk.

### Rules every executing agent carries

From `00-index.md` section 9. Rule 2 names the commit identity in general
words and rule 12 names the owner's conventions folder; the rest is word
for word.

1. **Stay in your lane.** Edit only the files your task names, plus the
   shared spots in section 4. Anything else is a pause.
2. **Branch and commits.** Work in your worktree on your lane branch. Never
   `main`. Never push, never merge. Commit by path (`git add <paths>`), never
   `git add -A`. The message says what changed and why and ends with
   `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. The repo is
   personal; commits go out under the repo's configured personal identity.
3. **No deletion.** No `rm` at all, no `git clean`, no `git reset --hard`,
   no deleting a branch. The one exception: a test's own
   `TemporaryDirectory` cleaning itself up in teardown. No test touches the
   live `mail/` or `status/`: every test runs under its own `TC_ROOT`.
4. **Never run the Azure CLI (`az`) or anything that touches Azure. Never
   run Docker.**
5. **Agents never run real `ssh` or real `codex`**, in tests or by hand.
   Tests put a fake on `PATH` that records its argv. The fake must be
   asserted called, or the test passes by not checking. Donald runs the
   real ones, in the human QA scripts.
6. **A listener is proven, not claimed.** Start `tc wait` only in the
   background with a timeout, and prove it by `tc health` naming its pid
   (it reads `/proc/locks`). "Listening" without that is a false claim
   (known bug `listener-reported-live-without-the-lock`). Every child a test
   starts is killed in teardown by its own pid; never `pkill -f`.
7. **Every claim names its proof.** "Tests pass" names the file and the
   command. A commit message cites only tests in the tree at that commit
   (known bug `test-claimed-that-is-not-in-the-tree`).
8. **Code rules.** Python 3 stdlib only. Linux and WSL2 only. No magic
   numbers: module constants with a comment saying why, as `tc` does. No
   globals beyond `ROOT` and the constants. A doc block on the module and
   every function with `@interacts`, `@deps`, `@complexity`, `@alloc`; `tc`'s
   own header is the pattern. A stale tag is worse than none: an edit that
   changes a block's behavior updates the block.
9. **Web rules.** No `innerHTML`. Meaning never rides on color alone: every
   state has a glyph and a word, ports differ by shape, a wire carries an
   arrow and a label. Clean up timers, observers and listeners on teardown.
10. **A question the brief cannot answer is a pause.** Write it to
    `docs/planning/connection-routes/pauses/<lane>-<n>.md`: the question,
    the options, your recommendation. Carry on with what does not depend on
    it. Never guess an interface.
11. **Attribution.** A new file starts with a header naming the model and
    `Status: unreviewed`. A new block in an existing file gets a one-line
    comment saying the same.
12. **Voice.** No em dashes, no en dashes. No machine register: the
    banned words and phrases are in
    `~/Conventions/tools/voice-rules.yaml`; read it once.
    Short sentences, concrete nouns. American English. Run
    `python3 ~/Conventions/tools/check_voice.py` and
    `check_american.py` on every Markdown file you write.

Rule 12's American check: see the note under Commands. `check_american.py`
alone proves nothing about a file here.

### QA

No `qa/bot/` in this plan. The unittest suite is the scripted playthrough
for every deterministic loop (send, wait, ring, forward, flush, gate, feed).
The human scripts in `qa/human/` cover the rest (`00-index.md` section 10).

---

## Deviations from the conventions

None.

---

## Status

The tool runs today on one machine: send, read, peek, wait (with
`--keepalive`), status, log, health and watch, plus the board look kit.
The core mailbox commands (send, read, peek, wait, log, status) have no
tests in the tree yet; CORE writes them.

GROUND (P0) adds this file (G1), `docs/known-bugs/` (G2) and
`tests/_root.py` (G3), one commit each on the GROUND lane branch. All three
are unreviewed until the review relay closes and the owner says merge.
Nothing else in the plan is built.
