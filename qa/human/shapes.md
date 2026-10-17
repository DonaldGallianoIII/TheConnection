# QA: the three shapes on the live board (D7)

Model:  Claude Opus 5.5 (the DOCS lane agent), 2026-10-17
Status: unreviewed. The roles below were checked once by the DOCS lane
        agent from the board's feed (`/feed`, read with the token) for
        the same commands; nobody has looked at the drawn page yet.

What this checks: no hub is assumed (D7). Three real shapes, each built
by hand from mail alone, and the live board draws each one with the
right roles: one relay with many workers, a relay whose worker is a
relay for others, and two orchestrators side by side who mail each
other. With no hints the board marks what it guessed as `· inferred`;
with `--reports-to` on the cards it does not. The board's one known
limit with no hints shows in shape 2, and `--reports-to` fixes it (C5,
"Roles and levels").

No session is needed: the mail is sent by hand, from terminals. Real
`ssh` and real `codex` are not needed. Run everything from the repo
root, in a plain terminal (not one inside a Claude Code session, whose
`CLAUDECODE=1` makes every card a `claude` card, so cards on one account
grow `native with ...` badges). Run `unset CLAUDECODE CLAUDE_CONFIG_DIR`
there first: with `CLAUDE_CONFIG_DIR` set, step 6's cards read that
folder's base name, not `account unknown`. Each shape gets its own
throwaway mailbox. Names here are made up.

Each box's title is its name and its role: `a · orchestrator`, `b ·
worker`, `x · peer`, with `· inferred` when the role came from mail
rather than a card. Look for those words, never a color.

## Shape 1: one relay, many workers

1. In terminal 1:
   ```
   export TC_ROOT=$(mktemp -d)
   for w in b c d; do ./tc send --from a --to $w "task for $w"; ./tc send --from $w --to a "done, $w"; done
   ```
   - Six `sent #N to ...` lines, each with a `new inbox: nobody has
     joined as ...` warning the first time a name gets mail.
2. In terminal 1: `python3 board/serve.py`, and open the URL it prints.
   If 8780 is taken, add `--port 8781`.
   - The list of roots under the title reads `1 orchestrator: a`.
   - One tree: `a · orchestrator · inferred` on top, and under it `b ·
     worker · inferred`, `c · worker · inferred` and `d · worker ·
     inferred`.
   - A mail wire joins a to each worker. None joins two workers.
   - Pass: those four titles, in that tree. Fail: a worker on top, a
     worker without `· inferred`, or two trees.
3. Stop the server with Ctrl+C.

## Shape 2: a relay whose worker is a relay for others

4. In terminal 1:
   ```
   export TC_ROOT=$(mktemp -d)
   ./tc send --from a --to b "plan"; ./tc send --from b --to a "ok"
   for w in c d; do ./tc send --from b --to $w "part for $w"; ./tc send --from $w --to b "done, $w"; done
   ```
5. Start the board as in step 2 and open its URL.
   - The known limit, with no hints: the roots list reads `1
     orchestrator: b`. `b · orchestrator · inferred` is on top, and
     under it `a · worker · inferred`, `c · worker · inferred` and `d ·
     worker · inferred`. a's only partner is b, and b has three, so the
     board guesses a works for b. This is the case the README's Limits
     names.
6. Stop the server. Now give the cards the truth. In terminal 1:
   ```
   ./tc join a
   ./tc join b --reports-to a
   ./tc join c --reports-to b
   ./tc join d --reports-to b
   ```
   - Each prints `joined as <name> (other, account unknown, route local)`,
     and b, c and d add `, reports to <relay>`.
7. Start the board again and open its URL.
   - The roots list reads `1 orchestrator: a`.
   - Three levels: `a · orchestrator` on top, `b · orchestrator` under
     it, and `c · worker` and `d · worker` under b. No title says
     `inferred`: every role now comes from a card.
   - A thin line runs from each of b, c and d up to the one it reports
     to, beside the mail wire, never on it.
   - Pass: a on top, b one level down and still an orchestrator, no
     `inferred`. Fail: b on top, or any `inferred` left.
8. Stop the server.

## Shape 3: two orchestrators side by side

9. In terminal 1:
   ```
   export TC_ROOT=$(mktemp -d)
   echo $TC_ROOT
   for p in "o1 w1" "o1 w2" "o2 w3" "o2 w4" "o1 o2"; do set -- $p; ./tc send --from $1 --to $2 "hi"; ./tc send --from $2 --to $1 "back"; done
   ```
10. Start the board and open its URL.
    - The roots list reads `2 orchestrators: o1, o2`.
    - Two trees side by side: `o1 · orchestrator · inferred` over `w1 ·
      worker · inferred` and `w2 · worker · inferred`, and `o2 ·
      orchestrator · inferred` over `w3 · worker · inferred` and `w4 ·
      worker · inferred`.
    - A mail wire joins o1 and o2 across the two trees.
    - Pass: two trees, each orchestrator over its own two workers, and
      the wire between o1 and o2. Fail: one orchestrator drawn as the
      other's worker, or no wire between them.
11. Send one more message and watch it move. Terminal 1 is busy running
    the board, so open terminal 2 in the repo root and run `export
    TC_ROOT=<the path step 9 echoed>`, then `./tc send --from o1 --to o2
    "one more"`.
    - Within 3 s the wire from o1 to o2 shows moving dashes, an arrow at
      o2 and a label, and o1's box reads `✎ writing` for about 10 s, then
      `○ idle` again.

## Every shape in grayscale

12. With shape 3's board still open, add `?gray=1` to the URL before the
    `#`, and reload.
    - Every title, role word, state glyph and word, and the roots list
      read the same as in color. No two roles differ only by color.
13. Stop the server.

## Afterward

14. Run `unset TC_ROOT` in both terminals. The three throwaway
    mailboxes are under the system temp folder.
15. Record what you saw in `qa/results/shapes.md`.
