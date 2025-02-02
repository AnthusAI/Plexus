import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import MultiTypeWorkflow from '../components/workflow/layouts/multi-type-workflow'

const meta = {
  title: 'Workflow Pictograms/Diagrams/Multi Type',
  component: MultiTypeWorkflow,
  parameters: {
    layout: 'centered',
  },
} satisfies Meta<typeof MultiTypeWorkflow>

export default meta
type Story = StoryObj<typeof MultiTypeWorkflow>

export const MultiType: Story = {
  render: () => (
    <div className="resize overflow-auto border border-border rounded-lg p-4 bg-background" 
         style={{ width: '90vw', height: '90vh', minWidth: '420px' }}>
      <MultiTypeWorkflow />
    </div>
  )
} 
