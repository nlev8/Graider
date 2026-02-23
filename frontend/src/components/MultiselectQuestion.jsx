/**
 * MultiselectQuestion - "Select all that apply" checkbox list
 * Answer format: array of selected option indices, e.g. [1, 2, 3]
 */
export default function MultiselectQuestion({ question, answer, onAnswer, readOnly, showAnswer }) {
  const selected = Array.isArray(answer) ? answer : [];
  const correctIndices = question.correct || [];

  const toggle = (idx) => {
    if (readOnly) return;
    const next = selected.includes(idx)
      ? selected.filter(i => i !== idx)
      : [...selected, idx];
    onAnswer(next);
  };

  return (
    <div style={styles.container}>
      {question.options?.map((opt, idx) => {
        const isSelected = selected.includes(idx);
        const isCorrect = correctIndices.includes(idx);
        let bg = 'var(--glass-bg)';
        let border = '1px solid var(--glass-border)';
        if (showAnswer) {
          if (isCorrect && isSelected) { bg = 'rgba(34,197,94,0.15)'; border = '1px solid #22c55e'; }
          else if (isCorrect && !isSelected) { bg = 'rgba(34,197,94,0.08)'; border = '1px dashed #22c55e'; }
          else if (!isCorrect && isSelected) { bg = 'rgba(239,68,68,0.15)'; border = '1px solid #ef4444'; }
        }
        return (
          <label key={idx} style={{ ...styles.option, background: bg, border }}>
            <input
              type="checkbox"
              checked={isSelected}
              onChange={() => toggle(idx)}
              disabled={readOnly}
              style={styles.checkbox}
            />
            <span style={styles.text}>{opt}</span>
            {showAnswer && isCorrect && <span style={styles.badge}>correct</span>}
          </label>
        );
      })}
      {showAnswer && (
        <div style={styles.answerNote}>
          Correct selections: {correctIndices.map(i => question.options?.[i]).filter(Boolean).join(', ')}
        </div>
      )}
    </div>
  );
}

const styles = {
  container: { display: 'flex', flexDirection: 'column', gap: '10px' },
  option: {
    display: 'flex', alignItems: 'center', gap: '10px',
    padding: '12px', borderRadius: '8px', cursor: 'pointer', transition: 'all 0.2s',
  },
  checkbox: { width: '18px', height: '18px', accentColor: '#6366f1' },
  text: { fontSize: '1rem', color: 'var(--text-primary)' },
  badge: {
    marginLeft: 'auto', fontSize: '0.7rem', fontWeight: 600,
    color: '#22c55e', background: 'rgba(34,197,94,0.1)',
    padding: '2px 8px', borderRadius: '4px',
  },
  answerNote: {
    fontSize: '0.85rem', color: '#22c55e', fontWeight: 500,
    padding: '8px 12px', background: 'rgba(34,197,94,0.08)', borderRadius: '8px',
  },
};
