// The graph: every ticked variable as a coloured line in one picture.
// Variables with the same unit share an axis; each unit gets its own axis,
// alternating left and right. Drawn by hand as SVG, no chart library.

const SVG_NS = "http://www.w3.org/2000/svg";
export const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const MONTHS_LONG = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
  "October", "November", "December"];
const AXIS_WIDTH = 52;
const INK_2 = "#555c58", INK_3 = "#8b918c", LINE = "#e3dfd5", LINE_STRONG = "#cbc5b8", IMAGINARY = "#9a5b12";

export function esc(text) {
  return String(text ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// About three meaningful digits, with a real minus sign.
export function fmt(value) {
  if (value == null || !isFinite(value)) return "—";
  const size = Math.abs(value);
  const digits = size >= 100 ? 0 : size >= 10 ? 1 : size >= 1 ? 2 : 3;
  let text = value.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: digits });
  if (Number(text.replace(/,/g, "")) === 0) text = "0";
  return text.replace("-", "−");
}

function node(name, attrs, parent) {
  const element = document.createElementNS(SVG_NS, name);
  for (const key in attrs) element.setAttribute(key, attrs[key]);
  if (parent) parent.appendChild(element);
  return element;
}

const ROUND_STEPS = [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10];

function niceStep(raw) {
  const power = Math.pow(10, Math.floor(Math.log10(raw)));
  return ROUND_STEPS.find((step) => step >= raw / power - 1e-9) * power;
}

// A scale with round tick values. Quantities that cannot be negative start at zero.
// With `intervals`, the scale has exactly that many steps, so several axes can share
// the same horizontal lines.
function scaleFor(values, intervals) {
  let min = Math.min(...values), max = Math.max(...values);
  if (!isFinite(min) || !isFinite(max)) { min = 0; max = 1; }
  if (min >= 0) min = 0;
  if (max <= min) max = min + 1;
  let step = niceStep((max - min) / (intervals || 4));
  let lo = Math.floor(min / step + 1e-9) * step;
  while (intervals && lo + intervals * step < max - step * 1e-9) {
    step = niceStep(step * 1.01);
    lo = Math.floor(min / step + 1e-9) * step;
  }
  const hi = intervals ? lo + intervals * step : Math.ceil(max / step - 1e-9) * step;
  const ticks = [];
  for (let t = lo; t <= hi + step / 2; t += step) ticks.push(Math.abs(t) < step / 1e6 ? 0 : t);
  return { lo, hi, ticks };
}

function daysBeforeMonths(year) {
  const starts = [];
  for (let m = 0; m < 12; m++) starts.push(Math.round((Date.UTC(year, m, 1) - Date.UTC(year, 0, 1)) / 864e5));
  return starts;
}

// Predictions are dashed, imaginary data is dotted, measurements are solid.
function dash(series, monthly) {
  if (series.predicted) return "7 5";
  if (series.imaginary) return monthly ? "0.1 5.5" : "0.1 3.6";
  return null;
}

// The legend above the graph: one entry per line, in the line's colour and style.
export function legendHTML(series, requirement) {
  const items = series.map((s) => {
    const style = s.predicted ? "dashed" : s.imaginary ? "dotted" : "";
    const empty = s.values.every((v) => v == null);
    const tags = (s.imaginary ? ` <span class="imaginary">imaginary${s.predicted ? " prediction" : ""}</span>` : "")
      + (empty ? ' <span class="unit">no data this year</span>' : "");
    return `<span class="legend-item" style="--c:${s.color}"><i class="legend-line ${style}"></i>${esc(s.label)}`
      + ` <span class="unit">${esc(s.unit)}</span>${tags}</span>`;
  });
  if (requirement) {
    items.push(`<span class="legend-item" style="--c:${IMAGINARY}"><i class="legend-line dashed"></i>`
      + `${esc(requirement.name)} needed <span class="imaginary">imaginary</span></span>`);
  }
  return items.join("");
}

// data: { x: {kind: "months" | "days", count, year}, series: [...] }
// options: { height, requirement: {values (12), unit, name} }
export function drawChart(host, data, options = {}) {
  host.innerHTML = "";
  const width = Math.max(host.clientWidth, 300);
  const height = options.height || 320;
  const series = data.series.filter((s) => s.values.some((v) => v != null));
  const { count, year } = data.x;
  const monthly = data.x.kind === "months";
  const monthStarts = daysBeforeMonths(year);
  const monthOf = (i) => (monthly ? i : monthStarts.findLastIndex((start) => i >= start));

  // One axis per unit.
  const groups = [];
  for (const s of series) {
    let group = groups.find((g) => g.unit === s.unit);
    if (!group) groups.push(group = { unit: s.unit, series: [] });
    group.series.push(s);
  }
  const requirement = options.requirement && groups.some((g) => g.unit === options.requirement.unit)
    ? options.requirement : null;
  groups.forEach((group, index) => {
    group.side = index % 2 === 0 ? "left" : "right";
    group.slot = Math.floor(index / 2);
    const values = [];
    for (const s of group.series) {
      for (const v of s.values) if (v != null) values.push(v);
      for (const v of s.usual || []) if (v != null) values.push(v);
    }
    if (requirement && requirement.unit === group.unit) values.push(...requirement.values);
    group.scale = scaleFor(values, height >= 400 ? 5 : 4);
  });

  const leftAxes = Math.max(1, Math.ceil(groups.length / 2)), rightAxes = Math.floor(groups.length / 2);
  const left = 6 + AXIS_WIDTH * leftAxes, right = Math.max(14, 6 + AXIS_WIDTH * rightAxes);
  const top = 26, bottom = 26;
  const plotW = width - left - right, plotH = height - top - bottom;
  const x = (i) => left + plotW * (i + 0.5) / count;
  for (const group of groups) {
    const { lo, hi } = group.scale;
    group.y = (v) => top + plotH * (1 - (v - lo) / (hi - lo));
  }

  const svg = node("svg", { viewBox: `0 0 ${width} ${height}`, height, role: "img" }, host);

  // Horizontal lines follow the first axis.
  if (groups.length) {
    for (const tick of groups[0].scale.ticks) {
      const y = groups[0].y(tick);
      node("line", { x1: left, x2: left + plotW, y1: y, y2: y, stroke: tick === 0 ? LINE_STRONG : LINE }, svg);
    }
  } else {
    node("line", { x1: left, x2: left + plotW, y1: top + plotH, y2: top + plotH, stroke: LINE_STRONG }, svg);
  }

  // Months along the bottom.
  for (let m = 0; m < 12; m++) {
    const from = monthly ? left + plotW * m / 12 : left + plotW * monthStarts[m] / count;
    const to = monthly ? left + plotW * (m + 1) / 12 : left + plotW * (m === 11 ? count : monthStarts[m + 1]) / count;
    if (!monthly && m > 0) node("line", { x1: from, x2: from, y1: top + plotH, y2: top + plotH + 4, stroke: LINE_STRONG }, svg);
    const label = node("text", { x: (from + to) / 2, y: height - 8, "text-anchor": "middle" }, svg);
    label.textContent = plotW / 12 >= 30 ? MONTHS[m] : MONTHS[m][0];
  }

  // The axes, each in the colour of its line when it has only one.
  for (const group of groups) {
    const color = group.series.length === 1 ? group.series[0].color : INK_2;
    const at = group.side === "left" ? left - 7 - group.slot * AXIS_WIDTH : left + plotW + 7 + group.slot * AXIS_WIDTH;
    const anchor = group.side === "left" ? "end" : "start";
    const unit = node("text", { x: at, y: top - 12, "text-anchor": anchor, style: `fill:${color};font-weight:600` }, svg);
    unit.textContent = group.unit;
    for (const tick of group.scale.ticks) {
      const text = node("text", { x: at, y: group.y(tick) + 4, "text-anchor": anchor, style: `fill:${color}` }, svg);
      text.textContent = fmt(tick);
    }
  }

  // The requirement of the risk assessment, with the shortfall shaded.
  const flowGroup = requirement && groups.find((g) => g.unit === requirement.unit);
  if (flowGroup) {
    const flow = flowGroup.series.find((s) => s.id === "discharge");
    const half = plotW / count / 2;
    if (flow) {
      for (let i = 0; i < count; i++) {
        const value = flow.values[i], need = requirement.values[monthOf(i)];
        if (value == null || value >= need) continue;
        const band = monthly ? half * 0.9 : half;
        node("rect", { x: x(i) - band, width: band * 2, y: flowGroup.y(need),
          height: Math.max(0, flowGroup.y(value) - flowGroup.y(need)), fill: IMAGINARY, opacity: 0.16 }, svg);
      }
    }
    let path = "";
    for (let i = 0; i < count; i++) {
      const y = flowGroup.y(requirement.values[monthOf(i)]);
      path += `${i ? "L" : "M"}${x(i) - half} ${y}L${x(i) + half} ${y}`;
    }
    node("path", { d: path, fill: "none", stroke: IMAGINARY, "stroke-width": 1.3, "stroke-dasharray": "5 4" }, svg);
  }

  // The lines. A missing value leaves a gap; it is never drawn as zero.
  const linePath = (values, y) => {
    let path = "", pen = false;
    values.forEach((v, i) => {
      if (v == null) { pen = false; return; }
      path += `${pen ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`;
      pen = true;
    });
    return path;
  };
  for (const group of groups) {
    for (const s of group.series) {
      if (s.usual) {
        node("path", { d: linePath(s.usual, group.y), fill: "none", stroke: s.color, "stroke-width": 1.1,
          "stroke-dasharray": "3 4", opacity: 0.5 }, svg);
      }
    }
  }
  for (const group of groups) {
    for (const s of group.series) {
      const attrs = { d: linePath(s.values, group.y), fill: "none", stroke: s.color,
        "stroke-width": monthly ? 2.2 : 1.4, "stroke-linejoin": "round", "stroke-linecap": "round" };
      const pattern = dash(s, monthly);
      if (pattern) { attrs["stroke-dasharray"] = pattern; if (!s.predicted) attrs["stroke-width"] = monthly ? 2.6 : 1.8; }
      node("path", attrs, svg);
      if (monthly) {
        s.values.forEach((v, i) => {
          if (v != null) node("circle", { cx: x(i), cy: group.y(v), r: 2.7, fill: s.predicted ? "#fdfcfa" : s.color,
            stroke: s.color, "stroke-width": 1.4 }, svg);
        });
      }
    }
  }

  // Pointing at the graph shows the values at that month or day.
  const guide = node("line", { y1: top, y2: top + plotH, stroke: INK_3, "stroke-dasharray": "2 3", visibility: "hidden" }, svg);
  const marks = node("g", {}, svg);
  const tip = document.createElement("div");
  tip.className = "tip";
  tip.hidden = true;
  host.appendChild(tip);
  const surface = node("rect", { x: left, y: top, width: plotW, height: plotH, fill: "transparent" }, svg);

  surface.addEventListener("pointermove", (event) => {
    const box = svg.getBoundingClientRect();
    const px = (event.clientX - box.left) * (width / box.width);
    const i = Math.min(count - 1, Math.max(0, Math.floor((px - left) / plotW * count)));
    guide.setAttribute("x1", x(i));
    guide.setAttribute("x2", x(i));
    guide.setAttribute("visibility", "visible");
    marks.innerHTML = "";
    const title = monthly ? `${MONTHS_LONG[i]} ${year}`
      : new Date(Date.UTC(year, 0, 1 + i)).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
    let rows = "";
    for (const group of groups) {
      for (const s of group.series) {
        const value = s.values[i];
        if (value != null) node("circle", { cx: x(i), cy: group.y(value), r: 4, fill: s.color, stroke: "#fdfcfa", "stroke-width": 1.5 }, marks);
        const usual = s.usual && s.usual[i] != null ? ` <span class="unit">usual ${fmt(s.usual[i])}</span>` : "";
        rows += `<div class="tip-row" style="--c:${s.color}"><i></i>${esc(s.label)}${s.imaginary ? ' <span class="imaginary">imaginary</span>' : ""}`
          + `<b>${value == null ? "no data" : fmt(value) + " " + esc(s.unit)}</b>${usual}</div>`;
      }
    }
    if (flowGroup) {
      rows += `<div class="tip-row" style="--c:${IMAGINARY}"><i></i>${esc(requirement.name)} needed`
        + `<b>${fmt(requirement.values[monthOf(i)])} ${esc(requirement.unit)}</b></div>`;
    }
    tip.innerHTML = `<div class="tip-title">${title}</div>${rows}`;
    tip.hidden = false;
    const scale = box.width / width;
    const tipWidth = tip.offsetWidth;
    const at = x(i) * scale;
    tip.style.left = `${at + 16 + tipWidth > box.width ? Math.max(0, at - tipWidth - 16) : at + 16}px`;
    tip.style.top = `${top}px`;
  });
  surface.addEventListener("pointerleave", () => {
    guide.setAttribute("visibility", "hidden");
    marks.innerHTML = "";
    tip.hidden = true;
  });
}

// A small bar for every year, e.g. days below the requirement. Clicking a bar picks that year.
export function drawYearBars(host, years, values, selectedYear, onPick) {
  host.innerHTML = "";
  const width = Math.max(host.clientWidth, 260), height = 86;
  const left = 30, right = 6, top = 8, bottom = 18;
  const plotW = width - left - right, plotH = height - top - bottom;
  const max = Math.max(1, ...values.filter((v) => v != null));
  const scale = scaleFor([0, max]);
  const step = plotW / years.length;
  const svg = node("svg", { viewBox: `0 0 ${width} ${height}`, height, role: "img" }, host);
  for (const tick of [0, scale.hi]) {
    const y = top + plotH * (1 - tick / scale.hi);
    node("line", { x1: left, x2: left + plotW, y1: y, y2: y, stroke: tick ? LINE : LINE_STRONG }, svg);
    const text = node("text", { x: left - 6, y: y + 4, "text-anchor": "end", "font-size": 11, fill: INK_3 }, svg);
    text.textContent = fmt(tick);
  }
  years.forEach((year, i) => {
    const value = values[i];
    const barHeight = value == null ? 0 : plotH * value / scale.hi;
    const bar = node("rect", {
      x: left + i * step + step * 0.14, width: step * 0.72,
      y: value == null ? top + plotH - 2 : top + plotH - Math.max(barHeight, 1), height: value == null ? 2 : Math.max(barHeight, 1),
      fill: year === selectedYear ? "#1d2220" : value == null ? LINE_STRONG : "#b4bab5", rx: 1,
    }, svg);
    node("title", {}, bar).textContent = value == null ? `${year}: not enough measurements` : `${year}: ${value} days`;
    bar.addEventListener("click", () => onPick(year));
    if (i === 0 || i === years.length - 1 || year === selectedYear) {
      const text = node("text", { x: left + (i + 0.5) * step, y: height - 4, "font-size": 11,
        "text-anchor": i === 0 ? "start" : i === years.length - 1 ? "end" : "middle",
        fill: year === selectedYear ? "#1d2220" : INK_3, "font-weight": year === selectedYear ? 600 : 400 }, svg);
      const nearEdge = year === selectedYear && (i < 4 || i > years.length - 5) && i !== 0 && i !== years.length - 1;
      if (!nearEdge) text.textContent = year;
    }
  });
}
