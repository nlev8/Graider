#!/usr/bin/env node
/**
 * SEO Health Check Script for graider.live
 * ==========================================
 * Validates all HTML pages have required SEO elements.
 * Outputs a report with PASS/FAIL per check per page.
 *
 * Usage:
 *   node landing/scripts/seo-health-check.js
 *
 * Exit code 0 = all pass, 1 = failures found (CI-friendly)
 */

const fs = require('fs');
const path = require('path');

const LANDING_DIR = path.resolve(__dirname, '..');

// ── Colors for terminal output ─────────────────────────────────────────
const GREEN = '\x1b[32m';
const RED = '\x1b[31m';
const YELLOW = '\x1b[33m';
const CYAN = '\x1b[36m';
const DIM = '\x1b[2m';
const RESET = '\x1b[0m';
const BOLD = '\x1b[1m';

const PASS = `${GREEN}PASS${RESET}`;
const FAIL = `${RED}FAIL${RESET}`;
const WARN = `${YELLOW}WARN${RESET}`;

// ── Required SEO checks ────────────────────────────────────────────────
const REQUIRED_CHECKS = [
  { name: '<title>', pattern: /<title>[^<]+<\/title>/i },
  { name: 'meta description', pattern: /<meta\s+name=["']description["']\s+content=["'][^"']+["']/i },
  { name: 'canonical URL', pattern: /<link\s+rel=["']canonical["']\s+href=["'][^"']+["']/i },
  { name: 'meta robots', pattern: /<meta\s+name=["']robots["']\s+content=["'][^"']+["']/i },
  { name: 'og:type', pattern: /<meta\s+property=["']og:type["']\s+content=["'][^"']+["']/i },
  { name: 'og:title', pattern: /<meta\s+property=["']og:title["']\s+content=["'][^"']+["']/i },
  { name: 'og:description', pattern: /<meta\s+property=["']og:description["']\s+content=["'][^"']+["']/i },
  { name: 'og:image', pattern: /<meta\s+property=["']og:image["']\s+content=["'][^"']+["']/i },
  { name: 'og:url', pattern: /<meta\s+property=["']og:url["']\s+content=["'][^"']+["']/i },
  { name: 'twitter:card', pattern: /<meta\s+(name|property)=["']twitter:card["']\s+content=["'][^"']+["']/i },
  { name: 'twitter:title', pattern: /<meta\s+(name|property)=["']twitter:title["']\s+content=["'][^"']+["']/i },
  { name: 'twitter:description', pattern: /<meta\s+(name|property)=["']twitter:description["']\s+content=["'][^"']+["']/i },
  { name: 'JSON-LD', pattern: /<script\s+type=["']application\/ld\+json["']/i },
];

// ── Blog-specific checks ───────────────────────────────────────────────
const BLOG_CHECKS = [
  { name: 'article:published_time', pattern: /<meta\s+property=["']article:published_time["']\s+content=["'][^"']+["']/i },
  { name: 'og:type=article', pattern: /<meta\s+property=["']og:type["']\s+content=["']article["']/i },
];

// ── Find HTML files ────────────────────────────────────────────────────
function findHtmlFiles(dir, baseDir) {
  const results = [];
  const entries = fs.readdirSync(dir, { withFileTypes: true });

  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);

    if (entry.isDirectory()) {
      if (['scripts', 'fonts', 'node_modules', '.git'].includes(entry.name)) continue;
      results.push(...findHtmlFiles(fullPath, baseDir));
    } else if (entry.isFile() && entry.name.endsWith('.html')) {
      // Skip template files
      if (entry.name.startsWith('_')) continue;
      results.push(path.relative(baseDir, fullPath));
    }
  }

  return results;
}

// ── Check for images without alt attributes ────────────────────────────
function checkImageAlts(html) {
  const imgRegex = /<img\s[^>]*>/gi;
  const issues = [];
  let match;

  while ((match = imgRegex.exec(html)) !== null) {
    const imgTag = match[0];
    if (!/alt=["'][^"']*["']/i.test(imgTag) && !/alt=""/i.test(imgTag)) {
      // Extract src for reporting
      const srcMatch = imgTag.match(/src=["']([^"']+)["']/i);
      const src = srcMatch ? srcMatch[1] : 'unknown';
      issues.push(src);
    }
  }

  return issues;
}

// ── Check internal links ───────────────────────────────────────────────
function checkInternalLinks(html, relPath) {
  const hrefRegex = /href=["']([^"'#]+)["']/gi;
  const brokenLinks = [];
  let match;

  while ((match = hrefRegex.exec(html)) !== null) {
    const href = match[1];

    // Only check internal relative links
    if (href.startsWith('http') || href.startsWith('mailto:') || href.startsWith('tel:')) continue;
    if (href.startsWith('#')) continue;
    if (href.startsWith('javascript:')) continue;

    // Resolve the path relative to the file's directory
    let targetPath;
    if (href.startsWith('/')) {
      targetPath = path.join(LANDING_DIR, href);
    } else {
      const fileDir = path.join(LANDING_DIR, path.dirname(relPath));
      targetPath = path.join(fileDir, href);
    }

    // Check if file exists (try with and without .html for cleanUrls)
    if (!fs.existsSync(targetPath) &&
        !fs.existsSync(targetPath + '.html') &&
        !fs.existsSync(targetPath + '/index.html') &&
        !fs.existsSync(path.join(targetPath, 'index.html'))) {
      brokenLinks.push(href);
    }
  }

  return brokenLinks;
}

// ── Main ───────────────────────────────────────────────────────────────
function main() {
  console.log(`\n${BOLD}${CYAN}🔍 SEO Health Check for graider.live${RESET}\n`);
  console.log(`${DIM}Scanning ${LANDING_DIR}${RESET}\n`);

  const htmlFiles = findHtmlFiles(LANDING_DIR, LANDING_DIR);
  let totalIssues = 0;
  let totalWarnings = 0;
  let totalChecks = 0;
  const pageSummaries = [];

  for (const relPath of htmlFiles.sort()) {
    const fullPath = path.join(LANDING_DIR, relPath);
    const html = fs.readFileSync(fullPath, 'utf-8');
    const isBlogPost = relPath.startsWith('blog/') && relPath !== 'blog/index.html';
    let pageIssues = 0;
    let pageWarnings = 0;

    console.log(`${BOLD}📄 ${relPath}${RESET}`);

    // Run required checks
    for (const check of REQUIRED_CHECKS) {
      totalChecks++;
      if (check.pattern.test(html)) {
        console.log(`   ${PASS}  ${check.name}`);
      } else {
        console.log(`   ${FAIL}  ${check.name}`);
        pageIssues++;
        totalIssues++;
      }
    }

    // Blog-specific checks
    if (isBlogPost) {
      for (const check of BLOG_CHECKS) {
        totalChecks++;
        if (check.pattern.test(html)) {
          console.log(`   ${PASS}  ${check.name} ${DIM}(blog)${RESET}`);
        } else {
          console.log(`   ${FAIL}  ${check.name} ${DIM}(blog)${RESET}`);
          pageIssues++;
          totalIssues++;
        }
      }
    }

    // Image alt check
    const missingAlts = checkImageAlts(html);
    totalChecks++;
    if (missingAlts.length === 0) {
      console.log(`   ${PASS}  image alt attributes`);
    } else {
      console.log(`   ${WARN}  ${missingAlts.length} image(s) missing alt: ${DIM}${missingAlts.join(', ')}${RESET}`);
      pageWarnings++;
      totalWarnings++;
    }

    // Internal link check
    const brokenLinks = checkInternalLinks(html, relPath);
    totalChecks++;
    if (brokenLinks.length === 0) {
      console.log(`   ${PASS}  internal links`);
    } else {
      console.log(`   ${WARN}  ${brokenLinks.length} broken link(s): ${DIM}${brokenLinks.join(', ')}${RESET}`);
      pageWarnings++;
      totalWarnings++;
    }

    const status = pageIssues > 0 ? `${RED}${pageIssues} issue(s)${RESET}` :
                   pageWarnings > 0 ? `${YELLOW}${pageWarnings} warning(s)${RESET}` :
                   `${GREEN}all clear${RESET}`;
    pageSummaries.push({ relPath, pageIssues, pageWarnings });
    console.log(`   ${DIM}─── ${status}${RESET}\n`);
  }

  // Summary
  console.log(`${BOLD}${CYAN}═══ Summary ═══${RESET}\n`);
  console.log(`  Pages scanned:  ${htmlFiles.length}`);
  console.log(`  Total checks:   ${totalChecks}`);
  console.log(`  Issues (FAIL):  ${totalIssues > 0 ? RED : GREEN}${totalIssues}${RESET}`);
  console.log(`  Warnings:       ${totalWarnings > 0 ? YELLOW : GREEN}${totalWarnings}${RESET}`);

  if (totalIssues > 0) {
    console.log(`\n${RED}${BOLD}❌ ${totalIssues} SEO issue(s) found across the following pages:${RESET}`);
    for (const p of pageSummaries) {
      if (p.pageIssues > 0) {
        console.log(`   ${RED}•${RESET} ${p.relPath} — ${p.pageIssues} issue(s)`);
      }
    }
    console.log(`\n${DIM}Fix these issues to improve search engine visibility.${RESET}\n`);
    process.exit(1);
  } else {
    console.log(`\n${GREEN}${BOLD}✅ All SEO checks passed!${RESET}\n`);
    process.exit(0);
  }
}

main();
