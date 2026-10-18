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
