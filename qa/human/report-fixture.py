"""
Builds the throwaway mailbox qa/human/report.md walks: the twelve
messages of tests/_report_fixture.py among four made-up names, in a fresh
folder each run, and prints one line for the shell to take in:

    eval "$(python3 qa/human/report-fixture.py)"

which sets TC_ROOT to the new mailbox and PAGES to a new, empty folder
for the pages. Given a folder (`python3 qa/human/report-fixture.py DIR`),
it builds there instead; the tests use that.

Model:  Claude Opus 5.5 (the DASH lane agent), 2026-10-17, fix round 1 (REC-12)
Status: unreviewed

@interacts  makes one folder (tempfile.mkdtemp, or the one given) with
            mailbox/ and pages/ in it, and writes the fixture under
            mailbox/ (see tests/_report_fixture.py); prints one line.
            Writes no bytecode: sys.dont_write_bytecode is set before the
            fixture module is imported.
@deps       python3 stdlib (pathlib, shlex, sys, tempfile);
            tests/_report_fixture.py.
@complexity O(12): one file per message.
@alloc      the folder and its files, kept for the walk; the person
            removes them after (the walk's last step says so).
"""

import pathlib
import shlex
import sys
import tempfile

sys.dont_write_bytecode = True
REPO = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "tests"))

import _report_fixture  # noqa: E402  (needs the two lines above)

# The new folder's name starts with this, so a person can tell it apart in /tmp.
FOLDER_PREFIX = "report-qa-"


def main(argv):
    """Build the fixture in a fresh folder (or `argv[1]`) and print the shell line that names it.

    @interacts  see the module block.
    @deps       pathlib, shlex, tempfile; _report_fixture.build.
    @complexity O(12).
    @alloc      the folder, kept.
    """
    base = pathlib.Path(argv[1]) if len(argv) > 1 else pathlib.Path(tempfile.mkdtemp(prefix=FOLDER_PREFIX))
    mailbox, pages = base / "mailbox", base / "pages"
    mailbox.mkdir(parents=True)
    pages.mkdir()
    _report_fixture.build(mailbox)
    print(f"export TC_ROOT={shlex.quote(str(mailbox))} PAGES={shlex.quote(str(pages))}")


if __name__ == "__main__":
    main(sys.argv)
