'use client'

import React, { useState, useMemo } from 'react'
import { BaseGauges, BaseGaugesConfig, BaseGaugesData } from './BaseGauges'
import { useTaskMetrics } from '../hooks/useUnifiedMetrics'

// Helper function to calculate time range based on period and offset
function calculateTimeRange(period: 'hour' | 'day' | 'week', offset: number): { start: Date; end: Date } {
  const now = new Date()
  
  let periodMs: number
  switch (period) {
    case 'hour':
      periodMs = 60 * 60 * 1000
      break
    case 'day':
      periodMs = 24 * 60 * 60 * 1000
      break
    case 'week':
      periodMs = 7 * 24 * 60 * 60 * 1000
      break
  }
  
  const end = new Date(now.getTime() - (offset * periodMs))
  const start = new Date(end.getTime() - periodMs)
  
  return { start, end }
}

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
        { start: 0, end: 90, color: 'var(--neutral)' },
        { start: 90, end: 100, color: 'var(--false)' }
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
  // Time navigation state
  const [timePeriod, setTimePeriod] = useState<'hour' | 'day' | 'week'>('day')
  const [timeOffset, setTimeOffset] = useState(0)

  // Calculate time range based on period and offset
  const timeRange = useMemo(() => calculateTimeRange(timePeriod, timeOffset), [timePeriod, timeOffset])

  // Use real task metrics with time range
  const { 
    metrics: metricsData, 
    isLoading, 
    error 
  } = useTaskMetrics({
    timeRange: {
      start: timeRange.start,
      end: timeRange.end,
      period: timePeriod
    }
  })

  // Transform metrics data to BaseGaugesData format
  // For task metrics, we query the tasks recordType from AggregatedMetrics
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
      enableTimeNavigation={true}
      timePeriod={timePeriod}
      timeOffset={timeOffset}
      onTimePeriodChange={setTimePeriod}
      onTimeOffsetChange={setTimeOffset}
    />
  )
} 