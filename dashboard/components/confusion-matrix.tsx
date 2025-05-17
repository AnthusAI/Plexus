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
import { useCallback } from "react"

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
  // Use callbacks for event handlers to prevent re-renders
  const handleCellClick = useCallback((predicted: string, actual: string) => {
    onSelectionChange?.({ predicted, actual })
  }, [onSelectionChange])

  const handlePredictedLabelClick = useCallback((label: string) => {
    onSelectionChange?.({ predicted: label, actual: null })
  }, [onSelectionChange])

  const handleActualLabelClick = useCallback((label: string) => {
    onSelectionChange?.({ predicted: null, actual: label })
  }, [onSelectionChange])

  // Safe default for maxValue in case validation fails
  const maxValue = data?.matrix 
    ? Math.max(1, ...data.matrix.reduce((acc, row) => {
        if (row && row.predictedClassCounts) {
          acc.push(...Object.values(row.predictedClassCounts));
        }
        return acc;
      }, [] as number[]))
    : 1;

  const getBackgroundColor = useCallback((value: number) => {
    const opacity = Math.max(0.15, value / maxValue) // Ensure some color even for 0, if maxValue is > 0
    return `hsl(var(--purple-6) / ${opacity})`
  }, [maxValue])

  const getTextColor = useCallback((value: number) => {
    const threshold = maxValue * 0.9; // 90% of max value
    return value >= threshold && maxValue > 0 ? 'text-foreground-selected' : 'text-foreground'; // ensure maxValue > 0 for threshold logic
  }, [maxValue])

  // Validate data structure
  if (!data || !data.labels || !Array.isArray(data.labels)) {
    return (
      <Alert variant="destructive">
        <ExclamationTriangleIcon className="h-4 w-4" />
        <AlertTitle>Error</AlertTitle>
        <AlertDescription>Invalid confusion matrix: Missing data or labels.</AlertDescription>
      </Alert>
    )
  }

  // Validate matrix structure
  if (!data.matrix || !Array.isArray(data.matrix)) {
    return (
      <Alert variant="destructive">
        <ExclamationTriangleIcon className="h-4 w-4" />
        <AlertTitle>Error</AlertTitle>
        <AlertDescription>Invalid confusion matrix: Missing or malformed matrix data.</AlertDescription>
      </Alert>
    )
  }

  if (data.labels.length === 0 && data.matrix.length > 0) {
    // if matrix has data but no labels are defined to interpret it
    return (
      <Alert variant="destructive">
        <ExclamationTriangleIcon className="h-4 w-4" />
        <AlertTitle>Error</AlertTitle>
        <AlertDescription>Invalid confusion matrix: Data provided but 'labels' array is empty or missing.</AlertDescription>
      </Alert>
    )
  }
  
  // Get all counts for color scaling
  const allCounts = data.matrix.reduce((acc, row) => {
    if (row && row.predictedClassCounts) {
      acc.push(...Object.values(row.predictedClassCounts));
    }
    return acc;
  }, [] as number[]);
  
  // We can safely reuse maxValue from the top-level calculation

  return (
    <div className="flex flex-col w-full gap-1 overflow-visible" style={{ overflow: 'visible', position: 'relative' }}>
      <div className="flex items-center gap-1 text-sm text-foreground h-5">
        <Grid2X2 className="w-4 h-4 text-foreground shrink-0" />
        <span>Confusion matrix</span>
      </div>

      <div className="flex flex-col min-w-0 flex-1 overflow-visible">
        {/* Matrix cells with integrated labels */}
        <div className="flex flex-col overflow-visible">
          {/* Iterate over ACTUAL classes (rows) based on data.labels */}
          {data.labels.map((actualLabel, rowIndex) => (
            <div key={`row-${actualLabel}-${rowIndex}`} className="flex overflow-visible">
              {/* Iterate over PREDICTED classes (columns) based on data.labels */}
              {data.labels.map((predictedLabel, colIndex) => {
                // Find the corresponding row in matrix by actualClassLabel
                const matrixRow = data.matrix.find(r => r && r.actualClassLabel === actualLabel);
                // Get the count for the current predictedLabel from that row's predictedClassCounts
                // Default to 0 if the actualLabel row doesn't exist or if the predictedLabel is not in its counts
                const count = matrixRow && matrixRow.predictedClassCounts ? 
                  (matrixRow.predictedClassCounts[predictedLabel] ?? 0) : 0;

                return (
                  <TooltipProvider key={`cell-${actualLabel}-${predictedLabel}-${rowIndex}-${colIndex}`}>
                    <Tooltip key={`tooltip-${actualLabel}-${predictedLabel}-${rowIndex}-${colIndex}`}>
                      <TooltipTrigger asChild>
                        <div
                          onClick={() => handleCellClick(
                            predictedLabel,
                            actualLabel
                          )}
                          className={`flex items-center justify-center h-16 relative
                            text-sm font-medium truncate ${getTextColor(count)}
                            cursor-pointer hover:opacity-80 flex-1 basis-0 min-w-0`}
                          style={{
                            backgroundColor: getBackgroundColor(count),
                          }}
                        >
                          {/* Bottom label (Column/Predicted) - only for last row */}
                          {rowIndex === data.labels.length - 1 && (
                            <div 
                              onClick={(e) => {
                                e.stopPropagation();
                                handlePredictedLabelClick(predictedLabel);
                              }}
                              className="absolute bottom-0 left-0 right-0 text-xs 
                                text-foreground text-center truncate px-0.5
                                hover:bg-muted/50 rounded-sm"
                              style={{
                                bottom: '-2px',
                              }}
                            >
                              {predictedLabel}
                            </div>
                          )}
                          
                          {/* Left label (Row/Actual) - only for first column */}
                          {colIndex === 0 && (
                            <div 
                              onClick={(e) => {
                                e.stopPropagation();
                                handleActualLabelClick(actualLabel);
                              }}
                              className="absolute left-0 text-xs 
                                text-foreground truncate
                                hover:bg-muted/50 rounded-sm px-0.5"
                              style={{
                                top: '50%',
                                left: '-2px',
                                transform: 'translateY(-50%) rotate(180deg)',
                                writingMode: 'vertical-rl',
                                textOrientation: 'mixed',
                                width: 'auto',
                                height: 'max-content',
                                maxHeight: '60px',
                              }}
                            >
                              {actualLabel}
                            </div>
                          )}
                          
                          {/* Cell value */}
                          <div>{count}</div>
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
      </div>

      {/* Headers for the matrix */}
      <div className="flex justify-between text-xs text-muted-foreground mt-2">
        <div className="flex items-center">
          <span>← Actual</span>
        </div>
        <div className="flex items-center">
          <span>Predicted ↑</span>
        </div>
      </div>
    </div>
  )
} 