'use client'

import React from 'react'
import { BaseGauges, BaseGaugesConfig, BaseGaugesData } from './BaseGauges'
import { useEvaluationsMetrics, useProceduresMetrics } from '../hooks/useUnifiedMetrics'

type ProceduresChartPoint = {
  time: string
  procedures?: number
  evaluations?: number
  bucketStart?: string
  bucketEnd?: string
}

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
    md: 1,
    lg: 2,
    xl: 3
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
    },
    {
      key: 'evaluations',
      title: 'Evaluations / hour',
      valueKey: 'evaluationsPerHour',
      averageKey: 'evaluationsAveragePerHour',
      peakKey: 'evaluationsPeakHourly',
      totalKey: 'evaluationsTotal24h',
      color: 'hsl(var(--chart-2))',
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
    },
    {
      dataKey: 'evaluations',
      label: 'Evaluations',
      color: 'var(--secondary)',
      fillOpacity: 0.8
    }
  ],
  chartConfig: {
    procedures: {
      label: 'Procedures',
      color: 'hsl(var(--chart-1))',
    },
    evaluations: {
      label: 'Evaluations',
      color: 'hsl(var(--chart-2))',
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
  // Use procedures and evaluations metrics for the Procedures dashboard.
  const { 
    metrics: proceduresMetrics, 
    isLoading: isProceduresLoading, 
    error: proceduresError 
  } = useProceduresMetrics()
  const {
    metrics: evaluationsMetrics,
    isLoading: isEvaluationsLoading,
    error: evaluationsError
  } = useEvaluationsMetrics()

  const chartDataByTime = new Map<string, ProceduresChartPoint>()

  proceduresMetrics?.chartData?.forEach((point: any) => {
    chartDataByTime.set(point.time, {
      time: point.time,
      procedures: point.items || 0,
      bucketStart: point.bucketStart,
      bucketEnd: point.bucketEnd
    })
  })

  evaluationsMetrics?.chartData?.forEach((point: any) => {
    const existing: ProceduresChartPoint = chartDataByTime.get(point.time) || { time: point.time }
    chartDataByTime.set(point.time, {
      ...existing,
      evaluations: point.items || 0,
      bucketStart: existing.bucketStart || point.bucketStart,
      bucketEnd: existing.bucketEnd || point.bucketEnd
    })
  })

  const chartData = Array.from(chartDataByTime.values()).map((point) => ({
    procedures: 0,
    evaluations: 0,
    ...point
  }))

  // Transform metrics data to BaseGaugesData format
  const data: BaseGaugesData | null = proceduresMetrics || evaluationsMetrics ? {
    // Procedures data
    proceduresPerHour: proceduresMetrics?.itemsPerHour || 0,
    proceduresAveragePerHour: proceduresMetrics?.itemsAveragePerHour || 0,
    proceduresPeakHourly: proceduresMetrics?.itemsPeakHourly || 10, // Use higher baseline for procedures
    proceduresTotal24h: proceduresMetrics?.itemsTotal24h || 0,

    // Evaluations data
    evaluationsPerHour: evaluationsMetrics?.itemsPerHour || 0,
    evaluationsAveragePerHour: evaluationsMetrics?.itemsAveragePerHour || 0,
    evaluationsPeakHourly: evaluationsMetrics?.itemsPeakHourly || 10,
    evaluationsTotal24h: evaluationsMetrics?.itemsTotal24h || 0,

    chartData,
    lastUpdated: proceduresMetrics?.lastUpdated || evaluationsMetrics?.lastUpdated || new Date(),
    hasErrorsLast24h: proceduresMetrics?.hasErrorsLast24h || evaluationsMetrics?.hasErrorsLast24h || false,
    totalErrors24h: (proceduresMetrics?.totalErrors24h || 0) + (evaluationsMetrics?.totalErrors24h || 0)
  } : null

  return (
    <BaseGauges
      className={className}
      config={proceduresGaugesConfig}
      data={useRealData ? data : null}
      isLoading={isProceduresLoading || isEvaluationsLoading}
      error={proceduresError || evaluationsError}
      title="Procedures"
      overrideData={overrideData}
      useRealData={useRealData}
      disableEmergenceAnimation={disableEmergenceAnimation}
      onErrorClick={onErrorClick}
    />
  )
}
