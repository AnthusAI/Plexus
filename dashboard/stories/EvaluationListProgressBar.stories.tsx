import type { Meta, StoryObj } from '@storybook/react'
import { EvaluationListProgressBar } from '@/components/EvaluationListProgressBar'

const meta = {
  title: 'Visualization/EvaluationListProgressBar',
  component: EvaluationListProgressBar,
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
} satisfies Meta<typeof EvaluationListProgressBar>

export default meta
type Story = StoryObj<typeof EvaluationListProgressBar>

export const Single: Story = {
  args: {
    progress: 65,
    totalSamples: 100,
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
    totalSamples: 100,
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
            <EvaluationListProgressBar progress={0} totalSamples={100} />
            <EvaluationListProgressBar progress={25} totalSamples={100} />
            <EvaluationListProgressBar progress={50} totalSamples={100} />
            <EvaluationListProgressBar progress={75} totalSamples={100} />
            <EvaluationListProgressBar progress={100} totalSamples={100} />
          </div>
          <div className="space-y-4">
            <h3 className="font-medium mb-2">Focused</h3>
            <EvaluationListProgressBar progress={0} totalSamples={100} isFocused />
            <EvaluationListProgressBar progress={25} totalSamples={100} isFocused />
            <EvaluationListProgressBar progress={50} totalSamples={100} isFocused />
            <EvaluationListProgressBar progress={75} totalSamples={100} isFocused />
            <EvaluationListProgressBar progress={100} totalSamples={100} isFocused />
          </div>
        </div>
      </div>
    ),
  ],
} 