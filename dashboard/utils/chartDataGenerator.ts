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
 * Key insight: For display buckets that represent full hours, we should show the full
 * calendar-aligned hour's data even if part of that hour falls outside our time range.
 * The visual width still represents only the portion within our time range.
 */
export async function generateChartData(
  accountId: string,
  startTime: Date,
  endTime: Date,
  scorecardId?: string,
  scoreId?: string,
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
  
  // Process hours backward from most recent to oldest for real-time visual feedback
  for (let i = chartData.length - 1; i >= 0; i--) {
    const dataPoint = chartData[i]
    
    // Use the full calendar-aligned hour for data aggregation
    const fullBucketStart = new Date(dataPoint._fullBucketStart!)
    const fullBucketEnd = new Date(dataPoint._fullBucketEnd!)
    
    // Get aggregated metrics for the FULL hour bucket (not just the visible portion)
    const [itemsMetrics, scoreResultsMetrics] = await Promise.all([
      getAggregatedMetrics(accountId, 'items', fullBucketStart, fullBucketEnd, scorecardId, scoreId),
      getAggregatedMetrics(accountId, 'scoreResults', fullBucketStart, fullBucketEnd, scorecardId, scoreId)
    ])

    // Update the chart data point with the full hour's data
    chartData[i].items = itemsMetrics.count
    chartData[i].scoreResults = scoreResultsMetrics.count

    // Clean up the internal properties before sending to UI
    delete (chartData[i] as any)._fullBucketStart
    delete (chartData[i] as any)._fullBucketEnd

    // Send progressive update to UI
    if (onProgress) {
      onProgress([...chartData])
    }
  }
  
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