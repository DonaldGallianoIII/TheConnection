# CARDS-5: C3 would quote the default remote path, so `~` never expands

Model:  Claude Opus 5.5 (the CARDS lane agent), 2026-10-14
Status: unreviewed
Pause:  settled by D13 (a2, for Donald, 2026-10-14). Option 1, for the
        SSH lane to build in S1: a leading `~/` goes bare and the rest is
        quoted; `~` alone and `~user/...` are refused with exit 6; the far
        side is assumed to run a POSIX login shell, which the README says.
        `tc card` already refuses both `~` forms; the CARDS fix round 1
        added their tests (commit 8bb1f8b).

## The question

C1 makes `~/TheConnection/tc` the default remote path on an ssh card,
and CARDS stores it as written. C3 builds the remote command with
`shlex.join([card["ssh"]["tc"], "send", "--from", sender, "--to", to])`.
`shlex.quote` quotes any word holding `~`, so the far side gets

```
'~/TheConnection/tc' send --from a --to b
```

and a POSIX shell does not expand a quoted `~`. Checked by hand:
`shlex.join` printed exactly that line, and `bash -c "echo '~/x' ~/x"`
printed `~/x` for the quoted word and the home path for the bare one.
Every send to a card made without `--remote-tc` would fail on the far
machine with "no such file".

## The options

1. In `deliver_ssh`, send a leading `~/` bare and quote only the rest:
   `"~/" + shlex.quote(path[2:])`.
2. `tc card` refuses `~/` and requires an absolute path (changes C1).
3. The far side runs the path through `sh -c 'exec "$HOME"/...'` (more
   moving parts on the far side).

## Recommendation

Option 1. It keeps C1's default, and the rest of the path stays quoted.
The SSH lane's S1 test can assert the exact remote command line for a
card made with no `--remote-tc`.
