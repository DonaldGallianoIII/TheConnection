/**
 * look.js: drawing tools for the board look. Builds the window frame, the
 * canvas, session nodes, ports and wires as DOM and SVG elements. The live
 * board's layer is pure: layoutLevels places a C5 feed's nodes in levels,
 * wrapped to a width, boardView turns a feed into what to draw, and
 * diffBoard says what changed between two views. patchBoard applies a diff
 * through a drawing kit (createKit for the DOM, or a test's fake), so the
 * board is never rebuilt. createFit keeps a board laid out to its canvas.
 * Every wire and connector is routed round the boxes (routeTree,
 * routeTreeWire, routeAround), a parent and child's wire beside their
 * connector, never on it, and every label is placed clear of boxes and
 * other labels (placeLabels); the routing section states the one rule. A
 * dotted or dashed wire is drawn over every solid one, on a knockout in the
 * canvas's color, so no other stroke shows in its gaps (drawEdge). A
 * native pair's boxes, a reports_to cycle's root and a down node whose
 * inbox the board could not list carry badge lines in words (badgesOf).
 * Each root's tree starts with a heading, rootsList and
 * createRoots make the list of roots at the top of the page, and on a
 * phone createFit draws outlineView's outline instead of the graph.
 *
 * @interacts  creates elements under the container the caller passes in; uses
 *             theme.css class names; applyLook writes data-theme on <html>;
 *             never touches innerHTML, storage or globals. layoutLevels,
 *             boardView, diffBoard, roleTitle, hueFor, pillText,
 *             layoutWidth, levelPort, routeTree, routeAround, roundedPath,
 *             placeLabels, rootsList, outlineView, fitTransform and
 *             tokenProblem read only their arguments (boardView writes the
 *             route cache it is given, if any); patchBoard writes only the
 *             board object it is given and calls only its kit; createRoots calls back on
 *             a click; createFit observes the canvas's stage through the
 *             observer it is given and writes the window's data-view, the
 *             frame's height and the view's size and transform, and its
 *             jump and the kit's reveals scroll the page; createPoller asks
 *             for the feed through the fetch and timers it is given and
 *             reports through its three callbacks (onFeed, onConn and
 *             onStale)
 * @deps       browser DOM and SVG for the drawing functions; the pure layer
 *             needs neither (node --test runs it with no DOM library)
 * @complexity every drawing function is O(1) per call, or O(p) over a run's
 *             p points; a board with n nodes and w wires costs O(n + w) to
 *             build. layoutLevels is O(n log n + l + r) over n feed nodes, l
 *             links and r recent wires (C5: n tens; l the mail pairs plus
 *             c(c-1)/2 native lines per account shared by c Claude cards,
 *             190 for 20 on one; r <= 50), the log from the sort by name.
 *             patchBoard lays nothing out when only ages moved (drawnKey);
 *             else boardView adds placeLabels and routeAround's search,
 *             O(g log g) over its g = 4XY states, per routed pair when
 *             the boxes, headings, extent or tree runs changed
 *             (createRouteCache's key), else only per routed pair new to
 *             the cache:
 *             up to 31,916 on the 14-name test feed at 1152 px (X 79 and Y
 *             101 lines), and 190 searches of up to 12,180 for 20 peers on
 *             one account, which drew in about 150 ms on the owner's machine
 *             (measured 2026-10-15). diffBoard
 *             is O(n + e) over two views' nodes and e edges, times their
 *             points; outlineView is O(n log n + l + r log r); rootsList and
 *             pillText are O(n) after the sort; createPoller is O(1) per poll
 * @alloc      one element tree (with one line per badge), one connector
 *             path and one heading per node, one path with its title, one
 *             knockout path and one label with its backing per wire, each
 *             released by its own remove(); one group per wire layer in
 *             the canvas; the outline's elements, one per group, row,
 *             badge line and traffic line, each kept from one draw to the
 *             next and removed when it leaves the outline (createKit's
 *             drawOutline patches it in place); one button
 *             per root in the roots list, replaced when the roots change.
 *             removeBoard clears the DOM
 *             under a parent and nothing else: a board object from
 *             createBoard goes with it, since nothing else holds its
 *             handles. That board holds one handle per drawn node and edge,
 *             dropped when patchBoard removes it, the last full view
 *             (board.view), replaced on every patch that lays out, the
 *             last feed's key (board.drawn), and its route cache
 *             (board.routes): one routed run per routed pair drawn now,
 *             by its ends, and their key, replaced on each layout, and
 *             two counts
 */

const SVG_NS = 'http://www.w3.org/2000/svg';

// Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
// No text on the board is drawn under this many CSS px at the scale it is
// shown, on a desktop or a phone, so every word reads without zooming.
const MIN_TEXT_PX = 11;
// The smallest font-size theme.css gives text inside the board (the state
// line, the note and the wire labels). tests/board-layout.test.mjs reads
// theme.css and fails if the two drift apart.
const BOARD_TEXT_MIN_PX = 11;
// Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
// A tree connector to a wrapped row runs down a lane of its own parent's
// block, this far from the block's edge and from the children beside it.
const ROUTE_GUTTER_PX = 12;
// The stage width under which the board draws the outline (CONFIG says
// why), and how much wider the stage must grow before it draws the graph
// again.
const OUTLINE_BELOW_PX = 560;
const VIEW_HYSTERESIS_PX = 24;

export const CONFIG = Object.freeze({
  // Model: Claude Opus 5.5 (the BOARD lane agent), 2026-10-14. Status:
  // unreviewed. Wider and taller than the look kit's 132 x 48, so a title
  // holds "name · orchestrator · inferred" and a third line holds the status.
  // 64 tall: three lines of 11 px or more inside a 4 px double border.
  NODE_W: 208,
  NODE_H: 64,
  // Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
  // A box carrying badge lines (a native pair, a cycle's root: words, never
  // color alone) is BADGE_H taller per line: one 11 px line in its dashed rule.
  BADGE_H: 16,
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
  // Root trees one under another are LAYOUT_ROW_GAP apart. Where a row
  // holds one box (a phone), children sit LAYOUT_INDENT right of their
  // parent so the levels still read.
  LAYOUT_COL_GAP: 28,
  LAYOUT_ROW_GAP: 56,
  LAYOUT_WRAP_GAP: 40,
  LAYOUT_ROOT_GAP: 72,
  LAYOUT_INDENT: 32,
  LAYOUT_MARGIN: 24,
  // Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
  // Each root's tree starts with a heading naming its root, as wide
  // as the tree: HEAD_H tall (an 11 px line and its rule), then HEAD_GAP
  // before the root's box (room for the root's in port ring, which stands
  // PORT_SIZE / 2 over the box).
  HEAD_H: 20,
  HEAD_GAP: 8,
  // Under OUTLINE_BELOW_PX of stage width (about a 600 px phone, less the
  // page's two 16 px margins, the window's borders and the body's 8 px
  // padding) the board draws the outline view instead of the graph. Back
  // to the graph only from GRAPH_FROM_PX: the gap is wider than a classic
  // scrollbar (about 15 to 17 px), so a scrollbar that comes or goes with
  // the view cannot flip it back every frame. Each outline row is indented
  // OUTLINE_INDENT px per level under its parent.
  OUTLINE_BELOW_PX,
  GRAPH_FROM_PX: OUTLINE_BELOW_PX + VIEW_HYSTERESIS_PX,
  OUTLINE_INDENT: 16,
  // A message at most this many seconds old flows on its wire. The feed's
  // WRITING_WINDOW_S, so the wire moves while its sender reads as writing.
  FLOW_AGE_S: 10,
  // Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
  // Routing. A routed wire keeps ROUTE_CLEAR px from every box; a bend
  // costs as much as ROUTE_TURN_COST px of length, so a route takes few
  // bends. A block whose children wrap into more than one row starts them
  // LAYOUT_LANE in, and its connectors to the wrapped rows run down the
  // middle of that lane, ROUTE_GUTTER from the block's edge and from the
  // children, so two parents never share one gutter. A bend is drawn
  // rounded, with a radius of at most ROUTE_CLEAR, so the curve stays as
  // clear as the corner.
  ROUTE_CLEAR: 10,
  ROUTE_TURN_COST: 40,
  ROUTE_GUTTER: ROUTE_GUTTER_PX,
  LAYOUT_LANE: 2 * ROUTE_GUTTER_PX,
  // A parent and child's mail wire, or their native line, runs this far
  // beside their connector, never on it, so the connector never fills the
  // gaps of its dots or dashes. It clears both port rings: a ring is placed
  // from the box's padding edge, so its center sits one node border right
  // of and below its port, and the wire must pass half a ring (PORT_SIZE /
  // 2, 6 px), half a wire (1.25 px) and the widest border (4 px, a
  // doorbell's; theme.css .tc-node). 6 + 1.25 + 4 is 11.25, so 12 leaves
  // 0.75 px at a doorbell and 3.25 px at the usual 1.5 px border.
  TREE_WIRE_OFFSET: 12,
  // A routed piece that runs alongside a tree connector, within ROUTE_CLEAR
  // of it, costs this many times its length, so a wire between trees takes
  // the gaps between them and crosses a connector rather than shadowing it.
  ROUTE_ALONG_COST: 4,
  // Labels. A label's box is LABEL_CHAR_W px per
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
  // Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
  // fitTransform never shrinks a board below this: the scale at which the
  // board's smallest text is MIN_TEXT_PX. With both at 11 it is 1, so the
  // board never shrinks; layoutLevels wraps it to the width instead, its
  // frame grows to its height and the page scrolls down.
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
  // Model: Claude Opus 5.5 (the P4 phase fixer), 2026-10-15. Status: unreviewed.
  // D24: a listener that mail woke, since tc wait exits on mail. working:
  // it shows life after the wake, or the wake is under two minutes old;
  // calm. woken: no sign of life past that; a warning, never down.
  woken: { glyph: '△', word: 'woken · not read' },
  working: { glyph: '◔', word: 'working' },
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
 * top-down levels: side 'in' is the middle of the top edge, 'out' the
 * middle of the bottom edge, so a parent's connector and its mail to a
 * child run down. `h` is the box's height: NODE_H, plus BADGE_H per badge
 * line the box carries.
 * Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
 * @complexity O(1)  @alloc one object
 */
export function levelPort(pos, side, h = CONFIG.NODE_H) {
  return { x: pos.x + CONFIG.NODE_W / 2, y: pos.y + (side === 'in' ? 0 : h) };
}

/**
 * Window frame: title bar with traffic dots, a status pill, a body and a
 * footer. The body starts with a line, hidden until setStale(text) gives
 * it words: while the feed is stale it reads, over the board, `stale ·
 * last answer N s ago`, and the window's data-conn turns `stale`, which
 * stops every flowing wire's dashes (theme.css), so nothing on the board
 * looks live that is not. setStale(null) hides it again.
 * @interacts  appends to parent
 * @complexity O(1)  @alloc one window subtree
 * @returns {{ root, title, body, foot, setConn(text, state), setStale(text) }}  state: 'up' | 'warn' | 'down'
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
  // Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
  const stale = el(doc, 'div', 'tc-stale');
  stale.hidden = true;
  body.append(stale);
  const foot = el(doc, 'div', 'tc-foot');
  root.append(title, body, foot);
  parent.append(root);
  return {
    root, title, body, foot,
    setConn(text, state) { ctext.textContent = text; conn.dataset.state = state; },
    setStale(text) {
      stale.textContent = text || '';
      stale.hidden = !text;
      root.dataset.conn = text ? 'stale' : 'live';
    },
  };
}

/**
 * Footer cells. Each item is { text }, { spacer: true }, or { legend, text }:
 * a legend is a row of its own, the first line of the footer, never over
 * the board. Replaces what was there. Cells wrap to a new line on a
 * narrow screen instead of cutting words off.
 * Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
 * @complexity O(k) for k items  @alloc k spans
 */
export function setFooter(doc, foot, items) {
  foot.replaceChildren(...items.map((it) => {
    if (it.spacer) return el(doc, 'span', 'tc-sp');
    if (it.legend) return el(doc, 'span', `tc-legend tc-legend-${it.legend}`, it.text);
    return el(doc, 'span', 'tc-cell', it.text);
  }));
}

// Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
// The wire layer's groups, in the order they are painted, bottom to top:
// solid lines (a quiet mail wire), then dashed ones (a flowing wire, a
// native line), then dotted ones (a wire to a session with no listener).
// See wireLayer.
const WIRE_LAYERS = Object.freeze(['plain', 'dashed', 'down']);

/**
 * Canvas: a stage holding the frame the board draws in, which holds the
 * view (a wire layer in SVG and a node layer), and the outline a phone
 * draws instead (theme.css shows one of the two by the
 * window's data-view). The frame grows to the
 * board's laid out height and the page scrolls, never sideways; nothing
 * sits over it (the legend is in the footer).
 * createFit watches the stage, which keeps the width the board may use.
 * The wire layer holds, after its defs, one group per WIRE_LAYERS entry
 * (`layers`, painted in that order, so a dotted wire is over every dashed
 * one and both are over every solid one), then a group for the wires'
 * labels, so every label is drawn over every wire.
 * @interacts  appends to parent
 * @complexity O(1)  @alloc one canvas subtree with an arrow marker def and
 *             one group per wire layer
 * @returns {{ root, frame, view, wires, layers: { plain, dashed, down }, labels, outline }}
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
  const layers = {};
  for (const name of WIRE_LAYERS) layers[name] = svg(doc, 'g', { class: `tc-layer-${name}` });
  const labels = svg(doc, 'g', { class: 'tc-labels' });
  wires.append(defs, ...WIRE_LAYERS.map((name) => layers[name]), labels);
  view.append(wires);
  frame.append(view);
  const outline = el(doc, 'div', 'tc-outline');
  root.append(frame, outline);
  parent.append(root);
  return { root, frame, view, wires, layers, labels, outline };
}

/**
 * The list of roots at the top of the page:
 * `2 orchestrators: a, z · 2 peers: p1, p2`, each name a button that calls
 * onJump(name), which brings that tree into view. set(groups) takes
 * rootsList's groups and rebuilds the list only when they change; with no
 * roots it is hidden.
 * Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
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
 * the role words after it never do. The second line holds the state's
 * glyph and word alone, so a long one (`woken · not read`) is never cut.
 * A third line holds `detail` (the unread words: `2 unread`, `unread
 * unknown`) in full, then `note` (a status line, or a reports_to that
 * names nobody), which may shorten; with neither, it is hidden. Under it,
 * one badge line per item of `badges` ({ lead, names, tail, text }: a
 * native pair, a cycle's root or an inbox the board could not list, in
 * words), each in a dashed rule; only
 * the names may shorten, and the whole text is the badge's title. `h` is
 * the box's height (NODE_H, plus BADGE_H per badge line). `problem`, tc's
 * reason for an unread count it could not take, goes on a second line of
 * the box's hover title, `unread unknown: <reason>`, as text, never as
 * markup: a group member chooses the file names in it.
 * @interacts  appends to canvas.view; remove() takes the node out again
 * @complexity O(1), plus O(b) over b badges  @alloc one node subtree
 * @returns {{ root, pos, setState(state, detail), setTitle(text), setNote(text), setProblem(text), setBadges(list),
 *            setHeight(h), moveTo(pos), remove() }}
 */
export function createNode(doc, canvas, { title, hue, pos, state, detail, note, problem, levels, h, badges }) {
  const root = el(doc, 'div', 'tc-node');
  root.style.width = `${CONFIG.NODE_W}px`;
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
  // Model: Claude Opus 5.5 (the P4 phase fixer, round 2), 2026-10-15. Status:
  // unreviewed. The third line: the unread words, never cut, then the note.
  const line = el(doc, 'span', 'tc-node-line');
  const unreadPart = el(doc, 'span', 'tc-node-unread');
  const noteLine = el(doc, 'span', 'tc-node-note');
  line.append(unreadPart, noteLine);
  const badgeBox = el(doc, 'span', 'tc-node-badges');
  body.append(t, sub, line, badgeBox);
  let detailText = '';
  let noteText = '';
  let titleText = '';
  let problemText = '';
  // The hover title: the box's title, and tc's reason on a line under it.
  const setHover = () => {
    root.title = problemText ? `${titleText}\n${UNREAD_WORDS.unknown}: ${problemText}` : titleText;
  };
  // The unread words lead the line, with a ` · ` before the note when
  // both are there; the line hides when it has neither.
  const fillLine = () => {
    unreadPart.textContent = detailText && noteText ? `${detailText} · ` : detailText;
    unreadPart.hidden = !detailText;
    noteLine.textContent = noteText;
    noteLine.hidden = !noteText;
    line.hidden = !detailText && !noteText;
  };
  const half = CONFIG.PORT_SIZE / 2;
  const at = levels ? levelPort : portPoint;
  const origin = { x: 0, y: 0 };
  const pin = el(doc, 'span', 'tc-port in');
  pin.title = 'in';
  pin.style.left = `${at(origin, 'in').x - half}px`;
  pin.style.top = `${at(origin, 'in').y - half}px`;
  const pout = el(doc, 'span', 'tc-port out');
  pout.title = 'out';
  root.append(bar, body, pin, pout);
  canvas.view.append(root);
  let shownBadges = null;
  const node = {
    root, pos,
    setHeight(height) {
      const tall = height || CONFIG.NODE_H;
      root.style.height = `${tall}px`;
      pout.style.left = `${at(origin, 'out', tall).x - half}px`;
      pout.style.top = `${at(origin, 'out', tall).y - half}px`;
    },
    setBadges(list) {
      const items = list || [];
      const key = items.map((b) => b.text).join('\n');
      if (key === shownBadges) return;
      shownBadges = key;
      badgeBox.replaceChildren(...items.map((b) => {
        const line = el(doc, 'span', 'tc-node-badge');
        line.title = b.text;
        line.append(el(doc, 'span', 'tc-node-badge-lead', b.lead), el(doc, 'span', 'tc-node-badge-names', b.names),
          el(doc, 'span', 'tc-node-badge-tail', b.tail));
        return line;
      }));
      badgeBox.hidden = !items.length;
    },
    setState(s, d) {
      const st = STATES[s] || STATES.idle;
      root.dataset.state = s;
      glyph.textContent = st.glyph;
      word.textContent = st.word;
      detailText = d || '';
      fillLine();
    },
    setTitle(title) {
      const text = String(title ?? '');
      const cut = text.indexOf(' · ');
      tName.textContent = cut < 0 ? text : text.slice(0, cut);
      tRole.textContent = cut < 0 ? '' : text.slice(cut);
      titleText = text;
      setHover();
    },
    setNote(text) {
      noteText = text || '';
      fillLine();
    },
    setProblem(text) {
      problemText = text ? String(text) : '';
      setHover();
    },
    moveTo(p) {
      node.pos = p;
      root.style.left = `${p.x}px`;
      root.style.top = `${p.y}px`;
    },
    remove() { root.remove(); },
  };
  node.moveTo(pos);
  node.setHeight(h);
  node.setTitle(title);
  node.setNote(note);
  node.setProblem(problem);
  node.setBadges(badges);
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

/**
 * Words on the board's hint lines and badges. Each hint is a line plus
 * words, never color alone. A native pair's two boxes each carry the badge
 * `native with <the other> · not observed`, and a reports_to cycle's root
 * carries `reports to <name> · cycle` (C5 asks for the native words).
 */
export const LINK_WORDS = Object.freeze({
  reports_to: 'reports to',
  native: 'native · not observed',
  nativeWith: 'native with',
  notObserved: 'not observed',
  notFound: 'not found',
  cycle: 'cycle',
});
// Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
// C1's word for an account nobody named. serve.py makes no native link on
// it (D15), and the page draws no native badge on it either: two such
// cards share no account that anyone knows.
const ACCOUNT_UNKNOWN = 'unknown';

/** True when two feed nodes may share a native badge and line: neither is on account `unknown`. @complexity O(1)  @alloc none */
function nativeAllowed(p, q) {
  return p.account !== ACCOUNT_UNKNOWN && q.account !== ACCOUNT_UNKNOWN;
}

/**
 * The legend: what each kind of line on the board means, in words, the
 * quiet mail wire too, and the thin line's parent whether a card declared
 * it or the feed inferred it from mail. It is a row of the footer, never
 * over the board; `empty` stands in for it while the feed holds no
 * sessions.
 * Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
 */
// Model: Claude Opus 5.5 (the P4 phase fixer, round 2), 2026-10-15. Status:
// unreviewed. The feed's DOWN_WINDOW_S (600) in minutes: a session that
// crashed after reading its mail reads working this long after it was last
// seen listening.
const DOWN_WINDOW_MIN = 10;
// Model: Claude Opus 5.5 (the P4 phase fixer), 2026-10-15; the two cases by
// the P4 phase fixer, round 2. Status: unreviewed.
// D24's two states in words, on both legends, with the two cases they
// cannot see (C5, D28).
const WAKE_WORDS = `${STATES.working.glyph} ${STATES.working.word}: mail woke it and it is on its turn · `
  + `${STATES.woken.glyph} ${STATES.woken.word}: mail woke it and nothing has read it · `
  + `the board cannot see a crash after reading (it looks ${STATES.working.word} for up to ${DOWN_WINDOW_MIN} min) `
  + 'or, with no board page open, when a listener went (mail that came meanwhile counts as a wake)';
export const LEGEND_WORDS = Object.freeze({
  outline: 'outline: each session under the one it reports to, or that mail shows it works for · '
    + `traffic: newest first, arrow toward the reader · ${WAKE_WORDS}`,
  graph: 'thin line: reports to, or inferred from mail · '
    + `thick line: mail, none in the last ${CONFIG.FLOW_AGE_S} s · `
    + 'dashes, arrow and words: mail now, arrow at the reader · dash-dot: native, not observed · dotted: no listener · '
    + WAKE_WORDS,
  empty: 'no sessions yet · send a message or start a listener',
});

/**
 * Words in an edge's title: a connector whose parent the feed
 * inferred from mail says so, and a quiet mail wire names its pair.
 * Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
 */
export const TREE_WORDS = Object.freeze({
  inferred: 'inferred from mail',
  mail: 'mail between',
});

/**
 * Words on a node's third line. A down or woken node's status was written
 * before it stopped listening, so it reads as the last thing it said,
 * never as its state now.
 * Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
 */
export const NOTE_WORDS = Object.freeze({
  lastStatus: 'last status:',
});

/**
 * Words for a node's unread mail. The feed's unread is null when tc could
 * not count an inbox (C5, with its reason in unread_problem): that reads
 * `unread unknown`, never a blank, which would read as no mail.
 * Model: Claude Opus 5.5 (the P4 phase fixer), 2026-10-15. Status: unreviewed.
 */
export const UNREAD_WORDS = Object.freeze({
  unread: 'unread',
  unknown: 'unread unknown',
});

/**
 * Words for an inbox the board could not list (the feed's
 * inbox_unreadable): beside `down`, the board cannot tell whether mail woke
 * the session, so it says so (C5, D28).
 * Model: Claude Opus 5.5 (the P4 phase fixer, round 2), 2026-10-15. Status: unreviewed.
 */
export const INBOX_WORDS = Object.freeze({
  unreadable: 'inbox unreadable',
});

/**
 * A node's unread words: `N unread`, `unread unknown` when the feed could
 * not count them (null), else '' (none, or a hand-made feed with no count).
 * Model: Claude Opus 5.5 (the P4 phase fixer), 2026-10-15. Status: unreviewed.
 * @complexity O(1)  @alloc one short string
 */
function unreadWords(n) {
  if (n.unread === null) return UNREAD_WORDS.unknown;
  return n.unread > 0 ? `${n.unread} ${UNREAD_WORDS.unread}` : '';
}

/**
 * tc's reason a node's unread count is unknown (the feed's unread_problem,
 * beside a null unread), or ''. Drawn only as text (createNode's hover
 * title, the outline row): a group member chooses the file names in it.
 * Model: Claude Opus 5.5 (the P4 phase fixer, round 2), 2026-10-15. Status: unreviewed.
 * @complexity O(1)  @alloc one short string
 */
function problemOf(n) {
  return n.unread === null && n.unread_problem ? String(n.unread_problem) : '';
}

/**
 * An empty map keyed by session name, with no prototype, so a name such as
 * __proto__ or constructor (both legal under C0) is an own key like any
 * other. Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14.
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
 * role_source says inferred (C5), and never on a peer (D27: `inferred`
 * marks a guess, and a peer is none; the feed gives a peer role_source
 * `none`). A node with no role is its name alone.
 * Model: Claude Opus 5.5 (the BOARD lane agent), 2026-10-14; the peer rule
 * by the P4 phase fixer, round 2, 2026-10-15. Status: unreviewed.
 * @complexity O(1)  @alloc one string
 */
export function roleTitle(node) {
  if (!node.role) return String(node.id);
  const guessed = node.role_source === 'inferred' && node.role !== 'peer';
  return `${node.id} · ${node.role}${guessed ? ' · inferred' : ''}`;
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
 * Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
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
 * Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14, from
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
 * The badge lines each node's box carries, in words: `inbox unreadable` on
 * a down node whose inbox the board could not list (C5, D28: it cannot
 * tell whether mail woke it), `native with b · not
 * observed` on both boxes of a native pair (C5's words, drawn whether or
 * not the pair also mails, never on account `unknown`, D15), and `reports
 * to q · cycle` on a reports_to cycle's root (its reports_to names a node,
 * yet the walk gave it no parent). Each badge is { lead, names, tail, text }:
 * on a box only the names may shorten.
 * Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14; the inbox line by
 * the P4 phase fixer, round 2, 2026-10-15. Status: unreviewed.
 * @interacts  none; pure
 * @complexity O(n + l + p log p) over n nodes, l links and p native partners
 *             of one node (its names are sorted)
 * @alloc      one partner set per node in a native pair, freed on return;
 *             the returned map and one small object per badge
 * @returns {{id: {lead, names, tail, text}[]}}  every node has a key
 */
function badgesOf(feed, known) {
  const partners = new Map();
  for (const l of (feed && feed.links) || []) {
    if (l.kind !== 'native') continue;
    const p = known.get(l.from);
    const q = known.get(l.to);
    if (!p || !q || p === q || !nativeAllowed(p, q)) continue;
    for (const [m, o] of [[p.id, q.id], [q.id, p.id]]) {
      if (!partners.has(m)) partners.set(m, new Set());
      partners.get(m).add(o);
    }
  }
  const badge = (lead, names, tail) => ({ lead, names, tail, text: `${lead}${names}${tail}` });
  const out = nameMap();
  for (const n of known.values()) {
    const list = [];
    if (n.state === 'down' && n.inbox_unreadable) list.push(badge(INBOX_WORDS.unreadable, '', ''));
    if (n.reports_to != null && n.reports_to !== n.id && known.has(n.reports_to) && n.parent == null) {
      list.push(badge(`${LINK_WORDS.reports_to} `, String(n.reports_to), ` · ${LINK_WORDS.cycle}`));
    }
    if (partners.has(n.id)) {
      const names = [...partners.get(n.id)].sort(byName).join(', ');
      list.push(badge(`${LINK_WORDS.nativeWith} `, names, ` · ${LINK_WORDS.notObserved}`));
    }
    out[n.id] = list;
  }
  return out;
}

/**
 * Where a C5 feed's nodes go, inside `width` board px (Infinity, the
 * default, never wraps). Roots in name order, levels top to bottom (C5),
 * on treeOf's tree. A parent sits over its children. The children, each
 * with its own subtree, fill a row left to right and wrap to a new row,
 * LAYOUT_WRAP_GAP lower, when the next one would pass the width, so the
 * board keeps its text size on a narrow screen. Where a row holds a single
 * box (a phone), the parent sits at the left and its children are indented
 * LAYOUT_INDENT under it while a box still fits. Root trees fill rows the
 * same way: LAYOUT_ROOT_GAP apart side by side, LAYOUT_ROW_GAP apart one
 * under another. Each subtree keeps a band no other box enters, so no two
 * boxes overlap. The extent stays within `width` whenever one box and the
 * margins fit in it and the tree is not both deep and bushy: each level
 * with two or more children keeps a lane out of its children's room, and
 * once a level's room is under NODE_W + LAYOUT_LANE its children's blocks
 * run past it. A tree about ten levels deep with two children at each
 * level outgrows a 560 px stage that way, and the canvas clips its right
 * edge; no board the owner runs comes near that. Every map is keyed with
 * no prototype (or is a Map), so a node named __proto__ lays out like any
 * other.
 *
 * Each box is NODE_H tall plus BADGE_H per badge line (badgesOf); `heights`
 * and `badges` say so. Each root's tree starts with a band HEAD_H +
 * HEAD_GAP tall for its heading, as wide as the tree; `heads` says where
 * each heading goes.
 *
 * `via` says where each child's tree connector turns, for routeTree. A
 * child in its parent's first row is reached across `band`, the middle of
 * the LAYOUT_ROW_GAP under the parent, which no box enters. A child in a
 * wrapped row is reached down `gutter`, then across `band`, the middle of
 * the LAYOUT_WRAP_GAP over its row. A block whose children wrap starts them
 * LAYOUT_LANE in (LAYOUT_INDENT where they indent anyway), and its gutter
 * runs down the middle of that lane: no box enters it, and every child's
 * block starts past it, so two parents never share a gutter. A parent with
 * two or more children keeps that lane out of the room it gives each
 * child, so a child's block never runs past the parent's room.
 * @interacts  none; pure
 * @complexity O(n log n + l) over n nodes and l links: one sort by name,
 *             badgesOf, then three walks that visit each node a fixed
 *             number of times
 * @alloc      the returned maps; eight Maps and the row lists for the
 *             walks, freed on return
 * @returns {{ pos: {id: {x, y}}, heights: {id: number}, badges: {id: object[]}, titles: {id: string},
 *            rows: {id: number}, roots: string[], kids: Map<string, string[]>, via: {id: {band, gutter}},
 *            heads: {id: {x, y, w, h}}, extent: {w, h} }}
 *          rows is each node's depth in its tree; gutter is null for a first-row child;
 *          heads is keyed by root
 */
export function layoutLevels(feed, width = Infinity) {
  const C = CONFIG;
  const { nodes, known, kids, roots } = treeOf(feed);
  const badges = badgesOf(feed, known);
  const heights = nameMap();
  for (const n of nodes) heights[n.id] = C.NODE_H + badges[n.id].length * C.BADGE_H;
  // Walk 1, top down: each node's depth, and the width its subtree may use.
  // A row that cannot hold two boxes is narrow: its children indent. A
  // parent with two or more children may wrap them, so it keeps its lane
  // out of their room.
  const rows = nameMap();
  const room = new Map();
  const indent = new Map();
  const kept = new Map();
  const order = [...roots];
  const rootRoom = width - 2 * C.LAYOUT_MARGIN;
  for (const r of roots) {
    rows[r] = 0;
    room.set(r, rootRoom);
  }
  for (let i = 0; i < order.length; i += 1) {
    const id = order[i];
    const w = room.get(id);
    const cs = kids.get(id) || [];
    const narrow = w < 2 * C.NODE_W + C.LAYOUT_COL_GAP;
    const ind = narrow && w - C.LAYOUT_INDENT >= C.NODE_W ? C.LAYOUT_INDENT : 0;
    indent.set(id, ind);
    kept.set(id, ind || (cs.length > 1 ? C.LAYOUT_LANE : 0));
    for (const c of cs) {
      rows[c] = rows[id] + 1;
      room.set(c, w - kept.get(id));
      order.push(c);
    }
  }
  // Walk 2, bottom up: each subtree's block, its children's places inside
  // it, where each child's tree connector turns, and where the node's own
  // box sits in it.
  const block = new Map();
  const inBlock = new Map();
  const ownX = new Map();
  const lane = new Map();
  for (let i = order.length - 1; i >= 0; i -= 1) {
    const id = order[i];
    const cs = kids.get(id) || [];
    const h = heights[id];
    if (!cs.length) {
      block.set(id, { w: C.NODE_W, h });
      ownX.set(id, 0);
      lane.set(id, 0);
      continue;
    }
    const ind = indent.get(id);
    const lines = packRows(cs.map((c) => ({ id: c, ...block.get(c) })), room.get(id) - kept.get(id), C.LAYOUT_COL_GAP);
    const left = ind || (lines.length > 1 ? C.LAYOUT_LANE : 0);
    lane.set(id, left);
    let y = h + C.LAYOUT_ROW_GAP;
    let areaW = 0;
    lines.forEach((line, li) => {
      let x = left;
      const band = li ? y - C.LAYOUT_WRAP_GAP / 2 : h + C.LAYOUT_ROW_GAP / 2;
      for (const b of line.items) {
        inBlock.set(b.id, { x, y, band, wrapped: li > 0 });
        x += b.w + C.LAYOUT_COL_GAP;
      }
      areaW = Math.max(areaW, line.w);
      y += line.h + C.LAYOUT_WRAP_GAP;
    });
    ownX.set(id, ind ? 0 : left + (areaW - C.NODE_W) / 2);
    block.set(id, { w: Math.max(C.NODE_W, left + areaW), h: y - C.LAYOUT_WRAP_GAP });
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
    const gutter = o.x + lane.get(id) / 2;
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
  return { pos, heights, badges, titles, rows, roots, kids, via, heads, extent };
}

/**
 * The width layoutLevels may use on a canvas `canvasWidth` CSS px wide: the
 * most the board may span at the smallest scale MIN_FIT_SCALE allows, so at
 * the scale fitTransform then picks it never runs past the canvas.
 * Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
 * @complexity O(1)  @alloc none
 */
export function layoutWidth(canvasWidth) {
  return canvasWidth / CONFIG.MIN_FIT_SCALE;
}

// ---------- routing and labels ----------
// Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
//
// The rule, one for the whole board: every wire and connector is a run of
// straight horizontal and vertical pieces that never enters a node box it
// does not end at. The ports belong to the tree. A parent's connector to
// its child leaves the parent's out port, at the middle of its bottom
// edge, and enters the child's in port, at the middle of its top edge,
// turning only in gaps the layout keeps empty (routeTree); so a line into
// a port always comes from that box's parent. Their mail wire, or their
// native line, runs TREE_WIRE_OFFSET beside that connector and never on it
// (routeTreeWire), so the connector never fills its dots or dashes.
// Siblings' wires may share a stretch; there drawEdge paints a dotted or
// dashed wire over the solid ones on a knockout, so no stroke fills its
// gaps whatever the shape. Every
// other pair (siblings, a child and a grandparent, two trees, two peers)
// joins a side of one box to a side of the other by the shortest such run
// with the fewest bends through the room round the boxes, keeping
// ROUTE_CLEAR px from every box and every port (routeAround), so two boxes
// side by side in one row are joined straight across. It would rather
// cross a connector or a tree wire than run alongside one. Bends are drawn
// with round corners of at most ROUTE_CLEAR (roundedPath), which keeps the
// curve as clear as the corner.

/** One step in each direction: right, left, down, up. */
const STEPS = Object.freeze([[1, 0], [-1, 0], [0, 1], [0, -1]]);
/** The step that undoes each of STEPS. */
const BACK = Object.freeze([1, 0, 3, 2]);
/** The sides routeAround joins (right, left), and which way each stub leaves (an index into STEPS). */
const SIDES = Object.freeze([{ dx: 1, dy: 0, dir: 0 }, { dx: -1, dy: 0, dir: 1 }]);
// Model: Claude Opus 5.5 (the P4 phase fixer), 2026-10-15. Status: unreviewed.
// What routeAround learns of one grid edge, kept so each edge is checked
// once per search (0: not checked yet): it enters an obstacle, it is clear,
// or it is clear and runs alongside a connector. Each grid point owns two
// edges, the one to its right neighbor and the one to the point below.
const EDGE = Object.freeze({ BLOCKED: 1, FREE: 2, ALONG: 3 });
const EDGES_PER_POINT = 2;

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
 * first-row child), or across to the gutter in the parent's lane, down it,
 * and across the band over the child's row (a wrapped child). Every turn
 * sits in a gap the layout keeps empty, so no box is entered. The out port
 * sits on the parent's bottom edge, however many badge lines it carries.
 * @interacts  none; pure
 * @complexity O(1)  @alloc one list of at most six points
 */
export function routeTree(lay, parent, child) {
  const out = levelPort(lay.pos[parent], 'out', lay.heights[parent]);
  const into = levelPort(lay.pos[child], 'in');
  const v = lay.via[child];
  if (v.gutter === null) return simplify([out, { x: out.x, y: v.band }, { x: into.x, y: v.band }, into]);
  const drop = out.y + CONFIG.LAYOUT_ROW_GAP / 2;
  return simplify([
    out, { x: out.x, y: drop }, { x: v.gutter, y: drop }, { x: v.gutter, y: v.band }, { x: into.x, y: v.band }, into,
  ]);
}

/**
 * A run moved `d` px to one side of each of its pieces: side 1 is the left
 * of the way it runs (east while it runs down), -1 the right. Every inner
 * point of a simplified run is a right-angle bend, where the two moved
 * pieces meet at the point moved by both, so the result keeps the run's
 * shape d px out and has no piece in common with it.
 * Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
 * @complexity O(p) over p points  @alloc one list
 */
function offsetRun(points, d, side) {
  const normals = points.slice(1).map((q, i) => {
    const dx = Math.sign(q.x - points[i].x);
    const dy = Math.sign(q.y - points[i].y);
    return { x: side * dy * d, y: -side * dx * d };
  });
  const none = { x: 0, y: 0 };
  return points.map((p, i) => {
    const before = normals[i - 1] || none;
    const after = normals[i] || none;
    return { x: p.x + before.x + after.x, y: p.y + before.y + after.y };
  });
}

/**
 * The run a parent and child's mail wire, or their native line, takes:
 * routeTree's run moved TREE_WIRE_OFFSET to one side (offsetRun), so it
 * shares no piece with the connector and crosses it nowhere. It leaves the
 * parent's bottom edge and enters the child's top edge TREE_WIRE_OFFSET
 * beside each port, on the side the connector first turns toward (west for
 * a child left of its parent or in a wrapped row, east otherwise), and its
 * first level piece runs on the parent's side of the connector's. So the
 * wires to a parent's children on its two sides keep apart; two children
 * on one side share the parent's end of their wires, as their connectors
 * share theirs, and drawEdge's layers and knockout keep a dotted or dashed
 * wire's gaps clear on that shared stretch.
 * Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
 * @interacts  none; pure
 * @complexity O(1)  @alloc two lists of at most six points
 */
function routeTreeWire(lay, parent, child) {
  const run = routeTree(lay, parent, child);
  const level = run.findIndex((p, i) => i > 0 && p.y === run[i - 1].y);
  const west = level > 0 && run[level].x < run[level - 1].x;
  return offsetRun(run, CONFIG.TREE_WIRE_OFFSET, west ? -1 : 1);
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
 * bottom to the lower's top. `counts`, when given (a route cache), gains
 * one in edgeHits each time the search looks up a grid edge it already
 * checked, which a test reads to see the edge flags at work.
 * @interacts  none; pure, but for adding to counts.edgeHits when given
 * @complexity O(g log g) over the g = 4 * X * Y search states, X and Y the
 *             line counts (X at most 4b + 3 and Y at most 4b + 7 over b
 *             obstacles: two lines per obstacle, the ring, the two middle
 *             heights and a middle between each two neighbors), plus an
 *             O(b + a) check of each grid edge, made once per search and
 *             kept, over a pieces of `along`. boardView's b is 3n + r (n
 *             boxes, two ports each, r headings): 46 on the 14-name test
 *             feed, where a is 64, X 79, Y 101 and g 31,916; 80 for 20
 *             peers, where g is 12,180
 * @alloc      the line lists, a cache of X * Y free flags and one of
 *             2 * X * Y grid edge flags, and the search's heap and maps,
 *             all freed on return; the returned points
 * @returns {{x, y}[]}
 */
export function routeAround(obstacles, from, to, extent, along = [], counts = null) {
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
  // One grid edge's EDGE value, worked out the first time the search
  // meets it and kept, as free() keeps each point's.
  const edgeFlags = new Uint8Array(xs.length * ny * EDGES_PER_POINT);
  const edgeOf = (ix, iy, jx, jy) => {
    const k = (Math.min(ix, jx) * ny + Math.min(iy, jy)) * EDGES_PER_POINT + (ix === jx ? 1 : 0);
    if (!edgeFlags[k]) {
      if (!pieceFree(ix, iy, jx, jy)) edgeFlags[k] = EDGE.BLOCKED;
      else edgeFlags[k] = alongside({ x: xs[ix], y: ys[iy] }, { x: xs[jx], y: ys[jy] }) ? EDGE.ALONG : EDGE.FREE;
    } else if (counts) {
      counts.edgeHits += 1;
    }
    return edgeFlags[k];
  };
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
      if (jx < 0 || jy < 0 || jx >= xs.length || jy >= ny || !free(jx, jy)) return;
      const edge = edgeOf(ix, iy, jx, jy);
      if (edge === EDGE.BLOCKED) return;
      const length = Math.abs(xs[jx] - xs[ix]) + Math.abs(ys[jy] - ys[iy]);
      const weight = edge === EDGE.ALONG ? CONFIG.ROUTE_ALONG_COST : 1;
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
 * Where each labeled edge's words go: a box beside a spot
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
 * The pill's words and state for a feed: `live · N listening`, or, while a
 * node is down or woken, `N listening · M no listener · K woken · not
 * read` (each part only when it counts one or more), in the same words the
 * boxes show (STATES.down, STATES.woken), and the state turns to warn. A
 * working node raises nothing (D24: it is on its turn). Listeners are
 * counted by listener_pid (a pid tc read from /proc/locks), never by
 * state: under D15 a listener that just sent reads writing and is still
 * listening.
 * Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
 * @interacts  none; pure
 * @complexity O(n) over n feed nodes  @alloc one object and a short list
 * @returns {{ text, state, listening }}  state: 'up' | 'warn', for createWindow's setConn
 */
export function pillText(feed) {
  const nodes = (feed && feed.nodes) || [];
  const listening = nodes.filter((n) => n.listener_pid).length;
  const warnings = ['down', 'woken']
    .map((state) => [nodes.filter((n) => n.state === state).length, STATES[state].word])
    .filter(([count]) => count > 0)
    .map(([count, word]) => `${count} ${word}`);
  return warnings.length
    ? { text: [`${listening} listening`, ...warnings].join(' · '), state: 'warn', listening }
    : { text: `live · ${listening} listening`, state: 'up', listening };
}

/**
 * A node's third line: a reports_to that names no node, else its status. A
 * down or woken node's status is stale (it was written before the node
 * stopped listening), so it reads `last status: ...` and never passes for
 * the node's state now.
 * @complexity O(1)  @alloc one string
 */
function noteFor(n, known) {
  if (n.reports_to && !known.has(n.reports_to)) return `${LINK_WORDS.reports_to} ${n.reports_to} · ${LINK_WORDS.notFound}`;
  if (!n.status) return '';
  return n.state === 'down' || n.state === 'woken' ? `${NOTE_WORDS.lastStatus} ${n.status}` : n.status;
}

// ---------- roots, headings and the phone's outline ----------
// Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.

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
 * the page: `2 orchestrators: a, z · 2 peers: p1, p2`.
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
 * The outline view of a feed, for a phone: no wires. One group per root,
 * in name order, headed by headWords (null for a tree of one session,
 * whose row says the same); in it one row
 * per session of that tree, parent before children, each `depth` levels
 * under its root, with its name, its role words, its state's glyph and
 * word, its unread count (unreadWords), its note (as boardView's), tc's
 * reason an unread count is unknown (problemOf, drawn as text) and its badges'
 * words (badgesOf: a native pair, a cycle's root, an inbox the board could
 * not list), one line each. Then the
 * recent traffic: one line per pair, its newest message, `a → b · #18 · 2
 * m ago`, newest first.
 * @interacts  none; pure
 * @complexity O(n log n + l + r log r) over n nodes, l links and r recent wires  @alloc the returned model
 * @returns {{ groups: { root, heading: string | null, rows: { id, depth, role, state, glyph, word, unread, note, problem, badges }[] }[],
 *            traffic: { from, to, seq, text }[] }}
 */
export function outlineView(feed) {
  const { known, kids, roots } = treeOf(feed);
  const badges = badgesOf(feed, known);
  const groups = roots.map((root) => {
    const rows = [];
    for (const stack = [[root, 0]]; stack.length;) {
      const [id, depth] = stack.pop();
      const n = known.get(id);
      const state = STATES[n.state] ? n.state : 'idle';
      rows.push({
        id, depth, role: roleTitle(n).slice(String(id).length), state, glyph: STATES[state].glyph, word: STATES[state].word,
        unread: unreadWords(n), note: noteFor(n, known), problem: problemOf(n), badges: badges[id].map((b) => b.text),
      });
      const children = kids.get(id) || [];
      for (let i = children.length - 1; i >= 0; i -= 1) stack.push([children[i], depth + 1]);
    }
    // A tree of one session needs no heading over its one row.
    return { root, heading: rows.length > 1 ? headWords(roleTitle(known.get(root)), rows.length) : null, rows };
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
 * and h (layoutLevels: the box's place and height), state, detail (unread
 * count, or `unread unknown`: unreadWords), note (`reports to N · not found`, else the status line, as `last
 * status: ...` on a down or woken node), problem (tc's reason an unread
 * count is unknown, or '': problemOf), `badges` (badgesOf: `native with b · not
 * observed` on both boxes of a native pair, `reports to q · cycle` on a
 * cycle's root, `inbox unreadable` on a down node whose inbox the board
 * could not list), and `connector`: on a node with a parent in the layout,
 * the hierarchy's own thin line from the parent's out port to this node's
 * in port (routeTree), with its words for a title and no label on the
 * board (the legend says what the thin line is); null on a root. It
 * belongs to the child, so it comes and goes and moves with it. It
 * replaces the reports_to hint, so a feed's reports_to links draw nothing
 * of their own: one that names no node is its node's note, and a cycle's
 * root carries its reports_to on a badge. A root's view has `head`, the
 * heading over its tree (layoutLevels' heads, with headWords' text); any
 * other node's is null. Wires and labels keep off headings as they do off
 * boxes.
 *
 * Edges, each a run of points (the rule is in the routing section above),
 * with `words` for its title, always:
 * - a mailbox link whose two ends are nodes: on a parent and child,
 *   routeTreeWire's run beside their connector; on any other pair,
 *   routeAround's run from the upper node to the lower, kept off the
 *   connectors and the tree wires where it can be. It flows, with dashes,
 *   an arrow at the reader and the label `from → to · #seq`, when its
 *   pair's newest wire is at most FLOW_AGE_S old; quiet, it is a solid line
 *   with no label. It is down when either end is down; a woken end (D24)
 *   never makes it down: the mail that woke it is drawn as any mail is.
 * - a native link with no mailbox link on its pair: the same runs,
 *   dash-dot, no label; its words, `native · not observed`, are in its
 *   title, on both boxes' badges and in the legend. On a pair with mail
 *   too, they go in the mail wire's title and on the badges, and no second
 *   line is drawn. On account `unknown` (D15) a native link draws nothing.
 * A label sits where placeLabels puts it (`at`), clear of every node box
 * and every other label, or is dropped (`at` null) with its words kept in
 * the title.
 * `routes`, when given (createRouteCache), keeps the routed runs by their
 * two ends: on the key the last call left there (the boxes, headings,
 * extent, connectors and tree wires) each pair it holds a run for reuses
 * it with no search, and only a pair it has none for searches. Each search
 * adds one to routes.searches, and each grid edge a search looks up again
 * one to routes.edgeHits. Runs reused or found again are the same, so the
 * board draws the same either way.
 * @interacts  none; pure, but for writing `routes` when given
 * @complexity O(n log n + l + r) for the layout and the edges over n
 *             nodes, l links and r wires, plus the route key, O(n + t)
 *             over the boxes and the t tree runs it names; routeAround per
 *             routed pair when there is no `routes` or its key changed,
 *             else per routed pair new to it; and placeLabels for the
 *             labels
 * @alloc      the returned views, one box per node, the key string and the
 *             routing's working sets, freed on return; with `routes`, its
 *             runs map, one run per routed pair drawn now, replaced on
 *             each call
 * @returns {{ nodes: {id: view}, edges: {id: view}, extent: {w, h} }}
 */
export function boardView(feed, width, routes = null) {
  const C = CONFIG;
  const lay = layoutLevels(feed, width);
  const known = new Map(((feed && feed.nodes) || []).map((n) => [n.id, n]));
  const nodes = nameMap();
  const boxOf = nameMap();
  for (const n of known.values()) {
    nodes[n.id] = {
      id: n.id, title: lay.titles[n.id], pos: lay.pos[n.id], h: lay.heights[n.id],
      state: STATES[n.state] ? n.state : 'idle', detail: unreadWords(n),
      note: noteFor(n, known), problem: problemOf(n), badges: lay.badges[n.id], connector: null, head: null,
    };
    boxOf[n.id] = { x: lay.pos[n.id].x, y: lay.pos[n.id].y, w: C.NODE_W, h: lay.heights[n.id] };
  }
  for (const root of lay.roots) {
    nodes[root].head = { ...lay.heads[root], text: headWords(lay.titles[root], treeSize(lay.kids, root)) };
  }
  const headBoxes = lay.roots.map((root) => lay.heads[root]);
  // Wires keep clear of every box, every port's stub and every heading;
  // labels keep off every box, every port ring and every heading.
  const boxes = Object.values(boxOf);
  const ports = (size) => boxes.flatMap((b) => ['in', 'out'].map((side) => {
    const at = levelPort(b, side, b.h);
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
    .filter((l) => l.kind === kind && known.has(l.from) && known.has(l.to) && l.from !== l.to
      && (kind !== 'native' || nativeAllowed(known.get(l.from), known.get(l.to))))
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
  // The links to draw, each with its ends top-down. A parent and child's
  // run is routeTreeWire's, found first, so every other run can keep off
  // those as well as off the connectors.
  const drawn = [];
  for (const l of links) {
    const p = known.get(l.from);
    const q = known.get(l.to);
    if (!p || !q || p === q || (l.kind !== 'mailbox' && l.kind !== 'native')) continue;
    const pair = pairKey(l.from, l.to);
    // A native link whose pair also has mail rides in that wire's title and
    // on the badges; on account `unknown` it draws nothing (D15).
    if (l.kind === 'native' && (mailboxPairs.has(pair) || !nativeAllowed(p, q))) continue;
    const tree = parentOf[q.id] === p.id || parentOf[p.id] === q.id;
    let ends = upperFirst(p, q, lay.pos).map((n) => n.id);
    if (tree) ends = parentOf[q.id] === p.id ? [p.id, q.id] : [q.id, p.id];
    drawn.push({ l, p, q, pair, from: ends[0], to: ends[1], points: tree ? routeTreeWire(lay, ends[0], ends[1]) : null });
  }
  const along = [...connectors, ...drawn.filter((d) => d.points).map((d) => d.points)];
  // Model: Claude Opus 5.5 (the P4 phase fixer), 2026-10-15; keyed per pair
  // by the P4 phase fixer, round 2. Status: unreviewed.
  // A routed run rests on the boxes by name, the headings, the extent and
  // the runs to keep off, one key for them all, and on its own two ends,
  // never on another routed pair: routeAround keeps off boxes, ports,
  // headings and `along`, and no routed run is in `along`. So on the key
  // `routes` holds, a pair it has a run for reuses it, and only a pair new
  // to it searches; a feed that only moved its ages or its flow, or gave a
  // native pair its first mail, searches none.
  const key = routes ? JSON.stringify([Object.entries(boxOf), headBoxes, lay.extent, along]) : null;
  const reuse = !!routes && routes.key === key;
  const runs = new Map();
  for (const { l, p, q, pair, from, to, points } of drawn) {
    const id = `${l.kind}:${l.from}>${l.to}`;
    const ends = `${from}>${to}`;
    let run = points || (reuse ? routes.runs.get(ends) : null);
    if (!run) {
      run = routeAround(obstacles, boxOf[from], boxOf[to], lay.extent, along, routes);
      if (routes) routes.searches += 1;
    }
    if (!points) runs.set(ends, run);
    const w = l.kind === 'mailbox' ? flowing.get(pair) : undefined;
    const back = !!w && w.from !== from;
    const label = w ? `${w.from} → ${w.to} · #${w.seq}` : '';
    const native = l.kind === 'native' || nativePairs.has(pair);
    const said = l.kind === 'mailbox' ? (label || `${TREE_WORDS.mail} ${from} and ${to}`) : `${from} and ${to}`;
    edges[id] = {
      id, kind: l.kind, from, to, points: run,
      label, seq: w ? w.seq : null, words: native ? `${said} · ${LINK_WORDS.native}` : said,
      arrow: w ? (back ? 'start' : 'end') : null, flow: !!w, back,
      down: l.kind === 'mailbox' && (p.state === 'down' || q.state === 'down'),
    };
  }
  if (routes) {
    routes.key = key;
    routes.runs = runs;
  }
  const spots = placeLabels(edges, [...boxes, ...ports(C.PORT_SIZE / 2), ...headBoxes], lay.extent);
  for (const e of Object.values(edges)) e.at = spots[e.id] || null;
  return { nodes, edges, extent: lay.extent };
}

const NODE_FIELDS = ['title', 'state', 'detail', 'note', 'problem', 'h'];
const EDGE_FIELDS = ['kind', 'from', 'to', 'label', 'seq', 'words', 'arrow', 'flow', 'back', 'down'];

/** True when two points sit at the same place. @complexity O(1)  @alloc none */
function samePoint(p, q) {
  return p.x === q.x && p.y === q.y;
}

/** True when two runs of points are the same. @complexity O(p) over p points  @alloc none */
function samePoints(p, q) {
  return p.length === q.length && p.every((pt, i) => samePoint(pt, q[i]));
}

/** One string for a node's badges, to compare two views by. @complexity O(b) over b badges  @alloc one string */
function badgeKey(badges) {
  return (badges || []).map((b) => b.text).join('\n');
}

/** True when two node views would draw the same, connector, heading and badges too. @complexity O(p + b) over p connector points and b badges  @alloc two short strings */
function sameNode(p, q) {
  const sameConnector = p.connector === q.connector || (p.connector && q.connector
    && p.connector.words === q.connector.words && samePoints(p.connector.points, q.connector.points));
  const sameHead = p.head === q.head || (p.head && q.head && p.head.text === q.head.text
    && samePoint(p.head, q.head) && p.head.w === q.head.w);
  return NODE_FIELDS.every((f) => p[f] === q[f]) && samePoint(p.pos, q.pos) && !!sameConnector && !!sameHead
    && badgeKey(p.badges) === badgeKey(q.badges);
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
 * An empty route cache for boardView: `key`, what the last routed runs
 * rested on; `runs`, those runs by their two ends (`from>to`, from the
 * upper box); `searches`, how many routeAround searches it has run; and
 * `edgeHits`, how many times those searches looked up a grid edge they
 * had already checked (routeAround's edge flags): the counts a test reads.
 * Model: Claude Opus 5.5 (the P4 phase fixer), 2026-10-15; runs by ends and
 * edgeHits by the P4 phase fixer, round 2. Status: unreviewed.
 * @complexity O(1)  @alloc one object and an empty Map
 */
export function createRouteCache() {
  return { key: null, runs: new Map(), searches: 0, edgeHits: 0 };
}

/**
 * Everything boardView reads from a feed, laid out at `width`, as one
 * string: each node less last_mail_age_s (an age boardView never reads),
 * each link's ends and kind, and each wire's ends, seq and whether it
 * flows (age_s at most FLOW_AGE_S). `at`, the machine and every other age
 * are left out, so two polls a few seconds apart with no news give one key.
 * Model: Claude Opus 5.5 (the P4 phase fixer), 2026-10-15. Status: unreviewed.
 * @complexity O(n + l + r) over n nodes, l links and r wires
 * @alloc      n + l + r + 4 short-lived objects (a copy of each node, an
 *             array per link and per wire, and the four arrays round them),
 *             freed on return; the key string, returned
 */
function drawnKey(feed, width) {
  const nodes = ((feed && feed.nodes) || []).map(({ last_mail_age_s: _age, ...rest }) => rest);
  const links = ((feed && feed.links) || []).map((l) => [l.from, l.to, l.kind]);
  const wires = ((feed && feed.wires) || []).map((w) => [w.from, w.to, w.seq, w.age_s != null && w.age_s <= CONFIG.FLOW_AGE_S]);
  return JSON.stringify([width, nodes, links, wires]);
}

/**
 * An empty board drawn through `kit`: { kit, nodes, edges, view, routes,
 * drawn }. kit has createNode(view) and createEdge(view), each returning
 * a handle with update(view) and remove(). createKit(doc, canvas) is the
 * DOM kit. `routes` is the board's route cache (createRouteCache) and
 * `drawn` the key of the feed it last drew (drawnKey).
 * @complexity O(1)  @alloc two empty maps, an empty view and an empty route cache
 */
export function createBoard(kit) {
  return {
    kit, nodes: new Map(), edges: new Map(), view: { nodes: nameMap(), edges: nameMap(), extent: { w: 0, h: 0 } },
    routes: createRouteCache(), drawn: null,
  };
}

/**
 * Bring `board` to `feed`, laid out inside `width` (see layoutLevels): add,
 * move and remove nodes and edges by id through board.kit, never rebuilding
 * what stays (C5). Returns the diff it applied. A feed whose drawnKey is the
 * last one drawn (a poll that only aged the mail, with no wire crossing
 * FLOW_AGE_S) would draw the same board, so nothing is laid out and the
 * diff is empty. Otherwise boardView lays it out with board.routes, which
 * searches only the routed pairs new to it while the boxes, headings,
 * extent and tree runs stand.
 * @interacts  calls board.kit and the handles it made; writes board.nodes,
 *             board.edges, board.view, board.routes and board.drawn
 * @complexity O(n + l + r) for drawnKey; when it changed, boardView's
 *             (a route search per routed pair on a route key miss, else
 *             per pair new to the cache, and labels), plus O(c) kit calls
 *             for c changes
 * @alloc      drawnKey's: n + l + r + 4 short-lived objects and the key
 *             string, kept as board.drawn; when it changed, one full view
 *             (an object per node and edge, plus the layout's maps), kept
 *             as board.view
 *             until the next one; one handle per added node or edge; each
 *             removed one is dropped from the maps after its remove()
 */
export function patchBoard(board, feed, width) {
  const drawn = drawnKey(feed, width);
  if (drawn === board.drawn) {
    return { addNodes: [], updateNodes: [], removeNodes: [], addEdges: [], updateEdges: [], removeEdges: [] };
  }
  const next = boardView(feed, width, board.routes);
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
  board.drawn = drawn;
  return ops;
}

/**
 * The layer an edge view is drawn in (WIRE_LAYERS): 'down' for a wire with
 * an end that has no listener (dotted), 'dashed' for a flowing wire or a
 * native line, 'plain' for a quiet mail wire (solid).
 * Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
 * @complexity O(1)  @alloc none
 */
function wireLayer(v) {
  if (v.down) return 'down';
  return v.flow || v.kind === 'native' ? 'dashed' : 'plain';
}

/**
 * One edge view as SVG: a path along its run with rounded bends
 * (roundedPath), its words in a title (shown on hover), and its label,
 * where placeLabels put one, centered in that box on an opaque backing of
 * the box's size, in canvas.labels, so it reads over any wire. The path
 * goes in its wireLayer's group of canvas.layers, and moves when its
 * layer changes. A dotted or dashed wire has a knockout right under it: a
 * path on the same run in the canvas's own color, wider than the wire
 * (theme.css .tc-knockout), so whatever its layer paints over (every solid
 * wire and connector, and for a dotted wire every dashed one) is hidden
 * along it, and its gaps show the canvas. Siblings' wires share the
 * parent's end of their runs (routeTreeWire), so this holds whatever the
 * shape; a solid wire under a dotted one shows again where it turns away.
 * @interacts  puts the path (and, while it is dotted or dashed, its
 *             knockout) in one of canvas.layers, and the label and its
 *             backing in canvas.labels; remove() takes all four out
 * @complexity O(p) per call over p points
 * @alloc      one path with a title, one knockout path, one rect and one
 *             text element
 * @returns {{ path, knock, label, update(view), remove() }}
 */
export function drawEdge(doc, canvas, view) {
  // Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
  const knock = svg(doc, 'path', { class: 'tc-knockout' });
  const path = svg(doc, 'path', { class: 'tc-wire' });
  const tip = svg(doc, 'title');
  path.append(tip);
  const back = svg(doc, 'rect', { class: 'tc-wire-label-back' });
  const label = svg(doc, 'text', { class: 'tc-wire-label', 'text-anchor': 'middle', 'dominant-baseline': 'central' });
  canvas.labels.append(back, label);
  let layer = null;
  const edge = {
    path, knock, label,
    update(v) {
      const d = roundedPath(v.points, CONFIG.ROUTE_CLEAR);
      path.setAttribute('d', d);
      path.setAttribute('class', ['tc-wire', `kind-${v.kind}`, v.flow && 'flow', v.back && 'back', v.down && 'down'].filter(Boolean).join(' '));
      path.setAttribute('data-edge', v.id);
      knock.setAttribute('d', d);
      knock.setAttribute('class', `tc-knockout kind-${v.kind}`);
      const next = wireLayer(v);
      if (next !== layer) {
        layer = next;
        knock.remove();
        if (layer === 'plain') canvas.layers.plain.append(path);
        else canvas.layers[layer].append(knock, path);
      }
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
      knock.remove();
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
 * path under every wire (right after the wire layer's defs, before every
 * group of canvas.layers, with its words as a title) and, on a root, the
 * heading over its tree; and edges with drawEdge (each in its layer, a
 * dotted or dashed one on its knockout), all on `canvas`. A node's reveal() scrolls its heading (or its box) to the
 * top of the view. drawOutline(model) brings canvas.outline to outlineView's
 * model in place: each group, row and traffic line keeps its element from
 * one call to the next, only words that changed are written, and an
 * element moves only when the order changed, so a poll that only ages the
 * traffic leaves every row alone (a selection or a screen reader's place
 * survives it). revealOutline(id) scrolls root id's group heading, or its
 * one row, to the top.
 * @interacts  see createNode and drawEdge; a node's remove() takes its
 *             connector and heading out too; drawOutline adds, updates,
 *             moves and removes canvas.outline's elements; the reveals
 *             scroll the page
 * @complexity O(1) per node call plus O(p) over p connector points; edges
 *             as drawEdge; drawOutline O(n + t) over n rows and t traffic
 *             lines
 * @alloc      one node subtree, one connector path and one heading per
 *             node, or one edge's elements (drawEdge's, its knockout
 *             included) per create; drawOutline one
 *             element tree per new group, row or traffic line, each kept
 *             until its group, row or line leaves the model
 */
export function createKit(doc, canvas) {
  // Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
  const groups = new Map();
  let traffic = null;
  const setText = (e, text) => { if (e.textContent !== text) e.textContent = text; };
  // Put `kids` under `parent` in order, moving only the ones out of place.
  const place = (parent, kids) => {
    kids.forEach((kid, i) => { if (parent.children[i] !== kid) parent.insertBefore(kid, parent.children[i] || null); });
    while (parent.children.length > kids.length) parent.lastElementChild.remove();
  };
  const makeRow = () => {
    const row = { root: el(doc, 'div', 'tc-row'), title: el(doc, 'span', 'tc-row-title'), name: el(doc, 'span', 'tc-row-name'),
      role: el(doc, 'span', 'tc-row-role'), state: el(doc, 'span', 'tc-row-state'), note: el(doc, 'span', 'tc-row-note'),
      problem: el(doc, 'span', 'tc-row-problem'), badges: [] };
    row.title.append(row.name, row.role);
    return row;
  };
  const fillRow = (row, r) => {
    const cls = r.depth ? 'tc-row nested' : 'tc-row';
    if (row.root.className !== cls) row.root.className = cls;
    if (row.root.dataset.state !== r.state) row.root.dataset.state = r.state;
    const indent = `${r.depth * CONFIG.OUTLINE_INDENT}px`;
    if (row.root.style.marginLeft !== indent) row.root.style.marginLeft = indent;
    setText(row.name, r.id);
    setText(row.role, r.role);
    setText(row.state, `${r.glyph} ${r.word}${r.unread ? ` · ${r.unread}` : ''}`);
    setText(row.note, r.note);
    if (row.note.hidden !== !r.note) row.note.hidden = !r.note;
    // Model: Claude Opus 5.5 (the P4 phase fixer, round 2), 2026-10-15. Status: unreviewed.
    const problem = r.problem ? `${UNREAD_WORDS.unknown}: ${r.problem}` : '';
    setText(row.problem, problem);
    if (row.problem.hidden !== !problem) row.problem.hidden = !problem;
    while (row.badges.length < r.badges.length) row.badges.push(el(doc, 'span', 'tc-row-badge'));
    while (row.badges.length > r.badges.length) row.badges.pop().remove();
    r.badges.forEach((words, i) => setText(row.badges[i], words));
    place(row.root, [row.title, row.state, row.note, row.problem, ...row.badges]);
  };
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
          node.setHeight(n.h);
          node.setTitle(n.title);
          node.setNote(n.note);
          node.setProblem(n.problem);
          node.setBadges(n.badges);
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
      const sections = model.groups.map((g) => {
        if (!groups.has(g.root)) groups.set(g.root, { root: el(doc, 'section', 'tc-group'), head: el(doc, 'div', 'tc-group-head'), rows: new Map() });
        const group = groups.get(g.root);
        setText(group.head, g.heading || '');
        if (group.head.hidden !== !g.heading) group.head.hidden = !g.heading;
        const ids = new Set(g.rows.map((r) => r.id));
        for (const [id, row] of group.rows) {
          if (!ids.has(id)) {
            row.root.remove();
            group.rows.delete(id);
          }
        }
        const rows = g.rows.map((r) => {
          if (!group.rows.has(r.id)) group.rows.set(r.id, makeRow());
          const row = group.rows.get(r.id);
          fillRow(row, r);
          return row.root;
        });
        place(group.root, [group.head, ...rows]);
        group.jump = g.heading ? group.head : rows[0];
        return group.root;
      });
      const roots = new Set(model.groups.map((g) => g.root));
      for (const [id, group] of groups) {
        if (!roots.has(id)) {
          group.root.remove();
          groups.delete(id);
        }
      }
      if (!traffic) {
        traffic = { root: el(doc, 'section', 'tc-traffic'), head: el(doc, 'div', 'tc-group-head', OUTLINE_WORDS.traffic), lines: [] };
      }
      const words = model.traffic.length ? model.traffic.map((t) => t.text) : [OUTLINE_WORDS.noTraffic];
      while (traffic.lines.length < words.length) traffic.lines.push(el(doc, 'div', 'tc-traffic-line'));
      while (traffic.lines.length > words.length) traffic.lines.pop().remove();
      words.forEach((text, i) => setText(traffic.lines[i], text));
      place(traffic.root, [traffic.head, ...traffic.lines]);
      place(canvas.outline, [...sections, traffic.root]);
    },
    revealOutline(id) {
      const group = groups.get(id);
      if (group && group.jump) group.jump.scrollIntoView({ block: 'start' });
    },
  };
}

/**
 * Scale and offset that fit a board of `extent` inside width x height with
 * `padding` to spare, centered, never enlarged and never under MIN_FIT_SCALE
 * (so no text drops under MIN_TEXT_PX). createFit passes the board's own
 * height plus `padding` as the height, since the frame grows to the board
 * so only the width can call for a smaller scale; a board laid
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
 * poll that changes the board forces no layout. The width picks the view:
 * the outline (outlineView, brought up to date in place by
 * board.kit.drawOutline, and only when it changed) once the stage is under
 * OUTLINE_BELOW_PX, the graph again once it is GRAPH_FROM_PX or wider, so a
 * scrollbar that comes or goes with the view never flips it back.
 * `mark`'s data-view names the view drawn, so theme.css shows that one and
 * its legend. In the graph, draw(feed) lays the feed out at that width
 * (layoutLevels wraps it) and patches the board; a resize that changes the
 * width draws the last feed again, and one that changes only the height
 * (the frame growing) draws nothing. The frame takes the board's height
 * plus `padding`, so the page scrolls down as far as the board goes, never
 * sideways, and the fit never shrinks the board to the frame's height; the
 * view and its wire layer take the board's extent. jump(id) brings root
 * id's tree into view. `Observer` is ResizeObserver on a page; a test
 * passes a fake.
 * Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
 * @interacts  observes canvas.root (the stage) from start() until stop()
 *             (the page calls them on load and pageshow, and on pagehide);
 *             writes mark's data-view, canvas.frame's height, canvas.view's
 *             transform, width and height and canvas.wires' width and
 *             height; calls patchBoard, and through it board.kit, or
 *             board.kit.drawOutline; jump calls a node handle's reveal or
 *             board.kit.revealOutline
 * @complexity one draw or width change: patchBoard's (nothing past its
 *             key when only ages moved; a route search per routed pair
 *             only when a box moved, as a width change does only when a
 *             row wraps differently, else only for a pair new to the
 *             cache), or outlineView's O(n log n + r log r)
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
    // Hysteresis: the outline under OUTLINE_BELOW_PX, the graph again only
    // from GRAPH_FROM_PX, so a stage near the line never flips every frame.
    const below = view === 'outline' ? CONFIG.GRAPH_FROM_PX : CONFIG.OUTLINE_BELOW_PX;
    view = width < below ? 'outline' : 'graph';
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
 * none of them says live. Model: Claude Opus 5.5 (the BOARD fixer),
 * 2026-10-14. Status: unreviewed.
 */
export const CONN_WORDS = Object.freeze({
  // Model: Claude Opus 5.5 (the P4 phase fixer), 2026-10-15. Status: unreviewed.
  tokenDamaged: 'token damaged · copy the URL serve.py printed again',
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
// Model: Claude Opus 5.5 (the P4 phase fixer), 2026-10-15. Status: unreviewed.
// The highest code point an HTTP header value may hold: fetch refuses a
// header past Latin-1 before it sends anything.
const LATIN1_MAX = 0xff;
// Model: Claude Opus 5.5 (the P4 phase fixer, round 2), 2026-10-15. Status:
// unreviewed. NUL, LF and CR: Latin-1, but fetch refuses a header value
// that holds one inside it, before anything is sent. A fragment's %00, %0A
// or %0D decodes to them. A token never holds one, so one anywhere is
// damage.
const HEADER_REFUSED = Object.freeze(['\0', '\n', '\r']);

/**
 * What is wrong with the URL's token before any request: CONN_WORDS.noToken
 * when there is none, CONN_WORDS.tokenDamaged when it holds a character
 * outside Latin-1 (a pasted ellipsis, say) or one of HEADER_REFUSED (NUL,
 * LF, CR), which fetch refuses in the X-TC-Token header, so fetch would
 * throw and the pill would blame a server that is running; else null.
 * serve.py's tokens are token_urlsafe and hold none of these, so any of
 * them, wherever it sits, is damage; any other wrong token reaches the
 * server and gets 401, `token refused`.
 * Model: Claude Opus 5.5 (the P4 phase fixer), 2026-10-15; NUL, LF and CR
 * by the P4 phase fixer, round 2. Status: unreviewed.
 * @complexity O(t) over t characters  @alloc none
 */
export function tokenProblem(token) {
  if (!token) return CONN_WORDS.noToken;
  for (const ch of token) {
    if (ch.codePointAt(0) > LATIN1_MAX || HEADER_REFUSED.includes(ch)) return CONN_WORDS.tokenDamaged;
  }
  return null;
}
// The pill counts the age of the last answer in whole seconds.
const MS_PER_S = 1000;

/**
 * Ask for the feed one request at a time: the next poll starts `pollMs`
 * after the last one settles, so requests never pile up behind a slow or
 * stopped server, and an older answer can never land after a newer one
 * (C6's newest answer wins, by construction). A request still out after
 * `timeoutMs` is aborted. When an answer fails or is late the pill says so
 * in words: `no answer · <why>` before any answer, else `stale · last
 * answer N s ago · <why>`; a 401 says the token was refused. Once a board
 * has been drawn, every failure (a 401 too) also calls onStale(`stale ·
 * last answer N s ago`), so the page can say it over the board and stop
 * its moving wires, and the next good answer calls onStale(null) before
 * onFeed. A good answer goes to onFeed, which writes the pill itself.
 * fetchFeed(signal) returns a fetch Response; timers is { setTimeout,
 * clearTimeout }; now() is a monotonic clock in ms (performance.now on a
 * page, a fake in a test).
 * Model: Claude Opus 5.5 (the BOARD fixer), 2026-10-14. Status: unreviewed.
 * @interacts  calls fetchFeed, timers, now, onFeed, onConn and onStale,
 *             nothing else. start() polls; stop() clears both timers and
 *             aborts the request in flight (the page calls them on load
 *             and pageshow, and on pagehide)
 * @complexity O(1) per poll, plus the caller's onFeed
 * @alloc      one AbortController and two timers while a request is out,
 *             one timer between polls; none after stop()
 * @returns {{ start(), stop() }}
 */
export function createPoller({ fetchFeed, pollMs, timeoutMs, timers, now, onFeed, onConn, onStale = () => {} }) {
  let running = false;
  let next = null;
  let deadline = null;
  let inFlight = null;
  let answeredAt = null;
  // The board's own line once an answer is late: `stale · last answer N s ago`.
  const staleWords = () => `${CONN_WORDS.stale} · last answer ${Math.round((now() - answeredAt) / MS_PER_S)} s ago`;
  const failed = (why) => {
    if (answeredAt === null) {
      onConn(`${CONN_WORDS.noAnswer} · ${why}`, 'down');
      return;
    }
    const words = staleWords();
    onConn(`${words} · ${why}`, 'down');
    onStale(words);
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
        if (answeredAt !== null) onStale(staleWords());
      } else if (!answer.ok) {
        failed(`HTTP ${answer.status}`);
      } else {
        const feed = await answer.json();
        if (inFlight !== ctl) return;
        answeredAt = now();
        onStale(null);
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
