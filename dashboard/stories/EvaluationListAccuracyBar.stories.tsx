import type { Meta, StoryObj } from '@storybook/react'
import { EvaluationListAccuracyBar } from '@/components/EvaluationListAccuracyBar'

const meta = {
  title: 'Visualization/EvaluationListAccuracyBar',
  component: EvaluationListAccuracyBar,
  parameters: {
    layout: 'centered',
  },
  decorators: [
    (Story) => (
      <div className="w-full">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof EvaluationListAccuracyBar>

export default meta
type Story = StoryObj<typeof EvaluationListAccuracyBar>

export const Single: Story = {
  args: {
    progress: 65,
    accuracy: 85,
    isFocused: false,
  },
  decorators: [
    (Story) => (
      <div className="w-1/2 min-w-[300px]">
        <Story />
      </div>
    ),
  ],
}

export const Focused: Story = {
  args: {
    progress: 65,
    accuracy: 85,
    isFocused: true,
  },
  decorators: [
    (Story) => (
      <div className="w-1/2 min-w-[300px]">
        <Story />
      </div>
    ),
  ],
}

export const Demo: Story = {
  parameters: {
    layout: 'padded',
  },
  decorators: [
    (Story) => (
      <div className="w-full max-w-[1200px] px-8">
        <div className="grid grid-cols-2 gap-16">
          <div className="space-y-4">
            <h3 className="font-medium mb-2">Not Focused</h3>
            <EvaluationListAccuracyBar progress={100} accuracy={100} />
            <EvaluationListAccuracyBar progress={100} accuracy={75} />
            <EvaluationListAccuracyBar progress={100} accuracy={50} />
            <EvaluationListAccuracyBar progress={100} accuracy={25} />
            <EvaluationListAccuracyBar progress={100} accuracy={0} />
          </div>
          <div className="space-y-4">
            <h3 className="font-medium mb-2">Focused</h3>
            <EvaluationListAccuracyBar progress={100} accuracy={100} isFocused />
            <EvaluationListAccuracyBar progress={100} accuracy={75} isFocused />
            <EvaluationListAccuracyBar progress={100} accuracy={50} isFocused />
            <EvaluationListAccuracyBar progress={100} accuracy={25} isFocused />
            <EvaluationListAccuracyBar progress={100} accuracy={0} isFocused />
          </div>
        </div>
      </div>
    ),
  ],
} 