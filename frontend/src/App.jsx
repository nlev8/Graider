import { useState, useEffect, useRef } from 'react'
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts'
import Icon from './components/Icon'
import * as api from './services/api'

// Tab configuration
const TABS = [
  { id: 'grade', label: 'Grade', icon: 'GraduationCap' },
  { id: 'results', label: 'Results', icon: 'FileText' },
  { id: 'builder', label: 'Builder', icon: 'FileEdit' },
  { id: 'analytics', label: 'Analytics', icon: 'BarChart3' },
  { id: 'planner', label: 'Planner', icon: 'BookOpen' },
  { id: 'resources', label: 'Resources', icon: 'FolderOpen' },
  { id: 'settings', label: 'Settings', icon: 'Settings' },
]

// Marker libraries by subject
const markerLibrary = {
  'Social Studies': ['Explain:', 'Describe the significance of:', 'Compare and contrast:', 'What were the causes of:', 'What were the effects of:', 'Analyze:', 'In your own words:', 'Why do you think:'],
  'English/ELA': ['Write your response:', 'Your thesis statement:', 'Analyze the text:', 'Provide evidence:', 'Explain the theme:', 'Character analysis:', 'Authors purpose:'],
  'Math': ['Show your work:', 'Solve:', 'Calculate:', 'Prove:', 'Find the value of:', 'Graph:', 'Simplify:', 'Word Problem:'],
  'Science': ['Hypothesis:', 'Data/Observations:', 'Conclusion:', 'Procedure:', 'Variables:', 'Analysis:', 'Explain the results:'],
  'History': ['Explain:', 'Describe:', 'What was the impact of:', 'Primary source analysis:', 'Timeline:', 'Cause and effect:', 'Historical significance:'],
  'Other': ['Answer:', 'Explain:', 'Describe:', 'Your response:', 'Short answer:', 'Essay:']
}

// StandardCard component for Planner
function StandardCard({ standard, isSelected, onToggle }) {
  return (
    <div
      onClick={onToggle}
      style={{
        background: isSelected ? 'rgba(99,102,241,0.2)' : 'rgba(255,255,255,0.03)',
        border: isSelected ? '1px solid #6366f1' : '1px solid rgba(255,255,255,0.1)',
        borderRadius: '12px',
        padding: '15px',
        cursor: 'pointer',
        transition: 'all 0.2s',
        marginBottom: '10px'
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
        <span style={{ fontWeight: 700, color: isSelected ? '#a5b4fc' : '#fff', fontSize: '0.9rem' }}>{standard.code}</span>
        {isSelected && <Icon name="CheckCircle" size={18} style={{ color: '#6366f1' }} />}
      </div>
      <p style={{ fontSize: '0.9rem', color: 'rgba(255,255,255,0.8)', lineHeight: '1.5', margin: '0 0 10px 0' }}>{standard.benchmark}</p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
        {(standard.topics || []).map(topic => (
          <span key={topic} style={{ fontSize: '0.75rem', padding: '3px 8px', borderRadius: '4px', background: 'rgba(255,255,255,0.1)', color: 'rgba(255,255,255,0.6)' }}>
            {topic}
          </span>
        ))}
      </div>
    </div>
  )
}

function App() {
  // Core state
  const [config, setConfig] = useState({
    assignments_folder: '',
    output_folder: '',
    roster_file: '',
    grading_period: 'Q1',
    grade_level: '7',
    subject: 'Social Studies',
  })

  const [status, setStatus] = useState({
    is_running: false,
    progress: 0,
    total: 0,
    current_file: '',
    log: [],
    results: [],
    complete: false,
    error: null,
  })

  const [activeTab, setActiveTab] = useState('grade')
  const [analytics, setAnalytics] = useState(null)
  const [selectedStudent, setSelectedStudent] = useState(null)
  const [analyticsPeriod, setAnalyticsPeriod] = useState('all')
  const [autoGrade, setAutoGrade] = useState(false)
  const [globalAINotes, setGlobalAINotes] = useState('')
  const [watchStatus, setWatchStatus] = useState({ watching: false, lastCheck: null, newFiles: 0 })

  // Builder state
  const [assignment, setAssignment] = useState({
    title: '',
    subject: 'Social Studies',
    totalPoints: 100,
    instructions: '',
    questions: [],
    customMarkers: [],
    gradingNotes: ''
  })
  const [savedAssignments, setSavedAssignments] = useState([])
  const [loadedAssignmentName, setLoadedAssignmentName] = useState('')
  const [selectedGradingConfig, setSelectedGradingConfig] = useState(null)
  const [importedDoc, setImportedDoc] = useState({ text: '', html: '', filename: '', loading: false })
  const [docEditorModal, setDocEditorModal] = useState({ show: false, editedHtml: '', viewMode: 'formatted' })

  // Results state
  const [editedResults, setEditedResults] = useState([])
  const [reviewModal, setReviewModal] = useState({ show: false, index: -1 })
  const [emailPreview, setEmailPreview] = useState({ show: false, emails: [] })
  const [emailStatus, setEmailStatus] = useState({ sending: false, sent: 0, failed: 0, message: '' })

  // Planner state
  const [plannerConfig, setPlannerConfig] = useState({ state: 'FL', grade: '7', subject: 'Civics' })
  const [standards, setStandards] = useState([])
  const [selectedStandards, setSelectedStandards] = useState([])
  const [lessonPlan, setLessonPlan] = useState(null)
  const [plannerLoading, setPlannerLoading] = useState(false)
  const [unitConfig, setUnitConfig] = useState({
    title: '',
    duration: 1,
    periodLength: 50,
    type: 'Lesson Plan',
    format: 'Word',
    requirements: ''
  })

  // File upload state
  const [rosters, setRosters] = useState([])
  const [periods, setPeriods] = useState([])
  const [supportDocs, setSupportDocs] = useState([])
  const [uploadingRoster, setUploadingRoster] = useState(false)
  const [uploadingPeriod, setUploadingPeriod] = useState(false)
  const [uploadingDoc, setUploadingDoc] = useState(false)
  const [newPeriodName, setNewPeriodName] = useState('')
  const [newDocType, setNewDocType] = useState('curriculum')
  const [newDocDescription, setNewDocDescription] = useState('')
  const [rosterMappingModal, setRosterMappingModal] = useState({ show: false, roster: null })

  // Rubric state
  const [rubric, setRubric] = useState({
    categories: [
      { name: 'Content Accuracy', weight: 40, description: 'Are answers factually correct?' },
      { name: 'Completeness', weight: 25, description: 'Did student attempt all questions?' },
      { name: 'Writing Quality', weight: 20, description: 'Is writing clear and readable?' },
      { name: 'Effort & Engagement', weight: 15, description: 'Did student show genuine effort?' }
    ],
    generous: true
  })

  const logRef = useRef(null)
  const fileInputRef = useRef(null)
  const docHtmlRef = useRef(null)
  const rosterInputRef = useRef(null)
  const periodInputRef = useRef(null)
  const supportDocInputRef = useRef(null)

  // Load saved settings on startup
  useEffect(() => {
    api.loadGlobalSettings()
      .then(data => {
        if (data.settings?.globalAINotes) setGlobalAINotes(data.settings.globalAINotes)
        if (data.settings?.config) setConfig(prev => ({ ...prev, ...data.settings.config }))
      })
      .catch(console.error)

    api.listAssignments()
      .then(data => { if (data.assignments) setSavedAssignments(data.assignments) })
      .catch(console.error)

    // Load uploaded files
    api.listRosters()
      .then(data => { if (data.rosters) setRosters(data.rosters) })
      .catch(console.error)

    api.listPeriods()
      .then(data => { if (data.periods) setPeriods(data.periods) })
      .catch(console.error)

    api.listSupportDocuments()
      .then(data => { if (data.documents) setSupportDocs(data.documents) })
      .catch(console.error)

    api.loadRubric()
      .then(data => { if (data.rubric) setRubric(data.rubric) })
      .catch(console.error)
  }, [])

  // Poll status while grading
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const data = await api.getStatus()
        setStatus(data)
      } catch (error) {
        console.error('Status poll error:', error)
      }
    }, 500)
    return () => clearInterval(interval)
  }, [])

  // Auto-grade watcher
  useEffect(() => {
    if (!autoGrade) return
    const watchInterval = setInterval(async () => {
      if (status.is_running) return
      try {
        const data = await api.checkNewFiles(config.assignments_folder, config.output_folder)
        setWatchStatus({ watching: true, lastCheck: new Date().toLocaleTimeString(), newFiles: data.new_files || 0 })
        if (data.new_files > 0 && !status.is_running) {
          handleStartGrading()
        }
      } catch (e) {
        console.error('Watch error:', e)
      }
    }, 10000)
    setWatchStatus({ watching: true, lastCheck: 'Starting...', newFiles: 0 })
    return () => {
      clearInterval(watchInterval)
      setWatchStatus({ watching: false, lastCheck: null, newFiles: 0 })
    }
  }, [autoGrade, config.assignments_folder, config.output_folder, status.is_running])

  // Fetch analytics when tab opens
  useEffect(() => {
    if (activeTab === 'analytics') {
      api.getAnalytics(analyticsPeriod)
        .then(data => setAnalytics(data))
        .catch(console.error)
    }
  }, [activeTab, analyticsPeriod])

  // Load standards when planner config changes
  useEffect(() => {
    if (activeTab === 'planner') {
      loadStandards()
    }
  }, [plannerConfig.state, plannerConfig.grade, plannerConfig.subject, activeTab])

  // Auto-scroll log
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [status.log])

  // Sync editedResults with status.results
  useEffect(() => {
    if (status.results.length > 0 && editedResults.length !== status.results.length) {
      setEditedResults(status.results.map(r => ({ ...r, edited: false })))
    }
  }, [status.results])

  // Grading functions
  const handleStartGrading = async () => {
    try {
      await api.startGrading({
        ...config,
        assignmentConfig: selectedGradingConfig,
        globalAINotes,
      })
      setStatus(prev => ({ ...prev, is_running: true, log: ['Starting...'] }))
    } catch (error) {
      console.error('Failed to start grading:', error)
    }
  }

  const handleStopGrading = async () => {
    try {
      await api.stopGrading()
      setAutoGrade(false)
    } catch (error) {
      console.error('Failed to stop grading:', error)
    }
  }

  const handleBrowse = async (type, field) => {
    try {
      const result = await api.browse(type)
      if (result.path) {
        setConfig(prev => ({ ...prev, [field]: result.path }))
      }
    } catch (error) {
      console.error('Browse error:', error)
    }
  }

  const openResults = () => api.openFolder(config.output_folder)

  // Load grading config
  const loadGradingConfig = async (name) => {
    if (!name) {
      setSelectedGradingConfig(null)
      return
    }
    try {
      const data = await api.loadAssignment(name)
      if (data.assignment) setSelectedGradingConfig(data.assignment)
    } catch (e) {
      console.error('Error loading config:', e)
    }
  }

  // Builder functions
  const handleDocImport = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    setImportedDoc({ text: '', html: '', filename: file.name, loading: true })
    try {
      const data = await api.parseDocument(file)
      if (data.error) {
        alert('Error parsing document: ' + data.error)
        setImportedDoc({ text: '', html: '', filename: '', loading: false })
      } else {
        setImportedDoc({ text: data.text || '', html: data.html || '', filename: file.name, loading: false })
        setLoadedAssignmentName('')
        setDocEditorModal({ show: true, editedHtml: data.html || '', viewMode: 'formatted' })
        if (!assignment.title) {
          const title = file.name.replace(/\.(docx|pdf|doc)$/i, '').replace(/_/g, ' ')
          setAssignment({ ...assignment, title })
        }
      }
    } catch (err) {
      alert('Error: ' + err.message)
      setImportedDoc({ text: '', html: '', filename: '', loading: false })
    }
  }

  const openDocEditor = () => {
    if (importedDoc.text || importedDoc.html) {
      setDocEditorModal({ show: true, editedHtml: importedDoc.html, viewMode: 'formatted' })
    }
  }

  const addSelectedAsMarker = () => {
    let text = ''
    try {
      if (docHtmlRef.current?.contentDocument) {
        const sel = docHtmlRef.current.contentDocument.getSelection()
        if (sel) text = sel.toString().trim()
      }
    } catch (e) {}
    if (!text) {
      const sel = window.getSelection()
      text = sel ? sel.toString().trim() : ''
    }
    if (text && text.length > 2 && text.length < 500) {
      if (!(assignment.customMarkers || []).includes(text)) {
        setAssignment({ ...assignment, customMarkers: [...(assignment.customMarkers || []), text] })
      }
    } else if (text.length <= 2) {
      alert('Please select more text (at least 3 characters)')
    } else if (text.length >= 500) {
      alert('Selection too long. Please select less text (under 500 characters)')
    }
  }

  const removeMarker = (marker) => {
    setAssignment({ ...assignment, customMarkers: (assignment.customMarkers || []).filter(m => m !== marker) })
  }

  const addQuestion = () => {
    setAssignment({
      ...assignment,
      questions: [...assignment.questions, {
        id: Date.now(),
        type: 'short_answer',
        prompt: '',
        points: 10,
        marker: markerLibrary[assignment.subject]?.[0] || 'Answer:'
      }]
    })
  }

  const updateQuestion = (index, field, value) => {
    const updated = [...assignment.questions]
    updated[index] = { ...updated[index], [field]: value }
    setAssignment({ ...assignment, questions: updated })
  }

  const removeQuestion = (index) => {
    setAssignment({ ...assignment, questions: assignment.questions.filter((_, i) => i !== index) })
  }

  const saveAssignmentConfig = async () => {
    if (!assignment.title) {
      alert('Please enter a title')
      return
    }
    try {
      const dataToSave = { ...assignment, importedDoc }
      await api.saveAssignmentConfig(dataToSave)
      alert('Assignment saved!')
      setLoadedAssignmentName(assignment.title)
      const list = await api.listAssignments()
      if (list.assignments) setSavedAssignments(list.assignments)
    } catch (e) {
      alert('Error saving: ' + e.message)
    }
  }

  const loadAssignment = async (name) => {
    try {
      const data = await api.loadAssignment(name)
      if (data.assignment) {
        setAssignment({
          title: data.assignment.title || '',
          subject: data.assignment.subject || 'Social Studies',
          totalPoints: data.assignment.totalPoints || 100,
          instructions: data.assignment.instructions || '',
          questions: data.assignment.questions || [],
          customMarkers: data.assignment.customMarkers || [],
          gradingNotes: data.assignment.gradingNotes || ''
        })
        setLoadedAssignmentName(name)
        if (data.assignment.importedDoc) {
          setImportedDoc(data.assignment.importedDoc)
        } else {
          setImportedDoc({ text: '', html: '', filename: '', loading: false })
        }
      }
    } catch (e) {
      alert('Error loading: ' + e.message)
    }
  }

  const deleteAssignment = async (name) => {
    if (!confirm(`Delete "${name}"?`)) return
    try {
      await api.deleteAssignment(name)
      setSavedAssignments(savedAssignments.filter(a => a !== name))
      if (loadedAssignmentName === name) {
        setAssignment({ title: '', subject: 'Social Studies', totalPoints: 100, instructions: '', questions: [], customMarkers: [], gradingNotes: '' })
        setLoadedAssignmentName('')
      }
    } catch (e) {
      alert('Error: ' + e.message)
    }
  }

  const exportAssignment = async (format) => {
    try {
      const data = await api.exportAssignment({ assignment, format })
      if (data.error) alert('Error: ' + data.error)
      else alert('Assignment exported!')
    } catch (e) {
      alert('Error exporting: ' + e.message)
    }
  }

  // Planner functions
  const loadStandards = async () => {
    setPlannerLoading(true)
    try {
      const data = await api.getStandards(plannerConfig)
      setStandards(data.standards || [])
    } catch (e) {
      console.error('Error loading standards:', e)
    } finally {
      setPlannerLoading(false)
    }
  }

  const toggleStandard = (code) => {
    setSelectedStandards(prev =>
      prev.includes(code) ? prev.filter(c => c !== code) : [...prev, code]
    )
  }

  const generateLessonPlan = async () => {
    if (selectedStandards.length === 0) {
      alert('Please select at least one standard.')
      return
    }
    if (!unitConfig.title) {
      alert('Please enter a title.')
      return
    }
    setPlannerLoading(true)
    try {
      const data = await api.generateLessonPlan({
        standards: selectedStandards,
        config: { ...plannerConfig, ...unitConfig }
      })
      if (data.error) alert('Error: ' + data.error)
      else setLessonPlan(data.plan || data)
    } catch (e) {
      alert('Error generating plan: ' + e.message)
    } finally {
      setPlannerLoading(false)
    }
  }

  const exportLessonPlanHandler = async () => {
    if (!lessonPlan) return
    try {
      const data = await api.exportLessonPlan(lessonPlan)
      if (data.error) alert('Error exporting: ' + data.error)
      else alert('Lesson plan exported to: ' + data.path)
    } catch (e) {
      alert('Error exporting: ' + e.message)
    }
  }

  // Results/Email functions
  const openReview = (index) => setReviewModal({ show: true, index })

  const updateGrade = (index, field, value) => {
    const updated = [...editedResults]
    updated[index] = { ...updated[index], [field]: value, edited: true }
    if (field === 'score') {
      const score = parseInt(value) || 0
      updated[index].letter_grade = score >= 90 ? 'A' : score >= 80 ? 'B' : score >= 70 ? 'C' : score >= 60 ? 'D' : 'F'
    }
    setEditedResults(updated)
  }

  const previewEmails = () => {
    const results = editedResults.length > 0 ? editedResults : status.results
    if (results.length === 0) {
      alert('No results to email. Run grading first.')
      return
    }
    const students = {}
    results.forEach(r => {
      const email = r.email || ''
      if (email && email.includes('@') && r.student_id !== 'UNKNOWN') {
        if (!students[email]) students[email] = { name: r.student_name, email, grades: [] }
        students[email].grades.push(r)
      }
    })
    const emailList = Object.values(students).map(s => {
      const firstName = s.name.split(' ')[0]
      const subject = s.grades.length === 1
        ? `Grade for ${s.grades[0].assignment}: ${s.grades[0].letter_grade}`
        : `Grades for ${s.grades.length} Assignments`
      let body = `Hi ${firstName},\n\n`
      if (s.grades.length === 1) {
        const g = s.grades[0]
        body += `Here is your grade and feedback for ${g.assignment}:\n\nGRADE: ${g.score}/100 (${g.letter_grade})\n\nFEEDBACK:\n${g.feedback}`
      } else {
        body += 'Here are your grades and feedback:\n\n'
        s.grades.forEach(g => {
          body += `━━━━━━━━━━━━━━━━━━━━━━━━━━\n${g.assignment}\nGRADE: ${g.score}/100 (${g.letter_grade})\n\nFEEDBACK:\n${g.feedback}\n\n`
        })
      }
      return { to: s.email, name: s.name, subject, body, assignments: s.grades.length }
    })
    setEmailPreview({ show: true, emails: emailList })
  }

  const sendEmails = async () => {
    setEmailPreview({ ...emailPreview, show: false })
    const results = editedResults.length > 0 ? editedResults : status.results
    if (results.length === 0) return
    setEmailStatus({ sending: true, sent: 0, failed: 0, message: 'Sending emails...' })
    try {
      const data = await api.sendEmails(results)
      setEmailStatus({
        sending: false,
        sent: data.sent || 0,
        failed: data.failed || 0,
        message: data.error ? `Error: ${data.error}` : `Sent ${data.sent} emails${data.failed > 0 ? `, ${data.failed} failed` : ''}`
      })
    } catch (e) {
      setEmailStatus({ sending: false, sent: 0, failed: 0, message: `Error: ${e.message}` })
    }
  }

  const pct = status.total > 0 ? (status.progress / status.total) * 100 : 0

  return (
    <div style={{ minHeight: '100vh', padding: '20px' }}>
      {/* Email Preview Modal */}
      {emailPreview.show && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.8)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
          <div style={{ background: '#1a1a2e', borderRadius: '20px', border: '1px solid rgba(255,255,255,0.1)', width: '100%', maxWidth: '800px', maxHeight: '90vh', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            <div style={{ padding: '20px 25px', borderBottom: '1px solid rgba(255,255,255,0.1)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 style={{ fontSize: '1.3rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '10px' }}><Icon name="Mail" size={24} />Email Preview ({emailPreview.emails.length} students)</h2>
              <button onClick={() => setEmailPreview({ show: false, emails: [] })} style={{ background: 'none', border: 'none', color: 'rgba(255,255,255,0.6)', cursor: 'pointer' }}><Icon name="X" size={24} /></button>
            </div>
            <div style={{ flex: 1, overflowY: 'auto', padding: '20px' }}>
              {emailPreview.emails.map((email, i) => (
                <div key={i} style={{ background: 'rgba(255,255,255,0.03)', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.1)', marginBottom: '15px', overflow: 'hidden' }}>
                  <div style={{ padding: '15px 20px', borderBottom: '1px solid rgba(255,255,255,0.05)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <div style={{ fontWeight: 600, marginBottom: '4px' }}>{email.name}</div>
                      <div style={{ fontSize: '0.85rem', color: 'rgba(255,255,255,0.5)' }}>{email.to}</div>
                    </div>
                    <span style={{ background: 'rgba(99,102,241,0.2)', color: '#a5b4fc', padding: '4px 12px', borderRadius: '20px', fontSize: '0.8rem' }}>{email.assignments} assignment{email.assignments > 1 ? 's' : ''}</span>
                  </div>
                  <div style={{ padding: '15px 20px' }}>
                    <div style={{ fontSize: '0.9rem', color: '#a5b4fc', marginBottom: '10px' }}><strong>Subject:</strong> {email.subject}</div>
                    <div style={{ fontSize: '0.85rem', color: 'rgba(255,255,255,0.7)', whiteSpace: 'pre-wrap', maxHeight: '150px', overflowY: 'auto', background: 'rgba(0,0,0,0.2)', padding: '12px', borderRadius: '8px', fontFamily: 'monospace' }}>{email.body}</div>
                  </div>
                </div>
              ))}
            </div>
            <div style={{ padding: '20px 25px', borderTop: '1px solid rgba(255,255,255,0.1)', display: 'flex', gap: '15px', justifyContent: 'flex-end' }}>
              <button onClick={() => setEmailPreview({ show: false, emails: [] })} className="btn btn-secondary">Cancel</button>
              <button onClick={sendEmails} className="btn btn-primary"><Icon name="Send" size={18} />Send All Emails</button>
            </div>
          </div>
        </div>
      )}

      {/* Review Modal */}
      {reviewModal.show && reviewModal.index >= 0 && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.8)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
          <div style={{ background: '#1a1a2e', borderRadius: '20px', border: '1px solid rgba(255,255,255,0.1)', width: '100%', maxWidth: '900px', maxHeight: '90vh', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            <div style={{ padding: '20px 25px', borderBottom: '1px solid rgba(255,255,255,0.1)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 style={{ fontSize: '1.3rem', fontWeight: 700 }}>Review: {(editedResults[reviewModal.index] || status.results[reviewModal.index])?.student_name}</h2>
              <button onClick={() => setReviewModal({ show: false, index: -1 })} style={{ background: 'none', border: 'none', color: 'rgba(255,255,255,0.6)', cursor: 'pointer' }}><Icon name="X" size={24} /></button>
            </div>
            <div style={{ flex: 1, overflowY: 'auto', padding: '20px' }}>
              {(() => {
                const r = editedResults[reviewModal.index] || status.results[reviewModal.index]
                if (!r) return null
                return (
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
                    <div>
                      <h3 style={{ marginBottom: '15px' }}>Student Work</h3>
                      <div style={{ background: 'rgba(0,0,0,0.3)', padding: '15px', borderRadius: '10px', maxHeight: '400px', overflowY: 'auto', whiteSpace: 'pre-wrap', fontSize: '0.9rem' }}>
                        {r.student_content || '[No content available]'}
                      </div>
                    </div>
                    <div>
                      <h3 style={{ marginBottom: '15px' }}>Grade & Feedback</h3>
                      <div style={{ marginBottom: '15px' }}>
                        <label className="label">Score</label>
                        <input
                          type="number"
                          className="input"
                          value={r.score}
                          onChange={e => updateGrade(reviewModal.index, 'score', e.target.value)}
                          style={{ width: '100px' }}
                        />
                        <span style={{ marginLeft: '10px', fontWeight: 700, color: r.score >= 90 ? '#4ade80' : r.score >= 80 ? '#60a5fa' : r.score >= 70 ? '#fbbf24' : '#f87171' }}>
                          {r.letter_grade}
                        </span>
                      </div>
                      <div>
                        <label className="label">Feedback</label>
                        <textarea
                          className="input"
                          value={r.feedback}
                          onChange={e => updateGrade(reviewModal.index, 'feedback', e.target.value)}
                          style={{ minHeight: '300px' }}
                        />
                      </div>
                    </div>
                  </div>
                )
              })()}
            </div>
            <div style={{ padding: '20px 25px', borderTop: '1px solid rgba(255,255,255,0.1)', display: 'flex', gap: '15px', justifyContent: 'flex-end' }}>
              <button onClick={() => setReviewModal({ show: false, index: -1 })} className="btn btn-primary">Done</button>
            </div>
          </div>
        </div>
      )}

      {/* Document Editor Modal */}
      {docEditorModal.show && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.95)', zIndex: 1000, display: 'flex', flexDirection: 'column' }}>
          <div style={{ padding: '15px 25px', borderBottom: '1px solid rgba(255,255,255,0.1)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#1a1a2e' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
              <h2 style={{ fontSize: '1.2rem', fontWeight: 700 }}><Icon name="FileEdit" size={20} /> {importedDoc.filename || 'Document Editor'}</h2>
              <span style={{ fontSize: '0.85rem', color: 'rgba(255,255,255,0.5)' }}>{(assignment.customMarkers || []).length} markers selected</span>
            </div>
            <div style={{ display: 'flex', gap: '10px' }}>
              <button onClick={addSelectedAsMarker} className="btn btn-primary"><Icon name="Target" size={16} />Mark Selection</button>
              <button onClick={() => setDocEditorModal({ ...docEditorModal, show: false })} className="btn btn-secondary">Done</button>
            </div>
          </div>
          <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '1fr 300px', overflow: 'hidden' }}>
            <div style={{ overflow: 'auto', padding: '20px' }}>
              <iframe
                ref={docHtmlRef}
                srcDoc={`<!DOCTYPE html><html><head><style>body{font-family:Georgia,serif;padding:40px;background:#fff;color:#000;line-height:1.6}::selection{background:#6366f1;color:#fff}</style></head><body>${docEditorModal.editedHtml}</body></html>`}
                style={{ width: '100%', height: '100%', border: 'none', borderRadius: '8px', minHeight: '600px' }}
              />
            </div>
            <div style={{ borderLeft: '1px solid rgba(255,255,255,0.1)', padding: '20px', overflowY: 'auto', background: 'rgba(0,0,0,0.3)' }}>
              <h3 style={{ fontSize: '1rem', marginBottom: '15px' }}>Marked Sections ({(assignment.customMarkers || []).length})</h3>
              <p style={{ fontSize: '0.85rem', color: 'rgba(255,255,255,0.5)', marginBottom: '15px' }}>Select text in the document and click "Mark Selection"</p>
              {(assignment.customMarkers || []).length === 0 ? (
                <p style={{ color: 'rgba(255,255,255,0.4)', fontSize: '0.9rem' }}>No markers yet</p>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {(assignment.customMarkers || []).map((marker, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 12px', background: 'rgba(251,191,36,0.2)', borderRadius: '6px', border: '1px solid rgba(251,191,36,0.3)' }}>
                      <Icon name="Target" size={12} style={{ color: '#fbbf24', flexShrink: 0 }} />
                      <span style={{ fontSize: '0.8rem', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis' }}>{marker}</span>
                      <button onClick={() => removeMarker(marker)} style={{ background: 'none', border: 'none', color: 'rgba(255,255,255,0.4)', cursor: 'pointer', padding: '0' }}><Icon name="X" size={12} /></button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Header */}
      <div style={{ textAlign: 'center', marginBottom: '30px', paddingTop: '20px' }}>
        <h1 style={{ fontSize: '2.5rem', fontWeight: 800, background: 'linear-gradient(135deg, #fff 0%, #a5b4fc 100%)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', marginBottom: '8px' }}>
          Graider
        </h1>
        <p style={{ color: 'rgba(255,255,255,0.6)', fontSize: '1rem' }}>AI-Powered Grading Assistant</p>
      </div>

      {/* Tab Navigation */}
      <div style={{ display: 'flex', justifyContent: 'center', gap: '10px', marginBottom: '30px', flexWrap: 'wrap' }}>
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              padding: '12px 20px',
              borderRadius: '12px',
              border: 'none',
              background: activeTab === tab.id ? 'linear-gradient(135deg, #6366f1, #8b5cf6)' : 'rgba(255,255,255,0.05)',
              color: activeTab === tab.id ? '#fff' : 'rgba(255,255,255,0.6)',
              fontSize: '0.95rem',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              transition: 'all 0.3s',
              boxShadow: activeTab === tab.id ? '0 10px 30px rgba(99,102,241,0.3)' : 'none',
            }}
          >
            <Icon name={tab.icon} size={18} />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Main Content */}
      <div style={{ maxWidth: '1400px', margin: '0 auto' }}>
        {/* Grade Tab */}
        {activeTab === 'grade' && (
          <div className="fade-in">
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
              {/* Left: Controls */}
              <div className="glass-card" style={{ padding: '25px' }}>
                <h2 style={{ fontSize: '1.3rem', fontWeight: 700, marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <Icon name="Play" size={24} />
                  Start Grading
                </h2>

                {/* Assignment Config Selection */}
                <div style={{ marginBottom: '20px' }}>
                  <label className="label">Assignment Config</label>
                  <select
                    className="input"
                    value={selectedGradingConfig?.title || ''}
                    onChange={e => loadGradingConfig(e.target.value)}
                  >
                    <option value="">Auto-detect from filename</option>
                    {savedAssignments.map(name => (
                      <option key={name} value={name}>{name}</option>
                    ))}
                  </select>
                </div>

                {/* Auto-Grade Toggle */}
                <div style={{ marginBottom: '20px', padding: '15px', background: autoGrade ? 'rgba(74,222,128,0.1)' : 'rgba(255,255,255,0.03)', borderRadius: '12px', border: autoGrade ? '1px solid rgba(74,222,128,0.3)' : '1px solid rgba(255,255,255,0.1)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <div style={{ fontWeight: 600, marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Icon name="Zap" size={16} style={{ color: autoGrade ? '#4ade80' : 'rgba(255,255,255,0.5)' }} />
                        Auto-Grade Mode
                      </div>
                      <div style={{ fontSize: '0.85rem', color: 'rgba(255,255,255,0.5)' }}>
                        {autoGrade ? `Watching... Last check: ${watchStatus.lastCheck}` : 'Watch folder for new files'}
                      </div>
                    </div>
                    <button
                      onClick={() => setAutoGrade(!autoGrade)}
                      style={{
                        padding: '8px 16px',
                        borderRadius: '8px',
                        border: 'none',
                        background: autoGrade ? '#4ade80' : 'rgba(255,255,255,0.1)',
                        color: autoGrade ? '#000' : '#fff',
                        fontWeight: 600,
                        cursor: 'pointer'
                      }}
                    >
                      {autoGrade ? 'ON' : 'OFF'}
                    </button>
                  </div>
                </div>

                {!status.is_running ? (
                  <button onClick={handleStartGrading} className="btn btn-primary" style={{ width: '100%', justifyContent: 'center', padding: '16px' }}>
                    <Icon name="Zap" size={20} />
                    Start Grading
                  </button>
                ) : (
                  <button onClick={handleStopGrading} className="btn btn-danger" style={{ width: '100%', justifyContent: 'center', padding: '16px' }}>
                    <Icon name="Square" size={20} />
                    Stop Grading
                  </button>
                )}

                {/* Progress */}
                {status.is_running && (
                  <div style={{ marginTop: '20px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '0.9rem' }}>
                      <span>Progress</span>
                      <span>{status.progress}/{status.total}</span>
                    </div>
                    <div style={{ height: '8px', background: 'rgba(255,255,255,0.1)', borderRadius: '4px', overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: `${pct}%`, background: 'linear-gradient(90deg, #6366f1, #8b5cf6)', transition: 'width 0.3s' }} />
                    </div>
                    {status.current_file && (
                      <p style={{ marginTop: '8px', fontSize: '0.85rem', color: 'rgba(255,255,255,0.5)' }}>{status.current_file}</p>
                    )}
                  </div>
                )}

                {status.complete && (
                  <button onClick={openResults} className="btn btn-secondary" style={{ width: '100%', marginTop: '15px', justifyContent: 'center' }}>
                    <Icon name="FolderOpen" size={18} />
                    Open Results Folder
                  </button>
                )}
              </div>

              {/* Right: Log */}
              <div className="glass-card" style={{ padding: '25px' }}>
                <h2 style={{ fontSize: '1.3rem', fontWeight: 700, marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <Icon name="Terminal" size={24} />
                  Activity Log
                </h2>
                <div
                  ref={logRef}
                  style={{ height: '350px', overflowY: 'auto', background: 'rgba(0,0,0,0.3)', borderRadius: '12px', padding: '15px', fontFamily: 'Monaco, monospace', fontSize: '0.85rem', lineHeight: '1.6' }}
                >
                  {status.log.length === 0 ? (
                    <p style={{ color: 'rgba(255,255,255,0.4)' }}>Ready to grade...</p>
                  ) : (
                    status.log.map((line, i) => <div key={i} style={{ marginBottom: '4px' }}>{line}</div>)
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Results Tab */}
        {activeTab === 'results' && (
          <div className="fade-in glass-card" style={{ padding: '25px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h2 style={{ fontSize: '1.3rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Icon name="FileText" size={24} />
                Grading Results ({status.results.length})
              </h2>
              {status.results.length > 0 && (
                <div style={{ display: 'flex', gap: '10px' }}>
                  <button onClick={previewEmails} className="btn btn-secondary">
                    <Icon name="Mail" size={18} />Preview Emails
                  </button>
                  <button onClick={openResults} className="btn btn-secondary">
                    <Icon name="FolderOpen" size={18} />Open Folder
                  </button>
                </div>
              )}
            </div>

            {emailStatus.message && (
              <div style={{ marginBottom: '15px', padding: '12px 15px', background: emailStatus.message.includes('Error') ? 'rgba(248,113,113,0.1)' : 'rgba(74,222,128,0.1)', borderRadius: '8px', border: emailStatus.message.includes('Error') ? '1px solid rgba(248,113,113,0.3)' : '1px solid rgba(74,222,128,0.3)' }}>
                {emailStatus.message}
              </div>
            )}

            {status.results.length === 0 ? (
              <p style={{ color: 'rgba(255,255,255,0.5)', textAlign: 'center', padding: '40px' }}>
                No results yet. Grade some assignments first.
              </p>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Student</th>
                    <th>Assignment</th>
                    <th>Score</th>
                    <th>Grade</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {(editedResults.length > 0 ? editedResults : status.results).map((r, i) => (
                    <tr key={i} style={{ background: r.edited ? 'rgba(251,191,36,0.1)' : 'transparent' }}>
                      <td>{r.student_name}</td>
                      <td>{r.assignment}</td>
                      <td>{r.score}</td>
                      <td>
                        <span style={{
                          padding: '4px 12px',
                          borderRadius: '20px',
                          fontWeight: 700,
                          background: r.score >= 90 ? 'rgba(74,222,128,0.2)' : r.score >= 80 ? 'rgba(96,165,250,0.2)' : r.score >= 70 ? 'rgba(251,191,36,0.2)' : 'rgba(248,113,113,0.2)',
                          color: r.score >= 90 ? '#4ade80' : r.score >= 80 ? '#60a5fa' : r.score >= 70 ? '#fbbf24' : '#f87171',
                        }}>
                          {r.letter_grade}
                        </span>
                      </td>
                      <td>
                        <button onClick={() => openReview(i)} style={{ background: 'none', border: 'none', color: '#a5b4fc', cursor: 'pointer', padding: '4px' }}>
                          <Icon name="Edit" size={16} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {/* Settings Tab */}
        {activeTab === 'settings' && (
          <div className="fade-in glass-card" style={{ padding: '25px' }}>
            <h2 style={{ fontSize: '1.3rem', fontWeight: 700, marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '10px' }}>
              <Icon name="Settings" size={24} />
              Settings
            </h2>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              <div>
                <label className="label">Assignments Folder</label>
                <div style={{ display: 'flex', gap: '10px' }}>
                  <input type="text" className="input" value={config.assignments_folder} onChange={e => setConfig(prev => ({ ...prev, assignments_folder: e.target.value }))} />
                  <button onClick={() => handleBrowse('folder', 'assignments_folder')} className="btn btn-secondary">Browse</button>
                </div>
              </div>

              <div>
                <label className="label">Output Folder</label>
                <div style={{ display: 'flex', gap: '10px' }}>
                  <input type="text" className="input" value={config.output_folder} onChange={e => setConfig(prev => ({ ...prev, output_folder: e.target.value }))} />
                  <button onClick={() => handleBrowse('folder', 'output_folder')} className="btn btn-secondary">Browse</button>
                </div>
              </div>

              <div>
                <label className="label">Roster File</label>
                <div style={{ display: 'flex', gap: '10px' }}>
                  <input type="text" className="input" value={config.roster_file} onChange={e => setConfig(prev => ({ ...prev, roster_file: e.target.value }))} />
                  <button onClick={() => handleBrowse('file', 'roster_file')} className="btn btn-secondary">Browse</button>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '20px' }}>
                <div>
                  <label className="label">Grade Level</label>
                  <select className="input" value={config.grade_level} onChange={e => setConfig(prev => ({ ...prev, grade_level: e.target.value }))}>
                    <option value="K">Kindergarten</option>
                    <option value="1">1st Grade</option>
                    <option value="2">2nd Grade</option>
                    <option value="3">3rd Grade</option>
                    <option value="4">4th Grade</option>
                    <option value="5">5th Grade</option>
                    <option value="6">6th Grade</option>
                    <option value="7">7th Grade</option>
                    <option value="8">8th Grade</option>
                    <option value="9">9th Grade</option>
                    <option value="10">10th Grade</option>
                    <option value="11">11th Grade</option>
                    <option value="12">12th Grade</option>
                  </select>
                </div>

                <div>
                  <label className="label">Subject</label>
                  <select className="input" value={config.subject} onChange={e => setConfig(prev => ({ ...prev, subject: e.target.value }))}>
                    <option value="Social Studies">Social Studies</option>
                    <option value="English/ELA">English/ELA</option>
                    <option value="Math">Math</option>
                    <option value="Science">Science</option>
                    <option value="History">History</option>
                    <option value="Civics">Civics</option>
                    <option value="Geography">Geography</option>
                    <option value="Other">Other</option>
                  </select>
                </div>

                <div>
                  <label className="label">Grading Period</label>
                  <select className="input" value={config.grading_period} onChange={e => setConfig(prev => ({ ...prev, grading_period: e.target.value }))}>
                    <option value="Q1">Quarter 1 (Q1)</option>
                    <option value="Q2">Quarter 2 (Q2)</option>
                    <option value="Q3">Quarter 3 (Q3)</option>
                    <option value="Q4">Quarter 4 (Q4)</option>
                    <option value="S1">Semester 1 (S1)</option>
                    <option value="S2">Semester 2 (S2)</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="label">Global AI Grading Instructions</label>
                <textarea
                  className="input"
                  value={globalAINotes}
                  onChange={e => setGlobalAINotes(e.target.value)}
                  placeholder="Instructions that apply to ALL assignments..."
                  style={{ minHeight: '120px', resize: 'vertical' }}
                />
              </div>

              {/* Rubric Configuration */}
              <div style={{ borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '20px', marginTop: '20px' }}>
                <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '15px', display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <Icon name="ClipboardCheck" size={20} style={{ color: '#8b5cf6' }} />
                  Grading Rubric
                </h3>
                <p style={{ fontSize: '0.85rem', color: 'rgba(255,255,255,0.5)', marginBottom: '15px' }}>
                  Configure how assignments are scored. Weights must total 100%.
                </p>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '15px' }}>
                  {rubric.categories.map((cat, idx) => (
                    <div key={idx} style={{ display: 'flex', gap: '10px', alignItems: 'center', padding: '12px', background: 'rgba(0,0,0,0.2)', borderRadius: '8px' }}>
                      <input
                        type="text"
                        className="input"
                        value={cat.name}
                        onChange={e => {
                          const updated = [...rubric.categories]
                          updated[idx].name = e.target.value
                          setRubric({ ...rubric, categories: updated })
                        }}
                        style={{ flex: 1 }}
                        placeholder="Category name"
                      />
                      <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                        <input
                          type="number"
                          className="input"
                          value={cat.weight}
                          onChange={e => {
                            const updated = [...rubric.categories]
                            updated[idx].weight = parseInt(e.target.value) || 0
                            setRubric({ ...rubric, categories: updated })
                          }}
                          style={{ width: '70px', textAlign: 'center' }}
                          min="0"
                          max="100"
                        />
                        <span style={{ color: 'rgba(255,255,255,0.5)' }}>%</span>
                      </div>
                      <button
                        onClick={() => {
                          const updated = rubric.categories.filter((_, i) => i !== idx)
                          setRubric({ ...rubric, categories: updated })
                        }}
                        style={{ padding: '6px', background: 'none', border: 'none', color: 'rgba(255,255,255,0.3)', cursor: 'pointer' }}
                      >
                        <Icon name="X" size={16} />
                      </button>
                    </div>
                  ))}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '15px', marginBottom: '15px' }}>
                  <button
                    onClick={() => {
                      setRubric({
                        ...rubric,
                        categories: [...rubric.categories, { name: '', weight: 0, description: '' }]
                      })
                    }}
                    className="btn btn-secondary"
                    style={{ fontSize: '0.85rem' }}
                  >
                    <Icon name="Plus" size={16} />Add Category
                  </button>
                  <span style={{ fontSize: '0.85rem', color: rubric.categories.reduce((sum, c) => sum + c.weight, 0) === 100 ? '#10b981' : '#ef4444' }}>
                    Total: {rubric.categories.reduce((sum, c) => sum + c.weight, 0)}%
                    {rubric.categories.reduce((sum, c) => sum + c.weight, 0) !== 100 && ' (must equal 100%)'}
                  </span>
                </div>

                <button
                  onClick={async () => {
                    try {
                      await api.saveRubric(rubric)
                      alert('Rubric saved!')
                    } catch (e) {
                      alert('Error saving rubric: ' + e.message)
                    }
                  }}
                  className="btn btn-secondary"
                  style={{ fontSize: '0.85rem' }}
                >
                  <Icon name="Save" size={16} />Save Rubric
                </button>
              </div>

              <button
                onClick={async () => {
                  try {
                    await api.saveGlobalSettings({ globalAINotes, config })
                    alert('Settings saved!')
                  } catch (e) {
                    alert('Error saving: ' + e.message)
                  }
                }}
                className="btn btn-primary"
                style={{ alignSelf: 'flex-start', marginTop: '20px' }}
              >
                <Icon name="Save" size={18} />Save Settings
              </button>

              {/* Roster Upload Section */}
              <div style={{ borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '25px', marginTop: '25px' }}>
                <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '15px', display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <Icon name="Users" size={20} style={{ color: '#6366f1' }} />
                  Student Roster
                </h3>
                <p style={{ fontSize: '0.85rem', color: 'rgba(255,255,255,0.5)', marginBottom: '15px' }}>
                  Upload CSV with Student ID, Name, Student Email, and Parent Email columns
                </p>

                <input
                  ref={rosterInputRef}
                  type="file"
                  accept=".csv"
                  style={{ display: 'none' }}
                  onChange={async (e) => {
                    const file = e.target.files?.[0]
                    if (!file) return
                    setUploadingRoster(true)
                    try {
                      const result = await api.uploadRoster(file)
                      if (result.error) {
                        alert(result.error)
                      } else {
                        const rostersData = await api.listRosters()
                        setRosters(rostersData.rosters || [])
                        setRosterMappingModal({ show: true, roster: result })
                      }
                    } catch (err) {
                      alert('Upload failed: ' + err.message)
                    }
                    setUploadingRoster(false)
                    e.target.value = ''
                  }}
                />

                <button
                  onClick={() => rosterInputRef.current?.click()}
                  className="btn btn-secondary"
                  disabled={uploadingRoster}
                  style={{ marginBottom: '15px' }}
                >
                  <Icon name="Upload" size={18} />
                  {uploadingRoster ? 'Uploading...' : 'Upload Roster CSV'}
                </button>

                {rosters.length > 0 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    {rosters.map(roster => (
                      <div key={roster.filename} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 15px', background: 'rgba(0,0,0,0.2)', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.1)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                          <Icon name="FileSpreadsheet" size={18} style={{ color: '#10b981' }} />
                          <div>
                            <div style={{ fontWeight: 600 }}>{roster.filename}</div>
                            <div style={{ fontSize: '0.8rem', color: 'rgba(255,255,255,0.5)' }}>
                              {roster.row_count} students • {roster.headers?.length || 0} columns
                              {Object.keys(roster.column_mapping || {}).length > 0 && ' • Mapped'}
                            </div>
                          </div>
                        </div>
                        <div style={{ display: 'flex', gap: '8px' }}>
                          <button
                            onClick={() => setRosterMappingModal({ show: true, roster })}
                            className="btn btn-secondary"
                            style={{ padding: '6px 12px', fontSize: '0.8rem' }}
                          >
                            <Icon name="Settings2" size={14} />Map Columns
                          </button>
                          <button
                            onClick={async () => {
                              if (confirm('Delete this roster?')) {
                                await api.deleteRoster(roster.filename)
                                const data = await api.listRosters()
                                setRosters(data.rosters || [])
                              }
                            }}
                            style={{ padding: '6px 10px', background: 'rgba(239,68,68,0.2)', border: 'none', borderRadius: '6px', color: '#ef4444', cursor: 'pointer' }}
                          >
                            <Icon name="Trash2" size={14} />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Period/Class Upload Section */}
              <div style={{ borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '25px', marginTop: '25px' }}>
                <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '15px', display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <Icon name="Clock" size={20} style={{ color: '#f59e0b' }} />
                  Class Periods
                </h3>
                <p style={{ fontSize: '0.85rem', color: 'rgba(255,255,255,0.5)', marginBottom: '15px' }}>
                  Upload separate rosters for each class period
                </p>

                <input
                  ref={periodInputRef}
                  type="file"
                  accept=".csv"
                  style={{ display: 'none' }}
                  onChange={async (e) => {
                    const file = e.target.files?.[0]
                    if (!file) return
                    if (!newPeriodName.trim()) {
                      alert('Please enter a period name first')
                      e.target.value = ''
                      return
                    }
                    setUploadingPeriod(true)
                    try {
                      const result = await api.uploadPeriod(file, newPeriodName)
                      if (result.error) {
                        alert(result.error)
                      } else {
                        const periodsData = await api.listPeriods()
                        setPeriods(periodsData.periods || [])
                        setNewPeriodName('')
                      }
                    } catch (err) {
                      alert('Upload failed: ' + err.message)
                    }
                    setUploadingPeriod(false)
                    e.target.value = ''
                  }}
                />

                <div style={{ display: 'flex', gap: '10px', marginBottom: '15px' }}>
                  <input
                    type="text"
                    className="input"
                    placeholder="Period name (e.g., Period 1, Block A)"
                    value={newPeriodName}
                    onChange={e => setNewPeriodName(e.target.value)}
                    style={{ maxWidth: '250px' }}
                  />
                  <button
                    onClick={() => periodInputRef.current?.click()}
                    className="btn btn-secondary"
                    disabled={uploadingPeriod || !newPeriodName.trim()}
                  >
                    <Icon name="Upload" size={18} />
                    {uploadingPeriod ? 'Uploading...' : 'Upload Period CSV'}
                  </button>
                </div>

                {periods.length > 0 && (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
                    {periods.map(period => (
                      <div key={period.filename} style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '10px 15px', background: 'rgba(0,0,0,0.2)', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.1)' }}>
                        <Icon name="Users" size={16} style={{ color: '#f59e0b' }} />
                        <div>
                          <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{period.period_name}</div>
                          <div style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.5)' }}>{period.row_count} students</div>
                        </div>
                        <button
                          onClick={async () => {
                            if (confirm(`Delete ${period.period_name}?`)) {
                              await api.deletePeriod(period.filename)
                              const data = await api.listPeriods()
                              setPeriods(data.periods || [])
                            }
                          }}
                          style={{ padding: '4px 6px', background: 'none', border: 'none', color: 'rgba(255,255,255,0.3)', cursor: 'pointer' }}
                        >
                          <Icon name="X" size={14} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Resources Tab */}
        {activeTab === 'resources' && (
          <div className="fade-in glass-card" style={{ padding: '25px' }}>
            <h2 style={{ fontSize: '1.3rem', fontWeight: 700, marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '10px' }}>
              <Icon name="FolderOpen" size={24} />
              Resources
            </h2>
            <p style={{ fontSize: '0.9rem', color: 'rgba(255,255,255,0.6)', marginBottom: '25px' }}>
              Upload curriculum guides, rubrics, standards documents, and other reference materials to enhance AI grading and lesson planning.
            </p>

            {/* Supporting Documents Section */}
            <div>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '15px', display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Icon name="FileText" size={20} style={{ color: '#10b981' }} />
                Supporting Documents
                </h3>
                <p style={{ fontSize: '0.85rem', color: 'rgba(255,255,255,0.5)', marginBottom: '15px' }}>
                  Upload curriculum guides, rubrics, standards docs, or other reference materials
                </p>

                <input
                  ref={supportDocInputRef}
                  type="file"
                  accept=".pdf,.docx,.doc,.txt,.md"
                  style={{ display: 'none' }}
                  onChange={async (e) => {
                    const file = e.target.files?.[0]
                    if (!file) return
                    setUploadingDoc(true)
                    try {
                      const result = await api.uploadSupportDocument(file, newDocType, newDocDescription)
                      if (result.error) {
                        alert(result.error)
                      } else {
                        const docsData = await api.listSupportDocuments()
                        setSupportDocs(docsData.documents || [])
                        setNewDocDescription('')
                      }
                    } catch (err) {
                      alert('Upload failed: ' + err.message)
                    }
                    setUploadingDoc(false)
                    e.target.value = ''
                  }}
                />

                <div style={{ display: 'flex', gap: '10px', marginBottom: '15px', flexWrap: 'wrap' }}>
                  <select
                    className="input"
                    value={newDocType}
                    onChange={e => setNewDocType(e.target.value)}
                    style={{ maxWidth: '180px' }}
                  >
                    <option value="curriculum">Curriculum Guide</option>
                    <option value="rubric">Rubric Template</option>
                    <option value="standards">Standards Document</option>
                    <option value="general">General Reference</option>
                  </select>
                  <input
                    type="text"
                    className="input"
                    placeholder="Description (optional)"
                    value={newDocDescription}
                    onChange={e => setNewDocDescription(e.target.value)}
                    style={{ flex: 1, minWidth: '200px' }}
                  />
                  <button
                    onClick={() => supportDocInputRef.current?.click()}
                    className="btn btn-secondary"
                    disabled={uploadingDoc}
                  >
                    <Icon name="Upload" size={18} />
                    {uploadingDoc ? 'Uploading...' : 'Upload Document'}
                  </button>
                </div>

                {supportDocs.length > 0 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    {supportDocs.map(doc => (
                      <div key={doc.filename} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 15px', background: 'rgba(0,0,0,0.2)', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.1)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                          <Icon name={doc.doc_type === 'rubric' ? 'ClipboardCheck' : doc.doc_type === 'standards' ? 'BookOpen' : 'FileText'} size={18} style={{ color: '#10b981' }} />
                          <div>
                            <div style={{ fontWeight: 600 }}>{doc.filename}</div>
                            <div style={{ fontSize: '0.8rem', color: 'rgba(255,255,255,0.5)' }}>
                              {doc.doc_type} {doc.description && `• ${doc.description}`}
                            </div>
                          </div>
                        </div>
                        <button
                          onClick={async () => {
                            if (confirm('Delete this document?')) {
                              await api.deleteSupportDocument(doc.filename)
                              const data = await api.listSupportDocuments()
                              setSupportDocs(data.documents || [])
                            }
                          }}
                          style={{ padding: '6px 10px', background: 'rgba(239,68,68,0.2)', border: 'none', borderRadius: '6px', color: '#ef4444', cursor: 'pointer' }}
                        >
                          <Icon name="Trash2" size={14} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
          </div>
        )}

        {/* Roster Column Mapping Modal */}
        {rosterMappingModal.show && (
          <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
            <div className="glass-card" style={{ width: '90%', maxWidth: '500px', maxHeight: '80vh', overflow: 'auto', padding: '25px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                <h3 style={{ fontSize: '1.2rem', fontWeight: 700 }}>Map Roster Columns</h3>
                <button onClick={() => setRosterMappingModal({ show: false, roster: null })} style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer' }}>
                  <Icon name="X" size={24} />
                </button>
              </div>

              <p style={{ fontSize: '0.9rem', color: 'rgba(255,255,255,0.6)', marginBottom: '20px' }}>
                Map your CSV columns to the required fields
              </p>

              {['student_id', 'student_name', 'first_name', 'last_name', 'student_email', 'parent_email'].map(field => (
                <div key={field} style={{ marginBottom: '15px' }}>
                  <label className="label" style={{ textTransform: 'capitalize' }}>{field.replace(/_/g, ' ')}</label>
                  <select
                    className="input"
                    value={rosterMappingModal.roster?.column_mapping?.[field] || ''}
                    onChange={e => {
                      const newMapping = { ...rosterMappingModal.roster?.column_mapping, [field]: e.target.value }
                      setRosterMappingModal(prev => ({
                        ...prev,
                        roster: { ...prev.roster, column_mapping: newMapping }
                      }))
                    }}
                  >
                    <option value="">-- Select Column --</option>
                    {(rosterMappingModal.roster?.headers || []).map(header => (
                      <option key={header} value={header}>{header}</option>
                    ))}
                  </select>
                </div>
              ))}

              <div style={{ display: 'flex', gap: '10px', marginTop: '20px' }}>
                <button
                  onClick={async () => {
                    try {
                      await api.saveRosterMapping(rosterMappingModal.roster.filename, rosterMappingModal.roster.column_mapping)
                      const data = await api.listRosters()
                      setRosters(data.rosters || [])
                      setRosterMappingModal({ show: false, roster: null })
                    } catch (err) {
                      alert('Error saving mapping: ' + err.message)
                    }
                  }}
                  className="btn btn-primary"
                >
                  <Icon name="Save" size={18} />Save Mapping
                </button>
                <button
                  onClick={() => setRosterMappingModal({ show: false, roster: null })}
                  className="btn btn-secondary"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Builder Tab */}
        {activeTab === 'builder' && (
          <div className="fade-in">
            {/* Saved Assignments */}
            <div className="glass-card" style={{ padding: '25px', marginBottom: '20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
                <h3 style={{ fontSize: '1.1rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <Icon name="FolderOpen" size={20} style={{ color: '#10b981' }} />
                  Saved Assignments ({savedAssignments.length})
                </h3>
                <button
                  onClick={() => {
                    setAssignment({ title: '', subject: 'Social Studies', totalPoints: 100, instructions: '', questions: [], customMarkers: [], gradingNotes: '' })
                    setImportedDoc({ text: '', html: '', filename: '', loading: false })
                    setLoadedAssignmentName('')
                  }}
                  className="btn btn-primary"
                >
                  + New Assignment
                </button>
              </div>

              {savedAssignments.length === 0 ? (
                <p style={{ textAlign: 'center', padding: '30px', color: 'rgba(255,255,255,0.4)' }}>No saved assignments yet. Create one below!</p>
              ) : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '12px' }}>
                  {savedAssignments.map(name => (
                    <div
                      key={name}
                      style={{
                        padding: '15px',
                        background: loadedAssignmentName === name ? 'rgba(99,102,241,0.2)' : 'rgba(0,0,0,0.2)',
                        borderRadius: '12px',
                        border: loadedAssignmentName === name ? '2px solid rgba(99,102,241,0.5)' : '1px solid rgba(255,255,255,0.1)',
                        cursor: 'pointer'
                      }}
                      onClick={() => loadAssignment(name)}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                        <div>
                          <div style={{ fontWeight: 600, marginBottom: '5px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <Icon name="FileText" size={16} style={{ color: '#a5b4fc' }} />
                            {name}
                          </div>
                          <div style={{ fontSize: '0.8rem', color: 'rgba(255,255,255,0.5)' }}>Click to load and edit</div>
                        </div>
                        <button onClick={(e) => { e.stopPropagation(); deleteAssignment(name) }} style={{ padding: '4px', background: 'none', border: 'none', color: 'rgba(255,255,255,0.3)', cursor: 'pointer' }}>
                          <Icon name="Trash2" size={14} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Assignment Editor */}
            <div className="glass-card" style={{ padding: '30px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '25px' }}>
                <h2 style={{ fontSize: '1.3rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <Icon name="FileEdit" size={24} />
                  {assignment.title ? `Editing: ${assignment.title}` : 'New Assignment'}
                </h2>
                {assignment.title && (
                  <span style={{ fontSize: '0.85rem', color: 'rgba(255,255,255,0.5)' }}>
                    {(assignment.customMarkers || []).length} markers
                  </span>
                )}
              </div>

              {/* Assignment Details */}
              <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: '15px', marginBottom: '25px' }}>
                <div>
                  <label className="label">Assignment Title</label>
                  <input type="text" className="input" value={assignment.title} onChange={e => setAssignment({ ...assignment, title: e.target.value })} placeholder="e.g., Louisiana Purchase Quiz" />
                </div>
                <div>
                  <label className="label">Subject</label>
                  <select className="input" value={assignment.subject} onChange={e => setAssignment({ ...assignment, subject: e.target.value })}>
                    {Object.keys(markerLibrary).map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
                <div>
                  <label className="label">Total Points</label>
                  <input type="number" className="input" value={assignment.totalPoints} onChange={e => setAssignment({ ...assignment, totalPoints: parseInt(e.target.value) || 100 })} />
                </div>
              </div>

              {/* Import Document */}
              <div style={{ marginBottom: '25px', padding: '20px', background: 'rgba(251,191,36,0.1)', borderRadius: '12px', border: '1px solid rgba(251,191,36,0.3)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <h3 style={{ fontSize: '1rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '5px' }}>
                      <Icon name="FileUp" size={20} />Import Document & Mark Sections
                    </h3>
                    <p style={{ fontSize: '0.85rem', color: 'rgba(255,255,255,0.5)', margin: 0 }}>
                      {importedDoc.text ? <><strong style={{ color: '#fbbf24' }}>{importedDoc.filename}</strong> loaded</> : 'Import a Word or PDF to highlight gradeable sections'}
                    </p>
                  </div>
                  <div style={{ display: 'flex', gap: '10px' }}>
                    <input type="file" ref={fileInputRef} onChange={handleDocImport} accept=".docx,.pdf,.doc,.txt" style={{ display: 'none' }} />
                    {importedDoc.text && (
                      <button onClick={openDocEditor} className="btn btn-secondary"><Icon name="Edit" size={16} />Edit & Mark</button>
                    )}
                    <button onClick={() => fileInputRef.current?.click()} className="btn btn-primary" style={{ background: 'linear-gradient(135deg, #f59e0b, #d97706)' }}>
                      <Icon name="Upload" size={16} />{importedDoc.loading ? 'Loading...' : 'Import Word/PDF'}
                    </button>
                  </div>
                </div>

                {/* Manual Marker Input */}
                <div style={{ marginTop: '15px', display: 'flex', gap: '10px', alignItems: 'center' }}>
                  <input
                    type="text"
                    id="manualMarkerInput"
                    placeholder="Type a marker phrase and press Add..."
                    className="input"
                    style={{ flex: 1 }}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && e.target.value.trim()) {
                        const newMarker = e.target.value.trim()
                        if (!(assignment.customMarkers || []).includes(newMarker)) {
                          setAssignment({ ...assignment, customMarkers: [...(assignment.customMarkers || []), newMarker] })
                        }
                        e.target.value = ''
                      }
                    }}
                  />
                  <button
                    onClick={() => {
                      const input = document.getElementById('manualMarkerInput')
                      if (input?.value.trim()) {
                        const newMarker = input.value.trim()
                        if (!(assignment.customMarkers || []).includes(newMarker)) {
                          setAssignment({ ...assignment, customMarkers: [...(assignment.customMarkers || []), newMarker] })
                        }
                        input.value = ''
                      }
                    }}
                    className="btn btn-secondary"
                  >
                    <Icon name="Plus" size={16} />Add
                  </button>
                </div>

                {/* Custom Markers */}
                {(assignment.customMarkers || []).length > 0 && (
                  <div style={{ marginTop: '15px', display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                    {assignment.customMarkers.map((marker, i) => (
                      <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 12px', background: 'rgba(251,191,36,0.2)', borderRadius: '6px', border: '1px solid rgba(251,191,36,0.3)' }}>
                        <Icon name="Target" size={12} style={{ color: '#fbbf24' }} />
                        <span style={{ fontSize: '0.8rem', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{marker}</span>
                        <button onClick={() => removeMarker(marker)} style={{ background: 'none', border: 'none', color: 'rgba(255,255,255,0.4)', cursor: 'pointer', padding: '0' }}><Icon name="X" size={12} /></button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Marker Library */}
              <div style={{ marginBottom: '25px', padding: '15px 20px', background: 'rgba(99,102,241,0.1)', borderRadius: '12px', border: '1px solid rgba(99,102,241,0.2)' }}>
                <label style={{ display: 'block', fontSize: '0.9rem', fontWeight: 600, marginBottom: '10px' }}><Icon name="Bookmark" size={16} style={{ marginRight: '8px' }} />Suggested Markers for {assignment.subject}</label>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                  {(markerLibrary[assignment.subject] || []).map((marker, i) => (
                    <span
                      key={i}
                      style={{ padding: '6px 12px', background: 'rgba(255,255,255,0.1)', borderRadius: '6px', fontSize: '0.85rem', cursor: 'pointer' }}
                      onClick={() => {
                        if (!(assignment.customMarkers || []).includes(marker)) {
                          setAssignment({ ...assignment, customMarkers: [...(assignment.customMarkers || []), marker] })
                        }
                      }}
                      title="Click to add"
                    >
                      {marker}
                    </span>
                  ))}
                </div>
              </div>

              {/* Grading Notes */}
              <div style={{ marginBottom: '25px' }}>
                <label className="label">Assignment-Specific Grading Notes</label>
                <textarea
                  className="input"
                  value={assignment.gradingNotes}
                  onChange={e => setAssignment({ ...assignment, gradingNotes: e.target.value })}
                  placeholder="Special instructions for grading this assignment..."
                  style={{ minHeight: '100px' }}
                />
              </div>

              {/* Questions */}
              <div style={{ marginBottom: '20px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
                  <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>Questions ({assignment.questions.length}) - {assignment.questions.reduce((sum, q) => sum + (q.points || 0), 0)} pts</h3>
                  <button onClick={addQuestion} className="btn btn-primary"><Icon name="Plus" size={16} /> Add Question</button>
                </div>

                {assignment.questions.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: '40px', background: 'rgba(0,0,0,0.2)', borderRadius: '12px', color: 'rgba(255,255,255,0.4)' }}>
                    <Icon name="FileQuestion" size={40} />
                    <p style={{ marginTop: '10px' }}>No questions yet. Click "Add Question" to start building.</p>
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
                    {assignment.questions.map((q, i) => (
                      <div key={q.id} style={{ background: 'rgba(255,255,255,0.03)', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.1)', padding: '20px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
                          <span style={{ fontSize: '0.9rem', fontWeight: 600, color: '#a5b4fc' }}>Question {i + 1}</span>
                          <button onClick={() => removeQuestion(i)} style={{ padding: '6px 10px', borderRadius: '6px', border: 'none', background: 'rgba(248,113,113,0.2)', color: '#f87171', cursor: 'pointer' }}><Icon name="Trash2" size={14} /></button>
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 150px 100px', gap: '12px', marginBottom: '12px' }}>
                          <div>
                            <label className="label" style={{ fontSize: '0.8rem' }}>Marker</label>
                            <select className="input" value={q.marker} onChange={e => updateQuestion(i, 'marker', e.target.value)}>
                              {(markerLibrary[assignment.subject] || markerLibrary['Other']).map(m => <option key={m} value={m}>{m}</option>)}
                            </select>
                          </div>
                          <div>
                            <label className="label" style={{ fontSize: '0.8rem' }}>Type</label>
                            <select className="input" value={q.type} onChange={e => updateQuestion(i, 'type', e.target.value)}>
                              <option value="short_answer">Short Answer</option>
                              <option value="essay">Essay</option>
                              <option value="fill_blank">Fill in Blank</option>
                              <option value="multiple_choice">Multiple Choice</option>
                            </select>
                          </div>
                          <div>
                            <label className="label" style={{ fontSize: '0.8rem' }}>Points</label>
                            <input type="number" className="input" value={q.points} onChange={e => updateQuestion(i, 'points', parseInt(e.target.value) || 0)} min="0" />
                          </div>
                        </div>
                        <div>
                          <label className="label" style={{ fontSize: '0.8rem' }}>Question/Prompt</label>
                          <textarea className="input" value={q.prompt} onChange={e => updateQuestion(i, 'prompt', e.target.value)} placeholder="Enter the question..." style={{ minHeight: '60px' }} />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Export Buttons */}
              <div style={{ display: 'flex', gap: '15px', flexWrap: 'wrap' }}>
                <button onClick={saveAssignmentConfig} disabled={!assignment.title} className="btn btn-primary" style={{ opacity: !assignment.title ? 0.5 : 1 }}>
                  <Icon name="Save" size={18} /> Save for Grading
                </button>
                <button onClick={() => exportAssignment('docx')} disabled={!assignment.title} className="btn btn-secondary" style={{ opacity: !assignment.title ? 0.5 : 1 }}>
                  <Icon name="FileText" size={18} /> Export Word Doc
                </button>
                <button onClick={() => exportAssignment('pdf')} disabled={!assignment.title} className="btn btn-secondary" style={{ opacity: !assignment.title ? 0.5 : 1 }}>
                  <Icon name="FileType" size={18} /> Export PDF
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Analytics Tab */}
        {activeTab === 'analytics' && (
          <div className="fade-in">
            {!analytics || analytics.error ? (
              <div className="glass-card" style={{ padding: '60px', textAlign: 'center' }}>
                <Icon name="BarChart3" size={64} />
                <h2 style={{ marginTop: '20px', fontSize: '1.5rem' }}>No Data Yet</h2>
                <p style={{ color: 'rgba(255,255,255,0.5)', marginTop: '10px' }}>Grade some assignments to see analytics here.</p>
              </div>
            ) : (
              <>
                {/* Period Filter */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
                  <h2 style={{ fontSize: '1.3rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <Icon name="BarChart3" size={24} />Class Analytics
                  </h2>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <label style={{ fontSize: '0.9rem', color: 'rgba(255,255,255,0.6)' }}>Filter by Period:</label>
                    <select value={analyticsPeriod} onChange={e => setAnalyticsPeriod(e.target.value)} className="input" style={{ width: 'auto' }}>
                      <option value="all">All Periods</option>
                      {(analytics.available_periods || []).map(p => <option key={p} value={p}>{p}</option>)}
                    </select>
                  </div>
                </div>

                {/* Stats Cards */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '15px', marginBottom: '20px' }}>
                  {[
                    { label: 'Total Graded', value: analytics.class_stats?.total_assignments || 0, icon: 'FileCheck', color: '#6366f1' },
                    { label: 'Students', value: analytics.class_stats?.total_students || 0, icon: 'Users', color: '#8b5cf6' },
                    { label: 'Class Average', value: `${analytics.class_stats?.class_average || 0}%`, icon: 'TrendingUp', color: '#10b981' },
                    { label: 'Highest Score', value: `${analytics.class_stats?.highest || 0}%`, icon: 'Trophy', color: '#f59e0b' },
                  ].map((stat, i) => (
                    <div key={i} className="glass-card" style={{ padding: '20px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
                        <div style={{ background: `${stat.color}20`, padding: '8px', borderRadius: '10px' }}><Icon name={stat.icon} size={20} /></div>
                        <span style={{ color: 'rgba(255,255,255,0.6)', fontSize: '0.9rem' }}>{stat.label}</span>
                      </div>
                      <div style={{ fontSize: '2rem', fontWeight: 800, color: stat.color }}>{stat.value}</div>
                    </div>
                  ))}
                </div>

                {/* Charts */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '20px', marginBottom: '20px' }}>
                  <div className="glass-card" style={{ padding: '25px' }}>
                    <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '10px' }}><Icon name="PieChart" size={20} />Grade Distribution</h3>
                    <ResponsiveContainer width="100%" height={200}>
                      <PieChart>
                        <Pie
                          data={[
                            { name: 'A', value: analytics.class_stats?.grade_distribution?.A || 0 },
                            { name: 'B', value: analytics.class_stats?.grade_distribution?.B || 0 },
                            { name: 'C', value: analytics.class_stats?.grade_distribution?.C || 0 },
                            { name: 'D', value: analytics.class_stats?.grade_distribution?.D || 0 },
                            { name: 'F', value: analytics.class_stats?.grade_distribution?.F || 0 },
                          ].filter(d => d.value > 0)}
                          cx="50%" cy="50%" outerRadius={70} dataKey="value"
                          label={({ name, value }) => `${name}: ${value}`}
                        >
                          {['#4ade80', '#60a5fa', '#fbbf24', '#f97316', '#ef4444'].map((c, i) => <Cell key={i} fill={c} />)}
                        </Pie>
                        <Tooltip />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>

                  <div className="glass-card" style={{ padding: '25px' }}>
                    <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '10px' }}><Icon name="BarChart3" size={20} />Assignment Averages</h3>
                    <ResponsiveContainer width="100%" height={200}>
                      <BarChart data={analytics.assignment_stats || []}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                        <XAxis dataKey="name" tick={{ fill: 'rgba(255,255,255,0.6)', fontSize: 11 }} />
                        <YAxis domain={[0, 100]} tick={{ fill: 'rgba(255,255,255,0.6)' }} />
                        <Tooltip contentStyle={{ background: '#1a1a2e', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }} />
                        <Bar dataKey="average" fill="#6366f1" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* Student Progress */}
                <div className="glass-card" style={{ padding: '25px', marginBottom: '20px', border: selectedStudent ? '2px solid #6366f1' : undefined }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
                    <h3 style={{ fontSize: '1.1rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <Icon name="TrendingUp" size={20} />
                      {selectedStudent ? `${selectedStudent}'s Progress` : 'Student Progress Over Time'}
                    </h3>
                    {selectedStudent && (
                      <button onClick={() => setSelectedStudent(null)} className="btn btn-secondary" style={{ padding: '6px 12px' }}>
                        <Icon name="X" size={14} /> Clear Selection
                      </button>
                    )}
                  </div>

                  {selectedStudent && (() => {
                    const studentData = (analytics.student_progress || []).find(s => s.name === selectedStudent)
                    if (!studentData) return null
                    const grades = studentData.grades || []
                    const highest = grades.length > 0 ? Math.max(...grades.map(g => g.score)) : 0
                    const lowest = grades.length > 0 ? Math.min(...grades.map(g => g.score)) : 0
                    return (
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '15px', marginBottom: '20px' }}>
                        <div style={{ background: 'rgba(99,102,241,0.1)', borderRadius: '12px', padding: '15px', textAlign: 'center' }}>
                          <div style={{ fontSize: '0.8rem', color: 'rgba(255,255,255,0.5)', marginBottom: '5px' }}>Average</div>
                          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#6366f1' }}>{studentData.average}%</div>
                        </div>
                        <div style={{ background: 'rgba(74,222,128,0.1)', borderRadius: '12px', padding: '15px', textAlign: 'center' }}>
                          <div style={{ fontSize: '0.8rem', color: 'rgba(255,255,255,0.5)', marginBottom: '5px' }}>Highest</div>
                          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#4ade80' }}>{highest}%</div>
                        </div>
                        <div style={{ background: 'rgba(248,113,113,0.1)', borderRadius: '12px', padding: '15px', textAlign: 'center' }}>
                          <div style={{ fontSize: '0.8rem', color: 'rgba(255,255,255,0.5)', marginBottom: '5px' }}>Lowest</div>
                          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#f87171' }}>{lowest}%</div>
                        </div>
                        <div style={{ background: 'rgba(251,191,36,0.1)', borderRadius: '12px', padding: '15px', textAlign: 'center' }}>
                          <div style={{ fontSize: '0.8rem', color: 'rgba(255,255,255,0.5)', marginBottom: '5px' }}>Assignments</div>
                          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#fbbf24' }}>{grades.length}</div>
                        </div>
                      </div>
                    )
                  })()}

                  {!selectedStudent && (
                    <p style={{ fontSize: '0.85rem', color: 'rgba(255,255,255,0.5)', marginBottom: '15px' }}>Click a student name below to view details</p>
                  )}

                  <ResponsiveContainer width="100%" height={250}>
                    <LineChart data={(() => {
                      const filtered = selectedStudent
                        ? (analytics.student_progress || []).filter(s => s.name === selectedStudent)
                        : (analytics.student_progress || [])
                      const allGrades = filtered.flatMap(s => (s.grades || []).map(g => ({ ...g, student: s.name.split(' ')[0] })))
                      return allGrades.sort((a, b) => (a.date || '').localeCompare(b.date || ''))
                    })()}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                      <XAxis dataKey="assignment" tick={{ fill: 'rgba(255,255,255,0.6)', fontSize: 10 }} angle={-20} textAnchor="end" height={60} />
                      <YAxis domain={[0, 100]} tick={{ fill: 'rgba(255,255,255,0.6)' }} />
                      <Tooltip contentStyle={{ background: '#1a1a2e', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }} />
                      <Line type="monotone" dataKey="score" stroke="#6366f1" strokeWidth={3} dot={{ fill: '#6366f1', r: 5 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>

                {/* Needs Attention + Top Performers */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '20px' }}>
                  <div style={{ background: 'rgba(239,68,68,0.1)', borderRadius: '20px', border: '1px solid rgba(239,68,68,0.3)', padding: '25px' }}>
                    <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '15px', display: 'flex', alignItems: 'center', gap: '10px', color: '#f87171' }}><Icon name="AlertTriangle" size={20} />Needs Attention</h3>
                    {(analytics.attention_needed || []).length === 0 ? (
                      <p style={{ color: 'rgba(255,255,255,0.5)' }}>All students are doing well!</p>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                        {(analytics.attention_needed || []).slice(0, 5).map((s, i) => (
                          <div key={i} onClick={() => setSelectedStudent(s.name)} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 15px', background: 'rgba(0,0,0,0.2)', borderRadius: '10px', cursor: 'pointer' }}>
                            <span style={{ textDecoration: 'underline dotted' }}>{s.name}</span>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                              <span style={{ color: '#f87171', fontWeight: 700 }}>{s.average}%</span>
                              <span style={{ fontSize: '0.8rem', padding: '2px 8px', borderRadius: '4px', background: s.trend === 'declining' ? 'rgba(239,68,68,0.3)' : 'rgba(251,191,36,0.3)', color: s.trend === 'declining' ? '#f87171' : '#fbbf24' }}>{s.trend}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  <div style={{ background: 'rgba(74,222,128,0.1)', borderRadius: '20px', border: '1px solid rgba(74,222,128,0.3)', padding: '25px' }}>
                    <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '15px', display: 'flex', alignItems: 'center', gap: '10px', color: '#4ade80' }}><Icon name="Award" size={20} />Top Performers</h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                      {(analytics.top_performers || []).map((s, i) => (
                        <div key={i} onClick={() => setSelectedStudent(s.name)} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 15px', background: 'rgba(0,0,0,0.2)', borderRadius: '10px', cursor: 'pointer' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                            <span style={{ width: '24px', height: '24px', borderRadius: '50%', background: i === 0 ? '#fbbf24' : i === 1 ? '#94a3b8' : i === 2 ? '#cd7f32' : 'rgba(255,255,255,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.75rem', fontWeight: 700 }}>{i + 1}</span>
                            <span style={{ textDecoration: 'underline dotted' }}>{s.name}</span>
                          </div>
                          <span style={{ color: '#4ade80', fontWeight: 700 }}>{s.average}%</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* All Students Table */}
                <div className="glass-card" style={{ padding: '25px' }}>
                  <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '15px', display: 'flex', alignItems: 'center', gap: '10px' }}><Icon name="Users" size={20} />All Students Overview</h3>
                  <table>
                    <thead>
                      <tr>
                        <th>Student</th>
                        <th style={{ textAlign: 'center' }}>Assignments</th>
                        <th style={{ textAlign: 'center' }}>Average</th>
                        <th style={{ textAlign: 'center' }}>Trend</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(analytics.student_progress || []).map((s, i) => (
                        <tr key={i} onClick={() => setSelectedStudent(s.name)} style={{ cursor: 'pointer', background: selectedStudent === s.name ? 'rgba(99,102,241,0.2)' : 'transparent' }}>
                          <td style={{ fontWeight: 600, textDecoration: 'underline dotted' }}>{s.name}</td>
                          <td style={{ textAlign: 'center' }}>{(s.grades || []).length}</td>
                          <td style={{ textAlign: 'center' }}>
                            <span style={{
                              padding: '4px 12px', borderRadius: '20px', fontWeight: 700,
                              background: s.average >= 90 ? 'rgba(74,222,128,0.2)' : s.average >= 80 ? 'rgba(96,165,250,0.2)' : s.average >= 70 ? 'rgba(251,191,36,0.2)' : 'rgba(248,113,113,0.2)',
                              color: s.average >= 90 ? '#4ade80' : s.average >= 80 ? '#60a5fa' : s.average >= 70 ? '#fbbf24' : '#f87171'
                            }}>{s.average}%</span>
                          </td>
                          <td style={{ textAlign: 'center' }}>
                            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', color: s.trend === 'improving' ? '#4ade80' : s.trend === 'declining' ? '#f87171' : '#94a3b8' }}>
                              <Icon name={s.trend === 'improving' ? 'TrendingUp' : s.trend === 'declining' ? 'TrendingDown' : 'Minus'} size={16} />
                              {s.trend}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>
        )}

        {/* Planner Tab */}
        {activeTab === 'planner' && (
          <div className="fade-in">
            <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: '25px' }}>
              {/* Sidebar */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                {/* Configuration */}
                <div className="glass-card" style={{ padding: '20px' }}>
                  <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '15px', display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <Icon name="Settings2" size={20} /> Configuration
                  </h3>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
                    <div>
                      <label className="label">State</label>
                      <select className="input" value={plannerConfig.state} onChange={e => setPlannerConfig({ ...plannerConfig, state: e.target.value })}>
                        <option value="FL">Florida</option>
                        <option value="TX">Texas</option>
                        <option value="NY">New York</option>
                        <option value="CA">California</option>
                      </select>
                    </div>
                    <div>
                      <label className="label">Grade Level</label>
                      <select className="input" value={plannerConfig.grade} onChange={e => setPlannerConfig({ ...plannerConfig, grade: e.target.value })}>
                        {['K', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12'].map(g => (
                          <option key={g} value={g}>{g === 'K' ? 'Kindergarten' : `${g}${g === '1' ? 'st' : g === '2' ? 'nd' : g === '3' ? 'rd' : 'th'} Grade`}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="label">Subject</label>
                      <select className="input" value={plannerConfig.subject} onChange={e => setPlannerConfig({ ...plannerConfig, subject: e.target.value })}>
                        <option value="Civics">Civics</option>
                        <option value="History">History</option>
                        <option value="Geography">Geography</option>
                        <option value="Economics">Economics</option>
                        <option value="Math">Math</option>
                        <option value="Science">Science</option>
                        <option value="ELA">English / ELA</option>
                      </select>
                    </div>
                  </div>
                </div>

                {/* Unit Details */}
                <div className="glass-card" style={{ padding: '20px' }}>
                  <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '15px', display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <Icon name="FileText" size={20} /> Details
                  </h3>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
                    <div>
                      <label className="label">Content Type</label>
                      <select className="input" value={unitConfig.type} onChange={e => setUnitConfig({ ...unitConfig, type: e.target.value })}>
                        <option value="Unit Plan">Unit Plan</option>
                        <option value="Lesson Plan">Lesson Plan</option>
                        <option value="Assignment">Assignment</option>
                        <option value="Project">Project</option>
                      </select>
                    </div>
                    <div>
                      <label className="label">Title</label>
                      <input type="text" className="input" value={unitConfig.title} onChange={e => setUnitConfig({ ...unitConfig, title: e.target.value })} placeholder="e.g., Foundations of Government" />
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                      <div>
                        <label className="label">Duration (Days)</label>
                        <input type="number" className="input" value={unitConfig.duration} onChange={e => setUnitConfig({ ...unitConfig, duration: parseInt(e.target.value) || 1 })} min="1" max="20" />
                      </div>
                      <div>
                        <label className="label">Period Length</label>
                        <input type="number" className="input" value={unitConfig.periodLength} onChange={e => setUnitConfig({ ...unitConfig, periodLength: parseInt(e.target.value) || 50 })} min="20" max="120" />
                      </div>
                    </div>
                    <div>
                      <label className="label">Additional Requirements</label>
                      <textarea className="input" value={unitConfig.requirements} onChange={e => setUnitConfig({ ...unitConfig, requirements: e.target.value })} placeholder="e.g. Focus on primary sources..." style={{ minHeight: '80px' }} />
                    </div>
                    <button
                      onClick={generateLessonPlan}
                      disabled={plannerLoading || selectedStandards.length === 0}
                      className="btn btn-primary"
                      style={{ width: '100%', justifyContent: 'center', opacity: (plannerLoading || selectedStandards.length === 0) ? 0.5 : 1 }}
                    >
                      {plannerLoading ? <Icon name="Loader2" size={18} style={{ animation: 'spin 1s linear infinite' }} /> : <Icon name="Sparkles" size={18} />}
                      {plannerLoading ? 'Generating...' : 'Generate Plan'}
                    </button>
                  </div>
                </div>
              </div>

              {/* Main Content */}
              <div>
                {lessonPlan ? (
                  <div className="glass-card" style={{ padding: '30px', maxHeight: '80vh', overflowY: 'auto' }}>
                    {/* Header */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '25px', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '20px' }}>
                      <div>
                        <h2 style={{ fontSize: '1.8rem', fontWeight: 700, marginBottom: '10px' }}>{lessonPlan.title}</h2>
                        <p style={{ color: 'rgba(255,255,255,0.6)', lineHeight: '1.6' }}>{lessonPlan.overview}</p>
                      </div>
                      <div style={{ display: 'flex', gap: '10px' }}>
                        <button onClick={exportLessonPlanHandler} className="btn btn-secondary"><Icon name="Download" size={16} /> Export</button>
                        <button onClick={() => setLessonPlan(null)} className="btn btn-secondary">Close</button>
                      </div>
                    </div>

                    {/* Days */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '30px' }}>
                      {(lessonPlan.days || []).map((day, i) => (
                        <div key={i} style={{ background: 'rgba(0,0,0,0.3)', borderRadius: '16px', padding: '25px' }}>
                          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '15px', marginBottom: '20px', paddingBottom: '15px', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
                            <div style={{ width: '50px', height: '50px', borderRadius: '12px', background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: '1.2rem' }}>{day.day}</div>
                            <div style={{ flex: 1 }}>
                              <h3 style={{ fontSize: '1.3rem', fontWeight: 600, marginBottom: '8px' }}>{day.topic}</h3>
                              <p style={{ fontSize: '0.9rem', color: 'rgba(255,255,255,0.8)' }}><strong style={{ color: '#10b981' }}>Objective:</strong> {day.objective}</p>
                            </div>
                          </div>

                          {day.bell_ringer && (
                            <div style={{ marginBottom: '15px', padding: '15px', background: 'rgba(165,180,252,0.1)', borderRadius: '10px', border: '1px solid rgba(165,180,252,0.2)' }}>
                              <h4 style={{ fontSize: '0.9rem', color: '#a5b4fc', marginBottom: '8px' }}><Icon name="Zap" size={14} /> Bell Ringer</h4>
                              <p style={{ fontSize: '0.9rem' }}>{typeof day.bell_ringer === 'object' ? day.bell_ringer.prompt : day.bell_ringer}</p>
                            </div>
                          )}

                          {day.activity && (
                            <div style={{ marginBottom: '15px', padding: '15px', background: 'rgba(74,222,128,0.1)', borderRadius: '10px', border: '1px solid rgba(74,222,128,0.2)' }}>
                              <h4 style={{ fontSize: '0.9rem', color: '#4ade80', marginBottom: '8px' }}><Icon name="Activity" size={14} /> Main Activity</h4>
                              <p style={{ fontSize: '0.9rem' }}>{typeof day.activity === 'object' ? day.activity.description : day.activity}</p>
                            </div>
                          )}

                          {day.assessment && (
                            <div style={{ padding: '15px', background: 'rgba(248,113,113,0.1)', borderRadius: '10px', border: '1px solid rgba(248,113,113,0.2)' }}>
                              <h4 style={{ fontSize: '0.9rem', color: '#f87171', marginBottom: '8px' }}><Icon name="CheckCircle" size={14} /> Assessment</h4>
                              <p style={{ fontSize: '0.9rem' }}>{typeof day.assessment === 'object' ? day.assessment.description : day.assessment}</p>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="glass-card" style={{ padding: '25px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
                      <h3 style={{ fontSize: '1.1rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <Icon name="Library" size={20} /> Select Standards ({selectedStandards.length})
                      </h3>
                      <span style={{ fontSize: '0.9rem', color: 'rgba(255,255,255,0.5)' }}>{standards.length} standards available</span>
                    </div>

                    <div style={{ maxHeight: '500px', overflowY: 'auto' }}>
                      {plannerLoading ? (
                        <div style={{ textAlign: 'center', padding: '40px', color: 'rgba(255,255,255,0.5)' }}>
                          <Icon name="Loader2" size={30} style={{ animation: 'spin 1s linear infinite' }} />
                          <p style={{ marginTop: '10px' }}>Loading standards...</p>
                        </div>
                      ) : standards.length > 0 ? (
                        standards.map(std => (
                          <StandardCard
                            key={std.code}
                            standard={std}
                            isSelected={selectedStandards.includes(std.code)}
                            onToggle={() => toggleStandard(std.code)}
                          />
                        ))
                      ) : (
                        <div style={{ textAlign: 'center', padding: '40px', background: 'rgba(255,255,255,0.03)', borderRadius: '12px' }}>
                          <p style={{ color: 'rgba(255,255,255,0.5)' }}>No standards found for this configuration.</p>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Footer */}
      <footer style={{ textAlign: 'center', marginTop: '30px', padding: '20px', color: 'rgba(255,255,255,0.3)', fontSize: '0.85rem' }}>
        Powered by OpenAI GPT-4o
      </footer>
    </div>
  )
}

export default App
