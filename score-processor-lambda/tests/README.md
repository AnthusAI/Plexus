# Score Processor Lambda Tests

These tests are specific to the Lambda function container and are **excluded from the main project test suite** in `pytest.ini`.

## Why Separate?

The Lambda function has different dependencies and runs in a container environment, so these tests:
1. Test container-specific functionality (imports, NLTK data, filesystem)
2. Use different fixtures and environment setup
3. Are meant to be run independently before deployment

## Running Tests

**From score-processor-lambda directory:**
```bash
# Run all tests
make test

# Run unit tests only
make test-unit

# Run container smoke test
make test-smoke
```

**Directly with pytest:**
```bash
cd /path/to/Plexus
PYTHONPATH=score-processor-lambda pytest score-processor-lambda/tests/test_*.py -v
```

## CI/CD

These tests are excluded from the main GitHub Actions CI workflow. They should be run:
1. Locally before committing Lambda changes
2. As part of the CDK deployment pipeline (if configured)

See [../README.md](../README.md#testing) for more details.
