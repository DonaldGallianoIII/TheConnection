# BOARD-3: the feed adds a `parent` key to each node

Model:  Claude Opus 5.5 (the BOARD lane agent), 2026-10-14
Status: unreviewed
Pause:  open. Built to the recommendation below.

## The question

C5 says `layoutLevels(feed)` puts "each root's tree side by side". To
know which tree a node belongs to, the page needs each node's parent.
C5's node shape has `reports_to` (the card's hint) and `level`, but not
the parent the level walk used. An inferred parent (from mail) appears
nowhere in the feed. C5 also says `feed()` computes roles and levels so
Python tests pin them, and `look.js` only lays them out. So the page
should not redo the inference.

## Options

1. **Add `parent` to each node:** the node's parent under C5 rule 2
   (declared or inferred), or null. A cycle's root keeps its parent edge
   here and sits at level 0; the layout hangs a node under its parent
   only when its level is the parent's plus one.
2. **Infer it again in `look.js`** from `reports_to` and the mailbox
   links. Two copies of rule 2, in two languages, that can drift.
3. **Lay out by level only**, with no trees: every level 0 node in one
   row, every level 1 node in the next. Two orchestrators' workers would
   mix in one row.

## Recommendation

Option 1. It only adds a key, so no reader of C5's shape breaks. Built
that way: `board/serve.py` emits it, `tests/test_board_feed.py` checks it
in every shape, and `layoutLevels` reads it. If approved, C5's node
example gains `"parent": null`.
