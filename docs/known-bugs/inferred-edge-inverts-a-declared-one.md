# inferred-edge-inverts-a-declared-one

Model:  Claude Opus 5.5 (the known-bugs writer, for the architect session), 2026-10-15
Status: unreviewed

**What:** code infers a missing parent for node N from a heuristic (N
talks only or mostly to P, and P is a hub) in a graph that also holds
declared parents. A guard that looks one hop only refuses when P's own
declared parent is N. When P sits below N through a chain of two or more
declared edges, the inferred edge closes a cycle anyway. A cycle breaker
that picks its root by name order (`min(cycle)`, the first sorted name)
can then cut a declared edge and keep the inferred one.

**How it showed:** twice, both in the board's feed (`board/serve.py`).

- One hop, the BOARD lane's full review, 2026-10-14. At `d250036`,
  rule 2 (`board/serve.py:383` to 387) never read the partner's card.
  `b` declares reports_to `z`, `z` mails only `b`, and `b` also mails
  `x`. `z` got `b` as its inferred parent, and the level walk drew `z`
  one row under its own worker (levels b 0, x 1, z 1). With `z` renamed
  `a` the levels looked right, but `a` still carried parent `b`.
- Through a chain, the P4 phase review, 2026-10-15. At `7daf64a` the
  one-hop guard was in (`board/serve.py:516` to 517). Cards: `zed` is the
  top, `mid` reports to `zed`, `alpha` reports to `mid`. Mail: `alpha` to
  `mid`, and `zed` to `alpha`. `zed`'s one partner is `alpha`, whose card
  names `mid`, not `zed`, so the guard let `zed` be inferred under
  `alpha`. That closed `zed`, `alpha`, `mid`. The level walk rooted the
  cycle at `min(cycle)` (`:601` to 606), which is `alpha`, so it cut
  `alpha`'s declared edge and kept `zed`'s inferred one.

**Why it's bad:** the drawn hierarchy puts a declared top under its own
worker, shows a reports_to cycle that no card makes, and changes when a
name changes. On the board: `alpha` drawn as the root with the badge
`reports to mid · cycle`, `zed` under `alpha`, and `mid` at the bottom.
Renamed `aaa`, the top drew the levels right, but `alpha` still read
`orchestrator · inferred` with nothing drawn under it, because roles were
built from every edge, the cut one included.

**Prevention:** an inferred edge never closes a cycle. Either walk P's
declared ancestors before accepting P for N and refuse if the walk
reaches N (O(depth) per inferred node), or, as the fix does, drop every
inferred edge that sits on a cycle before anything reads the parent map,
so roles, levels and the drawn parent all see one edge set. Name order
may break only a cycle made entirely of declared edges. Test the chain
under every order of the three names and assert each node's parent, level
and role. Add a seeded property test over many name orders asserting that
declared edges always survive.

**The check that catches it:** `tests/test_board_feed.py`:

- `ShapesTest.test_inference_never_inverts_a_declared_edge`: the one-hop
  shape with the top named `z`, then `a`.
- `ShapesTest.test_inference_never_closes_a_cycle_through_declared_edges`:
  `alpha`, `mid` and `zed` under all six name orders, and no root names a
  parent node.
- `InferencePropertyTest.test_declared_edges_survive_any_mail_and_any_name_order`:
  600 seeded cases. Every card's edge is drawn, roles match the drawing,
  and reversing the names' order changes nothing. At least 20 cases must
  build an inferred edge on a cycle, so the property cannot pass on easy
  cases alone.

**Detection:** (1) a parent assigned in a heuristic branch (`infer`,
`INFERRED`, `hub`, `HUB_MIN`, `len(partners) == 1`, `only partner`, a
majority share) whose guard reads the candidate's declared parent once, as
in `cards.get(only, {}).get("reports_to") != name`, and never loops up the
declared chain. (2) a cycle breaker that picks its root with
`min(cycle)`, `sorted(...)[0]` or first-seen order and does not read
whether each edge is declared or inferred. (3) a role or label function
that reads the full parent map while the level walk drops a cycle edge,
so the two disagree. Each one alone is worth a read. (1) and (2) in one
file is a hit.

**Source:** the one-hop form: the BOARD lane's full review (audit folder
`2026-10-14-1811-full`; review audits stay out of the repo), HIGH-2,
closed by the guard in `062dec9`. The chain form: the P4 phase review
(audit folder `2026-10-14-2344-full`), HIGH-1, closed by `a48f3db`, which
drops every inferred edge on a cycle (`drop_inferred_cycles`) inside
`hierarchy()`, so the roles and the levels read one cleaned map. D27
(`df304b3`) later made the guess a clear majority of a node's mail and
kept both guards. The fixes reached the dev branch with `a2953cb` and
`eb3e187`.

**Times hit:** 2. The fix for the one-hop form left the chain form open.

**Tier when hit:** HIGH, both times. C5 says inference never inverts a
declared edge, and the board drew the inversion. The wrong thing is the
board's output, not stored data.

**Shared catalog:** none fits. "Validator skips what the resolver
defaults." (`~/Conventions/code/known-bugs/any-language/state-and-persistence.md`)
also covers a filled-in value that contradicts kept data, but its
mechanism, a validator that returns early, is different. The catalog has
no entry on graphs or cycles.
