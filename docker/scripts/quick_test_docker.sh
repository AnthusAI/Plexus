#!/bin/bash
set -e

echo "🚀 Quick End-to-End Scoring Test"
echo "=================================="
echo ""

SCORECARD="moore_holdings_traditional_ai_test"
SCORE="${1:-}"

if [ -z "$SCORE" ]; then
    echo "❌ Please provide a score name as the first argument"
    echo ""
    echo "Usage: ./quick_test_docker.sh <score-name>"
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

# Step 3: Submit to RabbitMQ from inside the worker container
echo "3️⃣  Submitting to RabbitMQ queue..."

docker-compose -f docker-compose.full-stack.yml exec -T plexus-worker-celery python3 -c "
from celery import Celery
import sys
import os

# Use internal Docker network addresses
app = Celery('test', broker='amqp://plexus:plexus@rabbitmq:5672/', backend='rpc://plexus:plexus@rabbitmq:5672/')

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

print(f'   ✅ Task ID: {result.id}')
print('')
print('4️⃣  Waiting for worker to process (timeout: 120s)...')

try:
    task_result = result.get(timeout=120)
    print('')
    print('   ✅ Task completed successfully!')
    print('')
    import json
    print('   Result:')
    print(json.dumps(task_result, indent=2))
    sys.exit(0)
except Exception as e:
    print(f'')
    print(f'   ❌ Error: {e}')
    sys.exit(1)
"

RESULT=$?

echo ""
if [ $RESULT -eq 0 ]; then
    echo "5️⃣  Checking database for stored result..."
    docker-compose -f docker-compose.full-stack.yml exec -T postgres \
      psql -U plexus -d plexus_proxy -c "
        SELECT
          id,
          scorecard_id,
          score_id,
          doc->>'value' as value,
          doc->>'reasoning' as reasoning,
          created_at
        FROM private_data.score_results
        WHERE scoring_job_id = '$JOB_ID'
        ORDER BY created_at DESC;
      "

    echo ""
    echo "================================================"
    echo "✅ END-TO-END TEST COMPLETE!"
    echo "================================================"
    echo ""
    echo "Summary:"
    echo "  • Item created in PostgreSQL: $ITEM_ID"
    echo "  • Job submitted to RabbitMQ: $JOB_ID"
    echo "  • Worker processed successfully"
    echo "  • Result stored in PostgreSQL"
    echo ""
else
    echo "❌ Task failed. Check worker logs:"
    echo "   docker-compose -f docker-compose.full-stack.yml logs plexus-worker-celery --tail=50"
fi
