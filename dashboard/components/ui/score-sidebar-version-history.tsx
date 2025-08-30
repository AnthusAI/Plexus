"use client"

import React from 'react'
import { Button } from "@/components/ui/button"
import { Crown, Clock, PanelLeftOpen, PanelLeftClose } from 'lucide-react'
import { Timestamp } from "@/components/ui/timestamp"
import { ScoreVersion } from "./score-component"

interface ScoreSidebarVersionHistoryProps {
  versions?: ScoreVersion[]
  championVersionId?: string
  selectedVersionId?: string
  onVersionSelect?: (version: ScoreVersion) => void
  isSidebarCollapsed?: boolean
  onToggleSidebar?: () => void
}

export const ScoreSidebarVersionHistory: React.FC<ScoreSidebarVersionHistoryProps> = ({
  versions = [],
  championVersionId,
  selectedVersionId,
  onVersionSelect,
  isSidebarCollapsed = false,
  onToggleSidebar
}) => {
  // State for sidebar width (in pixels)
  const [sidebarWidth, setSidebarWidth] = React.useState(320) // Default 320px (w-80)

  // Drag resize handler
  const handleDragStart = React.useCallback((e: React.MouseEvent) => {
    if (isSidebarCollapsed) return // Don't allow resize when collapsed
    
    e.preventDefault();
    
    // Get the initial mouse position and sidebar width
    const startX = e.clientX;
    const startWidth = sidebarWidth;
    
    // Create the drag handler
    const handleDrag = (e: MouseEvent) => {
      // Calculate how far the mouse has moved
      const deltaX = e.clientX - startX;
      
      // Calculate the new width with constraints (min 200px, max 600px)
      const newWidth = Math.min(Math.max(startWidth + deltaX, 200), 600);
      
      // Update the state with the new width
      requestAnimationFrame(() => {
        setSidebarWidth(newWidth);
      });
    };
    
    // Create the cleanup function
    const handleDragEnd = () => {
      if (typeof document !== 'undefined') {
        document.removeEventListener('mousemove', handleDrag);
        document.removeEventListener('mouseup', handleDragEnd);
        document.body.style.cursor = '';
      }
    };
    
    // Set the cursor for the entire document during dragging
    if (typeof document !== 'undefined') {
      document.body.style.cursor = 'col-resize';
      
      // Add the event listeners
      document.addEventListener('mousemove', handleDrag);
      document.addEventListener('mouseup', handleDragEnd);
    }
  }, [isSidebarCollapsed, sidebarWidth])

  const championVersion = versions.find(v => v.id === championVersionId)
  const sortedVersions = [...versions].sort((a, b) => 
    new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
  )

  return (
    <div 
      className={`${isSidebarCollapsed ? 'w-12' : ''} transition-all duration-200 border-r border-border flex flex-col relative`}
      style={!isSidebarCollapsed ? { width: `${sidebarWidth}px` } : {}}
    >
      {/* Sidebar Header */}
      <div className="p-3 border-b border-border flex items-center justify-between">
        {!isSidebarCollapsed && (
          <h3 className="text-sm font-medium">Version History ({versions?.length || 0})</h3>
        )}
        <Button
          variant="ghost"
          size="sm"
          onClick={onToggleSidebar}
          className="h-8 w-8 p-0"
        >
          {isSidebarCollapsed ? (
            <PanelLeftOpen className="h-4 w-4" />
          ) : (
            <PanelLeftClose className="h-4 w-4" />
          )}
        </Button>
      </div>
      
      {/* Version List */}
      {!isSidebarCollapsed && (
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {/* Champion Version - Always at top */}
          {championVersion && (
            <Button
              key={championVersion.id}
              variant={selectedVersionId === championVersion.id ? "secondary" : "ghost"}
              size="sm"
              onClick={() => onVersionSelect?.(championVersion)}
              className="w-full justify-start text-left p-2 h-auto"
            >
              <div className="flex items-center gap-2 min-w-0 flex-1">
                <Crown className="h-4 w-4 flex-shrink-0" />
                <div className="min-w-0 flex-1">
                  <div className="text-xs font-medium truncate">
                    Champion Version
                  </div>
                  <div className="text-xs text-muted-foreground truncate">
                    {championVersion.note || `Version ${championVersion.id.slice(0, 8)}`}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    <Timestamp time={championVersion.createdAt} variant="relative" showIcon={false} />
                  </div>
                </div>
              </div>
            </Button>
          )}
          
          {/* Other Versions */}
          {sortedVersions.filter(v => v.id !== championVersionId).map((version) => (
            <Button
              key={version.id}
              variant={selectedVersionId === version.id ? "secondary" : "ghost"}
              size="sm"
              onClick={() => onVersionSelect?.(version)}
              className="w-full justify-start text-left p-2 h-auto"
            >
              <div className="flex items-center gap-2 min-w-0 flex-1">
                <Clock className="h-4 w-4 flex-shrink-0" />
                <div className="min-w-0 flex-1">
                  <div className="text-xs font-medium truncate">
                    {version.note || `Version ${version.id.slice(0, 8)}`}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    <Timestamp time={version.createdAt} variant="relative" showIcon={false} />
                  </div>
                </div>
              </div>
            </Button>
          ))}
        </div>
      )}
      
      {/* Collapsed Sidebar Content */}
      {isSidebarCollapsed && (
        <div className="flex-1 p-2 space-y-2">
          {/* Champion Version */}
          {championVersion && (
            <Button
              key={championVersion.id}
              variant={selectedVersionId === championVersion.id ? "secondary" : "ghost"}
              size="sm"
              onClick={() => onVersionSelect?.(championVersion)}
              className="w-full h-8 p-0"
              title="Champion Version"
            >
              <Crown className="h-4 w-4" />
            </Button>
          )}
          
          {/* Other Versions */}
          {sortedVersions.filter(v => v.id !== championVersionId).slice(0, 4).map((version) => (
            <Button
              key={version.id}
              variant={selectedVersionId === version.id ? "secondary" : "ghost"}
              size="sm"
              onClick={() => onVersionSelect?.(version)}
              className="w-full h-8 p-0"
              title={version.note || `Version ${version.id.slice(0, 8)}`}
            >
              <Clock className="h-4 w-4" />
            </Button>
          ))}
        </div>
      )}
      
      {/* Drag Handle - positioned at the right edge */}
      {!isSidebarCollapsed && (
        <div
          className="absolute top-0 right-0 w-[4px] h-full cursor-col-resize flex-shrink-0 group z-10"
          onMouseDown={handleDragStart}
        >
          <div className="absolute inset-0 transition-colors duration-150 group-hover:bg-accent" />
        </div>
      )}
    </div>
  )
}
