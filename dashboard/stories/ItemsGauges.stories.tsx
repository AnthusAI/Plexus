import type { Meta, StoryObj } from '@storybook/react'
import { ItemsGauges } from '@/components/ItemsGauges'
import { AccountProvider } from '@/app/contexts/AccountContext'

// Mock account data for Storybook
const mockAccount = {
  id: 'story-account-123',
  name: 'Storybook Account',
  email: 'storybook@example.com'
}

// Mock AccountProvider for Storybook
const MockAccountProvider = ({ children }: { children: React.ReactNode }) => (
  <AccountProvider value={{ 
    selectedAccount: mockAccount, 
    setSelectedAccount: () => {}, 
    accounts: [mockAccount],
    isLoading: false 
  }}>
    {children}
  </AccountProvider>
)

const meta: Meta<typeof ItemsGauges> = {
  title: 'Components/ItemsGauges',
  component: ItemsGauges,
  decorators: [
    (Story) => (
      <MockAccountProvider>
        <div className="@container">
          <Story />
        </div>
      </MockAccountProvider>
    ),
  ],
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
    scoreResultsAveragePerHour: {
      control: { type: 'range', min: 0, max: 100, step: 1 },
      description: '24-hour average score results per hour (light needle)',
    },
    itemsAveragePerHour: {
      control: { type: 'range', min: 0, max: 50, step: 1 },
      description: '24-hour average items per hour (light needle)',
    },
    itemsPeakHourly: {
      control: { type: 'range', min: 1, max: 100, step: 1 },
      description: 'Peak items per hour over 24h (gauge maximum)',
    },
    scoreResultsPeakHourly: {
      control: { type: 'range', min: 1, max: 200, step: 1 },
      description: 'Peak score results per hour over 24h (gauge maximum)',
    },
    itemsTotal24h: {
      control: { type: 'range', min: 0, max: 2000, step: 10 },
      description: 'Total items over last 24 hours',
    },
    scoreResultsTotal24h: {
      control: { type: 'range', min: 0, max: 5000, step: 10 },
      description: 'Total score results over last 24 hours', 
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
  { time: '00:00', items: 1, scoreResults: 1, bucketStart: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(), bucketEnd: new Date(Date.now() - 23 * 60 * 60 * 1000).toISOString() },
  { time: '04:00', items: 0, scoreResults: 1, bucketStart: new Date(Date.now() - 20 * 60 * 60 * 1000).toISOString(), bucketEnd: new Date(Date.now() - 19 * 60 * 60 * 1000).toISOString() },
  { time: '08:00', items: 2, scoreResults: 2, bucketStart: new Date(Date.now() - 16 * 60 * 60 * 1000).toISOString(), bucketEnd: new Date(Date.now() - 15 * 60 * 60 * 1000).toISOString() },
  { time: '12:00', items: 3, scoreResults: 3, bucketStart: new Date(Date.now() - 12 * 60 * 60 * 1000).toISOString(), bucketEnd: new Date(Date.now() - 11 * 60 * 60 * 1000).toISOString() },
  { time: '16:00', items: 1, scoreResults: 2, bucketStart: new Date(Date.now() - 8 * 60 * 60 * 1000).toISOString(), bucketEnd: new Date(Date.now() - 7 * 60 * 60 * 1000).toISOString() },
  { time: '20:00', items: 1, scoreResults: 1, bucketStart: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(), bucketEnd: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString() },
]

const highActivityData = [
  { time: '00:00', items: 18, scoreResults: 27, bucketStart: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(), bucketEnd: new Date(Date.now() - 23 * 60 * 60 * 1000).toISOString() },
  { time: '04:00', items: 15, scoreResults: 23, bucketStart: new Date(Date.now() - 20 * 60 * 60 * 1000).toISOString(), bucketEnd: new Date(Date.now() - 19 * 60 * 60 * 1000).toISOString() },
  { time: '08:00', items: 25, scoreResults: 37, bucketStart: new Date(Date.now() - 16 * 60 * 60 * 1000).toISOString(), bucketEnd: new Date(Date.now() - 15 * 60 * 60 * 1000).toISOString() },
  { time: '12:00', items: 31, scoreResults: 47, bucketStart: new Date(Date.now() - 12 * 60 * 60 * 1000).toISOString(), bucketEnd: new Date(Date.now() - 11 * 60 * 60 * 1000).toISOString() },
  { time: '16:00', items: 34, scoreResults: 51, bucketStart: new Date(Date.now() - 8 * 60 * 60 * 1000).toISOString(), bucketEnd: new Date(Date.now() - 7 * 60 * 60 * 1000).toISOString() },
  { time: '20:00', items: 21, scoreResults: 31, bucketStart: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(), bucketEnd: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString() },
]

const spikyActivityData = [
  { time: '00:00', items: 2, scoreResults: 3, bucketStart: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(), bucketEnd: new Date(Date.now() - 23 * 60 * 60 * 1000).toISOString() },
  { time: '02:00', items: 1, scoreResults: 2, bucketStart: new Date(Date.now() - 22 * 60 * 60 * 1000).toISOString(), bucketEnd: new Date(Date.now() - 21 * 60 * 60 * 1000).toISOString() },
  { time: '04:00', items: 18, scoreResults: 27, bucketStart: new Date(Date.now() - 20 * 60 * 60 * 1000).toISOString(), bucketEnd: new Date(Date.now() - 19 * 60 * 60 * 1000).toISOString() },
  { time: '06:00', items: 3, scoreResults: 5, bucketStart: new Date(Date.now() - 18 * 60 * 60 * 1000).toISOString(), bucketEnd: new Date(Date.now() - 17 * 60 * 60 * 1000).toISOString() },
  { time: '08:00', items: 29, scoreResults: 43, bucketStart: new Date(Date.now() - 16 * 60 * 60 * 1000).toISOString(), bucketEnd: new Date(Date.now() - 15 * 60 * 60 * 1000).toISOString() },
  { time: '10:00', items: 5, scoreResults: 7, bucketStart: new Date(Date.now() - 14 * 60 * 60 * 1000).toISOString(), bucketEnd: new Date(Date.now() - 13 * 60 * 60 * 1000).toISOString() },
  { time: '12:00', items: 38, scoreResults: 57, bucketStart: new Date(Date.now() - 12 * 60 * 60 * 1000).toISOString(), bucketEnd: new Date(Date.now() - 11 * 60 * 60 * 1000).toISOString() },
  { time: '14:00', items: 7, scoreResults: 11, bucketStart: new Date(Date.now() - 10 * 60 * 60 * 1000).toISOString(), bucketEnd: new Date(Date.now() - 9 * 60 * 60 * 1000).toISOString() },
  { time: '16:00', items: 26, scoreResults: 39, bucketStart: new Date(Date.now() - 8 * 60 * 60 * 1000).toISOString(), bucketEnd: new Date(Date.now() - 7 * 60 * 60 * 1000).toISOString() },
  { time: '18:00', items: 9, scoreResults: 13, bucketStart: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(), bucketEnd: new Date(Date.now() - 5 * 60 * 60 * 1000).toISOString() },
  { time: '20:00', items: 6, scoreResults: 9, bucketStart: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(), bucketEnd: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString() },
  { time: '22:00', items: 3, scoreResults: 5, bucketStart: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(), bucketEnd: new Date(Date.now() - 1 * 60 * 60 * 1000).toISOString() },
]

export const Default: Story = {
  args: {
    scoreResultsPerHour: 42,
    itemsPerHour: 18,
    scoreResultsAveragePerHour: 35,
    itemsAveragePerHour: 15,
    scoreResultsPeakHourly: 60,
    itemsPeakHourly: 25,
    scoreResultsTotal24h: 840, // 35 * 24
    itemsTotal24h: 360, // 15 * 24
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
    scoreResultsAveragePerHour: 68,
    itemsAveragePerHour: 28,
    scoreResultsPeakHourly: 120,
    itemsPeakHourly: 50,
    scoreResultsTotal24h: 1632, // 68 * 24
    itemsTotal24h: 672, // 28 * 24
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
    scoreResultsAveragePerHour: 8,
    itemsAveragePerHour: 3,
    scoreResultsPeakHourly: 25,
    itemsPeakHourly: 8,
    scoreResultsTotal24h: 192, // 8 * 24
    itemsTotal24h: 72, // 3 * 24
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
    scoreResultsAveragePerHour: 52,
    itemsAveragePerHour: 18,
    scoreResultsPeakHourly: 80,
    itemsPeakHourly: 35,
    scoreResultsTotal24h: 1248, // 52 * 24
    itemsTotal24h: 432, // 18 * 24
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
    scoreResultsAveragePerHour: 35,
    itemsAveragePerHour: 15,
    scoreResultsPeakHourly: 60,
    itemsPeakHourly: 25,
    scoreResultsTotal24h: 840,
    itemsTotal24h: 360,
    useRealData: false,
  },
  decorators: [
    (Story) => (
      <MockAccountProvider>
        <div style={{ width: '400px', margin: '0 auto' }}>
          <div className="@container">
            <Story />
          </div>
        </div>
      </MockAccountProvider>
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
    scoreResultsAveragePerHour: 35,
    itemsAveragePerHour: 15,
    scoreResultsPeakHourly: 60,
    itemsPeakHourly: 25,
    scoreResultsTotal24h: 840,
    itemsTotal24h: 360,
    useRealData: false,
  },
  decorators: [
    (Story) => (
      <MockAccountProvider>
        <div style={{ width: '500px', margin: '0 auto' }}>
          <div className="@container">
            <Story />
          </div>
        </div>
      </MockAccountProvider>
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
    scoreResultsAveragePerHour: 35,
    itemsAveragePerHour: 15,
    scoreResultsPeakHourly: 60,
    itemsPeakHourly: 25,
    scoreResultsTotal24h: 840,
    itemsTotal24h: 360,
    useRealData: false,
  },
  decorators: [
    (Story) => (
      <MockAccountProvider>
        <div style={{ width: '700px', margin: '0 auto' }}>
          <div className="@container">
            <Story />
          </div>
        </div>
      </MockAccountProvider>
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
    scoreResultsAveragePerHour: 35,
    itemsAveragePerHour: 15,
    scoreResultsPeakHourly: 60,
    itemsPeakHourly: 25,
    scoreResultsTotal24h: 840,
    itemsTotal24h: 360,
    useRealData: false,
  },
  decorators: [
    (Story) => (
      <MockAccountProvider>
        <div style={{ width: '900px', margin: '0 auto' }}>
          <div className="@container">
            <Story />
          </div>
        </div>
      </MockAccountProvider>
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
    scoreResultsAveragePerHour: 35,
    itemsAveragePerHour: 15,
    scoreResultsPeakHourly: 60,
    itemsPeakHourly: 25,
    scoreResultsTotal24h: 840,
    itemsTotal24h: 360,
    useRealData: false,
  },
  decorators: [
    (Story) => (
      <MockAccountProvider>
        <div style={{ width: '1100px', margin: '0 auto' }}>
          <div className="@container">
            <Story />
          </div>
        </div>
      </MockAccountProvider>
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
    scoreResultsAveragePerHour: 35,
    itemsAveragePerHour: 15,
    scoreResultsPeakHourly: 60,
    itemsPeakHourly: 25,
    scoreResultsTotal24h: 840,
    itemsTotal24h: 360,
    useRealData: false,
  },
  decorators: [
    (Story) => (
      <MockAccountProvider>
        <div className="@container">
          <div className="p-4">
            <div className="mb-4 text-sm text-muted-foreground">
              Resize your browser window or adjust the controls to see the responsive behavior.
              The layout adapts at different breakpoints to maintain optimal spacing.
            </div>
            <Story />
          </div>
        </div>
      </MockAccountProvider>
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
    scoreResultsAveragePerHour: 0,
    itemsAveragePerHour: 0,
    scoreResultsPeakHourly: 10,
    itemsPeakHourly: 5,
    scoreResultsTotal24h: 0,
    itemsTotal24h: 0,
    chartData: [
      { time: '00:00', items: 0, scoreResults: 0 },
      { time: '04:00', items: 0, scoreResults: 0 },
      { time: '08:00', items: 0, scoreResults: 0 },
      { time: '12:00', items: 0, scoreResults: 0 },
      { time: '16:00', items: 0, scoreResults: 0 },
      { time: '20:00', items: 0, scoreResults: 0 },
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
    scoreResultsAveragePerHour: 85,
    itemsAveragePerHour: 42,
    scoreResultsPeakHourly: 100,
    itemsPeakHourly: 50,
    scoreResultsTotal24h: 2040, // 85 * 24
    itemsTotal24h: 1008, // 42 * 24
    chartData: [
      { time: '00:00', items: 45, scoreResults: 95 },
      { time: '04:00', items: 49, scoreResults: 98 },
      { time: '08:00', items: 50, scoreResults: 100 },
      { time: '12:00', items: 50, scoreResults: 100 },
      { time: '16:00', items: 47, scoreResults: 97 },
      { time: '20:00', items: 43, scoreResults: 93 },
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

// Pegged gauges story - when value exceeds maximum
export const PeggedGauges: Story = {
  args: {
    scoreResultsPerHour: 65, // Higher than the peak we'll set (60)
    itemsPerHour: 45, // Higher than the peak we'll set (40)
    scoreResultsAveragePerHour: 48,
    itemsAveragePerHour: 32,
    scoreResultsPeakHourly: 60, // Peak scale - current values exceed this
    itemsPeakHourly: 40, // Peak scale - current values exceed this
    scoreResultsTotal24h: 1152, // 48 * 24
    itemsTotal24h: 768, // 32 * 24
    chartData: highActivityData,
    useRealData: false,
  },
  parameters: {
    docs: {
      description: {
        story: 'Pegged gauges - when current values exceed the maximum scale. Needles should turn gauge-great color, stop at 105%, and show actual values on tick marks.',
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