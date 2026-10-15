/**
 * Tests for the live board's diff and patch in board/look.js: patchBoard
 * keeps what stays, removes what went and adds what came, through a fake
 * drawing kit, so no DOM library is needed. Also C5's states (D24's working
 * and woken among them, with the pill and the wire they get), what
 * boardView draws for a feed's wires and links, and the pill's words;
 * names that are Object.prototype keys; a pair with a mailbox wire and a
 * native line (one path with the native words in its title); a down
 * node's stale status; the tree's own connector in place of the
 * reports_to hint; an unread count tc could not take (`unread unknown`);
 * the legend's two cases the states cannot see, and `inbox unreadable` on
 * a down node whose inbox the board could not list (D28);
 * a token that cannot ride in a header; and the page's poll loop
 * (createPoller) on fake timers and a fake fetch that the test settles by
 * hand, so no real clock or network is read. Then the badge lines on a
 * native pair's boxes and outline rows, with mail or without and never on
 * account `unknown`, and on a reports_to cycle's root; and the poller's
 * stale line over the board once an answer is late or refused.
 *
 * Model: Claude Opus 5.5 (the BOARD lane agent), 2026-10-14. Status: unreviewed.
 *
 * @interacts  imports board/look.js; no DOM; flushes promise callbacks with
 *             setImmediate, never waits on a real timer for a result
 * @deps       node:test, node:assert (Node 18+)
 * @complexity O(n + l) per test over a handful of nodes and links
 * @alloc      one board and one fake kit per test, dropped at its end
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  STATES, NOTE_WORDS, CONN_WORDS, LINK_WORDS, UNREAD_WORDS, INBOX_WORDS, LEGEND_WORDS, boardView, diffBoard, createBoard,
  patchBoard, pillText, layoutLevels, levelPort, createPoller, outlineView, tokenProblem, CONFIG,
} from '../board/look.js';

/**
 * A fake drawing kit: counts create calls and keeps every live handle.
 * @complexity O(1) per call  @alloc one handle per create, dropped on remove()
 */
function createFakeKit() {
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
  return { id, state: 'listening', role: 'peer', role_source: 'none', level: 0, parent: null, unread: 0, ...extra };
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

test('C5\'s states each have a glyph and a word of their own, D24\'s working and woken too', () => {
  for (const name of ['doorbell', 'remote', 'working', 'woken']) {
    assert.ok(STATES[name], `no state ${name}`);
    assert.ok(STATES[name].glyph && STATES[name].word, `${name} needs a glyph and a word`);
  }
  assert.equal(STATES.doorbell.glyph, '◎');
  assert.equal(STATES.remote.glyph, '⇄');
  assert.equal(STATES.remote.word, 'remote · not checked');
  assert.equal(STATES.woken.word, 'woken · not read');
  const glyphs = Object.values(STATES).map((s) => s.glyph);
  const words = Object.values(STATES).map((s) => s.word);
  assert.equal(Object.keys(STATES).length, 8);
  assert.equal(new Set(glyphs).size, glyphs.length, `glyphs repeat: ${glyphs}`);
  assert.equal(new Set(words).size, words.length, `words repeat: ${words}`);
});

// Model: Claude Opus 5.5 (the P4 phase fixer), 2026-10-15. Status: unreviewed.
// D24: a session that mail woke is working (calm) or woken (a warning), and
// neither is down: its wire stays a mail wire, never the dotted dead one.
test('a woken session warns in its own glyph and words and its wire is not the dotted dead wire; a working one is calm', () => {
  const feed = {
    nodes: [
      node('a', { listener_pid: 11 }), node('b', { state: 'woken', status: 'parsing the logs' }),
      node('c', { state: 'working', status: 'reading the diff' }),
    ],
    wires: [{ from: 'a', to: 'b', seq: 4, age_s: 0 }],
    links: [mailbox('a', 'b'), mailbox('a', 'c')],
  };
  const pill = pillText(feed);
  assert.deepEqual([pill.state, pill.text], ['warn', `1 listening · 1 ${STATES.woken.word}`]);
  assert.ok(!pill.text.includes(STATES.down.word), `the pill calls a woken session down: ${pill.text}`);
  assert.deepEqual(pillText({ nodes: [node('a', { listener_pid: 11 }), node('c', { state: 'working' })] }),
    { text: 'live · 1 listening', state: 'up', listening: 1 }, 'a working session raised the pill');
  const view = boardView(feed);
  assert.equal(view.edges['mailbox:a>b'].down, false, 'the wire to a woken session is drawn as the dead wire');
  assert.equal(view.edges['mailbox:a>b'].flow, true, 'the mail that woke b does not flow to it');
  assert.equal(view.edges['mailbox:a>c'].down, false);
  assert.deepEqual([view.nodes.b.state, view.nodes.b.note], ['woken', `${NOTE_WORDS.lastStatus} parsing the logs`]);
  assert.deepEqual([view.nodes.c.state, view.nodes.c.note], ['working', 'reading the diff']);
  const rows = Object.fromEntries(outlineView(feed).groups.flatMap((g) => g.rows).map((r) => [r.id, r]));
  assert.deepEqual([rows.b.glyph, rows.b.word], [STATES.woken.glyph, STATES.woken.word]);
  assert.deepEqual([rows.c.glyph, rows.c.word], [STATES.working.glyph, STATES.working.word]);
});

// Model: Claude Opus 5.5 (the P4 phase fixer, round 2), 2026-10-15. Status: unreviewed.
// C5 and D28: the legend names both cases the states cannot see, and a
// down node whose inbox the board could not list says so in words.
test('both legends name the two cases the states cannot see', () => {
  for (const [view, words] of [['graph', LEGEND_WORDS.graph], ['outline', LEGEND_WORDS.outline]]) {
    assert.match(words, /a crash after reading \(it looks working for up to 10 min\)/, `${view} legend: ${words}`);
    assert.match(words, /with no board page open, when a listener went/, `${view} legend: ${words}`);
    assert.ok(!words.includes('only a crash after reading'), `${view} legend still says a crash is the only case: ${words}`);
  }
});

test('a down node whose inbox the board could not list says inbox unreadable on its box and its row, and no other node does', () => {
  const feed = {
    nodes: [
      node('d', { state: 'down', inbox_unreadable: true, unread: null }), node('e', { state: 'down', inbox_unreadable: false }),
      node('l', { listener_pid: 12, inbox_unreadable: true }),
    ],
    wires: [], links: [],
  };
  const view = boardView(feed);
  const onBoxes = Object.fromEntries(Object.values(view.nodes).map((v) => [v.id, v.badges.map((b) => b.text)]));
  assert.deepEqual(onBoxes, { d: [INBOX_WORDS.unreadable], e: [], l: [] });
  assert.equal(INBOX_WORDS.unreadable, 'inbox unreadable');
  assert.equal(view.nodes.d.h, CONFIG.NODE_H + CONFIG.BADGE_H, 'the box did not grow a line for its words');
  assert.equal(view.nodes.d.state, 'down');
  const rows = Object.fromEntries(outlineView(feed).groups.flatMap((g) => g.rows).map((r) => [r.id, r.badges]));
  assert.deepEqual(rows, { d: [INBOX_WORDS.unreadable], e: [], l: [] });
});

test('patchBoard keeps what stays, drops what went, adds what came, and rebuilds nothing', () => {
  const kit = createFakeKit();
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

// The tree draws its own thin connector, parent's
// out port to child's in port, with no label; reports_to links draw nothing
// of their own; a native line has no label, its words in its title.
test('the tree draws its own connector, with no label; native words go in the title; a reports_to to nobody is a note', () => {
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
  assert.deepEqual(Object.keys(view.edges).filter((id) => id.startsWith('reports_to')), [], 'a reports_to link drew a line of its own');
  const stem = view.nodes.b.connector;
  assert.ok(stem, 'b has no connector to its parent');
  assert.deepEqual(stem.points[0], levelPort(view.nodes.a.pos, 'out', view.nodes.a.h), 'the connector does not leave a\'s out port');
  assert.deepEqual(stem.points.at(-1), levelPort(view.nodes.b.pos, 'in'), 'the connector does not reach b\'s in port');
  assert.equal(stem.words, 'b reports to a');
  assert.equal(view.nodes.a.connector, null, 'a root has a connector');
  const native = view.edges['native:a>b'];
  assert.equal(native.label, '', 'a native line carries a label on the board');
  assert.ok(native.words.endsWith(LINK_WORDS.native), `native words not in the title: ${native.words}`);
  assert.deepEqual(view.nodes.a.badges.map((b) => b.text), ['native with b · not observed'], 'a carries no native badge');
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
  for (const at of wire.points) assert.ok(Number.isFinite(at.x) && Number.isFinite(at.y), 'a wire point is not finite');
  const kit = createFakeKit();
  patchBoard(createBoard(kit), feed);
  assert.deepEqual(kit.created, { nodes: 4, edges: 2 });
});

test('a mailbox wire and a native line on one pair draw one path, the native words in its title and on both boxes', () => {
  const view = boardView({
    nodes: [node('a', { kind: 'claude' }), node('b', { kind: 'claude' })],
    wires: [{ from: 'a', to: 'b', seq: 5, age_s: 0 }],
    links: [mailbox('a', 'b'), { from: 'a', to: 'b', kind: 'native' }],
  });
  const onPair = Object.values(view.edges).filter((e) => [e.from, e.to].sort().join('>') === 'a>b');
  assert.equal(onPair.length, 1, 'two paths on one pair: the native dashes lie on the mailbox wire');
  const [wire] = onPair;
  assert.equal(wire.label, 'a → b · #5');
  assert.ok(wire.at, 'the label found no room on a board of two boxes');
  assert.equal(wire.words, `a → b · #5 · ${LINK_WORDS.native}`);
  assert.deepEqual([view.nodes.a.badges.length, view.nodes.b.badges.length], [1, 1], 'a pair that mails lost its native badges');
});

// Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
// C5 draws a native pair with the words `native · not observed`. Each box
// of the pair carries them on a badge, `native with <the other> · not
// observed`, whether or not the pair mails, and so does each outline row.
// Never on account `unknown` (D15): serve.py makes no such link, and a
// hand-made one draws no badge either.
const NATIVE_FEED = {
  nodes: [
    node('a', { kind: 'claude', account: 'home' }), node('b', { kind: 'claude', account: 'home' }),
    node('c', { kind: 'claude', account: 'lab' }), node('d', { kind: 'claude', account: 'lab' }),
    node('e', { kind: 'claude', account: 'lab' }),
    node('u1', { kind: 'claude', account: 'unknown' }), node('u2', { kind: 'claude', account: 'unknown' }),
  ],
  wires: [{ from: 'a', to: 'b', seq: 5, age_s: 0 }],
  links: [
    mailbox('a', 'b'), { from: 'a', to: 'b', kind: 'native' },
    { from: 'c', to: 'd', kind: 'native' }, { from: 'c', to: 'e', kind: 'native' }, { from: 'd', to: 'e', kind: 'native' },
    { from: 'u1', to: 'u2', kind: 'native' },
  ],
};
const NATIVE_WORDS = {
  a: ['native with b · not observed'], b: ['native with a · not observed'],
  c: ['native with d, e · not observed'], d: ['native with c, e · not observed'], e: ['native with c, d · not observed'],
  u1: [], u2: [],
};

test('both boxes and both outline rows of a native pair say native with the other, not observed, with mail or without', () => {
  const view = boardView(NATIVE_FEED);
  const onBoxes = Object.fromEntries(Object.values(view.nodes).map((v) => [v.id, v.badges.map((b) => b.text)]));
  assert.deepEqual(onBoxes, NATIVE_WORDS, 'the graph\'s badges');
  for (const v of Object.values(view.nodes)) {
    assert.equal(v.h, CONFIG.NODE_H + v.badges.length * CONFIG.BADGE_H, `${v.id}'s box is not one badge line taller per badge`);
    for (const b of v.badges) assert.equal(`${b.lead}${b.names}${b.tail}`, b.text, `${v.id}'s badge parts do not make its words`);
  }
  const ids = Object.keys(view.nodes);
  for (let i = 0; i < ids.length; i += 1) {
    for (let j = i + 1; j < ids.length; j += 1) {
      const [p, q] = [view.nodes[ids[i]], view.nodes[ids[j]]];
      const meet = p.pos.x < q.pos.x + CONFIG.NODE_W && q.pos.x < p.pos.x + CONFIG.NODE_W && p.pos.y < q.pos.y + q.h && q.pos.y < p.pos.y + p.h;
      assert.ok(!meet, `${p.id}'s box overlaps ${q.id}'s at their drawn heights`);
    }
  }
  const rows = Object.fromEntries(outlineView(NATIVE_FEED).groups.flatMap((g) => g.rows).map((r) => [r.id, r.badges]));
  assert.deepEqual(rows, NATIVE_WORDS, 'the outline\'s lines');
  assert.equal(Object.values(view.edges).filter((e) => e.kind === 'native').length, 3, 'a native pair with no mail lost its dash-dot line');
});

test('a reports_to cycle\'s root says whom it reports to, on a badge and in the outline', () => {
  const feed = {
    nodes: [
      node('p', { role: 'orchestrator', role_source: 'declared', reports_to: 'q' }),
      node('q', { role: 'orchestrator', role_source: 'declared', level: 1, parent: 'p', reports_to: 'p' }),
      node('r', { reports_to: 'ghost' }), node('s', { reports_to: 's' }),
    ],
    wires: [], links: [{ from: 'p', to: 'q', kind: 'reports_to' }, { from: 'q', to: 'p', kind: 'reports_to' }],
  };
  const view = boardView(feed);
  assert.deepEqual(view.nodes.p.badges.map((b) => b.text), ['reports to q · cycle'], 'the cycle\'s root hides its reports_to');
  for (const id of ['q', 'r', 's']) assert.deepEqual(view.nodes[id].badges, [], `${id} carries a badge`);
  assert.equal(view.nodes.r.note, 'reports to ghost · not found');
  const row = outlineView(feed).groups.flatMap((g) => g.rows).find((r) => r.id === 'p');
  assert.deepEqual(row.badges, ['reports to q · cycle']);
});

// Model: Claude Opus 5.5 (the P4 phase fixer), 2026-10-15. Status: unreviewed.
// SHARED's tc gives a null unread, with a reason, for an inbox it cannot
// count, and a reason beside a true count when it could not see only read/.
test('a null unread reads unread unknown in words, on the box and the row; a count with a reason keeps its count', () => {
  const feed = {
    nodes: [
      node('b', { unread: null, unread_problem: 'made-up reason' }), node('c', { unread: 2, unread_problem: null }),
      node('d', { unread: 0 }),
    ],
    wires: [], links: [],
  };
  const view = boardView(feed);
  assert.deepEqual([view.nodes.b.detail, view.nodes.c.detail, view.nodes.d.detail], [UNREAD_WORDS.unknown, '2 unread', '']);
  assert.equal(UNREAD_WORDS.unknown, 'unread unknown');
  const rows = Object.fromEntries(outlineView(feed).groups.flatMap((g) => g.rows).map((r) => [r.id, r.unread]));
  assert.deepEqual(rows, { b: UNREAD_WORDS.unknown, c: '2 unread', d: '' });
});

// A pasted token that ends in an ellipsis cannot ride in a header: fetch
// throws before it sends, and the pill used to blame a running server.
test('a token outside Latin-1 is called damaged in words, never `is serve.py running?`', () => {
  assert.equal(tokenProblem(''), CONN_WORDS.noToken);
  assert.equal(tokenProblem('abcDEF0189_-xyz…'), CONN_WORDS.tokenDamaged);
  assert.notEqual(CONN_WORDS.tokenDamaged, CONN_WORDS.noServer);
  assert.match(CONN_WORDS.tokenDamaged, /copy the URL/);
  assert.equal(tokenProblem('abcDEF0189_-xyz'), null);
  // A Latin-1 character rides in the header; the server refuses it (401, token refused).
  assert.equal(tokenProblem('abcé'), null);
});

test('a down node\'s status reads as its last status, never as its state now', () => {
  const view = boardView({
    nodes: [node('d', { state: 'down', status: '● listening' }), node('l', { status: 'reviewing the parser' })],
    wires: [], links: [],
  });
  assert.equal(view.nodes.d.note, `${NOTE_WORDS.lastStatus} ● listening`);
  assert.equal(view.nodes.l.note, 'reviewing the parser');
});

// Model: Claude Opus 5.5 (the BOARD fixer, round 1), 2026-10-14. Status: unreviewed.
// The page's poll loop. live.html's numbers, written here: a poll every
// 3 s, and a request still out after 2.5 s is late.
const POLL_MS = 3000;
const TIMEOUT_MS = 2500;

/**
 * Fake timers: setTimeout records; advance(ms) moves the fake clock and runs
 * each timer that comes due, in order.
 * @complexity O(t) per advance over t pending timers  @alloc one entry per pending timer
 */
function createFakeTimers() {
  let nowMs = 0;
  let ids = 0;
  const pending = new Map();
  return {
    pending,
    now: () => nowMs,
    setTimeout(fn, ms) {
      ids += 1;
      pending.set(ids, { fn, at: nowMs + ms });
      return ids;
    },
    clearTimeout(id) { pending.delete(id); },
    advance(ms) {
      const until = nowMs + ms;
      for (;;) {
        const due = [...pending].filter(([, t]) => t.at <= until).sort((x, y) => x[1].at - y[1].at)[0];
        if (!due) break;
        pending.delete(due[0]);
        nowMs = due[1].at;
        due[1].fn();
      }
      nowMs = until;
    },
  };
}

/**
 * A fake fetch: each call is a promise the test settles by hand; an abort
 * rejects it the way fetch does.
 * @complexity O(1) per call  @alloc one record per call
 */
function createFakeFetch() {
  const calls = [];
  const fetchFeed = (signal) => new Promise((resolve, reject) => {
    signal.addEventListener('abort', () => reject(Object.assign(new Error('aborted'), { name: 'AbortError' })));
    calls.push({ signal, resolve, reject });
  });
  return { calls, fetchFeed };
}

/** A 200 answer carrying `feed`. @complexity O(1)  @alloc one object */
const okAnswer = (feed) => ({ status: 200, ok: true, json: async () => feed });
/** Let settled promises run their callbacks. @complexity O(1)  @alloc one promise */
const flush = () => new Promise((resolve) => { setImmediate(resolve); });

/** A poller on fake timers and a fake fetch, recording what it reports. @complexity O(1)  @alloc one poller */
function createPollerRig() {
  const timers = createFakeTimers();
  const net = createFakeFetch();
  const seen = [];
  const pills = [];
  const poller = createPoller({
    fetchFeed: net.fetchFeed, pollMs: POLL_MS, timeoutMs: TIMEOUT_MS, timers, now: timers.now,
    onFeed: (feed) => seen.push(feed), onConn: (text, state) => pills.push([text, state]),
  });
  return { timers, net, seen, pills, poller };
}

test('the poll loop asks one request at a time, drops a late one, and says so in words, never live', async () => {
  const { timers, net, seen, pills, poller } = createPollerRig();
  poller.start();
  assert.equal(net.calls.length, 1);
  net.calls[0].resolve(okAnswer(FEED_A));
  await flush();
  assert.deepEqual(seen, [FEED_A]);
  timers.advance(POLL_MS - 1);
  assert.equal(net.calls.length, 1, 'the next poll came before POLL_MS');
  timers.advance(1);
  assert.equal(net.calls.length, 2);
  // This one hangs. No second request goes out while it does, and at
  // TIMEOUT_MS it is aborted and the pill says how old the last answer is.
  timers.advance(TIMEOUT_MS - 1);
  assert.equal(net.calls.length, 2, 'a second request went out while one was still in flight');
  assert.equal(net.calls[1].signal.aborted, false);
  timers.advance(1);
  await flush();
  assert.equal(net.calls[1].signal.aborted, true, 'a late request was never aborted');
  assert.deepEqual(pills.at(-1), [`${CONN_WORDS.stale} · last answer 6 s ago · ${CONN_WORDS.timedOut}`, 'down']);
  // The next poll waits POLL_MS after the last one settled, so a slow
  // server never gets a queue of requests.
  timers.advance(POLL_MS - 1);
  assert.equal(net.calls.length, 2, 'a poll went out before POLL_MS had passed since the last one settled');
  timers.advance(1);
  assert.equal(net.calls.length, 3, 'the loop stopped after a late answer');
  net.calls[2].reject(new TypeError('fetch failed'));
  await flush();
  assert.deepEqual(pills.at(-1), [`${CONN_WORDS.stale} · last answer 9 s ago · ${CONN_WORDS.noServer}`, 'down']);
  timers.advance(POLL_MS);
  net.calls[3].resolve({ status: 500, ok: false });
  await flush();
  assert.deepEqual(pills.at(-1), [`${CONN_WORDS.stale} · last answer 12 s ago · HTTP 500`, 'down']);
  assert.ok(pills.every(([text]) => !text.startsWith('live')), 'the pill said live with no answer behind it');
  poller.stop();
});

test('before any answer the pill says no answer, and a 401 says the token was refused', async () => {
  const { timers, net, pills, poller } = createPollerRig();
  poller.start();
  timers.advance(TIMEOUT_MS);
  await flush();
  assert.deepEqual(pills.at(-1), [`${CONN_WORDS.noAnswer} · ${CONN_WORDS.timedOut}`, 'down']);
  timers.advance(POLL_MS);
  net.calls[1].resolve({ status: 401, ok: false });
  await flush();
  assert.deepEqual(pills.at(-1), [CONN_WORDS.tokenRefused, 'down']);
  poller.stop();
});

// Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
// A stale feed froze the board while its wires kept moving under a legend
// that calls them mail now. The page now says stale over the board.
test('once a board is drawn, a late or refused answer says stale over the board, and the next good answer clears it', async () => {
  const timers = createFakeTimers();
  const net = createFakeFetch();
  const stale = [];
  const poller = createPoller({
    fetchFeed: net.fetchFeed, pollMs: POLL_MS, timeoutMs: TIMEOUT_MS, timers, now: timers.now,
    onFeed() {}, onConn() {}, onStale: (text) => stale.push(text),
  });
  poller.start();
  timers.advance(TIMEOUT_MS);
  await flush();
  assert.deepEqual(stale, [], 'stale said over a board never drawn');
  timers.advance(POLL_MS);
  net.calls[1].resolve(okAnswer(FEED_A));
  await flush();
  assert.deepEqual(stale, [null], 'a good answer did not clear the stale line');
  timers.advance(POLL_MS + TIMEOUT_MS);
  await flush();
  const late = Math.round((POLL_MS + TIMEOUT_MS) / 1000);
  assert.equal(stale.at(-1), `${CONN_WORDS.stale} · last answer ${late} s ago`, 'a late answer did not say stale over the board');
  timers.advance(POLL_MS);
  net.calls[3].resolve({ status: 401, ok: false });
  await flush();
  assert.match(String(stale.at(-1)), /^stale · last answer \d+ s ago$/, 'a refused token left the board looking live');
  timers.advance(POLL_MS);
  net.calls[4].resolve(okAnswer(FEED_B));
  await flush();
  assert.equal(stale.at(-1), null, 'the board stayed stale after a good answer');
  poller.stop();
});

test('stop clears every timer and aborts the request in flight; start polls again (pagehide, pageshow)', async () => {
  const { timers, net, seen, pills, poller } = createPollerRig();
  poller.start();
  assert.equal(timers.pending.size, 1, 'no deadline on the request in flight');
  poller.stop();
  assert.equal(timers.pending.size, 0, 'a timer outlived stop');
  assert.equal(net.calls[0].signal.aborted, true, 'stop left the request in flight');
  await flush();
  assert.deepEqual(pills, [], 'a request that stop aborted wrote the pill');
  timers.advance(10 * POLL_MS);
  assert.equal(net.calls.length, 1, 'it polled after stop');
  poller.start();
  assert.equal(net.calls.length, 2, 'start did not poll again');
  net.calls[1].resolve(okAnswer(FEED_B));
  await flush();
  assert.deepEqual(seen, [FEED_B]);
  assert.equal(timers.pending.size, 1, 'more than the next poll is pending');
  poller.stop();
  assert.equal(timers.pending.size, 0, 'the next poll outlived stop');
});
