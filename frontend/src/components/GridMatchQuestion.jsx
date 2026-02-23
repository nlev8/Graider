/**
 * GridMatchQuestion - Matrix/table matching with radio buttons
 * Answer format: 2D array with one-hot per row, e.g. [[0,1,0],[0,0,1],[1,0,0]]
 */
export default function GridMatchQuestion({ question, answer, onAnswer, readOnly, showAnswer }) {
  const rows = question.row_labels || [];
  const cols = question.column_labels || [];
  const correctMatrix = question.correct || [];
  const studentMatrix = Array.isArray(answer) ? answer : rows.map(() => Array(cols.length).fill(0));

  const handleSelect = (rowIdx, colIdx) => {
    if (readOnly) return;
    const next = studentMatrix.map((row, ri) => {
      if (ri !== rowIdx) return [...row];
      return cols.map((_, ci) => ci === colIdx ? 1 : 0);
    });
    onAnswer(next);
  };

  const isRowCorrect = (rowIdx) => {
    const s = studentMatrix[rowIdx] || [];
    const c = correctMatrix[rowIdx] || [];
    return s.length === c.length && s.every((v, i) => v === c[i]);
  };

  return (
    <div style={styles.wrapper}>
      <div style={styles.tableScroll}>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.cornerCell}></th>
              {cols.map((col, ci) => (
                <th key={ci} style={styles.colHeader}>{col}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, ri) => {
              const rowOk = showAnswer && isRowCorrect(ri);
              const rowWrong = showAnswer && !isRowCorrect(ri) && studentMatrix[ri]?.some(v => v === 1);
              let rowBg = 'transparent';
              if (rowOk) rowBg = 'rgba(34,197,94,0.1)';
              else if (rowWrong) rowBg = 'rgba(239,68,68,0.08)';
              return (
                <tr key={ri} style={{ background: rowBg }}>
                  <td style={styles.rowLabel}>{row}</td>
                  {cols.map((_, ci) => {
                    const isSelected = (studentMatrix[ri] || [])[ci] === 1;
                    const isCorrectCell = showAnswer && (correctMatrix[ri] || [])[ci] === 1;
                    let cellStyle = { ...styles.cell };
                    if (showAnswer && isCorrectCell && isSelected) cellStyle.background = 'rgba(34,197,94,0.2)';
                    else if (showAnswer && isCorrectCell && !isSelected) cellStyle.background = 'rgba(34,197,94,0.08)';
                    else if (showAnswer && !isCorrectCell && isSelected) cellStyle.background = 'rgba(239,68,68,0.15)';
                    return (
                      <td key={ci} style={cellStyle}>
                        <input
                          type="radio"
                          name={`grid-row-${ri}`}
                          checked={isSelected}
                          onChange={() => handleSelect(ri, ci)}
                          disabled={readOnly}
                          style={styles.radio}
                        />
                        {showAnswer && isCorrectCell && !isSelected && (
                          <span style={styles.correctDot}></span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {showAnswer && (
        <div style={styles.summary}>
          {rows.filter((_, ri) => isRowCorrect(ri)).length}/{rows.length} rows correct
        </div>
      )}
    </div>
  );
}

const styles = {
  wrapper: { display: 'flex', flexDirection: 'column', gap: '10px' },
  tableScroll: { overflowX: 'auto', WebkitOverflowScrolling: 'touch' },
  table: {
    width: '100%', borderCollapse: 'collapse',
    border: '1px solid var(--glass-border)', borderRadius: '8px',
  },
  cornerCell: {
    padding: '10px', background: 'var(--glass-bg)',
    borderBottom: '2px solid var(--glass-border)',
    borderRight: '1px solid var(--glass-border)',
  },
  colHeader: {
    padding: '10px 14px', fontSize: '0.82rem', fontWeight: 600,
    color: 'var(--text-primary)', textAlign: 'center',
    background: 'var(--glass-bg)', borderBottom: '2px solid var(--glass-border)',
    borderRight: '1px solid var(--glass-border)', minWidth: '120px',
  },
  rowLabel: {
    padding: '10px 14px', fontSize: '0.85rem', fontWeight: 500,
    color: 'var(--text-primary)', borderRight: '1px solid var(--glass-border)',
    borderBottom: '1px solid var(--glass-border)', whiteSpace: 'nowrap',
  },
  cell: {
    padding: '10px', textAlign: 'center', position: 'relative',
    borderRight: '1px solid var(--glass-border)',
    borderBottom: '1px solid var(--glass-border)',
  },
  radio: { width: '20px', height: '20px', accentColor: '#6366f1', cursor: 'pointer' },
  correctDot: {
    position: 'absolute', top: '4px', right: '4px',
    width: '8px', height: '8px', borderRadius: '50%', background: '#22c55e',
  },
  summary: {
    fontSize: '0.85rem', color: 'var(--text-secondary)', fontWeight: 500,
    padding: '8px 12px', background: 'var(--glass-bg)', borderRadius: '8px',
  },
};
