# QA: board look kit

What this checks: the look kit in `board/` draws the window, sessions and wires
the way the Greener Pastures node graph does, and every state reads without color.

1. From the repo root, run `python3 -m http.server 8765 -d board`.
2. Open http://localhost:8765/demo.html in a browser.
   - You should see a dark window with three traffic dots, the title
     `connection.board`, and a status pill on the right reading
     `5 listening · 1 down`.
   - Six session boxes: `you · phone`, `a · relay`, and four workers on the right.
     Each box has a colored bar on its left edge.
3. Watch for 15 seconds.
   - One wire at a time turns dashed and the dashes move. The moving dashes
     always run toward the session reading the message.
   - An arrowhead sits at the reader's end and a label like `a → b · #41` floats
     over the wire.
   - The sender's box gets a thicker border and its second line reads `✎ writing`.
4. Check each state reads without color (turn your screen to grayscale, or use the
   browser's devtools "emulate achromatopsia"):
   - `● listening`, `✎ writing`, `○ idle · 41m`, `✕ no listener` all show as words.
   - `zed · worker` has a dashed border and a dotted wire.
   - Ports: the left port on each box is a hollow ring (in), the right one a filled
     dot (out).
5. Narrow the window to phone width (about 390 px).
   - No sideways scroll. The board shrinks to fit inside the canvas.
6. Turn on reduced motion (OS setting, or devtools "prefers-reduced-motion: reduce").
   - The dashes stop moving, but the dashed line, arrow and label still show which
     wire is active.
7. Open http://localhost:8765/demo.html?theme=daylight (the Daylight light look).
   - A steel gray page, white session cards, and dark gunmetal title and footer
     bars with white words.
   - The writing line, the wires and the out ports are blue. `zed · worker` is hot
     pink with a dashed border, not red.
   - Steps 3 to 6 hold here too.
8. Open http://localhost:8765/demo.html?theme=daylight&gray=1, then the same
   without `theme=daylight`.
   - The page draws in grayscale. Every state still reads by its word and glyph,
     the dead wire is still dotted, the active one still dashed with an arrow.
9. Open http://localhost:8765/demo.html and use the switch at the right of the
   title bar.
   - It has two buttons, `◐ Dark` and `☀ Light`. The one that is on has a light
     face, dark bold words and a filled dot; the other has no face and a ring.
   - Click `Light`: the whole board turns to the light look at once, traffic
     keeps running, and the address bar now ends in `?theme=daylight`.
   - Reload: it stays on Light. Click `Dark`, reload: it stays on Dark.
   - At phone width the words drop and the `◐` and `☀` symbols stay, with the
     filled dot still on the pressed one.
10. Open http://localhost:8765/compare.html.
   - Both looks side by side, labeled, each running its own traffic. On a phone
     width they stack.
11. Stop the server with Ctrl+C.
