import { useState, useEffect } from 'react';
import InteractiveNumberLine from './InteractiveNumberLine';
import InteractiveCoordinatePlane from './InteractiveCoordinatePlane';
import InteractiveGeometry from './InteractiveGeometry';
import InteractiveBoxPlot from './InteractiveBoxPlot';
import InteractiveFunctionGraph from './InteractiveFunctionGraph';
import InteractiveDotPlot from './InteractiveDotPlot';
import InteractiveStemAndLeaf from './InteractiveStemAndLeaf';
import InteractiveUnitCircle from './InteractiveUnitCircle';
import InteractiveTransformations from './InteractiveTransformations';
import InteractiveFractionModel from './InteractiveFractionModel';
import InteractiveProbabilityTree from './InteractiveProbabilityTree';
import InteractiveTapeDiagram from './InteractiveTapeDiagram';
import InteractiveVennDiagram from './InteractiveVennDiagram';
import InteractiveProtractor from './InteractiveProtractor';
import MathInput from './MathInput';
import DataTable from './DataTable';
import VirtualMathKeyboard from './VirtualMathKeyboard';

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
  const [focusedInput, setFocusedInput] = useState(null);

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

  const handleInputFocus = (el, key, mode) => {
    setFocusedInput({ ref: el, key, mode });
  };

  const handleKeyboardInsert = (text) => {
    if (!focusedInput) return;
    const el = focusedInput.ref;
    const start = el?.selectionStart ?? (el?.value?.length || 0);
    const end = el?.selectionEnd ?? start;
    const parts = focusedInput.key.split('-');
    const sIdx = parseInt(parts[0]);
    const qIdx = parseInt(parts[1]);
    const subField = parts[2];
    const answerKey = `${sIdx}-${qIdx}`;
    const currentAnswer = answers[answerKey]?.value;

    if (subField === 'math' || subField === 'work') {
      const field = subField === 'math' ? 'final' : 'work';
      const otherField = subField === 'math' ? 'work' : 'final';
      const current = currentAnswer?.[field] || '';
      const newVal = current.slice(0, start) + text + current.slice(end);
      updateAnswer(sIdx, qIdx, { ...currentAnswer, [field]: newVal, [otherField]: currentAnswer?.[otherField] || '' });
    } else {
      const current = (typeof currentAnswer === 'string') ? currentAnswer : '';
      const newVal = current.slice(0, start) + text + current.slice(end);
      updateAnswer(sIdx, qIdx, newVal);
    }

    requestAnimationFrame(() => {
      if (el) {
        const newPos = start + text.length;
        el.selectionStart = newPos;
        el.selectionEnd = newPos;
        el.focus();
      }
    });
  };

  const handleKeyboardBackspace = () => {
    if (!focusedInput) return;
    const el = focusedInput.ref;
    const start = el?.selectionStart ?? 0;
    const end = el?.selectionEnd ?? start;
    if (start === 0 && end === 0) return;

    const parts = focusedInput.key.split('-');
    const sIdx = parseInt(parts[0]);
    const qIdx = parseInt(parts[1]);
    const subField = parts[2];
    const answerKey = `${sIdx}-${qIdx}`;
    const currentAnswer = answers[answerKey]?.value;

    const deleteStart = start === end ? start - 1 : start;

    if (subField === 'math' || subField === 'work') {
      const field = subField === 'math' ? 'final' : 'work';
      const otherField = subField === 'math' ? 'work' : 'final';
      const current = currentAnswer?.[field] || '';
      const newVal = current.slice(0, deleteStart) + current.slice(end);
      updateAnswer(sIdx, qIdx, { ...currentAnswer, [field]: newVal, [otherField]: currentAnswer?.[otherField] || '' });
    } else {
      const current = (typeof currentAnswer === 'string') ? currentAnswer : '';
      const newVal = current.slice(0, deleteStart) + current.slice(end);
      updateAnswer(sIdx, qIdx, newVal);
    }

    requestAnimationFrame(() => {
      if (el) {
        el.selectionStart = deleteStart;
        el.selectionEnd = deleteStart;
        el.focus();
      }
    });
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
              onInputFocus={handleInputFocus}
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

      {focusedInput && !readOnly && (
        <VirtualMathKeyboard
          mode={focusedInput.mode}
          onInsert={handleKeyboardInsert}
          onBackspace={handleKeyboardBackspace}
          onClose={() => setFocusedInput(null)}
        />
      )}
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
        <rect x={0} y={0} width={chartWidth} height={chartHeight + padding.top + padding.bottom} style={{ fill: 'var(--input-bg)' }} rx={8} />
        {title && (
          <text x={chartWidth / 2} y={20} textAnchor="middle" fontSize={14} fontWeight="600" style={{ fill: 'var(--text-primary)' }}>{title}</text>
        )}
        {y_label && (
          <text x={15} y={chartHeight / 2 + padding.top} textAnchor="middle" fontSize={11} style={{ fill: 'var(--text-muted)' }} transform={`rotate(-90, 15, ${chartHeight / 2 + padding.top})`}>{y_label}</text>
        )}
        <line x1={padding.left} y1={padding.top} x2={padding.left} y2={chartHeight + padding.top} style={{ stroke: 'var(--glass-border)' }} strokeWidth={1} />
        <line x1={padding.left} y1={chartHeight + padding.top} x2={chartWidth - padding.right} y2={chartHeight + padding.top} style={{ stroke: 'var(--glass-border)' }} strokeWidth={1} />
        {[0, 0.25, 0.5, 0.75, 1].map((tick, i) => {
          const y = padding.top + chartHeight * (1 - tick);
          return (
            <g key={i}>
              <line x1={padding.left - 5} y1={y} x2={padding.left} y2={y} style={{ stroke: 'var(--text-muted)' }} />
              <text x={padding.left - 10} y={y + 4} textAnchor="end" fontSize={10} style={{ fill: 'var(--text-muted)' }}>{Math.round(maxVal * tick)}</text>
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
              <text x={x + barWidth / 2} y={y - 5} textAnchor="middle" fontSize={10} style={{ fill: 'var(--text-primary)' }} fontWeight="500">{val}</text>
              <text x={x + barWidth / 2} y={chartHeight + padding.top + 15} textAnchor="middle" fontSize={10} style={{ fill: 'var(--text-primary)' }}>{labels[idx]}</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

/**
 * parseMarkdownTable - Detects markdown pipe tables in text and splits into
 * { before, table: { headers, rows }, after } or null if no table found.
 */
function parseMarkdownTable(text) {
  if (!text || typeof text !== 'string' || !text.includes('|')) return null;

  // Match pipe-delimited table patterns (may be on one line or multi-line)
  // Normalize: if all on one line, split on separator row pattern
  const lines = text.includes('\n')
    ? text.split('\n')
    : text.split(/(?=\|[\s-]+\|)/);

  // Find table boundaries
  let tableLines = [];
  let beforeText = '';
  let afterText = '';
  let inTable = false;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    const isSep = /^\|[\s-|:]+\|$/.test(line) || /^[\s-|:]+$/.test(line.replace(/\|/g, '|'));
    const isPipeRow = (line.match(/\|/g) || []).length >= 2;

    if (isPipeRow && !inTable) {
      inTable = true;
      // Everything before this is beforeText
      beforeText = lines.slice(0, i).join(' ').trim();
    }

    if (inTable) {
      if (isPipeRow) {
        tableLines.push(line);
      } else {
        afterText = lines.slice(i).join(' ').trim();
        break;
      }
    }
  }

  if (tableLines.length < 2) return null;

  // Parse rows - filter out separator rows
  const parseRow = (line) =>
    line.split('|').map(c => c.trim()).filter((c, i, arr) => i > 0 && i < arr.length);

  const dataRows = tableLines.filter(l => !/^\|[\s-:|]+\|?$/.test(l) && !/^[\s-:|]+$/.test(l));
  if (dataRows.length < 2) return null;

  const headers = parseRow(dataRows[0]);
  const rows = dataRows.slice(1).map(parseRow);

  return { before: beforeText, table: { headers, rows }, after: afterText };
}

/**
 * RenderQuestionText - renders question text with inline markdown tables parsed into HTML tables
 */
function RenderQuestionText({ text, style }) {
  const parsed = parseMarkdownTable(text);
  if (!parsed) return <p style={style}>{text}</p>;

  const tableStyle = {
    borderCollapse: 'collapse',
    margin: '10px 0',
    fontSize: '0.95rem',
    width: 'auto',
    minWidth: '200px',
  };
  const thStyle = {
    padding: '8px 16px',
    background: 'rgba(99, 102, 241, 0.15)',
    border: '1px solid rgba(255,255,255,0.15)',
    fontWeight: 600,
    textAlign: 'center',
    color: 'var(--text-primary)',
  };
  const tdStyle = {
    padding: '8px 16px',
    border: '1px solid rgba(255,255,255,0.1)',
    textAlign: 'center',
    color: 'var(--text-primary)',
  };

  return (
    <div>
      {parsed.before && <p style={style}>{parsed.before}</p>}
      <table style={tableStyle}>
        <thead>
          <tr>
            {parsed.table.headers.map((h, i) => <th key={i} style={thStyle}>{h}</th>)}
          </tr>
        </thead>
        <tbody>
          {parsed.table.rows.map((row, rIdx) => (
            <tr key={rIdx}>
              {row.map((cell, cIdx) => <td key={cIdx} style={tdStyle}>{cell}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
      {parsed.after && <p style={style}>{parsed.after}</p>}
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
  result,
  onInputFocus
}) {
  const qType = question.question_type || question.visual_type || 'short_answer';
  const qNum = question.number || questionIndex + 1;
  const inputKey = `${sectionIndex}-${questionIndex}`;

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
      case 'regular_polygon':
      case 'circle':
      case 'trapezoid':
      case 'parallelogram':
      case 'rectangular_prism':
      case 'cylinder':
      case 'cone':
      case 'pyramid':
      case 'sphere':
      case 'similarity':
      case 'pythagorean':
      case 'angles':
      case 'trig':
        return (
          <InteractiveGeometry
            type={qType === 'geometry' ? 'triangle' : qType}
            base={question.base || 6}
            height={question.height || 4}
            width={question.width}
            radius={question.radius}
            topBase={question.top_base}
            mode={question.mode || 'area'}
            sides={question.sides}
            sideLength={question.side_length}
            sideA={question.side_a}
            sideB={question.side_b}
            sideC={question.side_c}
            angle1={question.angle1}
            angle2={question.angle2}
            missingAngle={question.missing_angle}
            theta={question.theta}
            trigFunc={question.trig_func}
            missingSide={question.missing_side}
            slantHeight={question.slant_height}
            scale={question.scale}
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

      case 'function_graph':
        return (
          <InteractiveFunctionGraph
            xRange={question.x_range || [-10, 10]}
            yRange={question.y_range || [-10, 10]}
            expressions={answer || []}
            onChange={onAnswer}
            correctExpressions={showAnswer ? question.correct_expressions : null}
            readOnly={readOnly}
            maxExpressions={question.max_expressions || 3}
          />
        );

      case 'dot_plot':
        return (
          <InteractiveDotPlot
            categories={question.categories || []}
            minVal={question.min_val ?? 0}
            maxVal={question.max_val ?? 10}
            step={question.step ?? 1}
            dots={answer || {}}
            onChange={onAnswer}
            correctDots={showAnswer ? question.correct_dots : null}
            readOnly={readOnly}
            title={question.chart_title || ''}
          />
        );

      case 'stem_and_leaf':
        return (
          <InteractiveStemAndLeaf
            data={question.data || []}
            stems={question.stems || []}
            leaves={answer || {}}
            onChange={onAnswer}
            correctLeaves={showAnswer ? question.correct_leaves : null}
            readOnly={readOnly}
            title={question.chart_title || ''}
          />
        );

      case 'unit_circle':
        return (
          <InteractiveUnitCircle
            hiddenAngles={question.hidden_angles || []}
            hiddenValues={question.hidden_values || []}
            answers={answer || {}}
            onChange={onAnswer}
            correctAnswers={showAnswer ? question.correct_values : null}
            readOnly={readOnly}
            showRadians={question.show_radians !== false}
            showCoordinates={question.show_coordinates !== false}
          />
        );

      case 'transformations':
        return (
          <InteractiveTransformations
            originalVertices={question.original_vertices || [[1,1],[4,1],[4,3]]}
            transformationType={question.transformation_type || 'translation'}
            transformParams={question.transform_params || {}}
            userVertices={answer?.vertices || []}
            answer={answer?.answer || ''}
            onChange={onAnswer}
            correctVertices={showAnswer ? question.correct_vertices : null}
            correctAnswer={showAnswer ? question.answer : null}
            readOnly={readOnly}
            gridRange={question.grid_range || [-8, 8]}
            mode={question.mode || 'plot'}
          />
        );

      case 'fraction_model':
        return (
          <InteractiveFractionModel
            modelType={question.model_type || 'area'}
            denominator={question.denominator || 4}
            correctNumerator={showAnswer ? question.correct_numerator : null}
            shaded={answer?.shaded || []}
            answer={answer?.answer || ''}
            onChange={onAnswer}
            correctAnswer={showAnswer ? question.answer : null}
            readOnly={readOnly}
            showFractionInput={question.show_fraction_input !== false}
            compareFractions={question.compare_fractions || null}
          />
        );

      case 'probability_tree':
        return (
          <InteractiveProbabilityTree
            tree={question.tree || null}
            answers={answer || {}}
            onChange={onAnswer}
            correctAnswers={showAnswer ? question.correct_values : null}
            readOnly={readOnly}
          />
        );

      case 'tape_diagram':
        return (
          <InteractiveTapeDiagram
            tapes={question.tapes || []}
            answers={answer || {}}
            onChange={onAnswer}
            correctAnswers={showAnswer ? question.correct_values : null}
            readOnly={readOnly}
            title={question.chart_title || ''}
          />
        );

      case 'venn_diagram':
        return (
          <InteractiveVennDiagram
            sets={question.sets || 2}
            labels={question.set_labels || ['Set A', 'Set B']}
            regions={question.regions || {}}
            answers={answer || {}}
            onChange={onAnswer}
            correctAnswers={showAnswer ? question.correct_values : null}
            readOnly={readOnly}
            title={question.chart_title || ''}
            mode={question.mode || 'count'}
          />
        );

      case 'protractor':
      case 'angle_protractor':
        return (
          <InteractiveProtractor
            givenAngle={question.given_angle}
            targetAngle={question.target_angle}
            mode={question.mode || 'measure'}
            answer={typeof answer === 'object' ? answer?.answer || '' : answer || ''}
            userAngle={typeof answer === 'object' ? answer?.userAngle || 0 : 0}
            onChange={onAnswer}
            correctAnswer={showAnswer ? question.answer : null}
            readOnly={readOnly}
            showClassification={question.show_classification !== false}
          />
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
  };

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

      <div style={styles.inputContainer}>
        {renderInput()}
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
        'probability_tree', 'tape_diagram', 'venn_diagram', 'protractor', 'angle_protractor'
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
    borderBottom: '2px solid var(--glass-border)',
  },
  title: {
    fontSize: '1.8rem',
    fontWeight: '700',
    margin: '0 0 5px 0',
    color: 'var(--text-primary)',
  },
  studentName: {
    fontSize: '0.95rem',
    color: 'var(--text-muted)',
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
    background: 'var(--glass-border)',
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
    color: 'var(--text-muted)',
  },
  closeButton: {
    width: '36px',
    height: '36px',
    border: 'none',
    background: 'var(--input-bg)',
    borderRadius: '8px',
    fontSize: '1.5rem',
    cursor: 'pointer',
    color: 'var(--text-muted)',
  },
  instructions: {
    padding: '15px',
    background: 'rgba(99, 102, 241, 0.1)',
    borderRadius: '8px',
    marginBottom: '20px',
    color: 'var(--text-secondary)',
    fontSize: '0.95rem',
    border: '1px solid rgba(99, 102, 241, 0.2)',
  },
  tabs: {
    display: 'flex',
    gap: '8px',
    marginBottom: '20px',
    flexWrap: 'wrap',
  },
  tab: {
    padding: '10px 16px',
    border: '1px solid var(--glass-border)',
    background: 'var(--glass-bg)',
    borderRadius: '8px',
    cursor: 'pointer',
    fontSize: '0.9rem',
    fontWeight: '500',
    color: 'var(--text-secondary)',
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
    background: 'var(--glass-bg)',
    borderRadius: '12px',
    padding: '20px',
    border: '1px solid var(--glass-border)',
    marginBottom: '20px',
  },
  sectionTitle: {
    fontSize: '1.2rem',
    fontWeight: '600',
    marginBottom: '20px',
    color: 'var(--text-primary)',
  },
  question: {
    padding: '20px',
    background: 'var(--input-bg)',
    borderRadius: '10px',
    marginBottom: '15px',
    border: '1px solid var(--glass-border)',
  },
  questionCorrect: {
    background: 'rgba(16, 185, 129, 0.1)',
    borderColor: 'rgba(16, 185, 129, 0.3)',
  },
  questionIncorrect: {
    background: 'rgba(239, 68, 68, 0.1)',
    borderColor: 'rgba(239, 68, 68, 0.3)',
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
    color: 'var(--text-muted)',
    background: 'var(--glass-border)',
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
    color: 'var(--text-primary)',
    marginBottom: '15px',
    lineHeight: '1.5',
  },
  inputContainer: {
    marginTop: '10px',
  },
  shortAnswer: {
    width: '100%',
    padding: '12px',
    border: '1px solid var(--glass-border)',
    borderRadius: '8px',
    fontSize: '1rem',
    resize: 'vertical',
    fontFamily: 'inherit',
    background: 'var(--input-bg)',
    color: 'var(--text-primary)',
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
    color: 'var(--text-secondary)',
  },
  workTextarea: {
    width: '100%',
    minHeight: '100px',
    padding: '12px',
    border: '1px solid var(--glass-border)',
    borderRadius: '8px',
    fontSize: '1rem',
    resize: 'vertical',
    fontFamily: 'inherit',
    background: 'var(--input-bg)',
    color: 'var(--text-primary)',
  },
  finalAnswer: {
    display: 'flex',
    flexDirection: 'column',
    gap: '5px',
  },
  finalLabel: {
    fontSize: '0.9rem',
    fontWeight: '600',
    color: 'var(--text-secondary)',
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
    background: 'var(--glass-bg)',
    borderRadius: '8px',
    border: '1px solid var(--glass-border)',
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
    color: 'var(--text-primary)',
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
    border: '1px solid var(--glass-border)',
    borderRadius: '6px',
    fontSize: '1rem',
    background: 'var(--input-bg)',
    color: 'var(--text-primary)',
  },
  imageUploadArea: {
    marginTop: '10px',
    borderTop: '1px solid rgba(255,255,255,0.06)',
    paddingTop: '10px',
  },
  imageUploadLabel: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '8px',
    padding: '8px 14px',
    borderRadius: '8px',
    border: '1px dashed rgba(99, 102, 241, 0.3)',
    background: 'rgba(99, 102, 241, 0.05)',
    cursor: 'pointer',
    fontSize: '0.85rem',
    color: 'var(--text-secondary)',
    transition: 'all 0.2s',
  },
  imageUploadIcon: {
    fontSize: '1.1rem',
  },
  imageUploadText: {
    opacity: 0.8,
  },
  imagePreviewWrapper: {
    position: 'relative',
    display: 'inline-block',
  },
  imagePreview: {
    maxWidth: '300px',
    maxHeight: '200px',
    borderRadius: '8px',
    border: '1px solid var(--glass-border)',
  },
  imageRemoveBtn: {
    position: 'absolute',
    top: '-8px',
    right: '-8px',
    width: '24px',
    height: '24px',
    borderRadius: '50%',
    background: '#ef4444',
    color: '#fff',
    border: 'none',
    cursor: 'pointer',
    fontSize: '1rem',
    lineHeight: '1',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  correctAnswer: {
    marginTop: '15px',
    padding: '12px',
    background: 'rgba(16, 185, 129, 0.1)',
    borderRadius: '6px',
    color: '#10b981',
    fontSize: '0.9rem',
    border: '1px solid rgba(16, 185, 129, 0.2)',
  },
  feedback: {
    marginTop: '10px',
    padding: '12px',
    background: 'rgba(245, 158, 11, 0.1)',
    borderRadius: '6px',
    color: '#f59e0b',
    fontSize: '0.9rem',
    border: '1px solid rgba(245, 158, 11, 0.2)',
  },
  footer: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: '20px',
    paddingTop: '20px',
    borderTop: '1px solid var(--glass-border)',
  },
  navButtons: {
    display: 'flex',
    gap: '10px',
  },
  navButton: {
    padding: '10px 20px',
    border: '1px solid var(--glass-border)',
    background: 'var(--glass-bg)',
    borderRadius: '8px',
    cursor: 'pointer',
    fontSize: '0.95rem',
    fontWeight: '500',
    color: 'var(--text-primary)',
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
    color: 'var(--text-secondary)',
  },
  score: {
    fontSize: '1.3rem',
    fontWeight: '700',
    color: '#6366f1',
  },
  emptyState: {
    textAlign: 'center',
    padding: '60px 20px',
    color: 'var(--text-muted)',
  },
};
