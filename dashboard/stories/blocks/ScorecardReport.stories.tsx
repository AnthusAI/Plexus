import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { BlockRenderer } from '@/components/blocks/BlockRegistry';
import ScorecardReport from '@/components/blocks/ScorecardReport';
import { type ClassDistribution } from '@/components/ClassDistributionVisualizer';
import { type ConfusionMatrixData } from '@/components/confusion-matrix';

const meta: Meta<typeof BlockRenderer> = {
  title: 'Report Blocks/ScorecardReport',
  component: BlockRenderer,
  parameters: {
    layout: 'padded',
  },
};

export default meta;
type Story = StoryObj<typeof BlockRenderer>;

const baseScorecardReportData = {
  total_items: 0, // Will be overridden
  total_agreements: 0, // Will be overridden
  accuracy: 0, // Will be overridden
  overall_agreement: null, // Will be overridden
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
  accuracy: number,
  comparisons: number, 
  mismatches: number, 
  labelDistribution?: Record<string, number>,
  showPrecisionRecall = true,
  agreement?: number
) => {
  const baseScore = {
    id,
    score_name: name,
    item_count: comparisons,
    mismatches,
    accuracy,
    label_distribution: labelDistribution,
    ac1: agreement, // Include agreement score at individual level
  };
  
  // Add visualization data if label distribution is provided
  if (labelDistribution) {
    return {
      ...baseScore,
      precision: showPrecisionRecall ? accuracy + Math.random() * 5 - 2.5 : undefined, // Random value near accuracy for demo
      recall: showPrecisionRecall ? accuracy + Math.random() * 5 - 2.5 : undefined, // Random value near accuracy for demo
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

// Add mock attachedFiles for testing the UI buttons
const mockAttachedFiles = JSON.stringify([
  { name: 'Full Report.pdf', path: 'dummy/report.pdf' },
  { name: 'Data Export.csv', path: 'dummy/data.csv' },
]);

export const BasicScorecardReport: Story = {
  args: {
    name: 'Model Performance',
    type: 'ScorecardReport',
    position: 0,
    log: 'Log for scorecard report analysis.',
    attachedFiles: mockAttachedFiles, // Add the mock attached files
    config: { // Mock config passed to the block
      class: 'ScorecardReport',
      model_id: 'some-model-id',
      days: 30,
    },
    output: { // This is the actual data structure the component expects
      ...baseScorecardReportData,
      overall_agreement: 0.78, // Add overall agreement score
      scores: [
        scoreTemplate('score1', 'Topic Classification', 88.5, 200, 23, { 'Business': 80, 'Technology': 60, 'Health': 40, 'Entertainment': 20 }, true, 0.82),
        scoreTemplate('score2', 'Sentiment Analysis', 92.7, 150, 11, { 'Positive': 90, 'Neutral': 40, 'Negative': 20 }, true, 0.85),
        scoreTemplate('score3', 'Intent Recognition', 76.4, 180, 42, { 'Purchase': 70, 'Browse': 60, 'Support': 50 }, true, 0.69),
      ],
      total_items: 530,
      total_agreements: 454, // 530 - 76
      accuracy: 85.7,
      label_distribution: { 
        'Business': 80, 'Technology': 60, 'Health': 40, 'Entertainment': 20,
        'Positive': 90, 'Neutral': 40, 'Negative': 20,
        'Purchase': 70, 'Browse': 60, 'Support': 50
      }
    },
  },
};

export const WithCustomTitle: Story = {
  args: {
    ...BasicScorecardReport.args,
    name: 'Custom Title Report',
    config: {
      class: 'ScorecardReport',
      model_id: 'another-model-id',
      days: 60,
      title: 'ML Performance Metrics',
      subtitle: 'Quarterly evaluation results',
    },
  },
};

export const WithPrecisionRecall: Story = {
  args: {
    name: 'Model Precision and Recall',
    type: 'ScorecardReport',
    position: 1,
    log: 'Log for scorecard with precision/recall.',
    config: {
      class: 'ScorecardReport',
      model_id: 'precision-recall-model',
      days: 30,
      showPrecisionRecall: true,
    },
    output: {
      ...baseScorecardReportData,
      overall_agreement: 0.80, // Add overall agreement score
      scores: [
        scoreTemplate('score1', 'Topic Classification', 88.5, 200, 23, { 'Business': 80, 'Technology': 60, 'Health': 40, 'Entertainment': 20 }, true, 0.82),
        scoreTemplate('score2', 'Sentiment Analysis', 92.7, 150, 11, { 'Positive': 90, 'Neutral': 40, 'Negative': 20 }, true, 0.85),
        scoreTemplate('score3', 'Intent Recognition', 76.4, 180, 42, { 'Purchase': 70, 'Browse': 60, 'Support': 50 }, true, 0.69),
      ],
      total_items: 530,
      total_agreements: 454, // 530 - 76
      accuracy: 85.7,
      label_distribution: { 
        'Business': 80, 'Technology': 60, 'Health': 40, 'Entertainment': 20,
        'Positive': 90, 'Neutral': 40, 'Negative': 20,
        'Purchase': 70, 'Browse': 60, 'Support': 50
      }
    },
  },
};

export const WithoutPrecisionRecall: Story = {
  args: {
    name: 'Basic Metrics Only',
    type: 'ScorecardReport',
    position: 2,
    log: 'Log for scorecard without precision/recall.',
    config: {
      class: 'ScorecardReport',
      model_id: 'basic-metrics-model',
      days: 30,
      showPrecisionRecall: false,
    },
    output: {
      ...baseScorecardReportData,
      overall_agreement: 0.75, // Add overall agreement score
      scores: [
        scoreTemplate('score1', 'Topic Classification', 88.5, 200, 23, { 'Business': 80, 'Technology': 60, 'Health': 40, 'Entertainment': 20 }, false, 0.82),
        scoreTemplate('score2', 'Sentiment Analysis', 92.7, 150, 11, { 'Positive': 90, 'Neutral': 40, 'Negative': 20 }, false, 0.85),
        scoreTemplate('score3', 'Intent Recognition', 76.4, 180, 42, { 'Purchase': 70, 'Browse': 60, 'Support': 50 }, false, 0.69),
      ],
      total_items: 530,
      total_agreements: 454, // 530 - 76
      accuracy: 85.7,
      label_distribution: { 
        'Business': 80, 'Technology': 60, 'Health': 40, 'Entertainment': 20,
        'Positive': 90, 'Neutral': 40, 'Negative': 20,
        'Purchase': 70, 'Browse': 60, 'Support': 50
      }
    },
  },
};

export const WithWarnings: Story = {
  args: {
    name: 'Report With Warnings',
    type: 'ScorecardReport',
    position: 3,
    log: 'Log for scorecard with warnings.',
    config: {
      class: 'ScorecardReport',
      model_id: 'warning-model',
      days: 45,
    },
    output: {
      ...baseScorecardReportData,
      overall_agreement: 0.59, // Lower agreement for reports with warnings
      scores: [
        scoreTemplate('score1', 'Topic Classification', 88.5, 200, 23, { 'Business': 80, 'Technology': 60, 'Health': 40, 'Entertainment': 20 }, true, 0.78),
        {
          ...scoreTemplate('score2', 'Sentiment Analysis', 65.3, 150, 52, { 'Positive': 90, 'Neutral': 40, 'Negative': 20 }, true, 0.61),
          warning: "Low accuracy detected. Model may need retraining for this classification task."
        },
        {
          ...scoreTemplate('score3', 'Intent Recognition', 56.4, 180, 78, { 'Purchase': 70, 'Browse': 60, 'Support': 50 }, true, 0.45),
          warning: "Critical performance issue: Accuracy below acceptable threshold (75%). This indicates poor model performance."
        },
      ],
      total_items: 530,
      total_agreements: 377, // 530 - 153
      accuracy: 71.1,
      label_distribution: { 
        'Business': 80, 'Technology': 60, 'Health': 40, 'Entertainment': 20,
        'Positive': 90, 'Neutral': 40, 'Negative': 20,
        'Purchase': 70, 'Browse': 60, 'Support': 50
      }
    },
  },
};

export const WithNotesAndDiscussion: Story = {
  args: {
    name: 'Report With Notes',
    type: 'ScorecardReport',
    position: 4,
    log: 'Log for scorecard with notes and discussion.',
    config: {
      class: 'ScorecardReport',
      model_id: 'notes-model',
      days: 30,
    },
    output: {
      ...baseScorecardReportData,
      overall_agreement: 0.76, // Add overall agreement score
      scores: [
        {
          ...scoreTemplate('score1', 'Topic Classification', 88.5, 200, 23, { 'Business': 80, 'Technology': 60, 'Health': 40, 'Entertainment': 20 }, true, 0.80),
          notes: "Model performs well across all categories."
        },
        {
          ...scoreTemplate('score2', 'Sentiment Analysis', 92.7, 150, 11, { 'Positive': 90, 'Neutral': 40, 'Negative': 20 }, true, 0.88),
          discussion: "The sentiment analysis model shows excellent performance with 92.7% accuracy. The precision (94.1%) and recall (91.3%) metrics indicate that the model has a good balance between minimizing false positives and false negatives. The model performs particularly well on positive sentiment detection, which aligns with our business goals of identifying satisfied customers. However, there's a slight imbalance in the dataset with fewer negative samples (20% of total), which may impact the model's ability to generalize to real-world data where negative sentiment could be more prevalent."
        },
        {
          ...scoreTemplate('score3', 'Intent Recognition', 76.4, 180, 42, { 'Purchase': 70, 'Browse': 60, 'Support': 50 }, true, 0.65),
          notes: "Performance is acceptable but could be improved.",
          discussion: "The intent recognition model achieves moderate performance with 76.4% accuracy. While this is above our minimum threshold of 75%, there's room for improvement. The confusion matrix shows that most errors occur between 'Browse' and 'Purchase' intents, suggesting that these categories may have overlapping features or that our training data doesn't sufficiently distinguish between casual browsing behavior and serious purchase intent. Recommended actions include: 1) Refining the feature extraction process to better capture purchase signals, and 2) Collecting more balanced training data for these two categories."
        }
      ],
      total_items: 530,
      total_agreements: 454, // 530 - 76
      accuracy: 85.7,
      label_distribution: { 
        'Business': 80, 'Technology': 60, 'Health': 40, 'Entertainment': 20,
        'Positive': 90, 'Neutral': 40, 'Negative': 20,
        'Purchase': 70, 'Browse': 60, 'Support': 50
      }
    },
  },
};

export const NoScores: Story = {
  args: {
    name: 'Empty Report',
    type: 'ScorecardReport',
    position: 5,
    config: {
      class: 'ScorecardReport',
      model_id: 'empty-model-id',
    },
    output: {
      ...baseScorecardReportData,
      overall_agreement: null, // No agreement for empty report
      scores: [],
      total_items: 0,
      total_agreements: 0,
      accuracy: 0,
    },
  },
};

export const WithoutDateRange: Story = {
  args: {
    name: 'Report Without Date Range',
    type: 'ScorecardReport',
    position: 6,
    log: 'Log for scorecard without date range.',
    config: {
      class: 'ScorecardReport',
      model_id: 'no-date-range-model',
      days: 30,
      showDateRange: false,
    },
    output: {
      ...baseScorecardReportData,
      overall_agreement: 0.82,
      scores: [
        scoreTemplate('score1', 'Topic Classification', 88.5, 200, 23, { 'Business': 80, 'Technology': 60, 'Health': 40, 'Entertainment': 20 }, true, 0.82),
        scoreTemplate('score2', 'Sentiment Analysis', 92.7, 150, 11, { 'Positive': 90, 'Neutral': 40, 'Negative': 20 }, true, 0.85),
      ],
      total_items: 350,
      total_agreements: 34,
      accuracy: 90.3,
      label_distribution: { 
        'Business': 80, 'Technology': 60, 'Health': 40, 'Entertainment': 20,
        'Positive': 90, 'Neutral': 40, 'Negative': 20
      }
    },
  },
};

export const WithReportNotes: Story = {
  args: {
    name: 'Report With Descriptive Notes',
    type: 'ScorecardReport',
    position: 7,
    log: 'Log for scorecard with notes.',
    config: {
      class: 'ScorecardReport',
      model_id: 'notes-model',
      days: 30,
      title: 'Quarterly Model Evaluation',
      subtitle: 'Q1 2023 Results',
      notes: 'This report evaluates the performance of our production machine learning models across three key classification tasks. The evaluation is based on a randomly selected sample of 530 items from our production data during Q1 2023. Each item was independently scored by two expert annotators, and disagreements were reconciled by a third senior annotator. The metrics presented here reflect model performance against this gold standard dataset. Note that performance across different categories varies significantly, with sentiment analysis showing the strongest results and intent recognition requiring additional attention.',
    },
    output: {
      ...baseScorecardReportData,
      overall_agreement: 0.79,
      scores: [
        scoreTemplate('score1', 'Topic Classification', 88.5, 200, 23, { 'Business': 80, 'Technology': 60, 'Health': 40, 'Entertainment': 20 }, true, 0.82),
        scoreTemplate('score2', 'Sentiment Analysis', 92.7, 150, 11, { 'Positive': 90, 'Neutral': 40, 'Negative': 20 }, true, 0.85),
        scoreTemplate('score3', 'Intent Recognition', 76.4, 180, 42, { 'Purchase': 70, 'Browse': 60, 'Support': 50 }, true, 0.69),
      ],
      total_items: 530,
      total_agreements: 454, // 530 - 76
      accuracy: 85.7,
      label_distribution: { 
        'Business': 80, 'Technology': 60, 'Health': 40, 'Entertainment': 20,
        'Positive': 90, 'Neutral': 40, 'Negative': 20,
        'Purchase': 70, 'Browse': 60, 'Support': 50
      }
    },
  },
};

export const WithReportWarningAndError: Story = {
  args: {
    name: 'Reports With Warning and Error',
    type: 'ScorecardReport',
    position: 8,
    log: 'Log for scorecard with report-level warnings and errors.',
    config: {
      class: 'ScorecardReport',
      model_id: 'warning-error-model',
      days: 30,
      title: 'Model Evaluation with Warnings',
      subtitle: 'Demonstrating report-level warnings and errors',
    },
    output: {
      ...baseScorecardReportData,
      overall_agreement: 0.76,
      scores: [
        scoreTemplate('score1', 'Topic Classification', 88.5, 200, 23, { 'Business': 80, 'Technology': 60, 'Health': 40, 'Entertainment': 20 }, true, 0.82),
        scoreTemplate('score2', 'Sentiment Analysis', 92.7, 150, 11, { 'Positive': 90, 'Neutral': 40, 'Negative': 20 }, true, 0.85),
      ],
      total_items: 350,
      total_agreements: 316, // 350 - 34
      accuracy: 90.3,
      label_distribution: { 
        'Business': 80, 'Technology': 60, 'Health': 40, 'Entertainment': 20,
        'Positive': 90, 'Neutral': 40, 'Negative': 20
      },
      warning: "Some model evaluations are missing. This report may not reflect the full performance profile."
    },
  },
};

export const WithReportError: Story = {
  args: {
    name: 'Report With Error',
    type: 'ScorecardReport',
    position: 9,
    log: 'Log for scorecard with report-level error.',
    config: {
      class: 'ScorecardReport',
      model_id: 'error-model',
      days: 30,
      title: 'Model Evaluation with Error',
      subtitle: 'Demonstrating report-level error message',
    },
    output: {
      ...baseScorecardReportData,
      overall_agreement: 0.68,
      scores: [
        scoreTemplate('score1', 'Topic Classification', 76.5, 180, 42, { 'Business': 70, 'Technology': 50, 'Health': 30, 'Entertainment': 30 }, true, 0.71),
      ],
      total_items: 180,
      total_agreements: 138, // 180 - 42
      accuracy: 76.5,
      label_distribution: { 
        'Business': 70, 'Technology': 50, 'Health': 30, 'Entertainment': 30
      },
      error: "Critical data integrity issue detected: 23% of evaluation samples could not be processed due to missing ground truth labels."
    },
  },
};

export const WithAttachmentsAndLogs: Story = {
  args: {
    name: 'Report With Attachments and Logs',
    type: 'ScorecardReport',
    position: 10,
    log: 'This is an example log content.\nIt contains multiple lines.\nEach line demonstrates some log information.\n\nLogs are important for debugging and understanding what happened during report generation.\n\nThis is a lot of log content to demonstrate scrolling behavior.\nMore lines...\nAnd more lines...\nAnd even more lines...',
    attachedFiles: mockAttachedFiles,
    config: {
      class: 'ScorecardReport',
      model_id: 'logs-attachments-model',
      days: 30,
      title: 'Attachment & Log Testing',
      subtitle: 'Demonstrates buttons and UI for logs and file attachments',
      notes: 'This example specifically demonstrates the log and attachment capabilities of report blocks.'
    },
    output: {
      ...baseScorecardReportData,
      overall_agreement: 0.82,
      scores: [
        scoreTemplate('score1', 'Demo Score', 90.0, 100, 10, { 'ClassA': 50, 'ClassB': 50 }, true, 0.82),
      ],
      total_items: 100,
      total_agreements: 90,
      accuracy: 90.0,
      label_distribution: { 'ClassA': 50, 'ClassB': 50 },
      updatedAt: '2023-10-26T10:00:00Z',
      log: "Evaluation task completed successfully"
    },
  },
}; 