# Plexus Environment Setup Guide

## Critical Issue: Python Version Mismatch

**PROBLEM:** This project requires Python 3.11 (`py311` conda environment) but the current system only has Python 3.13 available.

## Project Requirements (from pyproject.toml)
- **Python Version:** `>=3.11` (specifically designed for 3.11)
- **Environment:** Miniconda environment named `py311`
- **Dependencies:** pandas==2.1.4 and other packages compatible with Python 3.11

## Current System Status
- **Available:** Python 3.13.3
- **Missing:** Python 3.11, conda/miniconda
- **Issue:** pandas 2.1.4 has compilation errors with Python 3.13

## Solutions

### Option 1: Install Python 3.11 via Deadsnakes PPA (Recommended)
```bash
# Add deadsnakes PPA for Python 3.11
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev

# Create proper environment
python3.11 -m venv py311
source py311/bin/activate
pip install -e .
```

### Option 2: Install Miniconda + Python 3.11 (Preferred)
```bash
# Install Miniconda
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh -b -p $HOME/miniconda3
source $HOME/miniconda3/bin/activate

# Create py311 environment
conda create -n py311 python=3.11
conda activate py311
pip install -e .
```

### Option 3: Update Dependencies for Python 3.13 (Last Resort)
```bash
# Update pyproject.toml to use compatible versions
pandas>=2.2.0  # Compatible with Python 3.13
# Then install normally
```

## Testing Commands Once Environment is Fixed

### Python Coverage (with py311 environment)
```bash
# Activate correct environment
conda activate py311  # or source py311/bin/activate

# Run full test suite with coverage
python -m pytest --cov=plexus --cov-report=term --cov-report=html

# Run specific CLI tests
python -m pytest plexus/tests/cli/ --cov=plexus.cli --cov-report=term -v
```

### TypeScript Coverage (already working)
```bash
cd dashboard
npm run test:coverage
```

## Verification Steps
```bash
# Check Python version
python --version  # Should show 3.11.x

# Check environment
conda info --envs  # Should show py311 as active

# Test basic import
python -c "import plexus; print('Environment OK')"

# Check key dependencies
pip list | grep -E "(pandas|mlflow|pytest)"
```

## Why This Matters
1. **pandas 2.1.4** specified in pyproject.toml doesn't compile with Python 3.13
2. **mlflow** and other dependencies may have version conflicts
3. **Test compatibility** - many tests were written for Python 3.11
4. **Consistency** - development team uses py311 conda environment

## For Future Development Sessions
1. **Always check:** `python --version` before starting
2. **Always activate:** `conda activate py311` or equivalent
3. **Never use:** System Python or wrong versions
4. **Reference:** This document and `.cursorrules` for environment setup

## Current Coverage Status
- **TypeScript:** ✅ 48% coverage measured successfully
- **Python:** ❌ Cannot measure due to Python version incompatibility
- **Blocking issue:** Python 3.13 vs required Python 3.11

---
*Created during environment setup debugging session*
*Date: January 7, 2025*