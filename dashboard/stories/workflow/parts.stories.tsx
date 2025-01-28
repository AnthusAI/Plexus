import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { CircleNode } from '../../components/workflow/nodes/circle-node'
import { SquareNode } from '../../components/workflow/nodes/square-node'
import { TriangleNode } from '../../components/workflow/nodes/triangle-node'
import { HexagonNode } from '../../components/workflow/nodes/hexagon-node'

const meta = {
  title: 'Workflow Pictograms/Parts',
  component: CircleNode,
  parameters: {
    layout: 'centered',
  },
} satisfies Meta<typeof CircleNode>

export default meta
type Story = StoryObj<typeof CircleNode>

const NodeContainer = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-background p-8">
    <svg width="400" height="100" viewBox="0 0 8 1"
         style={{ border: '1px solid #ccc' }}>
      {children}
    </svg>
  </div>
)

const StateContainer = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-background p-8">
    <svg width="400" height="400" viewBox="0 0 8 4"
         style={{ border: '1px solid #ccc' }}>
      {children}
    </svg>
  </div>
)

export const NodeTypes = {
  render: () => (
    <NodeContainer>
      <g transform="translate(1, 0.5)">
        <CircleNode status="complete" />
      </g>
      <g transform="translate(3, 0.5)">
        <SquareNode status="complete" />
      </g>
      <g transform="translate(5, 0.5)">
        <TriangleNode status="complete" />
      </g>
      <g transform="translate(7, 0.5)">
        <HexagonNode status="complete" />
      </g>
    </NodeContainer>
  ),
}

export const NodeStates = {
  render: () => (
    <StateContainer>
      <g transform="translate(1, 0.5)">
        <CircleNode status="not-started" />
      </g>
      <g transform="translate(3, 0.5)">
        <CircleNode status="processing" />
      </g>
      <g transform="translate(5, 0.5)">
        <CircleNode status="complete" />
      </g>
      
      <g transform="translate(1, 1.5)">
        <SquareNode status="not-started" />
      </g>
      <g transform="translate(3, 1.5)">
        <SquareNode status="processing" />
      </g>
      <g transform="translate(5, 1.5)">
        <SquareNode status="complete" />
      </g>
      
      <g transform="translate(1, 2.5)">
        <TriangleNode status="not-started" />
      </g>
      <g transform="translate(3, 2.5)">
        <TriangleNode status="processing" />
      </g>
      <g transform="translate(5, 2.5)">
        <TriangleNode status="complete" />
      </g>
      
      <g transform="translate(1, 3.5)">
        <HexagonNode status="not-started" />
      </g>
      <g transform="translate(3, 3.5)">
        <HexagonNode status="processing" />
      </g>
      <g transform="translate(5, 3.5)">
        <HexagonNode status="complete" />
      </g>
    </StateContainer>
  ),
} 