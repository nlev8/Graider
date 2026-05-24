"""Writing-style analysis for AI-detection / plagiarism signals.

Pure logic (regex + dict math, no LLM / I/O / Flask) extracted from
assignment_grader.py. Wave 7 Slice 1 (grading-engine decomposition).
"""
import re


def analyze_writing_style(text: str) -> dict:
    """
    Analyze writing style metrics from student text.
    Used to build a profile and detect AI-generated content.
    """
    if not text or len(text.strip()) < 20:
        return None

    # Clean text
    clean_text = text.strip()

    # Split into sentences (basic sentence detection)
    sentences = re.split(r'[.!?]+', clean_text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 3]

    # Split into words
    words = re.findall(r'\b[a-zA-Z]+\b', clean_text)
    if len(words) < 5:
        return None

    # Calculate metrics
    avg_word_length = sum(len(w) for w in words) / len(words)
    avg_sentence_length = len(words) / max(len(sentences), 1)

    # Vocabulary complexity (based on word length distribution)
    long_words = [w for w in words if len(w) > 7]
    complex_word_ratio = len(long_words) / len(words)

    # Check for specific patterns
    uses_contractions = bool(re.search(r"\b(don't|can't|won't|isn't|aren't|doesn't|didn't|wouldn't|couldn't|shouldn't|I'm|you're|they're|we're|it's|that's|what's|there's|here's)\b", clean_text, re.IGNORECASE))

    # Simple vs complex vocabulary indicators
    simple_words = ['the', 'a', 'an', 'is', 'was', 'are', 'were', 'it', 'they', 'he', 'she', 'we', 'you', 'i', 'and', 'but', 'or', 'so', 'because', 'like', 'just', 'really', 'very', 'good', 'bad', 'big', 'small']
    simple_count = sum(1 for w in words if w.lower() in simple_words)
    simple_ratio = simple_count / len(words)

    # Academic/AI indicator words
    academic_words = ['furthermore', 'therefore', 'consequently', 'however', 'nevertheless', 'moreover', 'subsequently', 'fundamental', 'significant', 'essentially', 'particularly', 'specifically', 'transforming', 'establishing', 'securing', 'trajectory', 'precedent', 'constitutional', 'acquisition', 'vital', 'expansion']
    academic_count = sum(1 for w in words if w.lower() in academic_words)

    # Calculate complexity score (1-10 scale)
    complexity_score = min(10, max(1,
        (avg_word_length - 3) * 1.5 +  # Word length contribution
        (avg_sentence_length / 5) +     # Sentence length contribution
        (complex_word_ratio * 10) +     # Complex words contribution
        (academic_count * 2) -          # Academic words add complexity
        (simple_ratio * 3)              # Simple words reduce complexity
    ))

    return {
        "avg_word_length": round(avg_word_length, 2),
        "avg_sentence_length": round(avg_sentence_length, 2),
        "word_count": len(words),
        "sentence_count": len(sentences),
        "complex_word_ratio": round(complex_word_ratio, 3),
        "simple_word_ratio": round(simple_ratio, 3),
        "academic_word_count": academic_count,
        "uses_contractions": uses_contractions,
        "complexity_score": round(complexity_score, 2)
    }


def compare_writing_styles(current_style: dict, historical_profile: dict) -> dict:
    """
    Compare current submission's writing style against student's historical profile.
    Returns deviation analysis and AI likelihood.
    """
    if not current_style or not historical_profile:
        return {"deviation": "unknown", "ai_likelihood": "unknown", "reason": "Insufficient data"}

    deviations = []

    # Check complexity score deviation
    hist_complexity = historical_profile.get("avg_complexity_score", 3.0)
    curr_complexity = current_style.get("complexity_score", 3.0)
    complexity_diff = curr_complexity - hist_complexity

    if complexity_diff > 3:
        deviations.append(f"Complexity jumped from {hist_complexity:.1f} to {curr_complexity:.1f}")

    # Check sentence length deviation
    hist_sent_len = historical_profile.get("avg_sentence_length", 8.0)
    curr_sent_len = current_style.get("avg_sentence_length", 8.0)
    sent_len_diff = curr_sent_len - hist_sent_len

    if sent_len_diff > 10:
        deviations.append(f"Sentence length jumped from {hist_sent_len:.1f} to {curr_sent_len:.1f} words")

    # Check for sudden academic vocabulary
    hist_academic = historical_profile.get("avg_academic_words", 0)
    curr_academic = current_style.get("academic_word_count", 0)

    if curr_academic > hist_academic + 2:
        deviations.append(f"Academic vocabulary increased significantly ({curr_academic} vs typical {hist_academic})")

    # Check word length deviation
    hist_word_len = historical_profile.get("avg_word_length", 4.0)
    curr_word_len = current_style.get("avg_word_length", 4.0)

    if curr_word_len - hist_word_len > 1.5:
        deviations.append(f"Word length increased from {hist_word_len:.1f} to {curr_word_len:.1f}")

    # Determine AI likelihood based on deviations
    if len(deviations) >= 3:
        ai_likelihood = "likely"
    elif len(deviations) >= 2:
        ai_likelihood = "possible"
    elif len(deviations) == 1 and complexity_diff > 4:
        ai_likelihood = "possible"
    else:
        ai_likelihood = "none"

    return {
        "deviation": "significant" if len(deviations) >= 2 else "minor" if len(deviations) == 1 else "none",
        "ai_likelihood": ai_likelihood,
        "deviations": deviations,
        "reason": "; ".join(deviations) if deviations else "Writing style consistent with history"
    }
