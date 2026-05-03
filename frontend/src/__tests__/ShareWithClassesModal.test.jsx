/**
 * Tests for ShareWithClassesModal.
 */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import ShareWithClassesModal from '../components/ShareWithClassesModal';

const baseProps = {
  open: true,
  onClose: () => {},
  content: { title: 'Civil War Quiz', unitName: 'Unit 4', content: {}, contentType: 'assessment' },
  setContent: () => {},
  selectedIds: [],
  setSelectedIds: () => {},
  sharing: false,
  classes: [
    { id: 'c1', name: 'Period 3', class_students: [{ count: 22 }] },
    { id: 'c2', name: 'Period 5', class_students: [{ count: 18 }] },
  ],
  onShare: () => {},
};

describe('ShareWithClassesModal', () => {
  it('renders nothing when open is false', () => {
    const { container } = render(<ShareWithClassesModal {...baseProps} open={false} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders header, content title, unit input, classes list', () => {
    render(<ShareWithClassesModal {...baseProps} />);
    expect(screen.getByText('Share with Class')).toBeDefined();
    expect(screen.getByText('"Civil War Quiz"')).toBeDefined();
    expect(screen.getByText('Period 3')).toBeDefined();
    expect(screen.getByText('Period 5')).toBeDefined();
    expect(screen.getByText('22 students')).toBeDefined();
    expect(screen.getByText('18 students')).toBeDefined();
  });

  it('Share button is disabled when no classes selected', () => {
    render(<ShareWithClassesModal {...baseProps} selectedIds={[]} />);
    expect(screen.getByText(/Share with 0 classes/).closest('button').disabled).toBe(true);
  });

  it('Share button label pluralizes correctly', () => {
    const { rerender } = render(<ShareWithClassesModal {...baseProps} selectedIds={['c1']} />);
    expect(screen.getByText('Share with 1 class')).toBeDefined();
    rerender(<ShareWithClassesModal {...baseProps} selectedIds={['c1', 'c2']} />);
    expect(screen.getByText('Share with 2 classes')).toBeDefined();
  });

  it('shows "Sharing..." when sharing prop is true', () => {
    render(<ShareWithClassesModal {...baseProps} selectedIds={['c1']} sharing={true} />);
    expect(screen.getByText('Sharing...')).toBeDefined();
  });

  it('Share button calls onShare', () => {
    const onShare = vi.fn();
    render(<ShareWithClassesModal {...baseProps} selectedIds={['c1']} onShare={onShare} />);
    fireEvent.click(screen.getByText('Share with 1 class').closest('button'));
    expect(onShare).toHaveBeenCalledTimes(1);
  });

  it('Cancel button calls onClose', () => {
    const onClose = vi.fn();
    render(<ShareWithClassesModal {...baseProps} onClose={onClose} />);
    fireEvent.click(screen.getByText('Cancel'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('clicking a class adds its id to selectedIds via setSelectedIds', () => {
    const setSelectedIds = vi.fn();
    render(<ShareWithClassesModal {...baseProps} selectedIds={[]} setSelectedIds={setSelectedIds} />);
    // Find the checkbox for Period 3
    const checkboxes = document.querySelectorAll('input[type="checkbox"]');
    // checkboxes[0] is "Select All", checkboxes[1] is c1, [2] is c2
    fireEvent.click(checkboxes[1]);
    expect(setSelectedIds).toHaveBeenCalledWith(['c1']);
  });

  it('Select All checks all class ids', () => {
    const setSelectedIds = vi.fn();
    render(<ShareWithClassesModal {...baseProps} selectedIds={[]} setSelectedIds={setSelectedIds} />);
    const checkboxes = document.querySelectorAll('input[type="checkbox"]');
    fireEvent.click(checkboxes[0]); // "Select All"
    expect(setSelectedIds).toHaveBeenCalledWith(['c1', 'c2']);
  });

  it('unit input change calls setContent with updater', () => {
    const setContent = vi.fn();
    const { container } = render(<ShareWithClassesModal {...baseProps} setContent={setContent} />);
    const unitInput = container.querySelector('input[type="text"]');
    fireEvent.change(unitInput, { target: { value: 'Unit 5' } });
    const updater = setContent.mock.calls[0][0];
    const next = updater({ title: 't', unitName: 'old' });
    expect(next.unitName).toBe('Unit 5');
  });
});
