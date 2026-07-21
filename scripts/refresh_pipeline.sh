#!/usr/bin/env bash
# Full pipeline refresh — harvest, compile, export.
#
# Usage:
#   bash scripts/refresh_pipeline.sh
#
# This script runs the entire data pipeline end-to-end:
#   0.  Pre-flight checks (credentials, disk space)
#   1.  Harvest raw data from UCDP, PRIO-GRID, GAUL, ACLED, GHS-POP, GHS-BUILT-S, V-Dem, SHDI
#   2.  Consolidate UCDP sources into event store
#   3.  Build viewpoint (survivorship + distribution + filtering)
#   4.  Compile UCDP grid
#   5.  Compile ACLED grid (consolidate + viewpoint + compile)
#   6.  Compile GHS-POP grid (viewpoint + compile, no consolidation)
#   7.  Compile GHS-BUILT-S grid (viewpoint + compile, no consolidation)
#   8.  Compile V-Dem grid (viewpoint + compile, no consolidation)
#   9.  Compile SHDI grid (viewpoint + compile, no consolidation — ADR-036)
#  10.  Assemble all features (UCDP + ACLED + GHS-POP + GHS-BUILT-S + V-Dem + SHDI + static + admin)
#  11.  Export to consumer formats (zarr, parquet)
#  12.  Run health check
#  13.  Verify consumer contract — freshness + plausibility (#323)
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
    # Immediate dead-man alert (C-131): the success ping at the end
    # of the script never fires on failure, so healthchecks would
    # only alert at the next missed schedule (up to the grace
    # period). /fail flips the check to failing right now. The
    # || true guard must stay — an unreachable monitoring service
    # must never mask the original exit code under set -e.
    if [ -n "${HEARTBEAT_URL:-}" ]; then
        curl -fsS --max-time 10 "$HEARTBEAT_URL/fail" >/dev/null 2>&1 || true
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
    if [ -f "data/status.html" ]; then
        echo "  Status page: http://204.168.219.108/status.html"
    else
        echo "  WARNING: data/status.html not found after generation"
    fi
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
echo "$$" >&200
# Child writer scripts check this instead of contending with
# their own parent's flock (C-316; see pipeline_lock.py).
export VIEWS_PIPELINE_LOCK_HELD=1

# Start-ping (C-317): SIGKILL (OOM killer) bypasses the ERR and
# EXIT traps, so a killed run would otherwise leave no signal at
# all until the next monthly schedule lapses. The /start ping
# leaves a dangling "started" state that healthchecks flags at
# the grace timeout (~24h) instead.
if [ -n "${HEARTBEAT_URL:-}" ]; then
    curl -fsS --max-time 10 "$HEARTBEAT_URL/start" >/dev/null 2>&1 || true
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
CURRENT_STEP="0/14: Pre-flight checks"
echo "── $CURRENT_STEP ──"
uv run python scripts/preflight.py
echo

# Step 1: Harvest
CURRENT_STEP="1/14: Harvest raw data"
echo "── $CURRENT_STEP ──"
uv run python scripts/harvest_ucdp.py
uv run python scripts/harvest_priogrid.py
uv run python scripts/harvest_shapefile.py
uv run python scripts/harvest_gaul.py
uv run python scripts/generate_area_majority_gaul.py \
    --data-dir data/raw/gaul_admin \
    --ledger-path provenance/gaul_admin/ingestion_ledger.jsonl \
    --supplement data/raw/gaul_admin/supplement_azores.geojson
uv run python scripts/harvest_acled.py
uv run python scripts/harvest_ghspop.py
uv run python scripts/harvest_ghsbuilts.py
uv run python scripts/harvest_vdem.py
uv run python scripts/harvest_shdi.py
echo

# Step 2: Consolidate
CURRENT_STEP="2/14: Consolidate UCDP sources"
echo "── $CURRENT_STEP ──"
uv run python scripts/consolidate_ucdp.py
echo

# Step 3: Build viewpoint
CURRENT_STEP="3/14: Build viewpoint"
echo "── $CURRENT_STEP ──"
uv run python scripts/build_viewpoint.py
echo

# Step 4: Compile UCDP grid
CURRENT_STEP="4/14: Compile UCDP to PRIO-GRID"
echo "── $CURRENT_STEP ──"
uv run python scripts/compile_grid.py
echo

# Step 5: Compile ACLED grid
CURRENT_STEP="5/14: Compile ACLED to PRIO-GRID"
echo "── $CURRENT_STEP ──"
uv run python scripts/run_acled_pipeline.py --skip-to consolidate
echo

# Step 6: Compile GHS-POP grid (no consolidation — ADR-029)
CURRENT_STEP="6/14: Compile GHS-POP to PRIO-GRID"
echo "── $CURRENT_STEP ──"
uv run python scripts/run_ghspop_pipeline.py --skip-to viewpoint
echo

# Step 7: Compile GHS-BUILT-S grid (no consolidation — ADR-034)
CURRENT_STEP="7/14: Compile GHS-BUILT-S to PRIO-GRID"
echo "── $CURRENT_STEP ──"
uv run python scripts/run_ghsbuilts_pipeline.py --skip-to viewpoint
echo

# Step 8: Compile V-Dem grid (no consolidation — ADR-035)
CURRENT_STEP="8/14: Compile V-Dem to PRIO-GRID"
echo "── $CURRENT_STEP ──"
uv run python scripts/run_vdem_pipeline.py --skip-to viewpoint
echo

# Step 9: Compile SHDI grid (no consolidation — ADR-036)
CURRENT_STEP="9/14: Compile SHDI to PRIO-GRID"
echo "── $CURRENT_STEP ──"
uv run python scripts/run_shdi_pipeline.py --skip-to viewpoint
echo

# Step 10: Assemble
CURRENT_STEP="10/14: Assemble all features"
echo "── $CURRENT_STEP ──"
uv run python scripts/assemble_grid.py \
    --acled-grid data/compiled/acled \
    --ghspop-grid data/compiled/ghspop \
    --ghsbuilts-grid data/compiled/ghsbuilts \
    --vdem-grid data/compiled/vdem \
    --shdi-grid data/compiled/shdi \
    --skip-if-unchanged
echo

# Step 11: Export
CURRENT_STEP="11/14: Export consumer formats"
echo "── $CURRENT_STEP ──"
uv run python scripts/export_zarr.py --skip-if-unchanged
uv run python scripts/export_dataframe.py
echo

# Step 12: Health check
CURRENT_STEP="12/14: Health check"
echo "── $CURRENT_STEP ──"
uv run python scripts/check_health.py
echo

# Step 13: Consumer contract verification (#323)
# Freshness (C-313 detector) + plausibility (C-314 detector),
# checked at the consumer boundary via load_dataset(). Replaces
# verify_remote_data.py in the nightly path — that script compares
# against the operator's LOCAL grid copy and false-alarms when the
# local copy is stale (62 false MISMATCHes on 2026-07-05).
CURRENT_STEP="13/14: Verify consumer contract"
echo "── $CURRENT_STEP ──"
uv run python scripts/verify_consumer_contract.py
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
