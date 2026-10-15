/**
 * board-browser-check.mjs: the live board in a real headless browser, at a
 * desktop and a phone size, measured against what the owner reads. Not part
 * of `node --test` (its name does not end .test.mjs): it needs Playwright
 * and a browser, and starts a server. Run it from the repo root, with
 * NODE_PATH set to a Playwright install's node_modules:
 *
 *   NODE_PATH=<a Playwright install>/node_modules node tests/board-browser-check.mjs
 *
 * It builds a throwaway mailbox in the system temp folder: 14 names in two
 * orchestrator trees and a pair of peers. The cards are in C1's shape:
 * written by `tc join` when this tree's tc has it (it says which), else by
 * hand. p1 and p2 share a named account and mail each other, and e2 and e3
 * share another and do not, so the board draws both kinds of native pair.
 * The mail is sent with this tree's tc. Six listeners start with
 * `tc wait --timeout`, each proven by `tc health`; then `d`'s and `e2`'s
 * are seen by the feed and stopped by their pids with no new mail, so both
 * are down workers, not woken ones (D24): `d` is b's only child on its
 * side, and `e2` sits in a's wrapped row, so its wire shares a stretch
 * with a's quiet wire to `b` and its flowing one to `e3`. It starts
 * board/serve.py on a port the OS picks, under its own time limit, opens
 * the board at 1280 x 900 and 390 x 844, and fails on any of: a console
 * error, sideways scroll, drawn text under 11 px, a session missing from the
 * view the width selects (the graph on a desktop, the outline on a phone; a
 * name cut off by an ancestor that clips without scrolling counts as
 * missing), overlapping session boxes, a window shorter than the viewport
 * less its margins, a wire label over another label, a node box or a tree
 * heading, a wire or connector through a node box, the legend not below the
 * last session, no list of roots (or a root link that does not bring its
 * tree into view), an ellipsis or cut words in the pill or the footer, a
 * native pair whose two sessions do not both say `native with <the other> ·
 * not observed` in full, and (on the desktop) a down worker's wire that is
 * not dotted, that a wire other than a dotted one is painted over, that
 * has no knockout in the canvas's face right under it, or whose gaps show
 * anything but the canvas in a screenshot. It saves four screenshots
 * (each size in color and in grayscale) to a temp folder it prints, never
 * into the repo. Every line it prints goes through masked(), so the board's
 * token never shows, an error's URL included.
 *
 * It stops serve.py and every listener by its own pid when it ends, when it
 * throws (a failed browser close included) and on SIGTERM or SIGINT. If it
 * is killed outright, serve.py still ends SERVE_LIMIT_S after it started
 * (an alarm set before serve.py is exec'd) and each listener at its own
 * --timeout.
 *
 * After SIGTERM or SIGINT it stops at its next await and prints nothing
 * past `check stopped by <signal>` but the stop line, and exits 128 plus
 * the signal.
 *
 * `--self-test` checks those promises without a browser: it runs this
 * script six times against a fake Playwright that it writes to a temp
 * folder (a page load that fails with the URL in its error, a browser close
 * that throws, a page load that hangs until SIGTERM, then SIGINT, and a
 * browser launch that settles only on SIGTERM, then SIGINT, so the run
 * resumes after the signal) and once more killed outright under a short
 * time limit, and fails if any run prints a token, leaves serve.py or a
 * listener alive, or prints anything after a signal but the stop line.
 *
 * Without Playwright it prints `skipped: playwright not found` and exits
 * 0, so a fork without it is not broken.
 *
 * Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
 *
 * @interacts  reads NODE_PATH (through require) for Playwright; makes two
 *             folders under the system temp folder (the mailbox and the
 *             screenshots) and leaves both there; runs this tree's ./tc
 *             (join when it has it, send, read, status, health) against
 *             that mailbox, with the session's own CLAUDE and CODEX
 *             variables left out of a join; starts six `tc wait` children
 *             and one board/serve.py child and stops each by its own pid;
 *             asks serve.py's /feed twice with the token; starts one
 *             headless Chromium and closes it; sets file times on the
 *             mailbox's messages, once before the down workers are made
 *             and again before each page, so the newest wires flow while
 *             the page is open and no down worker reads woken; takes one more screenshot per desktop page, kept in
 *             memory, to read the down wires' pixels; listens for SIGTERM
 *             and SIGINT. --self-test writes a
 *             fake playwright module to a temp folder, runs this file as a
 *             child seven times, signals or kills five of them, and stops
 *             anything they left by its pid
 * @deps       Node 18+, Playwright (any recent version; 1.63 on the owner's
 *             machine), python3, ./tc, board/serve.py
 * @complexity O(v * (b^2 + w * s * b + d * s' * c)) per view over b <= 14
 *             boxes, w wires and s samples along each, and the s' samples
 *             along each of the d = 2 down wires, each tested against c
 *             boxes, ports and labels (tens); decoding one screenshot is
 *             O(P) over its P pixels (about 1280 x 1800); a run takes
 *             seconds (the self-test, seven runs without a browser, tens of
 *             seconds)
 * @alloc      one browser, one page at a time, four screenshots on disk and
 *             one decoded screenshot per desktop page in memory
 */
import { createRequire } from 'node:module';
import { spawn, execFileSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, writeFileSync, readdirSync, readFileSync, utimesSync } from 'node:fs';
import { tmpdir, constants } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { inflateSync } from 'node:zlib';

const HERE = fileURLToPath(import.meta.url);
const REPO = join(dirname(HERE), '..');
const TC = join(REPO, 'tc');
const SERVE = join(REPO, 'board', 'serve.py');

// The owner's real board is about 14 names: two orchestrator trees (b is a
// relay under a) and two peers. [name, reports_to].
const CARDS = [
  ['a', null], ['b', 'a'], ['docs', 'a'], ['c', 'b'], ['d', 'b'], ['e1', 'a'], ['e2', 'a'], ['e3', 'a'],
  ['z', null], ['y1', 'z'], ['y2', 'z'], ['y3', 'z'], ['p1', null], ['p2', null],
];
const NAMES = CARDS.map(([name]) => name);
// Two native pairs: p1 and p2 share an account and mail each other; e2 and
// e3 share another and never mail each other. Every other card has an
// account of its own, so it is in no pair.
const SHARED_ACCOUNTS = { p1: 'acct-peers', p2: 'acct-peers', e2: 'acct-e', e3: 'acct-e' };
const accountOf = (name) => SHARED_ACCOUNTS[name] || `acct-${name}`;
// The words each session of a native pair must show, in full (C5).
const NATIVE_WORDS = {
  p1: 'native with p2 · not observed', p2: 'native with p1 · not observed',
  e2: 'native with e3 · not observed', e3: 'native with e2 · not observed',
};
// The mail, in send order: tc numbers them 1 to 18.
const MAIL = [
  ['a', 'b'], ['b', 'a'], ['a', 'docs'], ['b', 'c'], ['c', 'b'], ['b', 'd'], ['z', 'y1'], ['y1', 'z'], ['z', 'y2'],
  ['z', 'y3'], ['z', 'a'], ['a', 'z'], ['a', 'e1'], ['a', 'e2'], ['a', 'e3'], ['p1', 'p2'], ['p2', 'p1'], ['b', 'd'],
];
// Messages from this seq on are made fresh before each page opens, so their
// wires flow (the feed's 10 s writing window) and carry labels: five pairs,
// among them a wire between the two trees and one between the peers. A
// message to a down worker stays old: mail that reached it after it was
// last seen listening would read as a wake (D24), not a listener lost.
const FRESH_FROM_SEQ = 10;
// Every other message is set this old, past the writing window, so only
// the fresh ones flow and only their senders read writing.
const OLD_AGE_S = 600;
const MS_PER_S = 1000;
// d and e2 read their mail too, since a `tc wait` with mail waiting exits
// at once.
const READERS = ['a', 'b', 'c', 'z', 'd', 'e2'];
const LISTENERS = ['a', 'b', 'c', 'z', 'd', 'e2'];
// Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
// The workers made down, each with the wire to it: its listener is seen by
// the feed, then stopped. d is b's only child on its side. e2 is in a's
// wrapped row, so its wire shares the parent's end with a's quiet wire to b
// and nearly all its run with a's flowing wire to e3: its dots must still
// show nothing but the canvas between them.
const DOWN_EDGES = { d: 'mailbox:b>d', e2: 'mailbox:a>e2' };
const DOWN = Object.keys(DOWN_EDGES);
// A listener outlives the run on its own if no cleanup ran.
const LISTEN_TIMEOUT_S = 120;
// serve.py's own limit, for a run killed outright: an alarm set before
// serve.py is exec'd ends it this long after it starts. The self-test sets
// a short one through SERVE_LIMIT_ENV.
const SERVE_LIMIT_S = 120;
const SERVE_LIMIT_ENV = 'TC_CHECK_SERVE_LIMIT_S';
// python3 -c: set the alarm, then exec serve.py in the same process (same
// pid; an alarm survives exec, and SIGALRM's default ends the process).
const SERVE_UNDER_ALARM = 'import os, signal, sys; signal.alarm(int(sys.argv[1])); '
  + 'os.execv(sys.executable, [sys.executable] + sys.argv[2:])';
// A made-up join time, so no hand-written card carries the clock.
const JOINED_AT = '2026-10-14T12:00:00-05:00';
// The variables tc join reads from the session it runs in. They are left
// out, so no card carries the session running this check, and the kind and
// account come from the flags alone.
const SESSION_VARS = ['CODEX_THREAD_ID', 'CLAUDECODE', 'CLAUDE_CODE_SESSION_ID', 'CLAUDE_PID', 'CLAUDE_CONFIG_DIR'];
const TOKEN_HEADER = 'X-TC-Token';

const VIEWS = [
  { label: '1280', width: 1280, height: 900, expect: 'graph' },
  { label: '390', width: 390, height: 844, expect: 'outline' },
];
const MIN_TEXT_PX = 11;
// Two boxes may touch at an edge; this much overlap is a real overlap.
const OVERLAP_PX = 1;
// A wire starts on its node's edge, half its stroke inside the box. A sample
// this far inside a node box is a wire through it.
const WIRE_INSIDE_PX = 2;
// Samples along each wire, this many px of path apart.
const WIRE_STEP_PX = 2;
// Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
// A down wire's pixels, read along its middle from a screenshot taken with
// the animations stopped, one sample every DOTTED_STEP_PX of path. A sample
// more than INK_LUMA steps of luma (of 255) off the canvas's own face is
// ink. A dot is 2 px long (theme.css: stroke-dasharray 2 5), so a run of
// ink longer than DOT_INK_MAX_PX (a dot and a px of antialiasing at each
// end) means something else shows in a gap, and a run of canvas longer than
// GAP_MAX_PX (a 5 px gap and the same) means the dots are gone. END_SKIP_PX
// at each end is left out: there the arrowhead (ARROW_BACKOFF 15 of a 10
// unit marker 7 stroke widths of 2.5 px wide, so it reaches 26.25 px back)
// and the boxes' port rings and shadows sit on the wire. A sample within
// COVER_PX of a node box, a port ring or a wire label is left out too: those
// are drawn over every wire.
const DOTTED_STEP_PX = 1;
const INK_LUMA = 16;
const DOT_INK_MAX_PX = 4;
const GAP_MAX_PX = 7;
const END_SKIP_PX = 28;
const COVER_PX = 2;
// Rec. 709 luma weights, red, green and blue.
const LUMA = [0.2126, 0.7152, 0.0722];
// What this check reads of a PNG (the PNG specification): the 8 byte
// signature; in each chunk, the type 4 bytes in and the data 8 bytes in,
// with 12 bytes round the data (length, type, checksum); the IHDR fields'
// offsets, 8 bits per channel, no interlace, the channels of color types 2
// (RGB) and 6 (RGBA), and the five row filters.
const PNG = Object.freeze({
  SIGNATURE: 8, TYPE_AT: 4, DATA_AT: 8, CHUNK_ROUND: 12, WIDTH_AT: 0, HEIGHT_AT: 4, DEPTH_AT: 8, COLOR_AT: 9, INTERLACE_AT: 12,
  DEPTH: 8, CHANNELS: { 2: 3, 6: 4 }, NONE: 0, SUB: 1, UP: 2, AVERAGE: 3, PAETH: 4,
});
// Setup and settle times. The page polls every 3 s and draws the first
// answer at once; fonts may come from the network.
const SERVER_START_MS = 10000;
const PROOF_MS = 5000;
const PROOF_STEP_MS = 100;
const DRAWN_MS = 10000;
const SETTLE_MS = 800;
const STOP_MS = 5000;
const SPACES_IN_JSON = 0;
// A shell's code for a process ended by a signal: this plus its number.
const SIGNAL_EXIT_BASE = 128;
const SIGNALS = ['SIGTERM', 'SIGINT'];
// The self-test: how long one run may take, the short serve.py limit for
// the run it kills outright, and the grace past it.
const SELF_RUN_MS = 60000;
const SELF_SERVE_LIMIT_S = 4;
const SELF_GRACE_MS = 4000;
const FAKE_MODE_ENV = 'TC_FAKE_PLAYWRIGHT';
// The state letter /proc/<pid>/stat gives a process that has ended and
// waits to be reaped.
const ZOMBIE_STATE = 'Z';

/**
 * Text with every board token hidden. The pattern is the token's own
 * alphabet (token_urlsafe), global, so a URL that shows up twice in one
 * error (Playwright's goto puts it in the message and in its call log) is
 * hidden both times, and the rest of the text stays.
 * @complexity O(t) over t characters  @alloc one string
 */
const masked = (text) => String(text).replace(/token=[A-Za-z0-9_-]+/g, 'token=<hidden>');
/** Print one line, masked. Every line this script prints goes through it. @complexity O(t)  @alloc one string */
const say = (text = '') => console.log(masked(text));

/** The environment for a child: this one plus `extra`, less `drop`. @complexity O(v) over v variables  @alloc one object */
function envWith(extra, drop = []) {
  const env = { ...process.env, ...extra };
  for (const name of drop) delete env[name];
  return env;
}

/** Run ./tc with the mailbox in the env and return its stdout. @complexity one child  @alloc its output */
function tc(root, args, drop = []) {
  return execFileSync('python3', [TC, ...args], { env: envWith({ TC_ROOT: root }, drop), encoding: 'utf8' });
}

/** True when this tree's tc has `tc join` (CARDS' command): its help exits 0. @complexity one child  @alloc none */
function tcHasJoin(root) {
  try {
    execFileSync('python3', [TC, 'join', '--help'], { env: envWith({ TC_ROOT: root }), stdio: 'ignore' });
    return true;
  } catch {
    return false;
  }
}

/** A promise that settles after ms. @complexity O(1)  @alloc one timer */
const sleep = (ms) => new Promise((resolve) => { setTimeout(resolve, ms); });

/**
 * The throwaway mailbox: cards in C1's shape (through `tc join` when this
 * tree's tc has it, else written by hand), the mail, the inboxes of the
 * six READERS read, and their status lines.
 * @complexity O(names + mail) tc calls  @alloc the folder, left in place
 * @returns {{ root, joined: boolean }}
 */
function buildMailbox() {
  const root = mkdtempSync(join(tmpdir(), 'tc-board-check-'));
  const joined = tcHasJoin(root);
  if (!joined) mkdirSync(join(root, 'cards'));
  for (const [name, reportsTo] of CARDS) {
    if (joined) {
      tc(root, ['join', name, '--kind', 'claude', '--account', accountOf(name), ...(reportsTo ? ['--reports-to', reportsTo] : [])],
        SESSION_VARS);
      continue;
    }
    const card = {
      version: 1, name, kind: 'claude', account: accountOf(name), route: 'local', session_id: null, pid: null,
      thread_id: null, ssh: null, reports_to: reportsTo, joined_at: JOINED_AT,
    };
    writeFileSync(join(root, 'cards', `${name}.json`), `${JSON.stringify(card, null, 2)}\n`);
  }
  for (const [from, to] of MAIL) tc(root, ['send', '--from', from, '--to', to, `step for ${to}`]);
  for (const name of READERS) tc(root, ['read', name]);
  for (const name of LISTENERS) tc(root, ['status', name, `working on step ${name}`]);
  return { root, joined };
}

/**
 * Set every message from FRESH_FROM_SEQ on to now, so its wire flows, and
 * every older one OLD_AGE_S back, so it does not. Every message to a down
 * worker is set old too, so it reads down and never woken (D24).
 * @complexity O(m) over m message files  @alloc one list of names
 */
function freshen(root) {
  const now = new Date();
  const old = new Date(now.getTime() - OLD_AGE_S * MS_PER_S);
  const mail = join(root, 'mail');
  for (const box of readdirSync(mail).filter((d) => d.startsWith('to-'))) {
    const toDown = DOWN.includes(box.slice('to-'.length));
    for (const where of [join(mail, box), join(mail, box, 'read')]) {
      for (const file of readdirSync(where).filter((f) => f.endsWith('.md'))) {
        const when = !toDown && Number(file.slice(0, file.indexOf('-'))) >= FRESH_FROM_SEQ ? now : old;
        utimesSync(join(where, file), when, when);
      }
    }
  }
}

/**
 * Poll `tc health` until want(listeners) holds, PROOF_MS at most.
 * @complexity O(PROOF_MS / PROOF_STEP_MS) health calls  @alloc one parsed answer per call
 * @returns {Promise<object>}  the listeners map that passed
 */
async function healthUntil(root, want, what) {
  const until = Date.now() + PROOF_MS;
  while (Date.now() < until) {
    const { listeners } = JSON.parse(tc(root, ['health', '--json']));
    if (want(listeners)) return listeners;
    await sleep(PROOF_STEP_MS);
  }
  throw new Error(`tc health never showed ${what}`);
}

/**
 * Start the listeners and wait until tc health names each one's pid.
 * @complexity O(PROOF_MS / PROOF_STEP_MS) health calls  @alloc one child per listener
 * @returns {Promise<string[]>}  `name:pid` per listener
 */
async function startListeners(root, children, listenerOf) {
  for (const name of LISTENERS) {
    const child = spawn('python3', [TC, 'wait', name, '--timeout', String(LISTEN_TIMEOUT_S)], {
      env: envWith({ TC_ROOT: root }), stdio: 'ignore',
    });
    children.push(child);
    listenerOf.set(name, child);
  }
  const listeners = await healthUntil(root, (l) => LISTENERS.every((name) => l[name]), `all ${LISTENERS.length} listeners`);
  return LISTENERS.map((name) => `${name}:${listeners[name]}`);
}

/**
 * Start serve.py on a port the OS picks, under SERVE_LIMIT_S (or the
 * self-test's limit), and read the URL it prints.
 * @complexity O(1)  @alloc one child
 */
function startServer(root, children) {
  const limit = process.env[SERVE_LIMIT_ENV] || String(SERVE_LIMIT_S);
  const child = spawn('python3', ['-c', SERVE_UNDER_ALARM, limit, SERVE, '--port', '0'], {
    env: envWith({ TC_ROOT: root }), stdio: ['ignore', 'pipe', 'pipe'],
  });
  children.push(child);
  return new Promise((resolve, reject) => {
    let out = '';
    const timer = setTimeout(() => reject(new Error('serve.py printed no URL')), SERVER_START_MS);
    child.stdout.on('data', (chunk) => {
      out += chunk;
      const m = out.match(/board: (http:\/\/\S+)/);
      if (m) {
        clearTimeout(timer);
        resolve(m[1]);
      }
    });
    child.on('exit', (code) => reject(new Error(`serve.py exited with ${code}`)));
  });
}

/** One answer from serve.py's /feed, asked with the URL's token. @complexity one request  @alloc the parsed feed */
async function askFeed(url) {
  const { origin, hash } = new URL(url);
  const token = new URLSearchParams(hash.slice(1)).get('token') || '';
  const answer = await fetch(`${origin}/feed`, { headers: { [TOKEN_HEADER]: token } });
  if (!answer.ok) throw new Error(`the feed answered ${answer.status}`);
  return answer.json();
}

/**
 * Make each of DOWN a down worker the real way: the feed sees its
 * listener, the listener is stopped by its pid, tc health shows no pid,
 * and the feed then says down.
 * @complexity two feeds and O(PROOF_MS / PROOF_STEP_MS) health calls  @alloc two parsed feeds
 * @returns {Promise<number[]>}  the stopped listeners' pids, in DOWN's order
 */
async function makeDown(root, url, listenerOf) {
  const seen = (await askFeed(url)).nodes;
  for (const name of DOWN) {
    const node = seen.find((n) => n.id === name);
    if (!node || !node.listener_pid) throw new Error(`the feed never saw ${name} listening`);
  }
  for (const name of DOWN) await stop(listenerOf.get(name));
  await healthUntil(root, (l) => DOWN.every((name) => !l[name]), `${DOWN.join(' and ')}'s listeners gone`);
  const after = (await askFeed(url)).nodes;
  for (const name of DOWN) {
    const node = after.find((n) => n.id === name);
    if (!node || node.state !== 'down') throw new Error(`the feed says ${name} is ${node && node.state}, not down`);
  }
  return DOWN.map((name) => listenerOf.get(name).pid);
}

/** Stop a child by its own pid and wait for it to exit. @complexity O(1)  @alloc one promise */
async function stop(child) {
  if (child.exitCode !== null || child.signalCode !== null) return;
  const gone = new Promise((resolve) => { child.once('exit', resolve); });
  process.kill(child.pid, 'SIGTERM');
  await Promise.race([gone, sleep(STOP_MS)]);
  if (child.exitCode === null && child.signalCode === null) process.kill(child.pid, 'SIGKILL');
}

/**
 * Everything the checks read from one open page, measured in the page.
 * @complexity O(b^2 + w * s * b + d * s' * c) in the page (see the module
 *             block)  @alloc one plain object, with s' points per down wire
 */
function measure(page, names) {
  return page.evaluate(({ names, wireStep, insidePx, downEdges, dottedStep, endSkip, coverPx }) => {
    const visible = (el) => el.getClientRects().length > 0 && getComputedStyle(el).visibility !== 'hidden';
    // On screen means reachable: drawn, and not cut off by an ancestor that
    // clips without scrolling (overflow hidden or clip).
    const reachable = (el) => {
      if (!visible(el)) return false;
      const r = el.getBoundingClientRect();
      for (let a = el.parentElement; a; a = a.parentElement) {
        const cs = getComputedStyle(a);
        if (!['hidden', 'clip'].includes(cs.overflowX) && !['hidden', 'clip'].includes(cs.overflowY)) continue;
        const b = a.getBoundingClientRect();
        if (r.left < b.left - 1 || r.right > b.right + 1 || r.top < b.top - 1 || r.bottom > b.bottom + 1) return false;
      }
      return true;
    };
    const box = (r) => ({ left: r.left, top: r.top, right: r.right, bottom: r.bottom });
    const win = document.querySelector('.tc-win');
    const out = { view: win.dataset.view || 'graph', innerW: innerWidth, innerH: innerHeight };
    // Sideways scroll, on the page or in any scroll area.
    out.scrollW = document.documentElement.scrollWidth;
    out.sidewaysEls = [];
    for (const el of document.querySelectorAll('*')) {
      const cs = getComputedStyle(el);
      if ((cs.overflowX === 'auto' || cs.overflowX === 'scroll') && el.scrollWidth > el.clientWidth + 1) out.sidewaysEls.push(el.className);
    }
    // The smallest drawn text, HTML and SVG, visible only. An element's
    // scale is the product of its ancestors' CSS transforms (the board's
    // view is the one that may scale).
    out.minText = Infinity;
    out.minTextWhere = '';
    const scaleOf = (el) => {
      let k = 1;
      for (let a = el; a; a = a.parentElement) {
        const t = getComputedStyle(a).transform;
        if (t && t !== 'none') { const m = new DOMMatrix(t); k *= Math.hypot(m.a, m.b); }
      }
      return k;
    };
    const walker = document.createTreeWalker(win, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const t = walker.currentNode;
      const el = t.parentElement;
      if (!t.textContent.trim() || !el || el.closest('svg') || !visible(el)) continue;
      const px = parseFloat(getComputedStyle(el).fontSize) * scaleOf(el);
      if (px < out.minText) { out.minText = px; out.minTextWhere = `${el.className}: ${t.textContent.trim().slice(0, 30)}`; }
    }
    for (const t of document.querySelectorAll('svg text')) {
      if (!t.textContent.trim() || !visible(t)) continue;
      const ctm = t.getScreenCTM();
      const px = parseFloat(getComputedStyle(t).fontSize) * (ctm ? Math.hypot(ctm.a, ctm.b) : 1);
      if (px < out.minText) { out.minText = px; out.minTextWhere = `svg text: ${t.textContent.trim().slice(0, 30)}`; }
    }
    // Sessions on screen in the view the width selects.
    out.names = [...document.querySelectorAll('.tc-node-name, .tc-row-name')].filter(reachable).map((el) => el.textContent.trim());
    out.missing = names.filter((n) => !out.names.includes(n));
    const sessions = [...document.querySelectorAll('.tc-node, .tc-row')].filter(visible);
    out.boxes = sessions.map((el) => ({ ...box(el.getBoundingClientRect()), name: (el.querySelector('.tc-node-name, .tc-row-name') || {}).textContent }));
    // The badge lines each session shows on screen, and whether a box's
    // names were cut short.
    out.badges = {};
    for (const el of sessions) {
      const name = (el.querySelector('.tc-node-name, .tc-row-name') || {}).textContent;
      out.badges[name] = [...el.querySelectorAll('.tc-node-badge, .tc-row-badge')].filter(reachable).map((b) => {
        const part = b.querySelector('.tc-node-badge-names');
        return { text: b.textContent, cut: !!part && part.scrollWidth > part.clientWidth + 1 };
      });
    }
    const nodes = [...document.querySelectorAll('.tc-node')].filter(visible).map((el) => ({
      ...box(el.getBoundingClientRect()), name: el.querySelector('.tc-node-name').textContent,
    }));
    out.heads = [...document.querySelectorAll('.tc-head')].filter(visible).map((el) => ({ ...box(el.getBoundingClientRect()), text: el.textContent }));
    out.labels = [...document.querySelectorAll('svg text.tc-wire-label')]
      .filter((t) => t.textContent.trim() && visible(t))
      .map((t) => ({ ...box(t.getBoundingClientRect()), text: t.textContent }));
    // Wires and connectors: points along each drawn path, in page px.
    out.wireHits = [];
    out.wires = 0;
    const drawn = [...document.querySelectorAll('path.tc-wire')].filter((p) => visible(p) && p.getAttribute('d'));
    for (const p of drawn) {
      out.wires += 1;
      const ctm = p.getScreenCTM();
      const len = p.getTotalLength();
      for (let s = 0; s <= len; s += wireStep) {
        const q = new DOMPoint(p.getPointAtLength(s).x, p.getPointAtLength(s).y).matrixTransform(ctm);
        const hit = nodes.find((n) => q.x > n.left + insidePx && q.x < n.right - insidePx && q.y > n.top + insidePx && q.y < n.bottom - insidePx);
        if (hit) { out.wireHits.push(`${p.dataset.edge || p.getAttribute('class')} through ${hit.name}`); break; }
      }
    }
    // Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
    // Each down worker's wire: its class and dashes; every wire painted
    // after it (document order is paint order in SVG), which may only be
    // another dotted one; the path right before it, which must be its
    // knockout; and the page points along its middle where its pixels are
    // read, in document px (the screenshot is the full page). Points near
    // either end, or under a box, a port ring or a label, are left out.
    const canvasFace = getComputedStyle(document.querySelector('.tc-canvas')).backgroundColor;
    const covers = [...document.querySelectorAll('.tc-node, .tc-port, .tc-wire-label-back')].filter(visible)
      .map((el) => box(el.getBoundingClientRect())).filter((b) => b.right > b.left && b.bottom > b.top);
    const strokes = [...document.querySelectorAll('path.tc-wire')].filter((p) => p.getAttribute('d'));
    out.downs = downEdges.map((id) => {
      const p = drawn.find((x) => x.dataset.edge === id);
      if (!p) return { id, drawn: false };
      const cs = getComputedStyle(p);
      const over = strokes.slice(strokes.indexOf(p) + 1).filter((o) => !o.classList.contains('down'))
        .map((o) => o.dataset.edge || o.getAttribute('class'));
      const k = p.previousElementSibling;
      const knock = k && k.matches('path.tc-knockout') && k.getAttribute('d') === p.getAttribute('d')
        ? { stroke: getComputedStyle(k).stroke, width: parseFloat(getComputedStyle(k).strokeWidth), opacity: Number(getComputedStyle(k).opacity) }
        : null;
      const ctm = p.getScreenCTM();
      const len = p.getTotalLength();
      const samples = [];
      let covered = 0;
      for (let s = endSkip; s <= len - endSkip; s += dottedStep) {
        const at = p.getPointAtLength(s);
        const q = new DOMPoint(at.x, at.y).matrixTransform(ctm);
        if (covers.some((b) => q.x > b.left - coverPx && q.x < b.right + coverPx && q.y > b.top - coverPx && q.y < b.bottom + coverPx)) {
          covered += 1;
          continue;
        }
        samples.push([q.x + scrollX, q.y + scrollY, s]);
      }
      return {
        id, drawn: true, cls: p.getAttribute('class'), dash: cs.strokeDasharray, width: parseFloat(cs.strokeWidth),
        over, knock, canvasFace, samples, covered, pageW: document.documentElement.scrollWidth,
      };
    });
    const rect = win.getBoundingClientRect();
    const bodyCs = getComputedStyle(document.body);
    out.winH = rect.height;
    out.margins = parseFloat(bodyCs.paddingTop) + parseFloat(bodyCs.paddingBottom);
    const legend = [...document.querySelectorAll('.tc-legend')].find(visible);
    out.legend = legend ? { ...box(legend.getBoundingClientRect()), text: legend.textContent } : null;
    const roots = document.querySelector('.tc-roots');
    out.roots = roots && visible(roots) ? roots.textContent : null;
    const cut = (el) => el.scrollWidth > el.clientWidth + 1 || el.textContent.includes('…');
    const pill = document.querySelector('.tc-conn');
    out.pill = pill ? pill.textContent : null;
    out.cutWords = [pill, ...document.querySelectorAll('.tc-conn *, .tc-foot, .tc-foot *')].filter((el) => el && visible(el) && cut(el))
      .map((el) => `${el.className}: ${el.textContent.slice(0, 40)}`);
    out.foot = document.querySelector('.tc-foot').textContent;
    return out;
  }, {
    names, wireStep: WIRE_STEP_PX, insidePx: WIRE_INSIDE_PX, downEdges: Object.values(DOWN_EDGES), dottedStep: DOTTED_STEP_PX,
    endSkip: END_SKIP_PX, coverPx: COVER_PX,
  });
}

/**
 * A PNG's pixels, from Playwright's screenshot buffer: 8-bit RGB or RGBA,
 * not interlaced, which is what Chromium writes. Throws on anything else.
 * Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
 * @complexity O(P) over the image's P bytes  @alloc the inflated rows and one pixel buffer
 * @returns {{ width, height, channels, px: Buffer }}
 */
function decodePng(buf) {
  let at = PNG.SIGNATURE;
  let head = null;
  const data = [];
  while (at < buf.length) {
    const len = buf.readUInt32BE(at);
    const type = buf.toString('latin1', at + PNG.TYPE_AT, at + PNG.DATA_AT);
    const body = buf.subarray(at + PNG.DATA_AT, at + PNG.DATA_AT + len);
    if (type === 'IHDR') head = body;
    else if (type === 'IDAT') data.push(body);
    else if (type === 'IEND') break;
    at += PNG.CHUNK_ROUND + len;
  }
  const channels = head && PNG.CHANNELS[head[PNG.COLOR_AT]];
  if (!channels || head[PNG.DEPTH_AT] !== PNG.DEPTH || head[PNG.INTERLACE_AT] !== 0) throw new Error('the screenshot is not an 8-bit RGB or RGBA PNG');
  const width = head.readUInt32BE(PNG.WIDTH_AT);
  const height = head.readUInt32BE(PNG.HEIGHT_AT);
  const raw = inflateSync(Buffer.concat(data));
  const stride = width * channels;
  const px = Buffer.alloc(height * stride);
  for (let y = 0; y < height; y += 1) {
    const filter = raw[y * (stride + 1)];
    for (let i = 0; i < stride; i += 1) {
      const left = i >= channels ? px[y * stride + i - channels] : 0;
      const up = y ? px[(y - 1) * stride + i] : 0;
      const corner = y && i >= channels ? px[(y - 1) * stride + i - channels] : 0;
      let add = 0;
      if (filter === PNG.SUB) add = left;
      else if (filter === PNG.UP) add = up;
      else if (filter === PNG.AVERAGE) add = (left + up) >> 1;
      else if (filter === PNG.PAETH) {
        const guess = left + up - corner;
        const [dl, du, dc] = [Math.abs(guess - left), Math.abs(guess - up), Math.abs(guess - corner)];
        add = dl <= du && dl <= dc ? left : du <= dc ? up : corner;
      }
      px[y * stride + i] = (raw[y * (stride + 1) + 1 + i] + add) & 0xff;
    }
  }
  return { width, height, channels, px };
}

/** The luma of red, green and blue, 0 to 255. @complexity O(1)  @alloc none */
const lumaOf = (r, g, b) => LUMA[0] * r + LUMA[1] * g + LUMA[2] * b;

/**
 * Along one down wire's samples: how many were read, the longest run of
 * ink and the longest run of canvas, each in px of path. A run breaks where
 * a sample was left out (near an end, or under a box, a port or a label).
 * Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
 * @complexity O(s) over s samples  @alloc one small object
 */
function readDots(shot, down) {
  const face = lumaOf(...down.canvasFace.match(/\d+/g).slice(0, LUMA.length).map(Number));
  const scale = shot.width / down.pageW;
  let [ink, gap, longestInk, longestGap, inked, last] = [0, 0, 0, 0, 0, null];
  for (const [x, y, s] of down.samples) {
    if (last === null || s - last > DOTTED_STEP_PX) [ink, gap] = [0, 0];
    last = s;
    const i = (Math.floor(y * scale) * shot.width + Math.floor(x * scale)) * shot.channels;
    if (Math.abs(lumaOf(shot.px[i], shot.px[i + 1], shot.px[i + 2]) - face) > INK_LUMA) {
      inked += 1;
      [ink, gap] = [ink + DOTTED_STEP_PX, 0];
    } else {
      [ink, gap] = [0, gap + DOTTED_STEP_PX];
    }
    longestInk = Math.max(longestInk, ink);
    longestGap = Math.max(longestGap, gap);
  }
  return { read: down.samples.length, inked, longestInk, longestGap };
}

/** True when two page boxes overlap by more than OVERLAP_PX. @complexity O(1)  @alloc none */
const overlap = (p, q) => Math.min(p.right, q.right) - Math.max(p.left, q.left) > OVERLAP_PX
  && Math.min(p.bottom, q.bottom) - Math.max(p.top, q.top) > OVERLAP_PX;

/** Every pair of boxes in `list` that overlaps, named. @complexity O(b^2)  @alloc one list */
function pairsOverlapping(list, nameOf) {
  const hits = [];
  for (let i = 0; i < list.length; i += 1) {
    for (let j = i + 1; j < list.length; j += 1) if (overlap(list[i], list[j])) hits.push(`${nameOf(list[i])} on ${nameOf(list[j])}`);
  }
  return hits;
}

/**
 * The checks for one view, as [name, ok, detail] rows.
 * @complexity O(b^2 + l * b)  @alloc one list of rows
 */
function judge(view, m, errors, jump) {
  const rows = [];
  const check = (name, ok, detail) => rows.push([name, ok, ok ? '' : detail]);
  check(`draws the ${view.expect} view`, m.view === view.expect, `data-view is ${m.view}`);
  check('no console errors', errors.length === 0, errors.join(' | '));
  check('no sideways scroll', m.scrollW <= m.innerW + 1 && m.sidewaysEls.length === 0,
    `page ${m.scrollW} px in a ${m.innerW} px viewport; scroll areas: ${m.sidewaysEls.join(', ')}`);
  check(`smallest text at least ${MIN_TEXT_PX} px`, m.minText >= MIN_TEXT_PX, `${m.minText.toFixed(1)} px at ${m.minTextWhere}`);
  check(`every session on screen (${NAMES.length})`, m.missing.length === 0, `missing: ${m.missing.join(', ')}`);
  const boxHits = pairsOverlapping(m.boxes, (b) => b.name);
  check('no session box over another', boxHits.length === 0, boxHits.join('; '));
  check('window at least the viewport less its margins', m.winH >= m.innerH - m.margins - 1,
    `window ${m.winH.toFixed(0)} px, viewport ${m.innerH} less ${m.margins} px`);
  const labelHits = [
    ...pairsOverlapping(m.labels, (l) => `label "${l.text}"`),
    ...m.labels.flatMap((l) => m.boxes.filter((b) => overlap(l, b)).map((b) => `label "${l.text}" on ${b.name}`)),
    ...m.labels.flatMap((l) => m.heads.filter((h) => overlap(l, h)).map((h) => `label "${l.text}" on heading "${h.text}"`)),
  ];
  check(`no label over a label, a box or a heading (${m.labels.length} labels)`, labelHits.length === 0, labelHits.join('; '));
  check(`no wire through a node box (${m.wires} wires and connectors)`, m.wireHits.length === 0, m.wireHits.join('; '));
  const lastBottom = Math.max(...m.boxes.map((b) => b.bottom));
  check('legend below the last session', !!m.legend && m.legend.top >= lastBottom && !m.boxes.some((b) => overlap(m.legend, b)),
    m.legend ? `legend top ${m.legend.top.toFixed(0)}, last session bottom ${lastBottom.toFixed(0)}` : 'no legend shown');
  check('roots listed at the top', !!m.roots && m.roots.includes('2 orchestrators: a, z'), `roots: ${m.roots}`);
  check('the root link for z brings z\'s tree into view', jump.ok, jump.detail);
  check('nothing cut off in the pill or the footer', m.cutWords.length === 0, m.cutWords.join('; '));
  const badgeMiss = NAMES.flatMap((name) => {
    const want = NATIVE_WORDS[name] ? [NATIVE_WORDS[name]] : [];
    const got = (m.badges[name] || []).map((b) => b.text);
    const cutShort = (m.badges[name] || []).filter((b) => b.cut).map((b) => `${name}'s "${b.text}" is cut short`);
    return JSON.stringify(got) === JSON.stringify(want) ? cutShort : [`${name} shows ${JSON.stringify(got)}, not ${JSON.stringify(want)}`, ...cutShort];
  });
  check(`each native pair says native with the other, not observed (${Object.keys(NATIVE_WORDS).join(', ')})`,
    badgeMiss.length === 0, badgeMiss.join('; '));
  if (view.expect === 'graph') {
    for (const d of m.downs) {
      if (!d.drawn) {
        check(`the down worker's wire (${d.id}) is dotted and shows only the canvas in its gaps`, false, `no wire ${d.id} drawn`);
        continue;
      }
      const dots = d.dots;
      const knockOk = !!d.knock && d.knock.stroke === d.canvasFace && d.knock.width > d.width && d.knock.opacity === 1;
      const ok = /\bdown\b/.test(d.cls) && !!d.dash && d.dash !== 'none' && d.over.length === 0 && knockOk
        && dots.read > 0 && dots.longestInk <= DOT_INK_MAX_PX && dots.longestGap <= GAP_MAX_PX;
      check(`the down worker's wire (${d.id}) is dotted and shows only the canvas in its gaps (${dots.read} px read, `
        + `longest ink ${dots.longestInk} px, longest gap ${dots.longestGap} px)`, ok,
      `class "${d.cls}", dasharray ${d.dash}; painted over it: ${d.over.join(', ') || 'nothing'}; knockout: `
        + `${d.knock ? `${d.knock.width} px ${d.knock.stroke} at opacity ${d.knock.opacity} under a ${d.width} px wire on a ${d.canvasFace} canvas` : 'none'}; `
        + `${dots.read} px read (${d.covered} under a box, port or label): longest ink run ${dots.longestInk} px (most ${DOT_INK_MAX_PX}), `
        + `longest gap ${dots.longestGap} px (most ${GAP_MAX_PX}), ${dots.inked} px of ink`);
    }
  }
  return rows;
}

/**
 * Click the roots list's `z` and say whether z's heading is then on screen.
 * @complexity O(1)  @alloc one small object
 */
async function jumpToZ(page) {
  const button = page.locator('.tc-roots button', { hasText: /^z$/ });
  if (await button.count() !== 1) return { ok: false, detail: 'no button named z in the roots list' };
  await button.click();
  return page.evaluate(() => {
    const heads = [...document.querySelectorAll('.tc-head, .tc-group-head')].filter((el) => el.getClientRects().length);
    const head = heads.find((el) => el.textContent.startsWith('z ·'));
    if (!head) return { ok: false, detail: 'no heading for z' };
    const r = head.getBoundingClientRect();
    return { ok: r.top >= 0 && r.bottom <= innerHeight, detail: `z's heading at ${r.top.toFixed(0)} to ${r.bottom.toFixed(0)} in a ${innerHeight} px viewport` };
  });
}

/**
 * Open one view: color (measured and saved; on the desktop one more
 * screenshot, kept in memory, for the down wires' pixels), then grayscale
 * (saved). `halt` is called after each await: it throws once a signal has
 * begun cleanup, so a stopped run goes no further.
 * @complexity two page loads, plus one screenshot decoded in O(P) over its
 *             P pixels on the desktop
 * @alloc      two pages, closed; one decoded screenshot, dropped on return
 */
async function runView(browser, url, root, view, shots, halt) {
  const results = { rows: [], files: [] };
  for (const gray of [false, true]) {
    freshen(root);
    const page = await browser.newPage({ viewport: { width: view.width, height: view.height } });
    halt();
    const errors = [];
    page.on('console', (msg) => { if (msg.type() === 'error') errors.push(msg.text()); });
    page.on('pageerror', (err) => errors.push(String(err)));
    const [base, hash] = url.split('#');
    await page.goto(`${base}${gray ? '?gray=1' : ''}#${hash}`);
    halt();
    await page.waitForSelector('.tc-node, .tc-row', { timeout: DRAWN_MS });
    halt();
    await page.evaluate(() => document.fonts.ready);
    halt();
    await page.waitForTimeout(SETTLE_MS);
    halt();
    const file = join(shots, `board-${view.label}-${gray ? 'gray' : 'color'}.png`);
    await page.screenshot({ path: file, fullPage: true });
    halt();
    results.files.push(file);
    if (!gray) {
      const m = await measure(page, NAMES);
      halt();
      // Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
      // The down wires' pixels, from a full-page screenshot kept in memory,
      // taken with the animations stopped so a flowing down wire's dots sit still.
      if (view.expect === 'graph') {
        const shot = decodePng(await page.screenshot({ fullPage: true, animations: 'disabled' }));
        halt();
        for (const d of m.downs) if (d.drawn) d.dots = readDots(shot, d);
      }
      const jump = await jumpToZ(page);
      halt();
      results.rows.push(...judge(view, m, errors, jump));
      results.pill = m.pill;
      results.counts = { labels: m.labels.length, wires: m.wires, heads: m.heads.length };
    } else {
      results.rows.push(['grayscale page: no console errors', errors.length === 0, errors.join(' | ')]);
    }
    await page.close();
    halt();
  }
  return results;
}

/**
 * The check itself: mailbox, listeners, server, the down workers, then
 * each view. Every child is stopped by its own pid when it ends, when
 * anything throws (a failed browser close included) and on SIGTERM or
 * SIGINT. After a signal, check() stops at its next await (halt() throws
 * once cleanup has begun, and so does runView after each of its own) and
 * prints nothing more; the handler's exit code is 128 plus the signal.
 * @complexity see the module block  @alloc see the module block
 */
async function check(chromium) {
  const children = [];
  const listenerOf = new Map();
  let browser = null;
  let failed = 0;
  let cleaning = null;
  // Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
  // Before the finally only a signal starts cleanup, so a set `cleaning`
  // there means the run was stopped: halt() ends it at the next await.
  let signaled = false;
  const halt = () => {
    if (cleaning) throw new Error('stopped by a signal');
  };
  const cleanup = () => {
    if (!cleaning) {
      cleaning = (async () => {
        if (browser) {
          try {
            await Promise.race([browser.close(), sleep(STOP_MS).then(() => { throw new Error('browser close timed out'); })]);
          } catch (err) {
            failed += 1;
            say(`browser close failed: ${err.message}`);
          }
        }
        for (const child of [...children].reverse()) await stop(child);
        say(`stopped by pid: ${children.map((c) => c.pid).join(' ')}`);
      })();
    }
    return cleaning;
  };
  for (const name of SIGNALS) {
    process.once(name, () => {
      say(`\ncheck stopped by ${name}`);
      cleanup().finally(() => process.exit(SIGNAL_EXIT_BASE + constants.signals[name]));
    });
  }
  try {
    const { root, joined } = buildMailbox();
    say(`mailbox: ${root} (14 names, ${MAIL.length} messages; left in the temp folder)`);
    say(`cards: ${joined ? 'written by tc join' : 'written by hand in C1\'s shape (this tree\'s tc has no join)'}`);
    const proven = await startListeners(root, children, listenerOf);
    halt();
    say(`listeners proven by tc health: ${proven.join(' ')}`);
    const url = await startServer(root, children);
    halt();
    say(`serve.py: ${url} (pid ${children.at(-1).pid}; it ends by itself ${process.env[SERVE_LIMIT_ENV] || SERVE_LIMIT_S} s after start)`);
    // The mail was sent moments ago; aged now, none of it reads as waking
    // a down worker after the feed saw it listening (D24).
    freshen(root);
    const downPids = await makeDown(root, url, listenerOf);
    halt();
    say(`down workers: ${DOWN.join(', ')} (the feed saw their listeners; pids ${downPids.join(' ')} stopped; tc health shows none; `
      + 'the feed says down)');
    const shots = mkdtempSync(join(tmpdir(), 'tc-board-shots-'));
    browser = await chromium.launch({ headless: true, args: ['--password-store=basic'], handleSIGINT: false, handleSIGTERM: false, handleSIGHUP: false });
    halt();
    say(`browser: chromium ${browser.version()}`);
    const files = [];
    for (const view of VIEWS) {
      const r = await runView(browser, url, root, view, shots, halt);
      halt();
      say(`\n${view.width} x ${view.height}  pill "${r.pill}"  ${JSON.stringify(r.counts, null, SPACES_IN_JSON)}`);
      for (const [name, ok, detail] of r.rows) {
        if (!ok) failed += 1;
        say(`  ${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? `: ${detail}` : ''}`);
      }
      files.push(...r.files);
    }
    say(`\nscreenshots (not in the repo): ${shots}`);
    for (const f of files) say(`  ${f}`);
  } catch (err) {
    failed += 1;
    if (!cleaning) say(`check failed: ${err.message}`);
  } finally {
    signaled = !!cleaning;
    await cleanup();
  }
  if (signaled) return failed;
  say(failed ? `\nresult: FAIL (${failed})` : '\nresult: PASS');
  return failed;
}

// A stand-in for Playwright, written by the self-test as a CommonJS module.
// Its page load fails with the URL in the message and in a call log, as
// Playwright's goto does, or hangs; its browser close may throw. In
// 'launch-on-signal' mode its launch settles only when SIGTERM or SIGINT
// arrives, after check()'s own handler has begun cleanup, so the run's
// next step meets a stopping check.
const FAKE_PLAYWRIGHT = `
const mode = process.env.${FAKE_MODE_ENV};
exports.chromium = {
  async launch() {
    if (mode === 'launch-on-signal') {
      await new Promise((resolve) => { process.once('SIGTERM', resolve); process.once('SIGINT', resolve); });
    }
    return {
      version: () => 'fake (self-test)',
      async newPage() {
        return {
          on() {},
          async goto(url) {
            if (mode === 'hang') return new Promise(() => {});
            throw new Error('page.goto: net::ERR_CONNECTION_REFUSED at ' + url + '\\nCall log:\\n  - navigating to "' + url + '", waiting until "load"\\n');
          },
          async close() {},
        };
      },
      async close() {
        if (mode === 'close-error') throw new Error('browser.close: Target page, context or browser has been closed');
      },
    };
  },
};
`;

/**
 * True when a process with this pid is alive: it takes a signal and is not
 * a zombie waiting for its new parent to reap it (/proc/<pid>/stat says Z).
 * @complexity O(1)  @alloc one short string
 */
function alive(pid) {
  try {
    process.kill(pid, 0);
  } catch {
    return false;
  }
  try {
    const stat = readFileSync(`/proc/${pid}/stat`, 'utf8');
    return stat.slice(stat.lastIndexOf(')') + 2, stat.lastIndexOf(')') + 3) !== ZOMBIE_STATE;
  } catch {
    return false;
  }
}

/**
 * Run this file once as a child against the fake Playwright, in `mode`;
 * send `signal` once its output holds `sendOn` (by default, once it has a
 * browser), or kill it outright with SIGKILL, and wait for it to end.
 * @complexity one child run  @alloc its output
 * @returns {Promise<{ out, code, signal, pids: number[] }>}
 */
function selfRun(box, mode, signal, extraEnv = {}, sendOn = 'browser: ') {
  return new Promise((resolve) => {
    const child = spawn(process.execPath, [HERE], {
      env: envWith({ NODE_PATH: join(box, 'node_modules'), [FAKE_MODE_ENV]: mode, TMPDIR: box, ...extraEnv }),
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    let out = '';
    let sent = false;
    const ceiling = setTimeout(() => process.kill(child.pid, 'SIGKILL'), SELF_RUN_MS);
    const read = (chunk) => {
      out += chunk;
      if (signal && !sent && out.includes(sendOn)) {
        sent = true;
        process.kill(child.pid, signal);
      }
    };
    child.stdout.on('data', read);
    child.stderr.on('data', read);
    child.on('exit', (code, sig) => {
      clearTimeout(ceiling);
      const pids = [...out.matchAll(/\(pid (\d+);/g), ...out.matchAll(/ [a-z0-9]+:(\d+)/g)].map((m) => Number(m[1]));
      resolve({ out, code, signal: sig, pids: [...new Set(pids)] });
    });
  });
}

/**
 * --self-test: every promise about the token, the children and a stopped
 * run's output, kept with no browser. Seven runs of this file against a
 * fake Playwright.
 * @complexity seven child runs  @alloc one temp folder, left in place
 * @returns {Promise<number>}  how many checks failed
 */
async function selfTest() {
  const box = mkdtempSync(join(tmpdir(), 'tc-board-selftest-'));
  mkdirSync(join(box, 'node_modules', 'playwright'), { recursive: true });
  writeFileSync(join(box, 'node_modules', 'playwright', 'index.js'), FAKE_PLAYWRIGHT);
  say(`self-test: a fake playwright in ${box}`);
  let failed = 0;
  const report = (name, ok, detail) => {
    if (!ok) failed += 1;
    say(`  ${ok ? 'PASS' : 'FAIL'}  ${name}${ok ? '' : `: ${detail}`}`);
  };
  const cases = [
    { name: 'a page load that fails with the URL in its error', mode: 'goto-error' },
    { name: 'a browser close that throws', mode: 'close-error' },
    { name: 'SIGTERM while a page loads', mode: 'hang', signal: 'SIGTERM' },
    { name: 'SIGINT while a page loads', mode: 'hang', signal: 'SIGINT' },
    { name: 'SIGKILL while a page loads (serve.py ends at its own limit)', mode: 'hang', signal: 'SIGKILL',
      env: { [SERVE_LIMIT_ENV]: String(SELF_SERVE_LIMIT_S) } },
    // Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
    { name: 'SIGTERM while the browser starts', mode: 'launch-on-signal', signal: 'SIGTERM', sendOn: 'down workers: ' },
    { name: 'SIGINT while the browser starts', mode: 'launch-on-signal', signal: 'SIGINT', sendOn: 'down workers: ' },
  ];
  for (const c of cases) {
    const run = await selfRun(box, c.mode, c.signal, c.env, c.sendOn);
    const serve = run.out.match(/serve\.py: .*\(pid (\d+);/);
    if (c.signal === 'SIGKILL') await sleep(SELF_SERVE_LIMIT_S * MS_PER_S + SELF_GRACE_MS);
    const serveAlive = serve ? alive(Number(serve[1])) : true;
    const leftOver = run.pids.filter(alive);
    const unmasked = /token=(?!<hidden>)/.test(run.out);
    say(`\n${c.name}: exit ${run.code ?? run.signal}`);
    report('no token printed', !unmasked, 'an unmasked token= is in its output');
    if (c.mode === 'goto-error') {
      report('the failed page load was printed, masked', run.out.includes('check failed: page.goto') && run.out.includes('token=<hidden>'),
        'no masked error line');
    }
    if (c.signal === 'SIGKILL') {
      report('serve.py ended at its own limit', !!serve && !serveAlive,
        serve ? `serve.py pid ${serve[1]} outlived its ${SELF_SERVE_LIMIT_S} s limit` : 'serve.py never started');
    } else {
      report('serve.py started and is gone', !!serve && !serveAlive, serve ? `serve.py pid ${serve[1]} is still alive` : 'serve.py never started');
      report('every listener is gone', leftOver.length === 0, `still alive: ${leftOver.join(' ')}`);
      report('it says it stopped them by pid and ended in failure', run.out.includes('stopped by pid:') && run.code !== 0,
        `exit ${run.code}, ${run.out.includes('stopped by pid:') ? '' : 'no stopped by pid line'}`);
    }
    if (c.signal && c.signal !== 'SIGKILL') {
      // After the signal: the stop line and nothing else, and 128 plus the signal.
      const said = run.out.split(`check stopped by ${c.signal}`);
      const after = said.length > 1 ? said[1].split('\n').filter((line) => line.trim() && !line.startsWith('stopped by pid:')) : ['(no stop line)'];
      report('nothing printed after the signal but the stop line', after.length === 0, `printed after it: ${after.join(' | ')}`);
      report(`exit code ${SIGNAL_EXIT_BASE} plus ${c.signal}`, run.code === SIGNAL_EXIT_BASE + constants.signals[c.signal], `exit ${run.code ?? run.signal}`);
    }
    // Whatever a run left (a SIGKILL leaves its listeners), stopped by its own pid.
    for (const pid of run.pids.filter(alive)) process.kill(pid, 'SIGTERM');
  }
  say(failed ? `\nself-test: FAIL (${failed})` : '\nself-test: PASS');
  return failed;
}

if (process.argv.includes('--self-test')) {
  process.exit((await selfTest()) ? 1 : 0);
}
let chromium;
try {
  ({ chromium } = createRequire(import.meta.url)('playwright'));
} catch {
  say('skipped: playwright not found');
  process.exit(0);
}
process.exit((await check(chromium)) ? 1 : 0);
