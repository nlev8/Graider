import { useState, useRef, useEffect } from 'react';

/**
 * InteractiveNumberLine - Click to plot points on a number line
 */
export default function InteractiveNumberLine({
  minVal = -10,
  maxVal = 10,
  points = [],
  onChange,
  correctPoints = null,
  readOnly = false,
  labels = [],
  step = 1
}) {
  const svgRef = useRef(null);
  const [hoveredPoint, setHoveredPoint] = useState(null);
  const [dragIndex, setDragIndex] = useState(null);

  const width = 600;
  const height = 100;
  const padding = 40;
  const lineY = height / 2;

  // Convert value to x position
  const valToX = (val) => {
    return padding + ((val - minVal) / (maxVal - minVal)) * (width - 2 * padding);
  };

  // Convert x position to value
  const xToVal = (x) => {
    const val = minVal + ((x - padding) / (width - 2 * padding)) * (maxVal - minVal);
    // Snap to step
    return Math.round(val / step) * step;
  };

  const handleClick = (e) => {
    if (readOnly) return;

    const svg = svgRef.current;
    const rect = svg.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const val = xToVal(x);

    if (val >= minVal && val <= maxVal) {
      // Check if clicking on existing point to remove it
      const existingIdx = points.findIndex(p => Math.abs(p - val) < step / 2);
      if (existingIdx >= 0) {
        const newPoints = [...points];
        newPoints.splice(existingIdx, 1);
        onChange?.(newPoints);
      } else {
        onChange?.([...points, val]);
      }
    }
  };

  const handleMouseMove = (e) => {
    if (dragIndex === null || readOnly) return;

    const svg = svgRef.current;
    const rect = svg.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const val = xToVal(x);

    if (val >= minVal && val <= maxVal) {
      const newPoints = [...points];
      newPoints[dragIndex] = val;
      onChange?.(newPoints);
    }
  };

  const handleMouseUp = () => {
    setDragIndex(null);
  };

  useEffect(() => {
    if (dragIndex !== null) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
      return () => {
        window.removeEventListener('mousemove', handleMouseMove);
        window.removeEventListener('mouseup', handleMouseUp);
      };
    }
  }, [dragIndex, points]);

  // Generate tick marks
  const ticks = [];
  for (let i = minVal; i <= maxVal; i += step) {
    ticks.push(i);
  }

  return (
    <div style={styles.container}>
      <svg
        ref={svgRef}
        width={width}
        height={height}
        style={{ cursor: readOnly ? 'default' : 'crosshair' }}
        onClick={handleClick}
      >
        {/* Main line */}
        <line
          x1={padding - 10}
          y1={lineY}
          x2={width - padding + 10}
          y2={lineY}
          stroke="#374151"
          strokeWidth={2}
        />

        {/* Arrows */}
        <polygon
          points={`${width - padding + 15},${lineY} ${width - padding + 5},${lineY - 5} ${width - padding + 5},${lineY + 5}`}
          fill="#374151"
        />
        <polygon
          points={`${padding - 15},${lineY} ${padding - 5},${lineY - 5} ${padding - 5},${lineY + 5}`}
          fill="#374151"
        />

        {/* Tick marks and labels */}
        {ticks.map((val) => (
          <g key={val}>
            <line
              x1={valToX(val)}
              y1={lineY - 8}
              x2={valToX(val)}
              y2={lineY + 8}
              stroke="#374151"
              strokeWidth={val === 0 ? 2 : 1}
            />
            <text
              x={valToX(val)}
              y={lineY + 25}
              textAnchor="middle"
              fontSize={12}
              fill="#4b5563"
            >
              {val}
            </text>
          </g>
        ))}

        {/* Correct points (if showing answers) */}
        {correctPoints?.map((val, idx) => (
          <g key={`correct-${idx}`}>
            <circle
              cx={valToX(val)}
              cy={lineY}
              r={10}
              fill="#dcfce7"
              stroke="#22c55e"
              strokeWidth={2}
            />
            <text
              x={valToX(val)}
              y={lineY - 18}
              textAnchor="middle"
              fontSize={11}
              fill="#16a34a"
              fontWeight="bold"
            >
              {val}
            </text>
          </g>
        ))}

        {/* User-plotted points */}
        {points.map((val, idx) => {
          const isCorrect = correctPoints?.some(cp => Math.abs(cp - val) < step / 2);
          return (
            <g key={idx}>
              <circle
                cx={valToX(val)}
                cy={lineY}
                r={hoveredPoint === idx ? 12 : 10}
                fill={isCorrect === true ? '#22c55e' : isCorrect === false ? '#ef4444' : '#6366f1'}
                stroke="#fff"
                strokeWidth={2}
                style={{ cursor: readOnly ? 'default' : 'grab', transition: 'r 0.1s' }}
                onMouseEnter={() => setHoveredPoint(idx)}
                onMouseLeave={() => setHoveredPoint(null)}
                onMouseDown={(e) => {
                  e.stopPropagation();
                  if (!readOnly) setDragIndex(idx);
                }}
              />
              <text
                x={valToX(val)}
                y={lineY - 18}
                textAnchor="middle"
                fontSize={11}
                fill="#1f2937"
                fontWeight="bold"
              >
                {labels[idx] || val}
              </text>
            </g>
          );
        })}
      </svg>

      {!readOnly && (
        <p style={styles.hint}>
          Click on the number line to plot points. Click a point again to remove it. Drag points to move them.
        </p>
      )}

      {points.length > 0 && (
        <div style={styles.pointsList}>
          <strong>Plotted points:</strong> {points.map(p => p.toFixed(2)).join(', ')}
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
  hint: {
    fontSize: '0.85rem',
    color: '#6b7280',
    margin: 0,
  },
  pointsList: {
    fontSize: '0.9rem',
    color: '#374151',
    background: '#f3f4f6',
    padding: '8px 12px',
    borderRadius: '6px',
  },
};
