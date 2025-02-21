import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { expect, within, userEvent } from '@storybook/test'
import { Gauge } from '../components/gauge'

export default {
  title: 'Visualization/Gauge',
  component: Gauge,
  tags: ['autodocs'],
} satisfies Meta<typeof Gauge>

type Story = StoryObj<typeof Gauge>

export const Default: Story = {
  args: {
    value: 75,
    title: 'Accuracy'
  },
  decorators: [
    (Story) => (
      <div className="bg-card-light p-6 rounded-lg">
        <Story />
      </div>
    )
  ],
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const valueText = canvas.getByText('75%')
    const titleText = canvas.getByText('Accuracy')
    await expect(valueText).toHaveClass('text-[2.25rem]')
    await expect(titleText).toHaveClass('text-foreground')
  }
}

export const Priority: Story = {
  args: {
    value: 75,
    title: 'Accuracy',
    priority: true
  },
  decorators: [
    (Story) => (
      <div className="bg-card-light p-6 rounded-lg">
        <Story />
      </div>
    )
  ]
}

export const DecimalValue: Story = {
  args: {
    value: 75.7,
    title: 'Accuracy'
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByText('75.7%')).toBeInTheDocument()
  }
}

export const WithInformation: Story = {
  args: {
    value: 75,
    title: 'Accuracy',
    information: 'Test information content'
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const infoButton = canvas.getByLabelText('Toggle information')
    await expect(infoButton).toBeInTheDocument()
    
    await userEvent.click(infoButton)
    const infoText = canvas.getByText('Test information content')
    await expect(infoText).toBeInTheDocument()
    
    await userEvent.click(infoButton)
    await expect(infoText).not.toBeInTheDocument()
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
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const svg = canvas.getByText('75%').closest('svg')
    await expect(svg).toBeInTheDocument()
    const paths = svg?.querySelectorAll('path')
    await expect(paths?.length).toBeGreaterThanOrEqual(3)
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
      <div className="bg-card-light p-6 rounded-lg">
        <Story />
      </div>
    )
  ]
}

export const NoValue: Story = {
  args: {
    title: 'Accuracy'
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const titleText = canvas.getByText('Accuracy')
    await expect(titleText).toBeInTheDocument()
    
    // Verify no percentage value is displayed in the central text
    const centralTexts = canvasElement.querySelectorAll('.text-\\[2\\.25rem\\]')
    const hasVisibleValue = Array.from(centralTexts).some(el => el.textContent?.includes('%'))
    await expect(hasVisibleValue).toBe(false)
  }
}

export const LowValue: Story = {
  args: {
    value: 30,
    title: 'Accuracy'
  },
  decorators: [
    (Story) => (
      <div className="bg-card-light p-6 rounded-lg">
        <Story />
      </div>
    )
  ]
}

export const HighValue: Story = {
  args: {
    value: 95,
    title: 'Accuracy'
  },
  decorators: [
    (Story) => (
      <div className="bg-card-light p-6 rounded-lg">
        <Story />
      </div>
    )
  ]
}

export const NoTicks: Story = {
  args: {
    value: 75,
    title: 'Accuracy',
    showTicks: false
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const svg = canvas.getByText('75%').closest('svg')
    const tickTexts = svg?.querySelectorAll('text')
    const percentageTexts = Array.from(tickTexts || [])
      .filter(text => text.textContent?.includes('%'))
    await expect(percentageTexts.length).toBe(1)
  }
}

export const MetricsGrid: Story = {
  render: () => (
    <div className="grid grid-cols-2 gap-4 max-w-4xl bg-card-light p-6 rounded-lg">
      <Gauge
        value={92.5}
        title="Accuracy"
        priority={true}
        information={
          "Accuracy measures the overall correctness of predictions, showing the " +
          "percentage of all cases (both positive and negative) that were " +
          "correctly classified."
        }
        informationUrl="https://example.com/ml-metrics/accuracy"
      />
      <Gauge
        value={88.3}
        title="Sensitivity"
        information={
          "Sensitivity (also called Recall) measures the ability to correctly " +
          "identify positive cases, showing the percentage of actual positive " +
          "cases that were correctly identified."
        }
        informationUrl="https://example.com/ml-metrics/sensitivity"
      />
      <Gauge
        value={95.7}
        title="Specificity"
        information={
          "Specificity measures the ability to correctly identify negative " +
          "cases, showing the percentage of actual negative cases that were " +
          "correctly identified."
        }
        informationUrl="https://example.com/ml-metrics/specificity"
      />
      <Gauge
        value={90.1}
        title="Precision"
        information={
          "Precision measures the accuracy of positive predictions, showing " +
          "the percentage of predicted positive cases that were actually positive."
        }
        informationUrl="https://example.com/ml-metrics/precision"
      />
    </div>
  )
}
