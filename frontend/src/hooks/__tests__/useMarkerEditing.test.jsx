import { renderHook } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useMarkerEditing } from '../useMarkerEditing';

// Characterization net for the App.jsx -> useMarkerEditing extraction (slice 15).
// Pins the add-selected-as-marker branches (start/exclude/too-short) and removeMarker's
// remove-all + re-apply flow. window.getSelection is mocked to supply the selected text.
const COLORS = {
  start: { bg: 'g', border: 'gb' },
  end: { bg: 'r', border: 'rb' },
  exclude: { bg: 'o', border: 'ob' },
};

function setup(over = {}) {
  const fns = {};
  for (const s of ['addToast', 'setAssignment', 'setDocEditorModal', 'setImportedDoc']) fns[s] = vi.fn();
  const props = {
    docHtmlRef: { current: null },
    highlighterMode: 'start',
    assignment: { customMarkers: [], excludeMarkers: [] },
    docEditorModal: { editedHtml: '<p>foo bar baz</p>' },
    importedDoc: { html: '' },
    HIGHLIGHT_COLORS: COLORS,
    applyAllHighlights: vi.fn(() => 'REAPPLIED_HTML'),
    ...fns,
    ...over,
  };
  const { result } = renderHook(() => useMarkerEditing(props));
  return { result, props };
}

function mockSelection(text) {
  return vi.spyOn(window, 'getSelection').mockReturnValue({ toString: () => text });
}

describe('useMarkerEditing', () => {
  let sel;
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => sel && sel.mockRestore());

  it('addSelectedAsMarker (start): adds a start marker + highlights + toasts', () => {
    sel = mockSelection('foo');
    const { result, props } = setup();
    result.current.addSelectedAsMarker();
    expect(props.setAssignment).toHaveBeenCalledWith(expect.objectContaining({ customMarkers: ['foo'] }));
    expect(props.setDocEditorModal).toHaveBeenCalled();
    expect(props.addToast).toHaveBeenCalledWith('Start marker added (green)', 'success');
  });

  it('addSelectedAsMarker (exclude): adds an exclude marker', () => {
    sel = mockSelection('baz');
    const { result, props } = setup({ highlighterMode: 'exclude' });
    result.current.addSelectedAsMarker();
    expect(props.setAssignment).toHaveBeenCalledWith(expect.objectContaining({ excludeMarkers: ['baz'] }));
    expect(props.addToast).toHaveBeenCalledWith(expect.stringContaining('Exclude marker added'), 'success');
  });

  it('addSelectedAsMarker: warns when the selection is too short', () => {
    sel = mockSelection('fo'); // <= 2 chars
    const { result, props } = setup();
    result.current.addSelectedAsMarker();
    expect(props.addToast).toHaveBeenCalledWith('Please select more text (at least 3 characters)', 'warning');
    expect(props.setAssignment).not.toHaveBeenCalled();
  });

  it('removeMarker: filters the marker and re-applies remaining highlights to both docs', () => {
    const { result, props } = setup({ assignment: { customMarkers: ['foo', 'bar'], excludeMarkers: [] } });
    result.current.removeMarker('foo', 0);
    // applyAllHighlights called with the cleaned html + remaining markers
    expect(props.applyAllHighlights).toHaveBeenCalledWith(expect.any(String), ['bar'], []);
    expect(props.setAssignment).toHaveBeenCalledWith(expect.objectContaining({ customMarkers: ['bar'] }));
    expect(props.setDocEditorModal).toHaveBeenCalledWith(expect.objectContaining({ editedHtml: 'REAPPLIED_HTML' }));
    expect(props.setImportedDoc).toHaveBeenCalledWith(expect.objectContaining({ html: 'REAPPLIED_HTML' }));
  });
});
