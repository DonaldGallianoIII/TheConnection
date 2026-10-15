# QA: board look kit

What this checks: the look kit in `board/` draws the window, sessions and wires
the way the Greener Pastures node graph does, the demo draws D7's shapes (two
orchestrators side by side, one of them over a relay that is an orchestrator
too), and every state and every role reads without color.

Updated for the shapes demo by Claude Opus 5.5 (the BOARD lane agent),
2026-10-14. Status: unreviewed, not yet run by a person.

1. From the repo root, run `TC_ROOT=$(mktemp -d) python3 board/serve.py`.
   It prints a `live.html` URL; this script uses the demo pages, which need
   no token. (Port 8780; add `--port 8781` if it is taken.)
2. Open http://127.0.0.1:8780/demo.html in a browser.
   - You should see a dark window with three traffic dots, the title
     `connection.board`, and a status pill on the right reading
     `4 listening · 1 down`.
   - Two trees side by side, each root on the top row:
     - Left: `a · orchestrator` on top. Under it `b · orchestrator · inferred`
       and `docs · worker`. Under `b`, `c · worker` and `d · worker · inferred`.
     - Right: `z · orchestrator · inferred` on top, with `y1 · worker` and
       `y2 · worker · inferred` under it.
   - Each box has a colored bar on its left edge (identity only) and up to
     three lines: the title, the state, and a status line where one is set.
3. Watch for 20 seconds.
   - One wire at a time turns dashed and the dashes move. The moving dashes
     always run toward the session reading the message.
   - An arrowhead sits at the reader's end and a label like `a → b · #41`
     floats over the wire. `z → a · #45` runs between the two orchestrators.
   - The box that sends gets a thicker border and its second line reads
     `✎ writing` for its step, whether it was listening or not (D15: writing
     comes first).
4. Check each state reads without color (turn your screen to grayscale, or use
   the browser's devtools "emulate achromatopsia"):
   - `● listening` (`a`, `b`, `z`, `y1`), `○ idle` (`docs`), `✕ no listener`
     (`d`), `◎ doorbell` (`c`), `⇄ remote · not checked` (`y2`), and
     `✎ writing` on whichever box sends, all show as words.
   - `d` has a dashed border and its wire to `b` is dotted. `c` has a double
     border; `y2` a dotted one.
   - Thin lines with the words `reports to` run from the top of `b`, `docs`,
     `c` and `y1` up to the bottom of their parent.
   - A long-dash line with the words `native · not observed` joins `b` and
     `docs`.
   - Ports: the left port on each box is a hollow ring (in), the right one a
     filled dot (out).
5. Narrow the window to phone width (about 390 px).
   - No sideways scroll. The board shrinks to fit inside the canvas.
6. Turn on reduced motion (OS setting, or devtools "prefers-reduced-motion: reduce").
   - The dashes stop moving, but the dashed line, arrow and label still show which
     wire is active.
7. Open http://127.0.0.1:8780/demo.html?theme=daylight (the Daylight light look).
   - A steel gray page, white session cards, and dark gunmetal title and footer
     bars with white words.
   - The writing line, the wires and the out ports are blue. `d` is hot pink
     with a dashed border, not red.
   - Steps 3 to 6 hold here too.
8. Open http://127.0.0.1:8780/demo.html?theme=daylight&gray=1, then the same
   without `theme=daylight`.
   - The page draws in grayscale. Every state still reads by its word and glyph,
     the dead wire is still dotted, the active one still dashed with an arrow.
   - Each orchestrator reads as one by its word: `a · orchestrator`,
     `b · orchestrator · inferred` and `z · orchestrator · inferred`. Every other
     box reads `worker`. Nothing about a role depends on the colored bar.
9. Open http://127.0.0.1:8780/demo.html and use the switch at the right of the
   title bar.
   - It has two buttons, `◐ Dark` and `☀ Light`. The one that is on has a light
     face, dark bold words and a filled dot; the other has no face and a ring.
   - Click `Light`: the whole board turns to the light look at once, traffic
     keeps running, and the address bar now ends in `?theme=daylight`.
   - Reload: it stays on Light. Click `Dark`, reload: it stays on Dark.
   - At phone width the words drop and the `◐` and `☀` symbols stay, with the
     filled dot still on the pressed one.
10. Open http://127.0.0.1:8780/compare.html.
   - Both looks side by side, labeled, each running its own traffic. On a phone
     width they stack.
11. Stop the server with Ctrl+C.
