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
      <div className="bg-card p-6 rounded-lg">
        <Story />
      </div>
    ),
  ],
};

export default meta;
type Story = StoryObj<typeof BlockRenderer>;

export const Basic: Story = {
  args: {
    name: 'Customer Feedback Analysis',
    output: {
      overall_ac1: 0.846,
      question_ac1s: {
        "score1": {
          ac1: 0.927,
          name: "Customer Greeting",
          total_comparisons: 120,
          mismatches: 5,
          mismatch_percentage: 4.17
        },
        "score2": {
          ac1: 0.813,
          name: "Issue Identification",
          total_comparisons: 118,
          mismatches: 12,
          mismatch_percentage: 10.17
        },
        "score3": {
          ac1: 0.775,
          name: "Solution Explanation",
          total_comparisons: 115,
          mismatches: 18,
          mismatch_percentage: 15.65
        }
      },
      total_items: 120,
      total_mismatches: 35,
      mismatch_percentage: 9.72,
      date_range: {
        start: '2025-04-01T00:00:00Z',
        end: '2025-04-30T23:59:59Z'
      }
    },
    position: 0,
    config: {
      class: 'FeedbackAnalysis',
      scorecard: 'customer_service_v1',
      days: 30
    }
  },
};

export const WithScoreFilter: Story = {
  args: {
    name: 'Customer Greeting Analysis',
    output: {
      overall_ac1: 0.927,
      question_ac1s: {
        "score1": {
          ac1: 0.927,
          name: "Customer Greeting",
          total_comparisons: 120,
          mismatches: 5,
          mismatch_percentage: 4.17
        }
      },
      total_items: 120,
      total_mismatches: 5,
      mismatch_percentage: 4.17,
      date_range: {
        start: '2025-04-01T00:00:00Z',
        end: '2025-04-30T23:59:59Z'
      }
    },
    position: 1,
    config: {
      class: 'FeedbackAnalysis',
      scorecard: 'customer_service_v1',
      score_id: 'score1',
      days: 30
    }
  },
};

export const MixedPerformance: Story = {
  args: {
    name: 'Mixed Agreement Levels',
    output: {
      overall_ac1: 0.681,
      question_ac1s: {
        "score1": {
          ac1: 0.892,
          name: "Initial Greeting",
          total_comparisons: 50,
          mismatches: 3,
          mismatch_percentage: 6.0
        },
        "score2": {
          ac1: 0.743,
          name: "Problem Identification",
          total_comparisons: 50,
          mismatches: 8,
          mismatch_percentage: 16.0
        },
        "score3": {
          ac1: 0.623,
          name: "Solution Proposal",
          total_comparisons: 50,
          mismatches: 12,
          mismatch_percentage: 24.0
        },
        "score4": {
          ac1: 0.466,
          name: "Closing Remarks",
          total_comparisons: 50,
          mismatches: 18,
          mismatch_percentage: 36.0
        }
      },
      total_items: 200,
      total_mismatches: 41,
      mismatch_percentage: 20.5,
      date_range: {
        start: '2025-04-01T00:00:00Z',
        end: '2025-04-30T23:59:59Z'
      }
    },
    position: 2,
    config: {
      class: 'FeedbackAnalysis',
      scorecard: 'customer_service_v2',
      days: 30
    }
  },
};

export const NoData: Story = {
  args: {
    name: 'No Feedback Data',
    output: {
      overall_ac1: null,
      question_ac1s: {},
      total_items: 0,
      total_mismatches: 0,
      mismatch_percentage: 0,
      date_range: {
        start: '2025-04-01T00:00:00Z',
        end: '2025-04-30T23:59:59Z'
      }
    },
    position: 3,
    config: {
      class: 'FeedbackAnalysis',
      scorecard: 'new_scorecard_v1',
      days: 30
    }
  },
}; 