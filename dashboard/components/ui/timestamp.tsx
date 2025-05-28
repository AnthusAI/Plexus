import React, { useEffect, useState } from 'react'
import { Clock, Timer } from 'lucide-react'
import { formatDistanceToNow, formatDuration, intervalToDuration, format, Duration } from 'date-fns'
import { cn } from '@/lib/utils'
import NumberFlowWrapper from './number-flow'

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

const formatElapsedTime = (start: Date, end: Date): { type: 'string', value: string } | { type: 'component', value: React.ReactNode } => {
  const duration = intervalToDuration({ start, end })
  
  // Calculate total minutes to determine if we should show seconds
  const totalMinutes = (duration.hours || 0) * 60 + (duration.minutes || 0)
  
  // Build components with NumberFlow
  const parts: React.ReactNode[] = []
  
  if (totalMinutes >= 1) {
    // Show hours and minutes
    if (duration.hours && duration.hours > 0) {
      parts.push(
        <span key="hours">
          <NumberFlowWrapper value={duration.hours} /> hour{duration.hours === 1 ? '' : 's'}
        </span>
      )
    }
    if (duration.minutes && duration.minutes > 0) {
      parts.push(
        <span key="minutes"> 
          <NumberFlowWrapper value={duration.minutes} /> minute{duration.minutes === 1 ? '' : 's'}
        </span>
      )
    }
  } else {
    // Show minutes and seconds
    if (duration.minutes && duration.minutes > 0) {
      parts.push(
        <span key="minutes">
          <NumberFlowWrapper value={duration.minutes} /> minute{duration.minutes === 1 ? '' : 's'}
        </span>
      )
    }
    if (duration.seconds && duration.seconds > 0) {
      parts.push(
        <span key="seconds"> 
          <NumberFlowWrapper value={duration.seconds} /> second{duration.seconds === 1 ? '' : 's'}
        </span>
      )
    }
  }
  
  // If no parts, return empty
  if (parts.length === 0) {
    return { type: 'string', value: '' }
  }
  
  return { 
    type: 'component', 
    value: <span>{parts}</span>
  }
}

const areDatesMeaningfullyDifferent = (start: Date, end: Date): boolean => {
  // Return false if times are the same or within 1 second of each other
  const diffInMs = Math.abs(end.getTime() - start.getTime())
  return diffInMs > 1000 // More than 1 second difference
}

const formatRelativeTime = (date: Date): { type: 'string', value: string } | { type: 'component', value: React.ReactNode } => {
  try {
    // Check if date is valid
    if (isNaN(date.getTime())) {
      return { type: 'string', value: '' };
    }
    
    const now = new Date();
    const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);
    
    // Handle future dates
    if (diffInSeconds < 0) {
      return { type: 'string', value: 'in the future' };
    }
    
    // Less than 1 minute
    if (diffInSeconds < 60) {
      return { type: 'string', value: '<1 minute ago' };
    }
    
    // Minutes
    const diffInMinutes = Math.floor(diffInSeconds / 60);
    if (diffInMinutes < 60) {
      return { 
        type: 'component', 
        value: (
          <span>
            <NumberFlowWrapper value={diffInMinutes} /> minute{diffInMinutes === 1 ? '' : 's'} ago
          </span>
        )
      };
    }
    
    // Hours
    const diffInHours = Math.floor(diffInMinutes / 60);
    if (diffInHours < 24) {
      return { 
        type: 'component', 
        value: (
          <span>
            <NumberFlowWrapper value={diffInHours} /> hour{diffInHours === 1 ? '' : 's'} ago
          </span>
        )
      };
    }
    
    // Days
    const diffInDays = Math.floor(diffInHours / 24);
    if (diffInDays < 7) {
      return { 
        type: 'component', 
        value: (
          <span>
            <NumberFlowWrapper value={diffInDays} /> day{diffInDays === 1 ? '' : 's'} ago
          </span>
        )
      };
    }
    
    // Weeks
    const diffInWeeks = Math.floor(diffInDays / 7);
    if (diffInWeeks < 4) {
      return { 
        type: 'component', 
        value: (
          <span>
            <NumberFlowWrapper value={diffInWeeks} /> week{diffInWeeks === 1 ? '' : 's'} ago
          </span>
        )
      };
    }
    
    // Months
    const diffInMonths = Math.floor(diffInDays / 30);
    if (diffInMonths < 12) {
      return { 
        type: 'component', 
        value: (
          <span>
            <NumberFlowWrapper value={diffInMonths} /> month{diffInMonths === 1 ? '' : 's'} ago
          </span>
        )
      };
    }
    
    // Years
    const diffInYears = Math.floor(diffInDays / 365);
    return { 
      type: 'component', 
      value: (
        <span>
          <NumberFlowWrapper value={diffInYears} /> year{diffInYears === 1 ? '' : 's'} ago
        </span>
      )
    };
    
  } catch (e) {
    console.warn('Invalid date format:', date);
    return { type: 'string', value: '' };
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
  const [displayContent, setDisplayContent] = useState<React.ReactNode>('')
  const [showAbsolute, setShowAbsolute] = useState(false)
  const timeDate = typeof time === 'string' ? new Date(time) : time

  useEffect(() => {
    const updateTime = () => {
      if (variant === 'elapsed') {
        const endTime = completionTime 
          ? (typeof completionTime === 'string' ? new Date(completionTime) : completionTime)
          : new Date()
        
        // Only show elapsed time if the dates are meaningfully different
        if (areDatesMeaningfullyDifferent(timeDate, endTime)) {
          const result = formatElapsedTime(timeDate, endTime)
          setDisplayContent(result.type === 'component' ? result.value : result.value)
        } else {
          setDisplayContent('') // Return empty string if times are effectively the same
        }
      } else {
        if (showAbsolute) {
          setDisplayContent(formatAbsoluteTime(timeDate))
        } else {
          const result = formatRelativeTime(timeDate)
          setDisplayContent(result.type === 'component' ? result.value : result.value)
        }
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

  // Don't render anything if there's no content to display (e.g., elapsed time with same timestamps)
  if (!displayContent) {
    return null
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
      <span>{displayContent}</span>
    </div>
  )
} 