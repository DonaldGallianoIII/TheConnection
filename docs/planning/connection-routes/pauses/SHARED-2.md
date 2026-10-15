# SHARED-2: a planted link as a message, and a FIFO at a lock, are outside D17's list

Model:  Claude Opus 5.5 (the SHARED lane agent), 2026-10-14
Status: unreviewed
Pause:  open. Not fixed: outside D17's named files. Nothing built waits
        on it.

## The question

D17 names the files tc opens by name: the wait, watch and inbox locks,
`mail/.seq`, `status/<name>.md` and the ring marker. Each now opens with
`O_NOFOLLOW`, and a link there is refused. Two holes of the same kind
remain under a shared mailbox, and neither is in the list.

**A symlink planted as a message.** An inbox is group-writable and not
sticky (it cannot be: `tc read` moves mail other users wrote). So any
member can put a symlink named like a message, `000099-from-x.md`, in
another user's inbox, pointing at a file only that user can read.
`tc peek`, `tc read` and `tc log` print a message with
`Path.read_text()`, which follows the link. Checked by hand on this
lane's branch at `5c4981c`, under a scratch `TC_ROOT`: a link in
`mail/to-b/` pointing at a file outside the mailbox, and `tc peek b`
printed that file's text, exit 0. For a person that is their own file on
their own screen. For an agent session it puts the file in its context,
next to words the planter wrote, which can ask it to send the text on.

**A FIFO planted at a lock's name.** `open_by_name` opens the inbox lock
and the wait and watch locks with `O_WRONLY`. A FIFO with no reader
blocks that open forever, so one member can hang every send to a name,
or keep another user's listener from starting. tc did the same before
this lane (`open(..., "a")`). The reads already guard against it:
`read_regular_file` opens with `O_NONBLOCK` and checks `S_ISREG`.

Should D17 cover these two?

## The options

1. **Leave them.** The shared mailbox trusts its group for these. Say so
   in the README's shared section.
2. **Read every message file through `read_regular_file`** (or with
   `O_NOFOLLOW` and an `fstat` check) in `show()`, so a link or a FIFO
   among the messages is named on stderr and not printed, as `tc status`
   now does. A message cap is needed for `read_regular_file`;
   `SEND_BODY_MAX_BYTES` plus the header line fits, under its own name.
   `tc read` still moves a link into `read/` (rename moves the link, not
   its target), which is harmless once nothing follows it.
3. **Add `O_NONBLOCK` and an `S_ISREG` check to `open_by_name`**, so a
   FIFO or a device at a lock's name is refused with words, exit 1, like
   a link.

## Recommendation

Options 2 and 3 together, as a D17 amendment: the first is the one path
left by which a member can make another user's agent read a file it
should not, and the second is about four lines in a function this lane
wrote. Each takes one test in `tests/test_shared.py` in the style of the
planted-link tests.
