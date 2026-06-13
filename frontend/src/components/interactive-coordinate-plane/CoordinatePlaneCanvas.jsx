/**
 * CoordinatePlaneCanvas — the SVG grid, axes, labels, and point layers
 * extracted from InteractiveCoordinatePlane (Protocol-FE, cq8 wave 2).
 * Receives all values/handlers as pure props; contains no state of its own.
 */
export default function CoordinatePlaneCanvas({
  svgRef,
  size,
  padding,
  gridSize,
  xRange,
  yRange,
  gridLines,
  showQuadrants,
  valToX,
  valToY,
  readOnly,
  points,
  labels,
  correctPoints,
  hoveredPoint,
  setHoveredPoint,
  dragIndex,
  setDragIndex,
  cursorPos,
  pointColors,
  handleClick,
  handleMouseMove,
  handleMouseLeave,
}) {
  return (
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
      <rect x={padding} y={padding} width={gridSize} height={gridSize} style={{ fill: 'var(--input-bg)' }} />

      {/* Grid lines */}
      {gridLines.map((line, idx) => (
        <line
          key={idx}
          x1={line.type === 'v' ? valToX(line.val) : padding}
          y1={line.type === 'h' ? valToY(line.val) : padding}
          x2={line.type === 'v' ? valToX(line.val) : padding + gridSize}
          y2={line.type === 'h' ? valToY(line.val) : padding + gridSize}
          style={{ stroke: line.val === 0 ? 'var(--text-primary)' : 'var(--glass-border)' }}
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
            style={{ fill: 'var(--text-muted)' }}
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
            style={{ fill: 'var(--text-muted)' }}
          >
            {val}
          </text>
        );
      })}

      {/* Origin */}
      <text x={valToX(0) - 10} y={valToY(0) + 15} fontSize={10} style={{ fill: 'var(--text-muted)' }}>0</text>

      {/* Axis labels */}
      <text x={size - 15} y={valToY(0) + 4} fontSize={12} style={{ fill: 'var(--text-primary)' }} fontWeight="bold">x</text>
      <text x={valToX(0) + 8} y={20} fontSize={12} style={{ fill: 'var(--text-primary)' }} fontWeight="bold">y</text>

      {/* Quadrant labels */}
      {showQuadrants && (
        <>
          <text x={valToX(xRange[1] * 0.6)} y={valToY(yRange[1] * 0.6)} fontSize={20} style={{ fill: 'var(--glass-border)' }} fontWeight="bold">I</text>
          <text x={valToX(xRange[0] * 0.6)} y={valToY(yRange[1] * 0.6)} fontSize={20} style={{ fill: 'var(--glass-border)' }} fontWeight="bold">II</text>
          <text x={valToX(xRange[0] * 0.6)} y={valToY(yRange[0] * 0.6)} fontSize={20} style={{ fill: 'var(--glass-border)' }} fontWeight="bold">III</text>
          <text x={valToX(xRange[1] * 0.6)} y={valToY(yRange[0] * 0.6)} fontSize={20} style={{ fill: 'var(--glass-border)' }} fontWeight="bold">IV</text>
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
              style={{ fill: 'var(--text-primary)' }}
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
          style={{ fill: 'var(--text-muted)' }}
          textAnchor="end"
        >
          ({cursorPos.x}, {cursorPos.y})
        </text>
      )}
    </svg>
  );
}
