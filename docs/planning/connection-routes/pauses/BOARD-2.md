# BOARD-2: an inferred parent can turn a declared one upside down

Model:  Claude Opus 5.5 (the BOARD lane agent), 2026-10-14
Status: unreviewed
Pause:  settled by D15 (2026-10-14): option 2. Built in fix round 1.

## The ruling (D15)

Rule 2 never infers a parent that inverts a declared edge: inference skips
a node whose one partner's card reports to that node. C5 on the dev branch
says so in rule 2. Built in `board/serve.py` (`parents_of`).
`tests/test_board_feed.py` `test_inference_never_inverts_a_declared_edge`
runs the first case below with the top node named `z`, then `a`: the top
node is level 0 and `b` level 1 under it either way. The milder case stays
a known limit, as option 2 says.

The rest of this file is the question as first asked.

## The question

C5 rule 2 infers a parent "when nothing is declared", on the node itself.
It never asks whether the inferred edge runs against a declared one. So a
node can get its own declared worker as its inferred parent.

Seen by hand on `board/serve.py` as built (a scratch run, not a test):

- Cards: `b` reports to `z`. Mail: `z` and `b` exchange one each way,
  `x` and `b` the same.
- `z` has one partner, `b`; `b` has two (`z`, `x`). So rule 2 gives `z`
  the inferred parent `b`, against the card that says `b` reports to `z`.
- That makes a cycle. Rule 5 breaks it at the name that sorts first, `b`.
- Result: `b` at level 0, `z` at level 1 under its own worker. With names
  that sort the other way (`a` for `z`), the same shape draws right.

A milder case from the same rule: `x1` and `x2` report to `x` by card but
have never been mailed, and `x` mails only `y`, which has two workers by
mail. `x` gets `y` as its inferred parent and is drawn under it. That one
is the C5 rule 6 kind of limit (an orchestrator with no mail partners
below it), and `--reports-to` is its fix.

## Options

1. **Keep C5 as written.** The drawing depends on name order in the first
   case.
2. **Never invert a declared edge:** skip inference for node X when its
   one partner P declares X as P's own parent. One extra lookup per node.
   Fixes the first case, leaves the milder one as a known limit.
3. **No inference for any node a card names:** skip inference for X when
   any card reports to X. Fixes both cases, but also stops a mid relay
   with quiet declared workers from being drawn under its own relay by
   mail.

## Recommendation

Option 2, as a one-line change to rule 2 in `contracts.md`, plus a shape
test with the names above. The architect's call, since the contract
changes. Until then the board follows C5 step by step, as the brief asks.
