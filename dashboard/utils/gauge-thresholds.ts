/**
 * GaugeThresholdComputer sets color-band breakpoints for a raw-accuracy gauge.
 * Bands are derived from the dataset's empirical chance accuracy (Σ pᵢ²).
 */
export class GaugeThresholdComputer {
  /**
   * Computes gauge thresholds based on label distribution
   * 
   * @param labelCounts Object with labels as keys and counts as values
   * @returns Object containing threshold values (as percentages 0-100)
   */
  static computeThresholds(
    labelCounts: Record<string, number>
  ) {
    // Handle edge cases
    if (!labelCounts || Object.keys(labelCounts).length === 0) {
      return {
        chance: 50, // Default for unknown distribution
        okayThreshold: 70, // 50 + 20
        goodThreshold: 80, // 50 + 30
        greatThreshold: 90, // 50 + 40
        perfectThreshold: 95 // 50 + 45
      };
    }

    const total = Object.values(labelCounts).reduce((a, b) => a + b, 0);
    
    // Another edge case - if total is 0, return defaults
    if (total <= 0) {
      return {
        chance: 50,
        okayThreshold: 70,
        goodThreshold: 80,
        greatThreshold: 90,
        perfectThreshold: 95
      };
    }

    const probabilities = Object.values(labelCounts).map(c => c / total);
    
    // Calculate chance accuracy as sum of squared probabilities
    const chance = probabilities.reduce((sum, p) => sum + p * p, 0);
    
    // Calculate thresholds with increasing deltas from chance
    const okayDelta = 0.20; // 20%
    const goodDelta = 0.30; // 30%
    const greatDelta = 0.40; // 40%
    const perfectDelta = 0.45; // 45%
    
    const okayThreshold = Math.min(chance + okayDelta, 0.99);
    const goodThreshold = Math.min(chance + goodDelta, 0.995);
    const greatThreshold = Math.min(chance + greatDelta, 0.998);
    const perfectThreshold = Math.min(chance + perfectDelta, 0.999);

    return {
      chance: chance * 100,
      okayThreshold: okayThreshold * 100,
      goodThreshold: goodThreshold * 100,
      greatThreshold: greatThreshold * 100,
      perfectThreshold: perfectThreshold * 100
    };
  }
  
  /**
   * Creates gauge segments based on computed thresholds
   * 
   * @param thresholds Object with threshold values from computeThresholds
   * @returns Array of segment objects for the Gauge component
   */
  static createSegments(thresholds: { 
    chance: number; 
    okayThreshold: number;
    goodThreshold: number;
    greatThreshold: number;
    perfectThreshold: number;
  }) {
    return [
      { start: 0, end: thresholds.chance, color: 'var(--gauge-inviable)' }, // Below chance (poor)
      { start: thresholds.chance, end: thresholds.okayThreshold, color: 'var(--gauge-converging)' }, // Okay (slightly above chance)
      { start: thresholds.okayThreshold, end: thresholds.goodThreshold, color: 'var(--gauge-almost)' }, // Good
      { start: thresholds.goodThreshold, end: thresholds.greatThreshold, color: 'var(--gauge-viable)' }, // Great
      { start: thresholds.greatThreshold, end: 100, color: 'var(--gauge-great)' } // Perfect
    ];
  }
} 