import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { ContainerBase } from '../components/workflow/base/container-base'
import { ThumbsUpNode } from '../components/workflow/nodes/thumbs-up-node'
import { ThumbsDownNode } from '../components/workflow/nodes/thumbs-down-node'

const meta = {
  title: 'Workflow Pictograms/Parts/Classifier Nodes',
  component: ContainerBase,
  parameters: {
    layout: 'centered',
  },
} satisfies Meta<typeof ContainerBase>

export default meta
type Story = StoryObj<typeof ContainerBase>

const Container = ({ children }: { children: React.ReactNode }) => (
  <div className="resize overflow-auto border border-border rounded-lg p-4" 
       style={{ width: '90vw', height: '90vh', minWidth: '420px' }}>
    {children}
  </div>
)

export const ClassifierNodes = {
  render: () => (
    <Container>
      <ContainerBase viewBox="0 0 4 3">
        {/* Thumbs Up Row */}
        <g transform="translate(1, 1)">
          <ThumbsUpNode status="not-started" />
        </g>
        <g transform="translate(2, 1)">
          <ThumbsUpNode status="processing" />
        </g>
        <g transform="translate(3, 1)">
          <ThumbsUpNode status="complete" />
        </g>

        {/* Thumbs Down Row */}
        <g transform="translate(1, 2)">
          <ThumbsDownNode status="not-started" />
        </g>
        <g transform="translate(2, 2)">
          <ThumbsDownNode status="processing" />
        </g>
        <g transform="translate(3, 2)">
          <ThumbsDownNode status="complete" />
        </g>
      </ContainerBase>
    </Container>
  ),
} 