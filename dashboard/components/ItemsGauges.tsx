'use client'

import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Gauge } from '@/components/gauge'
import { ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import { AreaChart, Area, XAxis, CartesianGrid, ResponsiveContainer } from 'recharts'
import { cn } from '@/lib/utils'
import { useItemsMetrics } from '@/hooks/useItemsMetrics'
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
  chartData?: Array<{ time: string; items: number; scoreResults: number; bucketStart?: string; bucketEnd?: string }>
  // Control whether to use real data or override props
  useRealData?: boolean
  // Disable emergence animation (for drawer usage)
  disableEmergenceAnimation?: boolean
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
  disableEmergenceAnimation = false
}: ItemsGaugesProps) {
  const { metrics, isLoading, error } = useItemsMetrics()
  // Only consider we have data when we have meaningful hourly metrics (not just partial data)
  const hasData = !!metrics && metrics.itemsPerHour !== undefined && metrics.scoreResultsPerHour !== undefined
  const isInitialLoading = isLoading && !hasData
  const isRefreshing = isLoading && hasData

  // Determine which data to use - only use override values when NOT using real data
  const scoreResultsPerHour = useRealData ? (metrics?.scoreResultsPerHour ?? 0) : (overrideScoreResults ?? 0)
  const itemsPerHour = useRealData ? (metrics?.itemsPerHour ?? 0) : (overrideItems ?? 0)
  const scoreResultsAveragePerHour = useRealData ? (metrics?.scoreResultsAveragePerHour ?? 0) : (overrideScoreResultsAverage ?? 0)
  const itemsAveragePerHour = useRealData ? (metrics?.itemsAveragePerHour ?? 0) : (overrideItemsAverage ?? 0)
  const itemsPeakHourly = useRealData ? (metrics?.itemsPeakHourly ?? 50) : (overrideItemsPeak ?? Math.max(...(overrideChartData ?? fallbackChartData).map(point => point.items), 50))
  const scoreResultsPeakHourly = useRealData ? (metrics?.scoreResultsPeakHourly ?? 300) : (overrideScoreResultsPeak ?? Math.max(...(overrideChartData ?? fallbackChartData).map(point => point.scoreResults), 300))
  const itemsTotal24h = useRealData ? (metrics?.itemsTotal24h ?? 0) : (overrideItemsTotal24h ?? itemsAveragePerHour * 24)
  const scoreResultsTotal24h = useRealData ? (metrics?.scoreResultsTotal24h ?? 0) : (overrideScoreResultsTotal24h ?? scoreResultsAveragePerHour * 24)
  const chartData = useRealData ? (metrics?.chartData ?? fallbackChartData) : (overrideChartData ?? fallbackChartData)
  
  // For real data usage, hide component when no data (progressive disclosure)
  // Show error state if there's an error and no existing data
  if (useRealData) {
    if (error && !hasData) {
      return (
        <div className={cn("w-full", className)}>
          <div className="text-center p-8">
            <p className="text-sm text-muted-foreground mb-2">Unable to load metrics</p>
            <p className="text-xs text-muted-foreground">{error}</p>
          </div>
        </div>
      )
    }
    
    // Return null (hidden) when no data is available yet
    if (!hasData) {
      return null
    }
  }

  // Animation variants for progressive disclosure (faster, 1 second total)
  const containerVariants = {
    hidden: { 
      height: 0,
      opacity: 0,
      scale: 0.95
    },
    visible: { 
      height: 'auto',
      opacity: 1,
      scale: 1,
      transition: {
        height: { duration: 1, ease: 'easeOut' },
        opacity: { duration: 0.6, ease: 'easeOut', delay: 0.1 },
        scale: { duration: 0.6, ease: 'easeOut', delay: 0.1 }
      }
    },
    exit: {
      height: 0,
      opacity: 0,
      scale: 0.95,
      transition: {
        height: { duration: 0.4, ease: 'easeIn' },
        opacity: { duration: 0.3, ease: 'easeIn' },
        scale: { duration: 0.3, ease: 'easeIn' }
      }
    }
  }
  
  const contentVariants = {
    hidden: { y: 20, opacity: 0 },
    visible: { 
      y: 0, 
      opacity: 1,
      transition: {
        duration: 0.4,
        ease: 'easeOut',
        delay: 0.5 // Delay content animation until height animation is well underway
      }
    }
  }
  
  // Instant variants for drawer usage (no emergence animation)
  const instantVariants = {
    visible: { 
      height: 'auto',
      opacity: 1,
      scale: 1,
      y: 0,
      transition: { duration: 0 }
    }
  }

  return (
    <AnimatePresence>
      {(useRealData ? hasData : true) && (
        <motion.div 
          className={cn("w-full overflow-hidden", className)}
          variants={disableEmergenceAnimation ? instantVariants : containerVariants}
          initial={useRealData && !disableEmergenceAnimation ? "hidden" : "visible"}
          animate="visible"
          exit={disableEmergenceAnimation ? undefined : "exit"}
        >
          <motion.div 
            variants={disableEmergenceAnimation ? instantVariants : contentVariants}
            initial={useRealData && !disableEmergenceAnimation ? "hidden" : "visible"}
            animate="visible"
          >
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
        <div className="bg-card rounded-lg p-4 h-48">
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

        {/* Second gauge - Score Results per Hour */}
        <div className="bg-card rounded-lg p-4 h-48">
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

        {/* 
          Line Chart - Complex responsive behavior matching ItemCards grid exactly:
          - grid-cols-2 (< 500px): spans full width (col-span-2) on second row
          - @[500px]:grid-cols-3 (≥ 500px): spans 1 remaining column (col-span-1)  
          - @[700px]:grid-cols-4 (≥ 700px): spans 2 remaining columns (col-span-2)
          - @[900px]:grid-cols-5 (≥ 900px): spans 3 remaining columns (col-span-3) 
          - @[1100px]:grid-cols-6 (≥ 1100px): spans 4 remaining columns (col-span-4)
        */}
        <div className="col-span-2 @[500px]:col-span-1 @[700px]:col-span-2 @[900px]:col-span-3 @[1100px]:col-span-4 bg-card rounded-lg p-4 h-48 flex flex-col">
          <div className="flex flex-col h-full min-w-0">
            {/* Chart area - responsive height based on width - taller when wide */}
            <div className="w-full flex-[3] min-h-0 min-w-0 mb-1 @[700px]:flex-[4] @[700px]:mb-0">
              <ChartContainer config={chartConfig} className="w-full h-full">
                <AreaChart
                  accessibilityLayer
                  data={chartData}
                  margin={{
                    top: 12,
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
            
            {/* 24-hour totals at the bottom - responsive layout */}
            <div className="flex justify-between items-end text-sm flex-shrink-0 relative">
              {/* Items metric */}
              <div className="flex items-center gap-2 @[500px]:flex-col @[500px]:gap-1 @[500px]:items-center @[700px]:flex-row @[700px]:gap-2 @[700px]:items-center">
                <div className="flex flex-col items-center">
                  <span className="font-mono font-medium text-foreground text-base leading-tight">{itemsTotal24h.toLocaleString()}</span>
                  <span className="text-muted-foreground text-xs leading-tight">Items/24h</span>
                  <div 
                    className="w-3 h-3 rounded-sm mt-1 hidden @[500px]:block @[700px]:hidden" 
                    style={{ backgroundColor: '#3b82f6' }}
                  />
                </div>
                <div 
                  className="w-3 h-3 rounded-sm flex-shrink-0 block @[500px]:hidden @[700px]:block" 
                  style={{ backgroundColor: '#3b82f6' }}
                />
              </div>
              
              {/* Last updated timestamp - centered */}
              {useRealData && metrics?.lastUpdated && (
                <div className="absolute left-1/2 transform -translate-x-1/2 flex flex-col items-center">
                  <span className="text-[10px] text-muted-foreground leading-tight">Last updated</span>
                  <Timestamp 
                    time={metrics.lastUpdated} 
                    variant="relative" 
                    showIcon={false}
                    className="text-[10px] text-muted-foreground"
                  />
                </div>
              )}
              
              {/* Score Results metric */}
              <div className="flex items-center gap-2 @[500px]:flex-col @[500px]:gap-1 @[500px]:items-center @[700px]:flex-row @[700px]:gap-2 @[700px]:items-center">
                <div className="flex flex-col items-center">
                  <span className="font-mono font-medium text-foreground text-base leading-tight">{scoreResultsTotal24h.toLocaleString()}</span>
                  <span className="text-muted-foreground text-xs leading-tight">Results/24h</span>
                  <div 
                    className="w-3 h-3 rounded-sm mt-1 hidden @[500px]:block @[700px]:hidden" 
                    style={{ backgroundColor: '#a855f7' }}
                  />
                </div>
                <div 
                  className="w-3 h-3 rounded-sm flex-shrink-0 block @[500px]:hidden @[700px]:block" 
                  style={{ backgroundColor: '#a855f7' }}
                />
              </div>
            </div>
          </div>
        </div>
      </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}