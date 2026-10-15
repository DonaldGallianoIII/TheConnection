#!/usr/bin/env python3
"""
serve.py: the live board's feed (C5) and its server (C6). Loads tc as a
module and never edits it. feed() builds one JSON object from the parts
it needs: the machine (machine_now, tc's numbers and rounding read here),
the listeners and the mail (tc.listeners, tc.mailbox_summary), the
address cards and the message file names, never from tc.health_snapshot().
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
  nodes[].unread           snap["mail"][name]["unread"]; 0 with no inbox
  nodes[].last_mail_age_s  snap["mail"][name]["newest_mail_age_s"]: seconds
                           since the newest message in the name's inbox or
                           read/, so mail it received; None with no inbox
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

State, first match wins, in D15's order: `writing` (its newest sent message
is at most WRITING_WINDOW_S old, listener or not), `down` (no pid now, and
seen listening by this Board within DOWN_WINDOW_S), `listening` (a pid holds
the name's lock in /proc/locks), `doorbell` (route codex), `remote` (route
ssh), `idle`. A message whose mtime is in the future has no age, so it never
makes its sender writing. `down` lives in this object's memory only: after a
restart nothing is down until it has been seen listening again.

Roles and levels follow C5 step by step. Partners are the names a node has
exchanged mail with, either way, itself excluded; a partner need not be a
node. A parent is always a node: declared from the card's reports_to when
it names a node, else inferred as the one partner of a node with exactly
one partner when that partner has HUB_MIN_PARTNERS or more, unless that
partner's card declares this node as its own parent (D15: inference never
inverts a declared edge). A reports_to that names no node, or the node
itself, gives no parent and stops inference. An inferred edge that closes
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

@interacts  loads ../tc as a module with TC_ROOT set for the load only,
            then calls tc.now_iso(), tc.listeners("wait") (reads
            /proc/locks, globs mail/.wait-*.lock) and tc.mailbox_summary()
            (globs and stats mail/ and status/ under tc's ROOT); reads the
            load average and /proc/meminfo itself. Never runs nvidia-smi
            and never scans the process list. Reads cards/*.json and the
            head of status/<name>.md; lists mail/to-*/ and mail/to-*/read/
            and stats a few message files.
            Opens no message body. Writes nothing to the mailbox; the first
            load of tc may write tc's bytecode cache (__pycache__/ beside
            tc), as any import of it does. main() binds one
            TCP socket on 127.0.0.1, prints the URL with the token once to
            stdout, reads the allow-listed files in board/ per request, and
            writes no request log. A failed feed writes one line to stderr,
            and so does the first poll that meets a card nested past
            Python's recursion limit. Card and status files are opened with
            O_NONBLOCK and O_NOFOLLOW and read only when fstat says regular,
            so a FIFO never blocks a poll and a symlink never redirects one.
@deps       python3 stdlib (argparse, collections, heapq, hmac, http.server,
            importlib, io, json, os, pathlib, re, secrets, signal, stat,
            sys, threading, time, urllib.parse); ../tc; Linux (/proc:
            /proc/locks through tc, the load average and /proc/meminfo
            read here).
@complexity feed(), per poll: O(k + m log W + n + c^2). The snapshot:
            tc.listeners is O(k + n), k lines in /proc/locks (tens) and n
            names (single digits to tens); tc.mailbox_summary is O(n + m),
            since it stats every message file, m of them (about 800 after
            two weeks of heavy use, and only growing, since read/ is kept).
            Here: every inbox listed again and each of the m names matched
            once (no body read); the last WIRE_HISTORY picked in
            O(m log W), W = 50; W + n + l more stats for l linked pairs (at
            most n^2/2, tens in practice); each card read once, c cards;
            levels in O(n + e), e parent edges (at most n); and c(c-1)/2
            native links over the claude cards on one named account. In
            all m + W + n + l stats per poll, and no child process. One
            request: O(1) to route, plus one feed() or one read of a board
            file (tens of KB).
@alloc      per feed(): tc.mailbox_summary builds m path and stat objects; here
            one Message per message file, the per-pair counts, and the
            returned dict (n nodes, at most W wires, l + n + c(c-1)/2
            links); all freed when the caller drops them. Held across calls: the
            loaded tc module and last_listening_at, one float per name
            seen listening, pruned past DOWN_WINDOW_S on every feed(), and
            the names of cards found nested too deep, one each. The server
            holds one Board, the token, a lock and MAX_CONNECTIONS slots;
            one short-lived thread per request, at most MAX_CONNECTIONS at
            once, each ended by REQUEST_DEADLINE_S.
"""

import argparse
import collections
import heapq
import hmac
import http.server
import importlib.machinery
import importlib.util
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
import urllib.parse

BOARD_DIR = pathlib.Path(__file__).resolve().parent
TC_PATH = BOARD_DIR.parent / "tc"

# A name reads as writing for this long after its newest message (C5).
# Three of the page's 3 s polls, so a send is seen at least once; short
# enough that a session that went quiet stops reading as busy.
WRITING_WINDOW_S = 10
# A name seen listening this recently and not listening now is down (C5).
# Ten minutes covers a listener's re-arm gap and a long turn; past it, a
# name that stopped on purpose reads idle instead of raising an alarm.
DOWN_WINDOW_S = 600
# Characters of a status line on a node (C5): one line on a node box. The
# whole status stays in status/<name>.md.
STATUS_PREVIEW_CHARS = 80
# Bytes read from the head of a status file. The preview needs one line;
# a runaway status file costs a poll no more than this.
STATUS_READ_MAX_BYTES = 4096
# Messages carried in "wires" (C5): the recent traffic the page animates.
# Links still read every message file name.
WIRE_HISTORY = 50
# A node with exactly one partner is that partner's worker when the partner
# has at least this many partners (O11). With two, one partner alone is a
# pair of peers, and a relay needs a second partner to be one.
HUB_MIN_PARTNERS = 2
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
# folder listing, so serve.py, tc and the mailbox never leave.
STATIC_FILES = {
    "live.html": "text/html; charset=utf-8",
    "look.js": "text/javascript; charset=utf-8",
    "theme.css": "text/css; charset=utf-8",
    "demo.html": "text/html; charset=utf-8",
    "demo-script.json": "application/json; charset=utf-8",
    "compare.html": "text/html; charset=utf-8",
}
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

# C5's states, in the order the first match wins (D15).
WRITING, DOWN, LISTENING, DOORBELL, REMOTE, IDLE = (
    "writing", "down", "listening", "doorbell", "remote", "idle")
ORCHESTRATOR, WORKER, PEER = "orchestrator", "worker", "peer"
DECLARED, INFERRED = "declared", "inferred"
LINK_MAILBOX, LINK_REPORTS_TO, LINK_NATIVE = "mailbox", "reports_to", "native"

# One message, from its file name alone.
Message = collections.namedtuple("Message", "seq sender to path")


def load_tc(root=None):
    """Load ../tc as a module without running main(), the way C5 shows.

    tc fixes ROOT, MAIL, STATUS and SEQ_FILE at import, from TC_ROOT. With
    `root` given, TC_ROOT is set to it for the load and put back after, so
    the module points at `root` and the process's environment is unchanged.
    With `root` None, tc reads TC_ROOT as it stands (or its own folder).

    @interacts  reads and restores os.environ["TC_ROOT"]; executes ../tc's
                top level (imports and constants; tc's main() is not run).
    @deps       importlib; ../tc.
    @complexity O(1): one module load.
    @alloc      one module object, returned; the caller holds it.
    """
    old = os.environ.get("TC_ROOT")
    if root is not None:
        os.environ["TC_ROOT"] = str(root)
    try:
        loader = importlib.machinery.SourceFileLoader("tc", str(TC_PATH))
        tc = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
        loader.exec_module(tc)
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


def scan_messages(mail):
    """Every message under `mail`, from file names only: [Message].

    Looks in each mail/to-<name>/ and its read/. A name that does not match
    MESSAGE_NAME (a .tmp being written, a lock, anything else) is skipped.
    A to-* entry whose stat fails (a link that loops, a folder the user
    cannot search, a dead mount) is skipped on its own; the rest of the
    scan stands. Opens no file.

    @interacts  lists `mail`, each to-*/ folder and each to-*/read/.
    @deps       os, re.
    @complexity O(b + m) over b inbox folders and m file names in them.
    @alloc      one Message per message file, in the returned list.
    """
    found = []
    try:
        with os.scandir(mail) as listing:
            entries = list(listing)
    except OSError:
        return found
    boxes = []
    for entry in entries:
        if not entry.name.startswith(INBOX_PREFIX):
            continue
        try:
            if entry.is_dir():
                boxes.append(entry)
        except OSError:
            continue
    for box in boxes:
        to = box.name[len(INBOX_PREFIX):]
        if not to:
            continue
        for folder in (box.path, os.path.join(box.path, READ_FOLDER)):
            try:
                entries = os.scandir(folder)
            except OSError:
                continue
            with entries:
                for entry in entries:
                    match = MESSAGE_NAME.match(entry.name)
                    if match:
                        found.append(Message(int(match.group(1)), match.group(2), to, entry.path))
    return found


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


def file_age(path, now):
    """Whole seconds since `path` was last written, or None if it is gone.

    A message read between the scan and this stat moved to read/; its age
    is None for this poll and right on the next. An mtime ahead of `now`
    (a touched file, or a clock stepped back) is no age at all: None, so a
    message from the future never reads as just sent. Rounding gives half a
    second of grace to a file written in the same instant as `now`.

    @interacts  stats `path`; never opens it.
    @deps       os.
    @complexity O(1).
    @alloc      none.
    """
    try:
        age = round(now - os.stat(path).st_mtime)
    except OSError:
        return None
    return age if age >= 0 else None


def parents_of(names, cards, partners):
    """C5 rule 2: {name: (parent, DECLARED or INFERRED)} for each node with one.

    Declared: the card's reports_to, when it names a node other than the
    node itself. A reports_to that names no node (or itself) gives no
    parent, and nothing is inferred over it. Inferred, when nothing is
    declared: the one partner of a node with exactly one partner, when that
    partner is a node with HUB_MIN_PARTNERS or more partners and its card
    does not report to this node (D15: an inferred edge never runs against
    a declared one, whatever order the names sort in).

    @interacts  none; pure.
    @deps       none.
    @complexity O(n) over n names: one set lookup per node and per partner.
    @alloc      the returned dict, one entry per node with a parent.
    """
    found = {}
    for name in names:
        declared = cards.get(name, {}).get("reports_to")
        if declared is not None:
            if declared in names and declared != name:
                found[name] = (declared, DECLARED)
            continue
        mine = partners.get(name, ())
        if len(mine) == 1:
            (only,) = mine
            if (only in names and len(partners.get(only, ())) >= HUB_MIN_PARTNERS
                    and cards.get(only, {}).get("reports_to") != name):
                found[name] = (only, INFERRED)
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
    @complexity O(n + e) over n names and e parent edges.
    @alloc      the three returned dicts and their helpers' working sets.
    """
    parents = drop_inferred_cycles(parents_of(names, cards, partners))
    return parents, roles_of(names, parents), levels_of(names, parents)


def roles_of(names, parents):
    """C5 rules 3 and 4: {name: (role, role_source)}.

    orchestrator: one or more nodes have it as parent; declared when every
    one of those edges is. worker: it has a parent and no children; the
    source is that edge's. peer: neither, always inferred.

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
            roles[name] = (PEER, INFERRED)
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
    """The feed's state across polls: the loaded tc and who was seen listening.

    `clock` returns seconds since the epoch, as time.time does; tests pass a
    fake one so windows can be crossed without waiting. feed() is not safe
    from two threads at once; BoardServer calls it under its own lock.

    @interacts  see the module block.
    @deps       load_tc and the module's helpers.
    @complexity O(1) to build, plus one load of tc.
    @alloc      the tc module, last_listening_at and nested_cards, held for
                the object's life.
    """

    def __init__(self, root=None, clock=time.time):
        """Load tc for `root` (or TC_ROOT as it stands) and start with no history.

        @interacts  load_tc(root).
        @deps       load_tc.
        @complexity O(1).
        @alloc      the tc module, one empty dict and one empty set.
        """
        self.tc = load_tc(root)
        self.clock = clock
        self.last_listening_at = {}
        self.nested_cards = set()

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

        @interacts  see the module block: /proc/locks, the lock files, mail/
                    and status/ through tc; the load average and
                    /proc/meminfo through machine_now.
        @deps       tc.now_iso, tc.listeners, tc.mailbox_summary;
                    machine_now.
        @complexity O(k + n + m): k lines in /proc/locks, n names, m message
                    files.
        @alloc      one dict, returned.
        """
        return {"time": self.tc.now_iso(), "machine": machine_now(),
                "listeners": self.tc.listeners("wait"), "mail": self.tc.mailbox_summary()}

    def feed(self):
        """One C5 feed object for the mailbox as it is now.

        @interacts  see the module block; updates last_listening_at and,
                    through note_nested, nested_cards.
        @deps       snapshot, read_cards, scan_messages, status_preview,
                    file_age, hierarchy, note_nested.
        @complexity O(k + m log W + n + c^2) per poll; the module block
                    names each term.
        @alloc      the per-poll objects the module block lists, and the
                    returned dict; last_listening_at gains one float per
                    name listening now and drops each past DOWN_WINDOW_S.
        """
        now = self.clock()
        snap = self.snapshot()
        pids = snap["listeners"]
        for name, pid in pids.items():
            if pid:
                self.last_listening_at[name] = now
        for name, seen in list(self.last_listening_at.items()):
            if now - seen > DOWN_WINDOW_S:
                del self.last_listening_at[name]

        cards = read_cards(self.tc.ROOT / CARDS_FOLDER, self.note_nested)
        mail = snap["mail"]
        names = set(mail) | set(cards)
        messages = scan_messages(self.tc.MAIL)

        partners, sent, newest_pair, newest_sent = {}, {}, {}, {}
        for msg in messages:
            if msg.sender not in newest_sent or msg.seq > newest_sent[msg.sender].seq:
                newest_sent[msg.sender] = msg
            if msg.sender == msg.to:
                continue
            partners.setdefault(msg.sender, set()).add(msg.to)
            partners.setdefault(msg.to, set()).add(msg.sender)
            pair = tuple(sorted((msg.sender, msg.to)))
            counts = sent.setdefault(pair, dict.fromkeys(pair, 0))
            counts[msg.sender] += 1
            if pair not in newest_pair or msg.seq > newest_pair[pair].seq:
                newest_pair[pair] = msg

        parents, roles, levels = hierarchy(names, cards, partners)

        nodes = []
        for name in sorted(names):
            card = cards.get(name, {})
            box = mail.get(name)
            pid = pids.get(name) or None
            route = card.get("route") or DEFAULT_ROUTE
            mine = newest_sent.get(name)
            sent_age = file_age(mine.path, now) if mine else None
            # D15's order. Down needs `not pid`: every live listener was
            # just stamped into last_listening_at above, so the map alone
            # would call each one down.
            if sent_age is not None and sent_age <= WRITING_WINDOW_S:
                state = WRITING
            elif not pid and name in self.last_listening_at:
                state = DOWN
            elif pid:
                state = LISTENING
            elif route == ROUTE_CODEX:
                state = DOORBELL
            elif route == ROUTE_SSH:
                state = REMOTE
            else:
                state = IDLE
            role, role_source = roles[name]
            nodes.append({
                "id": name, "kind": card.get("kind"), "account": card.get("account"),
                "route": route, "state": state, "listener_pid": pid,
                "unread": box["unread"] if box else 0,
                "last_mail_age_s": box["newest_mail_age_s"] if box else None,
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
    on STATIC_FILES (or not on disk): 404. Every refusal has no body. The
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
        if name not in STATIC_FILES:
            self.send_empty(http.server.HTTPStatus.NOT_FOUND)
            return
        try:
            data = (BOARD_DIR / name).read_bytes()
        except OSError:
            self.send_empty(http.server.HTTPStatus.NOT_FOUND)
            return
        self.send_bytes(STATIC_FILES[name], data, with_body)


class BoardServer(http.server.ThreadingHTTPServer):
    """The board's HTTP server: bound to BIND_HOST, holding one Board and the token.

    Board.feed() keeps state across calls (last_listening_at), so requests
    take `feed_lock` around it. Request threads are daemon threads, so a
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
                one line to stdout, sets a SIGTERM handler.
    @deps       argparse, secrets, signal; Board, BoardServer.
    @complexity O(1) to start; then one request at a time per thread.
    @alloc      one Board and one BoardServer, closed on the way out.
    """
    ap = argparse.ArgumentParser(prog="serve.py",
                                 description="The live board: a read-only feed of the mailbox on 127.0.0.1.")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT,
                    help=f"port on {BIND_HOST} (default {DEFAULT_PORT}; 0 lets the OS pick)")
    args = ap.parse_args(argv)
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
