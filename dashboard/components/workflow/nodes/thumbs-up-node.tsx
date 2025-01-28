"use client"

import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { BaseNodeProps } from "../types"
import { ThumbsUp } from "lucide-react"

export function ThumbsUpNode({ 
  status, 
  isMain = false 
}: BaseNodeProps) {
  const radius = isMain ? 0.4 : 0.3
  const iconScale = isMain ? 0.5 : 0.35

  return (
    <g>
      <circle
        r={radius}
        className={cn(
          "transition-colors",
          status === "not-started" && "fill-card stroke-border",
          status === "processing" && "fill-card stroke-border",
          status === "complete" && "fill-true stroke-none"
        )}
        strokeWidth={0.02}
      />
      {status === "not-started" && (
        <circle
          r={radius * 0.6}
          className="stroke-border fill-none"
          strokeWidth={0.02}
        />
      )}
      {status === "processing" && (
        <circle
          r={radius * 0.6}
          className="stroke-secondary fill-none"
          strokeWidth={0.1}
          strokeLinecap="round"
          strokeDasharray={`${radius * 2} ${radius * 2}`}
        >
          <animateTransform
            attributeName="transform"
            type="rotate"
            from="0 0 0"
            to="360 0 0"
            dur="1s"
            repeatCount="indefinite"
          />
        </circle>
      )}
      {status === "complete" && (
        <g transform="scale(0.016) translate(-12, -12)">
          <ThumbsUp 
            className="stroke-background" 
            size={24}
            strokeWidth={2.5}
          />
        </g>
      )}
    </g>
  )
} 