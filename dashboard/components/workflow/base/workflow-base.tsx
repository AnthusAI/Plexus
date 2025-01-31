"use client"

import { useState, useEffect } from "react"
import { ContainerBase } from "./container-base"
import { ConnectionLine } from "./connection-line"
import { CircleNode } from "../nodes"
import { Check, type LucideIcon } from "lucide-react"
import React from "react"
import type { ComponentType } from "react"
import { motion, AnimatePresence } from "framer-motion"

export const POSITIONS = {
  main: { x: 0.42, y: 0.42 },
  "row1-a": { x: 1.42, y: 1.42 },
  "row1-b": { x: 2.42, y: 1.42 },
  "row2-a": { x: 1.42, y: 2.42 },
  "row2-b": { x: 2.42, y: 2.42 }
}

type Position = { x: number, y: number }
type WorkflowPositions = Record<keyof typeof POSITIONS, Position>

export type WorkflowTiming = {
  [K in keyof typeof POSITIONS]: {
    processingDelay: number
    completionDelay: number
  }
}

export const TIMING: WorkflowTiming = {
  main: {
    processingDelay: 0,
    completionDelay: 6000,  // Complete 500ms after last worker
  },
  "row1-a": {
    processingDelay: 1000,
    completionDelay: 4000,
  },
  "row1-b": {
    processingDelay: 2000,
    completionDelay: 5000,
  },
  "row2-a": {
    processingDelay: 1500,
    completionDelay: 4500,
  },
  "row2-b": {
    processingDelay: 2500,
    completionDelay: 5500,
  }
} as const

type NodeProps = {
  status: "not-started" | "processing" | "complete"
  isMain?: boolean
  icon?: LucideIcon
}

type WorkflowBaseProps = {
  getNodeComponent?: (position: string) => ComponentType<NodeProps>
  timing?: WorkflowTiming
  positions?: WorkflowPositions
}

const WorkflowBase = React.forwardRef<SVGGElement, WorkflowBaseProps>(
  ({ getNodeComponent, timing = TIMING, positions = POSITIONS }, ref) => {
  const [nodeStates, setNodeStates] = useState<Record<string, "not-started" | "processing" | "complete">>(
    Object.keys(positions).reduce((acc, key) => ({ ...acc, [key]: "not-started" }), {})
  )

  useEffect(() => {
    let isCurrentCycle = true
    let timers: NodeJS.Timeout[] = []

    const cycleStates = () => {
      if (!isCurrentCycle) return

      // Reset all nodes to not-started
      setNodeStates(Object.keys(positions).reduce((acc, key) => ({ ...acc, [key]: "not-started" }), {}))

      // Schedule processing states
      Object.entries(timing).forEach(([node, timing]) => {
        if (!isCurrentCycle) return
        const timer = setTimeout(() => {
          if (!isCurrentCycle) return
          setNodeStates(prev => ({ ...prev, [node]: "processing" }))
        }, timing.processingDelay)
        timers.push(timer)
      })

      // Schedule completion states
      Object.entries(timing).forEach(([node, timing]) => {
        if (!isCurrentCycle) return
        const timer = setTimeout(() => {
          if (!isCurrentCycle) return
          setNodeStates(prev => ({ ...prev, [node]: "complete" }))
        }, timing.completionDelay)
        timers.push(timer)
      })

      // Reset after full cycle
      const resetTimer = setTimeout(() => {
        if (!isCurrentCycle) return
        cycleStates()
      }, Math.max(...Object.values(timing).map(t => t.completionDelay)) + 2000)
      timers.push(resetTimer)
    }

    cycleStates() // Start the cycle

    return () => {
      isCurrentCycle = false
      timers.forEach(timer => clearTimeout(timer))
    }
  }, [timing, positions])

  return (
    <ContainerBase viewBox="0 0 2.79 2.84">
      <g ref={ref}>
        {/* Connection Lines */}
        <ConnectionLine 
          startX={positions.main.x} startY={positions.main.y} 
          endX={positions["row1-a"].x} endY={positions["row1-a"].y} 
          type="curve-right"
        />
        <ConnectionLine 
          startX={positions.main.x} startY={positions.main.y} 
          endX={positions["row2-a"].x} endY={positions["row2-a"].y} 
          type="curve-down"
        />
        <ConnectionLine 
          startX={positions["row1-a"].x} startY={positions["row1-a"].y} 
          endX={positions["row1-b"].x} endY={positions["row1-b"].y} 
        />
        <ConnectionLine 
          startX={positions["row2-a"].x} startY={positions["row2-a"].y} 
          endX={positions["row2-b"].x} endY={positions["row2-b"].y} 
        />

        {/* Nodes */}
        {Object.entries(positions).map(([position, coords]) => {
          const NodeComponent = getNodeComponent?.(position) || CircleNode
          const status = nodeStates[position]
          return (
            <g key={position} transform={`translate(${coords.x}, ${coords.y})`}>
              <NodeComponent
                status={status}
                isMain={position === "main"}
                icon={Check}
              />
              {status === "complete" && (
                <motion.g
                  initial={{ y: -10, opacity: 0 }}
                  animate={{ y: 0, opacity: 1 }}
                  transition={{
                    type: "spring",
                    stiffness: 500,
                    damping: 15,
                    mass: 1
                  }}
                  transform="scale(0.016) translate(-12, -12)"
                >
                  <Check 
                    className="stroke-background dark:stroke-foreground" 
                    size={24}
                    strokeWidth={2.5}
                  />
                </motion.g>
              )}
            </g>
          )
        })}
      </g>
    </ContainerBase>
  )
})

WorkflowBase.displayName = 'WorkflowBase'

export default WorkflowBase 
