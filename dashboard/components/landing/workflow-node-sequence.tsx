"use client"

import { Check, Loader2, Circle } from "lucide-react"
import { cn } from "@/lib/utils"
import { motion, AnimatePresence } from "framer-motion"

interface WorkflowNodeSequenceProps {
  sequence?: {
    startDelay?: number
    processingDuration?: number
    completionDelay?: number
  }
  isMain?: boolean
  className?: string
}

const defaultSequence = {
  startDelay: 0,
  processingDuration: 2000,
  completionDelay: 2500
}

export function WorkflowNodeSequence({ 
  sequence: userSequence,
  isMain = false, 
  className 
}: WorkflowNodeSequenceProps) {
  const sequence = {
    ...defaultSequence,
    ...userSequence
  }

  const radius = isMain ? 0.4 : 0.3
  const iconScale = isMain ? 0.4 : 0.3

  return (
    <div className={cn(
      "relative flex items-center justify-center",
      className
    )}>
      <svg 
        viewBox="-0.5 -0.5 1 1" 
        className={cn(
          "w-8 h-8",
          isMain ? "scale-[400%]" : "scale-[300%]"
        )}
      >
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
            <circle
              r={radius}
              className="fill-card stroke-border"
              strokeWidth={0.02}
            />
            <circle
              r={radius * 0.6}
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
            <circle
              r={radius}
              className="fill-card stroke-border"
              strokeWidth={0.02}
            />
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
            <circle
              r={radius}
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
      </svg>
    </div>
  )
} 
