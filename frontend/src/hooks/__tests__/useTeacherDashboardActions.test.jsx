import { renderHook } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('../../services/api', () => ({
  getPublishedAssessments: vi.fn(),
  getSharedResources: vi.fn(),
  getTeacherTags: vi.fn(),
  deleteSharedResource: vi.fn(),
  deleteSharedResourcesBulk: vi.fn(),
  getContentSubmissions: vi.fn(),
  getAssessmentResults: vi.fn(),
  getInProgressDrafts: vi.fn(),
  toggleAssessmentStatus: vi.fn(),
  deletePublishedAssessment: vi.fn(),
}));

import * as api from '../../services/api';
import { useTeacherDashboardActions } from '../useTeacherDashboardActions';

// Characterization net for the App.jsx -> useTeacherDashboardActions extraction (slice 11).
// Pins the load-bearing behavior, including the INTERNAL cross-calls (toggle -> the 3
// fetchers; fetchAssessmentResults -> fetchContentSubmissions) that resolve in the factory.
function setup(over = {}) {
  const fns = {};
  for (const s of [
    'addToast', 'setLoadingPublished', 'setPublishedAssessments', 'setLoadingSharedResources',
    'setSharedResources', 'setAllTeacherTags', 'setContentSubmissionsGroups', 'setLoadingResults',
    'setSelectedAssessmentResults', 'setInProgressDrafts',
  ]) fns[s] = vi.fn();
  const props = { selectedAssessmentResults: null, ...fns, ...over };
  const { result } = renderHook(() => useTeacherDashboardActions(props));
  return { result, props };
}

describe('useTeacherDashboardActions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getPublishedAssessments.mockResolvedValue({ assessments: [{ join_code: 'A' }] });
    api.getSharedResources.mockResolvedValue({ resources: [{ id: 1 }] });
    api.getTeacherTags.mockResolvedValue({ tags: ['t'] });
    api.deleteSharedResource.mockResolvedValue({ success: true });
    api.getAssessmentResults.mockResolvedValue({ title: 'X', submissions: [], stats: {} });
    api.getContentSubmissions.mockResolvedValue({ students: [] });
    api.getInProgressDrafts.mockResolvedValue({ drafts: [] });
    api.toggleAssessmentStatus.mockResolvedValue({ success: true, is_active: true });
    api.deletePublishedAssessment.mockResolvedValue({ success: true });
  });

  it('fetchPublishedAssessments: toggles loading and stores the list', async () => {
    const { result, props } = setup();
    await result.current.fetchPublishedAssessments();
    expect(props.setLoadingPublished).toHaveBeenNthCalledWith(1, true);
    expect(props.setPublishedAssessments).toHaveBeenCalledWith([{ join_code: 'A' }]);
    expect(props.setLoadingPublished).toHaveBeenLastCalledWith(false);
  });

  it('fetchSharedResources: stores the resources', async () => {
    const { result, props } = setup();
    await result.current.fetchSharedResources();
    expect(props.setSharedResources).toHaveBeenCalledWith([{ id: 1 }]);
  });

  it('handleDeleteSharedResource: filters the deleted id and toasts', async () => {
    const { result, props } = setup();
    await result.current.handleDeleteSharedResource(7, 'Doc');
    expect(api.deleteSharedResource).toHaveBeenCalledWith(7);
    const updater = props.setSharedResources.mock.calls[0][0];
    expect(updater([{ id: 7 }, { id: 9 }])).toEqual([{ id: 9 }]);
    expect(props.addToast).toHaveBeenCalledWith('Deleted "Doc"', 'success');
  });

  it('fetchAssessmentResults (short join code): stores results, clears drafts/submissions', async () => {
    const { result, props } = setup();
    await result.current.fetchAssessmentResults('ABC123'); // <= 10 chars
    expect(props.setSelectedAssessmentResults).toHaveBeenCalledWith(
      expect.objectContaining({ joinCode: 'ABC123', title: 'X' }),
    );
    expect(props.setContentSubmissionsGroups).toHaveBeenCalledWith([]);
    expect(props.setInProgressDrafts).toHaveBeenCalledWith([]);
    expect(api.getContentSubmissions).not.toHaveBeenCalled(); // short code -> no content fetch
  });

  it('fetchAssessmentResults (UUID join code): triggers the internal content + drafts fetch', async () => {
    const { result } = setup();
    await result.current.fetchAssessmentResults('00000000-0000-0000-0000-000000000000');
    expect(api.getContentSubmissions).toHaveBeenCalled(); // internal cross-call resolved
    expect(api.getInProgressDrafts).toHaveBeenCalled();
  });

  it('toggleAssessmentStatus: on success re-runs the 3 fetchers (internal cross-calls)', async () => {
    const { result, props } = setup();
    await result.current.toggleAssessmentStatus('A');
    expect(props.addToast).toHaveBeenCalledWith('Assessment activated', 'success');
    expect(api.getPublishedAssessments).toHaveBeenCalled();
    expect(api.getSharedResources).toHaveBeenCalled();
    expect(api.getTeacherTags).toHaveBeenCalled();
  });

  it('deletePublishedAssessment: confirm-gated; on confirm filters + clears selection', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    const { result, props } = setup({ selectedAssessmentResults: { joinCode: 'A' } });
    await result.current.deletePublishedAssessment('A');
    expect(api.deletePublishedAssessment).toHaveBeenCalledWith('A');
    const updater = props.setPublishedAssessments.mock.calls[0][0];
    expect(updater([{ join_code: 'A' }, { join_code: 'B' }])).toEqual([{ join_code: 'B' }]);
    expect(props.setSelectedAssessmentResults).toHaveBeenCalledWith(null); // selection cleared
    confirmSpy.mockRestore();
  });

  it('deletePublishedAssessment: aborts when not confirmed', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);
    const { result } = setup();
    await result.current.deletePublishedAssessment('A');
    expect(api.deletePublishedAssessment).not.toHaveBeenCalled();
    confirmSpy.mockRestore();
  });
});
