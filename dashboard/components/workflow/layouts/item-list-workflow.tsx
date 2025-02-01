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
import { WorkflowNode } from "../nodes"
import { ThumbsUp, ThumbsDown, Check } from "lucide-react"

type MediaNodeType = "audio" | "image" | "text"
type NodeResult = "thumbs-up" | "thumbs-down"
type NodeShape = "circle" | "square" | "triangle" | "hexagon" | "pill"
type ResultType = "boolean" | "text" | "stars" | "check"
type NodeColor = "true" | "false" | "card" | "muted-foreground" | undefined

interface TextValueConfig {
  text: string
  color?: NodeColor
  width?: number  // Width multiplier for pill shapes (default is 4)
}

interface MockValueConfig {
  type: ResultType
  values?: (string | TextValueConfig)[]  // For text values, can be string or object with color
  starRange?: { min: number; max: number }  // For star ratings
  booleanRatio?: number  // For boolean, ratio of true values (0-1)
}

interface ItemListWorkflowProps {
  allowedMediaTypes?: MediaNodeType[]
  allowedShapes?: NodeShape[]
  fixedShapeSequence?: NodeShape[]  // If provided, will cycle through these shapes in order
  resultTypes?: MockValueConfig[]  // If provided, will cycle through these types in order
}

interface ExtendedWorkflowStep extends WorkflowStep {
  mediaType?: MediaNodeType
  result?: NodeResult
  addedTimestamp: number
  sequence?: NodeSequence
  shape?: NodeShape
  resultValue?: string
  resultColor?: NodeColor
  pillWidth?: number  // Add width control to the step
}

// Debug multiplier to slow down all animations (set to 1 to restore original speed)
const DEBUG_SPEED_MULTIPLIER = 1  // Back to original speed

// Timing constants for animations
const TIMING = {
  ROW_ENTRANCE: 800,
  NODE_STAGGER: 50,
  INITIAL_DELAY: 200,
  PROCESSING: 1200,
  COMPLETION_BUFFER: 300,
  EXIT: 800,
  HEARTBEAT: 1200,
  ACCELERATION_DURATION: 30000,  // 30 seconds to reach max speed
  CYCLE_DURATION: 60000,         // 60 seconds total before reset
  MIN_SCALE: 1,
  MAX_SCALE: 4  // Maximum speed multiplier
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
const getTimingScale = (cycleStartTime: number) => {
  const elapsed = Date.now() - cycleStartTime
  const cycleElapsed = elapsed % TIMING.CYCLE_DURATION
  const accelerationElapsed = Math.min(cycleElapsed, TIMING.ACCELERATION_DURATION)
  
  return TIMING.MIN_SCALE + 
    (TIMING.MAX_SCALE - TIMING.MIN_SCALE) * 
    (accelerationElapsed / TIMING.ACCELERATION_DURATION)
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
  return steps.map((step, index) => {
    // Preserve media nodes exactly as they are
    if (step.mediaType) {
      return {
        ...step,
        status: "complete" // Ensure media nodes are always complete
      }
    }
    
    // Only add sequences to non-media nodes
    return {
      ...step,
      sequence: createNodeSequence(index, rowStartTime, false)
    }
  })
}

// Remove initialSteps constant as we'll start with an empty queue
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
  onCleanup: () => void
}

const WorkflowRow = React.forwardRef<SVGGElement, RowProps>(({ steps, rowY, yOffset, onCleanup }, ref) => {
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
        default:
          console.error('Invalid media type:', step.mediaType)
          return <AudioNode status="complete" /> // Fallback to audio if somehow invalid
      }
    }

    // Use sequence-based animation for non-media nodes
    if (step.sequence) {
      const now = Date.now()
      const elapsed = now - step.addedTimestamp
      const { startDelay, processingDuration } = step.sequence
      
      // Determine the current status based on elapsed time
      let status: "not-started" | "processing" | "complete" = "complete"
      if (elapsed < startDelay) {
        status = "not-started"
      } else if (elapsed < startDelay + processingDuration) {
        status = "processing"
      }

      // For boolean results (thumbs up/down)
      if (step.result !== undefined) {
        return (
          <WorkflowNode 
            status={status} 
            sequence={step.sequence}
            shape={step.shape || "circle"}
            icon={step.result === "thumbs-up" ? ThumbsUp : ThumbsDown}
          />
        )
      }
      
      // For text or star results
      if (step.resultValue) {
        const isStars = step.resultValue.startsWith("stars:")
        return (
          <WorkflowNode 
            status={status} 
            sequence={step.sequence} 
            shape={step.shape || "circle"} 
            text={step.resultValue}
            color={step.resultColor || (isStars ? "true" : undefined)}
            pillWidth={step.pillWidth}  // Pass through the pill width
          />
        )
      }

      // Default to a basic node with checkmark
      return (
        <WorkflowNode 
          status={status} 
          sequence={step.sequence}
          shape={step.shape || "circle"}
          icon={Check}
        />
      )
    }

    // For non-media nodes without sequence, default to basic complete node
    return (
      <WorkflowNode 
        status="complete"
        shape={step.shape || "circle"}
        icon={Check}
      />
    )
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
        ease: "linear",
        onComplete: () => {
          // If row has moved out of view, force a cleanup
          if (targetY <= 0.5 || targetY >= 4.5) {
            onCleanup()
          }
        }
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

const getRandomFromSequence = <T,>(sequence: T[], index: number): T => {
  return sequence[index % sequence.length]
}

const getRandomValue = (config: MockValueConfig): { result?: NodeResult; value?: string; color?: NodeColor; pillWidth?: number } => {
  switch (config.type) {
    case "boolean":
      const ratio = config.booleanRatio ?? 0.9  // Default to 90% true
      return {
        result: Math.random() < ratio ? "thumbs-up" : "thumbs-down"
      }
    case "text":
      if (!config.values || config.values.length === 0) {
        return { value: "N/A" }
      }
      const randomValue = config.values[Math.floor(Math.random() * config.values.length)]
      if (typeof randomValue === 'string') {
        return { value: randomValue }
      } else {
        return { 
          value: randomValue.text, 
          color: randomValue.color,
          pillWidth: randomValue.width
        }
      }
    case "stars":
      const min = config.starRange?.min ?? 1
      const max = config.starRange?.max ?? 5
      const stars = Math.floor(Math.random() * (max - min + 1)) + min
      return {
        value: `stars:${stars}/${max}`
      }
    case "check":
      return {} // No result or value needed, will use default checkmark
    default:
      return {}
  }
}

const ItemListWorkflow = React.forwardRef<SVGGElement, ItemListWorkflowProps>(({ 
  allowedMediaTypes = MEDIA_TYPES,
  allowedShapes = ["circle"],
  fixedShapeSequence,
  resultTypes = [{ type: "check" }]  // Default to check type
}, ref) => {
  const [steps, setSteps] = useState<ExtendedWorkflowStep[]>([])
  const [visibleRows, setVisibleRows] = useState(0)
  const [nextId, setNextId] = useState(1)
  const [cycleStartTime, setCycleStartTime] = useState(Date.now())
  const [isResetting, setIsResetting] = useState(false)

  const getRandomDelay = useCallback((min: number, max: number) => {
    return Math.random() * (max - min) + min
  }, [])

  const getRandomMediaType = (allowedTypes: MediaNodeType[] = MEDIA_TYPES) => {
    const index = Math.floor(Math.random() * allowedTypes.length)
    return allowedTypes[index]
  }

  const getRandomShape = (allowedShapes: NodeShape[] = ["circle"]) => {
    const index = Math.floor(Math.random() * allowedShapes.length)
    return allowedShapes[index]
  }

  // Helper to create sequences with scaled timing
  const createScaledSequences = useCallback((currentTime: number, steps: ExtendedWorkflowStep[]) => {
    const scale = getTimingScale(cycleStartTime)
    return steps.map((step, index) => {
      // Preserve media nodes exactly as they are
      if (step.mediaType) {
        return step
      }
      
      // Only add sequences to non-media nodes
      return {
        ...step,
        sequence: {
          // Higher base jitter with occasional outliers
          startDelay: Math.max(addJitter(TIMING.INITIAL_DELAY / scale, 1.2), 50), // 120% base jitter
          processingDuration: Math.max(addJitter(TIMING.PROCESSING / scale, 1.5), 300), // 150% base jitter
          completionDelay: Math.max(
            addJitter((TIMING.INITIAL_DELAY + TIMING.PROCESSING + TIMING.COMPLETION_BUFFER) / scale, 1.8),
            50
          ) + addJitter(index * TIMING.NODE_STAGGER / scale, 2.0) // 200% jitter on stagger
        }
      }
    })
  }, [cycleStartTime])

  // Reset everything when component mounts or when cycle completes
  const resetWorkflow = useCallback(() => {
    setSteps([])
    setVisibleRows(0)
    setNextId(1)
    setCycleStartTime(Date.now())
    setIsResetting(false)
  }, [])

  useEffect(() => {
    resetWorkflow()
  }, [resetWorkflow])

  // Initial row appearance and conveyor belt effect
  useEffect(() => {
    let timer: NodeJS.Timeout

    const scheduleNextHeartbeat = () => {
      const scale = getTimingScale(cycleStartTime)
      const interval = Math.max(Math.round(TIMING.HEARTBEAT / scale), 100)
      timer = setTimeout(heartbeat, interval)
    }

    const heartbeat = () => {
      const now = Date.now()
      const cycleElapsed = now - cycleStartTime

      // Check if we need to start resetting
      if (cycleElapsed >= TIMING.CYCLE_DURATION && !isResetting) {
        setIsResetting(true)
        // Let existing rows cycle off naturally
        return scheduleNextHeartbeat()
      }

      // If we're resetting and all rows are gone, start a new cycle
      if (isResetting && steps.length === 0) {
        resetWorkflow()
        return scheduleNextHeartbeat()
      }

      // Normal row creation logic
      const newSteps: ExtendedWorkflowStep[] = Array.from({ length: 5 }).map((_, i) => {
        const isFirstNode = i === 0
        const rowPosition = visibleRows + 1

        // Handle media node (first node)
        if (isFirstNode) {
          return {
            id: `${nextId}-${i + 1}`,
            label: `Item ${nextId}-${i + 1}`,
            status: "complete",
            position: `r${rowPosition}-${i + 1}`,
            mediaType: getRandomMediaType(allowedMediaTypes),
            addedTimestamp: now
          }
        }

        // Handle result nodes (non-first nodes)
        const nodeIndex = i - 1 // Index in the sequence (0-3 for nodes after media)
        
        // Get shape based on sequence or random
        const shape = fixedShapeSequence ? 
          getRandomFromSequence(fixedShapeSequence, nodeIndex) : 
          getRandomShape(allowedShapes)

        // Get result type and value based on sequence
        let result: NodeResult | undefined
        let resultValue: string | undefined
        let resultColor: NodeColor = undefined
        let pillWidth: number | undefined

        if (resultTypes && resultTypes.length > 0) {
          const config = getRandomFromSequence(resultTypes, nodeIndex)
          const value = getRandomValue(config)
          result = value.result
          resultValue = value.value
          resultColor = value.color
          pillWidth = value.pillWidth
        }

        return {
          id: `${nextId}-${i + 1}`,
          label: `Item ${nextId}-${i + 1}`,
          status: "processing",
          position: `r${rowPosition}-${i + 1}`,
          addedTimestamp: now,
          shape,
          result,
          resultValue,
          resultColor,
          pillWidth
        }
      })

      const sequencedNewSteps = createScaledSequences(now, newSteps)

      if (isResetting) {
        // During reset, only remove rows, don't add new ones
        setSteps(currentSteps => {
          const withoutFirstRow = currentSteps.slice(5)
          const updatedPositions = withoutFirstRow.map((step, index) => ({
            ...step,
            position: `r${Math.floor(index / 5) + 1}-${(index % 5) + 1}`
          }))
          return updatedPositions
        })
      } else if (visibleRows < 4) {
        // Initial phase: Just append the new row
        setSteps(currentSteps => [...currentSteps, ...sequencedNewSteps])
        setNextId(prev => prev + 1)
        setVisibleRows(prev => prev + 1)
      } else {
        // Ongoing phase: remove first row, shift others up, add new row
        setSteps(currentSteps => {
          const withoutFirstRow = currentSteps.slice(5)
          const updatedPositions = withoutFirstRow.map((step, index) => ({
            ...step,
            position: `r${Math.floor(index / 5) + 1}-${(index % 5) + 1}`
          }))
          return [...updatedPositions, ...sequencedNewSteps]
        })
        setNextId(prev => prev + 1)
      }

      scheduleNextHeartbeat()
    }

    scheduleNextHeartbeat()
    return () => clearTimeout(timer)
  }, [visibleRows, steps, nextId, cycleStartTime, isResetting, allowedMediaTypes, allowedShapes, fixedShapeSequence, resultTypes, resetWorkflow])

  const getRowSteps = useCallback((steps: ExtendedWorkflowStep[], rowIndex: number) => {
    return steps.slice(rowIndex * 5, (rowIndex + 1) * 5)
  }, [])

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
        default:
          console.error('Invalid media type:', step.mediaType)
          return <AudioNode status="complete" /> // Fallback to audio if somehow invalid
      }
    }

    // Use sequence-based animation for non-media nodes
    if (step.sequence) {
      const now = Date.now()
      const elapsed = now - step.addedTimestamp
      const { startDelay, processingDuration } = step.sequence
      
      // Determine the current status based on elapsed time
      let status: "not-started" | "processing" | "complete" = "complete"
      if (elapsed < startDelay) {
        status = "not-started"
      } else if (elapsed < startDelay + processingDuration) {
        status = "processing"
      }

      // For boolean results (thumbs up/down)
      if (step.result !== undefined) {
        return (
          <WorkflowNode 
            status={status} 
            sequence={step.sequence}
            shape={step.shape || "circle"}
            icon={step.result === "thumbs-up" ? ThumbsUp : ThumbsDown}
          />
        )
      }
      
      // For text or star results
      if (step.resultValue) {
        const isStars = step.resultValue.startsWith("stars:")
        return (
          <WorkflowNode 
            status={status} 
            sequence={step.sequence} 
            shape={step.shape || "circle"} 
            text={step.resultValue}
            color={step.resultColor || (isStars ? "true" : undefined)}
            pillWidth={step.pillWidth}  // Pass through the pill width
          />
        )
      }

      // Default to a basic node with checkmark
      return (
        <WorkflowNode 
          status={status} 
          sequence={step.sequence}
          shape={step.shape || "circle"}
          icon={Check}
        />
      )
    }

    // For non-media nodes without sequence, default to basic complete node
    return (
      <WorkflowNode 
        status="complete"
        shape={step.shape || "circle"}
        icon={Check}
      />
    )
  }, [])

  return (
    <ContainerBase viewBox="0 0 4.64 5">
      <g ref={ref}>
        <AnimatePresence mode="popLayout">
          {Array.from({ length: Math.min(4, visibleRows) }).map((_, index) => {
            const rowSteps = getRowSteps(steps, index)
            if (!rowSteps.length) return null
            
            const rowY = index + 1

            return (
              <WorkflowRow
                key={rowSteps[0].id}
                steps={rowSteps}
                rowY={rowY}
                yOffset={0}
                onCleanup={() => {}}
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