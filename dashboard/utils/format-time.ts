import { formatDistanceToNow } from 'date-fns'

export function formatTimeAgo(timestamp: string | Date, abbreviated: boolean = true): string {
  const date = typeof timestamp === 'string' ? new Date(timestamp) : timestamp
  const timeSince = formatDistanceToNow(date, { addSuffix: true })
  
  if (!abbreviated) {
    return timeSince
  }

  // Abbreviate the formatted time
  return timeSince
    .replace('about ', '')
    .replace('less than ', '<')
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
    .replace(' ago', '')
} 