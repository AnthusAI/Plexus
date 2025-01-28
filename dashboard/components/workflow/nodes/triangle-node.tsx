"use client"

import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { BaseNodeProps } from "../types"

export function TriangleNode({ 
  status, 
  isMain = false 
}: BaseNodeProps) {
  // Make triangle about 30% larger than circle/square
  const baseSize = isMain ? 0.8 : 0.6
  const size = baseSize * 1.3
  // Make checkmark smaller to fit better in triangle
  const iconScale = (isMain ? 0.5 : 0.35) * 0.8

  // Create equilateral triangle path
  const height = size * Math.sin(Math.PI / 3)
  const points = `${-size/2},${height/2} 0,${-height/2} ${size/2},${height/2}`

  // Create smaller triangle for processing animation
  const animSize = size * 0.6
  const animHeight = animSize * Math.sin(Math.PI / 3)
  // Center the inner triangle by using 0 as the vertical center
  const animPoints = `${-animSize/2},${animHeight/2} 0,${-animHeight/2} ${animSize/2},${animHeight/2}`

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
          points={animPoints}
          className="stroke-border fill-none"
          strokeWidth={0.02}
          transform="translate(0, 0.05)"
        />
      )}
      {status === "processing" && (
        <g transform="translate(0, 0.05)">
          <polygon
            points={animPoints}
            className="stroke-secondary fill-none"
            strokeWidth={0.1}
            strokeLinecap="round"
          >
            <animateTransform
              attributeName="transform"
              type="scale"
              values="0.8;1.1;0.8"
              dur="1.5s"
              repeatCount="indefinite"
              additive="sum"
            />
          </polygon>
        </g>
      )}
      {status === "complete" && (
        <path
          d={`M${-iconScale/2 - 0.02} ${isMain ? 0.15 : 0.12} l${iconScale/3} ${iconScale/3} l${iconScale/2} -${iconScale}`}
          className="stroke-background"
          strokeWidth={isMain ? 0.15 : 0.1}
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
        />
      )}
    </g>
  )
} 