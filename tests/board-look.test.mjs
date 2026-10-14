/**
 * Tests for the pure geometry in board/look.js.
 *
 * @interacts  imports board/look.js; no DOM needed for these functions
 * @deps       node:test, node:assert (Node 18+)
 * @complexity O(1) per test
 * @alloc      none retained
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { wirePath, portPoint, CONFIG, STATES } from '../board/look.js';

test('wirePath bends by half the span', () => {
  assert.equal(wirePath({ x: 0, y: 0 }, { x: 200, y: 50 }), 'M 0 0 C 100 0, 100 50, 200 50');
});

test('wirePath keeps a minimum bend on short wires', () => {
  const m = CONFIG.WIRE_MIN_BEND;
  assert.equal(wirePath({ x: 0, y: 0 }, { x: 10, y: 0 }), `M 0 0 C ${m} 0, ${10 - m} 0, 10 0`);
});

test('portPoint puts in on the left edge and out on the right, both mid-height', () => {
  const pos = { x: 40, y: 100 };
  assert.deepEqual(portPoint(pos, 'in'), { x: 40, y: 100 + CONFIG.NODE_H / 2 });
  assert.deepEqual(portPoint(pos, 'out'), { x: 40 + CONFIG.NODE_W, y: 100 + CONFIG.NODE_H / 2 });
});

test('every state has a glyph and a word, so none relies on color', () => {
  for (const [name, st] of Object.entries(STATES)) {
    assert.ok(st.glyph && st.glyph.length > 0, `${name} glyph`);
    assert.ok(st.word && st.word.length > 0, `${name} word`);
  }
  const glyphs = Object.values(STATES).map((s) => s.glyph);
  assert.equal(new Set(glyphs).size, glyphs.length, 'glyphs are distinct');
});
