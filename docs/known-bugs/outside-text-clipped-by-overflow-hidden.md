# outside-text-clipped-by-overflow-hidden

Model:  Claude Opus 5.5 (the known-bugs writer, for the architect session), 2026-10-15
Status: unreviewed

**What:** text that comes from data (a name, a title, a path) sits in a
flex or grid item that keeps the default `min-width: auto` and has no
`overflow-wrap`, sometimes with a child span set to `white-space: pre` or
`nowrap`. An ancestor has `overflow: hidden`. A long value with no break
point pushes the item past its row, and the ancestor clips it with no
ellipsis and no scroll.

**How it showed:** the P4 phase review, 2026-10-15, in the board's phone
outline. At `7daf64a`, `.tc-row-title` (`board/theme.css:405`) had no
`min-width: 0` and no `overflow-wrap`. The role span inside it was
`white-space: pre` (`:406`), the row was a wrapping flex row (`:402`), and
`.tc-win` was `overflow: hidden` (`:191`). `.tc-group-head` (`:392` to
401) and `.tc-root-btn` (`:354` to 364) had the same gap. A long name
with no hyphen ran past the window and was clipped at its edge. No test
drew a long name: the browser check gained two 64-character names (C0's
longest) only with the fix.

**Why it's bad:** two long names that differ only at the end read as the
same name, and the words after the name (the role) disappear. Those words
carry meaning without color, so for a colorblind reader the cue is gone.
The review estimated, without rendering, that about 25 characters plus an
inferred orchestrator role already overflow at 390 px.

**Prevention:** every flex or grid item that holds data text gets
`min-width: 0`, and the text gets `overflow-wrap: anywhere`. No
`white-space: pre` or `nowrap` on a span inside such a title
(`pre-wrap` keeps the spaces and still breaks). Prefer wrapping to an
ellipsis, since an ellipsis cuts the end, where two names differ.
`~/Conventions/code/WEB.md` already says wide content scrolls inside its
own container. This entry exists because the written rule did not stop
it, and grep can. Test at the narrowest supported width with the longest
legal name and a pair that differs only in the last character, and
assert that no element holding that text is clipped by an ancestor.

**The check that catches it:** `tests/board-browser-check.mjs`, at
390 x 844 with two 64-character names that differ only in the last
character: "no row, group heading or root button past the window's right
edge" and "each 64-character name's role words are on screen". It is the
only check. No `node --test` suite reads these CSS rules, and the browser
check needs Playwright: without it the script prints
`skipped: playwright not found` and exits 0, so on such a machine nothing
catches this pattern.

**Detection:** in CSS, a container with `overflow: hidden` or
`overflow: clip`; inside it, a `display: flex` row whose text child has no
`min-width: 0` and no `overflow-wrap` or `word-break`; any
`white-space: pre` or `nowrap` on a span inside a name or title element.
Then confirm the text comes from data, not a fixed list of short words.
In tests: every fixture name is short while the name rule allows far
longer.

**Source:** the P4 phase review, 2026-10-15 (audit folder
`2026-10-14-2344-full`; review audits stay out of the repo), MEDIUM-3.
Closed by `ea493c1`: at `eb3e187`, `.tc-row-title` has `min-width: 0`,
`max-width: 100%` and `overflow-wrap: anywhere` (`board/theme.css:485`),
the role span is `white-space: pre-wrap` (`:486`), and group headings and
root buttons wrap. `.tc-win` now clips with `overflow: clip` (`602b62a`,
for the sticky stale line), which cuts text the same way, so the wrap
rules are what keep the names whole. Both reached the dev branch with the
P4FIX merge, `eb3e187`.

**Times hit:** 1.

**Tier when hit:** MEDIUM. The role words that carry meaning without
color were lost on the phone, and two long names could not be told apart.
The conventions put a colorblind-rule breach at MEDIUM or higher.

**Shared catalog:** none on this mechanism. Same end state as "The
non-color encoding runs out."
(`~/Conventions/code/known-bugs/any-language/accessibility.md`): the cue
that does not rely on color is gone. `fit-to-screen-scales-text-below-legible`
is a different mechanism: a uniform shrink, not a missing break point.
