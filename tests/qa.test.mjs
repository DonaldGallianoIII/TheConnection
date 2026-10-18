/**
 * Tests for the QA checklist page (C8, "The page"): board/qa.js's pure
 * layer (the keys, the state words, the counts, the mark rules, the next
 * unmarked row) and its DOM layer, driven through a small fake document,
 * plus a scan of board/qa.html and board/qa.js for innerHTML and for any
 * other host.
 *
 * Model: Claude Opus 5.5 (the QA lane agent), 2026-10-18. Status: unreviewed.
 *
 * @interacts  imports board/qa.js; reads board/qa.html and board/qa.js as
 *             text; no browser and no DOM library (FakeDocument stands in)
 * @deps       node:test, node:assert, node:fs, node:url (Node 18+)
 * @complexity each test builds one page of at most four rows
 * @alloc      one fake document per test, dropped when it returns
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import {
  KEY_HELP, MARKS, STATE_WORDS, ENDED_WORDS, keyAction, nextUnmarked, countWords, markRequest, createPage,
} from '../board/qa.js';

const BOARD = new URL('../board/', import.meta.url);
const read = (name) => readFileSync(fileURLToPath(new URL(name, BOARD)), 'utf8');

/** One /state answer: four rows under two headings, `marks` by row number. @complexity O(1) @alloc one object */
function view(marks = {}, live = true) {
  const items = [['Cart', 'Add a mug to the cart'], ['Cart', 'Remove it again'], ['Pay', 'Pay with the test card'],
    ['Pay', 'See the receipt page']];
  const rows = items.map(([heading, item], i) => ({
    row: i + 1, heading, item, state: marks[i + 1]?.[0] ?? null, note: marks[i + 1]?.[1] ?? '',
  }));
  const counts = { pass: 0, fail: 0, skip: 0, unmarked: 0, rows: rows.length };
  rows.forEach((r) => { if (r.state) counts[r.state] += 1; else counts.unmarked += 1; });
  return {
    v: 1, run: '20261018-090000-1a2b', to: 'a', live, checklist: 'checklist.md', rows, counts,
    words: live ? 'This run is live; marks are saved as you make them' : ENDED_WORDS,
  };
}

/**
 * A fake element: the few DOM members qa.js's builder uses, and nothing
 * more, so a use of anything else (innerHTML among them) fails here.
 * @complexity O(1) per call  @alloc one object per element
 */
class FakeElement {
  constructor(doc, tag) {
    this.ownerDocument = doc;
    this.tagName = tag.toUpperCase();
    this.children = [];
    this.attrs = {};
    this.dataset = {};
    this.listeners = {};
    this.text = '';
    this.value = '';
    this.hidden = false;
    this.disabled = false;
    this.className = '';
    this.parent = null;
  }

  get textContent() { return this.text + this.children.map((c) => c.textContent).join(''); }

  set textContent(value) { this.children = []; this.text = String(value); }

  appendChild(child) { child.parent = this; this.children.push(child); return child; }

  replaceChildren(...kids) { this.children = []; this.text = ''; kids.forEach((k) => this.appendChild(k)); }

  setAttribute(name, value) { this.attrs[name] = String(value); }

  getAttribute(name) { return name in this.attrs ? this.attrs[name] : null; }

  removeAttribute(name) { delete this.attrs[name]; }

  addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }

  removeEventListener(type, fn) { this.listeners[type] = (this.listeners[type] || []).filter((f) => f !== fn); }

  focus() { this.ownerDocument.activeElement = this; }

  contains(other) { for (let n = other; n; n = n.parent) if (n === this) return true; return false; }

  closest(selector) {
    for (let n = this; n; n = n.parent) if (n.className.split(' ').includes(selector.replace('.', ''))) return n;
    return null;
  }

  dispatch(type, extra = {}) {
    const event = { type, target: this, key: '', preventDefault() { this.prevented = true; }, ...extra };
    (this.listeners[type] || []).forEach((fn) => fn(event));
    return event;
  }

  /** Every element under this one, this one first. @complexity O(n) @alloc one array */
  all() { return [this, ...this.children.flatMap((c) => c.all())]; }
}

/** A fake document: createElement, a body, an activeElement and listeners. @complexity O(1) @alloc one object */
class FakeDocument {
  constructor() {
    this.listeners = {};
    this.body = new FakeElement(this, 'body');
    this.activeElement = this.body;
  }

  createElement(tag) { return new FakeElement(this, tag); }

  addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }

  removeEventListener(type, fn) { this.listeners[type] = (this.listeners[type] || []).filter((f) => f !== fn); }

  key(key, extra = {}) {
    const event = { type: 'keydown', key, target: this.activeElement, preventDefault() { this.prevented = true; }, ...extra };
    (this.listeners.keydown || []).forEach((fn) => fn(event));
    return event;
  }
}

/** Build a page on a fake document with a stand-in for its requests; every mark posted is kept. @complexity O(rows) @alloc one page */
function page(initial = view(), answer = null) {
  const doc = new FakeDocument();
  const sent = [];
  const api = {
    async mark(body) {
      sent.push(body);
      if (answer) return answer(body);
      const marks = Object.fromEntries(initial.rows.filter((r) => r.state).map((r) => [r.row, [r.state, r.note]]));
      marks[body.row] = [body.state, body.note];
      return { status: 200, answer: { ok: true, state: view(marks) } };
    },
    async finish() { sent.push({ finish: true }); return { status: 200, answer: { ok: true, ending: true } }; },
  };
  const qa = createPage(doc, doc.body, { api, timers: { setTimeout: () => 0, clearTimeout: () => {} } });
  qa.render(initial);
  return { doc, qa, sent };
}

const settle = () => new Promise((resolve) => setImmediate(resolve));
const rowsOf = (doc) => doc.body.all().filter((e) => e.className.split(' ').includes('row'));
/** The page's rows, asserted to be the fixture's four first. @complexity O(n) @alloc one array */
const fourRows = (doc) => { const rows = rowsOf(doc); assert.equal(rows.length, 4, 'the page draws four rows'); return rows; };
const textOf = (doc) => doc.body.textContent;

test('the keys P, F, S, N and J are listed in words and map to their actions; typing in the note is left alone', () => {
  assert.deepEqual(KEY_HELP.map(([key]) => key), ['P', 'F', 'S', 'N or J']);
  for (const [key, words] of KEY_HELP) assert.ok(words.length > 10, `${key} has words`);
  assert.deepEqual(keyAction({ key: 'p' }), { kind: 'mark', state: 'pass' });
  assert.deepEqual(keyAction({ key: 'F' }), { kind: 'mark', state: 'fail' });
  assert.deepEqual(keyAction({ key: 's' }), { kind: 'mark', state: 'skip' });
  assert.deepEqual(keyAction({ key: 'n' }), { kind: 'next' });
  assert.deepEqual(keyAction({ key: 'J' }), { kind: 'next' });
  assert.equal(keyAction({ key: 'x' }), null);
  assert.equal(keyAction({ key: 'p', ctrlKey: true }), null);
  assert.equal(keyAction({ key: 'p', inField: true }), null);
  const { doc } = page();
  for (const [key, words] of KEY_HELP) {
    assert.ok(textOf(doc).includes(key) && textOf(doc).includes(words), `the page lists ${key}`);
  }
});

test('each mark is a glyph and a word, never a color alone', () => {
  assert.deepEqual(Object.fromEntries(Object.entries(MARKS).map(([s, m]) => [s, `${m.glyph} ${m.word}`])),
    { pass: '✓ Pass', fail: '✗ Fail', skip: '○ Skip' });
  const { doc } = page(view({ 1: ['pass', ''], 3: ['fail', 'it hung'] }));
  const rows = rowsOf(doc);
  assert.ok(rows[0].textContent.includes('Marked: ✓ Pass'));
  assert.ok(rows[1].textContent.includes('Not marked yet'));
  assert.ok(rows[2].textContent.includes('Marked: ✗ Fail'));
  const chosen = rows[0].all().filter((e) => e.getAttribute('aria-pressed') === 'true');
  assert.equal(chosen.length, 1);
  assert.equal(chosen[0].textContent, '✓ Pass');
});

test('the run\'s state is said in words: live, ended, no answer, no token', () => {
  assert.equal(ENDED_WORDS, 'This run has ended; marks are no longer saved');
  for (const key of ['live', 'ended', 'lost', 'noToken']) assert.ok(STATE_WORDS[key].text.length > 10, key);
  const { doc, qa } = page();
  assert.ok(textOf(doc).includes(STATE_WORDS.live.text));
  qa.render(view({}, false));
  assert.ok(textOf(doc).includes(ENDED_WORDS));
  qa.lost();
  assert.ok(textOf(doc).includes(ENDED_WORDS), 'an ended run stays ended when its server goes');
  const fresh = page();
  fresh.qa.lost();
  assert.ok(textOf(fresh.doc).includes(STATE_WORDS.lost.text));
});

test('the counts say how many rows are done and how many failed', () => {
  assert.equal(countWords({ pass: 1, fail: 1, skip: 0, unmarked: 2, rows: 4 }), '2 of 4 rows done · 1 failed');
  assert.equal(countWords({ pass: 0, fail: 0, skip: 0, unmarked: 0, rows: 0 }), 'No checklist rows in this run');
});

test('a fail needs a note, and a mark is pass, fail or skip on a row', () => {
  assert.deepEqual(markRequest(3, 'fail', '  '), { ok: false, error: 'A fail needs a note: say what went wrong' });
  assert.deepEqual(markRequest(3, 'fail', 'it hung'), { ok: true, body: { row: 3, state: 'fail', note: 'it hung' } });
  assert.deepEqual(markRequest(1, 'pass', ''), { ok: true, body: { row: 1, state: 'pass', note: '' } });
  assert.equal(markRequest(1, 'maybe', '').ok, false);
});

test('N and J go to the next unmarked row, wrapping, and say so when every row is marked', () => {
  const rows = view({ 2: ['pass', ''], 3: ['skip', ''] }).rows;
  assert.equal(nextUnmarked(rows, 0), 3);
  assert.equal(nextUnmarked(rows, 3), 0);
  assert.equal(nextUnmarked(view({ 1: ['pass', ''], 2: ['pass', ''], 3: ['pass', ''], 4: ['pass', ''] }).rows, 0), -1);
  const { doc } = page(view({ 2: ['pass', ''] }));
  const rows2 = rowsOf(doc);
  rows2[0].focus();
  doc.key('n');
  assert.equal(doc.activeElement, rows2[2]);
  doc.key('j');
  assert.equal(doc.activeElement, rows2[3]);
});

test('P marks the focused row; F with no note moves focus into the note and says a note is needed; Enter there sends the fail', async () => {
  const { doc, sent } = page();
  const rows = fourRows(doc);
  rows[0].focus();
  doc.key('p');
  await settle();
  assert.deepEqual(sent, [{ row: 1, state: 'pass', note: '' }]);
  assert.ok(rowsOf(doc)[0].textContent.includes('Marked: ✓ Pass'));
  rowsOf(doc)[2].focus();
  doc.key('f');
  await settle();
  assert.equal(sent.length, 1, 'no fail is sent without a note');
  const note = rowsOf(doc)[2].all().find((e) => e.tagName === 'TEXTAREA');
  assert.equal(doc.activeElement, note);
  assert.ok(rowsOf(doc)[2].textContent.includes('A fail needs a note'));
  assert.equal(note.getAttribute('aria-required'), 'true');
  note.value = 'the receipt page hung';
  note.dispatch('keydown', { key: 'Enter' });
  await settle();
  assert.deepEqual(sent[1], { row: 3, state: 'fail', note: 'the receipt page hung' });
  assert.ok(rowsOf(doc)[2].textContent.includes('Marked: ✗ Fail'));
});

test('a mark after the end is refused visibly, on the page and when the server says 409', async () => {
  const ended = page(view({}, false));
  fourRows(ended.doc)[0].focus();
  ended.doc.key('p');
  await settle();
  assert.deepEqual(ended.sent, [], 'an ended page sends nothing');
  assert.ok(rowsOf(ended.doc)[0].textContent.includes(`Not saved: ${ENDED_WORDS}`));
  assert.ok(rowsOf(ended.doc)[0].textContent.includes('Not marked yet'));
  const late = page(view(), () => ({ status: 409, answer: { ok: false, error: ENDED_WORDS } }));
  rowsOf(late.doc)[1].focus();
  late.doc.key('s');
  await settle();
  assert.equal(late.sent.length, 1);
  assert.ok(rowsOf(late.doc)[1].textContent.includes(`Not saved: ${ENDED_WORDS}`));
  assert.ok(textOf(late.doc).includes(ENDED_WORDS));
});

test('the page and its script hold no innerHTML, no inline handler and no other host', () => {
  for (const name of ['qa.html', 'qa.js']) {
    const text = read(name);
    for (const banned of ['innerHTML', 'outerHTML', 'insertAdjacentHTML', 'document.write', 'eval(']) {
      assert.ok(!text.includes(banned), `${name} holds ${banned}`);
    }
    assert.ok(!/\son[a-z]+=/i.test(text), `${name} holds an inline handler`);
    assert.ok(!/https?:\/\//.test(text.replace(/http:\/\/www\.w3\.org\/2000\/svg/g, '')), `${name} names a host`);
  }
  assert.ok(read('qa.html').includes('<script type="module" src="qa.js"></script>'));
});

test('the page is one column at 390 px with 44 px buttons and no sideways scroll', () => {
  const html = read('qa.html');
  assert.ok(/--tap:\s*44px/.test(html), 'a 44 px tap size token');
  assert.ok(/min-height:\s*var\(--tap\)/.test(html) && /min-width:\s*var\(--tap\)/.test(html));
  assert.ok(/overflow-wrap:\s*anywhere/.test(html), 'long words wrap');
  assert.ok(/overflow-x:\s*hidden/.test(html) || /max-width:\s*100%/.test(html));
  assert.ok(html.includes('@media (prefers-color-scheme: dark)'));
  assert.ok(html.includes(':root[data-theme="dark"]') && html.includes(':root[data-theme="light"]'));
  assert.ok(html.includes('prefers-reduced-motion'));
});
