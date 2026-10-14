/**
 * Tests for the Daylight look in board/theme.css: every color the dark look
 * sets is restated for Daylight, and the words Daylight draws clear WCAG's
 * 4.5 to 1 against the face they sit on.
 *
 * Model: Claude Opus 5.5, 2026-10-14. Status: unreviewed.
 *
 * @interacts  reads board/theme.css as text and imports pickLook and LOOKS
 *             from board/look.js; no DOM
 * @deps       node:test, node:assert, node:fs (Node 18+)
 * @complexity O(t) for t tokens in the file, about 50
 * @alloc      the stylesheet text and two token maps, released per test
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const CSS = readFileSync(new URL('../board/theme.css', import.meta.url), 'utf8');
// WCAG 2 AA for body text. Daylight's words are measured against it.
const MIN_TEXT_CONTRAST = 4.5;
// Tokens that are not colors, so Daylight has no reason to restate them.
const NOT_COLORS = /^--tc-(font|mono|radius|bar-w|port|wire-w|dash|gap|flow-speed|pulse-speed)/;

/** The custom properties declared in the first block that opens with `selector {`. */
function tokens(selector) {
  const start = CSS.indexOf(`${selector} {`);
  assert.ok(start >= 0, `no block for ${selector}`);
  const body = CSS.slice(start, CSS.indexOf('\n}', start));
  const out = {};
  for (const m of body.matchAll(/(--tc-[\w-]+):\s*([^;]+);/g)) out[m[1]] = m[2].trim();
  return out;
}

function luminance(hex) {
  const n = hex.replace('#', '');
  const ch = [0, 2, 4].map((i) => parseInt(n.slice(i, i + 2), 16) / 255)
    .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2];
}

function contrast(a, b) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

const dark = tokens(':root');
const day = tokens(":root[data-theme='daylight']");

test('Daylight restates every color the dark look sets', () => {
  const missing = Object.keys(dark).filter((k) => !NOT_COLORS.test(k) && !(k in day));
  assert.deepEqual(missing, [], `Daylight would inherit dark values for: ${missing.join(', ')}`);
});

test('Daylight words clear 4.5 to 1 on the face under them', () => {
  // [words, face, where it shows]
  const pairs = [
    ['--tc-text', '--tc-panel', 'a session title on its card'],
    ['--tc-dim', '--tc-panel', 'a session second line on its card'],
    ['--tc-dim', '--tc-inset', 'the canvas footnote'],
    ['--tc-dim', '--tc-bg', 'the SESSIONS heading'],
    ['--tc-cyan', '--tc-panel', 'the writing state line'],
    ['--tc-red', '--tc-panel', 'the no listener line'],
    ['--tc-text', '--tc-inset', 'a wire label on the canvas'],
    ['--tc-bar-text', '--tc-title-bg', 'the title bar words'],
    ['--tc-bar-dim', '--tc-title-bg', 'the title bar subtitle'],
    ['--tc-bar-muted', '--tc-foot-bg', 'the footer words'],
  ];
  const low = pairs
    .map(([fg, bg, where]) => ({ where, ratio: contrast(day[fg], day[bg]) }))
    .filter((p) => p.ratio < MIN_TEXT_CONTRAST)
    .map((p) => `${p.where} ${p.ratio.toFixed(2)}`);
  assert.deepEqual(low, [], `under ${MIN_TEXT_CONTRAST} to 1: ${low.join('; ')}`);
});

test('the contrast helper matches known WCAG values', () => {
  assert.equal(contrast('#000000', '#ffffff').toFixed(1), '21.0');
  // #007aff on white is the accent the writing line moved off: 4.02.
  assert.ok(contrast('#007aff', '#ffffff') < MIN_TEXT_CONTRAST);
});

test('pickLook: the URL wins, then the stored pick, then dark; unknown names fall through', async () => {
  const { pickLook, LOOKS, DEFAULT_LOOK } = await import('../board/look.js');
  assert.equal(pickLook('daylight', 'dark'), 'daylight');
  assert.equal(pickLook('dark', 'daylight'), 'dark');
  assert.equal(pickLook(null, 'daylight'), 'daylight');
  assert.equal(pickLook('neon', 'daylight'), 'daylight');
  assert.equal(pickLook('neon', 'stale'), DEFAULT_LOOK);
  // Inherited names must not count as looks.
  assert.equal(pickLook('toString', null), DEFAULT_LOOK);
  for (const l of Object.values(LOOKS)) assert.ok(l.glyph && l.word, 'every look has a glyph and a word');
});
