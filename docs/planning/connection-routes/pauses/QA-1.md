# QA-1: the name QA mail is sent from

Model:  Claude Opus 5.5 (the QA lane agent), 2026-10-18
Status: unreviewed
Pause:  settled by a2 for the owner, 2026-10-18, option 1, and `qa` is reserved (D46)

## The question

C8 says events become mail to `<name>` through tc's own router (C2). The
router takes a sender as well as a recipient, and the sender becomes part
of every message's file name (`NNNNNN-from-<sender>.md`), its header
line, and a node on the board. `tc qa run` takes `--to <name>` and no
`--from`. Which name is QA mail from?

## Options

1. **A fixed name, `qa`.** Every QA mail reads `from qa`. The board
   draws one `qa` node that mails the session; `tc log` and `tc report`
   count it as a sender. Two mailboxes' QA mail looks the same, which is
   the point: it is the tool speaking, not a session.
2. **A `--from <name>` flag**, default `qa`. Lets a person who runs two
   QA streams to one session tell them apart by sender. C8's command line
   would gain a flag it does not list.
3. **The run id as the sender** (`qa-20261018-090000-1a2b`). Every run
   is its own node on the board, and a long project grows one node per
   walk, which buries the sessions.

## Recommendation

Option 1. Built that way: `QA_SENDER = "qa"` in `board/qa.py`, a valid
C0 name, used for every mail a run sends. The run id is already on each
mail's first line (`QA: run <id> ...`), so runs stay apart without a
node each. If a2 picks option 2, it is one argparse line in `tc` and one
argument through `main`.
