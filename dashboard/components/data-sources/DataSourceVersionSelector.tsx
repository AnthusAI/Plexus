"use client"

import React, { useState, useEffect } from "react"
import { ChevronDown, ChevronRight, Calendar, Badge as BadgeIcon } from "lucide-react"
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
    <div className={cn("space-y-2", className)}>
      <Button
        variant="ghost"
        size="sm"
        onClick={toggleExpanded}
        className="h-auto p-2 text-sm text-muted-foreground hover:text-foreground justify-start"
      >
        {isExpanded ? (
          <ChevronDown className="h-4 w-4 mr-1" />
        ) : (
          <ChevronRight className="h-4 w-4 mr-1" />
        )}
        Versions:
        {versions.length > 0 && (
          <Badge variant="secondary" className="ml-2 text-xs">
            {versions.length}
          </Badge>
        )}
      </Button>

      {isExpanded && (
        <div className="bg-background border rounded-md p-3 space-y-2">
          {isLoading ? (
            <div className="text-sm text-muted-foreground">Loading versions...</div>
          ) : versions.length === 0 ? (
            <div className="text-sm text-muted-foreground">No versions found</div>
          ) : (
            <div className="space-y-2">
              {versions.map((version) => {
                const isCurrent = version.id === currentVersionId
                return (
                  <div
                    key={version.id}
                    className={cn(
                      "flex items-center justify-between p-2 rounded-md border cursor-pointer transition-colors",
                      "hover:bg-muted/50",
                      isCurrent && "bg-primary/10 border-primary/20"
                    )}
                    onClick={() => handleVersionClick(version)}
                  >
                    <div className="flex items-center space-x-2 flex-1">
                      <Calendar className="h-4 w-4 text-muted-foreground" />
                      <div className="flex-1">
                        <div className="text-sm">
                          <Timestamp time={version.createdAt} variant="relative" />
                        </div>
                        {version.note && (
                          <div className="text-xs text-muted-foreground mt-1">
                            {version.note}
                          </div>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      {version.isFeatured && (
                        <Badge variant="outline" className="text-xs">
                          Featured
                        </Badge>
                      )}
                      {isCurrent && (
                        <Badge variant="default" className="text-xs">
                          Current
                        </Badge>
                      )}
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