"""
Periodic Roster Sync — Webhook Endpoint
========================================
POST /api/sync/periodic-roster

Auth: Bearer token matching PERIODIC_SYNC_SECRET env var.
Rate limited: 1 request per 5 minutes.
"""

import os
import time
import logging
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify

from backend.extensions import limiter
from backend.utils.audit import audit_log
from backend.storage import load as storage_load, save as storage_save

logger = logging.getLogger(__name__)

sync_bp = Blueprint('sync', __name__)

MAX_TEACHERS_PER_RUN = 50


def get_supabase():
    """Get Supabase client. Module-level wrapper for testability."""
    try:
        from backend.supabase_client import get_supabase as _get_sb
        return _get_sb()
    except Exception:
        return None


def _validate_secret():
    """Validate the Authorization: Bearer <secret> header."""
    expected = os.environ.get('PERIODIC_SYNC_SECRET')
    if not expected:
        return False
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return False
    return auth[7:] == expected


def _discover_teachers():
    """Find teachers eligible for periodic sync.

    Returns list of dicts: [{teacher_id, provider, config}, ...]
    Paged via cursor stored in teacher_data key 'sync:last_cursor'.
    """
    try:
        sb = get_supabase()
        if not sb:
            return []

        # Get all teachers with SIS config
        config_result = sb.table('teacher_data').select(
            'teacher_id, data, updated_at'
        ).eq('data_key', 'district:sis_config').execute()

        if not config_result.data:
            return []

        # Get teachers with recent activity (student sessions in last 30 days)
        cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=30)).isoformat()
        session_result = sb.table('student_sessions').select(
            'teacher_id'
        ).gt('created_at', cutoff).execute()

        active_teacher_ids = {s['teacher_id'] for s in (session_result.data or [])}

        # Also include teachers whose SIS config was updated in last 30 days
        eligible = []
        for row in config_result.data:
            tid = row['teacher_id']
            updated_at = row.get('updated_at', '')
            config_recent = updated_at and updated_at > cutoff
            if tid in active_teacher_ids or config_recent:
                config = row.get('data', {})
                if isinstance(config, str):
                    import json
                    config = json.loads(config)
                provider = config.get('provider', '')
                if provider in ('clever', 'oneroster'):
                    eligible.append({
                        'teacher_id': tid,
                        'provider': provider,
                        'config': config,
                    })

        if not eligible:
            return []

        # Sort by teacher_id for cursor-based paging
        eligible.sort(key=lambda t: t['teacher_id'])

        # Apply cursor
        cursor = storage_load('sync:last_cursor', 'system')
        if cursor and isinstance(cursor, dict):
            last_id = cursor.get('last_teacher_id', '')
            # Filter to teachers after the cursor
            eligible = [t for t in eligible if t['teacher_id'] > last_id]
            # If we've gone past all teachers, wrap around
            if not eligible:
                # Re-query without cursor (start from beginning)
                eligible_all = []
                for row in config_result.data:
                    tid = row['teacher_id']
                    updated_at = row.get('updated_at', '')
                    config_recent = updated_at and updated_at > cutoff
                    if tid in active_teacher_ids or config_recent:
                        config = row.get('data', {})
                        if isinstance(config, str):
                            import json
                            config = json.loads(config)
                        provider = config.get('provider', '')
                        if provider in ('clever', 'oneroster'):
                            eligible_all.append({
                                'teacher_id': tid,
                                'provider': provider,
                                'config': config,
                            })
                eligible_all.sort(key=lambda t: t['teacher_id'])
                eligible = eligible_all

        # Cap at MAX_TEACHERS_PER_RUN
        if len(eligible) > MAX_TEACHERS_PER_RUN:
            logger.warning("Capping periodic sync at %d teachers (total eligible: %d)",
                           MAX_TEACHERS_PER_RUN, len(eligible))
            eligible = eligible[:MAX_TEACHERS_PER_RUN]

        return eligible

    except Exception as e:
        logger.exception("Teacher discovery failed: %s", e)
        return []


def _save_cursor(last_teacher_id):
    """Save the paging cursor after a successful batch."""
    try:
        storage_save('sync:last_cursor', {'last_teacher_id': last_teacher_id}, 'system')
    except Exception as e:
        logger.warning("Failed to save sync cursor: %s", e)


def _sync_one_teacher(teacher):
    """Sync roster for a single teacher. Returns result dict."""
    import asyncio
    from backend.roster_sync import sync_roster_to_db, deactivate_missing_students

    teacher_id = teacher['teacher_id']
    provider = teacher['provider']
    config = teacher['config']
    start = time.time()

    try:
        if provider == 'clever':
            from backend.clever import sync_roster as clever_sync_roster
            from backend.routes.clever_routes import _sync_classes_to_db

            district_token = config.get('district_token') or os.environ.get('CLEVER_DISTRICT_TOKEN')
            if not district_token:
                return {"teacher_id": teacher_id, "provider": provider,
                        "status": "skipped", "error": "No Clever district token",
                        "duration_s": round(time.time() - start, 1)}

            loop = asyncio.new_event_loop()
            try:
                roster_data = loop.run_until_complete(clever_sync_roster(district_token))
            finally:
                loop.close()

            sections = roster_data.get('sections', [])
            students = roster_data.get('students', [])

            counts = _sync_classes_to_db(sections, students, teacher_id)

            # Collect current student external IDs for deactivation
            current_ids = {s['data']['id'] for s in students if 'data' in s and 'id' in s['data']}
            deactivated = deactivate_missing_students(teacher_id, current_ids, "clever")

        elif provider == 'oneroster':
            from backend.oneroster import OneRosterClient, normalize_roster, get_oneroster_config

            or_config = get_oneroster_config(teacher_id)
            client = OneRosterClient(
                base_url=or_config['base_url'],
                client_id=or_config['client_id'],
                client_secret=or_config['client_secret'],
                token_url=or_config.get('token_url'),
            )

            loop = asyncio.new_event_loop()
            try:
                raw = loop.run_until_complete(client.fetch_roster(
                    school_id=or_config.get('school_id'),
                    teacher_sourced_id=or_config.get('teacher_sourced_id'),
                ))
            finally:
                loop.close()

            normalized = normalize_roster(raw)
            counts = sync_roster_to_db(
                normalized['classes'], normalized['students'],
                normalized['enrollments'], teacher_id, provider="oneroster"
            )

            current_ids = {s['external_id'] for s in normalized['students']}
            deactivated = deactivate_missing_students(teacher_id, current_ids, "oneroster")

        else:
            return {"teacher_id": teacher_id, "provider": provider,
                    "status": "skipped", "error": "Unknown provider: " + provider,
                    "duration_s": round(time.time() - start, 1)}

        duration = round(time.time() - start, 1)

        audit_log(
            action="PERIODIC_SYNC",
            details="provider=" + provider + " classes=" + str(counts.get('classes', 0)) +
                    " students=" + str(counts.get('students', 0)) + " deactivated=" + str(deactivated),
            user="system",
            teacher_id=teacher_id,
        )

        return {
            "teacher_id": teacher_id,
            "provider": provider,
            "status": "success",
            "classes": counts.get("classes", 0),
            "students": counts.get("students", 0),
            "deactivated": deactivated,
            "duration_s": duration,
        }

    except Exception as e:
        duration = round(time.time() - start, 1)
        logger.exception("Periodic sync failed for teacher %s (%s): %s",
                         teacher_id, provider, e)
        return {
            "teacher_id": teacher_id,
            "provider": provider,
            "status": "failed",
            "error": str(e)[:200],
            "duration_s": duration,
        }


@sync_bp.route('/api/sync/periodic-roster', methods=['POST'])
@limiter.limit("1 per 5 minutes")
def periodic_roster_sync():
    """Webhook endpoint for cron-triggered periodic roster sync."""
    if not _validate_secret():
        return jsonify({"error": "Unauthorized"}), 401

    teachers = _discover_teachers()
    results = []

    for teacher in teachers:
        result = _sync_one_teacher(teacher)
        results.append(result)

    # Save cursor after successful batch
    if teachers:
        last_id = teachers[-1]['teacher_id']
        _save_cursor(last_id)

    synced = sum(1 for r in results if r.get('status') == 'success')
    failed = sum(1 for r in results if r.get('status') == 'failed')
    skipped = sum(1 for r in results if r.get('status') == 'skipped')

    return jsonify({
        "synced": synced,
        "failed": failed,
        "skipped": skipped,
        "total_teachers": len(teachers),
        "has_failures": failed > 0,
        "details": results,
    })
