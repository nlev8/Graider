/**
 * API Service for Graider
 * Handles all API calls to the Flask backend
 */

import { supabase } from './supabase'
import { track } from './posthog'

const API_BASE = ''  // Empty for same-origin, Vite proxies /api to Flask

/**
 * Get authorization headers with current session token
 */
export async function getAuthHeaders() {
  // Clever/ClassLink users don't have Supabase sessions — skip entirely
  // (the browser sends the session cookie automatically)
  const currentUser = window.__graiderUser;
  if (currentUser && currentUser.id && (currentUser.id.startsWith('clever:') || currentUser.id.startsWith('classlink:'))) {
    return {}
  }
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
      // The 401 is likely from a timing issue where getSession() returned null
      // briefly. Wait for the session to stabilize and retry with fresh headers.
      // Do NOT call refreshSession() — it can cause Supabase to internally
      // fire SIGNED_OUT if it fails, kicking the user out.
      await new Promise(function(r) { setTimeout(r, 500) })
      var retryHeaders = await getAuthHeaders()
      if (retryHeaders.Authorization) {
        var retryResponse = await fetch(API_BASE + endpoint, {
          ...options,
          headers: {
            'Content-Type': 'application/json',
            ...retryHeaders,
            ...options.headers,
          },
        })
        if (retryResponse.ok) return await retryResponse.json()
        if (retryResponse.status !== 401) {
          // Non-auth error on retry — don't treat as auth failure
          throw new Error('API error: ' + retryResponse.status)
        }
      }
      // Still no valid session after waiting — truly expired
      // Don't fire for Clever users (they don't use Supabase sessions)
      var currentUser = window.__graiderUser;
      if (!(currentUser && currentUser.id && currentUser.id.startsWith('clever:'))) {
        window.dispatchEvent(new Event('auth-expired'))
      }
      throw new Error('Session expired. Please log in again.')
    }

    if (response.status === 403) {
      const errData = await response.json().catch(() => ({}))
      if (errData.code === 'NOT_APPROVED') {
        // JWT may have stale metadata — refresh session to pick up approval
        const { data: refreshData, error: refreshError } = await supabase.auth.refreshSession()
        if (!refreshError && refreshData?.session) {
          // Retry with fresh token (which now has approved: true if admin approved)
          const retryResponse = await fetch(API_BASE + endpoint, {
            ...options,
            headers: {
              'Content-Type': 'application/json',
              'Authorization': 'Bearer ' + refreshData.session.access_token,
              ...options.headers,
            },
          })
          if (retryResponse.ok) return await retryResponse.json()
          // Still 403 after refresh — user genuinely not approved
          const retryData = await retryResponse.json().catch(() => ({}))
          if (retryResponse.status === 403 && retryData.code === 'NOT_APPROVED') {
            window.dispatchEvent(new Event('account-not-approved'))
          }
          throw new Error(retryData.error || 'Access denied')
        }
        window.dispatchEvent(new Event('account-not-approved'))
      }
      throw new Error(errData.error || 'Access denied')
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

/**
 * Check API keys status — exported so App.jsx can use fetchApi instead of raw fetch
 */
export async function checkApiKeys() {
  return fetchApi('/api/check-api-keys')
}

// ============ Status & Grading ============

export async function getStatus() {
  return fetchApi('/api/status')
}

export async function stopGrading() {
  return fetchApi('/api/stop-grading', {
    method: 'POST',
  })
}

export async function clearResults(filenames = null) {
  return fetchApi('/api/clear-results', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filenames }),
  })
}

export async function deleteResult(filename) {
  return fetchApi('/api/delete-result', {
    method: 'POST',
    body: JSON.stringify({ filename }),
  })
}

export async function updateResult(filename, updates) {
  track('result_updated', {
    has_score_change: updates.score !== undefined,
    has_feedback_change: updates.feedback !== undefined,
  })
  return fetchApi('/api/update-result', {
    method: 'POST',
    body: JSON.stringify({ filename, ...updates }),
  })
}

// ============ Settings ============

export async function saveRubric(data) {
  track('rubric_saved', {
    category_count: data.categories ? data.categories.length : 0,
    grading_style: data.gradingStyle || 'standard',
  })
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
  track('assignment_config_saved', {
    has_markers: !!(data.customMarkers && data.customMarkers.length),
    has_grading_notes: !!data.gradingNotes,
  })
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
  track('content_exported', { type: 'assignment', format: data.format || 'docx' })
  return fetchApi('/api/export-assignment', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function generateModelAnswers(data) {
  return fetchApi('/api/generate-model-answers', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

// ============ Documents ============

export async function parseDocument(file) {
  var ext = file.name ? file.name.split('.').pop().toLowerCase() : 'unknown'
  track('document_parsed', { file_type: ext })
  const formData = new FormData()
  formData.append('file', file)

  const authHeaders = await getAuthHeaders()
  const response = await fetch('/api/parse-document', {
    method: 'POST',
    headers: { ...authHeaders },
    body: formData,
  })

  if (!response.ok) {
    const err = await response.json().catch(() => ({}))
    throw new Error(err.error || 'Failed to parse document')
  }

  return response.json()
}

// ============ Assessment Results ============

export async function getAggregatedAssessmentResults(category) {
  var url = '/api/assessment-results'
  if (category) url += '?category=' + encodeURIComponent(category)
  return fetchApi(url)
}

// ============ Standards ============

export async function getAvailableStates() {
  return fetchApi('/api/available-states')
}

// ============ Analytics ============

export async function getAnalytics(period, source) {
  var params = [];
  if (period && period !== 'all') params.push('period=' + encodeURIComponent(period));
  if (source && source !== 'all') params.push('source=' + encodeURIComponent(source));
  var url = '/api/analytics';
  if (params.length > 0) url += '?' + params.join('&');
  return fetchApi(url);
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

export async function alignDocumentToStandards(data) {
  return fetchApi('/api/align-document-to-standards', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function rewriteForAlignment(data) {
  return fetchApi('/api/rewrite-for-alignment', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function brainstormLessonIdeas(data) {
  return fetchApi('/api/brainstorm-lesson-ideas', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function generateLessonPlan(data) {
  track('lesson_plan_generated', { subject: data.subject, grade_level: data.grade_level })
  return fetchApi('/api/generate-lesson-plan', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function exportLessonPlan(plan) {
  track('content_exported', { type: 'lesson_plan' })
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

export async function generateAssignmentFromLesson(lessonPlan, config, assignmentType = 'assignment') {
  track('assignment_from_lesson_generated', { assignment_type: assignmentType })
  return fetchApi('/api/generate-assignment-from-lesson', {
    method: 'POST',
    body: JSON.stringify({ lessonPlan, config, assignmentType }),
  })
}

export async function exportGeneratedAssignment(assignment, format = 'docx', includeAnswers = false, opts = {}) {
  track('content_exported', { type: 'generated_assignment', format, include_answers: includeAnswers })
  return fetchApi('/api/export-generated-assignment', {
    method: 'POST',
    body: JSON.stringify({ assignment, format, include_answers: includeAnswers, teacher_name: opts.teacher_name || '', subject: opts.subject || '' }),
  })
}

// ============ Assessment Generation ============

export async function generateAssessment(standards, config, assessmentConfig, contentSources = []) {
  track('assessment_generated', {
    standard_count: standards ? standards.length : 0,
    question_count: assessmentConfig ? assessmentConfig.questionCount : null,
    has_content_sources: contentSources.length > 0,
  })
  return fetchApi('/api/generate-assessment', {
    method: 'POST',
    body: JSON.stringify({ standards, config, assessmentConfig, contentSources }),
  })
}

export async function exportAssessment(assessment, includeAnswerKey = false) {
  track('content_exported', { type: 'assessment', include_answer_key: includeAnswerKey })
  return fetchApi('/api/export-assessment', {
    method: 'POST',
    body: JSON.stringify({ assessment, includeAnswerKey }),
  })
}

export async function exportAssessmentForPlatform(assessment, platform, templateId = null) {
  track('content_exported', { type: 'assessment_platform', platform })
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

export async function regenerateQuestions(questionsToReplace, existingQuestions, config) {
  return fetchApi('/api/regenerate-questions', {
    method: 'POST',
    body: JSON.stringify({
      questions_to_replace: questionsToReplace,
      existing_questions: existingQuestions,
      config,
    }),
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

export async function deleteAssessment(joinCode) {
  return fetchApi('/api/teacher/assessment/' + joinCode, {
    method: 'DELETE',
  })
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
  track('emails_sent', { count: results ? results.length : 0 })
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

export async function updateApproval(filename, approval, graded_at) {
  return fetchApi('/api/update-approval', {
    method: 'POST',
    body: JSON.stringify({ filename, approval, graded_at }),
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

export async function parseDocumentForCalendar(filename) {
  return fetchApi('/api/calendar/parse-document', {
    method: 'POST',
    body: JSON.stringify({ filename }),
  })
}

export async function importCalendarEvents(events) {
  return fetchApi('/api/calendar/import-events', {
    method: 'POST',
    body: JSON.stringify({ events }),
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

export async function setStudentAccommodation(studentId, presets, customNotes = '', studentName = '') {
  return fetchApi(`/api/student-accommodations/${encodeURIComponent(studentId)}`, {
    method: 'POST',
    body: JSON.stringify({ presets, custom_notes: customNotes, student_name: studentName }),
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
  track('assessment_published_to_portal')
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

// ============ Student Account Portal ============

export async function createClass(name, subject, gradeLevel) {
  return fetchApi('/api/classes', {
    method: 'POST',
    body: JSON.stringify({ name, subject, grade_level: gradeLevel }),
  })
}

export async function listClasses() {
  return fetchApi('/api/classes')
}

export async function listClassStudents(classId) {
  return fetchApi('/api/classes/' + classId + '/students')
}

export async function publishToClass(classId, content, contentType, title, settings, dueDate) {
  return fetchApi('/api/publish-to-class', {
    method: 'POST',
    body: JSON.stringify({
      class_id: classId,
      content, content_type: contentType,
      title, settings, due_date: dueDate,
    }),
  })
}

export async function getPortalSubmissions() {
  return fetchApi('/api/portal-submissions')
}

export async function gradePortalSubmission(submissionId) {
  return fetchApi('/api/grade-portal-submission', {
    method: 'POST',
    body: JSON.stringify({ submission_id: submissionId }),
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

// ============ ELL Students (Bilingual Feedback) ============

export async function getEllStudents() {
  return fetchApi('/api/ell-students')
}

export async function saveEllStudents(ellData) {
  return fetchApi('/api/ell-students', {
    method: 'POST',
    body: JSON.stringify(ellData),
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

// ============ Focus Roster Import ============

export async function importFromFocus() {
  return fetchApi('/api/import-from-focus', { method: 'POST' })
}

export async function getFocusImportStatus() {
  return fetchApi('/api/focus-import-status')
}

export async function addStudent(data) {
  return fetchApi('/api/add-student', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function removeStudent(data) {
  return fetchApi('/api/remove-student', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateStudent(data) {
  return fetchApi('/api/update-student', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

// ============ Focus Batch Export ============

export async function exportFocusBatch(results = null, assignment = null) {
  track('content_exported', { type: 'focus_batch' })
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

export async function uploadFocusComments(data = {}) {
  return fetchApi('/api/upload-focus-comments', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function getFocusCommentsStatus() {
  return fetchApi('/api/focus-comments/status')
}

// ============ Outlook Email Export ============

export async function exportOutlookEmails(data = {}) {
  return fetchApi('/api/export-outlook-emails', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

// ============ Focus SIS Communications ============

export async function sendFocusComms(data = {}) {
  return fetchApi('/api/send-focus-comms', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function getFocusCommsStatus() {
  return fetchApi('/api/focus-comms/status')
}

export async function stopFocusComms() {
  return fetchApi('/api/focus-comms/stop', { method: 'POST' })
}

// ============ Outlook Playwright Sending ============

export async function sendOutlookEmails(data = {}) {
  return fetchApi('/api/send-outlook-emails', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function getOutlookSendStatus() {
  return fetchApi('/api/outlook-send/status')
}

export async function outlookLogin() {
  return fetchApi('/api/outlook-login', { method: 'POST' })
}

export async function sendSubmissionConfirmations() {
  return fetchApi('/api/send-submission-confirmations', { method: 'POST' })
}

export async function markConfirmationsSent(confirmationIds = [], status = 'sent') {
  return fetchApi('/api/mark-confirmations-sent', {
    method: 'POST',
    body: JSON.stringify({ confirmation_ids: confirmationIds, status }),
  })
}

// ============ File-Based Confirmation Emails ============

export async function sendFileConfirmations(data = {}) {
  return fetchApi('/api/send-confirmation-emails', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function markFileConfirmationsSent(filenames = []) {
  return fetchApi('/api/mark-confirmations-sent-file', {
    method: 'POST',
    body: JSON.stringify({ filenames }),
  })
}

export async function getPendingConfirmations(data = {}) {
  return fetchApi('/api/pending-confirmations', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

// ============ Assistant ============

export async function sendAssistantMessage(messages, sessionId, files = []) {
  track('assistant_message_sent', { has_files: files.length > 0 })
  const authHeaders = await getAuthHeaders()
  return fetch(API_BASE + '/api/assistant/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders },
    body: JSON.stringify({ messages, session_id: sessionId, files }),
  })
  // Returns raw Response for caller to read SSE stream
}

export async function clearAssistantSession(sessionId) {
  return fetchApi('/api/assistant/clear', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId }),
  })
}

export async function savePortalCredentials(email, password) {
  return fetchApi('/api/assistant/credentials', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
}

export async function getPortalCredentials() {
  return fetchApi('/api/assistant/credentials')
}

// Stripe Billing
export async function getSubscriptionStatus() {
  return fetchApi('/api/stripe/subscription-status')
}

export async function createCheckoutSession(plan) {
  return fetchApi('/api/stripe/create-checkout-session', {
    method: 'POST',
    body: JSON.stringify({ plan }),
  })
}

export async function createPortalSession() {
  return fetchApi('/api/stripe/create-portal-session', { method: 'POST' })
}

// ============ Reading Level Adjustment ============

export async function extractTextFromFile(file) {
  var formData = new FormData()
  formData.append('file', file)
  var response = await fetch('/api/extract-text', {
    method: 'POST',
    headers: await getAuthHeaders(),
    body: formData,
  })
  return response.json()
}

export async function adjustReadingLevel(text, targetLevel, subject, preserveTerms) {
  return fetchApi('/api/adjust-reading-level', {
    method: 'POST',
    body: JSON.stringify({
      text,
      target_level: targetLevel,
      subject: subject || '',
      preserve_terms: preserveTerms || [],
    }),
  })
}

// ============ LMS Grade Export ============

export async function exportLmsCsv(results, assignment, totalPoints, format) {
  track('content_exported', { type: 'lms_csv', format, result_count: results ? results.length : 0 })
  return fetchApi('/api/export-lms-csv', {
    method: 'POST',
    body: JSON.stringify({
      results,
      assignment,
      total_points: totalPoints,
      format,
    }),
  })
}

// ============ OneRoster Gradebook Sync ============

export async function syncOneRosterGrades(data) {
  track('grades_synced', { type: 'oneroster', score_count: data.scores ? data.scores.length : 0 })
  return fetchApi('/api/oneroster/sync-grades', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

// ============ Cost Tracking ============

export async function getPlannerCosts() {
  return fetchApi('/api/planner/costs')
}

export async function getAssistantCosts() {
  return fetchApi('/api/assistant/costs')
}

// ============ Automations ============

export async function listAutomations() {
  return fetchApi('/api/automations')
}

export async function getAutomation(id) {
  return fetchApi('/api/automations/' + id)
}

export async function saveAutomation(workflow) {
  return fetchApi('/api/automations', {
    method: 'POST',
    body: JSON.stringify(workflow),
  })
}

export async function deleteAutomation(id) {
  return fetchApi('/api/automations/' + id, { method: 'DELETE' })
}

export async function deleteTemplate(id) {
  return fetchApi('/api/automations/templates/' + id, { method: 'DELETE' })
}

export async function getTemplate(id) {
  return fetchApi('/api/automations/templates/' + id)
}

export async function listAutomationTemplates() {
  return fetchApi('/api/automations/templates')
}

export async function runAutomation(id, vars) {
  return fetchApi('/api/automations/' + id + '/run', {
    method: 'POST',
    body: JSON.stringify({ vars: vars || {} }),
  })
}

export async function getAutomationRunStatus() {
  return fetchApi('/api/automations/run/status')
}

export async function stopAutomationRun() {
  return fetchApi('/api/automations/run/stop', { method: 'POST' })
}

export async function startElementPicker(url, login = false) {
  return fetchApi('/api/automations/picker/start', {
    method: 'POST',
    body: JSON.stringify({ url: url || 'https://vportal.volusia.k12.fl.us/', login }),
  })
}

export async function getPickerEvents() {
  return fetchApi('/api/automations/picker/events')
}

export async function stopElementPicker() {
  return fetchApi('/api/automations/picker/stop', { method: 'POST' })
}

// ============ NotebookLM Materials ============

export async function notebookLMAuthStatus() {
  return fetchApi('/api/notebooklm/auth-status')
}

export async function notebookLMLogin(step) {
  return fetchApi('/api/notebooklm/login', {
    method: 'POST',
    body: JSON.stringify({ step: step || 'start' }),
  })
}

export async function notebookLMUploadContext(file) {
  const formData = new FormData()
  formData.append('file', file)
  const authHeaders = await getAuthHeaders()
  const response = await fetch('/api/notebooklm/upload-context', {
    method: 'POST',
    headers: { ...authHeaders },
    body: formData,
  })
  return response.json()
}

export async function notebookLMCreateNotebook(plan, standards, config, supportDocPaths, plannerDocTexts) {
  const body = { plan: plan, standards: standards, config: config }
  if (supportDocPaths && supportDocPaths.length > 0) {
    body.support_doc_paths = supportDocPaths
  }
  if (plannerDocTexts && plannerDocTexts.length > 0) {
    body.planner_docs = plannerDocTexts
  }
  return fetchApi('/api/notebooklm/create-notebook', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function notebookLMGenerate(notebookId, materials, options) {
  return fetchApi('/api/notebooklm/generate', {
    method: 'POST',
    body: JSON.stringify({ notebook_id: notebookId, materials: materials, options: options }),
  })
}

export async function notebookLMStatus() {
  return fetchApi('/api/notebooklm/status')
}

export async function notebookLMDownload(materialType) {
  var authHeaders = await getAuthHeaders()
  var response = await fetch('/api/notebooklm/download/' + materialType, {
    headers: authHeaders,
  })
  if (!response.ok) throw new Error('Download failed')
  var blob = await response.blob()
  var url = URL.createObjectURL(blob)
  var a = document.createElement('a')
  a.href = url
  var extMap = {
    audio_overview: 'mp3', video_overview: 'mp4', quiz: 'json',
    flashcards: 'json', study_guide: 'docx', slide_deck: 'pptx',
    mind_map: 'json', infographic: 'png', data_table: 'csv',
  }
  a.download = materialType + '.' + (extMap[materialType] || 'bin')
  document.body.appendChild(a)
  a.click()
  setTimeout(function() {
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }, 100)
}

export async function notebookLMPreview(materialType) {
  return fetchApi('/api/notebooklm/preview/' + materialType)
}

export async function notebookLMCancel() {
  return fetchApi('/api/notebooklm/cancel', { method: 'POST' })
}

export async function notebookLMRetry(options) {
  return fetchApi('/api/notebooklm/retry', {
    method: 'POST',
    body: JSON.stringify({ options: options || {} }),
  })
}

export async function shareMaterial(materialType, title, teacherName) {
  return fetchApi('/api/notebooklm/share-material', {
    method: 'POST',
    body: JSON.stringify({
      material_type: materialType,
      title: title || materialType,
      teacher_name: teacherName || 'Teacher',
    }),
  })
}

// ============ Resources (Assets) ============

export async function saveResource(content, contentType, title, resourceId) {
  return fetchApi('/api/save-resource', {
    method: 'POST',
    body: JSON.stringify({ content, content_type: contentType, title, resource_id: resourceId }),
  })
}

export async function listResources(typeFilter) {
  var url = '/api/list-resources'
  if (typeFilter) url += '?type=' + encodeURIComponent(typeFilter)
  return fetchApi(url)
}

export async function loadResource(resourceId) {
  return fetchApi('/api/load-resource', {
    method: 'POST',
    body: JSON.stringify({ resource_id: resourceId }),
  })
}

export async function deleteResource(resourceId) {
  return fetchApi('/api/delete-resource', {
    method: 'POST',
    body: JSON.stringify({ resource_id: resourceId }),
  })
}

// ============ Clever SSO & Sync ============

export async function getCleverLoginUrl() {
  return fetchApi('/api/clever/login-url')
}

export async function getCleverSession() {
  return fetchApi('/api/clever/session')
}

export async function syncCleverRoster() {
  return fetchApi('/api/clever/sync-roster', { method: 'POST' })
}

export async function applyCleverAccommodations(accommodations) {
  return fetchApi('/api/clever/apply-accommodations', {
    method: 'POST',
    body: JSON.stringify({ accommodations }),
  })
}

export async function cleverLogout() {
  return fetchApi('/api/clever/logout', { method: 'POST' })
}

// ============ OneRoster Integration ============

export async function getOneRosterConfig() {
  return fetchApi('/api/oneroster/config')
}

export async function saveOneRosterConfig(config) {
  return fetchApi('/api/oneroster/config', {
    method: 'POST',
    body: JSON.stringify(config),
  })
}

export async function testOneRosterConnection() {
  return fetchApi('/api/oneroster/test', { method: 'POST' })
}

export async function syncOneRosterRoster() {
  return fetchApi('/api/oneroster/sync-roster', { method: 'POST' })
}

export async function applyOneRosterAccommodations(accommodations) {
  return fetchApi('/api/oneroster/apply-accommodations', {
    method: 'POST',
    body: JSON.stringify({ accommodations }),
  })
}

export async function deleteOneRosterData() {
  return fetchApi('/api/oneroster/delete-data', { method: 'POST' })
}

export async function saveOneRosterTeacherId(teacherSourcedId) {
  return fetchApi('/api/oneroster/teacher-id', {
    method: 'POST',
    body: JSON.stringify({ teacher_sourced_id: teacherSourcedId }),
  })
}

// ============ LTI 1.3 Integration ============

export async function getLTIConfig() {
  return fetchApi('/api/lti/config')
}

export async function registerLTIPlatform(config) {
  return fetchApi('/api/lti/config', {
    method: 'POST',
    body: JSON.stringify(config),
  })
}

export async function deleteLTIPlatform(issuer) {
  return fetchApi('/api/lti/config', {
    method: 'DELETE',
    body: JSON.stringify({ issuer: issuer }),
  })
}

export async function syncLTIGrades(payload) {
  return fetchApi('/api/lti/sync-grades', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function getLTIContexts() {
  return fetchApi('/api/lti/contexts')
}

// ============ District Admin Setup ============

export async function districtAuth(password, setup) {
  return fetchApi('/api/district/auth', {
    method: 'POST',
    body: JSON.stringify({ password: password, setup: setup || false }),
  })
}

export async function districtLogout() {
  return fetchApi('/api/district/auth', { method: 'DELETE' })
}

export async function getDistrictConfig() {
  return fetchApi('/api/district/config')
}

export async function saveDistrictConfig(config) {
  return fetchApi('/api/district/config', {
    method: 'POST',
    body: JSON.stringify(config),
  })
}

export async function testDistrictConnection() {
  return fetchApi('/api/district/test-connection', { method: 'POST' })
}

export async function getDistrictConfigStatus() {
  return fetchApi('/api/district/config-status')
}

export async function changeDistrictPassword(currentPassword, newPassword) {
  return fetchApi('/api/district/change-password', {
    method: 'POST',
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  })
}

// ============ School Admin ============

export async function getAdminStatus() {
  return fetchApi('/api/admin/status')
}

export async function claimAdmin(code) {
  return fetchApi('/api/admin/claim', {
    method: 'POST',
    body: JSON.stringify({ code: code }),
  })
}

export async function getAdminTeachers() {
  return fetchApi('/api/admin/teachers')
}

export async function getAdminOverview() {
  return fetchApi('/api/admin/overview')
}

export async function getAdminTeacherSummary(teacherId) {
  return fetchApi('/api/admin/teacher/' + teacherId + '/summary')
}

export async function getAdminActivity() {
  return fetchApi('/api/admin/activity')
}

export async function createAdminInvite(school, manualTeachers) {
  return fetchApi('/api/district/admin-invite', {
    method: 'POST',
    body: JSON.stringify({ school: school, manual_teachers: manualTeachers || [] }),
  })
}

export async function listAdmins() {
  return fetchApi('/api/district/admins')
}

export async function revokeAdmin(userId) {
  return fetchApi('/api/district/admins', {
    method: 'DELETE',
    body: JSON.stringify({ user_id: userId }),
  })
}

export async function searchTeachers(query) {
  return fetchApi('/api/district/teacher-search?q=' + encodeURIComponent(query))
}

export default {
  getStatus,
  stopGrading,
  clearResults,
  deleteResult,
  updateResult,
  saveRubric,
  loadRubric,
  saveGlobalSettings,
  loadGlobalSettings,
  saveAssignmentConfig,
  generateModelAnswers,
  listAssignments,
  loadAssignment,
  deleteAssignment,
  exportAssignment,
  parseDocument,
  getAnalytics,
  getAvailableStates,
  exportDistrictReport,
  retranslateFeedback,
  getStandards,
  alignDocumentToStandards,
  rewriteForAlignment,
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
  parseDocumentForCalendar,
  importCalendarEvents,
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
  regenerateQuestions,
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
  // ELL Students
  getEllStudents,
  saveEllStudents,
  // Parent Contacts & Exports
  previewParentContacts,
  saveParentContactMapping,
  getParentContacts,
  // Focus Roster Import
  importFromFocus,
  getFocusImportStatus,
  addStudent,
  removeStudent,
  updateStudent,
  exportFocusBatch,
  exportFocusComments,
  uploadFocusComments,
  getFocusCommentsStatus,
  exportOutlookEmails,
  // Focus SIS Communications
  sendFocusComms,
  getFocusCommsStatus,
  stopFocusComms,
  // Outlook Sending
  sendOutlookEmails,
  getOutlookSendStatus,
  outlookLogin,
  // Submission Confirmations
  sendSubmissionConfirmations,
  markConfirmationsSent,
  // File-Based Confirmations
  sendFileConfirmations,
  markFileConfirmationsSent,
  getPendingConfirmations,
  // Assistant
  sendAssistantMessage,
  clearAssistantSession,
  savePortalCredentials,
  getPortalCredentials,
  // Stripe Billing
  getSubscriptionStatus,
  createCheckoutSession,
  createPortalSession,
  // Reading Level / LMS Export
  extractTextFromFile,
  adjustReadingLevel,
  exportLmsCsv,
  syncOneRosterGrades,
  // Cost Tracking
  getPlannerCosts,
  getAssistantCosts,
  // Automations
  listAutomations,
  getAutomation,
  saveAutomation,
  deleteAutomation,
  deleteTemplate,
  getTemplate,
  listAutomationTemplates,
  runAutomation,
  getAutomationRunStatus,
  stopAutomationRun,
  startElementPicker,
  getPickerEvents,
  stopElementPicker,
  checkApiKeys,
  // NotebookLM Materials
  notebookLMAuthStatus,
  notebookLMLogin,
  notebookLMUploadContext,
  notebookLMCreateNotebook,
  notebookLMGenerate,
  notebookLMStatus,
  notebookLMDownload,
  notebookLMPreview,
  notebookLMCancel,
  notebookLMRetry,
  shareMaterial,
  // Resources (Assets)
  saveResource,
  listResources,
  loadResource,
  deleteResource,
  // Assessment Results (aggregated)
  getAggregatedAssessmentResults,
  // Clever SSO & Sync
  getCleverLoginUrl,
  getCleverSession,
  syncCleverRoster,
  applyCleverAccommodations,
  cleverLogout,
  // OneRoster Integration
  getOneRosterConfig,
  saveOneRosterConfig,
  testOneRosterConnection,
  syncOneRosterRoster,
  applyOneRosterAccommodations,
  deleteOneRosterData,
  saveOneRosterTeacherId,
  // LTI 1.3 Integration
  getLTIConfig,
  registerLTIPlatform,
  deleteLTIPlatform,
  syncLTIGrades,
  getLTIContexts,
  // District Admin Setup
  districtAuth,
  districtLogout,
  getDistrictConfig,
  saveDistrictConfig,
  testDistrictConnection,
  getDistrictConfigStatus,
  changeDistrictPassword,
  // School Admin
  getAdminStatus,
  claimAdmin,
  getAdminTeachers,
  getAdminOverview,
  getAdminTeacherSummary,
  getAdminActivity,
  createAdminInvite,
  listAdmins,
  revokeAdmin,
  searchTeachers,
}
