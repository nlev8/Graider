/**
 * Tests for NewUnitModal.
 */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import NewUnitModal from '../components/NewUnitModal';

const baseProps = {
  open: true,
  onClose: () => {},
  value: '',
  setValue: () => {},
  mode: 'unit',
  onSubmit: () => {},
};

describe('NewUnitModal', () => {
  it('renders nothing when open is false', () => {
    const { container } = render(<NewUnitModal {...baseProps} open={false} />);
    expect(container.firstChild).toBeNull();
  });

  it('shows unit-mode header and CTA', () => {
    render(<NewUnitModal {...baseProps} mode="unit" />);
    expect(screen.getByText('New Unit')).toBeDefined();
    expect(screen.getByText('Enter a name for the new unit')).toBeDefined();
    expect(screen.getByText('Create Unit')).toBeDefined();
  });

  it('shows tag-mode header and CTA', () => {
    render(<NewUnitModal {...baseProps} mode="tag" />);
    expect(screen.getByText('New Tag')).toBeDefined();
    expect(screen.getByText('Enter a name for the new tag')).toBeDefined();
    expect(screen.getByText('Create Tag')).toBeDefined();
  });

  it('Create button is disabled when value is empty/whitespace', () => {
    const { rerender } = render(<NewUnitModal {...baseProps} value="" />);
    expect(screen.getByText('Create Unit').disabled).toBe(true);
    rerender(<NewUnitModal {...baseProps} value="   " />);
    expect(screen.getByText('Create Unit').disabled).toBe(true);
  });

  it('Create button is enabled when value is non-empty', () => {
    render(<NewUnitModal {...baseProps} value="Unit 1" />);
    expect(screen.getByText('Create Unit').disabled).toBe(false);
  });

  it('Create button calls onSubmit with trimmed value', () => {
    const onSubmit = vi.fn();
    render(<NewUnitModal {...baseProps} value="  My Unit  " onSubmit={onSubmit} />);
    fireEvent.click(screen.getByText('Create Unit'));
    expect(onSubmit).toHaveBeenCalledWith('My Unit');
  });

  it('Enter key calls onSubmit with trimmed value', () => {
    const onSubmit = vi.fn();
    const { container } = render(<NewUnitModal {...baseProps} value="My Unit" onSubmit={onSubmit} />);
    const input = container.querySelector('input');
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onSubmit).toHaveBeenCalledWith('My Unit');
  });

  it('Enter key does NOT call onSubmit when value is empty', () => {
    const onSubmit = vi.fn();
    const { container } = render(<NewUnitModal {...baseProps} value="" onSubmit={onSubmit} />);
    fireEvent.keyDown(container.querySelector('input'), { key: 'Enter' });
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('Escape key calls onClose', () => {
    const onClose = vi.fn();
    const { container } = render(<NewUnitModal {...baseProps} onClose={onClose} />);
    fireEvent.keyDown(container.querySelector('input'), { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('input change calls setValue', () => {
    const setValue = vi.fn();
    const { container } = render(<NewUnitModal {...baseProps} setValue={setValue} />);
    fireEvent.change(container.querySelector('input'), { target: { value: 'foo' } });
    expect(setValue).toHaveBeenCalledWith('foo');
  });

  it('Cancel button calls onClose', () => {
    const onClose = vi.fn();
    render(<NewUnitModal {...baseProps} onClose={onClose} />);
    fireEvent.click(screen.getByText('Cancel'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
