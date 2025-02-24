import * as React from 'react'
import { Card } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { MoreHorizontal, X, Square, RectangleVertical, FileStack, ChevronDown, ChevronUp } from 'lucide-react'
import { CardButton } from '@/components/CardButton'
import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import * as Popover from '@radix-ui/react-popover'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { generateClient } from 'aws-amplify/api'
import { toast } from 'sonner'
import { ScoreVersionHistory } from './score-version-history'

const client = generateClient();

export interface ScoreData {
  id: string
  name: string
  description: string
  type: string
  order: number
  externalId?: string
  icon?: React.ReactNode
}

interface ScoreVersion {
  id: string
  scoreId: string
  configuration: string
  isFeatured: boolean
  isChampion?: boolean
  comment?: string
  createdAt: string
  updatedAt: string
  user?: {
    name: string
    avatar: string
    initials: string
  }
}

interface ScoreVersionRecord {
  scoreId: string
  score: {
    name: string
    order: number
    type: string
    // ... other score fields
  }
  versions: ScoreVersion[]
}

interface ScoreComponentProps extends React.HTMLAttributes<HTMLDivElement> {
  score: ScoreData
  variant?: 'grid' | 'detail'
  isSelected?: boolean
  onClick?: () => void
  onClose?: () => void
  onToggleFullWidth?: () => void
  isFullWidth?: boolean
  onSave?: () => void
}

const GridContent = React.memo(({ 
  score,
  isSelected 
}: { 
  score: ScoreData
  isSelected?: boolean
}) => {
  return (
    <div className="flex justify-between items-start">
      <div className="space-y-2">
        <div className="font-medium">{score.name}</div>
        <div className="text-sm text-muted-foreground">{score.type}</div>
        <div className="text-sm">{score.description}</div>
      </div>
      {score.icon && (
        <div className="text-muted-foreground">
          {score.icon}
        </div>
      )}
    </div>
  )
})

const DetailContent = React.memo(({
  score,
  isFullWidth,
  onToggleFullWidth,
  onClose,
  onEditChange,
  onSave,
  onCancel,
  hasChanges,
  versions,
  championVersionId,
  onToggleFeature,
  versionComment,
  onCommentChange,
}: {
  score: ScoreData
  isFullWidth: boolean
  onToggleFullWidth?: () => void
  onClose?: () => void
  onEditChange?: (changes: Partial<ScoreData>) => void
  onSave?: () => void
  onCancel?: () => void
  hasChanges?: boolean
  versions?: ScoreVersion[]
  championVersionId?: string
  onToggleFeature?: (versionId: string) => void
  versionComment: string
  onCommentChange: (comment: string) => void
}) => {
  const [isHistoryExpanded, setIsHistoryExpanded] = React.useState(false)

  return (
    <div className="w-full flex flex-col min-h-0">
      <div className="flex justify-between items-start w-full">
        <div className="space-y-2 flex-1">
          <Input
            value={score.name}
            onChange={(e) => onEditChange?.({ name: e.target.value })}
            className="text-lg font-semibold bg-background border-0 px-2 h-auto w-full
                     focus-visible:ring-0 focus-visible:ring-offset-0 
                     placeholder:text-muted-foreground rounded-md"
            placeholder="Score Name"
          />
          <Input
            value={score.externalId ?? ''}
            onChange={(e) => onEditChange?.({ externalId: e.target.value })}
            className="font-mono bg-background border-0 px-2 h-auto w-full
                     focus-visible:ring-0 focus-visible:ring-offset-0 
                     placeholder:text-muted-foreground rounded-md"
            placeholder="External ID"
          />
        </div>
        <div className="flex gap-2 ml-4">
          <DropdownMenu.Root>
            <DropdownMenu.Trigger asChild>
              <CardButton
                icon={MoreHorizontal}
                onClick={() => {}}
                aria-label="More options"
              />
            </DropdownMenu.Trigger>
            <DropdownMenu.Portal>
              <DropdownMenu.Content align="end" className="min-w-[8rem] overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md">
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>
          {onToggleFullWidth && (
            <CardButton
              icon={isFullWidth ? RectangleVertical : Square}
              onClick={onToggleFullWidth}
              aria-label={isFullWidth ? 'Exit full width' : 'Full width'}
            />
          )}
          {onClose && (
            <CardButton
              icon={X}
              onClick={onClose}
              aria-label="Close"
            />
          )}
        </div>
      </div>

      {hasChanges && (
        <div className="mt-4 space-y-4">
          <div className="space-y-2">
            <label htmlFor="version-comment" className="text-sm text-muted-foreground">
              Version Comment
            </label>
            <textarea
              id="version-comment"
              value={versionComment}
              onChange={(e) => onCommentChange(e.target.value)}
              placeholder="Describe the changes made in this version..."
              className="w-full min-h-[80px] px-3 py-2 rounded-md border bg-background text-sm resize-none"
            />
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onCancel}>Cancel</Button>
            <Button onClick={onSave}>Save Changes</Button>
          </div>
        </div>
      )}

      <div className="mt-6">
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
        
        {isHistoryExpanded && versions && (
          <div className="mt-2 rounded-lg bg-background p-4">
            <ScoreVersionHistory
              versions={versions}
              championVersionId={championVersionId}
              onToggleFeature={onToggleFeature}
            />
          </div>
        )}
      </div>
    </div>
  )
})

export function ScoreComponent({
  score,
  variant = 'grid',
  isSelected,
  onClick,
  onClose,
  onToggleFullWidth,
  isFullWidth = false,
  onSave,
  className,
  ...props
}: ScoreComponentProps) {
  const [editedScore, setEditedScore] = React.useState<ScoreData>(score)
  const [hasChanges, setHasChanges] = React.useState(false)
  const [versions, setVersions] = React.useState<ScoreVersion[]>([])
  const [championVersionId, setChampionVersionId] = React.useState<string>()
  const [versionComment, setVersionComment] = React.useState('')

  React.useEffect(() => {
    setEditedScore(score)
    setVersionComment('') // Reset comment when score changes
    const fetchVersions = async () => {
      try {
        console.log('Fetching versions for score:', score.id);
        const response = await client.graphql({
          query: `
            query GetScoreVersions($scoreId: String!) {
              listScoreVersions(filter: { scoreId: { eq: $scoreId } }) {
                items {
                  id
                  scoreId
                  configuration
                  isFeatured
                  comment
                  createdAt
                  updatedAt
                }
              }
            }
          `,
          variables: {
            scoreId: score.id
          }
        });
        console.log('API Response:', response);
        
        if (response.data?.listScoreVersions?.items) {
          const versionItems = response.data.listScoreVersions.items;
          console.log('Found versions:', versionItems);
          setVersions(versionItems);
          // For now, let's consider the most recent version as champion
          if (versionItems.length > 0) {
            setChampionVersionId(versionItems[0].id);
          }
        } else {
          console.log('No versions found in response:', response);
        }
      } catch (error) {
        console.error('Error fetching versions:', error);
      }
    };
    fetchVersions();
  }, [score])

  const handleEditChange = (changes: Partial<ScoreData>) => {
    setEditedScore(prev => {
      const updated = { ...prev, ...changes }
      setHasChanges(true)
      return updated
    })
  }

  const handleCancel = () => {
    setEditedScore(score)
    setVersionComment('') // Reset comment on cancel
    setHasChanges(false)
  }

  const handleToggleFeature = async (versionId: string) => {
    try {
      const version = versions.find(v => v.id === versionId);
      if (!version) return;

      // TODO: Enable API call once schema is updated
      // await amplifyClient.ScoreVersion.update({
      //   id: versionId,
      //   isFeatured: !version.isFeatured
      // });

      // Update local state
      setVersions(prev => prev.map(v => 
        v.id === versionId ? { ...v, isFeatured: !v.isFeatured } : v
      ));

      toast.success('Version feature status updated');
    } catch (error) {
      console.error('Error toggling feature:', error);
      toast.error('Failed to update version feature status');
    }
  };

  const handleSave = async () => {
    try {
      // Update the Score record with the new values
      await client.graphql({
        query: `
          mutation UpdateScore($input: UpdateScoreInput!) {
            updateScore(input: $input) {
              id
              name
              externalId
            }
          }
        `,
        variables: {
          input: {
            id: score.id,
            name: editedScore.name,
            externalId: editedScore.externalId,
          }
        }
      });

      // Create a new version
      const versionPayload = {
        scoreId: score.id,
        configuration: JSON.stringify({
          name: editedScore.name,
          externalId: editedScore.externalId
        }),
        isFeatured: false,
        comment: versionComment || 'Updated score configuration', // Use default if no comment provided
      };

      const createVersionResponse = await client.graphql({
        query: `
          mutation CreateScoreVersion($input: CreateScoreVersionInput!) {
            createScoreVersion(input: $input) {
              id
              scoreId
              configuration
              isFeatured
              comment
              createdAt
              updatedAt
            }
          }
        `,
        variables: {
          input: versionPayload
        }
      });
      
      const newVersion = createVersionResponse.data.createScoreVersion;
      
      // Update local state with the new version
      const placeholderVersion = {
        ...newVersion,
        user: {
          name: "Ryan Porter",
          avatar: "/user-avatar.png",
          initials: "RP"
        }
      };
      setVersions(prev => [placeholderVersion, ...prev]);
      setChampionVersionId(placeholderVersion.id);
      
      toast.success('Score updated successfully');
      setHasChanges(false);
      setVersionComment(''); // Reset comment after successful save
    } catch (error) {
      console.error('Error saving score:', error);
      toast.error(error instanceof Error ? error.message : 'Error updating score');
    }
  };

  return (
    <div
      className={cn(
        "w-full rounded-lg text-card-foreground hover:bg-accent/50 transition-colors",
        variant === 'grid' ? (
          isSelected ? "bg-card-selected" : "bg-card"
        ) : "bg-card-selected",
        variant === 'detail' && "h-full flex flex-col",
        className
      )}
      {...props}
    >
      <div className={cn(
        "p-4 w-full",
        variant === 'detail' && "flex-1 flex flex-col min-h-0"
      )}>
        <div 
          className={cn(
            "w-full",
            variant === 'grid' && "cursor-pointer",
            variant === 'detail' && "h-full flex flex-col min-h-0"
          )}
          onClick={() => variant === 'grid' && onClick?.()}
          role={variant === 'grid' ? "button" : undefined}
          tabIndex={variant === 'grid' ? 0 : undefined}
          onKeyDown={variant === 'grid' ? (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault()
              onClick?.()
            }
          } : undefined}
        >
          {variant === 'grid' ? (
            <GridContent score={editedScore} isSelected={isSelected} />
          ) : (
            <DetailContent 
              score={editedScore}
              isFullWidth={isFullWidth}
              onToggleFullWidth={onToggleFullWidth}
              onClose={onClose}
              onEditChange={handleEditChange}
              onSave={onSave || handleSave}
              onCancel={handleCancel}
              hasChanges={hasChanges}
              versions={versions}
              championVersionId={championVersionId}
              onToggleFeature={handleToggleFeature}
              versionComment={versionComment}
              onCommentChange={setVersionComment}
            />
          )}
        </div>
      </div>
    </div>
  )
} 