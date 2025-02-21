import { formatTimeAgo } from './format-time'

describe('formatTimeAgo', () => {
  it('handles invalid date strings', () => {
    expect(formatTimeAgo('invalid-date')).toBe('Invalid date')
  })

  it('handles invalid Date objects', () => {
    expect(formatTimeAgo(new Date('invalid'))).toBe('Invalid date')
  })

  it('handles string timestamps', () => {
    const validDate = new Date().toISOString()
    expect(formatTimeAgo(validDate)).not.toBe('Invalid date')
  })
}) 