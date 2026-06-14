/**
 * BoxPlotSvg — pure SVG renderer for InteractiveBoxPlot.
 * Receives pre-computed stats + scale helpers; no state or effects.
 */
export default function BoxPlotSvg({
  stats,
  labels,
  svgWidth,
  svgHeight,
  padding,
  boxHeight,
  scaleMin,
  scaleMax,
  valToX,
}) {
  return (
    <svg width={svgWidth} height={svgHeight}>
      <rect x={0} y={0} width={svgWidth} height={svgHeight} style={{ fill: 'var(--input-bg)' }} rx={8} />

      {/* Scale line and ticks */}
      <line
        x1={padding}
        y1={svgHeight - 30}
        x2={svgWidth - padding}
        y2={svgHeight - 30}
        style={{ stroke: 'var(--text-primary)' }}
        strokeWidth={1}
      />
      {Array.from({ length: 11 }, (_, i) => {
        const val = scaleMin + (i / 10) * (scaleMax - scaleMin);
        return (
          <g key={i}>
            <line
              x1={valToX(val)}
              y1={svgHeight - 35}
              x2={valToX(val)}
              y2={svgHeight - 25}
              style={{ stroke: 'var(--text-primary)' }}
              strokeWidth={1}
            />
            <text
              x={valToX(val)}
              y={svgHeight - 10}
              textAnchor="middle"
              fontSize={10}
              style={{ fill: 'var(--text-muted)' }}
            >
              {Math.round(val)}
            </text>
          </g>
        );
      })}

      {/* Box plots */}
      {stats.map((s, idx) => {
        const y = 40 + idx * 60;

        return (
          <g key={idx}>
            {/* Label */}
            <text
              x={10}
              y={y + boxHeight / 2 + 4}
              fontSize={11}
              style={{ fill: 'var(--text-primary)' }}
              fontWeight="500"
            >
              {labels[idx] || `Set ${idx + 1}`}
            </text>

            {/* Whiskers */}
            <line
              x1={valToX(s.min)}
              y1={y + boxHeight / 2}
              x2={valToX(s.q1)}
              y2={y + boxHeight / 2}
              style={{ stroke: 'var(--text-primary)' }}
              strokeWidth={2}
            />
            <line
              x1={valToX(s.q3)}
              y1={y + boxHeight / 2}
              x2={valToX(s.max)}
              y2={y + boxHeight / 2}
              style={{ stroke: 'var(--text-primary)' }}
              strokeWidth={2}
            />

            {/* Whisker caps */}
            <line
              x1={valToX(s.min)}
              y1={y + 5}
              x2={valToX(s.min)}
              y2={y + boxHeight - 5}
              style={{ stroke: 'var(--text-primary)' }}
              strokeWidth={2}
            />
            <line
              x1={valToX(s.max)}
              y1={y + 5}
              x2={valToX(s.max)}
              y2={y + boxHeight - 5}
              style={{ stroke: 'var(--text-primary)' }}
              strokeWidth={2}
            />

            {/* Box */}
            <rect
              x={valToX(s.q1)}
              y={y}
              width={valToX(s.q3) - valToX(s.q1)}
              height={boxHeight}
              fill="#bfdbfe"
              stroke="#3b82f6"
              strokeWidth={2}
            />

            {/* Median line */}
            <line
              x1={valToX(s.median)}
              y1={y}
              x2={valToX(s.median)}
              y2={y + boxHeight}
              stroke="#1d4ed8"
              strokeWidth={3}
            />

            {/* Value labels on hover points */}
            <circle cx={valToX(s.min)} cy={y + boxHeight / 2} r={4} fill="#6366f1" />
            <circle cx={valToX(s.q1)} cy={y + boxHeight / 2} r={4} fill="#8b5cf6" />
            <circle cx={valToX(s.median)} cy={y + boxHeight / 2} r={4} fill="#ec4899" />
            <circle cx={valToX(s.q3)} cy={y + boxHeight / 2} r={4} fill="#f59e0b" />
            <circle cx={valToX(s.max)} cy={y + boxHeight / 2} r={4} fill="#10b981" />
          </g>
        );
      })}

      {/* Legend */}
      <g transform={`translate(${padding}, 10)`}>
        {[
          { label: 'Min', color: '#6366f1' },
          { label: 'Q1', color: '#8b5cf6' },
          { label: 'Med', color: '#ec4899' },
          { label: 'Q3', color: '#f59e0b' },
          { label: 'Max', color: '#10b981' },
        ].map((item, i) => (
          <g key={i} transform={`translate(${i * 70}, 0)`}>
            <circle cx={0} cy={5} r={5} fill={item.color} />
            <text x={10} y={9} fontSize={10} fill="#374151">{item.label}</text>
          </g>
        ))}
      </g>
    </svg>
  );
}
