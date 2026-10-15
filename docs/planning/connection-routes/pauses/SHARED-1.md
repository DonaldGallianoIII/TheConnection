# SHARED-1: a second user's first command needs write access to ROOT

Model:  Claude Opus 5.5 (the SHARED lane agent), 2026-10-14
Status: unreviewed
Pause:  open. Built to C4 as written (option 1); nothing else waits on it.

## The question

C4 has `tc init --shared --group <g>` set the group and mode on `mail/`,
`status/`, `cards/` and `outbox/` when they exist, and D16 says init
reaches only the folders there at the time. Init writes `ROOT/.shared`
and changes nothing about ROOT itself.

So on a fresh mailbox, the first user to run a command makes the folder
that command needs, inside ROOT. When that is the second Linux user, tc
needs write access to ROOT, which belongs to the first user. ROOT
defaults to the folder `tc` lives in, usually that user's git checkout,
mode 0755 or 0775 in the owner's own group. The second user's
`tc join b` then fails at the mkdir of `cards/`, with a Python
traceback, not words (make_folder lets the PermissionError out, as the
old `mkdir(parents=True)` did). Reasoned from the code, not run: the
harness has no second Linux user.

The second user also needs search access to ROOT and every folder above
it, and read access to `ROOT/.shared`. Recent Ubuntu releases make new
home folders 0750, so a mailbox under one user's home is out of reach
for another until someone opens it up. Nothing in C4 says who does
that, or how.

Should init make the shared folders, or should the docs tell the owner
to prepare ROOT?

## The options

1. **As built: init touches only what exists.** The README's shared
   section and `qa/human/route-shared.md` (DOCS, D4) tell the owner to
   put the mailbox where every user in the group can reach it, and to run
   init after `mail/`, `status/` and `cards/` exist (one `tc send`, one
   `tc status`, one `tc join` as the first user is enough), or to give
   ROOT group g and mode 2775 by hand.
2. **Init also makes `mail/`, `status/` and `cards/`** through
   make_folder, so they exist at 3775 in group g from the start. ROOT
   needs search access for the group, never write. `outbox/` stays the
   ssh route's to make. About three lines in `cmd_init`. The H1 test that
   asserts init on an empty root makes nothing would flip to assert the
   three folders.
3. **Init also gives ROOT group g and mode 2775.** It covers outbox/ as
   well, but it changes a folder C4 does not list, and with the default
   ROOT that is the user's git checkout.

Either way, tc could say the PermissionError in words (`tc: cannot make
<folder>: permission denied; see the shared mailbox section of the
README`) instead of a traceback.

## Recommendation

Option 2, plus the words for the PermissionError, and a line in the
README's shared section that ROOT and every folder above it need search
access for the group. It removes the trap for the owner's two-user
walk-through (D4) at the cost of three folders that do no harm. It needs
a ruling because C4 and D16 describe what init reaches, and a reviewer
could read them as forbidding it to make anything.
