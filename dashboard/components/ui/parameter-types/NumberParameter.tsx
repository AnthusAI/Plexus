"use client"

import React from 'react'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ParameterDefinition } from '@/types/parameters'

interface NumberParameterProps {
  definition: ParameterDefinition
  value: number | string
  onChange: (value: number) => void
  error?: string
}

export function NumberParameter({ definition, value, onChange, error }: NumberParameterProps) {
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
        type="number"
        value={value || ''}
        onChange={(e) => onChange(Number(e.target.value))}
        placeholder={definition.placeholder}
        min={definition.min}
        max={definition.max}
        className={error ? 'border-destructive' : ''}
      />
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  )
}



