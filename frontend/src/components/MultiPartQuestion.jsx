/**
 * MultiPartQuestion - Compound Part A / Part B questions
 * Answer format: { "0": "D", "1": "B" } keyed by part index
 */
export default function MultiPartQuestion({ question, answer, onAnswer, readOnly, showAnswer, sectionIndex, questionIndex }) {
  const answers = (answer && typeof answer === 'object') ? answer : {};
  const parts = question.parts || [];

  const handlePartAnswer = (partIdx, value) => {
    onAnswer({ ...answers, [String(partIdx)]: value });
  };

  return (
    <div style={styles.container}>
      {parts.map((part, idx) => {
        const partAnswer = answers[String(idx)] || '';
        const partType = part.question_type || 'multiple_choice';
        const isCorrect = showAnswer && String(partAnswer).trim().toLowerCase() === String(part.answer || '').trim().toLowerCase();
        const isWrong = showAnswer && partAnswer && !isCorrect;

        return (
          <div key={idx} style={styles.partBlock}>
            <div style={styles.partLabel}>{part.label || `Part ${String.fromCharCode(65 + idx)}`}</div>
            <div style={styles.partQuestion}>{part.question}</div>

            {partType === 'multiple_choice' || partType === 'true_false' ? (
              <div style={styles.options}>
                {(part.options || (partType === 'true_false' ? ['True', 'False'] : [])).map((opt, oi) => {
                  let bg = 'var(--glass-bg)';
                  let border = '1px solid var(--glass-border)';
                  if (showAnswer) {
                    const optLetter = opt.charAt(0);
                    const isThisCorrect = String(part.answer).trim().toLowerCase() === opt.trim().toLowerCase()
                      || String(part.answer).trim().toLowerCase() === optLetter.toLowerCase();
                    const isThisSelected = partAnswer === opt || partAnswer === optLetter;
                    if (isThisCorrect) { bg = 'rgba(34,197,94,0.15)'; border = '1px solid #22c55e'; }
                    else if (isThisSelected) { bg = 'rgba(239,68,68,0.15)'; border = '1px solid #ef4444'; }
                  }
                  return (
                    <label key={oi} style={{ ...styles.option, background: bg, border }}>
                      <input
                        type="radio"
                        name={`part-${sectionIndex}-${questionIndex}-${idx}`}
                        value={opt}
                        checked={partAnswer === opt}
                        onChange={() => handlePartAnswer(idx, opt)}
                        disabled={readOnly}
                        style={styles.radio}
                      />
                      <span style={styles.optText}>{opt}</span>
                    </label>
                  );
                })}
              </div>
            ) : (
              <textarea
                style={styles.textInput}
                value={partAnswer}
                onChange={(e) => handlePartAnswer(idx, e.target.value)}
                disabled={readOnly}
                placeholder="Type your answer..."
                rows={2}
              />
            )}

            {showAnswer && part.answer && (
              <div style={{ ...styles.answerLine, color: isCorrect ? '#22c55e' : '#ef4444' }}>
                {isCorrect ? 'Correct' : `Incorrect. Answer: ${part.answer}`}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

const styles = {
  container: { display: 'flex', flexDirection: 'column', gap: '20px' },
  partBlock: {
    padding: '16px', background: 'var(--glass-bg)', borderRadius: '10px',
    border: '1px solid var(--glass-border)',
  },
  partLabel: {
    fontSize: '0.8rem', fontWeight: 700, textTransform: 'uppercase',
    letterSpacing: '0.05em', color: '#6366f1', marginBottom: '6px',
  },
  partQuestion: { fontSize: '0.95rem', color: 'var(--text-primary)', marginBottom: '12px' },
  options: { display: 'flex', flexDirection: 'column', gap: '8px' },
  option: {
    display: 'flex', alignItems: 'center', gap: '10px',
    padding: '10px 12px', borderRadius: '8px', cursor: 'pointer', transition: 'all 0.2s',
  },
  radio: { width: '18px', height: '18px', accentColor: '#6366f1' },
  optText: { fontSize: '0.95rem', color: 'var(--text-primary)' },
  textInput: {
    width: '100%', padding: '10px 12px', borderRadius: '8px',
    border: '1px solid var(--glass-border)', background: 'var(--glass-bg)',
    color: 'var(--text-primary)', fontSize: '0.95rem', resize: 'vertical',
  },
  answerLine: { fontSize: '0.8rem', fontWeight: 600, marginTop: '8px' },
};
