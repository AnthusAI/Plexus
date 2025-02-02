"use client"

import { Check, Loader2, Circle } from "lucide-react"
import { cn } from "@/lib/utils"
import { motion } from "framer-motion"

export type NodeStatus = "not-started" | "processing" | "complete"

interface WorkflowNodeProps {
  status: NodeStatus
  isMain?: boolean
  className?: string
}

export function WorkflowNode({ status, isMain = false, className }: WorkflowNodeProps) {
  return (
    <div className={cn("relative flex items-center justify-center", className)}>
      <div
        className={cn(
          "rounded-full flex items-center justify-center transition-colors",
          isMain
            ? "w-[0.8rem] h-[0.8rem] scale-[400%]"
            : "w-[0.6rem] h-[0.6rem] scale-[400%]",
          status === "not-started" && "border-2 border-muted bg-background dark:bg-card",
          status === "processing" && "bg-background dark:bg-card border-2 border-muted",
          status === "complete" && "bg-true text-background",
        )}
      >
        {status === "not-started" && (
          <Circle className="w-[60%] h-[60%] text-border" />
        )}
        {status === "processing" && (
          <Loader2
            className="w-[60%] h-[60%] text-secondary animate-spin"
            strokeWidth={2}
          />
        )}
        {status === "complete" && (
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ duration: 0.3, ease: "easeInOut" }}
            className="w-[60%] h-[60%]"
          >
            <Check className="w-full h-full text-white" strokeWidth={2} />
          </motion.div>
        )}
      </div>
    </div>
  )
}

