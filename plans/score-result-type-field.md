# ScoreResult Type Field Enhancement

## 🚨 CURRENT STATUS & NEXT STEPS

**Current Phase:** Phase 3 - Production Testing & Deployment  
**Machine Requirements:** Data access machine (not development machine)  
**Blocking Issue:** Frontend work cannot proceed until production testing is complete

### For New AI Session on Data Access Machine:

1. **Pull the feature branch** with all the completed work
2. **Complete Phase 3 testing** (Steps 3.1 and 3.2) - see detailed commands below
3. **Deploy to production** (Step 3.3) if tests pass
4. **Only then** can frontend work (Phase 4) begin

### What's Already Complete:
- ✅ **Phase 1**: Data model enhanced with `type` field
- ✅ **Phase 2**: All score result creation points updated
- ✅ **Local Testing**: Type field works correctly in development

### What's Needed Now:
- 🔴 **Phase 3.1**: Test evaluation workflow creates `type: "evaluation"`
- 🔴 **Phase 3.2**: Test API workflow creates `type: "prediction"`  
- 🔴 **Phase 3.3**: Deploy to production
- 🔴 **Phase 4**: Frontend dashboard enhancements (blocked until Phase 3 complete)

## Background & Context

Currently, the Plexus system creates ScoreResult records through two main processes:
1. **Predictions** - When using the predict functionality to score items
2. **Evaluations** - When running evaluations to test model performance

Both processes create ScoreResult records and properly associate them with Items through the `itemId` foreign key field. However, there's currently no way to distinguish between score results created by predictions vs evaluations in the data model or dashboard.

## Problem Statement

Users need to be able to:
- Distinguish between prediction and evaluation score results in the database
- View separate counts and metrics for predictions vs evaluations in the dashboard
- Maintain backward compatibility with existing score results

## Solution Overview

Add a `type` field to the ScoreResult model to categorize score results by their creation method, and enhance the dashboard to show breakdowns by type.

## Key Files & Components

### Data Model
- `dashboard/amplify/data/resource.ts` - ScoreResult model definition (lines 397-440)
- `plexus/dashboard/api/models/score_result.py` - Python API model for ScoreResult

### Score Result Creation Points
- `plexus/Evaluation.py` - Evaluation score result creation (around line 1613, `_create_score_result` method)
- `plexus/cli/PredictionCommands.py` - Prediction functionality
- `plexus/dashboard/cli.py` - Dashboard CLI simulation (around line 690)

### Dashboard Components
- `dashboard/components/items-dashboard.tsx` - Main items dashboard
- `dashboard/hooks/useItemsMetrics.ts` - Metrics aggregation hook
- `plexus/dashboard/api/aggregation/` - Metrics aggregation system

## Step-by-Step Implementation Plan

### 📋 Phase 1: Data Model Enhancement

#### 🔄 Step 1.1: Add type field to ScoreResult model
**Status:** 🟢 Complete  
**Details:**
- ✅ Add `type: a.string()` field to ScoreResult model in `dashboard/amplify/data/resource.ts`
- ✅ Make field optional for backward compatibility with existing records
- ✅ Deploy schema changes to development environment
- **Files:** `dashboard/amplify/data/resource.ts` (around line 407)

#### 🔄 Step 1.2: Update Python API model
**Status:** 🟢 Complete  
**Details:**
- ✅ Add `type` field to ScoreResult class in `plexus/dashboard/api/models/score_result.py`
- ✅ Update `fields()` method to include type field
- ✅ Update `create()` method to accept type parameter
- ✅ Update `from_dict()` method to handle type field
- ✅ Update `__init__` method and dataclass fields
- **Files:** `plexus/dashboard/api/models/score_result.py`

### 📋 Phase 2: Score Result Creation Updates

#### 🔍 Step 2.1: Research all score result creation points
**Status:** 🟢 Complete  
**Details:**
- ✅ Audit codebase to find all locations where ScoreResult records are created
- ✅ Document each creation point and its context
- ✅ Found and updated all major creation points:
  - `plexus/Evaluation.py` - Evaluation score results (type: "evaluation")
  - `plexus/cli/BatchCommands.py` - Batch processing (type: "prediction")
  - `plexus/dashboard/cli.py` - CLI commands (type: "prediction" and "evaluation")
  - `plexus/cli/ResultCommands.py` - Test error results (type: "test")
  - `Call-Criteria-Python/api.py` - API predictions (type: "prediction")
- ✅ Verified batch creation method supports type field
- **Search patterns:** `ScoreResult.create`, `createScoreResult`, `_create_score_result`

#### 🔄 Step 2.2: Update evaluation score result creation
**Status:** 🟢 Complete  
**Details:**
- ✅ Modify `_create_score_result` method in `plexus/Evaluation.py` (around line 1613)
- ✅ Add `type: "evaluation"` when creating score results during evaluations
- ✅ Update GraphQL mutation to include type field
- ✅ Update dashboard CLI simulation to use `type: "evaluation"`
- **Files:** `plexus/Evaluation.py`, `plexus/dashboard/cli.py`

#### 🔄 Step 2.3: Update prediction score result creation
**Status:** 🟢 Complete  
**Details:**
- ✅ Update batch processing in `plexus/cli/BatchCommands.py` to use `type: "prediction"`
- ✅ Update dashboard CLI score result creation to use `type: "prediction"`
- ✅ Update test error result creation to use `type: "test"`
- ✅ Update Call-Criteria-Python API to use `type: "prediction"` for API calls
- **Files:** `plexus/cli/BatchCommands.py`, `plexus/dashboard/cli.py`, `plexus/cli/ResultCommands.py`, `Call-Criteria-Python/api.py`

#### 🔄 Step 2.4: Update any other score result creation points
**Status:** 🟢 Complete  
**Details:**
- ✅ All major score result creation points have been identified and updated
- ✅ Consistent type values implemented across all creation methods
- ✅ Comprehensive testing completed with all scenarios working correctly
- **Files:** All creation points updated in previous steps

#### 🧪 Step 2.5: Test implementation
**Status:** 🟢 Complete  
**Details:**
- ✅ Created comprehensive test script to verify type field functionality
- ✅ Tested prediction score result creation with `type: "prediction"`
- ✅ Tested evaluation score result creation with `type: "evaluation"`
- ✅ Tested backward compatibility with no type specified (returns None)
- ✅ Verified GraphQL queries properly include and return type field
- ✅ Confirmed GSI constraints are satisfied (scoreId required)
- ✅ All test scenarios passed successfully

### 📋 Phase 3: Production Testing & Deployment (🔴 CRITICAL - MUST COMPLETE BEFORE FRONTEND)

#### 🧪 Step 3.1: Test evaluation workflow with type field
**Status:** 🔴 Not Started - **REQUIRES DATA ACCESS MACHINE**  
**Details:**
- **CRITICAL**: Must be done on machine with data access before frontend work
- Run a simple evaluation that creates 1-2 score results
- Verify that evaluation score results are created with `type: "evaluation"`
- Check database/GraphQL to confirm type field is properly set
- **Commands to run:**
  ```bash
  # Source environment
  source .env
  
  # Run a minimal evaluation (adjust scorecard/score as needed)
  python -m plexus.cli evaluation run --scorecard "YOUR_SCORECARD" --score "YOUR_SCORE" --samples 2
  
  # Query recent score results to verify type field
  python -c "
  from plexus.dashboard.api.client import PlexusDashboardClient
  client = PlexusDashboardClient()
  results = client.execute('''
    query {
      listScoreResults(limit: 5, sortDirection: DESC) {
        items {
          id
          type
          evaluationId
          scoringJobId
          createdAt
        }
      }
    }
  ''')
  for item in results['listScoreResults']['items']:
      print(f'ID: {item[\"id\"]}, Type: {item[\"type\"]}, EvalID: {item[\"evaluationId\"]}, JobID: {item[\"scoringJobId\"]}')
  "
  ```
- **Expected Result**: Recent evaluation score results should show `type: "evaluation"`

#### 🧪 Step 3.2: Test API prediction workflow with type field  
**Status:** 🔴 Not Started - **REQUIRES DATA ACCESS MACHINE**
**Details:**
- **CRITICAL**: Must be done on machine with data access before frontend work
- Test Call-Criteria-Python API endpoint to create prediction score results
- Verify that API predictions are created with `type: "prediction"`
- **Commands to run:**
  ```bash
  # Test API endpoint (adjust URL/credentials as needed)
  curl -X GET "https://your-api-endpoint/v1/predictions/scorecards/YOUR_SCORECARD/scores/YOUR_SCORE/report_id/test-report-123" \
    -H "Authorization: Basic YOUR_CREDENTIALS"
  
  # Query recent score results to verify type field
  python -c "
  from plexus.dashboard.api.client import PlexusDashboardClient
  client = PlexusDashboardClient()
  results = client.execute('''
    query {
      listScoreResults(limit: 5, sortDirection: DESC) {
        items {
          id
          type
          evaluationId
          scoringJobId
          createdAt
        }
      }
    }
  ''')
  for item in results['listScoreResults']['items']:
      print(f'ID: {item[\"id\"]}, Type: {item[\"type\"]}, EvalID: {item[\"evaluationId\"]}, JobID: {item[\"scoringJobId\"]}')
  "
  ```
- **Expected Result**: Recent API score results should show `type: "prediction"`

#### 🚀 Step 3.3: Deploy to production
**Status:** 🔴 Not Started - **REQUIRES SUCCESSFUL TESTING**
**Details:**
- **PREREQUISITE**: Steps 3.1 and 3.2 must pass successfully
- Deploy Plexus project changes (schema + Python code)
- Deploy Call-Criteria-Python API changes
- **Deployment Commands:**
  ```bash
  # Deploy Plexus (schema + backend)
  npx ampx deploy
  
  # Deploy Call-Criteria-Python (separate deployment)
  # [Follow your standard API deployment process]
  ```
- **Verification**: Run quick smoke tests to ensure production deployments work

### 📋 Phase 4: Dashboard Enhancement (🔴 BLOCKED UNTIL PHASE 3 COMPLETE)

#### 🔄 Step 4.1: Enhance metrics aggregation system
**Status:** 🔴 Blocked - **WAITING FOR PRODUCTION DEPLOYMENT**
**Details:**
- Update metrics aggregation to support filtering by type
- Modify aggregation queries to optionally filter by score result type
- Ensure backward compatibility with existing aggregation logic
- **Files:** `dashboard/hooks/useItemsMetrics.ts`, aggregation system files

#### 🔄 Step 4.2: Update items dashboard to show type breakdown
**Status:** 🔴 Blocked - **WAITING FOR PRODUCTION DEPLOYMENT**
**Details:**
- Modify items dashboard to show total counts by default
- Add expandable section to show prediction vs evaluation breakdown
- Update ItemsGauges component to support type-specific metrics
- **Files:** `dashboard/components/items-dashboard.tsx`, related components

#### 🔄 Step 4.3: Add visual breakdown in dashboard popup
**Status:** 🔴 Blocked - **WAITING FOR PRODUCTION DEPLOYMENT**
**Details:**
- Enhance dashboard popup to show two rows instead of one
- Display separate metrics for predictions and evaluations
- Maintain existing total view as default
- **Files:** Dashboard popup components

### 📋 Phase 5: Final Validation (After Dashboard Enhancement)

#### 🧪 Step 5.1: End-to-end testing
**Status:** 🔴 Not Started  
**Details:**
- Test complete evaluation workflow with type field and dashboard display
- Test complete prediction workflow with type field and dashboard display
- Verify dashboard displays correct metrics and breakdowns by type
- Validate backward compatibility with existing score results

#### 🧪 Step 5.2: Performance validation
**Status:** 🔴 Not Started  
**Details:**
- Verify filtering performance is acceptable (vs GSI approach)
- Test dashboard responsiveness with type-based filtering
- Monitor for any performance regressions

## Technical Considerations

### Backward Compatibility
- Type field should be optional to support existing score results without type
- Dashboard should handle null/empty type values gracefully
- Aggregation should treat null type as "both" or "unknown"

### Indexing Strategy
- Initially, we'll use filtering rather than creating new GSIs
- Future consideration: Evaluate if type-based GSI is needed for performance
- Current GSIs are already complex, so filtering approach is preferred initially

### Type Values
- `"prediction"` - Score results created through prediction functionality
- `"evaluation"` - Score results created through evaluation processes
- `null`/empty - Existing score results or unknown type (treated as "both")

## Future Enhancements

- Consider adding more granular types (e.g., "batch_prediction", "manual_evaluation")
- Evaluate need for type-based GSI if filtering performance becomes an issue
- Add type-based filtering to other dashboard components and reports

## Status Legend

- 🔴 **Not Started** - Task has not been begun
- 🟡 **In Progress** - Task is currently being worked on
- 🟢 **Complete** - Task has been finished and tested
- ⚠️ **Blocked** - Task is waiting on dependencies or external factors
- 🔄 **In Review** - Task is complete but pending review/approval

## Dependencies

- Schema deployment capabilities
- Access to development environment for testing
- Dashboard testing environment
- Understanding of current metrics aggregation system

## Success Criteria

1. ScoreResult model includes optional `type` field
2. All evaluation score results are created with `type: "evaluation"`
3. All prediction score results are created with `type: "prediction"`
4. Dashboard shows total counts by default
5. Dashboard popup shows breakdown by prediction vs evaluation
6. Existing functionality remains unaffected
7. Performance impact is minimal (filtering vs new GSI) 