# GitHub Issue Brief: Generalize CloudWatch Logger Namespace

## Title
Remove client-specific branding from CloudWatch logger namespace

## Location
- **File:** `plexus/utils/scoring.py`
- **Line:** 26
- **Current Code:**
  ```python
  cloudwatch_logger = CloudWatchLogger(namespace="CallCriteria/API")
  ```

## Problem
The CloudWatch logger is initialized with a client-specific namespace `"CallCriteria/API"`. This references the old client name and should be generalized for multi-tenant use.

## Solution
Replace the hardcoded namespace with a configurable value:

1. **Option A (Environment Variable):**
   - Create `PLEXUS_CLOUDWATCH_NAMESPACE` environment variable (e.g., `"Plexus/API"`)
   - Read it with `os.getenv('PLEXUS_CLOUDWATCH_NAMESPACE', 'Plexus/API')`
   - Update both `.env` files and `.plexus/config.yaml` documentation

2. **Option B (Configuration):**
   - Add to Plexus configuration system
   - Allow setting via `plexus.cloudwatch.namespace` config property
   - Coordinate with existing configuration loading

3. **Option C (Hardcode Generic):**
   - Use a generic namespace like `"Plexus/API"` or `"Plexus/Scoring"`
   - No configuration needed

## Next Steps
1. Decide which approach fits Plexus architecture best
2. Implement the chosen solution
3. Update `plexus/utils/scoring.py` to use the new approach
4. Test CloudWatch logs are properly namespaced
5. Update documentation if needed

## Blocking
None - this is independent work that can be done anytime after decision is made.

## Category
This is part of broader effort to remove all client-specific "Call Criteria" branding from codebase.

