# Results Page Horizontal Overflow Issue

## Problem

On a 13" MacBook Air (effective CSS viewport ~1280px wide), the **Results tab** has a horizontal scrollbar when the sidebar is open (260px). When the sidebar is collapsed (70px), it's fine. Other tabs (Grade, Resources, Settings) must NOT be affected by any fix.

## Current Layout Structure

```
<div style={{ minHeight: "100vh", padding: "20px" }}>          ← Root (line 3712)
  <div style={{ display: "flex", minHeight: "100vh" }}>         ← Flex wrapper (line 5286)
    <div style={{ position: "fixed", width: "260px" }}>         ← Sidebar (line 5288, fixed pos)
    </div>

    <div style={{                                                ← Main Content (line 5465)
      flex: 1,
      marginLeft: "260px",
      padding: "0",
      maxWidth: "calc(100vw - 260px)",
      display: "flex",
      flexDirection: "column",
      transition: "all 0.3s ease",
    }}>
      {/* Tab content renders here */}
    </div>
  </div>
</div>
```

## Root Cause Analysis

The root div (line 3712) has `padding: 20px`. The main content div has `marginLeft: 260px` and `maxWidth: calc(100vw - 260px)`. The math from the left edge of the viewport:

```
20px (root left padding)
+ 260px (content marginLeft)
+ calc(100vw - 260px) (content maxWidth)
+ 20px (root right padding)
= 100vw + 40px  ← OVERFLOWS BY 40px
```

Additionally, `100vw` includes the vertical scrollbar width (~15px on some configurations), which can add further overflow.

On a large monitor, the content inside the main div may not actually reach its `maxWidth`, so no visible overflow occurs. On a 13" screen (~1280px), the Results tab content (8-column table, multiple button rows) fills the available width, hitting the overflow.

## What Has Already Been Tried (and failed or broke other tabs)

1. Adding `overflowX: "hidden"` to the main content div — currently in place, but doesn't prevent the body-level scrollbar since the root div + margins exceed viewport width
2. Adding `overflow-x: hidden` to `html, body` in CSS — currently in place, hides the scrollbar but clips content instead of fixing layout
3. Removing root `padding: 20px` and moving it to main content — **broke Grade, Resources, Settings tabs** (they depend on the root padding)
4. Using `width`/`maxWidth` with `box-sizing: border-box` — still overflowed due to `100vw` scrollbar issue
5. Removing all width/maxWidth constraints — still overflowed

## Constraints

- The root div `padding: 20px` at line 3712 MUST remain — other tabs depend on it
- The sidebar is `position: fixed` with `width: 260px` (open) or `70px` (collapsed)
- The fix must work on any screen size (13" laptop through large external monitors)
- Other tabs (Grade, Builder, Analytics, Planner, Resources, Settings) must not be affected

## Elements Overflowing on Results Tab

1. **Filter/action buttons row** — "Open Folder", "Clear All", "Focus Export", "Send All Emails" (has `flexWrap: wrap`)
2. **Authenticity Summary** — flex row with icon, stats, "Hover for details" text
3. **Auto-Approve row** — "Approve All", "Clear Approvals", "Mark All as Sent" buttons
4. **Results table** — 8 columns: Student, Assignment, Time, Score, Grade, Authenticity, Email, Actions

## Files

- `frontend/src/App.jsx` — Lines 3712 (root), 5286 (flex wrapper), 5288 (sidebar), 5465 (main content), 7188+ (results tab)
- `frontend/src/styles/globals.css` — Lines 73-89 (global resets, body styles)

## Question for Review

What is the correct CSS approach to make the main content div fill exactly the remaining viewport width (viewport minus fixed sidebar) while accounting for the root div's 20px padding, without using `100vw` (which includes scrollbar width)?
