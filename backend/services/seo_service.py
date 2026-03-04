"""
SEO Optimization Service
=========================
AI-powered SEO analysis and content optimization using Claude Haiku.
Provides meta tag optimization, schema generation, content analysis,
and blog topic suggestions.
"""
import json
import os


# ═══════════════════════════════════════════════════════
# HELPERS (same pattern as assistant_tools_ai.py)
# ═══════════════════════════════════════════════════════

HAIKU_MODEL = "claude-haiku-4-5-20251001"


def _get_anthropic_client():
    """Lazy-import anthropic and return a client, or None + error message."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None, "ANTHROPIC_API_KEY not configured"
    try:
        import anthropic
        return anthropic.Anthropic(api_key=api_key), None
    except ImportError:
        return None, "anthropic package not installed"


def _call_haiku(prompt, max_tokens=1500):
    """Make a single Haiku call. Returns parsed JSON dict or error dict."""
    client, err = _get_anthropic_client()
    if err:
        return {"error": err}
    try:
        response = client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        # Strip markdown fences if present
        if text.startswith("```"):
            first_nl = text.index("\n")
            last_fence = text.rfind("```")
            text = text[first_nl + 1:last_fence].strip()
        return json.loads(text)
    except json.JSONDecodeError:
        return {"error": "AI returned non-JSON response", "raw": text}
    except Exception as e:
        return {"error": f"AI call failed: {str(e)}"}


# ═══════════════════════════════════════════════════════
# SEO FUNCTIONS
# ═══════════════════════════════════════════════════════

def optimize_meta(content, page_url=""):
    """
    Takes page content text, returns optimized title, description, keywords.

    Args:
        content: The text content of the page
        page_url: Optional URL of the page for context

    Returns:
        dict with keys: title, description, keywords, og_title
    """
    if not content or not content.strip():
        return {"error": "content is required"}

    # Truncate to ~3000 chars to keep prompt size reasonable
    truncated = content.strip()[:3000]
    url_context = f"\nPage URL: {page_url}" if page_url else ""

    prompt = f"""You are an expert SEO specialist for EdTech websites. Analyze the following page content and generate optimized SEO meta tags.{url_context}

Page content:
---
{truncated}
---

Return a JSON object with:
- "title": SEO-optimized page title (50-60 characters, include primary keyword near the start)
- "description": Meta description (150-160 characters, compelling and keyword-rich, include a call to action)
- "keywords": Array of 10-15 relevant target keywords (mix of short-tail and long-tail)
- "og_title": Open Graph title variant (can differ slightly from title, more engaging for social sharing)

Focus on EdTech, AI grading, K-12 education, and teacher tools. Return ONLY valid JSON, no explanation."""

    return _call_haiku(prompt, max_tokens=800)


def generate_schema(page_info):
    """
    Takes page info dict, generates JSON-LD structured data.

    Args:
        page_info: dict with keys: type, title, description, url, published, faqs

    Returns:
        dict with key: json_ld containing the complete Schema.org markup
    """
    if not page_info.get("title"):
        return {"error": "title is required"}

    schema_type = page_info.get("type", "article")
    title = page_info.get("title", "")
    description = page_info.get("description", "")
    url = page_info.get("url", "")
    published = page_info.get("published", "")
    faqs = page_info.get("faqs", [])

    faqs_context = ""
    if faqs:
        faqs_context = f"\nFAQ items to include:\n{json.dumps(faqs, indent=2)}"

    prompt = f"""You are an expert in Schema.org structured data for SEO. Generate a complete JSON-LD structured data block for the following page.

Page type: {schema_type}
Title: {title}
Description: {description}
URL: {url}
Published date: {published}
Publisher: Graider (https://graider.live, logo: https://graider.live/logo.svg){faqs_context}

Generate a JSON object with a single key "json_ld" containing the complete @graph array with:
1. An Article (or WebPage) schema based on the page type
2. If FAQs are provided, include a FAQPage schema

Use @context "https://schema.org" and @graph array format.
Return ONLY valid JSON, no explanation."""

    return _call_haiku(prompt, max_tokens=2000)


def analyze_content(content, target_keyword=""):
    """
    Analyzes content for SEO score and provides suggestions.

    Args:
        content: The text content to analyze
        target_keyword: Optional primary keyword to optimize for

    Returns:
        dict with keys: score (0-100), factors, suggestions
    """
    if not content or not content.strip():
        return {"error": "content is required"}

    # Truncate to ~4000 chars for analysis
    truncated = content.strip()[:4000]
    keyword_context = f"\nTarget keyword: {target_keyword}" if target_keyword else ""

    prompt = f"""You are an SEO content analyst specializing in EdTech. Analyze the following content for SEO effectiveness.{keyword_context}

Content:
---
{truncated}
---

Evaluate and return a JSON object with:
- "score": Overall SEO score from 0-100
- "word_count": Approximate word count
- "factors": Array of objects, each with "name", "score" (0-100), and "detail". Evaluate these factors:
  - Keyword usage and density (if target keyword provided)
  - Heading structure (H1, H2, H3 usage)
  - Content length (ideal: 1500-2500 words for blog posts)
  - Readability (sentence length, paragraph length)
  - Internal linking opportunities
  - Meta-friendliness (does content have clear topic and summary potential?)
- "suggestions": Array of 3-5 specific, actionable improvement suggestions

Return ONLY valid JSON, no explanation."""

    return _call_haiku(prompt, max_tokens=1500)


def suggest_blog_topics(existing_titles, domain_keywords=None):
    """
    Given existing blog titles, suggests new topics for keyword coverage.

    Args:
        existing_titles: List of existing blog post titles
        domain_keywords: Optional list of target keywords in the domain

    Returns:
        dict with key: topics (array of topic suggestions)
    """
    if domain_keywords is None:
        domain_keywords = [
            "AI grading", "K-12", "teacher tools", "EdTech",
            "lesson planning", "rubric grading", "student feedback",
            "FERPA compliance", "IEP accommodations", "handwriting grading"
        ]

    titles_str = "\n".join(f"- {t}" for t in existing_titles) if existing_titles else "None yet"
    keywords_str = ", ".join(domain_keywords)

    prompt = f"""You are an SEO content strategist for an EdTech company called Graider (AI-powered grading and lesson planning for K-12 teachers).

Existing blog posts:
{titles_str}

Target domain keywords: {keywords_str}

Suggest 5 new blog post topics that would:
1. Fill keyword gaps not covered by existing posts
2. Target long-tail keywords with realistic search volume
3. Appeal to K-12 teachers searching for AI grading solutions
4. Support SEO for graider.live

Return a JSON object with key "topics" containing an array of objects, each with:
- "title": Suggested blog post title (SEO-optimized, 50-70 chars)
- "target_keyword": Primary long-tail keyword to target
- "search_intent": One of "informational", "commercial", "navigational"
- "estimated_difficulty": "low", "medium", or "high"
- "rationale": 1-2 sentence explanation of why this topic is valuable

Return ONLY valid JSON, no explanation."""

    return _call_haiku(prompt, max_tokens=1500)
