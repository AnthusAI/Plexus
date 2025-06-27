"use client"

import React, { useState } from "react"
import { ChevronDown, ChevronRight, File } from "lucide-react"
import { cn } from "@/lib/utils"
import { FileAttachments, type FileAttachmentsProps } from "@/components/items/FileAttachments"

interface CollapsibleFileAttachmentsProps extends Omit<FileAttachmentsProps, 'className'> {
  className?: string
}

export function CollapsibleFileAttachments({
  attachedFiles = [],
  className,
  ...props
}: CollapsibleFileAttachmentsProps) {
  const [isExpanded, setIsExpanded] = useState(false)

  const toggleExpanded = () => {
    setIsExpanded(!isExpanded)
  }

  return (
    <div className={cn("flex-shrink-0", className)}>
      <div 
        className="flex items-center gap-2 mb-4 cursor-pointer"
        onClick={toggleExpanded}
      >
        <File className="h-4 w-4 text-foreground" />
        <span className="text-sm font-medium">Files ({attachedFiles.length})</span>
        {isExpanded ? (
          <ChevronDown className="h-4 w-4 text-muted-foreground ml-1" />
        ) : (
          <ChevronRight className="h-4 w-4 text-muted-foreground ml-1" />
        )}
      </div>

      {isExpanded && (
        <div className="space-y-3">
          <FileAttachments
            attachedFiles={attachedFiles}
            {...props}
          />
        </div>
      )}
    </div>
  )
} 