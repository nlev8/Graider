import { useState } from 'react';

/*
 * useVirtualKeyboard — owns the focused-input tracking and virtual math
 * keyboard insert/backspace handlers for AssignmentPlayer, relocated verbatim
 * from AssignmentPlayer.jsx (CQ wave-4 split; mirrors the wave-3
 * useAssistantChat precedent for state/handler clusters).
 *
 * Behavior-preserving notes:
 *   - Called unconditionally from the always-mounted AssignmentPlayer, so the
 *     focusedInput state keeps the exact same lifecycle it had inline.
 *   - answers state and updateAnswer stay owned by AssignmentPlayer and are
 *     passed in; the handlers close over them exactly as before.
 */
export default function useVirtualKeyboard(answers, updateAnswer) {
  const [focusedInput, setFocusedInput] = useState(null);

  const handleInputFocus = (el, key, mode) => {
    setFocusedInput({ ref: el, key, mode });
  };

  const handleKeyboardInsert = (text) => {
    if (!focusedInput) return;
    const el = focusedInput.ref;
    const start = el?.selectionStart ?? (el?.value?.length || 0);
    const end = el?.selectionEnd ?? start;
    const parts = focusedInput.key.split('-');
    const sIdx = parseInt(parts[0]);
    const qIdx = parseInt(parts[1]);
    const subField = parts[2];
    const answerKey = `${sIdx}-${qIdx}`;
    const currentAnswer = answers[answerKey]?.value;

    if (subField === 'math' || subField === 'work') {
      const field = subField === 'math' ? 'final' : 'work';
      const otherField = subField === 'math' ? 'work' : 'final';
      const current = currentAnswer?.[field] || '';
      const newVal = current.slice(0, start) + text + current.slice(end);
      updateAnswer(sIdx, qIdx, { ...currentAnswer, [field]: newVal, [otherField]: currentAnswer?.[otherField] || '' });
    } else if (subField && subField.startsWith('expr')) {
      const exprIdx = parseInt(subField.replace('expr', ''));
      const exprs = Array.isArray(currentAnswer) ? [...currentAnswer] : [''];
      const current = exprs[exprIdx] || '';
      exprs[exprIdx] = current.slice(0, start) + text + current.slice(end);
      updateAnswer(sIdx, qIdx, exprs);
    } else {
      const current = (typeof currentAnswer === 'string') ? currentAnswer : '';
      const newVal = current.slice(0, start) + text + current.slice(end);
      updateAnswer(sIdx, qIdx, newVal);
    }

    requestAnimationFrame(() => {
      if (el) {
        const newPos = start + text.length;
        el.selectionStart = newPos;
        el.selectionEnd = newPos;
        el.focus();
      }
    });
  };

  const handleKeyboardBackspace = () => {
    if (!focusedInput) return;
    const el = focusedInput.ref;
    const start = el?.selectionStart ?? 0;
    const end = el?.selectionEnd ?? start;
    if (start === 0 && end === 0) return;

    const parts = focusedInput.key.split('-');
    const sIdx = parseInt(parts[0]);
    const qIdx = parseInt(parts[1]);
    const subField = parts[2];
    const answerKey = `${sIdx}-${qIdx}`;
    const currentAnswer = answers[answerKey]?.value;

    const deleteStart = start === end ? start - 1 : start;

    if (subField === 'math' || subField === 'work') {
      const field = subField === 'math' ? 'final' : 'work';
      const otherField = subField === 'math' ? 'work' : 'final';
      const current = currentAnswer?.[field] || '';
      const newVal = current.slice(0, deleteStart) + current.slice(end);
      updateAnswer(sIdx, qIdx, { ...currentAnswer, [field]: newVal, [otherField]: currentAnswer?.[otherField] || '' });
    } else if (subField && subField.startsWith('expr')) {
      const exprIdx = parseInt(subField.replace('expr', ''));
      const exprs = Array.isArray(currentAnswer) ? [...currentAnswer] : [''];
      const current = exprs[exprIdx] || '';
      exprs[exprIdx] = current.slice(0, deleteStart) + current.slice(end);
      updateAnswer(sIdx, qIdx, exprs);
    } else {
      const current = (typeof currentAnswer === 'string') ? currentAnswer : '';
      const newVal = current.slice(0, deleteStart) + current.slice(end);
      updateAnswer(sIdx, qIdx, newVal);
    }

    requestAnimationFrame(() => {
      if (el) {
        el.selectionStart = deleteStart;
        el.selectionEnd = deleteStart;
        el.focus();
      }
    });
  };

  return {
    focusedInput,
    setFocusedInput,
    handleInputFocus,
    handleKeyboardInsert,
    handleKeyboardBackspace,
  };
}
