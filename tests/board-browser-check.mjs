/**
 * board-browser-check.mjs: the live board in a real headless browser, at a
 * desktop and a phone size, measured against what the owner reads (round
 * 2's six items and a2's direction). Not part of `node --test` (its name
 * does not end .test.mjs): it needs Playwright and a browser, and starts a
 * server. Run it from the repo root:
 *
 *   NODE_PATH=<folder holding node_modules/playwright> node tests/board-browser-check.mjs
 *
 * It builds a throwaway mailbox in the system temp folder: 14 names in two
 * orchestrator trees and a pair of peers (cards written by hand in C1's
 * shape, since this tree's tc has no join; mail sent with this tree's tc;
 * four listeners started with `tc wait --timeout` and proven by
 * `tc health`). It starts board/serve.py on a port the OS picks, opens the
 * board at 1280 x 900 and 390 x 844, and fails on any of: a console error,
 * sideways scroll, drawn text under 11 px, a session missing from the view
 * the width selects (the graph on a desktop, the outline on a phone; a
 * name cut off by an ancestor that clips without scrolling counts as
 * missing),
 * overlapping session boxes, a window shorter than the viewport less its
 * margins, a wire label over another label, a node box or a tree heading, a
 * wire or connector through a node box, the legend not below the last
 * session, no list of roots (or a root link that does not bring its tree
 * into view), an ellipsis or cut words in the pill or the footer. It saves
 * four screenshots (each size in color and in grayscale) to a temp folder
 * it prints, never into the repo. It never prints the board's token.
 *
 * Without Playwright it prints `skipped: playwright not found` and exits
 * 0, so a fork without it is not broken.
 *
 * Model: Claude Opus 5.5 (the BOARD fixer, round 2), 2026-10-14. Status: unreviewed.
 *
 * @interacts  reads NODE_PATH (through require) for Playwright; makes two
 *             folders under the system temp folder (the mailbox and the
 *             screenshots) and leaves both there; runs this tree's ./tc
 *             (send, read, status, health) against that mailbox; starts four
 *             `tc wait` children and one board/serve.py child and stops each
 *             by its own pid in a finally block; starts one headless
 *             Chromium and closes it; sets file times on the mailbox's
 *             newest messages so their wires flow while the page is open
 * @deps       Node 18+, Playwright (any recent version; 1.63 on the owner's
 *             machine), python3, ./tc, board/serve.py
 * @complexity O(v * (b^2 + w * s * b)) per view over b <= 14 boxes, w
 *             wires and s samples along each wire; a run takes seconds
 * @alloc      one browser, one page at a time, four screenshots on disk
 */
import { createRequire } from 'node:module';
import { spawn, execFileSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, writeFileSync, readdirSync, utimesSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const REPO = join(dirname(fileURLToPath(import.meta.url)), '..');
const TC = join(REPO, 'tc');
const SERVE = join(REPO, 'board', 'serve.py');

// The owner's real board is about 14 names: two orchestrator trees (b is a
// relay under a) and two peers. [name, reports_to].
const CARDS = [
  ['a', null], ['b', 'a'], ['docs', 'a'], ['c', 'b'], ['d', 'b'], ['e1', 'a'], ['e2', 'a'], ['e3', 'a'],
  ['z', null], ['y1', 'z'], ['y2', 'z'], ['y3', 'z'], ['p1', null], ['p2', null],
];
const NAMES = CARDS.map(([name]) => name);
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
const READERS = ['a', 'b', 'c', 'z'];
const LISTENERS = ['a', 'b', 'c', 'z'];
// A listener outlives the run on its own if the finally block never ran.
const LISTEN_TIMEOUT_S = 120;
// A made-up join time, so no card carries the clock.
const JOINED_AT = '2026-10-14T12:00:00-05:00';

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
// Setup and settle times. The page polls every 3 s and draws the first
// answer at once; fonts may come from the network.
const SERVER_START_MS = 10000;
const PROOF_MS = 5000;
const PROOF_STEP_MS = 100;
const DRAWN_MS = 10000;
const SETTLE_MS = 800;
const STOP_MS = 5000;
const SPACES_IN_JSON = 0;

/** Run ./tc with the mailbox in the env and return its stdout. @complexity one child  @alloc its output */
function tc(root, args) {
  return execFileSync('python3', [TC, ...args], { env: { ...process.env, TC_ROOT: root }, encoding: 'utf8' });
}

/** A promise that settles after ms. @complexity O(1)  @alloc one timer */
const sleep = (ms) => new Promise((resolve) => { setTimeout(resolve, ms); });

/**
 * The throwaway mailbox: cards in C1's shape, the mail, four readers'
 * inboxes read, and four status lines.
 * @complexity O(names + mail) tc calls  @alloc the folder, left in place
 */
function buildMailbox() {
  const root = mkdtempSync(join(tmpdir(), 'tc-board-check-'));
  mkdirSync(join(root, 'cards'));
  for (const [name, reportsTo] of CARDS) {
    const card = {
      version: 1, name, kind: 'claude', account: `acct-${name}`, route: 'local', session_id: null, pid: null,
      thread_id: null, ssh: null, reports_to: reportsTo, joined_at: JOINED_AT,
    };
    writeFileSync(join(root, 'cards', `${name}.json`), `${JSON.stringify(card, null, 2)}\n`);
  }
  for (const [from, to] of MAIL) tc(root, ['send', '--from', from, '--to', to, `step for ${to}`]);
  for (const name of READERS) tc(root, ['read', name]);
  for (const name of LISTENERS) tc(root, ['status', name, `working on step ${name}`]);
  return root;
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
 * Start the four listeners and wait until tc health names each one's pid.
 * @complexity O(PROOF_MS / PROOF_STEP_MS) health calls  @alloc four children
 */
async function startListeners(root, children) {
  for (const name of LISTENERS) {
    children.push(spawn('python3', [TC, 'wait', name, '--timeout', String(LISTEN_TIMEOUT_S)], {
      env: { ...process.env, TC_ROOT: root }, stdio: 'ignore',
    }));
  }
  const until = Date.now() + PROOF_MS;
  while (Date.now() < until) {
    const { listeners } = JSON.parse(tc(root, ['health', '--json']));
    if (LISTENERS.every((name) => listeners[name])) return LISTENERS.map((name) => `${name}:${listeners[name]}`);
    await sleep(PROOF_STEP_MS);
  }
  throw new Error('tc health never named all four listeners');
}

/**
 * Start serve.py on a port the OS picks and read the URL it prints.
 * @complexity O(1)  @alloc one child
 */
function startServer(root, children) {
  const child = spawn('python3', [SERVE, '--port', '0'], { env: { ...process.env, TC_ROOT: root }, stdio: ['ignore', 'pipe', 'pipe'] });
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

/** The URL with its token hidden, for printing. @complexity O(1)  @alloc one string */
const masked = (url) => url.replace(/token=[^&]*/, 'token=<hidden>');

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
 * @complexity O(b^2 + w * s * b) in the page  @alloc one plain object
 */
function measure(page, names) {
  return page.evaluate(({ names, wireStep, insidePx }) => {
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
    for (const p of document.querySelectorAll('path.tc-wire')) {
      if (!visible(p) || !p.getAttribute('d')) continue;
      out.wires += 1;
      const ctm = p.getScreenCTM();
      const len = p.getTotalLength();
      for (let s = 0; s <= len; s += wireStep) {
        const q = new DOMPoint(p.getPointAtLength(s).x, p.getPointAtLength(s).y).matrixTransform(ctm);
        const hit = nodes.find((n) => q.x > n.left + insidePx && q.x < n.right - insidePx && q.y > n.top + insidePx && q.y < n.bottom - insidePx);
        if (hit) { out.wireHits.push(`${p.dataset.edge || p.getAttribute('class')} through ${hit.name}`); break; }
      }
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
  }, { names, wireStep: WIRE_STEP_PX, insidePx: WIRE_INSIDE_PX });
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

let chromium;
try {
  ({ chromium } = createRequire(import.meta.url)('playwright'));
} catch {
  console.log('skipped: playwright not found');
  process.exit(0);
}

const children = [];
let browser = null;
let failed = 0;
try {
  const root = buildMailbox();
  console.log(`mailbox: ${root} (14 names, ${MAIL.length} messages; left in the temp folder)`);
  const proven = await startListeners(root, children);
  console.log(`listeners proven by tc health: ${proven.join(' ')}`);
  const url = await startServer(root, children);
  console.log(`serve.py: ${masked(url)} (pid ${children.at(-1).pid})`);
  const shots = mkdtempSync(join(tmpdir(), 'tc-board-shots-'));
  browser = await chromium.launch({ headless: true, args: ['--password-store=basic'] });
  console.log(`browser: chromium ${browser.version()}`);
  const files = [];
  for (const view of VIEWS) {
    const r = await runView(browser, url, root, view, shots);
    console.log(`\n${view.width} x ${view.height}  pill "${r.pill}"  ${JSON.stringify(r.counts, null, SPACES_IN_JSON)}`);
    for (const [name, ok, detail] of r.rows) {
      if (!ok) failed += 1;
      console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? `: ${detail}` : ''}`);
    }
    files.push(...r.files);
  }
  console.log(`\nscreenshots (not in the repo): ${shots}`);
  for (const f of files) console.log(`  ${f}`);
} catch (err) {
  failed += 1;
  console.log(`check failed: ${err.message}`);
} finally {
  if (browser) await browser.close();
  for (const child of children.reverse()) await stop(child);
  console.log(`stopped by pid: ${children.map((c) => c.pid).join(' ')}`);
}
console.log(failed ? `\nresult: FAIL (${failed})` : '\nresult: PASS');
process.exit(failed ? 1 : 0);
