# GROUND-1: the American English check ignores the file it is given

Model:  Claude Opus 5.5 (the GROUND lane agent), 2026-10-14
Status: unreviewed

## The question

Rule 12 says to run `check_american.py` on every Markdown file a lane
writes. `~/Conventions/tools/check_american.py` takes no file argument. It
scans only the conventions folder it lives in (its `ROOT` is its own
parent folder) and prints `american english: clean, 8 file(s) checked`
whatever file is named. Its "clean" says nothing about this repo. Where
should a check that reads the named file live?

A second, smaller gap: `voice-rules.yaml` exempts any file named
`CLAUDE.md` from phrase matching, so `check_voice.py CLAUDE.md` checks
characters and slang only. A planted `CLAUDE.md` holding one banned
phrase from `voice-rules.yaml` came back clean.

## Options

1. **The owner fixes `check_american.py`** in the conventions folder to
   take file paths, as `check_voice.py` does. Every project gets the fix.
   Outside this lane: the conventions folder is read only from here.
2. **A wrapper in this repo** (for example `tools/american-on.py`) that
   loads the tool's word list and runs it on the named files. Adds a file
   no task names, and copies a workaround into a public repo.
3. **Keep the lane coordinator's wrapper**,
   `~/TheConnection-lanes/tools/american-on.py`, outside the repo. Works
   on the owner's machine today; a forker does not have it.

## Recommendation

Option 1, and option 3 until then. `CLAUDE.md` already says so under
Commands, and names the wrapper.

For the `CLAUDE.md` phrase exemption: no change asked. The exemption is
there so a guide can quote the phrases it bans. GROUND checked its
`CLAUDE.md` by running `check_voice.py`'s own `check_file` with the
exemption lists emptied (0 failures); that scratch script is not in the
repo.

## What carried on

Every Markdown file GROUND wrote was checked with the wrapper (option 3):
0 hits. Nothing in GROUND waits on this answer.
