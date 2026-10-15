# path-search-rerun-per-pair-on-every-poll

Model:  Claude Opus 5.5 (the known-bugs writer, for the architect session), 2026-10-15
Status: unreviewed

**What:** a view rebuild that runs on every poll answer and every resize
calls an expensive search (A*, a router, a layout solver) once per drawn
pair, from scratch, with no cache keyed on what the search reads. A
normal poll changes only ages and timestamps, so every search repeats the
same work. Inside one group the pair list grows as c(c-1)/2.

**How it showed:** the P4 phase review, 2026-10-15. At `7daf64a`,
patchBoard rebuilt the whole view on every call (`board/look.js:1754`),
createFit called it on every draw and every width change (`:2073`,
`:2084` to 2088), and live.html drew on every 3 s poll. boardView called
routeAround, an A* search, for every drawn pair that is not a parent and
child (`:1665`), and its `pieceFree` (`:1188`) scanned every obstacle per
neighbor with no memo. serve.py emitted one native link per pair of
Claude cards on one account (`board/serve.py:779` to 782), so the routed
pairs grew as c(c-1)/2 per account. The cost was estimated from source,
not measured: about 0.1 to 0.5 s per poll at 14 names on three shared
accounts, more at 20 peers on one. A run on a 14-name board where 10
of the 14 cards had an account of their own measured 9 to 24 ms, so the
finding rests on shared accounts.

**Why it's bad:** the main thread stalls once per poll and freezes while
a window edge is dragged, and the 3 s refresh the page promises
stretches.

**Prevention:** cache each searched path, keyed on exactly what the
search reads (box positions and sizes, headings, the extent, the tree's
runs) and on the pair's own ends. When the key matches, reuse the points
and recompute only labels, flow and words. Skip the rebuild when only
ages moved and no age crossed a display threshold. Memoize per-cell
predicates inside the search. Count, do not time: assert zero searches on
an age-only repatch, and an exact count on the first draw of the largest
realistic group. `~/Conventions/code/DOCBLOCKS.md` says why: a stopwatch
is the wrong instrument.

**The check that catches it:**

- `tests/board-layout.test.mjs`, "routes are searched once per routed
  pair, none on a poll that only aged the mail or stopped a flow, and
  draw as before".
- `tests/board-layout.test.mjs`, "twenty Claude peers on one account: the
  first draw searches once per native line and reuses grid edges, the
  next poll searches none" (190 searches, then none).
- `tests/board-layout.test.mjs`, "a pair's first mail searches only that
  pair, and a native pair's first mail searches none".
- `tests/board-layout.test.mjs`, "createFit searches no route from 1152 to
  1140 px, where no row wraps, and every native line again at 1000 px,
  where one does".
- `tests/board-leak.test.mjs`, "500 feeds of peers that come and go leave
  the route cache holding one run per routed pair drawn, no more".

**Detection:** a function wired to a poll callback or a ResizeObserver
(`onFeed`, `draw`, `fit.draw`, `new ResizeObserver(`) that rebuilds the
whole view (`boardView(feed, width)`, `buildView(`, `layout(`) and calls a
search routine (`routeAround(`, `astar`, `dijkstra`, `findPath`) inside a
loop over pairs or edges, with no Map outside the function holding
earlier results and no comparison of new inputs with the last ones before
the loop. Worse when that pair list comes from `combinations(` or a
nested loop over one group. Inside the search: a neighbor test like
`obstacles.some(` with no memo next to a sibling that is cached.

**Source:** the P4 phase review, 2026-10-15 (audit folder
`2026-10-14-2344-full`; review audits stay out of the repo), MEDIUM-2.
Closed by `ea493c1` (the route cache, `createRouteCache`; no layout for a
feed that differs only in its ages; each grid edge checked once per
search) and `ed56f3f` (runs kept by their ends, so a new pair searches
only itself; the tests count searches and grid-edge hits instead of
timing). `ea493c1`'s message records 20 peers on one account drawing
their 190 native lines in about 150 ms, and an age-only poll in under a
millisecond. Both reached the dev branch with the P4FIX merge, `eb3e187`.

**Times hit:** 1.

**Tier when hit:** MEDIUM. A stall on every poll for a realistic
shared-account board, estimated from source, not measured.

**Shared catalog:** closest is "No render pause on blur, or when nothing
can change."
(`~/Conventions/code/known-bugs/javascript/async-and-lifecycle.md`): both
redo full work when nothing that matters changed, and both want a dirty
check first. Here the cost is a search per pair, not a frame, so a flag
alone is not enough: the reused result needs a cache keyed on the
search's inputs. The hot-path entries on allocation and layout reads do
not cover a repeated search.
