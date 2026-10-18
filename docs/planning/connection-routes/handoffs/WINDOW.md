# Handoff: WINDOW, a time window on tc report

Model:  Claude Opus 5.5 (the WINDOW lane agent)
Status: unreviewed
Date:   2026-10-17
Branch: Claude-Development-TheConnection-WINDOW, from
        Claude-Development-TheConnection at 004b568
Where:  ~/TheConnection-lanes/window
Brief:  ~/TheConnection-lanes/briefs/WINDOW.md

The spec is contract C7's paragraph "A time window" (decision D44), with
the rest of C7 still holding.

## Commits

| Slice | Commit | Subject |
|---|---|---|
| Code and tests | `45b6605` | Add a time window to tc report: --from and --to (C7, D44) |
| README and QA | `275ddc9` | Show tc report's time window in the README and the QA walk (D44) |
| Handoff | the commit that adds this file | This handoff |

## Where each item is (line numbers at `45b6605`)

1. **Parse: in report.py, one place.** `window_of` (`board/report.py:802`)
   turns the two texts into a `Window` (`:384`) or None; `window_time`
   (`:783`) parses one bound with `datetime.fromisoformat`, and a naive
   result (a date alone is midnight, a time with no offset) takes the
   local zone's offset for that date through `astimezone()`. The words
   are `WINDOW_TIME_WORDS` and `WINDOW_ORDER_WORDS` (`:159` on). tc's
   argparse entry (`tc:10480`, `tc:10483`) passes the text through as
   `window_from` and `window_to`; `cmd_report` (`tc:5930`) calls
   `window_of` (`tc:5990`) and refuses a `ValueError` as
   `REPORT_WINDOW_WORDS` (`tc:5782`), exit 9. Why report.py: tc's work
   set here is `cmd_report`, its argparse entry and its constants, and a
   parser in tc would have been a new function outside those spots.
2. **Window.** `extract` (`:858`) cuts the records with `in_window`
   (`:820`, from inclusive, to exclusive, no sent time is outside) at
   `:894`, right after the sort and before the partner counts, C5's
   `hierarchy`, `first_mail_levels` and the sessions. So chart 1's counts,
   the roles and levels from mail (cards' `reports_to` still read), the
   first-mail order, the scrub's labels and ranks, T+0 and every chart
   come from the window's records. `unparsed` is counted before the cut.
3. **Read times stay.** Nothing touches `read`: a message sent inside the
   window keeps the read time it has, after `--to` or not.
4. **Ask to answer.** `answer_pairs` sees only the window's records, so
   both ends must be inside. `replies_before` (`:834`) counts, over the
   whole mailbox's records, the window's messages that answer (chart 5's
   rule: names #N, runs back from #N's recipient to #N's sender) a
   message sent before `--from`; `chart_answers` prints `<n> replies name
   a message before this window` (`1 reply names ...` for one) as a
   page-text note (`:1947`), only when the window has a start.
5. **As of.** `page_of` (`:917`) is unchanged in code: its records are
   the window's, so with no `--at` it is the last message inside.
6. **The face.** `summary_lines` (`:1395`) adds `<p class="window">`
   (`:1414`) from `window_words` (`:1215`): `From <from> to <to>.`,
   `From <from>.` or `Up to <to>.`, each bound by `bound_text` (`:1203`)
   with its offset, to the minute, or to the second when the bound has
   seconds, so a bound is never shown rounded. `scrub` (`:931`, `:973`)
   replaces the bounds with a length in seconds, so the renderer of a
   scrubbed page never holds a bound: `A window of this mailbox,
   <length> long.` in `span_text`'s form.
7. **Tests**, `tests/test_report.py`, `WindowTest` (`:1737`, 13 tests),
   over the three-day mailbox `WINDOW_MESSAGES`
   (`tests/_report_fixture.py:102`), built by `build` (`:136`), which now
   takes the messages and inboxes.
8. **README** (`README.md:239`, `:585`) and **QA** step 13a
   (`qa/human/report.md:126`).

## My calls, said here as the brief asks

- **A one-bound length.** With only `--from` or only `--to`, the scrubbed
  length runs from the first to the last message inside the window. With
  both, it is `--to` less `--from`.
- **"Quiet stretches, bounded by the window."** I read it as: gaps come
  only from the window's messages, so no gap runs across `--from` or
  `--to`. The lanes' axis still runs from the window's first message to
  its last, not from `--from` to `--to`, so no quiet stretch is drawn
  between `--from` and the first message. That keeps T+0 at the first
  message, as C7 says. The test: corwin's 22:00 to 01:00 gap across the
  middle day's start is gone from the window's chart 4.
- **What counts as a reply before the window.** A message inside the
  window that would answer that message by chart 5's rule, direction
  included, whether or not it is the first answer. One reply counts once.
- **Order of refusals.** `cmd_report` now loads report.py first, then
  checks the bounds, then opens OUT's folder. A bad bound with an
  existing OUT exits 9 and leaves OUT alone (tested). A one-file copy of
  tc now says it has no renderer before it judges OUT; both are exit 1.
- **A broken header inside a window.** The page says `<n> message had a
  header line that did not parse, so it has no sent time and is outside
  this window.` in place of the line that says chart 1 counts it, since
  chart 1 does not count it inside a window.
- **An empty window** says `No messages in this window.`, not `No
  messages yet.`

## Red, then green

`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_report`:

| Run | Result |
|---|---|
| Red, before any code | `Ran 64 tests`, `FAILED (failures=17, errors=8)`: no `window_of` (the in-process tests), and tc's `--from` unknown (exit 9 from argparse, but no `tc report:` words, no window line) |
| Green, at `45b6605` | `Ran 64 tests`, `OK` |

## Mutations

Each on a `git archive` copy of `45b6605` in the scratchpad, with
`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_report`:

| Mutation | Result and red line |
|---|---|
| The window ignored (`extract` never cuts) | `FAILED (failures=16)`: `Tuples differ: (1, 2, ..., 17) != (7, 8, 9, 10, 11, 12, 13, 14)`, and `Lists differ: [(2, 8), (7, 9), (10, 11), (13, 15)] != [(7, 9), (10, 11)]` |
| T+0 from the whole history (the scrub's origin set to the mailbox's first sent time) | `FAILED (failures=2)`: `Lists differ: [(1, 57600, 61200, ()), ...] != [(1, 0, 3600, ()), ...]` |
| The scrubbed page printing `--from` (the scrub passes the bounds through) | `FAILED (failures=4)`: `<re.Match object; span=(2947, 2957), match='2026-10-02'> is not None` |

The third first went red on the length line, ahead of the date check. I
moved the date, clock and name checks ahead of the length check in that
test, so a leaked bound now fails as a date leak; the three runs above
are on the commit with that order.

## The fixture page

The three-day mailbox's middle day, scrubbed, written by the command at
`45b6605` to the architect session's scratch folder, not in the repo.

## Not verified

- No person has walked step 13a. I ran its two commands on the walk
  fixture and read the words from those pages; the step's expected words
  are those.
- Local time is tested with two POSIX zones that have no daylight time
  (`EST5`, `UTC0`). A date-only bound on a daylight-time change day in
  a real zone takes that day's midnight offset from Python's
  `astimezone()`; not tested.
- A bound that falls in a local-time gap (the hour skipped in spring) is
  resolved by `astimezone()`; not tested.
- I have not looked at a window page in a browser. Its only new element
  is one line of page text, `<p class="window">`, styled as body text.

## Fix round 1 (audits/2026-10-18-0000-quick, and C7 at dev dc166ae)

<!-- Fix round 1 section added by Claude Opus 5.5 (the WINDOW lane agent), 2026-10-18. Status: unreviewed. -->

One code commit, `864dd06`, and this section's commit. Line numbers are
at `864dd06`.

1. **MEDIUM-1, as the relay ruled it into C7.** When both bounds are
   dates with no time, the scrubbed length is whole calendar days,
   `1 day` or `3 days`. Any other window's length is real elapsed time,
   as before, and T+ times stay real. The coordinator's first item 1 (a
   wall-clock difference) was replaced by this ruling before I wrote any
   code for it, so it was never built.
   - `calendar_date` (`board/report.py:835`) keeps a bound's date when
     its text is a date with no time (`date.fromisoformat` takes it);
     `Window` (`:403`) gained `start_date` and `end_date`.
   - `scrub` (`:1035`) gives `Length(None, days)` for two dates, else
     `Length(seconds, None)`. `Length` (`:408`) is a type of its own, so
     a scrubbed page's window is never a `Window` (DEBT-1, done in
     passing: `window_words` at `:1285` now tests for `Length`).
   - Under America/Chicago: 2026-11-01 to 2026-11-02, 2026-03-08 to
     2026-03-09 and 2026-10-02 to 2026-10-03 each read `1 day`;
     2026-11-01 to 2026-11-04 reads `3 days`; 2026-11-01T00:30 to
     2026-11-01T03:00 reads `3h30m`; offset bounds -05:00 to -06:00 a
     day apart read `1d01h`. The real face of the fall day prints
     `From 2026-11-01 00:00-05:00 to 2026-11-02 00:00-06:00.`
   - **The skipped spring hour.** `--from 2026-03-08T02:30` under
     America/Chicago names a local time that does not exist.
     `astimezone()` moves it forward by the skip: the page reads `From
     2026-03-08 03:30-05:00 to 2026-03-09 00:00-05:00.`, exit 0, no
     traceback. So the window starts at 03:30, which is the same instant
     as 02:30 CST would be (08:30 UTC). The test asks only for exit 0, no
     traceback and one window line; the face above is from a run.
2. **LOW-1.** `window_time` (`:829`) catches OverflowError, OSError and
   ValueError around `astimezone()` and raises `WINDOW_PLACE_WORDS`
   (`:166`), which name the flag and its text; tc refuses, exit 9. On
   this machine's Python the raw error was ValueError (`year 0 is out of
   range`), which tc already turned into exit 9, but with words that
   named neither the flag nor the bound. The test asks for the flag and
   the text, so it was red on that. Year 1 under Europe/Berlin and
   9999-12-31T23:00 under EST5.
3. **LOW-2.** `empty_words` (`:1295`) gives `EMPTY_WINDOW_WORDS` on a
   windowed page and `EMPTY_WORDS` otherwise; the summary and all five
   charts use it. No hard-coded `No messages yet.` is left.
4. **LOW-3, confirmed by the relay.** `WINDOW_ASK_CAVEAT` (`:332`)
   inserts C7's words after "answers without naming the ask": `A session
   that does not put #N on its first line answers without naming the
   ask, or one that replied after this window ends, so this count can
   include asks that were answered.` `chart_answers` (`:2028`) uses it on
   a windowed page only.
5. **LOW-4, no code.** Recorded in `scrub`'s doc block (`:1008`) as a
   known one-bit residual: a declared reports_to cycle whose members are
   all idle in the window breaks at the name that sorts first, and a
   drawn name below it can sit one row off.

**Tests** (`tests/test_report.py`, WindowTest): the daylight days and
three-date window (`:2001`), the fall day's two offsets (`:2025`), the
skipped hour (`:2040`), the unplaceable bounds (`:2056`), the empty
window (`:2077`), the caveat (`:2095`). One earlier case moved from
`1d00h` to `1 day`: the date-only case of the scrubbed-length test, as
C7 now says.

**Red, then green** (`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest
tests.test_report`):

| Run | Result |
|---|---|
| Red, new tests only | `Ran 70 tests`, `FAILED (failures=8)` |
| Red, with the 1 day case moved | `Ran 70 tests`, `FAILED (failures=9)` |
| Green, at `864dd06` | `Ran 70 tests`, `OK` |

Three of the new cases passed before the code, since the old code
already gave real elapsed time there: the timed `3h30m` window, the
offset `1d01h` window, and the skipped-hour run. They pin behavior C7
keeps. The fall day's real face passed before too.

**Mutations** (`git archive` copies of `864dd06`,
`PYTHONDONTWRITEBYTECODE=1`):

| Mutation | Result and red line |
|---|---|
| 1: two dates counted in seconds again | `FAILED (failures=5)`: `'<p class="window">A window of this mailbox, 1 day long.</p>' not found` |
| 2: no catch around `astimezone()` | `FAILED (failures=2)`: `"--from '0001-01-01'" not found in 'tc report: year 0 is out of range; nothing was written.\n'` |
| 3: `empty_words` always `No messages yet.` | `FAILED (failures=1)`: `'No messages yet.' unexpectedly found` |

**The fixture page**, re-rendered at `864dd06` to the same path, with
the same offset bounds as before, so its face still reads `A window of
this mailbox, 1d00h long.` (real elapsed time, as C7 says for bounds with
a time). It now carries the windowed caveat. No date or clock pattern
in it.

**Runs at `864dd06`.** `python3 -m unittest discover -s tests -p
'test_*.py'`: `Ran 462 tests in 268.930s`, `OK`. `node --test
tests/*.test.mjs`: `# tests 68`, `# pass 68`, `# fail 0`.

**Not verified this round.** The tests read America/Chicago and
Europe/Berlin from the system's tz database. Since `33c1c94` a test
that needs one skips, with words naming the zone, when its file is
missing under TZDIR or /usr/share/zoneinfo (`needs_zone`); a scratch
copy with both set to a made-up zone ran WindowTest as `Ran 19
tests`, `OK (skipped=4)`, and the year-1 test's EST5 subtest still
ran. The full suite at `33c1c94`: `Ran 462 tests in 255.268s`, `OK`;
`# tests 68`, `# pass 68`, `# fail 0`. No person has looked at
a page for a change day. REC-2 (a February page reads `28 days`) is the
architect's, as the synthesis says.
