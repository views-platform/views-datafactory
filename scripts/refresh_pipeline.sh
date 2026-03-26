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

echo "========================================"
echo "VIEWS Data Factory — Pipeline Refresh"
echo "Started: $(date -Iseconds)"
echo "========================================"
echo

# Step 1: Harvest
echo "── Step 1/7: Harvest raw data ──"
uv run python scripts/harvest_ucdp.py
uv run python scripts/harvest_priogrid.py
uv run python scripts/harvest_gaul.py
echo

# Step 2: Consolidate
echo "── Step 2/7: Consolidate UCDP sources ──"
uv run python scripts/consolidate_ucdp.py
echo

# Step 3: Build viewpoint
echo "── Step 3/7: Build viewpoint ──"
uv run python scripts/build_viewpoint.py
echo

# Step 4: Compile grid
echo "── Step 4/7: Compile to PRIO-GRID ──"
uv run python scripts/compile_grid.py
echo

# Step 5: Assemble
echo "── Step 5/7: Assemble all features ──"
uv run python scripts/assemble_grid.py
echo

# Step 6: Export
echo "── Step 6/7: Export consumer formats ──"
uv run python scripts/export_zarr.py
uv run python scripts/export_dataframe.py
echo

# Step 7: Health check
echo "── Step 7/7: Health check ──"
uv run python scripts/check_health.py
echo

echo "========================================"
echo "Pipeline refresh complete"
echo "Finished: $(date -Iseconds)"
echo "========================================"
