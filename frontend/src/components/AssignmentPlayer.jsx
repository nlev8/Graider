import { useState, useEffect } from 'react';
import QuestionEditOverlay from './QuestionEditOverlay';
import QuestionRenderer from './assignment-player/QuestionRenderer';
import useVirtualKeyboard from './assignment-player/useVirtualKeyboard';
import styles from './assignment-player/styles';

/**
 * AssignmentPlayer - Interactive assignment component for students
 * Supports: number lines, coordinate planes, geometry, box plots, math equations, data tables
 */
export default function AssignmentPlayer({
  assignment,
  onSubmit,
  onClose,
  studentName = '',
  readOnly = false,
  showAnswers = false,
  results: externalResults = null,
  // Question edit mode props
  editMode = false,
  selectedQuestions,
  editingQuestion,
  regeneratingQuestions,
  onToggleSelect,
  onStartEdit,
  onSaveEdit,
  onCancelEdit,
  onRegenerateOne,
}) {
  const [answers, setAnswers] = useState({});
  const [currentSection, setCurrentSection] = useState(0);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [internalResults, setInternalResults] = useState(null);

  // Use external results if provided, otherwise use internal
  const results = externalResults || internalResults;

  // Initialize answers from assignment
  useEffect(() => {
    if (assignment?.sections) {
      const initialAnswers = {};
      assignment.sections.forEach((section, sIdx) => {
        section.questions?.forEach((q, qIdx) => {
          const key = `${sIdx}-${qIdx}`;
          initialAnswers[key] = {
            value: null,
            type: q.question_type || section.type || 'short_answer'
          };
        });
      });
      setAnswers(initialAnswers);
    }
  }, [assignment]);

  const updateAnswer = (sectionIdx, questionIdx, value) => {
    const key = `${sectionIdx}-${questionIdx}`;
    setAnswers(prev => ({
      ...prev,
      [key]: { ...prev[key], value }
    }));
  };

  const {
    focusedInput,
    setFocusedInput,
    handleInputFocus,
    handleKeyboardInsert,
    handleKeyboardBackspace,
  } = useVirtualKeyboard(answers, updateAnswer);

  const handleSubmit = async () => {
    if (readOnly) return;
    setIsSubmitting(true);
    try {
      const result = await onSubmit?.(answers);
      setInternalResults(result);
    } catch (e) {
      console.error('Submit error:', e);
    } finally {
      setIsSubmitting(false);
    }
  };

  const getProgress = () => {
    const total = Object.keys(answers).length;
    const completed = Object.values(answers).filter(a => a.value !== null && a.value !== '').length;
    return { total, completed, percent: total > 0 ? Math.round((completed / total) * 100) : 0 };
  };

  const progress = getProgress();

  if (!assignment) {
    return (
      <div style={styles.container}>
        <div style={styles.emptyState}>
          <p>No assignment loaded</p>
        </div>
      </div>
    );
  }

  const sections = assignment.sections || [];

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <div>
          <h1 style={styles.title}>{assignment.title}</h1>
          {studentName && <p style={styles.studentName}>Student: {studentName}</p>}
        </div>
        <div style={styles.headerRight}>
          <div style={styles.progressContainer}>
            <div style={styles.progressBar}>
              <div style={{ ...styles.progressFill, width: `${progress.percent}%` }} />
            </div>
            <span style={styles.progressText}>{progress.completed}/{progress.total} answered</span>
          </div>
          {onClose && (
            <button onClick={onClose} style={styles.closeButton}>×</button>
          )}
        </div>
      </div>

      {/* Instructions */}
      {assignment.instructions && (
        <div style={styles.instructions}>
          <strong>Instructions:</strong> {assignment.instructions}
        </div>
      )}

      {/* Section Tabs */}
      <div style={styles.tabs}>
        {sections.map((section, idx) => (
          <button
            key={idx}
            onClick={() => setCurrentSection(idx)}
            style={{
              ...styles.tab,
              ...(currentSection === idx ? styles.tabActive : {})
            }}
          >
            {section.name}
            <span style={styles.tabPoints}>{section.points} pts</span>
          </button>
        ))}
      </div>

      {/* Current Section */}
      {sections[currentSection] && (
        <div style={styles.section}>
          <h2 style={styles.sectionTitle}>{sections[currentSection].name}</h2>

          {sections[currentSection].questions?.map((question, qIdx) => {
            const renderer = (
              <QuestionRenderer
                key={editMode ? undefined : qIdx}
                question={question}
                questionIndex={qIdx}
                sectionIndex={currentSection}
                answer={answers[`${currentSection}-${qIdx}`]?.value}
                onAnswer={(value) => updateAnswer(currentSection, qIdx, value)}
                readOnly={readOnly}
                showAnswer={showAnswers}
                result={results?.questions?.[`${currentSection}-${qIdx}`]}
                onInputFocus={handleInputFocus}
                focusedInputKey={focusedInput?.key}
                onKeyboardInsert={handleKeyboardInsert}
                onKeyboardBackspace={handleKeyboardBackspace}
                onKeyboardClose={() => setFocusedInput(null)}
                keyboardMode={focusedInput?.mode}
              />
            );
            if (editMode) {
              return (
                <QuestionEditOverlay
                  key={qIdx}
                  question={question}
                  sectionIndex={currentSection}
                  questionIndex={qIdx}
                  isSelected={selectedQuestions?.has(currentSection + "-" + qIdx)}
                  isEditing={editingQuestion === currentSection + "-" + qIdx}
                  isRegenerating={regeneratingQuestions?.has(currentSection + "-" + qIdx)}
                  onToggleSelect={onToggleSelect}
                  onStartEdit={onStartEdit}
                  onSaveEdit={onSaveEdit}
                  onCancelEdit={onCancelEdit}
                  onRegenerateOne={onRegenerateOne}
                >
                  {renderer}
                </QuestionEditOverlay>
              );
            }
            return renderer;
          })}
        </div>
      )}

      {/* Navigation & Submit */}
      <div style={styles.footer}>
        <div style={styles.navButtons}>
          <button
            onClick={() => setCurrentSection(prev => Math.max(0, prev - 1))}
            disabled={currentSection === 0}
            style={{ ...styles.navButton, opacity: currentSection === 0 ? 0.5 : 1 }}
          >
            ← Previous
          </button>
          <button
            onClick={() => setCurrentSection(prev => Math.min(sections.length - 1, prev + 1))}
            disabled={currentSection === sections.length - 1}
            style={{ ...styles.navButton, opacity: currentSection === sections.length - 1 ? 0.5 : 1 }}
          >
            Next →
          </button>
        </div>

        {!readOnly && !results && (
          <button
            onClick={handleSubmit}
            disabled={isSubmitting || progress.completed === 0}
            style={{
              ...styles.submitButton,
              opacity: isSubmitting || progress.completed === 0 ? 0.6 : 1
            }}
          >
            {isSubmitting ? 'Submitting...' : 'Submit Assignment'}
          </button>
        )}

        {results && (
          <div style={styles.resultsPreview}>
            <span style={styles.scoreLabel}>Score:</span>
            <span style={styles.score}>{results.score}/{results.total} ({results.percent}%)</span>
          </div>
        )}
      </div>

      {/* Keyboard is now rendered inline below each focused question */}
    </div>
  );
}
