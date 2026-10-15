# plain-object-keyed-by-outside-names

Model:  Claude Opus 5.5 (the known-bugs writer, for the architect session), 2026-10-15
Status: unreviewed

**What:** JavaScript code uses a plain `{}` as a map keyed by names that
come from outside the code (a user, a file, the network). A name equal to
`__proto__` sets the object's prototype instead of adding a key. The
entry is never stored, `Object.entries` skips it, and reads return
`Object.prototype`, which turns arithmetic into NaN. A read has the same
hole: a lookup in a fixed plain-object table keyed by outside data
(`TABLE[value]`) answers `constructor`, `toString` or `__proto__` with
something from `Object.prototype` instead of nothing.

**How it showed:** the BOARD lane, 2026-10-14. At `d250036`, layoutLevels
and boardView keyed `rows`, `span`, `pos`, `nodes` and `edges` by session
name (`board/look.js:411`, `:423`, `:430`, `:504`, `:517`). Contract C0
allows `__proto__` as a name. One such node was never drawn, every
position after it was NaN, the wires drew nothing, and the pill still
said live. A scratch run confirmed `a.x` was NaN and that no `__proto__`
key existed.

**Why it's bad:** one legal name wrecks the whole board with no error,
while the status says everything is fine.

**Prevention:** key by outside names only with `Map` or
`Object.create(null)` (look.js's `nameMap()`). A name rule that rejects
`__proto__` is not a fix where the contract allows that name. Read a fixed
table only behind `Object.hasOwn(TABLE, key)`, or make it a `Map`. Test
with nodes named `__proto__` and `constructor`, and assert every
coordinate passes `Number.isFinite`.

**The check that catches it:** `tests/board-patch.test.mjs`, "nodes
named __proto__, constructor and toString lay out and draw like any
other (C0 allows all three)": all four names are laid out, every position
and wire point is finite, and the kit creates four nodes and two edges.

**Detection:** `= {}` followed by `x[name] =`, `x[id] =` or `x[key] =`,
where the key traces back to input data (a feed, a file, the URL, a
form), and `Object.entries(` or `for...in` over that object. An
`Object.hasOwn` check on read does not clear it, because the key was
never set. Not a hit: `Map`, `Object.create(null)`, or writes whose keys
come from a fixed literal list. A read of a fixed literal table keyed by
outside data (`STATES[n.state]`) still counts unless `Object.hasOwn`
guards it. The tree holds such reads today: `board/look.js` reads
`STATES[...]`, a frozen plain object, at `:590`, `:1689` and `:1781`.
serve.py sends only its own state words, so no outside name reaches them
now; a feed that sent `constructor` as a state would pass the check.

**Source:** the BOARD lane's full review, 2026-10-14 (audit folder
`2026-10-14-1811-full`; review audits stay out of the repo), MEDIUM-4.
The reviewer that found it filed HIGH; the review moved it to MEDIUM (no
crash, no data loss, no exposure). Closed by `280a200`: every map keyed
by session name has no prototype, with the test above. It reached the dev
branch with the BOARD merge, `a2953cb`. The P4 phase review (audit folder
`2026-10-14-2344-full`) found names going through `nameMap` or a `Map`,
and noted the `STATES` reads above.

**Times hit:** 1.

**Tier when hit:** MEDIUM. No crash, no data loss and no exposure, but one
legal name silently wrecks every box and wire.

**Shared catalog:** none fits. "String-keyed Map in a hot path."
(`~/Conventions/code/known-bugs/javascript/hot-paths.md`) is about
allocation cost, not prototype keys.
