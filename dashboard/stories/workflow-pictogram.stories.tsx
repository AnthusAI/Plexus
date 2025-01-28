import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import Workflow from '../components/landing/workflow'
import MultiModelWorkflow from '../components/workflow/layouts/multi-model-workflow'
import ItemListWorkflow from '../components/workflow/layouts/item-list-workflow'

const meta = {
  title: 'Workflow Pictograms',
  component: Workflow,
  parameters: {
    layout: 'centered',
  },
} satisfies Meta<typeof Workflow>

export default meta
type Story = StoryObj<typeof Workflow>

const Container = ({ children }: { children: React.ReactNode }) => (
  <div className="resize overflow-auto border border-border rounded-lg p-4" 
       style={{ width: '90vw', height: '90vh', minWidth: '420px' }}>
    {children}
  </div>
)

export const Base = {
  render: () => (
    <Container>
      <Workflow />
    </Container>
  ),
}

export const MultiModel = {
  render: () => (
    <Container>
      <MultiModelWorkflow />
    </Container>
  ),
}

export const ItemList = {
  render: () => (
    <Container>
      <ItemListWorkflow />
    </Container>
  ),
} 