#!/bin/bash
set -e

echo "🧪 Plexus CLI Test Runner"
echo "========================="

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $2"
    else
        echo -e "${RED}✗${NC} $2"
        return 1
    fi
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Ensure we're in the right directory
cd "$(dirname "$0")/.."

echo "Current directory: $(pwd)"
echo

# Test 1: Quick smoke test
echo "1. Running CLI smoke test..."
if python tests/cli/test_cli_smoke.py; then
    print_status 0 "Smoke test passed"
else
    print_status 1 "Smoke test failed"
    exit 1
fi
echo

# Test 2: Basic command availability
echo "2. Testing command availability..."

commands=("score" "scorecard" "scorecards" "evaluate" "command worker" "report")
for cmd in "${commands[@]}"; do
    if plexus $cmd --help >/dev/null 2>&1; then
        print_status 0 "plexus $cmd"
    else
        print_status 1 "plexus $cmd"
        echo "   STDERR: $(plexus $cmd --help 2>&1 | head -3)"
    fi
done
echo

# Test 3: Import validation
echo "3. Testing critical imports..."
python -c "
import sys

critical_imports = [
    'plexus.cli.shared.CommandLineInterface',
    'plexus.cli.shared.CommandTasks',
    'plexus.cli.shared.CommandDispatch',
    'plexus.cli.score.scores',
    'plexus.cli.scorecard.scorecards'
]

failed = False
for module_name in critical_imports:
    try:
        __import__(module_name)
        print(f'✓ {module_name}')
    except ImportError as e:
        print(f'✗ {module_name}: {e}')
        failed = True

if failed:
    sys.exit(1)
"

if [ $? -eq 0 ]; then
    print_status 0 "All critical imports work"
else
    print_status 1 "Some imports failed"
    exit 1
fi
echo

# Test 4: Entry point validation
echo "4. Testing entry points..."

# Test plexus command
if plexus --help >/dev/null 2>&1; then
    print_status 0 "plexus command entry point"
else
    print_status 1 "plexus command entry point"
    exit 1
fi

# Test module execution
if python -m plexus.cli.shared.CommandLineInterface --help >/dev/null 2>&1; then
    print_status 0 "Module execution entry point"
else
    print_status 1 "Module execution entry point"
    exit 1
fi
echo

# Test 5: Regression tests (if requested)
if [ "$1" = "--full" ] || [ "$1" = "--regression" ]; then
    echo "5. Running full integration tests..."
    if python -m pytest tests/cli/test_cli_integration.py -v; then
        print_status 0 "Full integration tests"
    else
        print_status 1 "Full integration tests"
        exit 1
    fi
    echo
fi

echo -e "${GREEN}🎉 All CLI tests passed!${NC}"
echo
echo "To run full integration tests: $0 --full"
echo "To run in CI mode: python -m pytest tests/cli/ -v"
