import * as React from 'react'
import { cn } from '@/lib/utils'
import { Timestamp } from './timestamp'
import { Badge } from './badge'
import { Star, StarIcon, FileStack, ChevronDown, ChevronUp, Award } from 'lucide-react'
import { Button } from './button'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'

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
}

export function ScoreVersionHistory({
  versions,
  championVersionId,
  selectedVersionId,
  onVersionSelect,
  onToggleFeature,
  className,
  ...props
}: ScoreVersionHistoryProps) {
  const [isHistoryExpanded, setIsHistoryExpanded] = React.useState(false)

  // Sort versions by createdAt in descending order
  const sortedVersions = [...versions].sort(
    (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
  )

  // Get selected version or champion version if it exists, otherwise use most recent
  const selectedVersion = selectedVersionId ? versions.find(v => v.id === selectedVersionId) : null
  const championVersion = championVersionId ? versions.find(v => v.id === championVersionId) : null
  const firstVersion = selectedVersion || championVersion || sortedVersions[0]
  const otherVersions = sortedVersions
    .filter(v => v.id !== firstVersion?.id)
    .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())

  const renderVersion = (version: ScoreVersion) => {
    const config = JSON.parse(version.configuration)
    const isChampion = version.id === championVersionId
    const isSelected = version.id === selectedVersionId
    
    return (
      <div
        key={version.id}
        className={cn(
          "flex flex-col p-3 rounded-md cursor-pointer transition-colors",
          isSelected ? "bg-accent" : "bg-card hover:bg-accent/50",
          isSelected && "border-2 border-primary"
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
            <div className="text-sm text-muted-foreground">
              <Timestamp time={version.createdAt} variant="relative" />
              {isSelected && (
                <span className="ml-2 text-primary font-medium">(Selected)</span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2 ml-4">
            {isChampion && (
              <Award className="h-4 w-4 text-muted-foreground" />
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
          <div className="flex-1 text-sm text-muted-foreground italic break-words">
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
    <div className={cn("space-y-4", className)} {...props}>
      <div className="space-y-4">
        {/* Header with Award icon */}
        <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
          {selectedVersion ? (
            <>
              <Award className="h-4 w-4" />
              <span>Selected Version {selectedVersion.id === championVersionId && "(Champion)"}</span>
            </>
          ) : championVersion ? (
            <>
              <Award className="h-4 w-4" />
              <span>Champion Version</span>
            </>
          ) : (
            <>
              <FileStack className="h-4 w-4" />
              <span>Latest Version</span>
            </>
          )}
        </div>

        {/* Always show selected/champion/first version */}
        {firstVersion && renderVersion(firstVersion)}
        
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
        
        {/* Show other versions when expanded */}
        {isHistoryExpanded && otherVersions.length > 0 && (
          <div className="space-y-2">
            {otherVersions.map(renderVersion)}
          </div>
        )}
      </div>
    </div>
  )
} 