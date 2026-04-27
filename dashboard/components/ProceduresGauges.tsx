'use client'

import React from 'react'
import { BaseGauges, BaseGaugesConfig, BaseGaugesData } from './BaseGauges'
import { useProceduresMetrics } from '../hooks/useUnifiedMetrics'

// Configuration for procedures-specific gauges.
const proceduresGaugesConfig: BaseGaugesConfig = {
  // Use grid layout to match ItemsGauges pattern
  layout: 'grid',
  gridCols: {
    base: 1,
    sm: 2,
    md: 3,
    lg: 4,
    xl: 5
  },
  chartSpan: {
    base: 1,
    sm: 1,
    md: 2,
    lg: 3,
    xl: 4
  },
  
  gauges: [
    {
      key: 'procedures',
      title: 'Procedures / hour',
      valueKey: 'proceduresPerHour',
      averageKey: 'proceduresAveragePerHour',
      peakKey: 'proceduresPeakHourly',
      totalKey: 'proceduresTotal24h',
      color: 'hsl(var(--chart-1))',
      unit: '',
      decimalPlaces: 0,
      segments: [
        { start: 0, end: 90, color: 'var(--neutral)' },
        { start: 90, end: 100, color: 'var(--false)' }
      ]
    }
  ],
  chartAreas: [
    {
      dataKey: 'procedures',
      label: 'Procedures',
      color: 'var(--primary)',
      fillOpacity: 0.8
    }
  ],
  chartConfig: {
    procedures: {
      label: 'Procedures',
      color: 'hsl(var(--chart-1))',
    },
  }
}

interface ProceduresGaugesProps {
  className?: string
  // Override props for Storybook/testing
  overrideData?: Partial<BaseGaugesData>
  // Control whether to use real data or override props
  useRealData?: boolean
  // Disable emergence animation (for drawer usage)
  disableEmergenceAnimation?: boolean
  // Error handling
  onErrorClick?: () => void
}

export function ProceduresGauges({ 
  className,
  overrideData,
  useRealData = true,
  disableEmergenceAnimation = false,
  onErrorClick
}: ProceduresGaugesProps) {
  // Use procedures metrics.
  const { 
    metrics: metricsData, 
    isLoading, 
    error 
  } = useProceduresMetrics()

  // Transform metrics data to BaseGaugesData format
  const data: BaseGaugesData | null = metricsData ? {
    // Procedures data
    proceduresPerHour: metricsData.itemsPerHour || 0,
    proceduresAveragePerHour: metricsData.itemsAveragePerHour || 0,
    proceduresPeakHourly: metricsData.itemsPeakHourly || 10, // Use higher baseline for procedures
    proceduresTotal24h: metricsData.itemsTotal24h || 0,
    chartData: metricsData.chartData?.map((point: any) => ({
      time: point.time,
      procedures: point.items || 0, // Map items to procedures for chart display
      bucketStart: point.bucketStart,
      bucketEnd: point.bucketEnd
    })) || [],
    lastUpdated: metricsData.lastUpdated || new Date(),
    hasErrorsLast24h: metricsData.hasErrorsLast24h || false,
    totalErrors24h: metricsData.totalErrors24h || 0
  } : null

  return (
    <BaseGauges
      className={className}
      config={proceduresGaugesConfig}
      data={useRealData ? data : null}
      isLoading={isLoading}
      error={error}
      title="Procedures"
      overrideData={overrideData}
      useRealData={useRealData}
      disableEmergenceAnimation={disableEmergenceAnimation}
      onErrorClick={onErrorClick}
    />
  )
}
