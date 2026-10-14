# Handoff: GROUND (P0)

Model:  Claude Opus 5.5 (the GROUND lane agent)
Status: unreviewed
Date:   2026-10-14
Branch: Claude-Development-TheConnection-GROUND, from
        Claude-Development-TheConnection at b6a95d4
Where:  ~/TheConnection-lanes/ground

## Commits

| Task | Commit | Subject |
|---|---|---|
| G1 | `f9b27cb` | Add the repo's CLAUDE.md: what tc is, how to test it, the routing rule, the agent rules. |
| G2 | `cf0eb91` | Start the known-bugs index with the two failures seen on 2026-10-14. |
| G3 | `1d67c59` | Add tests/_root.py: throwaway roots, a proven listener, fake ssh and codex. |
| Handoff | the commit that adds this file | Write the GROUND handoff and its three pauses. |

No amend, reset or rebase. Nothing pushed or merged.

## What was built

**G1, `CLAUDE.md`.** The conventions template, filled in for this repo:
what `tc` is, Python 3 stdlib only, Linux and WSL2 only, the two ideas
behind it (the folder is the transport, the lock is the proof of life),
key patterns, current focus, off limits, the layout, the test commands,
the routing rule table from `00-index.md` section 1 word for word (plus
the paragraph under it), the section 9 rules, a QA note (no `qa/bot/`, as
section 10 says), "Deviations from the conventions: None.", and a status.

**G2, `docs/known-bugs/`.** `INDEX.md` plus one detail file per entry:

- `listener-reported-live-without-the-lock.md`: hit 1 time, MEDIUM. The
  check is the pid `tc health --json` reads from `/proc/locks`.
- `test-claimed-that-is-not-in-the-tree.md`: hit 2 times, MEDIUM. Commit
  messages `1db0430` and `deebaf2` cite 8 mailbox tests; `git ls-tree` at
  both commits holds none. The check is `git cat-file -e <commit>:<path>`
  for every test a message names.

Each entry has What, How it showed, Why it's bad, Prevention, The check
that catches it, Detection, Source, Times hit and Tier when hit, and names
the two shared catalog entries it is a form of.

**G3, `tests/_root.py` and `tests/test_root.py`.**

- `TcRoot()`: context manager. One temporary folder; `TC_ROOT` is
  `root/` inside it; inherited `TC_*` variables are dropped; the folder is
  removed on exit after any child still running is killed and reaped.
- `root.tc(*args, stdin=None, env=None, timeout=10)`: runs
  `[sys.executable, TC, *args]`, stdin from `/dev/null` unless given,
  returns `(exit, stdout, stderr)`. `env` is layered over the root's env;
  `TC_ROOT` stays the root whatever `env` says.
- `root.listener(name, timeout)`: starts `tc wait <name> --timeout
  <timeout>`, polls `/proc/locks` every 0.05 s with a 5 s ceiling until
  that pid holds `mail/.wait-<name>.lock`, yields the pid, and in
  teardown kills that pid (SIGKILL, by its own pid) and waits on it. A
  child that exits first, or a ceiling reached, raises
  `ListenerNotProven` (a subclass of `AssertionError`, so unittest counts
  it as a failure) with the child's own output.
- `root.fake_bin(name, exit_code)`: writes `fake-<name>-*/bin/<name>`,
  which appends `{"argv": [...], "stdin": "..."}` as one JSON line per
  call to `fake-<name>-*/calls.jsonl` and exits `exit_code`. Returns
  `(folder, calls)`; `calls()` is `[]` until the fake runs.
- `_root.flock_holders(path)`: the set of pids holding an flock on a path,
  from `/proc/locks`. Public, for CORE's K4.
- `tests/test_root.py`, 2 tests: the pid is in `/proc/locks` at the moment
  of yield and `tc health --json` names it; after the context the pid is
  gone from `/proc` (killed and reaped, no zombie), nothing holds the lock,
  `tc health --json` shows the name with no pid, and the root folder is
  removed. It reads `/proc/locks` with its own code, not the harness's.

Every new Python file has a module doc block and a doc block on every
function, class and method with `@interacts`, `@deps`, `@complexity`
(variables named, with bounds) and `@alloc`, plus the model and
`Status: unreviewed` header.

## What was not built

- No test for `fake_bin`, `tc()` or the listener's failure branches in the
  tree. The spec names 2 tests. Checked by hand instead (below). Pause
  GROUND-2.
- The fake writes nothing to its own stdout or stderr. SSH task S1 expects
  "its stderr printed" for a fake exiting 7; that lane may need a way to
  give the fake stderr text. Not asked for in G3, so not built.
- The existing health and keepalive tests were not moved onto the harness
  (out of scope in G3).
- No check script ties the tests and checkers together. `CLAUDE.md` lists
  the commands to run by hand.

## Assumptions

1. **Home machine paths.** The plan names a conventions folder on another
   machine. This lane used the owner's home conventions folder,
   `~/Conventions/` (template `templates/CLAUDE.md`, catalog
   `code/KNOWN-BUGS.md`, checkers in `tools/`). Lane worktrees are named
   only as `~/TheConnection-lanes/<lane>`.
2. **Public repo.** On 2026-10-14 the owner said this repo is public. So
   no file here names the other machine's paths, the employer, or an email
   address. Two section 9 rules were reworded in `CLAUDE.md`, and the file
   says so above the list:
   - Rule 2: the commit address became "commits go out under the repo's
     configured personal identity". On this machine that identity comes
     from the global git config, not a path rule.
   - Rule 12: the other machine's conventions path became
     `~/Conventions/tools/`.
   The co-author trailer in rule 2 stays word for word; its address is the
   only address in the lane's files.
3. **G2 detail files.** `phases.md` names only `INDEX.md`. The lane
   coordinator allowed index plus detail files; the conventions template
   says "INDEX.md plus one detail file per entry", so there are three
   files.
4. **The shared catalog.** The two shared slugs are cited by name only. The
   copy in the owner's conventions folder has neither slug.
   `any-language/tests-and-checks.md` there has an entry titled "A check
   that passes by not checking." (error guards, missing fixtures) and
   nothing for `written-claim-outlives-the-code`. No text was invented or
   copied for either.
5. **Harness shape.** `tc`, `listener` and `fake_bin` are methods on the
   `TcRoot` object ("with that root"). The fake records the arguments
   after the program name, because the program name is the fake's path in
   a temp folder and changes every run; CARDS R4's expected argv
   (`queue --thread t1 ...`) has no program name either.
6. **`TC_*` stripping.** The harness drops every inherited `TC_*`
   variable, so a machine with `TC_ROOT` or `TC_CACHE_TTL_SECONDS` set
   cannot change a test. A test that wants one passes it through `env`.
7. **`CLAUDE.md` names files that land later in the lane.** At `f9b27cb`
   its layout lists `docs/known-bugs/` and `tests/_root.py`, which arrive
   in G2 and G3; its Status says so.
8. **Deviations: none.** Written as the brief asked. A reviewer could count
   two things as deviations: no `qa/bot/` (the plan's section 10 makes the
   unittest suite the scripted playthrough) and no wired check script.

## Pauses

- `pauses/GROUND-1.md`: `check_american.py` ignores the file it is given;
  `check_voice.py` skips phrases in any file named `CLAUDE.md`.
  Recommendation: the owner fixes the American checker in the conventions
  folder; until then use the coordinator's wrapper.
- `pauses/GROUND-2.md`: `fake_bin` has no test in the tree.
  Recommendation: a third test in `tests/test_root.py`.
- `pauses/GROUND-3.md`: files in the base commit (plan files, the board
  look kit, one commit message) name the employer and the work machine.
  Recommendation: scrub the files after this lane merges; the owner
  decides on the history.

## Checkers

- Voice: `python3 ~/Conventions/tools/check_voice.py <file>`, which reads
  the file it is given.
- American English: `python3 ~/TheConnection-lanes/tools/american-on.py
  <file>`, the lane coordinator's wrapper that runs `check_american.py`'s
  own word list on the named files. `check_american.py` itself was not
  used: it ignores its argument and scans only the conventions folder.
- `CLAUDE.md` phrases: `check_voice.py` skips them in a file of that name,
  so GROUND also ran the tool's own `check_file` with the exemption lists
  emptied (a scratch script, not in the repo). 0 failures on `CLAUDE.md`
  and on the three known-bugs files. Proved it bites: a scratch
  `CLAUDE.md` holding one banned phrase from `voice-rules.yaml` was clean
  under `check_voice.py` and failed under the scratch run.

## G3 mutation and the red run

Mutation, by hand in `tests/_root.py`, `listener()`: yield before polling
for the lock. Two lines inserted after `try:`, both tagged `MUTANT`:

```python
            yield proc.pid  # MUTANT: yield before polling for the lock
            return  # MUTANT
```

Command: `python3 -m unittest tests.test_root -v`, run 3 times. Red 3 of
3, exit 1 each time. The failing line (home prefix cut from the path):

```
FAIL: test_listener_holds_its_lock_at_yield_and_health_names_it (tests.test_root.RootTest.test_listener_holds_its_lock_at_yield_and_health_names_it)
  File "tests/test_root.py", line 103, in test_listener_holds_its_lock_at_yield_and_health_names_it
    self.assertIn(pid, holders,
AssertionError: 685800 not found in set() : at yield, pid 685800 does not hold /tmp/tc-test-a6b6mrj6/root/mail/.wait-b.lock; holders: set()
```

The second test failed too under the mutant, at line 130
(`'b' not found in {} : tc health --json lost the lock file for b`): the
listener was killed before it created its lock file. Each run ended
`Ran 2 tests ... FAILED (failures=2)`.

Restore: the two lines removed by hand. `sha256sum -c` against the hash
taken before the mutation printed `tests/_root.py: OK`; `grep -c MUTANT
tests/_root.py` printed `0`; the command above passed again, 2 tests OK.

## Hand check of the rest of the harness

A scratch script (not in the repo) ran under `python3 -X dev`. It invoked
each fake by absolute path, so no real `ssh` or `codex` could run. 13 of
13 passed, exit 0:

- `calls()` is `[]` before the fake runs.
- A PATH lookup limited to the fake's folder finds the fake.
- A codex fake exiting 0 records
  `{"argv": ["queue", "--thread", "t1", "--message", "MAIL: 1 unread for c"], "stdin": ""}`.
- An ssh fake exits 7 on both calls and records both, in order, with the
  body on stdin only.
- Two fakes keep separate records.
- `tc()` feeds stdin and keeps `TC_ROOT` when `env` sets another.
- A second listener for one name raises `ListenerNotProven` ("exited 3").
- A listener with mail already waiting raises it ("exited 0").
- A listener the test killed with SIGKILL itself is still reaped.
- After `TcRoot` exits, all 3 child pids are gone from `/proc` and the
  temp folder is removed.

`python3 -X dev -c "import sys; sys.path.insert(0, 'tests'); import _root"`
imports cleanly; `py_compile` on both files is clean.

## Verify commands and their output

Run in `~/TheConnection-lanes/ground` at `1d67c59`. Color codes stripped.

```
$ python3 ~/Conventions/tools/check_voice.py CLAUDE.md
clean: 0 failures, 0 warning(s), 1 file(s) checked.
$ python3 ~/Conventions/tools/check_voice.py docs/known-bugs/*.md
clean: 0 failures, 0 warning(s), 3 file(s) checked.
$ python3 ~/TheConnection-lanes/tools/american-on.py CLAUDE.md
american english: 0 hit(s) in 1 file(s)
$ python3 ~/TheConnection-lanes/tools/american-on.py docs/known-bugs/*.md
american english: 0 hit(s) in 3 file(s)
$ python3 -m unittest tests.test_root -v
test_listener_holds_its_lock_at_yield_and_health_names_it (tests.test_root.RootTest.test_listener_holds_its_lock_at_yield_and_health_names_it)
At yield the pid holds mail/.wait-b.lock, and tc health --json names it. ... ok
test_listener_pid_is_gone_after_its_context (tests.test_root.RootTest.test_listener_pid_is_gone_after_its_context)
After the context the pid is killed and reaped, and nothing holds the lock. ... ok

----------------------------------------------------------------------
Ran 2 tests in 0.472s

OK
$ python3 -m unittest discover -s tests -p 'test_*.py'
../usr/lib/python3.12/unittest/suite.py:107: ResourceWarning: unclosed file <_io.TextIOWrapper name=3 encoding='UTF-8'>
  for index, test in enumerate(self):
ResourceWarning: Enable tracemalloc to get the object allocation traceback
/usr/lib/python3.12/unittest/suite.py:107: ResourceWarning: unclosed file <_io.TextIOWrapper name=5 encoding='UTF-8'>
  for index, test in enumerate(self):
ResourceWarning: Enable tracemalloc to get the object allocation traceback
.............
----------------------------------------------------------------------
Ran 15 tests in 9.935s

OK
$ node --test tests/*.test.mjs
1..8
# tests 8
# suites 0
# pass 8
# fail 0
```

Baseline before the lane: discover ran 13 tests OK, node 8 pass. After:
15 OK (13 plus the 2 in `tests/test_root.py`), node 8 pass.

The discover run prints `ResourceWarning: unclosed file` twice. They come
from `tests/test_health.py` (it starts listeners with `stdout=PIPE` and
never closes the pipes): run alone it emits them, `test_keepalive.py` and
`test_root.py` alone emit none, and the base commit's suite prints the
same two. Not fixed: outside this lane.

## Not verified

- Anything under a real `codex` or `ssh`, or on a second machine. Agents
  never run those.
- `/proc/locks` matching on a filesystem whose `stat` device differs from
  the lock table's (btrfs subvolumes, overlay). The temp folder here is
  `/tmp` on the WSL2 root filesystem (ext4, `df -T /tmp`), where it
  matches; `tc` makes the same assumption.
- The 5 s ceiling under heavy load. The machine ran another long job
  (load about 5.7 on 32 cores); the 2-test suite, two listeners and their
  `tc health` calls included, finished in under 0.5 s every run.
- WSL1, and Linux kernels other than this WSL2 one.
