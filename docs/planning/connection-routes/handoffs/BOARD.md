# Handoff: BOARD (P4)

Model:  Claude Opus 5.5 (the BOARD lane agent)
Status: unreviewed
Date:   2026-10-14
Branch: Claude-Development-TheConnection-BOARD, from
        Claude-Development-TheConnection at 89bdd2e (after GROUND merged)
Where:  ~/TheConnection-lanes/board

## Commits

| Task | Commit | Subject |
|---|---|---|
| B1 | `13f924c` | Add the board feed: nodes, states, wires and links from the mailbox, with D7's roles and levels. |
| B2 | `834c39f` | Add the board server: 127.0.0.1 only, a token on /feed, a Host check, GET and HEAD, an allow list. |
| B3 | `36eab83` | Add patchBoard, layoutLevels and the doorbell and remote states to the board look. |
| B4 | `89a152c` | Add live.html, the live board page, and its human QA script with a grayscale pass. |
| B5 | `340ef4a` | Add the board's leak tests: 1,000 feeds under 2 MB of RSS, a pruned down map, 500 patches back to baseline. |
| B6 | `798b0bc` | Make the demo draw D7's shapes: two orchestrators side by side, one over a relay. |
| Follow-up | `f6365cd` | Give every helper the board lane added a doc block of its own. |
| Cross-lane fix | `d3e4051` | Send no test mail to a codex or ssh card, and stop calling health's keys a full list. |
| Handoff | the commit that adds this file | Write the BOARD handoff. |

No amend, reset or rebase. Nothing pushed or merged. `tc` and
`tests/_root.py` were not edited.

## What was built

**B1, `board/serve.py` (the feed) and `tests/test_board_feed.py`.**
`load_tc(root)` loads `tc` as a module the C5 way, with `TC_ROOT` set for
the load only and put back after. `Board(root, clock).feed()` returns C5's
object: `at`, `machine` (`load1`, `cores`, `mem_avail_pct`), `nodes`,
`wires`, `links`. The module doc block maps each feed key to the tc key
that feeds it. The machine keys match tc's one to one, so no C5 field
lacks a source in tc. Cards come straight from `cards/*.json`, never from
health. Messages come from file names under `mail/to-*/` and
`mail/to-*/read/`; ages come from a stat of the file. No body is opened.
Roles and levels follow C5 step by step: partners, a declared or inferred
parent (`HUB_MIN_PARTNERS = 2`), role and `role_source`, and a breadth
first level walk that breaks each `reports_to` cycle, so it ends on any
cycle. `last_listening_at` lives on the Board and is pruned past
`DOWN_WINDOW_S` on every call. 13 tests: the main feed test, the status
line, writing then idle, and every D7 shape in phases.md B1, plus a node
below a cycle, links from every message, and the reports_to and native
links.

**B2, the server in `board/serve.py`, and `tests/test_board_server.py`.**
`python3 board/serve.py [--port 8780]` binds 127.0.0.1, makes a token with
`secrets.token_urlsafe(24)`, prints
`board: http://127.0.0.1:<port>/live.html#token=<t>` once, and serves until
Ctrl+C or SIGTERM. `/feed` needs `X-TC-Token` (compared with
`hmac.compare_digest`), else 401 with no body. A foreign Host gets 421. Any
method but GET and HEAD gets 405, made-up methods too. Only C6's six files
are served; everything else is 404. No request log. Requests run on daemon
threads and `feed()` runs under one lock. 5 tests. **The server runs in the
test's own process, on a thread, on a port the OS picks:** the harness in
this tree has no `start(argv=...)` yet (a P0 fixer adds it on its own
branch), so no test starts `serve.py` as a child.

**B3, `board/look.js`, `board/theme.css`, `tests/board-patch.test.mjs`,
`tests/board-layout.test.mjs`.** A pure layer: `layoutLevels(feed)` (roots
side by side in name order, levels top to bottom, one column per leaf, no
overlap), `boardView(feed)` (what to draw), `diffBoard(prev, next)` (what
changed by id). `patchBoard(board, feed)` applies the diff through a kit:
`createKit(doc, canvas)` for the DOM, a fake in the tests, so no DOM
library is needed. Two states: `doorbell` (◎, double border) and `remote`
(⇄, `remote · not checked`, dotted border). Every title carries its role
word, and `· inferred` exactly when `role_source` says so; the role words
never shorten. Nodes are 208 by 60 (were 132 by 48) to hold that and a
status line. A fresh wire flows toward its reader with `from → to · #seq`;
`reports to` hints run from a child's top to its parent's bottom with
their words; `native · not observed` lines carry theirs. No `innerHTML`.

**B4, `board/live.html` and `qa/human/board-live.md`.** The page reads the
token from the fragment, asks `./feed` every `POLL_MS` (3000), numbers its
requests and drops any answer older than the one on screen, and draws with
`patchBoard`. It has the look switch, `?theme` and `?gray=1`, and says in
the pill when the token is missing or refused or the server is gone. On
`pagehide` it clears the timer, aborts requests in flight and disconnects
its ResizeObserver. **The human script is written, not run.** Donald runs
it; it includes a grayscale pass where every state, port and wire must
read.

**B5, `tests/test_board_leak.py` and `tests/board-leak.test.mjs`.** 1,000
`feed()` calls on one Board over 23 names and 43 messages with one proven
listener: VmRSS from `/proc/self/status` grows less than
`FEED_LEAK_LIMIT_KB` (2,048) and no file descriptor is left open. 1,000
names that each listen once, 6 s apart on a fake clock: `last_listening_at`
never holds more than one `DOWN_WINDOW_S` of them. 500 feeds that add and
remove nodes, then the first feed again: the board's maps, view and live
handles are back to their first counts and nothing removed is held.

**B6, `board/demo-script.json`, `board/demo.html`,
`qa/human/board-look.md`.** The demo script is in the feed's shape: `a`
over `b` and `docs`, `b` over `c` and `d`, and `z` over `y1` and `y2`,
which mails `a`. Every state shows. `demo.html` draws it with
`patchBoard`, one message per step. The human script follows the new demo
and gains the step: in `?gray=1` each orchestrator reads as one by its
word. **That step is written, not run.** Two checks in
`tests/board-layout.test.mjs`: two level 0 orchestrators (`a`, `z`) and
one level 1 (`b`) laid out side by side, and every state, line kind and
scripted wire present.

## What was not built

- No automated test drives `live.html` in a browser; there is no browser
  on this machine. "Newest answer wins" and the cleanup were checked in a
  scratch run only (below). B4's verify is the human script.
- No test for `main()` (the printed URL, SIGTERM). Checked by hand only.
- The README's board section still names four states and serves the demo
  on port 8765. README is the DOCS lane's file, so it was left alone.
- C5 rule 6 says the known limit goes in the README too. It is in
  `serve.py`'s doc block and pinned by a test; the README line is DOCS'.

## Assumptions

1. **State precedence** is C5's list order, first match wins (pause
   BOARD-1). A listening sender reads `listening`, not `writing`.
2. **A parent is always a node.** Declared needs it (C5); for an inferred
   parent the one partner must be a node too, or the walk has nowhere to
   hang the child. Partners themselves need not be nodes, and count toward
   `HUB_MIN_PARTNERS`.
3. **Breaking a cycle:** from the first-sorted unreached node, follow
   parents to the cycle; the cycle member that sorts first becomes the
   root. C5 says unreached nodes "sit on a cycle", but a node below a cycle
   is unreached and not on it; making it a root would draw it above its own
   parent. Pinned by `test_a_node_below_a_cycle_stays_below_it`.
4. **A `reports_to` naming no node, or the node itself,** gives no parent
   and stops inference for that node (C5: "gives no parent"). A self
   report draws no `reports_to` link.
5. **A name that only sends** (no inbox, no card) is no node, as C5's node
   list says. Its wires and links stay in the feed; the page draws no line
   with a missing end.
6. **`last_mail_age_s`** is health's `newest_mail_age_s`: mail the name
   received. `writing` uses the newest message the name sent.
7. **No card:** `kind` and `account` are null and `route` is `local`.
8. **`parent` added to each node** for `layoutLevels` (pause BOARD-3).
9. **Hand-written cards** in the tests and QA scripts use C1's fields;
   CARDS' code is not in this tree.
10. **The leak run's PATH** holds a fake `nvidia-smi` that prints one GPU
    line, so tc still starts a child every call but 1,000 calls take
    seconds. The other board tests call tc's health snapshot as it is,
    which runs the real `nvidia-smi` (a query) on this machine, as
    `tests/test_health.py` already does.
11. **`qa/human/board-look.md`** now serves the demo with `serve.py` on
    8780, since C6 says 8765 is taken on the owner's machine.

## Pauses

- `pauses/BOARD-1.md`: which state wins when two hold. Built to C5's list
  order.
- `pauses/BOARD-2.md`: an inferred parent can turn a declared one upside
  down (`b` reports to `z`, `z` mails only `b`, `x` also mails `b`: `z` is
  drawn under `b`). Built to C5 as written; recommends one guard in rule 2.
- `pauses/BOARD-3.md`: the feed adds `parent` to each node. Built.
- `pauses/BOARD-4.md`: C5 links every pair of Claude cards on account
  `unknown` as native. Built to C5 as written; recommends skipping
  `unknown`.

## Cross-lane notes

- **From CARDS' review** (applied in `d3e4051`): with CARDS' router in
  `tc`, a send to a name whose card says route `ssh` is refused (exit 1)
  and a send to a `codex` card rings `codex` (the harness refuses it). No
  board test now sends to such a name; the cards alone make those nodes,
  and mail that must touch them goes from them or is written by hand in
  tc's layout (a .tmp renamed, `mail/.seq` raised).
- `health_snapshot()` gains a `cards` key after CARDS merges. `serve.py`'s
  doc block no longer reads as the full list of health's keys, and
  `feed()` never reads `cards` from health.

## Mutations and their red runs

Each was applied by hand to a staged file, run, seen red, and restored;
`git diff --exit-code` was clean after every restore. Red lines are the
assertion line only; temp folder names are cut to `tc-test-XXXX`, and feed
bodies to `...`.

| Task | Test | Mutation | Red line |
|---|---|---|---|
| B1 | `test_states_pids_wires_and_down_with_unreadable_bodies` | `scan_messages` opens each body | `PermissionError: [Errno 13] Permission denied: '/tmp/tc-test-XXXX/root/mail/to-b/read/000003-from-a.md'` |
| B1 | `test_two_orchestrators_side_by_side` | one root: every parentless node after the first put at level 1 | `AssertionError: {'x':[69 chars]ed', 1, None), ...} != {'x':[69 chars]ed', 0, None), ...}` (`'y'` at level 1, expected 0) |
| B1 | `test_two_orchestrators_share_a_worker` | names as a list, so a name with an inbox and a card is drawn twice | `AssertionError: 8 != 6 : a node is drawn twice: ['a', 'a2', 'a2', 'b', 'b', 'x', 'x1', 'x2']` |
| B1 | `test_two_orchestrators_share_a_worker` | the busiest partner wins over the card | diff line `'b': ('worker', 'inferred', 1, 'x')`, expected `'b': ('worker', 'declared', 1, 'a')` |
| B1 | `test_a_reports_to_cycle_ends` | levels by climbing parents with no visited set | `AssertionError: True is not false : feed() did not return within 2 s` |
| B1 | `test_links_read_every_message_not_only_the_wires` | links built from the last 50 messages only | `AssertionError: 0 != 1 : no link for old1 and old2: [...]` |
| B2 | `test_the_socket_is_bound_to_loopback_only` | `BIND_HOST = "0.0.0.0"` | `AssertionError: '0.0.0.0' != '127.0.0.1'` |
| B2 | `test_feed_needs_the_token` | token check skipped | `AssertionError: Tuples differ: (200, b'{"at": ...') != (401, b'')` |
| B2 | `test_a_foreign_host_gets_421` | Host check skipped | `AssertionError: Tuples differ: (200, b'{"at": ...') != (421, b'')` |
| B3 | `patchBoard keeps what stays, ...` | `patchBoard` diffs against an empty view (rebuilds) | `a is a new object: the board was rebuilt` |
| B3 | `two roots sit side by side ...` | the layout cursor never moves between roots | `x's tree runs into y's` (4 of 8 layout tests red) |
| B5 | `test_last_listening_at_is_pruned_past_the_down_window` | prune skipped | `AssertionError: 1000 not less than or equal to 101 : last_listening_at reached 1000 names; one window holds 101` |
| B5 | `test_a_thousand_feeds_grow_rss_under_the_limit` | Board keeps every feed's nodes, wires and links | `AssertionError: 29696 not less than 2048 : VmRSS grew 29696 kB over 1000 feed() calls` |
| B5 | `500 feeds that add and remove nodes ...` | `patchBoard` never deletes removed nodes from its map | `nodes: 503`, expected `nodes: 2` |
| B6 | `the demo holds two level 0 orchestrators ...` | `z` demoted to worker in the script | `not ok 9 - the demo holds two level 0 orchestrators and one level 1 orchestrator, side by side` |

The first B5 RSS run did not catch the keep-every-feed mutant: with three
names it grew 1,536 kB and passed. The test's mailbox was grown to 23
names before B5 was committed; the line above is from that version. After
`d3e4051` changed the main test's and the leak test's mail, the body,
one-root, drawn-twice, under-the-mailer, links-from-wires and
keep-every-feed mutations were applied again: each red with the line
shown.

## Hand runs

Port 8766, a temp `TC_ROOT`, each server stopped by its own pid with
SIGTERM. Scratch drivers, not in the repo; the token was masked in all
output.

- `serve.py` on 8766: printed `board: http://127.0.0.1:8766/live.html#token=<token>`
  (token 32 characters); `/feed` with no token 401, `Host: evil.example`
  421, `POST /feed` 405, `/../tc` 404, `/mail/` 404, `/demo.html` 200,
  `/feed` with the token 200 (nodes, states, roles and wires as sent; the
  token not in the body); `ss -ltnp` showed only `127.0.0.1:8766`; exit 0
  on SIGTERM; nothing left on 8766.
- `live.html`'s script in Node with a fake DOM against `serve.py` on
  8766: the token went in `X-TC-Token`; `?gray=1` set the filter; the pill
  read `live · 0 listening`; titles `a · worker · inferred`,
  `b · orchestrator · inferred`, `c · worker · inferred`; the wire label
  `a → b · #5` appeared 1.9 s after a `tc send`; Node exited 0 ms after
  `pagehide`. With `clearInterval` removed from a copy of the script, Node
  never exited and was killed at 30 s.
- `demo.html`'s script in Node with a fake DOM: pill `4 listening · 1
  down`; all nine steps flowed in order, `c` and `y2` read writing on their
  own steps; no element was made after the first step; exit right after
  `pagehide`.
- The demo's cards and links, built into a temp mailbox and fed to
  `serve.py`'s `feed()`: every role, source, level, parent and link matched
  the script.

## Verify commands and their output

Run in `~/TheConnection-lanes/board` at `d3e4051`.

```
$ python3 -m unittest tests.test_board_feed -v
... 13 lines ending "... ok"
Ran 13 tests in 2.050s
OK
$ python3 -m unittest tests.test_board_server -v
... 5 lines ending "... ok"
Ran 5 tests in 2.531s
OK
$ python3 -m unittest tests.test_board_leak -v
... 2 lines ending "... ok"
Ran 2 tests in 13.909s
OK
$ node --test tests/*.test.mjs
# tests 25
# pass 25
# fail 0
(the summary's suites, skipped and todo lines, all 0, cut)
$ python3 -m unittest discover -s tests -p 'test_*.py'
Ran 45 tests in 30.274s
OK
```

Baseline at `89bdd2e`: discover 25 OK, node 8 pass. After: 45 (25 plus
13, 5 and 2) and 25 (8 plus 6, 10 and 1). The discover run prints the two
`ResourceWarning: unclosed file` warnings GROUND traced to
`tests/test_health.py`; under `python3 -X dev` the three board suites
print none.

`check_voice.py` and `check_american.py` were clean on
`qa/human/board-live.md`, `qa/human/board-look.md`, the four pause files
and this file.

## Not verified

- **The board in a browser.** No browser here. Layout, fit, fonts, colors,
  the grayscale pass, reduced motion and phone width are for Donald's
  human scripts, `qa/human/board-live.md` and `qa/human/board-look.md`,
  neither of them run.
- Anything with CARDS' `tc`: these tests ran against this tree's `tc`.
  The cross-lane fix follows CARDS' description of its router; it was not
  run against CARDS' branch.
- A real `codex` or `ssh` node: only hand-written cards.
- The server under a second local user, or reached through a real DNS
  rebinding page; the Host check is tested with a forged header.
- RSS over hours of real polling; the leak test covers 1,000 calls.
- `compare.html` (unchanged; it frames `demo.html`).
