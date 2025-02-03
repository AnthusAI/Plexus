"use client"

import React from 'react'
import { WorkflowNode } from '../nodes'
import WorkflowBase, { POSITIONS, WorkflowTiming } from '../base/workflow-base'
import type { ComponentType } from 'react'
import type { BaseNodeProps } from '../types'

type NodeProps = BaseNodeProps & {
  status: "not-started" | "processing" | "complete"
  isMain?: boolean
}

// Extended timing for multi-model to show longer processing
const TIMING: WorkflowTiming = {
  main: {
    processingDelay: 0,
    completionDelay: 17000,  // Complete 2 seconds after workers
  },
  'row1-a': {
    processingDelay: 800,     // Slightly earlier than before
    completionDelay: 10700,   // Varied completion
  },
  'row1-b': {
    processingDelay: 2200,    // Slightly later
    completionDelay: 11900,   // Adjusted to avoid sync with 2A
  },
  'row1-c': {
    processingDelay: 2800,    // Earlier than before
    completionDelay: 13100,   // Slightly different timing
  },
  'row2-a': {
    processingDelay: 1800,    // Earlier start
    completionDelay: 12300,   // Adjusted to avoid sync with 1B
  },
  'row2-b': {
    processingDelay: 3200,    // Later start
    completionDelay: 13500,   // More varied
  },
  'row2-c': {
    processingDelay: 3700,    // Slightly earlier
    completionDelay: 14100,   // Different timing
  },
  'row3-a': {
    processingDelay: 2700,    // Earlier
    completionDelay: 12600,   // More varied
  },
  'row3-b': {
    processingDelay: 4300,    // Later
    completionDelay: 14400,   // Adjusted timing
  },
  'row3-c': {
    processingDelay: 4800,    // Slightly earlier
    completionDelay: 15000,   // Keep this timing for main node sync
  },
}

export default function MultiModelWorkflow() {
  const getNodeComponent = (id: string): ComponentType<NodeProps> => {
    switch (id) {
      case 'main':
        return (props: NodeProps) => (
          <WorkflowNode {...props} shape="circle" />
        )
      case 'row1-a':
        return (props: NodeProps) => (
          <WorkflowNode {...props} shape="hexagon" />
        )
      case 'row1-b':
        return (props: NodeProps) => (
          <WorkflowNode {...props} shape="triangle" />
        )
      case 'row1-c':
        return (props: NodeProps) => (
          <WorkflowNode {...props} shape="square" />
        )
      case 'row2-a':
        return (props: NodeProps) => (
          <WorkflowNode {...props} shape="square" />
        )
      case 'row2-b':
        return (props: NodeProps) => (
          <WorkflowNode {...props} shape="circle" />
        )
      case 'row2-c':
        return (props: NodeProps) => (
          <WorkflowNode {...props} shape="hexagon" />
        )
      case 'row3-a':
        return (props: NodeProps) => (
          <WorkflowNode {...props} shape="triangle" />
        )
      case 'row3-b':
        return (props: NodeProps) => (
          <WorkflowNode {...props} shape="hexagon" />
        )
      case 'row3-c':
        return (props: NodeProps) => (
          <WorkflowNode {...props} shape="square" />
        )
      default:
        return (props: NodeProps) => (
          <WorkflowNode {...props} shape="circle" />
        )
    }
  }

  return (
    <WorkflowBase
      positions={POSITIONS}
      getNodeComponent={getNodeComponent}
      timing={TIMING}
    />
  )
} 