import React, { useState, useEffect, useRef } from 'react';
import 'katex/dist/katex.min.css';
import { InlineMath, BlockMath } from 'react-katex';
import './MathInput.css';

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

export default function MathInput({ value, onChange, placeholder, block = false, label, disabled, onInputFocus, onInputBlur }) {
  const [latex, setLatex] = useState(value || '');
  const [error, setError] = useState(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    setLatex(value || '');
  }, [value]);

  const handleChange = (e) => {
    const newValue = e.target.value;
    setLatex(newValue);
    setError(null);
    onChange(newValue);
  };

  const MathComponent = block ? BlockMath : InlineMath;

  return (
    <div className="math-input-container">
      {label && <label className="math-input-label">{label}</label>}

      <textarea
        ref={textareaRef}
        className="latex-input"
        value={latex}
        onChange={handleChange}
        onFocus={() => onInputFocus?.(textareaRef.current)}
        onBlur={() => onInputBlur?.()}
        placeholder={placeholder || 'Type your math answer here'}
        rows={2}
        disabled={disabled}
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
