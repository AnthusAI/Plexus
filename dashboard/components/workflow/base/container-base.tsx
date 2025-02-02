"use client"

import { ReactNode } from "react"
import { cn } from "@/lib/utils"

interface ContainerBaseProps {
  children: ReactNode
  className?: string
  containerClassName?: string
  viewBox?: string
  preserveAspectRatio?: string
}

export function ContainerBase({
  children,
  className,
  containerClassName,
  viewBox = "0 0 4 4",
  preserveAspectRatio = "xMidYMid meet"
}: ContainerBaseProps) {
  return (
    <div className={cn("w-full h-full", className)}>
      <svg
        className="w-full h-full"
        viewBox={viewBox}
        preserveAspectRatio={preserveAspectRatio}
      >
        {children}
      </svg>
    </div>
  )
} 