# Handoff: CORE (P1)

Model:  Claude Opus 5.5 (the CORE lane agent)
Status: unreviewed
Date:   2026-10-14
Branch: Claude-Development-TheConnection-CORE, from
        Claude-Development-TheConnection at 89bdd2e
Where:  ~/TheConnection-lanes/core

## Commits

| Task | Commit | Subject |
|---|---|---|
| K1 to K8 | `a9b0ffd` | Add the core mailbox tests: send, read, peek, wait, log, status, the counter. |
| Handoff | the commit that adds this file | Write the CORE handoff: the eight mutations and their red runs |

No amend, reset or rebase. Nothing pushed or merged. `tc` is not edited:
`git diff --stat 89bdd2e HEAD -- tc` prints nothing.

## What was built

`tests/test_mailbox.py`, one test per row of the K table in `phases.md`,
all on `tests/_root.py`. Every test runs under its own `TcRoot`. Every
assertion message carries the command (`$ tc ...`), its exit code, its
stdout and its stderr. K2's message carries the in-process argv, the
captured output and every recorded file creation and `rename` call.

| # | Test | What it checks |
|---|---|---|
| K1 | `test_k1_a_message_is_read_once` | Send `hi` a to b. The first `tc read b` starts `# #1 from a to b`, shows `hi`, leaves `mail/to-b/` with no `.md` and `read/` with exactly that message. The second read prints only `no unread mail for b`. |
| K2 | `test_k2_a_message_appears_only_whole` | tc loaded as a module with `TC_ROOT` set before the load (and every inherited `TC_*` dropped). The test first checks the module's `MAIL` is its own root, so a bad load stops before any write. For the one send through `main()` (with `sys.argv` patched), `os.open` with `O_CREAT`, `builtins.open` given a path in a mode that creates, `Path.write_text` and `Path.rename` are wrapped with `mock.patch.object` in a `contextlib.ExitStack`, all restored as the send returns or raises. Then: the recorder saw at least one creation; none was the final `.md`; exactly one rename made it; its source is a sibling ending `.tmp` that a recorded creation made fresh; the final name did not exist before that rename; the `.tmp`'s bytes at the rename equal the final file's; `unread()`, called inside the rename while the `.tmp` sits in the inbox, lists no `.tmp`. (K2 fix, Claude Opus 5.5, unreviewed: the recorder no longer leans on one write API, so CARDS' `os.open` writes are seen.) |
| K3 | `test_k3_the_counter_waits_for_its_lock` | Two subtests, each on a fresh root. (1) The test takes an flock on `mail/.seq` and proves its own pid holds it with `_root.flock_holders`. One send starts through `root.start()`. The test proves that pid is blocked on the lock (a `->` line in `/proc/locks`). The send is still running 1 s later; after the release it finishes within 1 s as `sent #1`. (2) The test holds `mail/.seq`, starts 50 sends, proves all 50 pids are blocked on the lock, releases it. All 50 exit 0, print exactly 1 to 50, the inbox holds messages 1 to 50, and `.seq` reads `50`. |
| K4 | `test_k4_wait_exit_codes` | With mail waiting for b, `tc wait b --timeout 5` exits 0 with a `MAIL:` line. `tc wait c --timeout 1` exits 2 with a `TIMEOUT:` line. With the harness's listener on d (proven in `/proc/locks`), `tc wait d --timeout 1` exits 3 and prints `ALREADY LISTENING`, and the listener's pid still holds `mail/.wait-d.lock` afterward. |
| K5 | `test_k5_log_order_is_by_number_across_inboxes` | Sends a to b, b to a, a to b. Then sets the three files' times backward by number (#1 newest), and checks it did. `tc log` headers read `(1, a, b), (2, b, a), (3, a, b)`. |
| K6 | `test_k6_status_replaces_and_says_none_posted` | `tc status` with none posted prints `no status posted`. After two posts for b, `tc status` shows `second post`, not `first post`, one `## b status` header, and `status/b.md` holds no trace of the first. |
| K7 | `test_k7_empty_message_refused` | `tc send --from a --to b ""` exits non-zero, stderr has the line `tc send: empty message`, and no file exists in any inbox, unread or read. |
| K8 | `test_k8_peek_does_not_mark_read` | Two `tc peek b` both show message #1 and `hi`; after them the message is still unread in `mail/to-b/`; `tc read b` still shows it. |

Runtime on this machine (32 cores, load near 15 from a long job): the
file runs in about 3.2 s. K3 takes about 1.3 s: 1.1 s for the one-send
check (1 s of it the hold the plan asks for) and 0.2 s for the 50 senders.
Five runs in a row were green, and `python3 -X dev -m unittest
tests.test_mailbox -v` printed no warning.

## What was not built

- No test for anything outside K1 to K8.
- No `qa/human/` script. The plan has none for CORE (section 10: the
  unittest suite is the scripted playthrough).
- The tests were not run against CARDS' branch. The plan has CARDS'
  review do that before CARDS merges.

## Assumptions

1. **K3's second check is a subtest, not a ninth test.** The verify line
   says 8 passed. The 50-sender check sits inside K3 as its second
   `subTest`, under its own root, so the count stays 8.
2. **K3's "not finished after 1 s" counts from the proven block.** The
   test first proves the send is blocked on `mail/.seq` in
   `/proc/locks`, then waits 1 s more. That is stricter than 1 s from
   start, and a send that is only slow to start cannot pass it.
3. **K3's "50 at once" is made real.** All 50 sends are held at the lock
   until `/proc/locks` shows every one blocked, then released together.
   So under K3's mutation the second check also goes red, at its gate
   (`finished while the test held .../mail/.seq`), not at the count. It is
   a second check, as the brief says, not a mutation test.
4. **K5 sets the file times backward.** Sends made in order get file
   times in number order, so a log sorted by time would pass. The test
   sets #1 newest and #3 oldest with `os.utime`, 100 s apart. That models
   a real case: a sender that takes its number and writes after a later
   one.
5. **K2 runs `main()`, not `cmd_send()`.** It patches `sys.argv` and
   calls `main()`, so it holds when CARDS changes what `cmd_send()` does
   inside (C2 keeps its arguments and its output for route `local`). It
   calls `unread(name)`, a name `contracts.md` lists as today's.
6. **K2 asserts a recorded creation made the `.tmp`.** It records
   `os.open` with `O_CREAT`, `open()` in a creating mode and
   `Path.write_text` (widened in `62d8a6d`, when CARDS moved to `os.open`
   with `O_EXCL` and `O_NOFOLLOW`). That proves the record sees tc's
   writes, so "never wrote the final name" cannot pass by not checking. A
   write path the record misses fails with a message saying to wrap what
   tc uses now. A direct write through `open(path, "w")` was run as a
   mutation in `62d8a6d` and went red.
7. **K7's "no file"** is read as no file in any inbox, unread or
   `read/`. K7 does not check whether the counter moved.
8. **K4 uses three names in one root**: b (mail waiting), c (no mail),
   d (the listener). The mail case passes `--timeout 5` as a ceiling only,
   under the harness's 10 s per command.
9. **Own constants, not the harness's internals.** The P0 fixer is
   changing `tests/_root.py` beside this lane. The file uses only
   `TcRoot`, `tc()`, `start()`, `listener()` and `flock_holders()` from
   it, and keeps its own copies of the 5 s ceiling, the 0.05 s poll, the
   `TC_` prefix and the path to `tc`.
10. **The in-process load writes bytecode.** Loading `tc` as a module
    leaves `__pycache__/tccpython-312.pyc` at the repo root. It is
    gitignored, and `tests/test_keepalive.py` already writes the same
    file. Left in place (rule 3).

## Pauses

None. No test found a bug in `tc`: all 8 pass on the branch base's `tc`.
No question came up that the brief and the plan did not answer.

## The eight mutations and their red runs

Each mutation was one edit to `tc`, made by hand with an editor, tagged
`MUTANT`. Before the first, `sha256sum tc` was saved to a scratch file
(not in the repo). For each mutation:

1. `git diff --stat -- tc` showed the edit.
2. `python3 -m unittest tests.test_mailbox -v` ran (three times for K2
   and K3, once for the rest). Every run exited 1.
3. `git -C ~/TheConnection-lanes/core checkout -- tc` restored it.
4. `sha256sum -c` printed `tc: OK`, and `git diff --stat -- tc` printed
   nothing.

Each mutation turned only its own test red; the other seven passed every
time. Line numbers are in `tests/test_mailbox.py` at `a9b0ffd`. Below,
the temp root is cut to `<root>`, a pid to `<pid>`, and a timestamp to
`<time>`.

| Test | Mutation (tc at 89bdd2e) | Result | Red line |
|---|---|---|---|
| K1 | `cmd_read`, lines 144 to 145: the rename loop commented out | `FAILED (failures=1)` | line 309: `AssertionError: Lists differ: [PosixPath('<root>/mail/to-b/000001-from-a.md')] != []` (message: `the first read left the message unread`) |
| K2 | `cmd_send`, lines 127 to 128: `path.write_text(...)` in place of `tmp.write_text(...)`, and the rename commented out | `FAILED (failures=1)`, 3 of 3 runs | line 403: `AssertionError: PosixPath('<root>/mail/to-b/000001-from-a.md') unexpectedly found in [PosixPath('<root>/mail/to-b/000001-from-a.md')] : send wrote the final name 000001-from-a.md directly` |
| K3 | `next_seq`, line 111: `fcntl.flock(f, fcntl.LOCK_EX)` commented out | `FAILED (failures=2)`, 3 of 3 runs: both subtests | line 452, raised at line 280: `AssertionError: $ tc send --from a --to b hi: pid <pid> finished while the test held <root>/mail/.seq, so it never waited for the lock`. The 50-sender subtest: line 501, raised at line 280: `AssertionError: 50 senders to b: pid <pid> finished while the test held <root>/mail/.seq, so it never waited for the lock` |
| K4 | `cmd_wait`, line 168: `if msgs:` made `if msgs is not None:` (a wait that returns 0 with no mail) | `FAILED (failures=1)` | line 564: `AssertionError: 0 != 2 : a wait with no mail did not exit 2` (its stdout: `MAIL: 0 unread for c. Run: tc read c`) |
| K5 | `cmd_log`, line 194: sort key `p.name` made `p.stat().st_mtime` | `FAILED (failures=1)` | line 609: `AssertionError: Lists differ: [(3, 'a', 'b'), (2, 'b', 'a'), (1, 'a', 'b')] != [(1, 'a', 'b'), (2, 'b', 'a'), (3, 'a', 'b')]` (message: `tc log is not in number order across inboxes`) |
| K6 | `cmd_status`, line 189: `write_text` made `open(..., "a").write(...)` | `FAILED (failures=1)` | line 635: `AssertionError: 'first post' unexpectedly found in ['## b status, <time>', '', 'first post', '## b status, <time>', '', 'second post', ''] : the first post still shows` |
| K7 | `cmd_send`, lines 122 to 123: the empty-message check commented out | `FAILED (failures=1)` | line 654: `AssertionError: 0 == 0 : an empty message was not refused` (its stdout: `sent #1 to b: <root>/mail/to-b/000001-from-a.md`) |
| K8 | `cmd_peek`, after line 151: the read's rename loop added | `FAILED (failures=1)` | line 677: `AssertionError: Lists differ: [] != [(1, 'a', 'b')]` (message: `the second peek does not show message #1`; its stdout: `0 unread for b`) |

K1's mutant is caught at the first read's file check (line 309), before
the second read's `no unread mail` check runs. Both are the property the
row names.

## Verify command and its output

Run in `~/TheConnection-lanes/core` at `a9b0ffd`:

```
$ python3 -m unittest tests.test_mailbox -v
test_k1_a_message_is_read_once (tests.test_mailbox.MailboxTest.test_k1_a_message_is_read_once)
K1. Send hi a to b; read b twice. The first read shows it and moves it; the second says none. ... ok
test_k2_a_message_appears_only_whole (tests.test_mailbox.MailboxTest.test_k2_a_message_appears_only_whole)
K2. One in-process send: the .md is made only by a rename from a .tmp sibling. ... ok
test_k3_the_counter_waits_for_its_lock (tests.test_mailbox.MailboxTest.test_k3_the_counter_waits_for_its_lock)
K3. The counter waits for its flock; and 50 senders at once get exactly 1 to 50. ... ok
test_k4_wait_exit_codes (tests.test_mailbox.MailboxTest.test_k4_wait_exit_codes)
K4. Mail waiting: 0 and MAIL. None in 1 s: 2 and TIMEOUT. A second wait: 3 and ALREADY LISTENING. ... ok
test_k5_log_order_is_by_number_across_inboxes (tests.test_mailbox.MailboxTest.test_k5_log_order_is_by_number_across_inboxes)
K5. a to b, b to a, a to b: tc log shows #1, #2, #3 in that order. ... ok
test_k6_status_replaces_and_says_none_posted (tests.test_mailbox.MailboxTest.test_k6_status_replaces_and_says_none_posted)
K6. With none posted, tc status says so; a second post replaces the first. ... ok
test_k7_empty_message_refused (tests.test_mailbox.MailboxTest.test_k7_empty_message_refused)
K7. tc send --from a --to b "": exit not 0, stderr says empty message, no file. ... ok
test_k8_peek_does_not_mark_read (tests.test_mailbox.MailboxTest.test_k8_peek_does_not_mark_read)
K8. Peek b twice, then read b: both peeks and the read show the message. ... ok

----------------------------------------------------------------------
Ran 8 tests in 3.194s

OK
```

The whole suite, same tree:
`python3 -m unittest discover -s tests -p 'test_*.py'` ran 33 tests, OK
(the 25 before this lane plus these 8). It prints the two
`ResourceWarning: unclosed file` lines GROUND's handoff traced to
`tests/test_health.py`; `tests/test_mailbox.py` alone under `-X dev`
prints none. `node --test tests/*.test.mjs` passed 8 of 8.

Checked twice, after the mutation runs and again after the last discover
run: the worktree held no `mail/` or `status/`, and `/tmp` held no
`tc-test-*` folder.

## Not verified

- These tests against CARDS' `tc`. They are written to hold across O1
  and O2 (no assertion on a send's stderr; none needs read or peek to
  create an inbox), but they were not run on CARDS' branch.
- These tests on the P0 fixer's `tests/_root.py`. They use only the
  documented calls, but were run only on the harness at `89bdd2e`.
- K2 against a rename made with `os.replace` or `Path.replace`: it
  would fail loudly at "not made by exactly one rename", a false red,
  not a false pass. Not run.
- The 50-sender count against a lock misused rather than missing (taken
  after the read, or dropped before the write). Not a mutation test; not
  run.
- K3's 1 s release ceiling at a much higher load. Measured only at a load
  near 15 on 32 cores.
- Filesystems other than ext4 on this WSL2 kernel, and WSL1.
