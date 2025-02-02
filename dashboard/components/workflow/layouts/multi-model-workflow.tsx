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