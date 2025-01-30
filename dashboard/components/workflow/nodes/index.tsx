import React from 'react'
import { Check, Circle, Hexagon, Square, ThumbsDown, ThumbsUp, Triangle } from "lucide-react"
import { WorkflowNode } from "./workflow-node"
import { BaseNodeProps } from "../types"
import { LucideIcon } from "lucide-react"

export function CircleNode(props: BaseNodeProps & { icon?: LucideIcon }) {
  return <WorkflowNode {...props} shape="circle" icon={props.icon || Check} />
}

export function SquareNode(props: BaseNodeProps & { icon?: LucideIcon }) {
  return <WorkflowNode {...props} shape="square" icon={props.icon || Check} />
}

export function TriangleNode(props: BaseNodeProps & { icon?: LucideIcon }) {
  return <WorkflowNode {...props} shape="triangle" icon={props.icon || Check} />
}

export function HexagonNode(props: BaseNodeProps & { icon?: LucideIcon }) {
  return <WorkflowNode {...props} shape="hexagon" icon={props.icon || Check} />
}

export function ThumbsUpNode(props: BaseNodeProps) {
  return <WorkflowNode {...props} shape="circle" icon={ThumbsUp} />
}

export function ThumbsDownNode(props: BaseNodeProps) {
  return <WorkflowNode {...props} shape="circle" icon={ThumbsDown} />
}

// Export the base component as well in case it's needed
export { WorkflowNode } 