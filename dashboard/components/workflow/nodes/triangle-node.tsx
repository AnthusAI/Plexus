"use client"

import { motion, AnimatePresence } from "framer-motion"
import { cn } from "@/lib/utils"
import { BaseNodeProps } from "../types"

export function TriangleNode({ sequence, status, isMain = false }: BaseNodeProps) {
  const size = isMain ? 0.8 : 0.6
  const width = size * 1.15470  // Makes triangle equilateral
  const iconScale = isMain ? 0.4 : 0.3

  // Helper function to create equilateral triangle path with optional vertical offset
  const trianglePath = (s: number, yOffset: number = 0) => {
    const w = s * 1.15470
    return `M0,${-s/2 + yOffset} L${w/2},${s/2 + yOffset} L${-w/2},${s/2 + yOffset} Z`
  }

  // If using status-based props
  if (status !== undefined) {
    return (
      <g>
        <path
          d={trianglePath(size)}
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
            d={trianglePath(size * 0.6, size * 0.05)}
            className="stroke-border fill-none"
            strokeWidth={0.02}
          />
        )}
        {status === "processing" && (
          <path
            d={trianglePath(size * 0.6, size * 0.05)}
            className="stroke-secondary fill-none"
            strokeWidth={0.1}
            strokeLinecap="round"
            transform="translate(0 0)"
          >
            <animateTransform
              attributeName="transform"
              type="scale"
              values="0.8;1.1;0.8"
              dur="1.5s"
              repeatCount="indefinite"
              additive="sum"
            />
          </path>
        )}
        {status === "complete" && (
          <path
            d={`M${-iconScale/1.8} ${isMain ? 0.15 : 0.12} l${iconScale/3} ${iconScale/3} l${iconScale/2} -${iconScale}`}
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
    console.warn('TriangleNode: Neither status nor sequence provided')
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
          d={trianglePath(size)}
          className="fill-card stroke-border"
          strokeWidth={0.02}
        />
        <path
          d={trianglePath(size * 0.6, size * 0.05)}
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
          d={trianglePath(size)}
          className="fill-card stroke-border"
          strokeWidth={0.02}
        />
        <path
          d={trianglePath(size * 0.6, size * 0.05)}
          className="stroke-secondary fill-none"
          strokeWidth={0.1}
          strokeLinecap="round"
          transform="translate(0 0)"
        >
          <animateTransform
            attributeName="transform"
            type="scale"
            values="0.8;1.1;0.8"
            dur="1.5s"
            repeatCount="indefinite"
            additive="sum"
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
          d={trianglePath(size)}
          className="fill-true stroke-none"
          strokeWidth={0.02}
        />
        <path
          d={`M${-iconScale/1.8} ${isMain ? 0.15 : 0.12} l${iconScale/3} ${iconScale/3} l${iconScale/2} -${iconScale}`}
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