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
import { useTranslations } from "@/app/contexts/TranslationContext"

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
  const t = useTranslations('evaluations');

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

  const getBackgroundColor = (value: number, predicted: string, actual: string) => {
    const opacity = Math.max(0.15, value / maxValue) // Ensure some color even for 0, if maxValue is > 0
    // Use true color for correct predictions (diagonal), false color for incorrect
    return predicted === actual
      ? `hsl(var(--green-6) / ${opacity})`
      : `hsl(var(--red-6) / ${opacity})`
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
    <div className="flex flex-col w-full gap-1 overflow-visible" style={{ overflow: 'visible', position: 'relative' }}>
      <div className="flex items-center gap-1 text-sm text-foreground h-5">
        <Grid2X2 className="w-4 h-4 text-foreground shrink-0" />
        <span>{t('confusionMatrix')}</span>
      </div>

      <div className="flex flex-col min-w-0 flex-1 overflow-visible">
        {/* Matrix cells with integrated labels */}
        <div className="flex flex-col overflow-visible">
          {/* Iterate over ACTUAL classes (rows) based on data.labels */}
          {data.labels.map((actualLabel, rowIndex) => (
            <div key={`row-${actualLabel}-${rowIndex}`} className="flex overflow-visible">
              {/* Iterate over PREDICTED classes (columns) based on data.labels */}
              {data.labels.map((predictedLabel, colIndex) => {
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
                          className={`flex items-center justify-center h-16 relative
                            text-sm font-medium truncate ${getTextColor(count)}
                            cursor-pointer hover:opacity-80 flex-1 basis-0 min-w-0`}
                          style={{
                            backgroundColor: getBackgroundColor(count, predictedLabel, actualLabel),
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
        
        {/* Axis labels */}
        <div className="flex mt-2 text-xs text-foreground overflow-visible" style={{ overflow: 'visible' }}>
          <div className="flex-1 text-center relative" style={{ marginTop: '-10px' }}>Predicted</div>
          <div className="absolute" 
               style={{ 
                 top: '50%', 
                 left: '-2em', 
                 zIndex: 10, 
                 transform: 'translateY(-50%) rotate(-90deg)',
                 transformOrigin: 'center center'
               }}>
            Actual
          </div>
        </div>
      </div>
    </div>
  )
} 