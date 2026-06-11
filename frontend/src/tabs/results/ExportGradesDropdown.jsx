import React, { useState, useRef, useEffect } from "react";
import Icon from "../../components/Icon";
import * as api from "../../services/api";

export default function ExportGradesDropdown({
  gradesApproved, batchExportLoading, setBatchExportLoading,
  editedResults, status, resultsAssignmentFilter, resultsPeriodFilter,
  setFocusExportModal, addToast, config,
}) {
  var _open = useState(false)
  var open = _open[0]
  var setOpen = _open[1]
  var _lmsLoading = useState(false)
  var lmsLoading = _lmsLoading[0]
  var setLmsLoading = _lmsLoading[1]
  var dropdownRef = useRef(null)

  // Close dropdown on outside click
  useEffect(function() {
    function handleClick(e) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return function() { document.removeEventListener('mousedown', handleClick) }
  }, [])

  function getFilteredResults() {
    var source = editedResults.length > 0 ? editedResults : status.results
    var filtered = source
    if (resultsAssignmentFilter) {
      filtered = filtered.filter(function(r) { return r.assignment === resultsAssignmentFilter })
    }
    if (resultsPeriodFilter) {
      filtered = filtered.filter(function(r) { return r.period === resultsPeriodFilter })
    }
    return filtered
  }

  function getAssignment() {
    var source = editedResults.length > 0 ? editedResults : status.results
    return resultsAssignmentFilter || (source[0] && source[0].assignment) || 'Assignment'
  }

  async function handleFocusSIS() {
    setOpen(false)
    setFocusExportModal(true)
  }

  async function handleFocusBatch() {
    setOpen(false)
    setBatchExportLoading(true)
    try {
      var resultsToExport = getFilteredResults()
      var assignment = getAssignment()
      var batchRes = await api.exportFocusBatch(resultsToExport, assignment)
      await api.exportFocusComments(resultsToExport, assignment)
      if (batchRes.error) {
        addToast(batchRes.error, "error")
      } else {
        var totalCount = batchRes.periods.reduce(function(sum, p) { return sum + p.count }, 0)
        addToast("Exported " + totalCount + " grades + comments to " + batchRes.periods.length + " period files", "success")
      }
    } catch (err) {
      addToast("Batch export error: " + err.message, "error")
    } finally {
      setBatchExportLoading(false)
    }
  }

  var _sisLoading = useState(false)
  var sisLoading = _sisLoading[0]
  var setSisLoading = _sisLoading[1]

  async function handleOneRosterSync() {
    setOpen(false)
    setSisLoading(true)
    try {
      var resultsToSync = getFilteredResults()
      var assignment = getAssignment()
      var scores = resultsToSync.map(function(r) {
        var sid = r.student_id_number || ''
        if (sid.startsWith('oneroster:')) {
          sid = sid.substring('oneroster:'.length)
        } else {
          sid = ''
        }
        return {
          student_sourced_id: sid,
          score: r.score || 0,
          max_score: r.total_points || 100,
          comment: r.feedback_summary || r.feedback || '',
        }
      })
      var res = await api.syncOneRosterGrades({
        assessment_id: resultsAssignmentFilter || assignment,
        title: assignment,
        total_points: (resultsToSync[0] && resultsToSync[0].total_points) || 100,
        class_sourced_id: (resultsToSync[0] && resultsToSync[0].class_sourced_id) || '',
        scores: scores,
      })
      if (res.error) {
        addToast(res.error, "error")
      } else {
        var msg = "Synced " + res.synced + " grade" + (res.synced !== 1 ? "s" : "") + " to SIS"
        if (res.skipped > 0) msg += ", " + res.skipped + " skipped (no SIS match)"
        if (res.failed > 0) msg += ", " + res.failed + " failed"
        addToast(msg, res.failed > 0 ? "warning" : "success")
      }
    } catch (err) {
      addToast("SIS sync error: " + err.message, "error")
    } finally {
      setSisLoading(false)
    }
  }

  async function handleLmsExport(format) {
    setOpen(false)
    setLmsLoading(true)
    try {
      var resultsToExport = getFilteredResults()
      var assignment = getAssignment()
      var res = await api.exportLmsCsv(resultsToExport, assignment, 100, format)
      if (res.error) {
        addToast(res.error, "error")
      } else {
        var label = format === 'canvas' ? 'Canvas' : 'PowerSchool'
        addToast("Exported " + res.count + " grades as " + label + " CSV", "success")
      }
    } catch (err) {
      addToast(format + " export error: " + err.message, "error")
    } finally {
      setLmsLoading(false)
    }
  }

  var disabled = !gradesApproved || status.results.length === 0
  var loading = batchExportLoading || lmsLoading || sisLoading

  return (
    <div ref={dropdownRef} style={{ position: "relative", display: "inline-block" }}>
      <button
        onClick={() => setOpen(!open)}
        className="btn btn-primary"
        disabled={disabled || loading}
        style={{
          background: "linear-gradient(135deg, #8b5cf6, #6366f1)",
          opacity: gradesApproved ? 1 : 0.5,
          display: "flex", alignItems: "center", gap: "6px",
        }}
        title={gradesApproved ? "Export grades for LMS import" : "Approve grades first"}
      >
        <Icon name="Download" size={18} />
        {loading ? "Exporting..." : "Export Grades"}
        <Icon name="ChevronDown" size={14} />
      </button>
      {open && (
        <div style={{
          position: "absolute", top: "100%", left: 0, marginTop: "4px",
          background: "var(--glass-bg)", border: "1px solid var(--glass-border)",
          borderRadius: "8px", minWidth: "200px", zIndex: 1000,
          boxShadow: "0 8px 24px rgba(0,0,0,0.3)", overflow: "hidden",
        }}>
          {config.sis_type === 'focus' && (<>
          <DropdownItem onClick={handleFocusSIS} icon="Upload" label="Focus SIS" />
          <DropdownItem onClick={handleFocusBatch} icon="FolderDown" label="Focus Batch" />
          <div style={{ height: "1px", background: "var(--glass-border)", margin: "2px 0" }} />
          </>)}
          {(config || {}).sis_type === 'oneroster' && (<>
          <DropdownItem onClick={handleOneRosterSync} icon="RefreshCw" label="Sync to SIS" />
          <div style={{ height: "1px", background: "var(--glass-border)", margin: "2px 0" }} />
          </>)}
          <DropdownItem onClick={() => handleLmsExport('canvas')} icon="GraduationCap" label="Canvas LMS" />
          <DropdownItem onClick={() => handleLmsExport('powerschool')} icon="School" label="PowerSchool" />
        </div>
      )}
    </div>
  )
}

function DropdownItem({ onClick, icon, label }) {
  var _hover = useState(false)
  var hover = _hover[0]
  var setHover = _hover[1]
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        ...dropdownItemStyle,
        background: hover ? "rgba(99,102,241,0.1)" : "transparent",
      }}
    >
      <span style={{ display: "inline-flex", width: "20px", justifyContent: "center", flexShrink: 0 }}>
        <Icon name={icon} size={16} />
      </span>
      {label}
    </button>
  )
}

var dropdownItemStyle = {
  display: "flex", alignItems: "center", gap: "10px",
  width: "100%", padding: "10px 16px", border: "none",
  background: "transparent", color: "var(--text-primary)",
  fontSize: "0.85rem", cursor: "pointer", textAlign: "left",
  lineHeight: "20px",
}
