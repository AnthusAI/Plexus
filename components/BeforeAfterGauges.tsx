import React from 'react'
import { Gauge, type Segment } from './gauge'

interface BeforeAfterGaugesProps {
  title: string
  before: number
  after: number
  segments?: Segment[]
  min?: number
  max?: number
  variant?: 'grid' | 'detail'
  backgroundColor?: string
}

const getChangeArrow = (before: number, after: number) => {
  const difference = after - before
  const percentChange = (difference / before) * 100
  
  if (difference === 0) return '→'
  
  if (difference > 0) {
    if (percentChange >= 50) return '↑'
    return '↗'
  } else {
    if (percentChange <= -50) return '↓'
    return '↘'
  }
}

const BeforeAfterGauges: React.FC<BeforeAfterGaugesProps> = ({
  title,
  before,
  after,
  segments,
  min,
  max,
  variant = 'grid',
  backgroundColor
}) => {
  const arrowCharacter = getChangeArrow(before, after)
  
  return (
    <div data-testid="before-after-gauges" className="flex justify-center w-full">
      <div className="relative">
        <Gauge 
          value={after}
          beforeValue={before}
          title={title}
          segments={segments}
          min={min}
          max={max}
          showTicks={variant === 'detail'}
          backgroundColor={backgroundColor}
        />
        <div 
          className="absolute left-1/2 -translate-x-1/2 text-xs text-muted-foreground whitespace-nowrap"
          style={{
            bottom: variant === 'detail' ? '24px' : '36px'
          }}
        >
          {before}% {arrowCharacter} {after}%
        </div>
      </div>
    </div>
  )
}

export default BeforeAfterGauges
