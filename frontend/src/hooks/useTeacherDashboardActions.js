import * as api from "../services/api";

/*
 * useTeacherDashboardActions — the teacher-dashboard / published-assessment / shared-
 * resource handlers, pushed down from the App.jsx shell (App.jsx decomposition slice 11).
 * FACTORY hook (no internal React state/effects → no hook-order constraint), called once
 * during App's render. The 9 handler bodies moved VERBATIM (two source ranges joined; the
 * interspersed render helper itemMatchesTagFilter stayed in App). Several handlers call
 * each other (toggleAssessmentStatus → the 3 fetchers; fetchAssessmentResults →
 * fetchContentSubmissions) — those internal calls resolve within this factory. The state
 * setters + the one read value (selectedAssessmentResults) + addToast they close over are
 * passed in; `api` is imported here (it also stays imported in App for other handlers).
 */
export function useTeacherDashboardActions({
  addToast,
  selectedAssessmentResults,
  setLoadingPublished,
  setPublishedAssessments,
  setLoadingSharedResources,
  setSharedResources,
  setAllTeacherTags,
  setContentSubmissionsGroups,
  setLoadingResults,
  setSelectedAssessmentResults,
  setInProgressDrafts,
}) {
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

  const fetchSharedResources = async () => {
    setLoadingSharedResources(true);
    try {
      const data = await api.getSharedResources();
      if (data.resources) {
        setSharedResources(data.resources);
      }
    } catch (e) {
      console.error("Error loading shared resources:", e);
    } finally {
      setLoadingSharedResources(false);
    }
  };

  const fetchTeacherTags = async () => {
    try {
      const data = await api.getTeacherTags();
      if (data && data.tags) setAllTeacherTags(data.tags);
    } catch (e) {
      console.error('Error loading teacher tags:', e);
    }
  };

  const handleDeleteSharedResource = async (id, title) => {
    try {
      var data = await api.deleteSharedResource(id);
      if (data.success) {
        setSharedResources(function(prev) { return prev.filter(function(r) { return r.id !== id; }); });
        addToast('Deleted "' + title + '"', 'success');
      } else {
        addToast(data.error || 'Failed to delete', 'error');
      }
    } catch (e) {
      addToast('Failed to delete: ' + e.message, 'error');
    }
  };

  const handleDeleteAllSharedResources = async (title) => {
    try {
      var data = await api.deleteSharedResourcesBulk(title);
      if (data.success) {
        setSharedResources(function(prev) { return prev.filter(function(r) { return r.title !== title; }); });
        addToast('Deleted "' + title + '" from ' + data.deleted + ' class' + (data.deleted === 1 ? '' : 'es'), 'success');
      } else {
        addToast(data.error || 'Failed to delete', 'error');
      }
    } catch (e) {
      addToast('Failed to delete: ' + e.message, 'error');
    }
  };

  // Fetch results for a specific assessment
  const fetchContentSubmissions = async (contentId) => {
    try {
      var data = await api.getContentSubmissions(contentId);
      if (data && data.students) {
        setContentSubmissionsGroups(data.students);
      } else {
        setContentSubmissionsGroups([]);
      }
    } catch (e) {
      console.error("Error loading content submissions:", e);
      setContentSubmissionsGroups([]);
    }
  };

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
        if (joinCode && joinCode.length > 10) {
          fetchContentSubmissions(joinCode);
        } else {
          setContentSubmissionsGroups([]);
        }
      }
      // Try to fetch in-progress drafts — only works for class-based content (UUID)
      if (joinCode && joinCode.length > 10) {
        try {
          var inProg = await api.getInProgressDrafts(joinCode);
          if (inProg && inProg.drafts) {
            setInProgressDrafts(inProg.drafts);
          } else {
            setInProgressDrafts([]);
          }
        } catch (e) {
          setInProgressDrafts([]);
        }
      } else {
        setInProgressDrafts([]);
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
        fetchSharedResources();
        fetchTeacherTags();
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

  return {
    fetchPublishedAssessments,
    fetchSharedResources,
    fetchTeacherTags,
    handleDeleteSharedResource,
    handleDeleteAllSharedResources,
    fetchContentSubmissions,
    fetchAssessmentResults,
    toggleAssessmentStatus,
    deletePublishedAssessment,
  };
}
