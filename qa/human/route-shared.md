# QA: the shared mailbox, two Linux users in one group (C4, D19, D20, D21)

Model:  Claude Opus 5.5 (the SHARED lane agent), 2026-10-14; the D21
        steps (6, 7, 13 to 15, and 22) added by the SHARED fixer, Claude
        Opus 5.5; step 25's words and steps 27 to 29 added in round 2 by
        the SHARED fixer, Claude Opus 5.5; steps 30 and 31, and the words
        of steps 3, 15, 28 and 29, in round 3 by the SHARED fixer, Claude
        Opus 5.5, 2026-10-15; steps 15, 30 and 31 changed in round 4 by
        the SHARED fixer, Claude Opus 5.5, 2026-10-15; steps 15 and 31,
        and the paragraph after step 23, changed in round 5 by the
        SHARED fixer, Claude Opus 5.5, 2026-10-15; steps 15 and 31
        changed, and step 32 added, in round 6 by the SHARED fixer,
        Claude Opus 5.5, 2026-10-15; the lead paragraph changed, and
        step 33 added, in round 7 by the SHARED fixer, Claude Opus 5.5,
        2026-10-15; the lead paragraph changed in round 8 by the SHARED
        fixer, Claude Opus 5.5, 2026-10-15
Status: unreviewed

What this checks: two Linux users in one group share one mailbox. Each
can send, wait and read. Neither can delete, rename or rewrite the other's
unread mail (D20). Only the user who ran init can change the group, and a
send to a name nobody joined is refused even when an inbox is there
(D21). A planted link is never printed (D19). A member who sets
`mail/.seq` back or holds a lock can make the other's command fail, never
lose a message or hang it, and init never shares a ROOT the group may
write (round 2). A file a member plants under a message's name, in the
inbox or in read/, never replaces it, and init refuses a ROOT a member
could swap through a folder above it (round 3, D20, D23). tc read calls
neither of two such files forged, and a planted name of any length
wakes `tc wait` at most once (round 4). A member's init on the init
user's ROOT is refused with words that name who ran init and charge no
one, and a member who makes ROOT first stops the init user's init
(round 5, D28). That refused init then fixes the member's own entries
itself, through a no-follow open (round 6, D29). Every folder from ROOT
down is pinned by identity: init opens ROOT once, right after its walk,
and goes on only when it is the folder the walk looked at (on a
member's rerun, the init user's); then it opens each of the four, each
folder below them and each entry by its name in the folder above it,
never by its path, and changes an entry only when it is the one the
walk found. So a link or another folder swapped in for ROOT, a folder
above it, a folder on the way, or an entry, while init runs, never
leads either walk out of the mailbox (rounds 7 and 8). ROOT's owner and
every folder above it are judged by the walk, by path, before that (step
31). A file with a second name (a hard link) is never changed, and a
nest of folders too deep is named and left (round 8). The only command
line tc prints is D23's `chmod g-w,o-w`, to the owner of ROOT or of a
folder above it (steps 28 and 31); for an entry under the four it
prints none. The tests in
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
    - It exits 1 with two lines. The first: `tc init: /srv/tc-shared and
      its .shared belong to ann, who ran init on this mailbox, so only
      ann runs init on it. tc fixes the entries you own under it itself,
      and changes nothing else.` The second: `tc init: no entry you own
      under it needs a fix. Nothing changed.` The walk from ROOT up to
      `/` (D23) takes a folder only from root or the user running init.
      The owner of `.shared` gets no trust (round 5, D28): whoever makes
      ROOT can make the `.shared` in it. The words name ann and charge
      no one. Steps 7, 13 and 14 still get their own words: those
      refusals come first.
    - `ls -l /srv/tc-shared/.shared` still shows `-rw-rw-r--`, owner
      `ann`: ben's init never touches it.
    - As ben: `chmod 0644 /srv/tc-shared/cards/ben.json`, so one entry
      ben owns is not right. Run `ls -l /srv/tc-shared/cards/ann.json`
      and `ls -ld /srv/tc-shared/mail/to-ann` and note the lines. The
      same init again. It exits 1 with three lines: the first as above,
      then `tc init: fixed /srv/tc-shared/cards/ben.json: group tcshare,
      mode 0640`, then `tc init: 1 fixed and 0 skipped, each named
      above. Nothing else changed.` No `chgrp` or `chmod` line is
      printed (round 6, D29): tc made the change itself, through the
      open file, never by its name.
    - `ls -l /srv/tc-shared/cards/ben.json` shows `-rw-r-----`, group
      `tcshare`. ann's card and inbox print the lines you noted. The
      same init once more ends `tc init: no entry you own under it needs
      a fix. Nothing changed.`, exit 1.
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
fail, or make a codex ring come once more or once fewer (a member who
holds the ring marker through a failed ring leaves it clear, and that
send warns that a later send may not ring), never read, lose or alter
mail.

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

30. ben plants a file under the name of one of ann's messages, in her
    inbox or in her read/, and ann's read keeps both and calls neither
    forged (D20, round 4). The group may make names in both folders.
    - As ann: `ls /srv/tc-shared/mail/to-ann/read/`. Call `R` the name of
      ann's own note from step 16, now read (step 23), for example
      `00000N-from-ann.md`. Run `cat /srv/tc-shared/mail/to-ann/read/R`
      and note what it prints.
    - As ben: `echo "not written by tc" > /srv/tc-shared/mail/to-ann/R`.
      It works: a member may put a new file in an inbox.
    - As ann: `tc read ann`. It prints `tc read: two files had the name
      R, one in read/ and one in the inbox. tc never reuses a number, so
      one of them was not written by tc. Both are kept:
      /srv/tc-shared/mail/to-ann/read/R (owned by ann), unchanged, and
      /srv/tc-shared/mail/to-ann/read/by-hand-1-R (owned by ben), from
      the inbox, shown below:`, then `not written by tc`, and exits 0.
    - `cat /srv/tc-shared/mail/to-ann/read/R` prints what it did before.
      `ls /srv/tc-shared/mail/to-ann/read/` shows both `R` and
      `by-hand-1-R`. `ls /srv/tc-shared/mail/to-ann` no longer shows `R`,
      so ann's `tc wait ann` never wakes for it again.
    - The other order. As ann: `tc send --from ann --to ann "the real
      one"`, and call `S` the file name it prints. Before ann reads, as
      ben: `echo "planted first" > /srv/tc-shared/mail/to-ann/read/S`.
      As ann: `tc read ann`. It prints the same words with `S`, now
      `read/S (owned by ben)` and `read/by-hand-1-S (owned by ann)`,
      then `the real one`, and exits 0. Neither line calls ann's own
      message forged. `cat /srv/tc-shared/mail/to-ann/read/S` prints
      `planted first`, and `cat
      /srv/tc-shared/mail/to-ann/read/by-hand-1-S` prints ann's message.
    - A long name. As ben: `n=$(python3 -c "print('x' * 247 + '.md')")`
      (a 250-byte name), then `echo kept > /srv/tc-shared/mail/to-ann/read/$n`
      and `echo planted > /srv/tc-shared/mail/to-ann/$n`. As ann: `tc
      wait ann --timeout 5; echo $?` prints `MAIL: 1 unread for ann. Run:
      tc read ann` and `0`. `tc read ann; echo $?` prints the same words
      as above, then `planted`, and `0`. `ls
      /srv/tc-shared/mail/to-ann/read/ | grep by-hand-1-x` shows one name
      ending in `.md`, cut to fit the filesystem's 255-byte limit. `tc
      wait ann --timeout 5; echo $?` then prints `TIMEOUT: no mail for
      ann in 5s. Re-arm: tc wait ann` and `2`: the planted name woke it
      once, never again.
31. Init refuses a ROOT under a folder the group may write (D23).
    - As a user with sudo: `sudo mkdir /srv/team`, `sudo chgrp tcshare
      /srv/team`, `sudo chmod 2775 /srv/team`: a team folder every member
      may write.
    - As ann: `mkdir -m 0755 /srv/team/tc`. The mode matters: a bare
      `mkdir` under a umask of 002 (usual where each user has a group of
      their own) makes ROOT 2775 inside the setgid `/srv/team`, and init
      then refuses ROOT itself first, with step 28's words. With `-m
      0755`, `ls -ld /srv/team/tc` shows `drwxr-sr-x` (2755, not
      writable by the group).
    - As ann: `TC_ROOT=/srv/team/tc tc init
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
    - A member who gets there first (round 5, D28). As ben: `mkdir -m
      0755 /srv/team/tc2`, then `TC_ROOT=/srv/team/tc2 tc init --shared
      --group tcshare`. It exits 0: this mailbox is ben's. Run `ls -A
      /srv/team/tc2` and note what it prints. As ann: the same init,
      `TC_ROOT=/srv/team/tc2`. It exits 1 with two lines, `tc init:
      /srv/team/tc2 and its .shared belong to ben, who ran init on this
      mailbox, so only ben runs init on it. tc fixes the entries you own
      under it itself, and changes nothing else.` and `tc init: no entry
      you own under it needs a fix. Nothing changed.` `ls -A
      /srv/team/tc2` prints the same as before. Before round 5 this init
      exited 0 with the line of step 5, on a mailbox whose group only ben
      can change.

## A swapped link never leads init out of the mailbox (round 6, D29)

32. A recipient swaps a link in for a member's own message, and the
    member's init leaves the folder it points at alone. Here ann is the
    recipient who swaps: she owns her `read/`, and under sticky the
    folder's owner may rename anything in it. Any recipient of a
    member's mail can do the same. The message is ben's from step 10,
    `000001-from-ben.md`, in ann's `read/` since step 11 and still
    owned by ben.
    - As ben, first: `tc init --shared --group tcshare` once. Step 30
      left files ben made by hand in ann's `read/`, at the mode ben's
      shell gave them; this run fixes any that are not right (a `tc
      init: fixed` line each) and exits 1, so the run below shows only
      this step's two entries.
    - As ben: `mkdir -m 0700 ~/tc-qa-folder`, then `ls -ld
      ~/tc-qa-folder`, and note the line. Then `chmod 0664
      /srv/tc-shared/mail/to-ann/read/000001-from-ben.md`, as a send
      before D20 left a message, so ben's init has it to fix.
    - As ann: `mv /srv/tc-shared/mail/to-ann/read/000001-from-ben.md
      /srv/tc-shared/mail/to-ann/read/aside`, then `ln -s ~ben/tc-qa-folder
      /srv/tc-shared/mail/to-ann/read/000001-from-ben.md`. The message's
      name now holds a link to ben's folder.
    - As ben: `tc init --shared --group tcshare`. It exits 1. The first
      line is step 15's. Then, in either order, `tc init: skipped
      /srv/tc-shared/mail/to-ann/read/000001-from-ben.md: a symlink,
      which tc never follows` and `tc init: fixed
      /srv/tc-shared/mail/to-ann/read/aside: group tcshare, mode 0640`
      (the message, still ben's under its new name). The last line:
      `tc init: 1 fixed and 1 skipped, each named above. Nothing else
      changed.` No `chgrp` or `chmod` line is printed.
    - As ben: `ls -ld ~/tc-qa-folder` prints the line you noted, mode
      and group unchanged. Round 5 printed a `chgrp` and a `chmod` line
      for the message instead, and pasting them after ann's swap changed
      this folder.
    - Put it back. As ann: `rm
      /srv/tc-shared/mail/to-ann/read/000001-from-ben.md`, then `mv
      /srv/tc-shared/mail/to-ann/read/aside
      /srv/tc-shared/mail/to-ann/read/000001-from-ben.md`. As ben: `rmdir
      ~/tc-qa-folder`.

## A folder swapped on the way never leads init out of the mailbox (round 7)

33. A recipient swaps a whole folder on the way, not one entry, for a
    link to a folder of the member whose init is about to walk it. Here
    ann swaps her own `read/` (she owns it) for a link to a folder of
    ben's, while ben's init runs. Before round 7 the walk opened each
    folder by its path, so a swap made after the walk listed `to-ann/`
    and before it entered `read/` led ben's init into ben's own folder,
    which it then made group-shared. By hand the swap lands before ben's
    walk reaches `read/` or after it; the swap inside that gap is the
    tests' job (`test_a_folder_swapped_for_a_link_on_the_way_never_leads_a_members_rerun_outside`
    and `..._the_init_users_own_init_outside` in `tests/test_shared.py`).
    A sleep in a second terminal is enough to show the words.
    - As ben: `mkdir -m 0700 ~/tc-qa-folder2 ~/tc-qa-folder2/sub`, then
      `echo notes > ~/tc-qa-folder2/notes` and `chmod 0600
      ~/tc-qa-folder2/notes`. Run `ls -ld ~/tc-qa-folder2
      ~/tc-qa-folder2/sub` and `ls -l ~/tc-qa-folder2/notes`, and note
      the three lines.
    - As ann, in a second terminal, arm the swap: `sleep 5; mv
      /srv/tc-shared/mail/to-ann/read /srv/tc-shared/mail/to-ann/read-aside;
      ln -s ~ben/tc-qa-folder2 /srv/tc-shared/mail/to-ann/read`.
    - As ben, at once: `tc init --shared --group tcshare`. This run comes
      before the swap: step 15's first line, then `tc init: no entry you
      own under it needs a fix. Nothing changed.`, exit 1.
    - When ann's terminal returns, as ben, the same init again. It exits
      1 with three lines: step 15's first line, then `tc init: skipped
      /srv/tc-shared/mail/to-ann/read: a symlink, which tc never
      follows`, then `tc init: 0 fixed and 1 skipped, each named above.
      Nothing else changed.` Had the swap landed while ben's walk was
      inside `mail/to-ann/`, the middle line would instead end
      `/srv/tc-shared/mail/to-ann/read: a folder when tc first looked,
      but by the time tc came to enter it a link or another entry had its
      name, or it was gone or would not open; tc looked at nothing under
      it`. Either line means the same: ben's init did not go in.
    - As ben: the same `ls` commands print the three lines you noted,
      each mode and group unchanged. No `chgrp` or `chmod` line is
      printed.
    - Put it back. As ann: `rm /srv/tc-shared/mail/to-ann/read` (the
      link), then `mv /srv/tc-shared/mail/to-ann/read-aside
      /srv/tc-shared/mail/to-ann/read`. As ben: `rm ~/tc-qa-folder2/notes`,
      then `rmdir ~/tc-qa-folder2/sub ~/tc-qa-folder2`.

## Afterward

34. The mailbox, `/srv/team` and the group stay until you remove them
    yourself.
