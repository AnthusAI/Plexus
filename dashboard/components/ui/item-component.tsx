import * as React from 'react'
import { Card } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { MoreHorizontal, X, Square, Columns2, FileStack, ChevronDown, ChevronUp, Award, FileCode, Minimize, Maximize, ArrowDownWideNarrow, Expand, Shrink, File, Calendar, User } from 'lucide-react'
import { CardButton } from '@/components/CardButton'
import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { generateClient } from 'aws-amplify/api'
import { toast } from 'sonner'
import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { MetadataEditor } from './metadata-editor'

const client = generateClient();

export interface ItemData {
  id: string
  externalId?: string
  description?: string
  text?: string
  metadata?: Record<string, string> | null
  attachedFiles?: string[]
  accountId?: string
  scoreId?: string
  evaluationId?: string
  isEvaluation?: boolean
  createdAt?: string
  updatedAt?: string
}

interface ItemComponentProps extends React.HTMLAttributes<HTMLDivElement> {
  item: ItemData
  variant?: 'grid' | 'detail'
  isSelected?: boolean
  onClick?: () => void
  onClose?: () => void
  onToggleFullWidth?: () => void
  isFullWidth?: boolean
  onSave?: (item: ItemData) => Promise<void>
  onEdit?: () => void
  readOnly?: boolean
}

interface DetailContentProps {
  item: ItemData
  isFullWidth: boolean
  onToggleFullWidth?: () => void
  onClose?: () => void
  onEditChange?: (changes: Partial<ItemData>) => void
  onSave?: (item: ItemData) => Promise<void>
  onCancel?: () => void
  hasChanges?: boolean
  readOnly?: boolean
  isSaving?: boolean
}

const GridContent = React.memo(({ 
  item,
  isSelected 
}: { 
  item: ItemData
  isSelected?: boolean
}) => {
  // Pre-compute all displayed values to ensure stable rendering
  const displayData = React.useMemo(() => ({
    externalId: item.externalId || 'No ID',
    description: item.description || 'No description',
    text: item.text ? `${item.text.substring(0, 100)}${item.text.length > 100 ? '...' : ''}` : 'No content'
  }), [item.externalId, item.description, item.text]);
  
  return (
    <div className="flex justify-between items-start">
      <div className="space-y-2 min-h-[4.5rem] flex-1">
        <div className="font-medium text-sm">{displayData.externalId}</div>
        {displayData.description && (
          <div className="text-sm text-muted-foreground">{displayData.description}</div>
        )}
        <div className="text-xs text-muted-foreground">{displayData.text}</div>
      </div>
      <div className="text-muted-foreground ml-2">
        <File className="h-4 w-4" />
      </div>
    </div>
  )
})

const DetailContent = React.memo(({
  item,
  isFullWidth,
  onToggleFullWidth,
  onClose,
  onEditChange,
  onSave,
  onCancel,
  hasChanges,
  readOnly = false,
  isSaving = false
}: DetailContentProps) => {
  // Local state for form fields
  const [formData, setFormData] = React.useState({
    externalId: item.externalId || '',
    description: item.description || '',
    text: item.text || '',
    metadata: item.metadata || {},
    attachedFiles: item.attachedFiles || []
  })

  // Update form data when item changes
  React.useEffect(() => {
    setFormData({
      externalId: item.externalId || '',
      description: item.description || '',
      text: item.text || '',
      metadata: item.metadata || {},
      attachedFiles: item.attachedFiles || []
    })
  }, [item])

  // Handle form field changes
  const handleFormChange = (field: keyof typeof formData, value: any) => {
    if (readOnly) return
    
    const newFormData = { ...formData, [field]: value }
    setFormData(newFormData)
    onEditChange?.({ [field]: value })
  }

  // Handle metadata changes
  const handleMetadataChange = (metadata: Record<string, string>) => {
    handleFormChange('metadata', metadata)
  }

  // Handle file attachment changes
  const handleFileChange = (index: number, value: string) => {
    const newFiles = [...formData.attachedFiles]
    newFiles[index] = value
    handleFormChange('attachedFiles', newFiles)
  }

  const addFile = () => {
    const newFiles = [...formData.attachedFiles, '']
    handleFormChange('attachedFiles', newFiles)
  }

  const removeFile = (index: number) => {
    const newFiles = formData.attachedFiles.filter((_, i) => i !== index)
    handleFormChange('attachedFiles', newFiles)
  }

  // Handle save
  const handleSaveClick = async () => {
    if (onSave && !isSaving) {
      // Basic validation for new items
      if (!item.id && !formData.text && !formData.externalId && !formData.description) {
        toast.error('Please provide at least an External ID, Description, or Text Content before saving')
        return
      }
      
      try {
        await onSave({
          ...item,
          ...formData
        })
        
        // Show appropriate success message based on whether it's a new item or update
        if (item.id) {
          toast.success('Item updated successfully')
        } else {
          toast.success('Item created successfully! You can now reference it in scorecards.')
        }
      } catch (error) {
        console.error('Error saving item:', error)
        const errorMessage = error instanceof Error ? error.message : 'Failed to save item'
        toast.error(errorMessage)
      }
    }
  }

  return (
    <div className="w-full flex flex-col min-h-0">
      {/* Header */}
      <div className="flex items-center justify-between w-full">
        <div className="flex items-center space-x-2 flex-1">
          <File className="h-5 w-5 text-muted-foreground" />
          <h2 className="text-lg font-semibold">
            {item.id ? 'Edit Item' : 'New Item'}
          </h2>
        </div>
        <div className="flex items-center space-x-2 ml-4">
          {hasChanges && !readOnly && (
            <>
              <CardButton
                label="Cancel"
                onClick={() => onCancel?.()}
                aria-label="Cancel changes"
                disabled={isSaving}
              />
              <CardButton
                label={isSaving ? "Saving..." : "Save"}
                variant="primary"
                onClick={handleSaveClick}
                aria-label="Save changes"
                disabled={isSaving}
              />
            </>
          )}
          {onToggleFullWidth && (
            <CardButton
              icon={isFullWidth ? Columns2 : Square}
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

      {/* Content */}
      <div className="flex-1 overflow-y-auto mt-6 w-full">
        <div className="space-y-6 w-full">
          <div className="space-y-2">
            <Label htmlFor="externalId">External ID</Label>
            <Input
              id="externalId"
              value={formData.externalId}
              onChange={(e) => handleFormChange('externalId', e.target.value)}
              placeholder="Enter external identifier"
              className="bg-background border-0"
              disabled={readOnly}
            />
          </div>
          
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Label htmlFor="description" className="text-muted-foreground">Description</Label>
              <span className="text-[10px] text-muted-foreground/60">optional</span>
            </div>
            <Input
              id="description"
              value={formData.description}
              onChange={(e) => handleFormChange('description', e.target.value)}
              placeholder="Brief description of the item"
              className="bg-background border-0"
              disabled={readOnly}
            />
          </div>

          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Label htmlFor="text" className="text-muted-foreground">Text Content</Label>
              <span className="text-[10px] text-muted-foreground/60">optional</span>
            </div>
            <div className="text-xs text-muted-foreground/70 -mt-1 mb-2">
              For text-based items like emails, transcripts, or chat logs
            </div>
            <Textarea
              id="text"
              value={formData.text}
              onChange={(e) => handleFormChange('text', e.target.value)}
              placeholder="Enter the main content of the item"
              className="min-h-[200px] resize-none bg-background border-0"
              disabled={readOnly}
            />
          </div>

          <div className="space-y-4">
            <MetadataEditor
              value={formData.metadata}
              onChange={handleMetadataChange}
              disabled={readOnly}
              keyPlaceholder="Metadata key"
              valuePlaceholder="Metadata value"
            />
          </div>

          <div className="space-y-4">
            <div className="flex items-start justify-between">
              <div className="flex flex-col gap-1">
                <div className="flex items-center gap-2">
                  <Label className="text-muted-foreground">Attached Files</Label>
                  <span className="text-[10px] text-muted-foreground/60">optional</span>
                </div>
                <div className="text-xs text-muted-foreground/70">
                  For any type of files: documents, audio, images, or data files
                </div>
              </div>
              {!readOnly && (
                <CardButton
                  label="Add File"
                  onClick={addFile}
                  aria-label="Add file"
                />
              )}
            </div>
            
            {formData.attachedFiles.length > 0 ? (
              <div className="space-y-2">
                {formData.attachedFiles.map((file, index) => (
                  <div key={index} className="flex items-center space-x-2">
                    <Input
                      value={file}
                      onChange={(e) => handleFileChange(index, e.target.value)}
                      placeholder="File path or URL"
                      className="bg-background border-0"
                      disabled={readOnly}
                    />
                    {!readOnly && (
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => removeFile(index)}
                        className="h-8 w-8 text-muted-foreground hover:text-destructive"
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-6 text-muted-foreground bg-muted/30 rounded-md">
                No attached files
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
})

export function ItemComponent({
  item,
  variant = 'grid',
  isSelected,
  onClick,
  onClose,
  onToggleFullWidth,
  isFullWidth = false,
  onSave,
  onEdit,
  readOnly = false,
  className,
  ...props
}: ItemComponentProps) {
  // State for tracking changes and loading
  const [hasChanges, setHasChanges] = useState(false)
  const [editingItem, setEditingItem] = useState<ItemData>(item)
  const [isSaving, setIsSaving] = useState(false)

  // Update editing item when prop changes
  useEffect(() => {
    setEditingItem(item)
    setHasChanges(false)
  }, [item])

  // Handle edit changes
  const handleEditChange = (changes: Partial<ItemData>) => {
    setEditingItem(prev => ({ ...prev, ...changes }))
    setHasChanges(true)
  }

  // Handle cancel
  const handleCancel = () => {
    setEditingItem(item)
    setHasChanges(false)
  }

  // Handle save
  const handleSave = async (itemToSave: ItemData) => {
    if (onSave && !isSaving) {
      setIsSaving(true)
      try {
        await onSave(itemToSave)
        setHasChanges(false)
      } catch (error) {
        // Error handling is done in the DetailContent component
        throw error
      } finally {
        setIsSaving(false)
      }
    }
  }

  if (variant === 'grid') {
    return (
      <Card 
        className={cn(
          "h-fit cursor-pointer transition-all duration-200 hover:shadow-md",
          isSelected && "ring-2 ring-primary ring-offset-2",
          className
        )}
        onClick={onClick}
        {...props}
      >
        <div className="p-4">
          <GridContent item={item} isSelected={isSelected} />
        </div>
      </Card>
    )
  }

  // Detail variant - now matches the card pattern used by other components
  return (
    <div
      className={cn(
        "w-full rounded-lg text-card-foreground hover:bg-accent/50 transition-colors bg-card-selected h-full flex flex-col",
        className
      )}
      {...props}
    >
      <div className="p-4 w-full flex-1 flex flex-col min-h-0">
        <div className="w-full h-full flex flex-col min-h-0">
          <DetailContent
            item={editingItem}
            isFullWidth={isFullWidth}
            onToggleFullWidth={onToggleFullWidth}
            onClose={onClose}
            onEditChange={handleEditChange}
            onSave={handleSave}
            onCancel={handleCancel}
            hasChanges={hasChanges}
            readOnly={readOnly}
            isSaving={isSaving}
          />
        </div>
      </div>
    </div>
  )
} 