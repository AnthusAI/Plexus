"use client"

import React from "react"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ParameterDefinition, DateRangeValue } from "@/types/parameters"

interface DateRangeParameterProps {
  definition: ParameterDefinition
  value: DateRangeValue | undefined
  onChange: (value: DateRangeValue) => void
  disabled?: boolean
  error?: string
}

export function DateRangeParameter({ definition, value, onChange, disabled, error }: DateRangeParameterProps) {
  const start = value?.start || ""
  const end = value?.end || ""

  return (
    <div className="space-y-2">
      <Label htmlFor={`${definition.name}-start`}>
        {definition.label}
        {definition.required && <span className="text-destructive ml-1">*</span>}
      </Label>
      {definition.description && (
        <p className="text-xs text-muted-foreground">{definition.description}</p>
      )}
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        <div className="space-y-1">
          <Label className="text-xs text-muted-foreground" htmlFor={`${definition.name}-start`}>
            Start Date
          </Label>
          <Input
            id={`${definition.name}-start`}
            type="date"
            value={start}
            onChange={(e) => onChange({ start: e.target.value, end })}
            max={end || undefined}
            disabled={disabled}
            className={error ? "border-destructive" : ""}
          />
        </div>
        <div className="space-y-1">
          <Label className="text-xs text-muted-foreground" htmlFor={`${definition.name}-end`}>
            End Date
          </Label>
          <Input
            id={`${definition.name}-end`}
            type="date"
            value={end}
            onChange={(e) => onChange({ start, end: e.target.value })}
            min={start || undefined}
            disabled={disabled}
            className={error ? "border-destructive" : ""}
          />
        </div>
      </div>
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  )
}
