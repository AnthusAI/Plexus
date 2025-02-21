import { formatDistanceToNow } from 'date-fns'

export function formatTimeAgo(timestamp: string | Date, abbreviated: boolean = true): string {
  try {
    // Handle string timestamps
    const date = typeof timestamp === 'string' ? new Date(timestamp) : timestamp
    
    // Check for invalid dates
    if (isNaN(date.getTime())) {
      return 'Invalid date'
    }
    
    return formatDistanceToNow(date, { addSuffix: true })
  } catch (error) {
    console.error('Error formatting date:', error)
    return 'Invalid date'
  }
} 