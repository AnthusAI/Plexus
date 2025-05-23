import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { BlockRenderer } from '@/components/blocks/BlockRegistry';
import FeedbackAnalysis from '@/components/blocks/FeedbackAnalysis';
import { type ClassDistribution } from '@/components/ClassDistributionVisualizer';
import { type ConfusionMatrixData } from '@/components/confusion-matrix';

const meta: Meta<typeof BlockRenderer> = {
  title: 'Reports/Blocks/FeedbackAnalysis',
  component: BlockRenderer,
  parameters: {
    layout: 'padded',
  },
};

export default meta;
type Story = StoryObj<typeof BlockRenderer>;

const baseFeedbackAnalysisData = {
  total_items: 0, // Will be overridden
  total_mismatches: 0, // Will be overridden
  accuracy: 0, // Will be overridden
  date_range: {
    start: '2023-01-01T00:00:00Z',
    end: '2023-01-31T23:59:59Z',
  },
};

// Helper functions to create visualization data
const createClassDistribution = (labelDistribution: Record<string, number>): ClassDistribution[] => {
  return Object.entries(labelDistribution).map(([label, count]) => ({
    label,
    count
  }));
};

const createConfusionMatrix = (labelDistribution: Record<string, number>, accuracy: number): ConfusionMatrixData => {
  const labels = Object.keys(labelDistribution);
  const matrix = labels.map(label => {
    const actualClassCounts: Record<string, number> = {};
    const total = labelDistribution[label];
    
    labels.forEach(predictedLabel => {
      if (predictedLabel === label) {
        actualClassCounts[predictedLabel] = Math.round(total * (accuracy / 100));
      } else {
        // Distribute remaining errors among other classes
        const errorShare = Math.round((total * (1 - accuracy / 100)) / (labels.length - 1));
        actualClassCounts[predictedLabel] = errorShare;
      }
    });
    
    return {
      actualClassLabel: label,
      predictedClassCounts: actualClassCounts
    };
  });
  
  return {
    labels,
    matrix
  };
};

const scoreTemplate = (
  id: string, 
  name: string, 
  ac1: number | null, 
  comparisons: number, 
  mismatches: number, 
  accuracy: number,
  labelDistribution?: Record<string, number>
) => {
  const baseScore = {
    id,
    score_name: name,
    question: name, // For backward compatibility
    cc_question_id: `ext-${id}`,
    ac1,
    item_count: comparisons,
    mismatches,
    accuracy,
    label_distribution: labelDistribution,
  };
  
  // Add visualization data if label distribution is provided
  if (labelDistribution) {
    return {
      ...baseScore,
      class_distribution: createClassDistribution(labelDistribution),
      predicted_class_distribution: createClassDistribution(
        // Create a slightly different distribution for predicted
        Object.fromEntries(
          Object.entries(labelDistribution).map(([key, value]) => [
            key, 
            Math.max(0, value + Math.floor(Math.random() * 5) - 2)
          ])
        )
      ),
      confusion_matrix: createConfusionMatrix(labelDistribution, accuracy)
    };
  }
  
  return baseScore;
};

export const SingleScore: Story = {
  args: {
    name: 'Feedback Analysis - Single Score',
    type: 'FeedbackAnalysis', // This type must match the key used in registerBlock
    position: 0,
    log: 'Log for single score analysis.',
    config: { // Mock config passed to the block
      class: 'FeedbackAnalysis', // This is what the python block's config would look like
      scorecard: 'some-scorecard-id',
      days: 30,
    },
    output: { // This is the actual data structure the component expects
      ...baseFeedbackAnalysisData,
      overall_ac1: 0.75,
      scores: [
        scoreTemplate('score1', 'Agent Empathy', 0.75, 50, 12, 76.0, { 'Excellent': 30, 'Good': 15, 'Poor': 5 }),
      ],
      total_items: 50,
      total_mismatches: 12,
      accuracy: 76.0,
      label_distribution: { 'Excellent': 30, 'Good': 15, 'Poor': 5 }
    },
  },
};

export const MultipleScores: Story = {
  args: {
    name: 'Feedback Analysis - Multiple Scores',
    type: 'FeedbackAnalysis',
    position: 1,
    log: 'Log for multiple score analysis.',
    config: {
      class: 'FeedbackAnalysis',
      scorecard: 'another-scorecard-id',
      days: 60,
    },
    output: {
      ...baseFeedbackAnalysisData,
      overall_ac1: 0.82,
      scores: [
        scoreTemplate('score1', 'Agent Empathy', 0.75, 50, 12, 76.0, { 'High': 25, 'Medium': 15, 'Low': 10 }),
        scoreTemplate('score2', 'Problem Resolution', 0.88, 60, 7, 88.3, { 'Resolved': 45, 'Unresolved': 15 }),
        scoreTemplate('score3', 'Product Knowledge', 0.65, 45, 16, 64.4, { 'Expert': 15, 'Proficient': 20, 'Basic': 10 }),
        scoreTemplate('score4', 'Call Opening', null, 10, 5, 50.0, { 'Good': 5, 'Poor': 5 }),
      ],
      total_items: 165, // Sum of comparisons
      total_mismatches: 40, // Sum of mismatches
      accuracy: Number(((165 - 40) / 165 * 100).toFixed(1)), // Calculated accuracy
      label_distribution: { 'High': 25, 'Medium': 15, 'Low': 10, 'Resolved': 45, 'Unresolved': 15, 'Expert': 15, 'Proficient': 20, 'Basic': 10, 'Good': 5, 'Poor': 5 }
    },
  },
};

export const WithBalancedDistribution: Story = {
  args: {
    name: 'Feedback Analysis - Balanced Class Distribution',
    type: 'FeedbackAnalysis',
    position: 1,
    log: 'Log with balanced class distribution.',
    config: {
      class: 'FeedbackAnalysis',
      scorecard: 'balanced-example',
      days: 30,
    },
    output: {
      ...baseFeedbackAnalysisData,
      overall_ac1: 0.65,
      scores: [
        scoreTemplate('score1', 'Binary Score (50/50)', 0.65, 100, 25, 75.0, { 'yes': 50, 'no': 50 }),
        scoreTemplate('score2', 'Three Classes (Equal)', 0.72, 90, 20, 77.8, { 'low': 30, 'medium': 30, 'high': 30 })
      ],
      total_items: 190,
      total_mismatches: 45,
      accuracy: 76.3,
      label_distribution: { 'yes': 50, 'no': 50, 'low': 30, 'medium': 30, 'high': 30 }
    },
  },
};

export const WithImbalancedDistribution: Story = {
  args: {
    name: 'Feedback Analysis - Imbalanced Class Distribution',
    type: 'FeedbackAnalysis',
    position: 1,
    log: 'Log with imbalanced class distribution.',
    config: {
      class: 'FeedbackAnalysis',
      scorecard: 'imbalanced-example',
      days: 30,
    },
    output: {
      ...baseFeedbackAnalysisData,
      overall_ac1: 0.55,
      scores: [
        scoreTemplate('score1', 'Binary Score (90/10)', 0.55, 100, 10, 90.0, { 'yes': 90, 'no': 10 }),
        scoreTemplate('score2', 'Three Classes (Skewed)', 0.62, 100, 15, 85.0, { 'low': 70, 'medium': 20, 'high': 10 })
      ],
      total_items: 200,
      total_mismatches: 25,
      accuracy: 87.5,
      label_distribution: { 'yes': 90, 'no': 10, 'low': 70, 'medium': 20, 'high': 10 }
    },
  },
};

export const WithVeryImbalancedDistribution: Story = {
  args: {
    name: 'Feedback Analysis - Very Imbalanced',
    type: 'FeedbackAnalysis',
    position: 1,
    log: 'Log with extremely imbalanced class distribution.',
    config: {
      class: 'FeedbackAnalysis',
      scorecard: 'very-imbalanced-example',
      days: 30,
    },
    output: {
      ...baseFeedbackAnalysisData,
      overall_ac1: 0.25,
      scores: [
        scoreTemplate('score1', 'Binary Score (95/5)', 0.25, 100, 5, 95.0, { 'yes': 95, 'no': 5 }),
      ],
      total_items: 100,
      total_mismatches: 5,
      accuracy: 95.0,
      label_distribution: { 'yes': 95, 'no': 5 }
    },
  },
};

export const NoScores: Story = {
  args: {
    name: 'Feedback Analysis - No Scores',
    type: 'FeedbackAnalysis',
    position: 2,
    config: {
      class: 'FeedbackAnalysis',
      scorecard: 'empty-scorecard-id',
    },
    output: {
      ...baseFeedbackAnalysisData,
      overall_ac1: null,
      scores: [],
      total_items: 0,
      total_mismatches: 0,
      accuracy: 0,
    },
  },
};

export const LoadingState: Story = {
 args: {
    name: 'Feedback Analysis - Loading',
    type: 'FeedbackAnalysis',
    position: 0,
    config: {
      class: 'FeedbackAnalysis',
    },
    // To simulate loading, we pass null or an empty object for output
    // The component itself should handle this gracefully.
    output: null as any, // or an empty object that would trigger its internal "No data" state
  },
};

export const WithSingleWarning: Story = {
  args: {
    name: 'Feedback Analysis - One Score With Warning',
    type: 'FeedbackAnalysis',
    position: 3,
    log: 'Log for analysis with one warning.',
    config: {
      class: 'FeedbackAnalysis',
      scorecard: 'warning-example-single',
      days: 30,
    },
    output: {
      ...baseFeedbackAnalysisData,
      overall_ac1: 0.68,
      scores: [
        scoreTemplate('score1', 'Agent Empathy', 0.75, 50, 12, 76.0, { 'High': 25, 'Medium': 15, 'Low': 10 }),
        scoreTemplate('score2', 'Problem Resolution', 0.88, 60, 7, 88.3, { 'Resolved': 45, 'Unresolved': 15 }),
        // This score has a warning
        {
          ...scoreTemplate('score3', 'Product Knowledge', 0.32, 45, 18, 60.0, { 'Expert': 15, 'Proficient': 20, 'Basic': 10 }),
          warning: "Low agreement score detected. This suggests inconsistent scoring between raters."
        },
        scoreTemplate('score4', 'Call Opening', 0.67, 30, 8, 73.3, { 'Good': 20, 'Poor': 10 }),
      ],
      total_items: 185,
      total_mismatches: 45,
      accuracy: 75.7,
      label_distribution: { 'High': 25, 'Medium': 15, 'Low': 10, 'Resolved': 45, 'Unresolved': 15, 'Expert': 15, 'Proficient': 20, 'Basic': 10, 'Good': 20, 'Poor': 10 }
    },
  },
};

export const WithMultipleWarnings: Story = {
  args: {
    name: 'Feedback Analysis - Multiple Scores With Warnings',
    type: 'FeedbackAnalysis',
    position: 4,
    log: 'Log for analysis with multiple warnings.',
    config: {
      class: 'FeedbackAnalysis',
      scorecard: 'warning-example-multiple',
      days: 45,
    },
    output: {
      ...baseFeedbackAnalysisData,
      overall_ac1: 0.58,
      scores: [
        // First warning - data quality issue
        {
          ...scoreTemplate('score1', 'Agent Empathy', 0.48, 15, 4, 73.3, { 'High': 8, 'Medium': 4, 'Low': 3 }),
          warning: "Insufficient data: Only 15 samples available. Results may not be statistically significant."
        },
        scoreTemplate('score2', 'Problem Resolution', 0.82, 60, 10, 83.3, { 'Resolved': 45, 'Unresolved': 15 }),
        scoreTemplate('score3', 'Call Closing', 0.70, 40, 9, 77.5, { 'Strong': 25, 'Adequate': 10, 'Weak': 5 }),
        // Second warning - poor agreement
        {
          ...scoreTemplate('score4', 'Product Knowledge', 0.22, 50, 22, 56.0, { 'Expert': 10, 'Proficient': 25, 'Basic': 15 }),
          warning: "Critical reliability concern: AC1 score below acceptable threshold (0.4). This indicates poor inter-rater reliability."
        },
      ],
      total_items: 165,
      total_mismatches: 45,
      accuracy: 72.7,
      label_distribution: { 'High': 8, 'Medium': 4, 'Low': 3, 'Resolved': 45, 'Unresolved': 15, 'Strong': 25, 'Adequate': 10, 'Weak': 5, 'Expert': 10, 'Proficient': 25, 'Basic': 15 }
    },
  },
};

export const WithNotesAndDiscussion: Story = {
  args: {
    name: 'Feedback Analysis - With Notes and Discussion',
    type: 'FeedbackAnalysis',
    position: 5,
    log: 'Log for analysis with notes and discussion.',
    config: {
      class: 'FeedbackAnalysis',
      scorecard: 'notes-discussion-example',
      days: 30,
    },
    output: {
      ...baseFeedbackAnalysisData,
      overall_ac1: 0.64,
      scores: [
        // Score with just notes
        {
          ...scoreTemplate('score1', 'Agent Empathy', 0.75, 50, 12, 76.0, { 'High': 25, 'Medium': 15, 'Low': 10 }),
          notes: "Shows strong agreement between raters. Training seems to be working well."
        },
        // Score with just discussion
        {
          ...scoreTemplate('score2', 'Problem Resolution', 0.88, 60, 7, 88.3, { 'Resolved': 45, 'Unresolved': 15 }),
          discussion: "Problem resolution scores show excellent alignment between raters with an AC1 of 0.88. This is the highest agreement score across all evaluated categories, suggesting that the rating criteria for this question are very clear and consistently applied. The data shows a clear preference for the 'Resolved' category (75% of cases), which aligns with our service level targets. The distribution indicates that most customer issues are being successfully resolved, though there remains a significant minority (25%) of unresolved cases that should be investigated further to identify patterns or process improvement opportunities."
        },
        // Score with both notes and discussion
        {
          ...scoreTemplate('score3', 'Product Knowledge', 0.65, 45, 16, 64.4, { 'Expert': 15, 'Proficient': 20, 'Basic': 10 }),
          notes: "Moderate agreement between raters. Further clarification of 'Proficient' vs 'Basic' may help.",
          discussion: "The product knowledge assessment shows moderate agreement (AC1 0.65) between raters, indicating generally consistent application of rating guidelines, though with some areas for improvement. The distribution across categories is relatively balanced, with most agents falling into the 'Proficient' category (44%). \n\nInterestingly, most disagreements (approximately 70% of mismatches) occurred between 'Proficient' and 'Basic' ratings, suggesting some ambiguity in distinguishing these levels. This is a common challenge in skills assessment where the boundary between intermediate and basic skill levels can be subjective.\n\nRecommendation: Revise the rating rubric to provide more concrete, observable behaviors that differentiate 'Proficient' from 'Basic' product knowledge. Consider including specific examples of interactions that would qualify for each category."
        },
        // Score with notes and warning
        {
          ...scoreTemplate('score4', 'Call Opening', 0.38, 40, 15, 62.5, { 'Good': 24, 'Poor': 16 }),
          notes: "Significant inconsistency between raters. Needs immediate review of scoring criteria.",
          warning: "Low agreement score detected (AC1: 0.38). This suggests inconsistent application of rating criteria."
        },
      ],
      total_items: 195, // Sum of comparisons
      total_mismatches: 50, // Sum of mismatches
      accuracy: 74.4, // Calculated accuracy
      label_distribution: { 
        'High': 25, 'Medium': 15, 'Low': 10, 
        'Resolved': 45, 'Unresolved': 15, 
        'Expert': 15, 'Proficient': 20, 'Basic': 10, 
        'Good': 24, 'Poor': 16 
      }
    },
  },
}; 