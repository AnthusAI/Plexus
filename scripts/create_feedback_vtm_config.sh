#!/usr/bin/env bash
# Create the Feedback Analysis + Vector Topic Memory report config (one-time setup).
# After this, use Lab > Reports > Run Report in the dashboard, or run_feedback_vtm_report.sh

set -e
cd "$(dirname "$0")/.."

python -m plexus.cli.CommandLineInterface report config create \
  --name "Feedback Analysis + Vector Topic Memory" \
  --file feedback_and_vector_topic_memory_report.md \
  --description "Feedback analysis + Vector Topic Memory (OpenSearch clustering)"

echo ""
echo "Config created. Now run a report via:"
echo "  - Dashboard: Lab > Reports > Run Report (select this config, enter scorecard + days)"
echo "  - CLI: ./scripts/run_feedback_vtm_report.sh [scorecard_id] [days]"
