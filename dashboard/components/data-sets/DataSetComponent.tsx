"use client"

import React from "react"
import { Calendar, FileText, Table, X, MoreHorizontal, Download, Square, Columns2, Rows3, Columns3 } from "lucide-react"
import type { Schema } from "@/amplify/data/resource"
import { formatDistanceToNow, parseISO, format } from "date-fns"
import { cn } from "@/lib/utils"
import { CardButton } from "@/components/CardButton"
import { Timestamp } from "@/components/ui/timestamp"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Button } from "@/components/ui/button"
import ParquetViewer from "@/components/ui/ParquetViewer"
import { downloadData } from 'aws-amplify/storage'

interface DataSetComponentProps {
  variant: 'grid' | 'detail'
  dataSet: Schema['DataSet']['type']
  isSelected?: boolean
  onClick?: () => void
  onClose?: () => void
  isFullWidth?: boolean
  onToggleFullWidth?: () => void
}

// Helper function to check if a file is a Parquet file
const isParquetFile = (filePath: string): boolean => {
  return filePath.toLowerCase().endsWith('.parquet')
}

// Component to display dataset information
const DatasetInfo = React.memo(function DatasetInfo({ filePath }: { filePath: string }) {
  const [info, setInfo] = React.useState<{ totalRows: number; columns: number; fileName: string } | null>(null)
  const [isLoading, setIsLoading] = React.useState(true)

  React.useEffect(() => {
    const loadParquetInfo = async () => {
      setIsLoading(true)
      try {
        // Dynamic import of hyparquet
        const { parquetMetadataAsync, parquetSchema } = await import('hyparquet')
        
        // Determine which storage bucket to use based on file path
        let storageOptions: { path: string; options?: { bucket?: string } } = { path: filePath }
        
        if (filePath.startsWith('datasources/')) {
          storageOptions = { path: filePath }
        } else if (filePath.startsWith('datasets/')) {
          storageOptions = { path: filePath }
        } else if (filePath.startsWith('reportblocks/')) {
          storageOptions = {
            path: filePath,
            options: { bucket: 'reportBlockDetails' }
          }
        } else if (filePath.startsWith('scoreresults/')) {
          storageOptions = {
            path: filePath,
            options: { bucket: 'scoreResultAttachments' }
          }
        }
        
        // Download the file data
        const downloadResult = await downloadData(storageOptions).result
        const arrayBuffer = await (downloadResult.body as any).arrayBuffer()
        
        // Get metadata
        const metadata = await parquetMetadataAsync(arrayBuffer)
        const schema = parquetSchema(metadata)
        const totalRows = Number(metadata.num_rows)
        const columns = schema.children.length
        const fileName = filePath.split('/').pop() || 'dataset.parquet'
        
        setInfo({ totalRows, columns, fileName })
      } catch (error) {
        console.error('Error loading Parquet info:', error)
        setInfo(null)
      } finally {
        setIsLoading(false)
      }
    }

    if (filePath) {
      loadParquetInfo()
    }
  }, [filePath])

  if (isLoading) {
    return (
      <div className="text-sm text-muted-foreground">
        Loading dataset information...
      </div>
    )
  }

  if (!info) {
    return (
      <div className="text-sm text-muted-foreground">
        Unable to load dataset information
      </div>
    )
  }

  return (
    <div className="text-sm text-muted-foreground space-y-1">
      <div className="flex items-center gap-2">
        <Columns3 className="h-3 w-3" />
        <span>{info.columns} columns</span>
      </div>
      <div className="flex items-center gap-2">
        <Rows3 className="h-3 w-3" />
        <span>Showing {Math.min(100, info.totalRows).toLocaleString()} of {info.totalRows.toLocaleString()} total rows</span>
      </div>
    </div>
  )
})

// Grid content component
const GridContent = React.memo(function GridContent({ 
  dataSet, 
  isSelected 
}: { 
  dataSet: Schema['DataSet']['type']
  isSelected?: boolean
}) {
  return (
    <div className="flex justify-between items-start w-full">
      <div className="space-y-1.5 flex-1 min-w-0">
        <div className="font-medium text-foreground truncate">
          {dataSet.name || `Dataset ${format(parseISO(dataSet.createdAt), 'MMM d, HH:mm')}`}
        </div>
        {dataSet.description && (
          <div className="text-sm text-muted-foreground line-clamp-2">
            {dataSet.description}
          </div>
        )}
        <Timestamp 
          time={dataSet.createdAt} 
          variant="relative" 
          showIcon={true}
          className="text-xs"
        />
        {dataSet.file && (
          <div className="flex items-center text-xs text-muted-foreground">
            <FileText className="h-3 w-3 mr-1" />
            File attached
          </div>
        )}
      </div>
      <div className="text-muted-foreground ml-4">
        <Table className="h-[2.25rem] w-[2.25rem]" strokeWidth={1.25} />
      </div>
    </div>
  )
})

// Detail content component
const DetailContent = React.memo(function DetailContent({
  dataSet,
  onClose,
  isFullWidth,
  onToggleFullWidth
}: {
  dataSet: Schema['DataSet']['type']
  onClose?: () => void
  isFullWidth?: boolean
  onToggleFullWidth?: () => void
}) {
  const hasParquetFile = dataSet.file && isParquetFile(dataSet.file)
  const [isNarrowViewport, setIsNarrowViewport] = React.useState(false)

  // Monitor viewport width for responsive layout
  React.useEffect(() => {
    const checkViewportWidth = () => {
      setIsNarrowViewport(window.innerWidth < 640) // sm breakpoint
    }
    
    checkViewportWidth() // Initial check
    window.addEventListener('resize', checkViewportWidth)
    
    return () => window.removeEventListener('resize', checkViewportWidth)
  }, [])

  return (
    <div className="w-full flex flex-col min-h-0 h-full">
      <div className="flex justify-between items-start w-full mb-6">
        <div className="space-y-2 flex-1">
          <div className="flex items-center gap-2">
            <Table className="h-5 w-5 text-foreground" />
            <span className="text-lg font-semibold">Dataset</span>
          </div>
          {dataSet.description && (
            <div className="text-sm text-muted-foreground">
              {dataSet.description}
            </div>
          )}
          <div className="space-y-1 text-sm">
            <Timestamp 
              time={dataSet.createdAt} 
              variant="relative" 
              showIcon={true}
            />
          </div>
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
              {dataSet.file && (
                <DropdownMenuItem 
                  onClick={async () => {
                    if (dataSet.file) {
                      try {
                        // Import the necessary functions for file download
                        const { getUrl } = await import('aws-amplify/storage')
                        
                        // Get the download URL for the file
                        const urlResult = await getUrl({
                          path: dataSet.file
                        })
                        
                        if (urlResult.url) {
                          // Create a temporary anchor element for direct download
                          const fileName = dataSet.file.split('/').pop() || 'dataset.parquet'
                          const a = document.createElement('a')
                          a.href = urlResult.url.toString()
                          a.download = fileName
                          a.style.display = 'none'
                          document.body.appendChild(a)
                          a.click()
                          document.body.removeChild(a)
                        }
                      } catch (error) {
                        console.error('Error downloading dataset file:', error)
                        // You could add a toast notification here if available
                      }
                    }
                  }}
                >
                  <Download className="mr-2 h-4 w-4" />
                  <span>Download Dataset</span>
                </DropdownMenuItem>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
          {!isNarrowViewport && onToggleFullWidth && (
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

      {/* Dataset Info Section */}
      {hasParquetFile && (
        <div className="mb-4">
          <DatasetInfo filePath={dataSet.file!} />
        </div>
      )}

      {/* Parquet File Preview - Takes up most of the available space */}
      {hasParquetFile && (
        <div className="flex-1 min-h-0 mb-4">
          <div className="h-full overflow-hidden">
            <ParquetViewer 
              filePath={dataSet.file!} 
              fileName={dataSet.file!.split('/').pop() || 'dataset.parquet'}
              hideFileInfo={true}
            />
          </div>
        </div>
      )}
    </div>
  )
})

export default function DataSetComponent({ 
  variant, 
  dataSet, 
  isSelected = false, 
  onClick, 
  onClose,
  isFullWidth = false,
  onToggleFullWidth,
  ...props 
}: DataSetComponentProps) {
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
            <GridContent dataSet={dataSet} isSelected={isSelected} />
          ) : (
            <DetailContent 
              dataSet={dataSet}
              onClose={onClose}
              isFullWidth={isFullWidth}
              onToggleFullWidth={onToggleFullWidth}
            />
          )}
        </div>
      </div>
    </div>
  )
}