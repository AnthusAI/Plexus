import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { Gauge } from '../components/gauge'

export default {
  title: 'Components/Gauge',
  component: Gauge,
  tags: ['autodocs'],
} satisfies Meta<typeof Gauge>

type Story = StoryObj<typeof Gauge>

export const Default: Story = {
  args: {
    value: 75,
    title: 'Accuracy'
  }
}

export const CustomSegments: Story = {
  args: {
    value: 75,
    title: 'Accuracy',
    segments: [
      { start: 0, end: 60, color: 'var(--gauge-inviable)' },
      { start: 60, end: 85, color: 'var(--gauge-converging)' },
      { start: 85, end: 100, color: 'var(--gauge-great)' }
    ]
  }
}

export const CustomBackground: Story = {
  args: {
    value: 75,
    title: 'Accuracy',
    backgroundColor: 'var(--background)'
  },
  decorators: [
    (Story) => (
      <div className="bg-card p-6 rounded-lg">
        <Story />
      </div>
    )
  ]
}

export const LowValue: Story = {
  args: {
    value: 30,
    title: 'Accuracy'
  }
}

export const HighValue: Story = {
  args: {
    value: 95,
    title: 'Accuracy'
  }
}
