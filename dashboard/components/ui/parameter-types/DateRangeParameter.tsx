"use client"

import React from "react"
import { format, parseISO } from "date-fns"
import { CalendarIcon } from "lucide-react"
import { type DateRange } from "react-day-picker"
import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
import { Label } from "@/components/ui/label"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { cn } from "@/lib/utils"
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
  const today = new Date()
  today.setHours(23, 59, 59, 999)

  const selectedRange: DateRange | undefined = start
    ? {
        from: parseISO(start),
        to: end ? parseISO(end) : undefined,
      }
    : undefined

  const handleRangeSelect = (range: DateRange | undefined) => {
    if (!range?.from) {
      onChange({ start: "", end: "" })
      return
    }

    onChange({
      start: format(range.from, "yyyy-MM-dd"),
      end: range.to ? format(range.to, "yyyy-MM-dd") : "",
    })
  }

  const formatLabelDate = (raw: string): string => {
    const parsed = parseISO(raw)
    if (Number.isNaN(parsed.getTime())) return raw
    return format(parsed, "LLL dd, y")
  }

  return (
    <div className="space-y-2">
      <Label htmlFor={`${definition.name}-range`}>
        {definition.label}
        {definition.required && <span className="text-destructive ml-1">*</span>}
      </Label>
      {definition.description && (
        <p className="text-xs text-muted-foreground">{definition.description}</p>
      )}
      <Popover modal>
        <PopoverTrigger asChild>
          <Button
            id={`${definition.name}-range`}
            type="button"
            variant="outline"
            disabled={disabled}
            className={cn(
              "w-full justify-start text-left font-normal",
              !start && "text-muted-foreground",
              error && "border-destructive"
            )}
          >
            <CalendarIcon className="mr-2 h-4 w-4" />
            {start ? (
              end ? (
                <>
                  {formatLabelDate(start)} - {formatLabelDate(end)}
                </>
              ) : (
                formatLabelDate(start)
              )
            ) : (
              "Pick date range"
            )}
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-auto p-0" align="start">
          <Calendar
            mode="range"
            numberOfMonths={2}
            selected={selectedRange}
            defaultMonth={selectedRange?.from}
            onSelect={handleRangeSelect}
            disabled={(date) => date > today}
            initialFocus
          />
        </PopoverContent>
      </Popover>
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  )
}
