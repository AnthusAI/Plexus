'use client'

import React, { useState, useCallback } from 'react'
import { Button } from './button'
import { Input } from './input'
import { Plus, Trash2, Tag } from 'lucide-react'
import { cn } from '@/lib/utils'
import { CardButton } from '@/components/CardButton'

export interface MetadataEntry {
  key: string
  value: string
  originalValue?: any // Store original value for complex objects
  id: string
}

export interface MetadataEditorProps {
  /** Initial metadata entries */
  value?: Record<string, any> | MetadataEntry[] // Changed to allow any value type
  /** Callback when metadata changes */
  onChange?: (metadata: Record<string, string>) => void
  /** Custom className for the container */
  className?: string
  /** Placeholder text for the key input */
  keyPlaceholder?: string
  /** Placeholder text for the value input */
  valuePlaceholder?: string
  /** Whether the component is disabled */
  disabled?: boolean
  /** Whether to show the add button */
  showAddButton?: boolean
  /** Maximum number of entries allowed */
  maxEntries?: number
  /** Custom validation for keys */
  validateKey?: (key: string) => string | null
  /** Custom validation for values */
  validateValue?: (value: string) => string | null
}

const generateId = () => Math.random().toString(36).substr(2, 9)

// Helper function to format values for display
const formatValueForDisplay = (value: any): string => {
  if (value === null || value === undefined) {
    return ''
  }
  
  if (typeof value === 'string') {
    return value
  }
  
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value)
  }
  
  // For objects and arrays, format as JSON
  try {
    return JSON.stringify(value, null, 2)
  } catch (error) {
    return String(value)
  }
}

// Helper function to check if a value is complex (not a simple string/number/boolean)
const isComplexValue = (value: any): boolean => {
  return value !== null && 
         value !== undefined && 
         typeof value !== 'string' && 
         typeof value !== 'number' && 
         typeof value !== 'boolean'
}

export const MetadataEditor = React.forwardRef<HTMLDivElement, MetadataEditorProps>(
  ({
    value = {},
    onChange,
    className,
    keyPlaceholder = "Key",
    valuePlaceholder = "Value",
    disabled = false,
    showAddButton = true,
    maxEntries,
    validateKey,
    validateValue,
    ...props
  }, ref) => {
    // Convert value to internal format
    const convertToEntries = useCallback((val: Record<string, any> | MetadataEntry[]): MetadataEntry[] => {
      if (Array.isArray(val)) {
        return val.map(entry => ({ 
          ...entry, 
          key: String(entry.key || ''),
          value: String(entry.value || ''),
          originalValue: entry.originalValue,
          id: entry.id || generateId() 
        }))
      }
      return Object.entries(val).map(([key, originalValue]) => ({
        key: String(key || ''),
        value: String(originalValue || ''),
        originalValue: originalValue,
        id: generateId()
      }))
    }, [])

    const [entries, setEntries] = useState<MetadataEntry[]>(() => convertToEntries(value))
    const [errors, setErrors] = useState<Record<string, { key?: string; value?: string }>>({})

    // Update internal state when value prop changes, but preserve empty entries
    React.useEffect(() => {
      const newEntries = convertToEntries(value)
      // Only update if the new entries represent a different set of filled entries
      setEntries(prevEntries => {
        const currentFilledEntries = prevEntries.filter(entry => entry.key.trim() && entry.value.trim())
        const newFilledEntries = newEntries.filter(entry => entry.key.trim() && entry.value.trim())
        
        // If the filled entries are the same, keep the current entries (which may include empty ones)
        if (JSON.stringify(currentFilledEntries) === JSON.stringify(newFilledEntries)) {
          return prevEntries
        }
        
        // Otherwise, use the new entries
        return newEntries
      })
    }, [value, convertToEntries])

    const validateEntry = useCallback((key: string, value: string, id: string, allEntries: MetadataEntry[]) => {
      const entryErrors: { key?: string; value?: string } = {}
      
      const keyStr = String(key || '')
      const valueStr = String(value || '')

      // Check for duplicate keys
      const duplicateKey = allEntries.some(entry => entry.id !== id && String(entry.key || '') === keyStr && keyStr.trim() !== '')
      if (duplicateKey) {
        entryErrors.key = 'Duplicate key'
      }

      // Custom key validation
      if (validateKey && keyStr.trim()) {
        const keyError = validateKey(keyStr)
        if (keyError) {
          entryErrors.key = keyError
        }
      }

      // Custom value validation
      if (validateValue && valueStr.trim()) {
        const valueError = validateValue(valueStr)
        if (valueError) {
          entryErrors.value = valueError
        }
      }

      return entryErrors
    }, [validateKey, validateValue])

    const emitChange = useCallback((newEntries: MetadataEntry[]) => {
      if (onChange) {
        const metadata = newEntries
          .filter(entry => String(entry.key || '').trim() && String(entry.value || '').trim())
          .reduce((acc, entry) => {
            acc[String(entry.key || '').trim()] = String(entry.value || '').trim()
            return acc
          }, {} as Record<string, string>)
        onChange(metadata)
      }
    }, [onChange])

    const updateEntry = useCallback((id: string, field: 'key' | 'value', newValue: string) => {
      const newEntries = entries.map(entry =>
        entry.id === id ? { ...entry, [field]: String(newValue || '') } : entry
      )
      setEntries(newEntries)

      // Validate all entries
      const newErrors: Record<string, { key?: string; value?: string }> = {}
      newEntries.forEach(entry => {
        const entryErrors = validateEntry(String(entry.key || ''), String(entry.value || ''), entry.id, newEntries)
        if (Object.keys(entryErrors).length > 0) {
          newErrors[entry.id] = entryErrors
        }
      })
      setErrors(newErrors)

      emitChange(newEntries)
    }, [entries, validateEntry, emitChange])

    const addEntry = useCallback(() => {
      if (maxEntries && entries.length >= maxEntries) return
      
      const newEntry: MetadataEntry = {
        key: '',
        value: '',
        id: generateId()
      }
      const newEntries = [...entries, newEntry]
      setEntries(newEntries)
      emitChange(newEntries)
    }, [entries, maxEntries, emitChange])

    const removeEntry = useCallback((id: string) => {
      const newEntries = entries.filter(entry => entry.id !== id)
      setEntries(newEntries)
      
      // Remove errors for deleted entry
      const newErrors = { ...errors }
      delete newErrors[id]
      setErrors(newErrors)
      
      emitChange(newEntries)
    }, [entries, errors, emitChange])

    const hasValidEntries = entries.some(entry => String(entry.key || '').trim() && String(entry.value || '').trim())
    const canAddMore = !disabled && (!maxEntries || entries.length < maxEntries)

    return (
      <div ref={ref} className={cn("space-y-2", className)} {...props}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Tag className="h-3 w-3 text-muted-foreground" />
            <span className="text-sm font-medium leading-none text-muted-foreground peer-disabled:cursor-not-allowed peer-disabled:opacity-70">Metadata</span>
            {!disabled && <span className="text-[10px] text-muted-foreground">optional</span>}
          </div>
          {showAddButton && canAddMore && (
            <CardButton
              label="Add Entry"
              onClick={addEntry}
              disabled={disabled}
              aria-label="Add metadata entry"
            />
          )}
        </div>
        
        {entries.length > 0 ? (
          <div className={cn("space-y-2", disabled && "grid gap-1 grid-cols-[auto_1fr]")}>
            {entries.map((entry) => {
              // Use original value for display if available, otherwise use the string value
              const displayValue = entry.originalValue !== undefined ? entry.originalValue : entry.value
              const formattedValue = formatValueForDisplay(displayValue)
              const isComplex = isComplexValue(displayValue)
              
              return (
                <div key={entry.id} className={cn(disabled ? "contents" : "flex items-center space-x-2")}>
                  {disabled ? (
                    // Read-only mode: render in rounded rectangles with grid layout
                    <>
                      <div className="bg-background rounded px-2 py-1">
                        <span className="text-sm text-foreground font-medium font-mono">
                          {String(entry.key || '')}
                        </span>
                      </div>
                      <div className="bg-background rounded px-2 py-1">
                        {isComplex ? (
                          // For complex values, show formatted JSON in a code block
                          <pre className="text-xs text-foreground font-mono whitespace-pre-wrap break-words max-w-full overflow-hidden">
                            {formattedValue}
                          </pre>
                        ) : (
                          // For simple values, show as regular text
                          <span className="text-sm text-foreground">
                            {formattedValue}
                          </span>
                        )}
                      </div>
                    </>
                  ) : (
                    // Edit mode: render as inputs
                    <>
                      <Input
                        value={String(entry.key || '')}
                        onChange={(e) => updateEntry(entry.id, 'key', e.target.value)}
                        placeholder={keyPlaceholder}
                        disabled={disabled}
                        className={cn(
                          "bg-background border-0 focus-visible:ring-1 focus-visible:ring-ring flex-1 text-foreground",
                          errors[entry.id]?.key && "bg-destructive/10 focus-visible:ring-destructive"
                        )}
                      />
                      <Input
                        value={String(entry.value || '')}
                        onChange={(e) => updateEntry(entry.id, 'value', e.target.value)}
                        placeholder={valuePlaceholder}
                        disabled={disabled}
                        className={cn(
                          "bg-background border-0 focus-visible:ring-1 focus-visible:ring-ring flex-1 text-foreground",
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
            {/* Show validation errors below the rows */}
            {entries.map((entry) => {
              const hasErrors = errors[entry.id]?.key || errors[entry.id]?.value;
              if (!hasErrors) return null;
              
              return (
                <div key={`errors-${entry.id}`}>
                  {errors[entry.id]?.key && (
                    <div className="text-xs text-destructive mt-1 mb-1">{errors[entry.id].key}</div>
                  )}
                  {errors[entry.id]?.value && (
                    <div className="text-xs text-destructive mt-1 mb-1">{errors[entry.id].value}</div>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="text-center py-4 text-sm text-muted-foreground">
            No metadata entries
          </div>
        )}
      </div>
    )
  }
)

MetadataEditor.displayName = "MetadataEditor" 