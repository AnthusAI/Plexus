"use client"

import { WorkflowNode } from "./workflow-node"
import { BaseNodeProps } from "../types"

type TextNodeProps = BaseNodeProps & {
  text?: string
  shape?: "circle" | "square" | "pill"
  color?: "true" | "false"
}

export function TextNode({ 
  text = "",
  shape = "circle",
  color = "true",
  ...props 
}: TextNodeProps) {
  return (
    <WorkflowNode
      {...props}
      shape={shape}
      text={text}
      color={color}
    />
  )
} 