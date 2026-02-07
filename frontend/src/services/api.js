/**
 * API Service for Graider
 * Handles all API calls to the Flask backend
 */

import { supabase } from './supabase'

const API_BASE = ''  // Empty for same-origin, Vite proxies /api to Flask

/**
 * Get authorization headers with current session token
 */
export async function getAuthHeaders() {
  const { data: { session } } = await supabase.auth.getSession()
  if (session?.access_token) {
    return { 'Authorization': 'Bearer ' + session.access_token }
  }
  return {}
}

/**
 * Generic fetch wrapper with error handling and auth
 */
async function fetchApi(endpoint, options = {}) {
  try {
    const authHeaders = await getAuthHeaders()
    const response = await fetch(API_BASE + endpoint, {
      headers: {
        'Content-Type': 'application/json',
        ...authHeaders,
        ...options.headers,
      },
      ...options,
    })

    if (response.status === 401) {
      window.dispatchEvent(new Event('auth-expired'))
      throw new Error('Session expired. Please log in again.')
    }

    if (!response.ok) {
      throw new Error('API error: ' + response.status)
    }

    return await response.json()
  } catch (error) {
    console.error('API Error (' + endpoint + '):', error)
    throw error
  }
}

// ============ Status & Grading ============

export async function getStatus() {
  return fetchApi('/api/status')
}

export async function startGrading(config) {
  return fetchApi('/api/grade', {
    method: 'POST',
    body: JSON.stringify(config),
  })
}

export async function stopGrading() {
  return fetchApi('/api/stop-grading', {
    method: 'POST',
  })
}

export async function listFiles(folder) {
  return fetchApi('/api/list-files', {
    method: 'POST',
    body: JSON.stringify({ folder }),
  })
}

export async function clearResults(assignment = null) {
  return fetchApi('/api/clear-results', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ assignment }),
  })
}

export async function deleteResult(filename) {
  return fetchApi('/api/delete-result', {
    method: 'POST',
    body: JSON.stringify({ filename }),
  })
}

export async function updateResult(filename, updates) {
  return fetchApi('/api/update-result', {
    method: 'POST',
    body: JSON.stringify({ filename, ...updates }),
  })
}

export async function checkNewFiles(folder, outputFolder) {
  return fetchApi('/api/check-new-files', {
    method: 'POST',
    body: JSON.stringify({ folder, output_folder: outputFolder }),
  })
}

// ============ Settings ============

export async function saveRubric(data) {
  return fetchApi('/api/save-rubric', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function loadRubric() {
  return fetchApi('/api/load-rubric')
}

export async function saveGlobalSettings(data) {
  return fetchApi('/api/save-global-settings', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function loadGlobalSettings() {
  return fetchApi('/api/load-global-settings')
}

// ============ Assignments ============

export async function saveAssignmentConfig(data) {
  return fetchApi('/api/save-assignment-config', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function listAssignments() {
  return fetchApi('/api/list-assignments')
}

export async function loadAssignment(name) {
  return fetchApi(`/api/load-assignment?name=${encodeURIComponent(name)}`)
}

export async function deleteAssignment(name) {
  return fetchApi(`/api/delete-assignment?name=${encodeURIComponent(name)}`, {
    method: 'DELETE',
  })
}

export async function exportAssignment(data) {
  return fetchApi('/api/export-assignment', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

// ============ Documents ============

export async function browse(type = 'folder') {
  return fetchApi(`/api/browse?type=${type}`)
}

export async function parseDocument(file) {
  const formData = new FormData()
  formData.append('file', file)

  const authHeaders = await getAuthHeaders()
  const response = await fetch('/api/parse-document', {
    method: 'POST',
    headers: { ...authHeaders },
    body: formData,
  })

  return response.json()
}

export async function openFolder(folder) {
  return fetchApi('/api/open-folder', {
    method: 'POST',
    body: JSON.stringify({ folder }),
  })
}

// ============ Analytics ============

export async function getAnalytics(period = 'all') {
  const url = period === 'all' ? '/api/analytics' : `/api/analytics?period=${encodeURIComponent(period)}`
  return fetchApi(url)
}

export async function exportDistrictReport() {
  return fetchApi('/api/export-district-report')
}

export async function retranslateFeedback(englishFeedback, targetLanguage = 'spanish') {
  return fetchApi('/api/retranslate-feedback', {
    method: 'POST',
    body: JSON.stringify({ english_feedback: englishFeedback, target_language: targetLanguage }),
  })
}

// ============ Planner ============

export async function getStandards(config) {
  return fetchApi('/api/get-standards', {
    method: 'POST',
    body: JSON.stringify(config),
  })
}

export async function brainstormLessonIdeas(data) {
  return fetchApi('/api/brainstorm-lesson-ideas', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function generateLessonPlan(data) {
  return fetchApi('/api/generate-lesson-plan', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function exportLessonPlan(plan) {
  return fetchApi('/api/export-lesson-plan', {
    method: 'POST',
    body: JSON.stringify({ plan }),
  })
}

export async function saveLessonPlan(lesson, unitName) {
  return fetchApi('/api/save-lesson', {
    method: 'POST',
    body: JSON.stringify({ lesson, unitName }),
  })
}

export async function listLessons() {
  return fetchApi('/api/list-lessons')
}

export async function loadLesson(unit, filename) {
  return fetchApi(`/api/load-lesson?unit=${encodeURIComponent(unit)}&filename=${encodeURIComponent(filename)}`)
}

export async function deleteLesson(unit, filename) {
  return fetchApi(`/api/delete-lesson?unit=${encodeURIComponent(unit)}&filename=${encodeURIComponent(filename)}`, {
    method: 'DELETE',
  })
}

export async function listUnits() {
  return fetchApi('/api/list-units')
}

export async function generateAssignmentFromLesson(lessonPlan, config, assignmentType = 'worksheet') {
  return fetchApi('/api/generate-assignment-from-lesson', {
    method: 'POST',
    body: JSON.stringify({ lessonPlan, config, assignmentType }),
  })
}

export async function exportGeneratedAssignment(assignment, format = 'docx', includeAnswers = false) {
  return fetchApi('/api/export-generated-assignment', {
    method: 'POST',
    body: JSON.stringify({ assignment, format, include_answers: includeAnswers }),
  })
}

// ============ Assessment Generation ============

export async function generateAssessment(standards, config, assessmentConfig, contentSources = []) {
  return fetchApi('/api/generate-assessment', {
    method: 'POST',
    body: JSON.stringify({ standards, config, assessmentConfig, contentSources }),
  })
}

export async function exportAssessment(assessment, includeAnswerKey = false) {
  return fetchApi('/api/export-assessment', {
    method: 'POST',
    body: JSON.stringify({ assessment, includeAnswerKey }),
  })
}

export async function exportAssessmentForPlatform(assessment, platform, templateId = null) {
  return fetchApi('/api/export-assessment-platform', {
    method: 'POST',
    body: JSON.stringify({ assessment, platform, templateId }),
  })
}

export async function gradeAssessmentAnswers(assessment, answers) {
  return fetchApi('/api/grade-assessment-answers', {
    method: 'POST',
    body: JSON.stringify({ assessment, answers }),
  })
}

// ============ Assessment Templates ============

export async function uploadAssessmentTemplate(file, platform, name) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('platform', platform)
  formData.append('name', name)

  const authHeaders = await getAuthHeaders()
  const response = await fetch('/api/upload-assessment-template', {
    method: 'POST',
    headers: { ...authHeaders },
    body: formData,
  })
  return response.json()
}

export async function getAssessmentTemplates() {
  return fetchApi('/api/assessment-templates')
}

export async function deleteAssessmentTemplate(templateId) {
  return fetchApi(`/api/assessment-template/${templateId}`, {
    method: 'DELETE',
  })
}

// ============ Interactive Assignments ============

export async function publishAssignment(assignment) {
  return fetchApi('/api/assignment', {
    method: 'POST',
    body: JSON.stringify({ assignment }),
  })
}

export async function getAssignment(assignmentId) {
  return fetchApi(`/api/assignment/${assignmentId}`)
}

export async function submitAssignment(assignmentId, answers, studentName) {
  return fetchApi(`/api/assignment/${assignmentId}/submit`, {
    method: 'POST',
    body: JSON.stringify({ answers, student_name: studentName }),
  })
}

export async function getAssignmentSubmissions(assignmentId) {
  return fetchApi(`/api/assignment/${assignmentId}/submissions`)
}

// ============ Email ============

export async function sendEmails(results, teacherEmail = '', teacherName = '', emailSignature = '') {
  return fetchApi('/api/send-emails', {
    method: 'POST',
    body: JSON.stringify({
      results,
      teacher_email: teacherEmail,
      teacher_name: teacherName,
      email_signature: emailSignature
    }),
  })
}

export async function updateApproval(filename, approval) {
  return fetchApi('/api/update-approval', {
    method: 'POST',
    body: JSON.stringify({ filename, approval }),
  })
}

export async function updateApprovalsBulk(approvals) {
  return fetchApi('/api/update-approvals-bulk', {
    method: 'POST',
    body: JSON.stringify({ approvals }),
  })
}

// ============ Roster & Period Uploads ============

export async function uploadRoster(file) {
  const formData = new FormData()
  formData.append('file', file)

  const authHeaders = await getAuthHeaders()
  const response = await fetch('/api/upload-roster', {
    method: 'POST',
    headers: { ...authHeaders },
    body: formData,
  })
  return response.json()
}

export async function listRosters() {
  return fetchApi('/api/list-rosters')
}

export async function deleteRoster(filename) {
  return fetchApi('/api/delete-roster', {
    method: 'POST',
    body: JSON.stringify({ filename }),
  })
}

export async function saveRosterMapping(filename, mapping) {
  return fetchApi('/api/save-roster-mapping', {
    method: 'POST',
    body: JSON.stringify({ filename, mapping }),
  })
}

export async function uploadPeriod(file, periodName) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('period_name', periodName)

  const authHeaders = await getAuthHeaders()
  const response = await fetch('/api/upload-period', {
    method: 'POST',
    headers: { ...authHeaders },
    body: formData,
  })
  return response.json()
}

export async function listPeriods() {
  return fetchApi('/api/list-periods')
}

export async function getPeriodStudents(filename) {
  return fetchApi('/api/get-period-students', {
    method: 'POST',
    body: JSON.stringify({ filename }),
  })
}

export async function deletePeriod(filename) {
  return fetchApi('/api/delete-period', {
    method: 'POST',
    body: JSON.stringify({ filename }),
  })
}

export async function updatePeriodLevel(filename, classLevel) {
  return fetchApi('/api/update-period-level', {
    method: 'POST',
    body: JSON.stringify({ filename, class_level: classLevel }),
  })
}

// ============ Supporting Documents ============

export async function uploadSupportDocument(file, docType, description) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('doc_type', docType)
  formData.append('description', description || '')

  const authHeaders = await getAuthHeaders()
  const response = await fetch('/api/upload-document', {
    method: 'POST',
    headers: { ...authHeaders },
    body: formData,
  })
  return response.json()
}

export async function listSupportDocuments() {
  return fetchApi('/api/list-documents')
}

export async function deleteSupportDocument(filename) {
  return fetchApi('/api/delete-document', {
    method: 'POST',
    body: JSON.stringify({ filename }),
  })
}

// ============ Accommodations (IEP/504) ============

export async function getAccommodationPresets() {
  return fetchApi('/api/accommodation-presets')
}

export async function saveAccommodationPreset(preset) {
  return fetchApi('/api/accommodation-presets', {
    method: 'POST',
    body: JSON.stringify(preset),
  })
}

export async function deleteAccommodationPreset(presetId) {
  return fetchApi(`/api/accommodation-presets/${encodeURIComponent(presetId)}`, {
    method: 'DELETE',
  })
}

export async function getStudentAccommodations() {
  return fetchApi('/api/student-accommodations')
}

export async function getStudentAccommodation(studentId) {
  return fetchApi(`/api/student-accommodations/${encodeURIComponent(studentId)}`)
}

export async function setStudentAccommodation(studentId, presets, customNotes = '') {
  return fetchApi(`/api/student-accommodations/${encodeURIComponent(studentId)}`, {
    method: 'POST',
    body: JSON.stringify({ presets, custom_notes: customNotes }),
  })
}

export async function deleteStudentAccommodation(studentId) {
  return fetchApi(`/api/student-accommodations/${encodeURIComponent(studentId)}`, {
    method: 'DELETE',
  })
}

export async function importAccommodations(file, idColumn, accommodationColumn, notesColumn) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('id_column', idColumn)
  formData.append('accommodation_column', accommodationColumn)
  if (notesColumn) formData.append('notes_column', notesColumn)

  const authHeaders = await getAuthHeaders()
  const response = await fetch('/api/import-accommodations', {
    method: 'POST',
    headers: { ...authHeaders },
    body: formData,
  })
  return response.json()
}

export async function exportAccommodations() {
  return fetchApi('/api/export-accommodations')
}

export async function clearAllAccommodations() {
  return fetchApi('/api/clear-accommodations', {
    method: 'POST',
  })
}

export async function getAccommodationStats() {
  return fetchApi('/api/accommodation-stats')
}

// ============ Student Portal ============

export async function publishAssessmentToPortal(assessment, settings = {}) {
  return fetchApi('/api/publish-assessment', {
    method: 'POST',
    body: JSON.stringify({ assessment, settings }),
  })
}

export async function getPublishedAssessments() {
  return fetchApi('/api/teacher/assessments')
}

export async function getAssessmentResults(joinCode) {
  return fetchApi(`/api/teacher/assessment/${joinCode}/results`)
}

export async function toggleAssessmentStatus(joinCode) {
  return fetchApi(`/api/teacher/assessment/${joinCode}/toggle`, {
    method: 'POST',
  })
}

export async function deletePublishedAssessment(joinCode) {
  return fetchApi(`/api/teacher/assessment/${joinCode}`, {
    method: 'DELETE',
  })
}

// Student-facing endpoints
export async function getStudentAssessment(joinCode) {
  return fetchApi(`/api/student/join/${joinCode}`)
}

export async function submitStudentAssessment(joinCode, studentName, answers, timeTakenSeconds) {
  return fetchApi(`/api/student/submit/${joinCode}`, {
    method: 'POST',
    body: JSON.stringify({
      student_name: studentName,
      answers,
      time_taken_seconds: timeTakenSeconds,
    }),
  })
}

// ============ Saved Assessments (Local) ============

export async function saveAssessmentLocally(assessment, name) {
  return fetchApi('/api/save-assessment', {
    method: 'POST',
    body: JSON.stringify({ assessment, name }),
  })
}

export async function listSavedAssessments() {
  return fetchApi('/api/list-saved-assessments')
}

export async function loadSavedAssessment(filename) {
  return fetchApi('/api/load-saved-assessment', {
    method: 'POST',
    body: JSON.stringify({ filename }),
  })
}

export async function deleteSavedAssessment(filename) {
  return fetchApi('/api/delete-saved-assessment', {
    method: 'POST',
    body: JSON.stringify({ filename }),
  })
}

// Student History/Writing Profiles
export async function listStudentHistory() {
  return fetchApi('/api/student-history')
}

export async function getStudentHistory(studentId) {
  return fetchApi(`/api/student-history/${encodeURIComponent(studentId)}`)
}

export async function deleteStudentHistory(studentId) {
  return fetchApi(`/api/student-history/${encodeURIComponent(studentId)}`, {
    method: 'DELETE',
  })
}

export async function deleteAllStudentHistory() {
  return fetchApi('/api/student-history', {
    method: 'DELETE',
  })
}

export async function migrateStudentNames() {
  return fetchApi('/api/student-history/migrate-names', {
    method: 'POST',
  })
}

// ============ Parent Contacts ============

export async function previewParentContacts(file) {
  const formData = new FormData()
  formData.append('file', file)

  const authHeaders = await getAuthHeaders()
  const response = await fetch('/api/preview-parent-contacts', {
    method: 'POST',
    headers: { ...authHeaders },
    body: formData,
  })
  return response.json()
}

export async function saveParentContactMapping(mapping) {
  return fetchApi('/api/save-parent-contact-mapping', {
    method: 'POST',
    body: JSON.stringify(mapping),
  })
}

export async function getParentContacts() {
  return fetchApi('/api/parent-contacts')
}

// ============ Focus Batch Export ============

export async function exportFocusBatch(results = null, assignment = null) {
  return fetchApi('/api/export-focus-batch', {
    method: 'POST',
    body: JSON.stringify({ results, assignment }),
  })
}

export async function exportFocusComments(results = null, assignment = null) {
  return fetchApi('/api/export-focus-comments', {
    method: 'POST',
    body: JSON.stringify({ results, assignment }),
  })
}

// ============ Outlook Email Export ============

export async function exportOutlookEmails(data = {}) {
  return fetchApi('/api/export-outlook-emails', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export default {
  getStatus,
  startGrading,
  stopGrading,
  clearResults,
  deleteResult,
  updateResult,
  checkNewFiles,
  saveRubric,
  loadRubric,
  saveGlobalSettings,
  loadGlobalSettings,
  saveAssignmentConfig,
  listAssignments,
  loadAssignment,
  deleteAssignment,
  exportAssignment,
  browse,
  parseDocument,
  openFolder,
  getAnalytics,
  exportDistrictReport,
  retranslateFeedback,
  getStandards,
  brainstormLessonIdeas,
  generateLessonPlan,
  exportLessonPlan,
  saveLessonPlan,
  listLessons,
  loadLesson,
  deleteLesson,
  listUnits,
  generateAssignmentFromLesson,
  exportGeneratedAssignment,
  publishAssignment,
  getAssignment,
  submitAssignment,
  getAssignmentSubmissions,
  sendEmails,
  updateApproval,
  updateApprovalsBulk,
  uploadRoster,
  listRosters,
  deleteRoster,
  saveRosterMapping,
  uploadPeriod,
  listPeriods,
  getPeriodStudents,
  deletePeriod,
  updatePeriodLevel,
  uploadSupportDocument,
  listSupportDocuments,
  deleteSupportDocument,
  listFiles,
  getAccommodationPresets,
  saveAccommodationPreset,
  deleteAccommodationPreset,
  getStudentAccommodations,
  getStudentAccommodation,
  setStudentAccommodation,
  deleteStudentAccommodation,
  importAccommodations,
  exportAccommodations,
  clearAllAccommodations,
  getAccommodationStats,
  // Student Portal
  publishAssessmentToPortal,
  getPublishedAssessments,
  getAssessmentResults,
  toggleAssessmentStatus,
  deletePublishedAssessment,
  getStudentAssessment,
  submitStudentAssessment,
  // Saved Assessments
  saveAssessmentLocally,
  listSavedAssessments,
  loadSavedAssessment,
  deleteSavedAssessment,
  // Student History/Writing Profiles
  listStudentHistory,
  getStudentHistory,
  deleteStudentHistory,
  deleteAllStudentHistory,
  migrateStudentNames,
  // Parent Contacts & Exports
  previewParentContacts,
  saveParentContactMapping,
  getParentContacts,
  exportFocusBatch,
  exportFocusComments,
  exportOutlookEmails,
}
