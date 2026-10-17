#!/usr/bin/env python3
"""
serve.py: the live board's feed (C5) and its server (C6). Loads tc as a
module and never edits it. feed() builds one JSON object from the parts
it needs: the machine (machine_now, tc's numbers and rounding read here),
the listeners and the mail (tc.listeners, tc.mailbox_summary), each
stopped name's wait exit record (tc.wait_exits; F1, Claude Opus 5.5,
unreviewed), the address cards and the message file names, never from
tc.health_snapshot().
It never opens a message body. The server reads only: it answers GET and
HEAD on 127.0.0.1, gives the feed to a request that carries the token, and
serves an allow list of the board's own files.

    python3 board/serve.py [--port 8780]

prints `board: http://127.0.0.1:<port>/live.html#token=<t>` once and serves
until Ctrl+C or SIGTERM. The token sits in the URL fragment, which the
browser never sends, so it reaches no server log and no referrer. The
mailbox is tc's: TC_ROOT if set, else the folder tc lives in.

Model:  Claude Opus 5.5 (the BOARD lane agent), 2026-10-14
Status: unreviewed

Where each feed key comes from. `snap` is Board.snapshot(): the parts of
tc's health the feed needs, built here from tc.now_iso(), machine_now(),
tc.listeners("wait") and tc.mailbox_summary(), never the full
tc.health_snapshot(). That one also runs nvidia-smi, which can take tc's
GPU_QUERY_TIMEOUT_SECONDS (longer than the page waits for an answer),
reads every process's stat and cmdline, and on the merged tc reads every
card again; the feed uses none of those, so a poll never waits on a GPU
query. Cards never come from tc's health:

  at                       snap["time"] (tc's now_iso(): local time, seconds)
  machine.load1            snap["machine"]["load1"]: machine_now(), the
  machine.cores            numbers and rounding of tc's machine_stats
  machine.mem_avail_pct    without its GPU query
  nodes[].id               a name with an inbox (a key of snap["mail"]) or a
                           card (cards/<name>.json), sorted
  nodes[].listener_pid     snap["listeners"][name]: the pid tc read from
                           /proc/locks, or None
  nodes[].unread           snap["mail"][name]["unread"]; 0 with no inbox;
                           None when tc cannot count it (a tc that says
                           so for an inbox it cannot see into)
  nodes[].unread_problem   snap["mail"][name]["mail_problem"], tc's reason,
                           when unread is None; else None
  nodes[].inbox_unreadable True when this board could not list the name's
                           mail/to-<name>/ or its read/ (a folder it may
                           not open); the page says `inbox unreadable`
                           beside `down`
  nodes[].last_mail_age_s  snap["mail"][name]["newest_mail_age_s"]: seconds
                           since the newest message in the name's inbox or
                           read/, so mail it received, never under 0 (a
                           future mtime reads 0); None with no inbox
  nodes[].down_age_s       F1 fix round 1 (Claude Opus 5.5, unreviewed):
                           for a node `down` because its wait exit record
                           says `listening`, whole seconds since it stopped
                           as this Board knows it (Board.down_age: since its
                           lock was last seen held, else since the record's
                           time), never under 0; None for any other node.
                           The page counts a stop DOWN_WINDOW_S or more old
                           as `stopped earlier` and warns only on a fresher
                           one (C5), with no clock of its own
  nodes[].kind, account,   the card, read straight from cards/<name>.json
  route, reports_to        (C1), never from a `cards` key in health. With no
                           card: kind and account None, route "local" (C1:
                           no card means route local), reports_to None
  nodes[].status           status/<name>.md: the first non-empty line after
                           its "## <name> status, <time>" header, cut at
                           STATUS_PREVIEW_CHARS
  nodes[].state            below
  nodes[].role,            computed here, C5 "Roles and levels"; `parent` is
  role_source, level,      the parent the level walk used (D15, pause
  parent                   BOARD-3), or None: a root has none, and so does
                           the node that breaks a reports_to cycle
  wires, links             message file names under mail/to-*/ and
                           mail/to-*/read/; ages from each file's mtime (a
                           stat, never an open)

State, first match wins, in D15 and D24's order: `writing` (its newest sent
message is at most WRITING_WINDOW_S old, listener or not); then, for a name
with no pid now whose wait exit record says `listening`, `down` (F1,
below; F1 fix round 1: unless a second look at the locks finds it held,
a session that re-armed between the two reads, which is `listening`);
then, for a name with no pid now that this Board saw listening
within DOWN_WINDOW_S, one of `down`, `woken` or `working` (after_listening). Mail woke it when a message
landed in its inbox no earlier than tc's POLL_SECONDS before it was last
seen listening and no later than POLL_SECONDS after the first poll that
found no pid (D28): mail that lands after the board has seen the listener
gone woke nothing. No such mail: `down`, the lock vanished and nothing woke
it, whatever mail lands later. Woken: `working` when the message that woke
it has left the inbox, or its status file or its last sent message is
newer than when it was last seen listening, or the wake is under
WOKEN_GRACE_S old; else `woken`. A name whose inbox (or its read/) this
board cannot list reads `down` with inbox_unreadable set: the board cannot
tell. Then `listening` (a pid holds the name's lock in /proc/locks),
`doorbell` (route codex), `remote` (route ssh), `idle`. A message whose
mtime is in the future has no age, so it never makes its sender writing.
What was seen listening, when it was first seen gone and the wake found
live in this object's memory only: after a restart nothing is woken or
working until it has been seen listening again.

Model: Claude Opus 5.5 (the F1 lane agent), 2026-10-16. Status:
unreviewed. C5's wait exit record (D28, D37 part 2): tc wait keeps
mail/to-<name>/.wait.exit, and for each name with no pid this board reads
it through tc's one reader (tc.wait_exits). It is never proof of life;
only a pid is. It says why a lock that is gone went (stopped_state): a
record saying `listening` means the wait was killed or crashed, so the
name reads `down`, after a restart too and past DOWN_WINDOW_S (nothing
the board sees ends that down but the name listening again), and its
node carries down_age_s, so the page's pill warns only while that stop
is under DOWN_WINDOW_S old and counts older ones as `stopped earlier`
(F1 fix round 1, Claude Opus 5.5, unreviewed: the audit's LOW-1, C5's
"The pill warns only on a fresh stop"); a record
saying `mail` or `timeout`, dated after the board last saw the lock
(tc.left_on_purpose), means it left on purpose, so it is never `down`
(the woken and working rules above still apply, and a `down` they give
falls to the states after it); no record, or one tc's reader would not
take (a tc from before F1), keeps the rules above exactly, so with none
nothing is down after a restart until it has been seen listening again.
Two cases these states cannot see (C5): a session that crashes after
reading its mail reads `working` until DOWN_WINDOW_S has passed since it
was last seen listening; and with no board page open nothing polls, so
the board cannot tell when a listener went, unless its exit record says
why: without a record, mail that landed before the first poll after it
went counts as a wake.

Roles and levels follow C5 step by step. Partners are the names a node has
exchanged mail with, either way, itself excluded; a partner need not be a
node. A parent is always a node: declared from the card's reports_to when
it names a node, else inferred (D27) as the partner holding at least
PARENT_MAJORITY (two thirds) of the node's messages, sent and received,
when that partner has HUB_MIN_PARTNERS or more, unless that partner's card
declares this node as its own parent (D15: inference never inverts a
declared edge); a node split evenly between two relays gets no guess. A
reports_to that names no node, or the node itself, gives no parent and
stops inference. A peer's role_source is `none`, never `inferred`: no
edge decided it. An inferred edge that closes
a cycle, through any chain of declared ones, is taken out with every other
inferred edge on that cycle (drop_inferred_cycles), before roles and
levels are read, so the drawing never depends on the order the names sort
in. Nodes the walk from the roots cannot reach then hang on a cycle made
only of reports_to cards; the cycle member whose name sorts first becomes
a root (assumption in the BOARD handoff: a node below a cycle is not on
it, so it stays below).

Known limit (C5 rule 6): with no hints at all, a top relay whose only
partner is a lower relay is drawn as that relay's `worker`, marked
`inferred`. `tc join <name> --reports-to <relay>` fixes it.

@interacts  loads ../tc as a module from its source, compiled in memory,
            with TC_ROOT set for the load only, then calls tc.now_iso(), tc.listeners("wait") (reads
            ROOT/.shared and /proc/locks, opens mail/ and each
            mail/to-<name>/ by name and lstats the .wait.lock in it, its
            owner's since D35; on a private mailbox, until every listener
            started before has re-armed, also mail/.wait-*.lock: P3 fix
            round 1b, Claude Opus 5.5, unreviewed) and tc.mailbox_summary()
            (opens mail/ once and each mail/to-<name>/ and its read/ by
            name, lists each in its own descriptor and stats each message
            name there, never through a link, and lstats each name's
            status file; P3 fix round 2, Claude Opus 5.5, unreviewed: the
            audit's LOW-6, true to tc since its round 1a); reads the
            load average and /proc/meminfo itself. Never runs nvidia-smi
            and never scans the process list. Reads cards/*.json and the
            head of status/<name>.md; lists mail/to-*/ and mail/to-*/read/,
            each opened by its name in the folder above (mail/ once, by
            its path) and listed in its own descriptor (P3 fix round 1a,
            Claude Opus 5.5, unreviewed: D35), and stats a few message
            files by their names in those open folders, never by a path
            and never through a link, each folder held open until the
            poll has dated its messages (P3 fix round 1c, Claude Opus
            5.5, unreviewed: round 1a's MEDIUM), and for a name that
            stopped listening, its status file (by path, never followed),
            its last sent message and, while its wake window is open, its
            WAKE_CANDIDATES newest messages. F1 (Claude Opus 5.5,
            unreviewed): for each name with no pid, tc.wait_exits opens
            its inbox by name in mail/ and reads its wait exit record
            (read_wait_exit: never through a link, never blocking, only
            the inbox owner's one-line file); F1 fix round 1: when one
            says `listening`, tc.listeners("wait") once more.
            Opens no message body. Writes nothing to the mailbox, and
            reads and writes no bytecode cache of tc's. main() binds one
            TCP socket on 127.0.0.1, prints the URL with the token once to
            stdout, reads the allow-listed files in board/ per request, and
            writes no request log. A failed feed writes one line to stderr,
            and so do a client that hangs up mid-answer, any other request
            that fails past its handler (never a traceback), and the first
            poll that meets a card nested past Python's recursion limit.
            Card and status files are opened with O_NONBLOCK and O_NOFOLLOW
            and read only when fstat says regular, so a FIFO never blocks a
            poll and a symlink never redirects one; mail folders are listed
            the same way, never through a link.
@deps       python3 stdlib (argparse, collections, contextlib, errno,
            fractions, heapq, hmac, http.server, io, json, os, pathlib,
            re, secrets, signal, stat, sys, threading, time, types,
            urllib.parse); ../tc; Linux
            (/proc: /proc/locks through tc, the load average and
            /proc/meminfo read here).
@complexity feed(), per poll: O(k + n log n + M + m (log m + log W +
            log K) + c^2 + g log g). The
            snapshot: tc.listeners is O(k + n log n), k lines in
            /proc/locks (tens) and n names (single digits to tens), one
            inbox opened and one lock lstat()ed per name (P3 fix round
            1b, Claude Opus 5.5, unreviewed: D35);
            tc.mailbox_summary is O(n log n + M + m log m) over the M
            names listed in every inbox and read/ and the m message files
            among them (about 800 after two weeks of heavy use, and only
            growing, since read/ is kept): one listing per folder, one
            stat per message name and a sort per folder (P3 fix round 2,
            Claude Opus 5.5, unreviewed: the audit's LOW-6, tc's own
            @complexity since its round 1a). Here: every inbox listed
            again and each of the m names matched twice (no body read);
            the last WIRE_HISTORY picked in O(m log W), W = 50; W + n + l
            more stats for l linked pairs (at most n^2/2, tens in
            practice); each card read once, c cards; parents, roles and
            levels in O(n + l + e) from the l pairs' counts, e parent
            edges (at most n); c(c-1)/2 native links over the
            claude cards on one named account; and for each of s names
            that stopped listening within DOWN_WINDOW_S, its newest
            K = WAKE_CANDIDATES messages kept in a heap as the scan goes
            (O(log K) per message to such a name), stats of those K while
            its wake window is open (a poll or two per stop), and of its
            status file and its last sent message. F1 (Claude Opus 5.5,
            unreviewed): for each of the g names with no pid now (every
            name that ever listened and is not listening), one inbox
            open and one short read of its exit record (tc.wait_exits,
            O(g log g)). F1 fix round 1 (Claude Opus 5.5, unreviewed):
            when any of those records says `listening`, tc.listeners runs
            once more, O(k + n log n), so a session that re-armed between
            the two reads is listening, never down (the audit's LOW-3); a
            killed listener's record keeps saying `listening`, so with one
            on the board every poll lists the locks twice. In all about m + W + n + l + s(K + 2) stats and
            g record reads per poll at most, and no child process. One
            request: O(1) to route, plus one feed() or one read of a board
            file (tens of KB).
@alloc      per feed(): tc.mailbox_summary builds m path and stat objects; here
            one Message per message file, each one's dedupe key and dict
            slot, the name list of each folder (message_names), and for
            each message a short-lived sorted pair (a list and two tuples)
            and a default count dict, kept only for a pair's first
            message as the per-pair counts; the partner counts, one dict
            per name with a partner and two entries per pair; for each
            name that stopped listening, a heap of at most K Messages
            while its wake window is open and the set of its inbox's file
            names; then the returned dict (n nodes, at most W wires,
            l + n + c(c-1)/2 links); all freed when the caller drops them;
            and, for the poll only, one descriptor per inbox and per read/
            (two per name), closed before feed() returns (P3 fix round
            1c, Claude Opus 5.5, unreviewed); one small record per name
            with no pid that has one, dropped with the poll (F1). Held
            across calls: the
            loaded tc module; last_listening_at, one float per name seen
            listening, pruned past DOWN_WINDOW_S on every feed();
            first_missing_at, one float per name seen listening and not
            listening now, and wakes, one small dict per such name with
            the file names of the messages that woke it (one or two,
            WAKE_CANDIDATES at most), both cleared on the name's next
            sighting and pruned with last_listening_at; and the names of
            cards found nested too deep, one each. The server
            holds one Board, the token, a lock and MAX_CONNECTIONS slots;
            one short-lived thread per request, at most MAX_CONNECTIONS at
            once, each ended by REQUEST_DEADLINE_S.
"""

import argparse
import collections
import contextlib
import errno
import fractions
import heapq
import hmac
import http.server
import io
import json
import os
import pathlib
import re
import secrets
import signal
import stat
import sys
import threading
import time
import types
import urllib.parse

BOARD_DIR = pathlib.Path(__file__).resolve().parent
TC_PATH = BOARD_DIR.parent / "tc"

# A name reads as writing for this long after its newest message (C5).
# Three of the page's 3 s polls, so a send is seen at least once; short
# enough that a session that went quiet stops reading as busy.
WRITING_WINDOW_S = 10
# A name seen listening this recently and not listening now is down, woken
# or working (C5, D24). Ten minutes covers a listener's re-arm gap and a
# long turn; past it, a name that stopped on purpose reads idle instead of
# raising an alarm.
DOWN_WINDOW_S = 600
# Model: Claude Opus 5.5 (the P4 phase fixer), 2026-10-15. Status: unreviewed.
# A listener that mail woke reads working for this long after the wake
# with no other sign of life (D24): the time a session takes to start its
# turn. Past it with no sign, it reads woken, not read: the doorbell rang
# and nobody answered.
WOKEN_GRACE_S = 120
# Model: Claude Opus 5.5 (the P4 phase fixer, round 2), 2026-10-15. Status:
# unreviewed. A stopped name's newest this many messages, by number, are the
# candidates for its wake (D24, D28). A wake is the mail that lands within
# one of tc wait's polls of the board's last sighting: a message or two.
# They are kept as the scan walks the mail, never by sorting a name's whole
# history, and read in file time order, so a hand-made file with a high
# number and an old time takes one place and ends nothing. A burst past
# this many in that window still dates the wake inside it.
WAKE_CANDIDATES = 16
# What message_names makes of a folder it cannot open: no folder (ENOENT),
# a link (ELOOP under O_NOFOLLOW) or a file where a folder should be
# (ENOTDIR) holds no messages, as the scan has always read them. Any other
# error (EACCES, EIO) is a folder the board cannot list (C5: the name reads
# down, `inbox unreadable`).
NO_FOLDER_ERRNOS = (errno.ENOENT, errno.ELOOP, errno.ENOTDIR)
# Model: Claude Opus 5.5 (the P3 fixer, round 1a), 2026-10-15. Status:
# unreviewed. D35, one pinned handle (the audit's HIGH-1 and its Coverage
# note on this scan, audits/2026-10-15-1409-full). How the scan opens
# mail/ itself, by its path: read only, only a folder. A link there is
# followed, as the scan always did: only the init user can swap mail/
# (D34).
MAIL_FLAGS = os.O_RDONLY | os.O_DIRECTORY
# How it opens each inbox, by its name in mail/'s descriptor, and each
# read/, by its name in its inbox's: read only, only a folder, never
# through a link. A member who owns an inbox may swap it for a link after
# the scan looked; the read/ the scan lists is then still the one in the
# folder it opened.
FOLDER_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
# Characters of a status line on a node (C5): one line on a node box. The
# whole status stays in status/<name>.md.
STATUS_PREVIEW_CHARS = 80
# Bytes read from the head of a status file. The preview needs one line;
# a runaway status file costs a poll no more than this.
STATUS_READ_MAX_BYTES = 4096
# Messages carried in "wires" (C5): the recent traffic the page animates.
# Links still read every message file name.
WIRE_HISTORY = 50
# A node's guessed parent must have at least this many partners (O11, C5
# rule 2): a hub. With two, a pair that mails only each other is a pair of
# peers, and a relay needs a second partner to be one.
HUB_MIN_PARTNERS = 2
# Model: Claude Opus 5.5 (the P4 phase fixer, round 2), 2026-10-15. Status:
# unreviewed. With no card to say so, a node's parent is guessed only from
# a partner holding at least this share of the node's messages, sent and
# received (D27). The board counts every message ever sent, so one message
# between two siblings must not move both out of their relay's tree, and a
# worker split evenly between two relays gets no guess. Two thirds is a
# clear majority, and no two partners can both hold it.
PARENT_MAJORITY = fractions.Fraction(2, 3)
# A card is a few hundred bytes (C1). The board reads at most this much of a
# file in cards/ and skips a bigger one, which is not a card. The merged tc
# caps its own card reads at the same 65,536 bytes; feed() never calls tc's
# card readers (Board.snapshot takes only the parts it needs), so each poll
# reads each card once, here.
CARD_READ_MAX_BYTES = 65536
# Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
# machine_now() gives C5's machine keys as tc's machine_stats does: load to
# two places, free memory as a percent to one, from /proc/meminfo.
LOAD_ROUND_DIGITS = 2
MEM_PCT_ROUND_DIGITS = 1
PERCENT = 100.0
MEMINFO_PATH = "/proc/meminfo"

# The server (C6). 8780 because 8765 was taken on the owner's machine on
# 2026-10-14 (O7); --port moves it, and port 0 lets the OS pick.
DEFAULT_PORT = 8780
# Model: Claude Opus 5.5 (the P4 phase fixer), 2026-10-15. Status:
# unreviewed. http's own port. A browser leaves it out of its Host header,
# and the Host check wants 127.0.0.1:<port>, so on this port it would
# refuse the page itself; main() refuses the port at start instead of
# loosening the check.
HTTP_DEFAULT_PORT = 80
# Loopback only. Nothing off this machine can reach the board; the token
# guards it from other local users' pages.
BIND_HOST = "127.0.0.1"
# Bytes of randomness in the token (C6: secrets.token_urlsafe(24), 32
# characters). Made once per start, never written to disk.
TOKEN_BYTES = 24
TOKEN_HEADER = "X-TC-Token"
# The names the page may reach the server by. Any other Host header is a
# page on another name pointed here (DNS rebinding), and gets 421.
HOST_NAMES = ("127.0.0.1", "localhost")
FEED_PATH = "/feed"
# The only files the server sends (C6). Anything else is 404, with no
# folder listing, so serve.py, tc and the mailbox never leave. A request's
# path is matched whole against these keys and the key alone is read from
# board/, so no part of a request is ever joined into a path.
# Model: Claude Opus 5.5 (the P4 phase fixer), 2026-10-15. Status:
# unreviewed. The two faces and their licenses ship in board/fonts/, so the
# page asks no other host (D26).
STATIC_FILES = {
    "live.html": "text/html; charset=utf-8",
    "look.js": "text/javascript; charset=utf-8",
    "theme.css": "text/css; charset=utf-8",
    "demo.html": "text/html; charset=utf-8",
    "demo-script.json": "application/json; charset=utf-8",
    "compare.html": "text/html; charset=utf-8",
    "fonts/space-grotesk-latin-wght-normal.woff2": "font/woff2",
    "fonts/space-grotesk-latin-ext-wght-normal.woff2": "font/woff2",
    "fonts/jetbrains-mono-latin-wght-normal.woff2": "font/woff2",
    "fonts/jetbrains-mono-latin-ext-wght-normal.woff2": "font/woff2",
    "fonts/space-grotesk-ofl.txt": "text/plain; charset=utf-8",
    "fonts/jetbrains-mono-ofl.txt": "text/plain; charset=utf-8",
}
# Each allowed file's path, built from its key once, here.
STATIC_PATHS = {name: BOARD_DIR / name for name in STATIC_FILES}
FEED_TYPE = "application/json; charset=utf-8"
# Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
# The longest one request may take, start to end: reading its request line
# and headers and writing the answer. The page's requests take milliseconds.
# A socket timeout alone restarts on every byte, so a client that trickles
# one byte at a time would hold its thread for good; this deadline ends it.
REQUEST_DEADLINE_S = 10
# Connections served at once. The page keeps one request out at a time
# (look.js createPoller) and a browser opens at most six to one host. One
# past this is closed at once, so a local process cannot pile up threads.
MAX_CONNECTIONS = 16

# tc's message file name: NNNNNN-from-<sender>.md, tc's SEQ_WIDTH digits
# (more past 999999). The .tmp sibling a send writes first never matches.
MESSAGE_NAME = re.compile(r"^(\d+)-from-(.+)\.md$")
INBOX_PREFIX = "to-"
READ_FOLDER = "read"
CARDS_FOLDER = "cards"
CARD_SUFFIX = ".json"
STATUS_SUFFIX = ".md"
# The first line tc's `status` writes: "## <name> status, <time>".
STATUS_HEADER = re.compile(r"^## \S+ status, ")
# C1: no card means route local.
DEFAULT_ROUTE = "local"
ROUTE_CODEX = "codex"
ROUTE_SSH = "ssh"
KIND_CLAUDE = "claude"
# Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
# The account C1 writes when neither --account nor CLAUDE_CONFIG_DIR names
# one. Two cards on it share no known account, so they get no native link
# (D15): the link would claim a shared account that no card knows.
ACCOUNT_UNKNOWN = "unknown"

# C5's states, in the order the first match wins (D15, D24).
WRITING, DOWN, WOKEN, WORKING, LISTENING, DOORBELL, REMOTE, IDLE = (
    "writing", "down", "woken", "working", "listening", "doorbell", "remote", "idle")
ORCHESTRATOR, WORKER, PEER = "orchestrator", "worker", "peer"
# C5 rule 4's role_source words. NO_EDGE is a peer's (D27): no parent edge
# decided its role, so it is no guess and never reads `inferred`.
DECLARED, INFERRED, NO_EDGE = "declared", "inferred", "none"
LINK_MAILBOX, LINK_REPORTS_TO, LINK_NATIVE = "mailbox", "reports_to", "native"

# One message, from its file name alone; `read` when it lies in read/.
Message = collections.namedtuple("Message", "seq sender to path read")


# Model: Claude Opus 5.5 (the P3 fixer, round 1c), 2026-10-15. Status: unreviewed.
class MessagePath(str):
    """A message's path as text that also carries the open folder its name is in (`folder_fd`) and that name (`entry`), so file_age and file_time date the file the scan listed, by its name in that folder, never by the path.

    Round 1a's MEDIUM, from its handoff (D35): an inbox's owner who swaps
    the inbox after the scan could make the board date a same-named file
    at the link's target. The text is the path, so a name taken from it
    (os.path.basename), and anything that prints or compares it, are as
    before. `folder_fd` is valid only while the scan's `held` stack is
    open (scan_messages); feed() dates every message inside it.

    @interacts  none; holds a descriptor number, never opens or closes it.
    @deps       none.
    @complexity O(p) over p characters of the path, to build.
    @alloc      the string and two attributes.
    """

    def __new__(cls, path, folder_fd, entry):
        """The path `path`, carrying `folder_fd` and `entry`.

        @interacts  none.
        @deps       none.
        @complexity O(p) over p characters.
        @alloc      one string object, returned.
        """
        made = super().__new__(cls, path)
        made.folder_fd, made.entry = folder_fd, entry
        return made


def load_tc(root=None):
    """Load ../tc as a module without running main(), from its source alone.

    tc fixes five paths at import, from TC_ROOT: ROOT, MAIL, STATUS,
    SEQ_FILE and CARDS. With `root` given, TC_ROOT is set to it for the
    load and put back after, so the module points at `root` and the
    process's environment is unchanged. With `root` None, tc reads TC_ROOT
    as it stands (or its own folder).

    tc's source is read and compiled in memory and run in a fresh module,
    so no bytecode cache beside tc is read or written. An import would
    trust a cache by its header alone (the source's mtime and size, which
    anyone can read), and on a group-writable ROOT another user could plant
    one for the board to run as its own user.

    @interacts  reads ../tc's source; reads and restores
                os.environ["TC_ROOT"]; executes tc's top level (imports and
                constants; tc's main() is not run). Writes no file.
    @deps       types; ../tc.
    @complexity O(s) over s bytes of tc's source: one compile.
    @alloc      the source, freed on return; one module object, returned;
                the caller holds it.
    """
    code = compile(TC_PATH.read_bytes(), str(TC_PATH), "exec", dont_inherit=True)
    tc = types.ModuleType("tc")
    tc.__file__ = str(TC_PATH)
    old = os.environ.get("TC_ROOT")
    if root is not None:
        os.environ["TC_ROOT"] = str(root)
    try:
        exec(code, tc.__dict__)
    finally:
        if root is not None:
            if old is None:
                os.environ.pop("TC_ROOT", None)
            else:
                os.environ["TC_ROOT"] = old
    return tc


# Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
def machine_now():
    """C5's machine keys right now: load1, cores and mem_avail_pct.

    The same numbers and rounding as tc's machine_stats, without its GPU
    query: machine_stats runs nvidia-smi, which may take up to tc's
    GPU_QUERY_TIMEOUT_SECONDS, and the feed has no GPU key.

    @interacts  reads the load average and /proc/meminfo.
    @deps       os.
    @complexity O(1): one short /proc file.
    @alloc      one small dict, returned.
    """
    info = {}
    with open(MEMINFO_PATH) as meminfo:
        for line in meminfo:
            key, _, rest = line.partition(":")
            fields = rest.split()
            if fields and fields[0].isdigit():
                info[key] = int(fields[0])
    return {"load1": round(os.getloadavg()[0], LOAD_ROUND_DIGITS), "cores": os.cpu_count() or 1,
            "mem_avail_pct": round(PERCENT * info["MemAvailable"] / info["MemTotal"], MEM_PCT_ROUND_DIGITS)}


def read_regular(path, limit):
    """Up to `limit` bytes of `path` when it is a regular file, else None.

    Opened with O_NONBLOCK and O_NOFOLLOW, and checked with fstat before
    any read: a FIFO never blocks the feed (which holds feed_lock), and a
    symlink never points the board at a file outside the mailbox. Anything
    that is not a regular file, or cannot be opened or read, is None.

    @interacts  opens, fstats and reads one file, and closes it.
    @deps       os, stat.
    @complexity O(limit).
    @alloc      the bytes read, returned.
    """
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    except OSError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return None
        chunks, left = [], limit
        while left > 0:
            chunk = os.read(fd, left)
            if not chunk:
                break
            chunks.append(chunk)
            left -= len(chunk)
        return b"".join(chunks)
    except OSError:
        return None
    finally:
        os.close(fd)


def read_cards(folder, on_nested=None):
    """Every card in `folder` (cards/ under ROOT), as {name: fields}.

    The name is the file's stem (C1: cards/<name>.json). A file that is not
    a regular file (read_regular), is not a JSON object, is unreadable, or
    is over CARD_READ_MAX_BYTES is skipped: the board draws what it can. A
    file nested past Python's recursion limit is skipped too, and its file
    name goes to on_nested(name) when given. Only the fields the feed uses
    are kept, each checked for type: kind, account, route (default
    "local"), reports_to (a non-empty string, else None).

    @interacts  lists `folder`; reads each *.json in it, at most
                CARD_READ_MAX_BYTES + 1 bytes each; calls on_nested.
    @deps       json, pathlib; read_regular, card_text.
    @complexity O(c) over c card files (one per name, tens at most).
    @alloc      one small dict per card, returned.
    """
    cards = {}
    try:
        paths = sorted(folder.glob(f"*{CARD_SUFFIX}"))
    except OSError:
        return cards
    for path in paths:
        raw = read_regular(path, CARD_READ_MAX_BYTES + 1)
        if raw is None or len(raw) > CARD_READ_MAX_BYTES:
            continue
        try:
            card = json.loads(raw)
        except ValueError:
            continue
        except RecursionError:
            if on_nested is not None:
                on_nested(path.name)
            continue
        if not isinstance(card, dict):
            continue
        cards[path.stem] = {"kind": card_text(card, "kind"), "account": card_text(card, "account"),
                            "route": card_text(card, "route") or DEFAULT_ROUTE,
                            "reports_to": card_text(card, "reports_to")}
    return cards


def card_text(card, key):
    """card[key] when it is a non-empty string, else None.

    @interacts  none; pure.
    @deps       none.
    @complexity O(1).
    @alloc      none.
    """
    value = card.get(key)
    return value if isinstance(value, str) and value else None


def scan_messages(mail, held):
    """Every message under `mail`, from file names only: ([Message], {names whose inbox could not be listed}).

    Looks in each mail/to-<name>/ and its read/. A name that does not match
    MESSAGE_NAME (a .tmp being written, a lock, anything else) is skipped.
    A to-* entry or read/ the board cannot open (a folder the user may not
    read or search, a dead mount) is skipped on its own and its name goes
    in the second set, and so does a name whose inbox or read/
    message_names could not list; the rest of the scan stands. Opens no
    file, only folders.

    Never follows a link, so a link a group member puts in a shared
    mailbox points the board nowhere: a to-* entry or
    a read/ that is a link is not looked in, and only a regular file is a
    message (message_names). The inbox is listed before read/, and a file
    in read/ with the same recipient, number and sender as one in the inbox
    (a `tc read` moved it between the two listings, or a hand-made twin)
    counts once, as the inbox copy: a file put in read/ cannot hide or
    stand in for unread mail. Two files with one number and two senders are
    two messages.

    Model: Claude Opus 5.5 (the P3 fixer, round 1a), 2026-10-15. Status:
    unreviewed. D35, one pinned handle per inbox (the audit's HIGH-1 and
    its Coverage note on this scan). mail/ is opened once, each inbox by
    its name in mail/'s descriptor and its read/ by its name in the
    inbox's (open_folder), and each is listed in its own descriptor
    (message_names), never by a path. So an inbox's owner who swaps it for
    a link or another folder after the scan opened it leads the scan
    nowhere: the read/ listed is the one in the folder opened.

    Model: Claude Opus 5.5 (the P3 fixer, round 1c), 2026-10-15. Status:
    unreviewed. Round 1a's MEDIUM: each inbox and read/ descriptor is
    kept open in `held` (a contextlib.ExitStack the caller holds open
    until it has dated every message, as feed() does), and a Message's
    path is a MessagePath carrying its folder's descriptor and its name.
    So file_age and file_time date each message by its name in the
    folder the scan listed, never through a link or a folder swapped in
    after the scan.

    @interacts  opens and lists `mail`; opens each to-*/ folder by name in
                it and each to-*/read/ by name in its inbox, lists each,
                closes mail/'s descriptor and leaves the others to `held`.
    @deps       os, re; open_folder, message_names; MAIL_FLAGS,
                INBOX_PREFIX, READ_FOLDER, MESSAGE_NAME, Message,
                MessagePath.
    @complexity O(b log b + m) over b inbox folders (sorted) and m file
                names in them.
    @alloc      one Message per message file, in a dict by recipient,
                number and sender, returned as a list; one set of names;
                mail/'s descriptor, closed before return; one descriptor
                per inbox and per read/ (two per name, a few dozen names),
                closed when `held` closes.
    """
    try:
        mail_fd = os.open(mail, MAIL_FLAGS)
    except OSError:
        return [], set()
    found, unreadable = {}, set()
    try:
        try:
            entries = sorted(name for name in os.listdir(mail_fd) if name.startswith(INBOX_PREFIX))
        except OSError:
            return [], set()
        for entry in entries:
            to = entry[len(INBOX_PREFIX):]
            if not to:
                continue
            try:
                box_fd = open_folder(mail_fd, entry)
            except OSError:
                unreadable.add(to)  # a folder this board cannot open (C5: down, `inbox unreadable`)
                continue
            if box_fd is None:
                continue
            held.callback(os.close, box_fd)  # P3 fix round 1c: open until the caller has dated its messages
            folders = [(box_fd, os.path.join(mail, entry), False)]
            try:
                read_fd = open_folder(box_fd, READ_FOLDER)
            except OSError:
                read_fd = None
                unreadable.add(to)
            if read_fd is not None:
                held.callback(os.close, read_fd)
                folders.append((read_fd, os.path.join(mail, entry, READ_FOLDER), True))
            for folder_fd, folder, read in folders:
                names = message_names(folder_fd)
                if names is None:
                    unreadable.add(to)
                    continue
                for name in names:
                    match = MESSAGE_NAME.match(name)
                    msg = Message(int(match.group(1)), match.group(2), to,
                                  MessagePath(os.path.join(folder, name), folder_fd, name), read)
                    found.setdefault((to, msg.seq, msg.sender), msg)
    finally:
        os.close(mail_fd)
    return list(found.values()), unreadable


# Model: Claude Opus 5.5 (the P3 fixer, round 1a), 2026-10-15. Status: unreviewed.
def open_folder(folder_fd, name):
    """The descriptor of the folder `name` in the folder open at `folder_fd`, opened by its name and never through a link (FOLDER_FLAGS); None for a link, nothing or not a folder (NO_FOLDER_ERRNOS). Raises OSError for a folder it cannot open: the board cannot tell what it holds.

    @interacts  opens one folder by its name in `folder_fd`.
    @deps       os; FOLDER_FLAGS, NO_FOLDER_ERRNOS.
    @complexity O(1).
    @alloc      one descriptor, returned (the caller closes it), or none.
    """
    try:
        return os.open(name, FOLDER_FLAGS, dir_fd=folder_fd)
    except OSError as error:
        if error.errno in NO_FOLDER_ERRNOS:
            return None
        raise


# Model: Claude Opus 5.5 (the P4 phase fixer), 2026-10-15. Status: unreviewed.
def message_names(folder_fd):
    """The names of the regular files in the folder open at `folder_fd` that match MESSAGE_NAME; None when it cannot be listed.

    Listed through the descriptor, so the folder listed is the one opened
    (open_folder), never one a link at its name leads to, and an entry
    counts only when it is a regular file itself, never a link to one. A
    failure to list (a folder another user left closed to this one) is
    None: the board cannot tell what the folder holds. P3 fix round 1a
    (Claude Opus 5.5, unreviewed): D35. It takes the open descriptor, not
    a path: the caller opens each folder by its name in the one above.

    @interacts  lists one open folder; never closes it.
    @deps       os, re; MESSAGE_NAME.
    @complexity O(f) over f entries in the folder.
    @alloc      one list of names, returned.
    """
    try:
        with os.scandir(folder_fd) as entries:
            return [entry.name for entry in entries
                    if MESSAGE_NAME.match(entry.name) and entry.is_file(follow_symlinks=False)]
    except OSError:
        return None


def status_preview(folder, name):
    """The status line C5 shows for `name`, or None when there is none.

    The first non-empty line of status/<name>.md that is not tc's header
    line, cut at STATUS_PREVIEW_CHARS. A status path that is not a regular
    file (a FIFO, a symlink, a folder) shows no status (read_regular).

    @interacts  reads at most STATUS_READ_MAX_BYTES of status/<name>.md.
    @deps       re; read_regular.
    @complexity O(s) over s <= STATUS_READ_MAX_BYTES bytes read.
    @alloc      the bytes read and one short string, returned.
    """
    raw = read_regular(folder / f"{name}{STATUS_SUFFIX}", STATUS_READ_MAX_BYTES)
    if raw is None:
        return None
    lines = raw.decode("utf-8", "replace").splitlines()
    if lines and STATUS_HEADER.match(lines[0]):
        lines = lines[1:]
    for line in lines:
        if line.strip():
            return line.strip()[:STATUS_PREVIEW_CHARS]
    return None


# Model: Claude Opus 5.5 (the P3 fixer, round 1c), 2026-10-15. Status: unreviewed.
def stat_at(path):
    """The lstat result of `path`, never following a link: for a MessagePath, by its name in the open folder it carries (dir_fd), never by the path. Raises OSError.

    Round 1a's MEDIUM (D35): the board's ages and times of a message come
    from the folder the scan opened and listed, so an inbox swapped for a
    link or another folder after the scan dates nothing outside it. Any
    other path (a status file) is lstat()ed by its path.

    @interacts  lstats one name.
    @deps       os; MessagePath.
    @complexity O(1).
    @alloc      one stat result, returned.
    """
    if isinstance(path, MessagePath):
        return os.stat(path.entry, dir_fd=path.folder_fd, follow_symlinks=False)
    return os.stat(path, follow_symlinks=False)


def file_age(path, now):
    """Whole seconds since `path` was last written, or None if it is gone.

    A message read between the scan and this stat moved to read/; its age
    is None for this poll and right on the next. An mtime ahead of `now`
    (a touched file, or a clock stepped back) is no age at all: None, so a
    message from the future never reads as just sent. Rounding gives half a
    second of grace to a file written in the same instant as `now`.

    P3 fix round 1c (Claude Opus 5.5, unreviewed): round 1a's MEDIUM. A
    message is stat'ed by its name in the folder the scan holds open
    (stat_at), and a link is never followed.

    @interacts  lstats one name (stat_at); never opens it.
    @deps       stat_at.
    @complexity O(1).
    @alloc      none.
    """
    try:
        age = round(now - stat_at(path).st_mtime)
    except OSError:
        return None
    return age if age >= 0 else None


# Model: Claude Opus 5.5 (the P4 phase fixer), 2026-10-15. Status: unreviewed.
def file_time(path):
    """`path`'s mtime, seconds since the epoch, or None when it is gone. Never follows a link.

    P3 fix round 1c (Claude Opus 5.5, unreviewed): round 1a's MEDIUM. A
    message is stat'ed by its name in the folder the scan holds open
    (stat_at); a status file by its path.

    @interacts  lstats one name (stat_at); never opens it.
    @deps       stat_at.
    @complexity O(1).
    @alloc      none.
    """
    try:
        return stat_at(path).st_mtime
    except OSError:
        return None


# Model: Claude Opus 5.5 (the P4 phase fixer, round 2), 2026-10-15. Status: unreviewed.
def find_wake(candidates, since, until):
    """D24 and D28: (the earliest mtime, the file names) of the candidates that landed from `since` to `until`; (None, empty) for none.

    `tc wait` exits when mail lands, and a session re-arms only after its
    turn, so a lock that went away is not always a listener lost. The name
    was woken by a message that reached its inbox no earlier than `since`
    (tc's POLL_SECONDS before the board last saw it listening: a wait sees
    new mail up to one of its polls late, and the board may see its pid in
    that time) and no later than `until` (POLL_SECONDS after the first poll
    that found no pid): mail that lands after the board has seen the
    listener gone woke nothing (D28).

    `candidates` is the name's newest messages by number (WAKE_CANDIDATES
    at most). Each is lstatted, and the walk runs in file time order,
    newest first: a message past `until` is passed over, and the first one
    before `since` ends the walk, since every one after it in that order is
    older still. A number decides nothing here, so a hand-made file with a
    high number and an old time cannot end the walk early. A message gone
    between the scan and its lstat (a read moved it) is skipped this poll.

    @interacts  lstats each candidate; opens none.
    @deps       os; file_time.
    @complexity O(K log K) over the K <= WAKE_CANDIDATES candidates, plus K
                lstats.
    @alloc      one list of K (time, message) pairs and the returned set of
                names.
    """
    timed = []
    for msg in candidates:
        when = file_time(msg.path)
        if when is not None:
            timed.append((when, msg))
    timed.sort(key=lambda pair: pair[0], reverse=True)
    wake, names = None, set()
    for when, msg in timed:
        if when > until:
            continue
        if when < since:
            break
        wake = when
        names.add(os.path.basename(msg.path))
    return wake, names


# Model: Claude Opus 5.5 (the P4 phase fixer), 2026-10-15; the evidence by
# the P4 phase fixer, round 2. Status: unreviewed.
def after_listening(seen, now, wake, waking, inbox, sent, status_path):
    """D24: DOWN, WOKEN or WORKING for a name seen listening at `seen` and not listening now.

    `wake` is the mtime of the earliest message that woke it, or None, and
    `waking` those messages' file names (find_wake, kept by the Board).
    Not woken: DOWN, the lock vanished and nothing woke it. Woken, it is
    WORKING when it shows life after `seen` (a message that woke it has
    left the inbox: `inbox` is the file names in mail/to-<name>/ now, so
    where the message went, read/ under its own name or another, does not
    matter; or its status file or the message it sent last is newer than
    `seen`), or while the wake is at most WOKEN_GRACE_S old; else WOKEN.

    @interacts  lstats its status file and the message it sent last; opens
                none.
    @deps       file_time.
    @complexity O(w) over the w <= WAKE_CANDIDATES waking names (one or
                two), plus two lstats.
    @alloc      none.
    """
    if wake is None:
        return DOWN
    left = any(name not in inbox for name in waking)
    stamps = (file_time(status_path), file_time(sent.path) if sent else None)
    if left or any(at is not None and at > seen for at in stamps) or now - wake <= WOKEN_GRACE_S:
        return WORKING
    return WOKEN


def parents_of(names, cards, partners):
    """C5 rule 2: {name: (parent, DECLARED or INFERRED)} for each node with one.

    `partners` is {name: {partner: messages}}: how many messages each pair
    exchanged, both ways counted, a name's own notes left out. Declared:
    the card's reports_to, when it names a node other than the node
    itself. A reports_to that names no node (or itself) gives no parent,
    and nothing is inferred over it. Inferred, when nothing is declared
    (D27): the partner holding at least PARENT_MAJORITY of the node's
    messages, when that partner is a node with HUB_MIN_PARTNERS or more
    partners and its card does not report to this node (D15: an inferred
    edge never runs against a declared one, whatever order the names sort
    in). No partner holding that share, as with a node split evenly between
    two relays: no guess.

    @interacts  none; pure.
    @deps       fractions (PARENT_MAJORITY).
    @complexity O(n + p) over n names and p partner entries (two per
                pair that exchanged mail): each node's counts summed and
                walked once.
    @alloc      the returned dict, one entry per node with a parent.
    """
    found = {}
    for name in names:
        declared = cards.get(name, {}).get("reports_to")
        if declared is not None:
            if declared in names and declared != name:
                found[name] = (declared, DECLARED)
            continue
        mine = partners.get(name, {})
        total = sum(mine.values())
        for partner, count in mine.items():
            if count < PARENT_MAJORITY * total:
                continue
            if (partner in names and len(partners.get(partner, ())) >= HUB_MIN_PARTNERS
                    and cards.get(partner, {}).get("reports_to") != name):
                found[name] = (partner, INFERRED)
            break
    return found


# Model: Claude Opus 5.5 (the P4 phase fixer), 2026-10-15. Status: unreviewed.
def drop_inferred_cycles(parents):
    """`parents` with every inferred edge that sits on a cycle taken out.

    Rule 2's D15 guard looks one hop only, so an inferred parent can close
    a loop through a chain of declared ones: zed inferred under alpha,
    while alpha reports to mid and mid to zed by card. A cycle that holds an
    inferred edge loses every inferred edge on it, so the cards decide the
    shape whatever order the names sort in, and no badge names a cycle no
    card makes. A cycle made only of declared edges is left whole:
    levels_of breaks it at the name that sorts first. Each node has at most
    one parent, so cycles never share a node, and taking edges out makes
    no new one: one pass is enough.

    @interacts  none; pure.
    @deps       none.
    @complexity O(n) over n nodes with a parent: each is walked once.
    @alloc      the returned dict, one entry per edge kept; one walk list
                and two sets, freed on return.
    """
    done, cycles = set(), []
    for start in sorted(parents):
        path, on_path = [], set()
        at = start
        while at in parents and at not in done and at not in on_path:
            on_path.add(at)
            path.append(at)
            at = parents[at][0]
        if at in on_path:
            cycles.append(path[path.index(at):])
        done.update(path)
    kept = dict(parents)
    for cycle in cycles:
        if any(parents[name][1] == INFERRED for name in cycle):
            for name in cycle:
                if parents[name][1] == INFERRED:
                    del kept[name]
    return kept


# Model: Claude Opus 5.5 (the P4 phase fixer), 2026-10-15. Status: unreviewed.
def hierarchy(names, cards, partners):
    """C5 rules 2 to 5 in one call: (parents, roles, levels).

    parents is parents_of's map less every inferred edge on a cycle
    (drop_inferred_cycles), and roles_of and levels_of both read that one
    map, so an edge taken out leaves no role behind it.

    @interacts  none; pure.
    @deps       parents_of, drop_inferred_cycles, roles_of, levels_of.
    @complexity O(n + p + e) over n names, p partner entries and e parent
                edges.
    @alloc      the three returned dicts and their helpers' working sets.
    """
    parents = drop_inferred_cycles(parents_of(names, cards, partners))
    return parents, roles_of(names, parents), levels_of(names, parents)


def roles_of(names, parents):
    """C5 rules 3 and 4: {name: (role, role_source)}.

    orchestrator: one or more nodes have it as parent; declared when every
    one of those edges is. worker: it has a parent and no children; the
    source is that edge's. peer: neither; NO_EDGE (`none`, D27), since no
    edge decided it and a peer is no guess.

    @interacts  none; pure.
    @deps       none.
    @complexity O(n + e) over n names and e parent edges.
    @alloc      the returned dict and one list of edge sources per parent.
    """
    child_sources = {}
    for parent, source in parents.values():
        child_sources.setdefault(parent, []).append(source)
    roles = {}
    for name in names:
        if name in child_sources:
            every = all(source == DECLARED for source in child_sources[name])
            roles[name] = (ORCHESTRATOR, DECLARED if every else INFERRED)
        elif name in parents:
            roles[name] = (WORKER, parents[name][1])
        else:
            roles[name] = (PEER, NO_EDGE)
    return roles


def levels_of(names, parents):
    """C5 rule 5: {name: level}, every node exactly once, ending on any cycle.

    Roots (no parent) are level 0; a breadth-first walk runs down parent to
    child. A node still unreached sits on or below a cycle of parent edges:
    from the first-sorted unreached node, follow parents until one repeats,
    and the cycle member whose name sorts first becomes a root at level 0;
    the walk runs again from it. Repeat until every node has a level.

    @interacts  none; pure.
    @deps       collections.
    @complexity O(n + e) over n names and e parent edges: each node is
                levelled once, and a climb to a cycle only crosses nodes the
                next walk then levels.
    @alloc      the returned dict, one child list per parent, one queue and
                one climb record, freed on return.
    """
    order = sorted(names)
    children = {}
    for name in order:
        if name in parents:
            children.setdefault(parents[name][0], []).append(name)
    level = {}

    def walk(root):
        """Level `root` at 0 and every node below it not yet levelled, breadth first.

        @interacts  writes `level`; reads `children`.
        @deps       collections.
        @complexity O(k) over k nodes newly levelled.
        @alloc      one queue, freed on return.
        """
        level[root] = 0
        queue = collections.deque([root])
        while queue:
            at = queue.popleft()
            for child in children.get(at, ()):
                if child not in level:
                    level[child] = level[at] + 1
                    queue.append(child)

    for name in order:
        if name not in parents:
            walk(name)
    for name in order:
        if name in level:
            continue
        seen = set()
        at = name
        while at not in seen:
            seen.add(at)
            at = parents[at][0]
        cycle = [at]
        step = parents[at][0]
        while step != at:
            cycle.append(step)
            step = parents[step][0]
        walk(min(cycle))
    return level


class Board:
    """The feed's state across polls: the loaded tc, who was seen listening, when each was first seen gone, and what woke it.

    `clock` returns seconds since the epoch, as time.time does; tests pass a
    fake one so windows can be crossed without waiting. feed() is not safe
    from two threads at once; BoardServer calls it under its own lock.

    F1 (Claude Opus 5.5, unreviewed): C5's wait exit record. Each poll
    reads the record of every name with no pid afresh (tc.wait_exits) and
    keeps none of it, so a restart loses nothing the record says: a name
    whose record says `listening` (its wait was killed or crashed) reads
    `down` on a fresh Board and stays `down` past DOWN_WINDOW_S, until a
    pid holds its lock again (`writing` still comes first, as C5 orders
    it); one whose record says `mail` or `timeout`,
    dated after this Board last saw its lock (any date on a fresh Board),
    is never `down` (stopped_state). The memory above still decides
    `woken` and `working`, and every state with no record. The record is
    never proof of life: `listening` comes from a pid alone. F1 fix round
    1 (Claude Opus 5.5, unreviewed): a node `down` by its record carries
    down_age_s (down_age), from this Board's last sighting of its lock
    when it has one, else from the record's time.

    @interacts  see the module block; each poll also opens each stopped
                name's inbox and reads its exit record (tc.wait_exits),
                and lists the locks again when one says `listening` (F1
                fix round 1).
    @deps       load_tc and the module's helpers; stopped_state,
                down_age, tc.wait_exits, tc.left_on_purpose (F1);
                tc.listeners again (F1 fix round 1).
    @complexity O(1) to build, plus one load of tc.
    @alloc      the tc module, last_listening_at, first_missing_at, wakes
                and nested_cards, held for the object's life (the module
                block bounds each); nothing from the exit records is
                held across polls (F1).
    """

    def __init__(self, root=None, clock=time.time):
        """Load tc for `root` (or TC_ROOT as it stands) and start with no history.

        @interacts  load_tc(root).
        @deps       load_tc.
        @complexity O(1).
        @alloc      the tc module, three empty dicts and one empty set.
        """
        self.tc = load_tc(root)
        self.clock = clock
        self.last_listening_at = {}
        # Model: Claude Opus 5.5 (the P4 phase fixer, round 2), 2026-10-15.
        # Status: unreviewed. D28: the first poll that found no pid for a
        # name seen listening, and the wake found for it, until its next
        # sighting.
        self.first_missing_at = {}
        self.wakes = {}
        self.nested_cards = set()

    # Model: Claude Opus 5.5 (the P4 phase fixer, round 2), 2026-10-15. Status: unreviewed.
    def wake_of(self, name, now, candidates):
        """The wake kept for `name`, a stopped listener: {"at", "names", "settled"} (D24, D28).

        While the wake window is open (until POLL_SECONDS past the first
        poll that found no pid), each poll looks for the wake in
        `candidates` (find_wake) and adds what it finds to what earlier
        polls found, so a waking message that a read later moves out of the
        board's sight (a name MESSAGE_NAME does not match) stays known. The
        first poll past the window looks once more and settles it: no mail
        that lands later can be a wake, so later polls look for none.

        @interacts  updates wakes[name]; lstats the candidates (find_wake).
        @deps       find_wake; tc.POLL_SECONDS.
        @complexity find_wake's while the window is open, else O(1).
        @alloc      one small dict per stopped name, held until its next
                    sighting or the prune.
        """
        wake = self.wakes.setdefault(name, {"at": None, "names": set(), "settled": False})
        if wake["settled"]:
            return wake
        until = self.first_missing_at[name] + self.tc.POLL_SECONDS
        at, names = find_wake(candidates, self.last_listening_at[name] - self.tc.POLL_SECONDS, until)
        if at is not None:
            wake["at"] = at if wake["at"] is None else min(wake["at"], at)
            wake["names"] |= names
        wake["settled"] = now > until
        return wake

    # Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
    def note_nested(self, file_name):
        """Write one stderr line the first time a card file nests past the recursion limit.

        feed() skips such a card on every poll, never answering 500 for it;
        the line names the file once per Board, so a poll every 3 s does
        not repeat it. The name is printed escaped (repr), since anyone who
        can write to cards/ chooses it.

        @interacts  writes one line to stderr, the first time per file name.
        @deps       sys.
        @complexity O(1).
        @alloc      one string per distinct file name, held for the Board's
                    life (bounded by the files ever put in cards/).
        """
        if file_name in self.nested_cards:
            return
        self.nested_cards.add(file_name)
        # repr() escapes any control character in the name, so a planted
        # file name cannot write escape sequences to this terminal.
        print(f"serve.py: skipped {'cards/' + file_name!r}: nested past Python's recursion limit",
              file=sys.stderr, flush=True)

    # Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
    def snapshot(self):
        """The parts of tc's health the feed reads: time, machine, listeners, mail.

        Built from tc.now_iso(), machine_now(), tc.listeners("wait") and
        tc.mailbox_summary(), in tc.health_snapshot()'s shape, instead of
        calling tc.health_snapshot(), which also runs nvidia-smi (up to
        tc's GPU_QUERY_TIMEOUT_SECONDS), scans every process and, on the
        merged tc, reads every card: none of which the feed uses.

        The retry serves the dev branch's tc before SHARED merges: there a
        `tc read` that moves a message between mailbox_summary's glob and
        its stat makes it raise FileNotFoundError. It is asked once more,
        and finds the message in read/; a second miss raises, and that poll
        answers 500. SHARED's tc skips an entry that vanished before its
        stat, so with it the retry never runs and costs nothing, and the
        stand-in test of it says nothing about that tc.

        @interacts  see the module block: /proc/locks, the lock files, mail/
                    and status/ through tc; the load average and
                    /proc/meminfo through machine_now.
        @deps       tc.now_iso, tc.listeners, tc.mailbox_summary;
                    machine_now.
        @complexity O(k + n log n + M + m log m): k lines in /proc/locks, n
                    names, M names listed in every inbox and read/ and the m
                    message files among them (tc.listeners and
                    tc.mailbox_summary, by their own @complexity; P3 fix
                    round 2, Claude Opus 5.5, unreviewed: the audit's
                    LOW-6). The mailbox part runs once: this tc never
                    raises for a message that moved mid-poll, so the
                    retry never runs (P3 fix round 3, Claude Opus 5.5,
                    unreviewed: the audit's LOW-7).
        @alloc      one dict, returned.
        """
        try:
            mail = self.tc.mailbox_summary()
        except FileNotFoundError:
            mail = self.tc.mailbox_summary()
        return {"time": self.tc.now_iso(), "machine": machine_now(),
                "listeners": self.tc.listeners("wait"), "mail": mail}

    def feed(self):
        """One C5 feed object for the mailbox as it is now.

        @interacts  see the module block; updates last_listening_at,
                    first_missing_at, wakes and, through note_nested,
                    nested_cards; reads each name with no pid's wait exit
                    record (tc.wait_exits; F1); when one says `listening`,
                    lists the locks once more (tc.listeners; F1 fix round
                    1) and takes a pid found then.
        @deps       snapshot, read_cards, scan_messages, feed_from (P3 fix
                    round 1c: status_preview, file_age, wake_of,
                    after_listening, hierarchy; F1: stopped_state),
                    note_nested, tc.wait_exits, tc.listeners and
                    tc.WAIT_EXIT_LISTENING (F1 fix round 1); contextlib,
                    heapq, os;
                    tc.POLL_SECONDS.
        @complexity O(k + m (log W + log K) + n + c^2 + g log g) per poll;
                    the module block names each term (a second
                    tc.listeners, O(k + n log n), on a poll where a name
                    with no pid has a `listening` record: F1 fix round 1).
        @alloc      the scan's two descriptors per name, closed before
                    return (P3 fix round 1c); the per-poll objects the module block lists (a Message,
                    a sorted pair and a default count dict per message
                    among them, and a heap and an inbox name set per name
                    that stopped listening), and the returned dict;
                    last_listening_at gains one float per name listening
                    now, first_missing_at one per name that stopped, wakes
                    one small dict per stopped name; a sighting drops a
                    name from the last two, and the prune past
                    DOWN_WINDOW_S from all three.
        """
        now = self.clock()
        snap = self.snapshot()
        pids = snap["listeners"]
        # Model: Claude Opus 5.5 (the F1 lane agent), 2026-10-16. Status:
        # unreviewed. C5's wait exit record of each name with no pid now,
        # through tc's one reader (wait_exits); never a listener.
        exits = self.tc.wait_exits([name for name, pid in pids.items() if not pid])
        # F1 fix round 1 (Claude Opus 5.5, unreviewed): the audit's LOW-3. A
        # session that re-armed between the lock listing and the record read
        # holds its lock and wrote its own `listening`: look at the locks once
        # more for each such name, and a name held now is listening, not down.
        rearmed = [name for name, record in exits.items() if record.word == self.tc.WAIT_EXIT_LISTENING]
        if rearmed:
            again = self.tc.listeners("wait")
            for name in rearmed:
                if again.get(name):
                    pids[name] = again[name]
                    del exits[name]
        for name, pid in pids.items():
            if pid:
                self.last_listening_at[name] = now
                self.first_missing_at.pop(name, None)
                self.wakes.pop(name, None)
        for name, seen in list(self.last_listening_at.items()):
            if now - seen > DOWN_WINDOW_S:
                del self.last_listening_at[name]
                self.first_missing_at.pop(name, None)
                self.wakes.pop(name, None)
            elif not pids.get(name):
                # D28: the first poll that finds no pid after a sighting.
                self.first_missing_at.setdefault(name, now)

        cards =read_cards(self.tc.ROOT / CARDS_FOLDER, self.note_nested)
        # P3 fix round 1c (Claude Opus 5.5, unreviewed): round 1a's MEDIUM. The
        # scan's folders stay open until every message is dated in them.
        with contextlib.ExitStack() as held:
            messages, unreadable = scan_messages(self.tc.MAIL, held)
            return self.feed_from(now, snap, cards, messages, unreadable, exits)

    # Model: Claude Opus 5.5 (the F1 lane agent), 2026-10-16. Status: unreviewed.
    def stopped_state(self, name, now, record, unreadable, candidates, inbox, sent):
        """DOWN, WOKEN, WORKING or None for `name`, a name with no pid now: C5's rules for a listener gone, with its wait exit record `record` (a WaitExit, or None for no record).

        - `record` says `listening`: the wait was killed or crashed, so
          DOWN, whether or not this Board saw it listening (after a
          restart too, and past DOWN_WINDOW_S: nothing it can see ends a
          killed listener's down but its name listening again).
        - Seen listening within DOWN_WINDOW_S: the D24 and D28 rules, as
          before F1 (DOWN with `inbox unreadable` where the board cannot
          list the inbox; else after_listening). Then a DOWN becomes None
          when `record` says `mail` or `timeout` dated after the last
          sighting (tc's left_on_purpose): the listener left on purpose,
          and the states after (listening, doorbell, remote, idle) apply.
        - Otherwise None, as before F1: a restart, or a window gone by.

        No record, or one tc's reader would not take, keeps the rules as
        they were. The record is never proof of life: a pid is.

        @interacts  see wake_of and after_listening (lstats of a few
                    messages, the status file and a sent message).
        @deps       wake_of, after_listening; tc.WAIT_EXIT_LISTENING,
                    tc.left_on_purpose, tc.STATUS; DOWN, STATUS_SUFFIX.
        @complexity as wake_of and after_listening: O(K log K) at most,
                    K = WAKE_CANDIDATES.
        @alloc      none beyond wake_of's.
        """
        if record is not None and record.word == self.tc.WAIT_EXIT_LISTENING:
            return DOWN
        if name not in self.last_listening_at:
            return None
        if name in unreadable:
            # C5, D28: the board cannot list the inbox, so it cannot tell.
            state = DOWN
        else:
            wake = self.wake_of(name, now, candidates.get(name, ()))
            state = after_listening(self.last_listening_at[name], now, wake["at"], wake["names"],
                                    inbox.get(name, set()), sent, self.tc.STATUS / f"{name}{STATUS_SUFFIX}")
        if state == DOWN and self.tc.left_on_purpose(record, self.last_listening_at[name]):
            return None
        return state

    # Model: Claude Opus 5.5 (the F1 fixer, round 1), 2026-10-17. Status: unreviewed.
    def down_age(self, name, now, record):
        """Whole seconds since `name`'s listener stopped, as this Board knows it, for a name `down` because its wait exit record `record` says `listening`; None for any other record (C5, "The pill warns only on a fresh stop"; the audit's LOW-1).

        Counted from when this Board last saw the name's lock held, when it
        has (last_listening_at, kept within DOWN_WINDOW_S): the wait
        stopped after that poll. Else from the record's own time: the wait
        wrote `listening` as it took its lock, so it stopped no earlier than
        that, and on a fresh Board a stop may read older than it is, never
        newer. Never the record's time alone while a sighting is known: a
        wait runs for up to DEFAULT_WAIT_SECONDS (110 min), so a kill of
        one that started long ago is still a fresh stop. Never below 0.

        @interacts  none; reads last_listening_at.
        @deps       tc.WAIT_EXIT_LISTENING.
        @complexity O(1).
        @alloc      none.
        """
        if record is None or record.word != self.tc.WAIT_EXIT_LISTENING:
            return None
        return max(0, int(now - self.last_listening_at.get(name, record.at)))

    # Model: Claude Opus 5.5 (the P3 fixer, round 1c), 2026-10-15. Status: unreviewed.
    def feed_from(self, now, snap, cards, messages, unreadable, exits=None):
        """feed()'s object from what it gathered: the time `now`, the snapshot `snap`, the `cards`, the scan's `messages` and `unreadable` names, whose folders the caller holds open while this dates them (file_age, find_wake, after_listening), and `exits`, the wait exit record of each name with no pid (tc's wait_exits; None for none).

        Split out of feed() in P3 fix round 1c so the scan's held folders
        close when this returns, on every way out; the body is feed()'s as
        it was. F1 (Claude Opus 5.5, unreviewed): a name with no pid takes
        its down, woken or working from stopped_state, with its record.
        F1 fix round 1 (Claude Opus 5.5, unreviewed): a down node's
        down_age_s from down_age.

        @interacts  see feed(); stats each dated message by its name in
                    the folder the scan holds (file_age, file_time).
        @deps       see feed(); stopped_state, down_age.
        @complexity see feed().
        @alloc      see feed().
        """
        exits = exits or {}
        pids, mail = snap["listeners"], snap["mail"]
        names = set(mail) | set(cards)

        # Every stopped name's inbox file names (where its waking mail went
        # is evidence it was read), and, while its wake window is open, its
        # newest WAKE_CANDIDATES messages by number, kept as the walk goes.
        inbox = {name: set() for name in self.first_missing_at}
        candidates = {name: [] for name in self.first_missing_at
                      if not self.wakes.get(name, {}).get("settled")}
        sent, newest_pair, newest_sent = {}, {}, {}
        for msg in messages:
            if msg.sender not in newest_sent or msg.seq > newest_sent[msg.sender].seq:
                newest_sent[msg.sender] = msg
            if msg.to in inbox:
                if not msg.read:
                    inbox[msg.to].add(os.path.basename(msg.path))
                heap = candidates.get(msg.to)
                if heap is not None:
                    if len(heap) < WAKE_CANDIDATES:
                        heapq.heappush(heap, msg)
                    else:
                        heapq.heappushpop(heap, msg)
            if msg.sender == msg.to:
                continue
            pair = tuple(sorted((msg.sender, msg.to)))
            counts = sent.setdefault(pair, dict.fromkeys(pair, 0))
            counts[msg.sender] += 1
            if pair not in newest_pair or msg.seq > newest_pair[pair].seq:
                newest_pair[pair] = msg
        # C5 rule 1 with D27's counts: each name's partners, and how many
        # messages it exchanged with each, both ways.
        partners = {}
        for (low, high), counts in sent.items():
            both = counts[low] + counts[high]
            partners.setdefault(low, {})[high] = both
            partners.setdefault(high, {})[low] = both

        parents, roles, levels = hierarchy(names, cards, partners)

        nodes = []
        for name in sorted(names):
            card = cards.get(name, {})
            box = mail.get(name)
            pid = pids.get(name) or None
            route = card.get("route") or DEFAULT_ROUTE
            mine = newest_sent.get(name)
            sent_age = file_age(mine.path, now) if mine else None
            # D15 and D24's order. Down, woken and working each need `not
            # pid`, so one branch picks among them (stopped_state, with the
            # wait exit record since F1), asked only when the name is not
            # writing, as before: every live listener was just stamped into
            # last_listening_at above, so the map alone would catch each one.
            if sent_age is not None and sent_age <= WRITING_WINDOW_S:
                state = WRITING
            elif not pid and (stopped := self.stopped_state(name, now, exits.get(name), unreadable, candidates,
                                                            inbox, mine)) is not None:
                state = stopped
            elif pid:
                state = LISTENING
            elif route == ROUTE_CODEX:
                state = DOORBELL
            elif route == ROUTE_SSH:
                state = REMOTE
            else:
                state = IDLE
            role, role_source = roles[name]
            unread = box.get("unread") if box else 0
            newest = box.get("newest_mail_age_s") if box else None
            nodes.append({
                "id": name, "kind": card.get("kind"), "account": card.get("account"),
                "route": route, "state": state, "listener_pid": pid,
                # An inbox tc cannot count stays unknown, never 0, with tc's reason.
                "unread": unread, "unread_problem": box.get("mail_problem") if box and unread is None else None,
                "inbox_unreadable": name in unreadable,
                "last_mail_age_s": None if newest is None else max(0, newest),
                # F1 fix round 1 (Claude Opus 5.5, unreviewed): LOW-1, so the pill warns only on a fresh stop.
                "down_age_s": self.down_age(name, now, exits.get(name)) if state == DOWN else None,
                "status": status_preview(self.tc.STATUS, name),
                "role": role, "role_source": role_source,
                "reports_to": card.get("reports_to"), "level": levels[name],
                # The parent the walk used (D15): a cycle's root sits at
                # level 0 under no one, though its reports_to stays above.
                "parent": parents[name][0] if name in parents and levels[name] > 0 else None,
            })

        recent = sorted(heapq.nlargest(WIRE_HISTORY, messages, key=lambda msg: msg.seq),
                        key=lambda msg: msg.seq)
        wires = [{"from": msg.sender, "to": msg.to, "seq": msg.seq,
                  "age_s": file_age(msg.path, now)} for msg in recent]

        links = [{"from": pair[0], "to": pair[1], "kind": LINK_MAILBOX, "sent": sent[pair],
                  "last_age_s": file_age(newest_pair[pair].path, now)} for pair in sorted(sent)]
        links += [{"from": name, "to": cards[name]["reports_to"], "kind": LINK_REPORTS_TO}
                  for name in sorted(cards)
                  if cards[name]["reports_to"] not in (None, name)]
        by_account = {}
        for name in sorted(cards):
            if cards[name]["kind"] == KIND_CLAUDE and cards[name]["account"] not in (None, ACCOUNT_UNKNOWN):
                by_account.setdefault(cards[name]["account"], []).append(name)
        for account in sorted(by_account):
            same = by_account[account]
            links += [{"from": same[i], "to": same[j], "kind": LINK_NATIVE}
                      for i in range(len(same)) for j in range(i + 1, len(same))]

        machine = snap["machine"]
        return {
            "at": snap["time"],
            "machine": {key: machine[key] for key in ("load1", "cores", "mem_avail_pct")},
            "nodes": nodes, "wires": wires, "links": links,
        }


# Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
class DeadlineSocket(io.RawIOBase):
    """A request's socket, read and written against one deadline for the whole request.

    http.server reads the request line and headers through rfile and writes
    the answer through wfile. Each read and write here first sets the
    socket's timeout to the time left, so a client that trickles one byte
    at a time still runs out at the deadline. Past it, TimeoutError, which
    http.server answers by closing the connection. The deadline is on the
    monotonic clock: it times I/O, it decides nothing in the feed.

    @interacts  reads from and writes to one connected socket; sets its
                timeout before each call. Closing it leaves the socket to
                the server.
    @deps       io, time.
    @complexity O(b) per call over b bytes.
    @alloc      none retained.
    """

    def __init__(self, sock, deadline):
        """Wrap `sock` until `deadline`, a time.monotonic() value.

        @interacts  none.
        @deps       io.
        @complexity O(1).
        @alloc      none.
        """
        super().__init__()
        self.sock = sock
        self.deadline = deadline

    def readable(self):
        """True: http.server reads the request through this.

        @interacts  none.
        @deps       none.
        @complexity O(1).
        @alloc      none.
        """
        return True

    def writable(self):
        """True: http.server writes the answer through this.

        @interacts  none.
        @deps       none.
        @complexity O(1).
        @alloc      none.
        """
        return True

    def arm(self):
        """Set the socket's timeout to the time left; TimeoutError when none is left.

        @interacts  sets the socket's timeout.
        @deps       time.
        @complexity O(1).
        @alloc      none.
        """
        left = self.deadline - time.monotonic()
        if left <= 0:
            raise TimeoutError("request deadline passed")
        self.sock.settimeout(left)

    def readinto(self, buffer):
        """Read what the socket has into `buffer`, within the deadline.

        @interacts  one recv on the socket.
        @deps       arm.
        @complexity O(b) over b bytes read.
        @alloc      none.
        """
        self.arm()
        return self.sock.recv_into(buffer)

    def write(self, data):
        """Send all of `data` within the deadline (sendall's timeout covers the whole send).

        @interacts  one sendall on the socket.
        @deps       arm.
        @complexity O(b) over b bytes.
        @alloc      none.
        """
        self.arm()
        self.sock.sendall(data)
        return len(data)


class FeedHandler(http.server.BaseHTTPRequestHandler):
    """One request to the board: the Host check, then the feed or a board file.

    Every request is checked in this order. A Host that is not
    127.0.0.1:<port> or localhost:<port>: 421. A method other than GET or
    HEAD: 405. /feed without the right X-TC-Token header: 401. A path not
    on STATIC_FILES (or not on disk): 404. Every refusal has no body,
    http.server's own too (send_error), which come before the Host check:
    a request whose version http.server has read gets 400, 414 or 431, a
    status line and no body; one it still holds as HTTP/0.9 gets no bytes
    at all, not even a status line: a one-word request line, an unreadable
    version (`GET / FOO/1.0`) and HTTP/2.0, whose 505 never goes out. The
    whole request, read and answer, has REQUEST_DEADLINE_S (setup()).

    @interacts  reads the request; writes one response; calls the server's
                Board.feed() under its lock; reads one file in board/.
    @deps       hmac, http.server, io, json, time, urllib.parse;
                DeadlineSocket.
    @complexity O(1) to route, plus the feed or the file.
    @alloc      the response bytes, freed after the write.
    """

    server_version = "tc-board"
    sys_version = ""
    timeout = REQUEST_DEADLINE_S

    # Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
    def setup(self):
        """Read and write this request through one DeadlineSocket: REQUEST_DEADLINE_S in all.

        The streams http.server's setup made are closed and replaced.

        @interacts  sets the socket's timeout before each read and write.
        @deps       http.server, io, time; DeadlineSocket.
        @complexity O(1).
        @alloc      one DeadlineSocket and one read buffer, closed by finish().
        """
        super().setup()
        self.rfile.close()
        self.wfile.close()
        raw = DeadlineSocket(self.connection, time.monotonic() + REQUEST_DEADLINE_S)
        self.rfile = io.BufferedReader(raw)
        self.wfile = raw

    def __getattr__(self, name):
        """Any do_<METHOD> not defined below answers 405, so no method reaches 501.

        @interacts  none.
        @deps       none.
        @complexity O(1).
        @alloc      none.
        """
        if name.startswith("do_"):
            return self.refuse_method
        raise AttributeError(name)

    def do_GET(self):
        """Answer a GET with its body.

        @interacts  see answer().
        @deps       answer.
        @complexity see answer().
        @alloc      see answer().
        """
        self.answer(with_body=True)

    def do_HEAD(self):
        """Answer a HEAD: the same status and headers as GET, no body.

        @interacts  see answer().
        @deps       answer.
        @complexity see answer().
        @alloc      see answer().
        """
        self.answer(with_body=False)

    def log_message(self, format, *args):
        """Write no request log: the board polls every 3 s and nothing in a request is news.

        @interacts  none.
        @deps       none.
        @complexity O(1).
        @alloc      none.
        """

    def host_ok(self):
        """True when the Host header is 127.0.0.1:<port> or localhost:<port>.

        @interacts  reads the request's Host header and the bound port.
        @deps       none.
        @complexity O(h) over h = len(HOST_NAMES) = 2.
        @alloc      a few short strings.
        """
        port = self.server.server_address[1]
        host = (self.headers.get("Host") or "").lower()
        return host in {f"{name}:{port}" for name in HOST_NAMES}

    def send_empty(self, code, *headers):
        """Send `code` with no body, plus any (name, value) headers.

        @interacts  writes one response.
        @deps       http.server.
        @complexity O(1).
        @alloc      none retained.
        """
        self.send_response(code)
        for name, value in headers:
            self.send_header(name, value)
        self.send_header("Content-Length", "0")
        self.end_headers()

    # Model: Claude Opus 5.5 (the P4 phase fixer), 2026-10-15. Status: unreviewed.
    def send_error(self, code, message=None, explain=None):
        """Refuse with `code` and no body: http.server's own refusals too.

        http.server calls this when it cannot take a request at all (a bad
        request line, one past 65,536 bytes, too many or too long headers,
        an HTTP version it does not speak), before answer() and its Host
        check run. Its own page would carry a body, so every refusal here
        is empty, and the connection closes. A request it read as HTTP/0.9
        gets no status line either, as that version has none: a one-word
        request line, an unreadable version, and HTTP/2.0, whose 505 is
        never sent.

        @interacts  writes one empty response.
        @deps       send_empty.
        @complexity O(1).
        @alloc      none retained.
        """
        self.close_connection = True
        self.send_empty(code)

    def send_bytes(self, ctype, data, with_body):
        """Send 200 with `data` as `ctype`; the body only when `with_body`.

        @interacts  writes one response.
        @deps       http.server.
        @complexity O(b) over b bytes of data.
        @alloc      none retained.
        """
        self.send_response(http.server.HTTPStatus.OK)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        if with_body:
            self.wfile.write(data)

    def refuse_method(self):
        """421 for a foreign Host, else 405: nothing on the board writes.

        @interacts  writes one response.
        @deps       host_ok, send_empty.
        @complexity O(1).
        @alloc      none retained.
        """
        if not self.host_ok():
            self.send_empty(http.server.HTTPStatus.MISDIRECTED_REQUEST)
            return
        self.send_empty(http.server.HTTPStatus.METHOD_NOT_ALLOWED, ("Allow", "GET, HEAD"))

    def answer(self, with_body):
        """Route a GET or HEAD: the Host check, then /feed or an allowed file.

        @interacts  calls Board.feed() under the server's lock for /feed;
                    reads one file in board/ otherwise. A feed that raises
                    gets 500 and one line on stderr.
        @deps       hmac, json, urllib.parse; host_ok, send_empty, send_bytes.
        @complexity O(1) to route, plus one feed() or one file read.
        @alloc      the JSON or the file's bytes, freed after the write.
        """
        if not self.host_ok():
            self.send_empty(http.server.HTTPStatus.MISDIRECTED_REQUEST)
            return
        path = urllib.parse.urlsplit(self.path).path
        if path == FEED_PATH:
            given = (self.headers.get(TOKEN_HEADER) or "").encode("utf-8", "replace")
            if not hmac.compare_digest(given, self.server.token.encode("utf-8")):
                self.send_empty(http.server.HTTPStatus.UNAUTHORIZED)
                return
            try:
                with self.server.feed_lock:
                    data = json.dumps(self.server.board.feed()).encode("utf-8")
            except Exception as exc:  # the server stays up; the page shows "no answer"
                print(f"serve.py: feed failed: {exc!r}", file=sys.stderr, flush=True)
                self.send_empty(http.server.HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            self.send_bytes(FEED_TYPE, data, with_body)
            return
        name = path[1:] if path.startswith("/") else ""
        if name not in STATIC_PATHS:
            self.send_empty(http.server.HTTPStatus.NOT_FOUND)
            return
        try:
            data = STATIC_PATHS[name].read_bytes()
        except OSError:
            self.send_empty(http.server.HTTPStatus.NOT_FOUND)
            return
        self.send_bytes(STATIC_FILES[name], data, with_body)


class BoardServer(http.server.ThreadingHTTPServer):
    """The board's HTTP server: bound to BIND_HOST, holding one Board and the token.

    Board.feed() keeps state across calls (last_listening_at,
    first_missing_at, wakes), so requests take `feed_lock` around it.
    Request threads are daemon threads, so a
    stalled one never keeps the process alive. At most `max_connections`
    (MAX_CONNECTIONS) are served at once, each holding one of `slots`; one
    past that is closed at once, and each ends by REQUEST_DEADLINE_S.

    @interacts  binds one TCP socket on BIND_HOST:`port` (0: the OS picks).
    @deps       http.server, threading; FeedHandler.
    @complexity O(1) to build.
    @alloc      the socket, released by server_close(); the Board, the
                token, one lock and the slots, held for the server's life.
    """

    daemon_threads = True

    def __init__(self, board, port, token, max_connections=MAX_CONNECTIONS):
        """Bind BIND_HOST:`port` and keep `board` and `token` for the handler.

        @interacts  binds and listens on one socket.
        @deps       http.server, threading.
        @complexity O(1).
        @alloc      the socket, one lock and one semaphore.
        """
        super().__init__((BIND_HOST, port), FeedHandler)
        self.board = board
        self.token = token
        self.feed_lock = threading.Lock()
        self.slots = threading.BoundedSemaphore(max_connections)

    # Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
    def process_request(self, request, client_address):
        """Start the request's thread when a slot is free; with none free, close it at once.

        @interacts  takes one slot, or shuts the connection down.
        @deps       socketserver (through http.server), threading.
        @complexity O(1).
        @alloc      one thread while the request runs.
        """
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.slots.release()
            raise

    # Model: Claude Opus 5.5 (the P4 phase fixer), 2026-10-15. Status: unreviewed.
    def handle_error(self, request, client_address):
        """One line on stderr for a request that failed past its handler, never a traceback.

        A client that hangs up before its answer is written (a reload, a
        closed tab, a poll the page gave up on) makes the write raise
        BrokenPipeError or ConnectionResetError, and socketserver's own
        handle_error would print a traceback for it.

        @interacts  writes one line to stderr.
        @deps       sys.
        @complexity O(1).
        @alloc      one short string.
        """
        error = sys.exc_info()[1]
        if isinstance(error, (BrokenPipeError, ConnectionResetError)):
            print("serve.py: a client hung up before its answer was written", file=sys.stderr, flush=True)
        else:
            print(f"serve.py: a request failed: {error!r}", file=sys.stderr, flush=True)

    def process_request_thread(self, request, client_address):
        """Handle one request on its own thread, then give its slot back.

        @interacts  see FeedHandler; releases one slot.
        @deps       socketserver (through http.server).
        @complexity the request's.
        @alloc      none retained.
        """
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()


def stop_on_term(signum, frame):
    """SIGTERM handler: stop serve_forever the way Ctrl+C does, so the socket closes.

    @interacts  raises KeyboardInterrupt in the main thread.
    @deps       none.
    @complexity O(1).
    @alloc      none.
    """
    raise KeyboardInterrupt


def main(argv=None):
    """Start the board: print its URL with a fresh token once, serve until stopped.

    @interacts  see the module block: loads tc for the mailbox TC_ROOT
                names (or tc's own folder), binds BIND_HOST:--port, prints
                one line to stdout, sets a SIGTERM handler. A usage error,
                --port 80 among them, goes to stderr in words and exits 2
                (argparse's) before anything is loaded or bound.
    @deps       argparse, secrets, signal; Board, BoardServer.
    @complexity O(1) to start; then one request at a time per thread.
    @alloc      one Board and one BoardServer, closed on the way out.
    """
    ap = argparse.ArgumentParser(prog="serve.py",
                                 description="The live board: a read-only feed of the mailbox on 127.0.0.1.")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT,
                    help=f"port on {BIND_HOST} (default {DEFAULT_PORT}; 0 lets the OS pick)")
    args = ap.parse_args(argv)
    if args.port == HTTP_DEFAULT_PORT:
        ap.error(f"--port {HTTP_DEFAULT_PORT}: a browser leaves port {HTTP_DEFAULT_PORT} out of its Host header, "
                 "which the board refuses; pick another port (0 lets the OS pick)")
    token = secrets.token_urlsafe(TOKEN_BYTES)
    server = BoardServer(Board(), args.port, token)
    signal.signal(signal.SIGTERM, stop_on_term)
    host, port = server.server_address[:2]
    print(f"board: http://{host}:{port}/live.html#token={token}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
