"""
SEO Optimization Routes
========================
AI-powered SEO analysis and content optimization endpoints.
Uses Claude Haiku for cost-efficient analysis.

Endpoints:
    POST /api/seo/optimize-meta     — Optimize meta tags for given content
    POST /api/seo/generate-schema   — Generate JSON-LD structured data
    POST /api/seo/analyze-content   — SEO score + suggestions
    POST /api/seo/suggest-blog-topics — Blog topic ideas for keyword coverage
"""
from flask import Blueprint, request, jsonify
from backend.services.seo_service import (
    optimize_meta, generate_schema, analyze_content, suggest_blog_topics
)

seo_bp = Blueprint('seo', __name__)


@seo_bp.route('/api/seo/optimize-meta', methods=['POST'])
def api_optimize_meta():
    """Optimize meta tags (title, description, keywords) for given page content."""
    data = request.json or {}
    content = data.get('content', '')
    page_url = data.get('page_url', '')
    if not content:
        return jsonify({"error": "content is required"}), 400
    result = optimize_meta(content, page_url)
    if "error" in result:
        return jsonify(result), 500
    return jsonify(result)


@seo_bp.route('/api/seo/generate-schema', methods=['POST'])
def api_generate_schema():
    """Generate JSON-LD structured data for a page."""
    data = request.json or {}
    if not data.get('title'):
        return jsonify({"error": "title is required"}), 400
    result = generate_schema(data)
    if "error" in result:
        return jsonify(result), 500
    return jsonify(result)


@seo_bp.route('/api/seo/analyze-content', methods=['POST'])
def api_analyze_content():
    """Analyze content for SEO score and get improvement suggestions."""
    data = request.json or {}
    content = data.get('content', '')
    target_keyword = data.get('target_keyword', '')
    if not content:
        return jsonify({"error": "content is required"}), 400
    result = analyze_content(content, target_keyword)
    if "error" in result:
        return jsonify(result), 500
    return jsonify(result)


@seo_bp.route('/api/seo/suggest-blog-topics', methods=['POST'])
def api_suggest_topics():
    """Suggest new blog topics based on existing content and target keywords."""
    data = request.json or {}
    existing_titles = data.get('existing_titles', [])
    domain_keywords = data.get('domain_keywords', None)
    result = suggest_blog_topics(existing_titles, domain_keywords)
    if "error" in result:
        return jsonify(result), 500
    return jsonify(result)
