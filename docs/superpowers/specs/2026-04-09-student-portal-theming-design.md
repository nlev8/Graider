# Student Portal Dark/Light Mode — Design Spec

## Problem

The student portal components (`StudentLogin.jsx`, `StudentDashboard.jsx`, `StudentPortal.jsx`) hardcode dark-mode colors (e.g., `#0f172a`, `#1e293b`, `rgba(30,41,59,...)`, `#94a3b8`) in inline styles instead of using the CSS variables defined in `globals.css`. The student portal has a theme toggle button (`StudentPortal.jsx` lines 296-314) but it doesn't work because the colors don't respond to the `data-theme` attribute.

## Solution

Replace all hardcoded color values with existing CSS variables from `globals.css` that respond to `[data-theme="light"]`. Add a small number of missing CSS variables for colors that don't have equivalents yet. The existing theme toggle and `data-theme` attribute system handles the rest.

## Missing CSS Variables to Add

Add to `frontend/src/styles/globals.css` in both `:root` (dark) and `[data-theme="light"]` blocks:

| Variable | Dark Value | Light Value | Used For |
|----------|-----------|-------------|----------|
| `--danger-light` | `#fca5a5` | `#dc2626` | Error/logout text |
| `--danger-bg` | `rgba(239,68,68,0.15)` | `rgba(239,68,68,0.1)` | Error backgrounds |
| `--danger-border` | `rgba(239,68,68,0.3)` | `rgba(239,68,68,0.2)` | Error borders |
| `--warning-bg` | `rgba(245,158,11,0.15)` | `rgba(245,158,11,0.1)` | Warning backgrounds |
| `--warning-border` | `rgba(245,158,11,0.3)` | `rgba(245,158,11,0.2)` | Warning borders |
| `--success-bg` | `rgba(34,197,94,0.15)` | `rgba(34,197,94,0.1)` | Success backgrounds |
| `--success-border` | `rgba(34,197,94,0.3)` | `rgba(34,197,94,0.2)` | Success borders |

## Color Mapping Reference

### Backgrounds
| Hardcoded | CSS Variable |
|-----------|-------------|
| `#0f172a`, `#1e293b` (gradient) | `--bg-gradient-start`, `--bg-gradient-end` |
| `rgba(30,41,59,0.95)`, `rgba(30,41,59,0.8)` | `--glass-bg` or `--modal-content-bg` |
| `rgba(30,41,59,0.5)` | `--glass-bg` |
| `rgba(15,23,42,0.8)` | `--input-bg` |
| `rgba(0,0,0,0.5)` | `--modal-bg` |
| `#1e293b` (modal content) | `--modal-content-bg` |

### Text
| Hardcoded | CSS Variable |
|-----------|-------------|
| `white`, `#ffffff` | `--text-primary` |
| `#e2e8f0` | `--text-primary` |
| `#94a3b8`, `#64748b` | `--text-secondary` |
| `#cbd5e1` | `--text-muted` |
| `rgba(255,255,255,0.7)`, `rgba(255,255,255,0.6)` | `--text-secondary` |
| `rgba(255,255,255,0.5)`, `rgba(255,255,255,0.4)` | `--text-muted` |
| `#475569` | `--text-secondary` |

### Borders & Accents
| Hardcoded | CSS Variable |
|-----------|-------------|
| `rgba(99,102,241,0.2)`, `rgba(99,102,241,0.15)`, `rgba(99,102,241,0.1)` | `--glass-border` |
| `rgba(99,102,241,0.3)` | `--input-border` |
| `rgba(255,255,255,0.1)`, `rgba(255,255,255,0.05)` | `--glass-border`, `--glass-bg` |

### Status Colors
| Hardcoded | CSS Variable |
|-----------|-------------|
| `#22c55e`, `#4ade80` | `--success` |
| `#ef4444`, `#f87171` | `--danger` |
| `#fca5a5` | `--danger-light` (new) |
| `#f59e0b`, `#fbbf24` | `--warning` |
| `#60a5fa` | `--info` |
| `#6366f1` | `--accent-primary` |
| `#8b5cf6` | `--accent-secondary` |
| `#a5b4fc` | `--accent-light` |

## Files to Modify

| File | Estimated Changes | Complexity |
|------|-------------------|-----------|
| `frontend/src/styles/globals.css` | Add 7 CSS variables in both theme blocks | Low |
| `frontend/src/components/StudentLogin.jsx` | ~12 color replacements | Low |
| `frontend/src/components/StudentDashboard.jsx` | ~20 color replacements | Medium |
| `frontend/src/components/StudentPortal.jsx` | ~40+ color replacements | Medium (volume) |

## Theme Toggle Behavior

- `StudentPortal.jsx` already has a theme toggle (sun/moon icon, lines 296-314)
- It sets `document.body.setAttribute("data-theme", ...)` and stores preference in `localStorage` as `portal-theme`
- Student theme preference is independent from teacher dashboard theme
- `StudentLogin.jsx` and `StudentDashboard.jsx` need to read the stored `portal-theme` on mount and apply it

## Non-goals

- No new theming system — use existing CSS variables and `data-theme` attribute
- No changes to `FlashcardView.jsx` — it already uses CSS variables
- No backend changes
- No changes to teacher dashboard theming
