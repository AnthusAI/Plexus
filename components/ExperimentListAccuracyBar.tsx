import React from "react"

interface ExperimentListAccuracyBarProps {
  progress: number
  accuracy: number
}

export function ExperimentListAccuracyBar({ progress, accuracy }: ExperimentListAccuracyBarProps) {
  // Round accuracy to nearest whole number first, then clamp
  const roundedAccuracy = Math.round(accuracy)
  const clampedAccuracy = Math.min(Math.max(roundedAccuracy, 0), 100)
  const clampedProgress = Math.min(Math.max(progress, 0), 100)
  const opacity = clampedProgress / 100
  const trueWidth = clampedAccuracy
  const falseWidth = 100 - trueWidth
  
  return (
    <div className="relative w-full h-6 bg-neutral rounded-md">
      {clampedProgress > 0 && (
        <>
          <div
            className={`absolute top-0 left-0 h-full flex items-center pl-2 text-xs text-primary-foreground font-medium rounded-md`}
            style={{ width: 'auto' }}
          >
            {clampedAccuracy}%
          </div>
          {trueWidth > 0 && (
            <div
              className="absolute top-0 left-0 h-full bg-true flex items-center pl-2 text-xs text-primary-foreground font-medium"
              style={{ 
                width: `${trueWidth}%`, 
                borderTopLeftRadius: 'inherit', 
                borderBottomLeftRadius: 'inherit',
                borderTopRightRadius: falseWidth === 0 ? 'inherit' : 0,
                borderBottomRightRadius: falseWidth === 0 ? 'inherit' : 0,
                opacity
              }}
            >
              {clampedAccuracy}%
            </div>
          )}
          {falseWidth > 0 && (
            <div
              className="absolute top-0 h-full bg-false"
              style={{ 
                left: `${trueWidth}%`, 
                width: `${falseWidth}%`,
                borderTopRightRadius: 'inherit',
                borderBottomRightRadius: 'inherit',
                opacity
              }}
            />
          )}
        </>
      )}
    </div>
  )
} 