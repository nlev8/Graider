/*
 * markerHelpers — pure marker-accessor utilities, pushed down from the App.jsx shell
 * (App.jsx decomposition slice 14). PURE functions (marker in, value out; no React/state/
 * closure). calculateTotalPoints calls the sibling getMarkerPoints. Bodies moved VERBATIM
 * (de-indented to module scope).
 */
const getMarkerText = (marker) => {
  return typeof marker === 'string' ? marker : marker.start;
};

// Helper to get end marker (if exists)
const getEndMarker = (marker) => {
  return typeof marker === 'object' ? marker.end : null;
};

// Get marker points (default 10 if not specified)
const getMarkerPoints = (marker) => {
  if (typeof marker === 'string') return 10;
  return marker.points || 10;
};

// Get marker type (default "written")
const getMarkerType = (marker) => {
  if (typeof marker === 'string') return 'written';
  return marker.type || 'written';
};

// Calculate total points from markers
const calculateTotalPoints = (markers, effortPoints = 15) => {
  const markerTotal = (markers || []).reduce((sum, m) => sum + getMarkerPoints(m), 0);
  return markerTotal + effortPoints;
};

// Convert old string marker to new format
const normalizeMarker = (marker) => {
  if (typeof marker === 'string') {
    return { start: marker, points: 10, type: 'written' };
  }
  if (marker.start && !marker.points) {
    return { ...marker, points: 10, type: marker.type || 'written' };
  }
  return marker;
};

export {
  getMarkerText,
  getEndMarker,
  getMarkerPoints,
  getMarkerType,
  calculateTotalPoints,
  normalizeMarker,
};
