# Parallel Multi-Student Grading Implementation Plan

## Overview
Implement parallel grading to process 3-4 students simultaneously, reducing batch grading time by 60-75%.

## Current Flow (Sequential)
```
Student 1 (5s) → Student 2 (5s) → Student 3 (5s) → Student 4 (5s)
Total: 20 seconds
```

## New Flow (Parallel)
```
Student 1 (5s) ─┐
Student 2 (5s) ─┼→ All complete in ~5-6s
Student 3 (5s) ─┤
Student 4 (5s) ─┘
Total: ~6 seconds (with overhead)
```

## Configuration
- **PARALLEL_WORKERS**: 3 (conservative to avoid API rate limits)
- OpenAI rate limit: ~60 requests/minute = 1 request/second
- With parallel detection, each student = 2 API calls
- 3 workers × 2 calls = 6 calls in flight max (safe margin)

---

## Code Changes

### 1. Add Import (backend/app.py, line 14)

**Already done** - `concurrent.futures` was added.

---

### 2. Add Helper Function (backend/app.py, after line 641)

Insert this function after `all_grades = []`:

```python
        # ═══════════════════════════════════════════════════════════
        # PARALLEL GRADING HELPER FUNCTION
        # ═══════════════════════════════════════════════════════════
        def grade_single_file(filepath, file_index, total_files):
            """Grade a single file - designed for parallel execution."""
            try:
                parsed = parse_filename(filepath.name)
                student_name = f"{parsed['first_name']} {parsed['last_name']}"
                lookup_key = parsed['lookup_key']

                # Lookup student in roster
                if lookup_key in roster:
                    student_info = roster[lookup_key].copy()
                else:
                    # Try fuzzy matching for last name initials
                    student_info = None
                    first_name_lower = parsed['first_name'].lower()
                    last_name_lower = parsed['last_name'].lower()

                    if len(last_name_lower) <= 2:
                        for roster_key, roster_data in roster.items():
                            if isinstance(roster_data, dict):
                                roster_first = roster_data.get('first_name', '').lower()
                                roster_last = roster_data.get('last_name', '').lower()
                                if roster_first == first_name_lower and roster_last.startswith(last_name_lower):
                                    student_info = roster_data.copy()
                                    student_name = f"{roster_data.get('first_name', parsed['first_name'])} {roster_data.get('last_name', parsed['last_name'])}"
                                    break

                    if not student_info:
                        student_info = {"student_id": "UNKNOWN", "student_name": student_name,
                                       "first_name": parsed['first_name'], "last_name": parsed['last_name'], "email": ""}

                # Match assignment config
                matched_config = find_matching_config(filepath.name)
                if not matched_config:
                    try:
                        temp_file_data = read_assignment_file(filepath)
                        if temp_file_data and temp_file_data.get("type") == "text":
                            file_text = temp_file_data.get("content", "")
                            if file_text:
                                matched_config = find_matching_config(filepath.name, file_text)
                    except:
                        pass

                if matched_config:
                    file_markers = matched_config.get('customMarkers', [])
                    file_notes = matched_config.get('gradingNotes', '')
                    file_sections = matched_config.get('responseSections', [])
                    matched_title = matched_config.get('title', 'Unknown')
                    is_completion_only = matched_config.get('completionOnly', False)
                    imported_doc = matched_config.get('importedDoc', {})
                    assignment_template = imported_doc.get('text', '')
                else:
                    file_markers = fallback_markers
                    file_notes = fallback_notes
                    file_sections = fallback_sections
                    matched_title = ASSIGNMENT_NAME
                    is_completion_only = False
                    assignment_template = ''

                # Get student's period
                student_period = student_period_map.get(student_info['student_name'].lower(), class_period)

                # Handle completion-only assignments
                if is_completion_only:
                    return {
                        "success": True,
                        "student_info": student_info,
                        "filepath": filepath,
                        "matched_title": matched_title,
                        "student_period": student_period,
                        "is_completion_only": True,
                        "grade_result": {
                            "score": 100,
                            "letter_grade": "SUBMITTED",
                            "feedback": "Completion-only assignment - submitted successfully.",
                            "breakdown": {},
                            "student_responses": [],
                            "unanswered_questions": []
                        },
                        "file_data": {"type": "text", "content": ""},
                        "marker_status": "completion_only",
                        "baseline_deviation": {"flag": "normal", "reasons": [], "details": {}},
                        "log_messages": [f"  Completion only - recorded submission"]
                    }

                # Build AI notes
                file_ai_notes = global_ai_notes
                if file_notes:
                    file_ai_notes += f"\n\nASSIGNMENT-SPECIFIC INSTRUCTIONS:\n{file_notes}"

                # Add accommodation prompt if student has IEP/504
                if student_info.get('student_id') and student_info['student_id'] != "UNKNOWN":
                    accommodation_prompt = build_accommodation_prompt(student_info['student_id'])
                    if accommodation_prompt:
                        file_ai_notes += f"\n{accommodation_prompt}"

                # Add student history context
                if student_info.get('student_id') and student_info['student_id'] != "UNKNOWN":
                    history_context = build_history_context(student_info['student_id'])
                    if history_context:
                        file_ai_notes += f"\n{history_context}"

                # Read file
                file_data = read_assignment_file(filepath)
                if not file_data:
                    return {"success": False, "error": "Could not read file", "filepath": filepath}

                # Prepare grade data
                if file_data["type"] == "text":
                    grade_data = {"type": "text", "content": file_data["content"]}
                else:
                    grade_data = file_data

                # Grade with parallel detection
                grade_result = grade_with_parallel_detection(
                    student_info['student_name'], grade_data, file_ai_notes,
                    grade_level, subject, ai_model, student_info.get('student_id'), assignment_template
                )

                # Check for errors
                if grade_result.get('letter_grade') == 'ERROR':
                    return {"success": False, "error": grade_result.get('feedback', 'API error'),
                            "filepath": filepath, "is_api_error": True}

                # Determine marker status
                has_config = matched_config is not None
                has_custom_markers = len(file_markers) > 0
                has_grading_notes = bool(file_notes.strip()) if file_notes else False
                has_response_sections = len(file_sections) > 0
                is_verified = has_config or has_custom_markers or has_grading_notes or has_response_sections
                marker_status = "verified" if is_verified else "unverified"

                # Check baseline deviation
                baseline_deviation = {"flag": "normal", "reasons": [], "details": {}}
                if student_info.get('student_id') and student_info['student_id'] != "UNKNOWN":
                    try:
                        baseline_deviation = detect_baseline_deviation(student_info['student_id'], grade_result)
                    except:
                        pass

                # Save to student history
                if student_info.get('student_id') and student_info['student_id'] != "UNKNOWN":
                    try:
                        grade_record = {**student_info, **grade_result, "filename": filepath.name,
                                       "assignment": matched_title, "period": student_period}
                        add_assignment_to_history(student_info['student_id'], grade_record)
                    except:
                        pass

                log_messages = [f"  Score: {grade_result['score']} ({grade_result['letter_grade']})"]
                if marker_status == "unverified":
                    log_messages.append(f"  ⚠️  UNVERIFIED: No assignment config")
                if baseline_deviation.get('flag') != 'normal':
                    log_messages.append(f"  ⚠️  Baseline deviation: {baseline_deviation.get('flag')}")

                return {
                    "success": True,
                    "student_info": student_info,
                    "filepath": filepath,
                    "matched_title": matched_title,
                    "student_period": student_period,
                    "is_completion_only": False,
                    "grade_result": grade_result,
                    "file_data": file_data,
                    "marker_status": marker_status,
                    "baseline_deviation": baseline_deviation,
                    "log_messages": log_messages
                }

            except Exception as e:
                return {"success": False, "error": str(e), "filepath": filepath}
```

---

### 3. Replace Sequential Loop with Parallel Execution (backend/app.py)

**REPLACE** the entire `for i, filepath in enumerate(new_files, 1):` loop (lines 643-942) with:

```python
        # ═══════════════════════════════════════════════════════════
        # PARALLEL GRADING EXECUTION
        # ═══════════════════════════════════════════════════════════
        PARALLEL_WORKERS = 3  # Conservative: 3 students at once (6 API calls with detection)

        grading_state["log"].append(f"⚡ Parallel grading enabled ({PARALLEL_WORKERS} workers)")
        grading_state["log"].append("")

        completed = 0
        api_error_occurred = False

        with concurrent.futures.ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
            # Submit all files as futures
            future_to_file = {}
            for i, filepath in enumerate(new_files):
                if grading_state.get("stop_requested", False):
                    break
                future = executor.submit(grade_single_file, filepath, i + 1, len(new_files))
                future_to_file[future] = (filepath, i + 1)

            # Process completed futures as they finish
            for future in concurrent.futures.as_completed(future_to_file):
                if grading_state.get("stop_requested", False):
                    # Cancel remaining futures
                    for f in future_to_file:
                        f.cancel()
                    grading_state["log"].append("")
                    grading_state["log"].append(f"Stopped - {completed}/{len(new_files)} files completed")
                    break

                filepath, file_num = future_to_file[future]

                try:
                    result = future.result()
                except Exception as e:
                    grading_state["log"].append(f"[{file_num}/{len(new_files)}] {filepath.name}")
                    grading_state["log"].append(f"  ❌ Error: {str(e)}")
                    continue

                # Update progress
                completed += 1
                grading_state["progress"] = completed
                grading_state["current_file"] = filepath.name

                # Handle failed grading
                if not result.get("success"):
                    grading_state["log"].append(f"[{file_num}/{len(new_files)}] {filepath.name}")
                    grading_state["log"].append(f"  ❌ {result.get('error', 'Unknown error')}")

                    # Stop on API errors
                    if result.get("is_api_error"):
                        api_error_occurred = True
                        grading_state["log"].append("")
                        grading_state["log"].append("=" * 50)
                        grading_state["log"].append("⚠️  GRADING STOPPED - API ERROR")
                        grading_state["log"].append("=" * 50)
                        grading_state["error"] = f"API Error: {result.get('error')}"
                        # Cancel remaining futures
                        for f in future_to_file:
                            f.cancel()
                        break
                    continue

                # Log success
                student_info = result["student_info"]
                grade_result = result["grade_result"]

                grading_state["log"].append(f"[{file_num}/{len(new_files)}] {student_info['student_name']}")
                for msg in result.get("log_messages", []):
                    grading_state["log"].append(msg)

                # Build grade record
                file_data = result.get("file_data", {})
                if file_data.get("type") == "text":
                    student_content = file_data.get("content", "")[:5000]
                    full_content = file_data.get("content", "")[:10000]
                else:
                    student_content = "[Image file]"
                    full_content = "[Image file]"

                grade_record = {
                    **student_info,
                    **grade_result,
                    "filename": filepath.name,
                    "assignment": result["matched_title"],
                    "period": result["student_period"],
                    "grading_period": grading_period,
                    "has_markers": False
                }
                all_grades.append(grade_record)

                # Add to results
                grading_state["results"].append({
                    "student_name": student_info['student_name'],
                    "student_id": student_info.get('student_id', ''),
                    "student_email": student_info.get('email', ''),
                    "filename": filepath.name,
                    "filepath": str(filepath),
                    "assignment": result["matched_title"],
                    "period": result["student_period"],
                    "score": grade_result.get('score', 0),
                    "letter_grade": grade_result.get('letter_grade', 'N/A'),
                    "feedback": grade_result.get('feedback', ''),
                    "student_content": student_content,
                    "full_content": full_content,
                    "breakdown": grade_result.get('breakdown', {}),
                    "student_responses": grade_result.get('student_responses', []),
                    "unanswered_questions": grade_result.get('unanswered_questions', []),
                    "ai_detection": grade_result.get('ai_detection', {}),
                    "plagiarism_detection": grade_result.get('plagiarism_detection', {}),
                    "baseline_deviation": result.get("baseline_deviation", {}),
                    "skills_demonstrated": grade_result.get('skills_demonstrated', {}),
                    "marker_status": result.get("marker_status", "unverified"),
                    "graded_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })

        # Handle stop/error states
        if api_error_occurred:
            grading_state["complete"] = True
            grading_state["is_running"] = False
            if grading_state["results"]:
                save_results(grading_state["results"])
            return
```

---

### 4. Keep Export Logic (after the parallel block)

The existing export logic (lines 944-988) stays the same - it runs after the parallel grading completes.

---

## Summary of Changes

| File | Line | Change |
|------|------|--------|
| backend/app.py | 14 | Add `concurrent.futures` import ✅ (done) |
| backend/app.py | ~641 | Add `grade_single_file()` helper function |
| backend/app.py | ~643-942 | Replace sequential loop with parallel executor |

## Expected Performance

| Batch Size | Sequential | Parallel (3 workers) | Speedup |
|------------|------------|---------------------|---------|
| 10 files | ~50s | ~20s | 2.5x |
| 30 files | ~150s | ~55s | 2.7x |
| 100 files | ~500s | ~180s | 2.8x |

## Risk Mitigation

1. **API Rate Limits**: Using 3 workers (conservative) to stay under OpenAI's 60 req/min limit
2. **Error Handling**: API errors stop all grading and save progress
3. **Stop Button**: Works correctly - cancels pending futures
4. **Thread Safety**: Each file graded independently, results collected at end
5. **Progress Tracking**: Updates as each file completes (not in order)

## Testing Checklist

- [ ] Grade 5 files - verify parallel execution (check logs for interleaved output)
- [ ] Test stop button mid-grading
- [ ] Test with API error (disconnect internet mid-grade)
- [ ] Verify all results saved correctly
- [ ] Check detection flags are preserved
- [ ] Verify progress bar updates
