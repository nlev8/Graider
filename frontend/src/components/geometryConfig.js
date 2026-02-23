/**
 * geometryConfig.js — Formula maps, label maps, dimension configs for InteractiveGeometry.
 * Supports 8 geometry modes: area, perimeter, pythagorean, volume, surface_area, angles, similarity, trig
 */

export const GEOMETRY_TYPES = new Set([
  'geometry', 'triangle', 'rectangle', 'circle', 'trapezoid', 'parallelogram',
  'rectangular_prism', 'cylinder', 'cone', 'pyramid', 'sphere', 'regular_polygon',
  'pythagorean', 'angles', 'similarity', 'trig'
]);

const FORMULAS = {
  area: {
    triangle: 'A = \u00BD \u00D7 b \u00D7 h',
    rectangle: 'A = l \u00D7 w',
    circle: 'A = \u03C0r\u00B2',
    trapezoid: 'A = \u00BD(a + b) \u00D7 h',
    parallelogram: 'A = b \u00D7 h',
    regular_polygon: 'A = \u00BD \u00D7 n \u00D7 s \u00D7 a',
  },
  perimeter: {
    triangle: 'P = a + b + c',
    rectangle: 'P = 2l + 2w',
    circle: 'C = 2\u03C0r',
    regular_polygon: 'P = n \u00D7 s',
  },
  pythagorean: {
    triangle: 'a\u00B2 + b\u00B2 = c\u00B2',
  },
  volume: {
    rectangular_prism: 'V = l \u00D7 w \u00D7 h',
    cylinder: 'V = \u03C0r\u00B2h',
    cone: 'V = \u2153\u03C0r\u00B2h',
    pyramid: 'V = \u2153b\u00B2h',
    sphere: 'V = \u2154\u03C0r\u00B3',
  },
  surface_area: {
    rectangular_prism: 'SA = 2(lw + lh + wh)',
    cylinder: 'SA = 2\u03C0r\u00B2 + 2\u03C0rh',
    cone: 'SA = \u03C0r\u00B2 + \u03C0rl',
    pyramid: 'SA = b\u00B2 + 2bl',
    sphere: 'SA = 4\u03C0r\u00B2',
  },
  lateral_area: {
    cone: 'LA = \u03C0rl',
    pyramid: 'LA = 2bl',
  },
  angles: {
    triangle: '\u2220\u2081 + \u2220\u2082 + \u2220\u2083 = 180\u00B0',
  },
  decompose: {
    regular_polygon: 'A = n \u00D7 (\u00BD \u00D7 s \u00D7 a)',
  },
  similarity: {
    triangle: 'Corresponding sides are proportional',
  },
  trig: {
    triangle: null, // set dynamically based on trigFunc
  },
};

const TRIG_FORMULAS = {
  sin: 'sin(\u03B8) = opposite / hypotenuse',
  cos: 'cos(\u03B8) = adjacent / hypotenuse',
  tan: 'tan(\u03B8) = opposite / adjacent',
};

const LABELS = {
  area: { label: 'Area =', unit: 'square units' },
  perimeter: { label: 'Perimeter =', unit: 'units' },
  pythagorean: { label: 'Missing side =', unit: 'units' },
  volume: { label: 'Volume =', unit: 'cubic units' },
  surface_area: { label: 'Surface Area =', unit: 'square units' },
  lateral_area: { label: 'Lateral Area =', unit: 'square units' },
  angles: { label: 'Missing angle =', unit: 'degrees' },
  similarity: { label: 'Missing side =', unit: 'units' },
  trig: { label: 'Missing value =', unit: 'units' },
  decompose: { label: 'Area =', unit: 'square units' },
};

/**
 * Get formula string for display.
 * @param {string} mode - area|perimeter|pythagorean|volume|surface_area|angles|similarity|trig
 * @param {string} type - shape type (triangle, rectangle, circle, etc.)
 * @param {string} [trigFunc] - sin|cos|tan (only for trig mode)
 * @returns {string}
 */
export function getFormula(mode, type, trigFunc) {
  if (mode === 'trig') {
    return TRIG_FORMULAS[trigFunc] || TRIG_FORMULAS.sin;
  }
  if (mode === 'perimeter' && type === 'circle') {
    return 'C = 2\u03C0r (Circumference)';
  }
  const modeFormulas = FORMULAS[mode];
  if (!modeFormulas) return '';
  return modeFormulas[type] || '';
}

/**
 * Get answer label and unit for the answer field.
 * @param {string} mode
 * @param {string} type
 * @returns {{ label: string, unit: string }}
 */
export function getAnswerLabel(mode, type) {
  if (mode === 'perimeter' && type === 'circle') {
    return { label: 'Circumference =', unit: 'units' };
  }
  return LABELS[mode] || { label: 'Answer =', unit: '' };
}

/**
 * Get SVG canvas dimensions based on mode.
 * @param {string} mode
 * @returns {{ width: number, height: number }}
 */
export function getSvgDimensions(mode) {
  switch (mode) {
    case 'volume':
    case 'surface_area':
      return { width: 320, height: 240 };
    case 'similarity':
      return { width: 500, height: 220 };
    case 'decompose':
      return { width: 320, height: 280 };
    default:
      return { width: 300, height: 200 };
  }
}
