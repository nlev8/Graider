import React, { useState, useEffect, useRef, useMemo } from "react";
import Icon from "../components/Icon";
import { AssignmentPlayer } from "../components";
import QuestionEditToolbar from "../components/QuestionEditToolbar";
import QuestionEditOverlay from "../components/QuestionEditOverlay";
import MatchingCards from "../components/MatchingCards";
import MindMapView from "../components/MindMapView";
import FlashcardView from "../components/FlashcardView";
import * as api from "../services/api";
import { checkRequirementsMismatch } from "../utils/standardsMismatch";

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
                    {'\u2022'} {q}
                  </p>
                ))}
              </div>
            )}

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
                    {'\u2022'} {t}
                  </p>
                ))}
              </div>
            )}

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

// Extract unique domain codes from standards
const getDomains = (stds) => {
  const seen = [];
  stds.forEach((s) => {
    const parts = s.code.split(".");
    const domain = parts.length >= 3 ? parts[2] : "";
    if (domain && !seen.includes(domain)) seen.push(domain);
  });
  return seen;
};

// Inline CSV table preview — fetches CSV from URL and renders as HTML table
function DataTablePreview({ url }) {
  var [rows, setRows] = React.useState(null);
  React.useEffect(function() {
    fetch(url).then(function(r) { return r.text(); }).then(function(text) {
      var lines = text.trim().split(String.fromCharCode(10));
      var parsed = lines.map(function(line) {
        // Simple CSV parse (handles quoted fields)
        var result = [];
        var current = "";
        var inQuotes = false;
        for (var i = 0; i < line.length; i++) {
          var ch = line[i];
          if (ch === '"') { inQuotes = !inQuotes; }
          else if (ch === ',' && !inQuotes) { result.push(current.trim()); current = ""; }
          else { current += ch; }
        }
        result.push(current.trim());
        return result;
      });
      setRows(parsed);
    }).catch(function() { setRows([]); });
  }, [url]);
  if (!rows) return React.createElement("div", { style: { padding: "20px", textAlign: "center", color: "var(--text-secondary)" } }, "Loading table...");
  if (rows.length === 0) return React.createElement("div", { style: { padding: "20px", color: "var(--text-secondary)" } }, "Empty table");
  var header = rows[0];
  var body = rows.slice(1);
  return (
    React.createElement("div", { style: { maxHeight: "400px", overflow: "auto", borderRadius: "12px", border: "1px solid var(--border)" } },
      React.createElement("table", { style: { width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" } },
        React.createElement("thead", null,
          React.createElement("tr", null,
            header.map(function(h, i) {
              return React.createElement("th", { key: i, style: { padding: "10px 12px", background: "rgba(139, 92, 246, 0.1)", fontWeight: 600, textAlign: "left", borderBottom: "2px solid var(--border)", position: "sticky", top: 0 } }, h);
            })
          )
        ),
        React.createElement("tbody", null,
          body.map(function(row, ri) {
            return React.createElement("tr", { key: ri, style: { background: ri % 2 === 0 ? "transparent" : "rgba(0,0,0,0.02)" } },
              row.map(function(cell, ci) {
                return React.createElement("td", { key: ci, style: { padding: "8px 12px", borderBottom: "1px solid var(--border)" } }, cell);
              })
            );
          })
        )
      )
    )
  );
}


export default React.memo(function PlannerTab({
  config,
  status,
  periods,
  savedAssignments,
  savedAssignmentData,
  user,
  globalAINotes,
  addToast,
  studentAccommodations,
  assignment,
  setAssignment,
  setLoadedAssignmentName,
  setActiveTab,
}) {
  // Domain navigation data (subject-specific)
  const domainNamesBySubject = {
    Math: { NSO: "Number Sense & Ops", AR: "Algebraic Reasoning", GR: "Geometric Reasoning", DP: "Data & Probability", F: "Functions", T: "Trigonometry", LT: "Logic & Thinking", FL: "Financial Literacy" },
    Science: { N: "Nature of Science", P: "Physical Science", L: "Life Science", E: "Earth & Space" },
    "English/ELA": { R: "Reading", C: "Communication", V: "Vocabulary" },
    "Social Studies": { A: "American History", C: "Civics & Gov", E: "Economics", G: "Geography", W: "World History" },
    Civics: { C: "Civics & Gov", E: "Economics" },
    Geography: { G: "Geography" },
    "US History": { A: "American History" },
    "World History": { W: "World History" },
  };
  const domainNameMap = domainNamesBySubject[config.subject] || domainNamesBySubject.Math;

  const scrollToDomain = (ref, domain) => {
    const container = ref.current;
    if (!container) return;
    const target = container.querySelector('[data-domain="' + domain + '"]');
    if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  // Support documents for calendar import
  const [supportDocs, setSupportDocs] = useState([]);

  const sortedPeriods = useMemo(() => {
    return [...periods].sort((a, b) => {
      const numA = parseInt((a.period_name || "").match(/\d+/)?.[0] || "999", 10);
      const numB = parseInt((b.period_name || "").match(/\d+/)?.[0] || "999", 10);
      return numA - numB;
    });
  }, [periods]);

  const [standards, setStandards] = useState([]);
  const [selectedStandards, setSelectedStandards] = useState([]);
  const [expandedStandards, setExpandedStandards] = useState([]);
  const toggleStandard = (code) => {
    setSelectedStandards((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code],
    );
  };
  const standardsScrollRef = useRef(null);
  const assessmentStandardsScrollRef = useRef(null);
  const [lessonPlan, setLessonPlan] = useState(null);
  const [lessonVariations, setLessonVariations] = useState([]);
  const [brainstormIdeas, setBrainstormIdeas] = useState([]);
  const [selectedIdea, setSelectedIdea] = useState(null);
  const [plannerLoading, setPlannerLoading] = useState(false);
  const [brainstormLoading, setBrainstormLoading] = useState(false);
  const [generatedAssignment, setGeneratedAssignment] = useState(null);
  const [assignmentLoading, setAssignmentLoading] = useState(false);
  const [assignmentType, setAssignmentType] = useState("worksheet");
  const [assignmentSectionsOpen, setAssignmentSectionsOpen] = useState(false);
  const [assignmentSectionCategories, setAssignmentSectionCategories] = useState({
    multiple_choice: true, short_answer: true, math_computation: false,
    geometry_visual: false, graphing: false, data_analysis: false,
    extended_writing: true, vocabulary: false, true_false: false, florida_fast: false,
  });
  const [previewShowAnswers, setPreviewShowAnswers] = useState(true);
  const [previewResults, setPreviewResults] = useState(null);

  // NotebookLM materials state
  const [nlmAuthenticated, setNlmAuthenticated] = useState(false);
  const [nlmNotebookId, setNlmNotebookId] = useState(null);
  const [nlmGenerating, setNlmGenerating] = useState(false);
  const [nlmProgress, setNlmProgress] = useState([]);
  const [nlmCompleted, setNlmCompleted] = useState([]);
  const [nlmErrors, setNlmErrors] = useState([]);
  const [nlmMaterials, setNlmMaterials] = useState({});
  const [showNlmPanel, setShowNlmPanel] = useState(false);
  const [nlmSelectedMaterials, setNlmSelectedMaterials] = useState({
    audio_overview: false, video_overview: false, quiz: false,
    flashcards: false, study_guide: false, slide_deck: false,
    mind_map: false, infographic: false, data_table: false,
  });
  const [nlmOptions, setNlmOptions] = useState({});
  const [nlmPreviewData, setNlmPreviewData] = useState(null);
  const [nlmTotalSelected, setNlmTotalSelected] = useState(0);

  var NLM_MATERIAL_TYPES = [
    { id: "audio_overview", label: "Audio Overview", icon: "Headphones" },
    { id: "video_overview", label: "Video Overview", icon: "Video" },
    { id: "quiz", label: "Quiz", icon: "ClipboardCheck" },
    { id: "flashcards", label: "Flashcards", icon: "Layers" },
    { id: "study_guide", label: "Study Guide", icon: "BookOpen" },
    { id: "slide_deck", label: "Slide Deck", icon: "Presentation" },
    { id: "mind_map", label: "Mind Map", icon: "GitBranch" },
    { id: "infographic", label: "Infographic", icon: "Image" },
    { id: "data_table", label: "Data Table", icon: "Table2" },
  ];

  // Context document uploads for NotebookLM
  const [nlmContextFiles, setNlmContextFiles] = useState([]);
  const [nlmUploading, setNlmUploading] = useState(false);

  // Question editing state
  const [editMode, setEditMode] = useState(false);
  const [selectedQuestions, setSelectedQuestions] = useState(new Set());
  const [editingQuestion, setEditingQuestion] = useState(null); // "sIdx-qIdx" key
  const [regeneratingQuestions, setRegeneratingQuestions] = useState(new Set());

  // Reset preview results, edit state, and NLM notebook when assignment changes
  useEffect(() => {
    setPreviewResults(null);
    setEditMode(false);
    setSelectedQuestions(new Set());
    setNlmNotebookId(null);
    setNlmCompleted([]);
    setNlmMaterials({});
    setNlmErrors([]);
    setShowNlmPanel(false);
    setEditingQuestion(null);
    setRegeneratingQuestions(new Set());
  }, [lessonPlan, generatedAssignment]);

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
    totalQuestions: 10,
    questionsPerSection: 0,
  });

  // Assessment generator state
  const [assessmentConfig, setAssessmentConfig] = useState({
    type: "quiz",
    title: "",
    targetPeriod: "", // For differentiation based on Global AI Instructions
    totalQuestions: 20,
    totalPoints: 30,
    // Section categories — controls which "Parts" the AI generates
    // FL FAST-aligned defaults: MC, short answer, math computation, geometry, graphing, data analysis ON
    // Vocabulary and extended writing OFF by default
    sectionCategories: {
      multiple_choice: true,      // Part: Multiple Choice
      short_answer: true,         // Part: Short Answer / Gridded Response
      math_computation: true,     // Part: Math Computation (equations, solve for x)
      geometry_visual: true,      // Part: Geometry & Measurement (interactive shapes, protractor, transformations)
      graphing: true,             // Part: Graphing & Coordinate Plane (number lines, function graphs)
      data_analysis: true,        // Part: Data Analysis (tables, box plots, dot plots, stem-and-leaf)
      extended_writing: false,    // Part: Extended Writing / Essay
      vocabulary: false,          // Part: Vocabulary / Matching
      true_false: false,          // Part: True/False
      florida_fast: false,        // Part: FL FAST Item Types (multiselect, multi-part, grid match, inline dropdown)
    },
    questionTypes: {
      multiple_choice: 10,
      short_answer: 4,
      extended_response: 0,
      true_false: 0,
      matching: 0,
      math_equation: 3,
      data_table: 3,
    },
    pointsPerType: {
      multiple_choice: 1,
      short_answer: 2,
      true_false: 1,
      matching: 1,
      extended_response: 4,
      math_equation: 2,
      data_table: 3,
      multiselect: 2,
      multi_part: 2,
      grid_match: 3,
      inline_dropdown: 2,
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
  const [sectionsDropdownOpen, setSectionsDropdownOpen] = useState(false);

  // Helper function to distribute questions across types based on enabled section categories
  const distributeQuestions = (total, categories = null) => {
    const cats = categories || assessmentConfig.sectionCategories || {};
    // Map section categories → question types with weights
    // FL FAST alignment: heavy MC + short answer + STEM visuals
    const typeWeights = {};
    if (cats.multiple_choice) typeWeights.multiple_choice = 40;
    if (cats.short_answer) typeWeights.short_answer = 15;
    if (cats.math_computation) typeWeights.math_equation = 15;
    if (cats.geometry_visual || cats.graphing || cats.data_analysis) typeWeights.data_table = 15;
    if (cats.extended_writing) typeWeights.extended_response = 10;
    if (cats.true_false) typeWeights.true_false = 10;
    if (cats.vocabulary) typeWeights.matching = 10;
    if (cats.florida_fast) { typeWeights.multiselect = 10; typeWeights.multi_part = 8; typeWeights.grid_match = 6; typeWeights.inline_dropdown = 6; }

    // If nothing enabled, default to MC
    if (Object.keys(typeWeights).length === 0) typeWeights.multiple_choice = 100;

    const totalWeight = Object.values(typeWeights).reduce((a, b) => a + b, 0);
    const result = {};
    let assigned = 0;
    const entries = Object.entries(typeWeights);
    entries.forEach(([type, weight], i) => {
      if (i === entries.length - 1) {
        result[type] = Math.max(1, total - assigned); // remainder
      } else {
        const count = Math.max(1, Math.round(total * weight / totalWeight));
        result[type] = count;
        assigned += count;
      }
    });

    // Ensure all types exist in result
    const allTypes = ['multiple_choice', 'short_answer', 'extended_response', 'true_false', 'matching', 'math_equation', 'data_table', 'multiselect', 'multi_part', 'grid_match', 'inline_dropdown'];
    allTypes.forEach(t => { if (!(t in result)) result[t] = 0; });
    return result;
  };

  // Get subject-appropriate section category defaults
  const getSubjectSectionDefaults = (subject) => {
    const s = (subject || '').toLowerCase();
    const isMath = s.includes('math') || s.includes('algebra') || s.includes('geometry') || s.includes('calculus') || s.includes('statistics');
    const isScience = s.includes('science') || s.includes('biology') || s.includes('chemistry') || s.includes('physics') || s.includes('earth');
    const isELA = s.includes('ela') || s.includes('english') || s.includes('reading') || s.includes('writing') || s.includes('language arts') || s.includes('literature');
    const isSocialStudies = s.includes('history') || s.includes('social') || s.includes('civics') || s.includes('economics') || s.includes('geography') || s.includes('government');

    if (isMath) {
      return {
        multiple_choice: true,
        short_answer: true,
        math_computation: true,
        geometry_visual: true,
        graphing: true,
        data_analysis: true,
        extended_writing: false,
        vocabulary: false,
        true_false: false,
      };
    }
    if (isScience) {
      return {
        multiple_choice: true,
        short_answer: true,
        math_computation: false,
        geometry_visual: false,
        graphing: true,
        data_analysis: true,
        extended_writing: false,
        vocabulary: true,
        true_false: false,
      };
    }
    if (isELA) {
      return {
        multiple_choice: true,
        short_answer: true,
        math_computation: false,
        geometry_visual: false,
        graphing: false,
        data_analysis: false,
        extended_writing: true,
        vocabulary: true,
        true_false: false,
      };
    }
    if (isSocialStudies) {
      return {
        multiple_choice: true,
        short_answer: true,
        math_computation: false,
        geometry_visual: false,
        graphing: false,
        data_analysis: false,
        extended_writing: true,
        vocabulary: true,
        true_false: true,
      };
    }
    // Default — generic
    return {
      multiple_choice: true,
      short_answer: true,
      math_computation: false,
      geometry_visual: false,
      graphing: false,
      data_analysis: false,
      extended_writing: true,
      vocabulary: false,
      true_false: false,
    };
  };

  // Update section categories when subject changes (both assessment and assignment)
  useEffect(() => {
    if (config.subject) {
      const newCats = getSubjectSectionDefaults(config.subject);
      const total = assessmentConfig.totalQuestions || 20;
      const newTypes = distributeQuestions(total, newCats);
      const newPointsPerType = distributePoints(assessmentConfig.totalPoints || 30, newTypes);
      setAssessmentConfig(prev => ({
        ...prev,
        sectionCategories: newCats,
        questionTypes: newTypes,
        pointsPerType: newPointsPerType,
      }));
      setAssignmentSectionCategories(newCats);
    }
  }, [config.subject]);

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
  const [plannerMode, setPlannerMode] = useState("lesson"); // "lesson", "assessment", "dashboard", or "calendar"

  // Reset edit state when assessment changes
  useEffect(() => {
    setEditMode(false);
    setSelectedQuestions(new Set());
    setEditingQuestion(null);
    setRegeneratingQuestions(new Set());
  }, [generatedAssessment]);

  // Calendar state
  const [calendarData, setCalendarData] = useState({ scheduled_lessons: [], holidays: [], school_days: {} })
  const [calendarMonth, setCalendarMonth] = useState(new Date())
  const [calendarView, setCalendarView] = useState('month')
  const [selectedCalendarDate, setSelectedCalendarDate] = useState(null)
  const [showHolidayModal, setShowHolidayModal] = useState(false)
  const [holidayForm, setHolidayForm] = useState({ date: '', name: '', end_date: '' })
  const [calendarDragId, setCalendarDragId] = useState(null)

  // Reading Level Tool state
  const [rlInput, setRlInput] = useState('')
  const [rlTargetLevel, setRlTargetLevel] = useState('6')
  const [rlPreserveTerms, setRlPreserveTerms] = useState([])
  const [rlTermInput, setRlTermInput] = useState('')
  const [rlLoading, setRlLoading] = useState(false)
  const [rlResult, setRlResult] = useState(null)
  const [showImportModal, setShowImportModal] = useState(false)
  const [importParsing, setImportParsing] = useState(false)
  const [importEvents, setImportEvents] = useState([])
  const [importChecked, setImportChecked] = useState({})
  const [importSelectedDoc, setImportSelectedDoc] = useState('')
  const [importImporting, setImportImporting] = useState(false)
  const [editingEvent, setEditingEvent] = useState(null)
  const [quickAddForm, setQuickAddForm] = useState({ title: '', unit: '', color: '#6366f1' })
  const [publishingAssessment, setPublishingAssessment] = useState(false);
  const [publishedAssessmentModal, setPublishedAssessmentModal] = useState({ show: false, joinCode: "", joinLink: "" });

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

  // Clear selected standards when grade/subject/state changes
  useEffect(() => {
    setSelectedStandards([]);
    setStandards([]);
  }, [config.state, config.grade_level, config.subject]);

  // Load standards when planner tab is active
  useEffect(() => {
    if (config.subject) {
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
  }, [config.state, config.grade_level, config.subject]);

  // Check NotebookLM auth status on mount
  useEffect(function() {
    api.notebookLMAuthStatus().then(function(data) {
      setNlmAuthenticated(data.authenticated || false);
    }).catch(function() {});
  }, []);

  // NotebookLM generation status polling
  useEffect(function() {
    if (!nlmGenerating) return;
    var interval = setInterval(function() {
      api.notebookLMStatus().then(function(data) {
        setNlmProgress(data.progress || []);
        setNlmCompleted(data.completed || []);
        setNlmErrors(data.errors || []);
        setNlmMaterials(data.materials || {});
        if (!data.is_running) {
          setNlmGenerating(false);
          clearInterval(interval);
          if (data.errors && data.errors.length > 0) {
            addToast("Some materials failed: " + data.errors.join(", "), "warning");
          } else if (data.completed && data.completed.length > 0) {
            addToast("Materials generated successfully!", "success");
          }
        }
      }).catch(function() {});
    }, 2000);
    return function() { clearInterval(interval); };
  }, [nlmGenerating]);

  // Load calendar data when calendar mode is active
  useEffect(() => {
    if (plannerMode === 'calendar') {
      fetch('/api/calendar').then(r => r.json()).then(setCalendarData).catch(() => {})
    }
  }, [plannerMode])

  // Calendar helper functions
  function loadCalendar() {
    fetch('/api/calendar').then(r => r.json()).then(setCalendarData).catch(() => {})
  }

  async function scheduleLesson(entry) {
    try {
      const resp = await fetch('/api/calendar/schedule', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(entry),
      })
      const data = await resp.json()
      if (data.status === 'scheduled') loadCalendar()
    } catch (e) {
      if (addToast) addToast('Failed to schedule lesson', 'error')
    }
  }

  async function unscheduleLesson(entryId) {
    try {
      await fetch('/api/calendar/schedule/' + entryId, { method: 'DELETE' })
      loadCalendar()
    } catch (e) {
      if (addToast) addToast('Failed to remove lesson', 'error')
    }
  }

  async function addHoliday(holiday) {
    try {
      const resp = await fetch('/api/calendar/holiday', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(holiday),
      })
      const data = await resp.json()
      if (data.status === 'added') loadCalendar()
    } catch (e) {
      if (addToast) addToast('Failed to add holiday', 'error')
    }
  }

  async function removeHoliday(date) {
    try {
      await fetch('/api/calendar/holiday?date=' + date, { method: 'DELETE' })
      loadCalendar()
    } catch (e) {
      if (addToast) addToast('Failed to remove holiday', 'error')
    }
  }

  // Calendar grid computation
  function getCalendarDays(month) {
    const year = month.getFullYear()
    const m = month.getMonth()
    const firstDay = new Date(year, m, 1)
    const lastDay = new Date(year, m + 1, 0)
    const startDow = firstDay.getDay() // 0=Sun
    const totalDays = lastDay.getDate()

    const days = []
    // Fill leading blanks (start from Sunday)
    for (let i = 0; i < startDow; i++) days.push(null)
    for (let d = 1; d <= totalDays; d++) {
      const dateStr = year + '-' + String(m + 1).padStart(2, '0') + '-' + String(d).padStart(2, '0')
      days.push({ day: d, date: dateStr, dow: new Date(year, m, d).getDay() })
    }
    return days
  }

  function getWeekDays(startOfWeek) {
    const days = []
    for (let i = 0; i < 7; i++) {
      const d = new Date(startOfWeek)
      d.setDate(d.getDate() + i)
      const dateStr = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0')
      days.push({ day: d.getDate(), date: dateStr, dow: d.getDay(), fullDate: d })
    }
    return days
  }

  function getStartOfWeek(date) {
    const d = new Date(date)
    const day = d.getDay()
    d.setDate(d.getDate() - day)
    return d
  }

  function isHoliday(dateStr) {
    return (calendarData.holidays || []).find(h => {
      if (h.date === dateStr) return true
      if (h.end_date && dateStr >= h.date && dateStr <= h.end_date) return true
      return false
    })
  }

  function getLessonsForDate(dateStr) {
    return (calendarData.scheduled_lessons || []).filter(s => s.date === dateStr)
  }

  function isSchoolDay(dow) {
    const dayNames = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']
    return calendarData.school_days ? calendarData.school_days[dayNames[dow]] : (dow >= 1 && dow <= 5)
  }

  const brainstormIdeasHandler = async () => {
    if (!config.subject) {
      addToast("Please select a subject in Settings before generating", "warning");
      return;
    }
    if (!config.grade_level) {
      addToast("Please select a grade level in Settings before generating", "warning");
      return;
    }
    if (selectedStandards.length === 0) {
      addToast("Please select at least one standard", "warning");
      return;
    }
    const mismatchCheck = checkRequirementsMismatch(unitConfig.requirements, selectedStandards, standards);
    if (mismatchCheck.mismatch) addToast(mismatchCheck.message, "warning", 6000);
    setBrainstormLoading(true);
    setBrainstormIdeas([]);
    setSelectedIdea(null);
    setLessonPlan(null);  // Clear existing lesson plan so brainstorm results show
    setLessonVariations([]);  // Clear variations too
    try {
      // Look up full standard objects — include benchmark, vocabulary, and learning targets
      const fullStandards = selectedStandards.map((code) => {
        const std = standards.find((s) => s.code === code);
        if (!std) return code;
        let text = std.code + ": " + std.benchmark;
        if (std.vocabulary && std.vocabulary.length > 0) {
          text += " | Key Vocabulary: " + std.vocabulary.join(", ");
        }
        if (std.learning_targets && std.learning_targets.length > 0) {
          text += " | Learning Targets: " + std.learning_targets.join("; ");
        }
        return text;
      });
      const data = await api.brainstormLessonIdeas({
        standards: fullStandards,
        config: {
          state: config.state || "FL",
          grade: config.grade_level,
          subject: config.subject,
          availableTools: config.availableTools || [],
          requirements: unitConfig.requirements || "",
        },
      });
      if (data.error)
        addToast("Note: Using sample ideas - " + data.error, "info");
      setBrainstormIdeas(data.ideas || []);
      if (data.usage) addToast("Brainstorm cost: " + data.usage.cost_display + " (" + data.usage.total_tokens.toLocaleString() + " tokens)", "info");
    } catch (e) {
      addToast("Error brainstorming: " + e.message, "error");
    } finally {
      setBrainstormLoading(false);
    }
  };

  // Generate lesson plan (optionally from selected idea, optionally with variations)
  const generateLessonPlan = async (generateVariations = false) => {
    if (!config.subject) {
      addToast("Please select a subject in Settings before generating", "warning");
      return;
    }
    if (!config.grade_level) {
      addToast("Please select a grade level in Settings before generating", "warning");
      return;
    }
    if (selectedStandards.length === 0) {
      addToast("Please select at least one standard", "warning");
      return;
    }
    const mismatchCheck = checkRequirementsMismatch(unitConfig.requirements, selectedStandards, standards);
    if (mismatchCheck.mismatch) addToast(mismatchCheck.message, "warning", 6000);
    setPlannerLoading(true);
    setLessonVariations([]);
    try {
      // Look up full standard objects — include benchmark, vocabulary, and learning targets
      const fullStandards = selectedStandards.map((code) => {
        const std = standards.find((s) => s.code === code);
        if (!std) return code;
        let text = std.code + ": " + std.benchmark;
        if (std.vocabulary && std.vocabulary.length > 0) {
          text += " | Key Vocabulary: " + std.vocabulary.join(", ");
        }
        if (std.learning_targets && std.learning_targets.length > 0) {
          text += " | Learning Targets: " + std.learning_targets.join("; ");
        }
        return text;
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
          sectionCategories: unitConfig.type === "Assignment" ? assignmentSectionCategories : undefined,
        },
        selectedIdea: selectedIdea,
        generateVariations: generateVariations,
      });
      if (data.error) addToast("Error: " + data.error, "error");
      else if (data.variations) {
        setLessonVariations(data.variations);
        addToast(
          `Generated ${data.variations.length} ${(unitConfig.type || 'lesson plan').toLowerCase()} variations!`,
          "success",
        );
      } else {
        setLessonPlan(data.plan || data);
      }
      if (data.usage) addToast("Generation cost: " + data.usage.cost_display + " (" + data.usage.total_tokens.toLocaleString() + " tokens)", "info");
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

  // NotebookLM materials generation handler
  var handleNlmGenerate = async function() {
    var selected = Object.entries(nlmSelectedMaterials)
      .filter(function(entry) { return entry[1]; })
      .map(function(entry) { return entry[0]; });

    if (selected.length === 0) {
      addToast("Select at least one material type", "warning");
      return;
    }

    try {
      setNlmGenerating(true);
      setNlmTotalSelected(selected.length);
      setNlmProgress([]);
      setNlmCompleted([]);
      setNlmErrors([]);
      setNlmMaterials({});
      setNlmPreviewData(null);

      // Create notebook if needed
      var notebookId = nlmNotebookId;
      if (!notebookId) {
        addToast("Creating NotebookLM notebook...", "info");
        var enrichedStandards = selectedStandards.map(function(code) {
          var std = standards.find(function(s) { return s.code === code; });
          return std || { code: code };
        });
        var nbData = await api.notebookLMCreateNotebook(
          lessonPlan, enrichedStandards,
          { subject: config.subject, grade: config.grade_level },
          nlmContextFiles.map(function(f) { return f.path; })
        );
        if (nbData.error) {
          if (nbData.needs_login) {
            setNlmAuthenticated(false);
            addToast("Session expired. Please reconnect to NotebookLM.", "warning");
          } else {
            addToast("Error: " + nbData.error, "error");
          }
          setNlmGenerating(false);
          return;
        }
        notebookId = nbData.notebook_id;
        setNlmNotebookId(notebookId);
      }

      // Start generation
      var result = await api.notebookLMGenerate(notebookId, selected, nlmOptions);
      if (result.error) {
        addToast("Error: " + result.error, "error");
        setNlmGenerating(false);
      }
    } catch (e) {
      addToast("Error: " + e.message, "error");
      setNlmGenerating(false);
    }
  };

  var handleNlmPreview = async function(materialType) {
    try {
      var data = await api.notebookLMPreview(materialType);
      setNlmPreviewData(data);
    } catch (e) {
      addToast("Preview error: " + e.message, "error");
    }
  };

  // Assessment generation handlers
  const generateAssessmentHandler = async () => {
    if (!config.subject) {
      addToast("Please select a subject in Settings before generating", "warning");
      return;
    }
    if (!config.grade_level) {
      addToast("Please select a grade level in Settings before generating", "warning");
      return;
    }
    if (selectedStandards.length === 0) {
      addToast("Please select at least one standard", "warning");
      return;
    }
    const mismatchCheck = checkRequirementsMismatch(unitConfig.requirements, selectedStandards, standards);
    if (mismatchCheck.mismatch) addToast(mismatchCheck.message, "warning", 6000);
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
          requirements: unitConfig.requirements || "",
        },
        { ...assessmentConfig, title },
        selectedSources
      );

      if (data.error) {
        addToast("Error: " + data.error, "error");
      } else if (data.assessment) {
        if (!data.assessment.time_limit && data.assessment.time_limit !== 0) {
          const match = data.assessment.time_estimate?.match(/(\d+)/);
          data.assessment.time_limit = match ? parseInt(match[1]) : null;
        }
        setGeneratedAssessment(data.assessment);
        setAssessmentAnswers({}); // Clear previous answers
        addToast("Assessment generated successfully!", "success");
        if (data.usage) addToast("Generation cost: " + data.usage.cost_display + " (" + data.usage.total_tokens.toLocaleString() + " tokens)", "info");
      }
    } catch (e) {
      addToast("Error generating assessment: " + e.message, "error");
    } finally {
      setAssessmentLoading(false);
    }
  };

  const redistributePoints = (newTotal) => {
    if (!generatedAssessment) return;
    const currentTotal = generatedAssessment.total_points || 100;
    if (newTotal === currentTotal || newTotal < 1) return;

    const sections = (generatedAssessment.sections || []).map(s => {
      const questions = (s.questions || []).map(q => ({
        ...q,
        points: Math.max(1, Math.round((q.points || 1) * newTotal / currentTotal))
      }));
      return { ...s, questions, points: questions.reduce((sum, q) => sum + q.points, 0) };
    });

    const actualTotal = sections.reduce((sum, s) => sum + s.points, 0);
    if (actualTotal !== newTotal && sections.length > 0) {
      const lastSection = sections[sections.length - 1];
      if (lastSection.questions.length > 0) {
        const lastQ = lastSection.questions[lastSection.questions.length - 1];
        lastQ.points += (newTotal - actualTotal);
        lastSection.points += (newTotal - actualTotal);
      }
    }

    setGeneratedAssessment({ ...generatedAssessment, sections, total_points: newTotal });
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
    // Reset publish settings, pre-fill time limit from assessment
    setPublishSettings({
      period: '',
      periodFilename: '',
      isMakeup: false,
      selectedStudents: [],
      timeLimit: generatedAssessment.time_limit || null,
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
        if (!data.assessment.time_limit && data.assessment.time_limit !== 0) {
          const match = data.assessment.time_estimate?.match(/(\d+)/);
          data.assessment.time_limit = match ? parseInt(match[1]) : null;
        }
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
      if (data.usage) addToast("Grading cost: " + data.usage.cost_display + " (" + data.usage.total_tokens.toLocaleString() + " tokens)", "info");
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
    if (!config.subject) {
      addToast("Please select a subject in Settings before generating", "warning");
      return;
    }
    if (!config.grade_level) {
      addToast("Please select a grade level in Settings before generating", "warning");
      return;
    }
    if (!lessonPlan) {
      addToast("Please generate a lesson plan first", "warning");
      return;
    }
    if (selectedStandards.length > 0) {
      const mismatchCheck = checkRequirementsMismatch(unitConfig.requirements, selectedStandards, standards);
      if (mismatchCheck.mismatch) addToast(mismatchCheck.message, "warning", 6000);
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
          sectionCategories: assignmentSectionCategories,
          totalQuestions: unitConfig.totalQuestions,
          questionsPerSection: unitConfig.questionsPerSection,
          requirements: unitConfig.requirements || "",
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
        if (data.usage) addToast("Generation cost: " + data.usage.cost_display + " (" + data.usage.total_tokens.toLocaleString() + " tokens)", "info");
      }
    } catch (e) {
      addToast("Error generating assignment: " + e.message, "error");
    } finally {
      setAssignmentLoading(false);
    }
  };

  // ── Question Edit Mode Handlers ──

  /** Get the active assignment object (could be generatedAssignment, lessonPlan with sections, or generatedAssessment) */
  const getActiveAssignment = () => {
    if (generatedAssignment) return generatedAssignment;
    if (lessonPlan?.sections && !lessonPlan.days) return lessonPlan;
    if (generatedAssessment) return generatedAssessment;
    return null;
  };

  /** Set the active assignment object back into whichever state holds it */
  const setActiveAssignment = (updated) => {
    if (generatedAssignment) {
      setGeneratedAssignment(updated);
    } else if (lessonPlan?.sections && !lessonPlan.days) {
      setLessonPlan(updated);
    } else if (generatedAssessment) {
      setGeneratedAssessment(updated);
    }
  };

  /** Count total questions in the active assignment */
  const getTotalQuestionCount = () => {
    const a = getActiveAssignment();
    if (!a?.sections) return 0;
    return a.sections.reduce((sum, s) => sum + (s.questions?.length || 0), 0);
  };

  /** Toggle a question's selection */
  const toggleQuestionSelect = (qKey) => {
    setSelectedQuestions((prev) => {
      const next = new Set(prev);
      if (next.has(qKey)) next.delete(qKey);
      else next.add(qKey);
      return next;
    });
  };

  /** Select all questions */
  const selectAllQuestions = () => {
    const a = getActiveAssignment();
    if (!a?.sections) return;
    const keys = new Set();
    a.sections.forEach((s, sIdx) => {
      (s.questions || []).forEach((_, qIdx) => keys.add(sIdx + "-" + qIdx));
    });
    setSelectedQuestions(keys);
  };

  /** Save an inline-edited question back into the assignment */
  const saveEditedQuestion = (sIdx, qIdx, updatedQuestion) => {
    const a = getActiveAssignment();
    if (!a?.sections) return;
    const copy = JSON.parse(JSON.stringify(a));
    if (copy.sections[sIdx]?.questions?.[qIdx]) {
      // Preserve the original number
      updatedQuestion.number = copy.sections[sIdx].questions[qIdx].number;
      copy.sections[sIdx].questions[qIdx] = updatedQuestion;
      // Recalculate section points
      copy.sections[sIdx].points = copy.sections[sIdx].questions.reduce(
        (sum, q) => sum + (q.points || 0), 0
      );
      // Recalculate total
      copy.total_points = copy.sections.reduce((sum, s) => sum + (s.points || 0), 0);
      setActiveAssignment(copy);
    }
    setEditingQuestion(null);
    addToast("Question updated", "success");
  };

  /** Delete all selected questions */
  const deleteSelectedQuestions = () => {
    const a = getActiveAssignment();
    if (!a?.sections || selectedQuestions.size === 0) return;
    const copy = JSON.parse(JSON.stringify(a));
    const deleteCount = selectedQuestions.size;

    // Filter out selected questions from each section
    copy.sections.forEach((section, sIdx) => {
      section.questions = (section.questions || []).filter(
        (_, qIdx) => !selectedQuestions.has(sIdx + "-" + qIdx)
      );
      // Renumber
      section.questions.forEach((q, i) => { q.number = i + 1; });
      // Recalculate section points
      section.points = section.questions.reduce((sum, q) => sum + (q.points || 0), 0);
    });

    // Remove empty sections
    copy.sections = copy.sections.filter((s) => s.questions && s.questions.length > 0);

    // Recalculate total
    copy.total_points = copy.sections.reduce((sum, s) => sum + (s.points || 0), 0);

    setActiveAssignment(copy);
    setSelectedQuestions(new Set());
    addToast(deleteCount + " question(s) removed", "success");
  };

  /** Regenerate selected questions via AI */
  const regenerateSelectedQuestions = async () => {
    const a = getActiveAssignment();
    if (!a?.sections || selectedQuestions.size === 0) return;

    // Build the replacement specs and existing questions list
    const questionsToReplace = [];
    const existingQuestions = [];

    a.sections.forEach((section, sIdx) => {
      (section.questions || []).forEach((q, qIdx) => {
        const key = sIdx + "-" + qIdx;
        if (selectedQuestions.has(key)) {
          questionsToReplace.push({
            section_index: sIdx,
            question_index: qIdx,
            question_type: q.question_type || q.type || "short_answer",
            points: q.points || 1,
            dok: q.dok || 1,
            standard: q.standard || "",
          });
        } else {
          existingQuestions.push(q.question || "");
        }
      });
    });

    setRegeneratingQuestions(new Set(selectedQuestions));

    try {
      const data = await api.regenerateQuestions(
        questionsToReplace,
        existingQuestions,
        {
          grade: config.grade_level || "",
          subject: config.subject || "",
          globalAINotes: config.globalAINotes || "",
          requirements: unitConfig.requirements || "",
        }
      );

      if (data.error) {
        addToast("Regeneration error: " + data.error, "error");
        return;
      }

      // Merge replacements into the assignment
      const copy = JSON.parse(JSON.stringify(a));
      (data.replacements || []).forEach((r) => {
        const section = copy.sections[r.section_index];
        if (section?.questions?.[r.question_index]) {
          // Preserve the original question number
          r.question.number = section.questions[r.question_index].number;
          section.questions[r.question_index] = r.question;
        }
      });

      // Recalculate points
      copy.sections.forEach((section) => {
        section.points = section.questions.reduce((sum, q) => sum + (q.points || 0), 0);
      });
      copy.total_points = copy.sections.reduce((sum, s) => sum + (s.points || 0), 0);

      setActiveAssignment(copy);
      setSelectedQuestions(new Set());

      const costMsg = data.usage?.cost_display ? " (" + data.usage.cost_display + ")" : "";
      addToast(data.replacements.length + " question(s) regenerated" + costMsg, "success");
    } catch (e) {
      addToast("Regeneration failed: " + e.message, "error");
    } finally {
      setRegeneratingQuestions(new Set());
    }
  };

  /** Regenerate a single question */
  const regenerateOneQuestion = async (sIdx, qIdx) => {
    const a = getActiveAssignment();
    if (!a?.sections) return;
    const q = a.sections[sIdx]?.questions?.[qIdx];
    if (!q) return;

    const key = sIdx + "-" + qIdx;
    setRegeneratingQuestions(new Set([key]));

    const existingTexts = [];
    a.sections.forEach((s) => {
      (s.questions || []).forEach((ques) => existingTexts.push(ques.question || ""));
    });

    try {
      const data = await api.regenerateQuestions(
        [{
          section_index: sIdx,
          question_index: qIdx,
          question_type: q.question_type || q.type || "short_answer",
          points: q.points || 1,
          dok: q.dok || 1,
          standard: q.standard || "",
        }],
        existingTexts,
        {
          grade: config.grade_level || "",
          subject: config.subject || "",
          globalAINotes: config.globalAINotes || "",
          requirements: unitConfig.requirements || "",
        }
      );

      if (data.error) {
        addToast("Regeneration error: " + data.error, "error");
        return;
      }

      const copy = JSON.parse(JSON.stringify(a));
      (data.replacements || []).forEach((r) => {
        const section = copy.sections[r.section_index];
        if (section?.questions?.[r.question_index]) {
          r.question.number = section.questions[r.question_index].number;
          section.questions[r.question_index] = r.question;
        }
      });
      copy.sections.forEach((section) => {
        section.points = section.questions.reduce((sum, ques) => sum + (ques.points || 0), 0);
      });
      copy.total_points = copy.sections.reduce((sum, s) => sum + (s.points || 0), 0);

      setActiveAssignment(copy);
      setEditingQuestion(null);
      const costMsg = data.usage?.cost_display ? " (" + data.usage.cost_display + ")" : "";
      addToast("Question regenerated" + costMsg, "success");
    } catch (e) {
      addToast("Regeneration failed: " + e.message, "error");
    } finally {
      setRegeneratingQuestions(new Set());
    }
  };

  return (
    <>
                <div data-tutorial="planner-card" className="fade-in">
                  {/* Mode Toggle */}
                  <div
                    data-tutorial="planner-modes"
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
                    <button
                      onClick={() => setPlannerMode("calendar")}
                      style={{
                        padding: "10px 20px",
                        cursor: "pointer",
                        fontSize: "0.9rem",
                        background:
                          plannerMode === "calendar"
                            ? "linear-gradient(135deg, #f59e0b, #d97706)"
                            : "var(--glass-bg)",
                        border:
                          plannerMode === "calendar"
                            ? "none"
                            : "1px solid var(--glass-border)",
                        color: plannerMode === "calendar" ? "#fff" : "var(--text-secondary)",
                        fontWeight: 600,
                        borderRadius: "10px",
                        display: "flex",
                        alignItems: "center",
                        gap: "8px",
                      }}
                    >
                      <Icon name="Calendar" size={18} />
                      Calendar
                    </button>
                    <button
                      onClick={() => setPlannerMode("tools")}
                      style={{
                        padding: "10px 20px",
                        cursor: "pointer",
                        fontSize: "0.9rem",
                        background:
                          plannerMode === "tools"
                            ? "linear-gradient(135deg, #06b6d4, #0891b2)"
                            : "var(--glass-bg)",
                        border:
                          plannerMode === "tools"
                            ? "none"
                            : "1px solid var(--glass-border)",
                        color: plannerMode === "tools" ? "#fff" : "var(--text-secondary)",
                        fontWeight: 600,
                        borderRadius: "10px",
                        display: "flex",
                        alignItems: "center",
                        gap: "8px",
                      }}
                    >
                      <Icon name="Wrench" size={18} />
                      Tools
                    </button>
                  </div>

                  {/* Lesson Planning Mode */}
                  {plannerMode === "lesson" && (
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: (lessonPlan && ((lessonPlan.sections && !lessonPlan.days) || generatedAssignment)) ? "1fr" : "300px 1fr",
                      gap: "25px",
                    }}
                  >
                    {/* Sidebar — hidden when viewing a generated assignment; visible for lesson plans so user can configure & create assignments */}
                    {!(lessonPlan && ((lessonPlan.sections && !lessonPlan.days) || generatedAssignment)) && (
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
                              placeholder={
                                {
                                  'Math': 'e.g., Solving Systems of Linear Equations',
                                  'Science': 'e.g., Cell Structure and Function',
                                  'English/ELA': 'e.g., Analyzing Argumentative Texts',
                                  'US History': 'e.g., Causes of the American Revolution',
                                  'World History': 'e.g., Rise and Fall of the Roman Empire',
                                  'Social Studies': 'e.g., Rights and Responsibilities of Citizens',
                                  'Civics': 'e.g., Foundations of American Government',
                                  'Geography': 'e.g., Climate Zones and Human Adaptation',
                                }[config.subject] || 'e.g., Lesson Title'
                              }
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
                          {unitConfig.type === "Assignment" && (
                            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                              <div>
                                <label className="label">Total Questions</label>
                                <input
                                  type="number"
                                  className="input"
                                  value={unitConfig.totalQuestions}
                                  onChange={(e) =>
                                    setUnitConfig({
                                      ...unitConfig,
                                      totalQuestions: parseInt(e.target.value) || 10,
                                    })
                                  }
                                  min="5"
                                  max="50"
                                />
                              </div>
                              <div>
                                <label className="label">Per Section (0 = auto)</label>
                                <input
                                  type="number"
                                  className="input"
                                  value={unitConfig.questionsPerSection}
                                  onChange={(e) =>
                                    setUnitConfig({
                                      ...unitConfig,
                                      questionsPerSection: parseInt(e.target.value) || 0,
                                    })
                                  }
                                  min="0"
                                  max="20"
                                />
                              </div>
                            </div>
                          )}
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
                              placeholder={
                                {
                                  'Math': 'e.g., Include word problems with real-world scenarios, focus on showing work step-by-step',
                                  'Science': 'e.g., Include a lab component with data collection, tie to real-world applications',
                                  'English/ELA': 'e.g., Include text-dependent questions, require evidence-based responses with citations',
                                  'US History': 'e.g., Use primary source documents, include analysis of cause and effect',
                                  'World History': 'e.g., Compare perspectives from multiple civilizations, include map analysis',
                                  'Social Studies': 'e.g., Connect to current events, include civic action component',
                                  'Civics': 'e.g., Reference the U.S. Constitution, include a debate or discussion prompt',
                                  'Geography': 'e.g., Include map skills practice, analyze human-environment interaction',
                                }[config.subject] || 'e.g., Any special instructions for this lesson...'
                              }
                              style={{ minHeight: "80px" }}
                            />
                          </div>
                          {/* Assignment Sections Dropdown - visible when content type is Assignment */}
                          {unitConfig.type === "Assignment" && (
                            <div style={{
                              border: "1px solid var(--glass-border)",
                              borderRadius: "10px",
                              overflow: "hidden",
                            }}>
                              <button
                                type="button"
                                onClick={() => setAssignmentSectionsOpen(!assignmentSectionsOpen)}
                                style={{
                                  width: "100%",
                                  display: "flex",
                                  alignItems: "center",
                                  justifyContent: "space-between",
                                  background: "var(--glass-bg)",
                                  border: "none",
                                  cursor: "pointer",
                                  padding: "10px 14px",
                                  color: "inherit",
                                }}
                              >
                                <span style={{ fontSize: "0.9rem", fontWeight: 600, display: "flex", alignItems: "center", gap: "8px" }}>
                                  <Icon name="LayoutGrid" size={16} /> Sections
                                  <span style={{ fontSize: "0.7rem", fontWeight: 400, color: "var(--text-muted)" }}>
                                    ({Object.values(assignmentSectionCategories).filter(Boolean).length} active)
                                  </span>
                                </span>
                                <Icon name={assignmentSectionsOpen ? "ChevronUp" : "ChevronDown"} size={16} />
                              </button>
                              {assignmentSectionsOpen && (
                                <div style={{ padding: "10px 14px", display: "flex", flexDirection: "column", gap: "6px", borderTop: "1px solid var(--glass-border)" }}>
                                  {[
                                    { key: "multiple_choice", label: "Multiple Choice", icon: "CheckCircle", group: "core" },
                                    { key: "short_answer", label: "Short Answer", icon: "AlignLeft", group: "core" },
                                    { key: "math_computation", label: "Math Computation", icon: "Calculator", group: "stem" },
                                    { key: "geometry_visual", label: "Geometry & Measurement", icon: "Triangle", group: "stem" },
                                    { key: "graphing", label: "Graphing", icon: "LineChart", group: "stem" },
                                    { key: "data_analysis", label: "Data Analysis", icon: "BarChart3", group: "stem" },
                                    { key: "extended_writing", label: "Extended Writing", icon: "FileText", group: "optional" },
                                    { key: "vocabulary", label: "Vocabulary", icon: "BookOpen", group: "optional" },
                                    { key: "true_false", label: "True / False", icon: "ToggleLeft", group: "optional" },
                                    { key: "florida_fast", label: "FL FAST Items", icon: "ListChecks", group: "optional" },
                                  ].map((cat, idx, arr) => {
                                    const prevGroup = idx > 0 ? arr[idx - 1].group : null;
                                    const showDivider = cat.group !== prevGroup;
                                    const groupLabels = { core: "Core", stem: "STEM", optional: "Optional" };
                                    const groupColors = { core: "#22c55e", stem: "#6366f1", optional: "var(--text-muted)" };
                                    return (
                                      <div key={cat.key}>
                                        {showDivider && (
                                          <div style={{
                                            fontSize: "0.65rem", fontWeight: 700, textTransform: "uppercase",
                                            letterSpacing: "0.05em", color: groupColors[cat.group],
                                            marginTop: idx > 0 ? "4px" : 0, marginBottom: "2px",
                                          }}>
                                            {groupLabels[cat.group]}
                                          </div>
                                        )}
                                        <label style={{
                                          display: "flex", alignItems: "center", gap: "8px",
                                          padding: "5px 8px", borderRadius: "6px", cursor: "pointer",
                                          fontSize: "0.82rem",
                                          background: assignmentSectionCategories[cat.key] ? "rgba(99,102,241,0.1)" : "transparent",
                                        }}>
                                          <input
                                            type="checkbox"
                                            checked={!!assignmentSectionCategories[cat.key]}
                                            onChange={(e) => setAssignmentSectionCategories({
                                              ...assignmentSectionCategories,
                                              [cat.key]: e.target.checked,
                                            })}
                                            style={{ accentColor: "#6366f1" }}
                                          />
                                          <Icon name={cat.icon} size={14} />
                                          {cat.label}
                                        </label>
                                      </div>
                                    );
                                  })}
                                </div>
                              )}
                            </div>
                          )}

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
                              : "Brainstorm " + unitConfig.type + " Ideas"}
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
                              ? (unitConfig.type === "Assignment" ? "Creating Assignment..." : "Creating...")
                              : selectedIdea
                                ? "Create from Idea"
                                : "Create"}
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
                            {"Generate 3 " + unitConfig.type + " Variations"}
                          </button>
                        </div>
                      </div>
                    </div>
                    )}

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
                                {unitConfig.type + " Ideas"}
                              </h3>
                              <button
                                onClick={() => { setBrainstormIdeas([]); setSelectedIdea(null); }}
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
                                {(unitConfig.type || "Lesson Plan") + " Variations"}
                              </h2>
                              <p
                                style={{
                                  color: "var(--text-secondary)",
                                  fontSize: "0.9rem",
                                }}
                              >
                                Compare {lessonVariations.length} different
                                approaches for this {(unitConfig.type || "lesson plan").toLowerCase()}
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
                                    <Icon name="Check" size={16} /> {"Use This " + (unitConfig.type || "Plan")}
                                  </button>
                                </div>
                                {/* Content preview - varies by type */}
                                {variation.sections ? (
                                  <div style={{ marginTop: "10px" }}>
                                    <strong
                                      style={{
                                        fontSize: "0.85rem",
                                        color: "var(--text-primary)",
                                      }}
                                    >
                                      Sections:
                                    </strong>
                                    <ul
                                      style={{
                                        margin: "5px 0 0 20px",
                                        fontSize: "0.85rem",
                                        color: "var(--text-secondary)",
                                      }}
                                    >
                                      {variation.sections.map((s, si) => (
                                        <li key={si}>
                                          {s.name} ({s.points || 0} pts, {(s.questions || []).length} questions)
                                        </li>
                                      ))}
                                    </ul>
                                    {variation.total_points && (
                                      <p
                                        style={{
                                          fontSize: "0.8rem",
                                          color: "var(--text-muted)",
                                          marginTop: "5px",
                                        }}
                                      >
                                        Total: {variation.total_points} points
                                      </p>
                                    )}
                                  </div>
                                ) : variation.phases ? (
                                  <div style={{ marginTop: "10px" }}>
                                    <strong
                                      style={{
                                        fontSize: "0.85rem",
                                        color: "var(--text-primary)",
                                      }}
                                    >
                                      Phases:
                                    </strong>
                                    <ul
                                      style={{
                                        margin: "5px 0 0 20px",
                                        fontSize: "0.85rem",
                                        color: "var(--text-secondary)",
                                      }}
                                    >
                                      {variation.phases.map((p, pi) => (
                                        <li key={pi}>
                                          {p.name} ({p.duration})
                                        </li>
                                      ))}
                                    </ul>
                                    {variation.total_points && (
                                      <p
                                        style={{
                                          fontSize: "0.8rem",
                                          color: "var(--text-muted)",
                                          marginTop: "5px",
                                        }}
                                      >
                                        Total: {variation.total_points} points
                                      </p>
                                    )}
                                  </div>
                                ) : (
                                  <>
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
                                  </>
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
                              marginBottom: "25px",
                              borderBottom: "1px solid var(--glass-border)",
                              paddingBottom: "20px",
                            }}
                          >
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
                                marginBottom: "20px",
                              }}
                            >
                              {lessonPlan.overview}
                            </p>
                            <div
                              style={{
                                display: "flex",
                                gap: "10px",
                                alignItems: "center",
                                flexWrap: "wrap",
                              }}
                            >
                              {lessonPlan.sections && !lessonPlan.days ? (
                                /* Assignment-type content: Export PDF, Answer Key, Interactive Preview, Set Up Grading */
                                <>
                                  <button
                                    onClick={async () => {
                                      try {
                                        const result = await api.exportGeneratedAssignment(lessonPlan, "docx", false);
                                        if (result.error) {
                                          addToast("Error: " + result.error, "error");
                                        } else {
                                          addToast("Student worksheet exported as DOCX!", "success");
                                        }
                                      } catch (e) {
                                        addToast("Export failed: " + e.message, "error");
                                      }
                                    }}
                                    className="btn btn-primary"
                                    style={{ padding: "8px 14px" }}
                                    title="Export student version as Word Doc (Graider tables)"
                                  >
                                    <Icon name="FileText" size={16} /> Export DOCX
                                  </button>
                                  <button
                                    onClick={async () => {
                                      try {
                                        const result = await api.exportGeneratedAssignment(lessonPlan, "pdf", false);
                                        if (result.error) {
                                          addToast("Error: " + result.error, "error");
                                        } else {
                                          addToast("Student worksheet exported as PDF!", "success");
                                        }
                                      } catch (e) {
                                        addToast("Export failed: " + e.message, "error");
                                      }
                                    }}
                                    className="btn btn-secondary"
                                    style={{ padding: "8px 14px" }}
                                    title="Export student version as PDF"
                                  >
                                    <Icon name="Download" size={16} /> Export PDF
                                  </button>
                                  <button
                                    onClick={async () => {
                                      try {
                                        const result = await api.exportGeneratedAssignment(lessonPlan, "pdf", true);
                                        if (result.error) {
                                          addToast("Error: " + result.error, "error");
                                        } else {
                                          addToast("Answer key exported as PDF!", "success");
                                        }
                                      } catch (e) {
                                        addToast("Export failed: " + e.message, "error");
                                      }
                                    }}
                                    className="btn btn-secondary"
                                    style={{ padding: "8px 14px" }}
                                    title="Export teacher version with answers as PDF"
                                  >
                                    <Icon name="Key" size={16} /> Answer Key
                                  </button>
                                  <button
                                    onClick={() => setPreviewShowAnswers(prev => !prev)}
                                    className={previewShowAnswers ? "btn btn-primary" : "btn btn-secondary"}
                                    style={{ padding: "8px 14px", ...(previewShowAnswers ? { background: "linear-gradient(135deg, #10b981, #059669)" } : {}) }}
                                    title={previewShowAnswers ? "Hide answer key in preview" : "Show answer key in preview"}
                                  >
                                    <Icon name={previewShowAnswers ? "EyeOff" : "Eye"} size={16} /> {previewShowAnswers ? "Hide Answers" : "Show Answers"}
                                  </button>
                                  <button
                                    onClick={() => {
                                      let gradingNotes = "ANSWER KEY for " + lessonPlan.title + "\n\n";
                                      (lessonPlan.sections || []).forEach((section) => {
                                        gradingNotes += "--- " + section.name + " (" + section.points + " pts) ---\n";
                                        (section.questions || []).forEach((q) => {
                                          gradingNotes += "Q" + q.number + ": " + q.answer + " (" + q.points + " pts)\n";
                                        });
                                        gradingNotes += "\n";
                                      });
                                      if (lessonPlan.rubric?.criteria) {
                                        gradingNotes += "--- Rubric ---\n";
                                        lessonPlan.rubric.criteria.forEach((c) => {
                                          gradingNotes += c.name + " (" + c.points + " pts): " + c.description + "\n";
                                        });
                                      }
                                      const markers = (lessonPlan.sections || []).map((section) => ({
                                        start: section.name + ":",
                                        points: section.points || 10,
                                        type: "written",
                                      }));
                                      setAssignment({
                                        ...assignment,
                                        title: lessonPlan.title || "",
                                        totalPoints: lessonPlan.total_points || 100,
                                        customMarkers: markers,
                                        gradingNotes: gradingNotes.trim(),
                                        useSectionPoints: true,
                                        sectionTemplate: "Custom",
                                      });
                                      setLoadedAssignmentName("");
                                      setActiveTab("builder");
                                      addToast("Assignment loaded into Grading Setup with answer key and section markers", "success");
                                    }}
                                    className="btn btn-primary"
                                    style={{ padding: "8px 14px", background: "linear-gradient(135deg, #6366f1, #8b5cf6)" }}
                                    title="Set up grading configuration for this assignment"
                                  >
                                    <Icon name="Settings" size={16} /> Set Up Grading
                                  </button>
                                  <button
                                    onClick={() => { setEditMode((prev) => !prev); setSelectedQuestions(new Set()); setEditingQuestion(null); }}
                                    className={editMode ? "btn btn-primary" : "btn btn-secondary"}
                                    style={{ padding: "8px 14px", ...(editMode ? { background: "linear-gradient(135deg, #f59e0b, #d97706)" } : {}) }}
                                    title={editMode ? "Exit edit mode" : "Edit individual questions"}
                                  >
                                    <Icon name={editMode ? "X" : "Pencil"} size={16} /> {editMode ? "Exit Edit" : "Edit Questions"}
                                  </button>
                                </>
                              ) : generatedAssignment ? (
                                /* Assignment was created from this lesson — export it as PDF */
                                <>
                                  <button
                                    onClick={async () => {
                                      try {
                                        const result = await api.exportGeneratedAssignment(generatedAssignment, "docx", false);
                                        if (result.error) addToast("Error: " + result.error, "error");
                                        else addToast("Assignment exported as DOCX!", "success");
                                      } catch (e) {
                                        addToast("Export failed: " + e.message, "error");
                                      }
                                    }}
                                    className="btn btn-primary"
                                    style={{ padding: "8px 14px" }}
                                    title="Export student version as Word Doc (Graider tables)"
                                  >
                                    <Icon name="FileText" size={16} /> Export DOCX
                                  </button>
                                  <button
                                    onClick={async () => {
                                      try {
                                        const result = await api.exportGeneratedAssignment(generatedAssignment, "pdf", false);
                                        if (result.error) addToast("Error: " + result.error, "error");
                                        else addToast("Assignment exported as PDF!", "success");
                                      } catch (e) {
                                        addToast("Export failed: " + e.message, "error");
                                      }
                                    }}
                                    className="btn btn-secondary"
                                    style={{ padding: "8px 14px" }}
                                    title="Export assignment as PDF with graphics"
                                  >
                                    <Icon name="Download" size={16} /> Export PDF
                                  </button>
                                  <button
                                    onClick={async () => {
                                      try {
                                        const result = await api.exportGeneratedAssignment(generatedAssignment, "pdf", true);
                                        if (result.error) addToast("Error: " + result.error, "error");
                                        else addToast("Answer key exported as PDF!", "success");
                                      } catch (e) {
                                        addToast("Export failed: " + e.message, "error");
                                      }
                                    }}
                                    className="btn btn-secondary"
                                    style={{ padding: "8px 14px" }}
                                    title="Export teacher version with answers as PDF"
                                  >
                                    <Icon name="Key" size={16} /> Answer Key
                                  </button>
                                  <button
                                    onClick={() => { setEditMode((prev) => !prev); setSelectedQuestions(new Set()); setEditingQuestion(null); }}
                                    className={editMode ? "btn btn-primary" : "btn btn-secondary"}
                                    style={{ padding: "8px 14px", ...(editMode ? { background: "linear-gradient(135deg, #f59e0b, #d97706)" } : {}) }}
                                    title={editMode ? "Exit edit mode" : "Edit individual questions"}
                                  >
                                    <Icon name={editMode ? "X" : "Pencil"} size={16} /> {editMode ? "Exit Edit" : "Edit Questions"}
                                  </button>
                                </>
                              ) : (
                                /* Lesson plan / project: standard Export + Save */
                                <>
                                  <button
                                    onClick={exportLessonPlanHandler}
                                    className="btn btn-secondary"
                                  >
                                    <Icon name="Download" size={16} /> Export
                                  </button>
                                </>
                              )}
                              <button
                                onClick={() => setShowSaveLesson(true)}
                                className="btn btn-secondary"
                                title="Save for use in assessment generation"
                              >
                                <Icon name="FolderPlus" size={16} /> Save to Unit
                              </button>
                              {/* NotebookLM Materials */}
                              <button
                                onClick={function() {
                                  if (!nlmAuthenticated) {
                                    if (confirm("Connect your Google account to NotebookLM? A browser window will open for Google login.")) {
                                      api.notebookLMLogin("start").then(function(res) {
                                        if (res.already_authenticated) {
                                          setNlmAuthenticated(true);
                                          setShowNlmPanel(true);
                                          addToast("Already connected to NotebookLM!", "success");
                                        } else if (res.browser_opened) {
                                          addToast("Complete Google login in the browser window, then come back here.", "info");
                                          // Show a confirm dialog — when user clicks OK, complete the login
                                          var checkLogin = function() {
                                            if (confirm("Click OK after you have logged in to Google in the browser window.")) {
                                              api.notebookLMLogin("complete").then(function(res2) {
                                                if (res2.success) {
                                                  setNlmAuthenticated(true);
                                                  setShowNlmPanel(true);
                                                  addToast("Connected to NotebookLM!", "success");
                                                } else {
                                                  addToast("Login not detected. Try again.", "error");
                                                }
                                              }).catch(function(e) { addToast("Login failed: " + e.message, "error"); });
                                            } else {
                                              api.notebookLMLogin("cancel").catch(function() {});
                                            }
                                          };
                                          // Small delay to let browser open before showing confirm
                                          setTimeout(checkLogin, 1500);
                                        } else if (res.error) {
                                          addToast("Login error: " + res.error, "error");
                                        }
                                      }).catch(function(e) { addToast("Login failed: " + e.message, "error"); });
                                    }
                                  } else {
                                    setShowNlmPanel(function(prev) { return !prev; });
                                  }
                                }}
                                className={showNlmPanel ? "btn btn-primary" : "btn btn-secondary"}
                                style={{ padding: "8px 14px", ...(showNlmPanel ? { background: "linear-gradient(135deg, #ec4899, #8b5cf6)" } : {}) }}
                                title="Generate study materials with NotebookLM"
                              >
                                <Icon name="Sparkles" size={16} /> Materials
                              </button>
                              {/* Hide Create Assignment when already viewing an assignment or project (but show for lesson plans even if they have sections) */}
                              {(!lessonPlan.sections || lessonPlan.days) && !lessonPlan.phases && (
                              <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
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
                              )}
                              <div style={{ flex: 1 }} />
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

                          {/* NotebookLM Materials Panel */}
                          {showNlmPanel && lessonPlan && (
                            <div className="glass-card" style={{ padding: "20px", marginTop: "15px" }}>
                              <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "15px", display: "flex", alignItems: "center", gap: "10px" }}>
                                <Icon name="Sparkles" size={20} /> NotebookLM Materials
                              </h3>
                              <p style={{ color: "var(--text-secondary)", marginBottom: "15px", fontSize: "0.9rem" }}>
                                Generate study materials from your lesson plan using Google NotebookLM.
                              </p>

                              {/* Material type checkboxes */}
                              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "10px", marginBottom: "15px" }}>
                                {NLM_MATERIAL_TYPES.map(function(mt) {
                                  return (
                                    <label key={mt.id} style={{ display: "flex", alignItems: "center", gap: "8px", cursor: "pointer", padding: "8px 10px", borderRadius: "8px", background: nlmSelectedMaterials[mt.id] ? "var(--bg-hover)" : "transparent", transition: "background 0.2s" }}>
                                      <input
                                        type="checkbox"
                                        checked={nlmSelectedMaterials[mt.id]}
                                        onChange={function() { setNlmSelectedMaterials(function(prev) { var next = Object.assign({}, prev); next[mt.id] = !prev[mt.id]; return next; }); }}
                                      />
                                      <Icon name={mt.icon} size={16} />
                                      <span style={{ fontSize: "0.9rem" }}>{mt.label}</span>
                                    </label>
                                  );
                                })}
                              </div>

                              {/* Audio options */}
                              {nlmSelectedMaterials.audio_overview && (
                                <div style={{ display: "flex", gap: "10px", marginBottom: "10px", flexWrap: "wrap" }}>
                                  <div>
                                    <label className="label" style={{ fontSize: "0.8rem" }}>Audio Format</label>
                                    <select className="input" style={{ padding: "6px 10px" }} value={(nlmOptions.audio_overview || {}).format || "deep-dive"} onChange={function(e) { setNlmOptions(function(prev) { return Object.assign({}, prev, { audio_overview: Object.assign({}, prev.audio_overview, { format: e.target.value }) }); }); }}>
                                      <option value="deep-dive">Deep Dive</option>
                                      <option value="brief">Brief Summary</option>
                                      <option value="critique">Critique</option>
                                      <option value="debate">Debate</option>
                                    </select>
                                  </div>
                                  <div>
                                    <label className="label" style={{ fontSize: "0.8rem" }}>Length</label>
                                    <select className="input" style={{ padding: "6px 10px" }} value={(nlmOptions.audio_overview || {}).length || "medium"} onChange={function(e) { setNlmOptions(function(prev) { return Object.assign({}, prev, { audio_overview: Object.assign({}, prev.audio_overview, { length: e.target.value }) }); }); }}>
                                      <option value="short">Short</option>
                                      <option value="medium">Medium</option>
                                      <option value="long">Long</option>
                                    </select>
                                  </div>
                                </div>
                              )}

                              {/* Video options */}
                              {nlmSelectedMaterials.video_overview && (
                                <div style={{ display: "flex", gap: "10px", marginBottom: "10px" }}>
                                  <div>
                                    <label className="label" style={{ fontSize: "0.8rem" }}>Visual Style</label>
                                    <select className="input" style={{ padding: "6px 10px" }} value={(nlmOptions.video_overview || {}).style || "classic"} onChange={function(e) { setNlmOptions(function(prev) { return Object.assign({}, prev, { video_overview: Object.assign({}, prev.video_overview, { style: e.target.value }) }); }); }}>
                                      <option value="classic">Classic</option>
                                      <option value="whiteboard">Whiteboard</option>
                                      <option value="kawaii">Kawaii</option>
                                      <option value="anime">Anime</option>
                                    </select>
                                  </div>
                                </div>
                              )}

                              {/* Custom instructions */}
                              <div style={{ marginBottom: "10px" }}>
                                <label className="label" style={{ fontSize: "0.8rem", marginBottom: "4px" }}>Custom Instructions (optional)</label>
                                <textarea
                                  className="input"
                                  rows={2}
                                  placeholder="e.g., Content is for 6th graders even though standards are 8th grade. Focus on vocabulary. Use simple language for ELL students."
                                  value={(nlmOptions._global || {}).instructions || ""}
                                  onChange={function(e) { setNlmOptions(function(prev) { return Object.assign({}, prev, { _global: Object.assign({}, prev._global, { instructions: e.target.value }) }); }); }}
                                  style={{ width: "100%", fontSize: "0.85rem", resize: "vertical", minHeight: "48px" }}
                                />
                              </div>

                              {/* Reference Document Uploads */}
                              <div style={{ marginBottom: "10px" }}>
                                <label className="label" style={{ fontSize: "0.8rem", marginBottom: "4px" }}>Reference Documents (optional)</label>
                                <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)", margin: "0 0 6px 0" }}>
                                  Add textbook pages, reference docs, or images for richer materials
                                </p>
                                <input
                                  type="file"
                                  id="nlm-context-upload"
                                  multiple
                                  accept=".pdf,.doc,.docx,.png,.jpg,.jpeg,.gif,.webp,.txt"
                                  style={{ display: "none" }}
                                  onChange={async function(e) {
                                    var files = Array.from(e.target.files);
                                    if (files.length === 0) return;
                                    setNlmUploading(true);
                                    try {
                                      for (var i = 0; i < files.length; i++) {
                                        var result = await api.notebookLMUploadContext(files[i]);
                                        if (result.error) {
                                          addToast("Upload failed: " + result.error, "error");
                                        } else {
                                          setNlmContextFiles(function(prev) { return prev.concat([result]); });
                                          setNlmNotebookId(null); // Force new notebook with updated sources
                                        }
                                      }
                                    } catch (err) {
                                      addToast("Upload error: " + err.message, "error");
                                    } finally {
                                      setNlmUploading(false);
                                      e.target.value = "";
                                    }
                                  }}
                                />
                                <button
                                  onClick={function() { document.getElementById("nlm-context-upload").click(); }}
                                  className="btn btn-secondary"
                                  disabled={nlmUploading || nlmGenerating}
                                  style={{ padding: "6px 14px", fontSize: "0.8rem", display: "flex", alignItems: "center", gap: "6px" }}
                                >
                                  {nlmUploading
                                    ? React.createElement(React.Fragment, null, React.createElement(Icon, { name: "Loader", size: 14, className: "spinning" }), " Uploading...")
                                    : React.createElement(React.Fragment, null, React.createElement(Icon, { name: "Upload", size: 14 }), " Add Reference Documents")
                                  }
                                </button>
                                {nlmContextFiles.length > 0 && (
                                  <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginTop: "8px" }}>
                                    {nlmContextFiles.map(function(f, idx) {
                                      var ext = (f.filename || "").split(".").pop().toLowerCase();
                                      var iconName = ["png","jpg","jpeg","gif","webp"].includes(ext) ? "Image" : "FileText";
                                      return (
                                        <div key={idx} style={{
                                          display: "flex", alignItems: "center", gap: "6px",
                                          padding: "4px 10px", borderRadius: "8px",
                                          background: "var(--glass-bg)", border: "1px solid var(--glass-border)",
                                          fontSize: "0.8rem",
                                        }}>
                                          <Icon name={iconName} size={14} style={{ color: "var(--accent-primary)", flexShrink: 0 }} />
                                          <span style={{ maxWidth: "180px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                            {f.filename}
                                          </span>
                                          <span style={{ color: "var(--text-secondary)", fontSize: "0.7rem" }}>
                                            {f.size < 1024 ? f.size + "B" : f.size < 1048576 ? Math.round(f.size / 1024) + "KB" : (f.size / 1048576).toFixed(1) + "MB"}
                                          </span>
                                          <button
                                            onClick={function() {
                                              setNlmContextFiles(function(prev) { return prev.filter(function(_, i) { return i !== idx; }); });
                                              setNlmNotebookId(null);
                                            }}
                                            style={{ background: "none", border: "none", cursor: "pointer", padding: "2px", color: "var(--text-secondary)", lineHeight: 1 }}
                                            title="Remove"
                                          >
                                            <Icon name="X" size={12} />
                                          </button>
                                        </div>
                                      );
                                    })}
                                  </div>
                                )}
                              </div>

                              {/* Generate / Cancel / Retry buttons */}
                              <div style={{ display: "flex", gap: "10px", alignItems: "center", marginTop: "10px", flexWrap: "wrap" }}>
                                <button
                                  onClick={handleNlmGenerate}
                                  className="btn btn-primary"
                                  disabled={nlmGenerating || !Object.values(nlmSelectedMaterials).some(function(v) { return v; })}
                                  style={{ background: "linear-gradient(135deg, #ec4899, #8b5cf6)", padding: "10px 20px" }}
                                >
                                  {nlmGenerating
                                    ? React.createElement(React.Fragment, null, React.createElement(Icon, { name: "Loader", size: 16, className: "spinning" }), " Generating...")
                                    : React.createElement(React.Fragment, null, React.createElement(Icon, { name: "Sparkles", size: 16 }), " Generate Materials")
                                  }
                                </button>
                                {nlmGenerating && (
                                  <button onClick={function() {
                                    api.notebookLMCancel().then(function() {
                                      setNlmGenerating(false);
                                      addToast("Generation cancelled", "info");
                                    });
                                  }} className="btn btn-secondary" style={{ padding: "6px 12px" }}>
                                    <Icon name="X" size={14} /> Cancel
                                  </button>
                                )}
                                {!nlmGenerating && nlmErrors.length > 0 && (
                                  <button onClick={function() {
                                    setNlmGenerating(true);
                                    api.notebookLMRetry(nlmOptions).then(function(data) {
                                      if (data.error) {
                                        addToast(data.error, "error");
                                        setNlmGenerating(false);
                                      }
                                    });
                                  }} className="btn btn-secondary" style={{ padding: "6px 12px", color: "var(--warning)" }}>
                                    <Icon name="RefreshCw" size={14} /> Retry Failed
                                  </button>
                                )}
                                {nlmGenerating && (
                                  <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                                    {nlmCompleted.length} / {nlmTotalSelected} complete
                                  </span>
                                )}
                              </div>

                              {/* Progress */}
                              {nlmProgress.length > 0 && (
                                <div style={{ marginTop: "15px" }}>
                                  {/* Progress bar */}
                                  {nlmGenerating && (
                                    <div style={{ marginBottom: "12px" }}>
                                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
                                        <span style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--text-primary)" }}>
                                          {nlmCompleted.length} of {nlmTotalSelected} materials complete
                                        </span>
                                        <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                                          {nlmTotalSelected > 0 ? Math.round((nlmCompleted.length / nlmTotalSelected) * 100) : 0}%
                                        </span>
                                      </div>
                                      <div style={{ height: "8px", borderRadius: "4px", background: "rgba(139, 92, 246, 0.15)", overflow: "hidden" }}>
                                        <div style={{
                                          height: "100%",
                                          borderRadius: "4px",
                                          background: "linear-gradient(90deg, #8b5cf6, #ec4899)",
                                          width: (nlmTotalSelected > 0 ? Math.round((nlmCompleted.length / nlmTotalSelected) * 100) : 0) + "%",
                                          transition: "width 0.5s ease",
                                        }} />
                                      </div>
                                    </div>
                                  )}
                                  {/* Per-material status */}
                                  {nlmProgress.map(function(msg, i) {
                                    var isDone = nlmCompleted.indexOf(msg.type) !== -1;
                                    var hasError = nlmErrors.some(function(e) { return e.indexOf(msg.type) === 0; });
                                    var isActive = nlmGenerating && !isDone && !hasError && i === nlmProgress.length - 1 + (nlmErrors.length > 0 ? -nlmErrors.length : 0);
                                    var mt = NLM_MATERIAL_TYPES.find(function(m) { return m.id === msg.type; });
                                    return (
                                      <div key={i} style={{
                                        display: "flex", alignItems: "center", gap: "10px",
                                        fontSize: "0.85rem", padding: "6px 10px", marginBottom: "4px", borderRadius: "8px",
                                        background: isDone ? "rgba(34, 197, 94, 0.08)" : hasError ? "rgba(239, 68, 68, 0.08)" : isActive ? "rgba(139, 92, 246, 0.08)" : "transparent",
                                        color: isDone ? "var(--success)" : hasError ? "var(--error)" : "var(--text-secondary)",
                                      }}>
                                        {isDone
                                          ? React.createElement(Icon, { name: "CheckCircle", size: 16 })
                                          : hasError
                                          ? React.createElement(Icon, { name: "XCircle", size: 16 })
                                          : isActive
                                          ? React.createElement(Icon, { name: "Loader", size: 16, className: "spinning" })
                                          : React.createElement(Icon, { name: "Clock", size: 16 })
                                        }
                                        <span style={{ fontWeight: isDone || isActive ? 600 : 400 }}>
                                          {mt ? mt.label : msg.type.replace("_", " ")}
                                        </span>
                                        {isDone && (
                                          <span style={{ marginLeft: "auto", fontSize: "0.75rem", opacity: 0.7 }}>Done</span>
                                        )}
                                        {isActive && (
                                          <span style={{ marginLeft: "auto", fontSize: "0.75rem", opacity: 0.7 }}>Generating...</span>
                                        )}
                                      </div>
                                    );
                                  })}
                                  {nlmErrors.length > 0 && nlmErrors.map(function(err, i) {
                                    return (
                                      <div key={"err-" + i} style={{
                                        display: "flex", alignItems: "center", gap: "10px",
                                        fontSize: "0.85rem", padding: "6px 10px", marginBottom: "4px", borderRadius: "8px",
                                        background: "rgba(239, 68, 68, 0.08)", color: "var(--error)",
                                      }}>
                                        <Icon name="AlertTriangle" size={16} />
                                        <span>{err}</span>
                                      </div>
                                    );
                                  })}
                                </div>
                              )}

                              {/* Completed materials — download/preview */}
                              {nlmCompleted.length > 0 && !nlmGenerating && (
                                <div style={{ marginTop: "15px", borderTop: "1px solid var(--border)", paddingTop: "15px" }}>
                                  <h4 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "10px" }}>Generated Materials</h4>
                                  {nlmCompleted.map(function(type) {
                                    var mt = NLM_MATERIAL_TYPES.find(function(m) { return m.id === type; });
                                    var label = mt ? mt.label : type;
                                    var icon = mt ? mt.icon : "File";
                                    var jsonPreviewable = ["quiz", "flashcards", "mind_map", "study_guide"].indexOf(type) !== -1;
                                    var mediaPreviewable = ["audio_overview", "video_overview", "infographic", "data_table"].indexOf(type) !== -1;
                                    return (
                                      <div key={type} style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "8px" }}>
                                        <Icon name={icon} size={16} />
                                        <span style={{ flex: 1, fontSize: "0.9rem" }}>{label}</span>
                                        <button onClick={function() { api.notebookLMDownload(type); }} className="btn btn-secondary" style={{ padding: "4px 10px", fontSize: "0.8rem" }}>
                                          <Icon name="Download" size={14} /> Download
                                        </button>
                                        {jsonPreviewable && (
                                          <button onClick={function() { handleNlmPreview(type); }} className="btn btn-secondary" style={{ padding: "4px 10px", fontSize: "0.8rem" }}>
                                            <Icon name="Eye" size={14} /> Preview
                                          </button>
                                        )}
                                        {mediaPreviewable && (
                                          <button onClick={function() {
                                            setNlmPreviewData({ type: type, mediaUrl: "/api/notebooklm/download/" + type + "?inline=1" });
                                          }} className="btn btn-secondary" style={{ padding: "4px 10px", fontSize: "0.8rem" }}>
                                            <Icon name="Eye" size={14} /> Preview
                                          </button>
                                        )}
                                      </div>
                                    );
                                  })}
                                </div>
                              )}

                              {/* Inline preview */}
                              {nlmPreviewData && (
                                <div style={{ marginTop: "15px", borderTop: "1px solid var(--border)", paddingTop: "15px" }}>
                                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
                                    <h4 style={{ fontSize: "1rem", fontWeight: 600 }}>Preview: {(nlmPreviewData.type || "").replace(/_/g, " ")}</h4>
                                    <button onClick={function() { setNlmPreviewData(null); }} className="btn btn-secondary" style={{ padding: "4px 8px" }}>
                                      <Icon name="X" size={14} />
                                    </button>
                                  </div>
                                  {/* Mind map — visual tree */}
                                  {nlmPreviewData.type === "mind_map" && nlmPreviewData.data && (
                                    <div style={{ background: "var(--bg-secondary)", borderRadius: "12px", border: "1px solid var(--border)" }}>
                                      <MindMapView data={nlmPreviewData.data} />
                                    </div>
                                  )}
                                  {/* Study guide — rendered markdown */}
                                  {nlmPreviewData.type === "study_guide" && nlmPreviewData.content && (
                                    <div style={{ background: "var(--bg-secondary)", padding: "20px", borderRadius: "12px", fontSize: "0.9rem", maxHeight: "500px", overflow: "auto", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
                                      {nlmPreviewData.content}
                                    </div>
                                  )}
                                  {/* Flashcards — interactive flip cards */}
                                  {nlmPreviewData.type === "flashcards" && nlmPreviewData.data && (
                                    <div style={{ background: "var(--bg-secondary)", borderRadius: "12px", border: "1px solid var(--border)", padding: "16px" }}>
                                      <FlashcardView data={nlmPreviewData.data} />
                                    </div>
                                  )}
                                  {/* Quiz — formatted list */}
                                  {nlmPreviewData.type === "quiz" && nlmPreviewData.data && (
                                    <div style={{ maxHeight: "500px", overflow: "auto" }}>
                                      {(Array.isArray(nlmPreviewData.data) ? nlmPreviewData.data : nlmPreviewData.data.questions || nlmPreviewData.data.cards || [nlmPreviewData.data]).map(function(item, idx) {
                                        return (
                                          <div key={idx} style={{
                                            background: "var(--bg-secondary)", padding: "14px 16px", borderRadius: "10px",
                                            marginBottom: "8px", border: "1px solid var(--border)",
                                          }}>
                                            <div style={{ fontWeight: 600, fontSize: "0.9rem", marginBottom: "6px" }}>
                                              {"Q" + (idx + 1)}
                                            </div>
                                            <div style={{ fontSize: "0.85rem", color: "var(--text-primary)" }}>
                                              {item.question || item.front || item.term || item.text || JSON.stringify(item)}
                                            </div>
                                            {(item.answer || item.back || item.definition || item.correct_answer) && (
                                              <div style={{ marginTop: "8px", padding: "8px 12px", borderRadius: "8px", background: "rgba(34, 197, 94, 0.08)", fontSize: "0.85rem", color: "var(--success)" }}>
                                                <strong>Answer:</strong> {item.answer || item.back || item.definition || item.correct_answer}
                                              </div>
                                            )}
                                            {item.options && (
                                              <div style={{ marginTop: "6px", fontSize: "0.83rem" }}>
                                                {item.options.map(function(opt, oi) {
                                                  var isCorrect = opt === item.answer || opt === item.correct_answer || oi === item.correct_index;
                                                  return (
                                                    <div key={oi} style={{ padding: "3px 0", color: isCorrect ? "var(--success)" : "var(--text-secondary)" }}>
                                                      {String.fromCharCode(65 + oi)}) {typeof opt === "string" ? opt : opt.text || JSON.stringify(opt)}
                                                      {isCorrect ? " " + String.fromCharCode(10003) : ""}
                                                    </div>
                                                  );
                                                })}
                                              </div>
                                            )}
                                          </div>
                                        );
                                      })}
                                    </div>
                                  )}
                                  {/* Audio player */}
                                  {nlmPreviewData.type === "audio_overview" && nlmPreviewData.mediaUrl && (
                                    <div style={{ background: "var(--bg-secondary)", padding: "20px", borderRadius: "12px", textAlign: "center" }}>
                                      <audio controls style={{ width: "100%" }} src={nlmPreviewData.mediaUrl}>
                                        Your browser does not support the audio element.
                                      </audio>
                                    </div>
                                  )}
                                  {/* Video player */}
                                  {nlmPreviewData.type === "video_overview" && nlmPreviewData.mediaUrl && (
                                    <div style={{ background: "var(--bg-secondary)", padding: "12px", borderRadius: "12px", textAlign: "center" }}>
                                      <video controls style={{ width: "100%", maxHeight: "400px", borderRadius: "8px" }} src={nlmPreviewData.mediaUrl}>
                                        Your browser does not support the video element.
                                      </video>
                                    </div>
                                  )}
                                  {/* Infographic image */}
                                  {nlmPreviewData.type === "infographic" && nlmPreviewData.mediaUrl && (
                                    <div style={{ background: "var(--bg-secondary)", padding: "12px", borderRadius: "12px", textAlign: "center", maxHeight: "500px", overflow: "auto" }}>
                                      <img src={nlmPreviewData.mediaUrl} alt="Infographic" style={{ maxWidth: "100%", borderRadius: "8px" }} />
                                    </div>
                                  )}
                                  {/* Data table from CSV */}
                                  {nlmPreviewData.type === "data_table" && nlmPreviewData.mediaUrl && (
                                    <DataTablePreview url={nlmPreviewData.mediaUrl} />
                                  )}
                                  {/* Fallback — raw JSON */}
                                  {!["mind_map", "study_guide", "quiz", "flashcards", "audio_overview", "video_overview", "infographic", "data_table"].includes(nlmPreviewData.type) && (
                                    <pre style={{ background: "var(--bg-secondary)", padding: "15px", borderRadius: "8px", fontSize: "0.85rem", maxHeight: "400px", overflow: "auto", whiteSpace: "pre-wrap" }}>
                                      {nlmPreviewData.content || JSON.stringify(nlmPreviewData.data, null, 2)}
                                    </pre>
                                  )}
                                </div>
                              )}
                            </div>
                          )}

                          {/* Standards aligned to this content */}
                          {selectedStandards.length > 0 && lessonPlan.sections && (
                            <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginBottom: "12px" }}>
                              {selectedStandards.map((code) => {
                                const std = standards.find((s) => s.code === code);
                                return (
                                  <span
                                    key={code}
                                    title={std?.benchmark || code}
                                    style={{
                                      padding: "3px 8px",
                                      background: "rgba(139,92,246,0.15)",
                                      color: "#a78bfa",
                                      borderRadius: "8px",
                                      fontSize: "0.75rem",
                                      fontWeight: 500,
                                      maxWidth: "280px",
                                      overflow: "hidden",
                                      textOverflow: "ellipsis",
                                      whiteSpace: "nowrap",
                                    }}
                                  >
                                    {code}{std?.benchmark ? ": " + std.benchmark : ""}
                                  </span>
                                );
                              })}
                            </div>
                          )}

                          {/* Content display - varies by type */}
                          {lessonPlan.sections && !lessonPlan.days ? (
                            /* Assignment display - interactive AssignmentPlayer */
                            <>
                              {editMode && (
                                <QuestionEditToolbar
                                  selectedCount={selectedQuestions.size}
                                  totalCount={getTotalQuestionCount()}
                                  onSelectAll={selectAllQuestions}
                                  onDeselectAll={() => setSelectedQuestions(new Set())}
                                  onDeleteSelected={deleteSelectedQuestions}
                                  onRegenerateSelected={regenerateSelectedQuestions}
                                  onDoneEditing={() => { setEditMode(false); setSelectedQuestions(new Set()); setEditingQuestion(null); }}
                                  isRegenerating={regeneratingQuestions.size > 0}
                                />
                              )}
                              <AssignmentPlayer
                                assignment={lessonPlan}
                                showAnswers={previewShowAnswers}
                                results={previewResults}
                                editMode={editMode}
                                selectedQuestions={selectedQuestions}
                                editingQuestion={editingQuestion}
                                regeneratingQuestions={regeneratingQuestions}
                                onToggleSelect={toggleQuestionSelect}
                                onStartEdit={setEditingQuestion}
                                onSaveEdit={saveEditedQuestion}
                                onCancelEdit={() => setEditingQuestion(null)}
                                onRegenerateOne={regenerateOneQuestion}
                                onSubmit={async (answers) => {
                                  try {
                                    const published = await api.publishAssignment(lessonPlan);
                                    const result = await api.submitAssignment(published.assignment_id, answers, "Teacher Preview");
                                    setPreviewResults(result.results);
                                    addToast("Assignment graded! Score: " + result.results.percent + "%", "success");
                                  } catch (err) { addToast("Error grading: " + err.message, "error"); }
                                }}
                              />
                            </>
                          ) : lessonPlan.phases ? (
                            /* Project display - phases with tasks */
                            <div
                              style={{
                                display: "flex",
                                flexDirection: "column",
                                gap: "20px",
                              }}
                            >
                              {lessonPlan.driving_question && (
                                <div
                                  style={{
                                    background: "rgba(99,102,241,0.1)",
                                    borderRadius: "12px",
                                    padding: "15px",
                                    border: "1px solid rgba(99,102,241,0.2)",
                                  }}
                                >
                                  <strong style={{ color: "#818cf8" }}>Driving Question:</strong>{" "}
                                  <span style={{ fontSize: "0.95rem" }}>{lessonPlan.driving_question}</span>
                                </div>
                              )}
                              {lessonPlan.total_points && (
                                <p style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                                  Total: {lessonPlan.total_points} points
                                </p>
                              )}
                              {(lessonPlan.phases || []).map((phase, i) => (
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
                                      marginBottom: "15px",
                                      paddingBottom: "10px",
                                      borderBottom: "1px solid var(--glass-border)",
                                    }}
                                  >
                                    <div
                                      style={{
                                        width: "40px",
                                        height: "40px",
                                        borderRadius: "10px",
                                        background: "linear-gradient(135deg, #10b981, #06b6d4)",
                                        display: "flex",
                                        alignItems: "center",
                                        justifyContent: "center",
                                        fontWeight: 700,
                                        fontSize: "1rem",
                                        flexShrink: 0,
                                      }}
                                    >
                                      {phase.phase || i + 1}
                                    </div>
                                    <div style={{ flex: 1 }}>
                                      <h3 style={{ fontSize: "1.2rem", fontWeight: 600, marginBottom: "4px" }}>
                                        {phase.name}
                                      </h3>
                                      <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                                        {phase.duration}
                                      </span>
                                    </div>
                                  </div>
                                  <p style={{ fontSize: "0.9rem", marginBottom: "10px", lineHeight: 1.5 }}>
                                    {phase.description}
                                  </p>
                                  {phase.tasks && (
                                    <ul style={{ margin: "0 0 10px 20px", fontSize: "0.9rem", color: "var(--text-secondary)" }}>
                                      {phase.tasks.map((t, ti) => (
                                        <li key={ti} style={{ marginBottom: "4px" }}>{t}</li>
                                      ))}
                                    </ul>
                                  )}
                                  {phase.deliverable && (
                                    <p style={{ fontSize: "0.85rem", color: "#10b981" }}>
                                      <strong>Deliverable:</strong> {phase.deliverable}
                                    </p>
                                  )}
                                </div>
                              ))}
                              {lessonPlan.final_deliverable && (
                                <div
                                  style={{
                                    background: "rgba(16,185,129,0.1)",
                                    borderRadius: "16px",
                                    padding: "20px",
                                    border: "1px solid rgba(16,185,129,0.2)",
                                  }}
                                >
                                  <h3 style={{ fontSize: "1.1rem", fontWeight: 600, marginBottom: "10px", color: "#10b981" }}>
                                    <Icon name="Award" size={16} style={{ marginRight: "8px", verticalAlign: "middle" }} />
                                    Final Deliverable
                                  </h3>
                                  <p style={{ fontSize: "0.9rem", marginBottom: "8px" }}>
                                    <strong>Format:</strong> {lessonPlan.final_deliverable.format}
                                  </p>
                                  {lessonPlan.final_deliverable.requirements && (
                                    <ul style={{ margin: "0 0 0 20px", fontSize: "0.9rem", color: "var(--text-secondary)" }}>
                                      {lessonPlan.final_deliverable.requirements.map((r, ri) => (
                                        <li key={ri}>{r}</li>
                                      ))}
                                    </ul>
                                  )}
                                </div>
                              )}
                              {lessonPlan.rubric && lessonPlan.rubric.criteria && (
                                <div
                                  style={{
                                    background: "var(--input-bg)",
                                    borderRadius: "16px",
                                    padding: "20px",
                                  }}
                                >
                                  <h3 style={{ fontSize: "1.1rem", fontWeight: 600, marginBottom: "10px" }}>
                                    <Icon name="ClipboardList" size={16} style={{ marginRight: "8px", verticalAlign: "middle" }} />
                                    Rubric
                                  </h3>
                                  {lessonPlan.rubric.criteria.map((c, ci) => (
                                    <div key={ci} style={{ marginBottom: "10px", paddingBottom: "10px", borderBottom: ci < lessonPlan.rubric.criteria.length - 1 ? "1px solid var(--glass-border)" : "none" }}>
                                      <strong style={{ fontSize: "0.9rem" }}>{c.name}</strong>
                                      <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginLeft: "8px" }}>({c.points} pts)</span>
                                      <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginTop: "4px" }}>{c.description}</p>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          ) : (
                            /* Lesson Plan / Unit Plan display - days */
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
                          )}

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
                                  {selectedStandards.length > 0 && (
                                    <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginTop: "8px" }}>
                                      {selectedStandards.map((code) => {
                                        const std = standards.find((s) => s.code === code);
                                        return (
                                          <span
                                            key={code}
                                            title={std?.benchmark || code}
                                            style={{
                                              padding: "3px 8px",
                                              background: "rgba(139,92,246,0.15)",
                                              color: "#a78bfa",
                                              borderRadius: "8px",
                                              fontSize: "0.75rem",
                                              fontWeight: 500,
                                              maxWidth: "280px",
                                              overflow: "hidden",
                                              textOverflow: "ellipsis",
                                              whiteSpace: "nowrap",
                                            }}
                                          >
                                            {code}{std?.benchmark ? ": " + std.benchmark : ""}
                                          </span>
                                        );
                                      })}
                                    </div>
                                  )}
                                </div>
                                <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                                  <button
                                    onClick={async () => {
                                      try {
                                        const result =
                                          await api.exportGeneratedAssignment(
                                            generatedAssignment,
                                            "docx",
                                            false,
                                          );
                                        if (result.error) {
                                          addToast(
                                            "Error: " + result.error,
                                            "error",
                                          );
                                        } else {
                                          addToast(
                                            "Student worksheet exported as DOCX!",
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
                                    title="Export student version as Word Doc (Graider tables)"
                                  >
                                    <Icon name="FileText" size={16} />
                                    Export DOCX
                                  </button>
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
                                    className="btn btn-secondary"
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
                                    onClick={() => setPreviewShowAnswers(prev => !prev)}
                                    className={previewShowAnswers ? "btn btn-primary" : "btn btn-secondary"}
                                    style={{ padding: "8px 14px", ...(previewShowAnswers ? { background: "linear-gradient(135deg, #10b981, #059669)" } : {}) }}
                                    title={previewShowAnswers ? "Hide answer key in preview" : "Show answer key in preview"}
                                  >
                                    <Icon name={previewShowAnswers ? "EyeOff" : "Eye"} size={16} />
                                    {previewShowAnswers ? " Hide Answers" : " Show Answers"}
                                  </button>
                                  <button
                                    onClick={() => {
                                      // Build answer key as grading notes
                                      let gradingNotes = "ANSWER KEY for " + generatedAssignment.title + "\n\n";
                                      (generatedAssignment.sections || []).forEach((section) => {
                                        gradingNotes += "--- " + section.name + " (" + section.points + " pts) ---\n";
                                        (section.questions || []).forEach((q) => {
                                          gradingNotes += "Q" + q.number + ": " + q.answer + " (" + q.points + " pts)\n";
                                        });
                                        gradingNotes += "\n";
                                      });
                                      if (generatedAssignment.rubric?.criteria) {
                                        gradingNotes += "--- Rubric ---\n";
                                        generatedAssignment.rubric.criteria.forEach((c) => {
                                          gradingNotes += c.name + " (" + c.points + " pts): " + c.description + "\n";
                                        });
                                      }

                                      // Map sections to customMarkers, normalized so markers + effort = 100
                                      const effortPts = assignment.effortPoints ?? 15;
                                      const rawMarkers = (generatedAssignment.sections || []).map((section) => ({
                                        start: section.name + ":",
                                        points: section.points || 10,
                                        type: "written",
                                      }));
                                      const rawTotal = rawMarkers.reduce((sum, m) => sum + m.points, 0);
                                      const available = 100 - effortPts;
                                      const markers = rawTotal > 0 && rawTotal !== available
                                        ? rawMarkers.map((m) => ({
                                            ...m,
                                            points: Math.round((m.points / rawTotal) * available),
                                          }))
                                        : rawMarkers;
                                      // Fix rounding drift so total is exactly 100
                                      const markerSum = markers.reduce((s, m) => s + m.points, 0);
                                      if (markers.length > 0 && markerSum !== available) {
                                        markers[0].points += available - markerSum;
                                      }

                                      setAssignment({
                                        ...assignment,
                                        title: generatedAssignment.title || "",
                                        totalPoints: generatedAssignment.total_points || 100,
                                        customMarkers: markers,
                                        effortPoints: effortPts,
                                        gradingNotes: gradingNotes.trim(),
                                        useSectionPoints: true,
                                        sectionTemplate: "Custom",
                                      });
                                      setLoadedAssignmentName("");
                                      setActiveTab("builder");
                                      addToast("Assignment loaded into Grading Setup with answer key and section markers", "success");
                                    }}
                                    className="btn btn-primary"
                                    style={{
                                      padding: "8px 14px",
                                      background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
                                    }}
                                    title="Set up grading configuration for this assignment"
                                  >
                                    <Icon name="Settings" size={16} />
                                    Set Up Grading
                                  </button>
                                  <button
                                    onClick={() => { setEditMode((prev) => !prev); setSelectedQuestions(new Set()); setEditingQuestion(null); }}
                                    className={editMode ? "btn btn-primary" : "btn btn-secondary"}
                                    style={{ padding: "8px 14px", ...(editMode ? { background: "linear-gradient(135deg, #f59e0b, #d97706)" } : {}) }}
                                    title={editMode ? "Exit edit mode" : "Edit individual questions"}
                                  >
                                    <Icon name={editMode ? "X" : "Pencil"} size={16} />
                                    {editMode ? " Exit Edit" : " Edit Questions"}
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

                              {editMode && (
                                <QuestionEditToolbar
                                  selectedCount={selectedQuestions.size}
                                  totalCount={getTotalQuestionCount()}
                                  onSelectAll={selectAllQuestions}
                                  onDeselectAll={() => setSelectedQuestions(new Set())}
                                  onDeleteSelected={deleteSelectedQuestions}
                                  onRegenerateSelected={regenerateSelectedQuestions}
                                  onDoneEditing={() => { setEditMode(false); setSelectedQuestions(new Set()); setEditingQuestion(null); }}
                                  isRegenerating={regeneratingQuestions.size > 0}
                                />
                              )}
                              <AssignmentPlayer
                                assignment={generatedAssignment}
                                showAnswers={previewShowAnswers}
                                results={previewResults}
                                editMode={editMode}
                                selectedQuestions={selectedQuestions}
                                editingQuestion={editingQuestion}
                                regeneratingQuestions={regeneratingQuestions}
                                onToggleSelect={toggleQuestionSelect}
                                onStartEdit={setEditingQuestion}
                                onSaveEdit={saveEditedQuestion}
                                onCancelEdit={() => setEditingQuestion(null)}
                                onRegenerateOne={regenerateOneQuestion}
                                onSubmit={async (answers) => {
                                  try {
                                    const published = await api.publishAssignment(generatedAssignment);
                                    const result = await api.submitAssignment(published.assignment_id, answers, "Teacher Preview");
                                    setPreviewResults(result.results);
                                    addToast("Assignment graded! Score: " + result.results.percent + "%", "success");
                                  } catch (err) { addToast("Error grading: " + err.message, "error"); }
                                }}
                              />

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

                          {/* Domain jump bar */}
                          {standards.length > 0 && getDomains(standards).length > 1 && (
                            <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginBottom: "10px" }}>
                              {getDomains(standards).map((domain) => {
                                const count = selectedStandards.filter((c) => c.split(".")[2] === domain).length;
                                return (
                                  <button key={domain} onClick={() => scrollToDomain(standardsScrollRef, domain)}
                                    style={{
                                      padding: "4px 10px", fontSize: "0.75rem", fontWeight: 600,
                                      borderRadius: "20px", border: "none", cursor: "pointer",
                                      background: count > 0 ? "rgba(139, 92, 246, 0.2)" : "var(--glass-bg)",
                                      color: count > 0 ? "#a78bfa" : "var(--text-secondary)",
                                      transition: "all 0.2s",
                                    }}
                                  >
                                    {domainNameMap[domain] || domain}{count > 0 ? " (" + count + ")" : ""}
                                  </button>
                                );
                              })}
                            </div>
                          )}

                          <div
                            ref={standardsScrollRef}
                            style={{ maxHeight: "500px", overflowY: "auto" }}
                          >
                            {plannerLoading && standards.length === 0 ? (
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
                                <div key={std.code} data-domain={std.code.split(".")[2]}>
                                <StandardCard
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
                                </div>
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

                        {/* Section Categories Dropdown */}
                        <div className="glass-card" style={{ padding: "20px" }}>
                          <button
                            type="button"
                            onClick={() => setSectionsDropdownOpen(!sectionsDropdownOpen)}
                            style={{
                              width: "100%",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "space-between",
                              background: "none",
                              border: "none",
                              cursor: "pointer",
                              padding: 0,
                              color: "inherit",
                            }}
                          >
                            <h3
                              style={{
                                fontSize: "1rem",
                                fontWeight: 700,
                                margin: 0,
                                display: "flex",
                                alignItems: "center",
                                gap: "10px",
                              }}
                            >
                              <Icon name="LayoutGrid" size={18} /> Assessment Sections
                              <span style={{
                                fontSize: "0.75rem",
                                fontWeight: 400,
                                color: "var(--text-muted)",
                                marginLeft: "4px",
                              }}>
                                ({Object.values(assessmentConfig.sectionCategories || {}).filter(Boolean).length} active)
                              </span>
                            </h3>
                            <Icon name={sectionsDropdownOpen ? "ChevronUp" : "ChevronDown"} size={18} />
                          </button>

                          {sectionsDropdownOpen && (
                            <div style={{ marginTop: "15px", display: "flex", flexDirection: "column", gap: "10px" }}>
                              <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "4px" }}>
                                Select which sections to include. FL FAST-aligned defaults are pre-selected.
                              </p>

                              {[
                                { key: "multiple_choice", label: "Multiple Choice", desc: "Standard MC questions", icon: "CheckCircle", group: "core" },
                                { key: "short_answer", label: "Short Answer / Gridded Response", desc: "Text & numeric input", icon: "AlignLeft", group: "core" },
                                { key: "math_computation", label: "Math Computation", desc: "Equations, solve for x, expressions", icon: "Calculator", group: "stem" },
                                { key: "geometry_visual", label: "Geometry & Measurement", desc: "Interactive shapes, protractor, transformations", icon: "Triangle", group: "stem" },
                                { key: "graphing", label: "Graphing & Coordinate Plane", desc: "Number lines, function graphs, plotting", icon: "LineChart", group: "stem" },
                                { key: "data_analysis", label: "Data Analysis", desc: "Data tables, box plots, dot plots, stem-and-leaf", icon: "BarChart3", group: "stem" },
                                { key: "extended_writing", label: "Extended Writing / Essay", desc: "Paragraph responses with analysis", icon: "FileText", group: "optional" },
                                { key: "vocabulary", label: "Vocabulary / Matching", desc: "Term-definition matching", icon: "BookOpen", group: "optional" },
                                { key: "true_false", label: "True / False", desc: "Statement evaluation", icon: "ToggleLeft", group: "optional" },
                                { key: "florida_fast", label: "FL FAST Item Types", desc: "Multiselect, multi-part, grid match, inline dropdown", icon: "ListChecks", group: "optional" },
                              ].map((cat, idx, arr) => {
                                const prevGroup = idx > 0 ? arr[idx - 1].group : null;
                                const showDivider = cat.group !== prevGroup;
                                const groupLabels = { core: "FL FAST Core", stem: "STEM Visuals", optional: "Optional" };
                                return (
                                  <div key={cat.key}>
                                    {showDivider && (
                                      <div style={{
                                        fontSize: "0.7rem",
                                        fontWeight: 700,
                                        textTransform: "uppercase",
                                        letterSpacing: "0.05em",
                                        color: cat.group === "stem" ? "#6366f1" : cat.group === "optional" ? "var(--text-muted)" : "#22c55e",
                                        marginTop: idx > 0 ? "8px" : 0,
                                        marginBottom: "4px",
                                      }}>
                                        {groupLabels[cat.group]}
                                      </div>
                                    )}
                                    <label
                                      style={{
                                        display: "flex",
                                        alignItems: "center",
                                        gap: "10px",
                                        padding: "8px 10px",
                                        borderRadius: "8px",
                                        cursor: "pointer",
                                        background: assessmentConfig.sectionCategories?.[cat.key]
                                          ? "rgba(99, 102, 241, 0.1)"
                                          : "transparent",
                                        border: "1px solid " + (assessmentConfig.sectionCategories?.[cat.key]
                                          ? "rgba(99, 102, 241, 0.3)"
                                          : "rgba(255,255,255,0.05)"),
                                        transition: "all 0.2s",
                                      }}
                                    >
                                      <input
                                        type="checkbox"
                                        checked={!!assessmentConfig.sectionCategories?.[cat.key]}
                                        onChange={(e) => {
                                          const newCats = {
                                            ...assessmentConfig.sectionCategories,
                                            [cat.key]: e.target.checked,
                                          };
                                          // Redistribute questions based on new categories
                                          const newTypes = distributeQuestions(
                                            assessmentConfig.totalQuestions || 20,
                                            newCats
                                          );
                                          const newPointsPerType = distributePoints(
                                            assessmentConfig.totalPoints || 30,
                                            newTypes
                                          );
                                          setAssessmentConfig({
                                            ...assessmentConfig,
                                            sectionCategories: newCats,
                                            questionTypes: newTypes,
                                            pointsPerType: newPointsPerType,
                                          });
                                        }}
                                        style={{ accentColor: "#6366f1" }}
                                      />
                                      <Icon name={cat.icon} size={16} />
                                      <div style={{ flex: 1 }}>
                                        <div style={{ fontSize: "0.9rem", fontWeight: 500 }}>{cat.label}</div>
                                        <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{cat.desc}</div>
                                      </div>
                                    </label>
                                  </div>
                                );
                              })}
                            </div>
                          )}
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
                              { key: "math_equation", label: "Math Equation (STEM)", defaultPts: 2 },
                              { key: "data_table", label: "Data Table (STEM)", defaultPts: 3 },
                              { key: "multiselect", label: "Multiselect (FAST)", defaultPts: 2 },
                              { key: "multi_part", label: "Multi-Part (FAST)", defaultPts: 2 },
                              { key: "grid_match", label: "Grid Match (FAST)", defaultPts: 3 },
                              { key: "inline_dropdown", label: "Inline Dropdown (FAST)", defaultPts: 2 },
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
                          {/* Domain jump bar */}
                          {standards.length > 0 && getDomains(standards).length > 1 && (
                            <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginBottom: "10px" }}>
                              {getDomains(standards).map((domain) => {
                                const count = selectedStandards.filter((c) => c.split(".")[2] === domain).length;
                                return (
                                  <button key={domain} onClick={() => scrollToDomain(assessmentStandardsScrollRef, domain)}
                                    style={{
                                      padding: "4px 10px", fontSize: "0.75rem", fontWeight: 600,
                                      borderRadius: "20px", border: "none", cursor: "pointer",
                                      background: count > 0 ? "rgba(139, 92, 246, 0.2)" : "var(--glass-bg)",
                                      color: count > 0 ? "#a78bfa" : "var(--text-secondary)",
                                      transition: "all 0.2s",
                                    }}
                                  >
                                    {domainNameMap[domain] || domain}{count > 0 ? " (" + count + ")" : ""}
                                  </button>
                                );
                              })}
                            </div>
                          )}

                          <div
                            ref={assessmentStandardsScrollRef}
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
                                  data-domain={std.code.split(".")[2]}
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
                                    alignItems: "center",
                                  }}
                                >
                                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                                    <Icon name="Award" size={14} />
                                    <input
                                      type="number"
                                      min="1"
                                      value={generatedAssessment.total_points}
                                      onChange={(e) => {
                                        const newTotal = parseInt(e.target.value) || 1;
                                        redistributePoints(newTotal);
                                      }}
                                      style={{
                                        width: "60px",
                                        padding: "4px 8px",
                                        background: "rgba(255,255,255,0.1)",
                                        border: "1px solid var(--glass-border)",
                                        borderRadius: "6px",
                                        color: "var(--text-primary)",
                                        fontSize: "0.9rem",
                                        textAlign: "center",
                                      }}
                                    />
                                    <span>points</span>
                                  </div>
                                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                                    <Icon name="Clock" size={14} />
                                    {generatedAssessment.time_limit != null ? (
                                      <>
                                        <input
                                          type="number"
                                          min="1"
                                          value={generatedAssessment.time_limit}
                                          onChange={(e) => {
                                            const val = parseInt(e.target.value);
                                            setGeneratedAssessment({ ...generatedAssessment, time_limit: val > 0 ? val : 1 });
                                          }}
                                          style={{
                                            width: "60px",
                                            padding: "4px 8px",
                                            background: "rgba(255,255,255,0.1)",
                                            border: "1px solid var(--glass-border)",
                                            borderRadius: "6px",
                                            color: "var(--text-primary)",
                                            fontSize: "0.9rem",
                                            textAlign: "center",
                                          }}
                                        />
                                        <span>min</span>
                                        <button
                                          onClick={() => setGeneratedAssessment({ ...generatedAssessment, time_limit: null })}
                                          style={{
                                            background: "none",
                                            border: "none",
                                            color: "var(--text-muted)",
                                            cursor: "pointer",
                                            padding: "2px 4px",
                                            fontSize: "0.85rem",
                                            lineHeight: 1,
                                          }}
                                          title="Remove time limit"
                                        >
                                          ✕
                                        </button>
                                      </>
                                    ) : (
                                      <button
                                        onClick={() => setGeneratedAssessment({ ...generatedAssessment, time_limit: 30 })}
                                        style={{
                                          background: "none",
                                          border: "none",
                                          color: "var(--accent-secondary)",
                                          cursor: "pointer",
                                          padding: "0",
                                          fontSize: "0.85rem",
                                          textDecoration: "none",
                                        }}
                                        onMouseEnter={(e) => e.target.style.textDecoration = "underline"}
                                        onMouseLeave={(e) => e.target.style.textDecoration = "none"}
                                      >
                                        + Set time limit
                                      </button>
                                    )}
                                  </div>
                                  <span>
                                    {generatedAssessment.sections?.reduce(
                                      (sum, s) => sum + (s.questions?.length || 0),
                                      0
                                    )}{" "}
                                    questions
                                  </span>
                                </div>
                              </div>
                              <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", marginTop: "15px" }}>
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
                                <button
                                  onClick={() => { setEditMode((prev) => !prev); setSelectedQuestions(new Set()); setEditingQuestion(null); }}
                                  className={editMode ? "btn btn-primary" : "btn btn-secondary"}
                                  style={{ padding: "8px 16px", ...(editMode ? { background: "linear-gradient(135deg, #f59e0b, #d97706)" } : {}) }}
                                  title={editMode ? "Exit edit mode" : "Edit individual questions"}
                                >
                                  <Icon name={editMode ? "X" : "Pencil"} size={16} />
                                  {editMode ? " Exit Edit" : " Edit Questions"}
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

                            {/* Edit Toolbar */}
                            {editMode && (
                              <QuestionEditToolbar
                                selectedCount={selectedQuestions.size}
                                totalCount={getTotalQuestionCount()}
                                onSelectAll={selectAllQuestions}
                                onDeselectAll={() => setSelectedQuestions(new Set())}
                                onDeleteSelected={deleteSelectedQuestions}
                                onRegenerateSelected={regenerateSelectedQuestions}
                                onDoneEditing={() => { setEditMode(false); setSelectedQuestions(new Set()); setEditingQuestion(null); }}
                                isRegenerating={regeneratingQuestions.size > 0}
                              />
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
                                  {section.questions?.map((q, qIdx) => {
                                    const qCard = (
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
                                      {/* Quality warning badge */}
                                      {q.warning && (
                                        <div style={{
                                          padding: "6px 10px",
                                          background: q.warning_severity === "error" ? "rgba(239,68,68,0.15)" : q.warning_severity === "info" ? "rgba(59,130,246,0.15)" : "rgba(245,158,11,0.15)",
                                          border: q.warning_severity === "error" ? "1px solid rgba(239,68,68,0.3)" : q.warning_severity === "info" ? "1px solid rgba(59,130,246,0.3)" : "1px solid rgba(245,158,11,0.3)",
                                          borderRadius: "6px",
                                          fontSize: "0.8rem",
                                          color: q.warning_severity === "error" ? "#ef4444" : q.warning_severity === "info" ? "#3b82f6" : "#f59e0b",
                                          display: "flex",
                                          alignItems: "center",
                                          gap: "6px",
                                          marginBottom: "8px",
                                        }}>
                                          <Icon name="AlertTriangle" size={14} />
                                          {q.warning}
                                        </div>
                                      )}
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
                                      {/* Matching - Interactive card game */}
                                      {q.type === "matching" && q.terms && q.definitions && (
                                        <MatchingCards
                                          terms={q.terms}
                                          definitions={q.definitions}
                                          showAnswers={previewShowAnswers}
                                          onMatch={function(matches) {
                                            var newAnswers = Object.assign({}, assessmentAnswers);
                                            Object.entries(matches).forEach(function(entry) {
                                              var tIdx = entry[0];
                                              var matchKey = sIdx + "-" + qIdx + "-match-" + tIdx;
                                              newAnswers[matchKey] = String.fromCharCode(65 + parseInt(tIdx));
                                            });
                                            setAssessmentAnswers(newAnswers);
                                          }}
                                        />
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
                                    );
                                    return editMode ? (
                                      <QuestionEditOverlay
                                        key={qIdx}
                                        question={q}
                                        sectionIndex={sIdx}
                                        questionIndex={qIdx}
                                        isSelected={selectedQuestions.has(sIdx + "-" + qIdx)}
                                        isEditing={editingQuestion === sIdx + "-" + qIdx}
                                        isRegenerating={regeneratingQuestions.has(sIdx + "-" + qIdx)}
                                        onToggleSelect={toggleQuestionSelect}
                                        onStartEdit={setEditingQuestion}
                                        onSaveEdit={saveEditedQuestion}
                                        onCancelEdit={() => setEditingQuestion(null)}
                                        onRegenerateOne={regenerateOneQuestion}
                                      >
                                        {qCard}
                                      </QuestionEditOverlay>
                                    ) : qCard;
                                  })}
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
                              className="btn btn-secondary"
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
                            className="btn btn-secondary"
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

                  {/* Calendar Mode */}
                  {plannerMode === "calendar" && (
                    <div className="fade-in">
                      {/* Calendar Header */}
                      <div className="glass-card" style={{ padding: "16px 20px", marginBottom: "20px", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "12px" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                          <button
                            onClick={() => {
                              const d = new Date(calendarMonth)
                              d.setMonth(d.getMonth() - 1)
                              setCalendarMonth(d)
                            }}
                            style={{ background: "var(--glass-bg)", border: "1px solid var(--glass-border)", borderRadius: "8px", padding: "6px 10px", cursor: "pointer", color: "var(--text-primary)" }}
                          >
                            <Icon name="ChevronLeft" size={18} />
                          </button>
                          <h3 style={{ fontSize: "1.2rem", fontWeight: 700, margin: 0, minWidth: "180px", textAlign: "center" }}>
                            {calendarMonth.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}
                          </h3>
                          <button
                            onClick={() => {
                              const d = new Date(calendarMonth)
                              d.setMonth(d.getMonth() + 1)
                              setCalendarMonth(d)
                            }}
                            style={{ background: "var(--glass-bg)", border: "1px solid var(--glass-border)", borderRadius: "8px", padding: "6px 10px", cursor: "pointer", color: "var(--text-primary)" }}
                          >
                            <Icon name="ChevronRight" size={18} />
                          </button>
                          <button
                            onClick={() => setCalendarMonth(new Date())}
                            className="btn btn-secondary"
                            style={{ padding: "6px 14px", fontSize: "0.8rem" }}
                          >
                            Today
                          </button>
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                          <div style={{ display: "flex", borderRadius: "8px", overflow: "hidden", border: "1px solid var(--glass-border)" }}>
                            <button
                              onClick={() => setCalendarView('month')}
                              style={{
                                padding: "6px 14px", fontSize: "0.8rem", cursor: "pointer", border: "none",
                                background: calendarView === 'month' ? 'var(--accent-primary)' : 'var(--glass-bg)',
                                color: calendarView === 'month' ? '#fff' : 'var(--text-secondary)',
                                fontWeight: 600,
                              }}
                            >
                              Month
                            </button>
                            <button
                              onClick={() => setCalendarView('week')}
                              style={{
                                padding: "6px 14px", fontSize: "0.8rem", cursor: "pointer", border: "none",
                                background: calendarView === 'week' ? 'var(--accent-primary)' : 'var(--glass-bg)',
                                color: calendarView === 'week' ? '#fff' : 'var(--text-secondary)',
                                fontWeight: 600,
                              }}
                            >
                              Week
                            </button>
                          </div>
                          <button
                            onClick={() => { setHolidayForm({ date: '', name: '', end_date: '' }); setShowHolidayModal(true) }}
                            className="btn btn-secondary"
                            style={{ padding: "6px 14px", fontSize: "0.8rem" }}
                          >
                            <Icon name="CalendarOff" size={14} />
                            Add Holiday
                          </button>
                          <button
                            onClick={async () => {
                              setImportEvents([])
                              setImportChecked({})
                              setImportSelectedDoc('')
                              setShowImportModal(true)
                              if (supportDocs.length === 0) {
                                try {
                                  const data = await api.listSupportDocuments()
                                  if (data.documents) setSupportDocs(data.documents)
                                } catch (e) { /* ignore */ }
                              }
                            }}
                            className="btn btn-secondary"
                            style={{ padding: "6px 14px", fontSize: "0.8rem" }}
                          >
                            <Icon name="FileUp" size={14} />
                            Import
                          </button>
                        </div>
                      </div>

                      {/* Month View */}
                      {calendarView === 'month' && (() => {
                        const days = getCalendarDays(calendarMonth)
                        const today = new Date()
                        const todayStr = today.getFullYear() + '-' + String(today.getMonth() + 1).padStart(2, '0') + '-' + String(today.getDate()).padStart(2, '0')
                        return (
                          <div style={{ display: "grid", gridTemplateColumns: "repeat(7, minmax(0, 1fr))", gap: "2px" }}>
                            {/* Day headers */}
                            {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(d => (
                              <div key={d} style={{ textAlign: "center", fontSize: "0.75rem", fontWeight: 600, color: "var(--text-secondary)", padding: "6px" }}>
                                {d}
                              </div>
                            ))}
                            {/* Day cells */}
                              {days.map((cell, idx) => {
                                if (!cell) return <div key={'blank-' + idx} style={{ minHeight: "100px" }} />
                                const holiday = isHoliday(cell.date)
                                const lessons = getLessonsForDate(cell.date)
                                const school = isSchoolDay(cell.dow)
                                const isToday = cell.date === todayStr
                                return (
                                  <div
                                    key={cell.date}
                                    onDragOver={e => e.preventDefault()}
                                    onDrop={e => {
                                      e.preventDefault()
                                      if (calendarDragId) {
                                        const entry = (calendarData.scheduled_lessons || []).find(s => s.id === calendarDragId)
                                        if (entry) scheduleLesson({ ...entry, date: cell.date })
                                        setCalendarDragId(null)
                                      }
                                    }}
                                    onClick={() => {
                                      if (!holiday && school) {
                                        setQuickAddForm({ title: '', unit: '', color: '#6366f1' })
                                        setSelectedCalendarDate(cell.date)
                                      }
                                    }}
                                    style={{
                                      minHeight: "100px",
                                      background: holiday ? "rgba(239, 68, 68, 0.08)" : !school ? "rgba(100,100,100,0.05)" : isToday ? "rgba(99, 102, 241, 0.08)" : "var(--glass-bg)",
                                      border: isToday ? "2px solid var(--accent-primary)" : "1px solid var(--glass-border)",
                                      borderRadius: "8px",
                                      padding: "6px",
                                      cursor: !holiday && school ? "pointer" : "default",
                                      opacity: !school ? 0.5 : 1,
                                      transition: "all 0.15s",
                                    }}
                                  >
                                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                                      <span style={{ fontSize: "0.8rem", fontWeight: isToday ? 700 : 500, color: isToday ? "var(--accent-primary)" : "var(--text-primary)" }}>
                                        {cell.day}
                                      </span>
                                    </div>
                                    {holiday && (
                                      <div style={{
                                        fontSize: "0.7rem", padding: "2px 6px", borderRadius: "6px",
                                        background: "rgba(239, 68, 68, 0.2)", color: "#ef4444", fontWeight: 600,
                                        display: "flex", alignItems: "center", gap: "3px", marginBottom: "3px", justifyContent: "space-between",
                                      }}>
                                        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{holiday.name}</span>
                                        <button
                                          onClick={e => { e.stopPropagation(); removeHoliday(holiday.date) }}
                                          style={{ background: "none", border: "none", color: "#ef4444", cursor: "pointer", padding: 0, lineHeight: 1, flexShrink: 0 }}
                                        >
                                          <Icon name="X" size={10} />
                                        </button>
                                      </div>
                                    )}
                                    {lessons.map(lesson => (
                                      <div
                                        key={lesson.id}
                                        draggable
                                        onDragStart={() => setCalendarDragId(lesson.id)}
                                        onDragEnd={() => setCalendarDragId(null)}
                                        onClick={e => {
                                          e.stopPropagation()
                                          setEditingEvent({ ...lesson })
                                        }}
                                        style={{
                                          fontSize: "0.7rem", padding: "3px 6px", borderRadius: "6px",
                                          background: lesson.color || "#6366f1", color: "#fff", fontWeight: 500,
                                          marginBottom: "2px", cursor: "pointer", display: "flex", alignItems: "center",
                                          justifyContent: "space-between", gap: "2px",
                                        }}
                                      >
                                        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                          {lesson.day_number ? 'D' + lesson.day_number + ': ' : ''}{lesson.lesson_title}
                                        </span>
                                        <button
                                          onClick={e => { e.stopPropagation(); unscheduleLesson(lesson.id) }}
                                          style={{ background: "none", border: "none", color: "rgba(255,255,255,0.7)", cursor: "pointer", padding: 0, lineHeight: 1, flexShrink: 0 }}
                                        >
                                          <Icon name="X" size={10} />
                                        </button>
                                      </div>
                                    ))}
                                  </div>
                                )
                              })}
                          </div>
                        )
                      })()}

                      {/* Week View */}
                      {calendarView === 'week' && (() => {
                        const weekStart = getStartOfWeek(calendarMonth)
                        const days = getWeekDays(weekStart)
                        const today = new Date()
                        const todayStr = today.getFullYear() + '-' + String(today.getMonth() + 1).padStart(2, '0') + '-' + String(today.getDate()).padStart(2, '0')
                        return (
                          <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: "8px" }}>
                            {days.map(cell => {
                              const holiday = isHoliday(cell.date)
                              const lessons = getLessonsForDate(cell.date)
                              const school = isSchoolDay(cell.dow)
                              const isToday = cell.date === todayStr
                              const dayLabel = cell.fullDate.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
                              return (
                                <div
                                  key={cell.date}
                                  onDragOver={e => e.preventDefault()}
                                  onDrop={e => {
                                    e.preventDefault()
                                    if (calendarDragId) {
                                      const entry = (calendarData.scheduled_lessons || []).find(s => s.id === calendarDragId)
                                      if (entry) scheduleLesson({ ...entry, date: cell.date })
                                      setCalendarDragId(null)
                                    }
                                  }}
                                  onClick={() => {
                                    if (!holiday && school) {
                                      setQuickAddForm({ title: '', unit: '', color: '#6366f1' })
                                      setSelectedCalendarDate(cell.date)
                                    }
                                  }}
                                  className="glass-card"
                                  style={{
                                    minHeight: "280px", padding: "12px",
                                    opacity: !school ? 0.4 : 1,
                                    border: isToday ? "2px solid var(--accent-primary)" : undefined,
                                    background: holiday ? "rgba(239, 68, 68, 0.08)" : undefined,
                                    cursor: !holiday && school ? "pointer" : "default",
                                  }}
                                >
                                  <div style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: "10px", color: isToday ? "var(--accent-primary)" : "var(--text-primary)" }}>
                                    {dayLabel}
                                  </div>
                                  {holiday && (
                                    <div style={{
                                      fontSize: "0.8rem", padding: "6px 10px", borderRadius: "8px",
                                      background: "rgba(239, 68, 68, 0.15)", color: "#ef4444", fontWeight: 600,
                                      marginBottom: "8px", display: "flex", alignItems: "center", gap: "6px",
                                    }}>
                                      <Icon name="CalendarOff" size={14} />
                                      {holiday.name}
                                    </div>
                                  )}
                                  {lessons.map(lesson => (
                                    <div
                                      key={lesson.id}
                                      draggable
                                      onDragStart={() => setCalendarDragId(lesson.id)}
                                      onDragEnd={() => setCalendarDragId(null)}
                                      onClick={e => {
                                        e.stopPropagation()
                                        setEditingEvent({ ...lesson })
                                      }}
                                      style={{
                                        padding: "8px 10px", borderRadius: "8px",
                                        background: lesson.color || "#6366f1", color: "#fff",
                                        marginBottom: "6px", cursor: "pointer",
                                      }}
                                    >
                                      <div style={{ fontSize: "0.8rem", fontWeight: 600, marginBottom: "2px" }}>
                                        {lesson.day_number ? 'Day ' + lesson.day_number + ': ' : ''}{lesson.lesson_title}
                                      </div>
                                      {lesson.unit && <div style={{ fontSize: "0.7rem", opacity: 0.8 }}>{lesson.unit}</div>}
                                      <div style={{ display: "flex", gap: "6px", marginTop: "4px" }}>
                                        <button
                                          onClick={e => { e.stopPropagation(); setEditingEvent({ ...lesson }) }}
                                          style={{ background: "rgba(255,255,255,0.2)", border: "none", color: "#fff", cursor: "pointer", padding: "2px 6px", borderRadius: "4px", fontSize: "0.7rem" }}
                                        >
                                          Edit
                                        </button>
                                        <button
                                          onClick={e => { e.stopPropagation(); unscheduleLesson(lesson.id) }}
                                          style={{ background: "rgba(255,255,255,0.2)", border: "none", color: "#fff", cursor: "pointer", padding: "2px 6px", borderRadius: "4px", fontSize: "0.7rem" }}
                                        >
                                          Remove
                                        </button>
                                      </div>
                                    </div>
                                  ))}
                                  {!holiday && school && lessons.length === 0 && (
                                    <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", fontStyle: "italic", textAlign: "center", marginTop: "40px" }}>
                                      Click to add event
                                    </div>
                                  )}
                                </div>
                              )
                            })}
                          </div>
                        )
                      })()}

                      {/* Add Event / Schedule Lesson Modal */}
                      {selectedCalendarDate && (
                        <div
                          style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(0,0,0,0.6)", zIndex: 10000, display: "flex", alignItems: "center", justifyContent: "center", padding: "20px" }}
                          onClick={() => setSelectedCalendarDate(null)}
                        >
                          <div
                            className="glass-card"
                            style={{ maxWidth: "500px", width: "100%", padding: "24px", maxHeight: "80vh", overflowY: "auto" }}
                            onClick={e => e.stopPropagation()}
                          >
                            <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "4px", display: "flex", alignItems: "center", gap: "8px" }}>
                              <Icon name="CalendarPlus" size={20} style={{ color: "var(--accent-primary)" }} />
                              Add Event
                            </h3>
                            <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "16px" }}>
                              {new Date(selectedCalendarDate + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}
                            </p>

                            {/* Quick Add Custom Event */}
                            <div style={{ padding: "14px", background: "var(--glass-bg)", border: "1px solid var(--glass-border)", borderRadius: "10px", marginBottom: "16px" }}>
                              <div style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: "10px", display: "flex", alignItems: "center", gap: "6px", color: "var(--text-primary)" }}>
                                <Icon name="Plus" size={14} />
                                Custom Event
                              </div>
                              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                                <input
                                  type="text"
                                  value={quickAddForm.title}
                                  onChange={e => setQuickAddForm(prev => ({ ...prev, title: e.target.value }))}
                                  placeholder="Event title (e.g., Unit 5 Test, Lab Day)"
                                  style={{ width: "100%", padding: "8px 12px", background: "var(--input-bg)", border: "1px solid var(--input-border)", borderRadius: "8px", color: "var(--text-primary)", fontSize: "0.9rem" }}
                                  onKeyDown={e => {
                                    if (e.key === 'Enter' && quickAddForm.title.trim()) {
                                      scheduleLesson({ date: selectedCalendarDate, lesson_title: quickAddForm.title.trim(), unit: quickAddForm.unit.trim(), color: quickAddForm.color })
                                      setSelectedCalendarDate(null)
                                    }
                                  }}
                                  autoFocus
                                />
                                <div style={{ display: "flex", gap: "8px" }}>
                                  <input
                                    type="text"
                                    value={quickAddForm.unit}
                                    onChange={e => setQuickAddForm(prev => ({ ...prev, unit: e.target.value }))}
                                    placeholder="Unit (optional)"
                                    style={{ flex: 1, padding: "8px 12px", background: "var(--input-bg)", border: "1px solid var(--input-border)", borderRadius: "8px", color: "var(--text-primary)", fontSize: "0.85rem" }}
                                  />
                                  <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                                    {['#6366f1', '#8b5cf6', '#ec4899', '#f59e0b', '#22c55e', '#06b6d4', '#ef4444'].map(c => (
                                      <button
                                        key={c}
                                        onClick={() => setQuickAddForm(prev => ({ ...prev, color: c }))}
                                        style={{
                                          width: 22, height: 22, borderRadius: "6px", background: c, border: quickAddForm.color === c ? "2px solid #fff" : "2px solid transparent",
                                          cursor: "pointer", outline: quickAddForm.color === c ? "2px solid " + c : "none", padding: 0,
                                        }}
                                      />
                                    ))}
                                  </div>
                                </div>
                                <button
                                  onClick={() => {
                                    if (quickAddForm.title.trim()) {
                                      scheduleLesson({ date: selectedCalendarDate, lesson_title: quickAddForm.title.trim(), unit: quickAddForm.unit.trim(), color: quickAddForm.color })
                                      setSelectedCalendarDate(null)
                                    }
                                  }}
                                  className="btn btn-primary"
                                  style={{ width: "100%", padding: "8px" }}
                                  disabled={!quickAddForm.title.trim()}
                                >
                                  Add Event
                                </button>
                              </div>
                            </div>

                            {/* Saved Lessons Section */}
                            {Object.keys(savedLessons.units || {}).length > 0 && (
                              <>
                                <div style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "8px", display: "flex", alignItems: "center", gap: "6px" }}>
                                  <Icon name="BookOpen" size={14} />
                                  Or pick from saved lessons
                                </div>
                                <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                                  {Object.entries(savedLessons.units || {}).map(([unitName, unitLessons]) => (
                                    <div key={unitName}>
                                      <div style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "4px", display: "flex", alignItems: "center", gap: "6px" }}>
                                        <Icon name="FolderOpen" size={14} />
                                        {unitName}
                                      </div>
                                      {unitLessons.map((lesson, li) => {
                                        const unitColors = ['#6366f1', '#8b5cf6', '#ec4899', '#f59e0b', '#22c55e', '#06b6d4', '#ef4444']
                                        const colorIdx = Object.keys(savedLessons.units).indexOf(unitName) % unitColors.length
                                        return (
                                          <button
                                            key={li}
                                            onClick={() => {
                                              scheduleLesson({
                                                date: selectedCalendarDate,
                                                unit: unitName,
                                                lesson_title: lesson.title,
                                                lesson_file: unitName + '/' + lesson.filename + '.json',
                                                color: unitColors[colorIdx],
                                              })
                                              setSelectedCalendarDate(null)
                                            }}
                                            style={{
                                              width: "100%", textAlign: "left", padding: "10px 14px",
                                              background: "var(--glass-bg)", border: "1px solid var(--glass-border)",
                                              borderRadius: "8px", cursor: "pointer", color: "var(--text-primary)",
                                              fontSize: "0.85rem", marginBottom: "4px",
                                              display: "flex", alignItems: "center", gap: "8px",
                                              transition: "all 0.15s",
                                            }}
                                            onMouseEnter={e => { e.currentTarget.style.borderColor = "var(--accent-primary)"; e.currentTarget.style.background = "var(--glass-hover)" }}
                                            onMouseLeave={e => { e.currentTarget.style.borderColor = "var(--glass-border)"; e.currentTarget.style.background = "var(--glass-bg)" }}
                                          >
                                            <div style={{ width: 8, height: 8, borderRadius: "50%", background: unitColors[colorIdx], flexShrink: 0 }} />
                                            {lesson.title}
                                          </button>
                                        )
                                      })}
                                    </div>
                                  ))}
                                </div>
                              </>
                            )}
                            <button
                              onClick={() => setSelectedCalendarDate(null)}
                              className="btn btn-secondary"
                              style={{ marginTop: "16px", width: "100%" }}
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      )}

                      {/* Edit Event Modal */}
                      {editingEvent && (
                        <div
                          style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(0,0,0,0.6)", zIndex: 10000, display: "flex", alignItems: "center", justifyContent: "center", padding: "20px" }}
                          onClick={() => setEditingEvent(null)}
                        >
                          <div
                            className="glass-card"
                            style={{ maxWidth: "460px", width: "100%", padding: "24px" }}
                            onClick={e => e.stopPropagation()}
                          >
                            <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "16px", display: "flex", alignItems: "center", gap: "8px" }}>
                              <Icon name="Pencil" size={20} style={{ color: "var(--accent-primary)" }} />
                              Edit Event
                            </h3>
                            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                              <div>
                                <label style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: "4px" }}>Title</label>
                                <input
                                  type="text"
                                  value={editingEvent.lesson_title || ''}
                                  onChange={e => setEditingEvent(prev => ({ ...prev, lesson_title: e.target.value }))}
                                  style={{ width: "100%", padding: "8px 12px", background: "var(--input-bg)", border: "1px solid var(--input-border)", borderRadius: "8px", color: "var(--text-primary)", fontSize: "0.9rem" }}
                                  autoFocus
                                />
                              </div>
                              <div>
                                <label style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: "4px" }}>Date</label>
                                <input
                                  type="date"
                                  value={editingEvent.date || ''}
                                  onChange={e => setEditingEvent(prev => ({ ...prev, date: e.target.value }))}
                                  style={{ width: "100%", padding: "8px 12px", background: "var(--input-bg)", border: "1px solid var(--input-border)", borderRadius: "8px", color: "var(--text-primary)", fontSize: "0.9rem" }}
                                />
                              </div>
                              <div>
                                <label style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: "4px" }}>Unit</label>
                                <input
                                  type="text"
                                  value={editingEvent.unit || ''}
                                  onChange={e => setEditingEvent(prev => ({ ...prev, unit: e.target.value }))}
                                  placeholder="Unit name (optional)"
                                  style={{ width: "100%", padding: "8px 12px", background: "var(--input-bg)", border: "1px solid var(--input-border)", borderRadius: "8px", color: "var(--text-primary)", fontSize: "0.9rem" }}
                                />
                              </div>
                              <div>
                                <label style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: "6px" }}>Color</label>
                                <div style={{ display: "flex", gap: "6px" }}>
                                  {['#6366f1', '#8b5cf6', '#ec4899', '#f59e0b', '#22c55e', '#06b6d4', '#ef4444'].map(c => (
                                    <button
                                      key={c}
                                      onClick={() => setEditingEvent(prev => ({ ...prev, color: c }))}
                                      style={{
                                        width: 28, height: 28, borderRadius: "8px", background: c, border: (editingEvent.color || '#6366f1') === c ? "2px solid #fff" : "2px solid transparent",
                                        cursor: "pointer", outline: (editingEvent.color || '#6366f1') === c ? "2px solid " + c : "none", padding: 0,
                                      }}
                                    />
                                  ))}
                                </div>
                              </div>
                              <div style={{ display: "flex", gap: "8px", marginTop: "8px" }}>
                                <button
                                  onClick={() => {
                                    if (editingEvent.lesson_title && editingEvent.date) {
                                      scheduleLesson(editingEvent)
                                      setEditingEvent(null)
                                    }
                                  }}
                                  className="btn btn-primary"
                                  style={{ flex: 1 }}
                                  disabled={!editingEvent.lesson_title || !editingEvent.date}
                                >
                                  Save Changes
                                </button>
                                <button
                                  onClick={() => {
                                    unscheduleLesson(editingEvent.id)
                                    setEditingEvent(null)
                                  }}
                                  className="btn btn-secondary"
                                  style={{ color: "#ef4444" }}
                                >
                                  <Icon name="Trash2" size={14} />
                                  Delete
                                </button>
                                <button
                                  onClick={() => setEditingEvent(null)}
                                  className="btn btn-secondary"
                                >
                                  Cancel
                                </button>
                              </div>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* Add Holiday Modal */}
                      {showHolidayModal && (
                        <div
                          style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(0,0,0,0.6)", zIndex: 10000, display: "flex", alignItems: "center", justifyContent: "center", padding: "20px" }}
                          onClick={() => setShowHolidayModal(false)}
                        >
                          <div
                            className="glass-card"
                            style={{ maxWidth: "400px", width: "100%", padding: "24px" }}
                            onClick={e => e.stopPropagation()}
                          >
                            <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "16px", display: "flex", alignItems: "center", gap: "8px" }}>
                              <Icon name="CalendarOff" size={20} style={{ color: "#ef4444" }} />
                              Add Holiday / Break
                            </h3>
                            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                              <div>
                                <label style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: "4px" }}>Name</label>
                                <input
                                  type="text"
                                  value={holidayForm.name}
                                  onChange={e => setHolidayForm(prev => ({ ...prev, name: e.target.value }))}
                                  placeholder="e.g., Spring Break"
                                  style={{ width: "100%", padding: "8px 12px", background: "var(--input-bg)", border: "1px solid var(--input-border)", borderRadius: "8px", color: "var(--text-primary)", fontSize: "0.9rem" }}
                                />
                              </div>
                              <div>
                                <label style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: "4px" }}>Start Date</label>
                                <input
                                  type="date"
                                  value={holidayForm.date}
                                  onChange={e => setHolidayForm(prev => ({ ...prev, date: e.target.value }))}
                                  style={{ width: "100%", padding: "8px 12px", background: "var(--input-bg)", border: "1px solid var(--input-border)", borderRadius: "8px", color: "var(--text-primary)", fontSize: "0.9rem" }}
                                />
                              </div>
                              <div>
                                <label style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: "4px" }}>End Date (for multi-day breaks)</label>
                                <input
                                  type="date"
                                  value={holidayForm.end_date}
                                  onChange={e => setHolidayForm(prev => ({ ...prev, end_date: e.target.value }))}
                                  style={{ width: "100%", padding: "8px 12px", background: "var(--input-bg)", border: "1px solid var(--input-border)", borderRadius: "8px", color: "var(--text-primary)", fontSize: "0.9rem" }}
                                />
                              </div>
                              <div style={{ display: "flex", gap: "8px", marginTop: "8px" }}>
                                <button
                                  onClick={() => {
                                    if (holidayForm.date && holidayForm.name) {
                                      addHoliday(holidayForm)
                                      setShowHolidayModal(false)
                                    }
                                  }}
                                  className="btn btn-primary"
                                  style={{ flex: 1 }}
                                  disabled={!holidayForm.date || !holidayForm.name}
                                >
                                  Add Holiday
                                </button>
                                <button
                                  onClick={() => setShowHolidayModal(false)}
                                  className="btn btn-secondary"
                                  style={{ flex: 1 }}
                                >
                                  Cancel
                                </button>
                              </div>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* Import Document Modal */}
                      {showImportModal && (
                        <div
                          style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(0,0,0,0.6)", zIndex: 10000, display: "flex", alignItems: "center", justifyContent: "center", padding: "20px" }}
                          onClick={() => setShowImportModal(false)}
                        >
                          <div
                            className="glass-card"
                            style={{ maxWidth: "560px", width: "100%", padding: "24px", maxHeight: "80vh", display: "flex", flexDirection: "column" }}
                            onClick={e => e.stopPropagation()}
                          >
                            <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "16px", display: "flex", alignItems: "center", gap: "8px" }}>
                              <Icon name="FileUp" size={20} style={{ color: "var(--accent-primary)" }} />
                              Import Events from Document
                            </h3>

                            {/* Step 1: Select document */}
                            <div style={{ display: "flex", gap: "8px", marginBottom: "16px" }}>
                              <select
                                value={importSelectedDoc}
                                onChange={e => { setImportSelectedDoc(e.target.value); setImportEvents([]); setImportChecked({}) }}
                                style={{ flex: 1, padding: "8px 12px", background: "var(--input-bg)", border: "1px solid var(--input-border)", borderRadius: "8px", color: "var(--text-primary)", fontSize: "0.9rem" }}
                              >
                                <option value="">Select a document...</option>
                                {supportDocs.filter(d => /\.(pdf|docx?)$/i.test(d.filename)).map(d => (
                                  <option key={d.filename} value={d.filename}>{d.filename}</option>
                                ))}
                              </select>
                              <button
                                onClick={async () => {
                                  if (!importSelectedDoc) return
                                  setImportParsing(true)
                                  setImportEvents([])
                                  setImportChecked({})
                                  try {
                                    const data = await api.parseDocumentForCalendar(importSelectedDoc)
                                    if (data.events) {
                                      setImportEvents(data.events)
                                      const checked = {}
                                      data.events.forEach((_, i) => { checked[i] = true })
                                      setImportChecked(checked)
                                    } else if (data.error) {
                                      if (addToast) addToast(data.error, 'error')
                                    }
                                  } catch (e) {
                                    if (addToast) addToast('Failed to parse document', 'error')
                                  } finally {
                                    setImportParsing(false)
                                  }
                                }}
                                className="btn btn-primary"
                                style={{ padding: "8px 16px", fontSize: "0.85rem", whiteSpace: "nowrap" }}
                                disabled={!importSelectedDoc || importParsing}
                              >
                                {importParsing ? 'Parsing...' : 'Parse Document'}
                              </button>
                            </div>

                            {importParsing && (
                              <div style={{ textAlign: "center", padding: "24px 0", color: "var(--text-secondary)", fontSize: "0.9rem" }}>
                                <Icon name="Loader2" size={24} style={{ animation: "spin 1s linear infinite", marginBottom: "8px" }} />
                                <div>AI is extracting events from your document...</div>
                              </div>
                            )}

                            {/* Step 2: Event list with checkboxes */}
                            {importEvents.length > 0 && !importParsing && (
                              <>
                                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                                  <span style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--text-secondary)" }}>
                                    {importEvents.length} events found
                                  </span>
                                  <div style={{ display: "flex", gap: "8px" }}>
                                    <button
                                      onClick={() => {
                                        const all = {}
                                        importEvents.forEach((_, i) => { all[i] = true })
                                        setImportChecked(all)
                                      }}
                                      style={{ background: "none", border: "none", color: "var(--accent-primary)", cursor: "pointer", fontSize: "0.8rem", fontWeight: 600, padding: "2px 6px" }}
                                    >
                                      Select All
                                    </button>
                                    <button
                                      onClick={() => setImportChecked({})}
                                      style={{ background: "none", border: "none", color: "var(--text-secondary)", cursor: "pointer", fontSize: "0.8rem", fontWeight: 600, padding: "2px 6px" }}
                                    >
                                      Deselect All
                                    </button>
                                  </div>
                                </div>
                                <div style={{ flex: 1, overflowY: "auto", maxHeight: "340px", border: "1px solid var(--glass-border)", borderRadius: "8px", marginBottom: "16px" }}>
                                  {importEvents.map((ev, i) => (
                                    <label
                                      key={i}
                                      style={{
                                        display: "flex", alignItems: "center", gap: "10px", padding: "8px 12px",
                                        borderBottom: i < importEvents.length - 1 ? "1px solid var(--glass-border)" : "none",
                                        cursor: "pointer", fontSize: "0.85rem",
                                      }}
                                    >
                                      <input
                                        type="checkbox"
                                        checked={!!importChecked[i]}
                                        onChange={() => setImportChecked(prev => ({ ...prev, [i]: !prev[i] }))}
                                        style={{ accentColor: "var(--accent-primary)" }}
                                      />
                                      <span style={{
                                        display: "inline-block", padding: "2px 8px", borderRadius: "4px", fontSize: "0.7rem", fontWeight: 600,
                                        background: ev.type === 'holiday' ? "rgba(239, 68, 68, 0.15)" : "rgba(99, 102, 241, 0.15)",
                                        color: ev.type === 'holiday' ? "#ef4444" : "#6366f1",
                                        minWidth: "52px", textAlign: "center",
                                      }}>
                                        {ev.type === 'holiday' ? 'Holiday' : 'Lesson'}
                                      </span>
                                      <span style={{ fontWeight: 500, color: "var(--text-primary)", flex: 1 }}>{ev.title}</span>
                                      <span style={{ color: "var(--text-secondary)", fontSize: "0.8rem", whiteSpace: "nowrap" }}>{ev.date}</span>
                                    </label>
                                  ))}
                                </div>
                              </>
                            )}

                            {/* Action buttons */}
                            <div style={{ display: "flex", gap: "8px" }}>
                              {importEvents.length > 0 && !importParsing && (
                                <button
                                  onClick={async () => {
                                    const selected = importEvents.filter((_, i) => importChecked[i])
                                    if (selected.length === 0) return
                                    setImportImporting(true)
                                    try {
                                      const data = await api.importCalendarEvents(selected)
                                      if (data.status === 'imported') {
                                        loadCalendar()
                                        setShowImportModal(false)
                                        if (addToast) addToast('Imported ' + data.lessons_added + ' lessons and ' + data.holidays_added + ' holidays', 'success')
                                      } else if (data.error) {
                                        if (addToast) addToast(data.error, 'error')
                                      }
                                    } catch (e) {
                                      if (addToast) addToast('Failed to import events', 'error')
                                    } finally {
                                      setImportImporting(false)
                                    }
                                  }}
                                  className="btn btn-primary"
                                  style={{ flex: 1 }}
                                  disabled={importImporting || Object.values(importChecked).filter(Boolean).length === 0}
                                >
                                  {importImporting ? 'Importing...' : 'Import ' + Object.values(importChecked).filter(Boolean).length + ' Events'}
                                </button>
                              )}
                              <button
                                onClick={() => setShowImportModal(false)}
                                className="btn btn-secondary"
                                style={{ flex: importEvents.length > 0 && !importParsing ? undefined : 1 }}
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Tools Mode */}
                  {plannerMode === "tools" && (
                    <div className="fade-in" style={{ maxWidth: "800px" }}>
                      <div className="glass-card" style={{ padding: "24px" }}>
                        <h3 style={{ fontSize: "1.2rem", fontWeight: 700, marginBottom: "16px", display: "flex", alignItems: "center", gap: "8px" }}>
                          <Icon name="BookType" size={22} style={{ color: "#06b6d4" }} />
                          Reading Level Adjuster
                        </h3>
                        <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "16px" }}>
                          Paste text and adjust it to a target reading level. Key terms you specify will be preserved exactly.
                        </p>

                        {/* Input textarea */}
                        <textarea
                          value={rlInput}
                          onChange={e => setRlInput(e.target.value)}
                          placeholder="Paste text here to adjust its reading level..."
                          rows={8}
                          style={{ width: "100%", padding: "12px", background: "var(--input-bg)", border: "1px solid var(--input-border)", borderRadius: "8px", color: "var(--text-primary)", fontSize: "0.9rem", resize: "vertical", marginBottom: "16px", fontFamily: "inherit" }}
                        />

                        {/* Controls row */}
                        <div style={{ display: "flex", gap: "12px", alignItems: "flex-end", flexWrap: "wrap", marginBottom: "16px" }}>
                          <div style={{ flex: "0 0 auto" }}>
                            <label style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: "4px" }}>Target Level</label>
                            <select
                              value={rlTargetLevel}
                              onChange={e => setRlTargetLevel(e.target.value)}
                              style={{ padding: "8px 12px", background: "var(--input-bg)", border: "1px solid var(--input-border)", borderRadius: "8px", color: "var(--text-primary)", fontSize: "0.9rem" }}
                            >
                              <option value="2">Grade 2</option>
                              <option value="3">Grade 3</option>
                              <option value="4">Grade 4</option>
                              <option value="5">Grade 5</option>
                              <option value="6">Grade 6</option>
                              <option value="7">Grade 7</option>
                              <option value="8">Grade 8</option>
                              <option value="9">Grade 9</option>
                              <option value="10">Grade 10</option>
                              <option value="11">Grade 11</option>
                              <option value="12">Grade 12</option>
                              <option value="Simplified">Simplified</option>
                              <option value="Advanced/AP">Advanced / AP</option>
                            </select>
                          </div>

                          {/* Preserve terms input */}
                          <div style={{ flex: 1, minWidth: "200px" }}>
                            <label style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: "4px" }}>Key Terms to Preserve</label>
                            <div style={{ display: "flex", gap: "6px" }}>
                              <input
                                type="text"
                                value={rlTermInput}
                                onChange={e => setRlTermInput(e.target.value)}
                                onKeyDown={e => {
                                  if (e.key === 'Enter' && rlTermInput.trim()) {
                                    e.preventDefault()
                                    setRlPreserveTerms(prev => prev.indexOf(rlTermInput.trim()) === -1 ? prev.concat([rlTermInput.trim()]) : prev)
                                    setRlTermInput('')
                                  }
                                }}
                                placeholder="Type term and press Enter"
                                style={{ flex: 1, padding: "8px 12px", background: "var(--input-bg)", border: "1px solid var(--input-border)", borderRadius: "8px", color: "var(--text-primary)", fontSize: "0.9rem" }}
                              />
                            </div>
                          </div>

                          <button
                            onClick={async () => {
                              if (!rlInput.trim()) return
                              setRlLoading(true)
                              setRlResult(null)
                              try {
                                var res = await api.adjustReadingLevel(rlInput, rlTargetLevel, config.subject || '', rlPreserveTerms)
                                if (res.error) {
                                  addToast(res.error, 'error')
                                } else {
                                  setRlResult(res)
                                }
                              } catch (err) {
                                addToast('Error: ' + err.message, 'error')
                              } finally {
                                setRlLoading(false)
                              }
                            }}
                            className="btn btn-primary"
                            disabled={!rlInput.trim() || rlLoading}
                            style={{ padding: "8px 20px", background: "linear-gradient(135deg, #06b6d4, #0891b2)" }}
                          >
                            {rlLoading ? (
                              <><Icon name="Loader2" size={16} className="spin" /> Adjusting...</>
                            ) : (
                              <><Icon name="Wand2" size={16} /> Adjust</>
                            )}
                          </button>
                        </div>

                        {/* Preserve terms tags */}
                        {rlPreserveTerms.length > 0 && (
                          <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginBottom: "16px" }}>
                            {rlPreserveTerms.map(function(term, i) {
                              return (
                                <span key={i} style={{ display: "inline-flex", alignItems: "center", gap: "4px", padding: "3px 10px", background: "rgba(6,182,212,0.12)", color: "#06b6d4", borderRadius: "12px", fontSize: "0.8rem", fontWeight: 500 }}>
                                  {term}
                                  <button
                                    onClick={() => setRlPreserveTerms(prev => prev.filter(function(t) { return t !== term }))}
                                    style={{ background: "none", border: "none", color: "#06b6d4", cursor: "pointer", padding: "0 2px", fontSize: "1rem", lineHeight: 1 }}
                                  >
                                    x
                                  </button>
                                </span>
                              )
                            })}
                          </div>
                        )}

                        {/* Result panel */}
                        {rlResult && (
                          <div style={{ borderTop: "1px solid var(--glass-border)", paddingTop: "16px", marginTop: "8px" }}>
                            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
                              <span style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--text-secondary)" }}>
                                Estimated reading level: <span style={{ color: "#06b6d4", fontWeight: 700 }}>{rlResult.reading_level_estimate}</span>
                              </span>
                              <button
                                onClick={() => {
                                  navigator.clipboard.writeText(rlResult.adjusted_text)
                                  addToast('Copied to clipboard', 'success')
                                }}
                                className="btn btn-secondary"
                                style={{ padding: "4px 12px", fontSize: "0.8rem" }}
                              >
                                <Icon name="Copy" size={14} /> Copy
                              </button>
                            </div>
                            <div style={{ padding: "12px", background: "var(--input-bg)", borderRadius: "8px", fontSize: "0.9rem", lineHeight: 1.6, color: "var(--text-primary)", whiteSpace: "pre-wrap", maxHeight: "300px", overflowY: "auto", marginBottom: "12px" }}>
                              {rlResult.adjusted_text}
                            </div>

                            {/* Vocabulary changes */}
                            {rlResult.vocabulary_changes && rlResult.vocabulary_changes.length > 0 && (
                              <div>
                                <h4 style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "8px" }}>Vocabulary Changes</h4>
                                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "4px 16px", fontSize: "0.8rem" }}>
                                  {rlResult.vocabulary_changes.map(function(vc, i) {
                                    return (
                                      <React.Fragment key={i}>
                                        <span style={{ color: "var(--text-secondary)", textDecoration: "line-through" }}>{vc.original}</span>
                                        <span style={{ color: "#06b6d4", fontWeight: 500 }}>{vc.replacement}</span>
                                      </React.Fragment>
                                    )
                                  })}
                                </div>
                              </div>
                            )}

                            {rlResult.usage && (
                              <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "12px", textAlign: "right" }}>
                                {rlResult.usage.cost_display}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                </div>


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
                      addToast('Lesson saved to "' + unitName + '" — find it in the Resources tab under Content Sources', 'success');
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

    </>
  );
});
