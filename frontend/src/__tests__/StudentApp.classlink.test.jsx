/**
 * ClassLink student SSO glue — mirrors StudentApp.cleverSelect.test.jsx.
 * Backend security is unit-tested in Python; this guards the SPA wiring:
 * /student?classlink_select=1&sel=… renders the picker and finalizes against
 * /api/classlink/select-class.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import StudentApp from '../components/StudentApp';

function mockFetch() {
  return vi.fn((url, opts) => {
    const u = String(url);
    if (u.indexOf('/api/classlink/select-class') === 0 && (!opts || opts.method !== 'POST')) {
      return Promise.resolve({ json: () => Promise.resolve({ classes: [
        { class_id: 'cl-1', name: 'History 10', subject: 'history' },
        { class_id: 'cl-2', name: 'Bio 10', subject: 'bio' },
      ] }) });
    }
    if (u.indexOf('/api/classlink/select-class') === 0 && opts && opts.method === 'POST') {
      return Promise.resolve({ json: () => Promise.resolve({ token: 'cl-final' }) });
    }
    if (u.indexOf('/api/student/session') === 0) {
      return Promise.resolve({ json: () => Promise.resolve({
        valid: true, student: { first_name: 'Sam' }, class_info: { name: 'Bio 10' },
      }) });
    }
    return Promise.resolve({ json: () => Promise.resolve({}) });
  });
}

describe('StudentApp ClassLink multi-enrollment picker', () => {
  beforeEach(() => {
    localStorage.clear();
    window.history.pushState({}, '', '/student?classlink_select=1&sel=cltok-1');
  });

  it('renders candidate classes from the ClassLink selection token', async () => {
    global.fetch = mockFetch();
    render(<StudentApp />);
    expect(await screen.findByText('History 10')).toBeTruthy();
    expect(await screen.findByText('Bio 10')).toBeTruthy();
  });

  it('finalizes against /api/classlink/select-class with the chosen class', async () => {
    const fetchMock = mockFetch();
    global.fetch = fetchMock;
    render(<StudentApp />);
    fireEvent.click(await screen.findByText('Bio 10'));
    await waitFor(() => {
      const post = fetchMock.mock.calls.find(
        (c) => String(c[0]).indexOf('/api/classlink/select-class') === 0 &&
               c[1] && c[1].method === 'POST'
      );
      expect(post).toBeTruthy();
      expect(JSON.parse(post[1].body)).toEqual({ selection_token: 'cltok-1', class_id: 'cl-2' });
    });
    await waitFor(() => expect(localStorage.getItem('student_token')).toBe('cl-final'));
  });
});
