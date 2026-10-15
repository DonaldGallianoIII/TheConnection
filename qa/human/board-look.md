# QA: board look kit

What this checks: the look kit in `board/` draws the window, sessions and wires
the way the Greener Pastures node graph does, the demo draws D7's shapes (two
orchestrators, side by side on a wide screen and one under the other at the
window's 1180 px cap, one of them over a relay that is an orchestrator too),
and every state and every role reads without color.

Updated for the shapes demo by Claude Opus 5.5 (the BOARD lane agent),
2026-10-14, for routing, labels, headings, the outline, native badges
and wires beside their tree lines by Claude Opus 5.5 (the BOARD fixer),
and for D24's working and woken states and the dash-dot line by Claude
Opus 5.5 (the P4 phase fixer), 2026-10-15.
Status: unreviewed, not yet run by a person. `tests/board-browser-check.mjs` measures the same page frame on
the live board (see `qa/human/board-live.md`); this script is the demo's.

1. From the repo root, run `TC_ROOT=$(mktemp -d) python3 board/serve.py`.
   It prints a `live.html` URL; this script uses the demo pages, which need
   no token. (Port 8780; add `--port 8781` if it is taken.)
2. Open http://127.0.0.1:8780/demo.html in a browser.
   - You should see a dark window with three traffic dots, the title
     `connection.board`, and a status pill on the right reading
     `2 listening · 1 no listener · 1 woken · not read`, the same words as
     `d`'s and `y1`'s boxes.
   - The window reaches the bottom of the browser window. Under the title
     bar, the session chips, then the roots list: `2 orchestrators: a, z`.
   - Two trees, each with its root on top and a heading over it. Side by
     side at full text size they need more room than the window's 1180 px
     cap gives, so `z`'s tree sits under `a`'s, and the page may scroll down
     a little:
     - First: the heading `a · orchestrator · 5 sessions`, `a · orchestrator`
       on top, under it `b · orchestrator · inferred` and `docs · worker`,
       and under `b`, `c · worker` and `d · worker · inferred`.
     - Then: the heading `z · orchestrator · inferred · 3 sessions`, with
       `y1 · worker` and `y2 · worker · inferred` under `z`.
   - Click `z` in the roots list: `z`'s heading comes to the top of the
     screen.
   - Each box has a colored bar on its left edge (identity only) and up to
     three lines: the title (`a · orchestrator`, with a space each side of
     the dot), the state, and a status line where one is set. `b` and
     `docs` share an account, so each also carries a dashed badge in words:
     `native with docs · not observed` on `b`, `native with b · not
     observed` on `docs`.
   - A thin line runs from each parent's bottom (a filled dot, out) to each
     child's top (a hollow ring, in), with no words on it.
   - The legend is the first line of the footer, under the board.
3. Watch for 20 seconds.
   - One wire at a time turns dashed and the dashes move. The moving dashes
     always run toward the session reading the message.
   - An arrowhead sits at the reader's end and a label like `a → b · #41`
     sits beside the wire, never on it, on a box, or on another label.
     `a → b` runs beside the thin line from `a` to `b`, a little to one
     side of it, never on it. `z → a · #45` runs
     between the two orchestrators, from the side of one box to the side
     of the other, round every box between them.
   - No wire passes through a box, and only the thin tree lines touch a
     port.
   - The box that sends gets a thicker border and its second line reads
     `✎ writing` for its step, whether it was listening or not (D15: writing
     comes first).
4. Check each state reads without color (turn your screen to grayscale, or use
   the browser's devtools "emulate achromatopsia"):
   - `● listening` (`a`, `z`), `◔ working` (`b`: mail woke it and it is on
     its turn), `△ woken · not read` (`y1`: mail woke it and nothing read
     it), `○ idle` (`docs`), `✕ no listener` (`d`), `◎ doorbell` (`c`),
     `⇄ remote · not checked` (`y2`), and `✎ writing` on whichever box
     sends, all show as words.
   - `d` has a dashed border and its wire to `b` is dotted. The dotted wire
     runs beside `b`'s thin line to `d`, not on it, so its gaps show. `y1`
     has a heavier solid border, and its wire to `z` is a mail wire like
     any other, never dotted. `c` has a double border; `y2` a dotted one.
   - The tree's thin lines carry no words. Hover one: `docs reports to a`,
     or, where no card says so, `d under b · inferred from mail`. The legend
     names the thin line.
   - A dash-dot line joins `b` and `docs`, side to side, with no words on
     the line; the badges on both boxes say it in words. Hover the line:
     `b and docs · native · not observed`. The legend names the dash-dot line,
     and the thicker quiet mail line (`thick line: mail, none in the last
     10 s`), and says the thin line is `reports to, or inferred from
     mail`.
   - Ports: the port on each box's top edge is a hollow ring (in), the one
     on its bottom edge a filled dot (out).
5. Narrow the window to phone width (about 390 px).
   - No sideways scroll. The graph gives way to the outline: under the
     heading `a · orchestrator · 5 sessions`, one row per session of `a`'s
     tree, each child indented under its parent with a rule down its left;
     then `z`'s tree the same way; then `recent traffic`, one line per
     pair, newest first, such as `a → b · #41 · 0 s ago`. No wires.
   - Each row reads its name, role, state glyph and word, and unread count:
     `d · worker · inferred ✕ no listener`, and `y1 · worker △ woken · not
     read · 1 unread`. Under `b`'s row a line
     reads `native with docs · not observed`, and under `docs`'s `native
     with b · not observed`.
   - The pill takes a line of its own; it and the footer wrap rather than
     end in an ellipsis.
   - Every word reads without zooming.
6. Turn on reduced motion (OS setting, or devtools "prefers-reduced-motion: reduce"),
   at full width.
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
     `d`'s wire, the one dead wire, is still dotted, `y1`'s is not, and the
     active one is still dashed with an arrow and its words.
   - Each orchestrator reads as one by its word: `a · orchestrator`,
     `b · orchestrator · inferred` and `z · orchestrator · inferred`, and the
     two roots again in their headings and the roots list. Every other box
     reads `worker`. Nothing about a role depends on the colored bar.
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
