# GROUND-1: two gaps in the voice checkers

Model:  Claude Opus 5.5 (the GROUND lane agent), 2026-10-14
Status: unreviewed
Pause:  half settled. The American English half is settled; the
        `CLAUDE.md` half is open, and the owner's.

## Settled: the American English check

`check_american.py` was fixed in the owner's conventions folder (commit
`918e260` there). It now scans the paths it is given and exits 1 on a
hit, so rule 12's command works as written.

## Open, the owner's: phrases in a file named CLAUDE.md

`voice-rules.yaml` exempts any file named `CLAUDE.md` from phrase
matching, so `check_voice.py` checks only characters and slang there; the
exemption lets a guide quote the phrases it bans. Until the owner decides,
a `CLAUDE.md` is voice-checked by copying it to another name first and
checking the copy.

The exemption earns its place. Checked as copies under another name on
2026-10-14, the owner's conventions guide (`~/Conventions/CLAUDE.md`)
fails 11 phrase checks and the global agent guide fails 8, because both
quote the banned list on purpose. This repo's `CLAUDE.md` fails none.

### Options

1. **Narrow the exemption.** In `voice-rules.yaml`, replace the bare
   `CLAUDE.md` entry with path entries for the guides that quote the
   list. Every project's `CLAUDE.md` is then phrase-checked by the plain
   command. Cost: the checker matches a path entry only inside the
   conventions folder (a file outside it is matched by its bare name), so
   the global agent guide loses its exemption unless the checker learns
   to match paths outside the folder too.
2. **Keep the exemption and the copy.** Nothing changes; `CLAUDE.md`'s
   Commands section already says to check a copy. Cost: a manual step
   every agent must remember, and forgetting it passes silently.
3. **A flag that ignores the exemption lists.** `check_voice.py` gains
   one flag (for example `--no-exempt`) that phrase-checks the files it is
   given whatever the lists say, and this repo's Commands section uses it
   on `CLAUDE.md`. The guides that quote the list keep their exemption.
   Cost: a small change to the owner's checker, and the flag still has to
   be typed.

### Recommendation

Option 3. It keeps the owner's guides passing their own check, needs no
path matching outside the conventions folder, and turns the copy step
into one command a fork can read off the Commands block. The question
stays the owner's, because options 1 and 3 change his conventions folder.
