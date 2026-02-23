import { useState } from 'react';
import {
  renderTriangle, renderRectangle, renderCircle,
  renderTrapezoid, renderParallelogram,
  renderRectangularPrism, renderCylinder,
  renderRegularPolygon, renderSimilarity,
  renderPyramid, renderCone, renderSphere
} from './geometryRenderers';
import { getFormula, getAnswerLabel, getSvgDimensions } from './geometryConfig';

/**
 * InteractiveGeometry - Display geometric shapes and calculate area/perimeter/volume/etc.
 * Supports all shape types and modes defined in geometryConfig.js.
 */
export default function InteractiveGeometry({
  type = 'triangle',
  base = 6,
  height = 4,
  width = 6,
  radius,
  topBase,
  sides,
  sideLength,
  sideA, sideB, sideC,
  angle1, angle2, missingAngle,
  theta, trigFunc, missingSide,
  slantHeight,
  scale,
  mode = 'area',
  answer = '',
  onChange,
  correctAnswer = null,
  readOnly = false,
  showFormula = true,
  onInputFocus
}) {
  const [showWork, setShowWork] = useState('');

  const dims = getSvgDimensions(mode);
  const svgWidth = dims.width;
  const svgHeight = dims.height;
  const padding = 30;

  // Build props object to pass to renderers
  const shapeProps = {
    base, height, width, radius, topBase,
    sides, sideLength, sideA, sideB, sideC,
    angle1, angle2, missingAngle,
    theta, trigFunc, missingSide, slantHeight, scale, mode,
    slant_height: slantHeight
  };

  const RENDERERS = {
    triangle: renderTriangle,
    rectangle: renderRectangle,
    circle: renderCircle,
    trapezoid: renderTrapezoid,
    parallelogram: renderParallelogram,
    rectangular_prism: renderRectangularPrism,
    cylinder: renderCylinder,
    regular_polygon: renderRegularPolygon,
    similarity: renderSimilarity,
    pyramid: renderPyramid,
    cone: renderCone,
    sphere: renderSphere,
  };

  // Some modes imply a shape (pythagorean/trig/angles → triangle, similarity → similarity)
  const effectiveType = (mode === 'pythagorean' || mode === 'trig' || mode === 'angles')
    ? 'triangle'
    : mode === 'similarity'
      ? 'similarity'
      : type;

  const renderer = RENDERERS[effectiveType];
  const formula = getFormula(mode, effectiveType, trigFunc);
  const { label: answerLabel, unit: answerUnit } = getAnswerLabel(mode, effectiveType);

  const getPlaceholderHint = () => {
    switch (mode) {
      case 'area':
        if (effectiveType === 'triangle') return 'Calculate: ' + String.fromCharCode(189) + ' ' + String.fromCharCode(215) + ' ' + base + ' ' + String.fromCharCode(215) + ' ' + height + ' = ...';
        if (effectiveType === 'rectangle') return 'Calculate: ' + (width || base) + ' ' + String.fromCharCode(215) + ' ' + height + ' = ...';
        if (effectiveType === 'circle') return 'Calculate: ' + String.fromCharCode(960) + ' ' + String.fromCharCode(215) + ' ' + (radius || 5) + String.fromCharCode(178) + ' = ...';
        if (effectiveType === 'trapezoid') return 'Calculate: ' + String.fromCharCode(189) + '(' + (topBase || 4) + ' + ' + base + ') ' + String.fromCharCode(215) + ' ' + height + ' = ...';
        if (effectiveType === 'parallelogram') return 'Calculate: ' + base + ' ' + String.fromCharCode(215) + ' ' + height + ' = ...';
        return 'Show your calculation steps...';
      case 'perimeter':
        return 'Add all sides together...';
      case 'pythagorean':
        return 'Use a' + String.fromCharCode(178) + ' + b' + String.fromCharCode(178) + ' = c' + String.fromCharCode(178) + '...';
      case 'volume':
        return 'Calculate the volume...';
      case 'surface_area':
        return 'Calculate the surface area...';
      case 'angles':
        return 'Angles in a triangle sum to 180' + String.fromCharCode(176) + '...';
      case 'trig':
        return 'Use ' + (trigFunc || 'sin') + '(' + String.fromCharCode(952) + ') = ...';
      case 'similarity':
        return 'Use the scale factor to find the missing side...';
      default:
        return 'Show your work...';
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
        <rect x={0} y={0} width={svgWidth} height={svgHeight}
          style={{ fill: 'var(--input-bg)' }} rx={8} />
        {renderer && renderer(shapeProps, svgWidth, svgHeight, padding)}
      </svg>

      {showFormula && formula && (
        <div style={styles.formula}>
          <strong>Formula:</strong> {formula}
        </div>
      )}

      <div style={styles.workSection}>
        <label style={styles.label}>Show your work:</label>
        <textarea
          style={styles.workArea}
          value={showWork}
          onChange={(e) => handleWorkChange(e.target.value)}
          onFocus={(e) => onInputFocus?.(e.target, 'work', 'unicode')}
          placeholder={getPlaceholderHint()}
          disabled={readOnly}
          rows={3}
        />
      </div>

      <div style={styles.answerSection}>
        <label style={styles.label}>Final Answer:</label>
        <div style={styles.answerRow}>
          <span style={styles.areaLabel}>{answerLabel}</span>
          <input
            type="text"
            style={styles.answerInput}
            value={displayAnswer}
            onChange={(e) => handleAnswerChange(e.target.value)}
            onFocus={(e) => onInputFocus?.(e.target, 'answer', 'unicode')}
            placeholder="?"
            disabled={readOnly}
          />
          <span style={styles.unit}>{answerUnit}</span>
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
    color: 'var(--text-secondary)',
    background: 'var(--input-bg)',
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
    color: 'var(--text-secondary)',
    marginBottom: '5px',
  },
  workArea: {
    width: '100%',
    padding: '10px',
    border: '1px solid var(--glass-border)',
    borderRadius: '6px',
    fontSize: '1rem',
    fontFamily: 'monospace',
    resize: 'vertical',
    background: 'var(--input-bg)',
    color: 'var(--text-primary)',
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
    color: 'var(--text-primary)',
  },
  answerInput: {
    width: '100px',
    padding: '10px',
    border: '2px solid #6366f1',
    borderRadius: '6px',
    fontSize: '1.1rem',
    fontWeight: '600',
    textAlign: 'center',
    background: 'var(--input-bg)',
    color: 'var(--text-primary)',
  },
  unit: {
    fontSize: '0.9rem',
    color: 'var(--text-muted)',
  },
  correct: {
    padding: '10px 15px',
    background: 'rgba(16, 185, 129, 0.1)',
    borderRadius: '6px',
    color: '#10b981',
    fontSize: '0.9rem',
    border: '1px solid rgba(16, 185, 129, 0.2)',
  },
};
