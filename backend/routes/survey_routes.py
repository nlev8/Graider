"""
Parent Survey Routes for Graider.
Teachers create a survey link, parents click it and rate 4-5 questions.
Responses stored in published_assessments with content_type="survey".
"""
import random
from datetime import datetime
from flask import Blueprint, request, jsonify, make_response
from backend.supabase_client import get_supabase_or_raise as get_supabase

survey_bp = Blueprint('survey', __name__)

DEFAULT_QUESTIONS = [
    {
        "id": "communication",
        "text": "How well does the teacher communicate about your student's progress?",
        "type": "rating",
    },
    {
        "id": "availability",
        "text": "How available is the teacher when you have questions or concerns?",
        "type": "rating",
    },
    {
        "id": "support",
        "text": "How well does the teacher support your student's academic needs?",
        "type": "rating",
    },
    {
        "id": "expectations",
        "text": "How clearly does the teacher communicate classroom expectations and assignments?",
        "type": "rating",
    },
    {
        "id": "feedback",
        "text": "Is there anything else you'd like to share about your experience?",
        "type": "text",
    },
]


def _generate_survey_code():
    """Generate a unique 6-character survey code."""
    chars = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
    while True:
        code = ''.join(random.choices(chars, k=6))
        db = get_supabase()
        result = db.table('published_assessments').select('id').eq('join_code', code).execute()
        if len(result.data) == 0:
            return code


# ============ Teacher Endpoints ============

@survey_bp.route('/api/survey/create', methods=['POST'])
def create_survey():
    """Create a new parent survey and return the link."""
    data = request.json or {}
    teacher_name = data.get('teacher_name', 'Teacher')
    title = data.get('title', 'Parent Communication Survey')
    questions = data.get('questions', DEFAULT_QUESTIONS)

    code = _generate_survey_code()
    db = get_supabase()
    db.table('published_assessments').insert({
        'join_code': code,
        'title': title,
        'teacher_name': teacher_name,
        'assessment': {
            'content_type': 'survey',
            'questions': questions,
            'responses': [],
        },
        'settings': {
            'content_type': 'survey',
        },
        'is_active': True,
        'submission_count': 0,
    }).execute()

    return jsonify({
        'success': True,
        'join_code': code,
        'survey_url': f'/survey/{code}',
    })


@survey_bp.route('/api/survey/results')
def survey_results():
    """Get aggregate survey results for the teacher."""
    code = request.args.get('code')
    if not code:
        return jsonify({'error': 'Missing code parameter'}), 400

    db = get_supabase()
    result = db.table('published_assessments') \
        .select('assessment, title, submission_count') \
        .eq('join_code', code) \
        .execute()

    if not result.data:
        return jsonify({'error': 'Survey not found'}), 404

    record = result.data[0]
    assessment = record.get('assessment', {})
    responses = assessment.get('responses', [])
    questions = assessment.get('questions', [])

    # Aggregate ratings
    summary = {}
    for q in questions:
        qid = q['id']
        if q['type'] == 'rating':
            ratings = [r.get(qid) for r in responses if r.get(qid) is not None]
            summary[qid] = {
                'question': q['text'],
                'type': 'rating',
                'count': len(ratings),
                'average': round(sum(ratings) / len(ratings), 1) if ratings else 0,
                'distribution': {str(i): ratings.count(i) for i in range(1, 6)},
            }
        elif q['type'] == 'text':
            texts = [r.get(qid) for r in responses if r.get(qid)]
            summary[qid] = {
                'question': q['text'],
                'type': 'text',
                'count': len(texts),
                'responses': texts,
            }

    return jsonify({
        'title': record.get('title', 'Survey'),
        'total_responses': len(responses),
        'questions': summary,
    })


@survey_bp.route('/api/survey/list')
def list_surveys():
    """List all surveys created by the teacher."""
    db = get_supabase()
    result = db.table('published_assessments') \
        .select('join_code, title, submission_count, is_active, created_at') \
        .eq('settings->>content_type', 'survey') \
        .order('created_at', desc=True) \
        .execute()

    return jsonify({'surveys': result.data or []})


# ============ Parent-Facing Endpoints ============

@survey_bp.route('/survey/<code>')
def survey_page(code):
    """Serve the self-contained survey HTML page."""
    db = get_supabase()
    result = db.table('published_assessments') \
        .select('assessment, title, teacher_name, is_active') \
        .eq('join_code', code) \
        .execute()

    if not result.data:
        return make_response('<h1>Survey not found</h1>', 404)

    record = result.data[0]
    assessment = record.get('assessment', {})
    if assessment.get('content_type') != 'survey':
        return make_response('<h1>Not a survey</h1>', 400)
    if not record.get('is_active', True):
        return make_response('<h1>This survey is no longer accepting responses</h1>', 410)

    title = record.get('title', 'Parent Survey')
    teacher = record.get('teacher_name', 'Your Teacher')
    questions = assessment.get('questions', [])

    # Build questions HTML
    questions_html = ''
    for q in questions:
        if q['type'] == 'rating':
            stars = ''
            for i in range(1, 6):
                stars += f'''<label class="star-label">
                    <input type="radio" name="{q['id']}" value="{i}" required>
                    <span class="star" data-value="{i}">&#9733;</span>
                </label>'''
            questions_html += f'''
            <div class="question">
                <p class="q-text">{q['text']}</p>
                <div class="stars">{stars}</div>
                <div class="rating-labels"><span>Poor</span><span>Excellent</span></div>
            </div>'''
        elif q['type'] == 'text':
            questions_html += f'''
            <div class="question">
                <p class="q-text">{q['text']}</p>
                <textarea name="{q['id']}" rows="3" placeholder="Optional — share your thoughts..."></textarea>
            </div>'''

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f0f2f5; min-height: 100vh; display: flex; justify-content: center; padding: 20px; }}
.container {{ max-width: 560px; width: 100%; }}
.card {{ background: #fff; border-radius: 16px; box-shadow: 0 2px 12px rgba(0,0,0,0.08); padding: 32px; margin-bottom: 20px; }}
h1 {{ font-size: 1.5rem; color: #1a1a2e; margin-bottom: 4px; }}
.subtitle {{ color: #666; font-size: 0.95rem; margin-bottom: 24px; }}
.question {{ margin-bottom: 28px; }}
.q-text {{ font-size: 1rem; font-weight: 500; color: #1a1a2e; margin-bottom: 12px; line-height: 1.4; }}
.stars {{ display: flex; gap: 8px; justify-content: center; }}
.star-label {{ cursor: pointer; }}
.star-label input {{ display: none; }}
.star {{ font-size: 2.2rem; color: #ddd; transition: color 0.15s, transform 0.15s; display: block; }}
.star:hover, .star.active {{ color: #f59e0b; transform: scale(1.15); }}
.rating-labels {{ display: flex; justify-content: space-between; margin-top: 6px; font-size: 0.75rem; color: #999; padding: 0 12px; }}
textarea {{ width: 100%; border: 1.5px solid #e2e8f0; border-radius: 10px; padding: 12px; font-size: 0.95rem; font-family: inherit; resize: vertical; transition: border-color 0.2s; }}
textarea:focus {{ outline: none; border-color: #6366f1; }}
.btn {{ display: block; width: 100%; padding: 14px; background: linear-gradient(135deg, #6366f1, #8b5cf6); color: #fff; border: none; border-radius: 12px; font-size: 1.05rem; font-weight: 600; cursor: pointer; transition: transform 0.15s, box-shadow 0.15s; }}
.btn:hover {{ transform: translateY(-1px); box-shadow: 0 4px 16px rgba(99,102,241,0.35); }}
.btn:active {{ transform: translateY(0); }}
.btn:disabled {{ opacity: 0.6; cursor: not-allowed; transform: none; }}
.success {{ text-align: center; padding: 48px 32px; }}
.success-icon {{ font-size: 3rem; margin-bottom: 12px; }}
.success h2 {{ color: #1a1a2e; margin-bottom: 8px; }}
.success p {{ color: #666; }}
.anon-note {{ font-size: 0.8rem; color: #999; text-align: center; margin-top: 16px; }}
</style>
</head>
<body>
<div class="container">
    <div class="card" id="survey-form">
        <h1>{title}</h1>
        <p class="subtitle">From {teacher}</p>
        <form id="form">
            {questions_html}
            <button type="submit" class="btn" id="submit-btn">Submit Response</button>
        </form>
        <p class="anon-note">Your response is anonymous.</p>
    </div>
    <div class="card success" id="success" style="display:none;">
        <div class="success-icon">&#10003;</div>
        <h2>Thank you!</h2>
        <p>Your feedback has been submitted.</p>
    </div>
</div>
<script>
(function() {{
    // Star rating interaction
    document.querySelectorAll('.stars').forEach(function(group) {{
        var stars = group.querySelectorAll('.star');
        stars.forEach(function(star, idx) {{
            star.addEventListener('click', function() {{
                stars.forEach(function(s, i) {{
                    s.classList.toggle('active', i <= idx);
                }});
            }});
            star.addEventListener('mouseenter', function() {{
                stars.forEach(function(s, i) {{
                    s.style.color = i <= idx ? '#f59e0b' : '#ddd';
                }});
            }});
        }});
        group.addEventListener('mouseleave', function() {{
            stars.forEach(function(s) {{
                s.style.color = s.classList.contains('active') ? '#f59e0b' : '#ddd';
            }});
        }});
    }});

    document.getElementById('form').addEventListener('submit', function(e) {{
        e.preventDefault();
        var btn = document.getElementById('submit-btn');
        btn.disabled = true;
        btn.textContent = 'Submitting...';

        var data = {{}};
        var formData = new FormData(this);
        formData.forEach(function(value, key) {{
            var num = Number(value);
            data[key] = isNaN(num) || value === '' ? value : num;
        }});

        fetch('/api/survey/{code}/submit', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify(data),
        }}).then(function(r) {{ return r.json(); }}).then(function(res) {{
            if (res.success) {{
                document.getElementById('survey-form').style.display = 'none';
                document.getElementById('success').style.display = 'block';
            }} else {{
                btn.disabled = false;
                btn.textContent = 'Submit Response';
                alert(res.error || 'Something went wrong. Please try again.');
            }}
        }}).catch(function() {{
            btn.disabled = false;
            btn.textContent = 'Submit Response';
            alert('Network error. Please try again.');
        }});
    }});
}})();
</script>
</body>
</html>'''
    resp = make_response(html)
    resp.headers['Content-Type'] = 'text/html'
    return resp


@survey_bp.route('/api/survey/<code>/submit', methods=['POST'])
def submit_survey(code):
    """Submit a parent's survey response."""
    db = get_supabase()
    result = db.table('published_assessments') \
        .select('id, assessment, is_active') \
        .eq('join_code', code) \
        .execute()

    if not result.data:
        return jsonify({'error': 'Survey not found'}), 404

    record = result.data[0]
    if not record.get('is_active', True):
        return jsonify({'error': 'This survey is closed'}), 410

    assessment = record.get('assessment', {})
    if assessment.get('content_type') != 'survey':
        return jsonify({'error': 'Not a survey'}), 400

    response_data = request.json or {}
    response_data['submitted_at'] = datetime.utcnow().isoformat()

    responses = assessment.get('responses', [])
    responses.append(response_data)
    assessment['responses'] = responses

    db.table('published_assessments').update({
        'assessment': assessment,
        'submission_count': len(responses),
        'updated_at': datetime.utcnow().isoformat(),
    }).eq('id', record['id']).execute()

    return jsonify({'success': True})
