/**
 * Tests for the live board's diff and patch in board/look.js: patchBoard
 * keeps what stays, removes what went and adds what came, through a fake
 * drawing kit, so no DOM library is needed. Also the two new states, what
 * boardView draws for a feed's wires and links, and the pill's words. Round
 * 1 adds names that are Object.prototype keys, a pair with a mailbox wire
 * and a native line, and a down node's stale status.
 *
 * Model: Claude Opus 5.5 (the BOARD lane agent), 2026-10-14. Status: unreviewed.
 *
 * @interacts  imports board/look.js; no DOM
 * @deps       node:test, node:assert (Node 18+)
 * @complexity O(n + l) per test over a handful of nodes and links
 * @alloc      one board and one fake kit per test, dropped at its end
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  STATES, NOTE_WORDS, boardView, diffBoard, createBoard, patchBoard, pillText, layoutLevels, labelPoints, CONFIG,
} from '../board/look.js';

/**
 * A fake drawing kit: counts create calls and keeps every live handle.
 * @complexity O(1) per call  @alloc one handle per create, dropped on remove()
 */
function fakeKit() {
  const kit = {
    created: { nodes: 0, edges: 0 },
    live: new Set(),
    make(kind, v) {
      kit.created[kind] += 1;
      const handle = {
        view: v,
        removed: false,
        update(next) { handle.view = next; },
        remove() { handle.removed = true; kit.live.delete(handle); },
      };
      kit.live.add(handle);
      return handle;
    },
    createNode(v) { return kit.make('nodes', v); },
    createEdge(v) { return kit.make('edges', v); },
  };
  return kit;
}

/** One feed node, a listening peer unless `extra` says otherwise. @complexity O(1)  @alloc one object */
function node(id, extra) {
  return { id, state: 'listening', role: 'peer', role_source: 'inferred', level: 0, parent: null, unread: 0, ...extra };
}

/** One mailbox link between two names. @complexity O(1)  @alloc one object */
function mailbox(from, to) {
  return { from, to, kind: 'mailbox', sent: { [from]: 1, [to]: 1 }, last_age_s: 60 };
}

// Feed A: a over b and c, and x on its own.
const FEED_A = {
  nodes: [
    node('a', { role: 'orchestrator', role_source: 'declared' }),
    node('b', { role: 'worker', role_source: 'declared', level: 1, parent: 'a' }),
    node('c', { role: 'worker', role_source: 'declared', level: 1, parent: 'a' }),
    node('x'),
  ],
  wires: [],
  links: [mailbox('a', 'b'), mailbox('a', 'c')],
};

// Feed B: c gone, d new beside a, so x moves right; one new wire a to d.
const FEED_B = {
  nodes: [
    node('a', { role: 'orchestrator', role_source: 'declared' }),
    node('b', { role: 'worker', role_source: 'declared', level: 1, parent: 'a' }),
    node('d'),
    node('x'),
  ],
  wires: [{ from: 'a', to: 'd', seq: 7, age_s: 1 }],
  links: [mailbox('a', 'b'), mailbox('a', 'd')],
};

test('the two new states have a glyph and a word, distinct from the other four', () => {
  for (const name of ['doorbell', 'remote']) {
    assert.ok(STATES[name], `no state ${name}`);
    assert.ok(STATES[name].glyph && STATES[name].word, `${name} needs a glyph and a word`);
  }
  assert.equal(STATES.doorbell.glyph, '◎');
  assert.equal(STATES.remote.glyph, '⇄');
  assert.equal(STATES.remote.word, 'remote · not checked');
  const glyphs = Object.values(STATES).map((s) => s.glyph);
  const words = Object.values(STATES).map((s) => s.word);
  assert.equal(Object.keys(STATES).length, 6);
  assert.equal(new Set(glyphs).size, glyphs.length, `glyphs repeat: ${glyphs}`);
  assert.equal(new Set(words).size, words.length, `words repeat: ${words}`);
});

test('patchBoard keeps what stays, drops what went, adds what came, and rebuilds nothing', () => {
  const kit = fakeKit();
  const board = createBoard(kit);
  patchBoard(board, FEED_A);
  assert.deepEqual(kit.created, { nodes: 4, edges: 2 });
  const kept = { a: board.nodes.get('a'), b: board.nodes.get('b'), x: board.nodes.get('x') };
  const wireAB = board.edges.get('mailbox:a>b');
  const gone = board.nodes.get('c');
  const xBefore = kept.x.view.pos;

  const ops = patchBoard(board, FEED_B);

  for (const [id, handle] of Object.entries(kept)) {
    assert.equal(board.nodes.get(id), handle, `${id} is a new object: the board was rebuilt`);
  }
  assert.equal(board.edges.get('mailbox:a>b'), wireAB, 'the kept wire is a new object');
  assert.equal(board.nodes.has('c'), false);
  assert.equal(gone.removed, true, 'the removed node was never taken off the canvas');
  assert.equal(board.edges.has('mailbox:a>c'), false);
  assert.ok(board.nodes.get('d'), 'the new node is missing');
  assert.ok(board.edges.get('mailbox:a>d'), 'the new wire is missing');
  assert.deepEqual(kit.created, { nodes: 5, edges: 3 }, 'feed B made more than one node and one wire');
  assert.notDeepEqual(kept.x.view.pos, xBefore, 'x did not move');
  assert.ok(ops.updateNodes.some((v) => v.id === 'x'));
  assert.equal(kit.live.size, board.nodes.size + board.edges.size);
});

test('diffBoard of a view against itself is empty', () => {
  const view = boardView(FEED_B);
  const ops = diffBoard(view, boardView(FEED_B));
  for (const [name, list] of Object.entries(ops)) assert.deepEqual(list, [], name);
});

test('a fresh wire flows toward its reader with its words; an old one is quiet', () => {
  const fresh = boardView(FEED_B).edges['mailbox:a>d'];
  assert.equal(fresh.flow, true);
  assert.equal(fresh.label, 'a → d · #7');
  assert.equal(fresh.arrow, fresh.back ? 'start' : 'end');
  assert.equal(fresh.to === 'd', !fresh.back, 'the arrow is not at the reader');
  const old = boardView({ ...FEED_B, wires: [{ from: 'a', to: 'd', seq: 7, age_s: CONFIG.FLOW_AGE_S + 1 }] });
  assert.equal(old.edges['mailbox:a>d'].flow, false);
  assert.equal(old.edges['mailbox:a>d'].label, '');
  assert.equal(old.edges['mailbox:a>d'].arrow, null);
});

test('a reply flows back: the arrow sits at the start, at the reader', () => {
  const view = boardView({ ...FEED_A, wires: [{ from: 'b', to: 'a', seq: 9, age_s: 0 }] });
  const wire = view.edges['mailbox:a>b'];
  assert.equal(wire.from, 'a', 'a is above b, so the wire runs a to b');
  assert.deepEqual([wire.flow, wire.back, wire.arrow, wire.label], [true, true, 'start', 'b → a · #9']);
});

test('hint lines carry words: reports to, native, and a reports_to that names nobody', () => {
  const view = boardView({
    nodes: [
      node('a', { role: 'orchestrator', role_source: 'declared' }),
      node('b', { role: 'worker', role_source: 'declared', level: 1, parent: 'a', reports_to: 'a' }),
      node('r', { reports_to: 'ghost', status: 'reviewing' }),
      node('z', { state: 'down', status: 'gone quiet' }),
    ],
    wires: [],
    links: [
      { from: 'b', to: 'a', kind: 'reports_to' }, { from: 'r', to: 'ghost', kind: 'reports_to' },
      { from: 'a', to: 'b', kind: 'native' }, mailbox('a', 'z'),
    ],
  });
  const hint = view.edges['reports_to:b>a'];
  assert.deepEqual([hint.label, hint.arrow], ['reports to', 'end']);
  assert.ok(hint.a.y > hint.b.y, 'the hint runs up from the child to its parent');
  assert.equal(view.edges['native:a>b'].label, 'native · not observed');
  assert.equal(view.edges['reports_to:r>ghost'], undefined, 'a line to a node that is not there');
  assert.equal(view.nodes.r.note, 'reports to ghost · not found');
  assert.equal(view.nodes.z.note, 'last status: gone quiet', 'a down node shows its status as current');
  assert.equal(view.edges['mailbox:a>z'].down, true, 'a wire to a down node is not marked down');
});

// Model: Claude Opus 5.5 (the BOARD fixer, round 1), 2026-10-14. Status: unreviewed.
test('the pill counts listeners by pid, so a listener that is writing still counts (D15)', () => {
  const feed = {
    nodes: [
      node('w', { state: 'writing', listener_pid: 11 }), node('l', { listener_pid: 12 }),
      node('i', { state: 'idle', listener_pid: null }),
    ],
  };
  assert.deepEqual(pillText(feed), { text: 'live · 2 listening', state: 'up', listening: 2 });
});

test('the pill names down nodes in the word their boxes show', () => {
  const feed = { nodes: [node('l', { listener_pid: 12 }), node('d', { state: 'down' })] };
  assert.deepEqual(pillText(feed), { text: `1 listening · 1 ${STATES.down.word}`, state: 'warn', listening: 1 });
  assert.equal(STATES.down.word, 'no listener');
});

test('nodes named __proto__, constructor and toString lay out and draw like any other (C0 allows all three)', () => {
  const names = ['__proto__', 'a', 'constructor', 'toString'];
  const feed = {
    nodes: [
      node('__proto__', { role: 'orchestrator', role_source: 'declared' }),
      node('constructor', { role: 'worker', role_source: 'declared', level: 1, parent: '__proto__' }),
      node('toString'), node('a'),
    ],
    wires: [{ from: '__proto__', to: 'constructor', seq: 3, age_s: 0 }],
    links: [mailbox('__proto__', 'constructor'), mailbox('a', 'toString')],
  };
  const lay = layoutLevels(feed);
  assert.deepEqual(Object.keys(lay.pos).sort(), names);
  for (const [id, p] of Object.entries(lay.pos)) {
    assert.ok(Number.isFinite(p.x) && Number.isFinite(p.y), `${id} at ${p.x}, ${p.y}`);
  }
  assert.ok(Number.isFinite(lay.extent.w) && Number.isFinite(lay.extent.h), 'the extent is not finite');
  assert.equal(lay.rows.constructor, 1);
  const view = boardView(feed);
  assert.deepEqual(Object.keys(view.nodes).sort(), names);
  const wire = view.edges['mailbox:__proto__>constructor'];
  assert.ok(wire && wire.flow, 'the wire from __proto__ to constructor does not flow');
  for (const at of [wire.a, wire.b]) assert.ok(Number.isFinite(at.x) && Number.isFinite(at.y), 'a wire end is not finite');
  const kit = fakeKit();
  patchBoard(createBoard(kit), feed);
  assert.deepEqual(kit.created, { nodes: 4, edges: 2 });
});

test('a mailbox wire and a native line on one pair keep their words apart, on one path', () => {
  const view = boardView({
    nodes: [node('a', { kind: 'claude' }), node('b', { kind: 'claude' })],
    wires: [{ from: 'a', to: 'b', seq: 5, age_s: 0 }],
    links: [mailbox('a', 'b'), { from: 'a', to: 'b', kind: 'native' }],
  });
  const onPair = Object.values(view.edges).filter((e) => [e.from, e.to].sort().join('>') === 'a>b');
  assert.equal(onPair.length, 1, 'two paths on one pair: the native dashes lie on the mailbox wire');
  const [wire] = onPair;
  assert.deepEqual([wire.label, wire.sub], ['a → b · #5', 'native · not observed']);
  const at = labelPoints(wire);
  const apart = Math.abs(at.label.y - at.sub.y);
  assert.ok(apart >= CONFIG.BOARD_TEXT_MIN_PX, `the two label lines sit ${apart} px apart`);
});

test('a down node\'s status reads as its last status, never as its state now', () => {
  const view = boardView({
    nodes: [node('d', { state: 'down', status: '● listening' }), node('l', { status: 'reviewing the parser' })],
    wires: [], links: [],
  });
  assert.equal(view.nodes.d.note, `${NOTE_WORDS.lastStatus} ● listening`);
  assert.equal(view.nodes.l.note, 'reviewing the parser');
});
