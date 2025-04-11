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
    const infoButton = canvas.getByLabelText('More information')
    await expect(infoButton).toBeInTheDocument()
    
    await userEvent.click(infoButton)
    // The Popover is rendered in a portal, so we need to look at the document body
    const infoText = document.body.querySelector('.w-80.text-sm')
    await expect(infoText).toBeInTheDocument()
    await expect(infoText?.textContent).toContain('Test information content')
  }
}

export const CustomSegments: Story = {
  args: {
    value: 75,
    title: 'Accuracy',
    segments: [
      { start: 0, end: 50, color: 'var(--gauge-inviable)' },
      { start: 50, end: 70, color: 'var(--gauge-converging)' },
      { start: 70, end: 85, color: 'var(--gauge-almost)' },
      { start: 85, end: 95, color: 'var(--gauge-viable)' },
      { start: 95, end: 100, color: 'var(--gauge-great)' }
    ]
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const svg = canvas.getByText('75%').closest('svg')
    await expect(svg).toBeInTheDocument()
    const paths = svg?.querySelectorAll('path[fill^="var(--gauge"]')
    await expect(paths?.length).toBeGreaterThanOrEqual(5)
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

export const CustomValueUnit: Story = {
  args: {
    value: 42,
    title: 'Score',
    valueUnit: 'pts',
    max: 100
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const valueText = canvas.getByText('42pts')
    await expect(valueText).toBeInTheDocument()
    
    const titleText = canvas.getByText('Score')
    await expect(titleText).toBeInTheDocument()
  },
  decorators: [
    (Story) => (
      <div className="bg-card-light p-6 rounded-lg">
        <Story />
      </div>
    )
  ]
}

export const Alignment: Story = {
  args: {
    value: 0.76,
    title: 'Alignment',
    valueUnit: '',
    min: -1,
    max: 1,
    decimalPlaces: 2,
    showTicks: true,
    segments: [
      { start: 0, end: 50, color: 'var(--gauge-inviable)' },      // Negative values (-1 to 0)
      { start: 50, end: 60, color: 'var(--gauge-converging)' },   // Low alignment (0 to 0.2)
      { start: 60, end: 75, color: 'var(--gauge-almost)' },       // Moderate alignment (0.2 to 0.5)
      { start: 75, end: 90, color: 'var(--gauge-viable)' },       // Good alignment (0.5 to 0.8)
      { start: 90, end: 100, color: 'var(--gauge-great)' }        // Excellent alignment (0.8 to 1.0)
    ],
    information: "Fleiss' Kappa measures the degree of agreement between multiple raters when classifying items into categories. Values range from -1 (complete disagreement) to 1 (perfect agreement), with 0 indicating agreement equivalent to random chance. Values above 0 suggest positive alignment, with higher values indicating stronger agreement between raters."
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const valueText = canvas.getByText('0.76')
    await expect(valueText).toBeInTheDocument()
    
    const titleText = canvas.getByText('Alignment')
    await expect(titleText).toBeInTheDocument()
    
    // Test that the information button shows the Fleiss' Kappa explanation
    const infoButton = canvas.getByLabelText('More information')
    await userEvent.click(infoButton)
    // The Popover is rendered in a portal, so we need to look at the document body
    const infoText = document.body.querySelector('.w-80.text-sm')
    await expect(infoText).toBeInTheDocument()
    await expect(infoText?.textContent).toContain("Fleiss' Kappa measures")

    // Test for presence of tick marks (text elements with segment start values)
    const svg = canvas.getByText('0.76').closest('svg')
    const tickTexts = svg?.querySelectorAll('text.fill-muted-foreground')
    const tickLabels = Array.from(tickTexts || []).map(t => t.textContent)
    // Check for values based on min/max (-1 to 1) and segment percentages
    // 0% -> -1
    // 50% -> 0
    // 60% -> 0.2
    // 75% -> 0.5
    // 90% -> 0.8
    // 100% -> 1
    await expect(tickLabels).toContain('-1')
    await expect(tickLabels).toContain('0')
    await expect(tickLabels).toContain('0.2')
    await expect(tickLabels).toContain('0.5')
    await expect(tickLabels).toContain('0.8')
    await expect(tickLabels).toContain('1')
  },
  decorators: [
    (Story) => (
      <div className="bg-card-light p-6 rounded-lg">
        <Story />
      </div>
    )
  ]
}

export const DecimalPrecision: Story = {
  args: {
    value: 87.654,
    title: 'Precision Control',
    decimalPlaces: 2
  },
  parameters: {
    docs: {
      description: {
        story: 'The `decimalPlaces` prop controls how many decimal places are shown in the value display.'
      }
    }
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const valueText = canvas.getByText('87.65%')
    await expect(valueText).toBeInTheDocument()
  },
  decorators: [
    (Story) => (
      <div className="bg-card-light p-6 rounded-lg">
        <Story />
      </div>
    )
  ]
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
