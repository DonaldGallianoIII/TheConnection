# QA: tc health and tc watch

What this checks: `tc health` reports the machine, sessions, listeners and mail,
and `tc watch` wakes a session with a heartbeat or an alert.

1. Run `./tc health`.
   - `machine` shows load over your core count, free memory as a percent, and your
     GPU temperature and use (or `GPU none` without an NVIDIA card).
   - `sessions` counts Claude Code and Codex sessions running right now.
2. In a second terminal, run `./tc wait b`. Back in the first, run `./tc health`.
   - `listeners` now shows `b (pid NNNN)`. The number matches `pgrep -f "tc wait b"`.
3. Stop the listener with Ctrl+C. Run `./tc health` again.
   - `b` moves to `stopped:`.
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
