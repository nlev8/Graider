import { useState, useEffect } from "react";
import * as api from "../../services/api";
import { checkRequirementsMismatch } from "../../utils/standardsMismatch";

/*
 * useLessonGeneration — owns the lesson-gen big cluster, relocated verbatim
 * from PlannerTab.jsx (CQ wave-3 split).
 *
 * History: moved App.jsx → PlannerTab in PR 8d of the Planner extraction
 * sprint (deferred-cluster #2 final move). 6 useStates + 2 handlers
 * (brainstormIdeasHandler, generateLessonPlan) + 2 effects (load-standards,
 * subject-change-assignmentQuestionCounts).
 *
 * App-shell deps received as hook args: config, addToast, selectedStandards,
 * uploadedDocs, standards, unitConfig, contentOnly, setLessonPlan,
 * setStandards, activeTab, getSubjectSectionDefaults.
 *
 * Behavior-preserving notes: both effect dependency arrays are byte-identical
 * to the pre-split inline effects ([config.state, config.grade_level,
 * config.subject, activeTab] and [config.subject]); the hook is called
 * unconditionally from the always-the-same position in the PlannerTab shell,
 * so the effects' mount/unmount lifecycle is unchanged. Handlers are
 * intentionally NOT memoized — same as the pre-split plain-const
 * declarations recreated each render.
 */
export default function useLessonGeneration({
  activeTab,
  config,
  addToast,
  selectedStandards,
  uploadedDocs,
  standards,
  setStandards,
  unitConfig,
  contentOnly,
  setLessonPlan,
  getSubjectSectionDefaults,
}) {
  const [plannerLoading, setPlannerLoading] = useState(false);
  const [lessonVariations, setLessonVariations] = useState([]);
  const [brainstormIdeas, setBrainstormIdeas] = useState([]);
  const [selectedIdea, setSelectedIdea] = useState(null);
  const [brainstormLoading, setBrainstormLoading] = useState(false);
  const [assignmentQuestionCounts, setAssignmentQuestionCounts] = useState({
    multiple_choice: 4, short_answer: 2, math_computation: 0,
    geometry_visual: 0, graphing: 0, data_analysis: 0,
    extended_writing: 1, vocabulary: 0, true_false: 0, florida_fast: 0,
  });

  // Load standards when planner tab is active.
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

  // Subject-change effect (assignmentQuestionCounts portion). The
  // assessmentConfig portion of the original combined effect remains in
  // App.jsx — they were independent halves merged by convenience.
  useEffect(() => {
    if (config.subject && getSubjectSectionDefaults) {
      var newCats = getSubjectSectionDefaults(config.subject);
      var assignTotal = 10;
      var enabledCount = Object.values(newCats).filter(Boolean).length || 1;
      var assignNumeric = Object.fromEntries(Object.entries(newCats).map(function(e) { return [e[0], e[1] ? Math.max(1, Math.round(assignTotal / enabledCount)) : 0]; }));
      setAssignmentQuestionCounts(assignNumeric);
    }
  }, [config.subject]);

  const brainstormIdeasHandler = async () => {
    if (!config.subject) {
      addToast("Please select a subject in Settings before generating", "warning");
      return;
    }
    if (!config.grade_level) {
      addToast("Please select a grade level in Settings before generating", "warning");
      return;
    }
    if (selectedStandards.length === 0 && uploadedDocs.length === 0) {
      addToast("Please select at least one standard or upload reference documents", "warning");
      return;
    }
    const mismatchCheck = checkRequirementsMismatch(unitConfig.requirements, selectedStandards, standards);
    if (mismatchCheck.mismatch) addToast(mismatchCheck.message, "warning", 6000);
    setBrainstormLoading(true);
    setBrainstormIdeas([]);
    setSelectedIdea(null);
    setLessonPlan(null);
    setLessonVariations([]);
    try {
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

  const generateLessonPlan = async (generateVariations = false) => {
    if (!config.subject) {
      addToast("Please select a subject in Settings before generating", "warning");
      return;
    }
    if (!config.grade_level) {
      addToast("Please select a grade level in Settings before generating", "warning");
      return;
    }
    if (selectedStandards.length === 0 && uploadedDocs.length === 0) {
      addToast("Please select at least one standard or upload reference documents", "warning");
      return;
    }
    const mismatchCheck = checkRequirementsMismatch(unitConfig.requirements, selectedStandards, standards);
    if (mismatchCheck.mismatch) addToast(mismatchCheck.message, "warning", 6000);
    setPlannerLoading(true);
    setLessonVariations([]);
    try {
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
      const standardCodes = selectedStandards.join(", ");
      const autoTitle =
        unitConfig.title || (selectedIdea ? selectedIdea.title : "");

      const referenceDocs = uploadedDocs.map(doc => ({ filename: doc.filename, text: doc.text }));

      const data = await api.generateLessonPlan({
        standards: fullStandards,
        config: {
          state: config.state || "FL",
          grade: config.grade_level,
          subject: config.subject,
          availableTools: config.availableTools || [],
          ...unitConfig,
          title: autoTitle,
          standardCodes: standardCodes,
          sectionCategories: unitConfig.type === "Assignment" ? Object.fromEntries(Object.entries(assignmentQuestionCounts).map(function(e) { return [e[0], e[1] > 0]; })) : undefined,
          questionTypeCounts: unitConfig.type === "Assignment" ? assignmentQuestionCounts : undefined,
          contentOnly: contentOnly,
        },
        selectedIdea: selectedIdea,
        generateVariations: generateVariations,
        referenceDocs: referenceDocs,
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

  return {
    plannerLoading,
    lessonVariations, setLessonVariations,
    brainstormIdeas, setBrainstormIdeas,
    selectedIdea, setSelectedIdea,
    brainstormLoading,
    assignmentQuestionCounts, setAssignmentQuestionCounts,
    brainstormIdeasHandler,
    generateLessonPlan,
  };
}
