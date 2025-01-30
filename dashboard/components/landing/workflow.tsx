"use client"

import { useState, useEffect, useMemo } from "react"
import { ContainerBase } from "../workflow/base/container-base"
import { BaseConnection } from "../workflow/base/connection-base"
import { CircleNode } from "../workflow/nodes/circle-node"
import { WorkflowStep } from "../workflow/types"

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

const BASE_SEQUENCES = {
  main: {
    startDelay: 0,
    processingDuration: 5000,
    completionDelay: 5500
  },
  "row1-a": {
    startDelay: 1000,
    processingDuration: 2000,
    completionDelay: 3000
  },
  "row2-a": {
    startDelay: 1500,
    processingDuration: 2000,
    completionDelay: 3500
  },
  "row1-b": {
    startDelay: 2000,
    processingDuration: 2000,
    completionDelay: 4000
  },
  "row2-b": {
    startDelay: 2500,
    processingDuration: 2000,
    completionDelay: 4500
  }
} as const

// Add 10% random variation to timing
const addJitter = (value: number) => {
  const jitterFactor = 1 + (Math.random() * 0.2 - 0.1) // ±10%
  return Math.round(value * jitterFactor)
}

export default function Workflow() {
  const [key, setKey] = useState(0)
  
  // Create new jittered sequences on each render cycle
  const NODE_SEQUENCES = useMemo(() => {
    return Object.entries(BASE_SEQUENCES).reduce((acc, [key, sequence]) => {
      (acc as any)[key] = {
        startDelay: key === 'main' ? 0 : addJitter(sequence.startDelay), // Keep main start exact
        processingDuration: addJitter(sequence.processingDuration),
        completionDelay: addJitter(sequence.completionDelay)
      }
      return acc
    }, {} as Record<keyof typeof BASE_SEQUENCES, typeof BASE_SEQUENCES[keyof typeof BASE_SEQUENCES]>)
  }, [key]) // Recreate when key changes (on reset)
  
  useEffect(() => {
    const totalDuration = 7000
    const timer = setInterval(() => {
      setKey(k => k + 1)
    }, totalDuration)
    
    return () => clearInterval(timer)
  }, [])

  return (
    <ContainerBase key={key} viewBox="0 0 2.74 2.84">
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
      {Object.entries(POSITIONS).map(([position, coords]) => (
        <g 
          key={position} 
          transform={`translate(${coords.x}, ${coords.y})`}
        >
          <CircleNode
            sequence={NODE_SEQUENCES[position as keyof typeof NODE_SEQUENCES]}
            isMain={position === "main"}
          />
        </g>
      ))}
    </ContainerBase>
  )
}

