"use client"

import React from "react"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

interface TimeRangeSelectorProps {
  onTimeRangeChange: (range: string, customRange?: { from: Date | undefined; to: Date | undefined }) => void;
  options: Array<{ value: string; label: string }>;
}

export const TimeRangeSelector: React.FC<TimeRangeSelectorProps> = ({ onTimeRangeChange, options }) => {
  // Ensure options is always an array
  const safeOptions = Array.isArray(options) ? options : [];

  if (safeOptions.length === 0) {
    return null; // Don't render anything if there are no options
  }

  return (
    <Select onValueChange={(value) => onTimeRangeChange(value)}>
      <SelectTrigger className="w-[200px] h-10">
        <SelectValue placeholder="Select time range" />
      </SelectTrigger>
      <SelectContent>
        {safeOptions.map((option) => (
          <SelectItem key={option.value} value={option.value}>
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
