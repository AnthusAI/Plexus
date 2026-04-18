#!/usr/bin/env bash
# Run the Feedback Analysis + Vector Topic Memory report.
#
# Usage:
#   ./scripts/run_feedback_vtm_report.sh [scorecard_id] [days]
#   Default: scorecard=1438 (SelectQuote HCS Medium-Risk), days=10
#
# Prerequisite: Create the report config first (one-time):
#   plexus report config create \
#     --name "Feedback Analysis + Vector Topic Memory" \
#     --file feedback_and_vector_topic_memory_report.md
#
# Or use the Dashboard: Lab > Reports > Run Report, select the config, enter scorecard + days.

set -e
cd "$(dirname "$0")/.."

CONFIG_NAME="Feedback Analysis + Vector Topic Memory"
SCORECARD="${1:-1438}"
DAYS="${2:-10}"

echo "=== Feedback + Vector Topic Memory Report ==="
echo "Config: $CONFIG_NAME"
echo "Scorecard: $SCORECARD | Days: $DAYS"
echo ""

plexus report run \
  --config "$CONFIG_NAME" \
  scorecard="$SCORECARD" \
  days="$DAYS"

echo ""
echo "Done. Check Lab > Reports in the dashboard."
