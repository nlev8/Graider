import { useState, useRef } from 'react';
import TransformationCanvas from './interactive-transformations/TransformationCanvas.jsx';

/**
 * InteractiveTransformations - Apply geometric transformations on a coordinate grid.
 * Students plot transformed vertices or identify transformation type.
 * Supports: translation, reflection, rotation, dilation. Grades 8-10.
 */
export default function InteractiveTransformations({
  originalVertices = [[1, 1], [4, 1], [4, 3]],
  transformationType = 'translation',
  transformParams = {},
  userVertices = [],
  answer = '',
  onChange,
  correctVertices = null,
  correctAnswer = null,
  readOnly = false,
  gridRange = [-8, 8],
  mode = 'plot'
}) {
  const svgRef = useRef(null);
  const svgSize = 440;
  const padding = 30;
  const gridMin = gridRange[0];
  const gridMax = gridRange[1];
  const gridSpan = gridMax - gridMin;
  const cellSize = (svgSize - 2 * padding) / gridSpan;

  const toSvgX = (x) => padding + (x - gridMin) * cellSize;
  const toSvgY = (y) => padding + (gridMax - y) * cellSize;
  const fromSvgX = (px) => Math.round((px - padding) / cellSize + gridMin);
  const fromSvgY = (py) => Math.round(gridMax - (py - padding) / cellSize);

  const computeTransformed = () => {
    return originalVertices.map(([x, y]) => {
      switch (transformationType) {
        case 'translation': {
          const dx = transformParams.dx || 0;
          const dy = transformParams.dy || 0;
          return [x + dx, y + dy];
        }
        case 'reflection': {
          const axis = transformParams.axis || 'y-axis';
          if (axis === 'y-axis') return [-x, y];
          if (axis === 'x-axis') return [x, -y];
          if (axis === 'y=x') return [y, x];
          if (axis === 'y=-x') return [-y, -x];
          return [x, y];
        }
        case 'rotation': {
          const deg = transformParams.degrees || 90;
          const rad = (deg * Math.PI) / 180;
          const centerX = transformParams.centerX || 0;
          const centerY = transformParams.centerY || 0;
          const nx = Math.round((x - centerX) * Math.cos(rad) - (y - centerY) * Math.sin(rad) + centerX);
          const ny = Math.round((x - centerX) * Math.sin(rad) + (y - centerY) * Math.cos(rad) + centerY);
          return [nx, ny];
        }
        case 'dilation': {
          const scale = transformParams.scale || 2;
          const centerX = transformParams.centerX || 0;
          const centerY = transformParams.centerY || 0;
          return [
            Math.round(centerX + scale * (x - centerX)),
            Math.round(centerY + scale * (y - centerY))
          ];
        }
        default:
          return [x, y];
      }
    });
  };

  const expectedVertices = correctVertices || computeTransformed();

  const handleSvgClick = (e) => {
    if (readOnly || mode !== 'plot') return;
    const svg = svgRef.current;
    const rect = svg.getBoundingClientRect();
    const px = e.clientX - rect.left;
    const py = e.clientY - rect.top;
    const x = fromSvgX(px);
    const y = fromSvgY(py);

    if (x < gridMin || x > gridMax || y < gridMin || y > gridMax) return;

    const existIdx = userVertices.findIndex(([vx, vy]) => vx === x && vy === y);
    let next;
    if (existIdx >= 0) {
      next = userVertices.filter((_, i) => i !== existIdx);
    } else {
      next = [...userVertices, [x, y]];
    }
    onChange?.({ vertices: next, answer });
  };

  const handleAnswerChange = (val) => {
    onChange?.({ vertices: userVertices, answer: val });
  };

  const getTransformLabel = () => {
    switch (transformationType) {
      case 'translation': return `Translation: (x + ${transformParams.dx || 0}, y + ${transformParams.dy || 0})`;
      case 'reflection': return `Reflection over ${transformParams.axis || 'y-axis'}`;
      case 'rotation': return `Rotation ${transformParams.degrees || 90}${String.fromCharCode(176)} around (${transformParams.centerX || 0}, ${transformParams.centerY || 0})`;
      case 'dilation': return `Dilation scale factor ${transformParams.scale || 2} from (${transformParams.centerX || 0}, ${transformParams.centerY || 0})`;
      default: return transformationType;
    }
  };

  const drawPolygon = (verts, fill, stroke, strokeWidth) => {
    if (verts.length < 2) return null;
    const points = verts.map(([x, y]) => `${toSvgX(x)},${toSvgY(y)}`).join(' ');
    return (
      <polygon
        points={points}
        fill={fill}
        stroke={stroke}
        strokeWidth={strokeWidth}
        strokeLinejoin="round"
      />
    );
  };

  return (
    <div style={styles.container}>
      <div style={styles.transformLabel}>{getTransformLabel()}</div>

      <TransformationCanvas
        svgRef={svgRef}
        svgSize={svgSize}
        padding={padding}
        gridMin={gridMin}
        gridMax={gridMax}
        gridSpan={gridSpan}
        toSvgX={toSvgX}
        toSvgY={toSvgY}
        drawPolygon={drawPolygon}
        originalVertices={originalVertices}
        transformationType={transformationType}
        transformParams={transformParams}
        expectedVertices={expectedVertices}
        correctVertices={correctVertices}
        userVertices={userVertices}
        handleSvgClick={handleSvgClick}
        readOnly={readOnly}
        mode={mode}
      />

      {mode === 'identify' && (
        <div style={styles.identifySection}>
          <label style={styles.label}>Identify the transformation:</label>
          <input
            type="text"
            value={answer}
            onChange={(e) => handleAnswerChange(e.target.value)}
            disabled={readOnly}
            placeholder="e.g. reflection over y-axis"
            style={styles.textInput}
          />
          {correctAnswer && (
            <span style={styles.correctHint}>{correctAnswer}</span>
          )}
        </div>
      )}

      {mode === 'plot' && !readOnly && (
        <p style={styles.hint}>
          Click grid points to plot the transformed vertices ({String.fromCharCode(65)}'...{String.fromCharCode(65 + originalVertices.length - 1)}').
          Click a point again to remove it.
        </p>
      )}

      {userVertices.length > 0 && (
        <div style={styles.pointsList}>
          <strong>Your vertices:</strong>{' '}
          {userVertices.map(([x, y], i) => `${String.fromCharCode(65 + i)}'(${x}, ${y})`).join(', ')}
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
  transformLabel: {
    fontSize: '0.95rem',
    fontWeight: '600',
    color: 'var(--text-primary)',
    padding: '8px 14px',
    background: 'rgba(99, 102, 241, 0.1)',
    borderRadius: '6px',
    border: '1px solid rgba(99, 102, 241, 0.2)',
  },
  identifySection: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
    width: '100%',
    maxWidth: '400px',
  },
  label: {
    fontSize: '0.9rem',
    fontWeight: '500',
    color: 'var(--text-secondary)',
  },
  textInput: {
    padding: '10px',
    border: '1px solid var(--glass-border)',
    borderRadius: '6px',
    fontSize: '1rem',
    background: 'var(--input-bg)',
    color: 'var(--text-primary)',
  },
  correctHint: {
    fontSize: '0.85rem',
    color: '#22c55e',
    fontWeight: '500',
  },
  hint: {
    fontSize: '0.85rem',
    color: 'var(--text-muted)',
    margin: 0,
    textAlign: 'center',
  },
  pointsList: {
    fontSize: '0.9rem',
    color: 'var(--text-primary)',
    background: 'var(--input-bg)',
    padding: '8px 12px',
    borderRadius: '6px',
  },
};
