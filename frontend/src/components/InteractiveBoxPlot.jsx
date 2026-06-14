import { useState, useMemo } from 'react';
import BoxPlotSvg from './interactive-box-plot/BoxPlotSvg.jsx';

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
      {/* Box Plot SVG — rendered by BoxPlotSvg child */}
      <BoxPlotSvg
        stats={stats}
        labels={labels}
        svgWidth={svgWidth}
        svgHeight={svgHeight}
        padding={padding}
        boxHeight={boxHeight}
        scaleMin={scaleMin}
        scaleMax={scaleMax}
        valToX={valToX}
      />

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
                  borderColor: isCorrect === true ? '#22c55e' : isCorrect === false ? '#ef4444' : 'var(--glass-border)',
                  background: isCorrect === true ? 'rgba(16, 185, 129, 0.1)' : isCorrect === false ? 'rgba(239, 68, 68, 0.1)' : 'var(--input-bg)',
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
    color: 'var(--text-primary)',
    minWidth: '130px',
    borderLeft: '3px solid',
    paddingLeft: '8px',
  },
  answerInput: {
    width: '70px',
    padding: '8px',
    border: '1px solid var(--glass-border)',
    borderRadius: '6px',
    fontSize: '1rem',
    textAlign: 'center',
    color: 'var(--text-primary)',
  },
  correctValue: {
    fontSize: '0.85rem',
    color: '#16a34a',
    fontWeight: '500',
  },
  hint: {
    fontSize: '0.85rem',
    color: 'var(--text-muted)',
    margin: 0,
  },
};
