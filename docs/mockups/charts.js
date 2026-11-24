// Tiny SVG chart helpers for the static mockups (no libraries).
const SVG_NS = "http://www.w3.org/2000/svg";

function el(name, attrs, text) {
  const node = document.createElementNS(SVG_NS, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (text !== undefined) node.textContent = text;
  return node;
}

/** Vertical bars from the baseline; labels only on the bars listed in `label`. */
function columnChart(target, { labels, values, max, color, height = 200, unit = "", label = [] }) {
  const width = target.clientWidth || 600;
  const pad = { l: 34, r: 8, t: 18, b: 26 };
  const svg = el("svg", { width, height });
  const plotH = height - pad.t - pad.b;
  const step = (width - pad.l - pad.r) / labels.length;
  const barW = Math.min(46, step * 0.6);
  const ticks = 4;
  for (let i = 0; i <= ticks; i++) {
    const v = (max / ticks) * i;
    const y = pad.t + plotH - (v / max) * plotH;
    svg.append(el("line", { x1: pad.l, x2: width - pad.r, y1: y, y2: y, stroke: "var(--grid)" }));
    svg.append(el("text", { x: pad.l - 6, y: y + 4, "text-anchor": "end", class: "axis" }, Math.round(v)));
  }
  labels.forEach((name, i) => {
    const x = pad.l + step * i + (step - barW) / 2;
    const h = (values[i] / max) * plotH;
    const y = pad.t + plotH - h;
    if (h > 0) {
      // Rounded data end, square at the baseline.
      const r = Math.min(4, h);
      svg.append(el("path", {
        d: `M${x},${y + h} V${y + r} Q${x},${y} ${x + r},${y} H${x + barW - r} Q${x + barW},${y} ${x + barW},${y + r} V${y + h} Z`,
        fill: color,
      }));
    }
    if (label.includes(i)) {
      svg.append(el("text", { x: x + barW / 2, y: y - 5, "text-anchor": "middle", class: "val" }, values[i] + unit));
    }
    svg.append(el("text", { x: x + barW / 2, y: height - 8, "text-anchor": "middle", class: "axis" }, name));
  });
  target.append(svg);
}

/** Horizontal bars, one row per category, value label at the end. */
function barChart(target, { labels, values, max, color, unit = "" }) {
  const width = target.clientWidth || 600;
  const rowH = 34, padL = 110, padR = 60;
  const svg = el("svg", { width, height: rowH * labels.length + 6 });
  labels.forEach((name, i) => {
    const y = i * rowH + 6;
    const w = (values[i] / max) * (width - padL - padR);
    svg.append(el("text", { x: padL - 10, y: y + 17, "text-anchor": "end", class: "axis" }, name));
    svg.append(el("rect", { x: padL, y, width: Math.max(w, 2), height: 22, rx: 4, fill: color }));
    svg.append(el("text", { x: padL + w + 8, y: y + 16, class: "val" }, values[i] + unit));
  });
  target.append(svg);
}

/** Stacked horizontal bars (two series) with a 2px surface gap between segments. */
function stackedBars(target, { labels, a, b, colors, total }) {
  const width = target.clientWidth || 600;
  const rowH = 30, padL = 60, padR = 10;
  const svg = el("svg", { width, height: rowH * labels.length + 4 });
  const plotW = width - padL - padR;
  labels.forEach((name, i) => {
    const y = i * rowH + 4;
    const wa = (a[i] / total) * plotW, wb = (b[i] / total) * plotW;
    svg.append(el("text", { x: padL - 10, y: y + 15, "text-anchor": "end", class: "axis" }, name));
    if (wa > 0) svg.append(el("rect", { x: padL, y, width: Math.max(wa - 1, 1), height: 20, rx: 4, fill: colors[0] }));
    if (wb > 0) svg.append(el("rect", { x: padL + wa + 1, y, width: Math.max(wb - 1, 1), height: 20, rx: 4, fill: colors[1] }));
  });
  target.append(svg);
}

/** Heatmap: rows x columns, sequential one-hue scale, count printed in each cell. */
function heatmap(target, { rows, cols, data, scale }) {
  const cellW = 118, cellH = 38, padL = 54, padT = 26;
  const svg = el("svg", { width: padL + cellW * cols.length, height: padT + cellH * rows.length });
  cols.forEach((c, j) => svg.append(el("text", { x: padL + cellW * j + cellW / 2, y: 16, "text-anchor": "middle", class: "axis" }, c)));
  const max = Math.max(...data.flat());
  rows.forEach((r, i) => {
    svg.append(el("text", { x: padL - 10, y: padT + cellH * i + 24, "text-anchor": "end", class: "axis" }, r));
    cols.forEach((_, j) => {
      const v = data[i][j];
      const level = v === 0 ? 0 : Math.min(scale.length - 1, Math.ceil((v / max) * (scale.length - 1)));
      svg.append(el("rect", { x: padL + cellW * j + 1, y: padT + cellH * i + 1, width: cellW - 2, height: cellH - 2, rx: 4, fill: scale[level] }));
      svg.append(el("text", {
        x: padL + cellW * j + cellW / 2, y: padT + cellH * i + 24, "text-anchor": "middle",
        class: "val", fill: level >= 3 ? "#ffffff" : "var(--text-primary)",
        style: level >= 3 ? "fill:#fff" : "",
      }, v));
    });
  });
  target.append(svg);
}
