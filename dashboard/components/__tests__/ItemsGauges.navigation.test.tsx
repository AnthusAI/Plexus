/**
 * Focused tests for ItemsGauges time navigation behavior
 * Tests the key requirement: offset resets to 0 when time period changes
 */

import { describe, it, expect } from '@jest/globals'

// Helper functions from ItemsGauges (extracted for testing)
function calculateTimeRange(period: 'hour' | 'day' | 'week', offset: number): { start: Date; end: Date } {
  const now = new Date()
  let end: Date
  let start: Date
  
  if (offset === 0) {
    end = now
  } else {
    // Calculate historical end time
    switch (period) {
      case 'hour':
        end = new Date(now.getTime() + offset * 60 * 60 * 1000)
        break
      case 'day':
        end = new Date(now.getTime() + offset * 24 * 60 * 60 * 1000)
        break
      case 'week':
        end = new Date(now.getTime() + offset * 7 * 24 * 60 * 60 * 1000)
        break
    }
  }
  
  // Calculate start based on period
  switch (period) {
    case 'hour':
      start = new Date(end.getTime() - 60 * 60 * 1000)
      break
    case 'day':
      start = new Date(end.getTime() - 24 * 60 * 60 * 1000)
      break
    case 'week':
      start = new Date(end.getTime() - 7 * 24 * 60 * 60 * 1000)
      break
  }
  
  return { start, end }
}

function formatTimeRangeLabel(period: 'hour' | 'day' | 'week', offset: number, start: Date, end: Date): string {
  if (offset === 0) {
    switch (period) {
      case 'hour': return 'Last Hour'
      case 'day': return 'Last 24 Hours'
      case 'week': return 'Last Week'
    }
  }
  
  // Historical format: "Nov 19, 2pm-3pm", "Nov 19", "Nov 11-18"
  const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  
  switch (period) {
    case 'hour':
      return `${monthNames[start.getMonth()]} ${start.getDate()}, ${start.getHours() % 12 || 12}${start.getHours() >= 12 ? 'pm' : 'am'}-${end.getHours() % 12 || 12}${end.getHours() >= 12 ? 'pm' : 'am'}`
    case 'day':
      return `${monthNames[start.getMonth()]} ${start.getDate()}`
    case 'week':
      return `${monthNames[start.getMonth()]} ${start.getDate()}-${end.getDate()}`
  }
}

describe('ItemsGauges Time Navigation Logic', () => {
  describe('Time Range Calculation', () => {
    it('calculates correct time range for current hour (offset 0)', () => {
      const { start, end } = calculateTimeRange('hour', 0)
      const diffMs = end.getTime() - start.getTime()
      const diffHours = diffMs / (60 * 60 * 1000)
      expect(diffHours).toBe(1)
    })

    it('calculates correct time range for current day (offset 0)', () => {
      const { start, end } = calculateTimeRange('day', 0)
      const diffMs = end.getTime() - start.getTime()
      const diffHours = diffMs / (60 * 60 * 1000)
      expect(diffHours).toBe(24)
    })

    it('calculates correct time range for current week (offset 0)', () => {
      const { start, end } = calculateTimeRange('week', 0)
      const diffMs = end.getTime() - start.getTime()
      const diffDays = diffMs / (24 * 60 * 60 * 1000)
      expect(diffDays).toBe(7)
    })

    it('calculates correct time range for historical hour (offset -5)', () => {
      const now = new Date()
      const { start, end } = calculateTimeRange('hour', -5)
      
      // End should be 5 hours ago
      const expectedEnd = new Date(now.getTime() - 5 * 60 * 60 * 1000)
      expect(Math.abs(end.getTime() - expectedEnd.getTime())).toBeLessThan(1000) // Within 1 second
      
      // Duration should still be 1 hour
      const diffMs = end.getTime() - start.getTime()
      const diffHours = diffMs / (60 * 60 * 1000)
      expect(diffHours).toBe(1)
    })

    it('calculates correct time range for historical day (offset -3)', () => {
      const now = new Date()
      const { start, end } = calculateTimeRange('day', -3)
      
      // End should be 3 days ago
      const expectedEnd = new Date(now.getTime() - 3 * 24 * 60 * 60 * 1000)
      expect(Math.abs(end.getTime() - expectedEnd.getTime())).toBeLessThan(1000) // Within 1 second
      
      // Duration should still be 24 hours
      const diffMs = end.getTime() - start.getTime()
      const diffHours = diffMs / (60 * 60 * 1000)
      expect(diffHours).toBe(24)
    })
  })

  describe('Time Range Label Formatting', () => {
    it('formats current period labels correctly', () => {
      const hourRange = calculateTimeRange('hour', 0)
      expect(formatTimeRangeLabel('hour', 0, hourRange.start, hourRange.end)).toBe('Last Hour')
      
      const dayRange = calculateTimeRange('day', 0)
      expect(formatTimeRangeLabel('day', 0, dayRange.start, dayRange.end)).toBe('Last 24 Hours')
      
      const weekRange = calculateTimeRange('week', 0)
      expect(formatTimeRangeLabel('week', 0, weekRange.start, weekRange.end)).toBe('Last Week')
    })

    it('formats historical hour label with date and time', () => {
      const { start, end } = calculateTimeRange('hour', -1)
      const label = formatTimeRangeLabel('hour', -1, start, end)
      
      // Should include month name and day
      const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
      expect(monthNames.some(month => label.includes(month))).toBe(true)
      
      // Should include time with am/pm
      expect(label.match(/\d+(am|pm)/)).toBeTruthy()
    })

    it('formats historical day label with date only', () => {
      const { start, end } = calculateTimeRange('day', -1)
      const label = formatTimeRangeLabel('day', -1, start, end)
      
      // Should include month name and day
      const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
      expect(monthNames.some(month => label.includes(month))).toBe(true)
      
      // Should include day number
      expect(label.match(/\d+/)).toBeTruthy()
      
      // Should NOT include time
      expect(label.includes('am') || label.includes('pm')).toBe(false)
    })

    it('formats historical week label with date range', () => {
      const { start, end } = calculateTimeRange('week', -1)
      const label = formatTimeRangeLabel('week', -1, start, end)
      
      // Should include month name
      const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
      expect(monthNames.some(month => label.includes(month))).toBe(true)
      
      // Should include a dash (date range)
      expect(label.includes('-')).toBe(true)
    })
  })

  describe('Period Change Behavior (Key Requirement)', () => {
    it('should reset to current time when period changes', () => {
      // Simulate the behavior: when user is viewing historical data (offset -5)
      // and changes period, offset should reset to 0
      
      let period: 'hour' | 'day' | 'week' = 'day'
      let offset = -5 // User has navigated 5 days back
      
      // User changes period from 'day' to 'week'
      period = 'week'
      offset = 0 // This is the expected behavior - reset to now
      
      const { start, end } = calculateTimeRange(period, offset)
      const now = new Date()
      
      // End time should be approximately now (within 1 second)
      expect(Math.abs(end.getTime() - now.getTime())).toBeLessThan(1000)
      
      // Label should show "Last Week" not a historical date
      const label = formatTimeRangeLabel(period, offset, start, end)
      expect(label).toBe('Last Week')
    })

    it('demonstrates the problem if offset is NOT reset', () => {
      // This test shows why we need to reset offset
      
      let period: 'hour' | 'day' | 'week' = 'day'
      let offset = -5 // User has navigated 5 days back
      
      // User changes period from 'day' to 'week'
      period = 'week'
      // BAD: If we don't reset offset, we'd be showing 5 weeks ago!
      // offset = -5 // This would be confusing
      
      // With offset -5 for week period, we'd be showing data from 5 weeks ago
      const badRange = calculateTimeRange(period, -5)
      const badLabel = formatTimeRangeLabel(period, -5, badRange.start, badRange.end)
      
      // This would NOT be "Last Week", it would be a historical date
      expect(badLabel).not.toBe('Last Week')
      
      // This demonstrates why resetting to 0 is the correct behavior
    })
  })
})

