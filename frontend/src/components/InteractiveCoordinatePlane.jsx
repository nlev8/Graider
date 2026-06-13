import { useState, useRef, useEffect } from 'react';
import CoordinatePlaneCanvas from './interactive-coordinate-plane/CoordinatePlaneCanvas.jsx';

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

  const pointColors = ['#6366f1', '#ec4899', '#f59e0b', '#10b981', '#3b82f6', '#8b5cf6'];

  return (
    <div style={styles.container}>
      <CoordinatePlaneCanvas
        svgRef={svgRef}
        size={size}
        padding={padding}
        gridSize={gridSize}
        xRange={xRange}
        yRange={yRange}
        gridLines={gridLines}
        showQuadrants={showQuadrants}
        valToX={valToX}
        valToY={valToY}
        readOnly={readOnly}
        points={points}
        labels={labels}
        correctPoints={correctPoints}
        hoveredPoint={hoveredPoint}
        setHoveredPoint={setHoveredPoint}
        dragIndex={dragIndex}
        setDragIndex={setDragIndex}
        cursorPos={cursorPos}
        pointColors={pointColors}
        handleClick={handleClick}
        handleMouseMove={handleMouseMove}
        handleMouseLeave={handleMouseLeave}
      />

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
    color: 'var(--text-muted)',
    margin: 0,
  },
  pointsList: {
    fontSize: '0.9rem',
    color: 'var(--text-primary)',
    background: 'var(--input-bg)',
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
