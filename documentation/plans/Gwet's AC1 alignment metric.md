# Gwet's AC1 Alignment Metric Implementation Plan

## Status Tracking

This document serves as both a planning document and a status tracker for implementing Gwet's AC1 in Plexus.

Status indicators:
- ⬜ Not started
- 🔄 In progress
- ✅ Completed

## Overview

This document outlines the plan to implement Gwet's AC1 (Agreement Coefficient 1) as an alignment metric in the Plexus project. Gwet's AC1 is a robust alternative to Cohen's Kappa for measuring agreement between raters, particularly when there's high class imbalance. This implementation will move the existing functionality from the Call-Criteria-Python project into Plexus as a reusable component and integrate it with the evaluation system.

## Background

Gwet's AC1 resolves the "Kappa paradox" where high observed agreement can result in low Kappa values when there's high class imbalance. AC1 ranges from -1 to 1:
- 1: Perfect agreement
- 0: Agreement is no better than chance
- <0: Agreement is worse than chance (rare)

## Implementation Plan

### Step 1: Move Gwet's AC1 from Call-Criteria-Python to Plexus

✅ 1. Create a dedicated module in Plexus for Gwet's AC1:
   ```
   plexus/analysis/metrics/gwet_ac1.py
   ```

✅ 2. Implement the `GwetAC1` class based on the existing implementation in:
   ```
   /home/ryan/projects/Call-Criteria-Python/commands/data/feedback/gwet_ac1.py
   ```

✅ 3. Create necessary `__init__.py` files to make it a proper module:
   ```
   plexus/analysis/__init__.py
   plexus/analysis/metrics/__init__.py
   ```

✅ 4. Update the existing analysis script in Call-Criteria-Python to use the Plexus implementation:
   ```
   /home/ryan/projects/Call-Criteria-Python/commands/data/feedback/analyze.py
   ```

   This will require modifying the import statement to use:
   ```python
   from plexus.analysis.metrics import GwetAC1
   ```
   
   instead of the current local import.

✅ 5. Upon successful integration, the original `gwet_ac1.py` file in Call-Criteria-Python can be removed.

### Step 2: Add Test Coverage

✅ 1. Create a test file for the GwetAC1 implementation:
   ```
   plexus/analysis/metrics/gwet_ac1_test.py
   ```

✅ 2. Implement tests covering:
   - Basic functionality with known values
   - Edge cases (perfect agreement, no agreement, disagreement)
   - Error handling cases (empty inputs, different length inputs)
   - Special cases (single category, zero division handling)

✅ 3. Ensure test coverage meets project standards (typically >90% coverage).

✅ 4. Additional improvement: Created a standardized `Metric` base class:
   ```
   plexus/analysis/metrics/metric.py
   ```
   - Provides consistent Input/Output interfaces using Pydantic models
   - Standardizes range information for proper visualization
   - Added `Accuracy` metric as another example implementation
   - Added comprehensive test coverage for both metrics

### Step 3: Replace Sensitivity Metric with Gwet's AC1 in Evaluations

⬜ 1. Identify the evaluation metric calculation in:
   ```
   plexus/Evaluation.py
   ```

⬜ 2. Replace or extend the sensitivity metric with Gwet's AC1:
   - For backward compatibility, initially map the AC1 score from [-1, 1] to [0%, 100%]
   - Any negative AC1 scores will be mapped to 0%
   - AC1 scores of 1 will map to 100%

⬜ 3. Update the API documentation to communicate this change.

⬜ 4. Add logging to track both the raw AC1 value and the percentage conversion.

### Step 4: Update Frontend to Support Native AC1 Range

⬜ 1. Identify all locations in the dashboard where metrics are displayed:
   ```
   dashboard/components/
   dashboard/app/
   ```

⬜ 2. Modify the UI components to handle the AC1 range of -1 to 1:
   - Update progress bars or other visualization components
   - Add appropriate color coding (red for negative, yellow for near-zero, green for positive)
   - Include tooltips explaining the AC1 interpretation

⬜ 3. Update the evaluation result rendering to include both:
   - Percentage representation (for backward compatibility)
   - Raw AC1 score with appropriate visualization

## Success Criteria

✅ 1. The Gwet's AC1 implementation passes all tests and is properly integrated
✅ 2. Call-Criteria-Python successfully uses the Plexus implementation
⬜ 3. Evaluations correctly calculate and display AC1 scores
⬜ 4. The UI appropriately represents AC1 scores in their natural range
⬜ 5. Documentation is updated to reflect the new metric 