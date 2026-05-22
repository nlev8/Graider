import React from 'react';
import { render } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import PlannerDashboard from '../components/PlannerDashboard';

vi.mock('../services/api', () => ({}));

const makeProps = (overrides = {}) => ({
  // data
  allTeacherTags: [],
  contentSubmissionsGroups: [],
  inProgressDrafts: [],
  loadingPublished: false,
  loadingResults: false,
  loadingSavedAssessments: false,
  loadingSharedResources: false,
  publishedAssessments: [],
  savedAssessments: [],
  selectedAssessmentResults: null,
  selectedTagFilter: '',
  sharedResources: [],
  teacherClasses: [],
  // handlers
  addToast: vi.fn(),
  deletePublishedAssessment: vi.fn(),
  deleteSavedAssessment: vi.fn(),
  fetchAssessmentResults: vi.fn(),
  fetchPublishedAssessments: vi.fn(),
  fetchSavedAssessments: vi.fn(),
  fetchSharedResources: vi.fn(),
  fetchTeacherClasses: vi.fn(),
  fetchTeacherTags: vi.fn(),
  handleDeleteAllSharedResources: vi.fn(),
  handleDeleteSharedResource: vi.fn(),
  itemMatchesTagFilter: vi.fn().mockReturnValue(true),
  loadSavedAssessment: vi.fn(),
  toggleAssessmentStatus: vi.fn(),
  renderTagRow: vi.fn(() => null),
  // setters (forwarded)
  setAttemptDrawerStudent: vi.fn(),
  setInProgressDrafts: vi.fn(),
  setPublishedAssessments: vi.fn(),
  setSelectedAssessmentResults: vi.fn(),
  setSelectedTagFilter: vi.fn(),
  setSharedResources: vi.fn(),
  ...overrides,
});

describe('PlannerDashboard', () => {
  beforeEach(() => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) });
  });

  it('smoke: renders without crashing with empty data', () => {
    const { container } = render(<PlannerDashboard {...makeProps()} />);
    expect(container.firstChild).toBeTruthy();
  });

  it('renders one published assessment via the renderTagRow render-prop', () => {
    const renderTagRow = vi.fn(() => null);
    render(<PlannerDashboard {...makeProps({
      renderTagRow,
      publishedAssessments: [{ join_code: 'ABC123', title: 'Quiz 1', active: true, submission_count: 0 }],
    })} />);
    // renderTagRow is the forwarded PlannerTab closure invoked per published item;
    // if it were not forwarded this render path would throw a ReferenceError.
    expect(renderTagRow).toHaveBeenCalled();
  });
});
