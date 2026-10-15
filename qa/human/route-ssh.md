# QA: the ssh route, the outbox, tc flush and tc gate, across two machines (C3)

Model:  Claude Opus 5.5 (the SSH lane agent), 2026-10-15
Status: unreviewed

What this checks: mail crosses to a second machine and back, and a key
behind `tc gate` can deliver mail and nothing else (phases.md, SSH). On
the way: every ssh send leaves a record in the outbox (D25); a dead
target keeps its mail in order until `tc flush` (C3, D23); a far
refusal is filed, never retried; a retry of a message already delivered
is answered `already delivered` (D25); the gate delivers as its own key's
name, never as the far `--from`, never forwards to a third machine, and
answers `health --json` without cards (D16, D18).

The tests in `tests/test_ssh_route.py`, `tests/test_flush.py` and
`tests/test_gate.py` prove all of this against a fake ssh. Only a person
runs the real one (rule 5). This script is that run.

Every name here is made up. Use yours, and keep them out of the results:

| Here | What it stands for |
|---|---|
| `homebox` | the machine you send from |
| `farbox` | the other machine |
| `you` | your Linux user on homebox |
| `qa` | your Linux user on farbox |
| `farbox-tc` | an ssh alias on homebox for `qa` on farbox, with the QA key |
| `homebox-tc` | an ssh alias on farbox for `you` on homebox (the way back) |
| `home-a` | the mailbox name on homebox |
| `far-b`, `far-c`, `onward` | mailbox names on farbox |

Before you start:

- Both machines run this branch's `tc`. The far one needs `tc gate` and
  `tc send --origin`: an older far tc answers `--origin` with a usage
  error (exit 9), and every message then lands in `refused/`. If that
  happens, update the far tc, move each file from
  `outbox/to-<name>/refused/` back to `outbox/to-<name>/` by hand, and
  run `tc flush`.
- `qa`'s login shell on farbox is POSIX (sh, bash, dash or zsh). ssh
  hands the remote command to it, and tc quotes for POSIX (C3).
- farbox runs an ssh server you can reach from homebox. The way back
  (steps 18 to 21) needs one on homebox too; WSL2 often has none. If
  so, record those steps as not run.
- Both mailboxes are scratch folders made below, never the live one.

## Setup

1. On homebox, a scratch mailbox with its own copy of tc. A tc's
   mailbox is the folder it lives in unless `TC_ROOT` says otherwise:
   `mkdir -m 0700 ~/tc-qa-home`, then `cp /path/to/this/branch/tc
   ~/tc-qa-home/tc`, then `unset TC_ROOT`. Every `tc` below on homebox
   is `~/tc-qa-home/tc`.
2. On farbox, the same: `mkdir -m 0700 ~/tc-qa`, copy this branch's
   `tc` there as `~/tc-qa/tc` (for example `scp tc farbox:tc-qa/tc` from
   homebox, with your normal key), and `unset TC_ROOT`. Every `tc` below
   on farbox is `~/tc-qa/tc`.
3. On homebox, a key for this test only:
   `ssh-keygen -t ed25519 -N '' -C tc-qa-home-a -f ~/.ssh/tc_qa_ed25519`.
4. On farbox, the gate's line, one key per sending name (C3). Add one
   line at the end of `~/.ssh/authorized_keys`, with the public key from
   homebox's `cat ~/.ssh/tc_qa_ed25519.pub` in place of the last two
   words:

   ```
   command="/home/qa/tc-qa/tc gate --as home-a",no-pty,no-port-forwarding,no-agent-forwarding,no-X11-forwarding ssh-ed25519 AAAA... tc-qa-home-a
   ```

   - `~/.ssh` stays 0700 and `authorized_keys` 0600, or sshd ignores
     the file.
   - The path is absolute: sshd runs the line through `qa`'s shell, and
     a typo here shows as every send refused with that shell's `not
     found`.
5. On homebox, an alias that picks the key, since tc runs plain `ssh
   -- <target>`. Add to `~/.ssh/config`:

   ```
   Host farbox-tc
       HostName <farbox's name or address>
       User qa
       IdentityFile ~/.ssh/tc_qa_ed25519
       IdentitiesOnly yes
   ```

6. On homebox, meet farbox once by hand, since tc runs ssh with
   `BatchMode=yes` and never answers a prompt: `ssh -T farbox-tc`.
   Accept the host key if asked.
   - It prints `tc gate: refused` and exits 7: there was no command, and
     the gate runs nothing else. No shell, no prompt.
7. On farbox: `tc join far-b`. It prints `joined as far-b (...)`.
8. On homebox: `tc card far-b --ssh farbox-tc --remote-tc '~/tc-qa/tc'`.
   - It prints `card written: far-b (other, account unknown, route ssh
     to farbox-tc)` and nothing on stderr (the route is built).

## Mail goes out, and the key speaks only as itself

9. On homebox: `tc send --from home-a --to far-b "hello far"`.
   - It exits 0 and prints `sent over ssh to farbox-tc: sent #1 to
     far-b: /home/qa/tc-qa/mail/to-far-b/000001-from-home-a.md` (the
     numbers are farbox's).
   - `ls ~/tc-qa-home/outbox/to-far-b/sent/` lists
     `000001-from-home-a.md`, the record of the send (D25), and
     `ls ~/tc-qa-home/outbox/to-far-b/` shows no message waiting.
   - On farbox: `tc read far-b` prints `# #1 from home-a to far-b,
     <time>, via ssh gate, key home-a`, then `hello far`.
10. On homebox: `tc send --from someone-else --to far-b "who am I"`.
    - On farbox, `tc read far-b` shows it `from home-a`: the gate takes
      the key's name, never the far `--from`.

## The key can do nothing else

11. On homebox, each of these prints `tc gate: refused` and exits 7, and
    on farbox `ls -la ~/tc-qa/mail/to-far-b/` is the same before and
    after:
    - `ssh -T farbox-tc 'cat /etc/hostname'`
    - `ssh -T farbox-tc '~/tc-qa/tc read far-b'`
    - `ssh -T farbox-tc '~/tc-qa/tc send --from a --to far-b; id'`
    - `ssh -T farbox-tc 'env TC_ROOT=/tmp ~/tc-qa/tc send --from a --to far-b'`
    - `ssh -T farbox-tc '~/tc-qa/tc card x --ssh somewhere'`
12. On homebox: `ssh -T farbox-tc '~/tc-qa/tc health --json'`.
    - It prints the health JSON with no `cards` key, and `"gpus": null`
      (the gate runs no program to ask). On farbox, `tc health --json`
      run there does have `cards`.
13. The gate never forwards (D18). On farbox: `tc card onward --ssh
    elsewhere`. On homebox: `tc card onward --ssh farbox-tc --remote-tc
    '~/tc-qa/tc'`, then `tc send --from home-a --to onward "go on"`.
    - homebox prints `tc gate: onward is not a local name; the gate does
      not forward`, then `refused by farbox-tc (exit 7); filed in
      .../outbox/to-onward/refused/<n>-from-home-a.md, and nothing
      retries it`, and exits 7.
    - Beside it, `<n>-from-home-a.md.stderr` holds the far exit code and
      stderr.
    - On farbox, `ls ~/tc-qa/outbox` shows no `to-onward`: no ssh ran
      there.

## A dead target keeps its mail in order (C3, D23)

14. On homebox, an alias that cannot connect. Add to `~/.ssh/config`:

    ```
    Host farbox-tc-dead
        HostName localhost
        Port 1
    ```

    Then `tc card far-c --ssh farbox-tc-dead --remote-tc '~/tc-qa/tc'`.
15. On homebox: `tc send --from home-a --to far-c "first"`, then `tc send
    --from home-a --to far-c "second"`.
    - The first exits 4: `could not reach farbox-tc-dead (ssh: connect to
      host localhost port 1: Connection refused); kept in outbox:
      .../outbox/to-far-c/<n>-from-home-a.md. Run: tc flush`.
    - The second exits 4 without trying: `farbox-tc-dead has 1 waiting
      in the outbox; queued behind them. Run: tc flush`.
    - `tc flush` tries the first only, says `could not reach` for it and
      `left ...: farbox-tc-dead could not be reached (...)` for the
      second, and exits 4.
16. On homebox: `tc card far-c --ssh farbox-tc --remote-tc '~/tc-qa/tc'`
    (far-c now points at the live alias), then `tc flush`.
    - It prints `#<n> to far-c: sent over ssh to farbox-tc: ...` twice,
      the first message first, and exits 0. `tc flush` again prints
      `nothing waiting in the outbox`.
    - On farbox, `tc read far-c` shows `first`, then `second`.
17. A far tc that is busy is kept, not refused (D23). On farbox, hold
    far-b's inbox lock for 20 s, in the background: `python3 -c 'import
    fcntl, time; f = open("/home/qa/tc-qa/mail/.box-far-b.lock", "a");
    fcntl.flock(f, fcntl.LOCK_EX); time.sleep(20)' &`. At once, on
    homebox: `tc send --from home-a --to far-b "while busy"`.
    - It exits 4: `could not reach farbox-tc (the far tc was busy, exit
      10: tc: another process is holding far-b's lock; try again); kept
      in outbox: ...`.
    - After 20 s, `tc flush` sends it and exits 0.

## A retry never delivers twice (D25)

18. On homebox, put a sent message back as if a crash had left it:
    `cp ~/tc-qa-home/outbox/to-far-b/sent/000001-from-home-a.md
    ~/tc-qa-home/outbox/to-far-b/`, then `tc flush`.
    - It prints `#1 to far-b: sent over ssh to farbox-tc: already
      delivered (origin <32 hex digits>-1-home-a)` and exits 0.
    - On farbox, `tc peek far-b` shows no new message.
    - On homebox, `ls ~/tc-qa-home/outbox/to-far-b/sent/` now also lists
      `by-hand-1-000001-from-home-a.md`, the copy, filed beside the
      first, which is unchanged.

## The way back (C3)

Skip 19 to 22 when homebox has no ssh server, and record them as not
run.

19. On farbox, a key for the way back: `ssh-keygen -t ed25519 -N '' -C
    tc-qa-far-b -f ~/.ssh/tc_qa_back_ed25519`.
20. On homebox, the gate's line for it, at the end of
    `~/.ssh/authorized_keys`, with farbox's `cat
    ~/.ssh/tc_qa_back_ed25519.pub` in place of the last two words:

    ```
    command="/home/you/tc-qa-home/tc gate --as far-b",no-pty,no-port-forwarding,no-agent-forwarding,no-X11-forwarding ssh-ed25519 AAAA... tc-qa-far-b
    ```

21. On farbox, the alias and the card for the way back. A person writes
    this card, on the far machine: the gate refuses `tc card` (C3). Add
    to farbox's `~/.ssh/config`:

    ```
    Host homebox-tc
        HostName <homebox's name or address>
        User you
        IdentityFile ~/.ssh/tc_qa_back_ed25519
        IdentitiesOnly yes
    ```

    Then `ssh -T homebox-tc` once (it prints `tc gate: refused`, exit 7;
    accept the host key), then `tc card home-a --ssh homebox-tc
    --remote-tc '~/tc-qa-home/tc'`.
22. On farbox: `tc send --from far-b --to home-a "hello home"`.
    - It exits 0 with `sent over ssh to homebox-tc: sent #... to home-a:
      ...`.
    - On homebox, `tc read home-a` prints `# #... from far-b to home-a,
      <time>, via ssh gate, key far-b`, then `hello home`.

## Undo every step

23. On farbox: delete the line ending `tc-qa-home-a` from
    `~/.ssh/authorized_keys` (step 4), then `rm -r ~/tc-qa` (steps 2, 7
    and the far mailbox).
24. On homebox: delete the `Host farbox-tc` and `Host farbox-tc-dead`
    blocks from `~/.ssh/config` (steps 5 and 14), and farbox's host key
    that step 6 added: `ssh-keygen -R <farbox's name or address>`.
25. On homebox: `rm ~/.ssh/tc_qa_ed25519 ~/.ssh/tc_qa_ed25519.pub`
    (step 3), then `rm -r ~/tc-qa-home` (step 1 and the home mailbox).
26. If you ran the way back: on homebox, delete the line ending
    `tc-qa-far-b` from `~/.ssh/authorized_keys` (step 20); on farbox,
    delete the `Host homebox-tc` block from `~/.ssh/config`, run
    `ssh-keygen -R <homebox's name or address>`, and `rm
    ~/.ssh/tc_qa_back_ed25519 ~/.ssh/tc_qa_back_ed25519.pub` (steps 19
    and 21).
27. Record what you saw in `qa/results/` (D4), with every machine name,
    alias, address and user name replaced by the made-up ones above.
