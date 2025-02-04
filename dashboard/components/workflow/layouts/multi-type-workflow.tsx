"use client"

import React from 'react'
import { TextNode } from '../nodes/text-node'
import { ThumbsUpNode, ThumbsDownNode, WorkflowNode } from '../nodes'
import WorkflowBase, { POSITIONS, WorkflowTiming } from '../base/workflow-base'
import type { ComponentType } from 'react'
import type { BaseNodeProps } from '../types'
import { Check } from 'lucide-react'

type NodeProps = BaseNodeProps & {
  status: "not-started" | "processing" | "complete"
  isMain?: boolean
}

const MULTI_TYPE_POSITIONS = {
  ...POSITIONS,
  'row1-a': { x: 1.42, y: 1.5 },
  'row1-b': { x: 2.42, y: 1.5 },
  'row1-c': { x: 3.42, y: 1.5 },
  'row2-a': { x: 1.42, y: 2.5 },
  'row2-b': { x: 2.42, y: 2.5 },
  'row2-c': { x: 3.42, y: 2.5 },
  'row3-a': { x: 1.32, y: 3.5 },
  'row3-b': { x: 2.62, y: 3.5 },
  'row3-c': { x: 3.42, y: 3.5 },
}

// Adjusted timing: row3-c completes at 15000ms,
// and the main node completes later (at 21000ms), so its "heartbeat"
// happens noticeably after 3C's completion.
const TIMING: WorkflowTiming = {
  main: {
    processingDelay: 0,
    completionDelay: 16000,    // Complete 1 second after row3-c
  },
  'row1-a': {
    processingDelay: 900,      // Varied start
    completionDelay: 10900,    // Varied completion
  },
  'row1-b': {
    processingDelay: 2300,     // Later start
    completionDelay: 12200,    // Varied completion
  },
  'row1-c': {
    processingDelay: 2700,     // Earlier than before
    completionDelay: 13300,    // Slightly later
  },
  'row2-a': {
    processingDelay: 1700,     // Earlier start
    completionDelay: 11800,    // Earlier completion
  },
  'row2-b': {
    processingDelay: 3300,     // Later start
    completionDelay: 13200,    // Varied completion
  },
  'row2-c': {
    processingDelay: 3800,     // Slightly earlier
    completionDelay: 14300,    // Slightly later
  },
  'row3-a': {
    processingDelay: 2800,     // Varied timing
    completionDelay: 12900,    // Varied completion
  },
  'row3-b': {
    processingDelay: 4200,     // Later
    completionDelay: 14200,    // Later
  },
  'row3-c': {
    processingDelay: 4700,     // Slightly earlier
    completionDelay: 15000,    // Keep this timing for main node sync
  },
}

export default function MultiTypeWorkflow() {
  const getNodeComponent = (id: string): ComponentType<NodeProps> => {
    switch (id) {
      case 'main':
        return (props: NodeProps) => (
          <ThumbsUpNode {...props} />
        )
      case 'row1-a':
        return (props: NodeProps) => (
          <ThumbsUpNode {...props} />
        )
      case 'row1-b':
        return (props: NodeProps) => (
          <WorkflowNode {...props} shape="hexagon" text="N/A" color="true" />
        )
      case 'row1-c':
        return (props: NodeProps) => (
          <WorkflowNode {...props} shape="square" text="7D" color="true" />
        )
      case 'row2-a':
        return (props: NodeProps) => (
          <WorkflowNode {...props} shape="circle" icon={Check} />
        )
      case 'row2-b':
        return (props: NodeProps) => (
          <ThumbsDownNode {...props} />
        )
      case 'row2-c':
        return (props: NodeProps) => (
          <WorkflowNode {...props} shape="square" text="A7" color="muted-foreground" />
        )
      case 'row3-a':
        return (props: NodeProps) => (
          <TextNode {...props} shape="pill" text="stars:5/5" color="primary" />
        )
      case 'row3-b':
        return (props: NodeProps) => (
          <WorkflowNode {...props} shape="circle" text="98" color="true" />
        )
      case 'row3-c':
        return (props: NodeProps) => (
          <ThumbsUpNode {...props} />
        )
      default:
        return TextNode
    }
  }

  return (
    <WorkflowBase
      positions={MULTI_TYPE_POSITIONS}
      getNodeComponent={getNodeComponent}
      timing={TIMING}
    />
  )
} 