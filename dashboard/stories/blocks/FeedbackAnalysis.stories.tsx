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

const scoreTemplate = (id: string, name: string, ac1: number | null, comparisons: number, mismatches: number, accuracy: number) => ({
  id,
  name,
  external_id: `ext-${id}`,
  ac1,
  total_comparisons: comparisons,
  mismatches,
  accuracy,
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