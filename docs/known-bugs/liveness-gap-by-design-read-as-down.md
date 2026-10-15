# liveness-gap-by-design-read-as-down

Model:  Claude Opus 5.5 (the known-bugs writer, for the architect session), 2026-10-15
Status: unreviewed

**What:** a monitor labels a worker failed (`down`, `dead`, `offline`,
`no listener`) when its liveness signal is missing now but was seen
within a window. The worker drops that signal on purpose as part of its
normal cycle: a one-shot waiter exits when its event arrives and re-arms
only after the work is done. The branch that assigns the failure word
never checks whether that event arrived.

**How it showed:** the P4 phase review, 2026-10-15. At `7daf64a`,
`board/serve.py:741` set `down` for any name with no listener pid that
had been seen listening within `DOWN_WINDOW_S` (600 s):
`elif not pid and name in self.last_listening_at`. But `tc wait` exits 0
when mail lands, and a session re-arms its listener only after its turn.
So every delivery read as a lost listener. A run in a scratch `TC_ROOT`
showed a woken session as `('down', None, 'parsing the logs')` at +0 s
and +60 s, and `idle` at +601 s. Every test reached `down` by killing a
listener, and `qa/human/board-live.md` step 7 listed the alarm as the
expected result right after a normal delivery. The BOARD lane's full
review had raised the same point a phase earlier, as a recommendation (a
`woken` state, which needed a C5 change), not as a finding.

**Why it's bad:** every worker doing its job wears the alarm for its
whole turn, so the alarm nearly always means "working". A worker that
has died looks the same, then fades to a quiet state after the window,
so the real failure stops showing when it matters. On the board:
`✕ no listener`, a warn pill, a dotted wire, and a fresh status shown as
`last status:`.

**Prevention:** before mapping a missing signal to failure, list every
way the signal goes away on purpose, and read the evidence for each: mail
newer than the last time the worker was seen listening, a status written
after the wake, a send. Give the planned gap its own state with its own
glyph and word. D24 does this: `◔ working` within `WOKEN_GRACE_S` (120 s)
of the wake or with a sign of life after it, `△ woken · not read` past the
grace with no sign, and `down` only for a lock that vanished with no new
mail. Bound the wake too: mail that lands after the monitor has already
seen the worker gone is no wake. The first fix missed that, and its
re-review found a killed listener that a relay then mailed reading
`working` under a calm pill (D28). Test the failure state three ways: a
killed worker (expect the failure word), a worker woken by its own event
(expect any other word), and a killed worker mailed afterward (expect the
failure word still).

**The check that catches it:**

- `tests/test_board_feed.py`,
  `FeedTest.test_a_real_wake_reads_working_then_woken_and_never_down`:
  b's real `tc wait` exits on mail; b reads working, woken past the grace,
  and working after `tc read b`, never down. c, killed with no mail, reads
  down: the control.
- `tests/test_board_feed.py`,
  `FeedTest.test_a_sign_of_life_after_a_wake_reads_working`: a fresh
  status or a send after the wake reads working; neither reads woken.
- `tests/test_board_feed.py`,
  `FeedTest.test_mail_to_a_listener_the_board_saw_gone_is_no_wake`: mail
  that lands after the board saw c gone leaves c down.
- `tests/board-patch.test.mjs`, "a woken session warns in its own glyph
  and words and its wire is not the dotted dead wire; a working one is
  calm".

**Detection:** a state branch shaped like
`not pid and name in last_seen` or `now - last_seen < WINDOW` that assigns
a failure word, in a function that reads no arrival record for that name
(inbox mtime, newest message seq, an exit code, a status time). In tests:
every assertion of the failure state follows a `kill`, `terminate`,
`os.kill` or `SIGKILL`, and no test asserts the state after delivering the
event the waiter waits for (a send to that name, then the wait exiting 0).
In QA scripts: a step that lists the alarm as the expected result right
after a normal delivery.

**Source:** the P4 phase review, 2026-10-15 (audit folder
`2026-10-14-2344-full`; review audits stay out of the repo), MEDIUM-1.
Ruled as D24 (`f69f61b`) and built by `3f01a97`. The re-review's
follow-up became D28 (`8bdf363`), built by `95cc3c8`, which keeps the
first poll that found no listener so the wake has an upper bound. All
reached the dev branch with the P4FIX merge, `eb3e187`.

**Times hit:** 1.

**Tier when hit:** MEDIUM. The board's one alarm fired on every normal
delivery, so it could not mark a real failure. Nothing is lost: mail
waits in the inbox.

**Shared catalog:** none fits; the shared catalog has no liveness or
heartbeat entry. In this repo it is the mirror of
`listener-reported-live-without-the-lock` (a "listening" claim with no
lock behind it) and of `poll-without-a-deadline-shows-stale-as-live` (the
false all-clear on the page). This entry is the false alarm.
