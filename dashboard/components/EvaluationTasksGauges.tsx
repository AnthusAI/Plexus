'use client'

import React from 'react'
import { BaseGauges, BaseGaugesConfig, BaseGaugesData } from './BaseGauges'
import { useEvaluationsMetrics } from '../hooks/useUnifiedMetrics'

// Configuration for evaluation-specific gauges (two gauges: evaluations + score results)  
const evaluationTasksGaugesConfig: BaseGaugesConfig = {
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
      key: 'evaluations',
      title: 'Evaluations / hour',
      valueKey: 'evaluationsPerHour',
      averageKey: 'evaluationsAveragePerHour',
      peakKey: 'evaluationsPeakHourly',
      totalKey: 'evaluationsTotal24h',
      color: 'hsl(var(--chart-1))',
      unit: '',
      decimalPlaces: 0,
      segments: [
        { start: 0, end: 90, color: 'var(--neutral)' },
        { start: 90, end: 100, color: 'var(--false)' }
      ]
    },
    {
      key: 'scoreResults',
      title: 'Score Results / hour',
      valueKey: 'scoreResultsPerHour',
      averageKey: 'scoreResultsAveragePerHour',
      peakKey: 'scoreResultsPeakHourly',
      totalKey: 'scoreResultsTotal24h',
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
      dataKey: 'evaluations',
      label: 'Evaluations',
      color: 'var(--primary)',
      fillOpacity: 0.8
    },
    {
      dataKey: 'scoreResults',
      label: 'Score Results',
      color: 'var(--secondary)',
      fillOpacity: 0.8
    }
  ],
  chartConfig: {
    evaluations: {
      label: 'Evaluations',
      color: 'hsl(var(--chart-1))',
    },
    scoreResults: {
      label: 'Score Results',
      color: 'hsl(var(--chart-2))',
    },
  }
}

interface EvaluationTasksGaugesProps {
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

export function EvaluationTasksGauges({ 
  className,
  overrideData,
  useRealData = true,
  disableEmergenceAnimation = false,
  onErrorClick
}: EvaluationTasksGaugesProps) {
  // Time range state for navigation
  const [timeRange, setTimeRange] = React.useState<{ start: Date; end: Date; period: 'hour' | 'day' | 'week' } | null>(null)
  
  // Use evaluations metrics (Evaluation records + evaluation score results)
  const { 
    metrics: metricsData, 
    isLoading, 
    error 
  } = useEvaluationsMetrics({
    timeRange: timeRange || undefined
  })

  // Transform metrics data to BaseGaugesData format
  // For evaluations, we use both task data (evaluation tasks) and scoreResults data (score results from evaluations)
  const data: BaseGaugesData | null = metricsData ? {
    // Evaluations data (from tasks with taskType: 'evaluation')
    evaluationsPerHour: metricsData.itemsPerHour || 0,
    evaluationsAveragePerHour: metricsData.itemsAveragePerHour || 0,
    evaluationsPeakHourly: metricsData.itemsPeakHourly || 10, // Use higher baseline for evaluations
    evaluationsTotal24h: metricsData.itemsTotal24h || 0,
    
    // Score Results data (from scoreResults with scoreResultType: 'evaluation')
    scoreResultsPerHour: metricsData.scoreResultsPerHour || 0,
    scoreResultsAveragePerHour: metricsData.scoreResultsAveragePerHour || 0,
    scoreResultsPeakHourly: metricsData.scoreResultsPeakHourly || 300, // Use higher baseline for score results
    scoreResultsTotal24h: metricsData.scoreResultsTotal24h || 0,
    
    chartData: metricsData.chartData?.map((point: any) => ({
      time: point.time,
      evaluations: point.items || 0, // Map items to evaluations for chart display
      scoreResults: point.scoreResults || 0, // Map scoreResults for chart display
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
      config={evaluationTasksGaugesConfig}
      data={useRealData ? data : null}
      isLoading={isLoading}
      error={error}
      title="Evaluations & Score Results"
      overrideData={overrideData}
      useRealData={useRealData}
      disableEmergenceAnimation={disableEmergenceAnimation}
      onErrorClick={onErrorClick}
      enableTimeNavigation={true}
      onTimeRangeChange={setTimeRange}
    />
  )
} 