import React, { useState, useEffect } from 'react';
import 'katex/dist/katex.min.css';
import { InlineMath, BlockMath } from 'react-katex';
import './MathInput.css';

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

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error) {
    if (this.props.onError) {
      this.props.onError(error);
    }
  }

  componentDidUpdate(prevProps) {
    if (prevProps.latex !== this.props.latex) {
      this.setState({ hasError: false });
    }
  }

  render() {
    if (this.state.hasError) {
      return null;
    }
    return this.props.children;
  }
}

export default function MathInput({ value, onChange, placeholder, block = false, label }) {
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
      {label && <label className="math-input-label">{label}</label>}

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
            <ErrorBoundary onError={(e) => setError(e.message)} latex={latex}>
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
