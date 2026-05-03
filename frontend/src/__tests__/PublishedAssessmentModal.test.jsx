/**
 * Tests for PublishedAssessmentModal.
 */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import PublishedAssessmentModal from '../components/PublishedAssessmentModal';

const baseProps = {
  open: true,
  onClose: () => {},
  joinCode: 'ABC123',
  joinLink: 'https://app.graider.live/join/ABC123',
  isClassBased: false,
  onCopied: () => {},
};

beforeEach(() => {
  // Provide a writeable navigator.clipboard mock
  Object.defineProperty(navigator, 'clipboard', {
    configurable: true,
    value: { writeText: vi.fn() },
  });
});

describe('PublishedAssessmentModal', () => {
  it('renders nothing when open is false', () => {
    const { container } = render(<PublishedAssessmentModal {...baseProps} open={false} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders default title/subtitle and the join code', () => {
    render(<PublishedAssessmentModal {...baseProps} />);
    expect(screen.getByText('Published!')).toBeDefined();
    expect(screen.getByText(/Students can now access this/)).toBeDefined();
    // Code appears in the big display AND inline inside instructions; allow >=1
    expect(screen.getAllByText('ABC123').length).toBeGreaterThanOrEqual(1);
  });

  it('uses custom title and subtitle when provided', () => {
    render(
      <PublishedAssessmentModal
        {...baseProps}
        title="Assessment Published!"
        subtitle="Custom subtitle text."
      />
    );
    expect(screen.getByText('Assessment Published!')).toBeDefined();
    expect(screen.getByText('Custom subtitle text.')).toBeDefined();
  });

  it('switches labels based on isClassBased', () => {
    const { rerender } = render(<PublishedAssessmentModal {...baseProps} isClassBased={false} />);
    expect(screen.getByText('Join Code')).toBeDefined();
    expect(screen.getByText('Or share this link:')).toBeDefined();

    rerender(<PublishedAssessmentModal {...baseProps} isClassBased={true} />);
    expect(screen.getByText('Class Code')).toBeDefined();
    expect(screen.getByText('Student portal link:')).toBeDefined();
  });

  it('renders the join-code instructions when isClassBased=false', () => {
    render(<PublishedAssessmentModal {...baseProps} isClassBased={false} />);
    expect(screen.getByText(/app.graider.live\/join/)).toBeDefined();
  });

  it('renders the class-based instructions when isClassBased=true', () => {
    render(<PublishedAssessmentModal {...baseProps} isClassBased={true} />);
    expect(screen.getByText(/app.graider.live\/student/)).toBeDefined();
  });

  it('Copy button writes joinLink to clipboard and calls onCopied', () => {
    const onCopied = vi.fn();
    const { container } = render(<PublishedAssessmentModal {...baseProps} onCopied={onCopied} />);
    // The copy button is the only button containing the Copy icon — find by aria/role
    const buttons = container.querySelectorAll('button');
    // There are 2 buttons: copy + Done. Copy is first (it's inside the link row).
    const copyButton = buttons[0];
    fireEvent.click(copyButton);
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(baseProps.joinLink);
    expect(onCopied).toHaveBeenCalledTimes(1);
  });

  it('Done button calls onClose', () => {
    const onClose = vi.fn();
    render(<PublishedAssessmentModal {...baseProps} onClose={onClose} />);
    fireEvent.click(screen.getByText('Done'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
