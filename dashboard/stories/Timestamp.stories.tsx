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

// Helper functions to get dates for various time periods
const getTimeAgo = (amount: number, unit: 'seconds' | 'minutes' | 'hours' | 'days' | 'weeks' | 'months' | 'years') => {
  const date = new Date()
  
  switch (unit) {
    case 'seconds':
      date.setSeconds(date.getSeconds() - amount)
      break
    case 'minutes':
      date.setMinutes(date.getMinutes() - amount)
      break
    case 'hours':
      date.setHours(date.getHours() - amount)
      break
    case 'days':
      date.setDate(date.getDate() - amount)
      break
    case 'weeks':
      date.setDate(date.getDate() - (amount * 7))
      break
    case 'months':
      date.setMonth(date.getMonth() - amount)
      break
    case 'years':
      date.setFullYear(date.getFullYear() - amount)
      break
  }
  
  return date.toISOString()
}

// Individual story examples
export const RelativeTime: Story = {
  args: {
    time: getTimeAgo(5, 'minutes'),
    variant: 'relative',
    showIcon: true
  }
}

export const ElapsedTimeInProgress: Story = {
  args: {
    time: getTimeAgo(10, 'minutes'),
    variant: 'elapsed',
    showIcon: true
  }
}

export const ElapsedTimeCompleted: Story = {
  args: {
    time: getTimeAgo(10, 'minutes'),
    completionTime: getTimeAgo(2, 'minutes'),
    variant: 'elapsed',
    showIcon: true
  }
}

export const NoIcon: Story = {
  args: {
    time: getTimeAgo(5, 'minutes'),
    variant: 'relative',
    showIcon: false
  }
}

// Comprehensive showcase of different time intervals
export const TimeIntervalShowcase: Story = {
  render: () => (
    <div className="space-y-4 max-w-md">
      <div className="text-lg font-semibold mb-4">Relative Time Intervals</div>
      
      <div className="space-y-3">
        <div className="flex justify-between items-center">
          <span className="text-sm text-muted-foreground w-32">Less than a minute:</span>
          <Timestamp time={getTimeAgo(30, 'seconds')} variant="relative" />
        </div>
        
        <div className="flex justify-between items-center">
          <span className="text-sm text-muted-foreground w-32">~1.5 minutes:</span>
          <Timestamp time={getTimeAgo(90, 'seconds')} variant="relative" />
        </div>
        
        <div className="flex justify-between items-center">
          <span className="text-sm text-muted-foreground w-32">~5 minutes:</span>
          <Timestamp time={getTimeAgo(5, 'minutes')} variant="relative" />
        </div>
        
        <div className="flex justify-between items-center">
          <span className="text-sm text-muted-foreground w-32">~1 hour:</span>
          <Timestamp time={getTimeAgo(1, 'hours')} variant="relative" />
        </div>
        
        <div className="flex justify-between items-center">
          <span className="text-sm text-muted-foreground w-32">~3 hours:</span>
          <Timestamp time={getTimeAgo(3, 'hours')} variant="relative" />
        </div>
        
        <div className="flex justify-between items-center">
          <span className="text-sm text-muted-foreground w-32">~18 hours:</span>
          <Timestamp time={getTimeAgo(18, 'hours')} variant="relative" />
        </div>
        
        <div className="flex justify-between items-center">
          <span className="text-sm text-muted-foreground w-32">Yesterday:</span>
          <Timestamp time={getTimeAgo(1, 'days')} variant="relative" />
        </div>
        
        <div className="flex justify-between items-center">
          <span className="text-sm text-muted-foreground w-32">~1 week:</span>
          <Timestamp time={getTimeAgo(1, 'weeks')} variant="relative" />
        </div>
        
        <div className="flex justify-between items-center">
          <span className="text-sm text-muted-foreground w-32">~3 weeks:</span>
          <Timestamp time={getTimeAgo(3, 'weeks')} variant="relative" />
        </div>
        
        <div className="flex justify-between items-center">
          <span className="text-sm text-muted-foreground w-32">~4 months:</span>
          <Timestamp time={getTimeAgo(4, 'months')} variant="relative" />
        </div>
        
        <div className="flex justify-between items-center">
          <span className="text-sm text-muted-foreground w-32">~2 years:</span>
          <Timestamp time={getTimeAgo(2, 'years')} variant="relative" />
        </div>
      </div>
    </div>
  )
}

// Show width variation issue
export const WidthVariationDemo: Story = {
  render: () => (
    <div className="space-y-4">
      <div className="text-lg font-semibold mb-4">Width Variation Issue</div>
      <div className="text-sm text-muted-foreground mb-4">
        Notice how the text width varies significantly across different time intervals:
      </div>
      
      <div className="space-y-2 border-l-2 border-gray-200 pl-4">
        <div className="flex items-center">
          <div className="w-4 h-4 bg-blue-500 rounded mr-2"></div>
          <Timestamp time={getTimeAgo(30, 'seconds')} variant="relative" />
        </div>
        
        <div className="flex items-center">
          <div className="w-4 h-4 bg-blue-500 rounded mr-2"></div>
          <Timestamp time={getTimeAgo(90, 'seconds')} variant="relative" />
        </div>
        
        <div className="flex items-center">
          <div className="w-4 h-4 bg-blue-500 rounded mr-2"></div>
          <Timestamp time={getTimeAgo(5, 'minutes')} variant="relative" />
        </div>
        
        <div className="flex items-center">
          <div className="w-4 h-4 bg-blue-500 rounded mr-2"></div>
          <Timestamp time={getTimeAgo(1, 'hours')} variant="relative" />
        </div>
        
        <div className="flex items-center">
          <div className="w-4 h-4 bg-blue-500 rounded mr-2"></div>
          <Timestamp time={getTimeAgo(18, 'hours')} variant="relative" />
        </div>
        
        <div className="flex items-center">
          <div className="w-4 h-4 bg-blue-500 rounded mr-2"></div>
          <Timestamp time={getTimeAgo(3, 'weeks')} variant="relative" />
        </div>
        
        <div className="flex items-center">
          <div className="w-4 h-4 bg-blue-500 rounded mr-2"></div>
          <Timestamp time={getTimeAgo(4, 'months')} variant="relative" />
        </div>
      </div>
    </div>
  )
}

export const AllVariants: Story = {
  render: () => (
    <div className="space-y-4">
      <div>
        <div className="text-sm text-muted-foreground mb-2">Relative Time</div>
        <Timestamp time={getTimeAgo(5, 'minutes')} variant="relative" />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Elapsed Time (In Progress)</div>
        <Timestamp time={getTimeAgo(10, 'minutes')} variant="elapsed" />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Elapsed Time (Completed)</div>
        <Timestamp 
          time={getTimeAgo(10, 'minutes')} 
          completionTime={getTimeAgo(2, 'minutes')} 
          variant="elapsed" 
        />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Without Icon</div>
        <Timestamp time={getTimeAgo(5, 'minutes')} variant="relative" showIcon={false} />
      </div>
    </div>
  )
}

// Showcase simplified elapsed time formatting
export const ElapsedTimeFormatting: Story = {
  render: () => (
    <div className="space-y-4 max-w-md">
      <div className="text-lg font-semibold mb-4">Simplified Elapsed Time Formatting</div>
      <div className="text-sm text-muted-foreground mb-4">
        Seconds are only shown when duration is under 1 minute:
      </div>
      
      <div className="space-y-3">
        <div className="flex justify-between items-center">
          <span className="text-sm text-muted-foreground w-32">30 seconds:</span>
          <Timestamp time={getTimeAgo(30, 'seconds')} variant="elapsed" />
        </div>
        
        <div className="flex justify-between items-center">
          <span className="text-sm text-muted-foreground w-32">45 seconds:</span>
          <Timestamp time={getTimeAgo(45, 'seconds')} variant="elapsed" />
        </div>
        
        <div className="flex justify-between items-center">
          <span className="text-sm text-muted-foreground w-32">1.5 minutes:</span>
          <Timestamp time={getTimeAgo(90, 'seconds')} variant="elapsed" />
        </div>
        
        <div className="flex justify-between items-center">
          <span className="text-sm text-muted-foreground w-32">5 minutes:</span>
          <Timestamp time={getTimeAgo(5, 'minutes')} variant="elapsed" />
        </div>
        
        <div className="flex justify-between items-center">
          <span className="text-sm text-muted-foreground w-32">1 hour 15 min:</span>
          <Timestamp time={getTimeAgo(75, 'minutes')} variant="elapsed" />
        </div>
        
        <div className="flex justify-between items-center">
          <span className="text-sm text-muted-foreground w-32">3 hours 45 min:</span>
          <Timestamp time={getTimeAgo(225, 'minutes')} variant="elapsed" />
        </div>
      </div>
    </div>
  )
} 