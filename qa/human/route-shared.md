# QA: the shared mailbox, two Linux users in one group (C4, D19, D20, D21)

Model:  Claude Opus 5.5 (the SHARED lane agent), 2026-10-14; the D21
        steps (6, 7, 13 to 15, and 22) added by the SHARED fixer, Claude
        Opus 5.5; step 25's words and steps 27 to 29 added in round 2 by
        the SHARED fixer, Claude Opus 5.5; steps 30 and 31, and the words
        of steps 3, 15, 28 and 29, in round 3 by the SHARED fixer, Claude
        Opus 5.5, 2026-10-15
Status: unreviewed

What this checks: two Linux users in one group share one mailbox. Each
can send, wait and read. Neither can delete, rename or rewrite the other's
unread mail (D20). Only the user who ran init can change the group, and a
send to a name nobody joined is refused even when an inbox is there
(D21). A planted link is never printed (D19). A member who sets
`mail/.seq` back or holds a lock can make the other's command fail, never
lose a message or hang it, and init never shares a ROOT the group may
write (round 2). A file a member plants under a read message's name
never replaces it, and init refuses a ROOT a member could swap through a
folder above it (round 3, D20, D23). The tests in
`tests/test_shared.py` prove the modes, the owners and the checks tc
makes, but one user cannot prove another user's refusals. This script
does, by hand.

The names here are made up: users `ann` and `ben`, group `tcshare`,
mailbox `/srv/tc-shared`. Use your own. Every `tc` below is your own copy
of this branch's `tc`, run as `python3 /path/to/tc` or `./tc`. Real
`ssh` and real `codex` are not needed. Record what you saw in
`qa/results/` (D4).

## Setup, once, as a user with sudo

1. Make the group and put both users in it:
   `sudo groupadd tcshare`, `sudo usermod -aG tcshare ann`,
   `sudo usermod -aG tcshare ben`.
2. Log each user out and back in (or open a fresh `su - ann` and
   `su - ben`), then run `id -nG` as each.
   - Each list includes `tcshare`. A shell started before step 1 keeps
     its old groups; if `tcshare` is missing, log in again.
3. Make a mailbox both can reach, owned by ann and not group-writable:
   `sudo mkdir /srv/tc-shared`, `sudo chown ann:ann /srv/tc-shared`,
   `sudo chmod 0755 /srv/tc-shared`.
   - Do not give it group `tcshare` with group write, sticky or not. A
     member could then rename `mail/` itself, or replace `.shared`; init
     refuses such a ROOT (step 28). ben needs search access on every
     folder from `/` down to it, which `/srv` gives.
   - Every folder above it must belong to root or ann, and must not be
     writable by its group or anyone unless it is sticky (as `/tmp`).
     `/srv` at 0755, owned by root, is fine. Init refuses any other
     (step 31), since a member could rename the mailbox away and put
     their own in its place.
4. In every terminal below: `export TC_ROOT=/srv/tc-shared`.

## ann shares the mailbox

5. As ann: `tc init --shared --group tcshare`.
   - It prints `mailbox shared with group tcshare: 4 folders and 0 files
     in group tcshare` and exits 0.
   - `ls -ld /srv/tc-shared/mail /srv/tc-shared/status
     /srv/tc-shared/cards /srv/tc-shared/outbox` shows each as
     `drwxrwsr-t`, owner `ann`, group `tcshare` (3775: setgid, sticky).
   - `ls -l /srv/tc-shared/.shared` shows `-rw-r--r--`, owner `ann`
     (0644: only ann can write it, D21).
   - `tc health`, as ann and as ben, ends with `mailbox shared with
     group tcshare`.

## Only ann can change the group (D21)

6. As ann: `tc init --shared --group tcshare` again.
   - It exits 0. `ls -l /srv/tc-shared/.shared` still shows
     `-rw-r--r--`, owner `ann`. A rerun never makes it group-writable.
   - To see a `.shared` from before D21 put right: `chmod g+w
     /srv/tc-shared/.shared`, run the same init once more, and `ls -l`
     shows `-rw-r--r--` again.
7. As ben, before ben joins, try to rewrite `.shared`. Each try is
   refused:
   - `echo ben > /srv/tc-shared/.shared`: `Permission denied`.
   - `chmod g+w /srv/tc-shared/.shared`: `Operation not permitted`.
   - `tc init --shared --group ben` (ben's own group, or any group ben is
     in other than `tcshare`): one line, `tc init: may not change
     /srv/tc-shared/.shared; the mailbox stays shared with group tcshare;
     only the user who ran init (ann) can change the group. Nothing
     changed.`, and exit 1. No `skipped` lines: init refuses before it
     looks at a folder.
   - `cat /srv/tc-shared/.shared` still prints `tcshare`, and `tc health`
     as ben still ends with `mailbox shared with group tcshare`.

## The mailbox works for both

8. As ann: `tc join ann`. As ben: `tc join ben`.
   - Each prints `joined as <name> (...)` and exits 0.
   - `ls -ld /srv/tc-shared/mail/to-ann /srv/tc-shared/mail/to-ann/read`
     shows `drwxrws--T`, owner `ann`, group `tcshare` (3770: setgid,
     sticky, nothing for other users). The same for `to-ben`, owner
     `ben`.
9. As ann, in a second terminal: `tc wait ann --timeout 300`.
10. As ben: `tc send --from ben --to ann "hello from ben"`.
    - ben sees `sent #1 to ann: /srv/tc-shared/mail/to-ann/000001-from-ben.md`.
    - ann's wait prints `MAIL: 1 unread for ann. Run: tc read ann` and
      exits 0.
    - `ls -l /srv/tc-shared/mail/to-ann/000001-from-ben.md` shows
      `-rw-r-----`, owner `ben`, group `tcshare` (0640).
11. As ann: `tc read ann`.
    - It prints the message with `hello from ben`, and the file moves to
      `mail/to-ann/read/`.
12. As ben: `tc wait ben --timeout 300` in a second terminal. As ann:
    `tc send --from ann --to ben "hello from ann"`. As ben: `tc read ben`.
    - The same as steps 9 to 11, the other way round.

## Still only ann, after ben joins (D21)

13. ben now owns an inbox, a card and, from step 10, `mail/.seq`. As ben:
    `ls -ld /srv/tc-shared/mail/to-ben` and `ls -l
    /srv/tc-shared/cards/ben.json /srv/tc-shared/mail/.seq`, and note the
    lines. Then `tc init --shared --group ben` again.
    - The same one line as in step 7, `... only the user who ran init
      (ann) can change the group. Nothing changed.`, and exit 1.
    - The same three `ls` commands print the same lines: group `tcshare`
      on each, `drwxrws--T` on `to-ben`, `-rw-r-----` on the card,
      `-rw-rw-r--` on `.seq`.
    - As ann: `tc send --from ann --to ben "after ben's init"` lands. As
      ben: `tc read ben` prints it.
14. As ann: `chmod 600 /srv/tc-shared/.shared`, so ben cannot read it.
    As ben: `tc init --shared --group tcshare`.
    - It prints one line, `tc init: /srv/tc-shared/.shared is owned by
      ann and unreadable to you; only the user who ran init (ann) can
      change the group. Nothing changed.`, and exits 1. No `skipped`
      lines.
    - The three `ls` commands from step 13 print the same lines.
    - As ann: `chmod 644 /srv/tc-shared/.shared`, to put it back.
15. As ann: `chmod g+w /srv/tc-shared/.shared`, as init left it before
    D21. As ben: `tc init --shared --group tcshare`.
    - It exits 1 with one line, `tc init: /srv/tc-shared belongs to ann
      (mode 0755), who is neither root nor you, so ann could put a ROOT of
      their own, with their own .shared, in place of /srv/tc-shared and
      change the group. Keep the mailbox under folders only root or you
      own. Nothing changed.` Since D23 (round 3), init takes a folder from
      ROOT up to `/` only from root or the user running it, so a member's
      init on ann's ROOT stops there. Steps 7, 13 and 14 still get their
      own words: those refusals come first.
    - `ls -l /srv/tc-shared/.shared` still shows `-rw-rw-r--`, owner
      `ann`: ben's init leaves ann's file as it is.
    - As ann: `tc init --shared --group tcshare`. `ls -l` now shows
      `-rw-r--r--`.

## Nobody touches another member's unread mail (D20)

16. As ann: `tc send --from ann --to ann "ann's own note, do not touch"`.
    Note the file it names, below `M`:
    `M=/srv/tc-shared/mail/to-ann/00000N-from-ann.md` (N from the
    output). It is ann's unread mail, written by ann, in ann's inbox.
17. As ben, try each of these. Each is refused, and the file is unchanged:
    - `rm $M`: `rm: cannot remove ...: Operation not permitted`.
    - `mv $M /srv/tc-shared/mail/to-ann/renamed.md`: `Operation not
      permitted`.
    - `mv $M /srv/tc-shared/mail/to-ann/read/`: `Operation not permitted`.
    - `echo tampered > $M` and `echo tampered >> $M`: `Permission
      denied`.
    - `chmod g+w $M`: `Operation not permitted`.
    - `echo fake > /srv/tc-shared/mail/to-ann/fake.md` works (a member may
      put a new file in an inbox: that is how a send lands). Then
      `mv /srv/tc-shared/mail/to-ann/fake.md $M`: `Operation not
      permitted`. Then `rm /srv/tc-shared/mail/to-ann/fake.md`, which
      works, since ben owns it.
    - `mv /srv/tc-shared/mail/to-ann /srv/tc-shared/mail/to-gone`:
      `Operation not permitted` (the sticky `mail/`; ann owns `to-ann`).
18. As ben: `tc read ann`.
    - It prints `tc read: <M> not moved to read/ (Operation not
      permitted); left unread` on stderr, nothing on stdout, and exits 1,
      with no traceback. `$M` is still in `mail/to-ann/`.
19. As ben: `tc status ann "hijacked"`, after ann has run
    `tc status ann "busy"` once.
    - It exits 1 with `tc: /srv/tc-shared/status/ann.md belongs to ann,
      and this user may not open it (Permission denied); under a shared
      mailbox only its owner writes it; nothing written through it`.
      `tc status` still shows ann's `busy`.
20. As ben: `tc join ann`.
    - It exits 1 with `tc join: /srv/tc-shared/cards/ann.json belongs to
      ann; under a shared mailbox only its owner can replace it. No card
      written; pick another name, or ask ann.` No `.tmp` is left in
      `cards/`.
21. As ben: `tc send --from ben --to nobody "hi"`.
    - It exits 1 with `tc send: nobody has joined as nobody on this
      shared mailbox`, and `ls /srv/tc-shared/mail` shows no `to-nobody`.
22. As ben: `mkdir /srv/tc-shared/mail/to-ghost`, an inbox nobody joined
    (any member may make a folder in `mail/`). As ann: `cat
    /srv/tc-shared/mail/.seq`, then `tc send --from ann --to ghost "hi"`,
    then `cat /srv/tc-shared/mail/.seq` again.
    - The send exits 1 with exactly `tc send: nobody has joined as ghost
      on this shared mailbox` (D21). Without a card, an inbox never takes
      mail, so ann's words never land in a folder ben owns.
    - `ls -A /srv/tc-shared/mail/to-ghost` prints nothing, and both
      `cat`s print the same number.
    - As ben: `rmdir /srv/tc-shared/mail/to-ghost`. It works: ben owns
      it.
23. As ann: `tc read ann`.
    - It prints `ann's own note, do not touch`, unchanged.

What D20 does not stop, by design: a member may still change or remove a
message that member wrote, and the recipient may remove anything in its
own inbox. The files every member must write stay group-writable: as
ben, `echo 999 > /srv/tc-shared/mail/.seq` works, and the next send is
numbered 1000. The worst a member can do through them is make a send
fail or ring once more, never read, lose or alter mail.

## A planted link is never printed (D19)

24. As ben: `ln -s /home/ann/.profile
    /srv/tc-shared/mail/to-ann/000099-from-ben.md` (any file only ann can
    read will do).
25. As ann: `tc peek ann`, then `tc read ann`, then `tc log`. None of
    them prints a line of the linked file, and each exits 1 after
    printing the rest.
    - `tc peek ann` prints `0 unread for ann` on stdout, and on stderr
      `tc peek: /srv/tc-shared/mail/to-ann/000099-from-ben.md not shown
      (it is a symlink, which tc never follows)`.
    - `tc read ann` prints `no unread mail for ann` on stdout (nothing
      else is waiting), and on stderr `tc read:
      /srv/tc-shared/mail/to-ann/000099-from-ben.md not shown and left in
      place (it is a symlink, which tc never follows)`. The link stays in
      `mail/to-ann/`.
    - `tc log` prints the history on stdout, and on stderr `tc log:
      /srv/tc-shared/mail/to-ann/000099-from-ben.md not shown (it is a
      symlink, which tc never follows)`.
26. As ann: `rm /srv/tc-shared/mail/to-ann/000099-from-ben.md`.
    - It works: ann owns her inbox. ben could also remove his own link.

## A member's worst is a failed command (D20, D21, round 2)

27. A member sets `mail/.seq` back, and no unread mail is lost. As ann:
    `tc send --from ann --to ben "kept one"`. Call the number it prints
    N. As ben: `echo <N minus 1> > /srv/tc-shared/mail/.seq`, so the next
    number names ann's unread message. As ann: `tc send --from ann --to
    ben "after the set back"`.
    - It exits 0 and prints `sent #<N plus 1> to ben: ...`: the number
      past the one already taken, never N again.
    - `ls -l /srv/tc-shared/mail/to-ben` shows both messages from ann.
    - As ben: `tc read ben` prints `kept one` and `after the set back`,
      each whole.
28. Init refuses a ROOT the group may write, sticky or not. As ann:
    `chmod g+w /srv/tc-shared`, then `tc init --shared --group tcshare`.
    - It exits 1 with one line, `tc init: /srv/tc-shared is 0775: its
      group or anyone may write it, so any member could rename .shared or
      mail/ in it, or make them before init, and change the group. Its
      owner, ann, runs chmod g-w,o-w /srv/tc-shared first. Nothing
      changed.`
    - As ann: `chmod 1775 /srv/tc-shared` (sticky, still group-writable),
      then the same init. The same line, with `1775`, and exit 1.
    - As ann: `chmod 0755 /srv/tc-shared`, then the same init again.
      It exits 0.
29. A member holds a lock, and the other's command fails in about 3
    seconds instead of hanging, with exit 10 (busy: nothing written, run
    it again; D23).
    - As ben: `( flock 9 && sleep 60 ) 9< /srv/tc-shared/mail/.seq &`.
      The shell opens the counter read-only, which the group may, and
      holds its lock for a minute.
    - As ann, at once: `cat /srv/tc-shared/mail/.seq`, then `time tc
      send --from ann --to ben "while ben holds the counter"; echo $?`.
      After about 3 seconds it prints `tc: another process is holding
      /srv/tc-shared/mail/.seq's lock; try again`, and `echo` prints `10`.
      `ls /srv/tc-shared/mail/to-ben` shows no new message, and a second
      `cat` prints the same number.
    - As ben: `kill %1`. As ann: the same send now exits 0.
    - As ben: `( flock 9 && sleep 60 ) 9< /srv/tc-shared/mail/.box-ann.lock
      &`. As ann: `time tc read ann; echo $?`. After about 3 seconds it
      prints `tc: another process is holding ann's lock; try again`,
      `echo` prints `10`, and it moves nothing. As ben: `kill %1`.

## Nothing planted replaces read mail, and nobody swaps ROOT (round 3)

30. ben plants a file under the name of one of ann's read messages, and
    ann's read keeps both (D20).
    - As ann: `ls /srv/tc-shared/mail/to-ann/read/`. Call `R` the name of
      ann's own note from step 16, now read (step 23), for example
      `00000N-from-ann.md`. Run `cat /srv/tc-shared/mail/to-ann/read/R`
      and note what it prints.
    - As ben: `echo "not written by tc" > /srv/tc-shared/mail/to-ann/R`.
      It works: a member may put a new file in an inbox.
    - As ann: `tc read ann`. It prints `tc read: a second R arrived after
      the first was read. tc never reuses a number, so someone wrote this
      one by hand. The first stays in read/, unchanged; this one is kept
      as /srv/tc-shared/mail/to-ann/read/by-hand-1-R:`, then `not written
      by tc`, and exits 0.
    - `cat /srv/tc-shared/mail/to-ann/read/R` prints what it did before.
      `ls /srv/tc-shared/mail/to-ann/read/` shows both `R` and
      `by-hand-1-R`. `ls /srv/tc-shared/mail/to-ann` no longer shows `R`,
      so ann's `tc wait ann` never wakes for it again.
31. Init refuses a ROOT under a folder the group may write (D23).
    - As a user with sudo: `sudo mkdir /srv/team`, `sudo chgrp tcshare
      /srv/team`, `sudo chmod 2775 /srv/team`: a team folder every member
      may write.
    - As ann: `mkdir /srv/team/tc`, then `TC_ROOT=/srv/team/tc tc init
      --shared --group tcshare`. It exits 1 with one line, `tc init:
      /srv/team, on the way to /srv/team/tc, is 2775 and owned by root:
      its group or anyone may write it and it is not sticky, so any
      member could rename the entry in it that leads to /srv/team/tc and
      put their own, with their own .shared, in its place. Its owner,
      root, runs chmod g-w,o-w /srv/team first, or the mailbox moves.
      Nothing changed.` `ls -A /srv/team/tc` prints nothing.
    - As a user with sudo: `sudo chmod 3775 /srv/team` (sticky, as
      `/tmp`). As ann: the same init. It exits 0: in a sticky folder only
      an entry's owner may rename it.

## Afterward

32. The mailbox, `/srv/team` and the group stay until you remove them
    yourself.
