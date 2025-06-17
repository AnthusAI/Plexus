'use client'

import React from 'react'
import { BaseGauges, BaseGaugesConfig, BaseGaugesData } from './BaseGauges'
import { useTaskMetrics } from '../hooks/useUnifiedMetrics'

// Configuration for task-specific gauges (single gauge example)  
const tasksGaugesConfig: BaseGaugesConfig = {
  // Use flex layout with exact grid-calculated widths to match multi-gauge components
  layout: 'flex',
  gaugeWidths: {
    base: 'calc((100% - 0.75rem * (2 - 1)) / 2)',  // 1 of 2 columns with 0.75rem gap
    sm: 'calc((100% - 0.75rem * (3 - 1)) / 3)',    // 1 of 3 columns with 0.75rem gap
    md: 'calc((100% - 0.75rem * (4 - 1)) / 4)',    // 1 of 4 columns with 0.75rem gap
    lg: 'calc((100% - 0.75rem * (5 - 1)) / 5)',    // 1 of 5 columns with 0.75rem gap
    xl: 'calc((100% - 0.75rem * (6 - 1)) / 6)',    // 1 of 6 columns with 0.75rem gap
  },
  
  gauges: [
    {
      key: 'tasks',
      title: 'Tasks / hour',
      valueKey: 'tasksPerHour',
      averageKey: 'tasksAveragePerHour',
      peakKey: 'tasksPeakHourly',
      totalKey: 'tasksTotal24h',
      color: 'hsl(var(--chart-1))',
      unit: '',
      decimalPlaces: 0,
      segments: [
        { start: 0, end: 10, color: 'var(--false)' },
        { start: 10, end: 90, color: 'var(--neutral)' },
        { start: 90, end: 100, color: 'var(--true)' }
      ]
    }
  ],
  chartAreas: [
    {
      dataKey: 'tasks',
      label: 'Tasks',
      color: 'var(--primary)',
      fillOpacity: 0.8
    }
  ],
  chartConfig: {
    tasks: {
      label: 'Tasks',
      color: 'hsl(var(--chart-1))',
    },
  }
}

interface TasksGaugesProps {
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

export function TasksGauges({ 
  className,
  overrideData,
  useRealData = true,
  disableEmergenceAnimation = false,
  onErrorClick
}: TasksGaugesProps) {
  // Use real task metrics
  const { 
    metrics: metricsData, 
    isLoading, 
    error 
  } = useTaskMetrics()

  // Transform metrics data to BaseGaugesData format
  // For task metrics, we use the items data since tasks are tracked as items
  const data: BaseGaugesData | null = metricsData ? {
    tasksPerHour: metricsData.itemsPerHour || 0,
    tasksAveragePerHour: metricsData.itemsAveragePerHour || 0,
    tasksPeakHourly: metricsData.itemsPeakHourly || 10, // Use higher baseline for tasks
    tasksTotal24h: metricsData.itemsTotal24h || 0,
    chartData: metricsData.chartData?.map((point: any) => ({
      time: point.time,
      tasks: point.items || 0 // Map items to tasks for chart display
    })) || [],
    lastUpdated: metricsData.lastUpdated || new Date(),
    hasErrorsLast24h: metricsData.hasErrorsLast24h || false,
    totalErrors24h: metricsData.totalErrors24h || 0
  } : null

  return (
    <BaseGauges
      className={className}
      config={tasksGaugesConfig}
      data={useRealData ? data : null}
      isLoading={isLoading}
      error={error}
      title="Tasks, Last 24 Hours"
      overrideData={overrideData}
      useRealData={useRealData}
      disableEmergenceAnimation={disableEmergenceAnimation}
      onErrorClick={onErrorClick}
    />
  )
} 