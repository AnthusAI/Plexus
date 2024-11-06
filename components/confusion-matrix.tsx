"use client"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { ExclamationTriangleIcon } from "@radix-ui/react-icons"

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
    return `hsl(var(--blue-${Math.max(1, intensity)}))` 
  }

  return (
    <div className="w-full flex flex-col">
      <div className="relative w-full" style={{ paddingTop: 'calc(100% - 2.5rem)' }}>
        <div className="absolute inset-0 grid" style={{ 
          gridTemplateColumns: `minmax(1.5rem, auto) 1.5rem 1fr`
        }}>
          {/* Actual label */}
          <div className="flex items-center justify-center">
            <div className="transform -rotate-90 origin-[50%_50%] whitespace-nowrap text-sm font-medium text-muted-foreground min-w-[1.5rem]">
              Actual
            </div>
          </div>

          {/* Row labels */}
          <div className="grid" style={{ 
            gridTemplateRows: `repeat(${data.labels.length}, 1fr)`
          }}>
            {data.labels.map((label, index) => (
              <div key={`row-label-${index}`} className="flex items-center justify-end min-w-[1.5rem]">
                <div className="transform -rotate-90 origin-[50%_50%] whitespace-nowrap text-xs font-medium text-muted-foreground">
                  {label}
                </div>
              </div>
            ))}
          </div>

          {/* Matrix cells */}
          <div className="grid" style={{ 
            gridTemplateColumns: `repeat(${data.labels.length}, 1fr)`,
            gridTemplateRows: `repeat(${data.labels.length}, 1fr)`,
          }}>
            {data.matrix.flat().map((value, index) => (
              <div
                key={`cell-${index}`}
                className="flex items-center justify-center text-xl font-medium text-foreground"
                style={{
                  backgroundColor: getBackgroundColor(value),
                }}
              >
                {value}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Bottom labels stay the same */}
      <div className="h-5 flex items-center justify-center" 
        style={{ paddingLeft: "calc(1.5rem + 1.5rem)" }}>
        {data.labels.map((label, index) => (
          <div key={`header-${index}`} className="flex-1 text-center text-xs font-medium text-muted-foreground">
            {label}
          </div>
        ))}
      </div>
      <div className="h-5 flex items-center justify-center"
        style={{ paddingLeft: "calc(1.5rem + 1.5rem)" }}>
        <div className="text-sm font-medium text-muted-foreground">Predicted</div>
      </div>
    </div>
  )
}