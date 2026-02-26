// Lightweight client-side check: do the teacher's "Additional Requirements"
// align with the selected standards?  Returns an advisory warning (non-blocking).

const STOPWORDS = new Set([
  "a","an","the","is","are","was","were","be","been","being","have","has","had",
  "do","does","did","will","would","could","should","may","might","shall","can",
  "to","of","in","for","on","with","at","by","from","as","into","through",
  "during","before","after","above","below","between","under","again","further",
  "then","once","here","there","when","where","why","how","all","each","every",
  "both","few","more","most","other","some","such","no","not","only","own",
  "same","so","than","too","very","just","about","also","and","but","or","if",
  "because","until","while","that","this","these","those","what","which","who",
  "whom","its","their","they","them","it","he","she","we","you","i","me","my",
  "your","his","her","our","us","up","out","over",
]);

const GENERIC_WORDS = new Set([
  "include","use","make","add","create","provide","ensure","incorporate",
  "integrate","focus","emphasize","highlight","visuals","visual","images",
  "pictures","diagrams","charts","graphs","videos","media","interactive",
  "group","groups","pair","pairs","partner","partners","collaborative",
  "cooperative","teamwork","discussion","engaging","hands","kinesthetic",
  "activity","activities","differentiated","differentiation","scaffolded",
  "scaffolding","modified","accommodations","extensions","enrichment",
  "formative","summative","assessment","check","review","practice",
  "homework","classwork","bellringer","warmup","exit","ticket","closure",
  "reflection","journal","technology","digital","online","computer",
  "tablet","chromebook","minutes","minute","time","day","days","week",
  "period","easy","simple","brief","short","long","detailed","fun",
  "creative","real","world","relevant","rigorous","aligned","appropriate",
  "students","student","learners","class","classroom","teacher","guided",
  "independent","whole","small","work","project","presentation","poster",
  "worksheet","reading","writing","speaking","listening","questions",
  "question","answer","answers","response","responses","step","steps",
  "show","explain","describe","analyze","compare","contrast","identify",
  "define","list","example","examples","evidence","support","cite",
  "harder","easier","simpler","challenging","level","based","using",
]);

// Matches FL standard codes like SS.7.C.1.1, MA.6.NSO.1.1, SC.912.N.1.1
const CODE_RE = /\b(SS|MA|SC|ELA|HE|PE|VA|MU|TH|DA|WL)\.\d{1,3}[A-Z]?\.[A-Z]{1,4}\.\d+(\.\d+)?\b/g;

/** Strip punctuation, collapse whitespace, lowercase */
function normalize(text) {
  return text.toLowerCase().replace(/[^a-z0-9\s]/g, "").replace(/\s+/g, " ").trim();
}

function tokenize(text) {
  return normalize(text).split(" ").filter(w => w.length >= 2);
}

function isContentWord(w) {
  return !STOPWORDS.has(w) && !GENERIC_WORDS.has(w);
}

// Session-level dedup: keyed by requirements + standards combo
const _warned = new Set();

/**
 * Check if the teacher's additional requirements text aligns with the
 * selected standards' content.  Returns { mismatch, message }.
 *
 * @param {string}   requirementsText       Free-text from the requirements textarea
 * @param {string[]} selectedStandardCodes   Array of selected standard code strings
 * @param {Object[]} allStandards            Full standards array (topics, vocabulary, benchmark …)
 * @returns {{ mismatch: boolean, message: string }}
 */
export function checkRequirementsMismatch(requirementsText, selectedStandardCodes, allStandards) {
  const NO_WARN = { mismatch: false, message: "" };

  // Guard: nothing to check
  const req = (requirementsText || "").trim();
  if (!req) return NO_WARN;
  if (!selectedStandardCodes?.length) return NO_WARN;
  if (!allStandards?.length) return NO_WARN;          // standards not loaded yet

  // Session dedup — scoped to requirements text + selected standards
  const dedupKey = normalize(req) + "|" + [...selectedStandardCodes].sort().join(",");
  if (_warned.has(dedupKey)) return NO_WARN;

  // ---- Build keyword pool from selected standards ----
  const phrases = new Set();          // normalized multi-word phrases
  const words   = new Set();          // single content words
  const wordToStandardCount = {};     // track how many standards contain each word (for distinctiveness)

  const selectedSet = new Set(selectedStandardCodes);

  for (const code of selectedStandardCodes) {
    const std = allStandards.find(s => s.code === code);
    if (!std) continue;

    const wordsFromThisStandard = new Set();

    // Multi-word phrases from topics + vocabulary (normalized)
    for (const arr of [std.topics, std.vocabulary]) {
      if (!Array.isArray(arr)) continue;
      for (const entry of arr) {
        if (!entry) continue;
        const norm = normalize(entry);
        if (norm.includes(" ")) {
          phrases.add(norm);
        }
        // Also add individual words from phrases to the word pool
        for (const w of norm.split(" ")) {
          if (w.length >= 2 && isContentWord(w)) {
            words.add(w);
            wordsFromThisStandard.add(w);
          }
        }
      }
    }

    // Single words from benchmark + learning_targets
    for (const field of [std.benchmark, ...(std.learning_targets || [])]) {
      if (!field) continue;
      for (const w of tokenize(field)) {
        if (isContentWord(w)) {
          words.add(w);
          wordsFromThisStandard.add(w);
        }
      }
    }

    // Count how many standards each word appears in (across ALL standards, not just selected)
    for (const w of wordsFromThisStandard) {
      wordToStandardCount[w] = (wordToStandardCount[w] || 0) + 1;
    }
  }

  // Count word frequency across ALL standards for distinctiveness check
  const globalWordFreq = {};
  for (const std of allStandards) {
    const seen = new Set();
    for (const arr of [std.topics, std.vocabulary]) {
      if (!Array.isArray(arr)) continue;
      for (const entry of arr) {
        if (!entry) continue;
        for (const w of tokenize(entry)) {
          if (isContentWord(w)) seen.add(w);
        }
      }
    }
    for (const w of seen) {
      globalWordFreq[w] = (globalWordFreq[w] || 0) + 1;
    }
  }

  // ---- Tokenize requirements ----
  const reqNorm = normalize(req);
  const contentWords = tokenize(req).filter(isContentWord);

  // If requirements are entirely generic/instructional, skip
  if (contentWords.length === 0) return NO_WARN;

  // ---- Multi-word phrase matches ----
  let phraseHits = 0;
  for (const phrase of phrases) {
    if (reqNorm.includes(phrase)) phraseHits++;
  }

  // ---- Single-word matches ----
  const matchedWords = new Set();
  let hasDistinctiveHit = false;

  for (const w of contentWords) {
    if (words.has(w)) {
      matchedWords.add(w);
      // Distinctive: this word appears in ≤2 standards globally (niche topic)
      if ((globalWordFreq[w] || 0) <= 2) {
        hasDistinctiveHit = true;
      }
    }
  }

  // ---- Decision ----
  // Any multi-word phrase match = strong alignment signal
  if (phraseHits >= 1) return NO_WARN;
  // 2+ unique word hits = sufficient overlap
  if (matchedWords.size >= 2) return NO_WARN;
  // 1 hit but it's a distinctive/niche term = sufficient
  if (matchedWords.size === 1 && hasDistinctiveHit) return NO_WARN;

  // ---- Inverse code check ----
  const referencedCodes = [];
  let m;
  CODE_RE.lastIndex = 0;
  while ((m = CODE_RE.exec(req)) !== null) {
    const code = m[0];
    // Only flag if the code actually exists in standards (avoid prose false positives)
    if (!selectedSet.has(code) && allStandards.some(s => s.code === code)) {
      referencedCodes.push(code);
    }
  }

  let message = "Your additional requirements may not align with the selected standard(s). Please verify before generating.";
  if (referencedCodes.length > 0) {
    message = "Your requirements reference " + referencedCodes.join(", ") +
      " which " + (referencedCodes.length === 1 ? "is" : "are") +
      " not currently selected. " + message;
  }

  _warned.add(dedupKey);   // don't repeat for same text + standards combo
  return { mismatch: true, message };
}
