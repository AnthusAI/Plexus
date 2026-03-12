import type { Meta, StoryObj } from '@storybook/react'
import { ScoreHeaderInfo } from '@/components/ui/score-header-info'
import { useState } from 'react'

const meta: Meta<typeof ScoreHeaderInfo> = {
  title: 'Scorecards/ScoreHeaderInfo',
  component: ScoreHeaderInfo,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
  argTypes: {
    onChange: { action: 'changed' },
  },
}

export default meta
type Story = StoryObj<typeof meta>

// Interactive wrapper component for stories
function InteractiveWrapper(props: any) {
  const [data, setData] = useState(props.data)
  
  const handleChange = (changes: any) => {
    setData((prev: any) => ({ ...prev, ...changes }))
    props.onChange?.(changes)
  }

  return <ScoreHeaderInfo {...props} data={data} onChange={handleChange} />
}

export const Default: Story = {
  render: (args) => <InteractiveWrapper {...args} />,
  args: {
    data: {
      name: 'Customer Satisfaction Score',
      description: 'Measures overall customer satisfaction based on survey responses and interaction quality',
      key: 'csat-v2',
      externalId: 'CSAT_001'
    },
  },
}

export const Empty: Story = {
  render: (args) => <InteractiveWrapper {...args} />,
  args: {
    data: {
      name: '',
      description: '',
      key: '',
      externalId: ''
    },
  },
}

export const PartiallyFilled: Story = {
  render: (args) => <InteractiveWrapper {...args} />,
  args: {
    data: {
      name: 'New Score',
      description: '',
      key: '',
      externalId: ''
    },
  },
}

export const LongContent: Story = {
  render: (args) => <InteractiveWrapper {...args} />,
  args: {
    data: {
      name: 'Very Long Score Name That Might Wrap to Multiple Lines in Narrow Containers',
      description: 'This is a very long description that demonstrates how the component handles longer text content and how it wraps within the available space when the container becomes narrow',
      key: 'very-long-key-name',
      externalId: 'VERY_LONG_EXTERNAL_ID_123'
    },
  },
}

export const CustomPlaceholders: Story = {
  render: (args) => <InteractiveWrapper {...args} />,
  args: {
    data: {
      name: '',
      description: '',
      key: '',
      externalId: ''
    },
    namePlaceholder: 'Enter scorecard name...',
    descriptionPlaceholder: 'Add a description...',
    keyPlaceholder: 'scorecard-key',
    externalIdPlaceholder: 'EXT_ID'
  },
}

// Responsive demonstration stories
export const WideContainer: Story = {
  render: (args) => (
    <div style={{ width: '800px', border: '1px dashed #ccc', padding: '16px' }}>
      <p style={{ marginBottom: '16px', fontSize: '14px', color: '#666' }}>
        Container width: 800px (Grid layout)
      </p>
      <InteractiveWrapper {...args} />
    </div>
  ),
  args: {
    data: {
      name: 'Customer Satisfaction Score',
      description: 'Measures overall customer satisfaction',
      key: 'csat-v2',
      externalId: 'CSAT_001'
    },
  },
}

export const NarrowContainer: Story = {
  render: (args) => (
    <div style={{ width: '400px', border: '1px dashed #ccc', padding: '16px' }}>
      <p style={{ marginBottom: '16px', fontSize: '14px', color: '#666' }}>
        Container width: 400px (Single column layout)
      </p>
      <InteractiveWrapper {...args} />
    </div>
  ),
  args: {
    data: {
      name: 'Customer Satisfaction Score',
      description: 'Measures overall customer satisfaction',
      key: 'csat-v2',
      externalId: 'CSAT_001'
    },
  },
}

export const ResponsiveDemo: Story = {
  render: (args) => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ width: '800px', border: '1px dashed #ccc', padding: '16px' }}>
        <p style={{ marginBottom: '16px', fontSize: '14px', color: '#666' }}>
          Wide container (800px) - Grid layout
        </p>
        <InteractiveWrapper {...args} />
      </div>
      <div style={{ width: '500px', border: '1px dashed #ccc', padding: '16px' }}>
        <p style={{ marginBottom: '16px', fontSize: '14px', color: '#666' }}>
          Medium container (500px) - Single column layout
        </p>
        <InteractiveWrapper {...args} />
      </div>
      <div style={{ width: '300px', border: '1px dashed #ccc', padding: '16px' }}>
        <p style={{ marginBottom: '16px', fontSize: '14px', color: '#666' }}>
          Narrow container (300px) - Single column layout
        </p>
        <InteractiveWrapper {...args} />
      </div>
    </div>
  ),
  args: {
    data: {
      name: 'Customer Satisfaction Score',
      description: 'Measures overall customer satisfaction based on survey responses',
      key: 'csat-v2',
      externalId: 'CSAT_001'
    },
  },
}
