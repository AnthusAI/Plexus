"use client"

import React from 'react'
import { TextNode } from '../nodes/text-node'
import { ThumbsUpNode, ThumbsDownNode, WorkflowNode, SquareNode } from '../nodes'
import WorkflowBase, { POSITIONS, WorkflowTiming } from '../base/workflow-base'
import type { ComponentType } from 'react'
import type { BaseNodeProps } from '../types'

type NodeProps = BaseNodeProps & {
  status: "not-started" | "processing" | "complete"
  isMain?: boolean
}

const MULTI_TYPE_POSITIONS = {
  ...POSITIONS,
  'row1-a': { x: 1.12, y: 1.5 },
  'row1-b': { x: 1.88, y: 1.5 },
  'row2-a': { x: 0.92, y: 2.5 },
  'row2-b': { x: 2.08, y: 2.5 },
}

// Timing adjusted for quick processing and long completion phase
// Main node stays processing until all worker nodes complete
const TIMING: WorkflowTiming = {
  main: {
    processingDelay: 0,      // Start immediately
    completionDelay: 6000,   // Complete after all workers
  },
  'row1-a': {
    processingDelay: 1000,    // Start at 1s
    completionDelay: 2000,    // Process for 1s
  },
  'row1-b': {
    processingDelay: 2000,    // Start at 2s
    completionDelay: 3000,    // Process for 1s
  },
  'row2-a': {
    processingDelay: 3000,    // Start at 3s
    completionDelay: 4000,    // Process for 1s
  },
  'row2-b': {
    processingDelay: 4000,    // Start at 4s
    completionDelay: 5000,    // Process for 1s
  },
}

export default function MultiTypeWorkflow() {
  const getNodeComponent = (id: string): ComponentType<NodeProps> => {
    switch (id) {
      case 'main':
        return (props: NodeProps) => (
          <WorkflowNode {...props} shape="hexagon" text="92%" color="true" />
        )
      case 'row1-a':
        return (props: NodeProps) => (
          <ThumbsUpNode {...props} />
        )
      case 'row1-b':
        return (props: NodeProps) => (
          <WorkflowNode {...props} shape="square" text="N/A" color="true" />
        )
      case 'row2-a':
        return (props: NodeProps) => (
          <TextNode {...props} shape="pill" text="stars:4/5" color="primary" />
        )
      case 'row2-b':
        return (props: NodeProps) => (
          <ThumbsDownNode {...props} />
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