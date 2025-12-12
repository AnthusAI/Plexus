# LangGraphScore Test File Breakdown Plan

## Current State
- **File:** `plexus/scores/LangGraphScore_test.py`
- **Size:** 10,006 lines (441KB)
- **Test Functions:** 114
- **Problem:** Far too large to maintain, debug, or navigate

## Proposed Breakdown

### 1. **Core Functionality Tests** (`test_langgraphscore_core.py`)
**~15-20 tests, ~1000-1500 lines**
- Basic instance creation
- Predict flow
- Input/output handling
- State management
- Token usage
- Basic error handling

### 2. **Conditional Routing Tests** (`test_langgraphscore_routing.py`)
**~20-25 tests, ~1500-2000 lines**
- Conditional routing (the broken functionality we just discovered)
- Edge routing
- Conditions with fallback
- Routing debug logging
- Complex routing scenarios
- **Include our new actual execution tests**

### 3. **Output Aliasing & Bug Fix Tests** (`test_langgraphscore_output_bugs.py`)
**~25-30 tests, ~2000-2500 lines**
- All the output aliasing bug replications and fixes
- Explanation overwriting bugs
- Value setter bugs
- NA output aliasing bugs
- Comprehensive bug fix verifications

### 4. **Batch Processing Tests** (`test_langgraphscore_batch.py`)
**~15-20 tests, ~1500-2000 lines**
- Batch processing pause/resume
- Batch cleanup
- Batch with checkpointer
- Batch interruption and recovery
- Custom thread management

### 5. **Database & Infrastructure Tests** (`test_langgraphscore_database.py`)
**~10-15 tests, ~1000-1500 lines**
- PostgreSQL checkpointer
- Database setup/teardown
- Connection failures
- Async cleanup

### 6. **Advanced Features Tests** (`test_langgraphscore_advanced.py`)
**~15-20 tests, ~1500-2000 lines**
- Graph visualization
- Cost calculation
- Token usage aggregation
- Multimodal input
- Complex state combinations
- Context manager functionality

### 7. **Integration & Workflow Tests** (`test_langgraphscore_integration.py`)
**~10-15 tests, ~1000-1500 lines**
- Complex multi-node workflows
- Real-world scorecard patterns
- Full end-to-end scenarios
- Workflow compilation

## Benefits of This Breakdown

1. **Maintainability**: Each file focuses on a specific area
2. **Test Execution**: Can run specific test categories
3. **Debugging**: Easier to find relevant tests
4. **Development**: Teams can work on different areas without conflicts
5. **CI/CD**: Can parallelize test execution by category

## Implementation Strategy

1. Create new test files with proper imports and fixtures
2. Move related tests from the monolithic file
3. Ensure all fixtures are available in each file
4. Update pytest configuration if needed
5. Remove the original monolithic file
6. Add our new conditional routing execution tests to the routing file

## File Size Targets

- Target: **1000-2500 lines per file**
- Maximum: **3000 lines per file**
- Current: **10,006 lines (4x too large)**

This breakdown will create 7 focused, manageable test files instead of one massive file. 