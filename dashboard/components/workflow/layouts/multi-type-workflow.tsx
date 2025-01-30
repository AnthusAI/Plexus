"use client"

import { TextNode } from "../nodes/text-node"
import { ThumbsUpNode } from "../nodes"
import React from "react"
import WorkflowBase, { WorkflowTiming, POSITIONS } from "../base/workflow-base"

// Modify the base positions for this specific workflow
const MULTI_TYPE_POSITIONS = {
  ...POSITIONS,
  "row1-a": { x: 1.12, y: 1.42 }, // Shifted left
  "row2-a": { x: 1.12, y: 2.42 }  // Shifted left
}

const getNodeComponent = (position: string) => {
  switch (position) {
    case "main":
      return (props: any) => (
        <TextNode {...props} shape="hexagon" text="92%" color="true" />
      )
    case "row1-a":
      return (props: any) => (
        <TextNode {...props} shape="pill" text="stars:4/5" color="primary" />
      )
    case "row1-b":
      return (props: any) => (
        <TextNode {...props} shape="square" text="N/A" color="false" />
      )
    case "row2-a":
      return (props: any) => (
        <TextNode {...props} shape="pill" text="gamma" color="primary" />
      )
    case "row2-b":
      return (props: any) => (
        <ThumbsUpNode {...props} shape="hexagon" />
      )
    default:
      return (props: any) => <TextNode {...props} />
  }
}

// Custom timing configuration that emphasizes processing states
const MULTI_TYPE_TIMING: WorkflowTiming = {
  main: {
    processingDelay: 0,
    completionDelay: 15000, // 15 seconds of processing
  },
  "row1-a": {
    processingDelay: 1000,
    completionDelay: 11000, // 10 seconds of processing
  },
  "row1-b": {
    processingDelay: 2000,
    completionDelay: 13000, // 11 seconds of processing
  },
  "row2-a": {
    processingDelay: 1500,
    completionDelay: 11500, // 10 seconds of processing
  },
  "row2-b": {
    processingDelay: 2500,
    completionDelay: 13500, // 11 seconds of processing
  }
}

const MultiTypeWorkflow = React.forwardRef<SVGGElement>((props, ref) => {
  return (
    <WorkflowBase 
      ref={ref} 
      getNodeComponent={getNodeComponent} 
      timing={MULTI_TYPE_TIMING}
      positions={MULTI_TYPE_POSITIONS}
    />
  )
})

MultiTypeWorkflow.displayName = 'MultiTypeWorkflow'

export default React.memo(MultiTypeWorkflow) 