/**
 * Leak test for patchBoard in board/look.js: 500 feeds that add and remove
 * nodes and wires, then the starting feed again. The board's maps, its view
 * and the kit's live handles return to the starting counts, and no removed
 * node or wire is still held by the board. Then 500 feeds of peers that
 * come and go: the route cache holds a run for each routed pair drawn and
 * none for a pair gone.
 *
 * Model: Claude Opus 5.5 (the BOARD lane agent), 2026-10-14; the peer churn
 * by the P4 phase fixer, round 2, 2026-10-15. Status: unreviewed.
 *
 * @interacts  imports board/look.js; no DOM (a fake kit stands in)
 * @deps       node:test, node:assert (Node 18+)
 * @complexity O(F) patches over F = 500 feeds of at most 4 nodes each; the
 *             peer churn adds two route searches per feed on a board of
 *             three boxes
 * @alloc      one board and one kit; every handle the churn makes is
 *             removed before the end, which is what the test checks
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { createBoard, patchBoard } from '../board/look.js';

// Feeds in the run (phases.md B5).
const FEEDS = 500;

/**
 * A fake drawing kit that keeps every handle it ever made, by id.
 * @complexity O(1) per call  @alloc one handle per create
 */
function createFakeKit() {
  const kit = {
    live: new Set(),
    made: [],
    create(v) {
      const handle = {
        id: v.id,
        removed: false,
        update() {},
        remove() { handle.removed = true; kit.live.delete(handle); },
      };
      kit.live.add(handle);
      kit.made.push(handle);
      return handle;
    },
    createNode(v) { return kit.create(v); },
    createEdge(v) { return kit.create(v); },
  };
  return kit;
}

/** One feed node, a listening peer unless `extra` says otherwise. @complexity O(1)  @alloc one object */
const node = (id, extra) => ({ id, state: 'listening', role: 'peer', role_source: 'none', level: 0, parent: null, ...extra });
/** One mailbox link between two names. @complexity O(1)  @alloc one object */
const mailbox = (from, to) => ({ from, to, kind: 'mailbox', sent: { [from]: 1, [to]: 1 }, last_age_s: 1 });

const BASE = {
  nodes: [node('a', { role: 'orchestrator' }), node('b', { role: 'worker', level: 1, parent: 'a' })],
  links: [mailbox('a', 'b')],
  wires: [],
};

/**
 * Step i: the base plus two passing workers, t<i> and t<i+1>, each wired to a,
 * and a fresh message to t<i>. Every step adds one node and one wire and
 * removes one of each.
 * @complexity O(1)  @alloc one feed object
 */
function churn(i) {
  const extra = [`t${i}`, `t${i + 1}`];
  return {
    nodes: [...BASE.nodes, ...extra.map((id) => node(id, { role: 'worker', level: 1, parent: 'a' }))],
    links: [...BASE.links, ...extra.map((id) => mailbox('a', id))],
    wires: [{ from: 'a', to: `t${i}`, seq: i + 1, age_s: 0 }],
  };
}

test('500 feeds that add and remove nodes leave the board at its starting size, holding nothing removed', () => {
  const kit = createFakeKit();
  const board = createBoard(kit);
  patchBoard(board, BASE);
  const start = { nodes: board.nodes.size, edges: board.edges.size, live: kit.live.size };
  for (let i = 0; i < FEEDS; i += 1) patchBoard(board, churn(i));
  patchBoard(board, BASE);

  assert.deepEqual({ nodes: board.nodes.size, edges: board.edges.size, live: kit.live.size }, start);
  assert.deepEqual(Object.keys(board.view.nodes).sort(), ['a', 'b']);
  assert.deepEqual(Object.keys(board.view.edges), ['mailbox:a>b']);
  const held = new Set([...board.nodes.values(), ...board.edges.values()]);
  const passing = kit.made.filter((h) => h.id.startsWith('t') || h.id.includes('>t'));
  assert.ok(passing.length >= 2 * FEEDS, `only ${passing.length} passing handles were made`);
  for (const handle of passing) {
    assert.equal(handle.removed, true, `${handle.id} was never removed`);
    assert.equal(held.has(handle), false, `${handle.id} is still held by the board`);
  }
});

// Model: Claude Opus 5.5 (the P4 phase fixer, round 2), 2026-10-15. Status: unreviewed.
// The churn above is all tree pairs, which are never routed, so the route
// cache was never filled. Peers that come and go are routed pairs.
const PEER_BASE = {
  nodes: [node('x'), node('y')],
  links: [mailbox('x', 'y')],
  wires: [],
};

/**
 * Step i: the two base peers plus a passing peer q<i>, mailed by x: two
 * routed pairs, one of them new and the last step's gone.
 * @complexity O(1)  @alloc one feed object
 */
function peerChurn(i) {
  return {
    nodes: [...PEER_BASE.nodes, node(`q${i}`)],
    links: [...PEER_BASE.links, mailbox('x', `q${i}`)],
    wires: [{ from: 'x', to: `q${i}`, seq: i + 1, age_s: 0 }],
  };
}

test('500 feeds of peers that come and go leave the route cache holding one run per routed pair drawn, no more', () => {
  const board = createBoard(createFakeKit());
  patchBoard(board, PEER_BASE);
  let most = 0;
  for (let i = 0; i < FEEDS; i += 1) {
    patchBoard(board, peerChurn(i));
    most = Math.max(most, board.routes.runs.size);
  }
  patchBoard(board, PEER_BASE);
  assert.ok(board.routes.searches >= FEEDS, `only ${board.routes.searches} route searches, so the churn routed little`);
  assert.equal(most, 2, `the cache held ${most} runs while two pairs were drawn`);
  assert.deepEqual([...board.routes.runs.keys()], Object.values(board.view.edges).map((e) => `${e.from}>${e.to}`),
    'the cache does not hold exactly the drawn pairs\' runs');
});
