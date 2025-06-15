# Plexus Development Setup

This guide will help you set up a development environment for Plexus and run tests successfully.

## Python Version Requirement

**🚨 CRITICAL: Use Python 3.11**

This project **requires Python 3.11**. Using Python 3.13 or other versions will cause dependency installation failures due to pinned package versions (specifically `pandas==2.1.4` and others).

## Quick Start

### 1. Install Python 3.11

#### Using pyenv (Recommended)
```bash
# Install pyenv if you don't have it
curl https://pyenv.run | bash

# Install Python 3.11.13
pyenv install 3.11.13

# Set Python 3.11 for this project
pyenv local 3.11.13
```

#### Verify Python Version
```bash
python --version
# Should output: Python 3.11.13
```

### 2. Set Up Development Environment

```bash
# Create virtual environment
python -m venv plexus_env

# Activate virtual environment
source plexus_env/bin/activate  # On Linux/macOS
# or
plexus_env\Scripts\activate     # On Windows

# Install project dependencies
pip install --upgrade pip
pip install -e .
```

### 3. Run Tests

```bash
# Run all tests
python -m pytest -v

# Run tests with coverage
python -m pytest --cov=. --cov-report=term --cov-report=html -v

# Run specific test file
python -m pytest plexus/PromptTemplateLoader_test.py -v

# Run MCP server tests specifically
cd MCP
python -m pytest plexus_fastmcp_server_test.py --cov=plexus_fastmcp_server --cov-report=term -v
```

### 4. View Coverage Reports

After running tests with coverage, you can view the HTML report:

```bash
# Coverage report will be in htmlcov/index.html
# Open it in your browser or serve it locally:
cd htmlcov
python -m http.server 8000
# Then visit http://localhost:8000
```

## Test Results Overview

- **Total Tests:** 367 passing
- **Overall Coverage:** 30%
- **MCP Server Coverage:** 10% (needs improvement)
- **Test Execution Time:** ~45 seconds

## Common Issues

### Issue: Tests fail with import errors
**Solution:** Make sure you're using Python 3.11, not 3.13 or other versions.

### Issue: `pandas` installation fails
**Solution:** This happens when using Python 3.13. Switch to Python 3.11.

### Issue: Tests can't find modules
**Solution:** Make sure you installed the project in editable mode with `pip install -e .`

## Development Workflow

1. **Always check Python version first:** `python --version`
2. **Activate virtual environment:** `source plexus_env/bin/activate`
3. **Run tests before making changes:** `python -m pytest`
4. **Run tests after making changes:** `python -m pytest --cov=.`
5. **Check coverage reports** for areas needing more tests

## Priority Testing Areas

The following components need more test coverage:

1. **MCP Server (10% coverage)** - Critical priority
   - File: `MCP/plexus_fastmcp_server.py`
   - Missing: All 15+ MCP tool functions, authentication, error handling

2. **Analysis Tools (5-15% coverage)**
   - Files: `plexus/analysis/topics/`, `plexus/Evaluation.py`
   - Missing: Core analysis workflows, topic modeling

3. **CLI Components (0-30% coverage)**
   - Files: Various `plexus/cli/*` modules
   - Missing: Command integration testing

## Version Manager Files

This project includes several files to help ensure the correct Python version:

- **`.python-version`** - Automatically used by pyenv
- **`runtime.txt`** - Platform deployment version specification
- **`pyproject.toml`** - Contains `requires-python = ">=3.11"`

If you're using pyenv, it will automatically switch to Python 3.11.13 when you enter this directory.

## Getting Help

If you encounter issues:

1. Check you're using Python 3.11: `python --version`
2. Try recreating your virtual environment
3. Make sure all dependencies installed: `pip install -e .`
4. Check the main [README.md](README.md) for additional information

## Contributing

When contributing:

1. **Always run tests** before submitting PRs
2. **Add tests** for new functionality  
3. **Maintain or improve** test coverage
4. **Use Python 3.11** for development and testing