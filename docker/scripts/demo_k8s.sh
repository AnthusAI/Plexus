#!/bin/bash
set -e

echo "🎯 Kubernetes Demo - Call Center Quality Scoring"
echo "================================================="
echo ""
echo "This demo uses:"
echo "  - Public call-center data (demo-safe, no client data)"
echo "  - Kubernetes-deployed Plexus stack"
echo "  - Existing scorecard from AppSync backend"
echo ""

# Use the scorecard ID directly to avoid ambiguity with duplicate keys
# This is the second scorecard with champion versions set
SCORECARD="${SCORECARD:-c4793cf3-3ba3-4e30-a24a-f9b51f91ab09}"
SCORE="${1}"
NAMESPACE="${NAMESPACE:-plexus-local}"
PROXY_URL="${PROXY_URL:-http://localhost:8000}"

# Example call-center transcript (fictional)
TRANSCRIPT="Agent: Good afternoon, thank you for calling TechSupport Inc. My name is Sarah, how may I assist you today?

Customer: Hi Sarah, I'm having trouble with my internet connection. It keeps dropping every few minutes.

Agent: I understand how frustrating that must be. Let me help you troubleshoot this. Can you tell me if this started recently or has it been happening for a while?

Customer: It started about two days ago. I haven't changed anything on my end.

Agent: Thank you for that information. Let's start by checking a few things. First, could you please restart your modem by unplugging it for 30 seconds and then plugging it back in?

Customer: Okay, give me a moment... Alright, it's back on now.

Agent: Perfect. While we wait for it to fully reconnect, let me check your account status on our end. I can see your connection has been stable for the past few months until recently. There might be an issue with the local network in your area. Let me run a diagnostic test.

Customer: Okay, thank you.

Agent: The diagnostic shows there's some signal interference. I'm going to schedule a technician to come out and check the line. Would tomorrow between 2-5 PM work for you?

Customer: Yes, that works for me.

Agent: Excellent. I've scheduled the appointment and you'll receive a confirmation email shortly. The technician will call you 30 minutes before arrival. Is there anything else I can help you with today?

Customer: No, that's everything. Thank you for your help, Sarah.

Agent: You're very welcome! Thank you for calling TechSupport Inc. Have a great day!"

if [ -z "$SCORE" ]; then
    echo "❌ Please provide a score name as the first argument"
    echo ""
    echo "Usage: ./demo_k8s.sh <score-name>"
    echo ""
    echo "Available demo scores:"
    echo "  - ProfessionalTone"
    echo "  - ActiveListening"
    echo "  - ProperCallOpening"
    echo "  - ProperCallClosing"
    echo "  - ProblemResolution"
    echo ""
    echo "Example:"
    echo "  ./demo_k8s.sh ProfessionalTone"
    echo ""
    echo "To use a different scorecard, set SCORECARD environment variable:"
    echo "  SCORECARD=my_scorecard ./demo_k8s.sh MyScore"
    echo ""
    exit 1
fi

echo "📊 Scorecard: $SCORECARD"
echo "📈 Score: $SCORE"
echo "🔗 Proxy: $PROXY_URL"
echo "📦 Namespace: $NAMESPACE"
echo ""

# Step 1: Create a test item with demo transcript
echo "1️⃣  Creating test item with call-center transcript..."
ITEM_RESPONSE=$(curl -s -X POST $PROXY_URL/graphql \
  -H "Content-Type: application/json" \
  -H "x-api-key: local-dev-key" \
  -d "{
    \"query\": \"mutation CreateItem(\$input: CreateItemInput!) { createItem(input: \$input) { id accountId text } }\",
    \"variables\": {
      \"input\": {
        \"accountId\": \"demo-account\",
        \"text\": $(echo "$TRANSCRIPT" | python3 -c "import sys, json; print(json.dumps(sys.stdin.read()))"),
        \"externalId\": \"demo-k8s-$(date +%s)\",
        \"isEvaluation\": false,
        \"createdByType\": \"prediction\"
      }
    }
  }")

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
JOB_ID="demo-job-$(uuidgen | tr '[:upper:]' '[:lower:]')"
echo "2️⃣  Using job ID: $JOB_ID"
echo ""

# Step 3: Submit to RabbitMQ
echo "3️⃣  Submitting scoring job to RabbitMQ..."
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

print(f'Task ID: {result.id}')
print('Waiting for result...')

try:
    task_result = result.get(timeout=120)
    print('✅ Success!')
    print('='*60)
    print(f\"Score: {task_result.get('value')}\")
    print(f\"Explanation: {task_result.get('explanation')}\")
    print('='*60)
    sys.exit(0)
except Exception as e:
    print(f'❌ Error: {e}')
    sys.exit(1)
"

RESULT=$?

echo ""
if [ $RESULT -eq 0 ]; then
    echo "✅ DEMO COMPLETE!"
    echo ""
    echo "💡 This demo used:"
    echo "   - Public call-center dialogue (no client data)"
    echo "   - Generic quality scorecard (demo_call_center_quality)"
    echo "   - Kubernetes-deployed Plexus stack"
    echo ""
    echo "To view worker logs:"
    echo "  kubectl logs -n $NAMESPACE -l app.kubernetes.io/name=plexus-worker --tail=50"
else
    echo "❌ Demo failed. Check worker logs:"
    echo "  kubectl logs -n $NAMESPACE -l app.kubernetes.io/name=plexus-worker --tail=50"
fi
