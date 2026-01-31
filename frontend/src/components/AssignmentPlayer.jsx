import { useState, useEffect } from 'react';
import InteractiveNumberLine from './InteractiveNumberLine';
import InteractiveCoordinatePlane from './InteractiveCoordinatePlane';
import InteractiveGeometry from './InteractiveGeometry';
import InteractiveBoxPlot from './InteractiveBoxPlot';
import MathInput from './MathInput';
import DataTable from './DataTable';

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
  results: externalResults = null
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

          {sections[currentSection].questions?.map((question, qIdx) => (
            <QuestionRenderer
              key={qIdx}
              question={question}
              questionIndex={qIdx}
              sectionIndex={currentSection}
              answer={answers[`${currentSection}-${qIdx}`]?.value}
              onAnswer={(value) => updateAnswer(currentSection, qIdx, value)}
              readOnly={readOnly}
              showAnswer={showAnswers}
              result={results?.questions?.[`${currentSection}-${qIdx}`]}
            />
          ))}
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
    </div>
  );
}

/**
 * BarChartDisplay - Renders an SVG bar chart from data
 */
function BarChartDisplay({ data, title }) {
  if (!data || !data.labels || !data.values) {
    return <div style={{ color: '#ef4444', padding: '10px' }}>Missing chart data</div>;
  }

  const { labels, values, y_label } = data;
  const maxVal = Math.max(...values);
  const chartWidth = 400;
  const chartHeight = 200;
  const barWidth = Math.min(50, (chartWidth - 60) / labels.length - 10);
  const padding = { top: 30, right: 20, bottom: 40, left: 50 };

  return (
    <div style={{ marginBottom: '15px' }}>
      <svg width={chartWidth} height={chartHeight + padding.top + padding.bottom}>
        <rect x={0} y={0} width={chartWidth} height={chartHeight + padding.top + padding.bottom} fill="#fafafa" rx={8} />
        {title && (
          <text x={chartWidth / 2} y={20} textAnchor="middle" fontSize={14} fontWeight="600" fill="#374151">{title}</text>
        )}
        {y_label && (
          <text x={15} y={chartHeight / 2 + padding.top} textAnchor="middle" fontSize={11} fill="#6b7280" transform={`rotate(-90, 15, ${chartHeight / 2 + padding.top})`}>{y_label}</text>
        )}
        <line x1={padding.left} y1={padding.top} x2={padding.left} y2={chartHeight + padding.top} stroke="#d1d5db" strokeWidth={1} />
        <line x1={padding.left} y1={chartHeight + padding.top} x2={chartWidth - padding.right} y2={chartHeight + padding.top} stroke="#d1d5db" strokeWidth={1} />
        {[0, 0.25, 0.5, 0.75, 1].map((tick, i) => {
          const y = padding.top + chartHeight * (1 - tick);
          return (
            <g key={i}>
              <line x1={padding.left - 5} y1={y} x2={padding.left} y2={y} stroke="#9ca3af" />
              <text x={padding.left - 10} y={y + 4} textAnchor="end" fontSize={10} fill="#6b7280">{Math.round(maxVal * tick)}</text>
            </g>
          );
        })}
        {values.map((val, idx) => {
          const barHeight = (val / maxVal) * chartHeight;
          const x = padding.left + 20 + idx * ((chartWidth - padding.left - padding.right - 40) / labels.length);
          const y = padding.top + chartHeight - barHeight;
          const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];
          return (
            <g key={idx}>
              <rect x={x} y={y} width={barWidth} height={barHeight} fill={colors[idx % colors.length]} rx={3} />
              <text x={x + barWidth / 2} y={y - 5} textAnchor="middle" fontSize={10} fill="#374151" fontWeight="500">{val}</text>
              <text x={x + barWidth / 2} y={chartHeight + padding.top + 15} textAnchor="middle" fontSize={10} fill="#374151">{labels[idx]}</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

/**
 * QuestionRenderer - Renders the appropriate input component based on question type
 */
function QuestionRenderer({
  question,
  questionIndex,
  sectionIndex,
  answer,
  onAnswer,
  readOnly,
  showAnswer,
  result
}) {
  const qType = question.question_type || question.visual_type || 'short_answer';
  const qNum = question.number || questionIndex + 1;

  const renderInput = () => {
    switch (qType) {
      case 'number_line':
        return (
          <InteractiveNumberLine
            minVal={question.min_val ?? -10}
            maxVal={question.max_val ?? 10}
            points={answer || []}
            onChange={onAnswer}
            correctPoints={showAnswer ? question.points_to_plot : null}
            readOnly={readOnly}
          />
        );

      case 'coordinate_plane':
        return (
          <InteractiveCoordinatePlane
            xRange={question.x_range || [-6, 6]}
            yRange={question.y_range || [-6, 6]}
            points={answer || []}
            labels={question.point_labels || []}
            onChange={onAnswer}
            correctPoints={showAnswer ? question.points_to_plot : null}
            readOnly={readOnly}
          />
        );

      case 'geometry':
      case 'triangle':
      case 'rectangle':
        return (
          <InteractiveGeometry
            type={qType === 'geometry' ? 'triangle' : qType}
            base={question.base || 6}
            height={question.height || 4}
            answer={answer || ''}
            onChange={onAnswer}
            correctAnswer={showAnswer ? question.answer : null}
            readOnly={readOnly}
          />
        );

      case 'box_plot':
        return (
          <InteractiveBoxPlot
            data={question.data || [[50, 60, 70, 80, 90]]}
            labels={question.data_labels}
            answers={answer || {}}
            onChange={onAnswer}
            correctAnswers={showAnswer ? question.expected_values : null}
            readOnly={readOnly}
          />
        );

      case 'math_equation':
        return (
          <div style={styles.mathContainer}>
            <div style={styles.workArea}>
              <label style={styles.workLabel}>Show your work:</label>
              <textarea
                style={styles.workTextarea}
                value={answer?.work || ''}
                onChange={(e) => onAnswer({ ...answer, work: e.target.value, final: answer?.final || '' })}
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
              />
            </div>
          </div>
        );

      case 'data_table':
        return (
          <DataTable
            headers={question.headers || ['Column 1', 'Column 2', 'Column 3']}
            data={answer || question.initial_data || []}
            onChange={onAnswer}
            readOnly={readOnly}
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
            placeholder="Type your answer here..."
            disabled={readOnly}
            rows={3}
          />
        );
    }
  };

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
      <p style={styles.questionText}>{question.question}</p>

      <div style={styles.inputContainer}>
        {renderInput()}
      </div>

      {showAnswer && question.answer && (
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
    </div>
  );
}

const styles = {
  container: {
    maxWidth: '900px',
    margin: '0 auto',
    padding: '20px',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: '20px',
    paddingBottom: '15px',
    borderBottom: '2px solid #e5e7eb',
  },
  title: {
    fontSize: '1.8rem',
    fontWeight: '700',
    margin: '0 0 5px 0',
    color: '#1f2937',
  },
  studentName: {
    fontSize: '0.95rem',
    color: '#6b7280',
    margin: 0,
  },
  headerRight: {
    display: 'flex',
    alignItems: 'center',
    gap: '15px',
  },
  progressContainer: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'flex-end',
    gap: '4px',
  },
  progressBar: {
    width: '150px',
    height: '8px',
    background: '#e5e7eb',
    borderRadius: '4px',
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    background: 'linear-gradient(90deg, #6366f1, #8b5cf6)',
    transition: 'width 0.3s ease',
  },
  progressText: {
    fontSize: '0.8rem',
    color: '#6b7280',
  },
  closeButton: {
    width: '36px',
    height: '36px',
    border: 'none',
    background: '#f3f4f6',
    borderRadius: '8px',
    fontSize: '1.5rem',
    cursor: 'pointer',
    color: '#6b7280',
  },
  instructions: {
    padding: '15px',
    background: '#f0f9ff',
    borderRadius: '8px',
    marginBottom: '20px',
    color: '#0369a1',
    fontSize: '0.95rem',
  },
  tabs: {
    display: 'flex',
    gap: '8px',
    marginBottom: '20px',
    flexWrap: 'wrap',
  },
  tab: {
    padding: '10px 16px',
    border: '1px solid #e5e7eb',
    background: '#fff',
    borderRadius: '8px',
    cursor: 'pointer',
    fontSize: '0.9rem',
    fontWeight: '500',
    color: '#4b5563',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    transition: 'all 0.2s',
  },
  tabActive: {
    background: '#6366f1',
    color: '#fff',
    borderColor: '#6366f1',
  },
  tabPoints: {
    fontSize: '0.75rem',
    opacity: 0.8,
  },
  section: {
    background: '#fff',
    borderRadius: '12px',
    padding: '20px',
    boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
    marginBottom: '20px',
  },
  sectionTitle: {
    fontSize: '1.2rem',
    fontWeight: '600',
    marginBottom: '20px',
    color: '#1f2937',
  },
  question: {
    padding: '20px',
    background: '#f9fafb',
    borderRadius: '10px',
    marginBottom: '15px',
    border: '1px solid #e5e7eb',
  },
  questionCorrect: {
    background: '#f0fdf4',
    borderColor: '#86efac',
  },
  questionIncorrect: {
    background: '#fef2f2',
    borderColor: '#fca5a5',
  },
  questionHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    marginBottom: '10px',
  },
  questionNumber: {
    fontWeight: '600',
    color: '#6366f1',
    fontSize: '0.95rem',
  },
  questionPoints: {
    fontSize: '0.8rem',
    color: '#6b7280',
    background: '#e5e7eb',
    padding: '2px 8px',
    borderRadius: '10px',
  },
  resultCorrect: {
    color: '#16a34a',
    fontWeight: '600',
    marginLeft: 'auto',
  },
  resultIncorrect: {
    color: '#dc2626',
    fontWeight: '600',
    marginLeft: 'auto',
  },
  questionText: {
    fontSize: '1rem',
    color: '#374151',
    marginBottom: '15px',
    lineHeight: '1.5',
  },
  inputContainer: {
    marginTop: '10px',
  },
  shortAnswer: {
    width: '100%',
    padding: '12px',
    border: '1px solid #d1d5db',
    borderRadius: '8px',
    fontSize: '1rem',
    resize: 'vertical',
    fontFamily: 'inherit',
  },
  mathContainer: {
    display: 'flex',
    flexDirection: 'column',
    gap: '15px',
  },
  workArea: {
    display: 'flex',
    flexDirection: 'column',
    gap: '5px',
  },
  workLabel: {
    fontSize: '0.9rem',
    fontWeight: '500',
    color: '#4b5563',
  },
  workTextarea: {
    width: '100%',
    minHeight: '100px',
    padding: '12px',
    border: '1px solid #d1d5db',
    borderRadius: '8px',
    fontSize: '1rem',
    resize: 'vertical',
    fontFamily: 'inherit',
  },
  finalAnswer: {
    display: 'flex',
    flexDirection: 'column',
    gap: '5px',
  },
  finalLabel: {
    fontSize: '0.9rem',
    fontWeight: '600',
    color: '#4b5563',
  },
  mcContainer: {
    display: 'flex',
    flexDirection: 'column',
    gap: '10px',
  },
  mcOption: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    padding: '12px',
    background: '#fff',
    borderRadius: '8px',
    border: '1px solid #e5e7eb',
    cursor: 'pointer',
    transition: 'all 0.2s',
  },
  mcRadio: {
    width: '18px',
    height: '18px',
    accentColor: '#6366f1',
  },
  mcText: {
    fontSize: '1rem',
    color: '#374151',
  },
  barChartContainer: {
    display: 'flex',
    flexDirection: 'column',
    gap: '15px',
  },
  coordContainer: {
    display: 'flex',
    gap: '20px',
    flexWrap: 'wrap',
  },
  coordInput: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  coordField: {
    width: '120px',
    padding: '10px',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    fontSize: '1rem',
  },
  correctAnswer: {
    marginTop: '15px',
    padding: '12px',
    background: '#ecfdf5',
    borderRadius: '6px',
    color: '#065f46',
    fontSize: '0.9rem',
  },
  feedback: {
    marginTop: '10px',
    padding: '12px',
    background: '#fef3c7',
    borderRadius: '6px',
    color: '#92400e',
    fontSize: '0.9rem',
  },
  footer: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: '20px',
    paddingTop: '20px',
    borderTop: '1px solid #e5e7eb',
  },
  navButtons: {
    display: 'flex',
    gap: '10px',
  },
  navButton: {
    padding: '10px 20px',
    border: '1px solid #d1d5db',
    background: '#fff',
    borderRadius: '8px',
    cursor: 'pointer',
    fontSize: '0.95rem',
    fontWeight: '500',
  },
  submitButton: {
    padding: '12px 30px',
    border: 'none',
    background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
    color: '#fff',
    borderRadius: '8px',
    cursor: 'pointer',
    fontSize: '1rem',
    fontWeight: '600',
    boxShadow: '0 2px 8px rgba(99, 102, 241, 0.3)',
  },
  resultsPreview: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
  },
  scoreLabel: {
    fontSize: '1rem',
    color: '#4b5563',
  },
  score: {
    fontSize: '1.3rem',
    fontWeight: '700',
    color: '#6366f1',
  },
  emptyState: {
    textAlign: 'center',
    padding: '60px 20px',
    color: '#6b7280',
  },
};
