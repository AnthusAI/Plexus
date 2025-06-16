'use client'

import React from 'react'
import { Gauge } from '@/components/gauge'
import { ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, ResponsiveContainer } from 'recharts'
import { cn } from '@/lib/utils'
import { useAllItemsMetrics, UnifiedMetricsData } from '@/hooks/useUnifiedMetrics'
import { Timestamp } from '@/components/ui/timestamp'
import NumberFlowWrapper from '@/components/ui/number-flow'
import { AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/button'

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
  onErrorClick
}: ItemsGaugesProps) {
  const { metrics, isLoading, error } = useAllItemsMetrics()
  
  // Removed skeleton loader - component handles its own loading state
  
  // Progressive data availability states
  const hasHourlyData = !!metrics && metrics.itemsPerHour !== undefined && metrics.scoreResultsPerHour !== undefined
  const hasChartData = !!metrics && metrics.chartData && metrics.chartData.length > 0
  const hasFullData = hasHourlyData && hasChartData && !isLoading
  
  // Always show component when using real data (unless there's an error with no data)
  // This prevents flickering and allows progressive disclosure
  const shouldShowComponent = !useRealData || !error || hasHourlyData

  // Determine which data to use - progressive updates for real data
  const scoreResultsPerHour = useRealData ? (metrics?.scoreResultsPerHour ?? 0) : (overrideScoreResults ?? 0)
  const itemsPerHour = useRealData ? (metrics?.itemsPerHour ?? 0) : (overrideItems ?? 0)
  const scoreResultsAveragePerHour = useRealData ? (metrics?.scoreResultsAveragePerHour ?? 0) : (overrideScoreResultsAverage ?? 0)
  const itemsAveragePerHour = useRealData ? (metrics?.itemsAveragePerHour ?? 0) : (overrideItemsAverage ?? 0)
  const itemsPeakHourly = useRealData ? (metrics?.itemsPeakHourly ?? 50) : (overrideItemsPeak ?? Math.max(...(overrideChartData ?? fallbackChartData).map(point => point.items), 50))
  const scoreResultsPeakHourly = useRealData ? (metrics?.scoreResultsPeakHourly ?? 300) : (overrideScoreResultsPeak ?? Math.max(...(overrideChartData ?? fallbackChartData).map(point => point.scoreResults), 300))
  const itemsTotal24h = useRealData ? (metrics?.itemsTotal24h ?? 0) : (overrideItemsTotal24h ?? itemsAveragePerHour * 24)
  const scoreResultsTotal24h = useRealData ? (metrics?.scoreResultsTotal24h ?? 0) : (overrideScoreResultsTotal24h ?? scoreResultsAveragePerHour * 24)
  const chartData = useRealData ? (metrics?.chartData ?? fallbackChartData) : (overrideChartData ?? fallbackChartData)
  const hasErrorsLast24h = useRealData ? (metrics?.hasErrorsLast24h ?? false) : (overrideHasErrors ?? false)
  const errorsCount24h = useRealData ? (metrics?.totalErrors24h ?? 0) : (overrideErrorsCount ?? 0)
  
  // For chart display: show chart if we have any data (including fallback), only show loading on very first load
  // Since chartData always falls back to fallbackChartData, we should almost always show the chart
  const shouldShowChart = !isLoading || hasChartData || (chartData && chartData.length > 0)
  
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
  
  // Debug error indicator conditions
  console.log('🔧 Error indicator conditions:', {
    useRealData,
    hasErrorsLast24h,
    metricsHasErrors: metrics?.hasErrorsLast24h,
    onErrorClick: !!onErrorClick,
    shouldShow: useRealData && hasErrorsLast24h && onErrorClick
  })
  
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
          <div className="absolute top-4 left-1/2 transform -translate-x-1/2 z-10">
            <h3 className="text-sm font-medium text-muted-foreground">Items, Last 24 Hours</h3>
          </div>
          <div className="flex flex-col h-full min-w-0">
            {/* Chart area - responsive height based on width - taller when wide */}
            <div className="w-full flex-[4] min-h-0 min-w-0 mb-1 @[700px]:flex-[5] @[700px]:mb-0 mt-6">
              {!shouldShowChart && useRealData ? (
                // Loading state for chart - only show on very first load
                <div className="w-full h-full flex items-center justify-center">
                  <div className="text-center">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-2"></div>
                    <p className="text-sm text-muted-foreground">Loading chart data...</p>
                  </div>
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
                      <NumberFlowWrapper 
                        value={hasChartData ? itemsTotal24h : (hasHourlyData ? itemsTotal24h : 0)} 
                        format={{ useGrouping: false }}
                      />
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
                      <NumberFlowWrapper 
                        value={hasChartData ? itemsTotal24h : (hasHourlyData ? itemsTotal24h : 0)} 
                        format={{ useGrouping: false }}
                      />
                    </span>
                  </div>
                  <span className="text-muted-foreground text-xs leading-tight @[500px]:hidden @[700px]:block">Items / day</span>
                </div>
              </div>
              {/* Center: Error indicator or Last updated timestamp - absolutely centered in the chart card */}
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
                {useRealData && !hasErrorsLast24h && metrics?.lastUpdated && (
                  <>
                    <span className="text-[10px] text-muted-foreground leading-tight">Last updated</span>
                    <Timestamp 
                      time={metrics.lastUpdated} 
                      variant="relative" 
                      showIcon={false}
                      className="text-[10px] text-muted-foreground"
                    />
                  </>
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
                      <NumberFlowWrapper 
                        value={hasChartData ? scoreResultsTotal24h : (hasHourlyData ? scoreResultsTotal24h : 0)} 
                        format={{ useGrouping: false }}
                      />
                    </span>
                    <span className="text-muted-foreground text-xs leading-tight">per day</span>
                  </div>
                  {/* Default layout: dot beside number, single-line label */}
                  <div className="flex @[500px]:hidden @[700px]:flex items-center gap-1">
                    <span className="font-medium text-foreground text-base leading-tight">
                      <NumberFlowWrapper 
                        value={hasChartData ? scoreResultsTotal24h : (hasHourlyData ? scoreResultsTotal24h : 0)} 
                        format={{ useGrouping: false }}
                      />
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