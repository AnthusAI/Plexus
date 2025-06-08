import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import BeforeAfterGauges from '../components/BeforeAfterGauges'

export default {
  title: 'General/Components/BeforeAfterGauges',
  component: BeforeAfterGauges,
  tags: ['autodocs'],
} satisfies Meta<typeof BeforeAfterGauges>

type Story = StoryObj<typeof BeforeAfterGauges>

export const Default: Story = {
  args: {
    title: 'Accuracy',
    before: 30,
    after: 70,
  }
}

export const CustomSegments: Story = {
  args: {
    title: 'Precision',
    before: 45,
    after: 85,
    segments: [
      { start: 0, end: 60, color: 'var(--gauge-inviable)' },
      { start: 60, end: 85, color: 'var(--gauge-converging)' },
      { start: 85, end: 100, color: 'var(--gauge-great)' }
    ]
  }
}

export const NoChange: Story = {
  args: {
    title: 'F1 Score',
    before: 50,
    after: 50,
  }
}

export const FullChange: Story = {
  args: {
    title: 'ROC AUC',
    before: 0,
    after: 100,
  }
}
