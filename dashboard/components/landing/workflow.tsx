"use client"

import { useState, useEffect, useCallback, useRef } from "react"
import { WorkflowNode } from "./workflow-node"
import { cn } from "@/lib/utils"

type NodeStatus = "not-started" | "processing" | "complete"

interface WorkflowStep {
  id: string
  label: string
  status: NodeStatus
  position: "main" | "row1-a" | "row1-b" | "row2-a" | "row2-b"
}

const initialSteps: WorkflowStep[] = [
  { id: "1", label: "Main Process", status: "not-started", position: "main" },
  { id: "2", label: "Row 1A", status: "not-started", position: "row1-a" },
  { id: "3", label: "Row 1B", status: "not-started", position: "row1-b" },
  { id: "4", label: "Row 2A", status: "not-started", position: "row2-a" },
  { id: "5", label: "Row 2B", status: "not-started", position: "row2-b" },
]

export default function Workflow() {
  const [steps, setSteps] = useState<WorkflowStep[]>(initialSteps)
  const [sequence, setSequence] = useState(0)
  const containerRef = useRef<HTMLDivElement>(null)

  const getRandomDelay = useCallback((min: number, max: number) => {
    return Math.random() * (max - min) + min
  }, [])

  const advanceWorkflow = useCallback(() => {
    setSteps((currentSteps) => {
      const newSteps = [...currentSteps]
      switch (sequence) {
        case 0:
          newSteps[0].status = "processing" // Main starts
          break
        case 1:
          newSteps[1].status = "processing" // Row 1A starts
          break
        case 2:
          newSteps[3].status = "processing" // Row 2A starts
          break
        case 3:
          newSteps[2].status = "processing" // Row 1B starts
          break
        case 4:
          newSteps[4].status = "processing" // Row 2B starts
          break
        case 5:
          newSteps[1].status = "complete" // Row 1A completes
          break
        case 6:
          newSteps[3].status = "complete" // Row 2A completes
          break
        case 7:
          newSteps[2].status = "complete" // Row 1B completes
          break
        case 8:
          newSteps[4].status = "complete" // Row 2B completes
          break
        case 9:
          newSteps[0].status = "complete" // Main completes
          break
      }
      return newSteps
    })
    setSequence((prev) => prev + 1)
  }, [sequence])

  useEffect(() => {
    let timer: NodeJS.Timeout

    if (sequence < 10) {
      const delay = getRandomDelay(1000, 2500)
      timer = setTimeout(advanceWorkflow, delay)
    } else {
      const resetDelay = getRandomDelay(3000, 6000)
      timer = setTimeout(() => {
        setSteps((currentSteps) =>
          currentSteps.map((step) => ({
            ...step,
            status: "not-started",
          })),
        )
        setSequence(0)
      }, resetDelay)
    }

    return () => clearTimeout(timer)
  }, [sequence, advanceWorkflow, getRandomDelay])

  const getNodePosition = (position: WorkflowStep["position"]) => {
    switch (position) {
      case "main":
        return "absolute top-[25%] left-[25%] -translate-x-1/2 -translate-y-1/2"
      case "row1-a":
        return "absolute top-[50%] left-[50%] -translate-x-1/2 -translate-y-1/2"
      case "row1-b":
        return "absolute top-[50%] left-[75%] -translate-x-1/2 -translate-y-1/2"
      case "row2-a":
        return "absolute top-[75%] left-[50%] -translate-x-1/2 -translate-y-1/2"
      case "row2-b":
        return "absolute top-[75%] left-[75%] -translate-x-1/2 -translate-y-1/2"
    }
  }

  return (
    <div className="w-full" style={{ aspectRatio: '1/1' }}>
      <div
        ref={containerRef}
        className="relative w-full h-full p-8"
      >
        <svg 
          className="absolute inset-0 w-full h-full" 
          style={{ pointerEvents: "none" }}
          viewBox="0 0 4 4"
          preserveAspectRatio="xMidYMid meet"
        >
          {/* Connection Lines */}
          {/* Main to Row 1A */}
          <path
            d="M1 1 C1 1.3 0.9 2 2 2"
            className="stroke-muted-foreground"
            strokeWidth="0.15"
            fill="none"
            strokeLinecap="round"
          />
          {/* Main to Row 2A */}
          <path
            d="M1 1 L1 2.5 C1 2.7 0.9 3 2 3"
            className="stroke-muted-foreground"
            strokeWidth="0.15"
            fill="none"
            strokeLinecap="round"
          />
          {/* Row 1A to Row 1B */}
          <path
            d="M2 2 L3 2"
            className="stroke-muted-foreground"
            strokeWidth="0.15"
            fill="none"
            strokeLinecap="round"
          />
          {/* Row 2A to Row 2B */}
          <path
            d="M2 3 L3 3"
            className="stroke-muted-foreground"
            strokeWidth="0.15"
            fill="none"
            strokeLinecap="round"
          />

          {/* Nodes */}
          {steps.map((step) => {
            const position = (() => {
              switch (step.position) {
                case "main": return { x: 1, y: 1 }
                case "row1-a": return { x: 2, y: 2 }
                case "row1-b": return { x: 3, y: 2 }
                case "row2-a": return { x: 2, y: 3 }
                case "row2-b": return { x: 3, y: 3 }
              }
            })()
            const radius = step.position === "main" ? 0.6 : 0.4
            const iconScale = step.position === "main" ? 0.75 : 0.5

            return (
              <g key={step.id}>
                <circle
                  cx={position.x}
                  cy={position.y}
                  r={radius}
                  className={cn(
                    "transition-colors",
                    step.status === "not-started" && "fill-card stroke-border",
                    step.status === "processing" && "fill-card stroke-border",
                    step.status === "complete" && "fill-true stroke-none"
                  )}
                  strokeWidth={0.03}
                />
                {step.status === "not-started" && (
                  <circle
                    cx={position.x}
                    cy={position.y}
                    r={radius * 0.6}
                    className="stroke-border fill-none"
                    strokeWidth={0.03}
                  />
                )}
                {step.status === "processing" && (
                  <circle
                    cx={position.x}
                    cy={position.y}
                    r={radius * 0.6}
                    className="stroke-secondary fill-none"
                    strokeWidth={0.15}
                    strokeLinecap="round"
                    strokeDasharray={`${radius * 2} ${radius * 2}`}
                  >
                    <animateTransform
                      attributeName="transform"
                      type="rotate"
                      from={`0 ${position.x} ${position.y}`}
                      to={`360 ${position.x} ${position.y}`}
                      dur="1s"
                      repeatCount="indefinite"
                    />
                  </circle>
                )}
                {step.status === "complete" && (
                  <path
                    d={`M${position.x - iconScale/2} ${position.y + (step.position === "main" ? 0.12 : 0.075)} l${iconScale/3} ${iconScale/3} l${iconScale/2} -${iconScale}`}
                    className="stroke-background"
                    strokeWidth={step.position === "main" ? 0.225 : 0.15}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    fill="none"
                  />
                )}
              </g>
            )
          })}
        </svg>
      </div>
    </div>
  )
}

