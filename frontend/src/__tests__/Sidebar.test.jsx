import React from 'react';
import { render, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import Sidebar from '../components/Sidebar';

const base = () => ({
  activeTab: 'grade',
  TABS: [{ id: 'grade', label: 'Grade', icon: 'CheckCircle' }, { id: 'results', label: 'Results', icon: 'BarChart' }],
  isAdmin: false, sidebarCollapsed: false, theme: 'dark',
});
const makeProps = (o = {}) => new Proxy({ ...base(), ...o }, { get(t, p) { if (p in t) return t[p]; if (typeof p === 'symbol') return undefined; return vi.fn(); }, has() { return true; } });

describe('Sidebar', () => {
  it('smoke: renders nav without crashing', () => {
    const { container } = render(<Sidebar {...makeProps()} />);
    expect(container.firstChild).toBeTruthy();
  });
  it('collapse toggle invokes setSidebarCollapsed', () => {
    const setSidebarCollapsed = vi.fn();
    const { container } = render(<Sidebar {...makeProps({ setSidebarCollapsed })} />);
    const btn = container.querySelector('button');
    expect(btn).toBeTruthy();
    fireEvent.click(btn);
    expect(setSidebarCollapsed).toHaveBeenCalled();
  });
});
