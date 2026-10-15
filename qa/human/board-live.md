# QA: the live board

Model:  Claude Opus 5.5 (the BOARD lane agent), 2026-10-14; fix rounds by
        Claude Opus 5.5 (the BOARD fixer); the P4 phase fix (D24's states,
        long names, the fonts, the stale line) by Claude Opus 5.5 (the P4
        phase fixer), 2026-10-15; its round 2 (D28's late mail, D27's
        peers, an unreadable inbox, a damaged token, the jump under the
        stale line) by Claude Opus 5.5 (the P4 phase fixer), 2026-10-15
Status: unreviewed. Written, not yet run by a person.

What this checks: `board/serve.py` serves the live board on 127.0.0.1 only,
refuses without its token, and `board/live.html` draws a real mailbox and
follows it as mail moves. Every state, port and wire reads in grayscale.
The board fills the screen and the page scrolls, no wire passes through a
box, no label sits on a box or another label, the legend is in the
footer, each tree has a heading and the roots are listed at the top, and
a phone draws an outline instead of the graph. A native pair says so in
words on both boxes, a parent's mail runs beside its tree line (never on
it), and a stale feed says so over the board.

Run everything from the repo root, in a throwaway mailbox, never the live one.
Names below are made up.

## First: the browser check

A script opens the board in a headless browser at a desktop size and a
phone size and measures what the steps below ask you to look at. It is
not part of `node --test`. It needs Playwright: set NODE_PATH to a
Playwright install's node_modules.

```
NODE_PATH=<a Playwright install>/node_modules node tests/board-browser-check.mjs
```

- It builds its own throwaway mailbox with 16 names (two orchestrator
  trees and two peers, and a root over a worker whose names are 64
  characters long). It writes the cards with `tc join` when this
  tree's `tc` has it, else by hand, and prints which. `p1` and `p2` share
  an account and mail each other; `e2` and `e3` share another and do not.
  It starts six listeners and proves them with `tc health`, starts
  `serve.py` on a free port under a time limit of its own, then makes `d`
  and `e2` down workers: the feed sees their listeners, the listeners are
  stopped by their pids, and the feed says down. `e2`'s wire shares a
  stretch with its siblings' wires, so it tests that a dotted wire stays
  dotted beside others. It prints each step. Every line it prints
  is masked, so it never prints the token, not even in an error.
- At 1280 x 900 and at 390 x 844 it prints one line per check, each
  `PASS` or `FAIL`: the view (graph on the desktop, outline on the phone),
  no console errors, no sideways scroll, no text under 11 px, all 16 names
  on screen, no box over another, the window at least the viewport's
  height, no label on a label, a box or a heading, no wire through a box,
  the legend below the last session, the roots listed with a working link
  to `z` (z's heading starts out of view and the click brings it in), no
  outline row, group heading or root button past the window's edge, the
  long names' role words on screen at the phone size, no request to any
  host but 127.0.0.1, the board's two faces loaded from `serve.py`
  (D26), nothing cut off in the pill or the footer, each of `p1`, `p2`,
  `e2` and `e3` saying `native with <the other> · not observed` in full,
  and on the desktop the wires of `d` and `e2` dotted, with only the
  canvas showing in their gaps (read pixel by pixel).
- It saves four screenshots (each size in color and in grayscale) to a
  temp folder and prints their paths. Look at them. None goes in the repo.
- It stops the server and the listeners by their own pids, prints those
  pids, and ends with `result: PASS` (exit 0) or `result: FAIL (n)`
  (exit 1). It stops them on Ctrl+C or a SIGTERM too, and if it is killed
  outright, `serve.py` still ends 120 s after it started.
- Without Playwright it prints `skipped: playwright not found` and exits 0.
- `node tests/board-browser-check.mjs --self-test` needs no Playwright: it
  runs the check against a stand-in browser whose page load fails, whose
  close throws, and which hangs until SIGTERM, then SIGINT, then SIGKILL,
  and ends `self-test: PASS` only if no run printed a token or left
  `serve.py` or a listener alive.

## Set up

1. In terminal 1, make a throwaway mailbox and keep its path:
   ```
   export TC_ROOT=$(mktemp -d)
   echo $TC_ROOT
   ```
   Every other terminal below starts with `export TC_ROOT=<that path>`.
2. In terminal 2, start a listener for `b`: `./tc wait b`.
   In terminal 3, start one for `c`: `./tc wait c`.
3. In terminal 1, check both are proven: `./tc health`.
   - `listeners` names `b` and `c`, each with a pid.

## Start the board

4. In terminal 1: `python3 board/serve.py`
   - It prints one line: `board: http://127.0.0.1:8780/live.html#token=<t>`,
     with a long random token in place of `<t>`. It prints nothing else
     while it runs.
   - If 8780 is taken, add `--port 8781` and use that port below.
5. Open the printed URL in a browser.
   - A dark window titled `connection.board · TheConnection :: live`. It
     reaches the bottom of the browser window however tall that is.
   - The pill on the right reads `live · 2 listening`.
   - Under the title, the list of roots: `2 peers: b, c`.
   - Two boxes, `b · peer · inferred` and `c · peer · inferred`, each with
     `● listening` on its second line, each under a heading with its own
     title. Each box has a hollow ring on the middle of its top edge (in)
     and a filled dot on the middle of its bottom edge (out).
   - The legend is the first line of the footer, under the board, never
     over a box.

## Mail moves on the board

A name gets a box once it has an inbox (it was sent mail, or ran
`tc wait`) or a card. A listener wakes and exits when mail reaches it, the
same as in a real session, so each send to `b` or `c` below is followed by
re-arming that listener. A first send to a name with no inbox and no
card also prints `new inbox: nobody has joined as <name>` on stderr; that
is expected here. Send nothing to `cx` or `far` after step 11:
their cards route mail to `codex` and `ssh`, which this script never runs.

6. In terminal 4: `./tc send --from b --to a "ready"`
   - Within 3 s a box `a · peer · inferred` appears, reading
     `○ idle · 1 unread` (`a` has an inbox now, and no listener).
   - The wire between `a` and `b` turns dashed and moves, with the words
     `b → a · #1` beside it (never on it) and an arrow at `a`, the reader.
     `a` and `b` are side by side, so the wire runs straight across between
     their sides.
   - `b` reads `✎ writing` with a thicker border for about 10 s, then
     `● listening` again: a send shows first, listener or not (D15). The
     pill still reads `live · 2 listening` the whole time.
7. In terminal 4: `./tc send --from a --to b "first task"`
   - Within 3 s the same wire flows the other way, `a → b · #2`, with the
     arrow at `b`.
   - `a` reads `✎ writing` with a thicker border, for about 10 s.
   - `b`'s listener in terminal 2 exits with `MAIL:`, the way a session's
     listener ends when mail wakes it. If step 6 was less than 10 s ago,
     `b` still reads `✎ writing` from its own send; that is expected, not a
     failure. After that, `b` reads `◔ working`: mail woke it, and it may be
     on its turn (D24). It never reads `✕ no listener`, its wire stays a
     mail wire (dashed while the message is new, then solid), never dotted,
     and the pill reads `live · 1 listening`: only `c` holds a listener now.
   - Read nothing for 2 minutes. `b` then reads `△ woken · not read` with
     a heavier solid border: mail woke it and nothing has read it. The pill
     reads `1 listening · 1 woken · not read`, the same words as the box.
     The wire is still not dotted.
8. In terminal 2: `./tc read b`.
   - Within 3 s `b` reads `◔ working` again: the read is a sign of life.
     The pill goes back to `live · 1 listening`.
   Then, in terminal 2, `./tc wait b` again.
   - Within 3 s `b` reads `● listening` and the pill reads
     `live · 2 listening`.
9. Make `a` a relay. In terminal 4: `./tc send --from a --to c "second task"`,
   then in terminal 3 `./tc read c` and `./tc wait c` again, then in
   terminal 4 `./tc send --from c --to a "on it"`.
   - `a` sits on the top row and reads `a · orchestrator · inferred`, under
     the heading `a · orchestrator · inferred · 3 sessions`.
   - `b` and `c` sit one row below it and read `worker · inferred`.
   - A thin line runs from `a`'s out dot down to each child's in ring, with
     no words on it. Hover it: `b under a · inferred from mail`.
   - Each message flows beside that thin line within 3 s, a little to one
     side of it and never on it, dashed, with the arrow at the reader.
     `c → a` flows beside `c`'s line with the arrow at `a`'s end.
10. Wait 10 s with no mail.
    - The dashes and the words leave the wires. The quiet lines stay, with
      no words on them.

## Cards: doorbell, remote, reports to, native

11. Write four cards by hand, in C1's shape:
    ```
    mkdir -p $TC_ROOT/cards
    echo '{"version": 1, "name": "cx", "kind": "codex", "account": "work", "route": "codex", "thread_id": "t1", "reports_to": "a"}' > $TC_ROOT/cards/cx.json
    echo '{"version": 1, "name": "far", "kind": "claude", "account": "home", "route": "ssh", "ssh": {"target": "u@h", "tc": "~/TheConnection/tc"}, "reports_to": null}' > $TC_ROOT/cards/far.json
    echo '{"version": 1, "name": "b", "kind": "claude", "account": "work", "route": "local", "reports_to": "a"}' > $TC_ROOT/cards/b.json
    echo '{"version": 1, "name": "r", "kind": "claude", "account": "home", "route": "local", "reports_to": "ghost"}' > $TC_ROOT/cards/r.json
    ```
    - Within 3 s `cx · worker` appears under `a`, reading `◎ doorbell`, with
      a double border.
    - `b` now reads `b · worker`, with no `· inferred`. The thin line from
      `a` down to `b` carries no words; hover it: `b reports to a`. `cx`
      gets one too.
    - `far` appears as a root of its own beside or under `a`'s tree, with
      its own heading, reading `⇄ remote · not checked`, with a dotted
      border.
    - `r` appears as a root too. Its third line reads
      `reports to ghost · not found`.
    - The roots list at the top now names `a`, `far` and `r`.
    - `far` and `r` are both Claude cards on account `home`, so a dash-dot
      line joins them, side to side, with no words on the line. Each box
      grows a dashed badge in words: `far`'s reads `native with r · not
      observed`, `r`'s `native with far · not observed`. Hover the line:
      `far and r · native · not observed`. The legend names the dash-dot line.
12. Post a status: `./tc status c "reviewing the parser"`.
    - Within 3 s `c`'s third line reads `reviewing the parser`.

## The token and the address

13. In terminal 4:
    ```
    curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8780/feed
    curl -s -o /dev/null -w '%{http_code}\n' -H 'Host: evil.example' http://127.0.0.1:8780/feed
    curl -s -o /dev/null -w '%{http_code}\n' -X POST http://127.0.0.1:8780/feed
    curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8780/serve.py
    ss -ltnp | grep 8780
    ```
    - `401`, `421`, `405`, `404`, one per line.
    - `ss` shows the server listening on `127.0.0.1:8780` and nothing else:
      no `0.0.0.0`, no `*`.
14. Open the URL with the `#token=...` part cut off.
    - The pill reads `no token · open the URL serve.py printed`, with a dot
      that does not pulse. No boxes appear.
15. Open it with one character of the token changed.
    - The pill reads `token refused · open the URL serve.py printed`.

## Grayscale pass

16. Open the printed URL with `?gray=1` put before the `#`:
    `http://127.0.0.1:8780/live.html?gray=1#token=<t>`.
    The page draws in grayscale. Check each of these reads without color:
    - Every state by its glyph and word: `● listening`, `✎ writing` (send a
      message from a name with no listener, such as `a`, and look within
      10 s), `○ idle`, `✕ no listener`, `◔ working` and
      `△ woken · not read` (steps 7 and 8, again in gray), `◎ doorbell`,
      `⇄ remote · not checked`.
    - The second cue on each box: thick border for writing, dashed for no
      listener, a heavier solid border for woken, double for doorbell,
      dotted for remote. Working has none: it is calm.
    - Ports: the port on each box's top edge is a hollow ring (in), the one
      on its bottom edge a filled dot (out). Only the thin tree lines touch
      them; every other wire meets a box at its side.
    - A moving wire: dashes, an arrow at the reader, and `from → to · #n`
      beside it.
    - Stop `c`'s listener (Ctrl+C in terminal 3). Within 3 s `c` reads
      `✕ no listener` with a dashed border, and its wire is dotted. The
      dotted wire runs beside `c`'s thin tree line, never on it, so the
      gaps between its dots show.
    - Now mail it: `./tc send --from a --to c "still there?"`. `c` still
      reads `✕ no listener`, now and 2 minutes on, never `◔ working` or
      `△ woken · not read`: the board saw the listener gone before the
      mail came, so the mail woke nothing (D28). The pill still counts it
      under `no listener`.
    - Close `c`'s inbox to the board: `chmod 000 $TC_ROOT/mail/to-c`.
      Within 3 s `c`'s box carries a dashed badge `inbox unreadable` under
      `✕ no listener`: the board cannot tell what reached it. Open it
      again with `chmod u+rwx $TC_ROOT/mail/to-c`; the badge goes.
    - The legend says what the states cannot see: a crash after reading
      (it looks working for up to 10 min), and, with no board page open,
      when a listener went.
    - The tree's lines are thin and solid, with no words; the `native` line
      is dash-dot, with no words, and the badges on `far` and `r` say
      `native` in words. A quiet mail line is thicker than a tree line.
      The footer's legend names each kind of line in words, the quiet mail
      line too (`thick line: mail, none in the last 10 s`).
    - Each orchestrator reads as one by the word `orchestrator` in its title
      and in its tree's heading.
17. Do the same with `?theme=daylight&gray=1` before the `#`.
    - Same checks; the look is light with dark title and footer bars.

## The rest of the page

18. Use the switch at the right of the title bar (`◐ Dark`, `☀ Light`).
    - The whole board turns at once and keeps updating. The address bar
      keeps the `#token=...` part.
19. Narrow the window to phone width (about 390 px).
    - No sideways scroll. The graph gives way to the outline: under each
      root's heading, one row per session, each child indented under its
      parent with a rule down its left, each with its name, role, state
      glyph and word, and unread count. A tree of one session (`far`,
      `r`) has no heading; its row is enough. Under `far`'s and `r`'s rows,
      a line reads `native with r · not observed` and `native with far ·
      not observed`. Under the trees, `recent traffic`: one line per pair,
      such as `c → a · #4 · 1 m ago`, newest first. No wires.
    - Widen the window slowly. The graph comes back only about 24 px past
      the width where the outline appeared, and the page never flickers
      between the two.
    - The pill takes a line of its own under the title and wraps rather
      than end in an ellipsis. The footer's counts wrap onto more lines;
      none ends in an ellipsis.
    - The roots list is still at the top; tap a name and its tree's
      heading comes to the top of the screen.
20. Fourteen names, the size of Donald's real board. Write eight more
    worker cards under `a`, on account `unknown` so no native lines join
    them:
    ```
    for w in w1 w2 w3 w4 w5 w6 w7 w8; do
      echo "{\"version\": 1, \"name\": \"$w\", \"kind\": \"claude\", \"account\": \"unknown\", \"route\": \"local\", \"reports_to\": \"a\"}" > $TC_ROOT/cards/$w.json
    done
    ```
    The board now holds 14 names: `a`, `b`, `c`, `cx`, `far`, `r` and `w1`
    to `w8`.
    - At full desktop width, `a`'s children fill rows under it and wrap to
      a new row instead of running off the side. No box overlaps another.
      The thin lines to the wrapped rows run down a lane at the left of
      `a`'s own tree, which no other parent's lines share.
    - The window grows to hold the whole board and the page scrolls down to
      it; there is no scroll box inside the window. The legend sits under
      the board, in the footer.
    - Each tree starts with its heading: `a`'s starts `a · orchestrator`
      and ends `12 sessions` (all but `far` and `r`). Click `far` in the roots list at the top: its tree's
      heading comes to the top of the screen.
    - Send a few messages between workers in different rows (for example
      `./tc send --from w1 --to w8 "x"`). Their wires go round the boxes in
      the gaps, never through a box. Each moving wire's words sit beside it,
      never on a box or on another label.
    - Every title, state line, status line and wire label reads without
      zooming. In devtools, a `.tc-node-note` or a `.tc-wire-label` has a
      computed font-size of 11px or more, and the `.tc-view` element's
      style ends in `scale(1)`: the board is never shrunk.
    - Narrow the window to phone width (about 390 px). The outline: all 14
      names, each worker indented under `a`, and the recent traffic below.
      Nothing scrolls sideways.
    - Do the phone check again with `?gray=1` before the `#`: every state
      still reads by its glyph and word.
21. Turn on reduced motion (OS setting, or devtools
    "prefers-reduced-motion: reduce") and send a message.
    - The dashes stop moving, but the arrow and the words still show which
      wire carried it.
22. Stop the server: Ctrl+C in terminal 1, and look at the open page.
    - Within about 6 s a dashed line over the board reads `stale · last
      answer N s ago`, the pill reads the same with `is serve.py running?`,
      and no wire's dashes move: nothing looks live.
    - Scroll to the bottom of the board. The stale line stays at the top of
      the screen, on its own face. Narrow to phone width and scroll the
      outline: the same.
    - Restart the server with the same command and open the new URL it
      prints (the token is new). Nothing reads `✕ no listener`,
      `◔ working` or `△ woken · not read` until a listener has been seen
      and then stops: a restart forgets who was listening.
23. A reports_to cycle. Write two cards that report to each other:
    ```
    echo '{"version": 1, "name": "p", "kind": "claude", "account": "lab", "route": "local", "reports_to": "q"}' > $TC_ROOT/cards/p.json
    echo '{"version": 1, "name": "q", "kind": "claude", "account": "shop", "route": "local", "reports_to": "p"}' > $TC_ROOT/cards/q.json
    ```
    - Within 3 s `p` is a root with `q` under it, and `p`'s box carries a
      dashed badge `reports to q · cycle`, so the loop shows in words. At
      phone width the same words sit under `p`'s row.
24. Close the tab, then stop the server with Ctrl+C and both listeners with
    Ctrl+C. Run `unset TC_ROOT` in each terminal. The throwaway mailbox is
    under the system temp folder.

Record what you saw in `qa/results/` (the DOCS lane sets up that folder):
the date, the browser, and any step that did not read as written.
