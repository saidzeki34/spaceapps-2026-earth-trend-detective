// Claude's map, sidebar and results flow, connected to the saved trend backend.
// No observations, forecasts or occupational thresholds are generated here.
import { createMap } from './map.js';

const $ = (selector, root = document) => root.querySelector(selector);
const STORE = 'rivascope-claude-selection-v2';
const PAGE_SIZE = 40;
const OCCUPATIONS = [
  ['hydropower', 'Hydropower', 'How have the amount and the timing of the flow changed?'],
  ['data_center', 'Data center infrastructure', 'Explore the historical river conditions relevant to cooling.'],
  ['power_plant', 'Power plant', 'Explore river flow through warm and dry months.'],
  ['government', 'Government official', 'Where have the recorded river conditions changed?'],
  ['defence', 'Defence', 'How has this river varied through the year?'],
].map(([id, label, question]) => ({ id, label, question }));
const SCOPES = { catchment: 'River history', region: 'Regional comparison', sources: 'Observed / GLDAS', stations: 'Station network' };
const COLORS = { temperature_mean: '#c2532d', temperature_min: '#c2532d', temperature_max: '#c2532d', precipitation: '#3f7fb5', evap: '#b48a1f', swe: '#6c94a6', discharge_vol: '#15324f', discharge_spec: '#2f8a66' };
const WATER = new Set(['discharge_vol', 'discharge_spec', 'waterlevel', 'runoff_surface', 'runoff_base']);
const state = { occupation: null, country: null, river: null, dataset: 'ch', view: 'timeseries', options: {}, statistics: false, expanded: false, full: false };
let catalog, geodata, map, answer = null, tableData = null, page = 0;
let requestNumber = 0, courseRequest = 0, controller = null, yearTimer = null, drawTimer = null;
const courseCache = new Map();

function esc(value) { return String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
function numeric(value) { return value == null ? '—' : Number(value).toLocaleString('en-GB', { maximumSignificantDigits: 6 }); }
const dataset = () => catalog?.datasets.find(d => d.id === state.dataset);
const selectedView = () => dataset()?.views.find(v => v.id === state.view);
const selectedRiver = () => dataset()?.gauges.find(g => String(g.id) === state.river);
const countryName = code => geodata.countries[code]?.name || code;
const riverName = river => river?.river || river?.name || river?.id || '';
const isDemo = () => state.view === '__demo';

async function api(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || payload.message || `Request failed (${response.status}).`);
  return payload;
}

function recall() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORE));
    if (saved && typeof saved === 'object') {
      for (const key of ['occupation', 'dataset', 'view']) if (typeof saved[key] === 'string') state[key] = saved[key];
      if (saved.options && typeof saved.options === 'object') state.options = saved.options;
      state.statistics = saved.statistics === true;
    } else state.occupation = JSON.parse(localStorage.getItem('rivascope-selection'))?.occupation || null;
  } catch { /* Storage is optional. */ }
  const link = new URLSearchParams(location.hash.slice(1));
  state.occupation = link.get('o') || state.occupation;
  state.country = link.get('c');
  state.river = link.get('gauge') || link.get('r');
  state.dataset = link.get('dataset') || state.country?.toLowerCase() || state.dataset;
  state.view = link.get('view') || state.view;
  state.expanded = link.get('x') === '1';
  for (const key of ['year', 'variable', 'interval', 'metric', 'driver', 'attribute', 'kind', 'normalized', 'log_scale', 'pair']) {
    if (link.has(key)) state.options[key] = link.get(key);
  }
  if (link.has('y')) state.options.year = link.get('y');
  if (link.has('m')) state.options.interval = link.get('m') === 'native' ? 'daily' : 'monthly';
  // Saved links to Claude's Swiss identifiers remain usable.
  if (state.river?.startsWith('ch-')) state.river = state.river.slice(3);
  if (!OCCUPATIONS.some(o => o.id === state.occupation)) state.occupation = null;
  if (!catalog.datasets.some(d => d.id === state.dataset)) state.dataset = 'ch';
  if (state.river && !state.country) state.country = dataset()?.country || selectedRiver()?.country || 'CH';
  if (!geodata.countries[state.country]) state.country = null;
  normalize();
}

function remember() {
  try { localStorage.setItem(STORE, JSON.stringify({ occupation: state.occupation, dataset: state.dataset, view: state.view, options: state.options, statistics: state.statistics })); } catch { /* Storage is optional. */ }
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries({ o: state.occupation, c: state.country, r: state.river, dataset: state.dataset, view: state.view, x: state.expanded ? '1' : '', ...state.options })) {
    if (value != null && value !== '') params.set(key, String(value));
  }
  history.replaceState(null, '', `#${params}`);
}

function normalize() {
  if (state.river && !selectedRiver()) state.river = null;
  const list = dataset()?.views || [];
  if (!isDemo() && !list.some(v => v.id === state.view)) state.view = list[0]?.id || 'timeseries';
  for (const option of selectedView()?.options || []) {
    const ids = option.values.map(v => String(v.id));
    if (option.name === 'variable') {
      let chosen = String(state.options.variable || '').split(',').filter(id => ids.includes(id)).slice(0, 4);
      if (!chosen.length) chosen = ['temperature_mean', 'discharge_vol'].filter(id => ids.includes(id));
      state.options.variable = (chosen.length ? chosen : ids.slice(0, 1)).join(',');
    } else if (!ids.includes(String(state.options[option.name] ?? ''))) {
      state.options[option.name] = option.name === 'year' ? ids.at(-1) : option.name === 'interval' ? 'monthly' : ids[0];
    }
  }
}

function parameters() {
  const params = new URLSearchParams({ dataset: state.dataset, view: state.view });
  if (state.river) params.set('gauge', state.river);
  for (const option of selectedView()?.options || []) if (state.options[option.name] != null) params.set(option.name, state.options[option.name]);
  return params;
}

async function start() {
  try {
    [catalog, geodata] = await Promise.all([api('/api/catalog'), api('data/geodata.json')]);
    recall();
    $('#choices').innerHTML = OCCUPATIONS.map(o => `<li><button data-occupation="${o.id}"><span class="choice-name">${esc(o.label)}</span><span class="choice-question">${esc(o.question)}</span></button></li>`).join('');
    $('#occupation-select').innerHTML = OCCUPATIONS.map(o => `<option value="${o.id}">${esc(o.label)}</option>`).join('');
    $('#about-body').innerHTML = aboutHTML();
    const linked = location.hash.length > 1;
    $('#splash').classList.add('leaving');
    setTimeout(() => $('#splash')?.remove(), 500);
    if (linked && state.occupation) openApp(); else $('#occupation').hidden = false;
  } catch (error) {
    $('#splash-status').innerHTML = `RivaScope could not start. ${esc(error.message)} <button class="link" data-action="retry">Try again</button>`;
  }
}

function aboutHTML() {
  return `<p>RivaScope reads the team's saved trend results on this computer. Opening the application or reloading results never downloads observations or builds datasets.</p>
    ${catalog.datasets.map(d => `<p><b>${esc(d.label)}:</b> ${d.status === 'ready' ? `${d.count} gauges${d.first_date ? `, ${esc(d.first_date)} to ${esc(d.last_date)}` : ''}.` : esc(d.message || 'Not built.')} ${d.status !== 'ready' ? `<code>${esc(d.build_command)}</code>` : ''}</p>`).join('')}
    <p>GLDAS is land-surface model output, not measured river discharge or a forecast. Missing observations stay missing. Occupation is a navigation preference; no occupational requirements, risk scores or predictions have been implemented.</p>
    <p>The optional 3D surface is an isolated synthetic demonstration, unrelated to any selected river.</p>
    <p>Map imagery and place names: Esri. Country outlines: Natural Earth. Stored river segments: © OpenStreetMap contributors. A gauge may have no verified course; a catchment boundary is not a river line.</p>`;
}

function openApp() {
  $('#occupation').hidden = true;
  $('#app').hidden = false;
  $('#occupation-select').value = state.occupation;
  if (!map) map = createMap($('#map'), geodata, {
    country: code => go({ country: code, river: null, dataset: code.toLowerCase() }),
    river: id => {
      const gauge = dataset()?.gauges.find(g => String(g.id) === String(id));
      if (gauge) go({ river: String(id), country: dataset()?.country || gauge.country || state.country });
    },
    europe: () => go({ country: null, river: null }),
  });
  render();
}

function go(changes) {
  clearTimeout(yearTimer);
  const sourceChanged = changes.dataset && changes.dataset !== state.dataset;
  Object.assign(state, changes);
  if (sourceChanged) { state.river = null; state.options = {}; state.view = changes.dataset === 'stations' ? 'station_month_heatmap' : 'timeseries'; }
  state.full = false;
  if (!state.river) state.expanded = false;
  normalize(); render();
}

function render() {
  const hasResults = Boolean(state.river);
  $('#layout').classList.toggle('has-river', hasResults);
  $('#layout').classList.toggle('expanded', state.expanded && hasResults);
  renderCrumbs(); renderSide(); updateMap(); remember();
  if (hasResults) { renderTimeline(); refreshView(); }
  else { ++requestNumber; controller?.abort(); answer = null; tableData = null; $('#results').innerHTML = ''; $('#timeline').innerHTML = ''; }
}

function renderCrumbs() {
  const parts = [state.country ? '<button class="link" data-action="europe">Europe</button>' : '<span class="here">Europe</span>'];
  if (state.country) parts.push(state.river ? `<button class="link" data-action="rivers">${esc(countryName(state.country))}</button>` : `<span class="here">${esc(countryName(state.country))}</span>`);
  if (state.river) parts.push(`<span class="here">${esc(riverName(selectedRiver()))}</span>`);
  $('#crumbs').innerHTML = parts.join('<span class="sep">/</span>');
}

function sourceHTML() {
  const available = catalog.datasets.filter(d => d.country === state.country || d.id === 'stations');
  return `<label class="backend-select">Data source<select id="dataset">${available.map(d => `<option value="${d.id}" ${d.id === state.dataset ? 'selected' : ''}>${esc(d.label)}${d.status === 'ready' ? '' : ' · not built'}</option>`).join('')}</select></label>`;
}

function missingHTML(data) {
  return `<p class="message">${esc(data?.message || 'Saved results are not available for this selection.')}</p>${data?.build_command ? `<pre class="backend-command">${esc(data.build_command)}</pre>` : ''}`;
}

function rowsHTML(gauges) {
  return `<ul class="rows" id="river-list">${gauges.map(g => `<li><button class="row" data-river="${esc(g.id)}"><span class="row-name">${esc(riverName(g))}</span><span class="row-sub">${esc(g.place || g.name)} · ${esc(g.id)}</span></button></li>`).join('')}</ul>`;
}

function variableHTML(option) {
  const selected = String(state.options.variable).split(',');
  const check = item => `<label class="check" style="--c:${COLORS[item.id] || '#7a5aa8'}"><input type="checkbox" data-variable="${esc(item.id)}" ${selected.includes(String(item.id)) ? 'checked' : ''}><i class="swatch"></i><span>${esc(item.label)}</span></label>`;
  return [false, true].map(water => `<fieldset><p class="group-title">${water ? 'Water availability' : 'Reference'}</p>${option.values.filter(v => WATER.has(v.id) === water).map(check).join('')}</fieldset>${water ? '' : '<hr class="rule">'}`).join('');
}

function optionsHTML() {
  return (selectedView()?.options || []).filter(o => o.name !== 'year').map(option => {
    if (option.name === 'variable') return variableHTML(option);
    if (option.name === 'interval') return `<hr class="rule"><fieldset><p class="group-title">Calculation</p>${[['monthly', 'Monthly average', 'one value per month'], ['daily', 'Shortest interval', 'daily, the finest step of this dataset']].map(([id, label, hint]) => `<label class="check"><input type="radio" name="interval" value="${id}" ${state.options.interval === id ? 'checked' : ''}><span>${label}<small>${hint}</small></span></label>`).join('')}</fieldset>`;
    return `<label class="backend-select">${esc(option.label)}<select data-option="${esc(option.name)}">${option.values.map(v => `<option value="${esc(v.id)}" ${String(v.id) === String(state.options[option.name]) ? 'selected' : ''}>${esc(v.label)}</option>`).join('')}</select></label>`;
  }).join('');
}

function renderSide() {
  const side = $('#side'), data = dataset(), river = selectedRiver();
  if (!state.country) {
    side.innerHTML = `<h2>Countries</h2><p class="side-sub">Pick a country on the map or here.</p><ul class="rows">${Object.entries(geodata.countries).map(([code, country]) => {
      const saved = catalog.datasets.find(d => d.id === code.toLowerCase());
      return `<li><button class="row" data-country="${code}"><span class="row-name">${esc(country.name)}</span><span class="row-sub">${saved?.status === 'ready' ? `${saved.count} measured rivers` : 'Saved observations not built'}</span></button></li>`;
    }).join('')}</ul>`;
    return;
  }
  if (!river) {
    // CAMELS-CH includes bordering gauges; source region owns the navigation.
    const gauges = (data?.gauges || []).filter(g => data.country || !g.country || g.country === state.country);
    side.innerHTML = `<button class="link back" data-action="europe">← Europe</button><h2>${esc(countryName(state.country))}</h2>${sourceHTML()}${data?.status !== 'ready' ? missingHTML(data) : `<p class="side-sub">Pick a river on the map or here.</p><p class="group-title">${data.kind === 'model' ? 'Modelled catchments' : data.kind === 'network' ? 'Stations' : 'Measured mountain rivers'} <span class="quiet">${gauges.length}</span></p><input class="river-search" id="river-search" type="search" placeholder="Find a river or station" aria-label="Find a river or station">${rowsHTML(gauges)}`}`;
    return;
  }
  const facts = [river.area_km2 != null && `${numeric(river.area_km2)} km²`, river.elevation_m != null && `${river.elevation_statistic || 'mean'} height ${numeric(river.elevation_m)} m`].filter(Boolean);
  const views = data.views || [], scopes = [...new Set(views.map(v => v.scope))];
  side.innerHTML = `<button class="link back" data-action="rivers">← Rivers of ${esc(countryName(state.country))}</button><h2>${esc(riverName(river))}</h2><p class="side-sub">${data.kind === 'model' ? 'Model output for' : 'Station'} ${esc(river.place || river.name)}${facts.length ? ' · ' + esc(facts.join(' · ')) : ''}</p>${sourceHTML()}
    ${optionsHTML()}
    <hr class="rule"><fieldset><p class="group-title">Assessments</p>
      <label class="check"><input type="checkbox" disabled><span>Risk assessment<small>Not implemented</small></span></label>
      <label class="check"><input type="checkbox" id="statistics" ${state.statistics ? 'checked' : ''}><span>Statistics and saved records</span></label>
      <label class="check"><input type="checkbox" disabled><span>Physical models and prediction<small>Not implemented</small></span></label>
    </fieldset><hr class="rule"><label class="backend-select">Analysis<select id="view">${scopes.map(scope => `<optgroup label="${esc(SCOPES[scope] || scope)}">${views.filter(v => v.scope === scope).map(v => `<option value="${v.id}" ${v.id === state.view ? 'selected' : ''}>${esc(v.label)}</option>`).join('')}</optgroup>`).join('')}<optgroup label="Separate demonstration"><option value="__demo" ${isDemo() ? 'selected' : ''}>Synthetic 3D surface · imaginary</option></optgroup></select></label>
    <p class="backend-note">${data.kind === 'model' ? 'GLDAS is unrouted model runoff, not measured river discharge.' : 'Only saved backend results are shown.'}</p>`;
}

async function updateMap() {
  if (!map) return;
  const ticket = ++courseRequest;
  const data = dataset(), grouped = { CH: [], NO: [] };
  const sources = state.country ? [data] : catalog.datasets.filter(d => ['ch', 'no'].includes(d.id));
  for (const source of sources) for (const gauge of source?.gauges || []) {
    const region = source.country || gauge.country;
    if (grouped[region]) grouped[region].push({ ...gauge, id: String(gauge.id), name: riverName(gauge), place: gauge.place || gauge.name, measured: source.kind === 'observed' });
  }
  map.setRivers(grouped);
  map.setCourses({ type: 'FeatureCollection', features: [] });
  map.show({ country: state.country, river: state.river });
  try {
    const results = await Promise.all(sources.map(async source => {
      if (!courseCache.has(source.id)) courseCache.set(source.id, await api(`/api/courses?dataset=${encodeURIComponent(source.id)}`));
      return courseCache.get(source.id);
    }));
    if (ticket !== courseRequest) return;
    map.setCourses({ type: 'FeatureCollection', features: results.flatMap(r => r.features || []), missing: Object.assign({}, ...results.map(r => r.missing || {})) });
  } catch { /* Gauge locations and the station list stay available without river geometry. */ }
}

function renderTimeline() {
  const years = dataset()?.years || [];
  const selectable = selectedView()?.options.some(o => o.name === 'year') && !isDemo();
  if (!years.length || isDemo()) { $('#timeline').innerHTML = '<p class="quiet">Synthetic demonstration only · no river record or prediction</p>'; return; }
  if (selectedView()?.scope === 'sources') {
    $('#timeline').innerHTML = '<p class="quiet">Observed / GLDAS comparison · common saved coverage is reported with the chart</p>';
    return;
  }
  const first = years[0], last = years.at(-1);
  const calendar = state.dataset === 'stations' ? 'calendar years' : 'hydrological years';
  if (!selectable) { $('#timeline').innerHTML = `<div class="timeline-year">${first}–${last}</div><p class="quiet">Saved ${calendar} · this analysis uses the full saved record</p>`; return; }
  const startMonth = dataset()?.settings?.hydro_year_start_month;
  const start = startMonth ? ` · starts in ${new Intl.DateTimeFormat('en', { month: 'long', timeZone: 'UTC' }).format(new Date(Date.UTC(2000, startMonth - 1, 1)))}` : '';
  $('#timeline').innerHTML = `<div class="timeline-year" id="timeline-year">${esc(state.options.year)}</div><div class="timeline-track" style="--track:#555c58"><input type="range" id="year-range" min="0" max="${years.length - 1}" step="1" value="${Math.max(0, years.indexOf(Number(state.options.year)))}" aria-label="Hydrological year"><span class="tick first" style="left:0">${first}</span><span class="tick last" style="left:100%">latest data ${last}</span></div><p class="quiet">${calendar}${start}</p>`;
}

function resultsShell() {
  const river = selectedRiver(), spec = selectedView();
  const riverScope = spec?.scope === 'catchment' || spec?.id === 'source_regime';
  const heading = isDemo() ? 'Synthetic 3D surface' : riverScope ? `${esc(riverName(river))}${river?.place ? ` <small>at ${esc(river.place)}</small>` : ''}` : esc(spec?.scope === 'stations' ? 'Station network' : countryName(state.country));
  $('#results').innerHTML = `<header class="results-head"><div><h2>${heading}</h2><p class="results-meta" id="results-meta">${esc(dataset()?.label)} · ${esc(SCOPES[spec?.scope] || 'Synthetic demonstration')}</p></div><div class="head-actions"><button class="link" data-action="expand">${state.expanded ? 'Show the map' : 'Expand'}</button></div></header>
    <div class="results-scroll"><figure class="graph${state.full ? ' full' : ''}" id="graph"><div class="graph-title">${esc(spec?.label || 'Synthetic 3D surface')}</div><p class="message" id="figure-status">Reading the saved river record…</p><div class="chart backend-chart" id="chart" hidden></div><div class="graph-foot"><span>${['timeseries', 'hydrograph_vs_history'].includes(state.view) ? `<label><input type="checkbox" id="usual" ${state.view === 'hydrograph_vs_history' ? 'checked' : ''}> Compare discharge with a usual year</label>` : esc(spec?.label || 'Synthetic demonstration')}</span><button class="link" data-action="full">${state.full ? 'Close full screen' : 'Full screen'}</button></div></figure><div id="figure-notes"></div><section class="block" id="records" ${state.statistics && !isDemo() ? '' : 'hidden'}><h3>Statistics and saved records</h3><p class="backend-note" id="row-count"></p><button class="link" id="download" disabled>Download CSV</button><div class="table-scroll backend-table" id="table-wrap"></div><div class="backend-pagination" id="pagination"></div></section></div>`;
}

async function drawFigure(figure) {
  if (!window.Plotly) throw new Error('The chart library could not be loaded. Please reload the window.');
  const layout = { ...(figure.layout || {}), autosize: true, paper_bgcolor: '#fdfcfa', plot_bgcolor: '#fdfcfa', font: { ...(figure.layout?.font || {}), family: 'Segoe UI, system-ui, sans-serif', color: '#555c58' } };
  // Match Claude's variable swatches without changing any backend values or units.
  const variables = String(state.options.variable || '').split(',');
  const traces = (figure.data || []).map((trace, i) => {
    if (state.view !== 'timeseries') return trace;
    const color = COLORS[variables[i]] || '#7a5aa8';
    const axisName = i === 0 ? 'yaxis' : `yaxis${i + 1}`;
    const axis = layout[axisName] || {};
    layout[axisName] = { ...axis, title: { ...axis.title, font: { ...axis.title?.font, color } }, tickfont: { ...axis.tickfont, color } };
    return { ...trace, line: { ...trace.line, color }, marker: { ...trace.marker, color } };
  });
  delete layout.width;
  const height = Number(figure.layout?.height) || 330;
  layout.height = state.full ? Math.max(260, innerHeight - 125) : Math.max(state.expanded ? 440 : 330, height);
  $('#figure-status').hidden = true;
  const chart = $('#chart'); chart.hidden = false;
  await Plotly.react(chart, traces, layout, { responsive: true, displaylogo: false, displayModeBar: false, scrollZoom: false });
}

function showUnavailable(payload) {
  $('#chart').hidden = true;
  $('#figure-status').hidden = false;
  $('#figure-status').innerHTML = `${esc(payload.message || 'This analysis is unavailable.')}${payload.build_command ? `<pre class="backend-command">${esc(payload.build_command)}</pre>` : ''}`;
}

async function refreshView() {
  if (!state.river || (!selectedView() && !isDemo())) return;
  const ticket = ++requestNumber;
  controller?.abort(); controller = new AbortController();
  answer = null; tableData = null; page = 0;
  resultsShell(); remember();
  if (isDemo()) {
    $('#results-meta').textContent = 'IMAGINARY DATA · isolated visual demonstration';
    $('#figure-notes').innerHTML = '<p class="note-imaginary"><b>IMAGINARY DATA — VISUAL DEMONSTRATION ONLY.</b> No river, measurement, forecast or risk assessment is represented. Drag to rotate.</p>';
    answer = { figure: demoFigure() };
    try { await drawFigure(answer.figure); } catch (error) { showUnavailable({ message: error.message }); }
    return;
  }
  const params = parameters(), tables = new URLSearchParams(params);
  tables.set('table', selectedView().table);
  const options = { signal: controller.signal };
  await Promise.allSettled([
    api(`/api/figure?${params}`, options).then(async payload => {
      if (ticket !== requestNumber) return;
      if (payload.status !== 'ready' || !payload.figure) { showUnavailable(payload); return; }
      answer = payload;
      const context = payload.context || {};
      $('#results-meta').textContent = [context.source, context.period && `${context.period} · ${context.calendar || 'saved years'}`].filter(Boolean).join(' · ');
      $('#figure-notes').innerHTML = (payload.notes || []).map(note => `<p class="backend-note">${esc(note)}</p>`).join('');
      await drawFigure(payload.figure);
    }).catch(error => { if (ticket === requestNumber && error.name !== 'AbortError') showUnavailable({ message: error.message }); }),
    api(`/api/table?${tables}`, options).then(payload => {
      if (ticket !== requestNumber) return;
      if (payload.status !== 'ready') { $('#row-count').textContent = payload.message || 'No saved records are available.'; return; }
      tableData = payload; renderTable();
    }).catch(error => { if (ticket === requestNumber && error.name !== 'AbortError') $('#row-count').textContent = error.message; }),
  ]);
}

function renderTable() {
  if (!tableData) return;
  const rows = tableData.rows || [], columns = tableData.columns || [], pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  page = Math.max(0, Math.min(page, pages - 1));
  const total = tableData.total_rows || rows.length;
  $('#row-count').textContent = `${rows.length.toLocaleString()} records${total > rows.length ? ` shown of ${total.toLocaleString()}` : ''} · missing values shown as —`;
  $('#download').disabled = !rows.length;
  $('#table-wrap').innerHTML = `<table class="plain"><caption>${esc(selectedView()?.label)} · ${esc(dataset()?.label)}</caption><thead><tr>${columns.map(c => `<th scope="col">${esc(c)}</th>`).join('')}</tr></thead><tbody>${rows.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE).map(row => `<tr>${columns.map((c, i) => { const v = Array.isArray(row) ? row[i] : row[c]; return `<td>${esc(v == null ? '—' : typeof v === 'number' ? numeric(v) : typeof v === 'object' ? JSON.stringify(v) : v)}</td>`; }).join('')}</tr>`).join('')}</tbody></table>`;
  $('#pagination').innerHTML = pages > 1 ? `<button class="link" data-action="previous" ${page === 0 ? 'disabled' : ''}>Previous</button><span>Page ${page + 1} / ${pages}</span><button class="link" data-action="next" ${page === pages - 1 ? 'disabled' : ''}>Next</button>` : '';
}

function downloadCSV() {
  if (!tableData) return;
  const field = value => { let text = value == null ? '' : typeof value === 'object' ? JSON.stringify(value) : String(value); if (typeof value === 'string' && /^[=+\-@\t\r]/.test(text)) text = `'${text}`; return `"${text.replaceAll('"', '""')}"`; };
  const lines = [tableData.columns.map(field).join(','), ...tableData.rows.map(row => tableData.columns.map((c, i) => field(Array.isArray(row) ? row[i] : row[c])).join(','))];
  const url = URL.createObjectURL(new Blob(['\uFEFF' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8' }));
  const link = document.createElement('a'); link.href = url; link.download = `rivascope-${state.dataset}-${selectedView()?.table || state.view}.csv`; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function demoFigure() {
  const x = Array.from({ length: 35 }, (_, i) => -20 + i * 40 / 34), y = Array.from({ length: 35 }, (_, i) => -30 + i * 60 / 34);
  const z = y.map(b => x.map(a => 8 + .008 * a * a + .005 * b * b + 11 * Math.exp(-((a - 5) ** 2 / 120 + (b + 8) ** 2 / 180)) + 2.2 * Math.sin(a / 8) * Math.cos(b / 11)));
  return { data: [{ type: 'surface', x, y, z, colorscale: [[0, '#dbe8ef'], [.4, '#76a3bb'], [.7, '#306d93'], [1, '#17394f']], colorbar: { title: { text: 'Imaginary<br>variation (%)' }, thickness: 12 }, contours: { z: { show: true, usecolormap: true, project: { z: true } } }, hovertemplate: 'Imaginary timing: %{x:.1f} d<br>Imaginary quantity: %{y:.1f}%<br>Imaginary variation: %{z:.1f}%<extra>DEMONSTRATION</extra>' }], layout: { height: 440, margin: { l: 10, r: 65, t: 20, b: 20 }, scene: { xaxis: { title: { text: 'Timing shift (imaginary days)' } }, yaxis: { title: { text: 'Quantity change (imaginary %)' } }, zaxis: { title: { text: 'Variation (imaginary %)' } }, camera: { eye: { x: 1.6, y: -1.6, z: 1.1 } }, aspectratio: { x: 1.2, y: 1.2, z: .7 } } } };
}

async function reloadSaved() {
  clearTimeout(yearTimer);
  const button = $('[data-action="refresh"]'); button.disabled = true; button.textContent = 'Reading saved results…';
  ++requestNumber; controller?.abort(); tableData = null; answer = null;
  if (state.river) resultsShell();
  try { catalog = await api('/api/refresh', { method: 'POST' }); courseCache.clear(); normalize(); $('#about-body').innerHTML = aboutHTML(); render(); }
  catch (error) { if (state.river) showUnavailable({ message: error.message }); else $('#side').insertAdjacentHTML('beforeend', `<p class="message">${esc(error.message)}</p>`); }
  finally { button.disabled = false; button.textContent = 'Reload saved results'; }
}

document.addEventListener('click', event => {
  if (event.target.closest('#download')) { downloadCSV(); return; }
  const target = event.target.closest('[data-action], [data-country], [data-river], [data-occupation]');
  if (!target) return;
  if (target.dataset.occupation) { state.occupation = target.dataset.occupation; openApp(); }
  else if (target.dataset.country) go({ country: target.dataset.country, river: null, dataset: target.dataset.country.toLowerCase() });
  else if (target.dataset.river) go({ river: target.dataset.river });
  else if (target.dataset.action === 'europe') go({ country: null, river: null });
  else if (target.dataset.action === 'rivers') go({ river: null });
  else if (target.dataset.action === 'about') $('#about').showModal();
  else if (target.dataset.action === 'refresh') reloadSaved();
  else if (target.dataset.action === 'retry') start();
  else if (target.dataset.action === 'expand') { state.expanded = !state.expanded; $('#layout').classList.toggle('expanded', state.expanded); target.textContent = state.expanded ? 'Show the map' : 'Expand'; remember(); }
  else if (target.dataset.action === 'full') { state.full = !state.full; $('#graph').classList.toggle('full', state.full); target.textContent = state.full ? 'Close full screen' : 'Full screen'; if (answer?.figure) drawFigure(answer.figure); }
  else if (target.dataset.action === 'previous') { page--; renderTable(); }
  else if (target.dataset.action === 'next') { page++; renderTable(); }
});

document.addEventListener('change', event => {
  const input = event.target;
  if (input.id === 'occupation-select') { state.occupation = input.value; remember(); return; }
  if (input.id === 'dataset') { go({ dataset: input.value, river: null }); return; }
  if (input.id === 'statistics') { state.statistics = input.checked; $('#records').hidden = !state.statistics || isDemo(); remember(); return; }
  if (input.id === 'view' || input.id === 'usual') { state.view = input.id === 'view' ? input.value : input.checked ? 'hydrograph_vs_history' : 'timeseries'; normalize(); renderSide(); renderTimeline(); refreshView(); return; }
  if (input.dataset.variable) {
    const chosen = [...document.querySelectorAll('[data-variable]:checked')];
    if (!chosen.length || chosen.length > 4) { input.checked = !input.checked; return; }
    state.options.variable = chosen.map(node => node.dataset.variable).join(',');
  } else if (input.name === 'interval') state.options.interval = input.value;
  else if (input.dataset.option) state.options[input.dataset.option] = input.value;
  else return;
  refreshView();
});

document.addEventListener('input', event => {
  if (event.target.id === 'river-search') {
    const query = event.target.value.trim().toLowerCase();
    for (const row of document.querySelectorAll('#river-list li')) row.hidden = !row.textContent.toLowerCase().includes(query);
  }
  if (event.target.id !== 'year-range') return;
  state.options.year = String(dataset().years[Number(event.target.value)]);
  $('#timeline-year').textContent = state.options.year;
  clearTimeout(yearTimer); yearTimer = setTimeout(refreshView, 110);
});

document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && state.full) { state.full = false; $('#graph').classList.remove('full'); $('[data-action="full"]').textContent = 'Full screen'; if (answer?.figure) drawFigure(answer.figure); }
});

// Preserve Claude's draggable map/results divider.
{
  const grip = $('#grip'), layout = $('#layout');
  grip.addEventListener('pointerdown', event => { grip.setPointerCapture(event.pointerId); grip.classList.add('dragging'); });
  grip.addEventListener('pointermove', event => {
    if (!grip.classList.contains('dragging')) return;
    const left = $('.mapwrap').getBoundingClientRect().left;
    const most = layout.getBoundingClientRect().right - left - 420;
    layout.style.setProperty('--map-w', `${Math.max(240, Math.min(most, event.clientX - left))}px`);
  });
  for (const name of ['pointerup', 'pointercancel']) grip.addEventListener(name, () => grip.classList.remove('dragging'));
}

new ResizeObserver(() => {
  clearTimeout(drawTimer);
  drawTimer = setTimeout(() => { const chart = $('#chart'); if (chart && !chart.hidden && chart.data && window.Plotly) Plotly.Plots.resize(chart).catch(() => {}); }, 80);
}).observe($('#results'));
window.addEventListener('pagehide', () => navigator.sendBeacon('/api/bye'));
start();
