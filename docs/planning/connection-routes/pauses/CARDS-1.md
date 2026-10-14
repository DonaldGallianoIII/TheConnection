# CARDS-1: `tc card x --ssh -oProxyCommand=y` cannot exit 6 as written

Model:  Claude Opus 5.5 (the CARDS lane agent), 2026-10-14
Status: unreviewed
Pause:  open. Built to the recommendation below; nothing waits on it.

## The question

`phases.md` R2's test list says `tc card x --ssh -oProxyCommand=y`:
exit 6, nothing written. With a space between `--ssh` and the value, that
never reaches tc's target check. argparse reads `-oProxyCommand=y` as a
flag, so `--ssh` has no value and the parser refuses first. Seen in Python
3.12.3: `argument --ssh: expected one argument`, a usage error (exit 2
before R6, 9 after).

It is the same case as R1's `--to -x`, which the plan already rewrote to
the `=` form.

## The options

1. Test both forms: `--ssh=-oProxyCommand=y` exits 6 with the target
   words; `--ssh -oProxyCommand=y` is a usage error. Both write nothing.
2. Make the space form exit 6 by changing how `--ssh` parses (for
   example `nargs` tricks or reading argv by hand). That fights the parser
   and gives one flag a rule no other flag has.

## Recommendation

Option 1, which is what is built. `tests/test_cards.py`
(`test_a_bad_ssh_target_or_remote_path_writes_nothing`) checks both forms,
and `tests/test_usage.py` pins the space form at 9. Amend the R2 line in
`phases.md` the way R1's was amended.
