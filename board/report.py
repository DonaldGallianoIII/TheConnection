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
import json
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
