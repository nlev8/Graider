import { useState, useEffect, useRef } from "react";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import Icon from "./components/Icon";
import * as api from "./services/api";

// Tab configuration
const TABS = [
  { id: "grade", label: "Grade", icon: "GraduationCap" },
  { id: "results", label: "Results", icon: "FileText" },
  { id: "builder", label: "Builder", icon: "FileEdit" },
  { id: "analytics", label: "Analytics", icon: "BarChart3" },
  { id: "planner", label: "Planner", icon: "BookOpen" },
  { id: "resources", label: "Resources", icon: "FolderOpen" },
  { id: "settings", label: "Settings", icon: "Settings" },
];

// Marker libraries by subject
const markerLibrary = {
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
  Other: [
    "Answer:",
    "Explain:",
    "Describe:",
    "Your response:",
    "Short answer:",
    "Essay:",
  ],
};

// StandardCard component for Planner
function StandardCard({ standard, isSelected, onToggle }) {
  return (
    <div
      onClick={onToggle}
      style={{
        background: isSelected
          ? "rgba(99,102,241,0.2)"
          : "var(--glass-bg)",
        border: isSelected
          ? "1px solid var(--accent-primary)"
          : "1px solid var(--glass-border)",
        borderRadius: "12px",
        padding: "15px",
        cursor: "pointer",
        transition: "all 0.2s",
        marginBottom: "10px",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          marginBottom: "8px",
        }}
      >
        <span
          style={{
            fontWeight: 700,
            color: isSelected ? "var(--accent-light)" : "var(--text-primary)",
            fontSize: "0.9rem",
          }}
        >
          {standard.code}
        </span>
        {isSelected && (
          <Icon name="CheckCircle" size={18} style={{ color: "var(--accent-primary)" }} />
        )}
      </div>
      <p
        style={{
          fontSize: "0.9rem",
          color: "var(--text-secondary)",
          lineHeight: "1.5",
          margin: "0 0 10px 0",
        }}
      >
        {standard.benchmark}
      </p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
        {(standard.topics || []).map((topic) => (
          <span
            key={topic}
            style={{
              fontSize: "0.75rem",
              padding: "3px 8px",
              borderRadius: "4px",
              background: "var(--glass-hover)",
              color: "var(--text-secondary)",
            }}
          >
            {topic}
          </span>
        ))}
      </div>
    </div>
  );
}

// Helper functions for authenticity checks
const getAuthenticityStatus = (result) => {
  // New format with separate AI and plagiarism detection
  if (result.ai_detection || result.plagiarism_detection) {
    const ai = result.ai_detection || { flag: "none", confidence: 0, reason: "" };
    const plag = result.plagiarism_detection || { flag: "none", reason: "" };

    // Determine overall status for summary views
    const aiConcern = ai.flag === "likely" || ai.flag === "possible";
    const plagConcern = plag.flag === "likely" || plag.flag === "possible";

    let overallStatus = "clean";
    if (ai.flag === "likely" || plag.flag === "likely") {
      overallStatus = "flagged";
    } else if (aiConcern || plagConcern) {
      overallStatus = "review";
    }

    return { ai, plag, overallStatus, isNewFormat: true };
  }

  // Backward compatibility with old format
  const flag = result.authenticity_flag || "clean";
  const reason = result.authenticity_reason || "";
  return {
    ai: {
      flag: flag === "flagged" ? "likely" : flag === "review" ? "possible" : "none",
      confidence: flag === "flagged" ? 80 : flag === "review" ? 50 : 0,
      reason: flag !== "clean" ? reason : ""
    },
    plag: { flag: "none", reason: "" },
    overallStatus: flag,
    isNewFormat: false
  };
};

const getAIFlagColor = (flag) => {
  switch (flag) {
    case "likely": return { bg: "rgba(248,113,113,0.2)", text: "#f87171" };
    case "possible": return { bg: "rgba(251,191,36,0.2)", text: "#fbbf24" };
    case "unlikely": return { bg: "rgba(96,165,250,0.2)", text: "#60a5fa" };
    default: return { bg: "rgba(74,222,128,0.2)", text: "#4ade80" };
  }
};

const getPlagFlagColor = (flag) => {
  switch (flag) {
    case "likely": return { bg: "rgba(248,113,113,0.2)", text: "#f87171" };
    case "possible": return { bg: "rgba(251,191,36,0.2)", text: "#fbbf24" };
    default: return { bg: "rgba(74,222,128,0.2)", text: "#4ade80" };
  }
};

function App() {
  // Theme state with localStorage persistence
  const [theme, setTheme] = useState(() => {
    const savedTheme = localStorage.getItem("graider-theme");
    return savedTheme || "dark";
  });

  // Apply theme to document body
  useEffect(() => {
    document.body.setAttribute("data-theme", theme);
    localStorage.setItem("graider-theme", theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === "dark" ? "light" : "dark"));
  };

  // Core state
  const [config, setConfig] = useState({
    assignments_folder: "",
    output_folder: "",
    roster_file: "",
    grading_period: "Q1",
    grade_level: "7",
    subject: "US History",
    state: "FL",
    teacher_name: "",
    school_name: "",
    showToastNotifications: true,
    ai_model: "gpt-4o-mini",
  });

  const [status, setStatus] = useState({
    is_running: false,
    progress: 0,
    total: 0,
    current_file: "",
    log: [],
    results: [],
    complete: false,
    error: null,
  });

  // File selection state
  const [availableFiles, setAvailableFiles] = useState([]);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [filesLoading, setFilesLoading] = useState(false);
  const [selectedPeriod, setSelectedPeriod] = useState("");
  const [periodStudents, setPeriodStudents] = useState([]);

  const [activeTab, setActiveTab] = useState("grade");
  const [analytics, setAnalytics] = useState(null);
  const [selectedStudent, setSelectedStudent] = useState(null);
  const [analyticsPeriod, setAnalyticsPeriod] = useState("all");
  const [autoGrade, setAutoGrade] = useState(false);
  const [showActivityLog, setShowActivityLog] = useState(false);
  const [globalAINotes, setGlobalAINotes] = useState("");
  const [watchStatus, setWatchStatus] = useState({
    watching: false,
    lastCheck: null,
    newFiles: 0,
  });

  // Toast notifications
  const [toasts, setToasts] = useState([]);
  const lastResultCount = useRef(0);

  const addToast = (message, type = "success", duration = 4000) => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, duration);
  };

  // Sidebar state
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // Builder state
  const [assignment, setAssignment] = useState({
    title: "",
    subject: "Social Studies",
    totalPoints: 100,
    instructions: "",
    questions: [],
    customMarkers: [],
    gradingNotes: "",
    responseSections: [],
  });
  const [savedAssignments, setSavedAssignments] = useState([]);
  const [loadedAssignmentName, setLoadedAssignmentName] = useState("");
  const [gradeAssignment, setGradeAssignment] = useState({
    title: "",
    customMarkers: [],
    gradingNotes: "",
    responseSections: [],
  });
  const [gradeImportedDoc, setGradeImportedDoc] = useState({
    text: "",
    html: "",
    filename: "",
  });
  const [importedDoc, setImportedDoc] = useState({
    text: "",
    html: "",
    filename: "",
    loading: false,
  });
  const [docEditorModal, setDocEditorModal] = useState({
    show: false,
    editedHtml: "",
    viewMode: "formatted",
  });

  // Results state
  const [editedResults, setEditedResults] = useState([]);
  const [reviewModal, setReviewModal] = useState({ show: false, index: -1 });
  const [reviewModalTab, setReviewModalTab] = useState("detected"); // "detected" or "raw"
  const [emailPreview, setEmailPreview] = useState({ show: false, emails: [] });
  const [emailStatus, setEmailStatus] = useState({
    sending: false,
    sent: 0,
    failed: 0,
    message: "",
  });
  const [emailApprovals, setEmailApprovals] = useState({}); // { index: 'approved' | 'rejected' | 'pending' }
  const [autoApproveEmails, setAutoApproveEmails] = useState(false);
  const [viewingEmailIndex, setViewingEmailIndex] = useState(null);
  const [editedEmails, setEditedEmails] = useState({}); // { index: { subject, body } }
  const [resultsSearch, setResultsSearch] = useState("");

  // Planner state
  const [standards, setStandards] = useState([]);
  const [selectedStandards, setSelectedStandards] = useState([]);
  const [lessonPlan, setLessonPlan] = useState(null);
  const [plannerLoading, setPlannerLoading] = useState(false);
  const [unitConfig, setUnitConfig] = useState({
    title: "",
    duration: 1,
    periodLength: 50,
    type: "Lesson Plan",
    format: "Word",
    requirements: "",
  });

  // File upload state
  const [rosters, setRosters] = useState([]);
  const [periods, setPeriods] = useState([]);
  const [supportDocs, setSupportDocs] = useState([]);
  const [uploadingRoster, setUploadingRoster] = useState(false);
  const [uploadingPeriod, setUploadingPeriod] = useState(false);
  const [uploadingDoc, setUploadingDoc] = useState(false);
  const [newPeriodName, setNewPeriodName] = useState("");
  const [newDocType, setNewDocType] = useState("curriculum");
  const [newDocDescription, setNewDocDescription] = useState("");
  const [rosterMappingModal, setRosterMappingModal] = useState({
    show: false,
    roster: null,
  });

  // Rubric state
  const [rubric, setRubric] = useState({
    categories: [
      {
        name: "Content Accuracy",
        weight: 40,
        description: "Are answers factually correct?",
      },
      {
        name: "Completeness",
        weight: 25,
        description: "Did student attempt all questions?",
      },
      {
        name: "Writing Quality",
        weight: 20,
        description: "Is writing clear and readable?",
      },
      {
        name: "Effort & Engagement",
        weight: 15,
        description: "Did student show genuine effort?",
      },
    ],
    generous: true,
  });

  const logRef = useRef(null);
  const fileInputRef = useRef(null);
  const docHtmlRef = useRef(null);
  const rosterInputRef = useRef(null);
  const periodInputRef = useRef(null);
  const supportDocInputRef = useRef(null);

  // Track if initial load is complete (to avoid saving on first render)
  const [settingsLoaded, setSettingsLoaded] = useState(false);

  // Load saved settings on startup
  useEffect(() => {
    Promise.all([
      api
        .loadGlobalSettings()
        .then((data) => {
          if (data.settings?.globalAINotes)
            setGlobalAINotes(data.settings.globalAINotes);
          if (data.settings?.config) {
            // Migrate old "History" subject to "US History"
            const loadedConfig = { ...data.settings.config };
            if (loadedConfig.subject === 'History') {
              loadedConfig.subject = 'US History';
            }
            setConfig((prev) => ({ ...prev, ...loadedConfig }));
          }
        })
        .catch(console.error),
      api
        .loadRubric()
        .then((data) => {
          if (data.rubric) setRubric(data.rubric);
        })
        .catch(console.error),
    ]).then(() => {
      // Mark settings as loaded after a short delay to prevent immediate auto-save
      setTimeout(() => setSettingsLoaded(true), 500);
    });

    api
      .listAssignments()
      .then((data) => {
        if (data.assignments) setSavedAssignments(data.assignments);
      })
      .catch(console.error);

    // Load uploaded files
    api
      .listRosters()
      .then((data) => {
        if (data.rosters) setRosters(data.rosters);
      })
      .catch(console.error);

    api
      .listPeriods()
      .then((data) => {
        if (data.periods) setPeriods(data.periods);
      })
      .catch(console.error);

    api
      .listSupportDocuments()
      .then((data) => {
        if (data.documents) setSupportDocs(data.documents);
      })
      .catch(console.error);
  }, []);

  // Auto-save settings when they change (debounced)
  useEffect(() => {
    if (!settingsLoaded) return; // Don't save until initial load is complete

    const saveTimeout = setTimeout(() => {
      api.saveGlobalSettings({ globalAINotes, config }).catch(console.error);
    }, 1000); // Debounce 1 second

    return () => clearTimeout(saveTimeout);
  }, [config, globalAINotes, settingsLoaded]);

  // Auto-save rubric when it changes (debounced)
  useEffect(() => {
    if (!settingsLoaded) return;

    const saveTimeout = setTimeout(() => {
      api.saveRubric(rubric).catch(console.error);
    }, 1000);

    return () => clearTimeout(saveTimeout);
  }, [rubric, settingsLoaded]);

  // Poll status while grading
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const data = await api.getStatus();
        setStatus(data);
      } catch (error) {
        console.error("Status poll error:", error);
      }
    }, 500);
    return () => clearInterval(interval);
  }, []);

  // Auto-grade watcher
  useEffect(() => {
    if (!autoGrade) return;
    const watchInterval = setInterval(async () => {
      if (status.is_running) return;
      try {
        const data = await api.checkNewFiles(
          config.assignments_folder,
          config.output_folder,
        );
        setWatchStatus({
          watching: true,
          lastCheck: new Date().toLocaleTimeString(),
          newFiles: data.new_files || 0,
        });
        if (data.new_files > 0 && !status.is_running) {
          // Load files and filter by period before auto-grading
          const filesData = await api.listFiles(config.assignments_folder);
          if (filesData.files) {
            let filesToGrade = filesData.files.filter(f => !f.graded);

            // Filter by period if one is selected
            if (selectedPeriod && periodStudents.length > 0) {
              filesToGrade = filesToGrade.filter(f =>
                fileMatchesPeriodStudent(f.name, periodStudents)
              );
            }

            if (filesToGrade.length > 0) {
              // Update selected files and start grading
              const fileNames = filesToGrade.map(f => f.name);
              setSelectedFiles(fileNames);
              setAvailableFiles(filesData.files);
              // Small delay to ensure state updates before grading starts
              setTimeout(() => handleStartGrading(), 100);
            }
          }
        }
      } catch (e) {
        console.error("Watch error:", e);
      }
    }, 10000);
    setWatchStatus({ watching: true, lastCheck: "Starting...", newFiles: 0 });
    return () => {
      clearInterval(watchInterval);
      setWatchStatus({ watching: false, lastCheck: null, newFiles: 0 });
    };
  }, [
    autoGrade,
    config.assignments_folder,
    config.output_folder,
    status.is_running,
    selectedPeriod,
    periodStudents,
  ]);

  // Fetch analytics when tab opens
  useEffect(() => {
    if (activeTab === "analytics") {
      api
        .getAnalytics(analyticsPeriod)
        .then((data) => setAnalytics(data))
        .catch(console.error);
    }
  }, [activeTab, analyticsPeriod]);

  // Load standards when settings config changes
  useEffect(() => {
    if (activeTab === "planner" && config.subject) {
      setPlannerLoading(true);
      api.getStandards({
        state: config.state || 'FL',
        grade: config.grade_level || '7',
        subject: config.subject,
      })
        .then((data) => {
          console.log('Standards loaded:', data);
          setStandards(data.standards || []);
        })
        .catch((e) => {
          console.error("Error loading standards:", e);
          setStandards([]);
        })
        .finally(() => {
          setPlannerLoading(false);
        });
    }
  }, [
    config.state,
    config.grade_level,
    config.subject,
    activeTab,
  ]);

  // Auto-scroll log
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [status.log]);

  // Auto-expand Activity Monitor when error occurs
  useEffect(() => {
    if (status.error) {
      setShowActivityLog(true);
    }
  }, [status.error]);

  // Sync editedResults with status.results
  useEffect(() => {
    if (
      status.results.length > 0 &&
      editedResults.length !== status.results.length
    ) {
      setEditedResults(status.results.map((r) => ({ ...r, edited: false })));
    }
  }, [status.results]);

  // Show toast when new assignments are graded
  useEffect(() => {
    const currentCount = status.results.length;
    if (config.showToastNotifications && currentCount > lastResultCount.current && lastResultCount.current > 0) {
      const newResults = status.results.slice(lastResultCount.current);
      newResults.forEach((result) => {
        const grade = result.letter_grade || "N/A";
        const score = result.score !== undefined ? `${result.score}%` : "";
        addToast(
          `Graded: ${result.student_name} - ${grade} ${score}`,
          grade === "A" || grade === "B" ? "success" : grade === "C" ? "info" : "warning"
        );
      });
    }
    lastResultCount.current = currentCount;
  }, [status.results, config.showToastNotifications]);

  // Load files from assignments folder
  const loadAvailableFiles = async () => {
    if (!config.assignments_folder) return;
    setFilesLoading(true);
    try {
      const data = await api.listFiles(config.assignments_folder);
      if (data.files) {
        setAvailableFiles(data.files);
        // By default, select all ungraded files
        const ungraded = data.files.filter(f => !f.graded).map(f => f.name);
        setSelectedFiles(ungraded);
      }
    } catch (e) {
      console.error("Failed to load files:", e);
    }
    setFilesLoading(false);
  };

  // Load students from selected period
  const loadPeriodStudents = async (periodFilename) => {
    if (!periodFilename) {
      setPeriodStudents([]);
      return;
    }
    try {
      const data = await api.getPeriodStudents(periodFilename);
      if (data.students) {
        setPeriodStudents(data.students);
      }
    } catch (e) {
      console.error("Failed to load period students:", e);
      setPeriodStudents([]);
    }
  };

  // Check if a filename matches any student in the period
  const fileMatchesPeriodStudent = (filename, students) => {
    if (!students || students.length === 0) return true; // No filter
    const lowerFilename = filename.toLowerCase();
    return students.some(student => {
      const first = (student.first || "").toLowerCase().trim();
      const last = (student.last || "").toLowerCase().trim();
      const lastInitial = last.charAt(0);

      // Match patterns:
      // "First, Last" or "First, L" (common format)
      // "Last, First"
      // "First Last" or "First_Last"
      // Just first name + last initial
      return (
        // "First, Last" - e.g., "John, Smith"
        (first && last && lowerFilename.includes(`${first}, ${last}`)) ||
        // "First, L" - e.g., "John, S" (last initial only)
        (first && lastInitial && lowerFilename.includes(`${first}, ${lastInitial}`)) ||
        // "First L" - e.g., "John S" (no comma, last initial)
        (first && lastInitial && lowerFilename.match(new RegExp(`${first}\\s+${lastInitial}[^a-z]`, 'i'))) ||
        // "Last, First" - e.g., "Smith, John"
        (first && last && lowerFilename.includes(`${last}, ${first}`)) ||
        // "First Last" - e.g., "John Smith"
        (first && last && lowerFilename.includes(`${first} ${last}`)) ||
        // "First_Last" - e.g., "John_Smith"
        (first && last && lowerFilename.includes(`${first}_${last}`)) ||
        // Just first name at start of filename
        (first && lowerFilename.startsWith(`${first},`)) ||
        (first && lowerFilename.startsWith(`${first} `))
      );
    });
  };

  // Get filtered files based on period selection
  const getFilteredFiles = () => {
    if (!selectedPeriod || periodStudents.length === 0) {
      return availableFiles;
    }
    return availableFiles.filter(f => fileMatchesPeriodStudent(f.name, periodStudents));
  };

  // Grading functions
  const handleStartGrading = async () => {
    try {
      // Auto-save assignment config if it has a title and content
      const hasGradeConfig = gradeAssignment.title && (
        gradeAssignment.customMarkers.length > 0 ||
        gradeAssignment.gradingNotes ||
        (gradeAssignment.responseSections || []).length > 0 ||
        gradeImportedDoc.filename
      );

      if (hasGradeConfig) {
        try {
          const dataToSave = {
            ...gradeAssignment,
            importedDoc: gradeImportedDoc.filename ? gradeImportedDoc : null
          };
          await api.saveAssignmentConfig(dataToSave);
          // Refresh saved assignments list
          const list = await api.listAssignments();
          if (list.assignments) setSavedAssignments(list.assignments);
        } catch (saveError) {
          console.error("Failed to auto-save assignment config:", saveError);
        }
      }

      // Determine which files to grade
      let filesToGrade = selectedFiles.length > 0 ? selectedFiles : null;

      // If no files selected but period filter is active, load and filter files
      if (!filesToGrade && selectedPeriod && periodStudents.length > 0) {
        try {
          const filesData = await api.listFiles(config.assignments_folder);
          if (filesData.files) {
            const ungraded = filesData.files.filter(f => !f.graded);
            const filtered = ungraded.filter(f => fileMatchesPeriodStudent(f.name, periodStudents));
            if (filtered.length > 0) {
              filesToGrade = filtered.map(f => f.name);
            } else {
              alert("No ungraded files found for the selected period.");
              return;
            }
          }
        } catch (e) {
          console.error("Failed to load files for period filter:", e);
        }
      }

      await api.startGrading({
        ...config,
        grade_level: config.grade_level,
        subject: config.subject,
        teacher_name: config.teacher_name,
        school_name: config.school_name,
        assignmentConfig:
          gradeAssignment.customMarkers.length > 0 ||
          gradeAssignment.gradingNotes ||
          (gradeAssignment.responseSections || []).length > 0
            ? gradeAssignment
            : null,
        globalAINotes,
        // Pass selected files (null means grade all new files)
        selectedFiles: filesToGrade,
      });
      setStatus((prev) => ({
        ...prev,
        is_running: true,
        log: ["Starting..."],
      }));
      setShowActivityLog(true); // Auto-expand log when grading starts
    } catch (error) {
      console.error("Failed to start grading:", error);
    }
  };

  const handleStopGrading = async () => {
    try {
      await api.stopGrading();
      setAutoGrade(false);
    } catch (error) {
      console.error("Failed to stop grading:", error);
    }
  };

  const handleBrowse = async (type, field) => {
    try {
      const result = await api.browse(type);
      if (result.path) {
        setConfig((prev) => ({ ...prev, [field]: result.path }));
      }
    } catch (error) {
      console.error("Browse error:", error);
    }
  };

  const openResults = () => api.openFolder(config.output_folder);

  // Generate default email body for a result (matches exactly what backend sends)
  const getDefaultEmailBody = (index) => {
    const r = status.results[index];
    if (!r) return "";
    const firstName = r.student_name?.split(" ")[0] || "Student";
    const signature = [
      config.teacher_name || "Your Teacher",
      config.subject,
      config.school_name,
    ]
      .filter(Boolean)
      .join("\n");

    return `Hi ${firstName},

Here is your grade and feedback for ${r.assignment || "your assignment"}:

${"=".repeat(40)}
GRADE: ${r.score}/100 (${r.letter_grade})
${"=".repeat(40)}

FEEDBACK:
${r.feedback || "No feedback available."}

${"=".repeat(40)}

If you have any questions, please see me during class.

${signature}`;
  };

  // Builder functions
  const handleDocImport = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setImportedDoc({ text: "", html: "", filename: file.name, loading: true });
    try {
      const data = await api.parseDocument(file);
      if (data.error) {
        alert("Error parsing document: " + data.error);
        setImportedDoc({ text: "", html: "", filename: "", loading: false });
      } else {
        setImportedDoc({
          text: data.text || "",
          html: data.html || "",
          filename: file.name,
          loading: false,
        });
        setLoadedAssignmentName("");
        setDocEditorModal({
          show: true,
          editedHtml: data.html || "",
          viewMode: "formatted",
        });
        if (!assignment.title) {
          const title = file.name
            .replace(/\.(docx|pdf|doc)$/i, "")
            .replace(/_/g, " ");
          setAssignment({ ...assignment, title });
        }
      }
    } catch (err) {
      alert("Error: " + err.message);
      setImportedDoc({ text: "", html: "", filename: "", loading: false });
    }
  };

  const openDocEditor = () => {
    if (importedDoc.text || importedDoc.html) {
      setDocEditorModal({
        show: true,
        editedHtml: importedDoc.html,
        viewMode: "formatted",
      });
    }
  };

  const addSelectedAsMarker = () => {
    let text = "";
    try {
      if (docHtmlRef.current?.contentDocument) {
        const sel = docHtmlRef.current.contentDocument.getSelection();
        if (sel) text = sel.toString().trim();
      }
    } catch (e) {}
    if (!text) {
      const sel = window.getSelection();
      text = sel ? sel.toString().trim() : "";
    }
    if (text && text.length > 2 && text.length < 2000) {
      if (!(assignment.customMarkers || []).includes(text)) {
        setAssignment({
          ...assignment,
          customMarkers: [...(assignment.customMarkers || []), text],
        });
      }
    } else if (text.length <= 2) {
      alert("Please select more text (at least 3 characters)");
    } else if (text.length >= 2000) {
      alert(
        "Selection too long. Please select less text (under 2000 characters)",
      );
    }
  };

  const removeMarker = (marker) => {
    setAssignment({
      ...assignment,
      customMarkers: (assignment.customMarkers || []).filter(
        (m) => m !== marker,
      ),
    });
  };

  const addQuestion = () => {
    setAssignment({
      ...assignment,
      questions: [
        ...assignment.questions,
        {
          id: Date.now(),
          type: "short_answer",
          prompt: "",
          points: 10,
          marker: markerLibrary[assignment.subject]?.[0] || "Answer:",
        },
      ],
    });
  };

  const updateQuestion = (index, field, value) => {
    const updated = [...assignment.questions];
    updated[index] = { ...updated[index], [field]: value };
    setAssignment({ ...assignment, questions: updated });
  };

  const removeQuestion = (index) => {
    setAssignment({
      ...assignment,
      questions: assignment.questions.filter((_, i) => i !== index),
    });
  };

  const saveAssignmentConfig = async () => {
    if (!assignment.title) {
      alert("Please enter a title");
      return;
    }
    try {
      const dataToSave = { ...assignment, importedDoc };
      await api.saveAssignmentConfig(dataToSave);
      alert("Assignment saved!");
      setLoadedAssignmentName(assignment.title);
      const list = await api.listAssignments();
      if (list.assignments) setSavedAssignments(list.assignments);
    } catch (e) {
      alert("Error saving: " + e.message);
    }
  };

  const loadAssignment = async (name) => {
    try {
      const data = await api.loadAssignment(name);
      if (data.assignment) {
        setAssignment({
          title: data.assignment.title || "",
          subject: data.assignment.subject || "Social Studies",
          totalPoints: data.assignment.totalPoints || 100,
          instructions: data.assignment.instructions || "",
          questions: data.assignment.questions || [],
          customMarkers: data.assignment.customMarkers || [],
          gradingNotes: data.assignment.gradingNotes || "",
          responseSections: data.assignment.responseSections || [],
        });
        setLoadedAssignmentName(name);
        if (data.assignment.importedDoc) {
          setImportedDoc(data.assignment.importedDoc);
        } else {
          setImportedDoc({ text: "", html: "", filename: "", loading: false });
        }
      }
    } catch (e) {
      alert("Error loading: " + e.message);
    }
  };

  const deleteAssignment = async (name) => {
    if (!confirm(`Delete "${name}"?`)) return;
    try {
      await api.deleteAssignment(name);
      setSavedAssignments(savedAssignments.filter((a) => a !== name));
      if (loadedAssignmentName === name) {
        setAssignment({
          title: "",
          subject: "Social Studies",
          totalPoints: 100,
          instructions: "",
          questions: [],
          customMarkers: [],
          gradingNotes: "",
          responseSections: [],
        });
        setLoadedAssignmentName("");
      }
    } catch (e) {
      alert("Error: " + e.message);
    }
  };

  const exportAssignment = async (format) => {
    try {
      const data = await api.exportAssignment({ assignment, format });
      if (data.error) alert("Error: " + data.error);
      else alert("Assignment exported!");
    } catch (e) {
      alert("Error exporting: " + e.message);
    }
  };

  // Planner functions
  const toggleStandard = (code) => {
    setSelectedStandards((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code],
    );
  };

  const generateLessonPlan = async () => {
    if (selectedStandards.length === 0) {
      alert("Please select at least one standard.");
      return;
    }
    if (!unitConfig.title) {
      alert("Please enter a title.");
      return;
    }
    setPlannerLoading(true);
    try {
      const data = await api.generateLessonPlan({
        standards: selectedStandards,
        config: { state: 'FL', grade: config.grade_level, subject: config.subject, ...unitConfig },
      });
      if (data.error) alert("Error: " + data.error);
      else setLessonPlan(data.plan || data);
    } catch (e) {
      alert("Error generating plan: " + e.message);
    } finally {
      setPlannerLoading(false);
    }
  };

  const exportLessonPlanHandler = async () => {
    if (!lessonPlan) return;
    try {
      const data = await api.exportLessonPlan(lessonPlan);
      if (data.error) alert("Error exporting: " + data.error);
      else alert("Lesson plan exported to: " + data.path);
    } catch (e) {
      alert("Error exporting: " + e.message);
    }
  };

  // Results/Email functions
  const openReview = (index) => setReviewModal({ show: true, index });

  const updateGrade = (index, field, value) => {
    const updated = [...editedResults];
    updated[index] = { ...updated[index], [field]: value, edited: true };
    if (field === "score") {
      const score = parseInt(value) || 0;
      updated[index].letter_grade =
        score >= 90
          ? "A"
          : score >= 80
            ? "B"
            : score >= 70
              ? "C"
              : score >= 60
                ? "D"
                : "F";
    }
    setEditedResults(updated);
  };

  const sendEmails = async () => {
    setEmailPreview({ ...emailPreview, show: false });
    const results = editedResults.length > 0 ? editedResults : status.results;
    if (results.length === 0) return;
    setEmailStatus({
      sending: true,
      sent: 0,
      failed: 0,
      message: "Sending emails...",
    });
    try {
      const data = await api.sendEmails(results);
      setEmailStatus({
        sending: false,
        sent: data.sent || 0,
        failed: data.failed || 0,
        message: data.error
          ? `Error: ${data.error}`
          : `Sent ${data.sent} emails${data.failed > 0 ? `, ${data.failed} failed` : ""}`,
      });
    } catch (e) {
      setEmailStatus({
        sending: false,
        sent: 0,
        failed: 0,
        message: `Error: ${e.message}`,
      });
    }
  };

  const pct = status.total > 0 ? (status.progress / status.total) * 100 : 0;

  return (
    <div style={{ minHeight: "100vh", padding: "20px" }}>
      {/* Email Preview Modal */}
      {emailPreview.show && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "var(--modal-bg)",
            zIndex: 1000,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "20px",
          }}
        >
          <div
            style={{
              background: "var(--modal-content-bg)",
              borderRadius: "20px",
              border: "1px solid var(--glass-border)",
              width: "100%",
              maxWidth: "800px",
              maxHeight: "90vh",
              overflow: "hidden",
              display: "flex",
              flexDirection: "column",
            }}
          >
            <div
              style={{
                padding: "20px 25px",
                borderBottom: "1px solid var(--glass-border)",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <h2
                style={{
                  fontSize: "1.3rem",
                  fontWeight: 700,
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                }}
              >
                <Icon name="Mail" size={24} />
                Email Preview ({emailPreview.emails.length} students)
              </h2>
              <button
                onClick={() => setEmailPreview({ show: false, emails: [] })}
                style={{
                  background: "none",
                  border: "none",
                  color: "var(--text-secondary)",
                  cursor: "pointer",
                }}
              >
                <Icon name="X" size={24} />
              </button>
            </div>
            <div style={{ flex: 1, overflowY: "auto", padding: "20px" }}>
              {emailPreview.emails.map((email, i) => (
                <div
                  key={i}
                  style={{
                    background: "var(--glass-bg)",
                    borderRadius: "12px",
                    border: "1px solid var(--glass-border)",
                    marginBottom: "15px",
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      padding: "15px 20px",
                      borderBottom: "1px solid var(--table-row-border)",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 600, marginBottom: "4px" }}>
                        {email.name}
                      </div>
                      <div
                        style={{
                          fontSize: "0.85rem",
                          color: "var(--text-muted)",
                        }}
                      >
                        {email.to}
                      </div>
                    </div>
                    <span
                      style={{
                        background: "rgba(99,102,241,0.2)",
                        color: "var(--accent-light)",
                        padding: "4px 12px",
                        borderRadius: "20px",
                        fontSize: "0.8rem",
                      }}
                    >
                      {email.assignments} assignment
                      {email.assignments > 1 ? "s" : ""}
                    </span>
                  </div>
                  <div style={{ padding: "15px 20px" }}>
                    <div
                      style={{
                        fontSize: "0.9rem",
                        color: "var(--accent-light)",
                        marginBottom: "10px",
                      }}
                    >
                      <strong>Subject:</strong> {email.subject}
                    </div>
                    <div
                      style={{
                        fontSize: "0.85rem",
                        color: "var(--text-secondary)",
                        whiteSpace: "pre-wrap",
                        maxHeight: "150px",
                        overflowY: "auto",
                        background: "var(--input-bg)",
                        padding: "12px",
                        borderRadius: "8px",
                        fontFamily: "monospace",
                      }}
                    >
                      {email.body}
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <div
              style={{
                padding: "20px 25px",
                borderTop: "1px solid var(--glass-border)",
                display: "flex",
                gap: "15px",
                justifyContent: "flex-end",
              }}
            >
              <button
                onClick={() => setEmailPreview({ show: false, emails: [] })}
                className="btn btn-secondary"
              >
                Cancel
              </button>
              <button onClick={sendEmails} className="btn btn-primary">
                <Icon name="Send" size={18} />
                Send All Emails
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Review Modal - Full Screen */}
      {reviewModal.show && reviewModal.index >= 0 && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "var(--modal-content-bg)",
            zIndex: 1000,
            display: "flex",
            flexDirection: "column",
          }}
        >
          <div
            style={{
              padding: "20px 30px",
              borderBottom: "1px solid var(--glass-border)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <h2 style={{ fontSize: "1.4rem", fontWeight: 700 }}>
              Review:{" "}
              {
                (
                  editedResults[reviewModal.index] ||
                  status.results[reviewModal.index]
                )?.student_name
              }
            </h2>
            <button
              onClick={() => setReviewModal({ show: false, index: -1 })}
              style={{
                background: "var(--glass-bg)",
                border: "1px solid var(--glass-border)",
                borderRadius: "8px",
                padding: "8px",
                color: "var(--text-secondary)",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                transition: "all 0.2s",
              }}
              onMouseEnter={(e) => e.currentTarget.style.background = "var(--glass-hover)"}
              onMouseLeave={(e) => e.currentTarget.style.background = "var(--glass-bg)"}
            >
              <Icon name="X" size={20} />
            </button>
          </div>
          <div style={{ flex: 1, overflow: "hidden", padding: "25px 30px" }}>
            {(() => {
              const r =
                editedResults[reviewModal.index] ||
                status.results[reviewModal.index];
              if (!r) return null;
              return (
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr 1fr",
                    gap: "30px",
                    height: "100%",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      height: "100%",
                      background: "var(--glass-bg)",
                      borderRadius: "16px",
                      border: "1px solid var(--glass-border)",
                      overflow: "hidden",
                    }}
                  >
                    {/* Header with tabs */}
                    <div
                      style={{
                        padding: "16px 20px",
                        borderBottom: "1px solid var(--glass-border)",
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                      }}
                    >
                      <div style={{ display: "flex", gap: "8px" }}>
                        <button
                          onClick={() => setReviewModalTab("detected")}
                          style={{
                            padding: "8px 16px",
                            borderRadius: "8px",
                            border: "none",
                            background: reviewModalTab === "detected"
                              ? "linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))"
                              : "var(--glass-hover)",
                            color: reviewModalTab === "detected" ? "#fff" : "var(--text-secondary)",
                            fontWeight: 600,
                            fontSize: "0.85rem",
                            cursor: "pointer",
                            transition: "all 0.2s",
                            display: "flex",
                            alignItems: "center",
                            gap: "6px",
                          }}
                        >
                          <Icon name="CheckCircle" size={14} />
                          AI Detected
                        </button>
                        <button
                          onClick={() => setReviewModalTab("raw")}
                          style={{
                            padding: "8px 16px",
                            borderRadius: "8px",
                            border: "none",
                            background: reviewModalTab === "raw"
                              ? "linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))"
                              : "var(--glass-hover)",
                            color: reviewModalTab === "raw" ? "#fff" : "var(--text-secondary)",
                            fontWeight: 600,
                            fontSize: "0.85rem",
                            cursor: "pointer",
                            transition: "all 0.2s",
                            display: "flex",
                            alignItems: "center",
                            gap: "6px",
                          }}
                        >
                          <Icon name="FileText" size={14} />
                          Raw Text
                        </button>
                      </div>
                      <button
                        onClick={async () => {
                          try {
                            await api.openFolder(r.filepath);
                          } catch (e) {
                            alert("Could not open file: " + e.message);
                          }
                        }}
                        style={{
                          padding: "8px 12px",
                          borderRadius: "8px",
                          border: "1px solid var(--glass-border)",
                          background: "var(--glass-bg)",
                          color: "var(--text-secondary)",
                          fontSize: "0.8rem",
                          fontWeight: 500,
                          cursor: "pointer",
                          display: "flex",
                          alignItems: "center",
                          gap: "6px",
                          transition: "all 0.2s",
                        }}
                        onMouseEnter={(e) => e.currentTarget.style.background = "var(--glass-hover)"}
                        onMouseLeave={(e) => e.currentTarget.style.background = "var(--glass-bg)"}
                      >
                        <Icon name="ExternalLink" size={14} />
                        Open Original
                      </button>
                    </div>

                    {/* Tab Content */}
                    <div style={{ flex: 1, overflow: "auto", padding: "20px" }}>
                      {reviewModalTab === "detected" ? (
                        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                          {/* AI Detected Responses */}
                          {r.student_responses && r.student_responses.length > 0 ? (
                            <div>
                              <div
                                style={{
                                  fontWeight: 600,
                                  marginBottom: "12px",
                                  color: "#4ade80",
                                  display: "flex",
                                  alignItems: "center",
                                  gap: "8px",
                                  fontSize: "0.9rem",
                                }}
                              >
                                <Icon name="CheckCircle" size={16} />
                                Detected Responses ({r.student_responses.length})
                              </div>
                              <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                                {r.student_responses.map((resp, i) => (
                                  <div
                                    key={i}
                                    style={{
                                      padding: "14px 16px",
                                      background: "rgba(74,222,128,0.08)",
                                      borderRadius: "10px",
                                      fontSize: "0.9rem",
                                      color: "var(--text-primary)",
                                      border: "1px solid rgba(74,222,128,0.2)",
                                      lineHeight: 1.5,
                                    }}
                                  >
                                    {resp}
                                  </div>
                                ))}
                              </div>
                            </div>
                          ) : (
                            <div
                              style={{
                                padding: "30px",
                                textAlign: "center",
                                color: "var(--text-muted)",
                                fontSize: "0.9rem",
                              }}
                            >
                              No student responses detected
                            </div>
                          )}

                          {/* Unanswered Questions */}
                          {r.unanswered_questions && r.unanswered_questions.length > 0 && (
                            <div style={{ marginTop: "8px" }}>
                              <div
                                style={{
                                  fontWeight: 600,
                                  marginBottom: "12px",
                                  color: "#fbbf24",
                                  display: "flex",
                                  alignItems: "center",
                                  gap: "8px",
                                  fontSize: "0.9rem",
                                }}
                              >
                                <Icon name="AlertCircle" size={16} />
                                Unanswered ({r.unanswered_questions.length})
                              </div>
                              <div
                                style={{
                                  padding: "14px 16px",
                                  background: "rgba(251,191,36,0.08)",
                                  borderRadius: "10px",
                                  fontSize: "0.9rem",
                                  color: "var(--text-secondary)",
                                  border: "1px solid rgba(251,191,36,0.2)",
                                  lineHeight: 1.6,
                                }}
                              >
                                {r.unanswered_questions.join(" • ")}
                              </div>
                            </div>
                          )}
                        </div>
                      ) : (
                        <div
                          style={{
                            height: "100%",
                            background: "var(--input-bg)",
                            padding: "20px",
                            borderRadius: "10px",
                            whiteSpace: "pre-wrap",
                            fontSize: "0.85rem",
                            lineHeight: 1.6,
                            color: "var(--text-secondary)",
                            fontFamily: "monospace",
                            overflowY: "auto",
                          }}
                        >
                          {r.full_content || r.student_content || "[No content - click Open Original to view]"}
                        </div>
                      )}
                    </div>
                  </div>
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      height: "100%",
                      background: "var(--glass-bg)",
                      borderRadius: "16px",
                      border: "1px solid var(--glass-border)",
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        padding: "16px 20px",
                        borderBottom: "1px solid var(--glass-border)",
                        display: "flex",
                        alignItems: "center",
                        gap: "10px",
                      }}
                    >
                      <Icon name="Award" size={18} style={{ color: "var(--accent-primary)" }} />
                      <h3 style={{ fontSize: "1rem", fontWeight: 600 }}>Grade & Feedback</h3>
                    </div>
                    <div style={{ flex: 1, padding: "20px", display: "flex", flexDirection: "column", gap: "20px", overflow: "auto" }}>
                      <div>
                        <label className="label">Score</label>
                        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                          <input
                            type="number"
                            className="input"
                            value={r.score}
                            onChange={(e) =>
                              updateGrade(
                                reviewModal.index,
                                "score",
                                e.target.value,
                              )
                            }
                            style={{ width: "100px" }}
                          />
                          <span
                            style={{
                              padding: "6px 14px",
                              borderRadius: "8px",
                              fontWeight: 700,
                              fontSize: "0.9rem",
                              background:
                                r.score >= 90
                                  ? "rgba(74,222,128,0.15)"
                                  : r.score >= 80
                                    ? "rgba(96,165,250,0.15)"
                                    : r.score >= 70
                                      ? "rgba(251,191,36,0.15)"
                                      : "rgba(248,113,113,0.15)",
                              color:
                                r.score >= 90
                                  ? "#4ade80"
                                  : r.score >= 80
                                    ? "#60a5fa"
                                    : r.score >= 70
                                      ? "#fbbf24"
                                      : "#f87171",
                            }}
                          >
                            {r.letter_grade}
                          </span>
                        </div>
                      </div>
                      <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
                        <label className="label">Feedback</label>
                        <textarea
                          className="input"
                          value={r.feedback}
                          onChange={(e) =>
                            updateGrade(
                              reviewModal.index,
                              "feedback",
                              e.target.value,
                            )
                          }
                          style={{ flex: 1, minHeight: "200px", resize: "none" }}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              );
            })()}
          </div>
          <div
            style={{
              padding: "20px 30px",
              borderTop: "1px solid var(--glass-border)",
              display: "flex",
              gap: "12px",
              justifyContent: "flex-end",
            }}
          >
            <button
              onClick={() => setReviewModal({ show: false, index: -1 })}
              className="btn btn-primary"
              style={{ padding: "10px 24px" }}
            >
              Done
            </button>
          </div>
        </div>
      )}

      {/* Document Editor Modal */}
      {docEditorModal.show && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "var(--modal-bg)",
            zIndex: 1000,
            display: "flex",
            flexDirection: "column",
          }}
        >
          <div
            style={{
              padding: "15px 25px",
              borderBottom: "1px solid var(--glass-border)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              background: "var(--modal-content-bg)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "15px" }}>
              <h2 style={{ fontSize: "1.2rem", fontWeight: 700 }}>
                <Icon name="FileEdit" size={20} />{" "}
                {importedDoc.filename || "Document Editor"}
              </h2>
              <span
                style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}
              >
                {(assignment.customMarkers || []).length} markers selected
              </span>
            </div>
            <div style={{ display: "flex", gap: "10px" }}>
              <button onClick={addSelectedAsMarker} className="btn btn-primary">
                <Icon name="Target" size={16} />
                Mark Selection
              </button>
              <button
                onClick={() =>
                  setDocEditorModal({ ...docEditorModal, show: false })
                }
                className="btn btn-secondary"
              >
                Done
              </button>
            </div>
          </div>
          <div
            style={{
              flex: 1,
              display: "grid",
              gridTemplateColumns: "1fr 300px",
              overflow: "hidden",
            }}
          >
            <div style={{ overflow: "auto", padding: "20px" }}>
              <iframe
                ref={docHtmlRef}
                srcDoc={`<!DOCTYPE html><html><head><style>body{font-family:Georgia,serif;padding:40px;background:#fff;color:#000;line-height:1.6}::selection{background:#6366f1;color:#fff}</style></head><body>${docEditorModal.editedHtml}</body></html>`}
                style={{
                  width: "100%",
                  height: "100%",
                  border: "none",
                  borderRadius: "8px",
                  minHeight: "600px",
                }}
              />
            </div>
            <div
              style={{
                borderLeft: "1px solid var(--glass-border)",
                padding: "20px",
                overflowY: "auto",
                background: "var(--sidebar-bg)",
              }}
            >
              <h3 style={{ fontSize: "1rem", marginBottom: "15px" }}>
                Marked Sections ({(assignment.customMarkers || []).length})
              </h3>
              <p
                style={{
                  fontSize: "0.85rem",
                  color: "var(--text-muted)",
                  marginBottom: "15px",
                }}
              >
                Select text in the document and click "Mark Selection"
              </p>
              {(assignment.customMarkers || []).length === 0 ? (
                <p
                  style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}
                >
                  No markers yet
                </p>
              ) : (
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "8px",
                  }}
                >
                  {(assignment.customMarkers || []).map((marker, i) => (
                    <div
                      key={i}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "8px",
                        padding: "8px 12px",
                        background: "rgba(251,191,36,0.2)",
                        borderRadius: "6px",
                        border: "1px solid rgba(251,191,36,0.3)",
                      }}
                    >
                      <Icon
                        name="Target"
                        size={12}
                        style={{ color: "var(--warning)", flexShrink: 0 }}
                      />
                      <span
                        style={{
                          fontSize: "0.8rem",
                          flex: 1,
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                        }}
                      >
                        {marker}
                      </span>
                      <button
                        onClick={() => removeMarker(marker)}
                        style={{
                          background: "none",
                          border: "none",
                          color: "var(--text-muted)",
                          cursor: "pointer",
                          padding: "0",
                        }}
                      >
                        <Icon name="X" size={12} />
                      </button>
                    </div>
                  ))}
                </div>
              )}

              {/* Response Sections - Highlighter */}
              <div style={{
                marginTop: "25px",
                padding: "15px",
                background: "linear-gradient(135deg, rgba(74,222,128,0.08), rgba(250,204,21,0.08))",
                borderRadius: "12px",
                border: "1px solid rgba(74,222,128,0.25)",
                boxShadow: "0 0 15px rgba(74,222,128,0.1)",
              }}>
                <h3 style={{
                  fontSize: "0.95rem",
                  marginBottom: "10px",
                  display: "flex",
                  alignItems: "center",
                  gap: "10px"
                }}>
                  <span style={{
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    width: "26px",
                    height: "26px",
                    borderRadius: "6px",
                    background: "linear-gradient(135deg, #4ade80, #facc15)",
                    boxShadow: "0 0 10px rgba(74,222,128,0.4)",
                  }}>
                    <Icon name="Highlighter" size={14} style={{ color: "#000" }} />
                  </span>
                  Highlighter ({(assignment.responseSections || []).length})
                </h3>
                <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "12px" }}>
                  Mark sections where student answers are located
                </p>

                {/* Add new section */}
                <div style={{ marginBottom: "12px" }}>
                  <input
                    type="text"
                    placeholder="Start header (e.g., Part 1:)"
                    id="builder-section-start"
                    style={{
                      width: "100%",
                      padding: "8px 10px",
                      marginBottom: "6px",
                      borderRadius: "6px",
                      border: "1px solid var(--glass-border)",
                      background: "var(--input-bg)",
                      color: "var(--text-primary)",
                      fontSize: "0.8rem",
                    }}
                  />
                  <input
                    type="text"
                    placeholder="End header (optional)"
                    id="builder-section-end"
                    style={{
                      width: "100%",
                      padding: "8px 10px",
                      marginBottom: "8px",
                      borderRadius: "6px",
                      border: "1px solid var(--glass-border)",
                      background: "var(--input-bg)",
                      color: "var(--text-primary)",
                      fontSize: "0.8rem",
                    }}
                  />
                  <button
                    onClick={() => {
                      const startEl = document.getElementById("builder-section-start");
                      const endEl = document.getElementById("builder-section-end");
                      const start = startEl?.value?.trim();
                      const end = endEl?.value?.trim();
                      if (start) {
                        setAssignment(prev => ({
                          ...prev,
                          responseSections: [...(prev.responseSections || []), { start, end: end || null }]
                        }));
                        if (startEl) startEl.value = "";
                        if (endEl) endEl.value = "";
                      }
                    }}
                    style={{
                      width: "100%",
                      padding: "8px",
                      borderRadius: "6px",
                      border: "none",
                      background: "linear-gradient(135deg, #4ade80, #22c55e)",
                      color: "#000",
                      cursor: "pointer",
                      fontWeight: 600,
                      fontSize: "0.8rem",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: "6px",
                      boxShadow: "0 3px 10px rgba(74,222,128,0.3)",
                    }}
                  >
                    <Icon name="Plus" size={14} /> Add Section
                  </button>
                </div>

                {/* Section list */}
                {(assignment.responseSections || []).length > 0 && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                    {(assignment.responseSections || []).map((section, i) => (
                      <div
                        key={i}
                        style={{
                          padding: "10px 12px",
                          background: "linear-gradient(90deg, rgba(250,204,21,0.2), rgba(74,222,128,0.12))",
                          borderRadius: "6px",
                          border: "1px solid rgba(250,204,21,0.35)",
                          boxShadow: "0 0 8px rgba(250,204,21,0.15)",
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                          <div style={{ flex: 1 }}>
                            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                              <Icon name="ArrowRight" size={12} style={{ color: "#facc15" }} />
                              <span style={{ fontSize: "0.8rem", fontWeight: 600, color: "#facc15" }}>"{section.start}"</span>
                            </div>
                            {section.end ? (
                              <div style={{ display: "flex", alignItems: "center", gap: "6px", marginTop: "4px", marginLeft: "18px" }}>
                                <Icon name="ArrowRight" size={12} style={{ color: "#4ade80" }} />
                                <span style={{ fontSize: "0.8rem", fontWeight: 600, color: "#4ade80" }}>"{section.end}"</span>
                              </div>
                            ) : (
                              <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginTop: "3px", marginLeft: "18px", fontStyle: "italic" }}>
                                → until end
                              </div>
                            )}
                          </div>
                          <button
                            onClick={() => setAssignment(prev => ({
                              ...prev,
                              responseSections: (prev.responseSections || []).filter((_, idx) => idx !== i)
                            }))}
                            style={{
                              background: "none",
                              border: "none",
                              color: "var(--text-muted)",
                              cursor: "pointer",
                              padding: "0",
                            }}
                          >
                            <Icon name="X" size={12} />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* App Layout with Sidebar */}
      <div style={{ display: "flex", minHeight: "100vh" }}>
        {/* Sidebar */}
        <div
          style={{
            width: sidebarCollapsed ? "70px" : "260px",
            background: theme === "dark"
              ? "#000000"
              : "linear-gradient(180deg, #ffffff 0%, #f8fafc 50%, #f1f5f9 100%)",
            borderRight: `1px solid ${theme === "dark" ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.08)"}`,
            padding: "0",
            display: "flex",
            flexDirection: "column",
            position: "fixed",
            top: 0,
            left: 0,
            bottom: 0,
            zIndex: 100,
            transition: "width 0.3s ease",
          }}
        >
          {/* Collapse Toggle - Right Edge */}
          <button
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            style={{
              position: "absolute",
              right: "-12px",
              top: "50%",
              transform: "translateY(-50%)",
              width: "24px",
              height: "24px",
              borderRadius: "50%",
              border: `1px solid ${theme === "dark" ? "rgba(255,255,255,0.15)" : "rgba(0,0,0,0.1)"}`,
              background: theme === "dark" ? "#1f1f2a" : "#ffffff",
              color: "var(--text-secondary)",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              transition: "all 0.2s",
              zIndex: 101,
              boxShadow: "0 2px 8px rgba(0,0,0,0.15)",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--accent-primary)";
              e.currentTarget.style.color = "#fff";
              e.currentTarget.style.borderColor = "var(--accent-primary)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = theme === "dark" ? "#1f1f2a" : "#ffffff";
              e.currentTarget.style.color = "var(--text-secondary)";
              e.currentTarget.style.borderColor = theme === "dark" ? "rgba(255,255,255,0.15)" : "rgba(0,0,0,0.1)";
            }}
          >
            <Icon name={sidebarCollapsed ? "ChevronRight" : "ChevronLeft"} size={14} />
          </button>

          {/* Logo */}
          <div
            style={{
              overflow: "hidden",
              marginBottom: "-130px",
              display: sidebarCollapsed ? "none" : "block",
            }}
          >
            <img
              src="/logo.svg"
              alt="Graider"
              style={{
                width: "180%",
                display: "block",
                marginLeft: "-40%",
                marginTop: "-110px",
              }}
            />
          </div>

          {/* Collapsed Logo */}
          {sidebarCollapsed && (
            <div
              style={{
                padding: "20px 0",
                display: "flex",
                justifyContent: "center",
              }}
            >
              <img
                src="/Justbrain.svg"
                alt="Graider"
                style={{
                  width: "40px",
                  height: "40px",
                }}
              />
            </div>
          )}

          {/* Navigation */}
          <nav style={{ flex: 1, padding: sidebarCollapsed ? "10px 8px 0 8px" : "0 10px", marginTop: sidebarCollapsed ? "0" : "0" }}>
            {TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                title={sidebarCollapsed ? tab.label : ""}
                style={{
                  width: "100%",
                  padding: sidebarCollapsed ? "14px 0" : "14px 16px",
                  marginBottom: "6px",
                  borderRadius: "10px",
                  border: "none",
                  background:
                    activeTab === tab.id
                      ? "linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))"
                      : "transparent",
                  color:
                    activeTab === tab.id ? "#fff" : "var(--text-secondary)",
                  fontSize: "0.95rem",
                  fontWeight: 600,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: sidebarCollapsed ? "center" : "flex-start",
                  gap: "12px",
                  transition: "all 0.2s",
                  textAlign: "left",
                }}
                onMouseEnter={(e) => {
                  if (activeTab !== tab.id)
                    e.target.style.background = "var(--glass-hover)";
                }}
                onMouseLeave={(e) => {
                  if (activeTab !== tab.id)
                    e.target.style.background = "transparent";
                }}
              >
                <Icon name={tab.icon} size={20} />
                {!sidebarCollapsed && tab.label}
              </button>
            ))}
          </nav>

          {/* Footer */}
          {!sidebarCollapsed && (
            <div
              style={{
                padding: "15px 20px",
                borderTop: `1px solid ${theme === "dark" ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.08)"}`,
              }}
            >
              <div
                style={{
                  fontSize: "0.75rem",
                  color: "var(--text-muted)",
                  textAlign: "center",
                }}
              >
                AI-Powered Teaching Assistant
              </div>
            </div>
          )}
        </div>

        {/* Main Content */}
        <div
          style={{
            flex: 1,
            marginLeft: sidebarCollapsed ? "70px" : "260px",
            padding: "0",
            maxWidth: sidebarCollapsed ? "calc(100vw - 70px)" : "calc(100vw - 260px)",
            display: "flex",
            flexDirection: "column",
            transition: "all 0.3s ease",
          }}
        >
          {/* Top Header Bar */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              padding: "15px 30px",
              borderBottom: "1px solid var(--glass-border)",
              background: "var(--card-bg)",
              position: "sticky",
              top: 0,
              zIndex: 50,
            }}
          >
            {/* Left: Auto-Grade & Start/Stop */}
            <div style={{ display: "flex", alignItems: "center", gap: "15px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <Icon name="Zap" size={18} style={{ color: autoGrade ? '#4ade80' : 'var(--text-muted)' }} />
                <span style={{ fontSize: "0.9rem", fontWeight: 500 }}>Auto-Grade</span>
                <button
                  onClick={() => setAutoGrade(!autoGrade)}
                  style={{
                    padding: "4px 12px",
                    borderRadius: "6px",
                    border: "none",
                    background: autoGrade ? "#4ade80" : "var(--glass-bg)",
                    color: autoGrade ? "#000" : "var(--text-primary)",
                    fontWeight: 600,
                    fontSize: "0.8rem",
                    cursor: "pointer",
                  }}
                >
                  {autoGrade ? "ON" : "OFF"}
                </button>
                {autoGrade && watchStatus.lastCheck && (
                  <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                    Last: {watchStatus.lastCheck}
                  </span>
                )}
              </div>
              <div style={{ width: "1px", height: "24px", background: "var(--glass-border)" }} />
              {!status.is_running ? (
                <button onClick={handleStartGrading} className="btn btn-primary" style={{ padding: "8px 20px" }}>
                  <Icon name="Play" size={16} />
                  Start Grading
                </button>
              ) : (
                <button onClick={handleStopGrading} className="btn btn-danger" style={{ padding: "8px 20px" }}>
                  <Icon name="Square" size={16} />
                  Stop ({status.progress}/{status.total})
                </button>
              )}
            </div>

            {/* Right: Theme Toggle */}
            <button
              onClick={toggleTheme}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                padding: "10px",
                borderRadius: "8px",
                border: "1px solid var(--glass-border)",
                background: "var(--glass-bg)",
                color: "var(--text-primary)",
                cursor: "pointer",
              }}
              title={theme === "dark" ? "Switch to Light Mode" : "Switch to Dark Mode"}
            >
              <Icon name={theme === "dark" ? "Sun" : "Moon"} size={18} />
            </button>
          </div>

          <div style={{ padding: "30px", flex: 1, overflowY: "auto" }}>
          <div style={{ maxWidth: "1400px", margin: "0 auto" }}>
            {/* Grade Tab */}
            {activeTab === "grade" && (
              <div className="fade-in">
                {/* Error Alert Banner */}
                {status.error && (
                  <div
                    className="glass-card fade-in"
                    style={{
                      padding: "15px 20px",
                      marginBottom: "20px",
                      background: "rgba(248,113,113,0.1)",
                      border: "1px solid rgba(248,113,113,0.4)",
                      display: "flex",
                      alignItems: "center",
                      gap: "12px",
                    }}
                  >
                    <Icon name="AlertTriangle" size={24} style={{ color: "#f87171" }} />
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 600, color: "#f87171", marginBottom: "4px" }}>
                        Grading Stopped - Error Detected
                      </div>
                      <div style={{ fontSize: "0.9rem", color: "var(--text-secondary)" }}>
                        {status.error}
                      </div>
                    </div>
                    <button
                      onClick={() => setStatus((prev) => ({ ...prev, error: null }))}
                      style={{
                        background: "rgba(248,113,113,0.2)",
                        border: "none",
                        borderRadius: "8px",
                        padding: "8px 12px",
                        color: "#f87171",
                        cursor: "pointer",
                        fontSize: "0.85rem",
                        fontWeight: 500,
                      }}
                    >
                      Dismiss
                    </button>
                  </div>
                )}

                {/* Activity Monitor - Horizontal Collapsible */}
                <div
                  className="glass-card"
                  style={{
                    padding: "15px 20px",
                    marginBottom: "20px",
                    background: status.error
                      ? "rgba(248,113,113,0.05)"
                      : status.is_running
                      ? "rgba(74,222,128,0.05)"
                      : "var(--glass-bg)",
                    border: `1px solid ${
                      status.error
                        ? "rgba(248,113,113,0.3)"
                        : status.is_running
                        ? "rgba(74,222,128,0.3)"
                        : "var(--glass-border)"
                    }`,
                  }}
                >
                  <button
                    onClick={() => setShowActivityLog(!showActivityLog)}
                    style={{
                      width: "100%",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      background: "none",
                      border: "none",
                      cursor: "pointer",
                      color: "var(--text-primary)",
                      padding: 0,
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                      <Icon
                        name={status.error ? "AlertCircle" : "Terminal"}
                        size={18}
                        style={{
                          color: status.error
                            ? "#f87171"
                            : status.is_running
                            ? "#4ade80"
                            : "var(--text-secondary)",
                        }}
                      />
                      <span style={{ fontWeight: 600, fontSize: "0.95rem" }}>Activity Monitor</span>
                      {status.error && (
                        <span style={{
                          fontSize: "0.75rem",
                          padding: "3px 10px",
                          borderRadius: "12px",
                          background: "rgba(248,113,113,0.2)",
                          color: "#f87171",
                          fontWeight: 500,
                        }}>
                          Error
                        </span>
                      )}
                      {status.is_running && !status.error && (
                        <span style={{
                          fontSize: "0.75rem",
                          padding: "3px 10px",
                          borderRadius: "12px",
                          background: "rgba(74,222,128,0.2)",
                          color: "#4ade80",
                          fontWeight: 500,
                        }}>
                          Running...
                        </span>
                      )}
                      {status.log.length > 0 && (
                        <span style={{
                          fontSize: "0.75rem",
                          padding: "3px 8px",
                          borderRadius: "8px",
                          background: "var(--input-bg)",
                          color: "var(--text-muted)",
                        }}>
                          {status.log.length} entries
                        </span>
                      )}
                    </div>
                    <Icon
                      name={showActivityLog ? "ChevronUp" : "ChevronDown"}
                      size={18}
                      style={{ color: "var(--text-muted)" }}
                    />
                  </button>

                  {showActivityLog && (
                    <div
                      ref={logRef}
                      style={{
                        marginTop: "15px",
                        maxHeight: "200px",
                        overflowY: "auto",
                        background: "var(--input-bg)",
                        borderRadius: "10px",
                        padding: "15px",
                        fontFamily: "Monaco, Consolas, monospace",
                        fontSize: "0.8rem",
                        lineHeight: "1.6",
                      }}
                    >
                      {status.log.length === 0 ? (
                        <p style={{ color: "var(--text-muted)", margin: 0, textAlign: "center" }}>
                          Ready to grade. Activity will appear here...
                        </p>
                      ) : (
                        status.log.slice(-30).map((line, i) => (
                          <div key={i} style={{ marginBottom: "4px", color: "var(--text-secondary)" }}>
                            {line}
                          </div>
                        ))
                      )}
                    </div>
                  )}
                </div>

                {/* Full width layout */}
                <div className="glass-card" style={{ padding: "25px" }}>
                  <h2
                    style={{
                      fontSize: "1.3rem",
                      fontWeight: 700,
                      marginBottom: "20px",
                      display: "flex",
                      alignItems: "center",
                      gap: "10px",
                    }}
                  >
                    <Icon name="Play" size={24} />
                    Start Grading
                  </h2>

                  {/* Period Filter - Show when periods exist */}
                  {periods.length > 0 && (
                    <div
                      style={{
                        padding: "15px",
                        background: "linear-gradient(135deg, rgba(99, 102, 241, 0.1), rgba(168, 85, 247, 0.05))",
                        borderRadius: "12px",
                        border: "1px solid rgba(99, 102, 241, 0.2)",
                        marginBottom: "20px",
                      }}
                    >
                      <label className="label" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <Icon name="Users" size={16} style={{ color: "var(--accent-primary)" }} />
                        Filter by Class Period
                      </label>
                      <select
                        className="input"
                        value={selectedPeriod}
                        onChange={async (e) => {
                          const periodFilename = e.target.value;
                          setSelectedPeriod(periodFilename);
                          await loadPeriodStudents(periodFilename);
                        }}
                        style={{ cursor: "pointer" }}
                      >
                        <option value="">All Periods (No Filter)</option>
                        {periods.map((p) => (
                          <option key={p.filename} value={p.filename}>
                            {p.period_name} ({p.row_count} students)
                          </option>
                        ))}
                      </select>
                      {selectedPeriod && periodStudents.length > 0 && (
                        <p style={{ fontSize: "0.75rem", color: "var(--accent-primary)", marginTop: "8px", fontWeight: 500 }}>
                          ✓ Filtering to {periodStudents.length} students in {periods.find(p => p.filename === selectedPeriod)?.period_name}
                        </p>
                      )}
                    </div>
                  )}

                    {/* Assignment Editing - Same as Builder */}
                    <div
                      className="glass-card"
                      style={{
                        padding: "25px",
                        marginBottom: "20px",
                        background: "rgba(251,191,36,0.05)",
                        border: "1px solid rgba(251,191,36,0.2)",
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          marginBottom: "20px",
                        }}
                      >
                        <h3
                          style={{
                            fontSize: "1.1rem",
                            fontWeight: 700,
                            display: "flex",
                            alignItems: "center",
                            gap: "10px",
                          }}
                        >
                          <Icon
                            name="FileEdit"
                            size={20}
                            style={{ color: "#fbbf24" }}
                          />
                          Assignment Config (Optional)
                        </h3>
                        <div style={{ display: "flex", gap: "8px" }}>
                          {gradeAssignment.title && (
                            <button
                              onClick={async () => {
                                try {
                                  const dataToSave = {
                                    ...gradeAssignment,
                                    importedDoc: gradeImportedDoc.filename ? gradeImportedDoc : null
                                  };
                                  await api.saveAssignmentConfig(dataToSave);
                                  const list = await api.listAssignments();
                                  if (list.assignments) setSavedAssignments(list.assignments);
                                  alert("Assignment saved!");
                                } catch (e) {
                                  alert("Error saving: " + e.message);
                                }
                              }}
                              className="btn btn-primary"
                              style={{ padding: "6px 12px", fontSize: "0.85rem" }}
                            >
                              <Icon name="Save" size={14} />
                              Save
                            </button>
                          )}
                          {(gradeAssignment.customMarkers.length > 0 ||
                            gradeAssignment.gradingNotes ||
                            (gradeAssignment.responseSections || []).length > 0 ||
                            gradeImportedDoc.filename) && (
                            <button
                              onClick={() => {
                                setGradeAssignment({
                                  title: "",
                                  customMarkers: [],
                                  gradingNotes: "",
                                  responseSections: [],
                                });
                                setGradeImportedDoc({
                                  text: "",
                                  html: "",
                                  filename: "",
                                });
                              }}
                              className="btn btn-secondary"
                              style={{ padding: "6px 12px", fontSize: "0.85rem" }}
                            >
                              <Icon name="X" size={14} />
                              Clear
                            </button>
                          )}
                        </div>
                      </div>

                      {/* Load Saved Assignment */}
                      {savedAssignments.length > 0 && (
                        <div style={{ marginBottom: "20px" }}>
                          <label className="label">Load Saved Assignment</label>
                          <select
                            className="input"
                            value=""
                            onChange={async (e) => {
                              const name = e.target.value;
                              if (!name) return;
                              try {
                                const data = await api.loadAssignment(name);
                                if (data.assignment) {
                                  setGradeAssignment({
                                    title: data.assignment.title || "",
                                    customMarkers: data.assignment.customMarkers || [],
                                    gradingNotes: data.assignment.gradingNotes || "",
                                    responseSections: data.assignment.responseSections || [],
                                  });
                                  if (data.assignment.importedDoc) {
                                    setGradeImportedDoc(data.assignment.importedDoc);
                                  }
                                }
                              } catch (err) {
                                console.error("Load error:", err);
                              }
                            }}
                            style={{ cursor: "pointer" }}
                          >
                            <option value="">Select a saved assignment...</option>
                            {savedAssignments.map((name) => (
                              <option key={name} value={name}>{name}</option>
                            ))}
                          </select>
                        </div>
                      )}

                      {/* Assignment Title */}
                      <div style={{ marginBottom: "20px" }}>
                        <label className="label">Assignment Title</label>
                        <input
                          type="text"
                          className="input"
                          value={gradeAssignment.title}
                          onChange={(e) =>
                            setGradeAssignment({
                              ...gradeAssignment,
                              title: e.target.value,
                            })
                          }
                          placeholder="e.g., Louisiana Purchase Quiz"
                        />
                      </div>

                      {/* Import Document - Redesigned */}
                      <div style={{ marginBottom: "20px" }}>
                        <input
                          type="file"
                          id="gradeFileInput"
                          onChange={async (e) => {
                            const file = e.target.files?.[0];
                            if (!file) return;
                            try {
                              const data = await api.parseDocument(file);
                              if (data.text) {
                                setGradeImportedDoc({
                                  text: data.text,
                                  html: data.html || "",
                                  filename: file.name,
                                });
                                setGradeAssignment({
                                  ...gradeAssignment,
                                  title: file.name.replace(/\.[^/.]+$/, ""),
                                });
                              }
                            } catch (err) {
                              console.error("Import error:", err);
                            }
                            e.target.value = "";
                          }}
                          accept=".docx,.pdf,.doc,.txt"
                          style={{ display: "none" }}
                        />

                        {!gradeImportedDoc.text ? (
                          /* Empty state - Upload prompt */
                          <div
                            onClick={() => document.getElementById("gradeFileInput")?.click()}
                            style={{
                              padding: "30px",
                              borderRadius: "16px",
                              border: "2px dashed var(--glass-border)",
                              background: "var(--glass-bg)",
                              cursor: "pointer",
                              transition: "all 0.2s",
                              textAlign: "center",
                            }}
                            onMouseOver={(e) => {
                              e.currentTarget.style.borderColor = "#f59e0b";
                              e.currentTarget.style.background = "rgba(251,191,36,0.05)";
                            }}
                            onMouseOut={(e) => {
                              e.currentTarget.style.borderColor = "var(--glass-border)";
                              e.currentTarget.style.background = "var(--glass-bg)";
                            }}
                          >
                            <div style={{
                              width: "60px",
                              height: "60px",
                              borderRadius: "16px",
                              background: "linear-gradient(135deg, rgba(251,191,36,0.2), rgba(217,119,6,0.2))",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              margin: "0 auto 15px",
                            }}>
                              <Icon name="FileUp" size={28} style={{ color: "#f59e0b" }} />
                            </div>
                            <h4 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "8px" }}>
                              Import Document
                            </h4>
                            <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "15px" }}>
                              Drag & drop or click to upload a Word doc or PDF
                            </p>
                            <div style={{
                              display: "inline-flex",
                              alignItems: "center",
                              gap: "8px",
                              padding: "10px 20px",
                              borderRadius: "10px",
                              background: "linear-gradient(135deg, #f59e0b, #d97706)",
                              color: "#000",
                              fontWeight: 600,
                              fontSize: "0.9rem",
                            }}>
                              <Icon name="Upload" size={18} />
                              Choose File
                            </div>
                            <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "12px" }}>
                              Supports .docx, .pdf, .doc, .txt
                            </p>
                          </div>
                        ) : (
                          /* Document loaded state */
                          <div style={{
                            padding: "20px",
                            borderRadius: "16px",
                            background: "linear-gradient(135deg, rgba(251,191,36,0.08), rgba(217,119,6,0.05))",
                            border: "1px solid rgba(251,191,36,0.25)",
                          }}>
                            <div style={{ display: "flex", alignItems: "flex-start", gap: "15px" }}>
                              {/* Document icon */}
                              <div style={{
                                width: "50px",
                                height: "50px",
                                borderRadius: "12px",
                                background: "linear-gradient(135deg, #f59e0b, #d97706)",
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                                flexShrink: 0,
                              }}>
                                <Icon name="FileText" size={24} style={{ color: "#fff" }} />
                              </div>

                              {/* Document info */}
                              <div style={{ flex: 1, minWidth: 0 }}>
                                <h4 style={{
                                  fontSize: "0.95rem",
                                  fontWeight: 600,
                                  marginBottom: "4px",
                                  overflow: "hidden",
                                  textOverflow: "ellipsis",
                                  whiteSpace: "nowrap",
                                }}>
                                  {gradeImportedDoc.filename}
                                </h4>
                                <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", display: "flex", alignItems: "center", gap: "6px" }}>
                                  <Icon name="CheckCircle" size={14} style={{ color: "#4ade80" }} />
                                  Document loaded successfully
                                </p>
                              </div>

                              {/* Action buttons */}
                              <div style={{ display: "flex", gap: "8px", flexShrink: 0 }}>
                                <button
                                  onClick={() => {
                                    setImportedDoc({ ...gradeImportedDoc, loading: false });
                                    setDocEditorModal({
                                      show: true,
                                      editedHtml: gradeImportedDoc.html || gradeImportedDoc.text,
                                      viewMode: "formatted",
                                    });
                                  }}
                                  style={{
                                    padding: "10px 16px",
                                    borderRadius: "10px",
                                    border: "1px solid var(--glass-border)",
                                    background: "var(--glass-bg)",
                                    color: "var(--text-primary)",
                                    cursor: "pointer",
                                    display: "flex",
                                    alignItems: "center",
                                    gap: "8px",
                                    fontWeight: 500,
                                    fontSize: "0.85rem",
                                    transition: "all 0.2s",
                                  }}
                                >
                                  <Icon name="Highlighter" size={16} style={{ color: "#f59e0b" }} />
                                  Edit & Mark
                                </button>
                                <button
                                  onClick={() => document.getElementById("gradeFileInput")?.click()}
                                  style={{
                                    padding: "10px",
                                    borderRadius: "10px",
                                    border: "1px solid var(--glass-border)",
                                    background: "var(--glass-bg)",
                                    color: "var(--text-secondary)",
                                    cursor: "pointer",
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                    transition: "all 0.2s",
                                  }}
                                  title="Replace document"
                                >
                                  <Icon name="RefreshCw" size={16} />
                                </button>
                                <button
                                  onClick={() => setGradeImportedDoc({ text: '', html: '', filename: '' })}
                                  style={{
                                    padding: "10px",
                                    borderRadius: "10px",
                                    border: "1px solid rgba(239,68,68,0.3)",
                                    background: "rgba(239,68,68,0.1)",
                                    color: "#ef4444",
                                    cursor: "pointer",
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                    transition: "all 0.2s",
                                  }}
                                  title="Remove document"
                                >
                                  <Icon name="Trash2" size={16} />
                                </button>
                              </div>
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Markers Section */}
                      <div style={{
                        padding: "20px",
                        borderRadius: "16px",
                        background: "var(--glass-bg)",
                        border: "1px solid var(--glass-border)",
                        marginBottom: "20px",
                      }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "15px" }}>
                          <div style={{
                            width: "36px",
                            height: "36px",
                            borderRadius: "10px",
                            background: "rgba(99,102,241,0.15)",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                          }}>
                            <Icon name="Target" size={18} style={{ color: "#6366f1" }} />
                          </div>
                          <div>
                            <h4 style={{ fontSize: "0.95rem", fontWeight: 600, marginBottom: "2px" }}>Answer Markers</h4>
                            <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", margin: 0 }}>
                              Phrases that indicate where student answers begin
                            </p>
                          </div>
                        </div>

                        {/* Manual Marker Input */}
                        <div style={{ display: "flex", gap: "10px", marginBottom: "12px" }}>
                          <input
                            type="text"
                            id="gradeMarkerInput"
                            placeholder="Add a marker phrase (e.g., 'Answer:', 'Response:')"
                            className="input"
                            style={{ flex: 1 }}
                            onKeyDown={(e) => {
                              if (e.key === "Enter" && e.target.value.trim()) {
                                const newMarker = e.target.value.trim();
                                if (!gradeAssignment.customMarkers.includes(newMarker)) {
                                  setGradeAssignment({
                                    ...gradeAssignment,
                                    customMarkers: [...gradeAssignment.customMarkers, newMarker],
                                  });
                                }
                                e.target.value = "";
                              }
                            }}
                          />
                          <button
                            onClick={() => {
                              const input = document.getElementById("gradeMarkerInput");
                              if (input?.value.trim()) {
                                const newMarker = input.value.trim();
                                if (!gradeAssignment.customMarkers.includes(newMarker)) {
                                  setGradeAssignment({
                                    ...gradeAssignment,
                                    customMarkers: [...gradeAssignment.customMarkers, newMarker],
                                  });
                                }
                                input.value = "";
                              }
                            }}
                            style={{
                              padding: "10px 16px",
                              borderRadius: "10px",
                              border: "none",
                              background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
                              color: "#fff",
                              cursor: "pointer",
                              display: "flex",
                              alignItems: "center",
                              gap: "6px",
                              fontWeight: 500,
                              fontSize: "0.85rem",
                            }}
                          >
                            <Icon name="Plus" size={16} />
                            Add
                          </button>
                        </div>

                        {/* Custom Markers */}
                        {gradeAssignment.customMarkers.length > 0 && (
                          <div
                            style={{
                              marginTop: "15px",
                              display: "flex",
                              flexWrap: "wrap",
                              gap: "8px",
                            }}
                          >
                            {gradeAssignment.customMarkers.map((marker, i) => (
                              <div
                                key={i}
                                style={{
                                  display: "flex",
                                  alignItems: "center",
                                  gap: "6px",
                                  padding: "6px 12px",
                                  background: "rgba(251,191,36,0.2)",
                                  borderRadius: "6px",
                                  border: "1px solid rgba(251,191,36,0.3)",
                                }}
                              >
                                <Icon
                                  name="Target"
                                  size={12}
                                  style={{ color: "#fbbf24" }}
                                />
                                <span
                                  style={{
                                    fontSize: "0.8rem",
                                    maxWidth: "200px",
                                    overflow: "hidden",
                                    textOverflow: "ellipsis",
                                    whiteSpace: "nowrap",
                                  }}
                                >
                                  {marker}
                                </span>
                                <button
                                  onClick={() =>
                                    setGradeAssignment({
                                      ...gradeAssignment,
                                      customMarkers:
                                        gradeAssignment.customMarkers.filter(
                                          (m) => m !== marker,
                                        ),
                                    })
                                  }
                                  style={{
                                    background: "none",
                                    border: "none",
                                    color: "var(--text-muted)",
                                    cursor: "pointer",
                                    padding: "0",
                                  }}
                                >
                                  <Icon name="X" size={12} />
                                </button>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>

                      {/* Marker Library */}
                      <div
                        style={{
                          marginBottom: "20px",
                          padding: "15px 20px",
                          background: "rgba(99,102,241,0.1)",
                          borderRadius: "12px",
                          border: "1px solid rgba(99,102,241,0.2)",
                        }}
                      >
                        <label
                          style={{
                            display: "block",
                            fontSize: "0.9rem",
                            fontWeight: 600,
                            marginBottom: "10px",
                          }}
                        >
                          <Icon
                            name="Bookmark"
                            size={16}
                            style={{ marginRight: "8px" }}
                          />
                          Suggested Markers for{" "}
                          {config.subject || "Social Studies"}
                        </label>
                        <div
                          style={{
                            display: "flex",
                            flexWrap: "wrap",
                            gap: "8px",
                          }}
                        >
                          {(
                            markerLibrary[config.subject] ||
                            markerLibrary["Social Studies"] ||
                            []
                          ).map((marker, i) => (
                            <span
                              key={i}
                              style={{
                                padding: "6px 12px",
                                background: "var(--btn-secondary-bg)",
                                borderRadius: "6px",
                                fontSize: "0.85rem",
                                cursor: "pointer",
                              }}
                              onClick={() => {
                                if (
                                  !gradeAssignment.customMarkers.includes(
                                    marker,
                                  )
                                ) {
                                  setGradeAssignment({
                                    ...gradeAssignment,
                                    customMarkers: [
                                      ...gradeAssignment.customMarkers,
                                      marker,
                                    ],
                                  });
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
                      <div>
                        <label className="label">
                          Assignment-Specific Grading Notes
                        </label>
                        <textarea
                          className="input"
                          value={gradeAssignment.gradingNotes}
                          onChange={(e) =>
                            setGradeAssignment({
                              ...gradeAssignment,
                              gradingNotes: e.target.value,
                            })
                          }
                          placeholder="Special instructions for grading this assignment..."
                          style={{ minHeight: "100px" }}
                        />
                      </div>

                    </div>


                    {/* Progress */}
                    {status.is_running && (
                      <div style={{ marginTop: "20px" }}>
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            marginBottom: "8px",
                            fontSize: "0.9rem",
                          }}
                        >
                          <span>Progress</span>
                          <span>
                            {status.progress}/{status.total}
                          </span>
                        </div>
                        <div
                          style={{
                            height: "8px",
                            background: "var(--btn-secondary-bg)",
                            borderRadius: "4px",
                            overflow: "hidden",
                          }}
                        >
                          <div
                            style={{
                              height: "100%",
                              width: `${pct}%`,
                              background:
                                "linear-gradient(90deg, #6366f1, #8b5cf6)",
                              transition: "width 0.3s",
                            }}
                          />
                        </div>
                        {status.current_file && (
                          <p
                            style={{
                              marginTop: "8px",
                              fontSize: "0.85rem",
                              color: "var(--text-secondary)",
                            }}
                          >
                            {status.current_file}
                          </p>
                        )}
                      </div>
                    )}

                    {status.complete && (
                      <button
                        onClick={openResults}
                        className="btn btn-secondary"
                        style={{
                          width: "100%",
                          marginTop: "15px",
                          justifyContent: "center",
                        }}
                      >
                        <Icon name="FolderOpen" size={18} />
                        Open Results Folder
                      </button>
                    )}

                  </div>
                </div>
            )}

            {/* Results Tab */}
            {activeTab === "results" && (
              <div
                className="fade-in"
                style={{
                  display: "grid",
                  gridTemplateColumns:
                    viewingEmailIndex !== null ? "1fr 1fr" : "1fr",
                  gap: "20px",
                }}
              >
                {/* Results Table */}
                <div className="glass-card" style={{ padding: "25px" }}>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      marginBottom: "20px",
                    }}
                  >
                    <h2
                      style={{
                        fontSize: "1.3rem",
                        fontWeight: 700,
                        display: "flex",
                        alignItems: "center",
                        gap: "10px",
                      }}
                    >
                      <Icon name="FileText" size={24} />
                      Grading Results ({status.results.length})
                    </h2>
                    {status.results.length > 0 && (
                      <div style={{ display: "flex", gap: "10px" }}>
                        <button
                          onClick={openResults}
                          className="btn btn-secondary"
                        >
                          <Icon name="FolderOpen" size={18} />
                          Open Folder
                        </button>
                        <button
                          onClick={async () => {
                            if (
                              confirm(
                                "Clear all grading results? This cannot be undone.",
                              )
                            ) {
                              try {
                                await api.clearResults();
                                setStatus((prev) => ({
                                  ...prev,
                                  results: [],
                                  log: [],
                                  complete: false,
                                }));
                                setEditedResults([]);
                                setEmailApprovals({});
                                setEditedEmails({});
                              } catch (e) {
                                alert("Error clearing results: " + e.message);
                              }
                            }
                          }}
                          className="btn btn-secondary"
                          style={{ background: "rgba(239,68,68,0.2)" }}
                        >
                          <Icon name="Trash2" size={18} />
                          Clear
                        </button>
                      </div>
                    )}
                  </div>

                  {/* Authenticity Summary Alert */}
                  {status.results.length > 0 &&
                    (() => {
                      const authStats = status.results.reduce((acc, r) => {
                        const auth = getAuthenticityStatus(r);
                        if (auth.ai.flag === "likely") acc.aiLikely++;
                        else if (auth.ai.flag === "possible") acc.aiPossible++;
                        if (auth.plag.flag === "likely") acc.plagLikely++;
                        else if (auth.plag.flag === "possible") acc.plagPossible++;
                        return acc;
                      }, { aiLikely: 0, aiPossible: 0, plagLikely: 0, plagPossible: 0 });

                      const hasConcerns = authStats.aiLikely + authStats.aiPossible + authStats.plagLikely + authStats.plagPossible > 0;

                      return hasConcerns ? (
                        <div
                          style={{
                            marginBottom: "20px",
                            padding: "15px 20px",
                            borderRadius: "12px",
                            background:
                              "linear-gradient(135deg, rgba(248,113,113,0.1), rgba(251,191,36,0.1))",
                            border: "1px solid rgba(248,113,113,0.3)",
                            display: "flex",
                            alignItems: "center",
                            gap: "15px",
                          }}
                        >
                          <Icon
                            name="Shield"
                            size={24}
                            style={{ color: "#f87171" }}
                          />
                          <div style={{ flex: 1 }}>
                            <div style={{ fontWeight: 700, marginBottom: "8px" }}>
                              Authenticity Summary
                            </div>
                            <div
                              style={{
                                display: "flex",
                                gap: "20px",
                                fontSize: "0.9rem",
                              }}
                            >
                              {/* AI Detection Stats */}
                              <div>
                                <div style={{ color: "var(--text-muted)", fontSize: "0.8rem", marginBottom: "4px" }}>
                                  <Icon name="Bot" size={12} style={{ marginRight: "4px", verticalAlign: "middle" }} />
                                  AI Detection
                                </div>
                                <div style={{ display: "flex", gap: "10px" }}>
                                  {authStats.aiLikely > 0 && (
                                    <span style={{ color: "#f87171" }}>
                                      {authStats.aiLikely} likely
                                    </span>
                                  )}
                                  {authStats.aiPossible > 0 && (
                                    <span style={{ color: "#fbbf24" }}>
                                      {authStats.aiPossible} possible
                                    </span>
                                  )}
                                  {authStats.aiLikely === 0 && authStats.aiPossible === 0 && (
                                    <span style={{ color: "#4ade80" }}>All clear</span>
                                  )}
                                </div>
                              </div>
                              {/* Plagiarism Stats */}
                              <div>
                                <div style={{ color: "var(--text-muted)", fontSize: "0.8rem", marginBottom: "4px" }}>
                                  <Icon name="Copy" size={12} style={{ marginRight: "4px", verticalAlign: "middle" }} />
                                  Plagiarism
                                </div>
                                <div style={{ display: "flex", gap: "10px" }}>
                                  {authStats.plagLikely > 0 && (
                                    <span style={{ color: "#f87171" }}>
                                      {authStats.plagLikely} likely
                                    </span>
                                  )}
                                  {authStats.plagPossible > 0 && (
                                    <span style={{ color: "#fbbf24" }}>
                                      {authStats.plagPossible} possible
                                    </span>
                                  )}
                                  {authStats.plagLikely === 0 && authStats.plagPossible === 0 && (
                                    <span style={{ color: "#4ade80" }}>All clear</span>
                                  )}
                                </div>
                              </div>
                            </div>
                          </div>
                          <div
                            style={{
                              fontSize: "0.85rem",
                              color: "var(--text-secondary)",
                            }}
                          >
                            Hover for details
                          </div>
                        </div>
                      ) : null;
                    })()}

                  {/* Auto-Approve Toggle */}
                  {status.results.length > 0 && (
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "15px",
                        marginBottom: "20px",
                        padding: "12px 15px",
                        background: "var(--input-bg)",
                        borderRadius: "10px",
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "10px",
                        }}
                      >
                        <button
                          onClick={() =>
                            setAutoApproveEmails(!autoApproveEmails)
                          }
                          style={{
                            width: "44px",
                            height: "24px",
                            borderRadius: "12px",
                            border: "none",
                            background: autoApproveEmails
                              ? "#6366f1"
                              : "var(--btn-secondary-border)",
                            cursor: "pointer",
                            position: "relative",
                            transition: "background 0.2s",
                          }}
                        >
                          <div
                            style={{
                              width: "18px",
                              height: "18px",
                              borderRadius: "50%",
                              background: "#fff",
                              position: "absolute",
                              top: "3px",
                              left: autoApproveEmails ? "23px" : "3px",
                              transition: "left 0.2s",
                            }}
                          />
                        </button>
                        <span style={{ fontWeight: 600 }}>
                          Auto-Approve Emails
                        </span>
                      </div>
                      <span
                        style={{
                          fontSize: "0.85rem",
                          color: "var(--text-secondary)",
                        }}
                      >
                        {autoApproveEmails
                          ? "Emails will be sent automatically"
                          : "Review each email before sending"}
                      </span>
                      {!autoApproveEmails && (
                        <div
                          style={{
                            marginLeft: "auto",
                            display: "flex",
                            gap: "10px",
                          }}
                        >
                          <button
                            onClick={() => {
                              const approvals = {};
                              status.results.forEach((_, i) => {
                                approvals[i] = "approved";
                              });
                              setEmailApprovals(approvals);
                            }}
                            className="btn btn-secondary"
                            style={{ fontSize: "0.85rem", padding: "6px 12px" }}
                          >
                            <Icon name="CheckCircle" size={14} />
                            Approve All
                          </button>
                        </div>
                      )}
                    </div>
                  )}

                  {emailStatus.message && (
                    <div
                      style={{
                        marginBottom: "15px",
                        padding: "12px 15px",
                        background: emailStatus.message.includes("Error")
                          ? "rgba(248,113,113,0.1)"
                          : "rgba(74,222,128,0.1)",
                        borderRadius: "8px",
                        border: emailStatus.message.includes("Error")
                          ? "1px solid rgba(248,113,113,0.3)"
                          : "1px solid rgba(74,222,128,0.3)",
                      }}
                    >
                      {emailStatus.message}
                    </div>
                  )}

                  {status.results.length === 0 ? (
                    <p
                      style={{
                        color: "var(--text-secondary)",
                        textAlign: "center",
                        padding: "40px",
                      }}
                    >
                      No results yet. Grade some assignments first.
                    </p>
                  ) : (
                    <>
                      {/* Search Input */}
                      <div style={{ marginBottom: "15px" }}>
                        <div style={{ position: "relative" }}>
                          <Icon
                            name="Search"
                            size={18}
                            style={{
                              position: "absolute",
                              left: "12px",
                              top: "50%",
                              transform: "translateY(-50%)",
                              color: "var(--text-muted)",
                            }}
                          />
                          <input
                            type="text"
                            placeholder="Search by student or assignment name..."
                            value={resultsSearch}
                            onChange={(e) => setResultsSearch(e.target.value)}
                            style={{
                              width: "100%",
                              padding: "10px 12px 10px 40px",
                              borderRadius: "8px",
                              border: "1px solid var(--glass-border)",
                              background: "var(--input-bg)",
                              color: "var(--text-primary)",
                              fontSize: "0.9rem",
                            }}
                          />
                          {resultsSearch && (
                            <button
                              onClick={() => setResultsSearch("")}
                              style={{
                                position: "absolute",
                                right: "12px",
                                top: "50%",
                                transform: "translateY(-50%)",
                                background: "none",
                                border: "none",
                                color: "var(--text-muted)",
                                cursor: "pointer",
                                padding: "4px",
                              }}
                            >
                              <Icon name="X" size={16} />
                            </button>
                          )}
                        </div>
                      </div>
                      <table>
                        <thead>
                          <tr>
                            <th>Student</th>
                            <th>Assignment</th>
                            <th>Time</th>
                            <th>Score</th>
                            <th>Grade</th>
                            <th>Authenticity</th>
                            <th>Email</th>
                            <th>Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(editedResults.length > 0
                            ? editedResults
                            : status.results
                          )
                            .filter((r) => {
                              if (!resultsSearch.trim()) return true;
                              const search = resultsSearch.toLowerCase();
                              return (
                                (r.student_name || "")
                                  .toLowerCase()
                                  .includes(search) ||
                                (r.assignment || "")
                                  .toLowerCase()
                                  .includes(search)
                              );
                            })
                            .map((r, i) => {
                              // Find the original index for actions that need it
                              const originalIndex = status.results.findIndex(
                                (orig) => orig.filename === r.filename,
                              );
                              return (
                                <tr
                                  key={r.filename || i}
                                  style={{
                                    background:
                                      viewingEmailIndex === originalIndex
                                        ? "rgba(99,102,241,0.2)"
                                        : r.edited
                                          ? "rgba(251,191,36,0.1)"
                                          : "transparent",
                                    cursor: "pointer",
                                  }}
                                  onClick={() =>
                                    setViewingEmailIndex(
                                      viewingEmailIndex === originalIndex
                                        ? null
                                        : originalIndex,
                                    )
                                  }
                                >
                                  <td>{r.student_name}</td>
                                  <td
                                    style={{
                                      maxWidth: "150px",
                                      overflow: "hidden",
                                      textOverflow: "ellipsis",
                                      whiteSpace: "nowrap",
                                    }}
                                  >
                                    {r.assignment}
                                  </td>
                                  <td
                                    style={{
                                      fontSize: "0.8rem",
                                      color: "var(--text-secondary)",
                                      whiteSpace: "nowrap",
                                    }}
                                  >
                                    {r.graded_at || '-'}
                                  </td>
                                  <td>{r.score}</td>
                                  <td>
                                    <span
                                      style={{
                                        padding: "4px 12px",
                                        borderRadius: "20px",
                                        fontWeight: 700,
                                        background:
                                          r.score >= 90
                                            ? "rgba(74,222,128,0.2)"
                                            : r.score >= 80
                                              ? "rgba(96,165,250,0.2)"
                                              : r.score >= 70
                                                ? "rgba(251,191,36,0.2)"
                                                : "rgba(248,113,113,0.2)",
                                        color:
                                          r.score >= 90
                                            ? "#4ade80"
                                            : r.score >= 80
                                              ? "#60a5fa"
                                              : r.score >= 70
                                                ? "#fbbf24"
                                                : "#f87171",
                                      }}
                                    >
                                      {r.letter_grade}
                                    </span>
                                  </td>
                                  <td>
                                    {(() => {
                                      const auth = getAuthenticityStatus(r);
                                      const aiColor = getAIFlagColor(auth.ai.flag);
                                      const plagColor = getPlagFlagColor(auth.plag.flag);
                                      return (
                                        <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                                          {/* AI Detection */}
                                          <span
                                            title={auth.ai.reason || `AI: ${auth.ai.flag}${auth.ai.confidence ? ` (${auth.ai.confidence}%)` : ""}`}
                                            style={{
                                              display: "inline-flex",
                                              alignItems: "center",
                                              gap: "4px",
                                              padding: "3px 8px",
                                              borderRadius: "12px",
                                              fontWeight: 500,
                                              background: aiColor.bg,
                                              color: aiColor.text,
                                              fontSize: "0.75rem",
                                              cursor: auth.ai.reason ? "help" : "default",
                                            }}
                                          >
                                            <Icon
                                              name={auth.ai.flag === "likely" ? "Bot" : auth.ai.flag === "possible" ? "Bot" : "CheckCircle"}
                                              size={12}
                                            />
                                            AI: {auth.ai.flag === "none" ? "Clear" : auth.ai.flag}
                                            {auth.ai.confidence > 0 && ` ${auth.ai.confidence}%`}
                                          </span>
                                          {/* Plagiarism Detection */}
                                          <span
                                            title={auth.plag.reason || `Plagiarism: ${auth.plag.flag}`}
                                            style={{
                                              display: "inline-flex",
                                              alignItems: "center",
                                              gap: "4px",
                                              padding: "3px 8px",
                                              borderRadius: "12px",
                                              fontWeight: 500,
                                              background: plagColor.bg,
                                              color: plagColor.text,
                                              fontSize: "0.75rem",
                                              cursor: auth.plag.reason ? "help" : "default",
                                            }}
                                          >
                                            <Icon
                                              name={auth.plag.flag === "likely" ? "Copy" : auth.plag.flag === "possible" ? "Copy" : "CheckCircle"}
                                              size={12}
                                            />
                                            Copy: {auth.plag.flag === "none" ? "Clear" : auth.plag.flag}
                                          </span>
                                        </div>
                                      );
                                    })()}
                                  </td>
                                  <td>
                                    {autoApproveEmails ? (
                                      <span
                                        style={{
                                          color: "#4ade80",
                                          fontSize: "0.85rem",
                                        }}
                                      >
                                        Auto
                                      </span>
                                    ) : (
                                      <span
                                        style={{
                                          padding: "3px 8px",
                                          borderRadius: "4px",
                                          fontSize: "0.8rem",
                                          fontWeight: 600,
                                          background:
                                            emailApprovals[originalIndex] ===
                                            "approved"
                                              ? "rgba(74,222,128,0.2)"
                                              : emailApprovals[
                                                    originalIndex
                                                  ] === "rejected"
                                                ? "rgba(248,113,113,0.2)"
                                                : "var(--glass-border)",
                                          color:
                                            emailApprovals[originalIndex] ===
                                            "approved"
                                              ? "#4ade80"
                                              : emailApprovals[
                                                    originalIndex
                                                  ] === "rejected"
                                                ? "#f87171"
                                                : "var(--text-secondary)",
                                        }}
                                      >
                                        {emailApprovals[originalIndex] ===
                                        "approved"
                                          ? "Approved"
                                          : emailApprovals[originalIndex] ===
                                              "rejected"
                                            ? "Rejected"
                                            : "Pending"}
                                      </span>
                                    )}
                                  </td>
                                  <td style={{ display: "flex", gap: "4px" }}>
                                    <button
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        openReview(originalIndex);
                                      }}
                                      style={{
                                        background: "none",
                                        border: "none",
                                        color: "#a5b4fc",
                                        cursor: "pointer",
                                        padding: "4px",
                                      }}
                                      title="Edit"
                                    >
                                      <Icon name="Edit" size={16} />
                                    </button>
                                    <button
                                      onClick={async (e) => {
                                        e.stopPropagation();
                                        if (
                                          confirm(
                                            `Delete result for "${r.student_name}"?`,
                                          )
                                        ) {
                                          try {
                                            await api.deleteResult(r.filename);
                                            setStatus((prev) => ({
                                              ...prev,
                                              results: prev.results.filter(
                                                (result) =>
                                                  result.filename !==
                                                  r.filename,
                                              ),
                                            }));
                                            setEditedResults((prev) =>
                                              prev.filter(
                                                (result) =>
                                                  result.filename !==
                                                  r.filename,
                                              ),
                                            );
                                            // Clean up email approvals
                                            const newApprovals = {};
                                            Object.keys(emailApprovals).forEach(
                                              (key) => {
                                                const idx = parseInt(key);
                                                if (idx < originalIndex)
                                                  newApprovals[idx] =
                                                    emailApprovals[key];
                                                else if (idx > originalIndex)
                                                  newApprovals[idx - 1] =
                                                    emailApprovals[key];
                                              },
                                            );
                                            setEmailApprovals(newApprovals);
                                          } catch (err) {
                                            alert(
                                              "Error deleting result: " +
                                                err.message,
                                            );
                                          }
                                        }
                                      }}
                                      style={{
                                        background: "none",
                                        border: "none",
                                        color: "#f87171",
                                        cursor: "pointer",
                                        padding: "4px",
                                      }}
                                      title="Delete"
                                    >
                                      <Icon name="Trash2" size={16} />
                                    </button>
                                  </td>
                                </tr>
                              );
                            })}
                        </tbody>
                      </table>

                      {/* Send Approved Emails Button */}
                      {Object.values(emailApprovals).filter(
                        (v) => v === "approved",
                      ).length > 0 &&
                        !autoApproveEmails && (
                          <div
                            style={{
                              marginTop: "20px",
                              display: "flex",
                              justifyContent: "flex-end",
                            }}
                          >
                            <button
                              onClick={async () => {
                                // Build approved results with custom email content
                                const approvedResults = status.results
                                  .map((r, i) => {
                                    if (emailApprovals[i] !== "approved")
                                      return null;
                                    const edited = editedEmails[i];
                                    return {
                                      ...r,
                                      custom_email_subject:
                                        edited?.subject ||
                                        `Grade Report: ${r.assignment}`,
                                      custom_email_body:
                                        edited?.body || getDefaultEmailBody(i),
                                    };
                                  })
                                  .filter(Boolean);
                                if (approvedResults.length === 0) return;
                                setEmailStatus({
                                  sending: true,
                                  sent: 0,
                                  failed: 0,
                                  message: "Sending emails...",
                                });
                                try {
                                  const result =
                                    await api.sendEmails(approvedResults);
                                  setEmailStatus({
                                    sending: false,
                                    sent: result.sent || approvedResults.length,
                                    failed: result.failed || 0,
                                    message: `Sent ${result.sent || approvedResults.length} emails successfully!`,
                                  });
                                } catch (e) {
                                  setEmailStatus({
                                    sending: false,
                                    sent: 0,
                                    failed: approvedResults.length,
                                    message:
                                      "Error sending emails: " + e.message,
                                  });
                                }
                              }}
                              className="btn btn-primary"
                              disabled={emailStatus.sending}
                            >
                              <Icon name="Send" size={18} />
                              Send{" "}
                              {
                                Object.values(emailApprovals).filter(
                                  (v) => v === "approved",
                                ).length
                              }{" "}
                              Approved Emails
                            </button>
                          </div>
                        )}
                    </>
                  )}
                </div>
              </div>
            )}

            {/* Email Preview Modal */}
            {viewingEmailIndex !== null &&
              status.results[viewingEmailIndex] && (
                <div
                  style={{
                    position: "fixed",
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    background: "var(--modal-bg)",
                    zIndex: 1000,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    padding: "20px",
                  }}
                >
                  <div
                    style={{
                      background: "var(--modal-content-bg)",
                      borderRadius: "20px",
                      border: "1px solid var(--glass-border)",
                      width: "100%",
                      maxWidth: "800px",
                      maxHeight: "90vh",
                      overflow: "hidden",
                      display: "flex",
                      flexDirection: "column",
                    }}
                  >
                    {/* Modal Header */}
                    <div
                      style={{
                        padding: "20px 25px",
                        borderBottom: "1px solid var(--glass-border)",
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                      }}
                    >
                      <h3
                        style={{
                          fontSize: "1.2rem",
                          fontWeight: 700,
                          display: "flex",
                          alignItems: "center",
                          gap: "10px",
                          margin: 0,
                        }}
                      >
                        <Icon name="Mail" size={24} />
                        Email Preview -{" "}
                        {status.results[viewingEmailIndex].student_name}
                      </h3>
                      <button
                        onClick={() => setViewingEmailIndex(null)}
                        style={{
                          background: "none",
                          border: "none",
                          color: "var(--text-secondary)",
                          cursor: "pointer",
                          padding: "5px",
                        }}
                      >
                        <Icon name="X" size={24} />
                      </button>
                    </div>

                    {/* Modal Body */}
                    <div
                      style={{ padding: "25px", overflowY: "auto", flex: 1 }}
                    >
                      {/* Authenticity Check Alert */}
                      {(() => {
                        const auth = getAuthenticityStatus(status.results[viewingEmailIndex]);
                        const hasAIConcern = auth.ai.flag === "likely" || auth.ai.flag === "possible";
                        const hasPlagConcern = auth.plag.flag === "likely" || auth.plag.flag === "possible";

                        if (!hasAIConcern && !hasPlagConcern) return null;

                        return (
                          <div
                            style={{
                              marginBottom: "20px",
                              padding: "15px",
                              borderRadius: "10px",
                              background: "rgba(248,113,113,0.1)",
                              border: "1px solid rgba(248,113,113,0.3)",
                            }}
                          >
                            <div
                              style={{
                                display: "flex",
                                alignItems: "center",
                                gap: "10px",
                                marginBottom: "12px",
                              }}
                            >
                              <Icon name="Shield" size={20} style={{ color: "#f87171" }} />
                              <span style={{ fontWeight: 700, color: "#f87171" }}>
                                Authenticity Alert
                              </span>
                            </div>

                            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                              {/* AI Detection */}
                              {hasAIConcern && (
                                <div
                                  style={{
                                    display: "flex",
                                    alignItems: "flex-start",
                                    gap: "10px",
                                    padding: "10px",
                                    borderRadius: "8px",
                                    background: auth.ai.flag === "likely" ? "rgba(248,113,113,0.15)" : "rgba(251,191,36,0.15)",
                                  }}
                                >
                                  <Icon
                                    name="Bot"
                                    size={16}
                                    style={{
                                      color: auth.ai.flag === "likely" ? "#f87171" : "#fbbf24",
                                      marginTop: "2px",
                                    }}
                                  />
                                  <div>
                                    <div style={{ fontWeight: 600, color: auth.ai.flag === "likely" ? "#f87171" : "#fbbf24", marginBottom: "4px" }}>
                                      AI Generated: {auth.ai.flag} {auth.ai.confidence > 0 && `(${auth.ai.confidence}% confidence)`}
                                    </div>
                                    {auth.ai.reason && (
                                      <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", margin: 0 }}>
                                        {auth.ai.reason}
                                      </p>
                                    )}
                                  </div>
                                </div>
                              )}

                              {/* Plagiarism Detection */}
                              {hasPlagConcern && (
                                <div
                                  style={{
                                    display: "flex",
                                    alignItems: "flex-start",
                                    gap: "10px",
                                    padding: "10px",
                                    borderRadius: "8px",
                                    background: auth.plag.flag === "likely" ? "rgba(248,113,113,0.15)" : "rgba(251,191,36,0.15)",
                                  }}
                                >
                                  <Icon
                                    name="Copy"
                                    size={16}
                                    style={{
                                      color: auth.plag.flag === "likely" ? "#f87171" : "#fbbf24",
                                      marginTop: "2px",
                                    }}
                                  />
                                  <div>
                                    <div style={{ fontWeight: 600, color: auth.plag.flag === "likely" ? "#f87171" : "#fbbf24", marginBottom: "4px" }}>
                                      Plagiarism: {auth.plag.flag}
                                    </div>
                                    {auth.plag.reason && (
                                      <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", margin: 0 }}>
                                        {auth.plag.reason}
                                      </p>
                                    )}
                                  </div>
                                </div>
                              )}
                            </div>

                            <p
                              style={{
                                fontSize: "0.85rem",
                                color: "var(--text-muted)",
                                margin: "12px 0 0 0",
                                fontStyle: "italic",
                              }}
                            >
                              Please review the student's work before sending the email.
                            </p>
                          </div>
                        );
                      })()}

                      <div style={{ marginBottom: "20px" }}>
                        <div
                          style={{
                            fontSize: "0.9rem",
                            color: "var(--text-secondary)",
                            marginBottom: "6px",
                          }}
                        >
                          To:
                        </div>
                        <div style={{ fontWeight: 600, fontSize: "1.05rem" }}>
                          {status.results[viewingEmailIndex].email ||
                            "No email on file"}
                        </div>
                      </div>

                      <div style={{ marginBottom: "20px" }}>
                        <div
                          style={{
                            fontSize: "0.9rem",
                            color: "var(--text-secondary)",
                            marginBottom: "6px",
                          }}
                        >
                          Subject:
                        </div>
                        <input
                          type="text"
                          className="input"
                          value={
                            editedEmails[viewingEmailIndex]?.subject ??
                            `Grade Report: ${status.results[viewingEmailIndex].assignment}`
                          }
                          onChange={(e) =>
                            setEditedEmails((prev) => ({
                              ...prev,
                              [viewingEmailIndex]: {
                                ...prev[viewingEmailIndex],
                                subject: e.target.value,
                                body:
                                  prev[viewingEmailIndex]?.body ??
                                  getDefaultEmailBody(viewingEmailIndex),
                              },
                            }))
                          }
                          style={{ fontWeight: 600, fontSize: "1.05rem" }}
                        />
                      </div>

                      <div style={{ marginBottom: "20px" }}>
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                            marginBottom: "8px",
                          }}
                        >
                          <div
                            style={{
                              fontSize: "0.9rem",
                              color: "var(--text-secondary)",
                            }}
                          >
                            Message:
                          </div>
                          {editedEmails[viewingEmailIndex] && (
                            <button
                              onClick={() =>
                                setEditedEmails((prev) => {
                                  const updated = { ...prev };
                                  delete updated[viewingEmailIndex];
                                  return updated;
                                })
                              }
                              style={{
                                background: "none",
                                border: "none",
                                color: "#a5b4fc",
                                fontSize: "0.85rem",
                                cursor: "pointer",
                                display: "flex",
                                alignItems: "center",
                                gap: "6px",
                              }}
                            >
                              <Icon name="RotateCcw" size={14} />
                              Reset to Default
                            </button>
                          )}
                        </div>
                        <textarea
                          className="input"
                          value={
                            editedEmails[viewingEmailIndex]?.body ??
                            getDefaultEmailBody(viewingEmailIndex)
                          }
                          onChange={(e) =>
                            setEditedEmails((prev) => ({
                              ...prev,
                              [viewingEmailIndex]: {
                                ...prev[viewingEmailIndex],
                                subject:
                                  prev[viewingEmailIndex]?.subject ??
                                  `Grade Report: ${status.results[viewingEmailIndex].assignment}`,
                                body: e.target.value,
                              },
                            }))
                          }
                          style={{
                            minHeight: "400px",
                            fontSize: "1rem",
                            lineHeight: "1.7",
                            fontFamily: "monospace",
                            resize: "vertical",
                          }}
                        />
                      </div>
                    </div>

                    {/* Modal Footer */}
                    {!autoApproveEmails && (
                      <div
                        style={{
                          padding: "20px 25px",
                          borderTop: "1px solid var(--glass-border)",
                          display: "flex",
                          gap: "15px",
                          justifyContent: "flex-end",
                        }}
                      >
                        <button
                          onClick={() => setViewingEmailIndex(null)}
                          className="btn btn-secondary"
                        >
                          Close
                        </button>
                        <button
                          onClick={() =>
                            setEmailApprovals((prev) => ({
                              ...prev,
                              [viewingEmailIndex]: "rejected",
                            }))
                          }
                          className="btn btn-secondary"
                          style={{
                            background:
                              emailApprovals[viewingEmailIndex] === "rejected"
                                ? "rgba(239,68,68,0.3)"
                                : undefined,
                          }}
                        >
                          <Icon name="X" size={18} />
                          {emailApprovals[viewingEmailIndex] === "rejected"
                            ? "Rejected"
                            : "Reject"}
                        </button>
                        <button
                          onClick={() =>
                            setEmailApprovals((prev) => ({
                              ...prev,
                              [viewingEmailIndex]: "approved",
                            }))
                          }
                          className="btn btn-primary"
                          style={{
                            background:
                              emailApprovals[viewingEmailIndex] === "approved"
                                ? "#059669"
                                : undefined,
                          }}
                        >
                          <Icon name="Check" size={18} />
                          {emailApprovals[viewingEmailIndex] === "approved"
                            ? "Approved"
                            : "Approve"}
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              )}

            {/* Settings Tab */}
            {activeTab === "settings" && (
              <div className="fade-in glass-card" style={{ padding: "25px" }}>
                <h2
                  style={{
                    fontSize: "1.3rem",
                    fontWeight: 700,
                    marginBottom: "20px",
                    display: "flex",
                    alignItems: "center",
                    gap: "10px",
                  }}
                >
                  <Icon name="Settings" size={24} />
                  Settings
                </h2>

                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "20px",
                  }}
                >
                  <div>
                    <label className="label">Assignments Folder</label>
                    <div style={{ display: "flex", gap: "10px" }}>
                      <input
                        type="text"
                        className="input"
                        value={config.assignments_folder}
                        onChange={(e) =>
                          setConfig((prev) => ({
                            ...prev,
                            assignments_folder: e.target.value,
                          }))
                        }
                      />
                      <button
                        onClick={() =>
                          handleBrowse("folder", "assignments_folder")
                        }
                        className="btn btn-secondary"
                      >
                        Browse
                      </button>
                      <button
                        onClick={loadAvailableFiles}
                        disabled={!config.assignments_folder || filesLoading}
                        className="btn btn-secondary"
                        style={{ opacity: !config.assignments_folder ? 0.5 : 1 }}
                      >
                        {filesLoading ? "Loading..." : "Load Files"}
                      </button>
                    </div>
                  </div>

                  <div>
                    <label className="label">Output Folder</label>
                    <div style={{ display: "flex", gap: "10px" }}>
                      <input
                        type="text"
                        className="input"
                        value={config.output_folder}
                        onChange={(e) =>
                          setConfig((prev) => ({
                            ...prev,
                            output_folder: e.target.value,
                          }))
                        }
                      />
                      <button
                        onClick={() => handleBrowse("folder", "output_folder")}
                        className="btn btn-secondary"
                      >
                        Browse
                      </button>
                    </div>
                  </div>

                  <div>
                    <label className="label">Roster File</label>
                    <div style={{ display: "flex", gap: "10px" }}>
                      <input
                        type="text"
                        className="input"
                        value={config.roster_file}
                        onChange={(e) =>
                          setConfig((prev) => ({
                            ...prev,
                            roster_file: e.target.value,
                          }))
                        }
                      />
                      <button
                        onClick={() => handleBrowse("file", "roster_file")}
                        className="btn btn-secondary"
                      >
                        Browse
                      </button>
                    </div>
                  </div>

                  {/* File Selection */}
                  {availableFiles.length > 0 && (
                    <div
                      style={{
                        padding: "15px",
                        background: "var(--glass-bg)",
                        borderRadius: "12px",
                        border: "1px solid var(--glass-border)",
                      }}
                    >

                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                        <label className="label" style={{ marginBottom: 0 }}>
                          Select Files to Grade ({selectedFiles.length} of {getFilteredFiles().length} shown)
                        </label>
                        <div style={{ display: "flex", gap: "8px" }}>
                          <button
                            onClick={() => setSelectedFiles(getFilteredFiles().map(f => f.name))}
                            className="btn btn-secondary"
                            style={{ padding: "4px 10px", fontSize: "0.75rem" }}
                          >
                            Select All
                          </button>
                          <button
                            onClick={() => setSelectedFiles(getFilteredFiles().filter(f => !f.graded).map(f => f.name))}
                            className="btn btn-secondary"
                            style={{ padding: "4px 10px", fontSize: "0.75rem" }}
                          >
                            Ungraded Only
                          </button>
                          <button
                            onClick={() => setSelectedFiles([])}
                            className="btn btn-secondary"
                            style={{ padding: "4px 10px", fontSize: "0.75rem" }}
                          >
                            Clear
                          </button>
                        </div>
                      </div>
                      <div
                        style={{
                          maxHeight: "200px",
                          overflowY: "auto",
                          display: "flex",
                          flexDirection: "column",
                          gap: "4px",
                        }}
                      >
                        {getFilteredFiles().length === 0 ? (
                          <p style={{ textAlign: "center", color: "var(--text-muted)", padding: "20px", fontSize: "0.85rem" }}>
                            No files match the selected period filter
                          </p>
                        ) : (
                          getFilteredFiles().map((file) => (
                            <label
                              key={file.name}
                              style={{
                                display: "flex",
                                alignItems: "center",
                                gap: "10px",
                                padding: "8px 12px",
                                background: selectedFiles.includes(file.name)
                                  ? "rgba(99, 102, 241, 0.1)"
                                  : "transparent",
                                borderRadius: "8px",
                                cursor: "pointer",
                                transition: "all 0.15s",
                              }}
                            >
                              <input
                                type="checkbox"
                                checked={selectedFiles.includes(file.name)}
                                onChange={(e) => {
                                  if (e.target.checked) {
                                    setSelectedFiles([...selectedFiles, file.name]);
                                  } else {
                                    setSelectedFiles(selectedFiles.filter(f => f !== file.name));
                                  }
                                }}
                                style={{ width: "16px", height: "16px", cursor: "pointer" }}
                              />
                              <span style={{ flex: 1, fontSize: "0.85rem" }}>{file.name}</span>
                              {file.graded && (
                                <span
                                  style={{
                                    padding: "2px 8px",
                                    borderRadius: "4px",
                                    background: "rgba(74, 222, 128, 0.2)",
                                    color: "#4ade80",
                                    fontSize: "0.7rem",
                                    fontWeight: 600,
                                  }}
                                >
                                  Graded
                                </span>
                              )}
                            </label>
                          ))
                        )}
                      </div>
                    </div>
                  )}

                  {/* Teacher & School Info */}
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "repeat(2, 1fr)",
                      gap: "20px",
                    }}
                  >
                    <div>
                      <label className="label">Teacher Name</label>
                      <input
                        type="text"
                        className="input"
                        value={config.teacher_name}
                        onChange={(e) =>
                          setConfig((prev) => ({
                            ...prev,
                            teacher_name: e.target.value,
                          }))
                        }
                        placeholder="Mr. Smith"
                      />
                    </div>
                    <div>
                      <label className="label">School Name</label>
                      <input
                        type="text"
                        className="input"
                        value={config.school_name}
                        onChange={(e) =>
                          setConfig((prev) => ({
                            ...prev,
                            school_name: e.target.value,
                          }))
                        }
                        placeholder="Lincoln Middle School"
                      />
                    </div>
                  </div>

                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "repeat(3, 1fr)",
                      gap: "20px",
                    }}
                  >
                    <div>
                      <label className="label">State</label>
                      <select
                        className="input"
                        value={config.state}
                        onChange={(e) =>
                          setConfig((prev) => ({
                            ...prev,
                            state: e.target.value,
                          }))
                        }
                      >
                        <option value="FL">Florida</option>
                        <option value="TX">Texas</option>
                        <option value="CA">California</option>
                        <option value="NY">New York</option>
                        <option value="GA">Georgia</option>
                        <option value="NC">North Carolina</option>
                        <option value="VA">Virginia</option>
                        <option value="OH">Ohio</option>
                        <option value="PA">Pennsylvania</option>
                        <option value="IL">Illinois</option>
                      </select>
                    </div>

                    <div>
                      <label className="label">Grade Level</label>
                      <select
                        className="input"
                        value={config.grade_level}
                        onChange={(e) =>
                          setConfig((prev) => ({
                            ...prev,
                            grade_level: e.target.value,
                          }))
                        }
                      >
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
                      <select
                        className="input"
                        value={config.subject}
                        onChange={(e) =>
                          setConfig((prev) => ({
                            ...prev,
                            subject: e.target.value,
                          }))
                        }
                      >
                        <option value="US History">U.S. History</option>
                        <option value="World History">World History</option>
                        <option value="Social Studies">Social Studies</option>
                        <option value="Civics">Civics</option>
                        <option value="Geography">Geography</option>
                        <option value="English/ELA">English/ELA</option>
                        <option value="Math">Math</option>
                        <option value="Science">Science</option>
                        <option value="Other">Other</option>
                      </select>
                    </div>

                    <div>
                      <label className="label">Grading Period</label>
                      <select
                        className="input"
                        value={config.grading_period}
                        onChange={(e) =>
                          setConfig((prev) => ({
                            ...prev,
                            grading_period: e.target.value,
                          }))
                        }
                      >
                        <option value="Q1">Quarter 1 (Q1)</option>
                        <option value="Q2">Quarter 2 (Q2)</option>
                        <option value="Q3">Quarter 3 (Q3)</option>
                        <option value="Q4">Quarter 4 (Q4)</option>
                        <option value="S1">Semester 1 (S1)</option>
                        <option value="S2">Semester 2 (S2)</option>
                      </select>
                    </div>

                    <div>
                      <label className="label">AI Model</label>
                      <select
                        className="input"
                        value={config.ai_model}
                        onChange={(e) =>
                          setConfig((prev) => ({
                            ...prev,
                            ai_model: e.target.value,
                          }))
                        }
                      >
                        <option value="gpt-4o-mini">GPT-4o Mini (Fast & Cheap - $0.09/100 assignments)</option>
                        <option value="gpt-4o">GPT-4o (Best Quality - $1.43/100 assignments)</option>
                      </select>
                      <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "6px" }}>
                        GPT-4o Mini is recommended for most grading. Use GPT-4o for essays or if you need better AI detection.
                      </p>
                    </div>
                  </div>

                  <div>
                    <label className="label">
                      Global AI Grading Instructions
                    </label>
                    <textarea
                      className="input"
                      value={globalAINotes}
                      onChange={(e) => setGlobalAINotes(e.target.value)}
                      placeholder="Instructions that apply to ALL assignments..."
                      style={{ minHeight: "120px", resize: "vertical" }}
                    />
                  </div>

                  {/* Preferences */}
                  <div
                    style={{
                      borderTop: "1px solid var(--glass-border)",
                      paddingTop: "20px",
                      marginTop: "20px",
                    }}
                  >
                    <h3
                      style={{
                        fontSize: "1.1rem",
                        fontWeight: 700,
                        marginBottom: "15px",
                        display: "flex",
                        alignItems: "center",
                        gap: "8px",
                      }}
                    >
                      <Icon name="Bell" size={20} />
                      Notifications
                    </h3>

                    <label
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "12px",
                        cursor: "pointer",
                        padding: "12px 16px",
                        background: "var(--input-bg)",
                        borderRadius: "12px",
                        border: "1px solid var(--input-border)",
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={config.showToastNotifications}
                        onChange={(e) =>
                          setConfig((prev) => ({
                            ...prev,
                            showToastNotifications: e.target.checked,
                          }))
                        }
                        style={{
                          width: "18px",
                          height: "18px",
                          accentColor: "var(--accent-primary)",
                          cursor: "pointer",
                        }}
                      />
                      <div>
                        <div style={{ fontWeight: 600, fontSize: "0.95rem" }}>
                          Toast Notifications
                        </div>
                        <div style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                          Show popup notifications when assignments are graded
                        </div>
                      </div>
                    </label>
                  </div>

                  {/* Rubric Configuration */}
                  <div
                    style={{
                      borderTop: "1px solid var(--glass-border)",
                      paddingTop: "20px",
                      marginTop: "20px",
                    }}
                  >
                    <h3
                      style={{
                        fontSize: "1.1rem",
                        fontWeight: 700,
                        marginBottom: "15px",
                        display: "flex",
                        alignItems: "center",
                        gap: "10px",
                      }}
                    >
                      <Icon
                        name="ClipboardCheck"
                        size={20}
                        style={{ color: "#8b5cf6" }}
                      />
                      Grading Rubric
                    </h3>
                    <p
                      style={{
                        fontSize: "0.85rem",
                        color: "var(--text-secondary)",
                        marginBottom: "15px",
                      }}
                    >
                      Configure how assignments are scored. Weights must total
                      100%.
                    </p>

                    <div
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        gap: "12px",
                        marginBottom: "15px",
                      }}
                    >
                      {rubric.categories.map((cat, idx) => (
                        <div
                          key={idx}
                          style={{
                            display: "flex",
                            gap: "10px",
                            alignItems: "center",
                            padding: "12px",
                            background: "var(--input-bg)",
                            borderRadius: "8px",
                          }}
                        >
                          <input
                            type="text"
                            className="input"
                            value={cat.name}
                            onChange={(e) => {
                              const updated = [...rubric.categories];
                              updated[idx].name = e.target.value;
                              setRubric({ ...rubric, categories: updated });
                            }}
                            style={{ flex: 1 }}
                            placeholder="Category name"
                          />
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "5px",
                            }}
                          >
                            <input
                              type="number"
                              className="input"
                              value={cat.weight}
                              onChange={(e) => {
                                const updated = [...rubric.categories];
                                updated[idx].weight =
                                  parseInt(e.target.value) || 0;
                                setRubric({ ...rubric, categories: updated });
                              }}
                              style={{ width: "70px", textAlign: "center" }}
                              min="0"
                              max="100"
                            />
                            <span style={{ color: "var(--text-secondary)" }}>
                              %
                            </span>
                          </div>
                          <button
                            onClick={() => {
                              const updated = rubric.categories.filter(
                                (_, i) => i !== idx,
                              );
                              setRubric({ ...rubric, categories: updated });
                            }}
                            style={{
                              padding: "6px",
                              background: "none",
                              border: "none",
                              color: "var(--text-muted)",
                              cursor: "pointer",
                            }}
                          >
                            <Icon name="X" size={16} />
                          </button>
                        </div>
                      ))}
                    </div>

                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "15px",
                        marginBottom: "15px",
                      }}
                    >
                      <button
                        onClick={() => {
                          setRubric({
                            ...rubric,
                            categories: [
                              ...rubric.categories,
                              { name: "", weight: 0, description: "" },
                            ],
                          });
                        }}
                        className="btn btn-secondary"
                        style={{ fontSize: "0.85rem" }}
                      >
                        <Icon name="Plus" size={16} />
                        Add Category
                      </button>
                      <span
                        style={{
                          fontSize: "0.85rem",
                          color:
                            rubric.categories.reduce(
                              (sum, c) => sum + c.weight,
                              0,
                            ) === 100
                              ? "#10b981"
                              : "#ef4444",
                        }}
                      >
                        Total:{" "}
                        {rubric.categories.reduce(
                          (sum, c) => sum + c.weight,
                          0,
                        )}
                        %
                        {rubric.categories.reduce(
                          (sum, c) => sum + c.weight,
                          0,
                        ) !== 100 && " (must equal 100%)"}
                      </span>
                    </div>

                    <span
                      style={{
                        fontSize: "0.85rem",
                        color: "var(--text-secondary)",
                        display: "flex",
                        alignItems: "center",
                        gap: "6px",
                      }}
                    >
                      <Icon
                        name="Check"
                        size={14}
                        style={{ color: "#4ade80" }}
                      />
                      Auto-saved
                    </span>
                  </div>

                  {/* Auto-save indicator */}
                  <div
                    style={{
                      alignSelf: "flex-start",
                      marginTop: "20px",
                      padding: "12px 20px",
                      background: "rgba(74,222,128,0.1)",
                      border: "1px solid rgba(74,222,128,0.3)",
                      borderRadius: "10px",
                      display: "flex",
                      alignItems: "center",
                      gap: "10px",
                    }}
                  >
                    <Icon
                      name="CheckCircle"
                      size={20}
                      style={{ color: "#4ade80" }}
                    />
                    <span style={{ color: "#4ade80", fontWeight: 600 }}>
                      Settings auto-save
                    </span>
                    <span
                      style={{
                        color: "var(--text-secondary)",
                        fontSize: "0.85rem",
                      }}
                    >
                      Changes are saved automatically
                    </span>
                  </div>

                  {/* Roster Upload Section */}
                  <div
                    style={{
                      borderTop: "1px solid var(--glass-border)",
                      paddingTop: "25px",
                      marginTop: "25px",
                    }}
                  >
                    <h3
                      style={{
                        fontSize: "1.1rem",
                        fontWeight: 700,
                        marginBottom: "15px",
                        display: "flex",
                        alignItems: "center",
                        gap: "10px",
                      }}
                    >
                      <Icon
                        name="Users"
                        size={20}
                        style={{ color: "#6366f1" }}
                      />
                      Student Roster
                    </h3>
                    <p
                      style={{
                        fontSize: "0.85rem",
                        color: "var(--text-secondary)",
                        marginBottom: "15px",
                      }}
                    >
                      Upload CSV with Student ID, Name, Student Email, and
                      Parent Email columns
                    </p>

                    <input
                      ref={rosterInputRef}
                      type="file"
                      accept=".csv"
                      style={{ display: "none" }}
                      onChange={async (e) => {
                        const file = e.target.files?.[0];
                        if (!file) return;
                        setUploadingRoster(true);
                        try {
                          const result = await api.uploadRoster(file);
                          if (result.error) {
                            alert(result.error);
                          } else {
                            const rostersData = await api.listRosters();
                            setRosters(rostersData.rosters || []);
                            setRosterMappingModal({
                              show: true,
                              roster: result,
                            });
                          }
                        } catch (err) {
                          alert("Upload failed: " + err.message);
                        }
                        setUploadingRoster(false);
                        e.target.value = "";
                      }}
                    />

                    <button
                      onClick={() => rosterInputRef.current?.click()}
                      className="btn btn-secondary"
                      disabled={uploadingRoster}
                      style={{ marginBottom: "15px" }}
                    >
                      <Icon name="Upload" size={18} />
                      {uploadingRoster ? "Uploading..." : "Upload Roster CSV"}
                    </button>

                    {rosters.length > 0 && (
                      <div
                        style={{
                          display: "flex",
                          flexDirection: "column",
                          gap: "10px",
                        }}
                      >
                        {rosters.map((roster) => (
                          <div
                            key={roster.filename}
                            style={{
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "space-between",
                              padding: "12px 15px",
                              background: "var(--input-bg)",
                              borderRadius: "8px",
                              border: "1px solid var(--glass-border)",
                            }}
                          >
                            <div
                              style={{
                                display: "flex",
                                alignItems: "center",
                                gap: "12px",
                              }}
                            >
                              <Icon
                                name="FileSpreadsheet"
                                size={18}
                                style={{ color: "#10b981" }}
                              />
                              <div>
                                <div style={{ fontWeight: 600 }}>
                                  {roster.filename}
                                </div>
                                <div
                                  style={{
                                    fontSize: "0.8rem",
                                    color: "var(--text-secondary)",
                                  }}
                                >
                                  {roster.row_count} students •{" "}
                                  {roster.headers?.length || 0} columns
                                  {Object.keys(roster.column_mapping || {})
                                    .length > 0 && " • Mapped"}
                                </div>
                              </div>
                            </div>
                            <div style={{ display: "flex", gap: "8px" }}>
                              <button
                                onClick={() =>
                                  setRosterMappingModal({ show: true, roster })
                                }
                                className="btn btn-secondary"
                                style={{
                                  padding: "6px 12px",
                                  fontSize: "0.8rem",
                                }}
                              >
                                <Icon name="Settings2" size={14} />
                                Map Columns
                              </button>
                              <button
                                onClick={async () => {
                                  if (confirm("Delete this roster?")) {
                                    await api.deleteRoster(roster.filename);
                                    const data = await api.listRosters();
                                    setRosters(data.rosters || []);
                                  }
                                }}
                                style={{
                                  padding: "6px 10px",
                                  background: "rgba(239,68,68,0.2)",
                                  border: "none",
                                  borderRadius: "6px",
                                  color: "#ef4444",
                                  cursor: "pointer",
                                }}
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
                  <div
                    style={{
                      borderTop: "1px solid var(--glass-border)",
                      paddingTop: "25px",
                      marginTop: "25px",
                    }}
                  >
                    <h3
                      style={{
                        fontSize: "1.1rem",
                        fontWeight: 700,
                        marginBottom: "15px",
                        display: "flex",
                        alignItems: "center",
                        gap: "10px",
                      }}
                    >
                      <Icon
                        name="Clock"
                        size={20}
                        style={{ color: "#f59e0b" }}
                      />
                      Class Periods
                    </h3>
                    <p
                      style={{
                        fontSize: "0.85rem",
                        color: "var(--text-secondary)",
                        marginBottom: "15px",
                      }}
                    >
                      Upload separate rosters for each class period
                    </p>

                    <input
                      ref={periodInputRef}
                      type="file"
                      accept=".csv,.xlsx,.xls"
                      style={{ display: "none" }}
                      onChange={async (e) => {
                        const file = e.target.files?.[0];
                        if (!file) return;
                        if (!newPeriodName.trim()) {
                          alert("Please enter a period name first");
                          e.target.value = "";
                          return;
                        }
                        setUploadingPeriod(true);
                        try {
                          const result = await api.uploadPeriod(
                            file,
                            newPeriodName,
                          );
                          if (result.error) {
                            alert(result.error);
                          } else {
                            const periodsData = await api.listPeriods();
                            setPeriods(periodsData.periods || []);
                            setNewPeriodName("");
                          }
                        } catch (err) {
                          alert("Upload failed: " + err.message);
                        }
                        setUploadingPeriod(false);
                        e.target.value = "";
                      }}
                    />

                    <div
                      style={{
                        display: "flex",
                        gap: "10px",
                        marginBottom: "15px",
                      }}
                    >
                      <input
                        type="text"
                        className="input"
                        placeholder="Period name (e.g., Period 1, Block A)"
                        value={newPeriodName}
                        onChange={(e) => setNewPeriodName(e.target.value)}
                        style={{ maxWidth: "250px" }}
                      />
                      <button
                        onClick={() => periodInputRef.current?.click()}
                        className="btn btn-secondary"
                        disabled={uploadingPeriod || !newPeriodName.trim()}
                        style={{
                          opacity: (!newPeriodName.trim() || uploadingPeriod) ? 0.5 : 1,
                          cursor: (!newPeriodName.trim() || uploadingPeriod) ? "not-allowed" : "pointer",
                        }}
                        title={!newPeriodName.trim() ? "Enter a period name first" : ""}
                      >
                        <Icon name="Upload" size={18} />
                        {uploadingPeriod ? "Uploading..." : "Upload CSV/Excel"}
                      </button>
                    </div>
                    {!newPeriodName.trim() && (
                      <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "-10px", marginBottom: "10px" }}>
                        Enter a period name above, then click Upload
                      </p>
                    )}

                    {periods.length > 0 && (
                      <div
                        style={{
                          display: "flex",
                          flexWrap: "wrap",
                          gap: "10px",
                        }}
                      >
                        {periods.map((period) => (
                          <div
                            key={period.filename}
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "10px",
                              padding: "10px 15px",
                              background: "var(--input-bg)",
                              borderRadius: "8px",
                              border: "1px solid var(--glass-border)",
                            }}
                          >
                            <Icon
                              name="Users"
                              size={16}
                              style={{ color: "#f59e0b" }}
                            />
                            <div>
                              <div
                                style={{ fontWeight: 600, fontSize: "0.9rem" }}
                              >
                                {period.period_name}
                              </div>
                              <div
                                style={{
                                  fontSize: "0.75rem",
                                  color: "var(--text-secondary)",
                                }}
                              >
                                {period.row_count} students
                              </div>
                            </div>
                            <button
                              onClick={async () => {
                                if (confirm(`Delete ${period.period_name}?`)) {
                                  await api.deletePeriod(period.filename);
                                  const data = await api.listPeriods();
                                  setPeriods(data.periods || []);
                                }
                              }}
                              style={{
                                padding: "4px 6px",
                                background: "none",
                                border: "none",
                                color: "var(--text-muted)",
                                cursor: "pointer",
                              }}
                            >
                              <Icon name="X" size={14} />
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* FERPA Compliance & Data Privacy */}
                  <div
                    style={{
                      borderTop: "1px solid var(--glass-border)",
                      paddingTop: "25px",
                      marginTop: "25px",
                    }}
                  >
                    <h3
                      style={{
                        fontSize: "1.1rem",
                        fontWeight: 700,
                        marginBottom: "15px",
                        display: "flex",
                        alignItems: "center",
                        gap: "10px",
                      }}
                    >
                      <Icon
                        name="Shield"
                        size={20}
                        style={{ color: "#10b981" }}
                      />
                      Privacy & Data (FERPA)
                    </h3>
                    <p
                      style={{
                        fontSize: "0.85rem",
                        color: "var(--text-secondary)",
                        marginBottom: "20px",
                      }}
                    >
                      Graider is designed for FERPA compliance. Student names are
                      sanitized before AI processing, and all data is stored locally
                      on your computer.
                    </p>

                    {/* Privacy Features */}
                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(2, 1fr)",
                        gap: "15px",
                        marginBottom: "20px",
                      }}
                    >
                      <div
                        style={{
                          padding: "15px",
                          background: "rgba(74,222,128,0.1)",
                          borderRadius: "10px",
                          border: "1px solid rgba(74,222,128,0.2)",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
                          <Icon name="CheckCircle" size={16} style={{ color: "#4ade80" }} />
                          <span style={{ fontWeight: 600, fontSize: "0.9rem" }}>PII Sanitization</span>
                        </div>
                        <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", margin: 0 }}>
                          Student names, IDs, emails, and phone numbers are removed before AI processing
                        </p>
                      </div>

                      <div
                        style={{
                          padding: "15px",
                          background: "rgba(74,222,128,0.1)",
                          borderRadius: "10px",
                          border: "1px solid rgba(74,222,128,0.2)",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
                          <Icon name="CheckCircle" size={16} style={{ color: "#4ade80" }} />
                          <span style={{ fontWeight: 600, fontSize: "0.9rem" }}>Local Storage Only</span>
                        </div>
                        <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", margin: 0 }}>
                          All data stays on your computer. No cloud storage of student information
                        </p>
                      </div>

                      <div
                        style={{
                          padding: "15px",
                          background: "rgba(74,222,128,0.1)",
                          borderRadius: "10px",
                          border: "1px solid rgba(74,222,128,0.2)",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
                          <Icon name="CheckCircle" size={16} style={{ color: "#4ade80" }} />
                          <span style={{ fontWeight: 600, fontSize: "0.9rem" }}>No AI Training</span>
                        </div>
                        <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", margin: 0 }}>
                          OpenAI API does not use submitted data to train models (per their policy)
                        </p>
                      </div>

                      <div
                        style={{
                          padding: "15px",
                          background: "rgba(74,222,128,0.1)",
                          borderRadius: "10px",
                          border: "1px solid rgba(74,222,128,0.2)",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
                          <Icon name="CheckCircle" size={16} style={{ color: "#4ade80" }} />
                          <span style={{ fontWeight: 600, fontSize: "0.9rem" }}>Audit Logging</span>
                        </div>
                        <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", margin: 0 }}>
                          All data access is logged locally for compliance tracking
                        </p>
                      </div>
                    </div>

                    {/* Data Management Actions */}
                    <div
                      style={{
                        padding: "15px",
                        background: "var(--input-bg)",
                        borderRadius: "10px",
                        border: "1px solid var(--input-border)",
                      }}
                    >
                      <div style={{ fontWeight: 600, marginBottom: "12px" }}>Data Management</div>
                      <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
                        <button
                          onClick={async () => {
                            try {
                              const response = await fetch("/api/ferpa/data-summary");
                              const data = await response.json();
                              alert(
                                `Data Storage Summary\n\n` +
                                `• Grading Results: ${data.results.count} records\n` +
                                `• Settings: ${data.settings.exists ? "Saved" : "Not saved"}\n` +
                                `• Audit Log: ${data.audit_log.exists ? "Active" : "Not started"}\n\n` +
                                `Data Locations:\n` +
                                data.data_locations.join("\n")
                              );
                            } catch (err) {
                              alert("Failed to fetch data summary");
                            }
                          }}
                          className="btn btn-secondary"
                          style={{ fontSize: "0.85rem" }}
                        >
                          <Icon name="Database" size={16} />
                          View Data Summary
                        </button>

                        <button
                          onClick={async () => {
                            try {
                              const response = await fetch("/api/ferpa/export-data");
                              const data = await response.json();
                              const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
                              const url = URL.createObjectURL(blob);
                              const a = document.createElement("a");
                              a.href = url;
                              a.download = `graider_export_${new Date().toISOString().split("T")[0]}.json`;
                              a.click();
                              URL.revokeObjectURL(url);
                            } catch (err) {
                              alert("Failed to export data");
                            }
                          }}
                          className="btn btn-secondary"
                          style={{ fontSize: "0.85rem" }}
                        >
                          <Icon name="Download" size={16} />
                          Export All Data
                        </button>

                        <button
                          onClick={async () => {
                            if (!confirm(
                              "⚠️ DELETE ALL STUDENT DATA?\n\n" +
                              "This will permanently delete:\n" +
                              "• All grading results\n" +
                              "• Current session data\n\n" +
                              "This action cannot be undone.\n\n" +
                              "Type 'DELETE' in the next prompt to confirm."
                            )) return;

                            const confirmText = prompt("Type DELETE to confirm:");
                            if (confirmText !== "DELETE") {
                              alert("Deletion cancelled");
                              return;
                            }

                            try {
                              const response = await fetch("/api/ferpa/delete-all-data", {
                                method: "POST",
                                headers: { "Content-Type": "application/json" },
                                body: JSON.stringify({ confirm: true }),
                              });
                              const data = await response.json();
                              if (data.status === "success") {
                                alert("✓ All student data has been deleted.\n\n" + data.deleted.join("\n"));
                                window.location.reload();
                              } else {
                                alert("Error: " + (data.error || "Unknown error"));
                              }
                            } catch (err) {
                              alert("Failed to delete data: " + err.message);
                            }
                          }}
                          className="btn btn-danger"
                          style={{ fontSize: "0.85rem" }}
                        >
                          <Icon name="Trash2" size={16} />
                          Delete All Data
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Resources Tab */}
            {activeTab === "resources" && (
              <div className="fade-in glass-card" style={{ padding: "25px" }}>
                <h2
                  style={{
                    fontSize: "1.3rem",
                    fontWeight: 700,
                    marginBottom: "20px",
                    display: "flex",
                    alignItems: "center",
                    gap: "10px",
                  }}
                >
                  <Icon name="FolderOpen" size={24} />
                  Resources
                </h2>
                <p
                  style={{
                    fontSize: "0.9rem",
                    color: "var(--text-secondary)",
                    marginBottom: "25px",
                  }}
                >
                  Upload curriculum guides, rubrics, standards documents, and
                  other reference materials to enhance AI grading and lesson
                  planning.
                </p>

                {/* Supporting Documents Section */}
                <div>
                  <h3
                    style={{
                      fontSize: "1.1rem",
                      fontWeight: 700,
                      marginBottom: "15px",
                      display: "flex",
                      alignItems: "center",
                      gap: "10px",
                    }}
                  >
                    <Icon
                      name="FileText"
                      size={20}
                      style={{ color: "#10b981" }}
                    />
                    Supporting Documents
                  </h3>
                  <p
                    style={{
                      fontSize: "0.85rem",
                      color: "var(--text-secondary)",
                      marginBottom: "15px",
                    }}
                  >
                    Upload curriculum guides, rubrics, standards docs, or other
                    reference materials
                  </p>

                  <input
                    ref={supportDocInputRef}
                    type="file"
                    accept=".pdf,.docx,.doc,.txt,.md"
                    style={{ display: "none" }}
                    onChange={async (e) => {
                      const file = e.target.files?.[0];
                      if (!file) return;
                      setUploadingDoc(true);
                      try {
                        const result = await api.uploadSupportDocument(
                          file,
                          newDocType,
                          newDocDescription,
                        );
                        if (result.error) {
                          alert(result.error);
                        } else {
                          const docsData = await api.listSupportDocuments();
                          setSupportDocs(docsData.documents || []);
                          setNewDocDescription("");
                        }
                      } catch (err) {
                        alert("Upload failed: " + err.message);
                      }
                      setUploadingDoc(false);
                      e.target.value = "";
                    }}
                  />

                  <div
                    style={{
                      display: "flex",
                      gap: "10px",
                      marginBottom: "15px",
                      flexWrap: "wrap",
                    }}
                  >
                    <select
                      className="input"
                      value={newDocType}
                      onChange={(e) => setNewDocType(e.target.value)}
                      style={{ maxWidth: "180px" }}
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
                      onChange={(e) => setNewDocDescription(e.target.value)}
                      style={{ flex: 1, minWidth: "200px" }}
                    />
                    <button
                      onClick={() => supportDocInputRef.current?.click()}
                      className="btn btn-secondary"
                      disabled={uploadingDoc}
                    >
                      <Icon name="Upload" size={18} />
                      {uploadingDoc ? "Uploading..." : "Upload Document"}
                    </button>
                  </div>

                  {supportDocs.length > 0 && (
                    <div
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        gap: "10px",
                      }}
                    >
                      {supportDocs.map((doc) => (
                        <div
                          key={doc.filename}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            padding: "12px 15px",
                            background: "var(--input-bg)",
                            borderRadius: "8px",
                            border: "1px solid var(--glass-border)",
                          }}
                        >
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "12px",
                            }}
                          >
                            <Icon
                              name={
                                doc.doc_type === "rubric"
                                  ? "ClipboardCheck"
                                  : doc.doc_type === "standards"
                                    ? "BookOpen"
                                    : "FileText"
                              }
                              size={18}
                              style={{ color: "#10b981" }}
                            />
                            <div>
                              <div style={{ fontWeight: 600 }}>
                                {doc.filename}
                              </div>
                              <div
                                style={{
                                  fontSize: "0.8rem",
                                  color: "var(--text-secondary)",
                                }}
                              >
                                {doc.doc_type}{" "}
                                {doc.description && `• ${doc.description}`}
                              </div>
                            </div>
                          </div>
                          <button
                            onClick={async () => {
                              if (confirm("Delete this document?")) {
                                await api.deleteSupportDocument(doc.filename);
                                const data = await api.listSupportDocuments();
                                setSupportDocs(data.documents || []);
                              }
                            }}
                            style={{
                              padding: "6px 10px",
                              background: "rgba(239,68,68,0.2)",
                              border: "none",
                              borderRadius: "6px",
                              color: "#ef4444",
                              cursor: "pointer",
                            }}
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
              <div
                style={{
                  position: "fixed",
                  inset: 0,
                  background: "var(--modal-bg)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  zIndex: 1000,
                }}
              >
                <div
                  className="glass-card"
                  style={{
                    width: "90%",
                    maxWidth: "500px",
                    maxHeight: "80vh",
                    overflow: "auto",
                    padding: "25px",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      marginBottom: "20px",
                    }}
                  >
                    <h3 style={{ fontSize: "1.2rem", fontWeight: 700 }}>
                      Map Roster Columns
                    </h3>
                    <button
                      onClick={() =>
                        setRosterMappingModal({ show: false, roster: null })
                      }
                      style={{
                        background: "none",
                        border: "none",
                        color: "var(--text-primary)",
                        cursor: "pointer",
                      }}
                    >
                      <Icon name="X" size={24} />
                    </button>
                  </div>

                  <p
                    style={{
                      fontSize: "0.9rem",
                      color: "var(--text-secondary)",
                      marginBottom: "20px",
                    }}
                  >
                    Map your CSV columns to the required fields
                  </p>

                  {[
                    "student_id",
                    "student_name",
                    "first_name",
                    "last_name",
                    "student_email",
                    "parent_email",
                  ].map((field) => (
                    <div key={field} style={{ marginBottom: "15px" }}>
                      <label
                        className="label"
                        style={{ textTransform: "capitalize" }}
                      >
                        {field.replace(/_/g, " ")}
                      </label>
                      <select
                        className="input"
                        value={
                          rosterMappingModal.roster?.column_mapping?.[field] ||
                          ""
                        }
                        onChange={(e) => {
                          const newMapping = {
                            ...rosterMappingModal.roster?.column_mapping,
                            [field]: e.target.value,
                          };
                          setRosterMappingModal((prev) => ({
                            ...prev,
                            roster: {
                              ...prev.roster,
                              column_mapping: newMapping,
                            },
                          }));
                        }}
                      >
                        <option value="">-- Select Column --</option>
                        {(rosterMappingModal.roster?.headers || []).map(
                          (header) => (
                            <option key={header} value={header}>
                              {header}
                            </option>
                          ),
                        )}
                      </select>
                    </div>
                  ))}

                  <div
                    style={{ display: "flex", gap: "10px", marginTop: "20px" }}
                  >
                    <button
                      onClick={async () => {
                        try {
                          await api.saveRosterMapping(
                            rosterMappingModal.roster.filename,
                            rosterMappingModal.roster.column_mapping,
                          );
                          const data = await api.listRosters();
                          setRosters(data.rosters || []);
                          setRosterMappingModal({ show: false, roster: null });
                        } catch (err) {
                          alert("Error saving mapping: " + err.message);
                        }
                      }}
                      className="btn btn-primary"
                    >
                      <Icon name="Save" size={18} />
                      Save Mapping
                    </button>
                    <button
                      onClick={() =>
                        setRosterMappingModal({ show: false, roster: null })
                      }
                      className="btn btn-secondary"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Builder Tab */}
            {activeTab === "builder" && (
              <div className="fade-in">
                {/* Saved Assignments */}
                <div
                  className="glass-card"
                  style={{ padding: "25px", marginBottom: "20px" }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      marginBottom: "15px",
                    }}
                  >
                    <h3
                      style={{
                        fontSize: "1.1rem",
                        fontWeight: 700,
                        display: "flex",
                        alignItems: "center",
                        gap: "10px",
                      }}
                    >
                      <Icon
                        name="FolderOpen"
                        size={20}
                        style={{ color: "#10b981" }}
                      />
                      Saved Assignments ({savedAssignments.length})
                    </h3>
                    <button
                      onClick={() => {
                        setAssignment({
                          title: "",
                          subject: "Social Studies",
                          totalPoints: 100,
                          instructions: "",
                          questions: [],
                          customMarkers: [],
                          gradingNotes: "",
                          responseSections: [],
                        });
                        setImportedDoc({
                          text: "",
                          html: "",
                          filename: "",
                          loading: false,
                        });
                        setLoadedAssignmentName("");
                      }}
                      className="btn btn-primary"
                    >
                      + New Assignment
                    </button>
                  </div>

                  {savedAssignments.length === 0 ? (
                    <p
                      style={{
                        textAlign: "center",
                        padding: "30px",
                        color: "var(--text-muted)",
                      }}
                    >
                      No saved assignments yet. Create one below!
                    </p>
                  ) : (
                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns:
                          "repeat(auto-fill, minmax(280px, 1fr))",
                        gap: "12px",
                      }}
                    >
                      {savedAssignments.map((name) => (
                        <div
                          key={name}
                          style={{
                            padding: "15px",
                            background:
                              loadedAssignmentName === name
                                ? "rgba(99,102,241,0.2)"
                                : "var(--input-bg)",
                            borderRadius: "12px",
                            border:
                              loadedAssignmentName === name
                                ? "2px solid rgba(99,102,241,0.5)"
                                : "1px solid var(--glass-border)",
                            cursor: "pointer",
                          }}
                          onClick={() => loadAssignment(name)}
                        >
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "flex-start",
                            }}
                          >
                            <div>
                              <div
                                style={{
                                  fontWeight: 600,
                                  marginBottom: "5px",
                                  display: "flex",
                                  alignItems: "center",
                                  gap: "8px",
                                }}
                              >
                                <Icon
                                  name="FileText"
                                  size={16}
                                  style={{ color: "#a5b4fc" }}
                                />
                                {name}
                              </div>
                              <div
                                style={{
                                  fontSize: "0.8rem",
                                  color: "var(--text-secondary)",
                                }}
                              >
                                Click to load and edit
                              </div>
                            </div>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                deleteAssignment(name);
                              }}
                              style={{
                                padding: "4px",
                                background: "none",
                                border: "none",
                                color: "var(--text-muted)",
                                cursor: "pointer",
                              }}
                            >
                              <Icon name="Trash2" size={14} />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Assignment Editor */}
                <div className="glass-card" style={{ padding: "30px" }}>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      marginBottom: "25px",
                    }}
                  >
                    <h2
                      style={{
                        fontSize: "1.3rem",
                        fontWeight: 700,
                        display: "flex",
                        alignItems: "center",
                        gap: "10px",
                      }}
                    >
                      <Icon name="FileEdit" size={24} />
                      {assignment.title
                        ? `Editing: ${assignment.title}`
                        : "New Assignment"}
                    </h2>
                    {assignment.title && (
                      <span
                        style={{
                          fontSize: "0.85rem",
                          color: "var(--text-secondary)",
                        }}
                      >
                        {(assignment.customMarkers || []).length} markers
                      </span>
                    )}
                  </div>

                  {/* Assignment Details */}
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "2fr 1fr 1fr",
                      gap: "15px",
                      marginBottom: "25px",
                    }}
                  >
                    <div>
                      <label className="label">Assignment Title</label>
                      <input
                        type="text"
                        className="input"
                        value={assignment.title}
                        onChange={(e) =>
                          setAssignment({
                            ...assignment,
                            title: e.target.value,
                          })
                        }
                        placeholder="e.g., Louisiana Purchase Quiz"
                      />
                    </div>
                    <div>
                      <label className="label">Subject</label>
                      <input
                        type="text"
                        className="input"
                        value={config.subject || "Social Studies"}
                        disabled
                        style={{
                          background: "var(--glass-hover)",
                          color: "var(--text-secondary)",
                        }}
                        title="Subject is set in Settings tab"
                      />
                    </div>
                    <div>
                      <label className="label">Total Points</label>
                      <input
                        type="number"
                        className="input"
                        value={assignment.totalPoints}
                        onChange={(e) =>
                          setAssignment({
                            ...assignment,
                            totalPoints: parseInt(e.target.value) || 100,
                          })
                        }
                      />
                    </div>
                  </div>

                  {/* Import Document */}
                  <div
                    style={{
                      marginBottom: "25px",
                      padding: "20px",
                      background: "rgba(251,191,36,0.1)",
                      borderRadius: "12px",
                      border: "1px solid rgba(251,191,36,0.3)",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                      }}
                    >
                      <div>
                        <h3
                          style={{
                            fontSize: "1rem",
                            fontWeight: 600,
                            display: "flex",
                            alignItems: "center",
                            gap: "8px",
                            marginBottom: "5px",
                          }}
                        >
                          <Icon name="FileUp" size={20} />
                          Import Document & Mark Sections
                        </h3>
                        <p
                          style={{
                            fontSize: "0.85rem",
                            color: "var(--text-secondary)",
                            margin: 0,
                          }}
                        >
                          {importedDoc.text ? (
                            <>
                              <strong style={{ color: "#fbbf24" }}>
                                {importedDoc.filename}
                              </strong>{" "}
                              loaded
                            </>
                          ) : (
                            "Import a Word or PDF to highlight gradeable sections"
                          )}
                        </p>
                      </div>
                      <div style={{ display: "flex", gap: "10px" }}>
                        <input
                          type="file"
                          ref={fileInputRef}
                          onChange={handleDocImport}
                          accept=".docx,.pdf,.doc,.txt"
                          style={{ display: "none" }}
                        />
                        {importedDoc.text && (
                          <>
                            <button
                              onClick={openDocEditor}
                              className="btn btn-secondary"
                            >
                              <Icon name="Edit" size={16} />
                              Edit & Mark
                            </button>
                            <button
                              onClick={() => setImportedDoc({ text: '', html: '', filename: '', loading: false })}
                              className="btn btn-secondary"
                              style={{ background: 'rgba(239,68,68,0.2)', color: '#ef4444' }}
                              title="Clear imported document"
                            >
                              <Icon name="Trash2" size={16} />
                            </button>
                          </>
                        )}
                        <button
                          onClick={() => fileInputRef.current?.click()}
                          className="btn btn-primary"
                          style={{
                            background:
                              "linear-gradient(135deg, #f59e0b, #d97706)",
                          }}
                        >
                          <Icon name="Upload" size={16} />
                          {importedDoc.loading
                            ? "Loading..."
                            : "Import Word/PDF"}
                        </button>
                      </div>
                    </div>

                    {/* Manual Marker Input */}
                    <div
                      style={{
                        marginTop: "15px",
                        display: "flex",
                        gap: "10px",
                        alignItems: "center",
                      }}
                    >
                      <input
                        type="text"
                        id="manualMarkerInput"
                        placeholder="Type a marker phrase and press Add..."
                        className="input"
                        style={{ flex: 1 }}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" && e.target.value.trim()) {
                            const newMarker = e.target.value.trim();
                            if (
                              !(assignment.customMarkers || []).includes(
                                newMarker,
                              )
                            ) {
                              setAssignment({
                                ...assignment,
                                customMarkers: [
                                  ...(assignment.customMarkers || []),
                                  newMarker,
                                ],
                              });
                            }
                            e.target.value = "";
                          }
                        }}
                      />
                      <button
                        onClick={() => {
                          const input =
                            document.getElementById("manualMarkerInput");
                          if (input?.value.trim()) {
                            const newMarker = input.value.trim();
                            if (
                              !(assignment.customMarkers || []).includes(
                                newMarker,
                              )
                            ) {
                              setAssignment({
                                ...assignment,
                                customMarkers: [
                                  ...(assignment.customMarkers || []),
                                  newMarker,
                                ],
                              });
                            }
                            input.value = "";
                          }
                        }}
                        className="btn btn-secondary"
                      >
                        <Icon name="Plus" size={16} />
                        Add
                      </button>
                    </div>

                    {/* Custom Markers */}
                    {(assignment.customMarkers || []).length > 0 && (
                      <div
                        style={{
                          marginTop: "15px",
                          display: "flex",
                          flexWrap: "wrap",
                          gap: "8px",
                        }}
                      >
                        {assignment.customMarkers.map((marker, i) => (
                          <div
                            key={i}
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "6px",
                              padding: "6px 12px",
                              background: "rgba(251,191,36,0.2)",
                              borderRadius: "6px",
                              border: "1px solid rgba(251,191,36,0.3)",
                            }}
                          >
                            <Icon
                              name="Target"
                              size={12}
                              style={{ color: "#fbbf24" }}
                            />
                            <span
                              style={{
                                fontSize: "0.8rem",
                                maxWidth: "200px",
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                                whiteSpace: "nowrap",
                              }}
                            >
                              {marker}
                            </span>
                            <button
                              onClick={() => removeMarker(marker)}
                              style={{
                                background: "none",
                                border: "none",
                                color: "var(--text-muted)",
                                cursor: "pointer",
                                padding: "0",
                              }}
                            >
                              <Icon name="X" size={12} />
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Marker Library */}
                  <div
                    style={{
                      marginBottom: "25px",
                      padding: "15px 20px",
                      background: "rgba(99,102,241,0.1)",
                      borderRadius: "12px",
                      border: "1px solid rgba(99,102,241,0.2)",
                    }}
                  >
                    <label
                      style={{
                        display: "block",
                        fontSize: "0.9rem",
                        fontWeight: 600,
                        marginBottom: "10px",
                      }}
                    >
                      <Icon
                        name="Bookmark"
                        size={16}
                        style={{ marginRight: "8px" }}
                      />
                      Suggested Markers for {config.subject || "Social Studies"}
                    </label>
                    <div
                      style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}
                    >
                      {(
                        markerLibrary[config.subject] ||
                        markerLibrary["Social Studies"] ||
                        []
                      ).map((marker, i) => (
                        <span
                          key={i}
                          style={{
                            padding: "6px 12px",
                            background: "var(--btn-secondary-bg)",
                            borderRadius: "6px",
                            fontSize: "0.85rem",
                            cursor: "pointer",
                          }}
                          onClick={() => {
                            if (
                              !(assignment.customMarkers || []).includes(marker)
                            ) {
                              setAssignment({
                                ...assignment,
                                customMarkers: [
                                  ...(assignment.customMarkers || []),
                                  marker,
                                ],
                              });
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
                  <div style={{ marginBottom: "25px" }}>
                    <label className="label">
                      Assignment-Specific Grading Notes
                    </label>
                    <textarea
                      className="input"
                      value={assignment.gradingNotes}
                      onChange={(e) =>
                        setAssignment({
                          ...assignment,
                          gradingNotes: e.target.value,
                        })
                      }
                      placeholder="Special instructions for grading this assignment..."
                      style={{ minHeight: "100px" }}
                    />
                  </div>

                  {/* Questions */}
                  <div style={{ marginBottom: "20px" }}>
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        marginBottom: "15px",
                      }}
                    >
                      <h3 style={{ fontSize: "1rem", fontWeight: 600 }}>
                        Questions ({assignment.questions.length}) -{" "}
                        {assignment.questions.reduce(
                          (sum, q) => sum + (q.points || 0),
                          0,
                        )}{" "}
                        pts
                      </h3>
                      <button onClick={addQuestion} className="btn btn-primary">
                        <Icon name="Plus" size={16} /> Add Question
                      </button>
                    </div>

                    {assignment.questions.length === 0 ? (
                      <div
                        style={{
                          textAlign: "center",
                          padding: "40px",
                          background: "var(--input-bg)",
                          borderRadius: "12px",
                          color: "var(--text-muted)",
                        }}
                      >
                        <Icon name="FileQuestion" size={40} />
                        <p style={{ marginTop: "10px" }}>
                          No questions yet. Click "Add Question" to start
                          building.
                        </p>
                      </div>
                    ) : (
                      <div
                        style={{
                          display: "flex",
                          flexDirection: "column",
                          gap: "15px",
                        }}
                      >
                        {assignment.questions.map((q, i) => (
                          <div
                            key={q.id}
                            style={{
                              background: "var(--glass-bg)",
                              borderRadius: "12px",
                              border: "1px solid var(--glass-border)",
                              padding: "20px",
                            }}
                          >
                            <div
                              style={{
                                display: "flex",
                                justifyContent: "space-between",
                                alignItems: "center",
                                marginBottom: "15px",
                              }}
                            >
                              <span
                                style={{
                                  fontSize: "0.9rem",
                                  fontWeight: 600,
                                  color: "#a5b4fc",
                                }}
                              >
                                Question {i + 1}
                              </span>
                              <button
                                onClick={() => removeQuestion(i)}
                                style={{
                                  padding: "6px 10px",
                                  borderRadius: "6px",
                                  border: "none",
                                  background: "rgba(248,113,113,0.2)",
                                  color: "#f87171",
                                  cursor: "pointer",
                                }}
                              >
                                <Icon name="Trash2" size={14} />
                              </button>
                            </div>
                            <div
                              style={{
                                display: "grid",
                                gridTemplateColumns: "1fr 150px 100px",
                                gap: "12px",
                                marginBottom: "12px",
                              }}
                            >
                              <div>
                                <label
                                  className="label"
                                  style={{ fontSize: "0.8rem" }}
                                >
                                  Marker
                                </label>
                                <select
                                  className="input"
                                  value={q.marker}
                                  onChange={(e) =>
                                    updateQuestion(i, "marker", e.target.value)
                                  }
                                >
                                  {(
                                    markerLibrary[assignment.subject] ||
                                    markerLibrary["Other"]
                                  ).map((m) => (
                                    <option key={m} value={m}>
                                      {m}
                                    </option>
                                  ))}
                                </select>
                              </div>
                              <div>
                                <label
                                  className="label"
                                  style={{ fontSize: "0.8rem" }}
                                >
                                  Type
                                </label>
                                <select
                                  className="input"
                                  value={q.type}
                                  onChange={(e) =>
                                    updateQuestion(i, "type", e.target.value)
                                  }
                                >
                                  <option value="short_answer">
                                    Short Answer
                                  </option>
                                  <option value="essay">Essay</option>
                                  <option value="fill_blank">
                                    Fill in Blank
                                  </option>
                                  <option value="multiple_choice">
                                    Multiple Choice
                                  </option>
                                </select>
                              </div>
                              <div>
                                <label
                                  className="label"
                                  style={{ fontSize: "0.8rem" }}
                                >
                                  Points
                                </label>
                                <input
                                  type="number"
                                  className="input"
                                  value={q.points}
                                  onChange={(e) =>
                                    updateQuestion(
                                      i,
                                      "points",
                                      parseInt(e.target.value) || 0,
                                    )
                                  }
                                  min="0"
                                />
                              </div>
                            </div>
                            <div>
                              <label
                                className="label"
                                style={{ fontSize: "0.8rem" }}
                              >
                                Question/Prompt
                              </label>
                              <textarea
                                className="input"
                                value={q.prompt}
                                onChange={(e) =>
                                  updateQuestion(i, "prompt", e.target.value)
                                }
                                placeholder="Enter the question..."
                                style={{ minHeight: "60px" }}
                              />
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Export Buttons */}
                  <div
                    style={{ display: "flex", gap: "15px", flexWrap: "wrap" }}
                  >
                    <button
                      onClick={saveAssignmentConfig}
                      disabled={!assignment.title}
                      className="btn btn-primary"
                      style={{ opacity: !assignment.title ? 0.5 : 1 }}
                    >
                      <Icon name="Save" size={18} /> Save for Grading
                    </button>
                    <button
                      onClick={() => exportAssignment("docx")}
                      disabled={!assignment.title}
                      className="btn btn-secondary"
                      style={{ opacity: !assignment.title ? 0.5 : 1 }}
                    >
                      <Icon name="FileText" size={18} /> Export Word Doc
                    </button>
                    <button
                      onClick={() => exportAssignment("pdf")}
                      disabled={!assignment.title}
                      className="btn btn-secondary"
                      style={{ opacity: !assignment.title ? 0.5 : 1 }}
                    >
                      <Icon name="FileType" size={18} /> Export PDF
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Analytics Tab */}
            {activeTab === "analytics" && (
              <div className="fade-in">
                {!analytics || analytics.error ? (
                  <div
                    className="glass-card"
                    style={{ padding: "60px", textAlign: "center" }}
                  >
                    <Icon name="BarChart3" size={64} />
                    <h2 style={{ marginTop: "20px", fontSize: "1.5rem" }}>
                      No Data Yet
                    </h2>
                    <p
                      style={{
                        color: "var(--text-secondary)",
                        marginTop: "10px",
                      }}
                    >
                      Grade some assignments to see analytics here.
                    </p>
                  </div>
                ) : (
                  <>
                    {/* Period Filter */}
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        marginBottom: "20px",
                      }}
                    >
                      <h2
                        style={{
                          fontSize: "1.3rem",
                          fontWeight: 700,
                          display: "flex",
                          alignItems: "center",
                          gap: "10px",
                        }}
                      >
                        <Icon name="BarChart3" size={24} />
                        Class Analytics
                      </h2>
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "10px",
                        }}
                      >
                        <label
                          style={{
                            fontSize: "0.9rem",
                            color: "var(--text-secondary)",
                          }}
                        >
                          Filter by Period:
                        </label>
                        <select
                          value={analyticsPeriod}
                          onChange={(e) => setAnalyticsPeriod(e.target.value)}
                          className="input"
                          style={{ width: "auto" }}
                        >
                          <option value="all">All Periods</option>
                          {(analytics.available_periods || []).map((p) => (
                            <option key={p} value={p}>
                              {p}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>

                    {/* Stats Cards */}
                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(4, 1fr)",
                        gap: "15px",
                        marginBottom: "20px",
                      }}
                    >
                      {[
                        {
                          label: "Total Graded",
                          value: analytics.class_stats?.total_assignments || 0,
                          icon: "FileCheck",
                          color: "#6366f1",
                        },
                        {
                          label: "Students",
                          value: analytics.class_stats?.total_students || 0,
                          icon: "Users",
                          color: "#8b5cf6",
                        },
                        {
                          label: "Class Average",
                          value: `${analytics.class_stats?.class_average || 0}%`,
                          icon: "TrendingUp",
                          color: "#10b981",
                        },
                        {
                          label: "Highest Score",
                          value: `${analytics.class_stats?.highest || 0}%`,
                          icon: "Trophy",
                          color: "#f59e0b",
                        },
                      ].map((stat, i) => (
                        <div
                          key={i}
                          className="glass-card"
                          style={{ padding: "20px" }}
                        >
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "10px",
                              marginBottom: "10px",
                            }}
                          >
                            <div
                              style={{
                                background: `${stat.color}20`,
                                padding: "8px",
                                borderRadius: "10px",
                              }}
                            >
                              <Icon name={stat.icon} size={20} />
                            </div>
                            <span
                              style={{
                                color: "var(--text-secondary)",
                                fontSize: "0.9rem",
                              }}
                            >
                              {stat.label}
                            </span>
                          </div>
                          <div
                            style={{
                              fontSize: "2rem",
                              fontWeight: 800,
                              color: stat.color,
                            }}
                          >
                            {stat.value}
                          </div>
                        </div>
                      ))}
                    </div>

                    {/* Charts */}
                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "1fr 2fr",
                        gap: "20px",
                        marginBottom: "20px",
                      }}
                    >
                      <div className="glass-card" style={{ padding: "25px" }}>
                        <h3
                          style={{
                            fontSize: "1.1rem",
                            fontWeight: 700,
                            marginBottom: "20px",
                            display: "flex",
                            alignItems: "center",
                            gap: "10px",
                          }}
                        >
                          <Icon name="PieChart" size={20} />
                          Grade Distribution
                        </h3>
                        <ResponsiveContainer width="100%" height={200}>
                          <PieChart>
                            <Pie
                              data={[
                                {
                                  name: "A",
                                  value:
                                    analytics.class_stats?.grade_distribution
                                      ?.A || 0,
                                },
                                {
                                  name: "B",
                                  value:
                                    analytics.class_stats?.grade_distribution
                                      ?.B || 0,
                                },
                                {
                                  name: "C",
                                  value:
                                    analytics.class_stats?.grade_distribution
                                      ?.C || 0,
                                },
                                {
                                  name: "D",
                                  value:
                                    analytics.class_stats?.grade_distribution
                                      ?.D || 0,
                                },
                                {
                                  name: "F",
                                  value:
                                    analytics.class_stats?.grade_distribution
                                      ?.F || 0,
                                },
                              ].filter((d) => d.value > 0)}
                              cx="50%"
                              cy="50%"
                              outerRadius={70}
                              dataKey="value"
                              label={({ name, value }) => `${name}: ${value}`}
                            >
                              {[
                                "#4ade80",
                                "#60a5fa",
                                "#fbbf24",
                                "#f97316",
                                "#ef4444",
                              ].map((c, i) => (
                                <Cell key={i} fill={c} />
                              ))}
                            </Pie>
                            <Tooltip />
                          </PieChart>
                        </ResponsiveContainer>
                      </div>

                      <div className="glass-card" style={{ padding: "25px" }}>
                        <h3
                          style={{
                            fontSize: "1.1rem",
                            fontWeight: 700,
                            marginBottom: "20px",
                            display: "flex",
                            alignItems: "center",
                            gap: "10px",
                          }}
                        >
                          <Icon name="BarChart3" size={20} />
                          Assignment Averages
                        </h3>
                        <ResponsiveContainer width="100%" height={200}>
                          <BarChart data={analytics.assignment_stats || []}>
                            <CartesianGrid
                              strokeDasharray="3 3"
                              stroke="var(--glass-border)"
                            />
                            <XAxis
                              dataKey="name"
                              tick={{
                                fill: "var(--text-secondary)",
                                fontSize: 11,
                              }}
                            />
                            <YAxis
                              domain={[0, 100]}
                              tick={{ fill: "var(--text-secondary)" }}
                            />
                            <Tooltip
                              contentStyle={{
                                background: "var(--modal-content-bg)",
                                border: "1px solid var(--glass-border)",
                                borderRadius: "8px",
                              }}
                            />
                            <Bar
                              dataKey="average"
                              fill="#6366f1"
                              radius={[4, 4, 0, 0]}
                            />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </div>

                    {/* Student Progress */}
                    <div
                      className="glass-card"
                      style={{
                        padding: "25px",
                        marginBottom: "20px",
                        border: selectedStudent
                          ? "2px solid #6366f1"
                          : undefined,
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          marginBottom: "15px",
                        }}
                      >
                        <h3
                          style={{
                            fontSize: "1.1rem",
                            fontWeight: 700,
                            display: "flex",
                            alignItems: "center",
                            gap: "10px",
                          }}
                        >
                          <Icon name="TrendingUp" size={20} />
                          {selectedStudent
                            ? `${selectedStudent}'s Progress`
                            : "Student Progress Over Time"}
                        </h3>
                        {selectedStudent && (
                          <button
                            onClick={() => setSelectedStudent(null)}
                            className="btn btn-secondary"
                            style={{ padding: "6px 12px" }}
                          >
                            <Icon name="X" size={14} /> Clear Selection
                          </button>
                        )}
                      </div>

                      {selectedStudent &&
                        (() => {
                          const studentData = (
                            analytics.student_progress || []
                          ).find((s) => s.name === selectedStudent);
                          if (!studentData) return null;
                          const grades = studentData.grades || [];
                          const highest =
                            grades.length > 0
                              ? Math.max(...grades.map((g) => g.score))
                              : 0;
                          const lowest =
                            grades.length > 0
                              ? Math.min(...grades.map((g) => g.score))
                              : 0;
                          return (
                            <div
                              style={{
                                display: "grid",
                                gridTemplateColumns: "repeat(4, 1fr)",
                                gap: "15px",
                                marginBottom: "20px",
                              }}
                            >
                              <div
                                style={{
                                  background: "rgba(99,102,241,0.1)",
                                  borderRadius: "12px",
                                  padding: "15px",
                                  textAlign: "center",
                                }}
                              >
                                <div
                                  style={{
                                    fontSize: "0.8rem",
                                    color: "var(--text-secondary)",
                                    marginBottom: "5px",
                                  }}
                                >
                                  Average
                                </div>
                                <div
                                  style={{
                                    fontSize: "1.5rem",
                                    fontWeight: 700,
                                    color: "#6366f1",
                                  }}
                                >
                                  {studentData.average}%
                                </div>
                              </div>
                              <div
                                style={{
                                  background: "rgba(74,222,128,0.1)",
                                  borderRadius: "12px",
                                  padding: "15px",
                                  textAlign: "center",
                                }}
                              >
                                <div
                                  style={{
                                    fontSize: "0.8rem",
                                    color: "var(--text-secondary)",
                                    marginBottom: "5px",
                                  }}
                                >
                                  Highest
                                </div>
                                <div
                                  style={{
                                    fontSize: "1.5rem",
                                    fontWeight: 700,
                                    color: "#4ade80",
                                  }}
                                >
                                  {highest}%
                                </div>
                              </div>
                              <div
                                style={{
                                  background: "rgba(248,113,113,0.1)",
                                  borderRadius: "12px",
                                  padding: "15px",
                                  textAlign: "center",
                                }}
                              >
                                <div
                                  style={{
                                    fontSize: "0.8rem",
                                    color: "var(--text-secondary)",
                                    marginBottom: "5px",
                                  }}
                                >
                                  Lowest
                                </div>
                                <div
                                  style={{
                                    fontSize: "1.5rem",
                                    fontWeight: 700,
                                    color: "#f87171",
                                  }}
                                >
                                  {lowest}%
                                </div>
                              </div>
                              <div
                                style={{
                                  background: "rgba(251,191,36,0.1)",
                                  borderRadius: "12px",
                                  padding: "15px",
                                  textAlign: "center",
                                }}
                              >
                                <div
                                  style={{
                                    fontSize: "0.8rem",
                                    color: "var(--text-secondary)",
                                    marginBottom: "5px",
                                  }}
                                >
                                  Assignments
                                </div>
                                <div
                                  style={{
                                    fontSize: "1.5rem",
                                    fontWeight: 700,
                                    color: "#fbbf24",
                                  }}
                                >
                                  {grades.length}
                                </div>
                              </div>
                            </div>
                          );
                        })()}

                      {!selectedStudent && (
                        <p
                          style={{
                            fontSize: "0.85rem",
                            color: "var(--text-secondary)",
                            marginBottom: "15px",
                          }}
                        >
                          Click a student name below to view details
                        </p>
                      )}

                      <ResponsiveContainer width="100%" height={250}>
                        <LineChart
                          data={(() => {
                            const filtered = selectedStudent
                              ? (analytics.student_progress || []).filter(
                                  (s) => s.name === selectedStudent,
                                )
                              : analytics.student_progress || [];
                            const allGrades = filtered.flatMap((s) =>
                              (s.grades || []).map((g) => ({
                                ...g,
                                student: s.name.split(" ")[0],
                              })),
                            );
                            return allGrades.sort((a, b) =>
                              (a.date || "").localeCompare(b.date || ""),
                            );
                          })()}
                        >
                          <CartesianGrid
                            strokeDasharray="3 3"
                            stroke="var(--glass-border)"
                          />
                          <XAxis
                            dataKey="assignment"
                            tick={{
                              fill: "var(--text-secondary)",
                              fontSize: 10,
                            }}
                            angle={-20}
                            textAnchor="end"
                            height={60}
                          />
                          <YAxis
                            domain={[0, 100]}
                            tick={{ fill: "var(--text-secondary)" }}
                          />
                          <Tooltip
                            contentStyle={{
                              background: "var(--modal-content-bg)",
                              border: "1px solid var(--glass-border)",
                              borderRadius: "8px",
                            }}
                          />
                          <Line
                            type="monotone"
                            dataKey="score"
                            stroke="#6366f1"
                            strokeWidth={3}
                            dot={{ fill: "#6366f1", r: 5 }}
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>

                    {/* Needs Attention + Top Performers */}
                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "1fr 1fr",
                        gap: "20px",
                        marginBottom: "20px",
                      }}
                    >
                      <div
                        style={{
                          background: "rgba(239,68,68,0.1)",
                          borderRadius: "20px",
                          border: "1px solid rgba(239,68,68,0.3)",
                          padding: "25px",
                        }}
                      >
                        <h3
                          style={{
                            fontSize: "1.1rem",
                            fontWeight: 700,
                            marginBottom: "15px",
                            display: "flex",
                            alignItems: "center",
                            gap: "10px",
                            color: "#f87171",
                          }}
                        >
                          <Icon name="AlertTriangle" size={20} />
                          Needs Attention
                        </h3>
                        {(analytics.attention_needed || []).length === 0 ? (
                          <p style={{ color: "var(--text-secondary)" }}>
                            All students are doing well!
                          </p>
                        ) : (
                          <div
                            style={{
                              display: "flex",
                              flexDirection: "column",
                              gap: "10px",
                            }}
                          >
                            {(analytics.attention_needed || [])
                              .slice(0, 5)
                              .map((s, i) => (
                                <div
                                  key={i}
                                  onClick={() => setSelectedStudent(s.name)}
                                  style={{
                                    display: "flex",
                                    justifyContent: "space-between",
                                    alignItems: "center",
                                    padding: "10px 15px",
                                    background: "var(--input-bg)",
                                    borderRadius: "10px",
                                    cursor: "pointer",
                                  }}
                                >
                                  <span
                                    style={{
                                      textDecoration: "underline dotted",
                                    }}
                                  >
                                    {s.name}
                                  </span>
                                  <div
                                    style={{
                                      display: "flex",
                                      alignItems: "center",
                                      gap: "10px",
                                    }}
                                  >
                                    <span
                                      style={{
                                        color: "#f87171",
                                        fontWeight: 700,
                                      }}
                                    >
                                      {s.average}%
                                    </span>
                                    <span
                                      style={{
                                        fontSize: "0.8rem",
                                        padding: "2px 8px",
                                        borderRadius: "4px",
                                        background:
                                          s.trend === "declining"
                                            ? "rgba(239,68,68,0.3)"
                                            : "rgba(251,191,36,0.3)",
                                        color:
                                          s.trend === "declining"
                                            ? "#f87171"
                                            : "#fbbf24",
                                      }}
                                    >
                                      {s.trend}
                                    </span>
                                  </div>
                                </div>
                              ))}
                          </div>
                        )}
                      </div>

                      <div
                        style={{
                          background: "rgba(74,222,128,0.1)",
                          borderRadius: "20px",
                          border: "1px solid rgba(74,222,128,0.3)",
                          padding: "25px",
                        }}
                      >
                        <h3
                          style={{
                            fontSize: "1.1rem",
                            fontWeight: 700,
                            marginBottom: "15px",
                            display: "flex",
                            alignItems: "center",
                            gap: "10px",
                            color: "#4ade80",
                          }}
                        >
                          <Icon name="Award" size={20} />
                          Top Performers
                        </h3>
                        <div
                          style={{
                            display: "flex",
                            flexDirection: "column",
                            gap: "10px",
                          }}
                        >
                          {(analytics.top_performers || []).map((s, i) => (
                            <div
                              key={i}
                              onClick={() => setSelectedStudent(s.name)}
                              style={{
                                display: "flex",
                                justifyContent: "space-between",
                                alignItems: "center",
                                padding: "10px 15px",
                                background: "var(--input-bg)",
                                borderRadius: "10px",
                                cursor: "pointer",
                              }}
                            >
                              <div
                                style={{
                                  display: "flex",
                                  alignItems: "center",
                                  gap: "10px",
                                }}
                              >
                                <span
                                  style={{
                                    width: "24px",
                                    height: "24px",
                                    borderRadius: "50%",
                                    background:
                                      i === 0
                                        ? "#fbbf24"
                                        : i === 1
                                          ? "#94a3b8"
                                          : i === 2
                                            ? "#cd7f32"
                                            : "var(--glass-border)",
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                    fontSize: "0.75rem",
                                    fontWeight: 700,
                                  }}
                                >
                                  {i + 1}
                                </span>
                                <span
                                  style={{ textDecoration: "underline dotted" }}
                                >
                                  {s.name}
                                </span>
                              </div>
                              <span
                                style={{ color: "#4ade80", fontWeight: 700 }}
                              >
                                {s.average}%
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>

                    {/* All Students Table */}
                    <div className="glass-card" style={{ padding: "25px" }}>
                      <h3
                        style={{
                          fontSize: "1.1rem",
                          fontWeight: 700,
                          marginBottom: "15px",
                          display: "flex",
                          alignItems: "center",
                          gap: "10px",
                        }}
                      >
                        <Icon name="Users" size={20} />
                        All Students Overview
                      </h3>
                      <table>
                        <thead>
                          <tr>
                            <th>Student</th>
                            <th style={{ textAlign: "center" }}>Assignments</th>
                            <th style={{ textAlign: "center" }}>Average</th>
                            <th style={{ textAlign: "center" }}>Trend</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(analytics.student_progress || []).map((s, i) => (
                            <tr
                              key={i}
                              onClick={() => setSelectedStudent(s.name)}
                              style={{
                                cursor: "pointer",
                                background:
                                  selectedStudent === s.name
                                    ? "rgba(99,102,241,0.2)"
                                    : "transparent",
                              }}
                            >
                              <td
                                style={{
                                  fontWeight: 600,
                                  textDecoration: "underline dotted",
                                }}
                              >
                                {s.name}
                              </td>
                              <td style={{ textAlign: "center" }}>
                                {(s.grades || []).length}
                              </td>
                              <td style={{ textAlign: "center" }}>
                                <span
                                  style={{
                                    padding: "4px 12px",
                                    borderRadius: "20px",
                                    fontWeight: 700,
                                    background:
                                      s.average >= 90
                                        ? "rgba(74,222,128,0.2)"
                                        : s.average >= 80
                                          ? "rgba(96,165,250,0.2)"
                                          : s.average >= 70
                                            ? "rgba(251,191,36,0.2)"
                                            : "rgba(248,113,113,0.2)",
                                    color:
                                      s.average >= 90
                                        ? "#4ade80"
                                        : s.average >= 80
                                          ? "#60a5fa"
                                          : s.average >= 70
                                            ? "#fbbf24"
                                            : "#f87171",
                                  }}
                                >
                                  {s.average}%
                                </span>
                              </td>
                              <td style={{ textAlign: "center" }}>
                                <span
                                  style={{
                                    display: "inline-flex",
                                    alignItems: "center",
                                    gap: "4px",
                                    color:
                                      s.trend === "improving"
                                        ? "#4ade80"
                                        : s.trend === "declining"
                                          ? "#f87171"
                                          : "#94a3b8",
                                  }}
                                >
                                  <Icon
                                    name={
                                      s.trend === "improving"
                                        ? "TrendingUp"
                                        : s.trend === "declining"
                                          ? "TrendingDown"
                                          : "Minus"
                                    }
                                    size={16}
                                  />
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
            {activeTab === "planner" && (
              <div className="fade-in">
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "300px 1fr",
                    gap: "25px",
                  }}
                >
                  {/* Sidebar */}
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: "20px",
                    }}
                  >
                    {/* Unit Details */}
                    <div className="glass-card" style={{ padding: "20px" }}>
                      <h3
                        style={{
                          fontSize: "1.1rem",
                          fontWeight: 700,
                          marginBottom: "15px",
                          display: "flex",
                          alignItems: "center",
                          gap: "10px",
                        }}
                      >
                        <Icon name="FileText" size={20} /> Details
                      </h3>
                      <div
                        style={{
                          display: "flex",
                          flexDirection: "column",
                          gap: "15px",
                        }}
                      >
                        <div>
                          <label className="label">Content Type</label>
                          <select
                            className="input"
                            value={unitConfig.type}
                            onChange={(e) =>
                              setUnitConfig({
                                ...unitConfig,
                                type: e.target.value,
                              })
                            }
                          >
                            <option value="Unit Plan">Unit Plan</option>
                            <option value="Lesson Plan">Lesson Plan</option>
                            <option value="Assignment">Assignment</option>
                            <option value="Project">Project</option>
                          </select>
                        </div>
                        <div>
                          <label className="label">Title</label>
                          <input
                            type="text"
                            className="input"
                            value={unitConfig.title}
                            onChange={(e) =>
                              setUnitConfig({
                                ...unitConfig,
                                title: e.target.value,
                              })
                            }
                            placeholder="e.g., Foundations of Government"
                          />
                        </div>
                        <div
                          style={{
                            display: "grid",
                            gridTemplateColumns: "1fr 1fr",
                            gap: "12px",
                          }}
                        >
                          <div>
                            <label className="label">Duration (Days)</label>
                            <input
                              type="number"
                              className="input"
                              value={unitConfig.duration}
                              onChange={(e) =>
                                setUnitConfig({
                                  ...unitConfig,
                                  duration: parseInt(e.target.value) || 1,
                                })
                              }
                              min="1"
                              max="20"
                            />
                          </div>
                          <div>
                            <label className="label">Period Length</label>
                            <input
                              type="number"
                              className="input"
                              value={unitConfig.periodLength}
                              onChange={(e) =>
                                setUnitConfig({
                                  ...unitConfig,
                                  periodLength: parseInt(e.target.value) || 50,
                                })
                              }
                              min="20"
                              max="120"
                            />
                          </div>
                        </div>
                        <div>
                          <label className="label">
                            Additional Requirements
                          </label>
                          <textarea
                            className="input"
                            value={unitConfig.requirements}
                            onChange={(e) =>
                              setUnitConfig({
                                ...unitConfig,
                                requirements: e.target.value,
                              })
                            }
                            placeholder="e.g. Focus on primary sources..."
                            style={{ minHeight: "80px" }}
                          />
                        </div>
                        <button
                          onClick={generateLessonPlan}
                          disabled={
                            plannerLoading || selectedStandards.length === 0
                          }
                          className="btn btn-primary"
                          style={{
                            width: "100%",
                            justifyContent: "center",
                            opacity:
                              plannerLoading || selectedStandards.length === 0
                                ? 0.5
                                : 1,
                          }}
                        >
                          {plannerLoading ? (
                            <Icon
                              name="Loader2"
                              size={18}
                              style={{ animation: "spin 1s linear infinite" }}
                            />
                          ) : (
                            <Icon name="Sparkles" size={18} />
                          )}
                          {plannerLoading ? "Generating..." : "Generate Plan"}
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Main Content */}
                  <div>
                    {lessonPlan ? (
                      <div
                        className="glass-card"
                        style={{
                          padding: "30px",
                          maxHeight: "80vh",
                          overflowY: "auto",
                        }}
                      >
                        {/* Header */}
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "flex-start",
                            marginBottom: "25px",
                            borderBottom: "1px solid var(--glass-border)",
                            paddingBottom: "20px",
                          }}
                        >
                          <div>
                            <h2
                              style={{
                                fontSize: "1.8rem",
                                fontWeight: 700,
                                marginBottom: "10px",
                              }}
                            >
                              {lessonPlan.title}
                            </h2>
                            <p
                              style={{
                                color: "var(--text-secondary)",
                                lineHeight: "1.6",
                              }}
                            >
                              {lessonPlan.overview}
                            </p>
                          </div>
                          <div style={{ display: "flex", gap: "10px" }}>
                            <button
                              onClick={exportLessonPlanHandler}
                              className="btn btn-secondary"
                            >
                              <Icon name="Download" size={16} /> Export
                            </button>
                            <button
                              onClick={() => setLessonPlan(null)}
                              className="btn btn-secondary"
                            >
                              Close
                            </button>
                          </div>
                        </div>

                        {/* Days */}
                        <div
                          style={{
                            display: "flex",
                            flexDirection: "column",
                            gap: "30px",
                          }}
                        >
                          {(lessonPlan.days || []).map((day, i) => (
                            <div
                              key={i}
                              style={{
                                background: "var(--input-bg)",
                                borderRadius: "16px",
                                padding: "25px",
                              }}
                            >
                              <div
                                style={{
                                  display: "flex",
                                  alignItems: "flex-start",
                                  gap: "15px",
                                  marginBottom: "20px",
                                  paddingBottom: "15px",
                                  borderBottom:
                                    "1px solid var(--glass-border)",
                                }}
                              >
                                <div
                                  style={{
                                    width: "50px",
                                    height: "50px",
                                    borderRadius: "12px",
                                    background:
                                      "linear-gradient(135deg, #6366f1, #8b5cf6)",
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                    fontWeight: 700,
                                    fontSize: "1.2rem",
                                  }}
                                >
                                  {day.day}
                                </div>
                                <div style={{ flex: 1 }}>
                                  <h3
                                    style={{
                                      fontSize: "1.3rem",
                                      fontWeight: 600,
                                      marginBottom: "8px",
                                    }}
                                  >
                                    {day.topic}
                                  </h3>
                                  <p
                                    style={{
                                      fontSize: "0.9rem",
                                      color: "var(--text-primary)",
                                    }}
                                  >
                                    <strong style={{ color: "#10b981" }}>
                                      Objective:
                                    </strong>{" "}
                                    {day.objective}
                                  </p>
                                </div>
                              </div>

                              {day.bell_ringer && (
                                <div
                                  style={{
                                    marginBottom: "15px",
                                    padding: "15px",
                                    background: "rgba(165,180,252,0.1)",
                                    borderRadius: "10px",
                                    border: "1px solid rgba(165,180,252,0.2)",
                                  }}
                                >
                                  <h4
                                    style={{
                                      fontSize: "0.9rem",
                                      color: "#a5b4fc",
                                      marginBottom: "8px",
                                    }}
                                  >
                                    <Icon name="Zap" size={14} /> Bell Ringer
                                  </h4>
                                  <p style={{ fontSize: "0.9rem" }}>
                                    {typeof day.bell_ringer === "object"
                                      ? day.bell_ringer.prompt
                                      : day.bell_ringer}
                                  </p>
                                </div>
                              )}

                              {day.activity && (
                                <div
                                  style={{
                                    marginBottom: "15px",
                                    padding: "15px",
                                    background: "rgba(74,222,128,0.1)",
                                    borderRadius: "10px",
                                    border: "1px solid rgba(74,222,128,0.2)",
                                  }}
                                >
                                  <h4
                                    style={{
                                      fontSize: "0.9rem",
                                      color: "#4ade80",
                                      marginBottom: "8px",
                                    }}
                                  >
                                    <Icon name="Activity" size={14} /> Main
                                    Activity
                                  </h4>
                                  <p style={{ fontSize: "0.9rem" }}>
                                    {typeof day.activity === "object"
                                      ? day.activity.description
                                      : day.activity}
                                  </p>
                                </div>
                              )}

                              {day.assessment && (
                                <div
                                  style={{
                                    padding: "15px",
                                    background: "rgba(248,113,113,0.1)",
                                    borderRadius: "10px",
                                    border: "1px solid rgba(248,113,113,0.2)",
                                  }}
                                >
                                  <h4
                                    style={{
                                      fontSize: "0.9rem",
                                      color: "#f87171",
                                      marginBottom: "8px",
                                    }}
                                  >
                                    <Icon name="CheckCircle" size={14} />{" "}
                                    Assessment
                                  </h4>
                                  <p style={{ fontSize: "0.9rem" }}>
                                    {typeof day.assessment === "object"
                                      ? day.assessment.description
                                      : day.assessment}
                                  </p>
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : (
                      <div className="glass-card" style={{ padding: "25px" }}>
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                            marginBottom: "15px",
                          }}
                        >
                          <h3
                            style={{
                              fontSize: "1.1rem",
                              fontWeight: 700,
                              display: "flex",
                              alignItems: "center",
                              gap: "10px",
                            }}
                          >
                            <Icon name="Library" size={20} /> Select Standards (
                            {selectedStandards.length})
                          </h3>
                          <span
                            style={{
                              fontSize: "0.9rem",
                              color: "var(--text-secondary)",
                            }}
                          >
                            {standards.length} standards available
                          </span>
                        </div>

                        {/* Current config display */}
                        <div
                          style={{
                            display: "flex",
                            gap: "10px",
                            marginBottom: "15px",
                            flexWrap: "wrap",
                          }}
                        >
                          <span
                            style={{
                              padding: "6px 12px",
                              borderRadius: "20px",
                              background: "rgba(99,102,241,0.15)",
                              color: "var(--accent-light)",
                              fontSize: "0.85rem",
                              fontWeight: 500,
                            }}
                          >
                            <Icon name="MapPin" size={14} style={{ marginRight: "6px", verticalAlign: "middle" }} />
                            {{FL: "Florida", TX: "Texas", CA: "California", NY: "New York", GA: "Georgia", NC: "North Carolina", VA: "Virginia", OH: "Ohio", PA: "Pennsylvania", IL: "Illinois"}[config.state] || config.state}
                          </span>
                          <span
                            style={{
                              padding: "6px 12px",
                              borderRadius: "20px",
                              background: "rgba(74,222,128,0.15)",
                              color: "#4ade80",
                              fontSize: "0.85rem",
                              fontWeight: 500,
                            }}
                          >
                            <Icon name="GraduationCap" size={14} style={{ marginRight: "6px", verticalAlign: "middle" }} />
                            Grade {config.grade_level}
                          </span>
                          <span
                            style={{
                              padding: "6px 12px",
                              borderRadius: "20px",
                              background: "rgba(251,191,36,0.15)",
                              color: "#fbbf24",
                              fontSize: "0.85rem",
                              fontWeight: 500,
                            }}
                          >
                            <Icon name="BookOpen" size={14} style={{ marginRight: "6px", verticalAlign: "middle" }} />
                            {config.subject}
                          </span>
                        </div>

                        <div style={{ maxHeight: "500px", overflowY: "auto" }}>
                          {plannerLoading ? (
                            <div
                              style={{
                                textAlign: "center",
                                padding: "40px",
                                color: "var(--text-secondary)",
                              }}
                            >
                              <Icon
                                name="Loader2"
                                size={30}
                                style={{ animation: "spin 1s linear infinite" }}
                              />
                              <p style={{ marginTop: "10px" }}>
                                Loading standards...
                              </p>
                            </div>
                          ) : standards.length > 0 ? (
                            standards.map((std) => (
                              <StandardCard
                                key={std.code}
                                standard={std}
                                isSelected={selectedStandards.includes(
                                  std.code,
                                )}
                                onToggle={() => toggleStandard(std.code)}
                              />
                            ))
                          ) : (
                            <div
                              style={{
                                textAlign: "center",
                                padding: "40px",
                                background: "var(--glass-bg)",
                                borderRadius: "12px",
                              }}
                            >
                              <p style={{ color: "var(--text-secondary)" }}>
                                No standards found for this configuration.
                              </p>
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
          </div>
        </div>
      </div>

      {/* Toast Notifications */}
      <div
        style={{
          position: "fixed",
          bottom: "20px",
          right: "20px",
          zIndex: 9999,
          display: "flex",
          flexDirection: "column",
          gap: "10px",
          maxWidth: "350px",
        }}
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className="glass-card fade-in"
            style={{
              padding: "12px 16px",
              display: "flex",
              alignItems: "center",
              gap: "10px",
              background:
                toast.type === "success"
                  ? "rgba(74,222,128,0.15)"
                  : toast.type === "warning"
                  ? "rgba(251,191,36,0.15)"
                  : toast.type === "error"
                  ? "rgba(248,113,113,0.15)"
                  : "rgba(96,165,250,0.15)",
              border: `1px solid ${
                toast.type === "success"
                  ? "rgba(74,222,128,0.4)"
                  : toast.type === "warning"
                  ? "rgba(251,191,36,0.4)"
                  : toast.type === "error"
                  ? "rgba(248,113,113,0.4)"
                  : "rgba(96,165,250,0.4)"
              }`,
              boxShadow: "0 4px 20px rgba(0,0,0,0.3)",
            }}
          >
            <Icon
              name={
                toast.type === "success"
                  ? "CheckCircle"
                  : toast.type === "warning"
                  ? "AlertTriangle"
                  : toast.type === "error"
                  ? "XCircle"
                  : "Info"
              }
              size={18}
              style={{
                color:
                  toast.type === "success"
                    ? "#4ade80"
                    : toast.type === "warning"
                    ? "#fbbf24"
                    : toast.type === "error"
                    ? "#f87171"
                    : "#60a5fa",
                flexShrink: 0,
              }}
            />
            <span
              style={{
                fontSize: "0.9rem",
                color: "var(--text-primary)",
                flex: 1,
              }}
            >
              {toast.message}
            </span>
            <button
              onClick={() => setToasts((prev) => prev.filter((t) => t.id !== toast.id))}
              style={{
                background: "none",
                border: "none",
                cursor: "pointer",
                padding: "2px",
                color: "var(--text-muted)",
                flexShrink: 0,
              }}
            >
              <Icon name="X" size={14} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

export default App;
