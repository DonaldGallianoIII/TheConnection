# CARDS-4: three fields of a `tc card` card that C1 leaves open

Model:  Claude Opus 5.5 (the CARDS lane agent), 2026-10-14
Status: unreviewed
Pause:  settled by D13 (a2, for Donald, 2026-10-14). Items 1 and 2
        stand as built (exit 1, kind `other`). Item 3 takes the other
        option, built in the CARDS fix round 1 (commit 8bb1f8b):
        `--account`, else `unknown`, never `CLAUDE_CONFIG_DIR`.

C1 says how `tc join` fills a card. For `tc card` (a name on another
machine) it names the flags but leaves three things open.

## 1. The exit code when unread mail refuses the card

C1: "refused with words naming the count ... unless `--force`". The exit
table has no row for it. Row 1 is "refused with words" for `send`,
`join` and the router; row 6 lists `card` only for a bad name, a
self-report, a bad target or path.

- Built: exit 1, the "refused with words" code.
- Other option: 6, with the other `card` refusals.
- Recommendation: 1, and add `card` to row 1's "who" column.

## 2. The kind

C1 sets `kind` only for `tc join`, from the environment. The environment
of the session running `tc card` says nothing about the far name.

- Built: `other`.
- Other options: a `--kind` flag on `tc card`; or null.
- Recommendation: `other` now; a `--kind` flag if the board needs to
  draw a far Codex differently.

## 3. The account default

C1's account row is general: `--account`, else the base name of
`CLAUDE_CONFIG_DIR`, else `unknown`. Applied to `tc card`, that labels a
far name with the account of the local session that wrote the card.
Seen on the home machine: `CLAUDE_CONFIG_DIR` is set there, so
`tc card x --ssh u@h` wrote this session's own account label on x's card.

- Built: C1's chain as written, for both commands.
- Other option: for `tc card`, `--account`, else `unknown`.
- Recommendation: the other option. A wrong label is worse than
  `unknown`.
