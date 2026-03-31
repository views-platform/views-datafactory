#!/usr/bin/env bash
# Full pipeline refresh — harvest, compile, export.
#
# Usage:
#   bash scripts/refresh_pipeline.sh
#
# This script runs the entire data pipeline end-to-end:
#   1. Harvest raw data from UCDP, PRIO-GRID, and GAUL APIs
#   2. Consolidate UCDP sources into event store
#   3. Build viewpoint (survivorship + distribution + filtering)
#   4. Compile events onto PRIO-GRID
#   5. Assemble all features (UCDP + static + admin)
#   6. Export to consumer formats (zarr, parquet)
#   7. Run health check
#
# Requires:
#   - UCDP_API_TOKEN environment variable
#   - Internet access (for UCDP, PRIO-GRID, GAUL APIs)
#   - uv installed
#
# The script stops on first error (set -e). Check output for
# which step failed. Each step writes provenance to provenance/.
#
# For cron: 0 3 1 * * cd /path/to/views-datafactory && bash scripts/refresh_pipeline.sh >> logs/refresh.log 2>&1

set -euo pipefail

# ---- Environment ----
# Cron runs with minimal PATH; ensure uv and cargo binaries are available.
export PATH="$HOME/.cargo/bin:$HOME/.local/bin:/usr/local/bin:$PATH"

# Source bashrc for UCDP_API_TOKEN and other env vars (if non-interactive)
if [ -f "$HOME/.bashrc" ]; then
    # shellcheck source=/dev/null
    source "$HOME/.bashrc"
fi

# ---- Failure notification ----
# On any step failure, write a machine-readable sentinel and
# optionally send email (if mail is configured and ALERT_EMAIL set).
ALERT_FILE="logs/pipeline_failure.json"
CURRENT_STEP="init"

on_failure() {
    local exit_code=$?
    mkdir -p logs
    echo "{\"timestamp\": \"$(date -Iseconds)\", \"exit_code\": $exit_code, \"step\": \"$CURRENT_STEP\"}" > "$ALERT_FILE"
    echo
    echo "PIPELINE FAILED at step: $CURRENT_STEP (exit code $exit_code)"
    echo "Failure logged to $ALERT_FILE"
    if [ -n "${ALERT_EMAIL:-}" ] && command -v mail &>/dev/null; then
        echo "Pipeline failed at $CURRENT_STEP on $(hostname). Check logs/refresh.log" | \
            mail -s "VIEWS pipeline failure $(date -Iseconds)" "$ALERT_EMAIL"
    fi
}
trap on_failure ERR

echo "========================================"
echo "VIEWS Data Factory — Pipeline Refresh"
echo "Started: $(date -Iseconds)"
echo "========================================"
echo

# Step 1: Harvest
CURRENT_STEP="1/7: Harvest raw data"
echo "── $CURRENT_STEP ──"
uv run python scripts/harvest_ucdp.py
uv run python scripts/harvest_priogrid.py
uv run python scripts/harvest_shapefile.py
uv run python scripts/harvest_gaul.py
echo

# Step 2: Consolidate
CURRENT_STEP="2/7: Consolidate UCDP sources"
echo "── $CURRENT_STEP ──"
uv run python scripts/consolidate_ucdp.py
echo

# Step 3: Build viewpoint
CURRENT_STEP="3/7: Build viewpoint"
echo "── $CURRENT_STEP ──"
uv run python scripts/build_viewpoint.py
echo

# Step 4: Compile grid
CURRENT_STEP="4/7: Compile to PRIO-GRID"
echo "── $CURRENT_STEP ──"
uv run python scripts/compile_grid.py
echo

# Step 5: Assemble
CURRENT_STEP="5/7: Assemble all features"
echo "── $CURRENT_STEP ──"
uv run python scripts/assemble_grid.py
echo

# Step 6: Export
CURRENT_STEP="6/7: Export consumer formats"
echo "── $CURRENT_STEP ──"
uv run python scripts/export_zarr.py
uv run python scripts/export_dataframe.py
echo

# Step 7: Health check
CURRENT_STEP="7/7: Health check"
echo "── $CURRENT_STEP ──"
uv run python scripts/check_health.py
echo

# Success — remove any stale failure sentinel
rm -f "$ALERT_FILE"

echo "========================================"
echo "Pipeline refresh complete"
echo "Finished: $(date -Iseconds)"
echo "========================================"
