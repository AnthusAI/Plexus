import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { ScorecardReportEvaluation, ScorecardReportEvaluationData } from '@/components/ui/scorecard-evaluation';

const meta: Meta<typeof ScorecardReportEvaluation> = {
  title: 'Report Blocks/ScorecardReport/Evaluation',
  component: ScorecardReportEvaluation,
  parameters: {
    layout: 'padded',
  },
};

export default meta;
type Story = StoryObj<typeof ScorecardReportEvaluation>;

// Helper function to create score templates
const createScoreData = (
  id: string,
  name: string,
  comparisons: number,
  mismatches: number,
  accuracy: number,
  labelDistribution?: Record<string, number>,
  extraData?: Partial<ScorecardReportEvaluationData>
): ScorecardReportEvaluationData => ({
  id,
  score_name: name,
  item_count: comparisons,
  total_items: comparisons,
  mismatches,
  accuracy,
  label_distribution: labelDistribution,
  ...extraData
});

// Create visualization data for stories
const createClassDistribution = (labelDistribution: Record<string, number>) => {
  return Object.entries(labelDistribution).map(([label, count]) => ({
    label,
    count
  }));
};

const createConfusionMatrix = (labelDistribution: Record<string, number>, accuracy: number) => {
  const labels = Object.keys(labelDistribution);
  const matrix = labels.map(label => {
    const actualClassCounts: Record<string, number> = {};
    const total = labelDistribution[label];
    
    // Simplified logic just for the story - not accurate
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

// Responsive story that allows testing different widths
export const Responsive: Story = {
  decorators: [
    (Story) => (
      <div className="w-full p-2">
        <div className="border border-dashed border-muted-foreground p-4 resize-x overflow-auto min-w-[320px] max-w-full">
          <p className="text-xs text-muted-foreground mb-4">
            ↔️ Resize this container to see responsive layout changes
          </p>
          <Story />
        </div>
      </div>
    ),
  ],
  args: {
    score: createScoreData(
      'score-all-metrics',
      'Sentiment Analysis with All Metrics',
      150,
      15,
      90.0,
      { 'Positive': 90, 'Neutral': 40, 'Negative': 20 },
      {
        ac1: 0.82,
        precision: 92.3,
        recall: 88.7,
        class_distribution: createClassDistribution({ 'Positive': 90, 'Neutral': 40, 'Negative': 20 }),
        predicted_class_distribution: createClassDistribution({ 'Positive': 93, 'Neutral': 37, 'Negative': 20 }),
        confusion_matrix: createConfusionMatrix({ 'Positive': 90, 'Neutral': 40, 'Negative': 20 }, 90.0),
        notes: "This model shows excellent performance with high agreement between raters. The precision and recall metrics indicate good balance between minimizing false positives and negatives."
      }
    ),
    showPrecisionRecall: true
  },
};

// Multiple cards with different widths
export const ResponsiveCardGrid: Story = {
  decorators: [
    (Story) => (
      <div className="w-full">
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          <div className="w-full">
            <Story />
          </div>
          <div className="w-full">
            <Story />
          </div>
          <div className="w-full md:col-span-2 xl:col-span-1">
            <Story />
          </div>
        </div>
      </div>
    ),
  ],
  args: {
    score: createScoreData(
      'score-all-metrics',
      'Sentiment Analysis with All Metrics',
      150,
      15,
      90.0,
      { 'Positive': 90, 'Neutral': 40, 'Negative': 20 },
      {
        ac1: 0.82,
        precision: 92.3,
        recall: 88.7,
        class_distribution: createClassDistribution({ 'Positive': 90, 'Neutral': 40, 'Negative': 20 }),
        predicted_class_distribution: createClassDistribution({ 'Positive': 93, 'Neutral': 37, 'Negative': 20 }),
        confusion_matrix: createConfusionMatrix({ 'Positive': 90, 'Neutral': 40, 'Negative': 20 }, 90.0)
      }
    ),
    showPrecisionRecall: true
  },
};

// Full width story with all gauges
export const FullWidth: Story = {
  decorators: [
    (Story) => (
      <div className="w-full">
        <Story />
      </div>
    ),
  ],
  args: {
    score: createScoreData(
      'score-all-metrics',
      'Full Width Demo - All Metrics',
      150,
      15,
      90.0,
      { 'Positive': 90, 'Neutral': 40, 'Negative': 20 },
      {
        ac1: 0.82,
        precision: 92.3,
        recall: 88.7,
        class_distribution: createClassDistribution({ 'Positive': 90, 'Neutral': 40, 'Negative': 20 }),
        predicted_class_distribution: createClassDistribution({ 'Positive': 93, 'Neutral': 37, 'Negative': 20 }),
        confusion_matrix: createConfusionMatrix({ 'Positive': 90, 'Neutral': 40, 'Negative': 20 }, 90.0)
      }
    ),
    showPrecisionRecall: true
  },
}; 