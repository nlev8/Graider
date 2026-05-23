import React from 'react';
import { render } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import DocumentEditorModal from '../components/DocumentEditorModal';
vi.mock('../services/api', () => new Proxy({}, { get: () => vi.fn().mockResolvedValue({}) }));
const base = () => ({
  docEditorModal: { show: true, editedHtml: '<p>x</p>' },
  assignment: { customMarkers: [], excludeMarkers: [], modelAnswers: {}, title: 'A' },
  importedDoc: { filename: 'f.docx' },
  HIGHLIGHT_COLORS: { start: { bg: 'a', border: 'b', label: 'Start' }, end: { bg: 'a', border: 'b', label: 'End' }, exclude: { bg: 'a', border: 'b', label: 'Exclude' } },
  highlighterMode: 'start',
  docHtmlRef: { current: null },
});
const makeProps = (o = {}) => new Proxy({ ...base(), ...o }, { get(t, p) { if (p in t) return t[p]; if (typeof p === 'symbol') return undefined; return vi.fn(); }, has() { return true; } });
describe('DocumentEditorModal', () => {
  it('smoke: renders without crashing', () => {
    const { container } = render(<DocumentEditorModal {...makeProps()} />);
    expect(container).toBeTruthy();
  });
});
