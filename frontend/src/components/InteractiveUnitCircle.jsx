import { useState } from 'react';

/**
 * InteractiveUnitCircle - Unit circle with key angles, radians, and (cos, sin) coordinates.
 * Students fill in missing values. Used in trigonometry (grades 9-12).
 */
export default function InteractiveUnitCircle({
  hiddenAngles = [],
  hiddenValues = [],
  answers = {},
  onChange,
  correctAnswers = null,
  readOnly = false,
  showRadians = true,
  showCoordinates = true
}) {
  const svgSize = 460;
  const cx = svgSize / 2;
  const cy = svgSize / 2;
  const r = 170;

  const KEY_ANGLES = [
    { deg: 0, rad: '0', cos: '1', sin: '0' },
    { deg: 30, rad: String.fromCharCode(960) + '/6', cos: String.fromCharCode(8730) + '3/2', sin: '1/2' },
    { deg: 45, rad: String.fromCharCode(960) + '/4', cos: String.fromCharCode(8730) + '2/2', sin: String.fromCharCode(8730) + '2/2' },
    { deg: 60, rad: String.fromCharCode(960) + '/3', cos: '1/2', sin: String.fromCharCode(8730) + '3/2' },
    { deg: 90, rad: String.fromCharCode(960) + '/2', cos: '0', sin: '1' },
    { deg: 120, rad: '2' + String.fromCharCode(960) + '/3', cos: '-1/2', sin: String.fromCharCode(8730) + '3/2' },
    { deg: 135, rad: '3' + String.fromCharCode(960) + '/4', cos: '-' + String.fromCharCode(8730) + '2/2', sin: String.fromCharCode(8730) + '2/2' },
    { deg: 150, rad: '5' + String.fromCharCode(960) + '/6', cos: '-' + String.fromCharCode(8730) + '3/2', sin: '1/2' },
    { deg: 180, rad: String.fromCharCode(960), cos: '-1', sin: '0' },
    { deg: 210, rad: '7' + String.fromCharCode(960) + '/6', cos: '-' + String.fromCharCode(8730) + '3/2', sin: '-1/2' },
    { deg: 225, rad: '5' + String.fromCharCode(960) + '/4', cos: '-' + String.fromCharCode(8730) + '2/2', sin: '-' + String.fromCharCode(8730) + '2/2' },
    { deg: 240, rad: '4' + String.fromCharCode(960) + '/3', cos: '-1/2', sin: '-' + String.fromCharCode(8730) + '3/2' },
    { deg: 270, rad: '3' + String.fromCharCode(960) + '/2', cos: '0', sin: '-1' },
    { deg: 300, rad: '5' + String.fromCharCode(960) + '/3', cos: '1/2', sin: '-' + String.fromCharCode(8730) + '3/2' },
    { deg: 315, rad: '7' + String.fromCharCode(960) + '/4', cos: String.fromCharCode(8730) + '2/2', sin: '-' + String.fromCharCode(8730) + '2/2' },
    { deg: 330, rad: '11' + String.fromCharCode(960) + '/6', cos: String.fromCharCode(8730) + '3/2', sin: '-1/2' },
    { deg: 360, rad: '2' + String.fromCharCode(960), cos: '1', sin: '0' },
  ];

  const isHidden = (deg, field) => {
    if (hiddenAngles.includes(deg)) return true;
    if (hiddenValues.includes(field)) return true;
    return false;
  };

  const handleChange = (key, value) => {
    if (readOnly) return;
    onChange?.({ ...answers, [key]: value });
  };

  const degToRad = (deg) => (deg * Math.PI) / 180;

  return (
    <div style={styles.container}>
      <svg width={svgSize} height={svgSize}>
        <rect x={0} y={0} width={svgSize} height={svgSize} style={{ fill: 'var(--input-bg)' }} rx={8} />

        {/* Grid/Axes */}
        <line x1={20} y1={cy} x2={svgSize - 20} y2={cy} style={{ stroke: 'var(--text-primary)' }} strokeWidth={1.5} />
        <line x1={cx} y1={20} x2={cx} y2={svgSize - 20} style={{ stroke: 'var(--text-primary)' }} strokeWidth={1.5} />

        {/* Axis labels */}
        <text x={svgSize - 15} y={cy - 8} fontSize={12} style={{ fill: 'var(--text-muted)' }}>x</text>
        <text x={cx + 8} y={25} fontSize={12} style={{ fill: 'var(--text-muted)' }}>y</text>

        {/* Unit circle */}
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="#6366f1" strokeWidth={2} />

        {/* Quadrant labels */}
        <text x={cx + 40} y={cy - 40} fontSize={14} style={{ fill: 'rgba(99,102,241,0.3)' }} fontWeight="bold">I</text>
        <text x={cx - 55} y={cy - 40} fontSize={14} style={{ fill: 'rgba(99,102,241,0.3)' }} fontWeight="bold">II</text>
        <text x={cx - 60} y={cy + 55} fontSize={14} style={{ fill: 'rgba(99,102,241,0.3)' }} fontWeight="bold">III</text>
        <text x={cx + 40} y={cy + 55} fontSize={14} style={{ fill: 'rgba(99,102,241,0.3)' }} fontWeight="bold">IV</text>

        {/* Angle points and labels */}
        {KEY_ANGLES.filter(a => a.deg < 360).map((angle) => {
          const rad = degToRad(angle.deg);
          const px = cx + r * Math.cos(rad);
          const py = cy - r * Math.sin(rad);
          const outerR = r + 30;
          const labelX = cx + outerR * Math.cos(rad);
          const labelY = cy - outerR * Math.sin(rad);

          const degHidden = isHidden(angle.deg, 'degrees');
          const radHidden = isHidden(angle.deg, 'radians');
          const coordHidden = isHidden(angle.deg, 'coordinates');

          const degKey = `deg_${angle.deg}`;
          const radKey = `rad_${angle.deg}`;
          const cosKey = `cos_${angle.deg}`;
          const sinKey = `sin_${angle.deg}`;

          return (
            <g key={angle.deg}>
              {/* Radius line (subtle) */}
              <line x1={cx} y1={cy} x2={px} y2={py}
                stroke="rgba(99,102,241,0.2)" strokeWidth={1} strokeDasharray="3,3" />

              {/* Point on circle */}
              <circle cx={px} cy={py} r={4} fill="#6366f1" stroke="#fff" strokeWidth={1.5} />

              {/* Degree label */}
              <text
                x={labelX}
                y={labelY + (angle.deg > 180 ? 14 : -4)}
                textAnchor="middle"
                fontSize={10}
                fontWeight="600"
                style={{ fill: degHidden ? '#ef4444' : 'var(--text-primary)' }}
              >
                {degHidden ? (answers[degKey] || '?') + String.fromCharCode(176) : angle.deg + String.fromCharCode(176)}
              </text>

              {/* Radian label */}
              {showRadians && (
                <text
                  x={labelX}
                  y={labelY + (angle.deg > 180 ? 2 : 8)}
                  textAnchor="middle"
                  fontSize={9}
                  style={{ fill: radHidden ? '#f59e0b' : 'var(--text-muted)' }}
                >
                  {radHidden ? (answers[radKey] || '?') : angle.rad}
                </text>
              )}

              {/* Coordinate label */}
              {showCoordinates && (
                <text
                  x={labelX + (angle.deg > 90 && angle.deg < 270 ? -10 : 10)}
                  y={labelY + (angle.deg > 180 ? -8 : 20)}
                  textAnchor="middle"
                  fontSize={8}
                  style={{ fill: coordHidden ? '#ec4899' : 'var(--text-secondary)' }}
                >
                  {coordHidden
                    ? '(' + (answers[cosKey] || '?') + ', ' + (answers[sinKey] || '?') + ')'
                    : '(' + angle.cos + ', ' + angle.sin + ')'}
                </text>
              )}
            </g>
          );
        })}

        {/* Origin label */}
        <text x={cx + 8} y={cy + 14} fontSize={10} style={{ fill: 'var(--text-muted)' }}>(0, 0)</text>

        {/* Axis tick marks: 1 and -1 */}
        <text x={cx + r + 5} y={cy + 14} fontSize={10} style={{ fill: 'var(--text-muted)' }}>1</text>
        <text x={cx - r - 12} y={cy + 14} fontSize={10} style={{ fill: 'var(--text-muted)' }}>-1</text>
        <text x={cx + 8} y={cy - r - 5} fontSize={10} style={{ fill: 'var(--text-muted)' }}>1</text>
        <text x={cx + 8} y={cy + r + 14} fontSize={10} style={{ fill: 'var(--text-muted)' }}>-1</text>
      </svg>

      {/* Input fields for hidden values */}
      {(hiddenAngles.length > 0 || hiddenValues.length > 0) && !readOnly && (
        <div style={styles.inputsGrid}>
          {KEY_ANGLES.filter(a => a.deg < 360).map((angle) => {
            const fields = [];
            if (isHidden(angle.deg, 'degrees'))
              fields.push({ key: `deg_${angle.deg}`, label: `? ${String.fromCharCode(176)} degrees`, correct: String(angle.deg) });
            if (isHidden(angle.deg, 'radians'))
              fields.push({ key: `rad_${angle.deg}`, label: `? radians at ${angle.deg}${String.fromCharCode(176)}`, correct: angle.rad });
            if (isHidden(angle.deg, 'coordinates')) {
              fields.push({ key: `cos_${angle.deg}`, label: `cos(${angle.deg}${String.fromCharCode(176)})`, correct: angle.cos });
              fields.push({ key: `sin_${angle.deg}`, label: `sin(${angle.deg}${String.fromCharCode(176)})`, correct: angle.sin });
            }
            return fields.map(f => (
              <div key={f.key} style={styles.inputRow}>
                <label style={styles.inputLabel}>{f.label}:</label>
                <input
                  type="text"
                  value={answers[f.key] || ''}
                  onChange={(e) => handleChange(f.key, e.target.value)}
                  style={styles.input}
                  placeholder="?"
                />
                {correctAnswers && (
                  <span style={styles.correctHint}>
                    {normalizeAnswer(answers[f.key]) === normalizeAnswer(f.correct) ? String.fromCharCode(10003) : f.correct}
                  </span>
                )}
              </div>
            ));
          })}
        </div>
      )}
    </div>
  );
}

function normalizeAnswer(str) {
  return (str || '').replace(/\s+/g, '').toLowerCase();
}

const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '12px',
  },
  inputsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
    gap: '8px',
    width: '100%',
    maxWidth: '500px',
  },
  inputRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
  },
  inputLabel: {
    fontSize: '0.8rem',
    color: 'var(--text-secondary)',
    minWidth: '100px',
  },
  input: {
    width: '80px',
    padding: '6px 8px',
    border: '1px solid var(--glass-border)',
    borderRadius: '4px',
    fontSize: '0.9rem',
    fontFamily: 'monospace',
    textAlign: 'center',
    color: 'var(--text-primary)',
    background: 'var(--input-bg)',
  },
  correctHint: {
    fontSize: '0.8rem',
    color: '#22c55e',
    fontWeight: '500',
  },
};
