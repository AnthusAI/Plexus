"use client"

import { cn } from "@/lib/utils"
import { BaseNodeProps } from "../types"
import { Star, Dot } from "lucide-react"
import { motion } from "framer-motion"
import { WorkflowNode } from "./workflow-node"

type TextNodeProps = BaseNodeProps & {
  shape?: "circle" | "square" | "triangle" | "hexagon" | "pill"
  text?: string
  color?: "true" | "false" | "primary"
}

// Add helper function to parse star ratings
const parseStarRating = (text: string): { filled: number; total: number } | null => {
  const match = text?.match(/^stars:(\d+)\/(\d+)$/)
  if (!match) return null
  return {
    filled: parseInt(match[1], 10),
    total: parseInt(match[2], 10)
  }
}

// Add StarIcon component for consistent styling
const StarIcon = ({ filled }: { filled: boolean }) => {
  const Icon = filled ? Star : Dot
  return (
    <g transform="translate(-0.125, -0.125)">
      <Icon 
        className="stroke-background dark:stroke-foreground" 
        size={0.25}
        strokeWidth={2.5}
      />
    </g>
  )
}

export function TextNode({ 
  isMain = false,
  status,
  shape = "circle",
  text,
  color = "true"
}: TextNodeProps) {
  // Use the WorkflowNode for pill shape since it has proper animations
  if (shape === "pill") {
    return (
      <WorkflowNode
        status={status}
        isMain={isMain}
        shape="pill"
        text={text}
        color={color === "primary" ? "true" : color}
      />
    )
  }

  const radius = isMain ? 0.4 : 0.3
  const starRating = text ? parseStarRating(text) : null

  // Helper to get the shape path
  const getShapePath = () => {
    switch (shape) {
      case "square":
        return `M${-radius},${-radius} h${radius * 2} v${radius * 2} h${-radius * 2} z`
      case "triangle": {
        const height = radius * 1.732 // height of equilateral triangle
        return `M0,${-height/2} L${radius},${height/2} L${-radius},${height/2} z`
      }
      case "hexagon": {
        const points = []
        for (let i = 0; i < 6; i++) {
          const angle = (i * 60 - 30) * Math.PI / 180
          points.push(`${radius * Math.cos(angle)},${radius * Math.sin(angle)}`)
        }
        return `M${points.join(" L")} Z`
      }
      default: // circle
        return `M${-radius},0 a${radius},${radius} 0 1,0 ${radius * 2},0 a${radius},${radius} 0 1,0 ${-radius * 2},0`
    }
  }

  return (
    <g>
      {status === "processing" ? (
        <motion.path
          d={getShapePath()}
          className="fill-card stroke-border"
          strokeWidth={0.05}
          animate={{
            rotate: [0, 180, 360],
            scale: [1, 1.1, 1]
          }}
          transition={{
            duration: 2,
            repeat: Infinity,
            ease: "linear"
          }}
        />
      ) : (
        <path
          d={getShapePath()}
          className={cn(
            "transition-colors",
            status === "not-started" && "fill-card stroke-border",
            status === "complete" && (
              color === "primary" ? "fill-primary stroke-none" :
              color === "false" ? "fill-false stroke-none" :
              "fill-true stroke-none"
            )
          )}
          strokeWidth={0.05}
        />
      )}
      {status === "complete" && (starRating ? (
        <motion.g>
          {Array.from({ length: starRating.total }).map((_, i) => {
            // For 3 dots, we want positions like: -0.3, 0, 0.3
            const spacing = 0.3
            const x = spacing * (i - ((starRating.total - 1) / 2))
            
            return (
              <g key={i} transform={`translate(${x}, 0)`}>
                <StarIcon filled={i < starRating.filled} />
              </g>
            )
          })}
        </motion.g>
      ) : text && !starRating && (
        <text
          className="fill-background dark:fill-foreground text-[0.3px]"
          textAnchor="middle"
          dominantBaseline="middle"
        >
          {text}
        </text>
      ))}
    </g>
  )
} 