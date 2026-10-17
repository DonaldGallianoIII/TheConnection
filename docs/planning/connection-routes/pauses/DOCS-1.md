# DOCS-1: an empty text argument makes tc send wait on stdin

Model:  Claude Opus 5.5 (the DOCS lane agent), 2026-10-17
Status: unreviewed
Pause:  open. The docs do not depend on it: the README and both JOIN
        files say to leave the text off for stdin, never to pass `""`.

## What happens

`tc send --from a --to b ""` does not refuse as an empty message. An
empty text argument is falsy, so `read_body` (`tc:5725`) falls through to
`sys.stdin.buffer.read(...)`, as the doc block says ("reads stdin when
`message` is empty"). Then:

- with stdin at `/dev/null`, it reads nothing and refuses: `tc send:
  empty message`, exit 1, as the README's table says;
- with stdin open and idle, it waits until stdin closes.

The DOCS lane met the second case once, in its own agent session: a
command list that held `tc send --from a --to b ""` ran past the Bash
call's 120 s limit, was moved to the background, and the send was still
waiting on stdin when the lane killed it by its pid. A session that
sends with an empty shell variable (`"$reply"` before it is set) can hang
the same way until its Bash timeout, with nothing written.

## The question

Should an empty text argument (`""`) refuse at once, as an empty message,
instead of reading stdin?

## Options

1. **Refuse it.** In `read_body`, test `message is not None` instead of
   truthiness, so `""` is a text argument and refuses `tc send: empty
   message`, exit 1. A missing text argument (argparse gives None) still
   reads stdin. One line, plus a test that `tc send --from a --to b ""`
   with stdin held open exits 1 at once.
2. **Keep it, and say so.** The README's command table says to leave the
   text off for stdin; add that `""` reads stdin too.

## Recommendation

Option 1. Exit 1 is already the code for an empty message, so no exit
row changes, and a session's typo then fails in milliseconds instead of
holding its Bash call for minutes.
