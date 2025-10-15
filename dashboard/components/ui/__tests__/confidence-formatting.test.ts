/**
 * Critical tests for confidence formatting logic
 *
 * This ensures we never overstate predictions by rounding to 100%
 * and maintains appropriate precision levels.
 */

import { formatConfidence, formatConfidenceDetailed } from '@/lib/confidence-formatting'

describe('formatConfidence', () => {
  describe('Critical: Never rounds to 100%', () => {
    it('should cap extremely high confidence at 99.9%', () => {
      expect(formatConfidence(0.999999999)).toBe('99.9%')
      expect(formatConfidence(0.9999)).toBe('99.9%')
      expect(formatConfidence(0.99999)).toBe('99.9%')
      expect(formatConfidence(0.999999)).toBe('99.9%')
    })

    it('should never return 100% for any input', () => {
      // Test a range of very high values
      const highValues = [0.999, 0.9999, 0.99999, 0.999999, 0.9999999, 1.0]

      highValues.forEach(value => {
        const result = formatConfidence(value)
        expect(result).not.toBe('100%')
        expect(result).not.toBe('100.0%')
      })
    })
  })

  describe('High confidence (90%+): 0.1% precision', () => {
    it('should show one decimal place for 90% and above', () => {
      expect(formatConfidence(0.999)).toBe('99.9%')
      expect(formatConfidence(0.995)).toBe('99.5%')
      expect(formatConfidence(0.994)).toBe('99.4%')
      expect(formatConfidence(0.992)).toBe('99.2%')
      expect(formatConfidence(0.9567)).toBe('95.7%')
      expect(formatConfidence(0.9234)).toBe('92.3%')
      expect(formatConfidence(0.905)).toBe('90.5%')
      expect(formatConfidence(0.9)).toBe('90.0%')
    })

    it('should round to nearest 0.1% for 90%+ values', () => {
      expect(formatConfidence(0.9567)).toBe('95.7%') // 95.67% → 95.7%
      expect(formatConfidence(0.9234)).toBe('92.3%') // 92.34% → 92.3%
      expect(formatConfidence(0.9156)).toBe('91.6%') // 91.56% → 91.6%
      expect(formatConfidence(0.9123)).toBe('91.2%') // 91.23% → 91.2%
    })
  })

  describe('Lower confidence (<90%): Integer precision', () => {
    it('should round to integers for values below 90%', () => {
      expect(formatConfidence(0.896)).toBe('90%') // 89.6% → 90% (rounds up to cross 90% boundary)
      expect(formatConfidence(0.894)).toBe('89%') // 89.4% → 89%
      expect(formatConfidence(0.85)).toBe('85%')
      expect(formatConfidence(0.756)).toBe('76%') // 75.6% → 76%
      expect(formatConfidence(0.754)).toBe('75%') // 75.4% → 75%
      expect(formatConfidence(0.5)).toBe('50%')
      expect(formatConfidence(0.234)).toBe('23%') // 23.4% → 23%
      expect(formatConfidence(0.1)).toBe('10%')
    })

    it('should not show decimal places below 90%', () => {
      const results = [
        formatConfidence(0.85),
        formatConfidence(0.756),
        formatConfidence(0.5),
        formatConfidence(0.234),
        formatConfidence(0.1)
      ]

      results.forEach(result => {
        expect(result).not.toMatch(/\.\d%$/) // Should not end with .digit%
      })
    })
  })

  describe('Edge cases and boundary conditions', () => {
    it('should handle the 90% boundary correctly', () => {
      expect(formatConfidence(0.9)).toBe('90.0%')     // Exactly 90% - shows decimal
      expect(formatConfidence(0.8999)).toBe('90%')    // 89.99% rounds to 90% (integer)
      expect(formatConfidence(0.8944)).toBe('89%')    // 89.44% rounds to 89% (integer)
    })

    it('should handle very low confidence values', () => {
      expect(formatConfidence(0.01)).toBe('1%')
      expect(formatConfidence(0.005)).toBe('1%')  // 0.5% rounds to 1%
      expect(formatConfidence(0.004)).toBe('0%')  // 0.4% rounds to 0%
      expect(formatConfidence(0)).toBe('0%')
    })

    it('should handle the 99.95% boundary (never round to 100%)', () => {
      expect(formatConfidence(0.9995)).toBe('99.9%') // 99.95% → 99.9% (capped)
      expect(formatConfidence(0.9993)).toBe('99.9%') // 99.93% → 99.9% (normal rounding)
      expect(formatConfidence(0.9944)).toBe('99.4%') // 99.44% → 99.4% (normal rounding)
    })
  })

  describe('Business logic validation', () => {
    it('should provide appropriate precision for different confidence ranges', () => {
      // High confidence (90%+) needs more precision to distinguish between very confident predictions
      expect(formatConfidence(0.991)).toBe('99.1%')
      expect(formatConfidence(0.992)).toBe('99.2%')

      // Lower confidence (<90%) uses integers to avoid false precision
      expect(formatConfidence(0.851)).toBe('85%')
      expect(formatConfidence(0.859)).toBe('86%')
    })

    it('should never overstate model confidence', () => {
      // This is the critical business requirement
      const veryHighConfidenceValues = [0.999, 0.9999, 0.99999, 1.0]

      veryHighConfidenceValues.forEach(value => {
        const result = formatConfidence(value)
        const numericResult = parseFloat(result.replace('%', ''))
        expect(numericResult).toBeLessThan(100)
      })
    })
  })
})

describe('formatConfidenceDetailed', () => {
  describe('High precision display', () => {
    it('should show high precision for very close to 100% values', () => {
      expect(formatConfidenceDetailed(0.999999999)).toBe('99.9999999%')
      expect(formatConfidenceDetailed(0.9999999999)).toBe('99.99999999%') // Close to the cap (JS precision)
      expect(formatConfidenceDetailed(0.99999999999)).toBe('99.999999999%') // Over the cap, should be capped (JS precision)
    })

    it('should show full precision with trailing zeros removed', () => {
      expect(formatConfidenceDetailed(0.85)).toBe('85%') // No decimals needed
      expect(formatConfidenceDetailed(0.855)).toBe('85.5%') // One decimal
      expect(formatConfidenceDetailed(0.8555555555)).toBe('85.55555555%') // Multiple decimals
      expect(formatConfidenceDetailed(0.999999582722756)).toBe('99.9999582723%') // Real-world example (with JS precision)
    })

    it('should never round to 100%', () => {
      const veryHighValues = [0.999999999, 0.9999999999, 0.99999999999, 1.0]

      veryHighValues.forEach(value => {
        const result = formatConfidenceDetailed(value)
        expect(result).not.toBe('100%')
        expect(result).not.toMatch(/^100\.0+%$/) // Not 100.000...%

        const numericResult = parseFloat(result.replace('%', ''))
        expect(numericResult).toBeLessThan(100)
      })
    })

    it('should handle edge cases properly', () => {
      expect(formatConfidenceDetailed(0)).toBe('0%')
      expect(formatConfidenceDetailed(0.1)).toBe('10%')
      expect(formatConfidenceDetailed(0.5)).toBe('50%')
      expect(formatConfidenceDetailed(0.123456789)).toBe('12.3456789%')
    })
  })

  describe('Comparison with regular formatting', () => {
    it('should show more detail than regular formatting for high precision values', () => {
      const testValue = 0.999999582722756

      const regular = formatConfidence(testValue)
      const detailed = formatConfidenceDetailed(testValue)

      expect(regular).toBe('99.9%') // Rounded to 0.1%
      expect(detailed).toBe('99.9999582723%') // Full precision (with JS precision limits)

      expect(detailed.length).toBeGreaterThan(regular.length)
    })

    it('should be identical for simple values', () => {
      const simpleValues = [0, 0.1, 0.5, 0.85]

      simpleValues.forEach(value => {
        const regular = formatConfidence(value)
        const detailed = formatConfidenceDetailed(value)
        expect(detailed).toBe(regular)
      })
    })
  })
})