"""
No tracked text file holds a bidi control character (decision D46,
Trojan Source): U+202A to U+202E (embeddings and overrides) and U+2066
to U+2069 (isolates). Such a character can make source or prose read in
another order than it holds, so a reviewer sees one thing and Python or
a browser runs another.

Model:  Claude Opus 5.5 (the QA lane agent), 2026-10-18 (fix round 1)
Status: unreviewed

@interacts  runs `git ls-files -z` in the repo this file sits in; reads
            each listed file as bytes. A file holding a NUL byte in its
            first BINARY_SNIFF_BYTES is binary and skipped (the fonts);
            a file that is not UTF-8 is read with replacement, so a bidi
            mark in it is still found. Writes nothing.
@deps       python3 stdlib (pathlib, re, subprocess, unittest); git.
@complexity O(B) over B bytes of tracked files (a few MB).
@alloc      one file's bytes at a time.
"""

import pathlib
import re
import subprocess
import unittest

REPO = pathlib.Path(__file__).resolve().parent.parent
# The marks D46 names, written as escapes so this file holds none of them.
BIDI = re.compile("[\u202a-\u202e\u2066-\u2069]")
# How much of a file's head decides binary: a NUL byte there, as git and
# grep judge it.
BINARY_SNIFF_BYTES = 8000
# git answers in well under a second; this is a ceiling only.
GIT_CEILING_SECONDS = 30


class NoBidiTest(unittest.TestCase):
    """Every tracked text file is free of bidi control characters (D46).

    @interacts  see the module block.
    @deps       BIDI, BINARY_SNIFF_BYTES.
    @complexity O(B).
    @alloc      one file at a time.
    """

    def test_no_tracked_text_file_holds_a_bidi_control_character(self):
        """git ls-files lists tc at least; none of the text ones holds U+202A to U+202E or U+2066 to U+2069, each hit named with its line.

        @interacts  one git child; reads tracked files.
        @deps       subprocess; BIDI.
        @complexity O(B).
        @alloc      the list of hits.
        """
        listed = subprocess.run(["git", "-C", str(REPO), "ls-files", "-z"], capture_output=True, check=True,
                                timeout=GIT_CEILING_SECONDS).stdout.decode("utf-8").split("\0")
        names = [name for name in listed if name]
        self.assertIn("tc", names)
        hits = []
        for name in names:
            path = REPO / name
            if not path.is_file() or path.is_symlink():
                continue
            data = path.read_bytes()
            if b"\0" in data[:BINARY_SNIFF_BYTES]:
                continue
            for number, line in enumerate(data.decode("utf-8", "replace").splitlines(), 1):
                found = BIDI.search(line)
                if found:
                    hits.append(f"{name}:{number}: U+{ord(found.group(0)):04X}")
        self.assertEqual(hits, [], "bidi control characters in tracked files")


if __name__ == "__main__":
    unittest.main()
