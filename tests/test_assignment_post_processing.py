"""Golden tests + runtime smokes for backend/services/assignment_post_processing.

The pipeline mutates shared `q` dicts in place across 6 ordered phases.
Downstream consumers rely on specific field aliases. These tests snapshot
the end-to-end behavior so the PR4 context refactor cannot silently change
any alias or ordering.

Added in PR3; permanent regression guards.
"""
import builtins
import dis


def test_hydrate_data_table_aliases_column_headers_to_headers():
    """Data-table hydration maps `column_headers` → `headers` when `headers` is absent.

    Pinned from observed behavior: _hydrate_data_table sets q['headers'] = q['column_headers']
    at line 653 of backend/services/assignment_post_processing.py. Downstream frontend code
    reads `headers`, so this alias must survive any refactor of the hydration signature.
    """
    from backend.services.assignment_post_processing import _hydrate_question
    q = {
        "question_type": "data_table",
        "question": "Fill in the table",
        "column_headers": ["Day", "Apples"],
        "expected_data": [["Mon", 5], ["Tue", 6]],
    }
    _hydrate_question(q)
    # Contract: both keys present after hydration, both reference the same list
    assert q["headers"] == ["Day", "Apples"], "headers alias not populated from column_headers"
    assert q["column_headers"] == ["Day", "Apples"], "column_headers not preserved"
    # initial_data is populated with blanks for editable cells, matching expected_data shape
    assert q["initial_data"] == [["", ""], ["", ""]], (
        "initial_data must be a blanked-out copy of expected_data's shape"
    )
    assert q["num_rows"] == 2
    # question_type stays data_table (not downgraded)
    assert q["question_type"] == "data_table"


def test_hydrate_geometry_applies_rectangle_defaults_and_computes_answer():
    """Geometry hydration fills defaults (base=6, height=4) and computes area answer.

    Pinned observable behavior: a rectangle question with mode='area' receives
    defaults base=6, height=4, and answer is computed as '24' (6 * 4).
    """
    from backend.services.assignment_post_processing import _hydrate_question
    q = {
        "question_type": "rectangle",
        "mode": "area",
        "question": "Find the area of a rectangle.",
    }
    _hydrate_question(q)
    # Defaults applied from _GEOMETRY_DEFAULTS['rectangle']
    assert q["base"] == 6, "rectangle default base missing"
    assert q["height"] == 4, "rectangle default height missing"
    # Answer computed from formula (base * height = 6 * 4 = 24)
    assert q["answer"] == "24", "rectangle area answer (base*height) not computed"
    assert q["question_type"] == "rectangle"


def test_hydrate_matching_normalizes_to_term_definition_dict():
    """Matching hydration produces canonical dict {term: definition} on BOTH keys.

    _hydrate_matching writes both `correct_answer` and `answer` with the same dict
    so grading and frontend rendering share one shape. The frontend reads one,
    grading reads the other — breaking this alias silently breaks scoring.
    """
    from backend.services.assignment_post_processing import _hydrate_question
    q = {
        "question_type": "matching",
        "terms": ["Photosynthesis", "Respiration"],
        "definitions": ["Makes food", "Breaks down food"],
    }
    _hydrate_question(q)
    # Both keys populated with dict — fallback pairs terms[i] → definitions[i]
    assert q["correct_answer"] == {
        "Photosynthesis": "Makes food",
        "Respiration": "Breaks down food",
    }, "correct_answer must use terms[i]→definitions[i] fallback mapping"
    assert q["correct_answer"] == q["answer"], "correct_answer and answer must be identical dicts"


def test_validate_question_downgrades_mc_without_options():
    """_validate_question: multiple_choice without `options` → short_answer.

    _REQUIRED_FIELDS['multiple_choice'] = ['options']. Missing/empty options
    triggers downgrade per the guarded loop in _validate_question.
    Positive case: MC with options stays MC.
    """
    from backend.services.assignment_post_processing import _validate_question
    # Missing options → downgrade
    q_bare = {"question_type": "multiple_choice"}
    _validate_question(q_bare)
    assert q_bare["question_type"] == "short_answer", "MC without options must downgrade"

    # With options → preserved
    q_with = {"question_type": "multiple_choice", "options": ["A", "B", "C", "D"]}
    _validate_question(q_with)
    assert q_with["question_type"] == "multiple_choice", "MC with options must not downgrade"


def test_is_project_question_matches_keywords_and_excludes_others():
    """_is_project_question: True for project prompts, False for plain math.

    The regex drives Phase 3b question filtering — breaking its predicate
    changes which questions reach students.
    """
    from backend.services.assignment_post_processing import _is_project_question

    # "create a poster" branch of _PROJECT_KEYWORDS
    assert _is_project_question(
        {"question": "Create a poster that shows your understanding of the water cycle."}
    ) is True
    # "collaborate with your partner" branch
    assert _is_project_question(
        {"question": "Collaborate with your partner to solve the problem."}
    ) is True
    # Plain math — no branch matches
    assert _is_project_question({"question": "What is 2 + 2?"}) is False


def test_validate_question_quality_flags_mc_mismatch_and_dedupes():
    """_validate_question_quality: combined contract test.

    1. Flags MC where `answer` isn't in `options` (Check 3, severity='error').
    2. Removes duplicate questions with identical text (dedup pass).
    3. Attaches `warning` + `warning_severity` to flagged questions.
    """
    from backend.services.assignment_post_processing import _validate_question_quality
    assignment = {
        "sections": [{
            "questions": [
                # Mismatched MC — should be flagged
                {
                    "question": "What is the capital of France?",
                    "question_type": "multiple_choice",
                    "options": ["London", "Berlin", "Madrid", "Rome"],
                    "answer": "Paris",
                },
                # Duplicate of the first (identical text — the dedup is on text not content)
                # Use a different question so we can test dedup separately
                {"question": "What is 2+2?", "question_type": "short_answer", "answer": "4"},
                {"question": "What is 2+2?", "question_type": "short_answer", "answer": "4"},
            ]
        }]
    }
    warnings = _validate_question_quality(assignment)

    # Check 3 flagged the MC mismatch
    issues = [w["issue"] for w in warnings]
    assert any("does not match" in i for i in issues), (
        f"Expected 'Answer does not match any option' in warnings, got: {issues}"
    )

    # The flagged MC has warning fields attached (severity='error' from Check 3)
    mc_q = assignment["sections"][0]["questions"][0]
    assert mc_q.get("warning_severity") == "error", (
        f"MC with mismatched answer must have warning_severity='error', got {mc_q.get('warning_severity')}"
    )

    # Dedup: duplicate "What is 2+2?" was removed — only one copy survives
    remaining_texts = [q["question"] for q in assignment["sections"][0]["questions"]]
    assert remaining_texts.count("What is 2+2?") == 1, (
        "Identical question text must be deduplicated"
    )


def test_check_question_quality_missing_answer_gated_by_question_type():
    """_check_question_quality: 'Missing answer key' fires for short_answer but not for essay.

    Check 2 skips non_answer_types = {'essay', 'extended_response', 'multi_part'}.
    This gates which questions teachers see 'missing answer' warnings on.
    """
    from backend.services.assignment_post_processing import _check_question_quality

    # short_answer with no answer → flagged
    issues_sa = _check_question_quality(
        {"question": "What is the largest planet?", "question_type": "short_answer"}
    )
    assert any(i["issue"] == "Missing answer key" for i in issues_sa), (
        f"short_answer without answer must be flagged; got {[i['issue'] for i in issues_sa]}"
    )

    # essay with no answer → NOT flagged for missing answer
    issues_essay = _check_question_quality(
        {"question": "Write an essay about climate change.", "question_type": "essay"}
    )
    assert not any(i["issue"] == "Missing answer key" for i in issues_essay), (
        "essay questions must not be flagged for missing answer key"
    )


def test_pipeline_ast_global_refs_all_resolve():
    """AST bound-name completeness guard on _post_process_assignment.

    Post-PR5 the orchestrator lives in the service module. Every
    LOAD_GLOBAL reference in its bytecode must resolve to a name in
    the service module's namespace or builtins.
    """
    import backend.services.assignment_post_processing as module
    _post_process_assignment = module._post_process_assignment

    def collect_global_refs(code):
        refs = set()
        for inst in dis.get_instructions(code):
            if inst.opname == "LOAD_GLOBAL":
                refs.add(inst.argval.lstrip("+ "))
        for const in code.co_consts:
            if hasattr(const, "co_code"):
                refs.update(collect_global_refs(const))
        return refs

    needed = collect_global_refs(_post_process_assignment.__code__)
    module_names = set(dir(module))
    builtin_names = set(dir(builtins))

    # Phase 3a latent bugs — keep allowlisted per spec
    PREEXISTING_LATENT = {"config", "logger"}

    unresolved = needed - module_names - builtin_names - PREEXISTING_LATENT
    assert not unresolved, (
        f"_post_process_assignment references names that don't resolve: {sorted(unresolved)}"
    )


def test_handler_smoke_normalize_points_preserves_warning_fields():
    """Gotcha #5: _normalize_points must not clobber warning/warning_severity fields.

    generate_assessment reads these fields after _post_process_assignment runs.
    Pinning the contract here prevents PR4's signature refactor from silently
    dropping them.
    """
    from backend.services.assignment_post_processing import _normalize_points
    assignment = {
        "sections": [
            {"questions": [
                {"question_type": "multiple_choice", "points": 10, "warning": "test_warning", "warning_severity": "low"},
                {"question_type": "short_answer", "points": 5},
            ]}
        ]
    }
    _normalize_points(assignment, target_total=15)
    q0 = assignment["sections"][0]["questions"][0]
    assert q0.get("warning") == "test_warning", "warning field must survive _normalize_points"
    assert q0.get("warning_severity") == "low", "warning_severity field must survive"
