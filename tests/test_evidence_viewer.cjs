/* Apache-2.0. Dependency-free presentation tests; every generated row is synthetic. */
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { File } = require('node:buffer');
const { createHash } = require('node:crypto');
const viewer = require('../docs/evidence-viewer/viewer.js');
const encoder = new TextEncoder();
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const encode = value => encoder.encode(JSON.stringify(value));
const clone = value => JSON.parse(JSON.stringify(value));
const tick = () => new Promise(resolve => setImmediate(resolve));

// Presentation-shape fixture only. This is not a Python-verifier acceptance
// fixture, a hosted result, original evidence, or a reconstruction of a run.
function records() {
  const data = Object.fromEntries(viewer.NAMES.map(name => [name, { schema_version: viewer.SCHEMAS[name] }]));
  const jobs = Array.from({ length: 200 }, (_, i) => ({ job_id: `batch-${String(i).padStart(3, '0')}`, cohort: i % 2 ? 'b' : 'a' }));
  const events = [];
  for (const [index, job] of jobs.entries()) {
    ['activity_enter', 'handler_enter', 'handler_return', 'activity_exit'].forEach((event, offset) => {
      events.push({ sequence: events.length + 1, elapsed_us: index * 10 + [0, 4, 4, 8][offset], event, job_id: job.job_id });
    });
  }
  Object.assign(data['batch-trace.json'], { evidence_kind: 'FABRICATED_UNIT_DATA', plan: { jobs }, events });
  data['batch-metadata.json'].rows = jobs.map(job => ({ job_id: job.job_id, attempt: 1 }));
  data['batch-histories.json'].rows = jobs.map(job => ({ job_id: job.job_id }));
  data['batch-outcomes.json'].rows = jobs.map(job => ({ terminal: { job_id: job.job_id, tool_status: 'COMPLETED', semantic_valid: false, output: 199 } }));
  data['batch-summary.json'].summary = { evidence_kind: 'FABRICATED_UNIT_DATA', observed_activity_peak: 2,
    observed_handler_peak: 1, activity_overlap: 'DEMONSTRATED', handler_overlap: 'NOT_DEMONSTRATED', outstanding: null };
  data['batch-summary.json'].independent_original_replay = 'NOT_EVALUATED';
  Object.assign(data['manifest.json'], { evidence_kind: 'FABRICATED_UNIT_DATA', projection_kind: 'PUBLIC_PROJECTION',
    provenance: 'RECORDED_HOSTED_ASSERTIONS_NOT_INDEPENDENT_PROOF', retention_days: 30, revision: 'a'.repeat(40),
    run_attempt: 1, workflow_path: '.github/workflows/temporal-server.yml', workflow_sha256: 'b'.repeat(64),
    workflow_run_url: 'https://github.com/synthetic/fixture/actions/runs/123', files: {} });
  return data;
}
function bundle(data = records(), overrides = {}) {
  const encoded = {};
  for (const name of viewer.NAMES.filter(name => name !== 'manifest.json')) encoded[name] = overrides[name] || encode(data[name]);
  data['manifest.json'].files = Object.fromEntries(Object.entries(encoded).map(([name, bytes]) => [name, { bytes: bytes.length, sha256: hash(bytes) }]));
  encoded['manifest.json'] = overrides['manifest.json'] || encode(data['manifest.json']);
  return viewer.NAMES.map(name => new File([encoded[name]], name));
}
async function rejects(files, code) { await assert.rejects(viewer.inspect(files), error => error.code === code); }

class Element {
  constructor(tag, document) { this.tagName = tag; this.ownerDocument = document; this.children = []; this.dataset = {}; this.listeners = {}; this.attributes = {}; this.hidden = false; this.value = ''; this._text = ''; }
  set textContent(value) { this._text = String(value); this.children = []; }
  get textContent() { return this._text + this.children.map(child => child.textContent).join(' '); }
  append(...children) { for (const child of children) this.children.push(...(child.tagName === '#fragment' ? child.children : [child])); }
  replaceChildren(...children) { this.children = []; this._text = ''; this.append(...children); }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  setAttribute(name, value) { this.attributes[name] = value; }
  querySelectorAll(selector) { assert.equal(selector, 'button'); return this.children.flatMap(child => [...(child.tagName === 'button' ? [child] : []), ...child.querySelectorAll(selector)]); }
  focus() { this.ownerDocument.activeElement = this; }
  fire(name, target = this) { this.listeners[name]({ target }); }
}
function documentStub() {
  const document = { nodes: {}, activeElement: null,
    createElement(tag) { return new Element(tag, this); },
    createDocumentFragment() { return new Element('#fragment', this); },
    getElementById(id) { return this.nodes[id] ||= new Element('div', this); } };
  return document;
}

test('frozen file limits and schemas remain exact and separate from Python tests', () => {
  assert.equal(viewer.NAMES.length, 8); assert.equal(viewer.TOTAL, 10 * 1024 * 1024);
  assert.equal(viewer.LIMITS['batch-trace.json'], 5 * 1024 * 1024);
  assert.equal(viewer.LIMITS['batch-histories.json'], 4 * 1024 * 1024);
  assert.equal(viewer.SCHEMAS['manifest.json'], 'opendot.temporal.real-batch.public-bundle.v1');
});
test('200 synthetic jobs and all seven exact hashes are presented, without semantic verdict', async () => {
  const model = await viewer.inspect(bundle());
  assert.equal(model.jobs.length, 200); assert.equal(model.checks.length, 7);
  assert.equal(model.synthetic, true); assert.equal(model.demo, false);
  assert.equal(model.jobs[0].outcome.semantic_valid, false);
  assert.equal(model.summary.delivery_admission_acceptance, undefined);
  assert.equal(model.jobs[0].activity, 8); assert.equal(model.jobs[0].handler, 0);
});
test('real evidence-kind label supported only as supplied assertions', async () => {
  const data = records();
  ['manifest.json', 'batch-trace.json'].forEach(name => { data[name].evidence_kind = 'HOSTED_REAL_SERVICE'; });
  data['batch-summary.json'].summary.evidence_kind = 'HOSTED_REAL_SERVICE';
  const model = await viewer.inspect(bundle(data)); assert.equal(model.synthetic, false);
  assert.equal(model.replay, 'NOT_EVALUATED');
});
test('missing, null, zero, false and unsupported display distinctly', () => {
  assert.equal(viewer.number(undefined), 'Missing'); assert.equal(viewer.number(null), 'Not recorded (null)');
  assert.equal(viewer.number(0), '0'); assert.equal(viewer.boolean(false), 'false');
  assert.equal(viewer.number('0'), 'Unsupported'); assert.equal(viewer.number(-1), 'Unsupported');
  assert.equal(viewer.choice('<img src=x>', ['PASS']), 'Unsupported');
});
test('equal timestamps retain explicit sequence, not event-name sorting', async () => {
  const model = await viewer.inspect(bundle());
  assert.deepEqual(model.jobs[0].events.map(row => [row.sequence, row.elapsed_us]), [[1, 0], [2, 4], [3, 4], [4, 8]]);
});
test('missing or repeated interval endpoints never become zero', () => {
  assert.equal(viewer.duration([], 'start', 'end'), undefined);
  assert.equal(viewer.duration([{ event: 'start', sequence: 1, elapsed_us: 0 }], 'start', 'end'), undefined);
  assert.equal(viewer.duration([{ event: 'start', sequence: 1, elapsed_us: 0 }, { event: 'start', sequence: 2, elapsed_us: 0 }, { event: 'end', sequence: 3, elapsed_us: 0 }], 'start', 'end'), undefined);
});
test('selection rejects missing, extra, duplicate, path and ZIP names before read', () => {
  const files = bundle();
  for (const malformed of [[], files.slice(1), [...files, files[0]], files.map((file, i) => i === 1 ? files[0] : file), files.map((file, i) => i === 0 ? new File(['{}'], '../manifest.json') : file), files.map((file, i) => i === 0 ? new File(['{}'], 'bundle.zip') : file)]) {
    assert.throws(() => viewer.selection(malformed), error => error.code === 'FILES');
  }
});
test('pre-read limits refuse empty and per-file overflow; exact caps fit total ceiling', () => {
  const files = bundle().map(file => ({ name: file.name, size: file.size }));
  for (const size of [0, -1, Infinity, 16385]) assert.throws(() => viewer.selection(files.map((file, i) => i ? file : { ...file, size })), /bounded size/);
  assert.ok(Object.values(viewer.LIMITS).reduce((sum, limit) => sum + limit, 0) <= viewer.TOTAL);
  assert.equal(viewer.selection(files.map(file => ({ ...file, size: viewer.LIMITS[file.name] }))).size, 8);
});
test('reads are sequential and sliced to explicit per-file bounds', async () => {
  let active = 0, peak = 0; const calls = [];
  const files = bundle().map(file => ({ name: file.name, size: file.size, slice(start, end) {
    calls.push([file.name, start, end]); return { async arrayBuffer() {
      active++; peak = Math.max(peak, active); await tick(); const bytes = await file.arrayBuffer(); active--; return bytes;
    } };
  } }));
  await viewer.inspect(files); assert.equal(peak, 1); assert.equal(calls.length, 8);
  calls.forEach(([name, start, end]) => { assert.equal(start, 0); assert.equal(end, viewer.LIMITS[name] + 1); });
});
test('read size disagreement fails before digest or rendering', async () => {
  const files = bundle();
  await assert.rejects(viewer.inspect(files, { read: async () => new Uint8Array(1) }), error => error.code === 'SIZE');
});
test('changed bytes with unchanged length fail hash', async () => {
  const files = bundle(), index = files.findIndex(file => file.name === 'environment.json');
  const bytes = new Uint8Array(await files[index].arrayBuffer()); bytes[bytes.length - 2] ^= 1;
  files[index] = new File([bytes], 'environment.json'); await rejects(files, 'HASH');
});
test('manifest mismatched byte length fails without reading affected file', async () => {
  const files = bundle(), i = files.findIndex(file => file.name === 'manifest.json');
  const manifest = JSON.parse(await files[i].text()); manifest.files['environment.json'].bytes++;
  files[i] = new File([encode(manifest)], 'manifest.json'); await rejects(files, 'HASH');
});
test('manifest requires exact keys, names, hashes and provenance declarations', async () => {
  for (const mutation of [m => { m.extra = 'ignored?'; }, m => { m.files.unknown = { bytes: 1, sha256: 'a'.repeat(64) }; },
    m => { m.files['environment.json'].sha256 = 'A'.repeat(64); }, m => { m.projection_kind = 'AUTHENTIC'; },
    m => { m.run_attempt = 0; }, m => { m.retention_days = 31; }, m => { m.workflow_run_url = 'javascript:alert(1)'; },
    m => { m.workflow_path = 'other.yml'; }, m => { m.provenance = 'INDEPENDENT_PROOF'; }]) {
    const files = bundle(), i = files.findIndex(file => file.name === 'manifest.json');
    const manifest = JSON.parse(await files[i].text()); mutation(manifest); files[i] = new File([encode(manifest)], 'manifest.json');
    await rejects(files, 'SHAPE');
  }
});
test('strict JSON refuses malformed, duplicate, poison keys and trailing data', () => {
  for (const source of ['[]', '{', '{"x":1,}', '{"x":1,"x":2}', '{"__proto__":{}}', '{"constructor":0}', '{"x":{"prototype":0}}', '{} true', '{"x":NaN}', '{"x":Infinity}', '{"x":01}', '{"x":"\n"}']) {
    assert.throws(() => viewer.strictJSON(encoder.encode(source)), error => error.code === 'JSON');
  }
});
test('strict JSON bounded depth, strings, keys, numbers, arrays and object width', () => {
  const deep = '{"a":'.repeat(14) + '0' + '}'.repeat(14);
  const values = [deep, JSON.stringify({ x: 'x'.repeat(257) }), JSON.stringify({ ['k'.repeat(129)]: 0 }),
    JSON.stringify({ x: Array(4097).fill(0) }), JSON.stringify(Object.fromEntries(Array.from({ length: 65 }, (_, i) => [String(i), 0]))), '{"x":1e100}'];
  values.forEach(source => assert.throws(() => viewer.strictJSON(encoder.encode(source)), error => error.code === 'JSON'));
});
test('decimal precision cannot turn nonintegers or underflow into exact integer fields', () => {
  for (const token of ['1e-9999', '0.99999999999999999', '999999999999999.99', '1000000000000000.01', '-1e-9999']) {
    assert.throws(() => viewer.strictJSON(encoder.encode('{"value":' + token + '}')), error => error.code === 'JSON');
  }
  for (const token of ['1.25', '0.1', '2e-5', '1.0', '1e15', '0e9999']) {
    assert.equal(viewer.strictJSON(encoder.encode('{"value":' + token + '}')).value, Number(token));
  }
});
test('invalid UTF-8 fails with fixed message and no input reflection', () => {
  assert.throws(() => viewer.strictJSON(new Uint8Array([123, 34, 120, 34, 58, 34, 255, 34, 125])), error => error.code === 'JSON' && error.message === viewer.MESSAGES.JSON);
});
test('unknown schemas and conflicting synthetic labels fail closed', async () => {
  for (const mutation of [data => { data['batch-cleanup.json'].schema_version = 'future.v9'; },
    data => { data['batch-trace.json'].evidence_kind = 'HOSTED_REAL_SERVICE'; }]) {
    const data = records(); mutation(data); await rejects(bundle(data), 'SHAPE');
  }
});
test('plan count, job identity, table duplicates and event limits are bounded', async () => {
  for (const mutation of [data => { data['batch-trace.json'].plan.jobs.pop(); },
    data => { data['batch-trace.json'].plan.jobs[1].job_id = 'batch-000'; },
    data => { data['batch-metadata.json'].rows[1].job_id = 'batch-000'; },
    data => { data['batch-trace.json'].events = Array(4097).fill({}); }]) {
    const data = records(); mutation(data); await assert.rejects(viewer.inspect(bundle(data)), error => ['SHAPE', 'JSON'].includes(error.code));
  }
});
test('nonmonotonic or skipped sequences and unknown events refuse presentation', async () => {
  for (const mutation of [events => { events[1].sequence = 1; }, events => { events[1].sequence = 4; },
    events => { events[2].elapsed_us = 1; }, events => { events[2].event = 'untrusted<script>'; }]) {
    const data = records(); mutation(data['batch-trace.json'].events); await rejects(bundle(data), 'SHAPE');
  }
});
test('missing outcome rows stay missing without claiming delivery', async () => {
  const data = records(); data['batch-outcomes.json'].rows = [];
  const model = await viewer.inspect(bundle(data)); assert.equal(model.jobs.length, 200);
  assert.equal(model.jobs[0].outcome.tool_status, undefined);
});
test('a stale generation stops after its current bounded read', async () => {
  let current = true, calls = 0;
  await assert.rejects(viewer.inspect(bundle(), { current: () => current, read: async file => {
    calls++; current = false; return new Uint8Array(await file.arrayBuffer());
  } }), error => error.code === 'STALE');
  assert.equal(calls, 1);
});
test('replacement selections coalesce to latest, with one active chain', async () => {
  const notifications = [], pending = []; let calls = 0, active = 0, peak = 0;
  const control = viewer.controller(value => notifications.push(value), async (files, options) => {
    calls++; active++; peak = Math.max(peak, active);
    return new Promise(resolve => pending.push(() => { active--; resolve({ sequence: calls, current: options.current() }); }));
  });
  const files = bundle(); control.select(files);
  for (let i = 0; i < 30; i++) control.select(files);
  assert.equal(calls, 1); pending.shift()(); await tick(); assert.equal(calls, 2);
  pending.shift()(); await tick(); assert.equal(peak, 1);
  assert.equal(notifications.filter(state => state.type === 'loaded').length, 1);
  assert.equal(notifications.at(-1).model.current, true);
});
test('reset clears pending work and stale completion cannot repaint', async () => {
  const notifications = []; let finish, calls = 0;
  const control = viewer.controller(state => notifications.push(state), () => { calls++; return new Promise(resolve => { finish = resolve; }); });
  control.select(bundle()); control.select(bundle()); control.reset(); finish({ stale: true }); await tick();
  assert.equal(calls, 1); assert.equal(notifications.at(-1).type, 'empty');
  assert.equal(notifications.filter(state => state.type === 'loaded').length, 0);
});
test('demo invalidates read, stays tiny, synthetic, and does not claim hashing', async () => {
  const states = []; let finish;
  const control = viewer.controller(state => states.push(state), () => new Promise(resolve => { finish = resolve; }));
  control.select(bundle()); control.demo(); finish({ stale: true }); await tick();
  const model = states.at(-1).model;
  assert.equal(model.demo, true); assert.equal(model.synthetic, true); assert.equal(model.jobs.length, 3);
  assert.equal(model.checks.length, 0); assert.deepEqual(model.summary, {}); assert.equal(model.jobs[2].handler, undefined);
});
test('invalid new selection removes old result and reports fixed error', async () => {
  const states = []; const control = viewer.controller(state => states.push(state));
  control.demo(); control.select([]); assert.equal(states.at(-1).type, 'error');
  assert.equal(states.at(-1).message, viewer.MESSAGES.FILES);
});
test('DOM harness renders 200 rows and separate reported overlap values with text nodes', async () => {
  const doc = documentStub(), control = viewer.mount(doc); control.select(bundle());
  for (let i = 0; i < 100 && doc.getElementById('results').hidden; i++) await tick();
  // Rendering may await native SHA-256, so explicitly wait for its terminal state.
  while (doc.getElementById('status').textContent.startsWith('Reading')) await tick();
  assert.equal(doc.getElementById('jobs').children.length, 200);
  assert.match(doc.getElementById('metrics').textContent, /Activity overlap DEMONSTRATED Reported peak: 2/);
  assert.match(doc.getElementById('metrics').textContent, /Handler overlap NOT_DEMONSTRATED Reported peak: 1/);
  assert.match(doc.getElementById('trust').textContent, /FABRICATED UNIT DATA/);
  assert.equal(doc.getElementById('checks').children.length, 7);
  assert.match(doc.getElementById('metrics').textContent, /Not recorded \(null\)/);
});
test('DOM demo, cohort filter, button focus, reset and error states remain usable', () => {
  const doc = documentStub(), control = viewer.mount(doc); control.demo();
  assert.match(doc.getElementById('jobs-title').textContent, /3-job synthetic/);
  assert.match(doc.getElementById('trust').textContent, /No files were selected, hashed, or verified/);
  doc.getElementById('cohort').value = 'b'; doc.getElementById('cohort').fire('change');
  assert.equal(doc.getElementById('jobs').children.length, 1);
  doc.getElementById('jobs').querySelectorAll('button')[0].fire('click');
  assert.equal(doc.activeElement, doc.getElementById('detail-title'));
  control.reset(); assert.equal(doc.getElementById('results').hidden, true);
  assert.equal(doc.getElementById('events').children.length, 0);
  assert.equal(doc.getElementById('context').children.length, 0);
  control.select([]); assert.equal(doc.getElementById('status').className, 'status error');
});
test('unsupported supplied text cannot create executable nodes or links', async () => {
  const data = records(); data['batch-outcomes.json'].rows[0].terminal.tool_status = '<script>alert(1)</script>';
  data['batch-metadata.json'].rows[0].workflow_id = 'javascript:alert(1)';
  const doc = documentStub(), control = viewer.mount(doc); control.select(bundle(data));
  while (doc.getElementById('status').textContent.startsWith('Reading')) await tick();
  assert.doesNotMatch(doc.getElementById('jobs').textContent, /script/);
  assert.match(doc.getElementById('jobs').textContent, /Unsupported/);
  assert.doesNotMatch(doc.getElementById('detail').textContent, /javascript/);
});
test('source boundary: classic local resources, fixed CSP, no networking or persistence APIs', () => {
  const dir = path.join(__dirname, '../docs/evidence-viewer');
  const html = fs.readFileSync(path.join(dir, 'index.html'), 'utf8'), script = fs.readFileSync(path.join(dir, 'viewer.js'), 'utf8');
  assert.match(html, /default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'none'/);
  assert.match(html, /<script src="viewer.js" defer><\/script>/);
  assert.doesNotMatch(html, /<script[^>]*type="module"|https?:\/\/|\bon\w+=|<iframe|<form/);
  assert.doesNotMatch(script, /\b(?:fetch|XMLHttpRequest|WebSocket|localStorage|sessionStorage|indexedDB|serviceWorker|sendBeacon|eval|Function)\b|innerHTML|outerHTML|insertAdjacentHTML|createObjectURL/);
});
