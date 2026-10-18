# TheConnection, project guide

Model:  Claude Opus 5.5 (the GROUND lane agent), 2026-10-14; kept
        current at each merge by the architect session (Claude Opus 5.5)
Status: unreviewed

> **First instruction:** read this whole file before responding to any request.
> Conventions: `~/Conventions/CLAUDE.md`, in the owner's conventions folder.
> Deviations are marked below.

TheConnection is `tc`, a file mailbox that lets agent sessions message each
other. Today it serves Claude Code and Codex sessions on one machine, run
by one Linux user or by several who share one mailbox, and it has an
`ssh` route to another machine (built and tested with a fake ssh; not yet
run between two real machines). One message is one Markdown file, and a
session wakes when the `tc wait` it started in the background exits. The plan in
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
- The board (`board/`) is plain ES modules and CSS, no libraries, tested
  with `node --test` and a headless browser check. `board/serve.py`
  serves it and its live feed.
- No installs and no network of its own. The one server is the board's
  (`board/serve.py`, contract C6): bound to 127.0.0.1 only, its feed
  behind a token made at start. The page asks no other host (D26). SSH
  is the only way off the machine, and only through the `ssh` route:
  `tc send` to an ssh card on this side, `tc gate` (a forced command in
  `authorized_keys`) on the other.

### Architecture

Two ideas carry the whole tool.

1. **The folder is the transport.** `mail/to-<name>/NNNNNN-from-<sender>.md`
   is unread mail. `tc read` moves it to `read/`, which is the history. A
   counter in `mail/.seq`, under `flock`, numbers every message. A message is
   written to a `.tmp` sibling, hard-linked to its name and the `.tmp` name
   removed, so a reader never sees half a file and a message never replaces
   another.
2. **The lock is the proof of life.** `tc wait <name>` holds an exclusive
   `flock` on `mail/to-<name>/.wait.lock`, a `0600` file its owner makes
   inside its own inbox (D35), for as long as it runs, and the kernel drops
   it the moment the process dies. `tc health` reads `/proc/locks` to name
   the pid holding each lock, and names a holder only when it is the inbox
   owner's own process. "Listening" is checked there, never taken on
   someone's word.

### Key patterns

- Every tunable is a module constant at the top of `tc` with a comment
  saying why (`DEFAULT_WAIT_SECONDS`, `WAIT_MEMORY_CAP_BYTES`,
  `CACHE_TTL_SECONDS`); the one exception is `tc report`'s few
  constants, which sit beside `cmd_report` (DASH's work set named only
  that spot). The only other globals are `ROOT` and the
  paths built from it (`MAIL`, `STATUS`, `SEQ_FILE`, `CARDS`), plus
  `ROOT_FROM`, which says whether `TC_ROOT` set ROOT or tc's own folder
  did (R2; `tc health` prints it). tc fixes all six at import, from
  `TC_ROOT`.
- `TC_ROOT` moves the whole mailbox. Every test and every hand run uses its
  own `TC_ROOT` in a temp folder.
- Exit codes are the interface for the waking side. The one table is
  under "Exit codes" at the top of
  `docs/planning/connection-routes/contracts.md`. Read it there; this file
  keeps no copy. A usage error (a mistyped flag, a missing argument)
  exits 9 (D12, merged with CARDS), so it can never pass for a `tc wait`
  timeout, which is 2. A session re-arms its listener only on 0 (after
  reading the mail) or 2, starts none on 3, and on any other code stops
  and tells its relay.
- Tests run `tc` as a subprocess, or load it as a module without running
  `main()` (`tests/test_keepalive.py` shows how). A load reads `TC_ROOT`
  once, at import, from the test process's own environment. The harness
  cleans its children's environment, not that one. So a module loaded
  inside `with TcRoot() as root` points at the checkout's own `mail/`,
  or, if the shell exports `TC_ROOT`, at whatever that names, which can
  be a live mailbox. The harness root is the only safe target: set
  `os.environ["TC_ROOT"]` to `str(root.path)` before the load, inside
  the `with`, and restore the old value after. Patching `ROOT`
  after the load moves nothing: `MAIL`, `STATUS`, `SEQ_FILE` and `CARDS`
  keep the old paths. New tests build on the shared harness, `tests/_root.py`.
- `tc` is one file that several lanes edit. Each lane adds its own functions
  and touches only the shared spots named in `00-index.md` section 4: the
  `ROUTES` table (contract C2, built by CARDS), the argparse block in
  `main()`, and the module doc block's `@interacts` line, plus the merged
  spots `00-index.md` section 4 lists.

### Current focus

The connection routes plan, run in lanes and waves
(`docs/planning/connection-routes/00-index.md` section 4). Wave 0, GROUND
(this file, `docs/known-bugs/` and `tests/_root.py`), merged into the dev
branch at `a029bda`, CORE at `f5f6923`, CARDS at `4f35efc` and BOARD at
`a2953cb`, with the P4 phase review's fixes at `eb3e187`, and SHARED
(wave 2) at `84b97d2`, and SSH (wave 2b) at `616b9db`, with the P3 phase
review's fixes (D35 to D37) at `8b9b59d`, and F1, the wait exit record,
at `f57e490`, F2, the switch-over cleanup, at `d03fab9`, and DOCS (P5)
at `4179b88`. Every lane of the plan is merged, and the relay's picks
from the review backlog after it (DOCS-1, NAME, R30, R2, DOCS2,
EMPTYROOT, R39, EXITOK) are merged too. On the owner's ask the same
evening: read times (READTIME, D41) at `db142f9`, the README's
record-of-work section (RECORD) at `e2be34f`, and `tc report` (DASH v1,
D42) at `7b77092`. Next are a main update and the owner's human walks.

### Off limits

- `main`. Nobody commits to it or merges toward it; the owner does that.
- The live mailbox: `mail/`, `status/`, `cards/`, `outbox/` and `.shared`
  in any checkout that sessions use. Tests and hand runs never touch them.
- `docs/planning/connection-routes/contracts.md`. A lane that needs a
  contract changed writes a pause instead.
- The owner's conventions folder (`~/Conventions/`). Read it; never edit it
  from here.
- A cloud provider's CLI, anything that touches a cloud account, and
  Docker. Real `ssh` and real `codex`: only the owner runs those, in the
  human QA scripts, with the one exception rule 5 records (D30: the
  architect, real `ssh` only, to the owner's laptop).

---

## Layout

```
tc                                 the whole tool (python3, stdlib only)
JOIN.md                            what you point a new Claude session at
JOIN-CODEX.md                      what you point a new Codex session at
board/                             the live board: serve.py (127.0.0.1, token), live.html, look.js, theme.css; demo.html shows every state; report.py draws tc report's page (C7)
tests/test_*.py                    unittest suites (mailbox, names, cards, router, codex route, usage, health, shared, ssh, ...)
tests/test_inbox_pinned.py         the class proof that every inbox act works inside one pinned folder (D35)
tests/test_wake_files.py           the class proof that no member holds or redirects another's lock, ring record or exit record (D35, D36, F1)
tests/test_wait_exit.py            the wait exit record: writer, reader, tc watch, tc health and the board (F1)
tests/test_read_times.py           the read-time record: tc read writes it, tc log shows it, tc peek leaves it (D41)
tests/test_report.py               tc report: the facts, the scrub, each chart, the refusals, the same bytes twice (C7, D42)
tests/*.test.mjs                   node --test suites for the board
tests/board-browser-check.mjs      headless check of the live board (needs a Playwright install)
tests/_root.py                     shared harness: throwaway TC_ROOT, proven listener, fake ssh and codex
qa/human/                          step-by-step scripts a person runs
docs/known-bugs/                   INDEX.md plus one detail file per entry. See ~/Conventions/code/KNOWN-BUGS.md.
docs/planning/connection-routes/   the plan: 00-index, contracts, phases, decisions, handoffs/, pauses/
mail/to-<name>/NNNNNN-from-X.md    unread messages (gitignored)
mail/to-<name>/read/               read messages, kept as history
mail/to-<name>/read/.read-times    when each was read: one JSON line per message tc read moved (name, number, read time), 0640, its owner's, appended; a plant there is moved aside as .read-times.planted-<k> (D41)
mail/to-<name>/.wait.lock          the listener's lock, 0600, its owner's (D35); .watch.lock beside it for tc watch; a file planted there is moved aside as .wait.lock.planted-<k>
mail/to-<name>/.wait.exit          the wait's exit record, 0640, its owner's: listening, mail or timeout and a time; never proof of life (C5, F1)
mail/.wait-<name>.lock             the lock's old place before D35: tc never reads it since F2; old files may remain until the owner removes them
mail/.box-<name>.lock              the inbox lock: send's count plus write, read's glob, renames and read-time record, tc card's check plus write (D14)
mail/.ring-pending-<name>          the codex ring's state: ringing, failed, timed out, joined with unread mail, or clear; never removed (D14, D16, D20)
cards/<name>.json                  one address card per name: kind, account, route (gitignored)
.shared                            the group a shared mailbox uses, 0644, written by init (gitignored)
outbox/<user>/to-<name>/           ssh mail one member queued for a far name, with sent/ and refused/; a .stderr note beside a file holds the far side's last words (D25, D32, D36; gitignored)
outbox/<user>/.send-<key>.lock     that member's send lock for one target, 0600 (D33)
outbox/<user>/.rang-<name>         that member's last ring of a codex name, 0600; its time decides re-rings (D36)
outbox/.origin-token               this mailbox's random origin token (D25)
mail/.origins/<user>/<key-name>/   on the receiving side, the origin ids each far key delivered, so a retry never lands twice; init makes mail/.origins/ (D25, D33, D36)
status/<name>.md                   each side's latest status (gitignored)
```

Lane worktrees live at `~/TheConnection-lanes/<lane>`, one branch per lane.

---

## Commands

```bash
python3 -m unittest discover -s tests -p 'test_*.py'   # every Python test
python3 -m unittest tests.test_root -v                  # one suite, by module
node --test tests/*.test.mjs                            # the board tests
python3 board/serve.py                                  # the live board; open the printed URL
NODE_PATH=<playwright>/node_modules node tests/board-browser-check.mjs   # headless board check
python3 ~/Conventions/tools/check_voice.py FILE.md      # dashes, machine register
python3 ~/Conventions/tools/check_american.py FILE.md   # American spelling
```

There is no single check script. Run these by hand before every commit.
Each checker reads the files it is given and exits 1 on a hit.

The `~/Conventions/` tools, and the lane worktrees under
`~/TheConnection-lanes/`, live on the owner's machine. A fork without them
skips those checks or brings its own.

**The voice check skips phrases in any file named `CLAUDE.md`.** The
exemption list in `voice-rules.yaml` names `CLAUDE.md`, so on this file
`check_voice.py` checks characters and slang only. To voice-check a
`CLAUDE.md`, copy it to another name outside the repo first and check the
copy.

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

### Rules every executing agent carries

From `00-index.md` section 9, all 13, word for word. No rule here
differs from the plan's.

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
   One exception (D30, Donald, 2026-10-15): the architect session alone
   may run real `ssh` to the owner's laptop for the SSH lane's
   two-machine QA (`tc gate`, the outbox, `tc flush`), in its own scratch
   folder there, with light runs, touching nothing else on that machine,
   removing what it set up, and asking first before any change to an ssh
   config, a key, `authorized_keys` or a Windows setting. Results are
   scrubbed of machine names, aliases and addresses. Lane agents and
   fixers never run real `ssh`.
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

### QA

No `qa/bot/` in this plan. The unittest suite is the scripted playthrough
for every deterministic loop (send, wait, ring, forward, flush, gate, feed).
The human scripts in `qa/human/` cover the rest (`00-index.md` section 10).

---

## Deviations from the conventions

*Deviation:* no check script. The conventions copy the checkers from
`~/Conventions/tools/` into a repo and wire them into one check script.
This repo runs the owner's tools in place, by hand, from the list under
Commands.

*Deviation:* no `qa/bot/` step. The unittest suite is the scripted
playthrough for every deterministic loop (`00-index.md` section 10); the
human scripts in `qa/human/` cover the rest.

*Deviation:* JavaScript naming in `board/look.js`. Its `CONFIG` keys are
SCREAMING_SNAKE_CASE (the owner's first look kit, `349f36f`, began that
way, and every key and importer since follows it), a helper it does not
export is private without an underscore, and boolean locals may be plain
adjectives (`flow`, `down`). The conventions ask for PascalCase keys, an
underscore on private helpers and an is, has or can prefix. Accepted
from the P4 phase review rather than renamed: no JavaScript file here
follows those three rules, and the rename would churn a file contract C6
pins.

*Deviation:* uppercase lane ids in file names. Handoff and pause files
take the plan's lane ids as they are (`handoffs/GROUND.md`,
`pauses/GROUND-1.md`), against the lowercase-with-hyphens rule. Accepted,
not renamed: the plan's `<lane>` path templates give every lane these
names.

---

## Status

The tool runs today: send, read, peek, wait (with
`--keepalive`), status, log, health and watch; join, card and cards for
address cards; a router in send with the `local`, `codex` and `ssh`
routes, with `flush` for queued ssh mail and `gate` for inbound ssh;
`init --shared` for a mailbox several Linux users share; `report` for a
static HTML page of the mailbox; plus the live board (`python3
board/serve.py`).
`tests/test_mailbox.py` (CORE, K1 to K8) tests send, read, peek, wait,
log, status and the counter, each test proven by a hand mutation of
`tc`.

GROUND (P0) built this file (G1), `docs/known-bugs/` (G2) and
`tests/_root.py` (G3) on its lane branch. After the lane's two review
rounds, the architect merged it into the dev branch,
`Claude-Development-TheConnection`, at `a029bda`, with the merge
approved for the owner as decision D8 allows. `89bdd2e` followed with two
post-merge fixes, and the P0 phase review (D9) closed with a fix round at
`ab7bd31`. CORE (P1) merged at `f5f6923`, the K2 recorder fix at
`62d8a6d`, CARDS (P2) at `4f35efc`, and BOARD (P4) at `a2953cb`: the
live board (`python3 board/serve.py`, a token in the printed URL; a
headless check in `tests/board-browser-check.mjs`). The P4 phase review
(D9) closed with two fix rounds merged at `eb3e187`. The shared mailbox
(SHARED, P3's first half) merged at `84b97d2` after eight review rounds;
its two-user walk (`qa/human/route-shared.md`) is the owner's and not
yet run by a person. The `ssh` route (SSH, P3's second half) merged at
`616b9db` after its lane review and one fix round; real ssh has not run
yet: its two-machine walk (`qa/human/route-ssh.md`) is the architect's
under D30. The P3 phase review (D9) found that one member of a shared
mailbox could redirect, block or mislabel another's mail or listener; its
fix round (D35 to D37, five rounds, two reviews) merged at `8b9b59d`,
with the class proofs in `tests/test_inbox_pinned.py` and
`tests/test_wake_files.py`. F1, the wait exit record (D28, D37 part 2),
merged at `f57e490`: `tc watch --names` no longer calls a listener that
mail woke down, and the board reads a killed one as down after a restart
too, its pill warning only on a fresh stop. Nothing has run as a second
Linux user yet. F2 removed the switch-over at `d03fab9`: tc never reads
the old lock place again. DOCS (P5), the plan's last lane, merged at
`4179b88`: a README led by the routing rule, JOIN.md, JOIN-CODEX.md and
the human QA per route (`route-local`, `route-codex`, `two-accounts`,
`shapes`, beside `route-ssh` and `route-shared`). The plan's exit test,
a stranger getting two sessions talking from the README alone, waits for
a person to walk `qa/human/route-local.md`. After DOCS, from the review
backlog: an empty text argument refuses (DOCS-1, `8fe7e32`); `tc` keeps
its name and its hints say the name it was invoked by, so it can be
linked as `tconn` where the system has a traffic-control `tc` (NAME,
`3f2fc77`); the test loaders write no bytecode (R30, `ca0b368`); `tc
health` names the mailbox it read (R2, `9914051`); QA wording and two
README gaps (DOCS2, `0d96dfb`); an empty `TC_ROOT` refuses in tc and the
board (EMPTYROOT, `7ef22e3`); every README command and the exit table are
tested (R39, with `EXIT_OK`). `tc read` records when each message was
read in `read/.read-times`, and `tc log` shows it (READTIME, D41,
`db142f9`); the README says the mailbox is a record of the work
(RECORD, `e2be34f`); `tc report OUT.html [--scrub]` draws the mailbox
as one static HTML page, safe to share when scrubbed (DASH v1, D42,
`7b77092`; `qa/human/report.md` not yet walked by a person).
`main` stays the owner's alone.
