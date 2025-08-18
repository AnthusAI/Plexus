import React, { useCallback, useState } from 'react'
import { Task, TaskHeader, TaskContent } from '@/components/Task'
import { BaseTaskData } from '@/types/base'
import { Card, CardContent } from '@/components/ui/card'
import { FileCode2, MoreHorizontal, Square, X, Trash2, Columns2, Edit, Copy, FileText, ChevronRight, ChevronDown } from 'lucide-react'
import { Timestamp } from './ui/timestamp'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { toast } from 'sonner'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import Editor from "@monaco-editor/react"
import type { Schema } from "@/amplify/data/resource"
import { defineCustomMonacoThemes, applyMonacoTheme, setupMonacoThemeWatcher, getCommonMonacoOptions, configureYamlLanguage } from "@/lib/monaco-theme"

// Define the template data type
export interface TemplateTaskData extends BaseTaskData {
  id: string
  name: string
  description?: string
  template: string
  version: string
  category?: string
  isDefault?: boolean
  createdAt: string
  updatedAt: string
}

export interface TemplateTaskProps {
  variant: 'grid' | 'detail'
  template: TemplateTaskData
  onClick?: () => void
  controlButtons?: React.ReactNode
  isFullWidth?: boolean
  onToggleFullWidth?: () => void
  onClose?: () => void
  isSelected?: boolean
  onDelete?: (templateId: string) => void
  onEdit?: (templateId: string) => void
  onDuplicate?: (templateId: string) => void
  onSave?: (templateId: string, updates: Partial<TemplateTaskData>) => void
  isEditing?: boolean
}

export default function TemplateTask({
  variant,
  template,
  onClick,
  controlButtons,
  isFullWidth = false,
  onToggleFullWidth,
  onClose,
  isSelected = false,
  onDelete,
  onEdit,
  onDuplicate,
  onSave,
  isEditing = false
}: TemplateTaskProps) {
  const [editedTemplate, setEditedTemplate] = useState(template.template)
  const [editedName, setEditedName] = useState(template.name)
  const [editedDescription, setEditedDescription] = useState(template.description || '')
  const [editedVersion, setEditedVersion] = useState(template.version)
  const [editedCategory, setEditedCategory] = useState(template.category || '')
  const [isSaving, setIsSaving] = useState(false)

  // Function to handle template deletion with confirmation
  const handleDelete = useCallback(async () => {
    if (!onDelete) return
    
    const confirmed = window.confirm(`Are you sure you want to delete template "${template.name}"? This action cannot be undone.`)
    if (confirmed) {
      try {
        onDelete(template.id)
      } catch (error) {
        console.error('Error deleting template:', error)
        toast.error('Failed to delete template')
      }
    }
  }, [onDelete, template.id, template.name])

  const handleSave = useCallback(async () => {
    if (!onSave) return
    
    setIsSaving(true)
    try {
      await onSave(template.id, {
        name: editedName,
        description: editedDescription,
        template: editedTemplate,
        version: editedVersion,
        category: editedCategory
      })
      toast.success('Template saved successfully')
    } catch (error) {
      console.error('Error saving template:', error)
      toast.error('Failed to save template')
    } finally {
      setIsSaving(false)
    }
  }, [onSave, template.id, editedName, editedDescription, editedTemplate, editedVersion, editedCategory])

  const handleCancel = useCallback(() => {
    setEditedTemplate(template.template)
    setEditedName(template.name)
    setEditedDescription(template.description || '')
    setEditedVersion(template.version)
    setEditedCategory(template.category || '')
    if (onEdit) {
      onEdit('') // Signal to exit edit mode
    }
  }, [template, onEdit])

  // Create action buttons dropdown for both grid and detail views
  const headerContent = (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 rounded-md border-0 shadow-none bg-border"
          aria-label="More options"
        >
          <MoreHorizontal className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {onEdit && (
          <DropdownMenuItem onSelect={() => {
            onEdit(template.id);
          }}>
            <Edit className="mr-2 h-4 w-4" />
            Edit
          </DropdownMenuItem>
        )}
        {onDuplicate && (
          <DropdownMenuItem onSelect={() => {
            onDuplicate(template.id);
          }}>
            <Copy className="mr-2 h-4 w-4" />
            Duplicate
          </DropdownMenuItem>
        )}
        {onDelete && (
          <DropdownMenuItem onSelect={handleDelete} className="text-destructive">
            <Trash2 className="mr-2 h-4 w-4" />
            Delete
          </DropdownMenuItem>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )

  // Convert template to task data format
  const taskData = {
    id: template.id,
    type: 'Template',
    name: template.name,
    description: template.description,
    scorecard: template.category || 'Unknown',
    score: template.version,
    time: template.updatedAt
  }

  const renderHeader = () => (
    <TaskHeader
      variant={variant}
      task={taskData}
      controlButtons={headerContent}
      isFullWidth={isFullWidth}
      onToggleFullWidth={onToggleFullWidth}
      onClose={onClose}
    />
  )

  const renderContent = () => (
    <TaskContent variant={variant} task={taskData}>
      {variant === 'grid' ? (
        // Grid content shows basic info
        <div className="px-3 pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {template.isDefault && (
                <Badge variant="default" className="text-xs">Default</Badge>
              )}
              <Badge variant="outline" className="text-xs">
                v{template.version}
              </Badge>
            </div>
            <div className="text-xs text-muted-foreground">
              {template.category || 'Unknown'}
            </div>
          </div>
        </div>
      ) : (
        <div className="p-3">
          {isEditing ? (
            // Edit mode
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Name</label>
                  <input
                    type="text"
                    value={editedName}
                    onChange={(e) => setEditedName(e.target.value)}
                    className="w-full px-3 py-2 border rounded-md text-sm"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Version</label>
                  <input
                    type="text"
                    value={editedVersion}
                    onChange={(e) => setEditedVersion(e.target.value)}
                    className="w-full px-3 py-2 border rounded-md text-sm"
                  />
                </div>
              </div>
              
              <div className="space-y-2">
                <label className="text-sm font-medium">Description</label>
                <textarea
                  value={editedDescription}
                  onChange={(e) => setEditedDescription(e.target.value)}
                  className="w-full px-3 py-2 border rounded-md text-sm"
                  rows={3}
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">Category</label>
                <select
                  value={editedCategory}
                  onChange={(e) => setEditedCategory(e.target.value)}
                  className="w-full px-3 py-2 border rounded-md text-sm"
                >
                  <option value="hypothesis_generation">Hypothesis Generation</option>
                  <option value="beam_search">Beam Search</option>
                  <option value="custom">Custom</option>
                </select>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">Template Code</label>
                <div className="border rounded-md overflow-hidden">
                  <Editor
                    height="400px"
                    defaultLanguage="yaml"
                    value={editedTemplate}
                    onChange={(value) => setEditedTemplate(value || '')}
                    onMount={(editor, monaco) => {
                      defineCustomMonacoThemes(monaco)
                      applyMonacoTheme(monaco)
                      setupMonacoThemeWatcher(monaco)
                    }}
                    options={{
                      minimap: { enabled: false },
                      scrollBeyondLastLine: false,
                      fontSize: 13,
                      wordWrap: 'on',
                      automaticLayout: true
                    }}
                  />
                </div>
              </div>

              <div className="flex gap-2">
                <Button onClick={handleSave} disabled={isSaving}>
                  {isSaving ? 'Saving...' : 'Save Changes'}
                </Button>
                <Button variant="outline" onClick={handleCancel}>
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            // View mode
            <div className="space-y-6">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <div className="font-medium text-muted-foreground mb-1">Version</div>
                  <div>{template.version}</div>
                </div>
                <div>
                  <div className="font-medium text-muted-foreground mb-1">Category</div>
                  <div>{template.category || 'Unknown'}</div>
                </div>
              </div>

              {template.description && (
                <div>
                  <div className="font-medium text-muted-foreground mb-1 text-sm">Description</div>
                  <div className="text-sm text-muted-foreground">{template.description}</div>
                </div>
              )}

              {/* Template Code section */}
              <Accordion type="multiple" className="w-full">
                <AccordionItem value="template-code" className="border-b-0">
                  <AccordionTrigger className="hover:no-underline py-2 px-0 justify-start [&>svg]:hidden group">
                    <div className="flex items-center gap-2">
                      <FileCode2 className="h-3 w-3 text-muted-foreground" />
                      <span className="text-sm font-medium leading-none text-muted-foreground">Template Code</span>
                      <ChevronRight className="h-3 w-3 text-muted-foreground transition-transform duration-200 group-data-[state=open]:hidden" />
                      <ChevronDown className="h-3 w-3 text-muted-foreground transition-transform duration-200 hidden group-data-[state=open]:block" />
                    </div>
                  </AccordionTrigger>
                  <AccordionContent className="pt-0 pb-4">
                    <div className="overflow-hidden">
                      <div className="border rounded-md overflow-hidden">
                        <Editor
                          height="400px"
                          defaultLanguage="yaml"
                          value={template.template}
                          options={{
                            readOnly: true,
                            minimap: { enabled: false },
                            scrollBeyondLastLine: false,
                            fontSize: 13,
                            wordWrap: 'on',
                            automaticLayout: true
                          }}
                          onMount={(editor, monaco) => {
                            defineCustomMonacoThemes(monaco)
                            applyMonacoTheme(monaco)
                            setupMonacoThemeWatcher(monaco)
                          }}
                        />
                      </div>
                    </div>
                  </AccordionContent>
                </AccordionItem>
              </Accordion>

              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <span>Created: <Timestamp date={template.createdAt} /></span>
                <span>•</span>
                <span>Modified: <Timestamp date={template.updatedAt} /></span>
              </div>
            </div>
          )}
        </div>
      )}
    </TaskContent>
  )

  return (
    <Task
      variant={variant}
      task={taskData}
      renderHeader={renderHeader}
      renderContent={renderContent}
      onClick={onClick}
      isSelected={isSelected}
      isFullWidth={isFullWidth}
    />
  )
}