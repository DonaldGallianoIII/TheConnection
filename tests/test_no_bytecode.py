"""
Tests that loading tc or board/serve.py as a module never writes or trusts
a bytecode cache (R30). Python checks a cache by the source's size and
whole-second mtime only, so two same-size edits in one second would run
the first edit's code, and a mutation record could pass on old code.

Model:  Claude Opus 5.5 (the R30 lane agent), 2026-10-17
Status: unreviewed

Five tests:
  1. tc and serve.py loaded through _root.load_source, and through every
     loader in the suites, write no .pyc for either. Each load runs in its
     own child with bytecode writing on and PYTHONPYCACHEPREFIX pointed at
     a folder in the root's temp folder, so a cache that is written lands
     there, where the test reads it by value, and never in the checkout.
  2. The table of loaders names every load_tc and load_serve the suites
     define, and no test file but _root.py builds a loader of its own.
  3. A scratch copy of tc edited twice at the same size and the same
     mtime, loaded after each edit with bytecode writing on: the second
     load runs the second edit.
  4. The same two edits with a cache of the first planted beside the copy
     before the second load: the load still runs the second edit.
  5. Every child the harness starts sees PYTHONDONTWRITEBYTECODE=1, even
     when the test's own env tries to unset it.

@interacts  runs one child per row of LOADERS (sys.executable -c ...),
            outside the harness on purpose: a harness child gets
            PYTHONDONTWRITEBYTECODE=1, which would hide a loader that
            writes. Each child gets the root's env (its TC_ROOT, the
            refusing stubs on PATH) with that variable removed and
            PYTHONPYCACHEPREFIX set. subprocess.run waits for it, and kills
            it at CHILD_CEILING_SECONDS. Copies tc into the root's temp
            folder and loads the copy in this process with TC_ROOT set to
            the root and put back; plants one .pyc beside a copy with
            py_compile. Reads tests/test_*.py as text. Never touches the
            checkout's own __pycache__.
@deps       python3 stdlib (importlib.util, os, pathlib, py_compile, re,
            subprocess, sys, unittest, unittest.mock); tests/_root.py;
            ../tc; board/serve.py; the test modules LOADERS names.
@complexity Test 1: L = len(LOADERS) + 2 = 14 children, each one test
            module's import plus one load (well under a second each), then
            one walk of the cache folder, O(c) over c cached files (a few
            hundred stdlib and test modules). Test 2: O(b) over b bytes of
            tests/test_*.py (about 1 MB). Tests 3 and 4: O(s) over s bytes
            of tc, compiled twice each. Test 5: two children.
@alloc      one TcRoot per test, removed on exit, with the cache folder,
            the scratch copies and the planted cache in it.
"""

import importlib.util
import os
import pathlib
import py_compile
import re
import subprocess
import sys
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
# Run as `python3 -m unittest tests.test_no_bytecode` from the repo root,
# tests/ is not on sys.path; under discover it is. Add it once so both work.
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import _root  # noqa: E402  (needs the path line above)

SERVE_PATH = HERE.parent / "board" / "serve.py"
# A child imports one test module and loads once; that is well under a
# second. One that runs this long is hung.
CHILD_CEILING_SECONDS = 30
# The variables test 1 sets and removes for its children, and test 5 reads.
NO_BYTECODE_KEY = "PYTHONDONTWRITEBYTECODE"
CACHE_PREFIX_KEY = "PYTHONPYCACHEPREFIX"
# How a row of LOADERS reaches its loader in the child. IMPORT: the module
# loads serve.py when imported. ROOT: load_tc(root) under a TcRoot made in
# the child. TTL: test_keepalive's load_tc(ttl). HELPER: the row's text is
# the source path _root.load_source loads.
IMPORT, ROOT, TTL, HELPER = "import", "root", "ttl", "helper"
# The TTL test 1 hands test_keepalive's load_tc: any whole number does.
KEEPALIVE_TTL = 3600
# Every loader the suites define, by module, and how to reach it. Test 2
# checks this table against the files, so a new loader cannot be missed.
LOADERS = (
    ("test_board_feed", IMPORT),
    ("test_board_leak", IMPORT),
    ("test_board_server", IMPORT),
    ("test_inbox_pinned", IMPORT),
    ("test_wait_exit", IMPORT),
    ("test_cards", ROOT),
    ("test_codex_route", ROOT),
    ("test_mailbox", ROOT),
    ("test_names", ROOT),
    ("test_router", ROOT),
    ("test_shared", ROOT),
    ("test_keepalive", TTL),
)
# The helper itself, on each of the two sources the suites load.
HELPER_ROWS = ((str(_root.TC), HELPER), (str(SERVE_PATH), HELPER))
# A test module defines a loader under one of these names.
LOADER_DEF = re.compile(r"^def (load_tc|load_serve)\(", re.MULTILINE)
# Words that build a loader by hand. Only _root.py may hold them.
LOADER_WORDS = re.compile(r"SourceFileLoader|spec_from_file_location|exec_module")
# The one line tests 3 and 4 edit in the scratch copy, and its two values.
# Both have the same number of digits, so both edits leave the same size.
EDITED_LINE = re.compile(r"^DEFAULT_WAIT_SECONDS = \d+$", re.MULTILINE)
FIRST_VALUE = 1111
SECOND_VALUE = 2222
# What a harness child prints when it sees bytecode writing off.
NO_BYTECODE_SEEN = "1 True"
PROBE = f"import os, sys; print(os.environ.get({NO_BYTECODE_KEY!r}), sys.dont_write_bytecode)"

CHILD_HEAD = "import sys\nsys.path.insert(0, {tests!r})\nimport _root\n"
CHILD_CALL = {
    IMPORT: "import {target}\n",
    ROOT: "import {target}\nwith _root.TcRoot() as root:\n    {target}.load_tc(root)\n",
    TTL: "import {target}\n{target}.load_tc({ttl})\n",
    HELPER: "_root.load_source('no_bytecode_check', {target!r})\n",
}


def cached_sources(prefix):
    """Every .pyc under `prefix` that caches tc or board/serve.py, sorted.

    A cache's name is its source's name plus the interpreter's tag, so the
    two names to look for come from importlib.util.cache_from_source.

    @interacts  walks `prefix`. Writes nothing.
    @deps       importlib.util, pathlib; _root.TC, SERVE_PATH.
    @complexity O(c) over c files under `prefix` (a few hundred).
    @alloc      one list of strings, returned.
    """
    names = {pathlib.Path(importlib.util.cache_from_source(str(src))).name for src in (_root.TC, SERVE_PATH)}
    return sorted(str(p.relative_to(prefix)) for p in prefix.rglob("*.pyc") if p.name in names)


def load_scratch(root, path, name):
    """Load the scratch copy of tc at `path` through _root.load_source, with TC_ROOT set to the root.

    tc reads TC_ROOT once, at import, so it is set before the load and the
    old value is put back after, as every tc loader in the suites does.

    @interacts  sets and restores os.environ["TC_ROOT"]; runs the copy's
                top level (constants only, no disk writes); writes no
                bytecode (_root.load_source).
    @deps       os; _root.load_source.
    @complexity O(s) over s bytes of the copy: one compile.
    @alloc      one module object, returned.
    """
    old = os.environ.get("TC_ROOT")
    os.environ["TC_ROOT"] = str(root.path)
    try:
        return _root.load_source(name, path)
    finally:
        if old is None:
            os.environ.pop("TC_ROOT", None)
        else:
            os.environ["TC_ROOT"] = old


def edited(text, value):
    """tc's source `text` with its DEFAULT_WAIT_SECONDS line set to `value`.

    @interacts  none.
    @deps       EDITED_LINE.
    @complexity O(s) over s characters of `text`.
    @alloc      one string, returned.
    """
    return EDITED_LINE.sub(f"DEFAULT_WAIT_SECONDS = {value}", text, count=1)


class NoBytecodeTest(unittest.TestCase):
    """No loader in the suites writes or trusts a bytecode cache of tc or serve.py.

    @interacts  see the module block.
    @deps       _root.TcRoot, _root.load_source.
    @complexity see the module block.
    @alloc      one TcRoot per test.
    """

    def test_no_loader_writes_a_cache_of_tc_or_serve(self):
        """Each loader, and the helper on each source, leaves no .pyc of tc or serve.py under the cache prefix.

        @interacts  one child per row; see the module block.
        @deps       subprocess; cached_sources, CHILD_HEAD, CHILD_CALL.
        @complexity 14 children, then one walk of the cache folder each.
        @alloc      one TcRoot, removed on exit.
        """
        with _root.TcRoot() as root:
            for target, how in (*LOADERS, *HELPER_ROWS):
                prefix = root.base / f"cache-{pathlib.Path(target).name}"
                env = dict(root.env)
                env.pop(NO_BYTECODE_KEY, None)
                env[CACHE_PREFIX_KEY] = str(prefix)
                script = CHILD_HEAD.format(tests=str(HERE)) + CHILD_CALL[how].format(target=target, ttl=KEEPALIVE_TTL)
                done = subprocess.run([sys.executable, "-c", script], env=env, stdin=subprocess.DEVNULL,
                                      capture_output=True, text=True, timeout=CHILD_CEILING_SECONDS)
                with self.subTest(loader=target, check="ran"):
                    self.assertEqual(done.returncode, 0, done.stderr)
                with self.subTest(loader=target, check="cache"):
                    self.assertEqual(cached_sources(prefix), [], f"{target} wrote a bytecode cache")

    def test_the_table_names_every_loader_and_no_file_builds_its_own(self):
        """LOADERS matches the load_tc and load_serve defined in tests/test_*.py, and only _root.py builds a loader.

        @interacts  reads tests/test_*.py and tests/_root.py as text.
        @deps       LOADER_DEF, LOADER_WORDS, LOADERS.
        @complexity O(b) over b bytes of the test files.
        @alloc      the files' text, one at a time; two sets.
        """
        defined = {p.stem for p in sorted(HERE.glob("test_*.py")) if LOADER_DEF.search(p.read_text(encoding="utf-8"))}
        with self.subTest(check="table"):
            self.assertEqual(defined, {target for target, _ in LOADERS})
        own = pathlib.Path(__file__).resolve()
        builders = sorted(p.name for p in HERE.glob("test_*.py")
                          if p.resolve() != own and LOADER_WORDS.search(p.read_text(encoding="utf-8")))
        with self.subTest(check="builders"):
            self.assertEqual(builders, [], "a test file builds a loader instead of calling _root.load_source")
        with self.subTest(check="helper"):
            self.assertIsNotNone(LOADER_WORDS.search((HERE / "_root.py").read_text(encoding="utf-8")))

    def test_two_same_size_edits_in_one_second_run_the_second(self):
        """A scratch copy of tc, edited twice at one size and one mtime, runs each edit when loaded.

        Bytecode writing is turned on for the test (sys.dont_write_bytecode
        False), as a plain run has it, so a loader that caches does so here
        whatever the shell exports. The second edit's mtime is set to the
        first's, to the nanosecond, so "within one second" is certain
        rather than a race.

        @interacts  writes two versions of tc's copy in the root's temp
                    folder; loads each (load_scratch).
        @deps       os, unittest.mock; edited, load_scratch.
        @complexity O(s) over s bytes of tc, compiled twice.
        @alloc      one TcRoot, removed on exit.
        """
        text = _root.TC.read_text(encoding="utf-8")
        first, second = edited(text, FIRST_VALUE), edited(text, SECOND_VALUE)
        with _root.TcRoot() as root, mock.patch.object(sys, "dont_write_bytecode", False):
            scratch = root.base / "scratch" / "tc"
            scratch.parent.mkdir()
            scratch.write_text(first, encoding="utf-8")
            stamp = scratch.stat().st_mtime_ns
            seen_first = load_scratch(root, scratch, "tc_scratch_first").DEFAULT_WAIT_SECONDS
            scratch.write_text(second, encoding="utf-8")
            os.utime(scratch, ns=(stamp, stamp))
            seen_second = load_scratch(root, scratch, "tc_scratch_second").DEFAULT_WAIT_SECONDS
            cache = (scratch.parent / "__pycache__").exists()
        with self.subTest(check="edits differ at one size"):
            self.assertEqual((first != second, len(first.encode())), (True, len(second.encode())))
        with self.subTest(check="first edit ran"):
            self.assertEqual(seen_first, FIRST_VALUE)
        with self.subTest(check="second edit ran"):
            self.assertEqual(seen_second, SECOND_VALUE, "the second load ran the first edit's cached code")
        with self.subTest(check="no cache written"):
            self.assertFalse(cache, "loading the copy wrote a __pycache__ beside it")

    def test_a_planted_cache_of_the_first_edit_is_never_run(self):
        """A cache of the first edit, planted beside the copy with a matching header, does not run in place of the second.

        py_compile writes the cache as an import would: its header holds the
        first edit's mtime and size, which the second edit keeps. So this
        holds even where bytecode writing is off: a loader that only stops
        writing a cache still trusts one it finds.

        @interacts  writes two versions of tc's copy and one .pyc beside it
                    in the root's temp folder; loads the copy once.
        @deps       importlib.util, os, py_compile; edited, load_scratch.
        @complexity O(s) over s bytes of tc, compiled twice.
        @alloc      one TcRoot, removed on exit.
        """
        text = _root.TC.read_text(encoding="utf-8")
        with _root.TcRoot() as root:
            scratch = root.base / "scratch" / "tc"
            scratch.parent.mkdir()
            scratch.write_text(edited(text, FIRST_VALUE), encoding="utf-8")
            stamp = scratch.stat().st_mtime_ns
            cache = py_compile.compile(str(scratch), cfile=importlib.util.cache_from_source(str(scratch)),
                                       doraise=True, invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP)
            scratch.write_text(edited(text, SECOND_VALUE), encoding="utf-8")
            os.utime(scratch, ns=(stamp, stamp))
            planted = pathlib.Path(cache).is_file()
            seen = load_scratch(root, scratch, "tc_scratch_planted").DEFAULT_WAIT_SECONDS
        with self.subTest(check="cache planted"):
            self.assertTrue(planted)
        with self.subTest(check="second edit ran"):
            self.assertEqual(seen, SECOND_VALUE, "the load ran the planted cache of the first edit")

    def test_every_harness_child_runs_with_bytecode_writing_off(self):
        """A start() child sees PYTHONDONTWRITEBYTECODE=1, also when its env tries to unset it.

        @interacts  two start() children, each printing what it sees.
        @deps       _root.TcRoot.start; PROBE.
        @complexity two children.
        @alloc      one TcRoot, removed on exit.
        """
        with _root.TcRoot() as root:
            for label, env in (("default", None), ("unset by the test", {NO_BYTECODE_KEY: None})):
                out, err = root.start(argv=[sys.executable, "-c", PROBE], env=env).communicate(
                    timeout=CHILD_CEILING_SECONDS)
                with self.subTest(env=label):
                    self.assertEqual(out.strip(), NO_BYTECODE_SEEN, err)


if __name__ == "__main__":
    unittest.main()
