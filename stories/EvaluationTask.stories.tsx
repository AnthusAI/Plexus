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
const createSampleData = () => ({
  accuracy: 85.5,
  metrics: [
    { name: "Accuracy", value: 85.5, unit: "%", maximum: 100, priority: true },
    { name: "Precision", value: 88.2, unit: "%", maximum: 100, priority: true },
    { name: "Sensitivity", value: 82.1, unit: "%", maximum: 100, priority: true },
    { name: "Specificity", value: 91.3, unit: "%", maximum: 100, priority: true }
  ],
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
    labels: ["Positive", "Negative"]
  },
  scoreResults: Array.from({ length: 20 }, (_, i) => ({
    id: `result-${i}`,
    value: Math.random() > 0.15 ? 1 : 0,
    confidence: 0.7 + (Math.random() * 0.3),
    metadata: JSON.stringify({
      predicted_value: `Category ${(i % 3) + 1}`,
      true_value: `Category ${(i % 3) + 1 + (Math.random() > 0.85 ? 1 : 0)}`
    }),
    createdAt: new Date().toISOString(),
    itemId: `item-${i}`,
    EvaluationId: 'eval-1',
    scorecardId: 'scorecard-1'
  }))
})

// Base task props
const baseTask: EvaluationTaskProps = {
  variant: 'detail',
  task: {
    id: '1',
    type: 'Evaluation running',
    scorecard: 'Customer Intent Analysis',
    score: 'Intent Classification',
    time: '2 hours ago',
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
