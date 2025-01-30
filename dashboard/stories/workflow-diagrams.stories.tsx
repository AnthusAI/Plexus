import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import Workflow from '../components/landing/workflow'
import MultiModelWorkflow from '../components/workflow/layouts/multi-model-workflow'
import ItemListWorkflow from '../components/workflow/layouts/item-list-workflow'

const Container = ({ children }: { children: React.ReactNode }) => (
  <div className="resize overflow-auto border-2 border-red-500 rounded-lg p-4 bg-background" 
       style={{ 
         width: '90vw', 
         height: '90vh', 
         minWidth: '420px',
         background: 'linear-gradient(45deg, #f0f0f0 25%, transparent 25%, transparent 75%, #f0f0f0 75%, #f0f0f0) 0 0, linear-gradient(45deg, #f0f0f0 25%, transparent 25%, transparent 75%, #f0f0f0 75%, #f0f0f0) 20px 20px',
         backgroundSize: '40px 40px'
       }}>
    <div className="w-full h-full border border-blue-500 bg-white">
      {children}
    </div>
  </div>
)

const meta = {
  title: 'Workflow Pictograms/Diagrams',
  component: Workflow,
  parameters: {
    layout: 'centered',
  },
} satisfies Meta<typeof Workflow>

export default meta
type Story = StoryObj<typeof Workflow>

export const Base: Story = {
  render: () => (
    <Container>
      <Workflow />
    </Container>
  ),
}

export const MultiModel: Story = {
  render: () => (
    <Container>
      <MultiModelWorkflow />
    </Container>
  ),
}

export const ItemList: Story = {
  render: () => (
    <Container>
      <ItemListWorkflow />
    </Container>
  ),
} 