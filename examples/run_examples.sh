#!/bin/bash
#
# Verification suite runner for views-datafactory
#
# Discovers and runs all ex_*.py scripts in this directory.
# Each script tests one API capability and prints PASS/FAIL/XFAIL/SKIP.
#
# Usage:
#   bash examples/run_examples.sh                    # local backends only
#   bash examples/run_examples.sh --include-remote   # also test remote zarr
#
# Exit code:
#   0 — all scripts passed (PASS, XFAIL, SKIP count as pass)
#   1 — at least one script failed
#

set -uo pipefail

# ── Colors ────────────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BOLD='\033[1m'
NC='\033[0m'

# ── Parse arguments ──────────────────────────────────────────────────

INCLUDE_REMOTE=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --include-remote) INCLUDE_REMOTE=1; shift ;;
        --help|-h)
            echo "Usage: bash examples/run_examples.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --include-remote   Also run ex_zarr_remote.py (requires network + .netrc)"
            echo "  --help, -h         Show this help"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# ── Discover scripts ────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

SCRIPTS=()
for f in "$SCRIPT_DIR"/ex_*.py; do
    [ -f "$f" ] || continue
    basename=$(basename "$f")

    if [ "$INCLUDE_REMOTE" -eq 0 ] && [ "$basename" = "ex_zarr_remote.py" ]; then
        continue
    fi

    SCRIPTS+=("$basename")
done

IFS=$'\n' SCRIPTS=($(sort <<<"${SCRIPTS[*]}")); unset IFS

TOTAL=${#SCRIPTS[@]}
if [ "$TOTAL" -eq 0 ]; then
    echo "No ex_*.py scripts found in $SCRIPT_DIR"
    exit 1
fi

# ── Header ──────────────────────────────────────────────────────────

echo -e "${BOLD}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  views-datafactory verification suite${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════════════${NC}"
echo "  Scripts:  $TOTAL"
echo "  Remote:   $([ "$INCLUDE_REMOTE" -eq 1 ] && echo "included" || echo "skipped")"
echo -e "${BOLD}═══════════════════════════════════════════════════════════${NC}"
echo ""

# ── Run scripts ─────────────────────────────────────────────────────

declare -A RESULTS
declare -A OUTPUTS
PASS_COUNT=0
FAIL_COUNT=0
XFAIL_COUNT=0
SKIP_COUNT=0

for i in "${!SCRIPTS[@]}"; do
    script="${SCRIPTS[$i]}"
    idx=$((i + 1))
    echo -ne "[${idx}/${TOTAL}] ${BOLD}${script}${NC} ... "

    output=$(cd "$REPO_ROOT" && uv run python "examples/$script" 2>&1)
    exit_code=$?

    OUTPUTS[$script]="$output"

    if [ "$exit_code" -eq 0 ]; then
        if echo "$output" | grep -q "^XFAIL"; then
            echo -e "${YELLOW}XFAIL${NC}"
            RESULTS[$script]="XFAIL"
            XFAIL_COUNT=$((XFAIL_COUNT + 1))
        elif echo "$output" | grep -q "^SKIP"; then
            echo -e "${YELLOW}SKIP${NC}"
            RESULTS[$script]="SKIP"
            SKIP_COUNT=$((SKIP_COUNT + 1))
        else
            echo -e "${GREEN}PASS${NC}"
            RESULTS[$script]="PASS"
            PASS_COUNT=$((PASS_COUNT + 1))
        fi
    else
        echo -e "${RED}FAIL${NC}"
        RESULTS[$script]="FAIL"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
done

# ── Summary ─────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  Summary${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════════════${NC}"
echo ""

printf "%-35s %-10s %s\n" "Script" "Result" "Detail"
printf "%-35s %-10s %s\n" "------" "------" "------"

for script in "${SCRIPTS[@]}"; do
    result="${RESULTS[$script]}"
    detail=$(echo "${OUTPUTS[$script]}" | tail -1)
    case "$result" in
        PASS)  printf "%-35s ${GREEN}%-10s${NC} %s\n" "$script" "$result" "$detail" ;;
        FAIL)  printf "%-35s ${RED}%-10s${NC} %s\n" "$script" "$result" "$detail" ;;
        XFAIL) printf "%-35s ${YELLOW}%-10s${NC} %s\n" "$script" "$result" "$detail" ;;
        SKIP)  printf "%-35s ${YELLOW}%-10s${NC} %s\n" "$script" "$result" "$detail" ;;
    esac
done

echo ""
echo -e "  ${GREEN}Passed:${NC}  $PASS_COUNT"
[ "$XFAIL_COUNT" -gt 0 ] && echo -e "  ${YELLOW}XFail:${NC}   $XFAIL_COUNT (expected failures — documented gaps)"
[ "$SKIP_COUNT" -gt 0 ]  && echo -e "  ${YELLOW}Skipped:${NC} $SKIP_COUNT"
[ "$FAIL_COUNT" -gt 0 ]  && echo -e "  ${RED}Failed:${NC}  $FAIL_COUNT"
echo "  Total:   $TOTAL"
echo ""

# ── Failed script details ───────────────────────────────────────────

if [ "$FAIL_COUNT" -gt 0 ]; then
    echo -e "${RED}${BOLD}Failed script output:${NC}"
    echo ""
    for script in "${SCRIPTS[@]}"; do
        if [ "${RESULTS[$script]}" = "FAIL" ]; then
            echo -e "  ${BOLD}$script:${NC}"
            echo "${OUTPUTS[$script]}" | sed 's/^/    /'
            echo ""
        fi
    done
fi

# ── Exit ────────────────────────────────────────────────────────────

if [ "$FAIL_COUNT" -gt 0 ]; then
    exit 1
fi
exit 0
