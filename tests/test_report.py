"""
Tests for `tc report` (contract C7, decision D42): the extractor, the
scrub, the five charts, the page's words and the command, over the fixture
mailbox in tests/_report_fixture.py. No live mailbox, ever: every test
builds its own under a TcRoot.

Model:  Claude Opus 5.5 (the DASH lane agent), 2026-10-17
Status: unreviewed

@interacts  builds the fixture under a TcRoot's throwaway TC_ROOT; loads
            tc and board/report.py in this process through
            _root.load_source (no bytecode read or written), with TC_ROOT
            set to the root for tc's load and put back after; runs ../tc
            report as a child through the harness, writing its page in
            the root's temp folder, outside the mailbox.
@deps       python3 stdlib (datetime, os, pathlib, re, sys, unittest,
            xml.etree.ElementTree); tests/_root.py (TcRoot, load_source,
            TC); tests/_report_fixture.py; ../tc; board/report.py,
            board/serve.py.
@complexity Each test builds the 12-message fixture (O(12) files) and
            runs at most a few tc children or in-process loads, each
            O(s) over s bytes of tc's source to compile.
@alloc      one TcRoot per test, removed with everything in it on exit;
            the pages read back, freed when the test returns.
"""

import argparse
import datetime
import os
import pathlib
import re
import sys
import unittest
from unittest import mock
from xml.etree import ElementTree

HERE = pathlib.Path(__file__).resolve().parent
# Run as `python3 -m unittest tests.test_report` from the repo root,
# tests/ is not on sys.path; under discover it is. Add it once so both work.
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import _report_fixture as fixture  # noqa: E402  (needs the path line above)
import _root  # noqa: E402

REPORT_PATH = HERE.parent / "board" / "report.py"
# tc's exit codes these tests expect (contracts.md, "Exit codes").
EXIT_OK = 0
EXIT_REFUSED = 1
EXIT_USAGE = 9
# C7's scrub test patterns: no calendar date and no clock time anywhere.
DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")
CLOCK_PATTERN = re.compile(r"\b\d{1,2}:\d{2}\b")
# A --at for the as-of tests, after the fixture's last message.
AT_TIME = "2026-10-03T12:30:00-05:00"


def modules_for(root):
    """tc loaded with TC_ROOT set to `root`'s path, and board/report.py, both from source: (tc, report).

    tc reads TC_ROOT once, at import, so it is set for the load and put
    back after, as every tc load in the suites does.

    @interacts  sets and restores os.environ["TC_ROOT"]; runs tc's and
                report.py's top levels. Writes no file.
    @deps       os; _root.load_source, _root.TC; REPORT_PATH.
    @complexity O(s) over s bytes of both sources: two compiles.
    @alloc      two module objects, returned.
    """
    old = os.environ.get("TC_ROOT")
    os.environ["TC_ROOT"] = str(root.path)
    try:
        tc = _root.load_source("tc_for_report", _root.TC)
    finally:
        if old is None:
            os.environ.pop("TC_ROOT", None)
        else:
            os.environ["TC_ROOT"] = old
    return tc, _root.load_source("board_report", REPORT_PATH)


def fixture_time(offset):
    """The fixture's time `offset` seconds after its first message, as a datetime; None stays None.

    @interacts  none.
    @deps       datetime; fixture.BASE.
    @complexity O(1).
    @alloc      one datetime.
    """
    return None if offset is None else fixture.BASE + datetime.timedelta(seconds=offset)


class FirstLineTest(unittest.TestCase):
    """The tag and #N references come from the first body line alone, by C7's rule.

    @interacts  loads board/report.py.
    @deps       _root.load_source; REPORT_PATH.
    @complexity O(1) per case.
    @alloc      the module, freed with the test.
    """

    def setUp(self):
        """Load report.py from source.

        @interacts  reads board/report.py and runs its top level.
        @deps       _root.load_source.
        @complexity O(s) over s bytes of report.py and serve.py.
        @alloc      one module object.
        """
        self.report = _root.load_source("board_report", REPORT_PATH)

    def test_a_leading_token_is_the_tag_with_one_trailing_colon_stripped(self):
        """`PLAN-READY:` and `PLAN-READY` are both the tag PLAN-READY; a second colon, one letter, lowercase or 25 characters are no tag; a #N of more than REF_MAX_DIGITS digits is no ref, and 5000 digits raise nothing (LOW-1).

        @interacts  none.
        @deps       report.first_line_facts.
        @complexity O(1).
        @alloc      none.
        """
        cases = {
            "PLAN-READY: the plan is in": ("PLAN-READY", ()),
            "PLAN-READY the plan is in": ("PLAN-READY", ()),
            "PLAN-READY::": (None, ()),
            "A one letter": (None, ()),
            "Re #3: thanks": (None, (3,)),
            "ANSWER re #2: json": ("ANSWER", (2,)),
            "QUESTION #1 and #12, then #1 again": ("QUESTION", (1, 12)),
            "ABCDEFGHIJKLMNOPQRSTUVWXY too long": (None, ()),
            "ABCDEFGHIJKLMNOPQRSTUVWX fits": ("ABCDEFGHIJKLMNOPQRSTUVWX", ()),
            "": (None, ()),
            "PLAN #" + "9" * 5000 + " and #7": ("PLAN", (7,)),
            "PLAN #123456789 #1234567890": ("PLAN", (123456789,)),
        }
        for line, want in cases.items():
            with self.subTest(line=line):
                self.assertEqual(self.report.first_line_facts(line), want)


class HeadTest(unittest.TestCase):
    """parse_head reads a tag and refs only from the line after a tc header (LOW-6).

    @interacts  loads board/report.py.
    @deps       _root.load_source; REPORT_PATH.
    @complexity O(1) per case.
    @alloc      the module.
    """

    def test_no_tag_or_ref_comes_from_line_two_when_line_one_is_no_tc_header(self):
        """A file whose first line is not a tc header gives no tag and no refs; a tc header whose time does not parse still gives its first body line's.

        @interacts  loads report.py.
        @deps       report.parse_head.
        @complexity O(1).
        @alloc      none.
        """
        report = _root.load_source("board_report", REPORT_PATH)
        self.assertEqual(report.parse_head(b"hello there\nPLAN #3 second line\n"), (None, None, ()))
        self.assertEqual(report.parse_head(b"hello\n\nPLAN #3\n"), (None, None, ()))
        self.assertEqual(report.parse_head(b"# #5 from a to b, not a time\n\nPLAN #3\n"), (None, "PLAN", (3,)))

    def test_ties_in_sent_order_go_by_number_then_size_never_by_name(self):
        """Two messages at one time: the lower number first; at one number too, the smaller first, whatever the names (REC-3).

        @interacts  loads report.py.
        @deps       report.sent_order, report.Record.
        @complexity O(1).
        @alloc      none.
        """
        report = _root.load_source("board_report", REPORT_PATH)
        late = report.Record(5, "aaa", "bbb", fixture.BASE, None, 90, None, ())
        early = report.Record(5, "zzz", "yyy", fixture.BASE, None, 10, None, ())
        self.assertEqual(sorted([late, early], key=report.sent_order), [early, late])


class ExtractTest(unittest.TestCase):
    """extract() reads exactly C7's facts from the fixture mailbox.

    @interacts  builds the fixture under a TcRoot; loads tc and report.py.
    @deps       modules_for, fixture.build; _root.TcRoot.
    @complexity O(12) messages.
    @alloc      one TcRoot, removed on exit.
    """

    def test_each_message_is_one_closed_record_in_sent_order(self):
        """Number, sender, recipient, sent, read, size, tag and refs, for every message, in sent order with the unparsed one last.

        @interacts  see the class.
        @deps       report.extract, report.Record.
        @complexity O(12).
        @alloc      the records.
        """
        with _root.TcRoot() as root:
            fixture.build(root.path)
            tc, report = modules_for(root)
            box = report.extract(tc)
            self.assertEqual(report.Record._fields,
                             ("number", "sender", "recipient", "sent", "read", "size", "tag", "refs"))
            want = []
            for spec in fixture.MESSAGES:
                folder = root.path / "mail" / f"to-{spec.to}" / ("read" if spec.read is not None else "")
                size = (folder / f"{spec.number:06d}-from-{spec.sender}.md").stat().st_size
                tag, refs = (None, ()) if spec.sent is None else report.first_line_facts(spec.body.split("\n")[0])
                want.append(report.Record(spec.number, spec.sender, spec.to, fixture_time(spec.sent),
                                          fixture_time(spec.read), size, tag, refs))
            want.sort(key=lambda r: (r.sent is None, r.sent.timestamp() if r.sent else 0, r.number))
            self.assertEqual(list(box.records), want)
            self.assertEqual(box.unparsed, 1)

    def test_roles_come_from_c5_and_a_name_with_no_inbox_or_card_has_none(self):
        """Sessions in first-mail order, each with C5's role, source and level; dagny (no card, no inbox) has no role.

        @interacts  see the class.
        @deps       report.extract, report.Session.
        @complexity O(12).
        @alloc      the sessions.
        """
        with _root.TcRoot() as root:
            fixture.build(root.path)
            tc, report = modules_for(root)
            box = report.extract(tc)
            self.assertEqual(list(box.sessions), [
                report.Session("annika", "orchestrator", "declared", 0),
                report.Session("bertil", "worker", "declared", 1),
                report.Session("corwin", "worker", "declared", 1),
                report.Session("dagny", None, None, None),
            ])

    def test_a_header_that_real_tc_send_wrote_parses(self):
        """Mail sent and read by tc itself, through the harness: its sent time, tag, refs and read time come out (REC-1), so a change to tc's header shape goes red here.

        @interacts  runs tc join, send and read as children; loads tc and report.py.
        @deps       report.extract; _root.TcRoot.tc.
        @complexity four children and one extract.
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            for args in (("join", "ann"), ("join", "ben"), ("send", "--from", "ann", "--to", "ben", "PLAN: one"),
                         ("send", "--from", "ben", "--to", "ann", "ANSWER re #1: two"), ("read", "ben")):
                code, _, stderr = root.tc(*args)
                self.assertEqual(code, EXIT_OK, (args, stderr))
            tc, report = modules_for(root)
            box = report.extract(tc)
            self.assertEqual(box.unparsed, 0)
            got = {r.number: (r.tag, r.refs, r.sent is not None, r.read is not None) for r in box.records}
            self.assertEqual(got, {1: ("PLAN", (), True, True), 2: ("ANSWER", (1,), True, False)})

    def test_each_inbox_is_closed_before_the_next_is_walked(self):
        """Forty inboxes: the open descriptors never grow by more than a few during the walk (LOW-2).

        @interacts  builds forty inboxes; counts /proc/self/fd at each message read.
        @deps       report.extract, report.read_head.
        @complexity O(40).
        @alloc      forty small files.
        """
        with _root.TcRoot() as root:
            for n in range(1, 41):
                box = root.path / "mail" / f"to-box{n}"
                (box / "read").mkdir(parents=True)
                (box / f"{n:06d}-from-ann.md").write_text(f"# #{n} from ann to box{n}, {fixture.at(n)}\n\nFYI\n",
                                                          encoding="utf-8")
            tc, report = modules_for(root)
            real, counts = report.read_head, []

            def counting(*args):
                """read_head, counting this process's open descriptors first.

                @interacts  lists /proc/self/fd.
                @deps       os.
                @complexity O(f) over f descriptors.
                @alloc      one list entry.
                """
                counts.append(len(os.listdir("/proc/self/fd")))
                return real(*args)

            report.read_head = counting
            before = len(os.listdir("/proc/self/fd"))
            self.assertEqual(len(report.extract(tc).records), 40)
            self.assertLessEqual(max(counts) - before, 6, counts)

    def test_a_message_tc_read_moves_mid_walk_is_read_from_read(self):
        """A message renamed into read/ between the listing and its read is read from read/, with its read time, not counted as a header that did not parse (LOW-9).

        @interacts  builds the fixture; moves one message mid-walk.
        @deps       report.extract, report.read_head.
        @complexity O(12).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            fixture.build(root.path)
            tc, report = modules_for(root)
            box = root.path / "mail" / "to-annika"
            name = "000012-from-corwin.md"
            real, moved = report.read_head, []

            def moving(entry, folder_fd, limit):
                """Move message 12 into read/ (and record its read time) just before its first read, as tc read would.

                @interacts  renames one file; appends one line to read/.read-times.
                @deps       os.
                @complexity O(1).
                @alloc      none.
                """
                if entry == name and not moved:
                    moved.append(entry)
                    os.rename(box / name, box / "read" / name)
                    with open(box / "read" / ".read-times", "a", encoding="utf-8") as record:
                        record.write('{"name": "%s", "number": 12, "read": "%s"}\n' % (name, fixture.at(18 * fixture.HOUR)))
                return real(entry, folder_fd, limit)

            report.read_head = moving
            box_facts = report.extract(tc)
            self.assertTrue(moved)
            twelve = [r for r in box_facts.records if r.number == 12]
            self.assertEqual(len(twelve), 1)
            self.assertEqual((twelve[0].sent, twelve[0].read, twelve[0].tag),
                             (fixture_time(17 * fixture.HOUR), fixture_time(18 * fixture.HOUR), "QUESTION"))
            self.assertEqual(box_facts.unparsed, 1)

    def test_a_reports_to_cycle_is_broken_at_the_earliest_first_mail_not_the_first_name(self):
        """Cards zeta and alpha report to each other; zeta mails first. zeta is the root (level 0), though alpha sorts first (LOW-10, the relay's addition).

        @interacts  writes two cards and two messages; loads tc and report.py.
        @deps       report.extract.
        @complexity O(1).
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            for name, other, number, offset in (("zeta", "alpha", 1, 0), ("alpha", "zeta", 2, fixture.HOUR)):
                (root.path / "cards").mkdir(exist_ok=True)
                (root.path / "cards" / f"{name}.json").write_text('{"reports_to": "%s"}' % other, encoding="utf-8")
                box = root.path / "mail" / f"to-{other}"
                (box / "read").mkdir(parents=True, exist_ok=True)
                (box / f"{number:06d}-from-{name}.md").write_text(
                    f"# #{number} from {name} to {other}, {fixture.at(offset)}\n\nFYI\n", encoding="utf-8")
            tc, report = modules_for(root)
            levels = {s.name: s.level for s in report.extract(tc).sessions}
            self.assertEqual(levels, {"zeta": 0, "alpha": 1})

    def test_a_header_past_the_read_window_leaves_no_time_and_no_tag(self):
        """A header longer than MESSAGE_HEADER_MAX_BYTES + TAG_READ_MAX_BYTES gives no sent time and no tag: nothing past the window is read.

        @interacts  see the class; writes one more message by hand.
        @deps       report.extract, report.TAG_READ_MAX_BYTES; tc.MESSAGE_HEADER_MAX_BYTES.
        @complexity O(1).
        @alloc      one long file.
        """
        with _root.TcRoot() as root:
            fixture.build(root.path)
            tc, report = modules_for(root)
            pad = "x" * (tc.MESSAGE_HEADER_MAX_BYTES + report.TAG_READ_MAX_BYTES)
            path = root.path / "mail" / "to-annika" / "000013-from-bertil.md"
            path.write_text(f"# #13 from bertil to annika, {fixture.at(0)}, {pad}\n\nPLAN: late\n", encoding="utf-8")
            box = report.extract(tc)
            late = [r for r in box.records if r.number == 13]
            self.assertEqual([(r.sent, r.tag) for r in late], [(None, None)])
            self.assertEqual(box.unparsed, 2)


class ScrubTest(unittest.TestCase):
    """scrub() turns names, tags, times and numbers into C7's safe forms, on the records, before any rendering.

    @interacts  builds the fixture under a TcRoot; loads tc and report.py.
    @deps       modules_for, fixture.build; _root.TcRoot.
    @complexity O(12) messages.
    @alloc      one TcRoot, removed on exit.
    """

    # The fixture's numbers as ranks in sent order: 10's header does not
    # parse, so it ranks last.
    RANKS = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8, 9: 9, 11: 10, 12: 11, 10: 12}
    LABELS = {"annika": "orchestrator-1", "bertil": "worker-1", "corwin": "worker-2", "dagny": "session-1"}

    def test_the_allow_list_is_c7s(self):
        """SCRUB_TAGS holds exactly C7's seventeen tags.

        @interacts  loads report.py.
        @deps       report.SCRUB_TAGS.
        @complexity O(1).
        @alloc      none.
        """
        report = _root.load_source("board_report", REPORT_PATH)
        self.assertEqual(set(report.SCRUB_TAGS), {
            "ANSWER", "FYI", "QUESTION", "PLAN", "PLAN-READY", "PLAN-CHECK", "PLAN-EDIT", "PLAN-EDITED",
            "PLAN-REVIEWED", "CORRECTION", "HEADS-UP", "MERGE", "REVIEW", "STATUS", "BLOCKED", "DONE", "BREACH"})

    def test_names_tags_times_and_numbers_become_labels_other_elapsed_and_ranks(self):
        """Every scrubbed record: rank, role label by first mail, elapsed seconds, the size, an allow-listed tag or `other`, refs as ranks.

        @interacts  see the class.
        @deps       report.extract, report.page_of, report.scrub.
        @complexity O(12).
        @alloc      the records.
        """
        with _root.TcRoot() as root:
            fixture.build(root.path)
            tc, report = modules_for(root)
            page = report.scrub(report.page_of(report.extract(tc), None))
            self.assertTrue(page.scrubbed)
            want = []
            for spec in fixture.MESSAGES:
                folder = root.path / "mail" / f"to-{spec.to}" / ("read" if spec.read is not None else "")
                size = (folder / f"{spec.number:06d}-from-{spec.sender}.md").stat().st_size
                tag, refs = (None, ()) if spec.sent is None else report.first_line_facts(spec.body.split("\n")[0])
                tag = tag if tag in report.SCRUB_TAGS or tag is None else "other"
                want.append(report.Record(self.RANKS[spec.number], self.LABELS[spec.sender], self.LABELS[spec.to],
                                          spec.sent, spec.read, size, tag, tuple(self.RANKS[r] for r in refs)))
            want.sort(key=lambda r: r.number)
            self.assertEqual(list(page.records), want)
            self.assertEqual([s.name for s in page.sessions], list(self.LABELS.values()))
            self.assertEqual(page.as_of, 17 * fixture.HOUR)

    def test_a_reference_to_no_message_in_the_mailbox_is_dropped(self):
        """A #N naming no message here has no rank, so the scrubbed record drops it, never keeps the real number.

        @interacts  loads report.py.
        @deps       report.scrub, report.Page, report.Record, report.Session.
        @complexity O(1).
        @alloc      one small page.
        """
        report = _root.load_source("board_report", REPORT_PATH)
        record = report.Record(41, "ann", "ben", fixture.BASE, None, 10, "ANSWER", (7, 41))
        page = report.Page((record,), (report.Session("ann", None, None, None), report.Session("ben", None, None, None)),
                           0, False, None)
        self.assertEqual(report.scrub(page).records[0].refs, (1,))


def rendered(scrub=False, at=None):
    """The fixture's page as HTML, rendered in this process: (report module, html).

    @interacts  builds the fixture under a TcRoot of its own; loads tc
                and report.py.
    @deps       modules_for, fixture.build; _root.TcRoot.
    @complexity O(12) messages, plus two compiles.
    @alloc      one TcRoot, removed before return; the page, returned.
    """
    with _root.TcRoot() as root:
        fixture.build(root.path)
        tc, report = modules_for(root)
        page = report.page_of(report.extract(tc), at)
        return report, report.render(report.scrub(page) if scrub else page)


def charts(page):
    """Each chart's SVG in `page`, parsed: {data-chart: Element}.

    Every SVG is written as well-formed XML, so ElementTree parses it; a
    page that is not fails here.

    @interacts  none.
    @deps       re, xml.etree.ElementTree.
    @complexity O(p) over p characters of the page.
    @alloc      one tree per SVG, returned.
    """
    found = {}
    for svg in re.findall(r"<svg\b.*?</svg>", page, re.S):
        element = ElementTree.fromstring(svg)
        found[element.get("data-chart")] = element
    return found


def words(element):
    """All the text inside `element`, joined.

    @interacts  none.
    @deps       none.
    @complexity O(n) over n nodes under it.
    @alloc      one string.
    """
    return "".join(element.itertext())


def groups(element, kind):
    """Every <g> under `element` whose class list holds `kind`.

    @interacts  none.
    @deps       none.
    @complexity O(n) over n nodes under it.
    @alloc      one list.
    """
    return [g for g in element.iter("g") if kind in (g.get("class") or "").split()]


def title_of(element):
    """The text of `element`'s own <title> child, or None.

    @interacts  none.
    @deps       none.
    @complexity O(c) over c children.
    @alloc      none.
    """
    title = element.find("title")
    return None if title is None else title.text


# C7, pause DASH-1: the line under chart 5 that says what its count cannot see.
ASK_CAVEAT = ("A session that does not put #N on its first line answers without naming the ask, so this count "
              "can include asks that were answered.")

# The fixture's graph: one arrow per sender and recipient, with its count.
# Message 10's header does not parse, but its file name still counts here.
GRAPH_EDGES = {("annika", "bertil", 3), ("bertil", "annika", 3), ("corwin", "annika", 2),
               ("annika", "corwin", 2), ("dagny", "bertil", 1), ("bertil", "corwin", 1)}
GRAPH_NODES = {"annika": "orchestrator", "bertil": "worker", "corwin": "worker", "dagny": "no role"}


def message_count(count):
    """`1 message` or `<n> messages`.

    @interacts  none.
    @deps       none.
    @complexity O(1).
    @alloc      one string.
    """
    return f"{count} message" if count == 1 else f"{count} messages"


class PageTest(unittest.TestCase):
    """The page's frame: one self-contained HTML file with its title, lang, warning or scrub line, and escaped text.

    @interacts  builds the fixture; renders it in this process.
    @deps       rendered, charts.
    @complexity a few renders of 12 messages.
    @alloc      the pages.
    """

    def test_the_page_is_self_contained_with_a_title_lang_and_a_title_and_desc_in_each_svg(self):
        """No script, no link, no http, no url(; a <title>, lang, and each SVG's <title> and <desc>.

        @interacts  see the class.
        @deps       rendered, charts.
        @complexity O(p) over the page.
        @alloc      the page.
        """
        for scrub in (False, True):
            with self.subTest(scrub=scrub):
                _, page = rendered(scrub)
                self.assertTrue(page.startswith("<!doctype html>"))
                self.assertIn('<html lang="en">', page)
                self.assertRegex(page, r"<title>[^<]+</title>")
                for banned in ("<script", "<link", "http", "url(", "@import", "<img", "<iframe"):
                    self.assertNotIn(banned, page.lower())
                found = charts(page)
                self.assertTrue(found)
                for key, svg in found.items():
                    self.assertTrue(svg.find("title") is not None and svg.find("title").text, key)
                    self.assertTrue(svg.find("desc") is not None and svg.find("desc").text, key)

    def test_the_real_page_warns_and_the_scrubbed_page_says_it_is_scrubbed(self):
        """The unscrubbed page carries C7's warning on its face; the scrubbed page does not, and says it is scrubbed.

        @interacts  see the class.
        @deps       rendered.
        @complexity two renders.
        @alloc      the pages.
        """
        warning = "Holds real session names and times. Share only a --scrub copy."
        _, real = rendered(False)
        _, safe = rendered(True)
        self.assertIn(warning, real)
        self.assertNotIn(warning, safe)
        self.assertIn("Scrubbed:", safe)
        self.assertNotIn("Scrubbed:", real)

    def test_every_text_node_and_attribute_is_escaped(self):
        """A name holding markup reaches the page only escaped.

        @interacts  loads report.py; renders a hand-made page.
        @deps       report.render, report.Page, report.Record, report.Session.
        @complexity O(1).
        @alloc      one small page.
        """
        report = _root.load_source("board_report", REPORT_PATH)
        bad = '<b x="1">&'
        record = report.Record(1, bad, "ben", fixture.BASE, None, 10, "FYI", ())
        page = report.render(report.Page((record,), (report.Session(bad, None, None, None),
                                                    report.Session("ben", None, None, None)), 0, False, fixture.BASE))
        self.assertNotIn(bad, page)
        self.assertNotIn("<b ", page)
        self.assertIn("&lt;b x=&quot;1&quot;&gt;&amp;", page)
        charts(page)

    def test_an_empty_mailbox_draws_every_chart_with_words(self):
        """No messages: the page still renders, each chart saying so in words.

        @interacts  loads report.py; renders an empty page.
        @deps       report.render, report.Page.
        @complexity O(1).
        @alloc      one small page.
        """
        report = _root.load_source("board_report", REPORT_PATH)
        page = report.render(report.Page((), (), 0, True, None))
        self.assertEqual(set(charts(page)), {"graph", "senders", "read", "quiet", "answers"})
        self.assertIn("No messages yet.", page)


class GraphTest(unittest.TestCase):
    """Chart 1: one arrow per pair and direction with its count, node shape and role word by C5's role.

    @interacts  renders the fixture.
    @deps       rendered, charts, groups, title_of.
    @complexity two renders.
    @alloc      the pages.
    """

    def test_each_arrow_carries_its_count_and_each_node_its_role(self):
        """Every edge's title and count label, exactly; every node's role, shape and word; the same on a scrubbed page under its labels, where the label alone names the role (REC-10).

        @interacts  see the class.
        @deps       see the class.
        @complexity two renders.
        @alloc      the pages.
        """
        for scrub, names in ((False, {n: n for n in fixture.NAMES}), (True, ScrubTest.LABELS)):
            with self.subTest(scrub=scrub):
                _, page = rendered(scrub)
                graph = charts(page)["graph"]
                edges = {}
                for edge in groups(graph, "edge"):
                    labels = [t.text for t in edge.iter("text")]
                    edges[title_of(edge)] = labels
                self.assertEqual(edges, {f"{names[s]} to {names[r]}: {message_count(n)}": [str(n)]
                                         for s, r, n in GRAPH_EDGES})
                nodes = {}
                for node in groups(graph, "node"):
                    nodes[node.get("data-role")] = nodes.get(node.get("data-role"), set()) | {
                        "".join(node.find("text").itertext())}
                want = {}
                for name, role in GRAPH_NODES.items():
                    want.setdefault(role, set()).add(names[name] if scrub else f"{names[name]} · {role}")
                self.assertEqual(nodes, want)
                shapes = {node.get("data-role"): node[1].tag + (node[1].get("rx") or "") +
                          (node[1].get("stroke-dasharray") or "") for node in groups(graph, "node")}
                self.assertEqual(len(set(shapes.values())), len(shapes), shapes)


# A C0 name of the most characters (64), different at its end, for the
# tests that a long name never runs past the left edge.
LONG_NAME = "lng" + "q" * 53 + "-endpart"
# The fewest pixels a page's text may draw at (MEDIUM-1).
MIN_TEXT_PX = 11


def text_start(text, report):
    """Where `text` (an SVG <text> element) starts, estimated as report.py estimates it (its char_width): its x less its width for an end anchor, half for a middle one.

    @interacts  none.
    @deps       report.char_width.
    @complexity O(c) over c characters.
    @alloc      none.
    """
    wide = len(text.text or "") * report.char_width(text.get("class"))
    share = {"end": 1, "middle": 0.5}.get(text.get("text-anchor"), 0)
    return float(text.get("x")) - wide * share


class LegibleTest(unittest.TestCase):
    """MEDIUM-1 and MEDIUM-2: no chart scales its text under MIN_TEXT_PX, and no text starts left of x 0, a 64-character name included.

    @interacts  builds the fixture plus a long-named session; renders it.
    @deps       modules_for, charts, text_start, fixture.
    @complexity a few renders.
    @alloc      one TcRoot per test.
    """

    def long_page(self, scrub=False):
        """The fixture with a session named LONG_NAME that mails annika and is mailed back, rendered in process: (report, page).

        @interacts  builds the fixture and two more messages and a
                    read-time record under a TcRoot; loads tc and report.py.
        @deps       fixture, modules_for.
        @complexity one render.
        @alloc      one TcRoot, removed before return.
        """
        with _root.TcRoot() as root:
            fixture.build(root.path)
            box = root.path / "mail" / f"to-{LONG_NAME}" / "read"
            box.mkdir(parents=True)
            (root.path / "mail" / "to-annika" / f"000013-from-{LONG_NAME}.md").write_text(
                f"# #13 from {LONG_NAME} to annika, {fixture.at(18 * fixture.HOUR)}\n\nQUESTION #12\n", encoding="utf-8")
            (box / "000014-from-annika.md").write_text(
                f"# #14 from annika to {LONG_NAME}, {fixture.at(19 * fixture.HOUR)}\n\nANSWER re #13\n",
                encoding="utf-8")
            (box / ".read-times").write_text(
                '{"name": "000014-from-annika.md", "number": 14, "read": "%s"}\n' % fixture.at(20 * fixture.HOUR),
                encoding="utf-8")
            tc, report = modules_for(root)
            page = report.page_of(report.extract(tc), None)
            return report, report.render(report.scrub(page) if scrub else page)

    def test_no_text_starts_left_of_zero_and_a_cut_name_keeps_its_end_and_its_whole_in_a_title(self):
        """In every chart, every text's estimated start is at x 0 or right of it; the long name, where cut, shows its end after three periods and holds itself whole in a <title>.

        @interacts  see the class.
        @deps       see the class.
        @complexity one render.
        @alloc      the page.
        """
        report, page = self.long_page()
        cut = 0
        for key, chart in charts(page).items():
            for text in chart.iter("text"):
                with self.subTest(chart=key, text=text.text):
                    self.assertGreaterEqual(text_start(text, report), 0)
                title = text.find("title")
                if title is not None and title.text == LONG_NAME:
                    cut += 1
                    self.assertTrue(text.text.startswith("..."), text.text)
                    self.assertTrue(text.text.endswith("-endpart"), text.text)
        self.assertGreater(cut, 0, "the long name was never cut, so this test checked no cut")
        self.assertIn(LONG_NAME, page)

    def test_each_chart_has_a_width_floor_that_keeps_its_smallest_text_at_11_px(self):
        """Each SVG's min-width is its width x MIN_TEXT_PX / SMALL_TEXT_UNITS, rounded up, and no SVG text rule is smaller than SMALL_TEXT_UNITS.

        @interacts  see the class.
        @deps       see the class; re.
        @complexity two renders.
        @alloc      the pages.
        """
        for scrub in (False, True):
            report, page = self.long_page(scrub)
            self.assertEqual(report.MIN_TEXT_PX, MIN_TEXT_PX)
            sizes = [int(n) for n in re.findall(r"svg[^{]*\{[^}]*font-size:(\d+)px", report.PAGE_CSS)]
            sizes += [int(n) for n in re.findall(r"svg text\{font:(\d+)px", report.PAGE_CSS)]
            self.assertTrue(sizes)
            self.assertEqual(min(sizes), report.SMALL_TEXT_UNITS)
            for key, chart in charts(page).items():
                with self.subTest(scrub=scrub, chart=key):
                    width = float(chart.get("viewBox").split()[2])
                    floor = -(-int(width * MIN_TEXT_PX) // report.SMALL_TEXT_UNITS)
                    self.assertEqual(chart.get("style"), f"min-width:{floor}px")


def series_of(plot):
    """The series groups inside one plot group.

    @interacts  none.
    @deps       groups.
    @complexity O(n) over n nodes under it.
    @alloc      one list.
    """
    return groups(plot, "series")


def plots_by_label(chart):
    """{the label of a plot's first series: that plot} for every plot in `chart`.

    @interacts  none.
    @deps       groups, series_of.
    @complexity O(n) over n nodes in the chart.
    @alloc      one dict.
    """
    return {plot.get("data-plot"): plot for plot in groups(chart, "plot")}


def mark_titles(series):
    """The <title> text of every mark (a shape with a title) in a series, in order.

    @interacts  none.
    @deps       title_of.
    @complexity O(n) over n nodes under it.
    @alloc      one list.
    """
    return [title_of(mark) for mark in series.iter() if mark.tag in ("rect", "path", "circle", "g")
            and mark is not series and title_of(mark) is not None]


class SendersTest(unittest.TestCase):
    """Chart 2: messages over time per sender, one row each, hour or day buckets by a named rule.

    @interacts  renders the fixture.
    @deps       rendered, charts, plots_by_label, series_of, mark_titles.
    @complexity two renders.
    @alloc      the pages.
    """

    # The fixture's sent times, by sender, as (hour bucket, count); 10 has no time.
    BARS = {"annika": [(0, 2), (3, 1), (4, 1), (16, 1)], "bertil": [(0, 1), (2, 1), (5, 1)],
            "corwin": [(3, 1), (17, 1)], "dagny": [(6, 1)]}
    PEAKS = {"annika": 2, "bertil": 1, "corwin": 1, "dagny": 1}

    def test_the_bucket_is_an_hour_up_to_a_week_and_a_day_past_it(self):
        """bucket_seconds(span): an hour for a span of HOURLY_UP_TO_SECONDS or less, a day past it.

        @interacts  loads report.py.
        @deps       report.bucket_seconds, report.HOURLY_UP_TO_SECONDS.
        @complexity O(1).
        @alloc      none.
        """
        report = _root.load_source("board_report", REPORT_PATH)
        self.assertEqual(report.HOURLY_UP_TO_SECONDS, 7 * 24 * fixture.HOUR)
        self.assertEqual(report.bucket_seconds(0), fixture.HOUR)
        self.assertEqual(report.bucket_seconds(report.HOURLY_UP_TO_SECONDS), fixture.HOUR)
        self.assertEqual(report.bucket_seconds(report.HOURLY_UP_TO_SECONDS + 1), 24 * fixture.HOUR)

    def test_one_row_per_sender_with_a_bar_per_busy_hour(self):
        """Each sender's row: its label at its left, its count and peak, and one titled bar per hour it sent in.

        @interacts  see the class.
        @deps       see the class.
        @complexity two renders.
        @alloc      the pages.
        """
        for scrub, names in ((False, {n: n for n in fixture.NAMES}), (True, ScrubTest.LABELS)):
            with self.subTest(scrub=scrub):
                _, page = rendered(scrub)
                chart = charts(page)["senders"]
                plots = plots_by_label(chart)
                self.assertEqual(list(plots), [names[n] for n in self.BARS])
                for sender, bars in self.BARS.items():
                    (series,) = series_of(plots[names[sender]])
                    self.assertEqual(series.get("data-label"), names[sender])
                    texts = [t.text for t in series.iter("text")]
                    total = sum(count for _, count in bars)
                    self.assertEqual(texts, [names[sender], f"{total} sent · peak {self.PEAKS[sender]} in an hour"])
                    want = []
                    for bucket, count in bars:
                        start = (f"T+{bucket}h00m" if bucket else "T+0") if scrub else \
                            fixture_time(bucket * fixture.HOUR).isoformat(sep=" ", timespec="minutes")
                        want.append(f"{start}: {count} sent")
                    self.assertEqual(mark_titles(series), want)
                self.assertIn("one hour", words(chart))


def read_text(offset, scrub):
    """The fixture time `offset` as a page shows it: `T+<span>` scrubbed, the date, clock and offset when real.

    @interacts  none.
    @deps       fixture_time.
    @complexity O(1).
    @alloc      one string.
    """
    if not scrub:
        return fixture_time(offset).isoformat(sep=" ", timespec="minutes")
    hours, minutes = divmod(offset // fixture.MINUTE, 60)
    return f"T+{hours}h{minutes:02d}m" if hours else f"T+{minutes}m"


class ReadTest(unittest.TestCase):
    """Chart 3: sent to read, per recipient: one dot per message with a read time, the median as a labeled tick, and `n of m`.

    @interacts  renders the fixture.
    @deps       rendered, charts, plots_by_label, series_of, mark_titles.
    @complexity two renders.
    @alloc      the pages.
    """

    # Per recipient: (n of m words, median words, each dot's title as
    # (number, tag, sender, read offset, read after)).
    STRIPS = {
        "annika": ("3 of 5 messages have a read time", "median 20m",
                   [(2, "QUESTION", "bertil", 12 * fixture.MINUTE, "2m"),
                    (4, None, "bertil", 2 * fixture.HOUR + 20 * fixture.MINUTE, "20m"),
                    (8, "ANSWER", "bertil", 5 * fixture.HOUR + 30 * fixture.MINUTE, "30m")]),
        "bertil": ("3 of 4 messages have a read time", "median 5m",
                   [(1, "PLAN", "annika", 5 * fixture.MINUTE, "5m"), (3, "ANSWER", "annika", fixture.HOUR, "40m"),
                    (9, "FYI", "dagny", 6 * fixture.HOUR + fixture.MINUTE, "1m")]),
        "corwin": ("1 of 2 messages have a read time", "median 30m",
                   [(6, None, "annika", 4 * fixture.HOUR, "30m")]),
    }

    def test_the_delay_axis_labels_its_far_end_and_each_tick_the_data_reaches(self):
        """Chart 3's axis: 0s, 1m and 10m (each tick under the longest wait), then the longest wait itself, 40m, at its far end; chart 5's ends at 1h40m.

        @interacts  renders the fixture.
        @deps       rendered, charts, groups.
        @complexity one render.
        @alloc      the page.
        """
        _, page = rendered()
        found = charts(page)
        read = [t.text for g in groups(found["read"], "delay-tick") for t in g.iter("text")]
        self.assertEqual(read, ["0s", "1m", "10m", "40m"])
        answers = [t.text for g in groups(found["answers"], "delay-tick") for t in g.iter("text")]
        self.assertEqual(answers[-1], "1h40m")
        self.assertEqual(answers[:3], ["0s", "1m", "10m"])

    def test_each_strip_has_its_dots_its_median_and_its_count_in_words(self):
        """Exact dots, median and words per recipient, real and scrubbed; dagny, who got no mail, has no strip.

        @interacts  see the class.
        @deps       see the class.
        @complexity two renders.
        @alloc      the pages.
        """
        for scrub, names in ((False, {n: n for n in fixture.NAMES}), (True, ScrubTest.LABELS)):
            with self.subTest(scrub=scrub):
                _, page = rendered(scrub)
                plots = plots_by_label(charts(page)["read"])
                self.assertEqual(list(plots), [names[n] for n in self.STRIPS])
                for recipient, (count, median, dots) in self.STRIPS.items():
                    (series,) = series_of(plots[names[recipient]])
                    self.assertEqual([t.text for t in series.iter("text")], [names[recipient], count, median])
                    self.assertEqual(len(list(series.iter("circle"))), len(dots))
                    want = [f"#{ScrubTest.RANKS[n] if scrub else n}{' ' + tag if tag else ''} from {names[sender]}: "
                            f"read {read_text(read, scrub)}, after {after}" for n, tag, sender, read, after in dots]
                    self.assertEqual(mark_titles(series), want)


class QuietTest(unittest.TestCase):
    """Chart 4: one lane per session, ticks for mail sent and received, and every gap of QUIET_GAP_SECONDS or more hatched and labeled.

    @interacts  renders the fixture.
    @deps       rendered, charts, plots_by_label, series_of, groups.
    @complexity two renders.
    @alloc      the pages.
    """

    # Per name: (sent ticks, received ticks, each quiet gap's label).
    LANES = {"annika": (5, 5, ["quiet 11h00m"]), "bertil": (3, 4, ["quiet 3h00m", "quiet 10h00m"]),
             "corwin": (2, 2, ["quiet 12h50m"]), "dagny": (1, 0, [])}

    def test_each_lane_has_its_ticks_and_its_quiet_gaps(self):
        """Exact tick counts per series and exact gap labels per lane, real and scrubbed; each gap is hatched.

        @interacts  see the class.
        @deps       see the class; report.QUIET_GAP_SECONDS.
        @complexity two renders.
        @alloc      the pages.
        """
        for scrub, names in ((False, {n: n for n in fixture.NAMES}), (True, ScrubTest.LABELS)):
            with self.subTest(scrub=scrub):
                report, page = rendered(scrub)
                self.assertEqual(report.QUIET_GAP_SECONDS, 3 * fixture.HOUR)
                plots = plots_by_label(charts(page)["quiet"])
                self.assertEqual(list(plots), [names[n] for n in self.LANES])
                for name, (sent, received, gaps) in self.LANES.items():
                    plot = plots[names[name]]
                    series = {s.get("data-label"): s for s in series_of(plot)}
                    self.assertEqual(list(series), ["sent", "received"])
                    self.assertEqual(len(groups(series["sent"], "tick")), sent)
                    self.assertEqual(len(groups(series["received"], "tick")), received)
                    quiet = groups(plot, "quiet")
                    self.assertEqual([t.text for q in quiet for t in q.iter("text")], gaps)
                    for gap in quiet:
                        self.assertIn("hatch", [p.get("class") for p in gap.iter("path")])


class AnswersTest(unittest.TestCase):
    """Chart 5: a message whose first line names #N and goes from #N's recipient back to #N's sender answers #N, whatever its tag.

    @interacts  renders the fixture; loads tc and report.py.
    @deps       rendered, charts, plots_by_label, series_of, mark_titles,
                modules_for.
    @complexity two renders and one extract.
    @alloc      the pages.
    """

    # Per answerer: (detail words, median words, each dot as (ask, its tag,
    # answer, its tag, time)). annika answered 2 (by 3, `ANSWER re #2`) and
    # 5 (by 6, `#5 got it`); bertil answered 1 (by 2) and 3 (by 4, `Re #3`).
    STRIPS = {
        "annika": ("2 answers", "median 20m", [(2, "QUESTION", 3, "ANSWER", "10m"), (5, fixture.PLANTED_TAG, 6, None, "30m")]),
        "bertil": ("2 answers", "median 55m", [(1, "PLAN", 2, "QUESTION", "10m"), (3, "ANSWER", 4, None, "1h40m")]),
    }

    def test_replies_pair_by_their_named_number_and_direction_only(self):
        """The pairs, exactly: `ANSWER re #N` and `Re #N:` both pair; 7 (the wrong way round) and 8 (no #N) do not.

        @interacts  builds the fixture; loads tc and report.py.
        @deps       report.answer_pairs, report.extract.
        @complexity O(12).
        @alloc      the records.
        """
        with _root.TcRoot() as root:
            fixture.build(root.path)
            tc, report = modules_for(root)
            pairs = report.answer_pairs(report.extract(tc).records)
            self.assertEqual([(ask.number, answer.number) for ask, answer in pairs], [(1, 2), (2, 3), (3, 4), (5, 6)])

    def test_each_answerer_strip_has_its_pairs_its_median_and_the_unanswered_asks_in_words(self):
        """Exact dots, titles and medians per answerer, real and scrubbed, and the asks no answer names counted in words.

        @interacts  see the class.
        @deps       see the class.
        @complexity two renders.
        @alloc      the pages.
        """
        for scrub, names in ((False, {n: n for n in fixture.NAMES}), (True, ScrubTest.LABELS)):
            with self.subTest(scrub=scrub):
                _, page = rendered(scrub)
                chart = charts(page)["answers"]
                plots = plots_by_label(chart)
                self.assertEqual(list(plots), [names[n] for n in self.STRIPS])
                for answerer, (detail, median, dots) in self.STRIPS.items():
                    (series,) = series_of(plots[names[answerer]])
                    self.assertEqual([t.text for t in series.iter("text")], [names[answerer], detail, median])
                    want = []
                    for ask, ask_tag, answer, answer_tag, after in dots:
                        if scrub and ask_tag == fixture.PLANTED_TAG:
                            ask_tag = "other"
                        want.append(f"#{ask}{' ' + ask_tag if ask_tag else ''} to "
                                    f"#{answer}{' ' + answer_tag if answer_tag else ''}: {after}")
                    self.assertEqual(mark_titles(series), want)
                self.assertIn("4 answers name the message they answer.", words(chart))
                self.assertIn("1 ask has no reply that names it.", words(chart))
                self.assertIn(ASK_CAVEAT, words(chart))
                self.assertNotIn("nobody answered", page)
                self.assertNotIn("unanswered", page)

    def ask_words(self, records):
        """Chart 5's words for a hand-made page of `records` among ann and ben.

        @interacts  loads report.py; renders one chart.
        @deps       report.chart_answers, report.Page, report.Session.
        @complexity O(r) over r records.
        @alloc      one chart's text.
        """
        report = _root.load_source("board_report", REPORT_PATH)
        sessions = (report.Session("ann", None, None, None), report.Session("ben", None, None, None))
        return words(charts(report.chart_answers(report.Page(tuple(records), sessions, 0, False, None)))["answers"])

    def test_each_ask_tag_counts_and_other_tags_do_not(self):
        """Each of C7's five ask tags, alone and unreplied, is one ask with no reply; FYI is none; all five are five.

        @interacts  loads report.py.
        @deps       ask_words; report.ASK_TAGS, report.Record.
        @complexity O(1) per tag.
        @alloc      the pages.
        """
        report = _root.load_source("board_report", REPORT_PATH)
        self.assertEqual(report.ASK_TAGS, ("QUESTION", "PLAN-READY", "PLAN-CHECK", "MERGE", "BLOCKED"))

        def one(number, tag, sent=0):
            """One message from ann to ben tagged `tag`, `sent` seconds after the fixture's base (None: no time).

            @interacts  none.
            @deps       report.Record, fixture_time.
            @complexity O(1).
            @alloc      one record.
            """
            return report.Record(number, "ann", "ben", fixture_time(sent), None, 10, tag, ())

        for tag in report.ASK_TAGS:
            with self.subTest(tag=tag):
                self.assertIn("1 ask has no reply that names it.", self.ask_words([one(1, tag)]))
        self.assertIn("0 asks have no reply that names them.", self.ask_words([one(1, "FYI")]))
        every = [one(n, tag) for n, tag in enumerate(report.ASK_TAGS, 1)]
        self.assertIn("5 asks have no reply that names them.", self.ask_words(every))

    def test_an_ask_with_no_sent_time_is_left_out_of_the_count_and_said(self):
        """A QUESTION whose header did not parse is not counted as having no reply, and the words say one was left out.

        @interacts  loads report.py.
        @deps       ask_words; report.Record.
        @complexity O(1).
        @alloc      the page.
        """
        report = _root.load_source("board_report", REPORT_PATH)
        records = [report.Record(1, "ann", "ben", fixture_time(0), None, 10, "FYI", ()),
                   report.Record(2, "ann", "ben", None, None, 10, "QUESTION", ())]
        text = self.ask_words(records)
        self.assertIn("0 asks have no reply that names them.", text)
        self.assertIn("1 ask has no sent time and is left out of this count.", text)


def run_report(root, *args, out=None):
    """Run `tc report OUT [args]` through the harness, OUT in the root's temp folder (outside the mailbox): (exit, stdout, stderr, page text or None).

    @interacts  runs ../tc report as a child under the root's TC_ROOT;
                reads the page it wrote.
    @deps       _root.TcRoot.tc.
    @complexity the child's own work.
    @alloc      the page text, returned.
    """
    out = out or root.base / "out" / "report.html"
    out.parent.mkdir(exist_ok=True)
    code, stdout, stderr = root.tc("report", str(out), *args)
    return code, stdout, stderr, out.read_text(encoding="utf-8") if out.exists() else None


def tree(folder):
    """Every entry under `folder` as {relative path: (kind, bytes or link target or None, mode)}: a snapshot to compare byte for byte.

    @interacts  walks `folder` without following links; reads each file.
    @deps       os, pathlib, stat.
    @complexity O(f + b) over f entries and b bytes (the fixture: a few dozen files).
    @alloc      one dict, returned.
    """
    found = {}
    for path in sorted(folder.rglob("*")):
        st = path.lstat()
        if path.is_symlink():
            found[str(path.relative_to(folder))] = ("link", os.readlink(path), st.st_mode)
        elif path.is_dir():
            found[str(path.relative_to(folder))] = ("folder", None, st.st_mode)
        else:
            found[str(path.relative_to(folder))] = ("file", path.read_bytes(), st.st_mode)
    return found


class CommandTest(unittest.TestCase):
    """`tc report OUT [--scrub] [--force] [--at TIME]`: refusals, exits, a mailbox left as it was, and a page with nothing fetched.

    @interacts  builds the fixture under a TcRoot; runs tc report as a
                child; copies tc alone into the root's temp folder once.
    @deps       run_report, tree, fixture.build; _root.TcRoot, _root.TC.
    @complexity a few tc children per test.
    @alloc      one TcRoot per test, removed on exit.
    """

    def test_an_existing_file_is_refused_without_force_and_replaced_with_it(self):
        """Exit 1 with words and the old file untouched without --force; exit 0 and a new page with it; no .tmp left.

        @interacts  see the class.
        @deps       see the class.
        @complexity three children.
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            fixture.build(root.path)
            out = root.base / "out" / "report.html"
            out.parent.mkdir()
            out.write_text("keep me", encoding="utf-8")
            code, stdout, stderr, page = run_report(root, out=out)
            self.assertEqual((code, page), (EXIT_REFUSED, "keep me"), stderr)
            self.assertIn("--force", stderr)
            self.assertIn(str(out), stderr)
            code, stdout, stderr, page = run_report(root, "--force", out=out)
            self.assertEqual(code, EXIT_OK, stderr)
            self.assertTrue(page.startswith("<!doctype html>"))
            self.assertEqual(stdout.strip(), f"wrote {out.resolve()}: 12 messages, real names and times. Mailbox "
                                             f"{root.path}, from TC_ROOT.")
            self.assertEqual(sorted(p.name for p in out.parent.iterdir()), ["report.html"])

    def test_the_mailbox_is_unchanged_byte_for_byte(self):
        """A report, scrubbed or not, writes nothing in the mailbox: every entry under TC_ROOT is as it was.

        @interacts  see the class.
        @deps       see the class.
        @complexity two children and two walks.
        @alloc      two snapshots.
        """
        with _root.TcRoot() as root:
            fixture.build(root.path)
            before = tree(root.path)
            for args in ((), ("--scrub", "--force")):
                code, _, stderr, _ = run_report(root, *args)
                self.assertEqual(code, EXIT_OK, stderr)
            self.assertEqual(tree(root.path), before)

    def test_the_page_fetches_nothing(self):
        """No script tag, no http, no url( in either page the command writes.

        @interacts  see the class.
        @deps       see the class.
        @complexity two children.
        @alloc      the pages.
        """
        with _root.TcRoot() as root:
            fixture.build(root.path)
            for args in ((), ("--scrub", "--force")):
                code, _, stderr, page = run_report(root, *args)
                self.assertEqual(code, EXIT_OK, stderr)
                for banned in ("<script", "http", "url("):
                    self.assertNotIn(banned, page.lower(), args)

    def test_a_one_file_copy_of_tc_refuses_saying_where_it_looked(self):
        """tc copied alone, with no board/ beside it, then with report.py and no serve.py: each exit 1, words naming the file it looked for, nothing written.

        @interacts  copies ../tc into the root's temp folder and runs the copy.
        @deps       shutil-free copy by bytes; subprocess through root.start.
        @complexity one child.
        @alloc      the copy, removed with the root.
        """
        with _root.TcRoot() as root:
            fixture.build(root.path)
            lone = root.base / "lone"
            lone.mkdir()
            (lone / "tc").write_bytes(_root.TC.read_bytes())
            out = root.base / "lone-report.html"
            proc = root.start(argv=[sys.executable, str(lone / "tc"), "report", str(out)])
            stdout, stderr = proc.communicate(timeout=_root.DEFAULT_TC_TIMEOUT_SECONDS)
            self.assertEqual(proc.returncode, EXIT_REFUSED, stderr)
            self.assertIn(f"tc report: no renderer at {lone / 'board' / 'report.py'}", stderr)
            self.assertNotIn("Traceback", stderr)
            self.assertFalse(out.exists())
            (lone / "board").mkdir()
            (lone / "board" / "report.py").write_bytes(REPORT_PATH.read_bytes())
            proc = root.start(argv=[sys.executable, str(lone / "tc"), "report", str(out)])
            stdout, stderr = proc.communicate(timeout=_root.DEFAULT_TC_TIMEOUT_SECONDS)
            self.assertEqual(proc.returncode, EXIT_REFUSED, stderr)
            self.assertIn(f"tc report: no board/serve.py at {lone / 'board' / 'serve.py'}", stderr)
            self.assertNotIn("Traceback", stderr)
            self.assertFalse(out.exists())

    def test_a_page_that_cannot_be_written_refuses_with_words(self):
        """OUT in a folder that is not there: exit 1, words naming OUT, nothing written (pause DASH-2's recommendation).

        @interacts  see the class.
        @deps       see the class.
        @complexity one child.
        @alloc      none.
        """
        with _root.TcRoot() as root:
            fixture.build(root.path)
            out = root.base / "no-such-folder" / "report.html"
            code, _, stderr = root.tc("report", str(out))
            self.assertEqual(code, EXIT_REFUSED, stderr)
            self.assertIn(f"could not write {out}", stderr)
            self.assertNotIn("Traceback", stderr)
            self.assertFalse(out.parent.exists())

    def test_a_page_inside_the_mailbox_is_refused_and_roots_top_level_is_allowed(self):
        """An OUT in mail/, status/, cards/ or outbox/, named straight or through a link, refuses (exit 1, words naming its folder, nothing written); one at ROOT's top level is written.

        @interacts  see the class; makes outbox/ and one link in the root's temp folder.
        @deps       see the class.
        @complexity five children.
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            fixture.build(root.path)
            (root.path / "outbox").mkdir()
            link = root.base / "into-mail"
            link.symlink_to(root.path / "mail")
            cases = {"mail": root.path / "mail" / "to-annika" / "x.html", "status": root.path / "status" / "x.html",
                     "cards": root.path / "cards" / "x.html", "outbox": root.path / "outbox" / "x.html",
                     "link": link / "x.html"}
            for case, out in cases.items():
                with self.subTest(case=case):
                    before = tree(root.path)
                    code, _, stderr = root.tc("report", str(out))
                    self.assertEqual(code, EXIT_REFUSED, stderr)
                    self.assertTrue(stderr.startswith("tc report: "), stderr)
                    self.assertIn(os.path.realpath(out.parent), stderr)
                    self.assertIn("inside the mailbox", stderr)
                    self.assertEqual(tree(root.path), before)
            code, _, stderr = root.tc("report", str(root.path / "top.html"))
            self.assertEqual(code, EXIT_OK, stderr)
            self.assertTrue((root.path / "top.html").read_text(encoding="utf-8").startswith("<!doctype html>"))

    def test_a_file_made_at_out_between_the_check_and_the_publish_is_kept(self):
        """In process: a file appears at OUT after the existence check and before the publish; without --force it stays, the run refuses, and no .tmp is left.

        @interacts  loads tc in this process (modules_for) and runs its
                    cmd_report with the .tmp's random name stubbed so the
                    stub makes the file at OUT first.
        @deps       modules_for, mock; tc.cmd_report.
        @complexity one in-process report.
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            fixture.build(root.path)
            tc, _ = modules_for(root)
            out = root.base / "out" / "race.html"
            out.parent.mkdir()

            def late(_):
                """Make a file at OUT, as another process would, then give a fixed .tmp name.

                @interacts  writes OUT.
                @deps       none.
                @complexity O(1).
                @alloc      one file.
                """
                out.write_text("late", encoding="utf-8")
                return "0" * 16

            with mock.patch.object(tc.secrets, "token_hex", late):
                with self.assertRaises(SystemExit) as stop:
                    tc.cmd_report(argparse.Namespace(out=str(out), scrub=False, force=False, at=None))
            self.assertEqual(stop.exception.code, EXIT_REFUSED)
            self.assertEqual(out.read_text(encoding="utf-8"), "late")
            self.assertEqual(sorted(p.name for p in out.parent.iterdir()), ["race.html"])

    def test_an_out_name_at_the_name_limit_is_written(self):
        """An OUT whose name is 255 bytes, the most Linux allows, is written: the .tmp's name never grows from it.

        @interacts  see the class.
        @deps       see the class.
        @complexity one child.
        @alloc      one TcRoot.
        """
        with _root.TcRoot() as root:
            fixture.build(root.path)
            out = root.base / ("a" * 250 + ".html")
            code, _, stderr = root.tc("report", str(out))
            self.assertEqual(code, EXIT_OK, stderr)
            self.assertTrue(out.exists())

    def test_refusals_open_with_tc_report_under_any_invoked_name(self):
        """Run through a link named tconn, a refusal still opens `tc report:` (NAME's rule for prefixes).

        @interacts  see the class; makes one link in the root's temp folder.
        @deps       root.start; _root.TC.
        @complexity one child.
        @alloc      the link.
        """
        with _root.TcRoot() as root:
            fixture.build(root.path)
            link = root.base / "tconn"
            link.symlink_to(_root.TC)
            out = root.base / "taken.html"
            out.write_text("keep me", encoding="utf-8")
            proc = root.start(argv=[sys.executable, str(link), "report", str(out)])
            _, stderr = proc.communicate(timeout=_root.DEFAULT_TC_TIMEOUT_SECONDS)
            self.assertEqual(proc.returncode, EXIT_REFUSED, stderr)
            self.assertTrue(stderr.startswith("tc report: "), stderr)

    def test_usage_errors_exit_9(self):
        """No OUT, an unknown flag, and an --at that is not a time with its offset each exit 9.

        @interacts  see the class.
        @deps       see the class.
        @complexity four children.
        @alloc      none.
        """
        with _root.TcRoot() as root:
            for args in (("report",), ("report", "x.html", "--bogus"), ("report", "x.html", "--at", "noon"),
                         ("report", "x.html", "--at", "2026-10-03T12:30:00")):
                with self.subTest(args=args):
                    code, _, stderr = root.tc(*args)
                    self.assertEqual(code, EXIT_USAGE, stderr)


class SafetyTest(unittest.TestCase):
    """The planted-secret test, the scrub test, the accessibility test and determinism, on the pages the command writes.

    @interacts  builds the fixture; runs tc report as a child.
    @deps       run_report, charts, groups, series_of, fixture.
    @complexity a few children per test.
    @alloc      one TcRoot per test.
    """

    def pages(self, *extra):
        """The fixture's unscrubbed and scrubbed pages, each from one run of the command with `extra`: (real, scrubbed).

        @interacts  builds the fixture; two tc children.
        @deps       run_report; _root.TcRoot.
        @complexity two children.
        @alloc      one TcRoot, removed before return; the two pages.
        """
        with _root.TcRoot() as root:
            fixture.build(root.path)
            pages = []
            for args in ((), ("--scrub",)):
                out = root.base / "out" / f"report{len(pages)}.html"
                code, _, stderr, page = run_report(root, *args, *extra, out=out)
                self.assertEqual(code, EXIT_OK, stderr)
                pages.append(page)
            return tuple(pages)

    def test_planted_secrets_are_in_neither_page(self):
        """A word after a tag, a word on a second body line, a header note, a card field and a status file: absent from both pages, byte for byte.

        @interacts  see the class.
        @deps       fixture.SECRETS.
        @complexity two children.
        @alloc      the pages.
        """
        real, safe = self.pages()
        for secret in fixture.SECRETS:
            with self.subTest(secret=secret):
                self.assertNotIn(secret.encode(), real.encode("utf-8"))
                self.assertNotIn(secret.encode(), safe.encode("utf-8"))

    def test_the_scrubbed_page_holds_no_name_no_planted_tag_no_date_and_no_clock(self):
        """Scrubbed: no fixture name, not the off-list tag, no date, no clock, with --at too. Unscrubbed: every one of them there, so the test cannot pass by accident.

        @interacts  see the class.
        @deps       fixture.NAMES, fixture.PLANTED_TAG, DATE_PATTERN, CLOCK_PATTERN.
        @complexity four children.
        @alloc      the pages.
        """
        for extra in ((), ("--at", AT_TIME)):
            with self.subTest(at=extra):
                real, safe = self.pages(*extra)
                for name in fixture.NAMES:
                    self.assertIn(name, real)
                    self.assertNotIn(name, safe)
                self.assertIn(fixture.PLANTED_TAG, real)
                self.assertNotIn(fixture.PLANTED_TAG, safe)
                self.assertRegex(real, DATE_PATTERN)
                self.assertRegex(real, CLOCK_PATTERN)
                self.assertIsNone(DATE_PATTERN.search(safe), DATE_PATTERN.search(safe))
                self.assertIsNone(CLOCK_PATTERN.search(safe), CLOCK_PATTERN.search(safe))
                for spec in fixture.MESSAGES:
                    for offset in (spec.sent, spec.read):
                        if offset is not None:
                            self.assertIn(fixture_time(offset).isoformat(sep=" ", timespec="minutes"), real)

    def test_series_that_share_a_plot_differ_in_shape_and_dash_and_each_has_a_label(self):
        """In every plot of every chart, real and scrubbed: no two series share a marker shape, none share a dash, and each series holds a text naming it.

        @interacts  see the class.
        @deps       charts, groups, series_of.
        @complexity two children.
        @alloc      the pages.
        """
        shared = 0
        for page in self.pages():
            for key, chart in charts(page).items():
                for plot in groups(chart, "plot"):
                    series = series_of(plot)
                    with self.subTest(chart=key, plot=plot.get("data-plot")):
                        self.assertTrue(series)
                        shapes = [s.get("data-shape") for s in series]
                        dashes = [s.get("data-dash") for s in series]
                        self.assertEqual(len(set(shapes)), len(shapes), shapes)
                        self.assertEqual(len(set(dashes)), len(dashes), dashes)
                        for one in series:
                            label = one.get("data-label")
                            self.assertTrue(label)
                            self.assertTrue(any(label in (t.text or "") for t in one.iter("text")), label)
                    shared += len(series) > 1
        self.assertGreater(shared, 0, "no plot with two series was checked")

    def test_the_same_mailbox_gives_the_same_bytes_and_at_changes_only_the_as_of(self):
        """Two runs, the same bytes; a run with --at differs in the as-of line alone, real and scrubbed.

        @interacts  see the class.
        @deps       see the class.
        @complexity six children.
        @alloc      the pages.
        """
        first, second, at = self.pages(), self.pages(), self.pages("--at", AT_TIME)
        self.assertEqual(first, second)
        for plain, moved in zip(first, at):
            old = re.findall(r'<p class="as-of">[^<]*</p>', plain)
            new = re.findall(r'<p class="as-of">[^<]*</p>', moved)
            self.assertEqual(len(old), 1)
            self.assertNotEqual(old, new)
            self.assertEqual(plain.replace(old[0], new[0]), moved)
        self.assertIn("As of 2026-10-03 12:30-05:00.", at[0])
        self.assertIn("As of T+2d03h.", at[1])


if __name__ == "__main__":
    unittest.main()
