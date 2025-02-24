import * as React from 'react'
import { Card } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { MoreHorizontal, X, Square, RectangleVertical, FileStack, ChevronDown, ChevronUp, Award } from 'lucide-react'
import { CardButton } from '@/components/CardButton'
import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import * as Popover from '@radix-ui/react-popover'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { generateClient } from 'aws-amplify/api'
import { toast } from 'sonner'
import { ScoreVersionHistory } from './score-version-history'
import type { GraphQLResult } from '@aws-amplify/api'
import Editor from '@monaco-editor/react'
import { parse as parseYaml, stringify as stringifyYaml } from 'yaml'

const client = generateClient();

export interface ScoreData {
  id: string
  name: string
  description: string
  type: string
  order: number
  externalId?: string
  icon?: React.ReactNode
  configuration?: string // YAML configuration string
  championVersionId?: string // ID of the champion version
}

interface ScoreVersion {
  id: string
  scoreId: string
  configuration: string // YAML string
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

interface GetScoreVersionsResponse {
  listScoreVersions: {
    items: ScoreVersion[]
  }
}

interface CreateScoreVersionResponse {
  createScoreVersion: ScoreVersion
}

interface GetScoreResponse {
  getScore: {
    id: string
    name: string
    externalId?: string
    championVersionId?: string
  }
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
  selectedVersionId,
  onVersionSelect,
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
  selectedVersionId?: string
  onVersionSelect?: (version: ScoreVersion) => void
  onToggleFeature?: (versionId: string) => void
  versionComment: string
  onCommentChange: (comment: string) => void
}) => {
  // Get the current version's configuration
  const currentVersion = versions?.find(v => 
    v.id === (selectedVersionId || championVersionId)
  )
  
  // Parse YAML configuration if available, otherwise create default YAML
  const defaultYaml = stringifyYaml({
    name: score.name,
    externalId: score.externalId
  })
  const configuration = currentVersion?.configuration || defaultYaml
  
  // Parse current configuration for form fields
  const parsedConfig = React.useMemo(() => {
    try {
      return parseYaml(configuration)
    } catch (error) {
      console.error('Error parsing YAML:', error)
      return { name: score.name, externalId: score.externalId }
    }
  }, [configuration, score])

  return (
    <div className="w-full flex flex-col min-h-0">
      <div className="flex justify-between items-start w-full">
        <div className="space-y-2 flex-1">
          <Input
            value={parsedConfig.name}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => onEditChange?.({ name: e.target.value })}
            className="text-lg font-semibold bg-background border-0 px-2 h-auto w-full
                     focus-visible:ring-0 focus-visible:ring-offset-0 
                     placeholder:text-muted-foreground rounded-md"
            placeholder="Score Name"
          />
          <Input
            value={parsedConfig.externalId ?? ''}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => onEditChange?.({ externalId: e.target.value })}
            className="font-mono bg-background border-0 px-2 h-auto w-full
                     focus-visible:ring-0 focus-visible:ring-offset-0 
                     placeholder:text-muted-foreground rounded-md"
            placeholder="External ID"
          />
          <textarea
            value={versionComment}
            onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => onCommentChange(e.target.value)}
            placeholder="Add a comment about this version..."
            className="w-full px-2 py-1.5 rounded-md bg-background border-0 text-sm resize-none
                     focus-visible:ring-0 focus-visible:ring-offset-0 
                     placeholder:text-muted-foreground"
            rows={2}
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

      {/* YAML Editor */}
      <div className="mt-6 rounded-md border bg-background">
        <Editor
          height="300px"
          defaultLanguage="yaml"
          value={configuration}
          onChange={(value) => {
            try {
              // Parse YAML to validate it and get values for form
              const parsed = parseYaml(value || '')
              onEditChange?.({
                name: parsed.name,
                externalId: parsed.externalId,
                configuration: value // Store the original YAML string
              })
            } catch (error) {
              // Ignore parse errors while typing
            }
          }}
          options={{
            minimap: { enabled: false },
            fontSize: 14,
            lineNumbers: 'on',
            scrollBeyondLastLine: false,
            wordWrap: 'on',
            wrappingIndent: 'indent',
            automaticLayout: true,
            fontFamily: 'monospace'
          }}
        />
      </div>

      {hasChanges && (
        <div className="mt-4 space-y-4">
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onCancel}>Cancel</Button>
            <Button onClick={onSave}>Save Changes</Button>
          </div>
        </div>
      )}

      {versions && (
        <div className="mt-6">
          <ScoreVersionHistory
            versions={versions}
            championVersionId={championVersionId}
            selectedVersionId={selectedVersionId}
            onVersionSelect={onVersionSelect}
            onToggleFeature={onToggleFeature}
          />
        </div>
      )}
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
  const [selectedVersionId, setSelectedVersionId] = React.useState<string>()
  const [versionComment, setVersionComment] = React.useState('')

  React.useEffect(() => {
    setEditedScore(score)
    setVersionComment('') // Reset comment when score changes
    const fetchVersions = async () => {
      try {
        console.log('Fetching versions for score:', score.id);
        
        // First, get the score details to get the championVersionId
        const scoreResponse = await client.graphql({
          query: `
            query GetScore($id: ID!) {
              getScore(id: $id) {
                id
                name
                externalId
                championVersionId
              }
            }
          `,
          variables: {
            id: score.id
          }
        }) as GraphQLResult<GetScoreResponse>;
        
        let championId: string | undefined;
        
        if ('data' in scoreResponse && scoreResponse.data?.getScore) {
          const scoreData = scoreResponse.data.getScore;
          championId = scoreData?.championVersionId;
          
          if (championId) {
            setChampionVersionId(championId);
          }
        }
        
        // Then fetch all versions
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
        }) as GraphQLResult<GetScoreVersionsResponse>;
        
        console.log('API Response:', response);
        
        if ('data' in response && response.data?.listScoreVersions?.items) {
          const versionItems = response.data.listScoreVersions.items;
          console.log('Found versions:', versionItems);
          setVersions(versionItems);
          
          // Sort versions by createdAt in descending order
          const sortedVersions = [...versionItems].sort(
            (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
          );
          
          // Find champion version or use the most recent one
          const champion = championId 
            ? versionItems.find(v => v.id === championId) 
            : sortedVersions[0];
            
          if (champion) {
            if (!championId) {
              setChampionVersionId(champion.id);
            }
            // Automatically select the champion version
            handleVersionSelect(champion);
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
    setSelectedVersionId(undefined) // Reset selection to champion
  }

  const handleVersionSelect = (version: ScoreVersion) => {
    setSelectedVersionId(version.id)
    setVersionComment(version.comment || '')
    
    try {
      const config = parseYaml(version.configuration)
      setEditedScore(prev => ({
        ...prev,
        name: config.name || prev.name,
        externalId: config.externalId || prev.externalId,
        description: config.description || prev.description,
        configuration: version.configuration // Keep original YAML
      }))
      
      // If this is a new selection (not just re-rendering), show a confirmation
      if (selectedVersionId !== version.id) {
        toast.info(`Viewing version from ${new Date(version.createdAt).toLocaleString()}`)
      }
    } catch (error) {
      console.error('Error parsing version YAML:', error)
      toast.error('Error loading version configuration')
    }
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

      // Create a new version with YAML configuration
      const versionPayload = {
        scoreId: score.id,
        configuration: editedScore.configuration || stringifyYaml({
          name: editedScore.name,
          externalId: editedScore.externalId,
          description: editedScore.description
        }),
        isFeatured: false,
        comment: versionComment || 'Updated score configuration',
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
      }) as GraphQLResult<CreateScoreVersionResponse>;
      
      const newVersion = 'data' in createVersionResponse && createVersionResponse.data?.createScoreVersion;
      
      // Update local state with the new version
      if (newVersion) {
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
        setSelectedVersionId(placeholderVersion.id);
        
        // Update the Score record to set this as the champion version
        try {
          await client.graphql({
            query: `
              mutation UpdateScoreChampion($input: UpdateScoreInput!) {
                updateScore(input: $input) {
                  id
                  championVersionId
                }
              }
            `,
            variables: {
              input: {
                id: score.id,
                championVersionId: placeholderVersion.id,
              }
            }
          });
        } catch (error) {
          console.error('Error updating champion version:', error);
          // Continue even if this fails
        }
      }
      
      toast.success('Score updated successfully');
      setHasChanges(false);
      setVersionComment('');
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
              selectedVersionId={selectedVersionId}
              onVersionSelect={handleVersionSelect}
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