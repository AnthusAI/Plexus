"use client"

import { ContainerBase } from "../workflow/base/container-base"
import { BaseConnection } from "../workflow/base/connection-base"
import { WorkflowNodeSequence } from "./workflow-node-sequence"

const POSITIONS = {
  main: { x: 1, y: 1 },
  "row1-a": { x: 2, y: 2 },
  "row1-b": { x: 3, y: 2 },
  "row2-a": { x: 2, y: 3 },
  "row2-b": { x: 3, y: 3 }
} as const

// Pre-calculate all node sequences
const NODE_SEQUENCES = {
  main: {
    startDelay: 0,
    processingDuration: 2000,
    completionDelay: 8000
  },
  "row1-a": {
    startDelay: 500,
    processingDuration: 2000,
    completionDelay: 4500
  },
  "row2-a": {
    startDelay: 1000,
    processingDuration: 2000,
    completionDelay: 5000
  },
  "row1-b": {
    startDelay: 1500,
    processingDuration: 2000,
    completionDelay: 5500
  },
  "row2-b": {
    startDelay: 2000,
    processingDuration: 2000,
    completionDelay: 6000
  }
}

export default function WorkflowSequence() {
  return (
    <ContainerBase>
      {/* Connection Lines */}
      <BaseConnection 
        startX={1} startY={1} 
        endX={2} endY={2} 
        type="curve-right"
      />
      <BaseConnection 
        startX={1} startY={1} 
        endX={2} endY={3} 
        type="curve-down"
      />
      <BaseConnection 
        startX={2} startY={2} 
        endX={3} endY={2} 
      />
      <BaseConnection 
        startX={2} startY={3} 
        endX={3} endY={3} 
      />

      {/* Nodes */}
      {Object.entries(POSITIONS).map(([position, coords]) => (
        <g 
          key={position} 
          transform={`translate(${coords.x}, ${coords.y})`}
        >
          <WorkflowNodeSequence
            sequence={NODE_SEQUENCES[position as keyof typeof NODE_SEQUENCES]}
            isMain={position === "main"}
          />
        </g>
      ))}
    </ContainerBase>
  )
} 