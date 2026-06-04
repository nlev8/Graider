import { describe, it, expect } from 'vitest';
import { getSubjectSectionDefaults, distributeDOK, distributePoints } from '../assessmentDistribution';

// Characterization net for the App.jsx -> utils/assessmentDistribution.js extraction (slice 18).
// Pure helpers; tests pin the load-bearing shape/sum properties. The byte-verbatim workflow
// check proves they equal the original App.jsx definitions.
describe('assessmentDistribution (pure config helpers)', () => {
  it('distributeDOK splits a total ~20/40/30/10 across DOK 1-4 and sums to the total', () => {
    expect(distributeDOK(10)).toEqual({ 1: 2, 2: 4, 3: 3, 4: 1 });
    const d = distributeDOK(20);
    expect(d[1] + d[2] + d[3] + d[4]).toBe(20);
    expect(distributeDOK(0)).toEqual({ 1: 0, 2: 0, 3: 0, 4: 0 });
  });

  it('getSubjectSectionDefaults returns a defaults object for known and unknown subjects', () => {
    expect(getSubjectSectionDefaults('Math')).toBeTypeOf('object');
    expect(getSubjectSectionDefaults('Math')).not.toBeNull();
    // Unknown subject falls through to the default return (still an object, never throws)
    expect(getSubjectSectionDefaults('Totally Unknown Subject')).toBeTypeOf('object');
  });

  it('distributePoints returns an object (point allocation per question type)', () => {
    const pts = distributePoints(30, { mcq: 3, frq: 2 });
    expect(pts).toBeTypeOf('object');
    expect(pts).not.toBeNull();
  });
});
