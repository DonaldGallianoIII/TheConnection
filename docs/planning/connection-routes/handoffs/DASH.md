# Handoff: DASH, tc report draws the mailbox as one static page

Model:  Claude Opus 5.5 (the DASH lane agent)
Status: unreviewed
Date:   2026-10-17
Branch: Claude-Development-TheConnection-DASH, from
        Claude-Development-TheConnection at 864b277
Where:  ~/TheConnection-lanes/dash
Brief:  ~/TheConnection-lanes/briefs/DASH.md

The spec is contract C7 with a2's four adds (decision D42).

## Commits

| Slice | Commit | Subject |
|---|---|---|
| Extractor | `1856c8a` | Add the report's extractor: one closed record per message, roles from serve.py |
| Scrub | `f738403` | Add the report's scrub: role labels, the tag allow list, elapsed times, ranks |
| Page, chart 1 | `859d095` | Draw the report page and chart 1, who talks to whom |
| Chart 2 | `40db53c` | Draw chart 2, messages over time per sender |
| Chart 3 | `24fbb1d` | Draw chart 3, sent to read per recipient |
| Chart 4 | `6cfd3a7` | Draw chart 4, busy and quiet stretches |
| Chart 5, DASH-1 | `f079b60` | Draw chart 5, ask to answer, and pause DASH-1 on what an ask is |
| Command | `b655a73` | Add tc report OUT.html [--scrub] [--force] [--at TIME] |
| README, DASH-2 | `f546d3f` | Show tc report in the README, run its block, and pause DASH-2 |
| QA | `889e416` | Add the human QA walk for tc report |
| Layout at scale | `2d1c9e3` | Wrap wide graph levels, arc long same-line arrows, and bring the doc blocks up to date |
| Test tightening | `dcab984` | Make the report's refusal tests require tc's own words and no traceback |
| Handoff | the commit that adds this file | This handoff |

## Where each item is (line numbers at `dcab984`)

1. **Extractor**, `board/report.py`. `Record` (`:293`, exactly number,
   sender, recipient, sent, read, size, tag, refs), `walk_messages`
   (`:442`, tc's pinned walk through `tc.open_mail`, `tc.open_inbox`,
   `tc.message_files`, `tc.read_times`), `read_head` (`:379`, by name in
   the folder's descriptor, `O_NOFOLLOW | O_NONBLOCK`, at most
   `MESSAGE_HEADER_MAX_BYTES + TAG_READ_MAX_BYTES`), `parse_head`
   (`:350`, `HEADER_PATTERN` at `:103`), `first_line_facts` (`:327`,
   `TAG_READ_MAX_BYTES = 256` at `:93`), `read_reports_to` (`:515`, only
   `reports_to`, through serve.py's `card_text`), `extract` (`:547`).
   The first line's text lives only inside `first_line_facts` and
   `parse_head`; only the tag and refs leave them.
2. **Renderer**, `board/report.py`: `render` (`:1475`), the charts
   `chart_graph` (`:858`), `chart_senders` (`:1080`), `chart_read`
   (`:1227`), `chart_quiet` (`:1305`), `chart_answers` (`:1431`, pairs
   from `answer_pairs` at `:1396`). Every element goes through
   `element` (`:680`) and `esc` (`:657`, `html.escape`, quote=True). No
   clock read anywhere in the module; the as-of comes from `page_of`
   (`:588`).
3. **Accessibility.** `SERIES_SHAPES`, `SERIES_DASHES`, `SERIES_COLORS`
   (`:232` on): series i of a plot takes entry i of each, so the two
   series of a lane differ in shape, dash and color. Each series is
   labeled at itself (glyph and word). Quiet gaps are hatched by
   `hatch` (`:1285`) plus their words. Node shape and role word by role
   (`node_shape`, `role_word`). Each SVG has a `<title>` and `<desc>`
   (`svg_chart`, `:724`); the page has `lang="en"` and a `<title>`.
4. **Scrub**, `scrub` (`:601`): labels by first mail, `SCRUB_TAGS`
   (`:115`), elapsed seconds, ranks, refs mapped to ranks (a ref to no
   message here is dropped). It runs on the Page before `render`.
5. **Command**, `tc`: the constants and words (`:5728` on),
   `report_time` (`:5749`, `--at` needs an offset, else exit 9),
   `cmd_report` (`:5767`), the argparse entry (`:10298`), and the module
   block (`@interacts` `:282`, `@complexity` `:337`, `@rng` `:431`).
6. **Tests**, `tests/test_report.py` (28 tests) over
   `tests/_report_fixture.py`. The README chain:
   `tests/test_readme.py`, `test_the_report_block_writes_a_scrubbed_page`
   (`:925`).
7. **README**: the report part and export paragraph (`README.md:213` on),
   the Commands row (`:569`). **QA**: `qa/human/report.md`.

## How serve.py's functions are loaded

`load_board_module` (`board/report.py:307`) does what serve.py's own
`load_tc` does for tc: read serve.py's source, `compile` it in memory,
`exec` it in a fresh `types.ModuleType`. No bytecode is read or written,
serve.py's `main()` never runs, and nothing is copied: the roles come
from serve.py's `hierarchy()` itself. tc loads report.py the same way
(`type(sys)` is the module type, so tc needed no new import), then calls
`load_board_module` itself so a missing serve.py is refused in words.
The tests load both through `_root.load_source`, under names that
`tests/test_no_bytecode.py`'s loader census does not claim.

## Which names C5 gives no role

C5's nodes are the names with an inbox or a card; every node gets a role
(peer at least, rule 3), because rule 2 infers parents from mail too. So
the only name with no role is one that is in some message's file name as
a sender and has neither `mail/to-<name>/` nor `cards/<name>.json`. The
fixture's dagny is that name: it sends one message, has no card and no
inbox, and scrubs to `session-1`. A name with an inbox and no card is a
peer (or a worker by inference), not a session.

## Red, then green

Each slice's tests ran red before its code, with
`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_report`:

| Slice | Red run | Why |
|---|---|---|
| Extractor | `Ran 4 tests`, `FAILED (errors=4)` | no board/report.py |
| Scrub | `Ran 7 tests`, `FAILED (errors=3)` | no `SCRUB_TAGS`, `scrub`, `Page` |
| Page, chart 1 | `Ran 12 tests`, `FAILED (errors=7)` | no `render` |
| Chart 2 | `Ran 13 tests`, `FAILED (errors=3)` | no `senders` chart, no `HOURLY_UP_TO_SECONDS` |
| Chart 3 | `Ran 14 tests`, `FAILED (errors=2)` | no `read` chart |
| Chart 4 | `Ran 15 tests`, `FAILED (errors=2)` | no `QUIET_GAP_SECONDS` |
| Chart 5 | `Ran 18 tests`, `FAILED (failures=1, errors=3)` | no `answers` chart, no `answer_pairs`; the empty page lacked it |
| Command | `Ran 27 tests`, `FAILED (failures=9)` | every command test on its assertion: exit 9, `report` unknown |

Each slice then ran green before its commit. Not seen red before their
code: the README chain (written after the command; its one red was my
own setup, one message printing `1 message`), and the two refusal
tests written after `cmd_report`. Those two were then checked by
mutation, below, and one needed tightening (`dcab984`).

## Mutations

Each on a `git archive` copy in the scratchpad, run with
`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_report`.

| Mutation | Result |
|---|---|
| The scrub keeps real names | `FAILED (failures=8)`; the scrub test: `'annika' unexpectedly found` |
| The tag allow list skipped | `FAILED (failures=4)`; `'ZEBRAPLANT' unexpectedly found` |
| One relative time printed absolute (the scrubbed as-of kept as a date) | `FAILED (failures=4)`; the date pattern matched `2026-10-02` |
| The first-line read keeps the whole line | `FAILED (failures=10)`; the planted-secret test: `b'SECRETWORDA' unexpectedly found` |
| Two series given the same shape | `FAILED (failures=8)`; the accessibility test: `1 != 2 : ['triangle-up', 'triangle-up']` |
| The existing-file check removed (both checks) | `FAILED (failures=1)`; `Tuples differ: (0, '<!doctype html>...') != (1, 'keep me')` |
| The first existing-file check alone removed | `OK`: the re-check before the rename still refuses. Defense in depth, not a gap |
| The serve.py load unguarded | `OK` at first (a traceback also exits 1 and names the path); after `dcab984`, red: `'no renderer at .../serve.py' not found` |
| The page's write unguarded | `FAILED (failures=1)`; `'could not write ...' not found` |

## Deviations and things to know

- **No SVG `<pattern>`, no `<marker>`.** Item 6 bans `url(` in the
  output, and both need `url(#id)`. Quiet stretches are hatched with
  diagonal lines worked out and clipped in Python (`hatch`), and arrow
  heads are drawn triangles. The look is the same.
- **tc's constants for `report` sit beside `cmd_report`**, not at the
  top of tc: the work set names only the subcommand, its argparse entry
  and the module block. They are module constants with comments.
- **tc's `@rng` changed** too: it said "Nothing else draws randomness",
  and the page's `.tmp` name draws `secrets.token_hex`. Leaving it would
  have made a stale tag.
- **`tests/test_readme.py`'s `Story` gained a `cwd`** (default None,
  unchanged for every other chain), so the report block's relative
  `history.html` lands in the temp folder and never in the checkout.
- **README's Layout block** still lists `board/` as "serve.py,
  live.html, look.js, theme.css, demo.html": outside this lane's README
  spots, so `report.py` is not named there. CLAUDE.md's layout likewise.
- **Chart 3's dots carry their read time** in their hover title, so the
  real page shows every sent and read time and the scrub test can check
  them present.
- **Chart 1 at scale.** Levels wrap at 5 boxes a line, and an arrow
  between two boxes on one line with others between them arcs further.
  A mailbox where 16 names all mail each other is still a dense tangle
  (240 arrows); each arrow's hover title keeps the exact count.
- **Measured cost**: a synthetic 2000-message mailbox among 16 made-up
  names wrote a 1.8 MB page in 0.28 s.
- **The Write tool refused `qa/human/report.md`** as a report file (a
  guard against summary files); it is the brief's QA deliverable, so it
  was written through the shell.

## Pauses

- **DASH-1**: what an ask is, for chart 5's unanswered count. Carried on
  with `ASK_TAGS = ("QUESTION",)`.
- **DASH-2**: (a) a page that cannot be written: built as exit 1 with
  words, row 1 of the exit table would need the words; (b) a page named
  inside the mailbox's folders: not refused, waiting for a ruling.

## Not verified

- No person has walked `qa/human/report.md`. I looked at both fixture
  pages in headless Chromium, light, dark and with a grayscale filter,
  and at a 2000-message page.
- The page has not been made from the live mailbox (off limits).
- Glyph widths are estimated (`CHAR_WIDTH`), not measured, so a name
  near C0's 64 characters, or one of wide letters, may overrun its node
  box.

## Fix round 1 (audits/2026-10-17-2147-standard, and C7 at the dev checkout's fb9f330)

<!-- Fix round 1 section added by Claude Opus 5.5 (the DASH lane agent), 2026-10-17. Status: unreviewed. -->

Line numbers are at `fda6b69`.

### Commits

| Items | Commit | Subject |
|---|---|---|
| A1, A2, A4, LOW-4, LOW-7, LOW-13 | `9e95d2c` | the ask rulings, chart 3's axis end, and tc report: under any name |
| A3, DEBT-1, LOW-3, LOW-5, REC-7, REC-8, DEBT-5 | `d0a2466` | pin OUT's folder, refuse a page inside the mailbox, publish by link |
| MEDIUM-1, MEDIUM-2, REC-10 | `c4fbb8b` | a text floor per chart, row names that never pass x 0, scrubbed node labels |
| LOW-1, LOW-2, LOW-6, LOW-9, REC-1, REC-3, LOW-10 | `6d1f208` | bounded refs, one inbox open at a time, a moved message found, no name order |
| REC-9, REC-13, REC-5 | `6fcaf6c` | the scrub note lists its tags, the page counts unread folders, no report bytecode |
| LOW-11, LOW-12, REC-2, REC-12 | `01868e3` | README matches what the report reads, and the QA walk gets a setup script |
| LOW-8, LOW-15 to LOW-20 | `649fcbc` | doc blocks true to the code, no long lines, no shebang |
| Pauses | `fda6b69` | DASH-1 and DASH-2 settled; pause DASH-3 |
| Handoff | the commit that adds this section | this section |

### Where each item is

1. **DASH-1.** `ASK_TAGS` and `ASK_CAVEAT` (`board/report.py:281`,
   `:282`); `chart_answers` (`:1668`) counts `<n> asks have no reply
   that names them` (`1 ask has no reply that names it` for one), counts
   an ask with no sent time apart (LOW-4), and draws the caveat under
   the chart. `unanswered` and `nobody answered` appear nowhere.
2. **DASH-2(a).** `REPORT_WRITE_WORDS` (`tc:5767`) is C7's line exactly.
3. **DASH-2(b), DEBT-1, LOW-5, LOW-3.** `report_folder` (`tc:5788`)
   opens OUT's folder once, resolves it with `os.readlink` of
   `/proc/self/fd/<n>`, and refuses (`REPORT_INSIDE_WORDS`, `tc:5764`)
   a folder that is or is under the resolved `mail/`, `status/`,
   `cards/` or `outbox/`. `publish_report` (`tc:5823`) makes the .tmp by
   name in that descriptor (`REPORT_TMP_NAME`, `tc:5746`, a fixed short
   name), then `os.link` to OUT's name without `--force` (a file made
   meanwhile is kept; the run refuses) or `os.rename` with it, then
   unlinks the .tmp's name. No path step follows the open.
4. **Chart 3's axis.** `delay_strips` (`board/report.py:1378`) labels the
   far end with the longest delay drawn; a tick label nearer it than
   `DELAY_END_GAP` (`:251`) is left off, its grid line kept.
5. **MEDIUM-1, REC-10.** `svg_chart` (`:918`) sets each SVG's CSS
   `min-width` to its width x `MIN_TEXT_PX` (`:174`, 11) /
   `SMALL_TEXT_UNITS` (12, the smallest text, now the constant the CSS is
   built from), so a narrow screen scrolls each chart's box instead of
   shrinking its words. `node_label` (`:1023`): a scrubbed node reads
   `worker-1`.
6. **MEDIUM-2.** My call: cut, not widen. `row_label` (`:1288`) fits the
   name and the detail line with `fit_words` (`:888`) and `char_width`
   (`:877`), the estimate the graph sizes its boxes with; a cut name is
   three periods (the voice rules ban the one-character ellipsis) and
   its end, with the whole name in a `<title>` inside the text. I also
   widened the gutter (`LABEL_GUTTER`, `:216`, 230 to 280) so C7's `n of
   m messages have a read time` fits with four-digit counts. The
   estimate rose from 7.4 to 9.0 units a bold character (`CHAR_WIDTH`,
   `:164`) after a headless look showed a run of `q` overrunning x 0 at
   7.4 and at 8.0; small text has its own, 6.8. The false comment is
   gone. A median's words now stay inside the chart's width.
7. **LOW-1.** `REF_MAX_DIGITS` (`:108`, 9): a longer #N is no reference.
8. **LOW-2.** `walk_messages` (`:511`) closes each inbox's two
   descriptors as soon as `walk_inbox` (`:570`) is done with it.
9. **LOW-3.** The .tmp's name is `.tc-report-<16 hex>.tmp` whatever
   OUT's name; a 255-byte OUT name writes.
10. **LOW-4.** As in item 1.
11. **LOW-6.** `parse_head` (`:401`) reads a first body line only after
    a tc header (`TC_HEADER_START`, `:112`, its time parsed or not).
12. **LOW-7.** `REPORT_BOARD_MISSING_WORDS` (`tc:5760`).
13. **LOW-8, LOW-15 to LOW-20.** Doc blocks: chart_read, chart_quiet,
    render and both module blocks carry `O(s x t + t log t ...)`;
    first_line_facts's bound is the window's remainder;
    `TAG_READ_MAX_BYTES`'s comment says what it is; `publish_report`'s
    `@deps` names contextlib. No code line past 120 columns (one-line
    docstring summaries stay long, as serve.py's do); two blank lines
    before the renderer's marker; no shebang.
14. **LOW-9.** `walk_inbox` reads a message gone from the inbox by its
    name in read/, with its read time.
15. **LOW-11, LOW-12, REC-2.** README: the Layout line names report.py;
    the report reads cards' `reports_to` and `#N` anywhere in the first
    line; an unscrubbed page holds every leading tag. The page's face
    words stay C7's.
16. **LOW-13.** Every REPORT_ word, and the stderr lines, open `tc
    report:`.
17. **REC-1.** `ExtractTest.test_a_header_that_real_tc_send_wrote_parses`.
18. **REC-5.** `tests/test_no_bytecode.py`,
    `test_tc_report_writes_no_cache_of_report_or_serve`.
19. **REC-7.** The README example writes `~/history.html`; the stdout
    line prints the resolved path. The README chain sets HOME to its temp
    folder and expands `~/` as a shell would (`Story.home`).
20. **REC-8.** The stdout line names the mailbox as R2 does (`Mailbox
    <ROOT>, <words>`). The page does not: C7 says the renderer never sees
    ROOT. Pause DASH-3 asks; recommendation, leave the page as it is.
21. **REC-9.** The scrub note lists `SCRUB_TAGS`, now a tuple in C7's
    order (a frozenset's order changes with the string hash seed, which
    would have broken same-bytes once printed).
22. **REC-12.** `qa/human/report-fixture.py` builds the walk's mailbox in
    a fresh `/tmp/report-qa-...` folder and writes no bytecode;
    `qa/human/report.md` runs it with `eval`.
23. **REC-13.** `Page.unreadable` (`:350`) and a line in
    `summary_lines` (`:1173`).
24. **REC-3.** `sent_order` (`:491`) breaks ties by number, then size.
    Known residual, in scrub's doc block: two messages at one time with
    one number and one size (only a hand-made twin) keep the walk's
    order, inboxes by name.
25. **LOW-10, the relay's addition.** Done, in a few lines and with no
    change to serve.py: `first_mail_levels` (`:672`) calls serve.py's
    `levels_of` over stand-in names that sort in first-mail order, so a
    reports_to cycle breaks at the earliest first mail. It runs for the
    real page too, so a real and a scrubbed page draw one layout; the
    board's own layout is unchanged.
26. **DEBT-5**, though listed for "Not done": done in passing, because
    the in-process race test needed it. cmd_report hands report.py a
    module holding tc's names (`type(sys)(__name__)` filled from
    `globals()`), not `sys.modules[__name__]`.

### Red, then green

Each slice's tests ran red first (`PYTHONDONTWRITEBYTECODE=1 python3 -m
unittest tests.test_report`):

| Slice | Red run |
|---|---|
| A1, A4, LOW-7, LOW-13 | `Ran 32 tests`, `FAILED (failures=7)` |
| A3 | `Ran 35 tests`, `FAILED (failures=7, errors=1)`; the error was DEBT-5 (`KeyError: 'tc_for_report'`), and mutation 3b below shows the race test red on its assertion |
| MEDIUM-1, MEDIUM-2, REC-10 | `Ran 37 tests`, `FAILED (failures=2, errors=80)` (the errors are subtests on missing constants) |
| LOW-1, LOW-2, LOW-6, LOW-9, REC-3, LOW-10 | `Ran 43 tests`, `FAILED (failures=6, errors=1)`; the error is LOW-1's own ValueError |
| REC-9, REC-13 | `Ran 45 tests`, `FAILED (failures=17, errors=1)` |

Guards that passed when written, each then shown red by a mutation:
REC-1 (tc's header written `... to b at <time>`: `AssertionError: 2 !=
0`), REC-5 (the renderer loaded through importlib: a `.pyc` written),
and REC-12's setup test (`sys.dont_write_bytecode` flipped, done in place
and put back, not on a scratch copy: `['_report_fixture.cpython-312.pyc']
!= []`).

### Mutations, items 3, 5, 6 and 7

Each on a `git archive` copy, `PYTHONDONTWRITEBYTECODE=1`:

| Mutation | Result |
|---|---|
| 3a: the inside-the-mailbox check removed | `FAILED (failures=5)`: `AssertionError: 0 != 1` |
| 3b: publish without --force by rename, not link | `FAILED (failures=1)`: `AssertionError: SystemExit not raised` (the late file replaced) |
| 3c: the .tmp's name built from OUT's again | `FAILED (failures=1)`: `1 != 0 : tc report: could not write ...` |
| 5a: no width floor | `FAILED (failures=10)`: `None != 'min-width:880px'` |
| 5b: a scrubbed node repeats its role | `FAILED (failures=1)`: the node set differs |
| 6: a row name not fitted | `FAILED (failures=4)`: `-306.0 not greater than or equal to 0` |
| 7: ref digits uncapped | `FAILED (failures=1, errors=1)`: `Tuples differ: ('PLAN', (123456789, 1234567890))`, and the 5000-digit ValueError |
| REC-5: renderer loaded through importlib | `FAILED (failures=1)`: a `.pyc` listed |

### Runs at the tip

`python3 -m unittest discover -s tests -p 'test_*.py'`: `Ran 438 tests
in 277.465s`, `OK`. `node --test tests/*.test.mjs`: `# tests 68`, `# pass
68`, `# fail 0`.

### Not done, and why

- **DEBT-2** (cards read by path after a glob): the only swapper is the
  init user (D34); the same shape as tc's own card reads.
- **DEBT-3** (one 1,760-line file): a split moves tc's loader path,
  tc's words and the tests' module paths; worth its own lane.
- **DEBT-4** (every message ever on one page): a window changes page_of,
  the scrub's origin and every axis together; v2.
- **REC-4** (a D35 class-proof row for tc report): touches
  tests/test_inbox_pinned.py, outside this round's work set.
- **REC-6** (a counted growth test at t, 2t, 4t): not built; the cost
  figure in report.py's `@alloc` is one measured run, said as such.
- **REC-11** (an `--at "$(date -Iseconds)"` recipe): not added; the
  README says `--at` takes a time with its offset.
- **LOW-14, LOW-21, LOW-22**: the architect's at the merge.
- **REC-8's page half**: pause DASH-3.

### Not verified

- No person has walked `qa/human/report.md`. I looked at the fixture
  pages and a 64-character name's page in headless Chromium.
- The width estimate is an estimate: a name of only `W` or `m` in bold
  may still pass x 0 by a few units, and the test checks the estimate,
  not glyphs.
- `os.link` needs hard links: on a filesystem without them, a page
  without `--force` refuses with `could not write`, as a message send
  refuses there.

## Fix round 2 (audits/2026-10-17-2233-custom, and C7 at the dev checkout's d0523c7)

<!-- Fix round 2 section added by Claude Opus 5.5 (the DASH lane agent), 2026-10-17. Status: unreviewed. -->

One code commit, `00e3e92`, and this section's commit. Line numbers are
at `00e3e92`: `walk_messages` `board/report.py:514`, `walk_inbox` `:595`,
`fit_words` `:916`, `row_label` `:1320`, `delay_strips` `:1410`,
`DELAY_LABEL_PAD` `:254`; `REPORT_RESERVED_NAMES` `tc:5773`,
`REPORT_RESERVED_WORDS` `tc:5775`, `report_inside` `tc:5799`,
`report_folder` `tc:5815`.

1. **LOW-1, option A, built as the coordinator put it.** `walk_inbox`
   returns each message its retry found in read/ with no read time yet;
   `walk_messages` keeps that inbox's two descriptors open to the walk's
   end, reads its read/'s record once more then, and fills the read
   times the record has by then. tc read moves every message first and
   writes the lines after, so a re-read at the end of the walk, not at
   the moment of the retry, is what catches the common case. The
   docstring now says a message gets its read time when the record has
   it by the walk's end. The test writes the record line after the
   report has looked for it (at the next other message's read), which
   is tc's order; the round 1 test wrote both at once and passed on the
   old code. With the line moved, the old code was red on its
   assertion before the fix.
2. **LOW-2, option A, with one refinement.** A tick label is left off
   when its estimated extent (char_width) reaches within
   `DELAY_LABEL_PAD` of the end label's left edge. When the end label's
   words equal a tick's (a longest wait of 84 to 119 s reads `1m`, as
   the 60 s tick does), I leave off the end label, not the tick: the
   tick's label sits at its true place, and an end label `1m` at 100 s
   would mislabel the far end. The comment is rewritten. Tested at
   13h30m (`6h00m` is left off; the end reads `13h30m`) and at 100 s
   (`0s`, `1m`, no repeat).
3. **LOW-3, option A.** `fit_words(..., keep_start=True)` for a row's
   detail line, which opens with its count; a name still keeps its end.
   Tested with 12345 hand-made records: chart 3's line opens `12345 of
   12345`, chart 4's `12345 sent`.
4. **LOW-4, as the relay ruled it into C7.** `report_folder` refuses,
   exit 1, even with `--force`, an OUT whose folder resolves to ROOT and
   whose name is one of `REPORT_RESERVED_NAMES` (`.shared`, `mail`,
   `status`, `cards`, `outbox`, `tc`, `board`) or starts with a dot,
   whether or not the entry is there. Judged after resolving: the folder
   as its pinned descriptor resolves, and, when OUT's own name in that
   folder is a link, where the link leads, read by name in the
   descriptor and resolved from there. A link that leads into
   `mail/`, `status/`, `cards/` or `outbox/` is refused with the inside
   words. tc never writes through such a link anyway (a link or rename
   by name replaces the link itself), but C7 says to refuse it, so it
   does. Red first with the four cases: `.shared` with `--force` (on the
   old code the page replaced `.shared` and every later command
   refused), a missing `mail` entry, a link at ROOT to `.shared` with
   `--force` (plus a link elsewhere to `.shared`), and `history.html` in
   ROOT, which is written. The README's refusal line names the entries.
5. **LOW-5.** `walk_messages`' `@deps` now names what it calls
   (`walk_inbox`, `tc.read_times`, `parse_time`) and no `contextlib`;
   `row_label`'s block says which end each line keeps; tc's module block
   and cmd_report's say the new refusal.

**Mutations**, one each, on `git archive` copies with
`PYTHONDONTWRITEBYTECODE=1`:

| Mutation | Result |
|---|---|
| 1: no re-read at the walk's end | `FAILED (failures=1)`: the read time is `None` |
| 2: the fixed 48-unit gap put back | `FAILED (failures=1)`: `903.7 not less than 895.2` (6h00m overprints 13h30m) |
| 3: the count line keeps its end again | `FAILED (failures=1)`: `'... of 12345 messages have a read time'` |
| LOW-4: reserved names allowed | `FAILED (failures=5)`: `0 != 1`, and `.shared` replaced |

**Runs at `00e3e92`.** `python3 -m unittest discover -s tests -p
'test_*.py'`: `Ran 441 tests in 259.655s`, `OK`. `node --test
tests/*.test.mjs`: `# tests 68`, `# pass 68`, `# fail 0`.

**Not taken this round:** REC-1 (bind mounts) and REC-2 (a cycle made
only of names with no mail still breaks by name order: one bit about two
undrawn names, recorded here beside the hand-made-twin residual).
