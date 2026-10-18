# TheConnection

A file mailbox that lets agent sessions message each other: Claude Code
sessions under several accounts, Codex sessions, and sessions on another
machine over ssh. The tool is `tc`, one Python file. One message is one
Markdown file, so you can read any inbox with `cat`.

<!-- Rewritten for the routing plan by Claude Opus 5.5 (the DOCS lane agent), 2026-10-17. Status: unreviewed. -->
<!-- The mailbox line in both tc health samples added by Claude Opus 5.5 (the R2 lane agent), 2026-10-17. Status: unreviewed. -->
<!-- Every fenced block below is run or listed by tests/test_readme.py; a new block goes in one of its tables (R39, Claude Opus 5.5, 2026-10-17). Status: unreviewed. -->

## Which way to use

| Your case | Use |
|---|---|
| Two Claude sessions under **one account** on one machine | Claude Code's own messaging (SendMessage). Not tc. |
| **Codex**, or any tool with no messaging of its own | tc, the `codex` route |
| **Several Claude accounts** on one machine, several SSH windows | tc, the `local` route. **The headline case.** |
| A separate Linux user per account on one machine | tc, a shared mailbox |
| Sessions on **another machine** | tc, the `ssh` route |
| Unsure | tc |

Why the native path is not the whole answer even for one account: a
session in a different permission mode holds a native message for its
user's approval and can let it expire, and the mailbox is a record anyone
can read on disk.

### Which route am I

```
Is the other session on another machine?
  yes: the ssh route. Set it up as in "ssh, outbound" below: a key, a
       gate line on the far machine, an ssh alias, then a card.
  no:  Is it Codex, or a tool with no messaging of its own?
         yes: the codex route. It runs tc join once; each send rings it.
         no:  Is it a Claude session under your own account?
                yes: Claude Code's native messaging. Not tc.
                no:  Does each account run as its own Linux user?
                       yes: a shared mailbox. Run tc init --shared once.
                       no:  the local route. Nothing to set up.
Unsure at any step: tc.
```

Any shape works. One relay with many workers, a relay whose worker is a
relay for others, two orchestrators side by side who mail each other: no
name is special, and any name may send to any name.

## How it works

Two ideas carry the whole tool.

1. **The folder is the transport.** `tc send` writes
   `mail/to-<name>/NNNNNN-from-<sender>.md`. `tc read` prints it and
   moves it to `read/`, which is the history.
2. **The lock is the proof of life.** `tc wait <name>` holds a lock on a
   file in that name's inbox for as long as it runs, and polls the inbox
   every 5 s. The kernel drops the lock the moment the process dies.
   `tc health` reads the kernel's lock table and names the pid holding
   each one, so "listening" is checked, never taken on anyone's word.

A Claude Code session wakes when a command it started in the background
exits. So a session runs `tc wait <name>` in the background, and when
mail lands the wait exits and the session wakes up and reads it.

**Analogy.** A pneumatic tube between offices. Where it breaks: nobody
hears the tube land. Each side keeps a listener running (`tc wait`), and
a session that forgets to re-arm it goes deaf until someone types into
it directly.

## Requirements

- Linux or WSL2. tc uses `flock`, `RLIMIT_AS` and `/proc`. macOS and
  plain Windows are out of scope.
- Python 3, standard library only. No installs.
- [Claude Code](https://claude.com/claude-code) for the waking side: when
  a background command exits, the session that started it wakes up.
  Codex sessions are woken another way (the codex route).
- For the ssh route: `ssh` and an ssh server on the far machine, whose
  login shell for your user is POSIX (sh, bash, dash or zsh).

## Install

```
git clone https://github.com/DonaldGallianoIII/TheConnection ~/TheConnection
chmod +x ~/TheConnection/tc
command -v tc
```

<!-- NAME lane (Claude Opus 5.5), 2026-10-17: link as tconn when the system has a tc. Status: unreviewed. -->
The last line asks whether your system already has a `tc`. Most Linux
systems do: the kernel's traffic control, at `/usr/sbin/tc`, which
answers `Object "health" is unknown, try "tc help".` Pick the name for
your link by what it printed.

- **It printed nothing.** Link ours as `tc`:
  ```
  mkdir -p ~/.local/bin && ln -s ~/TheConnection/tc ~/.local/bin/tc
  ```
- **It printed a path, such as `/usr/sbin/tc`.** Leave that one alone and
  link ours as `tconn`, then type `tconn` wherever this README says `tc`:
  ```
  mkdir -p ~/.local/bin && ln -s ~/TheConnection/tc ~/.local/bin/tconn
  ```

tc's hints follow the name you ran it by. Run as `tconn`, a wait that
finds mail prints `MAIL: 1 unread for a. Run: tconn read a`, and its
usage lines, `--help` and a mistyped command's error line say `tconn`.
Run by its path, it says `tc`. The words that open a refusal
(`tc send: empty message`) stay `tc` under any name.

On Ubuntu and Debian, `~/.local/bin` joins `PATH` at your next login
once it exists; elsewhere, add it yourself. Check with `command -v tc`
(or `command -v tconn`): it must print the `~/.local/bin` path. Below, a
bare `tc` means that link, under the name you gave it. Without a link,
write `~/TheConnection/tc` each time: the file in the repo is always
`tc`.

The mailbox lives next to the script: `mail/`, `status/`, `cards/` and,
once ssh mail has gone out, `outbox/` (all gitignored). To keep it
somewhere else, set `TC_ROOT` to a folder, and set it the same way for
every session that shares the mailbox. Every command below assumes the
repo is at `~/TheConnection`. Use your own path if it is somewhere else.

## Quick start: two sessions, one mailbox

The headline case: two Claude Code sessions on one machine, each in its
own SSH window, each under its own Claude account, both run by your one
Linux user. That is the `local` route, and there is nothing to set up.
Two sessions under one account work the same way, though Claude Code's
own messaging serves that case.

1. **In the session you want to reach** (the worker), type:
   ```
   read ~/TheConnection/JOIN.md and follow it. your name is b, your relay is a, your account is work.
   ```
   (`work` is a label for the Claude account; leave that part off if you
   have none in mind.)
   It joins as `b`, arms its listener, proves it, says hello, and goes back
   to work.
2. **In the session you talk to** (the relay), type:
   ```
   You are the relay for session b over ~/TheConnection/tc. Run
   `~/TheConnection/tc join a`, then `~/TheConnection/tc wait a` with
   run_in_background and timeout 7200000. When the wait exits 0, run
   `~/TheConnection/tc read a`, tell me what it says, and start the wait
   again. On exit 2 start it again. On exit 3 one is running: start none.
   On any other exit, stop and tell me. When I ask you to pass something
   on, run `~/TheConnection/tc send --from a --to b "..."`.
   ```
3. **Check both are listening**, from any terminal:
   ```
   $ ~/TheConnection/tc health
   mailbox    /home/you/TheConnection, TC_ROOT unset, so the folder tc is in
   ...
   listeners  a (pid 213593) · b (pid 213592)
   ...
   ```
   A name with a pid has a live listener. A name without one is not
   listening, whatever a session says.
4. Talk to the relay from wherever you are. It relays with `tc send` and
   wakes up when b writes back.

Names are letters, digits, dot, dash and underscore, 1 to 64 of them, not
starting with a dash. With many accounts, `<account>-<project>` reads well
(`work-api`, `home-football`). Run as many workers as you like, each with
its own inbox.

What the two sessions run, as you would see it in a terminal:

```
$ tc join b --account work --reports-to a
joined as b (claude, account work, route local), reports to a
$ tc wait b                      # in the background
$ tc send --from b --to a "joined. working on the parser"
sent #1 to a: .../mail/to-a/000001-from-b.md
```

a's wait prints `MAIL: 1 unread for a. Run: tc read a` and exits 0, which
wakes the relay. It reads:

```
$ tc read a
# #1 from b to a, ...

joined. working on the parser

---
```

## The mailbox is a record of the work

Every message is a numbered file. Its header says who sent it, to whom
and when. `tc read` moves it to `read/` and never deletes it, and writes
down when it was read, with the time zone, in `read/.read-times`. So `tc
log` rebuilds the whole run: who asked whom what, when it was sent, and
when the other side picked it up.

```
$ tc log
# #1 from b to a, ...
read ...

joined. working on the parser

---
```

That is the part of a project git never sees: the plan, the questions,
the approvals, the reviews and the answers, in order, each with its
number and its times. The commits show what the work produced. The
mailbox shows how it was run.

<!-- The report part and the export paragraph's tc report --scrub: the DASH lane agent (Claude Opus 5.5), 2026-10-17. Status: unreviewed. -->
**The report.** `tc report` draws that record as one HTML page that
opens in any browser, offline: who mails whom and how often, each
session's mail over time, how long mail waits before it is read, the
busy and quiet stretches, and how long a message that names an earlier
one (`ANSWER re #12`, `Re #12:`) took to come back. It reads each
message's file name, size and header line, the read times, each card's
`reports_to`, and from the first line of each message only its leading
tag (a word in capitals, such as `PLAN` or `PLAN-READY:`) and any `#N`
numbers in that line, never the rest of a message.

```
$ tc report ~/history.html --scrub
wrote .../history.html: ... messages, scrubbed. Mailbox /home/you/TheConnection, TC_ROOT unset, so the folder tc is in.
```

It needs the `board/` folder beside `tc`, as a clone has it. The line it
prints names the page and the mailbox it read. An existing file is
refused unless you add `--force`, and so is a page named inside the
mailbox (`mail/`, `status/`, `cards/` or `outbox/`). `--at TIME` sets
the page's "as of" (a time with its offset); by default it is the last
message's.

To show your own history to someone, never hand over `mail/` itself: it
holds your real names and words. Share a `tc report --scrub` page
instead. Its names are role labels (`orchestrator-1`, `worker-2`), its
times count from the first message (`T+3h10m`), its message numbers are
ranks, and any tag off a fixed list reads `other`. The tags it keeps are
ANSWER, FYI, QUESTION, PLAN, PLAN-READY, PLAN-CHECK, PLAN-EDIT,
PLAN-EDITED, PLAN-REVIEWED, CORRECTION, HEADS-UP, MERGE, REVIEW, STATUS,
BLOCKED, DONE and BREACH, and the page lists them. A page made without
`--scrub` holds your real session names and times, and every message's
leading tag as you wrote it; its top says so for the names and times.
Keep that one to yourself.

## Exit codes

Exit codes are how a waking session knows what happened. The full list,
with every case, is under "Exit codes" at the top of
`docs/planning/connection-routes/contracts.md`. This table matches it and
adds what a session does with each code.

| Code | Meaning | What the session does |
|---|---|---|
| 0 | ok. `wait`: mail landed. `watch`: heartbeat. | `wait`: read the mail, act, re-arm. `watch`: handle it, re-arm. |
| 1 | refused, with words on stderr (an empty message, a send to a name nobody joined on a shared mailbox, a link where tc opens a file, and more) | Stop. Do not re-arm. Tell the relay what it said. |
| 2 | `wait` timed out, or hit its keep-alive | Re-arm. |
| 3 | another `tc wait` or `tc watch` already holds this name's lock | Start none. One is running. |
| 4 | kept in the outbox: ssh could not reach the target, the target already has a queue, or another of your sends holds the send lock | Nothing is lost. Run `tc flush` later. |
| 5 | `watch` alert: load, memory, GPU, or a named listener down | Handle the alert, re-arm the watch. |
| 6 | bad name, a name that reports to itself, or a bad ssh target or remote path | Fix the name. A listener stops and tells the relay. |
| 7 | refused by the gate on the far machine | Stop. Nothing retries it. Tell the relay. |
| 8 | message over 1 MiB | Send something shorter. |
| 9 | usage error: an unknown command or flag, or a missing argument | Fix the command. A listener stops and tells the relay. |
| 10 | busy: another process held a lock past 3 s; nothing was written | Run it again. Never from `wait` or `watch`. |
| 11 | refused by the far side with a code tc does not know | Stop. Nothing retries it. Tell the relay. |

**The re-arm rule.** A session re-arms its listener only on 0 (after
reading the mail) or 2. On 3 it starts none. On any other code it stops
and tells its relay. A usage error is 9, not argparse's usual 2, so a
mistyped listener can never pass for a timeout and loop.

## Routes

`tc send` reads the recipient's address card (`cards/<name>.json`) and
delivers by the route on it. No card means `local`. `tc join` writes the
card for the session it runs in, `tc card` writes one for a name on
another machine, and `tc cards` lists them.

### local

The default. Both sessions use the same mailbox folder on one machine,
under one Linux user. A send writes the file; the recipient's `tc wait`
sees it within 5 s.

Mail to a name nobody has joined still lands, with a warning:

```
$ tc send --from a --to newname "first mail"
sent #2 to newname: .../mail/to-newname/000002-from-a.md
new inbox: nobody has joined as newname
```

The warning goes to stderr, so a pipe or a log may show it first.

### codex

A Codex session cannot keep a listener: a `tc wait` started inside Codex
dies when its command returns. So it has no listener. Instead it runs
`tc join` once, and every send to it rings its thread with `codex queue`.

1. **Start Codex with the mailbox writable.** Codex's sandbox lets it
   write only inside its workspace. `tc read` moves files and `tc send`
   writes them in the mailbox, so add the mailbox folder:
   ```
   codex --add-dir ~/TheConnection
   ```
   (Or the folder `TC_ROOT` names.) `--add-dir` takes effect under the
   workspace-write sandbox. Without it, the Codex session cannot read or
   answer its mail.
2. **In the Codex session**, type:
   ```
   read ~/TheConnection/JOIN-CODEX.md and follow it. your name is cx, your relay is a, your account is work.
   ```
   It runs `tc join cx --kind codex --account work --reports-to a`,
   which reads `CODEX_THREAD_ID` from its own environment and writes a
   card with route `codex`:
   ```
   joined as cx (codex, account work, route codex), reports to a
   ```
   Then it goes idle. Run outside Codex, where `CODEX_THREAD_ID` is not
   set, the same join writes nothing and exits 1: `tc join: kind codex
   needs CODEX_THREAD_ID, the thread the codex route rings, and it is not
   set. Run tc join inside the Codex session.` Without `--kind codex` it
   would quietly write a `route local` card instead, and no send would
   ever ring the session.
3. **Send to it** from any session:
   ```
   $ tc send --from a --to cx "please review the parser"
   sent #3 to cx: .../mail/to-cx/000003-from-a.md
   rang codex cx (queued; delivered when its turn ends or the session is resumed)
   ```
   The ring is `codex queue --thread <its thread> --message "MAIL: 1 unread
   for cx. Run: TC_ROOT=... .../tc read cx, act on it, reply with
   TC_ROOT=... .../tc send --from cx --to a."`. It never carries the
   message itself. The sender's machine needs `codex` on its `PATH`.

A second send while the first is still unread does not ring again: one
doorbell, one read. That holds for 5 minutes after your last ring to that
name. A send after that, with mail still unread, rings once more.

**`ring failed`.** If `codex queue` fails, the mail is still in the
inbox, and the send still exits 0:

```
ring failed for cx: <codex's first stderr line>; the mail is in its inbox; the next send to cx rings again
```

The next send rings again, whatever the inbox holds. A ring that times
out (30 s) holds off further rings for 5 minutes and says when it will
try again, so ten sends to a dead Codex do not each wait 30 s. Mail sent
before a Codex session joins is not lost: `tc join` prints `1 unread
waiting for cx: run tc read cx`, and the next send rings the new thread.

### ssh, outbound

For a session on another machine. Both machines run the same `tc`, a
copy of this repo. The far machine also needs `tc gate` set up for your
key (the next section). Below, `homebox` is the machine you send from,
`farbox` the far one, and `far-b` the name on it.

1. **On farbox**, the far session joins as usual: `tc join far-b`.
2. **On homebox, a key for tc alone**, with no passphrase, since tc
   never answers a prompt:
   ```
   ssh-keygen -t ed25519 -f ~/.ssh/tc_ed25519 -N '' -C homebox-a
   ```
   It writes `~/.ssh/tc_ed25519` and its public half,
   `~/.ssh/tc_ed25519.pub`.
3. **On farbox, the gate line for that key.** Add the line from "ssh,
   inbound" below to farbox's `~/.ssh/authorized_keys`, with `--as
   homebox-a` and the one line of `tc_ed25519.pub` at its end. Do this
   before step 5: without it farbox does not know the key.
4. **On homebox**, an ssh alias that picks that key. tc runs plain
   `ssh -T -o BatchMode=yes -o ConnectTimeout=10 -- <target>`, so the
   alias is how you choose a key. In `~/.ssh/config`:
   ```
   Host farbox-tc
       HostName <farbox's name or address>
       User you
       IdentityFile ~/.ssh/tc_ed25519
       IdentitiesOnly yes
   ```
   `User` is your login on farbox, the one whose home holds tc there.
5. **Meet the host once by hand.** tc runs ssh with `BatchMode=yes`, so
   it never answers a host-key prompt. Run `ssh -T farbox-tc` and accept
   the key. With the gate in place it prints `tc gate: refused` and exits
   7: there was no command, and the gate runs nothing else.
6. **On homebox, a card for the far name:**
   ```
   $ tc card far-b --ssh farbox-tc --remote-tc '~/TheConnection/tc'
   card written: far-b (other, account unknown, route ssh to farbox-tc)
   ```
   `--remote-tc` is tc's path on farbox, starting with `/` or `~/`
   (default `~/TheConnection/tc`). Quote a `~/` path so your own shell
   leaves it alone. `~` alone and `~user/...` are refused, exit 6.
7. **Send:**
   ```
   $ tc send --from homebox-a --to far-b "hello far"
   sent over ssh to farbox-tc: sent #1 to far-b: mail/to-far-b/000001-from-homebox-a.md
   ```
   On farbox, `tc read far-b` shows it `from homebox-a`, with `via ssh
   gate, key homebox-a` on its header line. The far side labels mail by
   the key, never by your `--from`.
8. **The way back, on farbox.** For replies, farbox needs a card that
   points at homebox, and the gate refuses `tc card`, so a person writes
   it on farbox: a key and an alias for homebox (as in steps 2 and 4),
   then `tc card
   homebox-a --ssh homebox-tc --remote-tc '~/TheConnection/tc'`. homebox
   then needs its own gate line for farbox's key (the next section).

**A send can take about two minutes.** One ssh run is allowed about 60 s
(connect, the far side's codex ring and its lock waits), and a send that
finds another of your sends to the same target still running waits for
it first. A session that sends over ssh gives its Bash call a timeout of
at least 180000 ms.

**The outbox.** Every ssh send is first written to your own branch of
the outbox, `outbox/<you>/to-<name>/` (`<you>` is your Linux login), then
sent, then moved to `sent/`. If the far side cannot be reached, the mail
stays there in order:

```
$ tc send --from homebox-a --to far-c "first"
could not reach farbox-tc (ssh: connect to host farbox port 22: Connection refused); kept in outbox: .../outbox/<you>/to-far-c/000002-from-homebox-a.md. Run: tc flush
$ tc send --from homebox-a --to far-c "second"
farbox-tc has 1 waiting in the outbox; queued behind them. Run: tc flush
```

Both exit 4. Nothing retries in the background. Run `tc flush` (or `tc
flush --to far-c`) when the far side is back. It sends your waiting mail
oldest first, one ssh run each, and stops at the first failure per
target, so the order holds. It exits 0 when nothing of yours is left
waiting and 4 when something is. A far side that answers busy (its exit
10) is kept the same way, with the words `farbox-tc was busy (exit 10:
...)`. `tc health` lists any outbox mail waiting longer than a day, as a
`stuck` line with the last try's words.

A retry never delivers twice. Each ssh message carries an origin id, and
the far gate answers one it already delivered with `already delivered
(origin ...)`, exit 0.

**Refused mail.** If the far tc refuses (exit 1, 6, 7 or 8, or a code tc
does not know, 11), the file moves to `refused/` with the far side's
words beside it in `<file>.stderr`, and nothing retries it:

```
tc gate: onward is not a local name; the gate does not forward
refused by farbox-tc (exit 7); filed in .../outbox/<you>/to-onward/refused/000004-from-homebox-a.md, and nothing retries it
```

Once you have fixed the cause, move the file from `refused/` back to
`outbox/<you>/to-<name>/` and run `tc flush`.

**The far login shell must be POSIX** (sh, bash, dash or zsh). ssh hands
tc's remote command line to that shell, and tc quotes it for POSIX. fish
or csh as the login shell breaks it.

### ssh, inbound, through `tc gate`

A far key that delivers mail to this machine runs `tc gate` and nothing
else. One key per sending name. On the receiving machine, add one line to
`~/.ssh/authorized_keys`:

```
command="TC_ROOT=/home/you/TheConnection /home/you/TheConnection/tc gate --as homebox-a",no-pty,no-port-forwarding,no-agent-forwarding,no-X11-forwarding ssh-ed25519 AAAA... homebox
```

- Put your own paths in both places, and the far key's public key at the
  end. `TC_ROOT` in the line pins the mailbox, whatever the shell sshd
  starts inherits.
- `--as` is the name every message through this key is from. The key
  cannot speak as any other name.
- On OpenSSH 7.2 or later, `restrict` in place of the four `no-` options
  turns those off and anything a later OpenSSH adds.
- `~/.ssh` stays 0700 and `authorized_keys` 0600, or sshd ignores the file.

**Never add a key for this without the gate.** A key with no `command=`
can run anything as you on this machine. With the gate it can do two
things: deliver a message as its `--as` name, through the normal router
(so a Codex recipient is rung), and ask `health --json`, which gives no
cards, no paths, no logins and no pids. Anything else prints `tc gate:
refused` and exits 7. The gate starts no shell, never forwards mail to a
third machine (`tc gate: onward is not a local name; the gate does not
forward`, exit 7), and runs no program but the codex ring.

### shared mailbox

For a separate Linux user per Claude account on one machine. Below, the
users are `ann` and `ben` and their group is `tcshare`.

1. **As a user with sudo:** make the group and put both users in it
   (`sudo groupadd tcshare`, `sudo usermod -aG tcshare ann`, the same for
   ben). Each logs out and back in, so `id -nG` lists `tcshare`.
2. **A folder both can reach, owned by the user who will run init**, not
   writable by the group: `sudo mkdir /srv/tc-shared`, `sudo chown
   ann:ann /srv/tc-shared`, `sudo chmod 0755 /srv/tc-shared`. Every
   folder above it must belong to root or ann, and must not be writable by
   its group or anyone unless it is sticky (as `/tmp`). Init refuses
   otherwise, and says which folder and why.
3. **Every member exports the same root**, in every shell and session:
   `export TC_ROOT=/srv/tc-shared`. A Claude session puts
   `TC_ROOT=/srv/tc-shared` in front of each tc command instead, since a
   Bash call does not keep an `export` from an earlier one.
<!-- Step 4 and the prompt in step 6 added by the DOCS2 lane agent (Claude Opus 5.5), 2026-10-17. Status: unreviewed. -->
4. **Each member needs a tc to run.** Either the same checkout, if the
   group can read it and every folder above it (on many systems a home
   folder is not readable by others), or the member's own clone at the
   same commit: `git -C ~/TheConnection rev-parse HEAD` prints the same
   for both. With `TC_ROOT` set, tc keeps nothing beside itself, so a
   member needs no write access to the checkout.
5. **As ann, once:**
   ```
   $ tc init --shared --group tcshare
   mailbox shared with group tcshare: 5 folders and 0 files in group tcshare
   ```
6. **Each member runs `tc join <name>` as their own Linux user before
   anything else.** Join makes the member's own inbox. Until a name has
   joined, a send to it is refused, `tc send: nobody has joined as ben on
   this shared mailbox`, exit 1, and `tc wait ben` is refused the same
   way. Only the owner of a name's card can listen for it. So start the
   relay first: a worker's hello to a relay that has not joined is
   refused. A worker that hits it posts the words with `tc status <its
   name> "..."`, which needs no recipient, and the relay reads them with
   `tc status` once it is up.

   A Claude session learns the root from its prompt. In a session that
   ben runs, with ann as the relay, type:
   ```
   your mailbox is TC_ROOT=/srv/tc-shared. read ~/TheConnection/JOIN.md and follow it. your name is ben, your relay is ann.
   ```
   JOIN.md has the session put `TC_ROOT=/srv/tc-shared` in front of
   every tc command and join before anything else. The session runs as
   ben, so its join is ben's. If ben runs ann's checkout (step 4), put
   that checkout's path in place of `~/TheConnection`. ann's relay
   prompt is the quick start's, with `TC_ROOT=/srv/tc-shared` in front of
   each tc command.
7. Then use it like a private mailbox. `tc health` ends with `mailbox
   shared with group tcshare`.

**No member can touch another member's mail.** Each inbox belongs to its
recipient, and messages, cards and status files are 0640: the group reads
them, only the writer writes. Members cannot delete, rename or rewrite
each other's unread mail, cards, status or queued ssh mail. A few files
every member must write stay group-writable (the message counter, the
inbox locks, the Codex ring marker). The worst a member can do through
them is make a send fail (exit 10, with words naming who holds the lock),
or a Codex ring come once more or once fewer; never read, lose or alter
mail. Every member can read every message: the group is trusted with
mail.

- The user who ran init is trusted like an administrator: the owner of a
  folder can remove anything in it.
- Only that user can change the group. A member's own `tc init --shared`
  on ann's mailbox exits 1, with words naming ann as the one who ran init,
  after fixing that member's own files if any need it.
- If a member makes another member's outbox branch first, tc refuses to
  use it and `tc health` shows a `squatted` line with the one command the
  init user runs to clear it (`mv -T <branch> <aside>`).
- A Codex ring across Linux users probably fails. The mail still lands,
  and the next send rings again.

## Commands

| Command | What it does |
|---|---|
| `tc send --from a --to b "text"` | Send a message. For long ones, leave the text off and put the body on stdin. |
| `tc read b` | Print b's unread messages and move them to `read/` |
| `tc peek b` | The same, leaving them unread |
| `tc wait b` | Wait until b has mail. Run it in the background. Default timeout 6600 s (`--timeout` changes it). |
| `tc wait b --keepalive` | The same, but times out just under the cache TTL (55 min) so the wake keeps the cache warm |
| `tc status b "text"` | Post b's status |
| `tc status` | Show every side's status |
| `tc log [--last N]` | History in both directions: every message, with when it was sent and when it was read |
| `tc report OUT.html [--scrub] [--force] [--at TIME]` | The history drawn as one HTML page; `--scrub` makes it safe to share |
| `tc health [--json]` | Machine, sessions, listeners, cards and mail at a glance |
| `tc watch a` | Heartbeat or alert that wakes a. Run it in the background. |
| `tc join b [--account L] [--kind K] [--reports-to N]` | Write the card for the session this runs in |
| `tc card b --ssh user@host [--remote-tc PATH]` | Write a card for a name on another machine |
| `tc cards` | Every card, one line each |
| `tc flush [--to b]` | Send your ssh mail waiting in the outbox, oldest first |
| `tc gate --as b` | Only ever a forced command in `authorized_keys` |
| `tc init --shared --group g` | Share this mailbox with a group of Linux users |

Every command takes `--help`. Exit codes are in the table above.

`tc join` works out the card from the session's environment: kind `codex`
when `CODEX_THREAD_ID` is set, else `claude` when `CLAUDECODE=1`, else
`other`. The account is `--account`, else the base name of
`CLAUDE_CONFIG_DIR`, else `unknown`. `--reports-to` names the relay that
pointed this session here: a hint for the board's levels, never a route.
A card never carries a secret.

```
$ tc cards
a (claude, account unknown, route local)
b (claude, account work, route local), reports to a
cx (codex, account work, route codex), reports to a
far-b (other, account unknown, route ssh to farbox-tc)
```

Here `a` is the quick start's relay, whose plain `tc join a` names no
account, in a window with no `CLAUDE_CONFIG_DIR`. b and cx were told
their account is `work`.

## Health and heartbeats

```
$ tc health
mailbox    /home/you/TheConnection, TC_ROOT unset, so the folder tc is in
machine    load 3.01 / 32 cores · mem free 85.6% · GPU 39C 3%
sessions   8 Claude Code · 0 Codex
listeners  b (pid 213592) · stopped: a (mail, 9s ago)
watchers   none running
cards      a (claude, account unknown, route local)
           b (claude, account work, route local), reports to a
mail       a: 0 unread, last mail 12s ago
           b: 0 unread, status 6s ago
mailbox private
```

`tc health` only reads. It shows load over core count, free memory, GPU
temperature and use (if `nvidia-smi` exists), how many Claude Code and
Codex sessions run, which listeners are live with their pids, every card,
and each inbox's unread count and last activity. `tc health --json` gives
the same for a script or the board.

Live listeners come from the kernel's lock table (`/proc/locks`), so
checking never gets in a listener's way. A name that stopped shows how
its last wait ended, from the wait's exit record
(`mail/to-<name>/.wait.exit`):

- `mail` or `timeout`: it left on purpose, and its session re-arms after
  its turn.
- `listening`: it was killed or crashed while waiting. Nothing is
  listening for that name.

The exit record is never proof of life. Only a held lock is.

<!-- Clearing a closed session's name: the DOCS2 lane agent (Claude Opus 5.5), 2026-10-17. Status: unreviewed. -->
**A session closed for good** kills its wait, so its name keeps reading
`stopped: <name> (listening, ...)` here and `✕ no listener` on the
board. To clear it, run `tc wait <name> --timeout 1` once, as that
name's own Linux user: it ends at its timeout and records `timeout`, so
health lists `stopped: <name> (timeout, ...)` and the board reads
`○ idle`. If mail is waiting for the name, it ends at once with `MAIL:`
and records `mail` instead, and the board warns `woken · not read`
until someone runs `tc read <name>`.

Lines that appear only when something is wrong: `stuck` (ssh mail waiting
in the outbox longer than a day), `squatted` (an outbox branch another
member made), `held` (on a shared mailbox, a lock held by someone other
than its name's owner, with who holds it).

`tc watch a` is a watchdog that wakes session `a`. Run it with Bash
`run_in_background: true`. It polls every 15 s and:

- exits 0 with a `HEARTBEAT` line (load and peak, free memory and low,
  GPU peak, session counts, who is listening) once per heartbeat. The
  default heartbeat is just under the cache TTL, so a watch also keeps the
  cache warm.
- exits 5 with an `ALERT` line early if load stays over 0.9 x cores for 3
  polls, free memory drops under 15%, a GPU passes 85C, or a listener named
  in `--names` stops without having left on purpose. `--names` follows the
  names that were listening when the watch started. A wait that left on
  mail or at its timeout says so in its exit record, and the watch lets it
  be:
  ```
  ALERT ...: LISTENER DOWN: b
    now: load 1.67 / 32, mem free 85.5%, GPU 40C 10%
  Re-arm after handling: tc watch a
  ```
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

## The live board

A read-only page that draws your sessions and the mail between them, and
follows it as mail moves.

1. Start it from the repo, with the same `TC_ROOT` as your sessions (or
   none, for the mailbox beside `tc`):
   ```
   $ python3 board/serve.py
   board: http://127.0.0.1:8780/live.html#token=<t>
   ```
   `<t>` is a long random token, made at each start and printed once. If
   8780 is taken, add `--port 8781`.
2. Open that exact URL in a browser on the same machine. The server
   listens on 127.0.0.1 only, and its feed needs the token. The page asks
   no other host.

<!-- From a laptop over SSH: the DOCS2 lane agent (Claude Opus 5.5), 2026-10-17. Status: unreviewed. -->
**From a laptop, over SSH.** The board listens only on the machine that
runs it. To see it from the laptop you SSH in from, forward its port as
you connect:

```
ssh -L 8780:127.0.0.1:8780 <host>
```

Then open the printed URL, as it is, in the laptop's browser. Keep the
same port on both ends: the server answers only a request addressed to
`127.0.0.1:<its port>` or `localhost:<its port>`, and refuses any other
with `421`, so a tunnel from another laptop port loads nothing. With
`--port 8781`, forward `-L 8781:127.0.0.1:8781`.

Each session is a box titled with its name and role: `a · orchestrator`,
`b · worker`, `x · peer`, with `· inferred` when the role was worked out
from mail rather than from a card's `--reports-to`. Its second line is
its state, always as a glyph and a word:

| Glyph and word | Means |
|---|---|
| `● listening` | a `tc wait` holds its lock now |
| `✎ writing` | it sent mail in the last 10 s |
| `◔ working` | mail woke it, and it shows life (read the mail, posted status, or sent), or the wake is under 2 minutes old |
| `△ woken · not read` | mail woke it 2 minutes ago or more, and nothing has read it. A warning. |
| `✕ no listener` | its listener went with no mail to explain it, or its exit record says it was killed. The box says how long ago it stopped. With `inbox unreadable`, the board could not list its inbox and cannot tell. |
| `◎ doorbell` | a Codex name: no listener, and that is right |
| `⇄ remote · not checked` | a name on another machine; the board never runs ssh |
| `○ idle` | none of the above |

The pill at the top right reads `live · 2 listening` while all is well.
It turns to a warning, in words (`2 listening · 1 no listener`, or
`1 woken · not read`), for any box woken and not read, and for a fresh
stop: a listener that went less than 10 minutes ago. Older stops it
counts apart as `⊘ 3 stopped earlier`, so a retired session never keeps
the alarm on. When the feed is late, the pill and a line over the
board say `stale · last answer N s ago`.

A wire carrying mail has moving dashes, an arrow toward the reader and a
label. A thin line is a `reports to` hint. Two Claude cards on the same
account each carry `native with <the other> · not observed`, since tc
cannot see that traffic. The account `unknown` is the one exception: two
cards that both say `unknown` share no account anyone knows, so they get
no badge. The legend in the footer says all of this in words. Nothing on
the board depends on color alone. To see it in grayscale, put `?gray=1`
before the `#`, so the token stays last:
`http://127.0.0.1:8780/live.html?gray=1#token=<t>`. Added after the
token, it becomes part of the token, and the feed refuses it. Use the
switch for the dark (`◐ Dark`) or light (`☀ Light`) look.

`http://127.0.0.1:8780/demo.html` shows every state with made-up
sessions and traffic.

## Layout

```
tc                                    the whole tool (python3, stdlib only)
JOIN.md                               what you point a new Claude session at
JOIN-CODEX.md                         what you point a new Codex session at
board/                                the live board: serve.py, live.html, look.js, theme.css, demo.html; report.py, tc report's page
mail/to-<name>/NNNNNN-from-X.md       unread messages
mail/to-<name>/read/                  read messages, kept as history
mail/to-<name>/.wait.lock             the listener's lock, its owner's alone (0600); .watch.lock beside it
mail/to-<name>/.wait.exit             the last wait's exit record: listening, mail or timeout, and a time
mail/.seq                             the message counter
mail/.box-<name>.lock                 the inbox lock
mail/.ring-pending-<name>             a Codex name's ring state
mail/.origins/                        on the receiving side, the origin ids each far key delivered
cards/<name>.json                     one address card per name
status/<name>.md                      each side's latest status
outbox/<user>/to-<name>/              ssh mail one Linux user queued, with sent/ and refused/
.shared                               the group of a shared mailbox
```

`mail/`, `status/`, `cards/`, `outbox/` and `.shared` are the mailbox, and gitignored.

## Resource safety

- **Measured cost:** a listener holds about 13 MB, uses 1 thread, and uses 0% CPU. Over
  200,000 polls (about 11 days of listening) its peak memory stayed at 13 MB.
- **Hard ceiling:** a listener caps its own memory at 256 MB. If a bug pushes it past
  that, Python raises MemoryError and only the listener dies.
- **One listener per name:** a second `tc wait b` exits right away with code 3. The
  lock lives in b's own inbox, so only b's own Linux user can hold it. At worst, a
  session that died leaves one orphan listener. That orphan exits at the 6600 s
  timeout, and its lock is freed the moment it exits.

## Limits

- **Nobody guarantees a wake-up.** If a session never armed its listener, or forgot to
  re-arm it, mail sits unread until someone types into that session.
- **Poll interval is 5 s.** That's plenty for chat. Don't use this for anything that
  needs speed.
- **Who can read the mail.** On a private mailbox, anything running as your Linux user
  can read and write it. On a shared one, every member can read every message, and no
  member can change another's. Off the machine, only a key behind `tc gate`.
- **Permission prompts can't be answered through the mailbox.** If a worker stops on a
  permission dialog, it can't send mail either. Pre-approve what it needs to run.
- **Off the machine only through ssh.** No network transport of its own. Mounting
  another machine's mailbox (sshfs, NFS) is not supported: `flock` is not reliable
  there, and the message counter depends on it.
- **The board only reads.** It cannot send, and it cannot see ssh names or native
  messaging: it says `remote · not checked` and `native · not observed`.
- **The board's guess with no hints.** A top relay whose only partner is a lower relay
  is drawn as that relay's worker, marked `inferred`. `tc join --reports-to` fixes it.
- **Not yet run for real:** the ssh route between two real machines, and a shared
  mailbox with a second real Linux user. Both are tested with stand-ins
  (`tests/test_ssh_route.py`, `tests/test_gate.py`, `tests/test_flush.py`,
  `tests/test_shared.py`); the walks a person runs are `qa/human/route-ssh.md` and
  `qa/human/route-shared.md`.

## License

MIT. See [LICENSE](LICENSE).
