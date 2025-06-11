"use client"

import React, { useEffect, useRef, useState } from "react"
import { Calendar, HardDriveDownload, MoreHorizontal, X, Square, Columns2, FileCode, Table, Trash2, CopyPlus, Plus } from "lucide-react"
import type { Schema } from "@/amplify/data/resource"
import { formatDistanceToNow, parseISO } from "date-fns"
import { cn } from "@/lib/utils"
import { CardButton } from "@/components/CardButton"
import { Timestamp } from "@/components/ui/timestamp"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import Editor, { Monaco } from '@monaco-editor/react'
import * as monaco from 'monaco-editor'
import type { editor } from 'monaco-editor'
import { defineCustomMonacoThemes, applyMonacoTheme, setupMonacoThemeWatcher, getCommonMonacoOptions } from '@/lib/monaco-theme'
import { amplifyClient } from "@/utils/amplify-client"
import { FileAttachments } from "@/components/items/FileAttachments"
import { uploadData } from 'aws-amplify/storage'
import { toast } from 'sonner'

interface DataSourceComponentProps {
  variant: 'grid' | 'detail'
  dataSource: Schema['DataSource']['type']
  isSelected?: boolean
  onClick?: () => void
  onEdit?: () => void
  isFullWidth?: boolean
  onToggleFullWidth?: () => void
  onClose?: () => void
  onSave?: (savedDataSource?: Schema['DataSource']['type']) => void
  onDelete?: (dataSource: Schema['DataSource']['type']) => void
  onLoad?: (dataSource: Schema['DataSource']['type']) => void
  onDuplicate?: (dataSource: Schema['DataSource']['type']) => void
  dataSets?: Schema['DataSet']['type'][]
  onDataSetSelect?: (dataSet: Schema['DataSet']['type']) => void
  selectedDataSetId?: string
  accountId?: string
}

// Grid content component
const GridContent = React.memo(function GridContent({ 
  dataSource, 
  isSelected 
}: { 
  dataSource: Schema['DataSource']['type']
  isSelected?: boolean
}) {
  const isNew = dataSource.id === '' // Blank data source for creation

  return (
    <div className="flex justify-between items-start w-full">
      <div className="space-y-1.5 flex-1 min-w-0">
        <div className={cn(
          "font-medium truncate",
          isNew ? "text-muted-foreground italic" : "text-foreground"
        )}>
          {dataSource.name || 'New Data Source'}
        </div>
        {dataSource.key && (
          <div className="text-sm text-muted-foreground truncate">
            {dataSource.key}
          </div>
        )}
        {dataSource.description && (
          <div className="text-sm text-muted-foreground line-clamp-2">
            {dataSource.description}
          </div>
        )}
        {!isNew && dataSource.updatedAt && (
          <Timestamp 
            time={dataSource.updatedAt} 
            variant="relative" 
            showIcon={true}
            className="text-xs"
          />
        )}
      </div>
      <div className="text-muted-foreground ml-4">
        <HardDriveDownload className="h-[2.25rem] w-[2.25rem]" strokeWidth={1.25} />
      </div>
    </div>
  )
})

// Detail content component
const DetailContent = React.memo(function DetailContent({
  dataSource,
  isFullWidth,
  onToggleFullWidth,
  onClose,
  onSave,
  onDelete,
  onLoad,
  onDuplicate,
  onEditChange,
  hasChanges,
  onCancel,
  dataSets,
  onDataSetSelect,
  selectedDataSetId,
  accountId
}: {
  dataSource: Schema['DataSource']['type']
  isFullWidth?: boolean
  onToggleFullWidth?: () => void
  onClose?: () => void
  onSave?: (savedDataSource?: Schema['DataSource']['type']) => void
  onDelete?: (dataSource: Schema['DataSource']['type']) => void
  onLoad?: (dataSource: Schema['DataSource']['type']) => void
  onDuplicate?: (dataSource: Schema['DataSource']['type']) => void
  onEditChange?: (changes: Partial<Schema['DataSource']['type']>) => void
  hasChanges?: boolean
  onCancel?: () => void
  dataSets?: Schema['DataSet']['type'][]
  onDataSetSelect?: (dataSet: Schema['DataSet']['type']) => void
  selectedDataSetId?: string
  accountId?: string
}) {
  // Create a ref to store the Monaco instance
  const monacoRef = useRef<Monaco | null>(null)
  const editorInstanceRef = useRef<editor.IStandaloneCodeEditor | null>(null)
  
  // Add state to detect if we're on an iPad/mobile device
  const [isMobileDevice, setIsMobileDevice] = useState(false)

  // File upload handler
  const handleFileUpload = async (file: File): Promise<string> => {
    try {
      // Generate a unique file path for data sources organized by account
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-')
      const fileName = file.name.replace(/[^a-zA-Z0-9.-]/g, '_') // Sanitize filename
      const filePath = `datasources/${accountId || 'default'}/${dataSource.id || 'new'}/${timestamp}-${fileName}`
      
      // Upload to the attachments bucket
      const result = await uploadData({
        path: filePath,
        data: file,
        options: {
          onProgress: ({ transferredBytes, totalBytes }) => {
            if (totalBytes) {
              const percentage = Math.round((transferredBytes / totalBytes) * 100)
              console.log(`Upload progress: ${percentage}%`)
            }
          }
        }
      }).result
      
      // Return the path that was uploaded
      return filePath
    } catch (error) {
      console.error('File upload error:', error)
      throw new Error(error instanceof Error ? error.message : 'File upload failed')
    }
  }
  
  // Set up Monaco theme watcher
  useEffect(() => {
    if (!monacoRef.current) return
    
    const cleanup = setupMonacoThemeWatcher(monacoRef.current)
    return cleanup
  }, [monacoRef.current])
  
  // Detect mobile devices on component mount
  useEffect(() => {
    const checkMobileDevice = () => {
      const userAgent = navigator.userAgent.toLowerCase()
      const isIPad = /ipad/.test(userAgent) || 
                    (/macintosh/.test(userAgent) && 'ontouchend' in document)
      const isTablet = /tablet|ipad|playbook|silk|android(?!.*mobile)/i.test(userAgent)
      const isMobile = /iphone|ipod|android|blackberry|opera mini|opera mobi|skyfire|maemo|windows phone|palm|iemobile|symbian|symbianos|fennec/i.test(userAgent)
      
      setIsMobileDevice(isIPad || isTablet || isMobile)
    }
    
    checkMobileDevice()
  }, [])

  return (
    <div className="w-full flex flex-col min-h-0 h-full">
      {/* Header section - fixed size */}
      <div className="flex justify-between items-start w-full flex-shrink-0">
        <div className="space-y-2 flex-1">
          <Input
            value={dataSource.name}
            onChange={(e) => onEditChange?.({ name: e.target.value })}
            className="text-lg font-semibold bg-background border-0 px-2 h-auto w-full
                     focus-visible:ring-0 focus-visible:ring-offset-0 
                     placeholder:text-muted-foreground rounded-md"
            placeholder="Data Source Name"
          />
          <div className="flex gap-4 w-full">
            <Input
              value={dataSource.key || ''}
              onChange={(e) => onEditChange?.({ key: e.target.value })}
              className="font-mono bg-background border-0 px-2 h-auto flex-1
                       focus-visible:ring-0 focus-visible:ring-offset-0 
                       placeholder:text-muted-foreground rounded-md"
              placeholder="data-source-key"
            />
          </div>
          <Input
            value={dataSource.description || ''}
            onChange={(e) => onEditChange?.({ description: e.target.value })}
            className="bg-background border-0 px-2 h-auto w-full
                     focus-visible:ring-0 focus-visible:ring-offset-0 
                     placeholder:text-muted-foreground rounded-md"
            placeholder="Description"
          />
          <FileAttachments
            attachedFiles={dataSource.attachedFiles || []}
            onChange={(files) => {
              console.log('FileAttachments onChange called with:', files)
              onEditChange?.({ attachedFiles: files })
            }}
            onUpload={handleFileUpload}
            className="mt-4"
            maxFiles={5}
          />
        </div>
        <div className="flex gap-2 ml-4">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button 
                variant="ghost" 
                size="icon" 
                className="h-8 w-8 rounded-md bg-border"
                aria-label="More options"
              >
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => onLoad?.(dataSource)}>
                <HardDriveDownload className="mr-2 h-4 w-4" />
                <span>Load</span>
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onDuplicate?.(dataSource)}>
                <CopyPlus className="mr-2 h-4 w-4" />
                <span>Duplicate</span>
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onDelete?.(dataSource)}>
                <Trash2 className="mr-2 h-4 w-4" />
                <span>Delete</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          {onClose && (
            <CardButton
              icon={X}
              onClick={onClose}
              aria-label="Close"
            />
          )}
        </div>
      </div>

      {/* Configuration Label with Full Width Toggle - fixed size */}
      <div className="mt-6 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-2">
          <FileCode className="h-4 w-4 text-foreground" />
          <span className="text-sm font-medium">Configuration</span>
        </div>
        <div className="flex items-center gap-2">
          {onToggleFullWidth && (
            <CardButton
              icon={isFullWidth ? Columns2 : Square}
              onClick={onToggleFullWidth}
              aria-label={isFullWidth ? 'Exit full width' : 'Full width'}
            />
          )}
        </div>
      </div>

      {/* Main content area - flexible */}
      <div className="flex-1 flex flex-col min-h-0 mt-2">
        {/* YAML Editor - takes remaining space before datasets */}
        <div className={cn(
          "bg-background rounded-lg overflow-hidden relative min-h-[300px]",
          dataSets && dataSets.length > 0 ? "flex-1 mb-3" : "flex-1"
        )}>
          <Editor
            height="100%"
            defaultLanguage="yaml"
            value={dataSource.yamlConfiguration || ''}
            onMount={(editor, monaco) => {
              // Store the editor instance
              editorInstanceRef.current = editor
              
              // Store the Monaco instance
              monacoRef.current = monaco
              
              // Apply our custom theme when the editor mounts
              defineCustomMonacoThemes(monaco)
              applyMonacoTheme(monaco)
              
              // Force immediate layout to ensure correct sizing
              editor.layout()
              
              // Add error handling for iPad-specific issues
              window.addEventListener('error', (event) => {
                if (event.message === 'Canceled: Canceled' || 
                    event.error?.message === 'Canceled: Canceled') {
                  event.preventDefault()
                  return true // Prevent the error from propagating
                }
                return false
              })
            }}
            onChange={(value) => {
              if (!value) return
              
              try {
                // Update the YAML configuration
                onEditChange?.({ yamlConfiguration: value })
              } catch (error) {
                // Handle cancellation errors gracefully
                if (error instanceof Error && 
                    (error.message === 'Canceled' || error.message === 'Canceled: Canceled')) {
                  return // Just ignore the error
                }
                
                // Ignore other parse errors while typing
              }
            }}
            options={getCommonMonacoOptions(isMobileDevice)}
          />
        </div>

        {/* Save/Cancel buttons - fixed size */}
        {hasChanges && (
          <div className="flex justify-end gap-2 mt-4 flex-shrink-0">
            <Button variant="outline" onClick={onCancel}>Cancel</Button>
            <Button onClick={onSave}>Save Changes</Button>
          </div>
        )}

        {/* Datasets Section - fixed size, only when they exist */}
        {dataSets && dataSets.length > 0 && (
          <div className="flex-shrink-0">
            <div className="flex items-center gap-2 mb-4">
              <Table className="h-4 w-4 text-foreground" />
              <span className="text-sm font-medium">Generated Datasets ({dataSets.length})</span>
            </div>
            <div className="space-y-3">
              {dataSets.map((dataSet) => (
                <div
                  key={dataSet.id}
                  className={cn(
                    "p-3 rounded-lg cursor-pointer transition-colors",
                    selectedDataSetId === dataSet.id
                      ? "bg-selected"
                      : "bg-card hover:bg-accent"
                  )}
                  onClick={() => onDataSetSelect?.(dataSet)}
                >
                  <div className="flex justify-between items-start">
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-sm truncate">
                        {dataSet.name || `Dataset ${formatDistanceToNow(parseISO(dataSet.createdAt), { addSuffix: true })}`}
                      </div>
                      {dataSet.description && (
                        <div className="text-xs text-muted-foreground mt-1 line-clamp-2">
                          {dataSet.description}
                        </div>
                      )}
                      <div className="mt-1">
                        <Timestamp 
                          time={dataSet.createdAt} 
                          variant="relative" 
                          showIcon={true}
                          className="text-xs"
                        />
                      </div>
                    </div>
                    <Table className="h-4 w-4 text-muted-foreground ml-2 flex-shrink-0" />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
})

export default function DataSourceComponent({ 
  variant, 
  dataSource, 
  isSelected = false, 
  onClick, 
  onEdit,
  isFullWidth = false,
  onToggleFullWidth,
  onClose,
  onSave,
  onDelete,
  onLoad,
  onDuplicate,
  dataSets,
  onDataSetSelect,
  selectedDataSetId,
  accountId,
  ...props 
}: DataSourceComponentProps) {
  const [editedDataSource, setEditedDataSource] = React.useState<Schema['DataSource']['type']>(dataSource)
  const [hasChanges, setHasChanges] = React.useState(false)

  React.useEffect(() => {
    setEditedDataSource(dataSource)
  }, [dataSource])

  const handleEditChange = (changes: Partial<Schema['DataSource']['type']>) => {
    setEditedDataSource(prev => {
      const updated = { ...prev, ...changes }
      // Set hasChanges if any field was changed
      if ('name' in changes || 'key' in changes || 'description' in changes || 'yamlConfiguration' in changes || 'attachedFiles' in changes) {
        setHasChanges(true)
      }
      return updated
    })
  }

  const handleSave = async () => {
    try {
      if (editedDataSource.id === '') {
        // Create new data source
        // Validate required fields
        if (!editedDataSource.name || !editedDataSource.name.trim()) {
          console.error('Name is required for data source creation')
          return
        }
        if (!editedDataSource.accountId) {
          console.error('Account ID is required for data source creation')
          return
        }
        
        // Prepare the data, only including non-empty optional fields
        const createData: any = {
          name: editedDataSource.name.trim(),
          accountId: editedDataSource.accountId,
        }
        
        // Only add optional fields if they have values
        if (editedDataSource.key && editedDataSource.key.trim()) {
          createData.key = editedDataSource.key.trim()
        }
        if (editedDataSource.description && editedDataSource.description.trim()) {
          createData.description = editedDataSource.description.trim()
        }
        if (editedDataSource.yamlConfiguration && editedDataSource.yamlConfiguration.trim()) {
          createData.yamlConfiguration = editedDataSource.yamlConfiguration.trim()
        }
        if (editedDataSource.attachedFiles && editedDataSource.attachedFiles.length > 0) {
          createData.attachedFiles = editedDataSource.attachedFiles
        }
        if (editedDataSource.scorecardId) {
          createData.scorecardId = editedDataSource.scorecardId
        }
        if (editedDataSource.scoreId) {
          createData.scoreId = editedDataSource.scoreId
        }
        if (editedDataSource.currentVersionId) {
          createData.currentVersionId = editedDataSource.currentVersionId
        }
        
        const result = await amplifyClient.DataSource.create(createData)
        
        if (result.data) {
          // Update the component state with the new data source
          setEditedDataSource(result.data)
          setHasChanges(false)
          // Pass the created data source back to the parent
          onSave?.(result.data)
          return // Early return for successful creation
        }
      } else {
        // Update existing data source
        const result = await amplifyClient.DataSource.update({
          id: editedDataSource.id,
          name: editedDataSource.name,
          key: editedDataSource.key,
          description: editedDataSource.description,
          yamlConfiguration: editedDataSource.yamlConfiguration,
          attachedFiles: editedDataSource.attachedFiles,
          scorecardId: editedDataSource.scorecardId,
          scoreId: editedDataSource.scoreId,
          currentVersionId: editedDataSource.currentVersionId
        })
        
        if (result.data) {
          setHasChanges(false)
          // Pass the updated data source back to the parent
          onSave?.(result.data)
          return // Early return for successful update
        }
      }
      
      // Fallback - this shouldn't be reached if everything works correctly
      setHasChanges(false)
      onSave?.()
    } catch (error) {
      console.error('Error saving data source:', error)
      console.error('Error details:', JSON.stringify(error, null, 2))
    }
  }

  const handleCancel = () => {
    setEditedDataSource(dataSource)
    setHasChanges(false)
  }

  return (
    <div
      className={cn(
        "w-full rounded-lg text-card-foreground hover:bg-accent/50 transition-colors relative",
        variant === 'grid' ? (
          isSelected ? "bg-card-selected" : "bg-card"
        ) : "bg-card-selected",
        variant === 'detail' && "h-full flex flex-col",
        (isSelected && variant === 'grid') && "selected-border-rounded"
      )}
      {...props}
    >
      <div className={cn(
        "p-4 w-full relative z-10",
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
            <GridContent dataSource={editedDataSource} isSelected={isSelected} />
          ) : (
            <DetailContent 
              dataSource={editedDataSource}
              isFullWidth={isFullWidth}
              onToggleFullWidth={onToggleFullWidth}
              onClose={onClose}
              onSave={handleSave}
              onDelete={onDelete}
              onLoad={onLoad}
              onDuplicate={onDuplicate}
              onEditChange={handleEditChange}
              hasChanges={hasChanges}
              onCancel={handleCancel}
              dataSets={dataSets}
              onDataSetSelect={onDataSetSelect}
              selectedDataSetId={selectedDataSetId}
              accountId={accountId}
            />
          )}
        </div>
      </div>
    </div>
  )
}