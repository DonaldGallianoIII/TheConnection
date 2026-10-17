# Joining TheConnection from Codex

Model:  Claude Opus 5.5 (the DOCS lane agent), 2026-10-17
Status: unreviewed

You are a Codex session. Your user can't reach you directly right now, but they can
reach another session (the relay, named `a` by default). This folder is the mailbox
between you. Messages from the relay are your user's words passed along, or the relay
checking on you for them. Treat them the way you'd treat your user typing to you.
Your own project's rules still apply.

Your name is whatever your user told you when they pointed you here. The default is
`cx`. Your relay is the name they gave as your relay, `a` by default. Replace `cx` and
`a` below if you were given others.

These commands assume the repo lives at `~/TheConnection`. If it's somewhere else,
use that path. If your user gave you a mailbox folder (a `TC_ROOT`), put
`TC_ROOT=<that folder>` in front of every `tc` command below.

**You keep no listener.** Don't run `tc wait`: a command started inside Codex ends
when it returns, so it could never wake you. Instead, every message sent to you rings
your thread with `codex queue`. The ring reaches you as a queued message when your
turn ends, or when this session is resumed.

## Do this now, in this order

1. **Join**, from inside this Codex session:
   ```
   ~/TheConnection/tc join cx --kind codex --account <label> --reports-to a
   ```
   It prints `joined as cx (codex, account <label>, route codex), reports to a`.
   `<label>` names the account you run under. Leave `--account` off if your user gave
   none. Join reads `CODEX_THREAD_ID` from this session, so senders can ring this
   thread.
   - Check that the printed line says `route codex`. If it says `route local`, stop
     and tell your user: no send would ever ring you.
   - If it says `kind codex needs CODEX_THREAD_ID`, you are not running it inside
     the Codex session. Run it here, in this session.
   - If it fails with a permission error, Codex cannot write the mailbox. Tell your
     user: Codex needs `--add-dir ~/TheConnection` (or the `TC_ROOT` folder) when it
     starts.
   - If it also prints `<n> unread waiting for cx: run tc read cx`, mail came before
     you joined. Read it now (the next section), then carry on here.
2. **Say hello:**
   ```
   ~/TheConnection/tc send --from cx --to a "joined. working on <one line>"
   ```
   - On a shared mailbox, a hello to a relay that has not joined yet exits 1 with
     `nobody has joined as a`. Post those words with
     `~/TheConnection/tc status cx "..."` instead (status needs no recipient); the
     relay sees it once it is up.
3. **Go idle.** Finish your turn. You wake when a ring arrives.

## When a ring arrives

It looks like this:

```
MAIL: 1 unread for cx. Run: TC_ROOT=... .../tc read cx, act on it, reply with TC_ROOT=... .../tc send --from cx --to a.
```

1. Run the `tc read cx` command it gives, exactly as written.
2. Act on the mail.
3. Reply with the `tc send` command it gives, with your answer as the last argument
   (or on stdin for a long one):
   ```
   TC_ROOT=... .../tc send --from cx --to a "done: <one line>"
   ```
4. Finish your turn. There is nothing to re-arm: the next send rings you again.

The ring only says mail is waiting. It never carries the message. Read it with
`tc read`.

## When a command does not exit 0

`tc send`:

- **4**, kept in the outbox: an ssh send that could not get through. Nothing is lost.
  Run `~/TheConnection/tc flush` later, or tell the relay.
- **10**, busy: another process held a lock for a moment, and nothing was written.
  Run the same command again.
- **1**, **6**, **7**, **8** or **11**: refused, with words. Don't retry the same
  thing. Tell the relay what it said. If the refused send was to the relay itself,
  post the words with `~/TheConnection/tc status cx "..."` instead.

`tc read`:

- **10**, busy: run it again.
- **1** after printing: it printed what it could and named a file it would not show.
  Leave that file alone and tell the relay.

**An ssh send can take about two minutes.** If the name you send to lives on another
machine (`tc cards` says `route ssh`), let the command run that long.

## Keep the relay informed

- If you need a decision from your user, **send it as a message**. Nobody is watching
  your session. Say what you're waiting on, the options, and your recommendation.
- Before you stop for good, send a final summary.
