# Code Coverage Report - Plexus Project

## Executive Summary

This report provides an analysis of the current code coverage status for both the TypeScript (Dashboard) and Python (Core) components of the Plexus project.

## TypeScript/JavaScript Dashboard Coverage

**Coverage achieved:** Jest tests run successfully with coverage reporting

### Overall Coverage Metrics
- **Statements:** 48%
- **Branches:** 30%  
- **Functions:** 37%
- **Lines:** 49%

### Detailed Breakdown by Module

#### High Coverage Areas (>80%)
- **app/**: 81% statements - Core app routes and pages
- **app/contexts**: 80% statements - Context providers
- **components/landing**: 89% statements - Landing page components
- **types**: 100% statements - TypeScript type definitions

#### Medium Coverage Areas (40-80%)
- **components**: 64% statements - General UI components
- **utils**: 45% statements - Utility functions
- **components/ui**: 44% statements - UI component library
- **graphql**: 60% statements - GraphQL queries

#### Low Coverage Areas (<40%)
- **app/evaluations/[id]**: 39% statements - Evaluation detail pages
- **hooks**: 2% statements - Custom React hooks (needs attention)
- **lib**: 26% statements - Library functions

### Test Files Found
- 13 test suites total
- 99 tests passed
- Key test files:
  - `CTASection.test.tsx`
  - `hydration.test.tsx` 
  - `hierarchicalAggregator.test.ts`
  - `generalizedMetricsAggregator.test.ts`
  - `MetricsGauges.test.tsx`
  - `subscriptions.test.ts`
  - `amplify-api.test.ts`
  - `transformers.test.ts`

## Python Core Coverage

**Status:** Cannot measure - Python version incompatibility ❌

### Critical Issue
- **Project requires:** Python 3.11 (py311 conda environment)
- **Current system:** Python 3.13.3
- **Incompatibility:** pandas 2.1.4 (specified in pyproject.toml) doesn't compile with Python 3.13

### Project Requirements (from pyproject.toml)
- **Python version:** `>=3.11` (designed for 3.11)
- **Environment:** Miniconda environment `py311`
- **pandas version:** 2.1.4 (not compatible with Python 3.13)

### System Status
❌ **Python 3.11** not available on current system  
❌ **conda/miniconda** not installed  
❌ **py311 environment** cannot be created  
❌ **Coverage measurement** blocked by version incompatibility  

### Solutions Required
1. **Install Python 3.11** via deadsnakes PPA or pyenv
2. **Install Miniconda** and create py311 environment
3. **Install dependencies** with `pip install -e .` in correct environment

### What Was Attempted
- Created Python 3.13 virtual environment (incorrect)
- Installed pytest, pytest-cov, pandas 2.3.0 (wrong versions)
- Attempted module imports (failed due to missing mlflow, rich, celery)

### Codebase Analysis
- **Total Python files:** 161 files (~10,340 lines)
- **CLI modules:** 52 files in plexus/cli/
- **Test files:** 2 Python test files in plexus/tests/cli/
- **Dependencies:** mlflow, rich, celery, langchain (all require proper Python version)

## Recommendations

### TypeScript/Dashboard
1. **Priority:** Improve hooks coverage (currently 2%) - critical for React functionality
2. **Medium Priority:** 
   - Increase component/ui coverage from 44% to >60%
   - Improve utils coverage from 45% to >60%
   - Add more tests for app/evaluations pages
3. **Maintain:** Keep high coverage areas (landing pages, contexts, types) well-tested

### Python/Core
1. **Critical:** Install Python 3.11 environment (see ENVIRONMENT_SETUP.md)
   - Install Python 3.11 via deadsnakes PPA: `sudo add-apt-repository ppa:deadsnakes/ppa`
   - Create py311 environment: `python3.11 -m venv py311`
   - Install all dependencies: `pip install -e .` (includes mlflow, rich, celery)
2. **Coverage Goals:**
   - Current status: Cannot measure due to version incompatibility
   - Target: 70%+ coverage for critical CLI components once environment is fixed
   - Full test suite execution with proper Python 3.11 + pandas 2.1.4

### Overall Project
1. **CI/CD Integration:** Set up automated coverage reporting in build pipeline
2. **Coverage Targets:** 
   - TypeScript: Aim for 70% overall coverage
   - Python: Aim for 65% overall coverage
3. **Regular Monitoring:** Implement coverage regression detection

## Current Status Summary

| Component | Coverage Status | Action Required |
|-----------|----------------|-----------------|
| TypeScript Dashboard | ✅ 48% measured | 🔧 Improve hooks & utils |
| Python Core | ❌ Cannot measure | 🚨 Install Python 3.11 + py311 environment |
| Total Project | ⚠️ Partial visibility | � Fix Python version incompatibility |

## Next Steps

1. **Immediate:** Install Python 3.11 environment (see ENVIRONMENT_SETUP.md for instructions)
2. **Week 1:** Get baseline Python coverage measurement with proper environment
3. **Week 2:** Focus on improving TypeScript hooks coverage (critical gap)
4. **Week 3:** Implement automated coverage reporting in CI/CD
5. **Ongoing:** Regular coverage monitoring and incremental improvements

---
*Report generated on: Monday, July 7, 2025 at 13:11 UTC*
*TypeScript coverage: Measured via Jest (HTML report available at `dashboard/coverage/lcov-report/`)*
*Python coverage: Cannot measure - requires Python 3.11 environment (py311)*
*Critical issue: Python version incompatibility (current: 3.13, required: 3.11)*
*Solution: See ENVIRONMENT_SETUP.md for installation instructions*