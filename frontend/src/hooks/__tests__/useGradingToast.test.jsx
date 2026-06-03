import { renderHook } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../../services/posthog', () => ({ track: vi.fn() }));

import { track as phTrack } from '../../services/posthog';
import { useGradingToast } from '../useGradingToast';

// Characterization net for the App.jsx -> useGradingToast extraction (slice 7).
// Pins the persistent-toast lifecycle: show on start, update on file change, and on
// completion remove + emit the completion/cost-limit toasts + the analytics event.
function setup(initialStatus, { isLocalhost = false, config = {} } = {}) {
  const addToast = vi.fn(() => 42); // returns a truthy toast id
  const setToasts = vi.fn();
  const removeToast = vi.fn();
  const { rerender } = renderHook(
    ({ status }) => useGradingToast({ status, config, isLocalhost, addToast, setToasts, removeToast }),
    { initialProps: { status: initialStatus } },
  );
  return { addToast, setToasts, removeToast, rerender };
}

describe('useGradingToast', () => {
  beforeEach(() => vi.clearAllMocks());

  it('shows a persistent toast when grading starts', () => {
    const { addToast, rerender } = setup({ is_running: false });
    rerender({ status: { is_running: true, current_file: 'a.docx' } });
    expect(addToast).toHaveBeenCalledWith(
      expect.stringContaining('Grading in progress'), 'info', 0,
    );
  });

  it('updates the persistent toast message as the current file changes', () => {
    const { setToasts, rerender } = setup({ is_running: false });
    rerender({ status: { is_running: true, current_file: 'a.docx' } }); // start (sets the id)
    rerender({ status: { is_running: true, current_file: 'b.docx' } }); // progress
    expect(setToasts).toHaveBeenCalled();
  });

  it('on completion: removes the toast and shows a completion toast', () => {
    const { addToast, removeToast, rerender } = setup({ is_running: false });
    rerender({ status: { is_running: true, current_file: 'a.docx' } });
    rerender({ status: { is_running: false, results: [{}, {}], session_cost: { total_cost: 0 } } });
    expect(removeToast).toHaveBeenCalledWith(42);
    expect(addToast).toHaveBeenCalledWith(expect.stringContaining('Grading complete! 2'), 'success');
  });

  it('warns when the cost limit was hit', () => {
    const { addToast, rerender } = setup({ is_running: false }, { config: { cost_limit_per_session: 5 } });
    rerender({ status: { is_running: true } });
    rerender({ status: { is_running: false, cost_limit_hit: true, results: [] } });
    expect(addToast).toHaveBeenCalledWith(expect.stringContaining('cost limit of $5.00'), 'warning', 8000);
  });

  it('emits the grading_completed analytics event off-localhost', () => {
    const { rerender } = setup({ is_running: false });
    rerender({ status: { is_running: true } });
    rerender({ status: { is_running: false, results: [{}], session_cost: { total_cost: 0.12 } } });
    expect(phTrack).toHaveBeenCalledWith('grading_completed', expect.objectContaining({ result_count: 1 }));
  });

  it('does NOT emit analytics on localhost', () => {
    const { rerender } = setup({ is_running: false }, { isLocalhost: true });
    rerender({ status: { is_running: true } });
    rerender({ status: { is_running: false, results: [{}] } });
    expect(phTrack).not.toHaveBeenCalled();
  });
});
