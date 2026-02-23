import { useState } from 'react';

/**
 * InteractiveFractionModel - Visual fraction representations.
 * Supports: area model (rectangle), circle model (pie), strip model (bar).
 * Students shade parts to represent fractions. Grades 3-7.
 */
export default function InteractiveFractionModel({
  modelType = 'area',
  denominator = 4,
  correctNumerator = null,
  shaded = [],
  answer = '',
  onChange,
  correctAnswer = null,
  readOnly = false,
  showFractionInput = true,
  compareFractions = null
}) {
  const svgWidth = compareFractions ? 500 : 300;
  const svgHeight = modelType === 'circle' ? 280 : 200;

  const toggleShade = (idx) => {
    if (readOnly) return;
    const next = shaded.includes(idx)
      ? shaded.filter(i => i !== idx)
      : [...shaded, idx];
    onChange?.({ shaded: next, answer });
  };

  const handleAnswerChange = (val) => {
    onChange?.({ shaded, answer: val });
  };

  const renderAreaModel = (cx, cy, w, h, denom, shadedParts, label) => {
    const cellW = w / denom;
    return (
      <g>
        {label && (
          <text x={cx + w / 2} y={cy - 8} textAnchor="middle" fontSize={12}
            fontWeight="600" style={{ fill: 'var(--text-primary)' }}>{label}</text>
        )}
        {Array.from({ length: denom }, (_, i) => {
          const isFilled = shadedParts.includes(i);
          return (
            <rect
              key={i}
              x={cx + i * cellW}
              y={cy}
              width={cellW}
              height={h}
              fill={isFilled ? 'rgba(99, 102, 241, 0.5)' : 'transparent'}
              stroke="var(--text-primary)"
              strokeWidth={1.5}
              style={{ cursor: readOnly ? 'default' : 'pointer' }}
              onClick={() => toggleShade(i)}
            />
          );
        })}
      </g>
    );
  };

  const renderCircleModel = (cx, cy, radius, denom, shadedParts) => {
    const slices = [];
    for (let i = 0; i < denom; i++) {
      const startAngle = (i * 2 * Math.PI) / denom - Math.PI / 2;
      const endAngle = ((i + 1) * 2 * Math.PI) / denom - Math.PI / 2;
      const x1 = cx + radius * Math.cos(startAngle);
      const y1 = cy + radius * Math.sin(startAngle);
      const x2 = cx + radius * Math.cos(endAngle);
      const y2 = cy + radius * Math.sin(endAngle);
      const largeArc = denom <= 2 ? 1 : 0;

      const d = `M ${cx} ${cy} L ${x1} ${y1} A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2} Z`;
      const isFilled = shadedParts.includes(i);

      slices.push(
        <path
          key={i}
          d={d}
          fill={isFilled ? 'rgba(99, 102, 241, 0.5)' : 'transparent'}
          stroke="var(--text-primary)"
          strokeWidth={1.5}
          style={{ cursor: readOnly ? 'default' : 'pointer' }}
          onClick={() => toggleShade(i)}
        />
      );
    }
    return <g>{slices}</g>;
  };

  const renderStripModel = (cx, cy, w, h, denom, shadedParts, label) => {
    const cellW = w / denom;
    return (
      <g>
        {label && (
          <text x={cx + w / 2} y={cy - 8} textAnchor="middle" fontSize={12}
            fontWeight="600" style={{ fill: 'var(--text-primary)' }}>{label}</text>
        )}
        <rect x={cx} y={cy} width={w} height={h} fill="none"
          stroke="var(--text-primary)" strokeWidth={2} rx={4} />
        {Array.from({ length: denom }, (_, i) => {
          const isFilled = shadedParts.includes(i);
          return (
            <g key={i}>
              <rect
                x={cx + i * cellW}
                y={cy}
                width={cellW}
                height={h}
                fill={isFilled ? 'rgba(99, 102, 241, 0.5)' : 'transparent'}
                stroke="var(--text-primary)"
                strokeWidth={1}
                style={{ cursor: readOnly ? 'default' : 'pointer' }}
                onClick={() => toggleShade(i)}
              />
            </g>
          );
        })}
        {/* Fraction below */}
        <text x={cx + w / 2} y={cy + h + 20} textAnchor="middle" fontSize={14}
          fontWeight="600" style={{ fill: '#6366f1' }}>
          {shadedParts.length}/{denom}
        </text>
      </g>
    );
  };

  return (
    <div style={styles.container}>
      <svg width={svgWidth} height={svgHeight}>
        <rect x={0} y={0} width={svgWidth} height={svgHeight}
          style={{ fill: 'var(--input-bg)' }} rx={8} />

        {modelType === 'area' && !compareFractions && (
          renderAreaModel(30, 50, svgWidth - 60, 80, denominator, shaded)
        )}

        {modelType === 'circle' && !compareFractions && (
          renderCircleModel(svgWidth / 2, svgHeight / 2, 90, denominator, shaded)
        )}

        {modelType === 'strip' && !compareFractions && (
          renderStripModel(20, 60, svgWidth - 40, 50, denominator, shaded)
        )}

        {/* Compare mode: two fractions side by side */}
        {compareFractions && (
          <>
            {renderStripModel(20, 40, 200, 40, compareFractions.leftDenom || denominator,
              compareFractions.leftShaded || shaded, compareFractions.leftLabel || '')}
            <text x={svgWidth / 2} y={80} textAnchor="middle" fontSize={20}
              fontWeight="bold" style={{ fill: 'var(--text-primary)' }}>vs</text>
            {renderStripModel(280, 40, 200, 40, compareFractions.rightDenom || denominator,
              compareFractions.rightShaded || [], compareFractions.rightLabel || '')}
          </>
        )}
      </svg>

      {/* Fraction display */}
      {!compareFractions && (
        <div style={styles.fractionDisplay}>
          <span style={styles.fractionNum}>{shaded.length}</span>
          <span style={styles.fractionBar}></span>
          <span style={styles.fractionDen}>{denominator}</span>
          {shaded.length > 0 && (
            <span style={styles.fractionEqual}>
              = {(shaded.length / denominator * 100).toFixed(0)}%
            </span>
          )}
        </div>
      )}

      {showFractionInput && (
        <div style={styles.answerSection}>
          <label style={styles.label}>Your answer:</label>
          <input
            type="text"
            value={answer}
            onChange={(e) => handleAnswerChange(e.target.value)}
            disabled={readOnly}
            placeholder="e.g. 3/4 or 0.75"
            style={styles.textInput}
          />
          {correctAnswer && (
            <span style={styles.correctHint}>{correctAnswer}</span>
          )}
        </div>
      )}

      {!readOnly && (
        <p style={styles.hint}>
          {compareFractions
            ? 'Compare the two fractions and enter your answer below.'
            : 'Click sections to shade them, then write the fraction.'}
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
  fractionDisplay: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '2px',
    position: 'relative',
  },
  fractionNum: {
    fontSize: '1.4rem',
    fontWeight: '700',
    color: '#6366f1',
  },
  fractionBar: {
    width: '40px',
    height: '2px',
    background: 'var(--text-primary)',
  },
  fractionDen: {
    fontSize: '1.4rem',
    fontWeight: '700',
    color: '#6366f1',
  },
  fractionEqual: {
    fontSize: '0.9rem',
    color: 'var(--text-muted)',
    marginTop: '2px',
  },
  answerSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    width: '100%',
    maxWidth: '300px',
  },
  label: {
    fontSize: '0.9rem',
    fontWeight: '500',
    color: 'var(--text-secondary)',
  },
  textInput: {
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
    textAlign: 'center',
  },
  hint: {
    fontSize: '0.85rem',
    color: 'var(--text-muted)',
    margin: 0,
  },
};
