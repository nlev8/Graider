"""Curriculum standards lookup tools.

Pure-move of whole functions out of the former single-file module; bodies
are byte-identical.
"""
from backend.services.assistant_tools import _load_settings, _load_standards
from backend.utils.compliance import require_teacher_id


def get_standards_tool(topic=None, dok_max=None, teacher_id='local-dev'):
    """Look up curriculum standards filtered by topic and DOK level."""
    require_teacher_id(teacher_id)
    all_standards = _load_standards()
    if not all_standards:
        settings = _load_settings(teacher_id)
        config = settings.get('config', {})
        subj = config.get('subject', 'unknown')
        st = config.get('state', 'unknown')
        return {"error": f"No standards found for {subj} in {st}. Check Settings > Subject and State."}

    results = all_standards

    # Filter by DOK level
    if dok_max is not None:
        results = [s for s in results if s.get('dok', 99) <= dok_max]

    # Filter by topic keyword
    if topic:
        topic_lower = topic.lower()
        filtered = []
        for s in results:
            searchable = " ".join([
                s.get('benchmark', ''),
                " ".join(s.get('topics', [])),
                " ".join(s.get('vocabulary', [])),
                s.get('item_specs', ''),
            ]).lower()
            if topic_lower in searchable:
                filtered.append(s)
        results = filtered

    if not results:
        return {"error": f"No standards found matching '{topic or 'all'}' (DOK <= {dok_max or 'any'})"}

    return {
        "count": len(results),
        "standards": [
            {
                "code": s.get("code", ""),
                "benchmark": s.get("benchmark", ""),
                "dok": s.get("dok"),
                "topics": s.get("topics", []),
                "vocabulary": s.get("vocabulary", []),
                "learning_targets": s.get("learning_targets", []),
                "essential_questions": s.get("essential_questions", []),
                "sample_assessment": s.get("sample_assessment", ""),
            }
            for s in results
        ]
    }


def list_all_standards_tool(teacher_id='local-dev'):
    """Return a compact index of ALL curriculum standards for the teacher's subject."""
    require_teacher_id(teacher_id)
    all_standards = _load_standards()
    if not all_standards:
        settings = _load_settings(teacher_id)
        config = settings.get('config', {})
        subj = config.get('subject', 'unknown')
        st = config.get('state', 'unknown')
        return {"error": f"No standards found for {subj} in {st}. Check Settings > Subject and State."}

    settings = _load_settings(teacher_id)
    config = settings.get('config', {})

    compact = []
    for s in all_standards:
        benchmark = s.get("benchmark", "")
        compact.append({
            "code": s.get("code", ""),
            "benchmark": benchmark[:120] + "..." if len(benchmark) > 120 else benchmark,
            "dok": s.get("dok"),
            "topics": s.get("topics", []),
        })

    return {
        "subject": config.get('subject', 'unknown'),
        "state": config.get('state', 'unknown'),
        "grade_level": config.get('grade_level', 'unknown'),
        "total_count": len(compact),
        "standards": compact,
    }
