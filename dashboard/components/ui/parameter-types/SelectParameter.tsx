"use client"

import React from 'react'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { ParameterDefinition } from '@/types/parameters'

interface SelectParameterProps {
  definition: ParameterDefinition
  value: string
  onChange: (value: string) => void
  error?: string
}

export function SelectParameter({ definition, value, onChange, error }: SelectParameterProps) {
  return (
    <div className="space-y-2">
      <Label htmlFor={definition.name}>
        {definition.label}
        {definition.required && <span className="text-destructive ml-1">*</span>}
      </Label>
      {definition.description && (
        <p className="text-xs text-muted-foreground">{definition.description}</p>
      )}
      <Select value={value || ''} onValueChange={onChange}>
        <SelectTrigger id={definition.name} className={error ? 'border-destructive' : ''}>
          <SelectValue placeholder={definition.placeholder || `Select ${definition.label}`} />
        </SelectTrigger>
        <SelectContent>
          {definition.options?.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  )
}



