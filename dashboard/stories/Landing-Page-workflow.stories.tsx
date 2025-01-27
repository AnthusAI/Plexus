import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import Workflow from '../components/landing/workflow'

const meta = {
  title: 'Landing/Workflow',
  component: Workflow,
  parameters: {
    layout: 'centered',
  },
  decorators: [
    (Story) => (
      <div className="bg-background p-4">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof Workflow>

export default meta
type Story = StoryObj<typeof Workflow>

export const Default: Story = {
  decorators: [
    (Story) => (
      <div className="bg-background p-4">
        <div className="w-[400px] border-2 border-border">
          <Story />
        </div>
      </div>
    ),
  ],
}

export const ResponsiveContainer: Story = {
  decorators: [
    (Story) => (
      <div 
        className="resize overflow-auto border border-border rounded-lg" 
        style={{ minWidth: '420px', width: '90vw', height: '90vh' }}
      >
        <div className="border-2 border-border">
          <Story />
        </div>
      </div>
    ),
  ],
} 