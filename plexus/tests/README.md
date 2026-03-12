# Plexus Test Suite for API Loading Functionality

This directory contains the test suite for Plexus's API loading functionality, which enables evaluation commands to load scorecard configurations directly from the API rather than from local YAML files.

## Test Modules

The test suite is organized into the following modules:

### 1. `test_scorecard_api_loading.py`

Tests the core functionality for loading scorecards from the API:
- Resolving scorecard identifiers (ID, key, name, external ID)
- Caching of identifier resolution results for improved performance
- Fetching scorecard structure from the API

### 2. `test_score_dependency_resolution.py`

Tests the dependency discovery and resolution functionality:
- Extracting dependencies from score configurations
- Building a complete dependency graph
- Handling different dependency formats (list, dict)
- Resolving dependency names to IDs

### 3. `test_config_caching.py`

Tests the local caching mechanisms for score configurations:
- Saving configurations to local files
- Loading configurations from cache
- Checking if configurations exist in cache
- Performance improvements from caching

### 4. `test_evaluation_commands.py`

Tests the integration of API loading with CLI commands:
- Accuracy command with different identifier types
- Distribution command with API loading
- YAML flag behavior
- Error handling and user messages
- Dry run functionality

## Test Fixtures

The test suite uses the following fixtures:

- `fixtures/api_responses/scorecard_structure.json`: Mock API response for a scorecard structure query
- `fixtures/api_responses/score_configurations.json`: Mock API response for score configuration queries

## Running the Tests

To run the entire test suite:

```bash
python -m pytest plexus/tests/
```

To run a specific test module:

```bash
python -m pytest plexus/tests/test_scorecard_api_loading.py
```

To run a specific test class:

```bash
python -m pytest plexus/tests/test_scorecard_api_loading.py::TestIdentifierResolution
```

To run a specific test method:

```bash
python -m pytest plexus/tests/test_scorecard_api_loading.py::TestIdentifierResolution::test_scorecard_identifier_resolution_caching
```

## Test Dependencies

The test suite requires the following dependencies:
- pytest
- unittest
- pytest-mock (for mocking API responses)
- click.testing (for testing CLI commands)

## Mock Strategy

The tests use a combination of mocking strategies:
1. Mock API responses using JSON fixture files
2. Mock GraphQL client to avoid actual API calls
3. Patch core functions to isolate test cases
4. Use `CliRunner` for testing command-line interfaces

## Adding New Tests

When adding new tests:
1. Follow the existing pattern for test organization
2. Use appropriate mock objects for external dependencies
3. Include docstrings explaining what each test is verifying
4. Update this README if you add new test modules or fixtures 