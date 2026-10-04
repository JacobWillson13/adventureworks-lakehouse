#!/usr/bin/env bash
# Copy data/raw/*.csv into the Unity Catalog landing volume.
# Requires: Databricks CLI authenticated, and the aw_setup job run once.
# Usage: scripts/upload_raw.sh [catalog]     (default catalog: workspace)
set -euo pipefail
cd "$(dirname "$0")/.."

CATALOG="${1:-workspace}"
DEST="dbfs:/Volumes/${CATALOG}/aw_raw/landing"

n_local=$(find data/raw -maxdepth 1 -name '*.csv' | wc -l)
echo "Uploading ${n_local} files to ${DEST}"
for f in data/raw/*.csv; do
  databricks fs cp --overwrite "$f" "${DEST}/$(basename "$f")"
done

n_remote=$(databricks fs ls "$DEST" | grep -c '\.csv$' || true)
echo "Volume now holds ${n_remote} CSV files (local: ${n_local})"
[[ "$n_remote" -eq "$n_local" ]] || { echo "Count mismatch"; exit 1; }
