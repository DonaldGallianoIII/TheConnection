# QA: the codex route, a Claude side and a Codex session

Model:  Claude Opus 5.5 (the DOCS lane agent), 2026-10-17
Status: unreviewed. Not yet run by a person.

**For the owner.** This script runs real `codex`. Agents never do (rule
5). The tests (`tests/test_codex_route.py`, `tests/test_router.py`)
prove the route against a fake `codex` that records its arguments; this
is the run against the real one.

What this checks: a Claude side sends to a Codex session and the Codex
session wakes, through `tc send` alone (phases.md P2's exit). Codex
keeps no listener (D3). It joins once, every send to it rings its thread
with `codex queue`, and the ring arrives as a queued message. A failed
ring never loses the mail, and the next send rings again (D14). Mail
sent before a Codex session joins still wakes it (D16). Codex needs the
mailbox added with `--add-dir` to write it (the README's codex section).

Run everything from the repo root, in a throwaway mailbox, never the
checkout's own `mail/`. Names here are made up. In terminal 1, which
plays the Claude side by hand as `a`:

```
export TC_ROOT=$(mktemp -d)
echo $TC_ROOT
```

## Setup

1. In terminal 1: `codex --version`.
   - Note the version for the results. D3 was observed on 0.160 to
     0.162.1.
2. In terminal 1: `./tc join a`.
   - `joined as a (other, account unknown, route local)`.
3. In terminal 2, in any project folder: `codex --add-dir <the
   TC_ROOT path>`.
   - Codex starts. `--add-dir` makes the mailbox writable to it under the
     workspace-write sandbox.

## The Codex session joins

4. In the Codex session, type: `Your mailbox is TC_ROOT=<the path>. Read
   <repo>/JOIN-CODEX.md and follow it. Your name is cx, your relay is
   a.`
   - It runs `TC_ROOT=<the path> <repo>/tc join cx ... --reports-to a`,
     which prints `joined as cx (codex, account ..., route codex),
     reports to a`; then it sends a hello to `a` and ends its turn. It
     starts no `tc wait`.
   - Pass: a `route codex` card, a hello, no wait. Fail: `kind codex
     needs CODEX_THREAD_ID` (the join did not run inside Codex), a
     permission error (the sandbox could not write the mailbox), or a
     `tc wait` started.
5. In terminal 1: `./tc cards`, then `./tc read a`.
   - `cards` lists `cx (codex, account ..., route codex), reports to a`.
   - `read` prints cx's hello.

## A send wakes it

6. In terminal 1: `./tc send --from a --to cx "reply with the word
   pineapple"`.
   - It prints `sent #<n> to cx: ...`, then `rang codex cx (queued;
     delivered when its turn ends or the session is resumed)`, and exits
     0.
7. Watch the Codex session. You type nothing into it.
   - A message arrives on its own: `MAIL: 1 unread for cx. Run:
     TC_ROOT=<the path> <repo>/tc read cx, act on it, reply with
     TC_ROOT=<the path> <repo>/tc send --from cx --to a.` It runs the
     read, then the send, then ends its turn.
   - Note how long the message took to arrive.
8. In terminal 1: `./tc read a`.
   - It prints cx's reply, with `pineapple` in it.
   - Pass: the reply arrives with nothing typed into the Codex session.
     Fail: no message reaches Codex, or Codex reads and never replies.
9. Two sends in a row. In terminal 1: `./tc send --from a --to cx
   "first of two"`, then at once `./tc send --from a --to cx "second of
   two"`.
   - The first prints `rang codex cx ...`; the second prints no `rang`
     line, since the first is still unread: one doorbell, one read.
   - Codex gets one message and reads both with one `tc read`.

## A failed ring loses nothing (D14)

10. In terminal 1, a name whose thread does not exist:
    `CODEX_THREAD_ID=not-a-live-thread ./tc join cz`.
    - `joined as cz (codex, account unknown, route codex)`.
11. In terminal 1: `./tc send --from a --to cz "hello"; echo $?`, then
    `head -1 $TC_ROOT/mail/.ring-pending-cz`.
    - The send prints `sent #<n> to cz: ...` and the warning `ring
      failed for cz: <codex's first stderr line>; the mail is in its
      inbox; the next send to cz rings again`, and `echo` prints `0`.
      The marker's first line is `failed`.
    - If it prints `rang codex cz ...` instead, `codex queue` accepted a
      thread that does not exist. Record that: it means a ring to a dead
      thread is lost without a word, which D14 assumed `codex queue`
      would report.
12. In terminal 1: `./tc send --from a --to cz "again"`.
    - It tries the ring again, and prints the same `ring failed` warning.
      `./tc peek cz` shows both messages.
    - Pass: both sends exit 0, each warns, and both messages wait in the
      inbox. Fail: a send exits non-zero, or the second send does not try
      the ring.

## Mail before the join still wakes it (D16)

13. In terminal 1: `./tc send --from a --to cx2 "sent before you joined"`.
    - `new inbox: nobody has joined as cx2`, then `sent #<n> to cx2:
      ...`, and no ring: there is no card yet.
14. In terminal 3: `codex --add-dir <the TC_ROOT path>`. In that session,
    the same prompt as step 4 with the name `cx2`.
    - Its join prints `joined as cx2 (codex, ...)`, then `1 unread waiting
      for cx2: run tc read cx2`, and it reads the early message before
      ending its turn.
15. In terminal 1: `./tc send --from a --to cx2 "and one after"`.
    - `rang codex cx2 ...`, and the cx2 session gets the queued message
      and reads it.

## Without --add-dir

16. Optional. Close the cx2 session. In terminal 3: `codex` with no
    `--add-dir`, and the same prompt as step 4 with the name `cx3`.
    - Record what its `tc join` prints. The README says Codex cannot
      write the mailbox without `--add-dir`; a permission error here
      confirms it. If the join works, record your Codex sandbox setting
      (`/status` in Codex shows it), since the README's claim then needs
      narrowing.

## Afterward

17. Quit the Codex sessions. Run `unset TC_ROOT` in terminal 1. The
    throwaway mailbox is under the system temp folder.
18. Record what you saw in `qa/results/route-codex.md`: the Codex
    version, how long each ring took to arrive, and each pass or fail,
    with made-up names only and no thread ids.
