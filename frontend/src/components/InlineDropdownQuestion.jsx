/**
 * InlineDropdownQuestion - Cloze with inline <select> elements
 * Question text uses {0}, {1} placeholders replaced with dropdowns
 * Answer format: array of selected option indices, e.g. [1, 1]
 */
export default function InlineDropdownQuestion({ question, answer, onAnswer, readOnly, showAnswer }) {
  const dropdowns = question.dropdowns || [];
  const selections = Array.isArray(answer) ? answer : dropdowns.map(() => -1);

  const handleChange = (ddIdx, value) => {
    const next = [...selections];
    next[ddIdx] = parseInt(value, 10);
    onAnswer(next);
  };

  // Split question text on {N} placeholders
  const text = question.question || '';
  const parts = text.split(/(\{\d+\})/g);

  return (
    <div style={styles.container}>
      <div style={styles.textWrap}>
        {parts.map((part, pi) => {
          const match = part.match(/^\{(\d+)\}$/);
          if (!match) return <span key={pi}>{part}</span>;

          const ddIdx = parseInt(match[1], 10);
          const dd = dropdowns[ddIdx];
          if (!dd) return <span key={pi} style={{ color: '#ef4444' }}>[missing dropdown]</span>;

          const selected = selections[ddIdx] ?? -1;
          const isCorrect = showAnswer && selected === dd.correct;
          const isWrong = showAnswer && selected !== -1 && selected !== dd.correct;

          let borderColor = 'var(--glass-border)';
          if (isCorrect) borderColor = '#22c55e';
          else if (isWrong) borderColor = '#ef4444';

          return (
            <select
              key={pi}
              value={selected}
              onChange={(e) => handleChange(ddIdx, e.target.value)}
              disabled={readOnly}
              style={{
                ...styles.select,
                borderColor,
                background: isCorrect ? 'rgba(34,197,94,0.1)' : isWrong ? 'rgba(239,68,68,0.1)' : 'var(--glass-bg)',
              }}
            >
              <option value={-1}>— select —</option>
              {dd.options.map((opt, oi) => (
                <option key={oi} value={oi}>{opt}</option>
              ))}
            </select>
          );
        })}
      </div>
      {showAnswer && (
        <div style={styles.answerRow}>
          {dropdowns.map((dd, i) => (
            <span key={i} style={styles.answerChip}>
              Blank {i + 1}: <strong>{dd.options[dd.correct]}</strong>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

const styles = {
  container: { display: 'flex', flexDirection: 'column', gap: '12px' },
  textWrap: {
    fontSize: '1rem', lineHeight: '2.2', color: 'var(--text-primary)',
    display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '4px',
  },
  select: {
    display: 'inline-block', padding: '6px 10px', borderRadius: '6px',
    border: '2px solid var(--glass-border)', fontSize: '0.9rem',
    color: 'var(--text-primary)', cursor: 'pointer', transition: 'all 0.2s',
    margin: '0 2px',
  },
  answerRow: {
    display: 'flex', flexWrap: 'wrap', gap: '8px',
    padding: '8px 12px', background: 'rgba(34,197,94,0.08)', borderRadius: '8px',
  },
  answerChip: {
    fontSize: '0.82rem', color: '#22c55e', fontWeight: 500,
  },
};
