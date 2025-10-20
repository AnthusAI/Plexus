'use client'

import React from 'react'
import { Gauge } from './gauge'
import type { Segment } from './gauge'
import { cn } from '@/lib/utils'

interface MetricsSummaryProps {
  gauge: {
    value?: number
    target?: number
    label: string
    segments?: Segment[]
    min?: number
    max?: number
    backgroundColor?: string
    valueUnit?: string
    decimalPlaces?: number
  }
  evaluationUrl: string
  className?: string
}

const MetricsSummary: React.FC<MetricsSummaryProps> = ({
  gauge,
  evaluationUrl,
  className = ''
}) => {
  const [key, setKey] = React.useState(0)
  const ref = React.useRef<HTMLAnchorElement>(null)

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
    <a
      href={evaluationUrl}
      target="_blank"
      rel="noopener noreferrer"
      data-testid="metrics-summary"
      className={cn("block flex-shrink-0 cursor-pointer hover:opacity-80 transition-opacity", className)}
      ref={ref}
      style={{ width: '120px' }}
      onClick={(e) => e.stopPropagation()}
    >
      <div key={key}>
        <Gauge
          value={gauge.value}
          target={gauge.target}
          title={gauge.label}
          min={gauge.min}
          max={gauge.max}
          backgroundColor={gauge.backgroundColor}
          showTicks={false}
          valueUnit={gauge.valueUnit}
          decimalPlaces={gauge.decimalPlaces}
        />
      </div>
    </a>
  )
}

export default MetricsSummary
