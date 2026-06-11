import VirtualMathKeyboard from '../VirtualMathKeyboard';
import RenderQuestionText from './RenderQuestionText';
import MathVisualInput, { MATH_VISUAL_TYPES } from './MathVisualInput';
import ChoiceTextInput from './ChoiceTextInput';
import styles from './styles';

/**
 * QuestionRenderer - Renders the appropriate input component based on question type
 */
export default function QuestionRenderer({
  question,
  questionIndex,
  sectionIndex,
  answer,
  onAnswer,
  readOnly,
  showAnswer,
  result,
  onInputFocus,
  focusedInputKey,
  onKeyboardInsert,
  onKeyboardBackspace,
  onKeyboardClose,
  keyboardMode
}) {
  const qType = question.question_type || question.visual_type || 'short_answer';
  const qNum = question.number || questionIndex + 1;
  const inputKey = `${sectionIndex}-${questionIndex}`;

  // Show keyboard inline when any input in THIS question is focused
  // Exact match on "section-question" prefix (must match exactly or have '-' suffix for subfields)
  const isKeyboardVisible = !readOnly && focusedInputKey &&
    (focusedInputKey === inputKey || focusedInputKey.startsWith(inputKey + '-'));

  // Image upload handler — converts to base64 for submission
  const handleImageUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) { alert('Image must be under 5MB'); return; }
    const reader = new FileReader();
    reader.onload = () => {
      const currentVal = answer || {};
      const newAnswer = typeof currentVal === 'string'
        ? { text: currentVal, image: reader.result }
        : { ...currentVal, image: reader.result };
      onAnswer(newAnswer);
    };
    reader.readAsDataURL(file);
  };

  const removeImage = () => {
    if (typeof answer === 'object' && answer?.image) {
      const { image, ...rest } = answer;
      onAnswer(Object.keys(rest).length === 1 && rest.text !== undefined ? rest.text : rest);
    }
  };

  // Show image upload for text-based types (not math_equation — it has its own work area)
  const supportsImageUpload = ['short_answer', 'extended_response', 'essay'].includes(qType)
    || question.allow_image_upload;

  return (
    <div style={{
      ...styles.question,
      ...(result?.correct === true ? styles.questionCorrect : {}),
      ...(result?.correct === false ? styles.questionIncorrect : {})
    }}>
      <div style={styles.questionHeader}>
        <span style={styles.questionNumber}>Question {qNum}</span>
        {question.points && <span style={styles.questionPoints}>{question.points} pts</span>}
        {result && (
          <span style={result.correct ? styles.resultCorrect : styles.resultIncorrect}>
            {result.correct ? '✓' : '✗'} {result.points_earned}/{question.points}
          </span>
        )}
      </div>
      <RenderQuestionText text={question.question} style={styles.questionText} />

      {/* Quality warning badge */}
      {question.warning && (
        <div style={{
          padding: "6px 10px",
          background: question.warning_severity === "error" ? "rgba(239,68,68,0.15)" : question.warning_severity === "info" ? "rgba(59,130,246,0.15)" : "rgba(245,158,11,0.15)",
          border: question.warning_severity === "error" ? "1px solid rgba(239,68,68,0.3)" : question.warning_severity === "info" ? "1px solid rgba(59,130,246,0.3)" : "1px solid rgba(245,158,11,0.3)",
          borderRadius: "6px",
          fontSize: "0.8rem",
          color: question.warning_severity === "error" ? "#ef4444" : question.warning_severity === "info" ? "#3b82f6" : "#f59e0b",
          display: "flex",
          alignItems: "center",
          gap: "6px",
          marginBottom: "8px",
        }}>
          ⚠ {question.warning}
        </div>
      )}

      <div style={styles.inputContainer}>
        {MATH_VISUAL_TYPES.includes(qType) ? (
          <MathVisualInput
            question={question}
            qType={qType}
            answer={answer}
            onAnswer={onAnswer}
            readOnly={readOnly}
            showAnswer={showAnswer}
            inputKey={inputKey}
            onInputFocus={onInputFocus}
          />
        ) : (
          <ChoiceTextInput
            question={question}
            qType={qType}
            answer={answer}
            onAnswer={onAnswer}
            readOnly={readOnly}
            showAnswer={showAnswer}
            sectionIndex={sectionIndex}
            questionIndex={questionIndex}
            inputKey={inputKey}
            onInputFocus={onInputFocus}
          />
        )}
      </div>

      {/* Image upload option */}
      {supportsImageUpload && !readOnly && (
        <div style={styles.imageUploadArea}>
          {answer?.image ? (
            <div style={styles.imagePreviewWrapper}>
              <img src={answer.image} alt="Uploaded work" style={styles.imagePreview} />
              <button onClick={removeImage} style={styles.imageRemoveBtn} title="Remove image">×</button>
            </div>
          ) : (
            <label style={styles.imageUploadLabel}>
              <input
                type="file"
                accept="image/*"
                onChange={handleImageUpload}
                style={{ display: 'none' }}
              />
              <span style={styles.imageUploadIcon}>📷</span>
              <span style={styles.imageUploadText}>Upload photo of work (optional)</span>
            </label>
          )}
        </div>
      )}

      {/* Show correct answer — skip for types that render their own answer display */}
      {showAnswer && question.answer && ![
        'triangle', 'rectangle', 'regular_polygon', 'circle', 'trapezoid',
        'parallelogram', 'rectangular_prism', 'cylinder', 'geometry',
        'similarity', 'pythagorean', 'angles', 'trig',
        'box_plot', 'function_graph', 'dot_plot', 'stem_and_leaf',
        'unit_circle', 'transformations', 'fraction_model',
        'probability_tree', 'tape_diagram', 'venn_diagram', 'protractor', 'angle_protractor',
        'multiselect', 'multi_part', 'grid_match', 'inline_dropdown'
      ].includes(qType) && (
        <div style={styles.correctAnswer}>
          <strong>Correct Answer:</strong> {
            typeof question.answer === 'object'
              ? JSON.stringify(question.answer)
              : question.answer
          }
        </div>
      )}

      {result?.feedback && (
        <div style={styles.feedback}>{result.feedback}</div>
      )}

      {/* Inline virtual keyboard — appears below the focused question */}
      {isKeyboardVisible && (
        <VirtualMathKeyboard
          mode={keyboardMode}
          onInsert={onKeyboardInsert}
          onBackspace={onKeyboardBackspace}
          onClose={onKeyboardClose}
          inline={true}
        />
      )}
    </div>
  );
}
