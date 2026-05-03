/**
 * Tests for CurveModal.
 */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import CurveModal from '../components/CurveModal';

const baseProps = {
  open: true,
  onClose: () => {},
  curveType: 'add',
  setCurveType: () => {},
  curveValue: 5,
  setCurveValue: () => {},
  periodLabel: 'Period 3',
  onApply: () => {},
};

describe('CurveModal', () => {
  it('renders nothing when open is false', () => {
    const { container } = render(<CurveModal {...baseProps} open={false} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders header, period label, and the three curve types', () => {
    render(<CurveModal {...baseProps} />);
    expect(screen.getByText('Apply Grade Curve')).toBeDefined();
    expect(screen.getByText('Period 3')).toBeDefined();
    expect(screen.getByText(/Add Points/)).toBeDefined();
    expect(screen.getByText(/Percentage Boost/)).toBeDefined();
    expect(screen.getByText(/Set Minimum Score/)).toBeDefined();
  });

  it('"add" curveType + value=5 → preview shows 75% → 80%', () => {
    render(<CurveModal {...baseProps} curveType="add" curveValue={5} />);
    expect(screen.getByText('75% → 80%')).toBeDefined();
  });

  it('"add" caps preview at 100%', () => {
    render(<CurveModal {...baseProps} curveType="add" curveValue={50} />);
    expect(screen.getByText('75% → 100%')).toBeDefined();
  });

  it('"percent" curveType + 10% → 75% becomes 83% (rounded)', () => {
    render(<CurveModal {...baseProps} curveType="percent" curveValue={10} />);
    expect(screen.getByText('75% → 83%')).toBeDefined();
  });

  it('"set_min" curveType + value 80 → 75% becomes 80%', () => {
    render(<CurveModal {...baseProps} curveType="set_min" curveValue={80} />);
    expect(screen.getByText('75% → 80%')).toBeDefined();
  });

  it('"set_min" curveType + value 50 → 75% stays 75% (since min < example)', () => {
    render(<CurveModal {...baseProps} curveType="set_min" curveValue={50} />);
    expect(screen.getByText('75% → 75%')).toBeDefined();
  });

  it('Apply button calls onApply', () => {
    const onApply = vi.fn();
    render(<CurveModal {...baseProps} onApply={onApply} />);
    fireEvent.click(screen.getByText('Apply Curve'));
    expect(onApply).toHaveBeenCalledTimes(1);
  });

  it('Cancel button calls onClose', () => {
    const onClose = vi.fn();
    render(<CurveModal {...baseProps} onClose={onClose} />);
    fireEvent.click(screen.getByText('Cancel'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('changing curveValue input calls setCurveValue', () => {
    const setCurveValue = vi.fn();
    const { container } = render(<CurveModal {...baseProps} setCurveValue={setCurveValue} />);
    const numberInput = container.querySelector('input[type="number"]');
    fireEvent.change(numberInput, { target: { value: '15' } });
    expect(setCurveValue).toHaveBeenCalledWith('15');
  });

  it('changing curveType select calls setCurveType', () => {
    const setCurveType = vi.fn();
    const { container } = render(<CurveModal {...baseProps} setCurveType={setCurveType} />);
    const select = container.querySelector('select');
    fireEvent.change(select, { target: { value: 'percent' } });
    expect(setCurveType).toHaveBeenCalledWith('percent');
  });
});
