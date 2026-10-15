# fit-to-screen-scales-text-below-legible

Model:  Claude Opus 5.5 (the known-bugs writer, for the architect session), 2026-10-15
Status: unreviewed

**What:** a diagram grows one column per item and never wraps. It is
fitted to its container by one uniform scale with a floor that is not
derived from a minimum text size, inside a container with
`overflow: hidden`. As items are added, every word, glyph and label
shrinks together. Past a handful of items the text cannot be read, and
nothing scrolls.

**How it showed:** the BOARD lane, 2026-10-14. At `d250036`,
`board/look.js:426` to 449 gave every leaf its own 236 px column and never
wrapped. live.html scaled the whole board down as far as
`MIN_FIT_SCALE: 0.2` (`board/look.js:62`, applied at `:698`), and
`board/theme.css:278` set `overflow: hidden`, so nothing scrolled.

- On a 1152 px canvas, a star of 7 leaves drew role words at about 7.4 px
  (run in a scratch copy).
- At 390 px the demo drew near scale 0.25, with titles near 3 px (an
  estimate).
- Fourteen names at 390 px hit the floor with more than half the board
  clipped (arithmetic, not run in a browser).

The state line, the note and the wire labels were 9 px even at scale 1.
The comment at `board/look.js:61` said the floor keeps "a node legible".
The QA phone-width step passed on "shrinks to fit", which any scale meets.

**Why it's bad:** the board becomes unreadable at exactly the size where
it starts to matter. Words and glyphs are the cues that do not rely on
color. Once they shrink away only hue is left, which breaks the
colorblind hard rule.

**Prevention:** derive the floor from a named minimum text size:
`MIN_FIT_SCALE = MIN_TEXT_PX / BOARD_TEXT_MIN_PX` (1 today, so the board
is never shrunk). Below that floor, wrap into rows that fit the width and
scroll down. Never scroll sideways and never shrink further. Keep base
text at or above the minimum at scale 1 too. Test with the largest
realistic count at the narrowest supported width, asserting that the
drawn scale times the smallest font size is at least the minimum.

**The check that catches it:** `tests/board-layout.test.mjs`:

- "fourteen names fit a desktop and a phone: inside the width, no
  overlap, no text under MIN_TEXT_PX": a 14-node star and 14 peers at
  1152 and 358 px.
- "no font-size in theme.css is under MIN_TEXT_PX, and the board's
  smallest is BOARD_TEXT_MIN_PX".
- "an empty feed lays out nothing; fitTransform never enlarges or shrinks
  past its floor", which asserts the floor equals
  `MIN_TEXT_PX / BOARD_TEXT_MIN_PX`.

In a real browser, `tests/board-browser-check.mjs` fails on drawn text
under 11 px at 1280 x 900 and 390 x 844. It needs Playwright and is not
part of `node --test`; without Playwright it prints
`skipped: playwright not found` and exits 0.

**Detection:** a fit function returning one uniform scale
(`Math.min(w / extent.w, h / extent.h)`, `transform: scale(`), clamped by
a constant (`MIN_.*SCALE`, `Math.max(0.`) that is not computed from a
font size. The container's CSS has `overflow: hidden`. The layout's width
grows with the item count and never breaks to a new row (one column per
leaf, `x += colW`). Also: any `font-size` under the project minimum (11 px
here) on text that carries meaning, and any QA or test line that accepts
"fits" or "shrinks to fit" without naming a size.

**Source:** the BOARD lane's full review, 2026-10-14 (audit folder
`2026-10-14-1811-full`; review audits stay out of the repo), MEDIUM-1.
Closed by `280a200` (rows that wrap at the canvas width, every board font
at 11 px or more, the floor derived from the text size, and the first two
tests above) and `94a5dc1` (the window takes the viewport's height and the
page scrolls down). Both reached the dev branch with the BOARD merge,
`a2953cb`. The P4 phase review (audit folder `2026-10-14-2344-full`) found
no font under 11 px. One edge case is left, filed LOW there: a tree about
12 levels deep, two children per level, outgrows a 560 px stage.
`602b62a` made layoutLevels' doc block say when its extent can pass the
width.

**Times hit:** 1.

**Tier when hit:** MEDIUM. At the floor the only cue left is color, and
the conventions put a colorblind-rule breach at MEDIUM or higher.

**Shared catalog:** reaches the same end state as "The non-color
encoding runs out."
(`~/Conventions/code/known-bugs/any-language/accessibility.md`): past some
count, items differ by color alone. The mechanism differs: here the cues
shrink, rather than the list of marks running out. Text cut by a missing
break point is a separate entry, `outside-text-clipped-by-overflow-hidden`.
