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
      title: 'Feedback Items / day',
      valueKey: 'feedbackItemsPerDay',
      averageKey: 'feedbackItemsAveragePerDay',
      peakKey: 'feedbackItemsPeakDaily',
      totalKey: 'feedbackItemsTotal7d',
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
  const feedbackWindow = React.useMemo(() => {
    const end = new Date()
    const start = new Date(end.getTime() - 7 * 24 * 60 * 60 * 1000)
    return {
      start,
      end,
      period: 'week' as const,
    }
  }, [])

  // Use real feedback metrics
  const { 
    metrics: metricsData, 
    isLoading, 
    error 
  } = useFeedbackMetrics({
    timeRange: feedbackWindow,
  })

  const dailyRollups = React.useMemo(() => {
    const chartPoints = metricsData?.chartData || []
    if (chartPoints.length === 0) {
      return {
        total7d: 0,
        averagePerDay: 0,
        peakDaily: 0,
      }
    }

    const dailyTotals = new Map<string, number>()
    for (const point of chartPoints) {
      const bucketStart = point.bucketStart ? new Date(point.bucketStart) : null
      if (!bucketStart || Number.isNaN(bucketStart.getTime())) continue

      const dayKey = bucketStart.toLocaleDateString('en-CA')
      dailyTotals.set(dayKey, (dailyTotals.get(dayKey) || 0) + (point.items || 0))
    }

    const totals = Array.from(dailyTotals.values())
    const total7d = totals.reduce((sum, value) => sum + value, 0)
    const averagePerDay = totals.length > 0 ? Math.round(total7d / totals.length) : 0
    const peakDaily = totals.length > 0 ? Math.max(...totals) : 0

    return {
      total7d,
      averagePerDay,
      peakDaily,
    }
  }, [metricsData?.chartData])

  // Transform metrics data to BaseGaugesData format
  // For feedback metrics, we use the items data which contains feedbackItems counts
  const data: BaseGaugesData | null = metricsData ? {
    feedbackItemsPerDay: metricsData.itemsTotal24h || 0,
    feedbackItemsAveragePerDay: dailyRollups.averagePerDay || 0,
    feedbackItemsPeakDaily: dailyRollups.peakDaily || Math.max(metricsData.itemsTotal24h || 0, 10),
    feedbackItemsTotal7d: dailyRollups.total7d || 0,
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
      title="Feedback Items, Last 7 Days"
      overrideData={overrideData}
      useRealData={useRealData}
      disableEmergenceAnimation={disableEmergenceAnimation}
      onErrorClick={onErrorClick}
    />
  )
} 
