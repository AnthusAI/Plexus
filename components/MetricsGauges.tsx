'use client'

import React from 'react'
import { Gauge } from './gauge'
import type { Segment } from './gauge'
import { cn } from '@/lib/utils'

interface GaugeConfig {
  value?: number
  label: string
  segments?: Segment[]
  min?: number
  max?: number
  backgroundColor?: string
  showTicks?: boolean
  information?: string
}

interface MetricsGaugesProps {
  gauges: GaugeConfig[]
  className?: string
  variant?: 'grid' | 'detail'
}

const MetricsGauges: React.FC<MetricsGaugesProps> = ({ 
  gauges, 
  className = '',
  variant = 'detail'
}) => {
  return (
    <div 
      data-testid="metrics-gauges" 
      className="flex flex-col items-center w-full"
    >
      <div className={cn(
        "w-full",
        variant === 'detail' 
          ? 'grid grid-cols-2 gap-2' 
          : 'flex justify-center'
      )}>
        {gauges.map((gauge, index) => (
          <div key={index} className="flex justify-center">
            <Gauge
              value={gauge.value}
              title={gauge.label}
              min={gauge.min}
              max={gauge.max}
              backgroundColor={gauge.backgroundColor}
              showTicks={variant === 'detail'}
              information={gauge.information}
            />
          </div>
        ))}
      </div>
    </div>
  )
}

export default MetricsGauges
