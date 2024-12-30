import { formatDistanceToNow } from 'date-fns'

export function formatTimeAgo(timestamp: string | Date, abbreviated = false): string {
  // If the timestamp already contains 'ago', return it with appropriate formatting
  if (typeof timestamp === 'string' && timestamp.includes('ago')) {
    if (abbreviated) {
      return timestamp
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
    }
    return timestamp
  }

  // Otherwise, parse the date and format it
  const date = typeof timestamp === 'string' ? new Date(timestamp) : timestamp
  const formatted = formatDistanceToNow(date, { 
    addSuffix: true,
    includeSeconds: true,
  })

  if (abbreviated) {
    return formatted
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
  }

  return formatted
} 