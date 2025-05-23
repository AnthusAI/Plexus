import React, { useState, useEffect } from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import Workflow from '../components/landing/workflow'
import { 
  CircleNode,
  SquareNode,
  TriangleNode,
  HexagonNode,
  ThumbsUpNode,
  ThumbsDownNode
} from '../components/workflow/nodes'
import { AudioNode } from '../components/workflow/nodes/audio-node'
import { ImageNode } from '../components/workflow/nodes/image-node'
import { TextNode } from '../components/workflow/nodes/text-node'
import { ContainerBase } from '../components/workflow/base/container-base'
import { NodeStatus } from '../components/workflow/types'

const DEMO_DURATION = 3000 // 3 seconds per state

// Update NodeContainer viewBox back to 3 rows
const NodeContainer = ({ children }: { children: React.ReactNode }) => (
  <svg width="600" height="300" viewBox="0 0 6 3">
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
  title: 'Landing Pages/Pictograms/Parts',
  component: Workflow,
  parameters: {
    layout: 'centered',
  },
} satisfies Meta<typeof Workflow>

export default meta
type Story = StoryObj<typeof Workflow>

const SEQUENCE = {
  startDelay: 0,
  processingDuration: 2000,
  completionDelay: 0
}

export const NodeStates = {
  render: () => (
    <div className="space-y-4">
      <div>
        <h3 className="mb-2 font-medium">Not Started</h3>
        <NodeContainer>
          <g transform="translate(0.5, 0.5)">
            <CircleNode status="not-started" />
          </g>
          <g transform="translate(1.5, 0.5)">
            <SquareNode status="not-started" />
          </g>
          <g transform="translate(2.5, 0.5)">
            <TriangleNode status="not-started" />
          </g>
          <g transform="translate(3.5, 0.5)">
            <HexagonNode status="not-started" />
          </g>
          <g transform="translate(4.5, 0.5)">
            <ThumbsUpNode status="not-started" />
          </g>
          <g transform="translate(5.5, 0.5)">
            <ThumbsDownNode status="not-started" />
          </g>
          <g transform="translate(0.5, 1.5)">
            <TextNode status="not-started" shape="circle" text="Yes" color="true" />
          </g>
          <g transform="translate(1.5, 1.5)">
            <TextNode status="not-started" shape="square" text="No" color="false" />
          </g>
          <g transform="translate(3.5, 1.5)">
            <TextNode status="not-started" shape="pill" text="Text" color="true" />
          </g>
          <g transform="translate(1, 2.5)">
            <TextNode status="not-started" shape="pill" text="stars:1/3" color="true" />
          </g>
          <g transform="translate(3, 2.5)">
            <TextNode status="not-started" shape="pill" text="stars:2/3" color="true" />
          </g>
          <g transform="translate(5, 2.5)">
            <TextNode status="not-started" shape="pill" text="stars:3/5" color="true" />
          </g>
        </NodeContainer>
      </div>

      <div>
        <h3 className="mb-2 font-medium">Processing</h3>
        <NodeContainer>
          <g transform="translate(0.5, 0.5)">
            <CircleNode status="processing" />
          </g>
          <g transform="translate(1.5, 0.5)">
            <SquareNode status="processing" />
          </g>
          <g transform="translate(2.5, 0.5)">
            <TriangleNode status="processing" />
          </g>
          <g transform="translate(3.5, 0.5)">
            <HexagonNode status="processing" />
          </g>
          <g transform="translate(4.5, 0.5)">
            <ThumbsUpNode status="processing" />
          </g>
          <g transform="translate(5.5, 0.5)">
            <ThumbsDownNode status="processing" />
          </g>
          <g transform="translate(0.5, 1.5)">
            <TextNode status="processing" shape="circle" text="Yes" color="true" />
          </g>
          <g transform="translate(1.5, 1.5)">
            <TextNode status="processing" shape="square" text="No" color="false" />
          </g>
          <g transform="translate(3.5, 1.5)">
            <TextNode status="processing" shape="pill" text="Text" color="true" />
          </g>
          <g transform="translate(1, 2.5)">
            <TextNode status="processing" shape="pill" text="stars:1/3" color="true" />
          </g>
          <g transform="translate(3, 2.5)">
            <TextNode status="processing" shape="pill" text="stars:2/3" color="true" />
          </g>
          <g transform="translate(5, 2.5)">
            <TextNode status="processing" shape="pill" text="stars:3/5" color="true" />
          </g>
        </NodeContainer>
      </div>

      <div>
        <h3 className="mb-2 font-medium">Complete</h3>
        <NodeContainer>
          <g transform="translate(0.5, 0.5)">
            <CircleNode status="complete" />
          </g>
          <g transform="translate(1.5, 0.5)">
            <SquareNode status="complete" />
          </g>
          <g transform="translate(2.5, 0.5)">
            <TriangleNode status="complete" />
          </g>
          <g transform="translate(3.5, 0.5)">
            <HexagonNode status="complete" />
          </g>
          <g transform="translate(4.5, 0.5)">
            <ThumbsUpNode status="complete" />
          </g>
          <g transform="translate(5.5, 0.5)">
            <ThumbsDownNode status="complete" />
          </g>
          <g transform="translate(0.5, 1.5)">
            <TextNode status="complete" shape="circle" text="Yes" color="true" />
          </g>
          <g transform="translate(1.5, 1.5)">
            <TextNode status="complete" shape="square" text="No" color="false" />
          </g>
          <g transform="translate(3.5, 1.5)">
            <TextNode status="complete" shape="pill" text="Text" color="true" />
          </g>
          <g transform="translate(1, 2.5)">
            <TextNode status="complete" shape="pill" text="stars:1/3" color="true" />
          </g>
          <g transform="translate(3, 2.5)">
            <TextNode status="complete" shape="pill" text="stars:2/3" color="true" />
          </g>
          <g transform="translate(5, 2.5)">
            <TextNode status="complete" shape="pill" text="stars:3/5" color="true" />
          </g>
        </NodeContainer>
      </div>
    </div>
  )
}

const DemoSequence = () => {
  const [demoState, setDemoState] = useState<NodeStatus>("not-started")

  useEffect(() => {
    const cycleStates = () => {
      setDemoState("not-started")
      
      const processingTimer = setTimeout(() => {
        setDemoState("processing")
      }, DEMO_DURATION)

      const completeTimer = setTimeout(() => {
        setDemoState("complete")
      }, DEMO_DURATION * 2)

      // Reset after full cycle
      const resetTimer = setTimeout(() => {
        cycleStates()
      }, DEMO_DURATION * 3)

      return () => {
        clearTimeout(processingTimer)
        clearTimeout(completeTimer)
        clearTimeout(resetTimer)
      }
    }

    cycleStates() // Start the cycle
    return () => {} // Cleanup handled by cycleStates
  }, [])

  return (
    <div className="space-y-4">
      <div>
        <h3 className="mb-2 font-medium">Sequence Demo</h3>
        <NodeContainer>
          <g transform="translate(0.5, 0.5)">
            <CircleNode status={demoState} />
          </g>
          <g transform="translate(1.5, 0.5)">
            <SquareNode status={demoState} />
          </g>
          <g transform="translate(2.5, 0.5)">
            <TriangleNode status={demoState} />
          </g>
          <g transform="translate(3.5, 0.5)">
            <HexagonNode status={demoState} />
          </g>
          <g transform="translate(4.5, 0.5)">
            <ThumbsUpNode status={demoState} />
          </g>
          <g transform="translate(5.5, 0.5)">
            <ThumbsDownNode status={demoState} />
          </g>
          <g transform="translate(0.5, 1.5)">
            <TextNode status={demoState} shape="circle" text="Yes" color="true" />
          </g>
          <g transform="translate(1.5, 1.5)">
            <TextNode status={demoState} shape="square" text="No" color="false" />
          </g>
          <g transform="translate(3.5, 1.5)">
            <TextNode status={demoState} shape="pill" text="Text" color="true" />
          </g>
          <g transform="translate(1, 2.5)">
            <TextNode status={demoState} shape="pill" text="stars:1/3" color="true" />
          </g>
          <g transform="translate(3, 2.5)">
            <TextNode status={demoState} shape="pill" text="stars:2/3" color="true" />
          </g>
          <g transform="translate(5, 2.5)">
            <TextNode status={demoState} shape="pill" text="stars:3/5" color="true" />
          </g>
        </NodeContainer>
      </div>
    </div>
  )
}

export const NodeSequences = {
  render: () => <DemoSequence />
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