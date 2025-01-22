import { formatTimeAgo } from './format-time'

describe('formatTimeAgo', () => {
  it('never outputs "less than am ago"', () => {
    const now = new Date()
    const justNow = new Date(now.getTime() - 1000)  // 1 second ago
    const result = formatTimeAgo(justNow, true)
    expect(result).toBe('<1m ago')
    expect(result).not.toContain('less than am ago')
  })

  it('handles "less than a" cases correctly', () => {
    const now = new Date()
    const justNow = new Date(now.getTime() - 1000)  // 1 second ago
    expect(formatTimeAgo(justNow, true)).toBe('<1m ago')
    expect(formatTimeAgo(justNow, false)).toBe('less than a minute ago')
  })

  it('handles "less than X seconds ago"', () => {
    const now = new Date()
    const fiveSecondsAgo = new Date(now.getTime() - 5 * 1000)
    expect(formatTimeAgo(fiveSecondsAgo, true)).toBe('<1m ago')
  })

  it('handles times less than a minute ago', () => {
    const now = new Date()
    const thirtySecondsAgo = new Date(now.getTime() - 30 * 1000)
    expect(formatTimeAgo(thirtySecondsAgo, true)).toBe('<1m ago')
  })

  it('handles "half a minute ago"', () => {
    const now = new Date()
    const halfMinuteAgo = new Date(now.getTime() - 30 * 1000)
    expect(formatTimeAgo(halfMinuteAgo, true)).toBe('<1m ago')
  })

  it('handles "less than a minute ago"', () => {
    const now = new Date()
    const fortyFiveSecondsAgo = new Date(now.getTime() - 45 * 1000)
    expect(formatTimeAgo(fortyFiveSecondsAgo, true)).toBe('<1m ago')
  })

  it('handles exactly one minute ago', () => {
    const now = new Date()
    const oneMinuteAgo = new Date(now.getTime() - 60 * 1000)
    expect(formatTimeAgo(oneMinuteAgo, true)).toBe('1m ago')
  })

  it('handles multiple minutes ago', () => {
    const now = new Date()
    const fiveMinutesAgo = new Date(now.getTime() - 5 * 60 * 1000)
    expect(formatTimeAgo(fiveMinutesAgo, true)).toBe('5m ago')
  })
}) 