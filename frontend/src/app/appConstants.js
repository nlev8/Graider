/*
 * appConstants — static data moved out of App.jsx in the finale split of the
 * Code Quality campaign (App function 2,677 LOC → ≤300). Every block below is
 * a verbatim move of a plain `const` that was re-created on every App render;
 * hoisting read-only data to module scope is behavior-preserving (the objects
 * were only ever read, never mutated, and appear in no dependency arrays).
 * Source ranges cite pre-split App.jsx @ the finale base commit.
 */

// Marker libraries by subject — verbatim from App.jsx module scope (107-204).
export const markerLibrary = {
  "Social Studies": [
    "Explain:",
    "Describe the significance of:",
    "Compare and contrast:",
    "What were the causes of:",
    "What were the effects of:",
    "Analyze:",
    "In your own words:",
    "Why do you think:",
  ],
  "English/ELA": [
    "Write your response:",
    "Your thesis statement:",
    "Analyze the text:",
    "Provide evidence:",
    "Explain the theme:",
    "Character analysis:",
    "Authors purpose:",
  ],
  Math: [
    "Show your work:",
    "Solve:",
    "Calculate:",
    "Prove:",
    "Find the value of:",
    "Graph:",
    "Simplify:",
    "Word Problem:",
  ],
  Science: [
    "Hypothesis:",
    "Data/Observations:",
    "Conclusion:",
    "Procedure:",
    "Variables:",
    "Analysis:",
    "Explain the results:",
  ],
  "US History": [
    "Explain:",
    "Describe:",
    "What was the impact of:",
    "Primary source analysis:",
    "Timeline:",
    "Cause and effect:",
    "Historical significance:",
  ],
  "World History": [
    "Explain:",
    "Describe:",
    "What was the impact of:",
    "Primary source analysis:",
    "Timeline:",
    "Cause and effect:",
    "Historical significance:",
    "Compare civilizations:",
  ],
  Spanish: [
    "Traduce:",
    "Conjugación:",
    "Respuesta:",
    "Escribe en español:",
    "Completa la oración:",
    "Vocabulario:",
    "Lectura:",
    "Conversación:",
  ],
  French: [
    "Traduisez:",
    "Conjugaison:",
    "Répondez:",
    "Écrivez en français:",
    "Complétez la phrase:",
    "Vocabulaire:",
    "Lecture:",
    "Conversation:",
  ],
  "World Languages": [
    "Translate:",
    "Conjugation:",
    "Response:",
    "Write in target language:",
    "Complete the sentence:",
    "Vocabulary:",
    "Reading comprehension:",
    "Conversation:",
  ],
  Other: [
    "Answer:",
    "Explain:",
    "Describe:",
    "Your response:",
    "Short answer:",
    "Essay:",
  ],
};

// Verbatim from App.jsx 286-291 (was inside App()).
// Per-model cost estimates ($ per assignment)
export const MODEL_COST_PER_ASSIGNMENT = {
  "gpt-4o-mini": 0.001, "gpt-4o": 0.015,
  "claude-haiku": 0.002, "claude-sonnet": 0.02,
  "gemini-flash": 0.0005, "gemini-pro": 0.008
};

// Verbatim from App.jsx 348-576 (was inside App()).
// Available EdTech tools that can be selected
export const EDTECH_TOOLS = [
  // Microsoft & Google
  {
    id: "microsoft_365",
    name: "Microsoft 365",
    category: "All",
    description: "Word, Excel, PowerPoint",
  },
  {
    id: "microsoft_teams",
    name: "Microsoft Teams",
    category: "All",
    description: "Collaboration & meetings",
  },
  {
    id: "google_classroom",
    name: "Google Classroom",
    category: "All",
    description: "Assignment management",
  },
  {
    id: "google_slides",
    name: "Google Slides",
    category: "All",
    description: "Presentations",
  },
  {
    id: "google_docs",
    name: "Google Docs",
    category: "All",
    description: "Collaborative writing",
  },
  // LMS & Interactive
  {
    id: "canvas",
    name: "Canvas",
    category: "All",
    description: "Learning management system",
  },
  {
    id: "nearpod",
    name: "Nearpod",
    category: "All",
    description: "Interactive lessons",
  },
  {
    id: "edpuzzle",
    name: "Edpuzzle",
    category: "All",
    description: "Interactive video lessons",
  },
  {
    id: "pear_deck",
    name: "Pear Deck",
    category: "All",
    description: "Interactive slides",
  },
  {
    id: "padlet",
    name: "Padlet",
    category: "All",
    description: "Collaborative boards",
  },
  {
    id: "flipgrid",
    name: "Flip (Flipgrid)",
    category: "All",
    description: "Video discussions",
  },
  // Design & Media
  {
    id: "canva",
    name: "Canva",
    category: "All",
    description: "Design & infographics",
  },
  {
    id: "adobe_express",
    name: "Adobe Express",
    category: "All",
    description: "Creative design tool",
  },
  // Math
  {
    id: "ixl",
    name: "IXL",
    category: "Math/ELA",
    description: "Adaptive practice",
  },
  {
    id: "desmos",
    name: "Desmos",
    category: "Math",
    description: "Graphing calculator & activities",
  },
  {
    id: "geogebra",
    name: "GeoGebra",
    category: "Math",
    description: "Dynamic math software",
  },
  {
    id: "delta_math",
    name: "DeltaMath",
    category: "Math",
    description: "Math practice & videos",
  },
  {
    id: "fl_math_4_all",
    name: "FL Math 4 All",
    category: "Math",
    description: "Florida math resources",
  },
  {
    id: "prodigy",
    name: "Prodigy",
    category: "Math",
    description: "Math game",
  },
  {
    id: "zearn",
    name: "Zearn",
    category: "Math",
    description: "Math curriculum",
  },
  // ELA & Reading
  {
    id: "newsela",
    name: "Newsela",
    category: "ELA/SS",
    description: "Leveled articles",
  },
  {
    id: "commonlit",
    name: "CommonLit",
    category: "ELA",
    description: "Reading passages",
  },
  // Science
  {
    id: "phet",
    name: "PhET Simulations",
    category: "Science/Math",
    description: "Interactive simulations",
  },
  // Social Studies
  {
    id: "dbq_online",
    name: "DBQ Online",
    category: "SS/ELA",
    description: "Document-based questions",
  },
  {
    id: "cpalms",
    name: "CPALMS",
    category: "All",
    description: "Florida standards & resources",
  },
  // General Learning
  {
    id: "brainpop",
    name: "BrainPOP",
    category: "All",
    description: "Animated educational videos",
  },
  {
    id: "edgenuity",
    name: "Edgenuity",
    category: "All",
    description: "Online curriculum",
  },
  {
    id: "everfi",
    name: "EVERFI",
    category: "Life Skills",
    description: "Financial literacy & digital citizenship",
  },
  {
    id: "progress_learning",
    name: "Progress Learning",
    category: "All",
    description: "Standards-based practice",
  },
  {
    id: "hour_of_code",
    name: "Hour of Code",
    category: "CS",
    description: "Coding activities",
  },
  // Quiz & Games
  {
    id: "kahoot",
    name: "Kahoot",
    category: "All",
    description: "Game-based quizzes",
  },
  {
    id: "quizlet",
    name: "Quizlet",
    category: "All",
    description: "Flashcards & study sets",
  },
  {
    id: "blooket",
    name: "Blooket",
    category: "All",
    description: "Game-based review",
  },
  {
    id: "gimkit",
    name: "Gimkit",
    category: "All",
    description: "Live learning games",
  },
  // Video
  {
    id: "khan_academy",
    name: "Khan Academy",
    category: "All",
    description: "Video lessons & practice",
  },
  {
    id: "youtube",
    name: "YouTube",
    category: "All",
    description: "Educational videos",
  },
];

// Resizable Results-table default column widths — verbatim from App.jsx 617.
export const defaultColPercents = [13, 14, 11, 6, 10, 6, 13, 10, 17];

// Verbatim from App.jsx 758-763 (was inside App()).
// Highlight colors
export const HIGHLIGHT_COLORS = {
  start: { bg: "rgba(34, 197, 94, 0.4)", border: "#22c55e", label: "Start" },
  end: { bg: "rgba(239, 68, 68, 0.4)", border: "#ef4444", label: "End" },
  exclude: { bg: "rgba(251, 146, 60, 0.4)", border: "#fb923c", label: "Exclude" },
};

// Planner domain-name maps — verbatim from App.jsx 1676-1688 (was inside App()).
export const domainNamesBySubject = {
  Math: { NSO: "Number Sense & Ops", AR: "Algebraic Reasoning", GR: "Geometric Reasoning", DP: "Data & Probability", F: "Functions", T: "Trigonometry", LT: "Logic & Thinking", FL: "Financial Literacy" },
  Science: { N: "Nature of Science", P: "Physical Science", L: "Life Science", E: "Earth & Space" },
  "English/ELA": { R: "Reading", C: "Communication", V: "Vocabulary" },
  "Social Studies": { A: "American History", C: "Civics & Gov", E: "Economics", G: "Geography", W: "World History" },
  Civics: { C: "Civics & Gov", E: "Economics" },
  Geography: { G: "Geography" },
  "US History": { A: "American History" },
  "World History": { W: "World History" },
  Spanish: { C: "Communication", CU: "Culture", CO: "Connections", CM: "Comparisons", CT: "Communities" },
  French: { C: "Communication", CU: "Culture", CO: "Connections", CM: "Comparisons", CT: "Communities" },
  "World Languages": { C: "Communication", CU: "Culture", CO: "Connections", CM: "Comparisons", CT: "Communities" },
};
