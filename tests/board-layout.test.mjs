/**
 * Tests for layoutLevels in board/look.js over the D7 shapes, written as
 * feed JSON the way board/serve.py's feed() gives them (the values match
 * tests/test_board_feed.py's expectations): roots side by side in name
 * order, levels top to bottom, no two boxes overlapping, the cycle laid out,
 * and each title carrying its role word. The board reads at the owner's
 * size: fourteen names on a 1152 px desktop canvas and a 358 px phone
 * window, every box inside the width with no overlap and no text under
 * MIN_TEXT_PX, read against theme.css's own font sizes; createFit sizes
 * the board from the ResizeObserver entry and grows its frame to the
 * board. On the 14-name feeds at both widths: no wire or connector
 * entering a node box, no label on a label or a box, and two boxes in one
 * row joined straight across. A parent's mail (or native line) runs beside
 * its connector and shares no piece of it, and two parents' connectors
 * share no piece (a relay over a relay whose workers wrap, at a 1180 px
 * window and a 700 px stage); the switch between graph and outline has two
 * breakpoints; the outline is brought up to date in place (a fake document
 * counts its writes) and heads no tree of one; the legend names the quiet
 * wire and the inferred thin line, and calls each patterned line what
 * theme.css draws; a down wire whose siblings' wires share its run is drawn
 * after every solid and dashed one, on a knockout in the canvas's face
 * (createKit on the fake document); a tree wire clears both port rings at
 * the widest node border; routes are searched once per routed pair and
 * never on a poll that only aged the mail, and 20 Claude peers on one
 * account draw within a time budget; and theme.css asks no other host.
 *
 * Model: Claude Opus 5.5 (the BOARD lane agent), 2026-10-14. Status: unreviewed.
 *
 * @interacts  imports board/look.js; reads board/demo-script.json,
 *             board/theme.css and board/serve.py as text, and looks for
 *             the font files in board/fonts/; no DOM (a fake observer, kit
 *             and document)
 * @deps       node:test, node:assert, node:fs (Node 18+)
 * @complexity O(n^2) per shape over n <= 14 nodes, for the pairwise overlap
 *             check; O(r * p * n) for the runs over r runs of p points, and
 *             O(e^2 + e * n) for the labels over e labels
 * @alloc      the layouts, dropped at the end of each test
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import {
  layoutLevels, layoutWidth, roleTitle, fitTransform, boardView, createBoard, createFit, createKit, levelPort, rootsList,
  outlineView, createCanvas, patchBoard, STATES, CONFIG, LEGEND_WORDS,
} from '../board/look.js';

/** One feed node with the fields the layout reads. @complexity O(1)  @alloc one object */
function n(id, role, source, level, parent, extra) {
  return { id, role, role_source: source, level, parent, state: 'idle', ...extra };
}

// The B1 shapes, as feed nodes (only the fields the layout reads).
const SHAPES = {
  star: [n('a', 'orchestrator', 'declared', 0, null), n('b', 'worker', 'declared', 1, 'a'),
    n('c', 'worker', 'declared', 1, 'a'), n('d', 'worker', 'declared', 1, 'a')],
  chain: [n('a', 'orchestrator', 'declared', 0, null), n('b', 'orchestrator', 'declared', 1, 'a'),
    n('c', 'worker', 'declared', 2, 'b'), n('d', 'worker', 'declared', 2, 'b')],
  chainNoHints: [n('a', 'worker', 'inferred', 1, 'b'), n('b', 'orchestrator', 'inferred', 0, null),
    n('c', 'worker', 'inferred', 1, 'b'), n('d', 'worker', 'inferred', 1, 'b')],
  sideBySide: [n('x', 'orchestrator', 'declared', 0, null), n('x1', 'worker', 'declared', 1, 'x'),
    n('x2', 'worker', 'declared', 1, 'x'), n('y', 'orchestrator', 'inferred', 0, null),
    n('y1', 'worker', 'inferred', 1, 'y'), n('y2', 'worker', 'inferred', 1, 'y')],
  // A cycle's root carries no parent: the walk used none for it (D15).
  cycle: [n('p', 'orchestrator', 'declared', 0, null), n('q', 'orchestrator', 'declared', 1, 'p')],
  ghost: [n('r', 'peer', 'inferred', 0, null, { reports_to: 'ghost' })],
  sharedWorker: [n('a', 'orchestrator', 'declared', 0, null), n('a2', 'worker', 'declared', 1, 'a'),
    n('b', 'worker', 'declared', 1, 'a'), n('x', 'orchestrator', 'inferred', 0, null),
    n('x1', 'worker', 'inferred', 1, 'x'), n('x2', 'worker', 'inferred', 1, 'x')],
};

/** True when two node boxes at p and q overlap. @complexity O(1)  @alloc none */
function overlaps(p, q) {
  return p.x < q.x + CONFIG.NODE_W && q.x < p.x + CONFIG.NODE_W && p.y < q.y + CONFIG.NODE_H && q.y < p.y + CONFIG.NODE_H;
}

test('every shape lays out every node once, with no two boxes overlapping', () => {
  for (const [name, nodes] of Object.entries(SHAPES)) {
    const lay = layoutLevels({ nodes });
    assert.deepEqual(Object.keys(lay.pos).sort(), nodes.map((x) => x.id).sort(), name);
    for (const [id, p] of Object.entries(lay.pos)) {
      assert.ok(Number.isFinite(p.x) && Number.isFinite(p.y), `${name}: ${id} at ${p.x}, ${p.y}`);
    }
    const ids = Object.keys(lay.pos);
    for (let i = 0; i < ids.length; i += 1) {
      for (let j = i + 1; j < ids.length; j += 1) {
        assert.ok(!overlaps(lay.pos[ids[i]], lay.pos[ids[j]]), `${name}: ${ids[i]} overlaps ${ids[j]}`);
      }
    }
  }
});

test('two roots sit side by side in name order, each tree clear of the other', () => {
  const lay = layoutLevels({ nodes: SHAPES.sideBySide });
  assert.deepEqual(lay.roots, ['x', 'y']);
  assert.equal(lay.pos.x.y, lay.pos.y.y, 'the two roots are not on one row');
  const right = (ids) => Math.max(...ids.map((id) => lay.pos[id].x + CONFIG.NODE_W));
  const left = (ids) => Math.min(...ids.map((id) => lay.pos[id].x));
  assert.ok(right(['x', 'x1', 'x2']) < left(['y', 'y1', 'y2']), 'x\'s tree runs into y\'s');
  for (const kid of ['y1', 'y2']) assert.ok(lay.pos[kid].y > lay.pos.y.y, `${kid} is not below y`);
});

test('a tree three levels deep stacks three rows, top to bottom', () => {
  const lay = layoutLevels({ nodes: SHAPES.chain });
  assert.deepEqual({ ...lay.rows }, { a: 0, b: 1, c: 2, d: 2 });
  const ys = new Set(Object.values(lay.pos).map((p) => p.y));
  assert.equal(ys.size, 3);
  assert.ok(lay.pos.a.y < lay.pos.b.y && lay.pos.b.y < lay.pos.c.y);
  assert.equal(lay.pos.c.y, lay.pos.d.y);
});

test('the known-limit chain draws b on top with a, c and d under it', () => {
  const lay = layoutLevels({ nodes: SHAPES.chainNoHints });
  assert.deepEqual(lay.roots, ['b']);
  assert.deepEqual({ ...lay.rows }, { a: 1, b: 0, c: 1, d: 1 });
});

test('the cycle feed lays out: p on top, q under it', () => {
  const lay = layoutLevels({ nodes: SHAPES.cycle });
  assert.deepEqual(lay.roots, ['p']);
  assert.ok(lay.pos.q.y > lay.pos.p.y);
});

test('a shared worker sits once, under its declared parent', () => {
  const lay = layoutLevels({ nodes: SHAPES.sharedWorker });
  assert.deepEqual(lay.roots, ['a', 'x']);
  assert.ok(lay.pos.b.x + CONFIG.NODE_W < lay.pos.x.x, 'b is not in a\'s tree');
});

test('each title carries its role word, and "· inferred" exactly when role_source says so', () => {
  for (const [name, nodes] of Object.entries(SHAPES)) {
    const lay = layoutLevels({ nodes });
    for (const node of nodes) {
      const title = lay.titles[node.id];
      assert.ok(title.startsWith(`${node.id} · ${node.role}`), `${name}: ${title}`);
      assert.equal(title.endsWith(' · inferred'), node.role_source === 'inferred', `${name}: ${title}`);
    }
  }
  assert.equal(roleTitle({ id: 'a', role: 'orchestrator', role_source: 'declared' }), 'a · orchestrator');
  assert.equal(roleTitle({ id: 'x', role: 'peer', role_source: 'inferred' }), 'x · peer · inferred');
});

test('an empty feed lays out nothing; fitTransform never enlarges or shrinks past its floor', () => {
  assert.deepEqual(layoutLevels({ nodes: [] }).extent, { w: 0, h: 0 });
  const lay = layoutLevels({ nodes: SHAPES.sideBySide });
  const big = fitTransform(10000, 10000, lay.extent, 24);
  assert.equal(big.k, 1);
  assert.equal(big.x, (10000 - lay.extent.w) / 2, 'a board that fits is not centered');
  assert.equal(fitTransform(1, 1, lay.extent, 24).k, CONFIG.MIN_FIT_SCALE);
  // The floor is the scale at which the smallest board text is MIN_TEXT_PX.
  assert.equal(CONFIG.MIN_FIT_SCALE, CONFIG.MIN_TEXT_PX / CONFIG.BOARD_TEXT_MIN_PX);
});

// Model: Claude Opus 5.5 (the BOARD lane agent), 2026-10-14. Status: unreviewed.
// B6: the demo script draws D7's shapes.
const DEMO = JSON.parse(readFileSync(new URL('../board/demo-script.json', import.meta.url), 'utf8'));

test('the demo holds two level 0 orchestrators and one level 1 orchestrator, side by side', () => {
  const orchestrators = (level) => DEMO.nodes.filter((x) => x.role === 'orchestrator' && x.level === level).map((x) => x.id);
  assert.deepEqual(orchestrators(0), ['a', 'z']);
  assert.deepEqual(orchestrators(1), ['b']);
  const lay = layoutLevels({ nodes: DEMO.nodes });
  assert.deepEqual(lay.roots, ['a', 'z']);
  assert.equal(lay.pos.a.y, lay.pos.z.y);
  assert.ok(lay.pos.a.x < lay.pos.z.x);
  for (const node of DEMO.nodes) {
    assert.ok(lay.titles[node.id].startsWith(`${node.id} · ${node.role}`), lay.titles[node.id]);
  }
});

test('the demo shows every state, every line kind, and a wire for every scripted message', () => {
  const states = new Set(DEMO.nodes.map((x) => x.state));
  for (const s of Object.keys(STATES).filter((name) => name !== 'writing')) assert.ok(states.has(s), `no ${s} node`);
  const writers = DEMO.script.map((s) => DEMO.nodes.find((x) => x.id === s.from));
  assert.ok(writers.some((x) => x.state !== 'listening'), 'no step shows a writing node');
  assert.deepEqual([...new Set(DEMO.links.map((l) => l.kind))].sort(), ['mailbox', 'native', 'reports_to']);
  const view = boardView({ nodes: DEMO.nodes, links: DEMO.links, wires: [] });
  const pairs = new Set(Object.values(view.edges).filter((e) => e.kind === 'mailbox').map((e) => [e.from, e.to].sort().join('>')));
  for (const s of DEMO.script) assert.ok(pairs.has([s.from, s.to].sort().join('>')), `no wire for ${s.from} to ${s.to}`);
});

// Model: Claude Opus 5.5 (the BOARD fixer, round 1), 2026-10-14. Status: unreviewed.
// The board reads at the owner's real size, about 14 names, on a desktop
// and on a phone. The canvas inside .tc-win at its
// 1180 px cap is 1152 px (theme.css: 1180 less two 1 px borders, 12 px body
// padding each side, and the canvas's 1 px borders). 358 is a 390 px phone
// less the page's two 16 px gutters. Height does not limit the scale: a
// tall board scrolls.
const DESK_W = 1152;
const PHONE_W = 358;
const CANVAS_H = 620;
// live.html's FIT_PADDING.
const FIT_PADDING = 24;
const FOURTEEN = {
  star: [n('hub', 'orchestrator', 'declared', 0, null),
    ...Array.from({ length: 13 }, (_, i) => n(`w${i + 1}`, 'worker', 'declared', 1, 'hub'))],
  peers: Array.from({ length: 14 }, (_, i) => n(`p${i + 1}`, 'peer', 'inferred', 0, null)),
};
// The text drawn inside the board's view, so scaled with it, the headings
// over the trees too.
const BOARD_TEXT = ['.tc-node-title', '.tc-node-role', '.tc-node-sub', '.tc-node-note', '.tc-node-badge', '.tc-wire-label', '.tc-head'];
const CSS = readFileSync(new URL('../board/theme.css', import.meta.url), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');

/**
 * Every rule in theme.css that sets a font-size in px, as [selector, px].
 * @complexity O(c) over c characters of theme.css  @alloc one list
 */
function fontSizes() {
  return [...CSS.matchAll(/([^{}]+)\{([^{}]*)\}/g)]
    .map(([, selector, body]) => [selector.trim(), body.match(/font-size:\s*([\d.]+)px/)])
    .filter(([, m]) => m)
    .map(([selector, m]) => [selector, Number(m[1])]);
}

/** The smallest font-size theme.css gives board text. @complexity O(c)  @alloc one list */
function smallestBoardText() {
  const sizes = fontSizes().filter(([selector]) => BOARD_TEXT.includes(selector)).map(([, px]) => px);
  assert.equal(sizes.length, BOARD_TEXT.length, `theme.css sets ${sizes.length} of the board's ${BOARD_TEXT.length} text sizes`);
  return Math.min(...sizes);
}

test('no font-size in theme.css is under MIN_TEXT_PX, and the board\'s smallest is BOARD_TEXT_MIN_PX', () => {
  const under = fontSizes().filter(([, px]) => px < CONFIG.MIN_TEXT_PX).map(([selector, px]) => `${selector} ${px}px`);
  assert.deepEqual(under, [], `under ${CONFIG.MIN_TEXT_PX} px: ${under.join('; ')}`);
  assert.equal(smallestBoardText(), CONFIG.BOARD_TEXT_MIN_PX);
});

test('fourteen names fit a desktop and a phone: inside the width, no overlap, no text under MIN_TEXT_PX', () => {
  const smallest = smallestBoardText();
  for (const [shape, nodes] of Object.entries(FOURTEEN)) {
    for (const width of [DESK_W, PHONE_W]) {
      const where = `${shape} at ${width} px`;
      const lay = layoutLevels({ nodes }, layoutWidth(width));
      const t = fitTransform(width, CANVAS_H, lay.extent, FIT_PADDING);
      const ids = Object.keys(lay.pos);
      assert.equal(ids.length, nodes.length, where);
      for (const id of ids) {
        const p = lay.pos[id];
        const left = t.x + p.x * t.k;
        const right = t.x + (p.x + CONFIG.NODE_W) * t.k;
        assert.ok(left >= 0 && right <= width, `${where}: ${id} runs from ${left} to ${right}`);
        assert.ok(p.y >= 0 && p.y + CONFIG.NODE_H <= lay.extent.h, `${where}: ${id} is outside the extent`);
      }
      for (let i = 0; i < ids.length; i += 1) {
        for (let j = i + 1; j < ids.length; j += 1) {
          assert.ok(!overlaps(lay.pos[ids[i]], lay.pos[ids[j]]), `${where}: ${ids[i]} overlaps ${ids[j]}`);
        }
      }
      assert.ok(t.k * smallest >= CONFIG.MIN_TEXT_PX, `${where}: the smallest text is drawn at ${t.k * smallest} px`);
    }
  }
  // On the phone a row holds one box, so the workers indent under the hub.
  const phone = layoutLevels({ nodes: FOURTEEN.star }, layoutWidth(PHONE_W));
  for (let i = 1; i <= 13; i += 1) {
    assert.equal(phone.pos[`w${i}`].x, phone.pos.hub.x + CONFIG.LAYOUT_INDENT, `w${i} is not indented under hub`);
  }
});

test('createFit takes the canvas size from the ResizeObserver entry, never from a layout read', () => {
  let report = null;
  class FakeObserver {
    constructor(callback) { report = callback; }
    observe() {}
    disconnect() {}
  }
  const noLayoutRead = () => { throw new Error('a layout read after a patch'); };
  const attrs = {};
  const canvas = {
    root: { getBoundingClientRect: noLayoutRead },
    frame: { style: {}, getBoundingClientRect: noLayoutRead },
    view: { style: {} },
    wires: { setAttribute(name, value) { attrs[name] = value; } },
  };
  const made = new Map();
  const kit = {
    createNode(v) {
      const handle = { view: v, update(next) { handle.view = next; }, remove() {} };
      made.set(v.id, handle);
      return handle;
    },
    createEdge() { return { update() {}, remove() {} }; },
  };
  const board = createBoard(kit);
  const fit = createFit(canvas, board, { padding: FIT_PADDING, Observer: FakeObserver });
  fit.start();
  fit.draw({ nodes: FOURTEEN.star, links: [], wires: [] });
  assert.equal(made.size, 0, 'it drew before the canvas had a size');
  report([{ contentRect: { width: DESK_W, height: CANVAS_H } }]);
  assert.equal(made.size, FOURTEEN.star.length);
  for (const [id, handle] of made) {
    assert.ok(handle.view.pos.x + CONFIG.NODE_W <= DESK_W, `${id} runs past the desktop's width`);
  }
  const { extent } = board.view;
  const t = fitTransform(DESK_W, extent.h + FIT_PADDING, extent, FIT_PADDING);
  assert.equal(canvas.view.style.transform, `translate(${t.x}px, ${t.y}px) scale(${t.k})`);
  assert.equal(t.k, 1, 'the board was shrunk');
  assert.equal(canvas.view.style.height, `${extent.h}px`);
  assert.equal(Number(attrs.height), extent.h, 'the wire layer is not the board\'s height');
  // Model: Claude Opus 5.5 (the BOARD fixer, round 2), 2026-10-14. Status: unreviewed.
  // The frame grows to the board's height, so the page
  // scrolls to every box; a height-only resize lays nothing out again.
  assert.equal(canvas.frame.style.height, `${extent.h + FIT_PADDING}px`, 'the frame does not grow to the board');
  const laidOut = board.view;
  report([{ contentRect: { width: DESK_W, height: extent.h + FIT_PADDING } }]);
  assert.equal(board.view, laidOut, 'a height-only resize laid the board out again');
  const deskHub = made.get('hub').view.pos;
  report([{ contentRect: { width: DESK_W - CONFIG.NODE_W, height: CANVAS_H } }]);
  assert.notDeepEqual(made.get('hub').view.pos, deskHub, 'a width change did not lay the board out again');
  fit.stop();
});

// Model: Claude Opus 5.5 (the BOARD fixer, round 2), 2026-10-14. Status: unreviewed.
// Wires once looped through boxes, and labels sat on each other and on
// node text. The
// 14-name feeds at the desktop and phone widths, with every pair's newest
// message fresh, so every mail wire flows and wants a label (the worst
// case for labels). `mixed` is the screenshot's own shape.

/** One feed node with an unread count, as serve.py gives it. @complexity O(1)  @alloc one object */
function fed(id, role, source, level, parent, extra) {
  return { ...n(id, role, source, level, parent), unread: 0, ...extra };
}

/**
 * A feed of `nodes` with one mailbox link per pair and a fresh message on
 * each, from the pair's first name to its second.
 * @complexity O(p) over p pairs  @alloc one feed
 */
function routedFeed(nodes, pairs) {
  return {
    nodes,
    links: pairs.map(([x, y]) => ({ from: x < y ? x : y, to: x < y ? y : x, kind: 'mailbox' })),
    wires: pairs.map(([x, y], i) => ({ from: x, to: y, seq: i + 1, age_s: 0 })),
  };
}

// Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
// The shape where two parents' connectors once ran down one gutter: a
// over b and x, b over b1 to b5. At a 1180 px window (DESK_W) and at a
// 700 px stage, b's workers wrap and so do a's children.
const RELAY = [
  fed('a', 'orchestrator', 'declared', 0, null), fed('b', 'orchestrator', 'declared', 1, 'a', { reports_to: 'a' }),
  fed('x', 'worker', 'declared', 1, 'a', { reports_to: 'a' }),
  ...Array.from({ length: 5 }, (_, i) => fed(`b${i + 1}`, 'worker', 'declared', 2, 'b', { reports_to: 'b' })),
];
const MID_W = 700;

const ROUTED = {
  mixed: routedFeed([
    fed('a', 'orchestrator', 'declared', 0, null), fed('b', 'orchestrator', 'declared', 1, 'a', { reports_to: 'a' }),
    ...['docs', 'e1', 'e2', 'e3'].map((id) => fed(id, 'worker', 'declared', 1, 'a', { reports_to: 'a' })),
    ...['c', 'd'].map((id) => fed(id, 'worker', 'declared', 2, 'b', { reports_to: 'b' })),
    fed('z', 'orchestrator', 'declared', 0, null),
    ...['y1', 'y2', 'y3'].map((id) => fed(id, 'worker', 'declared', 1, 'z', { reports_to: 'z' })),
    fed('p1', 'peer', 'inferred', 0, null), fed('p2', 'peer', 'inferred', 0, null),
  ], [['b', 'a'], ['a', 'docs'], ['c', 'b'], ['y1', 'z'], ['z', 'y2'], ['z', 'y3'], ['a', 'z'], ['a', 'e1'],
    ['a', 'e2'], ['a', 'e3'], ['p2', 'p1'], ['b', 'd']]),
  // The hub mails every worker, and three pairs of workers in different rows mail each other.
  star: routedFeed(FOURTEEN.star.map((x) => fed(x.id, x.role, x.role_source, x.level, x.parent)), [
    ...Array.from({ length: 13 }, (_, i) => ['hub', `w${i + 1}`]), ['w1', 'w13'], ['w2', 'w7'], ['w6', 'w12'],
  ]),
  // Neighbors, far ends, and pairs across rows.
  peers: routedFeed(FOURTEEN.peers.map((x) => fed(x.id, x.role, x.role_source, x.level, x.parent)), [
    ['p1', 'p2'], ['p1', 'p14'], ['p3', 'p9'], ['p5', 'p6'], ['p7', 'p13'], ['p2', 'p11'],
  ]),
  // Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
  // A relay whose worker is a relay too, and whose own workers wrap: a over
  // b and x, b over b1 to b5, so a and b each have a wrapped row.
  relay: routedFeed(RELAY, [['a', 'b'], ['a', 'x'], ...Array.from({ length: 5 }, (_, i) => ['b', `b${i + 1}`]), ['x', 'b5']]),
};
const ROUTE_WIDTHS = [DESK_W, PHONE_W];

/** A node's box from its view. @complexity O(1)  @alloc one object */
const boxOf = (v) => ({ x: v.pos.x, y: v.pos.y, w: CONFIG.NODE_W, h: CONFIG.NODE_H, id: v.id });

/** True when a level or upright piece from p to q enters the inside of box b. @complexity O(1)  @alloc none */
function pieceEnters(p, q, b) {
  if (p.y === q.y) return p.y > b.y && p.y < b.y + b.h && Math.max(p.x, q.x) > b.x && Math.min(p.x, q.x) < b.x + b.w;
  return p.x > b.x && p.x < b.x + b.w && Math.max(p.y, q.y) > b.y && Math.min(p.y, q.y) < b.y + b.h;
}

/** True when point p lies on box b's edge. @complexity O(1)  @alloc none */
function onEdge(p, b) {
  const inX = p.x >= b.x && p.x <= b.x + b.w;
  const inY = p.y >= b.y && p.y <= b.y + b.h;
  return (inX && (p.y === b.y || p.y === b.y + b.h)) || (inY && (p.x === b.x || p.x === b.x + b.w));
}

/** True when two label or node boxes overlap. @complexity O(1)  @alloc none */
function boxesOverlap(p, q) {
  return p.x < q.x + q.w && q.x < p.x + p.w && p.y < q.y + q.h && q.y < p.y + p.h;
}

/**
 * The first piece two runs have in common: two level pieces on one line, or
 * two upright ones, overlapping by more than a point. Null when none.
 * Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
 * @complexity O(p * q) over the two runs' pieces  @alloc one small object when found
 */
function sharedPiece(p, q) {
  for (let i = 1; i < p.length; i += 1) {
    for (let j = 1; j < q.length; j += 1) {
      const [a, b, c, d] = [p[i - 1], p[i], q[j - 1], q[j]];
      const upright = a.x === b.x && c.x === d.x && a.x === c.x;
      const level = a.y === b.y && c.y === d.y && a.y === c.y;
      if (!upright && !level) continue;
      const [u, v, s, t] = upright ? [a.y, b.y, c.y, d.y] : [a.x, b.x, c.x, d.x];
      const lo = Math.max(Math.min(u, v), Math.min(s, t));
      const hi = Math.min(Math.max(u, v), Math.max(s, t));
      if (hi > lo) return upright ? { x: a.x, y: [lo, hi] } : { y: a.y, x: [lo, hi] };
    }
  }
  return null;
}

/**
 * Every run on a board view, named: each edge's, and each node's connector.
 * @complexity O(n + e)  @alloc one list
 */
function runsOf(view) {
  return [
    ...Object.values(view.edges).map((e) => ({ name: e.id, points: e.points, from: e.from, to: e.to })),
    ...Object.values(view.nodes).filter((v) => v.connector).map((v) => ({
      name: `connector to ${v.id}`, points: v.connector.points, to: v.id,
    })),
  ];
}

test('no wire or connector enters a node box or a heading, on the 14-name feeds at desktop and phone widths', () => {
  for (const [shape, feed] of Object.entries(ROUTED)) {
    for (const width of ROUTE_WIDTHS) {
      const view = boardView(feed, layoutWidth(width));
      const boxes = Object.values(view.nodes).map(boxOf);
      const heads = Object.values(view.nodes).filter((v) => v.head).map((v) => ({ ...v.head, id: `${v.id}'s heading` }));
      const runs = runsOf(view);
      assert.ok(runs.length >= feed.links.length, `${shape} at ${width} px draws ${runs.length} runs`);
      for (const run of runs) {
        const where = `${shape} at ${width} px: ${run.name}`;
        assert.ok(run.points.length >= 2, `${where} has no run`);
        for (let i = 1; i < run.points.length; i += 1) {
          const [p, q] = [run.points[i - 1], run.points[i]];
          assert.ok(p.x === q.x || p.y === q.y, `${where}: a piece is neither level nor upright`);
          for (const b of [...boxes, ...heads]) assert.ok(!pieceEnters(p, q, b), `${where} enters ${b.id}`);
        }
        assert.ok(onEdge(run.points.at(-1), boxOf(view.nodes[run.to])), `${where} does not end on ${run.to}'s edge`);
        if (run.from) assert.ok(onEdge(run.points[0], boxOf(view.nodes[run.from])), `${where} does not start on ${run.from}'s edge`);
      }
    }
  }
});

test('no label overlaps another label, a node box or a heading, on the 14-name feeds at desktop and phone widths', () => {
  for (const [shape, feed] of Object.entries(ROUTED)) {
    for (const width of ROUTE_WIDTHS) {
      const where = `${shape} at ${width} px`;
      const view = boardView(feed, layoutWidth(width));
      const boxes = [...Object.values(view.nodes).map(boxOf), ...Object.values(view.nodes).filter((v) => v.head).map((v) => ({ ...v.head, id: `${v.id}'s heading` }))];
      const labeled = Object.values(view.edges).filter((e) => e.label);
      assert.equal(labeled.length, feed.links.length, `${where}: a flowing wire has no label words`);
      const placed = labeled.filter((e) => e.at);
      assert.ok(placed.length > 0, `${where}: no label was placed`);
      if (width === DESK_W && shape === 'mixed') assert.equal(placed.length, labeled.length, `${where}: a label was dropped`);
      for (const e of labeled) assert.ok(e.words.includes(e.label), `${where}: ${e.id}'s words lost its label`);
      for (let i = 0; i < placed.length; i += 1) {
        const at = placed[i].at;
        assert.ok(at.x >= 0 && at.y >= 0 && at.x + at.w <= view.extent.w && at.y + at.h <= view.extent.h, `${where}: ${placed[i].id}'s label leaves the board`);
        for (const b of boxes) assert.ok(!boxesOverlap(at, b), `${where}: ${placed[i].id}'s label "${placed[i].label}" is on ${b.id}`);
        for (let j = i + 1; j < placed.length; j += 1) {
          assert.ok(!boxesOverlap(at, placed[j].at), `${where}: "${placed[i].label}" is on "${placed[j].label}"`);
        }
      }
    }
  }
  // A quiet wire and a connector carry no label.
  const quiet = boardView({ ...ROUTED.mixed, wires: ROUTED.mixed.wires.map((w) => ({ ...w, age_s: CONFIG.FLOW_AGE_S + 1 })) }, layoutWidth(DESK_W));
  for (const e of Object.values(quiet.edges)) assert.deepEqual([e.label, e.at, e.flow, e.arrow], ['', null, false, null], `${e.id} is quiet but labeled`);
  for (const v of Object.values(quiet.nodes)) assert.ok(!v.connector || !('label' in v.connector), `${v.id}'s connector has a label`);
});

// Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
// A wire on its connector lost its dots and dashes under it: the down
// wire's `dotted: no listener` read solid. The wire now runs beside it.
test('a parent\'s mail runs beside its connector and shares no piece of it; two boxes side by side are joined straight across', () => {
  let checked = 0;
  for (const [shape, feed] of Object.entries(ROUTED)) {
    const parentOf = Object.fromEntries(feed.nodes.map((x) => [x.id, x.parent]));
    for (const width of ROUTE_WIDTHS) {
      const view = boardView(feed, layoutWidth(width));
      for (const e of Object.values(view.edges)) {
        if (parentOf[e.to] !== e.from) continue;
        checked += 1;
        const shared = sharedPiece(e.points, view.nodes[e.to].connector.points);
        assert.equal(shared, null, `${shape} at ${width} px: ${e.id} lies on its connector at ${JSON.stringify(shared)}`);
      }
    }
  }
  assert.ok(checked >= 2 * ROUTE_WIDTHS.length, `only ${checked} parent and child wires were checked`);
  const view = boardView(ROUTED.mixed, layoutWidth(DESK_W));
  const wire = view.edges['mailbox:a>b'];
  const out = levelPort(view.nodes.a.pos, 'out', view.nodes.a.h);
  const into = levelPort(view.nodes.b.pos, 'in');
  assert.deepEqual([wire.points[0].y, Math.abs(wire.points[0].x - out.x)], [out.y, CONFIG.TREE_WIRE_OFFSET],
    'a\'s mail to b does not leave a\'s bottom edge TREE_WIRE_OFFSET beside the out port');
  assert.deepEqual([wire.points.at(-1).y, Math.abs(wire.points.at(-1).x - into.x)], [into.y, CONFIG.TREE_WIRE_OFFSET],
    'a\'s mail to b does not reach b\'s top edge TREE_WIRE_OFFSET beside the in port');
  assert.deepEqual([wire.from, wire.back, wire.arrow], ['a', true, 'start'], 'b\'s reply to a does not point at a');
  // A native line on a parent and child with no mail runs beside their connector too.
  const pair = boardView({
    nodes: [fed('a', 'orchestrator', 'declared', 0, null, { kind: 'claude', account: 'home' }),
      fed('b', 'worker', 'declared', 1, 'a', { kind: 'claude', account: 'home', reports_to: 'a' })],
    links: [{ from: 'a', to: 'b', kind: 'native' }], wires: [],
  }, layoutWidth(DESK_W));
  assert.equal(sharedPiece(pair.edges['native:a>b'].points, pair.nodes.b.connector.points), null, 'the native line lies on the connector');
  const peers = view.edges['mailbox:p1>p2'];
  assert.equal(view.nodes.p1.pos.y, view.nodes.p2.pos.y, 'p1 and p2 are not in one row');
  assert.equal(peers.points.length, 2, `p1 to p2 bends: ${JSON.stringify(peers.points)}`);
  assert.equal(peers.points[0].y, peers.points[1].y, 'p1 to p2 is not level');
});

// Model: Claude Opus 5.5 (the P4 phase fixer), 2026-10-15. Status: unreviewed.
// Every poll ran the router again for every pair that is not parent and
// child, and Claude cards on one account make c(c-1)/2 native lines. The
// board now keeps its runs while the boxes and the drawn pairs stand, and
// lays nothing out on a poll that only aged the mail.
const ACCOUNT_OF = {
  a: 'acct1', b: 'acct1', docs: 'acct1', e1: 'acct1', e2: 'acct1', z: 'acct2', y1: 'acct2', y2: 'acct2', y3: 'acct2',
  c: 'acct3', d: 'acct3', e3: 'acct3', p1: 'acct3', p2: 'acct3',
};
// A time budget for the first draw of PEERS Claude cards on one account,
// every one of their native lines routed: about 150 ms on the owner's
// machine (2026-10-15), so this leaves room for a loaded one.
const FIRST_DRAW_BUDGET_MS = 2000;
const PEERS = 20;

/**
 * The 14-name mixed feed with every card Claude, on three accounts of 5, 4
 * and 5, and one native link for each pair on an account (26 in all).
 * @complexity O(n^2) over the 14 names  @alloc one feed
 */
function sharedFeed() {
  const nodes = ROUTED.mixed.nodes.map((x) => ({ ...x, kind: 'claude', account: ACCOUNT_OF[x.id] }));
  const ids = nodes.map((x) => x.id).sort();
  const native = ids.flatMap((p, i) => ids.slice(i + 1).filter((q) => ACCOUNT_OF[p] === ACCOUNT_OF[q])
    .map((q) => ({ from: p, to: q, kind: 'native' })));
  return { ...ROUTED.mixed, nodes, links: [...ROUTED.mixed.links, ...native] };
}

/** A drawing kit that counts its calls and draws nothing. @complexity O(1) per call  @alloc one handle per create */
function createCountingKit() {
  const kit = { calls: 0 };
  const handle = () => ({ update() { kit.calls += 1; }, remove() { kit.calls += 1; } });
  kit.createNode = () => { kit.calls += 1; return handle(); };
  kit.createEdge = () => { kit.calls += 1; return handle(); };
  return kit;
}

/** Each edge's run, by id. @complexity O(e) over e edges  @alloc one object */
const runsById = (view) => Object.fromEntries(Object.entries(view.edges).map(([id, e]) => [id, e.points]));

test('routes are searched once per routed pair, none on a poll that only aged the mail or stopped a flow, and draw as before', () => {
  const width = layoutWidth(DESK_W);
  const feed = sharedFeed();
  const parentOf = Object.fromEntries(feed.nodes.map((x) => [x.id, x.parent]));
  const kit = createCountingKit();
  const board = createBoard(kit);
  patchBoard(board, feed, width);
  const routed = Object.values(board.view.edges).filter((e) => parentOf[e.to] !== e.from && parentOf[e.from] !== e.to);
  assert.ok(routed.length >= 20, `only ${routed.length} routed pairs, so the shape tests little`);
  assert.equal(board.routes.searches, routed.length, 'not one search per routed pair');
  assert.deepEqual(runsById(board.view), runsById(boardView(feed, width)), 'the cached board draws other runs than boardView alone');
  // Every age up 3 s, a new `at`, no wire past FLOW_AGE_S: nothing is laid out.
  const aged = {
    ...feed, at: 'three seconds on', wires: feed.wires.map((w) => ({ ...w, age_s: w.age_s + 3 })),
    nodes: feed.nodes.map((x) => ({ ...x, last_mail_age_s: 3 })),
  };
  const [view, calls] = [board.view, kit.calls];
  const ops = patchBoard(board, aged, width);
  assert.equal(board.routes.searches, routed.length, 'a poll that only aged the mail searched a route');
  assert.equal(board.view, view, 'a poll that only aged the mail laid the board out again');
  assert.equal(kit.calls, calls, 'a poll that only aged the mail called the kit');
  for (const [name, list] of Object.entries(ops)) assert.deepEqual(list, [], name);
  // One wire past FLOW_AGE_S: its flow and words change, its run does not.
  const stopped = { ...aged, wires: aged.wires.map((w, i) => (i ? w : { ...w, age_s: CONFIG.FLOW_AGE_S + 1 })) };
  const changed = patchBoard(board, stopped, width);
  assert.equal(board.routes.searches, routed.length, 'a wire that stopped flowing set off a route search');
  assert.ok(changed.updateEdges.length > 0, 'the wire that stopped flowing was not redrawn');
  assert.deepEqual(runsById(board.view), runsById(boardView(stopped, width)), 'a reused run differs from a fresh search');
});

test('twenty Claude peers on one account draw every native line within FIRST_DRAW_BUDGET_MS, and the next poll searches none', (t) => {
  const nodes = Array.from({ length: PEERS }, (_, i) => fed(`s${i + 1}`, 'peer', 'inferred', 0, null, { kind: 'claude', account: 'work' }));
  const links = nodes.flatMap((p, i) => nodes.slice(i + 1).map((q) => ({ from: p.id, to: q.id, kind: 'native' })));
  const feed = { nodes, links, wires: [] };
  const board = createBoard(createCountingKit());
  const start = performance.now();
  patchBoard(board, feed, layoutWidth(DESK_W));
  const ms = performance.now() - start;
  t.diagnostic(`first draw of ${PEERS} peers on one account: ${ms.toFixed(0)} ms, ${board.routes.searches} route searches`);
  assert.equal(board.routes.searches, (PEERS * (PEERS - 1)) / 2, 'not one search per native line');
  assert.ok(ms <= FIRST_DRAW_BUDGET_MS, `the first draw took ${ms.toFixed(0)} ms, over ${FIRST_DRAW_BUDGET_MS}`);
  patchBoard(board, { ...feed, at: 'the next poll' }, layoutWidth(DESK_W));
  assert.equal(board.routes.searches, (PEERS * (PEERS - 1)) / 2, 'the next poll searched again');
});

// Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
// Two parents' connectors once ran down one gutter, so a top relay's
// worker read as its sub-relay's. Each wrapping block now has a lane.
test('every connector trunk serves one parent: a over b and x, b over b1 to b5, at a 1180 px window and a 700 px stage', () => {
  const parentOf = Object.fromEntries(RELAY.map((x) => [x.id, x.parent]));
  for (const width of [DESK_W, MID_W]) {
    const where = `at ${width} px`;
    const view = boardView({ nodes: RELAY, links: [], wires: [] }, layoutWidth(width));
    const lay = layoutLevels({ nodes: RELAY }, layoutWidth(width));
    assert.ok(lay.via.x.gutter !== null && lay.via.b5.gutter !== null, `${where}: a's or b's children do not wrap, so the shape tests nothing`);
    const conns = Object.values(view.nodes).filter((v) => v.connector).map((v) => ({ id: v.id, points: v.connector.points }));
    for (let i = 0; i < conns.length; i += 1) {
      for (let j = i + 1; j < conns.length; j += 1) {
        const [p, q] = [conns[i], conns[j]];
        if (parentOf[p.id] === parentOf[q.id]) continue;
        const shared = sharedPiece(p.points, q.points);
        assert.equal(shared, null, `${where}: the connector to ${p.id} (under ${parentOf[p.id]}) and to ${q.id} (under ${parentOf[q.id]}) share ${JSON.stringify(shared)}`);
      }
    }
  }
});

// Model: Claude Opus 5.5 (the BOARD fixer, round 2), 2026-10-14. Status: unreviewed.
// The second orchestrator is reachable at a glance: a list of roots at
// the top, and a heading over each root's tree.

test('the roots list names each root by role, orchestrators first, in words', () => {
  assert.deepEqual(rootsList(ROUTED.mixed), [
    { role: 'orchestrator', words: '2 orchestrators', ids: ['a', 'z'] },
    { role: 'peer', words: '2 peers', ids: ['p1', 'p2'] },
  ]);
  assert.deepEqual(rootsList(ROUTED.star), [{ role: 'orchestrator', words: '1 orchestrator', ids: ['hub'] }]);
  assert.deepEqual(rootsList({ nodes: [] }), []);
});

test('each root\'s tree starts with a heading naming its root, over the whole tree, clear of every box', () => {
  for (const width of [DESK_W, PHONE_W]) {
    const view = boardView(ROUTED.mixed, layoutWidth(width));
    const lay = layoutLevels(ROUTED.mixed, layoutWidth(width));
    const boxes = Object.values(view.nodes).map(boxOf);
    const sizes = { a: 8, z: 4, p1: 1, p2: 1 };
    for (const [id, v] of Object.entries(view.nodes)) {
      const where = `${id} at ${width} px`;
      if (!lay.roots.includes(id)) {
        assert.equal(v.head, null, `${where} is not a root but has a heading`);
        continue;
      }
      const words = sizes[id] > 1 ? `${roleTitle(ROUTED.mixed.nodes.find((x) => x.id === id))} · ${sizes[id]} sessions` : view.nodes[id].title;
      assert.equal(v.head.text, words, `${where}: heading`);
      assert.ok(v.head.y + v.head.h <= v.pos.y - CONFIG.PORT_SIZE / 2, `${where}: the heading is not over the root's box and port`);
      for (const b of boxes) assert.ok(!boxesOverlap(v.head, b), `${where}: the heading is on ${b.id}`);
    }
    // The tree under each heading: every box of a's tree sits inside a's heading's width.
    for (const id of ['a', 'b', 'docs', 'c', 'd', 'e1', 'e2', 'e3']) {
      const p = view.nodes[id].pos;
      const h = view.nodes.a.head;
      assert.ok(p.x >= h.x && p.x + CONFIG.NODE_W <= h.x + h.w, `${id} at ${width} px is outside a's heading`);
    }
  }
});

// On a phone the board draws the outline view, one row per session,
// indented by level under its parent, each tree headed by its root, then
// the recent traffic. The 14-name feed at 358 px.

test('the outline lists every session once, indented by level under its parent, each tree headed by its root', () => {
  const model = outlineView(ROUTED.mixed);
  const rows = model.groups.flatMap((g) => g.rows);
  assert.deepEqual(rows.map((r) => r.id).sort(), ROUTED.mixed.nodes.map((x) => x.id).sort(), 'a session is missing or twice');
  assert.deepEqual(model.groups.map((g) => g.root), ['a', 'p1', 'p2', 'z']);
  for (const g of model.groups) {
    // A tree of one session draws no heading: its one row says the same.
    if (g.rows.length === 1) assert.equal(g.heading, null, `the one-session tree ${g.root} is headed "${g.heading}"`);
    else assert.ok(g.heading.startsWith(`${g.root} · `), `group ${g.root} is headed "${g.heading}"`);
    assert.equal(g.rows[0].id, g.root, `group ${g.root} does not start with its root`);
  }
  assert.deepEqual(model.groups.filter((g) => g.heading === null).map((g) => g.root), ['p1', 'p2']);
  const level = Object.fromEntries(ROUTED.mixed.nodes.map((x) => [x.id, x.level]));
  for (const r of rows) assert.equal(r.depth, level[r.id], `${r.id} sits at depth ${r.depth}, level ${level[r.id]}`);
  // A parent comes before its children, and each child right under its own parent's subtree.
  const order = rows.map((r) => r.id);
  for (const x of ROUTED.mixed.nodes.filter((y) => y.parent)) {
    assert.ok(order.indexOf(x.parent) < order.indexOf(x.id), `${x.id} comes before its parent ${x.parent}`);
  }
  assert.deepEqual(order.slice(0, 4), ['a', 'b', 'c', 'd'], 'b\'s children do not follow b');
  const a = rows.find((r) => r.id === 'a');
  assert.deepEqual([a.role, a.glyph, a.word, a.unread], [' · orchestrator', STATES.idle.glyph, STATES.idle.word, '']);
  // The traffic: one line per pair, newest first, with its words.
  assert.equal(model.traffic.length, ROUTED.mixed.links.length);
  assert.deepEqual(model.traffic.map((t) => t.seq), [...model.traffic.map((t) => t.seq)].sort((x, y) => y - x), 'not newest first');
  assert.equal(model.traffic[0].text, 'b → d · #12 · 0 s ago');
});

test('createFit draws the outline under OUTLINE_BELOW_PX and the graph above it, and jumps to a root in either', () => {
  let report = null;
  class FakeObserver {
    constructor(callback) { report = callback; }
    observe() {}
    disconnect() {}
  }
  const outlines = [];
  const revealed = [];
  const kit = {
    createNode(v) { return { update() {}, remove() {}, reveal() { revealed.push(['graph', v.id]); } }; },
    createEdge() { return { update() {}, remove() {} }; },
    drawOutline(model) { outlines.push(model); },
    revealOutline(id) { revealed.push(['outline', id]); },
  };
  const canvas = { root: {}, frame: { style: {} }, view: { style: {} }, wires: { setAttribute() {} } };
  const mark = { dataset: {} };
  const board = createBoard(kit);
  const fit = createFit(canvas, board, { padding: FIT_PADDING, Observer: FakeObserver, mark });
  fit.start();
  fit.draw(ROUTED.mixed);
  report([{ contentRect: { width: PHONE_W, height: CANVAS_H } }]);
  assert.equal(fit.view, 'outline');
  assert.equal(mark.dataset.view, 'outline');
  assert.equal(board.nodes.size, 0, 'the phone drew the graph');
  assert.equal(outlines.length, 1);
  assert.deepEqual(outlines[0], outlineView(ROUTED.mixed));
  fit.draw(ROUTED.mixed);
  assert.equal(outlines.length, 1, 'an unchanged outline was drawn again');
  fit.jump('z');
  // From the outline, the graph comes back only at GRAPH_FROM_PX.
  report([{ contentRect: { width: CONFIG.OUTLINE_BELOW_PX, height: CANVAS_H } }]);
  assert.equal(mark.dataset.view, 'outline', `${CONFIG.OUTLINE_BELOW_PX} px flipped the outline back to the graph`);
  report([{ contentRect: { width: CONFIG.GRAPH_FROM_PX, height: CANVAS_H } }]);
  assert.equal(mark.dataset.view, 'graph', `${CONFIG.GRAPH_FROM_PX} px does not draw the graph`);
  assert.equal(board.nodes.size, ROUTED.mixed.nodes.length);
  fit.jump('z');
  assert.deepEqual(revealed, [['outline', 'z'], ['graph', 'z']]);
  fit.stop();
});

// Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
// Near the line, a classic scrollbar moved the stage across it with each
// view, so the page flipped every frame. Two breakpoints stop that.
test('the switch between graph and outline has two breakpoints, so a stage near the line never flips back', () => {
  let report = null;
  class FakeObserver {
    constructor(callback) { report = callback; }
    observe() {}
    disconnect() {}
  }
  const kit = {
    createNode() { return { update() {}, remove() {} }; },
    createEdge() { return { update() {}, remove() {} }; },
    drawOutline() {},
  };
  const mark = { dataset: {} };
  const fit = createFit({ root: {}, frame: { style: {} }, view: { style: {} }, wires: { setAttribute() {} } }, createBoard(kit),
    { padding: FIT_PADDING, Observer: FakeObserver, mark });
  fit.start();
  fit.draw(ROUTED.mixed);
  assert.ok(CONFIG.GRAPH_FROM_PX - CONFIG.OUTLINE_BELOW_PX > 17, 'the two breakpoints are no wider apart than a classic scrollbar');
  const scrollbar = 15;
  const seen = [];
  for (const width of [CONFIG.OUTLINE_BELOW_PX + 5, CONFIG.OUTLINE_BELOW_PX + 5 - scrollbar, CONFIG.OUTLINE_BELOW_PX + 5,
    CONFIG.OUTLINE_BELOW_PX + 5 - scrollbar, CONFIG.GRAPH_FROM_PX]) {
    report([{ contentRect: { width, height: CANVAS_H } }]);
    seen.push(`${width}:${mark.dataset.view}`);
  }
  const [a, b, c, d, e] = [CONFIG.OUTLINE_BELOW_PX + 5, CONFIG.OUTLINE_BELOW_PX + 5 - scrollbar, CONFIG.OUTLINE_BELOW_PX + 5,
    CONFIG.OUTLINE_BELOW_PX + 5 - scrollbar, CONFIG.GRAPH_FROM_PX];
  assert.deepEqual(seen, [`${a}:graph`, `${b}:outline`, `${c}:outline`, `${d}:outline`, `${e}:graph`],
    'a scrollbar coming and going flipped the view');
  fit.stop();
});

/**
 * A fake document for createKit's outline and its board: elements with
 * children, words and attributes, each counting the writes to its words,
 * so a test can tell an element kept from one made new, and words kept
 * from words written again. Attributes (an SVG element's class, d and
 * data-edge) live in `attrs`.
 * Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
 * @complexity O(1) per element, O(k) per insert over k siblings  @alloc one object per element
 */
function createFakeDoc() {
  const make = (tag) => {
    const e = {
      tag, className: '', dataset: {}, hidden: false, title: '', children: [], parentNode: null, writes: 0, text: '', scrolled: 0,
      attrs: {},
      style: { setProperty(name, value) { this[name] = value; } },
      setAttribute(name, value) { e.attrs[name] = String(value); },
      getAttribute(name) { return Object.hasOwn(e.attrs, name) ? e.attrs[name] : null; },
      removeAttribute(name) { delete e.attrs[name]; },
      get textContent() { return e.children.length ? e.children.map((c) => c.textContent).join('') : e.text; },
      set textContent(v) {
        e.writes += 1;
        for (const c of e.children) c.parentNode = null;
        e.children = [];
        e.text = String(v);
      },
      get firstChild() { return e.children[0] || null; },
      get nextSibling() { return e.parentNode ? e.parentNode.children[e.parentNode.children.indexOf(e) + 1] || null : null; },
      get lastElementChild() { return e.children.at(-1) || null; },
      append(...kids) { for (const k of kids) e.insertBefore(k, null); },
      insertBefore(k, ref) {
        if (k.parentNode) k.remove();
        const i = ref ? e.children.indexOf(ref) : -1;
        if (i < 0) e.children.push(k);
        else e.children.splice(i, 0, k);
        k.parentNode = e;
        return k;
      },
      remove() {
        if (!e.parentNode) return;
        e.parentNode.children.splice(e.parentNode.children.indexOf(e), 1);
        e.parentNode = null;
      },
      replaceChildren(...kids) {
        for (const c of [...e.children]) c.remove();
        e.append(...kids);
      },
      scrollIntoView() { e.scrolled += 1; },
    };
    return e;
  };
  return { createElement: make, createElementNS: (ns, tag) => make(tag) };
}

/** Every element under `e`, itself first, in order. @complexity O(n) over n elements  @alloc one list */
const everyEl = (e) => [e, ...e.children.flatMap(everyEl)];

// Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
// The phone's outline was rebuilt whenever a traffic age ticked, which
// lost a selection and a screen reader's place. C5 and C6: never rebuild.
test('the outline is brought up to date in place: an age tick rewrites only traffic words; a new session adds one row', () => {
  const doc = createFakeDoc();
  const canvas = { outline: doc.createElement('div') };
  const kit = createKit(doc, canvas);
  const aged = (age, feed = ROUTED.mixed) => ({ ...feed, wires: feed.wires.map((w) => ({ ...w, age_s: age })) });
  kit.drawOutline(outlineView(aged(3)));
  const before = everyEl(canvas.outline);
  const rows = before.filter((e) => e.className === 'tc-row' || e.className === 'tc-row nested');
  assert.equal(rows.length, ROUTED.mixed.nodes.length);
  for (const e of before) e.writes = 0;
  kit.drawOutline(outlineView(aged(6)));
  const after = everyEl(canvas.outline);
  assert.ok(after.length === before.length && after.every((e, i) => e === before[i]), 'an age tick made new elements or moved old ones');
  const written = after.filter((e) => e.writes > 0).map((e) => e.className);
  assert.ok(written.length > 0, 'the ages were not written');
  assert.deepEqual([...new Set(written)], ['tc-traffic-line'], `an age tick rewrote ${written.join(', ')}`);
  // A new worker under z: one new row, every other row kept.
  const grown = aged(6, { ...ROUTED.mixed, nodes: [...ROUTED.mixed.nodes, fed('y4', 'worker', 'declared', 1, 'z', { reports_to: 'z' })] });
  kit.drawOutline(outlineView(grown));
  const now = everyEl(canvas.outline).filter((e) => e.className === 'tc-row' || e.className === 'tc-row nested');
  assert.equal(now.length, rows.length + 1);
  assert.deepEqual(now.filter((e) => !rows.includes(e)).map((e) => e.children[0].children[0].textContent), ['y4']);
  // A tree of one session shows no heading; its jump goes to its row.
  const p1 = canvas.outline.children.find((g) => g.children.some((e) => e.className === 'tc-row' && e.children[0].children[0].textContent === 'p1'));
  assert.equal(p1.children[0].hidden, true, 'p1\'s tree of one draws a heading');
  kit.revealOutline('p1');
  assert.equal(p1.children[1].scrolled, 1, 'the jump to p1 did not reach its row');
});

// Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
test('the legend names the quiet mail wire and says the thin line may be inferred; a title keeps its space; a stale board stops its dashes', () => {
  assert.ok(LEGEND_WORDS.graph.includes(`thick line: mail, none in the last ${CONFIG.FLOW_AGE_S} s`), LEGEND_WORDS.graph);
  assert.ok(LEGEND_WORDS.graph.includes('thin line: reports to, or inferred from mail'), LEGEND_WORDS.graph);
  const rule = (selector) => [...CSS.matchAll(/([^{}]+)\{([^{}]*)\}/g)].find(([, sel]) => sel.trim() === selector);
  assert.match((rule('.tc-node-role') || [])[2] || '', /white-space:\s*pre/, 'the role words drop their leading space');
  assert.match((rule('.tc-win[data-conn="stale"] .tc-wire.flow') || [])[2] || '', /animation:\s*none/, 'a stale board keeps its dashes moving');
});

// Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
// Siblings' tree wires share the parent's end of their runs, so a quiet
// sibling's solid wire lay along a down worker's dotted one and filled its
// gaps: `dotted: no listener` read solid. A dotted or dashed wire is now
// drawn over every solid one, on a knockout in the canvas's own face.
const SIBLINGS = ['w1', 'w2', 'w3', 'w4'];

/**
 * A relay over w1 to w4, each mailed by it: long ago (a quiet wire) but w4
 * just now (a flowing one). w2 is in state `w2State`.
 * @complexity O(1)  @alloc one feed
 */
function siblingsFeed(w2State) {
  return {
    nodes: [fed('a', 'orchestrator', 'declared', 0, null),
      ...SIBLINGS.map((id) => fed(id, 'worker', 'declared', 1, 'a', { reports_to: 'a', state: id === 'w2' ? w2State : 'listening' }))],
    links: SIBLINGS.map((id) => ({ from: 'a', to: id, kind: 'mailbox' })),
    wires: SIBLINGS.map((id, i) => ({ from: 'a', to: id, seq: i + 1, age_s: id === 'w4' ? 0 : CONFIG.FLOW_AGE_S + 1 })),
  };
}

/** The body of theme.css's rule for exactly `selector`, or ''. @complexity O(c) over c characters  @alloc one list */
const cssRule = (selector) => ([...CSS.matchAll(/([^{}]+)\{([^{}]*)\}/g)].find(([, sel]) => sel.trim() === selector) || [])[2] || '';

test('a relay over w1 to w4 it has mailed, w2 down, at 1152 px: the down wire is drawn after every solid wire, on a knockout', () => {
  const width = layoutWidth(DESK_W);
  const view = boardView(siblingsFeed('down'), width);
  assert.equal(view.edges['mailbox:a>w2'].down, true, 'w2\'s wire is not down');
  assert.ok(sharedPiece(view.edges['mailbox:a>w2'].points, view.edges['mailbox:a>w1'].points),
    'a>w1 and a>w2 share no piece, so the shape tests nothing');
  const doc = createFakeDoc();
  const canvas = createCanvas(doc, doc.createElement('div'));
  const board = createBoard(createKit(doc, canvas));
  // Drawn with w2 listening first, then w2 goes down, as on a live board:
  // its wire was made before w3's and w4's, so creation order alone would
  // leave it under them.
  patchBoard(board, siblingsFeed('listening'), width);
  patchBoard(board, siblingsFeed('down'), width);
  // Every path that draws (a root's connector is an empty path), in paint order.
  const order = everyEl(canvas.wires).filter((e) => e.tag === 'path' && e.getAttribute('d') && /\btc-(wire|knockout)\b/.test(e.getAttribute('class') || ''));
  const name = (e) => e.getAttribute('data-edge') || e.getAttribute('class');
  const at = order.findIndex((e) => e.getAttribute('data-edge') === 'mailbox:a>w2');
  assert.match(order[at].getAttribute('class'), /\bdown\b/, 'w2\'s wire is not drawn dotted');
  const wires = order.filter((e) => /\btc-wire\b/.test(e.getAttribute('class')));
  const solid = wires.filter((e) => !/\b(flow|down|kind-native)\b/.test(e.getAttribute('class')));
  const dashed = wires.filter((e) => /\b(flow|kind-native)\b/.test(e.getAttribute('class')) && !/\bdown\b/.test(e.getAttribute('class')));
  assert.equal(solid.length, SIBLINGS.length + 2, `solid strokes: ${solid.map(name).join(', ')} (four connectors, a>w1 and a>w3)`);
  assert.deepEqual(dashed.map(name), ['mailbox:a>w4']);
  const over = [...solid, ...dashed].filter((e) => order.indexOf(e) > at).map(name);
  assert.deepEqual(over, [], `drawn over the down wire: ${over.join(', ')}`);
  const knock = order[at - 1];
  assert.ok(knock && /^tc-knockout\b/.test(knock.getAttribute('class')) && knock.getAttribute('d') === order[at].getAttribute('d'),
    'the down wire has no knockout right under it');
  // Each dashed wire has its own knockout; a solid one has none.
  assert.equal(order.filter((e) => /^tc-knockout\b/.test(e.getAttribute('class'))).length, 2, 'not one knockout per dotted or dashed wire');
  // theme.css paints the knockout in the canvas's own face, wider than its wire.
  const face = cssRule('.tc-canvas').match(/background:\s*([^;]+);/);
  assert.ok(face && cssRule('.tc-knockout').includes(`stroke: ${face[1].trim()}`), 'the knockout is not the canvas\'s own face');
  assert.match(cssRule('.tc-knockout'), /stroke-width:\s*calc\(var\(--tc-wire-w\) \+ var\(--tc-wire-w-knockout-pad\)\)/);
  assert.match(CSS, /--tc-wire-w-knockout-pad:\s*var\(--tc-wire-w\);/, 'the knockout is not one quiet wire wider than its wire');
});

// Model: Claude Opus 5.5 (the P4 phase fixer), 2026-10-15. Status: unreviewed.
// For a colorblind reader a line's dash pattern is the channel, so the
// legend's word for each patterned line names the pattern theme.css draws.
test('the legend calls each patterned line what theme.css draws: dash-dot for native, dotted for no listener', () => {
  const dashes = (selector) => (cssRule(selector).match(/stroke-dasharray:\s*([^;]+);/) || [])[1] || '';
  const shapeOf = (pattern) => {
    const v = pattern.trim().split(/\s+/).map(Number);
    if (v.length === 4 && v[0] > v[2]) return 'dash-dot';
    if (v.length === 2 && 2 * v[0] <= v[1]) return 'dotted';
    return `a pattern with no word (${pattern})`;
  };
  for (const [selector, means] of [['.tc-wire.kind-native', 'native'], ['.tc-wire.down', 'no listener']]) {
    const word = shapeOf(dashes(selector));
    assert.ok(LEGEND_WORDS.graph.includes(`${word}: ${means}`), `theme.css draws ${selector} as ${word}; the legend says: ${LEGEND_WORDS.graph}`);
  }
});

// Model: Claude Opus 5.5 (the P4 phase fixer), 2026-10-15. Status: unreviewed.
// D26: the board asks no host but its own. The browser check watches the
// page's requests; this is the same promise read from the files.
test('theme.css names no other host, and each face it names ships in board/fonts/ and is on serve.py\'s allow list', () => {
  assert.ok(!/@import/.test(CSS), 'theme.css imports another stylesheet');
  assert.ok(!/url\(\s*['"]?[a-z][a-z0-9+.-]*:/i.test(CSS), 'theme.css names a URL with a scheme');
  const urls = [...CSS.matchAll(/url\(\s*['"]?([^'")]+)['"]?\s*\)/g)].map((m) => m[1]);
  assert.equal(urls.length, 4, `theme.css names ${urls.length} files: ${urls.join(', ')}`);
  const serve = readFileSync(new URL('../board/serve.py', import.meta.url), 'utf8');
  for (const url of urls) {
    assert.match(url, /^fonts\/[a-z0-9-]+\.woff2$/, `${url} is not a face in board/fonts/`);
    assert.ok(existsSync(new URL(`../board/${url}`, import.meta.url)), `${url} is not in board/fonts/`);
    assert.ok(serve.includes(`"${url}": "font/woff2"`), `${url} is not on serve.py's allow list`);
  }
  for (const family of ['Space Grotesk', 'JetBrains Mono']) {
    assert.ok(CSS.includes(`font-family: '${family}'`), `no face for ${family}, which the stacks name`);
  }
});

// Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
// A port ring is placed from its box's padding edge, so its center sits one
// node border right of and below its port; at 8 px the east ring covered
// up to 3.25 px of a tree wire. The offset counts the widest border.
test('a tree wire clears both port rings at the widest node border theme.css sets', () => {
  const borders = [...CSS.matchAll(/([^{}]+)\{([^{}]*)\}/g)]
    .filter(([, sel]) => /^\.tc-node(\[[^\]]*\])?$/.test(sel.trim()))
    .map(([, , body]) => body.match(/border(?:-width)?:\s*([\d.]+)px/))
    .filter(Boolean)
    .map((m) => Number(m[1]));
  assert.ok(borders.length >= 2, `found ${borders.length} node border widths in theme.css`);
  const wire = Number(CSS.match(/--tc-wire-w:\s*([\d.]+)px/)[1]);
  const inner = CONFIG.TREE_WIRE_OFFSET - wire / 2;
  const ring = CONFIG.PORT_SIZE / 2 + Math.max(...borders);
  assert.ok(inner > ring, `a tree wire's inner edge is ${inner} px from its port and the east ring reaches ${ring} px`);
});
