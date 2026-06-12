import React from "react";
import { gradeColor } from "./gradeColor";

// Custom SVG box plot — recharts has no native box plot.
// This is a FIVE-NUMBER-SUMMARY plot (min/Q1/median/Q3/max). No outlier treatment;
// whiskers extend to absolute min/max (NOT 1.5×IQR fences). If outlier display is
// ever requested by teachers, port the IQR-fence math from
// frontend/src/components/InteractiveBoxPlot.jsx (which is the input widget — never
// modify or import it from here; this read-only component owns its own math).
export default function BoxPlotRow({ assessments }) {
  var width = Math.max(600, assessments.length * 110);
  var height = 200;
  var pad = { top: 16, right: 24, bottom: 40, left: 48 };
  var plotH = height - pad.top - pad.bottom;
  var boxW = 60;
  var slotW = (width - pad.left - pad.right) / Math.max(assessments.length, 1);

  function yFor(pct) {
    return pad.top + plotH - (pct / 100) * plotH;
  }

  return (
    <svg width={width} height={height} style={{ display: "block" }}>
      {/* Y axis ticks at 0, 25, 50, 70, 85, 100 */}
      {[0, 25, 50, 70, 85, 100].map(function(t) {
        var y = yFor(t);
        var stroke = (t === 70 || t === 85) ? (t === 85 ? "var(--success)" : "var(--warning)") : "var(--glass-border)";
        var dash = (t === 70 || t === 85) ? "3 3" : undefined;
        return (
          <g key={t}>
            <line x1={pad.left} x2={width - pad.right} y1={y} y2={y} stroke={stroke} strokeDasharray={dash} />
            <text x={pad.left - 8} y={y + 4} fontSize="10" textAnchor="end" fill="var(--text-secondary)">{t}</text>
          </g>
        );
      })}
      {/* Box per assessment */}
      {assessments.map(function(a, i) {
        if (a.n === 0) {
          return (
            <g key={a.content_id}>
              <text x={pad.left + slotW * i + slotW / 2} y={yFor(50)} fontSize="11" textAnchor="middle" fill="var(--text-muted)">no data</text>
              <text x={pad.left + slotW * i + slotW / 2} y={height - pad.bottom + 16} fontSize="10" textAnchor="middle" fill="var(--text-secondary)">{a.title.length > 12 ? a.title.slice(0, 11) + String.fromCharCode(8230) : a.title}</text>
            </g>
          );
        }
        var color = gradeColor(a.mean);
        var cx = pad.left + slotW * i + slotW / 2;
        var x0 = cx - boxW / 2;
        var yMin = yFor(a.min);
        var yMax = yFor(a.max);
        var yQ1 = yFor(a.q1);
        var yQ3 = yFor(a.q3);
        var yMed = yFor(a.median);
        return (
          <g key={a.content_id}>
            {/* Whiskers */}
            <line x1={cx} x2={cx} y1={yMin} y2={yQ1} stroke={color.text} strokeWidth="1.5" />
            <line x1={cx} x2={cx} y1={yQ3} y2={yMax} stroke={color.text} strokeWidth="1.5" />
            <line x1={cx - 12} x2={cx + 12} y1={yMin} y2={yMin} stroke={color.text} strokeWidth="1.5" />
            <line x1={cx - 12} x2={cx + 12} y1={yMax} y2={yMax} stroke={color.text} strokeWidth="1.5" />
            {/* Box */}
            <rect x={x0} y={yQ3} width={boxW} height={Math.max(yQ1 - yQ3, 1)} fill={color.bg} stroke={color.text} strokeWidth="1.5" />
            {/* Median line */}
            <line x1={x0} x2={x0 + boxW} y1={yMed} y2={yMed} stroke={color.text} strokeWidth="2" />
            {/* X-axis label */}
            <text x={cx} y={height - pad.bottom + 16} fontSize="10" textAnchor="middle" fill="var(--text-secondary)">
              {a.title.length > 12 ? a.title.slice(0, 11) + String.fromCharCode(8230) : a.title}
            </text>
            <title>{a.title + ": median " + a.median + "%, IQR " + a.q1 + "-" + a.q3 + ", n=" + a.n}</title>
          </g>
        );
      })}
    </svg>
  );
}
