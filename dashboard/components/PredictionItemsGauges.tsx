'use client'

import React from 'react'
import { BaseGauges, BaseGaugesConfig, BaseGaugesData } from './BaseGauges'
import { useItemsMetricsWithType } from '@/hooks/useItemsMetricsWithType'

// Configuration for prediction-specific gauges
const predictionGaugesConfig: BaseGaugesConfig = {
  gauges: [
    {
      key: 'predictionItems',
      title: 'Prediction Items / hour',
      valueKey: 'predictionItemsPerHour',
      averageKey: 'predictionItemsAveragePerHour',
      peakKey: 'predictionItemsPeakHourly',
      totalKey: 'predictionItemsTotal24h',
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
      key: 'predictionScoreResults',
      title: 'Prediction Score Results / hour',
      valueKey: 'predictionScoreResultsPerHour',
      averageKey: 'predictionScoreResultsAveragePerHour',
      peakKey: 'predictionScoreResultsPeakHourly',
      totalKey: 'predictionScoreResultsTotal24h',
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
      label: 'Prediction Items',
      color: '#10b981',
      fillOpacity: 0.8
    },
    {
      dataKey: 'scoreResults',
      label: 'Prediction Score Results',
      color: '#f59e0b',
      fillOpacity: 0.6
    }
  ],
  chartConfig: {
    items: {
      label: 'Prediction Items',
      color: 'hsl(var(--chart-1))',
    },
    scoreResults: {
      label: 'Prediction Score Results', 
      color: 'hsl(var(--chart-2))',
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

interface PredictionItemsGaugesProps {
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

export function PredictionItemsGauges({ 
  className,
  overrideData,
  useRealData = true,
  disableEmergenceAnimation = false,
  onErrorClick
}: PredictionItemsGaugesProps) {
  const { metrics, isLoading, error } = useItemsMetricsWithType()
  
  // Transform the metrics data to match BaseGaugesData interface
  const transformedData: BaseGaugesData | null = metrics ? {
    // Prediction items metrics (we'll need to add these to the hook)
    predictionItemsPerHour: 0, // TODO: Add to useItemsMetricsWithType
    predictionItemsAveragePerHour: 0, // TODO: Add to useItemsMetricsWithType
    predictionItemsPeakHourly: 50, // TODO: Add to useItemsMetricsWithType
    predictionItemsTotal24h: 0, // TODO: Add to useItemsMetricsWithType
    
    // Prediction score results metrics
    predictionScoreResultsPerHour: metrics.predictions.scoreResultsPerHour,
    predictionScoreResultsAveragePerHour: metrics.predictions.scoreResultsAveragePerHour,
    predictionScoreResultsPeakHourly: Math.max(metrics.predictions.scoreResultsPerHour, metrics.predictions.scoreResultsAveragePerHour, 300),
    predictionScoreResultsTotal24h: metrics.predictions.scoreResultsTotal24h,
    
    // Chart data (use prediction-specific chart data)
    chartData: metrics.predictions.chartData,
    lastUpdated: metrics.lastUpdated,
    hasErrorsLast24h: false, // TODO: Add prediction-specific error tracking
    totalErrors24h: 0 // TODO: Add prediction-specific error tracking
  } : null

  return (
    <BaseGauges
      className={className}
      config={predictionGaugesConfig}
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