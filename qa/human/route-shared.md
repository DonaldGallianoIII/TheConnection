# QA: the shared mailbox, two Linux users in one group (C4, D19, D20, D21)

Model:  Claude Opus 5.5 (the SHARED lane agent), 2026-10-14; the D21
        steps (6, 7 and 19) added by the SHARED fixer, Claude Opus 5.5
Status: unreviewed

What this checks: two Linux users in one group share one mailbox. Each
can send, wait and read. Neither can delete, rename or rewrite the other's
unread mail (D20). Only the user who ran init can change the group, and a
send to a name nobody joined is refused even when an inbox is there
(D21). A planted link is never printed (D19). The tests in
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
   - Do not give it group `tcshare` with group write. A member could then
     rename `mail/` itself, or replace `.shared`. ben needs search access
     on every folder from `/` down to it, which `/srv` gives.
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
7. As ben, before ben joins, try to rewrite `.shared`. Each try is
   refused:
   - `echo ben > /srv/tc-shared/.shared`: `Permission denied`.
   - `chmod g+w /srv/tc-shared/.shared`: `Operation not permitted`.
   - `tc init --shared --group ben` (ben's own group, or any group ben is
     in other than `tcshare`): one line per top folder, `tc init: skipped
     /srv/tc-shared/mail: Operation not permitted (owned by ann)` and the
     same for `status`, `cards` and `outbox`, then `tc init: could not
     write /srv/tc-shared/.shared (Permission denied); the mailbox stays
     shared with group tcshare; only the user who ran init (ann) can
     change the group. 0 folders and 0 files are in group ben.` It exits
     1.
   - `cat /srv/tc-shared/.shared` still prints `tcshare`, and `tc health`
     as ben still ends with `mailbox shared with group tcshare`.
   - Why before the join: init moves what the running user owns into the
     new group before it tries `.shared`. After ben joins, the same
     command would move ben's inbox and card into group `ben` first, and
     ann could no longer send to ben until ben runs init again with
     `tcshare`.

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

## Nobody touches another member's unread mail (D20)

13. As ann: `tc send --from ann --to ann "ann's own note, do not touch"`.
    Note the file it names, below `M`:
    `M=/srv/tc-shared/mail/to-ann/00000N-from-ann.md` (N from the
    output). It is ann's unread mail, written by ann, in ann's inbox.
14. As ben, try each of these. Each is refused, and the file is unchanged:
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
15. As ben: `tc read ann`.
    - It prints `tc read: <M> not moved to read/ (Operation not
      permitted); left unread` on stderr, nothing on stdout, and exits 1,
      with no traceback. `$M` is still in `mail/to-ann/`.
16. As ben: `tc status ann "hijacked"`, after ann has run
    `tc status ann "busy"` once.
    - It exits 1 with `tc: /srv/tc-shared/status/ann.md belongs to ann,
      and this user may not open it (Permission denied); under a shared
      mailbox only its owner writes it; nothing written through it`.
      `tc status` still shows ann's `busy`.
17. As ben: `tc join ann`.
    - It exits 1 with `tc join: /srv/tc-shared/cards/ann.json belongs to
      ann; under a shared mailbox only its owner can replace it. No card
      written; pick another name, or ask ann.` No `.tmp` is left in
      `cards/`.
18. As ben: `tc send --from ben --to nobody "hi"`.
    - It exits 1 with `tc send: nobody has joined as nobody on this
      shared mailbox`, and `ls /srv/tc-shared/mail` shows no `to-nobody`.
19. As ben: `mkdir /srv/tc-shared/mail/to-ghost`, an inbox nobody joined
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
20. As ann: `tc read ann`.
    - It prints `ann's own note, do not touch`, unchanged.

What D20 does not stop, by design: a member may still change or remove a
message that member wrote, and the recipient may remove anything in its
own inbox. The files every member must write stay group-writable: as
ben, `echo 999 > /srv/tc-shared/mail/.seq` works, and the next send is
numbered 1000. The worst a member can do through them is make a send
fail or ring once more, never read, lose or alter mail.

## A planted link is never printed (D19)

21. As ben: `ln -s /home/ann/.profile
    /srv/tc-shared/mail/to-ann/000099-from-ben.md` (any file only ann can
    read will do).
22. As ann: `tc peek ann`, then `tc read ann`, then `tc log`.
    - None of them prints a line of the linked file. Each names
      `000099-from-ben.md not shown (it is a symlink, which tc never
      follows)` on stderr and exits 1 after printing the rest. `tc read`
      says `left in place` and leaves the link in `mail/to-ann/`.
23. As ann: `rm /srv/tc-shared/mail/to-ann/000099-from-ben.md`.
    - It works: ann owns her inbox. ben could also remove his own link.

## Afterward

24. The mailbox and the group stay until you remove them yourself.
