import { useState } from 'react';

/**
 * InteractiveDotPlot - Click to add/remove dots above values on a number line.
 * Used for frequency distributions in grades 6-8 statistics.
 */
export default function InteractiveDotPlot({
  categories = [],
  minVal = 0,
  maxVal = 10,
  step = 1,
  dots = {},
  onChange,
  correctDots = null,
  readOnly = false,
  title = ''
}) {
  const useCategories = categories.length > 0;
  const items = useCategories
    ? categories
    : Array.from({ length: Math.floor((maxVal - minVal) / step) + 1 }, (_, i) => minVal + i * step);

  const svgWidth = Math.max(400, items.length * 50 + 80);
  const svgHeight = 220;
  const padding = 40;
  const lineY = svgHeight - 50;
  const maxDotsVisible = 10;
  const dotR = 8;
  const dotSpacing = dotR * 2 + 2;

  const itemToX = (idx) => padding + (idx + 0.5) * ((svgWidth - 2 * padding) / items.length);

  const handleClick = (item) => {
    if (readOnly) return;
    const key = String(item);
    const current = dots[key] || 0;
    const next = { ...dots, [key]: current + 1 };
    onChange?.(next);
  };

  const handleRightClick = (e, item) => {
    e.preventDefault();
    if (readOnly) return;
    const key = String(item);
    const current = dots[key] || 0;
    if (current > 0) {
      const next = { ...dots, [key]: current - 1 };
      if (next[key] === 0) delete next[key];
      onChange?.(next);
    }
  };

  const maxCount = Math.max(1, ...Object.values(dots).map(Number), ...(correctDots ? Object.values(correctDots).map(Number) : [0]));

  return (
    <div style={styles.container}>
      {title && <div style={styles.title}>{title}</div>}
      <svg width={svgWidth} height={svgHeight}>
        <rect x={0} y={0} width={svgWidth} height={svgHeight} style={{ fill: 'var(--input-bg)' }} rx={8} />

        {/* Axis line */}
        <line
          x1={padding}
          y1={lineY}
          x2={svgWidth - padding}
          y2={lineY}
          style={{ stroke: 'var(--text-primary)' }}
          strokeWidth={2}
        />

        {/* Items and dots */}
        {items.map((item, idx) => {
          const x = itemToX(idx);
          const count = dots[String(item)] || 0;
          const correctCount = correctDots ? (correctDots[String(item)] || 0) : null;

          return (
            <g key={idx}>
              {/* Tick mark */}
              <line x1={x} y1={lineY - 5} x2={x} y2={lineY + 5}
                style={{ stroke: 'var(--text-primary)' }} strokeWidth={1} />

              {/* Label */}
              <text x={x} y={lineY + 22} textAnchor="middle" fontSize={11}
                style={{ fill: 'var(--text-secondary)' }}>
                {item}
              </text>

              {/* Clickable area */}
              {!readOnly && (
                <rect
                  x={x - 20} y={20} width={40} height={lineY - 25}
                  fill="transparent" style={{ cursor: 'pointer' }}
                  onClick={() => handleClick(item)}
                  onContextMenu={(e) => handleRightClick(e, item)}
                />
              )}

              {/* User dots */}
              {Array.from({ length: Math.min(count, maxDotsVisible) }, (_, di) => (
                <circle
                  key={`dot-${di}`}
                  cx={x}
                  cy={lineY - 15 - di * dotSpacing}
                  r={dotR}
                  fill="#6366f1"
                  stroke="#fff"
                  strokeWidth={1.5}
                />
              ))}
              {count > maxDotsVisible && (
                <text x={x} y={lineY - 15 - maxDotsVisible * dotSpacing}
                  textAnchor="middle" fontSize={10} fill="#6366f1" fontWeight="bold">
                  {count}
                </text>
              )}

              {/* Correct dots overlay */}
              {correctCount !== null && correctCount !== count && (
                <text x={x} y={15} textAnchor="middle" fontSize={10}
                  fill="#22c55e" fontWeight="bold">
                  ({correctCount})
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {!readOnly && (
        <p style={styles.hint}>
          Click a value to add a dot. Right-click to remove a dot.
        </p>
      )}

      {Object.keys(dots).length > 0 && (
        <div style={styles.summary}>
          <strong>Counts:</strong>{' '}
          {Object.entries(dots)
            .filter(([, v]) => v > 0)
            .sort(([a], [b]) => (useCategories ? 0 : Number(a) - Number(b)))
            .map(([k, v]) => `${k}: ${v}`)
            .join(', ')}
        </div>
      )}
    </div>
  );
}

const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '10px',
  },
  title: {
    fontSize: '0.95rem',
    fontWeight: '600',
    color: 'var(--text-primary)',
  },
  hint: {
    fontSize: '0.85rem',
    color: 'var(--text-muted)',
    margin: 0,
  },
  summary: {
    fontSize: '0.9rem',
    color: 'var(--text-primary)',
    background: 'var(--input-bg)',
    padding: '8px 12px',
    borderRadius: '6px',
  },
};
