# DASH-2: two refusals of tc report that C7 does not name

Model:  Claude Opus 5.5 (the DASH lane agent), 2026-10-17
Status: unreviewed
Pause:  open. The lane built (a) as recommended and left (b) out.

The brief: "Any other refusal is a pause, not a guess." C7 and row 1 of
the exit table name one refusal for `report`: its output file exists.
Two more cases come up.

## (a) OUT cannot be written

OUT's folder is not there, is not writable, or the disk is full. tc
must do something; a Python traceback (exit 1 by accident) is the worst
answer.

Options:
1. **Exit 1 with one line of words**, `tc report: could not write
   <OUT> (<why>); nothing was written there.`, after removing this
   run's own `.tmp`. Row 1 of the exit table gains "or cannot write it".
2. A new exit code for it. Nothing waits on `tc report`'s exit, so a
   new row buys nothing.

**Recommendation: option 1.** Built that way (`tc`, `cmd_report`,
`REPORT_WRITE_WORDS`), and tested
(`tests/test_report.py`,
`CommandTest.test_a_page_that_cannot_be_written_refuses_with_words`).
If accepted, contracts.md's row 1 needs the words added; this lane does
not edit contracts.md.

## (b) OUT inside the mailbox

`tc report mail/to-a/x.html` would write a file in an inbox (not a
message: it does not end in `.md`, so no listing counts it), and C7 says
the report "writes nothing in it". Running `tc report history.html`
from the checkout itself is the common case and must keep working: the
checkout is ROOT, but the page lands beside `tc`, not in `mail/`,
`status/`, `cards/` or `outbox/`.

Options:
1. **Refuse, exit 1, an OUT whose folder resolves inside ROOT's
   `mail/`, `status/`, `cards/` or `outbox/`**, with words naming the
   folder. ROOT itself stays allowed.
2. Leave it: a person who names a file in an inbox asked for it.

**Recommendation: option 1**, small and plain. Not built: it is a new
refusal, and the brief says a new refusal waits for a ruling. Today
such an OUT is written where it is named.
