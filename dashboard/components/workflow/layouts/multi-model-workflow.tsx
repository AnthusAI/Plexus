"use client"

import { useState, useEffect, useCallback } from "react"
import { ContainerBase } from "../base/container-base"
import { BaseConnection } from "../base/connection-base"
import { CircleNode } from "../nodes/circle-node"
import { SquareNode } from "../nodes/square-node"
import { TriangleNode } from "../nodes/triangle-node"
import { HexagonNode } from "../nodes/hexagon-node"
import { WorkflowStep } from "../types"

const initialSteps: WorkflowStep[] = [
  { id: "1", label: "Main Process", status: "not-started", position: "main" },
  { id: "2", label: "Row 1A", status: "not-started", position: "row1-a" },
  { id: "3", label: "Row 1B", status: "not-started", position: "row1-b" },
  { id: "4", label: "Row 2A", status: "not-started", position: "row2-a" },
  { id: "5", label: "Row 2B", status: "not-started", position: "row2-b" },
]

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

export default function MultiModelWorkflow() {
  const [steps, setSteps] = useState<WorkflowStep[]>(initialSteps)
  const [sequence, setSequence] = useState(0)

  const getRandomDelay = useCallback((min: number, max: number) => {
    return Math.random() * (max - min) + min
  }, [])

  const advanceWorkflow = useCallback(() => {
    setSteps((currentSteps) => {
      const newSteps = [...currentSteps]
      switch (sequence) {
        case 0:
          newSteps[0].status = "processing" // Main starts
          break
        case 1:
          newSteps[1].status = "processing" // Row 1A starts
          break
        case 2:
          newSteps[3].status = "processing" // Row 2A starts
          break
        case 3:
          newSteps[2].status = "processing" // Row 1B starts
          break
        case 4:
          newSteps[4].status = "processing" // Row 2B starts
          break
        case 5:
          newSteps[1].status = "complete" // Row 1A completes
          break
        case 6:
          newSteps[3].status = "complete" // Row 2A completes
          break
        case 7:
          newSteps[2].status = "complete" // Row 1B completes
          break
        case 8:
          newSteps[4].status = "complete" // Row 2B completes
          break
        case 9:
          newSteps[0].status = "complete" // Main completes
          break
      }
      return newSteps
    })
    setSequence((prev) => prev + 1)
  }, [sequence])

  useEffect(() => {
    let timer: NodeJS.Timeout

    if (sequence < 10) {
      const delay = getRandomDelay(1000, 2500)
      timer = setTimeout(advanceWorkflow, delay)
    } else {
      const resetDelay = getRandomDelay(3000, 6000)
      timer = setTimeout(() => {
        setSteps((currentSteps) =>
          currentSteps.map((step) => ({
            ...step,
            status: "not-started",
          })),
        )
        setSequence(0)
      }, resetDelay)
    }

    return () => clearTimeout(timer)
  }, [sequence, advanceWorkflow, getRandomDelay])

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
      {steps.map((step) => {
        const position = POSITIONS[step.position as keyof typeof POSITIONS]
        if (!position) return null

        const NodeComponent = getNodeComponent(step.position)
        return (
          <g key={step.id} transform={`translate(${position.x}, ${position.y})`}>
            <NodeComponent
              status={step.status}
              isMain={step.position === "main"}
            />
          </g>
        )
      })}
    </ContainerBase>
  )
} 