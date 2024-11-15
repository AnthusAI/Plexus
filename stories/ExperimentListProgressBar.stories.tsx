import type { Meta, StoryObj } from '@storybook/react'
import { ExperimentListProgressBar } from '@/components/ExperimentListProgressBar'

const meta = {
  title: 'Visualization/ExperimentListProgressBar',
  component: ExperimentListProgressBar,
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
} satisfies Meta<typeof ExperimentListProgressBar>

export default meta
type Story = StoryObj<typeof ExperimentListProgressBar>

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
            <ExperimentListProgressBar progress={0} totalSamples={100} />
            <ExperimentListProgressBar progress={25} totalSamples={100} />
            <ExperimentListProgressBar progress={50} totalSamples={100} />
            <ExperimentListProgressBar progress={75} totalSamples={100} />
            <ExperimentListProgressBar progress={100} totalSamples={100} />
          </div>
          <div className="space-y-4">
            <h3 className="font-medium mb-2">Focused</h3>
            <ExperimentListProgressBar progress={0} totalSamples={100} isFocused />
            <ExperimentListProgressBar progress={25} totalSamples={100} isFocused />
            <ExperimentListProgressBar progress={50} totalSamples={100} isFocused />
            <ExperimentListProgressBar progress={75} totalSamples={100} isFocused />
            <ExperimentListProgressBar progress={100} totalSamples={100} isFocused />
          </div>
        </div>
      </div>
    ),
  ],
} 