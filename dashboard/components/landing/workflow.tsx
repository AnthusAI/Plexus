"use client"

import { useState, useEffect, useMemo } from "react"
import { ContainerBase } from "../workflow/base/container-base"
import { BaseConnection } from "../workflow/base/connection-base"
import { CircleNode } from "../workflow/nodes/circle-node"
import { WorkflowStep } from "../workflow/types"

const POSITIONS = {
  main: { x: 1, y: 1 },
  "row1-a": { x: 2, y: 2 },
  "row1-b": { x: 3, y: 2 },
  "row2-a": { x: 2, y: 3 },
  "row2-b": { x: 3, y: 3 }
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
      acc[key as keyof typeof BASE_SEQUENCES] = {
        startDelay: key === 'main' ? 0 : addJitter(sequence.startDelay), // Keep main start exact
        processingDuration: addJitter(sequence.processingDuration),
        completionDelay: addJitter(sequence.completionDelay)
      }
      return acc
    }, {} as typeof BASE_SEQUENCES)
  }, [key]) // Recreate when key changes (on reset)
  
  useEffect(() => {
    const totalDuration = 7000
    const timer = setInterval(() => {
      setKey(k => k + 1)
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

