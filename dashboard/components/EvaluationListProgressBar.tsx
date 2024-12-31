import React from "react"
import { ProgressBar } from "@/components/ui/progress-bar"

interface EvaluationListProgressBarProps {
  progress: number
  totalSamples?: number
  isFocused?: boolean
}

export function EvaluationListProgressBar({ 
  progress, 
  totalSamples,
  isFocused = false
}: EvaluationListProgressBarProps) {
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