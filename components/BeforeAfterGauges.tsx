import React from 'react'
import { Gauge } from './gauge'
import type { Segment } from './gauge'

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
  return (
    <div data-testid="before-after-gauges" className="flex flex-col items-center w-full">
      <div className="text-lg font-bold mb-0">{title}</div>
      <div className="flex w-full justify-center space-x-8">
        <Gauge 
          value={before} 
          title="Before"
          segments={segments}
          min={min}
          max={max}
          showTicks={variant === 'detail'}
          backgroundColor={backgroundColor}
        />
        <Gauge 
          value={after} 
          title="After"
          segments={segments}
          min={min}
          max={max}
          showTicks={variant === 'detail'}
          backgroundColor={backgroundColor}
        />
      </div>
    </div>
  )
}

export default BeforeAfterGauges
