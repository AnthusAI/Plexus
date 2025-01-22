import { formatDistanceToNow } from 'date-fns'

export function formatTimeAgo(timestamp: string | Date, abbreviated = false): string {
  console.log('formatTimeAgo input:', { timestamp, abbreviated })

  // If the timestamp is already "less than a minute ago", handle it specially
  if (typeof timestamp === 'string' && timestamp === 'less than a minute ago') {
    return abbreviated ? '<1m ago' : timestamp
  }

  // If the timestamp already contains 'ago', return it with appropriate formatting
  if (typeof timestamp === 'string' && timestamp.includes('ago')) {
    console.log('Already contains ago:', timestamp)
    if (abbreviated) {
      const result = timestamp
        .replace('about ', '')
        .replace(' seconds', 's')
        .replace(' second', 's')
        .replace(' minutes', 'm')
        .replace(' minute', 'm')
        .replace(' hours', 'h')
        .replace(' hour', 'h')
        .replace(' days', 'd')
        .replace(' day', 'd')
        .replace(' months', 'mo')
        .replace(' month', 'mo')
        .replace(' years', 'y')
        .replace(' year', 'y')
      console.log('Abbreviated result:', result)
      return result
    }
    return timestamp
  }

  // Parse the date and check for sub-minute times first
  const date = typeof timestamp === 'string' ? new Date(timestamp) : timestamp
  const msSinceDate = Date.now() - date.getTime()
  console.log('Time since date (ms):', msSinceDate)

  if (msSinceDate < 60000) {
    const result = abbreviated ? '<1m ago' : 'less than a minute ago'
    console.log('Sub-minute result:', result)
    return result
  }

  // For all other times, use formatDistanceToNow
  const formatted = formatDistanceToNow(date, { 
    addSuffix: true,
    includeSeconds: false
  })
  console.log('formatDistanceToNow result:', formatted)

  if (abbreviated) {
    const result = formatted
      .replace('about ', '')
      .replace(' minutes', 'm')
      .replace(' minute', 'm')
      .replace(' hours', 'h')
      .replace(' hour', 'h')
      .replace(' days', 'd')
      .replace(' day', 'd')
      .replace(' months', 'mo')
      .replace(' month', 'mo')
      .replace(' years', 'y')
      .replace(' year', 'y')
    console.log('Final abbreviated result:', result)
    return result
  }

  return formatted
} 