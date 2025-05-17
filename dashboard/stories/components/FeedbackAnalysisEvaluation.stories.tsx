import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { FeedbackAnalysisEvaluation, FeedbackAnalysisEvaluationData } from '@/components/ui/feedback-analysis-evaluation';

const meta: Meta<typeof FeedbackAnalysisEvaluation> = {
  title: 'Report Blocks/FeedbackAnalysis/Evaluation',
  component: FeedbackAnalysisEvaluation,
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
type Story = StoryObj<typeof FeedbackAnalysisEvaluation>;

// Helper function to create score templates
const createScoreData = (
  id: string,
  name: string,
  ac1: number | null,
  comparisons: number,
  mismatches: number,
  accuracy: number,
  labelDistribution?: Record<string, number>,
  extraData?: Partial<FeedbackAnalysisEvaluationData>
): FeedbackAnalysisEvaluationData => ({
  id,
  score_name: name,
  question: name, // For backward compatibility
  cc_question_id: `ext-${id}`,
  ac1,
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

export const BalancedDistribution: Story = {
  args: {
    score: createScoreData(
      'score1',
      'Binary Score (50/50)',
      0.65,
      100,
      25,
      75.0,
      { 'yes': 50, 'no': 50 },
      {
        precision: 76.5,
        recall: 74.2,
        class_distribution: createClassDistribution({ 'yes': 50, 'no': 50 }),
        predicted_class_distribution: createClassDistribution({ 'yes': 52, 'no': 48 }),
        confusion_matrix: createConfusionMatrix({ 'yes': 50, 'no': 50 }, 75.0)
      }
    ),
  },
};

export const ImbalancedDistribution: Story = {
  args: {
    score: createScoreData(
      'score2',
      'Binary Score (90/10)',
      0.55,
      100,
      10,
      90.0,
      { 'yes': 90, 'no': 10 },
      {
        precision: 92.3,
        recall: 88.7,
        class_distribution: createClassDistribution({ 'yes': 90, 'no': 10 }),
        predicted_class_distribution: createClassDistribution({ 'yes': 93, 'no': 7 }),
        confusion_matrix: createConfusionMatrix({ 'yes': 90, 'no': 10 }, 90.0)
      }
    ),
  },
};

export const ThreeClasses: Story = {
  args: {
    score: createScoreData(
      'score3',
      'Three Classes (Equal)',
      0.72,
      90,
      20,
      77.8,
      { 'low': 30, 'medium': 30, 'high': 30 },
      {
        class_distribution: createClassDistribution({ 'low': 30, 'medium': 30, 'high': 30 }),
        predicted_class_distribution: createClassDistribution({ 'low': 32, 'medium': 28, 'high': 30 }),
        confusion_matrix: createConfusionMatrix({ 'low': 30, 'medium': 30, 'high': 30 }, 77.8)
      }
    ),
  },
};

export const VeryImbalanced: Story = {
  args: {
    score: createScoreData(
      'score4',
      'Very Imbalanced (95/5)',
      0.25,
      100,
      5,
      95.0,
      { 'yes': 95, 'no': 5 },
      {
        precision: 100.0,
        recall: 95.0,
        class_distribution: createClassDistribution({ 'yes': 95, 'no': 5 }),
        predicted_class_distribution: createClassDistribution({ 'yes': 95, 'no': 5 }),
        confusion_matrix: createConfusionMatrix({ 'yes': 95, 'no': 5 }, 95.0)
      }
    ),
  },
};

export const NoDistributionData: Story = {
  args: {
    score: createScoreData(
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
    score: createScoreData(
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

export const WithWarning: Story = {
  args: {
    score: createScoreData(
      'score-warning',
      'Score With Warning',
      0.35,
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
        warning: "Low agreement score detected. This suggests inconsistent scoring between raters."
      }
    ),
  },
};

export const WithLongWarning: Story = {
  args: {
    score: createScoreData(
      'score-long-warning',
      'Score With Detailed Warning',
      0.22,
      90,
      40,
      55.5,
      { 'yes': 45, 'no': 45 },
      {
        precision: 58.7,
        recall: 57.3,
        class_distribution: createClassDistribution({ 'yes': 45, 'no': 45 }),
        predicted_class_distribution: createClassDistribution({ 'yes': 49, 'no': 41 }),
        confusion_matrix: createConfusionMatrix({ 'yes': 45, 'no': 45 }, 55.5),
        warning: "Critical reliability concern: AC1 score below acceptable threshold (0.4). This indicates poor inter-rater reliability. Consider reviewing scoring guidelines and retraining raters. Interpretations based on this data should be made with extreme caution."
      }
    ),
  },
};

export const WithDataQualityWarning: Story = {
  args: {
    score: createScoreData(
      'score-data-warning',
      'Score With Data Quality Warning',
      0.48,
      20,
      5,
      75.0, 
      { 'yes': 14, 'no': 6 },
      {
        class_distribution: createClassDistribution({ 'yes': 14, 'no': 6 }),
        predicted_class_distribution: createClassDistribution({ 'yes': 16, 'no': 4 }),
        confusion_matrix: createConfusionMatrix({ 'yes': 14, 'no': 6 }, 75.0),
        warning: "Insufficient data: Only 20 samples available. Results may not be statistically significant. Consider collecting additional data."
      }
    ),
  },
};

export const WithNotesOnly: Story = {
  args: {
    score: createScoreData(
      'score-notes',
      'Score With Notes Only',
      0.62,
      80,
      16,
      80.0,
      { 'yes': 60, 'no': 20 },
      {
        class_distribution: createClassDistribution({ 'yes': 60, 'no': 20 }),
        predicted_class_distribution: createClassDistribution({ 'yes': 62, 'no': 18 }),
        confusion_matrix: createConfusionMatrix({ 'yes': 60, 'no': 20 }, 80.0),
        notes: "This question shows moderate agreement between raters. Existing rating guidelines seem to work well."
      }
    ),
  },
};

export const WithDiscussionOnly: Story = {
  args: {
    score: createScoreData(
      'score-discussion',
      'Score With Discussion Only',
      0.71,
      120,
      20,
      83.3,
      { 'Positive': 85, 'Negative': 35 },
      {
        class_distribution: createClassDistribution({ 'Positive': 85, 'Negative': 35 }),
        predicted_class_distribution: createClassDistribution({ 'Positive': 83, 'Negative': 37 }),
        confusion_matrix: createConfusionMatrix({ 'Positive': 85, 'Negative': 35 }, 83.3),
        discussion: "The sentiment analysis scores show good agreement (AC1 0.71) between human raters and the model. With 120 total samples, we have sufficient data for reliable analysis. The class distribution shows a positive sentiment bias in the dataset (71% positive, 29% negative), which is typical for customer feedback in this domain. The model achieved 83.3% raw agreement with human raters, which is well above the chance agreement level of approximately 58%. This indicates the model is performing significantly better than random classification."
      }
    ),
  },
};

export const WithNotesAndDiscussion: Story = {
  args: {
    score: createScoreData(
      'score-notes-discussion',
      'Score With Notes and Discussion',
      0.68,
      150,
      30,
      80.0,
      { 'High': 50, 'Medium': 60, 'Low': 40 },
      {
        class_distribution: createClassDistribution({ 'High': 50, 'Medium': 60, 'Low': 40 }),
        predicted_class_distribution: createClassDistribution({ 'High': 48, 'Medium': 62, 'Low': 40 }),
        confusion_matrix: createConfusionMatrix({ 'High': 50, 'Medium': 60, 'Low': 40 }, 80.0),
        notes: "Shows good agreement between raters. Consider clarifying distinction between 'Medium' and 'Low' categories.",
        discussion: "This customer satisfaction score demonstrates good reliability with an AC1 of 0.68, significantly above the minimum acceptable threshold of 0.4. The distribution across the three rating categories is relatively balanced, though slightly weighted toward the 'Medium' category (40%). \n\nThe 80% raw agreement rate is solid, especially for a 3-category scale where chance agreement would be approximately 33%. Most of the disagreements (about 70% of all mismatches) occurred between 'Medium' and 'Low' categories, suggesting some ambiguity in the rating guidelines for these categories. \n\nRecommendation: A brief clarification session with raters focused specifically on distinguishing 'Medium' from 'Low' ratings could further improve reliability. Additionally, updating the scoring rubric with more concrete examples for these categories would be beneficial for future analysis."
      }
    ),
  },
};

export const WithNotesAndWarning: Story = {
  args: {
    score: createScoreData(
      'score-notes-warning',
      'Score With Notes and Warning',
      0.35,
      75,
      30,
      60.0,
      { 'yes': 45, 'no': 30 },
      {
        class_distribution: createClassDistribution({ 'yes': 45, 'no': 30 }),
        predicted_class_distribution: createClassDistribution({ 'yes': 43, 'no': 32 }),
        confusion_matrix: createConfusionMatrix({ 'yes': 45, 'no': 30 }, 60.0),
        notes: "Raters are interpreting the question differently. Needs urgent attention.",
        warning: "Low agreement score detected. This suggests inconsistent scoring between raters."
      }
    ),
  },
}; 