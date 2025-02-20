Data Operations Refactoring Plan
=================================

Overview:
---------
Currently, our codebase has significant duplication in functions that interact with the Amplify client. In particular:

- Both dashboard/utils/data-operations.ts and dashboard/utils/amplify-helpers.ts contain similar implementations for model queries (e.g., listFromModel, getFromModel), data transformations (e.g., convertToAmplifyTask, processTask, transformAmplifyTask, transformEvaluation), and subscription handling (e.g., observeRecentTasks, observeRecentEvaluations, observeScoreResults).

Goals:
------
1. ✓ Consolidate the duplicated logic into well-organized, modular files.
2. ✓ Create dedicated modules for:
   - ✓ API interactions (CRUD operations): This module (e.g., "amplify-api" or "client") will house functions like getClient, listFromModel, getFromModel, createTask, updateTask.
   - ✓ Data Transformation: This module (e.g., "transformers" or "data-transformers") will include functions to transform raw API responses into processed entities (e.g., transformAmplifyTask, processTask, transformEvaluation).
   - ✓ Subscriptions: This module (e.g., "subscriptions") will handle all reactive functionality such as observeRecentTasks, observeRecentEvaluations, observeScoreResults.
3. ✓ Centralize common type definitions (e.g., LazyLoader, GraphQLResponse, AmplifyListResult) in a types file (like dashboard/utils/types.ts), and expand as needed.
4. Add test coverage for each new module – unit tests for API interactions, transformers, and subscription logic. Integration tests should also be implemented to verify overall functionality.

Current Status:
--------------
✓ Completed:
- Created and implemented API interactions module (amplify-api.ts)
- Created and implemented Data Transformations module (transformers.ts)
- Created and implemented Subscription Handling module (subscriptions.ts)
- Added necessary types to types.ts
- Removed duplicate code from data-operations.ts
- Fixed type checking issues in transformers.ts and subscriptions.ts
- Fixed async handling in subscription tests
- All unit tests are now passing

In Progress:
- Verifying the app's functionality with the refactored code
- Ensuring all components are using the correct imports from the new modules

Next Steps:
----------
1. Verify all components are using the correct imports:
   - Check for any remaining references to old data-operations.ts functions
   - Update imports to use the new modular structure
   - Ensure backward compatibility is maintained where needed

2. Add comprehensive test coverage:
   - Add integration tests for the interaction between modules
   - Add more edge case tests for transformers
   - Add error handling tests for API interactions
   - Add subscription lifecycle tests

3. Documentation:
   - Document the new module structure
   - Add inline documentation for complex transformations
   - Update API documentation to reflect the new structure
   - Add examples of common usage patterns

4. Final cleanup:
   - Remove any remaining deprecated code
   - Verify no duplicate functionality exists
   - Ensure consistent error handling across modules
   - Final type-safety verification

Key Process:
------------
A critical requirement throughout this refactoring is to maintain zero type-check errors. To ensure this, we will:
- ✓ Re-run `npm run typecheck` in the dashboard/ folder after every single, small change.
- ✓ Use baby steps to incrementally refactor functionality while verifying type-check validity at each step.

Itemized Checklist:
---------------------
1. ✓ Analysis & Planning
   - ✓ Review current implementations in data-operations.ts and amplify-helpers.ts.
   - ✓ Identify duplications and similarities between the functions (model queries, data transformations, subscriptions).

2. ✓ Module Creation & Consolidation
   a. ✓ Create a new module for API Interactions:
      - ✓ Extract and consolidate functions: listFromModel, getFromModel, createTask, updateTask, etc.
      - ✓ Verify that all consumers of these functions are updated to use the new module.
      - ✓ Re-run `npm run typecheck` after changes.

   b. ✓ Create a new module for Data Transformations:
      - ✓ Extract conversion and transformation functions: convertToAmplifyTask, processTask, transformAmplifyTask, transformEvaluation.
      - ✓ Ensure consistency in data structure conversion for tasks and evaluations.
      - ✓ Run type check after updates.

   c. ✓ Create a new module for Subscription Handling:
      - ✓ Consolidate subscription functions (observeRecentTasks, observeRecentEvaluations, observeScoreResults) into a separate file.
      - ✓ Ensure that subscription logic is unified and consistent.
      - ✓ Re-run type checks after changes.

   d. ✓ Organize/Review Types:
      - ✓ Consolidate common types (LazyLoader, GraphQLResponse, AmplifyListResult, etc.) into a unified types module.
      - ✓ Remove duplicate or redundant type declarations.
      - ✓ Verify via type check.

3. ✓ Refactoring & Integration
   - ✓ Update codebase consumers to refer to the new modules instead of the old ones.
   - ✓ Remove deprecated/duplicate code from data-operations.ts and amplify-helpers.ts.
   - ✓ Ensure that the new structure is well-documented within the code.

4. Testing (In Progress)
   - ✓ Fix existing unit tests for the new module structure
   - Add integration tests for module interactions
   - Add edge case tests for transformers
   - Add error handling tests for API interactions
   - Add subscription lifecycle tests
   - Re-run all tests and `npm run typecheck` after each change.

5. ✓ Continuous Verification
   - ✓ After every small change or refactoring step, run `npm run typecheck` in the dashboard/ folder to ensure that no new type errors are introduced.
   - ✓ Incrementally verify functionality with tests.

6. Documentation & Final Cleanup (Next Step)
   - Document the new module structure in the project documentation.
   - Add inline documentation for complex transformations.
   - Update API documentation to reflect the new structure.
   - Add examples of common usage patterns.
   - Remove any remaining deprecated code.
   - Verify no duplicate functionality exists.
   - Ensure consistent error handling across modules.
   - Final type-safety verification.