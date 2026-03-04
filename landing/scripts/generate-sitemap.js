#!/usr/bin/env node
/**
 * Auto-Sitemap Generator for graider.live
 * =========================================
 * Scans landing/ for HTML files and regenerates sitemap.xml automatically.
 * Preserves external entries (app.graider.live) and non-HTML entries (llms.txt).
 *
 * Usage:
 *   node landing/scripts/generate-sitemap.js
 *
 * Run from project root or as npm script: npm run generate-sitemap
 */

const fs = require('fs');
const path = require('path');

const BASE_URL = 'https://graider.live';
const LANDING_DIR = path.resolve(__dirname, '..');

// ── External entries to always preserve ────────────────────────────────
const EXTERNAL_ENTRIES = [
  { loc: 'https://app.graider.live/', changefreq: 'weekly', priority: '0.9' },
  { loc: 'https://app.graider.live/User_Manual.md', changefreq: 'monthly', priority: '0.7' },
];

// ── Non-HTML entries within graider.live ────────────────────────────────
const EXTRA_ENTRIES = [
  { path: 'llms.txt', changefreq: 'monthly', priority: '0.8' },
  { path: 'llms-full.txt', changefreq: 'monthly', priority: '0.7' },
];

// ── Priority & changefreq mapping ──────────────────────────────────────
function getPriority(relPath) {
  if (relPath === 'index.html') return '1.0';
  if (relPath === 'blog/index.html') return '0.8';
  if (relPath.startsWith('blog/') && relPath !== 'blog/index.html') {
    // "best-ai-grading-tools" is the flagship guide
    if (relPath.includes('best-ai-grading-tools')) return '0.9';
    return '0.8';
  }
  if (relPath === 'download.html') return '0.8';
  if (relPath === 'ferpa.html') return '0.5';
  if (relPath === 'privacy.html' || relPath === 'terms.html') return '0.4';
  return '0.6'; // default for any new pages
}

function getChangefreq(relPath) {
  if (relPath === 'index.html') return 'weekly';
  if (relPath === 'blog/index.html') return 'weekly';
  if (relPath.startsWith('blog/')) return 'monthly';
  if (relPath === 'download.html') return 'monthly';
  if (['privacy.html', 'terms.html', 'ferpa.html'].includes(relPath)) return 'yearly';
  return 'monthly';
}

// ── Scan for HTML files recursively ────────────────────────────────────
function findHtmlFiles(dir, baseDir) {
  const results = [];
  const entries = fs.readdirSync(dir, { withFileTypes: true });

  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);

    if (entry.isDirectory()) {
      // Skip scripts/, fonts/, and hidden directories
      if (['scripts', 'fonts', 'node_modules', '.git'].includes(entry.name)) continue;
      results.push(...findHtmlFiles(fullPath, baseDir));
    } else if (entry.isFile() && entry.name.endsWith('.html')) {
      // Skip template files (prefixed with _)
      if (entry.name.startsWith('_')) continue;

      const relPath = path.relative(baseDir, fullPath);
      results.push(relPath);
    }
  }

  return results;
}

// ── Get last-modified date from file ───────────────────────────────────
function getLastmod(filePath) {
  const stat = fs.statSync(filePath);
  return stat.mtime.toISOString().split('T')[0]; // YYYY-MM-DD
}

// ── Convert file path to URL (strip .html per Vercel cleanUrls) ────────
function filePathToUrl(relPath) {
  // index.html at root → /
  if (relPath === 'index.html') return '/';
  // blog/index.html → /blog
  if (relPath === 'blog/index.html') return '/blog';
  // Strip .html extension (Vercel cleanUrls: true)
  return '/' + relPath.replace(/\.html$/, '');
}

// ── Build XML ──────────────────────────────────────────────────────────
function buildSitemap(entries) {
  let xml = '<?xml version="1.0" encoding="UTF-8"?>\n';
  xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n';

  for (const entry of entries) {
    xml += '  <url>\n';
    xml += `    <loc>${entry.loc}</loc>\n`;
    xml += `    <lastmod>${entry.lastmod}</lastmod>\n`;
    xml += `    <changefreq>${entry.changefreq}</changefreq>\n`;
    xml += `    <priority>${entry.priority}</priority>\n`;
    xml += '  </url>\n';
  }

  xml += '</urlset>\n';
  return xml;
}

// ── Main ───────────────────────────────────────────────────────────────
function main() {
  console.log('🗺️  Generating sitemap.xml...\n');

  const htmlFiles = findHtmlFiles(LANDING_DIR, LANDING_DIR);
  const entries = [];

  // Add HTML file entries
  for (const relPath of htmlFiles) {
    const fullPath = path.join(LANDING_DIR, relPath);
    const url = filePathToUrl(relPath);

    entries.push({
      loc: `${BASE_URL}${url}`,
      lastmod: getLastmod(fullPath),
      changefreq: getChangefreq(relPath),
      priority: getPriority(relPath),
    });
  }

  // Add non-HTML entries (llms.txt, etc.)
  for (const extra of EXTRA_ENTRIES) {
    const fullPath = path.join(LANDING_DIR, extra.path);
    if (fs.existsSync(fullPath)) {
      entries.push({
        loc: `${BASE_URL}/${extra.path}`,
        lastmod: getLastmod(fullPath),
        changefreq: extra.changefreq,
        priority: extra.priority,
      });
    }
  }

  // Add external entries (app.graider.live) with today's date
  const today = new Date().toISOString().split('T')[0];
  for (const ext of EXTERNAL_ENTRIES) {
    entries.push({
      loc: ext.loc,
      lastmod: today,
      changefreq: ext.changefreq,
      priority: ext.priority,
    });
  }

  // Sort: homepage first, then by priority descending, then alphabetically
  entries.sort((a, b) => {
    if (a.loc === `${BASE_URL}/`) return -1;
    if (b.loc === `${BASE_URL}/`) return 1;
    const priDiff = parseFloat(b.priority) - parseFloat(a.priority);
    if (priDiff !== 0) return priDiff;
    return a.loc.localeCompare(b.loc);
  });

  const xml = buildSitemap(entries);
  const outputPath = path.join(LANDING_DIR, 'sitemap.xml');
  fs.writeFileSync(outputPath, xml, 'utf-8');

  console.log(`  Found ${htmlFiles.length} HTML pages`);
  console.log(`  Added ${EXTRA_ENTRIES.length} non-HTML entries`);
  console.log(`  Added ${EXTERNAL_ENTRIES.length} external entries`);
  console.log(`  Total: ${entries.length} URLs\n`);

  // Print all URLs
  for (const entry of entries) {
    console.log(`  ${entry.priority}  ${entry.loc}`);
  }

  console.log(`\n✅ Sitemap written to ${path.relative(process.cwd(), outputPath)}`);
}

main();
