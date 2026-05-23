import React from 'react';
import { render } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import HelpTab from '../components/HelpTab';

beforeEach(() => {
  global.fetch = vi.fn(() => Promise.resolve({ json: () => Promise.resolve({ content: '## Manual\nhello world' }) }));
});

const props = (over = {}) => ({ activeTab: 'help', setShowTutorial: vi.fn(), setTutorialStep: vi.fn(), ...over });

describe('HelpTab', () => {
  it('renders nothing when not the active tab', () => {
    const { container } = render(<HelpTab {...props({ activeTab: 'grade' })} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders the help content when active', async () => {
    const { findByText } = render(<HelpTab {...props()} />);
    expect(await findByText(/Interactive Tutorial/)).toBeTruthy();
  });

  it('fetches the manual once ever, even across tab switches', async () => {
    const { rerender, findByText } = render(<HelpTab {...props({ activeTab: 'grade' })} />);
    expect(global.fetch).not.toHaveBeenCalled();              // inactive: no fetch yet
    rerender(<HelpTab {...props({ activeTab: 'help' })} />);  // activate
    await findByText(/Interactive Tutorial/);
    expect(global.fetch).toHaveBeenCalledTimes(1);            // fetched on first activation
    rerender(<HelpTab {...props({ activeTab: 'grade' })} />); // switch away (component stays mounted)
    rerender(<HelpTab {...props({ activeTab: 'help' })} />);  // switch back
    expect(global.fetch).toHaveBeenCalledTimes(1);            // ONCE EVER — no refetch (the behavior the always-mounted form protects)
  });
});
