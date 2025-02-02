"use client"

import { motion, AnimatePresence } from "framer-motion"
import { cn } from "@/lib/utils"
import { BaseNodeProps } from "../types"

export function HexagonNode({ sequence, status, isMain = false }: BaseNodeProps) {
  // Slightly smaller than previous adjustment
  const size = isMain ? 0.9 : 0.7  // Reduced from 1.0/0.75
  const iconScale = isMain ? 0.4 : 0.3

  // Create hexagon path with equal width and height
  const hexagonPath = `M${size/2},0 L${size/4},${-size/2.5} L${-size/4},${-size/2.5} L${-size/2},0 L${-size/4},${size/2.5} L${size/4},${size/2.5} Z`
  const innerHexagonPath = `M${size/3},0 L${size/6},${-size/4} L${-size/6},${-size/4} L${-size/3},0 L${-size/6},${size/4} L${size/6},${size/4} Z`

  // If using status-based props
  if (status !== undefined) {
    return (
      <g>
        <path
          d={hexagonPath}
          className={cn(
            "transition-colors",
            status === "not-started" && "fill-card stroke-border",
            status === "processing" && "fill-card stroke-border",
            status === "complete" && "fill-true stroke-none"
          )}
          strokeWidth={0.02}
        />
        {status === "not-started" && (
          <path
            d={innerHexagonPath}
            className="stroke-border fill-none"
            strokeWidth={0.02}
          />
        )}
        {status === "processing" && (
          <path
            d={innerHexagonPath}
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
          </path>
        )}
        {status === "complete" && (
          <path
            d={`M${-iconScale/2.2} ${isMain ? 0.08 : 0.05} l${iconScale/3} ${iconScale/3} l${iconScale/2} -${iconScale}`}
            className="stroke-foreground"
            strokeWidth={isMain ? 0.12 : 0.08}
            strokeLinecap="round"
            strokeLinejoin="round"
            fill="none"
          />
        )}
      </g>
    )
  }

  // If using sequence-based props
  if (!sequence) {
    console.warn('HexagonNode: Neither status nor sequence provided')
    return null
  }

  return (
    <AnimatePresence mode="wait">
      {/* Not Started State */}
      <motion.g
        key="not-started"
        initial={{ opacity: 1 }}
        animate={{ opacity: 0 }}
        transition={{ 
          delay: sequence.startDelay / 1000,
          duration: 0.3 
        }}
      >
        <path
          d={hexagonPath}
          className="fill-card stroke-border"
          strokeWidth={0.02}
        />
        <path
          d={innerHexagonPath}
          className="stroke-border fill-none"
          strokeWidth={0.02}
        />
      </motion.g>

      {/* Processing State */}
      <motion.g
        key="processing"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ 
          delay: sequence.startDelay / 1000,
          duration: 0.3 
        }}
      >
        <path
          d={hexagonPath}
          className="fill-card stroke-border"
          strokeWidth={0.02}
        />
        <path
          d={innerHexagonPath}
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
        </path>
      </motion.g>

      {/* Completed State */}
      <motion.g
        key="complete"
        initial={{ opacity: 0, scale: 0 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ 
          delay: (sequence.startDelay + sequence.processingDuration) / 1000,
          duration: 0.3,
          ease: "easeInOut"
        }}
      >
        <path
          d={hexagonPath}
          className="fill-true stroke-none"
          strokeWidth={0.02}
        />
        <path
          d={`M${-iconScale/2.2} ${isMain ? 0.08 : 0.05} l${iconScale/3} ${iconScale/3} l${iconScale/2} -${iconScale}`}
          className="stroke-foreground"
          strokeWidth={isMain ? 0.12 : 0.08}
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
        />
      </motion.g>
    </AnimatePresence>
  )
} 