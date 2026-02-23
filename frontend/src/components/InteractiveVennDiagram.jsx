import { useState } from 'react';

/**
 * InteractiveVennDiagram - 2-3 overlapping circles for set operations.
 * Students place items, fill in counts, or identify regions.
 * Used in probability, logic, data classification. Grades 6-12.
 */
export default function InteractiveVennDiagram({
  sets = 2,
  labels = ['Set A', 'Set B', 'Set C'],
  regions = {},
  answers = {},
  onChange,
  correctAnswers = null,
  readOnly = false,
  title = '',
  mode = 'count'
}) {
  const svgWidth = sets === 3 ? 480 : 420;
  const svgHeight = sets === 3 ? 380 : 320;
  const cx = svgWidth / 2;
  const cy = svgHeight / 2;
  const r = sets === 3 ? 100 : 110;

  // Circle positions
  const circles = sets === 3
    ? [
        { cx: cx - 55, cy: cy - 30, label: labels[0], color: '#6366f1' },
        { cx: cx + 55, cy: cy - 30, label: labels[1], color: '#ec4899' },
        { cx: cx, cy: cy + 40, label: labels[2], color: '#10b981' },
      ]
    : [
        { cx: cx - 60, cy: cy, label: labels[0], color: '#6366f1' },
        { cx: cx + 60, cy: cy, label: labels[1], color: '#ec4899' },
      ];

  // Region definitions for inputs
  const regionKeys = sets === 3
    ? [
        { key: 'only_a', label: 'Only ' + labels[0], x: cx - 100, y: cy - 50 },
        { key: 'only_b', label: 'Only ' + labels[1], x: cx + 100, y: cy - 50 },
        { key: 'only_c', label: 'Only ' + labels[2], x: cx, y: cy + 80 },
        { key: 'a_and_b', label: labels[0] + ' ' + String.fromCharCode(8745) + ' ' + labels[1], x: cx, y: cy - 50 },
        { key: 'a_and_c', label: labels[0] + ' ' + String.fromCharCode(8745) + ' ' + labels[2], x: cx - 55, y: cy + 25 },
        { key: 'b_and_c', label: labels[1] + ' ' + String.fromCharCode(8745) + ' ' + labels[2], x: cx + 55, y: cy + 25 },
        { key: 'all', label: 'All three', x: cx, y: cy },
        { key: 'outside', label: 'Outside all', x: 40, y: svgHeight - 30 },
      ]
    : [
        { key: 'only_a', label: 'Only ' + labels[0], x: cx - 95, y: cy },
        { key: 'only_b', label: 'Only ' + labels[1], x: cx + 95, y: cy },
        { key: 'a_and_b', label: labels[0] + ' ' + String.fromCharCode(8745) + ' ' + labels[1], x: cx, y: cy },
        { key: 'outside', label: 'Outside both', x: 40, y: svgHeight - 30 },
      ];

  const handleChange = (key, value) => {
    if (readOnly) return;
    onChange?.({ ...answers, [key]: value });
  };

  return (
    <div style={styles.container}>
      {title && <div style={styles.title}>{title}</div>}

      <svg width={svgWidth} height={svgHeight}>
        <rect x={0} y={0} width={svgWidth} height={svgHeight}
          style={{ fill: 'var(--input-bg)' }} rx={8} />

        {/* Universal set rectangle */}
        <rect x={10} y={10} width={svgWidth - 20} height={svgHeight - 20}
          fill="none" stroke="var(--text-muted)" strokeWidth={1.5} rx={6}
          strokeDasharray="4,4" />
        <text x={svgWidth - 20} y={25} textAnchor="end" fontSize={11}
          style={{ fill: 'var(--text-muted)' }}>U</text>

        {/* Circles */}
        {circles.map((c, i) => (
          <g key={i}>
            <circle cx={c.cx} cy={c.cy} r={r}
              fill={c.color} fillOpacity={0.1}
              stroke={c.color} strokeWidth={2} />
            {/* Label above circle */}
            <text
              x={c.cx}
              y={i === 2 ? c.cy + r + 20 : c.cy - r - 8}
              textAnchor="middle" fontSize={13} fontWeight="700"
              style={{ fill: c.color }}>
              {c.label}
            </text>
          </g>
        ))}

        {/* Region values/inputs */}
        {regionKeys.map((region) => {
          const displayVal = regions[region.key];
          const isHidden = displayVal === undefined || displayVal === null;
          const userVal = answers[region.key] || '';
          const correctVal = correctAnswers?.[region.key];
          const isCorrect = correctVal !== undefined
            ? String(userVal).trim() === String(correctVal).trim()
            : null;

          return (
            <g key={region.key}>
              {isHidden || mode === 'count' ? (
                <foreignObject x={region.x - 22} y={region.y - 12} width={44} height={26}>
                  <input
                    type="text"
                    value={userVal}
                    onChange={(e) => handleChange(region.key, e.target.value)}
                    disabled={readOnly}
                    placeholder="?"
                    style={{
                      ...styles.regionInput,
                      borderColor: isCorrect === true ? '#22c55e'
                        : isCorrect === false ? '#ef4444'
                        : 'rgba(99,102,241,0.4)',
                      background: isCorrect === true ? 'rgba(16,185,129,0.1)'
                        : isCorrect === false ? 'rgba(239,68,68,0.1)'
                        : 'rgba(99,102,241,0.08)',
                    }}
                  />
                </foreignObject>
              ) : (
                <text x={region.x} y={region.y + 4} textAnchor="middle"
                  fontSize={14} fontWeight="600"
                  style={{ fill: 'var(--text-primary)' }}>
                  {displayVal}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {/* Region legend */}
      {mode === 'count' && !readOnly && (
        <div style={styles.legendGrid}>
          {regionKeys.map((region) => (
            <div key={region.key} style={styles.legendRow}>
              <span style={styles.legendLabel}>{region.label}:</span>
              <span style={styles.legendVal}>{answers[region.key] || '?'}</span>
            </div>
          ))}
        </div>
      )}

      {/* Text answer for set operation questions */}
      <div style={styles.answerSection}>
        <label style={styles.label}>Answer:</label>
        <input
          type="text"
          value={answers.final || ''}
          onChange={(e) => handleChange('final', e.target.value)}
          disabled={readOnly}
          placeholder="Enter your answer"
          style={styles.finalInput}
        />
        {correctAnswers?.final && (
          <span style={styles.correctHint}>
            {String(answers.final).trim() === String(correctAnswers.final).trim()
              ? String.fromCharCode(10003) : correctAnswers.final}
          </span>
        )}
      </div>
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
  title: {
    fontSize: '0.95rem',
    fontWeight: '600',
    color: 'var(--text-primary)',
  },
  regionInput: {
    width: '40px',
    padding: '3px',
    border: '1px solid rgba(99,102,241,0.4)',
    borderRadius: '4px',
    fontSize: '12px',
    fontWeight: '700',
    textAlign: 'center',
    color: 'var(--text-primary)',
    background: 'rgba(99,102,241,0.08)',
  },
  legendGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
    gap: '4px',
    width: '100%',
    maxWidth: '400px',
    fontSize: '0.8rem',
  },
  legendRow: {
    display: 'flex',
    justifyContent: 'space-between',
    padding: '3px 8px',
    background: 'var(--input-bg)',
    borderRadius: '4px',
  },
  legendLabel: {
    color: 'var(--text-secondary)',
  },
  legendVal: {
    fontWeight: '600',
    color: 'var(--text-primary)',
  },
  answerSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    width: '100%',
    maxWidth: '300px',
    alignItems: 'center',
  },
  label: {
    fontSize: '0.9rem',
    fontWeight: '500',
    color: 'var(--text-secondary)',
  },
  finalInput: {
    width: '200px',
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
};
