# Handoff: EMPTYROOT, an empty TC_ROOT refuses

Model:  Claude Opus 5.5 (the EMPTYROOT lane agent)
Status: unreviewed
Date:   2026-10-17
Branch: Claude-Development-TheConnection-EMPTYROOT, from
        Claude-Development-TheConnection at 26987a0
Where:  ~/TheConnection-lanes/emptyroot
Brief:  ~/TheConnection-lanes/briefs/EMPTYROOT.md

a2's ruling for the owner, from the brief: with `TC_ROOT` set but empty,
tc took the working folder as its mailbox and quietly made one wherever
it ran. Now an empty or whitespace-only `TC_ROOT` refuses with one line
and exit 9 before any command touches the disk. Unset keeps its meaning,
the folder tc is in.

## Commits

| Item | Commit | Subject |
|---|---|---|
| 1, 2, 3 | `ec54431` | An empty or whitespace-only TC_ROOT refuses, exit 9, before any command runs (EMPTYROOT) |
| 3 | the commit that adds this file | This handoff |

Line numbers below are at `ec54431`.

## Item 1: the refusal

1. `tc:9676` to `tc:9679`, first thing in `main()` after
   `invoked_name()`: if `TC_ROOT` is in the environment and its value
   `.strip()`s to nothing, print `ROOT_EMPTY_WORDS` to stderr and exit
   `EXIT_USAGE`. The parser is not built yet, so `.shared` is not read,
   no folder is made, and no command runs. A module load never calls
   `main()`, so the test loaders and `board/serve.py` load as before.
2. `tc:441` to `tc:445`, `ROOT_EMPTY_WORDS`, one line:

   ```
   tc: TC_ROOT is set but empty or only whitespace, so it names no mailbox folder. Unset it to use the folder tc is in, or set it to the mailbox's folder.
   ```

   `tc` is the invoked name (NAME), so a link named tconn says tconn.
3. `tc:427` to `tc:437`, the R2 comment above `ROOT_FROM`. It said
   `set, even empty (then ROOT is the working folder)`. Now it says an
   empty value still makes `ROOT` the working folder (or a folder named
   by the spaces under it) at import, but `main()` refuses it, so only a
   module load ever holds that `ROOT`: the test loaders, and
   `board/serve.py` (see For the architect, item 2).
4. One choice the brief left open: the check runs before the parser, so
   `tc --help` with an empty `TC_ROOT` refuses too. Nothing is read
   either way. Moving it after `parse_args()` would let help through, at
   the cost of the argument checks running first.

## Item 2: tests

`tests/test_usage.py:199` `EmptyRootTest`, two tests. The harness's
`tc()` always sets `TC_ROOT` to its root, so a new helper, `run_in`
(`tests/test_usage.py:182`), runs the child with the root's clean env
and a chosen working folder. Constants at `tests/test_usage.py:61` to
`tests/test_usage.py:76`.

1. `test_an_empty_tc_root_refuses_before_any_command_runs`
   (`tests/test_usage.py:211`): `send`, `wait` and `health` with
   `TC_ROOT=""` and `TC_ROOT="   "`, from an empty folder in the root's
   base. Each subTest checks one thing: exit 9, each of three word
   fragments, one stderr line, empty stdout, the working folder still
   empty. 6 runs, 42 subTests.
2. `test_an_unset_tc_root_still_uses_the_folder_tc_is_in`
   (`tests/test_usage.py:244`): a copy of tc in the root, run from the
   empty working folder with `TC_ROOT` unset, posts `tc status a here`.
   Checks exit 0, `status/a.md` beside the copy, the working folder
   empty.

### Red, before the fix

`env -u TC_ROOT PYTHONDONTWRITEBYTECODE=1 python3 -m unittest
tests.test_usage.EmptyRootTest`, with the tests in place and `tc` at
26987a0: 2 run, `FAILED (failures=40)`. Every subTest of the empty case
fails but two (send's stderr is one line on the old tc too). The unset
test passes, as it should on both. One of the red lines, from `health`
with spaces, shows what the old tc made:

```
AssertionError: Lists differ: ['   ', '   /mail', '   /mail/.box-b.lock'[292 chars]ead'] != []
```

### Green, after

`env -u TC_ROOT PYTHONDONTWRITEBYTECODE=1 python3 -m unittest
tests.test_usage`: `Ran 7 tests`, `OK`.

`env -u TC_ROOT python3 -m unittest discover -s tests -p 'test_*.py'`:
`Ran 370 tests in 251.719s`, `OK`, the two new tests among them. It
ran on the fix before one last comment-only edit (the R2 comment's
last line, naming `board/serve.py`); `tests.test_usage` ran again
after it, OK.

`node --test tests/*.test.mjs`: `# tests 68`, `# pass 68`, `# fail 0`.

### Mutation

On a scratch copy of `tc` and `tests/` in the session's scratch folder,
never in the worktree, with `PYTHONDONTWRITEBYTECODE=1`: the three-line
check in `main()` removed. `python3 -m unittest tests.test_usage`:
`FAILED (failures=40)`. The first red line:

```
AssertionError: 0 != 9 : stdout: 'sent #1 to b: /tmp/tc-test-g33_7y8w/work/mail/to-b/000001-from-a.md\n'
```

## Item 3: doc blocks

1. `main()`'s block, `tc:9651`: `@interacts` opens with the `TC_ROOT`
   check, `@deps` names `os.environ`, `ROOT_EMPTY_WORDS` and
   `EXIT_USAGE`, `@complexity` adds O(r) over the value's characters.
2. The module block has no exit 9 line of its own. The nearest are its
   layout line, `tc:10` to `tc:12`, which now says an empty or
   whitespace-only `TC_ROOT` makes every command refuse, exit 9, and
   the `EXIT_USAGE` constant's comment, `tc:460` to `tc:467`, which now
   lists this case under row 9.

## For the architect

1. Contract exit row 9 (`contracts.md`, the Exit codes table) should add:
   `a TC_ROOT set but empty or only whitespace, refused before any
   command runs with one line on stderr and no usage text`. Its last
   clause today, `the usage text goes to stderr`, is not true for this
   case: the brief asks for one line, and that is what tc prints.
2. `board/serve.py` loads tc as a module and never calls `main()`, so
   `python3 board/serve.py` with an empty `TC_ROOT` still serves the
   working folder as the mailbox (`board/serve.py:516` reads it as
   is). Outside this lane's work set; not changed. A one-line check at
   the serve's start would close it.
3. `tc gate` as a forced command with an empty `TC_ROOT` now exits 9
   with the line above, printed before `far_key_reads`. The line holds
   no path and no login, only the invoked name. The near side reads a
   far 9 as an unknown code, exit 11, and files the message in
   `refused/`.

## Not verified

1. Real ssh was not run (rule 5), and no test drives `tc gate` with an
   empty `TC_ROOT`. Item 3 under For the architect is read from the
   code and contract row 11, not run.
2. Nothing ran as a second Linux user.
