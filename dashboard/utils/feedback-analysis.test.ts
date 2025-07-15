/**
 * Tests for Feedback Analysis Utility Functions
 */

import {
  calculateAccuracy,
  calculateGwetAC1,
  createConfusionMatrix,
  calculateLabelDistributions,
  analyzeFeedbackForScore,
  analyzeFeedbackForScorecard,
  filterFeedbackByDateRange,
  convertToScorecardReportFormat,
  type FeedbackItem
} from './feedback-analysis';

// Mock data for testing
const createMockFeedbackItem = (
  id: string,
  scoreId: string,
  initialValue: string | null,
  finalValue: string | null,
  scoreName: string = 'Test Score',
  editedAt: string = '2023-01-01T00:00:00Z'
): FeedbackItem => ({
  id,
  itemId: `item-${id}`,
  scoreId,
  initialValue,
  finalValue,
  editedAt,
  createdAt: editedAt,
  scoreName,
  item: {
    id: `item-${id}`,
    externalId: `ext-${id}`,
    description: `Test item ${id}`
  }
});

describe('calculateAccuracy', () => {
  test('calculates accuracy correctly', () => {
    expect(calculateAccuracy(8, 10)).toBe(80);
    expect(calculateAccuracy(10, 10)).toBe(100);
    expect(calculateAccuracy(0, 10)).toBe(0);
  });

  test('handles edge cases', () => {
    expect(calculateAccuracy(0, 0)).toBe(100); // No items = 100% accuracy
    expect(calculateAccuracy(5, 5)).toBe(100);
  });
});

describe('calculateGwetAC1', () => {
  test('calculates AC1 for binary classification', () => {
    // Perfect agreement (Po = 1.0)
    const labelDistribution = { 'Yes': 5, 'No': 5 };
    const ac1 = calculateGwetAC1(1.0, labelDistribution);
    expect(ac1).toBe(1.0);
  });

  test('calculates AC1 for chance-level agreement', () => {
    // Balanced binary case: Pe = 0.5^2 + 0.5^2 = 0.5
    // If Po = 0.5 (chance level), AC1 should be 0
    const labelDistribution = { 'Yes': 50, 'No': 50 };
    const ac1 = calculateGwetAC1(0.5, labelDistribution);
    expect(ac1).toBeCloseTo(0.0, 5);
  });

  test('calculates AC1 for imbalanced classes', () => {
    // Imbalanced case: 95% Yes, 5% No
    // Using Gwet's formula: Pe = (π₁*(1-π₁) + π₂*(1-π₂)) / (k-1)
    // π₁ = 0.95, π₂ = 0.05, k = 2
    // Pe = (0.95*0.05 + 0.05*0.95) / (2-1) = (0.0475 + 0.0475) / 1 = 0.095
    const labelDistribution = { 'Yes': 95, 'No': 5 };
    const observedAgreement = 0.90; // 90% accuracy
    const expectedPe = 0.095;
    const expectedAC1 = (0.90 - expectedPe) / (1 - expectedPe);
    
    const ac1 = calculateGwetAC1(observedAgreement, labelDistribution);
    expect(ac1).toBeCloseTo(expectedAC1, 3);
  });

  test('handles three-class case', () => {
    // Three roughly equal classes: A=33%, B=33%, C=34%
    // Using Gwet's formula: Pe = (π₁*(1-π₁) + π₂*(1-π₂) + π₃*(1-π₃)) / (k-1)
    // π₁ = 0.33, π₂ = 0.33, π₃ = 0.34, k = 3
    // Pe = (0.33*0.67 + 0.33*0.67 + 0.34*0.66) / (3-1) = (0.2211 + 0.2211 + 0.2244) / 2 = 0.3333
    const labelDistribution = { 'A': 33, 'B': 33, 'C': 34 };
    const observedAgreement = 0.65;
    const expectedPe = 0.3333;
    const expectedAC1 = (0.65 - expectedPe) / (1 - expectedPe);
    
    const ac1 = calculateGwetAC1(observedAgreement, labelDistribution);
    expect(ac1).toBeCloseTo(expectedAC1, 3);
  });

  test('handles edge cases', () => {
    expect(calculateGwetAC1(0.5, {})).toBeNull(); // Empty distribution
    expect(calculateGwetAC1(0.5, { 'A': 0 })).toBeNull(); // Zero total
    
    // All items in one category - perfect agreement should return AC1 = 1.0
    expect(calculateGwetAC1(1.0, { 'A': 100 })).toBe(1.0);
  });

  test('clamps values to [-1, 1] range', () => {
    const labelDistribution = { 'A': 50, 'B': 50 };
    
    // Test lower bound
    const lowAC1 = calculateGwetAC1(0.0, labelDistribution); // Very poor agreement
    expect(lowAC1).toBeGreaterThanOrEqual(-1);
    
    // Test upper bound
    const highAC1 = calculateGwetAC1(1.0, labelDistribution); // Perfect agreement
    expect(highAC1).toBeLessThanOrEqual(1);
  });

  test('matches Python implementation results', () => {
    // Test case that should produce identical results to Python gwet_ac1.py
    // Binary case: 80% Yes, 20% No with 85% observed agreement
    const labelDistribution = { 'Yes': 80, 'No': 20 };
    const observedAgreement = 0.85;
    
    // Manual calculation using Gwet's formula:
    // π₁ = 0.8, π₂ = 0.2, k = 2
    // Pe = (0.8 * 0.2 + 0.2 * 0.8) / (2 - 1) = (0.16 + 0.16) / 1 = 0.32
    // AC1 = (0.85 - 0.32) / (1 - 0.32) = 0.53 / 0.68 = 0.7794117647
    const expectedAC1 = 0.7794117647;
    
    const ac1 = calculateGwetAC1(observedAgreement, labelDistribution);
    expect(ac1).toBeCloseTo(expectedAC1, 6); // High precision match
  });

  test('matches real-world Medication Review data', () => {
    // Test case based on actual "Medication Review" feedback data
    // 50 items: 44 agreements, 6 disagreements
    // Initial: 1 Yes, 49 No
    // Final: 5 Yes, 45 No
    // Combined distribution: 6 Yes, 94 No (total 100)
    const combinedLabelDistribution = { 'Yes': 6, 'No': 94 };
    const observedAgreement = 44 / 50; // 0.88
    
    // Manual calculation:
    // π₁ = 6/100 = 0.06, π₂ = 94/100 = 0.94, k = 2
    // Pe = (0.06 * 0.94 + 0.94 * 0.06) / (2 - 1) = (0.0564 + 0.0564) / 1 = 0.1128
    // AC1 = (0.88 - 0.1128) / (1 - 0.1128) = 0.7672 / 0.8872 = 0.8647430117
    const expectedAC1 = 0.8647430117;
    
    const ac1 = calculateGwetAC1(observedAgreement, combinedLabelDistribution);
    expect(ac1).toBeCloseTo(expectedAC1, 6); // Should match Python result of ~0.86
  });

  test('handles perfect agreement (single category)', () => {
    // Test case for "Shipping Address" scenario - all items are "Yes"
    // This should return AC1 = 1.0, not null
    const singleCategoryDistribution = { 'Yes': 26 }; // 13 initial + 13 final, all "Yes"
    const observedAgreement = 1.0; // Perfect agreement
    
    const ac1 = calculateGwetAC1(observedAgreement, singleCategoryDistribution);
    expect(ac1).toBe(1.0); // Should match Python result of 1.0
  });
});

describe('createConfusionMatrix', () => {
  test('creates confusion matrix for binary classification', () => {
    const feedbackItems = [
      createMockFeedbackItem('1', 'score1', 'Yes', 'Yes'),
      createMockFeedbackItem('2', 'score1', 'Yes', 'No'),
      createMockFeedbackItem('3', 'score1', 'No', 'No'),
      createMockFeedbackItem('4', 'score1', 'No', 'Yes'),
    ];

    const matrix = createConfusionMatrix(feedbackItems);
    
    expect(matrix.labels).toEqual(['No', 'Yes']); // Sorted alphabetically
    expect(matrix.matrix).toHaveLength(2);
    
    // Find the "Yes" actual row
    const yesRow = matrix.matrix.find(row => row.actualClassLabel === 'Yes');
    expect(yesRow?.predictedClassCounts).toEqual({ 'No': 1, 'Yes': 1 });
    
    // Find the "No" actual row  
    const noRow = matrix.matrix.find(row => row.actualClassLabel === 'No');
    expect(noRow?.predictedClassCounts).toEqual({ 'No': 1, 'Yes': 1 });
  });

  test('handles empty input', () => {
    const matrix = createConfusionMatrix([]);
    expect(matrix.labels).toEqual([]);
    expect(matrix.matrix).toEqual([]);
  });

  test('filters out items with null values', () => {
    const feedbackItems = [
      createMockFeedbackItem('1', 'score1', 'Yes', 'Yes'),
      createMockFeedbackItem('2', 'score1', null, 'No'),
      createMockFeedbackItem('3', 'score1', 'No', null),
    ];

    const matrix = createConfusionMatrix(feedbackItems);
    
    expect(matrix.labels).toEqual(['Yes']);
    expect(matrix.matrix).toHaveLength(1);
    expect(matrix.matrix[0].predictedClassCounts).toEqual({ 'Yes': 1 });
  });
});

describe('calculateLabelDistributions', () => {
  test('calculates distributions correctly', () => {
    const feedbackItems = [
      createMockFeedbackItem('1', 'score1', 'Yes', 'No'),
      createMockFeedbackItem('2', 'score1', 'Yes', 'Yes'),
      createMockFeedbackItem('3', 'score1', 'No', 'Yes'),
    ];

    const { labelDistribution, predictedLabelDistribution } = calculateLabelDistributions(feedbackItems);
    
    expect(labelDistribution).toEqual({ 'No': 1, 'Yes': 2 }); // Final values
    expect(predictedLabelDistribution).toEqual({ 'Yes': 2, 'No': 1 }); // Initial values
  });

  test('handles null values', () => {
    const feedbackItems = [
      createMockFeedbackItem('1', 'score1', 'Yes', null),
      createMockFeedbackItem('2', 'score1', null, 'Yes'),
    ];

    const { labelDistribution, predictedLabelDistribution } = calculateLabelDistributions(feedbackItems);
    
    expect(labelDistribution).toEqual({ 'Yes': 1 });
    expect(predictedLabelDistribution).toEqual({ 'Yes': 1 });
  });
});

describe('analyzeFeedbackForScore', () => {
  test('analyzes feedback for a single score', () => {
    const feedbackItems = [
      createMockFeedbackItem('1', 'score1', 'Yes', 'Yes', 'Test Score'), // Agreement
      createMockFeedbackItem('2', 'score1', 'Yes', 'No', 'Test Score'),  // Mismatch
      createMockFeedbackItem('3', 'score1', 'No', 'No', 'Test Score'),   // Agreement
      createMockFeedbackItem('4', 'score2', 'Yes', 'No', 'Other Score'), // Different score
    ];

    const result = analyzeFeedbackForScore(feedbackItems, 'score1', 'Test Score');
    
    expect(result.scoreId).toBe('score1');
    expect(result.scoreName).toBe('Test Score');
    expect(result.totalItems).toBe(3);
    expect(result.totalAgreements).toBe(2);
    expect(result.totalMismatches).toBe(1);
    expect(result.accuracy).toBeCloseTo(66.67, 1);
    expect(result.ac1).toBeGreaterThan(0); // Should have positive AC1
  });

  test('handles insufficient data warning', () => {
    const feedbackItems = [
      createMockFeedbackItem('1', 'score1', 'Yes', 'Yes', 'Test Score'),
    ];

    const result = analyzeFeedbackForScore(feedbackItems, 'score1', 'Test Score');
    
    expect(result.warning).toContain('Insufficient data');
    expect(result.totalItems).toBe(1);
  });

  test('handles low AC1 warning', () => {
    // Create a scenario with very poor agreement
    const feedbackItems = Array.from({ length: 25 }, (_, i) => 
      createMockFeedbackItem(
        `${i}`, 
        'score1', 
        i % 2 === 0 ? 'Yes' : 'No',
        i % 3 === 0 ? 'Yes' : 'No', // Different pattern for poor agreement
        'Test Score'
      )
    );

    const result = analyzeFeedbackForScore(feedbackItems, 'score1', 'Test Score');
    
    if (result.ac1 !== null && result.ac1 < 0.4) {
      expect(result.warning).toContain('Critical reliability concern');
    }
  });

  test('handles empty score data', () => {
    const result = analyzeFeedbackForScore([], 'score1', 'Test Score');
    
    expect(result.totalItems).toBe(0);
    expect(result.accuracy).toBe(0);
    expect(result.ac1).toBeNull();
    expect(result.confusionMatrix.labels).toEqual([]);
  });

  test('matches Python AC1 calculation with real Medication Review data', () => {
    // Simulated real-world Medication Review feedback items
    const realWorldFeedbackItems: FeedbackItem[] = [
      // 44 items where initial === final (agreements)
      ...Array(40).fill(null).map((_, i) => ({
        itemId: `item-agree-${i}`,
        initialValue: 'No',
        finalValue: 'No',
        scoreId: 'medication-review',
        editComment: 'agree'
      })),
      // 1 item: Yes -> No (disagreement)
      {
        itemId: 'item-yes-to-no',
        initialValue: 'Yes',
        finalValue: 'No',
        scoreId: 'medication-review',
        editComment: 'Agent did not verify dosage for a few medications'
      },
      // 5 items: No -> Yes (disagreements)
      ...Array(5).fill(null).map((_, i) => ({
        itemId: `item-no-to-yes-${i}`,
        initialValue: 'No',
        finalValue: 'Yes',
        scoreId: 'medication-review',
        editComment: 'Agent did verify medication details'
      })),
      // 4 more agreements
      ...Array(4).fill(null).map((_, i) => ({
        itemId: `item-agree-more-${i}`,
        initialValue: 'No',
        finalValue: 'No',
        scoreId: 'medication-review',
        editComment: 'agree'
      }))
    ];

    const result = analyzeFeedbackForScore(realWorldFeedbackItems, 'medication-review', 'Medication Review');
    
    expect(result.totalItems).toBe(50);
    expect(result.totalAgreements).toBe(44);
    expect(result.accuracy).toBeCloseTo(88, 1); // 88% accuracy
    expect(result.ac1).toBeCloseTo(0.8647, 3); // Should match Python result ~0.86
  });

  test('handles perfect agreement scenario like Shipping Address', () => {
    // Simulated "Shipping Address" feedback items - perfect agreement (all Yes → Yes)
    const perfectAgreementItems: FeedbackItem[] = Array(13).fill(null).map((_, i) => ({
      itemId: `shipping-item-${i}`,
      initialValue: 'Yes',
      finalValue: 'Yes',
      scoreId: 'shipping-address',
      editComment: 'agree'
    }));

    const result = analyzeFeedbackForScore(perfectAgreementItems, 'shipping-address', 'Shipping Address');
    
    expect(result.totalItems).toBe(13);
    expect(result.totalAgreements).toBe(13);
    expect(result.accuracy).toBe(100); // 100% accuracy
    expect(result.ac1).toBe(1.0); // Perfect AC1 score, matching Python
  });
});

describe('analyzeFeedbackForScorecard', () => {
  test('analyzes feedback for multiple scores', () => {
    const feedbackItems = [
      createMockFeedbackItem('1', 'score1', 'Yes', 'Yes', 'Score 1'),
      createMockFeedbackItem('2', 'score1', 'No', 'No', 'Score 1'),
      createMockFeedbackItem('3', 'score2', 'A', 'A', 'Score 2'),
      createMockFeedbackItem('4', 'score2', 'B', 'A', 'Score 2'), // Mismatch
    ];

    const result = analyzeFeedbackForScorecard(feedbackItems);
    
    expect(result.scores).toHaveLength(2);
    expect(result.overall.totalItems).toBe(4);
    expect(result.overall.totalAgreements).toBe(3);
    expect(result.overall.totalMismatches).toBe(1);
    expect(result.overall.accuracy).toBe(75);
  });

  test('filters by score IDs when provided', () => {
    const feedbackItems = [
      createMockFeedbackItem('1', 'score1', 'Yes', 'Yes', 'Score 1'),
      createMockFeedbackItem('2', 'score2', 'A', 'A', 'Score 2'),
      createMockFeedbackItem('3', 'score3', 'X', 'X', 'Score 3'),
    ];

    const result = analyzeFeedbackForScorecard(feedbackItems, ['score1', 'score2']);
    
    expect(result.scores).toHaveLength(2);
    expect(result.scores.map(s => s.scoreId)).toEqual(['score1', 'score2']);
    expect(result.overall.totalItems).toBe(2);
  });

  test('calculates correct overall AC1 for scorecard analysis', () => {
    // Test with mixed data from multiple scores to ensure overall AC1 matches combined calculation
    const feedbackItems = [
      // Score 1: 2 items, 1 agreement
      createMockFeedbackItem('1', 'score1', 'Yes', 'Yes', 'Score 1'),
      createMockFeedbackItem('2', 'score1', 'No', 'Yes', 'Score 1'),
      // Score 2: 2 items, 1 agreement  
      createMockFeedbackItem('3', 'score2', 'No', 'No', 'Score 2'),
      createMockFeedbackItem('4', 'score2', 'Yes', 'No', 'Score 2')
    ];

    const result = analyzeFeedbackForScorecard(feedbackItems);
    
    // Overall: 4 items, 2 agreements (50% accuracy)
    expect(result.overall.totalItems).toBe(4);
    expect(result.overall.totalAgreements).toBe(2);
    expect(result.overall.accuracy).toBe(50);
    
    // Combined distribution: Initial (2 Yes, 2 No) + Final (2 Yes, 2 No) = 4 Yes, 4 No
    // Expected AC1 calculation:
    // π₁ = 4/8 = 0.5, π₂ = 4/8 = 0.5, k = 2
    // Pe = (0.5 * 0.5 + 0.5 * 0.5) / (2 - 1) = 0.5
    // AC1 = (0.5 - 0.5) / (1 - 0.5) = 0 / 0.5 = 0
    expect(result.overall.ac1).toBe(0);
    
    // Individual scores should also be calculated correctly
    expect(result.scores).toHaveLength(2);
    expect(result.scores[0].totalItems).toBe(2);
    expect(result.scores[1].totalItems).toBe(2);
  });

  test('matches real-world scorecard analysis with multiple scores', () => {
    // Simulate a realistic scorecard with different performance across scores
    const feedbackItems = [
      // Medication Review: 4 items, 3 agreements (like real data but smaller)
      createMockFeedbackItem('1', 'medication-review', 'No', 'No', 'Medication Review'),
      createMockFeedbackItem('2', 'medication-review', 'No', 'No', 'Medication Review'),
      createMockFeedbackItem('3', 'medication-review', 'No', 'Yes', 'Medication Review'),
      createMockFeedbackItem('4', 'medication-review', 'Yes', 'No', 'Medication Review'),
      
      // Shipping Address: 3 items, perfect agreement (like real data)
      createMockFeedbackItem('5', 'shipping-address', 'Yes', 'Yes', 'Shipping Address'),
      createMockFeedbackItem('6', 'shipping-address', 'Yes', 'Yes', 'Shipping Address'),
      createMockFeedbackItem('7', 'shipping-address', 'Yes', 'Yes', 'Shipping Address'),
    ];

    const result = analyzeFeedbackForScorecard(feedbackItems);
    
    // Overall: 7 items, 5 agreements
    expect(result.overall.totalItems).toBe(7);
    expect(result.overall.totalAgreements).toBe(5);
    expect(result.overall.accuracy).toBeCloseTo(71.43, 1); // 5/7 * 100
    
    // Verify individual score results
    expect(result.scores).toHaveLength(2);
    
    const medicationReview = result.scores.find(s => s.scoreId === 'medication-review');
    const shippingAddress = result.scores.find(s => s.scoreId === 'shipping-address');
    
    expect(medicationReview?.totalItems).toBe(4);
    expect(medicationReview?.totalAgreements).toBe(2); // 2 agreements out of 4
    expect(medicationReview?.accuracy).toBe(50);
    
    expect(shippingAddress?.totalItems).toBe(3);
    expect(shippingAddress?.totalAgreements).toBe(3); // Perfect agreement
    expect(shippingAddress?.accuracy).toBe(100);
    expect(shippingAddress?.ac1).toBe(1.0); // Perfect AC1
    
    // Overall AC1 should be calculated from combined data, not averaged from individual scores
    // Combined: Initial (3 Yes, 4 No) + Final (4 Yes, 3 No) = 7 Yes, 7 No total
    // Observed agreement: 5/7 = 0.714285714
    // Pe = (0.5 * 0.5 + 0.5 * 0.5) / 1 = 0.5
    // AC1 = (0.714285714 - 0.5) / (1 - 0.5) = 0.214285714 / 0.5 = 0.428571428
    expect(result.overall.ac1).toBeCloseTo(0.44, 1);
  });
});

describe('filterFeedbackByDateRange', () => {
  test('filters feedback items by date range', () => {
    const feedbackItems = [
      createMockFeedbackItem('1', 'score1', 'Yes', 'Yes', 'Test', '2023-01-01T00:00:00Z'),
      createMockFeedbackItem('2', 'score1', 'No', 'No', 'Test', '2023-01-15T00:00:00Z'),
      createMockFeedbackItem('3', 'score1', 'Yes', 'No', 'Test', '2023-02-01T00:00:00Z'),
    ];

    const startDate = new Date('2023-01-01');
    const endDate = new Date('2023-01-31');
    
    const filtered = filterFeedbackByDateRange(feedbackItems, startDate, endDate);
    
    expect(filtered).toHaveLength(2);
    expect(filtered.map(item => item.id)).toEqual(['1', '2']);
  });

  test('handles items with missing editedAt using createdAt', () => {
    const feedbackItems = [
      {
        ...createMockFeedbackItem('1', 'score1', 'Yes', 'Yes', 'Test', '2023-01-01T00:00:00Z'),
        editedAt: '', // Empty editedAt
        createdAt: '2023-01-15T00:00:00Z'
      }
    ];

    const startDate = new Date('2023-01-10');
    const endDate = new Date('2023-01-20');
    
    const filtered = filterFeedbackByDateRange(feedbackItems, startDate, endDate);
    
    expect(filtered).toHaveLength(1);
  });
});

describe('convertToScorecardReportFormat', () => {
  test('converts analysis results to scorecard report format', () => {
    const analysisResult = {
      scores: [{
        scoreId: 'score1',
        scoreName: 'Test Score',
        accuracy: 75,
        totalItems: 4,
        totalAgreements: 3,
        totalMismatches: 1,
        ac1: 0.5,
        confusionMatrix: {
          labels: ['No', 'Yes'],
          matrix: [{
            actualClassLabel: 'Yes',
            predictedClassCounts: { 'Yes': 2, 'No': 1 }
          }]
        },
        labelDistribution: { 'Yes': 3, 'No': 1 },
        predictedLabelDistribution: { 'Yes': 2, 'No': 2 }
      }],
      overall: {
        accuracy: 75,
        totalItems: 4,
        totalAgreements: 3,
        totalMismatches: 1,
        ac1: 0.5,
        confusionMatrix: {
          labels: ['No', 'Yes'],
          matrix: []
        },
        labelDistribution: { 'Yes': 3, 'No': 1 },
        predictedLabelDistribution: { 'Yes': 2, 'No': 2 }
      }
    };

    const dateRange = {
      start: '2023-01-01T00:00:00Z',
      end: '2023-01-31T23:59:59Z'
    };

    const result = convertToScorecardReportFormat(analysisResult, dateRange);
    
    expect(result.scores).toHaveLength(1);
    expect(result.scores[0].score_name).toBe('Test Score');
    expect(result.scores[0].accuracy).toBe(75);
    expect(result.scores[0].ac1).toBe(0.5);
    expect(result.total_items).toBe(4);
    expect(result.overall_ac1).toBe(0.5);
    expect(result.date_range).toEqual(dateRange);
    
    // Check class_distribution format
    expect(result.scores[0].class_distribution).toEqual([
      { label: 'Yes', count: 3 },
      { label: 'No', count: 1 }
    ]);
  });
});