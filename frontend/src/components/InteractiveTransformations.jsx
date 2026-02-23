import { useState, useRef } from 'react';

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

      <svg ref={svgRef} width={svgSize} height={svgSize}
        style={{ cursor: readOnly || mode !== 'plot' ? 'default' : 'crosshair' }}
        onClick={handleSvgClick}>
        <rect x={0} y={0} width={svgSize} height={svgSize} style={{ fill: 'var(--input-bg)' }} rx={8} />

        {/* Grid lines */}
        {Array.from({ length: gridSpan + 1 }, (_, i) => {
          const val = gridMin + i;
          return (
            <g key={i}>
              <line x1={toSvgX(val)} y1={padding} x2={toSvgX(val)} y2={svgSize - padding}
                stroke={val === 0 ? 'var(--text-primary)' : 'rgba(255,255,255,0.07)'}
                strokeWidth={val === 0 ? 1.5 : 0.5} />
              <line x1={padding} y1={toSvgY(val)} x2={svgSize - padding} y2={toSvgY(val)}
                stroke={val === 0 ? 'var(--text-primary)' : 'rgba(255,255,255,0.07)'}
                strokeWidth={val === 0 ? 1.5 : 0.5} />
              {val !== 0 && val % 2 === 0 && (
                <>
                  <text x={toSvgX(val)} y={toSvgY(0) + 14} textAnchor="middle" fontSize={9} style={{ fill: 'var(--text-muted)' }}>{val}</text>
                  <text x={toSvgX(0) - 6} y={toSvgY(val) + 3} textAnchor="end" fontSize={9} style={{ fill: 'var(--text-muted)' }}>{val}</text>
                </>
              )}
            </g>
          );
        })}

        {/* Reflection axis line */}
        {transformationType === 'reflection' && (
          <>
            {transformParams.axis === 'y-axis' && (
              <line x1={toSvgX(0)} y1={padding} x2={toSvgX(0)} y2={svgSize - padding}
                stroke="#f59e0b" strokeWidth={2} strokeDasharray="6,3" />
            )}
            {transformParams.axis === 'x-axis' && (
              <line x1={padding} y1={toSvgY(0)} x2={svgSize - padding} y2={toSvgY(0)}
                stroke="#f59e0b" strokeWidth={2} strokeDasharray="6,3" />
            )}
            {transformParams.axis === 'y=x' && (
              <line x1={toSvgX(gridMin)} y1={toSvgY(gridMin)} x2={toSvgX(gridMax)} y2={toSvgY(gridMax)}
                stroke="#f59e0b" strokeWidth={2} strokeDasharray="6,3" />
            )}
          </>
        )}

        {/* Original shape */}
        {drawPolygon(originalVertices, 'rgba(99, 102, 241, 0.2)', '#6366f1', 2)}
        {originalVertices.map(([x, y], i) => (
          <g key={`orig-${i}`}>
            <circle cx={toSvgX(x)} cy={toSvgY(y)} r={5} fill="#6366f1" stroke="#fff" strokeWidth={1.5} />
            <text x={toSvgX(x) + 8} y={toSvgY(y) - 8} fontSize={10} fontWeight="bold" style={{ fill: '#6366f1' }}>
              {String.fromCharCode(65 + i)}
            </text>
          </g>
        ))}

        {/* Expected (correct) shape - show when reviewing */}
        {correctVertices && (
          <>
            {drawPolygon(expectedVertices, 'rgba(34, 197, 94, 0.15)', '#22c55e', 2)}
            {expectedVertices.map(([x, y], i) => (
              <circle key={`exp-${i}`} cx={toSvgX(x)} cy={toSvgY(y)} r={4}
                fill="#22c55e" stroke="#fff" strokeWidth={1} />
            ))}
          </>
        )}

        {/* User-plotted vertices */}
        {userVertices.length >= 2 && drawPolygon(userVertices, 'rgba(236, 72, 153, 0.2)', '#ec4899', 2)}
        {userVertices.map(([x, y], i) => (
          <g key={`user-${i}`}>
            <circle cx={toSvgX(x)} cy={toSvgY(y)} r={5} fill="#ec4899" stroke="#fff" strokeWidth={1.5} />
            <text x={toSvgX(x) + 8} y={toSvgY(y) - 8} fontSize={10} fontWeight="bold" style={{ fill: '#ec4899' }}>
              {String.fromCharCode(65 + i)}'
            </text>
          </g>
        ))}
      </svg>

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
