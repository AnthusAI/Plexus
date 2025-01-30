"use client"

import { useState, useEffect, useCallback } from "react"
import { ContainerBase } from "../base/container-base"
import { ConnectionLine } from "../base/connection-line"
import { 
  CircleNode,
  ThumbsUpNode,
  ThumbsDownNode
} from "../nodes"
import { AudioNode } from "../nodes/audio-node"
import { ImageNode } from "../nodes/image-node"
import { TextNode } from "../nodes/text-node"
import { WorkflowStep, NodeSequence } from "../types"
import { motion, AnimatePresence } from "framer-motion"
import React from "react"
import { cn } from "@/lib/utils"

type MediaNodeType = "audio" | "image" | "text"
type NodeResult = "thumbs-up" | "thumbs-down"

interface ExtendedWorkflowStep extends WorkflowStep {
  mediaType?: MediaNodeType
  result?: NodeResult
  addedTimestamp: number
  sequence?: NodeSequence
}

// Timing constants for animations
const TIMING = {
  ROW_ENTRANCE: 800,
  NODE_STAGGER: 50,
  INITIAL_DELAY: 200,
  PROCESSING: 1200,
  COMPLETION_BUFFER: 300,
  EXIT: 800,
  HEARTBEAT: 1200, // Base heartbeat interval
  ACCELERATION_DURATION: 30000, // 30 seconds
  MIN_SCALE: 1,
  MAX_SCALE: 2  // Changed from 4 to 2 to limit maximum speed
} as const

// Add jitter to timing values with occasional outliers
const addJitter = (value: number, factor: number = 0.1) => {
  // Occasionally create an outlier (about 10% of the time)
  if (Math.random() < 0.1) {
    // For outliers, use a much larger jitter factor (up to 3x the normal factor)
    const outlierFactor = factor * (2 + Math.random())
    const jitterAmount = (Math.random() * 2 - 0.5) * outlierFactor // Asymmetric distribution
    return Math.round(value * (1 + jitterAmount))
  }
  
  // Normal case: use skewed normal distribution for more natural variation
  const jitterAmount = (Math.random() * Math.random() * 2 - 0.5) * factor
  return Math.round(value * (1 + jitterAmount))
}

// Calculate timing scale factor (1x to 4x over 30 seconds)
const getTimingScale = (startTime: number) => {
  const elapsed = Date.now() - startTime
  if (elapsed >= TIMING.ACCELERATION_DURATION) {
    return TIMING.MAX_SCALE
  }
  return TIMING.MIN_SCALE + (TIMING.MAX_SCALE - TIMING.MIN_SCALE) * (elapsed / TIMING.ACCELERATION_DURATION)
}

// Scale a timing value by the current scale factor
const scaleTime = (value: number, scale: number) => {
  return Math.round(value / scale)
}

// Helper functions for sequence generation
const createNodeSequence = (
  position: number, 
  rowStartTime: number, 
  isMediaNode: boolean = false
): NodeSequence => {
  if (isMediaNode) {
    return {
      startDelay: 0,
      processingDuration: 0,
      completionDelay: 0
    }
  }

  // Add jitter to each timing component with much higher factors
  const initialDelay = addJitter(TIMING.INITIAL_DELAY, 0.8)    // 80% variation
  const staggerDelay = addJitter(position * TIMING.NODE_STAGGER, 0.7)  // 70% variation
  const baseDelay = TIMING.ROW_ENTRANCE + initialDelay + staggerDelay
  const processingTime = addJitter(TIMING.PROCESSING, 0.6)     // 60% variation
  const completionBuffer = addJitter(TIMING.COMPLETION_BUFFER, 0.8)  // 80% variation

  return {
    startDelay: baseDelay,
    processingDuration: processingTime,
    completionDelay: baseDelay + processingTime + completionBuffer
  }
}

const createRowSequences = (
  rowStartTime: number,
  steps: ExtendedWorkflowStep[]
): ExtendedWorkflowStep[] => {
  return steps.map((step, index) => ({
    ...step,
    sequence: createNodeSequence(index, rowStartTime, !!step.mediaType)
  }))
}

const initialSteps: (ExtendedWorkflowStep & { mediaType?: MediaNodeType })[] = [
  // Row 1
  { id: "1-1", label: "Item 1-1", status: "not-started", position: "r1-1", mediaType: "audio", addedTimestamp: 0 },
  { id: "1-2", label: "Item 1-2", status: "not-started", position: "r1-2", addedTimestamp: 0 },
  { id: "1-3", label: "Item 1-3", status: "not-started", position: "r1-3", addedTimestamp: 0 },
  { id: "1-4", label: "Item 1-4", status: "not-started", position: "r1-4", addedTimestamp: 0 },
  { id: "1-5", label: "Item 1-5", status: "not-started", position: "r1-5", addedTimestamp: 0 },
  // Row 2
  { id: "2-1", label: "Item 2-1", status: "not-started", position: "r2-1", mediaType: "image", addedTimestamp: 0 },
  { id: "2-2", label: "Item 2-2", status: "not-started", position: "r2-2", addedTimestamp: 0 },
  { id: "2-3", label: "Item 2-3", status: "not-started", position: "r2-3", addedTimestamp: 0 },
  { id: "2-4", label: "Item 2-4", status: "not-started", position: "r2-4", addedTimestamp: 0 },
  { id: "2-5", label: "Item 2-5", status: "not-started", position: "r2-5", addedTimestamp: 0 },
  // Row 3
  { id: "3-1", label: "Item 3-1", status: "not-started", position: "r3-1", mediaType: "text", addedTimestamp: 0 },
  { id: "3-2", label: "Item 3-2", status: "not-started", position: "r3-2", addedTimestamp: 0 },
  { id: "3-3", label: "Item 3-3", status: "not-started", position: "r3-3", addedTimestamp: 0 },
  { id: "3-4", label: "Item 3-4", status: "not-started", position: "r3-4", addedTimestamp: 0 },
  { id: "3-5", label: "Item 3-5", status: "not-started", position: "r3-5", addedTimestamp: 0 },
  // Row 4
  { id: "4-1", label: "Item 4-1", status: "not-started", position: "r4-1", mediaType: "audio", addedTimestamp: 0 },
  { id: "4-2", label: "Item 4-2", status: "not-started", position: "r4-2", addedTimestamp: 0 },
  { id: "4-3", label: "Item 4-3", status: "not-started", position: "r4-3", addedTimestamp: 0 },
  { id: "4-4", label: "Item 4-4", status: "not-started", position: "r4-4", addedTimestamp: 0 },
  { id: "4-5", label: "Item 4-5", status: "not-started", position: "r4-5", addedTimestamp: 0 },
]

const MEDIA_TYPES: MediaNodeType[] = ["audio", "image", "text"]

// Remove the static POSITIONS mapping and replace with a function
const getPosition = (position: string) => {
  const [_, row, col] = position.match(/r(\d+)-(\d+)/) || []
  if (!row || !col) return null
  return {
    x: 0.32 + (parseInt(col) - 1),  // Start at 0.32, increment by 1
    y: parseInt(row)
  }
}

interface RowProps {
  steps: (ExtendedWorkflowStep & { mediaType?: MediaNodeType })[]
  rowY: number
  yOffset: number
}

const WorkflowRow = React.forwardRef<SVGGElement, RowProps>(({ steps, rowY, yOffset }, ref) => {
  const renderNode = useCallback((step: ExtendedWorkflowStep) => {
    // Media nodes are always shown as-is, no state transitions
    if (step.mediaType) {
      switch (step.mediaType) {
        case "audio":
          return <AudioNode status="complete" />
        case "image":
          return <ImageNode status="complete" />
        case "text":
          return <TextNode status="complete" />
      }
    }

    // Use sequence-based animation for non-media nodes
    if (step.sequence) {
      const now = Date.now()
      const elapsed = now - step.addedTimestamp
      const { startDelay, processingDuration, completionDelay } = step.sequence
      
      // Ensure we spend proportional time in each state
      if (elapsed < startDelay) {
        return step.result === "thumbs-down" ? 
          <ThumbsDownNode status="not-started" sequence={step.sequence} /> : 
          <ThumbsUpNode status="not-started" sequence={step.sequence} />
      }
      
      if (elapsed < startDelay + processingDuration) {
        return step.result === "thumbs-down" ? 
          <ThumbsDownNode status="processing" sequence={step.sequence} /> : 
          <ThumbsUpNode status="processing" sequence={step.sequence} />
      }
      
      return step.result === "thumbs-down" ? 
        <ThumbsDownNode status="complete" sequence={step.sequence} /> : 
        <ThumbsUpNode status="complete" sequence={step.sequence} />
    }

    // Fallback to status-based for backward compatibility
    return <CircleNode status={step.status} isMain={false} />
  }, [])

  // Calculate the target Y position
  const targetY = rowY - yOffset
  
  return (
    <motion.g
      ref={ref}
      initial={{ 
        opacity: 0, 
        y: 5 // Always start from bottom of viewport
      }}
      animate={{ 
        opacity: targetY <= 0.5 ? 0 : targetY >= 4.5 ? 0 : 1,
        y: targetY
      }}
      exit={{
        opacity: 0,
        y: 0, // Always exit at top of viewport
        transition: { 
          duration: 0.3, // Faster exit to match accelerated pace
          ease: "linear"
        }
      }}
      transition={{ 
        duration: 0.3, // Faster transitions to match accelerated pace
        ease: "linear"
      }}
      layout="position"
    >
      {/* Connections */}
      <g transform={`translate(0, 0)`}>
        <ConnectionLine startX={0.32} startY={0} endX={1.32} endY={0} />
        <ConnectionLine startX={1.32} startY={0} endX={2.32} endY={0} />
        <ConnectionLine startX={2.32} startY={0} endX={3.32} endY={0} />
        <ConnectionLine startX={3.32} startY={0} endX={4.32} endY={0} />
      </g>

      {/* Nodes */}
      {steps.map((step) => {
        const position = getPosition(step.position)
        if (!position) return null

        return (
          <motion.g 
            key={step.id}
            style={{ x: position.x }}
          >
            {renderNode(step)}
          </motion.g>
        )
      })}
    </motion.g>
  )
})

// Add display name for better debugging
WorkflowRow.displayName = 'WorkflowRow'

const DEBUG = true // Easy to toggle logging

// Define the component
const ItemListWorkflow = React.forwardRef<SVGGElement>((props, ref) => {
  const [steps, setSteps] = useState<ExtendedWorkflowStep[]>(initialSteps)
  const [visibleRows, setVisibleRows] = useState(1)
  const [nextId, setNextId] = useState(5)
  const [baseRow, setBaseRow] = useState(1)
  const [startTime] = useState(Date.now()) // Add start time for scaling calculation

  const getRandomDelay = useCallback((min: number, max: number) => {
    return Math.random() * (max - min) + min
  }, [])

  const getRandomMediaType = useCallback(() => {
    const index = Math.floor(Math.random() * MEDIA_TYPES.length)
    return MEDIA_TYPES[index]
  }, [])

  const getRandomResult = useCallback(() => {
    return Math.random() < 0.9 ? "thumbs-up" as const : "thumbs-down" as const
  }, [])

  // Helper to create sequences with scaled timing
  const createScaledSequences = useCallback((currentTime: number, steps: ExtendedWorkflowStep[]) => {
    const scale = getTimingScale(startTime)
    return steps.map((step, index) => ({
      ...step,
      sequence: step.mediaType ? undefined : {
        // Higher base jitter with occasional outliers
        startDelay: Math.max(addJitter(TIMING.INITIAL_DELAY / scale, 1.2), 50), // 120% base jitter
        processingDuration: Math.max(addJitter(TIMING.PROCESSING / scale, 1.5), 300), // 150% base jitter
        completionDelay: Math.max(
          addJitter((TIMING.INITIAL_DELAY + TIMING.PROCESSING + TIMING.COMPLETION_BUFFER) / scale, 1.8),
          50
        ) + addJitter(index * TIMING.NODE_STAGGER / scale, 2.0) // 200% jitter on stagger
      }
    }))
  }, [startTime])

  // Reset everything when component mounts
  useEffect(() => {
    const currentTime = Date.now()
    // Reset all nodes, keeping media nodes but resetting all others to not-started
    const resetSteps = initialSteps.map(step => ({
      ...step,
      status: "not-started" as const,
      result: step.mediaType ? undefined : getRandomResult(),
      addedTimestamp: currentTime
    }))
    
    // Add sequences to initial rows
    const sequencedSteps = resetSteps.reduce<ExtendedWorkflowStep[]>((acc, _, index) => {
      if (index % 5 === 0) {
        // Get the next row of 5 steps
        const rowSteps = resetSteps.slice(index, index + 5)
        // Create sequences for this row
        const sequencedRow = createRowSequences(currentTime, rowSteps)
        return [...acc, ...sequencedRow]
      }
      return acc
    }, [])

    setSteps(sequencedSteps)
    setVisibleRows(1)
    setNextId(5)
    setBaseRow(1)
  }, [getRandomResult])

  // Initial row appearance and conveyor belt effect
  useEffect(() => {
    let timer: NodeJS.Timeout

    const scheduleNextHeartbeat = () => {
      const scale = getTimingScale(startTime)
      const interval = Math.max(Math.round(TIMING.HEARTBEAT / scale), 100) // Don't go faster than 100ms
      timer = setTimeout(heartbeat, interval)
    }

    const heartbeat = () => {
      if (visibleRows < 4) {
        // Initial phase: Just increment visible rows, media nodes are already set
        setVisibleRows(prev => prev + 1)
      } else {
        // Create new row
        const now = Date.now()
        const newSteps: ExtendedWorkflowStep[] = Array.from({ length: 5 }).map((_, i) => ({
          id: `${nextId}-${i + 1}`,
          label: `Item ${nextId}-${i + 1}`,
          status: "processing" as const,
          position: `r4-${i + 1}`, // Always start at row 4
          mediaType: i === 0 ? getRandomMediaType() : undefined,
          addedTimestamp: now,
          result: i === 0 ? undefined : getRandomResult()
        }))

        // Add sequences with scaled timing
        const sequencedNewSteps = createScaledSequences(now, newSteps)

        // Update all rows - shift everything up and add new row at bottom
        setSteps(currentSteps => {
          // Keep only the most recent 15 items (3 complete rows)
          const existingRows = currentSteps.slice(-15)
          
          // Update positions for existing rows to shift up
          const updatedExistingRows = existingRows.map((step, index) => {
            const rowNum = Math.floor(index / 5) + 1 // Start at row 1
            const colNum = (index % 5) + 1
            return {
              ...step,
              position: `r${rowNum}-${colNum}`
            }
          })

          return [...updatedExistingRows, ...sequencedNewSteps]
        })

        setNextId(prev => (prev % 50) + 1)
      }

      // Schedule next heartbeat with current scale
      scheduleNextHeartbeat()
    }

    // Start the initial heartbeat
    scheduleNextHeartbeat()

    return () => clearTimeout(timer)
  }, [visibleRows, nextId, getRandomMediaType, getRandomResult, createScaledSequences, startTime])

  // Cleanup old steps periodically
  useEffect(() => {
    const cleanup = () => {
      const currentTime = Date.now()
      setSteps(currentSteps => {
        return currentSteps.filter(step => {
          const age = currentTime - step.addedTimestamp
          return age < 10000 // Remove steps older than 10 seconds
        })
      })
    }

    const cleanupTimer = setInterval(cleanup, 5000)
    return () => clearInterval(cleanupTimer)
  }, [])

  const getRowSteps = useCallback((steps: ExtendedWorkflowStep[], rowIndex: number) => {
    return steps.slice(rowIndex * 5, (rowIndex + 1) * 5)
  }, [])

  // Add diagnostic logging
  useEffect(() => {
    if (DEBUG) {
      /* Diagnostic logging for troubleshooting - uncomment if needed
      const currentTime = Date.now()
      const rowAnalysis = Array.from({ length: Math.ceil(steps.length / 5) }).map((_, index) => {
        const rowSteps = getRowSteps(steps, index)
        return {
          rowIndex: index,
          firstNodeId: rowSteps[0].id,
          nodeCount: rowSteps.length,
          mediaNodes: rowSteps.filter(s => s.mediaType).length,
          oldestTimestamp: Math.min(...rowSteps.map(s => s.addedTimestamp)),
          age: currentTime - Math.min(...rowSteps.map(s => s.addedTimestamp))
        }
      })

      console.log('Workflow State Analysis:', {
        timestamp: new Date().toISOString(),
        totalSteps: steps.length,
        totalRows: Math.ceil(steps.length / 5),
        visibleRows,
        baseRow,
        nextId,
        rowDetails: rowAnalysis,
        memoryUsage: steps.reduce((acc, step) => {
          return acc + (step.sequence ? 1 : 0)
        }, 0),
        timing: {
          oldestNode: Math.min(...steps.map(s => s.addedTimestamp)),
          newestNode: Math.max(...steps.map(s => s.addedTimestamp)),
          timespan: Math.max(...steps.map(s => s.addedTimestamp)) - Math.min(...steps.map(s => s.addedTimestamp))
        }
      })
      */
    }
  }, [steps, visibleRows, baseRow, getRowSteps])

  return (
    <ContainerBase viewBox="0 0 4.64 5">
      <g ref={ref}>
        <AnimatePresence mode="popLayout">
          {Array.from({ length: Math.min(4, Math.ceil(steps.length / 5)) }).map((_, index) => {
            const rowSteps = getRowSteps(steps, index)
            const rowY = index + baseRow

            return (
              <WorkflowRow
                key={rowSteps[0].id}
                steps={rowSteps}
                rowY={rowY}
                yOffset={baseRow - 1}
              />
            )
          })}
        </AnimatePresence>
      </g>
    </ContainerBase>
  )
})

// Add display name before the export
ItemListWorkflow.displayName = 'ItemListWorkflow'

// Export the memoized component
export default React.memo(ItemListWorkflow) 