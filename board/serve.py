#!/usr/bin/env python3
"""
serve.py: the live board's feed (C5). Loads tc as a module and never edits
it. feed() builds one JSON object from tc's health snapshot, the address
cards and the message file names. It never opens a message body.

Model:  Claude Opus 5.5 (the BOARD lane agent), 2026-10-14
Status: unreviewed

Where each feed key comes from. tc is read at its own commit; `snap` is
tc.health_snapshot(), which returns time, machine, sessions, listeners,
watchers and mail:

  at                       snap["time"] (tc's now_iso(): local time, seconds)
  machine.load1            snap["machine"]["load1"]
  machine.cores            snap["machine"]["cores"]
  machine.mem_avail_pct    snap["machine"]["mem_avail_pct"]
                           (snap's "gpus", "sessions" and "watchers" are not
                           in C5 and are dropped)
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
  role_source, level,      this lane's addition (pause BOARD-3): the node the
  parent                   level walk hangs it under, or None
  wires, links             message file names under mail/to-*/ and
                           mail/to-*/read/; ages from each file's mtime (a
                           stat, never an open)

State, first match wins, in C5's order (pause BOARD-1): `listening` (a pid
holds the name's lock in /proc/locks), `writing` (its newest sent message is
at most WRITING_WINDOW_S old), `doorbell` (route codex), `remote` (route
ssh), `down` (seen listening by this Board within DOWN_WINDOW_S, not now),
`idle`. `down` lives in this object's memory only: after a restart nothing
is down until it has been seen listening again.

Roles and levels follow C5 step by step. Partners are the names a node has
exchanged mail with, either way, itself excluded; a partner need not be a
node. A parent is always a node: declared from the card's reports_to when
it names a node, else inferred as the one partner of a node with exactly
one partner when that partner has HUB_MIN_PARTNERS or more. A reports_to
that names no node, or the node itself, gives no parent and stops
inference. Nodes the walk from the roots cannot reach hang on a reports_to
cycle; the cycle member whose name sorts first becomes a root (assumption
in the BOARD handoff: a node below a cycle is not on it, so it stays below).

Known limit (C5 rule 6): with no hints at all, a top relay whose only
partner is a lower relay is drawn as that relay's `worker`, marked
`inferred`. `tc join <name> --reports-to <relay>` fixes it.

@interacts  loads ../tc as a module with TC_ROOT set for the load only,
            then calls tc.health_snapshot(), which reads /proc (meminfo,
            locks, each process's stat and cmdline), runs nvidia-smi when
            it exists, and globs and stats mail/ and status/ under tc's
            ROOT. Reads cards/*.json and the head of status/<name>.md; lists
            mail/to-*/ and mail/to-*/read/ and stats a few message files.
            Opens no message body. Writes nothing, anywhere.
@deps       python3 stdlib (collections, heapq, importlib, json, os,
            pathlib, re, time); ../tc; Linux (/proc via tc).
@complexity feed(): O(n + m + e) plus tc's own health_snapshot (O(p + k + n),
            see tc's header): n names (single digits to tens), m message
            file names (about 800 after two weeks of heavy use; each is
            matched once, no body read), e parent edges (at most n). The
            last WIRE_HISTORY messages are picked in O(m log W), W = 50.
            Stats: at most W + n + l files, l linked pairs (at most n^2/2,
            tens in practice).
@alloc      per feed(): one list of m small tuples and the returned dict,
            freed when the caller drops them. Held across calls: the
            loaded tc module and last_listening_at, one float per name
            seen listening, pruned past DOWN_WINDOW_S on every feed().
"""

import collections
import heapq
import importlib.machinery
import importlib.util
import json
import os
import pathlib
import re
import time

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
# A card is a few hundred bytes (C1). A file in cards/ bigger than this is
# not a card, and the board skips it instead of reading it on every poll.
CARD_READ_MAX_BYTES = 65536

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

# C5's states, in the order the first match wins (pause BOARD-1).
LISTENING, WRITING, DOORBELL, REMOTE, DOWN, IDLE = (
    "listening", "writing", "doorbell", "remote", "down", "idle")
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


def read_cards(folder):
    """Every card in `folder` (cards/ under ROOT), as {name: fields}.

    The name is the file's stem (C1: cards/<name>.json). A file that is not
    a JSON object, is unreadable, or is over CARD_READ_MAX_BYTES is skipped:
    the board draws what it can. Only the fields the feed uses are kept,
    each checked for type: kind, account, route (default "local"),
    reports_to (a non-empty string, else None).

    @interacts  lists `folder`; reads each *.json in it, at most
                CARD_READ_MAX_BYTES + 1 bytes each.
    @deps       json, pathlib; card_text.
    @complexity O(c) over c card files (one per name, tens at most).
    @alloc      one small dict per card, returned.
    """
    cards = {}
    try:
        paths = sorted(folder.glob(f"*{CARD_SUFFIX}"))
    except OSError:
        return cards
    for path in paths:
        try:
            with open(path, "rb") as f:
                raw = f.read(CARD_READ_MAX_BYTES + 1)
            if len(raw) > CARD_READ_MAX_BYTES:
                continue
            card = json.loads(raw)
        except (OSError, ValueError):
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
    Opens no file.

    @interacts  lists `mail`, each to-*/ folder and each to-*/read/.
    @deps       os, re.
    @complexity O(b + m) over b inbox folders and m file names in them.
    @alloc      one Message per message file, in the returned list.
    """
    found = []
    try:
        boxes = [entry for entry in os.scandir(mail)
                 if entry.name.startswith(INBOX_PREFIX) and entry.is_dir()]
    except OSError:
        return found
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
    line, cut at STATUS_PREVIEW_CHARS.

    @interacts  reads at most STATUS_READ_MAX_BYTES of status/<name>.md.
    @deps       re.
    @complexity O(s) over s <= STATUS_READ_MAX_BYTES bytes read.
    @alloc      the bytes read and one short string, returned.
    """
    try:
        with open(folder / f"{name}{STATUS_SUFFIX}", "rb") as f:
            head = f.read(STATUS_READ_MAX_BYTES).decode("utf-8", "replace")
    except OSError:
        return None
    lines = head.splitlines()
    if lines and STATUS_HEADER.match(lines[0]):
        lines = lines[1:]
    for line in lines:
        if line.strip():
            return line.strip()[:STATUS_PREVIEW_CHARS]
    return None


def file_age(path, now):
    """Whole seconds since `path` was last written, or None if it is gone.

    A message read between the scan and this stat moved to read/; its age
    is None for this poll and right on the next.

    @interacts  stats `path`; never opens it.
    @deps       os.
    @complexity O(1).
    @alloc      none.
    """
    try:
        return max(0, round(now - os.stat(path).st_mtime))
    except OSError:
        return None


def parents_of(names, cards, partners):
    """C5 rule 2: {name: (parent, DECLARED or INFERRED)} for each node with one.

    Declared: the card's reports_to, when it names a node other than the
    node itself. A reports_to that names no node (or itself) gives no
    parent, and nothing is inferred over it. Inferred, when nothing is
    declared: the one partner of a node with exactly one partner, when that
    partner is a node with HUB_MIN_PARTNERS or more partners.

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
            if only in names and len(partners.get(only, ())) >= HUB_MIN_PARTNERS:
                found[name] = (only, INFERRED)
    return found


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
    fake one so windows can be crossed without waiting.

    @interacts  see the module block.
    @deps       load_tc and the module's helpers.
    @complexity O(1) to build, plus one load of tc.
    @alloc      the tc module and last_listening_at, held for the object's life.
    """

    def __init__(self, root=None, clock=time.time):
        """Load tc for `root` (or TC_ROOT as it stands) and start with no history.

        @interacts  load_tc(root).
        @deps       load_tc.
        @complexity O(1).
        @alloc      the tc module and one empty dict.
        """
        self.tc = load_tc(root)
        self.clock = clock
        self.last_listening_at = {}

    def feed(self):
        """One C5 feed object for the mailbox as it is now.

        @interacts  see the module block; updates last_listening_at.
        @deps       tc.health_snapshot, read_cards, scan_messages,
                    status_preview, file_age, parents_of, roles_of,
                    levels_of.
        @complexity O(n + m + e), see the module block.
        @alloc      the returned dict; last_listening_at gains one float per
                    name listening now and drops each past DOWN_WINDOW_S.
        """
        now = self.clock()
        snap = self.tc.health_snapshot()
        pids = snap["listeners"]
        for name, pid in pids.items():
            if pid:
                self.last_listening_at[name] = now
        for name, seen in list(self.last_listening_at.items()):
            if now - seen > DOWN_WINDOW_S:
                del self.last_listening_at[name]

        cards = read_cards(self.tc.ROOT / CARDS_FOLDER)
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

        parents = parents_of(names, cards, partners)
        roles = roles_of(names, parents)
        levels = levels_of(names, parents)

        nodes = []
        for name in sorted(names):
            card = cards.get(name, {})
            box = mail.get(name)
            pid = pids.get(name) or None
            route = card.get("route") or DEFAULT_ROUTE
            mine = newest_sent.get(name)
            sent_age = file_age(mine.path, now) if mine else None
            if pid:
                state = LISTENING
            elif sent_age is not None and sent_age <= WRITING_WINDOW_S:
                state = WRITING
            elif route == ROUTE_CODEX:
                state = DOORBELL
            elif route == ROUTE_SSH:
                state = REMOTE
            elif name in self.last_listening_at:
                state = DOWN
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
                "parent": parents[name][0] if name in parents else None,
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
            if cards[name]["kind"] == KIND_CLAUDE and cards[name]["account"] is not None:
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
