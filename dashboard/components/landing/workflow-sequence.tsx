"use client"

import { useState, useEffect } from "react"
import { ContainerBase } from "../workflow/base/container-base"
import { ConnectionLine } from "../workflow/base/connection-line"
import { CircleNode, SquareNode, TriangleNode, HexagonNode } from "../workflow/nodes"
import { Check } from "lucide-react"

const POSITIONS = {
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

export default function WorkflowSequence() {
  const [currentState, setCurrentState] = useState<"not-started" | "processing" | "complete">("not-started")

  useEffect(() => {
    const cycleStates = () => {
      setCurrentState("not-started")
      
      const processingTimer = setTimeout(() => {
        setCurrentState("processing")
      }, 2000)

      const completeTimer = setTimeout(() => {
        setCurrentState("complete")
      }, 4000)

      // Reset after full cycle
      const resetTimer = setTimeout(() => {
        cycleStates()
      }, 7000)

      return () => {
        clearTimeout(processingTimer)
        clearTimeout(completeTimer)
        clearTimeout(resetTimer)
      }
    }

    cycleStates() // Start the cycle
    return () => {} // Cleanup handled by cycleStates
  }, [])

  return (
    <ContainerBase viewBox="0 0 2.79 2.84">
      {/* Connection Lines */}
      <ConnectionLine 
        startX={0.42} startY={0.42} 
        endX={1.42} endY={1.42} 
        type="curve-right"
      />
      <ConnectionLine 
        startX={0.42} startY={0.42} 
        endX={1.42} endY={2.42} 
        type="curve-down"
      />
      <ConnectionLine 
        startX={1.42} startY={1.42} 
        endX={2.42} endY={1.42} 
      />
      <ConnectionLine 
        startX={1.42} startY={2.42} 
        endX={2.42} endY={2.42} 
      />

      {/* Nodes */}
      {Object.entries(POSITIONS).map(([position, coords]) => {
        const NodeComponent = getNodeComponent(position)
        return (
          <g 
            key={position} 
            transform={`translate(${coords.x}, ${coords.y})`}
          >
            <NodeComponent
              status={currentState}
              isMain={position === "main"}
              icon={Check}
            />
          </g>
        )
      })}
    </ContainerBase>
  )
} 