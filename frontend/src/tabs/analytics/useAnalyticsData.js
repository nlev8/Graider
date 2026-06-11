import React, { useState, useEffect, useMemo } from "react";
import * as api from "../../services/api";
import { studentNameMatchesPeriod } from "./helpers";

// Data/state hook for AnalyticsTab — analytics fetch state, loading overlay
// phases, period rosters, and the period-filtered analytics memo, all moved
// verbatim from the AnalyticsTab component body (CQ wave 1 split).
export default function useAnalyticsData({ periods, status }) {
  // --- Analytics-specific state ---
  const [analytics, setAnalytics] = useState(null);
  const [analyticsLoading, setAnalyticsLoading] = useState(true);
  const [chartsOverlay, setChartsOverlay] = useState(false);
  const [chartsReady, setChartsReady] = useState(false);
  const [analyticsPeriod, setAnalyticsPeriod] = useState("all");
  const [analyticsClassPeriod, setAnalyticsClassPeriod] = useState("");
  const [analyticsClassStudents, setAnalyticsClassStudents] = useState([]);
  const [periodStudentMap, setPeriodStudentMap] = useState({});
  const [analyticsSource, setAnalyticsSource] = useState('all');

  // --- Effects ---

  // Fetch analytics data (component only mounts when tab is active)
  const analyticsInitialLoad = React.useRef(true);
  useEffect(() => {
    // Full loading spinner only on initial load — filter changes just refresh data in place
    if (analyticsInitialLoad.current) {
      setAnalyticsLoading(true);
      setChartsOverlay(false);
      setChartsReady(false);
    }
    api
      .getAnalytics(analyticsPeriod, analyticsSource)
      .then((data) => {
        setAnalytics(data);
        if (analyticsInitialLoad.current) {
          setChartsOverlay(true);
          analyticsInitialLoad.current = false;
        }
        setAnalyticsLoading(false);
      })
      .catch((err) => {
        console.error(err);
        setAnalyticsLoading(false);
        analyticsInitialLoad.current = false;
      });
  }, [analyticsPeriod, analyticsSource, status.results.length]);

  // Phase 2: after overlay paints, mount charts underneath
  useEffect(() => {
    if (!chartsOverlay || chartsReady) return;
    // Double rAF ensures the overlay spinner is painted before charts mount
    const id = requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        setChartsReady(true);
      });
    });
    return () => cancelAnimationFrame(id);
  }, [chartsOverlay, chartsReady]);

  // Phase 3: remove overlay after charts render
  useEffect(() => {
    if (!chartsReady) return;
    const timer = setTimeout(() => setChartsOverlay(false), 4000);
    return () => clearTimeout(timer);
  }, [chartsReady]);

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

  // Load all period rosters for By-Period distribution view
  useEffect(() => {
    if (periods.length === 0) return;
    Promise.all(
      periods.map((p) =>
        api.getPeriodStudents(p.filename).then((data) => ({ name: p.period_name, students: data.students || [] }))
          .catch(() => ({ name: p.period_name, students: [] }))
      )
    ).then((results) => {
      const map = {};
      results.forEach((r) => { map[r.name] = r.students; });
      setPeriodStudentMap(map);
    });
  }, [periods]);


  // --- Memos ---

  const filteredAnalytics = useMemo(() => {
    if (
      !analytics ||
      !analyticsClassPeriod ||
      analyticsClassStudents.length === 0
    ) {
      return analytics;
    }

    const filteredGrades = (analytics.all_grades || []).filter((g) =>
      studentNameMatchesPeriod(g.student_name, analyticsClassStudents),
    );

    const filteredProgress = (analytics.student_progress || []).filter((s) =>
      studentNameMatchesPeriod(s.name, analyticsClassStudents),
    );

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

    const filteredAttention = (analytics.attention_needed || []).filter((s) =>
      studentNameMatchesPeriod(s.name, analyticsClassStudents),
    );
    const filteredTop = filteredProgress
      .sort((a, b) => b.average - a.average)
      .slice(0, 5);

    const filteredCostTotal = filteredGrades.reduce((sum, g) => sum + (g.api_cost || 0), 0);
    const filteredCostSummary = analytics.cost_summary ? {
      ...analytics.cost_summary,
      total_cost: Math.round(filteredCostTotal * 10000) / 10000,
      total_tokens: filteredGrades.reduce((sum, g) => sum + (g.input_tokens || 0) + (g.output_tokens || 0), 0),
      total_api_calls: filteredGrades.reduce((sum, g) => sum + (g.api_calls || 0), 0),
      avg_cost_per_student: filteredGrades.length > 0 ? Math.round(filteredCostTotal / filteredGrades.length * 10000) / 10000 : 0,
    } : analytics.cost_summary;

    const filteredCategoryStats = (analytics.category_stats || []).filter((s) =>
      studentNameMatchesPeriod(s.name, analyticsClassStudents),
    );

    return {
      ...analytics,
      all_grades: filteredGrades,
      student_progress: filteredProgress,
      class_stats: filteredClassStats,
      attention_needed: filteredAttention,
      top_performers: filteredTop,
      cost_summary: filteredCostSummary,
      category_stats: filteredCategoryStats,
    };
  }, [analytics, analyticsClassPeriod, analyticsClassStudents]);

  return {
    analytics,
    analyticsLoading,
    chartsOverlay,
    chartsReady,
    analyticsPeriod,
    setAnalyticsPeriod,
    analyticsClassPeriod,
    setAnalyticsClassPeriod,
    analyticsSource,
    setAnalyticsSource,
    periodStudentMap,
    filteredAnalytics,
  };
}
