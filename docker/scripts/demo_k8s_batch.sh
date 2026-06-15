#!/bin/bash
set -e

echo "🎯 Kubernetes Demo - Batch Scoring with Real Call-Center Data"
echo "=============================================================="
echo ""

SCORECARD="${SCORECARD:-demo_call_center_quality}"
SCORE="${1:-ProfessionalTone}"
NAMESPACE="${NAMESPACE:-plexus-local}"
ITEM_FILE="${2:-docker/scripts/demo_items.json}"

if [ ! -f "$ITEM_FILE" ]; then
    echo "❌ Item file not found: $ITEM_FILE"
    echo ""
    echo "Please run fetch_demo_transcripts.py first:"
    echo "  python docker/scripts/fetch_demo_transcripts.py --num-samples 10"
    echo ""
    exit 1
fi

if [ -z "$SCORE" ]; then
    echo "❌ Please provide a score name as the first argument"
    echo ""
    echo "Usage: ./demo_k8s_batch.sh <score-name> [items-file]"
    echo ""
    echo "Available scores:"
    echo "  - ProfessionalTone"
    echo "  - ActiveListening"
    echo "  - ProblemResolution"
    echo "  - ProperCallOpening"
    echo "  - ProperCallClosing"
    echo ""
    exit 1
fi

# Read item IDs from file
ITEM_IDS=($(python3 -c "import json; print(' '.join(json.load(open('$ITEM_FILE'))['item_ids']))"))
ITEM_COUNT=${#ITEM_IDS[@]}

echo "📊 Scorecard: $SCORECARD"
echo "📈 Score: $SCORE"
echo "📦 Items: $ITEM_COUNT transcripts"
echo "📂 Namespace: $NAMESPACE"
echo ""

echo "🚀 Submitting $ITEM_COUNT scoring jobs..."
echo ""

SUCCESS_COUNT=0
FAIL_COUNT=0

for i in "${!ITEM_IDS[@]}"; do
    ITEM_ID="${ITEM_IDS[$i]}"
    JOB_ID="demo-batch-$(uuidgen | tr '[:upper:]' '[:lower:]')"

    echo "[$((i+1))/$ITEM_COUNT] Processing item: $ITEM_ID"

    # Submit to RabbitMQ
    python3 -c "
from celery import Celery
import sys

app = Celery('test', broker='amqp://plexus:plexus@localhost:5672/', backend='rpc://plexus:plexus@localhost:5672/')

result = app.send_task(
    'plexus.workers.celery_tasks.process_scoring_job',
    args=['$JOB_ID'],
    kwargs={
        'scorecard_name': '$SCORECARD',
        'score_name': '$SCORE',
        'item_id': '$ITEM_ID',
        'account_key': 'demo-account'
    },
    queue='scoring-requests'
)

try:
    task_result = result.get(timeout=60)
    print(f\"  ✓ {task_result.get('value', 'N/A')}: {task_result.get('explanation', '')[:100]}...\")
    sys.exit(0)
except Exception as e:
    print(f'  ✗ Error: {e}')
    sys.exit(1)
" && ((SUCCESS_COUNT++)) || ((FAIL_COUNT++))

    echo ""
done

echo "="*60
echo "📊 Batch Scoring Results"
echo "="*60
echo "Total items: $ITEM_COUNT"
echo "Successful:  $SUCCESS_COUNT"
echo "Failed:      $FAIL_COUNT"
echo ""

if [ $SUCCESS_COUNT -gt 0 ]; then
    echo "✅ Demo completed successfully!"
    echo ""
    echo "💡 This demo used:"
    echo "   - Real call-center transcripts from HuggingFace dataset"
    echo "   - Generic quality scorecard (safe for public demos)"
    echo "   - Kubernetes-deployed Plexus stack"
else
    echo "❌ All items failed. Check worker logs:"
    echo "  kubectl logs -n $NAMESPACE -l app.kubernetes.io/name=plexus-worker --tail=100"
fi
