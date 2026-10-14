# GROUND-2: fake_bin has no test in the tree

Model:  Claude Opus 5.5 (the GROUND lane agent), 2026-10-14
Status: unreviewed

## The question

Task G3's test spec names two tests, both about the listener, and its
verify line says `python3 -m unittest tests.test_root -v` shows 2 passed.
`fake_bin`, `tc()` and the listener's failure branches have no test in the
tree. CARDS (R4) and SSH (S1, S2) build on `fake_bin` and assert its
recording. Should GROUND add a test for it now?

## Options

1. **A third test in `tests/test_root.py`**: write a fake, run it by
   absolute path with arguments and stdin, assert `calls()` is `[]` before
   and holds exactly that call after, and the exit code matches. The G3
   verify line then reads 3 passed.
2. **Leave it to CARDS and SSH.** Their specs already assert the recording
   exists, so a broken fake turns their tests red. The failure then shows
   up far from its cause.
3. **A separate file, `tests/test_fake_bin.py`.** Keeps `test_root.py` at
   the 2 tests its verify line names. Adds a file no task names.

## Recommendation

Option 1. A harness every later lane trusts gets its own test, and the
change to the verify line is one word.

## What carried on

GROUND built `fake_bin` as specified and checked it by hand with a scratch
script (not in the repo) that ran each fake by absolute path, so no real
`ssh` or `codex` could run. All 13 checks passed: `calls()` is `[]` before
a call; argv and stdin are recorded in order; exit codes 0 and 7 come
back; two fakes keep separate records; `tc()` feeds stdin and keeps
`TC_ROOT` when `env` tries to change it; a second listener for one name
and a listener with mail already waiting both raise `ListenerNotProven`; a
listener the test kills itself is still reaped; every child is gone and
the temp folder removed after `TcRoot` exits. The handoff lists them.
