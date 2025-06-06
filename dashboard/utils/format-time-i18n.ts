// Internationalized time formatting utility
export function formatTimeAgoI18n(
  timestamp: string | Date, 
  t: (key: string, variables?: Record<string, any>) => string
): string {
  try {
    // Handle string timestamps
    const date = typeof timestamp === 'string' ? new Date(timestamp) : timestamp
    
    // Check for invalid dates
    if (isNaN(date.getTime())) {
      return t('time.invalidDate')
    }
    
    const now = new Date();
    const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);
    
    // Handle future dates
    if (diffInSeconds < 0) {
      return t('time.inTheFuture');
    }
    
    // Less than 1 minute
    if (diffInSeconds < 60) {
      return t('time.lessThanMinute');
    }
    
    // Minutes
    const diffInMinutes = Math.floor(diffInSeconds / 60);
    if (diffInMinutes < 60) {
      return t(diffInMinutes === 1 ? 'time.minuteAgo' : 'time.minutesAgo', { count: diffInMinutes });
    }
    
    // Hours
    const diffInHours = Math.floor(diffInMinutes / 60);
    if (diffInHours < 24) {
      return t(diffInHours === 1 ? 'time.hourAgo' : 'time.hoursAgo', { count: diffInHours });
    }
    
    // Days
    const diffInDays = Math.floor(diffInHours / 24);
    if (diffInDays < 7) {
      return t(diffInDays === 1 ? 'time.dayAgo' : 'time.daysAgo', { count: diffInDays });
    }
    
    // Weeks
    const diffInWeeks = Math.floor(diffInDays / 7);
    if (diffInWeeks < 4) {
      return t(diffInWeeks === 1 ? 'time.weekAgo' : 'time.weeksAgo', { count: diffInWeeks });
    }
    
    // Months
    const diffInMonths = Math.floor(diffInDays / 30);
    if (diffInMonths < 12) {
      return t(diffInMonths === 1 ? 'time.monthAgo' : 'time.monthsAgo', { count: diffInMonths });
    }
    
    // Years
    const diffInYears = Math.floor(diffInDays / 365);
    return t(diffInYears === 1 ? 'time.yearAgo' : 'time.yearsAgo', { count: diffInYears });
    
  } catch (error) {
    console.error('Error formatting date:', error)
    return t('time.invalidDate')
  }
}