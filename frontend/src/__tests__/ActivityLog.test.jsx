/**
 * Tests for ActivityLog.
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import ActivityLog from '../components/ActivityLog';

describe('ActivityLog', () => {
  it('renders nothing when open is false', () => {
    const { container } = render(<ActivityLog open={false} log={['x']} />);
    expect(container.firstChild).toBeNull();
  });

  it('shows the empty-state message when log is empty', () => {
    render(<ActivityLog open={true} log={[]} />);
    expect(screen.getByText(/Ready to grade/)).toBeDefined();
  });

  it('renders each line of the log', () => {
    render(<ActivityLog open={true} log={['line A', 'line B', 'line C']} />);
    expect(screen.getByText('line A')).toBeDefined();
    expect(screen.getByText('line B')).toBeDefined();
    expect(screen.getByText('line C')).toBeDefined();
  });

  it('renders only the last 30 lines when log has more', () => {
    const log = Array.from({ length: 50 }, (_, i) => `line ${i}`);
    render(<ActivityLog open={true} log={log} />);
    // Lines 0-19 should be missing, 20-49 should be present
    expect(screen.queryByText('line 0')).toBeNull();
    expect(screen.queryByText('line 19')).toBeNull();
    expect(screen.getByText('line 20')).toBeDefined();
    expect(screen.getByText('line 49')).toBeDefined();
  });

  it('forwards ref to the scrollable container', () => {
    const ref = React.createRef();
    render(<ActivityLog ref={ref} open={true} log={['x']} />);
    expect(ref.current).not.toBeNull();
    expect(ref.current.tagName).toBe('DIV');
  });
});
