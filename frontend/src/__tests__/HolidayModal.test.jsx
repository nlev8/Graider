/**
 * Tests for HolidayModal.
 */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import HolidayModal from '../components/HolidayModal';

const baseProps = {
  open: true,
  onClose: () => {},
  form: { name: '', date: '', end_date: '' },
  setForm: () => {},
  onAdd: () => {},
};

describe('HolidayModal', () => {
  it('renders nothing when open is false', () => {
    const { container } = render(<HolidayModal {...baseProps} open={false} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders header and the three labeled fields', () => {
    render(<HolidayModal {...baseProps} />);
    expect(screen.getByText('Add Holiday / Break')).toBeDefined();
    expect(screen.getByText('Name')).toBeDefined();
    expect(screen.getByText('Start Date')).toBeDefined();
    expect(screen.getByText(/End Date/)).toBeDefined();
  });

  it('Add button is disabled until both name and date are present', () => {
    const { rerender } = render(<HolidayModal {...baseProps} form={{ name: 'Spring Break', date: '', end_date: '' }} />);
    expect(screen.getByText('Add Holiday').disabled).toBe(true);

    rerender(<HolidayModal {...baseProps} form={{ name: '', date: '2026-04-01', end_date: '' }} />);
    expect(screen.getByText('Add Holiday').disabled).toBe(true);

    rerender(<HolidayModal {...baseProps} form={{ name: 'Spring Break', date: '2026-04-01', end_date: '' }} />);
    expect(screen.getByText('Add Holiday').disabled).toBe(false);
  });

  it('Add button calls onAdd with the form and then onClose', () => {
    const onAdd = vi.fn();
    const onClose = vi.fn();
    const form = { name: 'Spring Break', date: '2026-04-01', end_date: '2026-04-08' };
    render(<HolidayModal {...baseProps} form={form} onAdd={onAdd} onClose={onClose} />);
    fireEvent.click(screen.getByText('Add Holiday'));
    expect(onAdd).toHaveBeenCalledWith(form);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('Add button does nothing when fields are incomplete', () => {
    const onAdd = vi.fn();
    const onClose = vi.fn();
    render(<HolidayModal {...baseProps} form={{ name: '', date: '', end_date: '' }} onAdd={onAdd} onClose={onClose} />);
    fireEvent.click(screen.getByText('Add Holiday'));
    expect(onAdd).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });

  it('name input change calls setForm with an updater fn', () => {
    const setForm = vi.fn();
    const { container } = render(<HolidayModal {...baseProps} setForm={setForm} />);
    const nameInput = container.querySelectorAll('input')[0];
    fireEvent.change(nameInput, { target: { value: 'Winter Break' } });
    expect(setForm).toHaveBeenCalledTimes(1);
    // The component uses the prev-callback pattern: setForm((prev) => ({ ...prev, name: ... }))
    expect(typeof setForm.mock.calls[0][0]).toBe('function');
  });

  it('Cancel button calls onClose', () => {
    const onClose = vi.fn();
    render(<HolidayModal {...baseProps} onClose={onClose} />);
    fireEvent.click(screen.getByText('Cancel'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
