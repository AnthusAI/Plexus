"use client"

import { useState, useEffect, useCallback } from "react"
import { ContainerBase } from "../base/container-base"
import { BaseConnection } from "../base/connection-base"
import { CircleNode } from "../nodes/circle-node"
import { AudioNode } from "../nodes/audio-node"
import { ImageNode } from "../nodes/image-node"
import { TextNode } from "../nodes/text-node"
import { WorkflowStep } from "../types"
import { motion, AnimatePresence } from "framer-motion"

type MediaNodeType = "audio" | "image" | "text"

const initialSteps: (WorkflowStep & { mediaType?: MediaNodeType })[] = [
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
  steps: (WorkflowStep & { mediaType?: MediaNodeType })[]
  rowY: number
  yOffset: number
}

function WorkflowRow({ steps, rowY, yOffset }: RowProps) {
  const renderNode = useCallback((step: WorkflowStep & { mediaType?: MediaNodeType }) => {
    if (step.mediaType) {
      switch (step.mediaType) {
        case "audio":
          return <AudioNode status={step.status} />
        case "image":
          return <ImageNode status={step.status} />
        case "text":
          return <TextNode status={step.status} />
      }
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
  const [steps, setSteps] = useState<(WorkflowStep & { mediaType?: MediaNodeType })[]>(initialSteps)
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

  // Assign media node to first row immediately
  useEffect(() => {
    setSteps(currentSteps => {
      const newSteps = [...currentSteps]
      newSteps[0].mediaType = getRandomMediaType()
      return newSteps
    })
  }, [getRandomMediaType])

  // Initial row appearance and conveyor belt effect
  useEffect(() => {
    let timer: NodeJS.Timeout

    const heartbeat = () => {
      if (visibleRows < 4) {
        // Initial phase: Add rows until we have 4
        setSteps(currentSteps => {
          const newSteps = [...currentSteps]
          const leftmostIndex = visibleRows * 4
          newSteps[leftmostIndex].mediaType = getRandomMediaType()
          return newSteps
        })
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
      timer = setTimeout(heartbeat, getRandomDelay(500, 1500))
    }

    // Start the heartbeat
    timer = setTimeout(heartbeat, getRandomDelay(500, 1500))

    return () => clearTimeout(timer)
  }, [visibleRows, nextId, getRandomDelay, getRandomMediaType])

  const getRowSteps = useCallback((steps: (WorkflowStep & { mediaType?: MediaNodeType })[], rowIndex: number) => {
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