# CLI Testing Infrastructure

This directory contains comprehensive tests for the Plexus CLI to prevent issues like broken imports, missing command registrations, and restructuring problems.

## 🚨 Problem These Tests Solve

During CLI restructuring, several critical issues went undetected:
- **Entry point failures**: `plexus` command wouldn't start due to wrong import paths
- **Missing commands**: `scorecard` command was imported but not registered
- **Broken imports**: Internal CLI modules had outdated import paths
- **Worker failures**: `plexus command worker` crashed due to import errors

**These tests would have caught all of these issues!**

## 📁 Test Files

### `test_cli_smoke_ultra_fast.py` ⚡ **RECOMMENDED FOR DEVELOPMENT**
**Ultra-fast comprehensive smoke tests** (< 15 seconds)
- Essential CLI functionality validation
- PyTorch lazy loading verification
- Import and command registration testing
- Perfect for development iteration

```bash
python tests/cli/test_cli_smoke_ultra_fast.py
python -m pytest tests/cli/test_cli_smoke_ultra_fast.py -v
```

### `test_cli_integration_fast.py` 🚀 **RECOMMENDED FOR CI/CD**
**Fast comprehensive integration tests** (< 45 seconds)
- Full CLI command validation using optimized techniques
- In-process testing with Click's CliRunner
- Selective subprocess testing for critical commands
- Comprehensive coverage with excellent performance

```bash
python -m pytest tests/cli/test_cli_integration_fast.py -v
```

### Legacy Files (Still Available)

#### `test_cli_imports_only.py` 
**Import-only validation** (< 15 seconds)
- Basic import validation
- Use ultra-fast tests instead for better coverage

#### `test_cli_smoke.py`
**Basic smoke tests** (< 60 seconds)  
- Basic CLI functionality
- Use fast integration tests instead for better coverage

## 🛠️ Test Runners

### Local Development
```bash
# Quick test (recommended for development)
./scripts/test-cli.sh

# Full integration tests
./scripts/test-cli.sh --full

# Just imports (fastest)
python tests/cli/test_cli_imports_only.py
```

### CI/CD
```bash
# Run all CLI tests
python -m pytest tests/cli/ -v

# Run specific test suites
python -m pytest tests/cli/test_cli_smoke.py -v          # Fast
python -m pytest tests/cli/test_cli_integration.py -v   # Thorough
```

## 🤖 GitHub Actions Integration

The `.github/workflows/cli-tests.yml` workflow automatically:
1. **Smoke Tests**: Quick validation on every PR
2. **Integration Tests**: Comprehensive testing 
3. **Entry Point Validation**: Tests `pyproject.toml` entry points work
4. **Import Validation**: Tests all critical imports
5. **Regression Tests**: Tests specific issues that were previously broken

## 📊 Test Coverage

### What These Tests Catch:
✅ **Entry point failures** - `plexus` command won't start  
✅ **Import errors** - Broken module imports after restructuring  
✅ **Missing commands** - Commands imported but not registered  
✅ **Worker failures** - `plexus command worker` issues  
✅ **Command availability** - All major commands accessible  
✅ **Module restructuring** - Import path changes  

### What These Tests Don't Cover:
❌ **Functional correctness** - Commands work correctly with real data  
❌ **API integration** - Commands interact properly with backend  
❌ **Authentication** - Commands handle auth correctly  
❌ **Performance under load** - Commands perform well with large datasets  

## ⏱️ Performance Notes

The CLI startup time is ~15 seconds due to:
- PyTorch initialization (~8 seconds)
- Heavy dependency imports (~4 seconds)  
- Module loading (~3 seconds)

**Test timeouts are set to 30 seconds** to accommodate this.

## 🔄 Adding New Tests

When adding new CLI commands or restructuring:

1. **Add import tests** in `test_cli_imports_only.py`
2. **Add smoke tests** in `test_cli_smoke.py` 
3. **Add integration tests** in `test_cli_integration.py`
4. **Update CI workflow** if needed
5. **Run full test suite** to validate

## 🐛 Debugging Test Failures

If tests fail:

```bash
# Get detailed CLI debug info
python tests/cli/test_cli_integration.py

# Check specific command manually
plexus --help
plexus command worker --help

# Check import manually
python -c "from plexus.cli.shared.CommandLineInterface import main"
```

## 🎯 Best Practices

1. **Run import tests** during development (fastest feedback)
2. **Run smoke tests** before committing  
3. **Run full tests** before major releases
4. **Update tests** when restructuring CLI
5. **Add regression tests** for any new CLI issues discovered

---

**These tests prevent CLI breakage and ensure reliable command-line experience! 🚀**
