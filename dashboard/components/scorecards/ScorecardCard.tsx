import * as React from 'react'
import { Card } from '@/components/ui/card'
import { MoreHorizontal, Pencil, Database, ListTodo, X, Square, RectangleVertical, Plus, ChevronUp, ChevronDown } from 'lucide-react'
import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { cn } from '@/lib/utils'
import { CardButton } from '@/components/CardButton'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { EditableField } from '@/components/ui/editable-field'
import { amplifyClient } from '@/utils/amplify-client'
import { generateClient } from '@aws-amplify/api'
import type { Schema } from '@/amplify/data/resource'
import { ScoreItem } from './score-item'

const client = generateClient<Schema>()

export interface ScorecardData {
  id: string
  name: string
  key: string
  description: string
  type: string
  configuration: any
  order: number
  externalId?: string
  scoreCount?: number
  sections?: {
    items: Array<{
      id: string
      name: string
      order: number
      scores: {
        items: Array<{
          id: string
          name: string
          key: string
          description: string
          order: number
          type: string
          configuration: any
        }>
      }
    }>
  }
}

interface ScorecardCardProps extends React.HTMLAttributes<HTMLDivElement> {
  score: ScorecardData
  onEdit?: () => void
  onViewData?: () => void
  isSelected?: boolean
  onClick?: () => void
  isFullWidth?: boolean
  onToggleFullWidth?: () => void
  onClose?: () => void
  variant?: 'grid' | 'detail'
  onSave?: () => void
}

const GridContent = React.memo(({ 
  score,
  isSelected 
}: { 
  score: ScorecardData
  isSelected?: boolean
}) => {
  const scoreCount = score.scoreCount || 0
  const scoreText = scoreCount === 1 ? 'Score' : 'Scores'

  return (
    <div className="flex justify-between items-start w-full">
      <div className="space-y-1.5">
        <div className="font-medium">{score.name}</div>
        <div className="text-sm text-muted-foreground">ID: {score.externalId || '-'}</div>
        <div className="text-sm text-muted-foreground">{scoreCount} {scoreText}</div>
      </div>
      <div className="text-muted-foreground">
        <ListTodo className="h-[2.25rem] w-[2.25rem]" strokeWidth={1.25} />
      </div>
    </div>
  )
})

interface DetailContentProps {
  score: ScorecardData
  isFullWidth: boolean
  onToggleFullWidth?: () => void
  onClose?: () => void
  onEdit?: () => void
  onViewData?: () => void
  isEditing?: boolean
  onEditChange?: (changes: Partial<ScorecardData>) => void
  onAddSection?: () => void
  onMoveSection?: (index: number, direction: 'up' | 'down') => void
  onDeleteSection?: (index: number) => void
  onSave?: () => void
  onCancel?: () => void
  hasChanges?: boolean
}

const DetailContent = React.memo(({ 
  score,
  isFullWidth,
  onToggleFullWidth,
  onClose,
  onEdit,
  onViewData,
  isEditing,
  onEditChange,
  onAddSection,
  onMoveSection,
  onDeleteSection,
  onSave,
  onCancel,
  hasChanges
}: DetailContentProps) => {
  return (
    <div className="space-y-4 px-1">
      <div className="flex justify-between items-start">
        <div className="space-y-2 flex-1">
          <Input
            value={score.name}
            onChange={(e) => onEditChange?.({ name: e.target.value })}
            className="text-lg font-semibold bg-background border-0 px-2 h-auto 
                     focus-visible:ring-0 focus-visible:ring-offset-0 
                     placeholder:text-muted-foreground rounded-md"
            placeholder="Scorecard Name"
          />
          <div className="flex gap-4">
            <Input
              value={score.key}
              onChange={(e) => onEditChange?.({ key: e.target.value })}
              className="font-mono bg-background border-0 px-2 h-auto 
                       focus-visible:ring-0 focus-visible:ring-offset-0 
                       placeholder:text-muted-foreground rounded-md"
              placeholder="scorecard-key"
            />
            <Input
              value={score.externalId ?? ''}
              onChange={(e) => onEditChange?.({ externalId: e.target.value })}
              className="font-mono bg-background border-0 px-2 h-auto 
                       focus-visible:ring-0 focus-visible:ring-offset-0 
                       placeholder:text-muted-foreground rounded-md"
              placeholder="External ID"
            />
          </div>
          <p className="text-sm text-muted-foreground">{score.description}</p>
        </div>
        <div className="flex gap-2">
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
                {onViewData && (
                  <DropdownMenu.Item 
                    className="relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50"
                    onSelect={onViewData}
                  >
                    <Database className="mr-2 h-4 w-4" />
                    View Data
                  </DropdownMenu.Item>
                )}
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
        <div className="flex justify-end gap-2 mt-4">
          <Button variant="outline" onClick={onCancel}>Cancel</Button>
          <Button onClick={onSave}>Save Changes</Button>
        </div>
      )}

      <div className="space-y-6">
        {score.sections?.items?.map((section, index) => (
          <div key={section.id} className="space-y-2">
            <div className="flex justify-between items-center">
              <EditableField
                value={section.name}
                onChange={(value) => {
                  const updatedSections = [...(score.sections?.items || [])]
                  updatedSections[index] = { ...section, name: value }
                  onEditChange?.({ sections: { items: updatedSections } })
                }}
                className="text-sm font-medium text-muted-foreground"
              />
              <div className="flex items-center gap-2">
                <CardButton
                  icon={X}
                  onClick={() => onDeleteSection?.(index)}
                />
                <CardButton
                  icon={ChevronUp}
                  onClick={() => onMoveSection?.(index, 'up')}
                />
                <CardButton
                  icon={ChevronDown}
                  onClick={() => onMoveSection?.(index, 'down')}
                />
                <CardButton
                  icon={Plus}
                  label="Create Score"
                  onClick={() => {}}
                />
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
              {section.scores?.items?.map((score) => (
                <ScoreItem
                  key={score.id}
                  score={{
                    ...score,
                    sectionId: section.id,
                    accuracy: 0,
                    version: '',
                    timestamp: new Date(),
                    metadata: {
                      configuration: score.configuration,
                      distribution: [],
                      versionHistory: [],
                      isFineTuned: false
                    }
                  }}
                  scorecardId={score.id}
                  onEdit={() => undefined}
                />
              ))}
            </div>
          </div>
        ))}
        <div className="flex justify-end">
          <CardButton
            icon={Plus}
            label="Create Section"
            onClick={() => onAddSection?.()}
          />
        </div>
      </div>
    </div>
  )
})

export default function ScorecardCard({ 
  score, 
  onEdit, 
  onViewData, 
  variant = 'grid', 
  isSelected,
  onClick,
  isFullWidth = false,
  onToggleFullWidth,
  onClose,
  onSave,
  className, 
  ...props 
}: ScorecardCardProps) {
  const [editedScore, setEditedScore] = React.useState<ScorecardData>(score)
  const [hasChanges, setHasChanges] = React.useState(false)

  React.useEffect(() => {
    setEditedScore(score)
  }, [score])

  const handleEditChange = (changes: Partial<ScorecardData>) => {
    setEditedScore(prev => {
      const updated = { ...prev, ...changes }
      // Only set hasChanges if name, key, or externalId were changed
      if ('name' in changes || 'key' in changes || 'externalId' in changes) {
        setHasChanges(true)
      }
      return updated
    })
  }

  const handleAddSection = () => {
    const maxOrder = Math.max(0, ...(editedScore.sections?.items || []).map(s => s.order))
    const newSection = {
      id: `temp_${Date.now()}`,
      name: "New section",
      order: maxOrder + 1,
      scores: { items: [] }
    }
    setEditedScore(prev => ({
      ...prev,
      sections: {
        items: [...(prev.sections?.items || []), newSection]
      }
    }))
  }

  const handleMoveSection = (index: number, direction: 'up' | 'down') => {
    if (!editedScore.sections?.items) return

    const newSections = [...editedScore.sections.items]
    const newIndex = direction === 'up' ? index - 1 : index + 1
    
    if (newIndex < 0 || newIndex >= newSections.length) return
    
    const temp = newSections[index]
    newSections[index] = newSections[newIndex]
    newSections[newIndex] = temp
    
    newSections[index].order = index
    newSections[newIndex].order = newIndex
    
    setEditedScore(prev => ({
      ...prev,
      sections: { items: newSections }
    }))
  }

  const handleDeleteSection = (sectionIndex: number) => {
    if (!editedScore.sections?.items) return

    const updatedSections = [...editedScore.sections.items]
    updatedSections.splice(sectionIndex, 1)
    updatedSections.forEach((section, index) => {
      section.order = index
    })

    setEditedScore(prev => ({
      ...prev,
      sections: { items: updatedSections }
    }))
  }

  const handleSave = async () => {
    try {
      await amplifyClient.Scorecard.update({
        id: editedScore.id,
        name: editedScore.name,
        key: editedScore.key,
        externalId: editedScore.externalId,
        description: editedScore.description
      })

      setHasChanges(false)
      onSave?.()
    } catch (error) {
      console.error('Error saving scorecard:', error)
    }
  }

  const handleCancel = () => {
    setEditedScore(score)
    setHasChanges(false)
  }

  return (
    <div
      className={cn(
        "w-full rounded-lg bg-card text-card-foreground hover:bg-accent/50 transition-colors",
        isSelected && "bg-accent",
        className
      )}
      {...props}
    >
      <div className="flex justify-between items-start p-4">
        <div 
          className={cn(
            "flex-1",
            variant === 'grid' && "cursor-pointer"
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
              onViewData={onViewData}
              onEditChange={handleEditChange}
              onAddSection={handleAddSection}
              onMoveSection={handleMoveSection}
              onDeleteSection={handleDeleteSection}
              onSave={handleSave}
              onCancel={handleCancel}
              hasChanges={hasChanges}
            />
          )}
        </div>
      </div>
    </div>
  )
} 