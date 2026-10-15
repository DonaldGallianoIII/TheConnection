# Connection routes: the plan index

Model:  Claude Opus 5.5 (the TheConnection architect session), from
        Donald's asks of 2026-10-14 and the plan shape a planning
        session (Claude Fable 5.1) sent the same day
Status: draft. Reviewed once by the planning session (Claude Fable
        5.1, 2026-10-14, 24 findings, all folded in). Being built: P0,
        P1, P2 and P4 are merged into the dev branch (P4's phase fix
        round is running); P3's SHARED half is in its fix round, its SSH
        half and P5 are not started (CLAUDE.md's Status has the
        commits). Every item marked default is Donald's to confirm or
        overrule (section 11).
Date:   2026-10-15

> **Read this file first.** It says what the plan builds, how the work is
> cut into lanes, which lanes run at the same time, and the rules every
> executing agent carries. `contracts.md` holds the interfaces lanes build
> against. `phases.md` holds the tasks. `decisions.md` is the record.

---

## 1. What this plan builds

TheConnection today is a file mailbox for Claude Code sessions run by one
Linux user on one machine. This plan makes it the one way any agent
session reaches any other, wherever it runs, and says plainly which way to
use when.

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

**Any shape** (Donald, 2026-10-14, decision D7). No hub is assumed.
Real setups look like any of these, and both routing and the board handle
all of them:

- one relay, many workers: `a` to `b`, `c`, `d`
- a relay whose worker is itself a relay for others: `a` to `b`, and `b`
  to `c`, `d`
- two or more orchestrators side by side, each with its own workers, and
  sometimes mailing each other

The router never reads a hub from anywhere (C2). The board draws its
edges from mail that actually moved, and ranks levels from an optional
`reports_to` hint on the card, falling back to what the mail shows (C5).
With no hints at all it still draws every shape, and says which roles it
inferred.

Donald's three ways of working, each of which must work by the end:

1. Claude sessions on his computer, SSHed into another box that is the dev
   environment. The sessions and the mailbox are local: `local` route.
2. Claude sessions running on a box; he sends them messages from his
   computer: `ssh` route, outbound.
3. Rarely for him, likely for someone else: agents on another machine
   messaging his main computer: `ssh` route, inbound, through `tc gate`
   so a remote key can deliver mail and do nothing else.

What gets built:

- **Address cards.** Each mailbox name has a card saying what it is (Claude,
  Codex), which account, and how mail reaches it. `tc join` writes it.
- **A router in `tc send`.** It reads the card and delivers by route:
  `local`, `codex` (file plus the `codex queue` doorbell), `ssh` (forward to
  the other machine's tc).
- **A shared mailbox** (`tc init --shared --group`) so separate Linux users
  on one machine can all write to it.
- **`tc gate`**, an SSH forced command, so inbound SSH can only run `tc send`
  and `tc health --json`.
- **An outbox** for mail the ssh route could not deliver, and `tc flush`.
- **The live board**: a stdlib server on 127.0.0.1 with a token, feeding the
  board look real mailbox state.
- **Tests** for the core mailbox (CORE, merged at `f5f6923`).
- **The README** rewritten around the rule above, a "which route am I" chart,
  and one section per route. `JOIN.md` for Claude, `JOIN-CODEX.md` for Codex.

## 2. Not in scope

- A network transport of its own. SSH is the only way off the machine.
- Mounting another machine's mailbox (sshfs, NFS). flock across those is
  not reliable and the message counter depends on it.
- Pushing into an idle Claude session from outside. No supported way exists;
  Claude keeps its `tc wait` listener in every account.
- Board actions that wake a model (pings, "send from the board"). The board
  only reads in this plan. Each wake is a paid turn.
- Windows and macOS. Linux and WSL2 only, as today.
- Auth beyond the Linux user, SSH keys and the board's token.

## 3. Phases

| Phase | What | Exit condition |
|---|---|---|
| P0 Ground | Repo `CLAUDE.md`, `docs/known-bugs/INDEX.md`, the shared test harness | An Opus agent given only a brief and the repo can run every test, read the rules and the two known bugs |
| P1 Core tests | Tests for send, read, peek, wait, log, status | All pass; each named mutation turns its test red |
| P2 Cards and Codex | Names, address cards, `tc join`, the router, the `codex` route, the two behavior fixes | A Claude sends to a Codex and the Codex wakes, through `tc send` alone |
| P3 Routes | `ssh` route, outbox, `tc flush`, `tc gate`; the shared mailbox | Mail crosses to a second machine and back; inbound SSH can do nothing but deliver |
| P4 Live board | Feed, server, live page | The board draws the real mailbox and follows it as mail moves |
| P5 Docs | README, `JOIN.md`, `JOIN-CODEX.md`, QA scripts per route | A stranger forks it and gets two sessions talking by following the README |

## 4. Lanes and the schedule

Ceiling: **3 lanes at once.** Lanes in one wave start together.

| Wave | Lane | Phase | Waits on | Size |
|---|---|---|---|---|
| 0 | GROUND | P0 | nothing; `contracts.md` approved by Donald | small |
| 1 | CORE | P1 | GROUND merged | medium |
| 1 | CARDS | P2 | GROUND merged | medium |
| 1 | BOARD | P4 | GROUND merged (builds against C1 and C5, not CARDS' code) | medium |
| 2 | SHARED | P3 | CARDS merged | small |
| 2b | SSH | P3 | SHARED merged | medium |
| 2, 2b | BOARD (continues if not done) | P4 | | |
| 3 | DOCS | P5 | every other lane merged | medium |

```
GROUND --> CORE ------------------------------+
       \-> CARDS --> SHARED --> SSH ----------+--> DOCS
       \-> BOARD -----------------------------+
```

**Why CORE and CARDS run together** when the planner's shape put tests
first: Donald asked for speed. CORE writes tests only, CARDS changes
`tc`. The order is kept at the merge instead of at the start: **CORE merges
first**, and CARDS' review runs CORE's tests against CARDS' branch before
CARDS merges. A send that CARDS broke fails there.

**Why SHARED before SSH:** both edit `main()`'s argparse block and `tc`'s
doc block in the same wave. SHARED is small, so it goes first and SSH
starts from its merge. Costs a little time, saves a merge by hand on the
one file every lane touches.

**Shared files.** `tc` is one file, and CARDS, SSH and SHARED all edit it.
Each lane adds its own functions and touches only these shared spots, one
line each where it can: the `ROUTES` table (C2), the argparse block in
`main()`, the module doc block's `@interacts` line. In the merged code
from CARDS on, also: `main()`'s start (SHARED's umask must run before any
write), the exit-code constants, `write_new_file` and `inbox_lock` (SHARED
needs both to honor the group and setgid; the SSH gate needs the lock),
and the route tests in `tests/test_router.py` that assert `ssh` is not
built (SSH flips them). The architect resolves those at merge. BOARD never edits `tc`: `board/serve.py` loads it as a
module (C5). Any other file two lanes both need is a pause (rule 10).

## 5. Contracts

In `contracts.md`. Fixed before wave 1; a lane that needs one changed
writes a pause, never edits the contract.

| Id | What | Consumers |
|---|---|---|
| C0 | Mailbox names | every lane |
| C1 | The address card | CARDS writes; SSH, SHARED, BOARD, DOCS read |
| C2 | The router and the `ROUTES` table | CARDS builds; SSH, SHARED add routes |
| C3 | The `ssh` route, outbox, `tc flush`, `tc gate` | SSH |
| C4 | The `shared` route | SHARED |
| C5 | The board feed | BOARD |
| C6 | The board server | BOARD |

## 6. Review at every lane's done point

1. The lane agent commits its last task and writes
   `docs/planning/connection-routes/handoffs/<lane>.md`: what was built,
   what was not, every assumption, every pause.
2. The architect runs `/djinn:review standard --base <the lane's base>
   --goal "<the lane's exit line from phases.md>"` in the lane's worktree.
   **SSH and BOARD get `full` scope**: SSH builds a remote command line,
   BOARD opens a port.
3. HIGH and MEDIUM become briefs; one Opus fixer takes up to 20 findings
   (Donald's preference), and the split is stated. LOW never blocks.
4. Re-check with `/djinn:review quick` on the fix diff. Three rounds at
   most, then Donald.
5. a2 says merge, for Donald (D8). The architect merges the lane into
   `Claude-Development-TheConnection` and runs every test. Nobody merges
   toward `main`: that stays Donald's alone.

**After each phase lands** (D9), the architect runs a djinn review over
the merged dev branch: `/djinn:review standard --base <the commit before
the phase's first merge>` for P0, P1, P2 and P5, and `full` for P3 and P4
(a remote command line, an open port). The verdict and the HIGH and
MEDIUM counts go to a2 by mail.

The reviewer is never the session that built the lane. Every reviewer and
fixer runs on Opus. Fable is the escalation, after Opus has built and
reviewed and the problem is still there.

## 7. Lane setup

| Lane | Worktree | Branch | Board port |
|---|---|---|---|
| GROUND | `~/TheConnection-lanes/ground` | `Claude-Development-TheConnection-GROUND` | |
| CORE | `.../core` | `...-CORE` | |
| CARDS | `.../cards` | `...-CARDS` | |
| BOARD | `.../board` | `...-BOARD` | 8766 |
| SSH | `.../ssh` | `...-SSH` | |
| SHARED | `.../shared` | `...-SHARED` | |
| DOCS | `.../docs` | `...-DOCS` | 8767 |

Each branch starts from `Claude-Development-TheConnection` at the wave's
start. Every test and every hand run uses its own `TC_ROOT` in a temp
folder; the live `mail/` and `status/` are never touched.

## 8. Models

| Role | Model |
|---|---|
| Lane agents (write code, tests, docs) | Claude Opus 5.5, named on the dispatch |
| Reviewers and fixers | Claude Opus 5.5, a different session from the builder |
| Search and bulk reading, if a lane wants it | Sonnet or Haiku, read-only, never writes to the repo |
| Escalation | Claude Fable 5.1 |

## 9. Rules every executing agent carries

Pasted into every brief, word for word.

1. **Stay in your lane.** Edit only the files your task names, plus the
   shared spots in section 4. Anything else is a pause.
2. **Branch and commits.** Work in your worktree on your lane branch. Never
   `main`. Never push, never merge (the architect pushes lane branches and
   the dev branch, D10; never `main`, never a force push, never
   `--no-verify`). Commit by path (`git add <paths>`), never
   `git add -A`. The message says what changed and why and ends with
   `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. The repo is
   personal and public; commits go out under its configured personal identity.
3. **No deletion.** No `rm` at all, no `git clean`, no `git reset --hard`,
   no deleting a branch. The one exception: a test's own
   `TemporaryDirectory` cleaning itself up in teardown. No test touches the
   live `mail/` or `status/`: every test runs under its own `TC_ROOT`.
4. **Never run a cloud provider's CLI or anything that touches a cloud
   account. Never run Docker.**
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
    `~/Conventions/tools/voice-rules.yaml` (the owner's conventions folder);
    read it once. Short sentences, concrete nouns. American English. Run
    `python3 ~/Conventions/tools/check_voice.py <file>` and
    `python3 ~/Conventions/tools/check_american.py <file>` on every
    Markdown file you write. Each exits 1 on a hit.
13. **Public repo** (D11). Nothing sensitive goes into a file or a commit
    message: no keys, tokens or passwords, no real mailbox content, no
    hostnames, IPs or tailnet names, no email beyond the commit author, and
    nothing about the owner's employer or its systems. Test names and demo
    names are made up. Before every push, the pusher scans the whole tree
    at the branch tip and every new commit message with a pattern list
    kept outside the repo. A diff scan alone misses a stale tip. A commit
    message never quotes those patterns.

## 10. What every task carries, and what done means

Every task in `phases.md` carries: **files**, **do**, **out of scope**, a
**test spec** (property, a concrete input, the expected output, and a
wrong but plausible output the test must reject), **verify** (a command and
what its output must show), and a **PR line** for the commit.

**No `qa/bot/` in this plan:** the unittest suite is the scripted
playthrough for every deterministic loop (send, wait, ring, forward,
flush, gate, feed). The human scripts in `qa/human/` cover the rest.

**Done** for a task: its verify command shows what the task says, its test
fails when the named mutation is applied by hand and passes when restored,
the convention checks are clean, and it is committed. **Done** for a lane:
every task done, the handoff written, the review relay closed, Donald said
merge.

**The brief skeleton**, one task or one lane per dispatch:

```
You are the <LANE> agent for TheConnection. Model: Claude Opus 5.5; your
commits and new files name it.
WHERE: worktree <path>, branch <branch>. Stay in it.
READ FIRST, in order: CLAUDE.md; docs/known-bugs/INDEX.md;
docs/planning/connection-routes/00-index.md sections 1, 4, 9;
contracts.md (the contracts your lane names); README.md; tc (whole);
tests/_root.py; then your task's files.
YOUR TASKS: <ids from phases.md>, in order. Each task's files, do, out of
scope, test spec and verify are in phases.md; build exactly that.
RULES: <section 9, pasted>.
FINISH: commit each task by path; write handoffs/<lane>.md; report what you
verified with the command and its output, and nothing you did not.
```

## 11. Open items, with the default each lane builds to

| # | Item | Default until Donald says otherwise |
|---|---|---|
| O1 | `tc send` to a name nobody joined | Delivered, plus a warning on stderr: `new inbox: nobody has joined as <name>` |
| O2 | `tc peek` / `tc read` on an unknown name | Says `no unread mail`, creates nothing |
| O3 | Account label | `tc join --account <label>`; else the base name of `CLAUDE_CONFIG_DIR` if set; else the word `unknown`, never a blank |
| O4 | Mailbox name rule | `[A-Za-z0-9._-]`, 1 to 64 characters, refused otherwise (C0). Suggested form `<account>-<project>` |
| O5 | ssh route failure | Mail kept in `outbox/`, `send` exits 4 and says so; `tc flush` retries; no retry loop in the background |
| O6 | Inbound ssh | Only through `tc gate`. The README never shows an unrestricted key for this |
| O7 | Board port and poll | `127.0.0.1:8780` (8765 was taken on Donald's machine), token printed once at start, poll every 3 s |
| O8 | Remote names on the board | Drawn with route `ssh` and the words `remote · not checked`; no SSH from the board in this plan |
| O9 | Same-account Claude pairs | The board draws them as `native` with the words `native · not observed`, since tc cannot see that traffic |
| O10 | Role words | `orchestrator`, `worker`, `peer`, with `· inferred` when the role came from mail instead of a card (C5) |
| O11 | When mail alone makes a hub | `HUB_MIN_PARTNERS` = 2: a node with one partner is that partner's worker when the partner has two or more |

## 12. Files in this folder

| File | What |
|---|---|
| `00-index.md` | This file |
| `contracts.md` | C0 to C6 |
| `phases.md` | Every task, by lane |
| `decisions.md` | What was decided, by whom, when |
| `handoffs/` | One per lane, written by the lane agent |
| `pauses/` | Questions a lane could not answer |
