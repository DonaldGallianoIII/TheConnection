# CARDS-6: small choices C0 to C2 leave open, built to a default

Model:  Claude Opus 5.5 (the CARDS lane agent), 2026-10-14
Status: unreviewed
Pause:  open. Each item is built to the recommendation and tested where
        a test says so. Any of them is a small change if overruled.

Each item: the question, what is built, the other option.

1. **Which names `tc watch` checks.** C0's list of name spots leaves out
   `watch`; the exit table says "every command that takes a name" and R1
   says "every command". Built: `tc watch <name>` is checked (its name
   becomes a lock file name). The `--names` list is not checked: it only
   names listeners to track and never touches the disk. Other option:
   check each `--names` entry too and exit 6 on a bad one.
2. **A blank `--account`.** C1 says the account is never empty. Built: a
   blank or all-space `--account`, or a `CLAUDE_CONFIG_DIR` whose base
   name is blank, counts as not given, so the chain falls through to
   `unknown`. Other option: refuse a blank `--account` with exit 1.
3. **A card file that is not a JSON object**, at send time. C2 does not
   say. Built: `tc send` refuses with words naming the file, exit 1,
   nothing written; `tc cards` prints `<file>: unreadable card`; `tc
   health` shows it with its four fields null. Other option: treat it as
   no card (route local). Rejected: an unreadable ssh card would then
   deliver here, where nobody reads it.
4. **A codex card with no `thread_id`** (C1 says it is required, but a
   hand-made card can lack it). Built: the mail lands, and the warning is
   `ring failed for <to>: its card has no thread_id; the mail is in its
   inbox`, exit 0. Other option: refuse the send, exit 1.
5. **`<n>` in the ring's message.** Built: the unread count after this
   send lands, read again (1 unless another sender raced in). Other
   option: the count before plus one.
6. **The `cards` key's shape in `tc health --json`.** R5 names the
   fields, not the shape. Built: a list of objects with exactly `name`,
   `kind`, `account`, `route`, `reports_to`, in name order. Other option:
   a map from name to the other four, like `listeners` and `mail`. The
   board does not read this key (C5).
7. **Where `header_note` goes.** C2: "appended to the message's header
   line". Built: after a comma and a space, as in
   `# #3 from x to b, <time>, via ssh gate, key x`. The gate is the
   only caller (C3).
8. **`CLAUDE_PID` that is not a number.** Built: stored as an integer
   only when it is all ASCII digits, else null. Other option: store the
   string as given.
9. **What `tc card` and `tc join` print.** C1 gives join's line. Built:
   `tc card` prints `card written: <the same words>`, and `tc cards`
   prints the same words, one card a line, with `route ssh to <target>`
   for an ssh card. `tc cards` with none prints `no cards`.
