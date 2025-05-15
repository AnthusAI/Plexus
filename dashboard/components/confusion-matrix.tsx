"use client"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { ExclamationTriangleIcon } from "@radix-ui/react-icons"
import { Grid2X2, ArrowRight } from "lucide-react"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

export interface ConfusionMatrixRow {
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

/**
 * Props for the ConfusionMatrix component
 * @param data The confusion matrix data containing the matrix and class labels
 * @param onSelectionChange Callback when any selection is made, providing both predicted 
 *                         and actual class values. Either may be null if not selected.
 */
export interface ConfusionMatrixProps {
  data: ConfusionMatrixData
  onSelectionChange?: (selection: {
    predicted: string | null
    actual: string | null
  }) => void
}

/**
 * ConfusionMatrix Component
 * 
 * Displays a confusion matrix with interactive elements:
 * - Clickable cells showing the count of predictions
 * - Tooltips with detailed information
 * - Row labels showing actual classes
 * - Column labels showing predicted classes
 * 
 * All interactions (cell clicks, row labels, column labels) emit a standardized
 * selection event with both predicted and actual values, using null for the 
 * unselected dimension:
 * - Cell click: { predicted: "class1", actual: "class2" }
 * - Row label: { predicted: null, actual: "class2" }
 * - Column label: { predicted: "class1", actual: null }
 */
export function ConfusionMatrix({ data, onSelectionChange }: ConfusionMatrixProps) {
  // Updated validation logic
  if (!data || !data.labels) {
    return (
      <Alert variant="destructive">
        <ExclamationTriangleIcon className="h-4 w-4" />
        <AlertTitle>Error</AlertTitle>
        <AlertDescription>Invalid confusion matrix: Missing data or labels.</AlertDescription>
      </Alert>
    )
  }

  if (data.matrix && data.labels.length === 0 && data.matrix.length > 0) {
    // if matrix has data but no labels are defined to interpret it
    return (
      <Alert variant="destructive">
        <ExclamationTriangleIcon className="h-4 w-4" />
        <AlertTitle>Error</AlertTitle>
        <AlertDescription>Invalid confusion matrix: Data provided but 'labels' array is empty or missing.</AlertDescription>
      </Alert>
    )
  }
  
  // Validate that all actualClassLabels and predictedClassLabels in the matrix are present in the main 'labels' array
  for (const row of data.matrix) {
    if (!data.labels.includes(row.actualClassLabel)) {
      return (
        <Alert variant="destructive">
          <ExclamationTriangleIcon className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>
            Invalid confusion matrix: 'actualClassLabel' "{row.actualClassLabel}" not found in 'labels' array.
          </AlertDescription>
        </Alert>
      );
    }
    for (const predictedLabel of Object.keys(row.predictedClassCounts)) {
      if (!data.labels.includes(predictedLabel)) {
        return (
          <Alert variant="destructive">
            <ExclamationTriangleIcon className="h-4 w-4" />
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>
              Invalid confusion matrix: Predicted class label "{predictedLabel}" from 'predictedClassCounts' not found in 'labels' array.
            </AlertDescription>
          </Alert>
        );
      }
    }
  }

  const allCounts = data.matrix.reduce((acc, row) => {
    acc.push(...Object.values(row.predictedClassCounts));
    return acc;
  }, [] as number[]);
  
  const maxValue = allCounts.length > 0 ? Math.max(...allCounts) : 1;


  const getBackgroundColor = (value: number) => {
    const opacity = Math.max(0.15, value / maxValue) // Ensure some color even for 0, if maxValue is > 0
    return `hsl(var(--purple-6) / ${opacity})`
  }

  const getTextColor = (value: number) => {
    const threshold = maxValue * 0.9; // 90% of max value
    return value >= threshold && maxValue > 0 ? 'text-foreground-selected' : 'text-foreground'; // ensure maxValue > 0 for threshold logic
  }

  const handleCellClick = (predicted: string, actual: string) => {
    onSelectionChange?.({ predicted, actual })
  }

  const handlePredictedLabelClick = (label: string) => {
    onSelectionChange?.({ predicted: label, actual: null })
  }

  const handleActualLabelClick = (label: string) => {
    onSelectionChange?.({ predicted: null, actual: label })
  }
  
  // effectiveMatrix will be used for rendering. If data.matrix is empty but labels are provided,
  // we can still render the structure with all zero counts.
  const effectiveMatrix = data.matrix;

  return (
    <div className="flex flex-col w-full gap-1">
      <div className="flex items-center gap-1 text-sm text-foreground h-5">
        <Grid2X2 className="w-4 h-4 text-foreground shrink-0" />
        <span>Confusion matrix</span>
      </div>

      <div className="flex">
        <div className="flex">
          {/* Actual label column - height matches only the matrix */}
          <div className="w-6">
            <div className="flex flex-col items-center justify-center w-6"
              style={{ height: `${data.labels.length * 64}px` }}>
              <span className="-rotate-90 whitespace-nowrap text-sm
                text-muted-foreground truncate">
                Actual
              </span>
            </div>
          </div>

          {/* Row labels column */}
          <div className="flex flex-col w-6 shrink-0">
            {/* Iterate over data.labels for actual class labels (rows) */}
            {data.labels.map((actualLabel, index) => (
              <TooltipProvider key={`row-label-${actualLabel}-${index}`}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <div
                      onClick={() => handleActualLabelClick(actualLabel)}
                      className="flex items-center justify-center h-16 relative min-w-0
                        cursor-pointer hover:bg-muted/50"
                    >
                      <span className="-rotate-90 whitespace-nowrap text-sm
                        text-muted-foreground truncate">
                        {actualLabel}
                      </span>
                    </div>
                  </TooltipTrigger>
                  <TooltipContent>
                    <div className="flex flex-col gap-1">
                      <p>{actualLabel}</p>
                      <div
                        role="button"
                        onClick={() => handleActualLabelClick(actualLabel)}
                        className="flex items-center gap-1 text-xs bg-muted
                          px-2 py-0.5 rounded-full mt-1 text-muted-foreground
                          cursor-pointer hover:bg-muted/80"
                      >
                        <span>View</span>
                        <ArrowRight className="h-3 w-3" />
                      </div>
                    </div>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            ))}
          </div>
        </div>

        {/* Matrix columns - enforce equal width distribution */}
        <div className="flex flex-col min-w-0 flex-1">
          {/* Matrix cells */}
          <div className="flex flex-col">
            <div className="flex">
              {/* Iterate over PREDICTED classes (columns) based on data.labels */}
              {data.labels.map((predictedLabel, colIndex) => (
                <div key={`col-cells-${predictedLabel}-${colIndex}`}
                  className="flex flex-col flex-1 basis-0 min-w-0">
                  {/* Iterate over ACTUAL classes (rows) based on data.labels */}
                  {data.labels.map((actualLabel, rowIndex) => {
                    // Find the corresponding row in effectiveMatrix by actualClassLabel
                    const matrixRow = effectiveMatrix.find(r => r.actualClassLabel === actualLabel);
                    // Get the count for the current predictedLabel from that row's predictedClassCounts
                    // Default to 0 if the actualLabel row doesn't exist or if the predictedLabel is not in its counts
                    const count = matrixRow ? (matrixRow.predictedClassCounts[predictedLabel] ?? 0) : 0;

                    return (
                      <TooltipProvider key={`cell-${actualLabel}-${predictedLabel}-${rowIndex}-${colIndex}`}>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <div
                              onClick={() => handleCellClick(
                                predictedLabel,
                                actualLabel
                              )}
                              className={`flex items-center justify-center h-16
                                text-sm font-medium truncate ${getTextColor(count)}
                                cursor-pointer hover:opacity-80`}
                              style={{
                                backgroundColor: getBackgroundColor(count),
                              }}
                            >
                              {count}
                            </div>
                          </TooltipTrigger>
                          <TooltipContent>
                            <div className="flex flex-col gap-1">
                              <p>Predicted: {predictedLabel}</p>
                              <p>Actual: {actualLabel}</p>
                              <p>Count: {count}</p>
                              <div
                                role="button"
                                onClick={() => handleCellClick(
                                  predictedLabel,
                                  actualLabel
                                )}
                                className="flex items-center gap-1 text-xs bg-muted
                                  px-2 py-0.5 rounded-full mt-1 text-muted-foreground
                                  cursor-pointer hover:bg-muted/80"
                              >
                                <span>View</span>
                                <ArrowRight className="h-3 w-3" />
                              </div>
                            </div>
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    );
                  })}
                </div>
              ))}
            </div>

            {/* Bottom labels for Predicted Classes */}
            <div className="flex">
              {data.labels.map((predictedLabel, index) => (
                <TooltipProvider key={`bottom-label-${predictedLabel}-${index}`}>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <div
                        onClick={() => handlePredictedLabelClick(predictedLabel)}
                        className="flex-1 basis-0 flex items-center justify-center
                          border-t-0 min-w-0 w-8 overflow-hidden
                          cursor-pointer hover:bg-muted/50"
                      >
                        <span className="text-sm text-muted-foreground truncate w-full
                          text-center">
                          {predictedLabel}
                        </span>
                      </div>
                    </TooltipTrigger>
                    <TooltipContent>
                      <div className="flex flex-col gap-1">
                        <p>{predictedLabel}</p>
                        <div
                          role="button"
                          onClick={() => handlePredictedLabelClick(predictedLabel)}
                          className="flex items-center gap-1 text-xs bg-muted
                            px-2 py-0.5 rounded-full mt-1 text-muted-foreground
                            cursor-pointer hover:bg-muted/80"
                        >
                          <span>View</span>
                          <ArrowRight className="h-3 w-3" />
                        </div>
                      </div>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              ))}
            </div>

            {/* Predicted label text */}
            <div className="flex">
              <div className="flex-1 basis-0 flex items-center justify-center
                border-t-0 min-w-0 overflow-hidden">
                <span className="text-sm text-muted-foreground truncate">
                  Predicted
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}