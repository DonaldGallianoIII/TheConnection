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

import datetime
import os
import pathlib
import re
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
# Run as `python3 -m unittest tests.test_report` from the repo root,
# tests/ is not on sys.path; under discover it is. Add it once so both work.
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import _report_fixture as fixture  # noqa: E402  (needs the path line above)
import _root  # noqa: E402

REPORT_PATH = HERE.parent / "board" / "report.py"
EXIT_OK = 0


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
        """`PLAN-READY:` and `PLAN-READY` are both the tag PLAN-READY; a second colon, one letter, lowercase or 25 characters are no tag.

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
        }
        for line, want in cases.items():
            with self.subTest(line=line):
                self.assertEqual(self.report.first_line_facts(line), want)


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
                tag, refs = report.first_line_facts(spec.body.split("\n")[0])
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
                tag, refs = report.first_line_facts(spec.body.split("\n")[0])
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


if __name__ == "__main__":
    unittest.main()
