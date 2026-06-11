import { useState } from "react";
import Icon from "../../components/Icon";
import * as api from "../../services/api";

/*
 * useTagRow — owns the NewUnit + tag cluster, relocated verbatim from
 * PlannerTab.jsx (CQ wave-3 split).
 *
 * History: moved App.jsx → PlannerTab in PR 7e of the Planner extraction
 * sprint. 2 useStates (newUnitModal + tagDropdownOpenFor), 4 handlers
 * (handleSetUnit/handleSetTags/handleAddTag/handleRemoveTag) and the
 * renderTagRow helper (~140 LOC). Codex Round 1 of PR 7e expanded the slice
 * to include renderTagRow + the 3 tag handlers because renderTagRow closes
 * over setNewUnitModal + the handlers; moving newUnitModal alone would
 * orphan all the setter call sites inside renderTagRow.
 *
 * allTeacherTags + addToast + fetchTeacherTags remain App-shell props
 * (other consumers), received here as hook args. The NewUnitModal JSX block
 * (which also needs setSharedResources / setPublishedAssessments) lives in
 * PlannerNewUnitModal.jsx; this hook exposes newUnitModal/setNewUnitModal
 * for it.
 */
export default function useTagRow({ allTeacherTags, addToast, fetchTeacherTags }) {
  const [newUnitModal, setNewUnitModal] = useState(null); // { resourceId, value, mode, existingTags } or null
  const [tagDropdownOpenFor, setTagDropdownOpenFor] = useState(null); // content_id or null

  var handleSetUnit = async function(contentId, unitName, onSuccess) {
    try {
      var data = await api.updateSharedResourceUnit(contentId, unitName);
      if (data && data.success) {
        if (onSuccess) onSuccess(unitName);
        addToast(unitName ? ('Set unit to "' + unitName + '"') : 'Cleared unit', 'success');
        fetchTeacherTags();
      }
    } catch (e) {
      addToast('Failed to set unit: ' + (e.message || 'unknown'), 'error');
    }
  };

  var handleSetTags = async function(contentId, tags, onSuccess) {
    try {
      var data = await api.setContentTags(contentId, tags);
      if (data && data.success) {
        if (onSuccess) onSuccess(data.tags || tags);
        fetchTeacherTags();
      }
    } catch (e) {
      addToast('Failed to update tags: ' + (e.message || 'unknown'), 'error');
    }
  };

  var handleAddTag = function(contentId, existingTags, newTag, onSuccess) {
    var tags = (existingTags || []).slice();
    if (tags.indexOf(newTag) !== -1) return;
    tags.push(newTag);
    handleSetTags(contentId, tags, function(saved) {
      if (onSuccess) onSuccess(saved);
      addToast('Added tag "' + newTag + '"', 'success');
    });
  };

  var handleRemoveTag = function(contentId, existingTags, tagToRemove, onSuccess) {
    var tags = (existingTags || []).filter(function(t) { return t !== tagToRemove; });
    handleSetTags(contentId, tags, function(saved) {
      if (onSuccess) onSuccess(saved);
      addToast('Removed tag "' + tagToRemove + '"', 'success');
    });
  };

  // Reusable inline tag row for published content
  var renderTagRow = function(item, onUpdate) {
    var itemId = item.id || item.content_id;
    if (!itemId) return null;
    var isDropdownOpen = tagDropdownOpenFor === itemId;
    var unitName = item.unit_name || '';
    var tags = item.tags || [];
    var availableTags = allTeacherTags.filter(function(t) {
      return t !== unitName && tags.indexOf(t) === -1;
    });

    return (
      <div style={{ display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap", marginTop: "8px", position: "relative" }}>
        {unitName ? (
          <span
            onClick={function(e) {
              e.stopPropagation();
              handleSetUnit(itemId, '', function() { onUpdate({ unit_name: '' }); });
            }}
            style={{
              display: "inline-flex", alignItems: "center", gap: "4px",
              padding: "3px 10px", borderRadius: "12px",
              background: "rgba(99,102,241,0.15)", color: "var(--accent-primary)",
              fontSize: "0.72rem", fontWeight: 600, cursor: "pointer",
              border: "1px solid rgba(99,102,241,0.3)",
            }}
            title="Click to remove unit"
          >
            <Icon name="Folder" size={11} />
            {unitName}
          </span>
        ) : (
          <span style={{ fontSize: "0.72rem", color: "var(--text-muted)", fontStyle: "italic" }}>
            No unit
          </span>
        )}
        {tags.map(function(t) {
          return (
            <span
              key={t}
              onClick={function(e) {
                e.stopPropagation();
                handleRemoveTag(itemId, tags, t, function(saved) { onUpdate({ tags: saved }); });
              }}
              style={{
                padding: "3px 8px", borderRadius: "10px",
                background: "var(--glass-bg)", color: "var(--text-secondary)",
                fontSize: "0.7rem", cursor: "pointer",
                border: "1px solid var(--glass-border)",
              }}
              title="Click to remove tag"
            >
              {t}
            </span>
          );
        })}
        <button
          onClick={function(e) {
            e.stopPropagation();
            setTagDropdownOpenFor(isDropdownOpen ? null : itemId);
          }}
          style={{
            padding: "2px 8px", borderRadius: "10px",
            background: "var(--glass-bg)", color: "var(--text-secondary)",
            fontSize: "0.75rem", cursor: "pointer",
            border: "1px dashed var(--glass-border)",
          }}
          title="Add tag"
        >
          + Tag
        </button>
        {isDropdownOpen && (
          <div
            onClick={function(e) { e.stopPropagation(); }}
            style={{
              position: "absolute", top: "100%", left: 0, marginTop: "4px",
              background: "var(--modal-content-bg)", border: "1px solid var(--glass-border)",
              borderRadius: "10px", padding: "8px", minWidth: "220px", maxHeight: "280px",
              overflowY: "auto", zIndex: 50,
              boxShadow: "0 8px 24px rgba(0,0,0,0.3)",
            }}
          >
            {!unitName && allTeacherTags.length > 0 && (
              <div style={{ marginBottom: "6px" }}>
                <div style={{ fontSize: "0.65rem", fontWeight: 700, textTransform: "uppercase", color: "var(--text-muted)", padding: "4px 8px", letterSpacing: "0.05em" }}>Set as unit</div>
                {allTeacherTags.slice(0, 5).map(function(t) {
                  return (
                    <div
                      key={'u-' + t}
                      onClick={function() {
                        setTagDropdownOpenFor(null);
                        handleSetUnit(itemId, t, function() { onUpdate({ unit_name: t }); });
                      }}
                      style={{ padding: "6px 10px", fontSize: "0.8rem", borderRadius: "6px", cursor: "pointer", display: "flex", alignItems: "center", gap: "6px" }}
                      onMouseEnter={function(e) { e.currentTarget.style.background = 'var(--glass-bg)'; }}
                      onMouseLeave={function(e) { e.currentTarget.style.background = 'transparent'; }}
                    >
                      <Icon name="Folder" size={12} style={{ color: "var(--accent-primary)" }} />
                      {t}
                    </div>
                  );
                })}
                <div style={{ height: "1px", background: "var(--glass-border)", margin: "6px 0" }} />
              </div>
            )}
            <div style={{ fontSize: "0.65rem", fontWeight: 700, textTransform: "uppercase", color: "var(--text-muted)", padding: "4px 8px", letterSpacing: "0.05em" }}>
              {availableTags.length > 0 ? 'Add existing tag' : 'No other tags'}
            </div>
            {availableTags.map(function(t) {
              return (
                <div
                  key={'t-' + t}
                  onClick={function() {
                    setTagDropdownOpenFor(null);
                    handleAddTag(itemId, tags, t, function(saved) { onUpdate({ tags: saved }); });
                  }}
                  style={{ padding: "6px 10px", fontSize: "0.8rem", borderRadius: "6px", cursor: "pointer" }}
                  onMouseEnter={function(e) { e.currentTarget.style.background = 'var(--glass-bg)'; }}
                  onMouseLeave={function(e) { e.currentTarget.style.background = 'transparent'; }}
                >
                  {t}
                </div>
              );
            })}
            <div style={{ height: "1px", background: "var(--glass-border)", margin: "6px 0" }} />
            <div
              onClick={function() {
                setTagDropdownOpenFor(null);
                setNewUnitModal({ resourceId: itemId, value: '', mode: unitName ? 'tag' : 'unit', existingTags: tags });
              }}
              style={{ padding: "6px 10px", fontSize: "0.8rem", borderRadius: "6px", cursor: "pointer", color: "var(--accent-primary)", fontWeight: 600 }}
              onMouseEnter={function(e) { e.currentTarget.style.background = 'var(--glass-bg)'; }}
              onMouseLeave={function(e) { e.currentTarget.style.background = 'transparent'; }}
            >
              + Create new tag...
            </div>
          </div>
        )}
      </div>
    );
  };

  return { newUnitModal, setNewUnitModal, renderTagRow };
}
