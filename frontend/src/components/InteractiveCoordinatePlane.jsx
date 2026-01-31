import { useState, useRef, useEffect } from 'react';

/**
 * InteractiveCoordinatePlane - Click to plot points on a coordinate plane
 */
export default function InteractiveCoordinatePlane({
  xRange = [-6, 6],
  yRange = [-6, 6],
  points = [],
  labels = [],
  onChange,
  correctPoints = null,
  readOnly = false,
  showQuadrants = true
}) {
  const svgRef = useRef(null);
  const [hoveredPoint, setHoveredPoint] = useState(null);
  const [dragIndex, setDragIndex] = useState(null);
  const [cursorPos, setCursorPos] = useState(null);

  const size = 400;
  const padding = 40;
  const gridSize = size - 2 * padding;

  // Convert value to position
  const valToX = (val) => {
    return padding + ((val - xRange[0]) / (xRange[1] - xRange[0])) * gridSize;
  };
  const valToY = (val) => {
    return padding + ((yRange[1] - val) / (yRange[1] - yRange[0])) * gridSize;
  };

  // Convert position to value
  const xToVal = (x) => {
    const val = xRange[0] + ((x - padding) / gridSize) * (xRange[1] - xRange[0]);
    return Math.round(val);
  };
  const yToVal = (y) => {
    const val = yRange[1] - ((y - padding) / gridSize) * (yRange[1] - yRange[0]);
    return Math.round(val);
  };

  const handleClick = (e) => {
    if (readOnly) return;

    const svg = svgRef.current;
    const rect = svg.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const valX = xToVal(x);
    const valY = yToVal(y);

    if (valX >= xRange[0] && valX <= xRange[1] && valY >= yRange[0] && valY <= yRange[1]) {
      // Check if clicking on existing point to remove it
      const existingIdx = points.findIndex(p => p[0] === valX && p[1] === valY);
      if (existingIdx >= 0) {
        const newPoints = [...points];
        newPoints.splice(existingIdx, 1);
        onChange?.(newPoints);
      } else {
        onChange?.([...points, [valX, valY]]);
      }
    }
  };

  const handleMouseMove = (e) => {
    const svg = svgRef.current;
    const rect = svg.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    setCursorPos({ x: xToVal(x), y: yToVal(y) });

    if (dragIndex !== null && !readOnly) {
      const valX = xToVal(x);
      const valY = yToVal(y);

      if (valX >= xRange[0] && valX <= xRange[1] && valY >= yRange[0] && valY <= yRange[1]) {
        const newPoints = [...points];
        newPoints[dragIndex] = [valX, valY];
        onChange?.(newPoints);
      }
    }
  };

  const handleMouseUp = () => {
    setDragIndex(null);
  };

  const handleMouseLeave = () => {
    setCursorPos(null);
  };

  useEffect(() => {
    if (dragIndex !== null) {
      window.addEventListener('mouseup', handleMouseUp);
      return () => window.removeEventListener('mouseup', handleMouseUp);
    }
  }, [dragIndex]);

  // Generate grid lines
  const gridLines = [];
  for (let x = xRange[0]; x <= xRange[1]; x++) {
    gridLines.push({ type: 'v', val: x });
  }
  for (let y = yRange[0]; y <= yRange[1]; y++) {
    gridLines.push({ type: 'h', val: y });
  }

  const getQuadrant = (x, y) => {
    if (x > 0 && y > 0) return 'I';
    if (x < 0 && y > 0) return 'II';
    if (x < 0 && y < 0) return 'III';
    if (x > 0 && y < 0) return 'IV';
    return '';
  };

  const pointColors = ['#6366f1', '#ec4899', '#f59e0b', '#10b981', '#3b82f6', '#8b5cf6'];

  return (
    <div style={styles.container}>
      <svg
        ref={svgRef}
        width={size}
        height={size}
        style={{ cursor: readOnly ? 'default' : 'crosshair' }}
        onClick={handleClick}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
      >
        {/* Background */}
        <rect x={padding} y={padding} width={gridSize} height={gridSize} fill="#fafafa" />

        {/* Grid lines */}
        {gridLines.map((line, idx) => (
          <line
            key={idx}
            x1={line.type === 'v' ? valToX(line.val) : padding}
            y1={line.type === 'h' ? valToY(line.val) : padding}
            x2={line.type === 'v' ? valToX(line.val) : padding + gridSize}
            y2={line.type === 'h' ? valToY(line.val) : padding + gridSize}
            stroke={line.val === 0 ? '#374151' : '#e5e7eb'}
            strokeWidth={line.val === 0 ? 2 : 1}
          />
        ))}

        {/* Axis labels */}
        {[...Array(xRange[1] - xRange[0] + 1)].map((_, i) => {
          const val = xRange[0] + i;
          if (val === 0) return null;
          return (
            <text
              key={`x-${val}`}
              x={valToX(val)}
              y={valToY(0) + 15}
              textAnchor="middle"
              fontSize={10}
              fill="#6b7280"
            >
              {val}
            </text>
          );
        })}
        {[...Array(yRange[1] - yRange[0] + 1)].map((_, i) => {
          const val = yRange[0] + i;
          if (val === 0) return null;
          return (
            <text
              key={`y-${val}`}
              x={valToX(0) - 12}
              y={valToY(val) + 4}
              textAnchor="middle"
              fontSize={10}
              fill="#6b7280"
            >
              {val}
            </text>
          );
        })}

        {/* Origin */}
        <text x={valToX(0) - 10} y={valToY(0) + 15} fontSize={10} fill="#6b7280">0</text>

        {/* Axis labels */}
        <text x={size - 15} y={valToY(0) + 4} fontSize={12} fill="#374151" fontWeight="bold">x</text>
        <text x={valToX(0) + 8} y={20} fontSize={12} fill="#374151" fontWeight="bold">y</text>

        {/* Quadrant labels */}
        {showQuadrants && (
          <>
            <text x={valToX(xRange[1] * 0.6)} y={valToY(yRange[1] * 0.6)} fontSize={20} fill="#e5e7eb" fontWeight="bold">I</text>
            <text x={valToX(xRange[0] * 0.6)} y={valToY(yRange[1] * 0.6)} fontSize={20} fill="#e5e7eb" fontWeight="bold">II</text>
            <text x={valToX(xRange[0] * 0.6)} y={valToY(yRange[0] * 0.6)} fontSize={20} fill="#e5e7eb" fontWeight="bold">III</text>
            <text x={valToX(xRange[1] * 0.6)} y={valToY(yRange[0] * 0.6)} fontSize={20} fill="#e5e7eb" fontWeight="bold">IV</text>
          </>
        )}

        {/* Correct points (if showing answers) */}
        {correctPoints?.map((pt, idx) => (
          <g key={`correct-${idx}`}>
            <circle
              cx={valToX(pt[0])}
              cy={valToY(pt[1])}
              r={12}
              fill="#dcfce7"
              stroke="#22c55e"
              strokeWidth={2}
              strokeDasharray="4,2"
            />
          </g>
        ))}

        {/* User-plotted points */}
        {points.map((pt, idx) => {
          const isCorrect = correctPoints?.some(cp => cp[0] === pt[0] && cp[1] === pt[1]);
          const color = isCorrect === true ? '#22c55e' : isCorrect === false ? '#ef4444' : pointColors[idx % pointColors.length];
          const label = labels[idx] || String.fromCharCode(65 + idx); // A, B, C, ...

          return (
            <g key={idx}>
              <circle
                cx={valToX(pt[0])}
                cy={valToY(pt[1])}
                r={hoveredPoint === idx ? 10 : 8}
                fill={color}
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
                x={valToX(pt[0]) + 12}
                y={valToY(pt[1]) - 8}
                fontSize={12}
                fill="#1f2937"
                fontWeight="bold"
              >
                {label}({pt[0]}, {pt[1]})
              </text>
            </g>
          );
        })}

        {/* Cursor position indicator */}
        {!readOnly && cursorPos && (
          <text
            x={size - padding}
            y={padding - 10}
            fontSize={11}
            fill="#6b7280"
            textAnchor="end"
          >
            ({cursorPos.x}, {cursorPos.y})
          </text>
        )}
      </svg>

      {!readOnly && (
        <p style={styles.hint}>
          Click to plot points. Click an existing point to remove it. Drag points to move them.
        </p>
      )}

      {points.length > 0 && (
        <div style={styles.pointsList}>
          <strong>Plotted points:</strong>{' '}
          {points.map((p, i) => (
            <span key={i} style={{ ...styles.pointTag, background: pointColors[i % pointColors.length] }}>
              {labels[i] || String.fromCharCode(65 + i)}({p[0]}, {p[1]})
            </span>
          ))}
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
    display: 'flex',
    flexWrap: 'wrap',
    gap: '6px',
    alignItems: 'center',
  },
  pointTag: {
    color: '#fff',
    padding: '2px 8px',
    borderRadius: '4px',
    fontSize: '0.85rem',
    fontWeight: '500',
  },
};
