/**
 * look.js: drawing tools for the board look. Builds the window frame, the
 * canvas, session nodes, ports and wires as DOM and SVG elements. The live
 * board's layer is pure: layoutLevels places a C5 feed's nodes in levels,
 * wrapped to a width, boardView turns a feed into what to draw, and
 * diffBoard says what changed between two views. patchBoard applies a diff
 * through a drawing kit (createKit for the DOM, or a test's fake), so the
 * board is never rebuilt. createFit keeps a board laid out to its canvas.
 *
 * @interacts  creates elements under the container the caller passes in; uses
 *             theme.css class names; applyLook writes data-theme on <html>;
 *             never touches innerHTML, storage or globals. layoutLevels,
 *             boardView, diffBoard, roleTitle, hueFor, hintPath, pillText,
 *             layoutWidth, labelPoints and fitTransform read only their
 *             arguments; patchBoard writes only the board object it is given
 *             and calls only its kit; createFit observes the canvas's scroll
 *             area through the observer it is given and writes the view's
 *             size and transform
 * @deps       browser DOM and SVG for the drawing functions; the pure layer
 *             needs neither (node --test runs it with no DOM library)
 * @complexity every drawing function is O(1) per call; a board with n nodes
 *             and w wires costs O(n + w) to build. layoutLevels, boardView,
 *             diffBoard and patchBoard are O(n + l + r) over n feed nodes,
 *             l links and r recent wires (C5: n tens, l tens, r <= 50);
 *             pillText is O(n)
 * @alloc      one element tree per node, one path + label per wire, each
 *             released by its own remove(); removeBoard releases everything
 *             createBoard made. A board object from createBoard holds one
 *             handle per drawn node and edge, dropped when patchBoard
 *             removes it
 */

const SVG_NS = 'http://www.w3.org/2000/svg';

// Model: Claude Opus 5.5 (the BOARD fixer, round 1), 2026-10-14. Status: unreviewed.
// a2, for Donald (MEDIUM-1): no text on the board is drawn under this many
// CSS px at the scale it is shown, on a desktop or a phone.
const MIN_TEXT_PX = 11;
// The smallest font-size theme.css gives text inside the board (the state
// line, the note and the wire labels). tests/board-layout.test.mjs reads
// theme.css and fails if the two drift apart.
const BOARD_TEXT_MIN_PX = 11;

export const CONFIG = Object.freeze({
  // Model: Claude Opus 5.5 (the BOARD lane agent), 2026-10-14. Status:
  // unreviewed. Wider and taller than the look kit's 132 x 48, so a title
  // holds "name · orchestrator · inferred" and a third line holds the status.
  // 64 tall (round 1): three lines of 11 px or more inside a 4 px double border.
  NODE_W: 208,
  NODE_H: 64,
  PORT_SIZE: 12,
  // Wire bend: horizontal control-point reach is half the span, never less
  // than WIRE_MIN_BEND, so short wires still curve instead of kinking.
  WIRE_BEND_RATIO: 0.5,
  WIRE_MIN_BEND: 28,
  WIRE_SPACE: 5000,
  ARROW_SIZE: 7,
  // Arrow tip stops short of the port ring instead of sitting on it (marker units).
  ARROW_BACKOFF: 15,
  LABEL_LIFT: 7,
  // Model: Claude Opus 5.5 (the BOARD fixer, round 1), 2026-10-14. Status: unreviewed.
  // A second label line (a native link's words on a mailbox wire) sits with
  // its baseline this far under the wire's middle: one 11 px line plus
  // LABEL_LIFT, so it touches neither the first line nor the wire.
  LABEL_DROP: 18,
  // Model: Claude Opus 5.5 (the BOARD lane agent), 2026-10-14. Status: unreviewed.
  // layoutLevels: the gap between two boxes in one row; between a parent and
  // its children (room for a wire's two label lines, about 36 px, and a
  // reports_to hint's words); between two wrapped rows of one parent's
  // children (room for one wire label); between two root trees side by side
  // (wider than a column gap, so two trees read as two); and around the board.
  // Root trees one under another are LAYOUT_ROW_GAP apart. Round 1 added the
  // wrap gap and the indent: on a phone, where a row holds one box, children
  // sit LAYOUT_INDENT right of their parent so the levels still read.
  LAYOUT_COL_GAP: 28,
  LAYOUT_ROW_GAP: 56,
  LAYOUT_WRAP_GAP: 40,
  LAYOUT_ROOT_GAP: 72,
  LAYOUT_INDENT: 32,
  LAYOUT_MARGIN: 24,
  // A message at most this many seconds old flows on its wire. The feed's
  // WRITING_WINDOW_S, so the wire moves while its sender reads as writing.
  FLOW_AGE_S: 10,
  // A reports_to hint's label sits this far right of the line it names.
  HINT_LABEL_SHIFT: 6,
  // hueFor's string hash step: a small odd prime spreads short names.
  HUE_HASH_STEP: 31,
  // Model: Claude Opus 5.5 (the BOARD fixer, round 1), 2026-10-14. Status: unreviewed.
  // fitTransform never shrinks a board below this: the scale at which the
  // board's smallest text is MIN_TEXT_PX. With both at 11 it is 1, so the
  // board never shrinks; layoutLevels wraps it to the width instead and the
  // canvas scrolls down.
  MIN_TEXT_PX,
  BOARD_TEXT_MIN_PX,
  MIN_FIT_SCALE: MIN_TEXT_PX / BOARD_TEXT_MIN_PX,
  // The wire layer is never sized under this: SVG draws nothing at zero.
  MIN_LAYER_PX: 1,
});

/** Session states. Each one carries a glyph and a word, never color alone. */
export const STATES = Object.freeze({
  listening: { glyph: '●', word: 'listening' },
  writing: { glyph: '✎', word: 'writing' },
  idle: { glyph: '○', word: 'idle' },
  down: { glyph: '✕', word: 'no listener' },
  // Model: Claude Opus 5.5 (the BOARD lane agent), 2026-10-14. Status: unreviewed.
  // C5's two new states: a codex name is reached by its doorbell, with no
  // listener on purpose; an ssh name lives on another machine (O8).
  doorbell: { glyph: '◎', word: 'doorbell' },
  remote: { glyph: '⇄', word: 'remote · not checked' },
});

/**
 * The two looks. dark is the default and sets no attribute; the others set
 * data-theme on <html>, which theme.css keys its token sets on. Each has a
 * glyph and a word, so the switch never says which is on by color alone.
 */
export const LOOKS = Object.freeze({
  dark: { glyph: '◐', word: 'Dark', attr: null },
  daylight: { glyph: '☀', word: 'Light', attr: 'daylight' },
});
export const DEFAULT_LOOK = 'dark';

/**
 * Which look to draw: the URL's choice, else the stored one, else the
 * default. Unknown names are ignored, so a stale or mistyped value falls
 * through instead of drawing a look that has no tokens.
 * @complexity O(1)  @alloc none
 */
export function pickLook(fromUrl, fromStore) {
  if (Object.hasOwn(LOOKS, fromUrl)) return fromUrl;
  if (Object.hasOwn(LOOKS, fromStore)) return fromStore;
  return DEFAULT_LOOK;
}

/**
 * Draw the page in a look. Only the attribute changes; theme.css does the rest.
 * @interacts  writes data-theme on doc.documentElement
 * @complexity O(1)  @alloc none
 */
export function applyLook(doc, look) {
  const attr = LOOKS[look] ? LOOKS[look].attr : null;
  if (attr) doc.documentElement.dataset.theme = attr;
  else delete doc.documentElement.dataset.theme;
}

/**
 * Two-button switch between the looks. The pressed one has a filled dot and a
 * light face with dark words; the other a ring and no face, so pressed reads
 * by shape and lightness, not hue. Calls onPick(look) on a click; the caller
 * applies and stores it, and calls setLook so the switch follows.
 * @interacts  appends to parent; one click listener per button, released with
 *             the elements (removeBoard or the caller's own teardown)
 * @complexity O(k) for k looks, 2 today  @alloc one group and k buttons
 * @returns {{ root, setLook(look) }}
 */
export function createLookSwitch(doc, parent, { look, onPick }) {
  const root = el(doc, 'div', 'tc-look');
  root.setAttribute('role', 'group');
  root.setAttribute('aria-label', 'Look');
  const buttons = Object.entries(LOOKS).map(([name, l]) => {
    const b = el(doc, 'button', 'tc-look-btn');
    b.type = 'button';
    b.dataset.look = name;
    b.setAttribute('aria-label', l.word);
    b.append(el(doc, 'span', 'tc-look-dot'), el(doc, 'span', 'tc-look-glyph', l.glyph), el(doc, 'span', 'tc-look-word', l.word));
    b.addEventListener('click', () => onPick(name));
    return b;
  });
  root.append(...buttons);
  parent.append(root);
  const setLook = (current) => {
    for (const b of buttons) b.setAttribute('aria-pressed', String(b.dataset.look === current));
  };
  setLook(look);
  return { root, setLook };
}

/** Node bar hues. Identity only; the node title already names the session. */
export const HUES = Object.freeze([
  'var(--tc-cyan)', 'var(--tc-violet)', 'var(--tc-orange)', 'var(--tc-yellow)',
  'var(--tc-green)', 'var(--tc-red)', 'var(--tc-blue)', 'var(--tc-grey)',
]);

function el(doc, tag, cls, text) {
  const e = doc.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

function svg(doc, tag, attrs) {
  const e = doc.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) e.setAttribute(k, String(v));
  return e;
}

/**
 * Bezier path between two points, bending out horizontally like the notebook.
 * @complexity O(1)  @alloc one string
 */
export function wirePath(a, b) {
  const dx = Math.max(CONFIG.WIRE_MIN_BEND, Math.abs(b.x - a.x) * CONFIG.WIRE_BEND_RATIO);
  return `M ${a.x} ${a.y} C ${a.x + dx} ${a.y}, ${b.x - dx} ${b.y}, ${b.x} ${b.y}`;
}

/**
 * Where a node's port sits in board coordinates. side: 'in' (left) or 'out' (right).
 * @complexity O(1)  @alloc one object
 */
export function portPoint(pos, side) {
  return { x: pos.x + (side === 'in' ? 0 : CONFIG.NODE_W), y: pos.y + CONFIG.NODE_H / 2 };
}

/**
 * Window frame: title bar with traffic dots, a status pill, a body and a footer.
 * @interacts  appends to parent
 * @complexity O(1)  @alloc one window subtree
 * @returns {{ root, title, body, foot, setConn(text, state) }}  state: 'up' | 'warn' | 'down'
 */
export function createWindow(doc, parent, { file, sub }) {
  const root = el(doc, 'div', 'tc-win');
  const title = el(doc, 'div', 'tc-title');
  for (const c of ['r', 'y', 'g']) title.append(el(doc, 'span', `tc-dot ${c}`));
  title.append(el(doc, 'span', 'tc-fname', file), el(doc, 'span', 'tc-sub', sub));
  const conn = el(doc, 'span', 'tc-conn');
  const cdot = el(doc, 'span', 'tc-cdot');
  const ctext = el(doc, 'span', '', '');
  conn.append(cdot, ctext);
  title.append(conn);
  const body = el(doc, 'div', 'tc-body');
  const foot = el(doc, 'div', 'tc-foot');
  root.append(title, body, foot);
  parent.append(root);
  return {
    root, title, body, foot,
    setConn(text, state) { ctext.textContent = text; conn.dataset.state = state; },
  };
}

/**
 * Footer cells. Each item is { text } or { spacer: true }. Replaces what was there.
 * @complexity O(k) for k items  @alloc k spans
 */
export function setFooter(doc, foot, items) {
  foot.replaceChildren(...items.map((it) => (it.spacer ? el(doc, 'span', 'tc-sp') : el(doc, 'span', '', it.text))));
}

/**
 * Canvas: a frame holding a scroll area, which holds the view (a wire layer
 * in SVG and a node layer), and a HUD line over the frame's bottom edge. The
 * scroll area scrolls down when the board is taller than the canvas, never
 * sideways (round 1, a2's MEDIUM-1); the HUD stays put while it scrolls.
 * @interacts  appends to parent
 * @complexity O(1)  @alloc one canvas subtree with an arrow marker def
 * @returns {{ root, scroll, view, wires, hud }}
 */
export function createCanvas(doc, parent, hudText) {
  const root = el(doc, 'div', 'tc-canvas');
  const scroll = el(doc, 'div', 'tc-scroll');
  const view = el(doc, 'div', 'tc-view');
  const wires = svg(doc, 'svg', { class: 'tc-wires', width: CONFIG.WIRE_SPACE, height: CONFIG.WIRE_SPACE });
  const defs = svg(doc, 'defs');
  const marker = svg(doc, 'marker', {
    id: 'tc-arrow', viewBox: '0 0 10 10', refX: CONFIG.ARROW_BACKOFF, refY: 5,
    markerWidth: CONFIG.ARROW_SIZE, markerHeight: CONFIG.ARROW_SIZE, orient: 'auto-start-reverse',
  });
  marker.append(svg(doc, 'path', { d: 'M 0 0 L 10 5 L 0 10 z', class: 'tc-arrow' }));
  defs.append(marker);
  wires.append(defs);
  const hud = el(doc, 'div', 'tc-hud', hudText || '');
  view.append(wires);
  scroll.append(view);
  root.append(scroll, hud);
  parent.append(root);
  return { root, scroll, view, wires, hud };
}

/**
 * Session node at pos with an in port (ring) and an out port (dot). The
 * title splits at its first ' · ': the name may shorten with an ellipsis,
 * the role words after it never do. A third line holds `note` (a status
 * line, or a reports_to that names nobody); empty, it is hidden.
 * @interacts  appends to canvas.view; remove() takes the node out again
 * @complexity O(1)  @alloc one node subtree
 * @returns {{ root, pos, setState(state, detail), setTitle(text), setNote(text), moveTo(pos), remove() }}
 */
export function createNode(doc, canvas, { title, hue, pos, state, detail, note }) {
  const root = el(doc, 'div', 'tc-node');
  root.style.width = `${CONFIG.NODE_W}px`;
  root.style.height = `${CONFIG.NODE_H}px`;
  root.style.setProperty('--tc-node-hue', hue || HUES[HUES.length - 1]);
  const bar = el(doc, 'span', 'tc-node-bar');
  const body = el(doc, 'span', 'tc-node-body');
  const t = el(doc, 'span', 'tc-node-title');
  const tName = el(doc, 'span', 'tc-node-name');
  const tRole = el(doc, 'span', 'tc-node-role');
  t.append(tName, tRole);
  const sub = el(doc, 'span', 'tc-node-sub');
  const glyph = el(doc, 'span', 'tc-node-glyph');
  const word = el(doc, 'span');
  sub.append(glyph, word);
  const noteLine = el(doc, 'span', 'tc-node-note');
  body.append(t, sub, noteLine);
  const half = CONFIG.PORT_SIZE / 2;
  const pin = el(doc, 'span', 'tc-port in');
  pin.title = 'in';
  pin.style.left = `${-half}px`;
  pin.style.top = `${CONFIG.NODE_H / 2 - half}px`;
  const pout = el(doc, 'span', 'tc-port out');
  pout.title = 'out';
  pout.style.left = `${CONFIG.NODE_W - half}px`;
  pout.style.top = `${CONFIG.NODE_H / 2 - half}px`;
  root.append(bar, body, pin, pout);
  canvas.view.append(root);
  const node = {
    root, pos,
    setState(s, d) {
      const st = STATES[s] || STATES.idle;
      root.dataset.state = s;
      glyph.textContent = st.glyph;
      word.textContent = d ? `${st.word} · ${d}` : st.word;
    },
    setTitle(title) {
      const text = String(title ?? '');
      const cut = text.indexOf(' · ');
      tName.textContent = cut < 0 ? text : text.slice(0, cut);
      tRole.textContent = cut < 0 ? '' : text.slice(cut);
      root.title = text;
    },
    setNote(text) {
      noteLine.textContent = text || '';
      noteLine.hidden = !text;
    },
    moveTo(p) {
      node.pos = p;
      root.style.left = `${p.x}px`;
      root.style.top = `${p.y}px`;
    },
    remove() { root.remove(); },
  };
  node.moveTo(pos);
  node.setTitle(title);
  node.setNote(note);
  node.setState(state || 'idle', detail);
  return node;
}

/**
 * Wire from one node's out port to another's in port, with an arrow and a label.
 * setFlow(true, text, back) animates dashes toward the reader and shows the
 * label; back = true means the message runs from `to` toward `from` (a reply),
 * so the dashes run backward and the arrow sits at the start. setFlow(false)
 * leaves a quiet line. setDown(true) marks a broken link.
 * @interacts  appends to canvas.wires
 * @complexity O(1) per call  @alloc one path and one text element
 */
export function drawWire(doc, canvas, from, to) {
  const path = svg(doc, 'path', { class: 'tc-wire' });
  const label = svg(doc, 'text', { class: 'tc-wire-label', 'text-anchor': 'middle' });
  canvas.wires.append(path, label);
  const a = portPoint(from.pos, 'out');
  const b = portPoint(to.pos, 'in');
  path.setAttribute('d', wirePath(a, b));
  label.setAttribute('x', String((a.x + b.x) / 2));
  label.setAttribute('y', String((a.y + b.y) / 2 - CONFIG.LABEL_LIFT));
  return {
    path, label,
    setFlow(on, text, back) {
      path.classList.toggle('flow', on);
      path.classList.toggle('back', on && !!back);
      path.removeAttribute('marker-end');
      path.removeAttribute('marker-start');
      if (on) path.setAttribute(back ? 'marker-start' : 'marker-end', 'url(#tc-arrow)');
      label.textContent = on ? (text || '') : '';
    },
    setDown(on) { path.classList.toggle('down', on); },
  };
}

/**
 * Remove everything a board created under parent.
 * @complexity O(n) children  @alloc none
 */
export function removeBoard(parent) {
  parent.replaceChildren();
}

// ---------- the live board (C5), pure first, then its DOM kit ----------
// Model: Claude Opus 5.5 (the BOARD lane agent), 2026-10-14. Status: unreviewed.

/** Words on the board's hint lines. Each hint is a line plus words, never color alone. */
export const LINK_WORDS = Object.freeze({
  reports_to: 'reports to',
  native: 'native · not observed',
  notFound: 'not found',
});

/**
 * Words on a node's third line. A down node's status was written while it
 * listened, so it reads as the last thing it said, never as its state now.
 * Model: Claude Opus 5.5 (the BOARD fixer, round 1), 2026-10-14. Status: unreviewed.
 */
export const NOTE_WORDS = Object.freeze({
  lastStatus: 'last status:',
});

/**
 * An empty map keyed by session name, with no prototype, so a name such as
 * __proto__ or constructor (both legal under C0) is an own key like any
 * other. Model: Claude Opus 5.5 (the BOARD fixer, round 1), 2026-10-14.
 * Status: unreviewed.
 * @complexity O(1)  @alloc one object
 */
function nameMap() {
  return Object.create(null);
}

/** Compare two names by code point, as Python's sort does. @complexity O(c) over c characters  @alloc none */
function byName(p, q) {
  if (p < q) return -1;
  return p > q ? 1 : 0;
}

/**
 * A node's title: its name and role word, plus `· inferred` exactly when
 * role_source says inferred (C5). A node with no role is its name alone.
 * @complexity O(1)  @alloc one string
 */
export function roleTitle(node) {
  if (!node.role) return String(node.id);
  return `${node.id} · ${node.role}${node.role_source === 'inferred' ? ' · inferred' : ''}`;
}

/**
 * Index into HUES for a name: the same name gets the same bar every time.
 * Identity only; nothing reads meaning from it.
 * @complexity O(c) over c characters in the name  @alloc none
 */
export function hueFor(id) {
  let h = 0;
  for (const ch of String(id)) h = (h * CONFIG.HUE_HASH_STEP + ch.codePointAt(0)) % HUES.length;
  return h;
}

/**
 * Pack blocks into rows left to right: a block starts a new row when it
 * would take the row past `limit`. Infinity never wraps.
 * Model: Claude Opus 5.5 (the BOARD fixer, round 1), 2026-10-14. Status: unreviewed.
 * @complexity O(b) over b blocks  @alloc one row object per row, returned
 * @returns {{ items: {id, w, h}[], w, h }[]}
 */
function packRows(blocks, limit, gap) {
  const out = [];
  let row = null;
  for (const b of blocks) {
    if (row && row.w + gap + b.w <= limit) {
      row.items.push(b);
      row.w += gap + b.w;
      row.h = Math.max(row.h, b.h);
    } else {
      row = { items: [b], w: b.w, h: b.h };
      out.push(row);
    }
  }
  return out;
}

/**
 * Where a C5 feed's nodes go, inside `width` board px (Infinity, the
 * default, never wraps). Roots in name order, levels top to bottom (C5). A
 * node hangs under its `parent` when its level is the parent's plus one
 * (D15, pause BOARD-3); every other node is a root, so a cycle's root lays
 * out like any other. A parent sits over its children. The children, each
 * with its own subtree, fill a row left to right and wrap to a new row,
 * LAYOUT_WRAP_GAP lower, when the next one would pass the width (round 1,
 * a2's MEDIUM-1). Where a row holds a single box (a phone), the parent sits
 * at the left and its children are indented LAYOUT_INDENT under it while a
 * box still fits. Root trees fill rows the same way: LAYOUT_ROOT_GAP apart
 * side by side, LAYOUT_ROW_GAP apart one under another. Each subtree keeps
 * a band no other box enters, so no two boxes overlap, and the extent is at
 * most `width` whenever one box and the margins fit in it. Every map is
 * keyed with no prototype (or is a Map), so a node named __proto__ lays out
 * like any other.
 * @interacts  none; pure
 * @complexity O(n log n) over n nodes: one sort by name, then three walks
 *             that visit each node a fixed number of times
 * @alloc      the returned maps; six Maps and the row lists for the walks,
 *             freed on return
 * @returns {{ pos: {id: {x, y}}, titles: {id: string}, rows: {id: number}, roots: string[], extent: {w, h} }}
 *          rows is each node's depth in its tree
 */
export function layoutLevels(feed, width = Infinity) {
  const C = CONFIG;
  const sorted = [...((feed && feed.nodes) || [])].sort((p, q) => byName(p.id, q.id));
  const known = new Map(sorted.map((n) => [n.id, n]));
  const nodes = [...known.values()];
  const kids = new Map();
  const childIds = new Set();
  for (const n of nodes) {
    const parent = n.parent == null ? undefined : known.get(n.parent);
    if (n.level > 0 && parent && parent.level === n.level - 1) {
      if (!kids.has(parent.id)) kids.set(parent.id, []);
      kids.get(parent.id).push(n.id);
      childIds.add(n.id);
    }
  }
  const roots = nodes.filter((n) => !childIds.has(n.id)).map((n) => n.id);
  // Walk 1, top down: each node's depth, and the width its subtree may use.
  // A row that cannot hold two boxes is narrow: its children indent.
  const rows = nameMap();
  const room = new Map();
  const indent = new Map();
  const order = [...roots];
  const rootRoom = width - 2 * C.LAYOUT_MARGIN;
  for (const r of roots) {
    rows[r] = 0;
    room.set(r, rootRoom);
  }
  for (let i = 0; i < order.length; i += 1) {
    const id = order[i];
    const w = room.get(id);
    const narrow = w < 2 * C.NODE_W + C.LAYOUT_COL_GAP;
    indent.set(id, narrow && w - C.LAYOUT_INDENT >= C.NODE_W ? C.LAYOUT_INDENT : 0);
    for (const c of kids.get(id) || []) {
      rows[c] = rows[id] + 1;
      room.set(c, w - indent.get(id));
      order.push(c);
    }
  }
  // Walk 2, bottom up: each subtree's block, its children's places inside
  // it, and where the node's own box sits in it.
  const block = new Map();
  const inBlock = new Map();
  const ownX = new Map();
  for (let i = order.length - 1; i >= 0; i -= 1) {
    const id = order[i];
    const cs = kids.get(id) || [];
    if (!cs.length) {
      block.set(id, { w: C.NODE_W, h: C.NODE_H });
      ownX.set(id, 0);
      continue;
    }
    const ind = indent.get(id);
    const lines = packRows(cs.map((c) => ({ id: c, ...block.get(c) })), room.get(id) - ind, C.LAYOUT_COL_GAP);
    let y = C.NODE_H + C.LAYOUT_ROW_GAP;
    let areaW = 0;
    for (const line of lines) {
      let x = ind;
      for (const b of line.items) {
        inBlock.set(b.id, { x, y });
        x += b.w + C.LAYOUT_COL_GAP;
      }
      areaW = Math.max(areaW, line.w);
      y += line.h + C.LAYOUT_WRAP_GAP;
    }
    ownX.set(id, ind ? 0 : (areaW - C.NODE_W) / 2);
    block.set(id, { w: Math.max(C.NODE_W, ind + areaW), h: y - C.LAYOUT_WRAP_GAP });
  }
  // Walk 3, top down: root trees into rows, then every box by its block.
  const pos = nameMap();
  const origin = new Map();
  let top = C.LAYOUT_MARGIN;
  let widest = 0;
  for (const line of packRows(roots.map((r) => ({ id: r, ...block.get(r) })), rootRoom, C.LAYOUT_ROOT_GAP)) {
    let x = C.LAYOUT_MARGIN;
    for (const b of line.items) {
      origin.set(b.id, { x, y: top });
      x += b.w + C.LAYOUT_ROOT_GAP;
    }
    widest = Math.max(widest, line.w);
    top += line.h + C.LAYOUT_ROW_GAP;
  }
  for (const id of order) {
    const o = origin.get(id);
    pos[id] = { x: o.x + ownX.get(id), y: o.y };
    for (const c of kids.get(id) || []) {
      const at = inBlock.get(c);
      origin.set(c, { x: o.x + at.x, y: o.y + at.y });
    }
  }
  const extent = roots.length
    ? { w: widest + 2 * C.LAYOUT_MARGIN, h: top - C.LAYOUT_ROW_GAP + C.LAYOUT_MARGIN }
    : { w: 0, h: 0 };
  const titles = nameMap();
  for (const n of nodes) titles[n.id] = roleTitle(n);
  return { pos, titles, rows, roots, extent };
}

/**
 * The width layoutLevels may use on a canvas `canvasWidth` CSS px wide: the
 * most the board may span at the smallest scale MIN_FIT_SCALE allows, so at
 * the scale fitTransform then picks it never runs past the canvas.
 * Model: Claude Opus 5.5 (the BOARD fixer, round 1), 2026-10-14. Status: unreviewed.
 * @complexity O(1)  @alloc none
 */
export function layoutWidth(canvasWidth) {
  return canvasWidth / CONFIG.MIN_FIT_SCALE;
}

/**
 * Bezier for a reports_to hint, from a child's top edge to its parent's
 * bottom edge, bending vertically so it never lies on a side-port wire.
 * @complexity O(1)  @alloc one string
 */
export function hintPath(a, b) {
  const dy = Math.max(CONFIG.WIRE_MIN_BEND, Math.abs(b.y - a.y) * CONFIG.WIRE_BEND_RATIO);
  const s = a.y > b.y ? -1 : 1;
  return `M ${a.x} ${a.y} C ${a.x} ${a.y + s * dy}, ${b.x} ${b.y - s * dy}, ${b.x} ${b.y}`;
}

/** One key for a pair of names, whichever way the message ran. @complexity O(1)  @alloc one string */
function pairKey(p, q) {
  return p < q ? `${p}>${q}` : `${q}>${p}`;
}

/**
 * The two ends of a side-port wire: the upper node first (lower level),
 * then the one further left, then by name, so a wire runs out to in downhill.
 * @complexity O(1)  @alloc one two-item list
 */
function upperFirst(p, q, pos) {
  const order = [p, q].sort((m, n) => (pos[m.id].y - pos[n.id].y) || (pos[m.id].x - pos[n.id].x) || byName(m.id, n.id));
  return order;
}

/**
 * The pill's words and state for a feed: `live · N listening`, or
 * `N listening · M no listener` while a node is down, in the same words its
 * box shows (STATES.down). Listeners are counted by listener_pid (a pid tc
 * read from /proc/locks), never by state: under D15 a listener that just
 * sent reads writing and is still listening.
 * Model: Claude Opus 5.5 (the BOARD fixer, round 1), 2026-10-14. Status: unreviewed.
 * @interacts  none; pure
 * @complexity O(n) over n feed nodes  @alloc one object
 * @returns {{ text, state, listening }}  state: 'up' | 'warn', for createWindow's setConn
 */
export function pillText(feed) {
  const nodes = (feed && feed.nodes) || [];
  const listening = nodes.filter((n) => n.listener_pid).length;
  const down = nodes.filter((n) => n.state === 'down').length;
  return down
    ? { text: `${listening} listening · ${down} ${STATES.down.word}`, state: 'warn', listening }
    : { text: `live · ${listening} listening`, state: 'up', listening };
}

/**
 * A node's third line: a reports_to that names no node, else its status. A
 * down node's status is stale, so it reads `last status: ...` and never
 * passes for the node's state now (round 1, LOW-20).
 * @complexity O(1)  @alloc one string
 */
function noteFor(n, known) {
  if (n.reports_to && !known.has(n.reports_to)) return `${LINK_WORDS.reports_to} ${n.reports_to} · ${LINK_WORDS.notFound}`;
  if (!n.status) return '';
  return n.state === 'down' ? `${NOTE_WORDS.lastStatus} ${n.status}` : n.status;
}

/**
 * What to draw for a C5 feed laid out inside `width` (see layoutLevels):
 * one view per node and per edge, keyed by id. Node: title (roleTitle), pos
 * (layoutLevels), state, detail (unread count), note (`reports to N · not
 * found`, else the status line, as `last status: ...` on a down node).
 * Edges come from links whose two ends are both nodes: a mailbox link is a
 * wire between side ports that flows, with an arrow at the reader and
 * `from → to · #seq`, when its pair's newest wire is at most FLOW_AGE_S old,
 * and is down when either end is down; a reports_to link is a thin hint
 * from the child's top to the parent's bottom with an arrow at the parent
 * and the words `reports to`; a native link carries the words `native · not
 * observed`. A pair with a mailbox link and a native link draws one wire,
 * with the native words as its second label line (`sub`), under the line,
 * so neither label covers the other and the wire's dash pattern shows
 * (round 1, MEDIUM-3).
 * @interacts  none; pure
 * @complexity O(n log n + l + r) over n nodes, l links, r wires  @alloc the returned views
 * @returns {{ nodes: {id: view}, edges: {id: view}, extent: {w, h} }}
 */
export function boardView(feed, width) {
  const lay = layoutLevels(feed, width);
  const known = new Map(((feed && feed.nodes) || []).map((n) => [n.id, n]));
  const nodes = nameMap();
  for (const n of known.values()) {
    nodes[n.id] = {
      id: n.id, title: lay.titles[n.id], pos: lay.pos[n.id], state: STATES[n.state] ? n.state : 'idle',
      detail: n.unread > 0 ? `${n.unread} unread` : '', note: noteFor(n, known),
    };
  }
  const flowing = new Map();
  for (const w of (feed && feed.wires) || []) {
    if (w.age_s == null || w.age_s > CONFIG.FLOW_AGE_S || w.from === w.to) continue;
    const key = pairKey(w.from, w.to);
    if (!flowing.has(key) || w.seq > flowing.get(key).seq) flowing.set(key, w);
  }
  const links = (feed && feed.links) || [];
  const pairsOf = (kind) => new Set(links
    .filter((l) => l.kind === kind && known.has(l.from) && known.has(l.to) && l.from !== l.to)
    .map((l) => pairKey(l.from, l.to)));
  const mailboxPairs = pairsOf('mailbox');
  const nativePairs = pairsOf('native');
  const edges = nameMap();
  for (const l of links) {
    const p = known.get(l.from);
    const q = known.get(l.to);
    if (!p || !q || p === q) continue;
    const id = `${l.kind}:${l.from}>${l.to}`;
    if (l.kind === 'reports_to') {
      const child = lay.pos[p.id];
      const parent = lay.pos[q.id];
      edges[id] = {
        id, kind: l.kind, from: p.id, to: q.id,
        a: { x: child.x + CONFIG.NODE_W / 2, y: child.y }, b: { x: parent.x + CONFIG.NODE_W / 2, y: parent.y + CONFIG.NODE_H },
        label: LINK_WORDS.reports_to, sub: '', arrow: 'end', flow: false, back: false, down: false,
      };
      continue;
    }
    if (l.kind !== 'mailbox' && l.kind !== 'native') continue;
    // A native link whose pair also has mail rides on that wire's second line.
    if (l.kind === 'native' && mailboxPairs.has(pairKey(l.from, l.to))) continue;
    const [top, low] = upperFirst(p, q, lay.pos);
    const w = l.kind === 'mailbox' ? flowing.get(pairKey(l.from, l.to)) : undefined;
    const back = !!w && w.from !== top.id;
    edges[id] = {
      id, kind: l.kind, from: top.id, to: low.id,
      a: portPoint(lay.pos[top.id], 'out'), b: portPoint(lay.pos[low.id], 'in'),
      label: l.kind === 'native' ? LINK_WORDS.native : (w ? `${w.from} → ${w.to} · #${w.seq}` : ''),
      sub: l.kind === 'mailbox' && nativePairs.has(pairKey(l.from, l.to)) ? LINK_WORDS.native : '',
      arrow: w ? (back ? 'start' : 'end') : null, flow: !!w, back,
      down: l.kind === 'mailbox' && (p.state === 'down' || q.state === 'down'),
    };
  }
  return { nodes, edges, extent: lay.extent };
}

const NODE_FIELDS = ['title', 'state', 'detail', 'note'];
const EDGE_FIELDS = ['kind', 'from', 'to', 'label', 'sub', 'arrow', 'flow', 'back', 'down'];

/** True when two points sit at the same place. @complexity O(1)  @alloc none */
function samePoint(p, q) {
  return p.x === q.x && p.y === q.y;
}

/** True when two node views would draw the same. @complexity O(1)  @alloc none */
function sameNode(p, q) {
  return NODE_FIELDS.every((f) => p[f] === q[f]) && samePoint(p.pos, q.pos);
}

/** True when two edge views would draw the same. @complexity O(1)  @alloc none */
function sameEdge(p, q) {
  return EDGE_FIELDS.every((f) => p[f] === q[f]) && samePoint(p.a, q.a) && samePoint(p.b, q.b);
}

/**
 * What changed from one board view to the next, by id: nodes and edges to
 * add, update (moved, retitled, restated) and remove.
 * @interacts  none; pure
 * @complexity O(n + e) over n nodes and e edges in both views  @alloc six lists, returned
 */
export function diffBoard(prev, next) {
  const ops = { addNodes: [], updateNodes: [], removeNodes: [], addEdges: [], updateEdges: [], removeEdges: [] };
  for (const id of Object.keys(prev.nodes)) if (!Object.hasOwn(next.nodes, id)) ops.removeNodes.push(id);
  for (const [id, v] of Object.entries(next.nodes)) {
    if (!Object.hasOwn(prev.nodes, id)) ops.addNodes.push(v);
    else if (!sameNode(prev.nodes[id], v)) ops.updateNodes.push(v);
  }
  for (const id of Object.keys(prev.edges)) if (!Object.hasOwn(next.edges, id)) ops.removeEdges.push(id);
  for (const [id, v] of Object.entries(next.edges)) {
    if (!Object.hasOwn(prev.edges, id)) ops.addEdges.push(v);
    else if (!sameEdge(prev.edges[id], v)) ops.updateEdges.push(v);
  }
  return ops;
}

/**
 * An empty board drawn through `kit`: { kit, nodes, edges, view }. kit has
 * createNode(view) and createEdge(view), each returning a handle with
 * update(view) and remove(). createKit(doc, canvas) is the DOM kit.
 * @complexity O(1)  @alloc two empty maps and an empty view
 */
export function createBoard(kit) {
  return { kit, nodes: new Map(), edges: new Map(), view: { nodes: nameMap(), edges: nameMap(), extent: { w: 0, h: 0 } } };
}

/**
 * Bring `board` to `feed`, laid out inside `width` (see layoutLevels): add,
 * move and remove nodes and edges by id through board.kit, never rebuilding
 * what stays (C5). Returns the diff it applied.
 * @interacts  calls board.kit and the handles it made; writes board.nodes,
 *             board.edges and board.view
 * @complexity O(n log n + l + r) for boardView, plus O(c) kit calls for c changes
 * @alloc      one handle per added node or edge; each removed one is dropped
 *             from the maps after its remove()
 */
export function patchBoard(board, feed, width) {
  const next = boardView(feed, width);
  const ops = diffBoard(board.view, next);
  for (const id of ops.removeEdges) {
    board.edges.get(id).remove();
    board.edges.delete(id);
  }
  for (const id of ops.removeNodes) {
    board.nodes.get(id).remove();
    board.nodes.delete(id);
  }
  for (const v of ops.addNodes) board.nodes.set(v.id, board.kit.createNode(v));
  for (const v of ops.updateNodes) board.nodes.get(v.id).update(v);
  for (const v of ops.addEdges) board.edges.set(v.id, board.kit.createEdge(v));
  for (const v of ops.updateEdges) board.edges.get(v.id).update(v);
  board.view = next;
  return ops;
}

/**
 * Where an edge's words go: `label` over the line's middle (beside it for a
 * reports_to hint), and `sub`, its second line, LABEL_DROP under the
 * middle, so the two never sit on each other.
 * Model: Claude Opus 5.5 (the BOARD fixer, round 1), 2026-10-14. Status: unreviewed.
 * @interacts  none; pure
 * @complexity O(1)  @alloc two small objects
 * @returns {{ label: {x, y, anchor}, sub: {x, y, anchor} }}
 */
export function labelPoints(v) {
  const mx = (v.a.x + v.b.x) / 2;
  const my = (v.a.y + v.b.y) / 2;
  if (v.kind === 'reports_to') {
    const x = mx + CONFIG.HINT_LABEL_SHIFT;
    return { label: { x, y: my, anchor: 'start' }, sub: { x, y: my + CONFIG.LABEL_DROP, anchor: 'start' } };
  }
  return {
    label: { x: mx, y: my - CONFIG.LABEL_LIFT, anchor: 'middle' },
    sub: { x: mx, y: my + CONFIG.LABEL_DROP, anchor: 'middle' },
  };
}

/**
 * One edge view as SVG: a path and its words, on two lines where it has a
 * second (labelPoints). A reports_to hint goes under every other wire
 * (first in the layer), thin, with its words beside it.
 * @interacts  inserts into canvas.wires; remove() takes all three elements out
 * @complexity O(1) per call  @alloc one path and two text elements
 * @returns {{ path, label, sub, update(view), remove() }}
 */
export function drawEdge(doc, canvas, view) {
  const path = svg(doc, 'path', { class: 'tc-wire' });
  const label = svg(doc, 'text', { class: 'tc-wire-label' });
  const sub = svg(doc, 'text', { class: 'tc-wire-label' });
  if (view.kind === 'reports_to') {
    const after = canvas.wires.firstChild ? canvas.wires.firstChild.nextSibling : null;
    canvas.wires.insertBefore(path, after);
    canvas.wires.insertBefore(label, after);
    canvas.wires.insertBefore(sub, after);
  } else {
    canvas.wires.append(path, label, sub);
  }
  const place = (text, at, words) => {
    text.setAttribute('text-anchor', at.anchor);
    text.setAttribute('x', String(at.x));
    text.setAttribute('y', String(at.y));
    text.textContent = words || '';
  };
  const edge = {
    path, label, sub,
    update(v) {
      const hint = v.kind === 'reports_to';
      path.setAttribute('d', hint ? hintPath(v.a, v.b) : wirePath(v.a, v.b));
      path.setAttribute('class', ['tc-wire', `kind-${v.kind}`, v.flow && 'flow', v.back && 'back', v.down && 'down'].filter(Boolean).join(' '));
      path.removeAttribute('marker-end');
      path.removeAttribute('marker-start');
      if (v.arrow) path.setAttribute(`marker-${v.arrow}`, 'url(#tc-arrow)');
      const at = labelPoints(v);
      place(label, at.label, v.label);
      place(sub, at.sub, v.sub);
    },
    remove() {
      path.remove();
      label.remove();
      sub.remove();
    },
  };
  edge.update(view);
  return edge;
}

/**
 * The DOM kit patchBoard draws through: nodes with createNode, edges with
 * drawEdge, both on `canvas`.
 * @interacts  see createNode and drawEdge
 * @complexity O(1) per call  @alloc one node or edge subtree per create
 */
export function createKit(doc, canvas) {
  return {
    createNode(v) {
      const node = createNode(doc, canvas, { ...v, hue: HUES[hueFor(v.id)] });
      return {
        node,
        update(n) {
          node.moveTo(n.pos);
          node.setTitle(n.title);
          node.setNote(n.note);
          node.setState(n.state, n.detail);
        },
        remove() { node.remove(); },
      };
    },
    createEdge(v) { return drawEdge(doc, canvas, v); },
  };
}

/**
 * Scale and offset that fit a board of `extent` inside width x height with
 * `padding` to spare, centered, never enlarged and never under MIN_FIT_SCALE
 * (so no text drops under MIN_TEXT_PX). A board still taller than the
 * canvas at that scale starts at the top and the canvas scrolls down; one
 * laid out at layoutWidth(width) never runs past the width.
 * @complexity O(1)  @alloc one object
 * @returns {{ x, y, k }}
 */
export function fitTransform(width, height, extent, padding) {
  if (!extent.w || !extent.h) return { x: 0, y: 0, k: 1 };
  const k = Math.max(CONFIG.MIN_FIT_SCALE, Math.min(1, (width - padding) / extent.w, (height - padding) / extent.h));
  return { x: Math.max(0, (width - extent.w * k) / 2), y: Math.max(0, (height - extent.h * k) / 2), k };
}

/**
 * Keep a board laid out to its canvas. The canvas's size comes from the
 * ResizeObserver's own entry, never from a layout read after a patch, so a
 * poll that changes the board forces no layout (round 1, LOW-4). draw(feed)
 * lays the feed out at the canvas's width (layoutLevels wraps it) and
 * patches the board; a resize lays the last feed out again. The view and its
 * wire layer take the board's extent as their size, so the canvas scrolls
 * down as far as the board goes and never sideways. `Observer` is
 * ResizeObserver on a page; a test passes a fake.
 * Model: Claude Opus 5.5 (the BOARD fixer, round 1), 2026-10-14. Status: unreviewed.
 * @interacts  observes canvas.scroll from start() until stop() (the page
 *             calls them on load and pageshow, and on pagehide); writes
 *             canvas.view's transform, width and height and canvas.wires'
 *             width and height; calls patchBoard, and through it board.kit
 * @complexity one draw or resize: patchBoard's O(n log n + l + r)
 * @alloc      one observer for the fit's life; holds the last feed and the
 *             last size, each replaced by the next
 * @returns {{ draw(feed), start(), stop() }}
 */
export function createFit(canvas, board, { padding, Observer }) {
  let size = null;
  let feed = null;
  const apply = () => {
    if (!size) return;
    if (feed) patchBoard(board, feed, layoutWidth(size.width));
    const { extent } = board.view;
    const t = fitTransform(size.width, size.height, extent, padding);
    canvas.view.style.width = `${extent.w}px`;
    canvas.view.style.height = `${extent.h}px`;
    canvas.view.style.transform = `translate(${t.x}px, ${t.y}px) scale(${t.k})`;
    canvas.wires.setAttribute('width', String(Math.max(CONFIG.MIN_LAYER_PX, extent.w)));
    canvas.wires.setAttribute('height', String(Math.max(CONFIG.MIN_LAYER_PX, extent.h)));
  };
  const observer = new Observer((entries) => {
    const box = entries[entries.length - 1].contentRect;
    size = { width: box.width, height: box.height };
    apply();
  });
  return {
    draw(next) {
      feed = next;
      apply();
    },
    start() { observer.observe(canvas.scroll); },
    stop() { observer.disconnect(); },
  };
}
