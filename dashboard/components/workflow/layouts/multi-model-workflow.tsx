"use client"

import { useState, useEffect, useMemo } from "react"
import { ContainerBase } from "../base/container-base"
import { BaseConnection } from "../base/connection-base"
import { CircleNode } from "../nodes/circle-node"
import { SquareNode } from "../nodes/square-node"
import { TriangleNode } from "../nodes/triangle-node"
import { HexagonNode } from "../nodes/hexagon-node"
import { WorkflowStep } from "../types"

const BASE_SEQUENCES = {
  main: {
    startDelay: 0,
    processingDuration: 2000,
    completionDelay: 3000
  },
  "row1-a": {
    startDelay: 1000,
    processingDuration: 2000,
    completionDelay: 3500
  },
  "row2-a": {
    startDelay: 1500,
    processingDuration: 2000,
    completionDelay: 4000
  },
  "row1-b": {
    startDelay: 2000,
    processingDuration: 2000,
    completionDelay: 4500
  },
  "row2-b": {
    startDelay: 2500,
    processingDuration: 2000,
    completionDelay: 5000
  }
} as const

// Add 10% random variation to timing
const addJitter = (value: number) => {
  const jitterFactor = 1 + (Math.random() * 0.2 - 0.1) // ±10%
  return Math.round(value * jitterFactor)
}

const POSITIONS = {
  main: { x: 1, y: 1 },
  "row1-a": { x: 2, y: 2 },
  "row1-b": { x: 3, y: 2 },
  "row2-a": { x: 2, y: 3 },
  "row2-b": { x: 3, y: 3 }
} as const

const getNodeComponent = (position: string) => {
  switch (position) {
    case "main":
      return CircleNode
    case "row1-a":
      return SquareNode
    case "row1-b":
      return TriangleNode
    case "row2-a":
      return HexagonNode
    case "row2-b":
      return SquareNode
    default:
      return CircleNode
  }
}

const initialSteps: WorkflowStep[] = [
  { id: "1", label: "Main Process", status: "not-started", position: "main" },
  { id: "2", label: "Row 1A", status: "not-started", position: "row1-a" },
  { id: "3", label: "Row 1B", status: "not-started", position: "row1-b" },
  { id: "4", label: "Row 2A", status: "not-started", position: "row2-a" },
  { id: "5", label: "Row 2B", status: "not-started", position: "row2-b" },
]

export default function MultiModelWorkflow() {
  const [steps, setSteps] = useState<WorkflowStep[]>(initialSteps)
  const [key, setKey] = useState(0)

  // Create new jittered sequences on each render cycle
  const NODE_SEQUENCES = useMemo(() => {
    return Object.entries(BASE_SEQUENCES).reduce((acc, [key, sequence]) => {
      acc[key as keyof typeof BASE_SEQUENCES] = {
        startDelay: key === 'main' ? 0 : addJitter(sequence.startDelay),
        processingDuration: addJitter(sequence.processingDuration),
        completionDelay: addJitter(sequence.completionDelay)
      }
      return acc
    }, {} as typeof BASE_SEQUENCES)
  }, [key])

  useEffect(() => {
    const totalDuration = 7000
    const timer = setInterval(() => {
      setKey(k => k + 1)
      setSteps(initialSteps)
    }, totalDuration)
    
    return () => clearInterval(timer)
  }, [])

  return (
    <ContainerBase key={key}>
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
      {steps.map((step) => {
        const position = POSITIONS[step.position as keyof typeof POSITIONS]
        const sequence = NODE_SEQUENCES[step.position as keyof typeof NODE_SEQUENCES]
        if (!position || !sequence) return null

        const NodeComponent = getNodeComponent(step.position)
        return (
          <g key={step.id} transform={`translate(${position.x}, ${position.y})`}>
            <NodeComponent
              sequence={sequence}
              isMain={step.position === "main"}
            />
          </g>
        )
      })}
    </ContainerBase>
  )
} 