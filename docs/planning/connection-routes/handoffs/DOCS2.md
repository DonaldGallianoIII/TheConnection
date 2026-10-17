# Handoff: DOCS2, three doc items (R40, R41, R26)

Model:  Claude Opus 5.5 (the DOCS2 lane agent)
Status: unreviewed
Date:   2026-10-17
Branch: Claude-Development-TheConnection-DOCS2, from
        Claude-Development-TheConnection at ca0b368
Where:  ~/TheConnection-lanes/docs2
Brief:  ~/TheConnection-lanes/briefs/DOCS2.md

Docs only. No change to `tc`, `board/` or `tests/`.

## Commits

| Item | Commit | Subject |
|---|---|---|
| 1, R40 | `88c2ac9` | Make the local, shared and ssh QA walks pasteable and end in moves aside (R40) |
| 2, R41 | `b4f3a3a` | README: the board from a laptop over SSH, and a second user's tc and prompt (R41) |
| 3, R26 | `b5d3010` | README: how to clear a closed session's "no listener" for good (R26) |
| handoff | the commit that adds this file | This handoff |

Line numbers below are at `b5d3010`.

## Item 1, R40: QA wording

**route-local.md.**

- Step 2 (`qa/human/route-local.md:37` to 47): the check is now `ps -o
  args= -p NNNN` with the pid health named, and it passes when `ps`
  prints that one process's command line, `python3 ./tc wait b
  --timeout 300`. The old `pgrep -f "tc wait b"` printed the wait's pid
  and two others in my run, so "lists the same number" read
  as a count.
- Step 3 (`:48` to 56): the command and the two expected lines are
  fenced blocks. The expected line holds backticks of its own, which
  split the old inline code span in two.

**route-shared.md.**

- Opens with "What you need" (`qa/human/route-shared.md:11`), "The
  order, with route-ssh.md" (`:30`) and a short "What this checks"
  (`:43`). The Model block's round list, the outbox section's note and
  the old lead paragraph moved, words kept but for each opening clause,
  under "Round history" at the end (`:764`). The outbox section keeps a
  one-line attribution comment where its note was.
- `$M` (steps 16 and 17, `:200` and `:205`): ann's shell no longer sets
  what ben's uses. Each shell sets `M` itself, and ben checks it with
  `ls -l $M` before the tries, which prints the current folder's
  listing when `M` is empty.
- Moves aside, never rm. Step 4 (`:82`) has each user make
  `~/tc-qa-aside` once. Every "Put it back" that removed something now
  moves it there: steps 17, 22, 26, 30, 31, 32, 36, 37, 44 and 45.
  Step 33's `.watch.lock.planted-1`, a file tc itself moved aside,
  stays where tc put it until the cleanup moves the whole mailbox. The
  cleanup (`:743`, steps 46 to 50) unsets `TC_ROOT`, has sudo move
  `/srv/tc-shared` and `/srv/team` into a new 0700 `/srv/tc-qa-aside`,
  points at route-ssh.md's cleanup, and names what is left for the
  owner to remove: `/srv/tc-qa-aside`, each user's `~/tc-qa-aside`, and
  the group with both users in it. No `groupdel` or `gpasswd` is
  given: that removal is the owner's.
- One `rm` stays, on purpose: step 17's `rm $M`, which ben runs to show
  that it is refused (`Operation not permitted`). It is the check, not
  advice.

**route-ssh.md.**

- "The order, with route-shared.md" (`qa/human/route-ssh.md:67`): alone,
  1 to 28; with route-shared, both as ann, route-ssh 1 to 22, then
  route-shared 1 to 45, then route-shared's cleanup, then route-ssh's
  cleanup once, last.
- "Undo every step" is now "Cleanup" (`:287`, steps 23 to 28). Config
  edits stay (the gate lines, the Host blocks, `ssh-keygen -R`, which
  keeps the old file as `known_hosts.old`). Every `rm` is a move into
  `~/tc-qa-aside` on that machine. Step 27 (`:317`) names what is left
  for the owner. The old step 27, record the results, is step 28.

## Item 2, R41: two README gaps

- **The board from a laptop over SSH** (`README.md:663`): `ssh -L
  8780:127.0.0.1:8780 <host>`, then the printed URL as it is. Same port
  on both ends, since serve.py answers 421 to a Host naming another
  port; with `--port 8781`, `-L 8781:127.0.0.1:8781`.
- **A second Linux user's tc** (`README.md:447`, new shared step 4): the
  same checkout, if the group can read it and every folder above it, or
  the member's own clone at the same commit (`git -C ~/TheConnection
  rev-parse HEAD` the same in both). With `TC_ROOT` set, tc keeps
  nothing beside itself, so the member needs no write access to the
  checkout. The old steps 4 to 6 are 5 to 7; nothing referred to them
  by number.
- **The prompt that points a session at the shared root**
  (`README.md:471`, in step 6): `your mailbox is TC_ROOT=/srv/tc-shared.
  read ~/TheConnection/JOIN.md and follow it. your name is ben, your
  relay is ann.`, with the checkout's path in place of `~/TheConnection`
  when ben runs ann's, and the relay prompt with the same prefix.

## Item 3, R26: clearing "no listener" for good

`README.md:580`. The brief's check held, so the line gives that command:
`tc wait <name> --timeout 1`, once, as the name's own Linux user. With
mail waiting it ends on `MAIL:` instead, records `mail`, and a running
board warns `woken · not read` until the mail is read; the line says
so. It never advises rm.

## Commands run

Every run used a throwaway `TC_ROOT` under my scratch folder, written
`<scratch>` here, with `CLAUDECODE` and `CLAUDE_CONFIG_DIR` unset, `./tc`
from this worktree. Every background child was stopped by its own pid.
No real `ssh`, no real `codex`.

| For | Command | Result |
|---|---|---|
| R40 route-local 1 | `./tc join a --account work`, `./tc join b --account work --reports-to a` | `joined as a (other, account work, route local)`, `joined as b (other, account work, route local), reports to a` |
| R40 route-local 2 | `./tc wait b --timeout 300 &`, `./tc health` | `listeners  b (pid 577446)` |
| R40 route-local 2 | `ps -o args= -p 577446` | `python3 ./tc wait b --timeout 300` |
| R40 route-local 2, the old check | `pgrep -f "tc wait b"` | three pids: the wait and two other processes whose command lines held the words |
| R40 route-local 3 | `./tc wait b --timeout 5; echo $?` | step 3's ALREADY LISTENING line, word for word, and `3` |
| R40 route-shared 17 | `ls -l $M`, with `M` unset, then set | unset: the current folder's listing; set: the one file |
| R40 route-shared moves | every new `mv` of steps 17, 22, 26, 30, 31, 32, 36, 37, 44 and 45, the step 4 `mkdir -p -m 0700`, and step 47's `mkdir -m 0700` and `mv` (without sudo), in a one-user copy: a private mailbox with paths standing in for `/srv` and a home | each exits 0; links and a FIFO move as themselves (`lrwxrwxrwx`, `prw-r--r--` in the aside folder), never their targets; `tc read` and `tc health` work on the mailbox after the moves |
| R40 route-shared 33 | a `.watch.lock.planted-1` file left in an inbox, then `tc health`, `tc send`, `tc read`, `tc wait --timeout 1`, `tc watch --heartbeat 1` | exits 0, 0, 0, 2, 0; nothing names the file |
| R40 route-ssh cleanup | in a stand-in home: `ssh-keygen -q -t ed25519 -N '' ...` (a made-up key), `ssh-keygen -R <made-up host> -f <scratch>/known_hosts`, `mkdir -p -m 0700 ~/tc-qa-aside` twice, `mv` of the two key files and a `tc-qa-home` folder | `-R` exits 0 and prints `Original contents retained as .../known_hosts.old`; the second `mkdir -p` exits 0; the moves exit 0 |
| R41 board | `python3 board/serve.py` (port 8780 was free) | `board: http://127.0.0.1:8780/live.html#token=<t>` |
| R41 board | `curl` the feed with the token and Host `127.0.0.1:8780`, `localhost:8780`, `127.0.0.1:9000` | `200`, `200`, `421` |
| R41 board | `python3 board/serve.py --port 8786`, `curl` `live.html` with Host `127.0.0.1:8786`, `localhost:8786`, `127.0.0.1:8787`, `example.lan:8786` | `200`, `200`, `421`, `421` |
| R41 shared tc | a copy of `tc` in a 0555 folder, run by its path with `TC_ROOT` elsewhere: `tc join ben`, `tc health` | `joined as ben (...)`, exit 0; the card listed; nothing written beside the copy |
| R41 shared tc | `git -C <this worktree> rev-parse HEAD` | a 40-hex commit id (run on this worktree, never on `~/TheConnection`) |
| R26 | `./tc wait b --timeout 300 &`, a board on `--port 0` reading the feed, then `kill -9` the wait | health `stopped: b (listening, 3s ago)`; `.wait.exit` reads `listening <time>`; feed state `down` |
| R26 | `./tc wait b --timeout 1; echo $?` | `TIMEOUT: no mail for b in 1s. Re-arm: tc wait b`, `2`; `.wait.exit` reads `timeout <time>`; health `stopped: b (timeout, 0s ago)`, not `listening`; feed `idle`, again 4 s later, and `idle` on a fresh board |
| R26, mail waiting | the same kill, then `tc send --from a --to b ...`, then `./tc wait b --timeout 1` | `MAIL: 1 unread for b. Run: tc read b`, exit 0; record `mail`; health `stopped: b (mail, 1s ago)`; feed `working` at once, `woken` after 130 s, `working` after `tc read b`; a fresh board `idle` |

Not run: the `ssh -L` line (rule 5), anything as a second Linux user or
with sudo, the new prompt in a real Claude session, and either QA walk
as a whole. The route-shared moves ran as one user; across two users
they rest on the modes the file already states (a sticky folder lets
an entry's owner, and the folder's owner, move it).

## Checks

`python3 ~/Conventions/tools/check_voice.py` and
`python3 ~/Conventions/tools/check_american.py` on `README.md`,
`qa/human/route-local.md`, `route-shared.md`, `route-ssh.md` and this
file: clean, 0 failures, 0 warnings, each.

## Leak scan

The pattern list at `~/TheConnection-lanes/tools/leak-patterns.txt`,
case-insensitive, over every file the tree tracks at `b5d3010`, over
the four files the three commits changed, and over the three commit
messages: no hits. This file and its commit message are scanned again
before the report.
