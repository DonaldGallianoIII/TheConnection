/**
 * Tests for layoutLevels in board/look.js over the D7 shapes, written as
 * feed JSON the way board/serve.py's feed() gives them (the values match
 * tests/test_board_feed.py's expectations): roots side by side in name
 * order, levels top to bottom, no two boxes overlapping, the cycle laid out,
 * and each title carrying its role word.
 *
 * Model: Claude Opus 5.5 (the BOARD lane agent), 2026-10-14. Status: unreviewed.
 *
 * @interacts  imports board/look.js; no DOM
 * @deps       node:test, node:assert (Node 18+)
 * @complexity O(n^2) per shape over n <= 8 nodes, for the pairwise overlap check
 * @alloc      the layouts, dropped at the end of each test
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { layoutLevels, roleTitle, fitTransform, CONFIG } from '../board/look.js';

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
  cycle: [n('p', 'orchestrator', 'declared', 0, 'q'), n('q', 'orchestrator', 'declared', 1, 'p')],
  ghost: [n('r', 'peer', 'inferred', 0, null, { reports_to: 'ghost' })],
  sharedWorker: [n('a', 'orchestrator', 'declared', 0, null), n('a2', 'worker', 'declared', 1, 'a'),
    n('b', 'worker', 'declared', 1, 'a'), n('x', 'orchestrator', 'inferred', 0, null),
    n('x1', 'worker', 'inferred', 1, 'x'), n('x2', 'worker', 'inferred', 1, 'x')],
};

function overlaps(p, q) {
  return p.x < q.x + CONFIG.NODE_W && q.x < p.x + CONFIG.NODE_W && p.y < q.y + CONFIG.NODE_H && q.y < p.y + CONFIG.NODE_H;
}

test('every shape lays out every node once, with no two boxes overlapping', () => {
  for (const [name, nodes] of Object.entries(SHAPES)) {
    const lay = layoutLevels({ nodes });
    assert.deepEqual(Object.keys(lay.pos).sort(), nodes.map((x) => x.id).sort(), name);
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
  assert.deepEqual(lay.rows, { a: 0, b: 1, c: 2, d: 2 });
  const ys = new Set(Object.values(lay.pos).map((p) => p.y));
  assert.equal(ys.size, 3);
  assert.ok(lay.pos.a.y < lay.pos.b.y && lay.pos.b.y < lay.pos.c.y);
  assert.equal(lay.pos.c.y, lay.pos.d.y);
});

test('the known-limit chain draws b on top with a, c and d under it', () => {
  const lay = layoutLevels({ nodes: SHAPES.chainNoHints });
  assert.deepEqual(lay.roots, ['b']);
  assert.deepEqual(lay.rows, { a: 1, b: 0, c: 1, d: 1 });
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
  assert.equal(fitTransform(10000, 10000, lay.extent, 24).k, 1);
  assert.equal(fitTransform(1, 1, lay.extent, 24).k, CONFIG.MIN_FIT_SCALE);
  const half = fitTransform(lay.extent.w / 2 + 24, 10000, lay.extent, 24);
  assert.ok(Math.abs(half.k - 0.5) < 1e-9, `k ${half.k}`);
});
