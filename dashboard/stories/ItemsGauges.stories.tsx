import type { Meta, StoryObj } from '@storybook/react'
import { ItemsGauges } from '@/components/ItemsGauges'

const meta: Meta<typeof ItemsGauges> = {
  title: 'Components/ItemsGauges',
  component: ItemsGauges,
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component: 'ItemsGauges component with complex responsive grid layout. Features two gauges and a line chart that adapts to different container widths.',
      },
    },
  },
  argTypes: {
    scoreResultsPerHour: {
      control: { type: 'range', min: 0, max: 100, step: 1 },
      description: 'Score results per hour value for the first gauge',
    },
    itemsPerHour: {
      control: { type: 'range', min: 0, max: 50, step: 1 },
      description: 'Items per hour value for the second gauge',
    },
    useRealData: {
      control: { type: 'boolean' },
      description: 'Whether to use real data from the API or override props',
    },
  },
} satisfies Meta<typeof ItemsGauges>

export default meta
type Story = StoryObj<typeof meta>

// Sample chart data variations
const lowActivityData = [
  { time: '00:00', items: 1, scoreResults: 1 },
  { time: '04:00', items: 0, scoreResults: 1 },
  { time: '08:00', items: 2, scoreResults: 2 },
  { time: '12:00', items: 3, scoreResults: 3 },
  { time: '16:00', items: 1, scoreResults: 2 },
  { time: '20:00', items: 1, scoreResults: 1 },
]

const highActivityData = [
  { time: '00:00', items: 18, scoreResults: 27 },
  { time: '04:00', items: 15, scoreResults: 23 },
  { time: '08:00', items: 25, scoreResults: 37 },
  { time: '12:00', items: 31, scoreResults: 47 },
  { time: '16:00', items: 34, scoreResults: 51 },
  { time: '20:00', items: 21, scoreResults: 31 },
]

const spikyActivityData = [
  { time: '00:00', items: 2, scoreResults: 3 },
  { time: '02:00', items: 1, scoreResults: 2 },
  { time: '04:00', items: 18, scoreResults: 27 },
  { time: '06:00', items: 3, scoreResults: 5 },
  { time: '08:00', items: 29, scoreResults: 43 },
  { time: '10:00', items: 5, scoreResults: 7 },
  { time: '12:00', items: 38, scoreResults: 57 },
  { time: '14:00', items: 7, scoreResults: 11 },
  { time: '16:00', items: 26, scoreResults: 39 },
  { time: '18:00', items: 9, scoreResults: 13 },
  { time: '20:00', items: 6, scoreResults: 9 },
  { time: '22:00', items: 3, scoreResults: 5 },
]

export const Default: Story = {
  args: {
    scoreResultsPerHour: 42,
    itemsPerHour: 18,
    useRealData: false,
  },
  parameters: {
    docs: {
      description: {
        story: 'Default ItemsGauges with moderate activity levels.',
      },
    },
  },
}

export const HighActivity: Story = {
  args: {
    scoreResultsPerHour: 85,
    itemsPerHour: 35,
    chartData: highActivityData,
    useRealData: false,
  },
  parameters: {
    docs: {
      description: {
        story: 'High activity scenario with elevated gauge values and chart data.',
      },
    },
  },
}

export const LowActivity: Story = {
  args: {
    scoreResultsPerHour: 12,
    itemsPerHour: 4,
    chartData: lowActivityData,
    useRealData: false,
  },
  parameters: {
    docs: {
      description: {
        story: 'Low activity scenario with reduced gauge values and chart data.',
      },
    },
  },
}

export const SpikyActivity: Story = {
  args: {
    scoreResultsPerHour: 67,
    itemsPerHour: 23,
    chartData: spikyActivityData,
    useRealData: false,
  },
  parameters: {
    docs: {
      description: {
        story: 'Spiky activity pattern with more data points showing irregular peaks.',
      },
    },
  },
}

// Layout testing stories with different container widths
export const NarrowContainer: Story = {
  args: {
    scoreResultsPerHour: 42,
    itemsPerHour: 18,
    useRealData: false,
  },
  decorators: [
    (Story) => (
      <div style={{ width: '400px', margin: '0 auto' }}>
        <div className="@container">
          <Story />
        </div>
      </div>
    ),
  ],
  parameters: {
    docs: {
      description: {
        story: 'Layout test: Narrow container (400px) - gauges should stack vertically, chart should be full width below.',
      },
    },
  },
}

export const SmallContainer: Story = {
  args: {
    scoreResultsPerHour: 42,
    itemsPerHour: 18,
    useRealData: false,
  },
  decorators: [
    (Story) => (
      <div style={{ width: '500px', margin: '0 auto' }}>
        <div className="@container">
          <Story />
        </div>
      </div>
    ),
  ],
  parameters: {
    docs: {
      description: {
        story: 'Layout test: Small container (500px) - Should show 3-column layout with chart taking 1 column.',
      },
    },
  },
}

export const MediumContainer: Story = {
  args: {
    scoreResultsPerHour: 42,
    itemsPerHour: 18,
    useRealData: false,
  },
  decorators: [
    (Story) => (
      <div style={{ width: '700px', margin: '0 auto' }}>
        <div className="@container">
          <Story />
        </div>
      </div>
    ),
  ],
  parameters: {
    docs: {
      description: {
        story: 'Layout test: Medium container (700px) - Should show 4-column layout with chart taking 2 columns.',
      },
    },
  },
}

export const WideContainer: Story = {
  args: {
    scoreResultsPerHour: 42,
    itemsPerHour: 18,
    useRealData: false,
  },
  decorators: [
    (Story) => (
      <div style={{ width: '900px', margin: '0 auto' }}>
        <div className="@container">
          <Story />
        </div>
      </div>
    ),
  ],
  parameters: {
    docs: {
      description: {
        story: 'Layout test: Wide container (900px) - Should show 5-column layout with chart spanning 3 columns.',
      },
    },
  },
}

export const ExtraWideContainer: Story = {
  args: {
    scoreResultsPerHour: 42,
    itemsPerHour: 18,
    useRealData: false,
  },
  decorators: [
    (Story) => (
      <div style={{ width: '1100px', margin: '0 auto' }}>
        <div className="@container">
          <Story />
        </div>
      </div>
    ),
  ],
  parameters: {
    docs: {
      description: {
        story: 'Layout test: Extra wide container (1100px) - Should show 6-column layout with chart spanning 4 columns.',
      },
    },
  },
}

// Interactive playground story
export const Playground: Story = {
  args: {
    scoreResultsPerHour: 42,
    itemsPerHour: 18,
    useRealData: false,
  },
  decorators: [
    (Story) => (
      <div className="@container">
        <div className="p-4">
          <div className="mb-4 text-sm text-muted-foreground">
            Resize your browser window or adjust the controls to see the responsive behavior.
            The layout adapts at different breakpoints to maintain optimal spacing.
          </div>
          <Story />
        </div>
      </div>
    ),
  ],
  parameters: {
    docs: {
      description: {
        story: 'Interactive playground - adjust the gauge values and resize the browser to test responsive behavior.',
      },
    },
  },
}

// Edge cases
export const ZeroValues: Story = {
  args: {
    scoreResultsPerHour: 0,
    itemsPerHour: 0,
    chartData: [
      { time: '00:00', value: 0 },
      { time: '04:00', value: 0 },
      { time: '08:00', value: 0 },
      { time: '12:00', value: 0 },
      { time: '16:00', value: 0 },
      { time: '20:00', value: 0 },
    ],
    useRealData: false,
  },
  parameters: {
    docs: {
      description: {
        story: 'Edge case: All zero values - gauges should handle zero gracefully.',
      },
    },
  },
}

export const MaxValues: Story = {
  args: {
    scoreResultsPerHour: 100,
    itemsPerHour: 50,
    chartData: [
      { time: '00:00', value: 95 },
      { time: '04:00', value: 98 },
      { time: '08:00', value: 100 },
      { time: '12:00', value: 100 },
      { time: '16:00', value: 97 },
      { time: '20:00', value: 93 },
    ],
    useRealData: false,
  },
  parameters: {
    docs: {
      description: {
        story: 'Edge case: Maximum values - gauges should handle maximum values correctly.',
      },
    },
  },
}

// Real data story
export const WithRealData: Story = {
  args: {
    useRealData: true,
  },
  parameters: {
    docs: {
      description: {
        story: 'ItemsGauges using real data from the API - shows actual metrics from the last hour.',
      },
    },
  },
}