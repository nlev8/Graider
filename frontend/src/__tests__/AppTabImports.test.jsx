/**
 * Regression: every <XxxTab> component rendered in App.jsx must have a
 * matching `import XxxTab from ...` line.
 *
 * Caught by Codex during the 2026-05-04 9-dimension re-score: PR #191
 * extracted the inline Planner block into tabs/PlannerTab.jsx and rendered
 * `<PlannerTab .../>` in App.jsx, but forgot to add the import. The build
 * passed because vite/esbuild does NOT fail on undefined-identifier-in-JSX
 * (it just resolves to undefined). Only React.createElement at runtime
 * raises "Element type is invalid: expected a string... but got: undefined"
 * — which means the live planner tab would have crashed for users.
 *
 * Smoke-test in PlannerTab.test.jsx didn't catch this because it imports
 * PlannerTab directly. The full smoke.test.jsx avoids App.jsx integration
 * entirely. So this contract test fills the gap statically.
 *
 * Failure mode: if you add `<NewTab />` to App.jsx without importing it,
 * this test fails at parse time before the user ever sees a runtime crash.
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "fs";
import { join } from "path";

// The App.jsx finale split (CQ campaign) relocated the tab mounts into
// src/app/AppTabPanels.jsx, so the per-file import check now runs over both
// files — the guarantee is per-file (an import in one file cannot satisfy a
// usage in the other, which is exactly the PR #191 failure mode).
const FILES = [
  join(__dirname, "..", "App.jsx"),
  join(__dirname, "..", "app", "AppTabPanels.jsx"),
];

describe.each(FILES)("tab imports in %s", (appPath) => {
  it("every <XxxTab> rendered has a matching import", () => {
    const src = readFileSync(appPath, "utf-8");

    // Find all JSX usages of components matching `<XxxTab` (case-sensitive
    // to avoid lowercase HTML elements). Captures the component name.
    const usagePattern = /<([A-Z][A-Za-z0-9]*Tab)\b/g;
    const usedTabs = new Set();
    let m;
    while ((m = usagePattern.exec(src)) !== null) {
      usedTabs.add(m[1]);
    }

    // Find imports + lazy-imports of *Tab components.
    // Matches:
    //   import XxxTab from "./tabs/XxxTab"
    //   const XxxTab = React.lazy(...)
    //   var XxxTab = React.lazy(function() { return import("..."); });
    const importPattern = /(?:^|\n)\s*import\s+([A-Z][A-Za-z0-9]*Tab)\b/g;
    const lazyPattern = /(?:const|var)\s+([A-Z][A-Za-z0-9]*Tab)\s*=\s*React\.lazy/g;
    const importedTabs = new Set();
    while ((m = importPattern.exec(src)) !== null) {
      importedTabs.add(m[1]);
    }
    while ((m = lazyPattern.exec(src)) !== null) {
      importedTabs.add(m[1]);
    }

    // Every used must be imported.
    const missing = [...usedTabs].filter((t) => !importedTabs.has(t)).sort();
    expect(missing).toEqual([]);
  });
});
