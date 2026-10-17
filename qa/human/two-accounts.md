# QA: two Claude accounts on one machine

Model:  Claude Opus 5.5 (the DOCS lane agent), 2026-10-17
Status: unreviewed. Not yet run by a person.

**For the owner.** This script needs two real Claude accounts and two
real Claude Code sessions. No `ssh` or `codex` runs.

What this checks: the planner's measurement behind the routing rule's
headline case (D1). Two Claude Code sessions under two different
accounts on this machine cannot see each other through Claude Code's
native messaging, and `tc send` across them wakes the listener. It also
records whether each account runs with its own `CLAUDE_CONFIG_DIR`,
since `tc join` takes the account label from that folder's name when
`--account` is not given, and otherwise writes `unknown` (C1).

Run every `./tc` from the repo root, in a throwaway mailbox. In
terminal 1:

```
export TC_ROOT=$(mktemp -d)
echo $TC_ROOT
```

Below, the two accounts are "account A" and "account B". Keep their real
names and email addresses out of the results.

## The two windows

1. Open two windows, terminals or SSH windows, the way you normally run
   two accounts. In each, before starting Claude Code: `echo
   "CLAUDE_CONFIG_DIR=$CLAUDE_CONFIG_DIR"`.
   - Note for each window whether it is set, and whether the two
     differ. Note only the last part of each path, and replace it with
     a made-up word in the results.
2. Start Claude Code in each window, account A in window 1 and account B
   in window 2. In each, run `/status` and check which account it is.
   - Pass: the two sessions report different accounts. Fail: the same
     account in both. Then this script tests nothing new; stop and fix
     the setup.

## Native messaging does not cross accounts

3. In each session, type: `List the sessions you can reach with your
   native messaging tool (ListAgents). Do not message anyone.`
   - Note what each lists.
   - Pass, for the routing rule: neither lists the other session. Fail:
     one lists the other. Then native messaging crosses accounts, the
     headline case may not need tc, and the architect must hear of it.
     Carry on with the steps below either way.

## tc crosses them

4. In window 2 (account B, the worker), type: `Your mailbox is
   TC_ROOT=<the path>. Read <repo>/JOIN.md and follow it. Your name is
   b, your relay is a. Leave --account off.`
   - It joins, starts its listener in the background, proves it with
     `tc health`, and sends a hello to `a`.
5. In window 1 (account A, the relay), type the README's relay prompt,
   with `TC_ROOT=<the path>` in front of each tc command.
   - It joins as `a`, starts its listener, wakes at once for b's hello,
     and tells you about it.
6. In terminal 1: `./tc cards`.
   - Note each card's `account`. With `CLAUDE_CONFIG_DIR` set in a
     window, that card's account is the last part of that folder's
     path. With it unset, `unknown`.
   - Both lines read `(claude, account ..., route local)`, and b's ends
     `, reports to a`.
7. In terminal 1: `./tc health`.
   - `listeners` names `a (pid ...)` and `b (pid ...)`.
   - Pass: both have pids. Fail: either has none.
8. Tell session A: `ask b which account it runs under and what it is
   working on`.
   - Session B wakes with nothing typed into it, reads, and replies.
     Session A wakes on the reply and tells you.
   - Pass: the answer comes back across the two accounts with nothing
     typed into B. Fail: B never wakes, or A never wakes on the reply.
9. In terminal 1: `./tc health` again.
   - Both have pids again: each re-armed after its turn.

## The board

10. In terminal 1: `python3 board/serve.py --port 8781`, and open the
    URL it prints.
    - Two boxes, `a · orchestrator` and `b · worker` (no `· inferred`:
      b's card declares its relay), each `● listening` once neither has
      sent anything for 10 s.
    - If the two cards name different accounts, or either names
      `unknown`, no box carries `native with ... · not observed`. If
      both name the same account, both do: the board then believes they
      share an account, and the results should say why the labels
      matched.
    - Stop the server with Ctrl+C.

## Afterward

11. Tell each session to stop. Run `unset TC_ROOT` in terminal 1. The
    throwaway mailbox is under the system temp folder.
12. Record what you saw in `qa/results/two-accounts.md`: for each window,
    whether `CLAUDE_CONFIG_DIR` was set and whether the two differed;
    what each session's native messaging listed; each card's account
    word (made up if it was a real label); and each pass or fail. No
    account names, emails or machine names.
