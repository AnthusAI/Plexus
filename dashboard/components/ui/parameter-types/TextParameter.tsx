"use client"

import React from 'react'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ParameterDefinition } from '@/types/parameters'

interface TextParameterProps {
  definition: ParameterDefinition
  value: string
  onChange: (value: string) => void
  error?: string
}

export function TextParameter({ definition, value, onChange, error }: TextParameterProps) {
  return (
    <div className="space-y-2">
      <Label htmlFor={definition.name}>
        {definition.label}
        {definition.required && <span className="text-destructive ml-1">*</span>}
      </Label>
      {definition.description && (
        <p className="text-xs text-muted-foreground">{definition.description}</p>
      )}
      <Input
        id={definition.name}
        value={value || ''}
        onChange={(e) => onChange(e.target.value)}
        placeholder={definition.placeholder}
        className={error ? 'border-destructive' : ''}
      />
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  )
}



