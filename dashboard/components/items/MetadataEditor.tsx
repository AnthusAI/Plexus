'use client'

import React, { useState, useCallback } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Plus, Trash2, Edit3 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { CardButton } from '@/components/CardButton'

export interface MetadataEntry {
  key: string
  value: string
  id: string
}

export interface MetadataEditorProps {
  metadata?: Record<string, string> | null
  readOnly?: boolean
  onChange?: (metadata: Record<string, string>) => void
  className?: string
}

const generateId = () => Math.random().toString(36).substr(2, 9)

export const MetadataEditor = React.forwardRef<HTMLDivElement, MetadataEditorProps>(
  ({
    metadata = {},
    readOnly = false,
    onChange,
    className,
    ...props
  }, ref) => {
    // Convert metadata to internal format
    const convertToEntries = useCallback((meta: Record<string, string> | null): MetadataEntry[] => {
      if (!meta) return []
      return Object.entries(meta).map(([key, value]) => ({
        key,
        value,
        id: generateId()
      }))
    }, [])

    const [entries, setEntries] = useState<MetadataEntry[]>(() => convertToEntries(metadata))
    const [errors, setErrors] = useState<Record<string, { key?: string; value?: string }>>({})

    // Update internal state when metadata prop changes
    React.useEffect(() => {
      const newEntries = convertToEntries(metadata)
      setEntries(newEntries)
      setErrors({}) // Clear errors when metadata changes
    }, [metadata, convertToEntries])

    const validateEntry = useCallback((key: string, value: string, id: string, allEntries: MetadataEntry[]) => {
      const entryErrors: { key?: string; value?: string } = {}

      // Check for duplicate keys
      const duplicateKey = allEntries.some(entry => entry.id !== id && entry.key === key && key.trim() !== '')
      if (duplicateKey) {
        entryErrors.key = 'Duplicate key'
      }

      // Check for empty key
      if (key.trim() === '' && value.trim() !== '') {
        entryErrors.key = 'Key cannot be empty'
      }

      return entryErrors
    }, [])

    const emitChange = useCallback((newEntries: MetadataEntry[]) => {
      if (onChange && !readOnly) {
        const metadata = newEntries
          .filter(entry => entry.key.trim() && entry.value.trim())
          .reduce((acc, entry) => {
            acc[entry.key.trim()] = entry.value.trim()
            return acc
          }, {} as Record<string, string>)
        onChange(metadata)
      }
    }, [onChange, readOnly])

    const updateEntry = useCallback((id: string, field: 'key' | 'value', newValue: string) => {
      if (readOnly) return

      const newEntries = entries.map(entry =>
        entry.id === id ? { ...entry, [field]: newValue } : entry
      )
      setEntries(newEntries)

      // Validate all entries
      const newErrors: Record<string, { key?: string; value?: string }> = {}
      newEntries.forEach(entry => {
        const entryErrors = validateEntry(entry.key, entry.value, entry.id, newEntries)
        if (Object.keys(entryErrors).length > 0) {
          newErrors[entry.id] = entryErrors
        }
      })
      setErrors(newErrors)

      emitChange(newEntries)
    }, [entries, validateEntry, emitChange, readOnly])

    const addEntry = useCallback(() => {
      if (readOnly) return
      
      const newEntry: MetadataEntry = {
        key: '',
        value: '',
        id: generateId()
      }
      const newEntries = [...entries, newEntry]
      setEntries(newEntries)
      emitChange(newEntries)
    }, [entries, emitChange, readOnly])

    const removeEntry = useCallback((id: string) => {
      if (readOnly) return

      const newEntries = entries.filter(entry => entry.id !== id)
      setEntries(newEntries)
      
      // Remove errors for deleted entry
      const newErrors = { ...errors }
      delete newErrors[id]
      setErrors(newErrors)
      
      emitChange(newEntries)
    }, [entries, errors, emitChange, readOnly])

    const hasEntries = entries.length > 0 && entries.some(entry => entry.key.trim() && entry.value.trim())

    return (
      <div ref={ref} className={cn("space-y-4", className)} {...props}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium leading-none text-muted-foreground">Metadata</span>
            {!readOnly && <span className="text-[10px] text-muted-foreground/60">optional</span>}
            {readOnly && hasEntries && <Edit3 className="h-3 w-3 text-muted-foreground/60" />}
          </div>
          {!readOnly && (
            <CardButton
              label="Add Entry"
              onClick={addEntry}
              aria-label="Add metadata entry"
            />
          )}
        </div>
        
        {hasEntries ? (
          <div className="space-y-2">
            {entries.map((entry) => {
              // Only show entries that have content in read-only mode
              if (readOnly && (!entry.key.trim() || !entry.value.trim())) {
                return null
              }

              return (
                <div key={entry.id} className="flex items-center space-x-2">
                  {readOnly ? (
                    // Read-only view: display as formatted key-value pairs
                    <div className="flex-1 bg-background rounded-md p-2 border">
                      <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 items-start">
                        <dt className="text-sm font-medium text-muted-foreground min-w-0">
                          {entry.key}:
                        </dt>
                        <dd className="text-sm text-foreground break-words min-w-0">
                          {entry.value}
                        </dd>
                      </div>
                    </div>
                  ) : (
                    // Edit mode: input fields
                    <>
                      <Input
                        value={entry.key}
                        onChange={(e) => updateEntry(entry.id, 'key', e.target.value)}
                        placeholder="Key"
                        className={cn(
                          "bg-background border-0 focus-visible:ring-1 focus-visible:ring-ring flex-1",
                          errors[entry.id]?.key && "bg-destructive/10 focus-visible:ring-destructive"
                        )}
                      />
                      <Input
                        value={entry.value}
                        onChange={(e) => updateEntry(entry.id, 'value', e.target.value)}
                        placeholder="Value"
                        className={cn(
                          "bg-background border-0 focus-visible:ring-1 focus-visible:ring-ring flex-1",
                          errors[entry.id]?.value && "bg-destructive/10 focus-visible:ring-destructive"
                        )}
                      />
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => removeEntry(entry.id)}
                        className="h-8 w-8 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </>
                  )}
                </div>
              )
            })}
            
            {/* Show validation errors in edit mode */}
            {!readOnly && entries.map((entry) => {
              const hasErrors = errors[entry.id]?.key || errors[entry.id]?.value;
              if (!hasErrors) return null;
              
              return (
                <div key={`errors-${entry.id}`} className="space-y-1">
                  {errors[entry.id]?.key && (
                    <div className="text-xs text-destructive">{errors[entry.id].key}</div>
                  )}
                  {errors[entry.id]?.value && (
                    <div className="text-xs text-destructive">{errors[entry.id].value}</div>
                  )}
                </div>
              )
            })}
          </div>
        ) : (
          <div className="text-center py-4 text-sm text-muted-foreground bg-muted/30 rounded-md">
            {readOnly ? "No metadata" : "No metadata entries"}
          </div>
        )}
      </div>
    )
  }
)

MetadataEditor.displayName = "MetadataEditor" 