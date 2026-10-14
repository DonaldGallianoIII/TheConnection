# CARDS-2: the new-inbox warning says "nobody has joined" for a name that has

Model:  Claude Opus 5.5 (the CARDS lane agent), 2026-10-14
Status: unreviewed
Pause:  open. Built to the contract as written; the fix is one line.

## The question

C2 says `deliver_local` warns `new inbox: nobody has joined as <to>` when
the inbox did not exist before the send. C1's `tc join` writes a card and
no inbox. So the first send to a name that just joined, before it ever
ran `tc wait`, says nobody has joined. That is false, and a Codex name
never runs `tc wait` (D3), so every Codex name gets it on its first mail.

How it plays out: `tc join c` inside a Codex session, then
`tc send --from a --to c hi` prints the send line, `rang codex c`, and on
stderr `new inbox: nobody has joined as c`.

## The options

1. As built: the warning keys on the inbox alone (C2 word for word).
2. `tc join` also makes `mail/to-<name>/read/`, so a joined name always
   has an inbox.
3. The warning keys on "no inbox and no card": one line in
   `deliver_local` (`if not box_existed and card is None`).

## Recommendation

Option 3. The warning's words are about joining, and the card is the
record of a join. It keeps `tc join` to the one file C1 names. A name
nobody joined still gets the warning, which is what O1 wants.

Until this is settled, `tests/test_router.py` does not assert stderr on a
send to a joined name (`test_a_local_card_delivers_where_to_says_and_reports_to_routes_nothing`).
