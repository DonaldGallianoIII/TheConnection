/**
 * qa.js: the QA checklist page (C8, "The page"), served by tc qa run's
 * endpoint beside qa.html. It reads the token from the URL's fragment
 * (#token=...), asks /state for the run and its checklist every POLL_MS,
 * and sends each mark to /check with the token in the X-TC-Token header.
 *
 * Each row offers `✓ Pass`, `✗ Fail` and `○ Skip`; the chosen one is
 * filled with a heavy outline and the row says its mark in words. A note
 * box under each row is required on Fail. Keys, listed on the page: P, F
 * and S mark the focused row, N or J moves to the next unmarked row, and
 * Fail moves focus into the note. The page says the run's state in words,
 * and once the run has ended says `This run has ended; marks are no longer
 * saved` and refuses a mark visibly. Meaning never rides on color alone:
 * every state has a glyph and a word.
 *
 * Two layers. The pure layer (KEY_HELP, MARKS, STATE_WORDS, keyAction,
 * nextUnmarked, countWords, markRequest) reads only its arguments, so node
 * tests it with no DOM. The DOM layer (createPage) builds everything with
 * createElement and textContent through el(), which refuses an html
 * property: nothing on the page is parsed from markup, so text from the checklist or the run
 * is always text. start() wires the live page: the poller, the keys and
 * the Finish button; stop() releases them.
 *
 * Model: Claude Opus 5.5 (the QA lane agent), 2026-10-18. Status: unreviewed.
 *
 * @interacts  the pure layer: none. createPage: builds elements under the
 *             root it is given and listens for clicks and keys on them and
 *             one keydown on the document; asks through the api it is
 *             given. start(): reads the fragment and ?theme and ?gray from
 *             the URL, sets data-theme and a grayscale filter on <html>,
 *             fetches ./state and posts ./check (the page's own server, no
 *             other host); one poll timer, one AbortController and one
 *             Finish timer, all released by stop() on pagehide
 * @deps       browser DOM and fetch for start(); none for the pure layer
 * @complexity a render is O(r) over r rows (tens); a key or a click O(r)
 *             at most, for the next unmarked row
 * @alloc      one element tree per page: one row element per checklist
 *             row, kept from render to render and updated in place; the
 *             last /state answer; the timers above
 */

export const CONFIG = Object.freeze({
  // The run's state is asked for this often: a mark from another tab, or
  // the run's end, shows within two seconds, and a request costs the run
  // well under a millisecond.
  POLL_MS: 2000,
  // A /state answer takes milliseconds over loopback; one still out after
  // this is dropped and the page says it has no answer.
  FETCH_TIMEOUT_MS: 1500,
  // Finish asks twice: a second press within this long ends the run, so a
  // stray click never does.
  FINISH_CONFIRM_MS: 4000,
  TOKEN_HEADER: 'X-TC-Token',
});

// C8's words for an ended run, exactly as the endpoint sends them.
export const ENDED_WORDS = 'This run has ended; marks are no longer saved';
const FAIL_NOTE_WORDS = 'A fail needs a note: say what went wrong';
const STATE_MARK_WORDS = 'A mark is pass, fail or skip';

// Each mark: its glyph, its word and its key (C8).
export const MARKS = Object.freeze({
  pass: Object.freeze({ glyph: '✓', word: 'Pass', key: 'P' }),
  fail: Object.freeze({ glyph: '✗', word: 'Fail', key: 'F' }),
  skip: Object.freeze({ glyph: '○', word: 'Skip', key: 'S' }),
});
const MARK_ORDER = ['pass', 'fail', 'skip'];

// The keys, as the page lists them (C8: listed on the page).
export const KEY_HELP = Object.freeze([
  ['P', 'mark the focused row ✓ Pass'],
  ['F', 'mark it ✗ Fail: focus moves into its note, which a fail needs'],
  ['S', 'mark it ○ Skip'],
  ['N or J', 'go to the next row with no mark'],
]);
const NEXT_KEYS = ['n', 'j'];

// The run's state, a glyph and words each (C8: the run's state in words).
export const STATE_WORDS = Object.freeze({
  starting: Object.freeze({ glyph: '…', text: 'Asking the run for its checklist' }),
  live: Object.freeze({ glyph: '●', text: 'Live: marks are saved as you make them' }),
  ended: Object.freeze({ glyph: '■', text: ENDED_WORDS }),
  lost: Object.freeze({ glyph: '△', text: 'No answer from the run: it may have ended, and marks are not being saved' }),
  noToken: Object.freeze({ glyph: '△', text: 'No token in this page\'s address: open the exact URL tc qa run printed' }),
});

const NOT_MARKED = 'Not marked yet';
const NOT_SAVED = 'Not saved: ';
const NO_ANSWER = 'no answer from the run';
const ALL_MARKED = 'Every row has a mark.';
const FINISH_WORDS = 'Finish the run';
const FINISH_AGAIN = 'Press Finish again to end the run';
const FINISHING = 'Finishing: the run mails its summary and ends.';
const FINISHED = 'The run has ended and mailed its summary.';
const NOTE_LABEL = 'Note (needed for a fail)';
const NOTE_HINT = 'Write it, then press Enter or ✗ Fail again.';

/**
 * What a key does on the page: mark the focused row, or go to the next
 * unmarked one; null for any other key, a key with Ctrl, Alt or Meta, or a
 * key typed into a field (`inField`).
 * @complexity O(1)  @alloc one small object
 */
export function keyAction(event) {
  if (event.inField || event.ctrlKey || event.altKey || event.metaKey) return null;
  const key = String(event.key || '').toLowerCase();
  const state = MARK_ORDER.find((s) => MARKS[s].key.toLowerCase() === key);
  if (state) return { kind: 'mark', state };
  return NEXT_KEYS.includes(key) ? { kind: 'next' } : null;
}

/**
 * The index of the next row with no mark after `from`, wrapping round;
 * -1 when every row has one.
 * @complexity O(r) over r rows  @alloc none
 */
export function nextUnmarked(rows, from) {
  for (let step = 1; step <= rows.length; step += 1) {
    const at = (from + step) % rows.length;
    if (!rows[at].state) return at;
  }
  return -1;
}

/**
 * The counts in words: `2 of 4 rows done · 1 failed`.
 * @complexity O(1)  @alloc one string
 */
export function countWords(counts) {
  if (!counts.rows) return 'No checklist rows in this run';
  const done = counts.rows - counts.unmarked;
  return `${done} of ${counts.rows} rows done · ${counts.fail} failed`;
}

/**
 * A mark checked before it is sent: { ok, body } or { ok: false, error },
 * as the endpoint checks it (a fail needs a note).
 * @complexity O(n) over the note's length  @alloc one object
 */
export function markRequest(row, state, note) {
  if (!MARK_ORDER.includes(state)) return { ok: false, error: STATE_MARK_WORDS };
  const text = String(note || '').trim();
  if (state === 'fail' && !text) return { ok: false, error: FAIL_NOTE_WORDS };
  return { ok: true, body: { row, state, note: text } };
}

/**
 * One element: `tag` with props (class, text, attrs, dataset, on) and
 * children, string children as text nodes' text. An `html` prop throws:
 * this builder never parses markup.
 * @complexity O(p + c) over props and children  @alloc one element
 */
function el(doc, tag, props = {}, ...children) {
  if ('html' in props) throw new Error('el(): no html; text only');
  const node = doc.createElement(tag);
  if (props.class) node.className = props.class;
  if (props.text !== undefined) node.textContent = props.text;
  for (const [name, value] of Object.entries(props.attrs || {})) node.setAttribute(name, value);
  Object.assign(node.dataset, props.dataset || {});
  for (const [type, fn] of Object.entries(props.on || {})) node.addEventListener(type, fn);
  for (const child of children) {
    if (child === null || child === undefined) continue;
    node.appendChild(typeof child === 'string' ? el(doc, 'span', { text: child }) : child);
  }
  return node;
}

/**
 * The page, built under `root` on `doc`. `api.mark(body)` and
 * `api.finish()` answer { status, answer } (status 0 for no answer);
 * `timers` holds setTimeout and clearTimeout. Returns { render(view),
 * lost(), noToken(), destroy() }: render draws a /state answer, patching
 * the rows in place.
 * @complexity build O(1); render O(r)  @alloc see the module block
 */
export function createPage(doc, root, { api, timers }) {
  let current = null;
  let ended = false;
  let finishArmed = null;
  const rowParts = new Map();

  const stateLine = el(doc, 'p', { class: 'state', attrs: { role: 'status', 'aria-live': 'polite' } });
  const runLine = el(doc, 'p', { class: 'run' });
  const countLine = el(doc, 'p', { class: 'counts' });
  const keyList = el(doc, 'dl', { class: 'keys' });
  for (const [key, words] of KEY_HELP) {
    keyList.appendChild(el(doc, 'dt', {}, el(doc, 'kbd', { text: key })));
    keyList.appendChild(el(doc, 'dd', { text: words }));
  }
  const list = el(doc, 'div', { class: 'rows' });
  const finishWords = el(doc, 'p', { class: 'finish-words', attrs: { role: 'status' } });
  const finishButton = el(doc, 'button', { class: 'finish', text: FINISH_WORDS, attrs: { type: 'button' } });
  root.replaceChildren(
    el(doc, 'header', { class: 'top' }, el(doc, 'h1', { text: 'QA checklist' }), runLine, stateLine, countLine),
    el(doc, 'section', { class: 'help', attrs: { 'aria-label': 'Keys' } }, el(doc, 'h2', { text: 'Keys' }), keyList),
    el(doc, 'main', {}, list),
    el(doc, 'footer', { class: 'bottom' }, finishButton, finishWords),
  );

  /** The run's state line: a glyph and words. @complexity O(1) @alloc two spans */
  const sayState = (key) => {
    const { glyph, text } = STATE_WORDS[key];
    stateLine.replaceChildren(el(doc, 'span', { class: 'glyph', text: glyph, attrs: { 'aria-hidden': 'true' } }),
      el(doc, 'span', { text }));
    stateLine.dataset.state = key;
  };

  /** A row's message line: refusals and hints, in words. @complexity O(1) @alloc none */
  const sayRow = (row, words) => {
    const parts = rowParts.get(row);
    if (parts) parts.message.textContent = words;
  };

  /** Draw one row's mark: the chosen button pressed, its words, the note's need. @complexity O(1) @alloc none */
  const drawRow = (parts, data) => {
    parts.data = data;
    for (const state of MARK_ORDER) parts.buttons[state].setAttribute('aria-pressed', String(data.state === state));
    parts.node.dataset.state = data.state || 'none';
    parts.chosen.textContent = data.state ? `Marked: ${MARKS[data.state].glyph} ${MARKS[data.state].word}` : NOT_MARKED;
    const needed = data.state === 'fail' || parts.pendingFail;
    parts.note.setAttribute('aria-required', String(needed));
    if (data.note && doc.activeElement !== parts.note) parts.note.value = data.note;
  };

  /** Send one mark, unless the run has ended; draw the answer or the refusal. @complexity O(r) @alloc the request */
  const send = async (row, state) => {
    const parts = rowParts.get(row);
    if (ended) {
      sayRow(row, NOT_SAVED + ENDED_WORDS);
      return;
    }
    const checked = markRequest(row, state, parts.note.value);
    if (!checked.ok) {
      if (state === 'fail') {
        parts.pendingFail = true;
        drawRow(parts, parts.data);
        parts.note.focus();
        sayRow(row, `${checked.error}. ${NOTE_HINT}`);
      } else {
        sayRow(row, checked.error);
      }
      return;
    }
    const { status, answer } = await api.mark(checked.body);
    if (status === 200 && answer.ok) {
      parts.pendingFail = false;
      sayRow(row, '');
      render(answer.state);
      return;
    }
    if (status === 409) {
      render({ ...current, live: false });
    }
    sayRow(row, NOT_SAVED + (answer && answer.error ? answer.error : NO_ANSWER));
  };

  /** Build one row: its item, three buttons, its words, its note and its message line. @complexity O(1) @alloc one tree */
  const makeRow = (data) => {
    const parts = { pendingFail: false, data };
    parts.buttons = {};
    const group = el(doc, 'div', { class: 'marks', attrs: { role: 'group', 'aria-label': `Mark row ${data.row}` } });
    for (const state of MARK_ORDER) {
      const { glyph, word } = MARKS[state];
      parts.buttons[state] = el(doc, 'button', {
        class: `mark mark-${state}`, text: `${glyph} ${word}`, attrs: { type: 'button', 'aria-pressed': 'false' },
        on: { click: () => { send(data.row, state); } },
      });
      group.appendChild(parts.buttons[state]);
    }
    parts.chosen = el(doc, 'p', { class: 'chosen' });
    parts.note = el(doc, 'textarea', {
      class: 'note', attrs: { rows: '2', 'aria-label': `${NOTE_LABEL}, row ${data.row}`, maxlength: '1000' },
      on: {
        keydown: (event) => {
          if (event.key !== 'Enter' || event.shiftKey) return;
          event.preventDefault();
          const state = parts.pendingFail ? 'fail' : parts.data.state;
          if (state) send(data.row, state);
        },
      },
    });
    parts.message = el(doc, 'p', { class: 'message', attrs: { role: 'alert' } });
    parts.node = el(doc, 'div', { class: 'row', attrs: { tabindex: '0', 'aria-label': `Row ${data.row}: ${data.item}` },
      dataset: { row: String(data.row) } },
    el(doc, 'p', { class: 'item' }, el(doc, 'span', { class: 'number', text: `${data.row}.` }), ` ${data.item}`),
    group, parts.chosen,
    el(doc, 'label', { class: 'note-label' }, el(doc, 'span', { text: NOTE_LABEL }), parts.note),
    parts.message);
    rowParts.set(data.row, parts);
    return parts;
  };

  /** Draw a /state answer: the run line, the state, the counts, the rows (built once, then patched). @complexity O(r) @alloc new rows only */
  const render = (next) => {
    current = next;
    if (!next.live) ended = true;
    runLine.textContent = `Run ${next.run}, mailing ${next.to}${next.checklist ? `, checklist ${next.checklist}` : ''}.`;
    sayState(ended ? 'ended' : 'live');
    countLine.textContent = countWords(next.counts);
    if (rowParts.size !== next.rows.length) {
      rowParts.clear();
      const kids = [];
      let heading = null;
      for (const data of next.rows) {
        if (data.heading !== heading) {
          heading = data.heading;
          if (heading) kids.push(el(doc, 'h2', { class: 'heading', text: heading }));
        }
        kids.push(makeRow(data).node);
      }
      if (!next.rows.length) kids.push(el(doc, 'p', { class: 'empty', text: 'This run has no checklist. Notes and logs still reach the session.' }));
      list.replaceChildren(...kids);
    }
    for (const data of next.rows) drawRow(rowParts.get(data.row), data);
    finishButton.disabled = ended;
    if (ended && finishWords.textContent === FINISHING) finishWords.textContent = FINISHED;
  };

  /** The row the focus is in, or null. @complexity O(r) @alloc none */
  const focusedRow = () => {
    for (const parts of rowParts.values()) if (parts.node.contains(doc.activeElement)) return parts;
    return null;
  };

  /** The page's keys (C8): P, F, S on the focused row, N or J to the next unmarked row. @complexity O(r) @alloc none */
  const onKey = (event) => {
    const target = event.target || {};
    const inField = target.tagName === 'TEXTAREA' || target.tagName === 'INPUT';
    const action = keyAction({ ...event, key: event.key, inField });
    if (!action || !current) return;
    const parts = focusedRow();
    if (action.kind === 'mark') {
      if (!parts) return;
      event.preventDefault();
      send(parts.data.row, action.state);
      return;
    }
    event.preventDefault();
    const rows = current.rows;
    const from = parts ? rows.findIndex((r) => r.row === parts.data.row) : -1;
    const at = nextUnmarked(rows, from < 0 ? rows.length - 1 : from);
    if (at < 0) {
      countLine.textContent = `${countWords(current.counts)}. ${ALL_MARKED}`;
      return;
    }
    rowParts.get(rows[at].row).node.focus();
  };
  doc.addEventListener('keydown', onKey);

  /** Finish: the first press arms it, a second within FINISH_CONFIRM_MS ends the run. @complexity O(1) @alloc one timer */
  const onFinish = async () => {
    if (ended) {
      finishWords.textContent = ENDED_WORDS;
      return;
    }
    if (finishArmed === null) {
      finishButton.textContent = FINISH_AGAIN;
      finishArmed = timers.setTimeout(() => {
        finishArmed = null;
        finishButton.textContent = FINISH_WORDS;
      }, CONFIG.FINISH_CONFIRM_MS);
      return;
    }
    timers.clearTimeout(finishArmed);
    finishArmed = null;
    finishButton.textContent = FINISH_WORDS;
    const { status, answer } = await api.finish();
    finishWords.textContent = status === 200 && answer.ok ? FINISHING : NOT_SAVED + ((answer && answer.error) || NO_ANSWER);
  };
  finishButton.addEventListener('click', onFinish);

  sayState('starting');
  return {
    render,
    /** The run gave no answer: an ended run stays ended, a live one is lost. @complexity O(1) @alloc none */
    lost() { sayState(ended ? 'ended' : 'lost'); },
    /** The page's address holds no token. @complexity O(1) @alloc none */
    noToken() { sayState('noToken'); },
    /** Release the page's listeners and its Finish timer. @complexity O(1) @alloc none */
    destroy() {
      doc.removeEventListener('keydown', onKey);
      finishButton.removeEventListener('click', onFinish);
      if (finishArmed !== null) timers.clearTimeout(finishArmed);
      finishArmed = null;
    },
    /** True once the page knows the run has ended. @complexity O(1) @alloc none */
    get ended() { return ended; },
  };
}

/**
 * The live page: read the token, draw the page under #app, poll /state,
 * send marks and Finish to /check. Returns stop(), which releases the
 * timers, the request in flight and the listeners.
 * @complexity one poll O(r)  @alloc the page, one timer and one AbortController at a time
 */
export function start(win) {
  const doc = win.document;
  const query = new URLSearchParams(win.location.search);
  const theme = query.get('theme');
  if (theme === 'dark' || theme === 'light') doc.documentElement.setAttribute('data-theme', theme);
  if (query.get('gray') === '1') doc.documentElement.style.filter = 'grayscale(1)';
  const token = new URLSearchParams(win.location.hash.slice(1)).get('token') || '';
  const timers = { setTimeout: (fn, ms) => win.setTimeout(fn, ms), clearTimeout: (id) => win.clearTimeout(id) };
  let inFlight = null;
  let pollTimer = null;
  let stopped = false;

  /** One request to the page's own server, with the token; { status, answer }, status 0 for no answer. @complexity O(1) @alloc one AbortController */
  const ask = async (path, body) => {
    const control = new win.AbortController();
    inFlight = control;
    const giveUp = win.setTimeout(() => control.abort(), CONFIG.FETCH_TIMEOUT_MS);
    try {
      const response = await win.fetch(path, {
        method: body ? 'POST' : 'GET', cache: 'no-store', signal: control.signal,
        headers: { [CONFIG.TOKEN_HEADER]: token, ...(body ? { 'Content-Type': 'application/json' } : {}) },
        body: body ? JSON.stringify(body) : undefined,
      });
      let answer = {};
      try { answer = await response.json(); } catch { answer = {}; }
      return { status: response.status, answer };
    } catch {
      return { status: 0, answer: {} };
    } finally {
      win.clearTimeout(giveUp);
      if (inFlight === control) inFlight = null;
    }
  };

  const page = createPage(doc, doc.getElementById('app'), {
    api: { mark: (body) => ask('check', body), finish: () => ask('check', { finish: true }) },
    timers,
  });

  /** Ask /state, draw it, and ask again POLL_MS later unless the run has ended. @complexity O(r) @alloc one request */
  const poll = async () => {
    pollTimer = null;
    const { status, answer } = await ask('state');
    if (stopped) return;
    if (status === 200) page.render(answer);
    else page.lost();
    if (!page.ended) pollTimer = win.setTimeout(poll, CONFIG.POLL_MS);
  };

  if (!/^[A-Za-z0-9_-]+$/.test(token)) {
    page.noToken();
  } else {
    poll();
  }
  return function stop() {
    stopped = true;
    if (pollTimer !== null) win.clearTimeout(pollTimer);
    pollTimer = null;
    if (inFlight) inFlight.abort();
    page.destroy();
  };
}

// The page boots itself: qa.html loads this module with no inline script
// (its policy allows none). In node, which has no window, nothing runs.
if (typeof window !== 'undefined' && window.document && window.document.getElementById('app')) {
  let stopPage = start(window);
  window.addEventListener('pagehide', () => {
    if (stopPage) stopPage();
    stopPage = null;
  });
  window.addEventListener('pageshow', (event) => {
    if (event.persisted && !stopPage) stopPage = start(window);
  });
}
