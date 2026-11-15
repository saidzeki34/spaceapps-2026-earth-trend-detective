// RivaScope: what is on screen, and what happens when something is picked.
// The selection lives in `state`; the numbers come from the local server.

import { drawChart, drawYearBars, esc, fmt, legendHTML, MONTHS } from "./chart.js";
import { createMap } from "./map.js";
import { drawPlane } from "./plane.js";

const $ = (selector, root = document) => root.querySelector(selector);
const STORE_KEY = "rivascope-selection";
const SPLASH_MIN_MS = 2200;

const state = {
  occupation: null, country: null, river: null, year: null, method: "monthly",
  variables: [], sections: [], usual: false, expanded: false, full: false,
};
let boot = null;        // the menus; the rivers of each country are added once they have been read
let geodata = null;     // country outlines and large river lines for the map
let riversReady = null; // resolves when the list of rivers has arrived
let linkedRiver = null; // a river named in the address, opened once the rivers are known
let view = null;        // the latest answer for the open river
let map = null;
let asked = 0;          // counts requests, so a late answer never overwrites a newer one
let timelineKey = null;
let yearTimer = null;

async function getJSON(url) {
  const response = await fetch(url);
  const data = await response.json().catch(() => ({ error: "The answer could not be read." }));
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}

// ---------- Remembering the selection ----------

function remember() {
  const { occupation, method, variables, sections, usual } = state;
  localStorage.setItem(STORE_KEY, JSON.stringify({ occupation, method, variables, sections, usual }));
  const parts = { o: state.occupation, c: state.country, r: state.river, y: state.year, m: state.method,
    v: state.variables.join(","), s: state.sections.join(","), u: state.usual ? 1 : "", x: state.expanded ? 1 : "" };
  const hash = Object.entries(parts).filter(([, value]) => value !== null && value !== "" && value !== undefined)
    .map(([key, value]) => `${key}=${encodeURIComponent(value)}`).join("&");
  history.replaceState(null, "", "#" + hash);
}

function recall() {
  state.variables = boot.variables.filter((v) => v.default).map((v) => v.id);
  state.sections = boot.assessments.filter((a) => a.default).map((a) => a.id);
  try { Object.assign(state, JSON.parse(localStorage.getItem(STORE_KEY)) || {}); } catch { /* start fresh */ }
  const link = new URLSearchParams(location.hash.slice(1));
  const list = (key) => (link.get(key) || "").split(",").filter(Boolean);
  if (link.has("o")) state.occupation = link.get("o");
  if (link.has("m")) state.method = link.get("m");
  if (link.has("v")) state.variables = list("v");
  if (link.has("s")) state.sections = list("s");
  state.usual = link.has("u") ? link.get("u") === "1" : state.usual;
  state.expanded = link.get("x") === "1";
  const country = boot.countries.find((c) => c.code === link.get("c"));
  if (country) {
    state.country = country.code;
    if (link.get("r")) linkedRiver = { id: link.get("r"), year: Number(link.get("y")) || null };
  }
  // Drop anything the menus no longer offer.
  if (!boot.occupations.some((o) => o.id === state.occupation)) state.occupation = null;
  if (!boot.methods.some((m) => m.id === state.method)) state.method = boot.methods[0].id;
  state.variables = state.variables.filter((id) => boot.variables.some((v) => v.id === id));
  state.sections = state.sections.filter((id) => boot.assessments.some((a) => a.id === id));
}

// ---------- Small lookups ----------

const countryOf = (code) => boot.countries.find((c) => c.code === code);
const riverOf = (id) => boot.countries.flatMap((c) => c.rivers).find((r) => r.id === id);
const occupationOf = (id) => boot.occupations.find((o) => o.id === id);
const methodOf = (id) => boot.methods.find((m) => m.id === id);
const inOrder = (ids, all) => all.filter((item) => ids.includes(item.id)).map((item) => item.id);

// ---------- Start ----------

async function start() {
  const began = performance.now();
  try {
    [boot, geodata] = await Promise.all([getJSON("/api/bootstrap"), getJSON("data/geodata.json")]);
  } catch (error) {
    $("#splash-status").textContent = `RivaScope could not start. ${error.message}`;
    return;
  }
  // The menus are ready at once. The rivers take longer (the measurements have to be read),
  // so they arrive in the background while the first screens are already usable.
  boot.countries = Object.entries(geodata.countries).map(([code, c]) => ({ code, name: c.name, rivers: [], reading: true }));
  boot.data = null;
  riversReady = getJSON("/api/rivers").then(showRivers, (error) => {
    boot.countries.forEach((c) => { c.reading = false; c.failed = error.message; });
    if (!$("#app").hidden) renderSide();
  });
  const linked = location.hash.length > 1;
  recall();
  $("#choices").innerHTML = boot.occupations.map((o) => `
    <li><button data-occupation="${o.id}">
      <span class="choice-name">${esc(o.label)}</span>
      <span class="choice-question">${esc(o.question)}</span>
    </button></li>`).join("");
  $("#occupation-select").innerHTML = boot.occupations.map((o) => `<option value="${o.id}">${esc(o.label)}</option>`).join("");
  $("#about-body").innerHTML = aboutHTML();

  setTimeout(() => {
    const splash = $("#splash");
    splash.classList.add("leaving");
    setTimeout(() => splash.remove(), 500);
    if (linked && state.occupation) openApp(); else openOccupationMenu();
  }, linked ? 0 : Math.max(0, SPLASH_MIN_MS - (performance.now() - began)));
}

// The rivers have arrived: fill the lists and the map, and open a river named in the address.
function showRivers(answer) {
  boot.countries = answer.countries;
  boot.data = answer.data;
  $("#about-body").innerHTML = aboutHTML();
  const country = countryOf(state.country);
  if (linkedRiver && country && country.rivers.some((r) => r.id === linkedRiver.id)) {
    state.river = linkedRiver.id;
    state.year = linkedRiver.year;
  }
  linkedRiver = null;
  if (map) map.setRivers(Object.fromEntries(boot.countries.map((c) => [c.code, c.rivers])));
  if (!$("#app").hidden) render();
}

function aboutHTML() {
  const data = boot.data;
  if (!data) return "<p>The river data is still being read. Please look again in a moment.</p>";
  const measured = data.measured_rivers
    ? `<p>Measured rivers come from <b>${esc(data.measured_source)}</b>: observed daily records of Swiss catchments,
       analysed by this project's trend section. ${data.measured_rivers} mountain rivers are available.</p>`
    : `<p><b>No measured data was found on this computer.</b> ${esc(data.message).replace(/`([^`]+)`/g, "<code>$1</code>")}</p>`;
  return `${measured}
    <p>Anything marked <span class="imaginary">imaginary</span> is a placeholder, made up so that every part of the
    screen has something to show: rivers without measurements (all of Norway and the large Swiss rivers),
    evaporation, the prediction, the physical model, the requirements and the risk index. They are meant to be
    replaced as real sources arrive.</p>
    <p>Map imagery and place names: Esri. Country outlines: Natural Earth. Courses of the large rivers:
    © OpenStreetMap contributors. Catchments of the measured rivers: CAMELS-CH.</p>`;
}

function openOccupationMenu() {
  $("#app").hidden = true;
  $("#occupation").hidden = false;
}

function openApp() {
  $("#occupation").hidden = true;
  $("#app").hidden = false;
  $("#occupation-select").value = state.occupation;
  if (!map) {
    map = createMap($("#map"), geodata, {
      country: (code) => go({ country: code, river: null }),
      river: (id) => go({ river: id }),
      europe: () => go({ country: null, river: null }),
    });
    map.setRivers(Object.fromEntries(boot.countries.map((c) => [c.code, c.rivers])));
    riversReady.then(() => getJSON("/api/outlines")).then((outlines) => map.setOutlines(outlines)).catch(() => {});
  }
  render();
}

// ---------- Moving around ----------

function go(changes) {
  const riverChanged = "river" in changes && changes.river !== state.river;
  Object.assign(state, changes);
  if (riverChanged) { state.year = null; view = null; state.full = false; }
  if (!state.river) state.expanded = false;
  render();
}

function render() {
  const layout = $("#layout");
  layout.classList.toggle("has-river", Boolean(state.river));
  layout.classList.toggle("expanded", state.expanded);
  renderCrumbs();
  renderSide();
  map.show({ country: state.country, river: state.river });
  if (state.river) {
    if (!view) $("#results").innerHTML = `<div class="results-scroll"><p class="message">Reading this river’s record…</p></div>`;
    refresh();
  } else {
    timelineKey = null;
  }
  remember();
}

function renderCrumbs() {
  const country = countryOf(state.country), river = riverOf(state.river);
  const parts = [country ? `<button class="link" data-action="europe">Europe</button>` : `<span class="here">Europe</span>`];
  if (country) {
    parts.push(river ? `<button class="link" data-action="rivers">${esc(country.name)}</button>`
      : `<span class="here">${esc(country.name)}</span>`);
  }
  if (river) parts.push(`<span class="here">${esc(river.name)}</span>`);
  $("#crumbs").innerHTML = parts.join('<span class="sep">/</span>');
}

// ---------- Left box ----------

function rowsHTML(rivers) {
  return `<ul class="rows">${rivers.map((r) => `
    <li><button class="row" data-river="${r.id}">
      <span class="row-name">${esc(r.name)}</span>
      ${r.place ? `<span class="row-sub">${esc(r.place)}</span>` : ""}
    </button></li>`).join("")}</ul>`;
}

function renderSide() {
  const side = $("#side");
  const country = countryOf(state.country), river = riverOf(state.river);
  if (!country) {
    side.innerHTML = `
      <h2>Countries</h2>
      <p class="side-sub">Pick a country on the map or here.</p>
      <ul class="rows">${boot.countries.map((c) => {
        const measured = c.rivers.filter((r) => r.measured).length, other = c.rivers.length - measured;
        const text = c.reading ? "reading its rivers…" : c.failed ? "its rivers could not be read"
          : measured ? `${measured} measured rivers, ${other} more with imaginary data`
          : `${other} rivers, imaginary data for now`;
        return `<li><button class="row" data-country="${c.code}"><span class="row-name">${esc(c.name)}</span>
          <span class="row-sub">${text}</span></button></li>`;
      }).join("")}</ul>`;
  } else if (!river) {
    const measured = country.rivers.filter((r) => r.measured), other = country.rivers.filter((r) => !r.measured);
    const lists = country.reading ? `<p class="side-sub">Reading the rivers…</p>`
      : country.failed ? `<p class="side-sub">The rivers could not be read. ${esc(country.failed)}</p>`
      : `<p class="side-sub">Pick a river on the map or here.</p>
        ${measured.length ? `<p class="group-title">Measured mountain rivers <span class="quiet">${measured.length}</span></p>${rowsHTML(measured)}` : ""}
        <p class="group-title">Large rivers <span class="imaginary">imaginary data</span></p>${rowsHTML(other)}`;
    side.innerHTML = `
      <button class="link back" data-action="europe">← Europe</button>
      <h2>${esc(country.name)}</h2>
      ${lists}`;
  } else {
    const facts = [river.area_km2 && `${Math.round(river.area_km2)} km²`,
      river.elevation_m && `mean height ${Math.round(river.elevation_m).toLocaleString("en-US")} m`].filter(Boolean);
    const about = river.measured
      ? `Measured at ${esc(river.place)}${facts.length ? " · " + facts.join(" · ") : ""}`
      : `<span class="imaginary">Imaginary data.</span> No measurements are connected for this river yet.`;
    const check = (item, kind, checked, extra = "") => `
      <label class="check" ${item.color ? `style="--c:${item.color}"` : ""} title="${esc(item.explain || "")}">
        <input type="checkbox" data-${kind}="${item.id}" ${checked ? "checked" : ""}>
        ${item.color ? '<i class="swatch"></i>' : ""}
        <span>${esc(item.label)}${extra}</span>
        ${item.unit ? `<span class="unit">${esc(item.unit)}</span>` : ""}
      </label>`;
    const variables = (group) => boot.variables.filter((v) => v.group === group).map((v) => check(v, "variable",
      state.variables.includes(v.id),
      river.measured && boot.imaginary_variables.includes(v.id) ? ' <span class="imaginary">imaginary</span>' : "")).join("");
    side.innerHTML = `
      <button class="link back" data-action="rivers">← Rivers of ${esc(country.name)}</button>
      <h2>${esc(river.name)}</h2>
      <p class="side-sub">${about}</p>
      <fieldset><p class="group-title">Reference</p>${variables("reference")}</fieldset>
      <hr class="rule">
      <fieldset><p class="group-title">Water availability</p>${variables("water")}</fieldset>
      <hr class="rule">
      <fieldset><p class="group-title">Assessments</p>
        ${boot.assessments.map((a) => check(a, "section", state.sections.includes(a.id))).join("")}</fieldset>
      <hr class="rule">
      <fieldset><p class="group-title">Calculation</p>
        ${boot.methods.map((m) => `
          <label class="check"><input type="radio" name="method" value="${m.id}" ${state.method === m.id ? "checked" : ""}>
            <span>${esc(m.label)}<small>${esc(m.hint)}</small></span></label>`).join("")}</fieldset>`;
  }
}

// ---------- Asking for the numbers ----------

async function refresh() {
  if (!state.river) return;
  const ticket = ++asked;
  const query = new URLSearchParams({
    river: state.river, year: state.year ?? "", method: state.method, occupation: state.occupation,
    variables: state.variables.join(","), sections: state.sections.join(","), usual: state.usual ? "1" : "",
  });
  $(".results-scroll")?.classList.add("loading");
  try {
    const answer = await getJSON(`/api/view?${query}`);
    if (ticket !== asked) return;
    view = answer;
    state.year = answer.year;
    renderTimeline();
    renderResults();
    remember();
  } catch (error) {
    if (ticket !== asked) return;
    $("#results").innerHTML = `<div class="results-scroll"><p class="message">This river could not be read. ${esc(error.message)}</p></div>`;
  }
}

// ---------- Timeline under the map ----------

function renderTimeline() {
  const { first_year: first, last_year: last, prediction_year: prediction, id } = view.river;
  const host = $("#timeline");
  const key = `${id}|${first}|${prediction}`;
  if (timelineKey !== key) {
    timelineKey = key;
    const span = prediction - first;
    const at = (year) => `calc(8px + (100% - 16px) * ${(year - first) / span})`;
    const solid = ((last - first) / span) * 100;
    const decades = [];
    for (let year = Math.ceil((first + 3) / 10) * 10; year <= last - 11; year += 10) decades.push(year);
    host.innerHTML = `
      <div class="timeline-year" id="timeline-year"></div>
      <div class="timeline-track" style="--track: linear-gradient(to right, #555c58 0 ${solid}%, transparent ${solid}%),
          repeating-linear-gradient(to right, #9a5b12 0 3px, transparent 3px 7px)">
        <input type="range" id="year-range" min="${first}" max="${prediction}" step="1" aria-label="Year">
        <span class="tick first" style="left:0">${first}</span>
        ${decades.map((year) => `<span class="tick" style="left:${at(year)}">${year}</span>`).join("")}
        <span class="tick last" style="left:${at(last)}">latest data ${last}</span>
        <span class="tick prediction" style="left:100%">prediction ${prediction}</span>
      </div>`;
  }
  syncTimeline();
}

function syncTimeline() {
  const predicting = state.year === view.river.prediction_year;
  const range = $("#year-range");
  if (Number(range.value) !== state.year) range.value = state.year;
  range.classList.toggle("predicting", predicting);
  $("#timeline-year").innerHTML = `${state.year}${predicting ? "<small>prediction</small>" : ""}`;
}

// ---------- Right box ----------

function riskHTML(risk) {
  if (!risk) return "";
  const s = risk.scores;
  return `
    <section class="block">
      <h3>Risk assessment <small>for ${esc(risk.occupation.label.toLowerCase())}</small></h3>
      <p class="question">${esc(risk.occupation.question)}</p>
      <p class="requirement"><b>${esc(risk.requirement.name)}:</b> ${esc(risk.requirement.summary)}
        <span class="imaginary">imaginary</span>
        <span class="why">No documented requirement exists yet. This placeholder is ${esc(risk.requirement.text)}.</span></p>
      <p class="sentence">${esc(risk.year.sentence)}</p>
      <dl class="facts">${risk.year.facts.map((f) => `
        <div class="fact"><dt>${esc(f.label)}</dt><dd>${esc(f.value)}<small>${esc(f.of)}</small></dd></div>`).join("")}</dl>

      <h4>Days below the requirement, year by year</h4>
      <div class="minibars" id="year-bars"></div>
      <p class="quiet">${esc(risk.record.sentence)} Click a bar to open that year.</p>

      <h4>What has changed over the record</h4>
      <table class="plain">
        <tr><th></th><th>Usual</th><th>Change</th><th>Evidence</th></tr>
        ${risk.changes.map((c) => `<tr title="${esc(c.description)}">
          <td>${esc(c.label)}</td><td>${esc(c.usual)}</td>
          <td class="${c.significant ? "strong" : ""}">${esc(c.change)}</td>
          <td class="${c.significant ? "" : "faint"}">${esc(c.evidence)}</td></tr>`).join("")}
      </table>

      <h4>Volatility plane</h4>
      <div class="plane-wrap">
        <div class="plane" id="plane"></div>
        <div class="plane-text">
          <p>${esc(risk.plane.text || "Not enough years to place this river.")}</p>
          ${risk.plane.others.length ? `<p class="quiet">Grey dots are the other measured rivers. Drag the picture to turn it.</p>`
            : `<p class="quiet">Drag the picture to turn it.</p>`}
          <p class="quiet">Risk index ${s.index} of 10 &middot; quantity ${s.quantity}, timing ${s.timing},
            variability ${s.variability} <span class="imaginary">imaginary</span><br>
            No formula has been agreed for these scores yet.</p>
        </div>
      </div>
      <p class="needs">A real assessment would still need ${esc(risk.needs.slice(0, -1).join(", "))} and
        ${esc(risk.needs[risk.needs.length - 1])}.</p>
    </section>`;
}

function statisticsHTML(statistics) {
  if (!statistics) return "";
  if (!statistics.rows.length) {
    return `<section class="block"><h3>Statistics</h3><p class="message">Tick a variable to see its statistics.</p></section>`;
  }
  return `
    <section class="block">
      <h3>Statistics</h3>
      <table class="plain" style="margin-top:10px">
        <tr><th></th><th>${statistics.year_label ? esc(statistics.year_label) : "This year"}</th>
          <th>Usual ${esc(statistics.period)}</th><th>Change</th><th>Evidence</th></tr>
        ${statistics.rows.map((r) => `<tr>
          <td><i class="dot" style="--c:${r.color}"></i>${esc(r.variable)}${r.imaginary ? ' <span class="imaginary">imaginary</span>' : ""}
            <span class="sub">${esc(r.metric)}${r.unit ? ", " + esc(r.unit) : ""}</span></td>
          <td>${esc(r.year_value)}</td><td>${esc(r.mean)}</td>
          <td class="${r.significant ? "strong" : ""}">${esc(r.change)}</td>
          <td class="${r.significant ? "" : "faint"}">${esc(r.evidence)}</td></tr>`).join("")}
      </table>
      <p class="quiet" style="margin-top:10px">${esc(statistics.note)}</p>
    </section>`;
}

function physicalHTML(physical) {
  if (!physical) return "";
  return `
    <section class="block">
      <h3>Physical models</h3>
      <div class="legend" style="margin-top:12px">${legendHTML(physical.chart.series)}</div>
      <div class="chart" id="physical-chart"></div>
      <p class="quiet" style="margin-top:6px">Agreement with the discharge: ${esc(physical.agreement)}
        <span class="imaginary">imaginary</span>. ${esc(physical.note)}</p>
    </section>`;
}

// For the prediction year: the predicted value of every ticked variable, month by month.
function predictionTableHTML(series) {
  return `
    <h4>Predicted value for each month <span class="imaginary">imaginary</span></h4>
    <div class="table-scroll"><table class="plain months">
      <tr><th></th>${MONTHS.map((month) => `<th>${month}</th>`).join("")}</tr>
      ${series.map((s) => `<tr>
        <td><i class="dot" style="--c:${s.color}"></i>${esc(s.label)} <span class="unit">${esc(s.unit)}</span></td>
        ${s.values.map((value) => `<td>${fmt(value)}</td>`).join("")}</tr>`).join("")}
    </table></div>`;
}

function renderResults() {
  const host = $("#results");
  const river = view.river;
  const scrolled = $(".results-scroll", host)?.scrollTop || 0;
  const series = view.chart.series;
  const requirement = view.risk ? { ...view.risk.requirement } : null;
  const showsRequirement = requirement && series.some((s) => s.id === "discharge");
  const anyImaginary = !river.measured || series.some((s) => s.imaginary) || view.risk || view.physical;
  const label = view.predicted ? `${view.year} · prediction` : `${view.year}`;
  const source = river.measured ? `measured, ${esc(river.source)}` : `<span class="imaginary">imaginary data</span>`;

  host.innerHTML = `
    <header class="results-head">
      <div>
        <h2>${esc(river.name)}${river.place ? ` <small>at ${esc(river.place)}</small>` : ""}</h2>
        <p class="results-meta">${label} &middot; ${esc(methodOf(view.method).label.toLowerCase())} &middot; ${source}</p>
      </div>
      <div class="head-actions"><button class="link" data-action="expand">${state.expanded ? "Show the map" : "Expand"}</button></div>
    </header>
    <div class="results-scroll">
      ${series.length ? `
        <figure class="graph${state.full ? " full" : ""}" id="graph">
          <div class="graph-title">${esc(river.name)} &middot; ${label}</div>
          <div class="legend">${legendHTML(series, showsRequirement ? requirement : null)}</div>
          <div class="chart" id="chart"></div>
          <div class="graph-foot">
            <label><input type="checkbox" data-toggle="usual" ${state.usual ? "checked" : ""}> Compare with a usual year</label>
            <button class="link" data-action="full">${state.full ? "Close full screen" : "Full screen"}</button>
          </div>
        </figure>`
        : `<p class="message">Tick a variable in the left box to draw it here.</p>`}
      ${view.predicted && series.length ? predictionTableHTML(series) : ""}
      ${anyImaginary ? `<p class="note-imaginary">Dotted lines and anything marked imaginary are placeholders, not measurements.</p>` : ""}
      ${riskHTML(view.risk)}${statisticsHTML(view.statistics)}${physicalHTML(view.physical)}
    </div>`;
  $(".results-scroll", host).scrollTop = scrolled;
  drawPictures();
}

// Everything drawn with SVG needs its box's width, so it is drawn after the HTML is in place
// and again whenever the box changes size.
function drawPictures() {
  if (!view || !state.river) return;
  const chart = $("#chart");
  if (chart) {
    const requirement = view.risk ? view.risk.requirement : null;
    const height = state.full ? Math.max(260, chart.clientHeight) : state.expanded ? 440 : 330;
    drawChart(chart, view.chart, { height, requirement });
  }
  const bars = $("#year-bars");
  if (bars) drawYearBars(bars, view.risk.record.years, view.risk.record.days_below, view.predicted ? null : view.year, pickYear);
  const plane = $("#plane");
  if (plane) drawPlane(plane, view.risk.plane, view.river.name);
  const physical = $("#physical-chart");
  if (physical) drawChart(physical, view.physical.chart, { height: 220 });
}

function pickYear(year) {
  state.year = year;
  syncTimeline();
  refresh();
}

// ---------- Listening ----------

document.addEventListener("click", (event) => {
  const target = event.target.closest("[data-action], [data-country], [data-river], [data-occupation]");
  if (!target) return;
  if (target.dataset.occupation) {
    state.occupation = target.dataset.occupation;
    openApp();
  } else if (target.dataset.country) {
    go({ country: target.dataset.country, river: null });
  } else if (target.dataset.river) {
    go({ river: target.dataset.river });
  } else if (target.dataset.action === "europe") {
    go({ country: null, river: null });
  } else if (target.dataset.action === "rivers") {
    go({ river: null });
  } else if (target.dataset.action === "about") {
    $("#about").showModal();
  } else if (target.dataset.action === "expand") {
    state.expanded = !state.expanded;
    $("#layout").classList.toggle("expanded", state.expanded);
    renderResults();
    remember();
  } else if (target.dataset.action === "full") {
    state.full = !state.full;
    renderResults();
  }
});

document.addEventListener("change", (event) => {
  const input = event.target;
  if (input.id === "occupation-select") {
    state.occupation = input.value;
  } else if (input.dataset.variable) {
    const ids = new Set(state.variables);
    if (input.checked) ids.add(input.dataset.variable); else ids.delete(input.dataset.variable);
    state.variables = inOrder([...ids], boot.variables);
  } else if (input.dataset.section) {
    const ids = new Set(state.sections);
    if (input.checked) ids.add(input.dataset.section); else ids.delete(input.dataset.section);
    state.sections = inOrder([...ids], boot.assessments);
  } else if (input.name === "method") {
    state.method = input.value;
  } else if (input.dataset.toggle === "usual") {
    state.usual = input.checked;
  } else {
    return;
  }
  remember();
  refresh();
});

document.addEventListener("input", (event) => {
  if (event.target.id !== "year-range") return;
  state.year = Number(event.target.value);
  syncTimeline();
  clearTimeout(yearTimer);
  yearTimer = setTimeout(refresh, 110);
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && state.full) {
    state.full = false;
    renderResults();
  }
});

// Dragging the bar between the map and the results makes the results wider or narrower.
{
  const grip = $("#grip"), layout = $("#layout");
  grip.addEventListener("pointerdown", (event) => {
    grip.setPointerCapture(event.pointerId);
    grip.classList.add("dragging");
  });
  grip.addEventListener("pointermove", (event) => {
    if (!grip.classList.contains("dragging")) return;
    const mapLeft = $(".mapwrap").getBoundingClientRect().left;
    const most = layout.getBoundingClientRect().right - mapLeft - 420;
    layout.style.setProperty("--map-w", `${Math.max(240, Math.min(most, event.clientX - mapLeft))}px`);
  });
  const stop = () => grip.classList.remove("dragging");
  grip.addEventListener("pointerup", stop);
  grip.addEventListener("pointercancel", stop);
}

let drawTimer = null;
new ResizeObserver(() => {
  clearTimeout(drawTimer);
  drawTimer = setTimeout(drawPictures, 60);
}).observe($("#results"));

// Tell the local server when the window closes, so it can stop too.
window.addEventListener("pagehide", () => navigator.sendBeacon("/api/bye"));

start();
