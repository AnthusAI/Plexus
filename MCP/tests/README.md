# Plexus MCP Server Test Suite

This directory contains comprehensive tests for the refactored Plexus MCP Server.

## Test Structure

```
tests/
├── conftest.py                 # Pytest configuration and shared fixtures
├── pytest.ini                 # Pytest configuration
├── test_runner.py             # Custom test runner script
├── unit/                      # Unit tests
│   ├── shared/               # Tests for shared modules
│   │   ├── test_setup.py     # Tests for shared.setup
│   │   └── test_utils.py     # Tests for shared.utils
│   └── tools/                # Tests for tool modules
│       ├── test_scorecard_tools.py
│       ├── test_score_tools.py
│       ├── test_report_tools.py
│       └── test_util_tools.py
├── integration/              # Integration tests
│   ├── test_server_startup.py
│   ├── test_tool_registration.py
│   └── test_mcp_protocol.py
└── fixtures/                 # Test data and fixtures
    ├── sample_responses.json
    └── mock_data.py
```

## Running Tests

### Using the Custom Test Runner

The easiest way to run tests is using the custom test runner:

```bash
# Run all tests
python tests/test_runner.py

# Run only unit tests
python tests/test_runner.py --type unit

# Run only integration tests
python tests/test_runner.py --type integration

# Run tests without coverage
python tests/test_runner.py --no-coverage

# Install test dependencies and run tests
python tests/test_runner.py --install-deps
```

### Using Pytest Directly

You can also run pytest directly:

```bash
# Run all tests
pytest

# Run unit tests only
pytest tests/unit/ -m unit

# Run integration tests only
pytest tests/integration/ -m integration

# Run with coverage
pytest --cov=shared --cov=tools --cov=server --cov-report=html

# Run specific test file
pytest tests/unit/shared/test_utils.py -v

# Run specific test function
pytest tests/unit/shared/test_utils.py::TestURLGeneration::test_get_plexus_url_normal_path -v
```

## Test Categories

### Unit Tests

Unit tests focus on testing individual functions and classes in isolation:

- **`test_setup.py`**: Tests for shared setup functionality including stdout redirection, Plexus imports, and initialization
- **`test_utils.py`**: Tests for utility functions like URL generation, environment loading, and data helpers
- **`test_scorecard_tools.py`**: Tests for scorecard management tools
- **`test_score_tools.py`**: Tests for score management tools
- **Tool-specific tests**: Individual tests for each tool category

### Integration Tests

Integration tests verify that components work together correctly:

- **`test_server_startup.py`**: Tests server initialization and tool registration
- **`test_tool_registration.py`**: Tests that tools are properly registered with FastMCP
- **`test_mcp_protocol.py`**: Tests MCP protocol compliance

## Test Fixtures and Mocks

### Shared Fixtures (`conftest.py`)

- **`mock_environment`**: Provides mock environment variables
- **`mock_dashboard_client`**: Mock Plexus dashboard client
- **`sample_scorecard_data`**: Sample scorecard data for testing
- **`sample_report_data`**: Sample report data for testing
- **`capture_stdout`**: Utility for testing stdout redirection
- **`mock_fastmcp`**: Mock FastMCP instance for tool registration tests

### Custom Mocks

Tests use extensive mocking to:
- Avoid dependencies on external services
- Test error conditions reliably
- Ensure fast test execution
- Maintain test isolation

## Test Coverage

The test suite aims for high coverage of:

- **Core functionality**: 90%+ coverage of shared modules
- **Tool implementations**: 85%+ coverage of tool functions
- **Error handling**: Comprehensive testing of error paths
- **Edge cases**: Boundary conditions and unusual inputs

### Coverage Reports

Generate HTML coverage reports:

```bash
pytest --cov=shared --cov=tools --cov=server --cov-report=html:tests/coverage_html
```

View the report by opening `tests/coverage_html/index.html` in a browser.

## Writing New Tests

### Test Organization

1. **Unit tests** go in `tests/unit/` and should test individual functions/classes
2. **Integration tests** go in `tests/integration/` and test component interactions
3. Use descriptive test class and function names
4. Group related tests in classes

### Test Structure

Follow this pattern for test functions:

```python
def test_function_name_scenario(self, fixtures):
    """Test description explaining what is being tested"""
    # Arrange - set up test data and mocks
    mock_client = Mock()
    test_data = {"key": "value"}
    
    # Act - call the function being tested
    result = function_under_test(test_data, mock_client)
    
    # Assert - verify the results
    assert result == expected_value
    assert mock_client.method.called_once()
```

### Mocking Guidelines

1. **Mock external dependencies**: Database clients, HTTP requests, file system operations
2. **Mock at the right level**: Mock the immediate dependencies, not deep internals
3. **Verify interactions**: Assert that mocks are called with expected parameters
4. **Use fixtures**: Reuse common mocks through pytest fixtures

### Async Testing

For async functions, use `@pytest.mark.asyncio`:

```python
@pytest.mark.asyncio
async def test_async_function(self):
    result = await async_function_under_test()
    assert result is not None
```

## Continuous Integration

Tests are designed to run in CI environments with:

- No external dependencies
- Fast execution (< 30 seconds total)
- Clear failure messages
- Comprehensive coverage reporting

### Required Dependencies

```bash
pip install pytest pytest-cov pytest-asyncio pytest-mock
```

## Debugging Tests

### Running Individual Tests

```bash
# Run a specific test with detailed output
pytest tests/unit/shared/test_utils.py::TestURLGeneration::test_get_plexus_url_normal_path -v -s

# Drop into debugger on failure
pytest --pdb

# Show local variables on failure
pytest --tb=long

# Run tests that match a keyword
pytest -k "url_generation" -v
```

### Common Issues

1. **Import errors**: Ensure the MCP directory is in PYTHONPATH
2. **Mock issues**: Verify mock patches target the correct import paths
3. **Async issues**: Use `pytest-asyncio` and proper async/await syntax
4. **Fixture issues**: Check fixture names and scopes

## Contributing

When adding new tools or functionality:

1. Write unit tests for new functions
2. Add integration tests for new tool registrations
3. Update fixtures if new data structures are introduced
4. Maintain or improve test coverage
5. Follow existing test patterns and naming conventions

The test suite is crucial for maintaining code quality and ensuring the refactored MCP server works correctly. Comprehensive testing enables confident development and deployment of new features.