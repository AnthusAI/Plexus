import React, { useEffect, useState } from 'react'
import { Clock, Timer } from 'lucide-react'
import { formatDistanceToNow, formatDuration, intervalToDuration, format, Duration } from 'date-fns'
import { cn } from '@/lib/utils'

export interface TimestampProps {
  /**
   * The timestamp to display
   */
  time: string | Date
  /**
   * Optional completion time for elapsed time display
   */
  completionTime?: string | Date
  /**
   * The variant of the timestamp to display
   */
  variant: 'elapsed' | 'relative'
  /**
   * Whether to show the icon
   */
  showIcon?: boolean
  /**
   * Additional CSS classes
   */
  className?: string
}

const formatElapsedTime = (start: Date, end: Date): string => {
  const duration = intervalToDuration({ start, end })
  
  // Calculate total minutes to determine if we should show seconds
  const totalMinutes = (duration.hours || 0) * 60 + (duration.minutes || 0)
  
  // If duration is over 1 minute, don't show seconds
  let formatOptions
  if (totalMinutes >= 1) {
    formatOptions = ['hours', 'minutes']
  } else {
    formatOptions = ['minutes', 'seconds']
  }
  
  return formatDuration(duration, {
    format: formatOptions as any,
    zero: false,
    delimiter: ' '
  }).replace(/(\d+) (\w+)/g, '$1 $2') // Convert "1 hour 2 minutes" to "1 h 2 m"
}

const formatRelativeTime = (date: Date): string => {
  try {
    // Check if date is valid
    if (isNaN(date.getTime())) {
      return '';
    }
    
    const now = new Date();
    const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);
    
    // Handle future dates
    if (diffInSeconds < 0) {
      return 'in the future';
    }
    
    // Less than 1 minute
    if (diffInSeconds < 60) {
      return '<1 minute ago';
    }
    
    // Minutes
    const diffInMinutes = Math.floor(diffInSeconds / 60);
    if (diffInMinutes < 60) {
      return `${diffInMinutes} minute${diffInMinutes === 1 ? '' : 's'} ago`;
    }
    
    // Hours
    const diffInHours = Math.floor(diffInMinutes / 60);
    if (diffInHours < 24) {
      return `${diffInHours} hour${diffInHours === 1 ? '' : 's'} ago`;
    }
    
    // Days
    const diffInDays = Math.floor(diffInHours / 24);
    if (diffInDays < 7) {
      return `${diffInDays} day${diffInDays === 1 ? '' : 's'} ago`;
    }
    
    // Weeks
    const diffInWeeks = Math.floor(diffInDays / 7);
    if (diffInWeeks < 4) {
      return `${diffInWeeks} week${diffInWeeks === 1 ? '' : 's'} ago`;
    }
    
    // Months
    const diffInMonths = Math.floor(diffInDays / 30);
    if (diffInMonths < 12) {
      return `${diffInMonths} month${diffInMonths === 1 ? '' : 's'} ago`;
    }
    
    // Years
    const diffInYears = Math.floor(diffInDays / 365);
    return `${diffInYears} year${diffInYears === 1 ? '' : 's'} ago`;
    
  } catch (e) {
    console.warn('Invalid date format:', date);
    return '';
  }
}

const formatAbsoluteTime = (date: Date): string => {
  try {
    if (isNaN(date.getTime())) {
      return '';
    }
    return format(date, 'MMM d, yyyy h:mm:ss a');
  } catch (e) {
    console.warn('Invalid date format:', date);
    return '';
  }
}

export function Timestamp({ 
  time, 
  completionTime, 
  variant = 'relative',
  showIcon = true,
  className 
}: TimestampProps) {
  const [displayText, setDisplayText] = useState('')
  const [showAbsolute, setShowAbsolute] = useState(false)
  const timeDate = typeof time === 'string' ? new Date(time) : time

  useEffect(() => {
    const updateTime = () => {
      if (variant === 'elapsed') {
        const endTime = completionTime 
          ? (typeof completionTime === 'string' ? new Date(completionTime) : completionTime)
          : new Date()
        setDisplayText(formatElapsedTime(timeDate, endTime))
      } else {
        setDisplayText(showAbsolute ? formatAbsoluteTime(timeDate) : formatRelativeTime(timeDate))
      }
    }

    updateTime()
    
    // Only set up interval if:
    // 1. We're showing relative time and not absolute time, OR
    // 2. We're showing elapsed time and there's no completion time
    if ((!showAbsolute && variant === 'relative') || 
        (variant === 'elapsed' && !completionTime)) {
      const interval = setInterval(updateTime, 1000)
      return () => clearInterval(interval)
    }
  }, [time, completionTime, variant, showAbsolute])

  const handleClick = () => {
    if (variant === 'relative') {
      setShowAbsolute(!showAbsolute)
    }
  }

  return (
    <div 
      className={cn(
        "flex items-center gap-1 text-sm text-muted-foreground", 
        variant === 'relative' && "cursor-pointer hover:text-foreground",
        className
      )}
      onClick={handleClick}
      role={variant === 'relative' ? "button" : undefined}
      tabIndex={variant === 'relative' ? 0 : undefined}
      onKeyDown={variant === 'relative' ? (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          handleClick()
        }
      } : undefined}
      title={variant === 'relative' ? (showAbsolute ? 'Click to show relative time' : 'Click to show exact time') : undefined}
    >
      {showIcon && (variant === 'elapsed' ? (
        <Timer className="h-4 w-4" />
      ) : (
        <Clock className="h-4 w-4" />
      ))}
      <span>{displayText}</span>
    </div>
  )
} 