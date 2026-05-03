/**
 * Tests for PasswordResetScreen — uses supabase.auth.updateUser. Mocks
 * the supabase client at module level (vi.mock).
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock supabase BEFORE importing the component under test
vi.mock('../services/supabase', () => ({
  supabase: {
    auth: {
      updateUser: vi.fn(),
    },
  },
}));

import PasswordResetScreen from '../components/PasswordResetScreen';
import { supabase } from '../services/supabase';

beforeEach(() => {
  supabase.auth.updateUser.mockReset();
});

describe('PasswordResetScreen', () => {
  it('renders the form with two password fields and a submit button', () => {
    render(<PasswordResetScreen onDone={() => {}} />);
    expect(screen.getByText('Set your new password')).toBeDefined();
    expect(screen.getByPlaceholderText('Enter new password')).toBeDefined();
    expect(screen.getByPlaceholderText('Confirm new password')).toBeDefined();
    expect(screen.getByText('Set New Password')).toBeDefined();
  });

  it('shows error when new password is shorter than 6 chars', async () => {
    const { container } = render(<PasswordResetScreen onDone={() => {}} />);
    fireEvent.change(screen.getByPlaceholderText('Enter new password'), { target: { value: 'abc' } });
    fireEvent.change(screen.getByPlaceholderText('Confirm new password'), { target: { value: 'abc' } });
    fireEvent.submit(container.querySelector('form'));
    await waitFor(() => {
      expect(screen.getByText(/at least 6 characters/)).toBeDefined();
    });
    expect(supabase.auth.updateUser).not.toHaveBeenCalled();
  });

  it('shows error when passwords do not match', async () => {
    const { container } = render(<PasswordResetScreen onDone={() => {}} />);
    fireEvent.change(screen.getByPlaceholderText('Enter new password'), { target: { value: 'abcdef' } });
    fireEvent.change(screen.getByPlaceholderText('Confirm new password'), { target: { value: 'xyzxyz' } });
    fireEvent.submit(container.querySelector('form'));
    await waitFor(() => {
      expect(screen.getByText(/Passwords do not match/)).toBeDefined();
    });
    expect(supabase.auth.updateUser).not.toHaveBeenCalled();
  });

  it('calls supabase.auth.updateUser with the new password', async () => {
    supabase.auth.updateUser.mockResolvedValue({ error: null });
    const { container } = render(<PasswordResetScreen onDone={() => {}} />);
    fireEvent.change(screen.getByPlaceholderText('Enter new password'), { target: { value: 'goodpass' } });
    fireEvent.change(screen.getByPlaceholderText('Confirm new password'), { target: { value: 'goodpass' } });
    fireEvent.submit(container.querySelector('form'));
    await waitFor(() => {
      expect(supabase.auth.updateUser).toHaveBeenCalledWith({ password: 'goodpass' });
    });
  });

  it('shows the success state after a successful update', async () => {
    supabase.auth.updateUser.mockResolvedValue({ error: null });
    const { container } = render(<PasswordResetScreen onDone={() => {}} />);
    fireEvent.change(screen.getByPlaceholderText('Enter new password'), { target: { value: 'goodpass' } });
    fireEvent.change(screen.getByPlaceholderText('Confirm new password'), { target: { value: 'goodpass' } });
    fireEvent.submit(container.querySelector('form'));
    await waitFor(() => {
      expect(screen.getByText(/Password updated successfully/)).toBeDefined();
      expect(screen.getByText('Continue to App')).toBeDefined();
    });
  });

  it('shows the supabase error message when updateUser fails', async () => {
    supabase.auth.updateUser.mockResolvedValue({ error: { message: 'auth bad' } });
    const { container } = render(<PasswordResetScreen onDone={() => {}} />);
    fireEvent.change(screen.getByPlaceholderText('Enter new password'), { target: { value: 'goodpass' } });
    fireEvent.change(screen.getByPlaceholderText('Confirm new password'), { target: { value: 'goodpass' } });
    fireEvent.submit(container.querySelector('form'));
    await waitFor(() => {
      expect(screen.getByText('auth bad')).toBeDefined();
    });
  });

  it('Continue to App button calls onDone after success', async () => {
    supabase.auth.updateUser.mockResolvedValue({ error: null });
    const onDone = vi.fn();
    const { container } = render(<PasswordResetScreen onDone={onDone} />);
    fireEvent.change(screen.getByPlaceholderText('Enter new password'), { target: { value: 'goodpass' } });
    fireEvent.change(screen.getByPlaceholderText('Confirm new password'), { target: { value: 'goodpass' } });
    fireEvent.submit(container.querySelector('form'));
    await waitFor(() => {
      expect(screen.getByText('Continue to App')).toBeDefined();
    });
    fireEvent.click(screen.getByText('Continue to App'));
    expect(onDone).toHaveBeenCalledTimes(1);
  });
});
