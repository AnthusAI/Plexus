# Development Environment Setup

## Python Version Requirements

**CRITICAL: This project requires Python 3.11, NOT 3.13 or other versions.**

### Why Python 3.11?
- Required by `pyproject.toml` (`requires-python = ">=3.11"`)
- Dependency compatibility (especially pandas 2.1.4)
- Python 3.13 causes compatibility issues with core dependencies

## Environment Setup

### 1. Check for Existing Environment
```bash
conda env list | grep py311
```

### 2. Activate or Create py311 Environment

**If py311 exists:**
```bash
conda activate py311
```

**If py311 doesn't exist:**
```bash
conda create -n py311 python=3.11
conda activate py311
```

### 3. Install Project Dependencies
```bash
pip install -e .
```

## Core Dependencies

From `pyproject.toml`:
- **pytest**, pytest-cov, pytest-asyncio - Testing framework
- **pandas==2.1.4** - Use exactly this version for Python 3.11 compatibility
- **mlflow** - Required for many CLI modules
- **celery** - Required for task dispatch
- **rich** - Required for CLI formatting
- **langchain** - AI/ML framework
- **boto3** - AWS SDK
- **pyyaml**, **click** - Configuration and CLI

## Testing and Coverage

### Python Tests
```bash
# Run tests with coverage
python -m pytest --cov=plexus --cov-report=term --cov-report=html
```

### TypeScript Tests (Dashboard)
```bash
cd dashboard && npm run test:coverage
```

## Known Compatibility Issues

- **pandas 2.1.4**: Compatible with Python 3.11, NOT 3.13
- **mlflow**: Required for CLI modules, version specified in pyproject.toml
- **Import errors**: Usually indicate wrong Python version or missing dependencies
- **Test failures**: Often due to Python 3.13 vs 3.11 compatibility

## Environment Verification

Always verify your environment before starting work:

```bash
# Check Python version (should show 3.11.x)
python --version

# Check active environment (should show py311)
conda info --envs

# Verify pandas version (should show 2.1.4)
pip list | grep pandas

# Basic import test
python -c "import plexus; print('OK')"
```

## Task Automation with Invoke

The project includes `tasks.py` with convenient commands:

```bash
# Install dependencies
invoke install

# Run linting
invoke lint

# Run tests
invoke test

# Generate documentation
invoke docs

# Run lint + test together
invoke ci
```

## Common Issues

1. **Import errors** → Wrong Python version or missing dependencies
2. **Test failures** → Python 3.13 vs 3.11 compatibility
3. **Coverage failures** → Ensure pytest-cov installed in py311 environment

## Quick Start Checklist

- [ ] Activate py311 environment
- [ ] Verify Python version is 3.11.x
- [ ] Install/update dependencies: `pip install -e .`
- [ ] Run verification: `python -c "import plexus; print('OK')"`
- [ ] Ready to develop!
