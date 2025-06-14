'use client'

import React, { useState, useCallback } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { FileText, Upload, Trash2, ExternalLink, Plus, Loader2, AlertCircle, Eye, X, MoreHorizontal } from 'lucide-react'
import { cn } from '@/lib/utils'
import { CardButton } from '@/components/CardButton'
import { toast } from 'sonner'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import ParquetViewer from '@/components/ui/ParquetViewer'
import FileContentViewer from '@/components/ui/FileContentViewer'
import * as DropdownMenu from '@radix-ui/react-dropdown-menu'

export interface FileAttachmentsProps {
  attachedFiles?: string[]
  readOnly?: boolean
  onChange?: (files: string[]) => void
  onUpload?: (file: File) => Promise<string>
  className?: string
  maxFiles?: number
  allowedTypes?: string[]
}

interface FileEntry {
  id: string
  path: string
  isUploading?: boolean
  error?: string
}

const generateId = () => Math.random().toString(36).substr(2, 9)

const isValidUrl = (string: string) => {
  try {
    new URL(string)
    return true
  } catch (_) {
    return false
  }
}

const getFileNameFromPath = (path: string) => {
  if (isValidUrl(path)) {
    try {
      const url = new URL(path)
      const pathname = url.pathname
      return pathname.split('/').pop() || 'Unknown file'
    } catch {
      return 'Unknown file'
    }
  }
  return path.split('/').pop() || path
}

const getFileIcon = (fileName: string) => {
  const extension = fileName.split('.').pop()?.toLowerCase()
  
  // You can extend this with more specific icons based on file types
  switch (extension) {
    case 'pdf':
    case 'doc':
    case 'docx':
    case 'txt':
      return <FileText className="h-4 w-4" />
    default:
      return <FileText className="h-4 w-4" />
  }
}

const getFileExtension = (fileName: string) => {
  return fileName.split('.').pop()?.toLowerCase() || ''
}

const isParquetFile = (fileName: string) => {
  return getFileExtension(fileName) === 'parquet'
}

const isTextFile = (fileName: string) => {
  const textExtensions = ['txt', 'json', 'yaml', 'yml', 'csv', 'xml', 'html', 'htm', 'md', 'log']
  return textExtensions.includes(getFileExtension(fileName))
}

const isViewableFile = (fileName: string) => {
  return isParquetFile(fileName) || isTextFile(fileName)
}

export const FileAttachments = React.forwardRef<HTMLDivElement, FileAttachmentsProps>(
  ({
    attachedFiles = [],
    readOnly = false,
    onChange,
    onUpload,
    className,
    maxFiles = 10,
    allowedTypes = [], // Empty means all types allowed
    ...props
  }, ref) => {
    const [files, setFiles] = useState<FileEntry[]>(() =>
      attachedFiles.map(path => ({ id: generateId(), path }))
    )
    
    // State for file preview dialog
    const [previewFile, setPreviewFile] = useState<{ path: string; name: string } | null>(null)
    const [isPreviewOpen, setIsPreviewOpen] = useState(false)

    // Update internal state when attachedFiles prop changes
    React.useEffect(() => {
      console.log('FileAttachments useEffect - attachedFiles changed:', attachedFiles)
      const newFiles = attachedFiles.map(path => ({ id: generateId(), path }))
      console.log('FileAttachments useEffect - setting files to:', newFiles)
      setFiles(newFiles)
    }, [attachedFiles])

    const emitChange = useCallback((newFiles: FileEntry[]) => {
      if (onChange && !readOnly) {
        const paths = newFiles
          .filter(file => file.path.trim() && !file.isUploading)
          .map(file => file.path.trim())
        onChange(paths)
      }
    }, [onChange, readOnly])

    const updateFile = useCallback((id: string, path: string) => {
      if (readOnly) return

      const newFiles = files.map(file =>
        file.id === id ? { ...file, path, error: undefined } : file
      )
      setFiles(newFiles)
      emitChange(newFiles)
    }, [files, emitChange, readOnly])

    const addFile = useCallback(() => {
      console.log('addFile called', { readOnly, filesLength: files.length, maxFiles })
      if (readOnly || files.length >= maxFiles) return
      
      const newFile: FileEntry = {
        id: generateId(),
        path: ''
      }
      const newFiles = [...files, newFile]
      console.log('Adding new file, newFiles:', newFiles)
      setFiles(newFiles)
      // Don't emit change immediately for empty files - let the user fill them in first
      // emitChange will be called when they type in the input
    }, [files, maxFiles, readOnly])

    const removeFile = useCallback((id: string) => {
      if (readOnly) return

      const newFiles = files.filter(file => file.id !== id)
      setFiles(newFiles)
      emitChange(newFiles)
    }, [files, emitChange, readOnly])

    const handleFileUpload = useCallback(async (file: File, id: string) => {
      if (!onUpload || readOnly) return

      // Check file type if restrictions are set
      if (allowedTypes.length > 0 && !allowedTypes.includes(file.type)) {
        const errorMessage = `File type ${file.type} is not allowed`
        setFiles(prev => prev.map(f => 
          f.id === id ? { ...f, error: errorMessage } : f
        ))
        toast.error(errorMessage)
        return
      }

      // Set uploading state
      setFiles(prev => prev.map(f => 
        f.id === id ? { ...f, isUploading: true, error: undefined } : f
      ))

      try {
        const uploadedPath = await onUpload(file)
        
        // Update with uploaded path
        const newFiles = files.map(f =>
          f.id === id ? { ...f, path: uploadedPath, isUploading: false } : f
        )
        setFiles(newFiles)
        emitChange(newFiles)
        
        toast.success(`File "${file.name}" uploaded successfully`)
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Upload failed'
        setFiles(prev => prev.map(f => 
          f.id === id ? { ...f, isUploading: false, error: errorMessage } : f
        ))
        toast.error(errorMessage)
      }
    }, [onUpload, readOnly, allowedTypes, files, emitChange])

    const handleViewFile = useCallback((filePath: string, fileName: string) => {
      setPreviewFile({ path: filePath, name: fileName })
      setIsPreviewOpen(true)
    }, [])

    const closePreview = useCallback(() => {
      setIsPreviewOpen(false)
      setPreviewFile(null)
    }, [])

    const hasFiles = files.length > 0
    const canAddMore = !readOnly && files.length < maxFiles

    console.log('FileAttachments render:', { 
      readOnly, 
      hasFiles, 
      canAddMore, 
      filesLength: files.length, 
      maxFiles, 
      attachedFiles,
      files: files.map(f => ({ id: f.id, path: f.path }))
    })

    // In read-only mode, don't render the component at all if there are no files
    if (readOnly && !hasFiles) {
      return null
    }

    return (
      <>
        <div ref={ref} className={cn("space-y-4", className)} {...props}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium leading-none text-muted-foreground">Attached Files</span>
              {!readOnly && <span className="text-[10px] text-muted-foreground/60">optional</span>}
              {readOnly && hasFiles && <Upload className="h-3 w-3 text-muted-foreground/60" />}
            </div>
            {canAddMore && (
              <CardButton
                icon={Plus}
                label="Add File"
                onClick={addFile}
                aria-label="Add file attachment"
              />
            )}
          </div>
          
          {hasFiles ? (
            <div className="space-y-2">
              {files.map((file) => {
                // Only show files that have content in read-only mode
                if (readOnly && !file.path.trim()) {
                  return null
                }

                const fileName = getFileNameFromPath(file.path)
                const isUrl = isValidUrl(file.path)
                const canView = isViewableFile(fileName) && !isUrl // Only allow viewing for S3 files, not external URLs

                return (
                  <div key={file.id} className="space-y-2">
                    <div className="flex items-center space-x-2">
                      {readOnly ? (
                        // Read-only view: display as file links
                        <div className="flex-1 p-3">
                          <div className="flex items-center gap-3">
                            <div className="text-muted-foreground flex-shrink-0">
                              {getFileIcon(fileName)}
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="text-sm font-medium text-foreground truncate">
                                {fileName}
                              </div>
                              {isUrl && (
                                <div className="text-xs text-muted-foreground truncate">
                                  {file.path}
                                </div>
                              )}
                            </div>
                            <div className="flex gap-2">
                              {(canView || isUrl) && (
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
                                      {canView && (
                                        <DropdownMenu.Item 
                                          className="relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50"
                                          onSelect={() => handleViewFile(file.path, fileName)}
                                        >
                                          <Eye className="mr-2 h-4 w-4" />
                                          View File
                                        </DropdownMenu.Item>
                                      )}
                                      {isUrl && (
                                        <DropdownMenu.Item 
                                          className="relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50"
                                          onSelect={() => window.open(file.path, '_blank')}
                                        >
                                          <ExternalLink className="mr-2 h-4 w-4" />
                                          Open Link
                                        </DropdownMenu.Item>
                                      )}
                                    </DropdownMenu.Content>
                                  </DropdownMenu.Portal>
                                </DropdownMenu.Root>
                              )}
                            </div>
                          </div>
                        </div>
                      ) : (
                        // Edit mode: input fields and upload
                        <>
                          <div className="flex-1 space-y-2">
                            <Input
                              value={file.path}
                              onChange={(e) => updateFile(file.id, e.target.value)}
                              placeholder="File path or URL"
                              className={cn(
                                "bg-background border-0 focus-visible:ring-1 focus-visible:ring-ring",
                                file.error && "bg-destructive/10 focus-visible:ring-destructive"
                              )}
                              disabled={file.isUploading}
                            />
                            {onUpload && (
                              <div className="flex items-center gap-2">
                                <input
                                  type="file"
                                  id={`file-input-${file.id}`}
                                  className="hidden"
                                  onChange={(e) => {
                                    const selectedFile = e.target.files?.[0]
                                    if (selectedFile) {
                                      handleFileUpload(selectedFile, file.id)
                                    }
                                  }}
                                  accept={allowedTypes.length > 0 ? allowedTypes.join(',') : undefined}
                                />
                                <label htmlFor={`file-input-${file.id}`} className="flex-1">
                                  <div className="w-full p-3 cursor-pointer hover:bg-accent/50 transition-colors">
                                    <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
                                      {file.isUploading ? (
                                        <>
                                          <Loader2 className="h-4 w-4 animate-spin" />
                                          Uploading...
                                        </>
                                      ) : (
                                        <>
                                          <Upload className="h-4 w-4" />
                                          Upload File
                                        </>
                                      )}
                                    </div>
                                  </div>
                                </label>
                              </div>
                            )}
                          </div>
                          <div className="flex gap-2">
                            {canView && file.path.trim() && (
                              <CardButton
                                icon={Eye}
                                onClick={() => handleViewFile(file.path, fileName)}
                                aria-label="View file"
                              />
                            )}
                            <CardButton
                              icon={Trash2}
                              onClick={() => removeFile(file.id)}
                              aria-label="Remove file"
                              disabled={file.isUploading}
                            />
                          </div>
                        </>
                      )}
                    </div>
                    
                    {/* Show errors in edit mode */}
                    {!readOnly && file.error && (
                      <div className="flex items-center gap-2 text-xs text-destructive">
                        <AlertCircle className="h-3 w-3" />
                        {file.error}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          ) : (
            <div className="text-center py-6 text-sm text-muted-foreground">
              {readOnly ? "No attached files" : "No attached files"}
            </div>
          )}

          {/* File type restrictions info in edit mode */}
          {!readOnly && allowedTypes.length > 0 && (
            <div className="text-xs text-muted-foreground">
              Allowed file types: {allowedTypes.join(', ')}
            </div>
          )}
        </div>

        {/* File Preview Dialog */}
        <Dialog open={isPreviewOpen} onOpenChange={setIsPreviewOpen}>
          <DialogContent className="max-w-6xl max-h-[90vh] overflow-hidden flex flex-col">
            <DialogHeader>
              <div className="flex items-center justify-between">
                <DialogTitle>{previewFile?.name || 'File Preview'}</DialogTitle>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={closePreview}
                  className="h-6 w-6"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </DialogHeader>
            <div className="flex-1 overflow-auto">
              {previewFile && (
                <>
                  {isParquetFile(previewFile.name) ? (
                    <ParquetViewer 
                      filePath={previewFile.path} 
                      fileName={previewFile.name}
                    />
                  ) : isTextFile(previewFile.name) ? (
                    <FileContentViewer filePath={previewFile.path} />
                  ) : (
                    <div className="p-4 text-center text-muted-foreground">
                      Preview not available for this file type.
                    </div>
                  )}
                </>
              )}
            </div>
          </DialogContent>
        </Dialog>
      </>
    )
  }
)

FileAttachments.displayName = "FileAttachments" 