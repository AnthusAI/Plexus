export type NodeStatus = "not-started" | "processing" | "complete"

export type NodeShape = "circle" | "square" | "triangle" | "hexagon"

export type ResultType = "checkmark" | "text" | "rating"

export interface BaseNodeProps {
  status: NodeStatus
  size?: number
  className?: string
  isMain?: boolean
}

export interface WorkflowStep {
  id: string
  label: string
  status: NodeStatus
  position: string
  shape?: NodeShape
  resultType?: ResultType
  resultValue?: string | number
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