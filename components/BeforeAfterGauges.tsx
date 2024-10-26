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
}

const BeforeAfterGauges: React.FC<BeforeAfterGaugesProps> = ({
  title,
  before,
  after,
  segments,
  min,
  max,
}) => {
  return (
    <div data-testid="before-after-gauges" className="flex flex-col items-center">
      <div className="text-xl font-medium mb-4">{title}</div>
      <div className="flex space-x-8">
        <Gauge 
          value={before} 
          title="Before"
          segments={segments}
          min={min}
          max={max}
        />
        <Gauge 
          value={after} 
          title="After"
          segments={segments}
          min={min}
          max={max}
        />
      </div>
    </div>
  )
}

export default BeforeAfterGauges
