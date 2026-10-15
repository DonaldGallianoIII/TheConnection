# Connection routes: contracts

Model:  Claude Opus 5.5 (the TheConnection architect session)
Status: draft. Reviewed once by a planning session (Claude Fable 5.1,
        2026-10-14, 24 findings, all folded in). Amended for D7 (any
        topology) on 2026-10-14, and for the CARDS pauses (D13) the codex lost wake (D14) and the BOARD
        pauses (D15) the P1 and P2 phase review (D16), and the
        wave 2 rulings (D17 to D21) the same day, and D22 to D28 on
        2026-10-15.
        Fixed once a2 approves for Donald (D8); a lane that needs a change writes a pause and does not
        edit this file.
Date:   2026-10-14

Names below that exist in `tc` today were read from `tc` at commit
`1791cbf`: `ROOT`, `MAIL`, `STATUS`, `inbox()`, `unread()`, `next_seq()`,
`cmd_send()`, `cmd_health()`, `listeners()`, `health_snapshot()`, `main()`.
Everything else is new.

**Exit codes.** The one list. A lane that needs a new code writes a
pause; no lane reuses a number for a new meaning.

| Code | Meaning | Who exits with it | Since |
|---|---|---|---|
| 0 | ok (`wait`: mail; `watch`: heartbeat) | every command | today |
| 1 | refused with words: empty message, `--kind codex` with no thread, a route not built yet, a card over unread mail without `--force` | `send`, `join`, `card`, router | today (empty message), this plan |
| 2 | `wait` timed out or hit its keepalive | `wait` | today |
| 3 | another listener or watcher already holds this name's lock | `wait`, `watch` | today |
| 4 | kept in the outbox: ssh could not reach the target, or the target already has a queue | `send` (ssh route), `flush` | this plan (C3) |
| 5 | alert: load, memory, GPU or a named listener down | `watch` | today |
| 6 | bad name, under C0, for any name argument including `--reports-to`; also a self-report and a bad ssh target or remote path (including `~` alone or `~user/...`) | every command that takes a name, `card`, the ssh route | this plan (C0, C1, C3) |
| 7 | refused by the gate | `gate` | this plan (C3) |
| 8 | message over `SEND_BODY_MAX_BYTES` | `send`, `gate` | this plan (C0) |
| 9 | usage error: an unknown command, flag or missing argument; the usage text goes to stderr | every command (the parser) | this plan (D12) |
| 10 | busy: another process held `mail/.seq` or an inbox lock past `LOCK_WAIT_SECONDS`, or a send found `PUBLISH_MAX_TRIES` message numbers in a row taken by hand-made files (the next send starts past them); nothing written; try again. Never from `wait` or `watch`, so the re-arm rule below is unchanged. The ssh route and `flush` treat a far 10 like a dropped connection: the message stays queued (C3) | `send`, `read`, `card`, `join`, the codex route | this plan (D23) |

Why 9 (D12): argparse exits 2 on a usage error, the same code as a `wait`
timeout. A mistyped listener exits at once, its session reads 2 as a
timeout and re-arms the same typo, and that loops paid wakes. `tc`'s
parser overrides `ArgumentParser.error` to exit `EXIT_USAGE` (9) instead;
subparsers inherit it. A session re-arms its listener only on 0 (after
reading the mail) or 2, and never starts a second one on 3; on any other
code it stops and tells its relay (task D2).

---

## C0. Names and message size

**Names.**

- A name matches `^[A-Za-z0-9._][A-Za-z0-9._-]{0,63}$` (no leading dash)
  and is not made only of dots.
- `tc` checks every name it is given (`--from`, `--to`, `--as`, `read`,
  `peek`, `wait`, `status`, `join`, `card`) before it touches the disk,
  through one function `valid_name(name) -> bool`.
- A bad name: nothing is written, stderr says `tc: bad name "<name>":
  letters, digits, dot, dash, underscore, 1 to 64, not starting with a
  dash`, exit 6.
- Suggested form for many accounts: `<account>-<project>`, for example
  `work-api`, `home-football`. A suggestion in the README, not enforced.

Why: names become folder names here and words in a remote command line
over SSH (C3). A leading dash would read as an option there.

**Message size.**

- `SEND_BODY_MAX_BYTES = 1048576` (1 MiB): this is a mailbox for words.
- `send` reads at most that many bytes plus one from stdin
  (`sys.stdin.buffer.read(SEND_BODY_MAX_BYTES + 1)`), and checks a text
  argument the same way, **before** `next_seq()`.
- Over the limit: nothing written, no number used, stderr `tc send:
  message over 1 MiB; this is a mailbox for words`, exit 8. The gate (C3)
  inherits it.

## C1. The address card

One JSON file per name: `cards/<name>.json` under `ROOT`. Written whole to
a `.tmp` and renamed, like a message.

```json
{
  "version": 1,
  "name": "b",
  "kind": "claude",
  "account": "work",
  "route": "local",
  "session_id": "7fbd0da8-...",
  "pid": 119855,
  "thread_id": null,
  "ssh": null,
  "reports_to": null,
  "joined_at": "2026-10-14T12:00:00-05:00"
}
```

| Field | Values | Set by |
|---|---|---|
| `kind` | `claude`, `codex`, `other` | `tc join`: `codex` when `CODEX_THREAD_ID` is set, else `claude` when `CLAUDECODE=1`, else `other`. `--kind` overrides. `tc card`: `other` (D13). |
| `account` | a label, or `unknown` | `tc join`: `--account`; else the base name of `CLAUDE_CONFIG_DIR` if set; else `unknown`. `tc card`: `--account`, else `unknown`, since this session's account says nothing about a far name (D13). A blank value counts as not given. Never empty. |
| `route` | `local`, `codex`, `ssh` | `codex` for kind codex, `ssh` for a card made with `tc card --ssh`, else `local` |
| `session_id`, `pid` | from `CLAUDE_CODE_SESSION_ID`, `CLAUDE_PID` | `tc join` in a Claude session; null otherwise |
| `thread_id` | from `CODEX_THREAD_ID` | `tc join` in a Codex session; required for route `codex` |
| `ssh` | `{"target": "user@host", "tc": "/path/to/tc"}` | `tc card <name> --ssh user@host [--remote-tc PATH]`; `tc` defaults to `~/TheConnection/tc` |
| `reports_to` | a name (C0), or null | `--reports-to <name>` on `tc join` or `tc card`; null when not given. A hint for the board's levels (C5), never a route (D7). |

**What `tc join` reads.** Exactly these environment variables and no
others: `CODEX_THREAD_ID`, `CLAUDECODE`, `CLAUDE_CODE_SESSION_ID`,
`CLAUDE_PID`, `CLAUDE_CONFIG_DIR`. A Claude session's shell also holds
`CLAUDE_CODE_MESSAGING_SOCKET` and `CLAUDE_CODE_MESSAGING_TOKEN` (the
native path's socket and secret). A card is a readable file, group-shared
under C4, so **a card never carries a secret**. Observed in the architect
session on 2026-10-14: `CLAUDE_CONFIG_DIR` was not set, so the account
default lands on `unknown` unless each account runs with its own
`CLAUDE_CONFIG_DIR`. The two-accounts QA script (D4) records which.

**Checks on an ssh card.** `target` matches
`^[A-Za-z0-9._][A-Za-z0-9._-]*(@[A-Za-z0-9._][A-Za-z0-9._-]*)?$`: user at
host or host alone, no leading dash on either part, no spaces. The remote
`tc` path starts with `/` or `~/` and has no whitespace; `~` alone and
`~user/...` are refused, not guessed (D13). Otherwise `tc card` refuses
with words, exit 6, and writes nothing. If unread mail waits in
`mail/to-<name>/`, `tc card` refuses with exit 1 unless `--force`.

Commands:

- `tc join <name> [--account L] [--kind K] [--reports-to N]` writes the
  card for the session it runs in, prints `joined as <name> (<kind>,
  account <account>, route <route>)`, plus `, reports to <N>` when given. A name that already has a card is overwritten and `joined_at`
  reset (a restarted session rejoins). `--kind codex` with no
  `CODEX_THREAD_ID`: refused, exit 1, with the words why. A join that
  writes a codex card does it under the inbox lock and, when unread mail
  is already waiting (sent before the join, or rung to a thread that has
  since died), writes `mail/.ring-pending-<name>` so the next send rings
  the new thread, and prints `<n> unread waiting for <name>: run tc read
  <name>` (D16). With nothing waiting, it sets any old marker to clear,
  so an old thread's backoff never delays the new thread's first ring.
- `tc card <name> --ssh user@host [--remote-tc PATH] [--account L]
  [--reports-to N] [--force]` writes a card for a name that lives on another machine. If
  `mail/to-<name>/` holds unread mail here, refused with words naming the
  count (that mail would never be read once sends go remote), unless
  `--force`.
- `tc cards` prints every card, one line each, in words, with `reports to
  <N>` when set.
- `--reports-to` takes a C0 name (else exit 6, the C0 words). A name that
  reports to itself is refused: `tc: <name> cannot report to itself`, exit
  6, nothing written. The named mailbox need not exist yet. Two cards that
  report to each other are allowed; the board breaks the cycle (C5).
- **No card names a hub** (D7). `reports_to` is read only by `tc cards`,
  `tc health` and the board. Mail goes wherever `--to` says.
- **No card means route `local`.** Every mailbox that works today keeps
  working with no card.

## C2. The router

**No hub** (D7). The router delivers by the recipient's card alone. Any
name may send to any name, and no name is special: the README's `a` is a
default, not a role. A worker that is itself a relay for others is a name
that sends and receives, nothing more. Nothing in tc reads `reports_to` to
route.

`cmd_send()` keeps its arguments and its output for route `local`. After
checking names and size (C0) it reads the recipient's card and calls one
function from a table:

```python
ROUTES = {"local": deliver_local, "codex": deliver_codex}
# SSH adds its own line: "ssh": deliver_ssh
# Each: deliver_<route>(card_or_None, sender, to, body, header_note=None) -> Delivery
Delivery = collections.namedtuple("Delivery", "exit words warnings")
```

`send` prints `words` to stdout when `exit` is 0 and to stderr otherwise,
then prints each of `warnings` to stderr whatever the exit, then exits with
`exit`. A route named on a card that is not in `ROUTES` answers `tc send:
route <route> is not built yet; nothing sent`, exit 1, nothing written.

- `deliver_local`: today's behavior. Seq under flock, write `.tmp`, rename.
  If the inbox did not exist before **and the name has no card**, add the
  warning `new inbox: nobody has joined as <to>` (open item O1). A card is
  the record of a join, so a joined name gets no warning on its first mail,
  which matters for every Codex name: it never runs `tc wait` (D13). `header_note`, when given, is appended to
  the message's header line (the gate uses it, C3).
- `deliver_codex` (amended by D14, so a failed ring is never lost):
  1. Under the inbox lock `mail/.box-<to>.lock` (flock): count unread,
     check for the marker `mail/.ring-pending-<to>`, deliver through
     `deliver_local`, and decide to ring when the count was 0 **or** the
     marker says pending or timed out. Release the lock. The marker is a
     file that, once made, is never removed: its contents carry its state
     (pending, timed out, or clear), in both private and shared mode
     (D20).
  2. Outside the lock, ring:
     `codex queue --thread <thread_id> --message "MAIL: <n> unread for <to>. Run: TC_ROOT=<root> <tc path> read <to>, act on it, reply with TC_ROOT=<root> <tc path> send --from <to> --to <sender>."`
     (root and path quoted with `shlex.quote`). The marker is written
     **before** the ring (D16), so a sender killed mid-ring leaves it.
     with stdin from `/dev/null` and a timeout of `CODEX_RING_SECONDS`
     (30). The ring never runs under the lock, so a slow ring cannot
     block a `tc read`.
  3. Exit 0: set the marker to clear, and add the word line `rang codex <to>
     (queued; delivered when its turn ends or the session is resumed)`.
     Any other exit: keep the marker and add the warning `ring failed for
     <to>: <first stderr line>; the mail is in its inbox; the next send to
     <to> rings again`. A timeout: keep the marker, record in it that the
     ring timed out (its mtime is the time), and warn `ring failed for
     <to>: timed out; the mail is in its inbox; a send after HH:MM:SS
     rings again`, since the backoff (step 4) holds the next sends.
  4. **Backoff after a timeout** (D16): a send that finds a timed-out
     marker younger than `RING_BACKOFF_SECONDS` (300) skips the ring,
     keeps the marker and warns `ring pending for <to>: the last ring
     timed out at HH:MM:SS; a send after HH:MM:SS rings again`. A relay
     sending ten messages to a dead Codex would otherwise wait 30 s on
     each. A fast failure (a non-zero exit, not a timeout) starts no
     backoff.
  **The send still exits 0**: the mail landed. A card whose `thread_id` is
  not a string matching `[A-Za-z0-9][A-Za-z0-9._-]*` is not rung: the
  warning says `its card's thread_id is not a thread id`, and the marker is
  written. Two senders racing an empty inbox may both ring, and with the
  marker written before the ring, two quick sends may both ring: two
  doorbells, one read. Accepted, and said in the doc block, so nobody
  fixes it back into a lost wake.

`tc read` holds the same inbox lock from its glob of the inbox to its
last rename into `read/`, so a send cannot land a message between them
and skip its ring (D14). `tc peek` takes no lock: it moves nothing.

`tc read` and `tc peek` on a name with no inbox print `no unread mail for
<name>` and create nothing (open item O2).

## C3. The `ssh` route, the outbox, `tc flush`, `tc gate`

**Outbound** (`deliver_ssh`, added to `ROUTES` by the SSH lane):

```python
path = card["ssh"]["tc"]
# A quoted ~ never expands on the far side, so a leading ~/ goes bare and
# only the rest is quoted. Any other ~ form was refused when the card was
# written, and is refused again here (exit 6) for a hand-made card.
remote_tc = "~/" + shlex.quote(path[2:]) if path.startswith("~/") else shlex.quote(path)
argv = ["ssh", "-T", "-o", "BatchMode=yes", "-o", f"ConnectTimeout={SSH_CONNECT_SECONDS}",
        "--", card["ssh"]["target"],
        remote_tc + " " + shlex.join(["send", "--from", sender, "--to", to])]
subprocess.run(argv, input=body, text=True, capture_output=True,
               timeout=SSH_SEND_SECONDS)
```

- **The far side's login shell must be POSIX** (sh, bash, dash, zsh). ssh
  hands the remote command line to that shell, and the quoting above is
  POSIX quoting; fish or csh as the login shell would break it. The README's
  ssh section says so (D13).

- `SSH_CONNECT_SECONDS = 10`, `SSH_SEND_SECONDS = 30`,
  `SSH_CONNECT_FAILED = 255` (ssh's own exit for a connection failure).
- The body goes on stdin, never on the command line.
- **Every ssh send leaves a record** (D25). The outbox copies `mail/`'s
  layout: `outbox/to-<to>/NNNNNN-from-<sender>.md`, with `sent/` and
  `refused/` under each `to-<to>/`, so it parses exactly like an inbox
  and a name holding `-` never reads two ways. `deliver_ssh` first
  publishes the message there (same seq counter, same header as a
  message, the same no-replace publish as local mail), then sends it,
  then moves it to `sent/` on exit 0. A crash between the send and the
  move means `tc flush` sends it again: a duplicate, never a loss.
- **Origin ids make that duplicate harmless** (D25). Each ssh message
  carries an origin id: the sender's name, this mailbox's outbox number,
  and a random token made once per mailbox (never the hostname). It
  travels as `--origin <id>` on the remote command, checked against a
  fixed pattern. The far gate files each id it delivers and answers an id
  it has already filed with exit 0 and the words `already delivered`, so
  a flush retry never delivers twice. If the SSH lane cannot finish this
  in its first pass, it records it as a follow-up and builds the rest.
- **Queue order first.** If `outbox/` already holds mail waiting for this
  target (files directly in an `outbox/to-<to>/` whose card points at
  it), the new message is published behind it without trying: exit 4,
  words `<target> has <n> waiting in the outbox; queued behind them. Run:
  tc flush`. While a target has a queue, `tc flush` is its only sender.
- Exit 0: the file moves to `sent/`; words `sent over ssh to <target>:
  <remote stdout>`, exit 0.
- Exit 255 or a timeout (the connection failed): the message stays where
  it was published; words to stderr `could not reach <target> (<reason>);
  kept in outbox: <path>. Run: tc flush`, exit 4.
- **A far 10 is busy, not a refusal** (D23): the far tc could not get a
  lock in time and wrote nothing. Treat it like exit 255: keep the
  message in `outbox/`, exit 4, and `tc flush` retries it.
- **Any other non-zero is the far `tc`'s answer** (6 bad name, 7 refused,
  8 too large): the file moves to `refused/` with the far stderr beside
  it, tc prints that stderr and exits with its code, and nothing retries
  it. A refusal retried forever helps nobody.

**`tc flush [--to <name>]`**: tries each waiting outbox file in seq
order; on success moves it to its `sent/`; on a connection failure or a
far 10 for a target, stops trying that target, so its mail stays in
order; on a far refusal, moves the file to its `refused/` with the far
stderr beside it. Prints one line per file. Exit 0 when nothing is left
to send, 4 when anything is.

**Each sender's queue is their own** (D22). On a shared mailbox (C4),
ssh runs as the Linux user who ran `tc send`, with that user's keys, and
the far gate labels mail by key, never by `--from`. So `tc flush` sends
only the outbox files the running user owns, and "queue order first"
counts only the sender's own waiting files for that target. Flush says
how many files for a target belong to other members, and that each
member flushes their own. Order holds per sender per target. One
member's dead queue never holds up another member's mail.

**Inbound** (`tc gate`): for `~/.ssh/authorized_keys` on the receiving
machine, **one key per sending name**:

```
command="/home/you/TheConnection/tc gate --as homebox-b",no-pty,no-port-forwarding,no-agent-forwarding,no-X11-forwarding ssh-ed25519 AAAA... homebox
```

`tc gate --as <name>` reads `SSH_ORIGINAL_COMMAND`, splits it with
`shlex.split`, and allows exactly two shapes, ignoring only the first word
(the far side's path to its own tc):

- `<any> send --from <name> --to <name> [--origin <id>]`, both names
  valid under C0 and the id matching its fixed pattern (D25). The
  far side's `--from` is **ignored**: the message is delivered as from the
  `--as` name, **through the router** (C2) with the inbox lock and
  `header_note = "via ssh gate, key <as>"`, so a gated message to a codex
  name is rung and a card's route is respected (D16). A key can never
  speak as the relay or any other local name. Size limit (C0) applies.
- `<any> health --json`. Runs `cmd_health` **without the `cards` key**: a
  far key never reads account labels or ssh targets (D16).

**What the gate may run** (D18). The gate starts no shell. Its one
program is the codex ring, reached through the router for a recipient
whose card says codex: an argv list, the thread id validated (C2), and a
fixed message template holding only the validated name, `TC_ROOT` and
the words to run `tc read`. The ring never carries the message body or
any text the far side sent; the far sender's words reach Codex only
through `tc read`, like any mail. A gated message to a name whose local
card says `ssh` is refused, exit 7, `tc gate: <name> is not a local name;
the gate does not forward`. `tc send` and the gate share one path,
`route_and_deliver(sender, to, body, header_note=None)`, which holds the
route and inbox-lock steps; nothing else repeats them, since the inbox
lock is not re-entrant.

Anything else: stderr `tc gate: refused`, exit 7, nothing written. The gate
never starts a shell and never runs another program.

**The way back.** For replies, the far machine needs a card pointing at
this one, and the gate forbids `tc card`. A person writes it on the far
machine: `tc card <this-name> --ssh you@thisbox`. The README's ssh section
and the route-ssh QA script carry this as a numbered step on the far
machine.

## C4. The shared mailbox

For a separate Linux user per account on one machine.

- `tc init --shared --group <g>`: refuses unless the running user is in
  group `g` (`os.getgroups()`); creates `mail/`, `status/`, `cards/` and
  `outbox/` if they are missing, so no other user ever has to create a
  top folder inside a ROOT the first user owns (D19); then sets group
  `g` and mode `2775` on
  `mail/`, `status/`, `cards/`, `outbox/` and every folder under them,
  sets group `g` and mode `0664` on every file already under them
  (`mail/.seq` and the lock files included), and writes `ROOT/.shared`
  holding the group name.
- **Nobody can swap ROOT** (D21, D23). Init makes a missing ROOT `0755`
  and refuses a ROOT that its group or anyone may write. It then walks
  every folder from ROOT up to `/` and refuses, with words naming the
  folder, one owned by anyone but root or the user running init, or
  writable by its group or anyone without the sticky bit: ssh's own test
  for `authorized_keys` paths. Any of those would let a member rename
  ROOT and put their own `.shared` in its place. The owner of `.shared`
  gets no extra trust: whoever makes a folder can make the `.shared` in
  it, so that trust would certify itself (a member who made ROOT first
  would pass the init user's own first init). A member's rerun on the
  init user's ROOT is refused with words that name that user as the one
  who ran init and accuse no one, and a member fixes their own entries
  by hand, with the `chgrp` and `chmod` lines tc prints (D21, D23).
- **A held lock costs a failed send, never a hang** (D20, D23). `mail/.seq`
  and the inbox locks are group-writable, so a member can hold one. tc
  waits at most `LOCK_WAIT_SECONDS` per command for them, then exits 10
  with nothing written.
- While `.shared` exists, `tc` sets `os.umask(0o002)` before it writes
  anything, so every file and lock it makes is group-writable, and the
  setgid folders give them group `g`. Any folder `tc` creates later
  (`cards/`, `status/`, `outbox/`, an inbox and its `read/`) gets group
  `g` and mode `2775` as it is made. Init only reaches the folders that
  exist at the time (D16).
- **No planted links** (D17). The shared folders are group-writable, so
  one member could plant a link where another user's tc opens a file.
  - Every file tc opens by name (the wait, watch and inbox locks,
    `mail/.seq`, `status/<name>.md`, the ring marker) opens with
    `O_NOFOLLOW`; a link there is refused with words, exit 1, and nothing
    is written through it.
  - The shared folders (`mail/`, `status/`, `cards/`, `outbox/`) carry the
    sticky bit as well (mode `3775`), so a member cannot delete or rename
    another user's inbox, card or file, as in `/tmp`.
  - Before tc uses an inbox folder it checks it with `lstat` and refuses,
    exit 1, if it is a link and not a real folder.
  - Messages are read only from regular files (`O_NOFOLLOW`, `S_ISREG`, a
    size cap) by `read`, `peek` and `log`; a link or anything else in an
    inbox is skipped with words, left in place, and never printed, so a
    planted link cannot make another member's agent read a file from
    outside the mailbox (D19).
  - Lock and marker files open with `O_NONBLOCK` and an `S_ISREG` check,
    so a FIFO planted at a lock's name is refused with words instead of
    hanging tc (D19).
- **Nobody touches another member's mail** (D20, Donald: "prevent that
  from occurring"; it replaces D19's trust trade). Under shared mode:
  1. Each inbox folder (`mail/to-<name>/` and its `read/`) is owned by
     its recipient, with mode `3770` (setgid and sticky). `tc join`
     creates it as the joining user. Under sticky, only a file's owner or
     the folder's owner can delete or rename, so the recipient's `tc
     read` still moves anything into `read/`, and senders cannot touch
     each other's files.
  2. Message, card and status files are created `0640`, never
     group-writable, so nobody rewrites one in place.
  3. A local send to a name with no card is refused, exit 1, `tc send:
     nobody has joined as <name> on this shared mailbox`, whether or not
     an inbox exists (D21), so a sender never ends up owning someone
     else's inbox and a card-less inbox never takes mail. O1's deliver
     plus warning stays for a private mailbox.
  4. An inbox not owned by the owner of its recipient's card (an old
     one, or one made before this rule) is refused with words; tc never
     guesses.
  5. The files everyone must write stay group-writable and are never
     deleted under shared mode: `mail/.seq`, the lock files, and the ring
     marker (whose contents carry its state: pending, timed out, or
     clear, instead of being removed). The worst a member can do through
     them is make a send fail or ring once more; never read, lose or
     alter mail.
  6. `.shared` is `0644`, owned by whoever ran init and writable by that
     user only (D21), so no other member can change which group
     everyone's tc uses.
  The two-user cases are Donald's human QA (`qa/human/route-shared.md`),
  including a member trying to rewrite `.shared` and being refused.
- **The outbox is per sender** (D22). `outbox/` is sticky like the other
  shared folders, so a member cannot move another member's queued file,
  and a file sent with the wrong user's key would arrive labeled with
  that key's name. Each member's `tc flush` sends only their own files
  (C3).
- `tc health` says `mailbox shared with group <g>` or `mailbox private`.

## C5. The board feed

`board/serve.py` loads `tc` as a module and never edits it. It reads
tc's source, compiles it in memory and runs it in a fresh module, so it
never reads or writes a bytecode cache beside tc, which a member could
plant on a shared mailbox.

`feed()` returns one JSON object built from the parts of tc's health
that it reads (the machine's load and memory, the live listeners from
`/proc/locks`, the mailbox summary), the card files (read directly from
`cards/*.json` in C1's shape, **never** through a `cards` key in
`health`) and message file names. It never opens a message body, and it
never runs `nvidia-smi` or anything else slow on a request: the GPU part
of `tc health` is not on the board's path.

```json
{
  "at": "2026-10-14T12:00:00-05:00",
  "machine": { "load1": 0.25, "cores": 20, "mem_avail_pct": 78.9 },
  "nodes": [
    { "id": "a", "kind": "claude", "account": "work", "route": "local",
      "state": "listening", "listener_pid": 4242, "unread": 0,
      "last_mail_age_s": 30, "status": "reviewing parser",
      "role": "orchestrator", "role_source": "declared",
      "reports_to": null, "parent": null, "level": 0 }
  ],
  "wires": [ { "from": "a", "to": "b", "seq": 41, "age_s": 4 } ],
  "links": [ { "from": "a", "to": "b", "kind": "mailbox",
               "sent": { "a": 12, "b": 9 }, "last_age_s": 4 },
             { "from": "b", "to": "a", "kind": "reports_to" } ]
}
```

- `nodes`: every name with an inbox or a card. `state` is one of
  `listening` (a `tc wait` pid in `/proc/locks`), `writing` (sent within
  `WRITING_WINDOW_S` = 10), `doorbell` (route codex: no listener, and
  that is right), `remote` (route ssh: `remote · not checked`), `down`,
  `woken` (woken, not read), `working`, or `idle`.
- `down`: `serve.py` keeps `last_listening_at[name]` in memory for the
  life of the process. A name seen listening within `DOWN_WINDOW_S` = 600
  and not listening now, with no mail reaching its inbox since, is
  `down`: the lock vanished and nothing woke it. The lock file's time
  cannot be used: tc opens it at the listener's start. After a server
  restart nothing is `down`, `woken` or `working` until it has been seen
  listening again; the doc block says so.
- **A listener that mail woke is not down** (D24, D28). `tc wait` exits
  when mail lands and a session re-arms only after its turn, so a name
  seen listening within `DOWN_WINDOW_S`, not listening now, whose inbox
  got a message no older than `POLL_SECONDS` before it was last seen
  listening and no later than `POLL_SECONDS` after the first poll that
  found no listener, was woken. Mail that lands after the board has seen
  the listener gone is not a wake (D28): a killed listener stays `down`
  whatever mail reaches it later. The board keeps that first poll's time
  in memory beside `last_listening_at` and clears it on the next
  sighting. Where the board cannot list the inbox, it cannot tell, and
  the name reads `down` with the words `inbox unreadable`, and its node
  carries `inbox_unreadable: true`. It is:
  - `working` when there is evidence it is alive after the wake: the
    waking message has moved to `read/`, or its status file or a message
    it sent is newer than when it was last seen listening. Working fades
    to `idle` once `DOWN_WINDOW_S` has passed since it was last seen
    listening. It also shows `working` during the first
    `WOKEN_GRACE_S` = 120 after the wake, the time a session takes to
    start its turn.
  - `woken` (`woken · not read`) when `WOKEN_GRACE_S` has passed with no
    such evidence: the doorbell rang and nobody answered. A warning, with
    its own glyph and word, never color alone, and never `down`.
  - The legend says the cases it cannot see: a session that crashes
    after reading its mail looks `working` until the window ends; and
    with no board page open, the board cannot tell when a listener went,
    so it gives mail the benefit of the doubt. A planned follow-up, once
    SHARED merges, has `tc wait` write its exit reason into its lock file
    so the board reads it from disk (D28).
- `idle`: a card or inbox, no listener, not codex or ssh, not down,
  woken or working.
- `unread` is a count, or `null` when tc could not see into the inbox
  (a shared mailbox's inbox another user left unreadable); then
  `unread_problem` holds tc's reason, and the page says `unread unknown`
  in words, never a blank or a zero. `last_mail_age_s` is never below 0.
- **When more than one holds** (D15, D24), the first in this order wins:
  `writing`, `down`, `woken`, `working`, `listening`, `doorbell`,
  `remote`, `idle`. Writing
  comes first because nearly every session has a listener, and the
  moving activity is the point of the board. Writing lasts
  `WRITING_WINDOW_S`, so a node flashes `writing` and then shows its
  standing state again.
- `status`: from `status/<name>.md`, the first non-empty line after its
  `## <name> status, <time>` header, cut at `STATUS_PREVIEW_CHARS` = 80.
- `wires`: the last `WIRE_HISTORY` = 50 messages, read from file names
  (`NNNNNN-from-X.md` in `to-Y/` and `to-Y/read/`).
- `links`, all from what is on disk, never from a config that names a hub
  (D7):
  - `kind: mailbox`: one per pair that has ever exchanged mail, read from
    every message file name in every `to-*/` and `to-*/read/` (names
    only, never bodies). Undirected: `from` sorts before `to`. `sent`
    counts each side's messages; `last_age_s` is the newest one's age.
  - `kind: reports_to`: one per card with a `reports_to`, `from` the card,
    `to` the name it reports to. A hint, drawn as a thin line under the
    mailbox wires.
  - `kind: native`: two `claude` cards with the same `account`, drawn with
    the words `native · not observed`. Never when that account is the
    word `unknown` (D15): a link would claim a shared account no card
    knows.
- `look.js` gains two states, `doorbell` (glyph `◎`) and `remote`
  (glyph `⇄`), each with a word, and `patchBoard(board, feed)`, which adds,
  moves and removes nodes and wires by id and never rebuilds the board.

**Roles and levels** (D7). Any shape: one relay with many workers, a
relay whose worker is a relay for others, several orchestrators side by
side that mail each other, and cycles. `feed()` computes these, so they
are tested in Python; `look.js` only lays them out.

1. **Partners** of a node: the names it has exchanged at least one message
   with, either way, itself excluded.
2. **Parent.** Declared: the card's `reports_to`, when that name is a
   node. Inferred, when nothing is declared (D27): the partner holding at
   least `PARENT_MAJORITY` (two thirds) of the node's messages, sent and
   received, if that partner has `HUB_MIN_PARTNERS` (2) or more,
   **unless that partner's card declares this node as its own parent**
   (D15: inference never inverts a declared edge). Else none, so a node
   split evenly between two relays gets no guess. A majority, not "the
   only partner", because the board counts every message ever sent: one
   message between two siblings must not move both out of their relay's
   tree for good. An inferred edge that would close a cycle is dropped
   before roles and levels are worked out.
   A `reports_to` naming no node stays on the node, is drawn as `reports
   to <N> · not found`, and gives no parent. Each node carries the parent
   the walk used as `parent` (declared or inferred, or null), so
   `look.js` lays out trees without repeating this rule.
3. **Role.** `orchestrator` when one or more nodes have it as parent;
   `worker` when it has a parent and no children; `peer` otherwise. A
   relay for others under a relay is an `orchestrator` one level down.
4. **`role_source`**: `declared` when every parent edge that decided the
   role came from a card; `inferred` when any came from mail; `none` for
   a `peer`, which no edge decided (D27: `inferred` marks a guess, and a
   peer is not one).
5. **Level.** Nodes with no parent are roots, level 0. Walk breadth first
   down parent to child. Nodes still unreached sit on a cycle of
   `reports_to`: the one whose name sorts first becomes a root, and the
   walk runs again from it. Repeat until every node has a level. Each node
   gets exactly one level, and the walk ends on any cycle: O(n + e) for n
   nodes and e parent edges.
6. **Known limit**, said in `serve.py`'s doc block and the README: with no
   hints at all, a top relay whose only partner is a lower relay is drawn
   as that relay's `worker`, marked `inferred`. `--reports-to` fixes it,
   and JOIN.md writes it (task D2).

`look.js` gains `layoutLevels(feed)`, a pure function: each root's tree
side by side, roots in name order, levels top to bottom. Mailbox wires
between any two nodes (two orchestrators, cousins) draw whatever their
levels. Each node's title carries its role word (`a · orchestrator`,
`b · worker`, `x · peer`), with `· inferred` only when `role_source` is
`inferred`, never on a peer.
Role never rides on color.

Cost: O(k + m (log W + log K) + n + c^2) per poll for k cards, m message
file names scanned (every inbox and `read/` folder, names only, for
`links`; `wires` keeps the last `WIRE_HISTORY` = W in a heap, and each
name that stopped listening keeps its newest K candidate wakes), n names
and c cards on one account (the native links, c(c-1)/2 of them). m grows
with the mailbox's history: about 800 names after two weeks of heavy use
on Donald's machine, read once per poll. serve.py's module block names
each term.

## C6. The board server

- `python3 board/serve.py [--port 8780]` binds `127.0.0.1` only. The
  default is 8780 because 8765 was in use on Donald's machine (another local
  docs server) on 2026-10-14; the README says the port is a flag.
- A token from `secrets.token_urlsafe(24)`, made at start, printed once in
  the URL: `http://127.0.0.1:8780/live.html#token=<t>`. The fragment never
  reaches the server's log or another site's referrer.
- `GET /feed` needs header `X-TC-Token: <t>`, else 401 with no body.
- Requests whose `Host` is not `127.0.0.1:<port>` or `localhost:<port>` get
  421. This stops DNS rebinding.
- Static files: an allow list (`live.html`, `look.js`, `theme.css`,
  `demo.html`, `demo-script.json`, `compare.html`, and the six files in
  `fonts/`: two faces in two subsets each, as woff2, and their two
  licenses, D26), matched as exact strings; no path is joined from the
  request beyond them. Anything else 404. No folder listing. The page
  asks no host but 127.0.0.1 (D26).
- Any method but GET and HEAD: 405. Nothing on the board writes.
- `live.html` polls `/feed` every `POLL_MS` = 3000, keeps the newest answer
  only (a slow old answer never overwrites a newer one), and calls
  `patchBoard`. It has the look switch and `?gray=1` like the demo.
