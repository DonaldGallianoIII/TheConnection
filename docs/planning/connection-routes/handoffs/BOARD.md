# Handoff: BOARD (P4)

Model:  Claude Opus 5.5 (the BOARD lane agent); fix rounds 1 and 2 by
        Claude Opus 5.5 (the BOARD fixer), from
        audits/2026-10-14-1811-full/fixes/round-1.md and round-2.md, and
        a2's direction for the owner in round 2
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
| Handoff | `d250036` | Write the BOARD handoff. |
| Fix round 1 (a) | `062dec9` | Put the feed on D15's rules: writing first, no inverted edge, no native on unknown |
| Fix round 1 (b) | `280a200` | Make the board read at 14 names on a phone: wrap, keep text at 11 px, scroll down |
| Fix round 1 (c) | `6eafef6` | Poll one request at a time with a timeout, say stale in words, restart on pageshow |
| Fix round 1 (d) | `a2aa9c2` | Keep hostile files and slow clients from stalling the board's feed and server |
| Fix round 1 (e) | `d86f2f5` | Make the board's stale tags true, allow for the writing window in QA, settle the pauses |
| Fix round 2 (a) | `94a5dc1` | Make the board fill the screen, move the legend to the footer, wrap the pill and footer |
| Fix round 2 (b) | `880a304` | Route every wire round the boxes, and keep labels off boxes, wires and each other |
| Fix round 2 (c) | `bd23031` | Head each tree with its root, list the roots at the top, and draw an outline on a phone |
| Fix round 2 (d) | `6785fe0` | Add the board's browser check, and bring both QA scripts up to round 2 |
| Fix round 2 (e) | the commit that brings this file up to date | Describe fix round 2 in the BOARD handoff |

No amend, reset or rebase. Nothing pushed or merged. `tc`,
`tests/_root.py` and `board/serve.py` were not edited in round 2 (`tc` and
`tests/_root.py` in no round).

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
cycle. Since fix round 1 the feed follows D15: states in the order
writing, down, listening, doorbell, remote, idle (down needs no pid);
inference never inverts a declared edge; no native link on account
`unknown` (`ACCOUNT_UNKNOWN`); each node carries the parent the walk used,
so a cycle's root has none. A future mtime gives no age, so it never reads
as writing. Card and status files go through `read_regular` (O_NONBLOCK,
O_NOFOLLOW, regular files only), a card nested past the recursion limit is
skipped and named once on stderr, and one bad `to-*` entry skips only
itself. `last_listening_at` lives on the Board and is pruned past
`DOWN_WINDOW_S` on every call. 21 tests: the main feed test, the status
line, writing then idle, every D7 shape in phases.md B1 with a check that
each parent is the one the walk used, a node below a cycle, links from
every message, the reports_to and native links; round 1 added the D15
state order, the inversion in both name orders, account `unknown`, the
future mtime, and four hostile-mailbox tests.

**B2, the server in `board/serve.py`, and `tests/test_board_server.py`.**
`python3 board/serve.py [--port 8780]` binds 127.0.0.1, makes a token with
`secrets.token_urlsafe(24)`, prints
`board: http://127.0.0.1:<port>/live.html#token=<t>` once, and serves until
Ctrl+C or SIGTERM. `/feed` needs `X-TC-Token` (compared with
`hmac.compare_digest`), else 401 with no body. A foreign Host gets 421. Any
method but GET and HEAD gets 405, made-up methods too. Only C6's six files
are served; everything else is 404. No request log. Requests run on daemon
threads and `feed()` runs under one lock. Since round 1, `REQUEST_DEADLINE_S`
(10) bounds each whole request through `DeadlineSocket`, and at most
`MAX_CONNECTIONS` (16) are served at once; one past that is closed at once.
7 tests: the first 5, a trickling client dropped by the deadline, and a
connection past the cap closed at once. **The server runs in the
test's own process, on a thread, on a port the OS picks:** the harness in
this tree has no `start(argv=...)` yet (a P0 fixer adds it on its own
branch), so no test starts `serve.py` as a child.

**B3, `board/look.js`, `board/theme.css`, `tests/board-patch.test.mjs`,
`tests/board-layout.test.mjs`.** A pure layer: `layoutLevels(feed, width)`
(roots in name order, levels top to bottom, no overlap; since round 1 each
parent's children wrap into rows that fit the width, and on a phone, where
a row holds one box, they indent under their parent), `boardView(feed,
width)` (what to draw), `diffBoard(prev, next)` (what changed by id). `patchBoard(board, feed)` applies the diff through a kit:
`createKit(doc, canvas)` for the DOM, a fake in the tests, so no DOM
library is needed. Two states: `doorbell` (◎, double border) and `remote`
(⇄, `remote · not checked`, dotted border). Every title carries its role
word, and `· inferred` exactly when `role_source` says so; the role words
never shorten. Nodes are 208 by 64 (were 132 by 48) to hold that and a
status line. A fresh wire flows toward its reader with `from → to · #seq`;
`reports to` hints run from a child's top to its parent's bottom with
their words; `native · not observed` lines carry theirs, and on a pair that
also has mail they ride on the wire as a second label line under it
(`labelPoints`). No `innerHTML`. Since round 1 (a2's item for Donald): no
font-size in theme.css is under 11 px and `MIN_FIT_SCALE` is
`MIN_TEXT_PX / BOARD_TEXT_MIN_PX`, 1, so the board is never shrunk;
`createFit` lays it out at the canvas width from the ResizeObserver entry,
and the canvas scrolls down, never sideways. Every map keyed by session
name has no prototype, so `__proto__` lays out like any other name. A down
node's status reads `last status: ...`; the pill names down nodes `no
listener`, as their boxes do.

**B4, `board/live.html` and `qa/human/board-live.md`.** The page reads the
token from the fragment and draws each answer with `patchBoard`. Since
round 1 it asks `./feed` through look.js `createPoller`: one request at a
time, the next `POLL_MS` (3000) after the last settles, so an older answer
can never land after a newer one; a request still out after
`FETCH_TIMEOUT_MS` (2500) is aborted, and a late or failed answer turns the
pill to `stale · last answer N s ago · <why>` or `no answer · <why>`, never
`live`. It counts listeners by `listener_pid`. It has the look switch,
`?theme` and `?gray=1`, and says in the pill when the token is missing or
refused. On `pagehide` it stops the poller and the ResizeObserver; on a
`pageshow` from the back/forward cache it starts both again. **The human
script is written, not run.** Donald runs
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

## Fix round 2: the page as the owner reads it

The architect ran round 1's board in headless Chromium with 14 sessions.
The numbers passed; the screenshots did not read for the owner, who is
colorblind and reads the board on a phone. Round 2 fixed six items, and
a2's direction for the owner settled how (where it differed from the
brief, a2's won).

1. **The board fills the screen** (`theme.css` `.tc-win`, `.tc-canvas`;
   look.js `createFit`). The window is at least 100dvh less the page's
   margins; the board's frame grows to the board's height and the page
   scrolls, never sideways. createFit watches the stage's width and lays
   nothing out again when only the height changes.
2. **No wire passes through a box** (look.js routing section, `routeTree`,
   `routeAround`, `roundedPath`). One rule: every wire and connector is a
   run of level and upright pieces that never enters a node box. Ports
   follow the top-down levels (in on top, out on the bottom) and belong to
   the tree: a parent and child, the tree's thin connector and their mail
   on top of it, run port to port, turning only in gaps layoutLevels keeps
   empty (its new `via`). Every other pair joins a side of one box to a
   side of the other by A* over the lines ROUTE_CLEAR out from every box,
   port and heading, so two boxes in one row are joined straight across.
   A piece that shadows a connector costs ROUTE_ALONG_COST times its length.
3. **No label collides** (look.js `placeLabels`, `drawEdge`). No
   reports_to words on the board: the tree's connector has none, and the
   legend names the thin line; its words are in its hover title. A native
   line has none either. Only a flowing mail wire is labeled, beside its
   wire, never on it, clear of boxes, port rings, headings, wires and other
   labels, newest message first; one that cannot clear the wires may sit on
   one, on an opaque backing in a layer above every wire, and one that fits
   nowhere keeps its words in the wire's title.
4. **The legend never covers the board** (look.js `setFooter`,
   `LEGEND_WORDS`; theme.css `.tc-legend`). It is the footer's first row.
5. **The second orchestrator is reachable at a glance** (look.js
   `layoutLevels` heads, `rootsList`, `createRoots`, `createFit.jump`).
   Each root's tree starts with a heading as wide as the tree
   (`z · orchestrator · 4 sessions`), and a list at the top
   (`2 orchestrators: a, z · 2 peers: p1, p2`) brings each tree into view
   when a name is clicked or tapped.
6. **Nothing is cut off on a phone** (theme.css `.tc-conn`, `.tc-foot`,
   the 640 px block). The pill wraps and under 640 px takes a row of its
   own; the footer's cells wrap. The pill keeps the word `live`: a2 allowed
   dropping it, and with a row of its own it fits.

a2's phone view (look.js `outlineView`, the kit's `drawOutline`,
`createFit`): under OUTLINE_BELOW_PX of stage width (about a 600 px phone)
the page draws an outline instead of the graph: one group per root,
headed by it; one row per session, indented by level under its parent,
with its name, role words, state glyph and word, unread count and note;
then the recent traffic, one line per pair, newest first. No wires. Both
views come from the same feed.

`tests/board-browser-check.mjs` measures all of this in a real browser;
see Hand runs.

## What was not built

- `node --test` drives no browser. Since round 2,
  `tests/board-browser-check.mjs` opens `live.html` in headless Chromium
  (Playwright: set NODE_PATH to a Playwright install's node_modules), but
  it is a script run by hand, not part of `node --test`, and it skips
  without Playwright. The poll loop is look.js `createPoller`, tested on
  fake timers in `tests/board-patch.test.mjs`. B4's verify is still the
  human script.
- No test for `main()` (the printed URL, SIGTERM). Checked by hand only.
- The README's board section still names four states and serves the demo
  on port 8765, and since round 2 its look kit list is behind: createCanvas
  takes no HUD words now, and the live board draws routed edges (drawEdge),
  not drawWire. README is the DOCS lane's file, so it was left alone.
- C5 rule 6 says the known limit goes in the README too. It is in
  `serve.py`'s doc block and pinned by a test; the README line is DOCS'.

## Assumptions

1. **State precedence** is D15's order, first match wins: writing, down,
   listening, doorbell, remote, idle (pause BOARD-1, overruled). A
   listening sender reads `writing` for `WRITING_WINDOW_S`, then
   `listening`.
2. **A parent is always a node.** Declared needs it (C5); for an inferred
   parent the one partner must be a node too, or the walk has nowhere to
   hang the child. Partners themselves need not be nodes, and count toward
   `HUB_MIN_PARTNERS`.
3. **Breaking a cycle:** from the first-sorted unreached node, follow
   parents to the cycle; the cycle member that sorts first becomes the
   root. C5 says unreached nodes "sit on a cycle", but a node below a cycle
   is unreached and not on it; making it a root would draw it above its own
   parent. Pinned by `test_a_node_below_a_cycle_stays_below_it`. The
   cycle's root carries `parent: null` (D15).
4. **A `reports_to` naming no node, or the node itself,** gives no parent
   and stops inference for that node (C5: "gives no parent"). A self
   report draws no `reports_to` link.
5. **A name that only sends** (no inbox, no card) is no node, as C5's node
   list says. Its wires and links stay in the feed; the page draws no line
   with a missing end.
6. **`last_mail_age_s`** is health's `newest_mail_age_s`: mail the name
   received. `writing` uses the newest message the name sent.
7. **No card:** `kind` and `account` are null and `route` is `local`.
8. **`parent` added to each node** for `layoutLevels`: the parent the walk
   used (pause BOARD-3, settled by D15).
9. **Hand-written cards** in the tests and QA scripts use C1's fields;
   CARDS' code is not in this tree.
10. **The leak run's PATH** holds a fake `nvidia-smi` that prints one GPU
    line, so tc still starts a child every call but 1,000 calls take
    seconds. The other board tests call tc's health snapshot as it is,
    which runs the real `nvidia-smi` (a query) on this machine, as
    `tests/test_health.py` already does.
11. **`qa/human/board-look.md`** now serves the demo with `serve.py` on
    8780, since C6 says 8765 is taken on the owner's machine.
12. **Round 2: the tree's connector belongs to the child's node view**, not
    to the edge set. `tests/board-leak.test.mjs`, outside round 2's work
    set, pins the base feed's edges to `['mailbox:a>b']`; a connector edge
    would have broken it. As part of the child, the connector comes, goes
    and moves with it, and diffBoard compares it with the node.
13. **Round 2: `portPoint` keeps the look kit's side ports.**
    `tests/board-look.test.mjs`, outside the work set, pins them. The live
    board's top and bottom ports are `levelPort`, and createNode draws
    them with `levels`.
14. **Round 2: OUTLINE_BELOW_PX (560) is the stage's width**, the width
    createFit observes: about a 600 px viewport less the page's margins,
    the window's borders and the body's padding.

## Pauses

All four are settled by D15, and fix round 1 built each ruling.

- `pauses/BOARD-1.md`: which state wins when two hold. Overruled: the
  order is writing, down, listening, doorbell, remote, idle.
- `pauses/BOARD-2.md`: an inferred parent could turn a declared one upside
  down. Option 2 built: inference skips a node whose one partner's card
  reports to it.
- `pauses/BOARD-3.md`: the feed adds `parent` to each node. Option 1, with
  a cycle's root carrying `parent: null`.
- `pauses/BOARD-4.md`: native links on account `unknown`. Option 2 built:
  none.

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

Fix round 1, each applied by hand, run, seen red, and restored byte for
byte (a scratch helper compared the file before and after):

| Item | Test | Mutation | Red line |
|---|---|---|---|
| 1 | `test_state_order_follows_d15` | the old chain, listening first | diff line `'d1': ('doorbell', None)`, expected `'d1': ('down', None)`; `'w1': ('listening', 4242)`, expected `('writing', 4242)` |
| 1 | `test_state_order_follows_d15` | down without `not pid` | diff line `'l1': ('down', 4242)`, expected `('listening', 4242)` |
| 1 | `the pill counts listeners by pid, ...` | count by `state === 'listening'` | `text: 'live · 1 listening'`, expected `'live · 2 listening'` |
| 2 | `test_inference_never_inverts_a_declared_edge` | rule 2 with no D15 guard | (top z) diff line `'z': ('orchestrator', 'declared', 1, 'b')`, expected `0, None` |
| 3 | `test_no_native_link_on_account_unknown` | `is not None` filter only | extra `{'from': 'p', 'kind': 'native', 'to': 'q'}` |
| 15 | `test_a_message_from_the_future_is_not_writing` | `max(0, age)` | `AssertionError: 'writing' != 'idle'` |
| 18 | `test_a_node_below_a_cycle_stays_below_it` | cycle root keeps its edge | `AssertionError: 'q' is not None : p is a root at level 0 but carries parent q` |
| 4 | `fourteen names fit a desktop and a phone, ...` | layoutLevels ignores the width (the old one-column-per-leaf layout) | `star at 1152 px: hub runs from 1440 to 1648` |
| 4 | same | that layout and the old 0.2 floor | `star at 1152 px: the smallest text is drawn at 4.018134715025907 px` |
| 4 | `no font-size in theme.css is under MIN_TEXT_PX, ...` | `.tc-node-sub` back to 9 px | `under 11 px: .tc-node-sub 9px` |
| 6 | `a mailbox wire and a native line on one pair ...` | no fold | `two paths on one pair: the native dashes lie on the mailbox wire` |
| 6 | same | second line on the first | `the two label lines sit 0 px apart` |
| 7 | `nodes named __proto__, constructor and toString ...` | `pos` a plain `{}` | diff line `- '__proto__',` (missing from the keys) |
| 11 | `createFit takes the canvas size from the ResizeObserver entry, ...` | size from `getBoundingClientRect` | `a layout read after a patch` |
| 16 | `a down node's status reads as its last status, ...` | no prefix | `Expected values to be strictly equal` (`● listening` for `last status: ● listening`) |
| 19 | `the pill names down nodes in the word their boxes show` | the old word | `text: '1 listening · 1 down'`, expected `'1 listening · 1 no listener'` |
| 5 | `the poll loop asks one request at a time, ...` | no timeout | `a late request was never aborted` |
| 5 | same | a poll every POLL_MS whether or not the last settled | `a poll went out before POLL_MS had passed since the last one settled` |
| 5, 12 | `stop clears every timer and aborts the request in flight; ...` | stop leaves the deadline timer | `a timer outlived stop` |
| 12 | same | stop leaves the request in flight | `stop left the request in flight` |
| 8 | `test_a_card_nested_past_the_recursion_limit_is_skipped` | no `except RecursionError` | `RecursionError: maximum recursion depth exceeded while decoding a JSON array from a unicode string` |
| 9 | `test_one_bad_inbox_entry_skips_only_itself` | the whole-scan `try` | `AssertionError: Lists differ: [] != [('a', 'b'), ('b', 'a')]` |
| 10 | `test_a_fifo_card_or_status_does_not_block_the_feed` | a plain blocking open that follows links | `AssertionError: True is not false : feed() blocked on the FIFO at cards/pipe.json` (and at `status/a.md`) |
| 10 | `test_a_symlinked_status_or_card_is_not_followed` | same | `Lists differ: ['a', 'b'] != ['a'] : a symlinked card was read` |
| 13 | `test_a_trickling_client_is_dropped_at_the_deadline` | a timeout per read only | `AssertionError: unexpectedly None : a trickling client held its connection past 3 s` |
| 13 | `test_a_connection_past_the_cap_is_closed_at_once` | no cap | `AssertionError: None != b'' : a connection past the cap of 2 was held open` |

Fix round 2, each applied by hand to look.js, run, seen red, and restored
byte for byte (a scratch helper compared the file before and after). All
fifteen were run again at `6785fe0` with the lines below.

| Item | Test | Mutation | Red line |
|---|---|---|---|
| 1 | `createFit takes the canvas size from the ResizeObserver entry, ...` | the frame's height never set | `the frame does not grow to the board` |
| 1 | same | a height-only resize lays out again | `a height-only resize laid the board out again` |
| 2 | `no wire or connector enters a node box or a heading, ...` | routeAround ignores every box but its two ends | `mixed at 1152 px: mailbox:a>z enters b` |
| 2 | same | routeTree skips the gutter for a wrapped child | `mixed at 358 px: mailbox:a>docs enters b` |
| 2 | `a parent's mail runs down its connector, ...` | a parent and child mail through routeAround | `a's mail to b leaves the connector` |
| 2 | same | routeAround joins left sides only | `p1 to p2 bends: [...]` (six points) |
| 3 | `no label overlaps another label, a node box or a heading, ...` | placeLabels skips placed labels | `mixed at 358 px: "a → e1 · #8" is on "a → e3 · #10"` |
| 3 | same | placeLabels skips node boxes | `mixed at 1152 px: mailbox:p1>p2's label "p2 → p1 · #11" is on p1` |
| 5 | `the roots list names each root by role, ...` | no plural | diff line `words: '2 orchestrator'`, expected `'2 orchestrators'` |
| 5 | `each root's tree starts with a heading naming its root, ...` | no heading band | `a at 1152 px: the heading is not over the root's box and port` |
| outline | `the outline lists every session once, ...` | rows never indent | `b sits at depth 0, level 1` |
| outline | same | traffic oldest first | `not newest first` |
| outline | `createFit draws the outline under OUTLINE_BELOW_PX ...` | the breakpoint itself draws the outline | `560 px does not draw the graph` |
| outline | same | the outline drawn on every call | `an unchanged outline was drawn again` |
| 5 | same | a jump in the outline goes to the graph | diff: the `['outline', 'z']` entry missing |

The browser check, seen red under hand mutations of the page (theme.css
or look.js, each restored byte for byte):

| Mutation | FAIL lines |
|---|---|
| `.tc-win` back to a fixed `height: 560px` | `every session on screen (14): missing: z, y1, y2, y3, p1, p2` and `window at least the viewport less its margins: window 560 px, viewport 900 less 32 px` at 1280; at 390 `missing: y1, y2, y3` and the window line |
| `.tc-wire-label` at 10 px | `smallest text at least 11 px: 10.0 px at svg text: a → e1 · #13` |
| placeLabels skips node boxes | `no label over a label, a box or a heading (7 labels): label "p2 → p1 · #17" on p1; label "p2 → p1 · #17" on p2` |
| routeAround ignores every box but its two ends | `no wire through a node box (22 wires and connectors): mailbox:a>z through b` |
| `LAYOUT_COL_GAP: -100` | `no session box over another: b on docs; c on d; docs on e1; e1 on e2; e2 on e3; y1 on y2; y2 on y3` |
| `.tc-win` with `min-width: 600px` | at 390, `draws the outline view: data-view is graph` and `no sideways scroll: page 495 px in a 390 px viewport` |
| footer cells `nowrap` with `text-overflow: ellipsis` | `nothing cut off in the pill or the footer: tc-legend tc-legend-outline: ...` |

The first try at the window mutation only failed the height line: a
session clipped by the window's `overflow: hidden` still counted as on
screen. The check was changed to count a name cut off by a clipping
ancestor as missing, and the window mutation then failed both lines, as
shown. A first try at the sideways mutation (`width: 1180px`) failed
nothing because the window, a flex item, shrank back to 358 px: the page
had no sideways scroll to catch.

The first B5 RSS run did not catch the keep-every-feed mutant: with three
names it grew 1,536 kB and passed. The test's mailbox was grown to 23
names before B5 was committed; the line above is from that version. After
`d3e4051` changed the main test's and the leak test's mail, the body,
one-root, drawn-twice, under-the-mailer, links-from-wires and
keep-every-feed mutations were applied again: each red with the line
shown.

## Hand runs

Fix round 2: `NODE_PATH=<a Playwright install>/node_modules node
tests/board-browser-check.mjs`, Playwright 1.63, Chromium 153, on the
round 2 tree: `result: PASS` at 1280 x 900 (graph, 7 labels, 22 wires and
connectors, 4 headings) and 390 x 844 (outline), each server and listener
stopped by its own pid. The screenshots were looked at, in color and in
grayscale. `demo.html` was screenshot at 1280 and 390 by a scratch driver
(no console errors; graph and outline). Without NODE_PATH the check
printed `skipped: playwright not found` and exited 0.

Earlier rounds: port 8766, a temp `TC_ROOT`, each server stopped by its
own pid with SIGTERM. Scratch drivers, not in the repo; the token was
masked in all output.

- Fix round 1, `serve.py` on 8766: one printed line of the expected shape
  (token 32 characters), `/feed` without the token 401, with it 200 and
  C5's five keys (the token not in the body), `/live.html` 200,
  `Host: evil.example` 421, exit 0 on SIGTERM, port free after, nothing on
  stderr. A first try backgrounded a subshell, so its SIGTERM missed the
  server; the server was then found by port and stopped by its own pid.
- Fix round 1, `live.html` and `demo.html` scripts in Node with a fake DOM,
  a stub fetch and a fake ResizeObserver: at a 338 px canvas, 14 names
  (live) and 8 (demo) drawn at scale 1, x from 24 to 264 (live) and to 296
  (demo); the down node's note read `last status: ● listening`; the pair
  with mail and a native link showed both label lines, 25 px apart; on
  pagehide the observer stopped, and a persisted pageshow observed again
  and (live) asked for a new feed.

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

Fix round 2, run in `~/TheConnection-lanes/board` at `6785fe0`:
`node --test tests/*.test.mjs` 43 pass, 0 fail (36 plus 3 routing and
label tests and 4 roots, heading and outline tests); `python3 -m unittest
discover -s tests -p 'test_*.py'` 55 OK, with the two known
`ResourceWarning` lines from `tests/test_health.py`; the browser check
`result: PASS`. `check_voice.py` and `check_american.py` were clean on
`qa/human/board-live.md`, `qa/human/board-look.md` and this file.

Fix round 1, run in `~/TheConnection-lanes/board` before its last commit:
`tests.test_board_feed` 21 OK, `tests.test_board_server` 7 OK,
`tests.test_board_leak` 2 OK; discover 55 OK (45 plus 8 feed and 2 server
tests); `node --test tests/*.test.mjs` 36 pass (25 plus 3 layout and 8
patch tests). The run below is the lane's own, at `d3e4051`.

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

- **The board on a real phone and in other browsers.** The browser check
  is headless Chromium with an emulated viewport: no touch, no phone
  fonts, no Safari or Firefox. The human scripts,
  `qa/human/board-live.md` and `qa/human/board-look.md`, are written and
  not run.
- **The Daylight look and reduced motion in a browser.** The check opens
  the dark look only, with motion on. The Daylight pairs are checked as
  numbers by `tests/board-theme.test.mjs`; the outline's words sit on the
  card face (`--tc-panel`) so they use pairs that test checks.
- **Labels in another font.** A label's box is an estimate,
  LABEL_CHAR_W (7) px per character; JetBrains Mono at 11 px is about
  6.6. The browser check measures the drawn labels and found no overlap
  at 1280; a wider fallback font was not tried.
- **Routes on shapes other than the tested ones.** The node tests check
  three 14-name shapes at 1152 and 358 px, and the browser check one. A
  route never enters a box by construction, but how crowded the gaps get
  on other shapes (many wires between trees through one gap) was not
  measured. The graph between 560 and about 700 px of stage width (a
  small tablet) was not looked at.
- **Long wires on a phone** (round 1's item) no longer arise: a phone
  draws the outline, with no wires.
- **The demo at the window's 1180 px cap** draws `z`'s tree under `a`'s,
  now seen in a screenshot, with `z`'s heading and the roots list.
- Anything with CARDS' `tc`: these tests ran against this tree's `tc`.
  The cross-lane fix follows CARDS' description of its router; it was not
  run against CARDS' branch.
- A real `codex` or `ssh` node: only hand-written cards.
- The server under a second local user, or reached through a real DNS
  rebinding page; the Host check is tested with a forged header.
- RSS over hours of real polling; the leak test covers 1,000 calls.
- `compare.html` (unchanged; it frames `demo.html`).
