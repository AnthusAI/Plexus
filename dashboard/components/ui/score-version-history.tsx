import * as React from 'react'
import { cn } from '@/lib/utils'
import { Timestamp } from './timestamp'
import { Badge } from './badge'
import { Star, StarIcon } from 'lucide-react'
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
  onToggleFeature?: (versionId: string) => void
}

export function ScoreVersionHistory({
  versions,
  championVersionId,
  onToggleFeature,
  className,
  ...props
}: ScoreVersionHistoryProps) {
  // Sort versions by createdAt in descending order
  const sortedVersions = [...versions].sort(
    (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
  )

  return (
    <div className={cn("space-y-2", className)} {...props}>
      <div className="text-sm font-medium mb-4">Version History</div>
      <div className="space-y-2">
        {sortedVersions.map((version) => {
          const config = JSON.parse(version.configuration)
          const isChampion = version.id === championVersionId
          
          return (
            <div
              key={version.id}
              className={cn(
                "flex flex-col p-3 rounded-md",
                isChampion ? "bg-accent" : "bg-card hover:bg-accent/50"
              )}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="text-sm text-muted-foreground">
                    <Timestamp time={version.createdAt} variant="relative" />
                  </div>
                  {isChampion && (
                    <Badge variant="secondary">Champion</Badge>
                  )}
                </div>
                <div className="flex items-center gap-2 ml-4">
                  {onToggleFeature && (
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => onToggleFeature(version.id)}
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
        })}
      </div>
    </div>
  )
} 