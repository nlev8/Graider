import { useState } from 'react';
import FunctionGraphCanvas from './interactive-function-graph/FunctionGraphCanvas.jsx';

/**
 * InteractiveFunctionGraph - Enter function expressions and see live graph updates
 * Students can type expressions, identify intercepts, and analyze graphs.
 *
 * Canvas rendering extracted to FunctionGraphCanvas (Protocol-FE, Class A).
 */
export default function InteractiveFunctionGraph({
  xRange = [-10, 10],
  yRange = [-10, 10],
  expressions = [],
  onChange,
  correctExpressions = null,
  readOnly = false,
  maxExpressions = 3,
  onInputFocus,
}) {
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
      <FunctionGraphCanvas
        width={width}
        height={height}
        pad={pad}
        plotW={plotW}
        plotH={plotH}
        xRange={xRange}
        yRange={yRange}
        localExprs={localExprs}
        readOnly={readOnly}
        correctExpressions={correctExpressions}
        canvasStyle={styles.canvas}
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
                onFocus={(e) => onInputFocus?.(e.target, idx, 'unicode')}
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
