import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { FeedbackScoreCard, ScoreData } from '@/components/ui/feedback-score-card';

const meta: Meta<typeof FeedbackScoreCard> = {
  title: 'Components/FeedbackScoreCard',
  component: FeedbackScoreCard,
  parameters: {
    layout: 'padded',
  },
  decorators: [
    (Story) => (
      <div className="max-w-md mx-auto">
        <Story />
      </div>
    ),
  ],
};

export default meta;
type Story = StoryObj<typeof FeedbackScoreCard>;

// Helper function to create score templates
const createScore = (
  id: string,
  name: string,
  ac1: number | null,
  comparisons: number,
  mismatches: number,
  accuracy: number,
  labelDistribution?: Record<string, number>
): ScoreData => ({
  id,
  score_name: name,
  cc_question_id: `ext-${id}`,
  ac1,
  item_count: comparisons,
  mismatches,
  accuracy,
  label_distribution: labelDistribution,
});

export const BalancedDistribution: Story = {
  args: {
    score: createScore(
      'score1',
      'Binary Score (50/50)',
      0.65,
      100,
      25,
      75.0,
      { 'yes': 50, 'no': 50 }
    ),
  },
};

export const ImbalancedDistribution: Story = {
  args: {
    score: createScore(
      'score2',
      'Binary Score (90/10)',
      0.55,
      100,
      10,
      90.0,
      { 'yes': 90, 'no': 10 }
    ),
  },
};

export const ThreeClasses: Story = {
  args: {
    score: createScore(
      'score3',
      'Three Classes (Equal)',
      0.72,
      90,
      20,
      77.8,
      { 'low': 30, 'medium': 30, 'high': 30 }
    ),
  },
};

export const VeryImbalanced: Story = {
  args: {
    score: createScore(
      'score4',
      'Very Imbalanced (95/5)',
      0.25,
      100,
      5,
      95.0,
      { 'yes': 95, 'no': 5 }
    ),
  },
};

export const NoDistributionData: Story = {
  args: {
    score: createScore(
      'score5',
      'No Distribution Data',
      0.45,
      100,
      20,
      80.0
    ),
  },
};

export const WithNoAC1Data: Story = {
  args: {
    score: createScore(
      'score6',
      'Missing AC1 Score',
      null,
      100,
      20,
      80.0,
      { 'yes': 70, 'no': 30 }
    ),
  },
}; 