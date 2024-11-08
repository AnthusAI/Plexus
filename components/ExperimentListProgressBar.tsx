import React from "react"

interface ExperimentListProgressBarProps {
  progress: number
  totalSamples?: number
}

export function ExperimentListProgressBar({ 
  progress, 
  totalSamples 
}: ExperimentListProgressBarProps) {
  const clampedProgress = Math.min(Math.max(progress, 0), 100)
  
  return (
    <div className="relative w-full h-6 bg-neutral rounded-md">
      <div
        className={`absolute top-0 left-0 h-full flex items-center pl-2 
          text-xs text-primary-foreground font-medium rounded-md ${
          clampedProgress > 0 ? 'bg-secondary' : ''
        }`}
        style={{ width: clampedProgress > 0 ? `${clampedProgress}%` : 'auto' }}
      >
        {clampedProgress}%
      </div>
      {totalSamples !== undefined && (
        <div className="absolute top-0 right-2 h-full flex items-center
          text-xs text-primary-foreground font-medium">
          {totalSamples}
        </div>
      )}
    </div>
  )
} 