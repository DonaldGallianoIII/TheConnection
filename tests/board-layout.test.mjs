/**
 * Tests for layoutLevels in board/look.js over the D7 shapes, written as
 * feed JSON the way board/serve.py's feed() gives them (the values match
 * tests/test_board_feed.py's expectations): roots side by side in name
 * order, levels top to bottom, no two boxes overlapping, the cycle laid out,
 * and each title carrying its role word. Round 1 adds a2's legibility
 * check: fourteen names on a 1152 px desktop canvas and a 358 px phone
 * window, every box inside the width with no overlap and no text under
 * MIN_TEXT_PX, read against theme.css's own font sizes; and createFit,
 * which sizes the board from the ResizeObserver entry. Round 2 adds the
 * frame growing to the board, and on the 14-name feeds at both widths: no
 * wire or connector entering a node box, no label on a label or a box, a
 * parent's mail running down its connector, and two boxes in one row joined
 * straight across.
 *
 * Model: Claude Opus 5.5 (the BOARD lane agent), 2026-10-14. Status: unreviewed.
 *
 * @interacts  imports board/look.js; reads board/demo-script.json and
 *             board/theme.css as text; no DOM (a fake observer and kit)
 * @deps       node:test, node:assert, node:fs (Node 18+)
 * @complexity O(n^2) per shape over n <= 14 nodes, for the pairwise overlap
 *             check; O(r * p * n) for the runs over r runs of p points, and
 *             O(e^2 + e * n) for the labels over e labels
 * @alloc      the layouts, dropped at the end of each test
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  layoutLevels, layoutWidth, roleTitle, fitTransform, boardView, createBoard, createFit, levelPort, rootsList, outlineView,
  STATES, CONFIG,
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
  // Round 1: the floor is the scale at which the smallest board text is MIN_TEXT_PX.
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
// a2, for Donald (MEDIUM-1): the board reads at his real size, about 14
// names, on a desktop and on a phone. The canvas inside .tc-win at its
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
// The text drawn inside the board's view, so scaled with it (round 2 adds
// the headings over the trees).
const BOARD_TEXT = ['.tc-node-title', '.tc-node-role', '.tc-node-sub', '.tc-node-note', '.tc-wire-label', '.tc-head'];
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
  // Round 2, item 1: the frame grows to the board's height, so the page
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
// Round 2, items 2 and 3, from the architect's screenshots: wires looped
// through boxes and labels sat on each other and on node text. The
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

test('a parent\'s mail runs down its connector, port to port; two boxes side by side are joined straight across', () => {
  const view = boardView(ROUTED.mixed, layoutWidth(DESK_W));
  const wire = view.edges['mailbox:a>b'];
  assert.deepEqual(wire.points, view.nodes.b.connector.points, 'a\'s mail to b leaves the connector');
  assert.deepEqual(wire.points[0], levelPort(view.nodes.a.pos, 'out'), 'the wire does not leave a\'s out port');
  assert.deepEqual(wire.points.at(-1), levelPort(view.nodes.b.pos, 'in'), 'the wire does not reach b\'s in port');
  assert.deepEqual([wire.from, wire.back, wire.arrow], ['a', true, 'start'], 'b\'s reply to a does not point at a');
  const peers = view.edges['mailbox:p1>p2'];
  assert.equal(view.nodes.p1.pos.y, view.nodes.p2.pos.y, 'p1 and p2 are not in one row');
  assert.equal(peers.points.length, 2, `p1 to p2 bends: ${JSON.stringify(peers.points)}`);
  assert.equal(peers.points[0].y, peers.points[1].y, 'p1 to p2 is not level');
});

// Model: Claude Opus 5.5 (the BOARD fixer, round 2), 2026-10-14. Status: unreviewed.
// Round 2, item 5: the second orchestrator is reachable at a glance. A
// list of roots at the top, and a heading over each root's tree.

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

// a2's direction for the phone: the outline view, one row per session,
// indented by level under its parent, each tree headed by its root, then
// the recent traffic. The 14-name feed at 358 px.

test('the outline lists every session once, indented by level under its parent, each tree headed by its root', () => {
  const model = outlineView(ROUTED.mixed);
  const rows = model.groups.flatMap((g) => g.rows);
  assert.deepEqual(rows.map((r) => r.id).sort(), ROUTED.mixed.nodes.map((x) => x.id).sort(), 'a session is missing or twice');
  assert.deepEqual(model.groups.map((g) => g.root), ['a', 'p1', 'p2', 'z']);
  for (const g of model.groups) {
    assert.ok(g.heading.startsWith(`${g.root} · `), `group ${g.root} is headed "${g.heading}"`);
    assert.equal(g.rows[0].id, g.root, `group ${g.root} does not start with its root`);
  }
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
  report([{ contentRect: { width: CONFIG.OUTLINE_BELOW_PX, height: CANVAS_H } }]);
  assert.equal(mark.dataset.view, 'graph', `${CONFIG.OUTLINE_BELOW_PX} px does not draw the graph`);
  assert.equal(board.nodes.size, ROUTED.mixed.nodes.length);
  fit.jump('z');
  assert.deepEqual(revealed, [['outline', 'z'], ['graph', 'z']]);
  fit.stop();
});
