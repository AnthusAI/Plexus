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
npm run python:check
# Should show: Python 3.11.13 ✅
```

### 2. Set Up Development Environment

```bash
# Check Python version and install dependencies (all-in-one)
npm run python:setup
```

This will:
- Verify you're using Python 3.11
- Upgrade pip
- Install all project dependencies

### 3. Run Tests

```bash
# Check Python version only
npm run python:check

# Run all tests
npm run test:python

# Run tests with coverage (recommended)
npm run test:python:coverage

# Run MCP server tests specifically
npm run test:mcp

# Serve coverage report at http://localhost:8000
npm run coverage:serve
```

### 4. Clean Up

```bash
# Clean Python cache files and coverage reports
npm run clean:python
```

## Test Results Overview

- **Total Tests:** 367 passing
- **Overall Coverage:** 30%
- **MCP Server Coverage:** 10% (needs improvement)
- **Test Execution Time:** ~45 seconds

## Common Issues

### Issue: Tests fail with import errors
**Solution:** Make sure you're using Python 3.11, not 3.13 or other versions.
```bash
npm run python:check  # This will tell you if version is wrong
```

### Issue: `pandas` installation fails
**Solution:** This happens when using Python 3.13. Switch to Python 3.11.
```bash
pyenv local 3.11.13
npm run python:setup
```

### Issue: Tests can't find modules
**Solution:** Make sure dependencies are installed properly.
```bash
npm run python:setup
```

## Development Workflow

1. **Check Python version:** `npm run python:check`
2. **Set up environment:** `npm run python:setup` (first time only)
3. **Run tests before changes:** `npm run test:python`
4. **Run tests after changes:** `npm run test:python:coverage`
5. **View coverage reports:** `npm run coverage:serve`
6. **Clean up when needed:** `npm run clean:python`

## Available npm Scripts

| Command | Description |
|---------|-------------|
| `npm run python:check` | Verify Python 3.11 is being used |
| `npm run python:setup` | Install all dependencies (includes version check) |
| `npm run test:python` | Run all tests |
| `npm run test:python:coverage` | Run tests with coverage report |
| `npm run test:mcp` | Run MCP server tests specifically |
| `npm run coverage:serve` | Serve coverage report at localhost:8000 |
| `npm run clean:python` | Clean up cache files and reports |

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

1. Check Python version: `npm run python:check`
2. Try reinstalling: `npm run python:setup`
3. Clean and retry: `npm run clean:python && npm run python:setup`
4. Check the main [README.md](README.md) for additional information

## Contributing

When contributing:

1. **Always check Python version:** `npm run python:check`
2. **Run tests before submitting PRs:** `npm run test:python:coverage`
3. **Add tests** for new functionality  
4. **Maintain or improve** test coverage
5. **Use Python 3.11** for development and testing