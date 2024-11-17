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

export type ConfusionMatrixData = {
  matrix: number[][]
  labels: string[]
}

export function ConfusionMatrix({ data }: { data: ConfusionMatrixData }) {
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
    const intensity = Math.round((value / maxValue) * 10)
    return `hsl(var(--violet-${Math.max(1, intensity)}))` 
  }

  const getTextColor = (value: number) => {
    const intensity = Math.round((value / maxValue) * 10)
    return intensity > 5 ? 'text-white dark:text-foreground' : 'text-primary'
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
            <div className="flex flex-col items-center justify-center w-6 border" 
              style={{ height: `${data.labels.length * 32}px` }}>
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
                    <div className="flex items-center justify-center h-8 border relative min-w-0">
                      <span className="-rotate-90 whitespace-nowrap text-sm 
                        text-muted-foreground truncate">
                        {label}
                      </span>
                    </div>
                  </TooltipTrigger>
                  <TooltipContent>
                    <div className="flex flex-col gap-1">
                      <p>{label}</p>
                      <div className="flex items-center gap-1 text-xs bg-muted 
                        px-2 py-0.5 rounded-full mt-1 text-muted-foreground">
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
                            className={`flex items-center justify-center h-8 border
                              text-sm font-medium truncate ${getTextColor(row[colIndex])}`}
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
                            <div className="flex items-center gap-1 text-xs bg-muted 
                              px-2 py-0.5 rounded-full mt-1 text-muted-foreground">
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
                      <div className="flex-1 basis-0 flex items-center justify-center h-8 
                        border border-t-0 min-w-0 w-8 overflow-hidden">
                        <span className="text-sm text-muted-foreground truncate w-full 
                          text-center">
                          {label}
                        </span>
                      </div>
                    </TooltipTrigger>
                    <TooltipContent>
                      <div className="flex flex-col gap-1">
                        <p>{label}</p>
                        <div className="flex items-center gap-1 text-xs bg-muted 
                          px-2 py-0.5 rounded-full mt-1 text-muted-foreground">
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
              <div className="flex-1 basis-0 flex items-center justify-center h-8 
                border border-t-0 min-w-0 overflow-hidden">
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