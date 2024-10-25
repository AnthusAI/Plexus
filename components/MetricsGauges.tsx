'use client'

import React from 'react'
import { Gauge } from './gauge'

interface GaugeData {
  id: string
  value: number
  label: string
}

interface MetricsGaugesProps {
  gauges: GaugeData[]
}

const SingleGauge: React.FC<GaugeData> = ({ value, label }) => (
  <div className="text-center">
    <Gauge value={value} title={label} />
  </div>
)

const MetricsGauges: React.FC<MetricsGaugesProps> = ({ gauges }) => {
  return (
    <div 
      data-testid="metrics-gauges" 
      className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6"
    >
      {gauges.map((gauge) => (
        <SingleGauge key={gauge.id} {...gauge} />
      ))}
    </div>
  )
}

export default MetricsGauges
