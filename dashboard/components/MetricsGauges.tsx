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
  selectedIndex?: number
}

const MetricsGauges: React.FC<MetricsGaugesProps> = ({ 
  gauges, 
  className = '',
  variant = 'detail',
  metricsExplanation,
  selectedIndex
}) => {
  const [key, setKey] = React.useState(0)
  const ref = React.useRef<HTMLDivElement>(null)

  React.useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            setKey(prev => prev + 1)
          }
        })
      },
      { threshold: 0.5 }
    )

    if (ref.current) {
      observer.observe(ref.current)
    }

    return () => {
      if (ref.current) {
        observer.unobserve(ref.current)
      }
    }
  }, [])

  return (
    <div 
      data-testid="metrics-gauges" 
      className="flex flex-col items-center w-full"
      ref={ref}
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
            key={`${index}-${key}`}
            data-testid="gauge-container"
            className={cn(
              "flex justify-center rounded-lg p-2 transition-colors duration-500 ease-in-out",
              index === selectedIndex && variant === 'detail' ? "bg-card-light" : "bg-card"
            )}
            style={{
              '--gauge-background-transition': index === selectedIndex ? gauge.backgroundColor : 'var(--card-light)',
              transition: 'background-color 0.5s ease-in-out, --gauge-background-transition 0.5s ease-in-out'
            } as React.CSSProperties}
          >
            <Gauge
              value={gauge.value}
              title={gauge.label}
              min={gauge.min}
              max={gauge.max}
              backgroundColor={index === selectedIndex ? gauge.backgroundColor : 'var(--card-light)'}
              showTicks={variant === 'detail'}
              information={gauge.information}
              priority={index === selectedIndex}
            />
          </div>
        ))}
      </div>
    </div>
  )
}

export default MetricsGauges
