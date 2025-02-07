import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import EvaluationTask from '@/components/EvaluationTask';
import type { EvaluationTaskProps } from '@/components/EvaluationTask';

const meta = {
  title: 'Tasks/Types/EvaluationTask',
  component: EvaluationTask,
  parameters: {
    layout: 'centered',
  },
} satisfies Meta<typeof EvaluationTask>;

export default meta;
type Story = StoryObj<typeof EvaluationTask>;

// Sample data for our stories
const createSampleData = () => {
  // Create realistic sample data for a lead qualification evaluation
  const labels = ["Qualified", "Not Qualified"]
  const sampleTexts = [
    "Hi, I'm interested in implementing AI for our customer service team of 500+ agents. We're looking to improve efficiency and reduce response times. What kind of solutions can you offer?",
    "Just browsing your website. Not really looking to buy anything right now.",
    "We need help with our call center operations. Currently handling about 10,000 calls per month and want to implement quality monitoring. What's your pricing?",
    "I'm a student doing research on AI companies. Can I get some information about your technology?",
    "Looking for an enterprise solution for our insurance claims processing. We process over 50,000 claims monthly and need to improve accuracy.",
  ]
  
  return {
    accuracy: 85.5,
    metrics: [
      { name: "Accuracy", value: 85.5, unit: "%", maximum: 100, priority: true },
      { name: "Precision", value: 88.2, unit: "%", maximum: 100, priority: true },
      { name: "Sensitivity", value: 82.1, unit: "%", maximum: 100, priority: true },
      { name: "Specificity", value: 91.3, unit: "%", maximum: 100, priority: true }
    ],
    metricsExplanation: "",
    scoreGoal: "Accuracy",
    processedItems: 150,
    totalItems: 200,
    progress: 75,
    inferences: 150,
    cost: 0.15,
    status: 'running',
    elapsedSeconds: 3600,
    estimatedRemainingSeconds: 1200,
    confusionMatrix: {
      matrix: [
        [45, 5],
        [10, 40]
      ],
      labels: labels
    },
    datasetClassDistribution: [
      { label: labels[0], count: 55 },
      { label: labels[1], count: 45 }
    ],
    isDatasetClassDistributionBalanced: true,
    predictedClassDistribution: [
      { label: labels[0], count: 50 },
      { label: labels[1], count: 50 }
    ],
    isPredictedClassDistributionBalanced: true,
    scoreResults: Array.from({ length: 20 }, (_, i) => {
      const isQualified = Math.random() > 0.4
      const correctPrediction = Math.random() > 0.15
      const sampleText = sampleTexts[i % sampleTexts.length]
      const confidence = 0.7 + (Math.random() * 0.3)
      
      const predictedLabel = correctPrediction ? 
        (isQualified ? labels[0] : labels[1]) :
        (isQualified ? labels[1] : labels[0])
      
      const explanation = isQualified ?
        (correctPrediction ?
          "Shows clear interest in enterprise-level solution with specific requirements and scale indicators." :
          "Missed qualification signals: Mentioned team size and specific use case requirements.") :
        (correctPrediction ?
          "No clear buying intent or business requirements mentioned." :
          "Incorrectly interpreted general interest as qualified lead.")

      return {
        id: `result-${i}`,
        value: predictedLabel,
        confidence,
        explanation,
        metadata: JSON.stringify({
          human_label: isQualified ? labels[0] : labels[1],
          correct: correctPrediction,
          human_explanation: isQualified ?
            "Represents enterprise client with clear needs and scale" :
            "No clear business need or purchasing authority indicated",
          text: sampleText
        }),
        createdAt: new Date().toISOString(),
        itemId: `item-${i}`,
        EvaluationId: 'eval-1',
        scorecardId: 'scorecard-1'
      }
    })
  }
}

// Base task props
const baseTask: EvaluationTaskProps = {
  variant: 'detail',
  task: {
    id: '1',
    type: 'Evaluation running',
    scorecard: 'Lead Qualification',
    score: 'Qualified Lead?',
    time: '2 hours ago',
    summary: 'Evaluating lead qualification accuracy',
    data: createSampleData()
  },
  isFullWidth: true,
  onToggleFullWidth: () => console.log('Toggle full width'),
  onClose: () => console.log('Close')
}

// Story for one-column layout (<800px)
export const OneColumn: Story = {
  args: baseTask,
  decorators: [
    (Story) => (
      <div style={{ width: '700px', height: '800px' }}>
        <Story />
      </div>
    )
  ]
}

// Story for two-column layout (800px-1179px)
export const TwoColumns: Story = {
  args: baseTask,
  decorators: [
    (Story) => (
      <div style={{ width: '1000px', height: '800px' }}>
        <Story />
      </div>
    )
  ]
}

// Story for three-column layout (1180px+)
export const ThreeColumns: Story = {
  args: baseTask,
  decorators: [
    (Story) => (
      <div style={{ width: '1300px', height: '800px' }}>
        <Story />
      </div>
    )
  ]
}

// Story showing responsive behavior
export const Responsive: Story = {
  args: baseTask,
  parameters: {
    layout: 'fullscreen'
  },
  decorators: [
    (Story) => (
      <div className="p-4 w-full h-screen resize overflow-auto">
        <Story />
      </div>
    )
  ]
}
