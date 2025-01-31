"use client"

import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { BaseNodeProps } from "../types"
import { LucideIcon, Check, ThumbsDown, Star, Dot } from "lucide-react"
import { useEffect, useState } from "react"

const DEMO_DURATION = 3000 // 3 seconds per state

type Shape = "circle" | "square" | "triangle" | "hexagon" | "pill"
type NodeProps = BaseNodeProps & {
  shape: Shape
  icon?: LucideIcon
  text?: string
  color?: "true" | "false"
}

const CheckIcon = () => (
  <Check 
    className="stroke-background dark:stroke-foreground" 
    size={0.45}
    strokeWidth={4.5}
  />
)

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

export function WorkflowNode({ 
  sequence,
  status, 
  isMain = false,
  isDemo = false,
  shape,
  icon: Icon,
  text,
  color
}: NodeProps) {
  const radius = isMain ? 0.4 : 0.3
  const iconScale = 0.0016  // Reduced by factor of 10
  
  // Move hooks to the top level
  const [currentState, setCurrentState] = useState<"notStarted" | "processing" | "complete">("notStarted")

  useEffect(() => {
    // Only run effect if we're in demo mode or have a sequence
    if (!isDemo && !sequence) return;

    if (isDemo) {
      // Demo mode: cycle through states every DEMO_DURATION ms
      const cycleStates = () => {
        setCurrentState("notStarted")
        
        const processingTimer = setTimeout(() => {
          setCurrentState("processing")
        }, DEMO_DURATION)

        const completeTimer = setTimeout(() => {
          setCurrentState("complete")
        }, DEMO_DURATION * 2)

        // Reset after full cycle
        const resetTimer = setTimeout(() => {
          cycleStates()
        }, DEMO_DURATION * 3)

        return () => {
          clearTimeout(processingTimer)
          clearTimeout(completeTimer)
          clearTimeout(resetTimer)
        }
      }

      cycleStates() // Call immediately to start the cycle
      return () => {} // Cleanup will be handled by cycleStates
    } else if (sequence) {
      // Normal sequence mode
      const processingTimer = setTimeout(() => {
        setCurrentState("processing")
      }, sequence.startDelay)

      const completeTimer = setTimeout(() => {
        setCurrentState("complete")
      }, sequence.startDelay + sequence.processingDuration)

      return () => {
        clearTimeout(processingTimer)
        clearTimeout(completeTimer)
      }
    }
  }, [sequence, isDemo])
  
  // Calculate triangle offset if needed
  const triangleYOffset = shape === "triangle" ? 
    ((radius * 1.1) * 1.732) / 6 : // height/6 for triangles
    0  // no offset for other shapes

  // Shape-specific path generators
  const getShapePath = () => {
    switch (shape) {
      case "square":
        const size = radius * 2
        return `M${-radius},${-radius} h${size} v${size} h${-size} z`
      case "triangle":
        const height = (radius * 1.1) * 1.732 // 10% larger triangle
        const topY = -(2 * height/3)    // Top point is 2/3 above center
        const bottomY = height/3         // Bottom points are 1/3 below center
        return `M0,${topY + triangleYOffset} L${radius * 1.1},${bottomY + triangleYOffset} L${-radius * 1.1},${bottomY + triangleYOffset} z`
      case "hexagon":
        const points = []
        for (let i = 0; i < 6; i++) {
          const angle = (i * 60 - 30) * Math.PI / 180
          points.push(`${radius * Math.cos(angle)},${radius * Math.sin(angle)}`)
        }
        return `M${points.join(" L")} Z`
      case "pill":
        const pillWidth = radius * 4 // Make pill wider to fit 5 stars
        const pillHeight = radius * 1.2
        const rx = pillHeight / 2 // Rounded corners radius
        return `M${-pillWidth/2},${-pillHeight/2} h${pillWidth} a${rx},${rx} 0 0 1 0,${pillHeight} h${-pillWidth} a${rx},${rx} 0 0 1 0,${-pillHeight}`
      default: // circle doesn't need a path
        return ""
    }
  }

  // Shape-specific inner shape for not-started state
  const getNotStartedShape = () => {
    switch (shape) {
      case "square":
        return (
          <rect
            x={-radius * 0.6}
            y={-radius * 0.6}
            width={radius * 1.2}
            height={radius * 1.2}
            className="stroke-border fill-none"
            strokeWidth={0.05}
          />
        )
      case "triangle":
        // Calculate inner triangle coordinates directly
        const innerScale = 0.45  // Slightly smaller than before
        const innerRadius = radius * 1.1 * innerScale
        const innerHeight = innerRadius * 1.732
        // For an equilateral triangle centered at (0,0):
        // - Top point is 2/3 of height above center
        // - Bottom points are 1/3 of height below center
        const topY = -(2 * innerHeight/3)
        const bottomY = innerHeight/3
        return (
          <path
            d={`M0,${topY + triangleYOffset} L${innerRadius},${bottomY + triangleYOffset} L${-innerRadius},${bottomY + triangleYOffset} z`}
            className="stroke-border fill-none"
            strokeWidth={0.05}
          />
        )
      case "hexagon":
        const points = []
        for (let i = 0; i < 6; i++) {
          const angle = (i * 60 - 30) * Math.PI / 180
          points.push(`${radius * 0.6 * Math.cos(angle)},${radius * 0.6 * Math.sin(angle)}`)
        }
        return (
          <path
            d={`M${points.join(" L")} Z`}
            className="stroke-border fill-none"
            strokeWidth={0.05}
          />
        )
      case "pill":
        const pillWidth = radius * 4 * 0.6 // Scale down by 0.6
        const pillHeight = radius * 1.2 * 0.6
        const rx = pillHeight / 2
        return (
          <path
            d={`M${-pillWidth/2},${-pillHeight/2} h${pillWidth} a${rx},${rx} 0 0 1 0,${pillHeight} h${-pillWidth} a${rx},${rx} 0 0 1 0,${-pillHeight}`}
            className="stroke-border fill-none"
            strokeWidth={0.05}
          />
        )
      default: // circle
        return (
          <circle
            r={radius * 0.6}
            className="stroke-border fill-none"
            strokeWidth={0.05}
          />
        )
    }
  }

  // Shape-specific spinner generators
  const getProcessingSpinner = () => {
    switch (shape) {
      case "square":
        // Square: Step-wise rotation with pauses
        return (
          <motion.rect
            x={-radius * 0.6}
            y={-radius * 0.6}
            width={radius * 1.2}
            height={radius * 1.2}
            className="stroke-secondary fill-none"
            strokeWidth={0.1}
            strokeLinecap="round"
            initial={{ rotate: 0 }}
            animate={{
              rotate: [0, 90, 90, 180, 180, 270, 270, 360],
            }}
            transition={{
              duration: 2.4,
              times: [0, 0.2, 0.3, 0.45, 0.55, 0.7, 0.8, 1],
              repeat: Infinity,
              ease: "easeInOut",
              repeatDelay: 0.1
            }}
          />
        )
      case "pill":
        // Pill: Horizontal sliding animation with inset shape
        const pillWidth = radius * 4 * 0.6 // Scale down by 0.6
        const pillHeight = radius * 1.2 * 0.6
        const rx = pillHeight / 2
        return (
          <motion.g>
            <path
              d={`M${-pillWidth/2},${-pillHeight/2} h${pillWidth} a${rx},${rx} 0 0 1 0,${pillHeight} h${-pillWidth} a${rx},${rx} 0 0 1 0,${-pillHeight}`}
              className="stroke-secondary fill-none"
              strokeWidth={0.1}
              strokeLinecap="round"
            />
            <motion.circle
              r={pillHeight * 0.3}
              className="fill-secondary"
              initial={{ x: -pillWidth/2 + rx }}
              animate={{ x: pillWidth/2 - rx }}
              transition={{
                duration: 1.5,
                repeat: Infinity,
                repeatType: "reverse",
                ease: "easeInOut"
              }}
            />
          </motion.g>
        )
      case "triangle":
        // Calculate inner triangle coordinates for spinner
        const spinnerScale = 0.45  // Match the not-started state scale
        const spinnerRadius = radius * 1.1 * spinnerScale
        const spinnerHeight = spinnerRadius * 1.732
        // Same center point calculations
        const spinnerTopY = -(2 * spinnerHeight/3)
        const spinnerBottomY = spinnerHeight/3
        return (
          <motion.path
            d={`M0,${spinnerTopY + triangleYOffset} L${spinnerRadius},${spinnerBottomY + triangleYOffset} L${-spinnerRadius},${spinnerBottomY + triangleYOffset} z`}
            className="stroke-secondary fill-none"
            strokeWidth={0.1}
            strokeLinecap="round"
            initial={{ scale: 1 }}
            animate={{
              scale: [1, 1.15, 1],
            }}
            transition={{
              duration: 1.2,
              repeat: Infinity,
              ease: "easeInOut",
              times: [0, 0.5, 1]
            }}
          />
        )
      case "hexagon":
        // Hexagon: Counter-clockwise continuous rotation
        const points = []
        for (let i = 0; i < 6; i++) {
          const angle = (i * 60 - 30) * Math.PI / 180  // Added -30 degree offset to match outer hexagon
          points.push(`${radius * 0.6 * Math.cos(angle)},${radius * 0.6 * Math.sin(angle)}`)
        }
        return (
          <motion.path
            d={`M${points.join(" L")} Z`}
            className="stroke-secondary fill-none"
            strokeWidth={0.1}
            strokeLinecap="round"
            initial={{ rotate: 0 }}
            animate={{
              rotate: -360
            }}
            transition={{
              duration: 3,
              repeat: Infinity,
              ease: "linear"
            }}
          />
        )
      default: // circle: Clockwise continuous rotation with dashed stroke
        return (
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
        )
    }
  }

  // If using status-based props
  if (status !== undefined) {
    const starRating = text ? parseStarRating(text) : null
    const isStarNode = !!starRating

    return (
      <g>
        {shape === "circle" ? (
          <circle
            r={radius}
            className={cn(
              "transition-colors",
              status === "not-started" && "fill-card stroke-border",
              status === "processing" && "fill-card stroke-border",
              status === "complete" && (
                isStarNode ? "fill-primary stroke-none" :
                color === "false" ? "fill-false stroke-none" :
                Icon === ThumbsDown ? "fill-false stroke-none" : 
                "fill-true stroke-none"
              )
            )}
            strokeWidth={0.05}
          />
        ) : (
          <path
            d={getShapePath()}
            className={cn(
              "transition-colors",
              status === "not-started" && "fill-card stroke-border",
              status === "processing" && "fill-card stroke-border",
              status === "complete" && (
                isStarNode ? "fill-primary stroke-none" :
                color === "false" ? "fill-false stroke-none" :
                Icon === ThumbsDown ? "fill-false stroke-none" : 
                "fill-true stroke-none"
              )
            )}
            strokeWidth={0.05}
          />
        )}
        {status === "not-started" && getNotStartedShape()}
        {status === "processing" && getProcessingSpinner()}
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
        ) : text && !starRating ? (
          <text
            className="fill-background dark:fill-foreground text-[0.3px]"
            textAnchor="middle"
            dominantBaseline="middle"
            y={shape === "triangle" ? triangleYOffset : 0}
          >
            {text}
          </text>
        ) : Icon && (
          <motion.g 
            initial={{ 
              scale: 1, 
              opacity: 0,
              x: Icon === Check ? 
                (shape === "triangle" ? -0.25 : -0.225) : 
                -0.1875,
              y: Icon === Check ? 
                (shape === "triangle" ? -0.09 : -0.225) : 
                -0.1875
            }}
            animate={{ 
              scale: Icon === ThumbsDown ? 1 : [0, 1.4, 1],
              opacity: 1,
              x: Icon === Check ? 
                (shape === "triangle" ? -0.25 : -0.225) : 
                -0.1875,
              y: Icon === ThumbsDown ?
                [-0.1875, -0.1, -0.1875, -0.1, -0.1875, -0.1, -0.1875] :
                (Icon === Check ? 
                  (shape === "triangle" ? -0.09 : -0.225) : 
                  -0.1875)
            }}
            transition={{
              duration: Icon === ThumbsDown ? 1.2 : 0.4,
              times: Icon === ThumbsDown ? 
                [0, 0.167, 0.333, 0.5, 0.667, 0.833, 1] :
                [0, 0.6, 1],
              ease: "easeOut"
            }}
          >
            {Icon === Check ? (
              <CheckIcon />
            ) : (
              <Icon 
                className="stroke-background dark:stroke-foreground" 
                size={0.375}
                strokeWidth={2.5}
              />
            )}
          </motion.g>
        ))}
      </g>
    )
  }

  // Early return if no sequence or demo mode
  if (!sequence && !isDemo) {
    console.warn('WorkflowNode: Neither status nor sequence provided')
    return null
  }

  // Sequence-based or demo mode rendering
  return (
    <g>
      {/* Base Shape */}
      {shape === "circle" ? (
        <motion.circle
          r={radius}
          className={cn(
            currentState === "complete" ? "fill-true stroke-none" : "fill-card stroke-border"
          )}
          strokeWidth={0.05}
          initial={false}
          animate={currentState === "complete" ? {
            scale: [1, 1.3, 1],
            transition: {
              duration: 0.8,
              times: [0, 0.6, 1],
              ease: "easeOut"
            }
          } : {}}
        />
      ) : (
        <motion.path
          d={getShapePath()}
          className={cn(
            currentState === "complete" ? "fill-true stroke-none" : "fill-card stroke-border"
          )}
          strokeWidth={0.05}
          initial={false}
          animate={currentState === "complete" ? {
            scale: [1, 1.3, 1],
            transition: {
              duration: 0.8,
              times: [0, 0.6, 1],
              ease: "easeOut"
            }
          } : {}}
        />
      )}

      {/* Inner Shape (Not Started & Processing) */}
      {currentState !== "complete" && (
        <>
          {currentState === "notStarted" ? (
            getNotStartedShape()
          ) : (
            getProcessingSpinner()
          )}
        </>
      )}

      {/* Icon (Complete) */}
      {currentState === "complete" && Icon && (
        <motion.g 
          initial={{ 
            scale: 1, 
            opacity: 0,
            x: Icon === Check ? 
              (shape === "triangle" ? -0.25 : -0.225) : 
              -0.1875,
            y: Icon === Check ? 
              (shape === "triangle" ? -0.09 : -0.225) : 
              -0.1875
          }}
          animate={{ 
            scale: Icon === ThumbsDown ? 1 : [0, 1.4, 1],
            opacity: 1,
            x: Icon === Check ? 
              (shape === "triangle" ? -0.25 : -0.225) : 
              -0.1875,
            y: Icon === ThumbsDown ?
              [-0.1875, -0.1, -0.1875, -0.1, -0.1875, -0.1, -0.1875] :
              (Icon === Check ? 
                (shape === "triangle" ? -0.09 : -0.225) : 
                -0.1875)
          }}
          transition={{
            duration: Icon === ThumbsDown ? 1.2 : 0.4,
            times: Icon === ThumbsDown ? 
              [0, 0.167, 0.333, 0.5, 0.667, 0.833, 1] :
              [0, 0.6, 1],
            ease: "easeOut"
          }}
        >
          {Icon === Check ? (
            <CheckIcon />
          ) : (
            <Icon 
              className="stroke-background dark:stroke-foreground" 
              size={0.375}
              strokeWidth={2.5}
            />
          )}
        </motion.g>
      )}
    </g>
  )
} 