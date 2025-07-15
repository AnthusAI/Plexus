/**
 * Feedback Analysis Utility Functions
 * 
 * This file contains TypeScript implementations of statistical analysis functions
 * for feedback data, including GWETS AC1 agreement coefficients, accuracy metrics,
 * and confusion matrix calculations.
 */

export interface FeedbackItem {
  id: string;
  itemId: string;
  scoreId: string;
  initialValue: string | null;
  finalValue: string | null;
  editedAt: string;
  createdAt: string;
  scoreName?: string;
  item?: {
    id: string;
    externalId?: string;
    description?: string;
  };
}

export interface AnalysisResult {
  accuracy: number;
  totalItems: number;
  totalAgreements: number;
  totalMismatches: number;
  ac1: number | null;
  confusionMatrix: ConfusionMatrixResult;
  labelDistribution: Record<string, number>;
  predictedLabelDistribution: Record<string, number>;
}

export interface ConfusionMatrixResult {
  labels: string[];
  matrix: Array<{
    actualClassLabel: string;
    predictedClassCounts: Record<string, number>;
  }>;
}

export interface ScoreAnalysisResult extends AnalysisResult {
  scoreId: string;
  scoreName: string;
  warning?: string;
  notes?: string;
  discussion?: string;
}

/**
 * Calculate accuracy as percentage of correct predictions
 */
export function calculateAccuracy(agreements: number, totalItems: number): number {
  if (totalItems === 0) return 100.0;
  return (agreements / totalItems) * 100;
}

/**
 * Calculate Gwet's AC1 agreement coefficient
 * 
 * AC1 = (Po - Pe) / (1 - Pe)
 * where Po = observed agreement, Pe = expected agreement by chance
 * 
 * @param observedAgreement - Proportion of observed agreement (0-1)
 * @param labelDistribution - Distribution of labels in the dataset
 * @returns AC1 coefficient (-1 to 1, where 1 is perfect agreement)
 */
export function calculateGwetAC1(
  observedAgreement: number,
  labelDistribution: Record<string, number>
): number | null {
  if (Object.keys(labelDistribution).length === 0) return null;
  
  const totalItems = Object.values(labelDistribution).reduce((sum, count) => sum + count, 0);
  if (totalItems === 0) return null;
  
  // Calculate expected agreement by chance (Pe) using Gwet's formula
  // Pe = sum(π_i * (1 - π_i)) / (k - 1)
  // Where π_i is the marginal probability for category i, k is number of categories
  const categories = Object.keys(labelDistribution);
  const numCategories = categories.length;
  
  if (numCategories <= 1) return 1.0; // Perfect agreement - only one category exists
  
  const expectedAgreement = Object.values(labelDistribution).reduce((sum, count) => {
    const probability = count / totalItems;
    return sum + (probability * (1 - probability));
  }, 0) / (numCategories - 1);
  
  // AC1 = (Po - Pe) / (1 - Pe)
  if (expectedAgreement >= 1) return null; // Avoid division by zero
  
  const ac1 = (observedAgreement - expectedAgreement) / (1 - expectedAgreement);
  return Math.max(-1, Math.min(1, ac1)); // Clamp to [-1, 1] range
}

/**
 * Create a confusion matrix from feedback items
 */
export function createConfusionMatrix(feedbackItems: FeedbackItem[]): ConfusionMatrixResult {
  // Get all unique labels from both initial and final values
  const allLabels = new Set<string>();
  const validItems = feedbackItems.filter(item => 
    item.initialValue !== null && item.finalValue !== null
  );
  
  validItems.forEach(item => {
    if (item.initialValue) allLabels.add(item.initialValue);
    if (item.finalValue) allLabels.add(item.finalValue);
  });
  
  const labels = Array.from(allLabels).sort();
  
  // Initialize matrix
  const matrix = labels.map(actualLabel => ({
    actualClassLabel: actualLabel,
    predictedClassCounts: Object.fromEntries(labels.map(label => [label, 0]))
  }));
  
  // Populate matrix
  validItems.forEach(item => {
    const predicted = item.initialValue!;
    const actual = item.finalValue!;
    
    const actualRow = matrix.find(row => row.actualClassLabel === actual);
    if (actualRow) {
      actualRow.predictedClassCounts[predicted] = (actualRow.predictedClassCounts[predicted] || 0) + 1;
    }
  });
  
  return { labels, matrix };
}

/**
 * Calculate label distributions from feedback items
 */
export function calculateLabelDistributions(feedbackItems: FeedbackItem[]): {
  labelDistribution: Record<string, number>;
  predictedLabelDistribution: Record<string, number>;
} {
  const labelDistribution: Record<string, number> = {};
  const predictedLabelDistribution: Record<string, number> = {};
  
  feedbackItems.forEach(item => {
    // Actual values (final values)
    if (item.finalValue) {
      labelDistribution[item.finalValue] = (labelDistribution[item.finalValue] || 0) + 1;
    }
    
    // Predicted values (initial values)
    if (item.initialValue) {
      predictedLabelDistribution[item.initialValue] = (predictedLabelDistribution[item.initialValue] || 0) + 1;
    }
  });
  
  return { labelDistribution, predictedLabelDistribution };
}

/**
 * Analyze feedback items for a single score
 */
export function analyzeFeedbackForScore(
  feedbackItems: FeedbackItem[],
  scoreId: string,
  scoreName: string
): ScoreAnalysisResult {
  // Filter items for this score
  const scoreItems = feedbackItems.filter(item => item.scoreId === scoreId);
  
  // Filter out items with null values
  const validItems = scoreItems.filter(item => 
    item.initialValue !== null && item.finalValue !== null
  );
  
  if (validItems.length === 0) {
    return {
      scoreId,
      scoreName,
      accuracy: 0,
      totalItems: 0,
      totalAgreements: 0,
      totalMismatches: 0,
      ac1: null,
      confusionMatrix: { labels: [], matrix: [] },
      labelDistribution: {},
      predictedLabelDistribution: {}
    };
  }
  
  // Calculate agreements and mismatches
  const agreements = validItems.filter(item => item.initialValue === item.finalValue).length;
  const mismatches = validItems.length - agreements;
  
  // Calculate accuracy
  const accuracy = calculateAccuracy(agreements, validItems.length);
  
  // Calculate label distributions
  const { labelDistribution, predictedLabelDistribution } = calculateLabelDistributions(validItems);
  
  // Calculate AC1 using combined label distribution (both initial and final values)
  // This matches the Python implementation which combines both rater distributions
  const combinedLabelDistribution: Record<string, number> = {};
  validItems.forEach(item => {
    // Add both initial and final values to get the overall marginal distribution
    if (item.initialValue) {
      combinedLabelDistribution[item.initialValue] = (combinedLabelDistribution[item.initialValue] || 0) + 1;
    }
    if (item.finalValue) {
      combinedLabelDistribution[item.finalValue] = (combinedLabelDistribution[item.finalValue] || 0) + 1;
    }
  });
  
  const observedAgreement = agreements / validItems.length;
  const ac1 = calculateGwetAC1(observedAgreement, combinedLabelDistribution);
  
  // Create confusion matrix
  const confusionMatrix = createConfusionMatrix(validItems);
  
  // Generate warnings for low agreement
  let warning: string | undefined;
  if (validItems.length < 20) {
    warning = `Insufficient data: Only ${validItems.length} samples available. Results may not be statistically significant.`;
  } else if (ac1 !== null && ac1 < 0.4) {
    warning = `Critical reliability concern: AC1 score below acceptable threshold (0.4). This indicates poor inter-rater reliability.`;
  } else if (ac1 !== null && ac1 < 0.6) {
    warning = `Low agreement score detected. This suggests inconsistent scoring between raters.`;
  }
  
  return {
    scoreId,
    scoreName,
    accuracy,
    totalItems: validItems.length,
    totalAgreements: agreements,
    totalMismatches: mismatches,
    ac1,
    confusionMatrix,
    labelDistribution,
    predictedLabelDistribution,
    warning
  };
}

/**
 * Analyze feedback items for multiple scores (scorecard-level analysis)
 */
export function analyzeFeedbackForScorecard(
  feedbackItems: FeedbackItem[],
  scoreIds?: string[]
): {
  scores: ScoreAnalysisResult[];
  overall: AnalysisResult;
} {
  // Group items by score
  const itemsByScore = new Map<string, FeedbackItem[]>();
  feedbackItems.forEach(item => {
    if (!scoreIds || scoreIds.includes(item.scoreId)) {
      if (!itemsByScore.has(item.scoreId)) {
        itemsByScore.set(item.scoreId, []);
      }
      itemsByScore.get(item.scoreId)!.push(item);
    }
  });
  
  // Analyze each score
  const scores = Array.from(itemsByScore.entries()).map(([scoreId, items]) => {
    const scoreName = items[0]?.scoreName || `Score ${scoreId}`;
    return analyzeFeedbackForScore(items, scoreId, scoreName);
  });
  
  // Calculate overall statistics directly from valid items
  const validItems = feedbackItems.filter(item => 
    item.initialValue !== null && item.finalValue !== null &&
    (!scoreIds || scoreIds.includes(item.scoreId))
  );
  
  // Calculate agreements directly from the filtered items to avoid double-counting
  const totalAgreements = validItems.filter(item => item.initialValue === item.finalValue).length;
  const totalItems = validItems.length;
  const totalMismatches = totalItems - totalAgreements;
  
  const overallAccuracy = calculateAccuracy(totalAgreements, totalItems);
  
  // Calculate overall label distribution
  const { labelDistribution, predictedLabelDistribution } = calculateLabelDistributions(validItems);
  
  // Calculate overall AC1 using combined label distribution (both initial and final values)
  // This matches the fix applied to per-score analysis
  const combinedLabelDistribution: Record<string, number> = {};
  validItems.forEach(item => {
    // Add both initial and final values to get the overall marginal distribution
    if (item.initialValue) {
      combinedLabelDistribution[item.initialValue] = (combinedLabelDistribution[item.initialValue] || 0) + 1;
    }
    if (item.finalValue) {
      combinedLabelDistribution[item.finalValue] = (combinedLabelDistribution[item.finalValue] || 0) + 1;
    }
  });
  
  const observedAgreement = totalItems > 0 ? totalAgreements / totalItems : 0;
  const overallAC1 = calculateGwetAC1(observedAgreement, combinedLabelDistribution);
  
  // Create overall confusion matrix
  const overallConfusionMatrix = createConfusionMatrix(validItems);
  
  return {
    scores,
    overall: {
      accuracy: overallAccuracy,
      totalItems,
      totalAgreements,
      totalMismatches,
      ac1: overallAC1,
      confusionMatrix: overallConfusionMatrix,
      labelDistribution,
      predictedLabelDistribution
    }
  };
}

/**
 * Filter feedback items by date range
 */
export function filterFeedbackByDateRange(
  feedbackItems: FeedbackItem[],
  startDate: Date,
  endDate: Date
): FeedbackItem[] {
  return feedbackItems.filter(item => {
    const itemDate = new Date(item.editedAt || item.createdAt);
    return itemDate >= startDate && itemDate <= endDate;
  });
}

/**
 * Convert analysis results to the format expected by existing components
 */
export function convertToScorecardReportFormat(
  analysis: { scores: ScoreAnalysisResult[]; overall: AnalysisResult },
  dateRange: { start: string; end: string }
) {
  return {
    scores: analysis.scores.map(score => ({
      id: score.scoreId,
      score_name: score.scoreName,
      question: score.scoreName,
      cc_question_id: `ext-${score.scoreId}`,
      ac1: score.ac1,
      item_count: score.totalItems,
      mismatches: score.totalMismatches,
      accuracy: score.accuracy,
      label_distribution: score.labelDistribution,
      class_distribution: Object.entries(score.labelDistribution).map(([label, count]) => ({
        label,
        count
      })),
      predicted_class_distribution: Object.entries(score.predictedLabelDistribution).map(([label, count]) => ({
        label,
        count
      })),
      confusion_matrix: score.confusionMatrix,
      warning: score.warning,
      notes: score.notes,
      discussion: score.discussion
    })),
    total_items: analysis.overall.totalItems,
    total_agreements: analysis.overall.totalAgreements,
    total_mismatches: analysis.overall.totalMismatches,
    accuracy: analysis.overall.accuracy,
    overall_ac1: analysis.overall.ac1,
    date_range: dateRange,
    label_distribution: analysis.overall.labelDistribution
  };
}