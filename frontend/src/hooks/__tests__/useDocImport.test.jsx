import { renderHook } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('../../services/api', () => ({ parseDocument: vi.fn(), loadAssignment: vi.fn() }));

import * as api from '../../services/api';
import { useDocImport } from '../useDocImport';

// Characterization net for the App.jsx -> useDocImport extraction (slice 16).
// Pins handleDocImport (no-file guard, happy parse, existing-name confirm) + openDocEditor.
function setup(over = {}) {
  const fns = {};
  for (const s of ['addToast', 'setImportedDoc', 'setAssignment', 'setLoadedAssignmentName', 'setDocEditorModal']) fns[s] = vi.fn();
  const props = {
    importedDoc: { text: '', html: '' },
    assignment: { title: '', customMarkers: [], excludeMarkers: [] },
    savedAssignments: [],
    applyAllHighlights: vi.fn((html) => html),
    ...fns,
    ...over,
  };
  const { result } = renderHook(() => useDocImport(props));
  return { result, props };
}
const fileEvent = (name) => ({ target: { files: [{ name }] } });

describe('useDocImport', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.parseDocument.mockResolvedValue({ text: 'BODY', html: '<p>BODY</p>' });
    api.loadAssignment.mockResolvedValue({ assignment: { title: 'Quiz', customMarkers: [], excludeMarkers: [] } });
  });
  afterEach(() => { if (window.confirm.mockRestore) window.confirm.mockRestore(); });

  it('handleDocImport: no-op when no file is selected', async () => {
    const { result } = setup();
    await result.current.handleDocImport({ target: { files: [] } });
    expect(api.parseDocument).not.toHaveBeenCalled();
  });

  it('handleDocImport: parses a new doc, sets importedDoc + opens the editor + sets title', async () => {
    const { result, props } = setup();
    await result.current.handleDocImport(fileEvent('My Quiz.docx'));
    expect(api.parseDocument).toHaveBeenCalled();
    expect(props.setImportedDoc).toHaveBeenLastCalledWith(expect.objectContaining({ text: 'BODY', html: '<p>BODY</p>', filename: 'My Quiz.docx' }));
    expect(props.setLoadedAssignmentName).toHaveBeenCalledWith('');
    expect(props.setDocEditorModal).toHaveBeenCalledWith(expect.objectContaining({ show: true, editedHtml: '<p>BODY</p>' }));
    expect(props.setAssignment).toHaveBeenCalledWith(expect.objectContaining({ title: 'My Quiz' })); // derived from filename
  });

  it('handleDocImport: an error response toasts and resets importedDoc', async () => {
    api.parseDocument.mockResolvedValue({ error: 'bad file' });
    const { result, props } = setup();
    await result.current.handleDocImport(fileEvent('x.docx'));
    expect(props.addToast).toHaveBeenCalledWith('Error parsing document: bad file', 'error');
    expect(props.setImportedDoc).toHaveBeenLastCalledWith(expect.objectContaining({ filename: '', loading: false }));
  });

  it('handleDocImport: name matches a saved assignment + cancel -> aborts the import', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);
    const { result, props } = setup({ savedAssignments: ['Quiz'] });
    await result.current.handleDocImport(fileEvent('Quiz.docx'));
    expect(api.loadAssignment).not.toHaveBeenCalled();
    expect(props.setImportedDoc).toHaveBeenLastCalledWith(expect.objectContaining({ filename: '', loading: false }));
    confirmSpy.mockRestore();
  });

  it('handleDocImport: name matches + confirm -> loads the existing assignment with the new doc', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    const { result, props } = setup({ savedAssignments: ['Quiz'] });
    await result.current.handleDocImport(fileEvent('Quiz.docx'));
    expect(api.loadAssignment).toHaveBeenCalledWith('Quiz');
    expect(props.setAssignment).toHaveBeenCalledWith(expect.objectContaining({ title: 'Quiz' }));
    expect(props.setLoadedAssignmentName).toHaveBeenCalledWith('Quiz');
    confirmSpy.mockRestore();
  });

  it('openDocEditor: no-op when nothing imported', () => {
    const { result, props } = setup({ importedDoc: { text: '', html: '' } });
    result.current.openDocEditor();
    expect(props.setDocEditorModal).not.toHaveBeenCalled();
  });

  it('openDocEditor: opens the editor with the imported html', () => {
    const { result, props } = setup({ importedDoc: { text: 'T', html: '<h1>T</h1>' } });
    result.current.openDocEditor();
    expect(props.setDocEditorModal).toHaveBeenCalledWith(expect.objectContaining({ show: true, editedHtml: '<h1>T</h1>' }));
  });
});
