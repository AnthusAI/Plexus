'use client'

import React from 'react'
import { BaseGauges, BaseGaugesConfig, BaseGaugesData } from './BaseGauges'
import { useProceduresMetrics } from '../hooks/useUnifiedMetrics'

// Configuration for procedures-specific gauges (two gauges: procedures + chat sessions)
const proceduresGaugesConfig: BaseGaugesConfig = {
  // Use grid layout to match ItemsGauges pattern
  layout: 'grid',
  gridCols: {
    base: 2,  // < 500px: 2 cols, chart spans full width on second row
    sm: 3,    // >= 500px: 3 cols, chart takes 1 remaining column
    md: 4,    // >= 700px: 4 cols, chart takes 2 remaining columns  
    lg: 5,    // >= 900px: 5 cols, chart takes 3 remaining columns
    xl: 6     // >= 1100px: 6 cols, chart takes 4 remaining columns
  },
  chartSpan: {
    base: 2,  // spans full width on second row
    sm: 1,    // spans 1 remaining column
    md: 2,    // spans 2 remaining columns
    lg: 3,    // spans 3 remaining columns
    xl: 4     // spans 4 remaining columns
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
      key: 'chatSessions',
      title: 'Chat Sessions / hour',
      valueKey: 'chatSessionsPerHour',
      averageKey: 'chatSessionsAveragePerHour',
      peakKey: 'chatSessionsPeakHourly',
      totalKey: 'chatSessionsTotal24h',
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
      dataKey: 'chatSessions',
      label: 'Chat Sessions',
      color: 'var(--secondary)',
      fillOpacity: 0.8
    }
  ],
  chartConfig: {
    procedures: {
      label: 'Procedures',
      color: 'hsl(var(--chart-1))',
    },
    chatSessions: {
      label: 'Chat Sessions',
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
  // Use procedures metrics (procedures and chat sessions)
  const { 
    metrics: metricsData, 
    isLoading, 
    error 
  } = useProceduresMetrics()

  // Transform metrics data to BaseGaugesData format.
  // `scoreResults*` fields are reused for the second series in unified gauges.
  const data: BaseGaugesData | null = metricsData ? {
    // Procedures data
    proceduresPerHour: metricsData.itemsPerHour || 0,
    proceduresAveragePerHour: metricsData.itemsAveragePerHour || 0,
    proceduresPeakHourly: metricsData.itemsPeakHourly || 10, // Use higher baseline for procedures
    proceduresTotal24h: metricsData.itemsTotal24h || 0,
    
    // Chat sessions data
    chatSessionsPerHour: metricsData.scoreResultsPerHour || 0,
    chatSessionsAveragePerHour: metricsData.scoreResultsAveragePerHour || 0,
    chatSessionsPeakHourly: metricsData.scoreResultsPeakHourly || 10,
    chatSessionsTotal24h: metricsData.scoreResultsTotal24h || 0,
    
    chartData: metricsData.chartData?.map((point: any) => ({
      time: point.time,
      procedures: point.items || 0, // Map items to procedures for chart display
      chatSessions: point.scoreResults || 0,
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
      title="Procedures & Chat Sessions, Last 24 Hours"
      overrideData={overrideData}
      useRealData={useRealData}
      disableEmergenceAnimation={disableEmergenceAnimation}
      onErrorClick={onErrorClick}
    />
  )
}
