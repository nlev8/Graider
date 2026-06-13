import { useRef, useEffect } from 'react';

const colors = ['#2563eb', '#dc2626', '#16a34a', '#9333ea', '#ea580c'];

// Convert math value to canvas pixel
const valToX = (v, xRange, pad, plotW) =>
  pad + ((v - xRange[0]) / (xRange[1] - xRange[0])) * plotW;
const valToY = (v, yRange, pad, plotH) =>
  pad + ((yRange[1] - v) / (yRange[1] - yRange[0])) * plotH;

// Parse a simple expression string into an evaluable function
const parseExpr = (str) => {
  let s = str.trim();
  if (!s) return null;
  // Strip "y=" prefix
  if (s.match(/^y\s*=/i)) s = s.split('=').slice(1).join('=').trim();
  // Convert common notation
  s = s.replace(/\^/g, '**');
  // Insert multiplication: 2x → 2*x, )x → )*x, x( → x*(
  s = s.replace(/(\d)([a-zA-Z])/g, '$1*$2');
  s = s.replace(/([a-zA-Z])(\d)/g, '$1*$2');
  s = s.replace(/\)([a-zA-Z\d])/g, ')*$1');
  s = s.replace(/([a-zA-Z\d])\(/g, '$1*(');
  // Replace common functions
  s = s.replace(/\bsin\b/g, 'Math.sin');
  s = s.replace(/\bcos\b/g, 'Math.cos');
  s = s.replace(/\btan\b/g, 'Math.tan');
  s = s.replace(/\bsqrt\b/g, 'Math.sqrt');
  s = s.replace(/\babs\b/g, 'Math.abs');
  s = s.replace(/\bpi\b/g, 'Math.PI');
  s = s.replace(/\be\b/g, 'Math.E');
  try {
    // eslint-disable-next-line no-new-func
    const fn = new Function('x', 'return ' + s);
    // Quick test
    fn(0);
    return fn;
  } catch {
    return null;
  }
};

/**
 * FunctionGraphCanvas — canvas renderer for InteractiveFunctionGraph.
 * Owns the <canvas> element and the drawing effect; receives all data as props.
 */
export default function FunctionGraphCanvas({
  width,
  height,
  pad,
  plotW,
  plotH,
  xRange,
  yRange,
  localExprs,
  readOnly,
  correctExpressions,
  canvasStyle,
}) {
  const canvasRef = useRef(null);

  // Draw the graph on canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, width, height);

    // Read CSS variables for theme-aware rendering
    const cs = getComputedStyle(canvas);
    const textPrimary = cs.getPropertyValue('--text-primary').trim() || '#fff';
    const textMuted = cs.getPropertyValue('--text-muted').trim() || 'rgba(255,255,255,0.4)';
    const inputBg = cs.getPropertyValue('--input-bg').trim() || 'rgba(0,0,0,0.3)';
    const glassBorder = cs.getPropertyValue('--glass-border').trim() || 'rgba(255,255,255,0.1)';

    // Background
    ctx.fillStyle = inputBg;
    ctx.fillRect(0, 0, width, height);

    // Grid lines
    ctx.strokeStyle = glassBorder;
    ctx.lineWidth = 0.5;
    for (let v = Math.ceil(xRange[0]); v <= xRange[1]; v++) {
      const px = valToX(v, xRange, pad, plotW);
      ctx.beginPath(); ctx.moveTo(px, pad); ctx.lineTo(px, pad + plotH); ctx.stroke();
    }
    for (let v = Math.ceil(yRange[0]); v <= yRange[1]; v++) {
      const py = valToY(v, yRange, pad, plotH);
      ctx.beginPath(); ctx.moveTo(pad, py); ctx.lineTo(pad + plotW, py); ctx.stroke();
    }

    // Axes
    ctx.strokeStyle = textPrimary;
    ctx.lineWidth = 1.5;
    const originX = valToX(0, xRange, pad, plotW);
    const originY = valToY(0, yRange, pad, plotH);
    if (originX >= pad && originX <= pad + plotW) {
      ctx.beginPath(); ctx.moveTo(originX, pad); ctx.lineTo(originX, pad + plotH); ctx.stroke();
    }
    if (originY >= pad && originY <= pad + plotH) {
      ctx.beginPath(); ctx.moveTo(pad, originY); ctx.lineTo(pad + plotW, originY); ctx.stroke();
    }

    // Axis labels
    ctx.fillStyle = textMuted;
    ctx.font = '10px sans-serif';
    ctx.textAlign = 'center';
    for (let v = Math.ceil(xRange[0]); v <= xRange[1]; v++) {
      if (v === 0) continue;
      ctx.fillText(String(v), valToX(v, xRange, pad, plotW), Math.min(originY + 14, pad + plotH + 14));
    }
    ctx.textAlign = 'right';
    for (let v = Math.ceil(yRange[0]); v <= yRange[1]; v++) {
      if (v === 0) continue;
      ctx.fillText(String(v), Math.max(originX - 4, pad - 4), valToY(v, yRange, pad, plotH) + 3);
    }

    // Plot each expression
    const allExprs = readOnly && correctExpressions ? correctExpressions : localExprs;
    const step = (xRange[1] - xRange[0]) / plotW;

    allExprs.forEach((expr, idx) => {
      const fn = parseExpr(expr);
      if (!fn) return;

      ctx.strokeStyle = colors[idx % colors.length];
      ctx.lineWidth = 2;
      ctx.beginPath();
      let started = false;

      for (let px = 0; px <= plotW; px++) {
        const xVal = xRange[0] + px * step;
        try {
          const yVal = fn(xVal);
          if (!isFinite(yVal) || yVal < yRange[0] - 5 || yVal > yRange[1] + 5) {
            started = false;
            continue;
          }
          const cy = valToY(yVal, yRange, pad, plotH);
          if (!started) {
            ctx.moveTo(pad + px, cy);
            started = true;
          } else {
            ctx.lineTo(pad + px, cy);
          }
        } catch {
          started = false;
        }
      }
      ctx.stroke();
    });

    // Show correct answers overlay
    if (correctExpressions && !readOnly) {
      correctExpressions.forEach((expr) => {
        const fn = parseExpr(expr);
        if (!fn) return;
        ctx.strokeStyle = '#22c55e';
        ctx.lineWidth = 1.5;
        ctx.setLineDash([5, 3]);
        ctx.beginPath();
        let started = false;
        for (let px = 0; px <= plotW; px++) {
          const xVal = xRange[0] + px * step;
          try {
            const yVal = fn(xVal);
            if (!isFinite(yVal) || yVal < yRange[0] - 5 || yVal > yRange[1] + 5) {
              started = false; continue;
            }
            const cy = valToY(yVal, yRange, pad, plotH);
            if (!started) { ctx.moveTo(pad + px, cy); started = true; }
            else { ctx.lineTo(pad + px, cy); }
          } catch { started = false; }
        }
        ctx.stroke();
        ctx.setLineDash([]);
      });
    }
  }, [localExprs, xRange, yRange, correctExpressions, readOnly, width, height, pad, plotW, plotH]);

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      style={canvasStyle}
    />
  );
}
