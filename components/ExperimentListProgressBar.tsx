import React from "react"
import { ProgressBar } from "@/components/ui/progress-bar"

interface ExperimentListProgressBarProps {
  progress: number
  totalSamples?: number
  isFocused?: boolean
}

export function ExperimentListProgressBar({ 
  progress, 
  totalSamples,
  isFocused = false
}: ExperimentListProgressBarProps) {
  const roundedProgress = Math.round(progress)
  
  return (
    <ProgressBar 
      progress={roundedProgress}
      processedItems={totalSamples ? Math.round(progress * totalSamples / 100) : undefined}
      totalItems={totalSamples}
      color="secondary"
      isFocused={isFocused}
    />
  )
} 