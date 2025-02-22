import * as React from 'react'
import { Card } from '@/components/ui/card'
import { MoreHorizontal, Pencil, Database, ListTodo, X, Square, RectangleVertical, Plus, ChevronUp, ChevronDown, CheckSquare } from 'lucide-react'
import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { cn } from '@/lib/utils'
import { CardButton } from '@/components/CardButton'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { EditableField } from '@/components/ui/editable-field'
import { amplifyClient } from '@/utils/amplify-client'
import { generateClient } from '@aws-amplify/api'
import type { Schema } from '@/amplify/data/resource'
import NestedScorecardCard from './ScorecardCard'
import { toast } from "sonner";

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
  icon?: React.ReactNode
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
  onScoreSelect?: (score: any, sectionId: string) => void
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
        {score.icon || <ListTodo className="h-[2.25rem] w-[2.25rem]" strokeWidth={1.25} />}
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
  onScoreSelect?: (score: any, sectionId: string) => void
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
  hasChanges,
  onScoreSelect
}: DetailContentProps) => {
  const [editingSectionId, setEditingSectionId] = React.useState<string | null>(null)
  const [sectionNameChanges, setSectionNameChanges] = React.useState<Record<string, string>>({})

  const handleSectionNameChange = (sectionId: string, newName: string) => {
    setSectionNameChanges(prev => ({
      ...prev,
      [sectionId]: newName
    }))
    setEditingSectionId(sectionId)
  }

  const handleSectionNameSave = (section: {
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
  }, index: number) => {
    const updatedSections = [...(score.sections?.items || [])]
    updatedSections[index] = { ...section, name: sectionNameChanges[section.id] || section.name }
    onEditChange?.({ sections: { items: updatedSections } })
    setEditingSectionId(null)
    setSectionNameChanges(prev => {
      const { [section.id]: _, ...rest } = prev
      return rest
    })
  }

  const handleSectionNameCancel = (sectionId: string) => {
    setEditingSectionId(null)
    setSectionNameChanges(prev => {
      const { [sectionId]: _, ...rest } = prev
      return rest
    })
  }

  const handleDeleteSectionClick = (section: {
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
  }, index: number) => {
    console.log('Delete section clicked:', { section, index })
    const scoreCount = section.scores?.items?.length || 0
    console.log('Score count:', scoreCount)
    if (scoreCount > 0) {
      console.log('Showing toast for non-empty section')
      toast.error(`Cannot delete "${section.name}" because it contains ${scoreCount} score${scoreCount === 1 ? '' : 's'}. Please remove all scores first.`)
      return
    }
    console.log('Calling onDeleteSection with index:', index)
    onDeleteSection?.(index)
  }

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
            placeholder="Scorecard Name"
          />
          <div className="flex gap-4 w-full">
            <Input
              value={score.key}
              onChange={(e) => onEditChange?.({ key: e.target.value })}
              className="font-mono bg-background border-0 px-2 h-auto flex-1
                       focus-visible:ring-0 focus-visible:ring-offset-0 
                       placeholder:text-muted-foreground rounded-md"
              placeholder="scorecard-key"
            />
            <Input
              value={score.externalId ?? ''}
              onChange={(e) => onEditChange?.({ externalId: e.target.value })}
              className="font-mono bg-background border-0 px-2 h-auto flex-1
                       focus-visible:ring-0 focus-visible:ring-offset-0 
                       placeholder:text-muted-foreground rounded-md"
              placeholder="External ID"
            />
          </div>
          <p className="text-sm text-muted-foreground">{score.description}</p>
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

      <div className="flex-1 overflow-y-auto mt-6 w-full">
        <div className="space-y-6 w-full">
          {score.sections?.items?.map((section, index) => (
            <div key={section.id} className="space-y-2 w-full">
              <div className="flex justify-between items-center w-full">
                <div className="flex-1">
                  <Input
                    value={sectionNameChanges[section.id] ?? section.name}
                    onChange={(e) => handleSectionNameChange(section.id, e.target.value)}
                    className="text-base font-semibold bg-background border-0 px-2 py-1 h-auto w-full
                             focus-visible:ring-0 focus-visible:ring-offset-0 
                             placeholder:text-muted-foreground rounded-md"
                    placeholder="Section Name"
                  />
                </div>
                <div className="flex items-center gap-2 ml-4">
                  {editingSectionId === section.id && (
                    <>
                      <Button 
                        variant="outline" 
                        size="sm" 
                        onClick={() => handleSectionNameCancel(section.id)}
                      >
                        Cancel
                      </Button>
                      <Button 
                        size="sm" 
                        onClick={() => handleSectionNameSave(section, index)}
                      >
                        Save
                      </Button>
                    </>
                  )}
                  <CardButton
                    icon={X}
                    onClick={() => handleDeleteSectionClick(section, index)}
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
              <div className="bg-background rounded-lg p-4 w-full">
                <div className="@container w-full">
                  <div className="grid grid-cols-1 @[400px]:grid-cols-1 @[600px]:grid-cols-2 @[900px]:grid-cols-3 gap-2 w-full">
                    {section.scores?.items?.map((score) => (
                      <NestedScorecardCard
                        key={score.id}
                        variant="grid"
                        score={{
                          id: score.id,
                          name: score.name,
                          key: score.key,
                          description: score.description || '',
                          type: score.type,
                          configuration: score.configuration,
                          order: score.order,
                          externalId: '',
                          icon: <CheckSquare className="h-[2.25rem] w-[2.25rem]" strokeWidth={1.25} />
                        }}
                        onClick={() => onScoreSelect?.(score, section.id)}
                      />
                    ))}
                  </div>
                </div>
              </div>
            </div>
          ))}
          <div className="flex justify-end w-full">
            <CardButton
              icon={Plus}
              label="Create Section"
              onClick={() => onAddSection?.()}
            />
          </div>
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
  onScoreSelect,
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
        variant === 'detail' && "h-full flex flex-col",
        isSelected && "bg-accent",
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
              onViewData={onViewData}
              onEditChange={handleEditChange}
              onAddSection={handleAddSection}
              onMoveSection={handleMoveSection}
              onDeleteSection={handleDeleteSection}
              onSave={handleSave}
              onCancel={handleCancel}
              hasChanges={hasChanges}
              onScoreSelect={onScoreSelect}
            />
          )}
        </div>
      </div>
    </div>
  )
} 