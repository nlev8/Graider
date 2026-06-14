/**
 * NumberLineSvg — the SVG canvas layer extracted from InteractiveNumberLine.
 * Receives all data and handlers as props; contains no state or effects of its own.
 * Pure-prop extraction: every prop here maps 1-to-1 to a variable the parent already had.
 */
export default function NumberLineSvg({
  svgRef,
  width,
  height,
  padding,
  lineY,
  readOnly,
  handleClick,
  ticks,
  valToX,
  correctPoints,
  points,
  step,
  hoveredPoint,
  setHoveredPoint,
  setDragIndex,
  labels,
}) {
  return (
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
        style={{ stroke: 'var(--text-primary)' }}
        strokeWidth={2}
      />

      {/* Arrows */}
      <polygon
        points={`${width - padding + 15},${lineY} ${width - padding + 5},${lineY - 5} ${width - padding + 5},${lineY + 5}`}
        style={{ fill: 'var(--text-primary)' }}
      />
      <polygon
        points={`${padding - 15},${lineY} ${padding - 5},${lineY - 5} ${padding - 5},${lineY + 5}`}
        style={{ fill: 'var(--text-primary)' }}
      />

      {/* Tick marks and labels */}
      {ticks.map((val) => (
        <g key={val}>
          <line
            x1={valToX(val)}
            y1={lineY - 8}
            x2={valToX(val)}
            y2={lineY + 8}
            style={{ stroke: 'var(--text-primary)' }}
            strokeWidth={val === 0 ? 2 : 1}
          />
          <text
            x={valToX(val)}
            y={lineY + 25}
            textAnchor="middle"
            fontSize={12}
            style={{ fill: 'var(--text-secondary)' }}
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
              style={{ fill: 'var(--text-primary)' }}
              fontWeight="bold"
            >
              {labels[idx] || val}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
