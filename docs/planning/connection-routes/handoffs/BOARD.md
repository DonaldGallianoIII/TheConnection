# Handoff: BOARD (P4)

Model:  Claude Opus 5.5 (the BOARD lane agent); fix rounds 1 to 4 by
        Claude Opus 5.5 (the BOARD fixer), from
        audits/2026-10-14-1811-full/fixes/round-1.md and round-2.md, a2's
        direction for the owner in round 2,
        audits/2026-10-14-2047-custom/fixes/round-3.md and
        audits/2026-10-14-2209-quick/fixes/round-4.md
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
| Fix round 2 (e) | `53b2f28` | Describe fix round 2 in the BOARD handoff |
| Fix round 3 (a) | `4cf941d` | Draw native pairs in words again, keep tree wires off their connectors, give each wrapping parent its own gutter |
| Fix round 3 (b) | `0937669` | Keep the space in titles, head no tree of one, name the quiet wire, add view hysteresis, say stale over the board, patch the outline in place |
| Fix round 3 (c) | `c6c7609` | Build the feed from the parts it needs so it never waits on nvidia-smi, make the card-read comment true, escape a nested card's name |
| Fix round 3 (d) | `253ddf1` | Make the browser check use tc join where it can, mask every line, stop its children on any exit, and check native words and the dotted wire |
| Fix round 3 (e) | `fd0739b` | Describe the board as it is in the handoff, and drop audit ids and round numbers from shipped comments |
| Fix round 4 (a) | `4994610` | Draw dotted and dashed wires over every solid one, on a knockout in the canvas's face |
| Fix round 4 (b) | the commit that brings this file up to date | Stop the browser check at its next await after a signal, clear both port rings, and make the doc tags and test headers true |

No amend, reset or rebase. Nothing pushed or merged. `tc` and
`tests/_root.py` were edited in no round. `board/serve.py` was not edited
in round 2. Round 3 edited one file outside its work set,
`tests/test_board_leak.py`, as Fix round 3 says. Round 4 edited nothing
outside its work set.

## What was built

**B1, `board/serve.py` (the feed) and `tests/test_board_feed.py`.**
`load_tc(root)` loads `tc` as a module the C5 way, with `TC_ROOT` set for
the load only and put back after. `Board(root, clock).feed()` returns C5's
object: `at`, `machine` (`load1`, `cores`, `mem_avail_pct`), `nodes`,
`wires`, `links`. The module doc block maps each feed key to where it
comes from: `at`, the listener pids and the mail counts from tc
(`tc.now_iso()`, `tc.listeners("wait")`, `tc.mailbox_summary()`); the
machine keys from serve.py's own `machine_now()`, which reads the load
average and `/proc/meminfo` with tc's `machine_stats` numbers and rounding
but no GPU query; cards straight from `cards/*.json`, never from
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
`DOWN_WINDOW_S` on every call. Since fix round 3 the feed's snapshot is
`Board.snapshot()`: `tc.now_iso()`, `machine_now()` (tc's load and memory
numbers without its GPU query), `tc.listeners("wait")` and
`tc.mailbox_summary()`, never `tc.health_snapshot()`, so a poll never
waits on nvidia-smi, scans no process list and reads each card once; a
nested card's file name is printed escaped. 23 tests: the main feed test,
the status line, writing then idle, every D7 shape in phases.md B1 with a
check that each parent is the one the walk used, a node below a cycle,
links from every message, the reports_to and native links; round 1 added
the D15 state order, the inversion in both name orders, account
`unknown`, the future mtime, and four hostile-mailbox tests; round 3 added
no GPU query in a feed and the escaped card name.

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
test's own process, on a thread, on a port the OS picks.** This lane
branch was cut before the harness gained `start(argv=...)`; the dev
branch's `tests/_root.py` has it, built for B2, so once BOARD merges a
test can start `serve.py` as a child by its own pid. No test does yet.

**B3, `board/look.js`, `board/theme.css`, `tests/board-patch.test.mjs`,
`tests/board-layout.test.mjs`.** As the board is now, after fix round 4. A
pure layer: `layoutLevels(feed, width)` (roots in name order, levels top
to bottom, no overlap; each parent's children wrap into rows that fit the
width, and where a row holds one box they indent under their parent; a
block whose children wrap starts them `LAYOUT_LANE` in and runs its
connectors down that lane, so no two parents share a gutter),
`boardView(feed, width)` (what to draw), `diffBoard(prev, next)` (what
changed by id). `patchBoard(board, feed, width)` applies the diff through
a kit: `createKit(doc, canvas)` for the DOM, a fake in the tests, so no
DOM library is needed. Two states: `doorbell` (◎, double border) and
`remote` (⇄, `remote · not checked`, dotted border). Every title carries
its role word (`a · orchestrator`, with its spaces), and `· inferred`
exactly when `role_source` says so; the role words never shorten. Nodes
are 208 by 64 (were 132 by 48) to hold that and a status line, and 16 px
taller (`BADGE_H`) per badge line. The tree draws its own thin connector
from a parent's out port (bottom middle) to each child's in port (top
middle), with no words on the board; its words (`b reports to a`, `d
under b · inferred from mail`) are its hover title, and a feed's
reports_to links draw nothing of their own. A parent and child's mail
wire, or native line, runs `TREE_WIRE_OFFSET` (12 px since fix round 4,
8 before) beside that connector, never on it, clear of both port rings, so the connector never fills a dotted or dashed
wire's gaps; every other pair is routed side to side round the boxes.
Since fix round 4 the wire layer paints solid wires, then dashed ones
(flowing mail, native lines), then dotted ones (no listener), each in its
own group (`WIRE_LAYERS`), and a dotted or dashed wire has a knockout
under it, the same run in the canvas's face and one quiet wire wider
(`--tc-wire-w-knockout-pad`), so nothing but the canvas shows in its gaps
wherever another wire lies along it. A
fresh wire flows toward its reader with `from → to · #seq` beside it,
never on it; a quiet one is a thicker solid line with no words. Both boxes
of a native pair carry a dashed badge in words, `native with <the other> ·
not observed`, with mail or without and never on account `unknown`; a
native pair with no mail is joined by a long dash as well, with no words
on the line. A reports_to cycle's root carries `reports to <name> ·
cycle`, and a reports_to that names no node is its node's note. No
`innerHTML`. No font-size in theme.css is under 11 px and `MIN_FIT_SCALE`
is `MIN_TEXT_PX / BOARD_TEXT_MIN_PX`, 1, so the board is never shrunk;
`createFit` lays it out at the stage's width from the ResizeObserver
entry, the frame grows to the board's height and the page scrolls down,
never sideways. Under `OUTLINE_BELOW_PX` (560) of stage width it draws the
outline instead, and the graph again only from `GRAPH_FROM_PX` (584). Every
map keyed by session name has no prototype, so `__proto__` lays out like
any other name. A down node's status reads `last status: ...`; the pill
names down nodes `no listener`, as their boxes do.

**B4, `board/live.html` and `qa/human/board-live.md`.** The page reads the
token from the fragment and draws each answer with `patchBoard`. Since
round 1 it asks `./feed` through look.js `createPoller`: one request at a
time, the next `POLL_MS` (3000) after the last settles, so an older answer
can never land after a newer one; a request still out after
`FETCH_TIMEOUT_MS` (2500) is aborted, and a late or failed answer turns the
pill to `stale · last answer N s ago · <why>` or `no answer · <why>`, never
`live`; since round 3, once a board is drawn, a line over it reads `stale ·
last answer N s ago` and every flowing wire stops until the next good
answer. It counts listeners by `listener_pid`. It has the look switch,
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

## Fix round 3: what the second review found

The review of rounds 1 and 2 (`audits/2026-10-14-2047-custom`, FIX THEN
SHIP) found three places where a non-color cue or a readable tree was
lost, and LOWs. a2 had approved the look for the owner (the tree on a
desktop, the outline on a phone); round 3 kept it.

1. **Native pairs say so in words again** (MEDIUM-1; look.js `badgesOf`,
   `createNode`'s badges, theme.css `.tc-node-badge`, `.tc-row-badge`).
   Round 2 had left `native · not observed` in a hover title only, and
   nowhere on a pair that also mails or on a phone. Both boxes of a native
   pair now carry `native with <the other> · not observed` in a dashed
   badge, with mail or without, and the outline puts the same words under
   each row. Never on account `unknown` (D15): the page draws neither
   badge nor line there. A box is `BADGE_H` taller per badge, and the
   layout, ports and routing use its real height.
2. **A tree wire never lies on its connector** (MEDIUM-2; look.js
   `offsetRun`, `routeTreeWire`). A parent and child's mail wire, or native
   line, runs `TREE_WIRE_OFFSET` (8 px) beside the connector, on the side
   the connector turns toward first, so a down worker's dotted wire keeps
   its gaps. Wires between other pairs keep off these wires as they keep
   off connectors.
3. **Each wrapping parent has its own gutter** (MEDIUM-3; look.js
   `layoutLevels`). A block whose children wrap starts them `LAYOUT_LANE`
   in and runs its connectors down that lane, so a relay and its sub-relay
   never share a trunk.
4. **The rest**: titles keep their spaces (`a · orchestrator`); the phone
   outline draws no heading over a tree of one; the legend names the quiet
   wire (`thick line: mail, none in the last 10 s`) and says the thin line
   is `reports to, or inferred from mail`; a cycle's root shows its
   reports_to on a badge; the graph and outline switch has two
   breakpoints; a stale feed puts `stale · last answer N s ago` over the
   board and stops the moving wires; the outline is brought up to date in
   place; the feed never waits on nvidia-smi (serve.py `Board.snapshot`);
   the card-read comment and @complexity hold against the merged tc; a
   nested card's name is printed escaped; the browser check uses `tc join`
   where it can, masks every line, stops its children on SIGTERM, SIGINT
   and any throw, starts serve.py under a time limit, checks the native
   words and the dotted wire, and has a `--self-test`; the QA scripts and
   this file name no path from the owner's other projects; shipped
   comments carry no audit ids, round numbers or a2.

**Out of the work set.** `tests/test_board_leak.py` was not in round 3's
work set. Its prune test swapped `tc.health_snapshot` for a stand-in,
which item 12 (the feed built from parts) makes a no-op, so the test
failed (`'n999' not found in {}`). It now swaps `Board.snapshot`, and its
doc lines about the snapshot's child process are made true. No assertion
changed. For the architect to accept or send back.

**Known limits.**
- Two children on one side of a parent share the parent's end of their
  wires, as their connectors share theirs. Since fix round 4 a dotted or
  dashed wire is painted over every solid one on a knockout, so its
  pattern reads there (fix round 4, item 1); the solid wire it covers is
  hidden along the shared stretch and shows again where it turns off, and
  of two dashed wires on one stretch the later drawn shows. A dotted wire
  is always on top. A lane per child does not fit the 56 px gap under a
  parent with many children.
- Every parent and child pair with mail now draws two lines, the thin
  connector and the mail wire beside it. The tree's shape is as approved.
- Dev C5 said the feed is built from `health_snapshot()`. The architect
  amended it on the dev branch at `e3c1333` to the parts of tc's health
  the feed reads, as built here.

## Fix round 4: what the third review found

The review of round 3 (`audits/2026-10-14-2209-quick`, FIX THEN SHIP)
found one MEDIUM and LOWs. The look the owner approved is kept.

1. **A dotted wire reads dotted whatever lies along it** (MEDIUM-1;
   look.js `WIRE_LAYERS`, `wireLayer`, `drawEdge`, `createCanvas`;
   theme.css `.tc-knockout`, `--tc-wire-w-knockout-pad`). Siblings on one
   side of a parent share the parent's end of their tree wires, so a quiet
   sibling's solid wire filled a down worker's dots and the wire read
   solid. The wire layer now paints three groups in order: solid, dashed
   (flowing mail, native lines), dotted (no listener). A dotted or dashed
   wire sits on a knockout: the same run in the canvas's face, one quiet
   wire wider. So nothing but the canvas shows in its gaps, whatever the
   shape, and that holds by construction, not by layout. The cost: a solid
   wire under it is hidden along the shared stretch and shows again where
   it turns off. The browser check now has two down workers: `d`, as
   before, and `e2`, whose wire shares a stretch with `a`'s quiet wire to
   `b` and its flowing wire to `e3`. It reads each down wire's pixels from
   a screenshot taken with the animations stopped.
2. **The browser check stops at its next await after a signal** (LOW-1).
   check() and runView call `halt()` after each await; once a signal has
   begun cleanup it throws, and nothing more is printed. The exit code
   stays 128 plus the signal. Two new self-test runs prove it, with a fake
   browser launch that settles only on SIGTERM, then SIGINT.
3. **Tree wires clear both port rings** (LOW-2; look.js
   `TREE_WIRE_OFFSET`, 8 to 12). A ring is placed from its box's padding
   edge, so its center sits one border right of and below its port. 6 +
   1.25 + 4 (a doorbell's border) is 11.25, so 12 clears both rings at
   every border. At 8 the east ring covered up to 3.25 px of the wire.
4. **Doc tags and words made true** (LOW-3, LOW-4, LOW-6 to LOW-10):
   look.js's module block (createPoller's three callbacks, outlineView's
   O(n log n + l + r log r), the outline patched in place); serve.py's
   opening lines and `@deps` (the feed from its parts, never
   `health_snapshot()`; `/proc` read here and through tc); B1, B2 and
   assumption 9 here; the headers of `tests/test_board_feed.py`,
   `tests/test_board_leak.py` (its stand-in now returns Board.snapshot's
   four keys) and `tests/test_board_server.py`.

**Where this round differs from its brief.**
- Item 7 asked that `tests/test_board_feed.py`'s header say its cards are
  written by `tc join` when the tree's tc has it. They are not: every
  card there is written by hand, some are codex and ssh cards that a join
  cannot write, and the file never calls join. The header says that, and
  why. Moving its claude cards to `tc join` would change the tests, so it
  is left for the architect.
- `qa/human/board-live.md` was out of this round's work set, and its
  browser check lines then said five listeners and `d` down only. The
  architect brought them up to date at the merge (`7daf64a`): six
  listeners, `d` and `e2` down, both wires' gaps read in pixels.

## What was not built

- `node --test` drives no browser. Since round 2,
  `tests/board-browser-check.mjs` opens `live.html` in headless Chromium
  (Playwright: set NODE_PATH to a Playwright install's node_modules), but
  it is a script run by hand, not part of `node --test`, and it skips
  without Playwright. The poll loop is look.js `createPoller`, tested on
  fake timers in `tests/board-patch.test.mjs`. B4's verify is still the
  human script.
- No test for `main()` (the printed URL, SIGTERM). Checked by hand only.
  This lane's harness cannot start a script other than tc; the dev
  branch's can (`start(argv=...)`), so after the merge such a test is a
  choice, not a gap the harness forces.
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
9. **Cards in the tests and QA scripts.** The unit tests and the human
   QA scripts write their cards by hand in C1's shape, on any tc (some
   are codex and ssh cards, which `tc join` cannot write without a real
   Codex thread or `tc card`). The browser check writes its cards with
   `tc join` when the tree's tc has it, as the dev branch's tc does since
   CARDS merged, and by hand otherwise; it says which.
10. **The leak run's PATH** holds a fake `nvidia-smi` that prints one GPU
    line. Since round 3 feed() never runs it (Board.snapshot takes no GPU
    reading); one direct `tc.machine_stats()` call proves it is there.
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

Fix round 4, each applied by hand at the round's last state, run, seen
red, and restored byte for byte (a scratch helper compared the file's
sha256 before and after):

| Item | Test | Mutation | Red line |
|---|---|---|---|
| 1 | `a relay over w1 to w4 it has mailed, w2 down, ...` | the knockout never drawn | `the down wire has no knockout right under it` |
| 1 | browser check | the same | `FAIL  the down worker's wire (mailbox:a>e2) is dotted and shows only the canvas in its gaps (778 px read, longest ink 227 px, longest gap 4 px): ...; painted over it: nothing; knockout: none; ...` (and `mailbox:b>d`: `knockout: none`) |
| 1 | `a relay over w1 to w4 it has mailed, w2 down, ...` | the dotted layer painted first | `drawn over the down wire: mailbox:a>w1, mailbox:a>w3, mailbox:a>w4` |
| 1 | browser check | the same | `FAIL  the down worker's wire (mailbox:a>e2) ... (778 px read, longest ink 9 px, longest gap 4 px): ...; painted over it: mailbox:a>b, mailbox:a>docs, ... native:e2>e3; ...` (and `mailbox:b>d` for its paint order) |
| 2 | browser check `--self-test` | `halt()` does nothing | `FAIL  nothing printed after the signal but the stop line: printed after it: browser: chromium fake (self-test)` (SIGTERM and SIGINT runs) |
| 3 | `a tree wire clears both port rings at the widest node border ...` | `TREE_WIRE_OFFSET` back to 8 | `a tree wire's inner edge is 6.75 px from its port and the east ring reaches 10 px` |
| 8 | `test_last_listening_at_is_pruned_past_the_down_window`, with its new stand-in | prune skipped | `AssertionError: 1000 not less than or equal to 101 : last_listening_at reached 1000 names; one window holds 101` |

Fix round 3, each applied by hand, run, seen red, and restored byte for
byte (a scratch helper compared the file's sha256 before and after):

| Item | Test | Mutation | Red line |
|---|---|---|---|
| 1 | `both boxes and both outline rows of a native pair say ...`, `a mailbox wire and a native line on one pair ...` | no native badge on a pair that also mails | `a pair that mails lost its native badges`; `the graph's badges` |
| 1 | browser check | the same | `FAIL  each native pair says native with the other, not observed (p1, p2, e2, e3): p1 shows [], not ["native with p2 · not observed"]; ...` |
| 2 | `a parent's mail runs beside its connector ...` | routeTreeWire returns routeTree's run | `mixed at 1152 px: mailbox:a>b lies on its connector at {"x":506,"y":[116,144]}` |
| 2 | browser check | the same | `FAIL  the down worker's wire (mailbox:b>d) is dotted and no other stroke lies on it: class "tc-wire kind-mailbox flow down", dasharray 2px, 5px; the longest stretch under another stroke is 167 px (tree:d)` |
| 3 | `every connector trunk serves one parent: ...` | no lane for a wrapping block | `at 1152 px: the connector to x (under a) and to b5 (under b) share {"x":24,"y":[264,376]}` |
| 5 | `the outline lists every session once, ...` | a heading over every tree | `the one-session tree p1 is headed "p1 · peer · inferred"` |
| 8 | `a reports_to cycle's root says whom it reports to, ...` | no cycle badge | `the cycle's root hides its reports_to` |
| 9 | `the switch between graph and outline has two breakpoints, ...` and the createFit outline test | one breakpoint | `a scrollbar coming and going flipped the view`; `560 px flipped the outline back to the graph` |
| 10 | `once a board is drawn, a late or refused answer says stale ...` | no onStale on a failure | `a late answer did not say stale over the board` |
| 11 | `the outline is brought up to date in place: ...` | a new row element on every draw | `an age tick made new elements or moved old ones` |
| 12 | `test_a_feed_runs_no_gpu_query` | feed() from `tc.health_snapshot()` | `AssertionError: True is not false : feed() ran nvidia-smi` |
| 14 | `test_a_nested_card_is_named_escaped_on_stderr` | the name printed raw | `AssertionError: '\x1b' unexpectedly found in "serve.py: skipped cards/deep\x1b[2J.json: nested past Python's recursion limit" : ...` |
| 17 | browser check `--self-test` | the catch prints `err.message` unmasked | `FAIL  no token printed: an unmasked token= is in its output` |
| 17 | same | masked() without the g flag | `FAIL  no token printed: an unmasked token= is in its output` |
| 18 | same | no SIGTERM or SIGINT handler | `FAIL  serve.py started and is gone: serve.py pid N is still alive` |
| 18 | same | a throwing browser close skips the stop loop | `FAIL  serve.py started and is gone: serve.py pid N is still alive` |
| 18 | same | serve.py started with no alarm | `FAIL  serve.py ended at its own limit: serve.py pid N outlived its 4 s limit` |

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

Fix round 4: `NODE_PATH=<a Playwright install>/node_modules node
tests/board-browser-check.mjs`, Playwright 1.63, Chromium 153, on this
round's last state: cards by hand (this tree's tc has no join), six
listeners proven, `d` and `e2` made down through the feed, `result: PASS`
at 1280 x 900 (graph, 7 labels, 23 wires and connectors, 4 headings; the
down wires read 112 px and 778 px, longest ink run 3 px, longest gap 5
px) and 390 x 844 (outline), each server and listener stopped by its own
pid. The same check on a scratch copy of this round's board and check
beside the dev branch's `tc` at `e3c1333`: `cards: written by tc join`,
the same rows, `result: PASS`; its 14 cards carry no session id, pid or
thread id. `node tests/board-browser-check.mjs --self-test`: `self-test:
PASS` (seven runs against the fake Playwright), nothing left running.
Both runs' 1280 screenshots were looked at in grayscale, and an earlier
run of the same drawing code in color too: both down wires read dotted
along their whole run, `a`'s quiet wire to `b` and its flowing wire to
`e3` show where they turn off `e2`'s, and the tree wires clear both port
rings at 12 px.

Fix round 3: `NODE_PATH=<a Playwright install>/node_modules node
tests/board-browser-check.mjs`, Playwright 1.63, Chromium 153, at
`253ddf1`: cards by hand (this tree's tc has no join), five listeners
proven, `d` made down through the feed, `result: PASS` at 1280 x 900
(graph, 7 labels, 23 wires and connectors, 4 headings) and 390 x 844
(outline), each server and listener stopped by its own pid. The
screenshots were looked at in color and in grayscale. `node
tests/board-browser-check.mjs --self-test`: `self-test: PASS` (five runs
against the fake Playwright), nothing left running. The same check, on a
scratch copy of this round's board and check beside the dev branch's `tc`
at `1bede2c`: `cards: written by tc join`, `result: PASS`; its cards carry
no session id or pid. `demo.html` was screenshot at 1280 and 390 by a
scratch driver (no console errors; badges on `b` and `docs`).

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

Fix round 4, run in `~/TheConnection-lanes/board` before its last commit:
`node --test tests/*.test.mjs` 52 pass, 0 fail (50 plus 2 layout tests);
`python3 -m unittest discover -s tests -p 'test_*.py'` 57 OK.
`check_voice.py` and `check_american.py` were clean on this file.

Fix round 3, run in `~/TheConnection-lanes/board` before its last commit:
`node --test tests/*.test.mjs` 50 pass, 0 fail (43 plus 4 layout and 3
patch tests); `python3 -m unittest discover -s tests -p 'test_*.py'` 57
OK (55 plus 2 feed tests). `check_voice.py` and `check_american.py` were
clean on `qa/human/board-live.md`, `qa/human/board-look.md` and this file.

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
- Anything with CARDS' `tc`, but the browser check: the unit suites ran
  against this tree's `tc`. The browser check ran beside the dev
  branch's `tc` on a scratch copy, `tc join` path included, and passed:
  once in round 3 (`1bede2c`) and once in round 4 (`e3c1333`).
- Round 4's pixel check: it reads the dark look only, at 1280 x 900, and
  leaves out 28 px at each end of a down wire (its arrowhead and the port
  rings) and any point under a box, a port or a label; there the paint
  order and the knockout are checked, not pixels. Two dashed wires on one
  stretch (the later drawn shows) and a native line's knockout were not
  read in pixels. The Daylight knockout uses the same token as the
  Daylight canvas, checked as text only.
- Round 3 in a real browser beyond the check: the stale line and the
  stopped wires (node test and CSS rule only; QA step 22 looks at them),
  the outline patched in place (a fake document in the node test; no
  selection or screen reader was tried), and the two breakpoints with a
  real classic scrollbar (fake observer only).
- A badge's names in another font or with many partners: the names part
  shortens with an ellipsis and the whole text is the badge's title; the
  check measured only `p1`, `p2`, `e2` and `e3`.
- A real `codex` or `ssh` node: only hand-written cards.
- The server under a second local user, or reached through a real DNS
  rebinding page; the Host check is tested with a forged header.
- RSS over hours of real polling; the leak test covers 1,000 calls.
- `compare.html` (unchanged; it frames `demo.html`).

## P4 phase fix

Model:  Claude Opus 5.5 (the P4 phase fixer), 2026-10-15
Status: unreviewed
Brief:  audits/2026-10-14-2344-full/fixes/round-1.md, from that audit's
        synthesis (the ids below are its ids)
Branch: Claude-Development-TheConnection-P4FIX, from the dev branch at
        86f2061, in ~/TheConnection-lanes/p4fix

| Part | Commit | Subject |
|---|---|---|
| (a) item 1 | `a48f3db` | Take every inferred edge on a cycle out before roles and levels |
| (b) item 2 | `3f01a97` | Read a listener that mail woke as working or woken, never down (D24) |
| (c) items 3, 4 | `ea493c1` | Keep routed runs between polls, and wrap long names in the phone outline |
| (d) items 5, 6, 20 | `986bdfa` | Ship the board's two faces, and make the browser check prove the root jump |
| (e) items 7 to 14 | `9095578` | Harden serve.py's feed and refusals, and name an unknown count and a damaged token |
| (f) items 15 to 19 | the commit that adds this section | Make the board's words, tags and test names true, and keep the stale line in view |

No amend, reset or rebase. Nothing pushed or merged. `tc`,
`tests/_root.py`, `CLAUDE.md`, `README.md` and the plan files were not
edited. Above this section only the line about `qa/human/board-live.md`
under Fix round 4 changed (item 15).

**What changed, item by item.**
1. HIGH-1. `board/serve.py` drop_inferred_cycles and hierarchy: every
   inferred edge on a cycle is taken out before roles_of and levels_of
   read the parents; a cycle made only of cards keeps its break at the
   first name.
2. MEDIUM-1, D24. serve.py after_listening and WOKEN_GRACE_S (120):
   `down`, `woken` or `working` for a name seen listening and not
   listening now; tc's POLL_SECONDS is the slack for the wake. look.js
   STATES gains `◔ working` and `△ woken · not read`; the pill counts
   woken as a warning; a woken or down node's status reads `last
   status:`; both legends carry the line on the one case it cannot see;
   theme.css gives woken a heavier solid border and bold words. The demo
   shows both (`b` working, `y1` woken).
3. MEDIUM-2. look.js createRouteCache, drawnKey, boardView's `routes`
   and patchBoard's skip; routeAround keeps one flag per grid edge.
4. MEDIUM-3. theme.css `.tc-row-title`, `.tc-row-role`,
   `.tc-group-head`, `.tc-root-btn` wrap inside the window.
5. MEDIUM-4. tests/board-browser-check.mjs jumpToZ: z's heading out of
   view at a 400 px viewport first, a dispatched click, then a scroll and
   the heading in view.
6. D26. board/fonts/ holds the four woff2 subsets and the two licenses
   as fetched (sha256 matched the brief's list); theme.css declares them
   with @font-face; serve.py's allow list has the six files by exact key,
   and STATIC_PATHS builds every path from its key.
7. LOW-2. serve.py Board.snapshot asks mailbox_summary once more on
   FileNotFoundError.
8. LOW-3. serve.py: `unread` may be null, with tc's `mail_problem` in a
   new node key, `unread_problem`, only beside a null (a counted inbox
   with a problem keeps its count and no reason); `last_mail_age_s` is
   never under 0. look.js unreadWords: `unread unknown`.
9. LOW-4. serve.py scan_messages and message_names: no linked folder is
   listed (O_NOFOLLOW, O_DIRECTORY) and only regular files count.
10. LOW-5. serve.py load_tc compiles tc's source in memory; no bytecode
    cache is read or written.
11. LOW-8. serve.py FeedHandler.send_error: every refusal is empty.
12. LOW-13. serve.py scan_messages keys messages by recipient and number.
13. LOW-14. serve.py BoardServer.handle_error: one line, no traceback.
14. LOW-15, LOW-16. serve.py main refuses `--port 80` (exit 2, in
    words); look.js tokenProblem and CONN_WORDS.tokenDamaged, used by
    live.html.
15. LOW-6, LOW-7. The header of tests/test_board_server.py, the line
    above in this file, qa/human/board-live.md's new inbox line,
    tests/test_board_feed.py's router lines (and one in
    tests/test_board_leak.py), and every review-process comment in the
    board tests.
16. LOW-18, LOW-19. theme.css: `.tc-win` clips with `overflow: clip`, so
    `.tc-stale` sticks to the top of the screen; the legend, the theme
    comment and both QA scripts say dash-dot.
17. LOW-21, LOW-22. tests/test_board_feed.py's main test takes its clock
    from the message files' own times; the browser check settles on the
    window saying live and two animation frames, and SETTLE_MS is gone.
18. LOW-11, LOW-12, LOW-17, LOW-29. feed()'s @alloc names the per-message
    pair and count dict; the routing @complexity carries the real sizes
    and the cache (in part (c)); layoutLevels says when the extent can
    pass the width; load_tc names five paths and the in-memory compile
    (in part (e)).
19. LOW-25, LOW-26. createFakeKit, createFakeDoc, createPollerRig;
    assert_nodes.
20. The browser check, headless with this tree's tc: green after item 6
    with the request watch on, and twice more on the final code;
    `--self-test` green.

**Measured (item 3).** On this machine with Node 22 and look.js run
alone: the first draw of 20 Claude peers on one account (190 native
lines, every one routed) took 127 to 149 ms at load 0.5 and 191 to 213 ms
at load 16, against the test's FIRST_DRAW_BUDGET_MS of 2,000. Before the
grid edge flags it took 175 ms at load 0.5. A poll that only aged the
mail took 150 ms before (190 searches again) and 0.04 to 0.07 ms after.
On the 14-name test feed at 1152 px: X 79 and Y 101 lines, b 46
obstacles, a 64 pieces kept off, g 31,916 states; each search popped the
same states before and after, so the routes are the same.

**Mutations and their red lines.** Each applied by hand, seen red,
restored; the assertion line only.
- 1, the old cycle break (no drop_inferred_cycles): `AssertionError:
  {... 'zed': ('orchestrator', 'inferred', 2, 'mid')} != {... 'zed':
  ('worker', 'declared', 2, 'mid')}` in all six orders, and `AssertionError:
  0 != 4 : c is not drawn under f: case 11 of seed 20261015`.
- 2, `down` for every name that stopped listening: `AssertionError: {'b':
  ('down', None), 'c': ('down', None)} != {'b': ('working', None), 'c':
  ('down', None)}` and `{'s1': 'down', 's2': 'down', 'q': 'down', 'd':
  'down'} != {... 'working', 'working', 'woken', 'down'}`; a woken end
  marking the wire down: `the wire to a woken session is drawn as the
  dead wire`, `true !== false`.
- 3, no route reuse: `a wire that stopped flowing set off a route
  search`; no age-only skip: `a poll that only aged the mail laid the
  board out again`.
- 4, the old outline CSS: `FAIL every session on screen (16): missing:
  orchestrator_..._a, ..._b`, `FAIL no row, group heading or root button
  past the window's right edge (374 px): tc-root-btn ... ends at 493`,
  `FAIL each 64-character name's role words are on screen`.
- 5, a root button that does nothing: `FAIL the root link for z brings
  z's tree into view: before the click z's heading at 913 to 933 in a
  400 px viewport, scrollY 0; after it ... scrollY 0`.
- 6, the Google @import put back: `FAIL the page asked no host but
  127.0.0.1: asked: https://fonts.googleapis.com/...`; the fonts off the
  allow list: `AssertionError: 404 != 200 : jetbrains-mono-latin-ext-wght-normal.woff2`
  and `not ok 28 - theme.css names no other host ...`.
- 7, no retry: `FileNotFoundError: [Errno 2] No such file or directory:
  '000001-from-a.md'` out of feed().
- 8, the reason dropped: `{'b': (None, None, None), ...} != {'b': (None,
  'made-up reason: cannot list this inbox', None), ...}`; the reason
  copied beside a count: `... 'c': (2, 'made-up reason: ...', 0) ... !=
  ... 'c': (2, None, 0)`; a blank for null on the page: `+ '', -
  'unread unknown'`.
- 9, links followed: `Lists differ: [('a', 'b', 1), ('x', 'ghost', 2),
  ('w', 'c', 3), ('y', 'b', 4)] != [('a', 'b', 1)]`.
- 10, an import's loader: `AssertionError: True is not false : loading
  tc wrote a bytecode cache beside it`.
- 11, http.server's own send_error: `AssertionError: b'Content-Length: 0'
  not found in b"HTTP/1.0 400 Bad request syntax ... Content-Length: 371"`
  (and the same for 414 and 431).
- 12, no dedupe: `Lists differ: [('a', 'b', 5), ('a', 'b', 5)] != [('a',
  'b', 5)]`.
- 13, socketserver's own handle_error: `AssertionError: 'Traceback'
  unexpectedly found in '... Exception occurred during processing of
  request ...'`.
- 14, port 80 let through: `AssertionError: main() went past its usage
  check`; no Latin-1 check: `+ null - 'token damaged · copy the URL
  serve.py printed again'`.
- 16, no `position: sticky`: `FAIL a stale board says so where the
  reader is looking, scrolled down: stale line at -824 to -798 in a 400 px
  viewport at scrollY 895`; the legend back to `long dash`: `theme.css
  draws .tc-wire.kind-native as dash-dot; the legend says: ...`.
- 17, the old main test with 11 s of slow listener proofs:
  `AssertionError: {'a': ('listening', ...), 'b': ('listening', ...)} !=
  {'a': ('writing', ...), 'b': ('writing', ...)}`; the new one stays
  green with the same delay. The window never saying live: `check
  failed: page.waitForFunction: Timeout 10000ms exceeded.`

**Verify commands and their output**, in this worktree before the last
commit: `python3 -m py_compile tc board/serve.py && node --check
board/look.js` clean; `node --test tests/*.test.mjs` 59 pass, 0 fail
(52 before); `python3 -m unittest discover -s tests -p 'test_*.py'` 153
OK (140 before), with the two known `ResourceWarning` lines from
`tests/test_health.py`; `NODE_PATH=<a Playwright install>/node_modules
node tests/board-browser-check.mjs` (Playwright 1.63, Chromium 153)
`result: PASS`, 45 rows at the end, in four runs after item 6, the last
two on the final code (one run between them failed on the check's own
console count, the stale check's 500s judged as page errors, and was
fixed by judging the console first); `--self-test` `self-test: PASS`.
`check_voice.py` and `check_american.py` were clean on both QA scripts
and this file.

**Where this round differs from its brief, and what it decided.**
- A wire to a woken session is drawn as any mail wire is (the mail that
  woke it flows to it, then rests solid); only `down` dots a wire. The
  warning is on the box (glyph, words, a 3 px solid border) and the pill.
- The demo's `d` now has 0 unread: a down name with unread mail cannot
  happen under D24 (that mail would have woken it).
- The browser check keeps every message to `d` and `e2` old, and ages
  the mail once before making them down: under D24, mail that reached
  them after they were seen listening reads as a wake.
- The two long names are a root over a worker, so the phone shows one in
  a row, a group heading and a root button; the roots line now reads `3
  orchestrators: a, <long name>, z`.
- tokenProblem calls only a character outside Latin-1 damage: any other
  wrong token rides in the header and gets 401, `token refused`.
- The route key also holds the connectors and the tree wires, since
  routeAround keeps off them; and the grid edge flags cache the
  alongside check as well as pieceFree.
- The property test runs 600 seeded cases, not "a few hundred" exactly,
  so at least 20 build the cycle shape (27 do).
- Line 142 above still says the native pair is joined by `a long dash`;
  the brief keeps that part of this file as it is. The line is dash-dot.

**For the architect.** C5's node shape gains `unread_problem`, and
`unread` may be null (item 8); C6's allow list gains the six files under
`fonts/` (item 6); C5 still shows the SourceFileLoader load, which
load_tc no longer uses (item 10). contracts.md was not edited. All three
are made on the dev branch at `0b629e8` (C5's null `unread` with
`unread_problem`, C5's in-memory loader, C6's six `fonts/` files): no ask
is left open here.

**Not in this round** (the brief's list): LOW-1, LOW-23, LOW-24, LOW-31
and LOW-32 are the architect's (CLAUDE.md, tc, the plan); LOW-30 is the
DOCS lane's README. LOW-10 (the poll lists inboxes three times) waits for
SHARED's mailbox_summary. LOW-20 (siblings leave their relay's tree with
no hints) is a design question for a2; inference changed only for item
1. LOW-27 and LOW-28 stay: drawWire and removeBoard are the look kit's
API, and kind, route and last_mail_age_s are C5 keys. Every DEBT stays a
DEBT; DEBT-1 is now D25 and lands after the SSH lane.

**Not verified.**
- A real phone, Safari and Firefox: the browser check is headless
  Chromium only, so the faces, the sticky stale line, `overflow: clip`
  and the wrapped long names were seen there alone.
- The Daylight look's woken border (the warn token is blue there) in a
  browser; the check opens the dark look.
- A real session's wake on a live board, and a session that crashes after
  reading (it reads working until DOWN_WINDOW_S, as D24 says).
- Port 80 was never bound; the test stops main() at its usage check.
- The hang-up line with a real browser closing a tab; the test resets a
  raw socket.
- FIRST_DRAW_BUDGET_MS is a time on one machine; a much slower one could
  pass the routing and still fail the budget.
- The mutation run that put the Google @import back made real requests
  to fonts.googleapis.com and fonts.gstatic.com from this machine, once
  per page, during that run only.
- `test_a_recent_sender_with_no_listener_is_writing_then_idle` still
  reads the wall clock after a send, the same shape as LOW-21 with a
  smaller window; it was not in the brief.

## P4 phase fix, round 2

Model:  Claude Opus 5.5 (the P4 phase fixer), 2026-10-15
Status: unreviewed
Brief:  audits/2026-10-15-0150-custom/fixes/round-2.md, from that audit's
        synthesis (the ids below are its ids); D27 and D28 read on the dev
        branch at `8bdf363`, read only
Branch: Claude-Development-TheConnection-P4FIX, from `602b62a`, in
        ~/TheConnection-lanes/p4fix

| Part | Commit | Subject |
|---|---|---|
| (a) items 1, 3 | `95cc3c8` | Keep a killed listener down whatever mail lands later, and read the wake from what left the inbox (D28) |
| (b) item 2 | `df304b3` | Guess a parent only from a clear majority of a node's mail, and never call a peer inferred (D27) |
| (c) items 4, 5, 6 | `64d29a7` | Give a node's unread words their own place, stop a stale jump under the stale line, and call a header-breaking token damaged |
| (d) items 7, 8 | `ed56f3f` | Route a new pair alone, count the router's work instead of timing it, and pin the wake walk's cost |
| (e) items 9 to 12 | the commit that adds this section | Make the round's words and tags true, abort off-host requests in the browser check, and record the fonts' hashes |

No amend, reset or rebase. Nothing pushed or merged. `tc`,
`tests/_root.py`, `CLAUDE.md`, `README.md` and the plan files were not
edited. Above this section only the round 1 section's "For the architect"
paragraph changed (item 9, LOW-8).

**What changed, item by item.**
1. MEDIUM-1, D28, LOW-4. serve.py: the Board keeps `first_missing_at`,
   the first poll that found no pid after a sighting, cleared on the next
   sighting and pruned with last_listening_at. find_wake counts as the
   wake only mail that landed from POLL_SECONDS before the last sighting
   to POLL_SECONDS after that first poll, so a killed listener stays
   `down` whatever mail lands later. wake_of looks for the wake while that
   window is open and keeps what it found in `wakes` until the next
   sighting; past the window it looks no more. A name whose inbox or
   read/ the board cannot list (message_names now tells "no folder" from
   "cannot list") reads `down`, and the feed's new node key
   `inbox_unreadable` is true; the page shows `inbox unreadable` as a
   badge line on a down node (INBOX_WORDS). Both legends name the two
   cases C5 says the states cannot see.
2. D27. serve.py parents_of: the partner holding at least
   PARENT_MAJORITY (`fractions.Fraction(2, 3)`) of the node's messages,
   sent and received, if it has HUB_MIN_PARTNERS; D15's guard and
   drop_inferred_cycles stay. feed() builds the partner counts from the
   per-pair `sent` counts it already kept. A peer's role_source is
   `none` (NO_EDGE). look.js roleTitle never writes `inferred` on a peer.
   Every fixture, test and QA line that read `peer · inferred` now reads
   `peer` (role_source `none`).
3. LOW-3. scan_messages keys a message by recipient, number and sender
   and keeps the inbox copy; after_listening's read evidence is that a
   waking message left the inbox (by its file name), wherever it went;
   find_wake walks the candidates in file time order, so no number ends
   it.
4. LOW-5 (option A). createNode: the second line holds the state's glyph
   and word alone; the unread words lead the third line in
   `.tc-node-unread` (never shrinks), then the note (may shorten).
5. LOW-1. theme.css: `--tc-stale-h` from the stale line's line height,
   padding and border, `--tc-jump-gap` (the old 8 px), and a stale
   window's jump targets keep both clear.
6. LOW-11 (option B), LOW-10. tokenProblem: NUL, LF and CR are damage
   (HEADER_REFUSED). FeedHandler's and send_error's docs say a request
   http.server still holds as HTTP/0.9 (a one-word line, an unreadable
   version, HTTP/2.0) gets no bytes at all.
7. LOW-12, LOW-13, REC-12, REC-14. look.js: routes.runs is keyed by a
   pair's two ends under a shared key of boxes, headings, extent and
   tree runs; routeAround counts `edgeHits`. Answer to the brief's
   question: one pair's route does not depend on another's (routeAround
   keeps off boxes, ports, headings and `along`, and no routed run is in
   `along`), so the cache is keyed per pair.
8. LOW-14. The stopped name's candidates are its newest WAKE_CANDIDATES
   (16) messages by number, kept in a heap as feed()'s loop over the
   messages goes, only while its wake window is open; nothing sorts a
   name's history. The code landed in (a), where D28 needed it; (d)
   adds its test.
9. LOW-6 (option A), LOW-7, LOW-8, LOW-9, LOW-15. Board.snapshot's doc
   says the retry serves dev's tc before SHARED; "SHARED's tc" in
   serve.py, test_board_feed.py and board-patch.test.mjs now says what
   the code guards; the round 1 "For the architect" says the three
   changes are on dev at `0b629e8`; board-layout.test.mjs's @complexity
   covers the 20 peers (in (d), with the tests it describes); demo.html's
   pill comment counts woken; drawnKey's and patchBoard's @alloc, and
   live.html's per-poll @complexity (rootsList sorts), are true; serve.py's
   module @alloc was made true in (a), with the code it describes.
10. LOW-2 (option A). The browser check no longer waits on `data-conn`
    live; the comment names the settle: a drawn node or row, the faces,
    two frames.
11. REC-5, REC-6. watchHosts, used by every page: page.route aborts any
    request to a host but 127.0.0.1, and the row fails when the page
    asked another host or when the watch saw no request to 127.0.0.1.
12. REC-3, REC-4, REC-8. qa/human/board-live.md step 15 opens the URL
    with a damaged token; a node's hover title and its outline row show
    tc's reason beside `unread unknown` (problemOf, as text, through the
    title property and textContent, never markup); the hashes below.

**Where this round differs from its brief, and what it decided.**
- The unread words lead the third line, beside the note, rather than a
  fourth line of their own. A fourth line would make a box taller each
  time its count went from 0 to 1 and back, moving every box under it
  and setting off every route search; the box keeps the height the owner
  approved. The state words do have their line to themselves.
- `inbox unreadable` is a badge line (a dashed rule), not words on the
  state line: `no listener · inbox unreadable` is 30 characters, past
  the 25 the state line holds, and C5 wants the words whole.
- The feed carries `inbox_unreadable` as a node key, so the page knows
  when to say the words. C5 names the words and no key.
- `inbox` counts read/ too: a waking message already read sits there, so
  a read/ the board cannot list leaves it unable to tell, the same as
  the inbox.
- The wake's candidates are bounded (WAKE_CANDIDATES, 16). More than 16
  hand-made files numbered above the waking message push it out, and the
  name reads down. A waking message moved out of sight before the first
  poll that saw its listener gone is never seen either. Both need
  someone who can write the inbox.
- The new size tokens sit on `.tc-backdrop`, beside `--tc-page-pad`, not
  on `:root`: tests/board-theme.test.mjs (outside this lane's files)
  takes every `:root` token for a color Daylight must restate.
- The stale jump check uses a 300 px viewport of its own. At the 400 px
  of the first jump check the desktop page could not scroll z's heading
  to the top, so the check passed with the bug in. It now also fails
  when the heading lands more than the gap under the line.
- tokenProblem calls NUL, LF and CR damage wherever they sit. fetch
  strips them (with spaces and tabs) from the ends of a header value
  rather than refusing them, so a token with only a trailing %0A would
  have worked; serve.py's tokens never hold one, so it reads as damage.

**Mutations and their red lines.** Each applied by hand, seen red,
restored; the assertion line only.
- 1, no first-missing time (the wake window with no end):
  `AssertionError: {'b': ('working', None, False), 'c': ('working', None,
  False)} != {'b': ('working', None, False), 'c': ('down', None,
  False)}`. A folder that cannot be listed read as empty:
  `AssertionError: {'r': ('working', False), 'u1': ('down', False), 'u2':
  ('working', False)} != {'r': ('working', False), 'u1': ('down', True),
  'u2': ('down', True)}`. No inbox line in badgesOf: `+ d: [], - d: ['inbox
  unreadable']`.
- 2, the one-partner rule back: `AssertionError: {'a': ('peer', 'none', 0,
  None), 'b': ('peer', 'n[42 chars]one)} != {'a': ('orchestrator',
  'inferred', 0, None), 'b':[64 chars]'a')}`. A peer marked inferred:
  `AssertionError: {'x': ('peer', 'inferred', 0, None), 'r1':
  ('orchestrator[97 chars]r2')} != {'x': ('peer', 'none', 0, None), ...}`.
  roleTitle writing it: `+ 'x · peer · inferred' - 'x · peer'`.
- 3, the read/ copy winning the dedupe: `AssertionError: {'b': 'down', 'c':
  'down'} != {'b': 'woken', 'c': 'woken'}`. The wake looked for afresh
  each poll: `AssertionError: {'b': 'down', 'c': 'woken'} != {'b':
  'working', 'c': 'woken'}`. The walk in number order: `AssertionError:
  Tuples differ: ('down', 'down') != ('working', 'woken')`.
- 4, the unread words back on the state line: `+ '△woken · not read ·
  unread unknown' - '△woken · not read'`; in the browser, both looks:
  `FAIL dark look: the state line and the unread words are whole (y1,
  docs, y3): y1's state line "△woken · not read · unread unknown" is cut
  or is not woken · not read; ...`.
- 5, no stale scroll margin: `FAIL while stale, the root link for z stops
  z's heading under the stale line, not behind it: ... after it z's
  heading at 8 to 28, the stale line at 0 to 26, in a 300 px viewport at
  scrollY 939` (and at 390 px, scrollY 778).
- 6, no NUL, LF or CR check: `+ null - 'token damaged · copy the URL
  serve.py printed again'`.
- 7, the one key naming every drawn pair: `41 !== 21`. The edge flags not
  kept: `no search looked up a grid edge it had already checked: the edge
  flags keep nothing`. Runs never dropped: `the cache held 501 runs while
  two pairs were drawn`.
- 8, a stopped name's whole history as candidates: `AssertionError: Lists
  differ: [('working', 49), ('working', 49), ('working', 0)] !=
  [('working', 16), ('working', 16), ('working', 0)]`.
- 11, the home count dropped: `FAIL the page asked no host but 127.0.0.1
  (0 requests to it watched): no request to 127.0.0.1 seen, so the watch
  proves nothing`, on all six pages. An off-host @import (a made-up name
  under the reserved .invalid domain, which resolves nowhere) put in
  theme.css: `FAIL the page asked no host but 127.0.0.1 (7 requests to it
  watched): asked: http://off-host.invalid/x.css (aborted here: 1)`.

**Measured.** The 20-peer first draw: 190 route searches and 112,031
grid edges looked up again, 112 and 130 ms in two runs on this machine
at load under 5 (the 10 s stopwatch is a backstop only); with the edge
flags not kept (mutation 7) it took 162 ms and looked up none again. The property test now
builds 39 cases with an inferred edge on a cycle (27 before).

**Verify commands and their output**, in this worktree on the final
code: `python3 -m py_compile tc board/serve.py && node --check
board/look.js` clean; `node --test tests/*.test.mjs` 66 pass, 0 fail
(59 before); `python3 -m unittest discover -s tests -p 'test_*.py'` 161
OK (153 before), with the known `ResourceWarning` lines from
`tests/test_health.py`; `NODE_PATH=<a Playwright install>/node_modules
node tests/board-browser-check.mjs` (Playwright 1.63, Chromium 153)
`result: PASS`, 51 rows, twice; `--self-test` `self-test: PASS`.
`check_voice.py` and `check_american.py` clean on both QA scripts and
this file.

**The fonts, recorded (REC-8).** From the npm packages
`@fontsource-variable/space-grotesk` 5.3.0 and
`@fontsource-variable/jetbrains-mono` 5.3.0, each under the SIL Open
Font License 1.1. `sha256sum board/fonts/*` on this branch, matching the
round 1 brief's list:

```
79bfdab9ba467e26eea4122e6f2567e188dd8a09a8c730d501fc487c4ab99c6e  board/fonts/jetbrains-mono-latin-ext-wght-normal.woff2
18be452724bfdc236c074ca94a249a7f41a86752c7d04ab258ce9ed5651f6a7e  board/fonts/jetbrains-mono-latin-wght-normal.woff2
403581b69dac5cff4079205e01c6b467e56af449ecbd7247693ddb1baafa005b  board/fonts/jetbrains-mono-ofl.txt
952dddb45d2f96f71cbf3b7f510b24379afc3c89ea02fcf89d377b45d62c0166  board/fonts/space-grotesk-latin-ext-wght-normal.woff2
0640890476fc1198ab4de571fb658de443c4d85b66466ec09534a8737ab1ce9d  board/fonts/space-grotesk-latin-wght-normal.woff2
18a4de52385f6b988782639d5d0cc1326e5a8c2de9a7f01d7b20d9aedcc60943  board/fonts/space-grotesk-ofl.txt
```

**For the architect.** C5's node shape gains `inbox_unreadable` (a
boolean; the page owns the words) and role_source `none` (D27 names it).
C5's cost line (LOW-17) still reads O(n + m + e); feed() is now
O(k + m (log W + log K) + n + c^2), K = WAKE_CANDIDATES. contracts.md
was not edited.

**Not in this round** (the brief's list). DEBT-1 (the board reading D25's
outbox) waits for the SSH lane. DEBT-2 (routing in slices), REC-7 (a
Content-Security-Policy), REC-11 (handle_error's frame) and REC-13 (a
second route key) stay open. LOW-16 and LOW-17 are on dev, the
architect's. `tc wait` writing its exit reason into its lock file (D28's
follow-up) is a later task that edits tc.

**Not verified.**
- D28 on a live board with a real session: the feed tests drive proven
  listeners on a fake clock, and QA step 16's new lines are written, not
  run by a person.
- `inbox unreadable` from a real shared mailbox: tested with folders
  closed by mode 000 as this user. On the dev branch's tc an unlistable
  inbox counts 0 unread (pathlib's glob passes over the error); the
  board's own listing is what sets the flag.
- The stand-in feed's lines were measured in headless Chromium only, at
  1280 x 900; the outline's tc reason line only through the fake
  document.
- The stale line's height assumes its words fit one line; on a screen
  too narrow for `stale · last answer N s ago` the line wraps and a jump
  lands partly under it.
- A real phone, Safari and Firefox, as in round 1.
