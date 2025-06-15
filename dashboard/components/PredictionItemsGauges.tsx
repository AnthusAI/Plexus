'use client'

import React from 'react'
import { BaseGauges, BaseGaugesConfig, BaseGaugesData } from './BaseGauges'
import { usePredictionMetrics, UnifiedMetricsData } from '@/hooks/useUnifiedMetrics'

// Configuration for prediction-specific gauges
const predictionGaugesConfig: BaseGaugesConfig = {
  gauges: [
    {
      key: 'items',
      title: 'Prediction Items / hour',
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
      title: 'Prediction Score Results / hour',
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
      label: 'Prediction Items',
      color: 'hsl(var(--chart-1))',
    },
    {
      dataKey: 'scoreResults',
      label: 'Prediction Score Results',
      color: 'hsl(var(--chart-2))',
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
  const { metrics, isLoading, error } = usePredictionMetrics()
  
  // Transform the metrics data to match BaseGaugesData interface
  const transformedData: BaseGaugesData | null = metrics ? {
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