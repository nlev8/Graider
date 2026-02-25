# Assessment: Deterministic Assignment Generation Pipeline Refactor

## Executive Summary
The proposed refactoring plan (`PLAN.md`) is **highly recommended and technically sound**. It correctly identifies a core architectural flaw in the current assignment generation pipeline (over-reliance on the LLM for structured data generation and subsequent piecemeal patching) and proposes a clean, deterministic solution. By consolidating 7 scattered post-processing functions into a single 4-phase pipeline (`_post_process_assignment`), the codebase will become significantly easier to maintain, less token-intensive, and much more reliable for edge-case visual question types.

## Technical Feasibility & Alignment

### 1. Codebase Reality
Based on a review of `backend/routes/planner_routes.py`, the current state matches the plan's description perfectly. Functions like `_auto_upgrade_visual_types` (at line 141) and `_auto_correct_geometry_types` (at line 428) are massive blocks of reactive logic that attempt to override poor AI choices. Consolidating this logic into a proactive classification phase (`_classify_question_type`) is the correct architectural pattern.

### 2. The 4-Phase Architecture
The proposed pipeline (`classify -> hydrate -> validate -> enforce_count`) is logically sound.
*   **Classification:** Moving to regex and heuristic-based classification (e.g., detecting "y = 2x+1" to enforce `function_graph`) is far more reliable than expecting GPT-4o to consistently output `"question_type": "function_graph"`.
*   **Validation:** Adding a `_validate_question` step to downgrade broken visual questions (e.g., a `data_table` with no `headers`) to a `short_answer` is an excellent defensive programming measure that will prevent frontend crashes.
*   **Prompt Simplification:** Removing the hundreds of lines of "VISUAL/GRAPHICAL QUESTION TYPES" documentation from the AI prompts is a major win. It will save input tokens on every API call and likely improve the AI's focus on generating better pedagogical content rather than struggling with JSON schema compliance.

### 3. Implementation Steps
The step-by-step implementation order is well thought out:
1.  **Wrapper consolidation:** Zero-risk first step.
2.  **Classifier:** The core logic shift.
3.  **Validator:** Adds immediate stability.
4.  **Hydration consolidation:** Cleans up the namespace.
5.  **Prompt simplification:** Token savings realization.
6.  **Dead code removal:** Final cleanup.

This incremental approach allows for testing at each boundary and carries very low risk of catastrophic breakage since the underlying sub-functions (`_extract_dimensions_from_text`, `_detect_primary_shape`, etc.) are explicitly kept intact.

## Proposed Modifications / Considerations

1.  **Test Coverage Confidence:** The refactor relies entirely on existing detection logic (e.g., `_detect_primary_shape`). Since the behavior is being centralized, any existing bugs in those detection regexes will become more centralized as well. Ensure thorough manual testing (as outlined in the Verification section of the plan) after Step 2.
2.  **Fallback Logic:** In `_classify_question_type`, the plan states: `Phase 0: Trust AI for complex structural types`. This is critical. Types like `multiselect` or `inline_dropdown` are impossible to parse deterministically from raw text. Ensure `_TRUSTED_AI_TYPES` remains perfectly synchronized with the prompt instructions so the AI knows when it *must* supply the type.

## Verdict
**Proceed with Implementation.** The plan is comprehensive, accurate to the codebase, and addresses a critical technical debt item that will improve both performance (prompt length) and reliability (fewer frontend crashes due to malformed JSON).
