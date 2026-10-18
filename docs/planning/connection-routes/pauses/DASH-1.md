# DASH-1: what is an ask, for chart 5's count of asks no answer names

Model:  Claude Opus 5.5 (the DASH lane agent), 2026-10-17
Status: unreviewed
Pause:  settled by a2 for the owner, 2026-10-17: ASK_TAGS = QUESTION, PLAN-READY, PLAN-CHECK, MERGE, BLOCKED; the count reads `<n> asks have no reply that names them`, with a line saying why it can include answered asks (C7, built in fix round 1)

## The question

C7, chart 5: "asks with no answer naming them are counted in words,
never guessed." C7 defines an answer (a message whose first line names
`#N` and goes from #N's recipient back to #N's sender) but not an ask.
Every message is a possible ask, so "asks with no answer" needs a rule
for which messages count, or the count is every unanswered message.

## Options

1. **A message tagged `QUESTION`.** The count reads `1 QUESTION message
   has no answer naming it.` Plain, and it never guesses: the sender
   said it was asking. A message an answer names is drawn as an ask
   whatever its tag, as C7 says.
2. **A message tagged with any of a short list**: QUESTION, PLAN-CHECK,
   REVIEW. Wider, but a REVIEW is often a report back, not a request,
   so it would count answered work as open.
3. **Any message some later first line names by `#N`, in either
   direction, that no answer names.** Counts a message someone pointed
   at but nobody answered. It needs no tag, but a `Re #N` the wrong way
   round (a follow-up from the asker) makes its target an "ask", which
   reads as a guess.
4. **Every message with no answer.** Honest but useless: nearly every
   message is unanswered by design (reports, FYIs, status).

## Recommendation

Option 1. It is what the owner's sessions already write, it guesses
nothing, and the scrub keeps QUESTION (it is on `SCRUB_TAGS`), so a
scrubbed page shows the same count.

## What the lane did meanwhile

`board/report.py` has `ASK_TAGS = ("QUESTION",)` with a comment naming
this pause, and the chart 5 words read from it (`QUESTION message`).
Another answer changes that one tuple; the test that asserts the count
(`tests/test_report.py`, `AnswersTest`) names the tag in its expected
words and would change with it.
