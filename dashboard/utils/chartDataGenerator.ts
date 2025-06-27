import { getAggregatedMetrics, AggregatedMetricsData, alignToHour } from './metricsAggregator'

export interface ChartDataPoint {
  time: string
  items: number
  scoreResults: number
  bucketStart: string
  bucketEnd: string
  _fullBucketStart?: string
  _fullBucketEnd?: string
}

/**
 * Generate chart data for the last 24 hours using the new aggregation system
 * Now supports progressive loading with real-time UI updates
 * 
 * Key insight: For completed hour buckets, we show the full calendar-aligned hour's data.
 * For the current incomplete hour bucket, we show only the data up to the current time
 * to provide real-time visibility into current activity.
 */
export async function generateChartData(
  accountId: string,
  startTime: Date,
  endTime: Date,
  scorecardId?: string,
  scoreId?: string,
  type?: string,
  onProgress?: (chartData: ChartDataPoint[]) => void
): Promise<ChartDataPoint[]> {
  const requestHours = Math.ceil((endTime.getTime() - startTime.getTime()) / (1000 * 60 * 60))

  // Align the start time to the nearest hour boundary for consistent hour buckets
  const alignedStartTime = alignToHour(startTime)
  
  // Calculate how many hour buckets we need from the aligned start to cover the requested range
  const totalHours = Math.ceil((endTime.getTime() - alignedStartTime.getTime()) / (1000 * 60 * 60))

  const chartData: ChartDataPoint[] = []
  
  // Initialize chart data with empty values using hour-aligned buckets
  for (let i = 0; i < totalHours; i++) {
    const bucketStart = new Date(alignedStartTime.getTime() + i * 60 * 60 * 1000)
    const bucketEnd = new Date(Math.min(bucketStart.getTime() + 60 * 60 * 1000, endTime.getTime()))
    
    // Skip buckets that end before our actual start time
    if (bucketEnd <= startTime) {
      continue
    }
    
    // For display purposes: adjust bucket start if it's before our actual start time
    // This affects the visual width but not the data aggregation
    const displayBucketStart = bucketStart < startTime ? startTime : bucketStart
    
    const timeLabel = formatTimeLabel(displayBucketStart, chartData.length, totalHours)

    chartData.push({
      time: timeLabel,
      items: 0, // Start with 0, will be filled progressively
      scoreResults: 0, // Start with 0, will be filled progressively
      bucketStart: displayBucketStart.toISOString(), // For visual width calculation
      bucketEnd: bucketEnd.toISOString(), // For visual width calculation
      // Store the full calendar-aligned bucket for data aggregation
      _fullBucketStart: bucketStart.toISOString(),
      _fullBucketEnd: new Date(bucketStart.getTime() + 60 * 60 * 1000).toISOString()
    })
  }

  // Send initial empty chart data for immediate UI display
  if (onProgress) {
    onProgress([...chartData])
  }
  
  // Process buckets in parallel for much faster loading
  // Create promises for all bucket calculations
  const bucketPromises = chartData.map(async (dataPoint, index) => {
    // For the current incomplete hour bucket, use the actual time range (up to now)
    // For completed hour buckets, use the full calendar-aligned hour
    const fullBucketStart = new Date(dataPoint._fullBucketStart!)
    const fullBucketEnd = new Date(dataPoint._fullBucketEnd!)
    
    // Determine if this is the current incomplete hour bucket
    const isCurrentIncompleteHour = fullBucketEnd > endTime
    
    // Use appropriate time range for data aggregation
    const aggregationStart = fullBucketStart
    const aggregationEnd = isCurrentIncompleteHour ? endTime : fullBucketEnd
    
    // Get aggregated metrics for the appropriate time range
    const [itemsMetrics, scoreResultsMetrics] = await Promise.all([
      getAggregatedMetrics(accountId, 'items', aggregationStart, aggregationEnd, scorecardId, scoreId, type),
      getAggregatedMetrics(accountId, 'scoreResults', aggregationStart, aggregationEnd, scorecardId, scoreId, type)
    ])

    return {
      index,
      items: itemsMetrics.count,
      scoreResults: scoreResultsMetrics.count
    }
  })

  // Process buckets as they complete (for progressive updates)
  let completedBuckets = 0
  const bucketResults = await Promise.allSettled(bucketPromises.map(async (promise, index) => {
    const result = await promise
    
    // Update the chart data point
    chartData[result.index].items = result.items
    chartData[result.index].scoreResults = result.scoreResults
    
    // Clean up the internal properties
    delete (chartData[result.index] as any)._fullBucketStart
    delete (chartData[result.index] as any)._fullBucketEnd
    
    completedBuckets++
    
    // Send progressive update every few completed buckets or on completion
    if (onProgress && (completedBuckets % 3 === 0 || completedBuckets === chartData.length)) {
      onProgress([...chartData])
    }
    
    return result
  }))

  // Ensure final cleanup for any remaining internal properties
  chartData.forEach(point => {
    delete (point as any)._fullBucketStart
    delete (point as any)._fullBucketEnd
  })
  
  return chartData
}

/**
 * Format time labels for chart display
 */
function formatTimeLabel(bucketStart: Date, index: number, totalHours: number): string {
  const now = new Date()
  const hoursAgo = Math.round((now.getTime() - bucketStart.getTime()) / (1000 * 60 * 60))
  
  // For the first point (oldest), show "24h ago" or similar
  if (index === 0) {
    return `${hoursAgo}h ago`
  }
  
  // For the last point (newest), show "now"
  if (index === totalHours - 1) {
    return 'now'
  }
  
  // For middle points, show hour format
  if (totalHours <= 12) {
    // For shorter time ranges, show more labels
    return bucketStart.toLocaleTimeString('en-US', { 
      hour: 'numeric', 
      hour12: false 
    })
  } else {
    // For 24-hour view, only show key points
    if (index === Math.floor(totalHours / 2)) {
      return `${hoursAgo}h ago`
    }
    return ''
  }
}

/**
 * Calculate peak values from chart data for gauge scaling
 */
export function calculatePeakValues(chartData: ChartDataPoint[]): {
  itemsPeak: number
  scoreResultsPeak: number
} {
  const itemsValues = chartData.map(point => point.items)
  const scoreResultsValues = chartData.map(point => point.scoreResults)
  
  const itemsPeak = Math.max(...itemsValues, 50) // Minimum peak of 50 for reasonable scaling
  const scoreResultsPeak = Math.max(...scoreResultsValues, 300) // Minimum peak of 300 for reasonable scaling
  
  return {
    itemsPeak,
    scoreResultsPeak
  }
}

/**
 * Calculate average values from chart data
 */
export function calculateAverageValues(chartData: ChartDataPoint[]): {
  itemsAverage: number
  scoreResultsAverage: number
} {
  if (chartData.length === 0) {
    return { itemsAverage: 0, scoreResultsAverage: 0 }
  }
  
  const itemsTotal = chartData.reduce((sum, point) => sum + point.items, 0)
  const scoreResultsTotal = chartData.reduce((sum, point) => sum + point.scoreResults, 0)
  
  return {
    itemsAverage: Math.round(itemsTotal / chartData.length),
    scoreResultsAverage: Math.round(scoreResultsTotal / chartData.length)
  }
} 