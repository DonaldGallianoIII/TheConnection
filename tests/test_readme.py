"""
The README's shown commands print what the README shows, and its exit
table is contracts.md's (R39; phases.md D1's Verify).

Model:  Claude Opus 5.5 (the R39 lane agent), 2026-10-17
Status: unreviewed

The README is the plan's exit test's only input: a stranger gets two
sessions talking from it alone. So every fenced block in it is accounted
for here, by its first non-empty line (its key):

- A block with a `$ ` line (a command block) is either run by one of the
  chains below (RUN names which) or listed in LISTED with the reason no
  test can run it. A command block in neither fails
  test_every_block_is_run_or_listed, so a new block is never skipped in
  silence.
- A block with no `$ ` line (a prompt, a config line, a sample) is listed
  in NO_PROMPT with what it is. A new one fails the same test.
- A key in RUN, LISTED or NO_PROMPT that no README block has fails too.

A chain runs its blocks' commands in order, in one throwaway root, as a
reader would: blocks that build on each other share the root. Each
command is its own subTest. A step the README's prose says happened but
shows no `$` line for (the relay prompt's `tc join a`, JOIN.md's status
post, far-c's card) is a setup step, named in the chain with where the
README or JOIN.md says it. Each chain ends by asserting it ran exactly
the commands of the blocks RUN gives it.

How a command runs:

- `tc ...`, `~/TheConnection/tc ...` and `tconn ...` run a copy of this
  checkout's tc placed in the throwaway root, with TC_ROOT unset, as the
  README's reader runs it: the mailbox is then the folder tc is in, the
  throwaway root, never a live one (Story.env asserts it). `tconn` runs a
  link of that name to the copy, so the hints say `tconn`. A command
  whose comment says `in the background` is started in the background
  (the harness's start(), TC_ROOT set to the same folder), proven by
  /proc/locks naming its pid on the name's lock, and shows no output.
- What a command printed is its stdout lines, then its stderr lines: the
  order a terminal shows when stdout is written first. Its exit code is
  0 unless the README says otherwise for that command (the outbox
  block's "Both exit 4").
- The ssh blocks run against the harness's fake `ssh` behind a loopback
  wrapper that hands the remote command to a real `tc gate --as
  homebox-a` under a second throwaway root, as sshd's forced command
  would (or stops at the fake's exit 255 with ssh's connection words).
  The codex block runs against the harness's fake `codex`. Every fake is
  asserted called, and its argv is checked against the words the README
  says tc runs. Real ssh and codex never run (rule 5).
- `tc health` finds a fake `nvidia-smi` first on PATH that prints the
  README's GPU sample (FAKE_GPU_OUTPUT), so the GPU words are strict on
  any machine.
- The board block runs `python3 board/serve.py --port 0`: the README's
  next line allows `--port`, and port 0 cannot collide with a live board
  on 8780. The port its line prints must answer live.html with 200.

The mapping rule, from the README's text to a match (expected_pattern).
Everything not named here is literal: a changed word, digit or space
fails.

1. A line that is exactly `...` matches one or more whole lines.
2. `...` inside a line matches one or more characters of that line (a
   varying path, time or number).
3. `/home/you/TheConnection` matches the folder tc is in: the throwaway
   root that holds the copy.
4. `<you>` matches this Linux login, as tc names an outbox branch.
5. `<t>` matches a board token: serve.py's secrets.token_urlsafe(24),
   32 characters of letters, digits, `-` and `_`.
6. `<name> (pid N)` matches the pid of the listener this chain started
   for that name, exactly. A name with no listener fails.
7. `Ns ago` matches any whole number of seconds: an age the clock picks.
8. The machine line's `load X / Y cores · mem free Z%` matches any
   numbers in those three places, and `N Claude Code · M Codex` any two
   counts: they are this machine's, not tc's.
9. `127.0.0.1:8780/` matches `127.0.0.1:<any port>/` (the board block's
   --port 0, above), and that port is then asked for live.html.

The exit table test (item 2) parses the README's "Exit codes" table and
contracts.md's: the same codes, 0 to 11, in order, each meaning holding
the key words EXIT_KEY_WORDS gives it in both, and each code the value
of an EXIT_ constant in tc, 0 included (tc's EXIT_OK; pause R39-1,
settled by a2 for the owner, 2026-10-17).

@interacts  reads README.md, contracts.md and tc. Copies tc into each
            throwaway root and runs it there with TC_ROOT unset (its
            mailbox is that root); runs ../tc through tests/_root.py
            under a TC_ROOT of its own for background waits and the far
            side's gate; starts board/serve.py on 127.0.0.1, port 0, and
            asks it for live.html. Writes a fake nvidia-smi, a loopback
            ssh wrapper and the harness's fakes inside the root's temp
            folder. Reads /proc/locks to prove a listener. Every child
            is killed by its own pid in the harness's teardown. Loads tc
            as a module (load_source) with TC_ROOT set to a throwaway
            root for the load and put back after.
@deps       python3 stdlib (http.client, os, pathlib, pwd, re, select,
            shlex, shutil, subprocess, sys, unittest); tests/_root.py
            (TcRoot, fake_bin, start, flock_holders, load_source, TC,
            WAIT_LOCK_NAME, LOCK_CEILING_SECONDS, LOCK_POLL_SECONDS,
            DEFAULT_TC_TIMEOUT_SECONDS); ../tc; board/serve.py; /bin/sh
            for the wrappers.
@complexity Parsing: O(L) over L README lines (under a thousand), once
            per test. Matching one command: one regex over its output,
            O(o * e) at worst over o output bytes and e expected lines
            (a dozen each). A chain runs c commands (10 in the quick
            start chain, 4 in the ssh chain, 1 for the board) plus at
            most 5 setup steps, each one child; the quick start chain
            waits one tc wait poll (5 s) for a wake.
@alloc      one TcRoot per chain (two for the ssh chain), each removed
            with everything in it on exit; the parsed blocks and each
            command's captured output, freed when the test returns.
"""

import http.client
import os
import pathlib
import pwd
import re
import select
import shlex
import shutil
import subprocess
import sys
import time
import unittest

HERE = pathlib.Path(__file__).resolve().parent
# Run as `python3 -m unittest tests.test_readme` from the repo root,
# tests/ is not on sys.path; under discover it is. Add it once so both work.
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import _root  # noqa: E402  (needs the path line above)

REPO = HERE.parent
README = REPO / "README.md"
CONTRACTS = REPO / "docs" / "planning" / "connection-routes" / "contracts.md"
BOARD_SERVER = REPO / "board" / "serve.py"

# A fence line: three backticks, indented as far as the list item it sits in.
FENCE = re.compile(r"^( *)```")
# What starts a shown command inside a block.
PROMPT = "$ "
# The words a shown tc command starts with, and the name each runs tc by:
# the README's bare `tc` and `~/TheConnection/tc` are the same link, and
# `tconn` is the name Install gives it where the system has a `tc`.
TC_HEADS = {"tc": "tc", "~/TheConnection/tc": "tc", "tconn": "tconn"}
# The comment that marks a shown command as started in the background.
BACKGROUND_WORDS = "in the background"
# The only command the README shows in the background.
BACKGROUND_COMMAND = "wait"

# The mapping rule's placeholders (the module block, items 1 to 9).
ELLIPSIS = "..."
# Rule 1: one or more whole lines, the first possibly empty.
MANY_LINES = r"[^\n]*(?:\n[^\n]*)*"
# Rule 2: one or more characters within a line.
IN_LINE = r"[^\n]+"
# Rule 5: secrets.token_urlsafe(24) in board/serve.py (TOKEN_BYTES): 24
# bytes in unpadded base64url are 32 characters.
BOARD_TOKEN = r"[A-Za-z0-9_-]{32}"
# One alternative per placeholder; the first that starts earliest wins.
PLACEHOLDER = re.compile(
    r"(?P<ellipsis>\.\.\.)"
    r"|(?P<checkout>/home/you/TheConnection)"
    r"|(?P<login><you>)"
    r"|(?P<token><t>)"
    r"|(?P<pid>(?P<pidname>[A-Za-z0-9._][A-Za-z0-9._-]*) \(pid \d+\))"
    r"|(?P<age>\b\d+s ago)"
    r"|(?P<load>load \d+(?:\.\d+)? / \d+ cores · mem free \d+(?:\.\d+)?%)"
    r"|(?P<sessions>\b\d+ Claude Code · \d+ Codex)"
    r"|(?P<port>127\.0\.0\.1:8780/)")
# What each placeholder but ellipsis, checkout, login and pid becomes.
SAMPLE_PATTERNS = {
    "token": BOARD_TOKEN,
    "age": r"\d+s ago",
    "load": r"load \d+(?:\.\d+)? / \d+ cores · mem free \d+(?:\.\d+)?%",
    "sessions": r"\d+ Claude Code · \d+ Codex",
    "port": r"127\.0\.0\.1:\d+/",
}
# Reads the port back out of a board line that matched rule 9.
BOARD_PORT = re.compile(r"127\.0\.0\.1:(\d+)/")

# The chains (test methods of ReadmeBlocksTest), by the name RUN uses.
# RECORD (Claude Opus 5.5, unreviewed): the README shows `read ...`, which the
# mapping rule matches to any text after `read `; this pins a time with its offset.
READ_TIME_LINE = r"\Aread \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}\Z"
QUICK_START = "quick start, local, codex, cards and health"
SSH_OUTBOUND = "ssh outbound"
BOARD = "the live board"

# Every command block a chain runs, and which chain.
RUN = {
    "$ ~/TheConnection/tc health": QUICK_START,
    "$ tc join b --account work --reports-to a": QUICK_START,
    "$ tc read a": QUICK_START,
    "$ tc log": QUICK_START,  # RECORD (Claude Opus 5.5, unreviewed): the record-of-work section
    "$ tc health": QUICK_START,
    '$ tc send --from a --to newname "first mail"': QUICK_START,
    '$ tc send --from a --to cx "please review the parser"': QUICK_START,
    "$ tc cards": QUICK_START,
    "$ tc card far-b --ssh farbox-tc --remote-tc '~/TheConnection/tc'": SSH_OUTBOUND,
    '$ tc send --from homebox-a --to far-b "hello far"': SSH_OUTBOUND,
    '$ tc send --from homebox-a --to far-c "first"': SSH_OUTBOUND,
    "$ python3 board/serve.py": BOARD,
}

# Every command block no test can run, with the reason.
LISTED = {
    "$ tc init --shared --group tcshare":
        "needs the group tcshare, which step 1 makes with sudo, and a second "
        "Linux user to mean anything; tests/test_shared.py covers init with "
        "the running user's own groups",
}

# Every block with no `$ ` line, with what it is. None of these is run
# here, except that the quick start chain compares the codex join's
# printed line with its block (CODEX_JOIN_BLOCK).
NO_PROMPT = {
    "Is the other session on another machine?":
        "the which-route chart, plain text",
    "git clone https://github.com/DonaldGallianoIII/TheConnection ~/TheConnection":
        "Install: needs the network, and writes in the reader's home",
    "mkdir -p ~/.local/bin && ln -s ~/TheConnection/tc ~/.local/bin/tc":
        "Install: writes in the reader's home",
    "mkdir -p ~/.local/bin && ln -s ~/TheConnection/tc ~/.local/bin/tconn":
        "Install: writes in the reader's home",
    "read ~/TheConnection/JOIN.md and follow it. your name is b, your relay is a, your account is work.":
        "a prompt a person types into a Claude session",
    "You are the relay for session b over ~/TheConnection/tc. Run":
        "a prompt a person types into a Claude session",
    "codex --add-dir ~/TheConnection":
        "starts real codex (rule 5)",
    "read ~/TheConnection/JOIN-CODEX.md and follow it. your name is cx, your relay is a, your account is work.":
        "a prompt a person types into a Codex session",
    "joined as cx (codex, account work, route codex), reports to a":
        "the codex join's printed line, its command in the prose; the quick "
        "start chain runs that command and compares its output with this block",
    "ring failed for cx: <codex's first stderr line>; the mail is in its inbox; the next send to cx rings again":
        "a sample warning with no command; tests/test_codex_route.py covers a failed ring",
    "ssh-keygen -t ed25519 -f ~/.ssh/tc_ed25519 -N '' -C homebox-a":
        "makes a key in the reader's ~/.ssh",
    "Host farbox-tc":
        "an ssh config entry",
    "tc gate: onward is not a local name; the gate does not forward":
        "sample far refusal words with no command; tests/test_ssh_route.py "
        "and tests/test_gate.py cover a refusal",
    'command="TC_ROOT=/home/you/TheConnection /home/you/TheConnection/tc gate --as homebox-a",'
    "no-pty,no-port-forwarding,no-agent-forwarding,no-X11-forwarding ssh-ed25519 AAAA... homebox":
        "an authorized_keys line for a real sshd",
    "your mailbox is TC_ROOT=/srv/tc-shared. read ~/TheConnection/JOIN.md and follow it. your name is ben, "
    "your relay is ann.":
        "a prompt a person types into a Claude session",
    "ALERT ...: LISTENER DOWN: b":
        "a sample watch alert with no command; tests/test_wait_exit.py covers it",
    "tc wait b --keepalive    # listener that doubles as a keep-alive":
        "two commands with no `$` and no output: a listener and a watch that "
        "run for 55 minutes",
    "ssh -L 8780:127.0.0.1:8780 <host>":
        "real ssh to a real host (rule 5)",
    "tc                                    the whole tool (python3, stdlib only)":
        "the layout listing",
}

# The block whose text the codex join's output must equal.
CODEX_JOIN_BLOCK = "joined as cx (codex, account work, route codex), reports to a"
# A made-up Codex thread id, in THREAD_ID_PATTERN's shape.
CODEX_THREAD = "thread-demo-1"
# A Claude Code session's own marker, which tc join reads for kind claude
# (C1); the harness drops it from every child, and the README's a and b
# are Claude sessions.
CLAUDE_ENV = {"CLAUDECODE": "1"}
# What the README's quick start session b posts, per JOIN.md step 4.
STATUS_WORDS = "reading the parser"
# What a shown command exits with unless the README says otherwise.
EXIT_OK = 0
# The README's outbox block: "Both exit 4."
README_QUEUED_EXIT = 4
# ssh's own exit for a connection it could not make.
SSH_UNREACHABLE_EXIT = 255
# The connection words the README's outbox block shows ssh printing.
SSH_DOWN_STDERR = "ssh: connect to host farbox port 22: Connection refused\n"
# The far machine's name and the sending name its gate line gives the key.
FAR_TARGET = "farbox-tc"
FAR_KEY = "homebox-a"
FAR_NAME = "far-b"
# What the fake nvidia-smi prints: one GPU at the README's 39C and 3%, in
# the --format=csv,noheader,nounits form tc asks for.
FAKE_GPU_OUTPUT = "39, 3"
# A wrapper or a fake: its owner runs it, nobody else needs to.
OWN_EXE_MODE = 0o700
# The copy of tc in a root: read and run by its owner only.
COPY_MODE = 0o700
# tc wait polls every 5 s (the README's "every 5 s"): a wake after a send
# lands within one poll. Three polls of room for a loaded machine.
WAKE_CEILING_SECONDS = 15
# serve.py prints its line right after it binds; this is a ceiling only.
BOARD_LINE_CEILING_SECONDS = 10
# A request to loopback answers in milliseconds; this is a ceiling only.
HTTP_TIMEOUT_SECONDS = 5
HTTP_OK = 200
# Port 0: the OS picks a free one, so no live board's port is ever taken.
ANY_PORT = "0"

# Item 2: the words each code's meaning must carry, in the README's table
# and in contracts.md's, compared without case or backticks. Enough to
# tell each code from every other, never the full wording.
EXIT_KEY_WORDS = {
    0: ("ok", "wait", "mail", "watch", "heartbeat"),
    1: ("refused", "empty message"),
    2: ("wait", "timed out"),
    3: ("already holds this name's lock",),
    4: ("kept in the outbox", "could not reach the target", "already has a queue", "send lock"),
    5: ("alert", "load", "memory", "gpu", "listener down"),
    6: ("bad name", "ssh target", "remote path"),
    7: ("refused by the gate",),
    8: ("message over",),
    9: ("usage error", "unknown command", "missing argument"),
    10: ("busy", "another process held"),
    11: ("refused by the far side", "a code tc does not know"),
}
# The exit codes the contract fixes: 0 to 11.
EXIT_CODES = tuple(range(len(EXIT_KEY_WORDS)))
# Where each table starts, and the shape of one of its rows.
README_EXIT_HEADING = "## Exit codes"
CONTRACT_EXIT_LEAD = "**Exit codes.**"
EXIT_ROW = re.compile(r"^\| (\d+) \| (.+?) \|")


class Block:
    """One fenced README block: where it starts, its lines, and its commands.

    `lines` drops the fence's indent. `commands` is a list of (command,
    expected lines), one per `$ ` line, with the lines after it up to the
    next `$ ` line; a block with no `$ ` line has none.

    @interacts  none; string work only.
    @deps       PROMPT.
    @complexity O(n) over n lines in the block (a dozen at most).
    @alloc      the lists, held by the caller.
    """

    def __init__(self, start, lines):
        """Keep the block and split it into commands.

        Raises ValueError for a command block with text before its first
        `$ ` line, which no rule here could match to a command.

        @interacts  none.
        @deps       PROMPT.
        @complexity O(n) over n lines in the block.
        @alloc      two lists.
        """
        self.start = start
        self.lines = [line.rstrip() for line in lines]
        while self.lines and not self.lines[-1]:
            self.lines.pop()
        self.key = next((line for line in self.lines if line.strip()), "")
        self.commands = []
        if not any(line.startswith(PROMPT) for line in self.lines):
            return
        for line in self.lines:
            if line.startswith(PROMPT):
                self.commands.append((line[len(PROMPT):], []))
            elif not self.commands:
                raise ValueError(f"README.md:{start}: text before the block's first `$ ` line: {line!r}")
            else:
                self.commands[-1][1].append(line)


def readme_blocks(text):
    """Every fenced block in `text`, by key (its first non-empty line), in order.

    A fence may be indented, as inside a list item; the indent is taken
    off each line. Raises ValueError for two blocks with one key (the
    census could not tell them apart) or a fence left open.

    @interacts  none; string work only.
    @deps       Block, FENCE.
    @complexity O(L) over L lines of `text` (under a thousand).
    @alloc      one dict of Blocks, returned.
    """
    blocks, body, start, indent = {}, None, 0, 0
    for number, line in enumerate(text.split("\n"), 1):
        fence = FENCE.match(line)
        if fence and body is None:
            body, start, indent = [], number, len(fence.group(1))
        elif fence:
            block = Block(start, body)
            if block.key in blocks:
                raise ValueError(f"README.md:{start}: a second block starts {block.key!r}")
            blocks[block.key] = block
            body = None
        elif body is not None:
            body.append(line[indent:] if not line[:indent].strip() else line)
    if body is not None:
        raise ValueError(f"README.md:{start}: a fence is never closed")
    return blocks


def prose(pattern):
    """The first group of `pattern` in the README's text with every run of whitespace made one space.

    For a claim the README makes in a sentence, not a block (the MAIL
    line a wake prints, the words tc runs ssh and codex with). Raises
    AssertionError when the sentence is gone, so a reworded claim fails
    loudly instead of passing unchecked.

    @interacts  reads README.md.
    @deps       re.
    @complexity O(R) over R bytes of the README.
    @alloc      the README's text, freed on return; one string, returned.
    """
    found = re.search(pattern, " ".join(README.read_text(encoding="utf-8").split()))
    if found is None:
        raise AssertionError(f"README.md no longer says what this test checks: {pattern}")
    return found.group(1)


def expected_pattern(lines, story):
    """The regex that README output `lines` stand for, under the mapping rule (the module block).

    @interacts  none; string work only.
    @deps       PLACEHOLDER, SAMPLE_PATTERNS, MANY_LINES, IN_LINE; the
                story's checkout, login and pids.
    @complexity O(e * w) over e lines and w characters a line (a dozen
                lines of under 200).
    @alloc      one pattern string, returned.
    """
    pieces = []
    for line in lines:
        if line == ELLIPSIS:
            pieces.append(MANY_LINES)
            continue
        out, at = [], 0
        for hit in PLACEHOLDER.finditer(line):
            out.append(re.escape(line[at:hit.start()]))
            kind = hit.lastgroup if hit.lastgroup != "pidname" else "pid"
            if kind == "ellipsis":
                out.append(IN_LINE)
            elif kind == "checkout":
                out.append(re.escape(story.checkout))
            elif kind == "login":
                out.append(re.escape(story.login))
            elif kind == "pid":
                name = hit.group("pidname")
                if name not in story.pids:
                    raise AssertionError(f"the README shows a pid for {name!r}, and this chain started "
                                         f"no listener for it")
                out.append(re.escape(f"{name} (pid {story.pids[name]})"))
            else:
                out.append(SAMPLE_PATTERNS[kind])
            at = hit.end()
        out.append(re.escape(line[at:]))
        pieces.append("".join(out))
    return "\n".join(pieces)


def printed(out, err):
    """What a command printed, as the README shows it: its stdout lines, then its stderr lines.

    @interacts  none.
    @deps       none.
    @complexity O(o) over o bytes printed.
    @alloc      one string, returned.
    """
    return "\n".join(out.splitlines() + err.splitlines())


def loopback_ssh(root, fake, far):
    """A folder holding an `ssh` that runs the harness's fake at `fake`, then hands the remote command to a real `tc gate --as FAR_KEY` under the far root `far`.

    The wrapper keeps its stdin in a file, gives it to the fake (which
    records the call and exits with its code; a non-zero code ends the
    call there, as a failed connection does), then runs the gate with
    SSH_ORIGINAL_COMMAND set to its last argument and TC_ROOT set to the
    far root, as the README's authorized_keys line does. No real ssh
    runs (rule 5).

    @interacts  writes loopback-ssh-*/ssh (mode 0700) in the root's temp
                folder; each call keeps its stdin in a file beside it.
    @deps       shlex, os, sys; _root.TC; OWN_EXE_MODE.
    @complexity O(1).
    @alloc      one folder, removed with the temp folder; returned.
    """
    home = root.base / f"loopback-ssh-{len(list(root.base.glob('loopback-ssh-*')))}"
    home.mkdir()
    feed = shlex.quote(str(home / "stdin")) + ".$$"
    wrapper = home / "ssh"
    wrapper.write_text("#!/bin/sh\n"
                       "# A loopback ssh written by tests/test_readme.py: the fake, then a local tc gate.\n"
                       f"cat > {feed}\n"
                       f'{shlex.quote(str(fake / "ssh"))} "$@" < {feed} || exit $?\n'
                       "for last; do :; done\n"
                       f'SSH_ORIGINAL_COMMAND="$last" TC_ROOT={shlex.quote(str(far))} exec '
                       f"{shlex.quote(sys.executable)} {shlex.quote(str(_root.TC))} "
                       f"gate --as {shlex.quote(FAR_KEY)} < {feed}\n")
    wrapper.chmod(OWN_EXE_MODE)
    return home


def fake_gpu(root):
    """A folder holding an `nvidia-smi` that prints FAKE_GPU_OUTPUT, for tc health's GPU words.

    @interacts  writes fake-gpu/nvidia-smi (mode 0700) in the root's temp
                folder.
    @deps       shlex; FAKE_GPU_OUTPUT, OWN_EXE_MODE.
    @complexity O(1).
    @alloc      one folder, removed with the temp folder; returned.
    """
    home = root.base / "fake-gpu"
    home.mkdir()
    exe = home / "nvidia-smi"
    exe.write_text("#!/bin/sh\n"
                   "# A fake nvidia-smi written by tests/test_readme.py: one GPU, the README's sample.\n"
                   f"echo {shlex.quote(FAKE_GPU_OUTPUT)}\n")
    exe.chmod(OWN_EXE_MODE)
    return home


class Story:
    """One reader's run through the README: a throwaway root holding a copy of tc, and what the run has done so far.

    Attributes: `root` (the TcRoot), `copy` (tc, copied into the root),
    `checkout` (the folder tc is in, resolved: rule 3), `login` (rule 4),
    `pids` (name to the pid of the listener this story started: rule 6),
    `front` (folders put ahead of the harness's PATH: the fake GPU, a
    loopback ssh), `ran` (the (block key, command index) pairs run).

    @interacts  copies ../tc into the root's folder.
    @deps       shutil, pwd, os; _root.TC; COPY_MODE.
    @complexity O(s) over s bytes of tc, for the copy.
    @alloc      the copy, removed with the root; a dict, a list and a set.
    """

    def __init__(self, root):
        """Copy tc into `root`'s folder and start with nothing run.

        @interacts  writes <root.path>/tc (mode 0700).
        @deps       shutil, pwd, os; _root.TC; COPY_MODE, fake_gpu.
        @complexity O(s) over s bytes of tc.
        @alloc      the copy and the fields.
        """
        self.root = root
        self.copy = root.path / "tc"
        shutil.copyfile(_root.TC, self.copy)
        self.copy.chmod(COPY_MODE)
        self.checkout = str(self.copy.resolve().parent)
        self.login = pwd.getpwuid(os.geteuid()).pw_name
        self.pids = {}
        self.front = [fake_gpu(root)]
        self.ran = set()

    def exe(self, head):
        """The file to run for a command's first word: the copy, or a `tconn` link to it.

        @interacts  makes <root.path>/tconn, a link to the copy, the first
                    time `tconn` is asked for.
        @deps       TC_HEADS.
        @complexity O(1).
        @alloc      none.
        """
        name = TC_HEADS[head]
        link = self.root.path / name
        if name != self.copy.name and not link.is_symlink():
            link.symlink_to(self.copy.name)
        return link

    def env(self, extra=None):
        """The environment a shown command runs with: the harness's, TC_ROOT unset, `front` ahead on PATH, `extra` over it.

        Asserts first that the copy's own folder sits inside the root's
        temp folder, so with TC_ROOT unset the mailbox is a throwaway one
        and never a live one.

        @interacts  resolves the copy's path.
        @deps       os, pathlib.
        @complexity O(e) over e variables (tens).
        @alloc      one dict, returned.
        """
        base = pathlib.Path(os.path.realpath(self.root.base))
        if not pathlib.Path(self.checkout).is_relative_to(base):
            raise AssertionError(f"the copy's folder {self.checkout} is outside the test's temp folder")
        env = dict(self.root.env)
        env.pop("TC_ROOT", None)
        env.update(extra or {})
        for folder in self.front:
            if not pathlib.Path(os.path.realpath(folder)).is_relative_to(base):
                raise AssertionError(f"{folder} is outside the test's temp folder")
        env["PATH"] = os.pathsep.join([str(f) for f in self.front] + [self.root.env["PATH"]])
        return env

    def run(self, words, env=None):
        """Run one tc command, `words` from its first word on, in the foreground. Return (exit, stdout, stderr).

        @interacts  runs the copy (or its tconn link) as a child, stdin
                    /dev/null, and waits.
        @deps       subprocess, sys; exe, env; _root.DEFAULT_TC_TIMEOUT_SECONDS.
        @complexity the child's own work.
        @alloc      the captured output, returned.
        """
        done = subprocess.run([sys.executable, str(self.exe(words[0])), *words[1:]], env=self.env(env),
                              stdin=subprocess.DEVNULL, capture_output=True, text=True,
                              timeout=_root.DEFAULT_TC_TIMEOUT_SECONDS)
        return done.returncode, done.stdout, done.stderr

    def listen(self, words, env=None):
        """Start `tc wait <name>` in the background and prove it: /proc/locks names its pid on the name's lock. Return the Popen.

        Started through the harness's start(), so teardown kills it by
        its own pid; TC_ROOT is set there to the root's folder, the same
        mailbox the copy reads with TC_ROOT unset.

        @interacts  starts one child; stats the lock and reads /proc/locks
                    up to LOCK_CEILING_SECONDS / LOCK_POLL_SECONDS = 100
                    times.
        @deps       _root.flock_holders, time; exe.
        @complexity at most 100 reads of /proc/locks, each O(k) over k
                    lines (tens).
        @alloc      one Popen, held by the root until teardown.
        """
        if len(words) < 3 or words[1] != BACKGROUND_COMMAND:
            raise AssertionError(f"only `tc {BACKGROUND_COMMAND} <name>` runs in the background here: {words}")
        name = words[2]
        proc = self.root.start(argv=[sys.executable, str(self.exe(words[0])), *words[1:]], env=env)
        lock = self.root.path / "mail" / f"to-{name}" / _root.WAIT_LOCK_NAME
        deadline = time.monotonic() + _root.LOCK_CEILING_SECONDS
        while proc.pid not in _root.flock_holders(lock):
            if proc.poll() is not None or time.monotonic() >= deadline:
                out, err = proc.communicate()
                raise AssertionError(f"tc wait {name} (pid {proc.pid}) never held {lock}: "
                                     f"exit {proc.returncode}, {out!r} {err!r}")
            time.sleep(_root.LOCK_POLL_SECONDS)
        self.pids[name] = proc.pid
        return proc


class ReadmeCensusTest(unittest.TestCase):
    """Every README block is run, listed, or named as having no command; nothing listed is gone.

    @interacts  reads README.md.
    @deps       readme_blocks; RUN, LISTED, NO_PROMPT.
    @complexity O(L) over L README lines.
    @alloc      the parsed blocks, freed on return.
    """

    def test_every_block_is_run_or_listed(self):
        """Each command block is in RUN or LISTED (not both), each other block in NO_PROMPT, and every key names a block that is there.

        Must reject a new command block nobody runs or lists, a block
        dropped from LISTED without a chain that runs it, a listed block
        the README no longer has, and a block with no command filed as run.

        @interacts  reads README.md.
        @deps       readme_blocks.
        @complexity O(L) over L README lines, plus O(b) over b blocks (31).
        @alloc      the parsed blocks and a few sets.
        """
        blocks = readme_blocks(README.read_text(encoding="utf-8"))
        for key, block in blocks.items():
            with self.subTest(block=f"README.md:{block.start}: {key}"):
                if block.commands:
                    self.assertTrue((key in RUN) != (key in LISTED),
                                    "a command block must be run by a chain (RUN) or listed with a "
                                    "reason (LISTED), and not both")
                else:
                    self.assertIn(key, NO_PROMPT, "a block with no `$ ` line must be in NO_PROMPT, "
                                                  "saying what it is")
        for table, name in ((RUN, "RUN"), (LISTED, "LISTED"), (NO_PROMPT, "NO_PROMPT")):
            for key in table:
                with self.subTest(table=name, key=key):
                    self.assertIn(key, blocks, f"{name} names a block the README no longer has")
                    if name != "NO_PROMPT":
                        self.assertTrue(blocks[key].commands, f"{name} names a block with no `$ ` line")


class ReadmeBlocksTest(unittest.TestCase):
    """Each chain runs its README blocks in one throwaway root and compares every command's output with the README's.

    @interacts  see the module block.
    @deps       Story, readme_blocks, expected_pattern, printed, prose,
                loopback_ssh; _root.TcRoot.
    @complexity per chain, as the module block says.
    @alloc      per chain, one or two TcRoots, removed on exit.
    """

    def shown(self, story, key, first=0, last=None, env=None, exits=None):
        """Run commands `first` up to `last` of block `key` in order, each in its own subTest, and compare each with the README.

        A command whose comment says `in the background` is started and
        proven (Story.listen) and must show no output. Any other runs in
        the foreground; its exit must be `exits[i]` (EXIT_OK when not
        given) and what it printed must match the lines after it under
        the mapping rule. Each command run is added to story.ran.

        @interacts  runs one tc child per command (Story.run, Story.listen).
        @deps       readme_blocks, expected_pattern, printed; shlex.
        @complexity O(L) to parse, plus one child per command (at most 3).
        @alloc      the parsed blocks and each command's output.
        """
        block = readme_blocks(README.read_text(encoding="utf-8"))[key]
        stop = len(block.commands) if last is None else last
        for index in range(first, stop):
            command, lines = block.commands[index]
            story.ran.add((key, index))
            with self.subTest(block=f"README.md:{block.start}", command=command):
                words = shlex.split(command, comments=True)
                self.assertIn(words[0], TC_HEADS, f"not a tc command: {command}")
                if BACKGROUND_WORDS in command.partition("#")[2]:
                    self.assertEqual(lines, [], "the README shows output for a background command")
                    story.listen(words, env)
                    continue
                code, out, err = story.run(words, env)
                want = (exits or {}).get(index, EXIT_OK)
                self.assertEqual(code, want, f"exit {code}, the README's is {want}.\n{printed(out, err)}")
                shows = "\n".join(lines)
                self.assertIsNotNone(re.fullmatch(expected_pattern(lines, story), printed(out, err)),
                                     f"\nthe README shows:\n{shows}\n\ntc printed:\n{printed(out, err)}")

    def setup_step(self, story, words, env=None):
        """Run a step the README's prose says happened and shows no `$` line for; it must exit 0.

        @interacts  runs one tc child (Story.run).
        @deps       Story.run.
        @complexity the child's own work.
        @alloc      the captured output, returned.
        """
        code, out, err = story.run(words, env)
        self.assertEqual(code, EXIT_OK, f"setup step {shlex.join(words)}: exit {code}\n{printed(out, err)}")
        return out, err

    def assert_ran_all(self, story, chain):
        """The chain ran every command of every block RUN gives it, and nothing else.

        @interacts  reads README.md.
        @deps       readme_blocks; RUN.
        @complexity O(L) over L README lines.
        @alloc      two sets.
        """
        blocks = readme_blocks(README.read_text(encoding="utf-8"))
        owed = {(key, index) for key, owner in RUN.items() if owner == chain and key in blocks
                for index in range(len(blocks[key].commands))}
        self.assertEqual(story.ran, owed, f"the {chain} chain ran other commands than RUN gives it")

    def test_quick_start_then_local_codex_cards_and_health(self):
        """The quick start as its two sessions run it, then health, the local route's new inbox, a Codex join and ring, and the cards list, in one mailbox.

        Order: the relay prompt's `tc join a` and `tc wait a` (setup);
        b's join and background wait; the quick start's health (both
        pids); b's send, which wakes a's wait with the MAIL line the
        README quotes; a's read; the log, its read line a real time
        (RECORD); JOIN.md step 4's status post (setup);
        the health section's block; the new-inbox send; the Codex join
        (its command from the prose, its output equal to its block) and
        the send that rings it; far-b's card as ssh step 6 writes it
        (setup); `tc cards`.

        Must reject output that differs from the README in a word, a
        message number the reader would not see, a pid that is not the
        listener's, a wake that prints other words, and a ring whose
        argv differs from the words the README says it carries.

        @interacts  one TcRoot; tc children; two background waits; the
                    harness's fake codex, asserted called once.
        @deps       Story, shown, setup_step, assert_ran_all, prose,
                    expected_pattern; _root.TcRoot.
        @complexity 16 tc children, and one wait for a wake (one 5 s
                    poll).
        @alloc      one TcRoot, removed on exit.
        """
        quick_health = "$ ~/TheConnection/tc health"
        sessions = "$ tc join b --account work --reports-to a"
        with _root.TcRoot() as root:
            story = Story(root)
            self.setup_step(story, ["tc", "join", "a"], CLAUDE_ENV)  # the relay prompt: tc join a
            relay = story.listen(["tc", "wait", "a"])  # the relay prompt: tc wait a, in the background
            self.shown(story, sessions, 0, 2, env=CLAUDE_ENV)  # b joins and arms its wait
            self.shown(story, quick_health)  # quick start step 3: both listening
            self.shown(story, sessions, 2)  # b's hello wakes a
            with self.subTest(claim="a's wait prints the MAIL line and exits 0"):
                out, err = relay.communicate(timeout=WAKE_CEILING_SECONDS)
                self.assertEqual((relay.returncode, printed(out, err)),
                                 (EXIT_OK, prose(r"a's wait prints `([^`]+)` and exits 0")))
            self.shown(story, "$ tc read a")
            self.shown(story, "$ tc log")  # RECORD (Claude Opus 5.5, unreviewed): a's read is recorded
            with self.subTest(claim="tc log's read line is the read time, with its offset"):
                code, out, err = story.run(["tc", "log"])
                self.assertEqual(code, EXIT_OK, printed(out, err))
                self.assertRegex(out.splitlines()[1], READ_TIME_LINE)
            self.setup_step(story, ["tc", "status", "b", STATUS_WORDS])  # JOIN.md step 4: post status
            self.shown(story, "$ tc health")
            self.shown(story, '$ tc send --from a --to newname "first mail"')
            with self.subTest(claim="the Codex join prints its block"):
                out, err = self.setup_step(story, shlex.split(prose(r"It runs `(tc join cx [^`]+)`")),
                                           {"CODEX_THREAD_ID": CODEX_THREAD})
                block = readme_blocks(README.read_text(encoding="utf-8"))[CODEX_JOIN_BLOCK]
                self.assertEqual(printed(out, err), "\n".join(block.lines))
            folder, calls = root.fake_bin("codex", EXIT_OK)
            self.shown(story, '$ tc send --from a --to cx "please review the parser"')
            with self.subTest(claim="the ring is the codex queue the README names"):
                self.assertTrue((folder.parent / "calls.jsonl").exists(), "the fake codex never ran")
                rang = calls()
                self.assertEqual(len(rang), 1, rang)
                words = prose(r'The ring is `codex (queue --thread <its thread> --message) "')
                argv = shlex.split(words.replace("<its thread>", CODEX_THREAD))
                self.assertEqual(rang[0]["argv"][:len(argv)], argv)
                message = prose(r'--message "([^"]+)"`')
                self.assertEqual(len(rang[0]["argv"]), len(argv) + 1, rang[0]["argv"])
                self.assertIsNotNone(re.fullmatch(expected_pattern([message], story), rang[0]["argv"][-1]),
                                     f"README: {message}\nring:   {rang[0]['argv'][-1]}")
            # ssh step 6's card, as the cards block shows it.
            self.setup_step(story, ["tc", "card", FAR_NAME, "--ssh", FAR_TARGET, "--remote-tc", "~/TheConnection/tc"])
            self.shown(story, "$ tc cards")
            self.assert_ran_all(story, QUICK_START)

    def test_ssh_outbound_card_send_and_outbox(self):
        """ssh outbound on homebox: far-b's card, a send through the far gate, then two sends to far-c with farbox down, kept in the outbox.

        The far machine is a second root whose far-b joined (step 1,
        setup). The send goes through the loopback ssh to a real gate and
        lands as from homebox-a with the gate's note. far-c's card is a
        setup step (the README shows none). With ssh failing, the first
        send runs ssh once and keeps the mail; the second runs none and
        queues behind it; both exit 4.

        Must reject an ssh argv other than the README's, a far header
        that is not labeled by the key, outbox numbers or words other
        than the README's, and a second send that runs ssh.

        @interacts  two TcRoots; tc children; the harness's fake ssh,
                    twice, each asserted called; a real tc gate under the
                    far root.
        @deps       Story, shown, setup_step, assert_ran_all, prose,
                    loopback_ssh; _root.TcRoot.
        @complexity 7 tc children and 1 gate run (the far-c sends never
                    reach the gate).
        @alloc      two TcRoots, removed on exit.
        """
        card = "$ tc card far-b --ssh farbox-tc --remote-tc '~/TheConnection/tc'"
        with _root.TcRoot() as home, _root.TcRoot() as far:
            story = Story(home)
            code, out, err = far.tc("join", FAR_NAME)  # step 1, on farbox
            self.assertEqual(code, EXIT_OK, printed(out, err))
            self.shown(story, card)
            up, up_calls = home.fake_bin("ssh", EXIT_OK)
            story.front.append(loopback_ssh(home, up, far.path))
            self.shown(story, '$ tc send --from homebox-a --to far-b "hello far"')
            with self.subTest(claim="tc runs the ssh the README names, and farbox labels the mail by the key"):
                self.assertTrue((up.parent / "calls.jsonl").exists(), "the fake ssh never ran")
                calls = up_calls()
                self.assertEqual(len(calls), 1, calls)
                argv = shlex.split(prose(r"tc runs plain `ssh ([^`]+)`").replace("<target>", FAR_TARGET))
                self.assertEqual(calls[0]["argv"][:len(argv)], argv)
                code, out, err = far.tc("read", FAR_NAME)
                self.assertEqual(code, EXIT_OK, printed(out, err))
                header = out.splitlines()[0]
                for words in (prose(r"shows it `([^`]+)`, with `"), prose(r"with `([^`]+)` on its header line")):
                    self.assertIn(words, header)
            self.setup_step(story, ["tc", "card", "far-c", "--ssh", FAR_TARGET, "--remote-tc", "~/TheConnection/tc"])
            story.front.pop()
            down, down_calls = home.fake_bin("ssh", SSH_UNREACHABLE_EXIT, stderr=SSH_DOWN_STDERR)
            story.front.append(loopback_ssh(home, down, far.path))
            self.shown(story, '$ tc send --from homebox-a --to far-c "first"',
                       exits={0: README_QUEUED_EXIT, 1: README_QUEUED_EXIT})
            with self.subTest(claim="the first send ran ssh once, the second none"):
                self.assertTrue((down.parent / "calls.jsonl").exists(), "the fake ssh never ran")
                self.assertEqual(len(down_calls()), 1, down_calls())
            self.assert_ran_all(story, SSH_OUTBOUND)

    def test_the_live_board_prints_its_url(self):
        """`python3 board/serve.py` prints the README's line, and the port in it serves live.html.

        Run with `--port 0` (the module block, rule 9). The line is read
        from the server's stdout within BOARD_LINE_CEILING_SECONDS.

        Must reject a line with other words, a token of another shape,
        and a printed port that serves nothing.

        @interacts  one TcRoot; starts board/serve.py (killed by its pid
                    in teardown); one HTTP GET to 127.0.0.1.
        @deps       readme_blocks, expected_pattern; select, http.client,
                    shlex; _root.TcRoot.
        @complexity O(1): one start, one line, one request.
        @alloc      one TcRoot, removed on exit.
        """
        key = "$ python3 board/serve.py"
        block = readme_blocks(README.read_text(encoding="utf-8"))[key]
        with _root.TcRoot() as root:
            story = Story(root)
            for index, (command, lines) in enumerate(block.commands):
                story.ran.add((key, index))
                with self.subTest(block=f"README.md:{block.start}", command=command):
                    self.assertEqual(shlex.split(command), ["python3", "board/serve.py"])
                    proc = root.start(argv=[sys.executable, str(BOARD_SERVER), "--port", ANY_PORT])
                    ready, _, _ = select.select([proc.stdout], [], [], BOARD_LINE_CEILING_SECONDS)
                    self.assertTrue(ready, f"serve.py printed nothing in {BOARD_LINE_CEILING_SECONDS} s")
                    line = proc.stdout.readline().rstrip("\n")
                    self.assertIsNotNone(re.fullmatch(expected_pattern(lines, story), line),
                                         f"\nthe README shows:\n{chr(10).join(lines)}\n\nserve.py printed:\n{line}")
                    conn = http.client.HTTPConnection("127.0.0.1", int(BOARD_PORT.search(line).group(1)),
                                                      timeout=HTTP_TIMEOUT_SECONDS)
                    try:
                        conn.request("GET", "/live.html")
                        self.assertEqual(conn.getresponse().status, HTTP_OK)
                    finally:
                        conn.close()
            self.assert_ran_all(story, BOARD)


def exit_table(text, lead):
    """The exit table that follows the line `lead` in `text`: a list of (code, meaning), meaning lowercased with backticks taken out.

    Rows run from the first `| <digits> |` row after `lead` to the first
    line after it that is not a table row. Raises AssertionError when
    `lead` or the rows are missing.

    @interacts  none; string work only.
    @deps       EXIT_ROW.
    @complexity O(L) over L lines of `text`.
    @alloc      one list, returned.
    """
    lines = text.split("\n")
    starts = [i for i, line in enumerate(lines) if line.startswith(lead)]
    if not starts:
        raise AssertionError(f"no line starts {lead!r}")
    rows, seen = [], False
    for line in lines[starts[0] + 1:]:
        row = EXIT_ROW.match(line)
        if row:
            rows.append((int(row.group(1)), row.group(2).replace("`", "").lower()))
            seen = True
        elif seen and not line.startswith("|"):
            break
    if not rows:
        raise AssertionError(f"no exit rows after {lead!r}")
    return rows


class ExitTableTest(unittest.TestCase):
    """The README's exit table has contracts.md's codes and meanings, and tc defines each code.

    @interacts  reads README.md, contracts.md and tc (loaded as a module
                under a throwaway TC_ROOT).
    @deps       exit_table; _root.load_source, _root.TcRoot.
    @complexity O(L) over the two files' lines, plus one compile of tc.
    @alloc      the two tables and one module, freed on return.
    """

    def test_the_readme_table_is_the_contracts(self):
        """Codes 0 to 11 in both tables in order, each meaning carrying its key words in both, each code an EXIT_ value in tc.

        Must reject a row whose code or meaning changed in either file, a
        row added or dropped, and a code tc does not define.

        @interacts  reads both files; loads tc with TC_ROOT set to the
                    harness root for the load and put back after.
        @deps       exit_table, EXIT_KEY_WORDS; _root.load_source.
        @complexity O(L) over the files' lines, plus one compile of tc.
        @alloc      two lists and one module.
        """
        readme = exit_table(README.read_text(encoding="utf-8"), README_EXIT_HEADING)
        contract = exit_table(CONTRACTS.read_text(encoding="utf-8"), CONTRACT_EXIT_LEAD)
        self.assertEqual([code for code, _ in readme], list(EXIT_CODES), "the README's codes")
        self.assertEqual([code for code, _ in contract], list(EXIT_CODES), "contracts.md's codes")
        with _root.TcRoot() as root:
            old = os.environ.get("TC_ROOT")
            os.environ["TC_ROOT"] = str(root.path)
            try:
                tc = _root.load_source("tc_for_readme", _root.TC)
            finally:
                if old is None:
                    del os.environ["TC_ROOT"]
                else:
                    os.environ["TC_ROOT"] = old
        defined = {value for name, value in vars(tc).items() if name.startswith("EXIT_") and isinstance(value, int)}
        for (code, said), (_, fixed) in zip(readme, contract):
            with self.subTest(code=code):
                for words in EXIT_KEY_WORDS[code]:
                    self.assertIn(words, said, f"README row {code}")
                    self.assertIn(words, fixed, f"contracts.md row {code}")
                self.assertIn(code, defined, f"tc defines no EXIT_ constant with the value {code}")


if __name__ == "__main__":
    unittest.main()
