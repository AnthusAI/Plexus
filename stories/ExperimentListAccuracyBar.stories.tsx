import type { Meta, StoryObj } from '@storybook/react'
import { ExperimentListAccuracyBar } from '@/components/ExperimentListAccuracyBar'

const meta = {
  title: 'Experiments/AccuracyBar',
  component: ExperimentListAccuracyBar,
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
} satisfies Meta<typeof ExperimentListAccuracyBar>

export default meta
type Story = StoryObj<typeof ExperimentListAccuracyBar>

export const NoProgress: Story = {
  args: {
    progress: 0,
    accuracy: 85,
  },
}

export const QuarterProgress: Story = {
  args: {
    progress: 25,
    accuracy: 85,
  },
}

export const HalfProgress: Story = {
  args: {
    progress: 50,
    accuracy: 85,
  },
}

export const ThreeQuartersProgress: Story = {
  args: {
    progress: 75,
    accuracy: 85,
  },
}

export const Complete: Story = {
  args: {
    progress: 100,
    accuracy: 85,
  },
}

export const LowAccuracy: Story = {
  args: {
    progress: 100,
    accuracy: 30,
  },
}

export const PerfectAccuracy: Story = {
  args: {
    progress: 100,
    accuracy: 100,
  },
}

// Show different accuracies at half progress
export const HalfProgressVariants: Story = {
  render: () => (
    <div className="space-y-4">
      <ExperimentListAccuracyBar progress={50} accuracy={100} />
      <ExperimentListAccuracyBar progress={50} accuracy={75} />
      <ExperimentListAccuracyBar progress={50} accuracy={50} />
      <ExperimentListAccuracyBar progress={50} accuracy={25} />
      <ExperimentListAccuracyBar progress={50} accuracy={0} />
    </div>
  ),
} 