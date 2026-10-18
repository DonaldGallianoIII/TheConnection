# DASH-3: may the unscrubbed page name the mailbox it read?

Model:  Claude Opus 5.5 (the DASH lane agent), 2026-10-17, fix round 1
Status: unreviewed
Pause:  open. The lane built the stdout half and left the page half out.

## The question

Fix round 1, item 20 (the review's REC-8): "the page and the stdout line
name the mailbox read, as tc health's R2 line does. On a scrubbed page,
say only `this mailbox`, never the path."

C7, "The facts": "The renderer sees only these records, never a path, a
login, a hostname or ROOT." Naming ROOT on the unscrubbed page means
handing ROOT to the renderer, which C7 forbids in words. The brief says
a question the contract does not answer is a pause, and here the
contract answers the other way.

## What was built

The stdout line names the resolved page and the mailbox, as R2 does:
`wrote <page>: 12 messages, scrubbed. Mailbox <ROOT>, from TC_ROOT.`
(`tc`, `cmd_report`). That is the line a person sees right after a
mistyped `TC_ROOT`, which was REC-8's case. The page names nothing.

## Options

1. **Leave the page as it is.** The stdout line covers the mistyped
   `TC_ROOT`, and C7 stays as written.
2. **Amend C7** so the renderer may take one more fact, the mailbox's
   path, on an unscrubbed page only, shown in the summary; a scrubbed
   page says `this mailbox`. The scrub would drop it before the
   renderer, as it drops names.

## Recommendation

Option 1. The page is the thing a person keeps and passes around; a home
folder's path in it is one more real detail, and the stdout line already
answers "which mailbox did this read?" at the moment it matters.
