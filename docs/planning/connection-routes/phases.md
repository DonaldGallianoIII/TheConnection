# Connection routes: phases and tasks

Model:  Claude Opus 5.5 (the TheConnection architect session); the core
        test specs in CORE are a planning session's (Claude Fable 5.1)
        of 2026-10-14, kept as it wrote them where they still fit
Status: draft. Reviewed once by the planning session (Claude Fable 5.1,
        2026-10-14, 24 findings, all folded in)
Date:   2026-10-14

Each task: **files**, **do**, **out of scope**, **test** (property; input;
expected; must reject), **verify**, **PR**. Contracts are in
`contracts.md`. Rules are `00-index.md` section 9.

---

## GROUND (P0, wave 0)

Exit: an Opus agent given only a brief and the repo runs every test, reads
the rules, and knows the two known bugs.

### G1. Repo CLAUDE.md
- **Files:** `CLAUDE.md` (new).
- **Do:** fill in `~/Conventions/templates/CLAUDE.md` (the owner's template) for
  this repo: what it is; stdlib only; Linux and WSL2 only; the layout; the
  test commands (`python3 -m unittest discover -s tests -p 'test_*.py'` and
  `node --test tests/*.test.mjs`); the routing rule table from `00-index.md`
  section 1 word for word; the rules from section 9; commit identity is
  personal by path. Deviations from the conventions: none.
- **Out of scope:** README, JOIN.md.
- **Test:** none (prose). The voice and American checks are clean.
- **Verify:** both checkers print clean on `CLAUDE.md`.
- **PR:** Add the repo's CLAUDE.md: what tc is, how to test it, the routing rule, the agent rules.

### G2. Known-bugs index
- **Files:** `docs/known-bugs/INDEX.md` (new).
- **Do:** two entries, each with tier, times hit, how it showed, the check
  that catches it: `listener-reported-live-without-the-lock` (a Codex worker
  said "listening" about a `cmd &` its host had killed; the check is the
  pid in `/proc/locks`, never the claim) and
  `test-claimed-that-is-not-in-the-tree` (two commit messages cite 8 tests
  the repo never held; a claim names a file and a command or is not made).
  Note each is a form of the shared catalog's
  `check-that-passes-by-not-checking` and `written-claim-outlives-the-code`.
- **Verify:** checkers clean.
- **PR:** Start the known-bugs index with the two failures seen on 2026-10-14.

### G3. Shared test harness
- **Files:** `tests/_root.py` (new).
- **Do:** `TcRoot` context manager: a temp folder as `TC_ROOT`, removed in
  teardown. `tc(*args, stdin=None, env=None, timeout=10)` runs
  `[sys.executable, TC, *args]` with that root, stdin from `/dev/null` unless
  given, returns `(exit, stdout, stderr)`. `listener(name, timeout)` starts
  `tc wait` in the background, polls `/proc/locks` until the pid holds
  `mail/.wait-<name>.lock` (ceiling 5 s, never a bare sleep), yields the pid,
  and kills that pid in teardown. `fake_bin(name, exit_code)` writes a fake
  `codex` or `ssh` to a temp folder that records its argv and stdin to a
  file and exits with `exit_code`, and returns the folder to put first on
  `PATH` plus a reader for the recording.
- **Out of scope:** moving the existing health and keepalive tests onto it.
- **Test:** `tests/test_root.py`: a listener started through the harness is
  named by `tc health --json`; after the context exits its pid is gone. Must
  reject: a harness that returns before the lock is held (assert the pid is
  in `/proc/locks` at yield).
- **Verify:** `python3 -m unittest tests.test_root -v` shows 12 passed
  (the 2 above, plus 10 the review's fix round added for the env, the
  fakes, `start()` and teardown).
- **PR:** Add tests/_root.py: throwaway roots, a proven listener, fake ssh and codex.

---

## CORE (P1, wave 1)

Exit: every spec below passes, and each named mutation, applied by hand to
`tc`, turns its test red. CORE writes tests only; it never edits `tc`.
**CORE merges before CARDS.**

All in `tests/test_mailbox.py`, on `tests/_root.py`.

**If a CORE test finds a real bug in `tc`**, that is the point of it. Do
not edit `tc` and do not weaken the test. Write a pause naming the test,
the line in `tc` and what goes wrong; leave the test red on the branch;
list it in the handoff. The fix goes to CARDS or to its own fix brief.

| # | Property | Input | Expected | Must reject (mutation) |
|---|---|---|---|---|
| K1 | A message is read once | send `hi` a to b; read b; read b | first read prints a header starting `# #1 from a to b` and moves the file to `read/`; second prints `no unread mail for b` | a read that prints and leaves the file (comment out the rename) |
| K2 | A message appears only whole | load `tc` as a module (as `test_keepalive.py` does); wrap `pathlib.Path.rename` and `Path.write_text`; send once | the `.md` path is created only by a rename from a sibling ending `.tmp`; `unread()` never lists a `.tmp` | a send that writes the final name directly (white box, so it fails every run, not by timing luck) |
| K3 | The counter waits for its lock | the harness holds an exclusive flock on `mail/.seq`; `tc send` runs | the send has not finished after 1 s; it finishes within 1 s of the release | the counter read without the flock (the send would finish at once). A second check, not a mutation test: 50 senders at once get exactly 1 to 50 |
| K4 | Wait exit codes | mail waiting; `--timeout 1` with none; a second wait for the same name | 0 and a `MAIL:` line; 2 and a `TIMEOUT:` line; 3 and `ALREADY LISTENING` with the first pid still in `/proc/locks` | a wait that returns 0 with no mail |
| K5 | Log order is by number across inboxes | a to b, b to a, a to b | `tc log` shows #1, #2, #3 in that order | a log sorted by file time |
| K6 | Status | post twice; show with none posted | the second post replaces the first; `no status posted` | an append instead of a replace |
| K7 | Empty message refused | `tc send --from a --to b ""` | exit not 0, stderr `tc send: empty message`, no file | a send that writes an empty file |
| K8 | Peek does not mark read | peek b twice, then read b | both peeks show the message; read still shows it | a peek that moves the file |

Each assertion message carries the command and its captured output, so a
commit can point at a test by name.

- **Verify:** `python3 -m unittest tests.test_mailbox -v` shows 8 passed;
  the lane handoff lists each mutation and the red run it produced.
- **PR:** Add the core mailbox tests: send, read, peek, wait, log, status, the counter.

---

## CARDS (P2, wave 1)

Exit: a Claude session sends to a Codex session and the Codex wakes,
through `tc send` alone; a usage error exits 9, never 2. Proven by hand once (QA script, task D4), and by
the fake-codex tests always.

### R1. Names (C0)
- **Files:** `tc`, `tests/test_names.py`.
- **Do:** `valid_name()`; every command checks names first; exit 6.
- **Test:** property: no command writes anything for a bad name. Input:
  `tc send --from a --to ../x hi`, `tc read "a b"`, `tc wait ..`,
  `tc send --from a --to=-x hi`. Expected: exit 6, the C0 words, the
  root's file list unchanged. The leading dash case must use the `=` form:
  `--to -x` with a space never reaches `valid_name()`, because the parser
  reads `-x` as a flag and refuses first (exit 9 after R6, 2 before it).
  Today the `=` form gets through and makes `mail/to--x/` (seen by hand at
  b6a95d4). Test both forms; both write nothing. Must reject: a check on
  `--to` only (also test `--from` and `read`); a rule that lets a leading
  dash through.
- **Verify:** `python3 -m unittest tests.test_names -v`.

### R2. Cards and `tc join`, `tc card`, `tc cards` (C1)
- **Files:** `tc`, `tests/test_cards.py`.
- **Do:** as C1.
- **Test:** join with `CODEX_THREAD_ID=t1` in env gives kind codex, route
  codex, thread t1; with `CLAUDECODE=1 CLAUDE_CODE_SESSION_ID=s1 CLAUDE_PID=9`
  gives kind claude, route local, those ids; with neither and no
  `--account`, account is the word `unknown`. `--kind codex` with no
  `CODEX_THREAD_ID`: exit 1, no card. `tc card x --ssh u@h` gives route ssh
  and the default remote path. A second join of the same name overwrites
  and resets `joined_at`. `tc card x --ssh u@h` while `to-x` holds unread
  mail: refused naming the count; with `--force`: written. `tc card x --ssh
  -oProxyCommand=y`: exit 6, nothing written. With
  `CLAUDE_CODE_MESSAGING_TOKEN=secret123` in env, no value in the card
  contains `secret123`. `tc join b --reports-to a` stores `"reports_to":
  "a"`; a rejoin of `b` without the flag stores null; `tc join b
  --reports-to b` exits 6 with `cannot report to itself` and writes no
  card; `--reports-to ../x` exits 6. `tc cards` shows `reports to a`.
  Must reject: an empty account; a card written in place (assert the write
  goes through a `.tmp`); a join that copies the whole environment; a
  self-report written as a card.
- **Verify:** `python3 -m unittest tests.test_cards -v`.

### R3. The router, `deliver_local`, the two behavior fixes (C2, O1, O2)
- **Files:** `tc`, `tests/test_router.py`.
- **Do:** `ROUTES` (local and codex only), `Delivery(exit, words,
  warnings)`, `deliver_local`; the size limit (C0); the new-inbox warning;
  read and peek create nothing for an unknown name; a card naming a route
  not in `ROUTES` answers `route <route> is not built yet`, exit 1.
- **Test:** a send to a name with no card behaves exactly as K1 (run CORE's
  tests against this branch at review); a first send to `nobody` exits 0,
  prints the send line on stdout and the warning on stderr; a second send
  does not warn; `tc peek ghost` leaves the root's file list unchanged; a
  body of exactly 1 MiB is sent and one byte more is refused with exit 8,
  no file and no number used; an ssh card answers the not-built sentence.
  Must reject: a warning on every send; a size check after `next_seq()`
  (assert `.seq` unchanged after the refusal).
- **Verify:** `python3 -m unittest tests.test_router tests.test_mailbox -v`.

### R4. The `codex` route (C2)
- **Files:** `tc`, `tests/test_codex_route.py`.
- **Do:** `deliver_codex` as C2.
- **Test:** with a fake `codex` exiting 0: two sends to an empty codex
  inbox ring once, and the recorded argv is
  `queue --thread t1 --message MAIL: 1 unread for c...`; with the fake
  exiting 1: the send exits 0, the mail is in the inbox, stderr says
  `ring failed`. No ring for a claude card. Must reject: a test that passes
  because the fake was never called (assert the recording exists); a ring on
  every send; a send that fails because the ring failed. Also one recorded
  fixture of the real exit codes, labeled `matches Codex 0.162.1,
  2026-10-14` (0 queued, 1 unknown thread).
- **Verify:** `python3 -m unittest tests.test_codex_route -v`.

### R5. `tc health` shows cards
- **Files:** `tc`, `tests/test_health.py` (add a case).
- **Do:** a `cards` line in text and a `cards` key in `--json`: name, kind,
  account, route, reports_to.
- **Verify:** `python3 -m unittest tests.test_health -v`.

### R6. Usage errors exit 9 (D12)
- **Files:** `tc`, `tests/test_usage.py`.
- **Do:** a parser class whose `error()` prints the usage and the message
  to stderr and exits `EXIT_USAGE` (9), used by `main()` and inherited by
  every subparser. Add `EXIT_USAGE` beside the other exit constants.
- **Test:** `tc wait --timeot 1 b` exits 9 with `usage:` on stderr and no
  `TIMEOUT` on stdout; `tc wait b --timeout 1` still exits 2 with
  `TIMEOUT`; `tc` with no command exits 9; `tc frobnicate` exits 9;
  `tc send --to b hi` (no `--from`) exits 9 and writes nothing. Must
  reject: an override on the top parser only (the `wait` typo goes through
  the subparser, so it would still exit 2).
- **Verify:** `python3 -m unittest tests.test_usage -v`.
- **PR:** Make a usage error exit 9, so a mistyped listener cannot pass for a timeout.

SSH starts from SHARED's merge, not beside it: both edit `main()`'s
argparse block and `tc`'s doc block, and SHARED is small. SSH adds its
`"ssh": deliver_ssh` line to `ROUTES`.

Exit: mail crosses to a second machine and back by hand (QA, D4), and a
key behind `tc gate` can deliver mail and nothing else.

### S1. `deliver_ssh` and the outbox (C3)
- **Files:** `tc`, `tests/test_ssh_route.py`.
- **Test:** with a fake `ssh` exiting 0: the recorded argv is exactly the C3
  list, `-T` present and `--` right before the target; the body is the
  fake's stdin and not in its argv; exit 0. A name containing a quote:
  refused by C0 before ssh runs. Fake exiting 255: exit 4, one file in
  `outbox/`, stderr names `tc flush`. Fake exiting 7: exit 7, its stderr
  printed, `outbox/` empty. With one message already queued for the
  target, a new send does not call ssh at all (assert the recording is
  empty) and is queued behind it, exit 4. Must reject: the body on the
  command line; a remote command built by string joining without
  `shlex.join` (input: a remote tc path containing a quote; the fake must
  receive it quoted as one word); a refusal queued for retry.
- **Verify:** `python3 -m unittest tests.test_ssh_route -v`.

### S2. `tc flush` (C3)
- **Files:** `tc`, `tests/test_flush.py`.
- **Test:** three outbox files for one target, fake ssh exiting 255 on the
  second: the first moves to `outbox/sent/`, the second and third stay,
  exit 4. Fake fixed, flush again: all sent in seq order, exit 0. A file
  the far side refuses (fake exiting 6) moves to `outbox/refused/` with its
  stderr beside it. Must reject: a flush that skips a failure and sends the
  third first.
- **Verify:** `python3 -m unittest tests.test_flush -v`.

### S3. `tc gate` (C3)
- **Files:** `tc`, `tests/test_gate.py`.
- **Test:** `tc gate --as homebox-b` with
  `SSH_ORIGINAL_COMMAND="/x/tc send --from a --to b"` and a body on stdin
  delivers to b **as from `homebox-b`**, never as `a`, and the header line
  says `via ssh gate, key homebox-b`. Refused with exit 7 and nothing
  written: `rm -rf /`; `/x/tc send --from a --to b; id`; `/x/tc read b`;
  `/x/tc send --from a --to ../b`; `env TC_ROOT=/tmp /x/tc send ...`; an
  empty command; `tc gate` with no `--as`. A body over 1 MiB: exit 8.
  Must reject: a gate that runs anything else. Two checks: in process,
  patch `subprocess.*`, `os.system`, `os.spawn*`, `os.exec*`,
  `os.posix_spawn*` and `os.fork` to raise; and out of process, run the
  gate with `PATH` set to an empty folder and assert every refused case
  still exits 7 and writes nothing.
- **Verify:** `python3 -m unittest tests.test_gate -v`.

---

## SHARED (P3, wave 2, after CARDS merges)

Exit: a second Linux user in the group can send, read and wait on the same
mailbox (human QA, D4); modes are right by test.

### H1. `tc init --shared` and the umask (C4)
- **Files:** `tc`, `tests/test_shared.py`.
- **Test:** in a temp root, `tc init --shared --group <the user's own
  primary group>`: every folder has mode `2775` and that group; a message
  sent after is mode `0664`; a message and `mail/.seq` written **before**
  init are `0664` after it; `.shared` holds the group name. A group the
  user is not in: refused, nothing changed. `tc health` says `mailbox shared with
  group <g>`. Must reject: files at `0644` after init (the umask not set
  before the first write).
- **Verify:** `python3 -m unittest tests.test_shared -v`.

---

## BOARD (P4, waves 1 and 2)

Exit: the board draws the real mailbox and follows it as mail moves; it
refuses without the token; it binds nowhere but 127.0.0.1.

### B1. The feed (C5)
- **Files:** `board/serve.py` (new), `tests/test_board_feed.py`.
- **Test:** a temp root with two proven listeners (harness), a codex card
  and an ssh card **written by hand in C1's shape** (CARDS' code is not
  there yet), and three messages: four nodes, states `listening`,
  `listening`, `doorbell`, `remote`; three wires with the right from, to,
  seq; listener pids equal the harness pids. Kill one listener between two
  `feed()` calls on the same server object: it is `down` on the second. A
  status file's first line after the header shows, cut at 80. Must reject:
  a feed that opens message bodies (make bodies unreadable, mode `000`;
  the feed must still work).
- **Test, shapes (D7, C5 roles and levels)**, each a temp root with
  made-up names and hand-written cards:
  - star with hints (`b`, `c`, `d` report to `a`): `a` orchestrator level 0,
    the rest workers level 1, all `declared`.
  - chain with hints (`b` reports to `a`; `c`, `d` to `b`): levels 0, 1, 2,
    2; `a` and `b` orchestrators.
  - the same chain with no cards, mail only: `b` is the root and an
    `inferred` orchestrator, `a`, `c`, `d` its `inferred` workers. This
    pins the known limit, so a change to it is a decision, not a drift.
  - two orchestrators side by side (`x` over `x1`, `x2`; `y` over `y1`,
    `y2`; `x` and `y` mail each other): two level 0 orchestrators and a
    `mailbox` link between them.
  - a `reports_to` cycle (`p` reports to `q`, `q` to `p`): `p` level 0, `q`
    level 1, and `feed()` returns.
  - a `reports_to` naming nobody: the node is a root and keeps the name.
  - two orchestrators share a worker (`b` reports to `a` by card, and `x`
    also mails `b`): `b` appears once, at level 1 under `a`, and the
    `mailbox` link `b` and `x` is still in `links`.
  Must reject: a feed that picks one root for the whole board (the
  side-by-side case must give two level 0 nodes); a shared worker drawn
  twice or under the parent it only mails; a level walk with no
  cycle break (run the cycle case under a 2 s timeout); links taken from
  the last `WIRE_HISTORY` only (a pair whose only message is older than
  that must still have its link).
- **Verify:** `python3 -m unittest tests.test_board_feed -v`.

### B2. The server (C6)
- **Files:** `board/serve.py`, `tests/test_board_server.py`.
- **Test:** started on a free port: `/feed` without the token 401, with it
  200 and JSON; `Host: evil.example` 421; `POST /feed` 405;
  `/../tc` and `/mail/` 404; the listening socket's address is
  `127.0.0.1`. Must reject: a server bound to `0.0.0.0` (assert the address).
- **Verify:** `python3 -m unittest tests.test_board_server -v`.

### B3. `patchBoard` and the two new states (C5)
- **Files:** `board/look.js`, `board/theme.css`, `tests/board-patch.test.mjs`,
  `tests/board-layout.test.mjs`.
- **Test:** `patchBoard` over feed A then feed B (one node moved, one
  removed, one added, one wire new): the kept node is the same object, the
  removed one is gone, the new one exists; no rebuild (count create calls).
  The two new states have a glyph and a word, distinct from the others.
  Must reject: a patch that rebuilds everything (the kept node would be a
  new object). Pure functions only, so no DOM library is needed; split the
  diff from the drawing.
- **Test, layout (D7):** `layoutLevels` over the B1 shapes as feed JSON:
  two roots sit side by side in name order with no overlap; depth 3 stacks
  three rows; the cycle feed lays out; each title carries the role word,
  and `· inferred` exactly when `role_source` is `inferred`. Must reject: a
  layout that stacks every root in one column.
- **Verify:** `node --test tests/*.test.mjs`.

### B4. `live.html`
- **Files:** `board/live.html` (new), `qa/human/board-live.md` (new).
- **Do:** token from the URL fragment, poll `/feed` every 3 s, newest answer
  wins, `patchBoard`, the look switch, `?gray=1`. Clean up the timer on
  `pagehide`.
- **Verify:** the human script: start `serve.py`, open the printed URL, send
  a message between two test names, see the wire move within 3 s; in
  grayscale every state reads.

### B5. Leaks
- **Files:** `tests/test_board_leak.py`, `tests/board-leak.test.mjs`.
- **Test:** 1,000 `feed()` calls on one server object: RSS growth under
  `FEED_LEAK_LIMIT_KB` (2,048), measured from `/proc/self/status` the way
  the listener's 13 MB flat measurement was. `patchBoard` over 500 feeds
  that add and remove nodes: node and wire counts return to the baseline,
  and no removed node is still held by the board's maps. Must reject: a
  `last_listening_at` that grows without bound (feed 1,000 distinct names
  that come and go; the map is pruned past `DOWN_WINDOW_S`).
- **Verify:** both commands pass.

### B6. The demo shows the shapes (D7)
- **Files:** `board/demo-script.json`, `board/demo.html` if its loader
  needs it, `qa/human/board-look.md`.
- **Do:** the demo draws a two-level tree (`a` over `b` and `docs`; `b`
  over `c` and `d`) and a second orchestrator (`z` over `y1`, `y2`) that
  mails `a`. Made-up names only. Role words in every title.
- **Test:** `node --test tests/*.test.mjs` still passes; add a check that
  the script holds two level 0 orchestrators and one level 1 orchestrator.
- **Verify:** the human script gains a step: in `?gray=1`, each
  orchestrator reads as one by its word.

---

## DOCS (P5, wave 3, after every other lane merges)

Exit: someone who has never seen it forks the repo and gets two sessions
talking by following the README alone.

### D1. README
- **Files:** `README.md`.
- **Do:** lead with the routing rule (section 1 of the index), the headline
  case (several accounts, several SSH windows, one mailbox), and a "which
  route am I" chart. Then one section per route: local, codex (with the
  `--add-dir <mailbox>` line and why), ssh outbound, ssh inbound through
  `tc gate` (the `authorized_keys` line, and a plain warning never to add a
  key without the gate), the shared mailbox. Then commands, the board, limits.
  Keep "why it exists" honest: same-account Claude sessions should use the
  native path. And say in one sentence why that is not the whole answer even
  for one account: a session in a different permission mode holds a native
  message for its user's approval and can let it expire, and the mailbox is
  a record anyone can read on disk. The ssh section carries the way back
  (C3) as a numbered step on the far machine.
- **Verify:** checkers clean; every command shown in the README is run once
  against a temp root and its output matches what the README shows.

### D2. JOIN.md and JOIN-CODEX.md
- **Files:** `JOIN.md`, `JOIN-CODEX.md` (new).
- **Do:** JOIN.md gains `tc join <name> --account <label> --reports-to
  <relay>` (the relay that pointed it here), the re-arm rule from D12
  (re-arm only on exit 0 after reading the mail, or exit 2 for `TIMEOUT` or
  `KEEPALIVE`; on 3 one is already running, so start none; on any other
  code do not re-arm, and tell the relay), and the proven-listener rule (a listener is live when `tc health` names its pid).
  JOIN-CODEX.md: `tc join`, no listener, go idle, reply with `tc send`; the
  mail arrives as a queued message.

### D3. Decisions record
- **Files:** `docs/planning/connection-routes/decisions.md`.
- **Do:** add every open item Donald settled while the lanes ran.

### D4. Human QA per route
- **Files:** `qa/human/route-local.md`, `route-codex.md`, `route-ssh.md`,
  `route-shared.md`, `two-accounts.md`, `shapes.md` (new); results in
  `qa/results/`. `shapes.md` walks the three D7 shapes by hand under a
  temp `TC_ROOT` and checks the live board draws each.
- **Do:** step by step, what to type and what to see. `two-accounts.md` is
  the planner's measurement: two Claude accounts on this machine, neither
  lists the other with ListAgents, and `tc send` across them wakes the
  listener; it also records whether each account runs with its own
  `CLAUDE_CONFIG_DIR` (C1). `route-ssh.md` includes writing the return
  card on the far machine. Donald runs these, with real ssh and real
  codex; agents never do. The result files record what he saw.
