"use client"

import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { BaseNodeProps } from "../types"

export function HexagonNode({ 
  status, 
  isMain = false 
}: BaseNodeProps) {
  // Make hexagon about 15% larger than circle/square
  const baseSize = isMain ? 0.8 : 0.6
  const size = baseSize * 1.15
  const iconScale = isMain ? 0.5 : 0.35

  // Create regular hexagon points for outer shape
  const points = Array.from({ length: 6 }, (_, i) => {
    const angle = (i * Math.PI) / 3
    const x = (size/2) * Math.cos(angle)
    const y = (size/2) * Math.sin(angle)
    return `${x},${y}`
  }).join(" ")

  // Create smaller hexagon points for spinner (55% of outer size)
  const spinnerSize = size * 0.55
  const spinnerPoints = Array.from({ length: 6 }, (_, i) => {
    const angle = (i * Math.PI) / 3
    const x = (spinnerSize/2) * Math.cos(angle)
    const y = (spinnerSize/2) * Math.sin(angle)
    return `${x},${y}`
  }).join(" ")

  return (
    <g>
      <polygon
        points={points}
        className={cn(
          "transition-colors",
          status === "not-started" && "fill-card stroke-border",
          status === "processing" && "fill-card stroke-border",
          status === "complete" && "fill-true stroke-none"
        )}
        strokeWidth={0.02}
      />
      {status === "not-started" && (
        <polygon
          points={spinnerPoints}
          className="stroke-border fill-none"
          strokeWidth={0.02}
        />
      )}
      {status === "processing" && (
        <polygon
          points={spinnerPoints}
          className="stroke-secondary fill-none"
          strokeWidth={0.1}
          strokeLinecap="round"
        >
          <animateTransform
            attributeName="transform"
            type="rotate"
            from="360 0 0"
            to="0 0 0"
            dur="2s"
            repeatCount="indefinite"
          />
        </polygon>
      )}
      {status === "complete" && (
        <path
          d={`M${-iconScale/2} ${isMain ? 0.08 : 0.05} l${iconScale/3} ${iconScale/3} l${iconScale/2} -${iconScale}`}
          className="stroke-foreground"
          strokeWidth={isMain ? 0.15 : 0.1}
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
        />
      )}
    </g>
  )
} 