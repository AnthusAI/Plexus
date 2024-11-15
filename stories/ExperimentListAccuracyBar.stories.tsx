import type { Meta, StoryObj } from '@storybook/react'
import { ExperimentListAccuracyBar } from '@/components/ExperimentListAccuracyBar'

const meta = {
  title: 'Visualization/ExperimentListAccuracyBar',
  component: ExperimentListAccuracyBar,
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
} satisfies Meta<typeof ExperimentListAccuracyBar>

export default meta
type Story = StoryObj<typeof ExperimentListAccuracyBar>

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
            <ExperimentListAccuracyBar progress={100} accuracy={100} />
            <ExperimentListAccuracyBar progress={100} accuracy={75} />
            <ExperimentListAccuracyBar progress={100} accuracy={50} />
            <ExperimentListAccuracyBar progress={100} accuracy={25} />
            <ExperimentListAccuracyBar progress={100} accuracy={0} />
          </div>
          <div className="space-y-4">
            <h3 className="font-medium mb-2">Focused</h3>
            <ExperimentListAccuracyBar progress={100} accuracy={100} isFocused />
            <ExperimentListAccuracyBar progress={100} accuracy={75} isFocused />
            <ExperimentListAccuracyBar progress={100} accuracy={50} isFocused />
            <ExperimentListAccuracyBar progress={100} accuracy={25} isFocused />
            <ExperimentListAccuracyBar progress={100} accuracy={0} isFocused />
          </div>
        </div>
      </div>
    ),
  ],
} 