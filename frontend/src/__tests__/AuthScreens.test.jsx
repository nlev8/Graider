import React from 'react';
import { render, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { AuthLoadingScreen, ApprovalCheckingScreen, NotApprovedScreen } from '../components/AuthScreens';

describe('AuthScreens', () => {
  it('AuthLoadingScreen renders', () => {
    const { container } = render(<AuthLoadingScreen />);
    expect(container.firstChild).toBeTruthy();
  });

  it('ApprovalCheckingScreen renders the checking message', () => {
    const { getByText } = render(<ApprovalCheckingScreen />);
    expect(getByText(/Checking account status/i)).toBeTruthy();
  });

  it('NotApprovedScreen renders pending copy and Sign Out invokes handleLogout', () => {
    const handleLogout = vi.fn();
    const { getByText } = render(<NotApprovedScreen handleLogout={handleLogout} />);
    expect(getByText(/Account Pending Approval/i)).toBeTruthy();
    fireEvent.click(getByText('Sign Out'));
    expect(handleLogout).toHaveBeenCalledTimes(1);
  });
});
