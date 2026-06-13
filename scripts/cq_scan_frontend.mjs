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

const rows = [];

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
      let ast;
      try {
        ast = parse(fs.readFileSync(p, "utf8"), { sourceType: "module", plugins: ["jsx"] });
      } catch (e) {
        // Surface skips so an undercount during active refactoring is visible, not silent.
        console.error(`SKIP (parse error): ${p}: ${e.message}`);
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
process.exit(uniq.length ? 1 : 0);
