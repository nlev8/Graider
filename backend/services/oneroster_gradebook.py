"""
OneRoster Gradebook Service
============================
High-level helpers that wrap OneRosterClient gradebook methods and persist
line item mappings in teacher_data storage.
"""

from datetime import datetime, timezone
import logging

import sentry_sdk

from backend.storage import load, save

logger = logging.getLogger(__name__)

DATA_KEY = "oneroster_line_items"


async def ensure_line_item(client, teacher_id, assessment_id, title, total_points, class_sourced_id):
    """Return the OneRoster line_item_id for the given assessment, creating it if needed.

    Checks the stored mapping in teacher_data (key: oneroster_line_items).
    If a mapping already exists for assessment_id, returns the cached line_item_id.
    Otherwise calls client.create_line_item() and persists the new mapping.

    Args:
        client: OneRosterClient instance.
        teacher_id: Teacher's Supabase UUID or 'local-dev'.
        assessment_id: Graider assessment identifier (used as mapping key).
        title: Display title for the line item.
        total_points: Max score for the line item.
        class_sourced_id: OneRoster class sourcedId to associate the line item with.

    Returns:
        line_item_id string.
    """
    mapping = load(DATA_KEY, teacher_id) or {}

    if assessment_id in mapping:
        return mapping[assessment_id]["line_item_id"]

    line_item = await client.create_line_item(
        title=title,
        class_sourced_id=class_sourced_id,
        max_score=total_points,
    )
    line_item_id = line_item["sourcedId"]

    mapping[assessment_id] = {
        "line_item_id": line_item_id,
        "class_sourced_id": class_sourced_id,
        "title": title,
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    save(DATA_KEY, mapping, teacher_id)

    return line_item_id


async def post_results(client, line_item_id, scores):
    """Post a batch of student scores to a OneRoster line item.

    Args:
        client: OneRosterClient instance.
        line_item_id: The OneRoster line item sourcedId.
        scores: List of dicts, each with keys:
            - student_sourced_id: str (may be empty/None — will be skipped)
            - score: numeric score
            - max_score: numeric max score
            - comment: optional comment string

    Returns:
        Dict with counts: {"synced": N, "skipped": N, "failed": N, "errors": [...]}
    """
    synced = 0
    skipped = 0
    failed = 0
    errors = []

    for entry in scores:
        student_sourced_id = entry.get("student_sourced_id")

        if not student_sourced_id:
            skipped += 1
            continue

        try:
            await client.create_result(
                line_item_id=line_item_id,
                student_sourced_id=student_sourced_id,
                score=entry.get("score"),
                max_score=entry.get("max_score"),
                comment=entry.get("comment", ""),
            )
            synced += 1
        except Exception as exc:
            failed += 1
            errors.append(str(exc))
            sentry_sdk.capture_exception(exc)
            logger.warning(
                "post_results: failed for student %s on line_item %s: %s",
                student_sourced_id, line_item_id, exc,
            )

    return {"synced": synced, "skipped": skipped, "failed": failed, "errors": errors}
