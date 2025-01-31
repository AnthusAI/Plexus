"use client"

import { CircleNode, SquareNode, TriangleNode, HexagonNode } from "../nodes"
import { Check } from "lucide-react"
import React from "react"
import WorkflowBase, { WorkflowTiming } from "../base/workflow-base"

const getNodeComponent = (position: string) => {
  switch (position) {
    case "main":
      return CircleNode
    case "row1-a":
      return HexagonNode
    case "row1-b":
      return TriangleNode
    case "row2-a":
      return SquareNode
    case "row2-b":
      return HexagonNode
    default:
      return CircleNode
  }
}

// Custom timing configuration that emphasizes processing states
const MULTI_MODEL_TIMING: WorkflowTiming = {
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

const MultiModelWorkflow = React.forwardRef<SVGGElement>((props, ref) => {
  return <WorkflowBase ref={ref} getNodeComponent={getNodeComponent} timing={MULTI_MODEL_TIMING} />
})

MultiModelWorkflow.displayName = 'MultiModelWorkflow'

export default React.memo(MultiModelWorkflow) 