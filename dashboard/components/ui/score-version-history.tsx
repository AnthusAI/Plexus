import * as React from 'react'
import { cn } from '@/lib/utils'
import { Timestamp } from './timestamp'
import { Badge } from './badge'
import { Star, FileStack, ChevronDown, ChevronUp, Award } from 'lucide-react'
import { Button } from './button'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { ToggleGroup, ToggleGroupItem } from './toggle-group'
import { CardButton } from '@/components/CardButton'
import { parse as parseYaml } from 'yaml'

export interface ScoreVersion {
  id: string
  scoreId: string
  configuration: string
  isFeatured: boolean
  createdAt: string
  updatedAt: string
  // Temporary mock data until we have a user model
  note?: string
  user?: {
    name: string
    avatar: string
    initials: string
  }
}

export interface ScoreVersionHistoryProps extends React.HTMLAttributes<HTMLDivElement> {
  versions: ScoreVersion[]
  championVersionId?: string
  selectedVersionId?: string
  onVersionSelect?: (version: ScoreVersion) => void
  onToggleFeature?: (versionId: string) => void
  onPromoteToChampion?: (versionId: string) => void
  showOnlyFeatured?: boolean
  onToggleShowOnlyFeatured?: () => void
  forceExpanded?: boolean
}

export function ScoreVersionHistory({
  versions,
  championVersionId,
  selectedVersionId,
  onVersionSelect,
  onToggleFeature,
  onPromoteToChampion,
  showOnlyFeatured = false,
  onToggleShowOnlyFeatured,
  forceExpanded = false,
  className,
  ...props
}: ScoreVersionHistoryProps) {
  const [isHistoryExpanded, setIsHistoryExpanded] = React.useState(forceExpanded) // Collapsed by default, unless forceExpanded
  
  // Update expansion state when forceExpanded changes
  React.useEffect(() => {
    if (forceExpanded) {
      setIsHistoryExpanded(true)
    }
  }, [forceExpanded])
  
  // Smart default for featured filter based on version count
  const defaultShowOnlyFeatured = versions.length > 3
  const [internalShowOnlyFeatured, setInternalShowOnlyFeatured] = React.useState(defaultShowOnlyFeatured)
  
  // Use internal state if no external control is provided
  // If onToggleShowOnlyFeatured is provided, use external control, otherwise use internal
  const useInternalState = !onToggleShowOnlyFeatured
  const effectiveShowOnlyFeatured = useInternalState ? internalShowOnlyFeatured : showOnlyFeatured
  const effectiveOnToggleShowOnlyFeatured = useInternalState ? (() => {
    setInternalShowOnlyFeatured(prev => !prev);
  }) : onToggleShowOnlyFeatured

  // Sort versions by createdAt in descending order (newest first)
  const sortedVersions = [...versions].sort(
    (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
  )

  // Find champion version if it exists
  const championVersion = championVersionId ? versions.find(v => v.id === championVersionId) : null
  
  // Filter versions based on effective showOnlyFeatured toggle
  const filteredVersions = effectiveShowOnlyFeatured 
    ? sortedVersions.filter(v => v.isFeatured || v.id === championVersionId)
    : sortedVersions
  
  // Separate champion version from other versions
  const otherVersions = filteredVersions.filter(v => v.id !== championVersionId)

  const renderVersion = (version: ScoreVersion, isChampion = false) => {
    let config
    try {
      config = parseYaml(version.configuration)
    } catch (error) {
      console.warn('Failed to parse YAML configuration:', error)
      config = null
    }
    const isSelected = version.id === selectedVersionId
    
    return (
      <div
        key={version.id}
        className={cn(
          "flex flex-col p-3 rounded-md cursor-pointer transition-colors",
          isSelected ? "bg-card-selected" : "bg-card hover:bg-accent/10"
        )}
        onClick={() => onVersionSelect?.(version)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            onVersionSelect?.(version)
          }
        }}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="text-sm text-foreground">
              <Timestamp time={version.createdAt} variant="relative" />
            </div>
          </div>
          <div className="flex items-center gap-2 ml-4">
            {isChampion ? (
              <Award className="h-4 w-4 text-foreground" />
            ) : onPromoteToChampion && (
              <Button
                variant="outline"
                size="sm"
                onClick={(e) => {
                  e.stopPropagation()
                  onPromoteToChampion(version.id)
                }}
                className="h-7 text-xs px-2 py-0 flex items-center gap-1"
              >
                <Award className="h-3 w-3" />
                Promote
              </Button>
            )}
            {onToggleFeature && (
              <Button
                variant="ghost"
                size="icon"
                onClick={(e) => {
                  e.stopPropagation()
                  onToggleFeature(version.id)
                }}
                className="h-8 w-8"
              >
                {version.isFeatured ? (
                  <Star className="h-4 w-4" fill="currentColor" />
                ) : (
                  <Star className="h-4 w-4" />
                )}
              </Button>
            )}
          </div>
        </div>
        
        <div className="flex items-start gap-4 mt-2">
          <div className="flex-1 text-sm text-foreground italic break-words">
            {version.note || "Updated name and external ID"}
          </div>
          {version.user && (
            <Avatar className="h-8 w-8 flex-shrink-0">
              <AvatarImage src={version.user.avatar} alt={version.user.name} />
              <AvatarFallback className="bg-background dark:bg-border">
                {version.user.initials}
              </AvatarFallback>
            </Avatar>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className={cn("space-y-4 w-full", className)} {...props}>
      <div className="bg-background rounded-lg p-4 shadow-sm space-y-4">
        <div className="space-y-4">
          {/* Header with appropriate icon and toggle control */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm font-medium">
              {championVersion ? (
                <>
                  <Award className="h-4 w-4 text-foreground" />
                  <span>Champion Version</span>
                </>
              ) : (
                <>
                  <FileStack className="h-4 w-4" />
                  <span>Version History</span>
                </>
              )}
            </div>
          </div>

          {/* Always show champion version at the top if it exists */}
          {championVersion && renderVersion(championVersion, true)}
          
          {/* Show expand/collapse button if there are more versions */}
          {otherVersions.length > 0 && (
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <FileStack className="h-4 w-4" />
                <span className="text-sm font-medium">Version History</span>
              </div>
              
              <div className="flex items-center gap-2">
                {/* Featured filter toggle group - only show when expanded */}
                {isHistoryExpanded && (
                  <ToggleGroup 
                    type="single" 
                    value={effectiveShowOnlyFeatured ? "featured" : "all"}
                    onValueChange={(value) => {
                      if (value === "featured" && !effectiveShowOnlyFeatured) {
                        effectiveOnToggleShowOnlyFeatured();
                      } else if (value === "all" && effectiveShowOnlyFeatured) {
                        effectiveOnToggleShowOnlyFeatured();
                      }
                    }}
                    variant="outline"
                    className="h-8"
                  >
                    <ToggleGroupItem value="all" className="h-8 px-2 gap-1 text-xs">
                      <Star className="h-3 w-3" />
                      All
                    </ToggleGroupItem>
                    <ToggleGroupItem value="featured" className="h-8 px-2 gap-1 text-xs">
                      <Star className="h-3 w-3" fill="currentColor" />
                      Featured
                    </ToggleGroupItem>
                  </ToggleGroup>
                )}
                
                <CardButton
                  icon={isHistoryExpanded ? ChevronUp : ChevronDown}
                  onClick={() => setIsHistoryExpanded(!isHistoryExpanded)}
                  aria-label={isHistoryExpanded ? 'Collapse version history' : 'Expand version history'}
                  className="bg-card"
                />
              </div>
            </div>
          )}
          
          {/* Show versions when expanded */}
          {isHistoryExpanded && otherVersions.length > 0 && (
            <div className="mt-3 max-h-[300px] overflow-y-auto pr-1">
              <div className="space-y-3">
                {otherVersions.map(version => renderVersion(version, false))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
} 