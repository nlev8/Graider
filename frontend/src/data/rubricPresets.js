/**
 * B.E.S.T. rubric preset definitions for Florida teachers + standard default.
 * Used by OnboardingWizard and Settings > Grading tab.
 */

export const RUBRIC_PRESETS = {
  FL_ELA: {
    name: "B.E.S.T. ELA",
    description: "Florida B.E.S.T. English Language Arts rubric",
    badge: "B.E.S.T.",
    categories: [
      { name: "Reading Comprehension", weight: 30, description: "Understanding of texts and passages" },
      { name: "Written Communication", weight: 25, description: "Clarity, structure, and conventions" },
      { name: "Critical Analysis", weight: 25, description: "Evidence-based reasoning and argumentation" },
      { name: "Vocabulary & Language", weight: 20, description: "Word choice, grammar, and language use" },
    ],
  },
  FL_Math: {
    name: "B.E.S.T. Math",
    description: "Florida B.E.S.T. Mathematics rubric",
    badge: "B.E.S.T.",
    categories: [
      { name: "Conceptual Understanding", weight: 30, description: "Grasp of mathematical concepts" },
      { name: "Procedural Fluency", weight: 30, description: "Accuracy and efficiency of procedures" },
      { name: "Problem-Solving", weight: 25, description: "Application of strategies to solve problems" },
      { name: "Mathematical Reasoning", weight: 15, description: "Logical justification and proof" },
    ],
  },
  FL_Science: {
    name: "B.E.S.T. Science",
    description: "Florida B.E.S.T. Science rubric",
    badge: "B.E.S.T.",
    categories: [
      { name: "Scientific Inquiry", weight: 30, description: "Hypothesis, experiment design, and method" },
      { name: "Content Knowledge", weight: 30, description: "Understanding of scientific concepts" },
      { name: "Data Analysis", weight: 25, description: "Interpreting data, graphs, and evidence" },
      { name: "Communication", weight: 15, description: "Scientific writing and presentation" },
    ],
  },
  FL_History: {
    name: "B.E.S.T. Social Studies",
    description: "Florida B.E.S.T. Social Studies rubric",
    badge: "B.E.S.T.",
    categories: [
      { name: "Historical Knowledge", weight: 30, description: "Factual accuracy and context" },
      { name: "Source Analysis", weight: 25, description: "Primary/secondary source evaluation" },
      { name: "Critical Thinking", weight: 25, description: "Cause and effect, comparison, argumentation" },
      { name: "Communication", weight: 20, description: "Writing clarity and organization" },
    ],
  },
  default: {
    name: "Standard Rubric",
    description: "General-purpose grading rubric",
    badge: null,
    categories: [
      { name: "Content Accuracy", weight: 40, description: "Correctness of answers and information" },
      { name: "Completeness", weight: 25, description: "All parts of the assignment addressed" },
      { name: "Writing Quality", weight: 20, description: "Grammar, spelling, and organization" },
      { name: "Effort", weight: 15, description: "Evidence of thought and engagement" },
    ],
  },
};

/** Maps subject display names to B.E.S.T. category keys. */
export const SUBJECT_TO_CATEGORY = {
  "English Language Arts": "ELA",
  "Mathematics": "Math",
  "Science": "Science",
  "Biology": "Science",
  "Chemistry": "Science",
  "Physics": "Science",
  "US History": "History",
  "World History": "History",
  "Social Studies": "History",
  "Government": "History",
  "Economics": "History",
  "Geography": "History",
};

/**
 * Get the preset key for a given state and subject.
 * Returns e.g. "FL_ELA" or "default".
 */
export function getPresetKey(state, subject) {
  if (state !== "FL") return "default";
  const category = SUBJECT_TO_CATEGORY[subject];
  if (!category) return "default";
  const key = "FL_" + category;
  return RUBRIC_PRESETS[key] ? key : "default";
}

/**
 * Get the full preset object for a state + subject combo.
 */
export function getPresetForStateSubject(state, subject) {
  const key = getPresetKey(state, subject);
  return RUBRIC_PRESETS[key];
}
