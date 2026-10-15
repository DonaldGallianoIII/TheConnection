# two-edges-on-one-pair-share-a-path

Model:  Claude Opus 5.5 (the known-bugs writer, for the architect session), 2026-10-15
Status: unreviewed

**What:** a graph view draws more than one stroke between the same two
nodes (two edge kinds, or an edge over the tree's own connector), and it
computes each stroke's path and label point from the two endpoints alone.
The strokes lie on one path, their labels print on top of each other, and
one stroke fills the gaps of the other's dash pattern. That pattern may be
the cue for a state that does not rely on color.

**How it showed:** twice in the BOARD lane, 2026-10-14.

- Mailbox and native on one pair. At `d250036`, `board/look.js:533` to
  541 built the mailbox edge and the native edge for one pair from the
  same two ports, and drawEdge (`:651` to 653) put both labels at the
  midpoint. `a → b · #5` printed over `native · not observed`, and the
  native dash (`board/theme.css:358`) lay over the dotted `down` pattern
  (`:352`). The pair this hits is the one native links exist to flag: two
  sessions on one account that mail each other.
- Connector and mail wire on a parent and child. After the lane's second
  fix round (at `53b2f28`), a parent and child's mail wire or native line
  took the same run as their tree connector (`board/look.js:1415` to
  1417), and the connector sat under every edge. The solid connector
  filled the gaps of the dotted `no listener` pattern, so in grayscale the
  wire read as a solid beaded line, and a native tree line's long dash
  vanished.

**Why it's bad:** neither label can be read, and the wire's only cue for
a stopped listener that does not rely on color is covered. For a
colorblind reader the down state on that wire disappears.

**Prevention:** before drawing, collect the pairs that carry more than
one stroke. Then either fold the extra kinds into one stroke and put
their words where they are always drawn, or give each stroke its own
geometry (a named offset constant or a different route) and its own
label anchor. What landed here: a pair that mails draws one path, the
mail wire, and both boxes carry a badge
`native with <the other> · not observed`; a native pair with no mail
keeps its own dash-dot line; a parent and child's wire runs
`TREE_WIRE_OFFSET` beside the connector and shares no piece of it. Words
moved to a hover title only are not a fix: a phone has no hover. Test a
pair carrying every kind that can coexist, and assert one path holding
all the words, or distinct paths and label points.

**The check that catches it:**

- `tests/board-patch.test.mjs`, "a mailbox wire and a native line on one
  pair draw one path, the native words in its title and on both boxes".
- `tests/board-patch.test.mjs`, "both boxes and both outline rows of a
  native pair say native with the other, not observed, with mail or
  without".
- `tests/board-layout.test.mjs`, "a parent's mail runs beside its
  connector and shares no piece of it; two boxes side by side are joined
  straight across".

**Detection:** an edge builder that branches on kind but calls the same
path function with only the two endpoints for every kind (`portPoint(a)`,
`portPoint(b)`, `wirePath(a, b)`, `routeTree(` for both the connector and
the wire); edge ids like `${kind}:${from}>${to}`, one per kind per pair,
with no offset or merge step; a label placed at the path midpoint with no
offset per kind. Then check whether the feed can emit two kinds for one
pair (mailbox and native here, plus the tree connector under both; check
every pair of kinds the view can emit).

**Source:** the BOARD lane's full review (audit folder
`2026-10-14-1811-full`; review audits stay out of the repo), MEDIUM-3, and
the lane's round 2 review (audit folder `2026-10-14-2047-custom`),
MEDIUM-2. Round 1's fix, `280a200`, drew one wire with the native words on
a second label line. Round 2, `880a304`, moved those words to a hover
title only, and the round 2 review filed that as a regression. `4cf941d`
closed both findings: the badges on both boxes, and the tree wire offset
beside its connector. All reached the dev branch with the BOARD merge,
`a2953cb`. A related form, not counted here: siblings on one side of a
parent shared one offset run, so a quiet sibling's solid wire filled a
down worker's dots (the round 3 review, audit folder
`2026-10-14-2209-quick`, MEDIUM-1). `4994610` paints dotted and dashed
wires last, each on a knockout in the canvas's face, pinned by
`tests/board-layout.test.mjs`, "a relay over w1 to w4 it has mailed, w2
down, at 1152 px: the down wire is drawn after every solid wire, on a
knockout".

**Times hit:** 2, both in the BOARD lane on 2026-10-14.

**Tier when hit:** MEDIUM. Unreadable labels on the pair the feature
exists to flag, plus a covered cue that does not rely on color.

**Shared catalog:** none on this mechanism. Close kin of "The non-color
encoding runs out."
(`~/Conventions/code/known-bugs/any-language/accessibility.md`): here the
cue exists, but something is drawn over it.
