# QA-2: a test outside QA's work set that QA on SCRUB_TAGS makes wrong

Model:  Claude Opus 5.5 (the QA lane agent), 2026-10-18
Status: unreviewed
Pause:  settled by a2 for the owner, 2026-10-18, option 1 (fix round 1's list)

## The question

The brief lets QA edit `board/report.py` only to add QA to `SCRUB_TAGS`
(C7, D45). `tests/test_report.py`, which is not in QA's work set, pins
the old list:

```
ScrubTest.test_the_allow_list_is_c7s
    """SCRUB_TAGS holds exactly C7's seventeen tags.
```

and asserts a set of seventeen tags without QA. With QA added, as C7 now
reads, that test fails, so the full suite cannot be green without
touching it. May QA change it, or does the architect at the merge?

## Options

1. **QA edits the one test**: `seventeen` becomes `eighteen` in its doc
   line and `"QA"` joins the asserted set. The test then pins C7 as C7
   reads since D45. Nothing else in `tests/test_report.py` changes.
2. **QA leaves it**, and the suite runs with one failure until the
   architect makes the same edit at the merge.

## Recommendation

Option 1, built that way, so every count in QA's report is from a green
suite. The edit is two lines; the handoff names them. If a2 picks option
2, revert those two lines and the suite shows that one failure.

The README's report section lists the tags a scrubbed page keeps; QA
adds `QA` to that sentence too, since the README is in QA's work set and
the sentence would otherwise be false.
