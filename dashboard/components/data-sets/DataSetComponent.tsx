"use client"

import React from "react"
import { Calendar, FileText, Table, X, MoreHorizontal, Download } from "lucide-react"
import type { Schema } from "@/amplify/data/resource"
import { formatDistanceToNow, parseISO, format } from "date-fns"
import { cn } from "@/lib/utils"
import { CardButton } from "@/components/CardButton"
import { Timestamp } from "@/components/ui/timestamp"
import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { Button } from "@/components/ui/button"

interface DataSetComponentProps {
  variant: 'grid' | 'detail'
  dataSet: Schema['DataSet']['type']
  isSelected?: boolean
  onClick?: () => void
  onClose?: () => void
}

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
  onClose
}: {
  dataSet: Schema['DataSet']['type']
  onClose?: () => void
}) {
  return (
    <div className="w-full flex flex-col min-h-0 h-full">
      <div className="flex justify-between items-start w-full mb-6">
        <div className="space-y-2 flex-1">
          <div className="text-lg font-semibold text-foreground">
            {dataSet.name || `Dataset ${format(parseISO(dataSet.createdAt), 'MMM d, yyyy HH:mm')}`}
          </div>
          {dataSet.description && (
            <div className="text-sm text-muted-foreground">
              {dataSet.description}
            </div>
          )}
          <div className="space-y-1 text-sm">
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground">Created:</span>
              <Timestamp 
                time={dataSet.createdAt} 
                variant="relative" 
                showIcon={true}
              />
            </div>
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground">Updated:</span>
              <Timestamp 
                time={dataSet.updatedAt} 
                variant="relative" 
                showIcon={true}
              />
            </div>
          </div>
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
                {dataSet.file && (
                  <DropdownMenu.Item 
                    className="relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50"
                    onSelect={() => {
                      // TODO: Implement file download
                      console.log('Download dataset file:', dataSet.file)
                    }}
                  >
                    <Download className="mr-2 h-4 w-4" />
                    Download File
                  </DropdownMenu.Item>
                )}
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>
          {onClose && (
            <CardButton
              icon={X}
              onClick={onClose}
              aria-label="Close"
            />
          )}
        </div>
      </div>

      {/* Dataset Information */}
      <div className="space-y-4">
        <div>
          <h3 className="text-sm font-medium mb-2">Dataset Information</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Account ID:</span>
              <span className="font-mono text-xs">{dataSet.accountId}</span>
            </div>
            {dataSet.scorecardId && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Scorecard ID:</span>
                <span className="font-mono text-xs">{dataSet.scorecardId}</span>
              </div>
            )}
            {dataSet.scoreId && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Score ID:</span>
                <span className="font-mono text-xs">{dataSet.scoreId}</span>
              </div>
            )}
            <div className="flex justify-between">
              <span className="text-muted-foreground">Score Version ID:</span>
              <span className="font-mono text-xs">{dataSet.scoreVersionId}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Data Source Version ID:</span>
              <span className="font-mono text-xs">{dataSet.dataSourceVersionId}</span>
            </div>
          </div>
        </div>

        {dataSet.file && (
          <div>
            <h3 className="text-sm font-medium mb-2">File Information</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">File Path:</span>
                <span className="font-mono text-xs break-all">{dataSet.file}</span>
              </div>
              <Button variant="outline" size="sm" className="w-full" onClick={() => {
                // TODO: Implement file download
                console.log('Download dataset file:', dataSet.file)
              }}>
                <Download className="h-4 w-4 mr-2" />
                Download Dataset File
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
})

export default function DataSetComponent({ 
  variant, 
  dataSet, 
  isSelected = false, 
  onClick, 
  onClose,
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
            />
          )}
        </div>
      </div>
    </div>
  )
}