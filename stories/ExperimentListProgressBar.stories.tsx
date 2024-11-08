import type { Meta, StoryObj } from '@storybook/react'
import { ExperimentListProgressBar } from '@/components/ExperimentListProgressBar'

const meta = {
  title: 'Experiments/ProgressBar',
  component: ExperimentListProgressBar,
  parameters: {
    layout: 'centered',
  },
  decorators: [
    (Story) => (
      <div className="w-[200px]">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof ExperimentListProgressBar>

export default meta
type Story = StoryObj<typeof ExperimentListProgressBar>

export const NoProgress: Story = {
  args: {
    progress: 0,
    totalSamples: 100,
  },
}

export const InProgress: Story = {
  args: {
    progress: 65,
    totalSamples: 100,
  },
}

export const Complete: Story = {
  args: {
    progress: 100,
    totalSamples: 100,
  },
} 