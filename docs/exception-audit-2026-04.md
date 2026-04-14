# Exception Handler Audit — Graider Backend

> Generated: 2026-04-13
> Total handlers: 790
> Files scanned: 73

## Category Legend

- **INTENTIONAL** — broad catch is correct by design (SIS API flakiness, graceful degradation)
- **LEGACY** — should be replaced with typed exception or removed (Phase 2 fixes)
- **NEEDS_ALERT** — failure should be observable via BetterStack (currently silent)
- **UNCATEGORIZED** — not yet reviewed

## Handlers

| File | Line | Exception Type | Handler Behavior | Parent Function | Category |
|------|------|---------------|-----------------|-----------------|----------|
| `backend/accommodations.py` | 25 | `ImportError` | other | `<module>` | INTENTIONAL |
| `backend/accommodations.py` | 54 | `Exception` | print | `audit_log_accommodation` | NEEDS_ALERT |
| `backend/accommodations.py` | 303 | `Exception` | print + return | `save_preset` | NEEDS_ALERT |
| `backend/accommodations.py` | 333 | `Exception` | print + return | `delete_preset` | NEEDS_ALERT |
| `backend/accommodations.py` | 382 | `Exception` | print + return | `save_student_accommodations` | NEEDS_ALERT |
| `backend/accommodations.py` | 460 | `Exception` | pass | `_get_ell_language` | LEGACY |
| `backend/accommodations.py` | 694 | `Exception` | print + return | `clear_all_accommodations` | NEEDS_ALERT |
| `backend/accommodations.py` | 28 | `ImportError` | other | `<module>` | INTENTIONAL |
| `backend/accommodations.py` | 268 | `Exception` | print | `load_presets` | NEEDS_ALERT |
| `backend/accommodations.py` | 363 | `Exception` | print | `load_student_accommodations` | NEEDS_ALERT |
| `backend/api_keys.py` | 43 | `(ImportError, RuntimeError)` | return | `_get_district_id` | UNCATEGORIZED |
| `backend/api_keys.py` | 91 | `Exception` | pass | `get_api_key` | UNCATEGORIZED |
| `backend/api_keys.py` | 124 | `Exception` | other | `resolve_keys_for_teacher` | UNCATEGORIZED |
| `backend/app.py` | 38 | `ImportError` | pass + return | `<module>` | INTENTIONAL |
| `backend/app.py` | 59 | `ImportError` | return | `<module>` | INTENTIONAL |
| `backend/app.py` | 74 | `ImportError` | other | `<module>` | INTENTIONAL |
| `backend/app.py` | 169 | `Exception` | print | `<module>` | INTENTIONAL |
| `backend/app.py` | 175 | `Exception` | print | `<module>` | NEEDS_ALERT |
| `backend/app.py` | 206 | `Exception` | pass | `<module>` | INTENTIONAL |
| `backend/app.py` | 246 | `Exception` | print + return | `get_audit_logs` | LEGACY |
| `backend/app.py` | 2032 | `Exception` | append | `_run_grading_thread_inner` | NEEDS_ALERT |
| `backend/app.py` | 2237 | `Exception` | log.exception + return | `grade_individual` | INTENTIONAL |
| `backend/app.py` | 2288 | `Exception` | print | `_remove_from_master_csv` | LEGACY |
| `backend/app.py` | 2342 | `Exception` | print | `_sync_approval_to_master_csv` | LEGACY |
| `backend/app.py` | 2522 | `Exception` | log.exception + return | `delete_all_student_data` | INTENTIONAL |
| `backend/app.py` | 2865 | `Exception` | print | `export_individual_student_data` | LEGACY |
| `backend/app.py` | 2912 | `(json.JSONDecodeError, UnicodeDecodeError)` | log.exception + return | `import_individual_student_data` | INTENTIONAL |
| `backend/app.py` | 3167 | `Exception` | log.exception + return | `retranslate_feedback` | INTENTIONAL |
| `backend/app.py` | 3255 | `json.JSONDecodeError` | log.exception + return | `extract_student_from_image` | INTENTIONAL |
| `backend/app.py` | 3258 | `Exception` | log.exception + return | `extract_student_from_image` | INTENTIONAL |
| `backend/app.py` | 3333 | `Exception` | log.exception + return | `add_student_to_roster` | INTENTIONAL |
| `backend/app.py` | 3363 | `Exception` | log.exception + return | `list_periods` | INTENTIONAL |
| `backend/app.py` | 3386 | `Exception` | log.exception + return | `get_user_manual` | INTENTIONAL |
| `backend/app.py` | 3430 | `Exception` | other | `healthz` | INTENTIONAL |
| `backend/app.py` | 3443 | `Exception` | other | `healthz` | INTENTIONAL |
| `backend/app.py` | 41 | `ImportError` | pass + return | `<module>` | INTENTIONAL |
| `backend/app.py` | 62 | `ImportError` | return | `<module>` | INTENTIONAL |
| `backend/app.py` | 77 | `ImportError` | other | `<module>` | INTENTIONAL |
| `backend/app.py` | 400 | `Exception` | pass | `load_saved_results` | LEGACY |
| `backend/app.py` | 412 | `Exception` | print | `save_results` | LEGACY |
| `backend/app.py` | 502 | `(ValueError, TypeError)` | pass | `_check_batch_calibration` | INTENTIONAL |
| `backend/app.py` | 865 | `(ValueError, TypeError)` | return | `calculate_late_penalty` | INTENTIONAL |
| `backend/app.py` | 871 | `(OSError, TypeError)` | return | `calculate_late_penalty` | INTENTIONAL |
| `backend/app.py` | 2106 | `Exception` | pass | `grade_individual` | INTENTIONAL |
| `backend/app.py` | 2114 | `Exception` | pass | `grade_individual` | INTENTIONAL |
| `backend/app.py` | 2740 | `Exception` | pass | `export_individual_student_data` | LEGACY |
| `backend/app.py` | 2752 | `Exception` | pass | `export_individual_student_data` | LEGACY |
| `backend/app.py` | 2764 | `Exception` | pass | `export_individual_student_data` | LEGACY |
| `backend/app.py` | 2873 | `Exception` | pass | `export_individual_student_data` | INTENTIONAL |
| `backend/app.py` | 3090 | `Exception` | print | `import_individual_student_data` | LEGACY |
| `backend/app.py` | 3191 | `ImportError` | return | `extract_student_from_image` | INTENTIONAL |
| `backend/app.py` | 204 | `Exception` | pass | `<module>` | INTENTIONAL |
| `backend/app.py` | 318 | `Exception` | print | `load_support_documents_for_grading` | INTENTIONAL |
| `backend/app.py` | 1044 | `Exception` | pass | `_run_grading_thread_inner` | INTENTIONAL |
| `backend/app.py` | 1726 | `Exception` | log.error + return | `grade_single_file` | INTENTIONAL |
| `backend/app.py` | 2005 | `Exception` | append | `_run_grading_thread_inner` | LEGACY |
| `backend/app.py` | 2229 | `Exception` | print | `grade_individual` | NEEDS_ALERT |
| `backend/app.py` | 2688 | `Exception` | other | `export_individual_student_data` | INTENTIONAL |
| `backend/app.py` | 3040 | `Exception` | pass | `import_individual_student_data` | LEGACY |
| `backend/app.py` | 3056 | `Exception` | pass | `import_individual_student_data` | LEGACY |
| `backend/app.py` | 655 | `Exception` | pass | `_run_grading_thread_inner` | INTENTIONAL |
| `backend/app.py` | 1347 | `Exception` | print | `grade_single_file` | INTENTIONAL |
| `backend/app.py` | 2667 | `Exception` | pass | `export_individual_student_data` | INTENTIONAL |
| `backend/app.py` | 1016 | `Exception` | append | `_run_grading_thread_inner` | INTENTIONAL |
| `backend/app.py` | 1192 | `Exception` | pass | `grade_single_file` | INTENTIONAL |
| `backend/app.py` | 1681 | `Exception` | pass | `grade_single_file` | INTENTIONAL |
| `backend/app.py` | 1690 | `Exception` | pass | `grade_single_file` | NEEDS_ALERT |
| `backend/app.py` | 1773 | `Exception` | append | `_run_grading_thread_inner` | INTENTIONAL |
| `backend/app.py` | 3356 | `Exception` | pass | `list_periods` | INTENTIONAL |
| `backend/app.py` | 300 | `Exception` | other | `load_support_documents_for_grading` | INTENTIONAL |
| `backend/app.py` | 975 | `Exception` | pass | `_run_grading_thread_inner` | INTENTIONAL |
| `backend/app.py` | 1528 | `Exception` | pass | `grade_single_file` | INTENTIONAL |
| `backend/app.py` | 308 | `Exception` | other | `load_support_documents_for_grading` | INTENTIONAL |
| `backend/auth.py` | 30 | `Exception` | return | `load_clever_links` | NEEDS_ALERT |
| `backend/auth.py` | 45 | `Exception` | other | `save_clever_link` | NEEDS_ALERT |
| `backend/auth.py` | 146 | `jwt.ExpiredSignatureError` | return | `validate_token` | INTENTIONAL |
| `backend/auth.py` | 148 | `jwt.InvalidTokenError` | return | `validate_token` | INTENTIONAL |
| `backend/auth.py` | 132 | `jwt.ExpiredSignatureError` | return | `validate_token` | INTENTIONAL |
| `backend/auth.py` | 134 | `jwt.InvalidTokenError` | log.warning | `validate_token` | INTENTIONAL |
| `backend/auth.py` | 36 | `(FileNotFoundError, json.JSONDecodeError)` | return | `load_clever_links` | INTENTIONAL |
| `backend/auth.py` | 248 | `Exception` | log.warning | `check_auth` | LEGACY |
| `backend/clever.py` | 46 | `Exception` | pass | `get_clever_config` | LEGACY |
| `backend/clever.py` | 109 | `httpx.HTTPError` | log.error + return | `exchange_code_for_token` | INTENTIONAL |
| `backend/clever.py` | 152 | `httpx.HTTPError` | log.error + return | `get_clever_user` | INTENTIONAL |
| `backend/clever.py` | 184 | `httpx.HTTPError` | log.warning + raise | `_clever_get_with_retry` | INTENTIONAL |
| `backend/clever.py` | 545 | `(json.JSONDecodeError, ValueError)` | other | `persist_parent_contacts` | INTENTIONAL |
| `backend/clever.py` | 231 | `httpx.HTTPError` | log.error | `sync_roster` | NEEDS_ALERT |
| `backend/clever.py` | 245 | `httpx.HTTPError` | log.warning | `sync_roster` | NEEDS_ALERT |
| `backend/clever.py` | 361 | `(json.JSONDecodeError, ValueError)` | other | `persist_roster_as_csv` | INTENTIONAL |
| `backend/clever.py` | 404 | `(json.JSONDecodeError, ValueError)` | other | `persist_roster_as_csv` | INTENTIONAL |
| `backend/clever.py` | 217 | `httpx.HTTPError` | log.error | `sync_roster` | NEEDS_ALERT |
| `backend/lti.py` | 236 | `jwt.ExpiredSignatureError` | raise | `validate_launch_jwt` | INTENTIONAL |
| `backend/lti.py` | 238 | `jwt.InvalidAudienceError` | raise | `validate_launch_jwt` | INTENTIONAL |
| `backend/lti.py` | 240 | `jwt.InvalidIssuerError` | raise | `validate_launch_jwt` | INTENTIONAL |
| `backend/lti.py` | 242 | `Exception` | raise | `validate_launch_jwt` | INTENTIONAL |
| `backend/lti.py` | 442 | `Exception` | log.error + return | `post_score` | INTENTIONAL |
| `backend/observability/sentry.py` | 60 | `Exception` | pass | `_is_client_error` | INTENTIONAL |
| `backend/observability/sentry.py` | 83 | `ImportError` | return | `_resolve_user_id` | INTENTIONAL |
| `backend/observability/sentry.py` | 89 | `RuntimeError` | return | `_resolve_user_id` | INTENTIONAL |
| `backend/observability/sentry.py` | 94 | `RuntimeError` | return | `_resolve_user_id` | INTENTIONAL |
| `backend/observability/sentry.py` | 150 | `Exception` | pass | `_scrub_frame_locals` | INTENTIONAL |
| `backend/observability/sentry.py` | 288 | `ImportError` | log.warning + return | `init_sentry` | INTENTIONAL |
| `backend/observability/sentry.py` | 298 | `ImportError` | other | `init_sentry` | INTENTIONAL |
| `backend/observability/sentry.py` | 318 | `(BadDsn, ValueError)` | log.warning + return | `init_sentry` | INTENTIONAL |
| `backend/observability/sentry.py` | 221 | `Exception` | pass + raise | `wrapper` | INTENTIONAL |
| `backend/observability/sentry.py` | 230 | `Exception` | pass | `wrapper` | INTENTIONAL |
| `backend/oneroster.py` | 446 | `Exception` | log.debug | `get_oneroster_config` | UNCATEGORIZED |
| `backend/oneroster.py` | 423 | `Exception` | log.debug | `get_oneroster_config` | UNCATEGORIZED |
| `backend/oneroster.py` | 203 | `Exception` | log.info | `fetch_roster` | UNCATEGORIZED |
| `backend/oneroster.py` | 435 | `Exception` | pass | `get_oneroster_config` | UNCATEGORIZED |
| `backend/retry.py` | 91 | `(ValueError, TypeError)` | pass | `get_retry_delay` | INTENTIONAL |
| `backend/retry.py` | 147 | `Exception` | log.error + log.warning + raise | `with_retry` | INTENTIONAL |
| `backend/roster_sync.py` | 18 | `Exception` | return | `_get_supabase` | INTENTIONAL |
| `backend/roster_sync.py` | 76 | `Exception` | log.warning + return | `sync_roster_to_db` | NEEDS_ALERT |
| `backend/roster_sync.py` | 135 | `Exception` | log.warning + return | `sync_roster_to_db` | NEEDS_ALERT |
| `backend/roster_sync.py` | 217 | `Exception` | log.error + return | `deactivate_missing_students` | INTENTIONAL |
| `backend/roster_sync.py` | 168 | `Exception` | log.warning | `sync_roster_to_db` | NEEDS_ALERT |
| `backend/roster_sync.py` | 270 | `Exception` | log.error | `delete_roster_data` | NEEDS_ALERT |
| `backend/roster_sync.py` | 288 | `OSError` | log.warning | `delete_roster_data` | LEGACY |
| `backend/routes/admin_routes.py` | 109 | `Exception` | log.warning | `_discover_teachers` | LEGACY |
| `backend/routes/admin_routes.py` | 476 | `Exception` | log.warning | `admin_teacher_summary` | LEGACY |
| `backend/routes/admin_routes.py` | 68 | `(ValueError, TypeError)` | pass | `admin_claim` | INTENTIONAL |
| `backend/routes/admin_routes.py` | 127 | `Exception` | log.warning | `_discover_teachers` | LEGACY |
| `backend/routes/admin_routes.py` | 310 | `Exception` | log.warning | `_enrich_teachers` | LEGACY |
| `backend/routes/admin_routes.py` | 390 | `Exception` | log.warning | `admin_overview` | LEGACY |
| `backend/routes/admin_routes.py` | 510 | `Exception` | log.warning | `admin_activity` | LEGACY |
| `backend/routes/admin_routes.py` | 461 | `(ValueError, TypeError)` | pass | `admin_teacher_summary` | INTENTIONAL |
| `backend/routes/admin_routes.py` | 360 | `(ValueError, TypeError)` | pass | `admin_overview` | INTENTIONAL |
| `backend/routes/admin_routes.py` | 387 | `(ValueError, TypeError)` | pass | `admin_overview` | INTENTIONAL |
| `backend/routes/analytics_routes.py` | 124 | `Exception` | log.warning | `_fetch_assessment_analytics` | LEGACY |
| `backend/routes/analytics_routes.py` | 135 | `ImportError` | other | `_analytics_from_results` | INTENTIONAL |
| `backend/routes/analytics_routes.py` | 390 | `ImportError` | other | `get_analytics` | INTENTIONAL |
| `backend/routes/analytics_routes.py` | 498 | `Exception` | log.exception + return | `get_analytics` | INTENTIONAL |
| `backend/routes/analytics_routes.py` | 695 | `Exception` | pass | `export_district_report` | INTENTIONAL |
| `backend/routes/analytics_routes.py` | 737 | `Exception` | pass | `export_district_report` | LEGACY |
| `backend/routes/analytics_routes.py` | 862 | `ImportError` | other | `cleanup_master_csv` | INTENTIONAL |
| `backend/routes/analytics_routes.py` | 891 | `Exception` | log.exception + return | `cleanup_master_csv` | INTENTIONAL |
| `backend/routes/analytics_routes.py` | 985 | `Exception` | log.exception + return | `cleanup_master_csv` | INTENTIONAL |
| `backend/routes/analytics_routes.py` | 33 | `Exception` | pass | `_find_master_grades` | INTENTIONAL |
| `backend/routes/analytics_routes.py` | 60 | `ImportError` | other | `_fetch_assessment_analytics` | INTENTIONAL |
| `backend/routes/analytics_routes.py` | 354 | `Exception` | pass | `_load_valid_assignment_names` | LEGACY |
| `backend/routes/analytics_routes.py` | 762 | `Exception` | log.exception + return | `export_district_report` | INTENTIONAL |
| `backend/routes/analytics_routes.py` | 882 | `Exception` | pass | `cleanup_master_csv` | NEEDS_ALERT |
| `backend/routes/analytics_routes.py` | 393 | `ImportError` | other | `get_analytics` | INTENTIONAL |
| `backend/routes/analytics_routes.py` | 708 | `Exception` | pass | `export_district_report` | INTENTIONAL |
| `backend/routes/analytics_routes.py` | 867 | `ImportError` | other | `cleanup_master_csv` | INTENTIONAL |
| `backend/routes/analytics_routes.py` | 925 | `ValueError` | return | `_is_corrupted_row` | INTENTIONAL |
| `backend/routes/assessment_results_routes.py` | 170 | `Exception` | log.warning | `get_assessment_results` | NEEDS_ALERT |
| `backend/routes/assessment_results_routes.py` | 233 | `Exception` | log.warning | `get_assessment_results` | NEEDS_ALERT |
| `backend/routes/assessment_results_routes.py` | 308 | `Exception` | log.warning | `get_assessment_results` | NEEDS_ALERT |
| `backend/routes/assessment_results_routes.py` | 256 | `Exception` | pass | `get_assessment_results` | INTENTIONAL |
| `backend/routes/assessment_results_routes.py` | 263 | `Exception` | pass | `get_assessment_results` | INTENTIONAL |
| `backend/routes/assignment_player_routes.py` | 33 | `ImportError` | other | `<module>` | INTENTIONAL |
| `backend/routes/assignment_player_routes.py` | 40 | `ImportError` | return | `<module>` | INTENTIONAL |
| `backend/routes/assignment_player_routes.py` | 94 | `Exception` | pass | `_load_teacher_context` | INTENTIONAL |
| `backend/routes/assignment_player_routes.py` | 117 | `Exception` | log.exception + return | `get_assignment` | INTENTIONAL |
| `backend/routes/assignment_player_routes.py` | 154 | `Exception` | log.exception + return | `create_assignment` | INTENTIONAL |
| `backend/routes/assignment_player_routes.py` | 198 | `Exception` | log.exception + return | `submit_assignment` | INTENTIONAL |
| `backend/routes/assignment_player_routes.py` | 226 | `Exception` | log.exception + return | `get_submissions` | INTENTIONAL |
| `backend/routes/assignment_player_routes.py` | 371 | `Exception` | print + return | `_vision_ocr_fallback` | INTENTIONAL |
| `backend/routes/assignment_player_routes.py` | 574 | `Exception` | print + return | `_grade_with_ai` | INTENTIONAL |
| `backend/routes/assignment_player_routes.py` | 695 | `Exception` | return | `grade_question` | INTENTIONAL |
| `backend/routes/assignment_player_routes.py` | 958 | `(ValueError, TypeError)` | return | `grade_geometry` | INTENTIONAL |
| `backend/routes/assignment_player_routes.py` | 1027 | `Exception` | return | `grade_math_equation` | LEGACY |
| `backend/routes/assignment_player_routes.py` | 1056 | `Exception` | return | `grade_coordinates` | INTENTIONAL |
| `backend/routes/assignment_player_routes.py` | 1104 | `Exception` | return | `grade_data_table` | INTENTIONAL |
| `backend/routes/assignment_player_routes.py` | 1190 | `ImportError` | return | `grade_function_graph` | INTENTIONAL |
| `backend/routes/assignment_player_routes.py` | 1451 | `(ValueError, ZeroDivisionError)` | return | `normalize_fraction` | INTENTIONAL |
| `backend/routes/assignment_player_routes.py` | 994 | `Exception` | pass | `grade_box_plot` | INTENTIONAL |
| `backend/routes/assignment_player_routes.py` | 1523 | `ValueError` | return | `grade_tape_diagram` | INTENTIONAL |
| `backend/routes/assignment_player_routes.py` | 1583 | `(ValueError, TypeError)` | return | `grade_protractor` | INTENTIONAL |
| `backend/routes/assignment_player_routes.py` | 1605 | `ValueError` | pass | `grade_protractor` | INTENTIONAL |
| `backend/routes/assignment_player_routes.py` | 933 | `(ValueError, TypeError)` | return | `grade_geometry` | INTENTIONAL |
| `backend/routes/assignment_player_routes.py` | 1163 | `Exception` | other | `grade_function_graph` | INTENTIONAL |
| `backend/routes/assignment_player_routes.py` | 1503 | `ValueError` | other | `grade_tape_diagram` | INTENTIONAL |
| `backend/routes/assignment_player_routes.py` | 1544 | `ValueError` | other | `grade_venn_diagram` | INTENTIONAL |
| `backend/routes/assignment_player_routes.py` | 1092 | `(ValueError, TypeError)` | other | `grade_data_table` | INTENTIONAL |
| `backend/routes/assignment_player_routes.py` | 1173 | `Exception` | other | `grade_function_graph` | INTENTIONAL |
| `backend/routes/assignment_routes.py` | 22 | `ImportError` | other | `<module>` | INTENTIONAL |
| `backend/routes/assignment_routes.py` | 77 | `Exception` | log.exception + return | `save_assignment_config` | INTENTIONAL |
| `backend/routes/assignment_routes.py` | 155 | `json.JSONDecodeError` | return | `generate_model_answers` | INTENTIONAL |
| `backend/routes/assignment_routes.py` | 157 | `Exception` | log.exception + return | `generate_model_answers` | INTENTIONAL |
| `backend/routes/assignment_routes.py` | 248 | `Exception` | log.exception + return | `load_assignment` | INTENTIONAL |
| `backend/routes/assignment_routes.py` | 427 | `ImportError` | return | `_export_docx` | INTENTIONAL |
| `backend/routes/assignment_routes.py` | 429 | `Exception` | log.exception + return | `_export_docx` | INTENTIONAL |
| `backend/routes/assignment_routes.py` | 531 | `ImportError` | return | `_export_pdf` | INTENTIONAL |
| `backend/routes/assignment_routes.py` | 533 | `Exception` | log.exception + return | `_export_pdf` | INTENTIONAL |
| `backend/routes/assignment_routes.py` | 25 | `ImportError` | other | `<module>` | INTENTIONAL |
| `backend/routes/assignment_routes.py` | 271 | `Exception` | log.exception + return | `delete_assignment` | INTENTIONAL |
| `backend/routes/assignment_routes.py` | 216 | `Exception` | other | `list_assignments` | LEGACY |
| `backend/routes/assignment_routes.py` | 65 | `(json.JSONDecodeError, Exception)` | other | `save_assignment_config` | LEGACY |
| `backend/routes/assistant_routes.py` | 27 | `ImportError` | other | `<module>` | INTENTIONAL |
| `backend/routes/assistant_routes.py` | 32 | `ImportError` | other | `<module>` | INTENTIONAL |
| `backend/routes/assistant_routes.py` | 37 | `ImportError` | other | `<module>` | INTENTIONAL |
| `backend/routes/assistant_routes.py` | 50 | `ImportError` | other | `<module>` | INTENTIONAL |
| `backend/routes/assistant_routes.py` | 90 | `Exception` | return | `_get_assistant_model` | INTENTIONAL |
| `backend/routes/assistant_routes.py` | 234 | `Exception` | log.warning | `_persist_conversation` | LEGACY |
| `backend/routes/assistant_routes.py` | 246 | `Exception` | log.warning | `_load_conversation` | INTENTIONAL |
| `backend/routes/assistant_routes.py` | 289 | `Exception` | other | `_load_user_manual` | LEGACY |
| `backend/routes/assistant_routes.py` | 304 | `ImportError` | return | `_extract_text_from_pdf` | INTENTIONAL |
| `backend/routes/assistant_routes.py` | 306 | `Exception` | return | `_extract_text_from_pdf` | INTENTIONAL |
| `backend/routes/assistant_routes.py` | 334 | `ImportError` | return | `_extract_text_from_docx` | INTENTIONAL |
| `backend/routes/assistant_routes.py` | 336 | `Exception` | return | `_extract_text_from_docx` | INTENTIONAL |
| `backend/routes/assistant_routes.py` | 402 | `Exception` | pass | `_load_period_differentiation` | INTENTIONAL |
| `backend/routes/assistant_routes.py` | 423 | `Exception` | return | `_load_accommodation_summary` | INTENTIONAL |
| `backend/routes/assistant_routes.py` | 458 | `Exception` | pass | `_load_resource_names` | INTENTIONAL |
| `backend/routes/assistant_routes.py` | 533 | `Exception` | return | `_load_resource_content` | INTENTIONAL |
| `backend/routes/assistant_routes.py` | 545 | `Exception` | pass | `_load_rubric` | INTENTIONAL |
| `backend/routes/assistant_routes.py` | 576 | `Exception` | pass | `_load_assessment_templates` | INTENTIONAL |
| `backend/routes/assistant_routes.py` | 712 | `Exception` | return | `_load_analytics_snapshot` | LEGACY |
| `backend/routes/assistant_routes.py` | 969 | `Exception` | pass | `_build_system_prompt` | INTENTIONAL |
| `backend/routes/assistant_routes.py` | 1062 | `Exception` | pass | `_audit_log` | NEEDS_ALERT |
| `backend/routes/assistant_routes.py` | 1127 | `Exception` | log.error | `_record_assistant_cost` | LEGACY |
| `backend/routes/assistant_routes.py` | 1930 | `(FileNotFoundError, json.JSONDecodeError)` | return | `get_assistant_costs` | INTENTIONAL |
| `backend/routes/assistant_routes.py` | 2100 | `Exception` | pass | `get_voice_config` | INTENTIONAL |
| `backend/routes/assistant_routes.py` | 53 | `ImportError` | other | `<module>` | INTENTIONAL |
| `backend/routes/assistant_routes.py` | 599 | `Exception` | pass | `_load_analytics_snapshot` | INTENTIONAL |
| `backend/routes/assistant_routes.py` | 744 | `Exception` | pass | `_build_system_prompt` | INTENTIONAL |
| `backend/routes/assistant_routes.py` | 1094 | `(FileNotFoundError, json.JSONDecodeError)` | other | `_record_assistant_cost` | INTENTIONAL |
| `backend/routes/assistant_routes.py` | 1964 | `Exception` | pass | `get_memory` | NEEDS_ALERT |
| `backend/routes/assistant_routes.py` | 1977 | `Exception` | log.exception + return | `clear_memory` | INTENTIONAL |
| `backend/routes/assistant_routes.py` | 2039 | `Exception` | pass | `get_credentials` | NEEDS_ALERT |
| `backend/routes/assistant_routes.py` | 2067 | `Exception` | pass | `load_portal_credentials` | INTENTIONAL |
| `backend/routes/assistant_routes.py` | 511 | `Exception` | other | `_load_resource_content` | INTENTIONAL |
| `backend/routes/assistant_routes.py` | 1409 | `Exception` | log.warning | `generate` | INTENTIONAL |
| `backend/routes/assistant_routes.py` | 1814 | `Exception` | other | `generate` | LEGACY |
| `backend/routes/assistant_routes.py` | 449 | `Exception` | pass | `_load_resource_names` | INTENTIONAL |
| `backend/routes/assistant_routes.py` | 494 | `Exception` | pass | `_load_resource_content` | INTENTIONAL |
| `backend/routes/assistant_routes.py` | 630 | `(ValueError, TypeError)` | other | `_load_analytics_snapshot` | INTENTIONAL |
| `backend/routes/assistant_routes.py` | 1393 | `Exception` | pass | `generate` | INTENTIONAL |
| `backend/routes/assistant_routes.py` | 1424 | `queue.Empty` | other | `_flush_audio_queue` | INTENTIONAL |
| `backend/routes/assistant_routes.py` | 643 | `(ValueError, TypeError)` | pass | `_load_analytics_snapshot` | INTENTIONAL |
| `backend/routes/assistant_routes.py` | 1498 | `Exception` | pass | `generate` | INTENTIONAL |
| `backend/routes/assistant_routes.py` | 1712 | `json.JSONDecodeError` | other | `generate` | LEGACY |
| `backend/routes/assistant_routes.py` | 1844 | `queue.Empty` | other | `generate` | INTENTIONAL |
| `backend/routes/assistant_routes.py` | 1647 | `Exception` | pass | `generate` | LEGACY |
| `backend/routes/assistant_routes.py` | 1655 | `Exception` | pass | `generate` | INTENTIONAL |
| `backend/routes/assistant_routes.py` | 1796 | `Exception` | pass | `generate` | INTENTIONAL |
| `backend/routes/auth_routes.py` | 68 | `Exception` | return | `approve_user_route` | UNCATEGORIZED |
| `backend/routes/auth_routes.py` | 80 | `Exception` | log.error + return | `approve_user_route` | INTENTIONAL |
| `backend/routes/auth_routes.py` | 122 | `Exception` | log.error + return | `approval_status` | INTENTIONAL |
| `backend/routes/auth_routes.py` | 218 | `Exception` | log.error | `notify_signup_route` | UNCATEGORIZED |
| `backend/routes/auth_routes.py` | 179 | `Exception` | log.warning | `notify_signup_route` | UNCATEGORIZED |
| `backend/routes/automation_routes.py` | 95 | `json.JSONDecodeError` | pass | `_read_runner_output` | INTENTIONAL |
| `backend/routes/automation_routes.py` | 114 | `json.JSONDecodeError` | pass | `_read_picker_output` | INTENTIONAL |
| `backend/routes/automation_routes.py` | 141 | `Exception` | pass | `list_automations` | LEGACY |
| `backend/routes/automation_routes.py` | 236 | `Exception` | pass | `get_template` | LEGACY |
| `backend/routes/automation_routes.py` | 258 | `Exception` | pass | `delete_template` | NEEDS_ALERT |
| `backend/routes/automation_routes.py` | 56 | `Exception` | pass | `_cleanup_subprocesses` | INTENTIONAL |
| `backend/routes/automation_routes.py` | 215 | `Exception` | pass | `list_templates` | LEGACY |
| `backend/routes/automation_routes.py` | 59 | `Exception` | pass | `_cleanup_subprocesses` | INTENTIONAL |
| `backend/routes/behavior_routes.py` | 172 | `Exception` | log.debug | `get_behavior_data` | NEEDS_ALERT |
| `backend/routes/behavior_routes.py` | 268 | `(ValueError, TypeError)` | other | `get_behavior_events` | INTENTIONAL |
| `backend/routes/behavior_routes.py` | 287 | `Exception` | log.debug | `get_behavior_events` | NEEDS_ALERT |
| `backend/routes/behavior_routes.py` | 361 | `Exception` | return | `debug_behavior_data` | INTENTIONAL |
| `backend/routes/behavior_routes.py` | 378 | `Exception` | other | `debug_behavior_data` | NEEDS_ALERT |
| `backend/routes/behavior_routes.py` | 387 | `Exception` | other | `debug_behavior_data` | NEEDS_ALERT |
| `backend/routes/behavior_routes.py` | 450 | `Exception` | pass | `get_roster_for_behavior` | LEGACY |
| `backend/routes/behavior_routes.py` | 202 | `Exception` | pass | `get_behavior_data` | INTENTIONAL |
| `backend/routes/behavior_routes.py` | 421 | `Exception` | pass | `get_roster_for_behavior` | LEGACY |
| `backend/routes/classlink_routes.py` | 92 | `Exception` | log.warning | `_link_classlink_account` | NEEDS_ALERT |
| `backend/routes/classlink_routes.py` | 106 | `Exception` | return | `_resolve_classlink_user_id` | INTENTIONAL |
| `backend/routes/classlink_routes.py` | 226 | `Exception` | log.exception + return | `classlink_callback` | INTENTIONAL |
| `backend/routes/classlink_routes.py` | 241 | `Exception` | log.exception + return | `classlink_callback` | INTENTIONAL |
| `backend/routes/classlink_routes.py` | 150 | `Exception` | log.warning | `_bg_sync` | NEEDS_ALERT |
| `backend/routes/clever_routes.py` | 54 | `Exception` | pass | `_clever_audit` | LEGACY |
| `backend/routes/clever_routes.py` | 231 | `Exception` | log.warning + return | `_create_clever_student_session` | NEEDS_ALERT |
| `backend/routes/clever_routes.py` | 254 | `Exception` | log.warning | `_background_roster_sync` | NEEDS_ALERT |
| `backend/routes/clever_routes.py` | 432 | `Exception` | pass | `clever_session_check` | INTENTIONAL |
| `backend/routes/clever_routes.py` | 469 | `Exception` | log.error + return | `clever_sync_roster` | INTENTIONAL |
| `backend/routes/clever_routes.py` | 679 | `Exception` | log.error + return | `clever_delete_data` | INTENTIONAL |
| `backend/routes/clever_routes.py` | 392 | `Exception` | log.warning | `clever_callback` | INTENTIONAL |
| `backend/routes/clever_routes.py` | 603 | `Exception` | append + log.error | `clever_apply_accommodations` | INTENTIONAL |
| `backend/routes/clever_routes.py` | 672 | `Exception` | log.error | `clever_delete_data` | NEEDS_ALERT |
| `backend/routes/district_routes.py` | 82 | `Exception` | log.warning + return | `_clear_old_provider_data` | UNCATEGORIZED |
| `backend/routes/district_routes.py` | 128 | `Exception` | log.warning | `_clear_old_provider_data` | UNCATEGORIZED |
| `backend/routes/district_routes.py` | 138 | `Exception` | pass | `_clear_old_provider_data` | UNCATEGORIZED |
| `backend/routes/district_routes.py` | 429 | `Exception` | log.warning + return | `district_test_connection` | UNCATEGORIZED |
| `backend/routes/district_routes.py` | 149 | `OSError` | pass | `_clear_old_provider_data` | INTENTIONAL |
| `backend/routes/document_routes.py` | 107 | `ImportError` | append + return | `_parse_docx` | UNCATEGORIZED |
| `backend/routes/document_routes.py` | 201 | `ImportError` | return | `_parse_pdf` | UNCATEGORIZED |
| `backend/routes/document_routes.py` | 91 | `Exception` | pass | `_parse_docx` | UNCATEGORIZED |
| `backend/routes/email_routes.py` | 136 | `ImportError` | return | `send_emails` | INTENTIONAL |
| `backend/routes/email_routes.py` | 138 | `Exception` | log.exception + return | `send_emails` | INTENTIONAL |
| `backend/routes/email_routes.py` | 164 | `Exception` | log.exception + return | `test_email` | INTENTIONAL |
| `backend/routes/email_routes.py` | 193 | `Exception` | log.exception + return | `email_status` | INTENTIONAL |
| `backend/routes/email_routes.py` | 215 | `Exception` | log.exception + return | `save_email_config` | INTENTIONAL |
| `backend/routes/email_routes.py` | 359 | `Exception` | log.exception + return | `export_outlook_emails` | INTENTIONAL |
| `backend/routes/email_routes.py` | 577 | `Exception` | log.exception + return | `send_outlook_emails` | INTENTIONAL |
| `backend/routes/email_routes.py` | 616 | `Exception` | log.exception + return | `outlook_login` | INTENTIONAL |
| `backend/routes/email_routes.py` | 1061 | `Exception` | log.exception + return | `send_confirmation_emails` | INTENTIONAL |
| `backend/routes/email_routes.py` | 1153 | `Exception` | log.exception + return | `pending_confirmations` | INTENTIONAL |
| `backend/routes/email_routes.py` | 1175 | `Exception` | print | `_save_confirmed_filenames` | LEGACY |
| `backend/routes/email_routes.py` | 1229 | `Exception` | log.exception + return | `mark_confirmations_sent_file` | INTENTIONAL |
| `backend/routes/email_routes.py` | 1356 | `Exception` | pass | `_read_focus_comms_output` | NEEDS_ALERT |
| `backend/routes/email_routes.py` | 1390 | `Exception` | log.exception + return | `send_focus_comms` | INTENTIONAL |
| `backend/routes/email_routes.py` | 284 | `Exception` | pass | `export_outlook_emails` | LEGACY |
| `backend/routes/email_routes.py` | 456 | `json.JSONDecodeError` | pass | `_read_outlook_output` | INTENTIONAL |
| `backend/routes/email_routes.py` | 840 | `ImportError` | other | `send_confirmation_emails` | INTENTIONAL |
| `backend/routes/email_routes.py` | 865 | `Exception` | other | `send_confirmation_emails` | INTENTIONAL |
| `backend/routes/email_routes.py` | 1091 | `ImportError` | other | `pending_confirmations` | INTENTIONAL |
| `backend/routes/email_routes.py` | 1108 | `Exception` | pass | `pending_confirmations` | INTENTIONAL |
| `backend/routes/email_routes.py` | 1116 | `Exception` | other | `pending_confirmations` | INTENTIONAL |
| `backend/routes/email_routes.py` | 1164 | `Exception` | pass | `_load_confirmed_filenames` | LEGACY |
| `backend/routes/email_routes.py` | 1349 | `json.JSONDecodeError` | pass | `_read_focus_comms_output` | INTENTIONAL |
| `backend/routes/email_routes.py` | 1452 | `Exception` | pass | `confirm_send` | NEEDS_ALERT |
| `backend/routes/email_routes.py` | 1460 | `Exception` | log.exception + return | `confirm_send` | INTENTIONAL |
| `backend/routes/email_routes.py` | 51 | `Exception` | pass | `send_emails` | NEEDS_ALERT |
| `backend/routes/email_routes.py` | 267 | `Exception` | pass | `export_outlook_emails` | NEEDS_ALERT |
| `backend/routes/email_routes.py` | 1219 | `Exception` | print | `mark_confirmations_sent_file` | NEEDS_ALERT |
| `backend/routes/email_routes.py` | 1481 | `Exception` | pass | `confirm_send` | NEEDS_ALERT |
| `backend/routes/email_routes.py` | 999 | `Exception` | pass | `send_confirmation_emails` | NEEDS_ALERT |
| `backend/routes/email_routes.py` | 1494 | `Exception` | pass | `confirm_send` | NEEDS_ALERT |
| `backend/routes/email_routes.py` | 890 | `Exception` | pass | `send_confirmation_emails` | INTENTIONAL |
| `backend/routes/grading_routes.py` | 287 | `Exception` | print | `_sync_result_to_master_csv` | NEEDS_ALERT |
| `backend/routes/grading_routes.py` | 371 | `Exception` | pass | `update_result` | NEEDS_ALERT |
| `backend/routes/grading_routes.py` | 435 | `ImportError` | return | `grade_math` | INTENTIONAL |
| `backend/routes/grading_routes.py` | 470 | `ImportError` | return | `grade_data_table` | INTENTIONAL |
| `backend/routes/grading_routes.py` | 498 | `ImportError` | return | `grade_coordinates` | INTENTIONAL |
| `backend/routes/grading_routes.py` | 525 | `ImportError` | return | `grade_place_name` | INTENTIONAL |
| `backend/routes/grading_routes.py` | 551 | `ImportError` | return | `check_math_equivalence` | INTENTIONAL |
| `backend/routes/grading_routes.py` | 1225 | `Exception` | log.exception + return | `upload_focus_comments` | INTENTIONAL |
| `backend/routes/grading_routes.py` | 1282 | `Exception` | log.exception + return | `save_ell_students` | INTENTIONAL |
| `backend/routes/grading_routes.py` | 1426 | `Exception` | log.exception + return | `get_student_history` | INTENTIONAL |
| `backend/routes/grading_routes.py` | 1445 | `Exception` | log.exception + return | `delete_student_history` | INTENTIONAL |
| `backend/routes/grading_routes.py` | 778 | `Exception` | print | `export_focus_csv` | INTENTIONAL |
| `backend/routes/grading_routes.py` | 902 | `Exception` | pass | `export_focus_batch` | INTENTIONAL |
| `backend/routes/grading_routes.py` | 1019 | `Exception` | pass | `export_lms_csv` | INTENTIONAL |
| `backend/routes/grading_routes.py` | 1140 | `json.JSONDecodeError` | pass | `_read_focus_comments_output` | INTENTIONAL |
| `backend/routes/grading_routes.py` | 1262 | `Exception` | log.exception + return | `get_ell_students` | INTENTIONAL |
| `backend/routes/grading_routes.py` | 1387 | `Exception` | pass | `_build_student_name_lookup` | LEGACY |
| `backend/routes/grading_routes.py` | 1509 | `Exception` | print | `migrate_student_names` | NEEDS_ALERT |
| `backend/routes/grading_routes.py` | 163 | `Exception` | pass | `clear_results` | NEEDS_ALERT |
| `backend/routes/grading_routes.py` | 182 | `Exception` | print | `clear_results` | NEEDS_ALERT |
| `backend/routes/grading_routes.py` | 204 | `Exception` | pass | `clear_results` | NEEDS_ALERT |
| `backend/routes/grading_routes.py` | 212 | `Exception` | print | `clear_results` | NEEDS_ALERT |
| `backend/routes/grading_routes.py` | 395 | `Exception` | log.warning | `update_result` | LEGACY |
| `backend/routes/grading_routes.py` | 628 | `Exception` | pass | `export_focus_csv` | INTENTIONAL |
| `backend/routes/grading_routes.py` | 669 | `Exception` | pass | `export_focus_csv` | INTENTIONAL |
| `backend/routes/grading_routes.py` | 1468 | `Exception` | append | `delete_all_student_history` | INTENTIONAL |
| `backend/routes/grading_routes.py` | 1549 | `Exception` | pass | `migrate_student_names` | NEEDS_ALERT |
| `backend/routes/grading_routes.py` | 1325 | `Exception` | append | `list_student_history` | INTENTIONAL |
| `backend/routes/grading_routes.py` | 1403 | `Exception` | pass | `_build_student_name_lookup` | LEGACY |
| `backend/routes/grading_routes.py` | 1525 | `Exception` | pass | `migrate_student_names` | NEEDS_ALERT |
| `backend/routes/lesson_routes.py` | 15 | `ImportError` | other | `<module>` | INTENTIONAL |
| `backend/routes/lesson_routes.py` | 28 | `ImportError` | other | `<module>` | INTENTIONAL |
| `backend/routes/lesson_routes.py` | 171 | `Exception` | log.exception + return | `load_lesson` | INTENTIONAL |
| `backend/routes/lesson_routes.py` | 260 | `Exception` | return | `_load_calendar` | INTENTIONAL |
| `backend/routes/lesson_routes.py` | 432 | `Exception` | log.error + return | `parse_document_for_calendar` | INTENTIONAL |
| `backend/routes/lesson_routes.py` | 482 | `json.JSONDecodeError` | log.error + return | `parse_document_for_calendar` | INTENTIONAL |
| `backend/routes/lesson_routes.py` | 485 | `Exception` | log.error + return | `parse_document_for_calendar` | INTENTIONAL |
| `backend/routes/lesson_routes.py` | 31 | `ImportError` | other | `<module>` | INTENTIONAL |
| `backend/routes/lesson_routes.py` | 78 | `Exception` | log.exception + return | `save_lesson` | INTENTIONAL |
| `backend/routes/lesson_routes.py` | 194 | `Exception` | log.exception + return | `delete_lesson` | INTENTIONAL |
| `backend/routes/lesson_routes.py` | 142 | `Exception` | pass | `list_lessons` | LEGACY |
| `backend/routes/lti_routes.py` | 124 | `ValueError` | log.warning + return | `lti_launch` | UNCATEGORIZED |
| `backend/routes/lti_routes.py` | 353 | `Exception` | log.error + return | `lti_sync_grades` | INTENTIONAL |
| `backend/routes/notebooklm_routes.py` | 100 | `Exception` | log.exception + return | `nlm_login` | INTENTIONAL |
| `backend/routes/notebooklm_routes.py` | 207 | `Exception` | log.exception + return | `nlm_create_notebook` | INTENTIONAL |
| `backend/routes/notebooklm_routes.py` | 506 | `Exception` | log.exception + return | `share_material` | INTENTIONAL |
| `backend/routes/notebooklm_routes.py` | 558 | `Exception` | log.exception + return | `serve_shared_media` | INTENTIONAL |
| `backend/routes/notebooklm_routes.py` | 29 | `ImportError` | other | `_check_nlm_available` | UNCATEGORIZED |
| `backend/routes/notebooklm_routes.py` | 195 | `OSError` | log.warning | `nlm_create_notebook` | UNCATEGORIZED |
| `backend/routes/oneroster_routes.py` | 123 | `Exception` | log.warning + return | `test_connection` | INTENTIONAL |
| `backend/routes/oneroster_routes.py` | 157 | `Exception` | pass | `sync_roster` | LEGACY |
| `backend/routes/oneroster_routes.py` | 178 | `Exception` | log.error + return | `sync_roster` | INTENTIONAL |
| `backend/routes/oneroster_routes.py` | 204 | `Exception` | log.warning | `sync_roster` | NEEDS_ALERT |
| `backend/routes/oneroster_routes.py` | 218 | `Exception` | log.warning | `sync_roster` | NEEDS_ALERT |
| `backend/routes/oneroster_routes.py` | 363 | `Exception` | log.error + return | `sync_grades` | INTENTIONAL |
| `backend/routes/oneroster_routes.py` | 369 | `Exception` | log.error + return | `sync_grades` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 23 | `ImportError` | other | `<module>` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 35 | `ImportError` | other | `<module>` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 68 | `(FileNotFoundError, json.JSONDecodeError)` | other | `_record_planner_cost` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 730 | `Exception` | print | `_auto_fix_flagged_questions` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 2300 | `Exception` | return | `_load_standards_file` | LEGACY |
| `backend/routes/planner_routes.py` | 2519 | `Exception` | log.exception + return | `align_document_to_standards` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 2611 | `Exception` | log.exception + return | `rewrite_for_alignment` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 2655 | `Exception` | log.exception + return | `get_lesson_templates` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 2823 | `Exception` | print + return | `brainstorm_lesson_ideas` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 3314 | `Exception` | print + return | `generate_lesson_plan` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 3968 | `Exception` | print + return | `generate_assignment_from_lesson` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 4211 | `Exception` | log.exception + return | `export_lesson_plan` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 4344 | `Exception` | print | `_save_grading_config_for_export` | LEGACY |
| `backend/routes/planner_routes.py` | 5164 | `Exception` | log.exception + return | `export_generated_assignment` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 5749 | `Exception` | print + return | `_create_visual_for_question` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 6265 | `Exception` | print + return | `generate_assessment` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 6449 | `Exception` | log.exception + return | `export_assessment` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 6556 | `Exception` | other | `parse_template_structure` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 6614 | `Exception` | log.exception + return | `delete_assessment_template` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 6847 | `Exception` | log.exception + return | `export_assessment_for_platform` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 7143 | `Exception` | log.exception + return | `grade_assessment_answers` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 7272 | `Exception` | log.exception + return | `regenerate_questions` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 7285 | `(FileNotFoundError, json.JSONDecodeError)` | return | `get_planner_costs` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 7366 | `Exception` | log.exception + return | `adjust_reading_level` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 7460 | `Exception` | log.exception + return | `extract_text_from_file` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 7570 | `json.JSONDecodeError` | log.error + return | `generate_study_guide` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 7573 | `Exception` | log.exception + return | `generate_study_guide` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 7728 | `Exception` | log.exception + return | `export_study_guide` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 7831 | `json.JSONDecodeError` | log.error + return | `generate_flashcards` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 7834 | `Exception` | log.exception + return | `generate_flashcards` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 7978 | `Exception` | log.exception + return | `export_flashcards` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 8054 | `json.JSONDecodeError` | log.error + return | `generate_slides` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 8057 | `Exception` | log.exception + return | `generate_slides` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 8102 | `Exception` | log.exception + return | `export_slides` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 38 | `ImportError` | other | `<module>` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 1344 | `(ValueError, IndexError)` | pass | `_hydrate_fraction_model` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 2270 | `(ValueError, IndexError)` | pass | `_grade_matches` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 2510 | `json.JSONDecodeError` | print + return | `align_document_to_standards` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 2602 | `json.JSONDecodeError` | print + return | `rewrite_for_alignment` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 4764 | `Exception` | log.exception + return | `export_generated_assignment` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 562 | `(ValueError, IndexError)` | pass | `_check_question_quality` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 2203 | `Exception` | other | `load_support_documents_for_planning` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 4340 | `Exception` | pass | `_save_grading_config_for_export` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 6578 | `Exception` | pass | `get_assessment_templates` | LEGACY |
| `backend/routes/planner_routes.py` | 7120 | `Exception` | print | `grade_assessment_answers` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 8043 | `Exception` | log.warning | `generate_slides` | LEGACY |
| `backend/routes/planner_routes.py` | 8086 | `Exception` | pass | `export_slides` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 4523 | `Exception` | print | `_export_assignment_docx_graider` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 7411 | `ImportError` | return | `extract_text_from_file` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 1781 | `ValueError` | pass | `_extract_dimensions_from_text` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 2183 | `Exception` | other | `load_support_documents_for_planning` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 2191 | `Exception` | other | `load_support_documents_for_planning` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 7030 | `ValueError` | other | `grade_assessment_answers` | INTENTIONAL |
| `backend/routes/planner_routes.py` | 5440 | `Exception` | other | `_create_visual_for_question` | INTENTIONAL |
| `backend/routes/settings_routes.py` | 28 | `ImportError` | other | `<module>` | INTENTIONAL |
| `backend/routes/settings_routes.py` | 41 | `ImportError` | other | `<module>` | INTENTIONAL |
| `backend/routes/settings_routes.py` | 153 | `Exception` | print | `get_students_from_period_file` | LEGACY |
| `backend/routes/settings_routes.py` | 175 | `Exception` | log.exception + return | `save_rubric` | INTENTIONAL |
| `backend/routes/settings_routes.py` | 198 | `Exception` | log.exception + return | `load_rubric` | INTENTIONAL |
| `backend/routes/settings_routes.py` | 219 | `Exception` | log.exception + return | `save_global_settings` | INTENTIONAL |
| `backend/routes/settings_routes.py` | 242 | `Exception` | log.exception + return | `load_global_settings` | INTENTIONAL |
| `backend/routes/settings_routes.py` | 261 | `Exception` | return | `parse_csv_headers` | INTENTIONAL |
| `backend/routes/settings_routes.py` | 373 | `Exception` | log.exception + return | `delete_roster` | INTENTIONAL |
| `backend/routes/settings_routes.py` | 534 | `Exception` | log.exception + return | `delete_period` | INTENTIONAL |
| `backend/routes/settings_routes.py` | 574 | `Exception` | log.exception + return | `update_period_level` | INTENTIONAL |
| `backend/routes/settings_routes.py` | 598 | `Exception` | log.exception + return | `get_period_students` | INTENTIONAL |
| `backend/routes/settings_routes.py` | 681 | `Exception` | log.exception + return | `delete_document` | INTENTIONAL |
| `backend/routes/settings_routes.py` | 893 | `ImportError` | return | `preview_parent_contacts` | INTENTIONAL |
| `backend/routes/settings_routes.py` | 895 | `Exception` | log.exception + return | `preview_parent_contacts` | INTENTIONAL |
| `backend/routes/settings_routes.py` | 1106 | `ImportError` | return | `save_parent_contact_mapping` | INTENTIONAL |
| `backend/routes/settings_routes.py` | 1108 | `Exception` | log.exception + return | `save_parent_contact_mapping` | INTENTIONAL |
| `backend/routes/settings_routes.py` | 1169 | `Exception` | log.exception + return | `get_parent_contacts` | INTENTIONAL |
| `backend/routes/settings_routes.py` | 1374 | `Exception` | log.exception + return | `import_accommodations` | INTENTIONAL |
| `backend/routes/settings_routes.py` | 1572 | `Exception` | other | `_run_focus_import` | NEEDS_ALERT |
| `backend/routes/settings_routes.py` | 1953 | `Exception` | log.exception + return | `add_student` | INTENTIONAL |
| `backend/routes/settings_routes.py` | 2004 | `Exception` | log.exception + return | `remove_student` | INTENTIONAL |
| `backend/routes/settings_routes.py` | 2118 | `Exception` | log.exception + return | `update_student` | INTENTIONAL |
| `backend/routes/settings_routes.py` | 2145 | `Exception` | log.exception + return | `sync_to_cloud` | INTENTIONAL |
| `backend/routes/settings_routes.py` | 44 | `ImportError` | other | `<module>` | INTENTIONAL |
| `backend/routes/settings_routes.py` | 428 | `Exception` | pass | `upload_period` | INTENTIONAL |
| `backend/routes/settings_routes.py` | 1082 | `OSError` | pass | `save_parent_contact_mapping` | INTENTIONAL |
| `backend/routes/settings_routes.py` | 1130 | `Exception` | log.exception + return | `get_parent_contacts` | INTENTIONAL |
| `backend/routes/settings_routes.py` | 1147 | `Exception` | pass | `get_parent_contacts` | INTENTIONAL |
| `backend/routes/settings_routes.py` | 1596 | `(json.JSONDecodeError, IOError)` | pass | `_process_focus_import` | INTENTIONAL |
| `backend/routes/settings_routes.py` | 1788 | `(json.JSONDecodeError, IOError)` | pass | `_update_meta_row_count` | INTENTIONAL |
| `backend/routes/settings_routes.py` | 1815 | `(json.JSONDecodeError, IOError)` | pass | `_load_parent_contacts` | INTENTIONAL |
| `backend/routes/settings_routes.py` | 1834 | `RuntimeError` | other | `_save_parent_contacts` | INTENTIONAL |
| `backend/routes/settings_routes.py` | 130 | `ImportError` | print | `get_students_from_period_file` | INTENTIONAL |
| `backend/routes/settings_routes.py` | 348 | `Exception` | pass | `list_rosters` | LEGACY |
| `backend/routes/settings_routes.py` | 490 | `Exception` | print | `list_periods` | LEGACY |
| `backend/routes/settings_routes.py` | 656 | `Exception` | pass | `list_documents` | LEGACY |
| `backend/routes/settings_routes.py` | 1252 | `Exception` | pass | `get_all_student_accommodations` | INTENTIONAL |
| `backend/routes/settings_routes.py` | 1547 | `json.JSONDecodeError` | pass | `_run_focus_import` | INTENTIONAL |
| `backend/routes/settings_routes.py` | 1842 | `Exception` | log.warning | `_save_parent_contacts` | INTENTIONAL |
| `backend/routes/settings_routes.py` | 509 | `Exception` | print | `list_periods` | LEGACY |
| `backend/routes/settings_routes.py` | 773 | `(ValueError, TypeError)` | pass | `_suggest_mapping` | INTENTIONAL |
| `backend/routes/settings_routes.py` | 1266 | `Exception` | pass | `get_all_student_accommodations` | LEGACY |
| `backend/routes/settings_routes.py` | 1934 | `(json.JSONDecodeError, IOError)` | pass | `add_student` | INTENTIONAL |
| `backend/routes/settings_routes.py` | 2095 | `(json.JSONDecodeError, IOError)` | pass | `update_student` | INTENTIONAL |
| `backend/routes/settings_routes.py` | 1003 | `(ValueError, TypeError)` | other | `_process_rows` | INTENTIONAL |
| `backend/routes/stripe_routes.py` | 118 | `Exception` | log.exception + return | `subscription_status` | INTENTIONAL |
| `backend/routes/stripe_routes.py` | 156 | `Exception` | log.exception + return | `create_checkout_session` | INTENTIONAL |
| `backend/routes/stripe_routes.py` | 181 | `Exception` | log.exception + return | `create_portal_session` | INTENTIONAL |
| `backend/routes/stripe_routes.py` | 205 | `stripe.error.SignatureVerificationError` | return | `stripe_webhook` | UNCATEGORIZED |
| `backend/routes/stripe_routes.py` | 207 | `Exception` | log.error + return | `stripe_webhook` | INTENTIONAL |
| `backend/routes/stripe_routes.py` | 261 | `Exception` | pass | `_sync_subscription_metadata` | UNCATEGORIZED |
| `backend/routes/student_account_routes.py` | 78 | `Exception` | log.warning + return | `_spawn_grading_thread_safe` | INTENTIONAL |
| `backend/routes/student_account_routes.py` | 160 | `Exception` | log.exception + return | `create_class` | INTENTIONAL |
| `backend/routes/student_account_routes.py` | 179 | `Exception` | log.exception + return | `list_classes` | INTENTIONAL |
| `backend/routes/student_account_routes.py` | 301 | `Exception` | log.exception + return | `sync_roster_to_class` | INTENTIONAL |
| `backend/routes/student_account_routes.py` | 328 | `Exception` | log.exception + return | `list_class_students` | INTENTIONAL |
| `backend/routes/student_account_routes.py` | 388 | `Exception` | log.exception + return | `publish_to_class` | INTENTIONAL |
| `backend/routes/student_account_routes.py` | 454 | `Exception` | log.exception + return | `get_portal_submissions` | INTENTIONAL |
| `backend/routes/student_account_routes.py` | 558 | `Exception` | log.exception + return | `grade_portal_submission` | INTENTIONAL |
| `backend/routes/student_account_routes.py` | 643 | `Exception` | log.exception + return | `student_login` | INTENTIONAL |
| `backend/routes/student_account_routes.py` | 690 | `Exception` | log.exception + return | `student_dashboard` | INTENTIONAL |
| `backend/routes/student_account_routes.py` | 747 | `Exception` | log.exception + return | `get_student_content` | INTENTIONAL |
| `backend/routes/student_account_routes.py` | 951 | `Exception` | log.exception + return | `submit_student_work` | INTENTIONAL |
| `backend/routes/student_account_routes.py` | 998 | `Exception` | return | `check_student_session` | LEGACY |
| `backend/routes/student_account_routes.py` | 1101 | `Exception` | log.exception + return | `send_submission_confirmations` | INTENTIONAL |
| `backend/routes/student_account_routes.py` | 1138 | `Exception` | log.exception + return | `mark_confirmations_sent` | INTENTIONAL |
| `backend/routes/student_account_routes.py` | 1184 | `Exception` | log.exception + return | `student_resources` | INTENTIONAL |
| `backend/routes/student_account_routes.py` | 1229 | `Exception` | log.exception + return | `student_resource_content` | INTENTIONAL |
| `backend/routes/student_account_routes.py` | 1320 | `Exception` | log.exception + return | `save_submission_draft` | INTENTIONAL |
| `backend/routes/student_account_routes.py` | 1374 | `Exception` | log.exception + return | `get_submission_draft` | INTENTIONAL |
| `backend/routes/student_account_routes.py` | 450 | `Exception` | pass | `get_portal_submissions` | LEGACY |
| `backend/routes/student_account_routes.py` | 848 | `Exception` | raise + return | `submit_student_work` | INTENTIONAL |
| `backend/routes/student_account_routes.py` | 985 | `Exception` | pass | `check_student_session` | LEGACY |
| `backend/routes/student_account_routes.py` | 292 | `Exception` | append | `sync_roster_to_class` | INTENTIONAL |
| `backend/routes/student_account_routes.py` | 917 | `Exception` | log.debug | `submit_student_work` | INTENTIONAL |
| `backend/routes/student_account_routes.py` | 1058 | `Exception` | pass | `send_submission_confirmations` | INTENTIONAL |
| `backend/routes/student_portal_routes.py` | 45 | `(ValueError, AttributeError)` | return | `_parse_ts` | INTENTIONAL |
| `backend/routes/student_portal_routes.py` | 289 | `Exception` | log.exception + return | `publish_assessment` | INTENTIONAL |
| `backend/routes/student_portal_routes.py` | 331 | `Exception` | log.exception + return | `save_assessment` | INTENTIONAL |
| `backend/routes/student_portal_routes.py` | 371 | `Exception` | log.exception + return | `list_saved_assessments` | INTENTIONAL |
| `backend/routes/student_portal_routes.py` | 408 | `Exception` | log.exception + return | `load_saved_assessment` | INTENTIONAL |
| `backend/routes/student_portal_routes.py` | 438 | `Exception` | log.exception + return | `delete_saved_assessment` | INTENTIONAL |
| `backend/routes/student_portal_routes.py` | 472 | `Exception` | log.exception + return | `list_published_assessments` | INTENTIONAL |
| `backend/routes/student_portal_routes.py` | 521 | `Exception` | log.exception + return | `get_assessment_results` | INTENTIONAL |
| `backend/routes/student_portal_routes.py` | 558 | `Exception` | log.exception + return | `toggle_assessment` | INTENTIONAL |
| `backend/routes/student_portal_routes.py` | 589 | `Exception` | log.exception + return | `delete_published_assessment` | INTENTIONAL |
| `backend/routes/student_portal_routes.py` | 692 | `Exception` | log.exception + return | `get_assessment_for_student` | INTENTIONAL |
| `backend/routes/student_portal_routes.py` | 867 | `Exception` | log.exception + return | `submit_assessment` | INTENTIONAL |
| `backend/routes/student_portal_routes.py` | 910 | `Exception` | log.exception + return | `list_shared_resources` | INTENTIONAL |
| `backend/routes/student_portal_routes.py` | 933 | `Exception` | log.exception + return | `delete_shared_resource` | INTENTIONAL |
| `backend/routes/student_portal_routes.py` | 960 | `Exception` | log.exception + return | `delete_shared_resources_bulk` | INTENTIONAL |
| `backend/routes/student_portal_routes.py` | 990 | `Exception` | log.exception + return | `update_shared_resource_unit` | INTENTIONAL |
| `backend/routes/student_portal_routes.py` | 1027 | `Exception` | log.exception + return | `end_student_attempt` | INTENTIONAL |
| `backend/routes/student_portal_routes.py` | 1074 | `Exception` | log.exception + return | `list_in_progress_drafts` | INTENTIONAL |
| `backend/routes/student_portal_routes.py` | 1129 | `Exception` | log.exception + return | `list_content_submissions` | INTENTIONAL |
| `backend/routes/student_portal_routes.py` | 1245 | `Exception` | log.exception + return | `get_class_progress_rank` | INTENTIONAL |
| `backend/routes/student_portal_routes.py` | 1288 | `Exception` | log.exception + return | `list_teacher_tags` | INTENTIONAL |
| `backend/routes/student_portal_routes.py` | 1331 | `Exception` | log.exception + return | `set_content_tags` | INTENTIONAL |
| `backend/routes/student_portal_routes.py` | 787 | `Exception` | raise + return | `submit_assessment` | INTENTIONAL |
| `backend/routes/student_portal_routes.py` | 365 | `Exception` | pass | `list_saved_assessments` | INTENTIONAL |
| `backend/routes/sync_routes.py` | 32 | `Exception` | return | `get_supabase` | UNCATEGORIZED |
| `backend/routes/sync_routes.py` | 136 | `Exception` | log.exception + return | `_discover_teachers` | INTENTIONAL |
| `backend/routes/sync_routes.py` | 145 | `Exception` | log.warning | `_save_cursor` | UNCATEGORIZED |
| `backend/routes/sync_routes.py` | 239 | `Exception` | log.exception + return | `_sync_one_teacher` | INTENTIONAL |
| `backend/scripts/populate_fl_standards.py` | 177 | `requests.RequestException` | print + return | `fetch_ixl_page` | UNCATEGORIZED |
| `backend/scripts/populate_fl_standards.py` | 415 | `Exception` | print | `enrich_batch` | UNCATEGORIZED |
| `backend/scripts/populate_fl_standards.py` | 315 | `ValueError` | append | `_code_sort_key` | UNCATEGORIZED |
| `backend/services/assistant_tools.py` | 32 | `ImportError` | other | `<module>` | INTENTIONAL |
| `backend/services/assistant_tools.py` | 140 | `(ValueError, TypeError)` | return | `_safe_int_score` | INTENTIONAL |
| `backend/services/assistant_tools.py` | 242 | `Exception` | return | `_load_results` | LEGACY |
| `backend/services/assistant_tools.py` | 481 | `Exception` | pass | `_load_standards` | INTENTIONAL |
| `backend/services/assistant_tools.py` | 743 | `Exception` | return | `_load_parent_contacts` | LEGACY |
| `backend/services/assistant_tools.py` | 804 | `Exception` | return | `_load_calendar` | INTENTIONAL |
| `backend/services/assistant_tools.py` | 831 | `Exception` | return | `_load_memories` | LEGACY |
| `backend/services/assistant_tools.py` | 979 | `Exception` | return | `execute_tool` | INTENTIONAL |
| `backend/services/assistant_tools.py` | 35 | `ImportError` | other | `<module>` | INTENTIONAL |
| `backend/services/assistant_tools.py` | 329 | `Exception` | pass | `_load_master_csv` | NEEDS_ALERT |
| `backend/services/assistant_tools.py` | 463 | `Exception` | pass | `_load_settings` | INTENTIONAL |
| `backend/services/assistant_tools.py` | 509 | `Exception` | pass | `_load_standards` | LEGACY |
| `backend/services/assistant_tools.py` | 786 | `Exception` | pass | `_load_saved_assignments` | LEGACY |
| `backend/services/assistant_tools.py` | 852 | `Exception` | pass | `_load_email_config` | LEGACY |
| `backend/services/assistant_tools.py` | 919 | `(ImportError, AttributeError)` | other | `_merge_submodules` | INTENTIONAL |
| `backend/services/assistant_tools.py` | 420 | `Exception` | pass | `_load_period_class_levels` | INTENTIONAL |
| `backend/services/assistant_tools.py` | 446 | `Exception` | pass | `_load_accommodations` | NEEDS_ALERT |
| `backend/services/assistant_tools.py` | 673 | `Exception` | pass | `_load_roster` | LEGACY |
| `backend/services/assistant_tools.py` | 725 | `Exception` | pass | `_load_roster` | LEGACY |
| `backend/services/assistant_tools.py` | 961 | `Exception` | pass | `execute_tool` | NEEDS_ALERT |
| `backend/services/assistant_tools.py` | 631 | `Exception` | pass | `_load_roster` | INTENTIONAL |
| `backend/services/assistant_tools.py` | 693 | `Exception` | pass | `_load_roster` | LEGACY |
| `backend/services/assistant_tools.py` | 974 | `(ValueError, TypeError)` | other | `execute_tool` | INTENTIONAL |
| `backend/services/assistant_tools.py` | 546 | `Exception` | pass | `_load_saved_lessons` | LEGACY |
| `backend/services/assistant_tools_ai.py` | 113 | `ImportError` | return | `_get_anthropic_client` | UNCATEGORIZED |
| `backend/services/assistant_tools_ai.py` | 135 | `json.JSONDecodeError` | return | `_call_haiku` | UNCATEGORIZED |
| `backend/services/assistant_tools_ai.py` | 137 | `Exception` | return | `_call_haiku` | UNCATEGORIZED |
| `backend/services/assistant_tools_ai.py` | 312 | `json.JSONDecodeError` | pass | `generate_iep_progress_notes` | INTENTIONAL |
| `backend/services/assistant_tools_assessments.py` | 23 | `Exception` | return | `_get_supabase` | UNCATEGORIZED |
| `backend/services/assistant_tools_assessments.py` | 59 | `Exception` | log.exception + return | `list_published_assessments_tool` | INTENTIONAL |
| `backend/services/assistant_tools_assessments.py` | 172 | `Exception` | log.exception + return | `query_assessment_results` | INTENTIONAL |
| `backend/services/assistant_tools_automation.py` | 14 | `ImportError` | other | `<module>` | UNCATEGORIZED |
| `backend/services/assistant_tools_automation.py` | 17 | `ImportError` | other | `<module>` | UNCATEGORIZED |
| `backend/services/assistant_tools_automation.py` | 105 | `Exception` | pass | `list_automations_tool` | UNCATEGORIZED |
| `backend/services/assistant_tools_automation.py` | 192 | `Exception` | pass | `run_automation_tool` | UNCATEGORIZED |
| `backend/services/assistant_tools_behavior.py` | 78 | `Exception` | append + log.error + log.info + log.warning | `_load_behavior_events` | INTENTIONAL |
| `backend/services/assistant_tools_behavior.py` | 188 | `Exception` | return | `_load_settings` | LEGACY |
| `backend/services/assistant_tools_behavior.py` | 198 | `Exception` | return | `_load_parent_contacts` | NEEDS_ALERT |
| `backend/services/assistant_tools_behavior.py` | 329 | `Exception` | return | `debug_behavior` | INTENTIONAL |
| `backend/services/assistant_tools_behavior.py` | 617 | `Exception` | log.warning + return | `_generate_email_ai` | INTENTIONAL |
| `backend/services/assistant_tools_behavior.py` | 855 | `Exception` | pass | `send_behavior_email` | INTENTIONAL |
| `backend/services/assistant_tools_behavior.py` | 865 | `Exception` | pass | `send_behavior_email` | NEEDS_ALERT |
| `backend/services/assistant_tools_behavior.py` | 108 | `Exception` | log.error | `_load_behavior_events` | NEEDS_ALERT |
| `backend/services/assistant_tools_behavior.py` | 139 | `Exception` | pass | `_load_behavior_events` | INTENTIONAL |
| `backend/services/assistant_tools_communication.py` | 395 | `Exception` | pass | `generate_parent_conference_notes` | UNCATEGORIZED |
| `backend/services/assistant_tools_data.py` | 16 | `ImportError` | other | `<module>` | INTENTIONAL |
| `backend/services/assistant_tools_data.py` | 68 | `Exception` | return | `_load_memories` | LEGACY |
| `backend/services/assistant_tools_data.py` | 127 | `Exception` | return | `_load_calendar` | INTENTIONAL |
| `backend/services/assistant_tools_data.py` | 19 | `ImportError` | other | `<module>` | INTENTIONAL |
| `backend/services/assistant_tools_data.py` | 152 | `Exception` | pass | `_load_email_config` | LEGACY |
| `backend/services/assistant_tools_edtech.py` | 331 | `ImportError` | return | `generate_kahoot_quiz` | UNCATEGORIZED |
| `backend/services/assistant_tools_edtech.py` | 478 | `ImportError` | return | `generate_nearpod_questions` | UNCATEGORIZED |
| `backend/services/assistant_tools_grading.py` | 29 | `ImportError` | other | `<module>` | INTENTIONAL |
| `backend/services/assistant_tools_grading.py` | 88 | `Exception` | other | `_scan_submission_folder` | INTENTIONAL |
| `backend/services/assistant_tools_grading.py` | 854 | `Exception` | other | `scan_submissions_folder` | INTENTIONAL |
| `backend/services/assistant_tools_grading.py` | 32 | `ImportError` | other | `<module>` | INTENTIONAL |
| `backend/services/assistant_tools_grading.py` | 837 | `Exception` | pass | `scan_submissions_folder` | INTENTIONAL |
| `backend/services/assistant_tools_planning.py` | 191 | `Exception` | return | `_get_standards_for_lesson` | UNCATEGORIZED |
| `backend/services/assistant_tools_planning.py` | 724 | `ImportError` | return | `generate_sub_plans` | UNCATEGORIZED |
| `backend/services/assistant_tools_reports.py` | 34 | `ImportError` | other | `<module>` | INTENTIONAL |
| `backend/services/assistant_tools_reports.py` | 804 | `ImportError` | return | `_parse_curriculum_map_for_dates` | INTENTIONAL |
| `backend/services/assistant_tools_reports.py` | 811 | `Exception` | return | `_parse_curriculum_map_for_dates` | INTENTIONAL |
| `backend/services/assistant_tools_reports.py` | 1015 | `ImportError` | return | `_extract_pdf_text` | INTENTIONAL |
| `backend/services/assistant_tools_reports.py` | 1017 | `Exception` | return | `_extract_pdf_text` | INTENTIONAL |
| `backend/services/assistant_tools_reports.py` | 1049 | `ImportError` | return | `_extract_docx_text` | INTENTIONAL |
| `backend/services/assistant_tools_reports.py` | 1051 | `Exception` | return | `_extract_docx_text` | INTENTIONAL |
| `backend/services/assistant_tools_reports.py` | 1129 | `FileNotFoundError` | return | `create_focus_assignment` | INTENTIONAL |
| `backend/services/assistant_tools_reports.py` | 1131 | `Exception` | return | `create_focus_assignment` | INTENTIONAL |
| `backend/services/assistant_tools_reports.py` | 1570 | `ImportError` | return | `generate_worksheet_tool` | INTENTIONAL |
| `backend/services/assistant_tools_reports.py` | 1572 | `Exception` | return | `generate_worksheet_tool` | INTENTIONAL |
| `backend/services/assistant_tools_reports.py` | 1585 | `ImportError` | return | `generate_document_tool` | INTENTIONAL |
| `backend/services/assistant_tools_reports.py` | 1587 | `Exception` | return | `generate_document_tool` | INTENTIONAL |
| `backend/services/assistant_tools_reports.py` | 1674 | `Exception` | return | `save_document_style_tool` | INTENTIONAL |
| `backend/services/assistant_tools_reports.py` | 1684 | `Exception` | return | `list_document_styles_tool` | INTENTIONAL |
| `backend/services/assistant_tools_reports.py` | 1898 | `Exception` | pass | `get_calendar` | LEGACY |
| `backend/services/assistant_tools_reports.py` | 2025 | `Exception` | return | `list_resources_tool` | INTENTIONAL |
| `backend/services/assistant_tools_reports.py` | 2063 | `Exception` | return | `read_resource_tool` | INTENTIONAL |
| `backend/services/assistant_tools_reports.py` | 2359 | `ImportError` | return | `send_parent_emails` | INTENTIONAL |
| `backend/services/assistant_tools_reports.py` | 2361 | `Exception` | return | `send_parent_emails` | INTENTIONAL |
| `backend/services/assistant_tools_reports.py` | 2396 | `Exception` | return | `send_focus_comms` | INTENTIONAL |
| `backend/services/assistant_tools_reports.py` | 2505 | `ImportError` | return | `send_focus_comms` | INTENTIONAL |
| `backend/services/assistant_tools_reports.py` | 2507 | `Exception` | return | `send_focus_comms` | INTENTIONAL |
| `backend/services/assistant_tools_reports.py` | 2643 | `Exception` | return | `confirm_and_send` | INTENTIONAL |
| `backend/services/assistant_tools_reports.py` | 37 | `ImportError` | other | `<module>` | INTENTIONAL |
| `backend/services/assistant_tools_reports.py` | 2088 | `Exception` | pass | `read_resource_tool` | INTENTIONAL |
| `backend/services/assistant_tools_reports.py` | 2122 | `Exception` | pass | `save_assignment_config` | LEGACY |
| `backend/services/assistant_tools_reports.py` | 2337 | `Exception` | pass | `send_parent_emails` | NEEDS_ALERT |
| `backend/services/assistant_tools_reports.py` | 2484 | `Exception` | pass | `send_focus_comms` | NEEDS_ALERT |
| `backend/services/assistant_tools_reports.py` | 2541 | `Exception` | return | `confirm_and_send` | INTENTIONAL |
| `backend/services/assistant_tools_reports.py` | 792 | `Exception` | other | `_parse_curriculum_map_for_dates` | INTENTIONAL |
| `backend/services/assistant_tools_reports.py` | 823 | `ValueError` | other | `_parse_map_date` | INTENTIONAL |
| `backend/services/assistant_tools_reports.py` | 1831 | `Exception` | other | `get_recent_lessons` | LEGACY |
| `backend/services/assistant_tools_reports.py` | 656 | `(ValueError, TypeError)` | pass | `_analyze_group_weaknesses` | INTENTIONAL |
| `backend/services/assistant_tools_reports.py` | 750 | `(ValueError, TypeError)` | other | `_match_standards` | INTENTIONAL |
| `backend/services/assistant_tools_reports.py` | 2015 | `Exception` | pass | `list_resources_tool` | INTENTIONAL |
| `backend/services/assistant_tools_reports.py` | 2562 | `OSError` | pass | `confirm_and_send` | INTENTIONAL |
| `backend/services/assistant_tools_reports.py` | 2581 | `OSError` | pass | `confirm_and_send` | INTENTIONAL |
| `backend/services/assistant_tools_reports.py` | 2598 | `OSError` | pass | `_clear_behavior_pending` | INTENTIONAL |
| `backend/services/assistant_tools_stem.py` | 221 | `(TypeError, ValueError)` | return | `handle_grade_coordinates` | UNCATEGORIZED |
| `backend/services/assistant_tools_student.py` | 428 | `Exception` | log.warning + return | `_delete_student_supabase` | NEEDS_ALERT |
| `backend/services/assistant_tools_student.py` | 522 | `Exception` | append | `_execute_student_removal` | LEGACY |
| `backend/services/assistant_tools_student.py` | 548 | `Exception` | append | `_execute_student_removal` | LEGACY |
| `backend/services/assistant_tools_student.py` | 557 | `Exception` | append | `_execute_student_removal` | LEGACY |
| `backend/services/assistant_tools_student.py` | 574 | `Exception` | append | `_execute_student_removal` | LEGACY |
| `backend/services/assistant_tools_student.py` | 591 | `Exception` | append | `_execute_student_removal` | LEGACY |
| `backend/services/assistant_tools_student.py` | 608 | `Exception` | append | `_execute_student_removal` | LEGACY |
| `backend/services/assistant_tools_student.py` | 676 | `Exception` | pass | `remove_student_from_roster` | INTENTIONAL |
| `backend/services/assistant_tools_student.py` | 684 | `Exception` | pass | `remove_student_from_roster` | NEEDS_ALERT |
| `backend/services/assistant_tools_student.py` | 691 | `Exception` | pass | `remove_student_from_roster` | NEEDS_ALERT |
| `backend/services/assistant_tools_student.py` | 724 | `Exception` | pass | `confirm_student_removal` | NEEDS_ALERT |
| `backend/services/assistant_tools_student.py` | 749 | `Exception` | pass | `confirm_student_removal` | NEEDS_ALERT |
| `backend/services/assistant_tools_student.py` | 755 | `Exception` | pass | `confirm_student_removal` | NEEDS_ALERT |
| `backend/services/assistant_tools_student.py` | 875 | `(json.JSONDecodeError, UnicodeDecodeError)` | return | `import_student_data` | INTENTIONAL |
| `backend/services/assistant_tools_student.py` | 445 | `Exception` | other | `_execute_student_removal` | INTENTIONAL |
| `backend/services/assistant_tools_student.py` | 495 | `Exception` | append | `_execute_student_removal` | LEGACY |
| `backend/services/assistant_tools_student.py` | 642 | `Exception` | other | `remove_student_from_roster` | INTENTIONAL |
| `backend/services/assistant_tools_student.py` | 716 | `Exception` | other | `confirm_student_removal` | INTENTIONAL |
| `backend/services/assistant_tools_student.py` | 734 | `Exception` | pass | `confirm_student_removal` | NEEDS_ALERT |
| `backend/services/assistant_tools_student.py` | 1037 | `Exception` | print | `import_student_data` | LEGACY |
| `backend/services/assistant_tools_student.py` | 342 | `Exception` | other | `_find_all_student_files` | LEGACY |
| `backend/services/assistant_tools_student.py` | 900 | `Exception` | pass | `import_student_data` | NEEDS_ALERT |
| `backend/services/assistant_tools_student.py` | 921 | `Exception` | return | `import_student_data` | INTENTIONAL |
| `backend/services/assistant_tools_student.py` | 938 | `Exception` | pass | `import_student_data` | NEEDS_ALERT |
| `backend/services/assistant_tools_student.py` | 972 | `Exception` | pass | `import_student_data` | NEEDS_ALERT |
| `backend/services/assistant_tools_student.py` | 990 | `Exception` | pass | `import_student_data` | NEEDS_ALERT |
| `backend/services/assistant_tools_student.py` | 1007 | `Exception` | pass | `import_student_data` | NEEDS_ALERT |
| `backend/services/assistant_tools_student.py` | 479 | `Exception` | append | `_execute_student_removal` | INTENTIONAL |
| `backend/services/correction_patterns.py` | 15 | `ImportError` | other | `<module>` | UNCATEGORIZED |
| `backend/services/document_generator.py` | 53 | `(ValueError, TypeError)` | return | `_hex_to_rgb` | INTENTIONAL |
| `backend/services/document_generator.py` | 81 | `Exception` | pass | `load_style` | LEGACY |
| `backend/services/document_generator.py` | 91 | `(ValueError, TypeError)` | other | `load_style` | INTENTIONAL |
| `backend/services/document_generator.py` | 97 | `(ValueError, TypeError)` | other | `load_style` | INTENTIONAL |
| `backend/services/document_generator.py` | 105 | `(ValueError, TypeError)` | other | `load_style` | INTENTIONAL |
| `backend/services/document_generator.py` | 338 | `Exception` | other | `create_document_docx` | LEGACY |
| `backend/services/document_generator.py` | 353 | `Exception` | other | `create_document_docx` | LEGACY |
| `backend/services/document_generator.py` | 368 | `Exception` | other | `create_document_docx` | LEGACY |
| `backend/services/document_generator.py` | 409 | `Exception` | other | `create_document_docx` | LEGACY |
| `backend/services/document_generator.py` | 422 | `Exception` | other | `create_document_docx` | LEGACY |
| `backend/services/document_generator.py` | 447 | `Exception` | other | `create_document_docx` | LEGACY |
| `backend/services/document_generator.py` | 463 | `Exception` | other | `create_document_docx` | LEGACY |
| `backend/services/document_generator.py` | 479 | `Exception` | other | `create_document_docx` | LEGACY |
| `backend/services/document_generator.py` | 494 | `Exception` | other | `create_document_docx` | LEGACY |
| `backend/services/document_generator.py` | 510 | `Exception` | other | `create_document_docx` | LEGACY |
| `backend/services/document_generator.py` | 525 | `Exception` | other | `create_document_docx` | LEGACY |
| `backend/services/document_generator.py` | 541 | `Exception` | other | `create_document_docx` | LEGACY |
| `backend/services/document_generator.py` | 553 | `Exception` | other | `create_document_docx` | LEGACY |
| `backend/services/document_generator.py` | 567 | `Exception` | other | `create_document_docx` | LEGACY |
| `backend/services/document_generator.py` | 579 | `Exception` | other | `create_document_docx` | LEGACY |
| `backend/services/elevenlabs_service.py` | 17 | `ImportError` | other | `<module>` | UNCATEGORIZED |
| `backend/services/elevenlabs_service.py` | 204 | `Exception` | pass | `close` | UNCATEGORIZED |
| `backend/services/elevenlabs_service.py` | 259 | `Exception` | pass | `_on_message` | UNCATEGORIZED |
| `backend/services/elevenlabs_service.py` | 227 | `Exception` | other | `_keepalive_loop` | UNCATEGORIZED |
| `backend/services/email_service.py` | 21 | `ImportError` | print | `<module>` | UNCATEGORIZED |
| `backend/services/email_service.py` | 133 | `Exception` | print + return | `send_email` | UNCATEGORIZED |
| `backend/services/grading_service.py` | 129 | `Exception` | log.debug | `load_teacher_config` | UNCATEGORIZED |
| `backend/services/grading_service.py` | 250 | `Exception` | log.error | `grade_student_submission` | UNCATEGORIZED |
| `backend/services/grading_service.py` | 85 | `ValueError` | pass | `grade_deterministic_question` | INTENTIONAL |
| `backend/services/mathpix_ocr.py` | 115 | `requests.exceptions.Timeout` | return | `image_to_latex` | UNCATEGORIZED |
| `backend/services/mathpix_ocr.py` | 123 | `requests.exceptions.HTTPError` | return | `image_to_latex` | UNCATEGORIZED |
| `backend/services/mathpix_ocr.py` | 133 | `Exception` | return | `image_to_latex` | UNCATEGORIZED |
| `backend/services/notebooklm_service.py` | 66 | `ImportError` | return | `_get_default_storage_path` | INTENTIONAL |
| `backend/services/notebooklm_service.py` | 106 | `ImportError` | raise | `login_browser` | INTENTIONAL |
| `backend/services/notebooklm_service.py` | 169 | `Exception` | pass | `cancel_login` | INTENTIONAL |
| `backend/services/notebooklm_service.py` | 173 | `Exception` | pass | `cancel_login` | INTENTIONAL |
| `backend/services/notebooklm_service.py` | 192 | `(json.JSONDecodeError, IOError)` | pass | `get_generation_state` | INTENTIONAL |
| `backend/services/notebooklm_service.py` | 810 | `Exception` | pass | `run_generation_thread` | NEEDS_ALERT |
| `backend/services/notebooklm_service.py` | 234 | `(json.JSONDecodeError, IOError)` | pass | `cleanup_stale_states` | INTENTIONAL |
| `backend/services/notebooklm_service.py` | 502 | `Exception` | print | `_create_notebook_with_sources` | NEEDS_ALERT |
| `backend/services/notebooklm_service.py` | 799 | `Exception` | append | `run_generation_thread` | INTENTIONAL |
| `backend/services/notebooklm_service.py` | 259 | `Exception` | pass | `cleanup_expired_materials` | NEEDS_ALERT |
| `backend/services/notebooklm_service.py` | 783 | `Exception` | append + raise | `run_generation_thread` | INTENTIONAL |
| `backend/services/oneroster_gradebook.py` | 95 | `Exception` | append + log.warning | `post_results` | UNCATEGORIZED |
| `backend/services/openai_tts_service.py` | 20 | `ImportError` | other | `<module>` | UNCATEGORIZED |
| `backend/services/openai_tts_service.py` | 216 | `queue.Empty` | other | `_worker_loop` | UNCATEGORIZED |
| `backend/services/openai_tts_service.py` | 248 | `Exception` | log.error | `_worker_loop` | UNCATEGORIZED |
| `backend/services/outlook_sender.py` | 140 | `Exception` | raise | `navigate_to_outlook` | INTENTIONAL |
| `backend/services/outlook_sender.py` | 152 | `Exception` | pass | `navigate_to_outlook` | LEGACY |
| `backend/services/outlook_sender.py` | 81 | `Exception` | pass | `navigate_to_outlook` | NEEDS_ALERT |
| `backend/services/outlook_sender.py` | 98 | `Exception` | pass | `navigate_to_outlook` | NEEDS_ALERT |
| `backend/services/outlook_sender.py` | 123 | `Exception` | raise | `navigate_to_outlook` | INTENTIONAL |
| `backend/services/outlook_sender.py` | 184 | `Exception` | pass | `send_email` | INTENTIONAL |
| `backend/services/outlook_sender.py` | 206 | `Exception` | other | `send_email` | INTENTIONAL |
| `backend/services/outlook_sender.py` | 229 | `Exception` | other | `send_email` | INTENTIONAL |
| `backend/services/outlook_sender.py` | 351 | `Exception` | pass | `main` | LEGACY |
| `backend/services/outlook_sender.py` | 327 | `Exception` | pass | `main` | LEGACY |
| `backend/services/outlook_sender.py` | 355 | `Exception` | pass | `main` | NEEDS_ALERT |
| `backend/services/outlook_sender.py` | 332 | `Exception` | pass | `main` | NEEDS_ALERT |
| `backend/services/outlook_sender.py` | 337 | `Exception` | pass | `main` | LEGACY |
| `backend/services/portal_grading.py` | 39 | `(OSError, ValueError)` | pass | `<module>` | INTENTIONAL |
| `backend/services/portal_grading.py` | 54 | `(ImportError, AttributeError)` | log.warning + return | `_import_from_assignment_grader` | INTENTIONAL |
| `backend/services/portal_grading.py` | 243 | `Exception` | log.error + return | `_safe_generate_feedback` | INTENTIONAL |
| `backend/services/portal_grading.py` | 257 | `Exception` | log.error | `_safe_save_results` | INTENTIONAL |
| `backend/services/portal_grading.py` | 278 | `Exception` | log.error | `_safe_update_submission` | INTENTIONAL |
| `backend/services/portal_grading.py` | 612 | `Exception` | log.error + log.info + pass | `run_portal_grading_thread` | NEEDS_ALERT |
| `backend/services/portal_grading.py` | 178 | `Exception` | append + log.error | `grade_written_questions` | INTENTIONAL |
| `backend/services/portal_grading.py` | 350 | `Exception` | pass | `run_portal_grading_thread` | LEGACY |
| `backend/services/portal_grading.py` | 361 | `Exception` | pass | `run_portal_grading_thread` | LEGACY |
| `backend/services/portal_grading.py` | 404 | `Exception` | pass | `run_portal_grading_thread` | LEGACY |
| `backend/services/portal_grading.py` | 568 | `Exception` | log.error | `run_portal_grading_thread` | NEEDS_ALERT |
| `backend/services/portal_grading.py` | 606 | `Exception` | log.error | `run_portal_grading_thread` | NEEDS_ALERT |
| `backend/services/portal_grading.py` | 315 | `Exception` | pass | `run_portal_grading_thread` | LEGACY |
| `backend/services/portal_grading.py` | 330 | `Exception` | pass | `run_portal_grading_thread` | LEGACY |
| `backend/services/portal_grading.py` | 626 | `Exception` | pass | `run_portal_grading_thread` | LEGACY |
| `backend/services/portal_grading.py` | 340 | `Exception` | pass | `run_portal_grading_thread` | LEGACY |
| `backend/services/portal_grading.py` | 496 | `ValueError` | pass | `run_portal_grading_thread` | INTENTIONAL |
| `backend/services/seo_service.py` | 28 | `ImportError` | return | `_get_anthropic_client` | UNCATEGORIZED |
| `backend/services/seo_service.py` | 50 | `json.JSONDecodeError` | return | `_call_haiku` | UNCATEGORIZED |
| `backend/services/seo_service.py` | 52 | `Exception` | return | `_call_haiku` | UNCATEGORIZED |
| `backend/services/slide_generator.py` | 281 | `Exception` | log.warning | `generate_slide_images` | UNCATEGORIZED |
| `backend/services/stem_grading.py` | 42 | `(ValueError, TypeError)` | pass | `_normalize_math_input` | INTENTIONAL |
| `backend/services/stem_grading.py` | 69 | `Exception` | pass | `_normalize_math_input` | INTENTIONAL |
| `backend/services/stem_grading.py` | 75 | `Exception` | pass | `_normalize_math_input` | INTENTIONAL |
| `backend/services/stem_grading.py` | 101 | `Exception` | pass | `_compare_numeric_forms` | INTENTIONAL |
| `backend/services/stem_grading.py` | 115 | `(TypeError, ValueError)` | pass | `_compare_numeric_forms` | INTENTIONAL |
| `backend/services/stem_grading.py` | 143 | `ImportError` | return | `check_math_equivalence` | INTENTIONAL |
| `backend/services/stem_grading.py` | 217 | `Exception` | return | `check_math_equivalence` | INTENTIONAL |
| `backend/services/stem_grading.py` | 345 | `ValueError` | pass | `check_cell_value` | INTENTIONAL |
| `backend/services/stem_grading.py` | 514 | `(ValueError, TypeError)` | append | `grade_coordinate_question` | INTENTIONAL |
| `backend/services/stem_grading.py` | 49 | `(ValueError, TypeError)` | pass | `_normalize_math_input` | INTENTIONAL |
| `backend/services/stem_grading.py` | 173 | `ValueError` | pass | `check_math_equivalence` | INTENTIONAL |
| `backend/services/stem_grading.py` | 207 | `(TypeError, ValueError)` | pass | `check_math_equivalence` | INTENTIONAL |
| `backend/services/visualization.py` | 608 | `Exception` | other | `create_function_graph` | UNCATEGORIZED |
| `backend/services/worksheet_generator.py` | 233 | `Exception` | other | `_embed_visual` | UNCATEGORIZED |
| `backend/staging.py` | 98 | `(json.JSONDecodeError, OSError)` | pass | `_load_manifest` | INTENTIONAL |
| `backend/staging.py` | 145 | `OSError` | other | `stage_files` | UNCATEGORIZED |
| `backend/staging.py` | 204 | `OSError` | other | `stage_files` | UNCATEGORIZED |
| `backend/staging.py` | 192 | `OSError` | other | `stage_files` | UNCATEGORIZED |
| `backend/staging.py` | 233 | `OSError` | pass | `stage_files` | INTENTIONAL |
| `backend/storage.py` | 139 | `Exception` | log.warning + return | `_file_load` | INTENTIONAL |
| `backend/storage.py` | 159 | `Exception` | log.error + return | `_file_save` | INTENTIONAL |
| `backend/storage.py` | 173 | `Exception` | log.error + return | `_file_delete` | INTENTIONAL |
| `backend/storage.py` | 243 | `Exception` | log.error + return | `_sb_load` | INTENTIONAL |
| `backend/storage.py` | 263 | `Exception` | log.error + return | `_sb_save` | INTENTIONAL |
| `backend/storage.py` | 282 | `Exception` | log.error + return | `_sb_delete` | INTENTIONAL |
| `backend/storage.py` | 301 | `Exception` | log.error + return | `_sb_list_keys` | INTENTIONAL |
| `backend/storage.py` | 319 | `Exception` | return | `_file_load_student_history` | INTENTIONAL |
| `backend/storage.py` | 332 | `Exception` | log.error + return | `_file_save_student_history` | INTENTIONAL |
| `backend/storage.py` | 353 | `Exception` | log.error + return | `_sb_load_student_history` | INTENTIONAL |
| `backend/storage.py` | 373 | `Exception` | log.error + return | `_sb_save_student_history` | INTENTIONAL |
| `backend/storage.py` | 576 | `Exception` | log.warning | `sync_all_to_cloud` | LEGACY |
| `backend/storage.py` | 601 | `Exception` | pass | `sync_all_to_cloud` | LEGACY |
| `backend/student_history.py` | 17 | `ImportError` | other | `<module>` | INTENTIONAL |
| `backend/student_history.py` | 27 | `ImportError` | other | `<module>` | INTENTIONAL |
| `backend/student_history.py` | 104 | `Exception` | print | `save_student_history` | NEEDS_ALERT |
| `backend/student_history.py` | 20 | `ImportError` | other | `<module>` | INTENTIONAL |
| `backend/student_history.py` | 30 | `ImportError` | other | `<module>` | INTENTIONAL |
| `backend/student_history.py` | 79 | `Exception` | pass | `load_student_history` | NEEDS_ALERT |
| `backend/supabase_resilient.py` | 74 | `AttributeError` | return | `_classify_operation` | UNCATEGORIZED |
| `backend/supabase_resilient.py` | 134 | `AttributeError` | other | `_resilient_execute` | UNCATEGORIZED |
| `backend/supabase_resilient.py` | 155 | `Exception` | log.error + log.warning + raise | `_resilient_execute` | INTENTIONAL |
| `backend/utils/audit.py` | 38 | `Exception` | pass | `audit_log` | NEEDS_ALERT |
| `backend/utils/audit.py` | 56 | `Exception` | pass | `audit_log` | NEEDS_ALERT |
| `backend/utils/audit.py` | 30 | `(ImportError, RuntimeError)` | other | `audit_log` | INTENTIONAL |
| `backend/utils/audit.py` | 45 | `ImportError` | other | `audit_log` | INTENTIONAL |
| `backend/utils/auth_decorators.py` | 48 | `Exception` | other | `wrapper` | UNCATEGORIZED |
| `backend/utils/errors.py` | 28 | `Exception` | log.exception + return | `wrapper` | INTENTIONAL |
| `backend/utils/logging_utils.py` | 16 | `RuntimeError` | other | `format` | UNCATEGORIZED |
| `backend/utils/logging_utils.py` | 32 | `RuntimeError` | other | `format` | UNCATEGORIZED |
