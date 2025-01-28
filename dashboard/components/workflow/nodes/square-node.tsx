"use client"

import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { BaseNodeProps } from "../types"

export function SquareNode({ 
  status, 
  isMain = false 
}: BaseNodeProps) {
  const size = isMain ? 0.8 : 0.6
  const iconScale = isMain ? 0.5 : 0.35

  return (
    <g>
      <rect
        x={-size/2}
        y={-size/2}
        width={size}
        height={size}
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
          x={-size * 0.3}
          y={-size * 0.3}
          width={size * 0.6}
          height={size * 0.6}
          className="stroke-border fill-none"
          strokeWidth={0.02}
        />
      )}
      {status === "processing" && (
        <>
          <rect
            x={-size * 0.3}
            y={-size * 0.3}
            width={size * 0.6}
            height={size * 0.6}
            className="stroke-border fill-none"
            strokeWidth={0.02}
          />
          <g>
            <rect
              x={-size * 0.3}
              y={-size * 0.3}
              width={size * 0.6}
              height={size * 0.6}
              className="stroke-secondary fill-none"
              strokeWidth={0.1}
              strokeLinecap="round"
            >
              <animateTransform
                attributeName="transform"
                type="rotate"
                values="0;0;90;90;180;180;270;270;360"
                keyTimes="0;0.125;0.25;0.375;0.5;0.625;0.75;0.875;1"
                dur="4s"
                repeatCount="indefinite"
              />
            </rect>
          </g>
        </>
      )}
      {status === "complete" && (
        <path
          d={`M${-iconScale/2} ${isMain ? 0.08 : 0.05} l${iconScale/3} ${iconScale/3} l${iconScale/2} -${iconScale}`}
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