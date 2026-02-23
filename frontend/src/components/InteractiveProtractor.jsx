import { useState, useRef } from 'react';

/**
 * InteractiveProtractor - Angle measurement and construction tool.
 * Students measure given angles or construct angles of specified degrees.
 * Supports: measure, construct, classify, complementary/supplementary. Grades 4-8.
 */
export default function InteractiveProtractor({
  givenAngle = null,
  targetAngle = null,
  mode = 'measure',
  answer = '',
  userAngle = 0,
  onChange,
  correctAnswer = null,
  readOnly = false,
  showClassification = true
}) {
  const svgRef = useRef(null);
  const svgSize = 400;
  const cx = svgSize / 2;
  const cy = svgSize - 60;
  const outerR = 160;
  const innerR = 130;

  const displayAngle = mode === 'construct' ? userAngle : (givenAngle || 45);

  const degToRad = (d) => (d * Math.PI) / 180;

  const classifyAngle = (deg) => {
    if (deg === 0) return 'zero';
    if (deg < 90) return 'acute';
    if (deg === 90) return 'right';
    if (deg < 180) return 'obtuse';
    if (deg === 180) return 'straight';
    if (deg < 360) return 'reflex';
    return 'full';
  };

  const handleSvgClick = (e) => {
    if (readOnly || mode !== 'construct') return;
    const svg = svgRef.current;
    const rect = svg.getBoundingClientRect();
    const px = e.clientX - rect.left;
    const py = e.clientY - rect.top;

    // Calculate angle from center point
    const dx = px - cx;
    const dy = cy - py; // Flip y for standard math orientation
    let angleDeg = Math.atan2(dy, dx) * (180 / Math.PI);
    if (angleDeg < 0) angleDeg += 360;
    // Clamp to 0-180 for protractor
    angleDeg = Math.min(180, Math.max(0, angleDeg));
    // Snap to nearest 5 degrees
    angleDeg = Math.round(angleDeg / 5) * 5;

    onChange?.({ userAngle: angleDeg, answer });
  };

  const handleAnswerChange = (val) => {
    onChange?.({ userAngle, answer: val });
  };

  // Protractor arc ticks
  const ticks = [];
  for (let deg = 0; deg <= 180; deg += 5) {
    const rad = degToRad(deg);
    const isMajor = deg % 10 === 0;
    const tickR = isMajor ? innerR - 10 : innerR;
    ticks.push({
      deg,
      x1: cx + outerR * Math.cos(Math.PI - rad),
      y1: cy - outerR * Math.sin(Math.PI - rad),
      x2: cx + tickR * Math.cos(Math.PI - rad),
      y2: cy - tickR * Math.sin(Math.PI - rad),
      isMajor,
    });
  }

  // Angle arc
  const angleRad = degToRad(displayAngle);
  const arcR = 50;
  const arcEndX = cx + arcR * Math.cos(Math.PI - angleRad);
  const arcEndY = cy - arcR * Math.sin(Math.PI - angleRad);
  const largeArc = displayAngle > 180 ? 1 : 0;

  // Ray endpoint
  const rayEndX = cx + (outerR + 10) * Math.cos(Math.PI - angleRad);
  const rayEndY = cy - (outerR + 10) * Math.sin(Math.PI - angleRad);

  return (
    <div style={styles.container}>
      <svg ref={svgRef} width={svgSize} height={svgSize - 80}
        onClick={handleSvgClick}
        style={{ cursor: mode === 'construct' && !readOnly ? 'crosshair' : 'default' }}>
        <rect x={0} y={0} width={svgSize} height={svgSize - 80}
          style={{ fill: 'var(--input-bg)' }} rx={8} />

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
        <line x1={cx - outerR - 15} y1={cy} x2={cx + outerR + 15} y2={cy}
          stroke="var(--text-primary)" strokeWidth={2} />

        {/* Tick marks */}
        {ticks.map((t) => (
          <g key={t.deg}>
            <line x1={t.x1} y1={t.y1} x2={t.x2} y2={t.y2}
              stroke={t.isMajor ? 'var(--text-primary)' : 'rgba(99,102,241,0.3)'}
              strokeWidth={t.isMajor ? 1.5 : 0.8} />
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
        <line x1={cx} y1={cy} x2={cx + outerR + 10} y2={cy}
          stroke="var(--text-primary)" strokeWidth={2} />

        {/* Angle ray */}
        <line x1={cx} y1={cy} x2={rayEndX} y2={rayEndY}
          stroke="#ec4899" strokeWidth={2.5} />
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
          <rect x={cx + 8} y={cy - 18} width={10} height={10}
            fill="none" stroke="#ec4899" strokeWidth={1.5} />
        )}
      </svg>

      {/* Classification */}
      {showClassification && displayAngle > 0 && (
        <div style={styles.classification}>
          <span style={styles.classLabel}>{classifyAngle(displayAngle)}</span>
          <span style={styles.classAngle}>{displayAngle}{String.fromCharCode(176)}</span>
          {displayAngle !== 90 && displayAngle < 180 && (
            <span style={styles.classExtra}>
              Complement: {90 - displayAngle}{String.fromCharCode(176)} | Supplement: {180 - displayAngle}{String.fromCharCode(176)}
            </span>
          )}
        </div>
      )}

      {/* Answer input */}
      <div style={styles.answerSection}>
        <label style={styles.label}>
          {mode === 'measure' ? 'What is the angle?' : mode === 'classify' ? 'Classify this angle:' : 'Your answer:'}
        </label>
        <input
          type="text"
          value={answer}
          onChange={(e) => handleAnswerChange(e.target.value)}
          disabled={readOnly}
          placeholder={mode === 'measure' ? 'e.g. 45' : mode === 'classify' ? 'e.g. acute' : '?'}
          style={styles.answerInput}
        />
        {correctAnswer && (
          <span style={styles.correctHint}>
            {String(answer).trim().toLowerCase() === String(correctAnswer).trim().toLowerCase()
              ? String.fromCharCode(10003) : correctAnswer}
          </span>
        )}
      </div>

      {mode === 'construct' && !readOnly && (
        <p style={styles.hint}>
          Click on the protractor to set the angle. Target: {targetAngle}{String.fromCharCode(176)}
        </p>
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
  classification: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '2px',
    padding: '8px 16px',
    background: 'rgba(236, 72, 153, 0.08)',
    borderRadius: '6px',
    border: '1px solid rgba(236, 72, 153, 0.2)',
  },
  classLabel: {
    fontSize: '1rem',
    fontWeight: '700',
    color: '#ec4899',
    textTransform: 'capitalize',
  },
  classAngle: {
    fontSize: '0.9rem',
    color: 'var(--text-secondary)',
  },
  classExtra: {
    fontSize: '0.8rem',
    color: 'var(--text-muted)',
  },
  answerSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    alignItems: 'center',
  },
  label: {
    fontSize: '0.9rem',
    fontWeight: '500',
    color: 'var(--text-secondary)',
  },
  answerInput: {
    width: '150px',
    padding: '10px',
    border: '2px solid #6366f1',
    borderRadius: '6px',
    fontSize: '1.1rem',
    fontWeight: '600',
    textAlign: 'center',
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
  },
};
