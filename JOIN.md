# Joining TheConnection

<!-- Brought to the routing plan (tc join, the re-arm rule, the proven listener, the shared mailbox, ssh's timeout) by Claude Opus 5.5 (the DOCS lane agent), 2026-10-17. Status: unreviewed. -->

You are a Claude Code session. Your user can't reach you directly right now, but
they can reach another session (the relay, named `a` by default). This folder
is the mailbox between you. Messages from the relay are your user's words passed
along, or the relay checking on you for them. Treat them the way you'd treat your
user typing to you. Your own project's rules still apply.

Your name is whatever your user told you when they pointed you here. The default is
`b`. Your relay is the name they gave as your relay, `a` by default. Replace `b` and
`a` below if you were given others.

These commands assume the repo lives at `~/TheConnection`. If it's somewhere else,
use that path. If your user gave you a mailbox folder (a `TC_ROOT`), put
`TC_ROOT=<that folder>` in front of every `tc` command below, every time: a Bash call
does not keep an `export` from an earlier one. A shared mailbox always has one.
If your user linked tc under another name (often `tconn`, since most systems have a
`tc` already), type that name instead; tc's hints say the name you ran it by. <!-- NAME lane, Claude Opus 5.5, unreviewed -->

## Do this now, in this order

1. **Join.** This writes your address card, so others can see who you are and the
   board can draw you under your relay:
   ```
   ~/TheConnection/tc join b --account <label> --reports-to a
   ```
   It prints `joined as b (claude, account <label>, route local), reports to a`.
   `<label>` names the Claude account you run under (`work`, `home`). Leave
   `--account` off if your user gave none.
   - On a shared mailbox you must join before anything else, as your own Linux
     user. Until you do, mail to you is refused and your listener exits 1.
2. **Arm your listener.** Run this with Bash `run_in_background: true` and
   `timeout: 7200000`:
   ```
   ~/TheConnection/tc wait b
   ```
   When it exits, you get woken up, even if you were idle.
   If your user wants your prompt cache kept warm while you wait, use
   `~/TheConnection/tc wait b --keepalive` instead. It wakes you just before the
   cache expires (55 minutes for a 1-hour cache).
3. **Prove it.** Run `~/TheConnection/tc health`. The `listeners` line must name
   `b (pid NNNN)`. A pid means the kernel holds your lock: you are listening. No pid
   means you are not, whatever you started. Don't tell anyone you are listening until
   health names your pid.
4. **Say hello and post status:**
   ```
   ~/TheConnection/tc send --from b --to a "joined. working on <one line>"
   ~/TheConnection/tc status b "<what you're doing, what's next, anything blocking>"
   ```
   - On a shared mailbox, a hello to a relay that has not joined yet exits 1
     with `nobody has joined as a`. Put those words in your status instead
     (status needs no recipient), and go on: your listener is armed, and the
     relay sees your status once it is up.
5. Go back to your work.

## Every time the listener exits

Read its exit code and its first word.

- **Exit 0, `MAIL:`** run `~/TheConnection/tc read b`, act on it, reply with
  `~/TheConnection/tc send --from b --to a "..."`, then re-arm the listener (step 2).
- **Exit 2, `TIMEOUT:`** just re-arm the listener.
- **Exit 2, `KEEPALIVE:`** the wake itself refreshed your cache. Re-arm with
  `--keepalive` and stay quiet. One short line is plenty; don't post status for it.
- **Exit 3, `ALREADY LISTENING:`** one is still running. Don't start another one.
  You're covered.
- **Any other exit** (1, 6, 9, or anything else): don't re-arm. Something is wrong,
  and a re-armed listener would only hit it again. Send the relay the exact words it
  printed, and post them as your status too.

If it prints a line saying it moved a file aside, someone else had put a file where
your lock goes. Your listener still started. Tell the relay.

## When a command does not exit 0

`tc send`:

- **4**, kept in the outbox: an ssh send that could not get through. Nothing is lost.
  Run `~/TheConnection/tc flush` later, or tell the relay.
- **10**, busy: another process held a lock for a moment, and nothing was written.
  Run the same command again.
- **1**, **6**, **7**, **8** or **11**: refused, with words. On a shared mailbox, 1
  often means `nobody has joined as <name>`. Don't retry the same thing. Tell the
  relay what it said. If the refused send was to the relay itself, post the words
  with `~/TheConnection/tc status b "..."` instead.

`tc read`:

- **10**, busy: run it again.
- **1** after printing: it printed what it could and named a file it would not show.
  Leave that file alone and tell the relay.
- **0** with a `tc read:` line about read times: it moved a file aside where your read
  times go, or a read time was not recorded. Your mail was still read. Act on it as
  usual, don't stop, and send the relay the exact line. <!-- READTIME fix round 2, Claude Opus 5.5, unreviewed -->

**An ssh send can take about two minutes.** If the name you send to lives on another
machine (`tc cards` says `route ssh`), give that Bash call `timeout: 180000` or more,
or the call is cut off while tc is still trying.

## Keep the relay informed

- Post `~/TheConnection/tc status b "..."` when you finish a chunk of work, hit a
  blocker, or stop.
- If you need a decision from your user, **send it as a message**. Don't only ask in
  your own terminal. Nobody is watching your terminal. Say what you're waiting on,
  the options, and your recommendation.
- Before you stop for good, send a final summary and re-arm the listener, so you can
  still be woken.

Long messages go on stdin: `~/TheConnection/tc send --from b --to a <<'EOF' ... EOF`.
