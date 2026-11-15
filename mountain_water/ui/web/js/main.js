// RivaScope front end. Map-first navigation over the team's saved trend results.
// Every number and figure comes from /api (mountain_water.ui.backend, which calls the trend
// section). Nothing is generated here: no observations, forecasts, thresholds or scores.
import { createMap } from './map.js';

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const STORE = 'rivascope-v4';
const PAGE_SIZE = 40;
const FONT = "Bahnschrift, 'DIN Alternate', 'Helvetica Neue', Arial, sans-serif";
const INK = '#0a0a0a', MID = '#6f6f6b', GRID = '#e3e3df', ORANGE = '#ff4f00';

// Risk assessment: three headline trends, then the saved yearly indicators the chosen occupation
// reads first (rows of the backend's trend table). Only a selection of saved rows: no requirement,
// threshold or score is attached to an occupation.
const HEADLINE = [['Quantity', 'volume_hm3'], ['Timing', 'half_volume_doy'], ['Variability', 'cv_daily']];
const OCCUPATIONS = [
  { id: 'hydropower', label: 'Hydropower', metrics: ['volume_hm3', 'winter_mean_flow', 'summer_mean_flow', 'half_volume_doy', 'cv_daily'] },
  { id: 'data_center', label: 'Data center infrastructure', metrics: ['min7_flow', 'q95_low', 'days_below_q347', 'low_flow_doy', 'temp_summer'] },
  { id: 'power_plant', label: 'Power plant', metrics: ['summer_mean_flow', 'min7_flow', 'q95_low', 'days_below_q347', 'temp_summer'] },
  { id: 'government', label: 'Government official', metrics: ['volume_hm3', 'days_below_q347', 'half_volume_doy', 'precip_total_mm', 'swe_max_mm'] },
  { id: 'defence', label: 'Defence', metrics: ['min7_flow', 'days_below_q347', 'peak_flow', 'q10_high', 'flashiness'] },
];
const OCCUPATION_KEY = 'rivascope-occupation';   // the choice made on the first screen, kept between sessions

// Assessments (left box). Each ticked one adds its blocks under the shared graph.
const SECTIONS = [
  { id: 'risk', label: 'Risk assessment', blocks: [{ id: 'headline', kind: 'headline' }, { view: 'flow_surface' }] },
  { id: 'statistics', label: 'Statistics', blocks: [{ view: 'annual_metric' }, { view: 'window_means' }] },
  { id: 'regime', label: 'Seasonal regime', blocks: [{ view: 'hydrograph_vs_history' }, { view: 'regime_by_window' }, { view: 'daily_heatmap' }] },
  { id: 'drivers', label: 'Drivers', blocks: [{ view: 'correlation_matrix' }, { view: 'driver_scatter' }] },
];
const REGION_VIEWS = ['trend_heatmap', 'window_change_heatmap', 'trend_vs_attribute', 'attribution_bars', 'selection_summary'];
const STATION_VIEWS = ['station_month_heatmap', 'station_year_heatmaps', 'driver_change_scatter'];
const TITLES = {
  timeseries: 'Time series', hydrograph_vs_history: 'Year against history', regime_by_window: 'Regime by 10-year window',
  annual_metric: 'Annual metric and trend', daily_heatmap: 'Daily flow, all years', window_means: '10-year window means',
  correlation_matrix: 'Driver correlations', driver_scatter: 'Flow against driver', flow_surface: 'Flow surface',
  trend_heatmap: 'Trends', window_change_heatmap: 'Window change', trend_vs_attribute: 'Trend / attribute',
  attribution_bars: 'Attribution', selection_summary: 'Selection',
  station_month_heatmap: 'Stations / month', station_year_heatmaps: 'Stations / year', driver_change_scatter: 'Station drivers',
};
const HEIGHT = { timeseries: 390, hydrograph_vs_history: 360, regime_by_window: 360, annual_metric: 340, window_means: 320,
  daily_heatmap: 440, correlation_matrix: 460, driver_scatter: 360, trend_vs_attribute: 400, attribution_bars: 420, selection_summary: 320 };
// Figures that cannot be squeezed: below this width their box scrolls sideways instead.
const MIN_WIDTH = { station_month_heatmap: 1400, station_year_heatmaps: 1400, trend_heatmap: 720, window_change_heatmap: 720, correlation_matrix: 560 };
const SERIES = {
  discharge_vol: INK, discharge_spec: '#00875a', waterlevel: '#7b7b77', runoff_surface: '#3f8f6f', runoff_base: '#8fb9a6',
  temperature_mean: ORANGE, temperature_min: '#ff9d70', temperature_max: '#b73800', precipitation: '#1f6fe0',
  swe: '#22b3c7', rel_sun_dur: '#c9a100', evap: '#9c5a00', snowmelt: '#5fc7d6', snowfall: '#8aa6c9',
};
const WATER = new Set(['discharge_vol', 'discharge_spec', 'waterlevel', 'runoff_surface', 'runoff_base']);

const state = {
  occupation: null, country: null, river: null, dataset: 'ch', year: null, interval: 'monthly',
  variables: ['temperature_mean', 'discharge_vol'], sections: ['risk', 'statistics'], opts: {}, region: null, expanded: false,
};
let catalog, geodata, map, courseRequest = 0, yearTimer = null, resizeTimer = null, fullId = null;
const courseCache = new Map();
const live = new Map(); // block id -> block currently on screen

// ---------------------------------------------------------------- helpers
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const unit = text => String(text || '').replace('m3/s', 'm³/s').replace('degC', '°C').replace('km2', 'km²').replace(/^-$/, '');
const splitLabel = label => { const m = /^(.*?)\s*\[(.*)\]\s*$/.exec(String(label)); return m ? [m[1], unit(m[2])] : [String(label), '']; };
const finite = value => value != null && Number.isFinite(Number(value));
const digits = (value, places = 1) => Number(value).toLocaleString('en-GB', { minimumFractionDigits: places, maximumFractionDigits: places });
const significant = value => finite(value) ? Number(value).toLocaleString('en-GB', { maximumSignificantDigits: 3 }) : '—';
const signed = (value, places = 1) => !finite(value) ? '—' : (value > 0 ? '+' : value < 0 ? '−' : '') + digits(Math.abs(value), places);
const pValue = p => !finite(p) ? '—' : p < 0.001 ? '<0.001' : Number(p).toFixed(3);
const ds = (id = state.dataset) => catalog?.datasets.find(d => d.id === id);
const spec = (view, id = state.dataset) => ds(id)?.views.find(v => v.id === view);
const gauge = () => ds()?.gauges.find(g => String(g.id) === String(state.river));
const countryName = code => geodata.countries[code]?.name || code;
const riverName = g => g?.river || g?.name || g?.id || '';
const occupation = () => OCCUPATIONS.find(o => o.id === state.occupation) || OCCUPATIONS[0];
const metricInfo = id => { const m = ds()?.metrics?.find(x => x.id === id); const [name, u] = splitLabel(m?.label || id); return { name, unit: u }; };
const variableName = id => splitLabel((spec('timeseries')?.options.find(o => o.name === 'variable')?.values || []).find(v => String(v.id) === id)?.label || id)[0];
const period = d => d?.years?.length ? `${d.years[0]}–${d.years.at(-1)}` : '';

async function api(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || payload.message || `Request failed (${response.status}).`);
  return payload;
}

// ---------------------------------------------------------------- state
function recall() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORE));
    if (saved && typeof saved === 'object') {
      if (typeof saved.interval === 'string') state.interval = saved.interval;
      for (const key of ['variables', 'sections']) if (Array.isArray(saved[key])) state[key] = saved[key].map(String);
      if (saved.opts && typeof saved.opts === 'object') state.opts = saved.opts;
    }
    state.occupation = localStorage.getItem(OCCUPATION_KEY);
  } catch { /* Storage is optional. */ }
  const link = new URLSearchParams(location.hash.slice(1));
  state.occupation = link.get('o') || state.occupation;
  if (!OCCUPATIONS.some(o => o.id === state.occupation)) state.occupation = null;
  state.country = link.get('c');
  state.river = link.get('r');
  if (link.get('d')) state.dataset = link.get('d'); else if (state.country) state.dataset = state.country.toLowerCase();
  if (link.has('y')) state.year = link.get('y');
  if (link.has('m')) state.interval = link.get('m');
  if (link.has('v')) state.variables = link.get('v').split(',').filter(Boolean);
  if (link.has('s')) state.sections = link.get('s').split(',').filter(Boolean);
  if (link.has('g')) state.region = link.get('g');
  state.expanded = link.get('x') === '1';
  for (const key of ['metric', 'driver', 'attribute', 'kind', 'normalized', 'log_scale', 'pair']) if (link.has(key)) state.opts[key] = link.get(key);
  if (state.river?.startsWith('ch-')) state.river = state.river.slice(3); // links from the first version
}

function remember() {
  try {
    localStorage.setItem(STORE, JSON.stringify({ interval: state.interval, variables: state.variables, sections: state.sections, opts: state.opts }));
  } catch { /* Storage is optional. */ }
  const entries = { o: state.occupation, c: state.country, r: state.river, d: state.dataset, y: state.river ? state.year : '',
    m: state.interval, v: state.variables.join(','), s: state.sections.join(','), g: state.river ? '' : state.region,
    x: state.expanded ? '1' : '', ...state.opts };
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(entries)) if (value != null && value !== '') params.set(key, String(value));
  history.replaceState(null, '', `#${params}`);
}

function optionValues(name) {
  for (const id of [state.dataset, 'stations']) for (const view of ds(id)?.views || []) {
    const option = view.options.find(o => o.name === name);
    if (option) return option.values.map(v => String(v.id));
  }
  return [];
}

function normalize() {
  if (!geodata.countries[state.country]) state.country = null;
  if (!state.country) { state.river = null; state.expanded = false; return; }
  const own = catalog.datasets.filter(d => d.country === state.country);
  if (!own.some(d => d.id === state.dataset)) state.dataset = state.country.toLowerCase();
  if (state.river && !gauge()) state.river = null;
  const years = ds()?.years || [];
  if (!years.includes(Number(state.year))) state.year = years.at(-1) ?? null;
  const variables = optionValues('variable');
  state.variables = variables.filter(v => state.variables.includes(v)).slice(0, 4);   // always in the backend's order
  if (!state.variables.length) state.variables = variables.filter(v => ['temperature_mean', 'discharge_vol'].includes(v));
  if (!state.variables.length) state.variables = variables.slice(0, 1);
  if (!['monthly', 'daily'].includes(state.interval)) state.interval = 'monthly';
  state.sections = state.sections.filter(id => SECTIONS.some(s => s.id === id));
  const preferred = { metric: 'volume_hm3', driver: 'precip_total_mm', attribute: 'elevation', kind: 'volume', normalized: 'false', log_scale: 'true', pair: 'snow' };
  for (const name of Object.keys(preferred)) {
    const values = optionValues(name);
    if (!values.length) { delete state.opts[name]; continue; }
    if (!values.includes(String(state.opts[name]))) state.opts[name] = values.includes(preferred[name]) ? preferred[name] : values[0];
  }
  const tabs = regionTabs();
  if (!tabs.some(t => t.view === state.region)) state.region = tabs[0]?.view || null;
  if (!state.river && !tabs.length) state.expanded = false;
}

// The country-level analyses: comparisons across the saved catchments, and the station network.
function regionTabs() {
  const tabs = [];
  if (ds()?.status === 'ready') for (const view of REGION_VIEWS) if (spec(view)) tabs.push({ view, dataset: state.dataset });
  const network = ds('stations');
  if (ds()?.kind === 'observed' && network?.status === 'ready' && network.gauges.some(g => g.country === state.country)) {
    for (const view of STATION_VIEWS) if (spec(view, 'stations')) tabs.push({ view, dataset: 'stations' });
  }
  return tabs;
}

function params(block) {
  const id = block.dataset || state.dataset;
  const query = new URLSearchParams({ dataset: id, view: block.view });
  if (id !== 'stations' && state.river) query.set('gauge', state.river);
  for (const option of spec(block.view, id)?.options || []) {
    const value = option.name === 'year' ? state.year : option.name === 'variable' ? state.variables.join(',')
      : option.name === 'interval' ? state.interval : state.opts[option.name];
    if (value != null) query.set(option.name, value);
  }
  return query;
}

// ---------------------------------------------------------------- start
async function start() {
  const began = performance.now();
  try {
    [catalog, geodata] = await Promise.all([api('/api/catalog'), api('data/geodata.json')]);
  } catch (error) {
    $('#splash-status').innerHTML = `Could not start. ${esc(error.message)} <button data-action="retry">Retry</button>`;
    return;
  }
  recall();
  $('#about-body').innerHTML = aboutHTML();
  $('#choices').innerHTML = OCCUPATIONS.map((o, i) => `<li><button data-occupation="${o.id}"><span class="n">${String(i + 1).padStart(2, '0')}</span><span class="name">${esc(o.label)}</span><span class="ind">${o.metrics.map(m => esc(metricInfo(m).name)).join(' · ')}</span></button></li>`).join('');
  $('#occupation-select').innerHTML = OCCUPATIONS.map(o => `<option value="${o.id}">${esc(o.label)}</option>`).join('');
  $('#pick-data').textContent = catalog.datasets.filter(d => d.kind === 'observed').map(d => `${d.label}: ${d.status === 'ready' ? `${d.count} rivers, ${period(d)}` : 'not built'}`).join('  ·  ');
  // A link to a place opens the app directly; the occupation can be set in the bar above.
  const linked = location.hash.length > 1;
  if (!state.occupation && linked) state.occupation = OCCUPATIONS[0].id;
  // The loading screen stays long enough to be seen. The occupation menu follows it the first
  // time; afterwards the saved choice is used and the map opens directly.
  setTimeout(() => {
    $('#splash')?.remove();
    if (state.occupation) openApp(); else $('#occupation').hidden = false;
  }, linked ? 0 : Math.max(0, 1200 - (performance.now() - began)));
}

function chooseOccupation(id) {
  if (!OCCUPATIONS.some(o => o.id === id)) return;
  state.occupation = id;
  try { localStorage.setItem(OCCUPATION_KEY, id); } catch { /* Storage is optional. */ }
}

function aboutHTML() {
  const row = d => `<tr><td>${esc(d.label)}</td><td class="${d.status === 'ready' ? 'ok' : 'na'}">${d.status === 'ready' ? 'Ready' : d.status === 'error' ? 'Unreadable' : 'Not built'}</td><td>${d.status === 'ready' ? `${d.count} gauges${period(d) ? ` · ${period(d)}` : ''}` : `<code>${esc(d.build_command)}</code>`}</td></tr>`;
  return `<table><thead><tr><th>Saved results</th><th>State</th><th>Content / build command</th></tr></thead><tbody>${catalog.datasets.map(row).join('')}</tbody></table>
    <p>Saved results of the trend section are read from this computer. Nothing is downloaded or built here. Missing observations stay missing. The trend section interpolates gaps of up to 5 days before computing its yearly statistics and flags those days; the time series and the flow surface leave them out. GLDAS is model output, not measured discharge. Trends are statistical associations, not causes. No forecast model is connected.</p>
    <p>Imagery and names: Esri. Country outlines: Natural Earth. River segments: © OpenStreetMap contributors.</p>
    <button data-action="refresh">Reload saved results</button>`;
}

function openApp() {
  $('#occupation').hidden = true;
  $('#app').hidden = false;
  $('#occupation-select').value = occupation().id;
  if (!map) map = createMap($('#map'), geodata, {
    country: code => go({ country: code, river: null, dataset: code.toLowerCase() }),
    river: id => go({ river: String(id) }),
    europe: () => go({ country: null, river: null }),
  });
  render();
}

function go(changes) {
  clearTimeout(yearTimer);
  if ('river' in changes && !changes.river) state.expanded = false;
  Object.assign(state, changes);
  render();
}

function render() {
  normalize();
  const hasResults = Boolean(state.river) || (Boolean(state.country) && regionTabs().length > 0);
  const layout = $('#layout');
  layout.classList.toggle('has-results', hasResults);
  layout.classList.toggle('has-time', Boolean(state.river));
  layout.classList.toggle('expanded', hasResults && state.expanded);
  renderCrumbs(); renderSide(); renderTimeline(); renderResults(); updateMap(); remember();
}

function renderCrumbs() {
  const parts = [state.country ? '<button data-action="europe">Europe</button>' : '<b>Europe</b>'];
  if (state.country) parts.push(state.river ? `<button data-action="rivers">${esc(countryName(state.country))}</button>` : `<b>${esc(countryName(state.country))}</b>`);
  if (state.river) parts.push(`<b>${esc(riverName(gauge()))}</b>`);
  $('#crumbs').innerHTML = parts.join('<i>/</i>');
}

// ---------------------------------------------------------------- left box
function checkHTML(kind, id, label, on, color, note = '') {
  return `<label class="check"${color ? ` style="--c:${color}"` : ''}><input type="checkbox" data-${kind}="${esc(id)}" ${on ? 'checked' : ''}><i></i><span>${esc(label)}</span><em>${esc(note)}</em></label>`;
}

function renderSide() {
  const side = $('#side'), data = ds();
  if (!state.country) {
    side.innerHTML = `<div class="side-head"><small>Region</small><h2>Europe</h2></div><ul class="rows">${Object.entries(geodata.countries).map(([code, country]) => {
      const saved = ds(code.toLowerCase());
      return `<li><button data-country="${code}"><b>${esc(country.name)}</b><span>${saved?.status === 'ready' ? `${saved.count} rivers · ${period(saved)}` : 'Not built'}</span></button></li>`;
    }).join('')}</ul>`;
    return;
  }
  const sources = catalog.datasets.filter(d => d.country === state.country);
  const sourceHTML = sources.some(d => d.status === 'ready' && d.id !== state.dataset)
    ? `<label class="pickbox">Source<select id="dataset">${sources.map(d => `<option value="${d.id}" ${d.id === state.dataset ? 'selected' : ''} ${d.status === 'ready' ? '' : 'disabled'}>${esc(d.label)}</option>`).join('')}</select></label>` : '';
  const river = gauge();
  if (!river) {
    const head = `<div class="side-head"><button class="back" data-action="europe">← Europe</button><h2>${esc(countryName(state.country))}</h2>`;
    if (data?.status !== 'ready') {
      side.innerHTML = `${head}<small>${esc(data?.label || '')}</small></div>${sourceHTML}<div class="na-box"><b>${data?.status === 'error' ? 'Unreadable' : 'Not built'}</b><code>${esc(data?.build_command || '')}</code></div>`;
      return;
    }
    side.innerHTML = `${head}<small>${esc(data.label)} · ${data.count} rivers · ${period(data)}</small></div>${sourceHTML}
      <input class="filter" id="filter" type="search" placeholder="Filter" aria-label="Filter rivers">
      <ul class="rows" id="river-list">${data.gauges.map(g => `<li><button data-river="${esc(g.id)}"><b>${esc(riverName(g))}</b><span>${esc(g.place || g.name)} · ${esc(g.id)}</span>${finite(g.elevation_m) ? `<em>${Math.round(g.elevation_m)} m</em>` : ''}</button></li>`).join('')}</ul>`;
    return;
  }
  const facts = [river.place || river.name, river.id, finite(river.elevation_m) && `${Math.round(river.elevation_m)} m`, finite(river.area_km2) && `${significant(river.area_km2)} km²`].filter(Boolean);
  const variables = spec('timeseries')?.options.find(o => o.name === 'variable')?.values || [];
  const group = water => variables.filter(v => WATER.has(v.id) === water).map(v => {
    const [name, u] = splitLabel(v.label);
    return checkHTML('variable', v.id, name, state.variables.includes(String(v.id)), SERIES[v.id] || MID, u);
  }).join('');
  side.innerHTML = `<div class="side-head"><button class="back" data-action="rivers">← ${esc(countryName(state.country))}</button><h2>${esc(riverName(river))}</h2><small>${esc(facts.join(' · '))}</small></div>${sourceHTML}
    <fieldset class="grp"><legend><i>01</i>Reference</legend>${group(false)}</fieldset>
    <fieldset class="grp"><legend><i>02</i>Water availability</legend>${group(true)}</fieldset>
    <fieldset class="grp"><legend><i>03</i>Assessment</legend>${SECTIONS.map(s => checkHTML('section', s.id, s.label, state.sections.includes(s.id), '')).join('')}</fieldset>
    <fieldset class="grp"><legend><i>04</i>Calculation</legend><div class="seg">${[['monthly', 'Monthly avg.'], ['daily', 'Daily']].map(([id, label]) => `<button data-interval="${id}" class="${state.interval === id ? 'on' : ''}">${label}</button>`).join('')}</div></fieldset>`;
}

// ---------------------------------------------------------------- map
async function updateMap() {
  if (!map) return;
  const ticket = ++courseRequest;
  const grouped = { CH: [], NO: [] };
  const sources = state.country ? [ds()] : catalog.datasets.filter(d => d.kind === 'observed');
  for (const source of sources) for (const g of source?.gauges || []) {
    const region = source.country || g.country;
    if (grouped[region]) grouped[region].push({ ...g, id: String(g.id), name: riverName(g), place: g.place || g.name });
  }
  map.setRivers(grouped);
  map.show({ country: state.country, river: state.river });
  try {
    const answers = await Promise.all(sources.filter(Boolean).map(async source => {
      if (!courseCache.has(source.id)) courseCache.set(source.id, await api(`/api/courses?dataset=${encodeURIComponent(source.id)}`));
      return courseCache.get(source.id);
    }));
    if (ticket === courseRequest) map.setCourses({ type: 'FeatureCollection', features: answers.flatMap(a => a.features || []) });
  } catch { /* Gauge points stay usable without river lines. */ }
}

// ---------------------------------------------------------------- timeline
function renderTimeline() {
  const years = ds()?.years || [], element = $('#timeline');
  if (!state.river || !years.length) { element.innerHTML = ''; return; }
  const first = years[0], last = years.at(-1);
  element.innerHTML = `<div class="tl"><div class="yr"><small><span class="long">Hydrological year</span><span class="short">Hydr. year</span></small><b id="yr">${esc(state.year)}</b></div>
    <div class="track" id="track" tabindex="0" role="slider" aria-label="Hydrological year" aria-valuemin="${first}" aria-valuemax="${last}" aria-valuenow="${esc(state.year)}">
      ${years.map(y => `<i class="y${y % 5 === 0 ? ' major' : ''}${y === Number(state.year) ? ' on' : ''}" data-y="${y}">${y % 10 === 0 ? `<span class="${y % 20 === 0 ? 'd20' : ''}">${y}</span>` : ''}</i>`).join('')}
    </div>
    <div class="fc" title="No forecast model is connected"><b>${last + 1}</b><small>Forecast<br>no model</small></div></div>`;
}

function setYear(year) {
  if (!finite(year) || Number(year) === Number(state.year)) return;
  state.year = Number(year);
  $('#yr').textContent = state.year;
  $('#track').setAttribute('aria-valuenow', state.year);
  for (const cell of $$('#track .y')) cell.classList.toggle('on', Number(cell.dataset.y) === state.year);
  clearTimeout(yearTimer);
  yearTimer = setTimeout(() => { reload(b => usesOption(b, 'year')); remember(); }, 140);
}

function yearAt(clientX) {
  const cells = $$('#track .y');
  if (!cells.length) return null;
  const left = cells[0].getBoundingClientRect().left, right = cells.at(-1).getBoundingClientRect().right;
  const index = Math.max(0, Math.min(cells.length - 1, Math.floor((clientX - left) / (right - left) * cells.length)));
  return Number(cells[index].dataset.y);
}

// ---------------------------------------------------------------- results
const usesOption = (block, name) => Boolean(block.view) && (spec(block.view, block.dataset || state.dataset)?.options || []).some(o => o.name === name);

function blockHTML(block, number) {
  const options = (spec(block.view, block.dataset || state.dataset)?.options || []).filter(o => !['year', 'variable', 'interval'].includes(o.name));
  const selects = options.map(o => `<select data-opt="${esc(o.name)}" aria-label="${esc(o.label)}">${o.values.map(v => `<option value="${esc(v.id)}" ${String(v.id) === String(state.opts[o.name]) ? 'selected' : ''}>${esc(splitLabel(v.label)[0])}</option>`).join('')}</select>`).join('');
  const actions = block.kind ? '' : '<button data-act="table">Table</button><button data-act="csv">CSV</button><button data-act="full">Full</button>';
  return `<section class="fig" id="fig-${block.id}" data-block="${block.id}">
    <header><span class="no">${String(number).padStart(2, '0')}</span><h3>${esc(block.title)}</h3><span class="opts">${selects}</span><span class="acts">${actions}</span></header>
    <p class="cap" hidden></p><p class="msg">Loading</p><div class="scroll"><div class="plot" hidden></div></div><div class="tbl" hidden></div></section>`;
}

function renderResults() {
  for (const block of live.values()) block.controller?.abort();
  live.clear(); fullId = null;
  const element = $('#results'), data = ds(), river = gauge();
  let blocks = [], head = '';
  if (river) {
    blocks = [{ id: 'timeseries', view: 'timeseries', title: TITLES.timeseries }];
    for (const section of SECTIONS) if (state.sections.includes(section.id)) {
      for (const b of section.blocks) blocks.push({ ...b, id: b.id || b.view, section: section.id, title: b.kind === 'headline' ? `Risk assessment · ${occupation().label}` : TITLES[b.view] });
    }
    blocks = blocks.filter(b => b.kind || spec(b.view));
    const facts = [river.place || river.name, `No. ${river.id}`, finite(river.elevation_m) && `${Math.round(river.elevation_m)} m`, finite(river.area_km2) && `${significant(river.area_km2)} km²`].filter(Boolean);
    head = `<header class="res-head"><div><h2>${esc(riverName(river))}</h2><p>${esc(facts.join(' · '))}</p></div><div class="res-side"><p>${esc(data.label)}<br>${period(data)}</p><button data-action="expand">${state.expanded ? 'Map' : 'Expand'}</button></div></header>`;
  } else if (state.country && regionTabs().length) {
    const tabs = regionTabs(), current = tabs.find(t => t.view === state.region) || tabs[0];
    blocks = [{ id: current.view, view: current.view, dataset: current.dataset, title: TITLES[current.view] }];
    head = `<header class="res-head"><div><h2>${esc(countryName(state.country))}</h2><p>${data.count} rivers compared</p></div><div class="res-side"><p>${esc(data.label)}<br>${period(data)}</p><button data-action="expand">${state.expanded ? 'Map' : 'Expand'}</button></div></header>
      <nav class="tabs">${tabs.map(t => `<button data-region="${t.view}" class="${t.view === current.view ? 'on' : ''}">${esc(TITLES[t.view])}</button>`).join('')}</nav>`;
  } else { element.innerHTML = ''; return; }
  element.innerHTML = `${head}${blocks.map((b, i) => blockHTML(b, i + 1)).join('')}<p class="foot">Sen's slope per decade · Mann-Kendall test · FDR per metric. Statistical association, not cause.</p>`;
  element.scrollTop = 0;
  for (const block of blocks) { live.set(block.id, block); load(block); }
}

function reload(match = () => true) { for (const block of live.values()) if (match(block)) load(block); }

async function load(block) {
  const element = $(`#fig-${block.id}`);
  if (!element) return;
  block.controller?.abort();
  block.controller = new AbortController();
  const ticket = block.ticket = (block.ticket || 0) + 1;
  block.table = null;
  // What this request asks for; the answer is drawn with these, whatever is ticked by then.
  const asked = { variables: [...state.variables], interval: state.interval, year: state.year };
  try {
    if (block.kind === 'headline') {
      const query = new URLSearchParams({ dataset: state.dataset, view: 'annual_metric', gauge: state.river, table: 'trends' });
      const payload = await api(`/api/table?${query}`, { signal: block.controller.signal });
      if (ticket !== block.ticket) return;
      if (payload.status !== 'ready') return unavailable(element, payload);
      drawHeadline(element, payload.rows || []);
      return;
    }
    $('.tbl', element).hidden = true;
    const payload = await api(`/api/figure?${params(block)}`, { signal: block.controller.signal });
    if (ticket !== block.ticket) return;
    if (payload.status !== 'ready' || !payload.figure) return unavailable(element, payload);
    Object.assign(block, asked, { payload });
    await draw(block);
  } catch (error) {
    if (ticket === block.ticket && error.name !== 'AbortError') unavailable(element, { message: error.message });
  }
}

function unavailable(element, payload) {
  $('.plot', element).hidden = true;
  $('.cap', element).hidden = true;
  const message = $('.msg', element);
  message.hidden = false;
  message.innerHTML = `${esc(payload.status === 'missing' && payload.build_command ? 'Not built' : payload.message || 'Unavailable')}${payload.build_command ? `<code>${esc(payload.build_command)}</code>` : ''}`;
}

// The backend's categorical blue and orange become the plate's ink and signal colour.
// Ordered ramps and the red-blue change scales keep the backend's colours: they carry meaning.
function houseColours(data) {
  const text = JSON.stringify(data || []);
  const ramp = ['#86b6ef', '#5598e7', '#1c5cab', '#104281', '#0d366b'].some(colour => text.includes(colour));
  const swapped = text.replaceAll('#eb6834', ORANGE).replaceAll('rgba(42,120,214,', 'rgba(10,10,10,');
  return JSON.parse(ramp ? swapped : swapped.replaceAll('#2a78d6', INK));
}

// The backend decides what is drawn; this only sets the house typography and line colours.
function styleFigure(figure, block) {
  const layout = JSON.parse(JSON.stringify(figure.layout || {}));
  let data = houseColours(figure.data);
  const notes = [];
  delete layout.template;
  delete layout.width;
  const title = typeof layout.title === 'string' ? layout.title : layout.title?.text || '';
  const lines = title.split(/<br\s*\/?\s*>/i).map(line => line.replace(/<[^>]+>/g, '').trim()).filter(Boolean);
  if (lines.length > 1) notes.push(lines.slice(1).join(' · '));
  const margin = layout.margin || {};
  layout.title = { text: '' };
  layout.margin = { l: margin.l ?? 60, r: margin.r ?? 24, b: margin.b ?? 48, t: title ? Math.max(18, (margin.t ?? 60) - (lines.length > 1 ? 58 : 38)) : margin.t ?? 18 };
  layout.paper_bgcolor = 'rgba(0,0,0,0)';
  layout.plot_bgcolor = 'rgba(0,0,0,0)';
  layout.font = { family: FONT, size: 12, color: MID };
  layout.hoverlabel = { bgcolor: '#ffffff', bordercolor: INK, font: { family: FONT, size: 12, color: INK } };
  layout.legend = { ...(layout.legend || {}), bgcolor: 'rgba(0,0,0,0)', font: { family: FONT, size: 11, color: INK } };
  layout.colorway = [INK, ORANGE, '#1f6fe0', '#00875a', '#c9a100'];
  for (const key of Object.keys(layout)) if (/^[xy]axis\d*$/.test(key)) {
    const axis = layout[key] || {};
    const text = typeof axis.title === 'string' ? axis.title : axis.title?.text;
    layout[key] = { ...axis, gridcolor: GRID, linecolor: INK, zerolinecolor: GRID, ticks: axis.ticks ?? '', automargin: true,
      tickfont: { family: FONT, size: 11, color: MID },
      title: text ? { ...(typeof axis.title === 'object' ? axis.title : {}), text: unit(text), font: { family: FONT, size: 11, color: MID }, standoff: 8 } : axis.title };
  }
  for (const annotation of layout.annotations || []) annotation.font = { ...(annotation.font || {}), family: FONT };
  data = data.map(trace => trace.colorbar || trace.type === 'heatmap' ? { ...trace, colorbar: { ...(trace.colorbar || {}), outlinewidth: 0, thickness: 10,
    tickfont: { family: FONT, size: 10, color: MID } } } : trace);
  const hidden = Number(layout.meta?.interpolated_days_hidden) || 0;
  if (hidden) notes.push(`${hidden} interpolated ${hidden === 1 ? 'day' : 'days'} not drawn`);

  if (block.view === 'timeseries') {
    const variables = block.variables || state.variables, monthly = (block.interval || state.interval) === 'monthly';
    const empty = new Set(layout.meta?.empty_variables || []);
    const narrow = (block.width || 900) < 600;   // a narrow box drops the axis titles; the legend names the lines
    let place = 0;
    data = data.map((trace, i) => {
      const id = variables[i], color = SERIES[id] || MID;
      const key = i === 0 ? 'yaxis' : `yaxis${i + 1}`, axis = { ...(layout[key] || {}) };
      delete axis.position; delete axis.domain; delete axis.anchor; delete axis.autoshift; delete axis.shift;
      const name = unit(trace.name);
      if (empty.has(id)) {
        // No value in this year: the line stays in the legend as "no data" and takes no axis.
        layout[key] = { ...(i ? { overlaying: 'y' } : {}), visible: false, showgrid: false };
        return { ...trace, name: `${name} — no data`, line: { color, width: 1 }, marker: { color } };
      }
      const slot = place++;
      Object.assign(axis, slot === 0 ? { side: 'left', anchor: 'x', showgrid: true } : slot === 1 ? { side: 'right', anchor: 'x', showgrid: false }
        : { side: slot === 2 ? 'left' : 'right', anchor: 'free', position: slot === 2 ? 0 : 1, autoshift: true, shift: slot === 2 ? -6 : 6, showgrid: false });
      if (i) axis.overlaying = 'y';
      layout[key] = { ...axis, visible: true, tickfont: { family: FONT, size: 11, color }, linecolor: color, showline: true, automargin: true,
        title: narrow ? { text: '' } : { ...(axis.title || {}), text: unit(axis.title?.text || ''), font: { family: FONT, size: 11, color } } };
      return { ...trace, name, mode: monthly ? 'lines+markers' : 'lines', marker: { color, size: 5, symbol: 'square' },
        line: { color, width: id === 'discharge_vol' ? (monthly ? 2.6 : 1.5) : (monthly ? 1.8 : 1.1) } };
    });
    if (empty.size) notes.push(`No ${variables.filter(v => empty.has(v)).map(variableName).join(', ')} values saved for ${block.year ?? state.year}`);
    layout.xaxis = { ...(layout.xaxis || {}), domain: [0, 1], tickformat: '%b', dtick: 'M1', hoverformat: monthly ? '%b %Y' : '%d %b %Y', showgrid: true, ticklabelmode: monthly ? 'instant' : 'period' };
    layout.legend = { ...layout.legend, orientation: 'h', x: 0, y: 1.02, xanchor: 'left', yanchor: 'bottom' };
    layout.margin = { l: 8, r: 8, b: 40, t: 34 };
    layout.hovermode = 'x unified';
  }
  if (layout.scene) {
    const axis3d = axis => ({ ...(axis || {}), backgroundcolor: 'rgba(0,0,0,0)', gridcolor: '#cfcfca', zerolinecolor: '#cfcfca', linecolor: INK,
      showspikes: false, tickfont: { family: FONT, size: 10, color: MID },
      title: { ...(typeof axis?.title === 'object' ? axis.title : { text: axis?.title || '' }), font: { family: FONT, size: 11, color: INK } } });
    layout.scene = { ...layout.scene, xaxis: axis3d(layout.scene.xaxis), yaxis: axis3d(layout.scene.yaxis), zaxis: axis3d(layout.scene.zaxis),
      camera: { eye: { x: -1.75, y: -2.1, z: 1.05 }, center: { x: 0, y: 0, z: -0.12 } } };
    layout.margin = { l: 0, r: 0, t: 0, b: 0 };
    for (const axis of ['xaxis', 'yaxis', 'zaxis']) if (layout.scene[axis].title.text) layout.scene[axis].title.text = unit(layout.scene[axis].title.text);
    data = data.map(trace => trace.type === 'surface'
      ? { ...trace, colorscale: [[0, '#f3f3f0'], [0.12, '#cfcfca'], [0.4, '#8b8b87'], [0.75, '#3a3a38'], [1, INK]], lighting: { ambient: 0.9, diffuse: 0.35, specular: 0.05, roughness: 0.9 },
          contours: { z: { show: true, color: INK, width: 1, project: { z: true }, usecolormap: false } } }
      : trace.type === 'scatter3d' ? { ...trace, line: { ...(trace.line || {}), color: ORANGE, width: 7 } } : trace);
  }
  return { data, layout, caption: notes.join(' · ') };
}

// One drawing at a time per figure: a second request waits for the first to finish.
function draw(block) {
  block.drawing = (block.drawing || Promise.resolve()).then(() => paint(block)).catch(error => {
    const element = $(`#fig-${block.id}`);
    if (element) unavailable(element, { message: error.message });
  });
  return block.drawing;
}

async function paint(block) {
  const element = $(`#fig-${block.id}`);
  if (!element || !block.payload || !window.Plotly || live.get(block.id) !== block) return;
  block.width = element.clientWidth;
  const { data, layout, caption } = styleFigure(block.payload.figure, block);
  const plot = $('.plot', element), cap = $('.cap', element);
  const native = Number(block.payload.figure.layout?.height) || HEIGHT[block.view] || 360;
  layout.height = fullId === block.id ? Math.max(native, innerHeight - 96) : native;
  layout.autosize = true;
  plot.style.minWidth = `${MIN_WIDTH[block.view] || 0}px`;
  cap.textContent = caption; cap.hidden = !caption;
  $('.msg', element).hidden = true;
  plot.hidden = false;
  const config = { responsive: true, displaylogo: false, displayModeBar: false, scrollZoom: false, doubleClick: 'reset' };
  // Plotly cannot add axes to a drawn graph reliably, so a changed set of axes starts a fresh one.
  const shape = [block.view, data.map(t => `${t.type}:${t.yaxis || ''}`).join(','),
    Object.keys(layout).filter(k => /axis\d*$/.test(k)).sort().map(k => `${k}:${layout[k].side || ''}:${layout[k].anchor || ''}:${layout[k].visible === false ? 0 : 1}`).join(',')].join('|');
  try {
    if (plot.dataset.shape !== shape) Plotly.purge(plot);
    await Plotly.react(plot, data, layout, config);
  } catch {
    Plotly.purge(plot);
    await Plotly.newPlot(plot, data, layout, config);
  }
  plot.dataset.shape = shape;
}

// Risk assessment: the saved trend rows, straight from the backend's table. No score is computed.
function drawHeadline(element, rows) {
  const byMetric = Object.fromEntries(rows.map(r => [r.metric, r]));
  const change = (row, info) => finite(row.pct_per_decade) ? `${signed(row.pct_per_decade)} %` : `${signed(row.slope_per_decade)} ${/day/.test(info.unit) ? 'd' : info.unit}`;
  const mean = (row, info) => /day of/.test(info.unit) ? `day ${significant(row.mean)}` : `${significant(row.mean)} ${info.unit}`.trim();
  const mark = row => row.significant_fdr ? '<i class="sig on" title="Significant after FDR"></i>' : row.significant ? '<i class="sig" title="Significant before FDR only"></i>' : '';
  const cells = HEADLINE.map(([label, metric]) => {
    const row = byMetric[metric], info = metricInfo(metric);
    return `<div><small>${label}<br>${esc(info.name)}</small>${row ? `<b>${change(row, info)}</b><span>per decade · p ${pValue(row.p)} ${mark(row)}</span>` : '<b>—</b><span>no saved trend</span>'}</div>`;
  }).join('');
  const chosen = occupation().metrics.filter(m => byMetric[m]);
  const table = chosen.length ? `<div class="tbl-scroll"><table class="ind"><thead><tr><th>${esc(occupation().label)} indicators</th><th>Mean</th><th>Change / decade</th><th>p</th><th class="yrs">Years</th><th></th></tr></thead><tbody>${chosen.map(m => {
    const row = byMetric[m], info = metricInfo(m);
    return `<tr><td>${esc(info.name)}</td><td>${mean(row, info)}</td><td>${change(row, info)}</td><td>${pValue(row.p)}</td><td class="yrs">${row.first_year}–${row.last_year}</td><td>${mark(row)}</td></tr>`;
  }).join('')}</tbody></table></div><p class="key"><span><i class="sig on"></i>significant after FDR</span><span><i class="sig"></i>before FDR only</span></p>` : '';
  $('.msg', element).hidden = true;
  $('.plot', element).hidden = true;
  const body = $('.tbl', element);
  body.hidden = false;
  body.className = 'tbl headline';
  body.innerHTML = `<p class="key">Saved trend indicators only. Risk assessment, requirements, exposure estimates and risk scores are not implemented. Indicator selections by occupation await team review.</p><div class="readout">${cells}</div>${table}`;
}

// ---------------------------------------------------------------- tables and export
async function tableFor(block) {
  if (!block.table) {
    const query = params(block);
    query.set('table', spec(block.view, block.dataset || state.dataset).table);
    const payload = await api(`/api/table?${query}`);
    if (payload.status !== 'ready') throw new Error(payload.message || 'No saved records.');
    block.table = payload; block.page = 0;
  }
  return block.table;
}

function renderTable(block) {
  const body = $(`#fig-${block.id} .tbl`), rows = block.table.rows || [], columns = block.table.columns || [];
  const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  block.page = Math.max(0, Math.min(block.page || 0, pages - 1));
  const cell = v => v == null ? '—' : typeof v === 'number' ? Number(v).toLocaleString('en-GB', { maximumSignificantDigits: 6, useGrouping: false })
    : typeof v === 'object' ? JSON.stringify(v) : /^\d{4}-\d\d-\d\dT00:00:00/.test(v) ? v.slice(0, 10) : v;
  body.innerHTML = `<div class="tbl-scroll"><table><thead><tr>${columns.map(c => `<th>${esc(c)}</th>`).join('')}</tr></thead><tbody>${rows.slice(block.page * PAGE_SIZE, (block.page + 1) * PAGE_SIZE).map(row => `<tr>${columns.map(c => `<td>${esc(cell(row[c]))}</td>`).join('')}</tr>`).join('')}</tbody></table></div>
    <p class="pager"><span>${rows.length.toLocaleString('en-GB')} records · — = missing</span>${pages > 1 ? `<button data-act="prev" ${block.page === 0 ? 'disabled' : ''}>Prev</button><span>${block.page + 1} / ${pages}</span><button data-act="next" ${block.page === pages - 1 ? 'disabled' : ''}>Next</button>` : ''}</p>`;
  body.hidden = false;
}

function downloadCSV(block) {
  const field = value => { let text = value == null ? '' : typeof value === 'object' ? JSON.stringify(value) : String(value); if (typeof value === 'string' && /^[=+\-@\t\r]/.test(text)) text = `'${text}`; return `"${text.replaceAll('"', '""')}"`; };
  const { columns, rows } = block.table;
  const lines = [columns.map(field).join(','), ...rows.map(row => columns.map(c => field(row[c])).join(','))];
  const url = URL.createObjectURL(new Blob(['﻿' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = url; link.download = `rivascope-${block.dataset || state.dataset}-${block.view}.csv`; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function setFull(id) {
  const previous = fullId;
  fullId = id;
  for (const element of $$('.fig')) element.classList.toggle('full', element.dataset.block === fullId);
  for (const element of $$('.fig [data-act="full"]')) element.textContent = element.closest('.fig').dataset.block === fullId ? 'Close' : 'Full';
  for (const blockId of [previous, id]) if (blockId && live.get(blockId)?.payload) draw(live.get(blockId));
}

async function reloadSaved() {
  const button = $('[data-action="refresh"]');
  button.removeAttribute('title');
  button.disabled = true; button.textContent = 'Reading';
  try { catalog = await api('/api/refresh', { method: 'POST' }); courseCache.clear(); $('#about-body').innerHTML = aboutHTML(); if (!$('#app').hidden) render(); }
  catch (error) { button.textContent = `Retry reload: ${error.message}`; button.title = error.message; }
  finally { button.disabled = false; }
}

// ---------------------------------------------------------------- events
document.addEventListener('click', async event => {
  const act = event.target.closest('[data-act]');
  if (act) {
    const block = live.get(act.closest('.fig').dataset.block);
    if (!block) return;
    const body = $(`#fig-${block.id} .tbl`);
    try {
      if (act.dataset.act === 'full') setFull(fullId === block.id ? null : block.id);
      else if (act.dataset.act === 'table') { if (!body.hidden) { body.hidden = true; return; } await tableFor(block); renderTable(block); }
      else if (act.dataset.act === 'csv') { await tableFor(block); downloadCSV(block); }
      else if (act.dataset.act === 'prev') { block.page--; renderTable(block); }
      else if (act.dataset.act === 'next') { block.page++; renderTable(block); }
    } catch (error) { body.hidden = false; body.innerHTML = `<p class="pager"><span>${esc(error.message)}</span></p>`; }
    return;
  }
  const target = event.target.closest('[data-action], [data-country], [data-river], [data-interval], [data-region], [data-occupation]');
  if (!target) return;
  const d = target.dataset;
  if (d.occupation) { chooseOccupation(d.occupation); openApp(); }
  else if (d.country) go({ country: d.country, river: null, dataset: d.country.toLowerCase() });
  else if (d.river) go({ river: d.river });
  else if (d.interval) { state.interval = d.interval; for (const b of $$('[data-interval]')) b.classList.toggle('on', b.dataset.interval === d.interval); reload(b => b.view === 'timeseries'); remember(); }
  else if (d.region) { state.region = d.region; renderResults(); remember(); }
  else if (d.action === 'europe') go({ country: null, river: null });
  else if (d.action === 'rivers') go({ river: null });
  else if (d.action === 'about') $('#about').showModal();
  else if (d.action === 'refresh') reloadSaved();
  else if (d.action === 'retry') location.reload();
  else if (d.action === 'expand') { state.expanded = !state.expanded; $('#layout').classList.toggle('expanded', state.expanded); target.textContent = state.expanded ? 'Map' : 'Expand'; remember(); }
});

document.addEventListener('change', event => {
  const input = event.target, d = input.dataset;
  if (input.id === 'occupation-select') {
    chooseOccupation(input.value);
    const title = $('#fig-headline h3');
    if (title) title.textContent = `Risk assessment · ${occupation().label}`;
    reload(b => b.kind === 'headline'); remember();
  } else if (input.id === 'dataset') go({ dataset: input.value, river: null });
  else if (d.variable) {
    const chosen = $$('[data-variable]:checked').map(node => node.dataset.variable);
    if (!chosen.length || chosen.length > 4) { input.checked = !input.checked; return; }
    state.variables = optionValues('variable').filter(id => chosen.includes(id));
    reload(b => b.view === 'timeseries'); remember();
  } else if (d.section) {
    state.sections = SECTIONS.map(s => s.id).filter(id => $(`[data-section="${id}"]`)?.checked);
    renderResults(); remember();
  } else if (d.opt) {
    state.opts[d.opt] = input.value;
    for (const other of $$(`select[data-opt="${d.opt}"]`)) other.value = input.value;
    reload(b => usesOption(b, d.opt)); remember();
  }
});

document.addEventListener('input', event => {
  if (event.target.id !== 'filter') return;
  const query = event.target.value.trim().toLowerCase();
  for (const row of $$('#river-list li')) row.hidden = !row.textContent.toLowerCase().includes(query);
});

document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && fullId) setFull(null);
  if (event.target.id === 'track' && ['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) {
    const years = ds().years, index = years.indexOf(Number(state.year));
    setYear(event.key === 'Home' ? years[0] : event.key === 'End' ? years.at(-1) : years[Math.max(0, Math.min(years.length - 1, index + (event.key === 'ArrowLeft' ? -1 : 1)))]);
    event.preventDefault();
  }
});

// Dragging along the timeline picks the year under the pointer.
document.addEventListener('pointerdown', event => {
  const track = event.target.closest('#track');
  if (!track) return;
  track.setPointerCapture(event.pointerId);
  track.classList.add('dragging');
  setYear(yearAt(event.clientX));
});
document.addEventListener('pointermove', event => { if ($('#track.dragging')) setYear(yearAt(event.clientX)); });
for (const name of ['pointerup', 'pointercancel']) document.addEventListener(name, () => $('#track.dragging')?.classList.remove('dragging'));

// The divider between the map and the results box.
{
  const grip = $('#grip'), layout = $('#layout');
  grip.addEventListener('pointerdown', event => { grip.setPointerCapture(event.pointerId); grip.classList.add('dragging'); });
  grip.addEventListener('pointermove', event => {
    if (!grip.classList.contains('dragging')) return;
    const box = layout.getBoundingClientRect(), side = $('#side').getBoundingClientRect().width;
    layout.style.setProperty('--res', `${Math.max(420, Math.min(box.width - side - 240, box.right - event.clientX))}px`);
  });
  for (const name of ['pointerup', 'pointercancel']) grip.addEventListener(name, () => grip.classList.remove('dragging'));
}

// When the results box changes width, every figure is laid out again for its new size.
new ResizeObserver(() => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => { for (const block of live.values()) if (block.payload) draw(block); }, 120);
}).observe($('#results'));
window.addEventListener('pagehide', () => navigator.sendBeacon('/api/bye'));
start();
