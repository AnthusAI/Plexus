"use client"

import { useState, useEffect, useRef } from "react"
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
  "row1-c": { x: 3.42, y: 1.42 },
  "row2-a": { x: 1.42, y: 2.42 },
  "row2-b": { x: 2.42, y: 2.42 },
  "row2-c": { x: 3.42, y: 2.42 },
  "row3-a": { x: 1.42, y: 3.42 },
  "row3-b": { x: 2.42, y: 3.42 },
  "row3-c": { x: 3.42, y: 3.42 }
} as const

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
    completionDelay: 8000,  // Complete after all workers
  },
  "row1-a": {
    processingDelay: 1000,
    completionDelay: 4000,
  },
  "row1-b": {
    processingDelay: 2000,
    completionDelay: 5000,
  },
  "row1-c": {
    processingDelay: 3000,
    completionDelay: 6000,
  },
  "row2-a": {
    processingDelay: 1500,
    completionDelay: 4500,
  },
  "row2-b": {
    processingDelay: 2500,
    completionDelay: 5500,
  },
  "row2-c": {
    processingDelay: 3500,
    completionDelay: 6500,
  },
  "row3-a": {
    processingDelay: 2000,
    completionDelay: 5000,
  },
  "row3-b": {
    processingDelay: 3000,
    completionDelay: 6000,
  },
  "row3-c": {
    processingDelay: 4000,
    completionDelay: 7000,
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
  cycle?: boolean
}

const CYCLE_DURATION = 18000 // Base duration of a full cycle (15s completion + 3s pause)
const WATCHDOG_INTERVAL = 2000 // Check every 2 seconds
const MAX_CYCLE_AGE = CYCLE_DURATION * 1.5 // Allow 50% extra time before forcing reset
const COMPLETION_PAUSE = 3000 // Pause for 3 seconds after completion before resetting

const WorkflowBase = React.forwardRef<SVGGElement, WorkflowBaseProps>(
  ({ getNodeComponent, timing = TIMING, positions = POSITIONS, cycle = true }, ref) => {
  const [nodeStates, setNodeStates] = useState<Record<string, "not-started" | "processing" | "complete">>(
    Object.keys(positions).reduce((acc, key) => ({ ...acc, [key]: "not-started" }), {})
  )
  const isPageVisibleRef = useRef(true)
  const timersRef = useRef<NodeJS.Timeout[]>([])
  const cycleStatesFnRef = useRef<() => void>()
  const lastCycleTimeRef = useRef(Date.now())

  // Add watchdog effect
  useEffect(() => {
    const watchdogInterval = setInterval(() => {
      const now = Date.now()
      const timeSinceLastCycle = now - lastCycleTimeRef.current

      // If too much time has passed and we have a cycle function, force a restart
      if (timeSinceLastCycle > MAX_CYCLE_AGE && cycleStatesFnRef.current && isPageVisibleRef.current) {
        cycleStatesFnRef.current()
      }
    }, WATCHDOG_INTERVAL)

    return () => clearInterval(watchdogInterval)
  }, [])

  // Handle page visibility changes
  useEffect(() => {
    const handleVisibilityChange = () => {
      const wasVisible = isPageVisibleRef.current
      isPageVisibleRef.current = !document.hidden
      
      // Clear timers when page becomes hidden
      if (!isPageVisibleRef.current) {
        timersRef.current.forEach(timer => clearTimeout(timer))
        timersRef.current = []
      }
      // Restart cycle when page becomes visible again
      else if (!wasVisible && cycleStatesFnRef.current) {
        cycleStatesFnRef.current()
      }
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }, [])

  useEffect(() => {
    let isCurrentCycle = true

    const processStates = () => {
      // Only process states without automatic reset
      Object.entries(timing).forEach(([node, timing]) => {
        const processingTimer = setTimeout(() => {
          setNodeStates(prev => ({ ...prev, [node]: "processing" }));
        }, timing.processingDelay);
        
        const completeTimer = setTimeout(() => {
          setNodeStates(prev => ({ ...prev, [node]: "complete" }));
        }, timing.completionDelay);

        timersRef.current.push(processingTimer, completeTimer);
      });
    };

    // Define cycleStates function and store in ref for visibility handler
    const cycleStates = () => {
      if (!isCurrentCycle) return;
      
      lastCycleTimeRef.current = Date.now();
      timersRef.current.forEach(timer => clearTimeout(timer));
      timersRef.current = [];
      
      // Reset all nodes to not-started
      setNodeStates(Object.keys(positions).reduce(
        (acc, key) => ({ ...acc, [key]: "not-started" }),
        {}
      ));
      
      // Don't schedule new timers if page is hidden
      if (!isPageVisibleRef.current) return;
      
      processStates();
    };

    // Store cycleStates in ref for visibility handler and watchdog
    cycleStatesFnRef.current = cycleStates;

    processStates();
    
    if (cycle) {
      // Add reset timer only if cycling is enabled
      const resetTimer = setTimeout(() => {
        cycleStates();
      }, Math.max(...Object.values(timing).map(t => t.completionDelay)) + COMPLETION_PAUSE);
      timersRef.current.push(resetTimer);
    }

    return () => {
      isCurrentCycle = false;
      timersRef.current.forEach(clearTimeout);
    };
  }, [timing, cycle, positions]); // Added positions to dependencies

  return (
    <ContainerBase viewBox="0 0 3.79 3.84">
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
          startX={positions.main.x} startY={positions.main.y} 
          endX={positions["row3-a"].x} endY={positions["row3-a"].y} 
          type="curve-down"
        />
        <ConnectionLine 
          startX={positions["row1-a"].x} startY={positions["row1-a"].y} 
          endX={positions["row1-b"].x} endY={positions["row1-b"].y} 
        />
        <ConnectionLine 
          startX={positions["row1-b"].x} startY={positions["row1-b"].y} 
          endX={positions["row1-c"].x} endY={positions["row1-c"].y} 
        />
        <ConnectionLine 
          startX={positions["row2-a"].x} startY={positions["row2-a"].y} 
          endX={positions["row2-b"].x} endY={positions["row2-b"].y} 
        />
        <ConnectionLine 
          startX={positions["row2-b"].x} startY={positions["row2-b"].y} 
          endX={positions["row2-c"].x} endY={positions["row2-c"].y} 
        />
        <ConnectionLine 
          startX={positions["row3-a"].x} startY={positions["row3-a"].y} 
          endX={positions["row3-b"].x} endY={positions["row3-b"].y} 
        />
        <ConnectionLine 
          startX={positions["row3-b"].x} startY={positions["row3-b"].y} 
          endX={positions["row3-c"].x} endY={positions["row3-c"].y} 
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
