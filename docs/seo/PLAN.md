# Graider SEO + AI-Search (GEO) Domination Plan

**Goal:** Own the word **"Graider"** in Google search and in AI answers (ChatGPT, Claude, Perplexity, Google AI Overviews) — decisively separating us (US K-12, graider.live) from **grAIder.de** (German AI-grading competitor, sole proprietorship, Dresden).

**Strategic read:** Our on-page SEO/GEO is already top-tier (rich JSON-LD, llms.txt, AI-crawler-friendly robots.txt, comparison blog). The gap is **off-page entity authority + disambiguation**, not on-page tags. Because grAIder is German/EU and we're US/English, Google already localizes — a US searcher very likely gets us. Our real exposure is (a) AI answers conflating the two globally, and (b) thin entity signals. The plan attacks both.

**Domain decision:** Commit to **graider.live** (no `.com`/`.ai` pursuit). All entity signals point here.

**Canonical name/casing:** Always **"Graider"** (one cap G). They style **"grAIder"** — our consistent casing is itself a disambiguation signal.

---

## Tier 1 — Own the entity (highest leverage for a same-name collision)

| # | Action | Owner | Status |
|---|---|---|---|
| 1.1 | Create **Wikidata item** for Graider (draft in `entity-assets.md`). AI models lean on Wikidata for entity grounding — grAIder has none, so the slot is unclaimed. | **You** (account) + me (draft) | Draft ready |
| 1.2 | Populate JSON-LD `sameAs` with official profile URLs | Me (scaffolded) | **Done — pending live handles** |
| 1.3 | Claim consistent profiles (identical name/logo/desc → graider.live): **X (@graider)**, LinkedIn Company, GitHub org, Crunchbase, Product Hunt | **You** (copy in `entity-assets.md`) | Copy ready |
| 1.4 | List on EdTech directories: **G2, Capterra, Common Sense Education** (US-context corroboration AI engines triangulate) | **You** (copy in `entity-assets.md`) | Copy ready |

## Tier 2 — Authority (what actually drives ranking)

| # | Action | Owner | Status |
|---|---|---|---|
| 2.1 | **Product Hunt launch** (copy in `entity-assets.md`) — backlink + AI-corroboration in one move | **You** | Copy ready |
| 2.2 | Seed **G2/Capterra reviews** from real teacher users | **You** | — |
| 2.3 | Backlinks from US EdTech blogs / teacher communities (outreach list in `entity-assets.md`) | **You** | List ready |
| 2.4 | **SIS-integration SEO landing pages** (Clever / ClassLink / OneRoster AI grading) — uncontested queries grAIder doesn't target | Me | Planned (next commit) |

## Tier 3 — Geo + content moat

| # | Action | Owner | Status |
|---|---|---|---|
| 3.1 | Google **Search Console**: confirm #1 for "graider" in US, set US audience, watch query position | **You** | — |
| 3.2 | `<link hreflang="en-us">` + `en-US` geo signals in `index.html` | Me | **Done** |
| 3.3 | Flagship **"What is Graider?"** entity page + expand **"Graider vs X"** posts | Me | Planned (next commit) |
| 3.4 | Lean content into **US K-12 + SIS/SSO + IEP/504** — grAIder targets none of it | Me | Ongoing |

## Tier 0 — Continuous monitoring (the cron)

| # | Action | Owner | Status |
|---|---|---|---|
| 0.1 | **Durable GitHub Actions weekly audit** (`.github/workflows/seo-audit.yml` + `scripts/seo_audit.py`) — validates JSON-LD, schema types, non-empty `sameAs`, llms.txt/sitemap reachable, no `href="#"` dead links, required meta. Opens a GitHub issue on regression. Free, permanent, no API key. | Me | **Done** |
| 0.2 | **Session cron (weekly)** — Claude audits live SERP + AI-answer state for "Graider" vs grAIder.de via WebSearch, writes a dated report to `docs/seo/reports/`, and opens a **PR with on-page fixes** when it finds gaps. NOTE: session-bound + auto-expires after 7 days; re-arm each session, or rely on the GH Action as the permanent backbone. | Me | **Done (this session)** |

---

## Division of labor summary
- **Me (in-repo, shipping via PRs):** `sameAs` + footer wiring, hreflang, the audit workflow + script, the session cron, SIS landing pages, the "What is Graider?" page, and all drafted copy.
- **You (off-platform):** create the X/LinkedIn/GitHub/Crunchbase/Product Hunt profiles + Wikidata item using the ready copy, paste the live URLs back so I finalize `sameAs`, seed reviews, run the Product Hunt launch, and confirm US targeting in Search Console.

**Next from me after this PR merges:** SIS landing pages (2.4) + "What is Graider?" entity page (3.3).
