"use client"

import { useState } from "react"
import { format } from "date-fns"
import { CalendarIcon } from "lucide-react"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Calendar } from "@/components/ui/calendar"

export interface TimeRangeOption {
  value: string
  label: string
}

export const DEFAULT_TIME_RANGE_OPTIONS: TimeRangeOption[] = [
  { value: "last_hour", label: "Last hour" },
  { value: "last_3_hours", label: "Last 3 hours" },
  { value: "last_12_hours", label: "Last 12 hours" },
  { value: "last_24_hours", label: "Last 24 hours" },
  { value: "last_3_days", label: "Last 3 days" },
  { value: "last_week", label: "Last week" },
  { value: "custom", label: "Custom" },
]

interface TimeRangeSelectorProps {
  onTimeRangeChange: (range: string, customRange?: { from: Date | undefined; to: Date | undefined }) => void
  options?: TimeRangeOption[]
}

export function TimeRangeSelector({ onTimeRangeChange, options = DEFAULT_TIME_RANGE_OPTIONS }: TimeRangeSelectorProps) {
  const [selectedTimeRange, setSelectedTimeRange] = useState(options[0].value)
  const [customDateRange, setCustomDateRange] = useState<{
    from: Date | undefined;
    to: Date | undefined;
  }>({
    from: undefined,
    to: undefined,
  })

  const handleTimeRangeChange = (value: string) => {
    setSelectedTimeRange(value)
    if (value !== "custom") {
      onTimeRangeChange(value)
    } else {
      onTimeRangeChange(value, customDateRange)
    }
  }

  const handleCustomDateRangeChange = (range: { from: Date | undefined; to: Date | undefined } | undefined) => {
    if (range) {
      setCustomDateRange(range)
      onTimeRangeChange("custom", range)
    }
  }

  return (
    <div className="flex items-center space-x-4">
      {selectedTimeRange === "custom" && (
        <Popover>
          <PopoverTrigger asChild>
            <Button
              variant={"outline"}
              className={`w-[300px] justify-start text-left font-normal ${
                !customDateRange.from && "text-muted-foreground"
              }`}
            >
              <CalendarIcon className="mr-2 h-4 w-4" />
              {customDateRange.from ? (
                customDateRange.to ? (
                  <>
                    {format(customDateRange.from, "LLL dd, y")} -{" "}
                    {format(customDateRange.to, "LLL dd, y")}
                  </>
                ) : (
                  format(customDateRange.from, "LLL dd, y")
                )
              ) : (
                <span>Pick a date range</span>
              )}
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-auto p-0" align="start">
            <Calendar
              initialFocus
              mode="range"
              defaultMonth={customDateRange.from}
              selected={customDateRange}
              onSelect={handleCustomDateRangeChange}
              numberOfMonths={2}
            />
          </PopoverContent>
        </Popover>
      )}
      <Select
        value={selectedTimeRange}
        onValueChange={handleTimeRangeChange}
      >
        <SelectTrigger className="w-[200px] border border-secondary">
          <SelectValue placeholder="Time Range" />
        </SelectTrigger>
        <SelectContent>
          {options.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}
