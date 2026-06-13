"""Lesson recommendation + recent-lesson report tools.

Pure-move of whole functions out of the former single-file module; bodies
are byte-identical.
"""
import os
import json
import logging
from collections import defaultdict

from backend.services.assistant_tools import (
    _load_results, _load_settings, _load_accommodations,
    _load_standards, _load_saved_lessons, _load_period_class_levels,
    _safe_int_score, LESSONS_DIR,
)
from backend.utils.compliance import require_teacher_id
import sentry_sdk

_logger = logging.getLogger(__name__)


def _analyze_group_weaknesses(group_results):
    """Shared weakness analysis for a group of student results.
    Returns dict with category_weaknesses, content_gaps, developing_skills, strengths, scores."""
    total = len(group_results)
    if not total:
        return None

    # Category breakdown
    cat_totals = defaultdict(list)
    for r in group_results:
        bd = r.get('breakdown', {})
        if bd:
            for cat, val in bd.items():
                try:
                    cat_totals[cat].append(int(float(val)) if val else 0)
                except (ValueError, TypeError):
                    _logger.debug("Non-numeric breakdown value %r skipped for category %s", val, cat)

    category_weaknesses = []
    for cat, vals in cat_totals.items():
        avg = round(sum(vals) / len(vals), 1) if vals else 0
        max_possible = max(vals) if vals else 0
        zeros = sum(1 for v in vals if v == 0)
        category_weaknesses.append({
            "category": cat,
            "average": avg,
            "max_seen": max_possible,
            "zero_count": zeros,
            "zero_pct": round(zeros / len(vals) * 100, 1) if vals else 0,
        })
    category_weaknesses.sort(key=lambda x: x["average"])

    # Unanswered questions
    unanswered_counts = defaultdict(int)
    for r in group_results:
        uq = r.get('unanswered_questions')
        if uq and isinstance(uq, list):
            for q in uq:
                unanswered_counts[q] += 1
    content_gaps = sorted(unanswered_counts.items(), key=lambda x: x[1], reverse=True)[:8]

    # Skills
    developing_freq = defaultdict(int)
    strength_freq = defaultdict(int)
    for r in group_results:
        skills = r.get('skills_demonstrated', {})
        if isinstance(skills, dict):
            for s in (skills.get('developing', []) or []):
                developing_freq[s.strip()] += 1
            for s in (skills.get('strengths', []) or []):
                strength_freq[s.strip()] += 1

    top_developing = sorted(developing_freq.items(), key=lambda x: x[1], reverse=True)[:6]
    top_strengths = sorted(strength_freq.items(), key=lambda x: x[1], reverse=True)[:4]

    # Scores
    scores = [_safe_int_score(r.get('score')) for r in group_results]
    failing = [s for s in scores if s < 70]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0

    # Omissions
    omission_count = sum(1 for r in group_results
                         if r.get('unanswered_questions') and len(r.get('unanswered_questions', [])) > 0)

    return {
        "total_students": total,
        "average_score": avg_score,
        "failing_count": len(failing),
        "failing_pct": round(len(failing) / total * 100, 1) if total else 0,
        "omission_rate": round(omission_count / total * 100, 1) if total else 0,
        "category_weaknesses": category_weaknesses,
        "content_gaps": [{"topic": q, "students_missed": c,
                          "pct": round(c / total * 100, 1)}
                         for q, c in content_gaps],
        "developing_skills": [{"skill": s, "count": c} for s, c in top_developing],
        "student_strengths": [{"skill": s, "count": c} for s, c in top_strengths],
    }


def _match_standards(weakness_data, standards, target_dok=None):
    """Match curriculum standards to identified weaknesses, optionally filtering by DOK level."""
    if not standards or not weakness_data:
        return []

    weakness_keywords = set()
    for gap in weakness_data.get("content_gaps", []):
        for word in gap["topic"].lower().split():
            if len(word) > 3:
                weakness_keywords.add(word)
    for dev in weakness_data.get("developing_skills", []):
        for word in dev["skill"].lower().split():
            if len(word) > 3:
                weakness_keywords.add(word)

    relevant = []
    for std in standards:
        topics = [t.lower() for t in std.get('topics', [])]
        benchmark = std.get('benchmark', '').lower()
        vocab = [v.lower() for v in std.get('vocabulary', [])]
        all_text = ' '.join(topics + [benchmark] + vocab)

        match_count = sum(1 for kw in weakness_keywords if kw in all_text)
        if match_count > 0:
            std_dok = std.get('dok', '')
            dok_match = True
            if target_dok is not None and std_dok:
                try:
                    dok_val = int(std_dok) if str(std_dok).isdigit() else 0
                    dok_match = dok_val <= target_dok
                except (ValueError, TypeError):
                    dok_match = True

            relevant.append({
                "code": std.get('code', ''),
                "benchmark": std.get('benchmark', '')[:200],
                "topics": std.get('topics', []),
                "dok": std_dok,
                "essential_questions": std.get('essential_questions', [])[:2],
                "learning_targets": std.get('learning_targets', [])[:2],
                "relevance_score": match_count,
                "dok_appropriate": dok_match,
            })

    relevant.sort(key=lambda x: (-int(x["dok_appropriate"]), -x["relevance_score"]))
    return relevant[:5]


def recommend_next_lesson(assignment_name=None, period=None, num_assignments=1, teacher_id='local-dev'):
    """Analyze performance and recommend next lesson focus with period differentiation and IEP awareness."""
    require_teacher_id(teacher_id)
    results = _load_results(teacher_id)
    if not results:
        return {"error": "No grading results available"}

    num_assignments = min(num_assignments or 1, 5)

    # Determine which assignment(s) to analyze
    if assignment_name:
        target_results = [r for r in results
                          if assignment_name.lower() in r.get('assignment', '').lower()]
    else:
        sorted_results = sorted(results, key=lambda r: r.get('graded_at', ''), reverse=True)
        recent_assignments = []
        seen = set()
        for r in sorted_results:
            a = r.get('assignment', '')
            if a and a not in seen:
                seen.add(a)
                recent_assignments.append(a)
            if len(recent_assignments) >= num_assignments:
                break
        target_results = [r for r in results if r.get('assignment', '') in recent_assignments]

    if period:
        target_results = [r for r in target_results if r.get('period', '') == period]

    if not target_results:
        return {"error": "No matching results found for analysis"}

    analyzed_assignments = list(set(r.get('assignment', '') for r in target_results))

    # Load supplementary data
    period_levels = _load_period_class_levels(teacher_id)
    accommodations = _load_accommodations(teacher_id)
    standards = _load_standards()
    settings = _load_settings(teacher_id)
    config = settings.get('config', {})
    global_notes = settings.get('globalAINotes', '')
    saved_lessons = _load_saved_lessons(teacher_id)

    # === Overall weakness analysis ===
    overall = _analyze_group_weaknesses(target_results)

    # === Per-class-level analysis ===
    # Group results by class level (advanced/standard/support)
    level_groups = defaultdict(list)
    periods_by_level = defaultdict(list)

    for r in target_results:
        p = r.get('period', '')
        level = period_levels.get(p, 'standard')
        level_groups[level].append(r)
        if p not in periods_by_level[level]:
            periods_by_level[level].append(p)

    # DOK targets by class level
    dok_targets = {"advanced": 4, "standard": 3, "support": 2}

    class_level_analysis = {}
    for level in ["advanced", "standard", "support"]:
        group = level_groups.get(level, [])
        if not group:
            continue
        weakness = _analyze_group_weaknesses(group)
        if not weakness:
            continue

        target_dok = dok_targets.get(level, 3)
        matched_standards = _match_standards(weakness, standards, target_dok=target_dok)

        # Build skill needs for this level
        skill_needs = []
        cw = weakness["category_weaknesses"]
        if cw:
            weakest = cw[0]
            skill_needs.append(f"Weakest area: {weakest['category']} (avg {weakest['average']})")
        cg = weakness["content_gaps"]
        if cg:
            skill_needs.append(f"Most skipped: '{cg[0]['topic']}' ({cg[0]['pct']}%)")
        ds = weakness["developing_skills"]
        if ds:
            skill_needs.append(f"Top developing: '{ds[0]['skill']}' ({ds[0]['count']} students)")
        if weakness["omission_rate"] > 40:
            skill_needs.append(f"High omission rate: {weakness['omission_rate']}%")

        class_level_analysis[level] = {
            "class_level": level,
            "periods": periods_by_level[level],
            "target_dok": target_dok,
            "identified_needs": skill_needs,
            "recommended_standards": matched_standards,
            **weakness,
        }

    # === IEP/504 Accommodation Analysis ===
    accommodation_analysis = None
    if accommodations:
        # Match accommodated students to results by student_id or name
        accom_ids = set(accommodations.keys())
        accom_results = []
        non_accom_results = []
        matched_students = {}

        for r in target_results:
            sid = r.get('student_id', '')
            sname = r.get('student_name', '').lower().replace(' ', '_')
            if sid in accom_ids:
                accom_results.append(r)
                matched_students[sid] = accommodations[sid]
            elif sname in accom_ids:
                accom_results.append(r)
                matched_students[sname] = accommodations[sname]
            else:
                non_accom_results.append(r)

        if accom_results:
            accom_weakness = _analyze_group_weaknesses(accom_results)
            non_accom_weakness = _analyze_group_weaknesses(non_accom_results) if non_accom_results else None

            # Collect unique presets across matched students
            all_presets = set()
            for info in matched_students.values():
                for p in info.get('presets', []):
                    all_presets.add(p)

            score_gap = None
            if accom_weakness and non_accom_weakness:
                score_gap = round(non_accom_weakness["average_score"] - accom_weakness["average_score"], 1)

            accommodation_analysis = {
                "accommodated_student_count": len(accom_results),
                "total_student_count": len(target_results),
                "accommodation_presets_in_use": sorted(all_presets),
                "accommodated_avg_score": accom_weakness["average_score"] if accom_weakness else None,
                "non_accommodated_avg_score": non_accom_weakness["average_score"] if non_accom_weakness else None,
                "score_gap": score_gap,
                "accommodated_failing_pct": accom_weakness["failing_pct"] if accom_weakness else None,
                "accommodated_omission_rate": accom_weakness["omission_rate"] if accom_weakness else None,
                "accommodated_weaknesses": accom_weakness["category_weaknesses"][:3] if accom_weakness else [],
                "note": "IEP/504 students may need modified lesson pacing, scaffolded activities, or alternative assessments.",
            }

    # === Overall standards (no DOK filter) for the combined view ===
    overall_standards = _match_standards(overall, standards, target_dok=None)

    # === Build top-level identified needs ===
    skill_needs = []
    if overall["category_weaknesses"]:
        weakest = overall["category_weaknesses"][0]
        skill_needs.append(f"Weakest rubric area: {weakest['category']} (avg {weakest['average']})")
    if overall["content_gaps"]:
        top_gap = overall["content_gaps"][0]
        skill_needs.append(f"Most skipped section: '{top_gap['topic']}' ({top_gap['students_missed']} students, "
                          f"{top_gap['pct']}%)")
    if overall["developing_skills"]:
        skill_needs.append(f"Top developing skill: '{overall['developing_skills'][0]['skill']}' "
                          f"({overall['developing_skills'][0]['count']} students)")
    if overall["omission_rate"] > 40:
        skill_needs.append(f"High omission rate: {overall['omission_rate']}% of students "
                          f"left questions blank — consider assignment completion mini-lesson")

    # Note if class levels diverge significantly
    if len(class_level_analysis) > 1:
        level_avgs = {lv: d["average_score"] for lv, d in class_level_analysis.items()}
        max_avg = max(level_avgs.values())
        min_avg = min(level_avgs.values())
        if max_avg - min_avg > 10:
            skill_needs.append(
                f"Large gap between class levels: {max_avg} (highest) vs {min_avg} (lowest) — "
                f"differentiated lesson planning recommended"
            )

    return {
        "analyzed_assignments": analyzed_assignments,
        "period_filter": period or "all periods",
        "total_students": overall["total_students"],
        "average_score": overall["average_score"],
        "failing_count": overall["failing_count"],
        "failing_pct": overall["failing_pct"],
        "identified_needs": skill_needs,
        "category_weaknesses": overall["category_weaknesses"],
        "content_gaps": overall["content_gaps"],
        "developing_skills": overall["developing_skills"],
        "student_strengths": overall["student_strengths"],
        "relevant_standards": overall_standards,
        "existing_lessons": [l["title"] for l in saved_lessons],
        "teacher_subject": config.get('subject', ''),
        "teacher_grade": config.get('grade_level', ''),
        "period_differentiation_notes": global_notes[:500] if global_notes else "",
        "class_level_breakdown": class_level_analysis if class_level_analysis else None,
        "period_class_levels": period_levels if period_levels else None,
        "accommodation_analysis": accommodation_analysis,
    }


def get_recent_lessons(unit_name=None, teacher_id='local-dev'):
    """List saved lesson plans with full detail for document generation context."""
    require_teacher_id(teacher_id)
    if not os.path.exists(LESSONS_DIR):
        return {"error": "No saved lessons found. Generate and save lesson plans in the Planner tab first."}

    lessons = []
    for unit_dir in os.listdir(LESSONS_DIR):
        unit_path = os.path.join(LESSONS_DIR, unit_dir)
        if not os.path.isdir(unit_path):
            continue

        # Filter by unit name if provided
        if unit_name and unit_name.lower() not in unit_dir.lower():
            continue

        for fname in os.listdir(unit_path):
            if not fname.endswith('.json'):
                continue
            try:
                with open(os.path.join(unit_path, fname), 'r', encoding='utf-8') as fh:
                    data = json.load(fh)

                # Extract day-level details
                days_summary = []
                all_vocab = []
                all_standards = []
                for day in data.get('days', []):
                    day_info = {
                        "day": day.get("day"),
                        "topic": day.get("topic", ""),
                        "objective": day.get("objective", ""),
                    }
                    # Collect standards addressed
                    stds = day.get("standards_addressed", [])
                    if stds:
                        day_info["standards"] = stds
                        all_standards.extend(stds)
                    # Collect vocabulary
                    vocab = day.get("vocabulary", [])
                    for v in vocab:
                        term = v.get("term", v) if isinstance(v, dict) else str(v)
                        if term and term not in all_vocab:
                            all_vocab.append(term)
                    days_summary.append(day_info)

                lessons.append({
                    "unit": unit_dir,
                    "title": data.get("title", fname.replace(".json", "")),
                    "overview": data.get("overview", ""),
                    "essential_questions": data.get("essential_questions", []),
                    "num_days": len(data.get("days", [])),
                    "days": days_summary,
                    "vocabulary": all_vocab,
                    "standards_covered": list(set(all_standards)),
                    "saved_at": data.get("_saved_at", ""),
                })
            except Exception as e:  # noqa: BLE001  # broad catch: error is logged
                sentry_sdk.capture_exception(e)
                continue

    if not lessons:
        msg = f"No lessons found for unit '{unit_name}'." if unit_name else "No saved lessons found."
        return {"error": msg}

    # Sort by saved_at (most recent first), cap at 10
    lessons.sort(key=lambda x: x.get("saved_at", ""), reverse=True)
    lessons = lessons[:10]

    # Group by unit for readability
    units = {}
    for lesson in lessons:
        unit = lesson["unit"]
        if unit not in units:
            units[unit] = []
        units[unit].append(lesson)

    return {
        "total_lessons": len(lessons),
        "units": list(units.keys()),
        "lessons": lessons,
    }
