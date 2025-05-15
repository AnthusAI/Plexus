# Plan: Improve ConfusionMatrix Component Parameters

## 1. Problem Statement

The current `ConfusionMatrix` component (and its `ConfusionMatrixData` interface, likely defined in `dashboard/components/confusion-matrix.tsx`) accepts a `matrix` prop of type `number[][]`. The orientation of this 2D array (i.e., whether rows represent "Actual" and columns represent "Predicted", or vice-versa) is not explicitly defined by the type system.

This ambiguity has led to confusion and potential for errors, as observed during the recent refactoring of examples on the `dashboard/app/documentation/concepts/evaluation-metrics/page.tsx`. Developers consuming the component must rely on comments or convention, which can be easily overlooked or misinterpreted.

## 2. Goal

To make the expected structure and orientation of the confusion matrix data explicit within the component's props, thereby:
- Reducing the risk of incorrect data representation.
- Improving code clarity and developer understanding.
- Making the component more robust and easier to use correctly.

## 3. Proposed Solution

### 3.1. Modify `ConfusionMatrixData` Interface

We need to change the `matrix` field in the `ConfusionMatrixData` interface. Instead of a simple `number[][]`, we should adopt a more descriptive structure.

**Option A (Preferred): Array of Explicit Row Objects**

```typescript
// In dashboard/components/confusion-matrix.tsx (or wherever ConfusionMatrixData is defined)

interface ConfusionMatrixRow {
  actualClassLabel: string; // e.g., "Red", "Heads" - represents the true class for this row
  predictedClassCounts: { [predictedClassLabel: string]: number }; // Key is the predicted class label, value is the count
                                                                   // e.g., { "Red": 39, "Black": 0 }
}

export interface ConfusionMatrixData {
  matrix: ConfusionMatrixRow[];
  // The existing 'labels' prop might still be useful for defining the overall order of classes
  // if it cannot be solely derived from the matrix structure, or for UI display preferences.
  // Alternatively, 'labels' could be derived from the keys in `predictedClassCounts` and `actualClassLabel`.
  labels: string[]; // e.g., ["Red", "Black"] or ["Heads", "Tails"] - Defines the order of display
}
```

**Explanation of Option A:**
- Each element in the `matrix` array represents one "Actual" class.
- `actualClassLabel` clearly states what true class this row corresponds to.
- `predictedClassCounts` is an object where keys are the "Predicted" class labels and values are the counts for that intersection.
- This structure explicitly defines "Actual" for rows and "Predicted" for the inner counts.
- The overall `labels` array would define the canonical order of all classes present, ensuring consistent ordering in the UI if needed (e.g., for headers/axes).

**Option B: Explicit Orientation and Label Arrays**

```typescript
// Alternative, less preferred
export interface ConfusionMatrixData {
  matrix: {
    rowsRepresent: 'Actual' | 'Predicted';
    columnsRepresent: 'Actual' | 'Predicted';
    values: number[][];
    rowLabels: string[]; // e.g., ["Actual Red", "Actual Black"]
    columnLabels: string[]; // e.g., ["Predicted Red", "Predicted Black"]
  };
  // 'labels' prop might be redundant if row/column labels are detailed enough.
}
```
*Option A is preferred because it ties the counts more directly to named actual and predicted classes, reducing the chance of misalignment between `values` and separate `label` arrays.*

### 3.2. Update `ConfusionMatrix` Component Logic

The internal logic of the `ConfusionMatrix` component (in `dashboard/components/confusion-matrix.tsx`) will need to be updated to:
- Accept the new `ConfusionMatrixData` structure.
- Iterate through the `matrix` (e.g., `ConfusionMatrixRow[]`) to build the visual table.
- Use `actualClassLabel` for row identification and `predictedClassCounts` for cell values.
- Use the main `labels` array (from `ConfusionMatrixData`) to determine the order of columns (predicted classes) and potentially rows if they are not already ordered.

### 3.3. Update Call Sites

All locations where `ConfusionMatrix` is used or `ConfusionMatrixData` is constructed will need to be updated. This includes:
- `dashboard/components/EvaluationCard.tsx`: The `confusionMatrixData` prop passed to `EvaluationCard` will need to conform to the new structure. The `EvaluationCard` itself will then pass the correctly structured data to its internal `ConfusionMatrix` component.
- `dashboard/app/documentation/concepts/evaluation-metrics/page.tsx`: All direct instantiations of `ConfusionMatrix` and data passed to `EvaluationCard` examples.
- Any other parts of the application using these components.

### 3.4. Documentation

- Update JSDoc/TSDoc for `ConfusionMatrixData`, `ConfusionMatrixRow`, and the `ConfusionMatrix` component's props to clearly explain the new expected data structure.
- Emphasize that rows represent "Actual" classes and the inner objects/columns represent "Predicted" class counts.

## 4. Benefits

- **Type Safety:** The structure itself enforces clarity on actual vs. predicted.
- **Reduced Ambiguity:** No more guessing the orientation of `number[][]`.
- **Improved Maintainability:** Easier to understand and modify the component and its data.
- **Fewer Errors:** Lower likelihood of developers providing incorrectly structured data.

## 5. Considerations

- **Refactoring Effort:** All existing usages of `ConfusionMatrix` and `EvaluationCard` (where it uses confusion matrices) will need to be updated. This is primarily in the documentation examples but should be checked globally.
- **Deriving Labels:** Decide if the `labels: string[]` prop in `ConfusionMatrixData` is still the primary source for column/row order or if this can be fully derived from the new `matrix` structure (e.g., by taking all unique `actualClassLabel` and keys from `predictedClassCounts`). Using `labels` as the canonical ordering is likely still beneficial for consistent UI.
- **Data Transformation:** `EvaluationCard` might need to transform data if it receives it in a different format from its source before passing it to the `ConfusionMatrix` component, though ideally, the source data would also adopt the new clear structure.

## 6. Next Steps

1.  **Review & Approve:** Discuss this plan with the team.
2.  **Implementation:**
    a.  Define the new `ConfusionMatrixRow` and update `ConfusionMatrixData` interface in `dashboard/components/confusion-matrix.tsx`.
    b.  Refactor the `ConfusionMatrix` component to use the new data structure.
    c.  Update `EvaluationCard.tsx` to adapt its `confusionMatrixData` prop and correctly pass data to the `ConfusionMatrix` component.
    d.  Refactor all examples in `dashboard/app/documentation/concepts/evaluation-metrics/page.tsx`.
    e.  Search for and update any other usages in the codebase.
3.  **Testing:** Thoroughly test all instances of the confusion matrix to ensure correct display and data interpretation.
4.  **Documentation Update:** Update all relevant TSDoc/JSDoc comments. 