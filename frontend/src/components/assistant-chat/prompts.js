/*
 * Suggested-prompt data for AssistantChat, relocated verbatim from
 * AssistantChat.jsx (CQ wave-3 split; mirrors the wave-1/2 precedent of
 * moving module-level constants out of the component file unchanged).
 */
export const DEFAULT_SUGGESTED = [
  { text: "How is my class doing across the rubric categories?", icon: "Target" },
  { text: "What caused the low grades on the last assignment?", icon: "Search" },
  { text: "What should I teach next based on student performance?", icon: "Lightbulb" },
  { text: "Which students need attention?", icon: "AlertTriangle" },
]

export const DEFAULT_MORE = [
  "What's the class average?",
  "How is [student name] doing?",
  "Which rubric category is my class weakest in?",
  "Compare my class periods on the last assignment",
  "Show students below 60 on Cornell Notes",
  "How much did incomplete sections affect scores?",
  "What were the common feedback themes?",
  "Show assignment statistics",
  "What are students' biggest strengths?",
  "Create a Focus assignment called Quiz 3 worth 100 points",
  "Create a Cornell Notes worksheet about the American Revolution",
  "How do I set up my rubric?",
  "What export options are available?",
  "How does the grading pipeline work?",
]

export const SUBJECT_SUGGESTED = {
  "Math": [
    { text: "Check if 2x+3 is equivalent to 3+2x", icon: "Calculator" },
    { text: "What caused the low grades on the last assignment?", icon: "Search" },
    { text: "What should I teach next based on student performance?", icon: "Lightbulb" },
    { text: "Which students need attention?", icon: "AlertTriangle" },
  ],
  "Science": [
    { text: "How is my class doing across the rubric categories?", icon: "Target" },
    { text: "What caused the low grades on the last assignment?", icon: "Search" },
    { text: "Grade this lab data table against the answer key", icon: "Table" },
    { text: "Which students need attention?", icon: "AlertTriangle" },
  ],
  "Geography": [
    { text: "Check if 48.85N, 2.35E is close enough to Paris", icon: "MapPin" },
    { text: "What caused the low grades on the last assignment?", icon: "Search" },
    { text: "What should I teach next based on student performance?", icon: "Lightbulb" },
    { text: "Which students need attention?", icon: "AlertTriangle" },
  ],
}

export const SUBJECT_MORE = {
  "Math": [
    "Is \\frac{1}{2} equivalent to 0.5?",
    "Grade this math answer: student wrote 3x^2+6x, correct answer is 3x(x+2)",
    "Create a worksheet about solving linear equations",
    "What are the weakest math standards for my class?",
  ],
  "Science": [
    "Compare student lab data against the expected values with 5% tolerance",
    "Create a worksheet about the scientific method",
    "What are the weakest science standards for my class?",
    "Which students struggled most with data analysis?",
  ],
  "Geography": [
    "Is 'Britain' an acceptable answer for 'United Kingdom'?",
    "How far off is 40.7N, 74.0W from New York City?",
    "Create a worksheet about world capitals",
    "What are the weakest geography standards for my class?",
  ],
  "US History": [
    "Create a Cornell Notes worksheet about the Civil War",
    "What are the weakest history standards for my class?",
    "Which students struggled most with source analysis?",
    "Create a Kahoot quiz on the American Revolution",
  ],
  "Social Studies": [
    "Create a worksheet about civic responsibility",
    "What are the weakest social studies standards for my class?",
    "Compare my class periods on the last assignment",
    "Create a Blooket set from the civics standards vocabulary",
  ],
  "ELA": [
    "Create a short-answer worksheet about theme and character development",
    "What are the weakest ELA standards for my class?",
    "Which students struggled most with written communication?",
    "What were the common feedback themes on the essay?",
  ],
  "English/ELA": [
    "Create a short-answer worksheet about theme and character development",
    "What are the weakest ELA standards for my class?",
    "Which students struggled most with written communication?",
    "What were the common feedback themes on the essay?",
  ],
}

export function getSubjectPrompts(subject) {
  if (!subject) return { suggested: DEFAULT_SUGGESTED, more: DEFAULT_MORE }
  const subjectMore = SUBJECT_MORE[subject] || []
  return {
    suggested: SUBJECT_SUGGESTED[subject] || DEFAULT_SUGGESTED,
    more: [...subjectMore, ...DEFAULT_MORE],
  }
}

export const ACCEPTED_FILE_TYPES = '.png,.jpg,.jpeg,.gif,.webp,.pdf,.docx'
