"use client"

import { cn } from "@/lib/utils"
import { BaseNodeProps } from "../types"
import { Image } from "lucide-react"

export function ImageNode({ 
  isMain = false 
}: BaseNodeProps) {
  const radius = isMain ? 0.4 : 0.3

  return (
    <g>
      <circle
        r={radius}
        className="fill-card stroke-border"
        strokeWidth={0.02}
      />
      <g transform="scale(0.016) translate(-12, -12)">
        <Image
          className="stroke-muted-foreground" 
          size={24}
          strokeWidth={2}
        />
      </g>
    </g>
  )
} 