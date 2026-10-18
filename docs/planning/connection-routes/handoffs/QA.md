# Handoff: QA, tc qa streams a QA walk to a session

Model:  Claude Opus 5.5 (the QA lane agent)
Status: unreviewed
Date:   2026-10-18
Branch: Claude-Development-TheConnection-QA, from
        Claude-Development-TheConnection at fdeb9fa
Spec:   contract C8, word for word (decision D45)

## Commits

| Slice | Commit | Subject |
|---|---|---|
| 1 | `ffa2dad` | Add tc qa's event record and redaction (C8, D45), slice 1 |
| 2 | `30bfd7c` | Add tc qa's log follower and filters (C8), slice 2 |
| 3 | `da26117` | Add tc qa's batching, caps and delivery through tc's router (C8), slice 3 |
| 4 | `6a4906b` | Add tc qa's run lifecycle, checklist and results.md (C8), slice 4 |
| 5 | `ce7dfdd` | Add tc qa's endpoint and the run, note and stop commands (C8), slice 5 |
| 6 | `b497c3e` | Add tc qa's checklist page (C8), slice 6 |
| report | `6ca474d` | Keep QA's tag on a scrubbed tc report page (C7, D45) |
| docs | `2fce2fd` | Document tc qa in the README and the owner's walk (C8, D45) |
| fix | `3df0513` | Store nothing for an event that races a run's end (C8) |
| fix | `d81633b` | Check the status before the words in tc qa's ended-run tests |
| fix | `ae6c5a8` | Write tc qa's control-character patterns as escapes, not raw characters |
| test | `6306afa` | Test tc qa's events.jsonl cap (C8) |
| handoff | the commit that adds this file | This handoff |

## What changed

- New `board/qa.py`: the whole of tc qa. The event record and redaction,
  the log follower and the filters, batching and the caps, delivery
  through tc's router, the run's files and the one-live-run lock, the
  checklist and results.md, the endpoint, and the three commands.
- New `board/qa.html` and `board/qa.js`: the checklist page.
- `tc`: the `qa` parser entries, `QA_SOURCE`, `QA_LEVELS`,
  `QA_DEFAULT_PORT`, `QA_MISSING_WORDS` and `cmd_qa` (a thin loader, as
  `cmd_report` is), and the module doc block's layout, `@interacts`,
  `@complexity`, `@alloc` and `@rng` lines. Nothing else in tc.
- `board/report.py`: QA joins `SCRUB_TAGS`. Nothing else.
- `.gitignore`: `qaruns/` (with its one-line attribution comment).
- New `tests/test_qa.py` (46 tests) and `tests/qa.test.mjs` (10 tests).
- `tests/test_readme.py`: the QA chain and mapping rule 9's port 8790.
- `tests/test_report.py`: two lines, outside the work set, under pause
  QA-2 (see below).
- `README.md`: the QA streaming section, three Commands rows, and QA in
  the report section's list of kept tags.
- New `qa/human/qa-streaming.md`, the owner's walk.
- Pauses `QA-1` (the sender name) and `QA-2` (the test_report edit).

## Where each item is (line numbers at `6306afa`)

1. **The run.** `run_main` (`board/qa.py:2446`): the name check (tc's
   `require_names`, exit 6), `--port 80` refused as a usage error, then
   `prepare` (`:1820`: filters, `--redact`, the checklist; a usage error
   or an unreadable file makes nothing), the live lock (`claim`,
   `:1282`), the socket, `open_run` (`:1848`), the URL line, the loop
   (`TICK_SECONDS`, `:2312`), `QaRun.end` (`:1768`), then
   `ENDED_LINGER_SECONDS` (`:2316`). Sources: `LogFollower` (`:448`,
   from the end, a rotation drained then followed, a truncation read from
   the start, a log made late read from its start); the endpoint's
   `/event` (`QaRun.post`, `:1644`); `tc qa note` (`note_main`, `:2398`);
   the page's `/check` (`QaRun.mark`, `:1670`). Filters: `parse_filter`
   (`:616`) and `Filters` (`:650`), K=V on a field (or the event's own
   tag, level or src) or /re/ on the text, and `--level`. One live run:
   the flock on `qaruns/.live.lock`, held for the run's life; a second
   run refuses naming the first (`LIVE_WORDS`); `find_live` (`:1318`)
   and `claim` clear a stale run with words (`clear_stale`). Ending:
   Ctrl+C or SIGTERM (`Stopper`, `:2339`), `tc qa stop`, or Finish
   (`QaRun.finish`, `:1702`); `end` reads the logs once more, mails the
   last batch, refuses posts and marks from then on, sends the summary
   and marks results.md and run.json ended.
2. **Delivery.** `Stream` (`:855`): every event to `EventsFile` (`:796`);
   `can_mail` (`:901`) holds the caps; `add` (`:913`) flushes at once on
   an error-level event, a checklist fail, or `BATCH_MAX_EVENTS`; `due`
   and `take` batch on `BATCH_SECONDS`; the next mail's first line counts
   what the caps kept back. `router_delivery` (`:1012`) calls
   `tc.deliver_once` as `tc send` does, so routes, refusals and words
   are tc's; a busy router's `sys.exit` becomes an answer and the run
   goes on. Every constant (`BATCH_SECONDS`, `BATCH_MAX_EVENTS`,
   `MAILS_PER_MINUTE_MAX`, `RUN_MAILS_MAX`, `EVENTS_FILE_MAX_BYTES`,
   `POST_MAX_BYTES`, ...) has its why beside it. The clock and the sleep
   are passed in (`main`, `:2517`, picks the real ones; nothing past it
   reads the wall clock).
3. **Safety.** `QaHandler` (`:1956`): `host_ok` (`:2022`, 421),
   `token_ok` (`:2034`, constant-time, 401), POST on `/event` and
   `/check` only (`do_POST`, `:2198`; 405 elsewhere, 404 for a path never
   served), `read_body` (`:2171`, 411 with no length, 413 over
   `POST_MAX_BYTES` before reading). `QaServer` (`:2238`) binds serve.py's
   `BIND_HOST` (127.0.0.1) and reuses its `DeadlineSocket`, loaded from
   source. Redaction before storage and mail: `make_event` (`:362`) runs
   `clean` (`:173`), `Redactor` (`:241`) and the caps on every string;
   the raw line is never kept. Mail lines start `| ` under
   `DATA_HEADER`. No event text reaches a shell, a tc argument or a path:
   it goes into the message body only.
4. **The page.** `board/qa.js`: `KEY_HELP` (`:70`), `MARKS` (`:62`),
   `STATE_WORDS` (`:79`), `keyAction` (`:104`), `nextUnmarked` (`:117`),
   `markRequest` (`:140`), `createPage` (`:176`), built through `el`
   (`:153`), which refuses an `html` prop. A mark after the end is
   refused on the page and on a 409. `board/qa.html`: the 44 px
   `--tap` token (`:25`), the chosen mark filled with a heavy outline
   (`:103`), both themes, reduced motion (`:129`), one column.
5. **note and stop.** `note_main` (`:2398`) and `stop_main` (`:2420`)
   find the run through run.json (`find_live`); no live run is exit 1
   with words.
6. **README.** `README.md:802`, three blocks; the Commands rows at
   `:598`. `tests/test_readme.py:1037` runs all three.
7. **Tests.** Below.
8. **Mutations.** Below.
9. **QA.** `qa/human/qa-streaming.md`, with the grayscale look at 390 px
   (step 14).
10. **Doc blocks and headers** on every new file and function; the tc
    doc block names the new folder and the new behavior.

## Red, then green

Each slice's tests were run against a stub first and seen red on their
assertions, then green on the code. Every count below was read from that
run's printed output.

| Slice | Red | Green |
|---|---|---|
| 1 | `Ran 8 tests`, `FAILED (failures=13)`: 7 of 8 tests | `Ran 8 tests`, `OK` |
| 2 | `Ran 14 tests`, `FAILED (failures=14)`; then, follower built, `FAILED (failures=9)` on the filter counts | `Ran 14 tests`, `OK` |
| 3 | `Ran 24 tests`, `FAILED (failures=10)` | `Ran 24 tests`, `OK` |
| 4 | `Ran 33 tests`, `FAILED (failures=15)` | `Ran 33 tests`, `OK` |
| 5 | `Ran 44 tests`, `FAILED (failures=35)` | `Ran 44 tests`, `OK` |
| 6 (node) | `# tests 10`, `# pass 1`, `# fail 9` | `# tests 10`, `# pass 10`, `# fail 0` |
| report | `FAILED (failures=1)` (every QA dot read `other`) | `OK` |

Three guards cannot go red against a stub, since a stub that does
nothing passes them: the over-redaction test, the innerHTML and host
scan, and the README chain's words. Each was shown red by a mutation
instead (rows 7 to 9 below), and the events.jsonl cap test by a fourth.

Two first red runs errored instead of failing (an IndexError on an
empty inbox, a TypeError before the first assertion); each test then
gained an assertion on the count first and was run red again on that
assertion. The table shows the second runs.

## Mutations

Each on a scratch copy made by `git archive` at `d81633b` (the cap
mutation at `6306afa`'s test), run with `PYTHONDONTWRITEBYTECODE=1`,
each red on an assertion:

| # | Mutation | Test | Red line |
|---|---|---|---|
| 1 | redaction skipped (`Redactor.text` returns its input) | DeliveryTest planted kinds, RedactTest | `AssertionError: 'hunter2-sunrise' unexpectedly found in '# #1 from qa to a, ...` (`FAILED (failures=16)`) |
| 2 | the rate cap removed | `test_the_rate_cap_holds_back_mail...` | `AssertionError: 6 != 4` |
| 3 | the error flush removed | `test_an_error_event_flushes_at_once` | `AssertionError: 0 != 1` |
| 4 | the token check removed | `test_no_token_401_a_wrong_host_421...` | `AssertionError: Tuples differ: (200, {'ok': True, 'kept': True}) != (401, b'')` |
| 5 | the one-live-run check removed (no flock) | `test_a_second_run_refuses_naming_the_first...` | `AssertionError: Refused not raised` |
| 6 | a mark after the end accepted | `test_a_mark_after_the_end_is_refused...` | `AssertionError: 200 != 409` |
| 7 | the base64 rule redacts every run | `test_short_words_paths_and_snake_case_names_are_kept` | `AssertionError: '[redacted]' != 'test_checkout_with_an_expired_card_fails'` |
| 8 | the word innerHTML in qa.js | node test 9 | `not ok 9 - the page and its script hold no innerHTML...`, `error: 'qa.js holds innerHTML'` |
| 9 | the README's note line reworded | the README QA chain | `AssertionError: unexpectedly None` |
| 10 | the events.jsonl cap check removed | `test_events_jsonl_stops_at_its_cap...` | `AssertionError: 1190 not less than or equal to 600` |

Mutation 6 first crashed with a TypeError (a write to the events file
the end had closed). The code had the gap as well as the test: a post
racing the end raised on the endpoint's thread. `3df0513` makes such a
write store nothing; `d81633b` makes the two ended-run tests assert the
status before the words. The table is the run after both.

## The full suites

At the tip, `python3 -m unittest discover -s tests -p 'test_*.py'` and
`node --test tests/*.test.mjs`; the counts are in the lane's report to
the architect, read from that run.

A browser walk outside the repo (headless Chromium through a Playwright
install, against a throwaway TC_ROOT): at 390 px the page's scroll width
equaled its width (390), the smallest button was 44 px, all rows sat in
one column; P, N, F (focus into the note, the words asking for one),
Enter and S worked; Finish asked twice; after the end the state line read
`■ This run has ended; marks are no longer saved` and a P on an unmarked
row showed `Not saved: ...` and left it `Not marked yet`; the only host
asked was the run's own 127.0.0.1 port; no page errors. Screenshots in
light, dark and grayscale went to the architect.

## My calls, said here

- **GET /state.** C8 takes POST on `/event` and `/check` only. The page
  needs to read the run's rows and whether it has ended, so the
  endpoint also answers GET `/state`, behind the token, and GET of the
  page's two files with no token (the token is in the fragment, as C6).
  Nothing else answers GET. tc qa stop and the page's Finish both POST
  `/check` with `{"finish": true}`; stop adds `"by": "stop"` so run.json
  says which.
- **The linger.** After its end a run keeps answering for
  `ENDED_LINGER_SECONDS` (6), so an open page learns it ended instead of
  losing its server mid-mark; a second Ctrl+C cuts it short. Without it
  "a mark after the end is refused" could only ever be a dead connection.
- **A bad --to name exits 6.** C8 lists 0, 1 and 9; C0 gives every
  command that takes a name exit 6, and `tc qa run` calls tc's own
  `require_names`. No new code.
- **The first and last mail are outside the caps.** They frame the run
  and are always sent; the caps count batch mail only.
- **Filters apply to log and post events**, never to notes or marks: a
  person's note and a failed row always reach the session.
- **The base64 rule** redacts a run of 32 or more that mixes cases or
  letters and digits, so a lowercase snake_case name or a plain path
  survives; a CamelCase name of 32 or more, or a path with a digit, is
  redacted. Safety over convenience.
- **The JSON keys** are C8's exactly: `ev`, `tag` and `lvl`. A log that
  writes `level` or `msg` gets them as fields, at info level. Reading
  those too would be a C8 change.
- **Router words on stdout.** Each mail's `sent #N to a: <path>` line
  prints as tc send prints it, after the URL line, which always comes
  first.

## Not verified, or open

- **The full suite counts** are in the report, not here, because this
  file is part of the tip they run on.
- **Nobody has walked `qa/human/qa-streaming.md`.** The browser walk
  above was headless, by the lane agent.
- **Shared mailbox.** `qaruns/` is made 0700 by its first user; a second
  member of a shared mailbox cannot start or note a run there. Not tested
  with a second Linux user, and C8 does not say how QA and C4 meet.
- **Codex and ssh routes for QA mail** go through tc's router unchanged,
  but no test sends QA mail to a codex or ssh card.
- **Files the lane did not touch that now say something incomplete:**
  CLAUDE.md says the board's server is the one server (QA adds a second,
  on 127.0.0.1 behind a token) and its layout lacks `qaruns/` and
  `board/qa.*`; the README's Layout block lacks them too (the brief gave
  the lane only the README's QA section and Commands rows). The
  architect's to change.
- **History holds raw control characters.** Before `ae6c5a8`,
  `board/qa.py` and `tests/test_qa.py` held raw line-separator and bidi
  marks in their patterns; the tip has escapes only. A squash at merge
  would drop them from history too.
- **ResourceWarnings** (unclosed files) print during the full Python
  run. Each module run alone with `-W always::ResourceWarning` shows
  them in `tests/test_health.py` only (6), which this lane did not
  touch; `tests.test_qa` alone shows none. Not chased: outside the lane.

## Fix round 1

From the audit `audits/2026-10-18-1344-standard` (FIX THEN SHIP: H0 M5
L33 D4 R17) and the relay's rulings in D46, taken exactly as the relay
listed them. Where this section and the first round's disagree, this
one holds: the linger is `LINGER_SECONDS`, GET /state is in C8, and
pauses QA-1 and QA-2 are settled.

### Commits

| Part | Commit | Subject |
|---|---|---|
| A, D46 | `24393ea` | QA fix round 1, D46: reserve qa, the linger's name and words, no bidi marks |
| B, MEDIUMs | `87c8f8a` | QA fix round 1, the five MEDIUMs: bounded redaction, mail caps, nested and summary secrets, queued ssh mail |
| C, LOWs and docs | `286fc1b` | QA fix round 1, the LOWs taken, the README and the walk |
| handoff | the commit that adds this section | This section |

### Where each item is (line numbers at `286fc1b`)

**A. The relay's rulings (D46).**
1. `qa` reserved: `refuse_reserved` (`tc:6224`), called after the name
   check in send (`tc:4464`), join (`tc:6675`) and card (`tc:6762`),
   never inside the router, so QA mail itself goes through (DEBT-4's
   warning). Words: `tc: "qa" is reserved: tc qa's runs send their mail
   from it, so no session may take it. Pick another name.`, exit 6.
   Test: `RulingsTest` (`tests/test_qa.py:1640`).
2. GET /state carries rows, marks, notes and the ended flag, never event
   text: `RulingsTest.test_state_carries_rows_marks_and_the_ended_flag_never_event_text`.
3. `LINGER_SECONDS` (`board/qa.py:2698`); a second signal skips it and
   prints `LINGER_CUT_WORDS` (`:2700`), C8's words.
   `RulingsTest.test_a_second_ctrl_c_skips_the_linger_with_c8s_words`.
4. `tests/test_no_bidi.py`: `git ls-files`, binary files (a NUL in the
   first 8000 bytes) skipped, every hit named with its line.

**B. The MEDIUMs.**
5. MEDIUM-1. `REDACT_REPEAT_MAX` (`:198`) bounds every repeat but a
   run's last (`RUN_PATTERNS`); `SECRET_PAIR` (`:207`) starts a key at
   its run's start and `redact_secret_pairs` (`:348`) scans each value
   once (`secret_value_end`, `:311`). The follower cuts a line at
   LINE_MAX_BYTES and drops its rest (`cut_line`, `:626`;
   `split_lines`, `:740`); `feed` (`:1928`), `post` and `mark` make and
   redact events outside the run's lock. Tests: `RedactBoundTest`
   (`tests/test_qa.py:1744`): the parse trees of the patterns checked
   (no clock), a counted bound (the redactor is handed at most
   LINE_MAX_BYTES of a 1 MiB line), and a child ceiling of 30 s
   (`REDACT_CEILING_SECONDS`) for four 64 KiB lines, which only a
   backtracking regression could reach. Measured once, CPU time, one
   run each: before, 1 KiB of `pass` repeated took 0.96 s (0.12 s at
   512, 0.016 s at 256: cubic) and 1 KiB of letters and digits 0.024 s
   (quadratic); after, 64 KiB lines of letters and digits, `pass`,
   `password=`, `a.b` and `pass ` take 1.5 to 8 ms.
6. MEDIUM-2. `MAIL_MAX_BYTES` (`:937`, 64 KiB, checked under tc's
   SEND_BODY_MAX_BYTES in `main`) and `PENDING_MAX_EVENTS` (`:941`).
   `Stream.take` (`:1220`) takes at most BATCH_MAX_EVENTS and
   MAIL_MAX_BYTES; the rest wait, due when the caps allow; `end` mails
   what waits as the caps allow and counts the rest; `summary` (`:2102`)
   stays under MAIL_MAX_BYTES and counts the failed rows it cannot
   quote. Test: `BatchBoundTest` (`:1845`).
7. MEDIUM-3. `Redactor.nested` (`:438`) walks a JSON value, bounded by
   NESTED_MAX_DEPTH and NESTED_MAX_PARTS; in text, a key's object or
   list value is redacted to its closing bracket. Test:
   `LeakFixTest.test_a_secret_nested_inside_a_json_value_is_redacted`.
8. MEDIUM-4. A mark keeps its event's redacted item; `summary` quotes it.
   Test: `LeakFixTest.test_the_summary_quotes_failed_rows_and_notes_redacted`.
9. MEDIUM-5. `EXIT_QUEUED` (`:979`, checked equal to tc's); `open_run`
   starts on 0 or 4; `Stream.settle` (`:1271`) says a queued mail in
   words and counts it queued, never not delivered; the summary counts
   queued mails. Test: `QueuedTest` (`:1975`), the harness's fake ssh
   refusing (exit 255), asserted called.

**C. The LOWs taken.** Tests in `LowFixTest` (`:2014`), one each.
- LOW-1: `STOP_SIGNALS` (`:2733`) adds SIGHUP.
- LOW-4: a JSON line too deep is a plain line; a POST body too deep is 400.
- LOW-6: `ROUTER_REFUSED_WORDS` (`:975`) for any exit but busy.
- LOW-7: `ROTATION_DRAIN_MAX_BYTES` (`:615`); a rotation drains to the end.
- LOW-8: `PORT_MAX` (`:2715`); out of range is exit 9 before the lock.
- LOW-9: a long line is cut and its rest dropped, never split into pieces.
- LOW-10 to LOW-12: the module block rewritten (it also never named the
  endpoint, the commands or the signals); every stale complexity and
  size tag fixed.
- LOW-16: `Redactor.secret` judges the whole key before any cut.
- LOW-17: the README's curl line and the walk hand the token on stdin
  (`-H @-`); `tests/test_readme.py` runs the README's line whole in
  /bin/sh and checks the token is not in it.
- LOW-18: `SRC_WORDS` (`:2311`): /event takes src post only; tc qa note
  posts `{"note": {...}}` to /check; the note's dead filter words are gone.
- LOW-19: GET_METHODS removed.
- LOW-21: `stop_wait_seconds` (`:2819`): two of tc's slowest mails plus a
  margin (118 s at today's constants), in place of 15 s.
- LOW-22: `ENDING_WORDS` (`:1388`) names a run in its linger; the README
  says so.
- LOW-23: `SURROGATE_WORDS` (`:1695`): a post or mark holding a lone
  surrogate is 400, tc qa note with text that is not UTF-8 exits 1.
- LOW-24: tc report's guard also covers `qaruns/` (`tc:5995`).
- LOW-26 to LOW-28: blank lines; LOW-31: `/qaruns/` anchored; LOW-32:
  `types.ModuleType`.

### Red, then green

| Item | Red | Then |
|---|---|---|
| A1 reserved name | `AssertionError: 0 != 6` for join, card and send | green |
| A3 linger | `AssertionError: None != 6`, then, with the name, `'ended without the 6 s linger; ...' not found` | green |
| A4 bidi | on a planted file in a scratch clone: `Lists differ: ['docs/planted.md:1: U+202E'] != []` | green on the tree |
| A2 /state | a guard: the code already carried no event text | green |
| B, MEDIUMs | `Ran 8 tests`, `FAILED (failures=11, errors=2)`; the two errors (missing constants) rerun red on assertions (`7` failures) once the names existed | `Ran 57 tests`, `OK` |
| C, LOWs on the tree | `FAILED (failures=12, errors=1)` (LOW-1, 7, 8, 18, 22, 24; LOW-21's missing function, then `15 not greater than or equal to 118`) | green |
| C, LOWs fixed in part B | on a scratch copy with board/qa.py and tc from `24393ea`: LOW-6, LOW-9, LOW-16 and LOW-23's note half failed on assertions; LOW-4 and LOW-23's endpoint half errored with the defect itself (a RecursionError, a request thread that died) | green |

Five LOW fixes (4, 6, 9, 16, 23) landed in part B's commit, in code part
B was rewriting, before their tests existed; their red runs are the
scratch run above, against the code before part B.

### Mutations (at `286fc1b`, scratch copies, PYTHONDONTWRITEBYTECODE=1)

| Item | Mutation | Red line |
|---|---|---|
| 1 | the reserved name not checked | `AssertionError: 0 != 6` |
| 4 | a bidi mark planted in a tracked file of a clone | `Lists differ: ['docs/planted.md:1: U+2066'] != []` |
| 5 | the key rule's repeats unbounded and unanchored | `AssertionError: redacting 65536 bytes of alnum ran past 30 s` (and `pass`, `a.b`; the parse-tree check too) |
| 5 | the follower's line cut removed | `AssertionError: 1048576 not less than or equal to 65536` |
| 6 | a mail takes everything waiting | `AssertionError: 160 not less than or equal to 40` and `1 not greater than 1` |
| 7 | nested values not walked, brackets not scanned | `AssertionError: 's-41f' unexpectedly found in ...` |
| 8 | the summary quotes the checklist's own item | `'| fail row 1: Sign in as [redacted] with password=[redacted]' not found in ...` |

### Not done, and why

The relay's list was exact; these were left out of it.
- LOW-2 (a password in a URL with no dotted host; `pwd`, `auth` keys):
  widening the built-in kinds is a C8 change, the relay's to rule.
- LOW-3 (the state line scrolls out of view): a page change the list did
  not take.
- LOW-5 (a reused pid makes a dead run look live to note and stop): not
  on the list; the lock probe both reviewers propose is a small follow-up.
- LOW-13, LOW-14, LOW-15 (cost past the caps, a match text redacted with
  no /re/, the lock held across a read's adds): perf only; part B moved
  all redaction out of the lock, so LOW-15 is narrower now.
- LOW-20 (`QaRun` fields set by `__dict__.update`): not on the list.
- LOW-25 and LOW-33 (README Layout, CLAUDE.md): the Layout block is
  outside the lane's README work set, and CLAUDE.md is the architect's.
- LOW-29, LOW-30 (qa.js naming, the node suite's file name): the
  synthesis recommends a CLAUDE.md deviation, the architect's file; the
  brief named `tests/qa.test.mjs`.
- DEBT-1 to DEBT-4 and REC-1 to REC-17: not fix items. DEBT-4's warning
  shaped item A1.

### Not verified

- Nobody has walked `qa/human/qa-streaming.md`, now with steps 1a, 16
  (token on stdin), 22a and 22b.
- No real ssh: QueuedTest uses the harness's fake. No codex card was
  sent QA mail.
- A shared mailbox with a second Linux user is untested, as before.
- The full suite counts are in the lane's report, read from the run at
  the tip.

## Fix round 2

From the security re-review (`audits/2026-10-18-1445-custom`,
security-reviewer), plus two adds from that review's synthesis. Where
this section and fix round 1's disagree, this one holds: the key rule no
longer caps a key, a gap or an email's local part.

### Commits

| Part | Commit | Subject |
|---|---|---|
| code, tests, README | `54e3791` | QA fix round 2: redaction without capped keys or gaps, the reserved name's edges |
| tests | `f68ab50` | Give each round 2 redaction shape its own secret |
| handoff | the commit that adds this section | This section |

### Where each item is (line numbers at `f68ab50`)

1. **MEDIUM-1, round 1's regression.** Round 1 capped the key rule at 8
   spaces either side of the colon and 64 key characters either side of
   the secret word, so `DB_PASSWORD:` with 18 spaces, a key padded
   before its colon, a long flattened key such as
   `...connection.password=`, and an email local part over 64 all
   reached mail. Now, as the reviewer proposed: `SECRET_KEY_RUN`
   (`board/qa.py:213`) finds each run of key characters whole, once;
   `redact_secret_pairs` (`:369`) keeps a run when `SECRET_KEY` finds a
   secret word anywhere in it, matches `SECRET_GAP` (`:214`, any width)
   at the run's end, and scans the value (`secret_value_end`, `:325`).
   `BEARER` had the same regression (`\s{1,8}`), so it takes the same
   shape: the word searched (`:229`), its spaces and token matched at
   its end (`BEARER_VALUE`, `:230`; `redact_bearer`, `:403`). `EMAIL`
   (`:240`) caps only its domain labels (63 each, DNS's limit, at most 8
   dots); its local part starts once per run, after its lookbehind.
   `ANCHORED_PATTERNS` (`:247`) names the two patterns only ever matched
   at one position; the parse-tree test
   (`tests/test_qa.py:1757`) checks the source matches them and never
   searches them. Every pass stays linear. Measured once, CPU time: the
   worst 64 KiB lines (a key then 64 KiB of spaces, `password `
   repeated, a 64 KiB key run before `password=`, Bearer then 64 KiB of
   spaces, a 64 KiB local part, `pass: ` repeated) take 1.5 to 9 ms.
   The ceiling test gains those five lines.
2. **LOW-1.** `cmd_send` skips the reservation when `--origin` is given
   (`tc:4464`): only a far tc's ssh route sends it, and on a far key with
   no forced command that route runs `tc send --from qa --origin <id>`,
   which must land. `refuse_reserved`'s doc block says so (`tc:6225`).
3. **LOW-2.** `name.casefold() == QA_SENDER_NAME` (`tc:6240`).
4. **LOW-3.** README (`README.md:881`): one token serves every caller,
   so anything holding it can post a note, and notes skip the filters.
5. **LOW-4.** `secret_value_end`'s quoted branch steps over `\` and the
   character after it, as its bracket branch does.
6. **LOW-5.** `SECRET_HEADER` (`:224`): the spaces sit inside the
   lookahead, so a quoted or bracketed Cookie value goes to the key rule
   and no longer wipes the rest of the line.
7. **LOW-6.** `body_problem` (`:1770`), a stack walk with no recursion:
   `DEPTH_WORDS` (`:1753`) for fields nested past NESTED_MAX_DEPTH, the
   surrogate words only for a lone surrogate.
- **The synthesis's adds.** Nine top-level gaps in `board/qa.py` made two
  blank lines; `tests/test_readme.py` names `LINGER_SECONDS`; the
  README's gate paragraph (`README.md:496`) says a run's mail to a far
  name arrives through the gate from the key's `--as` name, its first
  line still `QA: run ...`.

### Red, then green

`Round2Test` (`tests/test_qa.py:2292`), with `ANCHORED_PATTERNS` added
alone first so the parse-tree test could load: `Ran 9 tests`,
`FAILED (failures=19)`, every failure on an assertion. Six shapes
leaked into the mail; QA, Qa and qA passed join, card and send;
`--origin` still got 6; `cd-tail` stayed after an escaped quote; the
cookie line read `{"cookie":[redacted]`; the depth post got the
surrogate words. Then green.

### Mutations (at `f68ab50`, scratch copies, PYTHONDONTWRITEBYTECODE=1)

| Item | Mutation | Fails | Red line |
|---|---|---|---|
| 1a | the gap after the : or = capped at 8 | only `padding after the colon` | `'after-pad-sunrise' unexpectedly found in ...` |
| 1b | the gap before the : capped at 8 | only `padding before the colon` | `'before-pad-sunrise' unexpectedly found in ...` |
| 1c | a key run capped at 64 | the two long-key shapes | `'long-prefix-sunrise' unexpectedly found in ...` |
| 1c | an email local part capped at 64 | only `a long email local part` | `'ortiz@example.test' unexpectedly found in ...` |
| 2 | the reservation also on a send with --origin | the --origin test | `AssertionError: 6 != 0` |
| 3 | the reservation compared with case | QA, Qa, qA (9 subtests) | `AssertionError: 0 != 6` |

The first mutation run failed all four key shapes for each of 1a, 1b
and 1c: the four plants shared one secret in one mail. `f68ab50` gives
each shape its own secret; the table is the run after it.

### Not done, and why

- REC-1 (a write to a hung-up terminal failing inside `end`) and REC-2
  (a truncation while skipping a long line drops the next line) are real
  and small, and were not on the list.
- REC-4 (`tc wait qa` and `tc send --to qa` still work): the relay's to
  rule.
- `api key` with a space inside the key is no longer one key run, so
  `api key: x` in plain text is not redacted by the key rule;
  `api_key`, `api-key` and `apikey` are. A JSON field named `api key`
  is still redacted (fields judge the whole key).
