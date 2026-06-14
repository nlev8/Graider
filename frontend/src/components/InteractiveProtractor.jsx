import { useState, useRef } from 'react';
import ProtractorCanvas from './interactive-protractor/ProtractorCanvas.jsx';

/**
 * InteractiveProtractor - Angle measurement and construction tool.
 * Students measure given angles or construct angles of specified degrees.
 * Supports: measure, construct, classify, complementary/supplementary. Grades 4-8.
 *
 * SVG rendering is delegated to ProtractorCanvas (CQ 7→8 wave-2 Protocol-FE split).
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
      <ProtractorCanvas
        svgRef={svgRef}
        svgSize={svgSize}
        cx={cx}
        cy={cy}
        outerR={outerR}
        innerR={innerR}
        ticks={ticks}
        displayAngle={displayAngle}
        givenAngle={givenAngle}
        arcR={arcR}
        arcEndX={arcEndX}
        arcEndY={arcEndY}
        largeArc={largeArc}
        rayEndX={rayEndX}
        rayEndY={rayEndY}
        mode={mode}
        readOnly={readOnly}
        degToRad={degToRad}
        handleSvgClick={handleSvgClick}
      />

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
