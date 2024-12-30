"use client"

import React from "react"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

interface TimeRangeSelectorProps {
  onTimeRangeChange: (range: string, customRange?: { from: Date | undefined; to: Date | undefined }) => void;
  options: Array<{ value: string; label: string }>;
}

export const TimeRangeSelector: React.FC<TimeRangeSelectorProps> = ({ onTimeRangeChange, options }) => {
  const safeOptions = Array.isArray(options) ? options : [];

  if (safeOptions.length === 0) {
    return null;
  }

  return (
    <Select onValueChange={(value) => onTimeRangeChange(value)}>
      <SelectTrigger className="w-[200px] h-8 bg-card-light border-none">
        <SelectValue placeholder="Select time range" />
      </SelectTrigger>
      <SelectContent className="bg-card border-none">
        {safeOptions.map((option) => (
          <SelectItem key={option.value} value={option.value}>
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
