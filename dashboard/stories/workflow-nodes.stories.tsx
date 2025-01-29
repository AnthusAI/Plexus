import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import Workflow from '../components/landing/workflow'
import { CircleNode } from '../components/workflow/nodes/circle-node'
import { SquareNode } from '../components/workflow/nodes/square-node'
import { TriangleNode } from '../components/workflow/nodes/triangle-node'
import { HexagonNode } from '../components/workflow/nodes/hexagon-node'
import { AudioNode } from '../components/workflow/nodes/audio-node'
import { ImageNode } from '../components/workflow/nodes/image-node'
import { TextNode } from '../components/workflow/nodes/text-node'
import { ThumbsUpNode } from '../components/workflow/nodes/thumbs-up-node'
import { ThumbsDownNode } from '../components/workflow/nodes/thumbs-down-node'
import { ContainerBase } from '../components/workflow/base/container-base'

// Update NodeContainer viewBox to fit 6 nodes
const NodeContainer = ({ children }: { children: React.ReactNode }) => (
  <svg width="600" height="100" viewBox="0 0 6 1">
    {children}
  </svg>
)

const Container = ({ children }: { children: React.ReactNode }) => (
  <div className="resize overflow-auto border border-border rounded-lg p-4 bg-background" 
       style={{ width: '90vw', height: '90vh', minWidth: '420px' }}>
    {children}
  </div>
)

const meta = {
  title: 'Workflow Pictograms/Parts',
  component: Workflow,
  parameters: {
    layout: 'centered',
  },
} satisfies Meta<typeof Workflow>

export default meta
type Story = StoryObj<typeof Workflow>

export const NodeStates = {
  render: () => {
    return (
      <div className="space-y-8">
        {/* Not Started State Row */}
        <div>
          <h3 className="mb-2 font-medium">Not Started State</h3>
          <NodeContainer>
            <g transform="translate(0.5, 0.5)">
              <CircleNode status="not-started" sequence={0} startDelay={0} />
            </g>
            <g transform="translate(1.5, 0.5)">
              <SquareNode status="not-started" sequence={0} startDelay={0} />
            </g>
            <g transform="translate(2.5, 0.5)">
              <TriangleNode status="not-started" sequence={0} startDelay={0} />
            </g>
            <g transform="translate(3.5, 0.5)">
              <HexagonNode status="not-started" sequence={0} startDelay={0} />
            </g>
            <g transform="translate(4.5, 0.5)">
              <ThumbsUpNode status="not-started" sequence={0} startDelay={0} />
            </g>
            <g transform="translate(5.5, 0.5)">
              <ThumbsDownNode status="not-started" sequence={0} startDelay={0} />
            </g>
          </NodeContainer>
        </div>

        {/* Processing State Row */}
        <div>
          <h3 className="mb-2 font-medium">Processing State</h3>
          <NodeContainer>
            <g transform="translate(0.5, 0.5)">
              <CircleNode status="processing" sequence={0} startDelay={0} />
            </g>
            <g transform="translate(1.5, 0.5)">
              <SquareNode status="processing" sequence={0} startDelay={0} />
            </g>
            <g transform="translate(2.5, 0.5)">
              <TriangleNode status="processing" sequence={0} startDelay={0} />
            </g>
            <g transform="translate(3.5, 0.5)">
              <HexagonNode status="processing" sequence={0} startDelay={0} />
            </g>
            <g transform="translate(4.5, 0.5)">
              <ThumbsUpNode status="processing" sequence={0} startDelay={0} />
            </g>
            <g transform="translate(5.5, 0.5)">
              <ThumbsDownNode status="processing" sequence={0} startDelay={0} />
            </g>
          </NodeContainer>
        </div>

        {/* Complete State Row */}
        <div>
          <h3 className="mb-2 font-medium">Complete State</h3>
          <NodeContainer>
            <g transform="translate(0.5, 0.5)">
              <CircleNode status="complete" sequence={0} startDelay={0} />
            </g>
            <g transform="translate(1.5, 0.5)">
              <SquareNode status="complete" sequence={0} startDelay={0} />
            </g>
            <g transform="translate(2.5, 0.5)">
              <TriangleNode status="complete" sequence={0} startDelay={0} />
            </g>
            <g transform="translate(3.5, 0.5)">
              <HexagonNode status="complete" sequence={0} startDelay={0} />
            </g>
            <g transform="translate(4.5, 0.5)">
              <ThumbsUpNode status="complete" sequence={0} startDelay={0} />
            </g>
            <g transform="translate(5.5, 0.5)">
              <ThumbsDownNode status="complete" sequence={0} startDelay={0} />
            </g>
          </NodeContainer>
        </div>
      </div>
    )
  }
}

export const NodeSequences = {
  render: () => {
    return (
      <div className="space-y-4">
        <div>
          <h3 className="mb-2 font-medium">Sequence Demo</h3>
          <NodeContainer>
            <g transform="translate(0.5, 0.5)">
              <CircleNode status="processing" sequence={0} startDelay={0} />
            </g>
            <g transform="translate(1.5, 0.5)">
              <SquareNode status="processing" sequence={1} startDelay={1000} />
            </g>
            <g transform="translate(2.5, 0.5)">
              <TriangleNode status="processing" sequence={2} startDelay={2000} />
            </g>
            <g transform="translate(3.5, 0.5)">
              <HexagonNode status="processing" sequence={3} startDelay={3000} />
            </g>
            <g transform="translate(4.5, 0.5)">
              <ThumbsUpNode status="processing" sequence={4} startDelay={4000} />
            </g>
            <g transform="translate(5.5, 0.5)">
              <ThumbsDownNode status="processing" sequence={5} startDelay={5000} />
            </g>
          </NodeContainer>
        </div>
      </div>
    )
  }
}

export const MediaNodes = {
  render: () => (
    <Container>
      <ContainerBase viewBox="0 0 4 2">
        <g transform="translate(1, 1)">
          <AudioNode status="not-started" />
        </g>
        <g transform="translate(2, 1)">
          <ImageNode status="not-started" />
        </g>
        <g transform="translate(3, 1)">
          <TextNode status="not-started" />
        </g>
      </ContainerBase>
    </Container>
  ),
} 