/**
 * geometryRenderers.js — SVG render functions for all geometry shapes and modes.
 * Each renderer is a pure function: (props, svgWidth, svgHeight, padding) => JSX <g>
 */
import React from 'react';

/* ── helpers ─────────────────────────────────────────────────────────── */

function dimensionLabel(x, y, text, opts = {}) {
  const { color, anchor = 'middle', bold = true, size = 14 } = opts;
  return (
    <text
      x={x} y={y}
      textAnchor={anchor}
      fontSize={size}
      fontWeight={bold ? 'bold' : 'normal'}
      style={{ fill: color || 'var(--text-primary)' }}
    >
      {text}
    </text>
  );
}

function dashedLine(x1, y1, x2, y2, color = '#ef4444') {
  return (
    <line x1={x1} y1={y1} x2={x2} y2={y2}
      stroke={color} strokeWidth={2} strokeDasharray="5,3" />
  );
}

function rightAngleMark(cx, cy, size = 12, dir = 'bl') {
  // dir: bl = bottom-left corner, br = bottom-right
  const dx = dir.includes('r') ? -size : size;
  const dy = -size;
  return (
    <path
      d={`M ${cx} ${cy + dy} L ${cx + dx} ${cy + dy} L ${cx + dx} ${cy}`}
      fill="none"
      style={{ stroke: 'var(--text-muted)' }}
      strokeWidth={1}
    />
  );
}

function angleArc(cx, cy, startAngle, endAngle, radius = 20, color = '#6366f1') {
  const startRad = (startAngle * Math.PI) / 180;
  const endRad = (endAngle * Math.PI) / 180;
  const x1 = cx + radius * Math.cos(startRad);
  const y1 = cy - radius * Math.sin(startRad);
  const x2 = cx + radius * Math.cos(endRad);
  const y2 = cy - radius * Math.sin(endRad);
  const largeArc = endAngle - startAngle > 180 ? 1 : 0;
  return (
    <path
      d={`M ${x1} ${y1} A ${radius} ${radius} 0 ${largeArc} 0 ${x2} ${y2}`}
      fill="none" stroke={color} strokeWidth={1.5}
    />
  );
}

/* ── TRIANGLE ────────────────────────────────────────────────────────── */

export function renderTriangle(props, W, H, pad) {
  const { mode = 'area', base = 6, height = 4, sideA, sideB, sideC,
    angle1, angle2, missingAngle, theta, trigFunc, missingSide } = props;

  // vertex positions (always a triangle, right-angle at bottom-left for pythagorean/trig)
  const isRight = mode === 'pythagorean' || mode === 'trig';
  const bx = pad;
  const by = H - pad;
  const cx = W - pad;
  const cy = H - pad;
  const ax = isRight ? pad : W / 2;
  const ay = pad + 20;

  const pts = `${ax},${ay} ${bx},${by} ${cx},${cy}`;

  if (mode === 'pythagorean') {
    // Use sideA/sideB/sideC directly — do NOT fall back to base/height defaults
    let a = sideA || null;
    let b = sideB || null;
    let c = sideC || null;
    const missing = missingSide || 'c';

    // Derive the missing value so labels always show numbers
    if (!c && a && b) c = Math.round(Math.sqrt(a * a + b * b) * 100) / 100;
    if (!b && a && c) b = Math.round(Math.sqrt(c * c - a * a) * 100) / 100;
    if (!a && b && c) a = Math.round(Math.sqrt(c * c - b * b) * 100) / 100;

    const aLabel = missing === 'a' ? 'a = ?' : a != null ? 'a = ' + a : 'a';
    const bLabel = missing === 'b' ? 'b = ?' : b != null ? 'b = ' + b : 'b';
    const cLabel = missing === 'c' ? 'c = ?' : c != null ? 'c = ' + c : 'c';

    // ? box position for whichever side is missing
    const qBoxPos = missing === 'a'
      ? { x: (bx + cx) / 2 - 15, y: by + 4 }
      : missing === 'b'
        ? { x: bx + 6, y: (ay + by) / 2 - 12 }
        : { x: (ax + cx) / 2 + 2, y: (ay + cy) / 2 - 22 };

    return (
      <g>
        <polygon points={pts} fill="#bfdbfe" stroke="#3b82f6" strokeWidth={2} />
        {rightAngleMark(bx, by, 12, 'bl')}
        {/* side a = bottom */}
        {dimensionLabel((bx + cx) / 2, by + 20, aLabel)}
        {/* side b = left vertical — positioned INSIDE triangle to avoid SVG clip */}
        {dimensionLabel(bx + 12, (ay + by) / 2, bLabel, { anchor: 'start' })}
        {/* side c = hypotenuse */}
        {dimensionLabel((ax + cx) / 2 + 14, (ay + cy) / 2 - 5, cLabel, { color: '#6366f1' })}
        {/* ? highlight box on missing side */}
        <rect x={qBoxPos.x} y={qBoxPos.y} width={30} height={20} rx={4}
          fill="#fef3c7" stroke="#f59e0b" strokeWidth={1.5} />
        {dimensionLabel(qBoxPos.x + 15, qBoxPos.y + 14, '?', { color: '#f59e0b' })}
      </g>
    );
  }

  if (mode === 'trig') {
    const th = theta || 30;
    const tf = trigFunc || 'sin';
    return (
      <g>
        <polygon points={pts} fill="#bfdbfe" stroke="#3b82f6" strokeWidth={2} />
        {rightAngleMark(bx, by, 12, 'bl')}
        {/* theta arc at bottom-right */}
        {angleArc(cx, cy, 135, 180, 25, '#8b5cf6')}
        {dimensionLabel(cx - 35, cy - 18, '\u03B8=' + th + '\u00B0', { color: '#8b5cf6', size: 12 })}
        {/* side labels: opp, adj, hyp — opp inside triangle to avoid SVG clip */}
        {dimensionLabel(bx + 12, (ay + by) / 2, 'opp', { anchor: 'start', color: '#ef4444', size: 12 })}
        {dimensionLabel((bx + cx) / 2, by + 18, 'adj', { color: '#22c55e', size: 12 })}
        {dimensionLabel((ax + cx) / 2 + 14, (ay + cy) / 2 - 5, 'hyp', { color: '#3b82f6', size: 12 })}
      </g>
    );
  }

  if (mode === 'angles') {
    const a1 = angle1;
    const a2 = angle2;
    const mi = missingAngle || 3;

    // Compute all three actual angle values (we always know them all)
    const numA = a1 || 60;   // top vertex
    const numB = a2 || 60;   // bottom-left vertex
    const numC = 180 - numA - numB; // bottom-right vertex

    // Labels: show '?' for the missing one
    const vals = [numA, numB, numC];
    if (mi === 1) vals[0] = '?';
    else if (mi === 2) vals[1] = '?';
    else vals[2] = '?';

    // Compute top vertex position from actual angles using law of sines.
    // B = bottom-left (bx, by), C = bottom-right (cx, cy), A = top.
    // From B, line to A makes angle numB with the horizontal base.
    // t = baseLen * sin(numC) / sin(numA)
    // ax = bx + t * cos(numB), ay = by - t * sin(numB)
    const baseLen = cx - bx;
    const radA = numA * Math.PI / 180;
    const radB = numB * Math.PI / 180;
    const radC = numC * Math.PI / 180;
    const sinA = Math.sin(radA);
    const t = sinA > 0.01 ? baseLen * Math.sin(radC) / sinA : baseLen * 0.8;
    let topX = bx + t * Math.cos(radB);
    let topY = by - t * Math.sin(radB);

    // Clamp within SVG bounds
    topX = Math.max(pad + 5, Math.min(W - pad - 5, topX));
    topY = Math.max(pad + 5, Math.min(by - 25, topY));

    const triPts = topX + ',' + topY + ' ' + bx + ',' + by + ' ' + cx + ',' + cy;

    // Compute arc sweep angles for each vertex based on the triangle geometry.
    // Bottom-left (B): base goes right (0°), side BA goes toward topX,topY
    const angleBtoA = Math.atan2(by - topY, topX - bx) * 180 / Math.PI;
    const arcB1 = -5;  // just below horizontal
    const arcB2 = angleBtoA + 5;

    // Bottom-right (C): base goes left (180°), side CA goes toward topX,topY
    const angleCtoA = Math.atan2(by - topY, topX - cx) * 180 / Math.PI;
    const arcC1 = angleCtoA - 5;
    const arcC2 = 185;

    // Top (A): sides go down to B and C
    const angleAtoB = Math.atan2(by - topY, bx - topX) * 180 / Math.PI;
    const angleAtoC = Math.atan2(by - topY, cx - topX) * 180 / Math.PI;
    const arcA1 = Math.min(angleAtoB, angleAtoC) - 5;
    const arcA2 = Math.max(angleAtoB, angleAtoC) + 5;

    // Right angle mark helper
    const has90 = numA === 90 ? 'A' : numB === 90 ? 'B' : numC === 90 ? 'C' : null;

    return (
      <g>
        <polygon points={triPts} fill="#e0e7ff" stroke="#6366f1" strokeWidth={2} />
        {/* Right angle mark if any angle is 90° */}
        {has90 === 'B' && rightAngleMark(bx, by, 12, 'bl')}
        {has90 === 'C' && rightAngleMark(cx, cy, 12, 'br')}
        {/* Top vertex (A) */}
        {has90 !== 'A' && angleArc(topX, topY, arcA1, arcA2, 18, '#ef4444')}
        {has90 === 'A' && <rect x={topX - 6} y={topY} width={8} height={8} fill="none" stroke="var(--text-muted)" strokeWidth={1} />}
        {dimensionLabel(topX, topY - 12, typeof vals[0] === 'number' ? vals[0] + '\u00B0' : vals[0], { color: '#ef4444', size: 12 })}
        {/* Bottom-left (B) */}
        {has90 !== 'B' && angleArc(bx, by, arcB1, arcB2, 18, '#22c55e')}
        {dimensionLabel(bx + 30, by - 14, typeof vals[1] === 'number' ? vals[1] + '\u00B0' : vals[1], { color: '#22c55e', size: 12 })}
        {/* Bottom-right (C) */}
        {has90 !== 'C' && angleArc(cx, cy, arcC1, arcC2, 18, '#6366f1')}
        {dimensionLabel(cx - 32, cy - 14, typeof vals[2] === 'number' ? vals[2] + '\u00B0' : vals[2], { color: '#6366f1', size: 12 })}
      </g>
    );
  }

  if (mode === 'perimeter') {
    const a = sideA || 5;
    const b = sideB || 4;
    const c = sideC || 3;
    return (
      <g>
        <polygon points={pts} fill="#bfdbfe" stroke="#3b82f6" strokeWidth={2} />
        {/* label all 3 sides — left label inside triangle to avoid SVG clip */}
        {dimensionLabel((bx + cx) / 2, by + 20, 'c = ' + c)}
        {dimensionLabel((isRight ? bx + 12 : bx - 10), (ay + by) / 2, 'a = ' + a, { anchor: isRight ? 'start' : 'end' })}
        {dimensionLabel((ax + cx) / 2 + 14, (ay + cy) / 2 - 5, 'b = ' + b)}
      </g>
    );
  }

  // Default: area mode
  return (
    <g>
      <polygon points={pts} fill="#bfdbfe" stroke="#3b82f6" strokeWidth={2} />
      <line x1={pad} y1={by + 15} x2={W - pad} y2={by + 15}
        style={{ stroke: 'var(--text-muted)' }} strokeWidth={1} />
      {dimensionLabel(W / 2, by + 30, 'b = ' + base)}
      {dashedLine(W / 2, by, W / 2, ay)}
      {dimensionLabel(W / 2 + 15, H / 2, 'h = ' + height, { color: '#ef4444' })}
      {rightAngleMark(W / 2, by, 15, 'bl')}
    </g>
  );
}

/* ── RECTANGLE ───────────────────────────────────────────────────────── */

export function renderRectangle(props, W, H, pad) {
  const { mode = 'area', base = 6, height = 4, width: w } = props;
  const rw = W - 2 * pad;
  const rh = H - 2 * pad - 20;
  const dispW = w || base;

  if (mode === 'perimeter') {
    return (
      <g>
        <rect x={pad} y={pad} width={rw} height={rh} fill="#bbf7d0" stroke="#22c55e" strokeWidth={2} />
        {/* top */}
        {dimensionLabel(W / 2, pad - 8, 'l = ' + dispW)}
        {/* bottom */}
        {dimensionLabel(W / 2, pad + rh + 20, 'l = ' + dispW)}
        {/* left */}
        {dimensionLabel(pad - 10, pad + rh / 2, 'w = ' + height, { anchor: 'end' })}
        {/* right */}
        {dimensionLabel(W - pad + 10, pad + rh / 2, 'w = ' + height, { anchor: 'start' })}
      </g>
    );
  }

  // area mode
  return (
    <g>
      <rect x={pad} y={pad} width={rw} height={rh} fill="#bbf7d0" stroke="#22c55e" strokeWidth={2} />
      {dimensionLabel(W / 2, H - pad + 20, 'w = ' + dispW)}
      {dimensionLabel(W - pad + 15, pad + rh / 2, 'h = ' + height)}
    </g>
  );
}

/* ── CIRCLE ──────────────────────────────────────────────────────────── */

export function renderCircle(props, W, H, pad) {
  const { radius = 5 } = props;
  const cxPos = W / 2;
  const cyPos = H / 2;
  const r = Math.min(W, H) / 2 - pad - 10;

  return (
    <g>
      <circle cx={cxPos} cy={cyPos} r={r} fill="#fde68a" stroke="#f59e0b" strokeWidth={2} />
      {/* center dot */}
      <circle cx={cxPos} cy={cyPos} r={3} fill="#f59e0b" />
      {/* radius line */}
      <line x1={cxPos} y1={cyPos} x2={cxPos + r} y2={cyPos}
        stroke="#ef4444" strokeWidth={2} />
      {dimensionLabel(cxPos + r / 2, cyPos - 10, 'r = ' + radius, { color: '#ef4444' })}
    </g>
  );
}

/* ── TRAPEZOID ───────────────────────────────────────────────────────── */

export function renderTrapezoid(props, W, H, pad) {
  const { topBase = 4, base = 8, height = 5 } = props;
  const bot = W - 2 * pad;
  const top = bot * (topBase / base);
  const topLeft = (W - top) / 2;
  const topRight = topLeft + top;
  const bottomY = H - pad;
  const topY = pad + 15;

  const pts = `${topLeft},${topY} ${topRight},${topY} ${W - pad},${bottomY} ${pad},${bottomY}`;

  return (
    <g>
      <polygon points={pts} fill="#e9d5ff" stroke="#a855f7" strokeWidth={2} />
      {/* top label */}
      {dimensionLabel(W / 2, topY - 8, 'a = ' + topBase, { color: '#a855f7' })}
      {/* bottom label */}
      {dimensionLabel(W / 2, bottomY + 20, 'b = ' + base, { color: '#a855f7' })}
      {/* height dashed */}
      {dashedLine(W / 2, topY, W / 2, bottomY, '#ef4444')}
      {dimensionLabel(W / 2 + 15, (topY + bottomY) / 2, 'h = ' + height, { color: '#ef4444' })}
      {rightAngleMark(W / 2, bottomY, 10, 'bl')}
    </g>
  );
}

/* ── PARALLELOGRAM ───────────────────────────────────────────────────── */

export function renderParallelogram(props, W, H, pad) {
  const { base = 7, height = 4 } = props;
  const offset = 40; // slant offset
  const bottomY = H - pad;
  const topY = pad + 15;

  const pts = `${pad + offset},${topY} ${W - pad},${topY} ${W - pad - offset},${bottomY} ${pad},${bottomY}`;

  return (
    <g>
      <polygon points={pts} fill="#fbcfe8" stroke="#ec4899" strokeWidth={2} />
      {/* base label bottom */}
      {dimensionLabel((pad + W - pad - offset) / 2, bottomY + 20, 'b = ' + base, { color: '#ec4899' })}
      {/* height dashed perpendicular */}
      {dashedLine(pad + offset, topY, pad + offset, bottomY, '#ef4444')}
      {dimensionLabel(pad + offset + 15, (topY + bottomY) / 2, 'h = ' + height, { color: '#ef4444' })}
      {rightAngleMark(pad + offset, bottomY, 10, 'bl')}
    </g>
  );
}

/* ── RECTANGULAR PRISM (pseudo-3D) ───────────────────────────────────── */

export function renderRectangularPrism(props, W, H, pad) {
  const { base: l = 5, width: w = 3, height: h = 4 } = props;
  // front face
  const fx = pad + 30;
  const fy = pad + 40;
  const fw = W * 0.5;
  const fh = H * 0.45;

  // 3D offset
  const ox = 30;
  const oy = -25;

  // Front face
  const front = `${fx},${fy} ${fx + fw},${fy} ${fx + fw},${fy + fh} ${fx},${fy + fh}`;
  // Top face
  const topFace = `${fx},${fy} ${fx + ox},${fy + oy} ${fx + fw + ox},${fy + oy} ${fx + fw},${fy}`;
  // Right face
  const rightFace = `${fx + fw},${fy} ${fx + fw + ox},${fy + oy} ${fx + fw + ox},${fy + fh + oy} ${fx + fw},${fy + fh}`;

  return (
    <g>
      <polygon points={front} fill="#bfdbfe" stroke="#3b82f6" strokeWidth={2} />
      <polygon points={topFace} fill="#93c5fd" stroke="#3b82f6" strokeWidth={2} />
      <polygon points={rightFace} fill="#60a5fa" stroke="#3b82f6" strokeWidth={2} />
      {/* l label (bottom of front face) */}
      {dimensionLabel(fx + fw / 2, fy + fh + 18, 'l = ' + l, { color: '#1d4ed8' })}
      {/* h label (left of front face) */}
      {dimensionLabel(fx - 10, fy + fh / 2, 'h = ' + h, { anchor: 'end', color: '#1d4ed8' })}
      {/* w label (top face depth) */}
      {dimensionLabel(fx + fw + ox / 2 + 8, fy + oy / 2 - 6, 'w = ' + w, { color: '#1d4ed8', size: 12 })}
    </g>
  );
}

/* ── CYLINDER ────────────────────────────────────────────────────────── */

export function renderCylinder(props, W, H, pad) {
  const { radius = 3, height: h = 7 } = props;
  const cx = W / 2;
  const topY = pad + 30;
  const botY = H - pad - 10;
  const rx = 60; // ellipse x-radius
  const ry = 18; // ellipse y-radius

  return (
    <g>
      {/* back half of bottom ellipse */}
      <ellipse cx={cx} cy={botY} rx={rx} ry={ry}
        fill="none" stroke="#22c55e" strokeWidth={1.5} strokeDasharray="5,3" />
      {/* cylinder body (two side lines) */}
      <line x1={cx - rx} y1={topY} x2={cx - rx} y2={botY} stroke="#22c55e" strokeWidth={2} />
      <line x1={cx + rx} y1={topY} x2={cx + rx} y2={botY} stroke="#22c55e" strokeWidth={2} />
      {/* body fill */}
      <rect x={cx - rx} y={topY} width={rx * 2} height={botY - topY}
        fill="#bbf7d0" stroke="none" />
      {/* bottom ellipse front */}
      <ellipse cx={cx} cy={botY} rx={rx} ry={ry}
        fill="#86efac" stroke="#22c55e" strokeWidth={2} />
      {/* top ellipse */}
      <ellipse cx={cx} cy={topY} rx={rx} ry={ry}
        fill="#bbf7d0" stroke="#22c55e" strokeWidth={2} />
      {/* radius line on top */}
      <line x1={cx} y1={topY} x2={cx + rx} y2={topY}
        stroke="#ef4444" strokeWidth={2} />
      <circle cx={cx} cy={topY} r={2.5} fill="#ef4444" />
      {dimensionLabel(cx + rx / 2, topY - 8, 'r = ' + radius, { color: '#ef4444', size: 12 })}
      {/* height label */}
      {dimensionLabel(cx + rx + 14, (topY + botY) / 2, 'h = ' + h, { anchor: 'start', color: '#1d4ed8' })}
    </g>
  );
}

/* ── SIMILARITY (two triangles side-by-side) ─────────────────────────── */

/* ── REGULAR POLYGON (N-gon) ─────────────────────────────────────────── */

export function renderRegularPolygon(props, W, H, pad) {
  const { sides = 6, sideLength = 4, mode = 'area' } = props;
  const n = Math.max(3, Math.min(12, sides));
  const cx = W / 2;
  const cy = H / 2;
  const R = Math.min(W, H) / 2 - pad - 10; // circumradius

  // Compute vertices (start from top: -π/2 rotation)
  const vertices = [];
  for (let i = 0; i < n; i++) {
    const angle = (2 * Math.PI * i) / n - Math.PI / 2;
    vertices.push([cx + R * Math.cos(angle), cy + R * Math.sin(angle)]);
  }
  const pts = vertices.map(([x, y]) => `${x},${y}`).join(' ');

  // Apothem (center to midpoint of a side)
  const midX = (vertices[0][0] + vertices[1][0]) / 2;
  const midY = (vertices[0][1] + vertices[1][1]) / 2;

  const showDecompose = mode === 'decompose';

  return (
    <g>
      <polygon points={pts} fill="#dbeafe" stroke="#3b82f6" strokeWidth={2} />
      {/* Decomposition lines from center to each vertex */}
      {showDecompose && vertices.map(([vx, vy], i) => (
        <line key={i} x1={cx} y1={cy} x2={vx} y2={vy}
          stroke="#6366f1" strokeWidth={1.5} strokeDasharray="4,3" />
      ))}
      {/* Center dot */}
      {showDecompose && <circle cx={cx} cy={cy} r={3} fill="#6366f1" />}
      {/* Apothem line (center to midpoint of first side) */}
      {!showDecompose && dashedLine(cx, cy, midX, midY, '#ef4444')}
      {!showDecompose && rightAngleMark(midX, midY, 8, midX < cx ? 'br' : 'bl')}
      {/* Side length label on first side */}
      {dimensionLabel(midX, midY + 18, 's = ' + sideLength, { color: '#3b82f6' })}
      {/* N label */}
      {dimensionLabel(cx, cy + (showDecompose ? 0 : -8),
        showDecompose ? n + ' triangles' : 'n = ' + n,
        { color: showDecompose ? '#6366f1' : 'var(--text-muted)', size: 12 })}
    </g>
  );
}

/* ── SIMILARITY (two triangles side-by-side) ─────────────────────────── */

export function renderSimilarity(props, W, H, pad) {
  const { sideA = 3, sideB = 4, sideC = 5, scale = 2 } = props;
  const halfW = W / 2 - 10;

  // Small triangle (left)
  const s1 = { bx: pad, by: H - pad, cx: halfW - pad, cy: H - pad, ax: pad, ay: pad + 20 };
  const pts1 = `${s1.ax},${s1.ay} ${s1.bx},${s1.by} ${s1.cx},${s1.cy}`;

  // Large triangle (right)
  const off = halfW + 20;
  const s2 = { bx: off, by: H - pad, cx: W - pad, cy: H - pad, ax: off, ay: pad + 20 };
  const pts2 = `${s2.ax},${s2.ay} ${s2.bx},${s2.by} ${s2.cx},${s2.cy}`;

  return (
    <g>
      {/* small triangle */}
      <polygon points={pts1} fill="#bfdbfe" stroke="#3b82f6" strokeWidth={2} />
      {dimensionLabel((s1.bx + s1.cx) / 2, s1.by + 18, '' + sideC, { color: '#3b82f6', size: 11 })}
      {dimensionLabel(s1.bx - 5, (s1.ay + s1.by) / 2, '' + sideA, { anchor: 'end', color: '#3b82f6', size: 11 })}
      {dimensionLabel((s1.ax + s1.cx) / 2 + 10, (s1.ay + s1.cy) / 2 - 3, '' + sideB, { color: '#3b82f6', size: 11 })}

      {/* ~ symbol between */}
      {dimensionLabel(W / 2, H / 2, '\u223C', { size: 22, color: 'var(--text-muted)' })}

      {/* large triangle */}
      <polygon points={pts2} fill="#dbeafe" stroke="#6366f1" strokeWidth={2} />
      {dimensionLabel((s2.bx + s2.cx) / 2, s2.by + 18, '' + (sideC * scale), { color: '#6366f1', size: 11 })}
      {dimensionLabel(s2.bx - 5, (s2.ay + s2.by) / 2, '' + (sideA * scale), { anchor: 'end', color: '#6366f1', size: 11 })}
      {dimensionLabel((s2.ax + s2.cx) / 2 + 10, (s2.ay + s2.cy) / 2 - 3, '?', { color: '#f59e0b', size: 14 })}

      {/* scale label */}
      {dimensionLabel(W / 2, H - 5, 'Scale factor: ' + scale, { size: 11, color: 'var(--text-muted)' })}
    </g>
  );
}

/* ── PYRAMID (square-based) ────────────────────────────────────────── */

export function renderPyramid(props, W, H, pad) {
  const { base = 6, height: h = 8, slant_height: sl } = props;
  const cx = W / 2;
  const apex = { x: cx, y: pad + 15 };
  // Base quad (3D perspective)
  const baseY = H - pad - 10;
  const bw = 100; // base visual width
  const bh = 30;  // perspective depth
  const bl = { x: cx - bw / 2, y: baseY };
  const br = { x: cx + bw / 2, y: baseY };
  const fl = { x: cx - bw / 3, y: baseY + bh };
  const fr = { x: cx + bw / 3, y: baseY + bh };

  return (
    <g>
      {/* back edges (dashed) */}
      <line x1={bl.x} y1={bl.y} x2={br.x} y2={br.y} stroke="#22c55e" strokeWidth={1.5} strokeDasharray="5,3" />
      <line x1={bl.x} y1={bl.y} x2={fl.x} y2={fl.y} stroke="#22c55e" strokeWidth={1.5} strokeDasharray="5,3" />
      {/* front edges */}
      <line x1={br.x} y1={br.y} x2={fr.x} y2={fr.y} stroke="#22c55e" strokeWidth={2} />
      <line x1={fl.x} y1={fl.y} x2={fr.x} y2={fr.y} stroke="#22c55e" strokeWidth={2} />
      {/* edges to apex */}
      <line x1={apex.x} y1={apex.y} x2={bl.x} y2={bl.y} stroke="#22c55e" strokeWidth={1.5} strokeDasharray="5,3" />
      <line x1={apex.x} y1={apex.y} x2={br.x} y2={br.y} stroke="#22c55e" strokeWidth={2} />
      <line x1={apex.x} y1={apex.y} x2={fl.x} y2={fl.y} stroke="#22c55e" strokeWidth={2} />
      <line x1={apex.x} y1={apex.y} x2={fr.x} y2={fr.y} stroke="#22c55e" strokeWidth={2} />
      {/* front faces fill */}
      <polygon points={`${apex.x},${apex.y} ${fr.x},${fr.y} ${br.x},${br.y}`} fill="#bbf7d0" opacity={0.4} />
      <polygon points={`${apex.x},${apex.y} ${fl.x},${fl.y} ${fr.x},${fr.y}`} fill="#dcfce7" opacity={0.4} />
      {/* height dashed line */}
      {dashedLine(cx, apex.y, cx, (bl.y + fl.y) / 2, '#ef4444')}
      {dimensionLabel(cx + 12, (apex.y + baseY) / 2, 'h = ' + h, { anchor: 'start', color: '#ef4444', size: 12 })}
      {/* base label */}
      {dimensionLabel((fl.x + fr.x) / 2, fl.y + 18, 'b = ' + base, { color: '#1d4ed8', size: 12 })}
      {/* slant height label */}
      {sl && dimensionLabel(cx + bw / 3 + 15, (apex.y + fr.y) / 2, 'l = ' + sl, { anchor: 'start', color: '#9333ea', size: 11 })}
    </g>
  );
}

/* ── CONE ──────────────────────────────────────────────────────────── */

export function renderCone(props, W, H, pad) {
  const { radius = 4, height: h = 6, slant_height: sl } = props;
  const cx = W / 2;
  const apexY = pad + 15;
  const baseY = H - pad - 10;
  const rx = 60;
  const ry = 18;

  return (
    <g>
      {/* back half of base ellipse */}
      <ellipse cx={cx} cy={baseY} rx={rx} ry={ry}
        fill="none" stroke="#22c55e" strokeWidth={1.5} strokeDasharray="5,3" />
      {/* side lines */}
      <line x1={cx} y1={apexY} x2={cx - rx} y2={baseY} stroke="#22c55e" strokeWidth={2} />
      <line x1={cx} y1={apexY} x2={cx + rx} y2={baseY} stroke="#22c55e" strokeWidth={2} />
      {/* front face fill */}
      <polygon points={`${cx},${apexY} ${cx - rx},${baseY} ${cx + rx},${baseY}`}
        fill="#bbf7d0" opacity={0.4} />
      {/* front half of base ellipse */}
      <ellipse cx={cx} cy={baseY} rx={rx} ry={ry}
        fill="#86efac" stroke="#22c55e" strokeWidth={2} />
      {/* apex dot */}
      <circle cx={cx} cy={apexY} r={3} fill="#22c55e" />
      {/* height dashed line */}
      {dashedLine(cx, apexY, cx, baseY, '#ef4444')}
      {dimensionLabel(cx + 12, (apexY + baseY) / 2, 'h = ' + h, { anchor: 'start', color: '#ef4444', size: 12 })}
      {/* radius line */}
      <line x1={cx} y1={baseY} x2={cx + rx} y2={baseY} stroke="#1d4ed8" strokeWidth={2} />
      <circle cx={cx} cy={baseY} r={2.5} fill="#1d4ed8" />
      {dimensionLabel(cx + rx / 2, baseY - 8, 'r = ' + radius, { color: '#1d4ed8', size: 12 })}
      {/* slant height */}
      {sl && dimensionLabel(cx + rx / 2 + 15, (apexY + baseY) / 2 - 10, 'l = ' + sl, { anchor: 'start', color: '#9333ea', size: 11 })}
    </g>
  );
}

/* ── SPHERE ────────────────────────────────────────────────────────── */

export function renderSphere(props, W, H, pad) {
  const { radius = 5 } = props;
  const cx = W / 2;
  const cy = H / 2;
  const r = Math.min(W, H) / 2 - pad - 10;

  return (
    <g>
      {/* main circle */}
      <circle cx={cx} cy={cy} r={r} fill="#bbf7d0" stroke="#22c55e" strokeWidth={2} />
      {/* equator ellipse */}
      <ellipse cx={cx} cy={cy} rx={r} ry={r * 0.3}
        fill="none" stroke="#22c55e" strokeWidth={1.5} strokeDasharray="5,3" />
      {/* radius line */}
      <line x1={cx} y1={cy} x2={cx + r} y2={cy} stroke="#ef4444" strokeWidth={2} />
      <circle cx={cx} cy={cy} r={2.5} fill="#ef4444" />
      {dimensionLabel(cx + r / 2, cy - 10, 'r = ' + radius, { color: '#ef4444', size: 12 })}
    </g>
  );
}
