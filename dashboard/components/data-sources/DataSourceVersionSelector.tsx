"use client"

import React, { useState, useEffect } from "react"
import { ChevronDown, ChevronRight, Calendar, SquareStack } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { amplifyClient } from "@/utils/amplify-client"
import type { Schema } from "@/amplify/data/resource"
import { Timestamp } from "@/components/ui/timestamp"
import { cn } from "@/lib/utils"
import { formatDistanceToNow, parseISO } from "date-fns"

interface DataSourceVersionSelectorProps {
  dataSourceId: string
  currentVersionId?: string
  onVersionSelect?: (version: Schema['DataSourceVersion']['type']) => void
  className?: string
}

export function DataSourceVersionSelector({
  dataSourceId,
  currentVersionId,
  onVersionSelect,
  className
}: DataSourceVersionSelectorProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [versions, setVersions] = useState<Schema['DataSourceVersion']['type'][]>([])
  const [isLoading, setIsLoading] = useState(false)

  // Fetch versions when expanded or when dataSourceId changes
  useEffect(() => {
    if (dataSourceId && (isExpanded || currentVersionId)) {
      fetchVersions()
    }
  }, [dataSourceId, isExpanded, currentVersionId])

  const fetchVersions = async () => {
    if (!dataSourceId) return
    
    setIsLoading(true)
    try {
      const result = await amplifyClient.DataSourceVersion.list({
        filter: { dataSourceId: { eq: dataSourceId } }
      })

      // Sort by createdAt descending (newest first)
      const sortedVersions = [...result.data].sort((a, b) => 
        new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
      )

      setVersions(sortedVersions)
    } catch (error) {
      console.error('Error fetching data source versions:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleVersionClick = (version: Schema['DataSourceVersion']['type']) => {
    onVersionSelect?.(version)
  }

  const toggleExpanded = () => {
    setIsExpanded(!isExpanded)
  }

  return (
    <div className={cn("flex-shrink-0", className)}>
      <div 
        className="flex items-center gap-2 mb-4 cursor-pointer"
        onClick={toggleExpanded}
      >
        <SquareStack className="h-4 w-4 text-foreground" />
        <span className="text-sm font-medium">Versions ({versions.length})</span>
        {isExpanded ? (
          <ChevronDown className="h-4 w-4 text-muted-foreground ml-1" />
        ) : (
          <ChevronRight className="h-4 w-4 text-muted-foreground ml-1" />
        )}
      </div>

      {isExpanded && (
        <div className="space-y-3 mb-2">
          {isLoading ? (
            <div className="text-sm text-muted-foreground">Loading versions...</div>
          ) : versions.length === 0 ? (
            <div className="text-sm text-muted-foreground">No versions found</div>
          ) : (
            <div className="space-y-3">
              {versions.map((version) => {
                const isCurrent = version.id === currentVersionId
                return (
                  <div
                    key={version.id}
                    className="p-3 rounded-lg cursor-pointer transition-colors bg-card hover:bg-accent"
                    onClick={() => handleVersionClick(version)}
                  >
                    <div className="flex justify-between items-start">
                      <div className="flex-1 min-w-0">
                        <div className="font-medium text-sm">
                          <Timestamp time={version.createdAt} variant="relative" />
                        </div>
                        {version.note && (
                          <div className="text-xs text-muted-foreground mt-1 line-clamp-2">
                            {version.note}
                          </div>
                        )}
                        {isCurrent && (
                          <div className="mt-1">
                            <Badge variant="default" className="text-xs">
                              Current
                            </Badge>
                          </div>
                        )}
                      </div>
                      <div className="flex flex-col items-center gap-0.5 ml-2 flex-shrink-0">
                        <Calendar className="h-4 w-4 text-muted-foreground" />
                        <div className="text-[10px] text-muted-foreground text-center">Version</div>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}