import React, { useEffect, useState } from 'react'
import { Clock, Timer } from 'lucide-react'
import { formatDistanceToNow, formatDuration, intervalToDuration, format } from 'date-fns'
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
  return formatDuration(duration, {
    format: ['hours', 'minutes', 'seconds'],
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
    return formatDistanceToNow(date, { 
      addSuffix: true,
      includeSeconds: true
    }).replace('about ', '');
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
    // Only set up interval if we're not showing absolute time
    if (!showAbsolute || variant === 'elapsed') {
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