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

## The shared catalog

Both entries are forms of two entries in the shared known-bugs catalog:
`check-that-passes-by-not-checking` and `written-claim-outlives-the-code`.
Each detail file says how.

The copy of the catalog in the owner's conventions folder does not hold
either slug yet. Its closest file is
`~/Conventions/code/known-bugs/any-language/tests-and-checks.md`, which has
an entry titled "A check that passes by not checking." about error guards
and missing fixtures. It has nothing for `written-claim-outlives-the-code`.
