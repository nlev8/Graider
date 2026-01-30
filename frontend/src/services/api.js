/**
 * API Service for Graider
 * Handles all API calls to the Flask backend
 */

const API_BASE = ''  // Empty for same-origin, Vite proxies /api to Flask

/**
 * Generic fetch wrapper with error handling
 */
async function fetchApi(endpoint, options = {}) {
  try {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    })

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`)
    }

    return await response.json()
  } catch (error) {
    console.error(`API Error (${endpoint}):`, error)
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

export async function clearResults() {
  return fetchApi('/api/clear-results', {
    method: 'POST',
  })
}

export async function deleteResult(filename) {
  return fetchApi('/api/delete-result', {
    method: 'POST',
    body: JSON.stringify({ filename }),
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

  const response = await fetch('/api/parse-document', {
    method: 'POST',
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

// ============ Email ============

export async function sendEmails(results) {
  return fetchApi('/api/send-emails', {
    method: 'POST',
    body: JSON.stringify({ results }),
  })
}

// ============ Roster & Period Uploads ============

export async function uploadRoster(file) {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch('/api/upload-roster', {
    method: 'POST',
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

  const response = await fetch('/api/upload-period', {
    method: 'POST',
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

// ============ Supporting Documents ============

export async function uploadSupportDocument(file, docType, description) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('doc_type', docType)
  formData.append('description', description || '')

  const response = await fetch('/api/upload-document', {
    method: 'POST',
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

  const response = await fetch('/api/import-accommodations', {
    method: 'POST',
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

export default {
  getStatus,
  startGrading,
  stopGrading,
  clearResults,
  deleteResult,
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
  sendEmails,
  uploadRoster,
  listRosters,
  deleteRoster,
  saveRosterMapping,
  uploadPeriod,
  listPeriods,
  getPeriodStudents,
  deletePeriod,
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
}
