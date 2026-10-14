# Connection routes: contracts

Model:  Claude Opus 5.5 (the TheConnection architect session)
Status: draft. Reviewed once by the CRC-Planner session (Claude Fable 5.1,
        2026-10-14, 24 findings, all folded in). Fixed once Donald
        approves; a lane that needs a change writes a pause and does not
        edit this file.
Date:   2026-10-14

Names below that exist in `tc` today were read from `tc` at commit
`1791cbf`: `ROOT`, `MAIL`, `STATUS`, `inbox()`, `unread()`, `next_seq()`,
`cmd_send()`, `cmd_health()`, `listeners()`, `health_snapshot()`, `main()`.
Everything else is new.

Exit codes in use today: 0 ok, 2 timeout or keepalive, 3 already
listening, 5 alert. This plan adds **4 kept in outbox**, **6 bad name**,
**7 refused by the gate**, **8 message too large**.

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
  `work-tms`, `home-football`. A suggestion in the README, not enforced.

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
  "joined_at": "2026-10-14T12:00:00-05:00"
}
```

| Field | Values | Set by |
|---|---|---|
| `kind` | `claude`, `codex`, `other` | `tc join`: `codex` when `CODEX_THREAD_ID` is set, else `claude` when `CLAUDECODE=1`, else `other`. `--kind` overrides. |
| `account` | a label, or `unknown` | `--account`; else the base name of `CLAUDE_CONFIG_DIR` if set; else `unknown`. Never empty. |
| `route` | `local`, `codex`, `ssh` | `codex` for kind codex, `ssh` for a card made with `tc card --ssh`, else `local` |
| `session_id`, `pid` | from `CLAUDE_CODE_SESSION_ID`, `CLAUDE_PID` | `tc join` in a Claude session; null otherwise |
| `thread_id` | from `CODEX_THREAD_ID` | `tc join` in a Codex session; required for route `codex` |
| `ssh` | `{"target": "user@host", "tc": "/path/to/tc"}` | `tc card <name> --ssh user@host [--remote-tc PATH]`; `tc` defaults to `~/TheConnection/tc` |

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
`tc` path starts with `/` or `~/` and has no whitespace. Otherwise `tc card`
refuses with words, exit 6, and writes nothing.

Commands:

- `tc join <name> [--account L] [--kind K]` writes the card for the session
  it runs in, prints `joined as <name> (<kind>, account <account>, route
  <route>)`. A name that already has a card is overwritten and `joined_at`
  reset (a restarted session rejoins). `--kind codex` with no
  `CODEX_THREAD_ID`: refused, exit 1, with the words why.
- `tc card <name> --ssh user@host [--remote-tc PATH] [--account L]
  [--force]` writes a card for a name that lives on another machine. If
  `mail/to-<name>/` holds unread mail here, refused with words naming the
  count (that mail would never be read once sends go remote), unless
  `--force`.
- `tc cards` prints every card, one line each, in words.
- **No card means route `local`.** Every mailbox that works today keeps
  working with no card.

## C2. The router

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
`exit`. A route named on a card that is not in `ROUTES` answers `route
<route> is not built yet`, exit 1, nothing written.

- `deliver_local`: today's behavior. Seq under flock, write `.tmp`, rename.
  If the inbox did not exist before, add the warning `new inbox: nobody has
  joined as <to>` (open item O1). `header_note`, when given, is appended to
  the message's header line (the gate uses it, C3).
- `deliver_codex`: count unread first, then `deliver_local`. If the count
  was 0, ring:
  `codex queue --thread <thread_id> --message "MAIL: <n> unread for <to>. Run: <tc path> read <to>, act on it, reply with <tc path> send --from <to> --to <sender>."`
  with stdin from `/dev/null` and a timeout of `CODEX_RING_SECONDS` (30).
  Exit 0 adds the word line `rang codex <to> (queued; delivered when its
  turn ends or the session is resumed)`. Any other exit or a timeout adds
  the warning `ring failed for <to>: <first stderr line>; the mail is in its
  inbox`. **The send still exits 0**: the mail landed. Two senders racing
  an empty inbox may both ring; accepted, and said in the doc block.

`tc read` and `tc peek` on a name with no inbox print `no unread mail for
<name>` and create nothing (open item O2).

## C3. The `ssh` route, the outbox, `tc flush`, `tc gate`

**Outbound** (`deliver_ssh`, added to `ROUTES` by the SSH lane):

```python
argv = ["ssh", "-T", "-o", "BatchMode=yes", "-o", f"ConnectTimeout={SSH_CONNECT_SECONDS}",
        "--", card["ssh"]["target"],
        shlex.join([card["ssh"]["tc"], "send", "--from", sender, "--to", to])]
subprocess.run(argv, input=body, text=True, capture_output=True,
               timeout=SSH_SEND_SECONDS)
```

- `SSH_CONNECT_SECONDS = 10`, `SSH_SEND_SECONDS = 30`,
  `SSH_CONNECT_FAILED = 255` (ssh's own exit for a connection failure).
- The body goes on stdin, never on the command line.
- **Queue order first.** If `outbox/` already holds mail for this target,
  the new message is queued behind it without trying: exit 4, words
  `<target> has <n> waiting in the outbox; queued behind them. Run: tc
  flush`. While a target has a queue, `tc flush` is its only sender.
- Exit 0: words `sent over ssh to <target>: <remote stdout>`, exit 0.
- Exit 255 or a timeout (the connection failed): write the message to
  `outbox/NNNNNN-from-<sender>-to-<to>.md` (same seq counter, same header
  as a message), words to stderr `could not reach <target> (<reason>); kept
  in outbox: <path>. Run: tc flush`, exit 4.
- **Any other non-zero is the far `tc`'s answer** (6 bad name, 7 refused,
  8 too large): print its stderr, exit with its code, queue nothing. A
  refusal retried forever helps nobody.

**`tc flush [--to <name>]`**: tries each outbox file in seq order; on
success moves it to `outbox/sent/`; on a connection failure for a target,
stops trying that target, so its mail stays in order; on a far refusal,
moves the file to `outbox/refused/` with the far stderr beside it. Prints
one line per file. Exit 0 when nothing is left to send, 4 when anything is.

**Inbound** (`tc gate`): for `~/.ssh/authorized_keys` on the receiving
machine, **one key per sending name**:

```
command="/home/you/TheConnection/tc gate --as homebox-b",no-pty,no-port-forwarding,no-agent-forwarding,no-X11-forwarding ssh-ed25519 AAAA... homebox
```

`tc gate --as <name>` reads `SSH_ORIGINAL_COMMAND`, splits it with
`shlex.split`, and allows exactly two shapes, ignoring only the first word
(the far side's path to its own tc):

- `<any> send --from <name> --to <name>`, both names valid under C0. The
  far side's `--from` is **ignored**: the message is delivered as from the
  `--as` name, through `deliver_local` with `header_note = "via ssh gate,
  key <as>"`. A key can never speak as the relay or any other local name.
  Size limit (C0) applies.
- `<any> health --json`. Runs `cmd_health`.

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
  group `g` (`os.getgroups()`); then sets group `g` and mode `2775` on
  `mail/`, `status/`, `cards/`, `outbox/` and every folder under them,
  sets group `g` and mode `0664` on every file already under them
  (`mail/.seq` and the lock files included), and writes `ROOT/.shared`
  holding the group name.
- While `.shared` exists, `tc` sets `os.umask(0o002)` before it writes
  anything, so every file and lock it makes is group-writable, and the
  setgid folders give them group `g`.
- `tc health` says `mailbox shared with group <g>` or `mailbox private`.

## C5. The board feed

`board/serve.py` loads `tc` as a module, never edits it, the way
`tests/test_keepalive.py` already does:

```python
loader = importlib.machinery.SourceFileLoader("tc", str(TC_PATH))
tc = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
loader.exec_module(tc)
```

`feed()` returns one JSON object built from `health_snapshot()`, the card
files (read directly from `cards/*.json` in C1's shape, **never** through
a `cards` key in `health`, which the CARDS lane adds later) and message
file names. It never opens a message body.

```json
{
  "at": "2026-10-14T12:00:00-05:00",
  "machine": { "load1": 0.25, "cores": 20, "mem_avail_pct": 78.9 },
  "nodes": [
    { "id": "a", "kind": "claude", "account": "work", "route": "local",
      "state": "listening", "listener_pid": 4242, "unread": 0,
      "last_mail_age_s": 30, "status": "reviewing parser" }
  ],
  "wires": [ { "from": "a", "to": "b", "seq": 781, "age_s": 4 } ],
  "links": [ { "from": "a", "to": "b", "kind": "mailbox" } ]
}
```

- `nodes`: every name with an inbox or a card. `state` is one of
  `listening` (a `tc wait` pid in `/proc/locks`), `writing` (sent within
  `WRITING_WINDOW_S` = 10), `doorbell` (route codex: no listener, and
  that is right), `remote` (route ssh: `remote · not checked`), `down` or
  `idle`.
- `down`: `serve.py` keeps `last_listening_at[name]` in memory for the
  life of the process. A name seen listening within `DOWN_WINDOW_S` = 600
  and not listening now is `down`. The lock file's time cannot be used: tc
  opens it at the listener's start. After a server restart nothing is
  `down` until it has been seen listening again; the doc block says so.
- `idle`: a card or inbox, no listener, not codex or ssh, not down.
- `status`: from `status/<name>.md`, the first non-empty line after its
  `## <name> status, <time>` header, cut at `STATUS_PREVIEW_CHARS` = 80.
- `wires`: the last `WIRE_HISTORY` = 50 messages, read from file names
  (`NNNNNN-from-X.md` in `to-Y/` and `to-Y/read/`).
- `links`: one per pair that has ever exchanged mail, `kind: mailbox`; and
  `kind: native` for two `claude` cards with the same `account`, drawn with
  the words `native · not observed`.
- `look.js` gains two states, `doorbell` (glyph `◎`) and `remote`
  (glyph `⇄`), each with a word, and `patchBoard(board, feed)`, which adds,
  moves and removes nodes and wires by id and never rebuilds the board.

Cost: O(n + m) for n names and m message files scanned, m capped by
`WIRE_HISTORY` per inbox listing.

## C6. The board server

- `python3 board/serve.py [--port 8780]` binds `127.0.0.1` only. The
  default is 8780 because 8765 was in use on Donald's machine (the TMS docs
  server) on 2026-10-14; the README says the port is a flag.
- A token from `secrets.token_urlsafe(24)`, made at start, printed once in
  the URL: `http://127.0.0.1:8780/live.html#token=<t>`. The fragment never
  reaches the server's log or another site's referrer.
- `GET /feed` needs header `X-TC-Token: <t>`, else 401 with no body.
- Requests whose `Host` is not `127.0.0.1:<port>` or `localhost:<port>` get
  421. This stops DNS rebinding.
- Static files: an allow list (`live.html`, `look.js`, `theme.css`,
  `demo.html`, `demo-script.json`, `compare.html`). Anything else 404. No
  folder listing.
- Any method but GET and HEAD: 405. Nothing on the board writes.
- `live.html` polls `/feed` every `POLL_MS` = 3000, keeps the newest answer
  only (a slow old answer never overwrites a newer one), and calls
  `patchBoard`. It has the look switch and `?gray=1` like the demo.
