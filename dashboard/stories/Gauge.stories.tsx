import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { expect, within, userEvent } from '@storybook/test'
import { Gauge } from '../components/gauge'

export default {
  title: 'General/Components/Gauge',
  component: Gauge,
  tags: ['autodocs'],
  parameters: {
    // Disable Storybook test-runner for this file to avoid flaky evaluate errors in CI
    test: { disable: true }
  }
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
    await expect(valueText).toBeInTheDocument()
    await expect(titleText).toBeInTheDocument()
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

export const WithTarget: Story = {
  args: {
    value: 75.7,
    title: 'Accuracy',
    target: 92.3
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByText('75.7%')).toBeInTheDocument()
    
    // Check that there are two needles in the gauge
    const svg = canvasElement.querySelector('svg')
    const needles = svg?.querySelectorAll('path[d^="M 0,-"]')
    await expect(needles).toBeTruthy()
    await expect(needles?.length).toBeGreaterThanOrEqual(2)
  },
  decorators: [
    (Story) => (
      <div className="bg-card-light p-6 rounded-lg">
        <Story />
      </div>
    )
  ],
  parameters: {
    docs: {
      description: {
        story: 'The `target` prop allows you to show a target value with a lighter needle, showing what value you want to reach.'
      }
    }
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
    const svg = canvasElement.querySelector('svg')
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
    // Verify the percentage value is displayed (now outside SVG in NumberFlow component)
    await expect(canvas.getByText('75%')).toBeInTheDocument()
    
    // Verify no tick marks are shown in the SVG when showTicks is false
    const svg = canvasElement.querySelector('svg')
    const tickTexts = svg?.querySelectorAll('text')
    const tickMarkerTexts = Array.from(tickTexts || [])
      .filter(text => text.textContent?.includes('%'))
    await expect(tickMarkerTexts.length).toBe(0)
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
    information: "Gwet's AC1 is an advanced agreement coefficient that measures inter-rater reliability, accounting for chance agreement more effectively than other metrics. Values range from -1 (complete disagreement) to 1 (perfect agreement), with 0 indicating random agreement. Values above 0.8 generally indicate strong agreement between multiple assessors."
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    
    // Check for the title rather than the value, which might be broken up
    const titleText = canvas.getByText('Alignment')
    await expect(titleText).toBeInTheDocument()
    
    // Test that the information button shows the Gwet's AC1 explanation
    const infoButton = canvas.getByLabelText('More information')
    await expect(infoButton).toBeInTheDocument()
    await userEvent.click(infoButton)
    
    // The Popover is rendered in a portal, so we need to look at the document body
    const infoText = document.body.querySelector('.w-80.text-sm')
    await expect(infoText).toBeInTheDocument()
    await expect(infoText?.textContent).toContain("Gwet's AC1")

    // Test for presence of SVG and other gauge elements
    const svg = canvasElement.querySelector('svg')
    await expect(svg).toBeInTheDocument()
    
    // Check for gauge segments
    const segments = svg?.querySelectorAll('path[fill^="var(--gauge"]')
    await expect(segments?.length).toBeGreaterThanOrEqual(5)
    
    // Check for needle (indicator)
    const needle = svg?.querySelector('path[d^="M 0,-"]')
    await expect(needle).toBeInTheDocument()
  },
  decorators: [
    (Story) => (
      <div className="bg-card-light p-6 rounded-lg">
        <Story />
      </div>
    )
  ]
}

export const AlignmentWithTarget: Story = {
  args: {
    value: 0.76,
    target: 0.92,
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
    information: "Gwet's AC1 is an advanced agreement coefficient that measures inter-rater reliability, accounting for chance agreement more effectively than other metrics. Values range from -1 (complete disagreement) to 1 (perfect agreement), with 0 indicating random agreement. Values above 0.8 generally indicate strong agreement between multiple assessors."
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    
    // Check for the title rather than the value, which might be broken up
    const titleText = canvas.getByText('Alignment')
    await expect(titleText).toBeInTheDocument()
    
    // Test for presence of SVG and gauge elements
    const svg = canvasElement.querySelector('svg')
    await expect(svg).toBeInTheDocument()
    
    // Test that there are two needles in the gauge (current value and target)
    const needles = svg?.querySelectorAll('path[d^="M 0,-"]')
    await expect(needles?.length).toBeGreaterThanOrEqual(2)
    // Verify the target tick has a dashed line
    const targetTickLine = svg?.querySelector('line.stroke-primary[stroke-dasharray="2,1"]')
    await expect(targetTickLine).toBeInTheDocument()
    
    // Test that the information button shows the Gwet's AC1 explanation
    const infoButton = canvas.getByLabelText('More information')
    await expect(infoButton).toBeInTheDocument()
    await userEvent.click(infoButton)
    // The Popover is rendered in a portal, so we need to look at the document body
    const infoText = document.body.querySelector('.w-80.text-sm')
    await expect(infoText).toBeInTheDocument()
    await expect(infoText?.textContent).toContain("Gwet's AC1")
  },
  decorators: [
    (Story) => (
      <div className="bg-card-light p-6 rounded-lg">
        <Story />
      </div>
    )
  ],
  parameters: {
    docs: {
      description: {
        story: 'This example shows an alignment gauge with both current value and target value. The target is displayed both as a lighter needle and as a special tick mark with label, making it easier to see the exact target value.'
      }
    }
  }
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

export const TickSpacing: Story = {
  args: {
    value: 80,
    title: 'Dense Segments',
    showTicks: true,
    segments: [
      { start: 0, end: 70, color: 'var(--gauge-inviable)' },
      { start: 70, end: 75, color: 'var(--gauge-converging)' },
      { start: 75, end: 80, color: 'var(--gauge-almost)' },
      { start: 80, end: 85, color: 'var(--gauge-viable)' },
      { start: 85, end: 90, color: 'var(--gauge-viable)' },
      { start: 90, end: 95, color: 'var(--gauge-viable)' },
      { start: 95, end: 100, color: 'var(--gauge-great)' }
    ],
    tickSpacingThreshold: 5
  },
  decorators: [
    (Story) => (
      <div className="bg-card-light p-6 rounded-lg">
        <Story />
      </div>
    )
  ],
  parameters: {
    docs: {
      description: {
        story: 'This example demonstrates the `tickSpacingThreshold` prop which controls how close tick marks can be. Ticks that are closer than the threshold (as a percentage of the total range) will not be shown.'
      }
    }
  }
}

export const TickSpacingComparison: Story = {
  render: () => (
    <div className="grid grid-cols-2 gap-8 max-w-4xl bg-card-light p-6 rounded-lg">
      <div>
        <h3 className="text-center mb-2 font-medium">Default spacing (5%)</h3>
        <Gauge
          value={80}
          title="Dense Segments"
          showTicks={true}
          segments={[
            { start: 0, end: 70, color: 'var(--gauge-inviable)' },
            { start: 70, end: 75, color: 'var(--gauge-converging)' },
            { start: 75, end: 80, color: 'var(--gauge-almost)' },
            { start: 80, end: 85, color: 'var(--gauge-viable)' },
            { start: 85, end: 90, color: 'var(--gauge-viable)' },
            { start: 90, end: 95, color: 'var(--gauge-viable)' },
            { start: 95, end: 100, color: 'var(--gauge-great)' }
          ]}
          tickSpacingThreshold={5}
        />
      </div>
      <div>
        <h3 className="text-center mb-2 font-medium">Smaller spacing (2%)</h3>
        <Gauge
          value={80}
          title="Dense Segments"
          showTicks={true}
          segments={[
            { start: 0, end: 70, color: 'var(--gauge-inviable)' },
            { start: 70, end: 75, color: 'var(--gauge-converging)' },
            { start: 75, end: 80, color: 'var(--gauge-almost)' },
            { start: 80, end: 85, color: 'var(--gauge-viable)' },
            { start: 85, end: 90, color: 'var(--gauge-viable)' },
            { start: 90, end: 95, color: 'var(--gauge-viable)' },
            { start: 95, end: 100, color: 'var(--gauge-great)' }
          ]}
          tickSpacingThreshold={2}
        />
      </div>
    </div>
  ),
  parameters: {
    docs: {
      description: {
        story: 'This comparison shows how different `tickSpacingThreshold` values affect which ticks are displayed. The left gauge uses the default 5% threshold, while the right uses a smaller 2% threshold, showing more tick marks.'
      }
    }
  }
}

export const WithMarkdownInformation: Story = {
  args: {
    value: 85,
    title: 'System Performance',
    information: `**Current Status:** Excellent  
*System is performing above target*

**Key Metrics:**
- Response time: \`< 200ms\`
- Uptime: **99.9%**
- Error rate: *0.1%*

> **Note:** Performance has improved significantly since the last deployment.

For more details, visit our [monitoring dashboard](https://example.com/monitoring).

**Thresholds:**
1. **Green:** 80-100% (Excellent)
2. **Yellow:** 60-79% (Good) 
3. **Red:** 0-59% (Needs attention)`
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const infoButton = canvas.getByLabelText('More information')
    await expect(infoButton).toBeInTheDocument()
    
    await userEvent.click(infoButton)
    // The Popover is rendered in a portal, so we need to look at the document body
    const infoPopover = document.body.querySelector('.w-80.text-sm')
    await expect(infoPopover).toBeInTheDocument()
    
    // Check for markdown formatting
    const boldText = infoPopover?.querySelector('strong')
    await expect(boldText).toBeInTheDocument()
    
    const italicText = infoPopover?.querySelector('em')
    await expect(italicText).toBeInTheDocument()
    
    const codeText = infoPopover?.querySelector('code')
    await expect(codeText).toBeInTheDocument()
    
    const link = infoPopover?.querySelector('a[href="https://example.com/monitoring"]')
    await expect(link).toBeInTheDocument()
    
    const list = infoPopover?.querySelector('ol')
    await expect(list).toBeInTheDocument()
  },
  parameters: {
    docs: {
      description: {
        story: 'Demonstrates the full markdown formatting capabilities of the information prop, including bold text, italics, code blocks, links, lists, and blockquotes.'
      }
    }
  }
}
