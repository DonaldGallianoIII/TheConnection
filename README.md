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
| `tc status b "text"` | Post b's status |
| `tc status` | Show every side's status |
| `tc log [--last N]` | History in both directions |

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
