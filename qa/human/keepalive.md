# QA: tc wait --keepalive

What this checks: a keep-alive listener wakes its session before the prompt cache
expires, and still wakes at once for real mail.

1. Short TTL so you don't wait an hour: run
   `TC_CACHE_TTL_SECONDS=12 ./tc wait b --keepalive`.
   - After 11 seconds it prints `KEEPALIVE: no mail for b in 11s. This wake refreshed
     the cache. Re-arm: tc wait b --keepalive` and exits 2.
2. Run `TC_CACHE_TTL_SECONDS=60 ./tc wait b --keepalive` and, in a second terminal,
   `./tc send --from a --to b "hi"`.
   - Within 5 seconds the first prints `MAIL: 1 unread for b` and exits 0.
3. In a real Claude Code session: point it at JOIN.md, ask it to use `--keepalive`,
   then leave it idle past an hour.
   - Its transcript shows a `KEEPALIVE` wake at about 55 minutes, a one-line reply,
     and a re-armed listener.
   - Its next real turn starts fast. Rebuilding a cold cache on a long context takes
     noticeably longer.
4. Run `./tc wait --help`. The `--keepalive` flag is listed with its meaning.
