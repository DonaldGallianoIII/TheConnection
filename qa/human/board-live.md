# QA: the live board

Model:  Claude Opus 5.5 (the BOARD lane agent), 2026-10-14
Status: unreviewed. Written, not yet run by a person.

What this checks: `board/serve.py` serves the live board on 127.0.0.1 only,
refuses without its token, and `board/live.html` draws a real mailbox and
follows it as mail moves. Every state, port and wire reads in grayscale.

Run everything from the repo root, in a throwaway mailbox, never the live one.
Names below are made up.

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
   - A dark window titled `connection.board · TheConnection :: live`.
   - The pill on the right reads `live · 2 listening`.
   - Two boxes, `b · peer · inferred` and `c · peer · inferred`, each with
     `● listening` on its second line.

## Mail moves on the board

A name gets a box once it has an inbox (it was sent mail, or ran
`tc wait`) or a card. A listener wakes and exits when mail reaches it, the
same as in a real session, so each send to `b` or `c` below is followed by
re-arming that listener. Once the CARDS lane's router is in `tc`, a first
send to a name may also print `new inbox: nobody has joined as <name>` on
stderr; that is expected here. Send nothing to `cx` or `far` after step 11:
their cards route mail to `codex` and `ssh`, which this script never runs.

6. In terminal 4: `./tc send --from b --to a "ready"`
   - Within 3 s a box `a · peer · inferred` appears, reading
     `○ idle · 1 unread` (`a` has an inbox now, and no listener).
   - The wire between `a` and `b` turns dashed and moves, with the words
     `b → a · #1` and an arrow at `a`, the reader.
7. In terminal 4: `./tc send --from a --to b "first task"`
   - Within 3 s the same wire flows the other way, `a → b · #2`, with the
     arrow at `b`.
   - `a` reads `✎ writing` with a thicker border, for about 10 s.
   - `b`'s listener in terminal 2 exits with `MAIL:`. Within 3 s `b` reads
     `✕ no listener` with a dashed border, its wire turns dotted, and the
     pill reads `1 listening · 1 no listener`, the same words as the box.
8. In terminal 2: `./tc read b`, then `./tc wait b` again.
   - Within 3 s `b` reads `● listening` again and the pill goes back to
     `live · 2 listening`.
9. Make `a` a relay. In terminal 4: `./tc send --from a --to c "second task"`,
   then in terminal 3 `./tc read c` and `./tc wait c` again, then in
   terminal 4 `./tc send --from c --to a "on it"`.
   - `a` sits on the top row and reads `a · orchestrator · inferred`.
   - `b` and `c` sit one row below it and read `worker · inferred`.
   - Each message flows on its wire within 3 s, with the arrow at the
     reader. `c → a` runs up the wire with the arrow at `a`'s end.
10. Wait 10 s with no mail.
    - The dashes stop and the words leave the wires. The quiet lines stay.

## Cards: doorbell, remote, reports to, native

11. Write four cards by hand (`tc join` is another lane's work, not in this
    tree yet):
    ```
    mkdir -p $TC_ROOT/cards
    echo '{"version": 1, "name": "cx", "kind": "codex", "account": "work", "route": "codex", "thread_id": "t1", "reports_to": "a"}' > $TC_ROOT/cards/cx.json
    echo '{"version": 1, "name": "far", "kind": "claude", "account": "home", "route": "ssh", "ssh": {"target": "u@h", "tc": "~/TheConnection/tc"}, "reports_to": null}' > $TC_ROOT/cards/far.json
    echo '{"version": 1, "name": "b", "kind": "claude", "account": "work", "route": "local", "reports_to": "a"}' > $TC_ROOT/cards/b.json
    echo '{"version": 1, "name": "r", "kind": "claude", "account": "home", "route": "local", "reports_to": "ghost"}' > $TC_ROOT/cards/r.json
    ```
    - Within 3 s `cx · worker` appears under `a`, reading `◎ doorbell`, with
      a double border.
    - `b` now reads `b · worker`, with no `· inferred`. A thin line with the
      words `reports to` runs from the top of `b` up to the bottom of `a`,
      and another from `cx`.
    - `far` appears as a root of its own to the right of `a`'s tree, reading
      `⇄ remote · not checked`, with a dotted border.
    - `r` appears as a root too. Its third line reads
      `reports to ghost · not found`.
    - `far` and `r` are both Claude cards on account `home`, so a long-dash
      line with the words `native · not observed` joins them.
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
      10 s), `○ idle`, `✕ no listener`, `◎ doorbell`,
      `⇄ remote · not checked`.
    - The second cue on each box: thick border for writing, dashed for no
      listener, double for doorbell, dotted for remote.
    - Ports: the left port on each box is a hollow ring (in), the right one a
      filled dot (out).
    - A moving wire: dashes, an arrow at the reader, and `from → to · #n`.
    - Stop `c`'s listener (Ctrl+C in terminal 3). Within 3 s `c` reads
      `✕ no listener` with a dashed border, and its wire is dotted.
    - The `reports to` lines are thin and carry their words; the `native`
      line is long-dashed and carries `native · not observed`.
    - Each orchestrator reads as one by the word `orchestrator` in its title.
17. Do the same with `?theme=daylight&gray=1` before the `#`.
    - Same checks; the look is light with dark title and footer bars.

## The rest of the page

18. Use the switch at the right of the title bar (`◐ Dark`, `☀ Light`).
    - The whole board turns at once and keeps updating. The address bar
      keeps the `#token=...` part.
19. Narrow the window to phone width (about 390 px).
    - No sideways scroll. The board keeps its size: the boxes wrap to one
      per row, each child set a little right of its parent, and the canvas
      scrolls down to the rest.
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
    - Every title, state line, status line and wire label reads without
      zooming. In devtools, a `.tc-node-note` or a `.tc-wire-label` has a
      computed font-size of 11px or more, and the `.tc-view` element's
      style ends in `scale(1)`: the board is never shrunk.
    - Narrow the window to phone width (about 390 px). One box per row, each
      worker a little right of `a`, so the levels still read. The canvas
      scrolls down to the rest. Nothing scrolls sideways, on the page or in
      the canvas.
    - Do the phone check again with `?gray=1` before the `#`: every state
      still reads by its glyph and word.
21. Turn on reduced motion (OS setting, or devtools
    "prefers-reduced-motion: reduce") and send a message.
    - The dashes stop moving, but the arrow and the words still show which
      wire carried it.
22. Stop the server: Ctrl+C in terminal 1, then restart it with the same
    command and open the new URL it prints (the token is new).
    - Nothing reads `✕ no listener` until a listener has been seen and then
      stops: a restart forgets who was listening.
23. Close the tab, then stop the server with Ctrl+C and both listeners with
    Ctrl+C. Run `unset TC_ROOT` in each terminal. The throwaway mailbox is
    under the system temp folder.

Record what you saw in `qa/results/` (the DOCS lane sets up that folder):
the date, the browser, and any step that did not read as written.
