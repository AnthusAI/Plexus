"use client"

import { ReactNode } from "react"
import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { BaseNodeProps } from "../types"

interface NodeBaseProps extends BaseNodeProps {
  children?: ReactNode
}

export function BaseNode({ 
  status, 
  size = 1, 
  className,
  isMain = false,
  children
}: NodeBaseProps) {
  const baseSize = isMain ? 0.8 : 0.6
  const scale = baseSize * size

  return (
    <g className={cn("transform -translate-x-1/2 -translate-y-1/2", className)}>
      <motion.circle
        r={scale / 2}
        className={cn(
          "transition-colors duration-200",
          status === "not-started" && 
            "fill-card stroke-border",
          status === "processing" && 
            "fill-card stroke-border",
          status === "complete" && 
            "fill-true stroke-none"
        )}
        strokeWidth={0.02}
        initial={{ scale: 0.8 }}
        animate={{ 
          scale: status === "processing" ? [0.9, 1.1, 0.9] : 1 
        }}
        transition={
          status === "processing" 
            ? { repeat: Infinity, duration: 2 }
            : { duration: 0.3 }
        }
      />
      <g transform={`scale(${scale})`}>
        {children}
      </g>
    </g>
  )
} 