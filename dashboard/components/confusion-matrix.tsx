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

export interface ConfusionMatrixData {
  matrix: number[][]
  labels: string[]
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
  if (!data || data.matrix.length !== data.labels.length) {
    return (
      <Alert variant="destructive">
        <ExclamationTriangleIcon className="h-4 w-4" />
        <AlertTitle>Error</AlertTitle>
        <AlertDescription>Invalid confusion matrix data</AlertDescription>
      </Alert>
    )
  }

  const maxValue = Math.max(...data.matrix.flat())

  const getBackgroundColor = (value: number) => {
    const opacity = Math.max(0.15, value / maxValue)
    return `hsl(var(--purple-6) / ${opacity})`
  }

  const getTextColor = (value: number) => {
    // Use white text for cells with values close to the max value
    const threshold = maxValue * 0.7; // 70% of max value
    return value >= threshold ? 'text-white' : 'text-card-selected-foreground';
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
            {data.labels.map((label, index) => (
              <TooltipProvider key={`row-${index}`}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <div 
                      onClick={() => handleActualLabelClick(label)}
                      className="flex items-center justify-center h-16 relative min-w-0
                        cursor-pointer hover:bg-muted/50"
                    >
                      <span className="-rotate-90 whitespace-nowrap text-sm 
                        text-muted-foreground truncate">
                        {label}
                      </span>
                    </div>
                  </TooltipTrigger>
                  <TooltipContent>
                    <div className="flex flex-col gap-1">
                      <p>{label}</p>
                      <div 
                        role="button"
                        onClick={() => handleActualLabelClick(label)}
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
            {/* Bottom labels */}
            <div className="flex">
              {data.matrix[0].map((_, colIndex) => (
                <div key={`col-${colIndex}`} 
                  className="flex flex-col flex-1 basis-0 min-w-0">
                  {data.matrix.map((row, rowIndex) => (
                    <TooltipProvider key={`cell-${rowIndex}-${colIndex}`}>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <div
                            onClick={() => handleCellClick(
                              data.labels[colIndex], 
                              data.labels[rowIndex]
                            )}
                            className={`flex items-center justify-center h-16
                              text-sm font-medium truncate ${getTextColor(row[colIndex])}
                              cursor-pointer hover:opacity-80`}
                            style={{
                              backgroundColor: getBackgroundColor(row[colIndex]),
                            }}
                          >
                            {row[colIndex]}
                          </div>
                        </TooltipTrigger>
                        <TooltipContent>
                          <div className="flex flex-col gap-1">
                            <p>Predicted: {data.labels[colIndex]}</p>
                            <p>Actual: {data.labels[rowIndex]}</p>
                            <p>Count: {row[colIndex]}</p>
                            <div 
                              role="button"
                              onClick={() => handleCellClick(
                                data.labels[colIndex], 
                                data.labels[rowIndex]
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
                  ))}
                </div>
              ))}
            </div>

            {/* Bottom labels */}
            <div className="flex">
              {data.labels.map((label, index) => (
                <TooltipProvider key={`bottom-${index}`}>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <div 
                        onClick={() => handlePredictedLabelClick(label)}
                        className="flex-1 basis-0 flex items-center justify-center 
                          border-t-0 min-w-0 w-8 overflow-hidden
                          cursor-pointer hover:bg-muted/50"
                      >
                        <span className="text-sm text-muted-foreground truncate w-full 
                          text-center">
                          {label}
                        </span>
                      </div>
                    </TooltipTrigger>
                    <TooltipContent>
                      <div className="flex flex-col gap-1">
                        <p>{label}</p>
                        <div 
                          role="button"
                          onClick={() => handlePredictedLabelClick(label)}
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

            {/* Predicted label */}
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