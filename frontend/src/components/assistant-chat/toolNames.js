/*
 * Tool-id → human label map for the tool-call chips, relocated verbatim
 * from inside the AssistantChat component (CQ wave-3 split). It was a
 * plain object literal recreated each render and referenced by nothing
 * else, so hoisting it to module scope is behavior-preserving.
 */
export const toolNameMap = {
  query_grades: 'Querying grades',
  get_student_summary: 'Loading student summary',
  get_class_analytics: 'Analyzing class data',
  get_assignment_stats: 'Getting assignment stats',
  list_assignments: 'Listing assignments',
  analyze_grade_causes: 'Analyzing grade causes',
  get_feedback_patterns: 'Analyzing feedback patterns',
  compare_periods: 'Comparing periods',
  recommend_next_lesson: 'Analyzing for lesson recommendation',
  create_focus_assignment: 'Creating Focus assignment',
  export_grades_csv: 'Exporting CSV',
  generate_worksheet: 'Generating worksheet',
  generate_document: 'Generating document',
  generate_csv: 'Generating CSV file',
  save_document_style: 'Saving document style',
  list_document_styles: 'Checking saved styles',
  save_memory: 'Saving to memory',
  get_standards: 'Looking up standards',
  list_all_standards: 'Loading standards index',
  get_recent_lessons: 'Loading recent lessons',
  get_calendar: 'Checking calendar',
  schedule_lesson: 'Scheduling lesson',
  add_calendar_holiday: 'Adding holiday',
  list_resources: 'Loading resources',
  read_resource: 'Reading document',
}
