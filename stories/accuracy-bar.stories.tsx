import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { AccuracyBar } from '@/components/ui/accuracy-bar'

const meta: Meta<typeof AccuracyBar> = {
  title: 'Components/AccuracyBar',
  component: AccuracyBar,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
}

export default meta
type Story = StoryObj<typeof AccuracyBar>

const Template: Story = {
  decorators: [
    (Story) => (
      <div className="w-[400px]">
        <Story />
      </div>
    ),
  ],
}

export const Empty: Story = {
  args: {
    accuracy: null,
  },
  ...Template,
}

export const ZeroPercent: Story = {
  args: {
    accuracy: 0,
  },
  ...Template,
}

export const LowAccuracy: Story = {
  args: {
    accuracy: 25.5,
  },
  ...Template,
}

export const MediumAccuracy: Story = {
  args: {
    accuracy: 50,
  },
  ...Template,
}

export const HighAccuracy: Story = {
  args: {
    accuracy: 85.5,
  },
  ...Template,
}

export const PerfectAccuracy: Story = {
  args: {
    accuracy: 100,
  },
  ...Template,
} 