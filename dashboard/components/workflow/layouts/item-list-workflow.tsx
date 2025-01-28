"use client"

import { useState, useEffect, useCallback } from "react"
import { ContainerBase } from "../base/container-base"
import { BaseConnection } from "../base/connection-base"
import { CircleNode } from "../nodes/circle-node"
import { WorkflowStep } from "../types"

const initialSteps: WorkflowStep[] = [
  // Row 1
  { id: "1-1", label: "Item 1-1", status: "not-started", position: "r1-1" },
  { id: "1-2", label: "Item 1-2", status: "not-started", position: "r1-2" },
  { id: "1-3", label: "Item 1-3", status: "not-started", position: "r1-3" },
  { id: "1-4", label: "Item 1-4", status: "not-started", position: "r1-4" },
  // Row 2
  { id: "2-1", label: "Item 2-1", status: "not-started", position: "r2-1" },
  { id: "2-2", label: "Item 2-2", status: "not-started", position: "r2-2" },
  { id: "2-3", label: "Item 2-3", status: "not-started", position: "r2-3" },
  { id: "2-4", label: "Item 2-4", status: "not-started", position: "r2-4" },
  // Row 3
  { id: "3-1", label: "Item 3-1", status: "not-started", position: "r3-1" },
  { id: "3-2", label: "Item 3-2", status: "not-started", position: "r3-2" },
  { id: "3-3", label: "Item 3-3", status: "not-started", position: "r3-3" },
  { id: "3-4", label: "Item 3-4", status: "not-started", position: "r3-4" },
  // Row 4
  { id: "4-1", label: "Item 4-1", status: "not-started", position: "r4-1" },
  { id: "4-2", label: "Item 4-2", status: "not-started", position: "r4-2" },
  { id: "4-3", label: "Item 4-3", status: "not-started", position: "r4-3" },
  { id: "4-4", label: "Item 4-4", status: "not-started", position: "r4-4" },
]

const POSITIONS = {
  // Row 1
  "r1-1": { x: 1, y: 1 },
  "r1-2": { x: 2, y: 1 },
  "r1-3": { x: 3, y: 1 },
  "r1-4": { x: 4, y: 1 },
  // Row 2
  "r2-1": { x: 1, y: 2 },
  "r2-2": { x: 2, y: 2 },
  "r2-3": { x: 3, y: 2 },
  "r2-4": { x: 4, y: 2 },
  // Row 3
  "r3-1": { x: 1, y: 3 },
  "r3-2": { x: 2, y: 3 },
  "r3-3": { x: 3, y: 3 },
  "r3-4": { x: 4, y: 3 },
  // Row 4
  "r4-1": { x: 1, y: 4 },
  "r4-2": { x: 2, y: 4 },
  "r4-3": { x: 3, y: 4 },
  "r4-4": { x: 4, y: 4 },
} as const

export default function ItemListWorkflow() {
  const [steps, setSteps] = useState<WorkflowStep[]>(initialSteps)
  const [sequence, setSequence] = useState(0)

  const getRandomDelay = useCallback((min: number, max: number) => {
    return Math.random() * (max - min) + min
  }, [])

  const advanceWorkflow = useCallback(() => {
    setSteps((currentSteps) => {
      const newSteps = [...currentSteps]
      const currentRow = Math.floor(sequence / 8)
      const isProcessing = sequence % 8 < 4
      const stepIndex = (sequence % 4) + (currentRow * 4)
      
      if (isProcessing) {
        newSteps[stepIndex].status = "processing"
      } else {
        newSteps[stepIndex].status = "complete"
      }
      
      return newSteps
    })
    setSequence((prev) => prev + 1)
  }, [sequence])

  useEffect(() => {
    let timer: NodeJS.Timeout

    if (sequence < 32) {
      const delay = getRandomDelay(500, 1500)
      timer = setTimeout(advanceWorkflow, delay)
    } else {
      const resetDelay = getRandomDelay(2000, 4000)
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
    <ContainerBase viewBox="0 0 5 5">
      {/* Connection Lines */}
      {[1, 2, 3, 4].map((row) => (
        <g key={`connections-row-${row}`}>
          <BaseConnection 
            startX={1} startY={row} 
            endX={2} endY={row} 
          />
          <BaseConnection 
            startX={2} startY={row} 
            endX={3} endY={row} 
          />
          <BaseConnection 
            startX={3} startY={row} 
            endX={4} endY={row} 
          />
        </g>
      ))}

      {/* Nodes */}
      {steps.map((step) => {
        const position = POSITIONS[step.position as keyof typeof POSITIONS]
        if (!position) return null

        return (
          <g key={step.id} transform={`translate(${position.x}, ${position.y})`}>
            <CircleNode
              status={step.status}
              isMain={false}
            />
          </g>
        )
      })}
    </ContainerBase>
  )
} 