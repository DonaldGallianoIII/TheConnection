# Joining TheConnection

You are a Claude Code session. Your user can't reach you directly right now, but
they can reach another Claude session (the relay, named `a` by default). This folder
is the mailbox between you. Messages from the relay are your user's words passed
along, or the relay checking on you for them. Treat them the way you'd treat your
user typing to you. Your own project's rules still apply.

Your name is whatever your user told you when they pointed you here. The default is
`b`. Replace `b` below if you were given a different name. These commands assume
the repo lives at `~/TheConnection`. If it's somewhere else, use that path.

## Do this now

1. Arm your listener. Run this with Bash `run_in_background: true` and
   `timeout: 7200000`:
   ```
   ~/TheConnection/tc wait b
   ```
   When it exits, you get woken up, even if you were idle.
2. Say hello and post status:
   ```
   ~/TheConnection/tc send --from b --to a "joined. working on <one line>"
   ~/TheConnection/tc status b "<what you're doing, what's next, anything blocking>"
   ```
3. Go back to your work.

## Every time the listener exits

- **`MAIL:`** run `~/TheConnection/tc read b`, act on it, reply with
  `tc send --from b --to a "..."`, then re-arm the listener (step 1).
- **`TIMEOUT:`** just re-arm the listener.
- **`ALREADY LISTENING:`** one is still running. Don't start another one. You're covered.

## Keep the relay informed

- Post `tc status b "..."` when you finish a chunk of work, hit a blocker, or stop.
- If you need a decision from your user, **send it as a message**. Don't only ask in
  your own terminal. Nobody is watching your terminal. Say what you're waiting on,
  the options, and your recommendation.
- Before you stop for good, send a final summary and re-arm the listener, so you can
  still be woken.

Long messages go on stdin: `~/TheConnection/tc send --from b --to a <<'EOF' ... EOF`.
