"use client"

import { motion, AnimatePresence } from "framer-motion"
import { cn } from "@/lib/utils"
import { BaseNodeProps } from "../types"

export function SquareNode({ sequence, status, isMain = false }: BaseNodeProps) {
  const size = isMain ? 0.8 : 0.6
  const iconScale = isMain ? 0.4 : 0.3

  // If using status-based props
  if (status !== undefined) {
    return (
      <g>
        <rect
          x={-size/2} y={-size/2}
          width={size} height={size}
          className={cn(
            "transition-colors",
            status === "not-started" && "fill-card stroke-border",
            status === "processing" && "fill-card stroke-border",
            status === "complete" && "fill-true stroke-none"
          )}
          strokeWidth={0.02}
        />
        {status === "not-started" && (
          <rect
            x={-size*0.3} y={-size*0.3}
            width={size*0.6} height={size*0.6}
            className="stroke-border fill-none"
            strokeWidth={0.02}
          />
        )}
        {status === "processing" && (
          <rect
            x={-size*0.3} y={-size*0.3}
            width={size*0.6} height={size*0.6}
            className="stroke-secondary fill-none"
            strokeWidth={0.1}
            strokeLinecap="round"
          >
            {sequence && sequence.startDelay + sequence.processingDuration > Date.now() && (
              <animateTransform
                attributeName="transform"
                type="rotate"
                values="0;0;90;90;180;180;270;270;360"
                keyTimes="0;0.125;0.25;0.375;0.5;0.625;0.75;0.875;1"
                dur="4s"
                repeatCount="indefinite"
              />
            )}
          </rect>
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
    console.warn('SquareNode: Neither status nor sequence provided')
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
        <rect
          x={-size/2} y={-size/2}
          width={size} height={size}
          className="fill-card stroke-border"
          strokeWidth={0.02}
        />
        <rect
          x={-size*0.3} y={-size*0.3}
          width={size*0.6} height={size*0.6}
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
          duration: 0.3,
          exit: {
            delay: (sequence.processingDuration - 300) / 1000,
            duration: 0.3
          }
        }}
      >
        <rect
          x={-size/2} y={-size/2}
          width={size} height={size}
          className="fill-card stroke-border"
          strokeWidth={0.02}
        />
        <rect
          x={-size*0.3} y={-size*0.3}
          width={size*0.6} height={size*0.6}
          className="stroke-secondary fill-none"
          strokeWidth={0.1}
          strokeLinecap="round"
        >
          {sequence && sequence.startDelay + sequence.processingDuration > Date.now() && (
            <animateTransform
              attributeName="transform"
              type="rotate"
              values="0;0;90;90;180;180;270;270;360"
              keyTimes="0;0.125;0.25;0.375;0.5;0.625;0.75;0.875;1"
              dur="4s"
              repeatCount="indefinite"
            />
          )}
        </rect>
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
        <rect
          x={-size/2} y={-size/2}
          width={size} height={size}
          className="fill-true stroke-none"
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