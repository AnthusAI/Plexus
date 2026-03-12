import type { Meta, StoryObj } from '@storybook/react'
import EvaluationCard from '../components/EvaluationCard'

const meta: Meta<typeof EvaluationCard> = {
  title: 'Evaluations/EvaluationCard',
  component: EvaluationCard,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
  argTypes: {
    accuracy: { control: { type: 'range', min: 0, max: 100 } },
    gwetAC1: { control: { type: 'range', min: 0, max: 1, step: 0.01 } },
    variant: {
      control: { type: 'radio' },
      options: ['default', 'oneGauge'],
    },
    disableAccuracySegments: { control: 'boolean' },
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

// Example with OneGauge variant
export const OneGaugeVariant: Story = {
  args: {
    title: 'Predicting a Fair Coin',
    subtitle: "You're asked to predict 100 flips of a fair coin, where heads and tails are equally likely (50/50 chance). After making your predictions, you find you were correct for 58 flips - a 58% accuracy rate.",
    classDistributionData: [
      { label: 'Heads', count: 50 },
      { label: 'Tails', count: 50 },
    ],
    isBalanced: true,
    accuracy: 58.0,
    confusionMatrixData: {
      labels: ["Heads", "Tails"],
      matrix: [
        { actualClassLabel: "Heads", predictedClassCounts: { "Heads": 30, "Tails": 20 } },
        { actualClassLabel: "Tails", predictedClassCounts: { "Heads": 22, "Tails": 28 } },
      ],
    },
    predictedClassDistributionData: [
      { label: "Heads", count: 52 },
      { label: "Tails", count: 48 }
    ],
    variant: 'oneGauge',
    gaugeDescription: (
      <p>
        <strong>Slightly better than chance:</strong> With a fair coin, your 58% accuracy is just slightly better than the 50% you'd expect from pure random guessing. This suggests you might have some very minimal insight into predicting this particular coin's behavior, but you're still not far from what luck would give you.
      </p>
    ),
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
    showBothGauges: true,
    notes: 'The Agreement (AC1) score of 0.72 indicates good agreement, showing that the model performs much better than would be expected by chance on this 4-class problem with a baseline chance level of 25%.'
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

// Example with OneGauge + Warning
export const OneGaugeWithWarning: Story = {
  args: {
    title: 'The "Always Safe" Email Filter',
    subtitle: "Imagine you're evaluating an email filtering system that claims 97% accuracy in detecting prohibited content. It labels everything as safe regardless of content.",
    classDistributionData: [
      { label: 'Safe', count: 970 },
      { label: 'Prohibited', count: 30 },
    ],
    isBalanced: false,
    confusionMatrixData: {
      labels: ["Safe", "Prohibited"],
      matrix: [
        { actualClassLabel: "Safe", predictedClassCounts: { "Safe": 970, "Prohibited": 0 } },
        { actualClassLabel: "Prohibited", predictedClassCounts: { "Safe": 30, "Prohibited": 0 } },
      ],
    },
    predictedClassDistributionData: [
      { label: "Safe", count: 1000 },
      { label: "Prohibited", count: 0 }
    ],
    accuracy: 97.0,
    variant: 'oneGauge',
    gaugeDescription: (
      <p>
        <strong>This 97% accuracy is dangerously misleading!</strong> The model failed to detect ANY prohibited content (0% recall for violations). It simply labels everything as "safe" and benefits from the extreme class imbalance.
      </p>
    ),
    warningMessage: (
      <div className="p-3 bg-destructive rounded-md">
        <p className="text-base font-bold text-white">CRITICAL FLAW</p>
        <p className="text-sm mt-1 text-white">
          This 97% accuracy is dangerously misleading! The model failed to detect ANY prohibited content (0% recall for violations). It simply labels everything as "safe" and benefits from the extreme class imbalance. This is worse than useless—it's a false sense of security.
        </p>
        <p className="text-sm mt-2 text-white">
          The AC1 score would be 0.0, correctly showing no predictive ability beyond chance.
        </p>
      </div>
    )
  },
}

// Example with disabled accuracy segments
export const WithDisabledAccuracySegments: Story = {
  args: {
    title: 'Raw Accuracy Without Context',
    subtitle: 'Showing accuracy value without implying interpretability through colored segments',
    classDistributionData: [
      { label: 'Class A', count: 60 },
      { label: 'Class B', count: 30 },
      { label: 'Class C', count: 10 },
    ],
    isBalanced: false,
    accuracy: 75.0,
    gwetAC1: 0.45,
    disableAccuracySegments: true,
    showBothGauges: true,
    notes: 'The accuracy gauge on the right has been set to show only a gray background without colored segments. This is useful when we want to display the raw accuracy value without implying how it should be interpreted in the context of the class distribution. The Agreement (AC1) gauge on the left remains unaffected by the disableAccuracySegments setting.'
  },
}

// Example with disabled accuracy segments in oneGauge variant
export const OneGaugeWithDisabledSegments: Story = {
  args: {
    title: 'Simplified Accuracy Display',
    subtitle: 'Model accuracy shown with a neutral gauge that makes no claims about interpretability',
    classDistributionData: [
      { label: 'Relevant', count: 15 },
      { label: 'Not Relevant', count: 85 },
    ],
    isBalanced: false,
    accuracy: 90.0,
    confusionMatrixData: {
      labels: ["Relevant", "Not Relevant"],
      matrix: [
        { actualClassLabel: "Relevant", predictedClassCounts: { "Relevant": 10, "Not Relevant": 5 } },
        { actualClassLabel: "Not Relevant", predictedClassCounts: { "Relevant": 5, "Not Relevant": 80 } },
      ],
    },
    predictedClassDistributionData: [
      { label: "Relevant", count: 15 },
      { label: "Not Relevant", count: 85 }
    ],
    variant: 'oneGauge',
    disableAccuracySegments: true,
    gaugeDescription: (
      <p>
        <strong>Raw accuracy value:</strong> This 90% accuracy is presented without interpretive context. With a highly imbalanced dataset (85% majority class), this value requires additional context from the confusion matrix to be properly evaluated.
      </p>
    ),
  },
} 