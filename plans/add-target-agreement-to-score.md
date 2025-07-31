# Plan: Add Target Agreement to Score Model and UI

**Goal:** Implement a configurable `targetAgreement` value for each `Score` and display this value as a target marker on relevant metric gauges within the detailed Evaluation view in the dashboard.

## Step 1: Backend Schema Modification

1.  **Modify Schema:**
    *   **File:** `dashboard/amplify/data/resource.ts`
    *   **Action:** Locate the `Score` model definition within the `schema`.
    *   **Add Field:** Add a new field named `targetAgreement` with the type `a.decimal()`. Make it optional (not `.required()`) initially.
        ```typescript
        Score: a
            .model({
                // ... existing fields ...
                targetAgreement: a.decimal(), // <-- Add this line
                accuracy: a.float(),
                // ... existing fields ...
            })
            // ... rest of model definition ...
        ```
2.  **Deploy Changes:**
    *   **Action:** Deploy the Amplify backend changes. This typically involves running `amplify push` or using the Amplify Studio UI. This step updates the GraphQL API and DynamoDB table to include the new field.

## Step 2: Frontend UI Integration

### 2a. Score Configuration UI (Future Task - Identification & Update)

*   **Action:** Identify the component(s) responsible for creating and editing `Score` configurations. This might be part of a Scorecard editor or a dedicated Score editing form.
*   **Action:** Update the identified UI component(s) to include a new input field (likely a number input) allowing users to set the `targetAgreement` value for a `Score`.
*   **Action:** Ensure the corresponding mutation or update function saves the entered value to the `targetAgreement` field of the `Score` object via the GraphQL API.

### 2b. Propagate Target Value to Metrics Gauges

1.  **Update GraphQL Query:**
    *   **File:** `dashboard/components/evaluations-dashboard.tsx`
    *   **Action:** Locate the `LIST_EVALUATIONS` GraphQL query string.
    *   **Modify:** Within the `score { ... }` selection set, add the `targetAgreement` field.
        ```graphql
        score {
          id
          name
          targetAgreement # <-- Add this line
        }
        ```
2.  **Ensure Data Availability in `evaluations-dashboard`:**
    *   **File:** `dashboard/components/evaluations-dashboard.tsx`
    *   **Verify:** Confirm that the `useEvaluationData` hook (or the data fetching logic it uses) correctly fetches the `score` object including `targetAgreement`.
    *   **Verify:** Check the `transformEvaluation` function (if still used directly for this part) or the processing within `useEvaluationData` ensures the full `score` object, including `targetAgreement`, is available on the `Evaluation` objects stored in the component's state (e.g., the `evaluations` array). The current spread `...evaluation` when passing to `TaskDisplay` should handle this implicitly if the data is fetched correctly.
3.  **Pass Data Through `TaskDisplay`:**
    *   **File:** `dashboard/components/TaskDisplay.tsx`
    *   **Action:** Locate the `taskProps` object creation logic.
    *   **Modify:** Update the `taskProps.task.data` object to extract `targetAgreement` from the `evaluationData.score` prop and add it as a new field, for example, `scoreTargetAgreement`.
        ```typescript
        // Inside TaskDisplay, when creating taskProps:
        data: {
          // ... existing fields ...
          scoreTargetAgreement: evaluationData.score?.targetAgreement ?? null, // <-- Add this
          // ... rest of data fields ...
        }
        ```
4.  **Update `EvaluationTaskData` Interface:**
    *   **File:** `dashboard/components/EvaluationTask.tsx` (or relevant types file like `dashboard/types/evaluation.ts` if it exists)
    *   **Action:** Locate the `EvaluationTaskData` interface.
    *   **Modify:** Add the new `scoreTargetAgreement` field.
        ```typescript
        export interface EvaluationTaskData extends BaseTaskData {
          // ... existing fields ...
          scoreTargetAgreement?: number | null; // <-- Add this line
          scoreResults?: ScoreResult[];
          // ... rest of interface ...
        }
        ```
5.  **Pass Target to `MetricsGauges`:**
    *   **File:** `dashboard/components/EvaluationTask.tsx`
    *   **Action:** Locate the `DetailContent` sub-component.
    *   **Action:** Find the `useMemo` hook (or other logic) responsible for creating the `metrics` array that is transformed into the `gauges` prop for `MetricsGauges`.
    *   **Modify:** Update the logic that maps `data.metrics` to `gauges`. For the specific gauge(s) where the target is relevant (e.g., based on `metric.name`), add a `target` property to the gauge object, assigning it the value from `data.scoreTargetAgreement`.
        ```typescript
         const metrics = useMemo(() =>
           variant === 'detail' ?
             (data.metrics ?? []).map(metric => ({
               // ... existing gauge props: value, label, information, maximum, unit, priority ...
               target: (metric.name === 'Accuracy' || metric.name === 'YourTargetMetricName') // Condition based on metric name
                 ? data.scoreTargetAgreement
                 : undefined // Set target only for specific metrics
             }))
             : // ... grid view logic ...
         , [variant, data.metrics, data.accuracy, data.scoreTargetAgreement]); // <-- Add data.scoreTargetAgreement to dependency array
        ```
    *   **Note:** The specific metric name (e.g., 'Accuracy') to apply the target to needs confirmation.
6.  **Update `MetricsGauges` Component:**
    *   **File:** `dashboard/components/MetricsGauges.tsx` (Verify path)
    *   **Action:** Update the props interface for individual gauges (e.g., `GaugeProps`, `MetricGaugeProps`) to accept an optional `target?: number | null` property.
    *   **Action:** Modify the rendering logic of the gauge component to visually display the target value when the `target` prop is provided (e.g., draw a line, marker, or indicator at the target position on the gauge). 