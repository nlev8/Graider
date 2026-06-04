import { describe, it, expect } from 'vitest';
import {
  normalizeText,
  htmlToPlainText,
  highlightTextInHtml,
  removeHighlightFromHtml,
  textToRichHtml,
  removeAllHighlightsFromHtml,
} from '../htmlHighlight';

// Characterization net for the App.jsx -> utils/htmlHighlight.js extraction (slice 13).
// These are PURE string functions; tests pin the load-bearing observable behavior. The
// byte-verbatim workflow check proves they equal the original App.jsx definitions.
describe('htmlHighlight (pure marker/highlight utilities)', () => {
  it('removeAllHighlightsFromHtml strips marker spans but keeps their text and non-marker markup', () => {
    expect(removeAllHighlightsFromHtml('a<span data-marker-id="x">b</span>c')).toBe('abc');
    expect(removeAllHighlightsFromHtml('<b>keep</b>')).toBe('<b>keep</b>');
  });

  it('removeAllHighlightsFromHtml passes through falsy input (the !html guard)', () => {
    expect(removeAllHighlightsFromHtml('')).toBe('');
    expect(removeAllHighlightsFromHtml(null)).toBe(null);
  });

  it('highlightTextInHtml wraps the matched text in a span carrying the marker id', () => {
    const out = highlightTextInHtml('<p>hello world</p>', 'world', '#ffeeee', 'm1');
    expect(out).toContain('data-marker-id="m1');
    expect(htmlToPlainText(out)).toContain('hello world'); // text content preserved
  });

  it('removeHighlightFromHtml removes a previously-applied highlight by marker id', () => {
    const highlighted = highlightTextInHtml('<p>alpha beta</p>', 'beta', '#eef', 'mk');
    expect(highlighted).toContain('data-marker-id="mk');
    const cleaned = removeHighlightFromHtml(highlighted, 'mk');
    expect(cleaned).not.toContain('data-marker-id="mk"');
    expect(htmlToPlainText(cleaned)).toContain('alpha beta');
  });

  it('htmlToPlainText strips tags and decodes entities', () => {
    const plain = htmlToPlainText('<p>Hi &amp; <b>bye</b></p>');
    expect(plain).not.toContain('<');
    expect(plain).toContain('Hi');
    expect(plain).toContain('&'); // &amp; decoded
    expect(plain).toContain('bye');
  });

  it('textToRichHtml turns plain text into HTML that preserves the text', () => {
    const html = textToRichHtml('First line');
    expect(typeof html).toBe('string');
    expect(htmlToPlainText(html)).toContain('First line');
  });

  it('normalizeText returns a string and is stable on already-normalized input', () => {
    const once = normalizeText('hello world');
    expect(typeof once).toBe('string');
    expect(normalizeText(once)).toBe(once); // idempotent on its own output
  });
});
