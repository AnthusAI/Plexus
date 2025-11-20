'use client'

import React from 'react'
import { Gauge } from '@/components/gauge'
import { ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, ResponsiveContainer } from 'recharts'
import { cn } from '@/lib/utils'
import { useUnifiedMetrics, UnifiedMetricsData } from '@/hooks/useUnifiedMetrics'
import { Timestamp } from '@/components/ui/timestamp'
import NumberFlowWrapper from '@/components/ui/number-flow'
import { AlertTriangle, ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

// Fallback data for the area chart when loading or no data
const fallbackChartData = [
  { time: '00:00', items: 0, scoreResults: 0 },
  { time: '04:00', items: 0, scoreResults: 0 },
  { time: '08:00', items: 0, scoreResults: 0 },
  { time: '12:00', items: 0, scoreResults: 0 },
  { time: '16:00', items: 0, scoreResults: 0 },
  { time: '20:00', items: 0, scoreResults: 0 },
]

// Helper function to calculate time range based on period and offset
function calculateTimeRange(period: 'hour' | 'day' | 'week', offset: number): { start: Date; end: Date } {
  const now = new Date()
  let end: Date
  let start: Date
  
  if (offset === 0) {
    end = now
  } else {
    // Calculate historical end time
    switch (period) {
      case 'hour':
        end = new Date(now.getTime() + offset * 60 * 60 * 1000)
        break
      case 'day':
        end = new Date(now.getTime() + offset * 24 * 60 * 60 * 1000)
        break
      case 'week':
        end = new Date(now.getTime() + offset * 7 * 24 * 60 * 60 * 1000)
        break
    }
  }
  
  // Calculate start based on period
  switch (period) {
    case 'hour':
      start = new Date(end.getTime() - 60 * 60 * 1000)
      break
    case 'day':
      start = new Date(end.getTime() - 24 * 60 * 60 * 1000)
      break
    case 'week':
      start = new Date(end.getTime() - 7 * 24 * 60 * 60 * 1000)
      break
  }
  
  return { start, end }
}

// Helper function to format time range label
function formatTimeRangeLabel(period: 'hour' | 'day' | 'week', offset: number, start: Date, end: Date): string {
  if (offset === 0) {
    switch (period) {
      case 'hour': return 'Last Hour'
      case 'day': return 'Last 24 Hours'
      case 'week': return 'Last Week'
    }
  }
  
  // Historical format: "Nov 19, 2pm-3pm", "Nov 19", "Nov 11-18"
  const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  
  switch (period) {
    case 'hour':
      return `${monthNames[start.getMonth()]} ${start.getDate()}, ${start.getHours() % 12 || 12}${start.getHours() >= 12 ? 'pm' : 'am'}-${end.getHours() % 12 || 12}${end.getHours() >= 12 ? 'pm' : 'am'}`
    case 'day':
      return `${monthNames[start.getMonth()]} ${start.getDate()}`
    case 'week':
      return `${monthNames[start.getMonth()]} ${start.getDate()}-${end.getDate()}`
  }
}

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
      <div className="bg-background rounded-lg shadow-lg p-3 text-sm">
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
                  <span className="font-medium">{displayName}: </span>
                </div>
                <span className="font-mono font-medium text-foreground">{entry.value}</span>
              </div>
            )
          })}
        </div>
        {bucketStart && bucketEnd && (
          <div className="pt-2 mt-2">
            <div className="text-xs text-muted-foreground space-y-1">
              <div className="flex items-center justify-between">
                <span>From: </span>
                <Timestamp time={bucketStart} variant="relative" showIcon={false} className="text-xs" />
              </div>
              <div className="flex items-center justify-between">
                <span>To: </span>
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
  chartData?: UnifiedMetricsData['chartData']
  // Control whether to use real data or override props
  useRealData?: boolean
  // Disable emergence animation (for drawer usage)
  disableEmergenceAnimation?: boolean
  // Error handling
  hasErrorsLast24h?: boolean
  errorsCount24h?: number
  onErrorClick?: () => void
  // Time navigation props (for Storybook/testing)
  timePeriod?: 'hour' | 'day' | 'week'
  timeOffset?: number
  onTimePeriodChange?: (period: 'hour' | 'day' | 'week') => void
  onTimeOffsetChange?: (offset: number) => void
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
  useRealData = true,
  disableEmergenceAnimation = false,
  hasErrorsLast24h: overrideHasErrors,
  errorsCount24h: overrideErrorsCount,
  onErrorClick,
  timePeriod: controlledTimePeriod,
  timeOffset: controlledTimeOffset,
  onTimePeriodChange,
  onTimeOffsetChange
}: ItemsGaugesProps) {
  // Time navigation state (internal or controlled)
  const [internalTimePeriod, setInternalTimePeriod] = React.useState<'hour' | 'day' | 'week'>('day')
  const [internalTimeOffset, setInternalTimeOffset] = React.useState<number>(0)
  
  // Use controlled props if provided, otherwise use internal state
  const timePeriod = controlledTimePeriod !== undefined ? controlledTimePeriod : internalTimePeriod
  const timeOffset = controlledTimeOffset !== undefined ? controlledTimeOffset : internalTimeOffset
  
  // Calculate time range based on period and offset
  const timeRange = React.useMemo(() => {
    const { start, end } = calculateTimeRange(timePeriod, timeOffset)
    return { start, end, period: timePeriod }
  }, [timePeriod, timeOffset])
  
  // Format the time range label
  const timeRangeLabel = React.useMemo(() => {
    return formatTimeRangeLabel(timePeriod, timeOffset, timeRange.start, timeRange.end)
  }, [timePeriod, timeOffset, timeRange])
  
  // Fetch metrics with custom time range
  const { metrics, isLoading, error } = useUnifiedMetrics(
    useRealData ? { timeRange } : {}
  )
  
  // Navigation handlers
  const handleTimePeriodChange = (newPeriod: 'hour' | 'day' | 'week') => {
    // Always reset to "now" when changing period
    if (onTimePeriodChange) {
      onTimePeriodChange(newPeriod)
    } else {
      setInternalTimePeriod(newPeriod)
    }
    
    // Reset offset to 0 (now) regardless of controlled/uncontrolled
    if (onTimeOffsetChange) {
      onTimeOffsetChange(0)
    } else {
      setInternalTimeOffset(0)
    }
  }
  
  const handleNavigateBack = () => {
    const newOffset = timeOffset - 1
    if (onTimeOffsetChange) {
      onTimeOffsetChange(newOffset)
    } else {
      setInternalTimeOffset(newOffset)
    }
  }
  
  const handleNavigateForward = () => {
    const newOffset = timeOffset + 1
    if (onTimeOffsetChange) {
      onTimeOffsetChange(newOffset)
    } else {
      setInternalTimeOffset(newOffset)
    }
  }
  
  // Removed skeleton loader - component handles its own loading state
  
  // Progressive data availability states
  const hasHourlyData = !!metrics && metrics.itemsPerHour !== undefined && metrics.scoreResultsPerHour !== undefined
  const hasChartData = !!metrics && metrics.chartData && metrics.chartData.length > 0
  const hasFullData = hasHourlyData && hasChartData && !isLoading
  
  // Always show component when using real data (unless there's an error with no data)
  // This prevents flickering and allows progressive disclosure
  const shouldShowComponent = !useRealData || !error || hasHourlyData

  // Determine which data to use - progressive updates for real data
  const scoreResultsPerHour = useRealData ? (metrics?.scoreResultsPerHour ?? undefined) : (overrideScoreResults ?? 0)
  const itemsPerHour = useRealData ? (metrics?.itemsPerHour ?? undefined) : (overrideItems ?? 0)
  const scoreResultsAveragePerHour = useRealData ? (metrics?.scoreResultsAveragePerHour ?? undefined) : (overrideScoreResultsAverage ?? 0)
  const itemsAveragePerHour = useRealData ? (metrics?.itemsAveragePerHour ?? undefined) : (overrideItemsAverage ?? 0)
  const itemsPeakHourly = useRealData ? (metrics?.itemsPeakHourly ?? 50) : (overrideItemsPeak ?? Math.max(...(overrideChartData ?? fallbackChartData).map(point => point.items), 50))
  const scoreResultsPeakHourly = useRealData ? (metrics?.scoreResultsPeakHourly ?? 300) : (overrideScoreResultsPeak ?? Math.max(...(overrideChartData ?? fallbackChartData).map(point => point.scoreResults), 300))
  const itemsTotal24h = useRealData ? (metrics?.itemsTotal24h ?? undefined) : (overrideItemsTotal24h ?? (itemsAveragePerHour ? itemsAveragePerHour * 24 : 0))
  const scoreResultsTotal24h = useRealData ? (metrics?.scoreResultsTotal24h ?? undefined) : (overrideScoreResultsTotal24h ?? (scoreResultsAveragePerHour ? scoreResultsAveragePerHour * 24 : 0))
  const chartData = useRealData ? (metrics?.chartData ?? fallbackChartData) : (overrideChartData ?? fallbackChartData)
  const hasErrorsLast24h = useRealData ? (metrics?.hasErrorsLast24h ?? false) : (overrideHasErrors ?? false)
  const errorsCount24h = useRealData ? (metrics?.totalErrors24h ?? 0) : (overrideErrorsCount ?? 0)
  
  // For chart display: show chart if we have real data or if we're not loading
  // Only show spinner during initial load when we have no real chart data
  const shouldShowChart = !isLoading || hasChartData
  
  // Calculate maximum value across all chart areas for consistent Y scale
  const maxChartValue = React.useMemo(() => {
    if (!chartData || chartData.length === 0) return 100
    
    let max = 0
    chartData.forEach(point => {
      const itemsValue = point.items || 0
      const scoreResultsValue = point.scoreResults || 0
      if (itemsValue > max) max = itemsValue
      if (scoreResultsValue > max) max = scoreResultsValue
    })
    
    // Use a baseline of 50 for items charts
    const baselineMax = 50
    
    // Add some padding (20%) and ensure reasonable minimum
    return Math.max(Math.ceil(max * 1.2), baselineMax)
  }, [chartData])
  
  // For real data usage, show error state if there's an error and no data at all
  if (useRealData && error && !hasHourlyData && !isLoading) {
    return (
      <div className={cn("w-full", className)}>
        <div className="text-center p-8">
          <p className="text-sm text-muted-foreground mb-2">Unable to load metrics</p>
          <p className="text-xs text-muted-foreground">{error}</p>
        </div>
      </div>
    )
  }

  // Removed all animation variants - component now appears normally

  return (
    <>
      {shouldShowComponent && (
        <div className={cn("w-full overflow-visible", className)}>
          <div>
            {/* 
              Complex responsive grid layout - MUST match ItemCards grid breakpoints exactly:
              - grid-cols-2 (base, < 500px): gauges stack vertically, chart below full width  
              - @[500px]:grid-cols-3 (≥ 500px): 3 cols, chart takes 1 remaining column
              - @[700px]:grid-cols-4 (≥ 700px): 4 cols, chart takes 2 remaining columns  
              - @[900px]:grid-cols-5 (≥ 900px): 5 cols, chart takes 3 remaining columns
              - @[1100px]:grid-cols-6 (≥ 1100px): 6 cols, chart takes 4 remaining columns
            */}
            <div className="grid grid-cols-2 @[500px]:grid-cols-3 @[700px]:grid-cols-4 @[900px]:grid-cols-5 @[1100px]:grid-cols-6 gap-3 items-start">
        
        {/* First gauge - Items per Hour */}
        <div className="bg-card rounded-lg h-48 overflow-visible flex items-center justify-center">
          <div className="w-full h-full flex items-center justify-center">
            <Gauge
              value={itemsPerHour}
              beforeValue={itemsAveragePerHour}
              title="Items / hour"
              information={hasHourlyData ? `**Current:** ${itemsPerHour}  
*Current hourly rate (rolling 60-min window)*

**Average:** ${itemsAveragePerHour}  
*24-hour average hourly rate*

**Peak:** ${itemsPeakHourly}  
*Peak hourly rate over last 24 hours*

**Total:** ${itemsTotal24h}  
*Total items over last 24 hours*` : "Loading hourly metrics..."}
              valueUnit=""
              min={0}
              max={itemsPeakHourly}
              showTicks={true}
              decimalPlaces={0}
              showOnlyEssentialTicks={true}  // Show only 0, max, and average ticks
              segments={[
                { start: 0, end: 10, color: 'var(--false)' },
                { start: 10, end: 90, color: 'var(--neutral)' },
                { start: 90, end: 100, color: 'var(--true)' }
              ]}
              backgroundColor="var(--background)"
            />
          </div>
        </div>

        {/* Second gauge - Score Results per Hour */}
        <div className="bg-card rounded-lg h-48 overflow-visible flex items-center justify-center">
          <div className="w-full h-full flex items-center justify-center">
            <Gauge
              value={scoreResultsPerHour}
              beforeValue={scoreResultsAveragePerHour}
              title="Score Results / hour"
              information={hasHourlyData ? `**Current:** ${scoreResultsPerHour}  
*Current hourly rate (rolling 60-min window)*

**Average:** ${scoreResultsAveragePerHour}  
*24-hour average hourly rate*

**Peak:** ${scoreResultsPeakHourly}  
*Peak hourly rate over last 24 hours*

**Total:** ${scoreResultsTotal24h}  
*Total score results over last 24 hours*` : "Loading hourly metrics..."}
              valueUnit=""
              min={0}
              max={scoreResultsPeakHourly}
              showTicks={true}
              decimalPlaces={0}
              showOnlyEssentialTicks={true}  // Show only 0, max, and average ticks
              segments={[
                { start: 0, end: 10, color: 'var(--false)' },
                { start: 10, end: 90, color: 'var(--neutral)' },
                { start: 90, end: 100, color: 'var(--true)' }
              ]}
              backgroundColor="var(--background)"
            />
          </div>
        </div>

        {/* 
          Line Chart - Complex responsive behavior matching ItemCards grid exactly:
          - grid-cols-2 (< 500px): spans full width (col-span-2) on second row
          - @[500px]:grid-cols-3 (≥ 500px): spans 1 remaining column (col-span-1)  
          - @[700px]:grid-cols-4 (≥ 700px): spans 2 remaining columns (col-span-2)
          - @[900px]:grid-cols-5 (≥ 900px): spans 3 remaining columns (col-span-3) 
          - @[1100px]:grid-cols-6 (≥ 1100px): spans 4 remaining columns (col-span-4)
        */}
        <div className="col-span-2 @[500px]:col-span-1 @[700px]:col-span-2 @[900px]:col-span-3 @[1100px]:col-span-4 bg-card rounded-lg p-4 h-48 flex flex-col relative">
          <div className="absolute top-4 left-1/2 transform -translate-x-1/2 z-10 flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              onClick={handleNavigateBack}
              className="h-6 w-6"
              title="Go back in time"
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            
            <Select value={timePeriod} onValueChange={handleTimePeriodChange}>
              <SelectTrigger className="h-6 w-auto border-0 bg-transparent px-2 text-sm font-medium text-muted-foreground hover:text-foreground focus:ring-0">
                <SelectValue>
                  <span className="text-sm font-medium text-muted-foreground">Items, {timeRangeLabel}</span>
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="hour">Last Hour</SelectItem>
                <SelectItem value="day">Last 24 Hours</SelectItem>
                <SelectItem value="week">Last Week</SelectItem>
              </SelectContent>
            </Select>
            
            <Button
              variant="ghost"
              size="icon"
              onClick={handleNavigateForward}
              disabled={timeOffset === 0}
              className="h-6 w-6"
              title="Go forward in time"
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
          <div className="flex flex-col h-full min-w-0">
            {/* Chart area - responsive height based on width - taller when wide */}
            <div className="w-full flex-[4] min-h-0 min-w-0 mb-1 @[700px]:flex-[5] @[700px]:mb-0 mt-6">
              {!shouldShowChart && useRealData ? (
                // Loading state for chart - only show on very first load
                <div className="w-full h-full flex items-center justify-center">
                  <div className="w-8 h-8 border-4 border-muted border-t-primary rounded-full animate-spin"></div>
                </div>
              ) : (
                <div
                  className="w-full h-full"
                  style={{
                    filter: 'drop-shadow(0 0 8px rgba(59, 130, 246, 0.2)) drop-shadow(0 0 8px rgba(168, 85, 247, 0.2))',
                  }}
                >
                  <ChartContainer config={chartConfig} className="w-full h-full">
                    <AreaChart
                      accessibilityLayer
                      data={chartData}
                      margin={{
                        top: 12,
                        right: 8,
                        left: 0,
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
                      <YAxis
                        tickLine={false}
                        axisLine={false}
                        tick={{ fontSize: 9 }}
                        tickMargin={2}
                        width={35}
                        domain={[0, maxChartValue]}
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
                        animationBegin={0}
                        animationDuration={300}
                        isAnimationActive={true}
                      />
                      <Area
                        dataKey="scoreResults"
                        type="step"
                        fill="#a855f7"
                        fillOpacity={0.8}
                        stroke="none"
                        strokeWidth={0}
                        stackId="1"
                        animationBegin={100}
                        animationDuration={300}
                        isAnimationActive={true}
                      />
                    </AreaChart>
                  </ChartContainer>
                </div>
              )}
            </div>
            
            {/* 24-hour totals at the bottom - responsive layout */}
            <div className="flex justify-between items-end text-sm flex-shrink-0 relative">
              {/* Items metric - left-justified with color on the left */}
              <div className="flex items-center gap-2 @[500px]:flex-col @[500px]:gap-1 @[500px]:items-center @[700px]:flex-row @[700px]:gap-2 @[700px]:items-start">
                <div className="flex flex-col items-start">
                  {/* Single-cell layout: dot on text line, two-line labels, left-justified */}
                  <div className="hidden @[500px]:flex @[700px]:hidden flex-col items-start gap-1">
                    <div className="flex items-center gap-1">
                      <div 
                        className="w-3 h-3 rounded-sm" 
                        style={{ 
                          backgroundColor: '#3b82f6',
                          filter: 'drop-shadow(0 0 8px rgba(59, 130, 246, 0.2))'
                        }}
                      />
                      <span className="text-muted-foreground text-xs leading-tight">Items</span>
                    </div>
                    <span className="font-medium text-foreground text-base leading-tight">
                      {itemsTotal24h !== undefined ? (
                        <NumberFlowWrapper 
                          value={itemsTotal24h} 
                          format={{ useGrouping: false }}
                        />
                      ) : null}
                    </span>
                    <span className="text-muted-foreground text-xs leading-tight">per day</span>
                  </div>
                  {/* Default layout: dot beside number, single-line label */}
                  <div className="flex @[500px]:hidden @[700px]:flex items-center gap-1">
                    <div 
                      className="w-3 h-3 rounded-sm" 
                      style={{ 
                        backgroundColor: '#3b82f6',
                        filter: 'drop-shadow(0 0 8px rgba(59, 130, 246, 0.2))'
                      }}
                    />
                    <span className="font-medium text-foreground text-base leading-tight">
                      {itemsTotal24h !== undefined ? (
                        <NumberFlowWrapper 
                          value={itemsTotal24h} 
                          format={{ useGrouping: false }}
                        />
                      ) : null}
                    </span>
                  </div>
                  <span className="text-muted-foreground text-xs leading-tight @[500px]:hidden @[700px]:block">Items / day</span>
                </div>
              </div>
              {/* Center: Error indicator - absolutely centered in the chart card */}
              <div className="absolute left-1/2 bottom-0 transform -translate-x-1/2 mb-1 flex flex-col items-center z-10">
                {useRealData && hasErrorsLast24h && onErrorClick && (
                  <div className="relative">
                    <div 
                      className="absolute inset-0 bg-destructive rounded-md animate-pulse"
                    />
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={onErrorClick}
                      className="h-auto p-1 relative z-10"
                      title="Errors detected in last 24 hours - click to filter"
                    >
                      <div className="flex flex-col items-center gap-1 text-attention">
                        <AlertTriangle className="h-3 w-3" />
                        <span className="text-[10px] leading-tight">{errorsCount24h} Error{errorsCount24h !== 1 ? 's' : ''}</span>
                      </div>
                    </Button>
                  </div>
                )}
              </div>
              {/* Score Results metric - right-justified with color on the right */}
              <div className="flex items-center gap-2 @[500px]:flex-col @[500px]:gap-1 @[500px]:items-end @[700px]:flex-row-reverse @[700px]:gap-2 @[700px]:items-end text-right">
                <div className="flex flex-col items-end">
                  {/* Single-cell layout: dot on text line, two-line labels, right-justified */}
                  <div className="hidden @[500px]:flex @[700px]:hidden flex-col items-end gap-1">
                    <div className="flex items-center gap-1">
                      <span className="text-muted-foreground text-xs leading-tight">Results</span>
                      <div 
                        className="w-3 h-3 rounded-sm" 
                        style={{ 
                          backgroundColor: '#a855f7',
                          filter: 'drop-shadow(0 0 8px rgba(168, 85, 247, 0.2))'
                        }}
                      />
                    </div>
                    <span className="font-medium text-foreground text-base leading-tight">
                      {scoreResultsTotal24h !== undefined ? (
                        <NumberFlowWrapper 
                          value={scoreResultsTotal24h} 
                          format={{ useGrouping: false }}
                        />
                      ) : null}
                    </span>
                    <span className="text-muted-foreground text-xs leading-tight">per day</span>
                  </div>
                  {/* Default layout: dot beside number, single-line label */}
                  <div className="flex @[500px]:hidden @[700px]:flex items-center gap-1">
                    <span className="font-medium text-foreground text-base leading-tight">
                      {scoreResultsTotal24h !== undefined ? (
                        <NumberFlowWrapper 
                          value={scoreResultsTotal24h} 
                          format={{ useGrouping: false }}
                        />
                      ) : null}
                    </span>
                    <div 
                      className="w-3 h-3 rounded-sm" 
                      style={{ 
                        backgroundColor: '#a855f7',
                        filter: 'drop-shadow(0 0 8px rgba(168, 85, 247, 0.2))'
                      }}
                    />
                  </div>
                  <span className="text-muted-foreground text-xs leading-tight @[500px]:hidden @[700px]:block">Score Results / day</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
          </div>
        </div>
      )}
    </>
  )
}