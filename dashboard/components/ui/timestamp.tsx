import React, { useEffect, useState } from 'react'
import { Clock, Timer } from 'lucide-react'
import { formatDistanceToNow, formatDuration, intervalToDuration, format, Duration } from 'date-fns'
import { cn } from '@/lib/utils'
import NumberFlowWrapper from './number-flow'
import { useTranslations } from '@/app/contexts/TranslationContext'

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
  /**
   * Whether to render in skeleton mode
   */
  skeletonMode?: boolean
}

const formatElapsedTime = (start: Date, end: Date, t: (key: string, variables?: Record<string, any>) => string): { type: 'string', value: string } | { type: 'component', value: React.ReactNode } => {
  const duration = intervalToDuration({ start, end })
  
  // Calculate total minutes to determine if we should show seconds
  const totalMinutes = (duration.hours || 0) * 60 + (duration.minutes || 0)
  
  // Build components with NumberFlow
  const parts: React.ReactNode[] = []
  
  if (totalMinutes >= 1) {
    // Show hours and minutes
    if (duration.hours && duration.hours > 0) {
      const hourText = duration.hours === 1 ? 'hour' : 'hours';
      parts.push(
        <span key="hours">
          <NumberFlowWrapper value={duration.hours} /> {t(hourText)}
        </span>
      )
    }
    if (duration.minutes && duration.minutes > 0) {
      const minuteText = duration.minutes === 1 ? 'minute' : 'minutes';
      parts.push(
        <span key="minutes"> 
          <NumberFlowWrapper value={duration.minutes} /> {t(minuteText)}
        </span>
      )
    }
  } else {
    // Show minutes and seconds
    if (duration.minutes && duration.minutes > 0) {
      const minuteText = duration.minutes === 1 ? 'minute' : 'minutes';
      parts.push(
        <span key="minutes">
          <NumberFlowWrapper value={duration.minutes} /> {t(minuteText)}
        </span>
      )
    }
    if (duration.seconds && duration.seconds > 0) {
      const secondText = duration.seconds === 1 ? 'second' : 'seconds';
      parts.push(
        <span key="seconds">
          <NumberFlowWrapper value={duration.seconds} /> {t(secondText)}
        </span>
      )
    }
  }

  // If no parts, it means the duration is less than a second, so we show 0 seconds.
  if (parts.length === 0) {
    return {
      type: 'component',
      value: (
        <span key="seconds">
          <NumberFlowWrapper value={0} /> seconds
        </span>
      ),
    }
  }

  return {
    type: 'component',
    value: <span>{parts}</span>
  }
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
      return { type: 'string', value: t('inTheFuture') };
    }

    // Less than 1 minute
    if (diffInSeconds < 60) {
      return { type: 'string', value: t('lessThanMinute') };
    }

    // Minutes
    const diffInMinutes = Math.floor(diffInSeconds / 60);
    if (diffInMinutes < 60) {
      const timeKey = diffInMinutes === 1 ? 'minuteAgo' : 'minutesAgo';
      return {
        type: 'string',
        value: t(timeKey, { count: diffInMinutes })
      };
    }

    // Hours
    const diffInHours = Math.floor(diffInMinutes / 60);
    if (diffInHours < 24) {
      const timeKey = diffInHours === 1 ? 'hourAgo' : 'hoursAgo';
      return {
        type: 'string',
        value: t(timeKey, { count: diffInHours })
      };
    }

    // Days
    const diffInDays = Math.floor(diffInHours / 24);
    if (diffInDays < 7) {
      const timeKey = diffInDays === 1 ? 'dayAgo' : 'daysAgo';
      return {
        type: 'string',
        value: t(timeKey, { count: diffInDays })
      };
    }

    // Weeks
    const diffInWeeks = Math.floor(diffInDays / 7);
    if (diffInWeeks < 4) {
      const timeKey = diffInWeeks === 1 ? 'weekAgo' : 'weeksAgo';
      return {
        type: 'string',
        value: t(timeKey, { count: diffInWeeks })
      };
    }

    // Months
    const diffInMonths = Math.floor(diffInDays / 30);
    if (diffInMonths < 12) {
      const timeKey = diffInMonths === 1 ? 'monthAgo' : 'monthsAgo';
      return {
        type: 'string',
        value: t(timeKey, { count: diffInMonths })
      };
    }

    // Years
    const diffInYears = Math.floor(diffInDays / 365);
    const timeKey = diffInYears === 1 ? 'yearAgo' : 'yearsAgo';
    return {
      type: 'string',
      value: t(timeKey, { count: diffInYears })
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
  className,
  skeletonMode = false
}: TimestampProps) {
  const t = useTranslations('time')
  const [displayContent, setDisplayContent] = useState<React.ReactNode>('')
  const [showAbsolute, setShowAbsolute] = useState(false)
  const timeDate = typeof time === 'string' ? new Date(time) : time

  // Skeleton mode rendering
  if (skeletonMode) {
    return (
      <div className={cn(
        "flex items-start gap-1 text-sm text-muted-foreground min-w-0", 
        className
      )}>
        {showIcon && <div className="h-4 w-4 bg-muted rounded animate-pulse flex-shrink-0" />}
        <div className="h-3 w-16 bg-muted rounded animate-pulse" />
      </div>
    )
  }

  useEffect(() => {
    const updateTime = () => {
      if (variant === 'elapsed') {
        const endTime = completionTime
          ? (typeof completionTime === 'string' ? new Date(completionTime) : completionTime)
          : new Date()

        const result = formatElapsedTime(timeDate, endTime, t)
        setDisplayContent(result.value)
      } else {
        if (showAbsolute) {
          setDisplayContent(formatAbsoluteTime(timeDate))
        } else {
          const result = formatRelativeTime(timeDate, t)
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
        "flex items-start gap-1 text-sm text-muted-foreground min-w-0", 
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
        <Timer className="h-4 w-4 flex-shrink-0" />
      ) : (
        <Clock className="h-4 w-4 flex-shrink-0" />
      ))}
      <span className="truncate">{displayContent}</span>
    </div>
  )
} 