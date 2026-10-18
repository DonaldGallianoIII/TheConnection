"""
report.py: `tc report`'s extractor, scrub and renderer (contract C7,
decision D42). tc loads this file from its own folder, from source, in
memory, and calls report(); nothing here runs on its own.

Model:  Claude Opus 5.5 (the DASH lane agent), 2026-10-17
Status: unreviewed

Three steps, each a pure handoff to the next, then one call for tc:

1. extract(tc, board): one pinned walk of every mail/to-*/ and its read/
   (D35, through tc's own open_mail, open_inbox and message_files, as tc
   log walks), one bounded read per message, one read of each read/'s
   .read-times (tc's read_times: C2's rules), and cards/*.json for
   reports_to only. Out comes one closed Record per message and one
   Session per name, with C5's role from board/serve.py's own
   hierarchy(), loaded from source (load_board_module), never copied.
2. page_of(mailbox, at), then scrub(page) for --scrub: names to role
   labels by first mail, tags off SCRUB_TAGS to `other`, every time to
   seconds from the first message, numbers to ranks. It runs on the
   records, before the renderer, so the renderer never sees a real
   name, time or number on a scrubbed page.
3. render(page): records in, one HTML string out. Pure: inline CSS and
   inline SVG, no script, no link, no url(, nothing fetched (D26); every
   text node and attribute escaped; no clock read, so the same page gives
   the same bytes. Charts 1 to 5 as C7 lists them (chart_graph,
   chart_senders, chart_read, chart_quiet, chart_answers).
4. report(tc, board, scrubbed, at): all of it, for tc's cmd_report.

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
            each read/'s .read-times through tc.read_times; globs cards/
            and reads each card through tc.read_regular_file. Writes
            nothing. load_board_module reads board/serve.py and runs its
            top level (imports and constants; its main() is not run).
            scrub and render touch nothing outside their arguments.
@deps       python3 stdlib (collections, datetime, html, json,
            math, os, pathlib, re, stat, types); the tc module its caller
            passes; board/serve.py (hierarchy, card_text).
@complexity extract O(n log n + T + t log t + R + c) over n inboxes, T
            names in every inbox and read/, t messages ever (low
            thousands after weeks of heavy use), each read at most
            MESSAGE_HEADER_MAX_BYTES + TAG_READ_MAX_BYTES, R bytes of the
            read-time records and c cards; plus serve.py's hierarchy,
            O(n + p + e), and first_mail_levels, O(t + n log n + e).
            scrub O(t + r + s) over r references and s sessions. render
            O(s x t + t log t + p + d log d + g x q) over p directed
            pairs, d dots in charts 3 and 5 (each strip sorted for its
            median), g quiet gaps and q hatch lines per gap (at most
            CHART_WIDTH / HATCH_STEP + LANE_HEIGHT / HATCH_STEP); the
            s x t term is chart 3's and chart 4's pass over the records
            once per session (tens of sessions), the t log t chart 4's
            sort of each lane's times.
@alloc      extract: one Record per message and one Session per name,
            returned; each inbox's two descriptors, closed before it
            returns; each message's head bytes, freed per message. scrub:
            a new Page of new Records. render: the page's text, O(t)
            bytes (measured: 2000 messages among 16 names made 1.8 MB, in
            0.3 s for the whole tc report), and each chart's text while it
            is built.
"""

import collections
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

# What C7's read window adds past the header's own bound (tc's
# MESSAGE_HEADER_MAX_BYTES): each message is read from its start for at
# most MESSAGE_HEADER_MAX_BYTES + TAG_READ_MAX_BYTES bytes, so its first
# body line gets whatever of that window its header leaves. A header at the
# bound leaves this much, enough for a tag (24 characters at most) and a
# reply's #N; a usual header of about 60 bytes leaves about 4,300. Not a
# bound on the body line by itself (fix round 1, LOW-20). It keeps the read
# of a 1 MiB body to one small block.
TAG_READ_MAX_BYTES = 256
# A tag (C7): a leading token of capitals, digits and dashes, 2 to 24
# characters, once one trailing colon is stripped.
TAG_PATTERN = re.compile(r"[A-Z][A-Z0-9-]{1,23}")
TAG_COLON = ":"
# A reference to an earlier message on a first line: `#` and its number.
REF_PATTERN = re.compile(r"#([0-9]+)")
# The most digits a #N may have to count as a reference (fix round 1,
# LOW-1). A billion messages is far past any mailbox's history, and a
# longer run of digits, which Python refuses to turn into an int past 4300
# of them, is no reference: it is passed by, never a traceback.
REF_MAX_DIGITS = 9
# A line that starts this way is a tc header, whether or not its time
# parses; only after one is the next line a first body line (fix round 1,
# LOW-6: C7 reads nothing past a body's first line).
TC_HEADER_START = re.compile(r"# #[0-9]+ from ")
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
# The tags a scrubbed page keeps as they are (C7), in C7's order: a tuple,
# not a set, so the scrub note lists them in the same order every run. The
# project's own working words, none of which names a person, a project or
# a machine; any other tag reads OTHER_TAG.
SCRUB_TAGS = ("ANSWER", "FYI", "QUESTION", "PLAN", "PLAN-READY", "PLAN-CHECK", "PLAN-EDIT", "PLAN-EDITED",
              "PLAN-REVIEWED", "CORRECTION", "HEADS-UP", "MERGE", "REVIEW", "STATUS", "BLOCKED", "DONE", "BREACH")
OTHER_TAG = "other"
# A stand-in name that sorts in first-mail order, zero-padded so text
# order is number order for any mailbox (first_mail_levels).
FIRST_MAIL_KEY = "{place:012d}"
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
                  f"ranks in sent order. The tags kept as they are: {', '.join(SCRUB_TAGS)}.")
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
# About how wide one character of the bold TEXT_UNITS label text is, to
# size a node box or fit a row's name without measuring text (no script
# runs). Set from wide letters (a run of `q` or `w` in a sans bold face),
# not the average, so a long name errs short of the edge. The plain small
# text is narrower per character.
CHAR_WIDTH = 9.0
SMALL_CHAR_WIDTH = 6.8
# Text sizes in the SVGs' own units: labels, and the smaller words under
# and beside them, the smallest text any chart draws.
TEXT_UNITS = 13
SMALL_TEXT_UNITS = 12
# The fewest pixels any text may draw at (fix round 1, MEDIUM-1). Each SVG
# gets a CSS min-width of its width x MIN_TEXT_PX / SMALL_TEXT_UNITS, so on
# a narrow screen its .figure scrolls sideways instead of the chart
# shrinking its text below this.
MIN_TEXT_PX = 11
# What a cut name or line starts with, three periods (the voice rules ban
# the one-character ellipsis); the end of the words is kept after it.
CUT_MARK = "..."
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
# An arrow between two boxes on one line with others between them bends
# further, by this share of its length, so it arcs over the boxes between
# its ends instead of through them.
EDGE_BEND_PER_LENGTH = 0.18
# A level with more names than this wraps onto further lines, so the
# graph stays near the page's width (and its width floor, MIN_TEXT_PX,
# near the column) when names are short.
GRAPH_LINE_MAX_NODES = 5
EDGE_GAP = 4
ARROW_LENGTH = 10
ARROW_HALF_WIDTH = 5
# The outline each role's node draws (C5, rule 9: role never by color):
# an orchestrator a square box with a heavy line, a worker a rounded pill,
# a peer a box pointed at both ends, a name with no role a dashed box.
ORCHESTRATOR, WORKER, PEER = "orchestrator", "worker", "peer"
NODE_DASH = "5 3"
NODE_CORNER = 4

# The row charts (2 to 5). Each row's words sit in a gutter this wide at
# the left, ending at its right edge; words wider than the room left of
# that edge are cut by fit_words (fix round 1, MEDIUM-2: a name of up to
# C0's 64 characters would otherwise run past x 0 and be clipped). The
# plot runs from the gutter to this far short of the right edge. The
# charts keep this much room above the first row and this much below the
# last for the time axis.
LABEL_GUTTER = 280
PLOT_RIGHT_PAD = 24
CHART_TOP = 16
AXIS_HEIGHT = 40
# The gap between a row's words and its plot, and between a word line
# and the next.
LABEL_GAP = 10
LINE_GAP = 15
# Chart 2. A row is this tall and its tallest bar this tall; a bar is
# this much narrower than its bucket, so neighbors stay apart.
SENDER_ROW_HEIGHT = 46
BAR_MAX_HEIGHT = 30
BAR_GAP = 1
# Chart 2's bucket rule (C7): one hour per bar while the report spans a
# week or less (at most 169 bars, about 4 units wide each in the plot),
# one day per bar past that, so a long history stays readable.
HOURLY_UP_TO_SECONDS = 7 * 24 * 60 * 60
# The words for each bucket.
BUCKET_WORDS = {"hour": "an hour", "day": "a day"}

# Charts 3 and 5, the delay strips. A strip is this tall; its dots have
# this radius and sit at these offsets from its middle line in turn, so
# dots at one delay stay apart; the median's tick reaches this far up and
# down. Delays run on a log scale (a minute and a day both need room), up
# to the longest delay drawn but never less than DELAY_SCALE_MIN_SECONDS,
# with a grid line at each of DELAY_TICKS_SECONDS that fits.
STRIP_HEIGHT = 56
DOT_RADIUS = 5
DOT_OFFSETS = (0, -7, 7)
MEDIAN_REACH = 15
DELAY_SCALE_MIN_SECONDS = 60
DELAY_TICKS_SECONDS = (0, 60, 600, 3600, 6 * 3600, 24 * 3600, 7 * 24 * 3600, 30 * 24 * 3600)
# The far end of the delay axis is labeled with the longest delay drawn;
# a tick label nearer it than this is left off (its grid line stays), so
# the two labels, each about five characters, never overlap.
DELAY_END_GAP = 48

# Chart 4. A gap of this long or more between two of a session's
# messages, sent or received, is quiet: hatched and labeled. Three hours:
# longer than a listener's wait (tc's DEFAULT_WAIT_SECONDS, 110 minutes),
# so a quiet stretch is one where nobody mailed, not one wait ending.
QUIET_GAP_SECONDS = 3 * 60 * 60
# A lane is this tall; a tick reaches this far from its middle line, a
# marker is this big either side of its point, and hatch lines run this
# far apart. A lane's own words end this far left of the plot, leaving
# room for its series' labels between them.
LANE_HEIGHT = 64
TICK_LENGTH = 14
MARKER_SIZE = 4
HATCH_STEP = 7
SERIES_LABEL_ROOM = 92
# The two fixed lists every series takes its look from (rule 9): series i
# in a plot gets SERIES_SHAPES[i], SERIES_DASHES[i] and SERIES_COLORS[i],
# so series that share a plot differ in marker shape and in dash, as well
# as color. Each shape's glyph labels the series in words beside it.
SERIES_SHAPES = ("triangle-up", "circle", "square", "diamond")
SERIES_DASHES = ("none", "3 2", "1 2", "6 2 1 2")
SERIES_COLORS = ("s1", "s2", "s3", "s4")
SHAPE_GLYPHS = {"triangle-up": "▲", "circle": "●", "square": "■", "diamond": "◆"}

# Chart 5 (C7, pause DASH-1 as a2 settled it). An ask is a message tagged
# one of these, or any message an answer names, whatever its tag. Asks
# with no reply that names them are counted in words, never called
# unanswered: a session that does not put #N on its first line answers
# without naming, and ASK_CAVEAT says so under the chart.
ASK_TAGS = ("QUESTION", "PLAN-READY", "PLAN-CHECK", "MERGE", "BLOCKED")
ASK_CAVEAT = ("A session that does not put #N on its first line answers without naming the ask, so this count "
              "can include asks that were answered.")

# The page's look. Colors are tokens, light and dark; every token pair of
# text on its surface holds its contrast in grayscale too, and no meaning
# rides on a color alone (shape, dash, position and words carry it).
PAGE_CSS = """
:root{--surface:#ffffff;--panel:#f6f8fa;--ink:#1f2328;--ink-2:#57606a;--rule:#d0d7de;
--node:#ffffff;--s1:#2f5fb3;--s2:#b8541a;--s3:#2e7d4f;--s4:#7b3fa0;--quiet:#8c959f;--warn:#fff4d6;
--warn-ink:#4d3800}
@media (prefers-color-scheme: dark){:root{--surface:#16191d;--panel:#1e2228;--ink:#e6e8eb;
--ink-2:#a3aab2;--rule:#3a4048;--node:#1e2228;--s1:#7aa7f0;--s2:#f0a060;--s3:#6cc58f;--s4:#c39be0;
--quiet:#7d8590;
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
svg text{font:TEXT_UNITSpx system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;fill:var(--ink)}
svg .small{font-size:SMALL_TEXT_UNITSpx;fill:var(--ink-2)}
svg .label{font-weight:600}
svg .halo{paint-order:stroke;stroke:var(--panel);stroke-width:4px;stroke-linejoin:round}
.node-box{fill:var(--node);stroke:var(--ink);stroke-width:1.5}
.orchestrator .node-box{stroke-width:3}
.edge-line{fill:none;stroke:var(--ink-2);stroke-width:1.5}
.edge-head{fill:var(--ink-2)}
.edge-count{font-weight:700}
.axis{stroke:var(--rule);stroke-width:1}
.bar{fill:var(--s1)}
.grid{stroke:var(--rule);stroke-width:1;stroke-dasharray:2 3}
.dot{fill:var(--s1);stroke:var(--panel);stroke-width:1.5}
.median{stroke:var(--ink);stroke-width:2.5}
.s1{fill:var(--s1);stroke:var(--s1)}.s2{fill:var(--s2);stroke:var(--s2)}
.s3{fill:var(--s3);stroke:var(--s3)}.s4{fill:var(--s4);stroke:var(--s4)}
.tick-line{fill:none;stroke-width:1.5}
.quiet-box{fill:none;stroke:var(--quiet);stroke-width:1;stroke-dasharray:4 2}
.hatch{fill:none;stroke:var(--quiet);stroke-width:1}
footer{margin-top:40px;color:var(--ink-2);font-size:13px}
"""
# The two text sizes, from their constants, so the CSS and the width floor
# never disagree.
PAGE_CSS = PAGE_CSS.replace("SMALL_TEXT_UNITSpx", f"{SMALL_TEXT_UNITS}px").replace("TEXT_UNITSpx", f"{TEXT_UNITS}px")

# One message, closed (C7): exactly these eight facts. sent and read are
# aware datetimes on a real page, whole seconds since the first message on
# a scrubbed one, or None; tag is a string or None; refs a tuple of ints.
Record = collections.namedtuple("Record", "number sender recipient sent read size tag refs")
# One name in the report: its label, and C5's role, role source and level
# (all None for a name C5 gives no role: one with no inbox and no card).
Session = collections.namedtuple("Session", "name role source level")
# What extract hands on: the records in sent order, the sessions in first
# mail order, how many headers did not parse, words for stderr (why a
# folder or record was not read), which never reach the page, and how many
# folders could not be read (fix round 1, REC-13), which does.
Mailbox = collections.namedtuple("Mailbox", "records sessions unparsed words unreadable")
# What the renderer draws, and all it ever sees: the records and sessions,
# the count of headers that did not parse, whether the page is scrubbed,
# its "as of" (a time, as the records' times are, or None), and how many
# folders could not be read (0 unless given).
Page = collections.namedtuple("Page", "records sessions unparsed scrubbed as_of unreadable", defaults=(0,))


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

    A #N of more than REF_MAX_DIGITS digits is no reference.

    @interacts  none; string work only.
    @deps       re; TAG_PATTERN, TAG_COLON, REF_PATTERN, REF_MAX_DIGITS.
    @complexity O(c) over c characters of the line: from a message, the
                rest of the read window after the header, at most
                MESSAGE_HEADER_MAX_BYTES + TAG_READ_MAX_BYTES less the
                header's own bytes (about 4,300).
    @alloc      the token and a tuple of ints, returned; the split, freed
                on return.
    """
    words = line.split(None, 1)
    token = words[0] if words else ""
    if token.endswith(TAG_COLON):
        token = token[:-len(TAG_COLON)]
    tag = token if TAG_PATTERN.fullmatch(token) else None
    refs = tuple(dict.fromkeys(int(number) for number in REF_PATTERN.findall(line)
                               if len(number) <= REF_MAX_DIGITS))
    return tag, refs


def parse_head(data):
    """A message's head bytes `data` as (sent datetime or None, tag or None, refs).

    The header is the first line; it parses only when it ends inside
    `data`, is UTF-8 and fullmatches HEADER_PATTERN with a time that has
    its offset. Only when it is a tc header (TC_HEADER_START, its time
    parsed or not) is one blank line after it passed over and the next
    line read as the first body line (first_line_facts), cut where `data`
    ends; any other first line gives no tag and no refs (fix round 1,
    LOW-6).

    @interacts  none; bytes and string work only.
    @deps       datetime; HEADER_PATTERN, TC_HEADER_START, first_line_facts.
    @complexity O(b) over b bytes of `data`, at most
                MESSAGE_HEADER_MAX_BYTES + TAG_READ_MAX_BYTES.
    @alloc      the decoded lines, freed on return; the facts, returned.
    """
    header, newline, rest = data.partition(b"\n")
    if not newline:
        return None, None, ()
    try:
        line = header.decode("utf-8")
    except ValueError:
        return None, None, ()
    if TC_HEADER_START.match(line) is None:
        return None, None, ()
    sent = None
    found = HEADER_PATTERN.fullmatch(line)
    if found is not None:
        try:
            sent = datetime.datetime.fromisoformat(found.group("sent"))
        except ValueError:
            sent = None
    if rest.startswith(b"\n"):
        rest = rest[1:]
    tag, refs = first_line_facts(rest.partition(b"\n")[0].decode("utf-8", "replace"))
    return sent, tag, refs


def read_head(name, folder_fd, limit):
    """At most `limit` bytes from the start of the message `name` in the folder open at `folder_fd`; None when it is not a regular file or cannot be read. Raises FileNotFoundError when nothing has the name (a `tc read` moved it since the listing: the walk looks in read/, LOW-9).

    Opened by name in the folder's descriptor (D35), never through a link
    and never blocking, and checked by fstat before any read.

    @interacts  opens, fstats and reads one file, and closes it.
    @deps       os, stat; HEAD_OPEN_FLAGS.
    @complexity O(limit).
    @alloc      the bytes read, returned; one descriptor, closed.
    """
    try:
        fd = os.open(name, HEAD_OPEN_FLAGS, dir_fd=folder_fd)
    except FileNotFoundError:
        raise
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
    """The sort key of sent order: messages with a sent time by that time, then by number, then by size; those with none last, by number, then size.

    Never by a name (fix round 1, REC-3): on a scrubbed page the ranks,
    and the first-mail order the labels follow, would otherwise tell
    which real name sorts first. Two messages at one time with one number
    and one size keep the walk's order (inboxes by name): a known
    residual, rare, as only a hand-made twin can make it.

    @interacts  none.
    @deps       none.
    @complexity O(1).
    @alloc      one tuple.
    """
    if record.sent is None:
        return (1, 0, record.number, record.size)
    when = record.sent.timestamp() if isinstance(record.sent, datetime.datetime) else record.sent
    return (0, when, record.number, record.size)


def walk_messages(tc, head_limit):
    """Every message in the mailbox as (records, names with an inbox, words, folders missed), records unsorted; each folder it could not open or list is one entry of `folders missed`, its words in `words` too.

    tc's pinned walk (D35), as tc log walks: mail/ opened once, each
    to-<name>/ by its name in it and its read/ by name in the inbox's
    descriptor (tc.open_inbox), each listed in its own descriptor
    (tc.message_files: regular files only, never a link). A name that is
    not a mailbox name under C0 is passed by. A message in read/ with the
    same recipient, number and sender as one in the inbox counts once, as
    the inbox copy (serve.py's rule). Each read/'s .read-times is read
    once, through tc.read_times, when read/ holds messages or a message
    moved into it mid-walk.

    Fix round 1 (Claude Opus 5.5, unreviewed): LOW-2, each inbox's two
    descriptors close as soon as that inbox is walked, so a mailbox of
    many names never runs out of descriptors; LOW-9, a message the inbox
    listed that is gone by its read (a `tc read` moved it) is read once
    more by its name in read/, with its read time, never counted as a
    header that did not parse.

    @interacts  see the module block's extract.
    @deps       contextlib, os; tc.open_mail, tc.open_inbox, tc.unpin,
                tc.message_files, tc.read_times, tc.valid_name,
                tc.MESSAGE_NAME_PATTERN; read_head, parse_head, parse_time,
                Record.
    @complexity O(n log n + T + t log t + R) over n inboxes, T names
                listed, t messages read (head_limit bytes each, plus a
                sort of each folder's names in message_files) and R
                record bytes.
    @alloc      one Record per message, returned; mail/'s descriptor and
                one inbox's two at a time, each closed when done with.
    """
    found, boxes, words, missed = {}, set(), [], []
    try:
        mail_fd = tc.open_mail()
    except OSError as err:
        missed.append(f"could not open {tc.MAIL} ({err.strerror})")
        return [], boxes, missed, missed
    if mail_fd is None:
        return [], boxes, words, missed
    try:
        try:
            entries = sorted(entry for entry in os.listdir(mail_fd) if entry.startswith(INBOX_PREFIX))
        except OSError as err:
            missed.append(f"could not list {tc.MAIL} ({err.strerror})")
            return [], boxes, missed, missed
        for entry in entries:
            to = entry[len(INBOX_PREFIX):]
            if tc.valid_name(to):
                inbox = tc.open_inbox(mail_fd, to)
                try:
                    walk_inbox(tc, inbox, to, head_limit, found, boxes, words, missed)
                finally:
                    tc.unpin(inbox.read, inbox.box)
    finally:
        os.close(mail_fd)
    return list(found.values()), boxes, words, missed


def walk_inbox(tc, inbox, to, head_limit, found, boxes, words, missed):
    """One open inbox's messages, unread then read, into `found` (keyed by recipient, number and sender), its name into `boxes`, anything it could not read into `words`, and each folder it could not open or list into `missed` and `words`, as walk_messages says.

    @interacts  lists the inbox and its read/ through their descriptors,
                reads each message's head and read/'s record once.
    @deps       tc.message_files, tc.read_times, tc.MESSAGE_NAME_PATTERN;
                read_head, parse_head, parse_time, Record; READ_FOLDER.
    @complexity O(U + u log u + R) over U names in the two folders, u
                messages among them and R record bytes.
    @alloc      one Record per new message, into `found`; the record's
                map while the inbox is walked.
    """
    if inbox.box.fd is None:
        if inbox.box.problem is not None:
            boxes.add(to)
            words.append(inbox.box.problem)
            missed.append(inbox.box.problem)
        return
    boxes.add(to)
    read_path = inbox.path / READ_FOLDER
    times = None

    def read_times():
        """read/'s record, read once, on first need: {name in read/: time text}.

        @interacts  reads read/.read-times through tc.read_times, once.
        @deps       tc.read_times.
        @complexity O(R) over R record bytes.
        @alloc      the map, kept for this inbox.
        """
        nonlocal times
        if times is None:
            times, why = tc.read_times(inbox.read, read_path) if inbox.read.fd is not None else ({}, None)
            if why is not None:
                words.append(why)
        return times

    for folder, pinned, in_read in ((inbox.path, inbox.box, False), (read_path, inbox.read, True)):
        if pinned.fd is None:
            if pinned.problem is not None:
                words.append(pinned.problem)
                missed.append(pinned.problem)
            continue
        messages, _, problem = tc.message_files(folder, pinned.fd)
        if problem is not None:
            words.append(problem)
            if not messages:
                missed.append(problem)
        for path, st in messages:
            named = tc.MESSAGE_NAME_PATTERN.fullmatch(path.name)
            if named is None:
                continue
            number, sender = int(named.group(1)), named.group(2)
            if (to, number, sender) in found:
                continue
            moved = in_read
            try:
                data = read_head(path.name, pinned.fd, head_limit)
            except FileNotFoundError:
                data = None
                if not in_read and inbox.read.fd is not None:
                    try:
                        data, moved = read_head(path.name, inbox.read.fd, head_limit), True
                    except FileNotFoundError:
                        data = None
            sent, tag, refs = parse_head(data) if data is not None else (None, None, ())
            read = parse_time(read_times().get(path.name)) if moved else None
            found[(to, number, sender)] = Record(number, sender, to, sent, read, st.st_size, tag, refs)


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


def first_mail_levels(board, nodes, parents, records):
    """C5 rule 5's levels for `nodes` under `parents`, with any reports_to cycle broken at the member with the earliest first mail instead of the first name in sort order (fix round 1, LOW-10, the relay's addition).

    serve.py's levels_of breaks a cycle at the name that sorts first, and
    on a scrubbed page the top node would then tell which real name sorts
    first. So levels_of runs here over stand-in names that sort in
    first-mail order (`records` is in sent order; a node with no mail
    follows, by name, and is never drawn), and the levels are mapped
    back. serve.py, and the board's own layout, are unchanged; with no
    cycle the levels are the same either way.

    @interacts  none; pure.
    @deps       board.levels_of; FIRST_MAIL_KEY.
    @complexity O(t + n log n + e) over t records, n nodes and e parent
                edges.
    @alloc      two maps of n names and the parent map in stand-ins,
                freed on return; the levels, returned.
    """
    order, seen = [], set()
    for record in records:
        for name in (record.sender, record.recipient):
            if name in nodes and name not in seen:
                seen.add(name)
                order.append(name)
    order += sorted(set(nodes) - seen)
    key = {name: FIRST_MAIL_KEY.format(place=place) for place, name in enumerate(order)}
    back = {stand: name for name, stand in key.items()}
    levels = board.levels_of(set(key.values()), {key[child]: (key[parent], source)
                                                 for child, (parent, source) in parents.items()})
    return {back[stand]: level for stand, level in levels.items()}


def extract(tc, board=None):
    """The mailbox's facts (C7): a Mailbox of records in sent order, sessions in first-mail order with C5's roles, the count of headers that did not parse, and words for stderr.

    C5's nodes are the names with an inbox or a card. Their partners are
    counted as the board counts them (every message between two names,
    both ways, a name's notes to itself left out), and serve.py's
    hierarchy() gives each node its role, role source and level. A name
    that only sends (no inbox, no card) is not a node: its Session has
    no role. `board` is serve.py as load_board_module gives it, loaded
    here when None.

    @interacts  see the module block's extract.
    @deps       walk_messages, read_reports_to, load_board_module,
                sent_order, first_mail_levels; Mailbox, Session;
                tc.MESSAGE_HEADER_MAX_BYTES; TAG_READ_MAX_BYTES.
    @complexity see the module block.
    @alloc      see the module block.
    """
    board = load_board_module() if board is None else board
    records, boxes, words, missed = walk_messages(tc, tc.MESSAGE_HEADER_MAX_BYTES + TAG_READ_MAX_BYTES)
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
    parents, roles, levels = board.hierarchy(nodes, cards, partners)
    levels = first_mail_levels(board, nodes, parents, records)
    sessions = {}
    for record in records:
        for name in (record.sender, record.recipient):
            if name not in sessions:
                role, source = roles.get(name, (None, None))
                sessions[name] = Session(name, role, source, levels.get(name))
    unparsed = sum(1 for record in records if record.sent is None)
    return Mailbox(tuple(records), tuple(sessions.values()), unparsed, tuple(words), len(missed))


def page_of(mailbox, at):
    """The unscrubbed Page of `mailbox`, as of `at` (an aware datetime, `--at`) or, when None, the last message's sent time.

    @interacts  none; pure.
    @deps       Page.
    @complexity O(t) over t records, for the last sent time.
    @alloc      one Page, returned; it shares the mailbox's tuples.
    """
    sent = [record.sent for record in mailbox.records if record.sent is not None]
    as_of = at if at is not None else (max(sent, key=lambda when: when.timestamp()) if sent else None)
    return Page(mailbox.records, mailbox.sessions, mailbox.unparsed, False, as_of, mailbox.unreadable)


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

    No order on the page follows real name order (fix round 1, LOW-10 and
    REC-3): extract breaks a reports_to cycle at the earliest first mail
    (first_mail_levels), and sent order breaks ties by number and size
    (sent_order). Known residual: two messages at one time with one
    number and one size, which only a hand-made twin makes, keep the
    walk's order, inboxes by name.

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
    return Page(records, tuple(sessions), page.unparsed, True, elapsed(page.as_of), page.unreadable)


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


def text_at(x, y, words, css=None, anchor=None, whole=None):
    """An SVG <text> of `words` at (x, y), escaped, with an optional class and text-anchor; `whole`, when given, goes in a <title> inside it (the full words of a cut line).

    @interacts  none.
    @deps       element, esc, num, titled.
    @complexity O(c) over c characters.
    @alloc      one string, returned.
    """
    attrs = [("x", num(x)), ("y", num(y))]
    if css:
        attrs.append(("class", css))
    if anchor:
        attrs.append(("text-anchor", anchor))
    return element("text", attrs, [esc(words)] + ([titled(whole)] if whole is not None else []))


def char_width(css):
    """The estimated width of one character of text with class list `css`: SMALL_CHAR_WIDTH for the small words, CHAR_WIDTH for the rest.

    @interacts  none.
    @deps       CHAR_WIDTH, SMALL_CHAR_WIDTH.
    @complexity O(c) over c characters of `css`.
    @alloc      none.
    """
    return SMALL_CHAR_WIDTH if "small" in (css or "").split() else CHAR_WIDTH


def fit_words(words, room, css="label"):
    """`words` as they fit in `room` units of width, for text of class list `css` (char_width): (words to draw, the whole words when cut, else None).

    A cut keeps the end (session names differ most at their ends: the
    `-api`, the `-2`) after CUT_MARK, and the caller puts the whole in a
    <title> inside the text.

    @interacts  none.
    @deps       char_width; CUT_MARK.
    @complexity O(c) over c characters.
    @alloc      one string, returned.
    """
    fits = int(room // char_width(css))
    if len(words) <= fits:
        return words, None
    keep = max(0, fits - len(CUT_MARK))
    return CUT_MARK + (words[-keep:] if keep else ""), words


def titled(words):
    """An SVG <title> child holding `words`: the hover text of the shape it sits in (no script needed).

    @interacts  none.
    @deps       element, esc.
    @complexity O(c).
    @alloc      one string.
    """
    return element("title", (), [esc(words)])


def svg_chart(key, width, height, title, desc, body, top=0):
    """One chart's SVG: its key, its size, a <title> and a <desc> (rule 9), and `body`. `top` is the y the drawing starts at (chart 1 draws arcs above its first row).

    No xmlns: inline SVG in HTML needs none, and the page holds no
    address of any host. Its CSS min-width is its width x MIN_TEXT_PX /
    SMALL_TEXT_UNITS, rounded up (fix round 1, MEDIUM-1): the page may
    scale a chart down to fit its column, but never so far that its
    smallest text draws under MIN_TEXT_PX; past that its .figure scrolls.

    @interacts  none.
    @deps       element, esc, num.
    @complexity O(b) over b characters of body.
    @alloc      one string.
    """
    floor = math.ceil(width * MIN_TEXT_PX / SMALL_TEXT_UNITS)
    return element("svg", (("class", "chart"), ("data-chart", key),
                           ("viewBox", f"0 {num(top)} {num(width)} {num(height)}"),
                           ("width", num(width)), ("height", num(height)), ("style", f"min-width:{floor}px"),
                           ("role", "img"),
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


def node_label(session, scrubbed):
    """A node's words: its name and role word, or on a scrubbed page its label alone, which already names its role (`worker-1`, fix round 1, REC-10), with `· inferred` kept when its role is a guess.

    @interacts  none.
    @deps       role_word; INFERRED.
    @complexity O(1).
    @alloc      one string.
    """
    if scrubbed:
        return f"{session.name} · {INFERRED}" if session.role and session.source == INFERRED else session.name
    return f"{session.name} · {role_word(session)}"


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
        corners = " ".join(f"{num(a)},{num(b)}" for a, b in points)
        return element("polygon", (("class", "node-box"), ("points", corners)))
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
    below them. In a row, names keep first-mail order (page.sessions), at
    most GRAPH_LINE_MAX_NODES to a line, a longer level wrapping onto more
    lines. An arrow is a curve that bends to the right of its travel, so a
    pair's two directions part; one between two boxes on one line with
    others between them bends further, with its length, to arc past
    them. Its head is drawn as a triangle (no marker, which would need a
    url() reference) and its count sits at its middle, with the full
    words in its title. A message a name sent itself draws no
    arrow; the caption counts them.

    @interacts  none; pure.
    @deps       math; element, text_at, titled, svg_chart, figure,
                node_shape, node_label, box_edge, plural, num; the graph
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
    labels = {s.name: node_label(s, page.scrubbed) for s in sessions}
    widths = {name: len(label) * CHAR_WIDTH + 2 * NODE_PAD_X for name, label in labels.items()}
    slot = max(widths.values()) + NODE_GAP
    lines = [rows[level][first:first + GRAPH_LINE_MAX_NODES] for level in sorted(rows)
             for first in range(0, len(rows[level]), GRAPH_LINE_MAX_NODES)]
    widest = max(len(row) for row in lines)
    width = max(CHART_WIDTH, slot * widest + 2 * GRAPH_MARGIN)
    height = 2 * GRAPH_MARGIN + NODE_HEIGHT + GRAPH_ROW_GAP * (len(lines) - 1)
    at, seat = {}, {}
    for line, row in enumerate(lines):
        start = (width - slot * len(row)) / 2
        for place, session in enumerate(row):
            at[session.name] = (start + slot * (place + 0.5), GRAPH_MARGIN + NODE_HEIGHT / 2 + GRAPH_ROW_GAP * line)
            seat[session.name] = (line, place)
    counts, selves = {}, 0
    for record in page.records:
        if record.sender == record.recipient:
            selves += 1
            continue
        pair = (record.sender, record.recipient)
        counts[pair] = counts.get(pair, 0) + 1
    edges, reach_y = [], (0, height)
    for (sender, recipient), count in counts.items():
        (sx, sy), (rx, ry) = at[sender], at[recipient]
        length = math.hypot(rx - sx, ry - sy) or 1
        ux, uy = (rx - sx) / length, (ry - sy) / length
        start = box_edge((sx, sy), (widths[sender] / 2, NODE_HEIGHT / 2), (ux, uy))
        end = box_edge((rx, ry), (widths[recipient] / 2, NODE_HEIGHT / 2), (-ux, -uy))
        normal = (-uy, ux)
        (line_s, place_s), (line_r, place_r) = seat[sender], seat[recipient]
        over = line_s == line_r and abs(place_s - place_r) > 1
        bend = EDGE_BEND + (EDGE_BEND_PER_LENGTH * length if over else 0)
        control = ((start[0] + end[0]) / 2 + 2 * bend * normal[0],
                   (start[1] + end[1]) / 2 + 2 * bend * normal[1])
        tx, ty = end[0] - control[0], end[1] - control[1]
        tangent = math.hypot(tx, ty) or 1
        tx, ty = tx / tangent, ty / tangent
        base = (end[0] - tx * ARROW_LENGTH, end[1] - ty * ARROW_LENGTH)
        head = (end, (base[0] - ty * ARROW_HALF_WIDTH, base[1] + tx * ARROW_HALF_WIDTH),
                (base[0] + ty * ARROW_HALF_WIDTH, base[1] - tx * ARROW_HALF_WIDTH))
        middle = ((start[0] + 2 * control[0] + end[0]) / 4, (start[1] + 2 * control[1] + end[1]) / 4)
        reach_y = (min(reach_y[0], middle[1]), max(reach_y[1], middle[1]))
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
    top = min(0, reach_y[0] - GRAPH_MARGIN)
    bottom = max(height, reach_y[1] + GRAPH_MARGIN)
    return figure(1, "Who talks to whom", how, svg_chart("graph", width, bottom - top, "Who talks to whom", desc,
                                                          edges + nodes, top))


def summary_lines(page):
    """The page's opening lines: the warning or the scrub line, the counts and span, the as-of, and the headers that did not parse.

    @interacts  none; pure.
    @deps       element, esc, plural, time_text, seconds_of; REAL_WARNING,
                SCRUBBED_WORDS; page.unreadable (fix round 1, REC-13).
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
    if page.unreadable:
        lines.append(element("p", (("class", "unreadable"),), [esc(
            f"{plural(page.unreadable, 'folder')} could not be read, so the mail in "
            f"{'it is' if page.unreadable == 1 else 'them is'} not drawn here; tc report's stderr names "
            f"{'it' if page.unreadable == 1 else 'them'}.")]))
    if page.unparsed:
        them = "it" if page.unparsed == 1 else "them"
        lines.append(element("p", (), [esc(f"{plural(page.unparsed, 'message')} had a header line that did not "
                                           f"parse, so the time charts (2 to 5) leave {them} out; chart 1 counts "
                                           f"{them}.")]))
    return lines


def later(origin, seconds):
    """The time `seconds` after `origin`, in `origin`'s own kind: a datetime (with its offset) or a scrubbed number.

    @interacts  none.
    @deps       datetime.
    @complexity O(1).
    @alloc      one value.
    """
    if isinstance(origin, datetime.datetime):
        return origin + datetime.timedelta(seconds=seconds)
    return origin + seconds


def bucket_seconds(span):
    """Chart 2's bucket for a report spanning `span` seconds: an hour up to HOURLY_UP_TO_SECONDS, a day past it.

    @interacts  none.
    @deps       HOURLY_UP_TO_SECONDS, SECONDS_PER_HOUR, SECONDS_PER_DAY.
    @complexity O(1).
    @alloc      none.
    """
    return SECONDS_PER_HOUR if span <= HOURLY_UP_TO_SECONDS else SECONDS_PER_DAY


def plot_right():
    """Where every row chart's plot ends, on the right.

    @interacts  none.
    @deps       CHART_WIDTH, PLOT_RIGHT_PAD.
    @complexity O(1).
    @alloc      none.
    """
    return CHART_WIDTH - PLOT_RIGHT_PAD


def time_span(records):
    """(first sent, last sent) over `records` with a sent time, in the records' own kind; (None, None) when none has one.

    @interacts  none.
    @deps       seconds_of.
    @complexity O(t) over t records.
    @alloc      one tuple.
    """
    sent = [r.sent for r in records if r.sent is not None]
    if not sent:
        return None, None
    return min(sent, key=seconds_of), max(sent, key=seconds_of)


def time_axis(first, last, y):
    """A time axis under a row chart at height `y`: a line across the plot, the first time at its left end and the last at its right.

    @interacts  none.
    @deps       element, text_at, num, time_text, plot_right; LABEL_GUTTER,
                LINE_GAP.
    @complexity O(1).
    @alloc      one string.
    """
    return element("g", (("class", "time-axis"),), [
        element("line", (("class", "axis"), ("x1", num(LABEL_GUTTER)), ("y1", num(y)), ("x2", num(plot_right())),
                         ("y2", num(y)))),
        text_at(LABEL_GUTTER, y + LINE_GAP, time_text(first), "small", "start"),
        text_at(plot_right(), y + LINE_GAP, time_text(last), "small", "end")])


def empty_chart(key, number, heading, words):
    """A chart's section when it has nothing to draw: the same heading and SVG, with `words` in place of marks.

    @interacts  none.
    @deps       svg_chart, figure, text_at; CHART_WIDTH, CHART_TOP,
                LINE_GAP, LABEL_GAP.
    @complexity O(1).
    @alloc      one string.
    """
    svg = svg_chart(key, CHART_WIDTH, CHART_TOP + 2 * LINE_GAP, heading, words,
                    [text_at(LABEL_GAP, CHART_TOP + LINE_GAP, words)])
    return figure(number, heading, words, svg)


def row_label(y, name, detail, edge=None):
    """A row's words at its left: the name, bold, and one line of detail under it, both ending at `edge` (the gutter's edge less LABEL_GAP when None), each cut by fit_words so it starts no further left than LABEL_GAP (fix round 1, MEDIUM-2).

    @interacts  none.
    @deps       text_at, fit_words; LABEL_GUTTER, LABEL_GAP, LINE_GAP.
    @complexity O(c) over c characters of the two lines.
    @alloc      two strings.
    """
    edge = LABEL_GUTTER - LABEL_GAP if edge is None else edge
    shown, whole = fit_words(name, edge - LABEL_GAP)
    said, said_whole = fit_words(detail, edge - LABEL_GAP, "small")
    return [text_at(edge, y - LINE_GAP / 2, shown, "label", "end", whole),
            text_at(edge, y + LINE_GAP / 2, said, "small", "end", said_whole)]


def chart_senders(page):
    """Chart 2, messages over time per sender: small multiples, one row per sender labeled at its left, one bar per bucket it sent in.

    The bucket is bucket_seconds(span) over the report's sent times, and
    bucket k covers [first + k x bucket, first + (k + 1) x bucket), from
    the first sent time, so a real and a scrubbed page draw the same bars.
    One height scale for every row: the busiest bucket anywhere is
    BAR_MAX_HEIGHT. A message with no sent time is left out.

    @interacts  none; pure.
    @deps       math; element, text_at, titled, svg_chart, figure,
                row_label, time_axis, time_span, bucket_seconds, later,
                seconds_of, plot_right, empty_chart, num, plural; the
                chart 2 constants.
    @complexity O(t + s x b) over t records, s senders and b buckets
                (at most 169 hours, or the span in days).
    @alloc      the SVG text, returned; one count map per sender.
    """
    heading = "Messages over time, per sender"
    first, last = time_span(page.records)
    if first is None:
        return empty_chart("senders", 2, heading, "No messages yet." if not page.records else
                           "No message has a sent time.")
    span = seconds_of(last) - seconds_of(first)
    bucket = bucket_seconds(span)
    unit = "hour" if bucket == SECONDS_PER_HOUR else "day"
    buckets = int(span // bucket) + 1
    counts = {}
    for record in page.records:
        if record.sent is not None:
            row = counts.setdefault(record.sender, {})
            index = int((seconds_of(record.sent) - seconds_of(first)) // bucket)
            row[index] = row.get(index, 0) + 1
    senders = [s.name for s in page.sessions if s.name in counts]
    tallest = max(max(row.values()) for row in counts.values())
    width = (plot_right() - LABEL_GUTTER) / buckets
    body = []
    for line, sender in enumerate(senders):
        base = CHART_TOP + SENDER_ROW_HEIGHT * (line + 1)
        row = counts[sender]
        marks = [element("line", (("class", "axis"), ("x1", num(LABEL_GUTTER)), ("y1", num(base)),
                                  ("x2", num(plot_right())), ("y2", num(base))))]
        for index in sorted(row):
            tall = BAR_MAX_HEIGHT * row[index] / tallest
            marks.append(element("rect", (("class", "bar"), ("x", num(LABEL_GUTTER + width * index)),
                                          ("y", num(base - tall)), ("width", num(max(width - BAR_GAP, BAR_GAP))),
                                          ("height", num(tall))),
                                 [titled(f"{time_text(later(first, index * bucket))}: {row[index]} sent")]))
        words = row_label(base - BAR_MAX_HEIGHT / 2, sender,
                          f"{sum(row.values())} sent · peak {max(row.values())} in {BUCKET_WORDS[unit]}")
        body.append(element("g", (("class", "plot"), ("data-plot", sender)), [
            element("g", (("class", "series"), ("data-label", sender), ("data-shape", "bar"), ("data-dash", "none")),
                    words + marks)]))
    height = CHART_TOP + SENDER_ROW_HEIGHT * len(senders) + AXIS_HEIGHT
    body.append(time_axis(first, last, CHART_TOP + SENDER_ROW_HEIGHT * len(senders) + LABEL_GAP))
    desc = (f"One row per sender; each bar is one {unit} of mail it sent, its height the count, on one scale for "
            f"every row. The bar is an hour when the report spans 7 days or less, else a day.")
    how = (f"Each bar is one {unit} of mail sent; taller is more, on one scale for every row. A report that spans "
           "7 days or less draws hours, a longer one days. Hover a bar for its time and count.")
    return figure(2, heading, how, svg_chart("senders", CHART_WIDTH, height, heading, desc, body))


def median_of(values):
    """The median of `values` (the mean of the middle two for an even count).

    @interacts  none.
    @deps       none.
    @complexity O(v log v) over v values.
    @alloc      one sorted copy, freed on return.
    """
    ordered = sorted(values)
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2


def delay_strips(key, rows, heading, desc, footer=()):
    """The SVG of charts 3 and 5: one strip per row, one dot per delay on a log scale, the median as a labeled tick.

    `rows` is a list of (name, detail words, [(delay seconds, title)]). A
    strip is its own plot with one series, labeled at its left; a row with
    no delays draws its words and no median; a median's words are kept
    inside the chart's width. `footer` is lines of words
    under the axis. The axis has a grid line at each of
    DELAY_TICKS_SECONDS the data reaches, each labeled, and the longest
    delay drawn labeled at its far end; a tick label closer to that end
    than DELAY_END_GAP is left off, so the two never overlap.

    @interacts  none; pure.
    @deps       math; element, text_at, titled, svg_chart, row_label,
                median_of, span_text, plot_right, num; the strip
                constants.
    @complexity O(d + r) over d delays and r rows, plus one sort per row
                for its median.
    @alloc      the SVG text, returned.
    """
    longest = max([DELAY_SCALE_MIN_SECONDS] + [delay for _, _, dots in rows for delay, _ in dots])
    reach = plot_right() - LABEL_GUTTER

    def x_of(delay):
        """The x of `delay` seconds on the log scale.

        @interacts  none.
        @deps       math.
        @complexity O(1).
        @alloc      none.
        """
        return LABEL_GUTTER + reach * math.log1p(delay) / math.log1p(longest)

    bottom = CHART_TOP + STRIP_HEIGHT * len(rows)
    body = []
    for tick in (t for t in DELAY_TICKS_SECONDS if t <= longest):
        label = ([] if tick == longest or x_of(longest) - x_of(tick) < DELAY_END_GAP else
                 [text_at(x_of(tick), bottom + LINE_GAP, span_text(tick), "small", "middle")])
        body.append(element("g", (("class", "delay-tick"),), [
            element("line", (("class", "grid"), ("x1", num(x_of(tick))), ("y1", num(CHART_TOP)),
                             ("x2", num(x_of(tick))), ("y2", num(bottom)))), *label]))
    body.append(element("g", (("class", "delay-tick"),), [
        text_at(x_of(longest), bottom + LINE_GAP, span_text(longest), "small", "end")]))
    for line, (name, detail, dots) in enumerate(rows):
        middle = CHART_TOP + STRIP_HEIGHT * line + STRIP_HEIGHT / 2
        marks = [element("line", (("class", "axis"), ("x1", num(LABEL_GUTTER)), ("y1", num(middle)),
                                  ("x2", num(plot_right())), ("y2", num(middle))))]
        for index, (delay, title) in enumerate(dots):
            marks.append(element("circle", (("class", "dot"), ("cx", num(x_of(delay))),
                                            ("cy", num(middle + DOT_OFFSETS[index % len(DOT_OFFSETS)])),
                                            ("r", num(DOT_RADIUS))), [titled(title)]))
        if dots:
            median = median_of([delay for delay, _ in dots])
            marks.append(element("line", (("class", "median"), ("x1", num(x_of(median))),
                                          ("y1", num(middle - MEDIAN_REACH)), ("x2", num(x_of(median))),
                                          ("y2", num(middle + MEDIAN_REACH)))))
            words = f"median {span_text(median)}"
            half = len(words) * SMALL_CHAR_WIDTH / 2
            marks.append(text_at(min(max(x_of(median), LABEL_GUTTER + half), CHART_WIDTH - half),
                                 middle - MEDIAN_REACH - DOT_RADIUS, words, "small halo", "middle"))
        body.append(element("g", (("class", "plot"), ("data-plot", name)), [
            element("g", (("class", "series"), ("data-label", name), ("data-shape", "circle"), ("data-dash", "none")),
                    row_label(middle, name, detail) + marks)]))
    height = bottom + AXIS_HEIGHT
    for words in footer:
        body.append(text_at(LABEL_GAP, height, words, "small"))
        height += LINE_GAP
    return svg_chart(key, CHART_WIDTH, height, heading, desc, body)


def dot_name(record):
    """How a dot names its message: `#<number>`, and its tag when it has one.

    @interacts  none.
    @deps       none.
    @complexity O(1).
    @alloc      one string.
    """
    return f"#{record.number} {record.tag}" if record.tag else f"#{record.number}"


def chart_read(page):
    """Chart 3, sent to read, per recipient: one dot per message with a read time, at its delay, the median as a labeled tick, and `n of m messages have a read time`.

    m counts the messages to that recipient with a sent time; n those of
    them with a read time too. A read before its sent time (a clock set
    back) draws at 0. A message with no sent time is left out.

    @interacts  none; pure.
    @deps       delay_strips, figure, empty_chart, dot_name, span_text,
                seconds_of, plural.
    @complexity O(s x t + d log d) over s sessions, t records and d
                dots: the records are filtered once per session (fix
                round 1, LOW-18), and each strip is sorted for its median.
    @alloc      the SVG text, returned; one list per recipient.
    """
    heading = "From sent to read, per recipient"
    timed = [r for r in page.records if r.sent is not None]
    if not timed:
        return empty_chart("read", 3, heading, "No messages yet." if not page.records else
                           "No message has a sent time.")
    rows = []
    for session in page.sessions:
        mine = [r for r in timed if r.recipient == session.name]
        if not mine:
            continue
        dots = []
        for record in mine:
            if record.read is not None:
                delay = max(0.0, seconds_of(record.read) - seconds_of(record.sent))
                dots.append((delay, f"{dot_name(record)} from {record.sender}: read {time_text(record.read)}, "
                                    f"after {span_text(delay)}"))
        verb = "has" if len(mine) == 1 else "have"
        rows.append((session.name, f"{len(dots)} of {plural(len(mine), 'message')} {verb} a read time", dots))
    how = ("One dot per message with a read time, placed by how long it waited from sent to read, on a log scale. "
           "The heavy tick is the median, named above it. A message read by a tc older than read-time records "
           "has no dot; the words at the left count them. Hover a dot for its message.")
    desc = ("One strip per recipient; each dot is one message's wait from sent to read, the median marked and "
            "named, and how many of its messages have a read time.")
    return figure(3, heading, how, delay_strips("read", rows, heading, desc))


def marker(shape, x, y, css):
    """A series marker of `shape` (one of SERIES_SHAPES) centered at (x, y), MARKER_SIZE either side.

    @interacts  none.
    @deps       element, num; MARKER_SIZE.
    @complexity O(1).
    @alloc      one string.
    """
    size = MARKER_SIZE
    if shape == "circle":
        return element("circle", (("class", css), ("cx", num(x)), ("cy", num(y)), ("r", num(size))))
    if shape == "square":
        return element("rect", (("class", css), ("x", num(x - size)), ("y", num(y - size)), ("width", num(2 * size)),
                                ("height", num(2 * size))))
    corners = (((x, y - size), (x + size, y + size), (x - size, y + size)) if shape == "triangle-up" else
               ((x, y - size), (x + size, y), (x, y + size), (x - size, y)))
    return element("polygon", (("class", css), ("points", " ".join(f"{num(a)},{num(b)}" for a, b in corners))))


def hatch(x0, y0, x1, y1):
    """Diagonal hatch lines filling the box (x0, y0) to (x1, y1), as one path: the quiet fill, drawn, never a fill color alone.

    The lines are worked out here, each clipped to the box, so the page
    needs no SVG pattern (which a fill reaches only through url()).

    @interacts  none.
    @deps       element, num; HATCH_STEP.
    @complexity O((w + h) / HATCH_STEP) over the box's width w and height h.
    @alloc      one string.
    """
    moves, k = [], x0 + y0 + HATCH_STEP
    while k < x1 + y1:
        start, end = max(x0, k - y1), min(x1, k - y0)
        if start < end:
            moves.append(f"M{num(start)},{num(k - start)} L{num(end)},{num(k - end)}")
        k += HATCH_STEP
    return element("path", (("class", "hatch"), ("d", " ".join(moves) or f"M{num(x0)},{num(y0)}")))


def chart_quiet(page):
    """Chart 4, busy and quiet stretches: one lane per session, a tick up for each message it sent and down for each it received, and each gap of QUIET_GAP_SECONDS or more hatched and labeled with its length.

    Each lane is a plot with two series that share it, sent and received;
    series i takes SERIES_SHAPES[i], SERIES_DASHES[i] and SERIES_COLORS[i],
    and its label (glyph and word) sits beside its ticks. A received tick
    is at the message's sent time: when it landed, not when it was read.
    A message with no sent time is left out.

    @interacts  none; pure.
    @deps       element, text_at, titled, svg_chart, figure, empty_chart,
                row_label, marker, hatch, time_axis, time_span, dot_name,
                seconds_of, time_text, span_text, plural, plot_right, num;
                the chart 4 constants.
    @complexity O(s x t + t log t + g x (w + h) / HATCH_STEP) over s
                sessions, t records and g quiet gaps: the records are
                filtered twice per session (fix round 1, LOW-18), each
                lane's times sorted, and each gap hatched in its box of
                width w and height h.
    @alloc      the SVG text, returned; one event list per session.
    """
    heading = "Busy and quiet stretches"
    first, last = time_span(page.records)
    if first is None:
        return empty_chart("quiet", 4, heading, "No messages yet." if not page.records else
                           "No message has a sent time.")
    start, span = seconds_of(first), seconds_of(last) - seconds_of(first)
    reach = plot_right() - LABEL_GUTTER

    def x_of(when):
        """The x of a time on the lanes' shared scale; the middle when the span is 0.

        @interacts  none.
        @deps       seconds_of.
        @complexity O(1).
        @alloc      none.
        """
        return LABEL_GUTTER + (reach * (seconds_of(when) - start) / span if span else reach / 2)

    lanes = []
    for session in page.sessions:
        sent = [r for r in page.records if r.sent is not None and r.sender == session.name]
        got = [r for r in page.records if r.sent is not None and r.recipient == session.name]
        if sent or got:
            lanes.append((session.name, sent, got))
    body = []
    for line, (name, sent, got) in enumerate(lanes):
        middle = CHART_TOP + LANE_HEIGHT * line + LANE_HEIGHT / 2
        top, bottom = middle - LANE_HEIGHT / 2 + MARKER_SIZE, middle + LANE_HEIGHT / 2 - MARKER_SIZE
        parts = row_label(middle, name, f"{len(sent)} sent · {len(got)} received", LABEL_GUTTER - SERIES_LABEL_ROOM)
        parts.append(element("line", (("class", "axis"), ("x1", num(LABEL_GUTTER)), ("y1", num(middle)),
                                      ("x2", num(plot_right())), ("y2", num(middle)))))
        times = sorted({seconds_of(r.sent) for r in sent + got})
        for before, after in zip(times, times[1:]):
            if after - before < QUIET_GAP_SECONDS:
                continue
            x0, x1 = x_of(later(first, before - start)), x_of(later(first, after - start))
            parts.append(element("g", (("class", "quiet"),), [
                titled(f"quiet from {time_text(later(first, before - start))} to "
                       f"{time_text(later(first, after - start))}: {span_text(after - before)}"),
                element("rect", (("class", "quiet-box"), ("x", num(x0)), ("y", num(top)), ("width", num(x1 - x0)),
                                 ("height", num(bottom - top)))),
                hatch(x0, top, x1, bottom),
                text_at((x0 + x1) / 2, middle - TICK_LENGTH - MARKER_SIZE, f"quiet {span_text(after - before)}",
                        "small halo", "middle")]))
        for index, (word, records, way) in enumerate((("sent", sent, -1), ("received", got, 1))):
            shape, dash, css = SERIES_SHAPES[index], SERIES_DASHES[index], SERIES_COLORS[index]
            end = middle + way * TICK_LENGTH
            marks = [text_at(LABEL_GUTTER - LABEL_GAP, end + way * MARKER_SIZE + (MARKER_SIZE if way > 0 else 0),
                             f"{SHAPE_GLYPHS[shape]} {word}", "small", "end")]
            for record in records:
                x = x_of(record.sent)
                other = f"to {record.recipient}" if way < 0 else f"from {record.sender}"
                line_attrs = [("class", f"tick-line {css}"), ("x1", num(x)), ("y1", num(middle)), ("x2", num(x)),
                              ("y2", num(end))]
                if dash != "none":
                    line_attrs.append(("stroke-dasharray", dash))
                marks.append(element("g", (("class", "tick"),), [
                    titled(f"{dot_name(record)} {other}, {time_text(record.sent)}"),
                    element("line", tuple(line_attrs)), marker(shape, x, end, css)]))
            parts.append(element("g", (("class", "series"), ("data-label", word), ("data-shape", shape),
                                        ("data-dash", dash)), marks))
        body.append(element("g", (("class", "plot"), ("data-plot", name)), parts))
    bottom_line = CHART_TOP + LANE_HEIGHT * len(lanes)
    body.append(time_axis(first, last, bottom_line + LABEL_GAP))
    how = (f"One lane per session. A solid tick up, tipped with {SHAPE_GLYPHS[SERIES_SHAPES[0]]}, is a message it "
           f"sent; a dashed tick down, tipped with {SHAPE_GLYPHS[SERIES_SHAPES[1]]}, one it received, when it "
           f"landed. A hatched box is a quiet stretch: {span_text(QUIET_GAP_SECONDS)} or more with no mail either "
           "way, its length written in it. Hover a tick for its message.")
    desc = ("One lane per session with ticks up for mail sent and down for mail received, and every gap of "
            f"{span_text(QUIET_GAP_SECONDS)} or more hatched and labeled with its length.")
    return figure(4, heading, how, svg_chart("quiet", CHART_WIDTH, bottom_line + AXIS_HEIGHT, heading, desc, body))


def answer_pairs(records):
    """C7's ask to answer pairs among `records` (in sent order): [(ask, answer)], in the answers' order.

    A message answers #N when its first line names #N (any tag, or none:
    `ANSWER re #N`, `Re #N: ...`), it goes from #N's recipient back to
    #N's sender, both have a sent time, and it comes after #N in sent
    order. #N is the first message numbered N. Only the first answer to
    each ask counts. A message naming no #N never pairs, and nothing is
    paired by time or by guess. A note a name sent itself is never an ask
    or an answer.

    @interacts  none; pure.
    @deps       none.
    @complexity O(t + r) over t records and r references.
    @alloc      a map of t numbers, a set of answered asks, and the list,
                returned.
    """
    first, place = {}, {}
    for index, record in enumerate(records):
        first.setdefault(record.number, record)
        place.setdefault(id(record), index)
    pairs, answered = [], set()
    for index, answer in enumerate(records):
        if answer.sent is None or answer.sender == answer.recipient:
            continue
        for ref in answer.refs:
            ask = first.get(ref)
            if (ask is None or id(ask) in answered or ask.sent is None or place[id(ask)] >= index
                    or ask.sender != answer.recipient or ask.recipient != answer.sender):
                continue
            answered.add(id(ask))
            pairs.append((ask, answer))
    return pairs


def chart_answers(page):
    """Chart 5, ask to answer: per answerer, one dot per pair at the time from the ask's sent time to the answer's, in chart 3's form, and in words how many answers paired, how many asks have no reply that names them (an ask with no sent time is left out of that count, and counted apart), and ASK_CAVEAT.

    @interacts  none; pure.
    @deps       answer_pairs, delay_strips, figure, empty_chart, element,
                text_at, dot_name, span_text, seconds_of, plural; ASK_TAGS.
    @complexity O(t + r + d log d) over t records, r references and d
                pairs.
    @alloc      the SVG text, returned; the pairs.
    """
    heading = "From ask to answer"
    if not any(r.sent is not None for r in page.records):
        return empty_chart("answers", 5, heading, "No messages yet." if not page.records else
                           "No message has a sent time.")
    pairs = answer_pairs(page.records)
    by_answerer = {}
    for ask, answer in pairs:
        wait = max(0.0, seconds_of(answer.sent) - seconds_of(ask.sent))
        by_answerer.setdefault(answer.sender, []).append(
            (wait, f"{dot_name(ask)} to {dot_name(answer)}: {span_text(wait)}"))
    rows = [(s.name, plural(len(by_answerer[s.name]), "answer"), by_answerer[s.name])
            for s in page.sessions if s.name in by_answerer]
    paired = {id(ask) for ask, _ in pairs}
    asks = [r for r in page.records if r.tag in ASK_TAGS and id(r) not in paired]
    open_asks = [r for r in asks if r.sent is not None]
    untimed = len(asks) - len(open_asks)
    named = ("1 answer names the message it answers." if len(pairs) == 1 else
             f"{len(pairs)} answers name the message they answer.")
    lines = [named + " " + ("1 ask has no reply that names it." if len(open_asks) == 1 else
                            f"{len(open_asks)} asks have no reply that names them.")]
    if untimed:
        lines.append("1 ask has no sent time and is left out of this count." if untimed == 1 else
                     f"{untimed} asks have no sent time and are left out of this count.")
    lines.append(ASK_CAVEAT)
    desc = ("One strip per session that answered; each dot is one ask and its first answer, placed by the time "
            "between them, the median marked and named. " + " ".join(lines))
    how = ("A message answers an earlier one when its first line names that message's number (#N, whatever its "
           "tag, as in ANSWER re #N or Re #N:) and it goes back from that message's recipient to its sender. "
           "Each dot is the time from the ask to its first answer, on a log scale, per answerer. Nothing is "
           "paired by guess: a reply that names no number is not drawn.")
    svg = delay_strips("answers", rows, heading, desc, lines)
    return figure(5, heading, how, svg)


# The charts, in page order. Each takes the Page and returns its section.
CHARTS = (chart_graph, chart_senders, chart_read, chart_quiet, chart_answers)


def render(page):
    """`page` as one self-contained HTML file (C7): inline CSS and inline SVG, no script, no link, nothing fetched.

    Pure: no clock, no file, no environment. The same page gives the same
    string, byte for byte.

    @interacts  none; pure.
    @deps       element, esc, summary_lines, CHARTS; PAGE_TITLE, PAGE_CSS.
    @complexity O(s x t + t log t + p + d log d + g x q) over s sessions,
                t records, p directed pairs, d dots in charts 3 and 5, and
                g quiet gaps of at most q hatch lines each, as each chart
                says (fix round 1, LOW-18).
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


def report(tc, board, scrubbed=False, at=None):
    """`tc report`'s whole work, for tc's cmd_report: (page HTML, one line of summary words, words for stderr). `board` is serve.py as load_board_module gives it, which tc loads first so a missing one is refused in words.

    extract, then page_of (as of `at` or the last message), then scrub
    when `scrubbed`, then render. The summary names the message count and
    whether the page is scrubbed; the stderr words say what could not be
    read (a folder, a read-time record) and never reach the page.

    @interacts  see extract; render is pure.
    @deps       extract, page_of, scrub, render, plural.
    @complexity extract's, then render's.
    @alloc      the page text and the words, returned.
    """
    mailbox = extract(tc, board)
    page = page_of(mailbox, at)
    if scrubbed:
        page = scrub(page)
    kind = "scrubbed" if scrubbed else "real names and times"
    return render(page), f"{plural(len(page.records), 'message')}, {kind}", mailbox.words
