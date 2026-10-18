# READTIME-1: where tc read records when a message was read

Model:  Claude Opus 5.5 (the TheConnection architect session), 2026-10-17
Status: unreviewed
Pause:  settled by a2 for the owner, 2026-10-17: as designed, plus the message number

## The ruling

a2 (#1615): yes, as designed. One addition: each line's fields stay
stable, since DASH will read this file, and each line carries the
message's number too. So a line is
`{"name": "000042-from-ann.md", "number": 42, "read": "2026-10-17T19:52:01-05:00"}`:
`number` is the number in the name the message had in its inbox
(`MESSAGE_NAME_PATTERN`), and null for a name that does not match it.
The three keys are a contract: a later change adds keys, never renames
or drops one.

## The ask

Donald, through a2 (#1609): a message records when it was sent (its
header line and its file's time) but not when it was read. Record the
read time, with its offset, durably, without changing the message's
header or body bytes. `tc log` shows sent and read times. `tc peek` marks
nothing read.

## The design (recommended)

1. **One record per inbox, in its history.** `mail/to-<name>/read/.read-times`,
   an append-only file of JSON lines, one per message moved:
   `{"name": "000042-from-ann.md", "read": "2026-10-17T19:52:01-05:00"}`.
   The name does not end in `.md`, so no listing of messages counts it
   (`message_files` picks by `MESSAGE_SUFFIX`). JSON escapes any name, so
   a by-hand name a member planted cannot break a line.
2. **Written by `tc read`, under the inbox lock, after the moves.** One
   `write` of every moved name's line with the one time `now_iso()` gives,
   then `fsync`. After the moves, so a rename that failed never gets a
   read time. A read killed between its last move and the write leaves
   those messages in `read/` with no read time: `tc log` says so. Never
   the other way round.
3. **Only the inbox's owner records** (the user who owns `read/`). In a
   private mailbox that is always the reader. In a shared mailbox (C4) a
   member's `tc read` of another name moves only that member's own
   messages, which is not the recipient picking them up, so it records
   nothing for them and says one line why. This is D36's rule ("only a
   name's owner listens for it") applied to reading.
4. **A file only its owner writes**, `0640`, the umask applied, like the
   wait exit record. It is opened by name in `read/`'s descriptor with
   `O_APPEND | O_CREAT | O_NOFOLLOW`, then fstat'ed: anything at the name
   that is not this user's own regular one-name file (a link, a FIFO, a
   folder, another member's file, a hard link) is moved aside with words,
   as `move_record_aside` does for `.wait.exit`, and the open tried once
   more. Under sticky `3770`, `read/`'s owner may move it.
5. **A failed record is words, not a failed read.** Disk full, a refused
   open, a plant that will not move: `tc read` prints its mail as usual,
   adds one line on stderr (`tc read: read time not recorded for <n>
   messages (<why>)`) and keeps its exit code. The mail was read; a
   waking session must not stop over a missing timestamp.
6. **`tc log` shows it.** After each message's header line it prints one
   line: `read <time>`, or `unread` for a message still in its inbox, or
   `read, time not recorded` for one in `read/` with no line (read before
   this change, by a non-owner, or by a read killed mid-way). The record
   is read once per inbox, bounded by a named byte limit; a line that
   does not parse (a torn last line after a crash) is passed by. The
   message files are never changed.
7. **`tc peek` writes nothing**, as now; a test pins it.
8. **`tc wait` and the board are unchanged.** The board's feed reads
   names only (C5) and `.read-times` is not a message name. DASH (a later
   lane, planned apart) may read it.

## Options set aside

- **A trailing line in the message file.** Changes the file's bytes, and
  in a shared mailbox the file is the sender's `0640` file: the reader
  cannot write it.
- **A sidecar per message** (`read/<name>.read`). Doubles the files in
  `read/`, and each one is a name a member could plant ahead.
- **The file's own times.** A rename sets ctime, but chmod and a copy
  change it too, and atime moves on every read. Not durable.

## Contract lines it adds

- C2, the paragraph on `tc read`: the read-time record, items 1 to 5.
- C4, the modes list: `0640` on `read/.read-times`, its owner's; and
  the planted-entry exception, as for `.wait.exit`.
- CLAUDE.md layout: one line for `mail/to-<name>/read/.read-times`.

## Recommendation

The design above. The lane builds it now; a change from a2 lands in the
lane before the merge ask, and the merge ask waits on this pause.
