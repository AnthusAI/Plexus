import type { Meta, StoryObj } from '@storybook/react'
import MetricsGaugesExplanation from '../components/MetricsGaugesExplanation'
import { Card, CardContent } from '@/components/ui/card'

const meta: Meta<typeof MetricsGaugesExplanation> = {
  title: 'Components/MetricsGaugesExplanation',
  component: MetricsGaugesExplanation,
  tags: ['autodocs'],
  decorators: [
    (Story) => (
      <Card className="max-w-2xl">
        <CardContent className="pt-6">
          <Story />
        </CardContent>
      </Card>
    )
  ],
}

export default meta
type Story = StoryObj<typeof MetricsGaugesExplanation>

const baseExplanation = "This experiment measures the model's ability to correctly " +
  "identify positive cases while maintaining a balance between precision " + 
  "and recall. The metrics show strong performance across all key indicators."

export const NoGoal: Story = {
  args: {
    explanation: baseExplanation,
    goal: null,
  },
}

export const SensitivityGoal: Story = {
  args: {
    explanation: baseExplanation,
    goal: 'sensitivity',
  },
}

export const PrecisionGoal: Story = {
  args: {
    explanation: baseExplanation,
    goal: 'precision',
  },
}

export const BalancedGoal: Story = {
  args: {
    explanation: baseExplanation,
    goal: 'balanced',
  },
}

export const UnknownGoal: Story = {
  args: {
    explanation: baseExplanation,
    goal: 'some-other-goal',
  },
} 