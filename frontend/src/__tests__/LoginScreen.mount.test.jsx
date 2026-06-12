import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import LoginScreen from '../components/LoginScreen';

// Content-asserting mount test for LoginScreen. Added with the CQ wave-8
// split of LoginScreen.jsx into login-screen/* (mirrors
// SettingsPrivacy.mount.test.jsx from wave 4, for the same reason): before
// this test, the only renderer was the innerHTML-length smoke in
// smoke.test.jsx, which passes even if a split leaves an unimported view
// component or a mis-threaded prop that blanks the auth surface at runtime.
// This test asserts real content from every extracted view actually mounts,
// in both the sign-in and forgot-password branches.

vi.mock('../services/supabase', () => ({
  supabase: {
    auth: {
      signInWithPassword: vi.fn().mockResolvedValue({ data: { user: {} }, error: null }),
      signInWithOAuth: vi.fn().mockResolvedValue({ error: null }),
      resetPasswordForEmail: vi.fn().mockResolvedValue({ error: null }),
    },
  },
}));

vi.mock('../services/posthog', () => ({
  track: vi.fn(),
}));

describe('LoginScreen mounts with content from every extracted view', () => {
  it('renders the sign-in view: form, OAuth buttons, and SSO buttons', () => {
    render(<LoginScreen onLogin={vi.fn()} theme="dark" toggleTheme={vi.fn()} />);

    // Orchestrator header + footer links
    expect(screen.getByText('Sign in to continue')).toBeTruthy();
    expect(screen.getByText(/go to Student Portal/)).toBeTruthy();
    expect(screen.getByText('District Administration')).toBeTruthy();
    // SignInView — email/password form
    expect(screen.getByText('Email')).toBeTruthy();
    expect(screen.getByText('Password')).toBeTruthy();
    expect(screen.getByPlaceholderText('Enter your password')).toBeTruthy();
    expect(screen.getByText('Sign In')).toBeTruthy();
    expect(screen.getByText('Forgot password?')).toBeTruthy();
    expect(screen.getByText('Need an account?')).toBeTruthy();
    // SignInView — OAuth + SSO buttons
    expect(screen.getByText('or continue with')).toBeTruthy();
    expect(screen.getByText('Google')).toBeTruthy();
    expect(screen.getByText('Microsoft')).toBeTruthy();
    expect(screen.getByText('Log in with ClassLink')).toBeTruthy();
    expect(screen.getByText('Log in with Clever')).toBeTruthy();
    // ForgotPasswordView — early-returns null while showForgot is false
    expect(screen.queryByText('Send Reset Link')).toBeNull();
  });

  it('switches to the forgot-password view and shows the sent confirmation', async () => {
    render(<LoginScreen onLogin={vi.fn()} theme="dark" toggleTheme={vi.fn()} />);

    fireEvent.click(screen.getByText('Forgot password?'));

    // ForgotPasswordView form branch; SignInView early-returns null
    expect(screen.getByText('Reset your password')).toBeTruthy();
    expect(screen.getByText('Send Reset Link')).toBeTruthy();
    expect(screen.getByText('Back to Sign In')).toBeTruthy();
    expect(screen.queryByText('Log in with Clever')).toBeNull();

    // Submit → forgotSent branch
    fireEvent.change(screen.getByPlaceholderText('you@school.edu'), {
      target: { value: 'teacher@school.edu' },
    });
    fireEvent.click(screen.getByText('Send Reset Link'));
    await waitFor(() => {
      expect(screen.getByText('Reset link sent! Check your email.')).toBeTruthy();
    });
  });
});
