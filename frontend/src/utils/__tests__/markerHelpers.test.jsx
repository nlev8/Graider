import { describe, it, expect } from 'vitest';
import {
  getMarkerText, getEndMarker, getMarkerPoints, getMarkerType,
  calculateTotalPoints, normalizeMarker,
} from '../markerHelpers';

// Characterization net for the App.jsx -> utils/markerHelpers.js extraction (slice 14).
// Pure marker accessors; tests pin each accessor's string-vs-object behavior and defaults.
describe('markerHelpers (pure marker accessors)', () => {
  it('getMarkerText: string passthrough, else .start', () => {
    expect(getMarkerText('hi')).toBe('hi');
    expect(getMarkerText({ start: 'x' })).toBe('x');
  });
  it('getEndMarker: object .end, else null', () => {
    expect(getEndMarker({ end: 'e' })).toBe('e');
    expect(getEndMarker('s')).toBe(null);
  });
  it('getMarkerPoints: default 10', () => {
    expect(getMarkerPoints('s')).toBe(10);
    expect(getMarkerPoints({ points: 5 })).toBe(5);
    expect(getMarkerPoints({})).toBe(10);
  });
  it('getMarkerType: default "written"', () => {
    expect(getMarkerType('s')).toBe('written');
    expect(getMarkerType({ type: 'vocab' })).toBe('vocab');
  });
  it('calculateTotalPoints: sums marker points + effort points', () => {
    expect(calculateTotalPoints([{ points: 5 }, { points: 5 }], 15)).toBe(25);
    expect(calculateTotalPoints([], 15)).toBe(15);
    expect(calculateTotalPoints(null)).toBe(15); // default effortPoints
  });
  it('normalizeMarker: upgrades string/legacy markers to {start,points,type}', () => {
    expect(normalizeMarker('s')).toEqual({ start: 's', points: 10, type: 'written' });
    expect(normalizeMarker({ start: 'a' })).toEqual({ start: 'a', points: 10, type: 'written' });
    const full = { start: 'b', points: 7, type: 'vocab' };
    expect(normalizeMarker(full)).toBe(full); // already-normalized passthrough
  });
});
