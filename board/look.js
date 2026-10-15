/**
 * look.js: drawing tools for the board look. Builds the window frame, the
 * canvas, session nodes, ports and wires as DOM and SVG elements. The live
 * board's layer is pure: layoutLevels places a C5 feed's nodes in levels,
 * wrapped to a width, boardView turns a feed into what to draw, and
 * diffBoard says what changed between two views. patchBoard applies a diff
 * through a drawing kit (createKit for the DOM, or a test's fake), so the
 * board is never rebuilt. createFit keeps a board laid out to its canvas.
 * Round 2: every wire and connector is routed round the boxes (routeTree,
 * routeAround) and every label is placed clear of boxes and other labels
 * (placeLabels); the routing section states the one rule. Each root's tree
 * starts with a heading, rootsList and createRoots make the list of roots
 * at the top of the page, and on a phone createFit draws outlineView's
 * outline instead of the graph.
 *
 * @interacts  creates elements under the container the caller passes in; uses
 *             theme.css class names; applyLook writes data-theme on <html>;
 *             never touches innerHTML, storage or globals. layoutLevels,
 *             boardView, diffBoard, roleTitle, hueFor, pillText,
 *             layoutWidth, levelPort, routeTree, routeAround, roundedPath,
 *             placeLabels, rootsList, outlineView and fitTransform read
 *             only their arguments; patchBoard writes only the board object
 *             it is given and calls only its kit; createRoots calls back on
 *             a click; createFit observes the canvas's stage through the
 *             observer it is given and writes the window's data-view, the
 *             frame's height and the view's size and transform, and its
 *             jump and the kit's reveals scroll the page; createPoller asks for the feed through
 *             the fetch and timers it is given and reports through its two
 *             callbacks
 * @deps       browser DOM and SVG for the drawing functions; the pure layer
 *             needs neither (node --test runs it with no DOM library)
 * @complexity every drawing function is O(1) per call, or O(p) over a run's
 *             p points; a board with n nodes and w wires costs O(n + w) to
 *             build. layoutLevels is O(n log n + l + r) over n feed nodes, l
 *             links and r recent wires (C5: n tens, l tens, r <= 50), the
 *             log from the sort by name; boardView and patchBoard add
 *             routeAround's search per routed pair, O(g log g) over its g
 *             states (thousands on a real board), and placeLabels; diffBoard
 *             is O(n + e) over two views' nodes and e edges, times their
 *             points; outlineView is O(n log n + r log r); rootsList and
 *             pillText are O(n) after the sort; createPoller is O(1) per poll
 * @alloc      one element tree, one connector path and one heading per
 *             node, one path with its title and one label with its backing
 *             per wire, each released by its own remove(); the outline's
 *             element tree, replaced when the outline changes; one button
 *             per root in the roots list, replaced when the roots change.
 *             removeBoard clears the DOM
 *             under a parent and nothing else: a board object from
 *             createBoard goes with it, since nothing else holds its
 *             handles. That board holds one handle per drawn node and edge,
 *             dropped when patchBoard removes it, and the last full view
 *             (board.view), replaced on every patch
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
  // drawWire's label sits this far over its wire's middle.
  LABEL_LIFT: 7,
  // Model: Claude Opus 5.5 (the BOARD lane agent), 2026-10-14. Status: unreviewed.
  // layoutLevels: the gap between two boxes in one row; between a parent and
  // its children (the band where its connectors turn, with room for a wire
  // label clear of both rows); between two wrapped rows of one parent's
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
  // Model: Claude Opus 5.5 (the BOARD fixer, round 2), 2026-10-14. Status: unreviewed.
  // Item 5: each root's tree starts with a heading naming its root, as wide
  // as the tree: HEAD_H tall (an 11 px line and its rule), then HEAD_GAP
  // before the root's box (room for the root's in port ring, which stands
  // PORT_SIZE / 2 over the box).
  HEAD_H: 20,
  HEAD_GAP: 8,
  // a2's direction: under this stage width (about a 600 px phone, less the
  // page's two 16 px margins, the window's borders and the body's 8 px
  // padding) the board draws the outline view instead of the graph. Each
  // outline row is indented OUTLINE_INDENT px per level under its parent.
  OUTLINE_BELOW_PX: 560,
  OUTLINE_INDENT: 16,
  // A message at most this many seconds old flows on its wire. The feed's
  // WRITING_WINDOW_S, so the wire moves while its sender reads as writing.
  FLOW_AGE_S: 10,
  // Model: Claude Opus 5.5 (the BOARD fixer, round 2), 2026-10-14. Status: unreviewed.
  // Routing (round 2, item 2, and a2's direction). A routed wire keeps
  // ROUTE_CLEAR px from every box; a bend costs as much as ROUTE_TURN_COST
  // px of length, so a route takes few bends; a tree's wire to a wrapped
  // row runs down the side of its parent's block ROUTE_GUTTER px out from
  // it, under half of LAYOUT_COL_GAP and of LAYOUT_MARGIN, so it keeps
  // clear of the block beside it too. A bend is drawn rounded, with a radius
  // of at most ROUTE_CLEAR, so the curve stays as clear as the corner.
  ROUTE_CLEAR: 10,
  ROUTE_TURN_COST: 40,
  ROUTE_GUTTER: 12,
  // A routed piece that runs alongside a tree connector, within ROUTE_CLEAR
  // of it, costs this many times its length, so a wire between trees takes
  // the gaps between them and crosses a connector rather than shadowing it.
  ROUTE_ALONG_COST: 4,
  // Labels (round 2, item 3). A label's box is LABEL_CHAR_W px per
  // character (an 11 px mono glyph is about 6.6 px wide; rounded up so the
  // box never undercuts the drawn words) plus LABEL_PAD each side, and
  // LABEL_H tall (11 px words and their halo). A label sits beside its
  // wire, LABEL_GAP clear of it, never on it (the dashes would show through
  // the spaces between its words). Spots to try sit LABEL_STEP px apart
  // along the wire and out from it, at most LABEL_REACH out (half a box's
  // height and a label's: room to clear a box beside a short wire), and
  // two labels keep LABEL_GAP px apart.
  LABEL_CHAR_W: 7,
  LABEL_PAD: 4,
  LABEL_H: 16,
  LABEL_STEP: 8,
  LABEL_REACH: 48,
  LABEL_GAP: 2,
  // hueFor's string hash step: a small odd prime spreads short names.
  HUE_HASH_STEP: 31,
  // Model: Claude Opus 5.5 (the BOARD fixer, round 1), 2026-10-14. Status: unreviewed.
  // fitTransform never shrinks a board below this: the scale at which the
  // board's smallest text is MIN_TEXT_PX. With both at 11 it is 1, so the
  // board never shrinks; layoutLevels wraps it to the width instead, its
  // frame grows to its height and the page scrolls down (round 2).
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
 * Where a node's port sits in board coordinates, for the look kit's plain
 * nodes and wires (createNode, drawWire). side: 'in' (left) or 'out' (right).
 * @complexity O(1)  @alloc one object
 */
export function portPoint(pos, side) {
  return { x: pos.x + (side === 'in' ? 0 : CONFIG.NODE_W), y: pos.y + CONFIG.NODE_H / 2 };
}

/**
 * Where a node's port sits on the live board, whose ports follow its
 * top-down levels (round 2, a2's direction): side 'in' is the middle of the
 * top edge, 'out' the middle of the bottom edge, so a parent's connector
 * and its mail to a child run down.
 * Model: Claude Opus 5.5 (the BOARD fixer, round 2), 2026-10-14. Status: unreviewed.
 * @complexity O(1)  @alloc one object
 */
export function levelPort(pos, side) {
  return { x: pos.x + CONFIG.NODE_W / 2, y: pos.y + (side === 'in' ? 0 : CONFIG.NODE_H) };
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
 * Footer cells. Each item is { text }, { spacer: true }, or { legend, text }:
 * a legend is a row of its own, the first line of the footer, never over
 * the board (round 2, item 4). Replaces what was there. Cells wrap to a new
 * line on a narrow screen instead of cutting words off (round 2, item 6).
 * Model: Claude Opus 5.5 (the BOARD fixer, round 2), 2026-10-14. Status: unreviewed.
 * @complexity O(k) for k items  @alloc k spans
 */
export function setFooter(doc, foot, items) {
  foot.replaceChildren(...items.map((it) => {
    if (it.spacer) return el(doc, 'span', 'tc-sp');
    if (it.legend) return el(doc, 'span', `tc-legend tc-legend-${it.legend}`, it.text);
    return el(doc, 'span', 'tc-cell', it.text);
  }));
}

/**
 * Canvas: a stage holding the frame the board draws in, which holds the
 * view (a wire layer in SVG and a node layer), and the outline a phone
 * draws instead (a2's direction; theme.css shows one of the two by the
 * window's data-view). The frame grows to the
 * board's laid out height and the page scrolls, never sideways (round 2,
 * item 1); nothing sits over it (the legend is in the footer, item 4).
 * createFit watches the stage, which keeps the width the board may use.
 * The wire layer ends with a group for the wires' labels, so every label
 * is drawn over every wire (round 2).
 * @interacts  appends to parent
 * @complexity O(1)  @alloc one canvas subtree with an arrow marker def
 * @returns {{ root, frame, view, wires, labels, outline }}
 */
export function createCanvas(doc, parent) {
  const root = el(doc, 'div', 'tc-stage');
  const frame = el(doc, 'div', 'tc-canvas');
  const view = el(doc, 'div', 'tc-view');
  const wires = svg(doc, 'svg', { class: 'tc-wires', width: CONFIG.WIRE_SPACE, height: CONFIG.WIRE_SPACE });
  const defs = svg(doc, 'defs');
  const marker = svg(doc, 'marker', {
    id: 'tc-arrow', viewBox: '0 0 10 10', refX: CONFIG.ARROW_BACKOFF, refY: 5,
    markerWidth: CONFIG.ARROW_SIZE, markerHeight: CONFIG.ARROW_SIZE, orient: 'auto-start-reverse',
  });
  marker.append(svg(doc, 'path', { d: 'M 0 0 L 10 5 L 0 10 z', class: 'tc-arrow' }));
  defs.append(marker);
  const labels = svg(doc, 'g', { class: 'tc-labels' });
  wires.append(defs, labels);
  view.append(wires);
  frame.append(view);
  const outline = el(doc, 'div', 'tc-outline');
  root.append(frame, outline);
  parent.append(root);
  return { root, frame, view, wires, labels, outline };
}

/**
 * The list of roots at the top of the page (round 2, item 5):
 * `2 orchestrators: a, z · 2 peers: p1, p2`, each name a button that calls
 * onJump(name), which brings that tree into view. set(groups) takes
 * rootsList's groups and rebuilds the list only when they change; with no
 * roots it is hidden.
 * Model: Claude Opus 5.5 (the BOARD fixer, round 2), 2026-10-14. Status: unreviewed.
 * @interacts  appends a nav to parent; one click listener per button,
 *             released with its button when the list is rebuilt
 * @complexity O(r) per change over r roots  @alloc one nav; one button per root
 * @returns {{ root, set(groups) }}
 */
export function createRoots(doc, parent, onJump) {
  const root = el(doc, 'nav', 'tc-roots');
  root.setAttribute('aria-label', 'Roots');
  root.hidden = true;
  parent.append(root);
  let shown = null;
  return {
    root,
    set(groups) {
      const key = JSON.stringify(groups);
      if (key === shown) return;
      shown = key;
      const parts = [];
      groups.forEach((g, i) => {
        if (i) parts.push(doc.createTextNode(' · '));
        parts.push(el(doc, 'span', 'tc-roots-words', `${g.words}: `));
        g.ids.forEach((id, j) => {
          if (j) parts.push(doc.createTextNode(', '));
          const b = el(doc, 'button', 'tc-root-btn', id);
          b.type = 'button';
          b.setAttribute('aria-label', `go to ${id}'s tree`);
          b.addEventListener('click', () => onJump(id));
          parts.push(b);
        });
      });
      root.replaceChildren(...parts);
      root.hidden = !groups.length;
    },
  };
}

/**
 * Session node at pos with an in port (ring) and an out port (dot): on the
 * left and right edges (portPoint), or with `levels` on the top and bottom
 * edges (levelPort), as the live board draws them. The
 * title splits at its first ' · ': the name may shorten with an ellipsis,
 * the role words after it never do. A third line holds `note` (a status
 * line, or a reports_to that names nobody); empty, it is hidden.
 * @interacts  appends to canvas.view; remove() takes the node out again
 * @complexity O(1)  @alloc one node subtree
 * @returns {{ root, pos, setState(state, detail), setTitle(text), setNote(text), moveTo(pos), remove() }}
 */
export function createNode(doc, canvas, { title, hue, pos, state, detail, note, levels }) {
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
  const at = levels ? levelPort : portPoint;
  const origin = { x: 0, y: 0 };
  const pin = el(doc, 'span', 'tc-port in');
  pin.title = 'in';
  pin.style.left = `${at(origin, 'in').x - half}px`;
  pin.style.top = `${at(origin, 'in').y - half}px`;
  const pout = el(doc, 'span', 'tc-port out');
  pout.title = 'out';
  pout.style.left = `${at(origin, 'out').x - half}px`;
  pout.style.top = `${at(origin, 'out').y - half}px`;
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
 * Wire from one node's out port to another's in port, with an arrow and a
 * label: the look kit's plain wire between side ports. The live board
 * draws routed edges instead (drawEdge).
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
 * Clear every element under parent. A board object from createBoard still
 * holds its handles and its view; the caller drops it with the elements.
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
 * The legend: what each kind of line on the board means, in words. It is a
 * row of the footer, never over the board (round 2, item 4); `empty` stands
 * in for it while the feed holds no sessions.
 * Model: Claude Opus 5.5 (the BOARD fixer, round 2), 2026-10-14. Status: unreviewed.
 */
export const LEGEND_WORDS = Object.freeze({
  outline: 'outline: each session under the one it reports to · traffic: newest first, arrow toward the reader',
  graph: 'thin line: reports to · dashes, arrow and words: mail now, arrow at the reader · long dash: native, not observed · dotted: no listener',
  empty: 'no sessions yet · send a message or start a listener',
});

/**
 * Words in an edge's title (round 2): a connector whose parent the feed
 * inferred from mail says so, and a quiet mail wire names its pair.
 * Model: Claude Opus 5.5 (the BOARD fixer, round 2), 2026-10-14. Status: unreviewed.
 */
export const TREE_WORDS = Object.freeze({
  inferred: 'inferred from mail',
  mail: 'mail between',
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
 * The tree a C5 feed draws: its nodes by name, each parent's children, and
 * the roots. A node hangs under its `parent` when its level is the
 * parent's plus one (D15, pause BOARD-3); every other node is a root, so a
 * cycle's root is one like any other. Roots and children are in name order.
 * layoutLevels places this tree; outlineView lists it.
 * Model: Claude Opus 5.5 (the BOARD fixer, round 2), 2026-10-14, from
 * layoutLevels' own first walk. Status: unreviewed.
 * @interacts  none; pure
 * @complexity O(n log n) over n nodes, for the sort by name
 * @alloc      a sorted copy of the nodes, a Map of them by name, a Map of
 *             child lists and the roots list, returned
 * @returns {{ nodes: object[], known: Map, kids: Map<string, string[]>, roots: string[] }}
 */
function treeOf(feed) {
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
  return { nodes, known, kids, roots };
}

/**
 * Where a C5 feed's nodes go, inside `width` board px (Infinity, the
 * default, never wraps). Roots in name order, levels top to bottom (C5),
 * on treeOf's tree. A parent sits over its children. The children, each
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
 *
 * Round 2 (item 5): each root's tree starts with a band HEAD_H + HEAD_GAP
 * tall for its heading, as wide as the tree; `heads` says where each
 * heading goes.
 *
 * Round 2 (item 2): `via` says where each child's tree wire turns, for
 * routeTree. A child in its parent's first row is reached across `band`,
 * the middle of the LAYOUT_ROW_GAP under the parent, which no box enters.
 * A child in a wrapped row is reached down `gutter`, a channel beside the
 * parent's block (ROUTE_GUTTER out from its left edge, or the middle of
 * the indent on a phone) that no box enters while the block lasts, then
 * across `band`, the middle of the LAYOUT_WRAP_GAP over its row.
 * @interacts  none; pure
 * @complexity O(n log n) over n nodes: one sort by name, then three walks
 *             that visit each node a fixed number of times
 * @alloc      the returned maps; six Maps and the row lists for the walks,
 *             freed on return
 * @returns {{ pos: {id: {x, y}}, titles: {id: string}, rows: {id: number}, roots: string[],
 *            kids: Map<string, string[]>, via: {id: {band, gutter}}, heads: {id: {x, y, w, h}},
 *            extent: {w, h} }}
 *          rows is each node's depth in its tree; gutter is null for a first-row child;
 *          heads is keyed by root
 */
export function layoutLevels(feed, width = Infinity) {
  const C = CONFIG;
  const { nodes, kids, roots } = treeOf(feed);
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
  // it, where each child's tree wire turns, and where the node's own box
  // sits in it.
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
    lines.forEach((line, li) => {
      let x = ind;
      const band = li ? y - C.LAYOUT_WRAP_GAP / 2 : C.NODE_H + C.LAYOUT_ROW_GAP / 2;
      for (const b of line.items) {
        inBlock.set(b.id, { x, y, band, wrapped: li > 0 });
        x += b.w + C.LAYOUT_COL_GAP;
      }
      areaW = Math.max(areaW, line.w);
      y += line.h + C.LAYOUT_WRAP_GAP;
    });
    ownX.set(id, ind ? 0 : (areaW - C.NODE_W) / 2);
    block.set(id, { w: Math.max(C.NODE_W, ind + areaW), h: y - C.LAYOUT_WRAP_GAP });
  }
  // Walk 3, top down: root trees into rows, each under its heading, then
  // every box by its block.
  const pos = nameMap();
  const via = nameMap();
  const heads = nameMap();
  const origin = new Map();
  const headBand = C.HEAD_H + C.HEAD_GAP;
  let top = C.LAYOUT_MARGIN;
  let widest = 0;
  const rootBlocks = roots.map((r) => ({ id: r, w: block.get(r).w, h: block.get(r).h + headBand }));
  for (const line of packRows(rootBlocks, rootRoom, C.LAYOUT_ROOT_GAP)) {
    let x = C.LAYOUT_MARGIN;
    for (const b of line.items) {
      heads[b.id] = { x, y: top, w: b.w, h: C.HEAD_H };
      origin.set(b.id, { x, y: top + headBand });
      x += b.w + C.LAYOUT_ROOT_GAP;
    }
    widest = Math.max(widest, line.w);
    top += line.h + C.LAYOUT_ROW_GAP;
  }
  for (const id of order) {
    const o = origin.get(id);
    pos[id] = { x: o.x + ownX.get(id), y: o.y };
    const ind = indent.get(id);
    const gutter = ind ? o.x + ind / 2 : o.x - C.ROUTE_GUTTER;
    for (const c of kids.get(id) || []) {
      const at = inBlock.get(c);
      origin.set(c, { x: o.x + at.x, y: o.y + at.y });
      via[c] = { band: o.y + at.band, gutter: at.wrapped ? gutter : null };
    }
  }
  const extent = roots.length
    ? { w: widest + 2 * C.LAYOUT_MARGIN, h: top - C.LAYOUT_ROW_GAP + C.LAYOUT_MARGIN }
    : { w: 0, h: 0 };
  const titles = nameMap();
  for (const n of nodes) titles[n.id] = roleTitle(n);
  return { pos, titles, rows, roots, kids, via, heads, extent };
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

// ---------- routing and labels (round 2, items 2 and 3) ----------
// Model: Claude Opus 5.5 (the BOARD fixer, round 2), 2026-10-14. Status: unreviewed.
//
// The rule, one for the whole board: every wire and connector is a run of
// straight horizontal and vertical pieces that never enters a node box it
// does not end at. The ports belong to the tree. A parent and its child
// (the tree's connector, and their mail on top of it) leave the parent's
// out port, at the middle of its bottom edge, and enter the child's in
// port, at the middle of its top edge, turning only in gaps the layout
// keeps empty (routeTree); so a line into a port always comes from that
// box's parent. Every other pair (siblings, a child and a grandparent, two
// trees, two peers) joins a side of one box to a side of the other by the
// shortest such run with the fewest bends through the room round the
// boxes, keeping ROUTE_CLEAR px from every box and every port
// (routeAround), so two boxes side by side in one row are joined straight
// across. It would rather cross a connector than run alongside one.
// Bends are drawn with round corners of at most ROUTE_CLEAR (roundedPath),
// which keeps the curve as clear as the corner.

/** One step in each direction: right, left, down, up. */
const STEPS = Object.freeze([[1, 0], [-1, 0], [0, 1], [0, -1]]);
/** The step that undoes each of STEPS. */
const BACK = Object.freeze([1, 0, 3, 2]);
/** The sides routeAround joins (right, left), and which way each stub leaves (an index into STEPS). */
const SIDES = Object.freeze([{ dx: 1, dy: 0, dir: 0 }, { dx: -1, dy: 0, dir: 1 }]);

/**
 * Points with repeats and straight-through middles dropped, so each piece
 * is one run and each point left is a bend (or an end).
 * @complexity O(p) over p points  @alloc one list
 */
function simplify(points) {
  const out = [];
  for (const q of points) {
    const last = out[out.length - 1];
    if (last && last.x === q.x && last.y === q.y) continue;
    const before = out[out.length - 2];
    const straight = before && ((before.x === last.x && last.x === q.x && (last.y - before.y) * (q.y - last.y) > 0)
      || (before.y === last.y && last.y === q.y && (last.x - before.x) * (q.x - last.x) > 0));
    if (straight) out[out.length - 1] = q;
    else out.push(q);
  }
  return out;
}

/**
 * The run from a parent's out port to its child's in port, on layoutLevels'
 * `via`: down into the band under the parent and across to the child (a
 * first-row child), or across to the gutter beside the parent's block,
 * down it, and across the band over the child's row (a wrapped child).
 * Every turn sits in a gap the layout keeps empty, so no box is entered.
 * @interacts  none; pure
 * @complexity O(1)  @alloc one list of at most six points
 */
export function routeTree(lay, parent, child) {
  const out = levelPort(lay.pos[parent], 'out');
  const into = levelPort(lay.pos[child], 'in');
  const v = lay.via[child];
  if (v.gutter === null) return simplify([out, { x: out.x, y: v.band }, { x: into.x, y: v.band }, into]);
  const drop = out.y + CONFIG.LAYOUT_ROW_GAP / 2;
  return simplify([
    out, { x: out.x, y: drop }, { x: v.gutter, y: drop }, { x: v.gutter, y: v.band }, { x: into.x, y: v.band }, into,
  ]);
}

/**
 * A binary min-heap of [cost, ...] entries, ordered by the first item.
 * @complexity O(log k) per push and pop over k entries  @alloc one list
 */
function createHeap() {
  const a = [];
  const up = (i) => {
    while (i > 0) {
      const parent = (i - 1) >> 1;
      if (a[parent][0] <= a[i][0]) return;
      [a[parent], a[i]] = [a[i], a[parent]];
      i = parent;
    }
  };
  const down = (i) => {
    for (;;) {
      const l = 2 * i + 1;
      const r = l + 1;
      let m = i;
      if (l < a.length && a[l][0] < a[m][0]) m = l;
      if (r < a.length && a[r][0] < a[m][0]) m = r;
      if (m === i) return;
      [a[m], a[i]] = [a[i], a[m]];
      i = m;
    }
  };
  return {
    get size() { return a.length; },
    push(item) { a.push(item); up(a.length - 1); },
    pop() {
      const top = a[0];
      const last = a.pop();
      if (a.length) {
        a[0] = last;
        down(0);
      }
      return top;
    },
  };
}

/**
 * The run between two boxes that enters no obstacle: the shortest one,
 * counting each bend as ROUTE_TURN_COST px, from the left or right side of
 * `from` to the left or right side of `to` (never a port: those belong to
 * the tree). It searches (A*) the lines ROUTE_CLEAR px out from every
 * obstacle's edges, the middles between those lines, the two boxes'
 * middle heights and a ring LAYOUT_MARGIN / 2 inside the board's edge,
 * which a layoutLevels board keeps empty, so a run always exists there. A
 * stub ROUTE_CLEAR long joins each end to its box's edge. `obstacles` must
 * hold `from` and `to` themselves (the same objects), so no run crosses its
 * own box either, and may hold more (boardView adds every port). `along`
 * holds runs to keep away from (the tree's connectors): a piece that lies
 * within ROUTE_CLEAR of one of their pieces, the same way, costs
 * ROUTE_ALONG_COST times its length. With no free side on a box, or no run (neither happens on a
 * layoutLevels board), it returns the straight line from the upper box's
 * bottom to the lower's top.
 * @interacts  none; pure
 * @complexity O(g log g) over the g = 4 * X * Y search states, X and Y the
 *             line counts (each at most 4b + 6 over b obstacles), with an
 *             O(b + a) check per state over a pieces of `along`; b and a
 *             are tens on a real board
 * @alloc      the line lists, a cache of X * Y free flags, and the search's
 *             heap and maps, all freed on return; the returned points
 * @returns {{x, y}[]}
 */
export function routeAround(obstacles, from, to, extent, along = []) {
  const C = CONFIG.ROUTE_CLEAR;
  const TURN = CONFIG.ROUTE_TURN_COST;
  const shadows = along.flatMap((run) => run.slice(1).map((q, i) => ({ p: run[i], q })));
  // True when the piece between two points runs alongside a piece of `along`.
  const alongside = (a, b) => shadows.some(({ p, q }) => (a.y === b.y
    ? p.y === q.y && Math.abs(p.y - a.y) < C && Math.min(Math.max(a.x, b.x), Math.max(p.x, q.x)) > Math.max(Math.min(a.x, b.x), Math.min(p.x, q.x))
    : p.x === q.x && Math.abs(p.x - a.x) < C && Math.min(Math.max(a.y, b.y), Math.max(p.y, q.y)) > Math.max(Math.min(a.y, b.y), Math.min(p.y, q.y))));
  const ring = CONFIG.LAYOUT_MARGIN / 2;
  const lines = (base) => {
    const sorted = [...new Set(base)].sort((p, q) => p - q);
    const all = sorted.flatMap((v, i) => (i ? [(sorted[i - 1] + v) / 2, v] : [v]));
    return [...new Set(all)].sort((p, q) => p - q);
  };
  const xs = lines([ring, extent.w - ring, ...obstacles.flatMap((o) => [o.x - C, o.x + o.w + C])]);
  const ys = lines([ring, extent.h - ring, from.y + from.h / 2, to.y + to.h / 2,
    ...obstacles.flatMap((o) => [o.y - C, o.y + o.h + C])]);
  const xAt = new Map(xs.map((v, i) => [v, i]));
  const yAt = new Map(ys.map((v, i) => [v, i]));
  const ny = ys.length;
  const inside = (o, x, y) => x > o.x - C && x < o.x + o.w + C && y > o.y - C && y < o.y + o.h + C;
  const flags = new Uint8Array(xs.length * ny);
  const free = (ix, iy) => {
    const k = ix * ny + iy;
    if (!flags[k]) flags[k] = obstacles.some((o) => inside(o, xs[ix], ys[iy])) ? 2 : 1;
    return flags[k] === 1;
  };
  // Between two neighboring lines a piece lies wholly in or out of each
  // obstacle's reach, so its middle says whether it enters one.
  const pieceFree = (ix, iy, jx, jy) => !obstacles.some((o) => inside(o, (xs[ix] + xs[jx]) / 2, (ys[iy] + ys[jy]) / 2));
  const ends = (box) => SIDES.map((side) => {
    const edge = { x: side.dx > 0 ? box.x + box.w : box.x, y: box.y + box.h / 2 };
    return { edge, ix: xAt.get(side.dx > 0 ? box.x + box.w + C : box.x - C), iy: yAt.get(edge.y), dir: side.dir };
  }).filter((e) => e.ix !== undefined && e.iy !== undefined && free(e.ix, e.iy));
  const straight = () => {
    const [hi, lo] = from.y <= to.y ? [from, to] : [to, from];
    const line = [{ x: hi.x + hi.w / 2, y: hi.y + hi.h }, { x: lo.x + lo.w / 2, y: lo.y }];
    return from === hi ? line : line.reverse();
  };
  const starts = ends(from);
  const goals = ends(to);
  if (!starts.length || !goals.length) return straight();
  const guess = (ix, iy) => Math.min(...goals.map((g) => Math.abs(xs[ix] - xs[g.ix]) + Math.abs(ys[iy] - ys[g.iy])));
  const keyOf = (ix, iy, dir) => (ix * ny + iy) * STEPS.length + dir;
  const heap = createHeap();
  const cost = new Map();
  const prev = new Map();
  const startAt = new Map();
  for (const s of starts) {
    const k = keyOf(s.ix, s.iy, s.dir);
    cost.set(k, C);
    startAt.set(k, s);
    heap.push([C + guess(s.ix, s.iy), C, k]);
  }
  let best = Infinity;
  let found = null;
  while (heap.size) {
    const [f, g, k] = heap.pop();
    if (f >= best) break;
    if (g > cost.get(k)) continue;
    const dir = k % STEPS.length;
    const cell = (k - dir) / STEPS.length;
    const iy = cell % ny;
    const ix = (cell - iy) / ny;
    for (const goal of goals) {
      if (goal.ix !== ix || goal.iy !== iy) continue;
      const total = g + C + (dir === BACK[goal.dir] ? 0 : TURN);
      if (total < best) {
        best = total;
        found = { k, goal };
      }
    }
    STEPS.forEach(([dx, dy], d) => {
      if (d === BACK[dir]) return;
      const jx = ix + dx;
      const jy = iy + dy;
      if (jx < 0 || jy < 0 || jx >= xs.length || jy >= ny || !free(jx, jy) || !pieceFree(ix, iy, jx, jy)) return;
      const length = Math.abs(xs[jx] - xs[ix]) + Math.abs(ys[jy] - ys[iy]);
      const weight = alongside({ x: xs[ix], y: ys[iy] }, { x: xs[jx], y: ys[jy] }) ? CONFIG.ROUTE_ALONG_COST : 1;
      const next = g + length * weight + (d === dir ? 0 : TURN);
      const nk = keyOf(jx, jy, d);
      if (next >= (cost.has(nk) ? cost.get(nk) : Infinity)) return;
      cost.set(nk, next);
      prev.set(nk, k);
      heap.push([next + guess(jx, jy), next, nk]);
    });
  }
  if (!found) return straight();
  const run = [];
  for (let k = found.k; k !== undefined; k = prev.get(k)) {
    const cell = (k - (k % STEPS.length)) / STEPS.length;
    run.push({ x: xs[(cell - (cell % ny)) / ny], y: ys[cell % ny] });
    if (!prev.has(k)) run.push(startAt.get(k).edge);
  }
  run.reverse();
  run.push(found.goal.edge);
  return simplify(run);
}

/**
 * SVG path data for a run of points, each bend rounded with a radius of at
 * most `radius` (and at most half of either piece it joins).
 * @complexity O(p) over p points  @alloc one string
 */
export function roundedPath(points, radius) {
  if (points.length < 2) return '';
  const toward = (from, to, r) => {
    const len = Math.hypot(to.x - from.x, to.y - from.y);
    return { x: from.x + ((to.x - from.x) * r) / len, y: from.y + ((to.y - from.y) * r) / len };
  };
  let d = `M ${points[0].x} ${points[0].y}`;
  for (let i = 1; i < points.length - 1; i += 1) {
    const [p, q, n] = [points[i - 1], points[i], points[i + 1]];
    const r = Math.min(radius, Math.hypot(q.x - p.x, q.y - p.y) / 2, Math.hypot(n.x - q.x, n.y - q.y) / 2);
    const a = toward(q, p, r);
    const b = toward(q, n, r);
    d += ` L ${a.x} ${a.y} Q ${q.x} ${q.y} ${b.x} ${b.y}`;
  }
  const last = points[points.length - 1];
  return `${d} L ${last.x} ${last.y}`;
}

/** True when two boxes overlap with `gap` px to spare. @complexity O(1)  @alloc none */
function boxesMeet(p, q, gap) {
  return p.x < q.x + q.w + gap && q.x < p.x + p.w + gap && p.y < q.y + q.h + gap && q.y < p.y + p.h + gap;
}

/**
 * Points along a run, `step` px apart by length, starting at its middle and
 * moving out to either end in turn; each says whether its piece is level.
 * @complexity O(p + L / step) over p points and length L  @alloc one list
 */
function spotsAlong(points, step) {
  const lengths = [0];
  for (let i = 1; i < points.length; i += 1) {
    lengths.push(lengths[i - 1] + Math.hypot(points[i].x - points[i - 1].x, points[i].y - points[i - 1].y));
  }
  const total = lengths[lengths.length - 1];
  const at = (s) => {
    let i = 1;
    while (i < lengths.length - 1 && lengths[i] < s) i += 1;
    const piece = lengths[i] - lengths[i - 1];
    const t = piece ? (s - lengths[i - 1]) / piece : 0;
    return {
      x: points[i - 1].x + (points[i].x - points[i - 1].x) * t,
      y: points[i - 1].y + (points[i].y - points[i - 1].y) * t,
      level: points[i].y === points[i - 1].y,
    };
  };
  const out = [];
  for (let k = 0; k * step <= total / 2; k += 1) {
    out.push(at(total / 2 + k * step));
    if (k) out.push(at(total / 2 - k * step));
  }
  return out;
}

/**
 * Where each labeled edge's words go (round 2, item 3): a box beside a spot
 * along its run, just over a level piece or just right of an upright one
 * (LABEL_GAP clear of the wire), the middle of the run first, then moving
 * out along the wire; then the other side; then a step further out each
 * time, up to LABEL_REACH (for a short wire between two close boxes),
 * until the box is inside the board, clear of every box in `boxes`, and
 * LABEL_GAP clear of every piece of every edge's run (its own too, so it
 * never sits on a wire) and of every label already placed. Where no such
 * spot exists (a short wire that another wire crosses), the same search
 * runs again without the wires: drawEdge puts every label on an opaque
 * backing above every wire, so one that must sit on a wire still reads.
 * Labels are placed newest message first (highest seq), so the newest wire
 * gets the best spot. An edge whose label fits nowhere gets null: its
 * words stay in its title.
 * @interacts  none; pure
 * @complexity O(e * s * o * (b + w + e)) over e labeled edges, s spots
 *             along each, o = 2 * LABEL_REACH / LABEL_STEP offsets out from
 *             it, b boxes and w pieces of all the edges' runs; at most two
 *             searches per label
 * @alloc      one box per placed label and the returned map
 * @returns {{id: {x, y, w, h} | null}}  only edges with a label have a key
 */
export function placeLabels(edges, boxes, extent) {
  const C = CONFIG;
  const placed = [];
  const out = nameMap();
  const pieces = Object.values(edges).flatMap((e) => e.points.slice(1).map((q, i) => {
    const p = e.points[i];
    return { x: Math.min(p.x, q.x), y: Math.min(p.y, q.y), w: Math.abs(q.x - p.x), h: Math.abs(q.y - p.y) };
  }));
  const order = Object.values(edges).filter((e) => e.label).sort((p, q) => (q.seq - p.seq) || byName(p.id, q.id));
  for (const e of order) {
    const w = [...e.label].length * C.LABEL_CHAR_W + 2 * C.LABEL_PAD;
    const h = C.LABEL_H;
    const spots = spotsAlong(e.points, C.LABEL_STEP);
    // The box's middle sits `clear` out from the wire: half the box across
    // it, plus LABEL_GAP, plus k steps.
    const at = (spot, side, k) => {
      const out = side * ((spot.level ? h : w) / 2 + C.LABEL_GAP + k * C.LABEL_STEP);
      return { x: spot.x - w / 2 + (spot.level ? 0 : out), y: spot.y - h / 2 + (spot.level ? -out : 0), w, h };
    };
    const fits = (b, offWires) => b.x >= 0 && b.y >= 0 && b.x + w <= extent.w && b.y + h <= extent.h
      && !boxes.some((o) => boxesMeet(b, o, 0)) && !(offWires && pieces.some((o) => boxesMeet(b, o, C.LABEL_GAP)))
      && !placed.some((o) => boxesMeet(b, o, C.LABEL_GAP));
    out[e.id] = null;
    for (const offWires of [true, false]) {
      for (let k = 0; k * C.LABEL_STEP <= C.LABEL_REACH && !out[e.id]; k += 1) {
        for (const side of [1, -1]) {
          const box = spots.map((spot) => at(spot, side, k)).find((b) => fits(b, offWires));
          if (box) {
            placed.push(box);
            out[e.id] = box;
            break;
          }
        }
      }
    }
  }
  return out;
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

// ---------- roots, headings and the outline (round 2, item 5, and a2's phone view) ----------
// Model: Claude Opus 5.5 (the BOARD fixer, round 2), 2026-10-14. Status: unreviewed.

/** Words for the outline and the roots list. Every one is a word, never a color. */
export const OUTLINE_WORDS = Object.freeze({
  traffic: 'recent traffic',
  noTraffic: 'no mail yet',
  session: 'session',
  ago: 'ago',
});
// Units for a message's age in the traffic list.
const S_PER_M = 60;
const S_PER_H = 3600;
const S_PER_D = 86400;
// The roots list names roles in this order; any other role comes after, by name.
const ROOT_ROLE_ORDER = Object.freeze(['orchestrator', 'peer', 'worker']);

/** How many nodes hang in `id`'s tree, itself included. @complexity O(t) over t nodes in it  @alloc one stack */
function treeSize(kids, id) {
  let count = 0;
  for (const stack = [id]; stack.length;) {
    count += 1;
    stack.push(...(kids.get(stack.pop()) || []));
  }
  return count;
}

/**
 * A root's heading: its title, plus how many sessions its tree holds when
 * that is more than one (`z · orchestrator · 4 sessions`).
 * @complexity O(1)  @alloc one string
 */
function headWords(title, size) {
  return size > 1 ? `${title} · ${size} ${OUTLINE_WORDS.session}s` : title;
}

/** A count and a word, plural past one (`2 orchestrators`). @complexity O(1)  @alloc one string */
function counted(n, word) {
  return `${n} ${word}${n === 1 ? '' : 's'}`;
}

/**
 * The roots of a feed's tree, grouped by role for the list at the top of
 * the page (round 2, item 5): `2 orchestrators: a, z · 2 peers: p1, p2`.
 * Orchestrators first, then peers, then workers, then any other role.
 * @interacts  none; pure
 * @complexity O(n log n) over n nodes, for treeOf  @alloc the returned groups
 * @returns {{ role, words, ids: string[] }[]}  words is the count and role, `2 orchestrators`
 */
export function rootsList(feed) {
  const { known, roots } = treeOf(feed);
  const byRole = new Map();
  for (const id of roots) {
    const role = known.get(id).role || OUTLINE_WORDS.session;
    if (!byRole.has(role)) byRole.set(role, []);
    byRole.get(role).push(id);
  }
  const rank = (role) => (ROOT_ROLE_ORDER.includes(role) ? ROOT_ROLE_ORDER.indexOf(role) : ROOT_ROLE_ORDER.length);
  return [...byRole.entries()]
    .sort(([p], [q]) => (rank(p) - rank(q)) || byName(p, q))
    .map(([role, ids]) => ({ role, words: counted(ids.length, role), ids }));
}

/** A message's age in words: `40 s ago`, `2 m ago`, `3 h ago`, `1 d ago`. @complexity O(1)  @alloc one string */
function agoWords(ageS) {
  if (ageS < S_PER_M) return `${Math.round(ageS)} s ${OUTLINE_WORDS.ago}`;
  if (ageS < S_PER_H) return `${Math.floor(ageS / S_PER_M)} m ${OUTLINE_WORDS.ago}`;
  if (ageS < S_PER_D) return `${Math.floor(ageS / S_PER_H)} h ${OUTLINE_WORDS.ago}`;
  return `${Math.floor(ageS / S_PER_D)} d ${OUTLINE_WORDS.ago}`;
}

/**
 * The outline view of a feed, for a phone (a2's direction): no wires.
 * One group per root, in name order, headed by headWords; in it one row
 * per session of that tree, parent before children, each `depth` levels
 * under its root, with its name, its role words, its state's glyph and
 * word, its unread count and its note (as boardView's). Then the recent
 * traffic: one line per pair, its newest message, `a → b · #18 · 2 m ago`,
 * newest first.
 * @interacts  none; pure
 * @complexity O(n log n + r log r) over n nodes and r recent wires  @alloc the returned model
 * @returns {{ groups: { root, heading, rows: { id, depth, role, state, glyph, word, unread, note }[] }[],
 *            traffic: { from, to, seq, text }[] }}
 */
export function outlineView(feed) {
  const { known, kids, roots } = treeOf(feed);
  const groups = roots.map((root) => {
    const rows = [];
    for (const stack = [[root, 0]]; stack.length;) {
      const [id, depth] = stack.pop();
      const n = known.get(id);
      const state = STATES[n.state] ? n.state : 'idle';
      rows.push({
        id, depth, role: roleTitle(n).slice(String(id).length), state, glyph: STATES[state].glyph, word: STATES[state].word,
        unread: n.unread > 0 ? `${n.unread} unread` : '', note: noteFor(n, known),
      });
      const children = kids.get(id) || [];
      for (let i = children.length - 1; i >= 0; i -= 1) stack.push([children[i], depth + 1]);
    }
    return { root, heading: headWords(roleTitle(known.get(root)), rows.length), rows };
  });
  const newest = new Map();
  for (const w of (feed && feed.wires) || []) {
    if (w.from === w.to) continue;
    const key = pairKey(w.from, w.to);
    if (!newest.has(key) || w.seq > newest.get(key).seq) newest.set(key, w);
  }
  const traffic = [...newest.values()].sort((p, q) => q.seq - p.seq).map((w) => ({
    from: w.from, to: w.to, seq: w.seq,
    text: `${w.from} → ${w.to} · #${w.seq}${w.age_s == null ? '' : ` · ${agoWords(w.age_s)}`}`,
  }));
  return { groups, traffic };
}

/**
 * What to draw for a C5 feed laid out inside `width` (see layoutLevels):
 * one view per node and per edge, keyed by id. Node: title (roleTitle), pos
 * (layoutLevels), state, detail (unread count), note (`reports to N · not
 * found`, else the status line, as `last status: ...` on a down node), and
 * `connector`: on a node with a parent in the layout, the hierarchy's own
 * thin line from the parent's out port to this node's in port (routeTree),
 * with its words for a title and no label on the board (round 2, a2's
 * direction; the legend says what the thin line is); null on a root. It
 * belongs to the child, so it comes and goes and moves with it. It replaces
 * the reports_to hint, so a feed's reports_to links draw nothing of their
 * own; one that names no node is still its node's note. A root's view has
 * `head`, the heading over its tree (layoutLevels' heads, with headWords'
 * text: round 2, item 5); any other node's is null. Wires and labels keep
 * off headings as they do off boxes.
 *
 * Edges, each a run of points (round 2, item 2; the rule is in the
 * routing section above), with `words` for its title, always:
 * - a mailbox link whose two ends are nodes: on a parent and child, the
 *   connector's own run, so their mail runs down along it; on any other
 *   pair, routeAround's run from the upper node to the lower, kept off the
 *   connectors where it can be. It flows,
 *   with dashes, an arrow at the reader and the label `from → to · #seq`,
 *   when its pair's newest wire is at most FLOW_AGE_S old; quiet, it is a
 *   thin line with no label (round 2, item 3). It is down when either end
 *   is down.
 * - a native link with no mailbox link on its pair: routeAround's run, long
 *   dashed, no label; its words, `native · not observed`, are in its title
 *   and the legend. On a pair with mail too, the words go in the mail
 *   wire's title and no second line is drawn.
 * A label sits where placeLabels puts it (`at`), clear of every node box
 * and every other label, or is dropped (`at` null) with its words kept in
 * the title.
 * @interacts  none; pure
 * @complexity O(n log n + l + r) for the layout and the edges over n
 *             nodes, l links and r wires, plus routeAround per routed pair
 *             and placeLabels for the labels
 * @alloc      the returned views, one box per node and the routing's
 *             working sets, freed on return
 * @returns {{ nodes: {id: view}, edges: {id: view}, extent: {w, h} }}
 */
export function boardView(feed, width) {
  const C = CONFIG;
  const lay = layoutLevels(feed, width);
  const known = new Map(((feed && feed.nodes) || []).map((n) => [n.id, n]));
  const nodes = nameMap();
  const boxOf = nameMap();
  for (const n of known.values()) {
    nodes[n.id] = {
      id: n.id, title: lay.titles[n.id], pos: lay.pos[n.id], state: STATES[n.state] ? n.state : 'idle',
      detail: n.unread > 0 ? `${n.unread} unread` : '', note: noteFor(n, known), connector: null, head: null,
    };
    boxOf[n.id] = { x: lay.pos[n.id].x, y: lay.pos[n.id].y, w: C.NODE_W, h: C.NODE_H };
  }
  for (const root of lay.roots) {
    nodes[root].head = { ...lay.heads[root], text: headWords(lay.titles[root], treeSize(lay.kids, root)) };
  }
  const headBoxes = lay.roots.map((root) => lay.heads[root]);
  // Wires keep clear of every box, every port's stub and every heading;
  // labels keep off every box, every port ring and every heading.
  const boxes = Object.values(boxOf);
  const ports = (size) => boxes.flatMap((b) => ['in', 'out'].map((side) => {
    const at = levelPort(b, side);
    return { x: at.x - C.PORT_SIZE / 2, y: side === 'in' ? at.y - size : at.y, w: C.PORT_SIZE, h: size };
  }));
  const obstacles = [...boxes, ...ports(C.ROUTE_CLEAR), ...headBoxes];
  const flowing = new Map();
  for (const w of (feed && feed.wires) || []) {
    if (w.age_s == null || w.age_s > C.FLOW_AGE_S || w.from === w.to) continue;
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
  const parentOf = nameMap();
  const connectors = [];
  for (const [parent, children] of lay.kids) {
    for (const child of children) {
      parentOf[child] = parent;
      nodes[child].connector = {
        points: routeTree(lay, parent, child),
        words: known.get(child).reports_to === parent ? `${child} reports to ${parent}` : `${child} under ${parent} · ${TREE_WORDS.inferred}`,
      };
      connectors.push(nodes[child].connector.points);
    }
  }
  for (const l of links) {
    const p = known.get(l.from);
    const q = known.get(l.to);
    if (!p || !q || p === q || (l.kind !== 'mailbox' && l.kind !== 'native')) continue;
    const pair = pairKey(l.from, l.to);
    // A native link whose pair also has mail rides in that wire's title.
    if (l.kind === 'native' && mailboxPairs.has(pair)) continue;
    const id = `${l.kind}:${l.from}>${l.to}`;
    let from;
    let to;
    let points;
    if (parentOf[q.id] === p.id || parentOf[p.id] === q.id) {
      [from, to] = parentOf[q.id] === p.id ? [p.id, q.id] : [q.id, p.id];
      points = routeTree(lay, from, to);
    } else {
      [from, to] = upperFirst(p, q, lay.pos).map((n) => n.id);
      points = routeAround(obstacles, boxOf[from], boxOf[to], lay.extent, connectors);
    }
    const w = l.kind === 'mailbox' ? flowing.get(pair) : undefined;
    const back = !!w && w.from !== from;
    const label = w ? `${w.from} → ${w.to} · #${w.seq}` : '';
    const native = l.kind === 'native' || nativePairs.has(pair);
    const said = l.kind === 'mailbox' ? (label || `${TREE_WORDS.mail} ${from} and ${to}`) : `${from} and ${to}`;
    edges[id] = {
      id, kind: l.kind, from, to, points, label, seq: w ? w.seq : null,
      words: native ? `${said} · ${LINK_WORDS.native}` : said,
      arrow: w ? (back ? 'start' : 'end') : null, flow: !!w, back,
      down: l.kind === 'mailbox' && (p.state === 'down' || q.state === 'down'),
    };
  }
  const spots = placeLabels(edges, [...boxes, ...ports(C.PORT_SIZE / 2), ...headBoxes], lay.extent);
  for (const e of Object.values(edges)) e.at = spots[e.id] || null;
  return { nodes, edges, extent: lay.extent };
}

const NODE_FIELDS = ['title', 'state', 'detail', 'note'];
const EDGE_FIELDS = ['kind', 'from', 'to', 'label', 'seq', 'words', 'arrow', 'flow', 'back', 'down'];

/** True when two points sit at the same place. @complexity O(1)  @alloc none */
function samePoint(p, q) {
  return p.x === q.x && p.y === q.y;
}

/** True when two runs of points are the same. @complexity O(p) over p points  @alloc none */
function samePoints(p, q) {
  return p.length === q.length && p.every((pt, i) => samePoint(pt, q[i]));
}

/** True when two node views would draw the same, connector and heading too. @complexity O(p) over p connector points  @alloc none */
function sameNode(p, q) {
  const sameConnector = p.connector === q.connector || (p.connector && q.connector
    && p.connector.words === q.connector.words && samePoints(p.connector.points, q.connector.points));
  const sameHead = p.head === q.head || (p.head && q.head && p.head.text === q.head.text
    && samePoint(p.head, q.head) && p.head.w === q.head.w);
  return NODE_FIELDS.every((f) => p[f] === q[f]) && samePoint(p.pos, q.pos) && !!sameConnector && !!sameHead;
}

/** True when two edge views would draw the same. @complexity O(p) over p points  @alloc none */
function sameEdge(p, q) {
  const sameAt = p.at === q.at || (p.at && q.at && samePoint(p.at, q.at) && p.at.w === q.at.w);
  return EDGE_FIELDS.every((f) => p[f] === q[f]) && !!sameAt && samePoints(p.points, q.points);
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
 * @complexity boardView's (routing and labels included), plus O(c) kit calls for c changes
 * @alloc      one full view per call (an object per node and edge, plus the
 *             layout's maps), kept as board.view until the next call; one
 *             handle per added node or edge; each removed one is dropped
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
 * One edge view as SVG: a path along its run with rounded bends
 * (roundedPath), its words in a title (shown on hover), and its label,
 * where placeLabels put one, centered in that box on an opaque backing of
 * the box's size, in canvas.labels, so it reads over any wire.
 * @interacts  puts the path before canvas.labels and the label and its
 *             backing in it; remove() takes all three out
 * @complexity O(p) per call over p points  @alloc one path with a title, one rect and one text element
 * @returns {{ path, label, back, update(view), remove() }}
 */
export function drawEdge(doc, canvas, view) {
  const path = svg(doc, 'path', { class: 'tc-wire' });
  const tip = svg(doc, 'title');
  path.append(tip);
  const back = svg(doc, 'rect', { class: 'tc-wire-label-back' });
  const label = svg(doc, 'text', { class: 'tc-wire-label', 'text-anchor': 'middle', 'dominant-baseline': 'central' });
  canvas.wires.insertBefore(path, canvas.labels);
  canvas.labels.append(back, label);
  const edge = {
    path, label,
    update(v) {
      path.setAttribute('d', roundedPath(v.points, CONFIG.ROUTE_CLEAR));
      path.setAttribute('class', ['tc-wire', `kind-${v.kind}`, v.flow && 'flow', v.back && 'back', v.down && 'down'].filter(Boolean).join(' '));
      path.setAttribute('data-edge', v.id);
      path.removeAttribute('marker-end');
      path.removeAttribute('marker-start');
      if (v.arrow) path.setAttribute(`marker-${v.arrow}`, 'url(#tc-arrow)');
      tip.textContent = v.words;
      const shown = v.label && v.at;
      label.setAttribute('x', String(shown ? v.at.x + v.at.w / 2 : 0));
      label.setAttribute('y', String(shown ? v.at.y + v.at.h / 2 : 0));
      label.textContent = shown ? v.label : '';
      for (const [name, value] of [['x', 'x'], ['y', 'y'], ['width', 'w'], ['height', 'h']]) {
        back.setAttribute(name, String(shown ? v.at[value] : 0));
      }
    },
    remove() {
      path.remove();
      back.remove();
      label.remove();
    },
  };
  edge.update(view);
  return edge;
}

/**
 * The DOM kit patchBoard draws through: nodes with createNode (ports on the
 * top and bottom edges), each with its connector from its parent as a thin
 * path under every wire (first in the layer, with its words as a title)
 * and, on a root, the heading over its tree (round 2, item 5); and edges
 * with drawEdge, all on `canvas`. A node's reveal() scrolls its heading (or
 * its box) to the top of the view. drawOutline(model) draws outlineView's
 * model into canvas.outline, replacing what was there, and
 * revealOutline(id) scrolls root id's group heading to the top.
 * @interacts  see createNode and drawEdge; a node's remove() takes its
 *             connector and heading out too; drawOutline replaces
 *             canvas.outline's children; the reveals scroll the page
 * @complexity O(1) per node call plus O(p) over p connector points; edges
 *             as drawEdge; drawOutline O(n + t) over n rows and t traffic lines
 * @alloc      one node subtree, one connector path and one heading per
 *             node, or one edge's elements per create; drawOutline one
 *             element tree for the outline, dropping the last, and a map of
 *             its group headings
 */
export function createKit(doc, canvas) {
  let outlineHeads = new Map();
  return {
    createNode(v) {
      const node = createNode(doc, canvas, { ...v, hue: HUES[hueFor(v.id)], levels: true });
      const stem = svg(doc, 'path', { class: 'tc-wire kind-tree' });
      const tip = svg(doc, 'title');
      stem.append(tip);
      canvas.wires.insertBefore(stem, canvas.wires.firstChild ? canvas.wires.firstChild.nextSibling : null);
      const head = el(doc, 'div', 'tc-head');
      head.style.height = `${CONFIG.HEAD_H}px`;
      canvas.view.append(head);
      const handle = {
        node,
        update(n) {
          node.moveTo(n.pos);
          node.setTitle(n.title);
          node.setNote(n.note);
          node.setState(n.state, n.detail);
          stem.setAttribute('d', n.connector ? roundedPath(n.connector.points, CONFIG.ROUTE_CLEAR) : '');
          stem.setAttribute('data-edge', `tree:${n.id}`);
          tip.textContent = n.connector ? n.connector.words : '';
          head.hidden = !n.head;
          head.textContent = n.head ? n.head.text : '';
          head.title = head.textContent;
          if (n.head) {
            head.style.left = `${n.head.x}px`;
            head.style.top = `${n.head.y}px`;
            head.style.width = `${n.head.w}px`;
          }
        },
        reveal() { (head.hidden ? node.root : head).scrollIntoView({ block: 'start' }); },
        remove() {
          node.remove();
          stem.remove();
          head.remove();
        },
      };
      handle.update(v);
      return handle;
    },
    createEdge(v) { return drawEdge(doc, canvas, v); },
    drawOutline(model) {
      outlineHeads = new Map();
      const parts = model.groups.map((g) => {
        const group = el(doc, 'section', 'tc-group');
        const head = el(doc, 'div', 'tc-group-head', g.heading);
        outlineHeads.set(g.root, head);
        group.append(head);
        for (const r of g.rows) {
          const row = el(doc, 'div', r.depth ? 'tc-row nested' : 'tc-row');
          row.dataset.state = r.state;
          row.style.marginLeft = `${r.depth * CONFIG.OUTLINE_INDENT}px`;
          const title = el(doc, 'span', 'tc-row-title');
          title.append(el(doc, 'span', 'tc-row-name', r.id), el(doc, 'span', 'tc-row-role', r.role));
          row.append(title, el(doc, 'span', 'tc-row-state', `${r.glyph} ${r.word}${r.unread ? ` · ${r.unread}` : ''}`));
          if (r.note) row.append(el(doc, 'span', 'tc-row-note', r.note));
          group.append(row);
        }
        return group;
      });
      const traffic = el(doc, 'section', 'tc-traffic');
      traffic.append(el(doc, 'div', 'tc-group-head', OUTLINE_WORDS.traffic));
      const lines = model.traffic.length ? model.traffic.map((t) => t.text) : [OUTLINE_WORDS.noTraffic];
      for (const text of lines) traffic.append(el(doc, 'div', 'tc-traffic-line', text));
      canvas.outline.replaceChildren(...parts, traffic);
    },
    revealOutline(id) {
      const head = outlineHeads.get(id);
      if (head) head.scrollIntoView({ block: 'start' });
    },
  };
}

/**
 * Scale and offset that fit a board of `extent` inside width x height with
 * `padding` to spare, centered, never enlarged and never under MIN_FIT_SCALE
 * (so no text drops under MIN_TEXT_PX). createFit passes the board's own
 * height plus `padding` as the height, since the frame grows to the board
 * (round 2), so only the width can call for a smaller scale; a board laid
 * out at layoutWidth(width) never runs past the width.
 * @complexity O(1)  @alloc one object
 * @returns {{ x, y, k }}
 */
export function fitTransform(width, height, extent, padding) {
  if (!extent.w || !extent.h) return { x: 0, y: 0, k: 1 };
  const k = Math.max(CONFIG.MIN_FIT_SCALE, Math.min(1, (width - padding) / extent.w, (height - padding) / extent.h));
  return { x: Math.max(0, (width - extent.w * k) / 2), y: Math.max(0, (height - extent.h * k) / 2), k };
}

/**
 * Keep a board laid out to its canvas. The stage's width comes from the
 * ResizeObserver's own entry, never from a layout read after a patch, so a
 * poll that changes the board forces no layout (round 1, LOW-4). The width
 * picks the view (a2's direction): under OUTLINE_BELOW_PX the outline
 * (outlineView, drawn by board.kit.drawOutline, only when it changed),
 * else the graph. `mark`'s data-view names the view drawn, so theme.css
 * shows that one and its legend. In the graph, draw(feed) lays the feed out
 * at that width (layoutLevels wraps it) and patches the board; a resize
 * that changes the width draws the last feed again, and one that changes
 * only the height (the frame growing) draws nothing. The frame takes the
 * board's height plus `padding` (round 2, item 1), so the page scrolls down
 * as far as the board goes, never sideways, and the fit never shrinks the
 * board to the frame's height; the view and its wire layer take the
 * board's extent. jump(id) brings root id's tree into view (item 5).
 * `Observer` is ResizeObserver on a page; a test passes a fake.
 * Model: Claude Opus 5.5 (the BOARD fixer, rounds 1 and 2), 2026-10-14. Status: unreviewed.
 * @interacts  observes canvas.root (the stage) from start() until stop()
 *             (the page calls them on load and pageshow, and on pagehide);
 *             writes mark's data-view, canvas.frame's height, canvas.view's
 *             transform, width and height and canvas.wires' width and
 *             height; calls patchBoard, and through it board.kit, or
 *             board.kit.drawOutline; jump calls a node handle's reveal or
 *             board.kit.revealOutline
 * @complexity one draw or width change: patchBoard's (boardView's routing
 *             included), or outlineView's O(n log n + r log r)
 * @alloc      one observer for the fit's life; holds the last feed, the
 *             last width and the last outline drawn (as a string), each
 *             replaced by the next
 * @returns {{ draw(feed), start(), stop(), jump(id), view }}  view: 'graph' | 'outline' | null
 */
export function createFit(canvas, board, { padding, Observer, mark }) {
  let width = null;
  let feed = null;
  let view = null;
  let drawnOutline = null;
  const apply = () => {
    if (width === null) return;
    view = width < CONFIG.OUTLINE_BELOW_PX ? 'outline' : 'graph';
    if (mark) mark.dataset.view = view;
    if (view === 'outline') {
      if (!feed) return;
      const model = outlineView(feed);
      const key = JSON.stringify(model);
      if (key !== drawnOutline) {
        drawnOutline = key;
        board.kit.drawOutline(model);
      }
      return;
    }
    if (feed) patchBoard(board, feed, layoutWidth(width));
    const { extent } = board.view;
    const height = extent.h + padding;
    const t = fitTransform(width, height, extent, padding);
    canvas.frame.style.height = `${height}px`;
    canvas.view.style.width = `${extent.w}px`;
    canvas.view.style.height = `${extent.h}px`;
    canvas.view.style.transform = `translate(${t.x}px, ${t.y}px) scale(${t.k})`;
    canvas.wires.setAttribute('width', String(Math.max(CONFIG.MIN_LAYER_PX, extent.w)));
    canvas.wires.setAttribute('height', String(Math.max(CONFIG.MIN_LAYER_PX, extent.h)));
  };
  const observer = new Observer((entries) => {
    const next = entries[entries.length - 1].contentRect.width;
    if (next === width) return;
    width = next;
    apply();
  });
  return {
    draw(next) {
      feed = next;
      apply();
    },
    start() { observer.observe(canvas.root); },
    stop() { observer.disconnect(); },
    jump(id) {
      if (view === 'outline') board.kit.revealOutline(id);
      else if (board.nodes.has(id)) board.nodes.get(id).reveal();
    },
    get view() { return view; },
  };
}

/**
 * The pill's words when the feed is not answering, each a plain statement;
 * none of them says live. Model: Claude Opus 5.5 (the BOARD fixer, round 1),
 * 2026-10-14. Status: unreviewed.
 */
export const CONN_WORDS = Object.freeze({
  asking: 'asking the server',
  noToken: 'no token · open the URL serve.py printed',
  tokenRefused: 'token refused · open the URL serve.py printed',
  noAnswer: 'no answer',
  stale: 'stale',
  timedOut: 'timed out',
  badAnswer: 'bad answer',
  noServer: 'is serve.py running?',
});
// The status serve.py gives /feed without the right token (C6).
const HTTP_UNAUTHORIZED = 401;
// The pill counts the age of the last answer in whole seconds.
const MS_PER_S = 1000;

/**
 * Ask for the feed one request at a time: the next poll starts `pollMs`
 * after the last one settles, so requests never pile up behind a slow or
 * stopped server, and an older answer can never land after a newer one
 * (C6's newest answer wins, by construction). A request still out after
 * `timeoutMs` is aborted. When an answer fails or is late the pill says so
 * in words: `no answer · <why>` before any answer, else `stale · last
 * answer N s ago · <why>`; a 401 says the token was refused. A good answer
 * goes to onFeed, which writes the pill itself. fetchFeed(signal) returns a
 * fetch Response; timers is { setTimeout, clearTimeout }; now() is a
 * monotonic clock in ms (performance.now on a page, a fake in a test).
 * Model: Claude Opus 5.5 (the BOARD fixer, round 1), 2026-10-14. Status: unreviewed.
 * @interacts  calls fetchFeed, timers, now, onFeed and onConn, nothing
 *             else. start() polls; stop() clears both timers and aborts the
 *             request in flight (the page calls them on load and pageshow,
 *             and on pagehide)
 * @complexity O(1) per poll, plus the caller's onFeed
 * @alloc      one AbortController and two timers while a request is out,
 *             one timer between polls; none after stop()
 * @returns {{ start(), stop() }}
 */
export function createPoller({ fetchFeed, pollMs, timeoutMs, timers, now, onFeed, onConn }) {
  let running = false;
  let next = null;
  let deadline = null;
  let inFlight = null;
  let answeredAt = null;
  const failed = (why) => {
    if (answeredAt === null) {
      onConn(`${CONN_WORDS.noAnswer} · ${why}`, 'down');
      return;
    }
    const ago = Math.round((now() - answeredAt) / MS_PER_S);
    onConn(`${CONN_WORDS.stale} · last answer ${ago} s ago · ${why}`, 'down');
  };
  const poll = async () => {
    next = null;
    const ctl = new AbortController();
    let late = false;
    let reached = false;
    inFlight = ctl;
    deadline = timers.setTimeout(() => {
      late = true;
      ctl.abort();
    }, timeoutMs);
    try {
      const answer = await fetchFeed(ctl.signal);
      reached = true;
      if (inFlight !== ctl) return;
      if (answer.status === HTTP_UNAUTHORIZED) {
        onConn(CONN_WORDS.tokenRefused, 'down');
      } else if (!answer.ok) {
        failed(`HTTP ${answer.status}`);
      } else {
        const feed = await answer.json();
        if (inFlight !== ctl) return;
        answeredAt = now();
        onFeed(feed);
      }
    } catch {
      if (inFlight === ctl) failed(late ? CONN_WORDS.timedOut : (reached ? CONN_WORDS.badAnswer : CONN_WORDS.noServer));
    } finally {
      if (inFlight === ctl) {
        timers.clearTimeout(deadline);
        deadline = null;
        inFlight = null;
        if (running) next = timers.setTimeout(poll, pollMs);
      }
    }
  };
  return {
    start() {
      if (running) return;
      running = true;
      poll();
    },
    stop() {
      running = false;
      timers.clearTimeout(next);
      timers.clearTimeout(deadline);
      next = null;
      deadline = null;
      const ctl = inFlight;
      inFlight = null;
      if (ctl) ctl.abort();
    },
  };
}
