'use client'

import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Gauge } from '@/components/gauge'
import { ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import { AreaChart, Area, XAxis, CartesianGrid, ResponsiveContainer } from 'recharts'
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
  [key: string]: number | Array<any> | Date | boolean | undefined
  chartData?: Array<{ time: string; [key: string]: any }>
  lastUpdated?: Date
  hasErrorsLast24h?: boolean
  totalErrors24h?: number
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
  
  // For real data usage, show error state if there's an error and no data at all
  if (useRealData && error && !hasGaugeData && !isLoading) {
    return (
      <div className={cn("w-full", className)}>
        <div className="text-center p-8">
          <p className="text-sm text-muted-foreground mb-2">Unable to load metrics</p>
          <p className="text-xs text-muted-foreground">{error}</p>
        </div>
      </div>
    )
  }

  // Animation variants for progressive disclosure
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
        delay: 0.5
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
      
      <AnimatePresence>
        {shouldShowComponent && (
        <motion.div 
          className={cn("w-full overflow-visible", className)}
          variants={disableEmergenceAnimation ? instantVariants : containerVariants}
          initial={useRealData && !disableEmergenceAnimation ? "hidden" : "visible"}
          animate="visible"
          exit={disableEmergenceAnimation ? undefined : "exit"}
          style={gaugeWidthStyles}
        >
          <motion.div 
            variants={disableEmergenceAnimation ? instantVariants : contentVariants}
            initial={useRealData && !disableEmergenceAnimation ? "hidden" : "visible"}
            animate="visible"
          >
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
                        <motion.div
                          key={chartData.length}
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          transition={{ duration: 4, ease: 'easeOut' }}
                          className="w-full h-full"
                          style={{
                            filter: 'drop-shadow(0 0 8px rgba(59, 130, 246, 0.2)) drop-shadow(0 0 8px rgba(168, 85, 247, 0.2))',
                            willChange: 'filter'
                          }}
                        >
                          <ChartContainer config={config.chartConfig} className="w-full h-full">
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
                                  if (totalPoints >= 12 && index === Math.floor(totalPoints / 2)) return "12h ago"
                                  return ""
                                }}
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
                        </motion.div>
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
                  </div>
                </div>
              </div>
            ) : (
              // Grid layout: original behavior
              <div className={cn("grid gap-3 items-start", gridClasses)}>
                
                {/* Render gauges */}
                {config.gauges.map((gaugeConfig) => {
                const value = effectiveData?.[gaugeConfig.valueKey] as number ?? 0
                const average = effectiveData?.[gaugeConfig.averageKey] as number ?? 0
                const peak = effectiveData?.[gaugeConfig.peakKey] as number ?? 50
                const total = effectiveData?.[gaugeConfig.totalKey] as number ?? 0

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
                      <motion.div
                        key={chartData.length}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ duration: 4, ease: 'easeOut' }}
                        className="w-full h-full"
                        style={{
                          filter: 'drop-shadow(0 0 8px rgba(59, 130, 246, 0.2)) drop-shadow(0 0 8px rgba(168, 85, 247, 0.2))',
                          willChange: 'filter'
                        }}
                      >
                        <ChartContainer config={config.chartConfig} className="w-full h-full">
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
                                if (totalPoints >= 12 && index === Math.floor(totalPoints / 2)) return "12h ago"
                                return ""
                              }}
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
                      </motion.div>
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
                </div>
              </div>
            </div>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
    </>
  )
} 