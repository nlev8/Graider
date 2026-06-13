#!/usr/bin/env node
/*
 * free-idents.cjs — list free (unbound) identifiers in a JS/JSX module.
 * Used by the App.jsx finale split to derive exact ctx-destructure lists for
 * the extracted segment hooks/sections, and as a no-undef gate (vite/esbuild
 * silently tolerates undefined identifiers in JSX — see AppTabImports.test.jsx).
 *
 * Usage: node scripts/free-idents.cjs <file> [...files]
 */
const fs = require('fs');
const parser = require('@babel/parser');
const traverse = require('@babel/traverse').default;

const GLOBALS = new Set([
  'window', 'document', 'console', 'fetch', 'localStorage', 'sessionStorage',
  'URL', 'Blob', 'URLSearchParams', 'FormData', 'navigator', 'alert', 'confirm',
  'setTimeout', 'clearTimeout', 'setInterval', 'clearInterval',
  'Promise', 'Object', 'Array', 'Math', 'JSON', 'Date', 'Set', 'Map', 'RegExp',
  'Error', 'TypeError', 'String', 'Number', 'Boolean', 'Symbol', 'Infinity', 'NaN',
  'parseInt', 'parseFloat', 'isNaN', 'isFinite', 'undefined', 'globalThis',
  'encodeURIComponent', 'decodeURIComponent', 'structuredClone', 'requestAnimationFrame',
  'FileReader', 'AbortController', 'Event', 'CustomEvent', 'Element', 'Node', 'crypto',
]);

for (const file of process.argv.slice(2)) {
  const code = fs.readFileSync(file, 'utf8');
  const ast = parser.parse(code, { sourceType: 'module', plugins: ['jsx'] });
  const free = new Map(); // name -> first line
  traverse(ast, {
    // ReferencedIdentifier covers plain identifiers + JSXIdentifier refs
    ReferencedIdentifier(p) {
      const name = p.node.name;
      if (GLOBALS.has(name)) return;
      if (p.scope.hasBinding(name, true)) return;
      if (!free.has(name)) free.set(name, p.node.loc && p.node.loc.start.line);
    },
  });
  const names = [...free.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  console.log(`== ${file} (${names.length} free)`);
  for (const [n, line] of names) console.log(`${n}\t@${line}`);
}
