export type NodeStatus = "not-started" | "processing" | "complete"

export type NodeShape = "circle" | "square" | "triangle" | "hexagon"

export type ResultType = "checkmark" | "text" | "rating"

export interface NodeSequence {
  startDelay: number
  processingDuration: number
  completionDelay: number
}

export interface BaseNodeProps {
  status?: NodeStatus
  size?: number
  className?: string
  isMain?: boolean
  sequence?: NodeSequence
  isDemo?: boolean
}

export interface WorkflowStep {
  id: string
  label: string
  status: "not-started" | "processing" | "complete"
  position: string
}

export interface SequenceTiming {
  startDelay: number
  processingDuration: number
  completionDelay: number
}

export interface BaseLayoutProps {
  steps: WorkflowStep[]
  className?: string
  containerClassName?: string
}

export interface ConnectionProps {
  startX: number
  startY: number
  endX: number
  endY: number
  className?: string
  animated?: boolean
}

export interface WorkflowPositions {
  [key: string]: { x: number; y: number }
} 