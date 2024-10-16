"use client"

import React, { useState } from "react"
import { Button } from "@/components/ui/button"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Input } from "@/components/ui/input"
import { X, Plus, Filter } from "lucide-react"

type FilterCondition = {
  field: string
  operator: string
  value: string
}

type FilterGroup = {
  type: 'AND' | 'OR'
  conditions: FilterCondition[]
}

export type FilterConfig = FilterGroup[]

interface FilterControlProps {
  onFilterChange: (filters: FilterConfig) => void
  availableFields: { value: string; label: string }[]
}

const operators = [
  { value: 'equals', label: 'Equals' },
  { value: 'not_equals', label: 'Not Equals' },
  { value: 'contains', label: 'Contains' },
  { value: 'not_contains', label: 'Not Contains' },
  { value: 'greater_than', label: 'Greater Than' },
  { value: 'less_than', label: 'Less Than' },
]

export function FilterControl({ onFilterChange, availableFields }: FilterControlProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [filters, setFilters] = useState<FilterConfig>([{ type: 'AND', conditions: [] }])

  const addCondition = (groupIndex: number) => {
    const newFilters = [...filters]
    newFilters[groupIndex].conditions.push({ field: '', operator: '', value: '' })
    setFilters(newFilters)
    onFilterChange(newFilters)
  }

  const removeCondition = (groupIndex: number, conditionIndex: number) => {
    const newFilters = [...filters]
    newFilters[groupIndex].conditions.splice(conditionIndex, 1)
    if (newFilters[groupIndex].conditions.length === 0) {
      newFilters.splice(groupIndex, 1)
    }
    setFilters(newFilters)
    onFilterChange(newFilters)
  }

  const updateCondition = (groupIndex: number, conditionIndex: number, field: keyof FilterCondition, value: string) => {
    const newFilters = [...filters]
    newFilters[groupIndex].conditions[conditionIndex][field] = value
    setFilters(newFilters)
    onFilterChange(newFilters)
  }

  const addGroup = () => {
    setFilters([...filters, { type: 'OR', conditions: [] }])
  }

  const toggleGroupType = (groupIndex: number) => {
    const newFilters = [...filters]
    newFilters[groupIndex].type = newFilters[groupIndex].type === 'AND' ? 'OR' : 'AND'
    setFilters(newFilters)
    onFilterChange(newFilters)
  }

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" className="">
          <Filter className="mr-2 h-4 w-4" />
          {filters.some(group => group.conditions.length > 0) ? 'Filtered' : 'Filter'}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[450px] p-0" align="start">
        <div className="p-4 space-y-4">
          {filters.map((group, groupIndex) => (
            <div key={groupIndex} className="space-y-2">
              <div className="flex items-center justify-between">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => toggleGroupType(groupIndex)}
                >
                  {group.type}
                </Button>
                {groupIndex > 0 && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      const newFilters = [...filters]
                      newFilters.splice(groupIndex, 1)
                      setFilters(newFilters)
                      onFilterChange(newFilters)
                    }}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                )}
              </div>
              {group.conditions.map((condition, conditionIndex) => (
                <div key={conditionIndex} className="flex items-center space-x-2">
                  <Select
                    value={condition.field}
                    onValueChange={(value) => updateCondition(groupIndex, conditionIndex, 'field', value)}
                  >
                    <SelectTrigger className="w-[120px]">
                      <SelectValue placeholder="Field" />
                    </SelectTrigger>
                    <SelectContent>
                      {availableFields.map((field) => (
                        <SelectItem key={field.value} value={field.value}>
                          {field.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Select
                    value={condition.operator}
                    onValueChange={(value) => updateCondition(groupIndex, conditionIndex, 'operator', value)}
                  >
                    <SelectTrigger className="w-[120px]">
                      <SelectValue placeholder="Operator" />
                    </SelectTrigger>
                    <SelectContent>
                      {operators.map((op) => (
                        <SelectItem key={op.value} value={op.value}>
                          {op.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Input
                    className="w-[80px]"
                    value={condition.value}
                    onChange={(e) => updateCondition(groupIndex, conditionIndex, 'value', e.target.value)}
                    placeholder="Value"
                  />
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => removeCondition(groupIndex, conditionIndex)}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              ))}
              <Button
                variant="outline"
                size="sm"
                onClick={() => addCondition(groupIndex)}
                className="w-full"
              >
                <Plus className="mr-2 h-4 w-4" />
                Add Condition
              </Button>
            </div>
          ))}
          {filters.length > 0 && (
            <Button
              variant="outline"
              size="sm"
              onClick={addGroup}
              className="w-full"
            >
              <Plus className="mr-2 h-4 w-4" />
              Add OR Group
            </Button>
          )}
        </div>
      </PopoverContent>
    </Popover>
  )
}
