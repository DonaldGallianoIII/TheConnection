# QA: the shared mailbox, two Linux users in one group (C4, D19, D20, D21)

Model:  Claude Opus 5.5 (the SHARED lane agent), 2026-10-14; changed in
        many fix rounds since, each listed under "Round history" at the
        end; what you need, the order with route-ssh.md, `M` set in each
        shell, the moves aside and the cleanup by the DOCS2 lane agent,
        Claude Opus 5.5, 2026-10-17
Status: unreviewed

<!-- What you need, the order and the short lead: the DOCS2 lane agent (Claude Opus 5.5), 2026-10-17. Status: unreviewed. -->
## What you need

- One machine with two Linux users, here `ann` and `ben`, and a login
  with sudo for steps 1 to 3, step 35 and the cleanup.
- A `tc` each user can run, from this branch: the same checkout, if it
  and every folder above it are readable by the group (on many systems
  a home folder is not), or each user's own clone at the same commit
  (`git rev-parse HEAD` in each prints the same). Every `tc` below is
  that copy, run as `python3 /path/to/tc` or `./tc`.
- Two terminals for each user: some steps keep a wait running in one.
- For steps 38 to 44 only: a far machine that ann's ssh key reaches
  through `tc gate` and ben's does not. `qa/human/route-ssh.md` sets it
  up; the next section says when. Those steps run real `ssh`. No step
  runs real `codex`: step 31 uses a stand-in.

The names here are made up: users `ann` and `ben`, group `tcshare`,
mailbox `/srv/tc-shared`. Use your own. Record what you saw in
`qa/results/` (D4).

## The order, with route-ssh.md

Walking both files, walk them as ann, so route-ssh.md's `you` is ann:

1. route-ssh.md, steps 1 to 22.
2. This file, steps 1 to 45, then 45a to 45c (read times, added after
   the numbers below were set, so nothing after them moved). Steps 38 to
   44 reuse route-ssh.md's alias `farbox-tc` and its far name `far-b`,
   so their setup is done.
3. This file's cleanup, steps 46 to 50.
4. route-ssh.md's cleanup, steps 23 to 28, once, last.

Walking this file alone: before step 38, as ann, do route-ssh.md's steps
2 to 7, and at the end its cleanup for what those steps made.

## What this checks

Two Linux users in one group share one mailbox. Each can send, wait and
read. Neither can delete, rename or rewrite the other's unread mail,
card, status or queued ssh mail, or hold the other's listener. Only the
user who ran init
can change the group, and a send to a name nobody joined is refused. A
planted link is never printed, a planted file never replaces a message,
and init never shares a ROOT a member could swap. Through the files
every member must write, the worst a member can do is make a command
fail, with words that name who holds the lock. The tests in
`tests/test_shared.py` prove the modes, the owners and the checks tc
makes, but one user cannot prove another user's refusals. This script
does, by hand. Which round added which check is under "Round history"
at the end.

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
     (step 35), since a member could rename the mailbox away and put
     their own in its place.
4. In every terminal below: `export TC_ROOT=/srv/tc-shared`.
   <!-- The aside folder: the DOCS2 lane agent (Claude Opus 5.5), 2026-10-17. Status: unreviewed. -->
   As ann and as ben, once: `mkdir -p -m 0700 ~/tc-qa-aside`. Nothing
   in this walk is removed: each "Put it back" moves what it clears into
   this folder, and you remove it yourself when you choose.

## ann shares the mailbox

5. As ann: `tc init --shared --group tcshare`.
   - It prints `mailbox shared with group tcshare: 5 folders and 0 files
     in group tcshare` and exits 0.
   - `ls -ld /srv/tc-shared/mail /srv/tc-shared/status
     /srv/tc-shared/cards /srv/tc-shared/outbox` shows each as
     `drwxrwsr-t`, owner `ann`, group `tcshare` (3775: setgid, sticky).
   - `ls -ld /srv/tc-shared/mail/.origins` shows the same, owner `ann`:
     init makes the folder every member's gate files origin ids under,
     so it is the init user's and never the first filer's (D36 (3), P3
     fix round 1c).
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

<!-- Steps 16 and 17: M set in each user's own shell, by the DOCS2 lane agent (Claude Opus 5.5), 2026-10-17. Status: unreviewed. -->
16. As ann: `tc send --from ann --to ann "ann's own note, do not touch"`.
    Note the file it names. It is ann's unread mail, written by ann, in
    ann's inbox. Below, `M` stands for that path, and each shell that
    uses `$M` sets it for itself: a variable set in ann's shell never
    reaches ben's.
17. As ben, first set `M` in ben's own shell, with the N from ann's
    output: `M=/srv/tc-shared/mail/to-ann/00000N-from-ann.md`. Check it:
    `ls -l $M` prints the file, owner `ann`. If it prints `ls`'s own
    listing of the current folder instead, `M` is not set in this shell.
    Then try each of these. Each is refused, and the file is unchanged:
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
      permitted`. Then `mv /srv/tc-shared/mail/to-ann/fake.md
      ~/tc-qa-aside/step17-fake.md`, which works, since ben owns it.
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
    - As ben: `mv /srv/tc-shared/mail/to-ghost
      ~/tc-qa-aside/step22-to-ghost`. It works: ben owns it.
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
26. As ann: `mv /srv/tc-shared/mail/to-ann/000099-from-ben.md
    ~/tc-qa-aside/step26-link`. `mv` moves the link itself, never the
    file it points at.
    - It works: ann owns her inbox. ben could also move his own link
      out.

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
    it again; D23), and names who holds it (D35 (3), P3 fix round 1b).
    - As ben: `python3 -c 'import fcntl, sys, time; f = open(sys.argv[1]);
      fcntl.flock(f, fcntl.LOCK_EX); time.sleep(60)'
      /srv/tc-shared/mail/.seq &`, and note the pid the shell prints. It
      opens the counter read-only, which the group may, and holds its
      lock for a minute. (A shell's `( flock 9 && sleep 60 ) 9< ...`
      holds it just as well, but the `flock` process that took it ends at
      once, and /proc/locks stops naming a lock whose taker has ended, so
      tc then says it names no holder instead.)
    - As ann, at once: `cat /srv/tc-shared/mail/.seq`, then `time tc
      send --from ann --to ben "while ben holds the counter"; echo $?`.
      After about 3 seconds it prints `tc: another process is holding
      /srv/tc-shared/mail/.seq's lock: ben (pid <that pid>); try again.
      If it stays held, ask ben to let it go, or ask the user who ran
      init (ann) to act.`, and `echo` prints `10`. `ls
      /srv/tc-shared/mail/to-ben` shows no new message, and a second
      `cat` prints the same number.
    - As ben: `kill %1`. As ann: the same send now exits 0.
    - As ben: the same one-liner on `/srv/tc-shared/mail/.box-ann.lock`,
      with `&`, and note its pid. As ann: `time tc read ann; echo $?`.
      After about 3 seconds it prints `tc: another process is holding
      ann's lock: ben (pid <that pid>); try again. If it stays held, ask
      ben to let it go, or ask the user who ran init (ann) to act.`,
      `echo` prints `10`, and it moves nothing. While ben holds it, `tc
      health` as ann has a line that starts with `held` and goes on
      `/srv/tc-shared/mail/.box-ann.lock: ann's inbox lock, held by ben
      (pid <that pid>), not by its owner ann`. As ben: `kill %1`. `tc
      health` then has no `held` line.
30. A member holds another member's wait lock, or the place it lived
    before D35, and the owner's listener still starts, holds its own lock,
    and is the one tc health names (D35 (1), P3 fix round 1b).
    - As ben: `ls -l /srv/tc-shared/mail/to-ann/.wait.lock`. It shows
      `-rw-------`, owner `ann` (0600): ann's wait made it in step 9.
    - As ben: `python3 -c 'import fcntl, sys, time; f = open(sys.argv[1]);
      fcntl.flock(f, fcntl.LOCK_EX); time.sleep(300)'
      /srv/tc-shared/mail/to-ann/.wait.lock`. It ends at once with
      `PermissionError: [Errno 13] Permission denied`: ben cannot open
      ann's lock, so he cannot hold it.
    - As ben: `python3 -c 'import fcntl, sys, time; f = open(sys.argv[1],
      "a"); fcntl.flock(f, fcntl.LOCK_EX); time.sleep(300)'
      /srv/tc-shared/mail/.wait-ann.lock &`. It runs: any member may make
      a file in `mail/`, here where ann's lock lived before round 1b, and
      hold it.
    - As ann, next: `tc wait ann --timeout 300 &`, then `echo $!`. Call
      the pid it prints A.
    - As ann: `tc health`. Its `listeners` line names `ann (pid A)`. `tc
      health --json | python3 -c 'import json, sys;
      print(json.load(sys.stdin)["listeners"]["ann"])'` prints A.
    - As ben: `tc send --from ben --to ann "are you listening"`. ann's
      wait prints `MAIL: 1 unread for ann. Run: tc read ann` and ends; as
      ann, `wait %1; echo $?` prints `0`, and `tc read ann` shows the
      message.
    - Pass: ben's open of ann's lock fails with `Permission denied`; ann's
      wait holds its own lock, with no `ALREADY LISTENING` and no exit 3;
      health names A, never the pid of ben's holder; and the mail wakes
      it. Fail: ann's wait prints `ALREADY LISTENING: another tc wait ann
      is running. Not starting a second.` and exits 3, or health names
      ben's holder as ann's listener, or the mail lands and nothing
      wakes.
    - Put it back. As ben: `kill %1`, then `mv
      /srv/tc-shared/mail/.wait-ann.lock ~/tc-qa-aside/step30-wait-ann.lock`
      (ben's own file).
31. A member rewrites a Codex member's doorbell to `clear`, and it costs
    at most one backoff, never the doorbell for good (D35 (2), D36 (1),
    P3 fix round 1b). Real codex is not needed: a stand-in named `codex`,
    first on ben's PATH, records each ring and answers as told.
    - As ann: `CODEX_THREAD_ID=qa-thread tc join annc` (a made-up thread
      id). It prints `joined as annc (codex, account ..., route codex)`.
    - As ben: `mkdir -p ~/tc-qa-bin`, then make the stand-in fail:
      `printf '#!/bin/sh\necho "$@" >> ~/tc-qa-bin/rings.txt\nexit 1\n' >
      ~/tc-qa-bin/codex` and `chmod 700 ~/tc-qa-bin/codex`.
    - As ben: `PATH=~/tc-qa-bin:$PATH tc send --from ben --to annc
      "first"`. It exits 0 and warns `ring failed for annc: codex exited 1
      with no stderr; the mail is in its inbox; the next send to annc
      rings again`. `wc -l < ~/tc-qa-bin/rings.txt` prints `1`. `head -1
      /srv/tc-shared/mail/.ring-pending-annc` prints `failed`. `ls -l
      /srv/tc-shared/outbox/ben/.rang-annc` shows `-rw-------`, owner
      `ben`: ben's own record of his last ring.
    - As ben, the forger: `printf 'clear\n' >
      /srv/tc-shared/mail/.ring-pending-annc`. It works: the marker is
      group-writable (C4).
    - As ben, make the stand-in answer 0: `printf '#!/bin/sh\necho "$@"
      >> ~/tc-qa-bin/rings.txt\nexit 0\n' > ~/tc-qa-bin/codex`.
    - As ben, at once: `PATH=~/tc-qa-bin:$PATH tc send --from ben --to
      annc "second"`. It exits 0 with no `rang codex` line: the marker
      says clear, mail waits, and ben's own last ring is under 5 minutes
      old. `wc -l` still prints `1`.
    - Wait until 5 minutes (RING_BACKOFF_SECONDS, 300 s) have passed
      since the first send. If the marker changed meanwhile, write
      `clear` into it again as above. As ben: `PATH=~/tc-qa-bin:$PATH tc
      send --from ben --to annc "third"`.
    - Pass: the third send prints `rang codex annc (queued; delivered
      when its turn ends or the session is resumed)`, and `wc -l` prints
      `2`: the forged `clear` held the doorbell off for one backoff at
      most. Fail: no `rang codex` line and still `1`: the marker alone
      decided, and annc would never be rung while its mail waits unread.
    - Put it back. As ann: `tc read annc`. As ben: `mv ~/tc-qa-bin
      ~/tc-qa-aside/step31-bin`.
32. Only a name's owner listens for it, and a name nobody joined is
    refused (D36 (2), P3 fix round 2). The tests show this with one
    Linux user standing in for two; this step shows the kernel's view.
    - As ben: `ls -la /srv/tc-shared/mail/to-ann > /tmp/before-ben.txt`.
    - As ben: `tc wait ann --timeout 5; echo $?`. It prints `tc wait:
      ann's inbox belongs to ann; only ann listens for it` and `1`.
    - As ben: `tc watch ann --heartbeat 5; echo $?`. It prints `tc
      watch: ann's inbox belongs to ann; only ann listens for it` and
      `1`.
    - As ben: `ls -la /srv/tc-shared/mail/to-ann | diff
      /tmp/before-ben.txt -` prints nothing: the refused wait and watch
      made nothing in ann's inbox.
    - As ben: `tc wait nobody-here --timeout 5; echo $?`. It prints `tc
      wait: nobody has joined as nobody-here on this shared mailbox; its
      owner runs tc join nobody-here first` and `1`, and `ls
      /srv/tc-shared/mail` shows no `to-nobody-here`.
    - Pass: each of the three runs exits 1 with those words, the `diff`
      prints nothing, and no `to-nobody-here` appears. Fail: any exit
      other than 1, an `ALREADY` or `HEARTBEAT` line, a changed listing
      of ann's inbox, or a `to-nobody-here` folder.
    - Put it back. As ben: `mv /tmp/before-ben.txt
      ~/tc-qa-aside/step32-before-ben.txt`.
33. A member plants and holds ann's watch lock before ann has ever run
    tc watch, and ann's watch moves it aside and runs (D35 (1), P3 fix
    round 2).
    - As ann: `ls -la /srv/tc-shared/mail/to-ann/.watch.lock` says `No
      such file or directory`: ann has never run tc watch here.
    - As ben: `python3 -c 'import fcntl, sys, time; f = open(sys.argv[1],
      "a"); fcntl.flock(f, fcntl.LOCK_EX); time.sleep(120)'
      /srv/tc-shared/mail/to-ann/.watch.lock &`, and note the pid the
      shell prints. Call it P. It runs: ann's inbox lets the group make a
      file in it.
    - As ann: `tc health` has a line `held
      /srv/tc-shared/mail/to-ann/.watch.lock: ann's watch lock, held by
      ben (pid P), not by its owner ann`.
    - As ann: `tc watch ann --heartbeat 0 --poll 1 --load-ratio 100000
      --mem-min-pct 0 --gpu-max-c 100000; echo $?`. On stderr: `tc watch:
      /srv/tc-shared/mail/to-ann/.watch.lock was a file owned by ben, not
      this user's own watch lock; moved it aside to
      /srv/tc-shared/mail/to-ann/.watch.lock.planted-1 and made a new
      one`. Then a `HEARTBEAT` line, and `echo` prints `0`.
    - As ann: `ls -la /srv/tc-shared/mail/to-ann/.watch.lock*` shows
      `.watch.lock` as `-rw-------`, owner `ann`, and
      `.watch.lock.planted-1` owned by `ben`.
    - Pass: the `held` line names ben and P; ann's watch says it moved
      ben's file aside, prints its heartbeat and exits 0; the new lock is
      ann's at `-rw-------`. Fail: `ALREADY WATCHING` and exit 3,
      `Operation not permitted` (ann's tc could not move ben's file), no
      `held` line, or a `.watch.lock` that is not ann's at `-rw-------`.
    - Put it back. As ben: `kill %1`. The file tc moved aside,
      `.watch.lock.planted-1`, stays where tc put it, out of the lock's
      way; the cleanup at the end moves it aside with the whole mailbox.

## Nothing planted replaces read mail, and nobody swaps ROOT (round 3)

34. ben plants a file under the name of one of ann's messages, in her
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
35. Init refuses a ROOT under a folder the group may write (D23).
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

36. A recipient swaps a link in for a member's own message, and the
    member's init leaves the folder it points at alone. Here ann is the
    recipient who swaps: she owns her `read/`, and under sticky the
    folder's owner may rename anything in it. Any recipient of a
    member's mail can do the same. The message is ben's from step 10,
    `000001-from-ben.md`, in ann's `read/` since step 11 and still
    owned by ben.
    - As ben, first: `tc init --shared --group tcshare` once. Step 34
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
    - Put it back. As ann: `mv
      /srv/tc-shared/mail/to-ann/read/000001-from-ben.md
      ~/tc-qa-aside/step36-link` (the link), then `mv
      /srv/tc-shared/mail/to-ann/read/aside
      /srv/tc-shared/mail/to-ann/read/000001-from-ben.md`. As ben: `mv
      ~/tc-qa-folder ~/tc-qa-aside/step36-folder`.

## A folder swapped on the way never leads init out of the mailbox (round 7)

37. A recipient swaps a whole folder on the way, not one entry, for a
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
    - Put it back. As ann: `mv /srv/tc-shared/mail/to-ann/read
      ~/tc-qa-aside/step37-link` (the link; with no `/` at its end, `mv`
      moves the link, not the folder it points at), then `mv
      /srv/tc-shared/mail/to-ann/read-aside
      /srv/tc-shared/mail/to-ann/read`. As ben: `mv ~/tc-qa-folder2
      ~/tc-qa-aside/step37-folder2`.

## Each member's outbox is their own (D22)

<!-- Added by the SSH lane agent (Claude Opus 5.5), 2026-10-15; its history is under "Round history"; the setup sentence changed for the order at the top by the DOCS2 lane agent (Claude Opus 5.5), 2026-10-17. Status: unreviewed. -->
ssh runs as the Linux user who ran `tc send`, with that user's keys, so
one member's dead queue must never hold up another's mail, and each
member's `tc flush` sends only that member's files. Each member's ssh
mail waits in a branch of the outbox that member alone owns,
`outbox/<user>/` (D32), mode 2750, so no other member can move, rename,
remove or plant anything in it (D33). These steps need a far machine
that ann's ssh key reaches through `tc gate` and ben's does not.
`qa/human/route-ssh.md` sets one up. If you walked it first, as the
order at the top says, its steps 2 to 7 are done: go on to step 38. If
not, as ann, do its steps 2 to 7 now (not 1 or 8), with
`TC_ROOT=/srv/tc-shared` still exported from step 4 here. `farbox-tc`
below is the ssh alias that file makes, and `far-b` the name on the far
machine. Both are made up; use yours.

38. As ann: `tc card far-b --ssh farbox-tc --remote-tc '~/tc-qa/tc'`.
    - It prints `card written: far-b (other, account unknown, route ssh
      to farbox-tc)`. ben reads the same card: `tc cards` as ben shows
      the same line.
39. As ben: `tc send --from ben --to far-b "from ben"`.
    - ben has no key there, so ssh fails: it exits 4 and says `could not
      reach farbox-tc (...); kept in outbox:
      /srv/tc-shared/outbox/ben/to-far-b/<n>-from-ben.md. Run: tc flush`.
      The words in the parentheses are ssh's own, such as `Permission
      denied (publickey).` or a host it could not resolve.
    - `ls -ld /srv/tc-shared/outbox/ben /srv/tc-shared/outbox/ben/to-far-b`
      shows each as `drwxr-s---`, owner `ben`, group `tcshare` (2750:
      setgid, no group write). `ls -l` of the file shows `-rw-r-----`,
      owner `ben` (0640).
    - Beside it, `<n>-from-ben.md.stderr` holds this try's words, its
      first line the same `could not reach farbox-tc (...)`, and `ls -l`
      shows it `-rw-r-----`, owner `ben` (D36 (4), P3 fix round 1c). Each
      later failed try replaces it.
40. A member who makes another member's branch first (D33). As ben,
    before ann has sent anything over ssh: `mkdir
    /srv/tc-shared/outbox/ann`. Then as ann: `tc send --from ann --to
    far-b "from ann"`.
    - It exits 1, writes nothing, and says `/srv/tc-shared/outbox/ann
      belongs to ben, not to ann: a branch and every folder in it are
      their member's alone (D32, D33), so tc wrote nothing there. The
      user who ran init (ann) clears it with one command: mv -T
      /srv/tc-shared/outbox/ann /srv/tc-shared/outbox/.squatted-ann-1`.
    - `tc health`, as ann, has a line `squatted
      /srv/tc-shared/outbox/ann: a folder ben owns, not ann's own branch.
      The user who ran init (ann) runs: mv -T ...`, the same command.
    - As ann, run that `mv -T` line exactly as printed. `tc health` then
      has no `squatted` line.
41. As ann: `tc send --from ann --to far-b "from ann"` again.
    - It goes out at once, ben's waiting file notwithstanding: exit 0,
      `sent over ssh to farbox-tc: sent #... to far-b: ...`. ann's queue
      holds only ann's files, so ben's file is not ahead of hers.
    - `ls /srv/tc-shared/outbox/ann/to-far-b/sent/` lists ann's message,
      and `ls -la /srv/tc-shared/outbox/ann/` (`-a`: the lock's name
      starts with a dot) shows her send lock, `.send-<16 hex
      digits>.lock`, as `-rw-------`, owner `ann` (0600).
    - On the far machine, `tc read far-b` shows it, from the gate's key
      name, never from `ann`.
42. As ann: `tc flush`.
    - It prints `1 waiting for farbox-tc from other members (ben); each
      member sends their own with tc flush`, then `nothing of yours
      waiting in the outbox`, and exits 0.
    - ben's file is where it was, unchanged: `ls -l` shows the same
      line as in step 39.
43. Neither member can touch the other's branch. Each of these is
    refused, and the `ls -l` of each branch afterward matches the one
    before:
    - As ann: `mv /srv/tc-shared/outbox/ben/to-far-b/<n>-from-ben.md
      /srv/tc-shared/outbox/ben/to-far-b/moved.md`: `Permission denied`
      (ben's folder has no group write). The rename stays inside the
      folder, so nothing is copied out on the way.
    - As ben: `mv /srv/tc-shared/outbox/ann/to-far-b/sent/<n>-from-ann.md
      /srv/tc-shared/outbox/ann/to-far-b/sent/moved.md`: `Permission
      denied`.
    - As ben: `mkdir /srv/tc-shared/outbox/ann/to-elsewhere`:
      `Permission denied`.
    - As ben: `mv /srv/tc-shared/outbox/ann /srv/tc-shared/outbox/ann-old`:
      `Operation not permitted` (outbox/ is sticky, and ben owns neither
      it nor ann's branch).
    - As ben: `cat /srv/tc-shared/outbox/ann/.send-*.lock`: `Permission
      denied`, so ben cannot open ann's send lock and hold it.
44. A member's stuck mail shows in every member's `tc health`, and a FIFO
    that member plants as its note never hangs it (D36 (4), P3 fix round
    2).
    - As ben, with step 39's file still waiting: `touch -d '2 days ago'
      /srv/tc-shared/outbox/ben/to-far-b/<n>-from-ben.md`.
    - As ann: `tc health` has a line `stuck
      /srv/tc-shared/outbox/ben/to-far-b/<n>-from-ben.md: ben's mail to
      far-b, waiting 2d; last failed try: could not reach farbox-tc
      (...)`, the words in the parentheses as step 39 printed them.
    - As ben: `mv /srv/tc-shared/outbox/ben/to-far-b/<n>-from-ben.md.stderr
      /srv/tc-shared/outbox/ben/to-far-b/kept-note`, then `mkfifo
      /srv/tc-shared/outbox/ben/to-far-b/<n>-from-ben.md.stderr`.
    - As ann: `time tc health`. It finishes with `real` under 2 seconds,
      and the same stuck line now ends `no failed try noted beside it`.
    - Pass: the stuck line names ben's mail with its note's first line,
      and with the FIFO in place `tc health` returns at once and says no
      failed try is noted. Fail: no stuck line for ben's mail, or a `tc
      health` that hangs (stop it with Ctrl+C, and write down that it
      hung).
    - Put it back. As ben: `mv
      /srv/tc-shared/outbox/ben/to-far-b/<n>-from-ben.md.stderr
      ~/tc-qa-aside/step44-fifo` (the FIFO), then `mv
      /srv/tc-shared/outbox/ben/to-far-b/kept-note
      /srv/tc-shared/outbox/ben/to-far-b/<n>-from-ben.md.stderr`.
<!-- Step 45 and the cleanup rewritten by the DOCS2 lane agent (Claude Opus 5.5), 2026-10-17: moves aside, never rm, and route-ssh.md's cleanup once, last. Status: unreviewed. -->
45. Put it back. As ben: `mv
    /srv/tc-shared/outbox/ben/to-far-b/<n>-from-ben.md
    /srv/tc-shared/outbox/ben/to-far-b/<n>-from-ben.md.stderr
    ~/tc-qa-aside/` (ben's own file and its note, so nothing of ben's
    waits for far-b any more), then `mv
    /srv/tc-shared/outbox/.squatted-ann-1 ~/tc-qa-aside/step40-squatted`
    (the folder ben made in step 40, which ann moved aside).
    route-ssh.md's cleanup comes later, once (the order at the top).

## Read times are the owner's (READTIME)

<!-- Steps 45a to 45c: the READTIME lane agent (Claude Opus 5.5), fix round 2, the review's REC-3, 2026-10-17. Status: unreviewed. -->
`tc read` appends one line per message it moves to `read/.read-times`,
and only the owner of `read/` records. These three steps run in the
same throwaway mailbox, `TC_ROOT=/srv/tc-shared`, and need no ssh.
`<n>` is the number a send prints.

45a. ben's `tc log` shows ann's read times. As ben: `tc log`, then `ls -l
    /srv/tc-shared/mail/to-ann/read/.read-times`.
    - Under the header of ben's step 10 message (`# #1 from ben to ann,
      ...`) the next line is `read <time>`, the time of ann's step 11
      read, with its offset, a moment after the header's sent time.
    - `ls -l` shows `-rw-r-----`, owner `ann`, group `tcshare` (0640).
    - Pass: `read <time>` under that header, and no `tc log:` line on
      stderr about `.read-times`. Fail: `read, time not recorded` under
      it, a `tc log: ... .read-times not read` line, or a record ben owns.
45b. ben's `tc read ann` records nothing. As ann first: `tc read ann`, so
    nothing of ann's waits in her inbox. As ben: `tc send --from ben
    --to ann "ben reads this himself"`, then `sha256sum
    /srv/tc-shared/mail/to-ann/read/.read-times`, then `tc read ann`,
    then the same `sha256sum` again.
    - `tc read ann` prints ben's message, moves it into ann's `read/`
      (ben owns that file, so he may), exits 0, and prints one line on
      stderr: `tc read: read times for ann are kept by ann, who owns
      /srv/tc-shared/mail/to-ann/read; none recorded for 1 message`.
    - Both `sha256sum` lines are the same.
    - As ann: `tc log`. Under that message's header: `read, time not
      recorded`.
    - Pass: the not-owner line, exit 0, the record unchanged. Fail: no
      line, a non-zero exit, a changed hash, or a time under that header.
45c. ann's first read moves ben's planted record aside. As ann: `tc join
    ann2` (a fresh name, so its `read/` has no record yet). As ben: `tc
    send --from ben --to ann2 "for ann2"`, which prints the message's
    file name, `<name>` here; then `echo '{"name": "<name>", "read":
    "2000-01-01T00:00:00+00:00"}' >
    /srv/tc-shared/mail/to-ann2/read/.read-times` (any member may make a
    file in `read/`). As ann: `tc read ann2`, then `ls -l
    /srv/tc-shared/mail/to-ann2/read/`, then `tc log`.
    - `tc read ann2` prints ben's message, exits 0, and prints on stderr
      `tc read: /srv/tc-shared/mail/to-ann2/read/.read-times was a file
      owned by ben, not this user's own read-time record; moved it aside
      to /srv/tc-shared/mail/to-ann2/read/.read-times.planted-1`.
    - `ls -l` shows `.read-times` owned by `ann`, `-rw-r-----`, and
      `.read-times.planted-1` owned by `ben`, its text unchanged.
    - In `tc log`, under the header of that message: `read <time>`, today's
      time from ann's read, never `read 2000-01-01T00:00:00+00:00`.
    - Pass: the words, both files as above, and ann's own time. Fail: no
      words, ben's line believed, ann's read exiting non-zero, or the
      plant gone.
    - Put it back. As ben: `mv
      /srv/tc-shared/mail/to-ann2/read/.read-times.planted-1
      ~/tc-qa-aside/step45c-planted` (ben's own file).

## Cleanup

Nothing here removes anything. Each step moves what this walk made out
of the way, and what is moved aside is yours to remove when you choose.

46. In every terminal, as ann and as ben: `unset TC_ROOT`.
47. As a user with sudo: `sudo mkdir -m 0700 /srv/tc-qa-aside`, then
    `sudo mv /srv/tc-shared /srv/team /srv/tc-qa-aside/`. That takes the
    mailbox and the team folder from step 35, with `tc` and `tc2` in it.
    - `ls /srv` no longer lists `tc-shared` or `team`, and neither user
      can reach what is under `/srv/tc-qa-aside`.
48. If you walked route-ssh.md too, do its cleanup now, steps 23 to 28,
    once. Walking this file alone, do its cleanup for what its steps 2
    to 7 made: its steps 23 and 24, and in its step 25 the key only.
49. Left for you to remove yourself, when you choose: `/srv/tc-qa-aside`
    (the mailbox and the team folder), `~/tc-qa-aside` of ann and of ben
    (what each "Put it back" moved there), and the group `tcshare`, with
    ann and ben in it.
50. Record what you saw in `qa/results/route-shared.md`, with made-up
    names only.

## Round history

<!-- Moved here from the top of this file (the Model block's list, the outbox section's note and the old lead paragraph), words kept but for each one's opening clause, by the DOCS2 lane agent (Claude Opus 5.5), 2026-10-17. Status: unreviewed. -->
A walker can skip this section. It says which round wrote which step
and which check, as each round recorded it. The step numbers in it are
as each round wrote them, not as they stand now.

**Who changed what.** The SHARED lane agent, Claude Opus 5.5, wrote this
file on 2026-10-14; the D21 steps (6, 7, 13 to 15, and 22) added by the
SHARED fixer, Claude Opus 5.5; step 25's words and steps 27 to 29 added
in round 2 by the SHARED fixer, Claude Opus 5.5; steps 30 and 31, and
the words of steps 3, 15, 28 and 29, in round 3 by the SHARED fixer,
Claude Opus 5.5, 2026-10-15; steps 15, 30 and 31 changed in round 4 by
the SHARED fixer, Claude Opus 5.5, 2026-10-15; steps 15 and 31, and the
paragraph after step 23, changed in round 5 by the SHARED fixer, Claude
Opus 5.5, 2026-10-15; steps 15 and 31 changed, and step 32 added, in
round 6 by the SHARED fixer, Claude Opus 5.5, 2026-10-15; the lead
paragraph changed, and step 33 added, in round 7 by the SHARED fixer,
Claude Opus 5.5, 2026-10-15; the lead paragraph changed in round 8 by
the SHARED fixer, Claude Opus 5.5, 2026-10-15; steps 34 to 39 (D22)
added, and the last step renumbered, by the SSH lane agent, Claude Opus
5.5, 2026-10-15; steps 34 to 40 rewritten for D32 and D33, and the last
step renumbered and its words made to name both folders, in fix round 1
by the SSH fixer, Claude Opus 5.5, 2026-10-15; step 29's words changed
for D35 (3), steps 30 and 31 added after it, and every step after them
renumbered by two, in P3 fix round 1b by the P3 fixer, Claude Opus 5.5,
2026-10-15; steps 5 and 37 to 42 brought to P3 fix round 1c (init makes
mail/.origins/, the note beside a waiting file, the squatted line's
sentence, the flush count's words, `ls -la` for the send lock) by the P3
fixer, Claude Opus 5.5, 2026-10-15; steps 32, 33 and 44 added (D36 (2),
D35 (1) with a planted watch lock, D36 (4) with a FIFO note), the steps
after 31 renumbered by two and the last two by three, with the
references to them, in P3 fix round 2 by the P3 fixer, Claude Opus 5.5,
2026-10-15.

**The outbox section (D22).** Added by the SSH lane agent (Claude Opus
5.5), 2026-10-15; rewritten for D32 and D33 in fix round 1 by the SSH
fixer, Claude Opus 5.5, 2026-10-15 (the old step 38, a known limit, is
the check in step 43 now: P3 fix round 1b renumbered it from 39, and P3
fix round 2 from 41). Status: unreviewed.

**The checks, by round.** Two Linux users in one group share one
mailbox. Each can send, wait and read. Neither can delete, rename or
rewrite the other's unread mail (D20). Only the user who ran init can
change the group, and a send to a name nobody joined is refused even
when an inbox is there (D21). A planted link is never printed (D19). A
member who sets `mail/.seq` back or holds a lock can make the other's
command fail, never lose a message or hang it, and init never shares a
ROOT the group may write (round 2); that failure names who holds the
lock, a member cannot hold another member's listener, and a member who
rewrites a Codex member's doorbell holds it off for one backoff at most
(P3 fix round 1b, D35, D36). Only a name's owner listens for it, a file
a member plants and holds at the owner's watch lock is moved aside, and
a member's stuck outbox mail shows in every member's `tc health`, a FIFO
planted as its note never hanging it (P3 fix round 2, D35 (1), D36 (2)
and (4)). A file a member plants under a message's name, in the inbox or
in read/, never replaces it, and init refuses a ROOT a member could swap
through a folder above it (round 3, D20, D23). tc read calls neither of
two such files forged, and a planted name of any length wakes `tc wait`
at most once (round 4). A member's init on the init user's ROOT is
refused with words that name who ran init and charge no one, and a
member who makes ROOT first stops the init user's init (round 5, D28).
That refused init then fixes the member's own entries itself, through a
no-follow open (round 6, D29). Every folder from ROOT down is pinned by
identity: init opens ROOT once, right after its walk, and goes on only
when it is the folder the walk looked at (on a member's rerun, the init
user's); then it opens each of the four, each folder below them and each
entry by its name in the folder above it, never by its path, and changes
an entry only when it is the one the walk found. So a link or another
folder swapped in for ROOT, a folder above it, a folder on the way, or
an entry, while init runs, never leads either walk out of the mailbox
(rounds 7 and 8). ROOT's owner and every folder above it are judged by
the walk, by path, before that (step 35). A file with a second name (a
hard link) is never changed, and a nest of folders too deep is named
and left (round 8). The only command line tc prints is D23's `chmod
g-w,o-w`, to the owner of ROOT or of a folder above it (steps 28 and
35); for an entry under the four it prints none.
