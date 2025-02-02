"use client"

import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { ConnectionProps } from "../types"

interface ExtendedConnectionProps extends ConnectionProps {
  type?: "straight" | "curve-down" | "curve-right"
}

export function ConnectionLine({
  startX,
  startY,
  endX,
  endY,
  type = "straight",
  className,
  animated = false
}: ConnectionProps & {
  type?: "straight" | "curve-right" | "curve-down"
}) {
  const pathData = (() => {
    switch (type) {
      case "curve-down":
        return `M${startX} ${startY} L${startX} ${(endY + startY) / 2} C${startX} ${endY - 0.3} ${startX + 0.1} ${endY} ${endX} ${endY}`
      case "curve-right":
        return `M${startX} ${startY} C${startX} ${startY + 0.3} ${startX - 0.1} ${endY} ${endX} ${endY}`
      default:
        return `M${startX} ${startY} L${endX} ${endY}`
    }
  })()
  
  const pathProps = {
    d: pathData,
    className: cn("stroke-card", className),
    strokeWidth: "0.1",
    fill: "none",
    strokeLinecap: "round" as const
  }

  return animated ? (
    <motion.path
      {...pathProps}
      initial={{ pathLength: 0 }}
      animate={{ pathLength: 1 }}
      transition={{ duration: 1, ease: "easeInOut" }}
    />
  ) : (
    <path {...pathProps} />
  )
} 