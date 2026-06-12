import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import StudentDashboard from '../components/StudentDashboard';

// Content-asserting mount test for StudentDashboard. Added with the CQ
// wave-7 split of StudentDashboard.jsx into student-dashboard/* (mirrors
// StudentPortal.mount.test.jsx from wave 6, for the same reason): before
// this test, the only renderer was the empty-items smoke in smoke.test.jsx,
// which passes even if the split leaves an unimported subcomponent or a
// mis-threaded prop that blanks the unit list or modal at runtime. This
// test loads a populated dashboard and asserts real content from every
// extracted piece actually mounts: DashboardHeader (name/class/logout),
// UnitGroupCard (unit accordion, assignment rows + status, study-material
// cards, expand/collapse), and ResourceViewerModal (study-guide sections
// via /api/student/resource/:id, flashcards via the _fromDashboard
// /api/student/content/:id path, and close-button dismissal).

const dashboardItems = [
  {
    content_id: 'c1', title: 'Algebra Quiz', content_type: 'assessment',
    status: 'graded', score: 9, percentage: 92.4, letter_grade: 'A-',
    unit_name: 'Unit 1', created_at: '2026-06-01T00:00:00Z',
  },
  {
    content_id: 'c2', title: 'Homework 3', content_type: 'assignment',
    status: 'not_started', unit_name: 'Unit 1', created_at: '2026-06-02T00:00:00Z',
  },
  // RESOURCE_TYPES entry published via the dashboard (the _fromDashboard
  // branch in UnitGroupCard fetches /api/student/content/:id for these).
  {
    content_id: 'f1', title: 'Unit Flashcards', content_type: 'flashcards',
    unit_name: 'Unit 1', created_at: '2026-06-03T00:00:00Z',
  },
];

const studyGuideResource = {
  id: 'r1', title: 'Chapter 5 Guide', content_type: 'study_guide',
  unit_name: 'Unit 1', created_at: '2026-06-04T00:00:00Z',
  content: {
    sections: [{
      heading: 'Key Ideas',
      content: ['Photosynthesis converts light into energy'],
      terms: [{ term: 'Cell', definition: 'the basic unit of life' }],
      questions: [{ question: 'Why do leaves look green?', answer: 'Chlorophyll reflects green light' }],
    }],
  },
};

function jsonResponse(body) {
  return Promise.resolve({ json: () => Promise.resolve(body) });
}

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('student_token', 'tok-123');
  global.fetch = vi.fn((url) => {
    if (url === '/api/student/dashboard') return jsonResponse({ items: dashboardItems });
    if (url === '/api/student/resources') return jsonResponse({ resources: [studyGuideResource] });
    if (url === '/api/student/resource/r1') return jsonResponse({ resource: studyGuideResource });
    if (url === '/api/student/content/f1') return jsonResponse({ content: { questions: [{ front: 'Q1 front', back: 'A1 back' }] } });
    return jsonResponse({});
  });
});

const baseProps = () => ({
  studentInfo: { first_name: 'Test', last_name: 'Student' },
  classInfo: { name: 'Period 1', subject: 'History' },
  onLogout: vi.fn(),
});

describe('StudentDashboard mounts content from every extracted piece', () => {
  it('renders header, auto-expanded unit card, and resource viewer modal', async () => {
    render(<StudentDashboard {...baseProps()} />);

    // DashboardHeader
    expect(screen.getByText('Period 1 • History')).toBeTruthy();
    expect(screen.getByText('Log Out')).toBeTruthy();

    // UnitGroupCard — unit auto-expands (most recent unit, first render)
    expect(await screen.findByText('Unit 1')).toBeTruthy();
    expect(screen.getByText('Current')).toBeTruthy();
    expect(await screen.findByText('Assignments')).toBeTruthy();
    expect(screen.getByText('Algebra Quiz')).toBeTruthy();
    expect(screen.getByText('Graded')).toBeTruthy();
    expect(screen.getByText('Homework 3')).toBeTruthy();
    expect(screen.getByText('Not Started')).toBeTruthy();
    expect(screen.getByText('Study Materials')).toBeTruthy();
    expect(screen.getByText('Chapter 5 Guide')).toBeTruthy();
    expect(screen.getByText('Study Guide')).toBeTruthy();
    expect(screen.getByText('Unit Flashcards')).toBeTruthy();

    // ResourceViewerModal — study guide path (/api/student/resource/:id)
    fireEvent.click(screen.getByText('Chapter 5 Guide'));
    expect(await screen.findByText('Key Ideas')).toBeTruthy();
    expect(screen.getByText('Photosynthesis converts light into energy', { exact: false })).toBeTruthy();
    expect(screen.getByText('the basic unit of life', { exact: false })).toBeTruthy();
    expect(screen.getByText('Answer: Chlorophyll reflects green light')).toBeTruthy();

    // Close button dismisses the modal
    fireEvent.click(screen.getByText(String.fromCharCode(10005)));
    expect(screen.queryByText('Key Ideas')).toBeNull();

    // ResourceViewerModal — flashcards via the _fromDashboard branch
    // (/api/student/content/:id), mounting FlashcardView
    fireEvent.click(screen.getByText('Unit Flashcards'));
    expect(await screen.findByText('Q1 front')).toBeTruthy();
  });

  it('collapses and re-expands a unit, and logs out through the header', async () => {
    const props = baseProps();
    render(<StudentDashboard {...props} />);

    expect(await screen.findByText('Algebra Quiz')).toBeTruthy();

    // Collapse the auto-expanded unit
    fireEvent.click(screen.getByText('Unit 1'));
    expect(screen.queryByText('Algebra Quiz')).toBeNull();

    // Re-expand
    fireEvent.click(screen.getByText('Unit 1'));
    expect(screen.getByText('Algebra Quiz')).toBeTruthy();

    // Logout clears the student session keys and calls onLogout
    fireEvent.click(screen.getByText('Log Out'));
    expect(props.onLogout).toHaveBeenCalledTimes(1);
    expect(localStorage.getItem('student_token')).toBeNull();
  });
});
