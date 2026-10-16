# Known bugs: TheConnection

Model:  Claude Opus 5.5 (the GROUND lane agent), 2026-10-14
Status: unreviewed

The failures this repo has already paid for. Every review checks new code
against them, and every plan task's "must reject" draws on them.

The relay's pattern checker reads files and has no shell, so it cannot run
entry 2's commit-message check (`git cat-file -e <commit>:<path>` for every
test a message names). The architect runs it, with git, at each lane
review.

## The format

Index plus detail, as in `~/Conventions/code/KNOWN-BUGS.md` in the owner's
conventions folder. This file is the index. Each entry has its own detail
file in this folder, named by its slug, in these ten parts:

- **What:** the pattern, in one or two sentences.
- **How it showed:** what was seen, when, and where.
- **Why it's bad:** the failure a user actually sees.
- **Prevention:** the rule that stops it.
- **The check that catches it:** the command or test that fails when the
  pattern is back.
- **Detection:** what a reviewer greps for.
- **Source:** where it was caught, with the commit or record that shows it.
- **Times hit:** how many times it has happened here.
- **Tier when hit:** HIGH, MEDIUM or LOW, with a few words of why. It is a
  floor: a review that matches an entry files the finding at that tier or
  higher.
- **Shared catalog:** the entry in the shared known-bugs catalog this one
  is a form of, and how.

An entry is never deleted for being old. One hit again is marked recurring
and its count goes up.

## Entries

| Entry | Tier when hit | Times hit | In one line |
|---|---|---|---|
| [`listener-reported-live-without-the-lock`](listener-reported-live-without-the-lock.md) | MEDIUM | 1 | A Codex worker said "listening" about a background job its host had already killed. |
| [`test-claimed-that-is-not-in-the-tree`](test-claimed-that-is-not-in-the-tree.md) | MEDIUM | 2 | Two commit messages say 8 mailbox tests pass; the repo never held them. |
| [`lane-built-to-a-contract-the-base-has-revised`](lane-built-to-a-contract-the-base-has-revised.md) | HIGH | 1 | A base-branch ruling changed three feed rules the board lane had built from its own contract copy; the lane's tests pinned the old rules. |
| [`placeholder-value-matched-as-a-real-value`](placeholder-value-matched-as-a-real-value.md) | HIGH | 1 | The feed dropped only a missing account, so every card on the default "unknown" account was linked to every other as sharing one. |
| [`inferred-edge-inverts-a-declared-one`](inferred-edge-inverts-a-declared-one.md) | HIGH | 2 | An inferred parent closed a cycle through declared ones, and a cycle break by name order drew the declared top under its own worker. |
| [`fit-to-screen-scales-text-below-legible`](fit-to-screen-scales-text-below-legible.md) | MEDIUM | 1 | The board shrank to fit instead of wrapping, so seven sessions put role words under 8 px and fourteen at phone width could not be read. |
| [`poll-without-a-deadline-shows-stale-as-live`](poll-without-a-deadline-shows-stale-as-live.md) | MEDIUM | 1 | A suspended server left the live board saying "live" and "listening" for minutes, because its fetch had no timeout. |
| [`two-edges-on-one-pair-share-a-path`](two-edges-on-one-pair-share-a-path.md) | MEDIUM | 2 | Two strokes on one pair drew on one path, so labels overprinted and the dotted "down" cue was hidden: mailbox over native, then a mail wire over its tree connector. |
| [`plain-object-keyed-by-outside-names`](plain-object-keyed-by-outside-names.md) | MEDIUM | 1 | A session named `__proto__` vanished from the board and turned every position after it into NaN, because the layout keyed plain objects by name. |
| [`liveness-gap-by-design-read-as-down`](liveness-gap-by-design-read-as-down.md) | MEDIUM | 1 | A session woken by mail read "no listener" for its whole turn, because the board called any lock lost within 600 s down. |
| [`path-search-rerun-per-pair-on-every-poll`](path-search-rerun-per-pair-on-every-poll.md) | MEDIUM | 1 | The board re-ran its A* router for every routed pair on every 3 s poll with nothing cached, so shared-account boards stall (estimated, not measured). |
| [`no-follow-open-guards-only-the-last-name`](no-follow-open-guards-only-the-last-name.md) | HIGH | 4 | A folder above a no-follow name was swapped after one lstat: a member's own init changed that member's files outside the mailbox, and a member's swapped inbox sent another member's message outside it. |
| [`per-owner-file-open-to-the-group`](per-owner-file-open-to-the-group.md) | HIGH | 1 | On a shared mailbox any member could flock another's 0664 wait lock or rewrite a Codex member's ring marker, so the owner's listener never started while health named the holder, and the doorbell went quiet. |
| [`outside-text-clipped-by-overflow-hidden`](outside-text-clipped-by-overflow-hidden.md) | MEDIUM | 1 | A long session name had no break point in the phone outline, so it ran off the row and its role words were clipped away. |

## The shared catalog

The first two entries are forms of two entries in the shared known-bugs
catalog: `check-that-passes-by-not-checking` and
`written-claim-outlives-the-code`. Each detail file says how.

The copy of the catalog in the owner's conventions folder does not hold
either slug yet. Its closest file is
`~/Conventions/code/known-bugs/any-language/tests-and-checks.md`, which has
an entry titled "A check that passes by not checking." about error guards
and missing fixtures. It has nothing for `written-claim-outlives-the-code`.

The ten board entries added on 2026-10-15 each name their closest shared
entry, or say none fits. Two lean on "A check that passes by not
checking.", three on "The non-color encoding runs out.", one on "Async
reentrant void call." and one on "No render pause on blur, or when
nothing can change." Three have no shared entry at all:
`inferred-edge-inverts-a-declared-one`,
`plain-object-keyed-by-outside-names` and
`liveness-gap-by-design-read-as-down`.
