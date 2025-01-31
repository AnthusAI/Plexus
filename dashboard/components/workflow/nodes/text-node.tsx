"use client"

import { BaseNodeProps } from "../types"
import { FileText } from "lucide-react"
import { WorkflowNode } from "./workflow-node"

type TextNodeProps = BaseNodeProps & {
  shape?: "circle" | "square" | "triangle" | "hexagon" | "pill"
  text?: string
  color?: "true" | "false" | "primary"
}

export function TextNode({ 
  isMain = false,
  status,
  shape,
  text,
  color = "true"
}: TextNodeProps) {
  // If shape is specified, use the old text node behavior
  if (shape) {
    return (
      <WorkflowNode
        status={status}
        isMain={isMain}
        shape={shape}
        text={text}
        color={color === "primary" ? "true" : color}
      />
    )
  }

  // New default behavior: circle with text icon
  const radius = isMain ? 0.4 : 0.3

  return (
    <g>
      <circle
        r={radius}
        className="fill-card stroke-border"
        strokeWidth={0.02}
      />
      <g transform="scale(0.016) translate(-12, -12)">
        <FileText
          className="stroke-muted-foreground" 
          size={24}
          strokeWidth={1.5}
        />
      </g>
    </g>
  )
} 