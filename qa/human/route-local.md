# QA: the local route, two sessions on one machine

Model:  Claude Opus 5.5 (the DOCS lane agent), 2026-10-17
Status: unreviewed. Part A was run once by the DOCS lane agent while it
        checked the README, in a throwaway mailbox; part B needs two
        real Claude Code sessions and is the owner's.

What this checks: two sessions on one machine, run by one Linux user,
reach each other through one mailbox folder with nothing set up (the
README's quick start). A listener is proven by the pid `tc health`
names, mail wakes it, and every exit code a waking session acts on comes
out as the README's table says: 0 on mail, 2 on a timeout, 3 for a
second listener, 9 for a typo, never 2 for a typo.

Run everything from the repo root, in a throwaway mailbox, never the
checkout's own `mail/`, which live sessions use. Names here are made up.
In terminal 1:

```
export TC_ROOT=$(mktemp -d)
echo $TC_ROOT
```

Every other terminal starts with `export TC_ROOT=<that path>`. Real
`ssh` and real `codex` are not needed.

## Part A: by hand, in terminals

1. In terminal 1: `./tc join a --account work`, then `./tc join b
   --account work --reports-to a`.
   - They print `joined as a (other, account work, route local)` and
     `joined as b (other, account work, route local), reports to a`. In
     a shell inside a Claude Code session the kind reads `claude`
     instead of `other`.
<!-- Steps 2 and 3 reworded by the DOCS2 lane agent (Claude Opus 5.5), 2026-10-17: the pid check and a pasteable expected line. Status: unreviewed. -->
2. In terminal 2: `./tc wait b --timeout 300`. In terminal 1: `./tc
   health`. Its `listeners` line names `b (pid NNNN)`. Then, still in
   terminal 1, give that pid to `ps`:
   ```
   ps -o args= -p NNNN
   ```
   - `ps` prints one line, the command line of the process health named:
     `python3 ./tc wait b --timeout 300`, the wait you started in
     terminal 2.
   - Pass: health names b with a pid, and `ps` prints that line for it.
     Fail: `listeners  none running`, or `ps` prints nothing or some
     other command.
3. In terminal 1:
   ```
   ./tc wait b --timeout 5; echo $?
   ```
   - It prints these two lines, at once:
     ```
     ALREADY LISTENING: another `tc wait b` is running. Not starting a second.
     3
     ```
4. In terminal 1: `./tc send --from a --to b "hello b"`.
   - It prints `sent #1 to b: <TC_ROOT>/mail/to-b/000001-from-a.md`.
   - Within 5 s, terminal 2 prints `MAIL: 1 unread for b. Run: tc read b`
     and its prompt returns. There, `echo $?` prints `0`.
   - `cat $TC_ROOT/mail/to-b/.wait.exit` prints `mail <time>`.
   - Pass: the wait ends on its own within 5 s, with exit 0. Fail: it
     keeps running, or exits with anything else.
5. In terminal 1: `./tc peek b`, then `./tc read b`, then `./tc read b`
   again.
   - `peek` prints `1 unread for b`, then `# #1 from a to b, <time>`,
     `hello b` and `---`. `read` prints the same message without the
     count line. The second `read` prints `no unread mail for b`.
6. In terminal 2: `./tc wait b --timeout 3; echo $?`.
   - After 3 s: `TIMEOUT: no mail for b in 3s. Re-arm: tc wait b`, and
     `2`.
7. A typo never passes for a timeout (D12). In terminal 1: `./tc wait;
   echo $?`, then `./tc wiat b; echo $?`.
   - Each prints a `usage:` line and an `error:` line, and `9`. Never
     `2`.
8. In terminal 1: `./tc send --from a --to "bad name" hi; echo $?`.
   - `tc: bad name "bad name": letters, digits, dot, dash, underscore, 1
     to 64, not starting with a dash`, and `6`.
9. In terminal 1: `./tc send --from a --to b "" < /dev/null; echo $?`.
   - `tc send: empty message`, and `1`.
10. In terminal 1: `./tc send --from a --to nobody-yet "hi"; echo $?`.
    - `sent #2 to nobody-yet: ...`, then `new inbox: nobody has joined
      as nobody-yet`, and `0`. On a private mailbox, mail to a name
      nobody joined still lands. (The warning goes to stderr; piped to a
      file or `less`, it may come first.)
11. A long message on stdin. In terminal 1:
    ```
    ./tc send --from a --to b <<'EOF'
    Two lines
    on stdin.
    EOF
    ```
    Then `./tc read b`.
    - It prints both lines, whole.
12. A killed listener is not a wake (F1). In terminal 2: `./tc wait b
    --timeout 300`. In terminal 1: `./tc health`, note b's pid, then
    `kill -9 <that pid>`, then `./tc health` again.
    - The second health has no pid for b, and lists `stopped: b
      (listening, Ns ago)`: the wait was killed before it could write an
      exit, so its record still says `listening`.
    - Pass: no pid for b after the kill, and the word `listening` under
      `stopped`. Fail: a pid for b, or `stopped: b (mail, ...)`.
13. In terminal 1: `./tc log`.
    - Every message so far, unread and read, in number order.

## Part B: two real sessions (the owner)

This is the README's quick start, followed as written, with the
throwaway mailbox in front of every command. Two Claude Code sessions,
in two terminals or two SSH windows. Under two Claude accounts is the
headline case; under one account it works the same way.

14. In session 1 (the worker), type: `Your mailbox is TC_ROOT=<the
    path>. Read <repo>/JOIN.md and follow it. Your name is b, your
    relay is a.`
    - It runs `TC_ROOT=<the path> <repo>/tc join b ... --reports-to a`,
      starts `tc wait b` in the background with a 7200000 ms timeout,
      runs `tc health` and finds its own pid, sends a hello to `a`, and
      posts a status.
15. In session 2 (the relay), type the README's relay prompt, with
    `TC_ROOT=<the path>` in front of each tc command.
    - It runs `tc join a`, starts `tc wait a` in the background, and the
      wait exits at once with `MAIL:` for b's hello, which it reads and
      tells you about. Then it starts the wait again.
16. In terminal 1: `./tc health`.
    - `listeners` names `a (pid ...)` and `b (pid ...)`.
    - Pass: both have pids. Fail: either has none. Then that session
      has no listener, whatever it says; note what it ran.
17. Tell the relay: `ask b what it is working on`.
    - The relay sends to b. Within about 5 s session b wakes on its own
      (you typed nothing into it), reads, and replies. Then session a
      wakes and tells you the answer.
    - Pass: the answer reaches you through the relay, with nothing typed
      into b. Fail: b never wakes, or a never wakes on the reply.
18. In terminal 1: `./tc health` again.
    - Both names have pids again, b's a new one: each session re-armed
      after its turn.
    - Pass: two pids. Fail: a name with no pid, which means a session did
      not re-arm (JOIN.md's "Every time the listener exits").
19. Tell the relay: `tell b to stop`. When b says it has stopped, check
    that it re-armed before stopping: `./tc health` still names b with a
    pid.

## Afterward

20. Close both sessions, and run `unset TC_ROOT` in each terminal. The
    throwaway mailbox is under the system temp folder.
21. Record what you saw in `qa/results/route-local.md`, with made-up
    names only.
