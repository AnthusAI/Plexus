'use client'

import React from 'react'
import { BaseGauges, BaseGaugesConfig, BaseGaugesData } from './BaseGauges'
import { useItemsMetricsWithType } from '@/hooks/useItemsMetricsWithType'

// Configuration for evaluation-specific gauges
const evaluationGaugesConfig: BaseGaugesConfig = {
  gauges: [
    {
      key: 'evaluationItems',
      title: 'Evaluation Items / hour',
      valueKey: 'evaluationItemsPerHour',
      averageKey: 'evaluationItemsAveragePerHour',
      peakKey: 'evaluationItemsPeakHourly',
      totalKey: 'evaluationItemsTotal24h',
      color: 'hsl(var(--primary))',
      unit: '',
      decimalPlaces: 0,
      segments: [
        { start: 0, end: 10, color: 'var(--false)' },
        { start: 10, end: 90, color: 'var(--neutral)' },
        { start: 90, end: 100, color: 'var(--true)' }
      ]
    },
    {
      key: 'evaluationScoreResults',
      title: 'Evaluation Score Results / hour',
      valueKey: 'evaluationScoreResultsPerHour',
      averageKey: 'evaluationScoreResultsAveragePerHour',
      peakKey: 'evaluationScoreResultsPeakHourly',
      totalKey: 'evaluationScoreResultsTotal24h',
      color: 'hsl(var(--secondary))',
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
      dataKey: 'items',
      label: 'Evaluation Items',
      color: '#3b82f6',
      fillOpacity: 0.8
    },
    {
      dataKey: 'scoreResults',
      label: 'Evaluation Score Results',
      color: '#a855f7',
      fillOpacity: 0.6
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
  const { metrics, isLoading, error } = useItemsMetricsWithType()
  
  // Transform the metrics data to match BaseGaugesData interface
  const transformedData: BaseGaugesData | null = metrics ? {
    // Evaluation items metrics (we'll need to add these to the hook)
    evaluationItemsPerHour: 0, // TODO: Add to useItemsMetricsWithType
    evaluationItemsAveragePerHour: 0, // TODO: Add to useItemsMetricsWithType
    evaluationItemsPeakHourly: 50, // TODO: Add to useItemsMetricsWithType
    evaluationItemsTotal24h: 0, // TODO: Add to useItemsMetricsWithType
    
    // Evaluation score results metrics
    evaluationScoreResultsPerHour: metrics.evaluations.scoreResultsPerHour,
    evaluationScoreResultsAveragePerHour: metrics.evaluations.scoreResultsAveragePerHour,
    evaluationScoreResultsPeakHourly: Math.max(metrics.evaluations.scoreResultsPerHour, metrics.evaluations.scoreResultsAveragePerHour, 300),
    evaluationScoreResultsTotal24h: metrics.evaluations.scoreResultsTotal24h,
    
    // Chart data (use evaluation-specific chart data)
    chartData: metrics.evaluations.chartData,
    lastUpdated: metrics.lastUpdated,
    hasErrorsLast24h: false, // TODO: Add evaluation-specific error tracking
    totalErrors24h: 0 // TODO: Add evaluation-specific error tracking
  } : null

  return (
    <BaseGauges
      className={className}
      config={evaluationGaugesConfig}
      data={transformedData}
      isLoading={isLoading}
      error={error}
      overrideData={overrideData}
      useRealData={useRealData}
      disableEmergenceAnimation={disableEmergenceAnimation}
      onErrorClick={onErrorClick}
    />
  )
} 