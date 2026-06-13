"""Tool definition schemas for the report / export / calendar / resource assistant tools.

Verbatim ``REPORT_TOOL_DEFINITIONS`` list, split out of the former single-file
module. The list literal is unchanged byte-for-byte.
"""

# ═══════════════════════════════════════════════════════
# TOOL DEFINITIONS
# ═══════════════════════════════════════════════════════

REPORT_TOOL_DEFINITIONS = [
    {
        "name": "create_focus_assignment",
        "description": "Create an assignment in Focus gradebook via browser automation. Requires VPortal credentials to be configured in Settings. The browser will open for the teacher to complete 2FA and verify before saving.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Assignment name"
                },
                "category": {
                    "type": "string",
                    "description": "Category (e.g., 'Assessments', 'Classwork')"
                },
                "points": {
                    "type": "integer",
                    "description": "Point value for the assignment"
                },
                "date": {
                    "type": "string",
                    "description": "Due date in MM/DD/YYYY format"
                },
                "description": {
                    "type": "string",
                    "description": "Assignment description"
                }
            },
            "required": ["name"]
        }
    },
    {
        "name": "export_grades_csv",
        "description": "Export grades as a Focus SIS-compatible CSV file. Generates per-period CSVs with Student ID and Score columns.",
        "input_schema": {
            "type": "object",
            "properties": {
                "assignment": {
                    "type": "string",
                    "description": "Assignment name to filter export (omit for all)"
                },
                "period": {
                    "type": "string",
                    "description": "Period to filter export (omit for all periods)"
                }
            }
        }
    },
    {
        "name": "lookup_student_info",
        "description": "Look up student contact and roster information. Returns student ID, local ID, grade level, period, course codes, student email, parent emails, parent phone numbers, 504 plan status, detailed contacts (up to 3 guardians with names, relationships, roles), and full student schedule (all periods with teachers and courses). Search by student name, ID, or period. Supports BATCH lookup via student_ids array — use this to get parent contacts for multiple students in one call (e.g., after querying grades to find failing students).",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_name": {
                    "type": "string",
                    "description": "Student name to search for (partial match, case-insensitive)"
                },
                "student_id": {
                    "type": "string",
                    "description": "Single student ID number to look up directly"
                },
                "student_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of student ID numbers for batch lookup. Use this to get contacts for multiple students at once."
                },
                "period": {
                    "type": "string",
                    "description": "List all students in this period (e.g., 'Period 1', '1')"
                }
            }
        }
    },
    {
        "name": "generate_worksheet",
        "description": "Generate a structured worksheet document (Cornell Notes, Fill-in-the-Blank, short-answer, vocabulary) from a reading or topic. Creates a downloadable Word document with an embedded invisible answer key for consistent AI grading. Automatically saved to Grading Setup. Use when the teacher asks to create a worksheet, assignment, or activity from a reading, textbook page, or topic.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Worksheet title (e.g., 'Cornell Notes - Expanding into Native American Lands')"
                },
                "worksheet_type": {
                    "type": "string",
                    "enum": ["cornell-notes", "fill-in-blank", "short-answer", "vocabulary"],
                    "description": "Type of worksheet to generate"
                },
                "vocab_terms": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "term": {"type": "string"},
                            "definition": {"type": "string", "description": "Expected definition (for answer key)"}
                        },
                        "required": ["term"]
                    },
                    "description": "Vocabulary terms with expected definitions"
                },
                "questions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "question": {"type": "string"},
                            "expected_answer": {"type": "string", "description": "Expected answer (for answer key)"},
                            "points": {"type": "integer", "default": 10},
                            "visual": {
                                "type": "object",
                                "description": "Optional visual element embedded above the answer box. Supports: math (LaTeX expression), number_line, coordinate_plane, graph (bar/line/scatter), box_plot, shape (triangle/rectangle). Example: {\"type\":\"math\",\"latex\":\"\\\\frac{1}{2}+\\\\frac{1}{3}\"} or {\"type\":\"shape\",\"shape_type\":\"triangle\",\"base\":8,\"height\":6} or {\"type\":\"graph\",\"graph_type\":\"bar\",\"categories\":[\"A\",\"B\"],\"values\":[3,7],\"title\":\"Sales\"}",
                                "properties": {
                                    "type": {"type": "string", "enum": ["math", "number_line", "coordinate_plane", "graph", "box_plot", "shape"]},
                                    "latex": {"type": "string", "description": "LaTeX expression (for math type)"},
                                    "font_size": {"type": "integer", "description": "Font size for math rendering"},
                                    "min": {"type": "number"}, "max": {"type": "number"},
                                    "points": {"type": "array", "items": {"type": "number"}},
                                    "labels": {"type": "object"}, "title": {"type": "string"},
                                    "blank": {"type": "boolean", "description": "If true, hide data for student to fill in"},
                                    "x_range": {"type": "array", "items": {"type": "number"}}, "y_range": {"type": "array", "items": {"type": "number"}},
                                    "graph_type": {"type": "string", "enum": ["bar", "line", "scatter"]},
                                    "categories": {"type": "array", "items": {"type": "string"}}, "values": {"type": "array", "items": {"type": "number"}},
                                    "x_data": {"type": "array", "items": {"type": "number"}}, "y_data": {"type": "array", "items": {"type": "number"}},
                                    "x_label": {"type": "string"}, "y_label": {"type": "string"},
                                    "data": {"type": "array", "items": {"type": "number"}}, "shape_type": {"type": "string", "enum": ["triangle", "rectangle"]},
                                    "base": {"type": "number"}, "height": {"type": "number"}, "width": {"type": "number"}
                                },
                                "required": ["type"]
                            }
                        },
                        "required": ["question"]
                    },
                    "description": "Questions with expected answers. Each question can include an optional 'visual' object to embed a math expression, graph, shape, or other visual above the answer box."
                },
                "summary_prompt": {
                    "type": "string",
                    "description": "Instruction for the summary section (e.g., 'Summarize the reading in 3-5 sentences...')"
                },
                "summary_key_points": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Key points that should appear in a good summary"
                },
                "total_points": {
                    "type": "integer",
                    "default": 100,
                    "description": "Total point value for the worksheet"
                },
                "style_name": {
                    "type": "string",
                    "description": "Name of a saved visual style to apply. Omit to use defaults."
                }
            },
            "required": ["title", "worksheet_type"]
        }
    },
    {
        "name": "generate_document",
        "description": "Generate a formatted Word document (.docx) with rich typography. Use for study guides, reference sheets, parent letters, lesson outlines, rubrics, or any document the teacher requests. NOT for gradeable worksheets (use generate_worksheet for those).",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Document title (main heading)"
                },
                "content": {
                    "type": "array",
                    "description": "Ordered content blocks. Text supports **bold** and *italic* markdown. Visual blocks (math, number_line, coordinate_plane, graph, box_plot, shape) embed images.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "enum": ["heading", "paragraph", "bullet_list", "numbered_list", "table", "math", "number_line", "coordinate_plane", "graph", "box_plot", "shape"]},
                            "text": {"type": "string", "description": "Text content (heading/paragraph)"},
                            "level": {"type": "integer", "description": "Heading level 1-3"},
                            "items": {"type": "array", "items": {"type": "string"}, "description": "List items"},
                            "rows": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}, "description": "Table rows (first = header)"},
                            "latex": {"type": "string", "description": "LaTeX math expression for type=math (e.g., '\\\\frac{-b \\\\pm \\\\sqrt{b^2-4ac}}{2a}')"},
                            "font_size": {"type": "integer", "description": "Font size for math rendering (default 20)"},
                            "min": {"type": "number", "description": "Min value for number_line"},
                            "max": {"type": "number", "description": "Max value for number_line"},
                            "points": {"type": "array", "items": {"type": "number"}, "description": "Points to plot. number_line: array of numbers. coordinate_plane: array of [x,y] pairs."},
                            "labels": {"type": "array", "items": {"type": "string"}, "description": "Labels for points or data sets"},
                            "title": {"type": "string", "description": "Title for visual blocks"},
                            "blank": {"type": "boolean", "description": "If true, create blank template for students to fill in"},
                            "x_range": {"type": "array", "items": {"type": "number"}, "description": "coordinate_plane: [min, max] for x-axis"},
                            "y_range": {"type": "array", "items": {"type": "number"}, "description": "coordinate_plane: [min, max] for y-axis"},
                            "graph_type": {"type": "string", "enum": ["bar", "line", "scatter"], "description": "Type of graph for type=graph"},
                            "categories": {"type": "array", "items": {"type": "string"}, "description": "Bar chart category labels"},
                            "values": {"type": "array", "items": {"type": "number"}, "description": "Bar chart values"},
                            "x_data": {"type": "array", "items": {"type": "number"}, "description": "X values for line/scatter graphs"},
                            "y_data": {"type": "array", "items": {"type": "number"}, "description": "Y values for line/scatter graphs"},
                            "x_label": {"type": "string", "description": "X-axis label for graphs"},
                            "y_label": {"type": "string", "description": "Y-axis label for graphs"},
                            "show_trend": {"type": "boolean", "description": "Show trend line on scatter plot"},
                            "data": {"type": "array", "items": {"type": "array", "items": {"type": "number"}}, "description": "box_plot: array of number arrays (one per data set)"},
                            "shape_type": {"type": "string", "enum": ["triangle", "rectangle"], "description": "Shape type for type=shape"},
                            "base": {"type": "number", "description": "Triangle base length"},
                            "height": {"type": "number", "description": "Shape height (triangle or rectangle)"},
                            "width": {"type": "number", "description": "Rectangle width"}
                        },
                        "required": ["type"]
                    }
                },
                "style_name": {
                    "type": "string",
                    "description": "Name of a saved visual style to apply. Omit to use defaults."
                },
                "save_to_builder": {
                    "type": "boolean",
                    "description": "If true, also save this document to Grading Setup for grading. Only set true if the teacher confirms they want it saved."
                }
            },
            "required": ["title", "content"]
        }
    },
    {
        "name": "save_document_style",
        "description": "Save a visual style (fonts, sizes, colors, spacing) so future documents of this type always look the same. Use when the teacher says they like how a document looks and want to reuse that formatting.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Style name (e.g., 'cornell-notes', 'parent-letter')"},
                "style": {
                    "type": "object",
                    "description": "Visual properties to save",
                    "properties": {
                        "title_font_name": {"type": "string"},
                        "title_font_size": {"type": "integer"},
                        "title_bold": {"type": "boolean"},
                        "heading_font_name": {"type": "string"},
                        "heading_sizes": {"type": "object"},
                        "body_font_name": {"type": "string"},
                        "body_font_size": {"type": "integer"},
                        "line_spacing": {"type": "number"},
                        "table_header_bg": {"type": "string"},
                        "accent_color": {"type": "string"}
                    }
                }
            },
            "required": ["name", "style"]
        }
    },
    {
        "name": "list_document_styles",
        "description": "List saved document visual styles. Use before generating a document to check if a matching style exists.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "generate_csv",
        "description": "Generate a downloadable spreadsheet file (XLSX or CSV). Use .xlsx for Wayground quizzes (required format) and any polished spreadsheet. Use .csv for simple data exports. When generating a Wayground quiz, use .xlsx and match the EXACT column structure from the Assessment Templates in your context (Question Text, Question Type, Option 1-5, Correct Answer, Time in seconds, Image Link, Answer explanation).",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Name for the file. Use .xlsx for Wayground and polished spreadsheets, .csv for simple exports. Defaults to .xlsx if no extension given."
                },
                "headers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Column headers for the CSV"
                },
                "rows": {
                    "type": "array",
                    "items": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "description": "Data rows. Each row is an array of string values matching the headers."
                }
            },
            "required": ["filename", "headers", "rows"]
        }
    },
    {
        "name": "recommend_next_lesson",
        "description": "Analyze student performance and recommend what the next lesson should focus on. Provides DIFFERENTIATED recommendations by class level (advanced/standard/support periods) with DOK-appropriate standards. Also identifies IEP/504 accommodation patterns — whether accommodated students struggled differently and what modifications may help. Cross-references rubric breakdowns, unanswered questions, developing skills, and curriculum standards. Use when teacher asks 'what should I teach next?', 'what do students need to work on?', or 'how should I differentiate the next lesson?'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "assignment_name": {
                    "type": "string",
                    "description": "Assignment to base recommendations on (partial match). Omit to use the most recent assignment."
                },
                "period": {
                    "type": "string",
                    "description": "Focus on a specific period (optional). Different periods may have different class levels and weaknesses."
                },
                "num_assignments": {
                    "type": "integer",
                    "description": "Number of recent assignments to analyze (default 1, max 5). More assignments = broader trend analysis."
                }
            }
        }
    },
    {
        "name": "get_standards",
        "description": "Look up curriculum standards for the teacher's state and subject. Returns ALL standards when no topic is specified, or filter by keyword. Use this to get full details (vocabulary, learning targets, essential questions) for standards. For a quick overview of all standards, use list_all_standards first.",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Topic keyword to filter standards (e.g., 'fractions', 'civil war', 'photosynthesis'). Matches against benchmark text, topics, and vocabulary."
                },
                "dok_max": {
                    "type": "integer",
                    "description": "Maximum DOK level to include (1-4). Use 2 for support classes, 3 for standard, 4 for advanced."
                }
            }
        }
    },
    {
        "name": "get_recent_lessons",
        "description": "List saved lesson plans, optionally filtered by unit name. Shows what has been taught recently — topics, standards covered, vocabulary, and objectives per day. Use this when the teacher asks to create a quiz or worksheet 'for this unit', 'for what we've been doing', or references past lessons.",
        "input_schema": {
            "type": "object",
            "properties": {
                "unit_name": {
                    "type": "string",
                    "description": "Filter by unit name (partial match, case-insensitive). Omit to show all units and recent lessons."
                }
            }
        }
    },
    {
        "name": "get_calendar",
        "description": "Read the teaching calendar — scheduled lessons and holidays for a date range. AUTHORITATIVE source for what the teacher is teaching. If scheduled_lessons is non-empty, those lessons ARE scheduled — always reference them by title and topic. Use when the teacher asks 'what am I teaching this week?', 'what's on my calendar?', 'generate a worksheet for Tuesday', or anything about their schedule. When asked about a specific day, set both start_date and end_date to that exact date.",
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "Start date in YYYY-MM-DD format. Defaults to today. For a specific day like 'Tuesday Feb 17', use '2026-02-17'."
                },
                "end_date": {
                    "type": "string",
                    "description": "End date in YYYY-MM-DD format. Defaults to 7 days from start. For a specific day, set equal to start_date."
                }
            }
        }
    },
    {
        "name": "schedule_lesson",
        "description": "Schedule a saved lesson plan onto the teaching calendar on a specific date. Use when the teacher says 'schedule the Revolution unit starting Monday', 'put Unit 3 on the calendar', or asks to plan out their week/month. For multi-day lessons, call this once per day with incrementing day_number and dates.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Date to schedule in YYYY-MM-DD format"
                },
                "unit": {
                    "type": "string",
                    "description": "Unit name the lesson belongs to"
                },
                "lesson_title": {
                    "type": "string",
                    "description": "Title of the lesson"
                },
                "day_number": {
                    "type": "integer",
                    "description": "Day number within the lesson (e.g., 1 for Day 1). Optional."
                },
                "lesson_file": {
                    "type": "string",
                    "description": "Path to lesson file like 'Unit Name/Lesson Title.json'. Optional."
                }
            },
            "required": ["date", "lesson_title"]
        }
    },
    {
        "name": "unschedule_lesson",
        "description": "Remove a lesson from the teaching calendar. Use when the teacher says 'remove the lesson on Friday', 'clear March 5th', or when correcting a schedule by removing the old entry before adding the new one.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Date to remove lesson(s) from in YYYY-MM-DD format"
                },
                "lesson_title": {
                    "type": "string",
                    "description": "Title of the specific lesson to remove. If omitted, removes ALL lessons on that date."
                }
            },
            "required": ["date"]
        }
    },
    {
        "name": "add_calendar_holiday",
        "description": "Add a holiday or break to the teaching calendar. Use when the teacher says 'add Spring Break', 'mark Monday as a holiday', or 'we're off next Friday'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Start date in YYYY-MM-DD format"
                },
                "name": {
                    "type": "string",
                    "description": "Name of the holiday or break (e.g., 'Spring Break', 'Teacher Workday')"
                },
                "end_date": {
                    "type": "string",
                    "description": "End date for multi-day breaks in YYYY-MM-DD format. Omit for single-day holidays."
                }
            },
            "required": ["date", "name"]
        }
    },
    {
        "name": "list_all_standards",
        "description": "Get a compact index of ALL curriculum standards for the teacher's subject. Returns every standard code with a short benchmark summary. Use this first to see what standards exist, then use get_standards with a topic keyword to get full details (vocabulary, learning targets, essential questions) for specific standards.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "list_resources",
        "description": "List all supporting documents uploaded by the teacher (curriculum guides, pacing calendars, rubrics, etc.). Shows filename, type, description, and size. Use this to discover what reference materials are available before reading specific ones with read_resource.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "read_resource",
        "description": "Read the full text content of an uploaded supporting document. The filenames are listed in the UPLOADED REFERENCE DOCUMENTS section of your context — pass the exact filename. Supports PDF, DOCX, DOC, TXT, and MD files. ALWAYS use this when the teacher mentions 'curriculum map', 'pacing guide', 'resources', or any uploaded document. Call this BEFORE answering any question about curriculum content, pacing, or uploaded materials.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Exact filename of the document to read (from list_resources results)"
                }
            },
            "required": ["filename"]
        }
    },
    {
        "name": "send_parent_emails",
        "description": "Generate a preview of personalized emails to parents/guardians via Outlook. Returns a preview with a confirmation action — messages are NOT sent by this tool. The teacher confirms sending via the UI. Supports template placeholders: {student_first_name}, {student_last_name}, {student_name}, {parent_name}, {period}, {teacher_name}, {subject_area}. Can target specific students or auto-find students with zero submissions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "email_subject": {
                    "type": "string",
                    "description": "Email subject line. Supports {student_first_name} etc."
                },
                "email_body": {
                    "type": "string",
                    "description": "Email body text. Use placeholders and newlines for paragraphs."
                },
                "student_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of student names to email parents of."
                },
                "period": {
                    "type": "string",
                    "description": "Email all parents in this period."
                },
                "zero_submissions": {
                    "type": "boolean",
                    "description": "If true, auto-target students with zero assignment submissions."
                }
            },
            "required": ["email_subject", "email_body"]
        }
    },
    {
        "name": "send_focus_comms",
        "description": "Generate a preview of email and/or SMS messages to parents via Focus SIS Communications. This is the DEFAULT and PREFERRED method for contacting parents — use this instead of send_parent_emails unless the teacher specifically asks for Outlook. Returns a preview with a confirmation action — messages are NOT sent by this tool. The teacher confirms sending via the UI. Supports template placeholders: {student_first_name}, {student_last_name}, {student_name}. When sending both email AND SMS, the SMS should be a short notification like 'Please check your email for a message regarding {subject}.' When sending SMS-only, omit email_body.",
        "input_schema": {
            "type": "object",
            "properties": {
                "email_subject": {
                    "type": "string",
                    "description": "Subject line for the email. Also used as the topic reference in SMS-only messages. Supports {student_first_name}, {student_last_name}, {student_name} placeholders."
                },
                "email_body": {
                    "type": "string",
                    "description": "Email body text. Omit to send SMS only. Supports template placeholders. Use newlines for paragraphs."
                },
                "sms_body": {
                    "type": "string",
                    "description": "SMS text (max 500 chars). If sending both email and SMS, use a short notification like 'Please check your email for a message about [topic] from [teacher].' If omitted, only email is sent."
                },
                "student_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of student names (Last, First format) to message parents of."
                },
                "period": {
                    "type": "string",
                    "description": "Send to all parents in this period."
                },
                "recipient_type": {
                    "type": "string",
                    "enum": ["Primary Contacts", "Students"],
                    "description": "Who receives the message. 'Primary Contacts' sends to parents (default). 'Students' sends directly to the student."
                }
            },
            "required": ["email_subject"]
        }
    },
    {
        "name": "confirm_and_send",
        "description": "Execute a pending email/SMS send after the teacher has confirmed the preview. Call this ONLY after showing a preview from send_focus_comms or send_parent_emails AND the teacher has confirmed they want to send it (e.g., 'yes', 'send it', 'looks good'). This triggers the actual Playwright automation to send the messages. Takes no parameters — it reads the pending payload automatically.",
        "input_schema": {
            "type": "object",
            "properties": {},
        }
    },
    {
        "name": "save_assignment_config",
        "description": "Save or update an assignment config in Grading Setup. Use when teacher asks to save an assignment, update point values, rename, change rubric type, or modify grading notes for an existing assignment. Can update individual fields without overwriting the entire config. IMPORTANT: If the teacher uploaded a document, always include document_text so the editor can display and mark it.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Assignment title (used as filename). If updating existing, must match exactly."
                },
                "document_text": {
                    "type": "string",
                    "description": "Full text content of the assignment document. Include this when saving a new assignment from an uploaded file so the editor can display it."
                },
                "questions": {
                    "type": "array",
                    "description": "Array of question objects: {id, type, prompt, points, marker, expected_answer}",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "type": {"type": "string", "enum": ["short_answer", "vocab_term", "written", "fill_in_blank"]},
                            "prompt": {"type": "string"},
                            "points": {"type": "integer"},
                            "marker": {"type": "string"},
                            "expected_answer": {"type": "string"}
                        },
                        "required": ["type", "prompt", "points"]
                    }
                },
                "totalPoints": {
                    "type": "integer",
                    "description": "Total points for the assignment"
                },
                "effortPoints": {
                    "type": "integer",
                    "description": "Points allocated for effort (default 15)"
                },
                "gradingNotes": {
                    "type": "string",
                    "description": "Grading notes / expected answers for the AI grader"
                },
                "rubricType": {
                    "type": "string",
                    "enum": ["standard", "cornell-notes", "fill-in-blank"],
                    "description": "Rubric type"
                },
                "customMarkers": {
                    "type": "array",
                    "description": "Section markers: [{start, points, type}]",
                    "items": {
                        "type": "object",
                        "properties": {
                            "start": {"type": "string"},
                            "points": {"type": "integer"},
                            "type": {"type": "string"}
                        }
                    }
                }
            },
            "required": ["title"]
        }
    },
]
