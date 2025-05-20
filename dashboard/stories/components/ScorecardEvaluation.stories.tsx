import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { ScorecardEvaluation, ScorecardReportEvaluationData } from '@/components/ui/scorecard-evaluation';

const meta: Meta<typeof ScorecardEvaluation> = {
  title: 'Report Blocks/ScorecardReport/Evaluation',
  component: ScorecardEvaluation,
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
type Story = StoryObj<typeof ScorecardEvaluation>;

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

export const BasicScore: Story = {
  args: {
    score: createScoreData(
      'score1',
      'Topic Classification',
      200,
      25,
      87.5,
      { 'Business': 80, 'Technology': 60, 'Health': 40, 'Entertainment': 20 },
      {
        class_distribution: createClassDistribution({ 'Business': 80, 'Technology': 60, 'Health': 40, 'Entertainment': 20 }),
        confusion_matrix: createConfusionMatrix({ 'Business': 80, 'Technology': 60, 'Health': 40, 'Entertainment': 20 }, 87.5)
      }
    ),
  },
};

export const WithPrecisionRecall: Story = {
  args: {
    score: createScoreData(
      'score2',
      'Sentiment Analysis',
      150,
      15,
      90.0,
      { 'Positive': 90, 'Neutral': 40, 'Negative': 20 },
      {
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

export const WithoutPrecisionRecall: Story = {
  args: {
    score: createScoreData(
      'score3',
      'Intent Recognition',
      180,
      30,
      83.3,
      { 'Purchase': 70, 'Browse': 60, 'Support': 50 },
      {
        precision: 85.6,
        recall: 82.1,
        class_distribution: createClassDistribution({ 'Purchase': 70, 'Browse': 60, 'Support': 50 }),
        predicted_class_distribution: createClassDistribution({ 'Purchase': 72, 'Browse': 58, 'Support': 50 }),
        confusion_matrix: createConfusionMatrix({ 'Purchase': 70, 'Browse': 60, 'Support': 50 }, 83.3)
      }
    ),
    showPrecisionRecall: false
  },
};

export const WithWarning: Story = {
  args: {
    score: createScoreData(
      'score-warning',
      'Score With Warning',
      100,
      35,
      65.0,
      { 'yes': 60, 'no': 40 },
      {
        precision: 68.2,
        recall: 63.5,
        class_distribution: createClassDistribution({ 'yes': 60, 'no': 40 }),
        predicted_class_distribution: createClassDistribution({ 'yes': 62, 'no': 38 }),
        confusion_matrix: createConfusionMatrix({ 'yes': 60, 'no': 40 }, 65.0),
        warning: "Low accuracy detected. Model may need retraining for this classification task."
      }
    ),
  },
};

export const WithAC1: Story = {
  args: {
    score: createScoreData(
      'score-ac1',
      'Score With AC1',
      100,
      20,
      80.0,
      { 'Positive': 60, 'Negative': 40 },
      {
        ac1: 0.62,
        class_distribution: createClassDistribution({ 'Positive': 60, 'Negative': 40 }),
        predicted_class_distribution: createClassDistribution({ 'Positive': 62, 'Negative': 38 }),
        confusion_matrix: createConfusionMatrix({ 'Positive': 60, 'Negative': 40 }, 80.0)
      }
    ),
  },
};

export const WithNotesOnly: Story = {
  args: {
    score: createScoreData(
      'score-notes',
      'Score With Notes Only',
      80,
      16,
      80.0,
      { 'yes': 60, 'no': 20 },
      {
        class_distribution: createClassDistribution({ 'yes': 60, 'no': 20 }),
        predicted_class_distribution: createClassDistribution({ 'yes': 62, 'no': 18 }),
        confusion_matrix: createConfusionMatrix({ 'yes': 60, 'no': 20 }, 80.0),
        notes: "This model shows good performance on the dataset. Consider evaluating on more diverse data."
      }
    ),
  },
};

export const WithDiscussionOnly: Story = {
  args: {
    score: createScoreData(
      'score-discussion',
      'Score With Discussion Only',
      120,
      20,
      83.3,
      { 'Positive': 85, 'Negative': 35 },
      {
        class_distribution: createClassDistribution({ 'Positive': 85, 'Negative': 35 }),
        predicted_class_distribution: createClassDistribution({ 'Positive': 83, 'Negative': 37 }),
        confusion_matrix: createConfusionMatrix({ 'Positive': 85, 'Negative': 35 }, 83.3),
        discussion: "The sentiment analysis model achieves good performance with 83.3% accuracy on the test dataset. The model performs particularly well on positive sentiment detection, with fewer errors in that category. The class distribution shows a positive sentiment bias in the dataset (71% positive, 29% negative), which is typical for customer feedback in this domain. To further improve model performance, we should consider collecting more negative examples to balance the training data."
      }
    ),
  },
};

export const WithNotesAndDiscussion: Story = {
  args: {
    score: createScoreData(
      'score-notes-discussion',
      'Score With Notes and Discussion',
      150,
      30,
      80.0,
      { 'High': 50, 'Medium': 60, 'Low': 40 },
      {
        precision: 82.5,
        recall: 78.3,
        class_distribution: createClassDistribution({ 'High': 50, 'Medium': 60, 'Low': 40 }),
        predicted_class_distribution: createClassDistribution({ 'High': 48, 'Medium': 62, 'Low': 40 }),
        confusion_matrix: createConfusionMatrix({ 'High': 50, 'Medium': 60, 'Low': 40 }, 80.0),
        notes: "Model performs well overall but struggles with 'Medium' vs 'Low' distinction.",
        discussion: "This classification model demonstrates solid performance with 80% accuracy across the three categories. The distribution across the rating categories is relatively balanced, with a slight weighting toward the 'Medium' category (40%). Most of the misclassifications (about 70% of all errors) occurred between 'Medium' and 'Low' categories, suggesting some ambiguity in the features that distinguish these categories. Recommendation: Consider feature engineering to better capture the subtle differences between 'Medium' and 'Low' categories, possibly by incorporating additional contextual information."
      }
    ),
  },
}; 