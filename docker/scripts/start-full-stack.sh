#!/bin/bash
set -e

# Quick start script for full stack local testing

echo "🚀 Starting Plexus Full Stack Local Environment"
echo "================================================"
echo ""

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

# Check if .env.full-stack exists
if [ ! -f "$PROJECT_ROOT/docker/.env.full-stack" ]; then
    echo "❌ Error: .env.full-stack not found"
    echo ""
    echo "Please create it from the example:"
    echo "  cp docker/.env.full-stack.example docker/.env.full-stack"
    echo "  # Edit docker/.env.full-stack with your credentials"
    echo ""
    exit 1
fi

echo "✅ Configuration found"
echo ""

# Start services
echo "📦 Starting services..."
echo ""
cd "$PROJECT_ROOT"
docker-compose -f docker/docker-compose.full-stack.yml --env-file docker/.env.full-stack up -d

echo ""
echo "⏳ Waiting for services to be healthy..."
echo ""

# Wait for services
sleep 5

# Check health
echo "🏥 Checking service health..."
echo ""

# Check RabbitMQ
if curl -s -u plexus:plexus http://localhost:15672/api/overview > /dev/null 2>&1; then
    echo "✅ RabbitMQ is running"
else
    echo "❌ RabbitMQ is not responding"
fi

# Check PostgreSQL
if docker-compose -f "$PROJECT_ROOT/docker/docker-compose.full-stack.yml" exec -T postgres pg_isready -U plexus > /dev/null 2>&1; then
    echo "✅ PostgreSQL is running"
else
    echo "❌ PostgreSQL is not responding"
fi

# Check GraphQL Proxy
if curl -s http://localhost:18080/healthz > /dev/null 2>&1; then
    echo "✅ GraphQL Proxy is running"
else
    echo "❌ GraphQL Proxy is not responding"
fi

# Check Worker
if docker-compose -f "$PROJECT_ROOT/docker/docker-compose.full-stack.yml" ps plexus-worker-celery | grep -q "Up"; then
    echo "✅ Plexus Worker is running"
else
    echo "❌ Plexus Worker is not running"
fi

echo ""
echo "================================================"
echo "🎉 Full Stack is Running!"
echo "================================================"
echo ""
echo "📊 Access Points:"
echo "  - RabbitMQ UI:    http://localhost:15672 (plexus/plexus)"
echo "  - GraphQL Proxy:  http://localhost:18080/graphql"
echo "  - PostgreSQL:     localhost:55432 (plexus/plexus)"
echo ""
echo "📝 Next Steps:"
echo "  1. Send a test job:"
echo "     python docker/scripts/send_test_job.py --health-check"
echo ""
echo "  2. Monitor worker logs:"
echo "     docker-compose -f docker/docker-compose.full-stack.yml logs -f plexus-worker-celery"
echo ""
echo "  3. View RabbitMQ queues:"
echo "     open http://localhost:15672"
echo ""
echo "  4. Stop services:"
echo "     docker-compose -f docker/docker-compose.full-stack.yml down"
echo ""
echo "📖 Full documentation: docker/FULL_STACK_LOCAL.md"
echo ""
