#!/usr/bin/env node
// CQ level-8 frontend scan: flag any function whose line span >200 LOC under frontend/src.
// Exit 1 if any offender, 0 if clean.
// Canonical:  node scripts/cq_scan_frontend.mjs            (run from repo root → scans frontend/src)
// Also works: cd frontend && node ../scripts/cq_scan_frontend.mjs
// @babel/parser is resolved from the frontend package's node_modules regardless of cwd
// (it lives there as a transitive dep of @vitejs/plugin-react; there is no root node_modules).
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const LIMIT = 200;

// Derive paths from the script's own location, not cwd, so the command works from anywhere.
const scriptDir = path.dirname(fileURLToPath(import.meta.url)); // <repo>/scripts
const repoRoot = path.resolve(scriptDir, "..");
const frontendDir = path.join(repoRoot, "frontend"); // owns @babel/parser as a transitive dep
const root = process.argv[2] || path.join(frontendDir, "src");

const require = createRequire(path.join(frontendDir, "noop.js"));
let parse;
try {
  ({ parse } = require("@babel/parser"));
} catch {
  console.error(
    `Cannot resolve @babel/parser from ${frontendDir}/node_modules — run \`cd frontend && npm install\` first.`,
  );
  process.exit(2);
}

if (!fs.existsSync(root)) {
  console.error(`Scan root does not exist: ${root}`);
  process.exit(2); // fail closed — never certify clean on a missing root
}

const rows = [];
let skipped = 0; // any unparsed file means the scan is incomplete → fail closed

function len(node) {
  return node.loc ? node.loc.end.line - node.loc.start.line + 1 : 0;
}
function visit(node, hint) {
  if (!node || typeof node !== "object") return;
  if (Array.isArray(node)) return node.forEach((n) => visit(n, hint));
  if (node.type) {
    const isMethod =
      node.type === "ObjectMethod" ||
      node.type === "ClassMethod" ||
      node.type === "ClassPrivateMethod";
    const isFn =
      node.type === "FunctionDeclaration" ||
      node.type === "FunctionExpression" ||
      node.type === "ArrowFunctionExpression" ||
      isMethod;
    if (isFn) {
      let nm;
      if (node.type === "FunctionDeclaration" && node.id) nm = node.id.name;
      else if (isMethod) nm = node.key?.name || node.key?.id?.name || hint || "(method)";
      else nm = hint || "(anon)";
      const L = len(node);
      // Key dedup on the node's source offset (unique per AST node), NOT L::file::name —
      // two distinct same-length anon functions in one file must not collapse (undercount).
      if (L > LIMIT) rows.push([L, node.__file, nm, node.start]);
    }
  }
  for (const k in node) {
    if (["loc", "start", "end", "leadingComments", "trailingComments"].includes(k)) continue;
    let h = hint;
    if (node.type === "VariableDeclarator" && node.id && node.id.name) h = node.id.name;
    visit(node[k], h);
  }
}
function walk(dir) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) {
      if (e.name === "node_modules") continue;
      walk(p);
    } else if (/\.(jsx?|tsx?)$/.test(e.name)) {
      // Per-extension plugins so .ts/.tsx parse instead of silently failing under jsx-only.
      const isTs = /\.tsx?$/.test(e.name);
      const isTsx = /\.tsx$/.test(e.name);
      const plugins = isTs ? (isTsx ? ["typescript", "jsx"] : ["typescript"]) : ["jsx"];
      let ast;
      try {
        ast = parse(fs.readFileSync(p, "utf8"), { sourceType: "module", plugins });
      } catch (e) {
        // Surface skips AND count them — an incomplete scan must fail closed below.
        console.error(`SKIP (parse error): ${p}: ${e.message}`);
        skipped++;
        continue;
      }
      const tag = (n) => {
        if (n && typeof n === "object") {
          if (n.type) n.__file = p;
          for (const k in n) if (k !== "__file") tag(n[k]);
        }
      };
      tag(ast);
      visit(ast, null);
    }
  }
}
walk(root);
const seen = new Set();
const uniq = rows.filter(([, file, , start]) => {
  const k = `${start}::${file}`; // source offset is unique per AST node — no false merges
  return seen.has(k) ? false : (seen.add(k), true);
});
uniq.sort((a, b) => b[0] - a[0]);
for (const [L, f, n] of uniq) {
  const rel = path.relative(repoRoot, f);
  console.log(`${String(L).padStart(5)}  ${rel}::${n}`);
}
console.error(`\n${uniq.length} functions >${LIMIT} LOC`);
if (uniq.length) process.exit(1);
if (skipped) {
  // Clean of offenders but the scan was incomplete — refuse to certify (fail closed).
  console.error(`INCOMPLETE: ${skipped} file(s) failed to parse — not certified clean.`);
  process.exit(2);
}
process.exit(0);
