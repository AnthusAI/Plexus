import type { Meta, StoryObj } from '@storybook/react'
import React from 'react'
import { expect, within } from '@storybook/test'
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
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const accuracyElements = canvas.getAllByText('85%')
    await expect(accuracyElements).toHaveLength(2)
    const overlayText = accuracyElements.find(el => 
      el.closest('div')?.className.includes('absolute'))
    await expect(overlayText).toBeDefined()
  }
}

export const HighPrecision: Story = {
  args: {
    progress: 100,
    accuracy: 99.7,
    isFocused: false,
  },
  decorators: [
    (Story) => (
      <div className="w-1/2 min-w-[300px]">
        <Story />
      </div>
    ),
  ],
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const accuracyElements = canvas.getAllByText('99.7%')
    await expect(accuracyElements).toHaveLength(2)
    const barText = accuracyElements.find(el => 
      el.closest('div')?.className.includes('bg-true'))
    await expect(barText).toBeDefined()
  }
}

export const NearlyPerfect: Story = {
  args: {
    progress: 100,
    accuracy: 97.9,
    isFocused: false,
  },
  decorators: [
    (Story) => (
      <div className="w-1/2 min-w-[300px]">
        <Story />
      </div>
    ),
  ],
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const accuracyElements = canvas.getAllByText('98%')
    await expect(accuracyElements).toHaveLength(2)
  }
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
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const accuracyElements = canvas.getAllByText('85%')
    await expect(accuracyElements).toHaveLength(2)
    const focusedElements = accuracyElements
      .filter(el => el.closest('div')?.className.includes('text-focus'))
    await expect(focusedElements).toHaveLength(2)
  }
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
            <EvaluationListAccuracyBar progress={100} accuracy={99.7} />
            <EvaluationListAccuracyBar progress={100} accuracy={98.2} />
            <EvaluationListAccuracyBar progress={100} accuracy={97.8} />
            <EvaluationListAccuracyBar progress={100} accuracy={75} />
            <EvaluationListAccuracyBar progress={100} accuracy={50} />
          </div>
          <div className="space-y-4">
            <h3 className="font-medium mb-2">Focused</h3>
            <EvaluationListAccuracyBar progress={100} accuracy={99.7} isFocused />
            <EvaluationListAccuracyBar progress={100} accuracy={98.2} isFocused />
            <EvaluationListAccuracyBar progress={100} accuracy={97.8} isFocused />
            <EvaluationListAccuracyBar progress={100} accuracy={75} isFocused />
            <EvaluationListAccuracyBar progress={100} accuracy={50} isFocused />
          </div>
        </div>
      </div>
    ),
  ],
} 