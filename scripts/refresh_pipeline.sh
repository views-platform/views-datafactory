#!/usr/bin/env bash
# Full pipeline refresh — harvest, compile, export.
#
# Usage:
#   bash scripts/refresh_pipeline.sh
#
# This script runs the entire data pipeline end-to-end:
#   0.  Pre-flight checks (credentials, disk space)
#   1.  Harvest raw data from UCDP, PRIO-GRID, GAUL, ACLED, GHS-POP, GHS-BUILT-S, V-Dem
#   2.  Consolidate UCDP sources into event store
#   3.  Build viewpoint (survivorship + distribution + filtering)
#   4.  Compile UCDP grid
#   5.  Compile ACLED grid (consolidate + viewpoint + compile)
#   6.  Compile GHS-POP grid (viewpoint + compile, no consolidation)
#   7.  Compile GHS-BUILT-S grid (viewpoint + compile, no consolidation)
#   8.  Compile V-Dem grid (viewpoint + compile, no consolidation)
#   9.  Assemble all features (UCDP + ACLED + GHS-POP + GHS-BUILT-S + V-Dem + static + admin)
#  10.  Export to consumer formats (zarr, parquet)
#  11.  Run health check
#  12.  Verify remote data correctness (C-138)
#
# Status page (EXIT trap):
#   generate_status.py runs on exit — success or failure — via
#   trap EXIT. This ensures the status page reflects the pipeline's
#   final state even when a step crashes (C-237).
#
# Deployment gate:
#   Before running any steps, the script reads ~/.views-deploy-tag
#   to find which tagged release to run (e.g., "v1.1.0"). It then
#   checks out that exact tag. This means the server always runs a
#   specific, tested version — not whatever happens to be on a branch.
#   If the file is missing, empty, or the tag doesn't exist, the script
#   stops immediately (fail-loud, ADR-011). See ADR-022 for rationale.
#
#   To deploy a new version: update ~/.views-deploy-tag on the server.
#   To roll back: write the old tag name to ~/.views-deploy-tag.
#   See docs/guides/hetzner_deployment_guide.md for full details.
#
# Requires:
#   - ~/.views-deploy-tag file containing a valid git tag
#   - UCDP_API_TOKEN environment variable
#   - ACLED_USERNAME and ACLED_PASSWORD environment variables
#   - Internet access (for UCDP, PRIO-GRID, GAUL, ACLED APIs)
#   - uv installed
#
# The script stops on first error (set -e). Check output for
# which step failed. Each step writes provenance to provenance/.
#
# For cron:  0 0 21 * * cd /path/to/views-datafactory && bash scripts/refresh_pipeline.sh 2>&1 | tee -a logs/refresh.log
# Manual:    sudo -u views-deploy bash -c 'source ~/.profile && cd ~/views-datafactory && bash scripts/refresh_pipeline.sh 2>&1 | tee -a logs/refresh.log'

set -euo pipefail

# ---- Environment ----
# Cron runs with minimal PATH; ensure uv and cargo binaries are available.
export PATH="$HOME/.cargo/bin:$HOME/.local/bin:/usr/local/bin:$PATH"

# Source env vars (UCDP_API_TOKEN, etc.) for non-interactive shells.
# .bashrc exits early when PS1 is unset (non-interactive), so env vars
# defined after that guard are unreachable. Use .profile instead.
if [ -f "$HOME/.profile" ]; then
    set +u
    # shellcheck source=/dev/null
    source "$HOME/.profile"
    set -u
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

# ---- Status page (C-237) ----
# Runs on exit regardless of success or failure. The status page is
# most valuable when a step has failed — it shows which stage broke.
# || echo ensures generation failure doesn't mask the real exit code.
generate_status_on_exit() {
    echo
    echo "── Generating status page ──"
    uv run python scripts/generate_status.py \
        --output data/status.html \
        || echo "Warning: status page generation failed (non-fatal)"
}
trap generate_status_on_exit EXIT

# ---- Deployment gate (C-98) ----
# The pipeline only runs a specific tagged release. Operators set the
# tag in ~/.views-deploy-tag. Without this file, the pipeline refuses
# to start (fail-loud per ADR-011).
DEPLOY_TAG_FILE="$HOME/.views-deploy-tag"
if [ ! -f "$DEPLOY_TAG_FILE" ]; then
    echo "FATAL: No deploy tag file at $DEPLOY_TAG_FILE"
    echo "Create it with: echo 'v1.0.0' > $DEPLOY_TAG_FILE"
    exit 1
fi

DEPLOY_TAG=$(tr -d '[:space:]' < "$DEPLOY_TAG_FILE")
if [ -z "$DEPLOY_TAG" ]; then
    echo "FATAL: Deploy tag file is empty: $DEPLOY_TAG_FILE"
    exit 1
fi

git fetch --tags --quiet
if ! git rev-parse "$DEPLOY_TAG" >/dev/null 2>&1; then
    echo "FATAL: Tag '$DEPLOY_TAG' not found in repository"
    exit 1
fi

# uv sync writes platform-specific changes to uv.lock which blocks
# git checkout on the next deploy. Safe to discard — we never commit
# on the server.
git checkout -- uv.lock 2>/dev/null || true
git checkout "$DEPLOY_TAG" --quiet

# ---- Concurrent execution guard (C-147) ----
LOCK_FILE="/var/lock/views-pipeline.lock"
exec 200>"$LOCK_FILE"
if ! flock -n 200; then
    echo "FATAL: Another pipeline run is already in progress (lock: $LOCK_FILE)"
    exit 1
fi

PIPELINE_START=$(date +%s)
PIPELINE_START_ISO=$(date -Iseconds)

echo "========================================"
echo "VIEWS Data Factory — Pipeline Refresh"
echo "Deploy tag: $DEPLOY_TAG"
echo "Started: $PIPELINE_START_ISO"
echo "========================================"
echo

# Step 0: Pre-flight checks (credentials, disk space)
CURRENT_STEP="0/13: Pre-flight checks"
echo "── $CURRENT_STEP ──"
uv run python scripts/preflight.py
echo

# Step 1: Harvest
CURRENT_STEP="1/13: Harvest raw data"
echo "── $CURRENT_STEP ──"
uv run python scripts/harvest_ucdp.py
uv run python scripts/harvest_priogrid.py
uv run python scripts/harvest_shapefile.py
uv run python scripts/harvest_gaul.py
uv run python scripts/generate_area_majority_gaul.py \
    --data-dir data/raw/gaul_admin \
    --ledger-path provenance/gaul_admin/ingestion_ledger.jsonl
uv run python scripts/harvest_acled.py
uv run python scripts/harvest_ghspop.py
uv run python scripts/harvest_ghsbuilts.py
uv run python scripts/harvest_vdem.py
echo

# Step 2: Consolidate
CURRENT_STEP="2/13: Consolidate UCDP sources"
echo "── $CURRENT_STEP ──"
uv run python scripts/consolidate_ucdp.py
echo

# Step 3: Build viewpoint
CURRENT_STEP="3/13: Build viewpoint"
echo "── $CURRENT_STEP ──"
uv run python scripts/build_viewpoint.py
echo

# Step 4: Compile UCDP grid
CURRENT_STEP="4/13: Compile UCDP to PRIO-GRID"
echo "── $CURRENT_STEP ──"
uv run python scripts/compile_grid.py
echo

# Step 5: Compile ACLED grid
CURRENT_STEP="5/13: Compile ACLED to PRIO-GRID"
echo "── $CURRENT_STEP ──"
uv run python scripts/run_acled_pipeline.py --skip-to consolidate
echo

# Step 6: Compile GHS-POP grid (no consolidation — ADR-029)
CURRENT_STEP="6/13: Compile GHS-POP to PRIO-GRID"
echo "── $CURRENT_STEP ──"
uv run python scripts/run_ghspop_pipeline.py --skip-to viewpoint
echo

# Step 7: Compile GHS-BUILT-S grid (no consolidation — ADR-034)
CURRENT_STEP="7/13: Compile GHS-BUILT-S to PRIO-GRID"
echo "── $CURRENT_STEP ──"
uv run python scripts/run_ghsbuilts_pipeline.py --skip-to viewpoint
echo

# Step 8: Compile V-Dem grid (no consolidation — ADR-035)
CURRENT_STEP="8/13: Compile V-Dem to PRIO-GRID"
echo "── $CURRENT_STEP ──"
uv run python scripts/run_vdem_pipeline.py --skip-to viewpoint
echo

# Step 9: Assemble
CURRENT_STEP="9/13: Assemble all features"
echo "── $CURRENT_STEP ──"
uv run python scripts/assemble_grid.py \
    --acled-grid data/compiled/acled \
    --ghspop-grid data/compiled/ghspop \
    --ghsbuilts-grid data/compiled/ghsbuilts \
    --vdem-grid data/compiled/vdem
echo

# Step 10: Export
CURRENT_STEP="10/13: Export consumer formats"
echo "── $CURRENT_STEP ──"
uv run python scripts/export_zarr.py
uv run python scripts/export_dataframe.py
echo

# Step 11: Health check
CURRENT_STEP="11/13: Health check"
echo "── $CURRENT_STEP ──"
uv run python scripts/check_health.py
echo

# Step 12: Remote data verification (C-138)
CURRENT_STEP="12/13: Verify remote data"
echo "── $CURRENT_STEP ──"
uv run python scripts/verify_remote_data.py
echo

# Success — remove any stale failure sentinel
rm -f "$ALERT_FILE"

# Optional heartbeat for external monitoring (C-131).
# Set HEARTBEAT_URL to a healthchecks.io/cronitor/uptimerobot ping URL.
if [ -n "${HEARTBEAT_URL:-}" ]; then
    curl -fsS --max-time 10 "$HEARTBEAT_URL" >/dev/null 2>&1 || true
fi

# Record pipeline duration (C-91)
PIPELINE_END=$(date +%s)
PIPELINE_DURATION=$((PIPELINE_END - PIPELINE_START))
DURATION_FILE="logs/pipeline_duration.json"
mkdir -p logs
echo "{\"deploy_tag\": \"$DEPLOY_TAG\", \"started\": \"$PIPELINE_START_ISO\", \"finished\": \"$(date -Iseconds)\", \"duration_seconds\": $PIPELINE_DURATION}" > "$DURATION_FILE"

echo "========================================"
echo "Pipeline refresh complete"
echo "Duration: ${PIPELINE_DURATION}s"
echo "Finished: $(date -Iseconds)"
echo "========================================"
