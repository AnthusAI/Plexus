"use client"

import { Check } from "lucide-react"
import { WorkflowNode } from "../workflow/nodes"
import { NodeSequence } from "../workflow/types"
import { useState, useEffect } from "react"

interface WorkflowNodeSequenceProps {
  sequence?: NodeSequence
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

  const [currentStatus, setCurrentStatus] = useState<"not-started" | "processing" | "complete">("not-started")

  useEffect(() => {
    // Start in not-started state
    setCurrentStatus("not-started")

    // Transition to processing after startDelay
    const processingTimer = setTimeout(() => {
      setCurrentStatus("processing")
    }, sequence.startDelay)

    // Transition to complete after processingDuration
    const completeTimer = setTimeout(() => {
      setCurrentStatus("complete")
    }, sequence.startDelay + sequence.processingDuration)

    return () => {
      clearTimeout(processingTimer)
      clearTimeout(completeTimer)
    }
  }, [sequence])

  return (
    <WorkflowNode
      shape="circle"
      icon={Check}
      sequence={sequence}
      status={currentStatus}
      isMain={isMain}
    />
  )
} 
