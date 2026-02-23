# AI Detection for Student Grading: Comprehensive Research Report

**Date**: February 2026
**Purpose**: Evaluate methods for consistent, accurate AI detection in K-12 grading across ELA, Social Studies, Science, and Math

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current State of AI Detection (2026)](#current-state)
3. [How Detection Tools Work Technically](#how-detection-works)
4. [Commercial Detection APIs for Integration](#commercial-apis)
5. [Open-Source / Hugging Face Models](#open-source-models)
6. [How Competing Grading Platforms Handle It](#competing-platforms)
7. [Linguistic Markers of AI-Generated Text](#linguistic-markers)
8. [Writing Style Forensics & Stylometry](#writing-style-forensics)
9. [Subject-Specific Detection Strategies](#subject-specific)
10. [Input Format & Environmental Controls](#input-format-controls)
11. [What Graider Currently Does](#what-graider-does)
12. [Gap Analysis & Recommendations](#recommendations)
13. [Sources](#sources)

---

## 1. Executive Summary <a name="executive-summary"></a>

**The hard truth**: No AI detection method is reliably accurate on its own. The best-performing commercial tool (Originality.ai) scores 98-100% on unedited AI text but accuracy drops dramatically on paraphrased, edited, or short content. At least 12 elite universities (Yale, Johns Hopkins, Northwestern) have disabled Turnitin's AI detection entirely due to false positive concerns.

**The industry is shifting** from "detect and punish" to "observe the process." The most promising approach for Graider is a **multi-signal scoring system** that combines:
- Linguistic pattern analysis (rule-based, no API cost)
- Writing style profiling against student history (already partially built)
- Grade-level vocabulary calibration by subject
- Optional API-based detection as a secondary signal
- Input format controls where possible (copy-paste detection, response text boxes)

No single technique is sufficient. The winning strategy is **layered signals with confidence scoring**, not binary flags.

---

## 2. Current State of AI Detection (2026) <a name="current-state"></a>

### The Arms Race Problem

Detection tools and evasion tools are in a perpetual arms race. "AI humanizer" tools (BypassGPT, Phrasly, Undetectable.ai, StealthWriter) can reduce detection rates by 65-99%. Adversarial paraphrasing guided by OpenAI-RoBERTa-Large reduces detection effectiveness by 64-99% across neural, watermark-based, and zero-shot detection approaches.

### False Positive Rates

- **ESL/ELL students**: 61.3% average false-positive rate on TOEFL essays. 19% of non-native speaker text unanimously misclassified as AI by 7 detectors
- **High-achieving students**: Formal, structured writing naturally triggers false positives
- **Students using grammar aids**: Grammarly/translation tools inflate AI probability scores
- **Racial disparities**: 20% of Black teens falsely accused of AI use vs. 7% of white teens

### University Abandonment

Universities disabling AI detection (2025-2026): Curtin University, University of Waterloo, University of Queensland, Yale, Johns Hopkins, Northwestern, and others. JISC (UK national AI center) advises institutions to move beyond detection tools.

### OpenAI Watermarking (Scrapped)

OpenAI built a watermarking system claimed to be 99.9% effective but abandoned it because:
- 30% of users would reduce usage
- Disproportionate impact on non-native speakers
- Simple paraphrasing defeats it
- Newer models (GPT-o3, GPT-o4 mini) appear to embed Narrow No-Break Space (NNBSP) characters as undocumented watermarks

### EU AI Act (August 2026)

Article 50 requires AI providers to mark AI-generated content in machine-readable format. Proposes multi-layered marking (metadata, watermarks, fingerprinting). Will require providers to implement detectors via API or UI.

---

## 3. How Detection Tools Work Technically <a name="how-detection-works"></a>

### Perplexity Analysis

Measures how "surprised" a language model is by text. AI-generated text has LOW perplexity (predictable); human text has HIGH perplexity (surprising/varied).

Formula: `PP = 2^(-1/N * SUM(log2 P(ti | t1...ti-1)))`

**Limitation**: Insufficient on its own. Brittle on domain/style shifts. Formal human writing has low perplexity too.

### Burstiness Analysis

Measures how much perplexity varies across a document. Human writing has HIGH burstiness (varied sentence structure); AI text has LOW burstiness (uniform pacing).

**Limitation**: Short texts lack enough variation to measure. ESL students naturally have low burstiness.

### Classifier-Based Detection

Train a neural network on examples of human vs. AI text. Most commercial tools use RoBERTa-based classifiers fine-tuned on human/AI text pairs.

**Limitation**: Models trained on GPT-3.5 output are "mostly useless" at detecting Claude, Gemini, or Llama output (per RAID benchmark). Must continuously retrain.

### Multi-Signal Architectures

GPTZero uses 7 components: Education Module, Burstiness, Perplexity, GPTZeroX, GPTZero Shield, Internet Text Search, Deep Learning. Weighted scores produce a final classification.

Ghostbuster (UC Berkeley) passes documents through a series of weaker language models and trains a classifier on combined features. Achieves 99.0 F1 across domains.

---

## 4. Commercial Detection APIs for Integration <a name="commercial-apis"></a>

| Service | API | Accuracy | Price | Min Text | Best For |
|---------|-----|----------|-------|----------|----------|
| **Originality.ai** | V3 REST API | 98-100% (RAID #1) | $0.01/100 words | ~50 words | Best accuracy-to-cost ratio |
| **GPTZero** | REST API | 85-95% real-world | $45/mo for 300K words | ~250 words | Education-focused, no data retention |
| **Copyleaks** | REST API | 99%+ claimed | $8.99-$74.99/mo | ~100 words | Multi-language (30+), LMS integrations |
| **Sapling** | REST API | ~97% claimed | $0.005/1K chars | Short OK | Cheapest per-character, HIPAA options |
| **Winston AI** | REST API | 86-99% | $10-18/mo | ~100 words | CMS integrations, Chrome extension |
| **Turnitin** | Institutional only | 92-100% | ~$3/student/yr | 150 words | Not available as standalone API |

### Recommendation for Graider

**Originality.ai** has the best independent benchmark scores (RAID #1) and offers pay-as-you-go pricing at $0.01/100 words — roughly $0.03-0.05 per student submission. For 30 students x 10 assignments = $9-15/semester. Could offer as a premium feature.

**Self-hosted models** (see next section) eliminate per-call costs entirely.

---

## 5. Open-Source / Hugging Face Models <a name="open-source-models"></a>

### Pre-Trained Detection Models

| Model | Repo | Size | Accuracy | Notes |
|-------|------|------|----------|-------|
| **RoBERTa-base OpenAI Detector** | `openai-community/roberta-base-openai-detector` | ~500MB | Moderate | Trained on GPT-2 only, outdated |
| **Fakespot AI Text Detection** | `fakespot-ai/roberta-base-ai-text-detection-v1` | ~500MB | Good | Fine-tuned RoBERTa for AI text |
| **Desklib AI Detector** | `desklib/ai-text-detector-v1.01` | ~500MB | Good | Multi-model training |
| **MAGE** | `yaful/MAGE` | Varies | 99.0 F1 | ACL 2024, strong cross-domain |
| **Ghostbuster** | Berkeley research | Lightweight | 99.0 F1 | Doesn't need target model probabilities |
| **Binoculars** | Research (2024) | Varies | High | Zero-shot detection, no training needed |

### Datasets for Training/Fine-Tuning

- **RAID**: 10M+ documents, 11 LLMs, 11 genres, 12 adversarial attacks
- **MAGE**: Human/AI text pairs with OOD test sets for GPT + paraphrased
- **M4**: Multi-generator, multi-domain, multi-lingual corpus
- **MGTPD**: 2.4M samples from various LLMs, multilingual
- **AI Text Detection Pile**: Long-form text/essays from GPT-2/3/ChatGPT

### Self-Hosting Feasibility

- **RoBERTa-base models**: ~500MB RAM, runs on CPU (no GPU needed), ~100ms inference
- **Can run on Railway**: Add as a Flask endpoint alongside existing backend
- **Zero marginal cost**: No per-call API fees after deployment
- **Limitation**: Pre-trained models are stale (trained on GPT-3.5 era text). Would need periodic fine-tuning on newer model outputs

### Python Libraries for Stylometric Analysis

| Library | Purpose | Install |
|---------|---------|---------|
| **TextDescriptives** | Readability, coherence, POS, dependency distance (spaCy-based) | `pip install textdescriptives` |
| **LexicalRichness** | TTR, MTLD, HD-D, vocd-D vocabulary diversity metrics | `pip install lexicalrichness` |
| **TRUNAJOD** | Text complexity, syntactic complexity, entity grids, cohesion | `pip install TRUNAJOD` |
| **textstat** | Flesch-Kincaid, Gunning Fog, SMOG, Coleman-Liau readability | `pip install textstat` |
| **spaCy** | NLP foundation for all above libraries | `pip install spacy` |

---

## 6. How Competing Grading Platforms Handle It <a name="competing-platforms"></a>

### Turnitin Clarity (TIME Best Invention 2025)

The industry-leading approach. Tracks the entire writing process:
- Records every keystroke, revision, editing decision
- Distinguishes typed vs. pasted text
- Creates version-history playback
- Tracks active writing time
- Piloting at UCLA and University of Arkansas (Spring 2026)

**Key insight**: Watches HOW text was created, not just analyzes the final output.

### Brisk Teaching (2,000+ schools, $15M raise)

"Inspect Writing" tool: process-oriented rather than binary detection. Shows how students draft, revise, and develop over time. 96% detection rate for GPT-4 generated content, drops to ~85% for hybrid content.

### Formative / GoFormative

- Copy-paste detection with persistent exclamation mark alert (even if student deletes and re-types)
- Timestamps every response opening, submission, and individual response
- LockDown Browser integration (Respondus)
- No text-analysis-based AI detection

### Google Classroom

- Native AI flags using algorithms for unnatural patterns
- Originality reports via Turnitin
- SynthID watermarking for Google AI-generated content (BETT 2026)
- GPTZero one-click integration, Pangram auto-scanning on submission

### Writable (HMH)

- Dual detection: internal AI detection + Turnitin integration
- Designed for Grades 3-12
- Anonymizes all writing submitted to OpenAI
- Districts configure which AI features are available

### Respondus LockDown Browser

- Prevents access to AI tools during exams (blocks ChatGPT, Gemini, Claude, Copilot, Meta AI)
- Webcam + audio + screen recording
- AI-powered facial detection for suspicious behavior
- Explicitly states: "detection works poorly with short answer responses" — relies on environmental control instead

### Securly (K-12 specific)

- First K-12 AI transparency solution (November 2025)
- Filters student AI prompts, tracks AI usage, safety alerts
- Manages 14 million school-issued devices, 75 million daily activities
- Free to all 3,000 schools/districts using Securly Filter

### Key Pattern: The Industry Shift

The dominant architectural trend is **away from "detect AI text" toward "observe the writing process."** Multi-layered defense combining:
1. Environmental controls (locked browsers)
2. Behavioral monitoring (keystroke tracking, timestamps)
3. Text analysis (AI detection algorithms)
4. Process documentation (revision history)

---

## 7. Linguistic Markers of AI-Generated Text <a name="linguistic-markers"></a>

### Wikipedia's "Signs of AI Writing" (Community-Maintained)

**Vocabulary Tells**:
- "delve" (25x increase since ChatGPT launch, dropped sharply in 2025)
- "underscore", "harness", "illuminate", "facilitate", "bolster"
- "tapestry", "realm", "beacon", "cacophony" (color words)
- "multifaceted", "pivotal", "crucial", "paramount"
- "it is important to note that..." (filler transition)

**Structural Tells**:
- Em dashes (---) used formulaically where humans use commas/colons
- Overly symmetrical bullet points
- Predictable connectors between paragraphs
- Perfect paragraph structure (topic sentence, evidence, conclusion, repeat)
- Equal weighting of all ideas regardless of importance

**Tone Tells**:
- Avoids contractions ("You will appreciate" vs "You'll love")
- "Importance inflation" — connects minor topics to grand themes
- Perpetually balanced perspective, reluctant to take a stance
- No personal anecdotes, emotional appeals, or unique insights
- Absence of common student errors appropriate for age

### Grade-Level Vocabulary Expectations (Lexile Framework)

| Grade | Lexile Range | Expected Writing Style |
|-------|-------------|----------------------|
| 6 | 855L-1165L | Simple sentences, informal tone, basic transitions, frequent misspellings |
| 7 | 925L-1235L | Slightly more complex, still informal, limited academic vocabulary |
| 8 | 985L-1295L | Emerging formality, some academic words, occasional complex sentences |
| 9 | 1080L-1335L | More sophisticated, growing vocabulary, multi-clause sentences |
| 10 | 1185L-1385L | Academic writing developing, discipline-specific vocabulary |
| 11-12 | 1300L+ | College-level complexity, analytical writing, nuanced arguments |

**AI text typically writes at college-level regardless of grade assignment** — this is a primary detection signal.

### Concrete Detection Rules (Implementable)

1. **Vocabulary sophistication mismatch**: If grade 6 student uses "fundamentally altered", "constitutional acquisition", "geopolitical trajectory" — flag
2. **No contractions**: AI rarely uses "don't", "isn't", "they're" — students almost always do
3. **Zero spelling/grammar errors**: Perfectly polished text from a student who typically makes errors — flag
4. **Hedging phrases**: "It is important to note", "furthermore", "moreover", "consequently" — uncommon in student writing before grade 10
5. **Em dash overuse**: AI uses em dashes 3-5x more than student writers
6. **Uniform sentence length**: Standard deviation of sentence length < 3 words suggests AI
7. **Absence of first person**: Students naturally write "I think", "I believe" — AI often avoids this
8. **Definition precision**: "exclusive possession or control of the supply of or trade in a commodity" for "monopoly" — obviously copied/AI

---

## 8. Writing Style Forensics & Stylometry <a name="writing-style-forensics"></a>

### Building Student Writing Profiles

**Metrics to track per student** (across assignments):
- Average sentence length (words)
- Sentence length standard deviation (burstiness proxy)
- Average word length (characters)
- Vocabulary richness (Type-Token Ratio, MTLD)
- Academic word frequency
- Contraction usage rate
- First-person pronoun frequency
- Spelling error rate
- Readability score (Flesch-Kincaid)
- Complexity score (composite)

**Deviation detection**: When a new submission's metrics deviate significantly from the student's historical profile (e.g., complexity jumps from 3.5 to 8.2), flag for review.

### Keystroke & Behavioral Analysis

- **TypeNet** (LSTM neural network): Authenticates users by typing speed, rhythm, key press duration
- **Keystroke logs**: Can predict whether text was written or transcribed with 99% accuracy (Educational Data Mining 2024)
- **Copy-paste detection**: Formative flags any paste event with a persistent indicator
- **Burst writing detection**: Large chunks of text appearing instantly (vs. gradual typing)

### Process-Based Detection (Most Promising Approach)

**Turnitin Clarity model** (what Graider should aspire to):
1. Record when text appears in a response field
2. Track whether text was typed character-by-character or pasted in bulk
3. Measure time-on-task vs. word count produced
4. Flag "burst writes" — 200+ words appearing in under 30 seconds
5. Compare revision patterns against student's typical editing behavior

**Google Docs revision history**: If students submit via Google Docs, the edit history shows exactly how text evolved. Some schools already use this for manual verification.

---

## 9. Subject-Specific Detection Strategies <a name="subject-specific"></a>

### ELA (English Language Arts)

**Most detectable**: Long-form essays, creative writing, literary analysis
- Full text analysis (perplexity, burstiness, vocabulary) works best here
- Compare writing voice to in-class samples
- AI struggles with genuine personal voice and specific textual references
- Flag: perfectly structured 5-paragraph essay from a student who typically writes 2-3 paragraphs

**Strategies**:
- Require specific textual citations from assigned readings (AI can't reference the exact page/paragraph)
- Ask for personal connections ("How does this relate to your own experience?")
- In-class writing baseline for comparison

### Social Studies / History

**Cornell Notes & Summaries** (Graider's primary use case):
- Template prompt + student answer on same line (the bug we just fixed)
- AI summaries tend to be balanced and comprehensive; student summaries are often incomplete, one-sided, or focused on what interested them
- Dictionary-perfect definitions = plagiarism flag (students paraphrase imperfectly)
- AI produces "textbook-quality" analysis; students produce messy, opinion-laden analysis

**DBQ (Document-Based Questions)**:
- AI can't reference specific documents from a provided packet by number/title
- Student-specific factual errors are actually authenticity markers
- Suspiciously correct and comprehensive answers from struggling students = flag

**Vocabulary Terms**:
- Short definitions (<15 words) are too brief for meaningful AI detection
- Flag only when definitions match dictionary/Wikipedia verbatim
- "exclusive possession or control of the supply of or trade in a commodity" = copied
- "when one company controls everything" = authentic student language

### Science

**Lab Reports**:
- AI produces generic lab report language; students include specific observations
- "The data showed a clear trend" (AI) vs "our group got 3.2, 3.5 and 3.1 so it went up a little" (student)
- Procedural descriptions that reference actual classroom equipment/setup are authentic
- Hypothesis writing with age-inappropriate sophistication = flag

**Data Analysis**:
- AI explanations are comprehensive and accurate; student explanations focus on obvious patterns
- Students reference their specific data values; AI generates plausible but generic analysis

### Math

**Most resistant to AI detection concerns**:
- Show-your-work problems: handwritten steps are inherently authentic
- Word problem explanations: AI produces clean logical reasoning; students show messy thinking
- Math solver tools (Photomath, Mathway) are a separate concern from ChatGPT
- Proofs and reasoning can be checked for AI patterns but are short enough to limit detection accuracy

**Strategies for Math**:
- Require handwritten work (scanned/photographed) when possible
- Check if explanation language matches the student's typical verbal reasoning level
- Step-by-step work that skips obvious steps (expert behavior) from a struggling student = flag

### Cross-Subject Patterns

| Signal | ELA Weight | Social Studies Weight | Science Weight | Math Weight |
|--------|-----------|---------------------|---------------|------------|
| Vocabulary sophistication | High | High | Medium | Low |
| Sentence structure uniformity | High | Medium | Medium | Low |
| Academic word frequency | High | High | Medium | Low |
| Contraction absence | Medium | Medium | Low | N/A |
| Perfect grammar | Medium | Medium | Low | N/A |
| Definition precision | Low | High | High | Low |
| Personal voice absence | High | Medium | Low | N/A |
| Grade-level mismatch | High | High | Medium | Medium |

---

## 10. Input Format & Environmental Controls <a name="input-format-controls"></a>

### Response Text Boxes (In-App Typing)

**Advantages**:
- Can detect copy-paste events (Formative's approach)
- Can track keystroke timing and typing cadence
- Can measure time-on-task
- Can flag "burst writes" (large text appearing instantly)
- Creates a controlled environment

**Disadvantages**:
- Requires students to type directly in Graider (major UX change)
- Students may prefer typing in Word/Docs and pasting
- Not viable for handwritten assignments (Graider's current workflow)

**Recommendation for Graider**: Add optional "Secure Response Mode" for high-stakes assignments. In this mode:
- Students type responses directly in a text box
- Copy-paste is detected and flagged (not blocked — blocking frustrates students)
- Time-on-task is recorded
- Typing cadence metadata is stored

### File Format Considerations

| Format | AI Detection Viability | Notes |
|--------|----------------------|-------|
| **.docx (Word)** | Good | Full text extraction, revision history possible, metadata available |
| **.pdf** | Good | Text extraction works, but no revision history |
| **Google Docs** | Excellent | Full revision history, edit timestamps, version comparison |
| **Handwritten (scanned)** | Excellent for authenticity | Inherently hard to AI-generate; OCR quality varies |
| **Images/Photos** | Excellent for authenticity | Handwritten = authentic by nature; typed then photographed = same as .docx |
| **Plain text** | Moderate | No metadata, no revision history |

**Key insight**: Handwritten submissions are the most resistant to AI cheating. Scanned handwriting requires extra effort to type into ChatGPT and then re-handwrite. The effort barrier alone deters most students.

**Recommendation**: For high-stakes assignments, recommend teachers assign handwritten work. For typed assignments, .docx format preserves metadata (author, creation date, revision time) that can provide authenticity signals.

### NNBSP Watermark Detection

OpenAI's newer models embed Narrow No-Break Space (U+202F) characters in generated text. This is a zero-cost detection signal:

```python
def check_nnbsp_watermark(text):
    """Check for OpenAI's undocumented NNBSP watermark."""
    nnbsp_count = text.count('\u202f')
    if nnbsp_count > 0:
        return {"detected": True, "count": nnbsp_count, "signal": "high"}
    return {"detected": False}
```

This is a **free, deterministic signal** with zero false positives (students don't type NNBSP characters). Should be implemented immediately.

---

## 11. What Graider Currently Does <a name="what-graider-does"></a>

### Existing AI Detection Pipeline

Graider already has a substantial multi-layer system:

1. **Parallel Detection Agent** (`detect_ai_plagiarism()`): GPT-4o-mini based classifier that analyzes student responses for AI patterns and plagiarism. Returns flag (none/unlikely/possible/likely) with confidence 0-100.

2. **Writing Style Profiling** (`analyze_writing_style()`): Computes complexity metrics (avg word length, sentence length, complex word ratio, academic word count, contraction usage, complexity score 1-10).

3. **Historical Comparison** (`compare_writing_styles()`): Compares current submission against student's historical profile. Flags when complexity jumps >3 points, sentence length jumps >10 words, or academic vocabulary increases significantly.

4. **Profile Accumulation** (`update_writing_profile()`): Maintains running averages across assignments. Only updates when submission isn't flagged as AI.

5. **Preprocessing** (`preprocess_for_ai_detection()`): Strips template text, question prompts, and fill-in-blank scaffolding. Filters to substantive written content only.

6. **Score Caps**: AI "likely" = max 50, AI "possible" = max 65, Plagiarism "likely" = max 50. Both AI + plagiarism = max 40.

7. **FITB Exemption**: Fill-in-blank answers correctly exempt from detection.

8. **Trusted Students**: Teacher can mark students to skip detection.

### Current Gaps

1. **No copy-paste detection**: Can't tell if text was typed or pasted
2. **No time-on-task tracking**: No behavioral signals
3. **Detection relies on GPT-4o-mini judgment**: Subjective, inconsistent, costs money per call
4. **No NNBSP watermark check**: Free signal not being captured
5. **Writing style metrics are basic**: No readability scores, no vocabulary diversity (MTLD/HD-D), no syntactic complexity
6. **No grade-level calibration**: Same detection criteria for grade 6 and grade 12
7. **No subject-specific tuning**: Same approach for ELA essays and Social Studies vocabulary
8. **Academic word list is small**: Only 21 words in the detection list
9. **No em-dash detection**: Documented AI tell not being checked
10. **No contraction analysis as detection signal**: Present in style analysis but not used for detection

---

## 12. Gap Analysis & Recommendations <a name="recommendations"></a>

### Tier 1: Quick Wins (No API cost, rule-based)

**A. NNBSP Watermark Detection**
- Check for `\u202f` characters in submitted text
- Zero false positives, free, deterministic
- Implementation: ~10 lines of code

**B. Expand Academic/AI Word List**
Current list has 21 words. Wikipedia's AI writing guide documents dozens more:
```
delve, underscore, harness, illuminate, facilitate, bolster,
tapestry, realm, beacon, cacophony, multifaceted, pivotal,
crucial, paramount, nuanced, landscape, foster, robust,
comprehensive, intricate, notably, leveraging, streamline,
encompass, groundbreaking, innovative, holistic, synergy
```

**C. Em-Dash Frequency Check**
AI uses em dashes 3-5x more than student writers. Count `\u2014` characters relative to sentence count.

**D. Contraction Absence Flag**
If a student's historical writing uses contractions (>5% of sentences) but current submission uses zero, flag as suspicious.

**E. Grade-Level Vocabulary Calibration**
Map Lexile ranges to expected complexity scores:
- Grade 6: complexity 2-4 expected, >6 suspicious
- Grade 8: complexity 3-5 expected, >7 suspicious
- Grade 10: complexity 4-7 expected, >8.5 suspicious
- Grade 12: complexity 5-8 expected, >9 suspicious

**F. Sentence Length Uniformity Check**
Calculate standard deviation of sentence lengths. SD < 3 words across 5+ sentences = low burstiness = AI flag.

### Tier 2: Enhanced Stylometry (Python libraries, no API cost)

**A. Install `textstat` for Readability Scoring**
- Flesch-Kincaid Grade Level: If output grade level is 5+ above student's actual grade, flag
- Coleman-Liau Index: Cross-reference with Lexile expectations
- ~1 line: `textstat.flesch_kincaid_grade(text)`

**B. Install `lexicalrichness` for Vocabulary Diversity**
- MTLD (Measure of Textual Lexical Diversity): AI text has consistently high MTLD; student text varies
- Type-Token Ratio: Unusually high TTR for a student's grade level = flag

**C. Enhanced Writing Profile Metrics**
Add to `analyze_writing_style()`:
- Readability grade level (Flesch-Kincaid)
- Vocabulary diversity (MTLD)
- First-person pronoun frequency (`I`, `me`, `my` / total words)
- Contraction frequency
- Em-dash count
- Spelling error estimate (basic: words not in common dictionary)

### Tier 3: Structural Improvements

**A. Composite AI Confidence Score**
Instead of binary flags, compute a weighted confidence score from multiple signals:

```
ai_confidence = (
    vocabulary_mismatch_score * 0.20 +
    style_deviation_score * 0.20 +
    linguistic_markers_score * 0.15 +  # em dashes, hedging, no contractions
    grade_level_mismatch_score * 0.15 +
    watermark_detection_score * 0.10 +
    sentence_uniformity_score * 0.10 +
    api_detection_score * 0.10  # if using external API
)
```

Thresholds: >0.7 = "likely", >0.5 = "possible", >0.3 = "unlikely", <0.3 = "none"

**B. Subject-Specific Detection Weights**
Apply different weights per subject (see table in Section 9). ELA weights vocabulary and voice heavily; Math weights almost nothing.

**C. Per-Section Detection**
Run detection on each section independently (not the whole document). A student might write their own notes but AI-generate their summary. Section-level detection catches this.

### Tier 4: Premium Features (API cost or major architecture change)

**A. External API Integration (Originality.ai)**
- $0.01/100 words, highest RAID benchmark accuracy
- Offer as a premium "Enhanced Detection" toggle
- Only run on submissions that score >0.3 on the local confidence score (reduce API calls)

**B. Self-Hosted Hugging Face Model**
- Deploy `fakespot-ai/roberta-base-ai-text-detection-v1` alongside Flask backend
- ~500MB RAM, runs on CPU, ~100ms inference
- Zero marginal cost after deployment
- Limitation: needs periodic retraining on newer model outputs

**C. Copy-Paste Detection (Response Text Boxes)**
- Add optional "Secure Response" mode for typed assignments
- Track paste events with JavaScript `paste` event listener
- Record time-on-task and typing speed
- Flag responses that appear instantly without typing activity

**D. Google Docs Revision History Analysis**
- If students submit Google Docs links, use Google Docs API to pull revision history
- Analyze edit timeline for burst-write patterns
- Compare typed vs. pasted text proportions

### Implementation Priority

| Priority | Item | Effort | Impact | Cost |
|----------|------|--------|--------|------|
| 1 | NNBSP watermark check | ~1 hour | Medium | Free |
| 2 | Expand AI word list | ~1 hour | Medium | Free |
| 3 | Em-dash + contraction checks | ~2 hours | Medium | Free |
| 4 | Grade-level calibration | ~3 hours | High | Free |
| 5 | Sentence uniformity check | ~2 hours | Medium | Free |
| 6 | `textstat` readability scoring | ~3 hours | High | Free |
| 7 | Composite confidence score | ~4 hours | High | Free |
| 8 | Subject-specific weights | ~3 hours | Medium | Free |
| 9 | Per-section detection | ~4 hours | High | Free |
| 10 | `lexicalrichness` MTLD/TTR | ~3 hours | Medium | Free |
| 11 | Originality.ai API integration | ~6 hours | High | ~$0.01/100 words |
| 12 | Copy-paste detection mode | ~8 hours | High | Free |
| 13 | Self-hosted HF model | ~8 hours | Medium | Free (RAM) |
| 14 | Google Docs revision analysis | ~12 hours | High | Free (API quota) |

---

## 13. Sources <a name="sources"></a>

### AI Detection Tools & Benchmarks
- [Originality.AI: Meta-Analysis of 13 Studies](https://originality.ai/blog/ai-detection-studies-round-up)
- [RAID Benchmark (ACL 2024)](https://arxiv.org/abs/2405.07940)
- [GPTZero: How AI Detectors Work](https://gptzero.me/news/how-ai-detectors-work/)
- [Ghostbuster: Detecting Text Ghostwritten by LLMs (UC Berkeley)](https://bair.berkeley.edu/blog/2023/11/14/ghostbuster/)
- [Binoculars: Zero-Shot Detection](https://arxiv.org/html/2401.12070v3)

### False Positives & Bias
- [Stanford HAI: AI Detectors Biased Against Non-Native Writers](https://hai.stanford.edu/news/ai-detectors-biased-against-non-native-english-writers)
- [GPT Detectors Are Biased (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC10382961/)
- [UCLA: The Imperfection of AI Detection Tools](https://humtech.ucla.edu/technology/the-imperfection-of-ai-detection-tools/)
- [Turnitin Fails: 750 Wrongly Flagged Students](https://gradpilot.com/news/turnitin-failed-admissions-pangram-replacement)

### University Policy Changes
- [Curtin University Disables AI Detection 2026](https://www.edtechinnovationhub.com/news/curtin-university-to-disable-turnitin-ai-detection-tool-in-2026-as-debate-over-reliability-continues)
- [Universities Stop Using AI Detection (Diplo)](https://www.diplomacy.edu/updates/universities-stop-using-ai-detection-tool-such-as-turnitin/)
- [JISC: AI Detection Assessment Update 2025](https://nationalcentreforai.jiscinvolve.org/wp/2025/06/24/ai-detection-assessment-2025/)

### Watermarking & Provenance
- [OpenAI Scraps Watermarking Plans](https://www.searchenginejournal.com/openai-scraps-chatgpt-watermarking-plans/523780/)
- [C2PA Content Credentials](https://c2pa.org/wp-content/uploads/sites/33/2025/10/content_credentials_wp_0925.pdf)
- [EU AI Act Transparency Code of Practice](https://digital-strategy.ec.europa.eu/en/policies/code-practice-ai-generated-content)

### Linguistic Markers
- [Wikipedia: Signs of AI Writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing)
- [The Ten Telltale Signs of AI-Generated Text](https://www.theaugmentededucator.com/p/the-ten-telltale-signs-of-ai-generated)
- [Why AI Models Use So Many Em-Dashes](https://www.seangoedecke.com/em-dashes/)

### Platforms & Tools
- [Turnitin Clarity (TIME Best Invention 2025)](https://www.turnitin.com/products/feedback-studio/clarity)
- [Brisk Teaching](https://www.briskteaching.com/post/how-to-detect-ai-writing-in-student-work)
- [Respondus on ChatGPT](https://web.respondus.com/what-is-respondus-doing-about-chatgpt/)
- [Securly AI Transparency](https://www.prnewswire.com/news-releases/popular-school-safety-platform-launches-first-comprehensive-student-ai-transparency-solution-for-k-12-district-and-school-leaders-302601498.html)
- [Copyleaks AI Logic LMS Launch](https://www.globenewswire.com/news-release/2025/07/29/3123248/0/en/Copyleaks-Launches-AI-Logic-Across-Major-Learning-Management-Systems-Delivering-Transparent-AI-Detection-for-Educators.html)

### Open-Source & HuggingFace
- [HuggingFace AI Detection Models](https://huggingface.co/models?other=ai-detection)
- [Fakespot RoBERTa AI Text Detection](https://huggingface.co/fakespot-ai/roberta-base-ai-text-detection-v1)
- [TextDescriptives (spaCy)](https://github.com/HLasse/TextDescriptives)
- [LexicalRichness](https://github.com/LSYS/LexicalRichness)
- [MAGE Dataset](https://huggingface.co/yaful/MAGE)

### Stylometry & Writing Analysis
- [Edutopia: What ELA Teachers Should Know About AI Detectors](https://www.edutopia.org/article/ai-detectors-what-teachers-should-know/)
- [Lexile Levels by Grade](https://lexile.com/wp-content/uploads/2018/09/Lexile-Educator-Guide-MM0066W.pdf)

### Adversarial Research
- [Adversarial Paraphrasing: Universal Attack for Humanizing AI Text](https://arxiv.org/abs/2506.07001)
- [AI Detection vs AI Humanization Arms Race](https://todaynews.co.uk/2026/02/03/ai-detection-vs-ai-humanization-the-arms-race-reshaping-content-creation/)
