# CARDS-3: phases.md R6's reason for its "must reject" does not hold

Model:  Claude Opus 5.5 (the CARDS lane agent), 2026-10-14
Status: unreviewed
Pause:  open. The test rejects the mutation anyway; only the plan's
        sentence is wrong.

## The question

R6 says: must reject an override on the top parser only, because "the
`wait` typo goes through the subparser, so it would still exit 2". In
Python 3.12.3 it does not. `tc wait --timeot 1 b` reaches the `wait`
parser, which takes `1` as the name and hands `--timeot` and `b` back as
leftovers; the top parser then refuses them (`unrecognized arguments`).
So with the override on the top parser only, that case still exits 9.

Seen by hand with the mutation applied (`parser_class=argparse.ArgumentParser`
on `add_subparsers`): `tc wait --timeot 1 b` exited 9, and the six cases
a subcommand's own parser finds exited 2.

## The options

1. Keep `tc wait --timeot 1 b` as the D12 case (it is the typo a session
   makes) and add cases the subparser finds, which catch the mutation.
2. Drop the `--timeot` case. It still guards the plain bug (no override
   at all exits 2 there), so dropping it loses that.

## Recommendation

Option 1, which is what is built. `tests/test_usage.py` keeps
`--timeot`, and `test_every_subcommand_parser_exits_9` holds six cases a
subcommand's parser finds: `send --to b hi` (the plan's own), `wait` with
no name, `wait b --timeout soon`, `send --to -x`, `card --ssh
-oProxyCommand=y`, and `join --kind robot`. Under the top-only mutation
all six go red. Amend R6's sentence in `phases.md` to name the missing
`--from` case as the one that rejects it.
