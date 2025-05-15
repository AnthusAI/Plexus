import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { BlockRenderer } from '@/components/blocks/BlockRegistry';
import FeedbackAnalysis from '@/components/blocks/FeedbackAnalysis';

const meta: Meta<typeof BlockRenderer> = {
  title: 'Report Blocks/FeedbackAnalysis',
  component: BlockRenderer,
  parameters: {
    layout: 'padded',
  },
  decorators: [
    (Story) => (
      <div className="bg-card p-6 rounded-lg max-w-3xl mx-auto">
        <Story />
      </div>
    ),
  ],
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

const scoreTemplate = (
  id: string, 
  name: string, 
  ac1: number | null, 
  comparisons: number, 
  mismatches: number, 
  accuracy: number,
  labelDistribution?: Record<string, number>
) => ({
  id,
  score_name: name,
  cc_question_id: `ext-${id}`,
  ac1,
  item_count: comparisons,
  mismatches,
  accuracy,
  label_distribution: labelDistribution,
});

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
        scoreTemplate('score1', 'Agent Empathy', 0.75, 50, 12, 76.0),
      ],
      total_items: 50,
      total_mismatches: 12,
      accuracy: 76.0,
      // type: 'FeedbackAnalysis' // Not needed here as it's a prop of BlockRenderer args
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
        scoreTemplate('score1', 'Agent Empathy', 0.75, 50, 12, 76.0),
        scoreTemplate('score2', 'Problem Resolution', 0.88, 60, 7, 88.3),
        scoreTemplate('score3', 'Product Knowledge', 0.65, 45, 16, 64.4),
        scoreTemplate('score4', 'Call Opening', null, 10, 5, 50.0), // Example with null AC1
      ],
      total_items: 165, // Sum of comparisons
      total_mismatches: 40, // Sum of mismatches
      accuracy: Number(((165 - 40) / 165 * 100).toFixed(1)), // Calculated accuracy
      // type: 'FeedbackAnalysis'
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
      // type: 'FeedbackAnalysis'
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
    // If the component had its own loading state prop, we would use that.
    // For BlockRenderer, the `output` prop is key.
    output: null as any, // or an empty object that would trigger its internal "No data" state
  },
}; 