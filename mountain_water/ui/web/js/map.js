// The satellite map: Europe with the two countries lit, then the saved gauges and river segments.
// Country boundaries remain context; they are never presented as river courses.

const EUROPE = [[43.0, -4.0], [71.6, 30.0]];
const IMAGERY = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";
const LABELS = "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}";
const COLOR = { border: "#ffffff", river: "#ffffff", selected: "#ff4f00" };
const esc = (value) => String(value ?? "").replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const key = (country, id) => `${String(country).toUpperCase()}:${String(id)}`;
const position = (river) => river.lat != null && river.lon != null &&
  Number.isFinite(Number(river.lat)) && Number.isFinite(Number(river.lon)) &&
  Math.abs(Number(river.lat)) <= 90 && Math.abs(Number(river.lon)) <= 180
  ? [Number(river.lat), Number(river.lon)] : null;

// geodata provides country outlines; handlers are { country(code), river(id), europe() }.
export function createMap(element, geodata, handlers) {
  if (typeof L === "undefined") {
    element.innerHTML = '<div class="map-error">The map could not be loaded. Select a station from the list.</div>';
    return { show() {}, setRivers() {}, setCourses() {}, fit() {} };
  }
  const map = L.map(element, {
    zoomSnap: 0.25, zoomDelta: 0.5, minZoom: 3, maxZoom: 13, worldCopyJump: true,
    maxBounds: [[20, -45], [82, 70]], maxBoundsViscosity: 0.6,
  });
  map.attributionControl.setPrefix(false);
  for (const [name, z] of [["labels", 250], ["shade", 300], ["countries", 410], ["rivers", 450], ["points", 460]]) {
    map.createPane(name).style.zIndex = z;
  }
  map.getPane("labels").style.pointerEvents = "none";
  map.getPane("shade").style.pointerEvents = "none";
  L.tileLayer(IMAGERY, { maxZoom: 13, attribution: "Imagery © Esri, Maxar, Earthstar Geographics" }).addTo(map);
  L.tileLayer(LABELS, { maxZoom: 13, pane: "labels", opacity: 0.4, attribution: "borders and names © Esri" }).addTo(map);

  // Everything outside the countries that can be explored is shaded.
  const holes = [];
  for (const country of Object.values(geodata.countries)) {
    for (const polygon of country.polygons) holes.push(polygon[0]);
  }
  L.polygon([[[-89, -360], [-89, 360], [89, 360], [89, -360]], ...holes],
    { pane: "shade", stroke: false, fillColor: "#000000", fillOpacity: 0.7, interactive: false }).addTo(map);

  let shown = { country: null, river: null };
  let rivers = {}; // country code -> saved gauge metadata, with raw gauge IDs
  let courses = {}; // country + raw gauge ID -> source-backed GeoJSON lines
  let courseCredit = false;
  const countryLayers = {}, countryLabels = {};
  for (const code in geodata.countries) {
    const country = geodata.countries[code];
    const layer = L.polygon(country.polygons, { pane: "countries", color: COLOR.border,
      weight: 0.7, opacity: 0.35, fillColor: "#fff", fillOpacity: 0 }).addTo(map);
    layer.on("click", () => { if (shown.country !== code) handlers.country(code); });
    countryLayers[code] = layer;
    const b = country.bounds;
    const at = code === "NO" ? [61.3, 9.0] : [(b[0][0] + b[1][0]) / 2, (b[0][1] + b[1][1]) / 2];
    const label = L.marker(at, { pane: "points", icon: L.divIcon({ className: "", iconSize: [0, 0],
      html: `<div class="map-label">${esc(country.name)}</div>` }) });
    label.on("click", () => handlers.country(code));
    countryLabels[code] = label;
  }

  const riverLayer = L.layerGroup().addTo(map);
  const back = L.control({ position: "topleft" });
  back.onAdd = () => {
    const el = L.DomUtil.create("div", "map-back");
    el.textContent = "← Europe";
    el.setAttribute("role", "button");
    L.DomEvent.disableClickPropagation(el);
    L.DomEvent.on(el, "click", () => handlers.europe());
    return el;
  };

  function courseFor(river) {
    return courses[key(river.country || shown.country, river.id)];
  }

  function tip(river) {
    const detail = [river.place, river.id].filter(Boolean).map(esc).join(" · ");
    const at = position(river), course = courseFor(river);
    const coordinates = at ? `<small>Gauge ${at[0].toFixed(5)}, ${at[1].toFixed(5)}</small>` : '';
    const source = course?.properties?.match_method === 'station_position_only'
      ? '<small>Channel matched by station position; river name differs.</small>' : '';
    const extent = course ? '<small>Mapped sections; source and mouth not verified.</small>' : '';
    return { html: `${esc(river.name || river.label || river.id)}<small>${detail}</small>${coordinates}${source}${extent}`,
      options: { sticky: true, direction: "top", offset: [0, -8], className: "map-tip" } };
  }

  function drawRivers() {
    riverLayer.clearLayers();
    if (!shown.country) return;
    // Several gauges can share the same upstream channel. Keep the selected
    // course and its hit target above the others, regardless of list order.
    const ordered = [...(rivers[shown.country] || [])].sort((a, b) =>
      Number(String(a.id) === shown.river) - Number(String(b.id) === shown.river));
    for (const river of ordered) {
      const selected = String(river.id) === shown.river, dim = shown.river && !selected;
      const pick = () => { if (!selected) handlers.river(String(river.id)); };
      const hint = tip(river), course = courseFor(river), at = position(river);
      if (course) {
        const core = L.geoJSON(course, { pane: "rivers", style: { color: selected ? COLOR.selected : COLOR.river,
          weight: selected ? 3.2 : 1.6, opacity: dim ? 0.5 : 1, interactive: false,
          lineCap: "butt", lineJoin: "miter" } });
        const hit = L.geoJSON(course, { pane: "rivers", style: { color: "#fff", weight: 18, opacity: 0 } });
        hit.bindTooltip(hint.html, hint.options);
        hit.on("mouseover", () => { if (!selected) core.setStyle({ weight: 3.2, opacity: 1 }); });
        hit.on("mouseout", () => { if (!selected) core.setStyle({ weight: 1.6, opacity: dim ? 0.5 : 1 }); });
        hit.on("click", pick);
        riverLayer.addLayer(core).addLayer(hit);
      }
      if (at) {
        // Gauges are square marks, as on a survey map.
        const point = L.marker(at, { pane: "points", icon: L.divIcon({ className: "", iconSize: [9, 9], iconAnchor: [5, 5],
          html: `<div class="gauge${selected ? " sel" : dim ? " dim" : ""}"></div>` }) });
        point.bindTooltip(hint.html, hint.options);
        point.on("click", pick);
        riverLayer.addLayer(point);
        if (selected) {
          riverLayer.addLayer(L.tooltip({ permanent: true, direction: "top", className: "map-tip selected", offset: [0, -10] })
            .setLatLng(at).setContent(esc(river.name || river.label || river.id)));
        }
      }
    }
  }

  function target() {
    const river = shown.river && (rivers[shown.country] || []).find((r) => String(r.id) === shown.river);
    if (river) {
      const course = courseFor(river), at = position(river);
      if (course) {
        const bounds = L.geoJSON(course).getBounds();
        if (at) bounds.extend(at);
        if (bounds.isValid()) return { bounds: bounds.pad(0.35), maxZoom: 12 };
      }
      if (at) return { bounds: L.latLng(at).toBounds(30000), maxZoom: 11 };
    }
    if (shown.country && geodata.countries[shown.country]) {
      return { bounds: L.latLngBounds(geodata.countries[shown.country].bounds).pad(0.06), maxZoom: 9 };
    }
    return { bounds: L.latLngBounds(EUROPE), maxZoom: 9 };
  }

  function fit(animate = false) {
    if (!element.clientWidth) return;
    const { bounds, maxZoom } = target();
    map.invalidateSize({ pan: false });
    if (animate) map.flyToBounds(bounds, { maxZoom, duration: 1.0, easeLinearity: 0.2 });
    else map.fitBounds(bounds, { maxZoom, animate: false });
  }

  function show(next) {
    const country = next.country ? String(next.country).toUpperCase() : null;
    const river = next.river == null ? null : String(next.river);
    const changed = country !== shown.country || river !== shown.river;
    const first = !map._loaded;
    shown = { country, river };
    for (const code in countryLabels) {
      if (shown.country) map.removeLayer(countryLabels[code]); else countryLabels[code].addTo(map);
      countryLayers[code].setStyle({ opacity: 0.35, weight: 0.7, fillOpacity: 0 });
    }
    if (shown.country) back.addTo(map); else back.remove();
    drawRivers();
    if (first || changed) fit(!first);
  }

  // Keep the view sensible when the map expands or its divider is dragged.
  let resizeTimer = null;
  new ResizeObserver(() => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => fit(false), 120);
  }).observe(element);

  fit(false);
  return {
    show,
    fit,
    setRivers(byCountry) {
      rivers = Object.fromEntries(Object.entries(byCountry || {}).map(([code, values]) => [code.toUpperCase(), values]));
      drawRivers();
    },
    setCourses(collection) {
      courses = {};
      for (const feature of collection?.features || []) {
        if (!["LineString", "MultiLineString"].includes(feature.geometry?.type)) continue;
        const properties = feature.properties || {};
        if (properties.country == null || properties.id == null) continue;
        courses[key(properties.country, properties.id)] = feature;
      }
      if (Object.keys(courses).length && !courseCredit) {
        map.attributionControl.addAttribution('rivers © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap contributors</a>');
        courseCredit = true;
      }
      drawRivers();
      if (shown.river) fit(false);
    },
  };
}
