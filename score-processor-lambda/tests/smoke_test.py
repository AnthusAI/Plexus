#!/usr/bin/env python3
"""
Container Smoke Test
Validates that the Lambda container has all required dependencies and can initialize.
This test is designed to run inside the Docker container.
"""
import asyncio
import sys
import os

# Set environment variables for container
os.environ.setdefault('SCORECARD_CACHE_DIR', '/tmp/scorecards')
os.environ.setdefault('NLTK_DATA', '/usr/local/share/nltk_data:/tmp/nltk_data')
os.environ['AWS_ACCESS_KEY_ID'] = 'test-access-key'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'test-secret-key'
os.environ['AWS_DEFAULT_REGION'] = 'us-west-2'
os.environ['PLEXUS_API_KEY'] = 'test-key'
os.environ['PLEXUS_API_URL'] = 'https://test.example.com/graphql'
os.environ['PLEXUS_ACCOUNT_KEY'] = 'test-account'
os.environ['PLEXUS_SCORING_WORKER_REQUEST_STANDARD_QUEUE_URL'] = 'https://test-queue'
os.environ['PLEXUS_RESPONSE_WORKER_QUEUE_URL'] = 'https://test-response-queue'


class SmokeTest:
    """Container smoke test suite"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tests = []

    def test(self, description):
        """Decorator to register a test"""
        def decorator(func):
            self.tests.append((description, func))
            return func
        return decorator

    async def run(self):
        """Run all tests"""
        print("=" * 70)
        print("LAMBDA CONTAINER SMOKE TEST")
        print("=" * 70)

        for description, test_func in self.tests:
            try:
                print(f"\n▶ {description}")
                if asyncio.iscoroutinefunction(test_func):
                    await test_func(self)
                else:
                    test_func(self)
                print(f"  ✓ PASS")
                self.passed += 1
            except Exception as e:
                print(f"  ✗ FAIL: {e}")
                self.failed += 1

        print("\n" + "=" * 70)
        print(f"RESULTS: {self.passed} passed, {self.failed} failed")
        print("=" * 70)

        return self.failed == 0


# Create test suite
suite = SmokeTest()


@suite.test("Import core dependencies")
def test_imports(self):
    """Test that all core dependencies can be imported"""
    import langchain
    import langchain_core
    import langgraph
    import langchain_anthropic
    import langchain_openai
    import tactus
    import boto3
    print(f"    - langchain: {langchain.__version__}")
    print(f"    - langchain-core: {langchain_core.__version__}")
    print(f"    - tactus: {tactus.__version__}")


@suite.test("Verify pinned LangChain versions")
def test_langchain_versions(self):
    """Verify LangChain packages have expected versions"""
    import langchain
    import langchain_core

    assert langchain.__version__ == "0.3.27", f"Expected langchain 0.3.27, got {langchain.__version__}"
    assert langchain_core.__version__ == "0.3.78", f"Expected langchain-core 0.3.78, got {langchain_core.__version__}"
    print(f"    - All versions match requirements.txt")


@suite.test("Import Plexus modules")
def test_plexus_imports(self):
    """Test that Plexus modules can be imported"""
    from plexus.dashboard.api.client import PlexusDashboardClient
    from plexus.dashboard.api.models.scoring_job import ScoringJob
    from plexus.dashboard.api.models.account import Account
    from plexus.dashboard.api.models.scorecard import Scorecard
    from plexus.dashboard.api.models.score import Score
    from plexus.utils.scoring import create_scorecard_instance_for_single_score
    print(f"    - All Plexus models import successfully")


@suite.test("Import handler module")
def test_handler_import(self):
    """Test that handler module can be imported"""
    import handler
    assert hasattr(handler, 'lambda_handler'), "lambda_handler not found"
    assert hasattr(handler, 'LambdaJobProcessor'), "LambdaJobProcessor not found"
    print(f"    - Handler module loads correctly")


@suite.test("Initialize LambdaJobProcessor")
def test_processor_init(self):
    """Test that LambdaJobProcessor can be initialized"""
    import handler
    processor = handler.LambdaJobProcessor()
    assert processor.client is not None, "PlexusDashboardClient not initialized"
    assert processor.sqs_client is not None, "SQS client not initialized"
    assert processor.request_queue_url is not None, "Request queue URL not set"
    assert processor.response_queue_url is not None, "Response queue URL not set"
    assert processor.account_key is not None, "Account key not set"
    print(f"    - LambdaJobProcessor initialized successfully")


@suite.test("Verify NLTK data")
def test_nltk_data(self):
    """Test that NLTK data is available"""
    import nltk
    # Try to use punkt tokenizer (requires downloaded data)
    try:
        nltk.data.find('tokenizers/punkt')
        print(f"    - NLTK punkt data found")
    except LookupError:
        raise AssertionError("NLTK punkt data not found")


@suite.test("Check writable directories")
def test_writable_dirs(self):
    """Test that required directories are writable"""
    import tempfile
    # Test /tmp is writable (only writable location in Lambda)
    test_file = '/tmp/test_write.txt'
    with open(test_file, 'w') as f:
        f.write('test')
    os.remove(test_file)
    print(f"    - /tmp is writable")


if __name__ == "__main__":
    success = asyncio.run(suite.run())
    sys.exit(0 if success else 1)
