// The satellite map: Europe with Norway and Switzerland lit, then the rivers
// of the chosen country, then the chosen river. Uses Leaflet (kept in vendor/).

const EUROPE = [[43.0, -4.0], [71.6, 30.0]];
const IMAGERY = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";
const LABELS = "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}";
const COLOR = { border: "#eaf4fb", river: "#7fc8f5", selected: "#ffd166", outline: "#ffffff" };

// geodata: outlines of the lit countries and the lines of the large rivers.
// handlers: { country(code), river(id), europe() }
export function createMap(element, geodata, handlers) {
  if (typeof L === "undefined") {
    element.innerHTML = '<div class="map-error">The map could not be loaded.</div>';
    return { show() {}, setRivers() {}, setOutlines() {} };
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
  L.tileLayer(LABELS, { maxZoom: 13, pane: "labels", attribution: "borders and names © Esri" }).addTo(map);
  if (Object.values(geodata.rivers).flat().some((river) => river.course === "OpenStreetMap")) {
    map.attributionControl.addAttribution("rivers © OpenStreetMap contributors");
  }

  // Everything outside the countries that can be explored is shaded.
  const holes = [];
  for (const code in geodata.countries) for (const polygon of geodata.countries[code].polygons) holes.push(polygon[0]);
  L.polygon([[[-89, -360], [-89, 360], [89, 360], [89, -360]], ...holes],
    { pane: "shade", stroke: false, fillColor: "#05090d", fillOpacity: 0.62, interactive: false }).addTo(map);

  let shown = { country: null, river: null };
  let rivers = {};      // country code -> [{id, name, place, measured, lat, lon}]
  let outlines = {};    // river id -> rings of its catchment
  const lines = {};     // river id -> {lines, bounds} of the large rivers
  for (const code in geodata.rivers) {
    for (const river of geodata.rivers[code]) lines[`${code.toLowerCase()}-${river.id}`] = river;
  }

  const countryLayers = {}, countryLabels = {};
  for (const code in geodata.countries) {
    const country = geodata.countries[code];
    const layer = L.polygon(country.polygons, { pane: "countries", color: COLOR.border, weight: 1.4, fillColor: "#fff", fillOpacity: 0 }).addTo(map);
    layer.on("mouseover", () => { if (shown.country !== code) layer.setStyle({ fillOpacity: 0.14 }); });
    layer.on("mouseout", () => layer.setStyle({ fillOpacity: 0 }));
    layer.on("click", () => { if (shown.country !== code) handlers.country(code); });
    countryLayers[code] = layer;
    const b = country.bounds;
    const at = code === "NO" ? [61.3, 9.0] : [(b[0][0] + b[1][0]) / 2, (b[0][1] + b[1][1]) / 2];
    const label = L.marker(at, { pane: "points", icon: L.divIcon({ className: "", iconSize: [0, 0], html: `<div class="map-label">${country.name}</div>` }) });
    label.on("click", () => handlers.country(code));
    countryLabels[code] = label;
  }

  const riverLayer = L.layerGroup().addTo(map);
  const back = L.control({ position: "topleft" });
  back.onAdd = () => {
    const el = L.DomUtil.create("div", "map-back");
    el.textContent = "← Europe";
    L.DomEvent.disableClickPropagation(el);
    L.DomEvent.on(el, "click", () => handlers.europe());
    return el;
  };

  function tip(river, selected) {
    const sub = selected ? "" : `<small>${river.measured ? river.place : "imaginary data"}</small>`;
    return { html: `${river.name}${sub}`, options: { sticky: true, direction: "top", offset: [0, -8], className: "map-tip" } };
  }

  function drawRivers() {
    riverLayer.clearLayers();
    if (!shown.country) return;
    for (const river of rivers[shown.country] || []) {
      const selected = river.id === shown.river, dim = shown.river && !selected;
      const pick = () => { if (!selected) handlers.river(river.id); };
      const hint = tip(river, selected);
      if (lines[river.id]) {
        const geometry = lines[river.id].lines;
        const core = L.polyline(geometry, { pane: "rivers", color: selected ? COLOR.selected : COLOR.river,
          weight: selected ? 3.4 : 2.2, opacity: dim ? 0.55 : 1, interactive: false, lineCap: "round", lineJoin: "round" });
        const hit = L.polyline(geometry, { pane: "rivers", color: "#fff", weight: 18, opacity: 0 });
        hit.bindTooltip(hint.html, hint.options);
        hit.on("mouseover", () => { if (!selected) core.setStyle({ weight: 3.6, opacity: 1 }); });
        hit.on("mouseout", () => { if (!selected) core.setStyle({ weight: 2.2, opacity: dim ? 0.55 : 1 }); });
        hit.on("click", pick);
        riverLayer.addLayer(core).addLayer(hit);
      } else {
        // A measured mountain river: its upstream catchment and its measuring point.
        let area = null;
        if (outlines[river.id]) {
          area = L.polygon(outlines[river.id], { pane: "rivers", color: selected ? COLOR.selected : COLOR.outline,
            weight: selected ? 2.4 : 1.2, opacity: dim ? 0.5 : 0.95, fillColor: selected ? COLOR.selected : "#fff",
            fillOpacity: selected ? 0.12 : dim ? 0.08 : 0.2 });
          area.bindTooltip(hint.html, hint.options);
          area.on("mouseover", () => { if (!selected) area.setStyle({ fillOpacity: 0.42, weight: 2 }); });
          area.on("mouseout", () => { if (!selected) area.setStyle({ fillOpacity: dim ? 0.08 : 0.2, weight: 1.2 }); });
          area.on("click", pick);
          riverLayer.addLayer(area);
        }
        if (river.lat != null && river.lon != null) {
          const point = L.circleMarker([river.lat, river.lon], { pane: "points", radius: selected ? 6 : 4.2,
            color: "#1d2220", weight: 1.2, fillColor: selected ? COLOR.selected : "#fff", fillOpacity: dim ? 0.6 : 1 });
          point.bindTooltip(hint.html, hint.options);
          point.on("click", pick);
          riverLayer.addLayer(point);
        }
      }
      if (selected) {
        const at = riverAnchor(river);
        if (at) {
          riverLayer.addLayer(L.tooltip({ permanent: true, direction: "top", className: "map-tip selected", offset: [0, -8] })
            .setLatLng(at).setContent(river.name));
        }
      }
    }
  }

  function riverAnchor(river) {
    if (river.lat != null && river.lon != null) return [river.lat, river.lon];
    const entry = lines[river.id];
    if (!entry) return null;
    const b = entry.bounds, mid = [(b[0][0] + b[1][0]) / 2, (b[0][1] + b[1][1]) / 2];
    let best = null, distance = Infinity;
    for (const line of entry.lines) {
      for (const p of line) {
        const d = (p[0] - mid[0]) ** 2 + (p[1] - mid[1]) ** 2;
        if (d < distance) { distance = d; best = p; }
      }
    }
    return best;
  }

  function target() {
    const river = shown.river && (rivers[shown.country] || []).find((r) => r.id === shown.river);
    if (river) {
      if (lines[river.id]) return { bounds: L.latLngBounds(lines[river.id].bounds).pad(0.35), maxZoom: 10 };
      if (outlines[river.id]) return { bounds: L.polygon(outlines[river.id]).getBounds().pad(0.5), maxZoom: 12 };
      if (river.lat != null) return { bounds: L.latLng(river.lat, river.lon).toBounds(30000), maxZoom: 11 };
    }
    if (shown.country) return { bounds: L.latLngBounds(geodata.countries[shown.country].bounds).pad(0.06), maxZoom: 9 };
    return { bounds: L.latLngBounds(EUROPE), maxZoom: 9 };
  }

  function fit(animate) {
    const { bounds, maxZoom } = target();
    if (animate) map.flyToBounds(bounds, { maxZoom, duration: 1.0, easeLinearity: 0.2 });
    else map.fitBounds(bounds, { maxZoom, animate: false });
  }

  function show(next) {
    const changed = next.country !== shown.country || next.river !== shown.river;
    const first = !map._loaded;
    shown = { country: next.country, river: next.river };
    for (const code in countryLabels) {
      if (shown.country) map.removeLayer(countryLabels[code]); else countryLabels[code].addTo(map);
      countryLayers[code].setStyle({ opacity: !shown.country || code === shown.country ? 0.9 : 0.4,
        weight: shown.country ? 1.1 : 1.4 });
    }
    if (shown.country) back.addTo(map); else back.remove();
    drawRivers();
    if (first || changed) fit(!first);
  }

  // Keep the view sensible when the map's box changes size (expanding, dragging the divider).
  let resizeTimer = null;
  new ResizeObserver(() => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      if (!element.clientWidth) return;
      map.invalidateSize({ pan: false });
      fit(false);
    }, 120);
  }).observe(element);

  fit(false);
  return {
    show,
    setRivers(byCountry) { rivers = byCountry; drawRivers(); },
    setOutlines(byRiver) { outlines = byRiver || {}; drawRivers(); if (shown.river) fit(true); },
  };
}
