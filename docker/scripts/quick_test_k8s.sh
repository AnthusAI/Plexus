#!/bin/bash
set -e

echo "🚀 Kubernetes End-to-End Scoring Test"
echo "======================================"
echo ""

SCORECARD="moore_holdings_traditional_ai_test"
SCORE="${1:-}"  # Pass score name as first argument
NAMESPACE="${NAMESPACE:-plexus-local}"
PROXY_URL="${PROXY_URL:-http://localhost:8000}"

if [ -z "$SCORE" ]; then
    echo "❌ Please provide a score name as the first argument"
    echo ""
    echo "Usage: ./quick_test_k8s.sh <score-name>"
    echo ""
    echo "Example: ./quick_test_k8s.sh Courtesy"
    echo ""
    echo "Note: Make sure you've port-forwarded the proxy first:"
    echo "  kubectl port-forward -n $NAMESPACE svc/plexus-graphql-proxy 8000:8000"
    echo ""
    exit 1
fi

echo "📊 Scorecard: $SCORECARD"
echo "📈 Score: $SCORE"
echo "🔗 Proxy: $PROXY_URL"
echo "📦 Namespace: $NAMESPACE"
echo ""

# Step 1: Create a test item
echo "1️⃣  Creating test item..."
ITEM_RESPONSE=$(curl -s -X POST $PROXY_URL/graphql \
  -H "Content-Type: application/json" \
  -H "x-api-key: local-dev-key" \
  -d '{
    "query": "mutation CreateItem($input: CreateItemInput!) { createItem(input: $input) { id accountId text } }",
    "variables": {
      "input": {
        "accountId": "call-criteria",
        "text": "This is a test call transcript for scoring. The agent was polite and helpful.",
        "externalId": "quick-test-k8s-'$(date +%s)'",
        "isEvaluation": false,
        "createdByType": "prediction"
      }
    }
  }')

echo "Response: $ITEM_RESPONSE"

ITEM_ID=$(echo "$ITEM_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['data']['createItem']['id'])" 2>/dev/null || echo "")

if [ -z "$ITEM_ID" ]; then
    echo "❌ Failed to create item. Response:"
    echo "$ITEM_RESPONSE" | python3 -m json.tool || echo "$ITEM_RESPONSE"
    exit 1
fi

echo "   ✅ Created item: $ITEM_ID"
echo ""

# Give the database a moment to ensure the item is fully written
sleep 1

# Step 2: Generate a scoring job ID
JOB_ID="test-job-$(uuidgen | tr '[:upper:]' '[:lower:]')"
echo "2️⃣  Using job ID: $JOB_ID"
echo ""

# Step 3: Submit to RabbitMQ
echo "3️⃣  Submitting to RabbitMQ queue..."
python3 -c "
from celery import Celery
import sys

# Connect to RabbitMQ at host.docker.internal (from host perspective, it's localhost)
app = Celery('test', broker='amqp://plexus:plexus@localhost:5672/', backend='rpc://plexus:plexus@localhost:5672/')

result = app.send_task(
    'plexus.workers.celery_tasks.process_scoring_job',
    args=['$JOB_ID'],
    kwargs={
        'scorecard_name': '$SCORECARD',
        'score_name': '$SCORE',
        'item_id': '$ITEM_ID',
        'account_key': 'call-criteria'
    },
    queue='scoring-requests'
)

print(f'Task ID: {result.id}')
print('Waiting for result...')

try:
    task_result = result.get(timeout=120)
    print('✅ Success!')
    print(task_result)
    sys.exit(0)
except Exception as e:
    print(f'❌ Error: {e}')
    sys.exit(1)
"

RESULT=$?

echo ""
if [ $RESULT -eq 0 ]; then
    echo "✅ TEST COMPLETE!"
    echo ""
    echo "4️⃣  Checking database for result..."

    # Get postgres password
    POSTGRES_PASSWORD=$(kubectl get secret -n $NAMESPACE plexus-postgresql -o jsonpath="{.data.password}" | base64 -d)

    # Query the database via kubectl exec (note: score_results is in private_data schema)
    echo "   Items in database:"
    kubectl exec -n $NAMESPACE plexus-postgresql-0 -- \
      env PGPASSWORD="$POSTGRES_PASSWORD" psql -U plexus_proxy -d plexus_proxy \
      -c "SELECT id, account_id, doc->>'text' as text FROM private_data.items WHERE id = '$ITEM_ID';"

    echo ""
    echo "   Score results:"
    kubectl exec -n $NAMESPACE plexus-postgresql-0 -- \
      env PGPASSWORD="$POSTGRES_PASSWORD" psql -U plexus_proxy -d plexus_proxy \
      -c "SELECT id, doc->>'value' as value, doc->>'reasoning' as reasoning FROM private_data.score_results WHERE scoring_job_id = '$JOB_ID';" 2>&1 || \
      echo "   Note: Score result may not be persisted to database (returned via Celery result backend instead)"

    echo ""
    echo "To view worker logs:"
    echo "  kubectl logs -n $NAMESPACE -l app.kubernetes.io/name=plexus-worker --tail=50"
else
    echo "❌ Task failed. Check worker logs:"
    echo "  kubectl logs -n $NAMESPACE -l app.kubernetes.io/name=plexus-worker --tail=50"
fi
