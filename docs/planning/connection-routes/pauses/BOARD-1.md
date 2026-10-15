# BOARD-1: which state wins when two hold at once

Model:  Claude Opus 5.5 (the BOARD lane agent), 2026-10-14
Status: unreviewed
Pause:  settled by D15 (2026-10-14). Overruled: the order is a2's, not
        the recommendation below. Built in fix round 1.

## The ruling (D15)

a2, for Donald, overruled option 1. When more than one state holds, the
first in this order wins: `writing`, `down`, `listening`, `doorbell`,
`remote`, `idle`. Writing comes first because nearly every session has a
listener, and the moving activity is the point of the board. A node shows
`writing` for `WRITING_WINDOW_S` after a send, then its standing state.

Built in `board/serve.py` (`Board.feed`). `down` also needs no pid now:
every live listener is in `last_listening_at` before the chain runs, so
the map alone would call each one down. `live.html` counts listeners by
`listener_pid` (look.js `pillText`), so a listener that is writing still
counts. `tests/test_board_feed.py` pins the order in
`test_state_order_follows_d15`, and the main feed test checks writing
inside the window and listening past it. B1's own test still reads
`listening`, `listening`: its feed's clock is moved past the window first.

The rest of this file is the question as first asked.

## The question

C5 defines six states for a node: `listening`, `writing`, `doorbell`,
`remote`, `down`, `idle`. A node can match more than one. A session with a
live `tc wait` that sent mail 3 s ago is both `listening` and `writing`. A
listener that died 5 s after it sent is both `writing` and `down`. C5 does
not say which one the feed reports.

B1's own test spec needs an answer. Its two listeners must read
`listening` while three messages move, and a listener cannot receive
unread mail (a `tc wait` exits when mail lands). So the listeners are the
ones sending, and they are inside the writing window.

## Options

1. **C5's list order, first match wins:** listening, writing, doorbell,
   remote, down, idle. A listening session never reads `writing`; the
   page still shows its traffic as a moving wire.
2. **Writing first:** writing, listening, doorbell, remote, down, idle.
   Matches the demo, where the sender flips to `✎ writing`. Fails B1's
   spec as written: its listeners would read `writing`.
3. **Down before writing:** listening, down, writing, and so on. A dead
   listener shows as dead at once, even while its last send is fresh.

## Recommendation

Option 1. It is the order C5 lists, it passes B1 as written, and the
moving wire already says who is writing. Built that way in
`board/serve.py`; `tests/test_board_feed.py` checks the listeners are
inside the writing window when they read `listening`.
