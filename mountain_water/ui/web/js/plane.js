// The volatility plane: quantity change, timing change and year-to-year
// variation as a small 3D picture. Drag it to turn it.

import { fmt } from "./chart.js";

const SVG_NS = "http://www.w3.org/2000/svg";
const INK = "#1d2220", INK_3 = "#8b918c", LINE = "#d9d4c8", ACCENT = "#1f5c7a";
const ROUND_STEPS = [1, 1.5, 2, 3, 4, 5, 6, 8, 10];

function node(name, attrs, parent) {
  const element = document.createElementNS(SVG_NS, name);
  for (const key in attrs) element.setAttribute(key, attrs[key]);
  if (parent) parent.appendChild(element);
  return element;
}

function roundUp(value, floor) {
  const size = Math.max(value, floor);
  const power = Math.pow(10, Math.floor(Math.log10(size)));
  return ROUND_STEPS.find((step) => step >= size / power - 1e-9) * power;
}

// plane: { point: {x, y, z} | null, others: [{name, x, y, z}], axes: {x, y, z} }
export function drawPlane(host, plane, ownName) {
  host.innerHTML = "";
  const W = 420, H = 296, S = 112, cx = W / 2 + 30, cy = 118;
  const svg = node("svg", { viewBox: `0 36 ${W} ${H - 36}`, role: "img" }, host);
  const all = [...plane.others, ...(plane.point ? [plane.point] : [])];
  const xr = roundUp(Math.max(...all.map((p) => Math.abs(p.x)), 0), 2);
  const yr = roundUp(Math.max(...all.map((p) => Math.abs(p.y)), 0), 2);
  const zr = roundUp(Math.max(...all.map((p) => p.z), 0), 10);
  let turn = -0.62, tilt = 0.52;

  const project = (nx, ny, nz) => {
    const across = nx * Math.cos(turn) - ny * Math.sin(turn);
    const away = nx * Math.sin(turn) + ny * Math.cos(turn);
    return [cx + across * S, cy - (nz * Math.cos(tilt) * 0.62 + away * Math.sin(tilt)) * S, away];
  };
  const place = (p) => project(p.x / xr, p.y / yr, (p.z / zr) * 2 - 1);
  const line = (a, b, attrs) => node("line", { x1: a[0], y1: a[1], x2: b[0], y2: b[1], ...attrs }, svg);
  const label = (at, text, attrs = {}) => {
    const t = node("text", { x: at[0], y: at[1], "text-anchor": "middle", ...attrs }, svg);
    t.textContent = text;
    return t;
  };

  function draw() {
    svg.innerHTML = "";
    // The floor: a grid, with the zero lines a little stronger.
    for (let k = -2; k <= 2; k++) {
      const v = k / 2, zero = k === 0;
      const style = { stroke: zero ? INK_3 : LINE, "stroke-width": 1, ...(zero ? { "stroke-dasharray": "3 3" } : {}) };
      line(project(v, -1, -1), project(v, 1, -1), style);
      line(project(-1, v, -1), project(1, v, -1), style);
    }
    // The upright axis stands on the left-most corner.
    const corners = [[-1, -1], [1, -1], [1, 1], [-1, 1]];
    const post = corners.reduce((a, b) => (project(a[0], a[1], -1)[0] < project(b[0], b[1], -1)[0] ? a : b));
    const foot = project(post[0], post[1], -1), head = project(post[0], post[1], 1);
    line(foot, head, { stroke: INK_3 });
    label([head[0] - 8, head[1] + 2], `${fmt(zr)} %`, { "text-anchor": "end" });
    label([foot[0] - 8, foot[1] + 2], "0", { "text-anchor": "end" });
    label([(foot[0] + head[0]) / 2 - 10, (foot[1] + head[1]) / 2], "variation", { "text-anchor": "end", style: "font-style:italic" });

    // Names along the two floor edges nearest to the viewer.
    const nearY = Math.cos(turn) > 0 ? -1 : 1, nearX = Math.sin(turn) > 0 ? -1 : 1;
    const below = (p) => [p[0], p[1] + 15];
    label(below(project(-0.8, nearY * 1.1, -1)), `−${fmt(xr)} %`);
    label(below(project(0.8, nearY * 1.1, -1)), `+${fmt(xr)} %`);
    label(below(project(0, nearY * 1.3, -1)), "less water ← quantity → more", { style: "font-style:italic" });
    label(below(project(nearX * 1.1, -0.8, -1)), `−${fmt(yr)} d`);
    label(below(project(nearX * 1.1, 0.8, -1)), `+${fmt(yr)} d`);
    label(below(project(nearX * 1.36, 0, -1)), "earlier ← timing → later", { style: "font-style:italic" });

    // The other measured rivers, far ones first.
    const others = plane.others.map((p) => ({ p, at: place(p) })).sort((a, b) => b.at[2] - a.at[2]);
    for (const { p, at } of others) {
      const dot = node("circle", { cx: at[0], cy: at[1], r: 2.6, fill: INK_3, opacity: 0.6 }, svg);
      node("title", {}, dot).textContent =
        `${p.name}: ${fmt(p.x)} % per decade, ${fmt(p.y)} days per decade, varies ${fmt(p.z)} %`;
    }
    // This river, with a line down to the floor so its height can be read.
    if (plane.point) {
      const at = place(plane.point);
      const shadow = project(plane.point.x / xr, plane.point.y / yr, -1);
      line(shadow, at, { stroke: ACCENT, "stroke-dasharray": "2 3" });
      node("circle", { cx: shadow[0], cy: shadow[1], r: 2.2, fill: "none", stroke: ACCENT }, svg);
      node("circle", { cx: at[0], cy: at[1], r: 5.5, fill: ACCENT, stroke: "#fdfcfa", "stroke-width": 1.6 }, svg);
      label([at[0], at[1] - 11], ownName, { style: `fill:${INK};font-weight:600;paint-order:stroke;stroke:#fdfcfa;stroke-width:3px` });
    }
  }

  let grab = null;
  svg.addEventListener("pointerdown", (event) => {
    grab = { x: event.clientX, y: event.clientY, turn, tilt };
    svg.setPointerCapture(event.pointerId);
  });
  svg.addEventListener("pointermove", (event) => {
    if (!grab) return;
    turn = grab.turn + (event.clientX - grab.x) * 0.01;
    tilt = Math.min(1.2, Math.max(0.12, grab.tilt + (event.clientY - grab.y) * 0.008));
    draw();
  });
  svg.addEventListener("pointerup", () => { grab = null; });
  svg.addEventListener("pointercancel", () => { grab = null; });
  draw();
}
