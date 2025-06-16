'use client'

import React from 'react'
import { BaseGauges, BaseGaugesConfig, BaseGaugesData } from './BaseGauges'
import { useEvaluationMetrics, UnifiedMetricsData } from '@/hooks/useUnifiedMetrics'

// Configuration for evaluation-specific gauges
const evaluationGaugesConfig: BaseGaugesConfig = {
  gauges: [
    {
      key: 'items',
      title: 'Evaluation Items / hour',
      valueKey: 'itemsPerHour',
      averageKey: 'itemsAveragePerHour',
      peakKey: 'itemsPeakHourly',
      totalKey: 'itemsTotal24h',
      color: 'hsl(var(--primary))',
      unit: '',
      decimalPlaces: 0,
    },
    {
      key: 'scoreResults',
      title: 'Evaluation Score Results / hour',
      valueKey: 'scoreResultsPerHour',
      averageKey: 'scoreResultsAveragePerHour',
      peakKey: 'scoreResultsPeakHourly',
      totalKey: 'scoreResultsTotal24h',
      color: 'hsl(var(--secondary))',
      unit: '',
      decimalPlaces: 0,
    }
  ],
  chartAreas: [
    {
      dataKey: 'items',
      label: 'Evaluation Items',
      color: '#3b82f6',
    },
    {
      dataKey: 'scoreResults',
      label: 'Evaluation Score Results',
      color: '#a855f7',
    }
  ],
  chartConfig: {
    items: {
      label: 'Evaluation Items',
      color: 'hsl(var(--primary))',
    },
    scoreResults: {
      label: 'Evaluation Score Results', 
      color: 'hsl(var(--secondary))',
    },
  },
  gridCols: {
    base: 2,  // < 500px: 2 columns
    sm: 3,    // >= 500px: 3 columns
    md: 4,    // >= 700px: 4 columns
    lg: 5,    // >= 900px: 5 columns
    xl: 6     // >= 1100px: 6 columns
  },
  chartSpan: {
    base: 2,  // < 500px: chart spans full width (2 cols)
    sm: 1,    // >= 500px: chart spans 1 remaining column
    md: 2,    // >= 700px: chart spans 2 remaining columns
    lg: 3,    // >= 900px: chart spans 3 remaining columns
    xl: 4     // >= 1100px: chart spans 4 remaining columns
  }
}

interface EvaluationItemsGaugesProps {
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

export function EvaluationItemsGauges({ 
  className,
  overrideData,
  useRealData = true,
  disableEmergenceAnimation = false,
  onErrorClick
}: EvaluationItemsGaugesProps) {
  const { metrics, isLoading, error } = useEvaluationMetrics()
  
  // Transform the metrics data to match BaseGaugesData interface
  const transformedData: BaseGaugesData | null = metrics ? {
    // Items metrics now available with createdByType filtering
    itemsPerHour: metrics.itemsPerHour,
    itemsAveragePerHour: metrics.itemsAveragePerHour,
    itemsPeakHourly: metrics.itemsPeakHourly,
    itemsTotal24h: metrics.itemsTotal24h,
    
    scoreResultsPerHour: metrics.scoreResultsPerHour,
    scoreResultsAveragePerHour: metrics.scoreResultsAveragePerHour,
    scoreResultsPeakHourly: metrics.scoreResultsPeakHourly,
    scoreResultsTotal24h: metrics.scoreResultsTotal24h,
    
    chartData: metrics.chartData,
    lastUpdated: metrics.lastUpdated,
    hasErrorsLast24h: metrics.hasErrorsLast24h,
    totalErrors24h: metrics.totalErrors24h,
  } : null

  return (
    <BaseGauges
      className={className}
      config={evaluationGaugesConfig}
      data={transformedData}
      isLoading={isLoading}
      error={error}
      title="Evaluations Items, Last 24 Hours"
      overrideData={overrideData}
      useRealData={useRealData}
      disableEmergenceAnimation={disableEmergenceAnimation}
      onErrorClick={onErrorClick}
    />
  )
} 