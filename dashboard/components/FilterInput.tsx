"use client"

import React, { useState, useEffect } from 'react'
import { ListFilter, XCircle } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

// Use a shared key for all dashboard filters so the value persists across pages
const SHARED_FILTER_KEY = 'dashboard-filter'

export interface FilterInputProps {
  /**
   * Placeholder text for the input
   */
  placeholder?: string
  /**
   * Callback when filter value changes
   */
  onFilterChange: (value: string) => void
  /**
   * Optional className for styling
   */
  className?: string
}

export function FilterInput({
  placeholder = "Filter...",
  onFilterChange,
  className
}: FilterInputProps) {
  const [filterValue, setFilterValue] = useState('')

  // Load filter value from sessionStorage on mount
  useEffect(() => {
    const savedFilter = sessionStorage.getItem(SHARED_FILTER_KEY)
    if (savedFilter) {
      setFilterValue(savedFilter)
      onFilterChange(savedFilter)
    }
  }, [onFilterChange])

  // Handle filter change
  const handleFilterChange = (value: string) => {
    setFilterValue(value)
    sessionStorage.setItem(SHARED_FILTER_KEY, value)
    onFilterChange(value)
  }

  // Clear filter
  const handleClear = () => {
    setFilterValue('')
    sessionStorage.setItem(SHARED_FILTER_KEY, '')
    onFilterChange('')
  }

  return (
    <div className={cn(
      "flex items-center gap-2 pl-2 pr-1 h-8 rounded-md bg-card w-[180px]",
      className
    )}>
      <ListFilter className="h-4 w-4 text-muted-foreground flex-shrink-0" />
      <div className="relative flex-1 min-w-0">
        <Input
          type="text"
          value={filterValue}
          onChange={(e) => handleFilterChange(e.target.value)}
          placeholder={placeholder}
          className="border-0 bg-background shadow-none focus-visible:ring-0 h-6 px-2 py-1 text-sm rounded"
        />
        {filterValue && (
          <button
            onClick={handleClear}
            className="absolute right-1 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
            aria-label="Clear filter"
          >
            <XCircle className="h-3 w-3" />
          </button>
        )}
      </div>
    </div>
  )
}
