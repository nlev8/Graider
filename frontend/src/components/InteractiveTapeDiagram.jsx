import { useState } from 'react';

/**
 * InteractiveTapeDiagram - Bar/tape diagrams for ratio, proportion, and part-whole problems.
 * Students label segments or fill in missing values. Grades 3-8.
 */
export default function InteractiveTapeDiagram({
  tapes = [],
  answers = {},
  onChange,
  correctAnswers = null,
  readOnly = false,
  title = ''
}) {
  /*
    tapes structure:
    [
      {
        label: 'Boys',
        segments: [
          { value: 3, color: '#6366f1', hidden: false },
          { value: 3, color: '#6366f1', hidden: false },
          { value: 3, color: '#6366f1', hidden: true }
        ],
        total: 9,
        totalHidden: false
      },
      {
        label: 'Girls',
        segments: [
          { value: 4, color: '#ec4899', hidden: false },
          { value: 4, color: '#ec4899', hidden: false }
        ],
        total: 8,
        totalHidden: true
      }
    ]
  */

  const defaultTapes = tapes.length > 0 ? tapes : [
    {
      label: 'Part A',
      segments: [
        { value: 3, color: '#6366f1' },
        { value: 3, color: '#6366f1' },
        { value: 3, color: '#6366f1' }
      ],
      total: 9
    },
    {
      label: 'Part B',
      segments: [
        { value: 4, color: '#ec4899' },
        { value: 4, color: '#ec4899' }
      ],
      total: 8
    }
  ];

  const svgWidth = 500;
  const tapeHeight = 45;
  const tapeGap = 30;
  const labelWidth = 70;
  const totalWidth = 60;
  const padding = 20;
  const barAreaWidth = svgWidth - labelWidth - totalWidth - 2 * padding;
  const svgHeight = padding * 2 + defaultTapes.length * (tapeHeight + tapeGap) - tapeGap + 20;

  // Find max total for proportional sizing
  const maxTotal = Math.max(...defaultTapes.map(t =>
    t.total || t.segments.reduce((sum, s) => sum + (s.value || 1), 0)
  ));

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

        {defaultTapes.map((tape, tapeIdx) => {
          const y = padding + tapeIdx * (tapeHeight + tapeGap);
          const tapeTotal = tape.total || tape.segments.reduce((sum, s) => sum + (s.value || 1), 0);
          const barWidth = (tapeTotal / maxTotal) * barAreaWidth;
          let xPos = labelWidth + padding;

          return (
            <g key={tapeIdx}>
              {/* Tape label */}
              <text x={padding + labelWidth - 10} y={y + tapeHeight / 2 + 5}
                textAnchor="end" fontSize={13} fontWeight="600"
                style={{ fill: 'var(--text-primary)' }}>
                {tape.label}
              </text>

              {/* Segments */}
              {tape.segments.map((seg, segIdx) => {
                const segWidth = ((seg.value || 1) / tapeTotal) * barWidth;
                const sx = xPos;
                xPos += segWidth;
                const segKey = `tape${tapeIdx}_seg${segIdx}`;
                const isHidden = seg.hidden;

                return (
                  <g key={segIdx}>
                    <rect
                      x={sx} y={y}
                      width={segWidth} height={tapeHeight}
                      fill={seg.color || '#6366f1'}
                      fillOpacity={0.3}
                      stroke={seg.color || '#6366f1'}
                      strokeWidth={1.5}
                    />
                    {/* Segment value */}
                    {isHidden ? (
                      <foreignObject x={sx + segWidth / 2 - 22} y={y + tapeHeight / 2 - 12} width={44} height={24}>
                        <input
                          type="text"
                          value={answers[segKey] || ''}
                          onChange={(e) => handleChange(segKey, e.target.value)}
                          disabled={readOnly}
                          placeholder="?"
                          style={styles.segInput}
                        />
                      </foreignObject>
                    ) : (
                      <text x={sx + segWidth / 2} y={y + tapeHeight / 2 + 5}
                        textAnchor="middle" fontSize={14} fontWeight="600"
                        style={{ fill: 'var(--text-primary)' }}>
                        {seg.value}
                      </text>
                    )}
                  </g>
                );
              })}

              {/* Total bracket and value */}
              <line x1={labelWidth + padding + barWidth + 10} y1={y}
                x2={labelWidth + padding + barWidth + 10} y2={y + tapeHeight}
                stroke="var(--text-muted)" strokeWidth={1.5} />
              <line x1={labelWidth + padding + barWidth + 5} y1={y}
                x2={labelWidth + padding + barWidth + 10} y2={y}
                stroke="var(--text-muted)" strokeWidth={1.5} />
              <line x1={labelWidth + padding + barWidth + 5} y1={y + tapeHeight}
                x2={labelWidth + padding + barWidth + 10} y2={y + tapeHeight}
                stroke="var(--text-muted)" strokeWidth={1.5} />

              {tape.totalHidden ? (
                <foreignObject
                  x={labelWidth + padding + barWidth + 15}
                  y={y + tapeHeight / 2 - 12}
                  width={50} height={24}>
                  <input
                    type="text"
                    value={answers[`tape${tapeIdx}_total`] || ''}
                    onChange={(e) => handleChange(`tape${tapeIdx}_total`, e.target.value)}
                    disabled={readOnly}
                    placeholder="?"
                    style={styles.totalInput}
                  />
                </foreignObject>
              ) : (
                <text
                  x={labelWidth + padding + barWidth + 20}
                  y={y + tapeHeight / 2 + 5}
                  fontSize={14} fontWeight="700"
                  style={{ fill: 'var(--text-primary)' }}>
                  = {tapeTotal}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {/* Text answer input */}
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

      {!readOnly && (
        <p style={styles.hint}>Fill in the missing values in the tape diagram.</p>
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
  title: {
    fontSize: '0.95rem',
    fontWeight: '600',
    color: 'var(--text-primary)',
  },
  segInput: {
    width: '40px',
    padding: '2px 4px',
    border: '1px solid #6366f1',
    borderRadius: '4px',
    fontSize: '12px',
    fontWeight: '600',
    textAlign: 'center',
    background: 'rgba(99, 102, 241, 0.1)',
    color: 'var(--text-primary)',
  },
  totalInput: {
    width: '46px',
    padding: '2px 4px',
    border: '1px solid var(--glass-border)',
    borderRadius: '4px',
    fontSize: '12px',
    fontWeight: '600',
    textAlign: 'center',
    background: 'var(--input-bg)',
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
  hint: {
    fontSize: '0.85rem',
    color: 'var(--text-muted)',
    margin: 0,
  },
};
