import { useState, useEffect, useRef, useMemo } from "react";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  ScatterChart,
  Scatter,
  Cell,
  XAxis,
  YAxis,
  ZAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  ReferenceLine,
} from "recharts";
import Icon from "./components/Icon";
import { AssignmentPlayer } from "./components";
import StudentPortal from "./components/StudentPortal";
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

// Assignment templates with section-based point values
const ASSIGNMENT_TEMPLATES = {
  "Cornell Notes": {
    markers: [
      { start: "Questions/Terms", points: 40, type: "fill-blank", description: "Fill-in-the-blank and short answers" },
      { start: "Summary (Bottom Section)", points: 20, type: "written", description: "3-4 sentence summary" },
      { start: "Vocabulary", points: 25, type: "vocabulary", description: "Vocabulary definitions" },
    ],
    effortPoints: 15,
    description: "Standard Cornell Notes format with summary section"
  },
  "Worksheet - Fill-in-Blank Heavy": {
    markers: [
      { start: "Fill-in-the-blank", points: 50, type: "fill-blank", description: "Fill-in-the-blank questions" },
      { start: "Short Answer", points: 35, type: "written", description: "Written response questions" },
    ],
    effortPoints: 15,
    description: "Worksheet with mostly fill-in-the-blank"
  },
  "Worksheet - Written Heavy": {
    markers: [
      { start: "Questions", points: 30, type: "fill-blank", description: "Fill-in-the-blank and factual questions" },
      { start: "Written Response", points: 40, type: "written", description: "Paragraph responses" },
      { start: "Reflection", points: 15, type: "written", description: "Personal reflection" },
    ],
    effortPoints: 15,
    description: "Worksheet emphasizing written responses"
  },
  "Essay": {
    markers: [
      { start: "Thesis/Introduction", points: 20, type: "written", description: "Opening paragraph with thesis" },
      { start: "Body Paragraphs", points: 45, type: "written", description: "Supporting arguments" },
      { start: "Conclusion", points: 20, type: "written", description: "Summary and closing" },
    ],
    effortPoints: 15,
    description: "Standard essay format"
  },
  "Custom": {
    markers: [
      { start: "Content", points: 85, type: "written", description: "Main assignment content" },
    ],
    effortPoints: 15,
    description: "Define your own sections and point values"
  }
};

// StandardCard component for Planner
function StandardCard({
  standard,
  isSelected,
  onToggle,
  isExpanded,
  onExpand,
}) {
  const dokColors = { 1: "#4ade80", 2: "#60a5fa", 3: "#f59e0b", 4: "#ef4444" };
  const dokLabels = {
    1: "Recall",
    2: "Skill/Concept",
    3: "Strategic Thinking",
    4: "Extended Thinking",
  };

  return (
    <div
      style={{
        background: isSelected ? "rgba(99,102,241,0.2)" : "var(--glass-bg)",
        border: isSelected
          ? "1px solid var(--accent-primary)"
          : "1px solid var(--glass-border)",
        borderRadius: "12px",
        padding: "15px",
        transition: "all 0.2s",
        marginBottom: "10px",
      }}
    >
      <div onClick={onToggle} style={{ cursor: "pointer" }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            marginBottom: "8px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <span
              style={{
                fontWeight: 700,
                color: isSelected
                  ? "var(--accent-light)"
                  : "var(--text-primary)",
                fontSize: "0.9rem",
              }}
            >
              {standard.code}
            </span>
            {standard.dok && (
              <span
                style={{
                  fontSize: "0.7rem",
                  padding: "2px 8px",
                  borderRadius: "10px",
                  background: dokColors[standard.dok] + "33",
                  color: dokColors[standard.dok],
                  fontWeight: 600,
                }}
                title={`Depth of Knowledge: ${dokLabels[standard.dok]}`}
              >
                DOK {standard.dok}
              </span>
            )}
          </div>
          {isSelected && (
            <Icon
              name="CheckCircle"
              size={18}
              style={{ color: "var(--accent-primary)" }}
            />
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
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "6px",
            alignItems: "center",
          }}
        >
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

      {/* Expand button */}
      {(standard.learning_targets ||
        standard.vocabulary ||
        standard.essential_questions) && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onExpand && onExpand();
          }}
          style={{
            marginTop: "10px",
            padding: "4px 10px",
            fontSize: "0.75rem",
            background: "transparent",
            border: "1px solid var(--glass-border)",
            borderRadius: "6px",
            color: "var(--text-secondary)",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: "4px",
          }}
        >
          <Icon name={isExpanded ? "ChevronUp" : "ChevronDown"} size={14} />
          {isExpanded ? "Hide Details" : "Show Details"}
        </button>
      )}

      {/* Expanded Details */}
      {isExpanded && (
        <div
          style={{
            marginTop: "15px",
            paddingTop: "15px",
            borderTop: "1px solid var(--glass-border)",
          }}
        >
          {/* Essential Questions */}
          {standard.essential_questions &&
            standard.essential_questions.length > 0 && (
              <div style={{ marginBottom: "12px" }}>
                <div
                  style={{
                    fontSize: "0.8rem",
                    fontWeight: 600,
                    color: "#8b5cf6",
                    marginBottom: "6px",
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                  }}
                >
                  <Icon name="HelpCircle" size={14} /> Essential Questions
                </div>
                {standard.essential_questions.map((q, i) => (
                  <p
                    key={i}
                    style={{
                      fontSize: "0.85rem",
                      color: "var(--text-secondary)",
                      margin: "4px 0",
                      paddingLeft: "20px",
                    }}
                  >
                    • {q}
                  </p>
                ))}
              </div>
            )}

          {/* Learning Targets */}
          {standard.learning_targets &&
            standard.learning_targets.length > 0 && (
              <div style={{ marginBottom: "12px" }}>
                <div
                  style={{
                    fontSize: "0.8rem",
                    fontWeight: 600,
                    color: "#10b981",
                    marginBottom: "6px",
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                  }}
                >
                  <Icon name="Target" size={14} /> Learning Targets
                </div>
                {standard.learning_targets.map((t, i) => (
                  <p
                    key={i}
                    style={{
                      fontSize: "0.85rem",
                      color: "var(--text-secondary)",
                      margin: "4px 0",
                      paddingLeft: "20px",
                    }}
                  >
                    • {t}
                  </p>
                ))}
              </div>
            )}

          {/* Vocabulary */}
          {standard.vocabulary && standard.vocabulary.length > 0 && (
            <div style={{ marginBottom: "12px" }}>
              <div
                style={{
                  fontSize: "0.8rem",
                  fontWeight: 600,
                  color: "#f59e0b",
                  marginBottom: "6px",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                }}
              >
                <Icon name="BookOpen" size={14} /> Key Vocabulary
              </div>
              <div
                style={{
                  display: "flex",
                  flexWrap: "wrap",
                  gap: "6px",
                  paddingLeft: "20px",
                }}
              >
                {standard.vocabulary.map((v, i) => (
                  <span
                    key={i}
                    style={{
                      fontSize: "0.8rem",
                      padding: "3px 10px",
                      borderRadius: "12px",
                      background: "rgba(245,158,11,0.15)",
                      color: "#f59e0b",
                    }}
                  >
                    {v}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Item Specifications */}
          {standard.item_specs && (
            <div style={{ marginBottom: "12px" }}>
              <div
                style={{
                  fontSize: "0.8rem",
                  fontWeight: 600,
                  color: "#6366f1",
                  marginBottom: "6px",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                }}
              >
                <Icon name="ClipboardList" size={14} /> Item Specifications
              </div>
              <p
                style={{
                  fontSize: "0.85rem",
                  color: "var(--text-secondary)",
                  margin: "0",
                  paddingLeft: "20px",
                }}
              >
                {standard.item_specs}
              </p>
            </div>
          )}

          {/* Sample Assessment */}
          {standard.sample_assessment && (
            <div>
              <div
                style={{
                  fontSize: "0.8rem",
                  fontWeight: 600,
                  color: "#ec4899",
                  marginBottom: "6px",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                }}
              >
                <Icon name="FileQuestion" size={14} /> Sample Assessment Item
              </div>
              <p
                style={{
                  fontSize: "0.85rem",
                  color: "var(--text-secondary)",
                  margin: "0",
                  paddingLeft: "20px",
                  fontStyle: "italic",
                  background: "var(--glass-hover)",
                  padding: "10px",
                  borderRadius: "8px",
                }}
              >
                {standard.sample_assessment}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Helper functions for authenticity checks
const getAuthenticityStatus = (result) => {
  // New format with separate AI and plagiarism detection
  if (result.ai_detection || result.plagiarism_detection) {
    const ai = result.ai_detection || {
      flag: "none",
      confidence: 0,
      reason: "",
    };
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
      flag:
        flag === "flagged" ? "likely" : flag === "review" ? "possible" : "none",
      confidence: flag === "flagged" ? 80 : flag === "review" ? 50 : 0,
      reason: flag !== "clean" ? reason : "",
    },
    plag: { flag: "none", reason: "" },
    overallStatus: flag,
    isNewFormat: false,
  };
};

const getAIFlagColor = (flag) => {
  switch (flag) {
    case "likely":
      return { bg: "rgba(248,113,113,0.2)", text: "#f87171" };
    case "possible":
      return { bg: "rgba(251,191,36,0.2)", text: "#fbbf24" };
    case "unlikely":
      return { bg: "rgba(96,165,250,0.2)", text: "#60a5fa" };
    default:
      return { bg: "rgba(74,222,128,0.2)", text: "#4ade80" };
  }
};

const getPlagFlagColor = (flag) => {
  switch (flag) {
    case "likely":
      return { bg: "rgba(248,113,113,0.2)", text: "#f87171" };
    case "possible":
      return { bg: "rgba(251,191,36,0.2)", text: "#fbbf24" };
    default:
      return { bg: "rgba(74,222,128,0.2)", text: "#4ade80" };
  }
};

function App() {
  // Check if this is the student portal route
  if (window.location.pathname.startsWith("/join")) {
    return <StudentPortal />;
  }

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
    teacher_email: "",
    email_signature: "",
    school_name: "",
    showToastNotifications: true,
    ai_model: "gpt-4o-mini",
    ensemble_enabled: false,
    ensemble_models: [], // e.g., ['gpt-4o-mini', 'claude-haiku', 'gemini-flash']
    availableTools: [], // Tools teacher has access to for lesson planning
  });

  // API Keys state (separate from config for security)
  const [apiKeys, setApiKeys] = useState({
    openai: "",
    anthropic: "",
    gemini: "",
    openaiConfigured: false,
    anthropicConfigured: false,
    geminiConfigured: false,
  });
  const [showApiKeys, setShowApiKeys] = useState({
    openai: false,
    anthropic: false,
    gemini: false,
  });
  const [savingApiKeys, setSavingApiKeys] = useState(false);

  // Focus Export state
  const [focusExportModal, setFocusExportModal] = useState(false);
  const [focusExportLoading, setFocusExportLoading] = useState(false);

  // Available EdTech tools that can be selected
  const EDTECH_TOOLS = [
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

  // State for custom tools
  const [customTools, setCustomTools] = useState([]);
  const [newCustomTool, setNewCustomTool] = useState("");

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
  const [gradeFilterStudent, setGradeFilterStudent] = useState(""); // Filter by individual student
  const [gradeFilterAssignment, setGradeFilterAssignment] = useState(""); // Filter by saved assignment

  // Individual upload state (for paper/handwritten assignments)
  const [individualUpload, setIndividualUpload] = useState({
    file: null,
    studentName: "",
    studentInfo: null, // Full student info from CSV (id, email, etc.)
    preview: null,
    isGrading: false,
    result: null,
    showSuggestions: false,
  });

  const [activeTab, setActiveTab] = useState("grade");
  const [settingsTab, setSettingsTab] = useState("general"); // general, grading, classroom, integration, privacy
  const [analytics, setAnalytics] = useState(null);
  const [selectedStudent, setSelectedStudent] = useState(null);
  const [analyticsPeriod, setAnalyticsPeriod] = useState("all"); // Quarter filter (Q1, Q2, etc.)
  const [analyticsClassPeriod, setAnalyticsClassPeriod] = useState(""); // Class period filter (Period 1, etc.)
  const [analyticsClassStudents, setAnalyticsClassStudents] = useState([]); // Students in selected class period
  const [resultsFilter, setResultsFilter] = useState("all"); // "all", "handwritten", "typed", "missing"
  const [resultsPeriodFilter, setResultsPeriodFilter] = useState(""); // Filter results by class period
  const [resultsSort, setResultsSort] = useState({
    field: "time",
    direction: "desc",
  }); // field: time, name, assignment, score, grade
  const [missingAssignmentFilter, setMissingAssignmentFilter] = useState(""); // Assignment to check for missing submissions
  const [missingPeriodFilter, setMissingPeriodFilter] = useState(""); // Period to filter missing report
  const [missingStudentFilter, setMissingStudentFilter] = useState(""); // Student to check for missing assignments
  const [missingUploadedFiles, setMissingUploadedFiles] = useState([]); // Files in folder for missing check
  const [missingFilesLoading, setMissingFilesLoading] = useState(false);
  const [skipVerified, setSkipVerified] = useState(false); // Skip verified grades on regrade
  const [excludeGradedStudents, setExcludeGradedStudents] = useState(false); // Exclude students already in results
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
  const toastIdCounter = useRef(0);

  const addToast = (message, type = "success", duration = 4000) => {
    const id = ++toastIdCounter.current;
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, duration);
  };

  const removeToast = (id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
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
    customMarkers: [],           // Now stores objects with points: { start: "Summary:", points: 20, type: "written" }
    excludeMarkers: [], // Sections to NOT grade (e.g., "Notes Section")
    gradingNotes: "",
    responseSections: [],
    aliases: [], // Previous names for matching renamed assignments
    completionOnly: false, // If true, track submission but don't AI grade
    rubricType: "standard", // standard, fill-in-blank, essay, cornell-notes, completion-only, custom
    customRubric: null, // Custom rubric categories if rubricType is "custom"
    sectionTemplate: "Custom",   // Track which template is applied
    effortPoints: 15,            // Points for effort/engagement category
  });
  const [savedAssignments, setSavedAssignments] = useState([]);
  const [savedAssignmentData, setSavedAssignmentData] = useState({}); // Map of name -> {aliases: [], title: ""}
  const [savedAssignmentsExpanded, setSavedAssignmentsExpanded] =
    useState(false);
  const [gradingModesExpanded, setGradingModesExpanded] = useState(false);
  const [loadedAssignmentName, setLoadedAssignmentName] = useState("");
  const [isLoadingAssignment, setIsLoadingAssignment] = useState(false); // Prevent auto-save during load
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

  // Highlighter mode: "start" (green), "end" (red), or "exclude" (orange)
  const [highlighterMode, setHighlighterMode] = useState("start");

  // Highlight colors
  const HIGHLIGHT_COLORS = {
    start: { bg: "rgba(34, 197, 94, 0.4)", border: "#22c55e", label: "Start" },
    end: { bg: "rgba(239, 68, 68, 0.4)", border: "#ef4444", label: "End" },
    exclude: { bg: "rgba(251, 146, 60, 0.4)", border: "#fb923c", label: "Exclude" },
  };

  // Results state
  const [editedResults, setEditedResults] = useState([]);
  const [reviewModal, setReviewModal] = useState({ show: false, index: -1 });
  const [reviewModalTab, setReviewModalTab] = useState("detected"); // "detected" or "raw"
  const [reviewModalRightTab, setReviewModalRightTab] = useState("edit"); // "edit" or "email"
  const [emailPreview, setEmailPreview] = useState({ show: false, emails: [] });
  const [emailStatus, setEmailStatus] = useState({
    sending: false,
    sent: 0,
    failed: 0,
    message: "",
  });
  const [emailApprovals, setEmailApprovals] = useState({}); // { index: 'approved' | 'rejected' | 'pending' }
  const [sentEmails, setSentEmails] = useState({}); // { index: true } - tracks which emails have been sent
  const [autoApproveEmails, setAutoApproveEmails] = useState(false);
  const [editedEmails, setEditedEmails] = useState({}); // { index: { subject, body } }
  const [resultsSearch, setResultsSearch] = useState("");
  const [curveModal, setCurveModal] = useState({ show: false, curveType: "add", curveValue: 5 }); // Curve modal state

  // Planner state
  const [standards, setStandards] = useState([]);
  const [selectedStandards, setSelectedStandards] = useState([]);
  const [expandedStandards, setExpandedStandards] = useState([]);
  const [lessonPlan, setLessonPlan] = useState(null);
  const [lessonVariations, setLessonVariations] = useState([]);
  const [brainstormIdeas, setBrainstormIdeas] = useState([]);
  const [selectedIdea, setSelectedIdea] = useState(null);
  const [plannerLoading, setPlannerLoading] = useState(false);
  const [brainstormLoading, setBrainstormLoading] = useState(false);
  const [generatedAssignment, setGeneratedAssignment] = useState(null);
  const [assignmentLoading, setAssignmentLoading] = useState(false);
  const [assignmentType, setAssignmentType] = useState("worksheet");
  const [showInteractivePreview, setShowInteractivePreview] = useState(false);
  const [interactiveResults, setInteractiveResults] = useState(null);

  // Saved lessons for assessment generation
  const [savedLessons, setSavedLessons] = useState({ units: {}, lessons: [] });
  const [savedUnits, setSavedUnits] = useState([]);
  const [selectedSources, setSelectedSources] = useState([]); // [{type, unit, filename, content}]
  const [showSaveLesson, setShowSaveLesson] = useState(false);
  const [saveLessonUnit, setSaveLessonUnit] = useState('');
  const [newUnitName, setNewUnitName] = useState('');

  const [unitConfig, setUnitConfig] = useState({
    title: "",
    duration: 1,
    periodLength: 50,
    type: "Lesson Plan",
    format: "Word",
    requirements: "",
  });

  // Assessment generator state
  const [assessmentConfig, setAssessmentConfig] = useState({
    type: "quiz",
    title: "",
    targetPeriod: "", // For differentiation based on Global AI Instructions
    totalQuestions: 20,
    totalPoints: 30,
    questionTypes: {
      multiple_choice: 10,
      short_answer: 4,
      extended_response: 2,
      true_false: 2,
      matching: 2,
    },
    pointsPerType: {
      multiple_choice: 1,
      short_answer: 2,
      true_false: 1,
      matching: 1,
      extended_response: 4,
    },
    dokDistribution: {
      "1": 4,
      "2": 8,
      "3": 6,
      "4": 2,
    },
    includeAnswerKey: true,
    includeStandardsReference: true,
  });

  // Helper function to distribute questions across types
  const distributeQuestions = (total) => {
    // Standard distribution: 50% MC, 15% SA, 10% ER, 15% TF, 10% Matching
    const mc = Math.round(total * 0.50);
    const sa = Math.round(total * 0.15);
    const er = Math.round(total * 0.10);
    const tf = Math.round(total * 0.15);
    const matching = total - mc - sa - er - tf; // remainder
    return {
      multiple_choice: Math.max(0, mc),
      short_answer: Math.max(0, sa),
      extended_response: Math.max(0, er),
      true_false: Math.max(0, tf),
      matching: Math.max(0, matching),
    };
  };

  // Helper function to distribute DOK levels
  const distributeDOK = (total) => {
    // Standard distribution: 20% DOK1, 40% DOK2, 30% DOK3, 10% DOK4
    const dok1 = Math.round(total * 0.20);
    const dok2 = Math.round(total * 0.40);
    const dok3 = Math.round(total * 0.30);
    const dok4 = total - dok1 - dok2 - dok3; // remainder
    return {
      "1": Math.max(0, dok1),
      "2": Math.max(0, dok2),
      "3": Math.max(0, dok3),
      "4": Math.max(0, dok4),
    };
  };

  // Helper function to distribute points per type to reach total
  const distributePoints = (totalPoints, questionTypes) => {
    // Base ratios: ER=4, SA=2, MC=TF=Matching=1
    const baseRatios = {
      multiple_choice: 1,
      short_answer: 2,
      true_false: 1,
      matching: 1,
      extended_response: 4,
    };

    // Get active types (count > 0)
    const activeTypes = Object.entries(questionTypes).filter(([, count]) => count > 0);
    if (activeTypes.length === 0) return { ...baseRatios };

    // Calculate weighted sum with base ratios
    let weightedSum = 0;
    activeTypes.forEach(([type, count]) => {
      weightedSum += count * (baseRatios[type] || 1);
    });

    if (weightedSum === 0) return { ...baseRatios };

    // Scale factor to reach target total
    const scale = totalPoints / weightedSum;

    // Apply scale and floor (start low, then add)
    const newPoints = { ...baseRatios };
    activeTypes.forEach(([type]) => {
      newPoints[type] = Math.max(1, Math.floor(baseRatios[type] * scale));
    });

    // Calculate current total
    const calcTotal = () => {
      let total = 0;
      activeTypes.forEach(([type, count]) => {
        total += count * newPoints[type];
      });
      return total;
    };

    // Iteratively adjust to hit target
    // Sort by ratio (highest first) - prefer adding to complex question types
    const sortedByRatio = [...activeTypes].sort((a, b) => (baseRatios[b[0]] || 1) - (baseRatios[a[0]] || 1));

    let iterations = 0;
    while (calcTotal() < totalPoints && iterations < 100) {
      // Add 1 point to the type that gets us closest to target
      let bestType = null;
      let bestDiff = Infinity;

      for (const [type, count] of sortedByRatio) {
        const newTotal = calcTotal() + count;
        const diff = Math.abs(totalPoints - newTotal);
        if (diff < bestDiff && newTotal <= totalPoints) {
          bestDiff = diff;
          bestType = type;
        }
      }

      if (bestType) {
        newPoints[bestType]++;
      } else {
        // Can't get closer without overshooting, pick smallest increment
        const [smallestType] = [...activeTypes].sort((a, b) => a[1] - b[1]);
        if (smallestType) newPoints[smallestType[0]]++;
        break;
      }
      iterations++;
    }

    return newPoints;
  };
  const [generatedAssessment, setGeneratedAssessment] = useState(null);
  const [assessmentLoading, setAssessmentLoading] = useState(false);
  const [assessmentAnswers, setAssessmentAnswers] = useState({}); // Track interactive answers for preview
  const [assessmentGradingResults, setAssessmentGradingResults] = useState(null); // Results from AI grading
  const [gradingAssessment, setGradingAssessment] = useState(false);
  const [plannerMode, setPlannerMode] = useState("lesson"); // "lesson" or "assessment"
  const [publishingAssessment, setPublishingAssessment] = useState(false);
  const [publishedAssessmentModal, setPublishedAssessmentModal] = useState({ show: false, joinCode: "", joinLink: "" });
  const [assessmentTemplates, setAssessmentTemplates] = useState([]);
  const [uploadingTemplate, setUploadingTemplate] = useState(false);
  const [showPlatformExport, setShowPlatformExport] = useState(false);

  // Teacher Dashboard state (Student Portal)
  const [publishedAssessments, setPublishedAssessments] = useState([]);
  const [loadingPublished, setLoadingPublished] = useState(false);
  const [selectedAssessmentResults, setSelectedAssessmentResults] = useState(null);
  const [loadingResults, setLoadingResults] = useState(false);

  // Saved Assessments state
  const [savedAssessments, setSavedAssessments] = useState([]);
  const [loadingSavedAssessments, setLoadingSavedAssessments] = useState(false);

  // Publish Modal state (enhanced with period, student selection)
  const [showPublishModal, setShowPublishModal] = useState(false);
  const [publishSettings, setPublishSettings] = useState({
    period: '',
    periodFilename: '',
    isMakeup: false,
    selectedStudents: [],
    timeLimit: null,
    applyAccommodations: true,
  });
  const [publishModalStudents, setPublishModalStudents] = useState([]);
  const [loadingPublishStudents, setLoadingPublishStudents] = useState(false);
  const [savingAssessment, setSavingAssessment] = useState(false);
  const [saveAssessmentName, setSaveAssessmentName] = useState('');

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

  // Accommodation state (IEP/504 support - FERPA compliant)
  const [accommodationPresets, setAccommodationPresets] = useState([]);
  const [studentAccommodations, setStudentAccommodations] = useState({});
  const [accommodationModal, setAccommodationModal] = useState({
    show: false,
    studentId: null,
  });
  const [selectedAccommodationPresets, setSelectedAccommodationPresets] =
    useState([]);
  const [accommodationCustomNotes, setAccommodationCustomNotes] = useState("");

  // Student writing profiles/history state
  const [studentHistoryList, setStudentHistoryList] = useState([]);
  const [studentHistoryLoading, setStudentHistoryLoading] = useState(false);
  const [selectedStudentHistory, setSelectedStudentHistory] = useState(null);

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
            if (loadedConfig.subject === "History") {
              loadedConfig.subject = "US History";
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
        if (data.assignmentData) setSavedAssignmentData(data.assignmentData);
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

    // Load accommodation presets and student mappings (FERPA compliant - local only)
    api
      .getAccommodationPresets()
      .then((data) => {
        if (data.presets) setAccommodationPresets(data.presets);
      })
      .catch(console.error);

    api
      .getStudentAccommodations()
      .then((data) => {
        if (data.accommodations) setStudentAccommodations(data.accommodations);
      })
      .catch(console.error);

    // Load saved lessons for assessment generation
    api
      .listLessons()
      .then((data) => {
        if (data.units) {
          setSavedLessons(data);
          setSavedUnits(Object.keys(data.units));
        }
      })
      .catch(console.error);

    // Check API keys status
    fetch("/api/check-api-keys")
      .then((res) => res.json())
      .then((data) => {
        setApiKeys((prev) => ({
          ...prev,
          openaiConfigured: data.openai_configured,
          anthropicConfigured: data.anthropic_configured,
          geminiConfigured: data.gemini_configured,
        }));
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

  // Auto-save Builder assignment when it changes (debounced)
  useEffect(() => {
    if (!settingsLoaded) return;
    if (!assignment.title) return; // Don't save assignments without a title
    if (isLoadingAssignment) return; // Don't save while loading an assignment

    const saveTimeout = setTimeout(async () => {
      // Double-check we're not in the middle of loading
      if (isLoadingAssignment) return;

      try {
        let dataToSave = { ...assignment, importedDoc };
        const isRename =
          loadedAssignmentName && loadedAssignmentName !== assignment.title;

        // If title changed from a previously loaded assignment, add old name to aliases
        if (isRename) {
          const currentAliases = assignment.aliases || [];
          if (!currentAliases.includes(loadedAssignmentName)) {
            dataToSave.aliases = [...currentAliases, loadedAssignmentName];
            // Also update local state with new alias
            setAssignment((prev) => ({ ...prev, aliases: dataToSave.aliases }));
          }
        }

        const saveResult = await api.saveAssignmentConfig(dataToSave);

        // Only proceed if save was successful
        if (saveResult.status === "saved") {
          // If renamed, delete the old assignment file (alias is preserved in new file)
          if (isRename) {
            try {
              await api.deleteAssignment(loadedAssignmentName);
              console.log(`Renamed assignment: "${loadedAssignmentName}" → "${assignment.title}" (old name saved as alias)`);
            } catch (deleteErr) {
              console.error("Failed to delete old assignment file:", deleteErr);
              // Don't fail the whole operation if delete fails
            }
          }

          // Refresh saved assignments list
          const list = await api.listAssignments();
          if (list.assignments) setSavedAssignments(list.assignments);
          if (list.assignmentData) setSavedAssignmentData(list.assignmentData);
          // Update loaded assignment name to reflect current title
          setLoadedAssignmentName(assignment.title);
        } else if (saveResult.error) {
          console.error("Failed to save assignment:", saveResult.error);
          addToast("Failed to save assignment: " + saveResult.error, "error");
        }
      } catch (error) {
        console.error("Failed to auto-save assignment:", error);
      }
    }, 1500); // Debounce 1.5 seconds (slightly longer for assignment changes)

    return () => clearTimeout(saveTimeout);
  }, [assignment, importedDoc, settingsLoaded, loadedAssignmentName, isLoadingAssignment]);

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

  // Load files when student filter is set (for file preview)
  useEffect(() => {
    if (
      gradeFilterStudent &&
      availableFiles.length === 0 &&
      config.assignments_folder
    ) {
      loadAvailableFiles();
    }
  }, [gradeFilterStudent, config.assignments_folder]);

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
            let filesToGrade = filesData.files.filter((f) => !f.graded);

            // Filter by period if one is selected
            if (selectedPeriod && periodStudents.length > 0) {
              filesToGrade = filesToGrade.filter((f) =>
                fileMatchesPeriodStudent(f.name, periodStudents),
              );
            }

            if (filesToGrade.length > 0) {
              // Update selected files and start grading
              const fileNames = filesToGrade.map((f) => f.name);
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

  // Load class period students for analytics filtering
  useEffect(() => {
    if (!analyticsClassPeriod) {
      setAnalyticsClassStudents([]);
      return;
    }
    api
      .getPeriodStudents(analyticsClassPeriod)
      .then((data) => {
        if (data.students) setAnalyticsClassStudents(data.students);
      })
      .catch(() => setAnalyticsClassStudents([]));
  }, [analyticsClassPeriod]);

  // Load uploaded files for missing assignments in analytics
  useEffect(() => {
    if (activeTab !== "analytics" || !config.assignments_folder) {
      return;
    }
    setMissingFilesLoading(true);
    api
      .listFiles(config.assignments_folder)
      .then((data) => {
        setMissingUploadedFiles(data.files || []);
      })
      .catch(() => setMissingUploadedFiles([]))
      .finally(() => setMissingFilesLoading(false));
  }, [activeTab, config.assignments_folder]);

  // Clear selected standards when grade/subject/state changes
  useEffect(() => {
    setSelectedStandards([]);
    setStandards([]);
  }, [config.state, config.grade_level, config.subject]);

  // Load standards when planner tab is active
  useEffect(() => {
    if (activeTab === "planner" && config.subject) {
      setPlannerLoading(true);
      api
        .getStandards({
          state: config.state || "FL",
          grade: config.grade_level || "7",
          subject: config.subject,
        })
        .then((data) => {
          console.log("Standards loaded:", data);
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
  }, [config.state, config.grade_level, config.subject, activeTab]);

  // Load assessment templates when settings tab is opened
  useEffect(() => {
    if (activeTab === "settings") {
      api.getAssessmentTemplates()
        .then((data) => {
          setAssessmentTemplates(data.templates || []);
        })
        .catch((e) => {
          console.error("Error loading assessment templates:", e);
        });
    }
  }, [activeTab]);

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

  // Load email approvals from persisted results
  useEffect(() => {
    if (status.results.length > 0) {
      const loadedApprovals = {};
      status.results.forEach((r, idx) => {
        if (r.email_approval) {
          loadedApprovals[idx] = r.email_approval;
        }
      });
      if (Object.keys(loadedApprovals).length > 0) {
        setEmailApprovals((prev) => ({ ...loadedApprovals, ...prev }));
      }
    }
  }, [status.results.length]); // Only run when results count changes

  // Sync editedResults with status.results (preserve user edits)
  useEffect(() => {
    if (status.results.length > 0) {
      setEditedResults((prev) => {
        // If we have fewer edited results than status results, add new ones
        if (prev.length < status.results.length) {
          const newResults = status.results.slice(prev.length).map((r) => ({
            ...r,
            edited: false,
          }));
          return [...prev, ...newResults];
        }
        // If same length, merge new data but preserve edits
        if (prev.length === status.results.length) {
          return prev.map((edited, i) => {
            if (edited.edited) {
              // Preserve user edits, only update non-edited fields
              return { ...status.results[i], ...edited, edited: true };
            }
            return { ...status.results[i], edited: false };
          });
        }
        // If status was cleared, reset
        if (status.results.length === 0) {
          return [];
        }
        return prev;
      });
    }
  }, [status.results]);

  // Auto-save edited results to backend (debounced)
  useEffect(() => {
    if (!editedResults.length) return;

    // Find results that have been edited
    const editedItems = editedResults.filter((r) => r.edited && r.filename);
    if (!editedItems.length) return;

    const saveTimeout = setTimeout(async () => {
      for (const item of editedItems) {
        try {
          await api.updateResult(item.filename, {
            score: item.score,
            letter_grade: item.letter_grade,
            feedback: item.feedback,
          });
          // Mark as saved by clearing the edited flag
          setEditedResults((prev) =>
            prev.map((r) =>
              r.filename === item.filename ? { ...r, edited: false } : r
            )
          );
        } catch (error) {
          console.error("Failed to save result:", error);
        }
      }
    }, 1000); // 1 second debounce

    return () => clearTimeout(saveTimeout);
  }, [editedResults]);

  // Show toast when new assignments are graded
  useEffect(() => {
    const currentCount = status.results.length;
    if (
      config.showToastNotifications &&
      currentCount > lastResultCount.current &&
      lastResultCount.current > 0
    ) {
      const newResults = status.results.slice(lastResultCount.current);
      newResults.forEach((result) => {
        const grade = result.letter_grade || "N/A";
        const score = result.score !== undefined ? `${result.score}%` : "";
        addToast(
          `Graded - ${result.student_name}: ${grade} ${score}`,
          grade === "A" || grade === "B"
            ? "success"
            : grade === "C"
              ? "info"
              : "warning",
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
        const ungraded = data.files.filter((f) => !f.graded).map((f) => f.name);
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
    return students.some((student) => {
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
        (first &&
          lastInitial &&
          lowerFilename.includes(`${first}, ${lastInitial}`)) ||
        // "First L" - e.g., "John S" (no comma, last initial)
        (first &&
          lastInitial &&
          lowerFilename.match(
            new RegExp(`${first}\\s+${lastInitial}[^a-z]`, "i"),
          )) ||
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

  // Check if a student name matches any student in the period roster
  const studentNameMatchesPeriod = (studentName, students) => {
    if (!students || students.length === 0) return true;
    const lowerName = (studentName || "").toLowerCase();
    return students.some((student) => {
      const first = (student.first || "").toLowerCase().trim();
      const last = (student.last || "").toLowerCase().trim();
      // Match "First Last" or "Last, First" patterns
      return (
        (first &&
          last &&
          lowerName.includes(first) &&
          lowerName.includes(last)) ||
        (first && lowerName.startsWith(first + " ")) ||
        (last && lowerName.endsWith(" " + last))
      );
    });
  };

  // Sort periods numerically by extracting number from period_name (e.g., "Period 1" → 1)
  const sortedPeriods = useMemo(() => {
    return [...periods].sort((a, b) => {
      const numA = parseInt(
        (a.period_name || "").match(/\d+/)?.[0] || "999",
        10,
      );
      const numB = parseInt(
        (b.period_name || "").match(/\d+/)?.[0] || "999",
        10,
      );
      return numA - numB;
    });
  }, [periods]);

  // Compute filtered analytics based on class period selection (memoized)
  const filteredAnalytics = useMemo(() => {
    if (
      !analytics ||
      !analyticsClassPeriod ||
      analyticsClassStudents.length === 0
    ) {
      return analytics;
    }

    // Filter all_grades by student name
    const filteredGrades = (analytics.all_grades || []).filter((g) =>
      studentNameMatchesPeriod(g.student_name, analyticsClassStudents),
    );

    // Filter student_progress by name
    const filteredProgress = (analytics.student_progress || []).filter((s) =>
      studentNameMatchesPeriod(s.name, analyticsClassStudents),
    );

    // Recompute class stats from filtered grades
    const scores = filteredGrades.map((g) => g.score);
    const filteredClassStats = {
      total_assignments: filteredGrades.length,
      total_students: filteredProgress.length,
      class_average:
        scores.length > 0
          ? Math.round(
              (scores.reduce((a, b) => a + b, 0) / scores.length) * 10,
            ) / 10
          : 0,
      highest: scores.length > 0 ? Math.max(...scores) : 0,
      lowest: scores.length > 0 ? Math.min(...scores) : 0,
      grade_distribution: {
        A: scores.filter((s) => s >= 90).length,
        B: scores.filter((s) => s >= 80 && s < 90).length,
        C: scores.filter((s) => s >= 70 && s < 80).length,
        D: scores.filter((s) => s >= 60 && s < 70).length,
        F: scores.filter((s) => s < 60).length,
      },
    };

    // Filter attention_needed and top_performers
    const filteredAttention = (analytics.attention_needed || []).filter((s) =>
      studentNameMatchesPeriod(s.name, analyticsClassStudents),
    );
    const filteredTop = filteredProgress
      .sort((a, b) => b.average - a.average)
      .slice(0, 5);

    return {
      ...analytics,
      all_grades: filteredGrades,
      student_progress: filteredProgress,
      class_stats: filteredClassStats,
      attention_needed: filteredAttention,
      top_performers: filteredTop,
    };
  }, [analytics, analyticsClassPeriod, analyticsClassStudents]);

  // Grading functions
  const handleStartGrading = async () => {
    try {
      // Auto-save assignment config if it has a title and content
      const hasGradeConfig =
        gradeAssignment.title &&
        (gradeAssignment.customMarkers.length > 0 ||
          gradeAssignment.gradingNotes ||
          (gradeAssignment.responseSections || []).length > 0 ||
          gradeImportedDoc.filename);

      if (hasGradeConfig) {
        try {
          const dataToSave = {
            ...gradeAssignment,
            importedDoc: gradeImportedDoc.filename ? gradeImportedDoc : null,
          };
          await api.saveAssignmentConfig(dataToSave);
          // Refresh saved assignments list
          const list = await api.listAssignments();
          if (list.assignments) setSavedAssignments(list.assignments);
          if (list.assignmentData) setSavedAssignmentData(list.assignmentData);
        } catch (saveError) {
          console.error("Failed to auto-save assignment config:", saveError);
        }
      }

      // Determine which files to grade
      // If filters are active, ALWAYS use filtered files (not the selectedFiles state which may be stale)
      let filesToGrade = null;
      const hasActiveFilter = selectedPeriod || gradeFilterStudent || gradeFilterAssignment;

      // If filters are active, load and filter files (takes precedence over checkbox selection)
      if (hasActiveFilter) {
        try {
          const filesData = await api.listFiles(config.assignments_folder);
          if (filesData.files) {
            let filtered = filesData.files.filter((f) => !f.graded);

            // Filter by period students
            if (selectedPeriod && periodStudents.length > 0) {
              filtered = filtered.filter((f) =>
                fileMatchesPeriodStudent(f.name, periodStudents),
              );
            }

            // Filter by individual student name
            if (gradeFilterStudent) {
              filtered = filtered.filter((f) => {
                const fileName = f.name.toLowerCase();
                let studentName = gradeFilterStudent.toLowerCase();
                // Handle "Last; First" or "Last, First" roster format - convert to "first last"
                if (studentName.includes(';') || studentName.includes(',')) {
                  const parts = studentName.split(/[;,]/).map(p => p.trim());
                  if (parts.length >= 2) {
                    const lastName = parts[0];
                    const firstName = parts[1].split(' ')[0]; // Take first word of first name
                    studentName = firstName + ' ' + lastName;
                  }
                }
                // Check if filename contains student name (handles various naming formats)
                return (
                  fileName.includes(studentName.replace(/\s+/g, "")) ||
                  fileName.includes(studentName.replace(/\s+/g, "_")) ||
                  fileName.includes(studentName.replace(/\s+/g, "-")) ||
                  fileName.includes(studentName)
                );
              });
            }

            // Filter by assignment name in filename (including aliases, title, and original imported filename)
            if (gradeFilterAssignment) {
              // Get all name variations to match: assignment name, title, aliases, and imported filename
              const assignmentConfig = savedAssignmentData[gradeFilterAssignment] || {};
              const importedFilename = (assignmentConfig.importedFilename || "").toLowerCase().replace(/\.[^/.]+$/, ""); // Remove extension

              // Clean function to remove emojis and special chars for better matching
              const cleanForMatch = (str) => str.replace(/[\u{1F300}-\u{1F9FF}]/gu, "").replace(/[–—]/g, "-").replace(/[^\w\s-]/g, "").trim();

              // Extract chapter/section patterns like "chapter 10 section 2"
              const extractChapterSection = (str) => {
                const match = str.match(/chapter\s*(\d+)\s*[-–—]?\s*section\s*(\d+)/i);
                return match ? `chapter ${match[1]} section ${match[2]}` : null;
              };

              const chapterSection = extractChapterSection(importedFilename) || extractChapterSection(assignmentConfig.title || "");

              const namesToMatch = [
                gradeFilterAssignment,
                assignmentConfig.title || "",
                ...(assignmentConfig.aliases || []),
                importedFilename,
                cleanForMatch(importedFilename),
                cleanForMatch(assignmentConfig.title || ""),
                chapterSection
              ].filter(Boolean).map(n => n.toLowerCase());

              filtered = filtered.filter((f) => {
                const fileName = f.name.toLowerCase();
                const fileNameNoExt = fileName.replace(/\.[^/.]+$/, ""); // Remove extension for matching
                const fileNameClean = cleanForMatch(fileNameNoExt);
                const fileChapterSection = extractChapterSection(fileName);

                // Check if filename contains any of the assignment names/aliases/imported filename
                return namesToMatch.some(name => {
                  if (!name) return false;
                  const nameClean = cleanForMatch(name);

                  // Check various spacing formats
                  if (fileName.includes(name.replace(/\s+/g, "")) ||
                      fileName.includes(name.replace(/\s+/g, "_")) ||
                      fileName.includes(name.replace(/\s+/g, "-")) ||
                      fileName.includes(name) ||
                      fileNameClean.includes(nameClean) ||
                      nameClean.includes(fileNameClean)) {
                    return true;
                  }
                  // Check chapter/section match
                  if (chapterSection && fileChapterSection && chapterSection === fileChapterSection) {
                    return true;
                  }
                  // Also check if the imported filename matches this file (for exact original document match)
                  if (importedFilename && (fileNameNoExt.includes(importedFilename) || importedFilename.includes(fileNameNoExt))) {
                    return true;
                  }
                  return false;
                });
              });
            }

            // Exclude students who already have results for THIS assignment
            if (excludeGradedStudents && status.results.length > 0) {
              // Filter results to only those matching the current assignment filter
              let relevantResults = status.results;
              if (gradeFilterAssignment) {
                const assignmentConfig = savedAssignmentData[gradeFilterAssignment] || {};
                const importedFilename = (assignmentConfig.importedFilename || "").toLowerCase().replace(/\.[^/.]+$/, "");
                const assignmentNamesToMatch = [
                  gradeFilterAssignment,
                  assignmentConfig.title || "",
                  ...(assignmentConfig.aliases || []),
                  importedFilename
                ].filter(Boolean).map(n => n.toLowerCase());

                relevantResults = status.results.filter((r) => {
                  const resultAssignment = (r.assignment || "").toLowerCase();
                  const resultFilename = (r.filename || "").toLowerCase();
                  return assignmentNamesToMatch.some(name =>
                    resultAssignment.includes(name) ||
                    resultFilename.includes(name) ||
                    name.includes(resultAssignment)
                  );
                });
              }

              const gradedStudentNames = relevantResults.map((r) =>
                (r.student_name || "").toLowerCase().replace(/\s+/g, "")
              );
              filtered = filtered.filter((f) => {
                const fileName = f.name.toLowerCase().replace(/\s+/g, "");
                // Check if any graded student name appears in the filename
                return !gradedStudentNames.some((name) =>
                  name && fileName.includes(name)
                );
              });
            }

            if (filtered.length > 0) {
              filesToGrade = filtered.map((f) => f.name);
              // Log which files will be graded based on filter
              const filterDesc = [
                gradeFilterStudent ? `student "${gradeFilterStudent}"` : null,
                gradeFilterAssignment ? `assignment "${gradeFilterAssignment}"` : null,
                selectedPeriod ? "selected period" : null,
              ].filter(Boolean).join(" and ");
              console.log(`Grading ${filtered.length} files for ${filterDesc}:`, filesToGrade);
              addToast(`Grading ${filtered.length} files for ${filterDesc}`, "info");
            } else {
              const filterDesc = [
                gradeFilterStudent ? `student "${gradeFilterStudent}"` : null,
                gradeFilterAssignment
                  ? `assignment "${gradeFilterAssignment}"`
                  : null,
                selectedPeriod ? "selected period" : null,
              ]
                .filter(Boolean)
                .join(" and ");
              addToast(`No ungraded files found for ${filterDesc}`, "warning");
              return;
            }
          }
        } catch (e) {
          console.error("Failed to load files for filter:", e);
        }
      } else if (selectedFiles.length > 0) {
        // No filter active, but user has manually selected files via checkboxes
        filesToGrade = selectedFiles;
      }
      // If no filter and no selection, filesToGrade stays null (grade all new files)

      // Get the period name for differentiated grading
      const selectedPeriodName = selectedPeriod
        ? periods.find(p => p.filename === selectedPeriod)?.period_name || ''
        : '';

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
        // Pass the custom rubric from Settings
        rubric: rubric,
        // Pass selected files (null means grade all new files)
        selectedFiles: filesToGrade,
        // Skip verified grades on regrade (only regrade unverified)
        skipVerified: skipVerified,
        // Pass the period name for differentiated grading expectations
        classPeriod: selectedPeriodName,
        // Pass ensemble models if enabled (need at least 2 models)
        ensemble_models: config.ensemble_enabled && config.ensemble_models?.length >= 2 ? config.ensemble_models : null,
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

  // Handle individual file upload for paper/handwritten assignments
  const handleIndividualFileSelect = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    // Create preview URL for images
    const preview = file.type.startsWith("image/")
      ? URL.createObjectURL(file)
      : null;
    setIndividualUpload((prev) => ({
      ...prev,
      file,
      preview,
      result: null,
    }));
  };

  const handleIndividualGrade = async () => {
    if (!individualUpload.file || !individualUpload.studentName.trim()) {
      addToast("Please select a file and enter the student name", "warning");
      return;
    }

    setIndividualUpload((prev) => ({ ...prev, isGrading: true, result: null }));

    try {
      const formData = new FormData();
      formData.append("file", individualUpload.file);
      formData.append("student_name", individualUpload.studentName.trim());
      formData.append("grade_level", config.grade_level);
      formData.append("subject", config.subject);
      formData.append("output_folder", config.output_folder);
      formData.append("globalAINotes", globalAINotes);
      formData.append("teacher_name", config.teacher_name || "");
      formData.append("school_name", config.school_name || "");
      // Pass class period for differentiated grading
      if (selectedPeriod) {
        const periodName = periods.find(p => p.filename === selectedPeriod)?.period_name || '';
        formData.append("classPeriod", periodName);
      }
      // Pass student info from CSV if available
      if (individualUpload.studentInfo) {
        formData.append(
          "studentInfo",
          JSON.stringify(individualUpload.studentInfo),
        );
      }
      // Pass assignment config if available
      if (
        gradeAssignment.gradingNotes ||
        gradeAssignment.customMarkers?.length > 0 ||
        gradeAssignment.title
      ) {
        formData.append("assignmentConfig", JSON.stringify(gradeAssignment));
      }

      const response = await fetch("/api/grade-individual", {
        method: "POST",
        body: formData,
      });
      const result = await response.json();

      if (result.error) {
        addToast("Grading error: " + result.error, "error");
        setIndividualUpload((prev) => ({ ...prev, isGrading: false }));
        return;
      }

      setIndividualUpload((prev) => ({ ...prev, isGrading: false, result }));

      // Add to results list
      setStatus((prev) => ({
        ...prev,
        results: [...prev.results, result],
      }));

      addToast(
        `Graded - ${individualUpload.studentName}: ${result.letter_grade} (${result.score}%)`,
        "success",
      );
    } catch (error) {
      console.error("Individual grading error:", error);
      addToast("Failed to grade: " + error.message, "error");
      setIndividualUpload((prev) => ({ ...prev, isGrading: false }));
    }
  };

  const clearIndividualUpload = () => {
    if (individualUpload.preview) {
      URL.revokeObjectURL(individualUpload.preview);
    }
    setIndividualUpload({
      file: null,
      studentName: "",
      studentInfo: null,
      preview: null,
      isGrading: false,
      result: null,
      showSuggestions: false,
    });
  };

  // Filter students for autocomplete
  const getStudentSuggestions = (input) => {
    if (!input || input.length < 2) return [];
    const lowerInput = input.toLowerCase();
    return periodStudents
      .filter((s) => {
        const fullName = s.full?.toLowerCase() || "";
        const first = s.first?.toLowerCase() || "";
        const last = s.last?.toLowerCase() || "";
        return (
          fullName.includes(lowerInput) ||
          first.includes(lowerInput) ||
          last.includes(lowerInput)
        );
      })
      .slice(0, 5); // Limit to 5 suggestions
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
        addToast("Error parsing document: " + data.error, "error");
        setImportedDoc({ text: "", html: "", filename: "", loading: false });
      } else {
        // Use filename as title (cleaner than document metadata which is often generic)
        const newTitle = file.name
          .replace(/\.(docx|pdf|doc|txt)$/i, "")
          .replace(/_/g, " ")
          .replace(/\s+/g, " ")
          .trim();

        // Sanitize title the same way backend does for filename comparison
        const safeTitle = newTitle.replace(/[^a-zA-Z0-9 \-_]/g, "").trim();

        // Check if this assignment already exists (compare sanitized names)
        const existingName = savedAssignments.find(
          (name) => name.toLowerCase() === safeTitle.toLowerCase(),
        );

        if (existingName) {
          const confirmLoad = window.confirm(
            `An assignment named "${existingName}" already exists.\n\nDo you want to load the existing assignment instead?`,
          );
          if (confirmLoad) {
            // Load existing assignment instead
            setImportedDoc({
              text: "",
              html: "",
              filename: "",
              loading: false,
            });
            try {
              const existingData = await api.loadAssignment(existingName);
              if (existingData.assignment) {
                setAssignment({
                  title: existingData.assignment.title || "",
                  subject: existingData.assignment.subject || "Social Studies",
                  totalPoints: existingData.assignment.totalPoints || 100,
                  instructions: existingData.assignment.instructions || "",
                  questions: existingData.assignment.questions || [],
                  customMarkers: existingData.assignment.customMarkers || [],
                  excludeMarkers: existingData.assignment.excludeMarkers || [],
                  gradingNotes: existingData.assignment.gradingNotes || "",
                  responseSections:
                    existingData.assignment.responseSections || [],
                });
                setLoadedAssignmentName(existingName);
                if (existingData.assignment.importedDoc) {
                  setImportedDoc(existingData.assignment.importedDoc);
                }
              }
            } catch (loadErr) {
              console.error("Failed to load existing assignment:", loadErr);
            }
            return;
          }
          // User chose not to load existing - cancel the import
          setImportedDoc({ text: "", html: "", filename: "", loading: false });
          return;
        }

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
          setAssignment({ ...assignment, title: newTitle });
        }
      }
    } catch (err) {
      addToast("Error: " + err.message, "error");
      setImportedDoc({ text: "", html: "", filename: "", loading: false });
    }
  };

  const openDocEditor = () => {
    if (importedDoc.text || importedDoc.html) {
      let html = importedDoc.html;

      // If no markers but HTML has highlights, clean orphaned highlights
      const hasHighlights = html && html.includes('data-marker-id=');
      const hasMarkers = (assignment.customMarkers || []).length > 0;

      if (hasHighlights && !hasMarkers) {
        html = removeAllHighlightsFromHtml(html);
        // Also update importedDoc to persist the cleanup
        setImportedDoc({ ...importedDoc, html });
      }

      setDocEditorModal({
        show: true,
        editedHtml: html,
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
      if (highlighterMode === "start") {
        // Adding a new start marker
        const exists = (assignment.customMarkers || []).some(m =>
          typeof m === 'string' ? m === text : m.start === text
        );
        if (!exists) {
          const newMarkers = [...(assignment.customMarkers || []), text];
          const markerIndex = newMarkers.length - 1;

          // Apply highlight to HTML
          const newHtml = highlightTextInHtml(
            docEditorModal.editedHtml,
            text,
            HIGHLIGHT_COLORS.start,
            `start-${markerIndex}`
          );

          setAssignment({ ...assignment, customMarkers: newMarkers });
          setDocEditorModal({ ...docEditorModal, editedHtml: newHtml });
          addToast("Start marker added (green)", "success");
        }
      } else if (highlighterMode === "exclude") {
        // Adding an exclude marker - section to NOT grade
        const exists = (assignment.excludeMarkers || []).some(m => m === text);
        if (!exists) {
          const newExcludeMarkers = [...(assignment.excludeMarkers || []), text];
          const excludeIndex = newExcludeMarkers.length - 1;

          // Apply highlight to HTML
          const newHtml = highlightTextInHtml(
            docEditorModal.editedHtml,
            text,
            HIGHLIGHT_COLORS.exclude,
            `exclude-${excludeIndex}`
          );

          setAssignment({ ...assignment, excludeMarkers: newExcludeMarkers });
          setDocEditorModal({ ...docEditorModal, editedHtml: newHtml });
          addToast("Exclude marker added (orange) - this section will NOT be graded", "success");
        } else {
          addToast("This section is already marked as excluded", "warning");
        }
      } else {
        // Adding an end marker - attach to the last marker that doesn't have one
        const markers = [...(assignment.customMarkers || [])];
        const lastWithoutEnd = markers.findIndex((m, i) => {
          // Find first marker without an end marker
          return typeof m === 'string' || !m.end;
        });

        if (lastWithoutEnd >= 0) {
          const startText = getMarkerText(markers[lastWithoutEnd]);
          markers[lastWithoutEnd] = { start: startText, end: text };

          // Apply highlight to HTML
          const newHtml = highlightTextInHtml(
            docEditorModal.editedHtml,
            text,
            HIGHLIGHT_COLORS.end,
            `end-${lastWithoutEnd}`
          );

          setAssignment({ ...assignment, customMarkers: markers });
          setDocEditorModal({ ...docEditorModal, editedHtml: newHtml });
          addToast("End marker added (red)", "success");
        } else {
          addToast("Add a start marker first", "warning");
        }
      }
    } else if (text.length <= 2) {
      addToast("Please select more text (at least 3 characters)", "warning");
    } else if (text.length >= 2000) {
      addToast(
        "Selection too long. Please select less text (under 2000 characters)",
        "warning",
      );
    }
  };

  // Helper to get marker text (handles both string and object formats)
  const getMarkerText = (marker) => {
    return typeof marker === 'string' ? marker : marker.start;
  };

  // Helper to get end marker (if exists)
  const getEndMarker = (marker) => {
    return typeof marker === 'object' ? marker.end : null;
  };

  // Get marker points (default 10 if not specified)
  const getMarkerPoints = (marker) => {
    if (typeof marker === 'string') return 10;
    return marker.points || 10;
  };

  // Get marker type (default "written")
  const getMarkerType = (marker) => {
    if (typeof marker === 'string') return 'written';
    return marker.type || 'written';
  };

  // Calculate total points from markers
  const calculateTotalPoints = (markers, effortPoints = 15) => {
    const markerTotal = (markers || []).reduce((sum, m) => sum + getMarkerPoints(m), 0);
    return markerTotal + effortPoints;
  };

  // Convert old string marker to new format
  const normalizeMarker = (marker) => {
    if (typeof marker === 'string') {
      return { start: marker, points: 10, type: 'written' };
    }
    if (marker.start && !marker.points) {
      return { ...marker, points: 10, type: marker.type || 'written' };
    }
    return marker;
  };

  const removeMarker = (marker, markerIndex) => {
    const markerText = getMarkerText(marker);

    // Remove ALL highlights and re-apply remaining ones (avoids index mismatch issues)
    let cleanHtml = removeAllHighlightsFromHtml(docEditorModal.editedHtml);

    // Filter out the removed marker
    const remainingMarkers = (assignment.customMarkers || []).filter(
      (m) => getMarkerText(m) !== markerText,
    );

    // Re-apply highlights for remaining markers
    const newHtml = applyAllHighlights(cleanHtml, remainingMarkers);

    setAssignment({
      ...assignment,
      customMarkers: remainingMarkers,
    });

    // Update BOTH docEditorModal AND importedDoc
    setDocEditorModal({ ...docEditorModal, editedHtml: newHtml });
    setImportedDoc({ ...importedDoc, html: newHtml });
  };

  // Add or update end marker for a given start marker
  const setEndMarker = (markerIndex, endText) => {
    const updated = [...(assignment.customMarkers || [])];
    const current = updated[markerIndex];
    const startText = getMarkerText(current);

    if (endText && endText.trim()) {
      // Convert to object with end marker
      updated[markerIndex] = { start: startText, end: endText.trim() };
    } else {
      // Remove end marker, convert back to string
      updated[markerIndex] = startText;
    }
    setAssignment({ ...assignment, customMarkers: updated });
  };

  // Highlight text in HTML with a colored span
  const highlightTextInHtml = (html, text, color, markerId) => {
    if (!text || !html) return html;

    // Escape special regex characters
    const escaped = text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    // Match the text (case-insensitive, first occurrence only)
    const regex = new RegExp(`(${escaped})`, 'i');

    // Check if already highlighted
    if (html.includes(`data-marker-id="${markerId}"`)) {
      return html; // Already highlighted
    }

    // Replace first occurrence with highlighted span
    return html.replace(regex, `<span data-marker-id="${markerId}" style="background:${color.bg};border-bottom:2px solid ${color.border};padding:2px 0;">$1</span>`);
  };

  // Remove highlight from HTML by marker ID
  const removeHighlightFromHtml = (html, markerId) => {
    if (!html) return html;
    // Remove the span but keep the inner content (handles nested tags)
    // Match opening span with marker ID, then capture everything until closing span
    const regex = new RegExp(`<span[^>]*data-marker-id="${markerId}"[^>]*>(.*?)</span>`, 'gis');
    return html.replace(regex, '$1');
  };

  // Remove ALL marker highlights from HTML (for clean reset)
  const removeAllHighlightsFromHtml = (html) => {
    if (!html) return html;
    // Remove all spans with data-marker-id attribute
    return html.replace(/<span[^>]*data-marker-id="[^"]*"[^>]*>(.*?)<\/span>/gis, '$1');
  };

  // Apply all marker highlights to HTML
  const applyAllHighlights = (html, markers) => {
    if (!html || !markers) return html;

    let result = html;
    markers.forEach((marker, i) => {
      const startText = getMarkerText(marker);
      const endText = getEndMarker(marker);

      // Highlight start marker in green
      result = highlightTextInHtml(result, startText, HIGHLIGHT_COLORS.start, `start-${i}`);

      // Highlight end marker in red (if exists)
      if (endText) {
        result = highlightTextInHtml(result, endText, HIGHLIGHT_COLORS.end, `end-${i}`);
      }
    });
    return result;
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
      addToast("Please enter a title", "warning");
      return;
    }
    try {
      const dataToSave = { ...assignment, importedDoc };
      await api.saveAssignmentConfig(dataToSave);
      addToast("Assignment saved!", "success");
      setLoadedAssignmentName(assignment.title);
      const list = await api.listAssignments();
      if (list.assignments) setSavedAssignments(list.assignments);
      if (list.assignmentData) setSavedAssignmentData(list.assignmentData);
    } catch (e) {
      addToast("Error saving: " + e.message, "error");
    }
  };

  const loadAssignment = async (name) => {
    try {
      setIsLoadingAssignment(true); // Prevent auto-save during load
      const data = await api.loadAssignment(name);
      if (data.assignment) {
        // Set importedDoc FIRST to prevent race condition
        if (data.assignment.importedDoc) {
          setImportedDoc(data.assignment.importedDoc);
          // Also restore the highlighted HTML to the editor
          if (data.assignment.importedDoc.html) {
            setDocEditorModal(prev => ({
              ...prev,
              editedHtml: data.assignment.importedDoc.html
            }));
          }
        } else {
          setImportedDoc({ text: "", html: "", filename: "", loading: false });
        }
        // Migrate old markers (strings or missing points) to have proper point values
        const effortPts = data.assignment.effortPoints ?? 15;
        let migratedMarkers = data.assignment.customMarkers || [];

        // Check if markers need migration (any string markers or markers without points)
        const needsMigration = migratedMarkers.length > 0 && migratedMarkers.some(m =>
          typeof m === 'string' || (typeof m === 'object' && !m.points)
        );

        if (needsMigration) {
          // Distribute remaining points (100 - effort) evenly among markers
          const availablePoints = 100 - effortPts;
          const pointsPerMarker = Math.floor(availablePoints / migratedMarkers.length);
          const remainder = availablePoints % migratedMarkers.length;

          migratedMarkers = migratedMarkers.map((m, i) => {
            const markerText = typeof m === 'string' ? m : m.start;
            const markerType = typeof m === 'object' ? (m.type || 'written') : 'written';
            // Give first marker any remainder points
            const pts = pointsPerMarker + (i === 0 ? remainder : 0);
            return { start: markerText, points: pts, type: markerType };
          });
        }

        setAssignment({
          title: data.assignment.title || "",
          subject: data.assignment.subject || "Social Studies",
          totalPoints: data.assignment.totalPoints || 100,
          instructions: data.assignment.instructions || "",
          questions: data.assignment.questions || [],
          customMarkers: migratedMarkers,
          excludeMarkers: data.assignment.excludeMarkers || [],
          gradingNotes: data.assignment.gradingNotes || "",
          responseSections: data.assignment.responseSections || [],
          aliases: data.assignment.aliases || [],
          completionOnly: data.assignment.completionOnly || false,
          rubricType: data.assignment.rubricType || "standard",
          customRubric: data.assignment.customRubric || null,
          sectionTemplate: data.assignment.sectionTemplate || "Custom",
          effortPoints: effortPts,
        });
        setLoadedAssignmentName(name);
      }
      // Small delay before allowing auto-save again
      setTimeout(() => setIsLoadingAssignment(false), 500);
    } catch (e) {
      setIsLoadingAssignment(false);
      addToast("Error loading: " + e.message, "error");
    }
  };

  const deleteAssignment = async (name) => {
    if (!confirm(`Delete "${name}"?`)) return;
    try {
      await api.deleteAssignment(name);
      setSavedAssignments(savedAssignments.filter((a) => a !== name));
      addToast(`"${name}" deleted`, "success");
      if (loadedAssignmentName === name) {
        setAssignment({
          title: "",
          subject: "Social Studies",
          totalPoints: 100,
          instructions: "",
          questions: [],
          customMarkers: [],
          excludeMarkers: [],
          gradingNotes: "",
          responseSections: [],
          aliases: [],
          completionOnly: false,
          rubricType: "standard",
          customRubric: null,
          sectionTemplate: "Custom",
          effortPoints: 15,
        });
        setLoadedAssignmentName("");
      }
    } catch (e) {
      addToast("Error: " + e.message, "error");
    }
  };

  const exportAssignment = async (format) => {
    try {
      const data = await api.exportAssignment({ assignment, format });
      if (data.error) addToast("Error: " + data.error, "error");
      else addToast("Assignment exported!", "success");
    } catch (e) {
      addToast("Error exporting: " + e.message, "error");
    }
  };

  // Planner functions
  const toggleStandard = (code) => {
    setSelectedStandards((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code],
    );
  };

  // Brainstorm lesson ideas
  const brainstormIdeasHandler = async () => {
    if (selectedStandards.length === 0) {
      addToast("Please select at least one standard", "warning");
      return;
    }
    setBrainstormLoading(true);
    setBrainstormIdeas([]);
    setSelectedIdea(null);
    setLessonPlan(null);  // Clear existing lesson plan so brainstorm results show
    setLessonVariations([]);  // Clear variations too
    try {
      // Look up full standard objects from codes
      const fullStandards = selectedStandards.map((code) => {
        const std = standards.find((s) => s.code === code);
        return std ? `${std.code}: ${std.benchmark}` : code;
      });
      const data = await api.brainstormLessonIdeas({
        standards: fullStandards,
        config: {
          state: config.state || "FL",
          grade: config.grade_level,
          subject: config.subject,
          availableTools: config.availableTools || [],
        },
      });
      if (data.error)
        addToast("Note: Using sample ideas - " + data.error, "info");
      setBrainstormIdeas(data.ideas || []);
    } catch (e) {
      addToast("Error brainstorming: " + e.message, "error");
    } finally {
      setBrainstormLoading(false);
    }
  };

  // Generate lesson plan (optionally from selected idea, optionally with variations)
  const generateLessonPlan = async (generateVariations = false) => {
    if (selectedStandards.length === 0) {
      addToast("Please select at least one standard", "warning");
      return;
    }
    setPlannerLoading(true);
    setLessonVariations([]);
    try {
      // Look up full standard objects from codes
      const fullStandards = selectedStandards.map((code) => {
        const std = standards.find((s) => s.code === code);
        return std ? `${std.code}: ${std.benchmark}` : code;
      });
      // Build title: use provided title, selected idea title, or let AI generate from standards
      const standardCodes = selectedStandards.join(", ");
      const autoTitle =
        unitConfig.title || (selectedIdea ? selectedIdea.title : "");

      const data = await api.generateLessonPlan({
        standards: fullStandards,
        config: {
          state: config.state || "FL",
          grade: config.grade_level,
          subject: config.subject,
          availableTools: config.availableTools || [],
          ...unitConfig,
          title: autoTitle, // Empty string tells backend to auto-generate title
          standardCodes: standardCodes, // Pass for title generation if needed
        },
        selectedIdea: selectedIdea,
        generateVariations: generateVariations,
      });
      if (data.error) addToast("Error: " + data.error, "error");
      else if (data.variations) {
        setLessonVariations(data.variations);
        addToast(
          `Generated ${data.variations.length} lesson plan variations!`,
          "success",
        );
      } else {
        setLessonPlan(data.plan || data);
      }
    } catch (e) {
      addToast("Error generating plan: " + e.message, "error");
    } finally {
      setPlannerLoading(false);
    }
  };

  const exportLessonPlanHandler = async () => {
    if (!lessonPlan) return;
    try {
      const data = await api.exportLessonPlan(lessonPlan);
      if (data.error) addToast("Error exporting: " + data.error, "error");
      else addToast("Lesson plan exported!", "success");
    } catch (e) {
      addToast("Error exporting: " + e.message, "error");
    }
  };

  // Assessment generation handlers
  const generateAssessmentHandler = async () => {
    if (selectedStandards.length === 0) {
      addToast("Please select at least one standard", "warning");
      return;
    }
    setAssessmentLoading(true);
    setGeneratedAssessment(null);
    try {
      // Get full standard objects
      const fullStandards = selectedStandards.map((code) => {
        return standards.find((s) => s.code === code) || { code, benchmark: code };
      });

      // Auto-generate title if not provided
      const title = assessmentConfig.title ||
        `${config.subject || "Subject"} ${assessmentConfig.type.charAt(0).toUpperCase() + assessmentConfig.type.slice(1)} - ${selectedStandards.slice(0, 2).join(", ")}${selectedStandards.length > 2 ? "..." : ""}`;

      const data = await api.generateAssessment(
        fullStandards,
        {
          grade: config.grade_level,
          subject: config.subject,
          teacher_name: config.teacher_name,
          globalAINotes: globalAINotes,
        },
        { ...assessmentConfig, title },
        selectedSources
      );

      if (data.error) {
        addToast("Error: " + data.error, "error");
      } else if (data.assessment) {
        setGeneratedAssessment(data.assessment);
        setAssessmentAnswers({}); // Clear previous answers
        addToast("Assessment generated successfully!", "success");
      }
    } catch (e) {
      addToast("Error generating assessment: " + e.message, "error");
    } finally {
      setAssessmentLoading(false);
    }
  };

  const exportAssessmentHandler = async (includeAnswerKey = false) => {
    if (!generatedAssessment) return;
    try {
      const data = await api.exportAssessment(generatedAssessment, includeAnswerKey);
      if (data.error) {
        addToast("Error exporting: " + data.error, "error");
      } else if (data.document) {
        // Download the document
        const link = document.createElement("a");
        link.href = "data:application/vnd.openxmlformats-officedocument.wordprocessingml.document;base64," + data.document;
        link.download = data.filename || "assessment.docx";
        link.click();
        addToast("Assessment exported!", "success");
      }
    } catch (e) {
      addToast("Error exporting: " + e.message, "error");
    }
  };

  const exportAssessmentForPlatformHandler = async (platform) => {
    if (!generatedAssessment) return;
    try {
      const data = await api.exportAssessmentForPlatform(generatedAssessment, platform);
      if (data.error) {
        addToast("Error exporting: " + data.error, "error");
      } else if (data.document) {
        const mimeTypes = {
          csv: "text/csv",
          xml: "application/xml",
          txt: "text/plain",
          json: "application/json",
        };
        const mimeType = mimeTypes[data.format] || data.mime_type || "application/octet-stream";
        const link = document.createElement("a");
        link.href = `data:${mimeType};base64,${data.document}`;
        link.download = data.filename;
        link.click();
        addToast(`Exported for ${platform}!`, "success");
      }
    } catch (e) {
      addToast("Error exporting: " + e.message, "error");
    }
  };

  // Open publish modal for assessment
  const publishAssessmentHandler = () => {
    if (!generatedAssessment) {
      addToast("No assessment to publish", "warning");
      return;
    }
    // Reset publish settings
    setPublishSettings({
      period: '',
      periodFilename: '',
      isMakeup: false,
      selectedStudents: [],
      timeLimit: null,
      applyAccommodations: true,
    });
    setPublishModalStudents([]);
    setShowPublishModal(true);
  };

  // Load students when period is selected in publish modal
  const loadPublishModalStudents = async (periodFilename) => {
    if (!periodFilename) {
      setPublishModalStudents([]);
      return;
    }
    setLoadingPublishStudents(true);
    try {
      const data = await api.getPeriodStudents(periodFilename);
      if (data.students) {
        setPublishModalStudents(data.students);
      }
    } catch (e) {
      console.error("Failed to load period students:", e);
      setPublishModalStudents([]);
    } finally {
      setLoadingPublishStudents(false);
    }
  };

  // Confirm and publish assessment with settings
  const confirmPublishAssessment = async () => {
    if (!generatedAssessment) return;

    setPublishingAssessment(true);
    try {
      // Build student accommodations map if applying accommodations
      let studentAccommodationsMap = {};
      if (publishSettings.applyAccommodations && publishModalStudents.length > 0) {
        publishModalStudents.forEach(student => {
          const studentId = student.id || student.email || (student.first + ' ' + student.last);
          const accommodation = studentAccommodations[studentId];
          if (accommodation) {
            studentAccommodationsMap[student.first + ' ' + student.last] = accommodation;
          }
        });
      }

      // Build restricted students list for makeup exams
      let restrictedStudents = null;
      if (publishSettings.isMakeup && publishSettings.selectedStudents.length > 0) {
        restrictedStudents = publishSettings.selectedStudents;
      }

      const data = await api.publishAssessmentToPortal(generatedAssessment, {
        teacher_name: config.teacher_name || "Teacher",
        teacher_email: config.teacher_email,
        show_correct_answers: true,
        show_score_immediately: true,
        period: publishSettings.period,
        restricted_students: restrictedStudents,
        student_accommodations: studentAccommodationsMap,
        time_limit_minutes: publishSettings.timeLimit,
      });

      if (data.error) {
        addToast("Error publishing: " + data.error, "error");
      } else if (data.success) {
        setShowPublishModal(false);
        setPublishedAssessmentModal({
          show: true,
          joinCode: data.join_code,
          joinLink: data.join_link,
        });
        addToast("Assessment published to student portal!", "success");
        // Refresh published assessments list
        fetchPublishedAssessments();
      }
    } catch (e) {
      addToast("Error publishing: " + e.message, "error");
    } finally {
      setPublishingAssessment(false);
    }
  };

  // Save assessment locally for later use (makeup exams)
  const saveAssessmentHandler = async () => {
    if (!generatedAssessment) {
      addToast("No assessment to save", "warning");
      return;
    }
    if (!saveAssessmentName.trim()) {
      addToast("Please enter a name for the assessment", "warning");
      return;
    }
    setSavingAssessment(true);
    try {
      const data = await api.saveAssessmentLocally(generatedAssessment, saveAssessmentName.trim());
      if (data.error) {
        addToast("Error saving: " + data.error, "error");
      } else if (data.success) {
        addToast("Assessment saved successfully!", "success");
        setSaveAssessmentName('');
        // Refresh saved assessments list
        fetchSavedAssessments();
      }
    } catch (e) {
      addToast("Error saving assessment: " + e.message, "error");
    } finally {
      setSavingAssessment(false);
    }
  };

  // Fetch saved lessons for assessment content sources
  const fetchSavedLessons = async () => {
    try {
      const data = await api.listLessons();
      if (data.units) {
        setSavedLessons(data);
        setSavedUnits(Object.keys(data.units));
      }
    } catch (e) {
      console.error("Error loading saved lessons:", e);
    }
  };

  // Fetch saved assessments
  const fetchSavedAssessments = async () => {
    setLoadingSavedAssessments(true);
    try {
      const data = await api.listSavedAssessments();
      if (data.assessments) {
        setSavedAssessments(data.assessments);
      }
    } catch (e) {
      console.error("Error loading saved assessments:", e);
    } finally {
      setLoadingSavedAssessments(false);
    }
  };

  // Load a saved assessment
  const loadSavedAssessment = async (filename) => {
    try {
      const data = await api.loadSavedAssessment(filename);
      if (data.error) {
        addToast("Error loading assessment: " + data.error, "error");
      } else if (data.assessment) {
        setGeneratedAssessment(data.assessment);
        setAssessmentAnswers({});
        setAssessmentGradingResults(null);
        addToast("Assessment loaded!", "success");
      }
    } catch (e) {
      addToast("Error loading assessment: " + e.message, "error");
    }
  };

  // Delete a saved assessment
  const deleteSavedAssessment = async (filename) => {
    if (!confirm("Delete this saved assessment?")) return;
    try {
      const data = await api.deleteSavedAssessment(filename);
      if (data.error) {
        addToast("Error deleting: " + data.error, "error");
      } else {
        addToast("Assessment deleted", "success");
        fetchSavedAssessments();
      }
    } catch (e) {
      addToast("Error deleting assessment: " + e.message, "error");
    }
  };

  // Grade assessment answers with AI
  const gradeAssessmentAnswersHandler = async () => {
    if (!generatedAssessment || Object.keys(assessmentAnswers).length === 0) {
      addToast("Please answer at least one question first", "warning");
      return;
    }
    setGradingAssessment(true);
    setAssessmentGradingResults(null);
    try {
      const data = await api.gradeAssessmentAnswers(generatedAssessment, assessmentAnswers);
      if (data.error) {
        addToast("Error grading: " + data.error, "error");
      } else if (data.results) {
        setAssessmentGradingResults(data.results);
        addToast(`Graded! Score: ${data.results.score}/${data.results.total_points} (${data.results.percentage}%)`, "success");
      }
    } catch (e) {
      addToast("Error grading assessment: " + e.message, "error");
    } finally {
      setGradingAssessment(false);
    }
  };

  // Fetch published assessments for teacher dashboard
  const fetchPublishedAssessments = async () => {
    setLoadingPublished(true);
    try {
      const data = await api.getPublishedAssessments();
      if (data.assessments) {
        setPublishedAssessments(data.assessments);
      }
    } catch (e) {
      addToast("Error loading assessments: " + e.message, "error");
    } finally {
      setLoadingPublished(false);
    }
  };

  // Fetch results for a specific assessment
  const fetchAssessmentResults = async (joinCode) => {
    setLoadingResults(true);
    try {
      const data = await api.getAssessmentResults(joinCode);
      if (data.error) {
        addToast("Error: " + data.error, "error");
      } else {
        setSelectedAssessmentResults({
          joinCode,
          title: data.title,
          submissions: data.submissions || [],
          stats: data.stats || {},
        });
      }
    } catch (e) {
      addToast("Error loading results: " + e.message, "error");
    } finally {
      setLoadingResults(false);
    }
  };

  // Toggle assessment active status
  const toggleAssessmentStatus = async (joinCode) => {
    try {
      const data = await api.toggleAssessmentStatus(joinCode);
      if (data.success) {
        addToast(data.is_active ? "Assessment activated" : "Assessment deactivated", "success");
        fetchPublishedAssessments();
      }
    } catch (e) {
      addToast("Error: " + e.message, "error");
    }
  };

  // Delete published assessment
  const deletePublishedAssessment = async (joinCode) => {
    if (!confirm("Delete this assessment and all its submissions?")) return;
    try {
      const data = await api.deletePublishedAssessment(joinCode);
      if (data.success) {
        addToast("Assessment deleted", "success");
        setPublishedAssessments(prev => prev.filter(a => a.join_code !== joinCode));
        if (selectedAssessmentResults?.joinCode === joinCode) {
          setSelectedAssessmentResults(null);
        }
      }
    } catch (e) {
      addToast("Error: " + e.message, "error");
    }
  };

  // Generate assignment from lesson plan
  const generateAssignmentFromLessonHandler = async () => {
    if (!lessonPlan) {
      addToast("Please generate a lesson plan first", "warning");
      return;
    }
    setAssignmentLoading(true);
    setGeneratedAssignment(null);
    try {
      const data = await api.generateAssignmentFromLesson(
        lessonPlan,
        {
          grade: config.grade_level,
          subject: config.subject,
          availableTools: config.availableTools || [],
        },
        assignmentType,
      );
      if (data.error) {
        addToast("Error: " + data.error, "warning");
      }
      if (data.assignment) {
        setGeneratedAssignment(data.assignment);
        addToast(
          `${assignmentType.charAt(0).toUpperCase() + assignmentType.slice(1)} generated from lesson!`,
          "success",
        );
      }
    } catch (e) {
      addToast("Error generating assignment: " + e.message, "error");
    } finally {
      setAssignmentLoading(false);
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

    // Also sync to status.results so the table updates immediately
    setStatus((prev) => {
      const updatedResults = [...prev.results];
      updatedResults[index] = { ...updatedResults[index], [field]: value, edited: true };
      if (field === "score") {
        const score = parseInt(value) || 0;
        updatedResults[index].letter_grade =
          score >= 90 ? "A" : score >= 80 ? "B" : score >= 70 ? "C" : score >= 60 ? "D" : "F";
      }
      return { ...prev, results: updatedResults };
    });
  };

  // Helper to get letter grade from score
  const getLetterGrade = (score) => {
    const s = parseInt(score) || 0;
    return s >= 90 ? "A" : s >= 80 ? "B" : s >= 70 ? "C" : s >= 60 ? "D" : "F";
  };

  // Apply curve to filtered results
  const applyCurve = () => {
    const { curveType, curveValue } = curveModal;
    const val = parseFloat(curveValue) || 0;
    if (val === 0) {
      addToast("Please enter a curve value", "warning");
      return;
    }

    // Get indices of filtered results (based on period filter)
    const filteredIndices = [];
    status.results.forEach((r, idx) => {
      if (resultsPeriodFilter && r.period !== resultsPeriodFilter) return;
      filteredIndices.push(idx);
    });

    if (filteredIndices.length === 0) {
      addToast("No results to curve", "warning");
      return;
    }

    // Apply curve to each result
    const newEditedResults = editedResults.length > 0 ? [...editedResults] : [...status.results];
    const newEditedEmails = { ...editedEmails };
    let curvedCount = 0;

    filteredIndices.forEach((idx) => {
      const result = status.results[idx];
      const oldScore = parseInt(result.score) || 0;
      const oldGrade = result.letter_grade || getLetterGrade(oldScore);

      // Calculate new score based on curve type
      let newScore;
      if (curveType === "add") {
        newScore = Math.min(100, Math.max(0, oldScore + val));
      } else if (curveType === "percent") {
        newScore = Math.min(100, Math.max(0, Math.round(oldScore * (1 + val / 100))));
      } else if (curveType === "set_min") {
        newScore = Math.max(val, oldScore);
      }

      const newGrade = getLetterGrade(newScore);

      // Skip if no change
      if (newScore === oldScore) return;

      curvedCount++;

      // Update the result
      if (!newEditedResults[idx]) newEditedResults[idx] = { ...result };
      newEditedResults[idx] = {
        ...newEditedResults[idx],
        score: newScore,
        letter_grade: newGrade,
        edited: true,
      };

      // Update feedback if it contains the old score/grade
      let feedback = newEditedResults[idx].feedback || "";
      if (feedback) {
        // Replace score patterns like "85/100" or "Score: 85"
        feedback = feedback.replace(new RegExp(oldScore + "/100", "g"), newScore + "/100");
        feedback = feedback.replace(new RegExp("Score:\\s*" + oldScore, "gi"), "Score: " + newScore);
        feedback = feedback.replace(new RegExp("\\b" + oldScore + "%", "g"), newScore + "%");
        // Replace letter grade if mentioned
        if (oldGrade !== newGrade) {
          feedback = feedback.replace(new RegExp("\\(" + oldGrade + "\\)", "g"), "(" + newGrade + ")");
          feedback = feedback.replace(new RegExp("Grade:\\s*" + oldGrade + "\\b", "gi"), "Grade: " + newGrade);
        }
        newEditedResults[idx].feedback = feedback;
      }

      // Update email if it exists
      if (newEditedEmails[idx]) {
        let subject = newEditedEmails[idx].subject || "";
        let body = newEditedEmails[idx].body || "";

        // Update subject
        subject = subject.replace(new RegExp(": " + oldGrade + "$"), ": " + newGrade);

        // Update body
        body = body.replace(new RegExp("GRADE: " + oldScore + "/100 \\(" + oldGrade + "\\)"), "GRADE: " + newScore + "/100 (" + newGrade + ")");
        body = body.replace(new RegExp(oldScore + "/100", "g"), newScore + "/100");

        newEditedEmails[idx] = { ...newEditedEmails[idx], subject, body };
      }
    });

    // Sync to state
    setEditedResults(newEditedResults);
    setEditedEmails(newEditedEmails);

    // Also update status.results
    setStatus((prev) => {
      const updatedResults = [...prev.results];
      filteredIndices.forEach((idx) => {
        if (newEditedResults[idx]) {
          updatedResults[idx] = { ...newEditedResults[idx] };
        }
      });
      return { ...prev, results: updatedResults };
    });

    setCurveModal({ ...curveModal, show: false });
    addToast(`Applied ${curveType === "add" ? "+" + val + " points" : curveType === "percent" ? "+" + val + "%" : "min " + val} curve to ${curvedCount} result${curvedCount !== 1 ? "s" : ""}`, "success");
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
      const data = await api.sendEmails(results, config.teacher_email, config.teacher_name, config.email_signature);
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

  // Send email for a single student
  const sendSingleEmail = async (result, index) => {
    const edited = editedEmails[index];
    const emailToUse = edited?.email || result.student_email;
    if (!emailToUse) {
      addToast("No email address for " + result.student_name, "error");
      return;
    }
    try {
      const emailResult = {
        ...result,
        student_email: emailToUse,
        custom_email_subject: edited?.subject || `Grade Report: ${result.assignment}`,
        custom_email_body: edited?.body || getDefaultEmailBody(index),
      };
      const response = await api.sendEmails([emailResult], config.teacher_email, config.teacher_name, config.email_signature);
      if (response.sent > 0) {
        addToast(`Email sent to ${result.student_name}`, "success");
      } else {
        addToast(`Failed to send email to ${result.student_name}`, "error");
      }
    } catch (e) {
      addToast("Error sending email: " + e.message, "error");
    }
  };

  // Update approval status with persistence
  const updateApprovalStatus = async (index, approval) => {
    setEmailApprovals((prev) => ({ ...prev, [index]: approval }));
    // Persist to backend
    const result = status.results[index];
    if (result?.filename) {
      try {
        await api.updateApproval(result.filename, approval);
      } catch (e) {
        console.error("Error saving approval:", e);
      }
    }
  };

  // Bulk update approvals with persistence
  const updateApprovalsBulk = async (approvals) => {
    setEmailApprovals(approvals);
    // Build filename -> approval map for API
    const filenameApprovals = {};
    Object.entries(approvals).forEach(([idx, approval]) => {
      const result = status.results[parseInt(idx)];
      if (result?.filename) {
        filenameApprovals[result.filename] = approval;
      }
    });
    if (Object.keys(filenameApprovals).length > 0) {
      try {
        await api.updateApprovalsBulk(filenameApprovals);
      } catch (e) {
        console.error("Error saving approvals:", e);
      }
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
            <div>
              <h2 style={{ fontSize: "1.4rem", fontWeight: 700, margin: 0 }}>
                Review:{" "}
                {
                  (
                    editedResults[reviewModal.index] ||
                    status.results[reviewModal.index]
                  )?.student_name
                }
              </h2>
              <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", margin: "4px 0 0 0" }}>
                {
                  (
                    editedResults[reviewModal.index] ||
                    status.results[reviewModal.index]
                  )?.assignment ||
                  (
                    editedResults[reviewModal.index] ||
                    status.results[reviewModal.index]
                  )?.filename
                }
              </p>
            </div>
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
              onMouseEnter={(e) =>
                (e.currentTarget.style.background = "var(--glass-hover)")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.background = "var(--glass-bg)")
              }
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
                            background:
                              reviewModalTab === "detected"
                                ? "linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))"
                                : "var(--glass-hover)",
                            color:
                              reviewModalTab === "detected"
                                ? "#fff"
                                : "var(--text-secondary)",
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
                          Responses
                        </button>
                        <button
                          onClick={() => setReviewModalTab("raw")}
                          style={{
                            padding: "8px 16px",
                            borderRadius: "8px",
                            border: "none",
                            background:
                              reviewModalTab === "raw"
                                ? "linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))"
                                : "var(--glass-hover)",
                            color:
                              reviewModalTab === "raw"
                                ? "#fff"
                                : "var(--text-secondary)",
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
                            addToast(
                              "Could not open file: " + e.message,
                              "error",
                            );
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
                        onMouseEnter={(e) =>
                          (e.currentTarget.style.background =
                            "var(--glass-hover)")
                        }
                        onMouseLeave={(e) =>
                          (e.currentTarget.style.background = "var(--glass-bg)")
                        }
                      >
                        <Icon name="ExternalLink" size={14} />
                        Open Original
                      </button>
                    </div>

                    {/* Tab Content */}
                    <div style={{ flex: 1, overflow: "auto", padding: "20px" }}>
                      {reviewModalTab === "detected" ? (
                        <div
                          style={{
                            display: "flex",
                            flexDirection: "column",
                            gap: "16px",
                          }}
                        >
                          {/* Student Responses */}
                          {r.student_responses &&
                          r.student_responses.length > 0 ? (
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
                                Detected Responses ({r.student_responses.length}
                                )
                              </div>
                              <div
                                style={{
                                  display: "flex",
                                  flexDirection: "column",
                                  gap: "10px",
                                }}
                              >
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
                          {r.unanswered_questions &&
                            r.unanswered_questions.length > 0 && (
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
                            overflowY: "auto",
                          }}
                        >
                          {r.is_handwritten ? (
                            <div style={{ textAlign: "center" }}>
                              <div
                                style={{
                                  display: "flex",
                                  alignItems: "center",
                                  justifyContent: "center",
                                  gap: "8px",
                                  marginBottom: "15px",
                                  color: "#10b981",
                                  fontWeight: 500,
                                }}
                              >
                                <Icon name="PenTool" size={18} />
                                Handwritten Assignment
                              </div>
                              {r.original_image_path ? (
                                <div>
                                  <p
                                    style={{
                                      fontSize: "0.85rem",
                                      color: "var(--text-muted)",
                                      marginBottom: "15px",
                                    }}
                                  >
                                    Original image saved to output folder
                                  </p>
                                  <button
                                    onClick={() =>
                                      api.openFolder(config.output_folder)
                                    }
                                    className="btn btn-secondary"
                                    style={{ margin: "0 auto" }}
                                  >
                                    <Icon name="FolderOpen" size={16} />
                                    Open Output Folder
                                  </button>
                                </div>
                              ) : (
                                <p
                                  style={{
                                    fontSize: "0.85rem",
                                    color: "var(--text-muted)",
                                  }}
                                >
                                  Handwritten responses were extracted by AI
                                  vision.
                                  <br />
                                  Check the "Responses" tab to see extracted
                                  answers.
                                </p>
                              )}
                            </div>
                          ) : (
                            <div
                              style={{
                                whiteSpace: "pre-wrap",
                                fontSize: "22px",
                                lineHeight: 1.7,
                                color: "var(--text-secondary)",
                                fontFamily: "monospace",
                              }}
                            >
                              {r.full_content ||
                                r.student_content ||
                                "[No content - click Open Original to view]"}
                            </div>
                          )}
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
                    {/* Right Panel Header with Tabs */}
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
                          onClick={() => setReviewModalRightTab("edit")}
                          style={{
                            padding: "8px 16px",
                            borderRadius: "8px",
                            border: "none",
                            background:
                              reviewModalRightTab === "edit"
                                ? "linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))"
                                : "var(--glass-hover)",
                            color:
                              reviewModalRightTab === "edit"
                                ? "#fff"
                                : "var(--text-secondary)",
                            fontWeight: 600,
                            fontSize: "0.85rem",
                            cursor: "pointer",
                            transition: "all 0.2s",
                            display: "flex",
                            alignItems: "center",
                            gap: "6px",
                          }}
                        >
                          <Icon name="Award" size={14} />
                          Grade & Feedback
                        </button>
                        <button
                          onClick={() => setReviewModalRightTab("email")}
                          style={{
                            padding: "8px 16px",
                            borderRadius: "8px",
                            border: "none",
                            background:
                              reviewModalRightTab === "email"
                                ? "linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))"
                                : "var(--glass-hover)",
                            color:
                              reviewModalRightTab === "email"
                                ? "#fff"
                                : "var(--text-secondary)",
                            fontWeight: 600,
                            fontSize: "0.85rem",
                            cursor: "pointer",
                            transition: "all 0.2s",
                            display: "flex",
                            alignItems: "center",
                            gap: "6px",
                          }}
                        >
                          <Icon name="Mail" size={14} />
                          Email Preview
                        </button>
                      </div>
                    </div>

                    {/* Right Panel Content */}
                    {reviewModalRightTab === "edit" ? (
                      <div
                        style={{
                          flex: 1,
                          padding: "20px",
                          display: "flex",
                          flexDirection: "column",
                          gap: "20px",
                          overflow: "auto",
                        }}
                      >
                        <div>
                          <label className="label">Score</label>
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "12px",
                            }}
                          >
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
                        <div
                          style={{
                            flex: 1,
                            display: "flex",
                            flexDirection: "column",
                          }}
                        >
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                              marginBottom: "6px",
                            }}
                          >
                            <label className="label" style={{ margin: 0 }}>
                              Feedback
                            </label>
                            {r.feedback && r.feedback.includes("---") && (
                              <button
                                onClick={async () => {
                                  const parts = r.feedback.split("---");
                                  if (parts.length >= 2) {
                                    const englishPart = parts[0].trim();
                                    try {
                                      const result =
                                        await api.retranslateFeedback(
                                          englishPart,
                                          r.student_language || "spanish",
                                        );
                                      if (result.translation) {
                                        const newFeedback =
                                          englishPart +
                                          "\n\n---\n\n" +
                                          result.translation;
                                        updateGrade(
                                          reviewModal.index,
                                          "feedback",
                                          newFeedback,
                                        );
                                      } else if (result.error) {
                                        addToast(
                                          "Translation error: " + result.error,
                                          "error",
                                        );
                                      }
                                    } catch (err) {
                                      addToast(
                                        "Failed to translate: " + err.message,
                                        "error",
                                      );
                                    }
                                  }
                                }}
                                style={{
                                  background: "rgba(99,102,241,0.1)",
                                  border: "1px solid rgba(99,102,241,0.3)",
                                  borderRadius: "6px",
                                  padding: "4px 10px",
                                  fontSize: "0.75rem",
                                  color: "#6366f1",
                                  cursor: "pointer",
                                  display: "flex",
                                  alignItems: "center",
                                  gap: "4px",
                                }}
                              >
                                <Icon name="Languages" size={12} />
                                Re-translate
                              </button>
                            )}
                          </div>
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
                            style={{
                              flex: 1,
                              minHeight: "200px",
                              resize: "none",
                            }}
                          />
                        </div>
                      </div>
                    ) : (
                      <div
                        style={{ flex: 1, padding: "20px", overflow: "auto" }}
                      >
                        <div
                          style={{
                            background: "#fff",
                            borderRadius: "12px",
                            padding: "30px",
                            color: "#333",
                            fontFamily: "Georgia, serif",
                            lineHeight: 1.7,
                            boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
                          }}
                        >
                          <div
                            style={{
                              marginBottom: "20px",
                              paddingBottom: "15px",
                              borderBottom: "1px solid #eee",
                            }}
                          >
                            <div
                              style={{
                                fontSize: "0.85rem",
                                color: "#666",
                                marginBottom: "4px",
                                display: "flex",
                                alignItems: "center",
                                gap: "8px",
                              }}
                            >
                              <span>To:</span>
                              <input
                                type="email"
                                value={editedEmails[reviewModal.index]?.email ?? r.student_email ?? r.email ?? ""}
                                onChange={(e) => {
                                  const newEmail = e.target.value;
                                  const studentId = r.student_id;
                                  const studentName = r.student_name;

                                  // Update editedEmails for ALL results with the same student
                                  setEditedEmails((prev) => {
                                    const updated = { ...prev };
                                    status.results.forEach((result, idx) => {
                                      if ((studentId && result.student_id === studentId) ||
                                          (studentName && result.student_name === studentName)) {
                                        updated[idx] = {
                                          ...prev[idx],
                                          email: newEmail,
                                        };
                                      }
                                    });
                                    return updated;
                                  });

                                  // Also update status.results so it persists when saved
                                  setStatus((prev) => ({
                                    ...prev,
                                    results: prev.results.map((result) => {
                                      if ((studentId && result.student_id === studentId) ||
                                          (studentName && result.student_name === studentName)) {
                                        return { ...result, student_email: newEmail };
                                      }
                                      return result;
                                    }),
                                  }));
                                }}
                                placeholder="Enter student email..."
                                style={{
                                  flex: 1,
                                  padding: "4px 8px",
                                  border: (editedEmails[reviewModal.index]?.email ?? r.student_email ?? r.email) ? "1px solid #ddd" : "1px solid #f87171",
                                  borderRadius: "4px",
                                  fontSize: "0.85rem",
                                  background: (editedEmails[reviewModal.index]?.email ?? r.student_email ?? r.email) ? "#fff" : "#fef2f2",
                                }}
                              />
                              {!(r.student_email || r.email) && !editedEmails[reviewModal.index]?.email && (
                                <span style={{ color: "#f87171", fontSize: "0.75rem" }}>
                                  (not found)
                                </span>
                              )}
                            </div>
                            <div
                              style={{
                                fontSize: "0.85rem",
                                color: "#666",
                                marginBottom: "4px",
                              }}
                            >
                              Subject: {r.assignment || "Assignment"} - Grade:{" "}
                              {r.letter_grade} ({r.score}%)
                            </div>
                          </div>
                          <div style={{ marginBottom: "20px" }}>
                            <p style={{ margin: "0 0 15px 0" }}>
                              Dear{" "}
                              {r.first_name ||
                                r.student_name?.split(" ")[0] ||
                                "Student"}
                              ,
                            </p>
                            <p style={{ margin: "0 0 15px 0" }}>
                              Your assignment{" "}
                              <strong>{r.assignment || "Assignment"}</strong>{" "}
                              has been graded.
                            </p>
                            <div
                              style={{
                                background:
                                  r.score >= 90
                                    ? "#dcfce7"
                                    : r.score >= 80
                                      ? "#dbeafe"
                                      : r.score >= 70
                                        ? "#fef3c7"
                                        : "#fee2e2",
                                padding: "15px 20px",
                                borderRadius: "8px",
                                marginBottom: "20px",
                                textAlign: "center",
                              }}
                            >
                              <div
                                style={{
                                  fontSize: "2rem",
                                  fontWeight: 700,
                                  color:
                                    r.score >= 90
                                      ? "#16a34a"
                                      : r.score >= 80
                                        ? "#2563eb"
                                        : r.score >= 70
                                          ? "#d97706"
                                          : "#dc2626",
                                }}
                              >
                                {r.letter_grade}
                              </div>
                              <div style={{ fontSize: "1rem", color: "#666" }}>
                                {r.score} / 100
                              </div>
                            </div>
                          </div>
                          <div style={{ marginBottom: "20px" }}>
                            <h4
                              style={{
                                margin: "0 0 10px 0",
                                fontSize: "1rem",
                                color: "#333",
                              }}
                            >
                              Feedback:
                            </h4>
                            <div
                              style={{ whiteSpace: "pre-wrap", color: "#444" }}
                            >
                              {r.feedback || "(No feedback provided)"}
                            </div>
                          </div>
                          <p
                            style={{
                              margin: "20px 0 0 0",
                              color: "#666",
                              fontSize: "0.9rem",
                            }}
                          >
                            If you have any questions about your grade, please
                            see me during class or office hours.
                          </p>
                          <div style={{ margin: "15px 0 0 0", color: "#666", whiteSpace: "pre-wrap" }}>
                            {config.email_signature ? (
                              config.email_signature
                            ) : (
                              <>
                                Best regards,
                                <br />
                                <strong>
                                  {config.teacher_name || "Your Teacher"}
                                </strong>
                                {config.school_name && (
                                  <>
                                    <br />
                                    <span>{config.school_name}</span>
                                  </>
                                )}
                              </>
                            )}
                          </div>
                        </div>
                        {/* Approve/Reject Buttons */}
                        {!autoApproveEmails && (
                          <div
                            style={{
                              marginTop: "20px",
                              display: "flex",
                              gap: "10px",
                              justifyContent: "center",
                            }}
                          >
                            <button
                              onClick={() => {
                                updateApprovalStatus(reviewModal.index, "approved");
                                addToast(
                                  "Email approved for sending",
                                  "success",
                                );
                              }}
                              className="btn"
                              style={{
                                padding: "10px 24px",
                                background:
                                  emailApprovals[reviewModal.index] ===
                                  "approved"
                                    ? "linear-gradient(135deg, #22c55e, #16a34a)"
                                    : "rgba(74,222,128,0.15)",
                                border:
                                  emailApprovals[reviewModal.index] ===
                                  "approved"
                                    ? "none"
                                    : "1px solid rgba(74,222,128,0.3)",
                                color:
                                  emailApprovals[reviewModal.index] ===
                                  "approved"
                                    ? "#fff"
                                    : "#4ade80",
                              }}
                            >
                              <Icon name="Check" size={18} />
                              {emailApprovals[reviewModal.index] === "approved"
                                ? "Approved"
                                : "Approve Email"}
                            </button>
                            <button
                              onClick={() => {
                                updateApprovalStatus(reviewModal.index, "rejected");
                                addToast("Email marked as rejected", "info");
                              }}
                              className="btn"
                              style={{
                                padding: "10px 24px",
                                background:
                                  emailApprovals[reviewModal.index] ===
                                  "rejected"
                                    ? "rgba(248,113,113,0.2)"
                                    : "var(--glass-bg)",
                                border: "1px solid var(--glass-border)",
                                color:
                                  emailApprovals[reviewModal.index] ===
                                  "rejected"
                                    ? "#f87171"
                                    : "var(--text-secondary)",
                              }}
                            >
                              <Icon name="X" size={18} />
                              {emailApprovals[reviewModal.index] === "rejected"
                                ? "Rejected"
                                : "Reject"}
                            </button>
                            <button
                              onClick={() => {
                                updateApprovalStatus(reviewModal.index, "approved");
                                setSentEmails((prev) => ({
                                  ...prev,
                                  [reviewModal.index]: true,
                                }));
                                addToast("Marked as sent (no email sent)", "info");
                              }}
                              className="btn"
                              style={{
                                padding: "10px 24px",
                                background: sentEmails[reviewModal.index]
                                  ? "rgba(59,130,246,0.25)"
                                  : "var(--glass-bg)",
                                border: sentEmails[reviewModal.index]
                                  ? "1px solid rgba(59,130,246,0.4)"
                                  : "1px solid var(--glass-border)",
                                color: sentEmails[reviewModal.index]
                                  ? "#3b82f6"
                                  : "var(--text-secondary)",
                              }}
                            >
                              <Icon name="Send" size={18} />
                              {sentEmails[reviewModal.index]
                                ? "Sent"
                                : "Mark as Sent"}
                            </button>
                          </div>
                        )}
                        <p
                          style={{
                            marginTop: "15px",
                            fontSize: "0.8rem",
                            color: "var(--text-muted)",
                            textAlign: "center",
                          }}
                        >
                          <Icon
                            name="Info"
                            size={12}
                            style={{
                              marginRight: "4px",
                              verticalAlign: "middle",
                            }}
                          />
                          Editing feedback in "Grade & Feedback" tab updates
                          this preview automatically
                        </p>
                      </div>
                    )}
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
              <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                {(assignment.customMarkers || []).length} markers selected
              </span>
            </div>
            <div style={{ display: "flex", gap: "10px" }}>
              <button
                onClick={() => {
                  // Reset everything and close
                  setAssignment({
                    title: "",
                    subject: "Social Studies",
                    totalPoints: 100,
                    instructions: "",
                    questions: [],
                    customMarkers: [],
                    excludeMarkers: [],
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
                  setDocEditorModal({ ...docEditorModal, show: false });
                }}
                className="btn btn-ghost"
                style={{ padding: "8px" }}
                title="Cancel and reset"
              >
                <Icon name="X" size={18} />
              </button>
              {/* Highlighter Mode Toggle */}
              <div style={{ display: "flex", borderRadius: "8px", overflow: "hidden", border: "1px solid var(--glass-border)" }}>
                <button
                  onClick={() => setHighlighterMode("start")}
                  style={{
                    padding: "8px 12px",
                    background: highlighterMode === "start" ? HIGHLIGHT_COLORS.start.bg : "transparent",
                    border: "none",
                    borderRight: "1px solid var(--glass-border)",
                    color: highlighterMode === "start" ? HIGHLIGHT_COLORS.start.border : "var(--text-muted)",
                    fontWeight: highlighterMode === "start" ? 600 : 400,
                    cursor: "pointer",
                    fontSize: "0.85rem",
                    display: "flex",
                    alignItems: "center",
                    gap: "4px",
                  }}
                >
                  <span style={{ width: "10px", height: "10px", borderRadius: "50%", background: HIGHLIGHT_COLORS.start.border }} />
                  Start
                </button>
                <button
                  onClick={() => setHighlighterMode("end")}
                  style={{
                    padding: "8px 12px",
                    background: highlighterMode === "end" ? HIGHLIGHT_COLORS.end.bg : "transparent",
                    border: "none",
                    borderRight: "1px solid var(--glass-border)",
                    color: highlighterMode === "end" ? HIGHLIGHT_COLORS.end.border : "var(--text-muted)",
                    fontWeight: highlighterMode === "end" ? 600 : 400,
                    cursor: "pointer",
                    fontSize: "0.85rem",
                    display: "flex",
                    alignItems: "center",
                    gap: "4px",
                  }}
                >
                  <span style={{ width: "10px", height: "10px", borderRadius: "50%", background: HIGHLIGHT_COLORS.end.border }} />
                  End
                </button>
                <button
                  onClick={() => setHighlighterMode("exclude")}
                  style={{
                    padding: "8px 12px",
                    background: highlighterMode === "exclude" ? HIGHLIGHT_COLORS.exclude.bg : "transparent",
                    border: "none",
                    color: highlighterMode === "exclude" ? HIGHLIGHT_COLORS.exclude.border : "var(--text-muted)",
                    fontWeight: highlighterMode === "exclude" ? 600 : 400,
                    cursor: "pointer",
                    fontSize: "0.85rem",
                    display: "flex",
                    alignItems: "center",
                    gap: "4px",
                  }}
                >
                  <span style={{ width: "10px", height: "10px", borderRadius: "50%", background: HIGHLIGHT_COLORS.exclude.border }} />
                  Exclude
                </button>
              </div>
              <button
                onClick={addSelectedAsMarker}
                className="btn btn-secondary"
                style={{
                  background: HIGHLIGHT_COLORS[highlighterMode].bg,
                  borderColor: HIGHLIGHT_COLORS[highlighterMode].border,
                }}
              >
                <Icon name="Target" size={16} />
                Mark {HIGHLIGHT_COLORS[highlighterMode].label}
              </button>
              <button
                onClick={async () => {
                  // Save assignment if it has a title and markers
                  if (
                    assignment.title &&
                    (assignment.customMarkers || []).length > 0
                  ) {
                    try {
                      // Include highlighted HTML in the saved data
                      const docToSave = { ...importedDoc, html: docEditorModal.editedHtml };
                      const dataToSave = { ...assignment, importedDoc: docToSave };
                      await api.saveAssignmentConfig(dataToSave);
                      // Refresh saved assignments list
                      const list = await api.listAssignments();
                      if (list.assignments)
                        setSavedAssignments(list.assignments);
                      if (list.assignmentData)
                        setSavedAssignmentData(list.assignmentData);
                    } catch (error) {
                      console.error("Failed to save assignment:", error);
                    }
                  }
                  // Reset the form for a new assignment
                  setAssignment({
                    title: "",
                    subject: "Social Studies",
                    totalPoints: 100,
                    instructions: "",
                    questions: [],
                    customMarkers: [],
                    excludeMarkers: [],
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
                  setDocEditorModal({ ...docEditorModal, show: false });
                }}
                className="btn btn-primary"
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
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "15px" }}>
                <h3 style={{ fontSize: "1rem", margin: 0 }}>
                  Marked Sections ({(assignment.customMarkers || []).length})
                </h3>
                {(assignment.customMarkers || []).length > 0 && (
                  <button
                    onClick={() => {
                      if (!confirm("Remove all markers and highlights?")) return;
                      const cleanHtml = removeAllHighlightsFromHtml(docEditorModal.editedHtml);
                      setAssignment({ ...assignment, customMarkers: [] });
                      setDocEditorModal({ ...docEditorModal, editedHtml: cleanHtml });
                      setImportedDoc({ ...importedDoc, html: cleanHtml });
                      addToast("All markers cleared", "success");
                    }}
                    style={{
                      background: "none",
                      border: "1px solid rgba(239,68,68,0.3)",
                      color: "#ef4444",
                      padding: "4px 8px",
                      borderRadius: "4px",
                      fontSize: "0.75rem",
                      cursor: "pointer",
                    }}
                  >
                    Clear All
                  </button>
                )}
              </div>
              <p
                style={{
                  fontSize: "0.85rem",
                  color: "var(--text-muted)",
                  marginBottom: "15px",
                }}
              >
                Select text and use <span style={{color: HIGHLIGHT_COLORS.start.border, fontWeight: 600}}>Start</span> (green) to mark section beginnings, <span style={{color: HIGHLIGHT_COLORS.end.border, fontWeight: 600}}>End</span> (red) to mark where they stop
              </p>
              {(assignment.customMarkers || []).length === 0 ? (
                <div>
                  <p style={{ color: "var(--text-muted)", fontSize: "0.9rem", marginBottom: "10px" }}>
                    No markers yet
                  </p>
                  {docEditorModal.editedHtml && docEditorModal.editedHtml.includes('data-marker-id=') && (
                    <button
                      onClick={() => {
                        const cleanHtml = removeAllHighlightsFromHtml(docEditorModal.editedHtml);
                        setDocEditorModal({ ...docEditorModal, editedHtml: cleanHtml });
                        setImportedDoc({ ...importedDoc, html: cleanHtml });
                        addToast("Orphaned highlights removed", "success");
                      }}
                      className="btn btn-secondary"
                      style={{
                        fontSize: "0.8rem",
                        padding: "6px 12px",
                        background: "rgba(239,68,68,0.15)",
                        border: "1px solid rgba(239,68,68,0.3)",
                        color: "#ef4444",
                      }}
                    >
                      <Icon name="Trash2" size={14} />
                      Remove Orphaned Highlights
                    </button>
                  )}
                </div>
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
                        flexDirection: "column",
                        gap: "4px",
                        padding: "8px 12px",
                        background: "rgba(251,191,36,0.2)",
                        borderRadius: "6px",
                        border: "1px solid rgba(251,191,36,0.3)",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <Icon
                          name="Target"
                          size={12}
                          style={{ color: "#22c55e", flexShrink: 0 }}
                        />
                        <span
                          style={{
                            fontSize: "0.8rem",
                            flex: 1,
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                          }}
                        >
                          {getMarkerText(marker).substring(0, 60)}{getMarkerText(marker).length > 60 ? '...' : ''}
                        </span>
                        <button
                          onClick={() => removeMarker(marker, i)}
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
                      {/* End marker display */}
                      {getEndMarker(marker) && (
                        <div style={{ display: "flex", alignItems: "center", gap: "6px", marginLeft: "20px" }}>
                          <Icon name="Flag" size={10} style={{ color: HIGHLIGHT_COLORS.end.border, flexShrink: 0 }} />
                          <span style={{ fontSize: "0.75rem", color: HIGHLIGHT_COLORS.end.border }}>
                            End: {getEndMarker(marker).substring(0, 40)}{getEndMarker(marker).length > 40 ? '...' : ''}
                          </span>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Excluded Sections */}
              {(assignment.excludeMarkers || []).length > 0 && (
                <div style={{ marginTop: "20px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
                    <h3 style={{ fontSize: "0.95rem", margin: 0, color: HIGHLIGHT_COLORS.exclude.border }}>
                      <Icon name="EyeOff" size={14} style={{ marginRight: "6px" }} />
                      Excluded Sections ({(assignment.excludeMarkers || []).length})
                    </h3>
                    <button
                      onClick={() => {
                        if (!confirm("Remove all exclude markers?")) return;
                        // Remove exclude highlights from HTML
                        let cleanHtml = docEditorModal.editedHtml;
                        (assignment.excludeMarkers || []).forEach((_, idx) => {
                          const regex = new RegExp(`<span[^>]*data-marker-id="exclude-${idx}"[^>]*>(.*?)</span>`, 'gi');
                          cleanHtml = cleanHtml.replace(regex, '$1');
                        });
                        setDocEditorModal({ ...docEditorModal, editedHtml: cleanHtml });
                        setAssignment({ ...assignment, excludeMarkers: [] });
                        addToast("All exclude markers cleared", "info");
                      }}
                      style={{
                        background: "none",
                        border: "none",
                        color: "var(--text-muted)",
                        cursor: "pointer",
                        fontSize: "0.75rem",
                      }}
                    >
                      Clear all
                    </button>
                  </div>
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: "8px",
                    }}
                  >
                    {(assignment.excludeMarkers || []).map((marker, i) => (
                      <div
                        key={i}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "8px",
                          padding: "8px 12px",
                          background: HIGHLIGHT_COLORS.exclude.bg,
                          borderRadius: "6px",
                          border: `1px solid ${HIGHLIGHT_COLORS.exclude.border}`,
                        }}
                      >
                        <Icon
                          name="EyeOff"
                          size={12}
                          style={{ color: HIGHLIGHT_COLORS.exclude.border, flexShrink: 0 }}
                        />
                        <span
                          style={{
                            fontSize: "0.8rem",
                            flex: 1,
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            color: HIGHLIGHT_COLORS.exclude.border,
                          }}
                        >
                          {marker.substring(0, 60)}{marker.length > 60 ? '...' : ''}
                        </span>
                        <button
                          onClick={() => {
                            // Remove this exclude marker
                            const newExcludeMarkers = [...(assignment.excludeMarkers || [])];
                            newExcludeMarkers.splice(i, 1);
                            // Remove highlight from HTML
                            const regex = new RegExp(`<span[^>]*data-marker-id="exclude-${i}"[^>]*>(.*?)</span>`, 'gi');
                            const cleanHtml = docEditorModal.editedHtml.replace(regex, '$1');
                            setDocEditorModal({ ...docEditorModal, editedHtml: cleanHtml });
                            setAssignment({ ...assignment, excludeMarkers: newExcludeMarkers });
                            addToast("Exclude marker removed", "info");
                          }}
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
                  <p style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginTop: "8px", fontStyle: "italic" }}>
                    These sections will NOT be graded or penalized.
                  </p>
                </div>
              )}

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
            background:
              theme === "dark"
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
              e.currentTarget.style.background =
                theme === "dark" ? "#1f1f2a" : "#ffffff";
              e.currentTarget.style.color = "var(--text-secondary)";
              e.currentTarget.style.borderColor =
                theme === "dark" ? "rgba(255,255,255,0.15)" : "rgba(0,0,0,0.1)";
            }}
          >
            <Icon
              name={sidebarCollapsed ? "ChevronRight" : "ChevronLeft"}
              size={14}
            />
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
          <nav
            style={{
              flex: 1,
              padding: sidebarCollapsed ? "10px 8px 0 8px" : "0 10px",
              marginTop: sidebarCollapsed ? "0" : "0",
            }}
          >
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
                  lineHeight: "1.4",
                }}
              >
                AI-Powered Teacher's Assistant
                <br />
                Made for Educators by Educators with ❤️
                <br />
                Powered by ChatGPT 4o
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
            maxWidth: sidebarCollapsed
              ? "calc(100vw - 70px)"
              : "calc(100vw - 260px)",
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
              <div
                style={{ display: "flex", alignItems: "center", gap: "10px" }}
              >
                <Icon
                  name="Zap"
                  size={18}
                  style={{ color: autoGrade ? "#4ade80" : "var(--text-muted)" }}
                />
                <span style={{ fontSize: "0.9rem", fontWeight: 500 }}>
                  Auto-Grade
                </span>
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
                  <span
                    style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}
                  >
                    Last: {watchStatus.lastCheck}
                  </span>
                )}
              </div>
              <div
                style={{
                  width: "1px",
                  height: "24px",
                  background: "var(--glass-border)",
                }}
              />
              {!status.is_running ? (
                <button
                  onClick={handleStartGrading}
                  className="btn btn-primary"
                  style={{ padding: "8px 20px" }}
                >
                  <Icon name="Play" size={16} />
                  Start Grading
                </button>
              ) : (
                <button
                  onClick={handleStopGrading}
                  className="btn btn-danger"
                  style={{ padding: "8px 20px" }}
                >
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
              title={
                theme === "dark"
                  ? "Switch to Light Mode"
                  : "Switch to Dark Mode"
              }
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
                      <Icon
                        name="AlertTriangle"
                        size={24}
                        style={{ color: "#f87171" }}
                      />
                      <div style={{ flex: 1 }}>
                        <div
                          style={{
                            fontWeight: 600,
                            color: "#f87171",
                            marginBottom: "4px",
                          }}
                        >
                          Grading Stopped - Error Detected
                        </div>
                        <div
                          style={{
                            fontSize: "0.9rem",
                            color: "var(--text-secondary)",
                          }}
                        >
                          {status.error}
                        </div>
                      </div>
                      <button
                        onClick={() =>
                          setStatus((prev) => ({ ...prev, error: null }))
                        }
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

                  {/* Assignment Grading Modes - Collapsible */}
                  {savedAssignments.length > 0 && (
                    <div
                      className="glass-card"
                      style={{
                        padding: gradingModesExpanded ? "15px 20px" : "12px 20px",
                        marginBottom: "20px",
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          cursor: "pointer",
                        }}
                        onClick={() => setGradingModesExpanded(!gradingModesExpanded)}
                      >
                        <h3
                          style={{
                            fontSize: "1rem",
                            fontWeight: 600,
                            display: "flex",
                            alignItems: "center",
                            gap: "10px",
                            margin: 0,
                          }}
                        >
                          <Icon
                            name={gradingModesExpanded ? "ChevronDown" : "ChevronRight"}
                            size={18}
                          />
                          <Icon name="FileCheck" size={18} style={{ color: "#10b981" }} />
                          Assignment Grading Modes
                          <span
                            style={{
                              fontSize: "0.8rem",
                              color: "var(--text-muted)",
                              fontWeight: 400,
                            }}
                          >
                            ({savedAssignments.filter(n => savedAssignmentData[n]?.completionOnly).length} completion-only)
                          </span>
                        </h3>
                      </div>

                      {gradingModesExpanded && (
                        <div style={{ marginTop: "15px" }}>
                          <p
                            style={{
                              fontSize: "0.85rem",
                              color: "var(--text-muted)",
                              marginBottom: "12px",
                            }}
                          >
                            Toggle assignments between AI grading and completion-only tracking.
                          </p>
                          <div
                            style={{
                              display: "flex",
                              flexDirection: "column",
                              gap: "8px",
                              maxHeight: "250px",
                              overflowY: "auto",
                            }}
                          >
                            {savedAssignments.map((name) => {
                              const isCompletionOnly = savedAssignmentData[name]?.completionOnly || false;
                              return (
                                <div
                                  key={name}
                                  style={{
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "space-between",
                                    padding: "10px 12px",
                                    borderRadius: "8px",
                                    background: isCompletionOnly
                                      ? "rgba(34, 197, 94, 0.1)"
                                      : "rgba(99, 102, 241, 0.05)",
                                    border: isCompletionOnly
                                      ? "1px solid rgba(34, 197, 94, 0.3)"
                                      : "1px solid var(--glass-border)",
                                  }}
                                >
                                  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                                    <Icon
                                      name={isCompletionOnly ? "CheckCircle" : "FileText"}
                                      size={18}
                                      style={{ color: isCompletionOnly ? "#22c55e" : "#6366f1" }}
                                    />
                                    <span style={{ fontWeight: 500 }}>{name}</span>
                                    {isCompletionOnly && (
                                      <span
                                        style={{
                                          fontSize: "0.7rem",
                                          background: "rgba(34, 197, 94, 0.2)",
                                          color: "#22c55e",
                                          padding: "2px 8px",
                                          borderRadius: "10px",
                                          fontWeight: 600,
                                        }}
                                      >
                                        COMPLETION
                                      </span>
                                    )}
                                  </div>
                                  <button
                                    className={isCompletionOnly ? "btn btn-secondary" : "btn btn-primary"}
                                    onClick={async (e) => {
                                      e.stopPropagation();
                                      const newData = {
                                        ...savedAssignmentData[name],
                                        completionOnly: !isCompletionOnly,
                                      };
                                      setSavedAssignmentData(prev => ({
                                        ...prev,
                                        [name]: newData,
                                      }));
                                      try {
                                        // Load the full assignment first to preserve all data (including importedDoc)
                                        const fullData = await api.loadAssignment(name);
                                        if (fullData.assignment) {
                                          await api.saveAssignmentConfig({
                                            ...fullData.assignment,
                                            completionOnly: !isCompletionOnly,
                                          });
                                        } else {
                                          // Fallback if load fails
                                          await api.saveAssignmentConfig({
                                            ...newData,
                                            title: name,
                                            completionOnly: !isCompletionOnly,
                                          });
                                        }
                                        addToast(
                                          `"${name}" set to ${!isCompletionOnly ? "Completion Only" : "AI Grading"}`,
                                          "success"
                                        );
                                      } catch (e) {
                                        addToast("Error saving: " + e.message, "error");
                                      }
                                    }}
                                    style={{ padding: "6px 12px", fontSize: "0.8rem" }}
                                  >
                                    {isCompletionOnly ? "Enable AI Grading" : "Completion Only"}
                                  </button>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}
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
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "10px",
                        }}
                      >
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
                        <span style={{ fontWeight: 600, fontSize: "0.95rem" }}>
                          Activity Monitor
                        </span>
                        {status.error && (
                          <span
                            style={{
                              fontSize: "0.75rem",
                              padding: "3px 10px",
                              borderRadius: "12px",
                              background: "rgba(248,113,113,0.2)",
                              color: "#f87171",
                              fontWeight: 500,
                            }}
                          >
                            Error
                          </span>
                        )}
                        {status.is_running && !status.error && (
                          <span
                            style={{
                              fontSize: "0.75rem",
                              padding: "3px 10px",
                              borderRadius: "12px",
                              background: "rgba(74,222,128,0.2)",
                              color: "#4ade80",
                              fontWeight: 500,
                            }}
                          >
                            Running...
                          </span>
                        )}
                        {status.log.length > 0 && (
                          <span
                            style={{
                              fontSize: "0.75rem",
                              padding: "3px 8px",
                              borderRadius: "8px",
                              background: "var(--input-bg)",
                              color: "var(--text-muted)",
                            }}
                          >
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
                          <p
                            style={{
                              color: "var(--text-muted)",
                              margin: 0,
                              textAlign: "center",
                            }}
                          >
                            Ready to grade. Activity will appear here...
                          </p>
                        ) : (
                          status.log.slice(-30).map((line, i) => (
                            <div
                              key={i}
                              style={{
                                marginBottom: "4px",
                                color: "var(--text-secondary)",
                              }}
                            >
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
                          background:
                            "linear-gradient(135deg, rgba(99, 102, 241, 0.1), rgba(168, 85, 247, 0.05))",
                          borderRadius: "12px",
                          border: "1px solid rgba(99, 102, 241, 0.2)",
                          marginBottom: "20px",
                        }}
                      >
                        <label
                          className="label"
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "8px",
                          }}
                        >
                          <Icon
                            name="Users"
                            size={16}
                            style={{ color: "var(--accent-primary)" }}
                          />
                          Filter by Class Period
                        </label>
                        <select
                          className="input"
                          value={selectedPeriod}
                          onChange={async (e) => {
                            const periodFilename = e.target.value;
                            setSelectedPeriod(periodFilename);
                            setGradeFilterStudent(""); // Clear student filter when period changes
                            await loadPeriodStudents(periodFilename);
                          }}
                          style={{ cursor: "pointer" }}
                        >
                          <option value="">All Periods (No Filter)</option>
                          {sortedPeriods.map((p) => (
                            <option key={p.filename} value={p.filename}>
                              {p.period_name} ({p.row_count} students)
                            </option>
                          ))}
                        </select>
                        {selectedPeriod && periodStudents.length > 0 && (
                          <p
                            style={{
                              fontSize: "0.75rem",
                              color: "var(--accent-primary)",
                              marginTop: "8px",
                              fontWeight: 500,
                            }}
                          >
                            ✓ Filtering to {periodStudents.length} students in{" "}
                            {
                              sortedPeriods.find(
                                (p) => p.filename === selectedPeriod,
                              )?.period_name
                            }
                          </p>
                        )}
                      </div>
                    )}

                    {/* Student Filter */}
                    <div
                      style={{
                        padding: "15px",
                        background:
                          "linear-gradient(135deg, rgba(139, 92, 246, 0.1), rgba(124, 58, 237, 0.05))",
                        borderRadius: "12px",
                        border: "1px solid rgba(139, 92, 246, 0.2)",
                        marginBottom: "20px",
                      }}
                    >
                      <label
                        className="label"
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "8px",
                        }}
                      >
                        <Icon
                          name="User"
                          size={16}
                          style={{ color: "#8b5cf6" }}
                        />
                        Filter by Student
                      </label>
                      {selectedPeriod && periodStudents.length > 0 ? (
                        <select
                          className="input"
                          value={gradeFilterStudent}
                          onChange={(e) =>
                            setGradeFilterStudent(e.target.value)
                          }
                          style={{ cursor: "pointer" }}
                        >
                          <option value="">All Students in Period</option>
                          {periodStudents.map((student, idx) => {
                            const displayName =
                              student.full ||
                              student.name ||
                              `${student.first || ""} ${student.last || ""}`.trim() ||
                              String(student);
                            return (
                              <option key={idx} value={displayName}>
                                {displayName}
                              </option>
                            );
                          })}
                        </select>
                      ) : (
                        <div style={{ position: "relative" }}>
                          <input
                            type="text"
                            className="input"
                            list="grade-student-suggestions"
                            value={gradeFilterStudent}
                            onChange={(e) =>
                              setGradeFilterStudent(e.target.value)
                            }
                            onClick={(e) => {
                              if (gradeFilterStudent) {
                                e.target.dataset.prev = gradeFilterStudent;
                                setGradeFilterStudent("");
                              }
                            }}
                            onBlur={(e) => {
                              if (
                                !gradeFilterStudent &&
                                e.target.dataset.prev
                              ) {
                                setGradeFilterStudent(e.target.dataset.prev);
                                e.target.dataset.prev = "";
                              }
                            }}
                            placeholder={
                              sortedPeriods.length > 0
                                ? "Type or select student..."
                                : "Type student name to filter..."
                            }
                            style={{
                              fontSize: "0.9rem",
                              paddingRight: gradeFilterStudent
                                ? "30px"
                                : undefined,
                            }}
                          />
                          {gradeFilterStudent && (
                            <button
                              onClick={(e) => {
                                e.preventDefault();
                                setGradeFilterStudent("");
                              }}
                              style={{
                                position: "absolute",
                                right: "8px",
                                top: "50%",
                                transform: "translateY(-50%)",
                                background: "none",
                                border: "none",
                                cursor: "pointer",
                                color: "#888",
                                padding: "4px",
                                display: "flex",
                                alignItems: "center",
                              }}
                              title="Clear"
                            >
                              <Icon name="X" size={14} />
                            </button>
                          )}
                          <datalist id="grade-student-suggestions">
                            {sortedPeriods
                              .flatMap((p) => p.students || [])
                              .map((s, i) => {
                                const name =
                                  s.full ||
                                  s.name ||
                                  (
                                    (s.first || "") +
                                    " " +
                                    (s.last || "")
                                  ).trim();
                                return <option key={i} value={name} />;
                              })}
                          </datalist>
                        </div>
                      )}
                      {gradeFilterStudent && (
                        <p
                          style={{
                            fontSize: "0.75rem",
                            color: "#8b5cf6",
                            marginTop: "8px",
                            fontWeight: 500,
                          }}
                        >
                          ✓ Will only grade files for "{gradeFilterStudent}"
                        </p>
                      )}
                    </div>

                    {/* Assignment Filter */}
                    {savedAssignments.length > 0 && (
                      <div
                        style={{
                          padding: "15px",
                          background:
                            "linear-gradient(135deg, rgba(16, 185, 129, 0.1), rgba(5, 150, 105, 0.05))",
                          borderRadius: "12px",
                          border: "1px solid rgba(16, 185, 129, 0.2)",
                          marginBottom: "20px",
                        }}
                      >
                        <label
                          className="label"
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "8px",
                          }}
                        >
                          <Icon
                            name="FileText"
                            size={16}
                            style={{ color: "#10b981" }}
                          />
                          Filter by Assignment
                        </label>
                        <select
                          className="input"
                          value={gradeFilterAssignment}
                          onChange={async (e) => {
                            const assignmentName = e.target.value;
                            setGradeFilterAssignment(assignmentName);
                            // Auto-load the assignment config when selected
                            if (assignmentName) {
                              try {
                                const data =
                                  await api.loadAssignment(assignmentName);
                                if (data.assignment) {
                                  setGradeAssignment({
                                    title: data.assignment.title || "",
                                    customMarkers:
                                      data.assignment.customMarkers || [],
                                    gradingNotes:
                                      data.assignment.gradingNotes || "",
                                    responseSections:
                                      data.assignment.responseSections || [],
                                  });
                                  if (data.assignment.importedDoc) {
                                    setGradeImportedDoc(
                                      data.assignment.importedDoc,
                                    );
                                  }
                                  addToast(
                                    `Loaded "${assignmentName}"`,
                                    "success",
                                  );
                                }
                              } catch (err) {
                                console.error("Load error:", err);
                              }
                            }
                          }}
                          style={{ cursor: "pointer" }}
                        >
                          <option value="">Select Assignment...</option>
                          {savedAssignments.map((name) => (
                            <option key={name} value={name}>
                              {name}
                              {savedAssignmentData[name]?.completionOnly
                                ? " (Completion)"
                                : ""}
                            </option>
                          ))}
                        </select>
                        {gradeFilterAssignment && (
                          <p
                            style={{
                              fontSize: "0.75rem",
                              color: "#10b981",
                              marginTop: "8px",
                              fontWeight: 500,
                            }}
                          >
                            ✓ Using "{gradeFilterAssignment}" configuration
                          </p>
                        )}
                      </div>
                    )}

                    {/* Active Filters Summary */}
                    {(gradeFilterStudent || gradeFilterAssignment) && (
                      <div
                        style={{
                          padding: "12px 15px",
                          background: "rgba(251, 191, 36, 0.1)",
                          borderRadius: "10px",
                          border: "1px solid rgba(251, 191, 36, 0.3)",
                          marginBottom: "20px",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          flexWrap: "wrap",
                          gap: "10px",
                        }}
                      >
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "8px",
                            flexWrap: "wrap",
                          }}
                        >
                          <Icon
                            name="Filter"
                            size={16}
                            style={{ color: "#f59e0b" }}
                          />
                          <span
                            style={{
                              fontSize: "0.85rem",
                              color: "#f59e0b",
                              fontWeight: 600,
                            }}
                          >
                            Active Filters:
                          </span>
                          {gradeFilterStudent && (
                            <span
                              style={{
                                padding: "4px 10px",
                                background: "rgba(99, 102, 241, 0.2)",
                                borderRadius: "6px",
                                fontSize: "0.8rem",
                                color: "var(--accent-primary)",
                              }}
                            >
                              Student: {gradeFilterStudent}
                            </span>
                          )}
                          {gradeFilterAssignment && (
                            <span
                              style={{
                                padding: "4px 10px",
                                background: "rgba(16, 185, 129, 0.2)",
                                borderRadius: "6px",
                                fontSize: "0.8rem",
                                color: "#10b981",
                              }}
                            >
                              Assignment: {gradeFilterAssignment}
                            </span>
                          )}
                        </div>
                        <button
                          onClick={() => {
                            setGradeFilterStudent("");
                            setGradeFilterAssignment("");
                          }}
                          style={{
                            padding: "4px 10px",
                            background: "rgba(239, 68, 68, 0.1)",
                            border: "1px solid rgba(239, 68, 68, 0.3)",
                            borderRadius: "6px",
                            color: "#ef4444",
                            fontSize: "0.8rem",
                            cursor: "pointer",
                          }}
                        >
                          Clear Filters
                        </button>
                      </div>
                    )}

                    {/* Matching Files Preview - Show when student filter is set */}
                    {gradeFilterStudent && availableFiles.length > 0 && (
                      <div
                        style={{
                          padding: "15px",
                          background:
                            "linear-gradient(135deg, rgba(59, 130, 246, 0.1), rgba(37, 99, 235, 0.05))",
                          borderRadius: "12px",
                          border: "1px solid rgba(59, 130, 246, 0.2)",
                          marginBottom: "20px",
                        }}
                      >
                        <label
                          className="label"
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "8px",
                            marginBottom: "10px",
                          }}
                        >
                          <Icon
                            name="FileSearch"
                            size={16}
                            style={{ color: "#3b82f6" }}
                          />
                          Matching Submissions for "{gradeFilterStudent}"
                        </label>
                        {(() => {
                          let studentName = gradeFilterStudent.toLowerCase();
                          // Handle "Last; First" or "Last, First" roster format
                          if (studentName.includes(';') || studentName.includes(',')) {
                            const parts = studentName.split(/[;,]/).map(p => p.trim());
                            if (parts.length >= 2) {
                              const lastName = parts[0];
                              const firstName = parts[1].split(' ')[0];
                              studentName = firstName + ' ' + lastName;
                            }
                          }
                          const matchingFiles = availableFiles.filter((f) => {
                            const fileName = f.name.toLowerCase();
                            return (
                              fileName.includes(
                                studentName.replace(/\s+/g, ""),
                              ) ||
                              fileName.includes(
                                studentName.replace(/\s+/g, "_"),
                              ) ||
                              fileName.includes(
                                studentName.replace(/\s+/g, "-"),
                              ) ||
                              fileName.includes(studentName)
                            );
                          });

                          if (matchingFiles.length === 0) {
                            return (
                              <p
                                style={{
                                  fontSize: "0.85rem",
                                  color: "var(--text-muted)",
                                  margin: 0,
                                }}
                              >
                                No files found matching "{gradeFilterStudent}"
                              </p>
                            );
                          }

                          return (
                            <div
                              style={{
                                display: "flex",
                                flexDirection: "column",
                                gap: "8px",
                              }}
                            >
                              <p
                                style={{
                                  fontSize: "0.75rem",
                                  color: "#3b82f6",
                                  margin: "0 0 5px 0",
                                }}
                              >
                                {matchingFiles.length} file
                                {matchingFiles.length !== 1 ? "s" : ""} found -
                                select to grade:
                              </p>
                              {matchingFiles.map((file, idx) => (
                                <label
                                  key={idx}
                                  style={{
                                    display: "flex",
                                    alignItems: "center",
                                    gap: "10px",
                                    padding: "10px 12px",
                                    background: selectedFiles.includes(
                                      file.name,
                                    )
                                      ? "rgba(59, 130, 246, 0.2)"
                                      : "var(--input-bg)",
                                    borderRadius: "8px",
                                    border: selectedFiles.includes(file.name)
                                      ? "1px solid rgba(59, 130, 246, 0.4)"
                                      : "1px solid var(--glass-border)",
                                    cursor: "pointer",
                                    transition: "all 0.2s",
                                  }}
                                >
                                  <input
                                    type="checkbox"
                                    checked={selectedFiles.includes(file.name)}
                                    onChange={(e) => {
                                      if (e.target.checked) {
                                        setSelectedFiles([
                                          ...selectedFiles,
                                          file.name,
                                        ]);
                                      } else {
                                        setSelectedFiles(
                                          selectedFiles.filter(
                                            (f) => f !== file.name,
                                          ),
                                        );
                                      }
                                    }}
                                    style={{
                                      width: "16px",
                                      height: "16px",
                                      cursor: "pointer",
                                    }}
                                  />
                                  <div style={{ flex: 1 }}>
                                    <span
                                      style={{
                                        fontSize: "0.9rem",
                                        fontWeight: 500,
                                      }}
                                    >
                                      {file.name}
                                    </span>
                                    {file.graded && (
                                      <span
                                        style={{
                                          marginLeft: "8px",
                                          padding: "2px 6px",
                                          background: "rgba(16, 185, 129, 0.2)",
                                          borderRadius: "4px",
                                          fontSize: "0.7rem",
                                          color: "#10b981",
                                        }}
                                      >
                                        Already Graded
                                      </span>
                                    )}
                                  </div>
                                </label>
                              ))}
                              {selectedFiles.length > 0 && (
                                <div
                                  style={{
                                    display: "flex",
                                    gap: "10px",
                                    marginTop: "5px",
                                  }}
                                >
                                  <button
                                    onClick={() =>
                                      setSelectedFiles(
                                        matchingFiles.map((f) => f.name),
                                      )
                                    }
                                    style={{
                                      padding: "6px 12px",
                                      background: "rgba(59, 130, 246, 0.1)",
                                      border:
                                        "1px solid rgba(59, 130, 246, 0.3)",
                                      borderRadius: "6px",
                                      color: "#3b82f6",
                                      fontSize: "0.8rem",
                                      cursor: "pointer",
                                    }}
                                  >
                                    Select All
                                  </button>
                                  <button
                                    onClick={() => setSelectedFiles([])}
                                    style={{
                                      padding: "6px 12px",
                                      background: "rgba(239, 68, 68, 0.1)",
                                      border:
                                        "1px solid rgba(239, 68, 68, 0.3)",
                                      borderRadius: "6px",
                                      color: "#ef4444",
                                      fontSize: "0.8rem",
                                      cursor: "pointer",
                                    }}
                                  >
                                    Clear Selection
                                  </button>
                                </div>
                              )}
                            </div>
                          );
                        })()}
                      </div>
                    )}

                    {/* Skip Verified Toggle - Show when there are unverified results */}
                    {status.results &&
                      status.results.some(
                        (r) => r.marker_status === "unverified",
                      ) && (
                        <div
                          style={{
                            padding: "15px",
                            background:
                              "linear-gradient(135deg, rgba(251, 191, 36, 0.1), rgba(245, 158, 11, 0.05))",
                            borderRadius: "12px",
                            border: "1px solid rgba(251, 191, 36, 0.3)",
                            marginBottom: "20px",
                          }}
                        >
                          <label
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "10px",
                              cursor: "pointer",
                            }}
                          >
                            <input
                              type="checkbox"
                              checked={skipVerified}
                              onChange={(e) =>
                                setSkipVerified(e.target.checked)
                              }
                              style={{
                                width: "18px",
                                height: "18px",
                                cursor: "pointer",
                              }}
                            />
                            <div>
                              <span
                                style={{ fontWeight: 600, color: "#fbbf24" }}
                              >
                                Skip Verified Grades (Regrade Only Unverified)
                              </span>
                              <p
                                style={{
                                  fontSize: "0.75rem",
                                  color: "var(--text-secondary)",
                                  margin: "4px 0 0 0",
                                }}
                              >
                                {
                                  status.results.filter(
                                    (r) => r.marker_status === "unverified",
                                  ).length
                                }{" "}
                                unverified assignments will be regraded.{" "}
                                {
                                  status.results.filter(
                                    (r) => r.marker_status === "verified",
                                  ).length
                                }{" "}
                                verified grades will be kept.
                              </p>
                            </div>
                          </label>
                        </div>
                      )}

                    {/* Exclude students already graded in this session */}
                    {status.results.length > 0 && (
                      <div
                        className="glass-card"
                        style={{
                          padding: "15px 20px",
                          marginBottom: "20px",
                          background: "rgba(34, 197, 94, 0.05)",
                          border: "1px solid rgba(34, 197, 94, 0.2)",
                        }}
                      >
                        <label
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "10px",
                            cursor: "pointer",
                          }}
                        >
                          <input
                            type="checkbox"
                            checked={excludeGradedStudents}
                            onChange={(e) =>
                              setExcludeGradedStudents(e.target.checked)
                            }
                            style={{
                              width: "18px",
                              height: "18px",
                              cursor: "pointer",
                            }}
                          />
                          <div>
                            <span
                              style={{ fontWeight: 600, color: "#22c55e" }}
                            >
                              Exclude Already Graded Students
                            </span>
                            <p
                              style={{
                                fontSize: "0.75rem",
                                color: "var(--text-secondary)",
                                margin: "4px 0 0 0",
                              }}
                            >
                              Skip files for {(() => {
                                // Filter results by current assignment filter
                                let relevantResults = status.results;
                                if (gradeFilterAssignment) {
                                  const cfg = savedAssignmentData[gradeFilterAssignment] || {};
                                  const importedFn = (cfg.importedFilename || "").toLowerCase().replace(/\.[^/.]+$/, "");
                                  const names = [gradeFilterAssignment, cfg.title || "", ...(cfg.aliases || []), importedFn].filter(Boolean).map(n => n.toLowerCase());
                                  relevantResults = status.results.filter((r) => {
                                    const rAssign = (r.assignment || "").toLowerCase();
                                    const rFile = (r.filename || "").toLowerCase();
                                    return names.some(n => rAssign.includes(n) || rFile.includes(n) || n.includes(rAssign));
                                  });
                                }
                                return [...new Set(relevantResults.map((r) => r.student_name))].length;
                              })()} student(s) who already have results{gradeFilterAssignment ? ` for "${gradeFilterAssignment}"` : ""}.
                              Only grade new students.
                            </p>
                          </div>
                        </label>
                      </div>
                    )}

                    {/* Grading Notes - Quick notes for this grading session */}
                    <div
                      className="glass-card"
                      style={{
                        padding: "20px",
                        marginBottom: "20px",
                        background: "rgba(251,191,36,0.05)",
                        border: "1px solid rgba(251,191,36,0.2)",
                      }}
                    >
                      <label
                        className="label"
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "8px",
                        }}
                      >
                        <Icon
                          name="FileEdit"
                          size={16}
                          style={{ color: "#fbbf24" }}
                        />
                        Grading Notes (Optional)
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
                        placeholder="Special instructions for this grading session..."
                        style={{ minHeight: "80px" }}
                      />
                      <p
                        style={{
                          fontSize: "0.75rem",
                          color: "var(--text-muted)",
                          marginTop: "8px",
                        }}
                      >
                        For full assignment setup (markers, imported docs), use
                        the Builder tab and select via "Filter by Assignment"
                        above.
                      </p>
                    </div>

                    {/* Individual Upload - For Paper/Handwritten Assignments */}
                    <div
                      style={{
                        marginTop: "20px",
                        padding: "20px",
                        borderRadius: "16px",
                        background:
                          "linear-gradient(135deg, rgba(16, 185, 129, 0.1), rgba(5, 150, 105, 0.05))",
                        border: "1px solid rgba(16, 185, 129, 0.2)",
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "10px",
                          marginBottom: "15px",
                        }}
                      >
                        <div
                          style={{
                            width: "36px",
                            height: "36px",
                            borderRadius: "10px",
                            background: "rgba(16, 185, 129, 0.15)",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                          }}
                        >
                          <Icon
                            name="Camera"
                            size={20}
                            style={{ color: "#10b981" }}
                          />
                        </div>
                        <div>
                          <h4 style={{ margin: 0, fontWeight: 600 }}>
                            Individual Upload
                          </h4>
                          <p
                            style={{
                              margin: 0,
                              fontSize: "0.75rem",
                              color: "var(--text-muted)",
                            }}
                          >
                            For paper/handwritten assignments (uses GPT-4o
                            vision)
                          </p>
                        </div>
                      </div>

                      <div
                        style={{
                          display: "grid",
                          gridTemplateColumns: individualUpload.preview
                            ? "1fr 1fr"
                            : "1fr",
                          gap: "15px",
                        }}
                      >
                        <div
                          style={{
                            display: "flex",
                            flexDirection: "column",
                            gap: "12px",
                          }}
                        >
                          {/* Student Name with Autocomplete */}
                          <div style={{ position: "relative" }}>
                            <input
                              type="text"
                              className="input"
                              placeholder={
                                periodStudents.length > 0
                                  ? "Start typing student name..."
                                  : "Student name..."
                              }
                              value={individualUpload.studentName}
                              onChange={(e) =>
                                setIndividualUpload((prev) => ({
                                  ...prev,
                                  studentName: e.target.value,
                                  studentInfo: null, // Clear selected student when typing
                                  showSuggestions: e.target.value.length >= 2,
                                }))
                              }
                              onFocus={() =>
                                setIndividualUpload((prev) => ({
                                  ...prev,
                                  showSuggestions: prev.studentName.length >= 2,
                                }))
                              }
                              onBlur={() =>
                                setTimeout(
                                  () =>
                                    setIndividualUpload((prev) => ({
                                      ...prev,
                                      showSuggestions: false,
                                    })),
                                  200,
                                )
                              }
                            />
                            {/* Autocomplete Dropdown */}
                            {individualUpload.showSuggestions &&
                              getStudentSuggestions(
                                individualUpload.studentName,
                              ).length > 0 && (
                                <div
                                  style={{
                                    position: "absolute",
                                    top: "100%",
                                    left: 0,
                                    right: 0,
                                    background: "var(--card-bg)",
                                    border: "1px solid var(--glass-border)",
                                    borderRadius: "8px",
                                    marginTop: "4px",
                                    zIndex: 100,
                                    boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
                                    maxHeight: "200px",
                                    overflowY: "auto",
                                  }}
                                >
                                  {getStudentSuggestions(
                                    individualUpload.studentName,
                                  ).map((student, idx) => (
                                    <div
                                      key={idx}
                                      onClick={() =>
                                        setIndividualUpload((prev) => ({
                                          ...prev,
                                          studentName:
                                            student.full ||
                                            `${student.first} ${student.last}`,
                                          studentInfo: student,
                                          showSuggestions: false,
                                        }))
                                      }
                                      style={{
                                        padding: "10px 12px",
                                        cursor: "pointer",
                                        borderBottom:
                                          idx <
                                          getStudentSuggestions(
                                            individualUpload.studentName,
                                          ).length -
                                            1
                                            ? "1px solid var(--glass-border)"
                                            : "none",
                                        display: "flex",
                                        alignItems: "center",
                                        gap: "10px",
                                      }}
                                      onMouseEnter={(e) =>
                                        (e.target.style.background =
                                          "var(--glass-bg)")
                                      }
                                      onMouseLeave={(e) =>
                                        (e.target.style.background =
                                          "transparent")
                                      }
                                    >
                                      <Icon
                                        name="User"
                                        size={16}
                                        style={{ color: "var(--text-muted)" }}
                                      />
                                      <div>
                                        <div style={{ fontWeight: 500 }}>
                                          {student.full ||
                                            `${student.first} ${student.last}`}
                                        </div>
                                        {student.email && (
                                          <div
                                            style={{
                                              fontSize: "0.75rem",
                                              color: "var(--text-muted)",
                                            }}
                                          >
                                            {student.email}
                                          </div>
                                        )}
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              )}
                            {/* Selected Student Indicator */}
                            {individualUpload.studentInfo && (
                              <div
                                style={{
                                  marginTop: "6px",
                                  fontSize: "0.75rem",
                                  color: "#10b981",
                                  display: "flex",
                                  alignItems: "center",
                                  gap: "4px",
                                }}
                              >
                                <Icon name="CheckCircle" size={12} />
                                Student matched from roster
                              </div>
                            )}
                          </div>

                          <div
                            onClick={() =>
                              document
                                .getElementById("individualFileInput")
                                ?.click()
                            }
                            style={{
                              padding: "20px",
                              border: "2px dashed var(--glass-border)",
                              borderRadius: "10px",
                              textAlign: "center",
                              cursor: "pointer",
                              background: individualUpload.file
                                ? "rgba(16, 185, 129, 0.1)"
                                : "var(--glass-bg)",
                            }}
                          >
                            <input
                              id="individualFileInput"
                              type="file"
                              accept="image/*,.pdf,.heic,.heif"
                              onChange={handleIndividualFileSelect}
                              style={{ display: "none" }}
                            />
                            {individualUpload.file ? (
                              <div
                                style={{
                                  display: "flex",
                                  alignItems: "center",
                                  justifyContent: "center",
                                  gap: "8px",
                                }}
                              >
                                <Icon
                                  name="CheckCircle"
                                  size={20}
                                  style={{ color: "#10b981" }}
                                />
                                <span
                                  style={{
                                    fontWeight: 500,
                                    fontSize: "0.9rem",
                                  }}
                                >
                                  {individualUpload.file.name}
                                </span>
                              </div>
                            ) : (
                              <>
                                <Icon
                                  name="Upload"
                                  size={24}
                                  style={{ color: "var(--text-muted)" }}
                                />
                                <p
                                  style={{
                                    margin: "8px 0 0",
                                    fontSize: "0.85rem",
                                    color: "var(--text-secondary)",
                                  }}
                                >
                                  Click to upload image
                                </p>
                              </>
                            )}
                          </div>

                          <div style={{ display: "flex", gap: "8px" }}>
                            <button
                              onClick={handleIndividualGrade}
                              disabled={
                                !individualUpload.file ||
                                !individualUpload.studentName.trim() ||
                                individualUpload.isGrading
                              }
                              className="btn btn-primary"
                              style={{
                                flex: 1,
                                opacity:
                                  !individualUpload.file ||
                                  !individualUpload.studentName.trim() ||
                                  individualUpload.isGrading
                                    ? 0.5
                                    : 1,
                              }}
                            >
                              {individualUpload.isGrading ? (
                                <>Grading...</>
                              ) : (
                                <>
                                  <Icon name="Sparkles" size={16} />
                                  Grade
                                </>
                              )}
                            </button>
                            {individualUpload.file && (
                              <button
                                onClick={clearIndividualUpload}
                                className="btn btn-secondary"
                                style={{ padding: "8px 12px" }}
                              >
                                <Icon name="X" size={16} />
                              </button>
                            )}
                          </div>

                          {individualUpload.result && (
                            <div
                              style={{
                                padding: "12px",
                                borderRadius: "10px",
                                background: "rgba(16, 185, 129, 0.15)",
                                border: "1px solid rgba(16, 185, 129, 0.3)",
                              }}
                            >
                              <div
                                style={{
                                  display: "flex",
                                  alignItems: "center",
                                  gap: "12px",
                                }}
                              >
                                <span
                                  style={{
                                    fontSize: "1.5rem",
                                    fontWeight: 800,
                                    color: "#10b981",
                                  }}
                                >
                                  {individualUpload.result.letter_grade}
                                </span>
                                <div>
                                  <div style={{ fontWeight: 600 }}>
                                    {individualUpload.result.score}%
                                  </div>
                                  <div
                                    style={{
                                      fontSize: "0.75rem",
                                      color: "var(--text-muted)",
                                    }}
                                  >
                                    {individualUpload.studentName}
                                  </div>
                                </div>
                              </div>
                            </div>
                          )}
                        </div>

                        {individualUpload.preview && (
                          <div
                            style={{
                              borderRadius: "10px",
                              overflow: "hidden",
                              border: "1px solid var(--glass-border)",
                            }}
                          >
                            <img
                              src={individualUpload.preview}
                              alt="Preview"
                              style={{
                                width: "100%",
                                height: "auto",
                                maxHeight: "250px",
                                objectFit: "contain",
                                background: "#fff",
                              }}
                            />
                          </div>
                        )}
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
                    gridTemplateColumns: "1fr",
                    gap: "20px",
                  }}
                >
                  {/* Results Table */}
                  <div className="glass-card" style={{ padding: "25px" }}>
                    <div style={{ marginBottom: "20px" }}>
                      <h2
                        style={{
                          fontSize: "1.3rem",
                          fontWeight: 700,
                          display: "flex",
                          alignItems: "center",
                          gap: "10px",
                          marginBottom: "15px",
                        }}
                      >
                        <Icon name="FileText" size={24} />
                        Grading Results (
                        {resultsFilter === "all" && !resultsPeriodFilter
                          ? status.results.length
                          : status.results.filter((r) => {
                              if (resultsFilter === "handwritten" && !r.is_handwritten)
                                return false;
                              if (resultsFilter === "typed" && r.is_handwritten)
                                return false;
                              if (resultsFilter === "verified" && r.marker_status !== "verified")
                                return false;
                              if (resultsFilter === "unverified" && r.marker_status !== "verified")
                                return false;
                              if (resultsPeriodFilter && r.period !== resultsPeriodFilter)
                                return false;
                              return true;
                            }).length}
                        {(resultsFilter !== "all" || resultsPeriodFilter) &&
                          ` of ${status.results.length}`}
                        )
                      </h2>
                      {status.results.length > 0 && (
                        <div
                          style={{
                            display: "flex",
                            gap: "10px",
                            alignItems: "center",
                            flexWrap: "wrap",
                          }}
                        >
                          {/* Sort Dropdown */}
                          <select
                            className="input"
                            value={
                              resultsSort.field + "_" + resultsSort.direction
                            }
                            onChange={(e) => {
                              const [field, direction] =
                                e.target.value.split("_");
                              setResultsSort({ field, direction });
                            }}
                            style={{
                              width: "auto",
                              padding: "8px 12px",
                              fontSize: "0.85rem",
                            }}
                          >
                            <option value="time_desc">Newest First</option>
                            <option value="time_asc">Oldest First</option>
                            <option value="name_asc">Name (A-Z)</option>
                            <option value="name_desc">Name (Z-A)</option>
                            <option value="score_desc">Score (High-Low)</option>
                            <option value="score_asc">Score (Low-High)</option>
                            <option value="assignment_asc">
                              Assignment (A-Z)
                            </option>
                            <option value="assignment_desc">
                              Assignment (Z-A)
                            </option>
                            <option value="grade_asc">Grade (A-F)</option>
                            <option value="grade_desc">Grade (F-A)</option>
                          </select>
                          {/* Filter Dropdown */}
                          <select
                            className="input"
                            value={resultsFilter}
                            onChange={(e) => setResultsFilter(e.target.value)}
                            style={{
                              width: "auto",
                              padding: "8px 12px",
                              fontSize: "0.85rem",
                            }}
                          >
                            <option value="all">All Results</option>
                            <option value="handwritten">
                              Handwritten Only
                            </option>
                            <option value="typed">Typed Only</option>
                            <option value="verified">Verified Only</option>
                            <option value="unverified">Unverified Only</option>
                          </select>
                          {/* Period Filter Dropdown */}
                          {sortedPeriods.length > 0 && (
                            <select
                              className="input"
                              value={resultsPeriodFilter}
                              onChange={(e) => setResultsPeriodFilter(e.target.value)}
                              style={{
                                width: "auto",
                                padding: "8px 12px",
                                fontSize: "0.85rem",
                              }}
                            >
                              <option value="">All Periods</option>
                              {sortedPeriods.map((p) => (
                                <option key={p.filename} value={p.period_name}>
                                  {p.period_name}
                                </option>
                              ))}
                            </select>
                          )}
                          {/* Apply Curve Button - shows when period is filtered */}
                          {resultsPeriodFilter && (
                            <button
                              onClick={() => setCurveModal({ ...curveModal, show: true })}
                              className="btn btn-secondary"
                              style={{
                                background: "linear-gradient(135deg, rgba(168, 85, 247, 0.2), rgba(139, 92, 246, 0.2))",
                                borderColor: "#a855f7",
                              }}
                              title="Apply a grade curve to all filtered results"
                            >
                              <Icon name="TrendingUp" size={18} />
                              Apply Curve
                            </button>
                          )}
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
                                  addToast(
                                    "Error clearing results: " + e.message,
                                    "error",
                                  );
                                }
                              }
                            }}
                            className="btn btn-secondary"
                            style={{ background: "rgba(239,68,68,0.2)" }}
                          >
                            <Icon name="Trash2" size={18} />
                            Clear
                          </button>
                          <button
                            onClick={() => setFocusExportModal(true)}
                            className="btn btn-primary"
                            style={{
                              background:
                                "linear-gradient(135deg, #8b5cf6, #6366f1)",
                            }}
                            title="Export grades for Focus SIS import"
                          >
                            <Icon name="Download" size={18} />
                            Focus Export
                          </button>
                          {/* Email Actions */}
                          <div style={{ borderLeft: "1px solid var(--glass-border)", height: "24px", margin: "0 5px" }} />
                          {/* Send by Period Dropdown */}
                          {sortedPeriods.length > 0 && (
                            <div style={{ display: "flex", alignItems: "center", gap: "5px" }}>
                              <select
                                className="input"
                                style={{ width: "auto", padding: "8px 12px", fontSize: "0.85rem" }}
                                defaultValue=""
                                onChange={async (e) => {
                                  const period = e.target.value;
                                  if (!period) return;
                                  const periodResults = status.results.filter((r) => r.period === period && r.student_email);
                                  if (periodResults.length === 0) {
                                    addToast(`No students with emails in ${period}`, "warning");
                                    e.target.value = "";
                                    return;
                                  }
                                  if (!confirm(`Send emails to ${periodResults.length} students in ${period}?`)) {
                                    e.target.value = "";
                                    return;
                                  }
                                  setEmailStatus({ sending: true, sent: 0, failed: 0, message: `Sending to ${period}...` });
                                  try {
                                    const resultsWithEmail = periodResults.map((r) => {
                                      const idx = status.results.findIndex((sr) => sr.filename === r.filename);
                                      const edited = editedEmails[idx];
                                      return {
                                        ...r,
                                        student_email: edited?.email || r.student_email,
                                        custom_email_subject: edited?.subject || `Grade Report: ${r.assignment}`,
                                        custom_email_body: edited?.body || getDefaultEmailBody(idx),
                                      };
                                    });
                                    const response = await api.sendEmails(resultsWithEmail, config.teacher_email, config.teacher_name, config.email_signature);
                                    setEmailStatus({
                                      sending: false,
                                      sent: response.sent || 0,
                                      failed: response.failed || 0,
                                      message: `${period}: Sent ${response.sent}${response.failed > 0 ? `, ${response.failed} failed` : ""}`,
                                    });
                                  } catch (err) {
                                    setEmailStatus({ sending: false, sent: 0, failed: 0, message: `Error: ${err.message}` });
                                  }
                                  e.target.value = "";
                                }}
                                disabled={emailStatus.sending}
                              >
                                <option value="">Send by Period...</option>
                                {sortedPeriods.map((p) => {
                                  const count = status.results.filter((r) => r.period === p.period_name && r.student_email).length;
                                  return (
                                    <option key={p.filename} value={p.period_name}>
                                      {p.period_name} ({count} emails)
                                    </option>
                                  );
                                })}
                              </select>
                            </div>
                          )}
                          <button
                            onClick={async () => {
                              // Include results with original email OR manually entered email
                              const withEmail = status.results.filter((r, idx) => r.student_email || editedEmails[idx]?.email);
                              if (withEmail.length === 0) {
                                addToast("No students have email addresses", "warning");
                                return;
                              }
                              // Count unique students (by email), not total results
                              const uniqueEmails = [...new Set(withEmail.map((r, idx) => {
                                const globalIdx = status.results.findIndex((sr) => sr.filename === r.filename);
                                return editedEmails[globalIdx]?.email || r.student_email;
                              }))];
                              const msg = uniqueEmails.length === 1
                                ? `Send 1 email to ${withEmail[0].student_name?.split(' ')[0] || 'student'} with ${withEmail.length} assignment${withEmail.length > 1 ? 's' : ''}?`
                                : `Send emails to ${uniqueEmails.length} students (${withEmail.length} total assignments)?`;
                              if (!confirm(msg)) return;
                              setEmailStatus({ sending: true, sent: 0, failed: 0, message: `Sending to ${uniqueEmails.length} student${uniqueEmails.length > 1 ? 's' : ''}...` });
                              try {
                                const resultsWithEmail = withEmail.map((r) => {
                                  const idx = status.results.findIndex((sr) => sr.filename === r.filename);
                                  const edited = editedEmails[idx];
                                  return {
                                    ...r,
                                    student_email: edited?.email || r.student_email,
                                    custom_email_subject: edited?.subject || `Grade Report: ${r.assignment}`,
                                    custom_email_body: edited?.body || getDefaultEmailBody(idx),
                                  };
                                });
                                const response = await api.sendEmails(resultsWithEmail, config.teacher_email, config.teacher_name, config.email_signature);
                                setEmailStatus({
                                  sending: false,
                                  sent: response.sent || 0,
                                  failed: response.failed || 0,
                                  message: `Sent ${response.sent} emails${response.failed > 0 ? `, ${response.failed} failed` : ""}`,
                                });
                              } catch (e) {
                                setEmailStatus({ sending: false, sent: 0, failed: 0, message: `Error: ${e.message}` });
                              }
                            }}
                            className="btn btn-primary"
                            disabled={emailStatus.sending}
                            style={{
                              background: "linear-gradient(135deg, #22c55e, #16a34a)",
                            }}
                            title="Send emails to all students"
                          >
                            <Icon name="Send" size={18} />
                            {emailStatus.sending ? "Sending..." : "Send All Emails"}
                          </button>
                        </div>
                      )}
                    </div>

                    {/* Authenticity Summary Alert */}
                    {status.results.length > 0 &&
                      (() => {
                        const authStats = status.results.reduce(
                          (acc, r) => {
                            const auth = getAuthenticityStatus(r);
                            if (auth.ai.flag === "likely") acc.aiLikely++;
                            else if (auth.ai.flag === "possible")
                              acc.aiPossible++;
                            if (auth.plag.flag === "likely") acc.plagLikely++;
                            else if (auth.plag.flag === "possible")
                              acc.plagPossible++;
                            return acc;
                          },
                          {
                            aiLikely: 0,
                            aiPossible: 0,
                            plagLikely: 0,
                            plagPossible: 0,
                          },
                        );

                        const hasConcerns =
                          authStats.aiLikely +
                            authStats.aiPossible +
                            authStats.plagLikely +
                            authStats.plagPossible >
                          0;

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
                              <div
                                style={{ fontWeight: 700, marginBottom: "8px" }}
                              >
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
                                  <div
                                    style={{
                                      color: "var(--text-muted)",
                                      fontSize: "0.8rem",
                                      marginBottom: "4px",
                                    }}
                                  >
                                    <Icon
                                      name="Bot"
                                      size={12}
                                      style={{
                                        marginRight: "4px",
                                        verticalAlign: "middle",
                                      }}
                                    />
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
                                    {authStats.aiLikely === 0 &&
                                      authStats.aiPossible === 0 && (
                                        <span style={{ color: "#4ade80" }}>
                                          All clear
                                        </span>
                                      )}
                                  </div>
                                </div>
                                {/* Plagiarism Stats */}
                                <div>
                                  <div
                                    style={{
                                      color: "var(--text-muted)",
                                      fontSize: "0.8rem",
                                      marginBottom: "4px",
                                    }}
                                  >
                                    <Icon
                                      name="Copy"
                                      size={12}
                                      style={{
                                        marginRight: "4px",
                                        verticalAlign: "middle",
                                      }}
                                    />
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
                                    {authStats.plagLikely === 0 &&
                                      authStats.plagPossible === 0 && (
                                        <span style={{ color: "#4ade80" }}>
                                          All clear
                                        </span>
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
                            {(resultsFilter !== "all" || resultsPeriodFilter) && (
                              <button
                                onClick={() => {
                                  const approvals = { ...emailApprovals };
                                  status.results.forEach((r, i) => {
                                    // Apply same filters as the display
                                    if (resultsFilter === "handwritten" && !r.is_handwritten) return;
                                    if (resultsFilter === "typed" && r.is_handwritten) return;
                                    if (resultsFilter === "verified" && r.marker_status !== "verified") return;
                                    if (resultsFilter === "unverified" && r.marker_status !== "verified") return;
                                    if (resultsPeriodFilter && r.period !== resultsPeriodFilter) return;
                                    approvals[i] = "approved";
                                  });
                                  updateApprovalsBulk(approvals);
                                }}
                                className="btn btn-secondary"
                                style={{
                                  fontSize: "0.85rem",
                                  padding: "6px 12px",
                                  background: "rgba(99,102,241,0.15)",
                                  border: "1px solid rgba(99,102,241,0.3)",
                                }}
                              >
                                <Icon name="Filter" size={14} />
                                Approve Filtered
                              </button>
                            )}
                            <button
                              onClick={() => {
                                const approvals = {};
                                status.results.forEach((_, i) => {
                                  approvals[i] = "approved";
                                });
                                updateApprovalsBulk(approvals);
                              }}
                              className="btn btn-secondary"
                              style={{
                                fontSize: "0.85rem",
                                padding: "6px 12px",
                              }}
                            >
                              <Icon name="CheckCircle" size={14} />
                              Approve All
                            </button>
                            {Object.keys(emailApprovals).length > 0 && (
                              <button
                                onClick={() => {
                                  updateApprovalsBulk({});
                                  addToast("All approvals cleared", "info");
                                }}
                                className="btn btn-secondary"
                                style={{
                                  fontSize: "0.85rem",
                                  padding: "6px 12px",
                                  background: "rgba(239, 68, 68, 0.15)",
                                  border: "1px solid rgba(239, 68, 68, 0.3)",
                                  color: "#f87171",
                                }}
                              >
                                <Icon name="X" size={14} />
                                Clear Approvals
                              </button>
                            )}
                            {Object.values(emailApprovals).some((v) => v === "approved") && (
                              <button
                                onClick={() => {
                                  const newSentEmails = { ...sentEmails };
                                  Object.keys(emailApprovals).forEach((idx) => {
                                    if (emailApprovals[idx] === "approved") {
                                      newSentEmails[idx] = true;
                                    }
                                  });
                                  setSentEmails(newSentEmails);
                                  addToast("All approved emails marked as sent (no emails sent)", "info");
                                }}
                                className="btn btn-secondary"
                                style={{
                                  fontSize: "0.85rem",
                                  padding: "6px 12px",
                                  background: "rgba(59, 130, 246, 0.15)",
                                  border: "1px solid rgba(59, 130, 246, 0.3)",
                                  color: "#3b82f6",
                                }}
                              >
                                <Icon name="Send" size={14} />
                                Mark All as Sent
                              </button>
                            )}
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
                                // Apply handwritten/typed filter
                                if (
                                  resultsFilter === "handwritten" &&
                                  !r.is_handwritten
                                )
                                  return false;
                                if (
                                  resultsFilter === "typed" &&
                                  r.is_handwritten
                                )
                                  return false;
                                // Apply verified/unverified filter
                                if (
                                  resultsFilter === "verified" &&
                                  r.marker_status !== "verified"
                                )
                                  return false;
                                if (
                                  resultsFilter === "unverified" &&
                                  r.marker_status !== "unverified"
                                )
                                  return false;
                                // Apply period filter
                                if (resultsPeriodFilter && r.period !== resultsPeriodFilter)
                                  return false;
                                // Apply search filter
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
                              .sort((a, b) => {
                                const { field, direction } = resultsSort;
                                let cmp = 0;
                                switch (field) {
                                  case "time":
                                    const timeA = a.graded_at || "";
                                    const timeB = b.graded_at || "";
                                    cmp = timeA.localeCompare(timeB);
                                    break;
                                  case "name":
                                    cmp = (a.student_name || "").localeCompare(
                                      b.student_name || "",
                                    );
                                    break;
                                  case "assignment":
                                    cmp = (a.assignment || "").localeCompare(
                                      b.assignment || "",
                                    );
                                    break;
                                  case "score":
                                    cmp = (a.score || 0) - (b.score || 0);
                                    break;
                                  case "grade":
                                    const gradeOrder = {
                                      A: 1,
                                      B: 2,
                                      C: 3,
                                      D: 4,
                                      F: 5,
                                      ERROR: 6,
                                    };
                                    cmp =
                                      (gradeOrder[a.letter_grade] || 99) -
                                      (gradeOrder[b.letter_grade] || 99);
                                    break;
                                  default:
                                    cmp = 0;
                                }
                                return direction === "desc" ? -cmp : cmp;
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
                                      background: r.edited
                                        ? "rgba(251,191,36,0.1)"
                                        : "transparent",
                                    }}
                                  >
                                    <td>
                                      <div
                                        style={{
                                          display: "flex",
                                          alignItems: "center",
                                          gap: "6px",
                                        }}
                                      >
                                        {r.student_name}
                                        {r.is_handwritten && (
                                          <span
                                            title="Handwritten/Scanned Assignment"
                                            style={{
                                              display: "inline-flex",
                                              alignItems: "center",
                                              justifyContent: "center",
                                              width: "20px",
                                              height: "20px",
                                              borderRadius: "4px",
                                              background:
                                                "rgba(16, 185, 129, 0.15)",
                                              color: "#10b981",
                                            }}
                                          >
                                            <Icon name="PenTool" size={12} />
                                          </span>
                                        )}
                                        {r.marker_status === "unverified" && (
                                          <span
                                            title="UNVERIFIED: No markers or config found. Grade may be inaccurate. Set up assignment config and regrade."
                                            style={{
                                              display: "inline-flex",
                                              alignItems: "center",
                                              justifyContent: "center",
                                              width: "20px",
                                              height: "20px",
                                              borderRadius: "4px",
                                              background:
                                                "rgba(251, 191, 36, 0.2)",
                                              color: "#fbbf24",
                                              cursor: "help",
                                            }}
                                          >
                                            <Icon
                                              name="AlertTriangle"
                                              size={12}
                                            />
                                          </span>
                                        )}
                                        {r.student_id &&
                                          studentAccommodations[
                                            r.student_id
                                          ] && (
                                            <span
                                              title={
                                                "Accommodations: " +
                                                (studentAccommodations[
                                                  r.student_id
                                                ]?.presets
                                                  ?.map((p) => p.name)
                                                  .join(", ") || "Custom")
                                              }
                                              style={{
                                                display: "inline-flex",
                                                alignItems: "center",
                                                justifyContent: "center",
                                                width: "20px",
                                                height: "20px",
                                                borderRadius: "4px",
                                                background:
                                                  "rgba(244, 114, 182, 0.15)",
                                                color: "#f472b6",
                                                cursor: "help",
                                              }}
                                            >
                                              <Icon name="Heart" size={12} />
                                            </span>
                                          )}
                                      </div>
                                    </td>
                                    <td
                                      style={{
                                        maxWidth: "300px",
                                        overflow: "hidden",
                                        textOverflow: "ellipsis",
                                        whiteSpace: "nowrap",
                                        cursor: "help",
                                      }}
                                      title={r.filename || r.assignment}
                                    >
                                      {r.filename || r.assignment}
                                    </td>
                                    <td
                                      style={{
                                        fontSize: "0.8rem",
                                        color: "var(--text-secondary)",
                                        whiteSpace: "nowrap",
                                      }}
                                    >
                                      {r.graded_at || "-"}
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
                                        const aiColor = getAIFlagColor(
                                          auth.ai.flag,
                                        );
                                        const plagColor = getPlagFlagColor(
                                          auth.plag.flag,
                                        );
                                        return (
                                          <div
                                            style={{
                                              display: "flex",
                                              flexDirection: "column",
                                              gap: "4px",
                                            }}
                                          >
                                            {/* AI Detection */}
                                            <span
                                              title={
                                                auth.ai.reason ||
                                                `AI: ${auth.ai.flag}${auth.ai.confidence ? ` (${auth.ai.confidence}%)` : ""}`
                                              }
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
                                                cursor: auth.ai.reason
                                                  ? "help"
                                                  : "default",
                                              }}
                                            >
                                              <Icon
                                                name={
                                                  auth.ai.flag === "likely"
                                                    ? "Bot"
                                                    : auth.ai.flag ===
                                                        "possible"
                                                      ? "Bot"
                                                      : "CheckCircle"
                                                }
                                                size={12}
                                              />
                                              AI:{" "}
                                              {auth.ai.flag === "none"
                                                ? "Clear"
                                                : auth.ai.flag}
                                              {auth.ai.confidence > 0 &&
                                                ` ${auth.ai.confidence}%`}
                                            </span>
                                            {/* Plagiarism Detection */}
                                            <span
                                              title={
                                                auth.plag.reason ||
                                                `Plagiarism: ${auth.plag.flag}`
                                              }
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
                                                cursor: auth.plag.reason
                                                  ? "help"
                                                  : "default",
                                              }}
                                            >
                                              <Icon
                                                name={
                                                  auth.plag.flag === "likely"
                                                    ? "Copy"
                                                    : auth.plag.flag ===
                                                        "possible"
                                                      ? "Copy"
                                                      : "CheckCircle"
                                                }
                                                size={12}
                                              />
                                              Copy:{" "}
                                              {auth.plag.flag === "none"
                                                ? "Clear"
                                                : auth.plag.flag}
                                            </span>
                                          </div>
                                        );
                                      })()}
                                    </td>
                                    <td>
                                      <div
                                        style={{
                                          display: "flex",
                                          flexDirection: "column",
                                          gap: "4px",
                                          alignItems: "flex-start",
                                        }}
                                      >
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
                                                sentEmails[originalIndex]
                                                  ? "rgba(59,130,246,0.25)"
                                                  : emailApprovals[
                                                      originalIndex
                                                    ] === "approved"
                                                    ? "rgba(74,222,128,0.2)"
                                                    : emailApprovals[
                                                          originalIndex
                                                        ] === "rejected"
                                                      ? "rgba(248,113,113,0.2)"
                                                      : "var(--glass-border)",
                                              color:
                                                sentEmails[originalIndex]
                                                  ? "#3b82f6"
                                                  : emailApprovals[
                                                      originalIndex
                                                    ] === "approved"
                                                    ? "#4ade80"
                                                    : emailApprovals[
                                                          originalIndex
                                                        ] === "rejected"
                                                      ? "#f87171"
                                                      : "var(--text-secondary)",
                                            }}
                                          >
                                            {sentEmails[originalIndex]
                                              ? "Sent"
                                              : emailApprovals[originalIndex] ===
                                                "approved"
                                                ? "Approved"
                                                : emailApprovals[
                                                      originalIndex
                                                    ] === "rejected"
                                                  ? "Rejected"
                                                  : "Pending"}
                                          </span>
                                        )}
                                        {r.edited && (
                                          <span
                                            style={{
                                              padding: "2px 6px",
                                              borderRadius: "4px",
                                              fontSize: "0.7rem",
                                              fontWeight: 500,
                                              background:
                                                "rgba(251,191,36,0.15)",
                                              color: "#fbbf24",
                                            }}
                                          >
                                            Edited
                                          </span>
                                        )}
                                      </div>
                                    </td>
                                    <td>
                                      <div style={{ display: "flex", gap: "4px", alignItems: "center" }}>
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
                                          if (!confirm(`Regrade "${r.student_name}"'s assignment? This will delete the previous grade.`)) return;
                                          try {
                                            // Delete the previous result first
                                            await api.deleteResult(r.filename);
                                            setStatus((prev) => ({
                                              ...prev,
                                              results: prev.results.filter((res) => res.filename !== r.filename),
                                            }));
                                            addToast(`Regrading ${r.student_name}...`, "info");
                                            // Use the original filename to regrade
                                            const filename = r.original_filename || r.filename;
                                            await api.startGrading({
                                              assignments_folder: config.assignments_folder,
                                              output_folder: config.output_folder,
                                              roster_file: config.roster_file,
                                              grading_period: config.grading_period,
                                              grade_level: config.grade_level,
                                              subject: config.subject,
                                              teacher_name: config.teacher_name,
                                              school_name: config.school_name,
                                              ai_model: config.ai_model,
                                              selectedFiles: [filename],
                                              globalAINotes: globalAINotes,
                                              classPeriod: r.period || '',
                                              ensemble_models: config.ensemble_enabled && config.ensemble_models?.length >= 2 ? config.ensemble_models : null,
                                            });
                                            // Poll for completion
                                            const checkStatus = setInterval(async () => {
                                              const st = await api.getStatus();
                                              if (!st.is_running) {
                                                clearInterval(checkStatus);
                                                if (st.results && st.results.length > 0) {
                                                  const newResult = st.results.find(res =>
                                                    res.student_name === r.student_name &&
                                                    (res.assignment === r.assignment || res.filename === filename)
                                                  );
                                                  if (newResult) {
                                                    addToast(`Regraded ${r.student_name}: ${newResult.letter_grade} (${newResult.score}%)`, "success");
                                                  }
                                                }
                                              }
                                            }, 1000);
                                          } catch (err) {
                                            addToast(`Regrade failed: ${err.message}`, "error");
                                          }
                                        }}
                                        style={{
                                          background: "none",
                                          border: "none",
                                          color: "#fbbf24",
                                          cursor: "pointer",
                                          padding: "4px",
                                        }}
                                        title="Regrade this assignment"
                                        disabled={status.is_running}
                                      >
                                        <Icon name="RefreshCw" size={16} />
                                      </button>
                                      <button
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          sendSingleEmail(r, originalIndex);
                                        }}
                                        style={{
                                          background: "none",
                                          border: "none",
                                          color: r.student_email ? "#4ade80" : "#6b7280",
                                          cursor: r.student_email ? "pointer" : "not-allowed",
                                          padding: "4px",
                                          opacity: r.student_email ? 1 : 0.5,
                                        }}
                                        title={r.student_email ? `Send email to ${r.student_email}` : "No email address"}
                                        disabled={!r.student_email}
                                      >
                                        <Icon name="Mail" size={16} />
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
                                              await api.deleteResult(
                                                r.filename,
                                              );
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
                                              Object.keys(
                                                emailApprovals,
                                              ).forEach((key) => {
                                                const idx = parseInt(key);
                                                if (idx < originalIndex)
                                                  newApprovals[idx] =
                                                    emailApprovals[key];
                                                else if (idx > originalIndex)
                                                  newApprovals[idx - 1] =
                                                    emailApprovals[key];
                                              });
                                              setEmailApprovals(newApprovals);
                                            } catch (err) {
                                              addToast(
                                                "Error deleting result: " +
                                                  err.message,
                                                "error",
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
                                      </div>
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
                                      const emailToUse = edited?.email || r.student_email;
                                      if (!emailToUse) return null; // Skip if no email
                                      return {
                                        ...r,
                                        student_email: emailToUse,
                                        custom_email_subject:
                                          edited?.subject ||
                                          `Grade Report: ${r.assignment}`,
                                        custom_email_body:
                                          edited?.body ||
                                          getDefaultEmailBody(i),
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
                                      await api.sendEmails(approvedResults, config.teacher_email, config.teacher_name, config.email_signature);
                                    setEmailStatus({
                                      sending: false,
                                      sent:
                                        result.sent || approvedResults.length,
                                      failed: result.failed || 0,
                                      message: `Sent ${result.sent || approvedResults.length} emails successfully!`,
                                    });
                                    // Mark approved emails as sent
                                    const newSentEmails = { ...sentEmails };
                                    Object.keys(emailApprovals).forEach((idx) => {
                                      if (emailApprovals[idx] === "approved") {
                                        newSentEmails[idx] = true;
                                      }
                                    });
                                    setSentEmails(newSentEmails);
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

              {/* Settings Tab */}
              {activeTab === "settings" && (
                <div className="fade-in glass-card" style={{ padding: "25px" }}>
                  <h2
                    style={{
                      fontSize: "1.3rem",
                      fontWeight: 700,
                      marginBottom: "15px",
                      display: "flex",
                      alignItems: "center",
                      gap: "10px",
                    }}
                  >
                    <Icon name="Settings" size={24} />
                    Settings
                  </h2>

                  {/* Settings Sub-tabs */}
                  <div style={{ display: "flex", gap: "4px", marginBottom: "20px", borderBottom: "1px solid var(--glass-border)", paddingBottom: "12px", flexWrap: "wrap" }}>
                    {[
                      { id: "general", label: "General", icon: "FolderOpen" },
                      { id: "grading", label: "Grading", icon: "ClipboardCheck" },
                      { id: "ai", label: "AI", icon: "Sparkles" },
                      { id: "classroom", label: "Classroom", icon: "Users" },
                      { id: "integration", label: "Tools", icon: "Laptop" },
                      { id: "privacy", label: "Privacy", icon: "Shield" },
                    ].map((tab) => (
                      <button
                        key={tab.id}
                        onClick={() => setSettingsTab(tab.id)}
                        style={{
                          padding: "8px 14px",
                          borderRadius: "8px",
                          border: "none",
                          background: settingsTab === tab.id ? "var(--accent-primary)" : "transparent",
                          color: settingsTab === tab.id ? "white" : "var(--text-secondary)",
                          cursor: "pointer",
                          display: "flex",
                          alignItems: "center",
                          gap: "6px",
                          fontSize: "0.85rem",
                          fontWeight: settingsTab === tab.id ? 600 : 500,
                          transition: "all 0.2s",
                        }}
                      >
                        <Icon name={tab.icon} size={16} />
                        {tab.label}
                      </button>
                    ))}
                  </div>

                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: "20px",
                    }}
                  >
                    {/* General Tab */}
                    {settingsTab === "general" && (
                      <>
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
                          style={{
                            opacity: !config.assignments_folder ? 0.5 : 1,
                          }}
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
                          onClick={() =>
                            handleBrowse("folder", "output_folder")
                          }
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
                        <label className="label">Teacher Email</label>
                        <input
                          type="email"
                          className="input"
                          value={config.teacher_email}
                          onChange={(e) =>
                            setConfig((prev) => ({
                              ...prev,
                              teacher_email: e.target.value,
                            }))
                          }
                          placeholder="teacher@school.edu"
                        />
                        <span style={{ fontSize: "0.75rem", color: "#888", marginTop: "4px", display: "block" }}>
                          Students will reply to this email
                        </span>
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

                    {/* Email Signature */}
                    <div>
                      <label className="label">Email Signature</label>
                      <textarea
                        className="input"
                        value={config.email_signature}
                        onChange={(e) =>
                          setConfig((prev) => ({
                            ...prev,
                            email_signature: e.target.value,
                          }))
                        }
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.stopPropagation();
                          }
                        }}
                        placeholder={"Best regards," + String.fromCharCode(10) + "Mr. Smith" + String.fromCharCode(10) + "Room 204 | Office Hours: Mon-Fri 3-4pm"}
                        rows={4}
                        style={{ resize: "vertical", minHeight: "100px", fontFamily: "inherit", lineHeight: "1.5" }}
                      />
                      <span style={{ fontSize: "0.75rem", color: "#888", marginTop: "4px", display: "block" }}>
                        Appears at the end of grade feedback emails
                      </span>
                    </div>

                    {/* Notifications */}
                    <div>
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
                        <Icon name="Bell" size={20} style={{ color: "#f59e0b" }} />
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
                          <div
                            style={{
                              fontSize: "0.85rem",
                              color: "var(--text-muted)",
                            }}
                          >
                            Show popup notifications when assignments are graded
                          </div>
                        </div>
                      </label>
                    </div>
                      </>
                    )}

                    {/* Grading Tab */}
                    {settingsTab === "grading" && (
                      <>
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
                    </div>

                    {/* Rubric Configuration */}
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
                    </div>
                      </>
                    )}

                    {/* AI Tab */}
                    {settingsTab === "ai" && (
                      <>
                    {/* AI Model Selection */}
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
                        <Icon name="Sparkles" size={20} style={{ color: "#8b5cf6" }} />
                        AI Model
                      </h3>
                      <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "15px" }}>
                        Choose which AI model to use for grading and assessment generation.
                      </p>
                      <select
                        className="input"
                        value={config.ai_model}
                        onChange={(e) =>
                          setConfig((prev) => ({
                            ...prev,
                            ai_model: e.target.value,
                          }))
                        }
                        style={{ maxWidth: "350px" }}
                      >
                        <optgroup label="OpenAI">
                          <option value="gpt-4o-mini">
                            GPT-4o Mini (Fast & Cheap)
                          </option>
                          <option value="gpt-4o">
                            GPT-4o (Best Quality)
                          </option>
                        </optgroup>
                        <optgroup label="Anthropic">
                          <option value="claude-haiku">
                            Claude Haiku (Fast & Cheap)
                          </option>
                          <option value="claude-sonnet">
                            Claude Sonnet (Balanced)
                          </option>
                          <option value="claude-opus">
                            Claude Opus (Most Capable)
                          </option>
                        </optgroup>
                        <optgroup label="Google">
                          <option value="gemini-flash">
                            Gemini 2.0 Flash (Fast & Cheap)
                          </option>
                          <option value="gemini-pro">
                            Gemini 2.0 Pro (Balanced)
                          </option>
                        </optgroup>
                      </select>
                      <p
                        style={{
                          fontSize: "0.8rem",
                          color: "var(--text-muted)",
                          marginTop: "10px",
                          padding: "10px 14px",
                          background: (() => {
                            const isConfigured = config.ai_model?.startsWith("claude")
                              ? apiKeys.anthropicConfigured
                              : config.ai_model?.startsWith("gemini")
                                ? apiKeys.geminiConfigured
                                : apiKeys.openaiConfigured;
                            return isConfigured ? "rgba(74,222,128,0.1)" : "rgba(245,158,11,0.1)";
                          })(),
                          borderRadius: "8px",
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "8px",
                        }}
                      >
                        <Icon
                          name={(() => {
                            const isConfigured = config.ai_model?.startsWith("claude")
                              ? apiKeys.anthropicConfigured
                              : config.ai_model?.startsWith("gemini")
                                ? apiKeys.geminiConfigured
                                : apiKeys.openaiConfigured;
                            return isConfigured ? "CheckCircle" : "AlertCircle";
                          })()}
                          size={16}
                          style={{ color: (() => {
                            const isConfigured = config.ai_model?.startsWith("claude")
                              ? apiKeys.anthropicConfigured
                              : config.ai_model?.startsWith("gemini")
                                ? apiKeys.geminiConfigured
                                : apiKeys.openaiConfigured;
                            return isConfigured ? "#4ade80" : "#f59e0b";
                          })() }}
                        />
                        {config.ai_model?.startsWith("claude")
                          ? apiKeys.anthropicConfigured
                            ? "Anthropic API connected"
                            : "Add Anthropic API key below to use Claude"
                          : config.ai_model?.startsWith("gemini")
                            ? apiKeys.geminiConfigured
                              ? "Google AI API connected"
                              : "Add Google AI API key below to use Gemini"
                            : apiKeys.openaiConfigured
                              ? "OpenAI API connected"
                              : "Add OpenAI API key below to use GPT"}
                      </p>

                      {/* Ensemble Grading Toggle */}
                      <div style={{ marginTop: "20px", padding: "15px", background: "var(--input-bg)", borderRadius: "10px", border: "1px solid var(--input-border)" }}>
                        <label style={{ display: "flex", alignItems: "center", gap: "10px", cursor: "pointer" }}>
                          <input
                            type="checkbox"
                            checked={config.ensemble_enabled}
                            onChange={(e) => setConfig((prev) => ({ ...prev, ensemble_enabled: e.target.checked }))}
                            style={{ width: "18px", height: "18px" }}
                          />
                          <span style={{ fontWeight: 600 }}>
                            <Icon name="Users" size={16} style={{ marginRight: "6px", verticalAlign: "middle" }} />
                            Ensemble Grading
                          </span>
                          <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                            (Grade with multiple AIs for accuracy)
                          </span>
                        </label>

                        {config.ensemble_enabled && (
                          <div style={{ marginTop: "15px" }}>
                            <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "10px" }}>
                              Select 2-3 models to grade each assignment. Final score = median of all models.
                            </p>
                            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                              {[
                                { value: "gpt-4o-mini", label: "GPT-4o Mini", cost: "$0.001", provider: "openai" },
                                { value: "gpt-4o", label: "GPT-4o", cost: "$0.015", provider: "openai" },
                                { value: "claude-haiku", label: "Claude Haiku", cost: "$0.002", provider: "anthropic" },
                                { value: "claude-sonnet", label: "Claude Sonnet", cost: "$0.02", provider: "anthropic" },
                                { value: "gemini-flash", label: "Gemini Flash", cost: "$0.0005", provider: "gemini" },
                                { value: "gemini-pro", label: "Gemini Pro", cost: "$0.008", provider: "gemini" },
                              ].map((model) => {
                                const isConfigured = model.provider === "openai" ? apiKeys.openaiConfigured
                                  : model.provider === "anthropic" ? apiKeys.anthropicConfigured
                                  : apiKeys.geminiConfigured;
                                const isSelected = config.ensemble_models?.includes(model.value);
                                return (
                                  <label
                                    key={model.value}
                                    style={{
                                      display: "flex",
                                      alignItems: "center",
                                      gap: "10px",
                                      padding: "8px 12px",
                                      borderRadius: "8px",
                                      background: isSelected ? "rgba(139, 92, 246, 0.15)" : "transparent",
                                      border: isSelected ? "1px solid rgba(139, 92, 246, 0.3)" : "1px solid transparent",
                                      cursor: isConfigured ? "pointer" : "not-allowed",
                                      opacity: isConfigured ? 1 : 0.5,
                                    }}
                                  >
                                    <input
                                      type="checkbox"
                                      checked={isSelected}
                                      disabled={!isConfigured}
                                      onChange={(e) => {
                                        setConfig((prev) => {
                                          const models = prev.ensemble_models || [];
                                          if (e.target.checked) {
                                            return { ...prev, ensemble_models: [...models, model.value] };
                                          } else {
                                            return { ...prev, ensemble_models: models.filter((m) => m !== model.value) };
                                          }
                                        });
                                      }}
                                      style={{ width: "16px", height: "16px" }}
                                    />
                                    <span style={{ flex: 1 }}>{model.label}</span>
                                    <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>~{model.cost}/assignment</span>
                                    {!isConfigured && (
                                      <span style={{ fontSize: "0.7rem", color: "#f59e0b" }}>No API key</span>
                                    )}
                                  </label>
                                );
                              })}
                            </div>
                            {config.ensemble_models?.length >= 2 && (
                              <p style={{ marginTop: "10px", fontSize: "0.8rem", color: "#4ade80" }}>
                                <Icon name="CheckCircle" size={14} style={{ marginRight: "4px", verticalAlign: "middle" }} />
                                {config.ensemble_models.length} models selected - estimated ~${(
                                  config.ensemble_models.reduce((sum, m) => {
                                    const costs = { "gpt-4o-mini": 0.001, "gpt-4o": 0.015, "claude-haiku": 0.002, "claude-sonnet": 0.02, "gemini-flash": 0.0005, "gemini-pro": 0.008 };
                                    return sum + (costs[m] || 0);
                                  }, 0)
                                ).toFixed(4)}/assignment
                              </p>
                            )}
                            {config.ensemble_models?.length === 1 && (
                              <p style={{ marginTop: "10px", fontSize: "0.8rem", color: "#f59e0b" }}>
                                <Icon name="AlertCircle" size={14} style={{ marginRight: "4px", verticalAlign: "middle" }} />
                                Select at least 2 models for ensemble grading
                              </p>
                            )}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Global AI Instructions */}
                    <div>
                      <h3
                        style={{
                          fontSize: "1.1rem",
                          fontWeight: 700,
                          marginBottom: "8px",
                          display: "flex",
                          alignItems: "center",
                          gap: "10px",
                        }}
                      >
                        <Icon name="MessageSquare" size={20} style={{ color: "#6366f1" }} />
                        Global AI Instructions
                      </h3>
                      <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "10px" }}>
                        These instructions apply to both grading AND assessment generation. Include differentiation rules for periods here.
                      </p>
                      <textarea
                        className="input"
                        value={globalAINotes}
                        onChange={(e) => setGlobalAINotes(e.target.value)}
                        placeholder="Example: For assessment generation, Periods 1,2,5 are advanced (7th-8th grade level). Periods 4,6,7 should be 6th grade level only."
                        style={{ minHeight: "120px", resize: "vertical" }}
                      />
                    </div>

                    {/* API Keys Section */}
                    <div>
                      <h3
                        style={{
                          fontSize: "1.1rem",
                          fontWeight: 700,
                          marginBottom: "8px",
                          display: "flex",
                          alignItems: "center",
                          gap: "8px",
                        }}
                      >
                        <Icon name="Key" size={20} style={{ color: "#f59e0b" }} />
                        API Keys
                      </h3>
                      <p
                        style={{
                          fontSize: "0.85rem",
                          color: "var(--text-muted)",
                          marginBottom: "15px",
                        }}
                      >
                        Connect your AI provider API keys. Keys are stored
                        securely and never shared.
                      </p>

                      <div
                        style={{
                          display: "flex",
                          flexDirection: "column",
                          gap: "15px",
                        }}
                      >
                        {/* OpenAI API Key */}
                        <div>
                          <label
                            className="label"
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "8px",
                            }}
                          >
                            OpenAI API Key
                            {apiKeys.openaiConfigured && (
                              <span
                                style={{
                                  color: "#22c55e",
                                  fontSize: "0.75rem",
                                  display: "flex",
                                  alignItems: "center",
                                  gap: "4px",
                                }}
                              >
                                <Icon name="CheckCircle" size={14} /> Connected
                              </span>
                            )}
                          </label>
                          <div style={{ display: "flex", gap: "10px" }}>
                            <div style={{ position: "relative", flex: 1 }}>
                              <input
                                type={showApiKeys.openai ? "text" : "password"}
                                className="input"
                                value={apiKeys.openai}
                                onChange={(e) =>
                                  setApiKeys((prev) => ({
                                    ...prev,
                                    openai: e.target.value,
                                  }))
                                }
                                placeholder={
                                  apiKeys.openaiConfigured
                                    ? "••••••••••••••••"
                                    : "sk-..."
                                }
                                style={{ paddingRight: "40px" }}
                              />
                              <button
                                type="button"
                                onClick={() =>
                                  setShowApiKeys((prev) => ({
                                    ...prev,
                                    openai: !prev.openai,
                                  }))
                                }
                                style={{
                                  position: "absolute",
                                  right: "10px",
                                  top: "50%",
                                  transform: "translateY(-50%)",
                                  background: "none",
                                  border: "none",
                                  cursor: "pointer",
                                  color: "var(--text-muted)",
                                }}
                              >
                                <Icon
                                  name={showApiKeys.openai ? "EyeOff" : "Eye"}
                                  size={18}
                                />
                              </button>
                            </div>
                          </div>
                          <p
                            style={{
                              fontSize: "0.75rem",
                              color: "var(--text-muted)",
                              marginTop: "4px",
                            }}
                          >
                            Get your key from{" "}
                            <a
                              href="https://platform.openai.com/api-keys"
                              target="_blank"
                              rel="noopener noreferrer"
                              style={{ color: "var(--accent)" }}
                            >
                              platform.openai.com
                            </a>
                          </p>
                        </div>

                        {/* Anthropic API Key */}
                        <div>
                          <label
                            className="label"
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "8px",
                            }}
                          >
                            Anthropic (Claude) API Key
                            {apiKeys.anthropicConfigured && (
                              <span
                                style={{
                                  color: "#22c55e",
                                  fontSize: "0.75rem",
                                  display: "flex",
                                  alignItems: "center",
                                  gap: "4px",
                                }}
                              >
                                <Icon name="CheckCircle" size={14} /> Connected
                              </span>
                            )}
                          </label>
                          <div style={{ display: "flex", gap: "10px" }}>
                            <div style={{ position: "relative", flex: 1 }}>
                              <input
                                type={
                                  showApiKeys.anthropic ? "text" : "password"
                                }
                                className="input"
                                value={apiKeys.anthropic}
                                onChange={(e) =>
                                  setApiKeys((prev) => ({
                                    ...prev,
                                    anthropic: e.target.value,
                                  }))
                                }
                                placeholder={
                                  apiKeys.anthropicConfigured
                                    ? "••••••••••••••••"
                                    : "sk-ant-..."
                                }
                                style={{ paddingRight: "40px" }}
                              />
                              <button
                                type="button"
                                onClick={() =>
                                  setShowApiKeys((prev) => ({
                                    ...prev,
                                    anthropic: !prev.anthropic,
                                  }))
                                }
                                style={{
                                  position: "absolute",
                                  right: "10px",
                                  top: "50%",
                                  transform: "translateY(-50%)",
                                  background: "none",
                                  border: "none",
                                  cursor: "pointer",
                                  color: "var(--text-muted)",
                                }}
                              >
                                <Icon
                                  name={
                                    showApiKeys.anthropic ? "EyeOff" : "Eye"
                                  }
                                  size={18}
                                />
                              </button>
                            </div>
                          </div>
                          <p
                            style={{
                              fontSize: "0.75rem",
                              color: "var(--text-muted)",
                              marginTop: "4px",
                            }}
                          >
                            Get your key from{" "}
                            <a
                              href="https://console.anthropic.com/settings/keys"
                              target="_blank"
                              rel="noopener noreferrer"
                              style={{ color: "var(--accent)" }}
                            >
                              console.anthropic.com
                            </a>
                          </p>
                        </div>

                        {/* Google AI (Gemini) API Key */}
                        <div>
                          <label
                            className="label"
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "8px",
                            }}
                          >
                            Google AI (Gemini) API Key
                            {apiKeys.geminiConfigured && (
                              <span
                                style={{
                                  color: "#22c55e",
                                  fontSize: "0.75rem",
                                  display: "flex",
                                  alignItems: "center",
                                  gap: "4px",
                                }}
                              >
                                <Icon name="CheckCircle" size={14} /> Connected
                              </span>
                            )}
                          </label>
                          <div style={{ display: "flex", gap: "10px" }}>
                            <div style={{ position: "relative", flex: 1 }}>
                              <input
                                type={
                                  showApiKeys.gemini ? "text" : "password"
                                }
                                className="input"
                                value={apiKeys.gemini}
                                onChange={(e) =>
                                  setApiKeys((prev) => ({
                                    ...prev,
                                    gemini: e.target.value,
                                  }))
                                }
                                placeholder={
                                  apiKeys.geminiConfigured
                                    ? "••••••••••••••••"
                                    : "AIza..."
                                }
                                style={{ paddingRight: "40px" }}
                              />
                              <button
                                type="button"
                                onClick={() =>
                                  setShowApiKeys((prev) => ({
                                    ...prev,
                                    gemini: !prev.gemini,
                                  }))
                                }
                                style={{
                                  position: "absolute",
                                  right: "10px",
                                  top: "50%",
                                  transform: "translateY(-50%)",
                                  background: "none",
                                  border: "none",
                                  cursor: "pointer",
                                  color: "var(--text-muted)",
                                }}
                              >
                                <Icon
                                  name={
                                    showApiKeys.gemini ? "EyeOff" : "Eye"
                                  }
                                  size={18}
                                />
                              </button>
                            </div>
                          </div>
                          <p
                            style={{
                              fontSize: "0.75rem",
                              color: "var(--text-muted)",
                              marginTop: "4px",
                            }}
                          >
                            Get your key from{" "}
                            <a
                              href="https://aistudio.google.com/apikey"
                              target="_blank"
                              rel="noopener noreferrer"
                              style={{ color: "var(--accent)" }}
                            >
                              aistudio.google.com
                            </a>
                          </p>
                        </div>

                        <button
                          onClick={async () => {
                            setSavingApiKeys(true);
                            try {
                              const response = await fetch(
                                "/api/save-api-keys",
                                {
                                  method: "POST",
                                  headers: {
                                    "Content-Type": "application/json",
                                  },
                                  body: JSON.stringify({
                                    openai_key: apiKeys.openai || undefined,
                                    anthropic_key: apiKeys.anthropic || undefined,
                                    gemini_key: apiKeys.gemini || undefined,
                                  }),
                                },
                              );
                              const data = await response.json();
                              if (data.status === "success") {
                                setApiKeys((prev) => ({
                                  ...prev,
                                  openai: "",
                                  anthropic: "",
                                  gemini: "",
                                  openaiConfigured: data.openai_configured,
                                  anthropicConfigured: data.anthropic_configured,
                                  geminiConfigured: data.gemini_configured,
                                }));
                                addToast(
                                  "API keys saved successfully",
                                  "success",
                                );
                              } else {
                                addToast(
                                  data.error || "Failed to save API keys",
                                  "error",
                                );
                              }
                            } catch (err) {
                              addToast(
                                "Error saving API keys: " + err.message,
                                "error",
                              );
                            } finally {
                              setSavingApiKeys(false);
                            }
                          }}
                          disabled={
                            savingApiKeys ||
                            (!apiKeys.openai && !apiKeys.anthropic && !apiKeys.gemini)
                          }
                          className="btn btn-primary"
                          style={{
                            alignSelf: "flex-start",
                            opacity:
                              !apiKeys.openai && !apiKeys.anthropic && !apiKeys.gemini ? 0.5 : 1,
                          }}
                        >
                          {savingApiKeys ? "Saving..." : "Save API Keys"}
                        </button>
                      </div>
                    </div>
                      </>
                    )}

                    {/* Integration Tab (now Tools) */}
                    {settingsTab === "integration" && (
                      <>
                    {/* Available EdTech Tools */}
                    <div>
                      <h3
                        style={{
                          fontSize: "1.1rem",
                          fontWeight: 700,
                          marginBottom: "8px",
                          display: "flex",
                          alignItems: "center",
                          gap: "8px",
                        }}
                      >
                        <Icon name="Laptop" size={20} />
                        Available EdTech Tools
                      </h3>
                      <p
                        style={{
                          fontSize: "0.85rem",
                          color: "var(--text-muted)",
                          marginBottom: "15px",
                        }}
                      >
                        Select the tools your school provides. Lesson plans will
                        only suggest activities using these tools.
                      </p>

                      <div
                        style={{
                          display: "grid",
                          gridTemplateColumns:
                            "repeat(auto-fill, minmax(200px, 1fr))",
                          gap: "10px",
                          maxHeight: "300px",
                          overflowY: "auto",
                          padding: "10px",
                          background: "var(--input-bg)",
                          borderRadius: "12px",
                          border: "1px solid var(--input-border)",
                        }}
                      >
                        {EDTECH_TOOLS.map((tool) => (
                          <label
                            key={tool.id}
                            style={{
                              display: "flex",
                              alignItems: "flex-start",
                              gap: "10px",
                              cursor: "pointer",
                              padding: "10px",
                              borderRadius: "8px",
                              background: config.availableTools?.includes(
                                tool.id,
                              )
                                ? "rgba(99,102,241,0.15)"
                                : "transparent",
                              border: config.availableTools?.includes(tool.id)
                                ? "1px solid rgba(99,102,241,0.3)"
                                : "1px solid transparent",
                              transition: "all 0.2s",
                            }}
                          >
                            <input
                              type="checkbox"
                              checked={
                                config.availableTools?.includes(tool.id) ||
                                false
                              }
                              onChange={(e) => {
                                const newTools = e.target.checked
                                  ? [...(config.availableTools || []), tool.id]
                                  : (config.availableTools || []).filter(
                                      (t) => t !== tool.id,
                                    );
                                setConfig((prev) => ({
                                  ...prev,
                                  availableTools: newTools,
                                }));
                              }}
                              style={{
                                width: "16px",
                                height: "16px",
                                accentColor: "var(--accent-primary)",
                                cursor: "pointer",
                                marginTop: "2px",
                              }}
                            />
                            <div>
                              <div
                                style={{ fontWeight: 600, fontSize: "0.9rem" }}
                              >
                                {tool.name}
                              </div>
                              <div
                                style={{
                                  fontSize: "0.75rem",
                                  color: "var(--text-muted)",
                                }}
                              >
                                {tool.category} • {tool.description}
                              </div>
                            </div>
                          </label>
                        ))}

                        {/* Custom Tools */}
                        {customTools.map((tool) => (
                          <label
                            key={tool}
                            style={{
                              display: "flex",
                              alignItems: "flex-start",
                              gap: "10px",
                              cursor: "pointer",
                              padding: "10px",
                              borderRadius: "8px",
                              background: config.availableTools?.includes(
                                `custom:${tool}`,
                              )
                                ? "rgba(16,185,129,0.15)"
                                : "transparent",
                              border: config.availableTools?.includes(
                                `custom:${tool}`,
                              )
                                ? "1px solid rgba(16,185,129,0.3)"
                                : "1px solid rgba(255,255,255,0.1)",
                              transition: "all 0.2s",
                            }}
                          >
                            <input
                              type="checkbox"
                              checked={
                                config.availableTools?.includes(
                                  `custom:${tool}`,
                                ) || false
                              }
                              onChange={(e) => {
                                const toolId = `custom:${tool}`;
                                const newTools = e.target.checked
                                  ? [...(config.availableTools || []), toolId]
                                  : (config.availableTools || []).filter(
                                      (t) => t !== toolId,
                                    );
                                setConfig((prev) => ({
                                  ...prev,
                                  availableTools: newTools,
                                }));
                              }}
                              style={{
                                width: "16px",
                                height: "16px",
                                accentColor: "#10b981",
                                cursor: "pointer",
                                marginTop: "2px",
                              }}
                            />
                            <div style={{ flex: 1 }}>
                              <div
                                style={{ fontWeight: 600, fontSize: "0.9rem" }}
                              >
                                {tool}
                              </div>
                              <div
                                style={{
                                  fontSize: "0.75rem",
                                  color: "var(--text-muted)",
                                }}
                              >
                                Custom • Added by you
                              </div>
                            </div>
                            <button
                              onClick={(e) => {
                                e.preventDefault();
                                setCustomTools(
                                  customTools.filter((t) => t !== tool),
                                );
                                setConfig((prev) => ({
                                  ...prev,
                                  availableTools: (
                                    prev.availableTools || []
                                  ).filter((t) => t !== `custom:${tool}`),
                                }));
                              }}
                              style={{
                                background: "rgba(239,68,68,0.2)",
                                border: "none",
                                borderRadius: "4px",
                                padding: "4px 8px",
                                color: "#ef4444",
                                cursor: "pointer",
                                fontSize: "0.75rem",
                              }}
                            >
                              Remove
                            </button>
                          </label>
                        ))}
                      </div>

                      {/* Add Custom Tool */}
                      <div style={{ marginTop: "15px" }}>
                        <label
                          style={{
                            fontSize: "0.85rem",
                            color: "var(--text-secondary)",
                            display: "block",
                            marginBottom: "8px",
                          }}
                        >
                          Add a custom tool not in the list:
                        </label>
                        <div style={{ display: "flex", gap: "8px" }}>
                          <input
                            type="text"
                            className="input"
                            value={newCustomTool}
                            onChange={(e) => setNewCustomTool(e.target.value)}
                            placeholder="e.g., Formative, Socrative, Classkick..."
                            style={{ flex: 1 }}
                            onKeyPress={(e) => {
                              if (e.key === "Enter" && newCustomTool.trim()) {
                                if (
                                  !customTools.includes(newCustomTool.trim())
                                ) {
                                  setCustomTools([
                                    ...customTools,
                                    newCustomTool.trim(),
                                  ]);
                                }
                                setNewCustomTool("");
                              }
                            }}
                          />
                          <button
                            onClick={() => {
                              if (
                                newCustomTool.trim() &&
                                !customTools.includes(newCustomTool.trim())
                              ) {
                                setCustomTools([
                                  ...customTools,
                                  newCustomTool.trim(),
                                ]);
                                setNewCustomTool("");
                              }
                            }}
                            className="btn btn-primary"
                            style={{ padding: "8px 16px" }}
                            disabled={!newCustomTool.trim()}
                          >
                            <Icon name="Plus" size={16} /> Add
                          </button>
                        </div>
                      </div>

                      <div
                        style={{
                          marginTop: "15px",
                          display: "flex",
                          gap: "10px",
                          flexWrap: "wrap",
                          alignItems: "center",
                        }}
                      >
                        <button
                          onClick={() => {
                            const allTools = [
                              ...EDTECH_TOOLS.map((t) => t.id),
                              ...customTools.map((t) => `custom:${t}`),
                            ];
                            setConfig((prev) => ({
                              ...prev,
                              availableTools: allTools,
                            }));
                          }}
                          className="btn btn-secondary"
                          style={{ padding: "6px 12px", fontSize: "0.85rem" }}
                        >
                          Select All
                        </button>
                        <button
                          onClick={() =>
                            setConfig((prev) => ({
                              ...prev,
                              availableTools: [],
                            }))
                          }
                          className="btn btn-secondary"
                          style={{ padding: "6px 12px", fontSize: "0.85rem" }}
                        >
                          Clear All
                        </button>
                        <span
                          style={{
                            fontSize: "0.85rem",
                            color: "var(--text-secondary)",
                          }}
                        >
                          {config.availableTools?.length || 0} tools selected
                          {customTools.length > 0 &&
                            ` (${customTools.length} custom)`}
                        </span>
                      </div>
                    </div>

                    {/* Assessment Platform Templates */}
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
                          marginBottom: "8px",
                          display: "flex",
                          alignItems: "center",
                          gap: "8px",
                        }}
                      >
                        <Icon name="FileSpreadsheet" size={20} />
                        Assessment Platform Templates
                      </h3>
                      <p
                        style={{
                          fontSize: "0.85rem",
                          color: "var(--text-muted)",
                          marginBottom: "15px",
                        }}
                      >
                        Upload sample templates from your assessment platforms (e.g., Wayground, Mastery Connect).
                        Graider will match the format when exporting assessments.
                      </p>

                      {/* Upload New Template */}
                      <div
                        style={{
                          padding: "15px",
                          background: "var(--glass-bg)",
                          borderRadius: "12px",
                          border: "1px dashed var(--glass-border)",
                          marginBottom: "15px",
                        }}
                      >
                        <div style={{ display: "flex", gap: "10px", alignItems: "flex-end", flexWrap: "wrap" }}>
                          <div style={{ flex: 1, minWidth: "150px" }}>
                            <label className="label" style={{ fontSize: "0.8rem" }}>Platform Name</label>
                            <select
                              className="input"
                              id="template-platform"
                              style={{ fontSize: "0.9rem" }}
                            >
                              <option value="wayground">Wayground</option>
                              <option value="mastery_connect">Mastery Connect</option>
                              <option value="edulastic">Edulastic</option>
                              <option value="illuminate">Illuminate</option>
                              <option value="schoology">Schoology</option>
                              <option value="custom">Other/Custom</option>
                            </select>
                          </div>
                          <div style={{ flex: 1, minWidth: "150px" }}>
                            <label className="label" style={{ fontSize: "0.8rem" }}>Template Name</label>
                            <input
                              type="text"
                              className="input"
                              id="template-name"
                              placeholder="e.g., Quiz Import Template"
                              style={{ fontSize: "0.9rem" }}
                            />
                          </div>
                          <div>
                            <input
                              type="file"
                              id="template-file"
                              accept=".csv,.xlsx,.xls,.json,.txt"
                              style={{ display: "none" }}
                              onChange={async (e) => {
                                const file = e.target.files[0];
                                if (!file) return;

                                const platform = document.getElementById("template-platform").value;
                                const name = document.getElementById("template-name").value || file.name;

                                setUploadingTemplate(true);
                                try {
                                  const result = await api.uploadAssessmentTemplate(file, platform, name);
                                  if (result.success) {
                                    addToast(`Template "${name}" uploaded successfully!`, "success");
                                    // Refresh templates list
                                    const templates = await api.getAssessmentTemplates();
                                    setAssessmentTemplates(templates.templates || []);
                                  } else {
                                    addToast("Error: " + (result.error || "Upload failed"), "error");
                                  }
                                } catch (err) {
                                  addToast("Error uploading template: " + err.message, "error");
                                } finally {
                                  setUploadingTemplate(false);
                                  e.target.value = "";
                                }
                              }}
                            />
                            <button
                              onClick={() => document.getElementById("template-file").click()}
                              className="btn btn-primary"
                              style={{ padding: "8px 16px" }}
                              disabled={uploadingTemplate}
                            >
                              {uploadingTemplate ? (
                                <>
                                  <Icon name="Loader2" size={16} className="spin" />
                                  Uploading...
                                </>
                              ) : (
                                <>
                                  <Icon name="Upload" size={16} />
                                  Upload Template
                                </>
                              )}
                            </button>
                          </div>
                        </div>
                        <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "10px" }}>
                          Supported formats: CSV, Excel (.xlsx), JSON, TXT
                        </p>
                      </div>

                      {/* Existing Templates */}
                      {assessmentTemplates.length > 0 && (
                        <div
                          style={{
                            display: "flex",
                            flexDirection: "column",
                            gap: "10px",
                          }}
                        >
                          <label style={{ fontSize: "0.85rem", fontWeight: 600 }}>
                            Uploaded Templates ({assessmentTemplates.length})
                          </label>
                          {assessmentTemplates.map((template) => (
                            <div
                              key={template.id}
                              style={{
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "space-between",
                                padding: "12px 15px",
                                background: "var(--glass-bg)",
                                borderRadius: "10px",
                                border: "1px solid var(--glass-border)",
                              }}
                            >
                              <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                                <Icon
                                  name={template.extension === ".csv" ? "Table" : template.extension === ".xlsx" ? "FileSpreadsheet" : "FileText"}
                                  size={20}
                                  style={{ color: "var(--accent-primary)" }}
                                />
                                <div>
                                  <div style={{ fontWeight: 600, fontSize: "0.9rem" }}>
                                    {template.name}
                                  </div>
                                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                                    {template.platform} • {template.structure?.columns?.length || 0} columns • {template.extension}
                                  </div>
                                </div>
                              </div>
                              <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                                {template.structure?.columns && (
                                  <span
                                    style={{
                                      fontSize: "0.7rem",
                                      color: "var(--text-muted)",
                                      maxWidth: "200px",
                                      overflow: "hidden",
                                      textOverflow: "ellipsis",
                                      whiteSpace: "nowrap",
                                    }}
                                    title={template.structure.columns.join(", ")}
                                  >
                                    {template.structure.columns.slice(0, 3).join(", ")}
                                    {template.structure.columns.length > 3 && "..."}
                                  </span>
                                )}
                                <button
                                  onClick={async () => {
                                    try {
                                      await api.deleteAssessmentTemplate(template.id);
                                      setAssessmentTemplates(assessmentTemplates.filter(t => t.id !== template.id));
                                      addToast("Template deleted", "info");
                                    } catch (err) {
                                      addToast("Error deleting template", "error");
                                    }
                                  }}
                                  style={{
                                    background: "rgba(239, 68, 68, 0.1)",
                                    border: "none",
                                    borderRadius: "6px",
                                    padding: "6px 10px",
                                    color: "#ef4444",
                                    cursor: "pointer",
                                    display: "flex",
                                    alignItems: "center",
                                    gap: "4px",
                                    fontSize: "0.8rem",
                                  }}
                                >
                                  <Icon name="Trash2" size={14} />
                                  Delete
                                </button>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}

                      {assessmentTemplates.length === 0 && (
                        <div
                          style={{
                            textAlign: "center",
                            padding: "20px",
                            color: "var(--text-muted)",
                            fontSize: "0.85rem",
                          }}
                        >
                          No templates uploaded yet. Upload a sample file from your assessment platform to get started.
                        </div>
                      )}
                    </div>
                      </>
                    )}

                    {/* Classroom Tab */}
                    {settingsTab === "classroom" && (
                      <>
                    {/* Roster Upload Section */}
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
                              addToast(result.error, "error");
                            } else {
                              const rostersData = await api.listRosters();
                              setRosters(rostersData.rosters || []);
                              setRosterMappingModal({
                                show: true,
                                roster: result,
                              });
                            }
                          } catch (err) {
                            addToast("Upload failed: " + err.message, "error");
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
                                    setRosterMappingModal({
                                      show: true,
                                      roster,
                                    })
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
                            addToast(
                              "Please enter a period name first",
                              "warning",
                            );
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
                              addToast(result.error, "error");
                            } else {
                              const periodsData = await api.listPeriods();
                              setPeriods(periodsData.periods || []);
                              setNewPeriodName("");
                            }
                          } catch (err) {
                            addToast("Upload failed: " + err.message, "error");
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
                            opacity:
                              !newPeriodName.trim() || uploadingPeriod
                                ? 0.5
                                : 1,
                            cursor:
                              !newPeriodName.trim() || uploadingPeriod
                                ? "not-allowed"
                                : "pointer",
                          }}
                          title={
                            !newPeriodName.trim()
                              ? "Enter a period name first"
                              : ""
                          }
                        >
                          <Icon name="Upload" size={18} />
                          {uploadingPeriod
                            ? "Uploading..."
                            : "Upload CSV/Excel"}
                        </button>
                      </div>
                      {!newPeriodName.trim() && (
                        <p
                          style={{
                            fontSize: "0.75rem",
                            color: "var(--text-muted)",
                            marginTop: "-10px",
                            marginBottom: "10px",
                          }}
                        >
                          Enter a period name above, then click Upload
                        </p>
                      )}

                      {sortedPeriods.length > 0 && (
                        <div
                          style={{
                            display: "flex",
                            flexWrap: "wrap",
                            gap: "10px",
                          }}
                        >
                          {sortedPeriods.map((period) => (
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
                              <div style={{ flex: 1 }}>
                                <div
                                  style={{
                                    fontWeight: 600,
                                    fontSize: "0.9rem",
                                  }}
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
                              <select
                                value={period.class_level || "standard"}
                                onChange={async (e) => {
                                  const newLevel = e.target.value;
                                  await api.updatePeriodLevel(period.filename, newLevel);
                                  const data = await api.listPeriods();
                                  setPeriods(data.periods || []);
                                }}
                                style={{
                                  padding: "4px 8px",
                                  borderRadius: "6px",
                                  border: "1px solid var(--glass-border)",
                                  background: period.class_level === "advanced" ? "rgba(139, 92, 246, 0.2)" : period.class_level === "support" ? "rgba(244, 114, 182, 0.2)" : "var(--input-bg)",
                                  color: period.class_level === "advanced" ? "#a78bfa" : period.class_level === "support" ? "#f472b6" : "var(--text-primary)",
                                  fontSize: "0.8rem",
                                  cursor: "pointer",
                                }}
                              >
                                <option value="standard">Standard</option>
                                <option value="advanced">Advanced</option>
                                <option value="support">Support</option>
                              </select>
                              <button
                                onClick={async () => {
                                  if (
                                    confirm(`Delete ${period.period_name}?`)
                                  ) {
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

                    {/* IEP/504 Accommodations Section */}
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
                          name="Heart"
                          size={20}
                          style={{ color: "#f472b6" }}
                        />
                        IEP/504 Accommodations
                        <span
                          style={{
                            fontSize: "0.7rem",
                            padding: "2px 8px",
                            background: "rgba(74, 222, 128, 0.2)",
                            color: "#4ade80",
                            borderRadius: "4px",
                            fontWeight: 500,
                          }}
                        >
                          FERPA Compliant
                        </span>
                      </h3>
                      <p
                        style={{
                          fontSize: "0.85rem",
                          color: "var(--text-secondary)",
                          marginBottom: "20px",
                        }}
                      >
                        Assign accommodation presets to students for
                        personalized feedback. Only accommodation types are sent
                        to AI - never student names or IDs.
                      </p>

                      {/* Available Presets */}
                      <div style={{ marginBottom: "20px" }}>
                        <div
                          style={{
                            fontWeight: 600,
                            marginBottom: "12px",
                            fontSize: "0.95rem",
                          }}
                        >
                          Available Presets
                        </div>
                        <div
                          style={{
                            display: "grid",
                            gridTemplateColumns:
                              "repeat(auto-fill, minmax(200px, 1fr))",
                            gap: "10px",
                          }}
                        >
                          {accommodationPresets.map((preset) => (
                            <div
                              key={preset.id}
                              style={{
                                padding: "12px",
                                background: "var(--input-bg)",
                                borderRadius: "8px",
                                border: "1px solid var(--input-border)",
                              }}
                            >
                              <div
                                style={{
                                  display: "flex",
                                  alignItems: "center",
                                  gap: "8px",
                                  marginBottom: "6px",
                                }}
                              >
                                <Icon
                                  name={preset.icon || "FileText"}
                                  size={16}
                                  style={{ color: "#f472b6" }}
                                />
                                <span
                                  style={{
                                    fontWeight: 600,
                                    fontSize: "0.85rem",
                                  }}
                                >
                                  {preset.name}
                                </span>
                              </div>
                              <p
                                style={{
                                  fontSize: "0.75rem",
                                  color: "var(--text-muted)",
                                  margin: 0,
                                }}
                              >
                                {preset.description}
                              </p>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Student Accommodations List */}
                      <div style={{ marginBottom: "20px" }}>
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                            marginBottom: "12px",
                          }}
                        >
                          <div style={{ fontWeight: 600, fontSize: "0.95rem" }}>
                            Student Accommodations (
                            {Object.keys(studentAccommodations).length}{" "}
                            students)
                          </div>
                          <button
                            onClick={() =>
                              setAccommodationModal({
                                show: true,
                                studentId: null,
                              })
                            }
                            className="btn btn-primary"
                            style={{ fontSize: "0.8rem", padding: "6px 12px" }}
                          >
                            <Icon name="Plus" size={14} />
                            Add Student
                          </button>
                        </div>

                        {Object.keys(studentAccommodations).length > 0 ? (
                          <div
                            style={{
                              maxHeight: "200px",
                              overflowY: "auto",
                              display: "flex",
                              flexDirection: "column",
                              gap: "8px",
                            }}
                          >
                            {Object.entries(studentAccommodations).map(
                              ([studentId, data]) => (
                                <div
                                  key={studentId}
                                  style={{
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "space-between",
                                    padding: "10px 14px",
                                    background: "var(--input-bg)",
                                    borderRadius: "8px",
                                    border: "1px solid var(--input-border)",
                                  }}
                                >
                                  <div>
                                    <div
                                      style={{
                                        fontWeight: 600,
                                        fontSize: "0.85rem",
                                      }}
                                    >
                                      Student ID:{" "}
                                      {studentId.length > 20
                                        ? studentId.slice(0, 20) + "..."
                                        : studentId}
                                    </div>
                                    <div
                                      style={{
                                        display: "flex",
                                        gap: "6px",
                                        marginTop: "4px",
                                        flexWrap: "wrap",
                                      }}
                                    >
                                      {data.presets.map((preset) => (
                                        <span
                                          key={preset.id}
                                          style={{
                                            padding: "2px 8px",
                                            background:
                                              "rgba(244, 114, 182, 0.15)",
                                            color: "#f472b6",
                                            borderRadius: "4px",
                                            fontSize: "0.7rem",
                                            fontWeight: 500,
                                          }}
                                        >
                                          {preset.name}
                                        </span>
                                      ))}
                                      {data.custom_notes && (
                                        <span
                                          style={{
                                            padding: "2px 8px",
                                            background:
                                              "rgba(99, 102, 241, 0.15)",
                                            color: "#818cf8",
                                            borderRadius: "4px",
                                            fontSize: "0.7rem",
                                            fontWeight: 500,
                                          }}
                                        >
                                          Custom Notes
                                        </span>
                                      )}
                                    </div>
                                  </div>
                                  <div style={{ display: "flex", gap: "6px" }}>
                                    <button
                                      onClick={() => {
                                        setSelectedAccommodationPresets(
                                          data.presets.map((p) => p.id),
                                        );
                                        setAccommodationCustomNotes(
                                          data.custom_notes || "",
                                        );
                                        setAccommodationModal({
                                          show: true,
                                          studentId,
                                        });
                                      }}
                                      className="btn btn-secondary"
                                      style={{ padding: "4px 8px" }}
                                    >
                                      <Icon name="Edit2" size={14} />
                                    </button>
                                    <button
                                      onClick={async () => {
                                        if (
                                          confirm(
                                            "Remove accommodations for this student?",
                                          )
                                        ) {
                                          try {
                                            await api.deleteStudentAccommodation(
                                              studentId,
                                            );
                                            const newData = {
                                              ...studentAccommodations,
                                            };
                                            delete newData[studentId];
                                            setStudentAccommodations(newData);
                                          } catch (err) {
                                            addToast(
                                              "Error removing accommodation: " +
                                                err.message,
                                              "error",
                                            );
                                          }
                                        }
                                      }}
                                      className="btn btn-secondary"
                                      style={{
                                        padding: "4px 8px",
                                        color: "#ef4444",
                                      }}
                                    >
                                      <Icon name="Trash2" size={14} />
                                    </button>
                                  </div>
                                </div>
                              ),
                            )}
                          </div>
                        ) : (
                          <div
                            style={{
                              padding: "30px",
                              textAlign: "center",
                              background: "var(--input-bg)",
                              borderRadius: "8px",
                              border: "1px dashed var(--input-border)",
                            }}
                          >
                            <Icon
                              name="Heart"
                              size={32}
                              style={{
                                color: "var(--text-muted)",
                                marginBottom: "10px",
                              }}
                            />
                            <p
                              style={{
                                color: "var(--text-muted)",
                                fontSize: "0.85rem",
                                margin: 0,
                              }}
                            >
                              No students with accommodations yet. Add students
                              from your roster.
                            </p>
                          </div>
                        )}
                      </div>

                      {/* Import/Export */}
                      <div
                        style={{
                          padding: "15px",
                          background: "var(--input-bg)",
                          borderRadius: "10px",
                          border: "1px solid var(--input-border)",
                        }}
                      >
                        <div style={{ fontWeight: 600, marginBottom: "12px" }}>
                          Import & Export
                        </div>
                        <div
                          style={{
                            display: "flex",
                            gap: "10px",
                            flexWrap: "wrap",
                          }}
                        >
                          <label
                            className="btn btn-secondary"
                            style={{ fontSize: "0.85rem", cursor: "pointer" }}
                          >
                            <Icon name="Upload" size={16} />
                            Import from CSV
                            <input
                              type="file"
                              accept=".csv"
                              style={{ display: "none" }}
                              onChange={async (e) => {
                                const file = e.target.files?.[0];
                                if (!file) return;
                                try {
                                  const result = await api.importAccommodations(
                                    file,
                                    "student_id",
                                    "accommodation_type",
                                    "accommodation_notes",
                                  );
                                  addToast(
                                    "Import complete: " +
                                      result.imported +
                                      " imported, " +
                                      result.skipped +
                                      " skipped",
                                    "success",
                                  );
                                  // Reload accommodations
                                  const data =
                                    await api.getStudentAccommodations();
                                  if (data.accommodations)
                                    setStudentAccommodations(
                                      data.accommodations,
                                    );
                                } catch (err) {
                                  addToast(
                                    "Import failed: " + err.message,
                                    "error",
                                  );
                                }
                                e.target.value = "";
                              }}
                            />
                          </label>
                          <button
                            onClick={async () => {
                              try {
                                const data = await api.exportAccommodations();
                                const blob = new Blob(
                                  [JSON.stringify(data, null, 2)],
                                  { type: "application/json" },
                                );
                                const url = URL.createObjectURL(blob);
                                const a = document.createElement("a");
                                a.href = url;
                                a.download =
                                  "graider_accommodations_" +
                                  new Date().toISOString().split("T")[0] +
                                  ".json";
                                a.click();
                                URL.revokeObjectURL(url);
                              } catch (err) {
                                addToast(
                                  "Export failed: " + err.message,
                                  "error",
                                );
                              }
                            }}
                            className="btn btn-secondary"
                            style={{ fontSize: "0.85rem" }}
                          >
                            <Icon name="Download" size={16} />
                            Export Accommodations
                          </button>
                        </div>
                        <p
                          style={{
                            fontSize: "0.75rem",
                            color: "var(--text-muted)",
                            marginTop: "10px",
                          }}
                        >
                          CSV should have columns: student_id,
                          accommodation_type, accommodation_notes (optional)
                        </p>
                      </div>
                    </div>
                      </>
                    )}

                    {/* Privacy Tab */}
                    {settingsTab === "privacy" && (
                      <>
                    {/* FERPA Compliance & Data Privacy */}
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
                        Graider is designed for FERPA compliance. Student names
                        are sanitized before AI processing, and all data is
                        stored locally on your computer.
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
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "8px",
                              marginBottom: "8px",
                            }}
                          >
                            <Icon
                              name="CheckCircle"
                              size={16}
                              style={{ color: "#4ade80" }}
                            />
                            <span
                              style={{ fontWeight: 600, fontSize: "0.9rem" }}
                            >
                              PII Sanitization
                            </span>
                          </div>
                          <p
                            style={{
                              fontSize: "0.8rem",
                              color: "var(--text-secondary)",
                              margin: 0,
                            }}
                          >
                            Student names, IDs, emails, and phone numbers are
                            removed before AI processing
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
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "8px",
                              marginBottom: "8px",
                            }}
                          >
                            <Icon
                              name="CheckCircle"
                              size={16}
                              style={{ color: "#4ade80" }}
                            />
                            <span
                              style={{ fontWeight: 600, fontSize: "0.9rem" }}
                            >
                              Local Storage Only
                            </span>
                          </div>
                          <p
                            style={{
                              fontSize: "0.8rem",
                              color: "var(--text-secondary)",
                              margin: 0,
                            }}
                          >
                            All data stays on your computer. No cloud storage of
                            student information
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
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "8px",
                              marginBottom: "8px",
                            }}
                          >
                            <Icon
                              name="CheckCircle"
                              size={16}
                              style={{ color: "#4ade80" }}
                            />
                            <span
                              style={{ fontWeight: 600, fontSize: "0.9rem" }}
                            >
                              No AI Training
                            </span>
                          </div>
                          <p
                            style={{
                              fontSize: "0.8rem",
                              color: "var(--text-secondary)",
                              margin: 0,
                            }}
                          >
                            OpenAI API does not use submitted data to train
                            models (per their policy)
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
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "8px",
                              marginBottom: "8px",
                            }}
                          >
                            <Icon
                              name="CheckCircle"
                              size={16}
                              style={{ color: "#4ade80" }}
                            />
                            <span
                              style={{ fontWeight: 600, fontSize: "0.9rem" }}
                            >
                              Audit Logging
                            </span>
                          </div>
                          <p
                            style={{
                              fontSize: "0.8rem",
                              color: "var(--text-secondary)",
                              margin: 0,
                            }}
                          >
                            All data access is logged locally for compliance
                            tracking
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
                        <div style={{ fontWeight: 600, marginBottom: "12px" }}>
                          Data Management
                        </div>
                        <div
                          style={{
                            display: "flex",
                            gap: "10px",
                            flexWrap: "wrap",
                          }}
                        >
                          <button
                            onClick={async () => {
                              try {
                                const response = await fetch(
                                  "/api/ferpa/data-summary",
                                );
                                const data = await response.json();
                                alert(
                                  `Data Storage Summary\n\n` +
                                    `• Grading Results: ${data.results.count} records\n` +
                                    `• Settings: ${data.settings.exists ? "Saved" : "Not saved"}\n` +
                                    `• Audit Log: ${data.audit_log.exists ? "Active" : "Not started"}\n\n` +
                                    `Data Locations:\n` +
                                    data.data_locations.join("\n"),
                                );
                              } catch (err) {
                                addToast(
                                  "Failed to fetch data summary",
                                  "error",
                                );
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
                                const response = await fetch(
                                  "/api/ferpa/export-data",
                                );
                                const data = await response.json();
                                const blob = new Blob(
                                  [JSON.stringify(data, null, 2)],
                                  { type: "application/json" },
                                );
                                const url = URL.createObjectURL(blob);
                                const a = document.createElement("a");
                                a.href = url;
                                a.download = `graider_export_${new Date().toISOString().split("T")[0]}.json`;
                                a.click();
                                URL.revokeObjectURL(url);
                              } catch (err) {
                                addToast("Failed to export data", "error");
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
                              if (
                                !confirm(
                                  "⚠️ DELETE ALL STUDENT DATA?\n\n" +
                                    "This will permanently delete:\n" +
                                    "• All grading results\n" +
                                    "• Current session data\n\n" +
                                    "This action cannot be undone.\n\n" +
                                    "Type 'DELETE' in the next prompt to confirm.",
                                )
                              )
                                return;

                              const confirmText = prompt(
                                "Type DELETE to confirm:",
                              );
                              if (confirmText !== "DELETE") {
                                addToast("Deletion cancelled", "warning");
                                return;
                              }

                              try {
                                const response = await fetch(
                                  "/api/ferpa/delete-all-data",
                                  {
                                    method: "POST",
                                    headers: {
                                      "Content-Type": "application/json",
                                    },
                                    body: JSON.stringify({ confirm: true }),
                                  },
                                );
                                const data = await response.json();
                                if (data.status === "success") {
                                  addToast(
                                    "All student data has been deleted",
                                    "success",
                                  );
                                  setTimeout(
                                    () => window.location.reload(),
                                    1000,
                                  );
                                } else {
                                  addToast(
                                    "Error: " + (data.error || "Unknown error"),
                                    "error",
                                  );
                                }
                              } catch (err) {
                                addToast(
                                  "Failed to delete data: " + err.message,
                                  "error",
                                );
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

                      {/* Student Writing Profiles */}
                      <div
                        style={{
                          marginTop: "20px",
                          padding: "15px",
                          background: "var(--input-bg)",
                          borderRadius: "10px",
                          border: "1px solid var(--input-border)",
                        }}
                      >
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                            marginBottom: "12px",
                          }}
                        >
                          <div style={{ fontWeight: 600 }}>
                            <Icon
                              name="UserCheck"
                              size={16}
                              style={{
                                marginRight: "8px",
                                verticalAlign: "middle",
                              }}
                            />
                            Student Writing Profiles
                          </div>
                          <button
                            onClick={async () => {
                              setStudentHistoryLoading(true);
                              try {
                                const data = await api.listStudentHistory();
                                setStudentHistoryList(data.students || []);
                              } catch (err) {
                                addToast(
                                  "Failed to load history: " + err.message,
                                  "error",
                                );
                              }
                              setStudentHistoryLoading(false);
                            }}
                            className="btn btn-secondary"
                            style={{ fontSize: "0.8rem", padding: "4px 10px" }}
                          >
                            {studentHistoryLoading ? "Loading..." : "Refresh"}
                          </button>
                        </div>
                        <p
                          style={{
                            fontSize: "0.8rem",
                            color: "var(--text-muted)",
                            marginBottom: "12px",
                          }}
                        >
                          Writing profiles track vocabulary complexity and style
                          patterns for AI detection. View or delete individual
                          profiles.
                        </p>

                        {studentHistoryList.length > 0 ? (
                          <>
                            <div
                              style={{
                                maxHeight: "200px",
                                overflowY: "auto",
                                marginBottom: "10px",
                              }}
                            >
                              {studentHistoryList.map((student) => (
                                <div
                                  key={student.student_id}
                                  style={{
                                    display: "flex",
                                    justifyContent: "space-between",
                                    alignItems: "center",
                                    padding: "8px 12px",
                                    background: "var(--glass-bg)",
                                    borderRadius: "6px",
                                    marginBottom: "6px",
                                    border: "1px solid var(--glass-border)",
                                  }}
                                >
                                  <div>
                                    <div
                                      style={{
                                        fontWeight: 500,
                                        fontSize: "0.85rem",
                                      }}
                                    >
                                      {student.name || student.student_id}
                                    </div>
                                    <div
                                      style={{
                                        fontSize: "0.75rem",
                                        color: "var(--text-muted)",
                                      }}
                                    >
                                      {student.submissions_analyzed} submissions
                                      • Complexity: {student.avg_complexity}
                                    </div>
                                  </div>
                                  <div style={{ display: "flex", gap: "6px" }}>
                                    <button
                                      onClick={async () => {
                                        try {
                                          const data =
                                            await api.getStudentHistory(
                                              student.student_id,
                                            );
                                          setSelectedStudentHistory(data);
                                        } catch (err) {
                                          addToast(
                                            "Failed to load: " + err.message,
                                            "error",
                                          );
                                        }
                                      }}
                                      className="btn btn-secondary"
                                      style={{
                                        padding: "4px 8px",
                                        fontSize: "0.75rem",
                                      }}
                                    >
                                      <Icon name="Eye" size={12} />
                                    </button>
                                    <button
                                      onClick={async () => {
                                        if (
                                          !confirm(
                                            `Delete writing profile for ${student.name || student.student_id}?`,
                                          )
                                        )
                                          return;
                                        try {
                                          await api.deleteStudentHistory(
                                            student.student_id,
                                          );
                                          setStudentHistoryList((prev) =>
                                            prev.filter(
                                              (s) =>
                                                s.student_id !==
                                                student.student_id,
                                            ),
                                          );
                                          addToast("Profile deleted", "success");
                                        } catch (err) {
                                          addToast(
                                            "Failed to delete: " + err.message,
                                            "error",
                                          );
                                        }
                                      }}
                                      className="btn btn-secondary"
                                      style={{
                                        padding: "4px 8px",
                                        fontSize: "0.75rem",
                                        color: "#ef4444",
                                      }}
                                    >
                                      <Icon name="Trash2" size={12} />
                                    </button>
                                  </div>
                                </div>
                              ))}
                            </div>
                            <button
                              onClick={async () => {
                                if (
                                  !confirm(
                                    "Delete ALL student writing profiles? This resets AI detection baselines.",
                                  )
                                )
                                  return;
                                try {
                                  const result =
                                    await api.deleteAllStudentHistory();
                                  setStudentHistoryList([]);
                                  addToast(
                                    `Deleted ${result.deleted} profiles`,
                                    "success",
                                  );
                                } catch (err) {
                                  addToast(
                                    "Failed to delete: " + err.message,
                                    "error",
                                  );
                                }
                              }}
                              className="btn btn-danger"
                              style={{ fontSize: "0.8rem" }}
                            >
                              <Icon name="Trash2" size={14} />
                              Delete All Profiles
                            </button>
                          </>
                        ) : (
                          <div
                            style={{
                              padding: "20px",
                              textAlign: "center",
                              color: "var(--text-muted)",
                              fontSize: "0.85rem",
                            }}
                          >
                            {studentHistoryLoading
                              ? "Loading..."
                              : 'Click "Refresh" to load student writing profiles'}
                          </div>
                        )}
                      </div>

                      {/* Student History Detail Modal */}
                      {selectedStudentHistory && (
                        <div
                          style={{
                            position: "fixed",
                            top: 0,
                            left: 0,
                            right: 0,
                            bottom: 0,
                            background: "rgba(0,0,0,0.7)",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            zIndex: 1000,
                          }}
                          onClick={() => setSelectedStudentHistory(null)}
                        >
                          <div
                            style={{
                              background: "var(--card-bg)",
                              borderRadius: "12px",
                              padding: "25px",
                              maxWidth: "600px",
                              maxHeight: "80vh",
                              overflow: "auto",
                              width: "90%",
                            }}
                            onClick={(e) => e.stopPropagation()}
                          >
                            <div
                              style={{
                                display: "flex",
                                justifyContent: "space-between",
                                alignItems: "center",
                                marginBottom: "20px",
                              }}
                            >
                              <h3 style={{ margin: 0 }}>
                                <Icon
                                  name="User"
                                  size={20}
                                  style={{ marginRight: "10px" }}
                                />
                                {selectedStudentHistory.name ||
                                  selectedStudentHistory.student_id ||
                                  "Student Profile"}
                              </h3>
                              <button
                                onClick={() => setSelectedStudentHistory(null)}
                                className="btn btn-secondary"
                                style={{ padding: "4px 8px" }}
                              >
                                <Icon name="X" size={16} />
                              </button>
                            </div>

                            <div
                              style={{
                                background: "var(--input-bg)",
                                borderRadius: "8px",
                                padding: "15px",
                                fontSize: "0.85rem",
                              }}
                            >
                              <pre
                                style={{
                                  margin: 0,
                                  whiteSpace: "pre-wrap",
                                  wordBreak: "break-word",
                                  fontFamily: "monospace",
                                  fontSize: "0.8rem",
                                }}
                              >
                                {JSON.stringify(
                                  selectedStudentHistory,
                                  null,
                                  2,
                                )}
                              </pre>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                      </>
                    )}
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
                      Upload curriculum guides, rubrics, standards docs, or
                      other reference materials
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
                            addToast(result.error, "error");
                          } else {
                            const docsData = await api.listSupportDocuments();
                            setSupportDocs(docsData.documents || []);
                            setNewDocDescription("");
                          }
                        } catch (err) {
                          addToast("Upload failed: " + err.message, "error");
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
                            rosterMappingModal.roster?.column_mapping?.[
                              field
                            ] || ""
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
                      style={{
                        display: "flex",
                        gap: "10px",
                        marginTop: "20px",
                      }}
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
                            setRosterMappingModal({
                              show: false,
                              roster: null,
                            });
                          } catch (err) {
                            addToast(
                              "Error saving mapping: " + err.message,
                              "error",
                            );
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

              {/* Accommodation Assignment Modal */}
              {accommodationModal.show && (
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
                      <h3
                        style={{
                          fontSize: "1.2rem",
                          fontWeight: 700,
                          display: "flex",
                          alignItems: "center",
                          gap: "10px",
                        }}
                      >
                        <Icon
                          name="Heart"
                          size={22}
                          style={{ color: "#f472b6" }}
                        />
                        {accommodationModal.studentId
                          ? "Edit Accommodations"
                          : "Add Student Accommodations"}
                      </h3>
                      <button
                        onClick={() => {
                          setAccommodationModal({
                            show: false,
                            studentId: null,
                          });
                          setSelectedAccommodationPresets([]);
                          setAccommodationCustomNotes("");
                        }}
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
                        fontSize: "0.85rem",
                        color: "var(--text-secondary)",
                        marginBottom: "20px",
                        padding: "10px",
                        background: "rgba(74, 222, 128, 0.1)",
                        borderRadius: "8px",
                        border: "1px solid rgba(74, 222, 128, 0.2)",
                      }}
                    >
                      <Icon
                        name="Shield"
                        size={14}
                        style={{ color: "#4ade80", marginRight: "6px" }}
                      />
                      FERPA Compliant: Only accommodation types are sent to AI,
                      never student names or IDs.
                    </p>

                    {/* Student ID Input (for new students) */}
                    {!accommodationModal.studentId && (
                      <div style={{ marginBottom: "20px" }}>
                        <label className="label">Student ID</label>
                        <input
                          type="text"
                          className="input"
                          placeholder="Enter student ID from roster..."
                          id="accommodation-student-id"
                        />
                      </div>
                    )}

                    {/* Preset Selection */}
                    <div style={{ marginBottom: "20px" }}>
                      <label className="label">
                        Select Accommodation Presets
                      </label>
                      <div
                        style={{
                          display: "flex",
                          flexDirection: "column",
                          gap: "8px",
                          maxHeight: "200px",
                          overflowY: "auto",
                        }}
                      >
                        {accommodationPresets.map((preset) => (
                          <label
                            key={preset.id}
                            style={{
                              display: "flex",
                              alignItems: "flex-start",
                              gap: "10px",
                              padding: "10px",
                              background: selectedAccommodationPresets.includes(
                                preset.id,
                              )
                                ? "rgba(244, 114, 182, 0.15)"
                                : "var(--input-bg)",
                              borderRadius: "8px",
                              border: selectedAccommodationPresets.includes(
                                preset.id,
                              )
                                ? "1px solid rgba(244, 114, 182, 0.4)"
                                : "1px solid var(--input-border)",
                              cursor: "pointer",
                            }}
                          >
                            <input
                              type="checkbox"
                              checked={selectedAccommodationPresets.includes(
                                preset.id,
                              )}
                              onChange={(e) => {
                                if (e.target.checked) {
                                  setSelectedAccommodationPresets([
                                    ...selectedAccommodationPresets,
                                    preset.id,
                                  ]);
                                } else {
                                  setSelectedAccommodationPresets(
                                    selectedAccommodationPresets.filter(
                                      (id) => id !== preset.id,
                                    ),
                                  );
                                }
                              }}
                              style={{ marginTop: "2px" }}
                            />
                            <div>
                              <div
                                style={{
                                  fontWeight: 600,
                                  fontSize: "0.85rem",
                                  display: "flex",
                                  alignItems: "center",
                                  gap: "6px",
                                }}
                              >
                                <Icon
                                  name={preset.icon || "FileText"}
                                  size={14}
                                  style={{ color: "#f472b6" }}
                                />
                                {preset.name}
                              </div>
                              <div
                                style={{
                                  fontSize: "0.75rem",
                                  color: "var(--text-muted)",
                                  marginTop: "2px",
                                }}
                              >
                                {preset.description}
                              </div>
                            </div>
                          </label>
                        ))}
                      </div>
                    </div>

                    {/* Custom Notes */}
                    <div style={{ marginBottom: "20px" }}>
                      <label className="label">
                        Additional Notes (Optional)
                      </label>
                      <textarea
                        className="input"
                        value={accommodationCustomNotes}
                        onChange={(e) =>
                          setAccommodationCustomNotes(e.target.value)
                        }
                        placeholder="Any additional accommodation instructions..."
                        style={{ minHeight: "80px", resize: "vertical" }}
                      />
                      <p
                        style={{
                          fontSize: "0.75rem",
                          color: "var(--text-muted)",
                          marginTop: "6px",
                        }}
                      >
                        These notes will be included in AI grading instructions
                        (without student identity).
                      </p>
                    </div>

                    {/* Actions */}
                    <div
                      style={{
                        display: "flex",
                        gap: "10px",
                        justifyContent: "flex-end",
                      }}
                    >
                      <button
                        onClick={async () => {
                          const studentId =
                            accommodationModal.studentId ||
                            document.getElementById("accommodation-student-id")
                              ?.value;

                          if (!studentId) {
                            addToast("Please enter a student ID", "warning");
                            return;
                          }

                          if (
                            selectedAccommodationPresets.length === 0 &&
                            !accommodationCustomNotes
                          ) {
                            addToast(
                              "Please select at least one preset or add custom notes",
                              "warning",
                            );
                            return;
                          }

                          try {
                            await api.setStudentAccommodation(
                              studentId,
                              selectedAccommodationPresets,
                              accommodationCustomNotes,
                            );

                            // Reload accommodations
                            const data = await api.getStudentAccommodations();
                            if (data.accommodations)
                              setStudentAccommodations(data.accommodations);

                            setAccommodationModal({
                              show: false,
                              studentId: null,
                            });
                            setSelectedAccommodationPresets([]);
                            setAccommodationCustomNotes("");
                          } catch (err) {
                            addToast(
                              "Error saving accommodation: " + err.message,
                              "error",
                            );
                          }
                        }}
                        className="btn btn-primary"
                      >
                        <Icon name="Save" size={18} />
                        Save Accommodations
                      </button>
                      <button
                        onClick={() => {
                          setAccommodationModal({
                            show: false,
                            studentId: null,
                          });
                          setSelectedAccommodationPresets([]);
                          setAccommodationCustomNotes("");
                        }}
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
                  {/* Saved Assignments - Collapsible */}
                  <div
                    className="glass-card"
                    style={{ padding: "15px 20px", marginBottom: "20px" }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        cursor: "pointer",
                      }}
                      onClick={() =>
                        setSavedAssignmentsExpanded(!savedAssignmentsExpanded)
                      }
                    >
                      <h3
                        style={{
                          fontSize: "1rem",
                          fontWeight: 600,
                          display: "flex",
                          alignItems: "center",
                          gap: "10px",
                          margin: 0,
                        }}
                      >
                        <Icon
                          name={
                            savedAssignmentsExpanded
                              ? "ChevronDown"
                              : "ChevronRight"
                          }
                          size={18}
                          style={{ color: "var(--text-secondary)" }}
                        />
                        <Icon
                          name="FolderOpen"
                          size={18}
                          style={{ color: "#10b981" }}
                        />
                        Saved Assignments ({savedAssignments.length})
                      </h3>
                    </div>

                    {savedAssignmentsExpanded && (
                      <>
                        {savedAssignments.length === 0 ? (
                          <p
                            style={{
                              textAlign: "center",
                              padding: "20px",
                              color: "var(--text-muted)",
                              margin: 0,
                            }}
                          >
                            No saved assignments yet. Create one below!
                          </p>
                        ) : (
                          <div
                            style={{
                              display: "grid",
                              gridTemplateColumns:
                                "repeat(auto-fill, minmax(250px, 1fr))",
                              gap: "10px",
                              marginTop: "15px",
                            }}
                          >
                            {savedAssignments.map((name) => {
                              const countsTowardsGrade = savedAssignmentData[name]?.countsTowardsGrade ?? true;
                              return (
                              <div
                                key={name}
                                style={{
                                  padding: "12px 15px",
                                  background:
                                    loadedAssignmentName === name
                                      ? "rgba(99,102,241,0.2)"
                                      : !countsTowardsGrade
                                        ? "rgba(100,100,100,0.1)"
                                        : "var(--input-bg)",
                                  borderRadius: "10px",
                                  border:
                                    loadedAssignmentName === name
                                      ? "2px solid rgba(99,102,241,0.5)"
                                      : !countsTowardsGrade
                                        ? "1px dashed rgba(100,100,100,0.4)"
                                        : "1px solid var(--glass-border)",
                                  cursor: "pointer",
                                  display: "flex",
                                  justifyContent: "space-between",
                                  alignItems: "center",
                                  opacity: countsTowardsGrade ? 1 : 0.6,
                                }}
                                onClick={() => loadAssignment(name)}
                                onDoubleClick={async () => {
                                  setIsLoadingAssignment(true); // Prevent auto-save during load
                                  const data = await api.loadAssignment(name);
                                  if (data.assignment) {
                                    // Set importedDoc FIRST to prevent race condition
                                    if (data.assignment.importedDoc?.html || data.assignment.importedDoc?.text) {
                                      setImportedDoc(data.assignment.importedDoc);
                                    } else {
                                      setImportedDoc({ text: "", html: "", filename: "", loading: false });
                                    }

                                    // Load the assignment
                                    setAssignment({
                                      title: data.assignment.title || "",
                                      subject: data.assignment.subject || "Social Studies",
                                      totalPoints: data.assignment.totalPoints || 100,
                                      instructions: data.assignment.instructions || "",
                                      questions: data.assignment.questions || [],
                                      customMarkers: data.assignment.customMarkers || [],
                                      gradingNotes: data.assignment.gradingNotes || "",
                                      responseSections: data.assignment.responseSections || [],
                                      aliases: data.assignment.aliases || [],
                                    });
                                    setLoadedAssignmentName(name);
                                    setTimeout(() => setIsLoadingAssignment(false), 500);

                                    // If there's an imported doc, open the editor modal
                                    if (data.assignment.importedDoc?.html || data.assignment.importedDoc?.text) {
                                      setDocEditorModal({
                                        show: true,
                                        editedHtml: data.assignment.importedDoc.html || '',
                                        viewMode: 'formatted'
                                      });
                                      const markerCount = (data.assignment.questions?.length || 0) + (data.assignment.customMarkers?.length || 0);
                                      addToast(
                                        `Loaded "${name}" with ${markerCount} marker${markerCount !== 1 ? 's' : ''}`,
                                        'success'
                                      );
                                    } else {
                                      // No document - check if it has markers
                                      const markerCount = (data.assignment.questions?.length || 0) + (data.assignment.customMarkers?.length || 0);
                                      if (markerCount > 0) {
                                        addToast(`"${name}" has ${markerCount} marker${markerCount !== 1 ? 's' : ''} but no document. Re-import the document to view.`, 'warning');
                                      } else {
                                        addToast(`"${name}" has no document or markers. Import a document to get started.`, 'info');
                                      }
                                    }
                                  } else {
                                    setIsLoadingAssignment(false);
                                  }
                                }}
                                title="Double-click to open document with markers"
                              >
                                <div
                                  style={{
                                    fontWeight: 500,
                                    display: "flex",
                                    alignItems: "center",
                                    gap: "8px",
                                    fontSize: "0.9rem",
                                    flex: 1,
                                  }}
                                >
                                  <Icon
                                    name={
                                      savedAssignmentData[name]?.completionOnly
                                        ? "CheckCircle"
                                        : "FileText"
                                    }
                                    size={14}
                                    style={{
                                      color: savedAssignmentData[name]
                                        ?.completionOnly
                                        ? "#22c55e"
                                        : "#a5b4fc",
                                    }}
                                  />
                                  {name}
                                  {savedAssignmentData[name]?.completionOnly && (
                                    <span
                                      style={{
                                        fontSize: "0.7rem",
                                        background: "rgba(34, 197, 94, 0.2)",
                                        color: "#22c55e",
                                        padding: "2px 6px",
                                        borderRadius: "4px",
                                        marginLeft: "4px",
                                      }}
                                    >
                                      Completion
                                    </span>
                                  )}
                                  {savedAssignmentData[name]?.rubricType && savedAssignmentData[name]?.rubricType !== 'standard' && !savedAssignmentData[name]?.completionOnly && (
                                    <span
                                      style={{
                                        fontSize: "0.65rem",
                                        background: savedAssignmentData[name]?.rubricType === 'fill-in-blank' ? "rgba(251, 191, 36, 0.2)" :
                                                   savedAssignmentData[name]?.rubricType === 'essay' ? "rgba(99, 102, 241, 0.2)" :
                                                   savedAssignmentData[name]?.rubricType === 'cornell-notes' ? "rgba(34, 211, 238, 0.2)" :
                                                   savedAssignmentData[name]?.rubricType === 'custom' ? "rgba(139, 92, 246, 0.2)" : "rgba(100,100,100,0.2)",
                                        color: savedAssignmentData[name]?.rubricType === 'fill-in-blank' ? "#fbbf24" :
                                               savedAssignmentData[name]?.rubricType === 'essay' ? "#818cf8" :
                                               savedAssignmentData[name]?.rubricType === 'cornell-notes' ? "#22d3ee" :
                                               savedAssignmentData[name]?.rubricType === 'custom' ? "#a78bfa" : "#888",
                                        padding: "2px 6px",
                                        borderRadius: "4px",
                                        marginLeft: "4px",
                                        textTransform: "uppercase",
                                        fontWeight: 600,
                                      }}
                                    >
                                      {savedAssignmentData[name]?.rubricType === 'fill-in-blank' ? 'Fill-in' :
                                       savedAssignmentData[name]?.rubricType === 'cornell-notes' ? 'Cornell' :
                                       savedAssignmentData[name]?.rubricType}
                                    </span>
                                  )}
                                </div>
                                <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                                  {/* Star toggle for "counts towards grade" */}
                                  <button
                                    onClick={async (e) => {
                                      e.stopPropagation();
                                      const currentValue = savedAssignmentData[name]?.countsTowardsGrade ?? true;
                                      const newValue = !currentValue;
                                      setSavedAssignmentData(prev => ({
                                        ...prev,
                                        [name]: { ...prev[name], countsTowardsGrade: newValue },
                                      }));
                                      try {
                                        const fullData = await api.loadAssignment(name);
                                        if (fullData.assignment) {
                                          await api.saveAssignmentConfig({
                                            ...fullData.assignment,
                                            countsTowardsGrade: newValue,
                                          });
                                        }
                                        addToast(
                                          newValue
                                            ? `"${name}" will count towards grade`
                                            : `"${name}" excluded from grade calculation`,
                                          "success"
                                        );
                                      } catch (err) {
                                        console.error("Error saving:", err);
                                      }
                                    }}
                                    style={{
                                      padding: "4px",
                                      background: "none",
                                      border: "none",
                                      cursor: "pointer",
                                      color: (savedAssignmentData[name]?.countsTowardsGrade ?? true) ? "#fbbf24" : "var(--text-muted)",
                                    }}
                                    title={(savedAssignmentData[name]?.countsTowardsGrade ?? true) ? "Counts towards grade (click to exclude)" : "Excluded from grade (click to include)"}
                                  >
                                    <Icon name={(savedAssignmentData[name]?.countsTowardsGrade ?? true) ? "Star" : "StarOff"} size={14} />
                                  </button>
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
                            );
                            })}
                          </div>
                        )}
                      </>
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
                      <div style={{ gridColumn: "1 / -1" }}>
                        <label className="label" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                          Aliases (Alternative Names)
                          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontWeight: 400 }}>
                            - helps match student files with different naming
                          </span>
                        </label>
                        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", marginBottom: "8px" }}>
                          {(assignment.aliases || []).map((alias, i) => (
                            <span
                              key={i}
                              style={{
                                padding: "4px 10px",
                                background: "rgba(139, 92, 246, 0.2)",
                                border: "1px solid rgba(139, 92, 246, 0.4)",
                                borderRadius: "6px",
                                fontSize: "0.85rem",
                                display: "flex",
                                alignItems: "center",
                                gap: "6px",
                              }}
                            >
                              {alias}
                              <button
                                onClick={() => setAssignment({
                                  ...assignment,
                                  aliases: assignment.aliases.filter((_, idx) => idx !== i)
                                })}
                                style={{
                                  background: "none",
                                  border: "none",
                                  color: "var(--text-muted)",
                                  cursor: "pointer",
                                  padding: "0",
                                  fontSize: "1rem",
                                  lineHeight: 1,
                                }}
                                title="Remove alias"
                              >
                                ×
                              </button>
                            </span>
                          ))}
                        </div>
                        <div style={{ display: "flex", gap: "8px" }}>
                          <input
                            type="text"
                            className="input"
                            placeholder="Add alias (e.g., Chapter 10 Section 2)"
                            style={{ flex: 1 }}
                            onKeyDown={(e) => {
                              if (e.key === "Enter" && e.target.value.trim()) {
                                e.preventDefault();
                                const newAlias = e.target.value.trim();
                                if (!assignment.aliases?.includes(newAlias)) {
                                  setAssignment({
                                    ...assignment,
                                    aliases: [...(assignment.aliases || []), newAlias]
                                  });
                                }
                                e.target.value = "";
                              }
                            }}
                          />
                          <button
                            className="btn btn-secondary"
                            style={{ padding: "8px 16px" }}
                            onClick={(e) => {
                              const input = e.target.previousSibling;
                              if (input.value.trim()) {
                                const newAlias = input.value.trim();
                                if (!assignment.aliases?.includes(newAlias)) {
                                  setAssignment({
                                    ...assignment,
                                    aliases: [...(assignment.aliases || []), newAlias]
                                  });
                                }
                                input.value = "";
                              }
                            }}
                          >
                            Add
                          </button>
                        </div>
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
                          onChange={(e) => {
                            const val = e.target.value;
                            setAssignment({
                              ...assignment,
                              totalPoints: val === '' ? '' : parseInt(val),
                            });
                          }}
                          onBlur={(e) => {
                            const val = parseInt(e.target.value) || 100;
                            setAssignment({
                              ...assignment,
                              totalPoints: val,
                            });
                          }}
                          disabled={assignment.completionOnly}
                          style={
                            assignment.completionOnly ? { opacity: 0.5 } : {}
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
                                onClick={() => {
                                  setImportedDoc({
                                    text: "",
                                    html: "",
                                    filename: "",
                                    loading: false,
                                  });
                                  setAssignment({
                                    ...assignment,
                                    title: "",
                                    customMarkers: [],
                                  });
                                  setLoadedAssignmentName("");
                                }}
                                className="btn btn-secondary"
                                style={{
                                  background: "rgba(239,68,68,0.2)",
                                  color: "#ef4444",
                                }}
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

                      {/* Section Template Selector */}
                      <div style={{ marginTop: "20px", marginBottom: "20px", padding: "15px", background: "rgba(59,130,246,0.1)", borderRadius: "8px", border: "1px solid rgba(59,130,246,0.2)" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "10px" }}>
                          <Icon name="Layout" size={18} style={{ color: "#3b82f6" }} />
                          <span style={{ fontWeight: "600" }}>Section Point Template</span>
                        </div>
                        <select
                          value={assignment.sectionTemplate || "Custom"}
                          onChange={(e) => {
                            const templateName = e.target.value;
                            const template = ASSIGNMENT_TEMPLATES[templateName];
                            if (template && templateName !== "Custom") {
                              setAssignment({
                                ...assignment,
                                sectionTemplate: templateName,
                                customMarkers: template.markers.map(m => ({ ...m })),
                                effortPoints: template.effortPoints || 15,
                              });
                            } else {
                              setAssignment({ ...assignment, sectionTemplate: "Custom" });
                            }
                          }}
                          className="input"
                          style={{ width: "100%", marginBottom: "8px" }}
                        >
                          {Object.keys(ASSIGNMENT_TEMPLATES).map(name => (
                            <option key={name} value={name}>{name}</option>
                          ))}
                        </select>
                        {assignment.sectionTemplate && ASSIGNMENT_TEMPLATES[assignment.sectionTemplate] && (
                          <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                            {ASSIGNMENT_TEMPLATES[assignment.sectionTemplate].description}
                          </div>
                        )}
                        <div style={{ marginTop: "10px", padding: "8px", background: "rgba(0,0,0,0.1)", borderRadius: "4px", fontSize: "13px" }}>
                          <strong>Total Points:</strong> {calculateTotalPoints(assignment.customMarkers, assignment.effortPoints || 15)}
                          {calculateTotalPoints(assignment.customMarkers, assignment.effortPoints || 15) !== 100 && (
                            <span style={{ color: "#ef4444", marginLeft: "10px" }}>
                              (Should equal 100)
                            </span>
                          )}
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

                      {/* Grading Sections with Points */}
                      <div style={{ marginTop: "15px" }}>
                        <div style={{ fontWeight: "600", marginBottom: "8px", display: "flex", alignItems: "center", gap: "8px" }}>
                          <Icon name="Target" size={16} />
                          Grading Sections
                        </div>
                        {(assignment.customMarkers || []).length === 0 ? (
                          <div style={{ color: "var(--text-muted)", fontSize: "13px", padding: "10px", background: "rgba(0,0,0,0.05)", borderRadius: "6px" }}>
                            No sections defined. Select a template above or add sections manually.
                          </div>
                        ) : (
                          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                            {assignment.customMarkers.map((marker, i) => (
                              <div key={i} style={{
                                display: "flex", alignItems: "center", gap: "8px", padding: "10px",
                                background: "rgba(251,191,36,0.15)", borderRadius: "6px", border: "1px solid rgba(251,191,36,0.3)"
                              }}>
                                <Icon name="Target" size={14} style={{ color: "#f59e0b", flexShrink: 0 }} />
                                <input
                                  type="text"
                                  value={getMarkerText(marker)}
                                  onChange={(e) => {
                                    const updated = [...assignment.customMarkers];
                                    if (typeof updated[i] === "string") {
                                      updated[i] = { start: e.target.value, points: 10, type: "written" };
                                    } else {
                                      updated[i] = { ...updated[i], start: e.target.value };
                                    }
                                    setAssignment({ ...assignment, customMarkers: updated, sectionTemplate: "Custom" });
                                  }}
                                  className="input"
                                  style={{ flex: 1, padding: "4px 8px", fontSize: "13px" }}
                                  placeholder="Section name..."
                                />
                                <input
                                  type="number"
                                  value={getMarkerPoints(marker)}
                                  onChange={(e) => {
                                    const updated = [...assignment.customMarkers];
                                    const pts = parseInt(e.target.value) || 0;
                                    if (typeof updated[i] === "string") {
                                      updated[i] = { start: updated[i], points: pts, type: "written" };
                                    } else {
                                      updated[i] = { ...updated[i], points: pts };
                                    }
                                    setAssignment({ ...assignment, customMarkers: updated, sectionTemplate: "Custom" });
                                  }}
                                  style={{ width: "60px", padding: "4px 8px", borderRadius: "4px", border: "1px solid var(--glass-border)", textAlign: "center", fontSize: "13px", background: "var(--input-bg)", color: "var(--text-primary)" }}
                                  min="0"
                                  max="100"
                                />
                                <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>pts</span>
                                <select
                                  value={getMarkerType(marker)}
                                  onChange={(e) => {
                                    const updated = [...assignment.customMarkers];
                                    if (typeof updated[i] === "string") {
                                      updated[i] = { start: updated[i], points: 10, type: e.target.value };
                                    } else {
                                      updated[i] = { ...updated[i], type: e.target.value };
                                    }
                                    setAssignment({ ...assignment, customMarkers: updated, sectionTemplate: "Custom" });
                                  }}
                                  style={{ padding: "4px 8px", borderRadius: "4px", border: "1px solid var(--glass-border)", fontSize: "12px", background: "var(--input-bg)", color: "var(--text-primary)" }}
                                >
                                  <option value="written">Written</option>
                                  <option value="fill-blank">Fill-blank</option>
                                  <option value="vocabulary">Vocabulary</option>
                                  <option value="matching">Matching</option>
                                </select>
                                <button
                                  onClick={() => removeMarker(marker, i)}
                                  style={{ background: "none", border: "none", cursor: "pointer", padding: "4px", color: "#ef4444" }}
                                >
                                  <Icon name="X" size={14} />
                                </button>
                              </div>
                            ))}
                            {/* Effort Points (always present) */}
                            <div style={{
                              display: "flex", alignItems: "center", gap: "8px", padding: "10px",
                              background: "rgba(34,197,94,0.15)", borderRadius: "6px", border: "1px solid rgba(34,197,94,0.3)"
                            }}>
                              <Icon name="Star" size={14} style={{ color: "#22c55e", flexShrink: 0 }} />
                              <span style={{ flex: 1, fontSize: "13px", fontWeight: "500" }}>Effort & Engagement</span>
                              <input
                                type="number"
                                value={assignment.effortPoints || 15}
                                onChange={(e) => setAssignment({ ...assignment, effortPoints: parseInt(e.target.value) || 0, sectionTemplate: "Custom" })}
                                style={{ width: "60px", padding: "4px 8px", borderRadius: "4px", border: "1px solid var(--glass-border)", textAlign: "center", fontSize: "13px", background: "var(--input-bg)", color: "var(--text-primary)" }}
                                min="0"
                                max="30"
                              />
                              <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>pts</span>
                              <div style={{ width: "90px" }}></div> {/* Spacer to align with other rows */}
                            </div>
                          </div>
                        )}
                      </div>
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
                              // Check if marker already exists (handle both string and object formats)
                              const exists = (assignment.customMarkers || []).some(m =>
                                typeof m === 'string' ? m === marker : m.start === marker
                              );
                              if (!exists) {
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
                            {typeof marker === 'string' ? marker : marker.start}
                          </span>
                        ))}
                      </div>
                    </div>

                    {/* Rubric Type Selector */}
                    <div style={{ marginBottom: "25px" }}>
                      <label className="label" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <Icon name="Scale" size={16} style={{ color: "#8b5cf6" }} />
                        Assignment Rubric
                      </label>
                      <select
                        className="input"
                        value={assignment.rubricType || "standard"}
                        onChange={(e) => {
                          const newType = e.target.value;
                          setAssignment({
                            ...assignment,
                            rubricType: newType,
                            // Auto-set grading notes for fill-in-blank if not already set
                            gradingNotes: newType === "fill-in-blank" && !assignment.gradingNotes
                              ? "This is a Fill-in-the-Blank activity. Grade on accuracy and completion only."
                              : assignment.gradingNotes,
                          });
                        }}
                        style={{ marginBottom: "10px" }}
                      >
                        <option value="standard">Standard (Use Global Rubric)</option>
                        <option value="fill-in-blank">Fill-in-the-Blank (Accuracy + Completion)</option>
                        <option value="essay">Essay/Written Response (Writing Quality Focus)</option>
                        <option value="cornell-notes">Cornell Notes (Structure + Summary)</option>
                        <option value="completion-only">Completion Only (No AI Grading)</option>
                        <option value="custom">Custom Rubric...</option>
                      </select>

                      {/* Rubric Preview/Description */}
                      {assignment.rubricType && assignment.rubricType !== "standard" && assignment.rubricType !== "custom" && (
                        <div style={{
                          padding: "12px",
                          background: "rgba(139, 92, 246, 0.1)",
                          borderRadius: "8px",
                          fontSize: "0.85rem",
                          color: "var(--text-secondary)",
                          marginBottom: "10px",
                        }}>
                          {assignment.rubricType === "fill-in-blank" && (
                            <div><strong>Categories:</strong> Accuracy (70%) + Completion (30%)<br/>Spelling errors ignored if intent is clear.</div>
                          )}
                          {assignment.rubricType === "essay" && (
                            <div><strong>Categories:</strong> Content (35%) + Writing Quality (30%) + Analysis (20%) + Effort (15%)</div>
                          )}
                          {assignment.rubricType === "cornell-notes" && (
                            <div><strong>Categories:</strong> Content (40%) + Note Structure (25%) + Summary (20%) + Effort (15%)</div>
                          )}
                          {assignment.rubricType === "completion-only" && (
                            <div><strong>No AI grading.</strong> Just tracks that the assignment was submitted.</div>
                          )}
                        </div>
                      )}

                      {/* Custom Rubric Editor */}
                      {assignment.rubricType === "custom" && (
                        <div style={{
                          padding: "15px",
                          background: "rgba(139, 92, 246, 0.08)",
                          borderRadius: "10px",
                          border: "1px solid rgba(139, 92, 246, 0.2)",
                        }}>
                          <div style={{ fontWeight: 600, marginBottom: "12px", fontSize: "0.9rem" }}>
                            Custom Rubric Categories
                          </div>
                          {(assignment.customRubric || [
                            { name: "Content Accuracy", weight: 40 },
                            { name: "Completeness", weight: 25 },
                            { name: "Writing Quality", weight: 20 },
                            { name: "Effort", weight: 15 },
                          ]).map((cat, i) => (
                            <div key={i} style={{ display: "flex", gap: "10px", marginBottom: "8px", alignItems: "center" }}>
                              <input
                                className="input"
                                value={cat.name}
                                onChange={(e) => {
                                  const newRubric = [...(assignment.customRubric || [
                                    { name: "Content Accuracy", weight: 40 },
                                    { name: "Completeness", weight: 25 },
                                    { name: "Writing Quality", weight: 20 },
                                    { name: "Effort", weight: 15 },
                                  ])];
                                  newRubric[i] = { ...newRubric[i], name: e.target.value };
                                  setAssignment({ ...assignment, customRubric: newRubric });
                                }}
                                placeholder="Category name"
                                style={{ flex: 1 }}
                              />
                              <input
                                className="input"
                                type="number"
                                value={cat.weight}
                                onChange={(e) => {
                                  const newRubric = [...(assignment.customRubric || [
                                    { name: "Content Accuracy", weight: 40 },
                                    { name: "Completeness", weight: 25 },
                                    { name: "Writing Quality", weight: 20 },
                                    { name: "Effort", weight: 15 },
                                  ])];
                                  newRubric[i] = { ...newRubric[i], weight: parseInt(e.target.value) || 0 };
                                  setAssignment({ ...assignment, customRubric: newRubric });
                                }}
                                style={{ width: "70px" }}
                                min="0"
                                max="100"
                              />
                              <span style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>%</span>
                              <button
                                onClick={() => {
                                  const newRubric = (assignment.customRubric || [
                                    { name: "Content Accuracy", weight: 40 },
                                    { name: "Completeness", weight: 25 },
                                    { name: "Writing Quality", weight: 20 },
                                    { name: "Effort", weight: 15 },
                                  ]).filter((_, idx) => idx !== i);
                                  setAssignment({ ...assignment, customRubric: newRubric });
                                }}
                                style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer" }}
                              >
                                <Icon name="X" size={16} />
                              </button>
                            </div>
                          ))}
                          <button
                            onClick={() => {
                              const newRubric = [...(assignment.customRubric || [
                                { name: "Content Accuracy", weight: 40 },
                                { name: "Completeness", weight: 25 },
                                { name: "Writing Quality", weight: 20 },
                                { name: "Effort", weight: 15 },
                              ]), { name: "", weight: 0 }];
                              setAssignment({ ...assignment, customRubric: newRubric });
                            }}
                            className="btn btn-secondary"
                            style={{ marginTop: "8px", fontSize: "0.85rem" }}
                          >
                            <Icon name="Plus" size={14} /> Add Category
                          </button>
                          <div style={{ marginTop: "10px", fontSize: "0.8rem", color: "var(--text-muted)" }}>
                            Total: {(assignment.customRubric || [
                              { name: "Content Accuracy", weight: 40 },
                              { name: "Completeness", weight: 25 },
                              { name: "Writing Quality", weight: 20 },
                              { name: "Effort", weight: 15 },
                            ]).reduce((sum, c) => sum + (c.weight || 0), 0)}%
                            {(assignment.customRubric || []).reduce((sum, c) => sum + (c.weight || 0), 0) !== 100 && (
                              <span style={{ color: "#f59e0b" }}> (should be 100%)</span>
                            )}
                          </div>
                        </div>
                      )}
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
                        <button
                          onClick={addQuestion}
                          className="btn btn-primary"
                        >
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
                                      updateQuestion(
                                        i,
                                        "marker",
                                        e.target.value,
                                      )
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
                      style={{
                        display: "flex",
                        gap: "15px",
                        flexWrap: "wrap",
                        alignItems: "center",
                      }}
                    >
                      {assignment.title && (
                        <span
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "6px",
                            color: "#4ade80",
                            fontSize: "0.85rem",
                            padding: "8px 12px",
                            background: "rgba(74,222,128,0.1)",
                            border: "1px solid rgba(74,222,128,0.3)",
                            borderRadius: "8px",
                          }}
                        >
                          <Icon
                            name="Check"
                            size={14}
                            style={{ color: "#4ade80" }}
                          />
                          Auto-saves
                        </span>
                      )}
                      <button
                        onClick={saveAssignmentConfig}
                        disabled={!assignment.title}
                        className="btn btn-secondary"
                        style={{ opacity: !assignment.title ? 0.5 : 1 }}
                      >
                        <Icon name="Save" size={18} /> Save Now
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
                  {!filteredAnalytics || filteredAnalytics.error ? (
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
                            gap: "15px",
                          }}
                        >
                          {/* Period Filter */}
                          {sortedPeriods.length > 0 && (
                            <div
                              style={{
                                display: "flex",
                                alignItems: "center",
                                gap: "8px",
                              }}
                            >
                              <label
                                style={{
                                  fontSize: "0.9rem",
                                  color: "var(--text-secondary)",
                                }}
                              >
                                Period:
                              </label>
                              <select
                                value={analyticsClassPeriod}
                                onChange={(e) =>
                                  setAnalyticsClassPeriod(e.target.value)
                                }
                                className="input"
                                style={{ width: "auto" }}
                              >
                                <option value="">All Periods</option>
                                {sortedPeriods.map((p) => (
                                  <option key={p.filename} value={p.filename}>
                                    {p.period_name}
                                  </option>
                                ))}
                              </select>
                            </div>
                          )}
                          {/* Quarter Filter */}
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "8px",
                            }}
                          >
                            <label
                              style={{
                                fontSize: "0.9rem",
                                color: "var(--text-secondary)",
                              }}
                            >
                              Quarter:
                            </label>
                            <select
                              value={analyticsPeriod}
                              onChange={(e) =>
                                setAnalyticsPeriod(e.target.value)
                              }
                              className="input"
                              style={{ width: "auto" }}
                            >
                              <option value="all">All Quarters</option>
                              {(filteredAnalytics.available_periods || []).map(
                                (p) => (
                                  <option key={p} value={p}>
                                    {p}
                                  </option>
                                ),
                              )}
                            </select>
                          </div>
                          {/* Export District Report Button */}
                          <button
                            className="btn btn-secondary"
                            onClick={async () => {
                              try {
                                const report = await api.exportDistrictReport();
                                if (report.error) {
                                  addToast(report.error, "error");
                                  return;
                                }
                                const blob = new Blob(
                                  [JSON.stringify(report, null, 2)],
                                  { type: "application/json" },
                                );
                                const url = URL.createObjectURL(blob);
                                const a = document.createElement("a");
                                a.href = url;
                                a.download = `district_report_${new Date().toISOString().split("T")[0]}.json`;
                                a.click();
                                URL.revokeObjectURL(url);
                              } catch (err) {
                                addToast(
                                  "Failed to export report: " + err.message,
                                  "error",
                                );
                              }
                            }}
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "6px",
                            }}
                          >
                            <Icon name="Download" size={16} />
                            Export District Report
                          </button>
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
                            value:
                              filteredAnalytics.class_stats
                                ?.total_assignments || 0,
                            icon: "FileCheck",
                            color: "#6366f1",
                          },
                          {
                            label: "Students",
                            value:
                              filteredAnalytics.class_stats?.total_students ||
                              0,
                            icon: "Users",
                            color: "#8b5cf6",
                          },
                          {
                            label: "Class Average",
                            value: `${filteredAnalytics.class_stats?.class_average || 0}%`,
                            icon: "TrendingUp",
                            color: "#10b981",
                          },
                          {
                            label: "Highest Score",
                            value: `${filteredAnalytics.class_stats?.highest || 0}%`,
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
                                      filteredAnalytics.class_stats
                                        ?.grade_distribution?.A || 0,
                                  },
                                  {
                                    name: "B",
                                    value:
                                      filteredAnalytics.class_stats
                                        ?.grade_distribution?.B || 0,
                                  },
                                  {
                                    name: "C",
                                    value:
                                      filteredAnalytics.class_stats
                                        ?.grade_distribution?.C || 0,
                                  },
                                  {
                                    name: "D",
                                    value:
                                      filteredAnalytics.class_stats
                                        ?.grade_distribution?.D || 0,
                                  },
                                  {
                                    name: "F",
                                    value:
                                      filteredAnalytics.class_stats
                                        ?.grade_distribution?.F || 0,
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
                            <BarChart
                              data={filteredAnalytics.assignment_stats || []}
                            >
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

                      {/* Proficiency vs Growth Scatterplot */}
                      <div
                        className="glass-card"
                        style={{ padding: "25px", marginBottom: "20px" }}
                      >
                        <h3
                          style={{
                            fontSize: "1.1rem",
                            fontWeight: 700,
                            marginBottom: "10px",
                            display: "flex",
                            alignItems: "center",
                            gap: "10px",
                          }}
                        >
                          <Icon name="Target" size={20} />
                          Student Proficiency vs Growth
                        </h3>
                        <p
                          style={{
                            fontSize: "0.85rem",
                            color: "var(--text-secondary)",
                            marginBottom: "15px",
                          }}
                        >
                          Click any dot to view that student's detailed
                          progress. Quadrants show performance patterns.
                        </p>
                        <ResponsiveContainer width="100%" height={350}>
                          <ScatterChart
                            margin={{
                              top: 20,
                              right: 30,
                              bottom: 60,
                              left: 50,
                            }}
                          >
                            <CartesianGrid
                              strokeDasharray="3 3"
                              stroke="var(--glass-border)"
                            />
                            <XAxis
                              type="number"
                              dataKey="proficiency"
                              name="Proficiency"
                              domain={[0, 100]}
                              tick={{
                                fill: "var(--text-secondary)",
                                fontSize: 11,
                              }}
                              label={{
                                value: "Average Score (%)",
                                position: "insideBottom",
                                offset: -5,
                                fill: "var(--text-secondary)",
                                fontSize: 12,
                              }}
                            />
                            <YAxis
                              type="number"
                              dataKey="growth"
                              name="Growth"
                              domain={[-30, 100]}
                              tick={{
                                fill: "var(--text-secondary)",
                                fontSize: 11,
                              }}
                              label={{
                                value: "Growth (pts)",
                                angle: -90,
                                position: "insideLeft",
                                fill: "var(--text-secondary)",
                                fontSize: 12,
                              }}
                            />
                            <ZAxis
                              type="number"
                              dataKey="assignments"
                              range={[60, 200]}
                              name="Assignments"
                            />
                            <ReferenceLine
                              x={70}
                              stroke="#f59e0b"
                              strokeDasharray="5 5"
                            />
                            <ReferenceLine
                              y={0}
                              stroke="#6366f1"
                              strokeDasharray="5 5"
                            />
                            <Tooltip
                              cursor={{ strokeDasharray: "3 3" }}
                              contentStyle={{
                                background: "var(--modal-content-bg)",
                                border: "1px solid var(--glass-border)",
                                borderRadius: "8px",
                                color: "var(--text-primary)",
                              }}
                              labelStyle={{ color: "var(--text-primary)" }}
                              itemStyle={{ color: "var(--text-secondary)" }}
                              formatter={(value, name) => {
                                if (name === "Growth")
                                  return [
                                    value > 0 ? `+${value}` : value,
                                    "Growth (pts)",
                                  ];
                                if (name === "Proficiency")
                                  return [`${value}%`, "Avg Score"];
                                if (name === "Assignments")
                                  return [value, "# Graded"];
                                return [value, name];
                              }}
                              labelFormatter={(_, payload) =>
                                payload[0]?.payload?.name || ""
                              }
                            />
                            <Legend
                              verticalAlign="bottom"
                              align="center"
                              wrapperStyle={{
                                paddingTop: "20px",
                                fontSize: "11px",
                              }}
                              payload={[
                                {
                                  value: "Star Performer",
                                  type: "circle",
                                  color: "#10b981",
                                },
                                {
                                  value: "Improving",
                                  type: "circle",
                                  color: "#f59e0b",
                                },
                                {
                                  value: "Stable",
                                  type: "circle",
                                  color: "#6366f1",
                                },
                                {
                                  value: "Needs Support",
                                  type: "circle",
                                  color: "#ef4444",
                                },
                              ]}
                            />
                            <Scatter
                              name="Students"
                              data={(
                                filteredAnalytics.student_progress || []
                              ).map((s) => {
                                const grades = s.grades || [];
                                let growth = 0;
                                if (grades.length >= 2) {
                                  const firstHalf = grades.slice(
                                    0,
                                    Math.ceil(grades.length / 2),
                                  );
                                  const secondHalf = grades.slice(
                                    Math.ceil(grades.length / 2),
                                  );
                                  const firstAvg =
                                    firstHalf.reduce(
                                      (sum, g) => sum + g.score,
                                      0,
                                    ) / firstHalf.length;
                                  const secondAvg =
                                    secondHalf.reduce(
                                      (sum, g) => sum + g.score,
                                      0,
                                    ) / secondHalf.length;
                                  growth = Math.round(secondAvg - firstAvg);
                                }
                                return {
                                  name: s.name,
                                  proficiency: s.average,
                                  growth: growth,
                                  assignments: grades.length,
                                  trend: s.trend,
                                };
                              })}
                              onClick={(data) => {
                                if (data && data.name)
                                  setSelectedStudent(data.name);
                              }}
                              style={{ cursor: "pointer" }}
                            >
                              {(filteredAnalytics.student_progress || []).map(
                                (s, index) => {
                                  const isLow = s.average < 70;
                                  const grades = s.grades || [];
                                  let growth = 0;
                                  if (grades.length >= 2) {
                                    const firstHalf = grades.slice(
                                      0,
                                      Math.ceil(grades.length / 2),
                                    );
                                    const secondHalf = grades.slice(
                                      Math.ceil(grades.length / 2),
                                    );
                                    const firstAvg =
                                      firstHalf.reduce(
                                        (sum, g) => sum + g.score,
                                        0,
                                      ) / firstHalf.length;
                                    const secondAvg =
                                      secondHalf.reduce(
                                        (sum, g) => sum + g.score,
                                        0,
                                      ) / secondHalf.length;
                                    growth = secondAvg - firstAvg;
                                  }
                                  let color = "#6366f1"; // Default purple
                                  if (isLow && growth <= 0)
                                    color = "#ef4444"; // Red - struggling
                                  else if (isLow && growth > 0)
                                    color = "#f59e0b"; // Orange - improving
                                  else if (!isLow && growth < -5)
                                    color = "#f97316"; // Dark orange - declining
                                  else if (!isLow && growth >= 5)
                                    color = "#10b981"; // Green - star
                                  return <Cell key={index} fill={color} />;
                                },
                              )}
                            </Scatter>
                          </ScatterChart>
                        </ResponsiveContainer>
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
                              filteredAnalytics.student_progress || []
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

                        {(() => {
                          const filtered = selectedStudent
                            ? (filteredAnalytics.student_progress || []).filter(
                                (s) => s.name === selectedStudent,
                              )
                            : filteredAnalytics.student_progress || [];
                          const allGrades = filtered.flatMap((s) =>
                            (s.grades || []).map((g) => ({
                              ...g,
                              student: s.name.split(" ")[0],
                            })),
                          );
                          const chartData = allGrades.sort((a, b) =>
                            (a.date || "").localeCompare(b.date || ""),
                          );
                          const chartWidth = Math.max(
                            800,
                            chartData.length * 80,
                          );

                          return (
                            <div
                              style={{ overflowX: "auto", overflowY: "hidden" }}
                            >
                              <div style={{ width: chartWidth, height: 300 }}>
                                <ResponsiveContainer width="100%" height="100%">
                                  <LineChart
                                    data={chartData}
                                    margin={{
                                      top: 15,
                                      bottom: 80,
                                      left: 10,
                                      right: 30,
                                    }}
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
                                      angle={-45}
                                      textAnchor="end"
                                      height={100}
                                      interval={0}
                                      tickFormatter={(value) =>
                                        value && value.length > 25
                                          ? value.substring(0, 25) + "..."
                                          : value
                                      }
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
                                      formatter={(value) => [
                                        value + "%",
                                        "Score",
                                      ]}
                                      labelFormatter={(label) => label}
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
                            </div>
                          );
                        })()}
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
                          {(filteredAnalytics.attention_needed || []).length ===
                          0 ? (
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
                              {(filteredAnalytics.attention_needed || [])
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
                            {(filteredAnalytics.top_performers || []).map(
                              (s, i) => (
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
                                      style={{
                                        textDecoration: "underline dotted",
                                      }}
                                    >
                                      {s.name}
                                    </span>
                                  </div>
                                  <span
                                    style={{
                                      color: "#4ade80",
                                      fontWeight: 700,
                                    }}
                                  >
                                    {s.average}%
                                  </span>
                                </div>
                              ),
                            )}
                          </div>
                        </div>
                      </div>

                      {/* Missing Assignments Section */}
                      <div className="glass-card" style={{ padding: "25px" }}>
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
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
                              margin: 0,
                            }}
                          >
                            <Icon name="UserX" size={20} />
                            Missing Assignments
                          </h3>
                          <button
                            className="btn btn-secondary"
                            onClick={() => {
                              if (!config.assignments_folder) {
                                addToast(
                                  "Set assignments folder in Settings first",
                                  "error",
                                );
                                return;
                              }
                              setMissingFilesLoading(true);
                              api
                                .listFiles(config.assignments_folder)
                                .then((data) =>
                                  setMissingUploadedFiles(data.files || []),
                                )
                                .catch(() => setMissingUploadedFiles([]))
                                .finally(() => setMissingFilesLoading(false));
                            }}
                            style={{ padding: "6px 12px", fontSize: "0.85rem" }}
                          >
                            <Icon name="RefreshCw" size={14} />
                            Refresh
                          </button>
                        </div>

                        {/* Filters */}
                        <div
                          style={{
                            display: "flex",
                            gap: "15px",
                            flexWrap: "wrap",
                            marginBottom: "20px",
                          }}
                        >
                          <div style={{ flex: "1", minWidth: "180px" }}>
                            <label
                              style={{
                                fontSize: "0.8rem",
                                color: "#888",
                                marginBottom: "4px",
                                display: "block",
                              }}
                            >
                              Period
                            </label>
                            <select
                              className="input"
                              value={missingPeriodFilter}
                              onChange={(e) => {
                                setMissingPeriodFilter(e.target.value);
                                setMissingStudentFilter("");
                              }}
                              style={{ width: "100%" }}
                            >
                              <option value="">All Periods</option>
                              {sortedPeriods.map((p) => (
                                <option key={p.filename} value={p.filename}>
                                  {p.period_name}
                                </option>
                              ))}
                            </select>
                          </div>
                          <div style={{ flex: "1", minWidth: "180px" }}>
                            <label
                              style={{
                                fontSize: "0.8rem",
                                color: "#888",
                                marginBottom: "4px",
                                display: "block",
                              }}
                            >
                              Student
                            </label>
                            <div style={{ position: "relative" }}>
                              <input
                                type="text"
                                className="input"
                                list="missing-student-suggestions"
                                placeholder="Type or select student..."
                                value={missingStudentFilter}
                                onChange={(e) =>
                                  setMissingStudentFilter(e.target.value)
                                }
                                onClick={(e) => {
                                  if (missingStudentFilter) {
                                    e.target.dataset.prev =
                                      missingStudentFilter;
                                    setMissingStudentFilter("");
                                  }
                                }}
                                onBlur={(e) => {
                                  if (
                                    !missingStudentFilter &&
                                    e.target.dataset.prev
                                  ) {
                                    setMissingStudentFilter(
                                      e.target.dataset.prev,
                                    );
                                    e.target.dataset.prev = "";
                                  }
                                }}
                                style={{
                                  width: "100%",
                                  paddingRight: missingStudentFilter
                                    ? "30px"
                                    : undefined,
                                }}
                              />
                              {missingStudentFilter && (
                                <button
                                  onClick={(e) => {
                                    e.preventDefault();
                                    setMissingStudentFilter("");
                                  }}
                                  style={{
                                    position: "absolute",
                                    right: "8px",
                                    top: "50%",
                                    transform: "translateY(-50%)",
                                    background: "none",
                                    border: "none",
                                    cursor: "pointer",
                                    color: "#888",
                                    padding: "4px",
                                    display: "flex",
                                    alignItems: "center",
                                  }}
                                  title="Clear"
                                >
                                  <Icon name="X" size={14} />
                                </button>
                              )}
                            </div>
                            <datalist id="missing-student-suggestions">
                              {(missingPeriodFilter
                                ? sortedPeriods.find(
                                    (p) => p.filename === missingPeriodFilter,
                                  )?.students || []
                                : sortedPeriods.flatMap((p) => p.students || [])
                              ).map((s, i) => {
                                const name =
                                  s.full ||
                                  s.name ||
                                  (
                                    (s.first || "") +
                                    " " +
                                    (s.last || "")
                                  ).trim();
                                return <option key={i} value={name} />;
                              })}
                            </datalist>
                          </div>
                          <div style={{ flex: "1", minWidth: "180px" }}>
                            <label
                              style={{
                                fontSize: "0.8rem",
                                color: "#888",
                                marginBottom: "4px",
                                display: "block",
                              }}
                            >
                              Assignment
                            </label>
                            <select
                              className="input"
                              value={missingAssignmentFilter}
                              onChange={(e) =>
                                setMissingAssignmentFilter(e.target.value)
                              }
                              style={{ width: "100%" }}
                            >
                              <option value="">All Assignments</option>
                              {savedAssignments.map((name) => (
                                <option key={name} value={name}>
                                  {name}
                                  {savedAssignmentData[name]?.completionOnly
                                    ? " (Completion)"
                                    : ""}
                                </option>
                              ))}
                            </select>
                          </div>
                        </div>

                        {/* Missing Report */}
                        {periods.length === 0 ? (
                          <div
                            style={{
                              color: "#888",
                              textAlign: "center",
                              padding: "20px",
                            }}
                          >
                            <Icon
                              name="AlertCircle"
                              size={24}
                              style={{ marginBottom: "10px", opacity: 0.5 }}
                            />
                            <div>
                              Upload period rosters in Settings to track missing
                              assignments
                            </div>
                          </div>
                        ) : missingFilesLoading ? (
                          <div
                            style={{
                              color: "#888",
                              textAlign: "center",
                              padding: "20px",
                            }}
                          >
                            Loading files...
                          </div>
                        ) : (
                          (() => {
                            // Get assignments to check
                            const assignmentsToCheck = missingAssignmentFilter
                              ? [missingAssignmentFilter]
                              : savedAssignments;

                            // Get periods to check
                            const periodsToCheck = missingPeriodFilter
                              ? sortedPeriods.filter(
                                  (p) => p.filename === missingPeriodFilter,
                                )
                              : sortedPeriods;

                            // Build set of uploaded file names (normalized)
                            const uploadedNames = new Set(
                              missingUploadedFiles.map((f) =>
                                (f.name || f)
                                  .toLowerCase()
                                  .replace(/[_\-\.]/g, " ")
                                  .trim(),
                              ),
                            );

                            // Check if student has uploaded for an assignment (including aliases)
                            const hasUploaded = (
                              studentName,
                              assignmentName,
                            ) => {
                              const sName = studentName.toLowerCase();
                              // Get all names to check (current name + aliases)
                              const assignmentData =
                                savedAssignmentData[assignmentName] || {};
                              const namesToCheck = [
                                assignmentName.toLowerCase(),
                                ...(assignmentData.aliases || []).map((a) =>
                                  a.toLowerCase(),
                                ),
                              ];

                              return [...uploadedNames].some((fileName) => {
                                const fLower = fileName.toLowerCase();
                                const nameParts = sName.split(" ");
                                const hasStudentName =
                                  nameParts.every((part) =>
                                    fLower.includes(part),
                                  ) || fLower.includes(sName.replace(" ", ""));
                                // Check if file matches any of the assignment names (current or aliases)
                                const hasAssignment = namesToCheck.some(
                                  (aName) =>
                                    fLower.includes(
                                      aName.replace(/[_\-]/g, " "),
                                    ),
                                );
                                return hasStudentName && hasAssignment;
                              });
                            };

                            // If filtering by student
                            if (missingStudentFilter) {
                              const studentLower =
                                missingStudentFilter.toLowerCase();
                              let studentInfo = null;
                              let studentPeriod = null;

                              for (const period of periodsToCheck) {
                                const found = (period.students || []).find(
                                  (s) => {
                                    const fullName = (
                                      s.full ||
                                      s.name ||
                                      (
                                        (s.first || "") +
                                        " " +
                                        (s.last || "")
                                      ).trim()
                                    ).toLowerCase();
                                    return (
                                      fullName.includes(studentLower) ||
                                      studentLower.includes(fullName)
                                    );
                                  },
                                );
                                if (found) {
                                  studentInfo = found;
                                  studentPeriod = period.period_name;
                                  break;
                                }
                              }

                              const displayName = studentInfo
                                ? studentInfo.full ||
                                  studentInfo.name ||
                                  (
                                    (studentInfo.first || "") +
                                    " " +
                                    (studentInfo.last || "")
                                  ).trim()
                                : missingStudentFilter;

                              const missing = assignmentsToCheck.filter(
                                (a) => !hasUploaded(displayName, a),
                              );
                              const submitted = assignmentsToCheck.filter((a) =>
                                hasUploaded(displayName, a),
                              );

                              return (
                                <div>
                                  <div
                                    style={{
                                      padding: "15px",
                                      background: "rgba(0,0,0,0.2)",
                                      borderRadius: "8px",
                                      marginBottom: "15px",
                                    }}
                                  >
                                    <div
                                      style={{
                                        fontWeight: 600,
                                        marginBottom: "8px",
                                      }}
                                    >
                                      {displayName}{" "}
                                      {studentPeriod && (
                                        <span
                                          style={{
                                            color: "#888",
                                            fontWeight: 400,
                                          }}
                                        >
                                          ({studentPeriod})
                                        </span>
                                      )}
                                    </div>
                                    <div
                                      style={{
                                        display: "flex",
                                        gap: "20px",
                                        fontSize: "0.9rem",
                                      }}
                                    >
                                      <span>
                                        <span
                                          style={{
                                            color: "#f59e0b",
                                            fontWeight: 600,
                                          }}
                                        >
                                          {missing.length}
                                        </span>{" "}
                                        missing
                                      </span>
                                      <span>
                                        <span
                                          style={{
                                            color: "#10b981",
                                            fontWeight: 600,
                                          }}
                                        >
                                          {submitted.length}
                                        </span>{" "}
                                        uploaded
                                      </span>
                                      <span>
                                        <span
                                          style={{
                                            color: "#6366f1",
                                            fontWeight: 600,
                                          }}
                                        >
                                          {assignmentsToCheck.length}
                                        </span>{" "}
                                        total
                                      </span>
                                    </div>
                                  </div>
                                  {missing.length > 0 ? (
                                    <div>
                                      <div
                                        style={{
                                          fontSize: "0.85rem",
                                          color: "#888",
                                          marginBottom: "10px",
                                        }}
                                      >
                                        Missing:
                                      </div>
                                      <div
                                        style={{
                                          display: "flex",
                                          flexWrap: "wrap",
                                          gap: "8px",
                                        }}
                                      >
                                        {missing.map((a) => (
                                          <span
                                            key={a}
                                            style={{
                                              padding: "6px 12px",
                                              background:
                                                "rgba(251,191,36,0.2)",
                                              borderRadius: "6px",
                                              fontSize: "0.85rem",
                                              color: "#fbbf24",
                                            }}
                                          >
                                            {a}
                                          </span>
                                        ))}
                                      </div>
                                    </div>
                                  ) : (
                                    <div
                                      style={{
                                        color: "#10b981",
                                        display: "flex",
                                        alignItems: "center",
                                        gap: "8px",
                                      }}
                                    >
                                      <Icon name="CheckCircle" size={18} />
                                      All assignments uploaded!
                                    </div>
                                  )}
                                </div>
                              );
                            }

                            // Default: show by period
                            let totalMissing = 0;
                            let totalStudents = 0;
                            const periodReports = [];

                            periodsToCheck.forEach((period) => {
                              const students = period.students || [];
                              totalStudents += students.length;
                              const studentsWithMissing = [];

                              students.forEach((student) => {
                                const name =
                                  student.full ||
                                  student.name ||
                                  (
                                    (student.first || "") +
                                    " " +
                                    (student.last || "")
                                  ).trim();
                                const missing = assignmentsToCheck.filter(
                                  (a) => !hasUploaded(name, a),
                                );
                                if (missing.length > 0) {
                                  studentsWithMissing.push({ name, missing });
                                  totalMissing += missing.length;
                                }
                              });

                              periodReports.push({
                                period: period.period_name,
                                total: students.length,
                                studentsWithMissing,
                                allComplete: studentsWithMissing.length === 0,
                              });
                            });

                            const totalSlots =
                              totalStudents * assignmentsToCheck.length;
                            const totalUploaded = totalSlots - totalMissing;

                            return (
                              <div>
                                {/* Summary Stats */}
                                <div
                                  style={{
                                    display: "flex",
                                    gap: "20px",
                                    marginBottom: "20px",
                                    padding: "15px",
                                    background: "rgba(0,0,0,0.2)",
                                    borderRadius: "8px",
                                  }}
                                >
                                  <div style={{ textAlign: "center" }}>
                                    <div
                                      style={{
                                        fontSize: "1.8rem",
                                        fontWeight: 700,
                                        color: "#f59e0b",
                                      }}
                                    >
                                      {totalMissing}
                                    </div>
                                    <div
                                      style={{
                                        fontSize: "0.75rem",
                                        color: "#888",
                                      }}
                                    >
                                      Missing
                                    </div>
                                  </div>
                                  <div style={{ textAlign: "center" }}>
                                    <div
                                      style={{
                                        fontSize: "1.8rem",
                                        fontWeight: 700,
                                        color: "#10b981",
                                      }}
                                    >
                                      {totalUploaded}
                                    </div>
                                    <div
                                      style={{
                                        fontSize: "0.75rem",
                                        color: "#888",
                                      }}
                                    >
                                      Uploaded
                                    </div>
                                  </div>
                                  <div style={{ textAlign: "center" }}>
                                    <div
                                      style={{
                                        fontSize: "1.8rem",
                                        fontWeight: 700,
                                        color: "#6366f1",
                                      }}
                                    >
                                      {totalStudents}
                                    </div>
                                    <div
                                      style={{
                                        fontSize: "0.75rem",
                                        color: "#888",
                                      }}
                                    >
                                      Students
                                    </div>
                                  </div>
                                  <div style={{ textAlign: "center" }}>
                                    <div
                                      style={{
                                        fontSize: "1.8rem",
                                        fontWeight: 700,
                                        color: "#8b5cf6",
                                      }}
                                    >
                                      {assignmentsToCheck.length}
                                    </div>
                                    <div
                                      style={{
                                        fontSize: "0.75rem",
                                        color: "#888",
                                      }}
                                    >
                                      Assignments
                                    </div>
                                  </div>
                                </div>

                                {/* Per Period Breakdown */}
                                <div style={{ display: "grid", gap: "12px" }}>
                                  {periodReports.map((report) => (
                                    <div
                                      key={report.period}
                                      style={{
                                        padding: "12px 15px",
                                        background: "rgba(0,0,0,0.15)",
                                        borderRadius: "8px",
                                        border: report.allComplete
                                          ? "1px solid rgba(16,185,129,0.3)"
                                          : "1px solid rgba(251,191,36,0.3)",
                                      }}
                                    >
                                      <div
                                        style={{
                                          display: "flex",
                                          justifyContent: "space-between",
                                          alignItems: "center",
                                          marginBottom:
                                            report.studentsWithMissing.length >
                                            0
                                              ? "10px"
                                              : 0,
                                        }}
                                      >
                                        <span style={{ fontWeight: 600 }}>
                                          {report.period}
                                        </span>
                                        <span style={{ fontSize: "0.85rem" }}>
                                          {report.allComplete ? (
                                            <span style={{ color: "#10b981" }}>
                                              ✓ All complete
                                            </span>
                                          ) : (
                                            <span style={{ color: "#f59e0b" }}>
                                              {
                                                report.studentsWithMissing
                                                  .length
                                              }{" "}
                                              students missing work
                                            </span>
                                          )}
                                        </span>
                                      </div>
                                      {report.studentsWithMissing.length >
                                        0 && (
                                        <div
                                          style={{
                                            display: "flex",
                                            flexDirection: "column",
                                            gap: "6px",
                                          }}
                                        >
                                          {report.studentsWithMissing.map(
                                            (s, idx) => (
                                              <div
                                                key={idx}
                                                style={{
                                                  display: "flex",
                                                  alignItems: "center",
                                                  gap: "10px",
                                                  flexWrap: "wrap",
                                                }}
                                              >
                                                <span
                                                  style={{
                                                    minWidth: "140px",
                                                    fontWeight: 500,
                                                    fontSize: "0.9rem",
                                                  }}
                                                >
                                                  {s.name}
                                                </span>
                                                <div
                                                  style={{
                                                    display: "flex",
                                                    gap: "5px",
                                                    flexWrap: "wrap",
                                                  }}
                                                >
                                                  {s.missing.map((a) => (
                                                    <span
                                                      key={a}
                                                      style={{
                                                        padding: "2px 8px",
                                                        background:
                                                          "rgba(251,191,36,0.2)",
                                                        borderRadius: "4px",
                                                        fontSize: "0.75rem",
                                                        color: "#fbbf24",
                                                      }}
                                                    >
                                                      {a}
                                                    </span>
                                                  ))}
                                                </div>
                                              </div>
                                            ),
                                          )}
                                        </div>
                                      )}
                                    </div>
                                  ))}
                                </div>
                              </div>
                            );
                          })()
                        )}
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
                              <th style={{ textAlign: "center" }}>
                                Assignments
                              </th>
                              <th style={{ textAlign: "center" }}>Average</th>
                              <th style={{ textAlign: "center" }}>Trend</th>
                            </tr>
                          </thead>
                          <tbody>
                            {(filteredAnalytics.student_progress || []).map(
                              (s, i) => (
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
                              ),
                            )}
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
                  {/* Mode Toggle */}
                  <div
                    style={{
                      display: "flex",
                      gap: "10px",
                      marginBottom: "20px",
                    }}
                  >
                    <button
                      onClick={() => setPlannerMode("lesson")}
                      className="btn"
                      style={{
                        padding: "10px 20px",
                        background:
                          plannerMode === "lesson"
                            ? "linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))"
                            : "var(--glass-bg)",
                        border:
                          plannerMode === "lesson"
                            ? "none"
                            : "1px solid var(--glass-border)",
                        color: plannerMode === "lesson" ? "#fff" : "var(--text-secondary)",
                        fontWeight: 600,
                        borderRadius: "10px",
                        display: "flex",
                        alignItems: "center",
                        gap: "8px",
                      }}
                    >
                      <Icon name="BookOpen" size={18} />
                      Lesson Planning
                    </button>
                    <button
                      onClick={() => setPlannerMode("assessment")}
                      className="btn"
                      style={{
                        padding: "10px 20px",
                        background:
                          plannerMode === "assessment"
                            ? "linear-gradient(135deg, #8b5cf6, #6366f1)"
                            : "var(--glass-bg)",
                        border:
                          plannerMode === "assessment"
                            ? "none"
                            : "1px solid var(--glass-border)",
                        color: plannerMode === "assessment" ? "#fff" : "var(--text-secondary)",
                        fontWeight: 600,
                        borderRadius: "10px",
                        display: "flex",
                        alignItems: "center",
                        gap: "8px",
                      }}
                    >
                      <Icon name="ClipboardCheck" size={18} />
                      Assessment Generator
                    </button>
                    <button
                      onClick={() => {
                        setPlannerMode("dashboard");
                        fetchPublishedAssessments();
                        fetchSavedAssessments();
                      }}
                      className="btn"
                      style={{
                        padding: "10px 20px",
                        background:
                          plannerMode === "dashboard"
                            ? "linear-gradient(135deg, #22c55e, #16a34a)"
                            : "var(--glass-bg)",
                        border:
                          plannerMode === "dashboard"
                            ? "none"
                            : "1px solid var(--glass-border)",
                        color: plannerMode === "dashboard" ? "#fff" : "var(--text-secondary)",
                        fontWeight: 600,
                        borderRadius: "10px",
                        display: "flex",
                        alignItems: "center",
                        gap: "8px",
                      }}
                    >
                      <Icon name="Users" size={18} />
                      Student Portal
                    </button>
                  </div>

                  {/* Lesson Planning Mode */}
                  {plannerMode === "lesson" && (
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
                                    periodLength:
                                      parseInt(e.target.value) || 50,
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
                          {/* Brainstorm Button */}
                          <button
                            onClick={brainstormIdeasHandler}
                            disabled={
                              brainstormLoading ||
                              selectedStandards.length === 0
                            }
                            className="btn btn-secondary"
                            style={{
                              width: "100%",
                              justifyContent: "center",
                              marginBottom: "10px",
                              opacity:
                                brainstormLoading ||
                                selectedStandards.length === 0
                                  ? 0.5
                                  : 1,
                            }}
                          >
                            {brainstormLoading ? (
                              <Icon
                                name="Loader2"
                                size={18}
                                style={{ animation: "spin 1s linear infinite" }}
                              />
                            ) : (
                              <Icon name="Lightbulb" size={18} />
                            )}
                            {brainstormLoading
                              ? "Brainstorming..."
                              : "Brainstorm Ideas"}
                          </button>

                          {/* Generate Plan Button */}
                          <button
                            onClick={() => generateLessonPlan(false)}
                            disabled={
                              plannerLoading || selectedStandards.length === 0
                            }
                            className="btn btn-primary"
                            style={{
                              width: "100%",
                              justifyContent: "center",
                              marginBottom: "10px",
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
                            {plannerLoading
                              ? "Generating..."
                              : selectedIdea
                                ? "Generate from Idea"
                                : "Generate Plan"}
                          </button>

                          {/* Generate Variations Button */}
                          <button
                            onClick={() => generateLessonPlan(true)}
                            disabled={
                              plannerLoading || selectedStandards.length === 0
                            }
                            className="btn btn-secondary"
                            style={{
                              width: "100%",
                              justifyContent: "center",
                              opacity:
                                plannerLoading || selectedStandards.length === 0
                                  ? 0.5
                                  : 1,
                              fontSize: "0.85rem",
                            }}
                          >
                            <Icon name="Layers" size={16} />
                            Generate 3 Variations
                          </button>
                        </div>
                      </div>
                    </div>

                    {/* Main Content */}
                    <div>
                      {/* Brainstormed Ideas Section - Full Width */}
                      {brainstormIdeas.length > 0 &&
                        !lessonPlan &&
                        lessonVariations.length === 0 && (
                          <div
                            className="glass-card"
                            style={{ padding: "25px", marginBottom: "20px" }}
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
                                  fontSize: "1.2rem",
                                  fontWeight: 700,
                                  display: "flex",
                                  alignItems: "center",
                                  gap: "10px",
                                  margin: 0,
                                }}
                              >
                                <Icon
                                  name="Lightbulb"
                                  size={24}
                                  style={{ color: "#f59e0b" }}
                                />{" "}
                                Lesson Plan Ideas
                              </h3>
                              <button
                                onClick={() => setBrainstormIdeas([])}
                                className="btn btn-secondary"
                                style={{
                                  padding: "6px 12px",
                                  fontSize: "0.85rem",
                                }}
                              >
                                <Icon name="X" size={14} /> Clear
                              </button>
                            </div>
                            <p
                              style={{
                                fontSize: "0.9rem",
                                color: "var(--text-secondary)",
                                marginBottom: "20px",
                              }}
                            >
                              Select an idea to develop into a full lesson plan,
                              or use it as inspiration.
                            </p>
                            <div
                              style={{
                                display: "grid",
                                gridTemplateColumns:
                                  "repeat(auto-fill, minmax(300px, 1fr))",
                                gap: "15px",
                              }}
                            >
                              {brainstormIdeas.map((idea) => (
                                <div
                                  key={idea.id}
                                  onClick={() => {
                                    setSelectedIdea(
                                      selectedIdea?.id === idea.id
                                        ? null
                                        : idea,
                                    );
                                    if (selectedIdea?.id !== idea.id) {
                                      setUnitConfig((prev) => ({
                                        ...prev,
                                        title: idea.title,
                                      }));
                                    }
                                  }}
                                  style={{
                                    padding: "20px",
                                    borderRadius: "12px",
                                    background:
                                      selectedIdea?.id === idea.id
                                        ? "rgba(99,102,241,0.15)"
                                        : "var(--input-bg)",
                                    border:
                                      selectedIdea?.id === idea.id
                                        ? "2px solid var(--accent-primary)"
                                        : "1px solid var(--glass-border)",
                                    cursor: "pointer",
                                    transition: "all 0.2s",
                                  }}
                                >
                                  <div
                                    style={{
                                      display: "flex",
                                      justifyContent: "space-between",
                                      alignItems: "flex-start",
                                      marginBottom: "10px",
                                    }}
                                  >
                                    <h4
                                      style={{
                                        fontWeight: 600,
                                        fontSize: "1.05rem",
                                        margin: 0,
                                        flex: 1,
                                      }}
                                    >
                                      {idea.title}
                                    </h4>
                                    <span
                                      style={{
                                        padding: "4px 12px",
                                        borderRadius: "12px",
                                        fontSize: "0.75rem",
                                        fontWeight: 600,
                                        marginLeft: "10px",
                                        background:
                                          idea.approach === "Activity-Based"
                                            ? "rgba(16,185,129,0.2)"
                                            : idea.approach === "Discussion"
                                              ? "rgba(99,102,241,0.2)"
                                              : idea.approach === "Project"
                                                ? "rgba(245,158,11,0.2)"
                                                : idea.approach === "Simulation"
                                                  ? "rgba(236,72,153,0.2)"
                                                  : "rgba(107,114,128,0.2)",
                                        color:
                                          idea.approach === "Activity-Based"
                                            ? "#10b981"
                                            : idea.approach === "Discussion"
                                              ? "#6366f1"
                                              : idea.approach === "Project"
                                                ? "#f59e0b"
                                                : idea.approach === "Simulation"
                                                  ? "#ec4899"
                                                  : "#6b7280",
                                      }}
                                    >
                                      {idea.approach}
                                    </span>
                                  </div>
                                  <p
                                    style={{
                                      fontSize: "0.9rem",
                                      color: "var(--text-secondary)",
                                      marginBottom: "12px",
                                      lineHeight: 1.5,
                                    }}
                                  >
                                    {idea.brief}
                                  </p>
                                  <div
                                    style={{
                                      fontSize: "0.85rem",
                                      color: "var(--text-muted)",
                                      marginBottom: "6px",
                                    }}
                                  >
                                    <strong>Hook:</strong> {idea.hook}
                                  </div>
                                  <div
                                    style={{
                                      fontSize: "0.85rem",
                                      color: "var(--text-muted)",
                                    }}
                                  >
                                    <strong>Activity:</strong>{" "}
                                    {idea.key_activity}
                                  </div>
                                  {idea.tools_used && idea.tools_used !== "None - hands-on activity" && (
                                    <div
                                      style={{
                                        fontSize: "0.85rem",
                                        color: "var(--accent-light)",
                                        marginTop: "6px",
                                        display: "flex",
                                        alignItems: "flex-start",
                                        gap: "6px",
                                      }}
                                    >
                                      <Icon name="Monitor" size={14} style={{ marginTop: "2px", flexShrink: 0 }} />
                                      <span><strong>Tools:</strong> {idea.tools_used}</span>
                                    </div>
                                  )}
                                  {selectedIdea?.id === idea.id && (
                                    <div
                                      style={{
                                        marginTop: "12px",
                                        padding: "10px",
                                        background: "rgba(99,102,241,0.1)",
                                        borderRadius: "8px",
                                        fontSize: "0.85rem",
                                        color: "var(--accent-light)",
                                      }}
                                    >
                                      <Icon
                                        name="CheckCircle"
                                        size={14}
                                        style={{
                                          marginRight: "6px",
                                          verticalAlign: "middle",
                                        }}
                                      />
                                      Selected - Click "Generate" to create
                                      lesson plan
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      {/* Lesson Variations Display */}
                      {lessonVariations.length > 0 && !lessonPlan && (
                        <div
                          className="glass-card"
                          style={{
                            padding: "30px",
                            maxHeight: "80vh",
                            overflowY: "auto",
                          }}
                        >
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                              marginBottom: "25px",
                              paddingBottom: "15px",
                              borderBottom: "1px solid var(--glass-border)",
                            }}
                          >
                            <div>
                              <h2
                                style={{
                                  fontSize: "1.5rem",
                                  fontWeight: 700,
                                  marginBottom: "5px",
                                }}
                              >
                                <Icon
                                  name="Layers"
                                  size={24}
                                  style={{
                                    marginRight: "10px",
                                    verticalAlign: "middle",
                                    color: "var(--accent-primary)",
                                  }}
                                />
                                Lesson Plan Variations
                              </h2>
                              <p
                                style={{
                                  color: "var(--text-secondary)",
                                  fontSize: "0.9rem",
                                }}
                              >
                                Compare {lessonVariations.length} different
                                approaches to teaching this content
                              </p>
                            </div>
                            <button
                              onClick={() => setLessonVariations([])}
                              className="btn btn-secondary"
                            >
                              <Icon name="X" size={16} /> Close
                            </button>
                          </div>
                          <div
                            style={{
                              display: "flex",
                              flexDirection: "column",
                              gap: "20px",
                            }}
                          >
                            {lessonVariations.map((variation, idx) => (
                              <div
                                key={idx}
                                style={{
                                  padding: "20px",
                                  background: "var(--input-bg)",
                                  borderRadius: "12px",
                                  border: "1px solid var(--glass-border)",
                                }}
                              >
                                <div
                                  style={{
                                    display: "flex",
                                    justifyContent: "space-between",
                                    alignItems: "flex-start",
                                    marginBottom: "15px",
                                  }}
                                >
                                  <div>
                                    <span
                                      style={{
                                        display: "inline-block",
                                        padding: "4px 12px",
                                        borderRadius: "15px",
                                        fontSize: "0.75rem",
                                        fontWeight: 600,
                                        marginBottom: "8px",
                                        background:
                                          idx === 0
                                            ? "rgba(16,185,129,0.2)"
                                            : idx === 1
                                              ? "rgba(99,102,241,0.2)"
                                              : "rgba(245,158,11,0.2)",
                                        color:
                                          idx === 0
                                            ? "#10b981"
                                            : idx === 1
                                              ? "#6366f1"
                                              : "#f59e0b",
                                      }}
                                    >
                                      {variation.approach ||
                                        `Variation ${idx + 1}`}
                                    </span>
                                    <h3
                                      style={{
                                        fontSize: "1.2rem",
                                        fontWeight: 600,
                                        margin: "8px 0",
                                      }}
                                    >
                                      {variation.title}
                                    </h3>
                                    <p
                                      style={{
                                        color: "var(--text-secondary)",
                                        fontSize: "0.9rem",
                                        lineHeight: 1.5,
                                      }}
                                    >
                                      {variation.overview}
                                    </p>
                                  </div>
                                  <button
                                    onClick={() => {
                                      setLessonPlan(variation);
                                      setLessonVariations([]);
                                    }}
                                    className="btn btn-primary"
                                    style={{ flexShrink: 0 }}
                                  >
                                    <Icon name="Check" size={16} /> Use This
                                    Plan
                                  </button>
                                </div>
                                {variation.essential_questions && (
                                  <div style={{ marginTop: "10px" }}>
                                    <strong
                                      style={{
                                        fontSize: "0.85rem",
                                        color: "var(--text-primary)",
                                      }}
                                    >
                                      Essential Questions:
                                    </strong>
                                    <ul
                                      style={{
                                        margin: "5px 0 0 20px",
                                        fontSize: "0.85rem",
                                        color: "var(--text-secondary)",
                                      }}
                                    >
                                      {variation.essential_questions
                                        .slice(0, 2)
                                        .map((q, i) => (
                                          <li key={i}>{q}</li>
                                        ))}
                                    </ul>
                                  </div>
                                )}
                                {variation.days && (
                                  <div
                                    style={{
                                      marginTop: "10px",
                                      fontSize: "0.85rem",
                                      color: "var(--text-muted)",
                                    }}
                                  >
                                    <Icon
                                      name="Calendar"
                                      size={14}
                                      style={{
                                        marginRight: "6px",
                                        verticalAlign: "middle",
                                      }}
                                    />
                                    {variation.days.length} day
                                    {variation.days.length !== 1
                                      ? "s"
                                      : ""}{" "}
                                    planned
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Single Lesson Plan Display */}
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
                            <div
                              style={{
                                display: "flex",
                                gap: "10px",
                                flexWrap: "wrap",
                              }}
                            >
                              <button
                                onClick={exportLessonPlanHandler}
                                className="btn btn-secondary"
                              >
                                <Icon name="Download" size={16} /> Export
                              </button>
                              <button
                                onClick={() => setShowSaveLesson(true)}
                                className="btn btn-secondary"
                                title="Save for use in assessment generation"
                              >
                                <Icon name="FolderPlus" size={16} /> Save to Unit
                              </button>
                              <div
                                style={{
                                  display: "flex",
                                  gap: "8px",
                                  alignItems: "center",
                                }}
                              >
                                <select
                                  value={assignmentType}
                                  onChange={(e) =>
                                    setAssignmentType(e.target.value)
                                  }
                                  className="input"
                                  style={{
                                    padding: "8px 12px",
                                    minWidth: "120px",
                                  }}
                                >
                                  <option value="worksheet">Worksheet</option>
                                  <option value="quiz">Quiz</option>
                                  <option value="homework">Homework</option>
                                  <option value="project">Project</option>
                                  <option value="essay">Essay</option>
                                  <option value="lab">Lab Activity</option>
                                </select>
                                <button
                                  onClick={generateAssignmentFromLessonHandler}
                                  className="btn btn-primary"
                                  disabled={assignmentLoading}
                                >
                                  {assignmentLoading ? (
                                    <>
                                      <Icon
                                        name="Loader"
                                        size={16}
                                        className="spinning"
                                      />{" "}
                                      Generating...
                                    </>
                                  ) : (
                                    <>
                                      <Icon name="FileText" size={16} /> Create
                                      Assignment
                                    </>
                                  )}
                                </button>
                              </div>
                              <button
                                onClick={() => {
                                  setLessonPlan(null);
                                  setSelectedIdea(null);
                                  setBrainstormIdeas([]);
                                  setGeneratedAssignment(null);
                                }}
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

                          {/* Generated Assignment Section */}
                          {generatedAssignment && (
                            <div
                              style={{
                                marginTop: "30px",
                                padding: "25px",
                                background:
                                  "linear-gradient(135deg, rgba(16,185,129,0.1), rgba(6,182,212,0.1))",
                                borderRadius: "16px",
                                border: "1px solid rgba(16,185,129,0.3)",
                              }}
                            >
                              <div
                                style={{
                                  display: "flex",
                                  justifyContent: "space-between",
                                  alignItems: "flex-start",
                                  marginBottom: "20px",
                                }}
                              >
                                <div>
                                  <h3
                                    style={{
                                      fontSize: "1.4rem",
                                      fontWeight: 700,
                                      marginBottom: "8px",
                                      display: "flex",
                                      alignItems: "center",
                                      gap: "10px",
                                    }}
                                  >
                                    <Icon
                                      name="FileText"
                                      size={24}
                                      style={{ color: "#10b981" }}
                                    />
                                    {generatedAssignment.title}
                                  </h3>
                                  <div
                                    style={{
                                      display: "flex",
                                      gap: "10px",
                                      flexWrap: "wrap",
                                    }}
                                  >
                                    <span
                                      style={{
                                        padding: "4px 10px",
                                        background: "rgba(16,185,129,0.2)",
                                        color: "#10b981",
                                        borderRadius: "12px",
                                        fontSize: "0.8rem",
                                        fontWeight: 500,
                                      }}
                                    >
                                      {generatedAssignment.type
                                        ?.charAt(0)
                                        .toUpperCase() +
                                        generatedAssignment.type?.slice(1)}
                                    </span>
                                    {generatedAssignment.time_estimate && (
                                      <span
                                        style={{
                                          padding: "4px 10px",
                                          background: "rgba(99,102,241,0.2)",
                                          color: "#818cf8",
                                          borderRadius: "12px",
                                          fontSize: "0.8rem",
                                        }}
                                      >
                                        <Icon
                                          name="Clock"
                                          size={12}
                                          style={{ marginRight: "4px" }}
                                        />
                                        {generatedAssignment.time_estimate}
                                      </span>
                                    )}
                                    {generatedAssignment.total_points && (
                                      <span
                                        style={{
                                          padding: "4px 10px",
                                          background: "rgba(251,191,36,0.2)",
                                          color: "#fbbf24",
                                          borderRadius: "12px",
                                          fontSize: "0.8rem",
                                        }}
                                      >
                                        {generatedAssignment.total_points}{" "}
                                        points
                                      </span>
                                    )}
                                  </div>
                                </div>
                                <div style={{ display: "flex", gap: "8px" }}>
                                  <button
                                    onClick={async () => {
                                      try {
                                        const result =
                                          await api.exportGeneratedAssignment(
                                            generatedAssignment,
                                            "pdf",
                                            false,
                                          );
                                        if (result.error) {
                                          addToast(
                                            "Error: " + result.error,
                                            "error",
                                          );
                                        } else {
                                          addToast(
                                            "Student worksheet exported as PDF!",
                                            "success",
                                          );
                                        }
                                      } catch (e) {
                                        addToast(
                                          "Export failed: " + e.message,
                                          "error",
                                        );
                                      }
                                    }}
                                    className="btn btn-primary"
                                    style={{ padding: "8px 14px" }}
                                    title="Export student version as PDF"
                                  >
                                    <Icon name="Download" size={16} />
                                    Export PDF
                                  </button>
                                  <button
                                    onClick={async () => {
                                      try {
                                        const result =
                                          await api.exportGeneratedAssignment(
                                            generatedAssignment,
                                            "pdf",
                                            true,
                                          );
                                        if (result.error) {
                                          addToast(
                                            "Error: " + result.error,
                                            "error",
                                          );
                                        } else {
                                          addToast(
                                            "Answer key exported as PDF!",
                                            "success",
                                          );
                                        }
                                      } catch (e) {
                                        addToast(
                                          "Export failed: " + e.message,
                                          "error",
                                        );
                                      }
                                    }}
                                    className="btn btn-secondary"
                                    style={{ padding: "8px 14px" }}
                                    title="Export teacher version with answers as PDF"
                                  >
                                    <Icon name="Key" size={16} />
                                    Answer Key
                                  </button>
                                  <button
                                    onClick={() =>
                                      setShowInteractivePreview(true)
                                    }
                                    className="btn btn-primary"
                                    style={{
                                      padding: "8px 14px",
                                      background:
                                        "linear-gradient(135deg, #10b981, #059669)",
                                    }}
                                    title="Preview assignment as students will see it"
                                  >
                                    <Icon name="Play" size={16} />
                                    Interactive Preview
                                  </button>
                                  <button
                                    onClick={() => setGeneratedAssignment(null)}
                                    className="btn btn-secondary"
                                    style={{ padding: "6px 12px" }}
                                  >
                                    <Icon name="X" size={16} />
                                  </button>
                                </div>
                              </div>

                              {generatedAssignment.instructions && (
                                <div
                                  style={{
                                    padding: "15px",
                                    background: "var(--glass-bg)",
                                    borderRadius: "10px",
                                    marginBottom: "20px",
                                  }}
                                >
                                  <h4
                                    style={{
                                      fontSize: "0.9rem",
                                      fontWeight: 600,
                                      marginBottom: "8px",
                                    }}
                                  >
                                    <Icon
                                      name="Info"
                                      size={14}
                                      style={{ marginRight: "6px" }}
                                    />
                                    Instructions
                                  </h4>
                                  <p
                                    style={{
                                      fontSize: "0.9rem",
                                      color: "var(--text-secondary)",
                                    }}
                                  >
                                    {generatedAssignment.instructions}
                                  </p>
                                </div>
                              )}

                              {/* Assignment Sections */}
                              {generatedAssignment.sections?.map(
                                (section, sIdx) => (
                                  <div
                                    key={sIdx}
                                    style={{
                                      marginBottom: "20px",
                                      padding: "20px",
                                      background: "var(--input-bg)",
                                      borderRadius: "12px",
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
                                      <h4
                                        style={{
                                          fontSize: "1rem",
                                          fontWeight: 600,
                                        }}
                                      >
                                        {section.name}
                                      </h4>
                                      <span
                                        style={{
                                          padding: "4px 8px",
                                          background: "rgba(99,102,241,0.15)",
                                          color: "var(--accent-light)",
                                          borderRadius: "8px",
                                          fontSize: "0.8rem",
                                        }}
                                      >
                                        {section.points} pts
                                      </span>
                                    </div>

                                    {section.questions?.map((q, qIdx) => (
                                      <div
                                        key={qIdx}
                                        style={{
                                          padding: "12px",
                                          background: "var(--glass-bg)",
                                          borderRadius: "8px",
                                          marginBottom: "10px",
                                        }}
                                      >
                                        <div
                                          style={{
                                            display: "flex",
                                            gap: "10px",
                                          }}
                                        >
                                          <span
                                            style={{
                                              minWidth: "24px",
                                              height: "24px",
                                              background:
                                                "var(--accent-primary)",
                                              borderRadius: "50%",
                                              display: "flex",
                                              alignItems: "center",
                                              justifyContent: "center",
                                              fontSize: "0.8rem",
                                              fontWeight: 600,
                                            }}
                                          >
                                            {q.number}
                                          </span>
                                          <div style={{ flex: 1 }}>
                                            <p style={{ marginBottom: "8px" }}>
                                              {q.question}
                                            </p>
                                            {q.options && (
                                              <div
                                                style={{
                                                  paddingLeft: "10px",
                                                  fontSize: "0.9rem",
                                                  color:
                                                    "var(--text-secondary)",
                                                }}
                                              >
                                                {q.options.map((opt, oIdx) => (
                                                  <div key={oIdx}>{opt}</div>
                                                ))}
                                              </div>
                                            )}
                                            <div
                                              style={{
                                                marginTop: "8px",
                                                fontSize: "0.8rem",
                                                color: "#10b981",
                                                fontStyle: "italic",
                                              }}
                                            >
                                              Answer: {q.answer}
                                            </div>
                                          </div>
                                          <span
                                            style={{
                                              fontSize: "0.8rem",
                                              color: "var(--text-secondary)",
                                            }}
                                          >
                                            {q.points} pts
                                          </span>
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                ),
                              )}

                              {/* Rubric */}
                              {generatedAssignment.rubric?.criteria && (
                                <div
                                  style={{
                                    padding: "15px",
                                    background: "rgba(251,191,36,0.1)",
                                    borderRadius: "10px",
                                    border: "1px solid rgba(251,191,36,0.2)",
                                  }}
                                >
                                  <h4
                                    style={{
                                      fontSize: "0.9rem",
                                      color: "#fbbf24",
                                      marginBottom: "10px",
                                      fontWeight: 600,
                                    }}
                                  >
                                    <Icon
                                      name="Award"
                                      size={14}
                                      style={{ marginRight: "6px" }}
                                    />
                                    Grading Rubric
                                  </h4>
                                  {generatedAssignment.rubric.criteria.map(
                                    (c, cIdx) => (
                                      <div
                                        key={cIdx}
                                        style={{
                                          display: "flex",
                                          justifyContent: "space-between",
                                          padding: "8px 0",
                                          borderBottom:
                                            cIdx <
                                            generatedAssignment.rubric.criteria
                                              .length -
                                              1
                                              ? "1px solid rgba(251,191,36,0.2)"
                                              : "none",
                                        }}
                                      >
                                        <span style={{ fontWeight: 500 }}>
                                          {c.name}
                                        </span>
                                        <span
                                          style={{
                                            color: "var(--text-secondary)",
                                            fontSize: "0.9rem",
                                          }}
                                        >
                                          {c.points} pts - {c.description}
                                        </span>
                                      </div>
                                    ),
                                  )}
                                </div>
                              )}
                            </div>
                          )}
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
                              <Icon name="Library" size={20} /> Select Standards
                              ({selectedStandards.length})
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
                              <Icon
                                name="MapPin"
                                size={14}
                                style={{
                                  marginRight: "6px",
                                  verticalAlign: "middle",
                                }}
                              />
                              {{
                                FL: "Florida",
                                TX: "Texas",
                                CA: "California",
                                NY: "New York",
                                GA: "Georgia",
                                NC: "North Carolina",
                                VA: "Virginia",
                                OH: "Ohio",
                                PA: "Pennsylvania",
                                IL: "Illinois",
                              }[config.state] || config.state}
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
                              <Icon
                                name="GraduationCap"
                                size={14}
                                style={{
                                  marginRight: "6px",
                                  verticalAlign: "middle",
                                }}
                              />
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
                              <Icon
                                name="BookOpen"
                                size={14}
                                style={{
                                  marginRight: "6px",
                                  verticalAlign: "middle",
                                }}
                              />
                              {config.subject}
                            </span>
                          </div>

                          <div
                            style={{ maxHeight: "500px", overflowY: "auto" }}
                          >
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
                                  style={{
                                    animation: "spin 1s linear infinite",
                                  }}
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
                                  isExpanded={expandedStandards.includes(
                                    std.code,
                                  )}
                                  onExpand={() =>
                                    setExpandedStandards((prev) =>
                                      prev.includes(std.code)
                                        ? prev.filter((c) => c !== std.code)
                                        : [...prev, std.code],
                                    )
                                  }
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
                                <Icon
                                  name="FileQuestion"
                                  size={40}
                                  style={{
                                    color: "var(--text-muted)",
                                    marginBottom: "15px",
                                  }}
                                />
                                <p
                                  style={{
                                    color: "var(--text-secondary)",
                                    marginBottom: "10px",
                                  }}
                                >
                                  No standards found for Grade{" "}
                                  {config.grade_level} {config.subject}.
                                </p>
                                <p
                                  style={{
                                    color: "var(--text-muted)",
                                    fontSize: "0.85rem",
                                  }}
                                >
                                  Try a different grade level or subject in
                                  Settings.
                                </p>
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                  )}

                  {/* Assessment Generator Mode */}
                  {plannerMode === "assessment" && (
                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "350px 1fr",
                        gap: "25px",
                      }}
                    >
                      {/* Assessment Config Sidebar */}
                      <div
                        style={{
                          display: "flex",
                          flexDirection: "column",
                          gap: "20px",
                        }}
                      >
                        {/* Assessment Type */}
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
                            <Icon name="Settings" size={20} /> Assessment Settings
                          </h3>
                          <div
                            style={{
                              display: "flex",
                              flexDirection: "column",
                              gap: "15px",
                            }}
                          >
                            <div>
                              <label className="label">Assessment Type</label>
                              <select
                                className="input"
                                value={assessmentConfig.type}
                                onChange={(e) =>
                                  setAssessmentConfig({
                                    ...assessmentConfig,
                                    type: e.target.value,
                                  })
                                }
                              >
                                <option value="quiz">Quiz</option>
                                <option value="test">Test</option>
                                <option value="benchmark">Benchmark Assessment</option>
                                <option value="formative">Formative Check</option>
                              </select>
                            </div>
                            <div>
                              <label className="label">Title (Optional)</label>
                              <input
                                type="text"
                                className="input"
                                value={assessmentConfig.title}
                                onChange={(e) =>
                                  setAssessmentConfig({
                                    ...assessmentConfig,
                                    title: e.target.value,
                                  })
                                }
                                placeholder="Auto-generated from standards"
                              />
                            </div>
                            <div>
                              <label className="label">Target Period</label>
                              {periods.length > 0 ? (
                                <select
                                  className="input"
                                  value={assessmentConfig.targetPeriod}
                                  onChange={(e) =>
                                    setAssessmentConfig({
                                      ...assessmentConfig,
                                      targetPeriod: e.target.value,
                                    })
                                  }
                                  style={{ width: "100%" }}
                                >
                                  <option value="">-- No specific period --</option>
                                  {periods.map((p) => (
                                    <option key={p.filename} value={p.period_name}>{p.period_name}</option>
                                  ))}
                                </select>
                              ) : (
                                <input
                                  type="text"
                                  className="input"
                                  value={assessmentConfig.targetPeriod}
                                  onChange={(e) =>
                                    setAssessmentConfig({
                                      ...assessmentConfig,
                                      targetPeriod: e.target.value,
                                    })
                                  }
                                  placeholder="e.g., Period 1, Advanced, Standard"
                                  style={{ width: "100%" }}
                                />
                              )}
                              <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "4px" }}>
                                Match to your Global AI Instructions
                              </p>
                            </div>
                            <div style={{ display: "flex", gap: "15px" }}>
                              <div style={{ flex: 1 }}>
                                <label className="label">Total Questions</label>
                                <input
                                  type="number"
                                  className="input"
                                  value={assessmentConfig.totalQuestions}
                                  onChange={(e) => {
                                    const val = e.target.value;
                                    const newTotal = val === '' ? '' : parseInt(val);
                                    setAssessmentConfig({
                                      ...assessmentConfig,
                                      totalQuestions: newTotal,
                                    });
                                  }}
                                  onBlur={(e) => {
                                    const val = parseInt(e.target.value) || 10;
                                    const clamped = Math.max(5, Math.min(50, val));
                                    const newTypes = distributeQuestions(clamped);
                                    const newDok = distributeDOK(clamped);
                                    const newPointsPerType = distributePoints(assessmentConfig.totalPoints || 30, newTypes);

                                    setAssessmentConfig({
                                      ...assessmentConfig,
                                      totalQuestions: clamped,
                                      questionTypes: newTypes,
                                      dokDistribution: newDok,
                                      pointsPerType: newPointsPerType,
                                    });
                                  }}
                                  min="5"
                                  max="50"
                                />
                              </div>
                              <div style={{ flex: 1 }}>
                                <label className="label">Total Points</label>
                                <input
                                  type="number"
                                  className="input"
                                  value={assessmentConfig.totalPoints}
                                  onChange={(e) => {
                                    const val = e.target.value;
                                    // Allow empty while typing, parse as number
                                    const newTotalPoints = val === '' ? '' : parseInt(val);
                                    setAssessmentConfig({
                                      ...assessmentConfig,
                                      totalPoints: newTotalPoints,
                                    });
                                  }}
                                  onBlur={(e) => {
                                    // On blur, ensure valid value and recalculate points
                                    const val = parseInt(e.target.value) || 30;
                                    const clamped = Math.max(10, Math.min(200, val));
                                    const newPointsPerType = distributePoints(clamped, assessmentConfig.questionTypes);
                                    setAssessmentConfig({
                                      ...assessmentConfig,
                                      totalPoints: clamped,
                                      pointsPerType: newPointsPerType,
                                    });
                                  }}
                                  min="10"
                                  max="200"
                                />
                              </div>
                            </div>
                          </div>
                        </div>

                        {/* Question Types */}
                        <div className="glass-card" style={{ padding: "20px" }}>
                          <h3
                            style={{
                              fontSize: "1rem",
                              fontWeight: 700,
                              marginBottom: "15px",
                              display: "flex",
                              alignItems: "center",
                              gap: "10px",
                            }}
                          >
                            <Icon name="List" size={18} /> Question Types
                          </h3>
                          {/* Column Headers */}
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "space-between",
                              marginBottom: "8px",
                              paddingBottom: "8px",
                              borderBottom: "1px solid rgba(255,255,255,0.1)",
                            }}
                          >
                            <span style={{ fontSize: "0.8rem", color: "rgba(255,255,255,0.6)", flex: 1 }}>Type</span>
                            <span style={{ fontSize: "0.8rem", color: "rgba(255,255,255,0.6)", width: "70px", textAlign: "center" }}>Count</span>
                            <span style={{ fontSize: "0.8rem", color: "rgba(255,255,255,0.6)", width: "70px", textAlign: "center" }}>Points</span>
                          </div>
                          <div
                            style={{
                              display: "flex",
                              flexDirection: "column",
                              gap: "12px",
                            }}
                          >
                            {[
                              { key: "multiple_choice", label: "Multiple Choice", defaultPts: 1 },
                              { key: "short_answer", label: "Short Answer", defaultPts: 2 },
                              { key: "extended_response", label: "Extended Response", defaultPts: 4 },
                              { key: "true_false", label: "True/False", defaultPts: 1 },
                              { key: "matching", label: "Matching", defaultPts: 1 },
                            ].map((qType) => (
                              <div
                                key={qType.key}
                                style={{
                                  display: "flex",
                                  alignItems: "center",
                                  justifyContent: "space-between",
                                }}
                              >
                                <label style={{ fontSize: "0.9rem", flex: 1 }}>{qType.label}</label>
                                <input
                                  type="number"
                                  className="input"
                                  value={assessmentConfig.questionTypes[qType.key] || 0}
                                  onChange={(e) =>
                                    setAssessmentConfig({
                                      ...assessmentConfig,
                                      questionTypes: {
                                        ...assessmentConfig.questionTypes,
                                        [qType.key]: parseInt(e.target.value) || 0,
                                      },
                                    })
                                  }
                                  style={{ width: "70px", textAlign: "center" }}
                                  min="0"
                                  max="30"
                                  title="Number of questions"
                                />
                                <input
                                  type="number"
                                  className="input"
                                  value={assessmentConfig.pointsPerType?.[qType.key] ?? qType.defaultPts}
                                  onChange={(e) =>
                                    setAssessmentConfig({
                                      ...assessmentConfig,
                                      pointsPerType: {
                                        ...assessmentConfig.pointsPerType,
                                        [qType.key]: parseInt(e.target.value) || 0,
                                      },
                                    })
                                  }
                                  style={{ width: "70px", textAlign: "center", marginLeft: "8px" }}
                                  min="0"
                                  max="100"
                                  title="Points per question"
                                />
                              </div>
                            ))}
                          </div>
                          {/* Totals Display */}
                          <div
                            style={{
                              marginTop: "15px",
                              paddingTop: "12px",
                              borderTop: "1px solid rgba(255,255,255,0.1)",
                              display: "flex",
                              flexDirection: "column",
                              gap: "8px",
                            }}
                          >
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                              <span style={{ fontSize: "0.9rem", fontWeight: 600 }}>Total Questions:</span>
                              {(() => {
                                const calculated = Object.values(assessmentConfig.questionTypes || {}).reduce((a, b) => a + b, 0);
                                const target = assessmentConfig.totalQuestions || 20;
                                const matches = calculated === target;
                                return (
                                  <span style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                                    <span style={{ fontSize: "1rem", fontWeight: 700, color: matches ? "#22c55e" : "#f59e0b" }}>
                                      {calculated}
                                    </span>
                                    {!matches && (
                                      <span style={{ fontSize: "0.8rem", color: "rgba(255,255,255,0.5)" }}>
                                        (target: {target})
                                      </span>
                                    )}
                                  </span>
                                );
                              })()}
                            </div>
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                              <span style={{ fontSize: "0.9rem", fontWeight: 600 }}>Total Points:</span>
                            {(() => {
                              const calculated = Object.entries(assessmentConfig.questionTypes || {}).reduce((total, [key, count]) => {
                                const pts = assessmentConfig.pointsPerType?.[key] || { multiple_choice: 1, short_answer: 2, extended_response: 4, true_false: 1, matching: 1 }[key] || 1;
                                return total + (count * pts);
                              }, 0);
                              const target = assessmentConfig.totalPoints || 30;
                              const matches = calculated === target;
                              return (
                                <span style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                                  <span style={{ fontSize: "1.1rem", fontWeight: 700, color: matches ? "#22c55e" : "#f59e0b" }}>
                                    {calculated}
                                  </span>
                                  {!matches && (
                                    <span style={{ fontSize: "0.8rem", color: "rgba(255,255,255,0.5)" }}>
                                      (target: {target})
                                    </span>
                                  )}
                                </span>
                              );
                            })()}
                            </div>
                          </div>
                        </div>

                        {/* DOK Distribution */}
                        <div className="glass-card" style={{ padding: "20px" }}>
                          <h3
                            style={{
                              fontSize: "1rem",
                              fontWeight: 700,
                              marginBottom: "15px",
                              display: "flex",
                              alignItems: "center",
                              gap: "10px",
                            }}
                          >
                            <Icon name="BarChart3" size={18} /> DOK Distribution
                          </h3>
                          <div
                            style={{
                              display: "flex",
                              flexDirection: "column",
                              gap: "12px",
                            }}
                          >
                            {[
                              { level: "1", label: "DOK 1 - Recall", color: "#22c55e" },
                              { level: "2", label: "DOK 2 - Skills", color: "#3b82f6" },
                              { level: "3", label: "DOK 3 - Strategic", color: "#f59e0b" },
                              { level: "4", label: "DOK 4 - Extended", color: "#ef4444" },
                            ].map((dok) => (
                              <div
                                key={dok.level}
                                style={{
                                  display: "flex",
                                  alignItems: "center",
                                  justifyContent: "space-between",
                                }}
                              >
                                <label
                                  style={{
                                    fontSize: "0.9rem",
                                    display: "flex",
                                    alignItems: "center",
                                    gap: "8px",
                                  }}
                                >
                                  <span
                                    style={{
                                      width: "12px",
                                      height: "12px",
                                      borderRadius: "50%",
                                      background: dok.color,
                                    }}
                                  />
                                  {dok.label}
                                </label>
                                <input
                                  type="number"
                                  className="input"
                                  value={assessmentConfig.dokDistribution[dok.level] || 0}
                                  onChange={(e) =>
                                    setAssessmentConfig({
                                      ...assessmentConfig,
                                      dokDistribution: {
                                        ...assessmentConfig.dokDistribution,
                                        [dok.level]: parseInt(e.target.value) || 0,
                                      },
                                    })
                                  }
                                  style={{ width: "70px" }}
                                  min="0"
                                  max="20"
                                />
                              </div>
                            ))}
                          </div>
                          {/* DOK Total Display */}
                          <div
                            style={{
                              marginTop: "12px",
                              paddingTop: "12px",
                              borderTop: "1px solid rgba(255,255,255,0.1)",
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                            }}
                          >
                            <span style={{ fontSize: "0.9rem", fontWeight: 600 }}>Total:</span>
                            {(() => {
                              const calculated = Object.values(assessmentConfig.dokDistribution || {}).reduce((a, b) => a + b, 0);
                              const target = assessmentConfig.totalQuestions || 20;
                              const matches = calculated === target;
                              return (
                                <span style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                                  <span style={{ fontSize: "1rem", fontWeight: 700, color: matches ? "#22c55e" : "#f59e0b" }}>
                                    {calculated}
                                  </span>
                                  {!matches && (
                                    <span style={{ fontSize: "0.8rem", color: "rgba(255,255,255,0.5)" }}>
                                      (target: {target})
                                    </span>
                                  )}
                                </span>
                              );
                            })()}
                          </div>
                        </div>

                        {/* Generate Button */}
                        <button
                          onClick={generateAssessmentHandler}
                          disabled={selectedStandards.length === 0 || assessmentLoading}
                          className="btn btn-primary"
                          style={{
                            padding: "14px 24px",
                            fontSize: "1rem",
                            opacity: selectedStandards.length === 0 ? 0.5 : 1,
                          }}
                        >
                          {assessmentLoading ? (
                            <>
                              <Icon name="Loader2" size={20} className="spin" />
                              Generating Assessment...
                            </>
                          ) : (
                            <>
                              <Icon name="Sparkles" size={20} />
                              Generate Assessment
                            </>
                          )}
                        </button>
                      </div>

                      {/* Main Content Area */}
                      <div
                        style={{
                          display: "flex",
                          flexDirection: "column",
                          gap: "20px",
                        }}
                      >
                        {/* Content Sources Panel */}
                        <div className="glass-card" style={{ padding: "20px" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "15px" }}>
                            <div>
                              <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "5px", display: "flex", alignItems: "center", gap: "10px" }}>
                                <Icon name="BookOpen" size={20} />
                                Content Sources
                              </h3>
                              <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                                Select lessons and assignments to generate questions from your actual instruction
                              </p>
                            </div>
                            <button
                              onClick={fetchSavedLessons}
                              className="btn btn-secondary"
                              style={{ padding: "6px 12px" }}
                            >
                              <Icon name="RefreshCw" size={14} />
                            </button>
                          </div>

                          {Object.keys(savedLessons.units || {}).length === 0 ? (
                            <div style={{
                              padding: "20px",
                              background: "rgba(255,255,255,0.03)",
                              borderRadius: "10px",
                              textAlign: "center"
                            }}>
                              <Icon name="FolderOpen" size={24} style={{ color: "var(--text-muted)", marginBottom: "10px" }} />
                              <p style={{ color: "var(--text-secondary)", marginBottom: "10px" }}>
                                No saved lessons yet
                              </p>
                              <p style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                                Save lessons from the Lesson Planner to use them here. Saved assignments from the Assignment Builder will also appear below.
                              </p>
                            </div>
                          ) : (
                            <div style={{ display: "flex", flexDirection: "column", gap: "15px" }}>
                              {Object.entries(savedLessons.units).map(([unitName, lessons]) => (
                                <div key={unitName}>
                                  <h4 style={{
                                    fontSize: "0.9rem",
                                    fontWeight: 600,
                                    marginBottom: "10px",
                                    color: "var(--primary)"
                                  }}>
                                    {unitName}
                                  </h4>
                                  <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                                    {lessons.map((lesson) => {
                                      const isSelected = selectedSources.some(
                                        s => s.type === 'lesson' && s.unit === unitName && s.filename === lesson.filename
                                      );
                                      return (
                                        <button
                                          key={lesson.filename}
                                          onClick={async () => {
                                            if (isSelected) {
                                              setSelectedSources(selectedSources.filter(
                                                s => !(s.type === 'lesson' && s.unit === unitName && s.filename === lesson.filename)
                                              ));
                                            } else {
                                              // Load full lesson content
                                              const data = await api.loadLesson(unitName, lesson.filename);
                                              if (data.lesson) {
                                                setSelectedSources([...selectedSources, {
                                                  type: 'lesson',
                                                  unit: unitName,
                                                  filename: lesson.filename,
                                                  title: lesson.title,
                                                  content: data.lesson
                                                }]);
                                              }
                                            }
                                          }}
                                          style={{
                                            padding: "8px 14px",
                                            borderRadius: "8px",
                                            border: isSelected ? "2px solid var(--primary)" : "1px solid var(--glass-border)",
                                            background: isSelected ? "rgba(99, 102, 241, 0.2)" : "rgba(255,255,255,0.05)",
                                            color: isSelected ? "var(--primary)" : "var(--text-primary)",
                                            cursor: "pointer",
                                            fontSize: "0.85rem",
                                            display: "flex",
                                            alignItems: "center",
                                            gap: "6px"
                                          }}
                                        >
                                          <Icon name={isSelected ? "CheckCircle" : "FileText"} size={14} />
                                          {lesson.title}
                                        </button>
                                      );
                                    })}
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}

                          {/* Saved Assignments Section */}
                          {savedAssignments.length > 0 && (
                            <div style={{ marginTop: "20px", paddingTop: "15px", borderTop: "1px solid var(--glass-border)" }}>
                              <h4 style={{
                                fontSize: "0.9rem",
                                fontWeight: 600,
                                marginBottom: "10px",
                                color: "var(--accent-primary)",
                                display: "flex",
                                alignItems: "center",
                                gap: "8px"
                              }}>
                                <Icon name="ClipboardList" size={16} />
                                Saved Assignments
                              </h4>
                              <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                                {savedAssignments.map((assignmentName) => {
                                  const isSelected = selectedSources.some(
                                    s => s.type === 'assignment' && s.filename === assignmentName
                                  );
                                  return (
                                    <button
                                      key={assignmentName}
                                      onClick={async () => {
                                        if (isSelected) {
                                          setSelectedSources(selectedSources.filter(
                                            s => !(s.type === 'assignment' && s.filename === assignmentName)
                                          ));
                                        } else {
                                          // Load full assignment content
                                          const data = await api.loadAssignment(assignmentName);
                                          if (data.assignment) {
                                            setSelectedSources([...selectedSources, {
                                              type: 'assignment',
                                              filename: assignmentName,
                                              title: data.assignment.title || assignmentName,
                                              content: data.assignment
                                            }]);
                                          }
                                        }
                                      }}
                                      style={{
                                        padding: "8px 14px",
                                        borderRadius: "8px",
                                        border: isSelected ? "2px solid var(--accent-primary)" : "1px solid var(--glass-border)",
                                        background: isSelected ? "rgba(251, 191, 36, 0.2)" : "rgba(255,255,255,0.05)",
                                        color: isSelected ? "var(--accent-primary)" : "var(--text-primary)",
                                        cursor: "pointer",
                                        fontSize: "0.85rem",
                                        display: "flex",
                                        alignItems: "center",
                                        gap: "6px"
                                      }}
                                    >
                                      <Icon name={isSelected ? "CheckCircle" : "FileText"} size={14} />
                                      {savedAssignmentData[assignmentName]?.title || assignmentName}
                                    </button>
                                  );
                                })}
                              </div>
                            </div>
                          )}

                          {selectedSources.length > 0 && (
                            <div style={{
                              marginTop: "15px",
                              padding: "10px 15px",
                              background: "rgba(34, 197, 94, 0.1)",
                              borderRadius: "8px",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "space-between"
                            }}>
                              <span style={{ color: "#22c55e", fontSize: "0.9rem", display: "flex", alignItems: "center", gap: "6px" }}>
                                <Icon name="Check" size={16} />
                                {selectedSources.length} source{selectedSources.length > 1 ? 's' : ''} selected - questions will be based on this content
                              </span>
                              <button
                                onClick={() => setSelectedSources([])}
                                style={{
                                  background: "none",
                                  border: "none",
                                  color: "var(--text-muted)",
                                  cursor: "pointer",
                                  fontSize: "0.85rem"
                                }}
                              >
                                Clear
                              </button>
                            </div>
                          )}
                        </div>

                        {/* Standards Selection */}
                        <div className="glass-card" style={{ padding: "20px" }}>
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
                              <Icon name="Target" size={20} />
                              Select Standards ({selectedStandards.length} selected)
                            </h3>
                            {selectedStandards.length > 0 && (
                              <button
                                onClick={() => setSelectedStandards([])}
                                className="btn btn-secondary"
                                style={{ padding: "6px 12px", fontSize: "0.85rem" }}
                              >
                                Clear All
                              </button>
                            )}
                          </div>
                          <div
                            style={{
                              maxHeight: "300px",
                              overflowY: "auto",
                              display: "flex",
                              flexDirection: "column",
                              gap: "8px",
                            }}
                          >
                            {plannerLoading ? (
                              <div style={{ textAlign: "center", padding: "20px" }}>
                                <Icon name="Loader2" size={24} className="spin" />
                                <p style={{ marginTop: "10px" }}>Loading standards...</p>
                              </div>
                            ) : standards.length > 0 ? (
                              standards.map((std) => (
                                <div
                                  key={std.code}
                                  onClick={() => toggleStandard(std.code)}
                                  style={{
                                    padding: "12px 15px",
                                    background: selectedStandards.includes(std.code)
                                      ? "rgba(139, 92, 246, 0.15)"
                                      : "var(--glass-bg)",
                                    border: selectedStandards.includes(std.code)
                                      ? "1px solid rgba(139, 92, 246, 0.4)"
                                      : "1px solid var(--glass-border)",
                                    borderRadius: "10px",
                                    cursor: "pointer",
                                    transition: "all 0.2s",
                                  }}
                                >
                                  <div
                                    style={{
                                      display: "flex",
                                      alignItems: "flex-start",
                                      gap: "12px",
                                    }}
                                  >
                                    <div
                                      style={{
                                        width: "20px",
                                        height: "20px",
                                        borderRadius: "6px",
                                        border: selectedStandards.includes(std.code)
                                          ? "none"
                                          : "2px solid var(--glass-border)",
                                        background: selectedStandards.includes(std.code)
                                          ? "linear-gradient(135deg, #8b5cf6, #6366f1)"
                                          : "transparent",
                                        display: "flex",
                                        alignItems: "center",
                                        justifyContent: "center",
                                        flexShrink: 0,
                                        marginTop: "2px",
                                      }}
                                    >
                                      {selectedStandards.includes(std.code) && (
                                        <Icon name="Check" size={14} style={{ color: "#fff" }} />
                                      )}
                                    </div>
                                    <div style={{ flex: 1 }}>
                                      <div
                                        style={{
                                          display: "flex",
                                          alignItems: "center",
                                          gap: "10px",
                                          marginBottom: "4px",
                                        }}
                                      >
                                        <span style={{ fontWeight: 700, color: "var(--accent-primary)" }}>
                                          {std.code}
                                        </span>
                                        <span
                                          style={{
                                            padding: "2px 8px",
                                            borderRadius: "12px",
                                            fontSize: "0.75rem",
                                            fontWeight: 600,
                                            background:
                                              std.dok === 1
                                                ? "rgba(34, 197, 94, 0.15)"
                                                : std.dok === 2
                                                  ? "rgba(59, 130, 246, 0.15)"
                                                  : std.dok === 3
                                                    ? "rgba(245, 158, 11, 0.15)"
                                                    : "rgba(239, 68, 68, 0.15)",
                                            color:
                                              std.dok === 1
                                                ? "#22c55e"
                                                : std.dok === 2
                                                  ? "#3b82f6"
                                                  : std.dok === 3
                                                    ? "#f59e0b"
                                                    : "#ef4444",
                                          }}
                                        >
                                          DOK {std.dok}
                                        </span>
                                      </div>
                                      <p
                                        style={{
                                          fontSize: "0.85rem",
                                          color: "var(--text-secondary)",
                                          margin: 0,
                                          lineHeight: 1.4,
                                        }}
                                      >
                                        {std.benchmark.length > 150
                                          ? std.benchmark.slice(0, 150) + "..."
                                          : std.benchmark}
                                      </p>
                                    </div>
                                  </div>
                                </div>
                              ))
                            ) : (
                              <div style={{ textAlign: "center", padding: "30px" }}>
                                <Icon
                                  name="FileQuestion"
                                  size={40}
                                  style={{ color: "var(--text-muted)", marginBottom: "10px" }}
                                />
                                <p style={{ color: "var(--text-secondary)" }}>
                                  No standards found. Check your grade and subject in Settings.
                                </p>
                              </div>
                            )}
                          </div>
                        </div>

                        {/* Generated Assessment Preview */}
                        {generatedAssessment && (
                          <div className="glass-card" style={{ padding: "25px" }}>
                            <div
                              style={{
                                display: "flex",
                                justifyContent: "space-between",
                                alignItems: "flex-start",
                                marginBottom: "20px",
                              }}
                            >
                              <div>
                                <h2
                                  style={{
                                    fontSize: "1.4rem",
                                    fontWeight: 700,
                                    marginBottom: "8px",
                                  }}
                                >
                                  {generatedAssessment.title}
                                </h2>
                                <div
                                  style={{
                                    display: "flex",
                                    gap: "15px",
                                    fontSize: "0.9rem",
                                    color: "var(--text-secondary)",
                                  }}
                                >
                                  <span>{generatedAssessment.total_points} points</span>
                                  <span>{generatedAssessment.time_estimate}</span>
                                  <span>
                                    {generatedAssessment.sections?.reduce(
                                      (sum, s) => sum + (s.questions?.length || 0),
                                      0
                                    )}{" "}
                                    questions
                                  </span>
                                </div>
                              </div>
                              <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
                                <button
                                  onClick={() => {
                                    setGeneratedAssessment(null);
                                    setAssessmentAnswers({});
                                    setSelectedSources([]);
                                  }}
                                  className="btn"
                                  style={{
                                    padding: "8px 16px",
                                    background: "rgba(239, 68, 68, 0.2)",
                                    border: "1px solid rgba(239, 68, 68, 0.3)"
                                  }}
                                  title="Clear assessment and start over"
                                >
                                  <Icon name="X" size={16} />
                                  Clear
                                </button>
                                <button
                                  onClick={() => exportAssessmentHandler(false)}
                                  className="btn btn-secondary"
                                  style={{ padding: "8px 16px" }}
                                >
                                  <Icon name="FileText" size={16} />
                                  Word Doc
                                </button>
                                <button
                                  onClick={() => exportAssessmentHandler(true)}
                                  className="btn btn-secondary"
                                  style={{ padding: "8px 16px" }}
                                >
                                  <Icon name="Key" size={16} />
                                  With Answer Key
                                </button>
                                <button
                                  onClick={gradeAssessmentAnswersHandler}
                                  disabled={gradingAssessment || Object.keys(assessmentAnswers).length === 0}
                                  className="btn"
                                  style={{
                                    padding: "8px 16px",
                                    background: Object.keys(assessmentAnswers).length > 0 ? "linear-gradient(135deg, #22c55e, #16a34a)" : "rgba(255,255,255,0.1)",
                                    opacity: Object.keys(assessmentAnswers).length === 0 ? 0.5 : 1,
                                  }}
                                >
                                  <Icon name={gradingAssessment ? "Loader" : "CheckCircle"} size={16} />
                                  {gradingAssessment ? "Grading..." : "Grade My Answers"}
                                </button>
                                <div style={{ position: "relative" }}>
                                  <button
                                    onClick={() => setShowPlatformExport(!showPlatformExport)}
                                    className="btn btn-primary"
                                    style={{ padding: "8px 16px" }}
                                  >
                                    <Icon name="Upload" size={16} />
                                    Export to Platform
                                    <Icon name="ChevronDown" size={14} style={{ marginLeft: "4px" }} />
                                  </button>
                                  {showPlatformExport && (
                                    <div
                                      style={{
                                        position: "absolute",
                                        top: "100%",
                                        right: 0,
                                        marginTop: "5px",
                                        background: "var(--surface)",
                                        border: "1px solid var(--glass-border)",
                                        borderRadius: "10px",
                                        boxShadow: "0 10px 40px rgba(0,0,0,0.3)",
                                        zIndex: 100,
                                        minWidth: "200px",
                                        overflow: "hidden",
                                      }}
                                    >
                                      {[
                                        { id: "wayground", name: "Wayground", icon: "FileSpreadsheet" },
                                        { id: "csv", name: "CSV (Generic)", icon: "Table" },
                                        { id: "canvas_qti", name: "Canvas (QTI)", icon: "GraduationCap" },
                                        { id: "kahoot", name: "Kahoot", icon: "Gamepad2" },
                                        { id: "quizlet", name: "Quizlet", icon: "BookOpen" },
                                        { id: "google_forms", name: "Google Forms", icon: "FormInput" },
                                      ].map((platform) => (
                                        <button
                                          key={platform.id}
                                          onClick={() => {
                                            exportAssessmentForPlatformHandler(platform.id);
                                            setShowPlatformExport(false);
                                          }}
                                          style={{
                                            display: "flex",
                                            alignItems: "center",
                                            gap: "10px",
                                            width: "100%",
                                            padding: "12px 16px",
                                            background: "transparent",
                                            border: "none",
                                            borderBottom: "1px solid var(--glass-border)",
                                            color: "var(--text-primary)",
                                            cursor: "pointer",
                                            textAlign: "left",
                                            fontSize: "0.9rem",
                                          }}
                                          onMouseEnter={(e) => e.target.style.background = "var(--glass-hover)"}
                                          onMouseLeave={(e) => e.target.style.background = "transparent"}
                                        >
                                          <Icon name={platform.icon} size={18} />
                                          {platform.name}
                                        </button>
                                      ))}
                                    </div>
                                  )}
                                </div>
                                <button
                                  onClick={publishAssessmentHandler}
                                  disabled={publishingAssessment}
                                  className="btn"
                                  style={{
                                    padding: "8px 16px",
                                    background: "linear-gradient(135deg, #8b5cf6, #6366f1)",
                                  }}
                                >
                                  <Icon name={publishingAssessment ? "Loader" : "Share2"} size={16} />
                                  {publishingAssessment ? "Publishing..." : "Publish to Portal"}
                                </button>
                              </div>
                            </div>

                            {/* Save Assessment Section */}
                            <div
                              style={{
                                display: "flex",
                                alignItems: "center",
                                gap: "10px",
                                marginBottom: "20px",
                                padding: "15px",
                                background: "var(--glass-bg)",
                                borderRadius: "10px",
                              }}
                            >
                              <Icon name="Save" size={20} style={{ color: "var(--accent-secondary)" }} />
                              <input
                                type="text"
                                placeholder="Assessment name..."
                                value={saveAssessmentName}
                                onChange={(e) => setSaveAssessmentName(e.target.value)}
                                style={{
                                  flex: 1,
                                  padding: "8px 12px",
                                  borderRadius: "6px",
                                  border: "1px solid var(--glass-border)",
                                  background: "var(--surface)",
                                  color: "var(--text-primary)",
                                  fontSize: "0.9rem",
                                }}
                              />
                              <button
                                onClick={saveAssessmentHandler}
                                disabled={savingAssessment || !saveAssessmentName.trim()}
                                className="btn btn-secondary"
                                style={{ padding: "8px 16px" }}
                              >
                                <Icon name={savingAssessment ? "Loader" : "Save"} size={16} />
                                {savingAssessment ? "Saving..." : "Save for Later"}
                              </button>
                            </div>

                            {/* DOK Summary */}
                            {generatedAssessment.dok_summary && (
                              <div
                                style={{
                                  display: "flex",
                                  gap: "15px",
                                  marginBottom: "20px",
                                  padding: "15px",
                                  background: "var(--glass-bg)",
                                  borderRadius: "10px",
                                }}
                              >
                                {[
                                  { level: 1, color: "#22c55e", label: "DOK 1" },
                                  { level: 2, color: "#3b82f6", label: "DOK 2" },
                                  { level: 3, color: "#f59e0b", label: "DOK 3" },
                                  { level: 4, color: "#ef4444", label: "DOK 4" },
                                ].map((dok) => (
                                  <div
                                    key={dok.level}
                                    style={{
                                      display: "flex",
                                      alignItems: "center",
                                      gap: "8px",
                                    }}
                                  >
                                    <span
                                      style={{
                                        width: "10px",
                                        height: "10px",
                                        borderRadius: "50%",
                                        background: dok.color,
                                      }}
                                    />
                                    <span style={{ fontSize: "0.85rem" }}>
                                      {dok.label}:{" "}
                                      {generatedAssessment.dok_summary[`dok_${dok.level}_count`] || 0}
                                    </span>
                                  </div>
                                ))}
                              </div>
                            )}

                            {/* Instructions */}
                            {generatedAssessment.instructions && (
                              <div
                                style={{
                                  padding: "15px",
                                  background: "rgba(99, 102, 241, 0.1)",
                                  borderRadius: "10px",
                                  marginBottom: "20px",
                                }}
                              >
                                <strong>Instructions:</strong> {generatedAssessment.instructions}
                              </div>
                            )}

                            {/* Sections */}
                            {generatedAssessment.sections?.map((section, sIdx) => (
                              <div key={sIdx} style={{ marginBottom: "25px" }}>
                                <h4
                                  style={{
                                    fontSize: "1.1rem",
                                    fontWeight: 700,
                                    marginBottom: "10px",
                                    color: "var(--accent-primary)",
                                  }}
                                >
                                  {section.name}
                                </h4>
                                {section.instructions && (
                                  <p
                                    style={{
                                      fontSize: "0.9rem",
                                      color: "var(--text-secondary)",
                                      marginBottom: "15px",
                                      fontStyle: "italic",
                                    }}
                                  >
                                    {section.instructions}
                                  </p>
                                )}
                                <div
                                  style={{
                                    display: "flex",
                                    flexDirection: "column",
                                    gap: "12px",
                                  }}
                                >
                                  {section.questions?.map((q, qIdx) => (
                                    <div
                                      key={qIdx}
                                      style={{
                                        padding: "15px",
                                        background: "var(--glass-bg)",
                                        borderRadius: "10px",
                                        borderLeft: `4px solid ${
                                          q.dok === 1
                                            ? "#22c55e"
                                            : q.dok === 2
                                              ? "#3b82f6"
                                              : q.dok === 3
                                                ? "#f59e0b"
                                                : "#ef4444"
                                        }`,
                                      }}
                                    >
                                      <div
                                        style={{
                                          display: "flex",
                                          justifyContent: "space-between",
                                          marginBottom: "8px",
                                        }}
                                      >
                                        <span style={{ fontWeight: 700 }}>
                                          {q.number}. {q.question}
                                        </span>
                                        <div
                                          style={{
                                            display: "flex",
                                            gap: "8px",
                                            fontSize: "0.75rem",
                                            flexWrap: "wrap",
                                          }}
                                        >
                                          {q.type && (
                                            <span
                                              style={{
                                                padding: "2px 8px",
                                                borderRadius: "8px",
                                                background: "rgba(100, 116, 139, 0.15)",
                                                color: "#94a3b8",
                                                textTransform: "capitalize",
                                              }}
                                            >
                                              {q.type.replace(/_/g, " ")}
                                            </span>
                                          )}
                                          <span
                                            style={{
                                              padding: "2px 8px",
                                              borderRadius: "8px",
                                              background: "rgba(139, 92, 246, 0.15)",
                                              color: "#8b5cf6",
                                            }}
                                          >
                                            {q.points} pt{q.points > 1 ? "s" : ""}
                                          </span>
                                          <span
                                            style={{
                                              padding: "2px 8px",
                                              borderRadius: "8px",
                                              background:
                                                q.dok === 1
                                                  ? "rgba(34, 197, 94, 0.15)"
                                                  : q.dok === 2
                                                    ? "rgba(59, 130, 246, 0.15)"
                                                    : q.dok === 3
                                                      ? "rgba(245, 158, 11, 0.15)"
                                                      : "rgba(239, 68, 68, 0.15)",
                                              color:
                                                q.dok === 1
                                                  ? "#22c55e"
                                                  : q.dok === 2
                                                    ? "#3b82f6"
                                                    : q.dok === 3
                                                      ? "#f59e0b"
                                                      : "#ef4444",
                                            }}
                                          >
                                            DOK {q.dok}
                                          </span>
                                        </div>
                                      </div>
                                      {/* Multiple Choice Options - Interactive */}
                                      {q.options && q.options.length > 0 && (
                                        <div
                                          style={{
                                            display: "flex",
                                            flexDirection: "column",
                                            gap: "8px",
                                            marginTop: "12px",
                                            paddingLeft: "15px",
                                          }}
                                        >
                                          {q.options.map((opt, oIdx) => {
                                            const answerKey = `${sIdx}-${qIdx}`;
                                            const isSelected = assessmentAnswers[answerKey] === oIdx;
                                            return (
                                              <label
                                                key={oIdx}
                                                onClick={() => setAssessmentAnswers({...assessmentAnswers, [answerKey]: oIdx})}
                                                style={{
                                                  display: "flex",
                                                  alignItems: "center",
                                                  gap: "10px",
                                                  padding: "10px 12px",
                                                  borderRadius: "8px",
                                                  cursor: "pointer",
                                                  background: isSelected ? "rgba(99, 102, 241, 0.2)" : "rgba(255,255,255,0.03)",
                                                  border: isSelected ? "2px solid var(--accent-primary)" : "2px solid transparent",
                                                  transition: "all 0.15s ease",
                                                }}
                                              >
                                                <span style={{
                                                  width: "20px",
                                                  height: "20px",
                                                  borderRadius: "50%",
                                                  border: isSelected ? "6px solid var(--accent-primary)" : "2px solid var(--text-muted)",
                                                  background: isSelected ? "white" : "transparent",
                                                  flexShrink: 0,
                                                }}></span>
                                                <span style={{ fontSize: "0.9rem", color: isSelected ? "white" : "var(--text-secondary)" }}>{opt}</span>
                                              </label>
                                            );
                                          })}
                                        </div>
                                      )}
                                      {/* True/False Options - Interactive */}
                                      {q.type === "true_false" && (
                                        <div
                                          style={{
                                            display: "flex",
                                            gap: "15px",
                                            marginTop: "12px",
                                            paddingLeft: "15px",
                                          }}
                                        >
                                          {["True", "False"].map((tf) => {
                                            const answerKey = `${sIdx}-${qIdx}`;
                                            const isSelected = assessmentAnswers[answerKey] === tf;
                                            return (
                                              <label
                                                key={tf}
                                                onClick={() => setAssessmentAnswers({...assessmentAnswers, [answerKey]: tf})}
                                                style={{
                                                  display: "flex",
                                                  alignItems: "center",
                                                  gap: "10px",
                                                  padding: "12px 24px",
                                                  borderRadius: "8px",
                                                  cursor: "pointer",
                                                  background: isSelected ? (tf === "True" ? "rgba(34, 197, 94, 0.2)" : "rgba(239, 68, 68, 0.2)") : "rgba(255,255,255,0.03)",
                                                  border: isSelected ? `2px solid ${tf === "True" ? "#22c55e" : "#ef4444"}` : "2px solid var(--text-muted)",
                                                  transition: "all 0.15s ease",
                                                }}
                                              >
                                                <span style={{
                                                  width: "20px",
                                                  height: "20px",
                                                  borderRadius: "50%",
                                                  border: isSelected ? `6px solid ${tf === "True" ? "#22c55e" : "#ef4444"}` : "2px solid var(--text-muted)",
                                                  background: isSelected ? "white" : "transparent",
                                                  flexShrink: 0,
                                                }}></span>
                                                <span style={{ fontSize: "0.95rem", fontWeight: 600, color: isSelected ? (tf === "True" ? "#22c55e" : "#ef4444") : "var(--text-secondary)" }}>{tf}</span>
                                              </label>
                                            );
                                          })}
                                        </div>
                                      )}
                                      {/* Matching - Interactive with dropdowns */}
                                      {q.type === "matching" && q.terms && q.definitions && (
                                        <div
                                          style={{
                                            display: "grid",
                                            gridTemplateColumns: "1fr 1fr",
                                            gap: "20px",
                                            marginTop: "12px",
                                            padding: "15px",
                                            background: "rgba(0,0,0,0.1)",
                                            borderRadius: "10px",
                                          }}
                                        >
                                          <div>
                                            <div style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: "10px", color: "var(--accent-primary)", display: "flex", alignItems: "center", gap: "6px" }}>
                                              <Icon name="List" size={14} /> Terms - Select matching letter
                                            </div>
                                            {q.terms.map((term, tIdx) => {
                                              const answerKey = `${sIdx}-${qIdx}-match-${tIdx}`;
                                              const selectedValue = assessmentAnswers[answerKey] || "";
                                              return (
                                                <div
                                                  key={tIdx}
                                                  style={{
                                                    padding: "10px 12px",
                                                    marginBottom: "8px",
                                                    background: selectedValue ? "rgba(99, 102, 241, 0.15)" : "rgba(99, 102, 241, 0.05)",
                                                    borderRadius: "8px",
                                                    fontSize: "0.9rem",
                                                    display: "flex",
                                                    alignItems: "center",
                                                    gap: "10px",
                                                    border: selectedValue ? "1px solid var(--accent-primary)" : "1px solid transparent",
                                                  }}
                                                >
                                                  <span style={{ fontWeight: 700, color: "var(--accent-primary)", minWidth: "20px" }}>{tIdx + 1}.</span>
                                                  <span style={{ flex: 1 }}>{term}</span>
                                                  <select
                                                    value={selectedValue}
                                                    onChange={(e) => setAssessmentAnswers({...assessmentAnswers, [answerKey]: e.target.value})}
                                                    style={{
                                                      padding: "6px 10px",
                                                      borderRadius: "6px",
                                                      border: "1px solid var(--text-muted)",
                                                      background: "var(--glass-bg)",
                                                      color: "white",
                                                      fontSize: "0.9rem",
                                                      fontWeight: 600,
                                                      cursor: "pointer",
                                                      minWidth: "50px",
                                                    }}
                                                  >
                                                    <option value="">--</option>
                                                    {q.definitions.map((_, dIdx) => (
                                                      <option key={dIdx} value={String.fromCharCode(65 + dIdx)}>{String.fromCharCode(65 + dIdx)}</option>
                                                    ))}
                                                  </select>
                                                </div>
                                              );
                                            })}
                                          </div>
                                          <div>
                                            <div style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: "10px", color: "#22c55e", display: "flex", alignItems: "center", gap: "6px" }}>
                                              <Icon name="BookOpen" size={14} /> Definitions
                                            </div>
                                            {q.definitions.map((def, dIdx) => {
                                              // Check if this definition is selected
                                              const letter = String.fromCharCode(65 + dIdx);
                                              const isUsed = Object.entries(assessmentAnswers).some(([k, v]) => k.startsWith(`${sIdx}-${qIdx}-match-`) && v === letter);
                                              return (
                                                <div
                                                  key={dIdx}
                                                  style={{
                                                    padding: "10px 12px",
                                                    marginBottom: "8px",
                                                    background: isUsed ? "rgba(34, 197, 94, 0.15)" : "rgba(34, 197, 94, 0.05)",
                                                    borderRadius: "8px",
                                                    fontSize: "0.9rem",
                                                    display: "flex",
                                                    alignItems: "flex-start",
                                                    gap: "10px",
                                                    border: isUsed ? "1px solid #22c55e" : "1px solid transparent",
                                                    opacity: isUsed ? 0.7 : 1,
                                                  }}
                                                >
                                                  <span style={{ fontWeight: 700, color: "#22c55e", minWidth: "20px" }}>{letter}.</span>
                                                  <span>{def}</span>
                                                </div>
                                              );
                                            })}
                                          </div>
                                        </div>
                                      )}
                                      {/* Short Answer - Interactive text input */}
                                      {q.type === "short_answer" && !q.options && !q.terms && (
                                        <div style={{ marginTop: "12px", paddingLeft: "15px" }}>
                                          <textarea
                                            value={assessmentAnswers[`${sIdx}-${qIdx}`] || ""}
                                            onChange={(e) => setAssessmentAnswers({...assessmentAnswers, [`${sIdx}-${qIdx}`]: e.target.value})}
                                            placeholder="Type your answer here..."
                                            rows={3}
                                            style={{
                                              width: "100%",
                                              padding: "12px",
                                              borderRadius: "8px",
                                              border: "1px solid var(--text-muted)",
                                              background: "rgba(255,255,255,0.03)",
                                              color: "white",
                                              fontSize: "0.9rem",
                                              resize: "vertical",
                                              fontFamily: "inherit",
                                            }}
                                          />
                                        </div>
                                      )}
                                      {/* Extended Response - Interactive textarea */}
                                      {q.type === "extended_response" && !q.options && !q.terms && (
                                        <div style={{ marginTop: "12px", paddingLeft: "15px" }}>
                                          {q.rubric && (
                                            <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "10px", padding: "8px 12px", background: "rgba(245, 158, 11, 0.1)", borderRadius: "6px", borderLeft: "3px solid #f59e0b" }}>
                                              <strong>Scoring Criteria:</strong> {q.rubric}
                                            </div>
                                          )}
                                          <textarea
                                            value={assessmentAnswers[`${sIdx}-${qIdx}`] || ""}
                                            onChange={(e) => setAssessmentAnswers({...assessmentAnswers, [`${sIdx}-${qIdx}`]: e.target.value})}
                                            placeholder="Write your extended response here. Be sure to include evidence and analysis to support your answer..."
                                            rows={6}
                                            style={{
                                              width: "100%",
                                              padding: "15px",
                                              borderRadius: "8px",
                                              border: "1px solid var(--text-muted)",
                                              background: "rgba(255,255,255,0.03)",
                                              color: "white",
                                              fontSize: "0.9rem",
                                              resize: "vertical",
                                              fontFamily: "inherit",
                                              lineHeight: 1.6,
                                            }}
                                          />
                                          <div style={{ marginTop: "6px", fontSize: "0.8rem", color: "var(--text-muted)", textAlign: "right" }}>
                                            {(assessmentAnswers[`${sIdx}-${qIdx}`] || "").split(/\s+/).filter(w => w).length} words
                                          </div>
                                        </div>
                                      )}
                                      {q.standard && (
                                        <div
                                          style={{
                                            marginTop: "8px",
                                            fontSize: "0.8rem",
                                            color: "var(--text-muted)",
                                          }}
                                        >
                                          Standard: {q.standard}
                                        </div>
                                      )}
                                    </div>
                                  ))}
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Student Portal Dashboard */}
                  {plannerMode === "dashboard" && (
                    <div className="fade-in">
                      <div style={{ display: "grid", gridTemplateColumns: selectedAssessmentResults ? "1fr 1fr" : "1fr", gap: "25px" }}>
                        {/* Published Assessments List */}
                        <div className="glass-card" style={{ padding: "20px" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
                            <h3 style={{ fontSize: "1.1rem", fontWeight: 700, display: "flex", alignItems: "center", gap: "10px" }}>
                              <Icon name="ClipboardList" size={20} />
                              Published Assessments
                            </h3>
                            <button
                              onClick={fetchPublishedAssessments}
                              className="btn"
                              style={{ padding: "8px 12px", fontSize: "0.85rem" }}
                              disabled={loadingPublished}
                            >
                              <Icon name={loadingPublished ? "Loader2" : "RefreshCw"} size={16} className={loadingPublished ? "spin" : ""} />
                              Refresh
                            </button>
                          </div>

                          {loadingPublished ? (
                            <div style={{ textAlign: "center", padding: "40px", color: "var(--text-secondary)" }}>
                              <Icon name="Loader2" size={32} className="spin" />
                              <p style={{ marginTop: "10px" }}>Loading assessments...</p>
                            </div>
                          ) : publishedAssessments.length === 0 ? (
                            <div style={{ textAlign: "center", padding: "40px", color: "var(--text-secondary)" }}>
                              <Icon name="FileQuestion" size={48} style={{ opacity: 0.5, marginBottom: "15px" }} />
                              <p>No published assessments yet.</p>
                              <p style={{ fontSize: "0.9rem", marginTop: "5px" }}>Generate an assessment and click "Publish to Portal" to get started.</p>
                            </div>
                          ) : (
                            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                              {publishedAssessments.map((assessment) => (
                                <div
                                  key={assessment.join_code}
                                  style={{
                                    padding: "15px",
                                    background: selectedAssessmentResults?.joinCode === assessment.join_code
                                      ? "rgba(139, 92, 246, 0.2)"
                                      : "rgba(255,255,255,0.03)",
                                    borderRadius: "10px",
                                    border: selectedAssessmentResults?.joinCode === assessment.join_code
                                      ? "1px solid var(--accent-primary)"
                                      : "1px solid rgba(255,255,255,0.1)",
                                    cursor: "pointer",
                                    transition: "all 0.2s",
                                  }}
                                  onClick={() => fetchAssessmentResults(assessment.join_code)}
                                >
                                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                                    <div style={{ flex: 1 }}>
                                      <div style={{ fontWeight: 600, marginBottom: "5px" }}>{assessment.title}</div>
                                      <div style={{ display: "flex", alignItems: "center", gap: "15px", fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                                        <span style={{ display: "flex", alignItems: "center", gap: "5px" }}>
                                          <Icon name="Hash" size={14} />
                                          {assessment.join_code}
                                        </span>
                                        <span style={{ display: "flex", alignItems: "center", gap: "5px" }}>
                                          <Icon name="Users" size={14} />
                                          {assessment.submission_count || 0} submissions
                                        </span>
                                        {assessment.period && (
                                          <span style={{ display: "flex", alignItems: "center", gap: "5px" }}>
                                            <Icon name="Clock" size={14} />
                                            {assessment.period}
                                          </span>
                                        )}
                                      </div>
                                      {assessment.is_makeup && (
                                        <span
                                          style={{
                                            marginTop: "8px",
                                            padding: "3px 8px",
                                            background: "rgba(245, 158, 11, 0.2)",
                                            color: "#f59e0b",
                                            borderRadius: "4px",
                                            fontSize: "0.75rem",
                                            fontWeight: 600,
                                          }}
                                        >
                                          Makeup Exam
                                        </span>
                                      )}
                                    </div>
                                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                                      <span
                                        style={{
                                          padding: "4px 10px",
                                          borderRadius: "12px",
                                          fontSize: "0.75rem",
                                          fontWeight: 600,
                                          background: assessment.is_active ? "rgba(34, 197, 94, 0.2)" : "rgba(239, 68, 68, 0.2)",
                                          color: assessment.is_active ? "#22c55e" : "#ef4444",
                                        }}
                                      >
                                        {assessment.is_active ? "Active" : "Closed"}
                                      </span>
                                      <button
                                        onClick={(e) => { e.stopPropagation(); toggleAssessmentStatus(assessment.join_code); }}
                                        style={{ background: "none", border: "none", cursor: "pointer", padding: "5px" }}
                                        title={assessment.is_active ? "Deactivate" : "Activate"}
                                      >
                                        <Icon name={assessment.is_active ? "Pause" : "Play"} size={16} />
                                      </button>
                                      <button
                                        onClick={(e) => { e.stopPropagation(); deletePublishedAssessment(assessment.join_code); }}
                                        style={{ background: "none", border: "none", cursor: "pointer", padding: "5px", color: "#ef4444" }}
                                        title="Delete"
                                      >
                                        <Icon name="Trash2" size={16} />
                                      </button>
                                    </div>
                                  </div>
                                  <div style={{ marginTop: "8px", fontSize: "0.8rem", color: "var(--text-muted)" }}>
                                    Created: {new Date(assessment.created_at).toLocaleDateString()}
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>

                        {/* Submissions Detail Panel */}
                        {selectedAssessmentResults && (
                          <div className="glass-card" style={{ padding: "20px" }}>
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
                              <h3 style={{ fontSize: "1.1rem", fontWeight: 700, display: "flex", alignItems: "center", gap: "10px" }}>
                                <Icon name="BarChart3" size={20} />
                                {selectedAssessmentResults.title}
                              </h3>
                              <button
                                onClick={() => setSelectedAssessmentResults(null)}
                                style={{ background: "none", border: "none", cursor: "pointer", padding: "5px" }}
                              >
                                <Icon name="X" size={20} />
                              </button>
                            </div>

                            {/* Stats Summary */}
                            {selectedAssessmentResults.submissions.length > 0 && (
                              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "15px", marginBottom: "20px" }}>
                                <div style={{ padding: "15px", background: "rgba(34, 197, 94, 0.1)", borderRadius: "10px", textAlign: "center" }}>
                                  <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "#22c55e" }}>
                                    {selectedAssessmentResults.submissions.length}
                                  </div>
                                  <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>Submissions</div>
                                </div>
                                <div style={{ padding: "15px", background: "rgba(99, 102, 241, 0.1)", borderRadius: "10px", textAlign: "center" }}>
                                  <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "#6366f1" }}>
                                    {Math.round(selectedAssessmentResults.submissions.reduce((sum, s) => sum + (s.percentage || 0), 0) / selectedAssessmentResults.submissions.length)}%
                                  </div>
                                  <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>Avg Score</div>
                                </div>
                                <div style={{ padding: "15px", background: "rgba(245, 158, 11, 0.1)", borderRadius: "10px", textAlign: "center" }}>
                                  <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "#f59e0b" }}>
                                    {Math.max(...selectedAssessmentResults.submissions.map(s => s.percentage || 0))}%
                                  </div>
                                  <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>High Score</div>
                                </div>
                              </div>
                            )}

                            {/* Student Submissions List */}
                            {loadingResults ? (
                              <div style={{ textAlign: "center", padding: "40px", color: "var(--text-secondary)" }}>
                                <Icon name="Loader2" size={32} className="spin" />
                              </div>
                            ) : selectedAssessmentResults.submissions.length === 0 ? (
                              <div style={{ textAlign: "center", padding: "40px", color: "var(--text-secondary)" }}>
                                <Icon name="UserX" size={48} style={{ opacity: 0.5, marginBottom: "15px" }} />
                                <p>No submissions yet.</p>
                                <p style={{ fontSize: "0.9rem", marginTop: "5px" }}>
                                  Share code <strong>{selectedAssessmentResults.joinCode}</strong> with students.
                                </p>
                              </div>
                            ) : (
                              <div style={{ display: "flex", flexDirection: "column", gap: "10px", maxHeight: "400px", overflowY: "auto" }}>
                                {selectedAssessmentResults.submissions.map((submission, idx) => (
                                  <div
                                    key={idx}
                                    style={{
                                      padding: "12px 15px",
                                      background: "rgba(255,255,255,0.03)",
                                      borderRadius: "8px",
                                      border: "1px solid rgba(255,255,255,0.1)",
                                      display: "flex",
                                      justifyContent: "space-between",
                                      alignItems: "center",
                                    }}
                                  >
                                    <div>
                                      <div style={{ fontWeight: 600 }}>{submission.student_name}</div>
                                      <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                                        {new Date(submission.submitted_at).toLocaleString()}
                                        {submission.time_taken_seconds && (
                                          <span> · {Math.floor(submission.time_taken_seconds / 60)}m {submission.time_taken_seconds % 60}s</span>
                                        )}
                                      </div>
                                    </div>
                                    <div style={{ textAlign: "right" }}>
                                      <div style={{
                                        fontSize: "1.2rem",
                                        fontWeight: 700,
                                        color: submission.percentage >= 80 ? "#22c55e" : submission.percentage >= 60 ? "#f59e0b" : "#ef4444"
                                      }}>
                                        {submission.percentage?.toFixed(0) || 0}%
                                      </div>
                                      <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                                        {submission.score}/{submission.total_points} pts
                                      </div>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        )}
                      </div>

                      {/* Saved Assessments Section */}
                      <div className="glass-card" style={{ padding: "20px", marginTop: "25px" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
                          <h3 style={{ fontSize: "1.1rem", fontWeight: 700, display: "flex", alignItems: "center", gap: "10px" }}>
                            <Icon name="Archive" size={20} />
                            Saved Assessments
                          </h3>
                          <button
                            onClick={fetchSavedAssessments}
                            className="btn"
                            style={{ padding: "8px 12px", fontSize: "0.85rem" }}
                            disabled={loadingSavedAssessments}
                          >
                            <Icon name={loadingSavedAssessments ? "Loader2" : "RefreshCw"} size={16} className={loadingSavedAssessments ? "spin" : ""} />
                            Refresh
                          </button>
                        </div>

                        <p style={{ fontSize: "0.9rem", color: "var(--text-secondary)", marginBottom: "15px" }}>
                          Load a saved assessment to view, modify, or publish it for makeup exams.
                        </p>

                        {loadingSavedAssessments ? (
                          <div style={{ textAlign: "center", padding: "40px", color: "var(--text-secondary)" }}>
                            <Icon name="Loader2" size={32} className="spin" />
                            <p style={{ marginTop: "10px" }}>Loading saved assessments...</p>
                          </div>
                        ) : savedAssessments.length === 0 ? (
                          <div style={{ textAlign: "center", padding: "40px", color: "var(--text-secondary)" }}>
                            <Icon name="FolderOpen" size={48} style={{ opacity: 0.5, marginBottom: "15px" }} />
                            <p>No saved assessments.</p>
                            <p style={{ fontSize: "0.9rem", marginTop: "5px" }}>Generate an assessment and use "Save for Later" to save it.</p>
                          </div>
                        ) : (
                          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(250px, 1fr))", gap: "12px" }}>
                            {savedAssessments.map((assessment) => (
                              <div
                                key={assessment.filename}
                                style={{
                                  padding: "15px",
                                  background: "rgba(255,255,255,0.03)",
                                  borderRadius: "10px",
                                  border: "1px solid rgba(255,255,255,0.1)",
                                }}
                              >
                                <div style={{ fontWeight: 600, marginBottom: "8px" }}>{assessment.name}</div>
                                <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "10px" }}>
                                  <Icon name="FileText" size={14} />
                                  {assessment.question_count || '?'} questions
                                  <span>·</span>
                                  <Icon name="Target" size={14} />
                                  {assessment.total_points || '?'} pts
                                </div>
                                <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "12px" }}>
                                  Saved: {new Date(assessment.saved_at).toLocaleDateString()}
                                </div>
                                <div style={{ display: "flex", gap: "8px" }}>
                                  <button
                                    onClick={() => loadSavedAssessment(assessment.filename)}
                                    className="btn btn-primary"
                                    style={{ padding: "6px 12px", fontSize: "0.85rem", flex: 1 }}
                                  >
                                    <Icon name="Download" size={14} />
                                    Load
                                  </button>
                                  <button
                                    onClick={() => deleteSavedAssessment(assessment.filename)}
                                    className="btn"
                                    style={{ padding: "6px 10px", fontSize: "0.85rem", background: "rgba(239, 68, 68, 0.2)", color: "#ef4444" }}
                                    title="Delete"
                                  >
                                    <Icon name="Trash2" size={14} />
                                  </button>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Focus Export Modal */}
      {focusExportModal && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "rgba(0,0,0,0.7)",
            zIndex: 10000,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "20px",
          }}
        >
          <div
            style={{
              background: "#1a1a2e",
              borderRadius: "12px",
              width: "100%",
              maxWidth: "500px",
              padding: "25px",
              border: "1px solid rgba(255, 255, 255, 0.1)",
              boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)",
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
              <h2
                style={{
                  fontSize: "1.2rem",
                  fontWeight: 700,
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                }}
              >
                <Icon name="Download" size={24} />
                Export to Focus
              </h2>
              <button
                onClick={() => setFocusExportModal(false)}
                style={{
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  padding: "5px",
                }}
              >
                <Icon name="X" size={20} />
              </button>
            </div>

            <p
              style={{
                color: "var(--text-secondary)",
                marginBottom: "20px",
                fontSize: "0.9rem",
              }}
            >
              Generate a CSV file formatted for Focus SIS import with Student_ID
              and Score columns.
            </p>

            {/* Group results by assignment */}
            {(() => {
              const assignments = [
                ...new Set(
                  status.results.map((r) => r.assignment || "Unknown"),
                ),
              ];
              const periods = [
                ...new Set(status.results.map((r) => r.period || "All")),
              ];
              return (
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "15px",
                  }}
                >
                  <div>
                    <label className="label">Assignment</label>
                    <select
                      id="focus-assignment"
                      className="input"
                      defaultValue={assignments[0]}
                    >
                      {assignments.map((a) => (
                        <option key={a} value={a}>
                          {a}
                        </option>
                      ))}
                    </select>
                  </div>
                  {periods.length > 1 && (
                    <div>
                      <label className="label">Period</label>
                      <select
                        id="focus-period"
                        className="input"
                        defaultValue="all"
                      >
                        <option value="all">All Periods</option>
                        {periods
                          .filter((p) => p !== "All")
                          .map((p) => (
                            <option key={p} value={p}>
                              {p}
                            </option>
                          ))}
                      </select>
                    </div>
                  )}
                  <div
                    style={{
                      padding: "12px",
                      background: "var(--glass-bg)",
                      borderRadius: "8px",
                      fontSize: "0.85rem",
                      color: "var(--text-secondary)",
                    }}
                  >
                    <Icon
                      name="Info"
                      size={14}
                      style={{ marginRight: "6px", verticalAlign: "middle" }}
                    />
                    Students without a Student_ID will be matched by name using
                    Claude AI.
                  </div>
                  <button
                    onClick={async () => {
                      setFocusExportLoading(true);
                      try {
                        const assignment =
                          document.getElementById("focus-assignment")?.value;
                        const period =
                          document.getElementById("focus-period")?.value ||
                          "all";

                        // Filter results
                        let resultsToExport = status.results.filter(
                          (r) =>
                            (r.assignment || "Unknown") === assignment &&
                            (period === "all" ||
                              (r.period || "All") === period),
                        );

                        const response = await fetch("/api/export-focus-csv", {
                          method: "POST",
                          headers: { "Content-Type": "application/json" },
                          body: JSON.stringify({
                            results: resultsToExport,
                            assignment,
                            period,
                            periods: periods.map((p) => ({ name: p })),
                          }),
                        });

                        const data = await response.json();
                        if (data.csv) {
                          // Download the CSV
                          const blob = new Blob([data.csv], {
                            type: "text/csv",
                          });
                          const url = URL.createObjectURL(blob);
                          const a = document.createElement("a");
                          a.href = url;
                          a.download = data.filename || "focus_grades.csv";
                          document.body.appendChild(a);
                          a.click();
                          document.body.removeChild(a);
                          URL.revokeObjectURL(url);

                          addToast(
                            `Exported ${data.count} grades to ${data.filename}`,
                            "success",
                          );
                          setFocusExportModal(false);
                        } else {
                          addToast(data.error || "Export failed", "error");
                        }
                      } catch (err) {
                        addToast("Export error: " + err.message, "error");
                      } finally {
                        setFocusExportLoading(false);
                      }
                    }}
                    disabled={focusExportLoading || status.results.length === 0}
                    className="btn btn-primary"
                    style={{ width: "100%", marginTop: "10px" }}
                  >
                    {focusExportLoading ? (
                      <>
                        <Icon
                          name="Loader2"
                          size={18}
                          style={{ animation: "spin 1s linear infinite" }}
                        />
                        Generating CSV with Claude...
                      </>
                    ) : (
                      <>
                        <Icon name="Download" size={18} />
                        Download Focus CSV
                      </>
                    )}
                  </button>
                </div>
              );
            })()}
          </div>
        </div>
      )}

      {/* Curve Modal */}
      {curveModal.show && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "rgba(0,0,0,0.7)",
            zIndex: 10000,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "20px",
          }}
          onClick={() => setCurveModal({ ...curveModal, show: false })}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: "#1a1a2e",
              borderRadius: "12px",
              width: "100%",
              maxWidth: "400px",
              padding: "25px",
              border: "1px solid rgba(168, 85, 247, 0.3)",
              boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)",
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
              <h2
                style={{
                  fontSize: "1.2rem",
                  fontWeight: 700,
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                  color: "#a855f7",
                }}
              >
                <Icon name="TrendingUp" size={24} />
                Apply Grade Curve
              </h2>
              <button
                onClick={() => setCurveModal({ ...curveModal, show: false })}
                style={{
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  padding: "5px",
                  color: "var(--text-muted)",
                }}
              >
                <Icon name="X" size={20} />
              </button>
            </div>

            <p
              style={{
                color: "var(--text-secondary)",
                marginBottom: "20px",
                fontSize: "0.9rem",
              }}
            >
              Apply a curve to all{" "}
              <span style={{ color: "#a855f7", fontWeight: 600 }}>
                {resultsPeriodFilter}
              </span>{" "}
              results. This will update scores, letter grades, feedback, and emails.
            </p>

            <div style={{ display: "flex", flexDirection: "column", gap: "15px" }}>
              <div>
                <label className="label">Curve Type</label>
                <select
                  className="input"
                  value={curveModal.curveType}
                  onChange={(e) => setCurveModal({ ...curveModal, curveType: e.target.value })}
                  style={{ width: "100%" }}
                >
                  <option value="add">Add Points (e.g., +5 to every score)</option>
                  <option value="percent">Percentage Boost (e.g., +10% to every score)</option>
                  <option value="set_min">Set Minimum Score (e.g., min 50)</option>
                </select>
              </div>

              <div>
                <label className="label">
                  {curveModal.curveType === "add"
                    ? "Points to Add"
                    : curveModal.curveType === "percent"
                      ? "Percentage Boost"
                      : "Minimum Score"}
                </label>
                <input
                  type="number"
                  className="input"
                  value={curveModal.curveValue}
                  onChange={(e) => setCurveModal({ ...curveModal, curveValue: e.target.value })}
                  placeholder={
                    curveModal.curveType === "add"
                      ? "5"
                      : curveModal.curveType === "percent"
                        ? "10"
                        : "50"
                  }
                  style={{ width: "100%" }}
                />
                <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "5px" }}>
                  {curveModal.curveType === "add"
                    ? "Adds this many points to each score (capped at 100)"
                    : curveModal.curveType === "percent"
                      ? "Increases each score by this percentage"
                      : "Sets this as the minimum score for all results"}
                </p>
              </div>

              {/* Preview */}
              <div
                style={{
                  padding: "12px",
                  background: "rgba(168, 85, 247, 0.1)",
                  borderRadius: "8px",
                  border: "1px solid rgba(168, 85, 247, 0.2)",
                }}
              >
                <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "5px" }}>
                  Preview (example):
                </div>
                <div style={{ fontWeight: 600 }}>
                  {(() => {
                    const val = parseFloat(curveModal.curveValue) || 0;
                    const example = 75;
                    let newScore;
                    if (curveModal.curveType === "add") {
                      newScore = Math.min(100, example + val);
                    } else if (curveModal.curveType === "percent") {
                      newScore = Math.min(100, Math.round(example * (1 + val / 100)));
                    } else {
                      newScore = Math.max(val, example);
                    }
                    return `75% → ${newScore}%`;
                  })()}
                </div>
              </div>

              <div style={{ display: "flex", gap: "10px", marginTop: "10px" }}>
                <button
                  onClick={() => setCurveModal({ ...curveModal, show: false })}
                  className="btn btn-secondary"
                  style={{ flex: 1 }}
                >
                  Cancel
                </button>
                <button
                  onClick={applyCurve}
                  className="btn btn-primary"
                  style={{
                    flex: 1,
                    background: "linear-gradient(135deg, #a855f7, #8b5cf6)",
                  }}
                >
                  <Icon name="Check" size={18} />
                  Apply Curve
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Toast Notifications */}
      <div
        style={{
          position: "fixed",
          top: "20px",
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
              onClick={(e) => {
                e.stopPropagation();
                removeToast(toast.id);
              }}
              style={{
                background: "rgba(255,255,255,0.1)",
                border: "none",
                borderRadius: "4px",
                cursor: "pointer",
                padding: "4px 6px",
                color: "var(--text-secondary)",
                flexShrink: 0,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Icon name="X" size={16} />
            </button>
          </div>
        ))}
      </div>

      {/* Interactive Assignment Player Modal */}
      {showInteractivePreview && generatedAssignment && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "rgba(0,0,0,0.7)",
            zIndex: 10000,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "20px",
          }}
        >
          <div
            style={{
              background: "#1a1a2e",
              borderRadius: "12px",
              width: "100%",
              maxWidth: "900px",
              maxHeight: "90vh",
              overflow: "auto",
              border: "1px solid rgba(255, 255, 255, 0.1)",
              boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)",
            }}
          >
            <AssignmentPlayer
              assignment={generatedAssignment}
              onSubmit={async (answers) => {
                try {
                  const published =
                    await api.publishAssignment(generatedAssignment);
                  const result = await api.submitAssignment(
                    published.assignment_id,
                    answers,
                    "Teacher Preview",
                  );
                  setInteractiveResults(result.results);
                  addToast(
                    "Assignment graded! Score: " + result.results.percent + "%",
                    "success",
                  );
                } catch (err) {
                  addToast("Error grading: " + err.message, "error");
                }
              }}
              onClose={() => {
                setShowInteractivePreview(false);
                setInteractiveResults(null);
              }}
              results={interactiveResults}
            />
          </div>
        </div>
      )}

      {/* Save Lesson Modal */}
      {showSaveLesson && lessonPlan && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0, 0, 0, 0.8)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 9999,
            padding: "20px",
          }}
          onClick={() => setShowSaveLesson(false)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="glass-card"
            style={{ padding: "30px", width: "400px", maxWidth: "90vw" }}
          >
            <h3 style={{ fontSize: "1.3rem", fontWeight: 700, marginBottom: "20px", display: "flex", alignItems: "center", gap: "10px" }}>
              <Icon name="FolderPlus" size={24} style={{ color: "var(--primary)" }} />
              Save Lesson to Unit
            </h3>

            <p style={{ fontSize: "0.9rem", color: "var(--text-secondary)", marginBottom: "20px" }}>
              Save this lesson to use it as a content source when generating assessments.
            </p>

            <div style={{ marginBottom: "15px" }}>
              <label className="label">Select Existing Unit</label>
              <select
                className="input"
                value={saveLessonUnit}
                onChange={(e) => {
                  setSaveLessonUnit(e.target.value);
                  if (e.target.value) setNewUnitName('');
                }}
                style={{ width: "100%" }}
              >
                <option value="">-- Select or create new --</option>
                {savedUnits.map((unit) => (
                  <option key={unit} value={unit}>{unit}</option>
                ))}
              </select>
            </div>

            {!saveLessonUnit && (
              <div style={{ marginBottom: "20px" }}>
                <label className="label">Or Create New Unit</label>
                <input
                  type="text"
                  className="input"
                  placeholder="e.g., Unit 3 - Fractions"
                  value={newUnitName}
                  onChange={(e) => setNewUnitName(e.target.value)}
                  style={{ width: "100%" }}
                />
              </div>
            )}

            <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end" }}>
              <button
                onClick={() => {
                  setShowSaveLesson(false);
                  setSaveLessonUnit('');
                  setNewUnitName('');
                }}
                className="btn btn-secondary"
              >
                Cancel
              </button>
              <button
                onClick={async () => {
                  const unitName = saveLessonUnit || newUnitName;
                  if (!unitName) {
                    addToast('Please select or enter a unit name', 'error');
                    return;
                  }
                  try {
                    const result = await api.saveLessonPlan(lessonPlan, unitName);
                    if (result.error) {
                      addToast('Error: ' + result.error, 'error');
                    } else {
                      setShowSaveLesson(false);
                      setSaveLessonUnit('');
                      setNewUnitName('');
                      fetchSavedLessons();
                      addToast('Lesson saved to ' + unitName + '!', 'success');
                    }
                  } catch (err) {
                    addToast('Failed to save: ' + err.message, 'error');
                  }
                }}
                className="btn btn-primary"
                disabled={!saveLessonUnit && !newUnitName}
              >
                <Icon name="Save" size={16} />
                Save Lesson
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Publish Settings Modal - Period, Makeup, Student Selection */}
      {showPublishModal && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0, 0, 0, 0.8)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 9999,
            padding: "20px",
          }}
          onClick={() => setShowPublishModal(false)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: "#1a1a2e",
              borderRadius: "16px",
              padding: "30px",
              maxWidth: "600px",
              width: "100%",
              maxHeight: "80vh",
              overflowY: "auto",
              border: "1px solid rgba(255, 255, 255, 0.1)",
              boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)",
            }}
          >
            <h2 style={{ fontSize: "1.5rem", fontWeight: 700, marginBottom: "20px", display: "flex", alignItems: "center", gap: "10px" }}>
              <Icon name="Share2" size={24} style={{ color: "var(--accent-primary)" }} />
              Publish Assessment
            </h2>

            {/* Period Selection */}
            <div style={{ marginBottom: "20px" }}>
              <label style={{ display: "block", marginBottom: "8px", fontWeight: 600, fontSize: "0.95rem" }}>
                Period (Optional)
              </label>
              <select
                value={publishSettings.periodFilename}
                onChange={(e) => {
                  const filename = e.target.value;
                  const selectedPeriod = periods.find(p => p.filename === filename);
                  setPublishSettings({
                    ...publishSettings,
                    periodFilename: filename,
                    period: selectedPeriod ? selectedPeriod.period_name : '',
                    selectedStudents: [],
                  });
                  loadPublishModalStudents(filename);
                }}
                style={{
                  width: "100%",
                  padding: "10px 12px",
                  borderRadius: "8px",
                  border: "1px solid var(--glass-border)",
                  background: "var(--surface)",
                  color: "var(--text-primary)",
                  fontSize: "0.95rem",
                }}
              >
                <option value="">-- No Period (Open to All) --</option>
                {periods.map((p) => (
                  <option key={p.filename} value={p.filename}>{p.name}</option>
                ))}
              </select>
            </div>

            {/* Makeup Exam Toggle */}
            <div style={{ marginBottom: "20px" }}>
              <label
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                  cursor: "pointer",
                  padding: "12px 15px",
                  background: publishSettings.isMakeup ? "rgba(139, 92, 246, 0.2)" : "var(--glass-bg)",
                  border: publishSettings.isMakeup ? "1px solid var(--accent-primary)" : "1px solid var(--glass-border)",
                  borderRadius: "8px",
                }}
              >
                <input
                  type="checkbox"
                  checked={publishSettings.isMakeup}
                  onChange={(e) => setPublishSettings({ ...publishSettings, isMakeup: e.target.checked, selectedStudents: [] })}
                  style={{ width: "18px", height: "18px", accentColor: "var(--accent-primary)" }}
                />
                <div>
                  <div style={{ fontWeight: 600 }}>Makeup Exam</div>
                  <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                    Restrict to selected students only
                  </div>
                </div>
              </label>
            </div>

            {/* Student Selection (only shown for makeup exams with a period selected) */}
            {publishSettings.isMakeup && publishSettings.periodFilename && (
              <div style={{ marginBottom: "20px" }}>
                <label style={{ display: "block", marginBottom: "8px", fontWeight: 600, fontSize: "0.95rem" }}>
                  Select Students ({publishSettings.selectedStudents.length} selected)
                </label>
                {loadingPublishStudents ? (
                  <div style={{ padding: "20px", textAlign: "center", color: "var(--text-secondary)" }}>
                    <Icon name="Loader" size={24} className="spin" />
                    <div style={{ marginTop: "10px" }}>Loading students...</div>
                  </div>
                ) : publishModalStudents.length === 0 ? (
                  <div style={{ padding: "20px", textAlign: "center", color: "var(--text-secondary)" }}>
                    No students in this period
                  </div>
                ) : (
                  <div
                    style={{
                      maxHeight: "200px",
                      overflowY: "auto",
                      border: "1px solid var(--glass-border)",
                      borderRadius: "8px",
                      background: "var(--surface)",
                    }}
                  >
                    {publishModalStudents.map((student, idx) => {
                      const studentName = student.first + ' ' + student.last;
                      const isSelected = publishSettings.selectedStudents.includes(studentName);
                      const studentId = student.id || student.email || studentName;
                      const hasAccommodation = studentAccommodations[studentId];
                      return (
                        <label
                          key={idx}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "10px",
                            padding: "10px 12px",
                            borderBottom: idx < publishModalStudents.length - 1 ? "1px solid var(--glass-border)" : "none",
                            cursor: "pointer",
                            background: isSelected ? "rgba(139, 92, 246, 0.1)" : "transparent",
                          }}
                        >
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={(e) => {
                              if (e.target.checked) {
                                setPublishSettings({ ...publishSettings, selectedStudents: [...publishSettings.selectedStudents, studentName] });
                              } else {
                                setPublishSettings({ ...publishSettings, selectedStudents: publishSettings.selectedStudents.filter(s => s !== studentName) });
                              }
                            }}
                            style={{ width: "16px", height: "16px", accentColor: "var(--accent-primary)" }}
                          />
                          <span style={{ flex: 1 }}>{studentName}</span>
                          {hasAccommodation && (
                            <span
                              style={{
                                padding: "2px 8px",
                                background: "rgba(59, 130, 246, 0.2)",
                                color: "#3b82f6",
                                borderRadius: "4px",
                                fontSize: "0.75rem",
                                fontWeight: 600,
                              }}
                            >
                              IEP/504
                            </span>
                          )}
                        </label>
                      );
                    })}
                  </div>
                )}
                {publishSettings.isMakeup && publishModalStudents.length > 0 && (
                  <div style={{ marginTop: "8px", display: "flex", gap: "10px" }}>
                    <button
                      onClick={() => setPublishSettings({ ...publishSettings, selectedStudents: publishModalStudents.map(s => s.first + ' ' + s.last) })}
                      className="btn btn-secondary"
                      style={{ padding: "6px 12px", fontSize: "0.85rem" }}
                    >
                      Select All
                    </button>
                    <button
                      onClick={() => setPublishSettings({ ...publishSettings, selectedStudents: [] })}
                      className="btn btn-secondary"
                      style={{ padding: "6px 12px", fontSize: "0.85rem" }}
                    >
                      Clear
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Apply Accommodations Toggle */}
            {publishSettings.periodFilename && Object.keys(studentAccommodations).length > 0 && (
              <div style={{ marginBottom: "20px" }}>
                <label
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "10px",
                    cursor: "pointer",
                    padding: "12px 15px",
                    background: publishSettings.applyAccommodations ? "rgba(59, 130, 246, 0.2)" : "var(--glass-bg)",
                    border: publishSettings.applyAccommodations ? "1px solid #3b82f6" : "1px solid var(--glass-border)",
                    borderRadius: "8px",
                  }}
                >
                  <input
                    type="checkbox"
                    checked={publishSettings.applyAccommodations}
                    onChange={(e) => setPublishSettings({ ...publishSettings, applyAccommodations: e.target.checked })}
                    style={{ width: "18px", height: "18px", accentColor: "#3b82f6" }}
                  />
                  <div>
                    <div style={{ fontWeight: 600 }}>Apply IEP/504 Accommodations</div>
                    <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                      Students with accommodations will see modified instructions
                    </div>
                  </div>
                </label>
              </div>
            )}

            {/* Time Limit */}
            <div style={{ marginBottom: "25px" }}>
              <label style={{ display: "block", marginBottom: "8px", fontWeight: 600, fontSize: "0.95rem" }}>
                Time Limit (Optional)
              </label>
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <input
                  type="number"
                  min="0"
                  value={publishSettings.timeLimit || ''}
                  onChange={(e) => setPublishSettings({ ...publishSettings, timeLimit: e.target.value ? parseInt(e.target.value) : null })}
                  placeholder="No limit"
                  style={{
                    width: "120px",
                    padding: "10px 12px",
                    borderRadius: "8px",
                    border: "1px solid var(--glass-border)",
                    background: "var(--surface)",
                    color: "var(--text-primary)",
                    fontSize: "0.95rem",
                  }}
                />
                <span style={{ color: "var(--text-secondary)" }}>minutes</span>
              </div>
            </div>

            {/* Actions */}
            <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end" }}>
              <button
                onClick={() => setShowPublishModal(false)}
                className="btn btn-secondary"
                style={{ padding: "10px 20px" }}
              >
                Cancel
              </button>
              <button
                onClick={confirmPublishAssessment}
                disabled={publishingAssessment || (publishSettings.isMakeup && publishSettings.selectedStudents.length === 0)}
                className="btn btn-primary"
                style={{
                  padding: "10px 24px",
                  background: "linear-gradient(135deg, #8b5cf6, #6366f1)",
                }}
              >
                <Icon name={publishingAssessment ? "Loader" : "Share2"} size={16} />
                {publishingAssessment ? "Publishing..." : "Publish Assessment"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Published Assessment Modal - Shows join code and link */}
      {publishedAssessmentModal.show && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0, 0, 0, 0.8)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 9999,
            padding: "20px",
          }}
          onClick={() => setPublishedAssessmentModal({ show: false, joinCode: "", joinLink: "" })}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: "#1a1a2e",
              borderRadius: "16px",
              padding: "30px",
              maxWidth: "500px",
              width: "100%",
              textAlign: "center",
              border: "1px solid rgba(255, 255, 255, 0.1)",
              boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)",
            }}
          >
            <div style={{ marginBottom: "20px" }}>
              <Icon name="CheckCircle" size={48} style={{ color: "#22c55e" }} />
            </div>
            <h2 style={{ fontSize: "1.5rem", fontWeight: 700, marginBottom: "10px" }}>
              Assessment Published!
            </h2>
            <p style={{ color: "var(--text-secondary)", marginBottom: "25px" }}>
              Students can now take this assessment using the code below.
            </p>

            {/* Join Code Display */}
            <div
              style={{
                background: "linear-gradient(135deg, rgba(139, 92, 246, 0.2), rgba(99, 102, 241, 0.2))",
                border: "2px solid var(--accent-primary)",
                borderRadius: "12px",
                padding: "20px",
                marginBottom: "20px",
              }}
            >
              <div style={{ fontSize: "0.9rem", color: "var(--text-secondary)", marginBottom: "8px" }}>
                Join Code
              </div>
              <div
                style={{
                  fontSize: "2.5rem",
                  fontWeight: 800,
                  letterSpacing: "0.15em",
                  fontFamily: "monospace",
                  color: "var(--accent-primary)",
                }}
              >
                {publishedAssessmentModal.joinCode}
              </div>
            </div>

            {/* Link */}
            <div style={{ marginBottom: "25px" }}>
              <div style={{ fontSize: "0.9rem", color: "var(--text-secondary)", marginBottom: "8px" }}>
                Or share this link:
              </div>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                  background: "var(--glass-bg)",
                  padding: "12px 15px",
                  borderRadius: "8px",
                }}
              >
                <input
                  type="text"
                  readOnly
                  value={publishedAssessmentModal.joinLink}
                  style={{
                    flex: 1,
                    background: "transparent",
                    border: "none",
                    color: "var(--text-primary)",
                    fontSize: "0.9rem",
                    outline: "none",
                  }}
                />
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(publishedAssessmentModal.joinLink);
                    addToast("Link copied to clipboard!", "success");
                  }}
                  className="btn btn-secondary"
                  style={{ padding: "8px 12px" }}
                >
                  <Icon name="Copy" size={16} />
                </button>
              </div>
            </div>

            {/* Instructions */}
            <div
              style={{
                background: "rgba(34, 197, 94, 0.1)",
                border: "1px solid rgba(34, 197, 94, 0.3)",
                borderRadius: "8px",
                padding: "15px",
                marginBottom: "25px",
                textAlign: "left",
              }}
            >
              <div style={{ fontWeight: 600, marginBottom: "8px", color: "#22c55e" }}>
                <Icon name="Info" size={16} style={{ marginRight: "8px" }} />
                How students join:
              </div>
              <ol style={{ margin: 0, paddingLeft: "20px", color: "var(--text-secondary)", fontSize: "0.9rem" }}>
                <li>Go to <strong>graider.live/join</strong></li>
                <li>Enter code: <strong>{publishedAssessmentModal.joinCode}</strong></li>
                <li>Enter their name and start the assessment</li>
              </ol>
            </div>

            <button
              onClick={() => setPublishedAssessmentModal({ show: false, joinCode: "", joinLink: "" })}
              className="btn btn-primary"
              style={{ padding: "12px 30px" }}
            >
              Done
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
