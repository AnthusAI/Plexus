#!/bin/bash
set -e

echo "🚀 Quick End-to-End Scoring Test"
echo "=================================="
echo ""

SCORECARD="moore_holdings_traditional_ai_test"
SCORE="${1:-}"  # Pass score name as first argument

if [ -z "$SCORE" ]; then
    echo "❌ Please provide a score name as the first argument"
    echo ""
    echo "Usage: ./quick_test.sh <score-name>"
    echo ""
    echo "To see available scores:"
    echo "  docker-compose -f docker-compose.full-stack.yml exec plexus-worker-celery \\"
    echo "    plexus scorecard describe moore_holdings_traditional_ai_test"
    echo ""
    exit 1
fi

echo "📊 Scorecard: $SCORECARD"
echo "📈 Score: $SCORE"
echo ""

# Step 1: Create a test item
echo "1️⃣  Creating test item..."
ITEM_RESPONSE=$(curl -s -X POST http://localhost:18080/graphql \
  -H "Content-Type: application/json" \
  -H "x-api-key: local-dev-key" \
  -d '{
    "query": "mutation CreateItem($input: CreateItemInput!) { createItem(input: $input) { id accountId text } }",
    "variables": {
      "input": {
        "accountId": "call-criteria",
        "text": "This is a test call transcript for scoring. The agent was polite and helpful.",
        "externalId": "quick-test-'$(date +%s)'",
        "isEvaluation": false,
        "createdByType": "prediction"
      }
    }
  }')

ITEM_ID=$(echo "$ITEM_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['data']['createItem']['id'])")
echo "   ✅ Created item: $ITEM_ID"
echo ""

# Step 2: Generate a scoring job ID
JOB_ID="test-job-$(uuidgen | tr '[:upper:]' '[:lower:]')"
echo "2️⃣  Using job ID: $JOB_ID"
echo ""

# Step 3: Submit to RabbitMQ
echo "3️⃣  Submitting to RabbitMQ queue..."
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
    echo "4️⃣  Checking database for result..."
    docker-compose -f docker-compose.full-stack.yml exec -T postgres \
      psql -U plexus -d plexus_proxy -c "SELECT id, value, reasoning FROM score_results WHERE scoring_job_id = '$JOB_ID';"

    echo ""
    echo "✅ TEST COMPLETE!"
else
    echo "❌ Task failed. Check worker logs:"
    echo "   docker-compose -f docker-compose.full-stack.yml logs plexus-worker-celery --tail=50"
fi
