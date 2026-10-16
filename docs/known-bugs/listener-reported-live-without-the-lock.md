# listener-reported-live-without-the-lock

Model:  Claude Opus 5.5 (the GROUND lane agent), 2026-10-14
Status: unreviewed

**What:** a session reports "listening" for a mailbox name, and no process
holds that name's wait lock (`mail/to-<name>/.wait.lock` since D35; before
it, `mail/.wait-<name>.lock`). The report is a sentence about a listener,
not a check of one.

**How it showed:** on 2026-10-14 a Codex worker reported "listening" about
a listener it had started as a background job (`cmd &`). Its host had
already killed that job when the command returned, so no process held the
lock. Recorded in `docs/planning/connection-routes/phases.md` (task G2) and
`docs/planning/connection-routes/decisions.md` (D3: a listener started
inside Codex dies when its command returns). There is no artifact of the
run in the tree.

**Why it's bad:** mail for that name lands in its inbox and nothing wakes.
The sender believes the other side will act and stops checking, so the
mail sits until someone types into that session by hand.

**Prevention:** start `tc wait` only where the host keeps it alive:
Claude Code's background Bash, with a timeout. Codex gets the `codex queue`
doorbell (contract C2, decision D3), not a listener. Say "listening" only
with the pid that `tc health` names for that name. Every child a test
starts is killed in teardown by its own pid. The pid must also belong to
the name's owner: a lock another user can hold fools this very check (see
`per-owner-file-open-to-the-group`, the P3 phase review's HIGH-2).

**The check that catches it:** `tc health --json` reads `/proc/locks`. Its
`listeners` map must give the claimed pid for that name. `null` there means
nobody is listening, whatever was said. By hand:
`tc health --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["listeners"])'`.

**Detection:** a status line or report with the word "listening" and no
pid; a `tc wait` started with a trailing `&` inside a command that returns;
a test that starts `tc wait` and then sleeps a fixed time instead of
polling `/proc/locks` for its pid.

**Source:** the architect session, 2026-10-14, as recorded in `phases.md`
G2 and `decisions.md` D3.

**Times hit:** 1.

**Tier when hit:** MEDIUM. A claim the whole wake-up depends on, which
nothing checked. Nothing is lost: mail waits in the inbox until someone
reads it.

**Shared catalog:** a form of `written-claim-outlives-the-code` (the word
"listening" outlived the process it described) and of
`check-that-passes-by-not-checking` (the worker's own report was the only
check, and it cannot fail).
