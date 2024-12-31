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
  priority?: boolean
}

interface MetricsGaugesProps {
  gauges: GaugeConfig[]
  className?: string
  variant?: 'grid' | 'detail'
  metricsExplanation?: string | null
}

const MetricsGauges: React.FC<MetricsGaugesProps> = ({ 
  gauges, 
  className = '',
  variant = 'detail',
  metricsExplanation
}) => {
  return (
    <div 
      data-testid="metrics-gauges" 
      className="flex flex-col items-center w-full"
    >
      {metricsExplanation && variant === 'detail' && (
        <p className="text-sm text-muted-foreground mb-4 text-left w-full">
          {metricsExplanation}
        </p>
      )}
      <div className={cn(
        "w-full",
        variant === 'detail' 
          ? 'grid grid-cols-2 gap-2' 
          : 'flex justify-center'
      )}>
        {gauges.map((gauge, index) => (
          <div 
            key={index}
            data-testid="gauge-container"
            className={cn(
              "flex justify-center rounded-lg p-2",
              gauge.priority && variant === 'detail' ? "bg-card-light" : "bg-card"
            )}
          >
            <Gauge
              value={gauge.value}
              title={gauge.label}
              min={gauge.min}
              max={gauge.max}
              backgroundColor={gauge.priority ? gauge.backgroundColor : 'var(--card-light)'}
              showTicks={variant === 'detail'}
              information={gauge.information}
              priority={gauge.priority}
            />
          </div>
        ))}
      </div>
    </div>
  )
}

export default MetricsGauges
