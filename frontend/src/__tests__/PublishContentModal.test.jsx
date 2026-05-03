/**
 * Tests for PublishContentModal — the largest extracted component
 * (15 props, branched assessment vs assignment flow, makeup-exam +
 * accommodations toggles, period-scoped student selection).
 */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import PublishContentModal from '../components/PublishContentModal';

const baseSettings = {
  contentType: 'assessment',
  assessmentCategory: 'formative',
  periodFilename: '',
  period: '',
  selectedStudents: [],
  isMakeup: false,
  applyAccommodations: false,
  timeLimit: 30,
  availableFrom: '',
  availableUntil: '',
  dueDate: '',
};

const baseProps = {
  open: true,
  onClose: () => {},
  settings: baseSettings,
  setSettings: () => {},
  classId: '',
  setClassId: () => {},
  teacherClasses: [
    { id: 'c1', name: 'Period 3', join_code: 'ABC' },
  ],
  periods: [
    { filename: 'p3.csv', name: 'Period 3 - Period 3' },
  ],
  onPeriodChange: () => {},
  modalStudents: [],
  loadingStudents: false,
  studentAccommodations: {},
  publishing: false,
  onPublish: () => {},
};

describe('PublishContentModal', () => {
  it('renders nothing when open is false', () => {
    const { container } = render(<PublishContentModal {...baseProps} open={false} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders "Publish Assessment" header for assessment contentType', () => {
    render(<PublishContentModal {...baseProps} />);
    // Appears in both the H2 header and the CTA button
    expect(screen.getAllByText('Publish Assessment').length).toBe(2);
  });

  it('renders "Publish Assignment" header for assignment contentType', () => {
    render(<PublishContentModal {...baseProps} settings={{ ...baseSettings, contentType: 'assignment' }} />);
    expect(screen.getAllByText('Publish Assignment').length).toBe(2);
  });

  it('shows formative/summative buttons only for assessments', () => {
    const { rerender } = render(<PublishContentModal {...baseProps} />);
    expect(screen.getByText('Formative')).toBeDefined();
    expect(screen.getByText('Summative')).toBeDefined();

    rerender(<PublishContentModal {...baseProps} settings={{ ...baseSettings, contentType: 'assignment' }} />);
    expect(screen.queryByText('Formative')).toBeNull();
    expect(screen.queryByText('Summative')).toBeNull();
  });

  it('shows Period dropdown only when no class is selected', () => {
    const { rerender } = render(<PublishContentModal {...baseProps} classId="" />);
    expect(screen.getByText(/Period \(Optional\)/)).toBeDefined();

    rerender(<PublishContentModal {...baseProps} classId="c1" />);
    expect(screen.queryByText(/Period \(Optional\)/)).toBeNull();
  });

  it('shows Makeup Exam toggle only for assessments', () => {
    const { rerender } = render(<PublishContentModal {...baseProps} />);
    expect(screen.getByText('Makeup Exam')).toBeDefined();

    rerender(<PublishContentModal {...baseProps} settings={{ ...baseSettings, contentType: 'assignment' }} />);
    expect(screen.queryByText('Makeup Exam')).toBeNull();
  });

  it('time-limit label is required (*) for assessments and "(Optional)" for assignments', () => {
    const { rerender } = render(<PublishContentModal {...baseProps} />);
    expect(screen.getByText('Time Limit *')).toBeDefined();

    rerender(<PublishContentModal {...baseProps} settings={{ ...baseSettings, contentType: 'assignment' }} />);
    expect(screen.getByText('Time Limit (Optional)')).toBeDefined();
  });

  it('shows Available From / Until for assessments and Due Date for assignments', () => {
    const { rerender } = render(<PublishContentModal {...baseProps} />);
    expect(screen.getByText('Available From')).toBeDefined();
    expect(screen.getByText('Available Until')).toBeDefined();
    expect(screen.queryByText('Due Date')).toBeNull();

    rerender(<PublishContentModal {...baseProps} settings={{ ...baseSettings, contentType: 'assignment' }} />);
    expect(screen.queryByText('Available From')).toBeNull();
    expect(screen.getByText('Due Date')).toBeDefined();
  });

  it('publish button is disabled for assessment when timeLimit is 0/empty', () => {
    render(<PublishContentModal {...baseProps} settings={{ ...baseSettings, timeLimit: null }} />);
    const buttons = screen.getAllByText(/Publish Assessment/);
    // The CTA button (not the H2) — find the one with "btn-primary" class
    const cta = buttons.find((b) => b.tagName === 'BUTTON');
    expect(cta.disabled).toBe(true);
  });

  it('publish button is disabled when isMakeup but no students selected', () => {
    render(<PublishContentModal {...baseProps} settings={{ ...baseSettings, isMakeup: true, periodFilename: 'p3.csv', selectedStudents: [] }} />);
    const cta = screen.getAllByText(/Publish Assessment/).find((b) => b.tagName === 'BUTTON');
    expect(cta.disabled).toBe(true);
  });

  it('publish button calls onPublish when clicked', () => {
    const onPublish = vi.fn();
    render(<PublishContentModal {...baseProps} onPublish={onPublish} />);
    const cta = screen.getAllByText(/Publish Assessment/).find((b) => b.tagName === 'BUTTON');
    fireEvent.click(cta);
    expect(onPublish).toHaveBeenCalledTimes(1);
  });

  it('shows "Publishing..." when publishing prop is true', () => {
    render(<PublishContentModal {...baseProps} publishing={true} />);
    expect(screen.getByText('Publishing...')).toBeDefined();
  });

  it('Cancel button calls onClose', () => {
    const onClose = vi.fn();
    render(<PublishContentModal {...baseProps} onClose={onClose} />);
    fireEvent.click(screen.getByText('Cancel'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('renders student list when isMakeup + period selected', () => {
    render(
      <PublishContentModal
        {...baseProps}
        settings={{ ...baseSettings, isMakeup: true, periodFilename: 'p3.csv' }}
        modalStudents={[
          { id: 's1', first: 'Jane', last: 'Doe' },
          { id: 's2', first: 'John', last: 'Smith', email: 'js@x.com' },
        ]}
        studentAccommodations={{ s1: { type: 'iep' } }}
      />
    );
    expect(screen.getByText('Jane Doe')).toBeDefined();
    expect(screen.getByText('John Smith')).toBeDefined();
    expect(screen.getByText('IEP/504')).toBeDefined();
  });
});
