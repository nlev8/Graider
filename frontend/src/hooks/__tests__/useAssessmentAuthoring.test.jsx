import { renderHook } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../../services/api', () => ({
  generateAssessment: vi.fn(),
  exportAssessment: vi.fn(),
  exportAssessmentForPlatform: vi.fn(),
}));
vi.mock('../../utils/standardsMismatch', () => ({
  checkRequirementsMismatch: vi.fn(() => ({ mismatch: false })),
}));

import * as api from '../../services/api';
import { useAssessmentAuthoring } from '../useAssessmentAuthoring';

// Characterization net for the App.jsx -> useAssessmentAuthoring extraction (slice 9).
// Pins the 4 authoring handlers' load-bearing behavior: generate validation + happy path,
// the points redistribution math, and the two export download paths.
function setup(over = {}) {
  const fns = {
    addToast: vi.fn(),
    setAssessmentLoading: vi.fn(),
    setGeneratedAssessment: vi.fn(),
    setAssessmentAnswers: vi.fn(),
  };
  const props = {
    config: { subject: 'Math', grade_level: '5', teacher_name: 'T' },
    selectedStandards: ['CCSS.1'],
    uploadedDocs: [],
    unitConfig: { requirements: '' },
    standards: [{ code: 'CCSS.1', benchmark: 'b' }],
    assessmentConfig: { title: 'Quiz', type: 'quiz', sectionCategories: { mcq: 5 } },
    selectedSources: [],
    globalAINotes: '',
    contentOnly: false,
    generatedAssessment: null,
    ...fns,
    ...over,
  };
  const { result } = renderHook(() => useAssessmentAuthoring(props));
  return { result, props };
}

describe('useAssessmentAuthoring', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.generateAssessment.mockResolvedValue({ assessment: { sections: [], total_points: 100 } });
    api.exportAssessment.mockResolvedValue({ document: 'BASE64', filename: 'a.docx' });
    api.exportAssessmentForPlatform.mockResolvedValue({ document: 'BASE64', filename: 'a.csv', format: 'csv' });
  });

  it('generate: blocks (warns, no API) when subject is missing', async () => {
    const { result, props } = setup({ config: { subject: '', grade_level: '5' } });
    await result.current.generateAssessmentHandler();
    expect(props.addToast).toHaveBeenCalledWith(expect.stringContaining('subject'), 'warning');
    expect(api.generateAssessment).not.toHaveBeenCalled();
  });

  it('generate: blocks when no standards and no uploaded docs', async () => {
    const { result, props } = setup({ selectedStandards: [], uploadedDocs: [] });
    await result.current.generateAssessmentHandler();
    expect(props.addToast).toHaveBeenCalledWith(expect.stringContaining('standard'), 'warning');
    expect(api.generateAssessment).not.toHaveBeenCalled();
  });

  it('generate: happy path calls the API and stores the assessment', async () => {
    const { result, props } = setup();
    await result.current.generateAssessmentHandler();
    expect(api.generateAssessment).toHaveBeenCalledTimes(1);
    // handler annotates data.assessment with a derived time_limit before storing it
    expect(props.setGeneratedAssessment).toHaveBeenCalledWith(
      expect.objectContaining({ sections: [], total_points: 100 }),
    );
    expect(props.setAssessmentAnswers).toHaveBeenCalledWith({});
    expect(props.addToast).toHaveBeenCalledWith('Assessment generated successfully!', 'success');
    expect(props.setAssessmentLoading).toHaveBeenLastCalledWith(false); // finally
  });

  it('redistributePoints: rescales question points to the new total', () => {
    const generatedAssessment = {
      total_points: 100,
      sections: [{ questions: [{ points: 50 }, { points: 50 }] }],
    };
    const { result, props } = setup({ generatedAssessment });
    result.current.redistributePoints(50);
    const arg = props.setGeneratedAssessment.mock.calls[0][0];
    expect(arg.total_points).toBe(50);
    const total = arg.sections.reduce((s, sec) => s + sec.questions.reduce((a, q) => a + q.points, 0), 0);
    expect(total).toBe(50); // points sum exactly to the new total
  });

  it('export: no-op without a generated assessment', async () => {
    const { result } = setup({ generatedAssessment: null });
    await result.current.exportAssessmentHandler();
    expect(api.exportAssessment).not.toHaveBeenCalled();
  });

  // Spy createElement AFTER renderHook (renderHook needs the real one for its container);
  // return a fake anchor only for 'a', delegate everything else to the real createElement.
  function spyAnchor() {
    const click = vi.fn();
    const real = document.createElement.bind(document);
    const spy = vi.spyOn(document, 'createElement').mockImplementation((tag) =>
      tag === 'a' ? { click, set href(v) {}, set download(v) {} } : real(tag),
    );
    return { click, spy };
  }

  it('export: downloads the .docx when an assessment exists', async () => {
    const { result, props } = setup({ generatedAssessment: { sections: [] } });
    const { click, spy } = spyAnchor();
    await result.current.exportAssessmentHandler(true);
    expect(api.exportAssessment).toHaveBeenCalledWith({ sections: [] }, true);
    expect(click).toHaveBeenCalled();
    expect(props.addToast).toHaveBeenCalledWith('Assessment exported!', 'success');
    spy.mockRestore();
  });

  it('exportForPlatform: calls the platform export and downloads', async () => {
    const { result, props } = setup({ generatedAssessment: { sections: [] } });
    const { click, spy } = spyAnchor();
    await result.current.exportAssessmentForPlatformHandler('canvas');
    expect(api.exportAssessmentForPlatform).toHaveBeenCalledWith({ sections: [] }, 'canvas');
    expect(click).toHaveBeenCalled();
    expect(props.addToast).toHaveBeenCalledWith('Exported for canvas!', 'success');
    spy.mockRestore();
  });
});
