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
 * The mail is sent with this tree's tc. Five listeners start with
 * `tc wait --timeout`, each proven by `tc health`; then `d`'s is seen by
 * the feed and stopped by its pid, so `d` is a down worker. It starts
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
 * not dotted or that another stroke lies on. It saves four screenshots
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
 * `--self-test` checks those promises without a browser: it runs this
 * script four times against a fake Playwright that it writes to a temp
 * folder (a page load that fails with the URL in its error, a browser close
 * that throws, a page load that hangs until SIGTERM, then SIGINT) and once
 * more killed outright under a short time limit, and fails if any run
 * prints a token or leaves serve.py or a listener alive.
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
 *             variables left out of a join; starts five `tc wait` children
 *             and one board/serve.py child and stops each by its own pid;
 *             asks serve.py's /feed twice with the token; starts one
 *             headless Chromium and closes it; sets file times on the
 *             mailbox's messages so the newest wires flow while the page is
 *             open; listens for SIGTERM and SIGINT. --self-test writes a
 *             fake playwright module to a temp folder, runs this file as a
 *             child five times, signals or kills three of them, and stops
 *             anything they left by its pid
 * @deps       Node 18+, Playwright (any recent version; 1.63 on the owner's
 *             machine), python3, ./tc, board/serve.py
 * @complexity O(v * (b^2 + w * s * b + o * s')) per view over b <= 14 boxes,
 *             w wires and s samples along each, and o strokes checked
 *             against the s' samples of the down wire; a run takes seconds
 *             (the self-test, five runs without a browser, tens of seconds)
 * @alloc      one browser, one page at a time, four screenshots on disk
 */
import { createRequire } from 'node:module';
import { spawn, execFileSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, writeFileSync, readdirSync, readFileSync, utimesSync } from 'node:fs';
import { tmpdir, constants } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

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
// wires flow (the feed's 10 s writing window) and carry labels: seven pairs,
// among them a wire between the two trees and one between the peers.
const FRESH_FROM_SEQ = 10;
// Every other message is set this old, past the writing window, so only
// the fresh ones flow and only their senders read writing.
const OLD_AGE_S = 600;
const MS_PER_S = 1000;
// d reads its mail too, since a `tc wait` with mail waiting exits at once.
const READERS = ['a', 'b', 'c', 'z', 'd'];
const LISTENERS = ['a', 'b', 'c', 'z', 'd'];
// The worker made down: its listener is seen by the feed, then stopped.
const DOWN = 'd';
const DOWN_EDGE = 'mailbox:b>d';
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
// Samples along the down wire, for the strokes that may lie on it.
const DOTTED_STEP_PX = 1;
// A stroke that crosses the down wire covers about its own width of it (2.5
// px at most); a run of the down wire longer than this inside another
// stroke means that stroke lies along it.
const CROSSING_MAX_PX = 6;
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
 * tree's tc has it, else written by hand), the mail, five readers' inboxes
 * read, and five status lines.
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
 * every older one OLD_AGE_S back, so it does not.
 * @complexity O(m) over m message files  @alloc one list of names
 */
function freshen(root) {
  const now = new Date();
  const old = new Date(now.getTime() - OLD_AGE_S * MS_PER_S);
  const mail = join(root, 'mail');
  for (const box of readdirSync(mail).filter((d) => d.startsWith('to-'))) {
    for (const where of [join(mail, box), join(mail, box, 'read')]) {
      for (const file of readdirSync(where).filter((f) => f.endsWith('.md'))) {
        const when = Number(file.slice(0, file.indexOf('-'))) >= FRESH_FROM_SEQ ? now : old;
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
 * Make DOWN a down worker the real way: the feed sees its listener, the
 * listener is stopped by its pid, tc health shows no pid, and the feed then
 * says down.
 * @complexity two feeds and O(PROOF_MS / PROOF_STEP_MS) health calls  @alloc two parsed feeds
 * @returns {Promise<number>}  the stopped listener's pid
 */
async function makeDown(root, url, listenerOf) {
  const seen = (await askFeed(url)).nodes.find((n) => n.id === DOWN);
  if (!seen || !seen.listener_pid) throw new Error(`the feed never saw ${DOWN} listening`);
  const child = listenerOf.get(DOWN);
  await stop(child);
  await healthUntil(root, (l) => !l[DOWN], `${DOWN}'s listener gone`);
  const after = (await askFeed(url)).nodes.find((n) => n.id === DOWN);
  if (!after || after.state !== 'down') throw new Error(`the feed says ${DOWN} is ${after && after.state}, not down`);
  return child.pid;
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
 * @complexity O(b^2 + w * s * b + o * s') in the page  @alloc one plain object
 */
function measure(page, names) {
  return page.evaluate(({ names, wireStep, insidePx, downEdge, dottedStep, crossMax }) => {
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
    // The down worker's wire: dotted, and no other stroke along it. Each
    // other stroke is tested solid (its dashes taken off for the test, then
    // put back), so a dashed wire on it cannot slip through its own gaps.
    out.dotted = null;
    const down = drawn.find((p) => p.dataset.edge === downEdge);
    if (down) {
      const dash = getComputedStyle(down).strokeDasharray;
      let worst = { run: 0, by: 'nothing' };
      const len = down.getTotalLength();
      for (const o of drawn) {
        if (o === down) continue;
        const kept = o.style.strokeDasharray;
        o.style.strokeDasharray = 'none';
        let run = 0;
        let longest = 0;
        for (let s = 0; s <= len; s += dottedStep) {
          const at = down.getPointAtLength(s);
          if (o.isPointInStroke(new DOMPoint(at.x, at.y))) longest = Math.max(longest, (run += dottedStep));
          else run = 0;
        }
        o.style.strokeDasharray = kept;
        if (longest > worst.run) worst = { run: longest, by: o.dataset.edge || o.getAttribute('class') };
      }
      out.dotted = {
        ok: down.classList.contains('down') && !!dash && dash !== 'none' && worst.run <= crossMax,
        detail: `class "${down.getAttribute('class')}", dasharray ${dash}; the longest stretch under another stroke is ${worst.run} px (${worst.by})`,
      };
    }
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
  }, { names, wireStep: WIRE_STEP_PX, insidePx: WIRE_INSIDE_PX, downEdge: DOWN_EDGE, dottedStep: DOTTED_STEP_PX, crossMax: CROSSING_MAX_PX });
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
    check(`the down worker's wire (${DOWN_EDGE}) is dotted and no other stroke lies on it`, !!m.dotted && m.dotted.ok,
      m.dotted ? m.dotted.detail : `no wire ${DOWN_EDGE} drawn`);
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
 * Open one view: color (measured and saved), then grayscale (saved).
 * @complexity two page loads  @alloc two pages, closed
 */
async function runView(browser, url, root, view, shots) {
  const results = { rows: [], files: [] };
  for (const gray of [false, true]) {
    freshen(root);
    const page = await browser.newPage({ viewport: { width: view.width, height: view.height } });
    const errors = [];
    page.on('console', (msg) => { if (msg.type() === 'error') errors.push(msg.text()); });
    page.on('pageerror', (err) => errors.push(String(err)));
    const [base, hash] = url.split('#');
    await page.goto(`${base}${gray ? '?gray=1' : ''}#${hash}`);
    await page.waitForSelector('.tc-node, .tc-row', { timeout: DRAWN_MS });
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(SETTLE_MS);
    const file = join(shots, `board-${view.label}-${gray ? 'gray' : 'color'}.png`);
    await page.screenshot({ path: file, fullPage: true });
    results.files.push(file);
    if (!gray) {
      const m = await measure(page, NAMES);
      const jump = await jumpToZ(page);
      results.rows.push(...judge(view, m, errors, jump));
      results.pill = m.pill;
      results.counts = { labels: m.labels.length, wires: m.wires, heads: m.heads.length };
    } else {
      results.rows.push(['grayscale page: no console errors', errors.length === 0, errors.join(' | ')]);
    }
    await page.close();
  }
  return results;
}

/**
 * The check itself: mailbox, listeners, server, the down worker, then each
 * view. Every child is stopped by its own pid when it ends, when anything
 * throws (a failed browser close included) and on SIGTERM or SIGINT.
 * @complexity see the module block  @alloc see the module block
 */
async function check(chromium) {
  const children = [];
  const listenerOf = new Map();
  let browser = null;
  let failed = 0;
  let cleaning = null;
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
    say(`listeners proven by tc health: ${proven.join(' ')}`);
    const url = await startServer(root, children);
    say(`serve.py: ${url} (pid ${children.at(-1).pid}; it ends by itself ${process.env[SERVE_LIMIT_ENV] || SERVE_LIMIT_S} s after start)`);
    const downPid = await makeDown(root, url, listenerOf);
    say(`down worker: ${DOWN} (the feed saw its listener; pid ${downPid} stopped; tc health shows none; the feed says down)`);
    const shots = mkdtempSync(join(tmpdir(), 'tc-board-shots-'));
    browser = await chromium.launch({ headless: true, args: ['--password-store=basic'], handleSIGINT: false, handleSIGTERM: false, handleSIGHUP: false });
    say(`browser: chromium ${browser.version()}`);
    const files = [];
    for (const view of VIEWS) {
      const r = await runView(browser, url, root, view, shots);
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
    say(`check failed: ${err.message}`);
  } finally {
    await cleanup();
  }
  say(failed ? `\nresult: FAIL (${failed})` : '\nresult: PASS');
  return failed;
}

// A stand-in for Playwright, written by the self-test as a CommonJS module.
// Its page load fails with the URL in the message and in a call log, as
// Playwright's goto does, or hangs; its browser close may throw.
const FAKE_PLAYWRIGHT = `
const mode = process.env.${FAKE_MODE_ENV};
exports.chromium = {
  async launch() {
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
 * send `signal` once it has a browser (or kill it outright with SIGKILL),
 * and wait for it to end.
 * @complexity one child run  @alloc its output
 * @returns {Promise<{ out, code, signal, pids: number[] }>}
 */
function selfRun(box, mode, signal, extraEnv = {}) {
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
      if (signal && !sent && out.includes('browser: ')) {
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
 * --self-test: every promise about the token and the children, kept with
 * no browser. Five runs of this file against a fake Playwright.
 * @complexity five child runs  @alloc one temp folder, left in place
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
  ];
  for (const c of cases) {
    const run = await selfRun(box, c.mode, c.signal, c.env);
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
