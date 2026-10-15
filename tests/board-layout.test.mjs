/**
 * Tests for layoutLevels in board/look.js over the D7 shapes, written as
 * feed JSON the way board/serve.py's feed() gives them (the values match
 * tests/test_board_feed.py's expectations): roots side by side in name
 * order, levels top to bottom, no two boxes overlapping, the cycle laid out,
 * and each title carrying its role word. Round 1 adds a2's legibility
 * check: fourteen names on a 1152 px desktop canvas and a 358 px phone
 * window, every box inside the width with no overlap and no text under
 * MIN_TEXT_PX, read against theme.css's own font sizes; and createFit,
 * which sizes the board from the ResizeObserver entry.
 *
 * Model: Claude Opus 5.5 (the BOARD lane agent), 2026-10-14. Status: unreviewed.
 *
 * @interacts  imports board/look.js; reads board/demo-script.json and
 *             board/theme.css as text; no DOM (a fake observer and kit)
 * @deps       node:test, node:assert, node:fs (Node 18+)
 * @complexity O(n^2) per shape over n <= 14 nodes, for the pairwise overlap check
 * @alloc      the layouts, dropped at the end of each test
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  layoutLevels, layoutWidth, roleTitle, fitTransform, boardView, createBoard, createFit, STATES, CONFIG,
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
// The text drawn inside the board's view, so scaled with it.
const BOARD_TEXT = ['.tc-node-title', '.tc-node-role', '.tc-node-sub', '.tc-node-note', '.tc-wire-label'];
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
