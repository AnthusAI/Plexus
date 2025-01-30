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

type Position = { x: number, y: number }
type WorkflowPositions = {
  main: Position
  "row1-a": Position
  "row1-b": Position
  "row2-a": Position
  "row2-b": Position
}

const POSITIONS: WorkflowPositions = {
  main: { x: 0.42, y: 0.42 },
  "row1-a": { x: 1.42, y: 1.42 },
  "row1-b": { x: 2.42, y: 1.42 },
  "row2-a": { x: 1.42, y: 2.42 },
  "row2-b": { x: 2.42, y: 2.42 }
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
      (acc as any)[key] = {
        startDelay: key === 'main' ? 0 : addJitter(sequence.startDelay),
        processingDuration: addJitter(sequence.processingDuration),
        completionDelay: addJitter(sequence.completionDelay)
      }
      return acc
    }, {} as Record<keyof typeof BASE_SEQUENCES, typeof BASE_SEQUENCES[keyof typeof BASE_SEQUENCES]>)
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
    <ContainerBase key={key} viewBox="0 0 2.79 2.84">
      {/* Connection Lines */}
      <BaseConnection 
        startX={0.42} startY={0.42} 
        endX={1.42} endY={1.42} 
        type="curve-right"
      />
      <BaseConnection 
        startX={0.42} startY={0.42} 
        endX={1.42} endY={2.42} 
        type="curve-down"
      />
      <BaseConnection 
        startX={1.42} startY={1.42} 
        endX={2.42} endY={1.42} 
      />
      <BaseConnection 
        startX={1.42} startY={2.42} 
        endX={2.42} endY={2.42} 
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