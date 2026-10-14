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
| Round 1 (a) | `1cd7dc9` | Match CLAUDE.md to the current plan and list its real deviations |
| Round 1 (b) | the commit that adds the "Review round 1" section | Settle GROUND-3 and half of GROUND-1, and cut the handoff to match |
| Round 1 (c) | the commit after (b) | Harden the test harness: a clean child env, refusing stubs, start(), per-call fakes |

No amend, reset or rebase. Nothing pushed or merged. Review round 1
changed some of what follows; the "Review round 1" section at the end
says what, and it wins where the two differ.

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

- At G3, no test for `fake_bin`, `tc()` or the listener's failure
  branches was in the tree; the spec named 2 tests, and the rest was
  checked by hand (below). Round 1 (c) added tests for `fake_bin` and
  `tc()` and for one listener failure branch (mail already waiting), and
  pause GROUND-2 is settled. The other two branches (a `tc wait` that
  exits first, the 5 s ceiling) still have no test.
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
   address. At G1, two section 9 rules in `CLAUDE.md` were reworded for
   that (the commit identity in rule 2, the conventions path in rule 12).
   Review round 1 replaced the block with the dev branch's current
   section 9, all 13 rules, word for word; none needs rewording now. The
   co-author trailer in rule 2 is the only address in the lane's files.
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
8. **Deviations.** G1 wrote "None." as its brief asked. Review round 1
   (LOW-3) lists the three real ones in `CLAUDE.md`: no check script, no
   `qa/bot/` (the plan's section 10 makes the unittest suite the scripted
   playthrough), and the plan's uppercase lane ids in handoff and pause
   file names (LOW-11, accepted, not renamed).

## Pauses

- `pauses/GROUND-1.md`: half settled. `check_american.py` now scans the
  paths it is given (conventions commit `918e260`). Open, and the
  owner's: `check_voice.py` skips phrases in any file named `CLAUDE.md`,
  so a `CLAUDE.md` is voice-checked through a copy under another name.
- `pauses/GROUND-2.md`, settled (architect, 2026-10-14): option 1.
  `tests/test_root.py` tests `fake_bin` (per-call exit codes, stderr, the
  record, a fake ahead of the refusing stub).
- `pauses/GROUND-3.md`, settled: files in the lane's base named the
  owner's employer; `7e87e0e` on the dev branch scrubbed the tree;
  rewriting history is the owner's call (D11).

## Checkers

- Voice: `python3 ~/Conventions/tools/check_voice.py <file>`, which reads
  the file it is given.
- American English: `python3 ~/Conventions/tools/check_american.py
  <file>`, which reads the files it is given and exits 1 on a hit. Round
  1's runs are in its section.
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

## Review round 1

Fixer: Claude Opus 5.5, a session apart from the builder, working from
the fix brief for audit `2026-10-14-1554-standard`: 20 items covering
MEDIUM-1, MEDIUM-2, LOW-1 to LOW-10, LOW-12 to LOW-16, REC-2, REC-3 and
REC-5. LOW-11 is accepted as a deviation, not renamed. The audit folder
is gitignored (`bade20a`), so it is not in the tree.

**`CLAUDE.md` and `docs/known-bugs/INDEX.md`** (`1cd7dc9`):

- The rules block is section 9 of the dev branch's `00-index.md`, all 13
  rules, word for word, so it names no cloud vendor, and the off-limits
  line names none either. The routing section adds the D7 "Any shape"
  block under the D1 table, word for word. Both blocks were diffed
  against the plan file: identical.
- Exit codes point at the one table in `contracts.md`, and say that a
  usage error exits 2 today, like a `wait` timeout, until CARDS R6 (D12).
- The in-process note says tc fixes `ROOT`, `MAIL`, `STATUS` and
  `SEQ_FILE` at import, so `TC_ROOT` goes in `os.environ` before the load.
- `check_american.py` is called directly. One line says the
  `~/Conventions/` tools live on the owner's machine, and a fork without
  them skips those checks or brings its own.
- Deviations lists three; Status reflects D8. `INDEX.md` names its tenth
  part, Shared catalog.

**The pauses and this handoff** (the commit that adds this section):
GROUND-3 is settled and cut to three sentences. GROUND-1 is settled for
its American English half; its `CLAUDE.md` half stays open, the owner's.
This handoff drops the retired checker and the long GROUND-3 passage.
GROUND-2's question (no test for `fake_bin`) is answered by the harness
commit below. The pause file was outside round 1's work set; `89bdd2e`,
after the merge, marked it settled.

**`tests/_root.py` and `tests/test_root.py`** (the commit after this one):

- No child gets `TC_*` or the eight names in `CHILD_ENV_DROP`: C1's five
  identity variables, the native path's socket and token, and
  `SSH_AUTH_SOCK`. Other inherited variables pass through. In `tc()` and
  `start()`, a key in `env` set to `None` is unset for that call.
- `__enter__` writes refusing `ssh` and `codex` stubs to `refuse/` and
  puts that folder first on every child's PATH. A stub prints `real
  <name> is not allowed in tests` and exits 97 (`REFUSED_EXIT_CODE`).
  `fake_bin()` puts its own folder ahead of the stubs. A PATH passed in
  `env` is guarded the same way, so the stubs always sit ahead of the
  system's folders; unsetting PATH raises `ValueError`.
- `fake_bin(name, exit_code, stderr="")`: `exit_code` is an int or a
  list (one per call, the last repeats), `stderr` is written on every
  call, and the call count is taken under the record's flock. The fake is
  a `/bin/sh` wrapper that `exec`s the interpreter on a recorder script,
  both paths quoted with `shlex.quote`.
- `start(*args, stdin=None, env=None)` starts a background tc child,
  registers it for teardown, and returns the Popen. Its stdout and stderr
  are text pipes; its stdin comes from a file, so feeding it never blocks.
- `listener()` raises `ListenerNotProven` before starting `tc wait` when
  the name already has unread mail. The deadline is checked before each
  read of `/proc/locks`, so the ceiling allows at most 100 reads.
- Teardown kills and reaps every child even when one times out, then
  raises one `ChildNotReaped` naming each that did. If the test's own
  exception is already on its way out, the failure goes to stderr
  instead, in the listener and in `__exit__` alike. The listener drops its
  Popen from the child list; `__exit__` clears the list and the env.
- Doc blocks: every `@complexity` names its variables and bounds (the
  class enters in O(e + p); a listener makes at most P = 100 reads), and
  every `@alloc` matches the code.
- `tests/test_root.py` gains 10 tests, one per behavior, 12 in all.

**Why no test for a space in the interpreter's path.** The defect was the
shebang line: the kernel splits `#!/a path/python3` at the first space.
The fake's shebang is now the fixed `#!/bin/sh`, so no interpreter path
reaches the kernel's parser. The path is a quoted word on the `exec`
line, and that quoting is `shlex.quote`'s, which the standard library
tests. A test with a spaced path would prove the library, not the
harness. Every fake in the tests runs in the wrapper form.

**Mutations.** Each is one exact edit to `tests/_root.py` made by a
scratch script (not in the repo), then the one test run, then the file
restored from a copy: `sha256sum -c` printed `OK` and `grep -c MUTANT`
printed `0`. Each run exited 1 with `FAILED (failures=1)`:

| Test | Mutation | Red line (paths and pids cut) |
|---|---|---|
| `identity_variables_never_reach_a_child` | drop only `TC_*` | `AssertionError: {'CLAUDE_CODE_SESSION_ID': 'planted-by-tes[...]OCK'} != {}` |
| `none_unsets_a_key_for_one_call` | skip a `None` key | `AssertionError: 'HARNESS_TEST_PLAIN_KEY' unexpectedly found in {...}` |
| `listener_refuses_a_name_with_mail_waiting` | no waiting-mail check | `AssertionError: 'not started' not found in "tc wait b (pid ...) exited 0 without holding ..."` |
| `teardown_reaps_every_child_when_one_times_out` | the old loop, stopping at the first failure | `AssertionError: True is not false : pid ... still in /proc: teardown stopped at a failure` |
| `listener_cleanup_failure_keeps_the_tests_own_exception` | the listener's teardown always raises | `AssertionError: ChildNotReaped('1 child(ren) still unreaped 5 s after SIGKILL: ...') is not an instance of <class 'tests.test_root.Planted'>` |
| `fake_gives_each_call_its_exit_code_and_stderr` | the fake ignores the call count | `AssertionError: Lists differ: [0, 0, 0, 0] != [0, 255, 0, 0]` |
| `started_children_are_dead_after_the_root_exits` | `start()` does not register its child | `AssertionError: True is not false : pid ... still in /proc after TcRoot exited` |
| `start_feeds_stdin_and_hands_back_the_output` | `start()` drops `stdin` | `AssertionError: 1 != 0 : tc send exited 1: tc send: empty message` |
| `bare_ssh_and_codex_hit_the_refusing_stub` | the stubs never go on PATH | ``AssertionError: False is not true : `ssh` resolved to /usr/bin/ssh, outside the test's temp folder: the real tool would have run`` |
| `a_fake_goes_ahead_of_the_refusing_stub` | `fake_bin()` leaves its folder off PATH | `AssertionError: False is not true : .../calls.jsonl missing: the fake never ran` |

Under the stub mutation the probe reported the real tool's path and did
not run it: the probe runs a tool only when it resolves inside the
test's temp folder.

**Round 1 runs**, in `~/TheConnection-lanes/ground` on the final harness:
`python3 -m unittest tests.test_root -v` ran 12 tests, OK;
`python3 -m unittest discover -s tests -p 'test_*.py'` ran 25, OK, with
the two `tests/test_health.py` warnings noted above; `node --test
tests/*.test.mjs` passed 8 of 8. `check_voice.py` and `check_american.py`
were clean on every Markdown file round 1 changed, and on a copy of
`CLAUDE.md` under another name.

**Not done in round 1:** REC-1, REC-4, REC-6, REC-8, REC-9, LOW-17 as a
finding (the new recorder imports one module per line anyway), and
DEBT-1. REC-7 was settled before the round by `bade20a`, which keeps
`audits/` out of the repo. A test of `__exit__`'s stderr path (a reap timeout while the
test's own exception is on its way out) is not in the tree; the listener's
copy of that path is tested.
