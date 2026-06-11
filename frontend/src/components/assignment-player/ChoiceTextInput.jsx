import MathInput from '../MathInput';
import DataTable from '../DataTable';
import MultiselectQuestion from '../MultiselectQuestion';
import MultiPartQuestion from '../MultiPartQuestion';
import GridMatchQuestion from '../GridMatchQuestion';
import InlineDropdownQuestion from '../InlineDropdownQuestion';
import BarChartDisplay from './BarChartDisplay';
import styles from './styles';

/**
 * ChoiceTextInput - renders choice/text-based question inputs (multiple
 * choice, true/false, math equation work areas, data tables, bar-chart
 * responses, coordinates, delegated composite types, and the short-answer
 * default). Case bodies relocated verbatim from the renderInput switch in
 * AssignmentPlayer.jsx's QuestionRenderer (CQ wave-4 split); every type not
 * in MATH_VISUAL_TYPES lands here, with short_answer as the default case.
 */
export default function ChoiceTextInput({
  question,
  qType,
  answer,
  onAnswer,
  readOnly,
  showAnswer,
  sectionIndex,
  questionIndex,
  inputKey,
  onInputFocus,
}) {
  switch (qType) {
    case 'math_equation':
      return (
        <div style={styles.mathContainer}>
          <div style={styles.workArea}>
            <label style={styles.workLabel}>Show your work:</label>
            <textarea
              style={styles.workTextarea}
              value={answer?.work || ''}
              onChange={(e) => onAnswer({ ...answer, work: e.target.value, final: answer?.final || '' })}
              onFocus={(e) => onInputFocus?.(e.target, inputKey + '-work', 'unicode')}
              placeholder="Show your steps here..."
              disabled={readOnly}
            />
          </div>
          <div style={styles.finalAnswer}>
            <label style={styles.finalLabel}>Final Answer:</label>
            <MathInput
              value={answer?.final || ''}
              onChange={(val) => onAnswer({ ...answer, final: val, work: answer?.work || '' })}
              disabled={readOnly}
              placeholder="Enter your answer"
              onInputFocus={(ref) => onInputFocus?.(ref, inputKey + '-math', 'latex')}
            />
          </div>
        </div>
      );

    case 'data_table':
      return (
        <DataTable
          headers={question.headers || question.column_headers || ['Column 1', 'Column 2', 'Column 3']}
          rowLabels={question.row_labels}
          data={answer?.data || answer || question.initial_data || []}
          onChange={onAnswer}
          editable={!readOnly}
          lockStructure={true}
        />
      );

    case 'multiselect':
      return (
        <MultiselectQuestion
          question={question} answer={answer} onAnswer={onAnswer}
          readOnly={readOnly} showAnswer={showAnswer}
        />
      );

    case 'multi_part':
      return (
        <MultiPartQuestion
          question={question} answer={answer} onAnswer={onAnswer}
          readOnly={readOnly} showAnswer={showAnswer}
          sectionIndex={sectionIndex} questionIndex={questionIndex}
        />
      );

    case 'grid_match':
      return (
        <GridMatchQuestion
          question={question} answer={answer} onAnswer={onAnswer}
          readOnly={readOnly} showAnswer={showAnswer}
        />
      );

    case 'inline_dropdown':
      return (
        <InlineDropdownQuestion
          question={question} answer={answer} onAnswer={onAnswer}
          readOnly={readOnly} showAnswer={showAnswer}
        />
      );

    case 'multiple_choice':
      return (
        <div style={styles.mcContainer}>
          {question.options?.map((opt, idx) => (
            <label key={idx} style={styles.mcOption}>
              <input
                type="radio"
                name={`q-${sectionIndex}-${questionIndex}`}
                value={opt}
                checked={answer === opt}
                onChange={() => onAnswer(opt)}
                disabled={readOnly}
                style={styles.mcRadio}
              />
              <span style={styles.mcText}>{opt}</span>
            </label>
          ))}
        </div>
      );

    case 'true_false':
      return (
        <div style={styles.mcContainer}>
          {['True', 'False'].map((opt) => (
            <label key={opt} style={styles.mcOption}>
              <input
                type="radio"
                name={`q-${sectionIndex}-${questionIndex}`}
                value={opt}
                checked={answer === opt}
                onChange={() => onAnswer(opt)}
                disabled={readOnly}
                style={styles.mcRadio}
              />
              <span style={styles.mcText}>{opt}</span>
            </label>
          ))}
        </div>
      );

    case 'bar_chart':
      return (
        <div style={styles.barChartContainer}>
          <BarChartDisplay
            data={question.chart_data}
            title={question.chart_data?.title || 'Data'}
          />
          <textarea
            style={styles.shortAnswer}
            value={answer || ''}
            onChange={(e) => onAnswer(e.target.value)}
            onFocus={(e) => onInputFocus?.(e.target, inputKey, 'unicode')}
            placeholder="Type your answer here..."
            disabled={readOnly}
            rows={3}
          />
        </div>
      );

    case 'polygon':
    case 'pie_chart':
      return (
        <div>
          {question.image_url && (
            <img src={question.image_url} alt={qType} style={{ maxWidth: '100%', borderRadius: '8px', marginBottom: '8px' }} />
          )}
          <textarea
            style={styles.shortAnswer}
            value={answer || ''}
            onChange={(e) => onAnswer(e.target.value)}
            onFocus={(e) => onInputFocus?.(e.target, inputKey, 'unicode')}
            placeholder="Type your answer here..."
            disabled={readOnly}
            rows={3}
          />
        </div>
      );

    case 'coordinates':
      return (
        <div style={styles.coordContainer}>
          <div style={styles.coordInput}>
            <label>Latitude:</label>
            <input
              type="number"
              step="0.0001"
              value={answer?.lat || ''}
              onChange={(e) => onAnswer({ ...answer, lat: parseFloat(e.target.value) || 0 })}
              disabled={readOnly}
              style={styles.coordField}
            />
            <span>°</span>
          </div>
          <div style={styles.coordInput}>
            <label>Longitude:</label>
            <input
              type="number"
              step="0.0001"
              value={answer?.lng || ''}
              onChange={(e) => onAnswer({ ...answer, lng: parseFloat(e.target.value) || 0 })}
              disabled={readOnly}
              style={styles.coordField}
            />
            <span>°</span>
          </div>
        </div>
      );

    case 'short_answer':
    default:
      return (
        <textarea
          style={styles.shortAnswer}
          value={answer || ''}
          onChange={(e) => onAnswer(e.target.value)}
          onFocus={(e) => onInputFocus?.(e.target, inputKey, 'unicode')}
          placeholder="Type your answer here..."
          disabled={readOnly}
          rows={3}
        />
      );
  }
}
