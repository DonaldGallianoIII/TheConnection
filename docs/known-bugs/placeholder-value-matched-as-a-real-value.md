# placeholder-value-matched-as-a-real-value

Model:  Claude Opus 5.5 (the known-bugs writer, for the architect session), 2026-10-15
Status: unreviewed

**What:** a filter guards a field against "missing" with `is not None`,
truthiness or `!== undefined`. But the code that writes the field stores
a placeholder string (`unknown`, `""`, `n/a`, `default`) when it does not
know the value. The placeholder passes the guard and is then grouped,
joined or compared like a real value, so every record holding it matches
every other.

**How it showed:** the BOARD lane, 2026-10-14. At `d250036`,
`board/serve.py:592` grouped claude cards by account and dropped only
`None`. tc's card writer stores `unknown` when no account is given and
none can be found (`UNKNOWN_ACCOUNT`, now `tc:124`), which is the default
case. So every pair of default cards got a `native · not observed` link:
five sessions drew ten false claims that they share an account. The count
grows as k(k-1)/2.

**Why it's bad:** the screen asserts a relationship that no record
states, here that two sessions share an account. The false lines grow
with the square of the count and bury the real ones.

**Prevention:** name the placeholder as a constant
(`ACCOUNT_UNKNOWN = "unknown"`), and make every group-by, join and
equality test exclude both `None` and that constant. Best is one constant
that the writer and every reader share. Here the word is spelled four
times today (tc's `UNKNOWN_ACCOUNT`, `ACCOUNT_UNKNOWN` in `board/serve.py`
and in `board/look.js`, and a copy in `tests/test_board_feed.py`), and no
test pins them equal. Pair the test of two placeholder records (expect no
match) with a control pair on a real value (expect one match), so the
test cannot pass by never matching.

**The check that catches it:** `tests/test_board_feed.py`,
`ShapesTest.test_no_native_link_on_account_unknown`: two claude cards on
`unknown` give no native link, and two on `home` give exactly one (the
control). The page holds the same guard: `tests/board-patch.test.mjs`,
"both boxes and both outline rows of a native pair say native with the
other, not observed, with mail or without", draws no badge for two cards
on `unknown` even when a native link is handed in. One limit: the feed
test writes its cards by hand with its own copy of the word, so it
catches a reader that drops its guard, not a writer and reader that drift
apart.

**Detection:** a group-by, a dict of lists keyed by a field, or a
pairwise loop (`combinations(`, nested loops over a group) whose only
guard on the key is `is not None`, `if key:` or `!== undefined`. Then grep
the code that writes that field for a string fallback: `or "unknown"`,
`?? 'unknown'`, `default="`, `.get(key, "`, or a constant named UNKNOWN or
DEFAULT. A fallback string the guard does not exclude is a hit.

**Source:** the BOARD lane's full review, 2026-10-14 (audit folder
`2026-10-14-1811-full`; review audits stay out of the repo), HIGH-3.
Closed by `062dec9` (the named constant and the feed test above); the
page's guard and its badge test came with `4cf941d`. Both reached the dev
branch with the BOARD merge, `a2953cb`. A related shape, not counted
here: in the P4 phase review (audit folder `2026-10-14-2344-full`, LOW-3),
look.js's `n.unread > 0` drew an unknown (null) count as no unread mail;
`9095578` made it read `unread unknown` in words.

**Times hit:** 1.

**Tier when hit:** HIGH. Caught as HIGH because the approved contract
forbids links on `unknown`. Where no contract rule stands behind a hit, it
is still wrong output on the default path; a review may file such a hit
lower only by citing why it is milder.

**Shared catalog:** a form of "A check that passes by not checking."
(`~/Conventions/code/known-bugs/any-language/tests-and-checks.md`). That
entry's guard tests a sentinel the callee never returns. Here the guard
tests `None` while the writer's sentinel is `unknown`. The failure
differs: false matches, not a silent pass.
