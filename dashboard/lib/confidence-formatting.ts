/**
 * Formats confidence scores with appropriate precision while never overstating predictions.
 *
 * Business rules:
 * - Never rounds to 100% (maximum is 99.9%)
 * - High confidence (90%+): Shows 0.1% precision (e.g., "95.7%", "90.0%")
 * - Lower confidence (<90%): Shows integer precision (e.g., "85%", "23%")
 *
 * @param confidence - Confidence value between 0 and 1
 * @returns Formatted percentage string
 */
export const formatConfidence = (confidence: number): string => {
  const percentage = confidence * 100

  // Never round to 100% - maximum is 99.9%
  if (percentage >= 99.95) {
    return '99.9%'
  }

  // For 90% and above, round to nearest 0.1%
  if (percentage >= 90) {
    const rounded = Math.round(percentage * 10) / 10
    // Always show one decimal place for 90% and above
    return `${rounded.toFixed(1)}%`
  }

  // Below 90%, round to nearest integer
  return `${Math.round(percentage)}%`
}

/**
 * Formats confidence scores for detailed view with high precision.
 *
 * Shows up to 10 decimal places for detailed analysis while still
 * never overstating predictions by rounding to 100%.
 *
 * @param confidence - Confidence value between 0 and 1
 * @returns Formatted percentage string with high precision
 */
export const formatConfidenceDetailed = (confidence: number): string => {
  const percentage = confidence * 100

  // Never round to 100% - cap at 99.9999999999% (10 decimal places)
  if (percentage >= 99.9999999999) {
    return '99.9999999999%'
  }

  // For detailed view, show up to 10 decimal places but remove trailing zeros
  const formatted = percentage.toFixed(10)
  const withoutTrailingZeros = parseFloat(formatted).toString()

  return `${withoutTrailingZeros}%`
}