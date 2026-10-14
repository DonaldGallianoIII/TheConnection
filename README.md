# TheConnection

A file mailbox that lets Claude Code sessions on one machine message each other.

**Why it exists.** You can only talk to one Claude session at a time, and maybe only
one of them is reachable from where you are (your phone over SSH, say). The others
run in terminals you can't see. With TheConnection, you talk to one session (the
relay), and it passes your words to the others and tells you what they report back.
All sessions run as the same Linux user, so a shared folder is the whole transport.
No server, no network, no installs.

**Analogy.** Think of a pneumatic tube between offices. Where it breaks: nobody hears
the tube land. Each side has to keep a listener running (`tc wait`), and a session
that forgets to re-arm it goes deaf until someone types into it directly.

## Requirements

- Linux or WSL2 (it uses `flock` and `RLIMIT_AS`). macOS and plain Windows are untested.
- Python 3, standard library only.
- [Claude Code](https://claude.com/claude-code). The wake-up relies on its background
  Bash: when a background command exits, the session that started it is woken up.

## Install

```
git clone https://github.com/DonaldGallianoIII/TheConnection ~/TheConnection
chmod +x ~/TheConnection/tc
```

The mailbox lives next to the script (`mail/` and `status/`, both gitignored). To
keep it somewhere else, set `TC_ROOT`.

## Quick start

1. **In the session you want to reach** (the worker), type:
   ```
   read ~/TheConnection/JOIN.md and follow it. your name is b.
   ```
   It arms its listener, says hello, and goes back to work.
2. **In the session you talk to** (the relay), type:
   ```
   You are the relay for session b over ~/TheConnection/tc. Run `~/TheConnection/tc wait a`
   with run_in_background, and re-arm it every time it exits. When mail arrives, run
   `tc read a` and tell me what it says. When I ask you to pass something on, send it
   with `tc send --from a --to b "..."`.
   ```
3. Talk to the relay from wherever you are. It relays with `tc send --to b` and
   wakes up when b writes back.

Names are just strings. Run as many workers as you like (`b`, `backend`, `builder`), each
with its own inbox.

## Commands

| Command | What it does |
|---|---|
| `tc send --from a --to b "text"` | Send a message. For long ones, put the body on stdin. |
| `tc read b` | Print b's unread messages and mark them read |
| `tc peek b` | Same, without marking them read |
| `tc wait b` | Block until b has mail. Run it in the background. Exit 0 = mail, exit 2 = timeout (6600 s), exit 3 = already listening. |
| `tc wait b --keepalive` | Same, but times out just under the cache TTL (55 min) so the wake keeps the cache warm |
| `tc status b "text"` | Post b's status |
| `tc status` | Show every side's status |
| `tc log [--last N]` | History in both directions |
| `tc health [--json]` | Machine, sessions, listeners and mail at a glance |
| `tc watch a` | Heartbeat or alert that wakes a. Run it in the background. Exit 0 = heartbeat, exit 5 = alert, exit 3 = already watching. |

## Health and heartbeats

```
tc health            # machine, sessions, listeners, mail, one screen
tc health --json     # same thing for a board or a script
tc watch a           # run in the background: heartbeat or alert wakes session a
```

`tc health` shows load over core count, free memory, GPU temperature and use (if
`nvidia-smi` exists), how many Claude Code and Codex sessions are running, which
listeners are live with their PIDs, and each inbox's unread count and last activity.
It only reads. Live listeners come from the kernel's lock table (`/proc/locks`), so
checking never gets in a listener's way.

`tc watch a` is a watchdog that wakes session `a`. Run it with Bash
`run_in_background: true`. It polls every 15 s and:

- exits 0 with a `HEARTBEAT` line (load and peak, free memory and low, GPU peak,
  session counts, who is listening) once per heartbeat. The default heartbeat is just
  under the cache TTL, so a watch also keeps the cache warm (see "Keep the cache warm").
- exits 5 with an `ALERT` line early if load stays over 0.9 x cores for 3 polls, free
  memory drops under 15%, a GPU passes 85C, or a listener named in `--names` stops.
- exits 3 if another `tc watch a` is already running.

Either way, re-arm it after you handle the output. Thresholds are flags:
`--load-ratio`, `--mem-min-pct`, `--gpu-max-c`, `--heartbeat`, `--poll`.

## Keep the cache warm

Claude caches a session's context between requests. With a 1-hour cache, a session
that sits idle for more than an hour loses it, and its next turn pays to rebuild the
whole context. `tc wait b --keepalive` wakes the session at 55 minutes, which counts as
a request and resets the clock. On a `KEEPALIVE:` exit the session just re-arms.

```
tc wait b --keepalive    # listener that doubles as a keep-alive
tc watch a               # heartbeat default is the same 55 minutes
```

**Is it worth it?** Each wake reads the cached context, at about a tenth of normal
input price. Rebuilding an expired 1-hour cache costs about twice normal input. So
roughly 20 wakes cost the same as one rebuild: about 18 hours of idling. If the
session will be used again within a day, keep-alive is cheaper. On a subscription
plan the same trade comes out of usage limits instead of dollars.

**Where it breaks.** It only helps an idle session waiting on `tc`. A session busy in
a long tool call refreshes its own cache anyway. If your plan's cache TTL is 5 minutes,
set `TC_CACHE_TTL_SECONDS=300` and the wake comes at 275 s. At that rate a rebuild
costs about 12 wakes, so it only pays if the session is back within the hour.

| Setting | Default | What it does |
|---|---|---|
| `TC_CACHE_TTL_SECONDS` | 3600 | Your cache lifetime |
| `TC_KEEPALIVE_MARGIN_SECONDS` | 300 | How early to wake (capped at a twelfth of the TTL) |

## Board look kit

`board/` holds the look for a visual board of your sessions: a window frame, session
boxes, ports and bezier wires, styled after the node graph in Greener Pastures. It is
styling and drawing tools only. It reads no mailbox. Build your own board on top of it.

- `board/theme.css`: colors, fonts, window, canvas, node, port and wire styles.
- `board/look.js`: `createWindow`, `createCanvas`, `createNode`, `drawWire`,
  `setFooter`, `wirePath`. Plain ES module, no libraries, no `innerHTML`.
- `board/demo.html` + `board/demo-script.json`: fake sessions and traffic so you can
  see every state.

```
python3 -m http.server 8765 -d board
# open http://localhost:8765/demo.html
```

Every state has a glyph and a word (`● listening`, `✎ writing`, `○ idle`,
`✕ no listener`). A wire carrying a message gets moving dashes toward the reader,
an arrow and a label, so nothing depends on color alone.

## Layout

```
tc                                  the whole tool (python3, stdlib only)
JOIN.md                             what you point a new session at
board/                              look kit for a visual session board
mail/to-<name>/NNNNNN-from-X.md     unread messages
mail/to-<name>/read/                read messages, kept as history
status/<name>.md                    each side's latest status
```

One message is one markdown file, so you can read any inbox with `cat`.

## Resource safety

- **Measured cost:** a listener holds about 13 MB, uses 1 thread, and uses 0% CPU. Over
  200,000 polls (about 11 days of listening) its peak memory stayed at 13 MB.
- **Hard ceiling:** a listener caps its own memory at 256 MB. If a bug pushes it past
  that, Python raises MemoryError and only the listener dies.
- **One listener per name:** a second `tc wait b` exits right away with code 3. At
  worst, a session that died leaves one orphan listener. That orphan exits at the
  6600 s timeout, and its lock is freed the moment it exits.

## Limits

- **Nobody guarantees a wake-up.** If a session never armed its listener, or forgot to
  re-arm it, mail sits unread until someone types into that session.
- **Poll interval is 5 s.** That's plenty for chat. Don't use this for anything that
  needs speed.
- **No auth.** Anything running as your Linux user can read and write the mailbox.
- **Permission prompts can't be answered through the mailbox.** If a worker stops on a
  permission dialog, it can't send mail either. Pre-approve what it needs to run.
- **One machine only.** The transport is a local folder.

## License

MIT. See [LICENSE](LICENSE).
