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
