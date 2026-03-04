#!/bin/bash
#
# Performance Monitoring Script for graider.live
# ================================================
# Uses Google PageSpeed Insights API (free, no key needed) to check
# Core Web Vitals and performance scores.
#
# Usage:
#   bash landing/scripts/lighthouse-check.sh
#
# Exit code 0 = all pages above threshold, 1 = below threshold

THRESHOLD=80  # Minimum performance score (0-100)
BASE_URL="https://graider.live"
STRATEGY="mobile"  # or "desktop"

# Pages to check
PAGES=(
    "/"
    "/blog"
    "/blog/best-ai-grading-tools"
)

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'

echo ""
echo -e "${BOLD}${CYAN}🚀 Performance Check for graider.live${RESET}"
echo -e "${DIM}Strategy: ${STRATEGY} | Threshold: ${THRESHOLD}/100${RESET}"
echo ""

# Check for curl and node (for JSON parsing)
if ! command -v curl &> /dev/null; then
    echo -e "${RED}Error: curl is required${RESET}"
    exit 1
fi

FAILURES=0
TOTAL=0

printf "  %-40s %6s %8s %8s %8s\n" "PAGE" "PERF" "LCP" "CLS" "INP"
printf "  %-40s %6s %8s %8s %8s\n" "────────────────────────────────────────" "──────" "────────" "────────" "────────"

for PAGE in "${PAGES[@]}"; do
    TOTAL=$((TOTAL + 1))
    URL="${BASE_URL}${PAGE}"
    API_URL="https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url=${URL}&strategy=${STRATEGY}&category=performance"

    # Fetch PageSpeed Insights data
    RESPONSE=$(curl -s --max-time 60 "$API_URL" 2>/dev/null)

    if [ -z "$RESPONSE" ]; then
        printf "  %-40s ${RED}%6s${RESET} %8s %8s %8s\n" "$PAGE" "ERROR" "—" "—" "—"
        FAILURES=$((FAILURES + 1))
        continue
    fi

    # Parse with node (available since we're in a Node project)
    RESULT=$(node -e "
        try {
            const data = JSON.parse(process.argv[1]);
            const lhr = data.lighthouseResult;
            if (!lhr) { console.log('ERROR|||—|||—|||—'); process.exit(0); }
            const perf = Math.round((lhr.categories.performance?.score || 0) * 100);
            const lcp = lhr.audits['largest-contentful-paint']?.displayValue || '—';
            const cls = lhr.audits['cumulative-layout-shift']?.displayValue || '—';
            const inp = lhr.audits['interaction-to-next-paint']?.displayValue || '—';
            console.log(perf + '|||' + lcp + '|||' + cls + '|||' + inp);
        } catch(e) {
            console.log('ERROR|||—|||—|||—');
        }
    " "$RESPONSE" 2>/dev/null)

    IFS='|||' read -r PERF_SCORE _ LCP _ CLS _ INP <<< "$RESULT"

    if [ "$PERF_SCORE" = "ERROR" ] || [ -z "$PERF_SCORE" ]; then
        printf "  %-40s ${RED}%6s${RESET} %8s %8s %8s\n" "$PAGE" "ERROR" "—" "—" "—"
        FAILURES=$((FAILURES + 1))
    elif [ "$PERF_SCORE" -lt "$THRESHOLD" ]; then
        printf "  %-40s ${RED}%6s${RESET} %8s %8s %8s\n" "$PAGE" "$PERF_SCORE" "$LCP" "$CLS" "$INP"
        FAILURES=$((FAILURES + 1))
    elif [ "$PERF_SCORE" -lt 90 ]; then
        printf "  %-40s ${YELLOW}%6s${RESET} %8s %8s %8s\n" "$PAGE" "$PERF_SCORE" "$LCP" "$CLS" "$INP"
    else
        printf "  %-40s ${GREEN}%6s${RESET} %8s %8s %8s\n" "$PAGE" "$PERF_SCORE" "$LCP" "$CLS" "$INP"
    fi
done

echo ""
echo -e "${DIM}  LCP = Largest Contentful Paint | CLS = Cumulative Layout Shift | INP = Interaction to Next Paint${RESET}"
echo ""

if [ "$FAILURES" -gt 0 ]; then
    echo -e "${RED}${BOLD}❌ ${FAILURES}/${TOTAL} page(s) below threshold (${THRESHOLD})${RESET}"
    echo ""
    exit 1
else
    echo -e "${GREEN}${BOLD}✅ All ${TOTAL} pages meet performance threshold (${THRESHOLD}+)${RESET}"
    echo ""
    exit 0
fi
