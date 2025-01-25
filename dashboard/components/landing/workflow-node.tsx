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
            ? "w-[calc(var(--base-size)*0.2)] h-[calc(var(--base-size)*0.2)]"
            : "w-[calc(var(--base-size)*0.16)] h-[calc(var(--base-size)*0.16)]",
          status === "not-started" && "border-2 border-border bg-background",
          status === "processing" && "bg-card-foreground border-2 border-border",
          status === "complete" && "bg-true text-background",
        )}
      >
        {status === "not-started" && (
          <Circle className={cn(isMain ? "w-[70%] h-[70%]" : "w-[60%] h-[60%]", "text-border")} />
        )}
        {status === "processing" && (
          <Loader2
            className={cn(isMain ? "w-[70%] h-[70%]" : "w-[60%] h-[60%]", "text-secondary animate-spin")}
            strokeWidth={4}
          />
        )}
        {status === "complete" && (
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ duration: 0.3, ease: "easeInOut" }}
            className={cn(isMain ? "w-[70%] h-[70%]" : "w-[60%] h-[60%]")}
          >
            <Check className="w-full h-full text-white" strokeWidth={5} />
          </motion.div>
        )}
      </div>
    </div>
  )
}

