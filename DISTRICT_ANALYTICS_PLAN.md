# District & School Analytics Implementation Plan

## Overview

Add multi-level analytics that aggregate grading data across teachers, schools, and the entire district. Enables administrators to view performance trends, identify struggling areas, and make data-driven decisions.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         DISTRICT LEVEL                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │  School A   │  │  School B   │  │  School C   │             │
│  │             │  │             │  │             │             │
│  │ ┌─────────┐ │  │ ┌─────────┐ │  │ ┌─────────┐ │             │
│  │ │Teacher 1│ │  │ │Teacher 4│ │  │ │Teacher 7│ │             │
│  │ │Teacher 2│ │  │ │Teacher 5│ │  │ │Teacher 8│ │             │
│  │ │Teacher 3│ │  │ │Teacher 6│ │  │ │Teacher 9│ │             │
│  │ └─────────┘ │  │ └─────────┘ │  │ └─────────┘ │             │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘             │
│         │                │                │                     │
│         └────────────────┼────────────────┘                     │
│                          ▼                                      │
│              ┌───────────────────────┐                          │
│              │  District Data Store  │                          │
│              │  ~/.graider_district/ │                          │
│              └───────────────────────┘                          │
└─────────────────────────────────────────────────────────────────┘
```

## Data Model

### New Files Structure

```
~/.graider_district/
├── config.json              # District/school configuration
├── schools/
│   ├── school_001.json      # School metadata
│   ├── school_002.json
│   └── ...
├── teachers/
│   ├── teacher_001.json     # Teacher metadata + school assignment
│   └── ...
├── aggregated/
│   ├── district_stats.json  # Cached district-wide stats
│   ├── school_001_stats.json
│   └── ...
└── sync_log.json            # Data sync history
```

---

## File 1: Create `backend/district_analytics.py`

```python
"""
District & School Analytics Manager
====================================
Aggregates grading data across teachers, schools, and districts.
Provides multi-level analytics for administrators.
"""

import os
import json
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path

DISTRICT_DIR = os.path.expanduser("~/.graider_district")


def ensure_district_dir():
    """Create district directory structure if it doesn't exist."""
    dirs = [
        DISTRICT_DIR,
        os.path.join(DISTRICT_DIR, "schools"),
        os.path.join(DISTRICT_DIR, "teachers"),
        os.path.join(DISTRICT_DIR, "aggregated"),
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)


def get_district_config():
    """Load or create district configuration."""
    ensure_district_dir()
    config_path = os.path.join(DISTRICT_DIR, "config.json")

    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            return json.load(f)

    # Default config
    config = {
        "district_name": "",
        "district_id": "",
        "schools": [],
        "admin_users": [],
        "created_at": datetime.now().isoformat(),
        "settings": {
            "auto_sync": True,
            "sync_interval_minutes": 30,
            "anonymize_student_names": True,
        }
    }

    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)

    return config


def save_district_config(config):
    """Save district configuration."""
    ensure_district_dir()
    config_path = os.path.join(DISTRICT_DIR, "config.json")
    config["updated_at"] = datetime.now().isoformat()

    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)


# ══════════════════════════════════════════════════════════════
# SCHOOL MANAGEMENT
# ══════════════════════════════════════════════════════════════

def create_school(school_id: str, school_name: str, metadata: dict = None):
    """Create a new school entry."""
    ensure_district_dir()
    school_path = os.path.join(DISTRICT_DIR, "schools", f"{school_id}.json")

    school_data = {
        "school_id": school_id,
        "school_name": school_name,
        "created_at": datetime.now().isoformat(),
        "teachers": [],
        "metadata": metadata or {},
    }

    with open(school_path, 'w') as f:
        json.dump(school_data, f, indent=2)

    # Add to district config
    config = get_district_config()
    if school_id not in config["schools"]:
        config["schools"].append(school_id)
        save_district_config(config)

    return school_data


def get_school(school_id: str):
    """Get school data."""
    school_path = os.path.join(DISTRICT_DIR, "schools", f"{school_id}.json")
    if os.path.exists(school_path):
        with open(school_path, 'r') as f:
            return json.load(f)
    return None


def list_schools():
    """List all schools in the district."""
    ensure_district_dir()
    schools = []
    schools_dir = os.path.join(DISTRICT_DIR, "schools")

    for filename in os.listdir(schools_dir):
        if filename.endswith('.json'):
            with open(os.path.join(schools_dir, filename), 'r') as f:
                schools.append(json.load(f))

    return sorted(schools, key=lambda x: x.get("school_name", ""))


# ══════════════════════════════════════════════════════════════
# TEACHER MANAGEMENT
# ══════════════════════════════════════════════════════════════

def register_teacher(teacher_id: str, teacher_name: str, school_id: str, metadata: dict = None):
    """Register a teacher in the district system."""
    ensure_district_dir()
    teacher_path = os.path.join(DISTRICT_DIR, "teachers", f"{teacher_id}.json")

    teacher_data = {
        "teacher_id": teacher_id,
        "teacher_name": teacher_name,
        "school_id": school_id,
        "registered_at": datetime.now().isoformat(),
        "last_sync": None,
        "metadata": metadata or {},
        "stats": {
            "total_assignments_graded": 0,
            "total_students": 0,
            "subjects": [],
        }
    }

    with open(teacher_path, 'w') as f:
        json.dump(teacher_data, f, indent=2)

    # Add teacher to school
    school = get_school(school_id)
    if school and teacher_id not in school.get("teachers", []):
        school["teachers"].append(teacher_id)
        school_path = os.path.join(DISTRICT_DIR, "schools", f"{school_id}.json")
        with open(school_path, 'w') as f:
            json.dump(school, f, indent=2)

    return teacher_data


def get_teacher(teacher_id: str):
    """Get teacher data."""
    teacher_path = os.path.join(DISTRICT_DIR, "teachers", f"{teacher_id}.json")
    if os.path.exists(teacher_path):
        with open(teacher_path, 'r') as f:
            return json.load(f)
    return None


def list_teachers(school_id: str = None):
    """List teachers, optionally filtered by school."""
    ensure_district_dir()
    teachers = []
    teachers_dir = os.path.join(DISTRICT_DIR, "teachers")

    if not os.path.exists(teachers_dir):
        return teachers

    for filename in os.listdir(teachers_dir):
        if filename.endswith('.json'):
            with open(os.path.join(teachers_dir, filename), 'r') as f:
                teacher = json.load(f)
                if school_id is None or teacher.get("school_id") == school_id:
                    teachers.append(teacher)

    return sorted(teachers, key=lambda x: x.get("teacher_name", ""))


# ══════════════════════════════════════════════════════════════
# DATA SYNC (Teacher → District)
# ══════════════════════════════════════════════════════════════

def sync_teacher_data(teacher_id: str, grading_data: list):
    """
    Sync a teacher's grading data to the district store.

    Args:
        teacher_id: The teacher's ID
        grading_data: List of grading results from master_grades.csv

    Returns:
        dict with sync status and stats
    """
    ensure_district_dir()

    teacher = get_teacher(teacher_id)
    if not teacher:
        return {"error": "Teacher not registered"}

    # Anonymize student data for district storage
    config = get_district_config()
    anonymize = config.get("settings", {}).get("anonymize_student_names", True)

    processed_data = []
    for record in grading_data:
        processed = {
            "date": record.get("Date", record.get("date", "")),
            "assignment": record.get("Assignment", record.get("assignment", "")),
            "quarter": record.get("Quarter", record.get("quarter", "")),
            "score": float(record.get("Overall Score", record.get("score", 0)) or 0),
            "letter_grade": record.get("Letter Grade", record.get("letter_grade", "")),
            "subject": record.get("Subject", teacher.get("metadata", {}).get("subject", "")),
            "grade_level": record.get("Grade Level", teacher.get("metadata", {}).get("grade_level", "")),
            "content_accuracy": float(record.get("Content Accuracy", 0) or 0),
            "completeness": float(record.get("Completeness", 0) or 0),
            "writing_quality": float(record.get("Writing Quality", 0) or 0),
            "effort_engagement": float(record.get("Effort Engagement", 0) or 0),
            "teacher_id": teacher_id,
            "school_id": teacher.get("school_id"),
        }

        if anonymize:
            # Use hashed student ID only
            processed["student_hash"] = hash(record.get("Student ID", "")) % 10000000
        else:
            processed["student_id"] = record.get("Student ID", "")
            processed["student_name"] = record.get("Student Name", "")

        processed_data.append(processed)

    # Save synced data
    sync_path = os.path.join(DISTRICT_DIR, "teachers", f"{teacher_id}_data.json")
    with open(sync_path, 'w') as f:
        json.dump({
            "teacher_id": teacher_id,
            "school_id": teacher.get("school_id"),
            "synced_at": datetime.now().isoformat(),
            "record_count": len(processed_data),
            "records": processed_data,
        }, f, indent=2)

    # Update teacher stats
    teacher["last_sync"] = datetime.now().isoformat()
    teacher["stats"]["total_assignments_graded"] = len(processed_data)
    unique_students = set()
    subjects = set()
    for r in processed_data:
        if anonymize:
            unique_students.add(r.get("student_hash"))
        else:
            unique_students.add(r.get("student_id"))
        if r.get("subject"):
            subjects.add(r["subject"])

    teacher["stats"]["total_students"] = len(unique_students)
    teacher["stats"]["subjects"] = list(subjects)

    teacher_path = os.path.join(DISTRICT_DIR, "teachers", f"{teacher_id}.json")
    with open(teacher_path, 'w') as f:
        json.dump(teacher, f, indent=2)

    # Log sync
    log_sync(teacher_id, len(processed_data))

    # Trigger aggregation refresh
    refresh_aggregated_stats(teacher.get("school_id"))

    return {
        "status": "success",
        "records_synced": len(processed_data),
        "synced_at": teacher["last_sync"],
    }


def log_sync(teacher_id: str, record_count: int):
    """Log a sync event."""
    log_path = os.path.join(DISTRICT_DIR, "sync_log.json")

    log = []
    if os.path.exists(log_path):
        with open(log_path, 'r') as f:
            log = json.load(f)

    log.append({
        "teacher_id": teacher_id,
        "timestamp": datetime.now().isoformat(),
        "records": record_count,
    })

    # Keep last 1000 entries
    log = log[-1000:]

    with open(log_path, 'w') as f:
        json.dump(log, f, indent=2)


# ══════════════════════════════════════════════════════════════
# AGGREGATED ANALYTICS
# ══════════════════════════════════════════════════════════════

def refresh_aggregated_stats(school_id: str = None):
    """Refresh aggregated statistics for a school or entire district."""
    ensure_district_dir()

    if school_id:
        _aggregate_school_stats(school_id)

    _aggregate_district_stats()


def _aggregate_school_stats(school_id: str):
    """Aggregate stats for a single school."""
    school = get_school(school_id)
    if not school:
        return

    all_records = []
    teacher_stats = []

    for teacher_id in school.get("teachers", []):
        data_path = os.path.join(DISTRICT_DIR, "teachers", f"{teacher_id}_data.json")
        if os.path.exists(data_path):
            with open(data_path, 'r') as f:
                data = json.load(f)
                all_records.extend(data.get("records", []))
                teacher = get_teacher(teacher_id)
                if teacher:
                    teacher_stats.append({
                        "teacher_id": teacher_id,
                        "teacher_name": teacher.get("teacher_name"),
                        "assignments_graded": data.get("record_count", 0),
                        "last_sync": data.get("synced_at"),
                    })

    if not all_records:
        return

    # Calculate school stats
    scores = [r["score"] for r in all_records if r.get("score")]

    stats = {
        "school_id": school_id,
        "school_name": school.get("school_name"),
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "total_assignments": len(all_records),
            "total_teachers": len(school.get("teachers", [])),
            "unique_students": len(set(r.get("student_hash", r.get("student_id")) for r in all_records)),
            "average_score": round(sum(scores) / len(scores), 1) if scores else 0,
            "highest_score": max(scores) if scores else 0,
            "lowest_score": min(scores) if scores else 0,
        },
        "grade_distribution": {
            "A": len([s for s in scores if s >= 90]),
            "B": len([s for s in scores if 80 <= s < 90]),
            "C": len([s for s in scores if 70 <= s < 80]),
            "D": len([s for s in scores if 60 <= s < 70]),
            "F": len([s for s in scores if s < 60]),
        },
        "by_subject": _group_by_field(all_records, "subject"),
        "by_grade_level": _group_by_field(all_records, "grade_level"),
        "by_quarter": _group_by_field(all_records, "quarter"),
        "teacher_stats": teacher_stats,
        "trends": _calculate_trends(all_records),
    }

    # Save school stats
    stats_path = os.path.join(DISTRICT_DIR, "aggregated", f"{school_id}_stats.json")
    with open(stats_path, 'w') as f:
        json.dump(stats, f, indent=2)


def _aggregate_district_stats():
    """Aggregate stats for the entire district."""
    config = get_district_config()

    all_records = []
    school_stats = []

    for school_id in config.get("schools", []):
        stats_path = os.path.join(DISTRICT_DIR, "aggregated", f"{school_id}_stats.json")
        if os.path.exists(stats_path):
            with open(stats_path, 'r') as f:
                stats = json.load(f)
                school_stats.append({
                    "school_id": school_id,
                    "school_name": stats.get("school_name"),
                    "average_score": stats.get("summary", {}).get("average_score", 0),
                    "total_assignments": stats.get("summary", {}).get("total_assignments", 0),
                    "total_teachers": stats.get("summary", {}).get("total_teachers", 0),
                    "total_students": stats.get("summary", {}).get("unique_students", 0),
                })

        # Load raw records for district-wide calculations
        school = get_school(school_id)
        if school:
            for teacher_id in school.get("teachers", []):
                data_path = os.path.join(DISTRICT_DIR, "teachers", f"{teacher_id}_data.json")
                if os.path.exists(data_path):
                    with open(data_path, 'r') as f:
                        data = json.load(f)
                        all_records.extend(data.get("records", []))

    if not all_records:
        return

    scores = [r["score"] for r in all_records if r.get("score")]

    district_stats = {
        "district_name": config.get("district_name", ""),
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "total_schools": len(config.get("schools", [])),
            "total_teachers": sum(s.get("total_teachers", 0) for s in school_stats),
            "total_students": len(set(r.get("student_hash", r.get("student_id")) for r in all_records)),
            "total_assignments": len(all_records),
            "average_score": round(sum(scores) / len(scores), 1) if scores else 0,
        },
        "grade_distribution": {
            "A": len([s for s in scores if s >= 90]),
            "B": len([s for s in scores if 80 <= s < 90]),
            "C": len([s for s in scores if 70 <= s < 80]),
            "D": len([s for s in scores if 60 <= s < 70]),
            "F": len([s for s in scores if s < 60]),
        },
        "by_subject": _group_by_field(all_records, "subject"),
        "by_grade_level": _group_by_field(all_records, "grade_level"),
        "school_comparison": sorted(school_stats, key=lambda x: x.get("average_score", 0), reverse=True),
        "trends": _calculate_trends(all_records),
    }

    # Save district stats
    stats_path = os.path.join(DISTRICT_DIR, "aggregated", "district_stats.json")
    with open(stats_path, 'w') as f:
        json.dump(district_stats, f, indent=2)


def _group_by_field(records: list, field: str) -> list:
    """Group records by a field and calculate stats."""
    groups = defaultdict(list)
    for r in records:
        key = r.get(field, "Unknown")
        if key:
            groups[key].append(r.get("score", 0))

    result = []
    for key, scores in groups.items():
        result.append({
            "name": key,
            "count": len(scores),
            "average": round(sum(scores) / len(scores), 1) if scores else 0,
        })

    return sorted(result, key=lambda x: x["count"], reverse=True)


def _calculate_trends(records: list) -> dict:
    """Calculate performance trends over time."""
    # Group by month
    monthly = defaultdict(list)
    for r in records:
        date_str = r.get("date", "")
        if date_str:
            try:
                # Parse YYYY-MM-DD format
                month = date_str[:7]  # YYYY-MM
                monthly[month].append(r.get("score", 0))
            except:
                pass

    trend_data = []
    for month, scores in sorted(monthly.items()):
        trend_data.append({
            "month": month,
            "average": round(sum(scores) / len(scores), 1) if scores else 0,
            "count": len(scores),
        })

    return trend_data[-12:]  # Last 12 months


# ══════════════════════════════════════════════════════════════
# ANALYTICS RETRIEVAL
# ══════════════════════════════════════════════════════════════

def get_district_analytics():
    """Get district-wide analytics."""
    stats_path = os.path.join(DISTRICT_DIR, "aggregated", "district_stats.json")
    if os.path.exists(stats_path):
        with open(stats_path, 'r') as f:
            return json.load(f)
    return None


def get_school_analytics(school_id: str):
    """Get analytics for a specific school."""
    stats_path = os.path.join(DISTRICT_DIR, "aggregated", f"{school_id}_stats.json")
    if os.path.exists(stats_path):
        with open(stats_path, 'r') as f:
            return json.load(f)
    return None


def get_teacher_analytics(teacher_id: str):
    """Get analytics for a specific teacher."""
    data_path = os.path.join(DISTRICT_DIR, "teachers", f"{teacher_id}_data.json")
    if not os.path.exists(data_path):
        return None

    with open(data_path, 'r') as f:
        data = json.load(f)

    records = data.get("records", [])
    if not records:
        return None

    scores = [r["score"] for r in records if r.get("score")]

    return {
        "teacher_id": teacher_id,
        "synced_at": data.get("synced_at"),
        "summary": {
            "total_assignments": len(records),
            "average_score": round(sum(scores) / len(scores), 1) if scores else 0,
            "unique_students": len(set(r.get("student_hash", r.get("student_id")) for r in records)),
        },
        "grade_distribution": {
            "A": len([s for s in scores if s >= 90]),
            "B": len([s for s in scores if 80 <= s < 90]),
            "C": len([s for s in scores if 70 <= s < 80]),
            "D": len([s for s in scores if 60 <= s < 70]),
            "F": len([s for s in scores if s < 60]),
        },
        "by_assignment": _group_by_field(records, "assignment"),
        "trends": _calculate_trends(records),
    }
```

---

## File 2: Create `backend/routes/district_routes.py`

```python
"""
District Analytics API Routes
"""

from flask import Blueprint, request, jsonify
from backend.district_analytics import (
    get_district_config,
    save_district_config,
    create_school,
    get_school,
    list_schools,
    register_teacher,
    get_teacher,
    list_teachers,
    sync_teacher_data,
    get_district_analytics,
    get_school_analytics,
    get_teacher_analytics,
    refresh_aggregated_stats,
)
import csv
import os

district_bp = Blueprint('district', __name__)


# ══════════════════════════════════════════════════════════════
# DISTRICT CONFIGURATION
# ══════════════════════════════════════════════════════════════

@district_bp.route('/api/district/config', methods=['GET'])
def get_config():
    """Get district configuration."""
    config = get_district_config()
    return jsonify(config)


@district_bp.route('/api/district/config', methods=['POST'])
def update_config():
    """Update district configuration."""
    data = request.json
    config = get_district_config()

    if "district_name" in data:
        config["district_name"] = data["district_name"]
    if "district_id" in data:
        config["district_id"] = data["district_id"]
    if "settings" in data:
        config["settings"].update(data["settings"])

    save_district_config(config)
    return jsonify({"status": "success", "config": config})


# ══════════════════════════════════════════════════════════════
# SCHOOL MANAGEMENT
# ══════════════════════════════════════════════════════════════

@district_bp.route('/api/district/schools', methods=['GET'])
def get_schools():
    """List all schools."""
    schools = list_schools()
    return jsonify({"schools": schools})


@district_bp.route('/api/district/schools', methods=['POST'])
def add_school():
    """Create a new school."""
    data = request.json

    if not data.get("school_id") or not data.get("school_name"):
        return jsonify({"error": "school_id and school_name required"}), 400

    school = create_school(
        data["school_id"],
        data["school_name"],
        data.get("metadata", {})
    )
    return jsonify({"status": "success", "school": school})


@district_bp.route('/api/district/schools/<school_id>', methods=['GET'])
def get_school_detail(school_id):
    """Get school details."""
    school = get_school(school_id)
    if not school:
        return jsonify({"error": "School not found"}), 404
    return jsonify(school)


# ══════════════════════════════════════════════════════════════
# TEACHER MANAGEMENT
# ══════════════════════════════════════════════════════════════

@district_bp.route('/api/district/teachers', methods=['GET'])
def get_teachers():
    """List teachers, optionally filtered by school."""
    school_id = request.args.get('school_id')
    teachers = list_teachers(school_id)
    return jsonify({"teachers": teachers})


@district_bp.route('/api/district/teachers', methods=['POST'])
def add_teacher():
    """Register a new teacher."""
    data = request.json

    required = ["teacher_id", "teacher_name", "school_id"]
    if not all(data.get(f) for f in required):
        return jsonify({"error": "teacher_id, teacher_name, and school_id required"}), 400

    teacher = register_teacher(
        data["teacher_id"],
        data["teacher_name"],
        data["school_id"],
        data.get("metadata", {})
    )
    return jsonify({"status": "success", "teacher": teacher})


@district_bp.route('/api/district/teachers/<teacher_id>', methods=['GET'])
def get_teacher_detail(teacher_id):
    """Get teacher details."""
    teacher = get_teacher(teacher_id)
    if not teacher:
        return jsonify({"error": "Teacher not found"}), 404
    return jsonify(teacher)


# ══════════════════════════════════════════════════════════════
# DATA SYNC
# ══════════════════════════════════════════════════════════════

@district_bp.route('/api/district/sync', methods=['POST'])
def sync_data():
    """Sync teacher's grading data to district store."""
    data = request.json

    teacher_id = data.get("teacher_id")
    if not teacher_id:
        return jsonify({"error": "teacher_id required"}), 400

    # Option 1: Data provided in request
    if data.get("grading_data"):
        result = sync_teacher_data(teacher_id, data["grading_data"])
        return jsonify(result)

    # Option 2: Read from teacher's master CSV
    output_folder = data.get("output_folder")
    if output_folder:
        master_file = os.path.join(output_folder, "master_grades.csv")
        if os.path.exists(master_file):
            grading_data = []
            with open(master_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    grading_data.append(row)

            result = sync_teacher_data(teacher_id, grading_data)
            return jsonify(result)
        else:
            return jsonify({"error": "master_grades.csv not found"}), 404

    return jsonify({"error": "grading_data or output_folder required"}), 400


@district_bp.route('/api/district/refresh', methods=['POST'])
def refresh_stats():
    """Manually refresh aggregated statistics."""
    data = request.json or {}
    school_id = data.get("school_id")

    refresh_aggregated_stats(school_id)
    return jsonify({"status": "success", "message": "Stats refreshed"})


# ══════════════════════════════════════════════════════════════
# ANALYTICS
# ══════════════════════════════════════════════════════════════

@district_bp.route('/api/district/analytics', methods=['GET'])
def district_analytics():
    """Get district-wide analytics."""
    analytics = get_district_analytics()
    if not analytics:
        return jsonify({"error": "No data available. Sync teacher data first."}), 404
    return jsonify(analytics)


@district_bp.route('/api/district/analytics/school/<school_id>', methods=['GET'])
def school_analytics(school_id):
    """Get school-level analytics."""
    analytics = get_school_analytics(school_id)
    if not analytics:
        return jsonify({"error": "No data available for this school"}), 404
    return jsonify(analytics)


@district_bp.route('/api/district/analytics/teacher/<teacher_id>', methods=['GET'])
def teacher_analytics(teacher_id):
    """Get teacher-level analytics."""
    analytics = get_teacher_analytics(teacher_id)
    if not analytics:
        return jsonify({"error": "No data available for this teacher"}), 404
    return jsonify(analytics)


@district_bp.route('/api/district/analytics/compare', methods=['GET'])
def compare_schools():
    """Compare metrics across schools."""
    analytics = get_district_analytics()
    if not analytics:
        return jsonify({"error": "No data available"}), 404

    return jsonify({
        "schools": analytics.get("school_comparison", []),
        "district_average": analytics.get("summary", {}).get("average_score", 0),
    })
```

---

## File 3: Modify `backend/routes/__init__.py`

### Add district routes registration

```python
# Add import at top
from .district_routes import district_bp

# Add registration in register_routes function
def register_routes(app, grading_state, run_grading_thread, reset_state):
    # ... existing registrations ...

    # District analytics routes
    app.register_blueprint(district_bp)
```

---

## File 4: Add District Analytics Tab to Frontend

### Edit `frontend/src/App.jsx`

#### 4.1: Add TABS entry (around line 20)

```javascript
// Add to TABS array
{ id: "district", label: "District", icon: "Building2" },
```

#### 4.2: Add state variables (around line 290)

```javascript
// District analytics state
const [districtData, setDistrictData] = useState(null);
const [districtView, setDistrictView] = useState("district"); // "district", "school", "teacher"
const [selectedSchool, setSelectedSchool] = useState(null);
const [selectedTeacher, setSelectedTeacher] = useState(null);
const [districtConfig, setDistrictConfig] = useState(null);
const [schools, setSchools] = useState([]);
const [teachers, setTeachers] = useState([]);
```

#### 4.3: Add useEffect to load district data (around line 600)

```javascript
// Load district data when tab opens
useEffect(() => {
  if (activeTab === "district") {
    // Load district config
    fetch('/api/district/config')
      .then(res => res.json())
      .then(data => setDistrictConfig(data))
      .catch(console.error);

    // Load schools list
    fetch('/api/district/schools')
      .then(res => res.json())
      .then(data => setSchools(data.schools || []))
      .catch(console.error);

    // Load district analytics
    fetch('/api/district/analytics')
      .then(res => res.json())
      .then(data => {
        if (!data.error) setDistrictData(data);
      })
      .catch(console.error);
  }
}, [activeTab]);

// Load school teachers when school selected
useEffect(() => {
  if (selectedSchool) {
    fetch(`/api/district/teachers?school_id=${selectedSchool}`)
      .then(res => res.json())
      .then(data => setTeachers(data.teachers || []))
      .catch(console.error);
  }
}, [selectedSchool]);
```

#### 4.4: Add District Tab JSX (after Analytics tab, around line 7900)

```jsx
{/* District Analytics Tab */}
{activeTab === "district" && (
  <div className="fade-in">
    {/* View Selector */}
    <div style={{ display: "flex", gap: "10px", marginBottom: "20px" }}>
      <button
        onClick={() => { setDistrictView("district"); setSelectedSchool(null); setSelectedTeacher(null); }}
        className={`btn ${districtView === "district" ? "btn-primary" : "btn-secondary"}`}
      >
        <Icon name="Building2" size={16} /> District Overview
      </button>
      <button
        onClick={() => setDistrictView("school")}
        className={`btn ${districtView === "school" ? "btn-primary" : "btn-secondary"}`}
      >
        <Icon name="School" size={16} /> School View
      </button>
      <button
        onClick={() => setDistrictView("teacher")}
        className={`btn ${districtView === "teacher" ? "btn-primary" : "btn-secondary"}`}
      >
        <Icon name="User" size={16} /> Teacher View
      </button>
    </div>

    {/* District Overview */}
    {districtView === "district" && districtData && (
      <>
        <h2 style={{ fontSize: "1.3rem", fontWeight: 700, marginBottom: "20px", display: "flex", alignItems: "center", gap: "10px" }}>
          <Icon name="Building2" size={24} />
          {districtConfig?.district_name || "District"} Analytics
        </h2>

        {/* Summary Cards */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: "15px", marginBottom: "20px" }}>
          {[
            { label: "Schools", value: districtData.summary?.total_schools || 0, icon: "School", color: "#6366f1" },
            { label: "Teachers", value: districtData.summary?.total_teachers || 0, icon: "Users", color: "#8b5cf6" },
            { label: "Students", value: districtData.summary?.total_students || 0, icon: "GraduationCap", color: "#ec4899" },
            { label: "Assignments", value: districtData.summary?.total_assignments || 0, icon: "FileCheck", color: "#10b981" },
            { label: "Avg Score", value: `${districtData.summary?.average_score || 0}%`, icon: "TrendingUp", color: "#f59e0b" },
          ].map((stat, i) => (
            <div key={i} className="glass-card" style={{ padding: "20px", textAlign: "center" }}>
              <Icon name={stat.icon} size={24} style={{ color: stat.color, marginBottom: "10px" }} />
              <div style={{ fontSize: "1.8rem", fontWeight: 800, color: stat.color }}>{stat.value}</div>
              <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>{stat.label}</div>
            </div>
          ))}
        </div>

        {/* School Comparison */}
        <div className="glass-card" style={{ padding: "25px", marginBottom: "20px" }}>
          <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "15px", display: "flex", alignItems: "center", gap: "10px" }}>
            <Icon name="BarChart3" size={20} /> School Comparison
          </h3>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--glass-border)" }}>
                <th style={{ textAlign: "left", padding: "10px" }}>School</th>
                <th style={{ textAlign: "right", padding: "10px" }}>Teachers</th>
                <th style={{ textAlign: "right", padding: "10px" }}>Students</th>
                <th style={{ textAlign: "right", padding: "10px" }}>Assignments</th>
                <th style={{ textAlign: "right", padding: "10px" }}>Avg Score</th>
              </tr>
            </thead>
            <tbody>
              {(districtData.school_comparison || []).map((school, i) => (
                <tr key={i} style={{ borderBottom: "1px solid var(--glass-border)" }}>
                  <td style={{ padding: "10px", fontWeight: 500 }}>{school.school_name}</td>
                  <td style={{ padding: "10px", textAlign: "right" }}>{school.total_teachers}</td>
                  <td style={{ padding: "10px", textAlign: "right" }}>{school.total_students}</td>
                  <td style={{ padding: "10px", textAlign: "right" }}>{school.total_assignments}</td>
                  <td style={{ padding: "10px", textAlign: "right" }}>
                    <span style={{
                      padding: "4px 12px",
                      borderRadius: "20px",
                      fontWeight: 700,
                      background: school.average_score >= 80 ? "rgba(74,222,128,0.2)" : school.average_score >= 70 ? "rgba(251,191,36,0.2)" : "rgba(248,113,113,0.2)",
                      color: school.average_score >= 80 ? "#4ade80" : school.average_score >= 70 ? "#fbbf24" : "#f87171",
                    }}>
                      {school.average_score}%
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Subject & Grade Level Breakdown */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px" }}>
          <div className="glass-card" style={{ padding: "25px" }}>
            <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "15px" }}>By Subject</h3>
            {(districtData.by_subject || []).map((s, i) => (
              <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "8px 0", borderBottom: "1px solid var(--glass-border)" }}>
                <span>{s.name}</span>
                <span style={{ fontWeight: 600 }}>{s.average}% avg ({s.count} assignments)</span>
              </div>
            ))}
          </div>
          <div className="glass-card" style={{ padding: "25px" }}>
            <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "15px" }}>By Grade Level</h3>
            {(districtData.by_grade_level || []).map((g, i) => (
              <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "8px 0", borderBottom: "1px solid var(--glass-border)" }}>
                <span>Grade {g.name}</span>
                <span style={{ fontWeight: 600 }}>{g.average}% avg ({g.count} assignments)</span>
              </div>
            ))}
          </div>
        </div>
      </>
    )}

    {/* School View */}
    {districtView === "school" && (
      <div className="glass-card" style={{ padding: "25px" }}>
        <h3 style={{ marginBottom: "15px" }}>Select a School</h3>
        <select
          className="input"
          value={selectedSchool || ""}
          onChange={(e) => setSelectedSchool(e.target.value)}
          style={{ marginBottom: "20px" }}
        >
          <option value="">Choose school...</option>
          {schools.map(s => (
            <option key={s.school_id} value={s.school_id}>{s.school_name}</option>
          ))}
        </select>
        {/* School-specific analytics would render here */}
      </div>
    )}

    {/* No Data State */}
    {!districtData && (
      <div className="glass-card" style={{ padding: "60px", textAlign: "center" }}>
        <Icon name="Building2" size={64} style={{ opacity: 0.3 }} />
        <h2 style={{ marginTop: "20px" }}>No District Data Yet</h2>
        <p style={{ color: "var(--text-secondary)", marginTop: "10px" }}>
          Configure your district and sync teacher data to see analytics.
        </p>
      </div>
    )}
  </div>
)}
```

---

## File 5: Add API functions to `frontend/src/services/api.js`

```javascript
// ============ District Analytics ============

export async function getDistrictConfig() {
  return fetchApi('/api/district/config')
}

export async function updateDistrictConfig(config) {
  return fetchApi('/api/district/config', {
    method: 'POST',
    body: JSON.stringify(config),
  })
}

export async function listSchools() {
  return fetchApi('/api/district/schools')
}

export async function createSchool(schoolId, schoolName, metadata = {}) {
  return fetchApi('/api/district/schools', {
    method: 'POST',
    body: JSON.stringify({ school_id: schoolId, school_name: schoolName, metadata }),
  })
}

export async function listDistrictTeachers(schoolId = null) {
  const url = schoolId ? `/api/district/teachers?school_id=${schoolId}` : '/api/district/teachers'
  return fetchApi(url)
}

export async function registerTeacher(teacherId, teacherName, schoolId, metadata = {}) {
  return fetchApi('/api/district/teachers', {
    method: 'POST',
    body: JSON.stringify({ teacher_id: teacherId, teacher_name: teacherName, school_id: schoolId, metadata }),
  })
}

export async function syncToDistrict(teacherId, outputFolder) {
  return fetchApi('/api/district/sync', {
    method: 'POST',
    body: JSON.stringify({ teacher_id: teacherId, output_folder: outputFolder }),
  })
}

export async function getDistrictAnalytics() {
  return fetchApi('/api/district/analytics')
}

export async function getSchoolAnalytics(schoolId) {
  return fetchApi(`/api/district/analytics/school/${schoolId}`)
}

export async function getTeacherDistrictAnalytics(teacherId) {
  return fetchApi(`/api/district/analytics/teacher/${teacherId}`)
}

// Add to default export
export default {
  // ... existing exports ...
  getDistrictConfig,
  updateDistrictConfig,
  listSchools,
  createSchool,
  listDistrictTeachers,
  registerTeacher,
  syncToDistrict,
  getDistrictAnalytics,
  getSchoolAnalytics,
  getTeacherDistrictAnalytics,
}
```

---

## Implementation Summary

| File | Action | Description |
|------|--------|-------------|
| `backend/district_analytics.py` | CREATE | Core district analytics logic |
| `backend/routes/district_routes.py` | CREATE | API endpoints for district features |
| `backend/routes/__init__.py` | MODIFY | Register district routes |
| `frontend/src/App.jsx` | MODIFY | Add District tab and UI |
| `frontend/src/services/api.js` | MODIFY | Add district API functions |

## Data Flow

```
1. Teacher grades assignments normally
2. Teacher clicks "Sync to District" (or auto-sync)
3. Master CSV data → anonymized → district store
4. Aggregation runs → school stats → district stats
5. Admins view dashboards at school/district level
```

## Privacy Features

- Student names anonymized by default (hashed IDs only)
- Data stays local (no cloud upload)
- Configurable per-district settings
- Audit trail for data access

## Future Enhancements

- [ ] Role-based access control (Teacher/Principal/Admin)
- [ ] Real-time sync with websockets
- [ ] PDF report generation
- [ ] Email digest for administrators
- [ ] Benchmark comparisons (state/national)
- [ ] SSO integration (Clever, ClassLink)
