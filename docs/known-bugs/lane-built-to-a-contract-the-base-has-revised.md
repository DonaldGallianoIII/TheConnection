# lane-built-to-a-contract-the-base-has-revised

Model:  Claude Opus 5.5 (the known-bugs writer, for the architect session), 2026-10-15
Status: unreviewed

**What:** a lane builds a contract section from its own branch's copy of
the contract file. A ruling on the base branch then revises that section,
often by settling one of the lane's own open pauses. The lane's code,
tests, doc blocks, demo data and QA script all still encode the old rule,
so every check inside the lane passes.

**How it showed:** the BOARD lane, 2026-10-14. The lane was cut at
`89bdd2e`, built C5 (the board's feed) as its own copy read, and filed
pauses BOARD-1 to BOARD-4 on the rules it was unsure of. Its last commit,
`d250036`, landed at 18:10. At 18:13 the dev branch recorded D15
(`58ac11b`), which settled all four pauses. Three rulings broke what the
lane had built:

- State order. The lane checked `listening` first
  (`board/serve.py:556` at `d250036`). D15 says writing, down, listening,
  doorbell, remote, idle.
- Inference. The lane inferred a parent without reading the partner's
  card (`:383`). D15 forbids an inferred edge that inverts a declared one.
- Native links. The lane dropped only a missing account (`:592`). D15
  says never on `unknown`.

A fourth (a cycle's root carries `parent: null`) was filed LOW. At
`d250036` the pause files still read `Pause: open`, and
`tests/test_board_feed.py` pinned the overruled order.

**Why it's bad:** the lane merges a feature that breaks the approved
contract on every rule the ruling changed, and its green tests say it
does not. Here: a session that just sent never shows `writing`, a codex or
ssh session that stopped listening never shows the alarm state, and every
pair of default-account sessions gets a false "shares an account" line.

**Prevention:** before review and before the handoff, the lane re-reads
every contract section it builds from the base branch's copy
(`git show <base>:docs/planning/connection-routes/contracts.md`), not its
worktree's, and checks the base branch's decisions for a ruling on its
pauses. A ruling can land after the handoff, as D15 did three minutes
after `d250036`, so the review and every fix brief build to the base's
text too. BOARD's round 1 fix brief said so in plain words. A pause file
is closed (status changed, ruling cited) in the same commit that carries
out the ruling. The base branch's task tests for that section are the
list the lane's tests must hold.

**The check that catches it:** no test catches the pattern itself. It is
a check across two branches, run with git:

- For each contract section the lane builds,
  `git diff <lane-cut>..<base> -- docs/planning/connection-routes/contracts.md`
  shows no change to that section, or every changed rule has a test in
  the lane.
- For the pauses,
  `git show <base>:docs/planning/connection-routes/decisions.md | grep -n '<LANE>'`
  finds no ruling, or each pause file cites it. Grep the lane's name, not
  each pause id: D15 names BOARD-2 to BOARD-4 by id and settles BOARD-1
  only as "the BOARD pauses", so a grep for `BOARD-1` misses it.

The relay's pattern checker has no shell, so the architect runs both at
each lane review. This instance's three rules are now pinned in
`tests/test_board_feed.py`: `FeedTest.test_state_order_follows_d15`,
`ShapesTest.test_inference_never_inverts_a_declared_edge` and
`ShapesTest.test_no_native_link_on_account_unknown`.

**Detection:** a pause file in the diff whose status line says `open`.
Grep the base branch's decisions.md for the lane's name. A match means
the code has to be read against the base copy of the contract, not the
lane's. Also: a doc block, test comment or QA line that cites a contract
section or decision (`C[0-9]`, `D[0-9]+`, `<LANE>-[0-9]`) where the base
copy of that text differs from the lane's. Read the base copy with
`git show <base>:<path>`.

**Source:** the BOARD lane's full review, 2026-10-14 (audit folder
`2026-10-14-1811-full`; review audits stay out of the repo), HIGH-1 to
HIGH-3, with the stale pauses filed LOW. Closed in the lane's fix round 1:
`062dec9` put the feed on D15's rules with the three tests above, and
`d86f2f5` marked BOARD-1 to BOARD-4 settled by D15. Both reached the dev
branch with the BOARD merge, `a2953cb`. The P4 phase review (audit folder
`2026-10-14-2344-full`) found the rulings and the code agree. The same
setup came back in that phase's fix round with no hit: D24 (`f69f61b`)
rewrote `down` after the reviewed head `7daf64a`, and the fix, `3f01a97`,
was built to D24.

**Times hit:** 1 (one lane, three HIGH findings).

**Tier when hit:** HIGH. On three rules the change did not do what the
approved contract says.

**Shared catalog:** a reverse form of `written-claim-outlives-the-code`:
here the code outlived the text it was built to, and the open pause files
were the forward form. Also a form of `check-that-passes-by-not-checking`,
because the lane's tests pinned the old rules and so they passed. The
conventions copy holds neither slug by name. Its closest entry is "A
check that passes by not checking." in
`~/Conventions/code/known-bugs/any-language/tests-and-checks.md`.
