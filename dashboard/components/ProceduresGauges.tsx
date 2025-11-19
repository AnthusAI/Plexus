'use client'

import React from 'react'
import { BaseGauges, BaseGaugesConfig, BaseGaugesData } from './BaseGauges'
import { useProceduresMetrics } from '../hooks/useUnifiedMetrics'

// Configuration for procedures-specific gauges (two gauges: procedures + graph nodes)  
const proceduresGaugesConfig: BaseGaugesConfig = {
  // Use grid layout to match ItemsGauges pattern
  layout: 'grid',
  gridCols: {
    base: 2,  // < 500px: 2 cols, chart spans full width on second row
    sm: 3,    // >= 500px: 3 cols, chart takes 1 remaining column
    md: 4,    // >= 700px: 4 cols, chart takes 2 remaining columns  
    lg: 5,    // >= 900px: 5 cols, chart takes 3 remaining columns
    xl: 6     // >= 1100px: 6 cols, chart takes 4 remaining columns
  },
  chartSpan: {
    base: 2,  // spans full width on second row
    sm: 1,    // spans 1 remaining column
    md: 2,    // spans 2 remaining columns
    lg: 3,    // spans 3 remaining columns
    xl: 4     // spans 4 remaining columns
  },
  
  gauges: [
    {
      key: 'procedures',
      title: 'Procedures / hour',
      valueKey: 'proceduresPerHour',
      averageKey: 'proceduresAveragePerHour',
      peakKey: 'proceduresPeakHourly',
      totalKey: 'proceduresTotal24h',
      color: 'hsl(var(--chart-1))',
      unit: '',
      decimalPlaces: 0,
      segments: [
        { start: 0, end: 10, color: 'var(--false)' },
        { start: 10, end: 90, color: 'var(--neutral)' },
        { start: 90, end: 100, color: 'var(--true)' }
      ]
    },
    {
      key: 'graphNodes',
      title: 'Graph Nodes / hour',
      valueKey: 'graphNodesPerHour',
      averageKey: 'graphNodesAveragePerHour',
      peakKey: 'graphNodesPeakHourly',
      totalKey: 'graphNodesTotal24h',
      color: 'hsl(var(--chart-2))',
      unit: '',
      decimalPlaces: 0,
      segments: [
        { start: 0, end: 50, color: 'var(--false)' },
        { start: 50, end: 450, color: 'var(--neutral)' },
        { start: 450, end: 500, color: 'var(--true)' }
      ]
    }
  ],
  chartAreas: [
    {
      dataKey: 'procedures',
      label: 'Procedures',
      color: 'var(--primary)',
      fillOpacity: 0.8
    },
    {
      dataKey: 'graphNodes',
      label: 'Graph Nodes',
      color: 'var(--secondary)',
      fillOpacity: 0.8
    }
  ],
  chartConfig: {
    procedures: {
      label: 'Procedures',
      color: 'hsl(var(--chart-1))',
    },
    graphNodes: {
      label: 'Graph Nodes',
      color: 'hsl(var(--chart-2))',
    },
  }
}

interface ProceduresGaugesProps {
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

export function ProceduresGauges({ 
  className,
  overrideData,
  useRealData = true,
  disableEmergenceAnimation = false,
  onErrorClick
}: ProceduresGaugesProps) {
  // Use procedures metrics (procedures and graph nodes)
  const { 
    metrics: metricsData, 
    isLoading, 
    error 
  } = useProceduresMetrics()

  // Transform metrics data to BaseGaugesData format
  // For procedures, we use both procedures data and graphNodes data
  const data: BaseGaugesData | null = metricsData ? {
    // Procedures data
    proceduresPerHour: metricsData.itemsPerHour || 0,
    proceduresAveragePerHour: metricsData.itemsAveragePerHour || 0,
    proceduresPeakHourly: metricsData.itemsPeakHourly || 10, // Use higher baseline for procedures
    proceduresTotal24h: metricsData.itemsTotal24h || 0,
    
    // Graph Nodes data
    graphNodesPerHour: metricsData.scoreResultsPerHour || 0,
    graphNodesAveragePerHour: metricsData.scoreResultsAveragePerHour || 0,
    graphNodesPeakHourly: metricsData.scoreResultsPeakHourly || 50, // Use higher baseline for graph nodes
    graphNodesTotal24h: metricsData.scoreResultsTotal24h || 0,
    
    chartData: metricsData.chartData?.map((point: any) => ({
      time: point.time,
      procedures: point.items || 0, // Map items to procedures for chart display
      graphNodes: point.scoreResults || 0, // Map scoreResults to graphNodes for chart display
      bucketStart: point.bucketStart,
      bucketEnd: point.bucketEnd
    })) || [],
    lastUpdated: metricsData.lastUpdated || new Date(),
    hasErrorsLast24h: metricsData.hasErrorsLast24h || false,
    totalErrors24h: metricsData.totalErrors24h || 0
  } : null

  return (
    <BaseGauges
      className={className}
      config={proceduresGaugesConfig}
      data={useRealData ? data : null}
      isLoading={isLoading}
      error={error}
      title="Procedures & Graph Nodes, Last 24 Hours"
      overrideData={overrideData}
      useRealData={useRealData}
      disableEmergenceAnimation={disableEmergenceAnimation}
      onErrorClick={onErrorClick}
    />
  )
}

