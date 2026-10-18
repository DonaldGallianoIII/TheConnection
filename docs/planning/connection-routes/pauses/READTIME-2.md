# READTIME-2: three tests outside READTIME's work set that the read-time record makes wrong

Model:  Claude Opus 5.5 (the READTIME lane agent), 2026-10-17
Status: unreviewed
Pause:  open

## The question

READTIME's brief lets the lane edit existing tests "only where they pin
tc log's output line for line". Three tests outside that list assert the
exact names in a `read/` after a `tc read`. Since READTIME, that read
leaves the read-time record, `read/.read-times`, beside the messages, as
pause READTIME-1 says it must. Each list lacks it, so five subtests
fail. May READTIME change them, or does the architect change them at the
merge?

This is F1-1's question again (the wait exit record in test_shared's
file list), which a2 settled as option 1.

### The five failures

From the full suite at the lane's build commit, `Ran 387 tests`,
`FAILED (failures=5)`. Every other test passes.

1. `tests/test_inbox_pinned.py`, line 629, in `check`, row (d), `tc
   read`, both kinds of swap (`link`, `real folder`):

   ```
   AssertionError: Tuples differ: ([], ['.read-times', '000001-from-ben.md']) != ([], ['000001-from-ben.md'])
   ```

   The record is in the real `read/`, the one tc pinned, which is what
   D35 wants. The far end is untouched (the row's earlier assertions
   pass).

2. `tests/test_shared.py`, line 2621,
   `NoLostMailNoHangTest.test_a_send_after_mail_seq_is_set_back_never_takes_a_read_messages_name`,
   both subtests (`shared=False`, `shared=True`):

   ```
   AssertionError: Lists differ: ['.read-times', '000001-from-a.md', '000002-from-a.md'] != ['000001-from-a.md', '000002-from-a.md']
   ```

3. `tests/test_shared.py`, line 1302,
   `RegularFilesOnlyTest.test_a_link_or_fifo_planted_as_a_message_is_never_printed_and_stays_in_place`:

   ```
   AssertionError: Lists differ: ['.read-times', '000001-from-a.md'] != ['000001-from-a.md']
   ```

## The options

1. **The lane adds the record to each list** (recommended). Three
   one-line changes, each with a comment naming READTIME:
   - `test_inbox_pinned.py:629`: `([], [".read-times", "000001-from-ben.md"])`.
   - `test_shared.py:2621`: `[".read-times", "000001-from-a.md", "000002-from-a.md"]`.
   - `test_shared.py:1302`: `self.assertEqual(moved, [".read-times", "000001-from-a.md"])`.
     `moved` is every name in `read/` (`test_shared.py:1283`), so the
     record belongs in it.
   Each test then also proves the record lands in the pinned `read/`,
   which row (d) of the class proof gains for free.
2. **The tests list messages only.** Filter each listing on the `.md`
   suffix. The tests stay about messages, but nothing outside
   `test_read_times.py` notices a record in the wrong place.
3. **The architect changes them at the merge.** The lane branch keeps
   five known failures until then.

## Recommendation

Option 1, as F1-1 was settled. Until it is settled, the lane changes
none of the three files, the full Python suite has these five known
failures, and every READTIME commit message and the handoff say so.
