# BOARD-4: native links between cards whose account is `unknown`

Model:  Claude Opus 5.5 (the BOARD lane agent), 2026-10-14
Status: unreviewed
Pause:  open. Built to C5 as written.

## The question

C5 draws a `native` link between "two `claude` cards with the same
`account`". O3 makes the account the word `unknown` when neither
`--account` nor `CLAUDE_CONFIG_DIR` gives one, and C1 notes the
architect's session had no `CLAUDE_CONFIG_DIR`. So on a machine where
nobody passes `--account`, every Claude card says `unknown`, and C5 links
every pair of them as `native · not observed`. Two sessions on two
different accounts would be drawn as one account that should be using
SendMessage. A hand run of `board/serve.py` with two such cards gave one
`native` link.

## Options

1. **Keep C5 as written.** The words say `not observed`, but the link
   still claims one account.
2. **Skip `unknown`:** no native link when the shared account is the
   word `unknown`. One comparison.
3. **Draw them apart:** a native link on `unknown` gets other words, such
   as `native? · account unknown`.

## Recommendation

Option 2. A link that claims a shared account no card knows is a wrong
claim on the board. Not built: it changes C5's rule, so it is the
architect's call.
