'use client'

import React from 'react'
import { BaseGauges, BaseGaugesConfig, BaseGaugesData } from './BaseGauges'

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
        { start: 0, end: 10, color: 'var(--false)' },
        { start: 10, end: 90, color: 'var(--neutral)' },
        { start: 90, end: 100, color: 'var(--true)' }
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
  // For now, we'll use mock data since we don't have a feedback-specific hook yet
  const isLoading = false
  const error = null
  
  // Mock data for demonstration
  const mockData: BaseGaugesData = {
    feedbackItemsPerHour: 12,
    feedbackItemsAveragePerHour: 8,
    feedbackItemsPeakHourly: 25,
    feedbackItemsTotal24h: 192,
    chartData: [
      { time: '24h ago', feedbackItems: 5 },
      { time: '20h ago', feedbackItems: 8 },
      { time: '16h ago', feedbackItems: 12 },
      { time: '12h ago', feedbackItems: 15 },
      { time: '8h ago', feedbackItems: 10 },
      { time: '4h ago', feedbackItems: 18 },
      { time: 'now', feedbackItems: 12 },
    ],
    lastUpdated: new Date(),
    hasErrorsLast24h: false,
    totalErrors24h: 0
  }

  return (
    <BaseGauges
      className={className}
      config={feedbackGaugesConfig}
      data={useRealData ? mockData : null} // Use mock data for now
      isLoading={isLoading}
      error={error}
      overrideData={overrideData}
      useRealData={useRealData}
      disableEmergenceAnimation={disableEmergenceAnimation}
      onErrorClick={onErrorClick}
    />
  )
} 