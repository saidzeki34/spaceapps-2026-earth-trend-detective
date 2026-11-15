// Presentation only. Scientific figures and records come from the trend backend.
import { createMap } from './map.js';

const $ = (selector) => document.querySelector(selector);
const PAGE_SIZE = 40;
const SCOPE_LABELS = { catchment: 'Catchment history', region: 'Regional comparison', sources: 'Observed / GLDAS', stations: 'Station network' };
const STORE = 'rivascope-backend-selection-v1';
const state = { dataset: 'ch', view: 'timeseries', gauge: '', options: {}, demo: false, expanded: false };
let catalog = null, requestNumber = 0, controller = null, tableData = null, page = 0;
let courseRequest = 0, plotted = false, resizeTimer = null;
const courseCache = new Map();

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
function human(value) { return String(value ?? '').replaceAll('_', ' '); }
function numeric(value) {
  return value == null || !Number.isFinite(Number(value)) ? '—' : Number(value).toLocaleString('en-GB', { maximumSignificantDigits: 6 });
}
function dataset() { return catalog?.datasets?.find((d) => d.id === state.dataset); }
function views() { return dataset()?.views || []; }
function selectedView() { return views().find((v) => v.id === state.view); }
function selectedGauge() { return (dataset()?.gauges || []).find((g) => String(g.id) === state.gauge); }
function labelGauge(gauge) { return gauge.label || [gauge.river || gauge.name, gauge.place, gauge.id].filter(Boolean).join(' / '); }

async function api(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => { throw new Error('The local server returned an unreadable response.'); });
  if (!response.ok) throw new Error(payload.message || payload.error || `Request failed (${response.status}).`);
  return payload;
}

function readSelection() {
  try {
    const stored = JSON.parse(localStorage.getItem(STORE));
    if (stored && typeof stored === 'object') {
      for (const key of ['dataset', 'view', 'gauge']) if (typeof stored[key] === 'string') state[key] = stored[key];
      if (stored.options && typeof stored.options === 'object') state.options = stored.options;
    }
  } catch { /* Storage is optional. */ }
  const query = new URLSearchParams(location.hash.slice(1));
  for (const key of ['dataset', 'view', 'gauge']) if (query.has(key)) state[key] = query.get(key);
  for (const key of ['metric', 'year', 'variable', 'interval', 'driver', 'attribute', 'kind', 'normalized', 'log_scale', 'pair']) {
    if (query.has(key)) state.options[key] = query.get(key);
  }
  state.demo = query.get('demo') === '1';
}

function remember() {
  const saved = { dataset: state.dataset, view: state.view, gauge: state.gauge, options: state.options };
  try { localStorage.setItem(STORE, JSON.stringify(saved)); } catch { /* Storage is optional. */ }
  const params = parameters();
  if (state.demo) params.set('demo', '1');
  history.replaceState(null, '', `#${params}`);
}

function parameters() {
  const params = new URLSearchParams({ dataset: state.dataset, view: state.view });
  if (state.gauge) params.set('gauge', state.gauge);
  for (const option of selectedView()?.options || []) {
    const value = state.options[option.name];
    if (value !== undefined && value !== '') params.set(option.name, Array.isArray(value) ? value.join(',') : String(value));
  }
  return params;
}

function renderDatasetOptions() {
  $('#dataset').innerHTML = catalog.datasets.map((d) => `<option value="${esc(d.id)}">${esc(d.label || d.id)}${d.status === 'ready' ? '' : d.status === 'error' ? ' · read error' : ' · not built'}</option>`).join('');
  $('#dataset').value = state.dataset;
  $('#dataset').disabled = false;
}

function renderViews() {
  const list = views();
  if (!list.some((v) => v.id === state.view)) state.view = list[0]?.id || '';
  const groups = [...new Set(list.map((v) => v.scope))];
  $('#view').innerHTML = groups.length ? groups.map((scope) => `<optgroup label="${esc(SCOPE_LABELS[scope] || human(scope))}">${list.filter((v) => v.scope === scope).map((v) => `<option value="${esc(v.id)}">${esc(v.label)}</option>`).join('')}</optgroup>`).join('') : '<option>No saved results</option>';
  $('#view').value = state.view;
  $('#view').disabled = !list.length;
}

function renderGaugeOptions() {
  const all = dataset()?.gauges || [];
  const filter = $('#gauge-filter').value.trim().toLowerCase();
  const filtered = all.filter((g) => labelGauge(g).toLowerCase().includes(filter));
  $('#gauge').innerHTML = filtered.length ? filtered.map((g) => `<option value="${esc(g.id)}">${esc(labelGauge(g))}</option>`).join('') : '<option value="">No matching gauges</option>';
  $('#gauge').value = filtered.some((g) => String(g.id) === state.gauge) ? state.gauge : '';
  $('#gauge').disabled = !filtered.length;
  $('#gauge-filter').disabled = !all.length;
}

function renderOptions() {
  const spec = selectedView();
  const options = spec?.options || [];
  const html = options.map((option) => {
    const items = option.values || [];
    const ids = items.map((v) => String(v.id));
    if (option.name === 'variable') {
      let chosen = String(state.options.variable || '').split(',').filter((id) => ids.includes(id)).slice(0, 4);
      if (!chosen.length && ids.length) chosen = [ids.includes('discharge_vol') ? 'discharge_vol' : ids[0]];
      state.options.variable = chosen.join(',');
      return `<div class="field"><fieldset><legend>Time-series variables · up to 4</legend><div class="check-list">${items.map((item) => `<label><input type="checkbox" data-variable="${esc(item.id)}" ${chosen.includes(String(item.id)) ? 'checked' : ''}><span>${esc(item.label)}</span></label>`).join('')}</div></fieldset></div>`;
    }
    let value = String(state.options[option.name] ?? '');
    if (!ids.includes(value)) value = String(option.default ?? (option.name === 'year' ? ids.at(-1) : ids[0]) ?? '');
    state.options[option.name] = value;
    return `<div class="field"><label for="option-${esc(option.name)}">${esc(option.label || human(option.name))}</label><select id="option-${esc(option.name)}" data-option="${esc(option.name)}" ${ids.length ? '' : 'disabled'}>${items.map((item) => `<option value="${esc(item.id)}" ${String(item.id) === value ? 'selected' : ''}>${esc(item.label)}</option>`).join('')}</select></div>`;
  });
  $('#view-options').innerHTML = html.join('');
  const needsGauge = spec?.scope === 'catchment' || spec?.id === 'source_regime';
  $('#gauge-controls').hidden = !needsGauge;
  renderGaugeFacts();
}

function renderGaugeFacts() {
  const gauge = selectedGauge();
  if (!gauge || $('#gauge-controls').hidden) { $('#gauge-facts').innerHTML = ''; return; }
  const facts = [['Station ID', gauge.id]];
  if (gauge.area_km2 != null) facts.push(['Catchment area', `${numeric(gauge.area_km2)} km²`]);
  if (gauge.elevation_m != null) facts.push([`${human(gauge.elevation_statistic || '')} elevation`.trim(), `${numeric(gauge.elevation_m)} m`]);
  $('#gauge-facts').innerHTML = facts.map(([key, value]) => `<dt>${esc(key)}</dt><dd>${esc(value)}</dd>`).join('');
}

function renderProvenance() {
  const data = dataset();
  const status = data?.status === 'ready';
  $('#dataset-state').textContent = status ? 'Loaded' : data?.status === 'error' ? 'Error' : 'Not built';
  $('#dataset-state').className = `tag ${status ? 'ready' : 'unavailable'}`;
  const facts = [['Source', data?.label || state.dataset], ['Record', data?.kind === 'model' ? 'Modelled runoff · not a gauge measurement' : data?.kind === 'network' ? 'Station comparison' : 'Historical observations']];
  if (data?.first_date) facts.push(['Saved daily coverage', `${data.first_date} to ${data.last_date}`]);
  if (data?.years?.length) facts.push(['Analysis years', `${data.years[0]}–${data.years.at(-1)}`]);
  if (data?.count != null) facts.push(['Gauge count', data.count]);
  $('#provenance').innerHTML = `<dl>${facts.map(([key, value]) => `<dt>${esc(key)}</dt><dd>${esc(value)}</dd>`).join('')}</dl>${data?.provenance && Object.keys(data.provenance).length ? `<h3 style="margin-top:14px">Provenance</h3><pre>${esc(JSON.stringify(data.provenance, null, 2))}</pre>` : '<p style="margin-top:12px">No additional provenance record is available.</p>'}${data?.settings ? `<details><summary>Backend settings</summary><pre>${esc(JSON.stringify(data.settings, null, 2))}</pre></details>` : ''}`;
}

function renderNotice(payload = null) {
  const node = $('#data-notice');
  if (state.demo) {
    node.className = 'notice demo'; node.hidden = false;
    node.innerHTML = '<strong>IMAGINARY DATA — VISUAL DEMONSTRATION ONLY</strong><p>This topographic surface uses invented values. It represents no river, measurement, forecast or operational risk assessment.</p>';
    return;
  }
  const data = payload || dataset();
  const isModel = dataset()?.kind === 'model';
  if (data?.status === 'ready' && !isModel) { node.hidden = true; return; }
  node.className = `notice${data?.status === 'error' ? ' error' : ''}`; node.hidden = false;
  node.innerHTML = data?.status === 'ready' ? '<strong>Model output</strong><p>GLDAS-2.1 is unrouted land-surface model runoff. It is not measured river discharge or a forecast.</p>' : `<strong>${data?.status === 'error' ? 'Saved result could not be read' : 'Saved result unavailable'}</strong><p>${esc(data?.message || 'No saved output is available for this selection.')}</p>${data?.build_command || data?.command ? `<pre>${esc(data.build_command || data.command)}</pre>` : ''}`;
}

function setMode(demo) {
  state.demo = demo;
  $('#observed-mode').classList.toggle('active', !demo);
  $('#demo-mode').classList.toggle('active', demo);
  $('#observed-mode').setAttribute('aria-pressed', String(!demo));
  $('#demo-mode').setAttribute('aria-pressed', String(demo));
  $('#table-panel').hidden = demo;
}

function showFigureStatus(title, detail = '', command = '') {
  $('#chart').hidden = true;
  $('#figure-status').hidden = false;
  $('#figure-status').innerHTML = `<h3>${esc(title)}</h3>${detail ? `<p class="status-detail">${esc(detail)}</p>` : ''}${command ? `<pre>${esc(command)}</pre>` : ''}`;
}

function showTableStatus(message) {
  tableData = null;
  $('#download').disabled = true;
  $('#table-wrap').hidden = true;
  $('#table-pagination').hidden = true;
  $('#table-status').hidden = false;
  $('#table-status').textContent = message;
  $('#row-count').textContent = '';
}

function contextText(context = {}) {
  if (typeof context === 'string') return context;
  return [context.source, context.period && `${context.period} · ${context.calendar || 'saved period'}`, context.unit].filter(Boolean).join(' / ');
}

async function drawFigure(figure) {
  if (!window.Plotly) throw new Error('The local Plotly library could not be loaded. Reload the page or check the server.');
  const layout = { ...(figure.layout || {}), autosize: true, paper_bgcolor: '#ffffff', plot_bgcolor: '#ffffff', font: { ...(figure.layout?.font || {}), family: 'Arial, Helvetica, sans-serif', size: 12, color: '#354e61' }, hoverlabel: { ...(figure.layout?.hoverlabel || {}), font: { ...(figure.layout?.hoverlabel?.font || {}), family: 'Arial, Helvetica, sans-serif' } } };
  delete layout.width;
  const chart = $('#chart');
  // Tall network figures keep their backend row spacing and scroll within the panel.
  const requestedHeight = Number(figure.layout?.height);
  chart.style.height = !state.expanded && requestedHeight > 600 ? `${requestedHeight}px` : '';
  if (!requestedHeight || state.expanded) delete layout.height;
  $('#figure-status').hidden = true;
  chart.hidden = false;
  await Plotly.react(chart, figure.data || [], layout, { responsive: true, displaylogo: false, displayModeBar: false, scrollZoom: false });
  plotted = true;
}

function renderTable() {
  if (!tableData) return;
  const rows = tableData.rows || [], columns = tableData.columns || [];
  const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  page = Math.max(0, Math.min(page, pages - 1));
  $('#table-status').hidden = true;
  $('#table-wrap').hidden = false;
  $('#download').disabled = !rows.length;
  const total = tableData.total_rows || tableData.total || rows.length;
  $('#row-count').textContent = `${rows.length.toLocaleString()} records${total > rows.length ? ` shown of ${total.toLocaleString()}` : ''}`;
  const caption = `${human(selectedView()?.table || state.view)} · ${dataset()?.label || state.dataset} · missing values shown as —`;
  const html = rows.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE).map((row) => `<tr>${columns.map((column, index) => {
    const value = Array.isArray(row) ? row[index] : row[column];
    const missing = value == null || (typeof value === 'number' && !Number.isFinite(value));
    const text = missing ? '—' : typeof value === 'number' ? numeric(value) : typeof value === 'object' ? JSON.stringify(value) : String(value);
    return `<td class="${missing ? 'missing' : typeof value === 'number' ? 'numeric' : ''}" title="${esc(missing ? 'Missing' : typeof value === 'object' ? text : value)}">${esc(text)}</td>`;
  }).join('')}</tr>`).join('');
  $('#table-wrap').innerHTML = `<table><caption>${esc(caption)}</caption><thead><tr>${columns.map((column) => `<th scope="col">${esc(column)}</th>`).join('')}</tr></thead><tbody>${html}</tbody></table>`;
  $('#table-pagination').hidden = pages < 2;
  $('#page-label').textContent = `Page ${page + 1} / ${pages}`;
  $('#previous-page').disabled = page === 0;
  $('#next-page').disabled = page === pages - 1;
}

async function refreshView() {
  const number = ++requestNumber;
  controller?.abort(); controller = new AbortController();
  setMode(state.demo); remember(); renderNotice();
  $('#figure-notes').innerHTML = '';
  if (state.demo) { await drawDemo(); return; }
  const data = dataset(), spec = selectedView();
  $('#figure-title').textContent = spec?.label || data?.label || 'No saved results';
  $('#figure-kicker').textContent = (SCOPE_LABELS[spec?.scope] || 'SAVED BACKEND RESULTS').toUpperCase();
  $('#figure-context').textContent = data?.label || '';
  if (data?.status !== 'ready' || !spec) {
    showFigureStatus(data?.status === 'error' ? 'Unable to load saved results' : 'Results not built', data?.message || 'No saved backend results exist for this source.', data?.build_command);
    showTableStatus('No records available.'); return;
  }
  showFigureStatus('Loading analysis', 'Reading saved backend output…');
  showTableStatus('Loading records…');
  $('#figure-panel').setAttribute('aria-busy', 'true');
  const params = parameters();
  const tableParams = new URLSearchParams(params);
  if (spec.table) tableParams.set('table', spec.table);
  const opts = { signal: controller.signal };
  const jobs = [
    api(`/api/figure?${params}`, opts).then(async (payload) => {
      if (number !== requestNumber) return;
      if (payload.status !== 'ready' || !payload.figure) {
        renderNotice(payload);
        showFigureStatus('Analysis unavailable', payload.message || 'No result is available for this selection.', payload.build_command);
        return;
      }
      $('#figure-context').textContent = contextText(payload.context);
      $('#figure-notes').innerHTML = (payload.notes || []).map((note) => `<p>${esc(note)}</p>`).join('');
      await drawFigure(payload.figure);
    }).catch((error) => {
      if (error.name !== 'AbortError' && number === requestNumber) showFigureStatus('Unable to display analysis', error.message);
    }).finally(() => { if (number === requestNumber) $('#figure-panel').setAttribute('aria-busy', 'false'); }),
    api(`/api/table?${tableParams}`, opts).then((payload) => {
      if (number !== requestNumber) return;
      if (payload.status !== 'ready') { showTableStatus(payload.message || 'No matching records.'); return; }
      tableData = payload; page = 0;
      if (!payload.rows?.length) { showTableStatus('No records match this selection.'); return; }
      renderTable();
    }).catch((error) => { if (error.name !== 'AbortError' && number === requestNumber) showTableStatus(error.message); }),
  ];
  await Promise.allSettled(jobs);
}

async function drawDemo() {
  $('#figure-kicker').textContent = 'IMAGINARY DATA / DEMONSTRATION';
  $('#figure-title').textContent = '3D volatility surface';
  $('#figure-context').textContent = 'Synthetic coordinates and values · not linked to the selected gauge';
  $('#figure-notes').innerHTML = '<p>Illustrative geometry only. Drag to rotate. There is no fitted model, observed river response or risk score behind this surface.</p>';
  const x = Array.from({ length: 35 }, (_, i) => -20 + i * 40 / 34);
  const y = Array.from({ length: 35 }, (_, i) => -30 + i * 60 / 34);
  const z = y.map((b) => x.map((a) => 8 + 0.008 * a * a + 0.005 * b * b + 11 * Math.exp(-((a - 5) ** 2 / 120 + (b + 8) ** 2 / 180)) + 2.2 * Math.sin(a / 8) * Math.cos(b / 11)));
  try {
    await drawFigure({ data: [{ type: 'surface', x, y, z, colorscale: [[0, '#dbe8ef'], [.4, '#76a3bb'], [.7, '#306d93'], [1, '#17394f']], colorbar: { title: { text: 'Imaginary<br>variation (%)', font: { size: 11 } }, thickness: 12 }, contours: { z: { show: true, usecolormap: true, project: { z: true } } }, hovertemplate: 'Imaginary timing: %{x:.1f} d<br>Imaginary quantity: %{y:.1f}%<br>Imaginary variation: %{z:.1f}%<extra>DEMONSTRATION</extra>' }], layout: { margin: { l: 18, r: 80, t: 20, b: 20 }, scene: { xaxis: { title: { text: 'Timing shift (imaginary days)' } }, yaxis: { title: { text: 'Quantity change (imaginary %)' } }, zaxis: { title: { text: 'Variation (imaginary %)' } }, camera: { eye: { x: 1.6, y: -1.6, z: 1.1 } }, aspectratio: { x: 1.2, y: 1.2, z: .7 } } } });
  } catch (error) { showFigureStatus('Demonstration unavailable', error.message); }
}

const map = createMap($('#map'), (id) => {
  if (!(dataset()?.gauges || []).some((g) => String(g.id) === id)) return;
  state.gauge = id; $('#gauge-filter').value = '';
  renderGaugeOptions(); renderGaugeFacts(); updateMap();
  if (selectedView()?.scope !== 'catchment') { state.view = 'timeseries'; renderViews(); renderOptions(); }
  setMode(false); refreshView();
});

async function updateMap() {
  const request = ++courseRequest, data = dataset();
  const datasetId = state.dataset;
  const region = data?.country?.toLowerCase() || (state.dataset === 'stations' ? 'ch' : state.dataset.split('_')[0]);
  const gauges = data?.gauges || [];
  const highlight = !$('#gauge-controls').hidden ? state.gauge : null;
  map.setData(gauges, null, highlight, region);
  $('#map-note').textContent = gauges.length ? 'Loading available river courses…' : 'No saved gauge positions are available for this source.';
  try {
    if (!courseCache.has(datasetId)) courseCache.set(datasetId, await api(`/api/courses?dataset=${encodeURIComponent(datasetId)}`));
    if (request !== courseRequest) return;
    const courses = courseCache.get(datasetId);
    map.setData(gauges, courses, highlight, region);
    const hasCourse = (courses.features || []).some((feature) => String(feature.properties?.id) === highlight);
    $('#map-note').textContent = !gauges.length ? 'No saved gauge positions are available for this source.' : highlight ? (hasCourse ? 'Gauge point and mapped OpenStreetMap river segments. The stored course may be incomplete; display geometry only.' : `Gauge point only. ${courses.missing?.[highlight] || 'No verified course is stored for this gauge.'}`) : 'Gauge points and mapped river segments. Display geometry only; the stored river network may be incomplete.';
  } catch {
    if (request !== courseRequest) return;
    $('#map-note').textContent = gauges.length ? 'Gauge points only. River-course geometry is unavailable.' : 'No saved gauge positions are available for this source.';
  }
}

async function chooseDataset() {
  const data = dataset();
  if (!(data?.gauges || []).some((g) => String(g.id) === state.gauge)) state.gauge = String(data?.gauges?.[0]?.id || '');
  $('#gauge-filter').value = '';
  renderViews(); renderGaugeOptions(); renderOptions(); renderProvenance();
  updateMap();
  await refreshView();
}

async function loadCatalogue(refresh = false) {
  $('#refresh').disabled = true;
  $('#connection').textContent = refresh ? 'Reloading saved results…' : 'Loading catalogue…';
  try {
    catalog = await api(refresh ? '/api/refresh' : '/api/catalog', refresh ? { method: 'POST' } : {});
    if (!Array.isArray(catalog.datasets) || !catalog.datasets.length) throw new Error('No dataset catalogue was returned.');
    if (!catalog.datasets.some((d) => d.id === state.dataset)) state.dataset = catalog.datasets.find((d) => d.status === 'ready')?.id || catalog.datasets[0].id;
    $('#startup-error').hidden = true;
    const ready = catalog.datasets.filter((d) => d.status === 'ready').length;
    $('#connection').textContent = `${ready} / ${catalog.datasets.length} saved datasets available`;
    if (refresh) courseCache.clear();
    renderDatasetOptions();
    await chooseDataset();
  } catch (error) {
    $('#startup-error').textContent = `${error.message} Use “Reload saved results” to retry.`;
    $('#startup-error').hidden = false;
    $('#connection').textContent = 'Local server unavailable';
    showFigureStatus('Unable to load the catalogue', error.message);
  } finally { $('#refresh').disabled = false; }
}

$('#dataset').addEventListener('change', () => { state.dataset = $('#dataset').value; setMode(false); chooseDataset(); });
$('#view').addEventListener('change', () => { state.view = $('#view').value; renderOptions(); updateMap(); setMode(false); refreshView(); });
$('#gauge-filter').addEventListener('input', renderGaugeOptions);
$('#gauge').addEventListener('change', () => { state.gauge = $('#gauge').value; renderGaugeFacts(); updateMap(); setMode(false); refreshView(); });
$('#view-options').addEventListener('change', (event) => {
  const input = event.target;
  if (input.dataset.option) state.options[input.dataset.option] = input.value;
  else if (input.dataset.variable) {
    const chosen = [...document.querySelectorAll('[data-variable]:checked')];
    if (chosen.length > 4 || chosen.length === 0) { input.checked = !input.checked; return; }
    state.options.variable = chosen.map((node) => node.dataset.variable).join(',');
  } else return;
  setMode(false); refreshView();
});
$('#refresh').addEventListener('click', () => loadCatalogue(true));
$('#observed-mode').addEventListener('click', () => { setMode(false); refreshView(); });
$('#demo-mode').addEventListener('click', () => { setMode(true); refreshView(); });
$('#map-reset').addEventListener('click', () => map.fit());
$('#previous-page').addEventListener('click', () => { page--; renderTable(); });
$('#next-page').addEventListener('click', () => { page++; renderTable(); });

function expandChart(expanded) {
  state.expanded = expanded;
  $('#figure-panel').classList.toggle('expanded', expanded);
  document.body.classList.toggle('chart-expanded', expanded);
  $('#expand').textContent = expanded ? 'Close expanded chart' : 'Expand chart';
  $('#expand').setAttribute('aria-expanded', String(expanded));
  if (plotted) {
    Plotly.relayout($('#chart'), { height: expanded ? $('#figure-panel').clientHeight - $('.figure-heading').offsetHeight - $('#figure-notes').offsetHeight : null, autosize: true });
  }
}
$('#expand').addEventListener('click', () => expandChart(!state.expanded));
document.addEventListener('keydown', (event) => { if (event.key === 'Escape' && state.expanded) expandChart(false); });
$('#download').addEventListener('click', () => {
  if (!tableData) return;
  const field = (value) => {
    let text = value == null ? '' : typeof value === 'object' ? JSON.stringify(value) : String(value);
    if (typeof value === 'string' && /^[=+\-@\t\r]/.test(text)) text = `'${text}`;
    return `"${text.replaceAll('"', '""')}"`;
  };
  const lines = [tableData.columns.map(field).join(','), ...tableData.rows.map((row) => tableData.columns.map((column, i) => field(Array.isArray(row) ? row[i] : row[column])).join(','))];
  const url = URL.createObjectURL(new Blob(['\uFEFF' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8' }));
  const link = document.createElement('a'); link.href = url;
  link.download = `rivascope-${state.dataset}-${selectedView()?.table || state.view}.csv`; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});

new ResizeObserver(() => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => { if (plotted && !$('#chart').hidden) Plotly.Plots.resize($('#chart')).catch(() => {}); }, 100);
}).observe($('#figure-panel'));
window.addEventListener('pagehide', () => navigator.sendBeacon('/api/bye'));
readSelection();
loadCatalogue();
