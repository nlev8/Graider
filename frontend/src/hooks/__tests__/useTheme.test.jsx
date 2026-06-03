import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, beforeEach } from 'vitest';
import { useTheme } from '../useTheme';

// Characterization net for the App.jsx -> useTheme extraction (slice 1).
// Pins the exact behavior the verbatim move must preserve: default "dark",
// localStorage hydration, the document-body data-theme side effect, and the
// toggle. If a future change alters any of these, this fails before users see it.
describe('useTheme', () => {
  beforeEach(() => {
    localStorage.clear();
    document.body.removeAttribute('data-theme');
  });

  it('defaults to "dark" when nothing is stored', () => {
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe('dark');
  });

  it('hydrates from localStorage("graider-theme") on mount', () => {
    localStorage.setItem('graider-theme', 'light');
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe('light');
  });

  it('applies the theme to document.body[data-theme] and persists it on mount', () => {
    renderHook(() => useTheme());
    expect(document.body.getAttribute('data-theme')).toBe('dark');
    expect(localStorage.getItem('graider-theme')).toBe('dark');
  });

  it('toggleTheme flips dark <-> light and re-runs the persistence effect', () => {
    const { result } = renderHook(() => useTheme());
    act(() => { result.current.toggleTheme(); });
    expect(result.current.theme).toBe('light');
    expect(document.body.getAttribute('data-theme')).toBe('light');
    expect(localStorage.getItem('graider-theme')).toBe('light');

    act(() => { result.current.toggleTheme(); });
    expect(result.current.theme).toBe('dark');
    expect(document.body.getAttribute('data-theme')).toBe('dark');
  });
});
