import * as React from 'react'
import { cn } from '@/lib/utils'
import { Timestamp } from './timestamp'
import { Badge } from './badge'
import { Star, StarIcon, FileStack, ChevronDown, ChevronUp, Award } from 'lucide-react'
import { Button } from './button'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { parse as parseYaml } from 'yaml'

export interface ScoreVersion {
  id: string
  scoreId: string
  configuration: string
  isFeatured: boolean
  createdAt: string
  updatedAt: string
  // Temporary mock data until we have a user model
  comment?: string
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
}

export function ScoreVersionHistory({
  versions,
  championVersionId,
  selectedVersionId,
  onVersionSelect,
  onToggleFeature,
  onPromoteToChampion,
  className,
  ...props
}: ScoreVersionHistoryProps) {
  const [isHistoryExpanded, setIsHistoryExpanded] = React.useState(false)

  // Sort versions by createdAt in descending order (newest first)
  const sortedVersions = [...versions].sort(
    (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
  )

  // Find champion version if it exists
  const championVersion = championVersionId ? versions.find(v => v.id === championVersionId) : null
  
  // Separate champion version from other versions
  const otherVersions = sortedVersions.filter(v => v.id !== championVersionId)

  const renderVersion = (version: ScoreVersion, isChampion = false) => {
    const config = parseYaml(version.configuration)
    const isSelected = version.id === selectedVersionId
    
    return (
      <div
        key={version.id}
        className={cn(
          "flex flex-col p-3 rounded-md cursor-pointer transition-colors",
          isSelected ? "bg-secondary" : "bg-background hover:bg-accent/10"
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
              <Award className="h-4 w-4 text-primary" />
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
                  <StarIcon className="h-4 w-4 fill-current" />
                ) : (
                  <Star className="h-4 w-4" />
                )}
              </Button>
            )}
          </div>
        </div>
        
        <div className="flex items-start gap-4 mt-2">
          <div className="flex-1 text-sm text-foreground italic break-words">
            {version.comment || "Updated name and external ID"}
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
      <div className="space-y-4">
        {/* Header with appropriate icon */}
        <div className="flex items-center gap-2 text-sm font-medium">
          {championVersion ? (
            <>
              <Award className="h-4 w-4" />
              <span>Champion Version</span>
            </>
          ) : (
            <>
              <FileStack className="h-4 w-4" />
              <span>Version History</span>
            </>
          )}
        </div>

        {/* Always show champion version at the top if it exists */}
        {championVersion && renderVersion(championVersion, true)}
        
        {/* Show expand/collapse button if there are more versions */}
        {otherVersions.length > 0 && (
          <Button
            variant="ghost"
            className="w-full flex items-center justify-start gap-2 h-auto py-2 px-0 font-medium hover:bg-transparent"
            onClick={() => setIsHistoryExpanded(!isHistoryExpanded)}
          >
            <FileStack className="h-4 w-4" />
            <span>History</span>
            {isHistoryExpanded ? (
              <ChevronUp className="h-4 w-4 ml-1" />
            ) : (
              <ChevronDown className="h-4 w-4 ml-1" />
            )}
          </Button>
        )}
        
        {/* Show other versions when expanded with proper scrolling */}
        {isHistoryExpanded && otherVersions.length > 0 && (
          <div className="max-h-[300px] overflow-y-auto pr-1">
            <div className="space-y-2">
              {otherVersions.map(version => renderVersion(version, false))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
} 