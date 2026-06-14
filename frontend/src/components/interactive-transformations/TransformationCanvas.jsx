/**
 * TransformationCanvas — SVG grid + shapes layer for InteractiveTransformations.
 * Pure display/interaction component; all state and logic live in the parent.
 */
export default function TransformationCanvas({
  svgRef,
  svgSize,
  padding,
  gridMin,
  gridMax,
  gridSpan,
  toSvgX,
  toSvgY,
  drawPolygon,
  originalVertices,
  transformationType,
  transformParams,
  expectedVertices,
  correctVertices,
  userVertices,
  handleSvgClick,
  readOnly,
  mode,
}) {
  return (
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
  );
}
