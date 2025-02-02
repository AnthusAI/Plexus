"use client"

import { useState, useEffect, useCallback } from "react"
import { ContainerBase } from "../base/container-base"
import { BaseConnection } from "../base/connection-base"
import { CircleNode } from "../nodes/circle-node"
import { AudioNode } from "../nodes/audio-node"
import { ImageNode } from "../nodes/image-node"
import { TextNode } from "../nodes/text-node"
import { ThumbsUpNode } from "../nodes/thumbs-up-node"
import { ThumbsDownNode } from "../nodes/thumbs-down-node"
import { WorkflowStep, NodeSequence } from "../types"
import { motion, AnimatePresence } from "framer-motion"

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
  NODE_STAGGER: 200,
  INITIAL_DELAY: 800,
  PROCESSING: 1200,
  COMPLETION_BUFFER: 300,
  EXIT: 800
} as const

// Add jitter to timing values (±10%)
const addJitter = (value: number, factor: number = 0.1) => {
  const jitterFactor = 1 + (Math.random() * factor * 2 - factor)
  return Math.round(value * jitterFactor)
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

  // Add jitter to each timing component
  const initialDelay = addJitter(TIMING.INITIAL_DELAY, 0.3)
  const staggerDelay = addJitter(position * TIMING.NODE_STAGGER, 0.25)
  const baseDelay = TIMING.ROW_ENTRANCE + initialDelay + staggerDelay
  const processingTime = addJitter(TIMING.PROCESSING, 0.2)
  const completionBuffer = addJitter(TIMING.COMPLETION_BUFFER, 0.3)

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

function WorkflowRow({ steps, rowY, yOffset }: RowProps) {
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
      // Calculate current state based on time
      const now = Date.now()
      const startTime = step.addedTimestamp + step.sequence.startDelay
      const processingTime = startTime + step.sequence.processingDuration
      const completeTime = step.addedTimestamp + step.sequence.completionDelay

      let currentStatus: "not-started" | "processing" | "complete" = "not-started"
      if (now >= completeTime) {
        currentStatus = "complete"
      } else if (now >= startTime) {
        currentStatus = "processing"
      }

      return step.result === "thumbs-down" ? 
        <ThumbsDownNode status={currentStatus} sequence={step.sequence} /> : 
        <ThumbsUpNode status={currentStatus} sequence={step.sequence} />
    }

    // Fallback to status-based for backward compatibility
    return <CircleNode status={step.status} isMain={false} />
  }, [])

  return (
    <motion.g
      initial={{ opacity: 0, y: rowY }}
      animate={{ 
        opacity: rowY - yOffset <= 0.5 ? 0 : rowY - yOffset >= 4.5 ? 0 : 1,
        y: rowY - yOffset
      }}
      exit={{
        opacity: 0,
        y: rowY - yOffset - 1,
        transition: { duration: 0.8, ease: "easeInOut" }
      }}
      transition={{ 
        duration: 0.8, 
        ease: "easeInOut",
        opacity: { duration: 0.6 }
      }}
    >
      {/* Connections */}
      <g transform={`translate(0, 0)`}>
        <BaseConnection startX={0.32} startY={0} endX={1.32} endY={0} />
        <BaseConnection startX={1.32} startY={0} endX={2.32} endY={0} />
        <BaseConnection startX={2.32} startY={0} endX={3.32} endY={0} />
        <BaseConnection startX={3.32} startY={0} endX={4.32} endY={0} />
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
}

export default function ItemListWorkflow() {
  const [steps, setSteps] = useState<ExtendedWorkflowStep[]>(initialSteps)
  const [visibleRows, setVisibleRows] = useState(1)
  const [nextId, setNextId] = useState(5)
  const [baseRow, setBaseRow] = useState(1)

  const getRandomDelay = useCallback((min: number, max: number) => {
    return Math.random() * (max - min) + min
  }, [])

  const getRandomMediaType = useCallback(() => {
    const index = Math.floor(Math.random() * MEDIA_TYPES.length)
    return MEDIA_TYPES[index]
  }, [])

  const getRandomResult = useCallback(() => {
    return Math.random() < 0.95 ? "thumbs-up" as const : "thumbs-down" as const
  }, [])

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

    const heartbeat = () => {
      if (visibleRows < 4) {
        // Initial phase: Just increment visible rows, media nodes are already set
        setVisibleRows(prev => prev + 1)
      } else {
        // Conveyor belt phase: Add new row and shift
        const currentTime = Date.now()
        const newSteps: ExtendedWorkflowStep[] = Array.from({ length: 5 }).map((_, i) => ({
          id: `${nextId}-${i + 1}`,
          label: `Item ${nextId}-${i + 1}`,
          status: "processing" as const,
          position: `r${nextId}-${i + 1}`,
          mediaType: i === 0 ? getRandomMediaType() : undefined,
          addedTimestamp: currentTime,
          result: i === 0 ? undefined : getRandomResult() // Pre-determine results
        }))

        // Add sequences to the new row
        const sequencedNewSteps = createRowSequences(currentTime, newSteps)

        setSteps(currentSteps => {
          // Keep only the last 20 items (4 rows of 5) and add the new row
          return [...currentSteps.slice(-20), ...sequencedNewSteps]
        })
        setNextId(prev => prev + 1)
        setBaseRow(prev => prev + 1)
      }

      // Schedule next heartbeat
      timer = setTimeout(heartbeat, getRandomDelay(1050, 1400))
    }

    // Start the heartbeat
    timer = setTimeout(heartbeat, getRandomDelay(1050, 1400))

    return () => clearTimeout(timer)
  }, [visibleRows, nextId, getRandomDelay, getRandomMediaType, getRandomResult])

  const getRowSteps = useCallback((steps: ExtendedWorkflowStep[], rowIndex: number) => {
    return steps.slice(rowIndex * 5, (rowIndex + 1) * 5)
  }, [])

  return (
    <ContainerBase viewBox="0 0 4.64 5">
      <AnimatePresence mode="sync">
        {Array.from({ length: Math.ceil(steps.length / 5) }).map((_, index) => {
          const rowSteps = getRowSteps(steps, index)
          const rowY = index + baseRow

          if (index >= 5) return null

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
    </ContainerBase>
  )
} 