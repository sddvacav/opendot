/* OpenDot Engineering; Apache-2.0. Local presentation, never an evidence authority. */
(function (root) {
  'use strict';
  const PREFIX = 'opendot.temporal.real-batch.';
  const LIMITS = Object.freeze({
    'manifest.json': 16384, 'environment.json': 65536,
    'batch-trace.json': 5242880, 'batch-metadata.json': 262144,
    'batch-histories.json': 4194304, 'batch-outcomes.json': 262144,
    'batch-cleanup.json': 65536, 'batch-summary.json': 65536
  });
  const NAMES = Object.freeze(Object.keys(LIMITS));
  const TOTAL = 10485760;
  const SCHEMAS = Object.freeze({
    'manifest.json': PREFIX + 'public-bundle.v1',
    'environment.json': 'opendot.temporal.server-gate.environment.v1',
    'batch-trace.json': PREFIX + 'trace.v1',
    'batch-metadata.json': PREFIX + 'metadata.v1',
    'batch-histories.json': PREFIX + 'history.v1',
    'batch-outcomes.json': PREFIX + 'outcomes.v1',
    'batch-cleanup.json': PREFIX + 'cleanup.v1',
    'batch-summary.json': PREFIX + 'public-summary.v1'
  });
  const EVENTS = new Set(['reservation', 'rpc_enter', 'acknowledgment', 'activity_enter',
    'execute_enter', 'handler_enter', 'handler_return', 'execute_return', 'activity_exit',
    'workflow_result', 'validated_terminal', 'handler_error', 'execute_error',
    'activity_error', 'uncertainty']);
  const MESSAGES = Object.freeze({
    FILES: 'Select exactly the eight fixed public JSON filenames, once each.',
    SIZE: 'A file or the total selection exceeds the bounded size, or is empty.',
    JSON: 'A selected file is not supported strict, bounded UTF-8 JSON.',
    SHAPE: 'The selected bundle has an unsupported presentation shape.',
    HASH: 'Selected bytes do not match the supplied manifest. No bundle data is shown.',
    CRYPTO: 'SHA-256 is unavailable in this browser. Use a supported local browser; do not weaken its security settings.',
    READ: 'A local file could not be read. Select the complete bundle again.',
    STALE: 'Selection was replaced or reset.'
  });
  function fail(code) { const error = new Error(MESSAGES[code]); error.code = code; throw error; }
  function need(condition, code = 'SHAPE') { if (!condition) fail(code); }
  function object(value) { return value !== null && typeof value === 'object' && !Array.isArray(value); }
  function exactKeys(value, keys) {
    need(object(value));
    const actual = Object.keys(value).sort();
    need(actual.length === keys.length && actual.every((key, index) => key === [...keys].sort()[index]));
  }
  function integer(value, min = 0, max = 1e15) { return Number.isSafeInteger(value) && value >= min && value <= max; }
  function missing(value) { return value === undefined ? 'Missing' : value === null ? 'Not recorded (null)' : null; }
  function number(value) { return missing(value) || (integer(value) ? String(value) : 'Unsupported'); }
  function boolean(value) { return missing(value) || (typeof value === 'boolean' ? String(value) : 'Unsupported'); }
  function choice(value, options) { return missing(value) || (options.includes(value) ? value : 'Unsupported'); }
  function matches(value, pattern) { return typeof value === 'string' && pattern.exec(value)?.[0] === value; }
  function identifier(value, pattern) { return missing(value) || (matches(value, pattern) ? value : 'Unsupported'); }
  const HASH = /^[a-f0-9]{64}$/;
  const JOB = /^batch-(?:0[0-9]{2}|1[0-9]{2})$/;
  const RUN = /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/;
  const REVISION = /^[a-f0-9]{40}$/;
  const URL = /^https:\/\/github\.com\/[A-Za-z0-9_.-]{1,100}\/[A-Za-z0-9_.-]{1,100}\/actions\/runs\/[1-9][0-9]{0,19}$/;

  // Reject duplicate/poison keys, excessive nesting, values and arrays before
  // constructing a full object. This is a presentation parser, not Python's verifier.
  function strictJSON(bytes) {
    let source;
    try { source = new TextDecoder('utf-8', { fatal: true }).decode(bytes); } catch (_) { fail('JSON'); }
    let at = 0, nodes = 0;
    function space() { while (at < source.length && /[ \t\r\n]/.test(source[at])) at++; }
    function string() {
      const start = at++;
      while (at < source.length) {
        const character = source[at++];
        if (character === '"') {
          let result;
          try { result = JSON.parse(source.slice(start, at)); } catch (_) { fail('JSON'); }
          need(result.length <= 256, 'JSON');
          return result;
        }
        if (character === '\\') at++;
        need(at - start <= 1540, 'JSON');
      }
      fail('JSON');
    }
    function value(depth) {
      need(++nodes <= 300000 && depth <= 12, 'JSON');
      space();
      const character = source[at];
      if (character === '"') return string();
      if (character === '{') {
        at++; space(); const result = Object.create(null); let count = 0;
        if (source[at] === '}') { at++; return result; }
        while (true) {
          need(source[at] === '"' && ++count <= 64, 'JSON');
          const key = string();
          need(key.length <= 128 && !['__proto__', 'prototype', 'constructor'].includes(key)
            && !Object.hasOwn(result, key), 'JSON');
          space(); need(source[at++] === ':', 'JSON'); result[key] = value(depth + 1); space();
          const end = source[at++];
          if (end === '}') return result;
          need(end === ',', 'JSON'); space();
        }
      }
      if (character === '[') {
        at++; space(); const result = [];
        if (source[at] === ']') { at++; return result; }
        while (true) {
          need(result.length < 4096, 'JSON'); result.push(value(depth + 1)); space();
          const end = source[at++];
          if (end === ']') return result;
          need(end === ',', 'JSON');
        }
      }
      for (const [token, result] of [['true', true], ['false', false], ['null', null]]) {
        if (source.startsWith(token, at)) { at += token.length; return result; }
      }
      const matched = /^(?:-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?)/.exec(source.slice(at, at + 64));
      need(matched, 'JSON'); at += matched[0].length;
      const token = matched[0], result = Number(token);
      need(Number.isFinite(result) && Math.abs(result) <= 1e15, 'JSON');
      // Fractional auxiliary fields are allowed, but decimal underflow or a
      // fraction rounded into an integer must not masquerade as an exact time,
      // count, byte length, or zero. Compare the original bounded decimal.
      const parts = /^-?([0-9]+)(?:\.([0-9]+))?(?:[eE]([+-]?[0-9]+))?$/.exec(token);
      const fraction = parts[2] || '', digits = BigInt(parts[1] + fraction);
      if (digits !== 0n) {
        need(result !== 0, 'JSON');
        const scale = Number(parts[3] || 0) - fraction.length;
        need(Number.isSafeInteger(scale) && Math.abs(scale) <= 1024, 'JSON');
        const numerator = scale >= 0 ? digits * 10n ** BigInt(scale) : digits;
        const denominator = scale >= 0 ? 1n : 10n ** BigInt(-scale);
        need(numerator <= 1000000000000000n * denominator, 'JSON');
        need(!Number.isInteger(result) || numerator % denominator === 0n, 'JSON');
      }
      return result;
    }
    const result = value(0); space(); need(at === source.length && object(result), 'JSON');
    return result;
  }
  function selection(files) {
    need(files && integer(files.length, 8, 8), 'FILES');
    const result = new Map(); let total = 0;
    for (const file of files) {
      need(file && Object.hasOwn(LIMITS, file.name) && !result.has(file.name), 'FILES');
      need(integer(file.size, 1, LIMITS[file.name]), 'SIZE');
      total += file.size; need(total <= TOTAL, 'SIZE'); result.set(file.name, file);
    }
    return result;
  }
  async function digest(bytes) {
    need(root.crypto && root.crypto.subtle, 'CRYPTO');
    const result = await root.crypto.subtle.digest('SHA-256', bytes);
    return Array.from(new Uint8Array(result), byte => byte.toString(16).padStart(2, '0')).join('');
  }
  async function read(file, maximum) {
    // Slice also bounds acquisition if a File-like reader advertises a false size.
    const bytes = new Uint8Array(await file.slice(0, maximum + 1).arrayBuffer());
    need(bytes.byteLength === file.size && bytes.byteLength <= maximum, 'SIZE');
    return bytes;
  }
  function checkManifest(manifest) {
    exactKeys(manifest, ['evidence_kind', 'files', 'projection_kind', 'provenance', 'retention_days',
      'revision', 'run_attempt', 'schema_version', 'workflow_path', 'workflow_run_url', 'workflow_sha256']);
    need(manifest.schema_version === SCHEMAS['manifest.json'] && manifest.projection_kind === 'PUBLIC_PROJECTION');
    need(['HOSTED_REAL_SERVICE', 'FABRICATED_UNIT_DATA'].includes(manifest.evidence_kind));
    need(manifest.provenance === 'RECORDED_HOSTED_ASSERTIONS_NOT_INDEPENDENT_PROOF'
      && manifest.retention_days === 30 && manifest.workflow_path === '.github/workflows/temporal-server.yml');
    need(matches(manifest.revision, REVISION)
      && matches(manifest.workflow_sha256, HASH)
      && matches(manifest.workflow_run_url, URL)
      && integer(manifest.run_attempt, 1, 99999));
    exactKeys(manifest.files, NAMES.filter(name => name !== 'manifest.json'));
    for (const [name, entry] of Object.entries(manifest.files)) {
      exactKeys(entry, ['bytes', 'sha256']);
      need(integer(entry.bytes, 1, LIMITS[name]) && matches(entry.sha256, HASH));
    }
  }
  function indexedRows(record, nested) {
    need(Array.isArray(record.rows) && record.rows.length <= 200);
    const result = new Map();
    for (const outer of record.rows) {
      need(object(outer)); const row = nested ? outer[nested] : outer;
      need(object(row) && matches(row.job_id, JOB) && !result.has(row.job_id));
      result.set(row.job_id, row);
    }
    return result;
  }
  function duration(events, start, end) {
    const starts = events.filter(event => event.event === start), ends = events.filter(event => event.event === end);
    if (starts.length !== 1 || ends.length !== 1 || starts[0].sequence >= ends[0].sequence) return undefined;
    return ends[0].elapsed_us - starts[0].elapsed_us;
  }
  function present(records, checks) {
    for (const name of NAMES) need(records[name].schema_version === SCHEMAS[name]);
    const manifest = records['manifest.json'], trace = records['batch-trace.json'];
    const summaryRecord = records['batch-summary.json'];
    need(trace.evidence_kind === manifest.evidence_kind && object(summaryRecord.summary)
      && summaryRecord.summary.evidence_kind === manifest.evidence_kind);
    need(object(summaryRecord.summary) && object(trace.plan) && Array.isArray(trace.plan.jobs)
      && trace.plan.jobs.length === 200 && Array.isArray(trace.events) && trace.events.length <= 4096);
    const metadata = indexedRows(records['batch-metadata.json']);
    const outcomes = indexedRows(records['batch-outcomes.json'], 'terminal');
    indexedRows(records['batch-histories.json']);
    const eventMap = new Map(); let previousTime = -1;
    trace.events.forEach((event, index) => {
      need(object(event) && event.sequence === index + 1 && integer(event.elapsed_us)
        && event.elapsed_us >= previousTime && EVENTS.has(event.event)
        && matches(event.job_id, JOB));
      previousTime = event.elapsed_us;
      if (!eventMap.has(event.job_id)) eventMap.set(event.job_id, []);
      eventMap.get(event.job_id).push({ sequence: event.sequence, elapsed_us: event.elapsed_us, event: event.event });
    });
    const jobs = trace.plan.jobs.map((job, index) => {
      need(object(job) && job.job_id === 'batch-' + String(index).padStart(3, '0') && ['a', 'b'].includes(job.cohort));
      const events = eventMap.get(job.job_id) || [];
      return { id: job.job_id, cohort: job.cohort, events, activity: duration(events, 'activity_enter', 'activity_exit'),
        handler: duration(events, 'handler_enter', 'handler_return'), metadata: metadata.get(job.job_id) || {},
        outcome: outcomes.get(job.job_id) || {} };
    });
    return { demo: false, synthetic: manifest.evidence_kind === 'FABRICATED_UNIT_DATA', manifest,
      summary: summaryRecord.summary, cleanup: records['batch-cleanup.json'],
      replay: summaryRecord.independent_original_replay, jobs, checks };
  }
  async function inspect(files, options = {}) {
    const current = options.current || (() => true), readFile = options.read || read, hash = options.digest || digest;
    const active = () => { if (!current()) fail('STALE'); };
    active(); const chosen = selection(files), records = Object.create(null), checks = [];
    active(); let bytes = await readFile(chosen.get('manifest.json'), LIMITS['manifest.json']); active();
    need(bytes instanceof Uint8Array && bytes.byteLength === chosen.get('manifest.json').size, 'SIZE');
    records['manifest.json'] = strictJSON(bytes); bytes = null; checkManifest(records['manifest.json']);
    for (const name of NAMES.filter(name => name !== 'manifest.json')) {
      active(); const file = chosen.get(name), entry = records['manifest.json'].files[name];
      need(entry.bytes === file.size, 'HASH');
      bytes = await readFile(file, LIMITS[name]); active();
      need(bytes instanceof Uint8Array && bytes.byteLength === file.size && bytes.byteLength <= LIMITS[name], 'SIZE');
      const actual = await hash(bytes); active(); need(actual === entry.sha256, 'HASH');
      records[name] = strictJSON(bytes); bytes = null;
      checks.push({ name, bytes: entry.bytes, hash: actual });
    }
    active(); return present(records, checks);
  }
  // At most one read/hash chain, with one latest pending selection. Reset and demo
  // invalidate the generation immediately; stale work can never repaint the view.
  function controller(notify, inspectBundle = inspect) {
    let generation = 0, running = false, pending = null;
    async function drain() {
      if (running) return;
      running = true;
      try {
        while (pending) {
          const work = pending; pending = null;
          try {
            const model = await inspectBundle(work.files, { current: () => work.generation === generation });
            if (work.generation === generation) notify({ type: 'loaded', model });
          } catch (error) {
            if (work.generation === generation) notify({ type: 'error', message: MESSAGES[error.code] || MESSAGES.READ });
          }
        }
      } finally { running = false; }
    }
    return {
      select(files) {
        generation++; pending = null;
        try { selection(files); } catch (error) { notify({ type: 'error', message: MESSAGES[error.code] || MESSAGES.FILES }); return; }
        pending = { files: Array.from(files), generation }; notify({ type: 'loading' }); void drain();
      },
      reset() { generation++; pending = null; notify({ type: 'empty' }); },
      demo() { generation++; pending = null; notify({ type: 'loaded', model: demo() }); }
    };
  }
  function demo() {
    const jobs = Array.from({ length: 3 }, (_, index) => ({
      id: 'batch-' + String(index).padStart(3, '0'), cohort: index % 2 ? 'b' : 'a',
      activity: index === 2 ? undefined : 8, handler: index === 2 ? undefined : 0,
      metadata: {}, outcome: {},
      events: [
        { sequence: index * 4 + 1, elapsed_us: index * 10, event: 'activity_enter' },
        { sequence: index * 4 + 2, elapsed_us: index * 10 + 4, event: 'handler_enter' },
        { sequence: index * 4 + 3, elapsed_us: index * 10 + 4, event: 'handler_return' },
        { sequence: index * 4 + 4, elapsed_us: index * 10 + 8, event: 'activity_exit' }
      ].slice(0, index === 2 ? 2 : 4)
    }));
    return { demo: true, synthetic: true, manifest: {}, summary: {}, cleanup: {}, replay: undefined, jobs, checks: [] };
  }
  function mount(document) {
    const byId = id => document.getElementById(id);
    let model = null, selected = null;
    const element = (name, text, className) => {
      const node = document.createElement(name);
      if (text !== undefined) node.textContent = text;
      if (className) node.className = className;
      return node;
    };
    function facts(target, rows) {
      const fragment = document.createDocumentFragment();
      rows.forEach(([label, value]) => fragment.append(element('dt', label), element('dd', value)));
      target.replaceChildren(fragment);
    }
    function showDetail(id, focus = false) {
      selected = id; const job = model.jobs.find(row => row.id === id);
      byId('detail-intro').textContent = job.id + (model.demo ? ' · SYNTHETIC DEMO, UNVERIFIED' : ' · reported fields only');
      facts(byId('detail'), [
        ['Workflow ID', identifier(job.metadata.workflow_id, /^opendot-batch-[0-9]{3}$/)],
        ['Run ID', identifier(job.metadata.run_id, RUN)], ['Attempt', number(job.metadata.attempt)],
        ['Reported output', number(job.outcome.output)], ['Reported semantic validity', boolean(job.outcome.semantic_valid)],
        ['Result artifact', identifier(job.outcome.result_artifact_id, /^sha256:[a-f0-9]{64}$/)]
      ]);
      const fragment = document.createDocumentFragment();
      job.events.forEach(event => {
        const row = element('tr'); [number(event.sequence), number(event.elapsed_us), event.event]
          .forEach(text => row.append(element('td', text))); fragment.append(row);
      });
      if (!job.events.length) { const row = element('tr'); row.append(element('td', 'No recorded events')); fragment.append(row); }
      byId('events').replaceChildren(fragment);
      byId('jobs').querySelectorAll('button').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.job === id)));
      if (focus) byId('detail-title').focus();
    }
    function ledger() {
      const cohort = byId('cohort').value;
      const visible = model.jobs.filter(job => cohort === 'all' || job.cohort === cohort);
      byId('jobs-title').textContent = model.demo ? '3-job synthetic demonstration' : '200-job ledger';
      byId('job-count').textContent = visible.length + ' of ' + model.jobs.length + ' jobs shown' +
        (model.demo ? ' · artificial examples, no bundle loaded' : ' · select a job for its event sequence');
      const fragment = document.createDocumentFragment();
      visible.forEach(job => {
        const row = element('tr'), cell = element('td'), button = element('button', job.id, 'job-button');
        button.type = 'button'; button.dataset.job = job.id; button.setAttribute('aria-pressed', String(selected === job.id));
        button.addEventListener('click', () => showDetail(job.id, true)); cell.append(button); row.append(cell);
        [job.cohort, number(job.activity), number(job.handler),
          choice(job.outcome.tool_status, ['COMPLETED', 'BLOCKED', 'FAILED', 'TIMEOUT']),
          choice(job.outcome.transport_status, ['COMPLETED', 'BLOCKED', 'FAILED', 'TIMEOUT']), boolean(job.outcome.semantic_valid)]
          .forEach(text => row.append(element('td', text))); fragment.append(row);
      });
      byId('jobs').replaceChildren(fragment);
    }
    function render(value) {
      model = value; selected = model.jobs[0].id; byId('cohort').value = 'all';
      byId('kind').textContent = model.synthetic ? 'SYNTHETIC · UNVERIFIED' : 'REPORTED HOST ASSERTIONS';
      byId('trust').textContent = model.demo ? 'Synthetic demonstration only. No files were selected, hashed, or verified. Three artificial rows illustrate equal timestamps and missing observations.' :
        (model.synthetic ? 'FABRICATED UNIT DATA. ' : '') + 'Selected bytes match supplied manifest. Authenticity, semantic validation, original replay, and scientific validity are not established by this browser.';
      const manifest = model.manifest, summary = model.summary;
      facts(byId('context'), [['Revision', identifier(manifest.revision, REVISION)],
        ['Recorded workflow run (text only)', identifier(manifest.workflow_run_url, URL)],
        ['Recorded attempt', number(manifest.run_attempt)],
        ['Recorded workflow path', choice(manifest.workflow_path, ['.github/workflows/temporal-server.yml'])],
        ['Recorded workflow SHA-256', identifier(manifest.workflow_sha256, HASH)],
        ['Original replay', choice(model.replay, ['NOT_EVALUATED'])],
        ['Reported scientific validity', boolean(summary.scientific_validity)],
        ['Reported device authority', boolean(summary.device_control_authority)],
        ['Reported independent review', choice(summary.independent_review, ['NOT_EVALUATED'])],
        ['Reported CPU parallelism', choice(summary.cpu_parallelism, ['NOT_EVALUATED'])],
        ['Provenance', model.demo ? 'SYNTHETIC DEMO / UNVERIFIED' : 'Recorded assertions; not independent proof']]);
      const cards = [
        ['Delivery / admission', choice(summary.delivery_admission_acceptance, ['PASS', 'FAIL']), 'Reported acceptance only'],
        ['Activity overlap', choice(summary.activity_overlap, ['DEMONSTRATED', 'NOT_DEMONSTRATED']), 'Reported peak: ' + number(summary.observed_activity_peak) + ' · configured slots: ' + number(summary.configured_activity_slots)],
        ['Handler overlap', choice(summary.handler_overlap, ['DEMONSTRATED', 'NOT_DEMONSTRATED']), 'Reported peak: ' + number(summary.observed_handler_peak)],
        ['Validated terminals', number(summary.validated_terminal), 'Reported planned: ' + number(summary.planned)],
        ['Outstanding reservations', number(summary.outstanding), 'Reported peak: ' + number(summary.peak_outstanding)],
        ['Cleanup', choice(model.cleanup.cleanup_status, ['PASS', 'FAIL']), 'Reported active Activities: ' + number(model.cleanup.active_activity_calls)]
      ];
      const fragment = document.createDocumentFragment();
      cards.forEach(([label, value, note]) => {
        const card = element('article', undefined, 'metric'); card.append(element('h3', label), element('p', value), element('small', note)); fragment.append(card);
      }); byId('metrics').replaceChildren(fragment);
      const checks = document.createDocumentFragment();
      model.checks.forEach(check => { const row = element('tr'); [check.name, number(check.bytes), check.hash]
        .forEach(text => row.append(element('td', text))); checks.append(row); });
      if (model.demo) { const row = element('tr'); row.append(element('td', 'Demo: no file-byte comparison performed')); checks.append(row); }
      byId('checks').replaceChildren(checks); ledger(); showDetail(selected);
      byId('empty').hidden = true; byId('results').hidden = false;
    }
    function clear() {
      model = null; selected = null; byId('results').hidden = true; byId('empty').hidden = false;
      ['context', 'metrics', 'jobs', 'events', 'detail', 'checks'].forEach(id => byId(id).replaceChildren());
      ['kind', 'trust', 'job-count', 'detail-intro'].forEach(id => { byId(id).textContent = ''; });
      byId('cohort').value = 'all';
    }
    const control = controller(state => {
      clear(); byId('status').className = state.type === 'error' ? 'status error' : 'status';
      if (state.type === 'loaded') { render(state.model); byId('status').textContent = state.model.demo ? 'Synthetic demo loaded · unverified' : 'Selected bytes match supplied manifest · reported assertions only'; }
      else byId('status').textContent = state.type === 'loading' ? 'Reading bounded local files and comparing exact bytes…' :
        state.type === 'error' ? state.message : 'No evidence loaded';
    });
    byId('files').addEventListener('change', event => control.select(event.target.files));
    byId('reset').addEventListener('click', () => { byId('files').value = ''; control.reset(); });
    byId('demo').addEventListener('click', () => { byId('files').value = ''; control.demo(); });
    byId('cohort').addEventListener('change', () => { if (model) ledger(); });
    return control;
  }
  const api = Object.freeze({ LIMITS, NAMES, TOTAL, SCHEMAS, MESSAGES, strictJSON, selection, inspect,
    present, controller, demo, mount, number, boolean, choice, duration });
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else if (root.document) mount(root.document);
})(typeof globalThis !== 'undefined' ? globalThis : this);
