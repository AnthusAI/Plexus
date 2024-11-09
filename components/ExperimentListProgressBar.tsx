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
  // Round progress to nearest whole number
  const roundedProgress = Math.round(progress)
  
  return (
    <ProgressBar 
      progress={roundedProgress}
      processedItems={totalSamples ? Math.round(progress * totalSamples / 100) : undefined}
      totalItems={totalSamples}
      color="secondary"
    />
  )
} 