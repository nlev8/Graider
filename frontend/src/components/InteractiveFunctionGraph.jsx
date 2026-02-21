import { useState, useRef, useEffect } from 'react';

/**
 * InteractiveFunctionGraph - Enter function expressions and see live graph updates
 * Students can type expressions, identify intercepts, and analyze graphs.
 */
export default function InteractiveFunctionGraph({
  xRange = [-10, 10],
  yRange = [-10, 10],
  expressions = [],
  onChange,
  correctExpressions = null,
  readOnly = false,
  maxExpressions = 3
}) {
  const canvasRef = useRef(null);
  const [localExprs, setLocalExprs] = useState(
    expressions.length > 0 ? expressions : ['']
  );
  const [error, setError] = useState(null);

  const width = 500;
  const height = 400;
  const pad = 40;
  const plotW = width - 2 * pad;
  const plotH = height - 2 * pad;

  const colors = ['#2563eb', '#dc2626', '#16a34a', '#9333ea', '#ea580c'];

  // Convert math value to canvas pixel
  const valToX = (v) => pad + ((v - xRange[0]) / (xRange[1] - xRange[0])) * plotW;
  const valToY = (v) => pad + ((yRange[1] - v) / (yRange[1] - yRange[0])) * plotH;

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
      const px = valToX(v);
      ctx.beginPath(); ctx.moveTo(px, pad); ctx.lineTo(px, pad + plotH); ctx.stroke();
    }
    for (let v = Math.ceil(yRange[0]); v <= yRange[1]; v++) {
      const py = valToY(v);
      ctx.beginPath(); ctx.moveTo(pad, py); ctx.lineTo(pad + plotW, py); ctx.stroke();
    }

    // Axes
    ctx.strokeStyle = textPrimary;
    ctx.lineWidth = 1.5;
    const originX = valToX(0);
    const originY = valToY(0);
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
      ctx.fillText(String(v), valToX(v), Math.min(originY + 14, pad + plotH + 14));
    }
    ctx.textAlign = 'right';
    for (let v = Math.ceil(yRange[0]); v <= yRange[1]; v++) {
      if (v === 0) continue;
      ctx.fillText(String(v), Math.max(originX - 4, pad - 4), valToY(v) + 3);
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
          const cy = valToY(yVal);
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
      correctExpressions.forEach((expr, idx) => {
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
            const cy = valToY(yVal);
            if (!started) { ctx.moveTo(pad + px, cy); started = true; }
            else { ctx.lineTo(pad + px, cy); }
          } catch { started = false; }
        }
        ctx.stroke();
        ctx.setLineDash([]);
      });
    }
  }, [localExprs, xRange, yRange, correctExpressions, readOnly]);

  const updateExpr = (idx, val) => {
    const next = [...localExprs];
    next[idx] = val;
    setLocalExprs(next);
    setError(null);
    if (onChange) onChange(next.filter(e => e.trim()));
  };

  const addExpr = () => {
    if (localExprs.length < maxExpressions) {
      const next = [...localExprs, ''];
      setLocalExprs(next);
    }
  };

  const removeExpr = (idx) => {
    if (localExprs.length <= 1) return;
    const next = localExprs.filter((_, i) => i !== idx);
    setLocalExprs(next);
    if (onChange) onChange(next.filter(e => e.trim()));
  };

  return (
    <div style={styles.container}>
      <canvas
        ref={canvasRef}
        width={width}
        height={height}
        style={styles.canvas}
      />
      {!readOnly && (
        <div style={styles.inputs}>
          {localExprs.map((expr, idx) => (
            <div key={idx} style={styles.exprRow}>
              <span style={{ ...styles.colorDot, background: colors[idx % colors.length] }} />
              <span style={styles.yLabel}>y =</span>
              <input
                type="text"
                value={expr}
                onChange={(e) => updateExpr(idx, e.target.value)}
                placeholder="e.g. 2x + 1, x^2, sin(x)"
                style={styles.exprInput}
              />
              {localExprs.length > 1 && (
                <button onClick={() => removeExpr(idx)} style={styles.removeBtn}>x</button>
              )}
            </div>
          ))}
          {localExprs.length < maxExpressions && (
            <button onClick={addExpr} style={styles.addBtn}>+ Add function</button>
          )}
        </div>
      )}
      {error && <div style={styles.error}>{error}</div>}
    </div>
  );
}

const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
    alignItems: 'center',
  },
  canvas: {
    border: '1px solid var(--glass-border)',
    borderRadius: '8px',
    maxWidth: '100%',
  },
  inputs: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
    width: '100%',
    maxWidth: '500px',
  },
  exprRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  colorDot: {
    width: '12px',
    height: '12px',
    borderRadius: '50%',
    flexShrink: 0,
  },
  yLabel: {
    fontWeight: 600,
    fontSize: '14px',
    color: 'var(--text-primary)',
    flexShrink: 0,
  },
  exprInput: {
    flex: 1,
    padding: '8px 12px',
    border: '1px solid var(--glass-border)',
    borderRadius: '6px',
    fontSize: '14px',
    fontFamily: 'monospace',
    background: 'var(--input-bg)',
    color: 'var(--text-primary)',
  },
  removeBtn: {
    background: 'rgba(239, 68, 68, 0.15)',
    color: '#ef4444',
    border: 'none',
    borderRadius: '4px',
    width: '28px',
    height: '28px',
    cursor: 'pointer',
    fontWeight: 'bold',
    flexShrink: 0,
  },
  addBtn: {
    background: 'rgba(37, 99, 235, 0.1)',
    color: '#3b82f6',
    border: '1px dashed rgba(37, 99, 235, 0.4)',
    borderRadius: '6px',
    padding: '6px 12px',
    cursor: 'pointer',
    fontSize: '13px',
    alignSelf: 'flex-start',
  },
  error: {
    color: '#dc2626',
    fontSize: '13px',
  },
};
