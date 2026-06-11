import { useState } from "react";
import * as api from "../../services/api";

/*
 * useShareWithClasses — owns the ShareWithClasses cluster, relocated verbatim
 * from PlannerTab.jsx (CQ wave-3 split).
 *
 * History: moved App.jsx → PlannerTab in PR 7d of the Planner extraction
 * sprint (4 useStates + 2 handlers + 1 modal block). teacherClasses,
 * setTeacherClasses, addToast, unitConfig are App-shell props, received here
 * as hook args.
 *
 * Behavior-preserving notes: handlers are intentionally NOT memoized — same
 * as the pre-split plain declarations recreated each render. The hook is
 * called unconditionally from the PlannerTab shell.
 */
export default function useShareWithClasses({
  teacherClasses,
  setTeacherClasses,
  addToast,
  unitConfig,
}) {
  const [showShareModal, setShowShareModal] = useState(false);
  const [shareModalContent, setShareModalContent] = useState(null);
  const [shareModalSelected, setShareModalSelected] = useState([]);
  const [shareModalSharing, setShareModalSharing] = useState(false);

  async function shareWithClass(content, contentType, title) {
    var classes = teacherClasses;
    if (!classes || classes.length === 0) {
      try {
        var data = await api.listClasses();
        if (data.classes && data.classes.length > 0) {
          classes = data.classes;
          setTeacherClasses(classes);
        }
      } catch (e) { /* fall through to check below */ }
    }
    if (!classes || classes.length === 0) {
      addToast('No classes found. Sync your roster first.', 'warning');
      return;
    }
    if (classes.length === 1) {
      try {
        var resp = await fetch('/api/publish-to-class', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            class_id: classes[0].id,
            content: content,
            content_type: contentType,
            title: title,
            settings: { unit_name: unitConfig.title || '' },
          }),
        });
        var result = await resp.json();
        if (result.error) {
          addToast(result.error, 'error');
        } else {
          addToast('Shared "' + title + '" with ' + classes[0].name, 'success');
        }
      } catch (err) {
        addToast('Failed to share: ' + err.message, 'error');
      }
      return;
    }
    setShareModalContent({ content: content, contentType: contentType, title: title, unitName: unitConfig.title || '' });
    setShareModalSelected([]);
    setShowShareModal(true);
  }

  async function executeShareWithClasses() {
    if (!shareModalContent || shareModalSelected.length === 0) return;
    setShareModalSharing(true);
    var successes = 0;
    var failures = 0;
    for (var i = 0; i < shareModalSelected.length; i++) {
      try {
        var resp = await fetch('/api/publish-to-class', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            class_id: shareModalSelected[i],
            content: shareModalContent.content,
            content_type: shareModalContent.contentType,
            title: shareModalContent.title,
            settings: { unit_name: shareModalContent.unitName || '' },
          }),
        });
        var result = await resp.json();
        if (result.error) {
          failures++;
        } else {
          successes++;
        }
      } catch (err) {
        failures++;
      }
    }
    setShareModalSharing(false);
    setShowShareModal(false);
    if (failures === 0) {
      addToast('Shared "' + shareModalContent.title + '" with ' + successes + ' class' + (successes === 1 ? '' : 'es'), 'success');
    } else if (successes > 0) {
      addToast('Shared with ' + successes + ' class' + (successes === 1 ? '' : 'es') + ', ' + failures + ' failed', 'warning');
    } else {
      addToast('Failed to share with any classes', 'error');
    }
  }

  return {
    showShareModal, setShowShareModal,
    shareModalContent, setShareModalContent,
    shareModalSelected, setShareModalSelected,
    shareModalSharing,
    shareWithClass,
    executeShareWithClasses,
  };
}
