import { useState } from 'react';

/**
 * InteractiveGeometry - Display geometric shapes and calculate area/perimeter
 */
export default function InteractiveGeometry({
  type = 'triangle',
  base = 6,
  height = 4,
  width = 6,  // For rectangles
  answer = '',
  onChange,
  correctAnswer = null,
  readOnly = false,
  showFormula = true
}) {
  const [showWork, setShowWork] = useState('');

  const svgWidth = 300;
  const svgHeight = 200;
  const padding = 30;

  const renderTriangle = () => {
    const points = [
      [padding, svgHeight - padding],
      [svgWidth - padding, svgHeight - padding],
      [(svgWidth) / 2, padding + 20]
    ];

    return (
      <g>
        <polygon
          points={points.map(p => p.join(',')).join(' ')}
          fill="#bfdbfe"
          stroke="#3b82f6"
          strokeWidth={2}
        />
        {/* Base label */}
        <line
          x1={padding}
          y1={svgHeight - padding + 15}
          x2={svgWidth - padding}
          y2={svgHeight - padding + 15}
          stroke="#6b7280"
          strokeWidth={1}
        />
        <text
          x={svgWidth / 2}
          y={svgHeight - padding + 30}
          textAnchor="middle"
          fontSize={14}
          fill="#374151"
          fontWeight="bold"
        >
          b = {base}
        </text>

        {/* Height line (dashed) */}
        <line
          x1={svgWidth / 2}
          y1={svgHeight - padding}
          x2={svgWidth / 2}
          y2={padding + 20}
          stroke="#ef4444"
          strokeWidth={2}
          strokeDasharray="5,3"
        />
        <text
          x={svgWidth / 2 + 15}
          y={svgHeight / 2}
          fontSize={14}
          fill="#ef4444"
          fontWeight="bold"
        >
          h = {height}
        </text>

        {/* Right angle marker */}
        <path
          d={`M ${svgWidth / 2} ${svgHeight - padding - 15} L ${svgWidth / 2 + 15} ${svgHeight - padding - 15} L ${svgWidth / 2 + 15} ${svgHeight - padding}`}
          fill="none"
          stroke="#6b7280"
          strokeWidth={1}
        />
      </g>
    );
  };

  const renderRectangle = () => {
    const w = svgWidth - 2 * padding;
    const h = svgHeight - 2 * padding - 20;

    return (
      <g>
        <rect
          x={padding}
          y={padding}
          width={w}
          height={h}
          fill="#bbf7d0"
          stroke="#22c55e"
          strokeWidth={2}
        />
        {/* Width label */}
        <text
          x={svgWidth / 2}
          y={svgHeight - padding + 20}
          textAnchor="middle"
          fontSize={14}
          fill="#374151"
          fontWeight="bold"
        >
          w = {width || base}
        </text>

        {/* Height label */}
        <text
          x={svgWidth - padding + 15}
          y={padding + h / 2}
          fontSize={14}
          fill="#374151"
          fontWeight="bold"
        >
          h = {height}
        </text>
      </g>
    );
  };

  const getFormula = () => {
    switch (type) {
      case 'triangle':
        return 'A = ½ × base × height = ½ × b × h';
      case 'rectangle':
        return 'A = width × height = w × h';
      default:
        return '';
    }
  };

  const handleAnswerChange = (value) => {
    onChange?.({
      value: value,
      work: showWork
    });
  };

  const handleWorkChange = (value) => {
    setShowWork(value);
    onChange?.({
      value: typeof answer === 'object' ? answer.value : answer,
      work: value
    });
  };

  const displayAnswer = typeof answer === 'object' ? answer.value : answer;

  return (
    <div style={styles.container}>
      <svg width={svgWidth} height={svgHeight}>
        <rect x={0} y={0} width={svgWidth} height={svgHeight} fill="#fafafa" rx={8} />
        {type === 'triangle' && renderTriangle()}
        {type === 'rectangle' && renderRectangle()}
      </svg>

      {showFormula && (
        <div style={styles.formula}>
          <strong>Formula:</strong> {getFormula()}
        </div>
      )}

      <div style={styles.workSection}>
        <label style={styles.label}>Show your work:</label>
        <textarea
          style={styles.workArea}
          value={showWork}
          onChange={(e) => handleWorkChange(e.target.value)}
          placeholder={`Calculate: ½ × ${base} × ${height} = ...`}
          disabled={readOnly}
          rows={3}
        />
      </div>

      <div style={styles.answerSection}>
        <label style={styles.label}>Final Answer:</label>
        <div style={styles.answerRow}>
          <span style={styles.areaLabel}>Area =</span>
          <input
            type="text"
            style={styles.answerInput}
            value={displayAnswer}
            onChange={(e) => handleAnswerChange(e.target.value)}
            placeholder="?"
            disabled={readOnly}
          />
          <span style={styles.unit}>square units</span>
        </div>
      </div>

      {correctAnswer && (
        <div style={styles.correct}>
          <strong>Correct Answer:</strong> {correctAnswer}
        </div>
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
    padding: '10px',
  },
  formula: {
    fontSize: '0.95rem',
    color: '#4b5563',
    background: '#f3f4f6',
    padding: '10px 15px',
    borderRadius: '6px',
    fontFamily: 'monospace',
  },
  workSection: {
    width: '100%',
    maxWidth: '400px',
  },
  label: {
    display: 'block',
    fontSize: '0.9rem',
    fontWeight: '500',
    color: '#4b5563',
    marginBottom: '5px',
  },
  workArea: {
    width: '100%',
    padding: '10px',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    fontSize: '1rem',
    fontFamily: 'monospace',
    resize: 'vertical',
  },
  answerSection: {
    width: '100%',
    maxWidth: '400px',
  },
  answerRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
  },
  areaLabel: {
    fontSize: '1rem',
    fontWeight: '600',
    color: '#374151',
  },
  answerInput: {
    width: '100px',
    padding: '10px',
    border: '2px solid #6366f1',
    borderRadius: '6px',
    fontSize: '1.1rem',
    fontWeight: '600',
    textAlign: 'center',
  },
  unit: {
    fontSize: '0.9rem',
    color: '#6b7280',
  },
  correct: {
    padding: '10px 15px',
    background: '#dcfce7',
    borderRadius: '6px',
    color: '#166534',
    fontSize: '0.9rem',
  },
};
