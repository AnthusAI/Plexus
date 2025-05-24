import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { ScorecardReportEvaluation, type ScorecardReportEvaluationData } from '@/components/ui/scorecard-evaluation';

const meta: Meta<typeof ScorecardReportEvaluation> = {
  title: 'Reports/Components/ScorecardReportEvaluation',
  component: ScorecardReportEvaluation,
  parameters: {
    layout: 'padded',
  },
  decorators: [
    (Story) => (
      <div className="w-full">
        <Story />
      </div>
    ),
  ],
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

// Mock attached files for testing confusion matrix interactions
const mockAttachedFiles = JSON.stringify([
  { name: 'score-1-results.json', path: 'reports/score-details.json' },
  { name: 'Full Report.pdf', path: 'reports/full-report.pdf' },
]);

// Example identifiers data
const exampleIdentifiers = JSON.stringify([
  { name: "form ID", id: "56288648", url: "https://app.callcriteria.com/r/56288648" },
  { name: "XCC ID", id: "44548" },
  { name: "session ID", id: "C6CDE6E4908045B9BDC2C0D46ACDA8E9" }
]);

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
        ac1: 0.82, // Add AC1 agreement score (comes first)
        class_distribution: createClassDistribution({ 'Business': 80, 'Technology': 60, 'Health': 40, 'Entertainment': 20 }),
        confusion_matrix: createConfusionMatrix({ 'Business': 80, 'Technology': 60, 'Health': 40, 'Entertainment': 20 }, 87.5)
      }
    ),
    scoreIndex: 0,
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
    scoreIndex: 0,
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
    scoreIndex: 0,
    showPrecisionRecall: false
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
    scoreIndex: 0,
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
    scoreIndex: 0,
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
    scoreIndex: 0,
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
    scoreIndex: 0,
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
    scoreIndex: 0,
  },
};

export const WithConfusionMatrix: Story = {
  args: {
    score: createScoreData(
      'score-confusion-matrix',
      'Confusion Matrix Display',
      150,
      25,
      83.3,
      { 'Positive': 85, 'Neutral': 35, 'Negative': 30 },
      {
        precision: 85.2,
        recall: 82.1,
        class_distribution: createClassDistribution({ 'Positive': 85, 'Neutral': 35, 'Negative': 30 }),
        predicted_class_distribution: createClassDistribution({ 'Positive': 87, 'Neutral': 33, 'Negative': 30 }),
        confusion_matrix: createConfusionMatrix({ 'Positive': 85, 'Neutral': 35, 'Negative': 30 }, 83.3),
        notes: "Shows confusion matrix without interactive drilling (no attached files)."
      }
    ),
    scoreIndex: 0,
    showPrecisionRecall: true
  },
};

export const WithConfusionMatrixInteraction: Story = {
  args: {
    score: createScoreData(
      'score-interactive',
      'Interactive Confusion Matrix',
      150,
      25,
      83.3,
      { 'Positive': 85, 'Neutral': 35, 'Negative': 30 },
      {
        precision: 85.2,
        recall: 82.1,
        class_distribution: createClassDistribution({ 'Positive': 85, 'Neutral': 35, 'Negative': 30 }),
        predicted_class_distribution: createClassDistribution({ 'Positive': 87, 'Neutral': 33, 'Negative': 30 }),
        confusion_matrix: createConfusionMatrix({ 'Positive': 85, 'Neutral': 35, 'Negative': 30 }, 83.3),
        notes: "Click on confusion matrix cells to see detailed item breakdown (with attached files)."
      }
    ),
    scoreIndex: 0,
    attachedFiles: mockAttachedFiles,
    showPrecisionRecall: true
  },
};

export const WithEditorInfo: Story = {
  args: {
    score: createScoreData(
      'score-editor',
      'Score With Editor Information',
      100,
      15,
      85.0,
      { 'yes': 70, 'no': 30 },
      {
        ac1: 0.78,
        class_distribution: createClassDistribution({ 'yes': 70, 'no': 30 }),
        confusion_matrix: createConfusionMatrix({ 'yes': 70, 'no': 30 }, 85.0),
        editorName: "SQ KKunkle",
        editedAt: "2025-05-21 09:52:00+00:00",
        notes: "Score has been manually reviewed and adjusted."
      }
    ),
    scoreIndex: 0,
  },
};

export const WithIdentifiers: Story = {
  args: {
    score: createScoreData(
      'score-identifiers',
      'Score With Identifiers',
      80,
      12,
      85.0,
      { 'yes': 60, 'no': 20 },
      {
        ac1: 0.82,
        class_distribution: createClassDistribution({ 'yes': 60, 'no': 20 }),
        confusion_matrix: createConfusionMatrix({ 'yes': 60, 'no': 20 }, 85.0),
        item: {
          id: "febec68a-417f-4074-8dbe-2e08648039f1",
          identifiers: exampleIdentifiers,
          externalId: "44548"
        }
      }
    ),
    scoreIndex: 0,
  },
};

export const WithAllFeatures: Story = {
  args: {
    score: createScoreData(
      'score-all-features',
      'All Features Demo',
      200,
      30,
      85.0,
      { 'High': 70, 'Medium': 80, 'Low': 50 },
      {
        ac1: 0.75,
        precision: 87.2,
        recall: 83.8,
        class_distribution: createClassDistribution({ 'High': 70, 'Medium': 80, 'Low': 50 }),
        predicted_class_distribution: createClassDistribution({ 'High': 72, 'Medium': 78, 'Low': 50 }),
        confusion_matrix: createConfusionMatrix({ 'High': 70, 'Medium': 80, 'Low': 50 }, 85.0),
        notes: "This score demonstrates all available features including metrics, visualizations, and metadata.",
        discussion: "This comprehensive example shows how all the different components work together. The model achieves good overall performance with balanced precision and recall. The confusion matrix reveals some interesting patterns in misclassification, particularly between adjacent categories. The class distribution visualization helps understand the data balance, while the predicted distribution shows how the model's outputs compare to the ground truth.",
        warning: "This is a demonstration warning to show how warnings are displayed.",
        editorName: "Demo User",
        editedAt: "2025-05-24 12:00:00+00:00",
        item: {
          id: "demo-item-id",
          identifiers: exampleIdentifiers,
          externalId: "DEMO123"
        }
      }
    ),
    scoreIndex: 0,
    attachedFiles: mockAttachedFiles,
    showPrecisionRecall: true
  },
};

// Responsive story that allows testing different widths with a resizable container
export const ResponsiveWidth: Story = {
  decorators: [
    (Story) => (
      <div className="w-full p-4 space-y-4">
        <div className="text-sm text-muted-foreground">
          📐 This story shows the component at different fixed widths to test responsive behavior:
        </div>
        <div className="space-y-8">
          <div className="space-y-2">
            <div className="text-xs font-medium text-muted-foreground">Mobile (320px)</div>
            <div className="w-80 border border-dashed border-muted-foreground p-4">
              <Story />
            </div>
          </div>
          <div className="space-y-2">
            <div className="text-xs font-medium text-muted-foreground">Tablet (600px)</div>
            <div className="w-[600px] border border-dashed border-muted-foreground p-4">
              <Story />
            </div>
          </div>
          <div className="space-y-2">
            <div className="text-xs font-medium text-muted-foreground">Desktop (800px)</div>
            <div className="w-[800px] border border-dashed border-muted-foreground p-4">
              <Story />
            </div>
          </div>
        </div>
      </div>
    ),
  ],
  args: {
    score: createScoreData(
      'score-responsive',
      'Responsive Layout Test',
      150,
      20,
      86.7,
      { 'Category A': 60, 'Category B': 50, 'Category C': 40 },
      {
        ac1: 0.78,
        precision: 88.2,
        recall: 85.4,
        class_distribution: createClassDistribution({ 'Category A': 60, 'Category B': 50, 'Category C': 40 }),
        predicted_class_distribution: createClassDistribution({ 'Category A': 62, 'Category B': 48, 'Category C': 40 }),
        confusion_matrix: createConfusionMatrix({ 'Category A': 60, 'Category B': 50, 'Category C': 40 }, 86.7),
        notes: "Resize the container to see how the layout adapts to different widths."
      }
    ),
    scoreIndex: 0,
    showPrecisionRecall: true
  },
};

export const MinimalData: Story = {
  args: {
    score: createScoreData(
      'score-minimal',
      'Minimal Data',
      50,
      10,
      80.0
    ),
    scoreIndex: 0,
  },
};

// Multi-score grid story to show how multiple evaluation components look together
export const MultipleScoresGrid: Story = {
  decorators: [
    (Story) => (
      <div className="w-full">
        <div className="@container">
          <div className="grid grid-cols-1 @[60rem]:grid-cols-2 gap-3">
            {/* Render multiple score evaluation components */}
            <Story />
            <div className="min-w-[280px]">
              {/* Second score */}
              <ScorecardReportEvaluation
                score={createScoreData(
                  'score2',
                  'Sentiment Analysis',
                  150,
                  15,
                  90.0,
                  { 'Positive': 90, 'Neutral': 40, 'Negative': 20 },
                  {
                    ac1: 0.85,
                    precision: 92.3,
                    recall: 88.7,
                    class_distribution: createClassDistribution({ 'Positive': 90, 'Neutral': 40, 'Negative': 20 }),
                    predicted_class_distribution: createClassDistribution({ 'Positive': 93, 'Neutral': 37, 'Negative': 20 }),
                    confusion_matrix: createConfusionMatrix({ 'Positive': 90, 'Neutral': 40, 'Negative': 20 }, 90.0)
                  }
                )}
                scoreIndex={1}
                showPrecisionRecall={true}
              />
            </div>
            <div className="min-w-[280px]">
              {/* Third score */}
              <ScorecardReportEvaluation
                score={createScoreData(
                  'score3',
                  'Intent Recognition',
                  180,
                  30,
                  83.3,
                  { 'Purchase': 70, 'Browse': 60, 'Support': 50 },
                  {
                    ac1: 0.69,
                    precision: 85.6,
                    recall: 82.1,
                    class_distribution: createClassDistribution({ 'Purchase': 70, 'Browse': 60, 'Support': 50 }),
                    predicted_class_distribution: createClassDistribution({ 'Purchase': 72, 'Browse': 58, 'Support': 50 }),
                    confusion_matrix: createConfusionMatrix({ 'Purchase': 70, 'Browse': 60, 'Support': 50 }, 83.3),
                    warning: "Lower agreement score suggests review of classification criteria may be needed."
                  }
                )}
                scoreIndex={2}
                showPrecisionRecall={true}
              />
            </div>
            <div className="min-w-[280px]">
              {/* Fourth score */}
              <ScorecardReportEvaluation
                score={createScoreData(
                  'score4',
                  'Call Quality Assessment',
                  100,
                  5,
                  95.0,
                  { 'Excellent': 60, 'Good': 30, 'Poor': 10 },
                  {
                    ac1: 0.92,
                    precision: 94.2,
                    recall: 95.8,
                    class_distribution: createClassDistribution({ 'Excellent': 60, 'Good': 30, 'Poor': 10 }),
                    predicted_class_distribution: createClassDistribution({ 'Excellent': 62, 'Good': 28, 'Poor': 10 }),
                    confusion_matrix: createConfusionMatrix({ 'Excellent': 60, 'Good': 30, 'Poor': 10 }, 95.0),
                    notes: "Excellent inter-rater reliability with minimal disagreements."
                  }
                )}
                scoreIndex={3}
                showPrecisionRecall={true}
              />
            </div>
          </div>
        </div>
      </div>
    ),
  ],
  args: {
    score: createScoreData(
      'score1',
      'Topic Classification',
      200,
      25,
      87.5,
      { 'Business': 80, 'Technology': 60, 'Health': 40, 'Entertainment': 20 },
      {
        ac1: 0.82,
        precision: 89.1,
        recall: 85.4,
        class_distribution: createClassDistribution({ 'Business': 80, 'Technology': 60, 'Health': 40, 'Entertainment': 20 }),
        predicted_class_distribution: createClassDistribution({ 'Business': 82, 'Technology': 58, 'Health': 40, 'Entertainment': 20 }),
        confusion_matrix: createConfusionMatrix({ 'Business': 80, 'Technology': 60, 'Health': 40, 'Entertainment': 20 }, 87.5)
      }
    ),
    scoreIndex: 0,
    showPrecisionRecall: true
  },
};