/**
 * Task A frontend — Clever multi-enrollment class picker.
 *
 * When the OAuth callback redirects a multi-enrolled student to
 * /student?clever_select=1&sel=<token>, StudentApp must:
 *   1. GET /api/clever/select-class?selection_token=… → render the
 *      candidate classes (NOT silently log in).
 *   2. On pick, POST {selection_token, class_id} → receive a session
 *      token → establish the session like the normal Clever flow.
 *
 * Security logic lives in the backend (fully unit-tested, 7 tests);
 * this guards the presentational glue + the correct request shape.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import StudentApp from '../components/StudentApp';

function mockFetch() {
  return vi.fn((url, opts) => {
    const u = String(url);
    if (u.indexOf('/api/clever/select-class') === 0 && (!opts || opts.method !== 'POST')) {
      return Promise.resolve({ json: () => Promise.resolve({ classes: [
        { class_id: 'cls-001', name: 'Math 9', subject: 'math' },
        { class_id: 'cls-002', name: 'Science 9', subject: 'science' },
      ] }) });
    }
    if (u.indexOf('/api/clever/select-class') === 0 && opts && opts.method === 'POST') {
      return Promise.resolve({ json: () => Promise.resolve({ token: 'tok-final' }) });
    }
    if (u.indexOf('/api/student/session') === 0) {
      return Promise.resolve({ json: () => Promise.resolve({
        valid: true, student: { first_name: 'Jane' }, class_info: { name: 'Science 9' },
      }) });
    }
    return Promise.resolve({ json: () => Promise.resolve({}) });
  });
}

describe('StudentApp Clever multi-enrollment picker', () => {
  beforeEach(() => {
    localStorage.clear();
    window.history.pushState({}, '', '/student?clever_select=1&sel=seltok-1');
  });

  it('renders the candidate classes from the selection token', async () => {
    global.fetch = mockFetch();
    render(<StudentApp />);
    expect(await screen.findByText('Math 9')).toBeTruthy();
    expect(await screen.findByText('Science 9')).toBeTruthy();
  });

  it('finalizes with the chosen class_id and establishes the session', async () => {
    const fetchMock = mockFetch();
    global.fetch = fetchMock;
    render(<StudentApp />);

    const science = await screen.findByText('Science 9');
    fireEvent.click(science);

    await waitFor(() => {
      const post = fetchMock.mock.calls.find(
        (c) => String(c[0]).indexOf('/api/clever/select-class') === 0 &&
               c[1] && c[1].method === 'POST'
      );
      expect(post).toBeTruthy();
      expect(JSON.parse(post[1].body)).toEqual({
        selection_token: 'seltok-1', class_id: 'cls-002',
      });
    });
    await waitFor(() => expect(localStorage.getItem('student_token')).toBe('tok-final'));
  });
});
