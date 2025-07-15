import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { FeedbackAnalysisDisplay } from '@/components/ui/feedback-analysis-display';
import { type ClassDistribution } from '@/components/ClassDistributionVisualizer';
import { type ConfusionMatrixData } from '@/components/confusion-matrix';

const meta: Meta<typeof FeedbackAnalysisDisplay> = {
  title: 'UI/FeedbackAnalysisDisplay',
  component: FeedbackAnalysisDisplay,
  parameters: {
    layout: 'padded',
  },
  argTypes: {
    showDateRange: {
      control: 'boolean',
      description: 'Whether to show the date range in the analysis'
    },
    showPrecisionRecall: {
      control: 'boolean',
      description: 'Whether to show precision/recall gauges'
    },
    onCellSelection: {
      action: 'cellSelected',
      description: 'Called when a confusion matrix cell is selected'
    }
  }
};

export default meta;
type Story = StoryObj<typeof FeedbackAnalysisDisplay>;

// Helper functions to create mock data
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

const createScoreData = (
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
    question: name,
    cc_question_id: `ext-${id}`,
    ac1,
    item_count: comparisons,
    mismatches,
    accuracy,
    label_distribution: labelDistribution,
  };
  
  if (labelDistribution) {
    return {
      ...baseScore,
      class_distribution: createClassDistribution(labelDistribution),
      predicted_class_distribution: createClassDistribution(
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

const baseFeedbackAnalysisData = {
  total_items: 0,
  total_agreements: 0, 
  total_mismatches: 0,
  accuracy: 0,
  date_range: {
    start: '2023-01-01T00:00:00Z',
    end: '2023-01-31T23:59:59Z',
  },
};

export const SingleScore: Story = {
  args: {
    title: 'Single Score Analysis',
    subtitle: 'Analysis of one score with good performance',
    data: {
      ...baseFeedbackAnalysisData,
      overall_ac1: 0.75,
      scores: [
        createScoreData('score1', 'Agent Empathy', 0.75, 50, 12, 76.0, { 'Excellent': 30, 'Good': 15, 'Poor': 5 }),
      ],
      total_items: 50,
      total_agreements: 38,
      total_mismatches: 12,
      accuracy: 76.0,
      label_distribution: { 'Excellent': 30, 'Good': 15, 'Poor': 5 }
    }
  }
};

export const MultipleScores: Story = {
  args: {
    title: 'Multiple Scores Analysis',
    subtitle: 'Comprehensive scorecard analysis',
    data: {
      ...baseFeedbackAnalysisData,
      overall_ac1: 0.82,
      scores: [
        createScoreData('score1', 'Agent Empathy', 0.75, 50, 12, 76.0, { 'High': 25, 'Medium': 15, 'Low': 10 }),
        createScoreData('score2', 'Problem Resolution', 0.88, 60, 7, 88.3, { 'Resolved': 45, 'Unresolved': 15 }),
        createScoreData('score3', 'Product Knowledge', 0.65, 45, 16, 64.4, { 'Expert': 15, 'Proficient': 20, 'Basic': 10 }),
        createScoreData('score4', 'Call Opening', null, 10, 5, 50.0, { 'Good': 5, 'Poor': 5 }),
      ],
      total_items: 165,
      total_agreements: 125,
      total_mismatches: 40,
      accuracy: 75.8,
      label_distribution: { 'High': 25, 'Medium': 15, 'Low': 10, 'Resolved': 45, 'Unresolved': 15, 'Expert': 15, 'Proficient': 20, 'Basic': 10, 'Good': 5, 'Poor': 5 }
    }
  }
};

export const BinaryClassification: Story = {
  args: {
    title: 'Binary Classification Analysis',
    subtitle: 'Simple yes/no classification performance',
    data: {
      ...baseFeedbackAnalysisData,
      overall_ac1: 0.65,
      scores: [
        createScoreData('score1', 'Policy Violation', 0.65, 100, 25, 75.0, { 'Yes': 50, 'No': 50 }),
      ],
      total_items: 100,
      total_agreements: 75,
      total_mismatches: 25,
      accuracy: 75.0,
      label_distribution: { 'Yes': 50, 'No': 50 }
    }
  }
};

export const ImbalancedClasses: Story = {
  args: {
    title: 'Imbalanced Classes Analysis',
    subtitle: 'Analysis with severely imbalanced class distribution',
    data: {
      ...baseFeedbackAnalysisData,
      overall_ac1: 0.25,
      scores: [
        createScoreData('score1', 'Rare Event Detection', 0.25, 100, 5, 95.0, { 'Normal': 95, 'Anomaly': 5 }),
      ],
      total_items: 100,
      total_agreements: 95,
      total_mismatches: 5,
      accuracy: 95.0,
      label_distribution: { 'Normal': 95, 'Anomaly': 5 }
    }
  }
};

export const WithWarnings: Story = {
  args: {
    title: 'Analysis with Warnings',
    subtitle: 'Scores with reliability concerns',
    data: {
      ...baseFeedbackAnalysisData,
      overall_ac1: 0.45,
      scores: [
        createScoreData('score1', 'Agent Empathy', 0.75, 50, 12, 76.0, { 'High': 25, 'Medium': 15, 'Low': 10 }),
        {
          ...createScoreData('score2', 'Product Knowledge', 0.22, 50, 22, 56.0, { 'Expert': 10, 'Proficient': 25, 'Basic': 15 }),
          warning: "Critical reliability concern: AC1 score below acceptable threshold (0.4). This indicates poor inter-rater reliability."
        },
        {
          ...createScoreData('score3', 'Call Handling', 0.48, 15, 4, 73.3, { 'Excellent': 8, 'Good': 4, 'Poor': 3 }),
          warning: "Insufficient data: Only 15 samples available. Results may not be statistically significant."
        }
      ],
      total_items: 115,
      total_agreements: 77,
      total_mismatches: 38,
      accuracy: 67.0,
      label_distribution: { 'High': 25, 'Medium': 15, 'Low': 10, 'Expert': 10, 'Proficient': 25, 'Basic': 15, 'Excellent': 8, 'Good': 4, 'Poor': 3 }
    }
  }
};

export const WithNotesAndDiscussion: Story = {
  args: {
    title: 'Detailed Analysis Report',
    subtitle: 'Analysis with comprehensive notes and discussion',
    data: {
      ...baseFeedbackAnalysisData,
      overall_ac1: 0.72,
      scores: [
        {
          ...createScoreData('score1', 'Agent Empathy', 0.75, 50, 12, 76.0, { 'High': 25, 'Medium': 15, 'Low': 10 }),
          notes: "Shows strong agreement between raters. Training seems to be working well."
        },
        {
          ...createScoreData('score2', 'Problem Resolution', 0.88, 60, 7, 88.3, { 'Resolved': 45, 'Unresolved': 15 }),
          discussion: "Problem resolution scores show excellent alignment between raters with an AC1 of 0.88. This is the highest agreement score across all evaluated categories, suggesting that the rating criteria for this question are very clear and consistently applied."
        },
        {
          ...createScoreData('score3', 'Product Knowledge', 0.65, 45, 16, 64.4, { 'Expert': 15, 'Proficient': 20, 'Basic': 10 }),
          notes: "Moderate agreement between raters. Further clarification of 'Proficient' vs 'Basic' may help.",
          discussion: "The product knowledge assessment shows moderate agreement (AC1 0.65) between raters. Most disagreements occurred between 'Proficient' and 'Basic' ratings, suggesting some ambiguity in distinguishing these levels."
        }
      ],
      total_items: 155,
      total_agreements: 120,
      total_mismatches: 35,
      accuracy: 77.4,
      label_distribution: { 'High': 25, 'Medium': 15, 'Low': 10, 'Resolved': 45, 'Unresolved': 15, 'Expert': 15, 'Proficient': 20, 'Basic': 10 }
    }
  }
};

export const EmptyState: Story = {
  args: {
    title: 'No Data Available',
    subtitle: 'Analysis when no feedback data is available',
    data: {
      ...baseFeedbackAnalysisData,
      overall_ac1: null,
      scores: [],
      total_items: 0,
      total_agreements: 0,
      total_mismatches: 0,
      accuracy: 0,
      label_distribution: {}
    }
  }
};

export const WithoutDateRange: Story = {
  args: {
    title: 'Analysis Without Date Range',
    subtitle: 'Display without showing date range',
    showDateRange: false,
    data: {
      ...baseFeedbackAnalysisData,
      overall_ac1: 0.68,
      scores: [
        createScoreData('score1', 'Customer Satisfaction', 0.68, 80, 20, 75.0, { 'Satisfied': 50, 'Neutral': 20, 'Dissatisfied': 10 }),
      ],
      total_items: 80,
      total_agreements: 60,
      total_mismatches: 20,
      accuracy: 75.0,
      label_distribution: { 'Satisfied': 50, 'Neutral': 20, 'Dissatisfied': 10 }
    }
  }
};

export const WithPrecisionRecall: Story = {
  args: {
    title: 'Analysis with Precision/Recall',
    subtitle: 'Display including precision and recall gauges',
    showPrecisionRecall: true,
    data: {
      ...baseFeedbackAnalysisData,
      overall_ac1: 0.72,
      scores: [
        {
          ...createScoreData('score1', 'Sentiment Analysis', 0.72, 100, 18, 82.0, { 'Positive': 45, 'Neutral': 30, 'Negative': 25 }),
          precision: 0.78,
          recall: 0.85
        },
        {
          ...createScoreData('score2', 'Intent Classification', 0.80, 90, 12, 86.7, { 'Support': 40, 'Sales': 30, 'Billing': 20 }),
          precision: 0.82,
          recall: 0.84
        }
      ],
      total_items: 190,
      total_agreements: 160,
      total_mismatches: 30,
      accuracy: 84.2,
      label_distribution: { 'Positive': 45, 'Neutral': 30, 'Negative': 25, 'Support': 40, 'Sales': 30, 'Billing': 20 }
    }
  }
};

export const InteractiveConfusionMatrix: Story = {
  args: {
    title: 'Interactive Analysis',
    subtitle: 'Click on confusion matrix cells to explore feedback items',
    data: {
      ...baseFeedbackAnalysisData,
      overall_ac1: 0.58,
      scores: [
        createScoreData('score1', 'Topic Classification', 0.58, 120, 35, 70.8, { 'Tech': 40, 'Billing': 35, 'General': 30, 'Urgent': 15 }),
      ],
      total_items: 120,
      total_agreements: 85,
      total_mismatches: 35,
      accuracy: 70.8,
      label_distribution: { 'Tech': 40, 'Billing': 35, 'General': 30, 'Urgent': 15 }
    },
    onCellSelection: (selection) => {
      console.log('Cell selected:', selection);
    }
  }
};