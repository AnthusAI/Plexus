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

// Timing adjusted for quick processing and long completion phase
// Main node stays processing until all worker nodes complete
const TIMING: WorkflowTiming = {
  main: {
    processingDelay: 0,      // Start immediately
    completionDelay: 15000,  // Complete after all workers
  },
  'row1-a': {
    processingDelay: 1000,
    completionDelay: 11000,
  },
  'row1-b': {
    processingDelay: 2000,
    completionDelay: 12000,
  },
  'row1-c': {
    processingDelay: 3000,
    completionDelay: 13000,
  },
  'row2-a': {
    processingDelay: 2000,
    completionDelay: 12000,
  },
  'row2-b': {
    processingDelay: 3000,
    completionDelay: 13000,
  },
  'row2-c': {
    processingDelay: 4000,
    completionDelay: 14000,
  },
  'row3-a': {
    processingDelay: 3000,
    completionDelay: 13000,
  },
  'row3-b': {
    processingDelay: 4000,
    completionDelay: 14000,
  },
  'row3-c': {
    processingDelay: 5000,
    completionDelay: 15000,
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
          <WorkflowNode {...props} shape="square" text="Skip" color="muted-foreground" />
        )
      case 'row3-a':
        return (props: NodeProps) => (
          <TextNode {...props} shape="pill" text="stars:5/5" color="primary" />
        )
      case 'row3-b':
        return (props: NodeProps) => (
          <WorkflowNode {...props} shape="circle" text="98%" color="true" />
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