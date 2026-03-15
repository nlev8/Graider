/**
 * Test data for Playwright E2E — mirrors the 5 load-test personas
 * but drives through the actual browser UI.
 */

export const TEACHERS = [
  {
    id: 'teacher-test-001',
    name: 'Ms. Rivera',
    subject: 'US History',
    grade: '8',
    roster: 'roster_history_8.csv',
    rubric: {
      categories: [
        { name: 'Historical Accuracy', weight: 30, description: 'Correct facts and dates' },
        { name: 'Analysis & Evidence', weight: 30, description: 'Uses primary sources' },
        { name: 'Writing Quality', weight: 20, description: 'Clear thesis, paragraphs' },
        { name: 'Completeness', weight: 20, description: 'All questions answered' },
      ],
    },
    globalNotes: 'Focus on critical thinking and source analysis. 8th grade US History.',
    lessonTopic: 'The American Revolution',
  },
  {
    id: 'teacher-test-002',
    name: 'Mr. Thompson',
    subject: 'Algebra I',
    grade: '9',
    roster: 'roster_math_6.csv',
    rubric: {
      categories: [
        { name: 'Problem Solving', weight: 35, description: 'Correct method and answer' },
        { name: 'Work Shown', weight: 30, description: 'All steps visible' },
        { name: 'Mathematical Notation', weight: 20, description: 'Proper symbols and format' },
        { name: 'Completeness', weight: 15, description: 'All problems attempted' },
      ],
    },
    globalNotes: 'Students must show all work. Partial credit for correct methods.',
    lessonTopic: 'Solving Quadratic Equations',
  },
  {
    id: 'teacher-test-003',
    name: 'Mrs. Chen',
    subject: 'English Language Arts',
    grade: '7',
    roster: 'roster_ela_7.csv',
    rubric: {
      categories: [
        { name: 'Thesis & Argument', weight: 25, description: 'Clear central claim' },
        { name: 'Evidence & Support', weight: 25, description: 'Textual evidence cited' },
        { name: 'Organization', weight: 25, description: 'Logical flow and transitions' },
        { name: 'Grammar & Mechanics', weight: 25, description: 'Correct grammar and spelling' },
      ],
    },
    globalNotes: 'Grade 7 ELA — essays should cite at least 2 sources.',
    lessonTopic: 'Persuasive Essay Writing',
  },
];

/** Sample assignment config for the Builder tab */
export const SAMPLE_ASSIGNMENT = {
  title: 'Chapter 5 Review Questions',
  sections: [
    {
      name: 'Vocabulary',
      type: 'vocab_term',
      questions: [
        { term: 'Democracy', definition: 'Government by the people' },
        { term: 'Republic', definition: 'Representative form of government' },
      ],
    },
    {
      name: 'Short Answer',
      type: 'numbered_question',
      questions: [
        { text: 'Explain the significance of the Declaration of Independence.', points: 10 },
        { text: 'Compare and contrast the Federalists and Anti-Federalists.', points: 10 },
      ],
    },
  ],
};
