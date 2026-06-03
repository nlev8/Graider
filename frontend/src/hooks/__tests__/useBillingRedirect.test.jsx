import { renderHook } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useBillingRedirect } from '../useBillingRedirect';

// Characterization net for the App.jsx -> useBillingRedirect extraction (slice 4).
// Pins the Stripe redirect behavior: per ?billing value, the right toast + tab
// navigation + URL cleanup fire on mount, and nothing fires without the param.
function setSearch(search) {
  window.history.replaceState({}, '', '/' + search);
}

describe('useBillingRedirect', () => {
  let addToast, setActiveTab, setSettingsTab;
  beforeEach(() => {
    addToast = vi.fn();
    setActiveTab = vi.fn();
    setSettingsTab = vi.fn();
  });
  afterEach(() => { window.history.replaceState({}, '', '/'); });

  it('billing=success: toasts success, opens Settings>Billing, cleans URL', () => {
    setSearch('?billing=success');
    renderHook(() => useBillingRedirect({ addToast, setActiveTab, setSettingsTab }));
    expect(addToast).toHaveBeenCalledWith('Subscription activated successfully!', 'success');
    expect(setActiveTab).toHaveBeenCalledWith('settings');
    expect(setSettingsTab).toHaveBeenCalledWith('billing');
    expect(window.location.search).toBe('');
  });

  it('billing=cancel: toasts cancel info, opens Settings>Billing', () => {
    setSearch('?billing=cancel');
    renderHook(() => useBillingRedirect({ addToast, setActiveTab, setSettingsTab }));
    expect(addToast).toHaveBeenCalledWith('Checkout cancelled', 'info');
    expect(setActiveTab).toHaveBeenCalledWith('settings');
    expect(setSettingsTab).toHaveBeenCalledWith('billing');
    expect(window.location.search).toBe('');
  });

  it('billing=portal-return: opens Settings>Billing with NO toast', () => {
    setSearch('?billing=portal-return');
    renderHook(() => useBillingRedirect({ addToast, setActiveTab, setSettingsTab }));
    expect(addToast).not.toHaveBeenCalled();
    expect(setActiveTab).toHaveBeenCalledWith('settings');
    expect(setSettingsTab).toHaveBeenCalledWith('billing');
    expect(window.location.search).toBe('');
  });

  it('no billing param: does nothing', () => {
    setSearch('');
    renderHook(() => useBillingRedirect({ addToast, setActiveTab, setSettingsTab }));
    expect(addToast).not.toHaveBeenCalled();
    expect(setActiveTab).not.toHaveBeenCalled();
    expect(setSettingsTab).not.toHaveBeenCalled();
  });
});
