"use client"

import React from 'react'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { ParameterDefinition } from '@/types/parameters'

interface BooleanParameterProps {
  definition: ParameterDefinition
  value: boolean
  onChange: (value: boolean) => void
  error?: string
}

export function BooleanParameter({ definition, value, onChange, error }: BooleanParameterProps) {
  return (
    <div className="space-y-2">
      <div className="flex items-center space-x-2">
        <Checkbox
          id={definition.name}
          checked={value || false}
          onCheckedChange={(checked) => onChange(checked === true)}
        />
        <Label 
          htmlFor={definition.name}
          className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
        >
          {definition.label}
          {definition.required && <span className="text-destructive ml-1">*</span>}
        </Label>
      </div>
      {definition.description && (
        <p className="text-xs text-muted-foreground ml-6">{definition.description}</p>
      )}
      {error && <p className="text-xs text-destructive ml-6">{error}</p>}
    </div>
  )
}



