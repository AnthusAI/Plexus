import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { Timestamp } from '../components/ui/timestamp'

const meta = {
  title: 'General/UI/Timestamp',
  component: Timestamp,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    variant: {
      control: 'select',
      options: ['elapsed', 'relative'],
      description: 'The variant of the timestamp to display'
    },
    showIcon: {
      control: 'boolean',
      description: 'Whether to show the icon'
    }
  }
} satisfies Meta<typeof Timestamp>

export default meta
type Story = StoryObj<typeof Timestamp>

// Helper to get a date from X minutes ago
const getTimeAgo = (minutes: number) => {
  const date = new Date()
  date.setMinutes(date.getMinutes() - minutes)
  return date.toISOString()
}

export const RelativeTime: Story = {
  args: {
    time: getTimeAgo(5),
    variant: 'relative',
    showIcon: true
  }
}

export const ElapsedTimeInProgress: Story = {
  args: {
    time: getTimeAgo(10),
    variant: 'elapsed',
    showIcon: true
  }
}

export const ElapsedTimeCompleted: Story = {
  args: {
    time: getTimeAgo(10),
    completionTime: getTimeAgo(2),
    variant: 'elapsed',
    showIcon: true
  }
}

export const NoIcon: Story = {
  args: {
    time: getTimeAgo(5),
    variant: 'relative',
    showIcon: false
  }
}

export const AllVariants: Story = {
  render: () => (
    <div className="space-y-4">
      <div>
        <div className="text-sm text-muted-foreground mb-2">Relative Time</div>
        <Timestamp time={getTimeAgo(5)} variant="relative" />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Elapsed Time (In Progress)</div>
        <Timestamp time={getTimeAgo(10)} variant="elapsed" />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Elapsed Time (Completed)</div>
        <Timestamp 
          time={getTimeAgo(10)} 
          completionTime={getTimeAgo(2)} 
          variant="elapsed" 
        />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Without Icon</div>
        <Timestamp time={getTimeAgo(5)} variant="relative" showIcon={false} />
      </div>
    </div>
  )
} 