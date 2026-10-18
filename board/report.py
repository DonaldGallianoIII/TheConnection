#!/usr/bin/env python3
"""
report.py: `tc report`'s extractor, scrub and renderer (contract C7,
decision D42). tc loads this file from its own folder, from source, in
memory, and calls report(); nothing here runs on its own.

Model:  Claude Opus 5.5 (the DASH lane agent), 2026-10-17
Status: unreviewed

Three steps, each a pure handoff to the next:

1. extract(tc): one pinned walk of every mail/to-*/ and its read/ (D35,
   through tc's own open_mail, open_inbox and message_files, as tc log
   walks), one bounded read per message, one read of each read/'s
   .read-times (tc's read_times: C2's rules), and cards/*.json for
   reports_to only. Out comes one closed Record per message and one
   Session per name, with C5's role from board/serve.py's own hierarchy(),
   loaded from source (load_board_module), never copied.
2. scrub(mailbox): names to role labels by first mail, tags off
   SCRUB_TAGS to `other`, every time to seconds from the first message,
   numbers to ranks. It runs on the records, before the renderer, so the
   renderer never sees a real name, time or number on a scrubbed page.
3. render(mailbox): records in, one HTML string out.

What it reads, and nothing else (C7, D42): each message's file name
(number, sender, recipient) and size; its header line, for the sent time
only (the header note is matched and dropped, never kept); the first line
of its body, inside the first MESSAGE_HEADER_MAX_BYTES +
TAG_READ_MAX_BYTES bytes of the file, from which only a tag and #N
references are kept; read/.read-times; and each card's reports_to. Never
a body past that line, a status file, an outbox, or anything outside
ROOT.

@interacts  extract: opens mail/ and each inbox and read/ by name (tc's
            pinned walk), lists and stats each message name, opens each
            message by name in its folder's descriptor (never through a
            link, never blocking) and reads at most tc's
            MESSAGE_HEADER_MAX_BYTES + TAG_READ_MAX_BYTES of it; reads
            each read/'s .read-times through tc.read_times; globs cards/ and reads each card through tc.read_regular_file.
            Writes nothing. load_board_module reads board/serve.py and runs
            its top level (imports and constants; its main() is not run).
@deps       python3 stdlib (collections, contextlib, datetime, json, os,
            pathlib, re, stat, types); the tc module its caller passes;
            board/serve.py (hierarchy, card_text).
@complexity extract O(n log n + T + t log t + R + c) over n inboxes, T
            names in every inbox and read/, t messages ever (low thousands
            after weeks of heavy use), each read at most
            MESSAGE_HEADER_MAX_BYTES + TAG_READ_MAX_BYTES, R bytes of the
            read-time records and c cards; plus serve.py's hierarchy, O(n + p + e).
@alloc      extract: one Record per message and one Session per name,
            returned; each inbox's two descriptors, closed before it
            returns; each message's head bytes, freed per message.
"""

import collections
import contextlib
import datetime
import html
import json
import math
import os
import pathlib
import re
import stat
import types

BOARD_DIR = pathlib.Path(__file__).resolve().parent
SERVE_PATH = BOARD_DIR / "serve.py"

# How far into a message's body the tag read goes, past the header's own
# bound (tc's MESSAGE_HEADER_MAX_BYTES). A tag is at most 24 characters and
# a reply's first line names its #N within a few words; 256 bytes holds
# that with room, and keeps the read of a 1 MiB body to one small block.
TAG_READ_MAX_BYTES = 256
# A tag (C7): a leading token of capitals, digits and dashes, 2 to 24
# characters, once one trailing colon is stripped.
TAG_PATTERN = re.compile(r"[A-Z][A-Z0-9-]{1,23}")
TAG_COLON = ":"
# A reference to an earlier message on a first line: `#` and its number.
REF_PATTERN = re.compile(r"#([0-9]+)")
# A message's header line, as tc's publish_message writes it: `# #<n> from
# <sender> to <to>, <time>[, <note>]`. Only the time is kept; the note is
# matched so a header that carries one still parses, and is never kept.
HEADER_PATTERN = re.compile(r"# #[0-9]+ from \S+ to \S+, "
                            r"(?P<sent>[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}[+-][0-9]{2}:[0-9]{2})"
                            r"(?:, .*)?")
# The folders the walk enters, as tc names them.
INBOX_PREFIX = "to-"
READ_FOLDER = "read"
CARD_SUFFIX = ".json"
# Opening a message: never through a link, never blocking on a FIFO.
HEAD_OPEN_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
# The tags a scrubbed page keeps as they are (C7). The project's own
# working words, none of which names a person, a project or a machine;
# any other tag reads OTHER_TAG.
SCRUB_TAGS = frozenset(("ANSWER", "FYI", "QUESTION", "PLAN", "PLAN-READY", "PLAN-CHECK", "PLAN-EDIT",
                        "PLAN-EDITED", "PLAN-REVIEWED", "CORRECTION", "HEADS-UP", "MERGE", "REVIEW",
                        "STATUS", "BLOCKED", "DONE", "BREACH"))
OTHER_TAG = "other"
# What a scrubbed name is called when C5 gives it no role (C7): a name
# with no inbox and no card.
NO_ROLE_LABEL = "session"

# ---------- the renderer's rules and sizes ----------
# Every length below is in the SVG's own units; the page scales each SVG
# down to its column, so these are proportions, not screen pixels.
PAGE_TITLE = "Mailbox report"
# C7, a2's add (d): the words an unscrubbed page carries on its face.
REAL_WARNING = "Holds real session names and times. Share only a --scrub copy."
SCRUBBED_WORDS = ("Scrubbed: names are role labels numbered by first mail, tags off a fixed list read "
                  f"{OTHER_TAG}, times are elapsed from the first message (T+0), and message numbers are "
                  "ranks in sent order.")
# Lengths of time, for the short forms (`3h10m`, `1d02h`) and the buckets.
SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 60 * SECONDS_PER_MINUTE
SECONDS_PER_DAY = 24 * SECONDS_PER_HOUR
# The role word a node carries for a name C5 gives no role.
NO_ROLE_WORD = "no role"
# The words beside C5's role source when it is a guess (C5 rule 4).
INFERRED = "inferred"
# The widest a chart draws by default: the page's column is 1000 px, and
# a chart this wide leaves a margin inside it.
CHART_WIDTH = 960
# About how wide one character of the 13 px label text is, to size a node
# box or a gutter from its words without measuring text (no script runs).
CHAR_WIDTH = 7.4
# Chart 1, the graph. A node is a box this tall, padded this much either
# side of its words; boxes in one row sit this far apart, rows this far
# apart center to center (room for the arrows and their counts between),
# and the drawing keeps this margin.
NODE_HEIGHT = 34
NODE_PAD_X = 14
NODE_GAP = 44
GRAPH_ROW_GAP = 130
GRAPH_MARGIN = 28
# An arrow bends this far to the right of its travel at its middle, so the
# two directions of one pair never lie on each other; it stops this far
# short of a box; its head is this long and this wide either side.
EDGE_BEND = 16
EDGE_GAP = 4
ARROW_LENGTH = 10
ARROW_HALF_WIDTH = 5
# The outline each role's node draws (C5, rule 9: role never by color):
# an orchestrator a square box with a heavy line, a worker a rounded pill,
# a peer a box pointed at both ends, a name with no role a dashed box.
ORCHESTRATOR, WORKER, PEER = "orchestrator", "worker", "peer"
NODE_DASH = "5 3"
NODE_CORNER = 4

# The page's look. Colors are tokens, light and dark; every token pair of
# text on its surface holds its contrast in grayscale too, and no meaning
# rides on a color alone (shape, dash, position and words carry it).
PAGE_CSS = """
:root{--surface:#ffffff;--panel:#f6f8fa;--ink:#1f2328;--ink-2:#57606a;--rule:#d0d7de;
--node:#ffffff;--s1:#2f5fb3;--s2:#b8541a;--quiet:#8c959f;--warn:#fff4d6;--warn-ink:#4d3800}
@media (prefers-color-scheme: dark){:root{--surface:#16191d;--panel:#1e2228;--ink:#e6e8eb;
--ink-2:#a3aab2;--rule:#3a4048;--node:#1e2228;--s1:#7aa7f0;--s2:#f0a060;--quiet:#7d8590;
--warn:#3a2f12;--warn-ink:#f5e2b0}}
*{box-sizing:border-box}
body{margin:0;background:var(--surface);color:var(--ink);
font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:1000px;margin:0 auto;padding:24px 16px 48px}
h1{font-size:26px;margin:0 0 8px}
h2{font-size:19px;margin:32px 0 4px}
p{margin:6px 0}
.warning,.scrubbed{padding:8px 12px;border:2px solid var(--ink-2);border-radius:6px;font-weight:600}
.warning{background:var(--warn);color:var(--warn-ink)}
.scrubbed{background:var(--panel)}
.how{color:var(--ink-2);font-size:14px}
.figure{overflow-x:auto}
svg{display:block;max-width:100%;height:auto;margin-top:8px;background:var(--panel);border-radius:6px}
svg text{font:13px system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;fill:var(--ink)}
svg .small{font-size:11px;fill:var(--ink-2)}
svg .label{font-weight:600}
svg .halo{paint-order:stroke;stroke:var(--panel);stroke-width:4px;stroke-linejoin:round}
.node-box{fill:var(--node);stroke:var(--ink);stroke-width:1.5}
.orchestrator .node-box{stroke-width:3}
.edge-line{fill:none;stroke:var(--ink-2);stroke-width:1.5}
.edge-head{fill:var(--ink-2)}
.edge-count{font-weight:700}
footer{margin-top:40px;color:var(--ink-2);font-size:13px}
"""

# One message, closed (C7): exactly these eight facts. sent and read are
# aware datetimes on a real page, whole seconds since the first message on
# a scrubbed one, or None; tag is a string or None; refs a tuple of ints.
Record = collections.namedtuple("Record", "number sender recipient sent read size tag refs")
# One name in the report: its label, and C5's role, role source and level
# (all None for a name C5 gives no role: one with no inbox and no card).
Session = collections.namedtuple("Session", "name role source level")
# What extract hands on: the records in sent order, the sessions in first
# mail order, how many headers did not parse, and words for stderr (why a
# folder or record was not read), which never reach the page.
Mailbox = collections.namedtuple("Mailbox", "records sessions unparsed words")
# What the renderer draws, and all it ever sees: the records and sessions,
# the count of headers that did not parse, whether the page is scrubbed,
# and its "as of" (a time, as the records' times are, or None).
Page = collections.namedtuple("Page", "records sessions unparsed scrubbed as_of")


def load_board_module():
    """board/serve.py as a fresh module, compiled from its source in memory, its main() not run.

    The same careful load serve.py gives tc (its load_tc): no bytecode
    cache beside serve.py is read or written, so a cache another user
    planted on a shared mailbox's checkout never runs here.

    @interacts  reads board/serve.py; runs its top level (imports and
                constants). Writes no file.
    @deps       types; SERVE_PATH.
    @complexity O(s) over s bytes of serve.py (about 90 KB): one compile.
    @alloc      the source, freed on return; one module object, returned.
    """
    code = compile(SERVE_PATH.read_bytes(), str(SERVE_PATH), "exec", dont_inherit=True)
    board = types.ModuleType("board_serve_for_report")
    board.__file__ = str(SERVE_PATH)
    exec(code, board.__dict__)
    return board


def first_line_facts(line):
    """The tag and the #N references of one first body line: (tag or None, (numbers, in first-seen order)).

    The tag is the line's leading token, with one trailing colon taken
    off, when it fullmatches TAG_PATTERN. Nothing else of the line is
    returned or kept.

    @interacts  none; string work only.
    @deps       re; TAG_PATTERN, TAG_COLON, REF_PATTERN.
    @complexity O(c) over c characters of the line, at most
                TAG_READ_MAX_BYTES of them from a message.
    @alloc      the token and a tuple of ints, returned; the split, freed
                on return.
    """
    words = line.split(None, 1)
    token = words[0] if words else ""
    if token.endswith(TAG_COLON):
        token = token[:-len(TAG_COLON)]
    tag = token if TAG_PATTERN.fullmatch(token) else None
    refs = tuple(dict.fromkeys(int(number) for number in REF_PATTERN.findall(line)))
    return tag, refs


def parse_head(data):
    """A message's head bytes `data` as (sent datetime or None, tag or None, refs).

    The header is the first line; it parses only when it ends inside
    `data`, is UTF-8 and fullmatches HEADER_PATTERN with a time that has
    its offset. One blank line after it is passed over, and the next line
    is the first body line (first_line_facts), cut where `data` ends.

    @interacts  none; bytes and string work only.
    @deps       datetime; HEADER_PATTERN, first_line_facts.
    @complexity O(b) over b bytes of `data`, at most
                MESSAGE_HEADER_MAX_BYTES + TAG_READ_MAX_BYTES.
    @alloc      the decoded lines, freed on return; the facts, returned.
    """
    header, newline, rest = data.partition(b"\n")
    sent = None
    if newline:
        try:
            found = HEADER_PATTERN.fullmatch(header.decode("utf-8"))
            if found is not None:
                sent = datetime.datetime.fromisoformat(found.group("sent"))
        except ValueError:
            sent = None
    if rest.startswith(b"\n"):
        rest = rest[1:]
    tag, refs = first_line_facts(rest.partition(b"\n")[0].decode("utf-8", "replace") if newline else "")
    return sent, tag, refs


def read_head(name, folder_fd, limit):
    """At most `limit` bytes from the start of the message `name` in the folder open at `folder_fd`; None when it is not a regular file or cannot be read.

    Opened by name in the folder's descriptor (D35), never through a link
    and never blocking, and checked by fstat before any read.

    @interacts  opens, fstats and reads one file, and closes it.
    @deps       os, stat; HEAD_OPEN_FLAGS.
    @complexity O(limit).
    @alloc      the bytes read, returned; one descriptor, closed.
    """
    try:
        fd = os.open(name, HEAD_OPEN_FLAGS, dir_fd=folder_fd)
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


def parse_time(text):
    """A read-time record's time text as an aware datetime, or None.

    @interacts  none.
    @deps       datetime.
    @complexity O(1).
    @alloc      one datetime.
    """
    if text is None:
        return None
    try:
        when = datetime.datetime.fromisoformat(text)
    except ValueError:
        return None
    return when if when.tzinfo is not None else None


def sent_order(record):
    """The sort key of sent order: messages with a sent time by that time, then by number; those with none last, by number.

    @interacts  none.
    @deps       none.
    @complexity O(1).
    @alloc      one tuple.
    """
    if record.sent is None:
        return (1, 0, record.number, record.sender, record.recipient)
    when = record.sent.timestamp() if isinstance(record.sent, datetime.datetime) else record.sent
    return (0, when, record.number, record.sender, record.recipient)


def walk_messages(tc, head_limit):
    """Every message in the mailbox as (records, names with an inbox, words), records unsorted.

    tc's pinned walk (D35), as tc log walks: mail/ opened once, each
    to-<name>/ by its name in it and its read/ by name in the inbox's
    descriptor (tc.open_inbox), each listed in its own descriptor
    (tc.message_files: regular files only, never a link). A name that is
    not a mailbox name under C0 is passed by. A message in read/ with the
    same recipient, number and sender as one in the inbox counts once, as
    the inbox copy (serve.py's rule). Each read/ that holds messages has
    its .read-times read once, through tc.read_times.

    @interacts  see the module block's extract.
    @deps       contextlib, os; tc.open_mail, tc.open_inbox, tc.unpin,
                tc.message_files, tc.read_times, tc.valid_name,
                tc.MESSAGE_NAME_PATTERN; read_head, parse_head, parse_time,
                Record.
    @complexity O(n log n + T + t + R) over n inboxes, T names listed, t
                messages read (head_limit bytes each) and R record bytes.
    @alloc      one Record per message, returned; two descriptors per
                inbox, closed before return.
    """
    found, boxes, words = {}, set(), []
    with contextlib.ExitStack() as held:
        try:
            mail_fd = tc.open_mail()
        except OSError as err:
            return [], boxes, [f"could not open {tc.MAIL} ({err.strerror})"]
        if mail_fd is None:
            return [], boxes, words
        held.callback(os.close, mail_fd)
        try:
            entries = sorted(entry for entry in os.listdir(mail_fd) if entry.startswith(INBOX_PREFIX))
        except OSError as err:
            return [], boxes, [f"could not list {tc.MAIL} ({err.strerror})"]
        for entry in entries:
            to = entry[len(INBOX_PREFIX):]
            if not tc.valid_name(to):
                continue
            inbox = tc.open_inbox(mail_fd, to)
            held.callback(tc.unpin, inbox.read, inbox.box)
            if inbox.box.fd is None:
                if inbox.box.problem is not None:
                    boxes.add(to)
                    words.append(inbox.box.problem)
                continue
            boxes.add(to)
            for folder, pinned, in_read in ((inbox.path, inbox.box, False),
                                            (inbox.path / READ_FOLDER, inbox.read, True)):
                if pinned.fd is None:
                    if pinned.problem is not None:
                        words.append(pinned.problem)
                    continue
                messages, _, problem = tc.message_files(folder, pinned.fd)
                if problem is not None:
                    words.append(problem)
                times, why = tc.read_times(pinned, folder) if in_read and messages else ({}, None)
                if why is not None:
                    words.append(why)
                for path, st in messages:
                    named = tc.MESSAGE_NAME_PATTERN.fullmatch(path.name)
                    if named is None:
                        continue
                    number, sender = int(named.group(1)), named.group(2)
                    if (to, number, sender) in found:
                        continue
                    data = read_head(path.name, pinned.fd, head_limit)
                    sent, tag, refs = parse_head(data) if data is not None else (None, None, ())
                    read = parse_time(times.get(path.name)) if in_read else None
                    found[(to, number, sender)] = Record(number, sender, to, sent, read, st.st_size, tag, refs)
    return list(found.values()), boxes, words


def read_reports_to(tc, board):
    """Each card's reports_to, as {name: {"reports_to": name or None}}: the one card field the report reads.

    Each cards/<name>.json is read through tc.read_regular_file (a regular
    file only, never through a link, at most CARD_READ_MAX_BYTES); one
    that does not read or is not a JSON object is passed by, as the board
    passes it by. Only reports_to is kept, through serve.py's card_text.

    @interacts  globs cards/ and reads each card. Writes nothing.
    @deps       json; tc.CARDS, tc.read_regular_file, tc.valid_name,
                tc.CARD_READ_MAX_BYTES; board.card_text.
    @complexity O(c) over c cards (a few dozen), each at most
                CARD_READ_MAX_BYTES.
    @alloc      one small dict per card, returned.
    """
    cards = {}
    try:
        paths = sorted(tc.CARDS.glob(f"*{CARD_SUFFIX}"))
    except OSError:
        return cards
    for path in paths:
        if not tc.valid_name(path.stem):
            continue
        try:
            card = json.loads(tc.read_regular_file(path, tc.CARD_READ_MAX_BYTES))
        except (OSError, ValueError, RecursionError):
            continue
        if isinstance(card, dict):
            cards[path.stem] = {"reports_to": board.card_text(card, "reports_to")}
    return cards


def extract(tc):
    """The mailbox's facts (C7): a Mailbox of records in sent order, sessions in first-mail order with C5's roles, the count of headers that did not parse, and words for stderr.

    C5's nodes are the names with an inbox or a card. Their partners are
    counted as the board counts them (every message between two names,
    both ways, a name's notes to itself left out), and serve.py's
    hierarchy() gives each node its role, role source and level. A name
    that only sends (no inbox, no card) is not a node: its Session has
    no role.

    @interacts  see the module block's extract.
    @deps       walk_messages, read_reports_to, load_board_module,
                sent_order; Mailbox, Session; tc.MESSAGE_HEADER_MAX_BYTES;
                TAG_READ_MAX_BYTES.
    @complexity see the module block.
    @alloc      see the module block.
    """
    board = load_board_module()
    records, boxes, words = walk_messages(tc, tc.MESSAGE_HEADER_MAX_BYTES + TAG_READ_MAX_BYTES)
    records.sort(key=sent_order)
    cards = read_reports_to(tc, board)
    nodes = boxes | set(cards)
    partners = {}
    for record in records:
        if record.sender == record.recipient:
            continue
        for one, other in ((record.sender, record.recipient), (record.recipient, record.sender)):
            mine = partners.setdefault(one, {})
            mine[other] = mine.get(other, 0) + 1
    _, roles, levels = board.hierarchy(nodes, cards, partners)
    sessions = {}
    for record in records:
        for name in (record.sender, record.recipient):
            if name not in sessions:
                role, source = roles.get(name, (None, None))
                sessions[name] = Session(name, role, source, levels.get(name))
    unparsed = sum(1 for record in records if record.sent is None)
    return Mailbox(tuple(records), tuple(sessions.values()), unparsed, tuple(words))


def page_of(mailbox, at):
    """The unscrubbed Page of `mailbox`, as of `at` (an aware datetime, `--at`) or, when None, the last message's sent time.

    @interacts  none; pure.
    @deps       Page.
    @complexity O(t) over t records, for the last sent time.
    @alloc      one Page, returned; it shares the mailbox's tuples.
    """
    sent = [record.sent for record in mailbox.records if record.sent is not None]
    as_of = at if at is not None else (max(sent, key=lambda when: when.timestamp()) if sent else None)
    return Page(mailbox.records, mailbox.sessions, mailbox.unparsed, False, as_of)


def scrub(page):
    """`page` made safe to share (C7): a Page whose records hold no real name, time, number or off-list tag.

    - Names become role labels from C5's roles, numbered per role in
      order of first mail (the order of page.sessions, which extract
      builds in sent order): orchestrator-1, worker-1, peer-1, and
      session-1 for a name C5 gives no role.
    - A tag not in SCRUB_TAGS becomes OTHER_TAG.
    - Every time becomes whole seconds since the first sent time (None
      when no message has one), the "as of" too.
    - Numbers become ranks from 1 in sent order (the records' order), and
      each #N reference the rank of the first message numbered N; a
      reference to no message here is dropped.

    @interacts  none; pure.
    @deps       datetime; Page, Record, Session, SCRUB_TAGS, OTHER_TAG,
                NO_ROLE_LABEL.
    @complexity O(t + r + s) over t records, r references and s sessions.
    @alloc      one new Page, its records and sessions, and three maps
                (labels, ranks, counters), freed on return.
    """
    counters, labels, sessions = {}, {}, []
    for session in page.sessions:
        role = session.role or NO_ROLE_LABEL
        counters[role] = counters.get(role, 0) + 1
        labels[session.name] = f"{role}-{counters[role]}"
        sessions.append(Session(labels[session.name], session.role, session.source, session.level))
    sent = [record.sent.timestamp() for record in page.records if record.sent is not None]
    first = min(sent) if sent else None

    def elapsed(when):
        """`when` as whole seconds since `first`; None when either is None.

        @interacts  none.
        @deps       none.
        @complexity O(1).
        @alloc      none.
        """
        if when is None or first is None:
            return None
        return round(when.timestamp() - first)

    ranks = {}
    for rank, record in enumerate(page.records, 1):
        ranks.setdefault(record.number, rank)
    records = tuple(
        Record(rank, labels[record.sender], labels[record.recipient], elapsed(record.sent), elapsed(record.read),
               record.size, record.tag if record.tag is None or record.tag in SCRUB_TAGS else OTHER_TAG,
               tuple(ranks[ref] for ref in record.refs if ref in ranks))
        for rank, record in enumerate(page.records, 1))
    return Page(records, tuple(sessions), page.unparsed, True, elapsed(page.as_of))



# ---------- the renderer ----------

def esc(value):
    """`value` as text safe in an HTML or SVG text node or a quoted attribute (html.escape, quote=True).

    @interacts  none.
    @deps       html.
    @complexity O(c) over c characters.
    @alloc      one string, returned.
    """
    return html.escape(str(value), quote=True)


def num(value):
    """A coordinate as short, fixed text: one decimal, a trailing `.0` dropped, so the same number always prints the same.

    @interacts  none.
    @deps       none.
    @complexity O(1).
    @alloc      one string, returned.
    """
    text = f"{value:.1f}"
    return text[:-2] if text.endswith(".0") else text


def element(name, attrs=(), children=None):
    """One SVG or HTML element: `<name a="v" ...>children</name>`, or self-closed when `children` is None.

    Every attribute value passes through esc. `children` are strings the
    caller built with element() or esc(), never raw text.

    @interacts  none.
    @deps       esc.
    @complexity O(a + c) over a attributes and c characters of children.
    @alloc      one string, returned.
    """
    attributes = "".join(f' {key}="{esc(value)}"' for key, value in attrs)
    if children is None:
        return f"<{name}{attributes}/>"
    return f"<{name}{attributes}>{''.join(children)}</{name}>"


def text_at(x, y, words, css=None, anchor=None):
    """An SVG <text> of `words` at (x, y), escaped, with an optional class and text-anchor.

    @interacts  none.
    @deps       element, esc, num.
    @complexity O(c) over c characters.
    @alloc      one string, returned.
    """
    attrs = [("x", num(x)), ("y", num(y))]
    if css:
        attrs.append(("class", css))
    if anchor:
        attrs.append(("text-anchor", anchor))
    return element("text", attrs, [esc(words)])


def titled(words):
    """An SVG <title> child holding `words`: the hover text of the shape it sits in (no script needed).

    @interacts  none.
    @deps       element, esc.
    @complexity O(c).
    @alloc      one string.
    """
    return element("title", (), [esc(words)])


def svg_chart(key, width, height, title, desc, body):
    """One chart's SVG: its key, its size, a <title> and a <desc> (rule 9), and `body`.

    No xmlns: inline SVG in HTML needs none, and the page holds no
    address of any host.

    @interacts  none.
    @deps       element, esc, num.
    @complexity O(b) over b characters of body.
    @alloc      one string.
    """
    return element("svg", (("class", "chart"), ("data-chart", key), ("viewBox", f"0 0 {num(width)} {num(height)}"),
                           ("width", num(width)), ("height", num(height)), ("role", "img"),
                           ("aria-labelledby", f"{key}-title {key}-desc")),
                   [element("title", (("id", f"{key}-title"),), [esc(title)]),
                    element("desc", (("id", f"{key}-desc"),), [esc(desc)]), *body])


def figure(number, heading, how, svg):
    """One chart's section: a numbered heading, a line on how to read it, then its SVG.

    @interacts  none.
    @deps       element, esc.
    @complexity O(s) over s characters of the SVG.
    @alloc      one string.
    """
    return element("section", (("class", "figure"),),
                   [element("h2", (), [esc(f"{number}. {heading}")]), element("p", (("class", "how"),), [esc(how)]),
                    svg])


def plural(count, one, many=None):
    """`<count> <one>` or `<count> <many>` (one + "s" when many is None).

    @interacts  none.
    @deps       none.
    @complexity O(1).
    @alloc      one string.
    """
    return f"{count} {one if count == 1 else (many or one + 's')}"


def seconds_of(when):
    """A record's time as seconds on one line: a datetime's epoch seconds, or a scrubbed time's own number.

    @interacts  none.
    @deps       datetime.
    @complexity O(1).
    @alloc      none.
    """
    return when.timestamp() if isinstance(when, datetime.datetime) else float(when)


def span_text(seconds):
    """A length of time in C7's short form: `45s`, `12m`, `3h10m`, `1d02h`.

    @interacts  none.
    @deps       SECONDS_PER_MINUTE, SECONDS_PER_HOUR, SECONDS_PER_DAY.
    @complexity O(1).
    @alloc      one string.
    """
    whole = int(round(abs(seconds)))
    if whole < SECONDS_PER_MINUTE:
        return f"{whole}s"
    if whole < SECONDS_PER_HOUR:
        return f"{whole // SECONDS_PER_MINUTE}m"
    if whole < SECONDS_PER_DAY:
        return f"{whole // SECONDS_PER_HOUR}h{whole % SECONDS_PER_HOUR // SECONDS_PER_MINUTE:02d}m"
    return f"{whole // SECONDS_PER_DAY}d{whole % SECONDS_PER_DAY // SECONDS_PER_HOUR:02d}h"


def time_text(when):
    """A record's time as the page shows it: a real time with its date, clock and offset, or a scrubbed one as `T+3h10m` (`T+0` at the first message).

    @interacts  none.
    @deps       datetime; span_text.
    @complexity O(1).
    @alloc      one string.
    """
    if isinstance(when, datetime.datetime):
        return when.isoformat(sep=" ", timespec="minutes")
    if when == 0:
        return "T+0"
    return f"T{'+' if when > 0 else '-'}{span_text(when)}"


def role_word(session):
    """The words after a node's name: its C5 role, `· inferred` when its role is a guess, or NO_ROLE_WORD.

    @interacts  none.
    @deps       NO_ROLE_WORD, INFERRED.
    @complexity O(1).
    @alloc      one string.
    """
    if session.role is None:
        return NO_ROLE_WORD
    return f"{session.role} · {INFERRED}" if session.source == INFERRED else session.role


def node_shape(role, x, y, width):
    """The outline of a node of `role` centered at (x, y), `width` wide: C5's role as a shape.

    @interacts  none.
    @deps       element, num; NODE_HEIGHT, NODE_DASH, NODE_CORNER.
    @complexity O(1).
    @alloc      one string.
    """
    half_w, half_h = width / 2, NODE_HEIGHT / 2
    box = (("class", "node-box"), ("x", num(x - half_w)), ("y", num(y - half_h)), ("width", num(width)),
           ("height", num(NODE_HEIGHT)))
    if role == ORCHESTRATOR:
        return element("rect", box)
    if role == WORKER:
        return element("rect", box + (("rx", num(half_h)),))
    if role == PEER:
        points = ((x - half_w, y), (x - half_w + half_h, y - half_h), (x + half_w - half_h, y - half_h),
                  (x + half_w, y), (x + half_w - half_h, y + half_h), (x - half_w + half_h, y + half_h))
        return element("polygon", (("class", "node-box"), ("points", " ".join(f"{num(a)},{num(b)}" for a, b in points))))
    return element("rect", box + (("rx", num(NODE_CORNER)), ("stroke-dasharray", NODE_DASH)))


def box_edge(center, half, direction):
    """Where a ray from `center` along the unit vector `direction` leaves a box of half sizes `half`, plus EDGE_GAP.

    @interacts  none.
    @deps       math; EDGE_GAP.
    @complexity O(1).
    @alloc      one tuple.
    """
    (cx, cy), (hw, hh), (ux, uy) = center, half, direction
    reach = min(hw / abs(ux) if ux else math.inf, hh / abs(uy) if uy else math.inf) + EDGE_GAP
    return cx + ux * reach, cy + uy * reach


def chart_graph(page):
    """Chart 1, who talks to whom: one arrow per sender and recipient with its count, nodes by C5's level, shape and role word by role.

    Rows are C5's levels, top to bottom; a name with no role sits on a row
    below them. In a row, names keep first-mail order (page.sessions). An
    arrow is a curve that bends to the right of its travel, so a pair's two
    directions part; its head is drawn as a triangle (no marker, which
    would need a url() reference) and its count sits at its middle, with
    the full words in its title. A message a name sent itself draws no
    arrow; the caption counts them.

    @interacts  none; pure.
    @deps       math; element, text_at, titled, svg_chart, figure,
                node_shape, box_edge, role_word, plural, num; the graph
                constants.
    @complexity O(t + s + p) over t records, s sessions and p directed
                pairs.
    @alloc      the SVG text, returned; a few maps of s and p entries.
    """
    sessions = page.sessions
    if not sessions:
        svg = svg_chart("graph", CHART_WIDTH, NODE_HEIGHT * 2, "Who talks to whom", "No messages yet.",
                        [text_at(GRAPH_MARGIN, NODE_HEIGHT, "No messages yet.")])
        return figure(1, "Who talks to whom", "No messages yet.", svg)
    deepest = max((s.level for s in sessions if s.level is not None), default=-1)
    rows = {}
    for session in sessions:
        rows.setdefault(session.level if session.level is not None else deepest + 1, []).append(session)
    labels = {s.name: f"{s.name} · {role_word(s)}" for s in sessions}
    widths = {name: len(label) * CHAR_WIDTH + 2 * NODE_PAD_X for name, label in labels.items()}
    slot = max(widths.values()) + NODE_GAP
    widest = max(len(row) for row in rows.values())
    width = max(CHART_WIDTH, slot * widest + 2 * GRAPH_MARGIN)
    order = sorted(rows)
    height = 2 * GRAPH_MARGIN + NODE_HEIGHT + GRAPH_ROW_GAP * (len(order) - 1)
    at = {}
    for line, level in enumerate(order):
        row = rows[level]
        start = (width - slot * len(row)) / 2
        for place, session in enumerate(row):
            at[session.name] = (start + slot * (place + 0.5), GRAPH_MARGIN + NODE_HEIGHT / 2 + GRAPH_ROW_GAP * line)
    counts, selves = {}, 0
    for record in page.records:
        if record.sender == record.recipient:
            selves += 1
            continue
        pair = (record.sender, record.recipient)
        counts[pair] = counts.get(pair, 0) + 1
    edges = []
    for (sender, recipient), count in counts.items():
        (sx, sy), (rx, ry) = at[sender], at[recipient]
        length = math.hypot(rx - sx, ry - sy) or 1
        ux, uy = (rx - sx) / length, (ry - sy) / length
        start = box_edge((sx, sy), (widths[sender] / 2, NODE_HEIGHT / 2), (ux, uy))
        end = box_edge((rx, ry), (widths[recipient] / 2, NODE_HEIGHT / 2), (-ux, -uy))
        normal = (-uy, ux)
        control = ((start[0] + end[0]) / 2 + 2 * EDGE_BEND * normal[0],
                   (start[1] + end[1]) / 2 + 2 * EDGE_BEND * normal[1])
        tx, ty = end[0] - control[0], end[1] - control[1]
        tangent = math.hypot(tx, ty) or 1
        tx, ty = tx / tangent, ty / tangent
        base = (end[0] - tx * ARROW_LENGTH, end[1] - ty * ARROW_LENGTH)
        head = (end, (base[0] - ty * ARROW_HALF_WIDTH, base[1] + tx * ARROW_HALF_WIDTH),
                (base[0] + ty * ARROW_HALF_WIDTH, base[1] - tx * ARROW_HALF_WIDTH))
        middle = ((start[0] + 2 * control[0] + end[0]) / 4, (start[1] + 2 * control[1] + end[1]) / 4)
        edges.append(element("g", (("class", "edge"),), [
            titled(f"{sender} to {recipient}: {plural(count, 'message')}"),
            element("path", (("class", "edge-line"), ("d", f"M{num(start[0])},{num(start[1])} Q{num(control[0])},"
                                                          f"{num(control[1])} {num(base[0])},{num(base[1])}"))),
            element("polygon", (("class", "edge-head"), ("points", " ".join(f"{num(a)},{num(b)}" for a, b in head)))),
            text_at(middle[0], middle[1] + 4, str(count), "edge-count halo", "middle")]))
    nodes = []
    for session in sessions:
        x, y = at[session.name]
        role = session.role or NO_ROLE_WORD
        nodes.append(element("g", (("class", f"node {role.replace(' ', '-')}"), ("data-role", role)), [
            titled(labels[session.name]), node_shape(session.role, x, y, widths[session.name]),
            text_at(x, y + 4, labels[session.name], "label", "middle")]))
    how = ("One arrow for each sender and recipient, its count at its middle. Arrows bend to the right of their "
           "travel, so a pair's two directions part. Shape and words give each role: a square box with a heavy "
           "line is an orchestrator, a rounded one a worker, a box pointed at both ends a peer, a dashed box a "
           "name with no role (no inbox and no card). Levels run top to bottom by the reports-to hints on cards "
           "and, where none, by who mails whom most.")
    if selves:
        how += f" {plural(selves, 'message')} a session sent itself draw no arrow."
    desc = (f"A graph of {plural(len(sessions), 'session')} and {plural(len(counts), 'arrow')}, each arrow "
            "labeled with how many messages went that way.")
    return figure(1, "Who talks to whom", how, svg_chart("graph", width, height, "Who talks to whom", desc,
                                                          edges + nodes))


def summary_lines(page):
    """The page's opening lines: the warning or the scrub line, the counts and span, the as-of, and the headers that did not parse.

    @interacts  none; pure.
    @deps       element, esc, plural, time_text, seconds_of; REAL_WARNING,
                SCRUBBED_WORDS.
    @complexity O(t) over t records.
    @alloc      a list of strings, returned.
    """
    lines = [element("p", (("class", "scrubbed"),), [esc(SCRUBBED_WORDS)]) if page.scrubbed else
             element("p", (("class", "warning"),), [esc(f"Warning: {REAL_WARNING}")])]
    sent = [r.sent for r in page.records if r.sent is not None]
    if not page.records:
        lines.append(element("p", (), [esc("No messages yet.")]))
    else:
        span = ""
        if sent:
            first, last = min(sent, key=seconds_of), max(sent, key=seconds_of)
            span = f", sent from {time_text(first)} to {time_text(last)}"
        lines.append(element("p", (), [esc(f"{plural(len(page.records), 'message')} among "
                                           f"{plural(len(page.sessions), 'session')}{span}.")]))
    if page.as_of is not None:
        lines.append(element("p", (("class", "as-of"),), [esc(f"As of {time_text(page.as_of)}.")]))
    if page.unparsed:
        them = "it" if page.unparsed == 1 else "them"
        lines.append(element("p", (), [esc(f"{plural(page.unparsed, 'message')} had a header line that did not "
                                           f"parse, so the time charts (2 to 5) leave {them} out; chart 1 counts "
                                           f"{them}.")]))
    return lines


# The charts, in page order. Each takes the Page and returns its section.
CHARTS = (chart_graph,)


def render(page):
    """`page` as one self-contained HTML file (C7): inline CSS and inline SVG, no script, no link, nothing fetched.

    Pure: no clock, no file, no environment. The same page gives the same
    string, byte for byte.

    @interacts  none; pure.
    @deps       element, esc, summary_lines, CHARTS; PAGE_TITLE, PAGE_CSS.
    @complexity O(t + s + p) over t records, s sessions and p pairs, as
                each chart says.
    @alloc      the page text, returned; each chart's text while built.
    """
    body = [element("h1", (), [esc(PAGE_TITLE)]), *summary_lines(page), *(chart(page) for chart in CHARTS),
            element("footer", (), [esc("Made by tc report from each message's file name, size and header time, "
                                       "the read-time records, a tag and #N references from each message's first "
                                       "line, and each card's reports-to. No other text of any message is in "
                                       "this file.")])]
    head = element("head", (), ['<meta charset="utf-8"/>',
                                '<meta name="viewport" content="width=device-width, initial-scale=1"/>',
                                element("title", (), [esc(PAGE_TITLE)]), element("style", (), [PAGE_CSS])])
    return "<!doctype html>\n" + element("html", (("lang", "en"),), [head, element("body", (), [
        element("main", (), body)])]) + "\n"
