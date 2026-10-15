# poll-without-a-deadline-shows-stale-as-live

Model:  Claude Opus 5.5 (the known-bugs writer, for the architect session), 2026-10-15
Status: unreviewed

**What:** a page polls a status endpoint with `fetch` and no
per-request deadline. The polls come from a `setInterval` that fires
whether or not the last request has settled, and the page changes its
"live" indicator only when a request settles. When the server stops
answering without refusing (suspended, stuck behind a lock, waiting on a
slow child process), nothing settles. The indicator stays "live", the
last frame stays on screen as if current, and requests pile up.

**How it showed:** the BOARD lane, 2026-10-14. At `d250036`, the fetch at
`board/live.html:111` had no signal but the page-teardown one, the
`setInterval` at `:135` started a poll every 3 s whether or not the last
had settled, and the pill was written only on settle (`:113`, `:117`,
`:125`). Two triggers: serve.py stopped with Ctrl+Z (the kernel still
accepts connections into the backlog), or a feed slower than the 3 s poll
(a GPU query in the feed was allowed 5 s then). The board kept
`live · N listening` and every `● listening` box up with no current check
behind them.

**Why it's bad:** the page says a session is listening when nobody has
checked for minutes. A user trusts the board, sends, and nothing wakes.
It is the failure `listener-reported-live-without-the-lock` records,
reached through the page instead of a report.

**Prevention:** one request at a time: schedule the next poll after the
last one settles. Every request carries a deadline (an `AbortController`
on a named timer, or `AbortSignal.timeout`, combined with the teardown
signal), and a late or failed answer maps to "no answer" or "stale" in
words, never "live". Once a view is drawn, mark the whole view stale in
words plus a cue that does not rely on color, and keep that cue where the
reader is looking: a stale line at the top of a page scrolled down is not
seen.

**The check that catches it:** `tests/board-patch.test.mjs`, on fake
timers and a fake fetch through look.js's `createPoller`:

- "the poll loop asks one request at a time, drops a late one, and says
  so in words, never live";
- "before any answer the pill says no answer, and a 401 says the token
  was refused";
- "once a board is drawn, a late or refused answer says stale over the
  board, and the next good answer clears it";
- "stop clears every timer and aborts the request in flight; start polls
  again (pagehide, pageshow)".

`tests/board-browser-check.mjs` also fails when the stale line is out of
view on a page scrolled down while the feed fails. It needs Playwright
and skips without it.

**Detection:** three things in one file: (1) `setInterval(` whose
callback is an async function that calls `fetch(`; (2) a `fetch(` with no
`signal`, or with a signal aborted only on `pagehide`, `unload` or
teardown, and no `AbortSignal.timeout` or `setTimeout(... abort` anywhere
in the file; (3) the status text written only after `await fetch`, inside
`.then`, or in `catch`. All three together is a hit. Also: a stale cue in
a header that is neither sticky nor fixed, on a page that scrolls.

**Source:** the BOARD lane's full review, 2026-10-14 (audit folder
`2026-10-14-1811-full`; review audits stay out of the repo), MEDIUM-2.
Closed by `6eafef6`: `createPoller` starts the next poll `POLL_MS` after
the last one settles, aborts a request still out after
`FETCH_TIMEOUT_MS` (2.5 s), and says `no answer` or
`stale · last answer N s ago`. `0937669` put the stale line over the
board. Both reached the dev branch with the BOARD merge, `a2953cb`. The P4
phase review (audit folder `2026-10-14-2344-full`, LOW-18) found the stale
line out of view on a scrolled page; `602b62a` made it stick to the top
of the screen.

**Times hit:** 1.

**Tier when hit:** MEDIUM. One suspend or one slow query left the board
claiming listeners nobody checked, under a live pill. Nothing is lost:
mail waits in the inbox.

**Shared catalog:** the pile-up half has the shape of "Async reentrant
void call."
(`~/Conventions/code/known-bugs/javascript/async-and-lifecycle.md`), but
that entry's re-entry boolean does not fix this bug: a hung request
behind the boolean still leaves "live" up. The stale-as-live half has no
shared entry. In this repo it is the page-side form of
`listener-reported-live-without-the-lock`, and
`liveness-gap-by-design-read-as-down` is its mirror: a false alarm, not a
false all-clear.
