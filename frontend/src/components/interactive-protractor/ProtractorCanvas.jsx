/**
 * ProtractorCanvas — SVG rendering layer for InteractiveProtractor.
 * Extracted from InteractiveProtractor.jsx (CQ 7→8 wave-2 Protocol-FE split).
 * Pure prop receiver: no fetches, no state, no effects. Renders the
 * semi-circle body, tick marks, degree labels, angle ray, arc, and
 * right-angle mark. Parent passes all geometry and event handlers.
 */
export default function ProtractorCanvas({
  svgRef,
  svgSize,
  cx,
  cy,
  outerR,
  innerR,
  ticks,
  displayAngle,
  givenAngle,
  arcR,
  arcEndX,
  arcEndY,
  largeArc,
  rayEndX,
  rayEndY,
  mode,
  readOnly,
  degToRad,
  handleSvgClick,
}) {
  return (
    <svg
      ref={svgRef}
      width={svgSize}
      height={svgSize - 80}
      onClick={handleSvgClick}
      style={{ cursor: mode === 'construct' && !readOnly ? 'crosshair' : 'default' }}
    >
      <rect
        x={0}
        y={0}
        width={svgSize}
        height={svgSize - 80}
        style={{ fill: 'var(--input-bg)' }}
        rx={8}
      />

      {/* Protractor body (semi-circle) */}
      <path
        d={`M ${cx - outerR} ${cy} A ${outerR} ${outerR} 0 0 1 ${cx + outerR} ${cy}`}
        fill="rgba(99, 102, 241, 0.06)"
        stroke="#6366f1"
        strokeWidth={2}
      />
      <path
        d={`M ${cx - innerR} ${cy} A ${innerR} ${innerR} 0 0 1 ${cx + innerR} ${cy}`}
        fill="none"
        stroke="rgba(99, 102, 241, 0.3)"
        strokeWidth={1}
      />

      {/* Baseline */}
      <line
        x1={cx - outerR - 15}
        y1={cy}
        x2={cx + outerR + 15}
        y2={cy}
        stroke="var(--text-primary)"
        strokeWidth={2}
      />

      {/* Tick marks */}
      {ticks.map((t) => (
        <g key={t.deg}>
          <line
            x1={t.x1}
            y1={t.y1}
            x2={t.x2}
            y2={t.y2}
            stroke={t.isMajor ? 'var(--text-primary)' : 'rgba(99,102,241,0.3)'}
            strokeWidth={t.isMajor ? 1.5 : 0.8}
          />
          {t.isMajor && t.deg % 30 === 0 && (
            <text
              x={cx + (innerR - 22) * Math.cos(Math.PI - degToRad(t.deg))}
              y={cy - (innerR - 22) * Math.sin(Math.PI - degToRad(t.deg)) + 4}
              textAnchor="middle"
              fontSize={10}
              fontWeight="500"
              style={{ fill: 'var(--text-secondary)' }}
            >
              {t.deg}{String.fromCharCode(176)}
            </text>
          )}
        </g>
      ))}

      {/* Center point */}
      <circle cx={cx} cy={cy} r={4} fill="#6366f1" />

      {/* Base ray (0 degrees) */}
      <line
        x1={cx}
        y1={cy}
        x2={cx + outerR + 10}
        y2={cy}
        stroke="var(--text-primary)"
        strokeWidth={2}
      />

      {/* Angle ray */}
      <line x1={cx} y1={cy} x2={rayEndX} y2={rayEndY} stroke="#ec4899" strokeWidth={2.5} />
      <circle cx={rayEndX} cy={rayEndY} r={3} fill="#ec4899" />

      {/* Angle arc */}
      <path
        d={`M ${cx + arcR} ${cy} A ${arcR} ${arcR} 0 ${largeArc} 0 ${arcEndX} ${arcEndY}`}
        fill="rgba(236, 72, 153, 0.15)"
        stroke="#ec4899"
        strokeWidth={2}
      />

      {/* Angle value display */}
      <text
        x={cx + 35 * Math.cos(Math.PI - degToRad(displayAngle / 2))}
        y={cy - 35 * Math.sin(Math.PI - degToRad(displayAngle / 2)) + 4}
        textAnchor="middle"
        fontSize={14}
        fontWeight="700"
        style={{ fill: '#ec4899' }}
      >
        {mode === 'measure' && givenAngle ? '' : displayAngle + String.fromCharCode(176)}
      </text>

      {/* Right angle mark */}
      {displayAngle === 90 && (
        <rect
          x={cx + 8}
          y={cy - 18}
          width={10}
          height={10}
          fill="none"
          stroke="#ec4899"
          strokeWidth={1.5}
        />
      )}
    </svg>
  );
}
