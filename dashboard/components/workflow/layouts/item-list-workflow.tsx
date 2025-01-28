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
import { WorkflowStep } from "../types"
import { motion, AnimatePresence } from "framer-motion"

type MediaNodeType = "audio" | "image" | "text"
type NodeResult = "thumbs-up" | "thumbs-down"

interface ExtendedWorkflowStep extends WorkflowStep {
  mediaType?: MediaNodeType
  result?: NodeResult
  processingStartTime?: number
}

const initialSteps: (ExtendedWorkflowStep & { mediaType?: MediaNodeType })[] = [
  // Row 1
  { id: "1-1", label: "Item 1-1", status: "not-started", position: "r1-1", mediaType: "audio" },
  { id: "1-2", label: "Item 1-2", status: "not-started", position: "r1-2" },
  { id: "1-3", label: "Item 1-3", status: "not-started", position: "r1-3" },
  { id: "1-4", label: "Item 1-4", status: "not-started", position: "r1-4" },
  // Row 2
  { id: "2-1", label: "Item 2-1", status: "not-started", position: "r2-1", mediaType: "image" },
  { id: "2-2", label: "Item 2-2", status: "not-started", position: "r2-2" },
  { id: "2-3", label: "Item 2-3", status: "not-started", position: "r2-3" },
  { id: "2-4", label: "Item 2-4", status: "not-started", position: "r2-4" },
  // Row 3
  { id: "3-1", label: "Item 3-1", status: "not-started", position: "r3-1", mediaType: "text" },
  { id: "3-2", label: "Item 3-2", status: "not-started", position: "r3-2" },
  { id: "3-3", label: "Item 3-3", status: "not-started", position: "r3-3" },
  { id: "3-4", label: "Item 3-4", status: "not-started", position: "r3-4" },
  // Row 4
  { id: "4-1", label: "Item 4-1", status: "not-started", position: "r4-1", mediaType: "audio" },
  { id: "4-2", label: "Item 4-2", status: "not-started", position: "r4-2" },
  { id: "4-3", label: "Item 4-3", status: "not-started", position: "r4-3" },
  { id: "4-4", label: "Item 4-4", status: "not-started", position: "r4-4" },
]

const MEDIA_TYPES: MediaNodeType[] = ["audio", "image", "text"]

// Remove the static POSITIONS mapping and replace with a function
const getPosition = (position: string) => {
  const [_, row, col] = position.match(/r(\d+)-(\d+)/) || []
  if (!row || !col) return null
  return {
    x: parseInt(col),
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

    // Only non-media nodes go through state transitions
    if (step.status === "complete") {
      return step.result === "thumbs-down" ? 
        <ThumbsDownNode status={step.status} /> : 
        <ThumbsUpNode status={step.status} />
    }
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
        <BaseConnection startX={1} startY={0} endX={2} endY={0} />
        <BaseConnection startX={2} startY={0} endX={3} endY={0} />
        <BaseConnection startX={3} startY={0} endX={4} endY={0} />
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

  // Reset everything when component mounts
  useEffect(() => {
    // Reset all nodes, keeping media nodes but resetting all others to not-started
    const resetSteps = initialSteps.map(step => ({
      ...step,
      status: "not-started" as const,
      result: undefined,
      processingStartTime: undefined
    }))
    
    setSteps(resetSteps)
    setVisibleRows(1)
    setNextId(5)
    setBaseRow(1)
  }, [])

  const getRandomDelay = useCallback((min: number, max: number) => {
    return Math.random() * (max - min) + min
  }, [])

  const getRandomMediaType = useCallback(() => {
    const index = Math.floor(Math.random() * MEDIA_TYPES.length)
    return MEDIA_TYPES[index]
  }, [])

  const startNodeProcessing = useCallback((stepId: string) => {
    setSteps(currentSteps => {
      const newSteps = [...currentSteps]
      const stepIndex = newSteps.findIndex(s => s.id === stepId)
      if (stepIndex === -1) return currentSteps

      const step = newSteps[stepIndex]
      if (step.status !== "not-started" || step.mediaType) return currentSteps

      step.status = "processing"
      step.processingStartTime = Date.now()
      return newSteps
    })
  }, [])

  const completeNodeProcessing = useCallback((stepId: string) => {
    setSteps(currentSteps => {
      const newSteps = [...currentSteps]
      const stepIndex = newSteps.findIndex(s => s.id === stepId)
      if (stepIndex === -1) return currentSteps

      const step = newSteps[stepIndex]
      if (step.status !== "processing" || step.mediaType) return currentSteps

      step.status = "complete"
      step.result = Math.random() < 0.9 ? "thumbs-up" : "thumbs-down"
      return newSteps
    })
  }, [])

  // Start node processing after random delay
  useEffect(() => {
    const timers: NodeJS.Timeout[] = []

    steps.forEach(step => {
      const position = getPosition(step.position)
      if (!position) return

      // Only start processing if the node is in a fully visible row (not sliding in)
      const isFullyVisible = position.y - baseRow + 1 <= visibleRows
      if (step.status === "not-started" && !step.mediaType && isFullyVisible) {
        const timer = setTimeout(() => {
          startNodeProcessing(step.id)
        }, getRandomDelay(200, 300))
        timers.push(timer)
      }
    })

    return () => timers.forEach(clearTimeout)
  }, [steps, startNodeProcessing, getRandomDelay, baseRow, visibleRows])

  // Complete node processing after random delay
  useEffect(() => {
    const timers: NodeJS.Timeout[] = []

    steps.forEach(step => {
      const position = getPosition(step.position)
      if (!position) return

      // Only complete processing if the node is in a fully visible row (not sliding in)
      const isFullyVisible = position.y - baseRow + 1 <= visibleRows
      if (step.status === "processing" && !step.mediaType && step.processingStartTime && isFullyVisible) {
        const timer = setTimeout(() => {
          completeNodeProcessing(step.id)
        }, getRandomDelay(250, 300))
        timers.push(timer)
      }
    })

    return () => timers.forEach(clearTimeout)
  }, [steps, completeNodeProcessing, getRandomDelay, baseRow, visibleRows])

  // Initial row appearance and conveyor belt effect
  useEffect(() => {
    let timer: NodeJS.Timeout

    const heartbeat = () => {
      if (visibleRows < 4) {
        // Initial phase: Just increment visible rows, media nodes are already set
        setVisibleRows(prev => prev + 1)
      } else {
        // Conveyor belt phase: Add new row and shift
        const newRow = Array.from({ length: 4 }).map((_, i) => ({
          id: `${nextId}-${i + 1}`,
          label: `Item ${nextId}-${i + 1}`,
          status: "not-started" as const,
          position: `r${nextId}-${i + 1}`,
          mediaType: i === 0 ? getRandomMediaType() : undefined
        }))

        setSteps(currentSteps => {
          // Keep only the last 16 items (4 rows) and add the new row
          return [...currentSteps.slice(-16), ...newRow]
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
  }, [visibleRows, nextId, getRandomDelay, getRandomMediaType])

  const getRowSteps = useCallback((steps: (ExtendedWorkflowStep & { mediaType?: MediaNodeType })[], rowIndex: number) => {
    return steps.slice(rowIndex * 4, (rowIndex + 1) * 4)
  }, [])

  return (
    <ContainerBase viewBox="0 0 5 5">
      <AnimatePresence mode="sync">
        {Array.from({ length: Math.ceil(steps.length / 4) }).map((_, index) => {
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