/*
 * assessmentDistribution — pure assessment-config distribution helpers, pushed down from
 * the App.jsx shell (App.jsx decomposition slice 18). PURE functions (inputs -> object, no
 * React/state/closure): getSubjectSectionDefaults(subject), distributeDOK(total),
 * distributePoints(totalPoints, questionTypes). The impure distributeQuestions (which reads
 * assessmentConfig) and the config.subject effect stayed in App; the effect imports these.
 * Bodies moved VERBATIM (de-indented to module scope; no template literals so de-indent is
 * content-safe).
 */
const getSubjectSectionDefaults = (subject) => {
  const s = (subject || '').toLowerCase();
  const isMath = s.includes('math') || s.includes('algebra') || s.includes('geometry') || s.includes('calculus') || s.includes('statistics');
  const isScience = s.includes('science') || s.includes('biology') || s.includes('chemistry') || s.includes('physics') || s.includes('earth');
  const isELA = s.includes('ela') || s.includes('english') || s.includes('reading') || s.includes('writing') || s.includes('language arts') || s.includes('literature');
  const isWorldLang = s.includes('spanish') || s.includes('french') || s.includes('world lang') || s.includes('german') || s.includes('italian') || s.includes('portuguese') || s.includes('chinese') || s.includes('japanese');
  const isSocialStudies = s.includes('history') || s.includes('social') || s.includes('civics') || s.includes('economics') || s.includes('geography') || s.includes('government');

  if (isMath) {
    return {
      multiple_choice: true,
      short_answer: true,
      math_computation: true,
      geometry_visual: true,
      graphing: true,
      data_analysis: true,
      extended_writing: false,
      vocabulary: false,
      true_false: false,
    };
  }
  if (isScience) {
    return {
      multiple_choice: true,
      short_answer: true,
      math_computation: false,
      geometry_visual: false,
      graphing: true,
      data_analysis: true,
      extended_writing: false,
      vocabulary: true,
      true_false: false,
    };
  }
  if (isELA) {
    return {
      multiple_choice: true,
      short_answer: true,
      math_computation: false,
      geometry_visual: false,
      graphing: false,
      data_analysis: false,
      extended_writing: true,
      vocabulary: true,
      true_false: false,
    };
  }
  if (isWorldLang) {
    return {
      multiple_choice: true,
      short_answer: true,
      math_computation: false,
      geometry_visual: false,
      graphing: false,
      data_analysis: false,
      extended_writing: true,
      vocabulary: true,
      true_false: true,
    };
  }
  if (isSocialStudies) {
    return {
      multiple_choice: true,
      short_answer: true,
      math_computation: false,
      geometry_visual: false,
      graphing: false,
      data_analysis: false,
      extended_writing: true,
      vocabulary: true,
      true_false: true,
    };
  }
  // Default — generic
  return {
    multiple_choice: true,
    short_answer: true,
    math_computation: false,
    geometry_visual: false,
    graphing: false,
    data_analysis: false,
    extended_writing: true,
    vocabulary: false,
    true_false: false,
  };
};

// Update assessment section categories when subject changes. The

const distributeDOK = (total) => {
  // Standard distribution: 20% DOK1, 40% DOK2, 30% DOK3, 10% DOK4
  const dok1 = Math.round(total * 0.20);
  const dok2 = Math.round(total * 0.40);
  const dok3 = Math.round(total * 0.30);
  const dok4 = total - dok1 - dok2 - dok3; // remainder
  return {
    "1": Math.max(0, dok1),
    "2": Math.max(0, dok2),
    "3": Math.max(0, dok3),
    "4": Math.max(0, dok4),
  };
};

// Helper function to distribute points per type to reach total
const distributePoints = (totalPoints, questionTypes) => {
  // Base ratios: ER=4, SA=2, MC=TF=Matching=1
  const baseRatios = {
    multiple_choice: 1,
    short_answer: 2,
    true_false: 1,
    matching: 1,
    extended_response: 4,
  };

  // Get active types (count > 0)
  const activeTypes = Object.entries(questionTypes).filter(([, count]) => count > 0);
  if (activeTypes.length === 0) return { ...baseRatios };

  // Calculate weighted sum with base ratios
  let weightedSum = 0;
  activeTypes.forEach(([type, count]) => {
    weightedSum += count * (baseRatios[type] || 1);
  });

  if (weightedSum === 0) return { ...baseRatios };

  // Scale factor to reach target total
  const scale = totalPoints / weightedSum;

  // Apply scale and floor (start low, then add)
  const newPoints = { ...baseRatios };
  activeTypes.forEach(([type]) => {
    newPoints[type] = Math.max(1, Math.floor(baseRatios[type] * scale));
  });

  // Calculate current total
  const calcTotal = () => {
    let total = 0;
    activeTypes.forEach(([type, count]) => {
      total += count * newPoints[type];
    });
    return total;
  };

  // Iteratively adjust to hit target
  // Sort by ratio (highest first) - prefer adding to complex question types
  const sortedByRatio = [...activeTypes].sort((a, b) => (baseRatios[b[0]] || 1) - (baseRatios[a[0]] || 1));

  let iterations = 0;
  while (calcTotal() < totalPoints && iterations < 100) {
    // Add 1 point to the type that gets us closest to target
    let bestType = null;
    let bestDiff = Infinity;

    for (const [type, count] of sortedByRatio) {
      const newTotal = calcTotal() + count;
      const diff = Math.abs(totalPoints - newTotal);
      if (diff < bestDiff && newTotal <= totalPoints) {
        bestDiff = diff;
        bestType = type;
      }
    }

    if (bestType) {
      newPoints[bestType]++;
    } else {
      // Can't get closer without overshooting, pick smallest increment
      const [smallestType] = [...activeTypes].sort((a, b) => a[1] - b[1]);
      if (smallestType) newPoints[smallestType[0]]++;
      break;
    }
    iterations++;
  }

  return newPoints;
};

export {
  getSubjectSectionDefaults,
  distributeDOK,
  distributePoints,
};
