'use client'

import React from 'react'
import { Gauge } from '@/components/gauge'
import { ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import { AreaChart, Area, XAxis, CartesianGrid, ResponsiveContainer } from 'recharts'
import { cn } from '@/lib/utils'
import { useItemsMetrics } from '@/hooks/useItemsMetrics'
import { Loader2 } from 'lucide-react'
import { Timestamp } from '@/components/ui/timestamp'

// Fallback data for the area chart when loading or no data
const fallbackChartData = [
  { time: '00:00', items: 0, scoreResults: 0 },
  { time: '04:00', items: 0, scoreResults: 0 },
  { time: '08:00', items: 0, scoreResults: 0 },
  { time: '12:00', items: 0, scoreResults: 0 },
  { time: '16:00', items: 0, scoreResults: 0 },
  { time: '20:00', items: 0, scoreResults: 0 },
]

const chartConfig = {
  items: {
    label: 'Items',
    color: 'hsl(var(--primary))',
  },
  scoreResults: {
    label: 'Score Results', 
    color: 'hsl(var(--secondary))',
  },
}

// Helper function to calculate percentage for debugging
const toPercentage = (value: number, max: number): number => {
  if (max === 0) return 0
  return Math.round((value / max) * 100)
}

// Custom tooltip component for the chart
const CustomChartTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    // Get the bucket times from the payload data
    const dataPoint = payload[0]?.payload
    const bucketStart = dataPoint?.bucketStart ? new Date(dataPoint.bucketStart) : null
    const bucketEnd = dataPoint?.bucketEnd ? new Date(dataPoint.bucketEnd) : null
    
    return (
      <div className="bg-background border rounded-lg shadow-lg p-3 text-sm">
        <div className="space-y-2">
          {payload.map((entry: any, index: number) => {
            // Use proper labels from chartConfig
            const displayName = chartConfig[entry.dataKey as keyof typeof chartConfig]?.label || entry.name
            return (
              <div key={index} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div 
                    className="w-3 h-3 rounded-sm" 
                    style={{ backgroundColor: entry.color }}
                  />
                  <span className="font-medium">{displayName}:</span>
                </div>
                <span className="font-mono font-medium text-foreground">{entry.value}</span>
              </div>
            )
          })}
        </div>
        {bucketStart && bucketEnd && (
          <div className="border-t pt-2 mt-2">
            <div className="text-xs text-muted-foreground space-y-1">
              <div className="flex items-center justify-between">
                <span>From:</span>
                <Timestamp time={bucketStart} variant="relative" showIcon={false} className="text-xs" />
              </div>
              <div className="flex items-center justify-between">
                <span>To:</span>
                <Timestamp time={bucketEnd} variant="relative" showIcon={false} className="text-xs" />
              </div>
            </div>
          </div>
        )}
      </div>
    )
  }
  return null
}

interface ItemsGaugesProps {
  className?: string
  // Override props for Storybook/testing
  scoreResultsPerHour?: number
  itemsPerHour?: number
  scoreResultsAveragePerHour?: number
  itemsAveragePerHour?: number
  itemsPeakHourly?: number
  scoreResultsPeakHourly?: number
  itemsTotal24h?: number
  scoreResultsTotal24h?: number
  chartData?: Array<{ time: string; items: number; scoreResults: number; bucketStart?: string; bucketEnd?: string }>
  // Control whether to use real data or override props
  useRealData?: boolean
}

export function ItemsGauges({ 
  className, 
  scoreResultsPerHour: overrideScoreResults, 
  itemsPerHour: overrideItems,
  scoreResultsAveragePerHour: overrideScoreResultsAverage,
  itemsAveragePerHour: overrideItemsAverage,
  itemsPeakHourly: overrideItemsPeak,
  scoreResultsPeakHourly: overrideScoreResultsPeak,
  itemsTotal24h: overrideItemsTotal24h,
  scoreResultsTotal24h: overrideScoreResultsTotal24h,
  chartData: overrideChartData,
  useRealData = true 
}: ItemsGaugesProps) {
  const { metrics, isLoading, error } = useItemsMetrics()

  // Determine which data to use
  const scoreResultsPerHour = useRealData && metrics ? metrics.scoreResultsPerHour : (overrideScoreResults ?? 0)
  const itemsPerHour = useRealData && metrics ? metrics.itemsPerHour : (overrideItems ?? 0)
  const scoreResultsAveragePerHour = useRealData && metrics ? metrics.scoreResultsAveragePerHour : (overrideScoreResultsAverage ?? 0)
  const itemsAveragePerHour = useRealData && metrics ? metrics.itemsAveragePerHour : (overrideItemsAverage ?? 0)
  const itemsPeakHourly = useRealData && metrics ? metrics.itemsPeakHourly : (overrideItemsPeak ?? Math.max(...(overrideChartData ?? fallbackChartData).map(point => point.items), 50))
  const scoreResultsPeakHourly = useRealData && metrics ? metrics.scoreResultsPeakHourly : (overrideScoreResultsPeak ?? Math.max(...(overrideChartData ?? fallbackChartData).map(point => point.scoreResults), 300))
  const itemsTotal24h = useRealData && metrics ? metrics.itemsTotal24h : (overrideItemsTotal24h ?? itemsAveragePerHour * 24)
  const scoreResultsTotal24h = useRealData && metrics ? metrics.scoreResultsTotal24h : (overrideScoreResultsTotal24h ?? scoreResultsAveragePerHour * 24)
  const chartData = useRealData && metrics ? metrics.chartData : (overrideChartData ?? fallbackChartData)
  
  
  // Debug chart data in component
  console.log('📊 ItemsGauges: Chart data received:', { 
    useRealData, 
    hasMetrics: !!metrics, 
    gaugeValues: {
      scoreResultsPerHour,
      scoreResultsAveragePerHour,
      itemsPerHour,
      itemsAveragePerHour
    },
    totals: {
      scoreResultsTotal24h,
      itemsTotal24h
    },
    dynamicScaling: {
      itemsPeakHourly,
      scoreResultsPeakHourly,
      itemsPercentage: toPercentage(itemsPerHour, itemsPeakHourly),
      scoreResultsPercentage: toPercentage(scoreResultsPerHour, scoreResultsPeakHourly),
      itemsAveragePercentage: toPercentage(itemsAveragePerHour, itemsPeakHourly),
      scoreResultsAveragePercentage: toPercentage(scoreResultsAveragePerHour, scoreResultsPeakHourly)
    },
    chartData,
    chartDataLength: chartData.length,
    hasNonZeroValues: chartData.some(point => point.items > 0 || point.scoreResults > 0)
  })
  // Show loading or error state
  if (useRealData && isLoading) {
    return (
      <div className={cn("w-full", className)}>
        <div className="grid grid-cols-2 @[500px]:grid-cols-3 @[700px]:grid-cols-4 @[900px]:grid-cols-5 @[1100px]:grid-cols-6 gap-3 items-start">
          {/* Loading skeletons */}
          {[1, 2, 3].map((i) => (
            <div key={i} className={`bg-card rounded-lg p-4 border h-48 flex items-center justify-center ${i === 3 ? 'col-span-2 @[500px]:col-span-1 @[700px]:col-span-2 @[900px]:col-span-3 @[1100px]:col-span-4' : ''}`}>
              <div className="flex flex-col items-center space-y-2">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                <span className="text-sm text-muted-foreground">Loading...</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (useRealData && error) {
    return (
      <div className={cn("w-full", className)}>
        <div className="grid grid-cols-2 @[500px]:grid-cols-3 @[700px]:grid-cols-4 @[900px]:grid-cols-5 @[1100px]:grid-cols-6 gap-3 items-start">
          {/* Error state */}
          <div className="col-span-2 @[500px]:col-span-3 @[700px]:col-span-4 @[900px]:col-span-5 @[1100px]:col-span-6 bg-card rounded-lg p-4 border h-48 flex items-center justify-center">
            <div className="text-center">
              <p className="text-sm text-muted-foreground mb-2">Failed to load metrics</p>
              <p className="text-xs text-muted-foreground">{error}</p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className={cn("w-full", className)}>
      {/* 
        Complex responsive grid layout - MUST match ItemCards grid breakpoints exactly:
        - grid-cols-2 (base, < 500px): gauges stack vertically, chart below full width  
        - @[500px]:grid-cols-3 (≥ 500px): 3 cols, chart takes 1 remaining column
        - @[700px]:grid-cols-4 (≥ 700px): 4 cols, chart takes 2 remaining columns  
        - @[900px]:grid-cols-5 (≥ 900px): 5 cols, chart takes 3 remaining columns
        - @[1100px]:grid-cols-6 (≥ 1100px): 6 cols, chart takes 4 remaining columns
      */}
      <div className="grid grid-cols-2 @[500px]:grid-cols-3 @[700px]:grid-cols-4 @[900px]:grid-cols-5 @[1100px]:grid-cols-6 gap-3 items-start">
        
        {/* First gauge - Score Results per Hour */}
        <div className="bg-card rounded-lg p-4 border h-48">
          <Gauge
            value={scoreResultsPerHour}
            beforeValue={scoreResultsAveragePerHour}
            title="Score Results/Hour"
            information={`Current: ${scoreResultsPerHour}
Current hourly rate (last 60 minutes)

Average: ${scoreResultsAveragePerHour}
24-hour average hourly rate

Peak: ${scoreResultsPeakHourly}
Peak hourly rate over last 24 hours

Total: ${scoreResultsTotal24h}
Total score results over last 24 hours`}
            valueUnit=""
            min={0}
            max={scoreResultsPeakHourly}
            showTicks={true}
            decimalPlaces={0}
            tickSpacingThreshold={85}  // Large threshold to only show min and max ticks
            segments={[
              { start: 0, end: 10, color: 'var(--false)' },
              { start: 10, end: 90, color: 'var(--neutral)' },
              { start: 90, end: 100, color: 'var(--true)' }
            ]}
          />
        </div>

        {/* Second gauge - Items per Hour */}
        <div className="bg-card rounded-lg p-4 border h-48">
          <Gauge
            value={itemsPerHour}
            beforeValue={itemsAveragePerHour}
            title="Items/Hour"
            information={`Current: ${itemsPerHour}
Current hourly rate (last 60 minutes)

Average: ${itemsAveragePerHour}
24-hour average hourly rate

Peak: ${itemsPeakHourly}
Peak hourly rate over last 24 hours

Total: ${itemsTotal24h}
Total items over last 24 hours`}
            valueUnit=""
            min={0}
            max={itemsPeakHourly}
            showTicks={true}
            decimalPlaces={0}
            tickSpacingThreshold={85}  // Large threshold to only show min and max ticks
            segments={[
              { start: 0, end: 10, color: 'var(--false)' },
              { start: 10, end: 90, color: 'var(--neutral)' },
              { start: 90, end: 100, color: 'var(--true)' }
            ]}
          />
        </div>

        {/* 
          Line Chart - Complex responsive behavior matching ItemCards grid exactly:
          - grid-cols-2 (< 500px): spans full width (col-span-2) on second row
          - @[500px]:grid-cols-3 (≥ 500px): spans 1 remaining column (col-span-1)  
          - @[700px]:grid-cols-4 (≥ 700px): spans 2 remaining columns (col-span-2)
          - @[900px]:grid-cols-5 (≥ 900px): spans 3 remaining columns (col-span-3) 
          - @[1100px]:grid-cols-6 (≥ 1100px): spans 4 remaining columns (col-span-4)
        */}
        <div className="col-span-2 @[500px]:col-span-1 @[700px]:col-span-2 @[900px]:col-span-3 @[1100px]:col-span-4 bg-card rounded-lg p-4 border h-48 flex flex-col">
          <div className="flex flex-col h-full min-w-0">
            <h3 className="text-sm font-medium text-foreground truncate mb-2 flex-shrink-0">Activity Over Time</h3>
            <div className="w-full flex-1 min-h-0 min-w-0">
              <ChartContainer config={chartConfig} className="w-full h-full">
                <AreaChart
                  accessibilityLayer
                  data={chartData}
                  margin={{
                    top: 8,
                    right: 8,
                    left: 20,
                    bottom: 8,
                  }}
                >
                  <CartesianGrid vertical={false} strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis
                    dataKey="time"
                    tickLine={false}
                    axisLine={false}
                    tickMargin={3}
                    tick={{ fontSize: 9 }}
                    interval={0}
                    tickFormatter={(value, index) => {
                      const totalPoints = chartData.length
                      if (index === 0) return "24h ago"
                      if (index === totalPoints - 1) return "now"
                      // Show middle label only if chart is wide enough (2+ grid cells)
                      // We can approximate this by checking if we have enough data points
                      if (totalPoints >= 12 && index === Math.floor(totalPoints / 2)) return "12h ago"
                      return "" // Hide other ticks
                    }}
                  />
                  <ChartTooltip
                    cursor={false}
                    content={<CustomChartTooltip />}
                  />
                  <Area
                    dataKey="items"
                    type="step"
                    fill="#3b82f6"
                    fillOpacity={0.8}
                    stroke="none"
                    strokeWidth={0}
                    stackId="1"
                  />
                  <Area
                    dataKey="scoreResults"
                    type="step"
                    fill="#a855f7"
                    fillOpacity={0.8}
                    stroke="none"
                    strokeWidth={0}
                    stackId="1"
                  />
                </AreaChart>
              </ChartContainer>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}