import type { Meta, StoryObj } from '@storybook/react'
import EvaluationCard from '../components/EvaluationCard'

const meta: Meta<typeof EvaluationCard> = {
  title: 'Cards/EvaluationCard',
  component: EvaluationCard,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
  argTypes: {
    accuracy: { control: { type: 'range', min: 0, max: 100 } },
    gwetAC1: { control: { type: 'range', min: 0, max: 1, step: 0.01 } },
  },
}

export default meta
type Story = StoryObj<typeof EvaluationCard>

// Example data for a coin flip prediction (balanced binary)
export const CoinFlipExample: Story = {
  args: {
    title: 'Coin Flip Prediction (50/50)',
    subtitle: 'A fair coin has a 50% chance of heads or tails. Random guessing achieves 50% accuracy.',
    classDistributionData: [
      { label: 'Heads', count: 50 },
      { label: 'Tails', count: 50 },
    ],
    isBalanced: true,
    accuracy: 50.0,
    notes: 'Without context (left gauge), the 50% accuracy has no meaning. With proper contextual segments (right gauge), we can see that 50% is exactly at the chance level for a balanced binary problem, indicating no prediction skill.',
  },
}

// Example with confusion matrix
export const WithConfusionMatrix: Story = {
  args: {
    title: 'Email Filter Example',
    subtitle: 'Model performance on email classification task',
    classDistributionData: [
      { label: 'Safe', count: 970 },
      { label: 'Prohibited', count: 30 },
    ],
    isBalanced: false,
    confusionMatrixData: {
      matrix: [
        {
          actualClassLabel: 'Safe',
          predictedClassCounts: { 'Safe': 950, 'Prohibited': 20 }
        },
        {
          actualClassLabel: 'Prohibited',
          predictedClassCounts: { 'Safe': 20, 'Prohibited': 10 }
        }
      ],
      labels: ['Safe', 'Prohibited'],
    },
    predictedClassDistributionData: [
      { label: 'Safe', count: 970 },
      { label: 'Prohibited', count: 30 },
    ],
    accuracy: 96.0,
    notes: 'The model achieved 96% accuracy, but the confusion matrix shows it only caught 10 out of 30 prohibited emails.',
  },
}

// Example with Gwet AC1
export const WithAC1Score: Story = {
  args: {
    title: 'Card Suit Prediction',
    subtitle: 'AC1 gives better insight for this multiclass problem',
    classDistributionData: [
      { label: 'Hearts', count: 13 },
      { label: 'Diamonds', count: 13 },
      { label: 'Clubs', count: 13 },
      { label: 'Spades', count: 13 },
    ],
    isBalanced: true,
    accuracy: 40.0,
    gwetAC1: 0.72,
    notes: 'The AC1 score of 0.72 indicates good agreement, showing that the model performs much better than would be expected by chance on this 4-class problem.',
  },
}

// Example with warning message
export const WithWarning: Story = {
  args: {
    title: 'Always Safe Email Filter',
    subtitle: 'This model simply labels everything as "safe"',
    classDistributionData: [
      { label: 'Safe', count: 970 },
      { label: 'Prohibited', count: 30 },
    ],
    isBalanced: false,
    confusionMatrixData: {
      matrix: [
        {
          actualClassLabel: 'Safe',
          predictedClassCounts: { 'Safe': 970, 'Prohibited': 0 }
        },
        {
          actualClassLabel: 'Prohibited',
          predictedClassCounts: { 'Safe': 30, 'Prohibited': 0 }
        }
      ],
      labels: ['Safe', 'Prohibited'],
    },
    predictedClassDistributionData: [
      { label: 'Safe', count: 1000 },
      { label: 'Prohibited', count: 0 },
    ],
    accuracy: 97.0,
    warningMessage: 'CRITICAL FLAW: This 97% accuracy is dangerously misleading! The model failed to detect ANY prohibited content (0% recall for violations). It simply labels everything as "safe" and benefits from the extreme class imbalance.',
  },
} 