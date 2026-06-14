import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import WritingProfilesSection from '../components/settings-privacy/WritingProfilesSection';

vi.mock('../services/api', () => new Proxy({}, { get: () => vi.fn().mockResolvedValue({}) }));

const makeProps = (over = {}) => ({
  addToast: vi.fn(),
  setSelectedStudentHistory: vi.fn(),
  setStudentHistoryList: vi.fn(),
  setStudentHistoryLoading: vi.fn(),
  studentHistoryList: [],
  studentHistoryLoading: false,
  ...over,
});

describe('WritingProfilesSection', () => {
  it('renders header and empty-state hint when list is empty', () => {
    render(<WritingProfilesSection {...makeProps()} />);
    expect(screen.getByText('Student Writing Profiles')).toBeTruthy();
    expect(screen.getByText('Click "Refresh" to load student writing profiles')).toBeTruthy();
    expect(screen.getByText('Refresh')).toBeTruthy();
  });

  it('shows Loading... in button and empty-state when loading', () => {
    render(<WritingProfilesSection {...makeProps({ studentHistoryLoading: true })} />);
    // Both the Refresh button label and the empty-state text show "Loading..."
    const nodes = screen.getAllByText('Loading...');
    expect(nodes.length).toBeGreaterThan(0);
  });

  it('renders student rows and Delete All Profiles when list is populated', () => {
    render(
      <WritingProfilesSection
        {...makeProps({
          studentHistoryList: [
            { student_id: 's1', name: 'Alice Smith', submissions_analyzed: 5, avg_complexity: 6.8 },
            { student_id: 's2', name: 'Bob Jones', submissions_analyzed: 2, avg_complexity: 4.1 },
          ],
        })}
      />
    );
    expect(screen.getByText('Alice Smith')).toBeTruthy();
    expect(screen.getByText('Bob Jones')).toBeTruthy();
    expect(screen.getByText(/5 submissions/)).toBeTruthy();
    expect(screen.getByText('Delete All Profiles')).toBeTruthy();
  });

  it('falls back to student_id when name is absent', () => {
    render(
      <WritingProfilesSection
        {...makeProps({
          studentHistoryList: [
            { student_id: 'anon-99', name: null, submissions_analyzed: 1, avg_complexity: 3.0 },
          ],
        })}
      />
    );
    expect(screen.getAllByText('anon-99').length).toBeGreaterThan(0);
  });
});
