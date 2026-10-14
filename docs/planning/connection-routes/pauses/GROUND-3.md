# GROUND-3: plan files in the base commit name things a public repo should not

Model:  Claude Opus 5.5 (the GROUND lane agent), 2026-10-14
Status: unreviewed

## The question

The owner said on 2026-10-14 that this repo is public, and that nothing in
it should name the work machine's paths, the employer, or the employer's
sessions and products. GROUND's own files follow that. Files already in
the lane's base commit (`b6a95d4`) do not:

- `docs/planning/connection-routes/00-index.md`: the header names the
  planner session; rule 12 names the work machine's conventions path.
- `docs/planning/connection-routes/phases.md`: the header names the
  planner session; tasks G1 and G2 name the work machine's conventions
  path.
- `docs/planning/connection-routes/contracts.md`: the header names the
  planner session; C0's suggested names and the board port note name the
  employer's product.
- `docs/planning/connection-routes/decisions.md`: D1, D4 and D5 name the
  planner session or the employer's product.
- The board look kit, from the Daylight commit: `board/theme.css` (its
  header and the Daylight block), `board/compare.html`, `board/demo.html`,
  `board/demo-script.json` (a demo session's id and title),
  `qa/human/board-look.md` step 7, and two comments in
  `tests/board-theme.test.mjs`. All name the employer's product or a
  short form of it.
- The commit message of `1791cbf` names the employer's product and a path
  in its code.

Found with `git grep` on `b6a95d4`. These are outside GROUND's files, so
GROUND did not touch them. Who scrubs them, and what about the history?

## Options

1. **The architect, or a small fix lane, scrubs these files** in one
   commit on the integration branch after GROUND merges. The words leave
   the current tree; the history keeps them. The board files need care:
   the Daylight look's colors stay, only the names go.
2. **Leave the files as they are.** Every lane brief keeps quoting them.
3. **Rewrite history** to drop them from old commits too. Destructive;
   only the owner can decide it, and only matters if the commits have not
   been pushed anywhere public yet.

## Recommendation

Option 1 now. The owner decides on option 3, starting from whether those
commits are already public.

## What carried on

Nothing in GROUND depends on this. GROUND's own files and commit messages
pass the leak scan the coordinator gave (the handoff says what it found).
