# QA: tc report, the mailbox drawn as one page

Model:  Claude Opus 5.5 (the DASH lane agent), 2026-10-17; fix round 1
        the same day (a setup script, the round's words and refusals)
Status: unreviewed, not yet run by a person.

What this checks: `tc report` writes one page that opens offline, draws
the five charts of contract C7 with the facts a known mailbox holds, and
reads in grayscale as well as in color. A scrubbed page holds no name,
no date and no clock time. Everything here runs on a throwaway mailbox
of made-up names; nothing touches your live one.

The throwaway mailbox is the test suite's own fixture
(`tests/_report_fixture.py`): twelve messages among annika (an
orchestrator), bertil and corwin (workers), and dagny, who only sends
(no card, no inbox). Message 10's header is broken on purpose.

## Setup

1. Open a terminal in the repo (the checkout with `tc` and `board/`).
2. Make a fresh throwaway mailbox and a folder for the pages (a new one
   each walk, so a second walk never meets the first one's pages):
   ```
   eval "$(python3 qa/human/report-fixture.py)"
   echo $TC_ROOT $PAGES
   ```
   - Pass: two paths in a new `/tmp/report-qa-...` folder, and
     `ls $TC_ROOT/mail` shows `to-annika  to-bertil  to-corwin`. No
     `__pycache__` appears under `tests/` (`ls tests | grep pycache`
     prints nothing).
   - Fail: an error, other folders, or a `__pycache__`.
3. Write both pages:
   ```
   ./tc report $PAGES/real.html
   ./tc report $PAGES/safe.html --scrub
   ```
   - Pass: each prints one line, `wrote <PAGES>/real.html: 12 messages, real names and times. Mailbox <TC_ROOT>, from TC_ROOT.`
     and the same for `safe.html` ending `scrubbed. Mailbox ...`, and exits 0 (`echo $?` prints 0).
   - Fail: anything else.
4. Run the first one again, then try a page inside the mailbox:
   ```
   ./tc report $PAGES/real.html; echo $?
   ./tc report $TC_ROOT/mail/x.html; echo $?
   ```
   - Pass: one line opening `tc report:` saying the file already exists
     and to pass `--force`, then `1`; then one line opening `tc report:`
     saying the folder is inside the mailbox, then `1`, and no `x.html`
     in `$TC_ROOT/mail`.
   - Fail: exit 0, the file changed (its time in `ls -l` moved), or a page in the mailbox.

## The real page

5. Open `$PAGES/real.html` in a browser (File, Open). Turn off the
   network first if you can (the browser's offline mode, or unplug).
   - Pass: the page draws whole, offline. At the top, a box reading
     `Warning: Holds real session names and times. Share only a --scrub copy.`
     Under it: `12 messages among 4 sessions, sent from 2026-10-01 09:00-05:00 to 2026-10-02 02:00-05:00.`,
     `As of 2026-10-02 02:00-05:00.`, and a line saying 1 message had a
     header line that did not parse.
   - Fail: anything missing, or the page waits on the network.
6. **Chart 1, who talks to whom.**
   - Pass: `annika · orchestrator` on top in a square box with a heavy
     line; `bertil · worker` and `corwin · worker` under it in rounded
     boxes; `dagny · no role` at the bottom in a dashed box. Arrows, each
     with a count: annika to bertil 3, bertil to annika 3, annika to
     corwin 2, corwin to annika 2, bertil to corwin 1, dagny to bertil 1.
     The two arrows of one pair bend apart. Hovering an arrow shows its
     words, as `annika to bertil: 3 messages`.
   - Fail: a count or role wrong, two arrows on top of each other, or a
     role you can tell only by color.
7. **Chart 2, messages over time per sender.**
   - Pass: four rows, labeled at their left: annika `5 sent · peak 2 in an hour`,
     bertil `3 sent · peak 1 in an hour`, corwin `2 sent · peak 1 in an hour`,
     dagny `1 sent · peak 1 in an hour`. annika's first bar is twice as tall
     as the rest. The axis runs from 2026-10-01 09:00-05:00 to
     2026-10-02 02:00-05:00.
   - Fail: a row missing, or bars that do not match the words.
8. **Chart 3, from sent to read.**
   - Pass: three strips. annika `3 of 5 messages have a read time`,
     `median 20m`; bertil `3 of 4 ...`, `median 5m`; corwin `1 of 2 ...`,
     `median 30m`. Each strip has that many dots. Hovering a dot names its
     message, as `#2 QUESTION from bertil: read 2026-10-01 09:12-05:00, after 2m`.
     The axis under the strips reads `0s`, `1m`, `10m` and, at its far
     end, `40m`, the longest wait.
   - Fail: a count, a median or a dot wrong.
9. **Chart 4, busy and quiet stretches.**
   - Pass: four lanes. Each has `▲ sent` above its line and `● received`
     below it, and the ticks match: solid ticks up tipped with a
     triangle, dashed ticks down tipped with a dot. Hatched boxes, each
     with its length written in it: annika `quiet 11h00m`; bertil
     `quiet 3h00m` and `quiet 10h00m`; corwin `quiet 12h50m`; dagny none.
   - Fail: a gap missing or mislabeled, or sent and received told apart
     only by color.
10. **Chart 5, from ask to answer.**
    - Pass: two strips. annika `2 answers`, `median 20m`; bertil
      `2 answers`, `median 55m`. Under them: `4 answers name the message they answer. 1 ask has no reply that names it.`,
      then a line saying a session that does not put #N on its first
      line answers without naming the ask, so this count can include
      asks that were answered. Hovering annika's right dot shows
      `#5 ZEBRAPLANT to #6: 30m`.
    - Fail: a pair that should not be there (message 7 runs the wrong
      way, message 8 names no number), or a count wrong.
11. Search the page (Ctrl+F) for `SECRETWORDA`, `SECONDLINEPLANT`,
    `NOTEPLANT`, `ACCOUNTPLANT` and `STATUSPLANT`.
    - Pass: none found. These are words planted in message text, a
      header note, a card and a status file, which the report never reads.
    - Fail: any found.

## The scrubbed page

12. Open `$PAGES/safe.html`.
    - Pass: the top box starts `Scrubbed:`, says what that means and
      lists the tags it keeps; no warning box. The names read
      `orchestrator-1`, `worker-1`, `worker-2` and `session-1` (dagny),
      each node in chart 1 its label alone, with no role word after it. Times read `T+0` to `T+17h00m`.
      Chart 5's dot reads `#5 other to #6: 30m`.
    - Fail: any of annika, bertil, corwin, dagny or ZEBRAPLANT anywhere
      (search with Ctrl+F), or any date or clock time such as `2026` or
      `09:00`.
13. Check each chart against its words as in steps 6 to 10, with the
    labels for names.
    - Pass: the same counts, medians and gaps.
    - Fail: any differ.

## Grayscale and dark

14. Turn on grayscale: in Chrome or Edge, DevTools, Ctrl+Shift+P, "Show
    Rendering", "Emulate vision deficiencies", Achromatopsia. Or the OS
    filter (Windows: Win+Ctrl+C once color filters are on in Settings).
    Look at both pages again.
    - Pass: every chart still reads. In chart 4, sent and received differ
      by direction, dash and marker shape. In chart 1, roles differ by
      outline and words. The hatch shows. All text is readable.
    - Fail: two things that mean different things look the same.
15. Set the OS or browser to dark mode and reload.
    - Pass: a dark page with light text, every chart readable.
    - Fail: dark text on dark, or a chart that vanishes.
15a. Make the browser window narrow, as a phone (DevTools, the device
    toolbar, 390 px wide).
    - Pass: each chart keeps its words readable and scrolls sideways
      inside its own box; nothing shrinks to a size you must squint at.
    - Fail: a chart whose text shrinks with the window.

## Clean up

16. `unset TC_ROOT PAGES`. The `/tmp/report-qa-...` folder (the
    mailbox and the pages) is yours to remove; nothing else was written.
