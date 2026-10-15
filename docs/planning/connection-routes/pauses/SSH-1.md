# SSH-1: the member who makes an outbox/to-<name>/ can still move the others' mail in it

Model:  Claude Opus 5.5 (the SSH lane agent), 2026-10-15
Status: unreviewed
Pause:  open. Nothing built waits on it: the lane built lane note 2 as
        written (each outbox/to-<name>/ and its sent/ and refused/
        sticky, 3775), and this is what stays open after it.

## The question

C4 says `outbox/` "is sticky like the other shared folders, so a member
cannot move another member's queued file", and D22 that the outbox is
per sender. Lane note 2 makes each `outbox/to-<name>/`, and its `sent/`
and `refused/`, sticky too (3775), and this lane built that
(`shared_folder_mode`, commit `7700fc1`).

Sticky stops a member from renaming or deleting a file that member does
not own, in a folder that member does not own. It does not stop the
folder's owner. `outbox/to-<name>/` is made by whichever member first
sends to `<name>` over ssh, and that member owns it. So that member can
move or delete every other member's queued mail for `<name>`, and
rename the `sent/` or `refused/` another member made inside it. The
inbox has the same shape on purpose (D20: the recipient owns the inbox
so `tc read` can move mail), but the outbox has no recipient: its
owner is only whoever came first.

What that member cannot do: read more than the group already reads
(the files are 0640), or rewrite another member's file in place. What
they can do: make another member's queued message disappear before
`tc flush` sends it, which D20 calls loss when it is unread mail.

Not checked with a real second user: one user cannot own a folder and
a file as two users. `qa/human/route-shared.md` step 38 asks Donald to
look.

## The options

1. **Accept and say so.** C4's sentence gains "except the member who
   made that `outbox/to-<name>/`". The README's shared section says the
   outbox trusts the first sender to a name. No code changes.
2. **A folder per sender inside each queue:**
   `outbox/to-<name>/<user>/NNNNNN-from-<sender>.md`, with `sent/` and
   `refused/` under each `<user>/`, each made by that user, so every
   queued file sits in a folder its own sender owns. `to-<name>/` stays
   sticky and shared. This changes D25's layout (C3), the board's
   future reading of the outbox, `outbox_files`, `file_away` and init's
   expected modes.

Not an option: init cannot make `outbox/to-<name>/` ahead of time for
names nobody has sent to yet, and a folder that root owns needs root.

## Recommendation

Option 1 now, with the words above, and option 2 as a follow-up if
Donald wants D22's sentence to hold against every member. The window
is narrow (a member who sends to the same far name first, and then
moves files by hand), and nothing in tc moves another member's file.

## Ruling
