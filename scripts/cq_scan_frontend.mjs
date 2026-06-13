#!/usr/bin/env node
// CQ level-8 frontend scan: flag any function whose line span >200 LOC under frontend/src.
// Exit 1 if any offender, 0 if clean. Run from frontend/ (needs @babel/parser).
import fs from "node:fs";
import path from "node:path";
import { parse } from "@babel/parser";

const LIMIT = 200;
const root = process.argv[2] || "src";
const rows = [];

function len(node) {
  return node.loc ? node.loc.end.line - node.loc.start.line + 1 : 0;
}
function visit(node, hint) {
  if (!node || typeof node !== "object") return;
  if (Array.isArray(node)) return node.forEach((n) => visit(n, hint));
  if (node.type) {
    const isFn =
      node.type === "FunctionDeclaration" ||
      node.type === "FunctionExpression" ||
      node.type === "ArrowFunctionExpression";
    if (isFn) {
      const nm =
        node.type === "FunctionDeclaration" && node.id ? node.id.name : hint || "(anon)";
      const L = len(node);
      if (L > LIMIT) rows.push([L, node.__file, nm]);
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
      } catch {
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
const uniq = rows.filter((r) => {
  const k = r.join("::");
  return seen.has(k) ? false : (seen.add(k), true);
});
uniq.sort((a, b) => b[0] - a[0]);
for (const [L, f, n] of uniq) console.log(`${String(L).padStart(5)}  ${f}::${n}`);
console.error(`\n${uniq.length} functions >${LIMIT} LOC`);
process.exit(uniq.length ? 1 : 0);
