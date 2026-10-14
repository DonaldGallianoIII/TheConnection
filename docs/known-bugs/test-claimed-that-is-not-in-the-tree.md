# test-claimed-that-is-not-in-the-tree

Model:  Claude Opus 5.5 (the GROUND lane agent), 2026-10-14
Status: unreviewed

**What:** a commit message says tests pass, and the tests it cites are not
in the repo at that commit. Nobody who checks out that commit can run
them.

**How it showed:** two commit messages cite 8 mailbox round-trip tests the
repo never held.

- `1db0430` (Add tc health and tc watch): "The original 8 mailbox
  round-trip tests still pass against this tc."
- `deebaf2` (Add tc wait --keepalive): "All 13 new tests and the original
  8 mailbox tests pass."

`git ls-tree -r --name-only 1db0430` holds `tests/test_health.py` and
`tests/board-look.test.mjs`; `deebaf2` adds `tests/test_keepalive.py`. No
mailbox test is in either tree. The first commit, `63e4332`, said where
those tests were ("the tests and the QA checklist stay in the private repo
for now"). The two later messages dropped that, and the claim read as if
the tests were here.

**Why it's bad:** the core mailbox (send, read, peek, wait, log, status)
looked tested and was not, in this repo, until CORE's
`tests/test_mailbox.py` merged at `f5f6923` (K1 to K8). Before that, most
ways of breaking the core mailbox passed every test, while the history
said it was covered.

**Prevention:** a claim names a file and a command, and the file is in the
tree at that commit. Tests kept somewhere else are not cited as passing
here; say where they live, or say nothing.

**The check that catches it:** for every test file a commit message
names, `git cat-file -e <commit>:<path>` exits 0. A count of tests with no
file name ("8 tests pass") fails the check by itself, because there is
nothing to look up.

**Detection:** in `git log --format=%B`, a number next to "tests" or
"pass" with no path on the same line; a test file named in a message that
`git ls-tree -r --name-only <commit>` does not list.

**Source:** commit messages `1db0430` and `deebaf2`. Recorded 2026-10-14
in `docs/planning/connection-routes/phases.md` (task G2); `00-index.md`
section 1 noted the core mailbox had no tests in the tree; CORE (P1)
closed that gap.

**Times hit:** 2.

**Tier when hit:** MEDIUM. A check that cannot fail while guarding a claim
the project relies on: that the core mailbox is tested.

**Shared catalog:** a form of `written-claim-outlives-the-code` (the
message outlived any link to the tests it named) and of
`check-that-passes-by-not-checking` (tests that never run here cannot fail
here).
