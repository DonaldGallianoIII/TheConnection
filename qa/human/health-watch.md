# QA: tc health and tc watch

What this checks: `tc health` reports the machine, sessions, listeners and mail,
and `tc watch` wakes a session with a heartbeat or an alert.

Run every step in a throwaway mailbox, never the checkout's own `mail/`,
which live sessions use: a step here leaves an exit record saying
`listening` behind, and the live board would read `b` down for good.
Before step 1, run `export TC_ROOT=$(mktemp -d)` in the first terminal,
then `echo $TC_ROOT` and run `export TC_ROOT=<that path>` in a second
and a third terminal. Run everything from the repo root. Names here are
made up. (F1 fix round 1, Claude Opus 5.5, 2026-10-17. Status:
unreviewed.)

1. Run `./tc health`.
   - `machine` shows load over your core count, free memory as a percent, and your
     GPU temperature and use (or `GPU none` without an NVIDIA card).
   - `sessions` counts Claude Code and Codex sessions running right now.
2. In a second terminal, run `./tc wait b`. Back in the first, run `./tc health`.
   - `listeners` now shows `b (pid NNNN)`. The number matches `pgrep -f "tc wait b"`.
3. Stop the listener with Ctrl+C. Run `./tc health` again.
   - `b` moves to `stopped:`, as `b (listening, Ns ago)`: Ctrl+C stopped
     the wait before it wrote an exit, so its exit record still says
     listening (F1, C5). `b` has no pid: only a held lock says a listener
     runs.
4. Run `./tc health --json`. You get the same data as JSON, ready for a board.
5. Heartbeat: run `./tc watch a --heartbeat 10 --poll 2`.
   - After 10 seconds it prints one `HEARTBEAT` line (load and its peak, free memory
     and its low, GPU peak, session counts, who is listening) and exits 0.
6. Alert: run `./tc watch a --heartbeat 60 --poll 2 --mem-min-pct 101`.
   - Within a couple of seconds it prints `ALERT ... mem free ...% under 101%` and
     exits 5.
7. Listener down: start `./tc wait b` in the second terminal. In the first, run
   `./tc watch a --names b --heartbeat 60 --poll 2`. Stop the listener with Ctrl+C.
   - Within about 2 seconds the watch prints `ALERT ... LISTENER DOWN: b` and exits 5.
8. One watcher per name: with a `./tc watch a` running, start another `./tc watch a`.
   - The second prints `ALREADY WATCHING` and exits 3.
9. A wake is not a lost listener (F1, C5's wait exit record). Added by the
   F1 lane agent (Claude Opus 5.5), 2026-10-16. Status: unreviewed.
   All three terminals use the throwaway mailbox set at the top.
   In the second, start `./tc wait b`. In the first, run
   `./tc watch a --names b --heartbeat 20 --poll 2`. In the third, mail b:
   `./tc send --from c --to b "task"`.
   - Within 5 s the wait in the second terminal prints `MAIL:` and exits.
     `cat $TC_ROOT/mail/to-b/.wait.exit` reads `mail <time>`.
   - Pass: the watch prints nothing until its heartbeat, then one
     `HEARTBEAT` line, and exits 0. `./tc health` then lists
     `stopped: b (mail, Ns ago)`.
   - Fail: the watch prints `ALERT ... LISTENER DOWN: b` and exits 5.

   In the third terminal run `./tc read b`, so the `task` is read and the
   next wait has nothing waiting: a wait started over unread mail exits
   at once with `MAIL:` and holds no lock to kill. (F1 fix round 1, Claude
   Opus 5.5, 2026-10-17. Status: unreviewed.)

   Now start `./tc wait b` again in the second terminal, run the same
   watch in the first, and in the third stop the wait hard with
   `kill -9 <pid>`, the pid `./tc health` names for `b`.
   - Pass: within about 2 s the watch prints `ALERT ... LISTENER DOWN: b`
     once and exits 5, and `cat $TC_ROOT/mail/to-b/.wait.exit` reads
     `listening <time>`.
   - Fail: the watch runs on to its heartbeat, or the record reads `mail`
     or `timeout`.

10. Run `unset TC_ROOT` in each terminal. The throwaway mailbox is under
    the system temp folder.
