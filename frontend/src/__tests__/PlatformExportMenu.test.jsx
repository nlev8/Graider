/**
 * Tests for PlatformExportMenu.
 */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import PlatformExportMenu from '../components/PlatformExportMenu';

describe('PlatformExportMenu', () => {
  it('renders nothing when open is false', () => {
    const { container } = render(<PlatformExportMenu open={false} onSelect={() => {}} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders all 6 platform options when open', () => {
    render(<PlatformExportMenu open={true} onSelect={() => {}} />);
    expect(screen.getByText('Wayground')).toBeDefined();
    expect(screen.getByText('CSV (Generic)')).toBeDefined();
    expect(screen.getByText('Canvas (QTI)')).toBeDefined();
    expect(screen.getByText('Kahoot')).toBeDefined();
    expect(screen.getByText('Quizlet')).toBeDefined();
    expect(screen.getByText('Google Forms')).toBeDefined();
  });

  it('calls onSelect with the platform id when an entry is clicked', () => {
    const onSelect = vi.fn();
    render(<PlatformExportMenu open={true} onSelect={onSelect} />);
    fireEvent.click(screen.getByText('Wayground'));
    expect(onSelect).toHaveBeenCalledWith('wayground');
  });

  it('calls onSelect with canvas_qti when Canvas (QTI) is clicked', () => {
    const onSelect = vi.fn();
    render(<PlatformExportMenu open={true} onSelect={onSelect} />);
    fireEvent.click(screen.getByText('Canvas (QTI)'));
    expect(onSelect).toHaveBeenCalledWith('canvas_qti');
  });

  it('calls onSelect with google_forms when Google Forms is clicked', () => {
    const onSelect = vi.fn();
    render(<PlatformExportMenu open={true} onSelect={onSelect} />);
    fireEvent.click(screen.getByText('Google Forms'));
    expect(onSelect).toHaveBeenCalledWith('google_forms');
  });
});
