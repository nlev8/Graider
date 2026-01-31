import { useState, useMemo } from 'react';

/**
 * InteractiveBoxPlot - Display box plot and answer questions about it
 */
export default function InteractiveBoxPlot({
  data = [[50, 55, 60, 65, 70, 75, 80, 85, 90]],
  labels = ['Data Set'],
  answers = {},
  onChange,
  correctAnswers = null,
  readOnly = false
}) {
  // Calculate statistics for each dataset
  const stats = useMemo(() => {
    return data.map(dataset => {
      const sorted = [...dataset].sort((a, b) => a - b);
      const n = sorted.length;
      const min = sorted[0];
      const max = sorted[n - 1];
      const median = n % 2 === 0
        ? (sorted[n / 2 - 1] + sorted[n / 2]) / 2
        : sorted[Math.floor(n / 2)];

      const lowerHalf = sorted.slice(0, Math.floor(n / 2));
      const upperHalf = sorted.slice(Math.ceil(n / 2));

      const q1 = lowerHalf.length % 2 === 0
        ? (lowerHalf[lowerHalf.length / 2 - 1] + lowerHalf[lowerHalf.length / 2]) / 2
        : lowerHalf[Math.floor(lowerHalf.length / 2)];

      const q3 = upperHalf.length % 2 === 0
        ? (upperHalf[upperHalf.length / 2 - 1] + upperHalf[upperHalf.length / 2]) / 2
        : upperHalf[Math.floor(upperHalf.length / 2)];

      return { min, q1, median, q3, max, range: max - min, iqr: q3 - q1 };
    });
  }, [data]);

  const svgWidth = 500;
  const svgHeight = 150 + (data.length - 1) * 60;
  const padding = 50;
  const boxHeight = 30;

  // Find overall min/max for scale
  const allValues = data.flat();
  const scaleMin = Math.min(...allValues) - 5;
  const scaleMax = Math.max(...allValues) + 5;

  const valToX = (val) => {
    return padding + ((val - scaleMin) / (scaleMax - scaleMin)) * (svgWidth - 2 * padding);
  };

  const handleInputChange = (field, value) => {
    onChange?.({ ...answers, [field]: value });
  };

  const fields = [
    { key: 'min', label: 'Minimum', color: '#6366f1' },
    { key: 'q1', label: 'Q1 (First Quartile)', color: '#8b5cf6' },
    { key: 'median', label: 'Median', color: '#ec4899' },
    { key: 'q3', label: 'Q3 (Third Quartile)', color: '#f59e0b' },
    { key: 'max', label: 'Maximum', color: '#10b981' },
    { key: 'range', label: 'Range (Max - Min)', color: '#6b7280' },
    { key: 'iqr', label: 'IQR (Q3 - Q1)', color: '#6b7280' },
  ];

  return (
    <div style={styles.container}>
      {/* Box Plot SVG */}
      <svg width={svgWidth} height={svgHeight}>
        <rect x={0} y={0} width={svgWidth} height={svgHeight} fill="#fafafa" rx={8} />

        {/* Scale line and ticks */}
        <line
          x1={padding}
          y1={svgHeight - 30}
          x2={svgWidth - padding}
          y2={svgHeight - 30}
          stroke="#374151"
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
                stroke="#374151"
                strokeWidth={1}
              />
              <text
                x={valToX(val)}
                y={svgHeight - 10}
                textAnchor="middle"
                fontSize={10}
                fill="#6b7280"
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
                fill="#374151"
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
                stroke="#374151"
                strokeWidth={2}
              />
              <line
                x1={valToX(s.q3)}
                y1={y + boxHeight / 2}
                x2={valToX(s.max)}
                y2={y + boxHeight / 2}
                stroke="#374151"
                strokeWidth={2}
              />

              {/* Whisker caps */}
              <line
                x1={valToX(s.min)}
                y1={y + 5}
                x2={valToX(s.min)}
                y2={y + boxHeight - 5}
                stroke="#374151"
                strokeWidth={2}
              />
              <line
                x1={valToX(s.max)}
                y1={y + 5}
                x2={valToX(s.max)}
                y2={y + boxHeight - 5}
                stroke="#374151"
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

      {/* Answer inputs */}
      <div style={styles.answersGrid}>
        {fields.map(field => {
          const isCorrect = correctAnswers
            ? Math.abs(parseFloat(answers[field.key]) - stats[0][field.key]) < 0.5
            : null;

          return (
            <div key={field.key} style={styles.answerRow}>
              <label style={{ ...styles.answerLabel, borderLeftColor: field.color }}>
                {field.label}:
              </label>
              <input
                type="number"
                step="0.1"
                value={answers[field.key] || ''}
                onChange={(e) => handleInputChange(field.key, e.target.value)}
                disabled={readOnly}
                style={{
                  ...styles.answerInput,
                  borderColor: isCorrect === true ? '#22c55e' : isCorrect === false ? '#ef4444' : '#d1d5db',
                  background: isCorrect === true ? '#f0fdf4' : isCorrect === false ? '#fef2f2' : '#fff',
                }}
              />
              {correctAnswers && (
                <span style={styles.correctValue}>
                  {isCorrect ? '✓' : `(${stats[0][field.key]})`}
                </span>
              )}
            </div>
          );
        })}
      </div>

      {!readOnly && (
        <p style={styles.hint}>
          Examine the box plot and fill in the five-number summary plus range and IQR.
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
    gap: '15px',
  },
  answersGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
    gap: '10px',
    width: '100%',
    maxWidth: '500px',
  },
  answerRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  answerLabel: {
    fontSize: '0.85rem',
    color: '#374151',
    minWidth: '130px',
    borderLeft: '3px solid',
    paddingLeft: '8px',
  },
  answerInput: {
    width: '70px',
    padding: '8px',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    fontSize: '1rem',
    textAlign: 'center',
  },
  correctValue: {
    fontSize: '0.85rem',
    color: '#16a34a',
    fontWeight: '500',
  },
  hint: {
    fontSize: '0.85rem',
    color: '#6b7280',
    margin: 0,
  },
};
