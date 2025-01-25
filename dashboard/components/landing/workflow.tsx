"use client"

import { useState, useEffect, useCallback, useRef } from "react"
import { WorkflowNode } from "./workflow-node"

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
  const [size, setSize] = useState({ width: 0, height: 0 })
  const containerRef = useRef<HTMLDivElement>(null)

  const getRandomDelay = useCallback((min: number, max: number) => {
    return Math.random() * (max - min) + min
  }, [])

  const advanceWorkflow = useCallback(() => {
    setSteps((currentSteps) => {
      const newSteps = [...currentSteps]
      switch (sequence) {
        case 0:
          newSteps[1].status = "processing" // Row 1A starts
          newSteps[0].status = "processing" // Main starts
          break
        case 1:
          newSteps[3].status = "processing" // Row 2A starts
          break
        case 2:
          newSteps[2].status = "processing" // Row 1B starts
          break
        case 3:
          newSteps[4].status = "processing" // Row 2B starts
          break
        case 4:
          newSteps[1].status = "complete" // Row 1A completes
          break
        case 5:
          newSteps[3].status = "complete" // Row 2A completes
          break
        case 6:
          newSteps[2].status = "complete" // Row 1B completes
          break
        case 7:
          newSteps[4].status = "complete" // Row 2B completes
          break
        case 8:
          newSteps[0].status = "complete" // Main completes
          break
      }
      return newSteps
    })
    setSequence((prev) => prev + 1)
  }, [sequence])

  useEffect(() => {
    let timer: NodeJS.Timeout

    if (sequence < 9) {
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

  useEffect(() => {
    const updateSize = () => {
      if (containerRef.current) {
        setSize({
          width: containerRef.current.offsetWidth,
          height: containerRef.current.offsetHeight,
        })
      }
    }

    updateSize()

    const resizeObserver = new ResizeObserver(updateSize)
    if (containerRef.current) {
      resizeObserver.observe(containerRef.current)
    }

    return () => resizeObserver.disconnect()
  }, [])

  const getNodePosition = (position: WorkflowStep["position"]) => {
    switch (position) {
      case "main":
        return "absolute top-[10%] left-[25%] -translate-x-1/2 -translate-y-1/2"
      case "row1-a":
        return "absolute top-[45%] left-[50%] -translate-x-1/2 -translate-y-1/2"
      case "row1-b":
        return "absolute top-[45%] right-[10%] -translate-y-1/2"
      case "row2-a":
        return "absolute top-[90%] left-[50%] -translate-x-1/2 -translate-y-1/2"
      case "row2-b":
        return "absolute top-[90%] right-[10%] -translate-y-1/2"
    }
  }

  const baseSize = size.width
  const baseHeight = size.height
  const strokeWidth = baseSize * 0.045

  return (
    <div className="w-full" style={{ aspectRatio: '2/1' }}>
      <div
        ref={containerRef}
        className="relative w-full h-full"
        style={
          {
            "--base-size": `${baseSize}px`,
            "--stroke-width": `${strokeWidth}px`,
          } as React.CSSProperties
        }
      >
        <svg className="absolute inset-0 w-full h-full" style={{ pointerEvents: "none" }}>
          {/* Main to Row 1A */}
          <path
            d={`M${baseSize * 0.25} ${baseHeight * 0.1} 
                L ${baseSize * 0.25} ${baseHeight * 0.3} 
                C ${baseSize * 0.25} ${baseHeight * 0.4}, ${baseSize * 0.35} ${baseHeight * 0.45}, ${baseSize * 0.5} ${
              baseHeight * 0.45
            }`}
            className="stroke-border"
            strokeWidth={strokeWidth}
            fill="none"
            strokeLinecap="round"
          />
          {/* Main to Row 2A */}
          <path
            d={`M${baseSize * 0.25} ${baseHeight * 0.1} 
                L ${baseSize * 0.25} ${baseHeight * 0.7} 
                C ${baseSize * 0.25} ${baseHeight * 0.85}, ${baseSize * 0.35} ${baseHeight * 0.9}, ${baseSize * 0.5} ${
              baseHeight * 0.9
            }`}
            className="stroke-border"
            strokeWidth={strokeWidth}
            fill="none"
            strokeLinecap="round"
          />
          {/* Row 1A to Row 1B */}
          <path
            d={`M${baseSize * 0.55} ${baseHeight * 0.45} L ${baseSize * 0.85} ${baseHeight * 0.45}`}
            className="stroke-border"
            strokeWidth={strokeWidth}
            fill="none"
            strokeLinecap="round"
          />
          {/* Row 2A to Row 2B */}
          <path
            d={`M${baseSize * 0.55} ${baseHeight * 0.9} L ${baseSize * 0.85} ${baseHeight * 0.9}`}
            className="stroke-border"
            strokeWidth={strokeWidth}
            fill="none"
            strokeLinecap="round"
          />
        </svg>

        {steps.map((step) => (
          <div key={step.id} className={`${getNodePosition(step.position)} z-10`}>
            <WorkflowNode status={step.status} isMain={step.position === "main"} />
          </div>
        ))}
      </div>
    </div>
  )
}

