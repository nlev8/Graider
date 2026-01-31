# STEM Subject Support Implementation Plan

This document contains precise code edits for implementing Math, Science, and Geography support in the Assignment Builder and Lesson Planner.

## Implementation Status

| Phase | Feature | Status |
|-------|---------|--------|
| 1 | Math Equation Support | ✅ Implemented |
| 2 | Science Data Table Support | ✅ Implemented |
| 3 | Geography Coordinate Support | ✅ Implemented |
| 4 | Subject-Specific Lesson Templates | ✅ Implemented |
| 5 | App.jsx Integration | 🔲 Pending (requires frontend integration) |

### Files Created/Modified

**New Files:**
- `frontend/src/components/MathInput.jsx` - Math equation input with LaTeX
- `frontend/src/components/MathInput.css` - Styling for math input
- `frontend/src/components/DataTable.jsx` - Editable data table for science
- `frontend/src/components/DataTable.css` - Styling for data table
- `frontend/src/components/CoordinateInput.jsx` - Geographic coordinates input
- `frontend/src/components/CoordinateInput.css` - Styling for coordinates
- `frontend/src/components/index.js` - Component exports
- `backend/services/stem_grading.py` - STEM grading logic (SymPy, tolerances)
- `backend/data/lesson_templates.json` - Subject-specific activity templates

**Modified Files:**
- `requirements.txt` - Added sympy, antlr4-python3-runtime
- `frontend/package.json` - Added katex, react-katex
- `backend/routes/grading_routes.py` - Added STEM grading API endpoints
- `backend/routes/planner_routes.py` - Added lesson templates endpoint

### Next Steps

1. Run `npm install` in frontend to install katex/react-katex
2. Run `pip install sympy antlr4-python3-runtime` to install backend deps
3. Integrate MathInput, DataTable, CoordinateInput into App.jsx Builder tab

---

## Phase 1: Math Equation Support

### 1.1 Install KaTeX for Math Rendering

**File: `requirements.txt`** - No changes needed (math rendering is frontend-only)

**File: `frontend/package.json`** - Add dependency:
```json
{
  "dependencies": {
    "katex": "^0.16.9",
    "react-katex": "^3.0.1"
  }
}
```

### 1.2 Create Math Input Component

**New File: `frontend/src/components/MathInput.jsx`**
```jsx
import React, { useState, useEffect } from 'react';
import 'katex/dist/katex.min.css';
import { InlineMath, BlockMath } from 'react-katex';

const MATH_SYMBOLS = [
  { label: '÷', latex: '\\div' },
  { label: '×', latex: '\\times' },
  { label: '±', latex: '\\pm' },
  { label: '≠', latex: '\\neq' },
  { label: '≤', latex: '\\leq' },
  { label: '≥', latex: '\\geq' },
  { label: '√', latex: '\\sqrt{}' },
  { label: 'π', latex: '\\pi' },
  { label: '∞', latex: '\\infty' },
  { label: 'θ', latex: '\\theta' },
];

const MATH_TEMPLATES = [
  { label: 'Fraction', latex: '\\frac{a}{b}', display: '\\frac{a}{b}' },
  { label: 'Exponent', latex: 'x^{n}', display: 'x^{n}' },
  { label: 'Subscript', latex: 'x_{n}', display: 'x_{n}' },
  { label: 'Square Root', latex: '\\sqrt{x}', display: '\\sqrt{x}' },
  { label: 'Nth Root', latex: '\\sqrt[n]{x}', display: '\\sqrt[n]{x}' },
  { label: 'Absolute Value', latex: '|x|', display: '|x|' },
  { label: 'Summation', latex: '\\sum_{i=1}^{n}', display: '\\sum_{i=1}^{n}' },
  { label: 'Integral', latex: '\\int_{a}^{b}', display: '\\int_{a}^{b}' },
  { label: 'Limit', latex: '\\lim_{x \\to a}', display: '\\lim_{x \\to a}' },
  { label: 'Matrix 2x2', latex: '\\begin{pmatrix} a & b \\\\ c & d \\end{pmatrix}', display: '\\begin{pmatrix} a & b \\\\ c & d \\end{pmatrix}' },
];

export default function MathInput({ value, onChange, placeholder, block = false }) {
  const [latex, setLatex] = useState(value || '');
  const [showToolbar, setShowToolbar] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLatex(value || '');
  }, [value]);

  const handleChange = (e) => {
    const newValue = e.target.value;
    setLatex(newValue);
    setError(null);
    onChange(newValue);
  };

  const insertSymbol = (symbol) => {
    const newLatex = latex + symbol;
    setLatex(newLatex);
    onChange(newLatex);
  };

  const insertTemplate = (template) => {
    const newLatex = latex + template;
    setLatex(newLatex);
    onChange(newLatex);
  };

  const MathComponent = block ? BlockMath : InlineMath;

  return (
    <div className="math-input-container">
      <div className="math-toolbar">
        <button
          type="button"
          className="toolbar-toggle"
          onClick={() => setShowToolbar(!showToolbar)}
        >
          {showToolbar ? 'Hide Math Tools' : 'Show Math Tools'}
        </button>

        {showToolbar && (
          <div className="toolbar-content">
            <div className="symbol-row">
              <span className="row-label">Symbols:</span>
              {MATH_SYMBOLS.map((sym, idx) => (
                <button
                  key={idx}
                  type="button"
                  className="symbol-btn"
                  onClick={() => insertSymbol(sym.latex)}
                  title={sym.latex}
                >
                  <InlineMath math={sym.latex} />
                </button>
              ))}
            </div>
            <div className="template-row">
              <span className="row-label">Templates:</span>
              {MATH_TEMPLATES.map((tmpl, idx) => (
                <button
                  key={idx}
                  type="button"
                  className="template-btn"
                  onClick={() => insertTemplate(tmpl.latex)}
                  title={tmpl.label}
                >
                  <InlineMath math={tmpl.display} />
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      <textarea
        className="latex-input"
        value={latex}
        onChange={handleChange}
        placeholder={placeholder || 'Enter LaTeX (e.g., \\frac{1}{2} or x^2 + 3x - 4)'}
        rows={3}
      />

      <div className="math-preview">
        <span className="preview-label">Preview:</span>
        <div className="preview-content">
          {latex ? (
            <ErrorBoundary onError={(e) => setError(e.message)}>
              <MathComponent math={latex} />
            </ErrorBoundary>
          ) : (
            <span className="preview-placeholder">Math will render here</span>
          )}
          {error && <span className="preview-error">Invalid LaTeX: {error}</span>}
        </div>
      </div>
    </div>
  );
}

// Simple error boundary for catching KaTeX errors
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error) {
    if (this.props.onError) {
      this.props.onError(error);
    }
  }

  render() {
    if (this.state.hasError) {
      return null;
    }
    return this.props.children;
  }
}
```

### 1.3 Math Input Styles

**New File: `frontend/src/components/MathInput.css`**
```css
.math-input-container {
  display: flex;
  flex-direction: column;
  gap: 8px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px;
  background: #f8fafc;
}

.math-toolbar {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.toolbar-toggle {
  padding: 6px 12px;
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  width: fit-content;
}

.toolbar-toggle:hover {
  background: #2563eb;
}

.toolbar-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px;
  background: white;
  border-radius: 4px;
  border: 1px solid #e2e8f0;
}

.symbol-row, .template-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
}

.row-label {
  font-size: 12px;
  color: #64748b;
  min-width: 70px;
}

.symbol-btn, .template-btn {
  padding: 4px 8px;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  border-radius: 4px;
  cursor: pointer;
  min-width: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.symbol-btn:hover, .template-btn:hover {
  background: #e2e8f0;
}

.latex-input {
  padding: 8px;
  border: 1px solid #e2e8f0;
  border-radius: 4px;
  font-family: 'Fira Code', 'Monaco', monospace;
  font-size: 14px;
  resize: vertical;
}

.math-preview {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 12px;
  background: white;
  border-radius: 4px;
  border: 1px solid #e2e8f0;
  min-height: 40px;
}

.preview-label {
  font-size: 12px;
  color: #64748b;
  min-width: 60px;
}

.preview-content {
  flex: 1;
  font-size: 18px;
}

.preview-placeholder {
  color: #94a3b8;
  font-style: italic;
}

.preview-error {
  color: #ef4444;
  font-size: 12px;
}
```

### 1.4 Update Assignment Builder for Math Questions

**File: `frontend/src/App.jsx`** - Add to Builder tab section (after existing question types):

```jsx
// Add to state declarations (around line 45)
const [questionType, setQuestionType] = useState('text'); // 'text', 'math', 'data-table', 'coordinates'

// Add to the Builder panel question creation section
{questionType === 'math' && (
  <div className="math-question-section">
    <h4>Math Question</h4>
    <MathInput
      value={currentQuestion.equation}
      onChange={(latex) => setCurrentQuestion({
        ...currentQuestion,
        equation: latex,
        type: 'math'
      })}
      placeholder="Enter the equation or expression"
      block={true}
    />

    <div className="answer-section">
      <label>Correct Answer(s):</label>
      <MathInput
        value={currentQuestion.correctAnswer}
        onChange={(latex) => setCurrentQuestion({
          ...currentQuestion,
          correctAnswer: latex
        })}
        placeholder="Enter the correct answer (can include equivalent forms)"
      />

      <div className="equivalent-forms">
        <label>
          <input
            type="checkbox"
            checked={currentQuestion.acceptEquivalent}
            onChange={(e) => setCurrentQuestion({
              ...currentQuestion,
              acceptEquivalent: e.target.checked
            })}
          />
          Accept mathematically equivalent forms
        </label>
        <p className="hint">
          e.g., ½ = 0.5 = 1/2, or x² - 4 = (x+2)(x-2)
        </p>
      </div>

      <div className="partial-credit">
        <label>
          <input
            type="checkbox"
            checked={currentQuestion.showWork}
            onChange={(e) => setCurrentQuestion({
              ...currentQuestion,
              showWork: e.target.checked
            })}
          />
          Require work shown (allows partial credit)
        </label>
      </div>
    </div>
  </div>
)}
```

### 1.5 Backend Math Grading Support

**File: `assignment_grader.py`** - Add math-specific grading logic:

```python
# Add to imports
import sympy
from sympy.parsing.latex import parse_latex
from sympy import simplify, nsimplify

def check_math_equivalence(student_answer: str, correct_answer: str, tolerance: float = 0.001) -> dict:
    """
    Check if two math expressions are equivalent.
    Returns dict with 'equivalent', 'simplified_student', 'simplified_correct', 'error'
    """
    try:
        # Parse LaTeX to SymPy expressions
        student_expr = parse_latex(student_answer)
        correct_expr = parse_latex(correct_answer)

        # Try symbolic equivalence first
        difference = simplify(student_expr - correct_expr)
        if difference == 0:
            return {
                'equivalent': True,
                'method': 'symbolic',
                'simplified_student': str(simplify(student_expr)),
                'simplified_correct': str(simplify(correct_expr))
            }

        # Try numerical evaluation if symbolic fails
        try:
            student_val = float(student_expr.evalf())
            correct_val = float(correct_expr.evalf())
            if abs(student_val - correct_val) < tolerance:
                return {
                    'equivalent': True,
                    'method': 'numerical',
                    'difference': abs(student_val - correct_val)
                }
        except:
            pass

        return {
            'equivalent': False,
            'simplified_student': str(simplify(student_expr)),
            'simplified_correct': str(simplify(correct_expr))
        }

    except Exception as e:
        return {
            'equivalent': False,
            'error': str(e)
        }


def grade_math_question(question: dict, student_response: str) -> dict:
    """
    Grade a math question with support for:
    - Equivalent forms acceptance
    - Partial credit for work shown
    - Step-by-step solution checking
    """
    result = {
        'question_type': 'math',
        'points_earned': 0,
        'points_possible': question.get('points', 1),
        'feedback': []
    }

    correct_answer = question.get('correctAnswer', '')
    accept_equivalent = question.get('acceptEquivalent', True)
    show_work = question.get('showWork', False)

    # Check the final answer
    equivalence = check_math_equivalence(student_response, correct_answer)

    if equivalence.get('equivalent'):
        result['points_earned'] = result['points_possible']
        result['feedback'].append('Correct! Your answer is mathematically equivalent to the expected answer.')

        if equivalence.get('method') == 'numerical':
            result['feedback'].append(f"(Verified numerically within tolerance)")
    else:
        # If work shown is required, use AI to check for partial credit
        if show_work and len(student_response) > 20:
            result['needs_ai_review'] = True
            result['feedback'].append('Answer differs from expected. Work will be reviewed for partial credit.')
        else:
            result['feedback'].append(f"Incorrect. Expected: {correct_answer}")

            if equivalence.get('error'):
                result['feedback'].append(f"Note: Could not parse your answer. Please use proper notation.")

    return result
```

### 1.6 Add SymPy to Requirements

**File: `requirements.txt`** - Add:
```
sympy>=1.12
antlr4-python3-runtime==4.11.*
```

---

## Phase 2: Science Data Table Support

### 2.1 Create Data Table Component

**New File: `frontend/src/components/DataTable.jsx`**
```jsx
import React, { useState, useEffect } from 'react';

export default function DataTable({
  columns = 3,
  rows = 4,
  headers = [],
  data = [],
  editable = true,
  units = [],
  onChange
}) {
  const [tableData, setTableData] = useState(() => {
    if (data.length > 0) return data;
    return Array(rows).fill(null).map(() => Array(columns).fill(''));
  });

  const [tableHeaders, setTableHeaders] = useState(() => {
    if (headers.length > 0) return headers;
    return Array(columns).fill('').map((_, i) => `Column ${i + 1}`);
  });

  const [columnUnits, setColumnUnits] = useState(() => {
    if (units.length > 0) return units;
    return Array(columns).fill('');
  });

  useEffect(() => {
    if (onChange) {
      onChange({
        headers: tableHeaders,
        units: columnUnits,
        data: tableData
      });
    }
  }, [tableHeaders, columnUnits, tableData]);

  const updateCell = (rowIdx, colIdx, value) => {
    const newData = tableData.map((row, ri) =>
      ri === rowIdx
        ? row.map((cell, ci) => (ci === colIdx ? value : cell))
        : row
    );
    setTableData(newData);
  };

  const updateHeader = (colIdx, value) => {
    const newHeaders = [...tableHeaders];
    newHeaders[colIdx] = value;
    setTableHeaders(newHeaders);
  };

  const updateUnit = (colIdx, value) => {
    const newUnits = [...columnUnits];
    newUnits[colIdx] = value;
    setColumnUnits(newUnits);
  };

  const addRow = () => {
    setTableData([...tableData, Array(columns).fill('')]);
  };

  const removeRow = (idx) => {
    if (tableData.length > 1) {
      setTableData(tableData.filter((_, i) => i !== idx));
    }
  };

  const addColumn = () => {
    setTableHeaders([...tableHeaders, `Column ${tableHeaders.length + 1}`]);
    setColumnUnits([...columnUnits, '']);
    setTableData(tableData.map(row => [...row, '']));
  };

  const removeColumn = (idx) => {
    if (tableHeaders.length > 1) {
      setTableHeaders(tableHeaders.filter((_, i) => i !== idx));
      setColumnUnits(columnUnits.filter((_, i) => i !== idx));
      setTableData(tableData.map(row => row.filter((_, i) => i !== idx)));
    }
  };

  return (
    <div className="data-table-container">
      <div className="table-controls">
        <button type="button" onClick={addRow}>+ Add Row</button>
        <button type="button" onClick={addColumn}>+ Add Column</button>
      </div>

      <table className="data-table">
        <thead>
          <tr className="header-row">
            {tableHeaders.map((header, colIdx) => (
              <th key={colIdx}>
                {editable ? (
                  <input
                    type="text"
                    value={header}
                    onChange={(e) => updateHeader(colIdx, e.target.value)}
                    placeholder="Header"
                    className="header-input"
                  />
                ) : (
                  header
                )}
                {editable && (
                  <button
                    type="button"
                    className="remove-col-btn"
                    onClick={() => removeColumn(colIdx)}
                    title="Remove column"
                  >
                    ×
                  </button>
                )}
              </th>
            ))}
            {editable && <th className="action-col"></th>}
          </tr>
          <tr className="units-row">
            {columnUnits.map((unit, colIdx) => (
              <th key={colIdx}>
                {editable ? (
                  <input
                    type="text"
                    value={unit}
                    onChange={(e) => updateUnit(colIdx, e.target.value)}
                    placeholder="units (e.g., mL, °C)"
                    className="unit-input"
                  />
                ) : (
                  unit && `(${unit})`
                )}
              </th>
            ))}
            {editable && <th></th>}
          </tr>
        </thead>
        <tbody>
          {tableData.map((row, rowIdx) => (
            <tr key={rowIdx}>
              {row.map((cell, colIdx) => (
                <td key={colIdx}>
                  {editable ? (
                    <input
                      type="text"
                      value={cell}
                      onChange={(e) => updateCell(rowIdx, colIdx, e.target.value)}
                      placeholder="—"
                      className="cell-input"
                    />
                  ) : (
                    cell || '—'
                  )}
                </td>
              ))}
              {editable && (
                <td className="action-col">
                  <button
                    type="button"
                    className="remove-row-btn"
                    onClick={() => removeRow(rowIdx)}
                    title="Remove row"
                  >
                    ×
                  </button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

### 2.2 Data Table Styles

**New File: `frontend/src/components/DataTable.css`**
```css
.data-table-container {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.table-controls {
  display: flex;
  gap: 8px;
}

.table-controls button {
  padding: 6px 12px;
  background: #10b981;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}

.table-controls button:hover {
  background: #059669;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  border: 1px solid #e2e8f0;
  background: white;
}

.data-table th,
.data-table td {
  border: 1px solid #e2e8f0;
  padding: 4px;
  text-align: center;
}

.data-table th {
  background: #f1f5f9;
}

.header-row th {
  position: relative;
}

.header-input {
  width: 100%;
  padding: 6px;
  border: none;
  background: transparent;
  text-align: center;
  font-weight: 600;
}

.unit-input {
  width: 100%;
  padding: 4px;
  border: none;
  background: transparent;
  text-align: center;
  font-size: 12px;
  color: #64748b;
}

.cell-input {
  width: 100%;
  padding: 6px;
  border: none;
  text-align: center;
}

.cell-input:focus,
.header-input:focus,
.unit-input:focus {
  outline: 2px solid #3b82f6;
  background: #eff6ff;
}

.action-col {
  width: 30px;
  background: transparent !important;
  border: none !important;
}

.remove-col-btn,
.remove-row-btn {
  width: 20px;
  height: 20px;
  padding: 0;
  background: #fee2e2;
  color: #ef4444;
  border: none;
  border-radius: 50%;
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
}

.remove-col-btn:hover,
.remove-row-btn:hover {
  background: #fecaca;
}

.remove-col-btn {
  position: absolute;
  top: 2px;
  right: 2px;
}

.units-row th {
  background: #f8fafc;
  font-weight: normal;
  font-size: 12px;
  color: #64748b;
}
```

### 2.3 Science Data Grading Logic

**File: `assignment_grader.py`** - Add:

```python
def grade_data_table(expected_table: dict, student_table: dict, tolerance_percent: float = 5.0) -> dict:
    """
    Grade a data table with tolerance for numerical values.

    Args:
        expected_table: {'headers': [...], 'units': [...], 'data': [[...]]}
        student_table: Same structure as expected
        tolerance_percent: Acceptable percentage deviation for numerical values

    Returns:
        Grading result with per-cell feedback
    """
    result = {
        'question_type': 'data_table',
        'total_cells': 0,
        'correct_cells': 0,
        'cell_results': [],
        'feedback': []
    }

    expected_data = expected_table.get('data', [])
    student_data = student_table.get('data', [])

    # Check dimensions
    if len(student_data) != len(expected_data):
        result['feedback'].append(f"Row count mismatch: expected {len(expected_data)}, got {len(student_data)}")

    for row_idx, expected_row in enumerate(expected_data):
        if row_idx >= len(student_data):
            result['feedback'].append(f"Missing row {row_idx + 1}")
            continue

        student_row = student_data[row_idx]

        for col_idx, expected_val in enumerate(expected_row):
            result['total_cells'] += 1

            if col_idx >= len(student_row):
                result['cell_results'].append({
                    'row': row_idx,
                    'col': col_idx,
                    'correct': False,
                    'feedback': 'Missing value'
                })
                continue

            student_val = student_row[col_idx]
            cell_result = check_cell_value(expected_val, student_val, tolerance_percent)
            cell_result['row'] = row_idx
            cell_result['col'] = col_idx

            if cell_result['correct']:
                result['correct_cells'] += 1

            result['cell_results'].append(cell_result)

    # Calculate score
    if result['total_cells'] > 0:
        result['score_percent'] = (result['correct_cells'] / result['total_cells']) * 100
    else:
        result['score_percent'] = 0

    return result


def check_cell_value(expected: str, student: str, tolerance_percent: float) -> dict:
    """Check if a single cell value is correct within tolerance."""
    # Clean values
    expected_clean = str(expected).strip()
    student_clean = str(student).strip()

    # Exact match
    if expected_clean.lower() == student_clean.lower():
        return {'correct': True, 'feedback': 'Correct'}

    # Try numerical comparison
    try:
        expected_num = float(expected_clean.replace(',', ''))
        student_num = float(student_clean.replace(',', ''))

        if expected_num == 0:
            if student_num == 0:
                return {'correct': True, 'feedback': 'Correct'}
        else:
            percent_diff = abs((student_num - expected_num) / expected_num) * 100
            if percent_diff <= tolerance_percent:
                return {
                    'correct': True,
                    'feedback': f'Correct (within {tolerance_percent}% tolerance)',
                    'deviation': percent_diff
                }
            else:
                return {
                    'correct': False,
                    'feedback': f'Expected {expected_clean}, got {student_clean} ({percent_diff:.1f}% off)',
                    'deviation': percent_diff
                }
    except ValueError:
        pass

    # String comparison failed
    return {
        'correct': False,
        'feedback': f'Expected "{expected_clean}", got "{student_clean}"'
    }
```

---

## Phase 3: Geography Coordinate Support

### 3.1 Create Coordinate Input Component

**New File: `frontend/src/components/CoordinateInput.jsx`**
```jsx
import React, { useState, useEffect } from 'react';

const COORDINATE_FORMATS = [
  { id: 'dd', label: 'Decimal Degrees', example: '40.7128, -74.0060' },
  { id: 'dms', label: 'Degrees Minutes Seconds', example: '40°42\'46"N, 74°0\'22"W' },
  { id: 'dm', label: 'Degrees Decimal Minutes', example: '40°42.767\'N, 74°0.360\'W' },
];

export default function CoordinateInput({ value, onChange, format = 'dd', showMap = false }) {
  const [latitude, setLatitude] = useState('');
  const [longitude, setLongitude] = useState('');
  const [inputFormat, setInputFormat] = useState(format);

  // For DMS format
  const [latDeg, setLatDeg] = useState('');
  const [latMin, setLatMin] = useState('');
  const [latSec, setLatSec] = useState('');
  const [latDir, setLatDir] = useState('N');
  const [lonDeg, setLonDeg] = useState('');
  const [lonMin, setLonMin] = useState('');
  const [lonSec, setLonSec] = useState('');
  const [lonDir, setLonDir] = useState('W');

  useEffect(() => {
    if (value) {
      parseValue(value);
    }
  }, [value]);

  const parseValue = (val) => {
    // Try to parse the incoming value
    if (typeof val === 'object' && val.latitude && val.longitude) {
      setLatitude(String(val.latitude));
      setLongitude(String(val.longitude));
    } else if (typeof val === 'string') {
      const parts = val.split(',').map(s => s.trim());
      if (parts.length === 2) {
        setLatitude(parts[0]);
        setLongitude(parts[1]);
      }
    }
  };

  const handleDecimalChange = () => {
    const coord = {
      latitude: parseFloat(latitude) || 0,
      longitude: parseFloat(longitude) || 0,
      format: 'dd',
      raw: `${latitude}, ${longitude}`
    };
    onChange(coord);
  };

  const handleDMSChange = () => {
    // Convert DMS to decimal
    const latDecimal = dmsToDecimal(latDeg, latMin, latSec, latDir);
    const lonDecimal = dmsToDecimal(lonDeg, lonMin, lonSec, lonDir);

    const coord = {
      latitude: latDecimal,
      longitude: lonDecimal,
      format: 'dms',
      raw: `${latDeg}°${latMin}'${latSec}"${latDir}, ${lonDeg}°${lonMin}'${lonSec}"${lonDir}`
    };
    onChange(coord);
  };

  const dmsToDecimal = (deg, min, sec, dir) => {
    const d = parseFloat(deg) || 0;
    const m = parseFloat(min) || 0;
    const s = parseFloat(sec) || 0;
    let decimal = d + m / 60 + s / 3600;
    if (dir === 'S' || dir === 'W') {
      decimal = -decimal;
    }
    return decimal;
  };

  return (
    <div className="coordinate-input-container">
      <div className="format-selector">
        <label>Format:</label>
        <select value={inputFormat} onChange={(e) => setInputFormat(e.target.value)}>
          {COORDINATE_FORMATS.map(f => (
            <option key={f.id} value={f.id}>{f.label}</option>
          ))}
        </select>
        <span className="format-example">e.g., {COORDINATE_FORMATS.find(f => f.id === inputFormat)?.example}</span>
      </div>

      {inputFormat === 'dd' && (
        <div className="decimal-input">
          <div className="coord-field">
            <label>Latitude:</label>
            <input
              type="number"
              step="0.0001"
              value={latitude}
              onChange={(e) => setLatitude(e.target.value)}
              onBlur={handleDecimalChange}
              placeholder="-90 to 90"
              min="-90"
              max="90"
            />
          </div>
          <div className="coord-field">
            <label>Longitude:</label>
            <input
              type="number"
              step="0.0001"
              value={longitude}
              onChange={(e) => setLongitude(e.target.value)}
              onBlur={handleDecimalChange}
              placeholder="-180 to 180"
              min="-180"
              max="180"
            />
          </div>
        </div>
      )}

      {inputFormat === 'dms' && (
        <div className="dms-input">
          <div className="dms-row">
            <label>Latitude:</label>
            <input type="number" value={latDeg} onChange={(e) => setLatDeg(e.target.value)} placeholder="°" className="deg" />
            <span>°</span>
            <input type="number" value={latMin} onChange={(e) => setLatMin(e.target.value)} placeholder="'" className="min" />
            <span>'</span>
            <input type="number" step="0.01" value={latSec} onChange={(e) => setLatSec(e.target.value)} placeholder='"' className="sec" />
            <span>"</span>
            <select value={latDir} onChange={(e) => setLatDir(e.target.value)}>
              <option value="N">N</option>
              <option value="S">S</option>
            </select>
          </div>
          <div className="dms-row">
            <label>Longitude:</label>
            <input type="number" value={lonDeg} onChange={(e) => setLonDeg(e.target.value)} placeholder="°" className="deg" />
            <span>°</span>
            <input type="number" value={lonMin} onChange={(e) => setLonMin(e.target.value)} placeholder="'" className="min" />
            <span>'</span>
            <input type="number" step="0.01" value={lonSec} onChange={(e) => setLonSec(e.target.value)} placeholder='"' className="sec" />
            <span>"</span>
            <select value={lonDir} onChange={(e) => setLonDir(e.target.value)}>
              <option value="E">E</option>
              <option value="W">W</option>
            </select>
          </div>
          <button type="button" onClick={handleDMSChange} className="convert-btn">
            Update Coordinates
          </button>
        </div>
      )}

      {showMap && latitude && longitude && (
        <div className="map-preview">
          <iframe
            title="Location Preview"
            width="100%"
            height="200"
            frameBorder="0"
            src={`https://www.openstreetmap.org/export/embed.html?bbox=${parseFloat(longitude)-0.01},${parseFloat(latitude)-0.01},${parseFloat(longitude)+0.01},${parseFloat(latitude)+0.01}&layer=mapnik&marker=${latitude},${longitude}`}
          />
        </div>
      )}
    </div>
  );
}
```

### 3.2 Geography Grading Logic

**File: `assignment_grader.py`** - Add:

```python
from math import radians, sin, cos, sqrt, atan2

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points in kilometers.
    """
    R = 6371  # Earth's radius in kilometers

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))

    return R * c


def grade_coordinate_question(expected: dict, student: dict, tolerance_km: float = 50) -> dict:
    """
    Grade a coordinate answer with tolerance for distance.

    Args:
        expected: {'latitude': float, 'longitude': float}
        student: Same structure
        tolerance_km: Maximum distance in km for correct answer

    Returns:
        Grading result
    """
    result = {
        'question_type': 'coordinates',
        'correct': False,
        'feedback': []
    }

    try:
        exp_lat = float(expected.get('latitude', 0))
        exp_lon = float(expected.get('longitude', 0))
        stu_lat = float(student.get('latitude', 0))
        stu_lon = float(student.get('longitude', 0))

        distance = haversine_distance(exp_lat, exp_lon, stu_lat, stu_lon)
        result['distance_km'] = round(distance, 2)

        if distance <= tolerance_km:
            result['correct'] = True
            if distance < 1:
                result['feedback'].append('Excellent! Your coordinates are very precise.')
            else:
                result['feedback'].append(f'Correct! Your answer is within {distance:.1f} km of the expected location.')
        else:
            result['correct'] = False
            result['feedback'].append(f'Your coordinates are {distance:.1f} km from the expected location (tolerance: {tolerance_km} km).')

            # Provide hints about direction
            if stu_lat < exp_lat:
                result['feedback'].append('Hint: The correct location is further north.')
            elif stu_lat > exp_lat:
                result['feedback'].append('Hint: The correct location is further south.')

            if stu_lon < exp_lon:
                result['feedback'].append('Hint: The correct location is further east.')
            elif stu_lon > exp_lon:
                result['feedback'].append('Hint: The correct location is further west.')

    except (ValueError, TypeError) as e:
        result['feedback'].append(f'Could not parse coordinates: {str(e)}')

    return result


def grade_place_name(expected_names: list, student_answer: str) -> dict:
    """
    Grade a place name question, accepting common alternatives.

    Args:
        expected_names: List of acceptable names ['United Kingdom', 'UK', 'Britain']
        student_answer: Student's response
    """
    result = {
        'question_type': 'place_name',
        'correct': False,
        'feedback': []
    }

    student_clean = student_answer.strip().lower()

    for name in expected_names:
        if name.lower() == student_clean:
            result['correct'] = True
            result['feedback'].append('Correct!')
            return result

    # Check for partial matches
    for name in expected_names:
        if name.lower() in student_clean or student_clean in name.lower():
            result['correct'] = True
            result['feedback'].append(f'Correct! (Accepted as matching "{name}")')
            return result

    result['feedback'].append(f'Incorrect. Expected one of: {", ".join(expected_names)}')
    return result
```

---

## Phase 4: Subject-Specific Lesson Templates

### 4.1 Create Subject Templates JSON

**New File: `backend/data/lesson_templates.json`**
```json
{
  "math": {
    "activity_types": [
      {
        "id": "problem_solving",
        "name": "Problem-Solving Workshop",
        "description": "Students work through progressively challenging problems",
        "structure": [
          "Warm-up problem (5 min)",
          "Guided practice with teacher (10 min)",
          "Partner work on similar problems (15 min)",
          "Challenge problem for early finishers",
          "Class discussion of strategies (5 min)"
        ],
        "materials": ["Whiteboards", "Markers", "Problem sets", "Calculator (if appropriate)"]
      },
      {
        "id": "manipulatives",
        "name": "Hands-On Manipulatives",
        "description": "Concrete objects to explore abstract concepts",
        "structure": [
          "Introduction of concept (5 min)",
          "Distribute manipulatives and explore (10 min)",
          "Guided activity with manipulatives (15 min)",
          "Connect to abstract representation (10 min)",
          "Practice without manipulatives (10 min)"
        ],
        "materials": ["Algebra tiles", "Fraction bars", "Base-ten blocks", "Geometric solids"]
      },
      {
        "id": "real_world",
        "name": "Real-World Application",
        "description": "Connect math concepts to authentic situations",
        "structure": [
          "Present real-world scenario (5 min)",
          "Identify mathematical elements (5 min)",
          "Model solution process (10 min)",
          "Students solve similar scenario (15 min)",
          "Present and compare approaches (10 min)"
        ],
        "materials": ["Scenario cards", "Data sets", "Calculators", "Graph paper"]
      },
      {
        "id": "math_talk",
        "name": "Number Talk / Math Talk",
        "description": "Discussion-based mental math strategies",
        "structure": [
          "Present problem (no paper/pencil)",
          "Think time (1-2 min)",
          "Students share strategies verbally",
          "Record strategies on board",
          "Compare efficiency of methods"
        ],
        "materials": ["Whiteboard/projector", "Number talk prompt"]
      }
    ],
    "differentiation_strategies": {
      "struggling": [
        "Provide manipulatives for concrete representation",
        "Use graphic organizers for problem-solving steps",
        "Reduce number of problems, increase depth",
        "Pair with supportive partner",
        "Allow calculator for computation when focusing on concepts"
      ],
      "advanced": [
        "Extend with multi-step problems",
        "Ask students to create their own problems",
        "Explore multiple solution methods",
        "Connect to higher-level concepts",
        "Lead peer tutoring sessions"
      ]
    }
  },

  "science": {
    "activity_types": [
      {
        "id": "lab_investigation",
        "name": "Laboratory Investigation",
        "description": "Hands-on experiment following scientific method",
        "structure": [
          "Pre-lab discussion and safety (10 min)",
          "Review procedure and hypothesis (5 min)",
          "Conduct experiment (20-30 min)",
          "Record observations and data",
          "Clean up and post-lab discussion (10 min)"
        ],
        "materials": ["Lab materials (specify)", "Lab notebooks", "Safety equipment", "Data tables"]
      },
      {
        "id": "inquiry_based",
        "name": "Inquiry-Based Learning",
        "description": "Student-driven investigation",
        "structure": [
          "Present phenomenon or problem (5 min)",
          "Students generate questions (5 min)",
          "Design investigation (10 min)",
          "Conduct investigation (20 min)",
          "Share findings and discuss (10 min)"
        ],
        "materials": ["Open-ended materials", "Research resources", "Documentation tools"]
      },
      {
        "id": "model_building",
        "name": "Scientific Modeling",
        "description": "Create and revise models to explain phenomena",
        "structure": [
          "Observe phenomenon (5 min)",
          "Create initial model (10 min)",
          "Share and critique models (10 min)",
          "Gather new information (10 min)",
          "Revise models (10 min)"
        ],
        "materials": ["Modeling materials", "Anchor phenomenon", "Information sources"]
      },
      {
        "id": "data_analysis",
        "name": "Data Analysis Activity",
        "description": "Work with real scientific data sets",
        "structure": [
          "Introduce data context (5 min)",
          "Explore data set (10 min)",
          "Identify patterns and trends (10 min)",
          "Draw evidence-based conclusions (10 min)",
          "Present findings (10 min)"
        ],
        "materials": ["Data sets", "Graph paper or software", "Calculators", "Analysis guides"]
      }
    ],
    "differentiation_strategies": {
      "struggling": [
        "Provide structured data tables",
        "Use sentence stems for claims and evidence",
        "Pre-label diagrams for completion",
        "Reduce variables in experiments",
        "Partner with peer mentor"
      ],
      "advanced": [
        "Design own investigation",
        "Analyze additional variables",
        "Research real-world applications",
        "Present findings to class",
        "Mentor struggling peers"
      ]
    }
  },

  "geography": {
    "activity_types": [
      {
        "id": "map_skills",
        "name": "Map Skills Workshop",
        "description": "Practice reading and creating maps",
        "structure": [
          "Review map elements (5 min)",
          "Guided practice with sample map (10 min)",
          "Partner map reading challenge (15 min)",
          "Create or modify a map (15 min)",
          "Share and discuss (5 min)"
        ],
        "materials": ["Various maps (physical, political, thematic)", "Blank maps", "Colored pencils", "Atlas"]
      },
      {
        "id": "geo_inquiry",
        "name": "Geographic Inquiry",
        "description": "Investigate geographic questions",
        "structure": [
          "Present geographic question (5 min)",
          "Examine multiple sources (15 min)",
          "Analyze spatial patterns (10 min)",
          "Form conclusions (10 min)",
          "Discuss implications (10 min)"
        ],
        "materials": ["Maps", "Data sources", "Geographic images", "Analysis frameworks"]
      },
      {
        "id": "virtual_field_trip",
        "name": "Virtual Field Trip",
        "description": "Explore locations using digital tools",
        "structure": [
          "Introduction to location (5 min)",
          "Guided exploration (15 min)",
          "Scavenger hunt or observation task (15 min)",
          "Compare to local geography (10 min)",
          "Reflection and discussion (5 min)"
        ],
        "materials": ["Google Earth/Maps", "Virtual tour links", "Observation worksheet", "Devices"]
      },
      {
        "id": "case_study",
        "name": "Geographic Case Study",
        "description": "Deep dive into specific location or issue",
        "structure": [
          "Introduce case (5 min)",
          "Provide background materials (10 min)",
          "Group analysis (15 min)",
          "Present findings (10 min)",
          "Connect to broader themes (10 min)"
        ],
        "materials": ["Case study materials", "Maps of region", "Supplementary data", "Presentation tools"]
      }
    ],
    "differentiation_strategies": {
      "struggling": [
        "Provide labeled maps for reference",
        "Use graphic organizers for note-taking",
        "Pre-select key information sources",
        "Pair with geography mentor",
        "Allow verbal responses to map questions"
      ],
      "advanced": [
        "Analyze multiple map projections",
        "Create thematic maps from raw data",
        "Research current geographic issues",
        "Compare regions independently",
        "Lead class discussions"
      ]
    }
  }
}
```

### 4.2 Update Lesson Plan Generator

**File: `backend/routes/planner_routes.py`** - Modify `generate_lesson_plan` to use templates:

```python
# Add at top of file
import json
from pathlib import Path

def load_lesson_templates():
    """Load subject-specific lesson templates."""
    template_path = Path(__file__).parent.parent / 'data' / 'lesson_templates.json'
    if template_path.exists():
        with open(template_path) as f:
            return json.load(f)
    return {}

# Modify the generate_lesson_plan function to include templates
@planner_bp.route('/api/generate-lesson-plan', methods=['POST'])
def generate_lesson_plan():
    # ... existing code ...

    # Load templates for the subject
    templates = load_lesson_templates()
    subject_templates = templates.get(subject.lower().replace(' ', '_'), {})

    # Include in prompt
    template_info = ""
    if subject_templates:
        activity_types = subject_templates.get('activity_types', [])
        template_info = f"""

Available activity templates for {subject}:
{json.dumps(activity_types, indent=2)}

Differentiation strategies:
{json.dumps(subject_templates.get('differentiation_strategies', {}), indent=2)}

Please incorporate appropriate activity types from these templates.
"""

    prompt = f"""
Generate a comprehensive lesson plan for:
- Subject: {subject}
- Grade Level: {grade_level}
- Standard: {benchmark_code} - {benchmark_text}
- Duration: {duration} minutes
{template_info}

{existing_prompt_content}
"""

    # ... rest of function ...
```

---

## Phase 5: Update App.jsx for Question Types

### 5.1 Add Question Type Selector to Builder

**File: `frontend/src/App.jsx`** - Add to Builder tab:

```jsx
// Add imports at top (if using separate component files)
// import MathInput from './components/MathInput';
// import DataTable from './components/DataTable';
// import CoordinateInput from './components/CoordinateInput';

// Add to state (around line 45-50)
const [questionType, setQuestionType] = useState('text');
const [currentMathQuestion, setCurrentMathQuestion] = useState({
  equation: '',
  correctAnswer: '',
  acceptEquivalent: true,
  showWork: false
});
const [currentDataTable, setCurrentDataTable] = useState(null);
const [currentCoordinate, setCurrentCoordinate] = useState(null);

// Add question type selector in Builder panel (where questions are created)
<div className="question-type-selector">
  <label>Question Type:</label>
  <select value={questionType} onChange={(e) => setQuestionType(e.target.value)}>
    <option value="text">Text / Essay</option>
    <option value="math">Math Equation</option>
    <option value="data_table">Data Table (Science)</option>
    <option value="coordinates">Coordinates (Geography)</option>
    <option value="multiple_choice">Multiple Choice</option>
  </select>
</div>

{questionType === 'text' && (
  <div className="text-question">
    {/* Existing text question UI */}
  </div>
)}

{questionType === 'math' && (
  <div className="math-question">
    <h4>Math Question</h4>
    {/* MathInput component for question */}
    {/* MathInput component for answer */}
    {/* Checkboxes for equivalent forms and show work */}
  </div>
)}

{questionType === 'data_table' && (
  <div className="data-table-question">
    <h4>Data Table Question</h4>
    <p>Create a data table that students will complete:</p>
    {/* DataTable component */}
    <div className="tolerance-setting">
      <label>Numerical tolerance: </label>
      <input type="number" defaultValue={5} min={0} max={50} /> %
    </div>
  </div>
)}

{questionType === 'coordinates' && (
  <div className="coordinate-question">
    <h4>Geographic Coordinate Question</h4>
    <p>Students will identify the coordinates of a location:</p>
    {/* CoordinateInput component */}
    <div className="tolerance-setting">
      <label>Distance tolerance: </label>
      <input type="number" defaultValue={50} min={1} max={500} /> km
    </div>
  </div>
)}
```

---

## Implementation Priority

1. **Week 1**: Math support (highest demand from teachers)
   - MathInput component
   - KaTeX integration
   - SymPy backend grading

2. **Week 2**: Science data tables
   - DataTable component
   - Tolerance-based grading
   - Lab report integration

3. **Week 3**: Geography coordinates
   - CoordinateInput component
   - Distance-based grading
   - Map preview

4. **Week 4**: Lesson templates
   - Subject-specific templates
   - Activity type selection
   - Enhanced differentiation

---

## Testing Checklist

- [ ] Math equations render correctly in builder
- [ ] LaTeX input parses without errors
- [ ] Equivalent math expressions are recognized
- [ ] Data tables save/load correctly
- [ ] Tolerance grading works for numerical values
- [ ] Coordinate input accepts multiple formats
- [ ] Distance calculation is accurate
- [ ] Lesson templates load for each subject
- [ ] Export to Word preserves math formatting
