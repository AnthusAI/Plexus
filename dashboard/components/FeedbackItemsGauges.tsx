'use client'

import React from 'react'
import { BaseGauges, BaseGaugesConfig, BaseGaugesData } from './BaseGauges'
import { useFeedbackMetrics } from '../hooks/useUnifiedMetrics'

// Configuration for feedback-specific gauges (single gauge example)  
const feedbackGaugesConfig: BaseGaugesConfig = {
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
      key: 'feedbackItems',
      title: 'Feedback Items / hour',
      valueKey: 'feedbackItemsPerHour',
      averageKey: 'feedbackItemsAveragePerHour',
      peakKey: 'feedbackItemsPeakHourly',
      totalKey: 'feedbackItemsTotal24h',
      color: 'hsl(var(--chart-3))',
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
      dataKey: 'feedbackItems',
      label: 'Feedback Items',
      color: '#8b5cf6',
      fillOpacity: 0.8
    }
  ],
  chartConfig: {
    feedbackItems: {
      label: 'Feedback Items',
      color: 'hsl(var(--chart-3))',
    },
  }
}

interface FeedbackItemsGaugesProps {
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

export function FeedbackItemsGauges({ 
  className,
  overrideData,
  useRealData = true,
  disableEmergenceAnimation = false,
  onErrorClick
}: FeedbackItemsGaugesProps) {
  // Use real feedback metrics
  const { 
    metrics: metricsData, 
    isLoading, 
    error 
  } = useFeedbackMetrics()

  // Transform metrics data to BaseGaugesData format
  // For feedback metrics, we use the items data which contains feedbackItems counts
  const data: BaseGaugesData | null = metricsData ? {
    feedbackItemsPerHour: metricsData.itemsPerHour || 0,
    feedbackItemsAveragePerHour: metricsData.itemsAveragePerHour || 0,
    feedbackItemsPeakHourly: metricsData.itemsPeakHourly || 10,
    feedbackItemsTotal24h: metricsData.itemsTotal24h || 0,
    chartData: metricsData.chartData?.map((point: any) => ({
      time: point.time,
      feedbackItems: point.items || 0 // Map items to feedbackItems for chart display
    })) || [],
    lastUpdated: metricsData.lastUpdated || new Date(),
    hasErrorsLast24h: metricsData.hasErrorsLast24h || false,
    totalErrors24h: metricsData.totalErrors24h || 0
  } : null

  return (
    <BaseGauges
      className={className}
      config={feedbackGaugesConfig}
      data={useRealData ? data : null}
      isLoading={isLoading}
      error={error}
      title="Feedback Items, Last 24 Hours"
      overrideData={overrideData}
      useRealData={useRealData}
      disableEmergenceAnimation={disableEmergenceAnimation}
      onErrorClick={onErrorClick}
    />
  )
} 