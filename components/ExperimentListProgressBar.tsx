import React from "react"
import { ProgressBar } from "@/components/ui/progress-bar"

interface ExperimentListProgressBarProps {
  progress: number
  totalSamples?: number
}

export function ExperimentListProgressBar({ 
  progress, 
  totalSamples 
}: ExperimentListProgressBarProps) {
  return (
    <ProgressBar 
      progress={progress}
      processedItems={totalSamples ? Math.round(progress * totalSamples / 100) : undefined}
      totalItems={totalSamples}
      color="secondary"
    />
  )
} 