'use client'

import React from 'react'
import { Gauge } from './gauge'
import type { Segment } from './gauge'

interface GaugeConfig {
  value: number
  label: string
  segments?: Segment[]
  min?: number
  max?: number
  backgroundColor?: string
  showTicks?: boolean
}

interface MetricsGaugesProps {
  gauges: GaugeConfig[]
  className?: string
}

const MetricsGauges: React.FC<MetricsGaugesProps> = ({ gauges, className = '' }) => {
  return (
    <div 
      data-testid="metrics-gauges" 
      className={`flex w-full justify-center space-x-8 ${className}`}
    >
      {gauges.map((gauge, index) => (
        <Gauge
          key={index}
          value={gauge.value}
          title={gauge.label}
          segments={gauge.segments}
          min={gauge.min}
          max={gauge.max}
          backgroundColor={gauge.backgroundColor}
          showTicks={gauge.showTicks}
        />
      ))}
    </div>
  )
}

export default MetricsGauges
