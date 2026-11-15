'use strict';
const $ = id => document.getElementById(id);
const make = (tag, text, className) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
};
let source = null;
let analysis = null;
let dirty = false;
let selected = null;
let page = 0;
const pageSize = 20;

function showError(message) {
    $('form-error').textContent = message;
    $('form-error').hidden = !message;
}
function setBusy(busy) {
    $('analyze').disabled = busy || !source;
    $('sample').disabled = busy;
    $('demo').disabled = busy;
    $('csv-file').disabled = busy;
    $('analyze').textContent = busy ? 'Analyzing…' : 'Analyze records →';
}
function markDirty() {
    dirty = true;
    $('stale-note').hidden = !analysis;
    $('export').disabled = true;
    $('form-status').textContent = 'Ready to analyze. Results update when you run the analysis.';
    showError('');
}
function dateLabel(value) {
    if (!value) return 'Not recorded';
    return value.replace('T', ' ').replace('+00:00', ' UTC');
}
function amountLabel(value) {
    const [whole, fraction] = value.split('.');
    return whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',') + (fraction ? '.' + fraction : '');
}
const rateLabel = value => value === null ? '—' : value.toFixed(1) + '%';
const timeLabel = value => value === null ? '—' : (Number.isInteger(value) ? value : value.toFixed(2)) + ' min';

async function loadSample(kind = 'sample') {
    setBusy(true);
    showError('');
    try {
        const response = await fetch(kind === 'demo' ? '/api/demo' : '/api/sample', {cache: 'no-store'});
        if (!response.ok) throw Error('Could not load the sample. Start this app with python3 server.py.');
        const result = await response.json();
        source = {name: result.filename, text: result.csv_text, sample: true};
        $('file-label').textContent = source.name;
        $('csv-file').value = '';
        $('observation').value = result.observation_time;
        $('target').value = result.target_minutes;
        displayAnalysis(result.analysis);
    } catch (error) {
        showError(error.message);
        $('form-status').textContent = 'Sample unavailable.';
    } finally {
        setBusy(false);
    }
}
async function chooseFile(file) {
    if (!file) return;
    source = null;
    $('file-label').textContent = file.name;
    markDirty();
    $('analyze').disabled = true;
    if (file.size > 1024 * 1024) {
        showError('Choose a CSV smaller than 1 MB.');
        return;
    }
    try {
        const buffer = await file.arrayBuffer();
        const text = new TextDecoder('utf-8', {fatal: true}).decode(buffer);
        source = {name: file.name, text, sample: false};
        $('form-status').textContent = 'File selected. Check the observation time and click Analyze records.';
        $('analyze').disabled = false;
    } catch {
        showError('Could not read this file as UTF-8 text. Export it as a UTF-8 CSV and try again.');
    }
}
$('csv-file').addEventListener('change', event => chooseFile(event.target.files[0]));
for (const name of ['dragenter', 'dragover']) $('dropzone').addEventListener(name, event => {
    event.preventDefault(); $('dropzone').classList.add('dragging');
});
for (const name of ['dragleave', 'drop']) $('dropzone').addEventListener(name, event => {
    event.preventDefault(); $('dropzone').classList.remove('dragging');
});
$('dropzone').addEventListener('drop', event => {
    if (!$('csv-file').disabled) chooseFile(event.dataTransfer.files[0]);
});
for (const id of ['observation', 'target']) $(id).addEventListener('input', markDirty);
$('sample').addEventListener('click', () => loadSample());
$('demo').addEventListener('click', () => loadSample('demo'));
$('analysis-form').addEventListener('submit', async event => {
    event.preventDefault();
    if (!source || !$('analysis-form').reportValidity()) return;
    setBusy(true);
    showError('');
    $('form-status').textContent = 'Checking and analyzing records…';
    try {
        const response = await fetch('/api/analyze', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({csv_text: source.text, observation_time: $('observation').value,
                                  target_minutes: Number($('target').value)})
        });
        const result = await response.json();
        if (!response.ok) throw Error(result.error || 'Analysis failed.');
        displayAnalysis(result);
    } catch (error) {
        dirty = true;
        $('stale-note').hidden = !analysis;
        $('export').disabled = true;
        showError(error.message);
        $('form-status').textContent = 'Analysis not updated. Fix the input and try again.';
    } finally {
        setBusy(false);
    }
});

function displayAnalysis(result) {
    analysis = result;
    dirty = false;
    selected = null;
    $('stale-note').hidden = true;
    $('export').disabled = false;
    $('case-detail').hidden = true;
    $('source-badge').textContent = source.sample ? 'SYNTHETIC' : 'CSV';
    $('synthetic-note').hidden = !source.sample;
    $('result-source').textContent = source.name;
    $('analysis-context').textContent = 'Observed ' + dateLabel(result.observation_time) + ' · ' + result.summary.target_minutes + '-minute credit target';
    const s = result.summary;
    $('target-rate').textContent = rateLabel(s.target_rate_percent);
    $('target-rate').style.color = s.target_rate_percent === null ? 'var(--muted)' : s.over_target ? 'var(--attention)' : 'var(--positive)';
    $('rate-detail').textContent = s.eligible_deposits
        ? `${s.within_target} of ${s.eligible_deposits} eligible deposits met the target` +
          (s.not_yet_due ? ` (${s.total_deposits} total; ${s.not_yet_due} not yet due excluded)` : '')
        : 'No eligible deposits at this observation time';
    $('total').textContent = s.total_deposits;
    $('completion-note').textContent = s.completed_deposits + ' completed';
    $('unresolved').textContent = s.unresolved_deposits;
    $('unresolved').style.color = s.unresolved_deposits ? 'var(--attention)' : 'var(--ink)';
    const overdueUnresolved = result.records.filter(r => !r.credited_at && r.deadline_code === 'late').length;
    $('unresolved-note').textContent = `${overdueUnresolved} overdue · ${s.not_yet_due} not yet due`;
    $('median').textContent = timeLabel(s.median_completion_minutes);
    $('deadline-chart').replaceChildren();
    for (const [label, count, color] of [
        ['Within target', s.within_target, 'teal'], ['Over target / overdue', s.over_target, 'amber-bg'],
        ['Not yet due', s.not_yet_due, 'gray']
    ]) {
        const row = make('div', undefined, 'chart-row');
        const labelRow = make('div', undefined, 'chart-label');
        labelRow.append(make('span', label), make('strong', String(count)));
        const track = make('div', undefined, 'chart-track');
        track.setAttribute('aria-hidden', 'true');
        const bar = make('div', undefined, 'chart-bar ' + color);
        bar.style.width = count / s.total_deposits * 100 + '%';
        track.append(bar); row.append(labelRow, track); $('deadline-chart').append(row);
    }
    const scenario = result.scenario;
    $('scenario-before').textContent = rateLabel(scenario.original_rate);
    $('scenario-after').textContent = rateLabel(scenario.scenario_rate);
    $('before-bar').style.width = (scenario.original_rate ?? 0) + '%';
    $('after-bar').style.width = (scenario.scenario_rate ?? 0) + '%';
    $('scenario-measure').textContent = `Deposits meeting the ${s.target_minutes}-minute credit-time target`;
    $('scenario-before-count').textContent = s.eligible_deposits ? s.within_target.toLocaleString('en-US') : '—';
    $('scenario-after-count').textContent = s.eligible_deposits ? (s.within_target + scenario.additional_within_target).toLocaleString('en-US') : '—';
    for (const id of ['scenario-before-denominator', 'scenario-after-denominator']) {
        $(id).textContent = s.eligible_deposits ? `of ${s.eligible_deposits.toLocaleString('en-US')} eligible deposits` : 'No eligible deposits';
    }
    $('scenario-status').textContent = scenario.original_rate === null ? 'No eligible deposits to compare at this observation time.' :
        `${scenario.additional_within_target} additional completed late ${scenario.additional_within_target === 1 ? 'deposit would meet' : 'deposits would meet'} the target under this assumption.`;
    $('scenario-exclusions').textContent = `${s.not_yet_due} unresolved ${s.not_yet_due === 1 ? 'deposit is' : 'deposits are'} not yet due and excluded from both percentages. Unresolved records are unchanged by the scenario.`;
    $('search').value = '';
    $('filter').value = 'all';
    $('evidence-filter').value = 'all';
    $('findings-list').replaceChildren(...ReviewTools.findings(result.records).map(text => make('li', text)));
    page = 0;
    renderRows();
    $('form-status').textContent = `${s.total_deposits} records analyzed. No source files were changed.`;
    showError('');
}
function minutesOverTarget(record) {
    return Math.max(0, record.elapsed_minutes - analysis.summary.target_minutes);
}
function prioritizeRecords(records) {
    // Missing credit is a record-based triage signal, not proof funds are missing.
    const rank = r => r.deadline_code === 'late' ? (r.credited_at ? 1 : 0) : r.deadline_code === 'pending' ? 2 : 3;
    return [...records].sort((a, b) => rank(a) - rank(b) ||
        (a.deadline_code === 'late' ? minutesOverTarget(b) - minutesOverTarget(a) : 0) ||
        a.deposit_id.localeCompare(b.deposit_id, 'en', {numeric: true}));
}
function renderRows() {
    if (!analysis) return;
    const query = $('search').value.trim().toLowerCase();
    const filter = $('filter').value;
    const rows = prioritizeRecords(analysis.records.filter(r => r.deposit_id.toLowerCase().includes(query) && ReviewTools.matches(r, filter, $('evidence-filter').value)));
    const table = $('record-rows');
    const panel = $('case-detail');
    // Preserve the reusable evidence panel before replacing table rows.
    if (table.contains(panel)) table.parentElement.after(panel);
    table.replaceChildren();
    $('record-count').textContent = analysis.records.length + ' records';
    const pages = Math.max(1, Math.ceil(rows.length / pageSize));
    page = Math.min(page, pages - 1);
    const visible = rows.slice(page * pageSize, (page + 1) * pageSize);
    $('page-number').textContent = `Page ${page + 1} of ${pages}`;
    $('previous').disabled = page === 0;
    $('next').disabled = page + 1 >= pages;
    $('table-status').textContent = `${rows.length ? page * pageSize + 1 : 0}–${page * pageSize + visible.length} of ${rows.length} matching records · ${analysis.records.length} total · All times UTC`;
    if (selected && !visible.some(r => r.deposit_id === selected)) { selected = null; $('case-detail').hidden = true; }
    if (!rows.length) {
        const tr = make('tr'); const td = make('td', 'No deposits match these filters.'); td.colSpan = 6; tr.append(td); table.append(tr); return;
    }
    for (const r of visible) {
        const row = make('tr');
        if (r.deposit_id === selected) row.className = 'selected';
        const id = make('td', r.deposit_id, 'deposit-id');
        const amount = make('td', amountLabel(r.amount_usdc), 'amount');
        const deadline = make('td');
        deadline.append(make('span', r.deadline_status, 'status-tag status-' + r.deadline_code));
        const overdue = make('td', r.deadline_code === 'late' ? timeLabel(minutesOverTarget(r)) : '—', 'amount');
        const category = make('td', r.category);
        const action = make('td');
        const inspect = make('button', 'Inspect', 'inspect-button'); inspect.type = 'button';
        inspect.setAttribute('aria-label', 'Inspect ' + r.deposit_id);
        inspect.setAttribute('aria-expanded', String(selected === r.deposit_id));
        inspect.setAttribute('aria-controls', 'case-detail');
        inspect.onclick = () => {
            showCase(r);
            renderRows();
            panel.scrollIntoView({block: 'center', behavior: 'instant'});
            panel.focus({preventScroll: true});
        };
        action.append(inspect); row.append(id, amount, deadline, overdue, category, action); table.append(row);
        if (r.deposit_id === selected) {
            const detailRow = make('tr', undefined, 'detail-row');
            const detailCell = make('td'); detailCell.colSpan = 6;
            detailCell.append(panel); detailRow.append(detailCell); table.append(detailRow);
        }
    }
}
function showCase(r) {
    selected = r.deposit_id;
    const panel = $('case-detail'); panel.hidden = false;
    const title = make('div', undefined, 'case-heading');
    const close = make('button', 'Close'); close.type = 'button'; close.onclick = () => {
        selected = null; panel.hidden = true; renderRows();
        const trigger = [...$('record-rows').querySelectorAll('button')].find(button => button.getAttribute('aria-label') === 'Inspect ' + r.deposit_id);
        if (trigger) trigger.focus();
    };
    title.append(make('h3', r.deposit_id + ' · Recorded evidence'), close);
    const grid = make('div', undefined, 'evidence-grid');
    for (const [label, text] of [
        ['Initiated', dateLabel(r.initiated_at)], ['Confirmation', dateLabel(r.confirmed_at)],
        ['Account credit', dateLabel(r.credited_at)], ['Before confirmation', timeLabel(r.before_confirmation_minutes)],
        ['After confirmation', timeLabel(r.after_confirmation_minutes)],
        [r.credited_at ? 'Total completion time' : 'Elapsed at observation', timeLabel(r.elapsed_minutes)],
        ['Over target by', r.deadline_code === 'late' ? timeLabel(minutesOverTarget(r)) : 'Not over target']
    ]) { const item = make('div'); item.append(make('p', label), make('strong', text)); grid.append(item); }
    const suggestion = ReviewTools.nextCheck(r);
    const check = make('div', undefined, 'suggested-check');
    check.append(make('h4', 'Suggested next check · ' + suggestion.title), make('p', suggestion.text), make('small', 'Rule-based suggestion for human review; not a verified cause or an AI response.'));
    panel.replaceChildren(title, grid, check, make('p', 'Rule-based triage; no AI review. Times are rounded for display. Missing records do not prove events never happened or establish a cause.', 'evidence-note'));
}
$('search').addEventListener('input', () => { page = 0; renderRows(); });
$('filter').addEventListener('change', () => { page = 0; renderRows(); });
$('evidence-filter').addEventListener('change', () => { page = 0; renderRows(); });
$('previous').addEventListener('click', () => { page = Math.max(0, page - 1); renderRows(); });
$('next').addEventListener('click', () => { page++; renderRows(); });
$('export').addEventListener('click', () => {
    if (!analysis || dirty) return;
    const columns = ['deposit_id', 'amount_usdc', 'deadline_status', 'minutes_over_target', 'category', 'initiated_at', 'confirmed_at', 'credited_at', 'observation_time', 'target_minutes'];
    const cell = value => {
        let text = value == null ? '' : String(value);
        // Prevent spreadsheet formula execution when someone opens an exported ID.
        if (/^[=+\-@\t\r]/.test(text)) text = "'" + text;
        return '"' + text.replace(/"/g, '""') + '"';
    };
    const text = [columns.join(','), ...prioritizeRecords(analysis.records).map(r => columns.map(key => cell(key === 'minutes_over_target' ? minutesOverTarget(r) : key === 'observation_time' ? analysis.observation_time : key === 'target_minutes' ? analysis.summary.target_minutes : r[key])).join(','))].join('\r\n');
    const url = URL.createObjectURL(new Blob([text], {type: 'text/csv;charset=utf-8'}));
    const anchor = make('a'); anchor.href = url; anchor.download = 'deposit-review-results.csv'; anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
});
loadSample('demo');
