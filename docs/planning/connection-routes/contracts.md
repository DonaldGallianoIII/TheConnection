# Connection routes: contracts

Model:  Claude Opus 5.5 (the TheConnection architect session)
Status: draft, unreviewed. Fixed once Donald approves; a lane that needs a
        change writes a pause and does not edit this file.
Date:   2026-10-14

Names below that exist in `tc` today were read from `tc` at commit
`1791cbf`: `ROOT`, `MAIL`, `STATUS`, `inbox()`, `unread()`, `next_seq()`,
`cmd_send()`, `listeners()`, `health_snapshot()`, `main()`. Everything else
is new.

Exit codes in use today: 0 ok, 2 timeout or keepalive, 3 already listening,
5 alert. This plan adds **4 kept in outbox**, **6 bad name**, **7 refused
by the gate**.

---

## C0. Mailbox names

- A name matches `^[A-Za-z0-9._-]{1,64}$` and is not made only of dots.
- `tc` checks every name it is given (`--from`, `--to`, `read`, `peek`,
  `wait`, `status`, `join`, `card`) before it touches the disk, through one
  function `valid_name(name) -> bool`.
- A bad name: nothing is written, stderr says
  `tc: bad name "<name>": letters, digits, dot, dash, underscore, 1 to 64`,
  exit 6.
- Suggested form for many accounts: `<account>-<project>`, for example
  `work-tms`, `home-football`. A suggestion in the README, not enforced.

Why: names become folder names here and words in a remote command line
over SSH (C3). One rule closes both.

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

Commands:

- `tc join <name> [--account L] [--kind K]` writes the card for the session
  it runs in, prints `joined as <name> (<kind>, account <account>, route
  <route>)`. Run inside Codex with no `CODEX_THREAD_ID`, and `--kind codex`
  asked: refused, exit 1, with the words why.
- `tc card <name> --ssh user@host [--remote-tc PATH] [--account L]` writes
  a card for a name that lives on another machine. It joins nothing locally.
- `tc cards` prints every card, one line each, in words.
- **No card means route `local`.** Every mailbox that works today keeps
  working with no card.

## C2. The router

`cmd_send()` keeps its arguments and its output for route `local`. After
checking names (C0) it reads the recipient's card and calls one function
from a table:

```python
ROUTES = {"local": deliver_local, "codex": deliver_codex, "ssh": deliver_ssh}
# Each: deliver_<route>(card_or_None, sender, to, body) -> Delivery
Delivery = collections.namedtuple("Delivery", "exit words")
```

`send` prints `words` (stdout on exit 0, stderr otherwise) and exits with
`exit`.

- `deliver_local`: today's behavior. Seq under flock, write `.tmp`, rename.
  If the inbox did not exist before, also print to stderr
  `new inbox: nobody has joined as <to>` (open item O1).
- `deliver_codex`: count unread first, then `deliver_local`. If the count
  was 0, ring:
  `codex queue --thread <thread_id> --message "MAIL: <n> unread for <to>. Run: <tc path> read <to>, act on it, reply with <tc path> send --from <to> --to <sender>."`
  with stdin from `/dev/null` and a timeout of `CODEX_RING_SECONDS` (30).
  Exit 0 prints `rang codex <to> (queued; delivered when its turn ends or
  the session is resumed)`. Any other exit or a timeout prints
  `ring failed for <to>: <first stderr line>; the mail is in its inbox`.
  **The send still exits 0**: the mail landed. Two senders racing an empty
  inbox may both ring; accepted, and said in the doc block.
- `deliver_ssh`: C3.

`tc read` and `tc peek` on a name with no inbox print `no unread mail for
<name>` and create nothing (open item O2).

## C3. The `ssh` route, the outbox, `tc flush`, `tc gate`

**Outbound** (`deliver_ssh`):

```python
argv = ["ssh", "-o", "BatchMode=yes", "-o", f"ConnectTimeout={SSH_CONNECT_SECONDS}",
        card["ssh"]["target"],
        shlex.join([card["ssh"]["tc"], "send", "--from", sender, "--to", to])]
subprocess.run(argv, input=body, text=True, capture_output=True,
               timeout=SSH_SEND_SECONDS)
```

- `SSH_CONNECT_SECONDS = 10`, `SSH_SEND_SECONDS = 30`.
- The body goes on stdin, never on the command line.
- Exit 0: print `sent over ssh to <target>: <remote stdout>`, exit 0.
- Anything else: write the message to
  `outbox/NNNNNN-from-<sender>-to-<to>.md` (same seq counter, same header
  as a message), print to stderr
  `could not reach <target> (<reason>); kept in outbox: <path>. Run: tc flush`,
  exit 4.

**`tc flush [--to <name>]`**: tries each outbox file in seq order; on
success moves it to `outbox/sent/`; on the first failure for a target,
stops trying that target, so its mail stays in order. Prints one line per
file. Exit 0 when the outbox is empty after, 4 when anything is left.

**Inbound** (`tc gate`): for `~/.ssh/authorized_keys` on the receiving
machine:

```
command="/home/you/TheConnection/tc gate",no-pty,no-port-forwarding,no-agent-forwarding,no-X11-forwarding ssh-ed25519 AAAA... sender-machine
```

`tc gate` reads `SSH_ORIGINAL_COMMAND`, splits it with `shlex.split`, and
allows exactly two shapes, ignoring only the first word (the far side's
path to its own tc):

- `<any> send --from <name> --to <name>`, both names valid under C0. Runs
  `cmd_send` in this process with stdin as the body.
- `<any> health --json`. Runs `cmd_health`.

Anything else: stderr `tc gate: refused`, exit 7, nothing written. The gate
never starts a shell and never runs another program.

## C4. The shared mailbox

For a separate Linux user per account on one machine.

- `tc init --shared --group <g>`: refuses unless the running user is in
  group `g` (`os.getgroups()`); then sets group `g` and mode `2775` on
  `mail/`, `status/`, `cards/`, `outbox/` and every folder under them, and
  writes `ROOT/.shared` holding the group name.
- While `.shared` exists, `tc` sets `os.umask(0o002)` before it writes
  anything, so every file and lock it makes is group-writable, and the
  setgid folders give them group `g`.
- `tc health` says `mailbox shared with group <g>` or `mailbox private`.

## C5. The board feed

`board/serve.py` loads `tc` as a module, never edits it:

```python
spec = importlib.util.spec_from_loader("tc", importlib.machinery.SourceFileLoader("tc", str(TC_PATH)))
```

`feed()` returns one JSON object built from `health_snapshot()`, the cards
(C1) and message file names. It never opens a message body.

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
  that is right), `remote` (route ssh: `remote · not checked`), `idle`
  (a card or inbox, no listener, not codex or ssh) or `down` (had a
  listener in the last `DOWN_WINDOW_S` = 600 and lost it).
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

- `python3 board/serve.py [--port 8765]` binds `127.0.0.1` only.
- A token from `secrets.token_urlsafe(24)`, made at start, printed once in
  the URL: `http://127.0.0.1:8765/live.html#token=<t>`. The fragment never
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
