import katex from 'katex';

/**
 * Render LaTeX expressions in question text to HTML using KaTeX.
 *
 * Supported delimiters (unambiguous, never collide with currency or plain text):
 *   - \(...\)  → inline math
 *   - \[...\]  → display math
 *
 * Dollar-sign delimiters ($...$, $$...$$) are NOT supported because they
 * are ambiguous with currency values and cause rendering failures when the
 * AI generates text like "$4 meters".  All $ characters are treated as
 * literal text.
 */
export function renderQuestionText(text) {
  if (!text || typeof text !== 'string') return text || '';

  // Quick check — if no backslash-paren/bracket delimiters, return plain text fast
  if (!text.includes('\\(') && !text.includes('\\[')) {
    return escapeHtml(text);
  }

  let result = '';
  let i = 0;

  while (i < text.length) {
    // Check for \[ (display math)
    if (text[i] === '\\' && text[i + 1] === '[') {
      const closeIdx = text.indexOf('\\]', i + 2);
      if (closeIdx !== -1) {
        const latex = text.slice(i + 2, closeIdx);
        result += renderKatex(latex, true);
        i = closeIdx + 2;
        continue;
      }
    }

    // Check for \( (inline math)
    if (text[i] === '\\' && text[i + 1] === '(') {
      const closeIdx = text.indexOf('\\)', i + 2);
      if (closeIdx !== -1) {
        const latex = text.slice(i + 2, closeIdx);
        result += renderKatex(latex, false);
        i = closeIdx + 2;
        continue;
      }
    }

    result += escapeHtml(text[i]);
    i++;
  }

  return result;
}

function renderKatex(latex, displayMode) {
  try {
    return katex.renderToString(latex, {
      throwOnError: false,
      displayMode,
    });
  } catch {
    // On error, show the raw expression as plain text
    const delim = displayMode ? ['\\[', '\\]'] : ['\\(', '\\)'];
    return escapeHtml(delim[0] + latex + delim[1]);
  }
}

function escapeHtml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
