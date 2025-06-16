'use client'

import React from 'react'
import { Gauge } from '@/components/gauge'
import { ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, ResponsiveContainer } from 'recharts'
import { cn } from '@/lib/utils'
import { Timestamp } from '@/components/ui/timestamp'
import NumberFlowWrapper from '@/components/ui/number-flow'
import { AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/button'

// Fallback data for the area chart when loading or no data
const fallbackChartData = [
  { time: '00:00', primary: 0, secondary: 0 },
  { time: '04:00', primary: 0, secondary: 0 },
  { time: '08:00', primary: 0, secondary: 0 },
  { time: '12:00', primary: 0, secondary: 0 },
  { time: '16:00', primary: 0, secondary: 0 },
  { time: '20:00', primary: 0, secondary: 0 },
]

// Configuration for individual gauges
export interface GaugeConfig {
  key: string
  title: string
  valueKey: string // Key in the metrics data for current value
  averageKey: string // Key in the metrics data for average value
  peakKey: string // Key in the metrics data for peak value
  totalKey: string // Key in the metrics data for total value
  color: string // CSS color variable
  unit?: string
  decimalPlaces?: number
  segments?: Array<{ start: number; end: number; color: string }>
  // Optional column span configuration for responsive layouts
  colSpan?: {
    base?: number
    sm?: number
    md?: number
    lg?: number
    xl?: number
  }
}

// Configuration for chart areas
export interface ChartAreaConfig {
  dataKey: string
  label: string
  color: string
  fillOpacity?: number
}

// Main configuration for the entire component
export interface BaseGaugesConfig {
  gauges: GaugeConfig[]
  chartAreas: ChartAreaConfig[]
  chartConfig: Record<string, { label: string; color: string }>
  // Layout configuration
  layout?: 'grid' | 'flex' // Default: 'grid'
  // Responsive grid configuration (only used when layout is 'grid')
  gridCols?: {
    base: number // < 500px
    sm: number   // >= 500px
    md: number   // >= 700px
    lg: number   // >= 900px
    xl: number   // >= 1100px
  }
  // Chart span configuration (only used when layout is 'grid')
  chartSpan?: {
    base: number
    sm: number
    md: number
    lg: number
    xl: number
  }
  // Responsive gauge widths for flex layout (only used when layout is 'flex')
  gaugeWidths?: {
    base: string // < 500px
    sm: string   // >= 500px
    md: string   // >= 700px
    lg: string   // >= 900px
    xl: string   // >= 1100px
  }
}

// Data structure that components must provide
export interface BaseGaugesData {
  [key: string]: number | string | Array<any> | Date | boolean | undefined
  chartData?: Array<{ time: string; [key: string]: any }>
  lastUpdated?: Date
  hasErrorsLast24h?: boolean
  totalErrors24h?: number
}

// Helper function to render a value that might be a number or string (like "?")
const renderValue = (value: number | string | boolean | Array<any> | Date | undefined, format?: any) => {
  if (typeof value === 'string') {
    return value
  }
  if (typeof value === 'number') {
    return (
      <NumberFlowWrapper 
        value={value} 
        format={format}
      />
    )
  }
  // For other types, return 0
  return (
    <NumberFlowWrapper 
      value={0} 
      format={format}
    />
  )
}

// Custom tooltip component for the chart
const CustomChartTooltip = ({ active, payload, label, chartConfig }: any) => {
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
            const displayName = chartConfig[entry.dataKey]?.label || entry.name
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

interface BaseGaugesProps {
  className?: string
  config: BaseGaugesConfig
  data: BaseGaugesData | null
  isLoading: boolean
  error: string | null
  // Override props for Storybook/testing
  overrideData?: Partial<BaseGaugesData>
  // Control whether to use real data or override props
  useRealData?: boolean
  // Disable emergence animation (for drawer usage)
  disableEmergenceAnimation?: boolean
  // Error handling
  onErrorClick?: () => void
}

export function BaseGauges({ 
  className, 
  config,
  data,
  isLoading,
  error,
  overrideData,
  useRealData = true,
  disableEmergenceAnimation = false,
  onErrorClick
}: BaseGaugesProps) {
  
  // Progressive data availability states
  const hasGaugeData = !!data && config.gauges.every(gauge => 
    data[gauge.valueKey] !== undefined
  )
  const hasChartData = !!data && data.chartData && data.chartData.length > 0
  const hasFullData = hasGaugeData && hasChartData && !isLoading
  
  // Always show component when using real data (unless there's an error with no data)
  const shouldShowComponent = !useRealData || !error || hasGaugeData

  // Determine which data to use - progressive updates for real data
  const effectiveData = useRealData ? data : { ...data, ...overrideData }
  const chartData = effectiveData?.chartData ?? fallbackChartData
  const hasErrorsLast24h = effectiveData?.hasErrorsLast24h ?? false
  const errorsCount24h = effectiveData?.totalErrors24h ?? 0
  
  // Calculate maximum value across all chart areas for consistent Y scale
  const maxChartValue = React.useMemo(() => {
    if (!chartData || chartData.length === 0) return 100
    
    let max = 0
    chartData.forEach(point => {
      config.chartAreas.forEach(area => {
        const value = point[area.dataKey] || 0
        if (value > max) max = value
      })
    })
    
    // For score results, use a higher baseline to ensure both prediction and evaluation charts have similar scales
    // This helps when one chart has much lower values than the other
    const baselineMax = config.chartAreas.some(area => area.label.toLowerCase().includes('score')) ? 200 : 50
    
    // Add some padding (20%) and ensure reasonable minimum
    return Math.max(Math.ceil(max * 1.2), baselineMax)
  }, [chartData, config.chartAreas])
  
  // For real data usage, show error state only if there's a persistent error with no data after loading
  // This prevents flickering during the loading process
  if (useRealData && error && !hasGaugeData && !isLoading && !data) {
    return (
      <div className={cn("w-full", className)}>
        <div className="text-center p-8">
          <p className="text-sm text-muted-foreground mb-2">Unable to load metrics</p>
          <p className="text-xs text-muted-foreground">{error}</p>
        </div>
      </div>
    )
  }

  // Removed animation variants - component handles its own loading state

  // Determine layout type
  const isFlexLayout = config.layout === 'flex'
  
  // Generate responsive grid classes (only for grid layout)
  const gridClasses = (!isFlexLayout && config.gridCols) ? [
    `grid-cols-${config.gridCols.base}`,
    `@[500px]:grid-cols-${config.gridCols.sm}`,
    `@[700px]:grid-cols-${config.gridCols.md}`,
    `@[900px]:grid-cols-${config.gridCols.lg}`,
    `@[1100px]:grid-cols-${config.gridCols.xl}`
  ].join(' ') : ''

  // Generate chart span classes (only for grid layout)
  const chartSpanClasses = (!isFlexLayout && config.chartSpan) ? [
    `col-span-${config.chartSpan.base}`,
    `@[500px]:col-span-${config.chartSpan.sm}`,
    `@[700px]:col-span-${config.chartSpan.md}`,
    `@[900px]:col-span-${config.chartSpan.lg}`,
    `@[1100px]:col-span-${config.chartSpan.xl}`
  ].join(' ') : ''

  // Generate responsive gauge width styles for flex layout
  const gaugeWidthStyles = isFlexLayout && config.gaugeWidths ? {
    '--gauge-width-base': config.gaugeWidths.base,
    '--gauge-width-sm': config.gaugeWidths.sm,
    '--gauge-width-md': config.gaugeWidths.md,
    '--gauge-width-lg': config.gaugeWidths.lg,
    '--gauge-width-xl': config.gaugeWidths.xl,
  } as React.CSSProperties : {}

  return (
    <>
      {/* Responsive gauge width styles for flex layout */}
      {isFlexLayout && config.gaugeWidths && (
        <style>{`
          .responsive-gauge-width {
            width: ${config.gaugeWidths.base};
          }
          @container (min-width: 500px) {
            .responsive-gauge-width {
              width: ${config.gaugeWidths.sm};
            }
          }
          @container (min-width: 700px) {
            .responsive-gauge-width {
              width: ${config.gaugeWidths.md};
            }
          }
          @container (min-width: 900px) {
            .responsive-gauge-width {
              width: ${config.gaugeWidths.lg};
            }
          }
          @container (min-width: 1100px) {
            .responsive-gauge-width {
              width: ${config.gaugeWidths.xl};
            }
          }
        `}</style>
      )}
      
      {shouldShowComponent && (
        <div 
          className={cn("w-full overflow-visible", className)}
          style={gaugeWidthStyles}
        >
          <div>
            {isFlexLayout ? (
              // Flex layout: gauge fixed width, chart greedy
              <div className="@container flex gap-3 items-start">
                {/* Render single gauge with fixed width */}
                {config.gauges.map((gaugeConfig) => {
                  const value = effectiveData?.[gaugeConfig.valueKey] as number ?? 0
                  const average = effectiveData?.[gaugeConfig.averageKey] as number ?? 0
                  const peak = effectiveData?.[gaugeConfig.peakKey] as number ?? 50
                  const total = effectiveData?.[gaugeConfig.totalKey] as number ?? 0

                  return (
                    <div 
                      key={gaugeConfig.key} 
                      className="bg-card rounded-lg h-48 overflow-visible flex items-center justify-center flex-shrink-0 responsive-gauge-width"
                    >
                      <div className="w-full h-full flex items-center justify-center">
                        <Gauge
                          value={value}
                          beforeValue={average}
                          title={gaugeConfig.title}
                          information={hasGaugeData ? `**Current:** ${value}  
*Current hourly rate (rolling 60-min window)*

**Average:** ${average}  
*24-hour average hourly rate*

**Peak:** ${peak}  
*Peak hourly rate over last 24 hours*

**Total:** ${total}  
*Total over last 24 hours*` : "Loading metrics..."}
                          valueUnit={gaugeConfig.unit ?? ""}
                          min={0}
                          max={peak}
                          showTicks={true}
                          decimalPlaces={gaugeConfig.decimalPlaces ?? 0}
                          showOnlyEssentialTicks={true}
                          segments={gaugeConfig.segments ?? [
                            { start: 0, end: 10, color: 'var(--false)' },
                            { start: 10, end: 90, color: 'var(--neutral)' },
                            { start: 90, end: 100, color: 'var(--true)' }
                          ]}
                          backgroundColor="var(--background)"
                        />
                      </div>
                    </div>
                  )
                })}

                {/* Chart component - greedy */}
                <div className="bg-card rounded-lg p-4 h-48 flex flex-col flex-grow min-w-0">
                  <div className="flex flex-col h-full min-w-0">
                    <div className="w-full flex-[3] min-h-0 min-w-0 mb-1 @[700px]:flex-[4] @[700px]:mb-0">
                      {!hasChartData && useRealData ? (
                        // Loading state for chart
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
                          <ChartContainer config={config.chartConfig} className="w-full h-full">
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
                                  if (totalPoints >= 12 && index === Math.floor(totalPoints / 2)) return "12h ago"
                                  return ""
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
                                content={<CustomChartTooltip chartConfig={config.chartConfig} />}
                              />
                              {config.chartAreas.map((area, index) => (
                                <Area
                                  key={area.dataKey}
                                  dataKey={area.dataKey}
                                  type="step"
                                  fill={area.color}
                                  fillOpacity={area.fillOpacity ?? 0.8}
                                  stroke="none"
                                  strokeWidth={0}
                                  stackId="1"
                                  animationBegin={0}
                                  animationDuration={300}
                                  isAnimationActive={true}
                                />
                              ))}
                            </AreaChart>
                          </ChartContainer>
                        </div>
                      )}
                    </div>

                    {/* Error indicator */}
                    {useRealData && hasErrorsLast24h && onErrorClick && (
                      <div className="flex-shrink-0 pt-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={onErrorClick}
                          className="h-6 px-2 text-xs text-destructive hover:text-destructive hover:bg-destructive/10 gap-1"
                        >
                          <AlertTriangle className="h-3 w-3" />
                          {errorsCount24h} errors (24h)
                        </Button>
                      </div>
                    )}
                    
                    {/* 24-hour totals at the bottom - responsive layout */}
                    <div className="flex justify-between items-end text-sm flex-shrink-0 relative">
                      {/* First metric - left-justified with color on the left */}
                      {config.gauges.length > 0 && (
                        <div className="flex items-center gap-2 @[500px]:flex-col @[500px]:gap-1 @[500px]:items-center @[700px]:flex-row @[700px]:gap-2 @[700px]:items-start">
                          <div className="flex flex-col items-start">
                            {/* Single-cell layout: dot on text line, two-line labels, left-justified */}
                            <div className="hidden @[500px]:flex @[700px]:hidden flex-col items-start gap-1">
                              <div className="flex items-center gap-1">
                                <div 
                                  className="w-3 h-3 rounded-sm" 
                                  style={{ 
                                    backgroundColor: config.chartAreas[0]?.color || '#3b82f6',
                                    filter: `drop-shadow(0 0 8px ${config.chartAreas[0]?.color || '#3b82f6'}20)`
                                  }}
                                />
                                <span className="text-muted-foreground text-xs leading-tight">{config.chartAreas[0]?.label || 'Items'}</span>
                              </div>
                              <span className="font-medium text-foreground text-base leading-tight">
                                {renderValue(effectiveData?.[config.gauges[0].totalKey], { useGrouping: false })}
                              </span>
                              <span className="text-muted-foreground text-xs leading-tight">per day</span>
                            </div>
                            {/* Default layout: dot beside number, single-line label */}
                            <div className="flex @[500px]:hidden @[700px]:flex items-center gap-1">
                              <div 
                                className="w-3 h-3 rounded-sm" 
                                style={{ 
                                  backgroundColor: config.chartAreas[0]?.color || '#3b82f6',
                                  filter: `drop-shadow(0 0 8px ${config.chartAreas[0]?.color || '#3b82f6'}20)`
                                }}
                              />
                              <span className="font-medium text-foreground text-base leading-tight">
                                {renderValue(effectiveData?.[config.gauges[0].totalKey], { useGrouping: false })}
                              </span>
                            </div>
                            <span className="text-muted-foreground text-xs leading-tight @[500px]:hidden @[700px]:block">{config.chartAreas[0]?.label || 'Items'} / day</span>
                          </div>
                        </div>
                      )}
                      
                      {/* Center: Last updated timestamp - absolutely centered in the chart card */}
                      <div className="absolute left-1/2 bottom-0 transform -translate-x-1/2 mb-1 flex flex-col items-center z-10">
                        {useRealData && effectiveData?.lastUpdated && (
                          <>
                            <span className="text-[10px] text-muted-foreground leading-tight">Last updated</span>
                            <Timestamp 
                              time={effectiveData.lastUpdated as Date} 
                              variant="relative" 
                              showIcon={false}
                              className="text-[10px] text-muted-foreground"
                            />
                          </>
                        )}
                      </div>
                      
                      {/* Second metric - right-justified with color on the right */}
                      {config.gauges.length > 1 && (
                        <div className="flex items-center gap-2 @[500px]:flex-col @[500px]:gap-1 @[500px]:items-end @[700px]:flex-row-reverse @[700px]:gap-2 @[700px]:items-end text-right">
                          <div className="flex flex-col items-end">
                            {/* Single-cell layout: dot on text line, two-line labels, right-justified */}
                            <div className="hidden @[500px]:flex @[700px]:hidden flex-col items-end gap-1">
                              <div className="flex items-center gap-1">
                                <span className="text-muted-foreground text-xs leading-tight">{config.chartAreas[1]?.label || 'Results'}</span>
                                <div 
                                  className="w-3 h-3 rounded-sm" 
                                  style={{ 
                                    backgroundColor: config.chartAreas[1]?.color || '#a855f7',
                                    filter: `drop-shadow(0 0 8px ${config.chartAreas[1]?.color || '#a855f7'}20)`
                                  }}
                                />
                              </div>
                              <span className="font-medium text-foreground text-base leading-tight">
                                {renderValue(effectiveData?.[config.gauges[1].totalKey], { useGrouping: false })}
                              </span>
                              <span className="text-muted-foreground text-xs leading-tight">per day</span>
                            </div>
                            {/* Default layout: dot beside number, single-line label */}
                            <div className="flex @[500px]:hidden @[700px]:flex items-center gap-1">
                              <span className="font-medium text-foreground text-base leading-tight">
                                {renderValue(effectiveData?.[config.gauges[1].totalKey], { useGrouping: false })}
                              </span>
                              <div 
                                className="w-3 h-3 rounded-sm" 
                                style={{ 
                                  backgroundColor: config.chartAreas[1]?.color || '#a855f7',
                                  filter: `drop-shadow(0 0 8px ${config.chartAreas[1]?.color || '#a855f7'}20)`
                                }}
                              />
                            </div>
                            <span className="text-muted-foreground text-xs leading-tight @[500px]:hidden @[700px]:block">{config.chartAreas[1]?.label || 'Results'} / day</span>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              // Grid layout: original behavior
              <div className={cn("grid gap-3 items-start", gridClasses)}>
                
                {/* Render gauges */}
                {config.gauges.map((gaugeConfig) => {
                const rawValue = effectiveData?.[gaugeConfig.valueKey]
                const rawAverage = effectiveData?.[gaugeConfig.averageKey]
                const rawPeak = effectiveData?.[gaugeConfig.peakKey]
                const rawTotal = effectiveData?.[gaugeConfig.totalKey]
                
                const value = typeof rawValue === 'string' ? 0 : (rawValue as number ?? 0)
                const average = typeof rawAverage === 'string' ? 0 : (rawAverage as number ?? 0)
                const peak = typeof rawPeak === 'string' ? 50 : (rawPeak as number ?? 50)
                const total = typeof rawTotal === 'string' ? 0 : (rawTotal as number ?? 0)
                
                const isQuestionMark = typeof rawValue === 'string' || typeof rawAverage === 'string' || typeof rawPeak === 'string' || typeof rawTotal === 'string'

                // Generate gauge column span classes if specified
                const gaugeSpanClasses = gaugeConfig.colSpan ? [
                  gaugeConfig.colSpan.base ? `col-span-${gaugeConfig.colSpan.base}` : '',
                  gaugeConfig.colSpan.sm ? `@[500px]:col-span-${gaugeConfig.colSpan.sm}` : '',
                  gaugeConfig.colSpan.md ? `@[700px]:col-span-${gaugeConfig.colSpan.md}` : '',
                  gaugeConfig.colSpan.lg ? `@[900px]:col-span-${gaugeConfig.colSpan.lg}` : '',
                  gaugeConfig.colSpan.xl ? `@[1100px]:col-span-${gaugeConfig.colSpan.xl}` : ''
                ].filter(Boolean).join(' ') : ''

                return (
                  <div key={gaugeConfig.key} className={cn("bg-card rounded-lg h-48 overflow-visible flex items-center justify-center", gaugeSpanClasses)}>
                    <div className="w-full h-full flex items-center justify-center">
                      <Gauge
                        value={value}
                        beforeValue={average}
                        title={gaugeConfig.title}
                        information={hasGaugeData ? `**Current:** ${isQuestionMark ? '?' : value}  
*Current hourly rate (rolling 60-min window)*

**Average:** ${isQuestionMark ? '?' : average}  
*24-hour average hourly rate*

**Peak:** ${isQuestionMark ? '?' : peak}  
*Peak hourly rate over last 24 hours*

**Total:** ${isQuestionMark ? '?' : total}  
*Total over last 24 hours*` : "Loading metrics..."}
                        valueUnit={gaugeConfig.unit ?? ""}
                        min={0}
                        max={peak}
                        showTicks={true}
                        decimalPlaces={gaugeConfig.decimalPlaces ?? 0}
                        showOnlyEssentialTicks={true}
                        segments={gaugeConfig.segments ?? [
                          { start: 0, end: 10, color: 'var(--false)' },
                          { start: 10, end: 90, color: 'var(--neutral)' },
                          { start: 90, end: 100, color: 'var(--true)' }
                        ]}
                        backgroundColor="var(--background)"
                      />
                    </div>
                  </div>
                )
              })}

              {/* Chart component */}
              <div className={cn("bg-card rounded-lg p-4 h-48 flex flex-col", chartSpanClasses)}>
                <div className="flex flex-col h-full min-w-0">
                  <div className="w-full flex-[3] min-h-0 min-w-0 mb-1 @[700px]:flex-[4] @[700px]:mb-0">
                    {!hasChartData && useRealData ? (
                      // Loading state for chart
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
                        <ChartContainer config={config.chartConfig} className="w-full h-full">
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
                                if (totalPoints >= 12 && index === Math.floor(totalPoints / 2)) return "12h ago"
                                return ""
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
                              content={<CustomChartTooltip chartConfig={config.chartConfig} />}
                            />
                            {config.chartAreas.map((area, index) => (
                              <Area
                                key={area.dataKey}
                                dataKey={area.dataKey}
                                type="step"
                                fill={area.color}
                                fillOpacity={area.fillOpacity ?? 0.8}
                                stroke="none"
                                strokeWidth={0}
                                stackId="1"
                                animationBegin={0}
                                animationDuration={300}
                                isAnimationActive={true}
                              />
                            ))}
                          </AreaChart>
                        </ChartContainer>
                      </div>
                    )}
                  </div>

                  {/* Error indicator */}
                  {useRealData && hasErrorsLast24h && onErrorClick && (
                    <div className="flex-shrink-0 pt-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={onErrorClick}
                        className="h-6 px-2 text-xs text-destructive hover:text-destructive hover:bg-destructive/10 gap-1"
                      >
                        <AlertTriangle className="h-3 w-3" />
                        {errorsCount24h} errors (24h)
                      </Button>
                    </div>
                  )}
                  
                  {/* 24-hour totals at the bottom - responsive layout */}
                  <div className="flex justify-between items-end text-sm flex-shrink-0 relative">
                    {/* First metric - left-justified with color on the left */}
                    {config.gauges.length > 0 && (
                      <div className="flex items-center gap-2 @[500px]:flex-col @[500px]:gap-1 @[500px]:items-center @[700px]:flex-row @[700px]:gap-2 @[700px]:items-start">
                        <div className="flex flex-col items-start">
                          {/* Single-cell layout: dot on text line, two-line labels, left-justified */}
                          <div className="hidden @[500px]:flex @[700px]:hidden flex-col items-start gap-1">
                            <div className="flex items-center gap-1">
                              <div 
                                className="w-3 h-3 rounded-sm" 
                                style={{ 
                                  backgroundColor: config.chartAreas[0]?.color || '#3b82f6',
                                  filter: `drop-shadow(0 0 8px ${config.chartAreas[0]?.color || '#3b82f6'}20)`
                                }}
                              />
                              <span className="text-muted-foreground text-xs leading-tight">{config.chartAreas[0]?.label || 'Items'}</span>
                            </div>
                            <span className="font-medium text-foreground text-base leading-tight">
                              {renderValue(effectiveData?.[config.gauges[0].totalKey], { useGrouping: false })}
                            </span>
                            <span className="text-muted-foreground text-xs leading-tight">per day</span>
                          </div>
                          {/* Default layout: dot beside number, single-line label */}
                          <div className="flex @[500px]:hidden @[700px]:flex items-center gap-1">
                            <div 
                              className="w-3 h-3 rounded-sm" 
                              style={{ 
                                backgroundColor: config.chartAreas[0]?.color || '#3b82f6',
                                filter: `drop-shadow(0 0 8px ${config.chartAreas[0]?.color || '#3b82f6'}20)`
                              }}
                            />
                            <span className="font-medium text-foreground text-base leading-tight">
                              {renderValue(effectiveData?.[config.gauges[0].totalKey], { useGrouping: false })}
                            </span>
                          </div>
                          <span className="text-muted-foreground text-xs leading-tight @[500px]:hidden @[700px]:block">{config.chartAreas[0]?.label || 'Items'} / day</span>
                        </div>
                      </div>
                    )}
                    
                    {/* Center: Last updated timestamp - absolutely centered in the chart card */}
                    <div className="absolute left-1/2 bottom-0 transform -translate-x-1/2 mb-1 flex flex-col items-center z-10">
                      {useRealData && effectiveData?.lastUpdated && (
                        <>
                          <span className="text-[10px] text-muted-foreground leading-tight">Last updated</span>
                          <Timestamp 
                            time={effectiveData.lastUpdated as Date} 
                            variant="relative" 
                            showIcon={false}
                            className="text-[10px] text-muted-foreground"
                          />
                        </>
                      )}
                    </div>
                    
                    {/* Second metric - right-justified with color on the right */}
                    {config.gauges.length > 1 && (
                      <div className="flex items-center gap-2 @[500px]:flex-col @[500px]:gap-1 @[500px]:items-end @[700px]:flex-row-reverse @[700px]:gap-2 @[700px]:items-end text-right">
                        <div className="flex flex-col items-end">
                          {/* Single-cell layout: dot on text line, two-line labels, right-justified */}
                          <div className="hidden @[500px]:flex @[700px]:hidden flex-col items-end gap-1">
                            <div className="flex items-center gap-1">
                              <span className="text-muted-foreground text-xs leading-tight">{config.chartAreas[1]?.label || 'Results'}</span>
                              <div 
                                className="w-3 h-3 rounded-sm" 
                                style={{ 
                                  backgroundColor: config.chartAreas[1]?.color || '#a855f7',
                                  filter: `drop-shadow(0 0 8px ${config.chartAreas[1]?.color || '#a855f7'}20)`
                                }}
                              />
                            </div>
                            <span className="font-medium text-foreground text-base leading-tight">
                              {renderValue(effectiveData?.[config.gauges[1].totalKey], { useGrouping: false })}
                            </span>
                            <span className="text-muted-foreground text-xs leading-tight">per day</span>
                          </div>
                          {/* Default layout: dot beside number, single-line label */}
                          <div className="flex @[500px]:hidden @[700px]:flex items-center gap-1">
                            <span className="font-medium text-foreground text-base leading-tight">
                              {renderValue(effectiveData?.[config.gauges[1].totalKey], { useGrouping: false })}
                            </span>
                            <div 
                              className="w-3 h-3 rounded-sm" 
                              style={{ 
                                backgroundColor: config.chartAreas[1]?.color || '#a855f7',
                                filter: `drop-shadow(0 0 8px ${config.chartAreas[1]?.color || '#a855f7'}20)`
                              }}
                            />
                          </div>
                          <span className="text-muted-foreground text-xs leading-tight @[500px]:hidden @[700px]:block">{config.chartAreas[1]?.label || 'Results'} / day</span>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
            )}
          </div>
        </div>
      )}
    </>
  )
} 