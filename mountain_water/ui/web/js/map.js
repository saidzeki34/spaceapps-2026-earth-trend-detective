// Display only: real gauge points and stored river courses, never catchment polygons.
const IMAGERY = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';
const LABELS = 'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}';
const EXTENTS = { ch: [[45.75, 5.9], [47.85, 10.6]], no: [[57.8, 4.2], [71.4, 31.3]] };
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

export function createMap(element, selectGauge) {
  if (!window.L) {
    element.innerHTML = '<div class="map-unavailable">The map library is unavailable. Select gauges from the list.</div>';
    return { setData() {}, fit() {} };
  }
  const map = L.map(element, { zoomControl: true, maxZoom: 15, minZoom: 3, zoomSnap: .5, attributionControl: true });
  map.attributionControl.setPrefix(false);
  L.tileLayer(IMAGERY, { maxZoom: 15, attribution: 'Imagery © Esri, Maxar, Earthstar Geographics' }).addTo(map);
  L.tileLayer(LABELS, { maxZoom: 15, attribution: 'Names © Esri' }).addTo(map);
  const layer = L.featureGroup().addTo(map);
  let gauges = [], courses = null, selected = null, region = 'ch', courseCredit = false;
  let bounds = null;

  function fit() {
    if (!element.clientWidth) return;
    map.invalidateSize({ pan: false });
    if (bounds?.isValid()) map.fitBounds(bounds, { padding: [18, 18], maxZoom: selected ? 12 : 9, animate: false });
    else map.fitBounds(EXTENTS[region] || EXTENTS.ch, { padding: [12, 12], animate: false });
  }

  function draw() {
    layer.clearLayers();
    const wanted = new Set(gauges.map((gauge) => String(gauge.id)));
    const selectedLayers = [];
    for (const feature of courses?.features || []) {
      const id = String(feature.properties?.id);
      if (!wanted.has(id) || !['LineString', 'MultiLineString'].includes(feature.geometry?.type)) continue;
      const active = selected === id;
      const line = L.geoJSON(feature, { style: { color: active ? '#ffdf7c' : '#86ccef', weight: active ? 3.2 : 1.8, opacity: selected && !active ? .4 : 1 } });
      const name = [feature.properties?.river, feature.properties?.name].filter(Boolean).join(' — ') || id;
      line.bindTooltip(`${esc(name)}<br>Mapped river segments · OpenStreetMap`);
      line.on('click', () => selectGauge(id));
      layer.addLayer(line);
      if (active) selectedLayers.push(line);
    }
    for (const gauge of gauges) {
      const id = String(gauge.id);
      if (gauge.lat == null || gauge.lon == null || !Number.isFinite(Number(gauge.lat)) || !Number.isFinite(Number(gauge.lon))) continue;
      const active = selected === id;
      const point = L.circleMarker([Number(gauge.lat), Number(gauge.lon)], { radius: active ? 6 : 3.5, color: '#17394f', weight: 1.4, fillColor: active ? '#ffdf7c' : '#fff', fillOpacity: selected && !active ? .55 : 1 });
      point.bindTooltip(esc(gauge.label || `${gauge.name || gauge.river || ''} (${id})`));
      point.on('click', () => selectGauge(id));
      layer.addLayer(point);
      if (active) selectedLayers.push(point);
    }
    if (courses?.features?.length && !courseCredit) {
      map.attributionControl.addAttribution('Rivers © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap contributors</a>');
      courseCredit = true;
    }
    bounds = selectedLayers.length ? L.featureGroup(selectedLayers).getBounds() : layer.getBounds();
    fit();
  }

  new ResizeObserver(() => fit()).observe(element);
  fit();
  return {
    setData(nextGauges, nextCourses, nextSelected, nextRegion) {
      gauges = nextGauges; courses = nextCourses; selected = nextSelected; region = nextRegion;
      draw();
    },
    fit,
  };
}
