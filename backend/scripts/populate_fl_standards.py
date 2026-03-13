#!/usr/bin/env python3
"""
Populate Florida education standards JSON files from IXL public pages.

Usage:
  python -m backend.scripts.populate_fl_standards --subject us_history
  python -m backend.scripts.populate_fl_standards --all
  python -m backend.scripts.populate_fl_standards --all --dry-run
  python -m backend.scripts.populate_fl_standards --all --skip-enrich

Phases:
  1. Fetch codes + benchmarks from IXL HTML pages
  2. Merge with existing data (preserves current entries)
  3. AI enrichment via GPT-4o-mini (optional, skippable)
  4. Output complete JSON files
  5. Validation summary
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import requests
from lxml import html as lxml_html
from dotenv import load_dotenv

# ── Paths ──────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
DATA_DIR = SCRIPT_DIR.parent / "data"
CACHE_FILE = SCRIPT_DIR / ".enrichment_cache.json"

load_dotenv(PROJECT_ROOT / ".env", override=True)

# ── IXL URL mappings ──────────────────────────────────────────────────────────

IXL_PAGES = {
    "us_history": [
        ("https://www.ixl.com/standards/florida/social-studies/grade-8", "8"),
    ],
    "world_history": [
        # Existing file has SS.912.W codes (NGSSS, no IXL source).
        # IXL grade-6 has SS.6.W codes to supplement.
        ("https://www.ixl.com/standards/florida/social-studies/grade-6", "6"),
    ],
    "civics": [
        ("https://www.ixl.com/standards/florida/social-studies/grade-7", "7"),
        # High school page has SS.912.CG codes
        ("https://www.ixl.com/standards/florida/social-studies/high-school", "912"),
    ],
    "geography": [
        ("https://www.ixl.com/standards/florida/social-studies/grade-6", "6"),
        ("https://www.ixl.com/standards/florida/social-studies/grade-7", "7"),
        ("https://www.ixl.com/standards/florida/social-studies/grade-8", "8"),
    ],
    "spanish": [
        ("https://www.ixl.com/standards/florida/spanish?documentId=2020001279&subsetId=2020001910", "NM"),
        ("https://www.ixl.com/standards/florida/spanish?documentId=2020001279&subsetId=2020001909", "NH"),
    ],
    "english-ela": [
        (f"https://www.ixl.com/standards/florida/ela/grade-{n}", str(n))
        for n in range(6, 13)
    ],
    "math": [
        *[(f"https://www.ixl.com/standards/florida/math/grade-{n}", str(n)) for n in range(6, 9)],
        ("https://www.ixl.com/standards/florida/math/algebra-1", "912"),
        ("https://www.ixl.com/standards/florida/math/geometry", "912"),
        ("https://www.ixl.com/standards/florida/math/algebra-2", "912"),
        ("https://www.ixl.com/standards/florida/math/precalculus", "912"),
    ],
    "science": [
        *[(f"https://www.ixl.com/standards/florida/science/grade-{n}", str(n)) for n in range(6, 9)],
        ("https://www.ixl.com/standards/florida/science/biology", "912"),
        ("https://www.ixl.com/standards/florida/science/chemistry", "912"),
        ("https://www.ixl.com/standards/florida/science/physics", "912"),
        ("https://www.ixl.com/standards/florida/science/earth-space-science", "912"),
    ],
}

# Subject-specific code prefixes to filter relevant standards
SUBJECT_CODE_PREFIXES = {
    "us_history": ["SS."],
    "world_history": ["SS."],
    "civics": ["SS."],
    "geography": ["SS."],
    "english-ela": ["ELA.", "LAFS."],
    "math": ["MA."],
    "science": ["SC."],
    "spanish": ["WL."],
}

# For geography, only keep geography-related strand codes
GEOGRAPHY_STRANDS = {"G"}
# For civics, only keep civics-related strand codes
CIVICS_STRANDS = {"C", "CG"}
# For us_history, keep American history strands
US_HISTORY_STRANDS = {"A"}

# Subject-specific strand filtering (applied after prefix match)
# Key = subject, Value = set of valid strand letters for that subject
# None means accept all strands
SUBJECT_STRAND_FILTER = {
    "us_history": {"A"},           # SS.X.A only
    "civics": {"C", "CG", "E"},    # SS.X.C (NGSSS), SS.X.CG (B.E.S.T.), SS.X.E (Economics)
    "geography": {"G"},            # SS.X.G only
    "world_history": {"W"},        # SS.X.W only
}

# ── High School course mapping ────────────────────────────────────────────────

HS_COURSE_MAP = {
    # Math
    "MA.912.AR": "Algebra 1",
    "MA.912.NSO": "Algebra 1",
    "MA.912.F": "Algebra 1",
    "MA.912.GR": "Geometry",
    "MA.912.T": "Precalculus",
    "MA.912.LT": "Geometry",
    "MA.912.DP": "Algebra 2",
    "MA.912.C": "Precalculus",
    # Science
    "SC.912.L": "Biology",
    "SC.912.P": "Chemistry",
    "SC.912.E": "Earth/Space Science",
    "SC.912.N": "Biology",
    # Social Studies
    "SS.912.A": "American History",
    "SS.912.W": "World History",
    "SS.912.C": "American Government",
    "SS.912.E": "Economics",
    "SS.912.G": "World Geography",
    "SS.912.FL": "Financial Literacy",
    "SS.912.CG": "American Government",
}

# ── Code pattern for recognizing valid FL standard codes ──────────────────────

# Matches: SS.8.A.4.1, MA.6.NSO.1.1, ELA.6.R.1.1, SC.6.N.1.1, etc.
CODE_PATTERN = re.compile(
    r'^(SS|MA|ELA|SC|LAFS)\.\d{1,3}\.[A-Z]{1,4}\.\d+\.\d+'
    r'|^WL\.K12\.[A-Z]{2,3}\.\d+\.\d+'
)

# Also match parent codes like SS.68.AA.1 (strand headers), but we prefer full codes
PARENT_CODE_PATTERN = re.compile(
    r'^(SS|MA|ELA|SC|LAFS)\.\d{1,3}\.[A-Z]{1,4}\.\d+'
    r'|^WL\.K12\.[A-Z]{2,3}\.\d+'
)


def get_course_for_code(code):
    """Determine the HS course for a 912-level code."""
    for prefix, course in sorted(HS_COURSE_MAP.items(), key=lambda x: -len(x[0])):
        if code.startswith(prefix):
            return course
    return None


# ── Phase 1: Fetch from IXL ──────────────────────────────────────────────────

def fetch_ixl_page(url):
    """Fetch and parse an IXL standards page. Returns list of (code, benchmark)."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  WARNING: Failed to fetch {url}: {e}")
        return []

    tree = lxml_html.fromstring(resp.text)
    results = []
    seen_codes = set()

    # IXL uses <h4> tags containing standard codes and descriptions
    # Pattern: "SS.8.A.4.1 Examine the causes..." or "MA.6.NSO.1.1 Extend..."
    for el in tree.iter("h4", "span", "div", "p", "li"):
        text = el.text_content().strip()
        if not text or len(text) < 15:
            continue

        match = CODE_PATTERN.match(text)
        if match:
            code = match.group(0)
            if code in seen_codes:
                continue
            # Benchmark is everything after the code
            benchmark = text[len(code):].strip()
            # Clean up: remove leading punctuation/whitespace
            benchmark = benchmark.lstrip(":.- ").strip()
            # Clean HTML artifacts (collapsed whitespace from nested elements)
            benchmark = re.sub(r'\s{2,}', ' ', benchmark).strip()
            if benchmark:
                results.append((code, benchmark))
                seen_codes.add(code)

    return results


def filter_by_subject(codes_benchmarks, subject):
    """Filter extracted codes to only those relevant for this subject."""
    prefixes = SUBJECT_CODE_PREFIXES.get(subject, [])
    strand_filter = SUBJECT_STRAND_FILTER.get(subject)

    filtered = []
    for code, benchmark in codes_benchmarks:
        # Check prefix
        if not any(code.startswith(p) for p in prefixes):
            continue

        # Check strand filter if applicable
        if strand_filter is not None:
            parts = code.split(".")
            if len(parts) >= 3:
                strand = parts[2]
                if strand not in strand_filter:
                    continue

        filtered.append((code, benchmark))
    return filtered


def fetch_all_for_subject(subject):
    """Fetch all standards for a subject from IXL pages."""
    pages = IXL_PAGES.get(subject, [])
    if not pages:
        return {}

    all_codes = {}
    for url, grade_hint in pages:
        print(f"  Fetching {url} ...")
        raw = fetch_ixl_page(url)
        filtered = filter_by_subject(raw, subject)
        for code, benchmark in filtered:
            if code not in all_codes:
                all_codes[code] = benchmark
        print(f"    Found {len(filtered)} relevant codes (total unique: {len(all_codes)})")
        time.sleep(1)  # Be polite

    return all_codes


# ── Phase 2: Merge with existing ─────────────────────────────────────────────

def load_existing(subject):
    """Load existing standards file. Returns (list_of_entries, is_wrapped)."""
    filename = f"standards_fl_{subject}.json"
    filepath = DATA_DIR / filename
    if not filepath.exists():
        return [], False

    with open(filepath, "r") as f:
        data = json.load(f)

    if isinstance(data, list):
        return data, False
    elif isinstance(data, dict) and "standards" in data:
        return data["standards"], True
    return [], False


def merge_standards(existing_entries, new_codes):
    """Merge new codes into existing entries. Preserves existing, adds new."""
    existing_by_code = {}
    for entry in existing_entries:
        code = entry.get("code", "")
        if code:
            existing_by_code[code] = entry

    merged = []
    seen = set()

    # First, add all existing entries (preserving order and data)
    for entry in existing_entries:
        code = entry.get("code", "")
        if code and code not in seen:
            merged.append(entry)
            seen.add(code)

    # Then add new codes not in existing
    new_count = 0
    for code, benchmark in sorted(new_codes.items()):
        if code not in seen:
            merged.append({
                "code": code,
                "benchmark": benchmark,
                "_needs_enrichment": True,
            })
            seen.add(code)
            new_count += 1

    # Sort by code
    merged.sort(key=lambda s: _code_sort_key(s.get("code", "")))

    return merged, new_count


def _code_sort_key(code):
    """Sort key that handles numeric parts correctly."""
    parts = code.split(".")
    result = []
    for part in parts:
        try:
            result.append((0, int(part)))
        except ValueError:
            result.append((1, part))
    return result


# ── Phase 3: AI Enrichment ────────────────────────────────────────────────────

ENRICHMENT_FIELDS = [
    "topics", "dok", "item_specs", "essential_questions",
    "learning_targets", "vocabulary", "sample_assessment"
]

ENRICHMENT_PROMPT = """You are an expert on Florida education standards (NGSSS and B.E.S.T.).
Generate enrichment data for the following Florida education standards.

For each standard, provide a JSON object with these fields:
- "topics": array of 2-4 concise topic tags (strings)
- "dok": Webb's Depth of Knowledge level (integer 1-4)
- "item_specs": one paragraph describing how assessment items should be structured
- "essential_questions": array of 2-3 guiding questions (strings)
- "learning_targets": array of 2-4 "I can..." statements (strings)
- "vocabulary": array of 5-10 key terms (strings)
- "sample_assessment": one sample multiple-choice question as a string

Return a JSON array with one object per standard, in the same order as the input.
Only return the JSON array, no other text.

Standards to enrich:
"""


def load_cache():
    """Load enrichment cache."""
    if CACHE_FILE.exists():
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_cache(cache):
    """Save enrichment cache."""
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


def enrich_batch(standards_batch, cache):
    """Enrich a batch of standards via GPT-4o-mini. Returns enriched entries."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("  ERROR: OPENAI_API_KEY not set. Skipping enrichment.")
        return standards_batch

    # Build input for the prompt
    input_lines = []
    for s in standards_batch:
        input_lines.append(f'{s["code"]}: {s["benchmark"]}')

    prompt = ENRICHMENT_PROMPT + "\n".join(input_lines)

    try:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 4000,
            },
            timeout=60,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]

        # Parse JSON from response (handle markdown code blocks)
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r'^```(?:json)?\s*', '', content)
            content = re.sub(r'\s*```$', '', content)

        enrichments = json.loads(content)

        if len(enrichments) != len(standards_batch):
            print(f"  WARNING: Got {len(enrichments)} enrichments for {len(standards_batch)} standards")

        # Apply enrichments
        for i, s in enumerate(standards_batch):
            if i < len(enrichments):
                enrichment = enrichments[i]
                for field in ENRICHMENT_FIELDS:
                    if field in enrichment:
                        s[field] = enrichment[field]
                # Cache the enrichment
                cache[s["code"]] = {f: enrichment.get(f) for f in ENRICHMENT_FIELDS if f in enrichment}
            # Remove the flag
            s.pop("_needs_enrichment", None)

    except Exception as e:
        print(f"  ERROR enriching batch: {e}")
        # Don't remove the flag so it can be retried

    return standards_batch


def enrich_standards(standards, skip_enrich=False):
    """Enrich all standards that need it."""
    if skip_enrich:
        # Just fill in minimal defaults for unenriched standards
        for s in standards:
            if s.get("_needs_enrichment"):
                s.pop("_needs_enrichment", None)
                # Set empty defaults so the file is structurally valid
                for field in ENRICHMENT_FIELDS:
                    if field not in s:
                        if field == "dok":
                            s[field] = 2
                        elif field in ("topics", "essential_questions", "learning_targets", "vocabulary"):
                            s[field] = []
                        elif field in ("item_specs", "sample_assessment"):
                            s[field] = ""
        return standards

    cache = load_cache()

    # Separate: needs enrichment vs already has it
    # Check both the flag AND empty topics (in case --skip-enrich was run first)
    to_enrich = []
    for s in standards:
        needs = s.get("_needs_enrichment") or not s.get("topics")
        if needs:
            # Check cache first
            if s["code"] in cache:
                cached = cache[s["code"]]
                for field in ENRICHMENT_FIELDS:
                    if field in cached and cached[field] is not None:
                        s[field] = cached[field]
                s.pop("_needs_enrichment", None)
            else:
                to_enrich.append(s)

    if not to_enrich:
        return standards

    print(f"  Enriching {len(to_enrich)} standards via GPT-4o-mini...")

    # Process in batches of 5
    batch_size = 5
    for i in range(0, len(to_enrich), batch_size):
        batch = to_enrich[i:i + batch_size]
        codes = [s["code"] for s in batch]
        print(f"    Batch {i // batch_size + 1}/{(len(to_enrich) + batch_size - 1) // batch_size}: {codes[0]}...{codes[-1]}")
        enrich_batch(batch, cache)
        save_cache(cache)
        time.sleep(0.5)  # Rate limiting

    return standards


# ── Phase 4: Output ──────────────────────────────────────────────────────────

def write_output(subject, standards, dry_run=False):
    """Write the standards JSON file."""
    # Add course field for 912-level codes
    for s in standards:
        code = s.get("code", "")
        parts = code.split(".")
        if len(parts) >= 2 and parts[1] == "912":
            course = get_course_for_code(code)
            if course:
                s["course"] = course

    # Remove internal flags
    for s in standards:
        s.pop("_needs_enrichment", None)

    filename = f"standards_fl_{subject}.json"
    filepath = DATA_DIR / filename

    if dry_run:
        print(f"  [DRY RUN] Would write {len(standards)} standards to {filename}")
        return

    # Check existing format — use flat array for all files now for consistency
    # (load_standards handles both formats)
    with open(filepath, "w") as f:
        json.dump(standards, f, indent=2, ensure_ascii=False)

    print(f"  Wrote {len(standards)} standards to {filename}")


# ── Phase 5: Validation ──────────────────────────────────────────────────────

def validate_standards(standards, subject):
    """Validate a standards list. Returns list of warnings."""
    warnings = []

    # Check for duplicates
    codes = [s.get("code", "") for s in standards]
    seen = set()
    for code in codes:
        if code in seen:
            warnings.append(f"Duplicate code: {code}")
        seen.add(code)

    # Check required fields
    for s in standards:
        code = s.get("code", "")
        if not code:
            warnings.append("Entry missing 'code' field")
            continue
        if not s.get("benchmark"):
            warnings.append(f"{code}: missing 'benchmark'")

    # Check grades covered
    grades = set()
    for s in standards:
        code = s.get("code", "")
        parts = code.split(".")
        if len(parts) >= 2:
            grades.add(parts[1])

    return warnings, sorted(grades)


# ── Social Studies composite ──────────────────────────────────────────────────

def build_social_studies_composite(all_standards, dry_run=False):
    """Build the social_studies composite file from the 4 SS subject files."""
    composite = []
    seen = set()

    for subject in ["us_history", "civics", "geography", "world_history"]:
        entries = all_standards.get(subject, [])
        for entry in entries:
            code = entry.get("code", "")
            if code and code not in seen:
                composite.append(entry)
                seen.add(code)

    composite.sort(key=lambda s: _code_sort_key(s.get("code", "")))

    write_output("social_studies", composite, dry_run=dry_run)
    return composite


# ── Main ──────────────────────────────────────────────────────────────────────

ALL_SUBJECTS = ["us_history", "world_history", "civics", "geography",
                "english-ela", "math", "science", "spanish"]


def process_subject(subject, dry_run=False, skip_enrich=False):
    """Process a single subject end-to-end."""
    print(f"\n{'='*60}")
    print(f"Processing: {subject}")
    print(f"{'='*60}")

    # Phase 1: Fetch
    print("\n[Phase 1] Fetching from IXL...")
    new_codes = fetch_all_for_subject(subject)
    print(f"  Total unique codes from IXL: {len(new_codes)}")

    if not new_codes:
        print("  WARNING: No codes fetched. Using existing data only.")

    # Phase 2: Merge
    print("\n[Phase 2] Merging with existing data...")
    existing, was_wrapped = load_existing(subject)
    print(f"  Existing entries: {len(existing)}")
    merged, new_count = merge_standards(existing, new_codes)
    print(f"  New entries to add: {new_count}")
    print(f"  Total after merge: {len(merged)}")

    if dry_run:
        # Show sample new entries
        new_entries = [s for s in merged if s.get("_needs_enrichment")]
        if new_entries:
            print(f"\n  Sample new entries (first 5):")
            for s in new_entries[:5]:
                print(f"    {s['code']}: {s['benchmark'][:80]}...")
        write_output(subject, merged, dry_run=True)
        return merged

    # Phase 3: Enrich
    print("\n[Phase 3] Enrichment...")
    merged = enrich_standards(merged, skip_enrich=skip_enrich)

    # Phase 4: Output
    print("\n[Phase 4] Writing output...")
    write_output(subject, merged, dry_run=False)

    # Phase 5: Validate
    print("\n[Phase 5] Validation...")
    warnings, grades = validate_standards(merged, subject)
    if warnings:
        for w in warnings:
            print(f"  WARNING: {w}")
    else:
        print("  All validations passed.")
    print(f"  Grades covered: {', '.join(grades)}")

    return merged


def print_summary(all_standards):
    """Print a summary table."""
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"{'Subject':<20} | {'Count':>6} | Grades Covered")
    print(f"{'-'*20}-+-{'-'*6}-+-{'-'*30}")
    for subject in ALL_SUBJECTS:
        entries = all_standards.get(subject, [])
        _, grades = validate_standards(entries, subject)
        print(f"{subject:<20} | {len(entries):>6} | {', '.join(grades)}")

    if "social_studies" in all_standards:
        entries = all_standards["social_studies"]
        _, grades = validate_standards(entries, "social_studies")
        print(f"{'social_studies':<20} | {len(entries):>6} | {', '.join(grades)} (composite)")
    print()


def main():
    parser = argparse.ArgumentParser(description="Populate Florida standards data")
    parser.add_argument("--subject", choices=ALL_SUBJECTS, help="Process a single subject")
    parser.add_argument("--all", action="store_true", help="Process all subjects")
    parser.add_argument("--dry-run", action="store_true", help="Don't write files, just show what would happen")
    parser.add_argument("--skip-enrich", action="store_true", help="Skip AI enrichment (codes+benchmarks only)")
    args = parser.parse_args()

    if not args.subject and not args.all:
        parser.error("Specify --subject SUBJECT or --all")

    subjects = ALL_SUBJECTS if args.all else [args.subject]
    all_standards = {}

    for subject in subjects:
        result = process_subject(subject, dry_run=args.dry_run, skip_enrich=args.skip_enrich)
        all_standards[subject] = result

    # Build social studies composite
    if args.all or args.subject in ["us_history", "civics", "geography", "world_history"]:
        # Load any SS subjects not just processed
        for ss_subj in ["us_history", "civics", "geography", "world_history"]:
            if ss_subj not in all_standards:
                existing, _ = load_existing(ss_subj)
                all_standards[ss_subj] = existing

        print(f"\n{'='*60}")
        print("Building social_studies composite...")
        print(f"{'='*60}")
        composite = build_social_studies_composite(all_standards, dry_run=args.dry_run)
        all_standards["social_studies"] = composite

    print_summary(all_standards)


if __name__ == "__main__":
    main()
