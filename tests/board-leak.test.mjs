/**
 * Leak test for patchBoard in board/look.js: 500 feeds that add and remove
 * nodes and wires, then the starting feed again. The board's maps, its view
 * and the kit's live handles return to the starting counts, and no removed
 * node or wire is still held by the board.
 *
 * Model: Claude Opus 5.5 (the BOARD lane agent), 2026-10-14. Status: unreviewed.
 *
 * @interacts  imports board/look.js; no DOM (a fake kit stands in)
 * @deps       node:test, node:assert (Node 18+)
 * @complexity O(F) patches over F = 500 feeds of at most 4 nodes each
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
const node = (id, extra) => ({ id, state: 'listening', role: 'peer', role_source: 'inferred', level: 0, parent: null, ...extra });
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
