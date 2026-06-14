import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';

// Render-time smoke test for StandardsSelectorPanel. Added with the CQ
// wave-8 split (#cq8-07) that extracted StandardsConfigChips from the
// parent. Verifies: (1) header + count renders, (2) config chips render
// state/grade/subject via StandardsConfigChips, (3) domain jump bar renders
// when multiple domains present, (4) standard cards render via StandardCard,
// (5) loading state renders, (6) empty state renders. Tests use Vitest
// native matchers (toBeTruthy), not jest-dom.

vi.mock('../components/StandardCard', () => ({
  default: function MockStandardCard({ standard }) {
    return <div data-testid="standard-card">{standard.code}</div>;
  },
}));

vi.mock('../components/Icon', () => ({
  default: function MockIcon({ name }) {
    return <span data-testid={`icon-${name}`} />;
  },
}));

import StandardsSelectorPanel from '../components/planner-lesson/StandardsSelectorPanel';

afterEach(() => {
  vi.clearAllMocks();
});

const STD_A = {
  code: 'MAFS.K12.MP.1.1',
  benchmark: 'Make sense of problems.',
  dok: 2,
  topics: [],
  learning_targets: [],
  vocabulary: [],
  essential_questions: [],
  item_specs: '',
  sample_assessment: '',
};
const STD_B = {
  code: 'MAFS.K12.MP.2.1',
  benchmark: 'Reason abstractly.',
  dok: 2,
  topics: [],
  learning_targets: [],
  vocabulary: [],
  essential_questions: [],
  item_specs: '',
  sample_assessment: '',
};

const standardsScrollRef = { current: null };

function baseProps(overrides = {}) {
  return {
    config: { state: 'FL', grade_level: '6', subject: 'Math' },
    domainNameMap: { MP: 'Mathematical Practices' },
    expandedStandards: [],
    getDomains: (stds) => [...new Set(stds.map((s) => s.code.split('.')[2]))],
    plannerLoading: false,
    scrollToDomain: vi.fn(),
    selectedStandards: [],
    setExpandedStandards: vi.fn(),
    standards: [STD_A, STD_B],
    standardsScrollRef,
    toggleStandard: vi.fn(),
    ...overrides,
  };
}

describe('StandardsSelectorPanel mounts without crashing (render-time smoke)', () => {
  it('renders header with selected count and standards available count', () => {
    const { container } = render(<StandardsSelectorPanel {...baseProps({ selectedStandards: ['MAFS.K12.MP.1.1'] })} />);
    // Count and label are split across text nodes — check heading textContent directly.
    const h3 = container.querySelector('h3');
    expect(h3).toBeTruthy();
    expect(h3.textContent).toMatch(/Select Standards.*1/);
    // "standards available" span — textContent spans "2" + " standards available".
    expect(container.textContent).toMatch(/2.*standards available/);
  });

  it('renders config chips via StandardsConfigChips — state, grade, subject', () => {
    render(<StandardsSelectorPanel {...baseProps()} />);
    expect(screen.getByText('Florida')).toBeTruthy();
    expect(screen.getByText('Grade 6')).toBeTruthy();
    expect(screen.getByText('Math')).toBeTruthy();
  });

  it('renders domain jump bar when multiple domains exist', () => {
    render(<StandardsSelectorPanel {...baseProps()} />);
    // Only one domain (MP) from both standards — bar should not render
    // (requires >1 domain). Override with two domains:
    const STD_C = { ...STD_B, code: 'MAFS.K12.NS.1.1' };
    const { unmount } = render(
      <StandardsSelectorPanel
        {...baseProps({ standards: [STD_A, STD_C] })}
      />,
    );
    expect(screen.getByText('Mathematical Practices')).toBeTruthy();
    unmount();
  });

  it('clicking a domain button calls scrollToDomain', () => {
    const scrollToDomain = vi.fn();
    const STD_C = { ...STD_B, code: 'MAFS.K12.NS.1.1' };
    render(
      <StandardsSelectorPanel
        {...baseProps({ standards: [STD_A, STD_C], scrollToDomain, domainNameMap: { MP: 'Mathematical Practices', NS: 'Number Sense' } })}
      />,
    );
    fireEvent.click(screen.getByText('Mathematical Practices'));
    expect(scrollToDomain).toHaveBeenCalledWith(standardsScrollRef, 'MP');
  });

  it('renders StandardCard for each standard', () => {
    render(<StandardsSelectorPanel {...baseProps()} />);
    const cards = screen.getAllByTestId('standard-card');
    expect(cards.length).toBeTruthy();
    expect(cards[0].textContent).toBeTruthy();
  });

  it('renders loading state when plannerLoading=true and no standards', () => {
    render(
      <StandardsSelectorPanel
        {...baseProps({ plannerLoading: true, standards: [] })}
      />,
    );
    expect(screen.getByText('Loading standards...')).toBeTruthy();
  });

  it('renders empty state when not loading and no standards', () => {
    render(
      <StandardsSelectorPanel
        {...baseProps({ plannerLoading: false, standards: [] })}
      />,
    );
    expect(screen.getByText(/No standards found for Grade/)).toBeTruthy();
    expect(screen.getByText(/Try a different grade level/)).toBeTruthy();
  });

  it('renders fallback state label when state not in map', () => {
    render(
      <StandardsSelectorPanel
        {...baseProps({ config: { state: 'AK', grade_level: '3', subject: 'Science' } })}
      />,
    );
    // AK is not in the map — should fall back to the raw code
    expect(screen.getByText('AK')).toBeTruthy();
  });
});
