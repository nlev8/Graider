/**
 * Tests for StandardCard.
 */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import StandardCard from '../components/StandardCard';

const baseStandard = {
  code: 'SS.7.A.4.1',
  benchmark: 'Examine the causes of the Civil War.',
  dok: 3,
  topics: ['Civil War', 'Causes'],
};

const richStandard = {
  ...baseStandard,
  essential_questions: ['What caused the war?', 'Could it have been avoided?'],
  learning_targets: ['Identify economic factors', 'Identify political factors'],
  vocabulary: ['secession', 'abolition'],
  item_specs: 'Select all factors that contributed.',
  sample_assessment: 'Which of the following...',
};

describe('StandardCard', () => {
  it('renders the code, benchmark, DOK badge, and topics', () => {
    render(<StandardCard standard={baseStandard} isSelected={false} onToggle={() => {}} isExpanded={false} onExpand={() => {}} />);
    expect(screen.getByText('SS.7.A.4.1')).toBeDefined();
    expect(screen.getByText(/Examine the causes/)).toBeDefined();
    expect(screen.getByText('DOK 3')).toBeDefined();
    expect(screen.getByText('Civil War')).toBeDefined();
    expect(screen.getByText('Causes')).toBeDefined();
  });

  it('calls onToggle when the row is clicked', () => {
    const onToggle = vi.fn();
    render(<StandardCard standard={baseStandard} isSelected={false} onToggle={onToggle} isExpanded={false} onExpand={() => {}} />);
    fireEvent.click(screen.getByText('SS.7.A.4.1'));
    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it('does NOT show "Show Details" button when standard has no detail fields', () => {
    render(<StandardCard standard={baseStandard} isSelected={false} onToggle={() => {}} isExpanded={false} onExpand={() => {}} />);
    expect(screen.queryByText(/Show Details/)).toBeNull();
  });

  it('shows "Show Details" when learning_targets/vocabulary/essential_questions present and isExpanded=false', () => {
    render(<StandardCard standard={richStandard} isSelected={false} onToggle={() => {}} isExpanded={false} onExpand={() => {}} />);
    expect(screen.getByText('Show Details')).toBeDefined();
  });

  it('shows "Hide Details" when isExpanded=true', () => {
    render(<StandardCard standard={richStandard} isSelected={false} onToggle={() => {}} isExpanded={true} onExpand={() => {}} />);
    expect(screen.getByText('Hide Details')).toBeDefined();
  });

  it('renders all expanded sections when isExpanded=true', () => {
    render(<StandardCard standard={richStandard} isSelected={false} onToggle={() => {}} isExpanded={true} onExpand={() => {}} />);
    // Bullet-prefixed lines: match by substring
    expect(screen.getByText(/What caused the war\?/)).toBeDefined();
    expect(screen.getByText(/Identify economic factors/)).toBeDefined();
    expect(screen.getByText('secession')).toBeDefined();
    expect(screen.getByText(/Select all factors/)).toBeDefined();
    expect(screen.getByText(/Which of the following/)).toBeDefined();
  });

  it('expand button click calls onExpand and does NOT call onToggle (stopPropagation)', () => {
    const onToggle = vi.fn();
    const onExpand = vi.fn();
    render(<StandardCard standard={richStandard} isSelected={false} onToggle={onToggle} isExpanded={false} onExpand={onExpand} />);
    fireEvent.click(screen.getByText('Show Details'));
    expect(onExpand).toHaveBeenCalledTimes(1);
    expect(onToggle).not.toHaveBeenCalled();
  });

  it('renders selected styling when isSelected=true', () => {
    const { container } = render(<StandardCard standard={baseStandard} isSelected={true} onToggle={() => {}} isExpanded={false} onExpand={() => {}} />);
    // Selection border uses var(--accent-primary) when isSelected
    const card = container.firstChild;
    expect(card.style.border).toContain('var(--accent-primary)');
  });
});
