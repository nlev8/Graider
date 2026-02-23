import { useState, useEffect } from 'react';

/**
 * InteractiveStemAndLeaf - Enter leaf values for each stem.
 * Students build stem-and-leaf plots from raw data. Grades 6-8 statistics.
 */
export default function InteractiveStemAndLeaf({
  data = [],
  stems = [],
  leaves = {},
  onChange,
  correctLeaves = null,
  readOnly = false,
  title = '',
  keyLabel = 'Key: 1|5 = 15'
}) {
  // Auto-derive stems from data if not provided
  const derivedStems = stems.length > 0
    ? stems
    : [...new Set(data.map(v => Math.floor(v / 10)))].sort((a, b) => a - b);

  // Auto-compute correct leaves from data if data is provided
  const computedCorrect = data.length > 0
    ? derivedStems.reduce((acc, stem) => {
        const leafVals = data
          .filter(v => Math.floor(v / 10) === stem)
          .map(v => v % 10)
          .sort((a, b) => a - b);
        acc[String(stem)] = leafVals.join(' ');
        return acc;
      }, {})
    : correctLeaves;

  const handleLeafChange = (stem, value) => {
    if (readOnly) return;
    const next = { ...leaves, [String(stem)]: value };
    onChange?.(next);
  };

  return (
    <div style={styles.container}>
      {title && <div style={styles.title}>{title}</div>}

      <div style={styles.tableWrap}>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>Stem</th>
              <th style={{ ...styles.th, textAlign: 'left' }}>Leaf</th>
            </tr>
          </thead>
          <tbody>
            {derivedStems.map((stem) => {
              const userVal = leaves[String(stem)] || '';
              const correctVal = computedCorrect ? computedCorrect[String(stem)] : null;
              const isCorrect = correctVal !== null
                ? normalizeLeaves(userVal) === normalizeLeaves(correctVal)
                : null;

              return (
                <tr key={stem}>
                  <td style={styles.stemCell}>{stem}</td>
                  <td style={styles.leafCell}>
                    <input
                      type="text"
                      value={userVal}
                      onChange={(e) => handleLeafChange(stem, e.target.value)}
                      disabled={readOnly}
                      placeholder={readOnly ? '' : 'e.g. 2 3 5 8'}
                      style={{
                        ...styles.leafInput,
                        borderColor: isCorrect === true ? '#22c55e'
                          : isCorrect === false ? '#ef4444'
                          : 'var(--glass-border)',
                        background: isCorrect === true ? 'rgba(16, 185, 129, 0.08)'
                          : isCorrect === false ? 'rgba(239, 68, 68, 0.08)'
                          : 'var(--input-bg)',
                      }}
                    />
                    {isCorrect === false && correctVal && (
                      <span style={styles.correctHint}>{correctVal}</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div style={styles.key}>{keyLabel}</div>

      {data.length > 0 && !readOnly && (
        <div style={styles.rawData}>
          <strong>Data:</strong> {data.join(', ')}
        </div>
      )}

      {!readOnly && (
        <p style={styles.hint}>
          Enter the leaf digits for each stem, separated by spaces.
        </p>
      )}
    </div>
  );
}

function normalizeLeaves(str) {
  return (str || '').replace(/[^0-9]/g, ' ').trim().split(/\s+/).sort((a, b) => a - b).join(' ');
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
  tableWrap: {
    width: '100%',
    maxWidth: '400px',
    borderRadius: '8px',
    overflow: 'hidden',
    border: '1px solid var(--glass-border)',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
  },
  th: {
    padding: '8px 12px',
    background: 'rgba(99, 102, 241, 0.15)',
    color: 'var(--text-primary)',
    fontSize: '0.85rem',
    fontWeight: '600',
    textAlign: 'center',
    borderBottom: '1px solid var(--glass-border)',
  },
  stemCell: {
    padding: '6px 12px',
    textAlign: 'center',
    fontWeight: '700',
    fontSize: '1rem',
    color: '#6366f1',
    borderRight: '2px solid #6366f1',
    borderBottom: '1px solid var(--glass-border)',
    width: '60px',
    background: 'rgba(99, 102, 241, 0.05)',
  },
  leafCell: {
    padding: '4px 8px',
    borderBottom: '1px solid var(--glass-border)',
    position: 'relative',
  },
  leafInput: {
    width: '100%',
    padding: '6px 8px',
    border: '1px solid var(--glass-border)',
    borderRadius: '4px',
    fontSize: '1rem',
    fontFamily: 'monospace',
    letterSpacing: '2px',
    color: 'var(--text-primary)',
    background: 'var(--input-bg)',
  },
  correctHint: {
    display: 'block',
    fontSize: '0.8rem',
    color: '#22c55e',
    fontFamily: 'monospace',
    marginTop: '2px',
  },
  key: {
    fontSize: '0.85rem',
    color: 'var(--text-muted)',
    fontFamily: 'monospace',
    padding: '6px 12px',
    background: 'var(--input-bg)',
    borderRadius: '6px',
  },
  rawData: {
    fontSize: '0.85rem',
    color: 'var(--text-secondary)',
    background: 'var(--input-bg)',
    padding: '8px 12px',
    borderRadius: '6px',
    maxWidth: '400px',
    wordBreak: 'break-word',
  },
  hint: {
    fontSize: '0.85rem',
    color: 'var(--text-muted)',
    margin: 0,
  },
};
